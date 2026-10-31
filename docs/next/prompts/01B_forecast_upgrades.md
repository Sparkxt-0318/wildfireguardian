# Claude Code prompt: Track 1B, forecast upgrades (perimeter-trained, differentiable, physically structured)

Copy everything below the line into Claude Code, started in the repository root on a fresh branch `track/1b-forecast-v2` (or in a worktree created by the orchestrator). Read `docs/NEXT_INTERFACES.md` first if it exists; the ownership excerpt at the end of this prompt is authoritative otherwise. This track does not touch routing and does not conflict with tracks 1A or 1C as long as the ownership rules are respected.

---

You are working in the WildfireGuardian repository (Main branch, late October 2026). Before writing code, read: `forecast/GITHUB_SNAPSHOT.md`, `forecast/README.md`, `forecast/documents/api.md`, `forecast/wildfire/models.py` (especially `new_burn_probability`, `EnvironmentConditionedConvolution`, `_PatchGenerator`, `MixedNonnegativeKernel`, `BayesianBurnModel`), `forecast/wildfire/rollout.py` (`simulate`, read-only for you), `forecast/wildfire/train.py` (`train`, `parser`, `fit_global_rate`), `forecast/wildfire/data.py` (`WildfireSequenceDataset`, `load_data`), `forecast/wildfire/cohort.py`, `forecast/wildfire/evaluate.py`, `forecast/wildfire/observed_data.py`, `forecast/wildfire/observed_evaluation.py`, `forecast/wildfire/observed_combined.py`, `forecast/wildfire/heat.py` (`FlameResidenceTime.from_fbfm40`), and `research/forecast/FORECAST_EVIDENCE_HANDOFF.md` plus its `ABLATION_RESULTS.md`. Write your reading notes to `research/forecast-v2/PLAN.md` before coding.

## What the evidence already says (so you do not repeat it)

- The selected checkpoint c651 (four-branch mixed nonnegative kernel, 3/5/7/9) reached Brier 0.008402 and AP 0.1461 on 25 Wapiti NIROPS intervals (275,961 cell-interval entries, 2,525 new burns), an 8.17% Brier improvement over no-new-burn persistence. 93.9% of entries sit in the lowest reliability bin where the mapped new-burn frequency (0.364%) is about 28 times the mean prediction (0.0131%); 617 of 2,525 positives received exactly zero empirical probability from 1,024 trajectories. The choice to report that model followed held-out diagnostic inspection, so the Wapiti result is not blind.
- The frozen ablation (17 variants x 3 seeds) found that a single 9x9 kernel is not worse than the four-scale mixture (Korean Brier 0.1296 versus 0.1387, pooled 0.0328 versus 0.0343, paired interval including zero) at 50.6% fewer parameters. Architecture is not where the gains are.
- Training labels are variance-weighted-kriging reconstructions of arrival time from satellite detections (Choi et al. 2026, Zenodo 10.5281/zenodo.21788344), which are smooth by construction; the Zenodo archive also contains kriging standard-deviation rasters that are currently unused.
- `rollout.simulate` already accepts `environmental_forecast` sequences; repeating cutoff weather is a data choice, not a code limitation.
- `FlameResidenceTime.from_fbfm40` and `EcologicalFuelMaps.from_fccs_rasters` exist; a per-fuel residence time is available in code.

Your job is to make the forecast trainable on real perimeters, differentiable over multi-hour intervals, structurally sensible (burnout, wind frame), and evaluated against baselines a reviewer would demand, with a pre-registered blind protocol for 2026 fires. You never replace checkpoint c651 as the integration default and never edit `forecast/wildfire/rollout.py`.

## Ownership (files you may create or modify)

`forecast/wildfire/meanfield.py`, `forecast/wildfire/survival.py`, `forecast/wildfire/canonical.py`, `forecast/wildfire/burnout.py`, `forecast/wildfire/baselines.py`; additive classes in `forecast/wildfire/models.py` (do not change existing class behaviour or signatures); additive CLI options in `forecast/wildfire/train.py` and `forecast/wildfire/evaluate.py` (defaults must reproduce current behaviour); new tests under `forecast/tests/`; a new run directory `forecast/runs/<YYYYMMDD>_perimeter_trained/`; `forecast/documents/preregistration_blind_test.md`; `research/forecast-v2/**`. Nothing else. If you need the training rasters, ask the user for `--data-root` (it must contain `events.json` and the aligned event inputs; the repository holds metadata only), and for the NIROPS archive use `forecast/wildfire/observed_data.py` (Mendeley 95rj5d379g v1, SHA-256 recorded there). Do not download anything else without recording its hash and licence in `research/forecast-v2/DATA_PROVENANCE.md`.

