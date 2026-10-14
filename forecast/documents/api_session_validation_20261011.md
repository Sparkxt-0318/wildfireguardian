# Integrated cumulative API and tutorial verification — 2026-10-11

The public cumulative API and API tutorial incorporate recursive hourly spread,
explicit-duration evaluation, missing initial burned-state initialization,
full-rectangle environmental data, and unburned exterior padding.

## API behavior

- Recursive cumulative prediction defaults to `boundary="zero"`: burned-state
  sources outside the rectangle are unburned, with the existing environmental
  padding in model-input space. The original rectangle and coordinates remain
  unchanged. Complete interior inputs retain valid edge coverage at every horizon.
- Missing initial burned observations are initialized as unburned only inside
  physical/time support. Missing environmental inputs inside the rectangle and
  physical/time padding remain unavailable.
- Explicit `boundary="unknown"` remains supported. Ordinary `predict()` and
  `method="fixed"` retain their previous unknown-boundary defaults. Fixed mode
  retains fractional horizons and rate diagnostics.
- `evaluate_cumulative` is exported from both `wildfire` and `wildfire.api`;
  `CumulativePrediction.evaluate` provides the corresponding result method.
  Evaluation requires explicit `hours`, exact endpoints and original reference
  masks, distinguishing new burns from total burned occupancy.
- Forecast support is applied before named-channel projection, so padded values
  do not cause false one-hot errors when channels are reordered or selected from
  a superset. Invalid known interior categorical groups are still rejected.

## Verification results

The [complete regression suite](api_session_zero_boundary_tests_20261011.log)
passed **2,027 tests** in **72.01 seconds**, with no failures,
errors or skips. It recorded 272 warnings. The focused API,
rollout, environment rectangle and cumulative suite passed 159 tests in 4.33 seconds.

The [executed tutorial](../demonstration/api_session/20261011_zero_boundary/api_tutorial.executed.ipynb) ran all
**28 code cells** in **54.78 seconds**
using the existing data and checkpoint. No data preparation or training ran.
The [editable source](../api_tutorial.ipynb) remained unchanged during execution
and retains empty outputs. All nine plot previews passed visual inspection;
all 20 saved artifact hashes matched the manifest.

| Hours after cutoff | Valid cumulative probability cells | Spatial shape |
| --- | --- | --- |
| 1 | 7,519 | 103 × 73 |
| 3 | 7,519 | 103 × 73 |
| 6 | 7,519 | 103 × 73 |
| 12 | 7,519 | 103 × 73 |

All 19 environmental channels are known across all 7,519 pixels, including
4,877 cells outside the original arrival-observation mask. Those 4,877 missing
initial burned states are assumed unburned for simulation; their reference masks
remain unchanged for evaluation. The 252 initially burned cells have exact
new-burn probability zero, total burned probability one, and zero Monte Carlo
standard error and Wilson bounds for new-burn probability.

Evaluation explicitly selected 1, 3 and 6 hours. The four protocols (new burn or
total burned occupancy, each with per-horizon or shared coverage) produced
12 metric rows and 84 calibration-bin rows. New-burn evaluation uses 2,390 known
initially unburned reference cells, and total occupancy uses 2,642 known endpoint
reference cells at each selected horizon. All evaluation reports retain the
original observation masks and exact cutoff-plus-duration endpoints.

The optional forecast example remains disabled in the default notebook run;
forecast behavior is covered by API integration tests. The default tutorial
repeats current environmental conditions at each interval. Its separate heat
workflow continues to use the original analytic next-hour probability.

## Saved results

- [Execution checks](api_session_notebook_zero_boundary_20261011.json)
- [Complete verification record](api_session_validation_20261011.json)
- [Run manifest](../demonstration/api_tutorial/runs/run-vk49kexj/manifest.json)
- [Cumulative arrays](../demonstration/api_tutorial/runs/run-vk49kexj/cumulative_probability.npz)
- [Fixed-mode arrays](../demonstration/api_tutorial/runs/run-vk49kexj/fixed_cumulative_probability.npz)
- [Evaluation JSON](../demonstration/api_tutorial/runs/run-vk49kexj/cumulative_evaluation.json)
- [Evaluation CSV](../demonstration/api_tutorial/runs/run-vk49kexj/cumulative_evaluation.csv)
- [Calibration CSV](../demonstration/api_tutorial/runs/run-vk49kexj/cumulative_calibration_bins.csv)

Earlier tutorial executions are preserved in separate directories. These checks
establish functional behavior for the recorded implementation and example;
they do not establish independent forecasting skill. Pointwise Wilson intervals
describe Monte Carlo error, not confidence intervals for evaluation metrics.
