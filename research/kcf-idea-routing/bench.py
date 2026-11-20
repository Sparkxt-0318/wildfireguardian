"""Benchmark of the margin field against the existing backward pass. The plan is BENCH_PLAN.md (frozen first).

    python3 research/kcf-idea-routing/bench.py --data-root data/routing --out research/kcf-idea-routing/results/bench.json

Sections can be run separately with --sections t12,t3,mem,b (default: all).
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/kcf-theorem"))
sys.path.insert(0, str(ROOT / "research/harness-2026-11/F-3.1"))
import randgraphs  # noqa: E402
from deadline_field.core import backward, issue_set  # noqa: E402
from margin_field import field as mf  # noqa: E402
from margin_field import pl  # noqa: E402
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
    return {"median": round(statistics.median(xs), 4), "min": round(min(xs), 4), "max": round(max(xs), 4)}


def sampled(doc):
    specs = cache_specs(doc)
    rng = random.Random(SEED)
    return specs if len(specs) <= 6 else rng.sample(specs, 6)


def instance_of(pm, spec):
    (dn, dwell, win), origins = spec
    return pm.instance("cert", [{"node": dn, "dwell": dwell, "window": list(win)}], sorted(origins))


def bench_t12(inst):
    E = len(inst.tail)
    row = {"edges": E}
    # ---- T1
    old, new, mism = [], [], 0
    for r in range(REPEATS):
        order = ("old", "new") if r % 2 == 0 else ("new", "old")
        res = {}
        for which in order:
            if which == "old":
                t, res["old"] = timed(lambda: backward(inst))
                old.append(t)
            else:
                t, res["new"] = timed(lambda: mf.margin_field(inst, 0))
                new.append(t)
        if r == 0:
            ref, fld = res["old"], res["new"]
            mism = sum(pl.level_set(fld.mu[s], 0) != ref.R[s] or pl.level_set(fld.gamma[s], 0) != ref.G[s]
                       for s in range(E))
            row["T1_existing_pushes"], row["T1_new_pops"] = ref.stats["pushes"], fld.stats["pops"]
        del res
    row["T1"] = {"existing_s": med(old), "new_s": med(new), "mismatches": mism,
                 "ratio": round(statistics.median(old) / statistics.median(new), 3)}
    # ---- T2: one margin pass with M = 600, timed once per repeat and shared by every K
    widened = {m: None for K in KS for m in margins_for(K)}
    t_widen = {}
    for m in widened:
        t_widen[m], widened[m] = timed(lambda: mf.widen(inst, m))
    t_old = {m: [] for m in widened}
    t_pass, t_read = [], {K: [] for K in KS}
    refs = {}
    for r in range(REPEATS):
        def run_old():
            for m in widened:
                t, ref = timed(lambda: backward(widened[m]))
                t_old[m].append(t)
                if r == 0:
                    refs[m] = (ref.R, ref.G)

        def run_new():
            t, fld = timed(lambda: mf.margin_field(inst, M))
            t_pass.append(t)
            for K in KS:
                t, got = timed(lambda: {m: ([pl.level_set(f, m) for f in fld.mu],
                                            [pl.level_set(f, m) for f in fld.gamma]) for m in margins_for(K)})
                t_read[K].append(t)
                if r == 0:
                    row.setdefault("T2_mismatches", {})[str(K)] = sum(
                        got[m][0][s] != refs[m][0][s] or got[m][1][s] != refs[m][1][s]
                        for m in margins_for(K) for s in range(E)) if refs else None
            if r == 0:
                row["new_M600_stats"] = fld.stats
            return fld

        if r % 2 == 0:
            run_old()
            run_new()
        else:
            fld = run_new()
            run_old()
            del fld
    if any(v is None for v in row["T2_mismatches"].values()):          # first repeat always runs old first
        raise AssertionError("reference missing")
    row["new_pass_M600_s"] = med(t_pass)
    row["T2"] = {}
    for K in KS:
        ms = margins_for(K)
        old_tot = [sum(t_old[m][r] for m in ms) for r in range(REPEATS)]
        new_tot = [t_pass[r] + t_read[K][r] for r in range(REPEATS)]
        row["T2"][str(K)] = {
            "margins": ms, "existing_s": med(old_tot), "existing_widen_s_not_counted": round(sum(t_widen[m] for m in ms), 4),
            "new_pass_plus_readoff_s": med(new_tot), "new_readoff_s": med(t_read[K]),
            "ratio": round(statistics.median(old_tot) / statistics.median(new_tot), 3),
            "ratio_pass_only": round(statistics.median(old_tot) / statistics.median(t_pass), 3),
            "mismatches": row["T2_mismatches"][str(K)]}
    del row["T2_mismatches"]
    return row


def bench_t3(inst, origin_idx):
    t_old = t_widen = 0.0
    ref = {}
    for m in range(M + 1):
        tw, wi = timed(lambda: mf.widen(inst, m))
        t_widen += tw
        t, sets = timed(lambda: (lambda f: [issue_set(f, o) for o in origin_idx])(backward(wi)))
        t_old += t
        ref[m] = sets
    t_pass, fld = timed(lambda: mf.margin_field(inst, M))
    t_read, got = timed(lambda: (lambda fo: {m: [pl.level_set(f, m) for f in fo] for m in range(M + 1)})(
        [mf.issue_margin(fld, o) for o in origin_idx]))
    mism = sum(got[m] != ref[m] for m in range(M + 1))
    return {"margins": M + 1, "origins": len(origin_idx), "existing_s": round(t_old, 2),
            "existing_widen_s_not_counted": round(t_widen, 2), "new_pass_s": round(t_pass, 4),
            "new_readoff_s": round(t_read, 4), "new_total_s": round(t_pass + t_read, 4),
            "ratio": round(t_old / (t_pass + t_read), 1), "margins_with_mismatch": mism}


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

    def keep_fields(f):                       # what a caller keeps: the sets, not the instance copy
        return (f.R, f.G)

    ms = margins_for(16)
    wid = [mf.widen(inst, m) for m in ms]
    return {"existing_one_pass_margin0": measure(lambda: keep_fields(backward(inst))),
            "existing_16_passes_all_kept": measure(lambda: [keep_fields(backward(w)) for w in wid]),
            "new_M600_mu_gamma_only": measure(lambda: (lambda f: (f.mu, f.gamma))(mf.margin_field(inst, M))),
            "new_M600_with_tents": measure(lambda: mf.margin_field(inst, M)),
            "new_M0_mu_gamma_only": measure(lambda: (lambda f: (f.mu, f.gamma))(mf.margin_field(inst, 0)))}


def bench_b():
    cases = []
    for fam in ("general", "closure"):
        for seed in range(6000):
            rng = random.Random(f"margin-{fam}-{seed}")
            inst, _ = randgraphs.generate(rng, fam)
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
            "new_s": med(new), "ratio": round(statistics.median(old) / statistics.median(new), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sections", default="t12,t3,mem,b")
    ap.add_argument("--only")
    a = ap.parse_args()
    sections = set(a.sections.split(","))
    out = json.loads(a.out.read_text()) if a.out.exists() else {}
    out["environment"] = {"python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
                          "cpu_count": os.cpu_count(), "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                          "repeats": REPEATS, "M": M, "seed": SEED}
    out.setdefault("caches", {})
    for cp in sorted(glob.glob(str(ROOT / "planner/cache/*/*.json"))):
        if a.only and a.only not in cp:
            continue
        name = str(Path(cp).relative_to(ROOT))
        doc, pm = load(cp, a.data_root)
        specs = sampled(doc)
        row = out["caches"].setdefault(name, {"n_specs_in_cache": len(cache_specs(doc)), "sampled": len(specs)})
        if "t12" in sections:
            row["specs"] = []
            for spec in specs:
                inst = instance_of(pm, spec)
                r = bench_t12(inst)
                r["spec"] = [spec[0][0], spec[0][1], list(spec[0][2])]
                row["specs"].append(r)
                print(name, r["spec"][0], "T1", r["T1"]["ratio"], "T2", {k: v["ratio"] for k, v in r["T2"].items()},
                      flush=True)
                a.out.write_text(json.dumps(out, indent=1))
        if "t3" in sections:
            inst = instance_of(pm, specs[0])
            row["T3"] = bench_t3(inst, [pm.nidx[o] for o in sorted(specs[0][1])])
            print(name, "T3", row["T3"], flush=True)
            a.out.write_text(json.dumps(out, indent=1))
        if "mem" in sections:
            row["memory"] = bench_mem(instance_of(pm, specs[0]))
            print(name, "memory", row["memory"], flush=True)
            a.out.write_text(json.dumps(out, indent=1))
    if "b" in sections and not a.only:
        out["random_graphs"] = bench_b()
        print("random graphs", out["random_graphs"], flush=True)
    out["environment"]["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