## Deliverable 1: differentiable mean-field propagation (`meanfield.py`)

Implement `propagate_mean_field(model, p0, environment_sequence, step_durations, ...)` that evolves a continuous occupancy field p_t in [0, 1] instead of binary samples:

p_{t+dt} = p_t + (1 - p_t) * (1 - exp(-dt * lambda_t)), with lambda_t computed by the same environment-conditioned kernels as `new_burn_probability` but applied to p_t (expected sources) rather than a binary map. Unknown cells stay unknown (propagate a validity mask exactly as `new_burn_probability` does; unknown is never zero). Use the model's existing kernel generation path so that at dt -> 0 and binary p the mean-field step equals the Monte Carlo transition's expectation. This gives a deterministic, differentiable multi-hour forecast in one forward pass per hour.

Quantify the approximation: on 12 saved cutoffs (6 Korean, 6 US) compare mean-field p_T with the Monte Carlo mean over 1,024 trajectories at T = 1, 3, 6, 12, 24 h (use `model.predict_cumulative`, read-only). Report RMSE between the two fields, Brier of each against NIROPS where available, and runtime. Expect mean-field to over-predict where spread is correlated; document where it does and does not matter.

## Deliverable 2: interval-censored survival training on perimeters (`survival.py`, additive options in `train.py`)

Perimeter data tells you that a cell ignited somewhere in (t1, t2], not when. The hazard formulation already gives the survival probability over an interval, so train directly on perimeter-to-perimeter transitions:

- Build the training set from NIROPS progression (the same archive used for evaluation): for each fire and each consecutive survey pair, the initial mapped extent at t1, the environment sequence (cutoff repeat if no forecast weather is available; forecast weather when it is, flagged per sample), and the endpoint label at t2 on initially unburned cells. Split by fire and by year: fit on 2020 to 2023 fires, hold out all 2024 fires (including Wapiti) and all Korean 2025 fires. Record the split in `research/forecast-v2/SPLIT.json` before fitting and never change it afterwards.
- Loss: the endpoint Brier score (and clipped NLL as a diagnostic) of mean-field p_{t2} against the mapped endpoint, which is exactly the interval-censored likelihood under the hazard model when evaluated through the survival product. Keep the inverse-inclusion sampling weights where you subsample negatives; keep the categorical (biome) emphasis option as in `train.py`.
- Also support mixed training: kriged hourly labels (existing pipeline) with per-sample weights derived from the kriging standard-deviation rasters (down-weight labels with large SD, or treat them as interval labels tau +/- 2 SD). Report both regimes.
- Keep the model family small: the single 9x9 generator the ablation favoured, plus the structural additions below. Do not re-run the full 17-variant sweep.

## Deliverable 3: structural changes (`canonical.py`, `burnout.py`, additive classes in `models.py`)

1. Wind-frame equivariance. First implement exact D4 (rotations by 90 degrees and flips) augmentation of environment patches and labels, which is free on the grid; then implement wind-aligned canonicalization: rotate the environmental patch so that the wind vector points along +x (bilinear resampling), generate the kernel, rotate the kernel back. Ablate: none, D4, D4 + canonicalization. With about 25 training fires, this is the cheapest sample-efficiency gain available; measure it.
2. Physics prior. Parameterize the kernel as an elliptical template whose length-to-breadth ratio follows a documented wind-speed relation (Anderson 1983 ellipse) multiplied by a learned nonnegative residual, versus the free kernel. Ablate.
3. Burnout. Add a flaming-window state: a cell contributes as a source only while its age since ignition is below the residence time t_r (from `FlameResidenceTime.from_fbfm40` where fuel data exist, otherwise a scalar), plus a learned smouldering multiplier for older cells. In mean-field, p_burning(t) = p_ign(t) - p_ign(t - t_r). Ablate against the absorbing-source model. This removes the "every burned cell is a source forever" assumption and makes the heat timing consistent with track 1A.
4. Long-range (spotting) branch: a wind-aligned, sparse, low-rank kernel with support up to 15 cells and a learned amplitude, emitted only by cells in the flaming window. Ablate; report whether it moves the lowest reliability bin.

