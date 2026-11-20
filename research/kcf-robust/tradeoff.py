"""Secondary: the whole knob range of b (m), c (r) and e (p), not only the calibrated values (PROTOCOL section 6,
secondary). Route-independent, from the stored latest-departure curves:

  unsafe     leave-by L_X >= 0 later than the truth's latest safe departure L_T (no route at all is safe at L_X;
             every such advised departure is a failed evacuation, whatever the route);
  given up   median of (L_T - L_X) / 60 over place-pairs the truth cuts with L_T >= 0 (lead time given up).

    python3 tradeoff.py twin OUT | python3 tradeoff.py replay OUT
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

M_GRID = list(range(0, 28800 + 1, 300))
R_GRID = [round(0.125 * i, 3) for i in range(121)]
OTHER = ["e50", "e80", "e90", "e95", "e99", "a80", "a", "truth"]


def tags(kind):
    if kind == "twin":
        import run_twin as RT
        return [("twin", "s%d_h%d" % (s, h)) for s, h in RT.pairs()]
    return [("replay", "%s_%s" % (rid, T.strftime("%H"))) for rid in lib.REGIONS for T in lib.REPLAY_ISSUES]


def load(out, sub, tag):
    res = json.loads((out / sub / (tag + ".json")).read_text())
    z = np.load(out / sub / (tag + "_curves.npz"))
    cur = {}
    for k in z.files:
        kind, oid = k.split("|", 1)
        cur.setdefault(kind, {})[oid] = z[k]
    return res, cur


def main(kind, out):
    out = Path(out)
    LT, CUT, X = [], [], {}
    for sub, tag in tags(kind):
        res, cur = load(out, sub, tag)
        refused = {pid for k in res["rules"] for pid, r in res["rules"][k].items() if r["refused"]}
        for pid in sorted(res["rules"]["a"]):
            if pid in refused:
                continue
            t = res["rules"]["truth"][pid]
            o = cur["other"][pid]
            assert int(o[-1]) == int(t["L"]), (tag, pid, int(o[-1]), t["L"])
            LT.append(int(t["L"]))
            CUT.append(t["cut"] is not None)
            X.setdefault("b", []).append(cur["b"][pid])
            X.setdefault("c", []).append(cur["c"][pid])
            X.setdefault("o", []).append(o)
    LT, CUT = np.asarray(LT), np.asarray(CUT)
    lead_set = CUT & (LT >= 0)
    rows = []

    def add(knob, value, L):
        L = np.asarray(L)
        rows.append({"knob": knob, "value": value, "n": len(L), "unsafe": int(((L >= 0) & (L > LT)).sum()),
                     "lead_n": int(lead_set.sum()),
                     "lead_given_up_median_min": float(np.median((LT[lead_set] - L[lead_set]) / 60.0)),
                     "lead_given_up_mean_min": float(np.mean((LT[lead_set] - L[lead_set]) / 60.0))})

    B, C, O = np.stack(X["b"]), np.stack(X["c"]), np.stack(X["o"])
    for i, m in enumerate(M_GRID):
        add("b_m_s", m, B[:, i])
    for i, r in enumerate(R_GRID):
        add("c_r_km", r, C[:, i])
    for i, name in enumerate(OTHER):
        add("other", name, O[:, i])
    fp = out / ("tradeoff_%s.csv" % kind)
    with open(fp, "w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        if r["knob"] == "other" or (r["knob"] == "b_m_s" and r["value"] % 1800 == 0) or (r["knob"] == "c_r_km" and r["value"] in (0, 0.5, 1, 2, 3, 4, 5, 7.5, 10, 15)):
            print("%-7s %-6s unsafe %4d / %d  given up median %7.1f mean %7.1f min" % (
                r["knob"], r["value"], r["unsafe"], r["n"], r["lead_given_up_median_min"], r["lead_given_up_mean_min"]))


if __name__ == "__main__":
    if sys.argv[1] == "twin":
        sys.path.insert(0, str(lib.REPO / "research/kcf-validate/twin"))
    main(sys.argv[1], sys.argv[2])
