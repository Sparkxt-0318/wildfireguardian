"""Independent cross-check against the kit's own dense backward sweep (integration/kit/phaseB/zsweep.py,
``EarliestArrivalBound``, unchanged frozen code by other authors): exact-activity contact on router cell pieces,
int16 earliest-arrival table C[t, state] for every second.

For sampled (origin, destination) pairs: build the kit's table with departure 0 and compare, for EVERY second
t in [0, H], (a) feasibility: C[t, issue] < INF  <=>  t in our router-field issue_core (the kit table has no issue-point
check), and (b) earliest arrival: C[t, issue] == our witness arrival (on all boundary seconds of the feasible set and
every k-th second).

The kit model's ``cell_intervals`` are built exactly as road_bounds.RoadBoundModel builds them (exact phases
[b, b + T) per first-new ignition, [0, R) for present fire), here from the npz via tools/explain_deadlines/packet.py.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "integration" / "kit" / "phaseB"))
sys.path.insert(0, str(ROOT / "integration" / "kit" / "routing_candidate" / "baseline" / "routing-package"))

import zsweep  # noqa: E402  (frozen kit code)
from routing import core as kit_core  # noqa: E402  (kit's geometry provider)

from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_core, witness  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402


class _Model:
    def __init__(self, pk):
        ci = {}
        for s in range(pk.S):
            for c, (b, xe, _xr, kind) in pk.phases[s].items():
                ci.setdefault(c, []).append((b, xe))
        self.cell_intervals = {k: sorted(set(v)) for k, v in ci.items()}


def crosscheck(region, compact, pairs, *, data_root, every=7, seed=0):
    graph_path = data_root / "graphs" / region / "graph.json"
    packet_dir = data_root / "latest_inputs_try02" / "packets" / region / compact
    pm = PacketModel(graph_path, packet_dir)
    graph = pm.raw
    hazard = {"dt": 1}
    model = _Model(pm.pk)
    rows = []
    for o, d, dwell, window in pairs:
        req = {"departure": 0, "horizon": pm.H, "position": {"node": o}, "incoming_edge": None,
               "destinations": [{"node": d, "dwell": dwell, "open_intervals": [list(window)]}]}
        t0 = time.perf_counter()
        ea = zsweep.EarliestArrivalBound(graph, hazard, req, model, kit_core)
        kit_s = time.perf_counter() - t0
        t1 = time.perf_counter()
        inst = pm.instance("router", [{"node": d, "dwell": dwell, "window": list(window)}], [])
        fld = backward(inst)
        ours_s = time.perf_counter() - t1
        oi = pm.nidx[o]
        core = issue_core(fld, oi)
        S = iv.to_set(core)
        mism_feas = []
        kit_feas = set()
        for t in range(0, pm.H + 1):
            b = ea.bound(o, None, t, True)
            if b != float("inf"):
                kit_feas.add(t)
        mism_feas = sorted(S ^ kit_feas)
        probe = set(range(0, pm.H + 1, every))
        for lo, hi in core:
            probe.update({lo, hi})
        mism_arr = []
        n_arr = 0
        for t in sorted(probe):
            if t not in S or t not in kit_feas:
                continue
            w = witness(fld, oi, t)
            n_arr += 1
            kb = ea.bound(o, None, t, True)
            if w is None or w[0] != kb:
                mism_arr.append((t, kb, None if w is None else w[0]))
        rows.append({"origin": o, "destination": d, "dwell": dwell, "window": window,
                     "seconds_compared": pm.H + 1, "feasible_seconds": len(S), "feasibility_mismatches": mism_feas[:20],
                     "n_feasibility_mismatches": len(mism_feas), "arrivals_compared": n_arr,
                     "arrival_mismatches": mism_arr[:20], "n_arrival_mismatches": len(mism_arr),
                     "kit_sweep_s": kit_s, "our_field_s": ours_s})
        print(json.dumps(rows[-1]), flush=True)
    return rows


def sample_pairs(cache_path: Path, k: int, seed: int):
    doc = json.loads(cache_path.read_text())
    pairs = sorted({(rc["request"]["start"]["node_id"], rc["request"]["destination"]["node_id"], rc["request"]["dwell_s"],
                     tuple(rc["request"]["destination_window"])) for rc in doc["route_checks"].values()}, key=str)
    rnd = random.Random(seed)
    return doc["region_id"], doc["input_time"].replace("-", "").replace(":", ""), rnd.sample(pairs, min(k, len(pairs)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("caches", nargs="+", type=Path)
    ap.add_argument("--pairs", type=int, default=3)
    ap.add_argument("--seed", type=int, default=20261112)
    ap.add_argument("--every", type=int, default=7)
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "routing")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    allrows = []
    for c in a.caches:
        region, compact, pairs = sample_pairs(c, a.pairs, a.seed)
        rows = crosscheck(region, compact, pairs, data_root=a.data_root, every=a.every)
        for r in rows:
            r["cache"] = str(c)
        allrows.extend(rows)
    a.out.write_text(json.dumps(allrows, indent=1, default=str))
    bad = sum(r["n_feasibility_mismatches"] + r["n_arrival_mismatches"] for r in allrows)
    print("PAIRS", len(allrows), "SECONDS", sum(r["seconds_compared"] for r in allrows),
          "ARRIVALS", sum(r["arrivals_compared"] for r in allrows), "MISMATCHES", bad)


if __name__ == "__main__":
    main()
