# Final report packaging checklist, source-only preparation

Prepared 2026-10-31. This checklist reads frozen source and documentary requirements only. No assessment receipt/output, NPZ, probability field, model binary or quality-result file was opened; no numerical/reporting command was run. The parent reports both cohorts are running against the published freeze. Do not execute the commands below until both processes have closed and their complete case/assessment receipts are immutable. This document does not verify their results.

Graph context supplied by the parent: Verify Tier2, project `wfg-next-1b-20261030`, generation `2026-10-30T02:11:43Z`; relevant research scripts returned zero indexed symbols, no pagination, and freshness `not_tracked` with best-effort `no_recorded_issue`. Exact full source fallback was used. There is no graph-completeness or call-chain claim.

## 1. Preconditions and exact post-assessment commands

- Retain the pre-inference source/input/checkpoint/selection/registry freeze and its published commit6887 identity. The parent-reported seven final fits, software checks and canonical FIT_COVERAGE are prerequisites, not recomputed by this checklist.
- Preserve every COMPLETE/HOLD/FAILED/UNAVAILABLE outcome. An honest HOLD may still produce descriptive metrics or explicit unavailable panels. A script exit0 does not mean cohort completeness or superiority.
- Before rerunning any reporting command, preserve and hash any earlier `RESULTS.json`, figures, `FIGURE_QA.json`, `FARSITE_SCORES.json` and `REQUIREMENTS_STATUS.json`. These scripts overwrite their named outputs. Keep earlier failure evidence and do not silently replace its meaning.
- Use the canonical evidence directory as `--out`: `report.py` looks for `MODEL_SELECTION.json` under that directory. Redirecting it to a bare scratch directory would skip that selection-file branch and cannot be presented as the canonical frozen-selection report.
- Run postprocessing sequentially after both cohort jobs close. None of these commands launches new fitting, Monte Carlo or native FARSITE execution. FARSITE rescoring and report bootstrap calculations still read saved arrays and consume CPU, so they belong after the running jobs, not in this preparation task.

Setup, from a fresh shell after the parent confirms the safe boundary:

```sh
set -euo pipefail
FORECAST_REPO=/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b
FORECAST_PY=/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/venv-forecast/bin/python
FORECAST_DATA=/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/data/forecast-v2
FORECAST_RUN="$FORECAST_REPO/forecast/runs/20261030_perimeter_trained/execution_v3"
FORECAST_OUT="$FORECAST_REPO/research/forecast-v2"
cd "$FORECAST_REPO"
export PYTHONPATH="$FORECAST_REPO/forecast"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
```

Generate the canonical report, retaining the command, exit and output hashes:

```sh
"$FORECAST_PY" "$FORECAST_OUT/scripts/report.py" \
  --run "$FORECAST_RUN" --out "$FORECAST_OUT"
```

Recompute only the available stored FARSITE matched subset against the current US assessment. `--assessment` takes the directory, not the JSON filename; identity-only mode without this argument does not satisfy measurement packaging:

```sh
"$FORECAST_PY" "$FORECAST_OUT/scripts/audit_farsite.py" \
  --data "$FORECAST_DATA" --assessment "$FORECAST_RUN/heldout" \
  --out "$FORECAST_OUT/FARSITE_SCORES.json"
```

Then inspect all five current PNG/SVG pairs and create the separate hash-bound visual-QA receipt described below. Do not generate PASS by a file-existence test.

Preserve receipt-bound original producers with a fresh manifest. This example is a new versioned output name; if it already exists, retain it and use an explicitly new version rather than deleting it. Omit `--prune-identical-plain`, which removes existing snapshot files:

```sh
test ! -e "$FORECAST_OUT/SOURCE_PACKAGING_POST_ASSESSMENT_20261031.json"
"$FORECAST_PY" "$FORECAST_OUT/scripts/package_sources.py" \
  --out "$FORECAST_OUT/SOURCE_PACKAGING_POST_ASSESSMENT_20261031.json"
```

Finally refresh the requirement ledger after the report, FARSITE output and visual receipt exist:

```sh
"$FORECAST_PY" "$FORECAST_OUT/scripts/status.py"
```

Do not rerun `run_campaign.py fits/baselines/compare/freeze`, alter MODEL_SELECTION/BLIND_REGISTRY/protocols, or launch a second assessment to improve an outcome. No 2026 execution, OSF action, push or merge is part of these steps. The parent owns PR88 and any later publication.

