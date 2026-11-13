"""CR1 §7 power table, from A1's committed derive/POWER.json only (no fire data is read).

Method (A1 §6.3, unchanged): cohort R's 6 fires stand in for the fire population.
For each simulated cohort of N fires, drawn with replacement from R, the A1 primary
analysis is run: entry-weighted pooled Brier difference (candidate - reference) in
the 4 km band, 2,000 whole-fire bootstrap draws, 95% percentile interval. Power is
the share of simulated cohorts whose interval lies entirely below 0.

Inputs per fire, from POWER.json: the per-fire mean difference
(`r_per_fire_difference`) and the in-band entry count (`r_entries_in_band`). The
per-fire squared-error difference sum is their product, which is exactly what
derive/power.py resamples.

Scenarios:
  - "R effect": the per-fire differences as observed on R.
  - "half": every fire shifted by -0.5 * (pooled R effect) * count, which halves
    the pooled effect and keeps the between-fire spread (derive/power.py's rule).

The candidate is the available proxy `d4_wind_seed0`; the eventual CR1 candidate's
effect is unknown. Six fires are a very small population, so every figure is a
rough scale estimate.

    python power_cr1.py --power ../derive/POWER.json --out POWER_CR1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

N_GRID = (20, 30, 45, 60, 90)
COHORTS = 2000
BOOT = 2000
SEED = 20261113
REFERENCES = ("persistence", "dilation_8h", "logistic")
SCENARIOS = {"r_effect": 1.0, "half_r_effect": 0.5}


def power_for(diff: np.ndarray, counts: np.ndarray, n: int, rng: np.random.Generator) -> float:
    below = 0
    k = len(diff)
    for _ in range(COHORTS):
        idx = rng.integers(0, k, n)
        cd, cc = diff[idx], counts[idx]
        b = rng.integers(0, n, size=(BOOT, n))
        hi = np.quantile(cd[b].sum(1) / cc[b].sum(1), 0.975)
        below += hi < 0
    return below / COHORTS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--power", required=True, type=Path, help="A1 derive/POWER.json")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    raw = a.power.read_bytes()
    src = json.loads(raw)
    fires = src["r_fires"]
    counts = np.array(src["r_entries_in_band"], float)
    cand = src["candidate"]
    rng = np.random.default_rng(SEED)
    out = dict(source=str(a.power.name), source_sha256=hashlib.sha256(raw).hexdigest(), candidate=cand,
               r_fires=len(fires), n_grid=list(N_GRID), cohorts=COHORTS, bootstrap_draws=BOOT, seed=SEED,
               method="A1 §6.3: resample R fires as the population; pooled entry-weighted ΔBrier; "
                      "whole-fire percentile bootstrap; power = share of cohorts with 95% upper bound < 0",
               comparisons={})
    for ref in REFERENCES:
        per_fire = src["comparisons"][f"{cand}__vs__{ref}"]["r_per_fire_difference"]
        diff = np.array([per_fire[f] for f in fires]) * counts
        effect = diff.sum() / counts.sum()
        res = dict(r_pooled_difference=float(effect))
        for name, scale in SCENARIOS.items():
            d = diff + (scale - 1.0) * effect * counts
            res[name] = {str(n): power_for(d, counts, n, rng) for n in N_GRID}
        out["comparisons"][ref] = res
    a.out.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    for ref, r in out["comparisons"].items():
        print(ref, f"R effect {r['r_pooled_difference']:+.3e}")
        for name in SCENARIOS:
            print("  ", name, r[name])


if __name__ == "__main__":
    main()
