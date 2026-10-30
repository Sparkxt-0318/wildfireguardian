# Next research tracks, execution plan

Base: fetched origin/Main at 8670e350b845db94a17df4c5448f2af515fc0feb (2026-10-30, Asia/Shanghai).

Tracks: 1A flame-front radiation, 1B forecast upgrades, 1C coherent members, SIPP and synthetic truth. Track 1D is archived as a supplied prompt only; it is outside the requested execution.

## Ownership table (files a track may create or modify; everything else is read-only for that track)

- 1A: `experimental/flame-front-radiation/**`, `research/flame-front-radiation/**`, `docs/RADIATION_LAW_V2.md`, and a test-only adapter under `experimental/flame-front-radiation/adapters/` that plugs law v2 into a copy of the journey checker for evaluation. 1A never edits `integration/**` or `forecast/**`.
- 1B: `forecast/wildfire/meanfield.py`, `forecast/wildfire/survival.py`, `forecast/wildfire/canonical.py`, `forecast/wildfire/burnout.py`, `forecast/wildfire/baselines.py`, additive classes in `forecast/wildfire/models.py`, additive CLI options in `forecast/wildfire/train.py` and `forecast/wildfire/evaluate.py`, new tests under `forecast/tests/`, a new run directory `forecast/runs/<date>_perimeter_trained/`, `forecast/documents/preregistration_blind_test.md`, and `research/forecast-v2/**`. 1B never edits `forecast/wildfire/rollout.py`, `integration/**` or the c651 checkpoint path.
- 1C: `experimental/sipp-routing/**`, `experimental/scenario-members/**`, `experimental/synthetic-truth/**`, `research/sipp-routing/**`, `research/scenario-members/**`, `research/synthetic-truth/**`, `integration/src/wfg_latest/export.py` (v3 additive), the single `trajectory_callback` kwarg in `forecast/wildfire/rollout.py`, and a new bridge module `experimental/scenario-members/bridge_v2.py` that imports but does not modify `integration/src/wfg_latest/bridge.py`.
- Orchestrator only: `docs/NEXT_INTERFACES.md` (this file), `docs/NEXT_PLAN.md`, final merge and the combined evidence README.


## Coordination decisions

- The orchestrator owns this log; agents report deliverable updates by message. This resolves the conflicting request for agents to edit an orchestrator-only file.
- Four pull requests total: 1A, 1B, 1C and integration, following the orchestrator instruction over 1C's request for three PRs. Each 1C deliverable remains separately tracked below.
- The 1C proof and predicate documents live under experimental/sipp-routing/docs/, because root docs paths are absent from its explicit ownership allowance.
- Track diffs against Main include inherited contract/plan commits. Ownership checks examine each track's unique delta from the common orchestrator base, and separately enumerate inherited orchestrator files.
- No GitHub PR merges. Merging passed branches into a local integration worktree is authorized by step 4, conditional on acceptance gates. No default checkpoint promotion.
- Use available collaboration/worktree tools in place of Claude-specific task and messaging tool names.

## Recommended merge order

1C-1 export and members, 1A library, 1B, 1C-2 SIPP, 1C-3 harness, integration. Preserve this logical order when reviewing the single 1C PR.

## Acceptance gates

- Fresh pinned environments: Python 3.12 and constraints-routing.txt with ./integration[packets] for routing; the pinned forecast environment for 1B. Record commands and exits.
- Track suites pass. Rollout default byte-identical; v2 exports unchanged unless v3 requested. No frozen kit or checkpoint edits.
- Headline evidence has producing scripts, seeds, hashes, host and Scope and limits. Missing data or failed gates are explicit, never success.
- Review README uses of validated, proves, guarantees and safe. No field or universal speed claims.
- No em dashes in new prose, comments, labels or commit messages. Supplied prompts are preserved byte-for-byte as requested.
- Figures: 300 dpi PNG and SVG, captions and shared style.
- Ownership diff for each track, exact callback-only rollout diff, additive export/forecast changes.

## Tasks

| ID | Deliverable | Status |
|---|---|---|
| 1A-1 | Radiation library | pending |
| 1A-2 | Physics comparisons | pending |
| 1A-3 | Binding statistics | pending |
| 1B-1 | Differentiable mean field | pending |
| 1B-2 | Survival training | pending |
| 1B-3 | Structural ablations | pending |
| 1B-4 | Baselines | pending |
| 1B-5 | Blind pre-registration | pending |
| 1C-1 | Export v3, members and reduction | pending |
| 1C-2 | SIPP equivalence and cost | pending |
| 1C-3 | Synthetic-truth harness and campaigns | pending |
| INT | Integration checks | pending, gated on track acceptance |
| EVIDENCE | Combined evidence README | pending |
| PR | Four pull requests opened | pending |

## Progress log

- 2026-10-30: Verified repository identity and case-sensitive Main. Fetched remote Main; existing checkouts and branches preserved. Copied all six supplied documents, with canonical prompt names, and identical shared interfaces into docs/NEXT_INTERFACES.md.
