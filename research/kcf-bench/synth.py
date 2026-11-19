"""Scaling (PLAN.md 6): method B on synthetic road grids larger than the recorded graphs.

    python3 synth.py SIDE OUT_JSON

Frozen generator (seed 20261120): a SIDE x SIDE grid of nodes 150 m apart, every neighbour pair joined by two directed
edges (4*SIDE*(SIDE-1) edges), U-turns forbidden, every node waitable. Travel ticks per undirected road from a seeded
choice of 30/50/70 km/h (18/11/8 s). H = 3600 s. One circular fire front from (0.2*L, 0.5*L), L = SIDE*150 m, radius
0.05*L at t = 0 growing linearly to 0.25*L at t = H, so the burning share of the graph is the same at every size. Contact
sets: an edge whose nearer end ignites at t_i is blocked for starts [t_i - D, H]; a wait at a node igniting at t_i for
[t_i - 1, H]; issue points likewise from t_i. Five destination specs (nodes on the far edge, dwell 120 s, window
[0, 3600]), 100 seeded origins. Per spec, exactly as run_b.py does: build the Instance, run `core.backward`, read the
issue set of every origin, and a forward witness at departure 0 where feasible. Stops early (recorded) if 30 min
elapse or peak RSS passes 12 GiB (checked between specs).
"""
from __future__ import annotations

import json
import math
import random
import resource
import sys
import time
from pathlib import Path

T_START = time.perf_counter()
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, SAMPLE_SEED  # noqa: E402

sys.path.insert(0, str(ROOT / "research" / "harness-2026-11" / "F-3.1"))
from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import Instance, backward, issue_set, witness  # noqa: E402

H, DWELL, SP = 3600, 120, 150.0
TIME_CAP_S, RSS_CAP_MIB = 1800.0, 12 * 1024
SCALE = 1.0 if sys.platform == "darwin" else 1024.0


def rss_mib():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * SCALE / 2 ** 20


def main():
    side, out = int(sys.argv[1]), Path(sys.argv[2])
    rnd = random.Random("%d:synth:%d" % (SAMPLE_SEED, side))
    t0 = time.perf_counter()
    n = side * side
    L = side * SP
    cx, cy, r0, r1 = 0.2 * L, 0.5 * L, 0.05 * L, 0.25 * L
    v = (r1 - r0) / H

    def t_ign(node):
        x, y = (node % side) * SP, (node // side) * SP
        d = math.hypot(x - cx, y - cy)
        return 0 if d <= r0 else math.ceil((d - r0) / v)      # may exceed H: never burns inside the horizon

    ign = [t_ign(i) for i in range(n)]
    tail, head, D = [], [], []
    for y in range(side):
        for x in range(side):
            u = y * side + x
            for (xx, yy) in ((x + 1, y), (x, y + 1)):
                if xx < side and yy < side:
                    w = yy * side + xx
                    d = rnd.choice((18, 11, 8))
                    tail += [u, w]; head += [w, u]; D += [d, d]
    E = len(tail)
    forbidden = {(j, j ^ 1) for j in range(E)}            # edges 2k and 2k+1 are each other's reverse
    B = [[(min(ign[tail[j]], ign[head[j]]) - D[j], H)] if min(ign[tail[j]], ign[head[j]]) <= H else [] for j in range(E)]
    W = [[(ign[i] - 1, H)] if ign[i] <= H else [] for i in range(n)]
    origins = sorted(rnd.sample(range(n), 100))
    IB = {o: ([(ign[o], H)] if ign[o] <= H else []) for o in origins}
    dests = sorted(rnd.sample([y * side + side - 1 for y in range(side)], 5))
    t_build = time.perf_counter() - t0
    per_spec, stopped = [], None
    for dn in dests:
        if time.perf_counter() - T_START > TIME_CAP_S:
            stopped = "time cap"; break
        if rss_mib() > RSS_CAP_MIB:
            stopped = "memory cap"; break
        t1 = time.perf_counter()
        an = iv.subtract_all(iv.normalize([(0, H - DWELL)]), iv.normalize([(ign[dn] - DWELL, H)] if ign[dn] <= H else []))
        A = [list(an) if head[j] == dn else [] for j in range(E)]
        inst = Instance(H=H, n_nodes=n, tail=tail, head=head, D=D, waitable=[True] * n, forbidden=forbidden,
                        B=B, W=W, A=A, IB=IB, AN={dn: an})
        t_inst = time.perf_counter() - t1
        t2 = time.perf_counter()
        fld = backward(inst)
        t_back = time.perf_counter() - t2
        t3 = time.perf_counter()
        feas = {o: issue_set(fld, o) for o in origins if o != dn}
        wit = sum(1 for o, f in feas.items() if iv.contains(f, 0) and witness(fld, o, 0) is not None)
        t_read = time.perf_counter() - t3
        per_spec.append({"dest": dn, "instance_s": t_inst, "backward_s": t_back, "issue_and_witness_s": t_read,
                         "pieces": fld.stats["pieces"], "origins_feasible_at_0": wit,
                         "origins_with_any_feasible": sum(1 for f in feas.values() if f), "rss_mib_after": rss_mib()})
        del fld, inst, A
    rec = {"side": side, "nodes": n, "edges": E, "burning_edges_within_H": sum(1 for b in B if b), "build_s": t_build,
           "specs_done": len(per_spec), "specs_planned": len(dests), "stopped": stopped, "per_spec": per_spec,
           "total_in_process_s": time.perf_counter() - T_START, "peak_rss_mib_self": rss_mib()}
    out.write_text(json.dumps(rec, indent=1))
    print(json.dumps({k: rec[k] for k in ("side", "edges", "specs_done", "stopped", "total_in_process_s", "peak_rss_mib_self")}))


if __name__ == "__main__":
    main()
