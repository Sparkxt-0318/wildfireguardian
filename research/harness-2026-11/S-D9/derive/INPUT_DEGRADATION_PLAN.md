# Input-degradation curve: plan (S-D9). NOT RUN

**Status.** This is a plan only, written before any run. It is descriptive, with no decision weight, and is not part of any §6 criterion.
- It starts only after the part-c prerequisites are frozen and rebuilt (orchestrator, 2026-11-12).
- It needs Daniel's rebuilt part-a weather.
- It does not open part b, c or d, or any H-test fire.

## Question
How fast does each forecast degrade when an input is stale or missing in the ways an operational run would actually meet? The fault list follows Iris.

**Training context.** No model is trained with input dropout or missing-input augmentation:
- d4_wind and the D2 arms use dropout 0.0, and their only augmentation is D4;
- c651 has hidden-feature `Dropout2d(0.15)` only;
- the logistic model has no augmentation.

Missing values are zero-filled at forecast time (`forecast/wildfire/survival.py:183-184`).

## Faults and levels (fixed now)
| Fault | Levels | Applies to |
|---|---|---|
| Weather aged | 0 (reference), 6, 12, 24 h: the cutoff weather is taken from `cutoff − age` | all |
| Wind → climatology | wind speed and direction replaced by the fire's part-a climatological mean for that month and region; other weather unchanged | all models with wind inputs |
| Static layer → regional mean | one layer at a time (slope, fuel/cover, elevation-derived), replaced by its regional mean over the fire's rectangle | all |
| Stale fire state | the cutoff state replaced by the previous survey's perimeter; target and horizon unchanged | all |
| Blanked detections | detections removed for the detection-based Korean stratum only | detection-based stratum only |

There is one fault at a time and no combinations.

## Models and populations
Every row states which population it comes from:
- **Archive-trained models** (c651 and any frozen archive model): run directly on part a, since they never saw part a.
- **Rebuilt refits** (d4_wind_rebuilt, logistic_rebuilt, d2_*_rebuilt): **only** through the part-a cross-validation folds already defined for Elena's part-a CV, so each fold's degraded inputs are scored on held-out fires. These are never evaluated on fires they were fit on.

## Scoring (unchanged scorer)
- The scorer is `sd9bench.score()` at its frozen SHA, with the same masks and new-burn population as the unperturbed score.
- Reported per model × fault × level:
  - pooled Brier;
  - AP;
  - lowest-bin calibration (observed vs mean predicted in [0, 0.01));
  - the change from level 0 in each.

## "Steep" (defined before running)
A fault level is **steep** for a model if the change in pooled Brier from the unperturbed score is larger than the half-width of the unperturbed score's 95% whole-fire bootstrap interval:
- B = 2,000 fire resamples;
- the seed is fixed at the run, recorded and never chosen after the fact.

AP and calibration changes are reported alongside but do not define "steep". The label is descriptive and drives no decision.

## Outputs
- `derive/INPUT_DEGRADATION.json` and `.md`: per row, the model, population (archive / CV fold), fault, level, n, Brier, AP, lowest-bin observed and mean, delta, and the steep flag.
- Input hashes and the code SHA.
- No raster data is committed.

## Not decided here
- The exact climatology window for wind.
- Which static layers exist per model; this depends on the rebuilt channel list.

Both are fixed in a revision of this file, committed before the run.