## 2. Required canonical artifacts and JSON keys

### Current cohort custody and report

The report expects `RUN/heldout/ASSESSMENT.json` and `RUN/korean2025/ASSESSMENT.json`, each accompanied by its `FROZEN_ASSESSMENT.json` and exact receipt-listed per-fire files. Current receipt version must be `wfg.forecast-assessment/2`, status COMPLETE or HOLD, with `frozen_sha256`, `events`, `cases`, `per_fire_files`, and `failed_or_unavailable` retained. The reader checks the frozen phase/spotting-source identity and per-fire bytes. A scored file without an assessment receipt refuses reporting. An empty result must be explicit HOLD with reasons; it is not a zero score.

`RUN/report_inputs.json` must bind the US frozen assessment through `frozen_assessment_sha256`, `n_samples`, `seed`, `data_manifest_sha256`, and the source pointers used by the example panel. These must match frozen `trajectories`, `seed` and `extraction_manifest_sha256`. Do not repair a mismatch by rewriting identities after results exist.

Required generated files:

| File | Required interpretation |
| --- | --- |
| `research/forecast-v2/RESULTS.json` | Authenticated current-cohort statistics, separate secondary reconstruction, comparison provenance, availability and gate states |
| `research/forecast-v2/per_fire.csv` | Columns `model,fire,entries,positives,brier,bss_vs_persistence,bss_vs_best_dilation,average_precision,roc_auc,ece_10_bins,clipped_nll`; may be header-only for honest empty HOLD |
| `research/forecast-v2/ablation.csv` | Absolute own-support development scores; no inferred paired common-cell development effect |
| `research/forecast-v2/meanfield_vs_mc.csv` | All66 authenticated historical a06 rows, including null/unavailable rows |
| `research/forecast-v2/figures/fig01...fig05` | Both PNG and SVG for every required stem, including explicit diagnostic panels where metric data are unavailable |
| `research/forecast-v2/FARSITE_SCORES.json` | Separate stored-scenario matched-subset measurement/status, never full-cohort superiority |
| `research/forecast-v2/FIGURE_QA.json` | Separate human visual inspection of the exact current PNG/SVG hashes |
| `research/forecast-v2/REQUIREMENTS_STATUS.json` | Refreshed ledger; inspect row states and evidence, not the printed pending count alone |

Minimum `RESULTS.json` top-level checklist: `current_phase`, `label`, `run`, `ablation`, `primary_candidate_rule`, `final_models`, `primary_candidate`, `model_selection_sha256`, `development_ablation_interpretation`, `heldout_inputs`, `heldout`, `retrospective_superiority_gate`, `heldout_ablation`, `korean2025_secondary_reconstruction`, `korean2025_secondary_ablation`, `meanfield_vs_mc`, `figure_evidence`, `example_figure`, `report_status`. Cohort/result keys conditional in code must be present for these two actual completed assessment attempts; missing keys are not equivalent to unavailable metrics. `example_figure` may legitimately be null with a diagnostic panel.

`heldout` and the separate Korean object must retain `assessment_status`, `metric_status`, `unscored_outcomes`, `declared_fires`, `attempted_cases`, `case_outcome_counts`, `statistic_scope`, `models`, `paired`, `fires`, `entries`, `positives`. Empty metrics have `metric_unavailability_reason`, zero entries, null positives and empty model/paired maps. HOLD metrics are a descriptive supported subset, not a completed-cohort estimate.

For each model with actual supported entries, check these exact paths/fields:

- `models.<alias>.pooled`: `brier`, `bss_vs_persistence`, `bss_vs_best_dilation`, `average_precision`, `roc_auc`, `ece_10_bins`, `clipped_nll`, `lowest_bin`, `calibration`, `exact_nll`.
- `models.<alias>.per_fire.<event>`: matching per-fire scores and counts. Do not replace cell-pooled scores with an equal-fire mean without labeling the different estimand.
- `models.<alias>.bss_vs_persistence_paired_fire_95_interval` and `.bss_vs_best_dilation_paired_fire_95_interval`: `interval`, `draws`, `seed`, `undefined_zero_reference_draws`, `unit`. A zero-reference denominator stays undefined, not perfect skill.
- `paired.<primary_alias>__vs__persistence` and `paired.<primary_alias>__vs__dilation_best`: preserve `point_difference` and `percentile_95_interval`, using the frozen10,000 whole-fire resamples and seed20261030. No cell-level independent intervals.
- `pooled.lowest_bin`: `count`, `mean_prediction`, `observed_frequency`; show the before/after absolute calibration gap for primary, persistence and best dilation. No moving the bin after seeing results.
- `pooled.exact_nll`: `value`, `infinite`, `certainty_wrong_entries`. Infinity is explicitly reported; clipped NLL is a separate diagnostic.
- US `c651_mc.pooled` additionally retains `brier_mc_variance_corrected` and `mc_trajectories`. The fixed correction does not replace the primary observed Brier or establish calibration.

