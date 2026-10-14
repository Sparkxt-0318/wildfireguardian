# FARSITE evaluation verification — 2026-10-12

The actual six-hour FishCreek FARSITE run completed over the exact UTC interval
2024-08-21 06:00 through 12:00. The native timing file confirms actual start,
actual end, and 360 elapsed simulation minutes. The arrival output is identical
to three earlier native executions with spotting disabled.

The original 103 × 73 rectangle is retained after removing only the configured
one-cell exterior buffer from the native 105 × 75 grid. All 7,519 physical input
cells are available. The simulation has five initial burns, thirteen new burns,
and eighteen total burns. Original reference availability excludes two simulated
new burns from scoring. New-burn scoring uses 2,637 cells, with TP=3, FP=8,
TN=2,612, FN=14. Occupancy scoring uses 2,642 cells, with TP=8, FP=8,
TN=2,612, FN=14.

An independent deterministic Bernoulli oracle reproduces all nine distances from
22/2637 and 22/2642. Exact KL, NLL, and Bhattacharyya distances are infinite;
separately floored values preserve epsilon=1e-7. Predictions are binary and have
no Monte Carlo uncertainty fields.

All physical/weather, grid, cutoff-source, generated-input, implementation,
engine, portability-patch, and 30 PNG/SVG hashes were verified. Independent
reviews checked all 15 figures for labels, support, infinite values, and layout.
The notebook passes schema/code-syntax validation, and its new report-preview
cell executed against the completed artifact.

Repository regression: **2,251 passed**, zero failures/errors/skips.
The run emitted 272 plotting dependency deprecation warnings. Test duration was
281.31 seconds.

The [report](../runs/20261012_farsite_6h/report.md),
[JSON validation record](farsite_evaluation_validation_20261012.json),
[JUnit results](farsite_regression_20261012.xml), and
[option/assumption reference](farsite_evaluation.md) retain the evidence.
