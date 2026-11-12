"""Addendum A1 revision 5: what a 10-fire cohort can detect, estimated from cohort R only.

R's 6 fires are treated as the population of fire-level outcomes. Each fire
contributes its squared-error sums and entry count inside the primary band
(dist_m <= 4,000 m, set by band_rule.py). For each simulated cohort, 10 fires
are drawn with replacement from R, and the A1 primary analysis is run on them:
pooled Brier difference, 2,000 whole-fire bootstrap draws, 95% percentile
interval. The script reports, per comparison:
  - observed R effect: pooled and equal-fire Brier difference
  - power: the share of simulated cohorts whose interval lies below 0
  - median interval half-width, a rough minimum detectable effect
This conditions on 6 fires standing in for the fire population. That is a
strong assumption, so the output is a scale estimate, not a guarantee.

  python power.py --dist DIR --out POWER.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

BAND_M = 4000.0
CANDIDATE = "d4_wind_seed0"
REFERENCES = ("persistence", "dilation_8h")
N_FIRES = 10
SIZING_N = (10, 15, 20, 25, 30, 40, 60)
TARGET_POWER = 0.80
COHORTS = 2000
BOOT = 2000
SEED = 20261112


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    fires, sums, counts = [], {}, []
    for path in sorted(args.dist.glob("*.npz")):
        with np.load(path, allow_pickle=False) as z:
            m = z["dist_m"] <= BAND_M
            y = z["y"][m].astype(float)
            fires.append(path.stem)
            counts.append(int(m.sum()))
            for name in (CANDIDATE,) + REFERENCES:
                sums.setdefault(name, []).append(float(((z[f"p_{name}"][m].astype(float) - y) ** 2).sum()))
    counts = np.array(counts, float)
    rng = np.random.default_rng(SEED)
    out = dict(band_m=BAND_M, candidate=CANDIDATE, n_fires=N_FIRES, cohorts=COHORTS, bootstrap_draws=BOOT,
               seed=SEED, r_fires=fires, r_entries_in_band=counts.astype(int).tolist(), comparisons={})
    for ref in REFERENCES:
        diff = np.array(sums[CANDIDATE]) - np.array(sums[ref])          # per-fire squared-error difference sums
        per_fire = diff / counts
        res = dict(r_pooled_difference=float(diff.sum() / counts.sum()),
                   r_equal_fire_mean_difference=float(per_fire.mean()),
                   r_per_fire_difference=dict(zip(fires, per_fire.tolist())),
                   r_fires_favouring_candidate=int((per_fire < 0).sum()))
        below, halfw, eq_below = 0, [], 0
        for _ in range(COHORTS):
            idx = rng.integers(0, len(fires), N_FIRES)
            cd, cc, pf = diff[idx], counts[idx], per_fire[idx]
            b = rng.integers(0, N_FIRES, size=(BOOT, N_FIRES))
            vals = cd[b].sum(1) / cc[b].sum(1)
            lo, hi = np.quantile(vals, [0.025, 0.975])
            below += hi < 0
            halfw.append((hi - lo) / 2)
            ev = pf[b].mean(1)
            eq_below += np.quantile(ev, 0.975) < 0
        res.update(power_pooled_interval_below_zero=below / COHORTS,
                   power_equal_fire_interval_below_zero=eq_below / COHORTS,
                   median_pooled_interval_half_width=float(np.median(halfw)))
        out["comparisons"][f"{CANDIDATE}__vs__{ref}"] = res
    # Sizing (orchestrator request): power vs cohort size for the binding comparison, vs persistence.
    ref = "persistence"
    diff = np.array(sums[CANDIDATE]) - np.array(sums[ref])
    sizing = {}
    for n in SIZING_N:
        below = 0
        for _ in range(COHORTS):
            idx = rng.integers(0, len(fires), n)
            cd, cc = diff[idx], counts[idx]
            b = rng.integers(0, n, size=(BOOT, n))
            hi = np.quantile(cd[b].sum(1) / cc[b].sum(1), 0.975)
            below += hi < 0
        sizing[str(n)] = below / COHORTS
    out["sizing_vs_persistence"] = dict(target_power=TARGET_POWER, power_by_n_fires=sizing,
                                        smallest_n_reaching_target=next((int(k) for k, v in sizing.items()
                                                                         if v >= TARGET_POWER), None))
    args.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out["sizing_vs_persistence"], indent=1))
    print(json.dumps(out["comparisons"], indent=1))


if __name__ == "__main__":
    main()
