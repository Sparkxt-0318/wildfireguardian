"""Differential test on real data: run the independent checker (checker.py) over

  (a) every recorded checked route in the six committed planner caches (planner/cache/*/*.json, route_checks with
      verdict checked_route; legs rebuilt by tools/explain_deadlines/plans.reconstruct_legs, which verifies the
      recorded route_sha256), and
  (b) the field's witness at every exact deadline L (one per destination spec and origin), plus an exhaustive search
      at L + 1 pruned only by fire-free static travel time (a pruned configuration cannot be accepted even with no
      fire at all), capped at --cap configurations.

The masks (closure intervals) come from the repository's reduction deadline_field.real.PacketModel, unchanged; the
checker only sees the edges and nodes the route uses (its verdict depends on nothing else).

    python3 research/kcf-theorem/differential_witnesses.py --data-root <fetched data/routing> --out <json>
"""
from __future__ import annotations

import argparse
import bisect
import glob
import heapq
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/harness-2026-11/F-3.1"))
import checker  # noqa: E402
from deadline_field.core import backward, issue_set, witness  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
from tools.explain_deadlines.plans import reconstruct_legs  # noqa: E402


def sub_instance(inst, legs):
    """Checker dict restricted to the edges and nodes of `legs` (indices into inst), renumbered."""
    E = [x for k, x, _, _ in legs if k == "EDGE"]
    edges = list(dict.fromkeys(E))
    nodes = list(dict.fromkeys([inst.tail[j] for j in edges] + [inst.head[j] for j in edges] +
                               [x for k, x, _, _ in legs if k == "WAIT"]))
    ei, ni = {j: i for i, j in enumerate(edges)}, {v: i for i, v in enumerate(nodes)}
    lst = lambda ivs: [[lo, hi] for lo, hi in ivs]  # noqa: E731
    d = {"H": inst.H, "n_nodes": len(nodes),
         "edges": [[ni[inst.tail[j]], ni[inst.head[j]], inst.D[j]] for j in edges],
         "waitable": [ni[v] for v in nodes if inst.waitable[v]],
         "forbidden": [[ei[a], ei[b]] for a, b in inst.forbidden if a in ei and b in ei],
         "B": {ei[j]: lst(inst.B[j]) for j in edges}, "A": {ei[j]: lst(inst.A[j]) for j in edges},
         "W": {ni[v]: lst(inst.W[v]) for v in nodes if inst.waitable[v]},
         "IB": {ni[v]: lst(inst.IB[v]) for v in nodes if v in inst.IB}, "AN": {}}
    route = [[k, ei[x] if k == "EDGE" else ni[x], a, b] for k, x, a, b in legs]
    return d, route, ni


def _in(ivs, t):
    i = bisect.bisect_right(ivs, (t, float("inf"))) - 1
    return i >= 0 and ivs[i][0] <= t <= ivs[i][1]


