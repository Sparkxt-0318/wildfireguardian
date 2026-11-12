"""Unknown-support three-way rule on the 20 Korean missions (orchestrator decision; definitions from Iris, 2026-11-12).

UNKNOWN = U_state ∪ U_q with, from the packet's native masks (constructed_arrays.npz),
  U_state = mask__unknown_cumulative_state
  U_q     = mask__policy_assigned_zero ∧ ¬mask__known_burned ∧ ¬U_state
Optimistic instance  = the frozen instance (unknown treated as no fire).
Pessimistic instances = frozen activity ∪ extra activity on unknown cells, same cell→road footprint rule as flame:
  Tier A        every UNKNOWN cell active on [0, H]
  Tier B(v)     U_state active on [0, H]; a U_q cell at centre distance d from S0 = present fire ∪ U_state ∪
                positive native probability is active on [d / v, H] (not at all if d / v > H); v = 1.5 and 8.2 km/h.
Label: checked = ROUTE in the pessimistic instance (certificate accepted by both checkers); no_route = NO_ROUTE in the
optimistic instance (certificate accepted by both checkers); otherwise unresolved.
NOT done here: Iris's §4 dose/peak precondition with U_state cells as possible radiation sources (contact relaxation
only), and the full-policy checker on pessimistic witnesses.

Usage: python unknown_support.py --out DIR --c-checker PATH
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from fractions import Fraction as F
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p1_check as P1  # noqa: E402
import cases  # noqa: E402
import generate  # noqa: E402
from wfg_scenario_members.contact import ContactModel  # noqa: E402
from wfg_sipp.frontend import build_instance  # noqa: E402

KMH = {"B1.5": F(15, 10), "B8.2": F(82, 10)}


class Augmented:
    """Duck-typed contact model: the frozen cell intervals plus extra half-open intervals per graph cell."""

    def __init__(self, base, extra):
        u = {c: list(v) for c, v in base.cell_intervals.items()}
        for c, iv in extra.items():
            u.setdefault(c, []).append(iv)
        self.cell_intervals = {c: sorted(set(v)) for c, v in u.items()}
        self.supported = True
        self.ids = base.ids


def masks(packet):
    with np.load(Path(packet) / "constructed_arrays.npz", allow_pickle=False) as a:
        P1.require_routable_arrays(a, packet)          # refuse HAZARD-only packets loudly (Leo 588f74e)
        m = {k: a["mask__" + k].astype(bool) for k in ("unknown_cumulative_state", "policy_assigned_zero", "known_burned",
                                                         "positive_native_probability")}
        cur = a["current_active"].astype(bool)
    u_state = m["unknown_cumulative_state"]
    u_q = m["policy_assigned_zero"] & ~m["known_burned"] & ~u_state
    s0 = cur | u_state | m["positive_native_probability"]
    return u_state, u_q, s0


def extra_intervals(model, graph, u_state, u_q, s0, H, tier):
    """{graph cell: (b, e)} with e = H + 1 (half-open, so [b, H] is covered)."""
    Hn, W = u_state.shape
    res = F(graph["grid"]["resolution"])
    end = F(H) + 1
    out = {}
    for r, c in zip(*np.nonzero(u_state)):
        out[model._g(int(r) * W + int(c))] = (F(0), end)
    if tier == "A":
        for r, c in zip(*np.nonzero(u_q)):
            out[model._g(int(r) * W + int(c))] = (F(0), end)
        return out
    v = KMH[tier] * 1000 / 3600                       # m/s, exact rational
    src = np.argwhere(s0)
    for r, c in zip(*np.nonzero(u_q)):
        if len(src) == 0:
            break
        d2 = int(((src - np.array([r, c])) ** 2).sum(axis=1).min())   # squared cell-centre distance in cells
        # d / v <= H  <=>  d^2 <= (H v)^2 ; start = ceil-free exact rational via sqrt bound: use the exact
        # comparison for inclusion and a rational upper bound on d for the start (conservative = earlier start)
        d_m_sq = F(d2) * res * res
        if d_m_sq > (F(H) * v) ** 2:
            continue
        d_lo = F(int(np.floor(np.sqrt(float(d_m_sq)))))          # floor(d) <= d  -> earlier (more blocking) start
        while d_lo * d_lo > d_m_sq:
            d_lo -= 1
        out[model._g(int(r) * W + int(c))] = (max(F(0), d_lo / v), end)
    return out


def certify_and_check(inst, path, c_checker):
    claim, T, text, ih, st = generate.certify(inst)
    path.write_text(text)
    py = subprocess.run([sys.executable, str(HERE / "check_py.py"), str(path)], capture_output=True, text=True).stdout.strip()
    cc = subprocess.run([c_checker, str(path)], capture_output=True, text=True).stdout.strip()
    # both checkers must accept AND agree with the generator's claim and threshold (Mira, sign-off (c))
    ok = py == cc == "ACCEPT %s %s" % (claim, T)
    return dict(claim=claim, T=T, instance_sha256=ih, py=py, c=cc, accepted=ok, blocked_edges=len(inst.edge_block))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--c-checker", required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rows, packets = [], {}
    for c in cases.korean_cases():
        g = json.loads(Path(c["graph"]).read_text()); r = json.loads(Path(c["request"]).read_text())
        model = ContactModel.from_packet(c["packet"])
        u_state, u_q, s0 = masks(c["packet"])
        if u_state.shape != (g["grid"]["height"], g["grid"]["width"]):
            raise RuntimeError("GRID_MISMATCH " + c["mission"])
        packets[c["region"] + "/" + c["mission"].split("_")[0]] = dict(cells=int(u_state.size), U_state=int(u_state.sum()),
                                                                       U_q=int(u_q.sum()), S0=int(s0.sum()))
        H = int(F(r["horizon"]))
        row = dict(mission=c["mission"], region=c["region"])
        inst_opt, _ = build_instance(g, r, model)
        row["optimistic"] = certify_and_check(inst_opt, out / (c["mission"] + "__opt.wfgc"), a.c_checker)
        for tier in ("A", "B1.5", "B8.2"):
            extra = extra_intervals(model, g, u_state, u_q, s0, H, tier)
            inst_p, _ = build_instance(g, r, Augmented(model, extra))
            res = certify_and_check(inst_p, out / ("%s__pess_%s.wfgc" % (c["mission"], tier)), a.c_checker)
            res["extra_cells"] = len(extra)
            row["pess_" + tier] = res
            opt = row["optimistic"]
            if res["claim"] == "ROUTE" and res["accepted"]:
                label = "checked"
            elif opt["claim"] == "NO_ROUTE" and opt["accepted"]:
                label = "no_route"
            else:
                label = "unresolved"
            row["label_" + tier] = label
        rows.append(row)
        print(json.dumps({k: row[k] for k in ("mission", "label_A", "label_B1.5", "label_B8.2")}
                         | {"opt": "%s %s" % (row["optimistic"]["claim"], row["optimistic"]["T"]),
                            "pessA": "%s %s" % (row["pess_A"]["claim"], row["pess_A"]["T"]),
                            "pessB8.2": "%s %s" % (row["pess_B8.2"]["claim"], row["pess_B8.2"]["T"])}), flush=True)
    (HERE / "results" / "unknown_support.json").write_text(json.dumps({"packets": packets, "rows": rows}, indent=1) + "\n")


if __name__ == "__main__":
    main()
