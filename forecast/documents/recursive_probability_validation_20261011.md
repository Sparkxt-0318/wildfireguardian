# Recursive probability validation — 2026-10-11

The implementation passed all 1,929 tests, including 70 recursive cases and 14 result-container cases. No failures, errors or skipped tests remain. The complete probability demonstration passed all six code cells in 21.15 seconds.

## Result behavior

`predict_cumulative` defaults to absorbing binary trajectories with simultaneous hourly updates, 1,024 samples, seed 0 and trajectory blocks of 32. Each Bayesian trajectory retains its sampled component. Results expose first-new-burn probability, total burned probability, Monte Carlo standard error and pointwise nominal 95% Wilson bounds. Recursive aggregate rates are unavailable. Explicit `method="fixed"` retains the former frozen-state calculation and fractional horizons.

The confirmed default `missing_burned_area="unburned"` initializes unavailable initial burned observations as zero within true pixel/time support. Environmental gaps and padding remain unavailable. `missing_burned_area="unknown"` retains the conservative initial-state option. Neither initialization alters supplied arrays or retrospective reference masks.

## Independent probability checks

The directed chain has only its first cell initially burned and hourly edge probabilities of 0.5. With 8,192 trajectories, the last-cell estimates are 0 at hour one, 0.251831 at hour two and 0.501587 at hour three, compared with exact probabilities 0, 0.25 and 0.5. Equal posterior mass on components with hourly probabilities 0.2 and 0.8 produces a two-hour estimate of 0.662842 against the persistent-component exact value 0.66.

## Executed FishCreek example

The cutoff is `2024-08-23T00:00:00Z`. The example initializes 4,877 previously unavailable cutoff-cell entries as unburned. Coverage includes the following cells; the assumed-unburned column is the subset still covered at each horizon.

| Horizon (hours) | Valid cells | Valid initialized-unburned cells | Valid assumed-unburned cells |
| ---: | ---: | ---: | ---: |
| 1 | 6,831 | 6,640 | 4,189 |
| 3 | 5,551 | 5,360 | 2,909 |
| 6 | 3,871 | 3,680 | 1,514 |

The source notebook retains empty execution outputs. The executed copy, previews and detailed notebook validation are in `demonstration/recursive/20261011`.

## Evidence and limits

- Regression log: `documents/recursive_probability_tests_20261011.log`.
- Regression JUnit: `documents/recursive_probability_tests_20261011.xml`.
- Machine-readable validation and source digests: `documents/recursive_probability_validation_20261011.json`.
- Notebook validation: `demonstration/recursive/20261011/validation.json`.

Validation covers CPU functionality and the specified stochastic model. Sampling intervals describe Monte Carlo error; these checks do not establish longer-horizon forecast calibration or skill.
