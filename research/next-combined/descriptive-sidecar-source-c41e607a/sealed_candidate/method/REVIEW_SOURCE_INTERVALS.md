# Frozen source interval review

The current report has a documentary gap against prompt lines 54 and 73: headline absolute pooled Brier and AP have point estimates without their own 95% interval fields. Paired Brier-difference and BSS intervals already exist. The broader diagnostic reading of line 54 also calls for explicit pooled ROC AUC, fixed-bin ECE and clipped NLL intervals. A separate descriptive saved-output supplement can close these gaps without changing any frozen primary result, model selection, calibration criterion or 223 frozen files. This is source-scope clearance for that bounded proposal, not clearance to run it or scientific validation.

## Evidence and scope

All inspected source/document bytes came from immutable Git commit6887dc618253e6568c6cbbfd3c9a96f1d0d86b70 using `git --no-replace-objects show`. Exact copies and SHA-256 values are in `source/` and `SOURCE_MANIFEST.json`. No current study output, metric, NPZ, checkpoint, label, probability or live assessment was opened. No production function, scorer, model, MC or native job was executed. Tiny invented arithmetic examples are the only numerical work.

Tier2 graph project `wfg-next-1b-fixture-49a7cccc-20261030` was confirmed ready at the declared track1B root; coverage generation is2026-10-30T12:52:57Z. The script-scope metric/bootstrap search returned0, no more. This is not absence evidence: scripts are wholly excluded/not_tracked. Direct frozen source fallback covered every material definition and caller listed below. Baselines discovery returned all15 functions, no more. A both-direction depth2 trace of score_entries returned12 callees and2 callers, without truncation; unrelated low-confidence heuristic edges were discarded. Exact graph snippets for score_entries, paired_fire_bootstrap, score and _average_precision agreed with the frozen source. Baselines and evaluate coverage were metadata_match/no recorded issue. Protocol Markdown had metadata_changed, so the immutable Git document was read directly; no live-document claim is made. Docs were excluded. Relevant scope coverage pagination had no more entries. No exhaustive project-list claim is made from the paginated project inventory.

Material source reads: full baselines.py1-242; report.py imports1-38, load_assessment314-343, load_report_inputs347-356, assessment_scores359-376, retrospective_gate379-399, heldout_ablation464-495, primary_candidate498-502, detailed_scores505-531, figure_per_fire573-593, figure_ablation596-616 and full main716-845; score_cohorts.py constants32-39, full predict_case188-227 and full main230-371; blind_test.py full primary_decision557-572 and score575-681; evaluate.py full kernels_main166-179 and perimeter_scores_main182-192; prompt42-82; RUN_PROTOCOL.json full1-233; frozen protocol relevant selection30-63, support126-147 and scoring149-168; SPLIT.json full held_out mapping. SPLIT coverage is metadata_match/no recorded issue. Model/predictor dependency chains were outside scope and were not run.

## Exact current report fields and estimands

`report.main -> load_assessment -> B.load_scored_entries -> assessment_scores -> detailed_scores -> B.score_entries` is established by direct source. The scorer writes all supported cell-interval rows by event; the loader concatenates per-fire files and converts labels/probabilities to float64. Counts vary by fire. Equal weighting of entries is not equal weighting of fires.

| Frozen field below heldout (also Korean secondary via assessment_scores) | Exact estimand | Existing95% interval |
| --- | --- | --- |
| models.<model>.pooled.brier | Total squared error divided by total common cell-interval entries | None for this absolute point |
| models.<model>.pooled.average_precision | Pooled tied-score AP, recomputed over every concatenated entry | None |
| models.<model>.per_fire.<event>.brier / average_precision | Same score restricted to one fire, pooling its intervals | None for each absolute point |
| paired.<model>__vs__<reference>.point_difference | Pooled Brier(candidate) minus pooled Brier(reference), same entries | percentile_95_interval,10,000 whole-fire draws, seed20261030 in canonical report |
| models.<model>.pooled.bss_vs_persistence | 1 minus candidate total SSE / persistence total SSE | models.<model>.bss_vs_persistence_paired_fire_95_interval |
| models.<model>.pooled.bss_vs_best_dilation | 1 minus candidate total SSE / fixed best-dilation total SSE | models.<model>.bss_vs_best_dilation_paired_fire_95_interval |
| models.<model>.pooled.roc_auc / ece_10_bins / clipped_nll | Pooled point metrics on the same entries | None in this report path |

