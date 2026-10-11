# Explicit-duration cumulative evaluation validation

The implementation requires the caller to enter `hours`. Each duration must already be present in the cumulative prediction. The evaluator aligns known reference states at the exact cutoff and endpoint and scores each horizon separately.

Public access is through `CumulativePrediction.evaluate(observed, *, hours, ...)` or `wildfire.evaluate_cumulative(prediction, observed, *, hours, ...)`. The complete protocol is documented in [the API reference](api.md#evaluate-cumulative-predictions).

## Verification

- Full regression suite: **2,003 passed**, no failures, errors or skips; 85.21 seconds.
- Focused evaluator coverage: **70 passing tests**, including independently computed metric and distance definitions, reference alignment, masks, weighted numerical extremes and real recursive prediction integration.
- Probability demonstration: **8 of 8 code cells executed**, no errors; source unchanged; 26.50 seconds.
- Exports: four quantity/coverage reports, 12 horizon rows and 84 calibration-bin rows; strict JSON serialization succeeded.
- Both generated preview images were visually inspected.

The full-suite log and JUnit records are [the test log](cumulative_evaluation_tests_20261011.log) and [JUnit XML](cumulative_evaluation_tests_20261011.xml).

## Evaluation protocol

New-burn scoring uses cells known to be unburned at the cutoff and known at the endpoint; initial burns and unavailable references are excluded. Total-burned scoring uses known endpoint occupancy, including initial burns. It does not require a known cutoff reference. Known cumulative 1-to-0 transitions are rejected.

The simulation's unavailable-state initialization does not supply reference labels. There is no cutoff-neighbor-contact restriction. Physical and time padding, prediction coverage, reference masks, caller selection and positive weights determine the cohort. `coverage="shared"` intersects covered eligible entries over only the explicitly selected durations.

Distances are weight-normalized averages of per-cell Bernoulli distances on binary support `{0,1}` with unit ground distance. They are not geographic transport or joint-map distances. Exact unsupported outcomes preserve infinite NLL, KL and Bhattacharyya distance as the JSON string `"infinity"`; floored scores are separate. Thresholds are caller supplied and never tuned here. Individual-cell Monte Carlo confidence bounds are not confidence intervals for evaluation metrics.

## FishCreek demonstration

The demonstration uses cutoff `2024-08-23T00:00:00Z`, durations 1, 3 and 6 hours, 1,024 trajectories, seed 0, trajectory blocks of 32 and repeated current environmental conditions. It retains the original 103 by 73 rectangle and unknown exterior boundary policy. All 19 selected environmental channels are valid throughout that rectangle. Missing cutoff burned states are initialized as unburned for simulation only.

For new-burn evaluation with per-horizon coverage:

| Duration (h) | Evaluated cells | Observed new burns | Brier | Exact NLL / KL |
| --- | --- | --- | --- | --- |
| 1 | 2451 | 2 | 0.000793080 | 0.003518012 |
| 3 | 2451 | 8 | 0.002794200 | 0.010921011 |
| 6 | 2166 | 16 | 0.005323844 | 0.018445814 |

Shared new-burn coverage contains 2,166 entries at all three durations. Total-burned per-horizon coverage contains 2,642, 2,642 and 2,357 entries, respectively; shared total-burned coverage contains 2,357 entries throughout. Total-burned scores include 191 initial burns whose probability remains one, so their target and cohort differ from those of new spread.

These results verify the scoring workflow on one retrospective example. They do not establish aggregate multi-event forecast skill or calibrated probabilities.

The [executed notebook](../demonstration/cumulative_evaluation/20261011/probability.executed.ipynb), [JSON reports](../demonstration/cumulative_evaluation/20261011/cumulative_evaluation.json), [evaluation CSV](../demonstration/cumulative_evaluation/20261011/cumulative_evaluation.csv), [calibration CSV](../demonstration/cumulative_evaluation/20261011/calibration_bins.csv) and [notebook validation](../demonstration/cumulative_evaluation/20261011/validation.json) are saved separately from prior demonstration artifacts. The [machine-readable validation record](cumulative_evaluation_validation_20261011.json) includes current source hashes.
