# Pre-registered blind test of hourly wildfire spread forecasts on 2026 fires

Status: FROZEN PROTOCOL (track 1B). Version 1, written 2026-10-29, before any 2026 perimeter or reconstruction was read by this project. The document is to be registered on OSF by the project owner; the registered copy and its SHA-256 become the reference, and nothing below may be changed after registration. Any deviation that turns out to be unavoidable is reported as a deviation, next to the pre-registered result, never in place of it.

## 1. Question

On fires that started in calendar year 2026, does a model fitted by track 1B forecast the mapped growth of a fire between two consecutive perimeter surveys better than the best simple dilation baseline, judged by the Brier score and paired by fire?

## 2. Models under test (identities are fixed by file hash)

| Role | Identity | File | SHA-256 |
|---|---|---|---|
| Integration default (comparator) | c651, `MixedNonnegativeKernel` 3/5/7/9, recursive Monte Carlo, 1,024 trajectories | `forecast/runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt` | `c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843` |
| Primary candidate | the track 1B final model named `primary_candidate` in `research/forecast-v2/RESULTS.json`, seed and variant as recorded there, run with the mean field (`wildfire.survival.sample_forecast`) | `forecast/runs/20261029_perimeter_trained/<variant>_seed<seed>/checkpoint.pt` | recorded in `research/forecast-v2/RESULTS.json` under `primary_candidate.checkpoint_sha256` at the commit that registers this document |
| Secondary candidates | every other final checkpoint listed in `research/forecast-v2/RESULTS.json` under `final_models` | same run directory | recorded there |

The candidate checkpoint hashes are copied into the registered OSF document verbatim at registration. A model whose file does not match its registered hash is not scored.

Source code: the git commit registered with this document (`git rev-parse HEAD` at registration) of the WildfireGuardian repository. Inference uses that commit's `forecast/wildfire/` package with the pinned environment of `forecast/pyproject.toml` (Python 3.12, NumPy 1.26.4, PyTorch 2.5.1).

## 3. Data

- Perimeters: dated NIROPS (or successor) aerial-infrared survey perimeters of US fires that started in 2026, from the next release of the archive used here (Magstadt et al., Mendeley Data 10.17632/95rj5d379g). The archive file, its SHA-256 and its licence are recorded before scoring. Korean 2026 fires enter only if a perimeter time series (not only a final perimeter) is published; otherwise Korean 2026 reconstructions (Zenodo 10.5281/zenodo.21788344 successor) are scored as a separately reported secondary analysis with kriged labels.
- Fire inclusion: every 2026 fire in that release with at least 10 distinct survey times and a final mapped area of at least 2,000 ha. Fires are included or excluded on these two counts only, before any forecast is made.
- Grid and covariates: each fire gets a 375 m grid built by the repository's environment pipeline (`forecast/wildfire/environment.py`, the same sources as the training inputs: ECMWF IFS 9 km hourly weather through the Open-Meteo archive, Copernicus GLO-30 slope, Copernicus Global Land Cover tree cover, RESOLVE 2017 biomes), covering the bounding box of the final mapped perimeter plus 10 cells on every side. A fire whose inputs cannot be built completely is reported as not scored, with the reason.
- Intervals: consecutive distinct survey times t1 < t2 with 0 < t2 - t1 <= 48 h (the rule in `research/forecast-v2/SPLIT.json`). State at t is the union of that fire's polygons with time <= t, rasterized at cell centres. Covariates are taken at the last whole hour at or before t1 and repeated over the interval (no future weather).
- Scored cells: every cell of the rectangle outside the initial union at t1, with complete covariates, valid for every scored model. Outside the union at t2 counts as a negative mapped-extent outcome. All models are scored on exactly this common set.

## 4. Baselines (fixed now)