The paired Brier draw resamples F whole fires with replacement, pools each selected fire's error sums and counts with multiplicity, and divides the pooled error difference by the pooled count. The point is the same pooled difference on the original population, not the mean per-fire difference. The reported per_fire_difference and fires_favouring_candidate are additional descriptors, not substitutes for the pooled point.

The BSS draw is1 minus a ratio of resampled SSE sums. It is not the mean per-fire BSS. Zero-reference-SSE draws are omitted from the existing interval calculation and counted in undefined_zero_reference_draws. Existing BSS intervals therefore describe defined-denominator draws when that count is nonzero; retain this frozen behavior and disclose the count. Do not silently relabel it as an unconditional interval. The existing fields carry interval,draws,seed,undefined_zero_reference_draws and unit="whole fire, pooled error ratio". A zero observed reference SSE gives a null point.

The canonical report passes seed20261030 explicitly through detailed_scores. The raw baselines.score_entries and paired_fire_bootstrap defaults are20261029. The alternate evaluate --perimeter-scores path uses that raw default and does not call detailed_scores; it cannot stand in for the canonical report's full fields or seed. The canonical protocol fixes10,000 draws and seed20261030.

AP sorts descending probability and evaluates precision at the end of each exact score tie group. It returns null when there are no positives. All-positive AP remains defined and equals1; ROC AUC requires both classes. No AP resampling or undefined-draw policy is implemented in the frozen report. A library's default zero/no-positive AP must not replace this null rule.

`report.main` additionally writes `heldout.models.c651_mc.pooled.brier_mc_variance_corrected`, subtracting the fixed finite-MC variance correction, at lines766-772. It is a separate point with a different estimand. A raw stored-probability Brier interval must not be attached to that corrected point.

The current primary rule stays unchanged: development selection is lowest equal-fire development Brier across the fixed2020/2021/2022 folds with fixed tie order; the selected variant is already d4_wind_seed0. The retrospective gate requires the selected model's paired pooled Brier upper interval endpoint below0 against both persistence and dilation_best, plus a lowest-bin absolute calibration gap no worse than either baseline and a complete cohort/selection. The bin is the existing first equal-width bin [0,.1). No absolute Brier/AP interval enters this gate. HOLD estimates remain supported-subset descriptors and primary criteria remain closed.

## Future source is a distinct path

The frozen blind_test.score calls B.score_entries at649, then adds best-dilation BSS point values at650-660. It does not call report.detailed_scores. It therefore has paired Brier-difference intervals and absolute Brier/AP/BSS points, but no absolute Brier/AP or BSS interval fields. This distinction prevents attributing current report BSS interval fields to future scorer output. Its primary decision retains the paired Brier and lowest-bin criteria, complete/documentary admission and minimum10 fires. This review neither changes nor authorizes future scoring/registration.

## Bounded descriptive supplement recommendation

After both current cohorts close and root authorizes final saved-output review, a new source-pinned supplement may read only authenticated saved common-cohort predictions. Its minimum fields should cover pooled absolute raw Brier, AP, ROC AUC, fixed-bin ECE and clipped NLL intervals for all 16 fixed model columns in each complete cohort, plus paired pooled AP differences versus persistence and dilation_best using identical draws. Keep the canonical RESULTS.json, primary decision, paired Brier/BSS outputs and all 223 frozen files untouched. Bind supplement code, exact dependency versions, canonical result/assessment/frozen receipts and every consumed saved artifact hash. First require the full expected 306-case census and existing independent result checks. A missing expected fire/case closes the complete-cohort supplement; do not bootstrap only available fires. Preserve every failed/unavailable outcome. Any later separately requested supported-subset diagnostic must be visibly scoped and cannot satisfy this full-cohort deliverable.

Use separate US2024 and Korean2025 populations with their frozen fire identities. Do not combine mapped extent and reconstruction labels. For every fixed model, use the same10,000 whole-fire draws, seed20261030, canonical lexically sorted fire order and pinned NumPy RNG implementation. Cache multiplicity vectors only as an execution optimization. The point and interval must target the same pooled cell-interval estimand; do not attach an equal-fire macro interval to a pooled point. All secondary models remain secondary, and no interval selects a replacement model.

