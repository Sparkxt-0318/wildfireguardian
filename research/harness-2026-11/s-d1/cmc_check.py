"""Conditional Monte Carlo (in-edge cut) vs plain trajectory counting at equal cost.

For each synthetic regime: run the CMC sampler (which also yields the plain indicators from the same
trajectories) and the plain sampler alone, time both, and compare per-cell estimator variance:
    efficiency gain = (Var_plain_per_traj * sec_plain_per_traj) / (Var_cmc_per_traj * sec_cmc_per_traj)
Var_plain_per_traj = p(1-p) with p the CMC estimate (Bernoulli variance of the indicator).
Gains are summarised by probability bin. The bias of the lower estimator, bounded by
(cmc_hi - cmc_lo), is reported per bin too.

    python research/harness-2026-11/s-d1/cmc_check.py [--n 4000]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fpp import first_passage, first_passage_cmc  # noqa: E402
from gate1 import SIZE, regimes  # noqa: E402

BINS = [(1e-1, 1.0), (1e-2, 1e-1), (1e-3, 1e-2), (1e-4, 1e-3), (1e-6, 1e-4), (0.0, 1e-6)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--regimes", nargs="*", default=["R3_heterogeneous9_static_wind",
                                                     "R5_c651_magnitude_heterogeneous9"])
    args = ap.parse_args()
    init = np.zeros((SIZE, SIZE), bool)
    init[19:22, 19:22] = True
    small = regimes()["R2_fast_uniform5"]["K"][:, :, :8, :8]
    first_passage(small, init[16:24, 16:24], [1.0], n_samples=2, seed=0)
    first_passage_cmc(small, init[16:24, 16:24], [1.0], n_samples=2, seed=0)
    out = {}
    for name in args.regimes:
        spec = regimes()[name]
        K, T = spec["K"], float(spec["T"])
        horizons = [T / 2, T]
        t0 = time.perf_counter()
        first_passage(K, init, horizons, n_samples=args.n, seed=31)
        sec_plain = (time.perf_counter() - t0) / args.n
        t0 = time.perf_counter()
        r = first_passage_cmc(K, init, horizons, n_samples=args.n, seed=32)
        sec_cmc = (time.perf_counter() - t0) / args.n
        res = dict(T=T, n=args.n, ms_per_traj_plain=1000 * sec_plain, ms_per_traj_cmc=1000 * sec_cmc,
                   gap_fraction=r["gap_fraction"].tolist(), horizons={})
        for h, t in enumerate(horizons):
            p = r["cmc_lo"][h][~init]
            v_cmc = r["cmc_lo_var"][h][~init]
            gap = (r["cmc_hi"][h] - r["cmc_lo"][h])[~init]
            plain_hits = r["plain"][h][~init] * args.n
            rows = []
            for lo, hi in BINS:
                m = (p >= lo) & (p < hi) & (p > 0)
                if not m.any():
                    continue
                gain = (p[m] * (1 - p[m]) * sec_plain) / np.maximum(v_cmc[m] * sec_cmc, 1e-300)
                rows.append(dict(p_bin=[lo, hi], cells=int(m.sum()),
                                 gain_median=float(np.median(gain)),
                                 gain_q10_q90=[float(np.quantile(gain, 0.1)), float(np.quantile(gain, 0.9))],
                                 cmc_rel_se_median=float(np.median(np.sqrt(v_cmc[m] / args.n) / p[m])),
                                 plain_rel_se_median=float(np.median(np.sqrt(p[m] * (1 - p[m]) / args.n) / p[m])),
                                 cells_with_zero_plain_hits=int((plain_hits[m] == 0).sum()),
                                 max_rel_gap_hi_lo=float(np.max(gap[m] / p[m]))))
            res["horizons"][str(t)] = rows
            print(f"== {name} t={t}h  ms/traj plain {1000 * sec_plain:.2f} cmc {1000 * sec_cmc:.2f}")
            for row in rows:
                print(f"   p in [{row['p_bin'][0]:.0e},{row['p_bin'][1]:.0e}) cells {row['cells']:5d} "
                      f"gain median {row['gain_median']:9.2f} (q10 {row['gain_q10_q90'][0]:.2f}, q90 {row['gain_q10_q90'][1]:.2f}) "
                      f"relSE cmc {row['cmc_rel_se_median']:.3f} plain {row['plain_rel_se_median']:.3f} "
                      f"zero-hit cells {row['cells_with_zero_plain_hits']} max rel gap {row['max_rel_gap_hi_lo']:.3f}")
        out[name] = res
    Path(__file__).with_name("RESULTS_cmc.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
