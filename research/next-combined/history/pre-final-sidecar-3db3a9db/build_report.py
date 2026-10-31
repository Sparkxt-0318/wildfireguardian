"""Render current readiness from pinned local evidence, without running a study.

Edit CURRENT_EVIDENCE.json only after a new bounded review. Historical reports,
original failures and the previous generator remain archived unchanged.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def build(out):
    current = json.loads((out / 'CURRENT_EVIDENCE.json').read_text())
    assert current['schema'] == 'wfg.next.combined-readiness/2'
    assert not current['publication']['branches_merged'] and not current['publication']['github_merges']
    assert not current['publication']['checkpoint_promoted']
    for name, row in current['cross_track_checks'].items():
        assert row['state'] in ('NOT_RUN_GATED', 'NOT_RUN_ALIGNMENT_UNESTABLISHED', 'NOT_RUN_CONTACT_ADMISSION'), name
    a, b, c = (current['tracks'][key] for key in ('1A', '1B', '1C'))
    audit = json.loads((out / b['review']).read_text())
    assert audit.get('source_head', audit.get('track_head')) == b.get('review_source_head', b['source_head']) and audit['checks'] == audit['passed'] == b['checks']
    software = json.loads((out / b['final_software_gate']['receipt']).read_text())
    coverage = json.loads((out / b['historical_actual_fit_coverage_failure']['receipt']).read_text())
    assert software['status'] == 'PASS' and all(row['exit_code'] == 0 for row in software['checks'])
    assert coverage['status'] == 'HOLD' and coverage['exit_code'] == 1 and coverage['output_sha256'] is None
    assert b['actual_fit_coverage']['actual_result_checker'] == 'PASS_INDEPENDENT_SAVED_RESULT_AUDIT_87EB_SEPARATE_FROM_ORIGINAL_B3_HOLD'
    assert b['current_admission']['state'] == 'CLEARED_COMMITTED_PUBLISHED_6887_WITH_SCOPE'
    source_review = json.loads((out / b['coverage_recipe_candidate_review']['audit']).read_text())
    assert source_review['checks'] == source_review['passed'] == 99 and not source_review['actual_fit_coverage_audit_run']
    assert source_review['candidate_sha256'] == b['coverage_recipe_candidate_review']['candidate_sha256']
    provisional_review = json.loads((out / b['provisional_coverage_review']['audit']).read_text())
    assert provisional_review['checks'] == provisional_review['passed'] == 9612
    assert not provisional_review['raw_non_admission_tested'] and not provisional_review['actual_member_or_cache_value_replay']
    mfmc = json.loads((out / b['mfmc_actual_reconciliation']['result']).read_text())
    assert mfmc['status'] == 'PASS_SAVED_METRIC_RECONCILIATION' and mfmc['case_count'] == 12 and mfmc['row_count'] == 66
    assert not mfmc['raw_field_replay'] and not mfmc['producer_writes_field_arrays']
    gate_v2 = json.loads((out / b['final_software_gate_v2']['receipt']).read_text())
    canonical = json.loads((out / b['actual_fit_coverage']['receipt']).read_text())
    assert gate_v2['status'] == canonical['status'] == 'PASS' and canonical['exit_code'] == 0
    assert b['actual_fit_coverage']['state'] == 'SOFTWARE_MEMBERSHIP_PASS_WITH_SCOPE'
    canonical_review = json.loads((out / b['canonical_independent_review']['inventory']).read_text())
    assert canonical_review['passed'] == canonical_review['correlated_metadata_custody_predicates'] == 9841
    assert not b['canonical_saved_result_review']['readiness_array_model_or_checker_replay'] and not b['freeze_process']['future2026_inference_authorized']
    assert b['current_census_preparation']['synthetic_passed'] == 34 and b['current_census_preparation']['actual'] == 'PASS_COMPLETE_FROZEN_306_CASE_CENSUS'
    assert not b['driver_static_review']['actual_driver_replay']
    assert b['wapiti_integrity']['cases'] == 52 and not b['wapiti_integrity']['prediction_or_source_arrays_copied_by_readiness']
    (out / 'GATES.json').write_text(json.dumps(current, indent=2, allow_nan=False) + '\n')
    closure = json.loads((out / b['current_cohort_execution']['closure']['root_check']).read_text())
    assert closure['all223_frozen_files_match'] and all(closure['receipt_log_identity_checks'].values())
    progress = closure['last_metadata_monitor']['progress']
    assert progress['us2024']['statuses'] == {'SCORED': 273}
    assert progress['korea2025']['statuses'] == {'SCORED': 26, 'UNAVAILABLE': 7}
    assert b['current_cohort_execution']['state'] == 'BOTH_CLOSED_ACTUAL_SAVED_RESULT_CENSUS_PASS_PRIMARY_FALSE_KR_HOLD'
    assert b['descriptive_intervals']['actual_computation'] == 'NOT_AUTHORIZED_NOT_RUN'
    assert not b['descriptive_intervals']['source_review_is_candidate_implementation_review']
    actual = json.loads((out / b['canonical_saved_result_review']['result']).read_text())
    census = json.loads((out / b['current_census_actual']['result']).read_text())
    results = json.loads((out / b['canonical_primary_result']['canonical_summary']).read_text())
    assert actual['status'] == 'PASS_INDEPENDENT_SAVED_RESULT_AUDIT'
    assert actual['checker_sha256'] == '87eb9a2467f4e8011e960273ca77a6878a7807173f5869041905363214a297aa'
    assert census['total_expected_cases'] == census['total_represented_cases'] == 306 and not census['scientific_clearance']
    assert results['retrospective_superiority_gate']['criteria_pass'] is False
    assert results['korean2025_secondary_reconstruction']['assessment_status'] == 'HOLD'
    assert b['stored_farsite_actual_review']['canonical_status'] == 'HOLD'
    assert not b['stored_farsite_actual_review']['native_execution_this_command']
    text = f'''# Current next-track readiness

**[Draft readiness, PR 87]({current['publication']['integration_draft_pr']}). The independent saved-result audit and exact 306-case census pass; the selected forecast fails the frozen primary criterion.** Korea retains full-cohort HOLD with seven unavailable windows. Stored FARSITE reconciliation and publication figure QA pass within their scopes. The descriptive interval sidecar remains blocked. A physics and C support/risk gates keep Step 4 **NOT_RUN_GATED**. No track code is merged here, and no default promotion or future 2026 execution is cleared.

## Current track state

| Track and pinned source | Reviewable evidence | Current acceptance |
|---|---|---|
| [1A radiation, PR 85]({a['draft_pr']}) `{a['source_head'][:9]}` | Scoped mathematics review; 42 fixed arithmetic checks; separate 42 functional tests and 367 release hashes, exit 0 | Physics HOLD; journey, peak/dose binding and route-rejection counts gated/null |
| [1B forecast, PR 88]({b['draft_pr']}) canonical/source `{b['source_head'][:9]}`; published `{b['published_head'][:9]}`; freeze 6887 | Independent actual saved-result checker 87eb PASS; exact 306-case census PASS; unchanged 858 source/canonical bytes reported by root; layout-only five-pair visual QA PASS | Primary criterion FALSE. US: 6 fires, 273 windows, 1,705,079 entries, 8,520 positives. KR: 4 fires, 33 represented / 26 supported windows, 1,792 supported entries, 404 positives, 7 UNAVAILABLE; full-cohort HOLD |
| [1C members/SIPP/truth, PR 86]({c['draft_pr']}) report `{c['current_report_head'][:9]}`; contact phase `{c['contact_campaign']['source_phase_head'][:9]}` | Conditional 320-record contact study; independent output 22/22 and figure/boundary 5/5 checks | Restricted contact evidence. Strict support 0/15,360; 42,008 risk-admission records contain zero scored risk cases |

The [canonical summary]({b['canonical_primary_result']['canonical_summary']}) retains selected d4_wind raw US Brier **0.0049268862** and AP **0.05425462**. Its Brier-difference interval versus persistence, **[-0.0001376572, +0.0000228664]**, includes zero. Its lowest-bin absolute calibration gap **0.00407585** is worse than best dilation's **0.00154577**. Both failures are retained; no replacement model is selected. Original US process exit 0 and separate Korean exit 1/HOLD remain distinct from the negative scientific criterion.

The original b3 checker HOLD is preserved. An independent development-only proof explains a one-ULP mean difference from floating accumulation order; reviewed checker 87eb routes only that assertion through its pre-existing finite comparison policy. No tolerance was tuned, canonical result changed or primary rule relaxed. The original 38 controls, separate 63 targeted controls and 256 correlated development predicates retain their separate scopes. The subsequent authorized actual 87eb saved-output audit exits 0. [Precision review]({b['canonical_saved_result_review']['review']}); [actual receipt]({b['canonical_saved_result_review']['result']}).

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

**Radiation.** A has a conditional mathematical/software argument for represented panels, supported by separate arithmetic and functional checks. This remains unvalidated physics, not a machine-checked universal proof. Its zero lower bound, fallback outside the separation cone, possible hull-refinement nonconvergence and precision/budget limits constrain use. Literature geometry does not uniquely identify physical emitter parameters. No empirical route-rejection or binding count follows. [Mathematics review]({a['review']}).

**Forecast.** Saved-output reconciliation and exact membership now pass, while the frozen primary result is negative. Selected d4_wind has pooled US Brier 0.0049268862 and AP 0.05425462, but its persistence comparison interval includes zero and calibration is worse than best dilation. These are six mapped-extent fires, not 273 independent fires or physical flame truth. Korea represents all 33 windows but supports only 26; seven unavailable outcomes retain full-cohort HOLD. Its supported subset cannot supply a complete-cohort conclusion. Models, selection, inputs and primary rules remain frozen. The reviewed one-ULP checker correction preserves all original source/failure evidence and changes no canonical value.

**Intervals.** Core source has paired pooled Brier and pooled SSE-ratio BSS intervals; absolute pooled raw Brier/AP/AUC/ECE/clipped-NLL intervals remain missing. BSS intervals exclude and count zero-reference-SSE draws, making affected intervals conditional on defined denominators. The future blind scorer's BSS point path is distinct. Method 5fd was fixed before final quality interpretation. Candidate 6080 fails strict nonfinite-JSON admission on exponent overflow; its source/synthetic review is HOLD, with separate V2 repair in progress. Actual sidecar computation is **NOT_AUTHORIZED**. Prerequisite V2 binds reviewed 87eb and original b3/HOLD lineage without changing the method. Korean complete-cohort intervals must remain null/unavailable; no available-26 bootstrap.

**Comparators.** The 12-cutoff/66-row MF/MC check reconciles saved summaries, not unsaved per-cell fields or MC correctness. The separate stored FARSITE audit reconciles 29 exact subsets, 288,999 entries, 17 columns and 32 paired comparisons; one 4,489-minute case remains unavailable under the 48-hour policy. Its canonical status remains HOLD, native execution false and superiority false. Sixty original ASC/timing paths are absent at their recorded locations and in the local seven-file packages; this bounded custody limit is not a global absence claim. Historical receipts/saved arrays were authenticated by that reviewer; native execution and weather/landscape encoding were not regenerated.

**Contact and figures.** C's known-footprint campaign retains 48 completed-search pairs, 36 arrivals, 12 restricted exhaustions and 224 unknown-endpoint records with null costs. Saved recheck receipts cover 72 returned routes; the independent audit did not replay geometric witnesses. Median SIPP/sweep planner ratio 0.561111 is descriptive on the recorded host; repeats are not independent fires and K=32 loses two earlier returns. Strict support remains 0/15,360. Full-policy, safety and risk rates remain unresolved. B's five layout-only publication pairs pass root visual QA while original clipping and failed-v1 title/source history remain preserved. Visual readability adds no numerical or physical proof. External 2026 registration/chronology remains NOT_READY.

## Evidence, history and reproduction

[GATES.json](GATES.json) records exact sources, outcomes, nulls and limits. [EVIDENCE_SHA256.json](EVIDENCE_SHA256.json) binds retained bytes. [The prior summary]({current['historical_evidence']['pre_actual_result_summary']}) and [index]({current['historical_evidence']['pre_actual_result_inventory']}) remain verbatim. All earlier failed audits, including original b3/HOLD and candidate 6080, are preserved; the [original history index](history/ARCHIVE_INDEX.json) links detailed earlier stages.

| Current evidence | Scope and remaining limits |
|---|---|
| [Actual canonical audit]({b['canonical_saved_result_review']['inventory']}) and [root authorizations/858 map](canonical-review-parent-authorizations/SOURCE_INVENTORY.json) | Checker 87eb, result a7d667cc, unchanged results 083d06c5; saved arithmetic/custody, no original rasters/support/geometry or model replay |
| [Exact 306-case census]({b['current_census_actual']['result']}) and [receipt/log custody]({b['current_census_actual']['inventory']}) | 273 US SCORED; 26 KR SCORED + 7 UNAVAILABLE. Membership/status pass does not clear scientific criteria. The original b3 companion reference is retained separately from actual executable 87eb |
| [Stored FARSITE review]({b['stored_farsite_actual_review']['review']}) and [source/result custody]({b['stored_farsite_actual_review']['inventory']}) | 26,614 correlated actual predicates, separate 568 metadata and 25 synthetic controls; not independent samples or pooled counts. Maximum arithmetic difference 1.11e-16 under pre-existing policy |
| [Publication figure QA]({b['publication_five_figures']['parent_review']}) and [metadata/source/failure custody]({b['publication_five_figures']['inventory']}) | Root viewed all five vector previews and changed 03/05 rasters; other three rasters exact original copies. Readiness copies no figure payload or scientific array |
| [Fixed method]({b['descriptive_intervals']['protocol']}), [prerequisite V2]({b['descriptive_intervals']['prerequisites']}) and [candidate HOLD]({b['descriptive_intervals']['original_candidate_review']['review']}) | Original method/V1 prerequisite/source-only review retained. Candidate: four positive and four failed refusal probes; separate owner 53-control replay. V2 scratch/actual computation not inspected or cleared |
| [A functional receipt]({a['functional_receipt']}), [C contact review]({c['contact_campaign']['independent_review']}) and [strict support census]({c['contact_support_census']['inventory']}) | Earlier functional/contact evidence unchanged; no Step 4 experiment or physical/risk clearance |

The earlier 3,507-test/367-release owner gate and canonical software/membership review remain source/time-scoped evidence. Their 9,841 bookkeeping predicates are correlated, and source-derived historical pure schedules are not retroactive runtime IDs. Fit source/cache/member values and models were not replayed here. Root's unchanged 858-byte map is archived as attributed custody; readiness did not open/re-hash those scientific/model payloads.

From this integration worktree, regenerate only readiness prose and hashes:

```sh
../venv-routing/bin/python research/next-combined/build_report.py
```

Exact executed commands, exits, seeds, hosts/dependency versions and source hashes remain in linked receipts. Original B bootstrap uses 10,000 whole-fire draws, seed 20261030; represented C contact source uses seed 20261008. Saved reviews report native macOS arm64, Python 3.12.1 and pinned scientific dependencies. This archival pass reads authorized immutable summary JSON and closed review/metadata only; it executes no checker, metric, test, inference, native or numerical job and copies no NPZ/original scientific arrays/model payloads. No default promotion, merge or push occurs. Earlier remote Claude results remain reference only. Review order remains exports/members, radiation library, forecasting, SIPP, truth harness, then integration, conditional on gates.
'''
    (out / 'README.md').write_text(text)
    hashes = {}
    for path in sorted(out.rglob('*')):
        if path.is_file() and path.name not in ('EVIDENCE_SHA256.json', 'GATES.json', 'README.md') and '__pycache__' not in path.parts:
            hashes[str(path.relative_to(out))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (out / 'EVIDENCE_SHA256.json').write_text(json.dumps({'algorithm':'SHA256','scope':'Exact retained local evidence/source/archive bytes, excluding generated README/GATES and this manifest','files':hashes},indent=2) + '\n')
    print(json.dumps({'status': current['status'], 'source_heads': {key: row.get('source_head', row.get('published_head')) for key,row in current['tracks'].items()}, 'evidence_files':len(hashes)}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir',type=Path,default=Path(__file__).resolve().parent)
    build(parser.parse_args().out_dir)