The exact model set is `score_cohorts.EXPECTED_MODELS` at lines 37-39, not a caller-selected list: base_seed0, burnout_seed0, burnout_spotting_seed0, c651_mc, c651_meanfield, d4_seed0, d4_wind_seed0, dilation_1h, dilation_2h, dilation_4h, dilation_8h, dilation_best, ellipse_seed0, logistic, mixed_base_seed0, persistence. All 16 must be present in both complete cohorts. `dilation_best` is the exact model alias; `bss_vs_best_dilation` is a distinct metric field name.

The frozen SPLIT.json SHA-256 is f72282e967fa49172ff9721e0abf363a49a568929b305426cdc949c2763d2af2. Canonical complete-cohort event order, matching `np.unique(fire)`, is:

```text
US2024:
ID-BOF-000683_Wapiti_Wapiti
ID-BOF-000904_Goat
ID-BOF-001080_Lava
ID-SCF-240202_RedRock
WA-SES-000173_Pioneer
WY-BTF-002416_FishCreek

Korean2025:
KFS_01
KFS_04
KFS_06
KFS_13
```

Use the exact construction already used by canonical paired Brier/BSS, separately for each cohort, under the pinned NumPy version:

```python
fires = np.unique(fire)  # exact expected sorted IDs above; refuse any missing/extra fire
rng = np.random.default_rng(20261030)
sampled = rng.integers(0, len(fires), size=(10000, len(fires)))
# Each sampled row becomes np.bincount(row, minlength=len(fires)).
# Reuse that same matrix for every model, reference and diagnostic.
interval = np.quantile(values, [0.025, 0.975], method="linear")
```

The frozen source omits the explicit quantile method argument; NumPy's default is linear, so making it explicit in the separate supplement preserves this convention. Pin the actual dependency version and draw-matrix bytes/digest in the supplement. This recommendation does not replace integers with choice, change RNG family, alter fire order or use a separate seed for AP. The synthetic environment is NumPy 1.26.4 and sklearn 1.5.2; this report has not independently audited all registered dependency pins.

For absolute Brier, let S_f be a model's total squared error, n_f its count and m_f the sampled fire multiplicity. The draw value is sum(m_f S_f)/sum(m_f n_f). The original point is sum(S_f)/sum(n_f). Take the2.5th and97.5th percentiles of the10,000 actual draw values. Repeated draws remain repeated observations when taking quantiles. Label: "Pooled cell-interval Brier;95% whole-fire percentile interval, conditional on these fixed saved predictions and mapped/reconstructed references." This is raw Brier, not the separate MC-variance-corrected point.

For pooled AP, sort each fixed model once by its exact stored-probability values after canonical conversion, preserving exact ties without rounding. For every descending score group g and fire f, retain total count n_gf and positive count a_gf. For multiplicity vector m, compute n_g=sum(m_f n_gf), a_g=sum(m_f a_gf), total positives A=sum_g a_g, cumulative positives C_g and cumulative count N_g. If A>0, AP(m)=sum over groups with n_g>0 of (a_g/A)*(C_g/N_g). Skip zero-weight groups. This is exactly AP on the multiset formed by duplicating all entries of each sampled fire, including all its intervals. It is not an average of per-fire AP values.

There are at most C(2F-1,F-1) distinct multiplicity vectors:462 for6 fires and35 for4. Evaluate AP once per observed vector/model, then restore each vector's frequency in the original10,000 sampled draws before quantiles. Uniformly weighting cached vectors changes the bootstrap law and is wrong. Processing one model/vector batch at a time can bound memory; this review makes no runtime or memory claim for actual study arrays. Any nontrivial saved-array join/sort still requires the shared HEAVY lease after active cohort jobs close.

Use a new explicit AP interval policy before actual inspection: a no-positive original population has null AP and null interval. Every no-positive bootstrap draw remains null and is counted, never replaced by0. If any of the10,000 draws is undefined, the full95% AP interval is unavailable. Optionally provide a separate percentile interval of defined draws under an explicit "conditional on a positive-label draw" label with total, defined and undefined counts. If no draw is defined, that conditional interval is also null. Keep all-positive AP defined as1. This new descriptive policy does not alter any frozen primary rule or existing BSS policy.

