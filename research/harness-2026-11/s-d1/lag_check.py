"""Iris's alternative explanation: is the hourly-vs-continuous gap mostly synchronous-update lag?

Arms, on identical kernels and ignition (the gate1.py regimes): hourly CA; hourly CA with the half-step
lag correction (cells ignited in a step emit for half a step; ``fpp.cellular_automaton(half_step=True)``);
CA with m = 2, 4, 8 sub-steps; first-passage. Reported: mean burned area at T and the gate1 distances
(L1, Linf of per-cell per-hour marginals, relative W1 of burned area) to first-passage, plus the share
of the hourly->first-passage area gap each arm closes.

    python research/harness-2026-11/s-d1/lag_check.py [--n 2000]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fpp import cellular_automaton, first_passage  # noqa: E402
from gate1 import SIZE, distances, regimes  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--regimes", nargs="*", default=["R5_c651_magnitude_heterogeneous9",
                                                     "R3_heterogeneous9_static_wind", "R2_fast_uniform5"])
    args = ap.parse_args()
    init = np.zeros((SIZE, SIZE), bool)
    init[19:22, 19:22] = True
    out = {}
    for name in args.regimes:
        spec = regimes()[name]
        K, T = spec["K"], spec["T"]
        hours = np.arange(1, T + 1, dtype=float)
        c, arr = first_passage(K, init, hours, n_samples=args.n, seed=1, keep_arrivals=args.n)
        ref_F = c / args.n
        ref_area = ((arr <= T) & ~init).sum(axis=(1, 2))
        ref_mean = ref_area.mean()
        arms = {}
        for arm, kw in (("hourly", dict(dt=1.0)), ("hourly_half_step", dict(dt=1.0, half_step=True)),
                        ("m2", dict(dt=0.5)), ("m4", dict(dt=0.25)), ("m8", dict(dt=0.125))):
            t0 = time.perf_counter()
            cc, tot = cellular_automaton(K, init, hours, n_samples=args.n, seed=200 + len(arms),
                                         return_totals=True, **kw)
            sec = time.perf_counter() - t0
            d = distances(cc / args.n, ref_F, tot[-1], ref_area, ref_mean)
            arms[arm] = dict(mean_area=float(tot[-1].mean()), se=float(tot[-1].std(ddof=1) / np.sqrt(args.n)),
                             seconds=sec, **d)
        gap = ref_mean - arms["hourly"]["mean_area"]
        for v in arms.values():
            v["share_of_hourly_gap_closed"] = float((v["mean_area"] - arms["hourly"]["mean_area"]) / gap)
        out[name] = dict(T=T, n=args.n, first_passage_mean_area=float(ref_mean),
                         first_passage_se=float(ref_area.std(ddof=1) / np.sqrt(args.n)), arms=arms)
        print(f"== {name}: first-passage {ref_mean:.2f} ± {out[name]['first_passage_se']:.2f}")
        for k, v in arms.items():
            print(f"   {k:17s} area {v['mean_area']:8.2f} ± {v['se']:.2f}  gap closed {100 * v['share_of_hourly_gap_closed']:6.1f}%"
                  f"  L1 {v['L1']:.4f}  W1rel {v['W1_rel']:.3f}  {v['seconds']:.1f}s", flush=True)
    Path(__file__).with_name("RESULTS_lag.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
