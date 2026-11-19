"""T1 (brute force) and T2 (unlimited capacity vs the deadline field) of PROTOCOL section 5.
Usage: python3 -m kq.run_t1_t2 T1 N_NETWORKS OUT.json   |   T2 N OUT.json   (from research/kcf-queue)"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from . import brute, randnet, solver

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research/harness-2026-11/F-3.1"))


def t1(n_nets, out):
    rep = {"networks": 0, "cases": 0, "soundness_violations": [], "solver_feasible_brute_not": 0, "brute_feasible_solver_not": 0,
           "agree_feasible": 0, "agree_infeasible": 0, "networks_with_any_gap": 0, "max_tmax": 12, "examples_gap": []}
    for seed in range(n_nets):
        net, o, sh = randnet.make(seed)
        rnd = random.Random(10_000 + seed)
        N, W = rnd.randint(1, 3), rnd.randint(0, 3)
        ctx = solver.Ctx(net, o, sh)
        rep["networks"] += 1
        gap = False
        for s in range(0, 11):
            rel = solver.releases(N, s, W)
            sol = solver.try_start(net, ctx, N, s, W, {}) is not None
            bru = brute.feasible(net, o, sh, rel, 12)
            rep["cases"] += 1
            if sol and not bru:
                rep["soundness_violations"].append({"seed": seed, "s": s, "N": N, "W": W})
                rep["solver_feasible_brute_not"] += 1
            elif bru and not sol:
                rep["brute_feasible_solver_not"] += 1
                gap = True
                if len(rep["examples_gap"]) < 5:
                    rep["examples_gap"].append({"seed": seed, "s": s, "N": N, "W": W})
            elif sol:
                rep["agree_feasible"] += 1
            else:
                rep["agree_infeasible"] += 1
        rep["networks_with_any_gap"] += gap
    Path(out).write_text(json.dumps(rep, indent=1))
    print({k: v for k, v in rep.items() if k != "examples_gap"})


def t2(n_nets, out):
    from deadline_field import core
    rep = {"networks": 0, "start_seconds_compared": 0, "mismatches": [], "L0_mismatches": 0}
    for seed in range(n_nets):
        net, o, sh = randnet.make(5_000_000 + seed, unlimited=True, max_t=14)
        H = 14
        E = net.E
        B = [[(net.lo[j], H)] if net.lo[j] <= H else [] for j in range(E)]
        Wt = [[(max(net.wcut[u] - 1, 0), H)] if net.wcut[u] <= H + 1 else [] for u in range(net.n)]
        A = [[] for _ in range(E)]
        for v, amax in sh.items():
            for j in net.inc[v]:
                A[j] = [(0, amax)] if amax >= 0 else []
        IB = {o: [(net.wcut[o], H)] if net.wcut[o] <= H else []}
        inst = core.Instance(H=H, n_nodes=net.n, tail=net.tail, head=net.head, D=net.D, waitable=[True] * net.n,
                             forbidden=set(net.forbid), B=B, W=Wt, A=A, IB=IB)
        fld = core.backward(inst)
        feas = set()
        for a, b in core.issue_set(fld, o):
            feas.update(range(a, b + 1))
        ctx = solver.Ctx(net, o, sh)
        rep["networks"] += 1
        mine = set()
        for t in range(0, H + 1):
            if solver.route(net, ctx, t, {}) is not None:
                mine.add(t)
            rep["start_seconds_compared"] += 1
        if mine != feas:
            rep["mismatches"].append({"seed": seed, "field": sorted(feas), "mine": sorted(mine)})
        L = ctx.L0(net)
        if (max(feas) if feas else None) != L:
            rep["L0_mismatches"] += 1
    Path(out).write_text(json.dumps(rep, indent=1))
    print({k: (v if k != "mismatches" else len(v)) for k, v in rep.items()})


if __name__ == "__main__":
    {"T1": t1, "T2": t2}[sys.argv[1]](int(sys.argv[2]), sys.argv[3])
