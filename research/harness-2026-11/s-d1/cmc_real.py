"""Conditional estimators at a real grid size, with peak memory and a fair hourly baseline (Iris).

Grid 160x160 (larger than the Wapiti case rectangle 111x105), 9x9 heterogeneous kernels built like
gate1.R5 (c651-magnitude, mean coefficient sum 0.25/h) and gate1.R3 (0.6/h), 3x3 centre ignition, 12 h.
Arms, each in a fresh subprocess (peak RSS = ru_maxrss of that process):
  fpp_plain   first-passage, trajectory counting
  fpp_cmc     first-passage, in-edge-cut conditional estimator (lower value; upper value also stored)
  ca_plain    hourly CA (the existing recursion), trajectory counting
  ca_cmc      hourly CA, conditional estimator Y_i = sum_k 1{unburned before k} q_i(k)
Efficiency gain of a conditional arm over its own plain arm, per cell, at equal wall time:
  (p(1-p) * sec_plain_per_traj) / (Var_cond_per_traj * sec_cond_per_traj).
The two models differ (hourly vs continuous), so each conditional estimator is compared with its own
plain estimator only; probabilities are binned on that model's own conditional estimate.

    python research/harness-2026-11/s-d1/cmc_real.py [--n 1000] [--size 160]
"""
import argparse
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BINS = [(1e-1, 1.0), (1e-2, 1e-1), (1e-3, 1e-2), (1e-4, 1e-3), (1e-6, 1e-4)]
KERNELS = {"c651_magnitude_0p25": (13, 0.25), "fast_0p6": (11, 0.6)}


def build(size, kernel):
    sys.path.insert(0, str(HERE))
    import gate1
    gate1.SIZE = size
    seed, total = KERNELS[kernel]
    K = gate1.heterogeneous_kernel(seed, [0.0], mean_total=total)
    init = np.zeros((size, size), bool)
    c = size // 2
    init[c - 1:c + 2, c - 1:c + 2] = True
    return K, init


def child(arm, n, size, kernel, out):
    from fpp import cellular_automaton, first_passage, first_passage_cmc
    K, init = build(size, kernel)
    T = [12.0]
    first_passage(K[:, :, :12, :12], np.eye(12, dtype=bool), [1.0], n_samples=2, seed=0)
    first_passage_cmc(K[:, :, :12, :12], np.eye(12, dtype=bool), [1.0], n_samples=2, seed=0)
    t0 = time.perf_counter()
    if arm == "fpp_plain":
        c, _ = first_passage(K, init, T, n_samples=n, seed=1)
        res = dict(p=c[0] / n)
    elif arm == "fpp_cmc":
        r = first_passage_cmc(K, init, T, n_samples=n, seed=2)
        res = dict(p=r["cmc_lo"][0], hi=r["cmc_hi"][0], var=r["cmc_lo_var"][0], plain=r["plain"][0])
    elif arm == "ca_plain":
        c = cellular_automaton(K, init, T, dt=1.0, n_samples=n, seed=3, batch=250)
        res = dict(p=c[0] / n)
    elif arm == "ca_cmc":
        r = cellular_automaton(K, init, T, dt=1.0, n_samples=n, seed=4, batch=250, return_cmc=True)
        res = dict(p=r["cmc_mean"][0], var=r["cmc_var"][0], plain=r["counts"][0] / n)
    sec = time.perf_counter() - t0
    np.savez(out, init=init, seconds=sec, peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, **res)


def gains(p, var, sec_plain, sec_cond, n, init):
    m0 = ~init
    p, var = p[m0], var[m0]
    rows = []
    for lo, hi in BINS:
        m = (p >= lo) & (p < hi)
        if not m.any():
            continue
        g = (p[m] * (1 - p[m]) * sec_plain) / np.maximum(var[m] * sec_cond, 1e-300)
        rows.append(dict(p_bin=[lo, hi], cells=int(m.sum()), gain_median=float(np.median(g)),
                         gain_q10_q90=[float(np.quantile(g, 0.1)), float(np.quantile(g, 0.9))]))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--size", type=int, default=160, help="multiple of 8 (fuel blocks)")
    ap.add_argument("--child", nargs=2, default=None)
    ap.add_argument("--kernel", default="c651_magnitude_0p25")
    args = ap.parse_args()
    if args.child:
        sys.path.insert(0, str(HERE))
        child(args.child[0], args.n, args.size, args.kernel, args.child[1])
        return
    out = dict(n=args.n, size=args.size, horizon_h=12, results={})
    with tempfile.TemporaryDirectory() as tmp:
        for kernel in KERNELS:
            arms = {}
            for arm in ("fpp_plain", "fpp_cmc", "ca_plain", "ca_cmc"):
                path = str(Path(tmp) / f"{kernel}_{arm}.npz")
                subprocess.run([sys.executable, __file__, "--child", arm, path, "--n", str(args.n),
                                "--size", str(args.size), "--kernel", kernel], check=True)
                arms[arm] = dict(np.load(path))
            init = arms["fpp_plain"]["init"]
            res = {a: dict(seconds=float(v["seconds"]), ms_per_traj=1000 * float(v["seconds"]) / args.n,
                           peak_rss_mib=float(v["peak_rss_mib"]),
                           mean_new_cells=float(v["p"][~init].sum())) for a, v in arms.items()}
            spf = res["fpp_plain"]["seconds"] / args.n
            spc = res["ca_plain"]["seconds"] / args.n
            res["gain_fpp_cmc_vs_fpp_plain"] = gains(arms["fpp_cmc"]["p"], arms["fpp_cmc"]["var"], spf,
                                                     res["fpp_cmc"]["seconds"] / args.n, args.n, init)
            res["gain_ca_cmc_vs_ca_plain"] = gains(arms["ca_cmc"]["p"], arms["ca_cmc"]["var"], spc,
                                                   res["ca_cmc"]["seconds"] / args.n, args.n, init)
            gap = (arms["fpp_cmc"]["hi"] - arms["fpp_cmc"]["p"])[~init]
            pp = arms["fpp_cmc"]["p"][~init]
            pos = pp > 0
            res["fpp_cmc_rel_gap_hi_lo_q50_q99_max"] = [float(x) for x in np.quantile(gap[pos] / pp[pos], [0.5, 0.99, 1.0])]
            out["results"][kernel] = res
            print(kernel, json.dumps(res, indent=1), flush=True)
    (HERE / "RESULTS_cmc_real.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
