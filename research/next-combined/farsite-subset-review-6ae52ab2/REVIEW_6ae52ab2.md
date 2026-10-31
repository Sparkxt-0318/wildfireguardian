# Independent stored-FARSITE subset tool review

Review head: `6ae52ab20b9c48666d7a8fcb900a817f9239c4b1`.
Audit tool SHA-256: `122605a495156f4a449caf155ea9fa0854c70091f6346560e2116fea5765f996`.

Verdict: HOLD for two confirmed admission gaps. No actual quality assessment, stored prediction array, native execution, model inference or historical M548 array was opened. The existing identity-only JSON was read for counts and horizon metadata only.

## P2: A missing required comparator silently narrows the comparison

`audit_farsite.py:152-154` derives the required columns from the supplied aggregate. `280-282` requires the same resulting columns across matched cases, but neither enforces the fixed full forecast/baseline comparator set. `probe_missing_model.py` removes `p_d4_seed0` consistently from the synthetic individual and per-fire NPZ files and updates their exact receipt hashes. The current frozen phase is unchanged. The command accepts the pair, emits `DESCRIPTIVE_MATCHED_SUBSET_COMPLETE` and `scores_available=true`, and silently omits `d4_seed0` from the score table. Superiority remains false, but the required all-model comparison is not enforced.

Require the exact protocol comparator set, including every fixed seed0 forecast variant, current c651 modes and required baselines, before scoring. Missing or unexpected columns should refuse or produce an explicitly incomplete comparison; they must not be a complete matched-subset result.

## P2: Current receipt matching does not enforce the frozen interval duration bound

`audit_farsite.py:101-108` authenticates the reporting receipt and checks only `cohort=us2024` before indexing its cases. Neither this path nor the scoring path checks the frozen `0 < duration <= 48h` eligibility rule. `probe_long_interval.py` constructs a fully consistent synthetic 49-hour historical/current case, with its own finite 2940-minute native horizon and updated case/aggregate/historical receipts. It is accepted as `SCORED_COMMON_SUBSET` and `DESCRIPTIVE_MATCHED_SUBSET_COMPLETE`.

This is a cohort-admission defect, not a horizon defect. A sufficiently long native run cannot make an interval eligible for a cohort capped at 48 hours. In particular, the authentic 4489-minute identity-only case must remain an unmatched or explicitly ineligible row. Enforce the exact frozen case population and duration constraint before metrics, retaining the historical row and reason.

## Scoped positive evidence

The 23 owner synthetic tests pass independently in 1.73 seconds. A separate 21-control audit passes the inclusive endpoint, finite no-arrival censor, missing/invalid/short native horizon, duration/selection/hash/origin/unit/sentinel mismatches, false positive/negative occupancy and initial-cell exclusion controls. Manual two-fire synthetic arithmetic reproduces cell-pooled Brier 0.11 and per-fire Brier 0.04 and 0.25. These checks are separate from the two confirmed gap probes and are not pooled as one pass claim.

Source inspection confirms individual case JSON equality to its embedded receipt, frozen-assessment binding, exact prediction and per-fire hashes, ordered unique integer coordinates, source endpoint labels, initial-burn exclusion, exact shared aggregate entries and finite probabilities. Every matched comparator uses the same ordered common cells; the first finding concerns completeness of the comparator set. Existing tests retain all 30 mixed available/failed/unavailable rows, suppress scores for empty intersections, keep HOLD status and always keep `superiority_criteria_pass=false`.

Identity metadata contains 30 scenarios across six fires, native horizons from 263 to 4489 minutes, all with source-recorded finite horizon availability; exactly one exceeds 48 hours. No 1470-minute universal cap was inferred or borrowed from the unrelated routing study.

Tier 2 graph project `wfg-next-1b-audit-6ae52ab2-20261030`, generation `2026-10-30T09:34:11Z`, was verified. The scripts subtree is deliberately excluded, so the full 291-line audit source and the material reporting-loader/detailed-scoring source were read directly. The narrowed test-function query returned all 13 functions with no pagination. Test, baseline and identity-JSON coverage is current with no recorded issue, a best-effort signal only. No graph mutation or tracked edit was made; the immutable worktree remains clean.
