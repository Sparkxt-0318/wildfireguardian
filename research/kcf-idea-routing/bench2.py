"""Second benchmark (round 2). The plan is BENCH_PLAN_V2.md, frozen before this file was first run on the caches.

    .venv-kcf/bin/python research/kcf-idea-routing/bench2.py --data-root data/routing \
        --out research/kcf-idea-routing/results/bench2.json

Methods: EXISTING = deadline_field.core.backward (unchanged); NEW = margin_field(fast=True); V1 = margin_field(
fast=False) (the method of BENCH.md section 1); NB = the compiled pass of margin_field/nb.py; NB0 = the same compiled
kernel run with M = 0 once per margin on the widened instance (the compiled level-by-level baseline).
"""
from __future__ import annotations

import argparse
import gc
import glob
import json
import os
import platform
import random
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tests"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/kcf-theorem"))
sys.path.insert(0, str(ROOT / "research/harness-2026-11/F-3.1"))
from deadline_field.core import backward, issue_set  # noqa: E402
from margin_field import field as mf  # noqa: E402
from margin_field import nb, pl  # noqa: E402
from real_caches import cache_specs, load  # noqa: E402

M = 600
KS = (1, 2, 4, 8, 16)
REPEATS = 5
SEED = 20261119


def margins_for(K):
    return [60] if K == 1 else [round(M * i / (K - 1)) for i in range(K)]


def timed(fn):
    gc.collect()
    t0 = time.perf_counter()
    out = fn()
    return time.perf_counter() - t0, out


def med(xs):
    return {"median": round(statistics.median(xs), 5), "min": round(min(xs), 5), "max": round(max(xs), 5)}


def ratio(a, b):
    return round(statistics.median(a) / statistics.median(b), 3)


def sampled(doc):
    specs = cache_specs(doc)
    rng = random.Random(SEED)
    return specs if len(specs) <= 6 else rng.sample(specs, 6)


def instance_of(pm, spec):
    (dn, dwell, win), origins = spec
    return pm.instance("cert", [{"node": dn, "dwell": dwell, "window": list(win)}], sorted(origins))


def arrays_R(fld, m, E):
    """R of every state at margin m of a compiled field, as python interval lists (checking only, never timed)."""
    out, cnt = nb.level_arrays(fld, m)
    return [[tuple(r) for r in out[s, :cnt[s]].tolist()] for s in range(E)]


