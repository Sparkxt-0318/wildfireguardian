# Zero-padded rectangular prediction validation — 2026-10-12

Unavailable burned-state values are initialized as unburned zero only within real input support. Ordinary, fixed cumulative, and recursive public prediction now share `missing_burned_area="unburned"` and `boundary="zero"` defaults. Exterior model context is zero padded while output dimensions and coordinates retain the supplied rectangle. Original input/reference masks are unchanged.

The configured checkpoint is `runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt`, a nonnegative 3/5/7/9 mixed kernel with 19 channels. For FishCreek, all **7,519 cells** of the **103 × 73** rectangle are valid for the one-hour map, fixed horizons 0.5/1/3.5 hours, and recursive horizons 1/3/6/12 hours. There are **0 unavailable probability cells** in these complete-environment matrices. The initialization metadata records **4,877 assumed unburned cutoff cells**.

The notebook's 29 existing code cells executed successfully in 590.87 seconds using **1,024 trajectories**, seed 0 and trajectory batch size 32. The concurrently added read-only FARSITE report preview was checked separately afterward; the refreshed executed copy contains all 30 current code cells. All existing executed code sources matched the latest source exactly. Prose was refreshed from the latest source, and the editable source retains empty outputs.

The full regression suite passed **2251 tests**, with no failures, errors or skips. Saved array coverage and all 20 artifact hashes were verified. The selected-time probability map, combined event/probability map, and cumulative-horizon map passed visual inspection. The unavailable legend now appears only when the displayed matrix actually contains unavailable values.

Genuine interior environmental gaps and physical/time padding retain missingness. Full edge coverage applies to the original unpadded event rectangle; synthetic padding within differently sized collated items remains excluded context. Heat and active-flame inference preserve their conservative assumptions separately. This is functional coverage validation, not a claim of forecast accuracy.

- [Editable notebook](../api_tutorial.ipynb)
- [Executed notebook](../demonstration/zero_padded_prediction/20261012/api_tutorial.executed.ipynb)
- [Run manifest](../demonstration/api_tutorial/runs/run-gi0pm58i/manifest.json)
- [Machine-readable validation](zero_padded_prediction_validation_20261012.json)
- [Regression log](zero_padded_prediction_tests_20261012.log)
