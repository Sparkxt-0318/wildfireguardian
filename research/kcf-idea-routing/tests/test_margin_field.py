"""Tests for METHOD.md. Standard library only (unittest). Run from the repository root:

    python3 -m unittest research/kcf-idea-routing/tests/test_margin_field.py -v

KCF_CASES (default 6000) is the number of random instances PER FAMILY (two families: "general" with reopening, late
shelters and origin closures; "closure" satisfying M1-M4), so 12,000 by default. KCF_MUTANT_CASES (default 1000) is
the number per family per mutant. Counts are written to research/kcf-idea-routing/results/.

Three independent references are used:
  * the existing field   deadline_field.core.backward / issue_set on the widened instance (code unchanged);
  * the brute-force oracle  research/kcf-theorem/checker.py (imports nothing from the repository), on a widened
    instance that this file builds second by second with Python sets (``widen_chk``), not with field.widen;
  * dense per-second evaluation of every tent-function operation.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
import unittest
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(PKG.parent / "kcf-theorem"))
sys.path.insert(0, str(PKG.parent / "harness-2026-11" / "F-3.1"))

import checker  # noqa: E402
import randgraphs  # noqa: E402
from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, check_fixed_point as core_fixed_point, issue_set, witness  # noqa: E402
from margin_field import field as mf  # noqa: E402
from margin_field import pl  # noqa: E402

N_CASES = int(os.environ.get("KCF_CASES", "6000"))
N_MUT = int(os.environ.get("KCF_MUTANT_CASES", "1000"))
RESULTS = PKG / "results"


# ------------------------------------------------------------------------------------- independent widening (sets)
def _secs(ivs):
    out = set()
    for lo, hi in ivs or ():
        out.update(range(int(lo), int(hi) + 1))
    return out


def _points(s):
    return [[t, t] for t in sorted(s)]


def widen_chk(chk, m, erode):
    """The m-widened instance of METHOD.md section 1 as a checker dict, built from the definition with sets."""
    H = chk["H"]

    def dil(ivs):
        s = _secs(ivs)
        return _points({t for x in s for t in range(x - m, x + m + 1)})

    def ero(ivs):
        s = {t for t in _secs(ivs) if 0 <= t <= H}        # acceptance is clipped to T first (C4)
        return _points({t for t in s if all(u in s for u in range(t - m, t + m + 1))}) if erode else _points(s)

    out = dict(chk)
    for k in ("B", "W", "IB"):
        out[k] = {j: dil(v) for j, v in chk.get(k, {}).items()}
    for k in ("A", "AN"):
        out[k] = {j: ero(v) for j, v in chk.get(k, {}).items()}
    return out


def rand_tent(rng, lo, hi, vmax):
    """A random member of the tent class on [lo, hi] (with gaps), as a canonical piece list."""
    vals, t = {}, lo
    while t <= hi:
        if rng.random() < 0.25:
            t += rng.randint(1, 4)
            continue
        v = rng.randint(0, vmax)
        for _ in range(rng.randint(1, 6)):
            if t > hi:
                break
            vals[t] = v
            v = min(vmax, max(0, v + rng.choice((-1, 0, 1))))
            t += 1
    return dense_to_pl(vals), vals


def dense_to_pl(vals):
    out = []
    for t in sorted(vals):
        pl._emit(out, t, t, vals[t], 0)
    return out


def as_dict(f):
    return {t: v + s * (t - lo) for lo, hi, v, s in f for t in range(lo, hi + 1)}


class TentAlgebra(unittest.TestCase):
    """Every operation of margin_field/pl.py against per-second evaluation (METHOD.md Lemmas 4.1-4.3)."""

    def test_operations_dense(self):
        rng = random.Random(20261119)
        n = 0
        for _ in range(20000):
            f, df = rand_tent(rng, 0, 30, 6)
            g, dg = rand_tent(rng, 0, 30, 6)
            for p in f + g:
                self.assertTrue(p[0] <= p[1] and p[3] in (-1, 0, 1) and p[2] >= 0)
            self.assertEqual(as_dict(f), df)
            want_min = {t: min(df[t], dg[t]) for t in df if t in dg}
            self.assertEqual(as_dict(pl.pmin(f, g)), want_min)
            want_max = {t: max(df.get(t, -1), dg.get(t, -1)) for t in set(df) | set(dg)}
            h, clo, chi = pl.raise_to(f, g)
            self.assertEqual(as_dict(h), want_max)
            ch = [t for t in dg if dg[t] > df.get(t, -1)]
            self.assertEqual((clo, chi), (min(ch), max(ch)) if ch else (None, None))
            self.assertEqual(pl.canon(h), dense_to_pl(want_max))          # greedy-maximal form is unique
            a, b = sorted((rng.randint(-2, 32), rng.randint(-2, 32)))
            self.assertEqual(as_dict(pl.restrict(f, a, b)), {t: v for t, v in df.items() if a <= t <= b})
            d = rng.randint(-5, 5)
            self.assertEqual(as_dict(pl.shift(f, d)), {t + d: v for t, v in df.items()})
            m = rng.randint(0, 6)
            self.assertEqual(iv.to_set(pl.level_set(f, m)), {t for t, v in df.items() if v >= m})
            if df:
                left = rng.randint(-1, 5)
                top = max(df)
                want = {}
                for t in range(left, top + 1):
                    x = max((v for u, v in df.items() if u >= t), default=-1)
                    if x >= 0:
                        want[t] = x
                self.assertEqual(as_dict(pl.suffix_max(f, left)), want)
            # waiting closure: c(t) = max(mu(t), min(omega(t), c(t + 1))), evaluated from the right
            c, nxt = {}, -1
            for t in range(31, -2, -1):
                cur = max(df.get(t, -1), min(dg.get(t, -1), nxt))
                if cur >= 0:
                    c[t] = cur
                nxt = cur
            self.assertEqual(as_dict(mf.wait_close(f, g)), c)
            n += 1
        self.assertEqual(n, 20000)

    def test_tent_is_distance_minus_one(self):
        rng = random.Random(7)
        for _ in range(5000):
            closed = iv.normalize([(a, a + rng.randint(0, 5)) for a in (rng.randint(-6, 36) for _ in
                                                                         range(rng.randint(0, 4)))])
            M = rng.randint(0, 9)
            S = iv.to_set(closed)
            want = {}
            for t in range(0, 31):
                if t in S:
                    continue
                d = min((abs(t - x) for x in S), default=10 ** 9)
                want[t] = min(M, d - 1)
            self.assertEqual(as_dict(pl.tent(closed, 0, 30, M)), want)


class Examples(unittest.TestCase):
    def test_two_route_example(self):
        """METHOD.md Proposition 3: one unbroken window [0, 11], but second 5 has margin 0."""
        chk = {"H": 12, "n_nodes": 2, "edges": [[0, 1, 1], [0, 1, 1]], "waitable": [], "forbidden": [],
               "B": {0: [[6, 40]], 1: [[0, 5]]}, "W": {}, "A": {0: [[0, 12]], 1: [[0, 12]]}, "IB": {}, "AN": {}}
        inst = randgraphs.to_instance(chk)
        self.assertEqual(issue_set(backward(inst), 0), [(0, 11)])
        self.assertEqual(checker.feasible_set(chk, 0), list(range(12)))
        fld = mf.margin_field(inst, 8)
        f = mf.issue_margin(fld, 0)
        self.assertEqual(pl.to_dense(f, 0, 12), [5, 4, 3, 2, 1, 0, 0, 1, 2, 3, 4, 5, -1])
        self.assertEqual(mf.issue_set_at(fld, 0, 2), [(0, 3), (8, 11)])
        self.assertEqual(checker.feasible_set(widen_chk(chk, 2, False), 0), [0, 1, 2, 3, 8, 9, 10, 11])
        self.assertEqual(mf.leave_by(fld, 0), [(0, 11), (1, 4), (2, 3), (3, 2), (4, 1), (5, 0), (6, None)])

    def test_repo_toy(self):
        """The 6-node toy of research/kcf-evidence/ALGORITHM_APPENDIX.md (feasible 0-10 and 26-32)."""
        chk = {"H": 60, "n_nodes": 6, "waitable": [], "forbidden": [], "W": {}, "IB": {}, "AN": {},
               "edges": [[0, 1, 10], [1, 5, 10], [0, 2, 15], [2, 3, 15], [3, 5, 15], [1, 4, 5], [4, 5, 8]],
               "B": {1: [[18, 60]], 6: [[14, 40]]}, "A": {1: [[0, 55]], 4: [[0, 55]], 6: [[0, 55]]}}
        inst = randgraphs.to_instance(chk)
        fld = mf.margin_field(inst, 20)
        mf.check_fixed_point(fld)
        self.assertEqual(mf.issue_set_at(fld, 0, 0), [(0, 10), (26, 32)])
        for m in range(21):
            self.assertEqual(mf.issue_set_at(fld, 0, m), issue_set(backward(mf.widen(inst, m)), 0))
            self.assertEqual(iv.to_set(mf.issue_set_at(fld, 0, m)), set(checker.feasible_set(widen_chk(chk, m, False), 0)))


def _perturbed(rng, chk, inst, m, erode):
    """A random member of the perturbation class P(m) of METHOD.md section 3: every closure interval has each end
    moved by at most m seconds (or is deleted); with erode, every acceptance interval loses at most m at each end."""
    def move(ivs):
        out = []
        for lo, hi in ivs:
            if rng.random() < 0.15:
                continue
            a, b = lo + rng.randint(-m, m), hi + rng.randint(-m, m)
            if a <= b:
                out.append([a, b])
        return out

    out = dict(chk)
    E = len(chk["edges"])
    out["B"] = {j: move(inst.B[j]) for j in range(E)}
    out["W"] = {v: move(inst.W[v]) for v in range(chk["n_nodes"])}
    out["IB"] = {o: move(iv.normalize(x)) for o, x in inst.IB.items()}
    if erode:
        def shrink(ivs):
            return [[lo + rng.randint(0, m), hi - rng.randint(0, m)] for lo, hi in ivs]
        out["A"] = {j: [p for p in shrink(inst.A[j]) if p[0] <= p[1]] for j in range(E)}
        out["AN"] = {o: [p for p in shrink(x) if p[0] <= p[1]] for o, x in inst.AN.items()}
    return out


class PropertyVsFieldAndOracle(unittest.TestCase):
    def test_random_graphs(self):
        c = Counter()
        t_new = t_old = t_brute = 0.0
        for fam in ("general", "closure"):
            for seed in range(N_CASES):
                rng = random.Random(f"margin-{fam}-{seed}")
                inst, chk = randgraphs.generate(rng, fam)
                M = rng.randint(0, 8)
                erode = rng.random() < 0.5
                n, E = chk["n_nodes"], len(chk["edges"])
                c[fam + ":cases"] += 1
                t0 = time.perf_counter()
                fld = mf.margin_field(inst, M, erode_accept=erode)
                fo = [mf.issue_margin(fld, o) for o in range(n)]
                t_new += time.perf_counter() - t0
                mf.check_fixed_point(fld)
                c[fam + ":margin_fixed_point_ok"] += 1
                feas0 = None
                for m in range(M + 1):
                    wi = mf.widen(inst, m, erode_accept=erode)
                    t0 = time.perf_counter()
                    ref = backward(wi)
                    ref_sets = [issue_set(ref, o) for o in range(n)]
                    t_old += time.perf_counter() - t0
                    for s in range(E):                              # (1) the existing field, every edge state
                        self.assertEqual(pl.level_set(fld.mu[s], m), ref.R[s], (fam, seed, m, s))
                        self.assertEqual(pl.level_set(fld.gamma[s], m), ref.G[s], (fam, seed, m, s))
                        c[fam + ":state_sets_equal_existing_field"] += 2
                    fa = mf.field_at(fld, m)                        # read-off Field passes the existing certificate
                    core_fixed_point(fa)
                    wm = checker.Model(widen_chk(chk, m, erode))
                    pert = checker.Model(_perturbed(rng, chk, inst, m, erode))
                    for o in range(n):
                        got = pl.level_set(fo[o], m)
                        self.assertEqual(got, ref_sets[o], (fam, seed, m, o))
                        c[fam + ":origin_sets_equal_existing_field"] += 1
                        t0 = time.perf_counter()
                        truth = set(checker.feasible_set(wm, o))    # (2) brute force on the set-built widening
                        t_brute += time.perf_counter() - t0
                        self.assertEqual(iv.to_set(got), truth, (fam, seed, m, o, got))
                        c[fam + ":origin_sets_equal_oracle"] += 1
                        c[fam + ":departure_seconds_compared"] += chk["H"] + 1
                        if m == 0:
                            feas0 = feas0 or {}
                            feas0[o] = truth
                            c[fam + ":nonempty_at_margin_0"] += bool(truth)
                            c[fam + ":not_prefix_at_margin_0"] += bool(truth) and not (
                                min(truth) == 0 and len(truth) == max(truth) + 1)
                        for t in sorted(truth):                     # (3) Theorem 2: one route, every perturbation
                            w = witness(fa, o, t)
                            route = [[k, x, a, b] for k, x, a, b in w[1]]
                            ok, why = checker.check_route(wm, o, t, route)
                            self.assertTrue(ok, (fam, seed, m, o, t, why))
                            ok, why = checker.check_route(pert, o, t, route)
                            self.assertTrue(ok, (fam, seed, m, o, t, why))
                            c[fam + ":routes_valid_under_random_perturbation"] += 1
                            if erode and m:                         # (4) Proposition 3: the shifted route
                                for t2 in range(max(0, t - m), t + m + 1):
                                    self.assertIn(t2, feas0[o], (fam, seed, m, o, t, t2))
                                c[fam + ":prop3_neighbourhood_feasible"] += 1
                if erode:                                           # Proposition 3 as a bound, and how often strict
                    for o in range(n):
                        d = pl.to_dense(fo[o], 0, chk["H"])
                        for t, v in enumerate(d):
                            if v < 0:
                                continue
                            dist = next(k for k in range(1, chk["H"] + 3)
                                        if t + k > chk["H"] or d[t + k] < 0 or (t - k >= 0 and d[t - k] < 0))
                            self.assertLessEqual(v, min(M, dist - 1), (fam, seed, o, t))
                            c[fam + ":prop3_seconds_checked"] += 1
                            c[fam + ":prop3_seconds_margin_strictly_below_window_distance"] += v < min(M, dist - 1)
        out = {"cases_per_family": N_CASES, "margins": "0..M, M uniform in 0..8, erode_accept with probability 1/2",
               "counts": dict(sorted(c.items())), "mismatches": 0,
               "seconds": {"margin_field_one_pass_all_margins": round(t_new, 2),
                           "existing_backward_one_pass_per_margin": round(t_old, 2),
                           "brute_force": round(t_brute, 2)}}
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "property_tests.json").write_text(json.dumps(out, indent=1))
        print("\n" + json.dumps(out, indent=1))


# ------------------------------------------------------------------------------------------------------------ mutants
def _mut_tent_off_by_one(orig):
    def tent(closed, lo, hi, M):                    # min(M, distance) instead of min(M, distance - 1)
        if not closed or M == 0:
            return orig(closed, lo, hi, M)
        return [(a, b, v + 1, s) for a, b, v, s in orig(closed, lo, hi, M - 1)]
    return tent


MUTANTS = {
    "tent_off_by_one": "level function = distance to the closure (not distance - 1): every closure widened one second too little",
    "wait_ignores_mask": "waiting closure ignores the wait mask omega (waits through fire)",
    "shift_off_by_one": "edge travel taken as D - 1 when shifting back",
    "ignore_turns": "forbidden turns not removed from the predecessor lists",
    "drop_dirty_low": "only the top second of a changed region is re-delivered (dirty hull collapsed)",
}


class Patched:
    """Context manager that installs one mutation into margin_field.field / pl and removes it again."""

    def __init__(self, name):
        self.name = name

    def __enter__(self):
        self.saved = (pl.tent, mf.wait_close, pl.shift, pl.raise_to, mf.Instance)
        n = self.name
        if n == "tent_off_by_one":
            pl.tent = _mut_tent_off_by_one(self.saved[0])
        elif n == "wait_ignores_mask":
            wc = self.saved[1]
            mf.wait_close = lambda mu, omega: wc(mu, [(0, 400, 99, 0)]) if omega else mu
        elif n == "shift_off_by_one":
            sh = self.saved[2]
            pl.shift = lambda f, d: sh(f, d + 1) if d < -1 else sh(f, d)
        elif n == "drop_dirty_low":
            rt = self.saved[3]

            def raise_to(f, g):
                h, a, b = rt(f, g)
                return h, (b if a is not None else None), b
            pl.raise_to = raise_to
        return self

    def __exit__(self, *exc):
        pl.tent, mf.wait_close, pl.shift, pl.raise_to, mf.Instance = self.saved


def _run_mutant(name, inst, M, erode):
    if name == "ignore_turns":
        saved = inst.forbidden
        inst.forbidden = set()
        try:
            fld = mf.margin_field(inst, M, erode_accept=erode)
        finally:
            inst.forbidden = saved
        fld.inst = inst
        return fld
    with Patched(name):
        return mf.margin_field(inst, M, erode_accept=erode)


class Mutants(unittest.TestCase):
    """Do the checks above have teeth? Five bugs planted in the margin pass; each must be caught by the comparison
    with the existing field, by the oracle, or by the fixed-point certificate."""

    def test_each_mutant_is_caught(self):
        report = {}
        for name in [None] + list(MUTANTS):
            c = Counter()
            for fam in ("general", "closure"):
                for seed in range(N_MUT):
                    rng = random.Random(f"margin-mut-{fam}-{seed}")
                    inst, chk = randgraphs.generate(rng, fam)
                    M = rng.randint(0, 8)
                    erode = rng.random() < 0.5
                    fld = _run_mutant(name, inst, M, erode) if name else mf.margin_field(inst, M, erode_accept=erode)
                    how = set()
                    try:
                        mf.check_fixed_point(fld)
                    except AssertionError:
                        how.add("certificate")
                    for m in range(M + 1):
                        ref = backward(mf.widen(inst, m, erode_accept=erode))
                        if any(pl.level_set(fld.mu[s], m) != ref.R[s] for s in range(len(inst.tail))):
                            how.add("existing_field")
                        wm = checker.Model(widen_chk(chk, m, erode))
                        for o in range(chk["n_nodes"]):
                            if iv.to_set(pl.level_set(mf.issue_margin(fld, o), m)) != set(checker.feasible_set(wm, o)):
                                how.add("oracle")
                    c[fam + ":cases"] += 1
                    c[fam + ":caught"] += bool(how)
                    for h in how:
                        c[fam + ":by_" + h] += 1
            report[str(name)] = dict(sorted(c.items()))
            caught = c["general:caught"] + c["closure:caught"]
            if name is None:
                self.assertEqual(caught, 0, c)
            else:
                self.assertGreater(caught, 0, name)
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "mutation_tests.json").write_text(json.dumps(
            {"cases_per_family": N_MUT, "mutants": MUTANTS, "results": report}, indent=1))
        for k, v in report.items():
            print(k, v)


if __name__ == "__main__":
    unittest.main()