The primary remains the previously frozen development choice, not whichever current model wins. The retrospective gate requires complete US cohort, frozen selection present, both paired Brier upper endpoints below zero, and primary lowest-bin absolute calibration gap no worse than both baselines. Preserve `criteria_pass`, `brier_comparisons_pass`, `calibration_pass`, `complete_cohort_pass`, `lowest_bin_absolute_gaps`, `descriptive_subset_criteria`, `diagnostic_status`, `interpretation`. Every promotion criterion remains false under HOLD. Current2024 mapped-extent testing is not blind2026 testing.

`heldout_ablation` and `korean2025_secondary_ablation` retain assessment/frozen/per-fire identities, cohort, estimand, bootstrap, scope, unscored outcomes, completeness and `promotion_criteria_pass=false`. Their effects are cell-pooled candidate-minus-base Brier on common receipt-bound cells. Development `difference_vs_base`, `interval_95`, `excludes_zero`, and `fires_better_than_base` remain null because exact common-cell development predictions were not saved. Do not infer common cells from equal weights.

### Figure and visual-receipt checklist

| Stem | Evidence and mandatory qualification | Canvas at300dpi |
| --- | --- | --- |
| `fig01_reliability_all_models` | All models; ten fixed equal-width calibration bins, plus labeled low-probability display; HOLD/absence explicit | 7.2x3.0in,2160x900 |
| `fig02_per_fire_brier_paired` | Common-cell US per-fire values; primary versus best-dilation pairing; this plot is not itself a bootstrap CI | 7.2x2.6in,2160x780 |
| `fig03_ablation_forest_plot` | Receipt-bound US heldout common-cell effects only;10,000 whole-fire draws; HOLD descriptive or UNAVAILABLE | 3.5x3.0in for six effects/absence,1050x900 |
| `fig04_meanfield_vs_mc_rmse_by_horizon` | All1/3/6/12/24h positions and null points, cutoff/event denominators; range is cutoff min/max, not CI; active p>.001 is not physical flaming | 3.5x2.4in,1050x720 |
| `fig05_example_forecast_vs_perimeter` | Frozen primary and c651 against exact source extents, same selected window and0..1 scale; median positive-count illustration only, or diagnostic if absent | 7.2x2.0in,2160x600 |

Every `figure_evidence.<stem>` requires `status`, `metric_data_available`, and `files_sha256.png/svg`; Figure04 additionally reports execution and support counts. A generated unavailable-evidence panel is a completed diagnostic artifact, not available metric evidence. Inspect raster and vector renderings for clipping, legends, readable annotations, correct nulls, denominators, fixed colors/scales and truthful cohort labels. DejaVu Sans and the frozen plotting geometry should remain unchanged.

The minimum status-reader schema for `FIGURE_QA.json` is:

```json
{"figures":{"<each exact stem>":{"status":"PASS","files_sha256":{"png":"<exact current file SHA256>","svg":"<exact current file SHA256>"}}}}
```

Those placeholder values explain the schema; do not write them or PASS until a named reviewer has actually inspected the current pair. Record reviewer/date/scope as documentary metadata too. Status accepts QA only when both hashes equal `RESULTS.figure_evidence` and the actual files. `report_status` itself stays `GENERATED_PENDING_VISUAL_QA` or HOLD; the separate visual receipt is what closes visual QA. Do not edit a result to manufacture a different status.

### Comparison and FARSITE separation