For paired pooled AP, compute AP_candidate(m) minus AP_reference(m) using the same multiplicity vector, with positive values favouring the candidate. Use the same fixed original-point difference and full 10,000 draw frequencies. No-positive draws are null for both models because the labels/common population are shared; preserve nulls and counts. Any undefined draw makes the full paired AP interval unavailable; an optional separate conditional interval must say so. The pairing controls also reject using a reference from a different fire draw. These AP descriptors do not change the primary paired Brier rule, whose favourable direction is negative.

For ROC AUC, retain the source average-rank tie convention: it is the fraction of positive-negative pairs ranked correctly, with half credit for equal scores. The same cached score-group/fire counts suffice: for each weighted group, multiply its positive count by the count of negatives below it plus half its tied negative count, sum, then divide by total positives times total negatives. No-positive or no-negative original populations/draws are null, not zero. Any undefined draw makes the full AUC interval unavailable; an optional defined-draw interval must be separately conditioned on both classes being present. Do not adopt the AP-only no-positive rule for AUC.

For fixed-bin ECE, preserve `BINS=np.linspace(0.0,1.0,11)` and the source `np.clip(np.digitize(p,BINS[1:-1],right=False),0,9)`, using the actual floating edges without rounding. For a draw, sum over bins the absolute difference between the weighted probability sum and weighted positive-label sum, then divide by the weighted total entry count. This equals the source count-weighted absolute calibration gap. Empty bins contribute zero. Keep the same 10 bins for all draws/models; do not refit bins, smooth calibration or move the primary lowest bin.

For clipped NLL, preserve `LOG_FLOOR=1e-7` and `q=np.clip(p,1e-7,1-1e-7)`. Cache each fire's sum of `-y*log(q)-(1-y)*log1p(-q)` and divide the resampled weighted loss sum by the resampled total entry count. Apply linear percentile quantiles to all 10,000 finite draw values. This is the clipped diagnostic; it does not hide or replace the separately frozen exact-NLL infinity/certainty-error fields. Brier, ECE and clipped NLL remain defined on every nonempty validated draw; an empty fire/population or invalid probability is an admission error, not a zero diagnostic. No broader diagnostic conflicts with the frozen source semantics under these definitions.

Suggested supplement fields: estimand,point,percentile_95_interval,status,draws,seed,fire_order,fire_count,entry_count,defined_draws,undefined_no_positive_draws,undefined_no_negative_draws,conditional_on_defined_draws_interval and bindings. For undefined AUC draws, counts should distinguish no positives/no negatives and retain a union count without double counting. Label any conditional interval separately. A comparison table should call its columns "pooled point" and "whole-fire interval for the same pooled estimand". Every AP difference is a separately named secondary descriptor, not a substitute superiority criterion.

## Synthetic checks and limits

`synthetic_estimands.py`:12/12 invented arithmetic controls pass. They distinguish pooled and equal-fire Brier, paired Brier differences and BSS, demonstrate pooled-versus-macro AP, duplicated-fire AP, tied-score invariance, all-positive AP, null no-positive AP, retained undefined draw counts, zero-reference SSE and identical-model zero paired effects.

`synthetic_cached_ap.py`: all 462 six-fire and 35 four-fire multiplicity vectors for two invented models match literal duplicated-fire concatenation exactly as rational numbers, 994 comparisons. The 978 defined comparisons also agree with sklearn weighted AP within 2e-15; 16 invented no-positive vectors remain null. A separate repeated-vector control verifies restored draw frequencies and catches uniform unique-vector weighting. Another 1,988 paired AP comparisons against invented persistence/dilation references match literal duplicated-fire differences and retain nulls; a wrong reference draw is detected. The toy data use unequal fire sizes, cross-fire ties, no-positive fires and an all-positive fire.

`synthetic_diagnostics.py`: seven invented four-fire draws pass pooled Brier/ECE/clipped-NLL sufficient-statistic versus literal concatenation checks; defined AUC agrees with both literal and weighted sklearn AUC and absent-class draws stay null. Three boundary controls check the exact bin boundary rule, half-credit AUC ties and clipping floor. These are correctness controls for the recommended arithmetic, not actual study intervals or evidence of model quality.

The proposal is mathematically coherent and within a separate descriptive reporting scope. Current raw artifacts were not inspected, and no actual supplement was run. The small number of fires limits interpretation of cluster percentile intervals; they remain conditional on frozen models, support and mapped/reconstructed labels, with no survey-completeness, physical flame, prospective detection, routing-safety or promotion conclusion. Full final metric/census and visual review remain separately pending root authorization.