def brute_later(inst, o, t0, cap):
    """Exhaustive search departing o at t0 over (edge or None, time, admitted), pruned only by the fire-free static
    bound: time + h(node) > latest accepted arrival. Returns ('route', n) / ('none', n) / ('cap', n)."""
    if _in(inst.IB.get(o, []), t0):
        return "none", 0
    latest = max((hi for a in inst.A for lo, hi in a), default=-1)
    INF = 1 << 60
    h = [INF] * inst.n_nodes
    pq = [(0, inst.head[j]) for j, a in enumerate(inst.A) if a]
    for _, v in pq:
        h[v] = 0
    heapq.heapify(pq)
    while pq:
        dv, v = heapq.heappop(pq)
        if dv == h[v]:
            for j in inst.inc[v]:
                if dv + inst.D[j] < h[inst.tail[j]]:
                    h[inst.tail[j]] = dv + inst.D[j]
                    heapq.heappush(pq, (dv + inst.D[j], inst.tail[j]))
    seen, stack = set(), [(None, t0, False)]
    while stack:
        s, t, adm = stack.pop()
        if adm and _in(inst.A[s], t):
            return "route", len(seen)
        node = o if s is None else inst.head[s]
        nxt = []
        for j in inst.out[node]:
            arr = t + inst.D[j]
            if (s is not None and (s, j) in inst.forbidden) or arr > inst.H or _in(inst.B[j], t):
                continue
            if arr + h[inst.head[j]] <= latest:
                nxt.append((j, arr, True))
        if inst.waitable[node] and t + 1 <= inst.H and not _in(inst.W[node], t) and t + 1 + h[node] <= latest:
            nxt.append((s, t + 1, False))
        for c in nxt:
            if c not in seen:
                seen.add(c)
                stack.append(c)
                if len(seen) > cap:
                    return "cap", len(seen)
    return "none", len(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cap", type=int, default=2_000_000)
    ap.add_argument("--only", help="substring of the cache path to run (default: all six)")
    a = ap.parse_args()
    total, rows = Counter(), []
    for cp in sorted(glob.glob(str(ROOT / "planner/cache/*/*.json"))):
        if a.only and a.only not in cp:
            continue
        t0 = time.perf_counter()
        doc = json.loads(Path(cp).read_text())
        region, compact = doc["region_id"], doc["input_time"].replace("-", "").replace(":", "")
        pm = PacketModel(a.data_root / "graphs" / region / "graph.json",
                         a.data_root / "latest_inputs_try02/packets" / region / compact)
        eidx = {e: i for i, e in enumerate(pm.g.edge_ids)}
        specs = {}
        for key, job in sorted(doc["route_checks"].items()):
            q = job["request"]
            spec = (q["destination"]["node_id"], q["dwell_s"], tuple(q["destination_window"]))
            specs.setdefault(spec, {"origins": set(), "jobs": []})
            specs[spec]["origins"].add(q["start"]["node_id"])
            specs[spec]["jobs"].append((key, job))
        c = Counter()
        fails, capped = [], []
        for spec, sv in sorted(specs.items(), key=str):
            for var in ("router", "cert"):
                inst = pm.instance(var, [{"node": spec[0], "dwell": spec[1], "window": list(spec[2])}],
                                   sorted(sv["origins"]))
                for key, job in sv["jobs"]:
                    if (job.get("result") or {}).get("verdict") != "checked_route":
                        continue
                    rl = reconstruct_legs(job)
                    legs = [("EDGE", eidx[l["edge"]], l["start"], l["end"]) if l["kind"] == "EDGE"
                            else ("WAIT", pm.nidx[l["node"]], l["start"], l["end"]) for l in rl["legs"]]
                    d, route, ni = sub_instance(inst, legs)
                    ok, why = checker.check_route(d, ni[pm.nidx[rl["start_node"]]], rl["departure"], route)
                    c["recorded_%s:%s" % (var, "VALID" if ok else "INVALID")] += 1
                    if not ok and len(fails) < 20:
                        fails.append({"job": key, "variant": var, "why": why})
                if var != "router":
                    continue
                fld = backward(inst)
                for o in sorted(sv["origins"]):
                    oi = pm.nidx[o]
                    S = issue_set(fld, oi)
                    if not S:
                        c["deadline:empty_set"] += 1
                        continue
                    L = S[-1][1]
                    w = witness(fld, oi, L)
                    d, route, ni = sub_instance(inst, w[1])
                    if not route:
                        d["n_nodes"], d["IB"] = 1, {0: [[lo, hi] for lo, hi in inst.IB.get(oi, [])]}
                        ni = {oi: 0}
                    ok, why = checker.check_route(d, ni[oi], L, route)
                    c["deadline_witness:%s" % ("VALID" if ok else "INVALID")] += 1
                    if not ok and len(fails) < 20:
                        fails.append({"origin": o, "spec": spec, "L": L, "why": why})
                    if L + 1 <= inst.H:
                        res, n = brute_later(inst, oi, L + 1, a.cap)
                        c["L_plus_1:%s" % res] += 1
                        c["L_plus_1:configs_explored"] += n
                        if res == "cap":
                            capped.append({"origin": o, "spec": spec, "L": L})
                        if res == "route" and len(fails) < 20:
                            fails.append({"origin": o, "spec": spec, "L+1": L + 1, "why": "route found"})
        row = {"cache": str(Path(cp).relative_to(ROOT)), "counts": dict(sorted(c.items())), "failures": fails, "L_plus_1_capped": capped,
               "seconds": round(time.perf_counter() - t0, 1)}
        print(json.dumps(row, default=str), flush=True)
        rows.append(row)
        total.update(c)
    a.out.write_text(json.dumps({"total": dict(sorted(total.items())), "per_cache": rows}, indent=1, default=str))
    print(json.dumps(dict(sorted(total.items()))))


if __name__ == "__main__":
    main()
