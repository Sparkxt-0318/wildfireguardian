"""Share of cells repaired and the extra time of the exact local repair (threshold 0.05, fixed), at real
grid size (Iris item 4). Same kernels as cmc_real.py; one horizon, 12 h.

    python research/harness-2026-11/s-d1/repair_check.py [--n 1000] [--size 160]
"""
import argparse
import json
import resource
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cmc_real import KERNELS, build  # noqa: E402
from fpp import first_passage_cmc_repaired  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--size", type=int, default=160)
    ap.add_argument("--threshold", type=float, default=0.05)
    args = ap.parse_args()
    K0, i0 = build(16, "fast_0p6")
    first_passage_cmc_repaired(K0, i0, 2.0, n_samples=2, seed=0)  # JIT warm-up
    out = dict(n=args.n, size=args.size, horizon_h=12.0, threshold=args.threshold, results={})
    for kernel in KERNELS:
        K, init = build(args.size, kernel)
        r = first_passage_cmc_repaired(K, init, 12.0, n_samples=args.n, seed=1, threshold=args.threshold)
        unb = ~init
        lo, hi, est = r["lo"][unb], r["hi"][unb], r["estimate"][unb]
        pos = est > 0
        flagged = r["flagged"][unb]
        rel_err_lo = np.abs(lo[flagged] - est[flagged]) / np.maximum(est[flagged], 1e-300)
        res = dict(
            cells_with_positive_estimate=int(pos.sum()), cells_flagged=int(flagged.sum()),
            share_flagged_of_positive=float(flagged.sum() / max(pos.sum(), 1)),
            repairs=r["repairs"], repairs_per_trajectory=r["repairs"] / args.n,
            ms_per_traj_pass1=1000 * r["seconds_pass1"] / args.n, ms_per_traj_pass2=1000 * r["seconds_pass2"] / args.n,
            flagged_p_q10_q50_q90=[float(x) for x in np.quantile(est[flagged], [0.1, 0.5, 0.9])] if flagged.any() else None,
            lo_rel_error_on_flagged_q50_max=[float(np.median(rel_err_lo)), float(rel_err_lo.max())] if flagged.any() else None,
            peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
        out["results"][kernel] = res
        print(kernel, json.dumps(res), flush=True)
    (HERE / "RESULTS_repair.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
