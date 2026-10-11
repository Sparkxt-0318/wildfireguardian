# Cumulative model evaluation runner verification — 2026-10-11

The new `python -m wildfire evaluate-cumulative` command evaluates saved tensor
checkpoints using an editable whole-hour cumulative horizon, defaulting to six
hours, and writes Markdown, JSON, CSV and optional prediction-array reports.

The [runner](../wildfire/cumulative_report.py), [CLI entry](../wildfire/__main__.py)
and [independent tests](../tests/test_cumulative_report.py) are covered by
**2,048 passing regression tests**, with zero failures, errors or skips, in
70.69 seconds. The suite includes 21 new runner tests. It
records 272 warnings. [Test log](cumulative_models_final_tests_20261011.log)
and [JUnit record](cumulative_models_final_tests_20261011.xml) are preserved.

The installed `.venv/bin/wildfire` console command also returned exit status
zero and wrote a bounded plan. The dispatcher preserves success rather than
passing a result dictionary to the console exit handler.

## Exhaustive model/case plan

The [final plan](../demonstration/cumulative_models/20261011_plan_final/report.md) contains all
**561** canonical tensor checkpoints across the current categorical benchmark,
the earlier multiscale experiment and the Bayesian average. All have compatible
real-data schemas and ten common exclusively held-out test events. With six-hour
horizons and six-hour chronological cutoff stride, the catalog provides
**1,860 cases per model**, or **1,043,460 model/case evaluations**. Twelve saved
random-forest artifacts are listed as outside the public recursive tensor API.
Synthetic workflow fixtures and optimizer/roundtrip copies are excluded by the
chosen roots and canonical filename rule. No exhaustive simulation was run.

## Final-source bounded real-data execution

The [generated report](../demonstration/cumulative_models/20261011_all_models_6h_final/report.md) evaluates all
561 checkpoints, covering all five maintained tensor architectures, at
`KFS_06`, cutoff `2025-03-24T03:00:00Z`, with the exact six-hour endpoint. This
functional diagnostic uses **8 trajectories**, rather than the production
command's default 1,024 trajectories. It completed in 57.42
seconds with no failed models or cases.

Every model retains the complete **14 × 14 rectangle**, with all 196 cells
valid. Prediction exports have shape `[561,1,1,14,14]`. Original reference masks
restrict new-burn evaluation to 51 cells with four positives, and total burned
occupancy to 78 cells with 31 positives. The 27 initial burns have exact new-burn
probability zero, total burned probability one and zero new-burn Monte Carlo
standard error and Wilson bounds. Shared cohorts are identical across models.

All checkpoint hashes and recorded implementation hashes were checked. The
final seeded prediction arrays agree exactly with the preserved earlier run.
Both JSON records are strict JSON; infinite exact losses remain strings, with
floored scores separately reported. The scratch entry files were removed on
successful completion, and progress status is complete.

| Export | Rows |
| --- | ---: |
| `summary.csv` | 2,244 |
| `per_event.csv` | 2,244 |
| `per_cutoff.csv` | 2,244 |
| `calibration.csv` | 31,416 |

The new independent tests include pooled ranking-score oracles, original-mask
and shared-cohort checks, bounded data loading, guarded cutoff-only inputs,
local seed stability, exact/undefined scores, populated/empty CSV transitions,
registry integrity, explicit request validation, failed progress/partial
artifact handling and output preservation.

## Records and results

- [Complete verification JSON](cumulative_models_validation_20261011.json)
- [Final generated comparison](../demonstration/cumulative_models/20261011_all_models_6h_final/report.md)
- [Final comparison JSON](../demonstration/cumulative_models/20261011_all_models_6h_final/report.json)
- [Pooled comparison CSV](../demonstration/cumulative_models/20261011_all_models_6h_final/summary.csv)
- [Full-rectangle prediction arrays](../demonstration/cumulative_models/20261011_all_models_6h_final/predictions/000000.npz)
- [Final exhaustive plan JSON](../demonstration/cumulative_models/20261011_plan_final/protocol.json)

This execution verifies functionality and source provenance on one bounded
held-out case. Its small trajectory budget is a diagnostic; it is not an
exhaustive forecasting benchmark. The requested full command is documented in
[the README](../README.md#run-cumulative-evaluation-for-every-saved-model) and
[the API reference](api.md#evaluate-all-saved-models-from-the-command-line).