`meanfield_vs_mc` must retain `execution_complete`, `execution_status`, `metric_data_available`, `metric_availability`, `support_by_horizon`, `authentication`, `runtime`, all66 `rows`, and the original aggregate/checkpoint/case identities. Its loader binds the12/66 key set, complete closed source family, historical argv hash, receipts/logs and round-trip CSV/JSON equality. Authentication does not replay unsaved fields/masks. Fixed-horizon costs are one joint24h MC/MF call per cutoff, counted once rather than five times; the six US fractional endpoints are separate helper-cacheTrue calls versus API-cacheFalse fixed calls. RMSE is model agreement over known initially-unburned cells, with a further p>.001 active mask for the plot. US Brier is observed only at survey endpoints; Korean fixed-horizon Brier is reconstruction. Repeated cutoffs are not independent fires.

`FARSITE_SCORES.json` must retain all historical inventory rows, including explicit unavailable/failed reasons. Require `execution_status=NO_NATIVE_EXECUTION_STORED_SCENARIOS_ONLY`, `native_execution_this_command=false`, `superiority_criteria_pass=false`, `scores_available`, `scored_cases`, `total_historical_cases`, `stored_case_count`, `stored_fire_count`, `all_stored_cases_scored`, `skipped_unavailable_cases`, `measurement_status`, `metric_status`, `assessment_status`, `assessment_complete`, assessment/frozen hashes, `current_case_admission_pass`, `rejected_current_cases`, `assessment_unscored_outcomes`, `configuration_differences`. `scores.models` is present only for actual nonempty matches; an empty scores object or exit0 is not a measurement success. HOLD may coexist with a legitimate descriptive scored subset.

Each scored historical row requires authenticated current US2024 membership,0<duration<=48h, ordered common cell identities/labels and all16 current comparators plus `farsite_scenario`. Preserve each scenario's own native-horizon receipt and right-censor convention before treating no-arrival cells as endpoint negatives. Missing/short horizon or an empty FARSITE intersection remains unavailable. Historical M548 predictions never enter this comparison. Weather is a spatially summarized repeated station scenario rather than repeated spatial rasters; FARSITE uses one-cell fuel99 padding rather than current zero exterior; one deterministic scenario differs from1024 c651 trajectories. No new native campaign or full-cohort superiority follows.

## 3. Exact ledger requirements and documentary gaps

`REQUIREMENTS_STATUS.json` requires `schema=wfg.forecast-v2.requirements/1`, `current_phase`, `evidence_class`, `authenticated_development_fits`, `authenticated_final_fits`, `promotion_authority=false`, `comparison_execution_complete`, `receipts`, `requirements`.

Check all requirement families:

- `1B-1-library`, `1B-1-12cutoffs`, `1B-2-development`, `1B-2-full-final-fits`, `1B-3-structural-ablations`, `1B-4-baseline-fitting`, `1B-4-heldout-scoring`, `1B-4-FARSITE-matched-subset`, `1B-5-pre-registration`.
- `1B-2-frozen-split`, `1B-2-exact-model-selection-freeze`, `1B-2-complete-fit-membership`, `1B-global-spotting-wind-inputs`, `1B-data-geometry-sensitivity`.
- Seven `1B-ablation-<variant>` rows; `1B-assessment-us2024`, `1B-assessment-korea2025`; nine `1B-baseline-assessment-<baseline>` rows.
- Ten `1B-metric-...` rows: `Brier`, `BSS-persistence`, `BSS-best-dilation`, `AP`, `ROC-AUC`, `fixed-bin-ECE`, `clipped-NLL`, `per-fire-values`, `whole-fire-bootstrap`, `lowest-bin-calibration`.
- Five exact figure stems with current artifact status, `metric_data_available`, `visual_qa` and both file paths;12 cutoff requirements plus66 horizon rows, preserving execution versus reference/support availability.

Documentary attention, without changing frozen source during the running assessments:

