"""X1 (PASS_RULES.md): does the router's ContactModel see the same hazard as the packet's HAZARD.json?

For each packet: (0) the raw arrays are routable (p1_check.require_routable_arrays; a HAZARD-only packet is reported
REFUSED, never read); (1) same active cell set on [0, H); (2) per cell, same interval count and starts, ends equal or
within 1 µs; (3) for EVERY origin of the INSTANCE.json entry and each departure, frontend.build_instance on HAZARD
intervals equals the one on ContactModel intervals; (4) the independent raw re-derivation p1_check.from_raw equals
ContactModel exactly. Exit status 1 if any packet fails or is refused.

Usage: python x1_packets.py --leo WORKTREE --packets REL... [--departures 0 7200] [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction as F
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import p1_check as P  # noqa: E402
from wfg_scenario_members.contact import ContactModel  # noqa: E402
from wfg_sipp.frontend import build_instance, prepared  # noqa: E402

US = F(1, 10**6)


def classify(haz, con):
    """Counts per X1 rules 1 and 2: cells only on one side, identical, end-only within 1 µs, other."""
    out = dict(only_hazard=0, only_contact=0, identical=0, end_within_1us=0, other=0, examples=[])
    for k in sorted(set(haz) | set(con)):
        a, b = haz.get(k), con.get(k)
        if a is None or b is None:
            out["only_hazard" if b is None else "only_contact"] += 1
            if len(out["examples"]) < 3:
                out["examples"].append([k, str(a), str(b)])
        elif a == b:
            out["identical"] += 1
        elif len(a) == len(b) and all(x0 == y0 and abs(x1 - y1) < US for (x0, x1), (y0, y1) in zip(a, b)):
            out["end_within_1us"] += 1
        else:
            out["other"] += 1
            if len(out["examples"]) < 3:
                out["examples"].append([k, str(a[:2]), str(b[:2])])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--leo", required=True)
    ap.add_argument("--packets", nargs="+", required=True)
    ap.add_argument("--departures", type=int, nargs="+", default=[0, 7200])
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    L = Path(a.leo) / "research/harness-2026-11/F-DYN/_data"
    instances = json.loads((L / "INSTANCE.json").read_text())["instances"]
    graphs, rows = {}, []
    for rel in a.packets:
        pk = Path(a.leo) / rel
        name, region = pk.name, pk.parent.name
        start = name.split("_")[0]
        H = int(name.split("_h")[1].split("_")[0]) * 3600
        variant = name.split("_h%d_" % (H // 3600), 1)[1].rsplit("_central_", 1)[0]
        hz = json.loads((pk / "HAZARD.json").read_text())
        Hs = F(H)
        haz = {k: v for k, v in P.from_hazard(hz, Hs).items() if v}
        try:
            with np.load(pk / "constructed_arrays.npz", allow_pickle=False) as arr:
                P.require_routable_arrays(arr, pk)
            con = {k: v for k, v in ((k, P.merge(v, F(0), Hs)) for k, v in ContactModel.from_packet(pk).cell_intervals.items()) if v}
            raw = {k: v for k, v in P.from_raw(pk, Hs).items() if v}
        except Exception as e:                          # HAZARD-only packet: refused by design, reported, never read
            row = dict(packet=rel, variant=variant, region=region, start=start, writer=P.writer_identity(hz),
                       active_hazard=len(haz), REFUSED=str(e)[:200], PASS=False)
            rows.append(row); print(json.dumps(row), flush=True)
            continue
        raw_vs_contact = sum(raw.get(k) != con.get(k) for k in set(raw) | set(con))
        c = classify(haz, con)
        if region not in graphs:
            g = json.loads((L / "graphs_interim" / region / "graph.json").read_text())
            graphs[region] = (g, prepared(g))
        g, pg = graphs[region]
        # origins are the region's graph entry nodes (the same for every start of a region and horizon); a synthetic
        # start has no entry of its own, so fall back to the region/horizon entry and record which one was used
        same = [i for i in instances if i["region"] == region and i["horizon_s"] == H]
        entry = next((i for i in same if i["start_tag"] == start), same[0])

        class HzModel:
            cell_intervals = haz
            supported = True

        class CoModel:
            cell_intervals = con
            supported = True
        n = eq = 0
        bad = []
        for o in entry["origins"]:
            for dep in a.departures:
                req = {"position": {"node": o["entry_node"]}, "incoming_edge": None, "departure": dep, "horizon": H,
                       "destinations": [{"node": d["node"], "dwell": d["dwell_s"], "open_intervals": [[0, H]]} for d in o["destinations"]]}
                i1, _ = build_instance(g, req, HzModel, prepared_graph=pg)
                i2, _ = build_instance(g, req, CoModel, prepared_graph=pg)
                same = (i1.edge_block, i1.wait_block, i1.accept) == (i2.edge_block, i2.wait_block, i2.accept)
                n += 1; eq += same
                if not same and len(bad) < 3:
                    bad.append([o["origin_id"], dep])
        ok = c["only_hazard"] == c["only_contact"] == c["other"] == 0 and eq == n and raw_vs_contact == 0
        row = dict(packet=rel, variant=variant, region=region, start=start, writer=P.writer_identity(hz),
                   active_hazard=len(haz), active_contact=len(con),
                   **{k: v for k, v in c.items() if k != "examples"}, instances_equal=eq, instances_compared=n,
                   raw_vs_contact=raw_vs_contact, origins_from=entry["start_tag"],
                   PASS=ok, examples=c["examples"], instance_mismatch_examples=bad)
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if "examples" not in k}), flush=True)
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=1) + "\n")
    return 0 if all(r["PASS"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
