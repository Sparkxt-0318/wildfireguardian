# Track 1B plan and reading notes

Written before any model code or fit (2026-10-29). Branch `track/1b-forecast-v2`, worktree created from `next/orchestrator`.

## What I read and what matters for this track

- `forecast/GITHUB_SNAPSHOT.md`: c651 (`runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt`, SHA-256 `c651f672...bd1843`) is the integration default. Prediction defaults are zero boundary padding and unburned missing state. Large inputs are not in git.
- `forecast/wildfire/models.py`:
  - `new_burn_probability(burned, kernel_rates, dt, masks, boundary)`: lambda_i = sum_delta K[i,delta] B[i+delta], q = 1 - exp(-dt lambda). Kernels use the cross-correlation convention: offset (dy, dx) multiplies the source at (row+dy, col+dx). Validity: a target is valid only if it is known, its kernel is finite, and every positive-weight source is known (padding of availability is separate from padding of values). Unknown is never zero.
  - `EnvironmentConditionedConvolution._features` builds the complete-context mask; `_kernels` is softplus(logits) times an off-centre mask. `LearnedNonnegativeKernel` with `_PatchGenerator` ("cnn" reads the full K x K patch with one hidden SiLU layer). `MixedNonnegativeKernel` sums branch kernels embedded in the largest patch with global nonnegative weights before one exponential; `kernel_rates(...)` is available for it, so the mixture has a burned-independent kernel and the mean-field step applies to c651 exactly. `NeuralMixedNonnegativeKernel` has no burned-independent kernel (mean field is undefined for it and must refuse).
  - `TrainedBurnModel` normalizes raw channels, validates one-hot groups and, for the `at_least_one_burned_neighbor` contract (c651), restricts validity to contact or a structural zero with complete sources. `BayesianBurnModel` mixes component probabilities with posterior mass; in the rollout each trajectory draws one component.
- `forecast/wildfire/rollout.py` (read only): synchronous conditionally independent Bernoulli ignitions, absorbing burning, per-trajectory component draw, coverage is a deterministic envelope computed by probing the base state: `mask[k+1] = mask[k] & (observed_burns | probe.rate_valid)`. Seeds come from `SeedSequence([seed, cutoff, block, stream])`. `step_durations` allows an exact fractional final step. The empirical probability counts new burns excluding observed initial burns. I must reproduce this envelope in the mean field so both are scored on identical cells.
- `forecast/wildfire/train.py`: full-batch-free minibatch Brier on cached centre patches, inverse-inclusion weights, categorical (biome) balance factors from `metrics.fit_categorical_balance`, Adam, validation-Brier early stopping. `fit_global_rate` fits one per-neighbour rate. `parser()` defaults: epochs 30, patience 6, batch 1024, hidden 16, lr 1e-3, wd 1e-4, seed 7, threads 4, device cpu. Any option I add must leave these and the saved `configuration` dictionary unchanged when not used.
- `forecast/wildfire/data.py`: `WildfireSequenceDataset` reads `events.json` and `regions/<id>/{weather,terrain,vegetation,biome,...}/*_375m.tif`; one-hot categorical expansion; weather hourly bands must match the event window exactly.
- `forecast/wildfire/cohort.py`: contact cohorts are label-free; unknown never counts as unburned.
- `forecast/wildfire/evaluate.py`: kernel comparison on a common cached cohort; whole-fire cluster bootstrap exists for Brier (`cluster_bootstrap_brier`).
- `forecast/wildfire/observed_data.py`, `observed_catalog_data.py`, `observed_evaluation.py`, `observed_combined.py`: NIROPS v1 archive pinned by SHA-256 `b19fb16c...75615`; survey references are cumulative unions of polygons with time <= t, rasterized at cell centres (`all_touched=False`) on the event grid; outside the union inside the rectangle is a negative mapped-extent outcome (no coverage footprint exists); c651 runs with `boundary="zero"`, `missing_burned_area="unburned"`, cutoff covariates repeated from the last whole hour at or before the survey, hourly steps plus one exact fractional final step.
- `forecast/wildfire/heat.py`: `FlameResidenceTime.from_fbfm40` gives point flame residence from Scott and Burgan fuel codes (Anderson 384/sigma minutes), which is minutes, far below the 1 h step at 375 m. Cell burning duration (`heat_duration.py`) is the relevant time scale for a 375 m source.
- `research/forecast/FORECAST_EVIDENCE_HANDOFF.md` and `ABLATION_RESULTS.md`: single 9x9 not worse than the 3/5/7/9 mixture; environment-independent kernels and global-neighbour baselines are competitive; exact log loss is often infinite; the 25 Wapiti NIROPS intervals give c651 Brier 0.008402 on 275,961 entries, not blind. No FARSITE rows are stored in the repository (only Mac paths), so the FARSITE baseline cannot be rerun here.

## Data situation on this host (decision D4)

- The private `--data-root` with the aligned environmental rasters is absent. The orchestrator asked the human; meanwhile I rebuild the six source channels c651 reads (temperature, wind u/v, slope, tree cover, biome) from the public sources named in `forecast/wildfire/environment.py`, outside git, with `research/forecast-v2/scripts/rebuild_environment.py`. A rebuilt raster is not guaranteed to equal the private one; this is recorded as a deviation.
- Labels: NIROPS v1 perimeters (all 29 Zenodo US fires, 2020 to 2024) and Zenodo 10.5281/zenodo.21788344 arrival and kriging-SD rasters (29 US, 15 Korean). Both CC BY 4.0.

## Work plan, in order

1. `SPLIT.json` committed before any fit: fit and development on US fires 2020 to 2022 (no 2023 US fire is in the archive) plus, for the kriged regime only, Korean 2022 to 2023 fires; development folds are leave-one-year-out over 2020, 2021, 2022; held out: all six 2024 US fires (Goat, Lava, Pioneer, RedRock, FishCreek, Wapiti) and all four Korean 2025 fires.
2. `meanfield.py` (D1) with tests against `new_burn_probability` at 1e-9 and the rollout validity envelope; quantify mean field against Monte Carlo on 12 cutoffs.
3. `survival.py` (D2): perimeter-pair samples, interval-censored endpoint Brier through the mean-field survival product, kriging-SD weighted mixed regime; additive `--objective` option in `train.py` whose default leaves the original code path and saved configuration untouched.
4. `canonical.py`, `burnout.py`, additive classes in `models.py` (D3): exact D4 augmentation (spatial transform plus wind-vector transform), wind-aligned canonicalization, Anderson (1983) ellipse template times a learned nonnegative residual, flaming window with smouldering multiplier, wind-aligned low-rank spotting branch.
5. `baselines.py` (D4): persistence, dilation k in {1, 2, 4, 8}, logistic regression on hand features, metrics (Brier, BSS, AP, AUC, ECE, clipped NLL), per-fire values and a paired bootstrap over fires.
6. `forecast/documents/preregistration_blind_test.md` (D5).
7. Evidence: `research/forecast-v2/README.md`, `RESULTS.json`, per-fire CSV, figures fig01 to fig05.

## Compute limits (decision D3)

4 vCPU shared with two other tracks: at most 2 threads, small models (one 9x9 CNN generator, hidden width 16), seeds and epochs scaled to what finishes here and reported.
