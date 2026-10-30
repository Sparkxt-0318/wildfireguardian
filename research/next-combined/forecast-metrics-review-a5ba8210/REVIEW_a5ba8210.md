# Independent forecast metrics and reporting audit

Source under review: `a5ba82108c44956c01071d8450751b5d2defa387`. No actual study input, checkpoint, prediction or score was opened. All executable checks use tiny hand-specified arrays or temporary reporting fixtures. No training, simulator or heavy lease was executed; no repository file was edited.

## Confirmed finding: unmatched-weight ablation can manufacture an improvement

`research/forecast-v2/scripts/report.py:ablation` forms each model/fire squared-error total as Brier times its own reported validation weight, subtracts the base total, and divides by the base weight. It does not require matching weights or authenticate identical scored cells. Model validity and therefore the evaluated development population can differ, especially with added source support. Its result is not generally the labelled candidate-minus-base Brier difference.

Exact independent reproduction: base Brier 0.1 at weight 100, burnout Brier 0.1 at weight 50, one synthetic common fire. Both absolute pooled Briers are 0.1. The current report nevertheless returns difference -0.05, interval [-0.05, -0.05], `excludes_zero=true` and one fire favouring burnout. The true difference between those two reported Briers is zero. This is a reporting arithmetic/comparability defect; it does not alter training or the separately computed frozen equal-fire selection rule.

Reproduction: `ablation_weight_repro_a5ba8210.py` and its JSON output. Report source SHA-256: `99f7b4d4f587c8a24fd1edb482bd4c491538318dbd6d258d18df31093536264b`. This audit did not inspect actual development weights, so it does not assert that a particular saved numerical row is wrong.

Required repair before final comparative claims: authenticate identical scored cells/weights for a paired common-cell ablation, or retain per-model absolute/descriptive scores and explicitly mark the paired comparison unsupported. Equal counts alone do not prove identical coordinates. A descriptive difference of two separately normalized scores must use each model's own denominator in the point and every resample, with the differing-population scope explicit; it must not be presented as an identified structural effect. Preserve historical reports, source and the frozen selection rule. Active numerical source closures must stay fixed until their safe boundary.

## Other scoped checks passed

The separate arithmetic/gate audit passes 51/51 controls:

- Manual Brier, tied-threshold average precision, pairwise ROC AUC, fixed-bin ECE and clipped NLL agree on six tiny arrays, including empty, all-positive, all-negative, equal-score and exact 0/1 forecasts. Degenerate AP/AUC/zero-reference BSS remain undefined where appropriate. Invalid probabilities refuse.
- A deliberately unequal-size three-fire example manually reproduces the whole-fire cluster bootstrap point and percentile endpoints. A fire selected twice contributes its entire cell set twice. The seed and repeated results match. This estimates the declared pooled error difference, distinct from equal-fire development selection.
- Detailed BSS uses pooled squared-error ratios with the same sampled whole fires. Zero-reference resamples retain their explicit undefined count. Infinite exact NLL retains null finite value and the number of certainty-wrong entries.
- A gate truth table passes only with a complete nonempty assessment, frozen selection, both persistence and best-dilation paired upper limits strictly below zero, and no worse lowest-bin absolute calibration gap. A zero-touching interval, either adverse comparison, missing lowest-bin data, worse calibration, empty score population, HOLD subset or missing selection closes the gate.
- Fixed dilation ties choose the slowest tied growth rate as documented.

Source reading confirms that the held-out scorer reconstructs deterministic common support independently of MC samples. Fresh MC/model validity must equal that support; numerical failures cannot trim the scoring population. All models, baselines and labels use the same source-bound ordered coordinates in each saved case. Source-bound unavailable/failed cases force assessment HOLD. The original guarded identity and model selection path remains required before inference; the report cannot promote an absent frozen selection.

The logistic baseline and dilation selection consume fit-fire lists only. Logistic negative sampling carries inverse inclusion weights through scaling and fitting. Korean 2025 reconstruction scores use a separate cohort/directory/result key. Stored FARSITE subset audit was outside this bounded source version and was not rerun or generalized to a whole-cohort result.

## Evidence and limits

`audit_metrics_a5ba8210.py/.json/.log` contains the 51 passing controls, exact source hashes, host and scope. `ablation_weight_repro_a5ba8210.py/.json` preserves the confirmed failure. Commands: `PYTHONDONTWRITEBYTECODE=1 work/venv-forecast/bin/python SCRIPT`, both exit 0; the reproduction intentionally records the wrong current output rather than claiming a passing correctness assertion.

Graph evidence uses Tier 2 project `wfg-next-1b-audit-a5ba8210-20261030`, generation `2026-10-30T08:44:12Z`, confirmed at the exact detached root. Narrow baselines discovery returns all 15 functions; exact bootstrap source was read by qualified symbol. Baselines and material existing tests have current metadata/no recorded gaps. A broad test-name discovery returned 40/93 and was not used for exhaustive claims; a narrowed baseline-test query returns all seven functions. Research scripts are deliberately excluded, so complete relevant reporting/scoring/baseline training functions were read directly. Coverage is best-effort, not a completeness proof.

These checks do not establish empirical quality, physical calibration, population validity or a blind 2026 result. The one confirmed ablation finding remains a reporting HOLD until repaired and independently rechecked; other reviewed arithmetic and gate paths have scoped software clearance.