def bench_spec(inst, origin_idx):
    E = len(inst.tail)
    row = {"edges": E}
    order = ["existing", "new", "v1", "nb"]
    # ------------------------------------------------------------------ T1: one field, margin 0
    fns = {"existing": lambda: backward(inst), "new": lambda: mf.margin_field(inst, 0),
           "v1": lambda: mf.margin_field(inst, 0, fast=False), "nb": lambda: nb.margin_field_nb(inst, 0)}
    t = {k: [] for k in order}
    first = {}
    for r in range(REPEATS):
        for k in (order if r % 2 == 0 else order[::-1]):
            dt, res = timed(fns[k])
            t[k].append(dt)
            if r == 0:
                first[k] = res
    ref = first["existing"]
    mm = {}
    for k in ("new", "v1"):
        f = first[k]
        mm[k] = sum(pl.level_set(f.mu[s], 0) != ref.R[s] or pl.level_set(f.gamma[s], 0) != ref.G[s] for s in range(E))
    got = arrays_R(first["nb"], 0, E)
    mm["nb_R_only"] = sum(got[s] != ref.R[s] for s in range(E))
    row["T1"] = {"seconds": {k: med(v) for k, v in t.items()}, "mismatches": mm,
                 "ratio_existing_over_new": ratio(t["existing"], t["new"]),
                 "ratio_existing_over_v1": ratio(t["existing"], t["v1"]),
                 "ratio_existing_over_nb": ratio(t["existing"], t["nb"]),
                 "existing_pushes": ref.stats["pushes"], "new_stats": first["new"].stats,
                 "nb_stats": first["nb"].stats}
    del first, got
    # ------------------------------------------------------------------ T2: K margins
    all_m = sorted({m for K in KS for m in margins_for(K)})
    widened = {m: mf.widen(inst, m) for m in all_m}
    graph = nb.graph_arrays(inst)                                  # shared by NB and NB0, built once, not timed
    t_old = {m: [] for m in all_m}
    t_nb0 = {m: [] for m in all_m}
    t_new_pass, t_new_read = [], {K: [] for K in KS}
    t_nb_pass, t_nb_read = [], {K: [] for K in KS}
    refs, refs_nb0 = {}, {}
    mism = {"new": {}, "nb_vs_existing_R": {}, "nb_vs_nb0_R": {}}

    def run_old(r):
        for m in all_m:
            dt, f = timed(lambda: backward(widened[m]))
            t_old[m].append(dt)
            if r == 0:
                refs[m] = (f.R, f.G)

    def run_nb0(r):
        for m in all_m:
            dt, f = timed(lambda: nb.margin_field_nb(widened[m], 0, graph=graph))
            t_nb0[m].append(dt)
            if r == 0:
                refs_nb0[m] = nb.level_arrays(f, 0)

    def run_new(r):
        dt, fld = timed(lambda: mf.margin_field(inst, M))
        t_new_pass.append(dt)
        for K in KS:
            dt, got = timed(lambda: {m: ([pl.level_set(f, m) for f in fld.mu], [pl.level_set(f, m) for f in fld.gamma])
                                     for m in margins_for(K)})
            t_new_read[K].append(dt)
            if r == 0:
                mism["new"][str(K)] = sum(got[m][0][s] != refs[m][0][s] or got[m][1][s] != refs[m][1][s]
                                          for m in margins_for(K) for s in range(E))
        if r == 0:
            row["new_M600_stats"] = fld.stats

    def run_nb(r):
        dt, fld = timed(lambda: nb.margin_field_nb(inst, M, graph=graph))
        t_nb_pass.append(dt)
        for K in KS:
            dt, got = timed(lambda: {m: nb.level_arrays(fld, m) for m in margins_for(K)})
            t_nb_read[K].append(dt)
            if r == 0:
                bad = 0
                for m in margins_for(K):
                    o1, c1 = got[m]
                    o0, c0 = refs_nb0[m]
                    w = min(o1.shape[1], o0.shape[1])
                    same = (c1 == c0) & (c1 <= w)
                    for i in range(w):
                        live = c1 > i
                        same &= ~live | ((o1[:, i, 0] == o0[:, i, 0]) & (o1[:, i, 1] == o0[:, i, 1]))
                    bad += int((~same).sum())
                mism["nb_vs_nb0_R"][str(K)] = bad
        if r == 0:
            row["nb_M600_stats"] = fld.stats
            for m in [x for x in (0, 60, M) if x in refs]:
                got = arrays_R(fld, m, E)
                mism["nb_vs_existing_R"][str(m)] = sum(got[s] != refs[m][0][s] for s in range(E))

    runs = [run_old, run_nb0, run_new, run_nb]                    # the two baselines first on the first repeat
    for r in range(REPEATS):
        for fn in (runs if r % 2 == 0 else [run_new, run_nb, run_old, run_nb0] if r else runs):
            fn(r)
    row["T2"] = {}
    for K in KS:
        ms = margins_for(K)
        old = [sum(t_old[m][r] for m in ms) for r in range(REPEATS)]
        nb0 = [sum(t_nb0[m][r] for m in ms) for r in range(REPEATS)]
        new = [t_new_pass[r] + t_new_read[K][r] for r in range(REPEATS)]
        nbt = [t_nb_pass[r] + t_nb_read[K][r] for r in range(REPEATS)]
        row["T2"][str(K)] = {"margins": ms, "existing_s": med(old), "new_s": med(new), "new_readoff_s": med(t_new_read[K]),
                             "nb0_s": med(nb0), "nb_s": med(nbt), "nb_readoff_s": med(t_nb_read[K]),
                             "ratio_existing_over_new": ratio(old, new), "ratio_nb0_over_nb": ratio(nb0, nbt),
                             "ratio_existing_over_nb": ratio(old, nbt)}
    row["new_pass_M600_s"] = med(t_new_pass)
    row["nb_pass_M600_s"] = med(t_nb_pass)
    row["T2_mismatches"] = mism
    # ------------------------------------------------------------------ T4: margin of leaving now, bisection baseline
    t_bis, t_new4, passes = [], [], 0
    for r in range(REPEATS):
        def bisect():
            memo, out, n = {}, [], 0
            for o in origin_idx:
                lo, hi = -1, M                                     # largest m with second 0 feasible; -1 if none
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if mid not in memo:
                        memo[mid] = backward(widened_all(mid))
                        n += 1
                    s = issue_set(memo[mid], o)
                    if s and s[0][0] == 0:
                        lo = mid
                    else:
                        hi = mid - 1
                out.append(lo)
            return out, n

        cache = {}

        def widened_all(m):
            if m not in cache:
                cache[m] = mf.widen(inst, m)
            return cache[m]

        bisect()                                                   # untimed: fills the widening cache
        new4 = lambda: [pl.value(mf.issue_margin(f, o), 0) for f in [mf.margin_field(inst, M)]  # noqa: E731
                        for o in origin_idx]
        if r % 2 == 0:
            dt, (want, passes) = timed(bisect)
            dn, got = timed(new4)
        else:
            dn, got = timed(new4)
            dt, (want, passes) = timed(bisect)
        t_bis.append(dt)
        t_new4.append(dn)
        if r == 0:
            row["T4_mismatches"] = sum(a != b for a, b in zip(want, got))
            row["T4_margins_now"] = want
    row["T4"] = {"origins": len(origin_idx), "existing_bisection_s": med(t_bis), "existing_passes": passes,
                 "new_s": med(t_new4), "ratio": ratio(t_bis, t_new4), "mismatches": row.pop("T4_mismatches")}
    return row


