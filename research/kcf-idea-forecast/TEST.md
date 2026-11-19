# TEST: frozen protocol for the lee-slope bypass idea (kcf-idea-forecast)

Frozen 18 November 2026 (Asia/Shanghai), committed before any reach value was joined to any predictor. Changes after this commit go under "Amendments" with a reason. The idea is in `IDEA.md`; the parameter values are in `params.json`.

## What I had already seen when this was frozen

- The `kcf-margin` and `kcf-gust` results, including the Gyeongbuk hour-by-hour reach and ERA5 gust tables.
- The first 17 hourly ERA5 10 m wind values at one Korean grid point on 25 March 2025 (2.8 rising to 9.2 m/s), printed by an API connectivity check.
- Summary statistics of the ERA5 wind for the 28 California fires (10 m: median 1.4, max 8.5 m/s; 100 m: max 13.8 m/s).
- A back-of-envelope done from memory of the Korean figures (8.2 km/h, gusts near 20 m/s): with t_i = 900 s the idea gives almost no gain on 1.5 km ridges, with t_i = 300 s it gives a factor near 1.6. **The primary t_i = 300 s was chosen knowing this.** The physical reason given in `IDEA.md` (a crest line lights a contour line, not a point) stands on its own, but the choice is not blind, so t_i = 900 s and t_i = 0 are reported beside it everywhere.

No California reach value had been compared with wind, terrain or F. No Korean terrain or 100 m wind had been read.

## Data

| role | file | note |
|---|---|---|
| California reach S_h(t) | `../kcf-margin/derived/gofer_reach.csv.gz`, column `reach_km` (5 km separate-fire rule), h = 5 (primary) and 8 | 28 GOFER fires, hourly, UTC; computed and frozen by kcf-margin |
| California wind | `data/era5_ca.csv.gz` (Open-Meteo archive, ERA5, one point per fire as in kcf-margin) | realised series used as a perfect forecast (ASSUMED) |
| California terrain | AWS Terrarium tiles, zoom 11, resampled to 90 m; a 60 × 60 km box centred on the weather point | the box does not depend on where the fire went |
| Korean reach | `../kcf-margin/derived/gyeongbuk_reach.csv`, 25 March 2025 KST, 23 complete issue hours for 5 h, 20 for 8 h | detections, not perimeters |
| Korean wind | ERA5 at the five `kcf-gust` grid points, hourly maximum over points; direction from the point with the largest 100 m wind | fetched only after the California results are committed |
| Korean terrain | same DEM source, 60 × 60 km box centred on 128.95 E, 36.45 N (centre of the kcf-margin box) | built only after the California results are committed |

## Predictors (no fitted constant)

For issue hour t and horizon h, with hourly stamps τ = t+1 … t+h:

- X1 = Σ 0.1·U10(τ)·3.6 km (the 10% rule integrated).
- X2 = Σ 0.1·U10(τ)·F(τ)·3.6 km, with F from `terrain.py` and `params.json`, wind direction in 16 bins, crest wind rounded to 1 m/s, r rounded to 0.1 m/s.
- F_h(t) = X2/X1 (set to 1 when X1 = 0).

Parameter sets: `primary` (w_t 5 m/s, t_b 150 s, t_i 300 s, z0 20 m, crest wind = ERA5 100 m). Sensitivity: `ti0`, `ti900`, `wt2p5`, `wt8`, `gust` (crest wind = ERA5 10 m gust). Only `primary` decides the verdict.

## Held-out design

- X1 and X2 contain no fitted constant, so no California fire is used to tune them.
- The exponent β below is an estimate with a fire-level bootstrap interval. It is a diagnostic and is never fed back into a prediction.
- The one fitted number, the conformal scale κ in the descriptive margin comparison, is set leave-one-fire-out.
- **Korea is test-only.** No Korean predictor is built until `RESULTS.md` has the California section and that commit exists.

## Power precondition (inputs only, checked before any reach is read)

Count issue hours (h = 5, `primary`) with F_h ≥ 1.2. The California arm is **informative** only if there are at least 300 such hours from at least 6 fires. Otherwise the California arm is declared NOT INFORMATIVE and P1 is reported but cannot pass or fail.

## P1 (primary, California): does reach scale with F at equal wind?

Model for the 0.9 quantile of reach: q(S) = κ · X1^γ · F_h^β. γ is a nuisance exponent that absorbs any non-linearity of reach in wind. Fit (κ, γ, β) by minimising the pinball loss at 0.9 over all issue hours with X1 > 0, each fire given total weight 1. Interval: 1,000 bootstrap resamples of fires (seed 20261118), percentile 95%.

- Baseline predicts β = 0. The idea predicts β = 1.
- **Pass:** the 95% interval of β lies above 0.
- **Fail:** the upper end of the interval is below 0.5.
- **Indeterminate:** anything else.

Reported with it: the same fit for h = 8 and for each sensitivity set; the share of hours with S > X1 and with S > X2, split by F_h < 1.2 and F_h ≥ 1.2, fire-weighted.

## P2 (descriptive, California): margins

For each of three margins, R = 3.8 km (kcf-margin, frozen), R = κ·max(X1, 1 km), R = κ·max(X2, 1 km): κ by the kcf-margin split-conformal rule (one random hour per fire, 2,000 draws, seed 20261116, α = 0.10) on the other 27 fires. Report the leave-one-fire-out miss rate (fire-weighted) and the mean margin in km. No pass threshold.

## P3 (Korea, test-only): does the frozen prediction cover 25 March 2025?

With nothing fitted, count the 23 complete 5 h issue hours with S > X1 (misses of the baseline) and with S > X2 (misses of the idea).

- **Pass:** misses(X2) ≤ 2 and misses(X1) − misses(X2) ≥ 3.
- **Fail:** otherwise.

Reported with it: the hour-by-hour table; h = 8; every sensitivity set; the largest hourly predicted rate 0.1·U10·F in km/h beside the 8.2 km/h briefing figure (news-sourced). One fire, one day: no rate is claimed.

## Verdict rule

| novelty search | California arm | P1 | P3 | verdict |
|---|---|---|---|---|
| idea found in print | – | – | – | ALREADY KNOWN |
| clear | informative | Pass | Pass | NEW AND SUPPORTED |
| clear | informative | Fail | any | REFUTED BY THE DATA |
| clear | informative | Pass | Fail | NEW BUT NOT TESTABLE WITH THIS DATA |
| clear | informative | Indeterminate | any | NEW BUT NOT TESTABLE WITH THIS DATA |
| clear | not informative | – | any | NEW BUT NOT TESTABLE WITH THIS DATA |

Korea alone (one fire, one day) cannot make the verdict SUPPORTED.

## Amendments

None at freeze.
