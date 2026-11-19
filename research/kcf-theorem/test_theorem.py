"""Tests for THEOREM.md. Standard library only (unittest). Run from the repository root:

    python3 -m unittest research/kcf-theorem/test_theorem.py -v

KCF_CASES (default 6000) sets the number of random instances PER FAMILY (two families, so 12,000 by default).
KCF_MUTANT_CASES (default 3000) sets the instances per family per mutant. Measured counts are written to
research/kcf-theorem/results/. WFG_ROUTING_DATA (path to the fetched data/routing) enables the real-data
differential test.
"""
from __future__ import annotations

import itertools
import json
import os
import random
import sys
import time
import unittest
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "harness-2026-11" / "F-3.1"))

import checker  # noqa: E402
import mutants  # noqa: E402
import randgraphs  # noqa: E402
from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import Instance, backward, check_fixed_point, issue_set, witness  # noqa: E402

N_CASES = int(os.environ.get("KCF_CASES", "6000"))
N_MUT = int(os.environ.get("KCF_MUTANT_CASES", "3000"))
RESULTS = HERE / "results"
NEG = -(10 ** 9)


def is_prefix(s):
    return not s or (min(s) == 0 and len(s) == max(s) + 1)


def scalar_deadlines(chk):
    """THEOREM.md Theorem 2(b), written from the statement, not from the code: c_j, a_j, then the least solution of
    l_s = max(a_s, max_j min(c_j - 1, l_j - D_j)) by iteration; origins read off with the issue closure."""
    H, edges = chk["H"], chk["edges"]
    m = checker.Model(chk)
    c = [min([t for t in m.B.get(j, ()) if 0 <= t <= H - D] or [H - D + 1]) for j, (_, _, D) in enumerate(edges)]
    a = [max([t for t in m.A.get(j, ()) if 0 <= t <= H] or [NEG]) for j in range(len(edges))]

    def term(j, lj):
        x = min(c[j] - 1, lj - edges[j][2])
        return x if x >= 0 and lj > NEG else NEG

    ell = list(a)
    changed = True
    while changed:
        changed = False
        for s in range(len(edges)):
            best = a[s]
            for j in m.out.get(edges[s][1], ()):
                if (s, j) not in m.forbidden:
                    best = max(best, term(j, ell[j]))
            if best > ell[s]:
                ell[s], changed = best, True
    L = {}
    for o in range(chk["n_nodes"]):
        lo = max([term(j, ell[j]) for j in m.out.get(o, ())] + [max(m.AN.get(o, ()) or [NEG])])
        first_ib = min(m.IB.get(o, ()) or [H + 1])
        L[o] = min(lo, first_ib - 1) if lo >= 0 else NEG
    return ell, L


def legs(w):
    return [[k, x, a, b] for k, x, a, b in w[1]]


