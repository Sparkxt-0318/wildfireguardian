# Random-forest cumulative evaluation and plot verification

The forest API, mixed-model evaluation runner, probability-distance report, and comparison plots passed verification on 2026-10-11. The full regression suite passed **2,104 tests** with no failures or errors. The test log and JUnit record are `cumulative_forest_plots_final_tests_20261011.log` and `.xml` in this directory. The machine-readable validation record is `cumulative_forest_plots_validation_20261011.json`.

## Implemented behavior

Saved `PatchRandomForest` joblib files use their fitted mean tree probability at each one-hour transition of the existing binary, synchronous, absorbing rollout. Newly ignited cells become sources during the next hour. Forests retain their own embedded channel normalization and run on CPU. No tree is sampled as a Bayesian component, and no estimator or preprocessing is refitted. Ordinary forest prediction and fixed mode accept only the fitted one-hour interval; longer forest horizons use recursion. The ordinary diagnostic `-log(1-q)` is an equivalent one-hour quantity, not a fitted continuous-time hazard. Recursive rates remain NaN with false rate-validity masks.

The original rectangle is retained with unburned exterior sources and zero exterior environmental context. Missing initial burned observations inside actual support are initialized as unburned for simulation. Missing environmental inputs remain unavailable. Original observation masks remain authoritative during evaluation, so unknown reference cells are excluded rather than labeled unburned.

Historical forests omit event partitions but save the original training-cache digest. Their partition evidence is authenticated against companion tensor contracts with the identical saved digest and ordered channel schema. The runner checks all canonical witnesses in the owning experiment, including unselected witnesses, and rejects conflicting evidence. It records witness paths and hashes. Forest normalization is never copied from a companion. Missing evidence prevents a default test-partition evaluation; explicitly retrospective `--split all` remains available.

## Actual six-hour run

The report in `demonstration/cumulative_models/20261011_forests_plots/report.md` completed for **573 saved models**: 561 tensor checkpoints and all 12 forests. It uses KFS_06, cutoff **2025-03-24T03:00:00Z**, exact endpoint **2025-03-24T09:00:00Z**, eight trajectories per model, block size eight, base seed zero, threshold 0.5, repeated cutoff environment, and CPU inference. Observed elapsed time was approximately 65.3 seconds while other validation ran concurrently.

This is a bounded functional and visual diagnostic on one cutoff, not an exhaustive forecast-skill comparison. The normal evaluation command uses 1,024 trajectories and the requested six-hour horizon by default.

Every model returned the complete **14 × 14 rectangle**, with all 196 prediction cells available. The saved probability tensor has shape **(573, 1, 1, 14, 14)** and coordinates have shape **(14, 14, 2)**. On identical original reference masks, each shared new-burn cohort has **51 entries and four positive outcomes**; total occupancy has **78 entries and 31 positives**. All 27 known initial burns have exact new-burn probability zero, total burned probability one, Monte Carlo standard error zero, and new-burn Wilson bounds [0, 0]. The standard-error formula, probability bounds, Wilson containment, full rectangle dimensions, original reference eligibility, all checkpoint hashes, source hashes, and forest partition-witness hashes were checked against the saved arrays and records.

## Distances and plots

The written report contains four full probability-distance tables, one for each shared/native cohort and new-burn/occupancy quantity. Each table includes all 573 models and nine fields:

- Exact KL divergence and separately probability-floored KL divergence.
- Total variation, Hellinger, Jensen–Shannon divergence, Jensen–Shannon distance, Bhattacharyya, Wasserstein-1, and Wasserstein-2.

These compare each predicted Bernoulli distribution with the observed binary outcome. KL is directed from observation to prediction. Natural logarithms give nats. Square roots are taken per cell before pooling. TV and Wasserstein-1 coincide on binary support with unit ground distance. These are not distances between complete spatial maps or geographic transport scores. Infinite exact KL/NLL and Bhattacharyya values remain infinite; undefined scores remain explicitly undefined. Floored results are labeled separately.

The run generated **14 figures**, each in PNG and SVG, for 28 image files: metrics, architecture comparisons, probability distances, reliability, per-event Brier, coverage, and pooled ROC/precision-recall curves for both probability quantities. Every model appears in the metric, architecture, and coverage overviews. The detail displays use at most 20 representatives; reliability and curves use at most eight. Both forest and Bayesian architecture representatives are present. Display selection changes presentation only. Scores use every eligible entry, and pooled curves use complete stored entries.

The plot manifest records every included/omitted detail identifier and all image hashes. `plots/model_index.csv` maps 573 distinct short identifiers to exact model records. All PNGs were visually inspected across the three reviewers. Labels, legends, infinity markers, quantity distinctions, and distance rows remain visible at the actual 573-model scale. All 28 image hashes and all report image/export links match existing files.

The saved best-model registries also passed a plan-only run: **57 models**, including four forests, and **1,860 complete six-hour cases**. This plan did not simulate or assign scores to those cases.

## Tutorial

The API tutorial contains an optional forest example and the mixed-model report command. The editable source has 58 cells, including 29 code cells, all with empty outputs and execution counts; every code cell compiles. The newly added forest example was validated separately with KFS_06 at 2025-03-22T05:00:00Z, six hours, and eight trajectories. Its two known initial burns have exact new-burn probability zero and total probability one, and all 196 rectangle cells remain available. Both original-mask evaluations expose every distance field, and JSON/CSV/NPZ plus a two-map PNG export succeeded. The artifacts are retained in `demonstration/cumulative_models/20261011_forests_plots/tutorial_forest/`. Historical executed tutorial copies remain preserved; earlier tutorial cells were not rerun. The updated notebook source hash is `0677ef9a844ebcf5d8e7d5f4e61520df8626b3d052b29f4419f754de170f5ea0`. Its optional controls expose the duration and sample count explicitly.
