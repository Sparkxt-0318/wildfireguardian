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
    assert audit['track_head'] == b['source_head'] and audit['checks'] == audit['passed'] == b['checks'] == 57
    (out / 'GATES.json').write_text(json.dumps(current, indent=2, allow_nan=False) + '\n')
    text = f'''# Current next-track readiness

**[Draft readiness, PR 87]({current['publication']['integration_draft_pr']}). No combined scientific experiment has run, and no track code has been merged here.** A physics and supported risk-truth gates remain closed. B numerical evidence is pending; its software admission checks have scoped clearance. A passing implementation check is not a completed scientific study.

## Current track state

| Track and source | Reviewable evidence | Current acceptance |
|---|---|---|
| [1A radiation, PR 85]({a['draft_pr']}) at `{a['source_head'][:9]}` | Separate independent math review found no confirmed actionable defect within its declared domain; 42 fixed arithmetic sanity checks reported | 42 fresh functional tests and 367 copied-hash release checks pass, both exit 0. Physics HOLD; full journey/binding studies gated |
| [1B forecast, PR 88]({b['draft_pr']}) at `{b['published_head'][:9]}`; admission review `{b['source_head'][:9]}` | 57/57 assessment admission checks pass; separate 20-control adapter repair review passes; prospective wiring and coverage each 25/25 at 6c; actual numerical evidence pending | Scoped software clearance conditional on complete frozen final identities/selection. Numerical delivery and global-wind dependency review pending |
| [1C members, SIPP and truth, PR 86]({c['draft_pr']}) at `{c['published_head'][:9]}`; software `{c['software_head'][:9]}` | 52/52 native contact pairs match; 10,000 abstract comparisons; 15/15 export byte checks; repaired reader/core fixtures pass | Draft software reviewable; science HOLD_PARTIAL. 42,008 strict admission records contain zero scored risk cases |

The C publication head adds analysis/evidence only and leaves tested core software unchanged. The full saved-member census covers 1,024 members on each of 15 exact contact domains, 15,360 checks, with zero supported members under the current strict contact predicate. SIPP was slower in 4/52 native pairs. Its native panel covers 26 missions and 104 executions. The strong export method checks dtype, shape and payload/NPY bytes, including NaN bits; its historical weaker value-equality method remains retained.

## Cross-track checks

| Requested check | State | Reason |
|---|---|---|
| C1/C4, radiation v2 versus v1 | NOT_RUN_GATED | A physics/full-journey studies and supported C risk truth remain unresolved |
| Binding on coherent members, K=4 and K=16 | NOT_RUN_GATED | No accepted physics/binding study or supported multi-step coherence comparison |
| SIPP on combined bridge-v2 packets | NOT_RUN_GATED | Orchestrator Step 4 acceptance precondition is not met |
| Contact-only member-count scaling | NOT_RUN_CONTACT_ADMISSION | Every saved member on each audited domain has unknown cells; any nonempty selection fails current support admission before search |
| Native Caldor/Rim forecast exports | NOT_RUN_ALIGNMENT_UNESTABLISHED | Causal six-channel inputs, exact grids and compatible cutoff binding unestablished in bounded local evidence |

No pending rate or binding count is replaced by zero. No checkpoint is promoted. The logical future review order is exports/members, radiation library, forecasting, SIPP, truth harness, then integration; this is conditional review order and gives no instruction to merge the present drafts.

## Scientific claim changes

The radiation revision supports a conditional software/mathematical claim about its represented panels. Directed arithmetic and conservative geometric bounds replace the retained numerical counterexample; the independent reviewer reports point flux 5.844308577232327e-26 below upper 5.865954053640389e-25 kW/m2. This is not empirical validation or a machine-checked universal proof. The lower bound remains zero, a unit fallback remains outside the separation cone, whole-quad hull refinement need not converge, and adaptive precision has no uniform runtime/memory guarantee. An outer checker still needs a budget and an unresolved state. Literature geometry does not uniquely identify physical emitter parameters. No supported new routing-rejection, peak-binding or dose-binding count follows. The earlier f9 evidence and failures remain history. The separate 433 arithmetic sanity checks, fresh functional suite and source-integrity release check retain their distinct scopes; none is physical validation.

Forecasting has stronger input custody, source/reference binding and case-completion checks. The selected execution baselines must match frozen bytes; fresh and resumed scoring use independently rebuilt common support, and numerical failure cannot quietly remove cells. The 57 checks use tiny synthetic files and mocked numerical producers. They do not establish actual predictive performance, physical spread accuracy or corruption of real caches. Development selection uses fixed equal-fire Brier over 23 fit fires; its secondary cell-pooled summaries target a different estimand. The draft future protocol separately specifies pooled cell-interval Brier with a whole-fire bootstrap as its primary comparison. No heldout score was inspected by this readiness audit. Final numerical evidence, full identity/selection freeze and the dependency review remain pending.

Future 2026 testing is separately NOT_READY for external release, chronology and OSF gates. The historical a6d15519 review found symlink, trailing-DBF and nested-TGZ gaps; the separate 961fec6d recheck confirmed those mechanisms repaired but retained an optional quality-raster VRT gap that changed 54 valid feature entries to 45. The final d031b72b independent review passes 20 targeted controls, including ordinary pinned quality rasters/masks and specific refusals of unpinned quality/mask VRT dependencies. It gives scoped permission to wire the reviewed module, currently unwired at that source revision; subsequent wiring still needs source/pinning and software checks. The owner reports 74 tests passed, not rerun or pooled with the 20 controls here. These are bounded software checks, not a universal GDAL/filesystem proof or authentication of first-public-release completeness, exclusions, access chronology or OSF registration. No future data or registration action was taken. The retained 9b5eb72f failure concerned incomplete full-fit membership, not an asserted omission in actual fits. Its 6c586d52 repair passes the original 25 wiring controls and a separate 25 membership/schedule controls, with overlapping counts kept separate. Exact intended event and source-derived sample membership, effective last arguments, per-epoch counts/no-skips and new mixed runtime IDs now bind registry admission. Historical pure schedules remain explicitly source-derived inference, not retroactively logged IDs; a preserved-phase positive control and re-signed mislabel refusal pass. Raw inventory, terrain dependencies, bound human attestation and separate relocated final-review guards retain their scoped clearance. Actual final coverage/registry evidence, source-class/model and wind semantics, external documentary gates and superiority remain ungranted.

Coherent-member and SIPP evidence remains narrower than risk validation. All-member and k-of-m decisions preserve unknown mass; the copied full journey checker is a cell-centre surrogate and does not prove whole-road validity. The native SIPP panel is a contact relaxation, not a full thermal optimum or universal speedup. The all-N census closes the earlier first-K selector question for the saved inputs: all 1,024 members in each of 15 exact domains contain unknown cells, so every nonempty selected set fails the current whole-domain contact predicate, regardless of weights or later k-of-m acceptance. This is a contact admission limit, separate from radiation physics and full-policy truth gates. Readiness independently reconciled all saved CSV indices and counts plus one mask digest per domain; the owner separately compared original Boolean masks byte-for-byte. The historical 52-row counter table uses the original constructed members at K=4 only, uses distinct SIPP/sweep internal work units, and supplies neither a multi-K measured series nor the unproduced states-vs-members figure. No search/risk result is inferred from these admission records. Strict global-source completeness is a conservative admission policy, not proof that every local or pessimistic checker must fail. Its 42,008 unresolved records yield no false-safe/refusal rate. Missing-data policy must match across comparisons. Stored finite-run FARSITE nonarrival is right-censoring, never global nonignition; explicit bounded queries are required. Native no-argument usage establishes execution availability only, not a spread simulation.

The Caldor/Rim audit inventories 1,167 files and reports all 59 source-asset and 158 frozen-study digests matching their ledgers. This readiness pass verified report/inventory identities and internal counts, not every external file. The sealed packets are retrospective survey-gap timing constructions with assumed fire phases and scalar fuel parameters. Neither the bounded sealed tree nor the supplied 44-event catalog establishes native causal c651 inputs on the two grids; origins at 03:20 and 08:30 also miss the export contract's whole-hour cutoff. This does not claim aligned inputs cannot exist elsewhere. No forced alignment, resampling, forecast, thermal experiment or new physical/safety claim was made.

## Evidence, history and reproduction

- [Current machine-readable state](GATES.json) gives exact source heads, statuses, null counts and scope. [Evidence hashes](EVIDENCE_SHA256.json) bind retained local files.
- [Prior narrative, archived verbatim]({current['historical_evidence']['narrative']}) and [prior full gate ledger]({current['historical_evidence']['full_gate_ledger']}) preserve superseded stages. [Archive index](history/ARCHIVE_INDEX.json) records exact bytes. Every original failed audit JSON and producer script remains unchanged.
- [A fresh functional receipt]({a['functional_receipt']}) and [log/source inventory]({a['functional_inventory']}) record the orchestrator's independent 42-test and 367-hash passes. The canceled earlier queued attempt executed no checks and is not counted; test-run wall output is not performance evidence.
- [C full-member contact census]({c['contact_support_census']['review']}), [custody and CSV reconciliation]({c['contact_support_census']['inventory']}) and [fixed-K counter table]({c['K_scaling']['fixed_K_counter_table']}) retain the source-admission result separately from performance and risk evidence.
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

The saved B/C fixture commands exited 0 on native macOS arm64, Python 3.12.1 and NumPy 1.26.4; B uses Torch 2.5.1. Their elapsed times are not performance evidence. Original campaign seeds, commands and hosts remain in the linked historical ledger and receipts. Archived radiation/future-adapter scripts retain their original directory assumptions, documented in their source inventories; copying them alone into another folder is not a relocated replay. Report generation summarizes pinned files and runs no numerical study. Earlier remote Claude results remain reference material and are not counted as new executions.
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