class ToyAndCounterexample(unittest.TestCase):
    def test_repo_toy_has_a_hole(self):
        """The 6-node toy of research/kcf-evidence/ALGORITHM_APPENDIX.md: feasible departures 0-10 and 26-32."""
        chk = {"H": 60, "n_nodes": 6, "waitable": [], "forbidden": [], "W": {}, "IB": {}, "AN": {},
               "edges": [[0, 1, 10], [1, 5, 10], [0, 2, 15], [2, 3, 15], [3, 5, 15], [1, 4, 5], [4, 5, 8]],
               "B": {1: [[18, 60]], 6: [[14, 40]]}, "A": {1: [[0, 55]], 4: [[0, 55]], 6: [[0, 55]]}}
        fld = backward(randgraphs.to_instance(chk))
        self.assertEqual(issue_set(fld, 0), [(0, 10), (26, 32)])
        self.assertEqual(checker.feasible_set(chk, 0), list(range(0, 11)) + list(range(26, 33)))
        ok, why = checker.confirm_deadline(chk, 0, 32, legs(witness(fld, 0, 32)))
        self.assertTrue(ok, why)
        ok, why = checker.check_route(chk, 0, 20, [["EDGE", 0, 20, 30], ["EDGE", 5, 30, 35], ["EDGE", 6, 35, 43]])
        self.assertFalse(ok)
        self.assertIn("closed at start second 35", why)

    def test_smallest_counterexamples(self):
        reopen = {"H": 2, "n_nodes": 2, "edges": [[0, 1, 1]], "waitable": [], "forbidden": [],
                  "B": {0: [[0, 0]]}, "A": {0: [[0, 2]]}}
        late = {"H": 2, "n_nodes": 2, "edges": [[0, 1, 1]], "waitable": [], "forbidden": [],
                "B": {}, "A": {0: [[2, 2]]}}
        for chk in (reopen, late):
            fld = backward(randgraphs.to_instance(chk))
            self.assertEqual(issue_set(fld, 0), [(1, 1)])          # the algorithm returns exactly {1}
            self.assertEqual(checker.feasible_set(chk, 0), [1])
            self.assertEqual(issue_set(backward(randgraphs.to_instance(randgraphs.monotone_hull(chk))), 0), [])
        # origin = shelter (never in the recorded caches): one node, no edge, origin closed at 0 only
        one = {"H": 1, "n_nodes": 1, "edges": [], "IB": {0: [[0, 0]]}, "AN": {0: [[0, 1]]}}
        self.assertEqual(checker.feasible_set(one, 0), [1])
        self.assertEqual(issue_set(backward(randgraphs.to_instance({**one, "waitable": [], "forbidden": [],
                                                                     "B": {}, "W": {}, "A": {}})), 0), [(1, 1)])

    def test_nothing_smaller_fails(self):
        """Exhaustive: origin != shelter, at most 2 nodes and 1 edge, H <= 1, every mask (B, W, A, IB) and every
        waitable choice: every feasible set is a prefix. Plus H = 2 with no non-monotone mask: prefix."""
        n = 0
        for H in (0, 1):
            T = range(H + 1)
            subsets = [[[t, t] for t in s] for r in range(H + 2) for s in itertools.combinations(T, r)]
            for D, Bm, Am, IBm, wt, Wm in itertools.product((1, 2), subsets, subsets, subsets, (0, 1, 2, 3), subsets):
                chk = {"H": H, "n_nodes": 2, "edges": [[0, 1, D]], "forbidden": [],
                       "waitable": [v for v in (0, 1) if wt >> v & 1], "B": {0: Bm}, "A": {0: Am},
                       "IB": {0: IBm}, "W": {v: Wm for v in (0, 1)}}
                self.assertTrue(is_prefix(checker.feasible_set(chk, 0)))
                n += 1
        self.assertGreater(n, 1000)


class PropertyVsBruteForce(unittest.TestCase):
    def test_random_graphs(self):
        c = Counter()
        t_field = t_brute = 0.0
        examples = []
        for fam in ("general", "closure"):
            for seed in range(N_CASES):
                inst, chk = randgraphs.generate(random.Random(f"{fam}-{seed}"), fam)
                c[fam + ":cases"] += 1
                t0 = time.perf_counter()
                fld = backward(inst)
                sets = {o: issue_set(fld, o) for o in range(chk["n_nodes"])}
                t_field += time.perf_counter() - t0
                check_fixed_point(fld)
                m = checker.Model(chk)
                ell, Lsc = scalar_deadlines(chk) if fam == "closure" else (None, None)
                hull = None
                if fam == "general":
                    hull_chk = randgraphs.monotone_hull(chk)
                    hull = backward(randgraphs.to_instance(hull_chk))
                for o in range(chk["n_nodes"]):
                    S = iv.to_set(sets[o])
                    t0 = time.perf_counter()
                    T = set(checker.feasible_set(m, o))
                    t_brute += time.perf_counter() - t0
                    c[fam + ":origin_sets"] += 1
                    c[fam + ":departure_seconds_compared"] += chk["H"] + 1
                    self.assertEqual(S, T, (fam, seed, o, sets[o]))
                    c[fam + ":nonempty"] += bool(T)
                    if not is_prefix(T):
                        c[fam + ":NOT_prefix"] += 1
                        if len(examples) < 3:
                            examples.append({"family": fam, "seed": seed, "origin": o, "feasible": sets[o]})
                    if fam == "closure":
                        self.assertTrue(is_prefix(T), (seed, o))
                        want = set(range(Lsc[o] + 1)) if Lsc[o] >= 0 else set()
                        self.assertEqual(T, want, (seed, o, Lsc[o]))
                        c["closure:scalar_recursion_equal"] += 1
                    else:
                        H_o = iv.to_set(issue_set(hull, o))
                        self.assertTrue(is_prefix(H_o) and H_o <= T, (seed, o))
                        c["general:hull_prefix_and_subset"] += 1
                        c["general:hull_loses_seconds"] += len(T - H_o)
                    if T:
                        L = max(T)
                        ok, why = checker.confirm_deadline(m, o, L, legs(witness(fld, o, L)))
                        self.assertTrue(ok, why)
                        c[fam + ":deadline_confirmed"] += 1
                if fam == "closure":
                    for s in range(len(chk["edges"])):
                        g = iv.to_set(fld.G[s])
                        self.assertTrue(is_prefix(g))
                        self.assertEqual(max(g) if g else NEG, ell[s])
        out = {"cases_per_family": N_CASES, "counts": dict(sorted(c.items())), "non_prefix_examples": examples,
               "seconds": {"backward_and_issue_sets": round(t_field, 2), "brute_force_one_second_at_a_time":
                           round(t_brute, 2)}, "mismatches": 0}
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "property_tests.json").write_text(json.dumps(out, indent=1))
        print("\n" + json.dumps(out, indent=1))