1. README currently contains pre-inference statements such as parent verification pending and heldout inference has not run. The parent must reconcile narrative timing after receipts close. Prompt deliverables still require heldout headline Brier/AP/BSS and their supported uncertainty, lowest-bin before/after, per-fire tables, runtime/parameters, commands/seeds/hashes/host. The completed source-only clarification in section3A confirms paired Brier/BSS intervals only: AP/ROC/ECE intervals are absent, and the explicit AP headline-interval requirement remains a reporting gap. Do not relabel Brier intervals as uncertainty for another metric or silently invent a new post-outcome method. Add only authenticated outcomes with HOLD/UNAVAILABLE qualification; do not turn development values into heldout headlines. Preserve earlier documentary versions and verify whether a document is pinned before editing it.
2. The status ledger's baseline identifier `c651_mf` differs from the actual fixed comparator spelling `c651_meanfield` in the FARSITE/current assessment contract. Treat this as a ledger label, not a seventeenth model, and state the alias in the release documentation. No outcome-driven column rename is authorized.
3. Status `pending` stdout counts every row whose status is not literally COMPLETE. Legitimate IMPLEMENTED_TESTED, READY_FOR_OWNER_REGISTRATION and generated-figure statuses contribute. Inspect structured rows and separate expected2026 NOT_READY from current missing deliverables. Several training/geometry membership rows are existence-based summaries; the saved registry admission and canonical audits remain the authenticity evidence.
4. `package_sources.py` covers `EVIDENCE/executions/*.json` source maps, not an automatic traversal of both current assessment directories or every223-file frozen identity. Require `unresolved_original_source=[]`, `retired_spotting_sources_complete=true`, schema `wfg.forecast-source-snapshots/1`, phase receipt identities and original/compressed hashes. Exit0 can still contain unresolved non-retired producers. Separately inventory the frozen registry/selection/protocol, the full published assessment-source closure, inputs, checkpoints, both case/per-fire/assessment receipts and report/QA artifacts; do not claim the source-packaging manifest alone is the entire release.
5. The FARSITE script records the directories it finds and does not itself hardcode the expected30 historical cases. Reconcile `cases`/counts with the previously authenticated fixed30-case inventory and retain all rows/reasons; no omission to obtain a complete-looking subset. It remains a separate-scenario baseline even when every available match is scored.
6. No automatic Markdown headline writer, FARSITE figure or separate Korean per-fire CSV/figure suite is generated. Korean per-fire/model statistics are in the separate JSON object; the required five figures are principally the US report plus the fit-cutoff MC/MF comparison. Any additional documentary presentation must preserve frozen estimands/selection and identify its cohort, without tuning or inventing missing metrics.
7. The source packager may add gzip snapshots and a new manifest; `--prune-identical-plain` removes files and is intentionally excluded. Do not rebuild/re-sign MODEL_SELECTION, registry, preregistration or input manifests after assessment access just to absorb packaging changes. Preserve the parent223-file source bookend and all failed/retired/provisional evidence as distinct identities.
8. Keep the scope statements: mapped extent/reconstruction, no complete survey coverage mask, retrospective rectangles, cutoff-repeat weather and unestablished operational as-of availability, no physical flame/evacuation-safety or universal speed validation. Brier is a proper score, not a likelihood; multi-step mean field is a closure approximation. Frozen event/year catalog membership is not physical ignition-year proof.
9. The protocol can be READY_FOR_OWNER_REGISTRATION with exact fitted identities while2026 execution remains NOT_READY. Current retrospective results, software gates and source hashes do not establish external publisher-first chronology, OSF registration, or the independently attested pre-run/post-score clearance prerequisites. The parent/user owns those later actions.

## 3A. Frozen uncertainty fields: confirmed source-only clarification

**Confirmed mandatory headline-reporting gap:** the supplied evidence wording explicitly asks heldout Brier/AP/BSS with paired-by-fire95% intervals. The frozen current report emits paired Brier-difference and BSS intervals, but **no AP interval**. Neither absolute AP nor AP-minus-reference has a generated CI field or implemented resampling method. ROC AUC and ECE also have point estimates only. This is a bounded claim about the complete current `report.py -> baselines.py` scoring path, not a claim about every unrelated metric helper in the repository. No actual result file was inspected.

The requirement is at [01B prompt line73](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/docs/next/prompts/01B_forecast_upgrades.md:73); the broader metric list is at [line54](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/docs/next/prompts/01B_forecast_upgrades.md:54). The primary superiority criterion is Brier-based ([prompt line56](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/docs/next/prompts/01B_forecast_upgrades.md:56)); this AP uncertainty omission does not change that frozen criterion or imply any observed model outcome.

### Exact fields generated, and fields not generated

Let `S` be `RESULTS.heldout`, `RESULTS.korean2025_secondary_reconstruction`, or the descriptive `FARSITE_SCORES.scores` object when its supported subset exists.

