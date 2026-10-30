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
        assert row['state'] in ('NOT_RUN_GATED', 'NOT_RUN_ALIGNMENT_UNESTABLISHED'), name
    a, b, c = (current['tracks'][key] for key in ('1A', '1B', '1C'))
    audit = json.loads((out / b['review']).read_text())
    assert audit['track_head'] == b['source_head'] and audit['checks'] == audit['passed'] == b['checks'] == 57
    (out / 'GATES.json').write_text(json.dumps(current, indent=2, allow_nan=False) + '\n')
    text = f'''# Current next-track readiness

**Draft readiness only. No combined scientific experiment has run, and no track code has been merged here.** A physics and supported risk-truth gates remain closed. B numerical evidence is pending; its software admission checks have scoped clearance. A passing implementation check is not a completed scientific study.

## Current track state

| Track and source | Reviewable evidence | Current acceptance |
|---|---|---|
| [1A radiation, PR 85]({a['draft_pr']}) at `{a['source_head'][:9]}` | Separate independent math review found no confirmed actionable defect within its declared domain; 42 fixed arithmetic sanity checks reported | Physics HOLD. Orchestrator's fresh 42-test suite pending; full journey/binding studies gated |
| 1B forecast at `{b['source_head'][:9]}` | 57/57 independent synthetic admission checks pass, with valid controls before refusals | Scoped software clearance conditional on complete frozen final identities/selection. Numerical delivery and global-wind dependency review pending |
| [1C members, SIPP and truth, PR 86]({c['draft_pr']}) at `{c['published_head'][:9]}`; software `{c['software_head'][:9]}` | 52/52 native contact pairs match; 10,000 abstract comparisons; 15/15 export byte checks; repaired reader/core fixtures pass | Draft software reviewable; science HOLD_PARTIAL. 42,008 strict admission records contain zero scored risk cases |

The C publication head adds four owned reports and leaves tested software unchanged. SIPP was slower in 4/52 native pairs. Its native panel covers 26 missions and 104 executions. The strong export method checks dtype, shape and payload/NPY bytes, including NaN bits; its historical weaker value-equality method remains retained.

## Cross-track checks

| Requested check | State | Reason |
|---|---|---|
| C1/C4, radiation v2 versus v1 | NOT_RUN_GATED | A physics/full-journey studies and supported C risk truth remain unresolved |
| Binding on coherent members, K=4 and K=16 | NOT_RUN_GATED | No accepted physics/binding study or supported multi-step coherence comparison |
| SIPP on combined bridge-v2 packets | NOT_RUN_GATED | Orchestrator Step 4 acceptance precondition is not met |
| Native Caldor/Rim forecast exports | NOT_RUN_ALIGNMENT_UNESTABLISHED | Causal six-channel inputs, exact grids and compatible cutoff binding unestablished in bounded local evidence |

No pending rate or binding count is replaced by zero. No checkpoint is promoted. The logical future review order is exports/members, radiation library, forecasting, SIPP, truth harness, then integration; this is conditional review order and gives no instruction to merge the present drafts.

## Scientific claim changes

The radiation revision supports a conditional software/mathematical claim about its represented panels. Directed arithmetic and conservative geometric bounds replace the retained numerical counterexample; the independent reviewer reports point flux 5.844308577232327e-26 below upper 5.865954053640389e-25 kW/m2. This is not empirical validation or a machine-checked universal proof. The lower bound remains zero, a unit fallback remains outside the separation cone, whole-quad hull refinement need not converge, and adaptive precision has no uniform runtime/memory guarantee. An outer checker still needs a budget and an unresolved state. Literature geometry does not uniquely identify physical emitter parameters. No supported new routing-rejection, peak-binding or dose-binding count follows. The earlier f9 evidence and failures remain history; the separate 433 math review does not silently substitute for the queued fresh unit suite.

Forecasting has stronger input custody, source/reference binding and case-completion checks. The selected execution baselines must match frozen bytes; fresh and resumed scoring use independently rebuilt common support, and numerical failure cannot quietly remove cells. The 57 checks use tiny synthetic files and mocked numerical producers. They do not establish actual predictive performance, physical spread accuracy or corruption of real caches. Development selection uses fixed equal-fire Brier over 23 fit fires; its secondary cell-pooled summaries target a different estimand. The draft future protocol separately specifies pooled cell-interval Brier with a whole-fire bootstrap as its primary comparison. No heldout score was inspected by this readiness audit. Final numerical evidence, full identity/selection freeze and the dependency review remain pending.

Future 2026 testing is separately NOT_READY. The independent inventory review at a6d15519 confirms three software gaps: directory symlinks bypass environmental pinning, trailing DBF records can be ignored, and a nested TGZ can hide an unenumerated incident. The adapter is unwired and its owner is repairing it. A derived catalog, successful software check or supplied OSF URL cannot authenticate a complete first public raw release, exclusions, publication/access chronology or external registration. No future data or registration action was taken.

Coherent-member and SIPP evidence remains narrower than risk validation. All-member and k-of-m decisions preserve unknown mass; the copied full journey checker is a cell-centre surrogate and does not prove whole-road validity. The native SIPP panel is a contact relaxation, not a full thermal optimum or universal speedup. Strict global-source completeness is a conservative admission policy, not proof that every local or pessimistic checker must fail. Its 42,008 unresolved records yield no false-safe/refusal rate. Missing-data policy must match across comparisons. Stored finite-run FARSITE nonarrival is right-censoring, never global nonignition; explicit bounded queries are required. Native no-argument usage establishes execution availability only, not a spread simulation.

The Caldor/Rim audit inventories 1,167 files and reports all 59 source-asset and 158 frozen-study digests matching their ledgers. This readiness pass verified report/inventory identities and internal counts, not every external file. The sealed packets are retrospective survey-gap timing constructions with assumed fire phases and scalar fuel parameters. Neither the bounded sealed tree nor the supplied 44-event catalog establishes native causal c651 inputs on the two grids; origins at 03:20 and 08:30 also miss the export contract's whole-hour cutoff. This does not claim aligned inputs cannot exist elsewhere. No forced alignment, resampling, forecast, thermal experiment or new physical/safety claim was made.

## Evidence, history and reproduction

- [Current machine-readable state](GATES.json) gives exact source heads, statuses, null counts and scope. [Evidence hashes](EVIDENCE_SHA256.json) bind retained local files.
- [Prior narrative, archived verbatim]({current['historical_evidence']['narrative']}) and [prior full gate ledger]({current['historical_evidence']['full_gate_ledger']}) preserve superseded stages. [Archive index](history/ARCHIVE_INDEX.json) records exact bytes. Every original failed audit JSON and producer script remains unchanged.
- [B scoped repair audit]({b['review']}), [independent radiation review]({a['review']}), [C alignment audit]({c['alignment_review']}) and [future-adapter review]({b['future_adapter_review']}) distinguish our executions from archived reviewer/owner evidence.

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
