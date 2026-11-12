# S-D4mix: rate-mixture layer (development)

Owner: Marcus. Adopted by the orchestrator from Iris as a development experiment. It is the cheapest form of the direction document's shared latent factor (D4).

**Idea.** Run the existing model at a few global rate multipliers and mix the per-cell probabilities. The kernels are not refitted.
- The multiplier grid is frozen in S-D9 A1 §3.1: m ∈ {1, 2, 4, 8, 16}, applied to `d4_wind_rebuilt`.
- The mixture weights are fit on the A1 training pool.
- It stays development-only until it performs in leave-one-fire-out on the exposed cohort R (US2024).

## Pre-check without a rollout (`precheck.py` → `RESULTS_precheck.json`)

DEVELOPMENT-ONLY, on the exposed US2024 cohort R. `dist_m` comes from S-D9's `derive_dist.py` and is regenerated locally, not committed. The run is recorded in the S-D9 ledger.

Command: `python research/harness-2026-11/s-d4mix/precheck.py --dist-dir <derive_dist output>`.

Verified byte-identical by Hannah and by Owen (ada7709, PASS WITH NOTES).

**Valid findings for `p_d4_wind_seed0`, 4 km band, 273 intervals:**
- **Decay with distance.** Within an interval, the median predicted probability falls by a median factor of **0.086 per 375 m cell**. Owen measured this as robust to the 1e-12 log floor: 0.079–0.086 across floors. The q10 is NOT robust: 0.070 at a 1e-12 floor, 0.041 at 1e-20.
- **Tail concentration.** Tail positives are those with p < 1e-5. The top 10 intervals hold **79%** of the 1,310 tail positives, against 32% of non-tail positives. The share depends on the threshold: 69% at p < 1e-4, 84% at 1e-6, 89% at 1e-7 (Owen).
- **Few independent units.** 8 of the top 10 intervals come from 2 fires (Wapiti 4, Fish Creek 4).
- **Tail intervals are faster.** Their median apparent speed is about 4× higher (89 vs 23 m/h, measured as max positive distance / hours). This is a **lower bound**: in 6 of the top 10 intervals the max positive distance is ≥ 3.9 km and is truncated by the 4 km band.

**NOT valid, do not quote: the `p_c651_mc` decay and tail numbers** (Owen).
- 27.8% of `p_c651_mc` values in the band are exact Monte Carlo zeros, and 862 of 2,730 bin medians sit at the 1e-12 log floor. So the slope is set by the floor: the per-cell factor q50 is 0.035 / 0.0034 / 0.0002 at floors 1e-12 / 1e-20 / 1e-30, and 0.39 with floored bins dropped.
- Its "tail" is just MC-zero positives: 571 at every threshold from 1e-4 to 1e-7.

**Reading (hypothesis).** These findings are consistent with Iris's mechanism: one typical spread speed, with probability falling geometrically with distance, while a few run intervals carry the near-zero misses. The evidence is thin, because the top intervals come from only two fires. The model has to be tested by the rollouts.

## Multipliers with the first-passage sampler

With static (repeated-cutoff) weather, scaling every rate by c scales every first-passage arrival time by exactly 1/c pathwise. The test is `research/harness-2026-11/s-d1/tests/test_fpp.py::test_speed_multiplier_scales_arrival_times_exactly_under_static_kernels`, which covers both burned and unburned branches. So one trajectory set serves every multiplier.

This does not hold for hourly-varying weather unless all rates share one time profile. The hourly recursion does not have the property at all.

## Blocked on

Daniel's rebuilt covariates (weather after the Open-Meteo reset) and the A1 §3.1 `d4_wind_rebuilt` refit.