| Metric/estimand | Generated point field | Generated95% interval field | Frozen definition/limit |
| --- | --- | --- | --- |
| Absolute Brier | `S.models.<m>.pooled.brier` and `.per_fire.<event>.brier` | **None for absolute Brier** | Its available confidence interval is for a candidate-minus-reference difference, not for the absolute point score. If an absolute Brier CI is required in addition to paired differences, that is a separate unresolved output requirement. |
| Paired Brier difference | `S.paired.<m>__vs__<r>.point_difference` | `S.paired.<m>__vs__<r>.percentile_95_interval` | Cell-pooled candidate Brier minus reference Brier, whole fires resampled with replacement; reference defaults persistence/best dilation. Negative favors candidate. |
| BSS versus persistence | `S.models.<m>.pooled.bss_vs_persistence` | `S.models.<m>.bss_vs_persistence_paired_fire_95_interval.interval` | Ratio of pooled squared-error sums under the same whole-fire draw schedule. `draws`, `seed`, `unit`, and `undefined_zero_reference_draws` are retained. |
| BSS versus best dilation | `S.models.<m>.pooled.bss_vs_best_dilation` | `S.models.<m>.bss_vs_best_dilation_paired_fire_95_interval.interval` | Same ratio definition. Zero-reference draws are excluded and counted explicitly; all-undefined interval is null. |
| Average precision | `S.models.<m>.pooled.average_precision` and `.per_fire.<event>.average_precision` | **None** | Non-interpolated tie-group AP point estimator; no positive labels gives null. No AP resampling code, AP CI seed, AP bootstrap-draw handling or paired AP-difference output exists in this path. |
| ROC AUC | `S.models.<m>.pooled.roc_auc` and `.per_fire.<event>.roc_auc` | **None** | Rank-based point estimate with average tied ranks; a single class gives null. |
| Fixed-bin ECE | `S.models.<m>.pooled.ece_10_bins` and `.per_fire.<event>.ece_10_bins` | **None** | Ten fixed equal-width bins, count-weighted absolute calibration gaps. Calibration-table rows and lowest-bin values are descriptive points, not confidence intervals. |

The engine return schema is explicit in [baselines.py score, lines145-163](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/forecast/wildfire/baselines.py:145). [per_fire_scores, lines166-167](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/forecast/wildfire/baselines.py:166) calls the same point-score function per fire. [score_entries, lines229-242](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/forecast/wildfire/baselines.py:229) adds only `paired_fire_bootstrap` comparisons, whose [entire body, lines170-193](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/forecast/wildfire/baselines.py:170) operates on squared errors. AP is computed separately in [lines108-120](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/forecast/wildfire/baselines.py:108), ROC AUC in [lines123-129](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/forecast/wildfire/baselines.py:123), and calibration/ECE in [lines132-163](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/forecast/wildfire/baselines.py:132). None of those point-estimator functions resamples data.

### Actual canonical draw schedule and seed

[report.py detailed_scores, lines505-531](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/research/forecast-v2/scripts/report.py:505) calls `B.score_entries` with `draws=10000, seed=20261030`, then adds exact-NLL diagnostics and the BSS intervals above. It does not add AP, ROC or ECE confidence intervals. Each draw samples `len(unique fires)` whole fires with replacement using `np.random.default_rng(seed).integers`; repeated fires repeat all their scored cells and counts, so the Brier estimate is pooled rather than an unweighted average of fire-level Briers. Endpoints are `np.quantile(values,[.025,.975])`. The uncertainty conditions on the fixed predictions and scored mapped labels; it does not include training, reconstruction, missing-support or physical-truth uncertainty.

[RUN_PROTOCOL lines224-227](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/research/forecast-v2/RUN_PROTOCOL.json:224) fixes unit whole fire,10,000 draws and seed20261030. These generic controls alone do **not** make a complete AP CI definition: the engine never recomputes pooled AP on a draw and does not specify what an AP interval does with resamples containing no positives. AP has a frozen point-estimator definition, but no frozen implemented CI field/method in the current scoring path. A hypothetical AP cluster bootstrap is not an output this code currently produces.

The raw baseline helper defaults use seed20261029 ([baselines.py line171](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/forecast/wildfire/baselines.py:170), [line230](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/forecast/wildfire/baselines.py:229)); the canonical report explicitly overrides that default to20261030. The alternate `evaluate.py --perimeter-scores` route calls `score_entries` without a seed ([evaluate.py lines182-191](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/forecast/wildfire/evaluate.py:182)), so it is not a canonical-report replacement and does not create the missing AP CI. Do not launch it as a workaround.

