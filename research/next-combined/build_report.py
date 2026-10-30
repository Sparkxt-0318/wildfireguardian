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
    assert b['actual_fit_coverage']['actual_result_checker'] == 'NOT_RUN'
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
    assert not b['current_cohort_execution']['results_read_by_readiness'] and not b['freeze_process']['future2026_inference_authorized']
    assert b['current_census_preparation']['synthetic_passed'] == 34 and b['current_census_preparation']['actual'] == 'NOT_RUN'
    assert not b['driver_static_review']['actual_driver_replay']
    assert b['wapiti_integrity']['cases'] == 52 and not b['wapiti_integrity']['prediction_or_source_arrays_copied_by_readiness']
    (out / 'GATES.json').write_text(json.dumps(current, indent=2, allow_nan=False) + '\n')
    closure = json.loads((out / b['current_cohort_execution']['closure']['root_check']).read_text())
    assert closure['all223_frozen_files_match'] and all(closure['receipt_log_identity_checks'].values())
    progress = closure['last_metadata_monitor']['progress']
    assert progress['us2024']['statuses'] == {'SCORED': 273}
    assert progress['korea2025']['statuses'] == {'SCORED': 26, 'UNAVAILABLE': 7}
    assert b['current_cohort_execution']['state'] == 'BOTH_ORIGINAL_COHORTS_CLOSED_CUSTODY_PASS_RESULTS_UNREAD'
    assert b['descriptive_intervals']['actual_computation'] == 'NOT_AUTHORIZED_NOT_RUN'
    assert not b['descriptive_intervals']['source_review_is_candidate_implementation_review']
    text = f'''# Current next-track readiness

**[Draft readiness, PR 87]({current['publication']['integration_draft_pr']}). Both original forecast cohorts have closed; exact full-case census and quality review remain pending.** The verified 6887 freeze remains cleared and published. No track code has been merged here. A physics HOLD and C support/risk limitations keep orchestrator Step 4 **NOT_RUN_GATED**. No default promotion or future 2026 execution is cleared.

## Current track state

| Track and pinned source | Reviewable evidence | Current acceptance |
|---|---|---|
| [1A radiation, PR 85]({a['draft_pr']}) `{a['source_head'][:9]}` | Scoped independent mathematics review; 42 fixed arithmetic checks; separate 42 fresh functional tests and 367 release hashes, exit 0 | Mathematical/software evidence only. Physics HOLD; full journey, peak/dose binding and route-rejection counts remain gated/null |
| [1B forecast, PR 88]({b['draft_pr']}) freeze `{b['source_head'][:9]}`; software `{b['current_software_head'][:9]}` | 3,507 owner software tests plus 367 release hashes, exit 0; canonical software/membership pass over 21 development and seven final phases; verified selection/protocol/registry published | Both original cohorts closed: US 273 SCORED, exit 0; KR 26 SCORED + 7 UNAVAILABLE, exit 1/HOLD. Root custody check passes. Exact 306-case identity census, metrics, FARSITE and final five figures pending; no quality conclusion |
| [1C members/SIPP/truth, PR 86]({c['draft_pr']}) report `{c['current_report_head'][:9]}`; contact phase `{c['contact_campaign']['source_phase_head'][:9]}` | Conditional 320-record contact study; independent output 22/22 and figure/boundary 5/5 checks | Restricted contact evidence only. Strict support remains 0/15,360; 42,008 risk-admission records contain zero scored risk cases |

The [closed root custody record]({b['current_cohort_execution']['closure']['root_check']}) checks four execution receipt/log identities and all 223 frozen current bytes at 23:04:26 UTC. Root reports US closure at 18:02:45.555747 UTC and separate KR closure at 18:14:29.641685 UTC on October 30. The outer exit is 1, with no reported source/custody failure. Counts come from saved metadata; they do not replace the pending exact-case census. Readiness copied no actual case JSON, execution log, prediction/source array or model, and read no quality values. Earlier partial progress snapshots remain historical in GATES/history.

## Cross-track checks

| Requested check | State | Reason |
|---|---|---|
| C1/C4, radiation v2 versus v1 | NOT_RUN_GATED | A physics/full-journey acceptance and supported C risk truth remain unresolved |
| Binding on coherent members, K=4 and K=16 | NOT_RUN_GATED | No accepted physics/binding or supported multi-step coherence comparison |
| SIPP on combined bridge-v2 packets | NOT_RUN_GATED | Orchestrator Step 4 acceptance precondition is unmet |
| Strict whole-domain contact K scaling | NOT_RUN_CONTACT_ADMISSION | Every saved member has unknown domain cells under the strict predicate |
| Known-footprint contact K study | COMPLETE_CONDITIONAL | Restricted contact problem completed; no full-policy/risk result |
| Native Caldor/Rim forecast exports | NOT_RUN_ALIGNMENT_UNESTABLISHED | Causal six-channel inputs, exact grids and cutoff binding unestablished |

## Scientific claim changes

**Radiation.** The represented-panel model now has a scoped conditional mathematical/software argument, supported by separate fixed arithmetic and functional checks. This is not physical validation or a machine-checked universal proof. Its zero lower bound, fallback outside the separation cone, possible hull-refinement nonconvergence and outer precision/budget requirement limit use. Literature geometry does not uniquely identify physical emitter parameters. No empirical route-rejection or peak/dose-binding count follows. [Full mathematics review]({a['review']}).

**Forecast admission and results.** Source/reference bytes, ordered scoring cells, complete fit membership, baseline execution and selection/registry identities have separate scoped passes. The 9,841 canonical bookkeeping predicates are correlated metadata/custody checks, not scientific samples or a replay of cache values, arrays or models. Historical pure-fit schedules remain source-derived; mixed final records 4,391 attempts, 4,376 updates and 15 logged skips per epoch. Fixed equal-fire development selection chose d4_wind; its mean-fire Brier 0.0374951161 and pooled own-support Brier 0.0408148207 estimate different quantities. Both current cohorts have now closed, but the exact 306-case census and canonical quality review are pending. Seven unavailable Korean windows prevent a complete-cohort Korean result; the available 26 must not be substituted. [Admission and freeze evidence]({b['freeze_process']['independent_review']}).

**Intervals.** Frozen source provides paired pooled Brier and pooled SSE-ratio BSS intervals, while absolute pooled raw Brier, AP, ROC AUC, fixed-bin ECE and clipped NLL lack their own intervals. Existing BSS intervals omit and count zero-reference-SSE draws, so any such interval is conditional on defined denominators. The separate future blind scorer supplies BSS points through a different path. A descriptive supplement method was fixed at 17:10 UTC before final quality interpretation, without changing primary rules or the 223 frozen files. The source-only review and invented arithmetic controls support that proposal; they do not clear its candidate implementation. Actual computation remains **NOT_AUTHORIZED** until canonical b3f/census prerequisites, implementation review and root authorization. The Korean complete-cohort supplement must stay null/unavailable, with no available-26 bootstrap. [Method and exact prerequisites]({b['descriptive_intervals']['protocol']}); [source-only review]({b['descriptive_intervals']['source_review']}).

**Comparison and contact.** The 12-cutoff/66-row MF/MC reconciliation validates saved summaries, retaining 56 comparable and 10 unavailable rows. Unsaved per-cell errors/masks, MC correctness, physical accuracy and speed superiority are unverified. C's 320 records are a separate known-footprint contact problem: 48 completed-search pairs contain 36 matched arrivals and 12 restricted exhaustions; 224 unknown-endpoint records retain null costs. All 72 returned-route records have saved original-data recheck receipts, but the independent output audit did not replay geometric witnesses. Median SIPP/sweep planner ratio 0.561111 is descriptive on the recorded macOS arm64 host. Repeats are not independent fires; K=32 loses two earlier returns. Strict support remains 0/15,360. Full-policy, physical safety and false-safe/refusal rates remain unresolved. [Conditional contact review]({c['contact_campaign']['independent_review']}).

External 2026 release chronology/registration remains NOT_READY. Finite-run nonarrival is censoring; native FARSITE usage availability is not a spread simulation. Caldor/Rim packet custody does not establish causal forecast alignment. All original failures and prior remote Claude reference results retain their original scopes.

## Evidence, history and reproduction

[GATES.json](GATES.json) retains exact heads, separate scope/count/status fields and null outcomes; [EVIDENCE_SHA256.json](EVIDENCE_SHA256.json) binds retained evidence. [The immediately prior summary]({current['historical_evidence']['pre_cohort_closure_summary']}) is archived verbatim with its [index]({current['historical_evidence']['pre_cohort_closure_inventory']}). Detailed earlier audit material remains in that narrative and the [original history index](history/ARCHIVE_INDEX.json); no failed record was replaced.

| Evidence and custody | Scope retained |
|---|---|
| [A functional receipt]({a['functional_receipt']}) and [source/log inventory]({a['functional_inventory']}) | Parent execution, no timing-performance inference |
| [Canonical independent coverage]({b['canonical_independent_review']['review']}) and [freeze bytes]({b['freeze_process']['parent_inventory']}) | Saved metadata/custody versus historical runtime attestation remain distinct; overlapping source/checkpoint/dependency maps are not summed |
| [Closed cohorts]({b['current_cohort_execution']['closure']['inventory']}) and [original current-only authorization]({b['current_cohort_execution']['inventory']}) | 273 US + 33 KR authorized; process closure/counts are not full-case identity or quality validation |
| [Prepared 306-case census]({b['current_census_preparation']['inventory']}) and [prepared metric checker]({b['prepared_final_result_checker']['inventory']}) | Separate 34 and 38 synthetic-control packages; actual final reviews pending |
| [Interval source inventory]({b['descriptive_intervals']['source_review_inventory']}) and [fixed method/prerequisites]({b['descriptive_intervals']['protocol_inventory']}) | 19 original manifest entries and nine frozen Git sources verified. Saved invented controls are overlapping comparisons, not study samples; no candidate or actual-output review |
| [Wapiti artifact integrity]({b['wapiti_integrity']['alignment_review']}) and [mapped-label linkage]({b['wapiti_integrity']['source_label_review']}) | Same 52 cases; no quality, physical truth, common-validity or prediction-replay claim |
| [Actual MF/MC reconciliation]({b['mfmc_actual_reconciliation']['inventory']}) | Original F175 producer/contract; live F65 applied afterward; no raw-field replay |
| [C contact study]({c['contact_campaign']['evidence']}) and [strict support census]({c['contact_support_census']['inventory']}) | Conditional and strict outcomes kept separate; no full-policy/risk promotion |

The source-only interval controls retain 12 invented estimand checks, 994 cached-AP/literal comparisons, 978 defined sklearn comparisons, 16 null vectors, 1,988 paired-AP comparisons, seven diagnostic draws and three boundary controls. These overlap and are not pooled. The fixed supplement uses 10,000 whole-fire draws at seed 20261030, separately per cohort, and retains null/undefined draws. Its implementation and actual execution are not cleared by these controls.

From this integration worktree, regenerate only the readiness summary and hashes:

```sh
../venv-routing/bin/python research/next-combined/build_report.py
```

Original commands, exits, seeds, host/dependency versions and source hashes remain in the linked exact receipts and inventories. Prior tiny fixtures used native macOS arm64, Python 3.12.1 and NumPy 1.26.4; saved interval controls additionally report sklearn 1.5.2. C's represented contact source uses seed 20261008. The MF/MC checker ran under original F175; its old live-path command cannot be replayed against changed sources as the same phase. No fixture/study is rerun for this archive, and reported elapsed times do not establish performance. Review order remains exports/members, radiation library, forecasting, SIPP, truth harness, then integration, conditional on gates. No merge is requested.
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
