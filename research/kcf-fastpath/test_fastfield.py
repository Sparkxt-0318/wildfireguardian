"""Equality tests on random instances (PROTOCOL.md, test E3): the fast solver against the unchanged
``deadline_field.core.backward``, and against the independent brute force of ``research/kcf-theorem/checker.py``.

    python3 research/kcf-fastpath/test_fastfield.py [N_PER_FAMILY] [OUT_JSON]

Families: ``general`` and ``closure`` from ``research/kcf-theorem/randgraphs.py`` (small, brute-forced), plus
``mixed``: larger graphs (up to 40 nodes, 120 edges, H up to 90) where most closures are permanent and a few roads
reopen, a few waits reopen and a few shelters open late, so that scalar and interval states sit side by side.
Every variant (scalar alone, pruning alone, both, neither; scalar with the plain THEOREM.md hypotheses) is compared state by state and origin by origin.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "kcf-theorem"))
import fastfield as ff  # noqa: E402
import randgraphs  # noqa: E402
import checker  # noqa: E402
from deadline_field import core  # noqa: E402
from deadline_field import intervals as iv  # noqa: E402

VARIANTS = [("neither", False, False, True), ("scalar", True, False, True), ("prune", False, True, True),
            ("both", True, True, True), ("scalar_plain", True, False, False), ("both_plain", True, True, False)]


def mixed(rng):
    n = rng.randint(3, 40)
    H = rng.randint(10, 90)
    E = rng.randint(2, min(120, 4 * n))
    edges = []
    for _ in range(E):
        u = rng.randrange(n)
        v = rng.randrange(n - 1)
        v = v + 1 if v >= u else v
        edges.append([u, v, rng.randint(1, 8)])
    shelters = set(rng.sample(range(n), rng.randint(1, min(3, n))))
    waitable = [v for v in range(n) if rng.random() < 0.4]
    inc = {}
    for j, (u, v, _) in enumerate(edges):
        inc.setdefault(v, []).append(j)
    forbidden = [[i, j] for j, (u, _, _) in enumerate(edges) for i in inc.get(u, []) if rng.random() < 0.1]
    p_bad = rng.choice([0.0, 0.02, 0.05, 0.15])
    gen = lambda: randgraphs._random_ivs(rng, H)  # noqa: E731
    acc = {d: (gen() if rng.random() < p_bad else randgraphs._prefix(rng, H)) for d in shelters}
    B, W, A, IB, AN = {}, {}, {}, {}, {}
    for j, (u, v, _) in enumerate(edges):
        B[j] = gen() if rng.random() < p_bad else randgraphs._suffix(rng, H, 0.6)
        if v in shelters:
            A[j] = acc[v]
    for v in waitable:
        W[v] = gen() if rng.random() < p_bad else randgraphs._suffix(rng, H, 0.6)
    for o in range(n):
        if rng.random() < 0.3:
            IB[o] = gen() if rng.random() < p_bad else randgraphs._suffix(rng, H, 0)
        if o in shelters and rng.random() < 0.2:
            AN[o] = acc[o]
    chk = {"H": H, "edges": edges, "waitable": waitable, "forbidden": forbidden,
           "B": B, "W": W, "A": A, "IB": IB, "AN": AN, "n_nodes": n}
    return randgraphs.to_instance(chk), chk


def clip(ivs, lo, H):
    return [(max(a, lo), min(b, H)) for a, b in ivs if b >= lo and a <= H]


def check_variant(inst, chk, ref, ref_feas, brute, nodes, subset, vname, sc, pr, wd, tally, fails, kinds, family,
                  case):
        f = ff.solve(inst, scalar=sc, prune_origins=subset if pr else None, windows=wd)
        for kk, vv in f.stats["kinds"].items():
            kinds[(family, vname, kk)] += vv
        tally["fixed_point_checks"] += 1
        try:
            ff.check_fixed_point(f)
        except AssertionError as exc:
            fails.append((family, case, vname, "fixed_point", str(exc)[:200]))
        E = len(inst.tail)
        for s in range(E):
            lo = f.lo[s]
            want_R = clip(ref.R[s], lo, inst.H) if pr else ref.R[s]
            want_G = clip(ref.G[s], lo, inst.H) if pr else ref.G[s]
            tally["state_sets"] += 1
            if f.R[s] != want_R or f.G[s] != want_G:
                fails.append((family, case, vname, "state", s, f.R[s], want_R, f.G[s], want_G))
        queried = subset if pr else nodes
        for o in queried:
            got = ff.issue_set(f, o)
            tally["origin_sets"] += 1
            if got != ref_feas[o]:
                fails.append((family, case, vname, "feas", o, got, ref_feas[o]))
            if brute is not None and got != brute[o]:
                fails.append((family, case, vname, "feas_vs_brute", o))
            for lo_, hi_ in ref_feas[o]:
                for t in range(lo_, hi_ + 1):
                    tally["witnesses"] += 1
                    w_ref = core.witness(ref, o, t)
                    w = ff.witness(f, o, t)
                    if w != w_ref:
                        fails.append((family, case, vname, "witness", o, t, w, w_ref))
                    elif brute is not None:
                        ok, why = checker.check_route(checker.Model(chk), o, t, w[1])
                        tally["witness_checked"] += 1
                        if not ok:
                            fails.append((family, case, vname, "witness_invalid", o, t, why))
        if pr:
            others = [o for o in nodes if o not in set(subset)]
            for o in others:
                tally["guard_checks"] += 1
                try:
                    ff.issue_set(f, o)
                    fails.append((family, case, vname, "guard_missing", o))
                except ValueError:
                    pass
                if ff.issue_set(f, o, fallback=True) != ref_feas[o]:
                    fails.append((family, case, vname, "fallback", o))


def run(n_per_family=2000, seed=20261123):
    rng = random.Random(seed)
    tally = Counter()
    fails = []
    kinds = Counter()
    for family in ("general", "closure", "mixed"):
        for case in range(n_per_family):
            if family == "mixed":
                inst, chk = mixed(rng)
            else:
                inst, chk = randgraphs.generate(rng, family)
            ref = core.backward(inst)
            nodes = list(range(inst.n_nodes))
            ref_feas = {o: core.issue_set(ref, o) for o in nodes}
            brute = None
            if family != "mixed":
                m = checker.Model(chk)
                brute = {o: iv.from_set(set(checker.feasible_set(m, o))) for o in nodes}
                for o in nodes:
                    tally["brute_origin_sets"] += 1
                    if brute[o] != ref_feas[o]:
                        fails.append((family, case, "core_vs_brute", o))
            k = rng.randint(1, len(nodes))
            subset = sorted(rng.sample(nodes, k))
            for vname, sc, pr, wd in VARIANTS:
                try:
                    check_variant(inst, chk, ref, ref_feas, brute, nodes, subset, vname, sc, pr, wd, tally, fails,
                                  kinds, family, case)
                except Exception as exc:      # a crash (for example a witness dead end) is a detected failure
                    fails.append((family, case, vname, "crash", type(exc).__name__, str(exc)[:200]))
            tally["instances"] += 1
    return {"seed": seed, "n_per_family": n_per_family, "tally": dict(tally), "failures": len(fails),
            "first_failures": [repr(x) for x in fails[:20]],
            "state_kinds": {"%s/%s/%s" % k: v for k, v in sorted(kinds.items())}}


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    res = run(n)
    print(json.dumps({k: v for k, v in res.items() if k != "state_kinds"}, indent=1))
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(json.dumps(res, indent=1))
    sys.exit(1 if res["failures"] else 0)
