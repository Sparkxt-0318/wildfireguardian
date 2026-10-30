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
    assert audit.get('source_head', audit.get('track_head')) == b['source_head'] and audit['checks'] == audit['passed'] == b['checks']
    (out / 'GATES.json').write_text(json.dumps(current, indent=2, allow_nan=False) + '\n')
    text = f'''# Current next-track readiness

**[Draft readiness, PR 87]({current['publication']['integration_draft_pr']}). No combined scientific experiment has run, and no track code has been merged here.** A physics and supported risk-truth gates remain closed. B numerical evidence is pending; its development-recipe admission repair now has scoped independent clearance. Actual fit/selection/registry freeze remains pending; report-alias lookup has separate narrow clearance, while paired-ablation CI reporting has a new support-weight defect on HOLD. C has a completed, independently output-audited conditional contact study, which does not clear scientific integration. A passing implementation check is not a completed scientific study.

## Current track state

| Track and source | Reviewable evidence | Current acceptance |
|---|---|---|
| [1A radiation, PR 85]({a['draft_pr']}) at `{a['source_head'][:9]}` | Separate independent math review found no confirmed actionable defect within its declared domain; 42 fixed arithmetic sanity checks reported | 42 fresh functional tests and 367 copied-hash release checks pass, both exit 0. Physics HOLD; full journey/binding studies gated |
| [1B forecast, PR 88]({b['draft_pr']}) reviewed software `{b['source_head'][:9]}`; published `{b['published_head'][:9]}` | Independent development admission 23/23 and separate historical-skip 6/6 controls pass; parent 637 report-alias 2/2 passes. Earlier failures remain preserved | Scoped software admission passes; paired-ablation CI/reporting HOLD. Corrected fits and actual seven-fit coverage/selection/registry freeze remain pending; no heldout scoring |
| [1C members, SIPP and truth, PR 86]({c['draft_pr']}) current report `{c['current_report_head'][:9]}`; contact phase `{c['contact_campaign']['source_phase_head'][:9]}` | Conditional 320 records; independent output 22/22 and figure/boundary 5/5 checks pass. Earlier 52/52 native pairs, 10,000 abstract comparisons and 15/15 export byte checks remain separate | Conditional contact evidence reviewable. Strict whole-domain support remains 0/15,360; 42,008 risk-admission records contain zero scored risk cases |

C's new study uses original first-K 4/8/16/32 members on a declared known-footprint contact restriction, at measured source 095b8d174. It retains all 320 execution records: 48 completed-search pairs contain 36 matched arrivals and 12 matched restricted exhaustions; 224 unknown-endpoint records retain null solver costs. All 72 returned route records have separate original-data recheck receipts. The independent audit verifies saved receipts/control flow and does not replay geometric witnesses. The median SIPP/sweep planner ratio is 0.561111 across the 48 completed-search pairs, descriptive on the recorded macOS arm64 host. Earlier 52/52 native pairs and the new campaign are different panels. Prior reader/core software e681 remains a separate evidence pin.

The coordinator reports B's mixed final fit completed 3 epochs with 4,391 attempted IDs, 4,376 updates and 15 logged unsupported cases per epoch; 4,296 environment caches and 114 active sample lists rederived exactly, with 34 obsolete mixed caches retained/excluded. All three corrected spotting development fits are complete after the owner reported 3,259 regression tests passed. The corrected full spotting fit is queued behind the first fixed-source a06 comparison cutoff; 12 a06 cutoffs are required. Heldout scoring has not run. These are coordinator progress statements, not new readiness data/model inspections or current registry clearance.

## Cross-track checks

| Requested check | State | Reason |
|---|---|---|
| C1/C4, radiation v2 versus v1 | NOT_RUN_GATED | A physics/full-journey studies and supported C risk truth remain unresolved |
| Binding on coherent members, K=4 and K=16 | NOT_RUN_GATED | No accepted physics/binding study or supported multi-step coherence comparison |
| SIPP on combined bridge-v2 packets | NOT_RUN_GATED | Orchestrator Step 4 acceptance precondition is not met |
| Strict whole-domain contact K scaling | NOT_RUN_CONTACT_ADMISSION | Every saved member has unknown domain cells under the unchanged strict predicate |
| Known-footprint contact K study | COMPLETE_CONDITIONAL | 320 records at measured 095; independent output/figure review passes. Separate restricted contact problem, no full-policy/risk result |
| Native Caldor/Rim forecast exports | NOT_RUN_ALIGNMENT_UNESTABLISHED | Causal six-channel inputs, exact grids and compatible cutoff binding unestablished in bounded local evidence |

No pending rate or binding count is replaced by zero. No checkpoint is promoted. The logical future review order is exports/members, radiation library, forecasting, SIPP, truth harness, then integration; this is conditional review order and gives no instruction to merge the present drafts.

## Scientific claim changes

Radiation has a conditional software/mathematical argument for represented panels, with 42 fixed arithmetic checks, 42 fresh functional tests and 367 release hashes kept distinct. It remains unvalidated physics, not a machine-checked universal proof. The lower bound is zero, a unit fallback remains outside the separation cone, hull refinement need not converge, and adaptive precision needs an outer budget/unresolved outcome. Literature geometry does not uniquely identify physical emitter parameters. No new route-rejection, peak-binding or dose-binding count follows.

Forecast admission now binds source/reference bytes, exact ordered scoring cells, case completion and executed baselines. Fresh/resumed support checks refuse numerical trimming. The earlier 57 synthetic checks do not establish predictive performance or corruption of real caches. Development selection uses fixed equal-fire Brier over 23 fit fires; cell-pooled summaries estimate something different. At bbb, fixed development budgets/train/sample membership were incompletely bound. The separate a5ba independent review now passes 23 admission controls plus 6 historical-skip controls, with counts not pooled. Exact bounded source prefixes and recorded policy now bind admission; historical IDs remain source-derived inference. The historical spotting-alias failure is preserved; a separate adapted parent 637 control passes 2/2 name/gate checks with source-auth entry points and figures mocked. A separate independent metric review finds paired-ablation reporting can fabricate a difference when model support weights differ: equal Brier 0.1 with weights 100/50 yields -0.05 and a CI excluding zero. That reporting repair is on HOLD; training and equal-fire selection are unaffected. The exact failure is now archived alongside 51/51 passing nonablation arithmetic/gate controls. These do not clear paired-ablation reporting or establish actual forecast quality. No heldout score was inspected here and no checkpoint is promoted.

Future 2026 testing remains NOT_READY for external release, chronology, pre-access and OSF gates. The d03 adapter 20-control and 6c coverage/wiring 25-control passes retain bounded software scope; all earlier failures remain linked history. Historical pure fit schedules are source-derived inference, not retroactive runtime IDs. New mixed accounting binds actual attempted IDs and explicit source-supported skips under the preexisting policy, without inventing optimizer masks. A bound human documentary attestation checks local evidence identity and declared procedure; software does not authenticate external truth or independence.

C's new known-footprint study changes the contact evidence while preserving the strict negative result. All 1,024 members on each of 15 domains still contain unknown cells; 0/15,360 satisfy whole-domain support. The separate adapter permits only represented contact paths with known occupied sources and finite clocks. Three original API defects remain preserved; parent 700 repair evidence passes 17 tiny controls, 65 custody checks and 72 targeted tests, not pooled or rerun here. The 320-record campaign uses 20 original missions, K=4/8/16/32, two methods and two verification repeats. It retains 48 completed-search pairs, 36 matched arrivals, 12 matched restricted exhaustions and 224 unknown-endpoint records with null solver costs. All 72 returned route records have separate raw-data recheck receipts. The independent 22+5 output/figure audit verifies those saved receipts/control flow and hashes 339 outputs, 115 actual inputs and 41 source/evidence pins; it does not replay geometric witnesses. Initial audit assumption failures remain harness history.

Median planner ratio 0.561111 and complete-child ratio 0.671574 are descriptive paired host measurements, not universal speedups. Repeats are not independent fires; K=32 loses two previously returned routes. Different solver work units stay in separate panels. The represented source uses seed 20261008, H=3600 s and T=3970.4642815 s, so increasing interval fragmentation is not implied. Sampled/final resource controls are not an instantaneous OS cap. Conditional optimality applies only to the known-footprint contact problem; restricted exhaustion is unresolved about the original unknown domain. Full-policy, peak, dose, physical safety and risk remain unknown. The 42,008 strict risk-admission records still identify no false-safe/refusal rate. The copied full journey checker remains a cell-centre surrogate. Finite-run FARSITE nonarrival remains right-censoring; native usage availability is not a spread simulation. A physics HOLD still gates Step 4.

The Caldor/Rim report inventories 1,167 files and reports 59 source-asset and 158 study-ledger digest matches; readiness verified report custody, not every external file. Those packets are retrospective constructions with assumed phases/fuel parameters. Native causal c651 inputs, exact grids and compatible cutoff binding remain unestablished. No forced alignment, resampling, forecast, thermal experiment or new physical claim followed.

## Evidence, history and reproduction

- [Current machine-readable state](GATES.json) gives exact source heads, statuses, null counts and scope. [Evidence hashes](EVIDENCE_SHA256.json) bind retained local files.
- [Immediately preceding bbb HOLD summary]({current['historical_evidence']['pre_contact_campaign_summary']}) is archived verbatim before the separate parent repair and contact-study updates.
- [Prior narrative, archived verbatim]({current['historical_evidence']['narrative']}) and [prior full gate ledger]({current['historical_evidence']['full_gate_ledger']}) preserve superseded stages. [Archive index](history/ARCHIVE_INDEX.json) records exact bytes. Every original failed audit JSON and producer script remains unchanged.
- [A fresh functional receipt]({a['functional_receipt']}) and [log/source inventory]({a['functional_inventory']}) record the orchestrator's independent 42-test and 367-hash passes. The canceled earlier queued attempt executed no checks and is not counted; test-run wall output is not performance evidence.
- [C full-member contact census]({c['contact_support_census']['review']}), [custody and CSV reconciliation]({c['contact_support_census']['inventory']}) and [fixed-K counter table]({c['K_scaling']['fixed_K_counter_table']}) retain the source-admission result separately from performance and risk evidence.
- [C conditional contact evidence]({c['contact_campaign']['evidence']}) and [independent output/figure review]({c['contact_campaign']['independent_review']}) retain 320 records and exact original/audit custody. [Parent 700 adapter repair inventory]({c['contact_adapter_repair']['inventory']}) preserves all original failed fixtures and later scoped passes; no reruns here.
- [Independent B metric/report review]({b['paired_ablation_reporting']['review']}) preserves the unequal-support false-CI reproduction and 51/51 nonablation arithmetic/gate controls. Paired-ablation reporting remains HOLD; actual study quality results were unread. [Pre-metrics current summary]({current['historical_evidence']['pre_metrics_summary']}) remains archived verbatim.
- [B current development-admission repair review]({b['current_development_admission']['review']}) records the independent 23/23 and separate 6/6 synthetic controls; [exact archive inventory]({b['current_development_admission']['inventory']}) preserves source/report/producer custody. No new readiness rerun or actual study-data audit occurred.
- [B report-alias repair]({b['current_report_alias_repair']['review']}) records the parent's adapted 2/2 name/gate checks, with new source-auth/figure mocks stated explicitly.
- [Current B source/phase/support review]({b['source_phase_review']['review']}) retains the 30/26 main audit, separate base-positive/spotting-failure report control 1/2 and 6 reused owner compatibility controls. The historical two findings remain unchanged; report-alias lookup has a separate parent 637 repair pass, and development admission has a separate a5ba scoped pass. Overlapping counts are not summed.
- [Prospective wiring/registry review]({b['prospective_wiring_review']['review']}) records the separate passing coverage/wiring suites; [original 9b failure]({b['prospective_wiring_initial_review']['review']}) and exact reproduction remain retained. Source a6 remains the earlier assessment-admission authority.
- [Historical future-adapter review]({b['future_adapter_initial_review']}) and [intermediate quality-gap review]({b['future_adapter_repair_history']['961fec6d']['review']}) preserve all failed stages; [final repair source inventory]({b['future_adapter_inventory']}) records exact source and file digests.
- [B scoped repair audit]({b['review']}), [independent radiation review]({a['review']}), [C alignment audit]({c['alignment_review']}) and [final future-adapter repair review]({b['future_adapter_review']}) distinguish our executions from archived reviewer/owner evidence.

From the integration worktree, these commands use the prepared pinned environments. Use new output paths for fixture reruns:

```sh
../venv-routing/bin/python research/next-combined/build_report.py
../venv-forecast/bin/python research/next-combined/audit_1b_final_admission.py --track-b ../audit-1b --out research/next-combined/audit/FRESH_B.json
../venv-routing/bin/python research/next-combined/audit_1c_readers.py --track-c ../audit-1c --out research/next-combined/audit/FRESH_C_READERS.json
../venv-routing/bin/python research/next-combined/audit_1c_semantics.py --track-c ../audit-1c --out research/next-combined/audit/FRESH_C_CORE.json
```

The saved earlier a6/e681 B/C fixture commands exited 0 at their pinned source heads on native macOS arm64, Python 3.12.1 and NumPy 1.26.4; B uses Torch 2.5.1. Their elapsed times are not performance evidence. Original campaign seeds, commands and hosts remain in the linked historical ledger and receipts. Archived radiation/future-adapter scripts retain their original directory assumptions, documented in their source inventories; copying them alone into another folder is not a relocated replay. Report generation summarizes pinned files and runs no numerical study. Earlier remote Claude results remain reference material and are not counted as new executions.
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
