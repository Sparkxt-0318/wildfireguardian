> **Post-merge status — 31 October 2026:** PRs #85–88 are merged into Main. The readiness report below is the preserved pre-merge assessment, including its then-current draft/PR statuses. Merging experimental code does not clear its scientific HOLDs or promote a checkpoint. See [post-merge compatibility and regression repairs](../postmerge-fixes-20261031/README.md).

# Current next-track readiness

**[Draft readiness, PR 87](https://github.com/Sparkxt-0318/wildfireguardian/pull/87). The independent saved-result audit and exact 306-case census pass; the selected forecast fails the frozen primary criterion.** Korea retains full-cohort HOLD with seven unavailable windows. Stored FARSITE reconciliation and publication figure QA pass within their scopes. The separate US descriptive interval sidecar is complete and independently passes saved-output review; Korea retains null complete-cohort metrics. A physics and C support/risk gates keep Step 4 **NOT_RUN_GATED**. No track code is merged here, and no default promotion or future 2026 execution is cleared.

## Current track state

| Track and pinned source | Reviewable evidence | Current acceptance |
|---|---|---|
| [1A radiation, PR 85](https://github.com/Sparkxt-0318/wildfireguardian/pull/85) `43324736f` | Scoped mathematics review; 42 fixed arithmetic checks; separate 42 functional tests and 367 release hashes, exit 0 | Physics HOLD; journey, peak/dose binding and route-rejection counts gated/null |
| [1B forecast, PR 88](https://github.com/Sparkxt-0318/wildfireguardian/pull/88) canonical/source `691cc162b`; sidecar result `bd9b9498f`; published `473c8da0a`; freeze 6887 | Independent actual saved-result checker 87eb PASS; exact 306-case census PASS; unchanged 858 source/canonical bytes reported by root; layout-only five-pair visual QA PASS; complete US16-model descriptive interval replay PASS | Primary criterion FALSE. US: 6 fires, 273 windows, 1,705,079 entries, 8,520 positives. KR: 4 fires, 33 represented / 26 supported windows, 1,792 supported entries, 404 positives, 7 UNAVAILABLE; full-cohort HOLD |
| [1C members/SIPP/truth, PR 86](https://github.com/Sparkxt-0318/wildfireguardian/pull/86) report `06ad9fe90`; contact phase `095b8d174` | Conditional 320-record contact study; independent output 22/22 and figure/boundary 5/5 checks | Restricted contact evidence. Strict support 0/15,360; 42,008 risk-admission records contain zero scored risk cases |

The [canonical summary](canonical-summary-691cc162/RESULTS.json) retains selected d4_wind raw US Brier **0.0049268862** and AP **0.05425462**. Its Brier-difference interval versus persistence, **[-0.0001376572, +0.0000228664]**, includes zero. Its lowest-bin absolute calibration gap **0.00407585** is worse than best dilation's **0.00154577**. Both failures are retained; no replacement model is selected. Original US process exit 0 and separate Korean exit 1/HOLD remain distinct from the negative scientific criterion.

Selected US pooled diagnostics, conditional on fixed predictions/support and the six mapped-extent fires:

| Metric | Point | 95% whole-fire interval |
|---|---|---|
| Raw Brier | 0.004926886223 | [0.002923498278, 0.006528267901] |
| AP | 0.05425462117 | [0.03740655210, 0.07898795971] |
| Canonical BSS versus persistence | 0.01399879889 | [-0.006717251331, 0.02508271040] |
| Canonical BSS versus best dilation | 0.9616455801 | [0.9533396126, 0.9734959123] |

Brier/AP intervals are new separate descriptive sidecar fields; BSS rows are unchanged canonical fields with zero undefined-denominator draws. Positive secondary AP descriptors override neither primary requirement. Full AUC/ECE/clipped-NLL intervals and all fixed-model records are in the [completed sidecar](descriptive-sidecar-producer-bd9b9498/supplements/current_descriptive_intervals_output_20261031_v2/DESCRIPTIVE_INTERVALS.json). Korean complete-cohort metrics remain null, with all seven unavailable outcomes retained and no Korean array decoding.

The original b3 checker HOLD is preserved. An independent development-only proof explains a one-ULP mean difference from floating accumulation order; reviewed checker 87eb routes only that assertion through its pre-existing finite comparison policy. No tolerance was tuned, canonical result changed or primary rule relaxed. The original 38 controls, separate 63 targeted controls and 256 correlated development predicates retain their separate scopes. The subsequent authorized actual 87eb saved-output audit exits 0. [Precision review](canonical-result-precision-review-87eb9a24/REVIEW.md); [actual receipt](canonical-result-precision-review-87eb9a24/AUTHORIZED_ACTUAL_REVIEW_V2.json).

## Cross-track checks

| Requested check | State | Reason |
|---|---|---|
| C1/C4, radiation v2 versus v1 | NOT_RUN_GATED | A physics/full-journey acceptance and supported C risk truth unresolved |
| Binding on coherent members, K=4 and K=16 | NOT_RUN_GATED | No accepted physics/binding or supported multi-step coherence comparison |
| SIPP on combined bridge-v2 packets | NOT_RUN_GATED | Orchestrator Step 4 acceptance precondition unmet |
| Strict whole-domain contact K scaling | NOT_RUN_CONTACT_ADMISSION | Every saved member has unknown domain cells under the strict predicate |
| Known-footprint contact K study | COMPLETE_CONDITIONAL | Restricted contact problem completed; no full-policy/risk result |
| Native Caldor/Rim forecast exports | NOT_RUN_ALIGNMENT_UNESTABLISHED | Causal six-channel inputs, exact grids and cutoff binding unestablished |

## Scientific claim changes

**Radiation.** A has a conditional mathematical/software argument for represented panels, supported by separate arithmetic and functional checks. This remains unvalidated physics, not a machine-checked universal proof. Its zero lower bound, fallback outside the separation cone, possible hull-refinement nonconvergence and precision/budget limits constrain use. Literature geometry does not uniquely identify physical emitter parameters. No empirical route-rejection or binding count follows. [Mathematics review](radiation-review-43324736/REVIEW.md).

**Forecast.** Saved-output reconciliation and exact membership now pass, while the frozen primary result is negative. Selected d4_wind has pooled US Brier 0.0049268862 and AP 0.05425462, but its persistence comparison interval includes zero and calibration is worse than best dilation. These are six mapped-extent fires, not 273 independent fires or physical flame truth. Korea represents all 33 windows but supports only 26; seven unavailable outcomes retain full-cohort HOLD. Its supported subset cannot supply a complete-cohort conclusion. Models, selection, inputs and primary rules remain frozen. The reviewed one-ULP checker correction preserves all original source/failure evidence and changes no canonical value.

**Intervals.** The separate fixed-method sidecar now supplies US pooled raw Brier/AP/AUC/ECE/clipped-NLL intervals for all 16 models. Independent replay matches 80 exact points, 80 absolute intervals and 32 secondary paired-AP descriptors, using 10,000 whole-fire draws at seed 20261030. These remain descriptive over six fires. Canonical paired Brier/BSS/calibration, selection and primary criteria are unchanged; the future blind scorer's BSS point path remains distinct. Original candidate6080 and the first incomplete-input-map refusal remain preserved. Reviewed c41 repairs nonfinite-JSON admission; a fresh 654-input authorization adds only two already-frozen inventories, with the same method/source. Korean metrics stay null/unavailable, retaining all seven outcomes and no available-26 bootstrap.

**Comparators.** The 12-cutoff/66-row MF/MC check reconciles saved summaries, not unsaved per-cell fields or MC correctness. The separate stored FARSITE audit reconciles 29 exact subsets, 288,999 entries, 17 columns and 32 paired comparisons; one 4,489-minute case remains unavailable under the 48-hour policy. Its canonical status remains HOLD, native execution false and superiority false. Sixty original ASC/timing paths are absent at their recorded locations and in the local seven-file packages; this bounded custody limit is not a global absence claim. Historical receipts/saved arrays were authenticated by that reviewer; native execution and weather/landscape encoding were not regenerated.

**Contact and figures.** C's known-footprint campaign retains 48 completed-search pairs, 36 arrivals, 12 restricted exhaustions and 224 unknown-endpoint records with null costs. Saved recheck receipts cover 72 returned routes; the independent audit did not replay geometric witnesses. Median SIPP/sweep planner ratio 0.561111 is descriptive on the recorded host; repeats are not independent fires and K=32 loses two earlier returns. Strict support remains 0/15,360. Full-policy, safety and risk rates remain unresolved. B's five layout-only publication pairs pass root visual QA while original clipping and failed-v1 title/source history remain preserved. Visual readability adds no numerical or physical proof. External 2026 registration/chronology remains NOT_READY.

## Evidence, history and reproduction

[GATES.json](GATES.json) records exact sources, outcomes, nulls and limits. [EVIDENCE_SHA256.json](EVIDENCE_SHA256.json) binds retained bytes. [The prior summary](history/pre-publication-correction-ced8bc81/README.md) and [index](history/pre-publication-correction-ced8bc81/ARCHIVE_INDEX.json) remain verbatim. All earlier failed audits, including original b3/HOLD and candidate 6080, are preserved; the [original history index](history/ARCHIVE_INDEX.json) links detailed earlier stages.

| Current evidence | Scope and remaining limits |
|---|---|
| [Final Bdocument review](final-b-document-review-473c8da0/REVIEW_473c8da0.md) and [root final ownership/custody check](final-b-parent-check-473c8da0/FINAL_B_PARENT_CHECK.json) | 125 unique requirement IDs, 21 links and final headlines/HOLDs consistent; root1738file ownership/style check and unchanged858/sidecar/source bytes. Documentary/custody scope, no new numerical or physical validation |
| [Actual canonical audit](canonical-result-precision-review-87eb9a24/SOURCE_INVENTORY.json) and [root authorizations/858 map](canonical-review-parent-authorizations/SOURCE_INVENTORY.json) | Checker 87eb, result a7d667cc, unchanged results 083d06c5; saved arithmetic/custody, no original rasters/support/geometry or model replay |
| [Exact 306-case census](current-cohort-census-actual-8d29a5e1/ACTUAL_CENSUS.json) and [receipt/log custody](current-cohort-census-actual-8d29a5e1/SOURCE_INVENTORY.json) | 273 US SCORED; 26 KR SCORED + 7 UNAVAILABLE. Membership/status pass does not clear scientific criteria. The original b3 companion reference is retained separately from actual executable 87eb |
| [Stored FARSITE review](farsite-actual-review-f759f2e9/REVIEW.md) and [source/result custody](farsite-actual-review-f759f2e9/SOURCE_INVENTORY.json) | 26,614 correlated actual predicates, separate 568 metadata and 25 synthetic controls; not independent samples or pooled counts. Maximum arithmetic difference 1.11e-16 under pre-existing policy |
| [Publication figure QA](publication-five-figure-review-f759f2e9/PUBLICATION_FIVE_FIGURE_QA_PARENT.json) and [metadata/source/failure custody](publication-five-figure-review-f759f2e9/SOURCE_INVENTORY.json) | Root viewed all five vector previews and changed 03/05 rasters; other three rasters exact original copies. Readiness copies no figure payload or scientific array |
| [Actual sidecar receipt](descriptive-sidecar-actual-review-bd9b9498/INDEPENDENT_REVIEW_RECEIPT.json), [independent report](descriptive-sidecar-actual-review-bd9b9498/REVIEW_ACTUAL_ATTEMPT2.md) and [source/results inventory](descriptive-sidecar-actual-review-bd9b9498/SOURCE_INVENTORY.json) | 80 exact points + 80 absolute intervals + 32 paired AP descriptors. Separate predeclared 30 literal metric / 12 sklearn ranking comparisons and 22 invented preparation controls; not scientific samples |
| [Source c41 review](descriptive-sidecar-source-c41e607a/REVIEW_c41e607a.md), [fixed method](descriptive-interval-protocol-v1/DESCRIPTIVE_INTERVAL_PROTOCOL_V1.json) and [prerequisite V2](descriptive-interval-prerequisites-v2/DESCRIPTIVE_INTERVAL_PREREQUISITES_V2.json) | Original6080 failure unchanged; distinct V2 source repair passes. Owner77, original8 and additional27 source controls overlap and are not pooled |
| [Producer output/attempt custody](descriptive-sidecar-producer-bd9b9498/SOURCE_INVENTORY.json) and [root authorizations/metadata preflight](descriptive-sidecar-root-authorization-attempt2/SOURCE_INVENTORY.json) | First attempt refused before arrays/output directory:652-map omitted two already-frozen inventories. Complete static closure adds only those two, fresh3195 authorization uses654 inputs, unchanged c41/5fd/0dff. Original8b5 authority/refusal and preflight tripwire records retained |
| [A functional receipt](a-functional-checks-43324736/test-1a-bounds-independent.json), [C contact review](contact-campaign-review-06ad9fe9/REVIEW_06ad9fe9.md) and [strict support census](contact-member-admission-7c1cae3f/SOURCE_INVENTORY.json) | Earlier functional/contact evidence unchanged; no Step 4 experiment or physical/risk clearance |

The actual sidecar reviewer checks 654 consumed inputs, 223 frozen paths and 858 canonical artifacts before/after; overlapping input/frozen maps consolidate to 873 distinct files. Nine binary files are hashed without deserialization. All 80 diagnostic distributions and 32 paired-AP distributions are independently reconstructed; unsaved producer per-draw metric intermediates cannot be byte-compared. Case-to-fire probability equality additionally relies on prior 87eb. The draw matrix is only referenced here: B `us2024_draws.npy`, shape 10000x6, `<i8`, C order, NPY SHA4943b1da and raw payload SHAc1f5a138. Its 445 observed multiplicity vectors restore all 10,000 draw frequencies. Readiness copies no NPY/NPZ or model payload and reruns no numerical job.

Root confirms the final B push at473, exit0; PR88 is OPEN/DRAFT at that exact head, with [all eight CI checks successful](publication-ci-pr88-473c8da0/ROOT_GH_SNAPSHOT.json) in the later root snapshot. The [earlier RUNNING observation](history/ci-running-observation-07c81174.json) is retained separately. The original remote B stayed at6887 until this push. f759 was the local render-content ancestor, now reachable from473. [The explicit metadata correction](PUBLICATION_METADATA_CORRECTION.json) qualifies older mistaken published-head wording while preserving it verbatim in history. No numerical or source evidence changes.

The earlier 3,507-test/367-release owner gate and canonical software/membership review remain source/time-scoped evidence. Their 9,841 bookkeeping predicates are correlated, and source-derived historical pure schedules are not retroactive runtime IDs. Fit source/cache/member values and models were not replayed here. Root's unchanged 858-byte map is archived as attributed custody; readiness did not open/re-hash those scientific/model payloads.

From this integration worktree, regenerate only readiness prose and hashes:

```sh
../venv-routing/bin/python research/next-combined/build_report.py
```

Exact executed commands, exits, seeds, hosts/dependency versions and source hashes remain in linked receipts. Original B bootstrap uses 10,000 whole-fire draws, seed 20261030; represented C contact source uses seed 20261008. Saved reviews report native macOS arm64, Python 3.12.1 and pinned scientific dependencies. This archival pass reads authorized immutable summary JSON and closed review/metadata only; it executes no checker, metric, test, inference, native or numerical job and copies no NPZ/original scientific arrays/model payloads. Readiness makes no push, merge or default promotion. Earlier remote Claude results remain reference only. Review order remains exports/members, radiation library, forecasting, SIPP, truth harness, then integration, conditional on gates.