class Mutants(unittest.TestCase):
    def test_each_mutant_is_caught(self):
        report = {}
        for mut in (None,) + mutants.MUTATIONS:
            c = Counter()
            first = None
            for fam in ("general", "closure"):
                for seed in range(N_MUT):
                    inst, chk = randgraphs.generate(random.Random(f"mut-{fam}-{seed}"), fam)
                    m = checker.Model(chk)
                    try:
                        fld = mutants.backward(inst, mut)
                    except RuntimeError:
                        c[fam + ":crash"] += 1
                        continue
                    c[fam + ":cases"] += 1
                    caught = Counter()
                    try:
                        check_fixed_point(fld)
                    except AssertionError:
                        caught["certificate"] += 1
                    for o in range(chk["n_nodes"]):
                        S, T = iv.to_set(mutants.issue_set(fld, o)), set(checker.feasible_set(m, o))
                        if S - T:
                            caught["brute_force_overclaim"] += 1
                        if T - S:
                            caught["brute_force_underclaim"] += 1
                        for t in sorted(S):
                            r = mutants.greedy_route(fld, o, t)
                            if isinstance(r, str):
                                caught["route_dead_end"] += 1
                            elif not checker.check_route(m, o, t, r)[0]:
                                caught["checker_rejects_route"] += 1
                                if first is None:
                                    first = {"family": fam, "seed": seed, "origin": o, "departure": t, "route": r,
                                             "checker": checker.check_route(m, o, t, r)[1]}
                    for k, v in caught.items():
                        c[fam + ":" + k] += v
                    c[fam + ":cases_caught"] += bool(caught)
                    if caught and first is None:
                        first = {"family": fam, "seed": seed, "how": sorted(caught)}
            report[str(mut)] = {"counts": dict(sorted(c.items())), "first_detection": first}
            if mut is None:
                self.assertEqual(c["general:cases_caught"] + c["closure:cases_caught"], 0, c)
            else:
                self.assertGreater(c["general:cases_caught"] + c["closure:cases_caught"], 0, mut)
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "mutation_tests.json").write_text(json.dumps({"cases_per_family": N_MUT, **report}, indent=1,
                                                                default=str))
        for k, v in report.items():
            print(k, {x: y for x, y in v["counts"].items() if "caught" in x or "cases" in x})


@unittest.skipUnless(os.environ.get("WFG_ROUTING_DATA"), "set WFG_ROUTING_DATA to the fetched data/routing directory")
class RealDataDifferential(unittest.TestCase):
    """Every recorded checked route of the six caches through the independent checker (about 40 min on 4 cores)."""

    def test_every_recorded_route_and_deadline_witness(self):
        import subprocess
        out = RESULTS / "differential_real.json"
        subprocess.run([sys.executable, str(HERE / "differential_witnesses.py"), "--data-root",
                        os.environ["WFG_ROUTING_DATA"], "--out", str(out)], check=True)
        tot = json.loads(out.read_text())["total"]
        for k, v in tot.items():
            if k.endswith("INVALID") or k == "L_plus_1:route":
                self.assertEqual(v, 0, k)
        self.assertEqual(tot["recorded_router:VALID"], tot["recorded_cert:VALID"])


if __name__ == "__main__":
    unittest.main()