## Deliverable 4: baselines and metrics (`baselines.py`, additive options in `evaluate.py`)

Add and evaluate on exactly the same cells and intervals:

- Persistence (no new burn) and dilation baselines: dilate the perimeter by one cell per k hours for k in {1, 2, 4, 8} (and the best k chosen on training fires only).
- Logistic regression on hand features: distance to nearest burned cell, wind alignment of that direction, slope along it, fuel/biome class, hours in interval.
- The existing checkpoint c651 (recursive Monte Carlo) and the FARSITE scenario rows already in `research/forecast/`.
- Metrics: Brier, BSS relative to persistence, AP, ROC AUC, fixed-bin ECE, clipped NLL, plus per-fire values and a paired bootstrap over fires (not cells) for confidence intervals. Add calibration curves per model on one figure.

A model is only reported as better if it beats the best dilation baseline and persistence on the held-out fires with a paired-by-fire interval that excludes zero, and its calibration curve is not worse in the lowest bin.

## Deliverable 5: pre-registration (`forecast/documents/preregistration_blind_test.md`)

Write a frozen protocol for a blind test on fires that occurred in 2026 (perimeters will become available in the NIROPS archive's next release and Korean 2026 reconstructions): the exact model identities (checkpoint hashes) to be tested, the baselines, the metrics, the per-fire reporting, the pre-specified primary comparison (held-out Brier versus best dilation baseline, paired by fire) and the stopping rule (no model selection after seeing 2026 data). The user will register this document on OSF; your job is to make it precise enough that nothing is left to decide later. Include the command that produces every number.

## Tests (`forecast/tests/`)

- Mean-field step equals the expectation of the Monte Carlo transition for binary p (compare against `new_burn_probability` directly, 1e-9).
- Mean-field with validity masks: an unknown source never contributes, and a target depending on an unknown source is unknown.
- Survival loss on a two-cell toy fire with known hazard recovers the analytic interval probability.
- D4 augmentation: the model's prediction for a rotated patch is the rotated prediction when the kernel is generated equivariantly (test on the constant generator).
- Burnout: a cell older than t_r contributes only the smouldering multiplier.
- Baselines: dilation by one cell per hour on a planar front moving one cell per hour has Brier 0.

## Evidence (`research/forecast-v2/`)

`README.md` with headline numbers first (held-out 2024 fires: Brier, AP, BSS versus persistence and versus best dilation, with paired-by-fire 95% intervals; lowest-bin reliability before and after), then ablation tables (D4, canonicalization, ellipse prior, burnout, spotting), the mean-field versus Monte Carlo comparison, per-fire tables, runtime and parameter counts, commands, seeds, hashes, host. Figures: `fig01_reliability_all_models`, `fig02_per_fire_brier_paired`, `fig03_ablation_forest_plot`, `fig04_meanfield_vs_mc_rmse_by_horizon`, `fig05_example_forecast_vs_perimeter` (initial extent, forecast, later extent, same window and colour scale). Write a "Scope and limits" section: labels are mapped extent, not flames; no complete survey-coverage mask; one archive; weather is repeated unless flagged; a positive result on 2024 fires is still not the blind 2026 test.

Commit in small steps. Open a pull request "Track 1B: perimeter-trained differentiable forecast with structural ablations and a pre-registered blind protocol". Do not merge. Do not promote any new checkpoint to the integration default; the routing kit continues to use c651 until the orchestrator decides otherwise.

## What not to do

- Do not touch `rollout.py`, `export.py`, anything under `integration/`, or the c651 checkpoint.
- Do not evaluate on Wapiti while developing; it is in the held-out year. Use 2020 to 2023 validation folds for all development decisions and say so in the README.
- Do not report cell-level confidence intervals as if cells were independent; pair by fire.
- No em dashes anywhere.