- Persistence: probability zero of new burning.
- Dilation: the initial union grown by one cell (8-neighbourhood) per k hours, floor(T/k) cells for an interval of T hours, as a 0/1 forecast, for k in {1, 2, 4, 8}. The **best dilation baseline** is the k recorded in `forecast/runs/20261029_perimeter_trained/baselines/dilation_choice.json` (chosen on 2020 to 2022 fit fires only). It is not re-chosen on 2026 data.
- Logistic regression on hand features, the fitted file `forecast/runs/20261029_perimeter_trained/baselines/logistic.pkl` (hash recorded in `RESULTS.json`).

## 5. Metrics

On equally weighted cell-interval entries: Brier score; Brier skill score against persistence; average precision; ROC AUC; expected calibration error over ten equal-width bins; negative log likelihood with probabilities clipped to [1e-7, 1 - 1e-7]; the count of positive entries forecast with probability exactly zero; the calibration table, in particular the lowest bin [0, 0.1). Every metric is reported pooled and per fire.

## 6. Primary comparison and decision rule

- Primary endpoint: pooled Brier score of the primary candidate minus pooled Brier score of the best dilation baseline, over all scored 2026 entries.
- Uncertainty: paired bootstrap over fires (whole fires resampled with replacement, 10,000 draws, seed 20261029, percentile 95% interval), as implemented in `wildfire.baselines.paired_fire_bootstrap`. Cells are never resampled as if independent.
- The primary candidate is reported as **better than the best dilation baseline** only if (a) the point difference is negative, (b) the 95% interval lies entirely below zero, (c) the same holds against persistence, and (d) in the lowest calibration bin its absolute difference between mean forecast and observed frequency is not larger than that of c651. Otherwise the result is reported as "not shown to be better", with the numbers.
- Secondary comparisons, reported without a decision claim: every candidate and c651 against persistence, against the best dilation baseline and against each other, with the same bootstrap; per-fire Brier differences and the number of fires favouring each model.
- With fewer than 5 scored fires the interval is still reported, but no claim of superiority is made in either direction.

## 7. Stopping rule and what may not change

- No model selection, refitting, recalibration, threshold choice, hyperparameter change or interval-rule change after any 2026 perimeter has been read. The models, code commit and baselines above are the only ones scored.
- Each fire is scored once. A failed run is repaired only for a software fault that does not depend on the 2026 outcomes, and the repair is disclosed with the failed output kept.
- Scoring starts only when the release is complete for all included fires, or one year after this registration, whichever comes first; fires released later are reported separately.

## 8. Commands that produce every number

From the repository root at the registered commit, with the pinned forecast environment and `OMP_NUM_THREADS=2`:

```sh
# 1. perimeter states on the 2026 grids
python research/forecast-v2/scripts/prepare_perimeters.py --shapefile <2026 NIROPS .shp> --zenodo <zenodo results dir> --out <work>/perimeters_2026
# 2. covariates for the 2026 fires (environment pipeline, data root layout of wildfire.data)
python -m wildfire environment ...   # as documented in forecast/README.md for new events
# 3. scoring: all models and baselines on the common cells
python research/forecast-v2/scripts/pipeline.py heldout --data-root <2026 data root> --perimeters <work>/perimeters_2026 \
    --work <work> --run forecast/runs/20261029_perimeter_trained --n-samples 1024 --seed 0 --events <2026 fire ids>
# 4. pooled, per-fire and fire-paired scores
python -m wildfire evaluate --perimeter-scores --run-dir forecast/runs/20261029_perimeter_trained --output-dir <work>/scores_2026
```

The held-out scorer writes one entry file per fire; step 4 produces `perimeter_scores.json`, which contains every metric and comparison of sections 5 and 6. Before step 3 the `heldout/` output folder is moved aside so that 2024 entries and 2026 entries are never pooled.

## 9. Known limits stated in advance

Labels are mapped extent, not active flame or ignition time; the archive has no survey coverage mask; publisher timestamps may be estimated; weather is repeated from the cutoff; one archive and one region. A positive result shows better agreement with mapped perimeter growth on these fires under this protocol. It does not show physical accuracy, operational suitability or skill on other regions.
