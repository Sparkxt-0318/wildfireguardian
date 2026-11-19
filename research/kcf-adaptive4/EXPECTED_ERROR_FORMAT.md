# Format of `derived/expected_error.csv.gz` (for research/kcf-robust)

Written with the code, before the file was produced or scored. One row per fire, issue hour and lead time. Every
row comes from a model that was fitted without that fire (California: fitted on the 16 development fires; Korea and
25 March: leave-one-fire-out). The model is the primary BASE with the TARGETED correction (PROTOCOL sections 2 and 4).

Gzip-compressed CSV, comma separated, header row, UTF-8, distances in km, times in UTC.

| column | type | meaning |
|---|---|---|
| `set` | text | `CA-HELD` (12 held-out GOFER fires), `KR` (12 Korean fires, Choi rasters), `DET` (KFS_01, detection product, 25 March 2025 KST) |
| `fire` | text | fire name (GOFER) or id (`KFS_nn`) |
| `product` | text | `GOFER`, `CHOI` or `DET` |
| `t_utc` | `YYYY-MM-DD HH:MM:SS` | issue hour t; the forecast uses only what is known at t |
| `lead_h` | integer 1..8 | lead time h; the row describes the fire's reach over (t, t+h] |
| `wind_kmh` | number | the wind term: issued forecast wind (maximum over the next 8 h), km/h |
| `k` | number | dimensionless spread coefficient in use for this lead (pooled, after calibration) |
| `pooled_margin_km` | number | k x wind x lead before any correction; the scale of the error quantiles |
| `margin_km` | number | **the issued margin**: distance from the known burned area that the fire is expected to stay within over the lead, at a 10% miss rate |
| `corrected` | 0/1 | 1 if any online correction is active at this hour |
| `blamed_term` | text | term blamed for recent misses at this hour: `wind`, `k`, `start`, `timing` or `none` |
| `wind_mult`, `k_mult` | number | multipliers on the wind term and on k (1 = no correction) |
| `start_add_km` | number | distance added for a starting-area deficit |
| `timing_hold_h` | integer | hours for which the wind term is held at its recent maximum |
| `err_q50_km`, `err_q80_km`, `err_q90_km`, `err_q95_km`, `err_q99_km` | number | **the model's own expected reach error**: calibrated quantiles of (reach - `margin_km`). Negative = the fire is expected to stay that far inside the margin; positive = that far beyond it. Read "with probability p the reach is at most `margin_km` + `err_qP_km`" |
| `scored` | 0/1 | 1 if this (t, lead) is an eligible issue hour with a known outcome |
| `reach_km` | number or empty | realised reach over the lead. **Outcome, for checking only: not known at t and never an input** |

How the quantiles are made: on the training fires, the ratio (reach - margin) / `pooled_margin_km` is collected per
lead and per `corrected` state; its fire-weighted p-quantile times `pooled_margin_km` is `err_qP_km` (if a state has
fewer than 200 training rows at a lead, both states are pooled). So the expected error grows with forecast wind and
with lead, and differs between hours with and without an active correction.

How a router can use it. A reach bound at confidence p for lead h is `margin_km + err_qP_km`; a robust router can
take p = 0.95 or 0.99 for the worst case and p = 0.5 for the nominal case, or treat the five quantiles as scenario
weights (0.5, 0.3, 0.1, 0.05, 0.04, 0.01 for the six intervals they delimit). Whether these quantiles are calibrated
on held-out fires is reported per lead in RESULTS.md (`numbers_final.json`, key `expected_error_calibration`):
the share of scored rows with reach - margin above `err_qP_km` should be 1 - p.

Limits: the margin is a scalar distance around the whole known area (no direction); the wind term is one 8 h window
for every lead; rows with `scored` = 0 have a margin but no outcome.