The heldout ablation uses the same Brier bootstrap with base as reference and explicit10000/20261030 ([report.py lines464-495](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/research/forecast-v2/scripts/report.py:464)). FARSITE calls `reporting.detailed_scores(...,draws=10000,seed=20261030)` ([audit_farsite.py line364](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/research/forecast-v2/scripts/audit_farsite.py:364)), so it inherits the same absence of AP/ROC/ECE intervals. The future protocol explicitly specifies its primary Brier-difference interval ([preregistration lines20-27](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/forecast/documents/preregistration_blind_test.md:20)); its general metric list ([lines158-163](/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/forecast/documents/preregistration_blind_test.md:158)) does not supply an implemented current AP CI output.

### Required documentary resolution, without changing the frozen run

Do not claim the literal headline-interval deliverable is fully satisfied. Report AP/ROC/ECE as point estimates and mark their CIs `UNAVAILABLE_NOT_IMPLEMENTED_IN_FROZEN_SCORER`; this is documentary wording, not a new JSON output key that the current code emits. At minimum, AP's requested interval remains an explicit mandatory reporting gap. Absolute Brier intervals are also absent if the owner interprets the prompt as requiring them in addition to paired Brier differences. ROC/ECE point metrics are required; the prompt is less specific about separate headline CIs for them, so their absence should be disclosed without conflating it with a failed Brier superiority gate.

The owner must explicitly accept/document the unmet AP interval requirement or authorize a separately specified supplement. That supplement would need its own frozen estimand, common resample identities, zero-positive/undefined-draw rule, interval construction, seed and provenance before inspecting the corresponding quality results. This source-only clarification does not authorize such a change, a new numerical run, editing any223 frozen files, replacing the selected model, changing the gate, or retrospectively claiming the current code already had the method. Never substitute Brier intervals, Figure04 ranges, pointwise trajectory intervals, or between-fire AP spread for an AP CI.

Source identities additionally inspected: `forecast/wildfire/baselines.py` SHA325abbe79ba7c22ed3eb60391a68d2becdbfd0aa4c6659debb94db6a34afbb1f; `forecast/wildfire/evaluate.py` SHAa6a21b4a8fb5cb16b1c61d706825f149c07386e9bd32c8b73bd0090c7b9155c9; RUN_PROTOCOL SHA c2dce7f7724b1bda6d71391b690904067e6ad46c808276c34f72fd4a1b1e8243; preregistration document SHAaaae3df67d4297d486ad3f81ab6b32692157d1390d9adf2e41cfc6617866dbe6. Report remains SHA56e7769084481167cc57d2d62510eef37cb4f7657826e9737985b77d9dd7dfc7. Graph recheck remained generation2026-10-30T02:11:43Z/ready19157nodes; report/baselines not_tracked, evaluate metadata_changed; exact source fallback, no graph mutation or graph-based completeness assertion.

## 4. Exact source identities read for this checklist

No outcome files were used. Full files were read, with additional targeted reads to fill tool-output truncation.

| Relative to repository root | SHA256 |
| --- | --- |
| `research/forecast-v2/scripts/report.py` | `56e7769084481167cc57d2d62510eef37cb4f7657826e9737985b77d9dd7dfc7` |
| `research/forecast-v2/scripts/status.py` | `dece20897d7442c7c19e270f5e0f2384e6b5f9cd5e221d38b7f44ce459ec477d` |
| `research/forecast-v2/scripts/audit_farsite.py` | `6edb769fbcb9a7977e2689f7de337ed327feabd5dadd9983f3cec3443e04a6db` |
| `research/forecast-v2/scripts/package_sources.py` | `f7a77e6a3dd9bb32f694d62f874e49dd85224357129614ed6293801b9ddc2dfc` |
| `research/forecast-v2/README.md` | `12880dd2699370845f3d255799962d1eb896ca4bc7780ee76db473480a54bdb7` |
| `research/forecast-v2/PLAN.md` | `4a8e28fa10646546651ed432a0cf8498e5dca9b8fcfa9e5f2ddf5df352e1e23d` |
| `docs/next/prompts/01B_forecast_upgrades.md` | `99434f85fc42cfe556c9592ee872f5e70be29c9a080e06fcbb0a6d24ba0739ce` |