def bench_mem(inst):
    def measure(fn):
        gc.collect()
        tracemalloc.start()
        base = tracemalloc.get_traced_memory()[0]
        out = fn()
        gc.collect()
        cur, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        del out
        return {"peak_MB": round((peak - base) / 1e6, 2), "retained_MB": round((cur - base) / 1e6, 2)}

    f = nb.margin_field_nb(inst, M)
    return {"existing_one_pass_margin0": measure(lambda: (lambda f: (f.R, f.G))(backward(inst))),
            "new_fast_M600_whole_result": measure(lambda: mf.margin_field(inst, M)),
            "new_fast_M0_whole_result": measure(lambda: mf.margin_field(inst, 0)),
            "nb_M600_arrays_MB": round(sum(a.nbytes for a in f.arrays) / 1e6, 2), "nb_cap": f.stats.get("cap")}


def bench_b():
    import test_margin_field as T
    cases = []
    for fam in T.FAMILIES:
        for seed in range(6000):
            rng = random.Random(f"margin-{fam}-{seed}")
            inst, _ = T._generate(rng, fam)
            Mx = rng.randint(0, 8)
            er = rng.random() < 0.5
            cases.append((inst, Mx, er, [mf.widen(inst, m, erode_accept=er) for m in range(Mx + 1)]))
    old, new = [], []
    for r in range(REPEATS):
        def run_old():
            for _, _, _, ws in cases:
                for w in ws:
                    backward(w)

        def run_new():
            for inst, Mx, er, _ in cases:
                mf.margin_field(inst, Mx, erode_accept=er)

        for which in (("old", "new") if r % 2 == 0 else ("new", "old")):
            t, _ = timed(run_old if which == "old" else run_new)
            (old if which == "old" else new).append(t)
    return {"graphs": len(cases), "existing_passes": sum(len(c[3]) for c in cases), "existing_s": med(old),
            "new_s": med(new), "ratio": ratio(old, new)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only")
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--skip-b", action="store_true")
    a = ap.parse_args()
    try:
        import numba
        nbv = numba.__version__
    except Exception:
        nbv = None
    out = {"environment": {"python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
                           "cpu_count": os.cpu_count(), "numba": nbv, "numpy": np.__version__,
                           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           "repeats": REPEATS, "M": M, "seed": SEED}, "caches": {}}
    # compile everything once on a toy instance so that no timing includes compilation
    import randgraphs
    toy, _ = randgraphs.generate(random.Random("warm"), "general")
    f = nb.margin_field_nb(toy, 3)
    nb.level_arrays(f, 1)
    for cp in sorted(glob.glob(str(ROOT / "planner/cache/*/*.json"))):
        if a.only and a.only not in cp:
            continue
        name = str(Path(cp).relative_to(ROOT))
        doc, pm = load(cp, a.data_root)
        specs = sampled(doc)[:a.limit]
        row = out["caches"][name] = {"n_specs_in_cache": len(cache_specs(doc)), "sampled": len(specs), "specs": []}
        for spec in specs:
            inst = instance_of(pm, spec)
            r = bench_spec(inst, [pm.nidx[o] for o in sorted(spec[1])])
            r["spec"] = [spec[0][0], spec[0][1], list(spec[0][2])]
            row["specs"].append(r)
            print(name, r["spec"][0], "T1", r["T1"]["ratio_existing_over_new"], "nb", r["T1"]["ratio_existing_over_nb"],
                  "T2", {k: (v["ratio_existing_over_new"], v["ratio_nb0_over_nb"]) for k, v in r["T2"].items()},
                  "T4", r["T4"]["ratio"], "mism", r["T1"]["mismatches"], r["T2_mismatches"], r["T4"]["mismatches"],
                  flush=True)
            a.out.parent.mkdir(parents=True, exist_ok=True)
            a.out.write_text(json.dumps(out, indent=1))
        row["memory"] = bench_mem(instance_of(pm, specs[0]))
        print(name, "memory", row["memory"], flush=True)
        a.out.write_text(json.dumps(out, indent=1))
    if not a.only and not a.skip_b:
        out["random_graphs"] = bench_b()
        print("random graphs", out["random_graphs"], flush=True)
    out["environment"]["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    a.out.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
