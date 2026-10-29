# Next tracks: orchestration plan and progress log

This is the record the human reads first. It is maintained by the orchestrator only. Contracts are in `docs/NEXT_INTERFACES.md`; the track prompts are in `docs/next/prompts/`.

## Tracks

| Track | Prompt | Working branch | Pull request title |
|---|---|---|---|
| 1A flame-front radiation law v2 | `docs/next/prompts/01A_flame_front_radiation.md` | `track/1a-flame-front-radiation` | Track 1A: flame-front radiation law v2 (opt-in library, physics validation, binding statistics) |
| 1B forecast upgrades | `docs/next/prompts/01B_forecast_upgrades.md` | `track/1b-forecast-v2` | Track 1B: perimeter-trained differentiable forecast with structural ablations and a pre-registered blind protocol |
| 1C routing v2 | `docs/next/prompts/01C_routing_members_sipp_validation.md` | `track/1c-routing-v2` (split at PR time into `track/1c-1-members`, `track/1c-2-sipp`, `track/1c-3-synthetic-truth`) | Track 1C-1: trajectory members and scenario reduction; Track 1C-2: SIPP relaxation with equivalence proof and cost study; Track 1C-3: synthetic-truth validation harness (OSSE) |
| Integration | Step 4 of `docs/next/prompts/00_ORCHESTRATOR_multi_agent.md` | `next/integration` | Next: combined evidence for radiation law v2, trajectory members, SIPP and synthetic-truth validation |

Deliverables tracked: 1A-1 library, 1A-2 physics validation, 1A-3 binding statistics, 1B-1 mean field, 1B-2 survival training, 1B-3 structural ablations, 1B-4 baselines, 1B-5 pre-registration, 1C-1 members, 1C-2 SIPP, 1C-3 synthetic truth, integration checks, combined evidence README, pull requests opened.

## Ownership tables (verbatim from docs/NEXT_INTERFACES.md)

- 1A: `experimental/flame-front-radiation/**`, `research/flame-front-radiation/**`, `docs/RADIATION_LAW_V2.md`, and a test-only adapter under `experimental/flame-front-radiation/adapters/` that plugs law v2 into a copy of the journey checker for evaluation. 1A never edits `integration/**` or `forecast/**`.
- 1B: `forecast/wildfire/meanfield.py`, `forecast/wildfire/survival.py`, `forecast/wildfire/canonical.py`, `forecast/wildfire/burnout.py`, `forecast/wildfire/baselines.py`, additive classes in `forecast/wildfire/models.py`, additive CLI options in `forecast/wildfire/train.py` and `forecast/wildfire/evaluate.py`, new tests under `forecast/tests/`, a new run directory `forecast/runs/<date>_perimeter_trained/`, `forecast/documents/preregistration_blind_test.md`, and `research/forecast-v2/**`. 1B never edits `forecast/wildfire/rollout.py`, `integration/**` or the c651 checkpoint path.
- 1C: `experimental/sipp-routing/**`, `experimental/scenario-members/**`, `experimental/synthetic-truth/**`, `research/sipp-routing/**`, `research/scenario-members/**`, `research/synthetic-truth/**`, `integration/src/wfg_latest/export.py` (v3 additive), the single `trajectory_callback` kwarg in `forecast/wildfire/rollout.py`, and a new bridge module `experimental/scenario-members/bridge_v2.py` that imports but does not modify `integration/src/wfg_latest/bridge.py`.
- Orchestrator only: `docs/NEXT_INTERFACES.md` (this file), `docs/NEXT_PLAN.md`, final merge and the combined evidence README.

The track prompts also name a few documents inside each track's scope (1C: `docs/SIPP_EQUIVALENCE.md`, `docs/JOURNEY_SAFETY_PREDICATE.md`; 1A: `docs/RADIATION_LAW_V2.md`). The orchestrator treats those named files as owned by the track whose prompt names them.

## Orchestrator decisions (recorded before launch)

- D1. `integration/src/wfg_latest/export.py` is hash-pinned in `docs/PUBLICATION_SOURCE_MANIFEST.json` and checked by `tools/verify_release.py` in the required `Research release integrity` workflow. Editing it would turn the release check red, and the manifest is owned by no track. Track 1C is therefore told to implement export v3 as an additive overlay `experimental/scenario-members/export_v3.py` that imports the v2 export and leaves `export.py` byte-identical. Contract A field names and semantics are unchanged. If the human prefers the in-place edit plus a manifest refresh, this is reversible.
- D2. `forecast/PUBLICATION_MANIFEST.json` records hashes of `forecast/wildfire/rollout.py`, `models.py`, `train.py` and `evaluate.py`. It is not checked by CI and no track owns it, so it is not updated; each track README that changes one of those files must say that the manifest describes the released snapshot.
- D3. Execution host: a Linux cloud container, 4 vCPU, 15 GiB RAM, no GPU. The frozen protocol was measured on native macOS. Every timing number from this run is host-specific and must say so; it is not comparable as a speedup with the frozen Mac numbers. The three tracks share the host, so each track limits itself to at most 2 compute threads for heavy work and records the load conditions.
- D4. Data that is not in the repository: the Caldor/Rim sealed-study packets (recorded at absolute paths on the owner's Mac), the forecast training and environmental rasters (`--data-root`), and FARSITE. Until the human answers, tracks run on the public Korean inputs (`tools/fetch_routing_inputs.py`), the Zenodo and Mendeley archives already referenced in `forecast/data/source_manifest.json` and `forecast/wildfire/observed_data.py` (hash and licence recorded), and state plainly what was not run.
- D6. Progress lines: tracks append to `research/<track>/PROGRESS.md` on their own branch and message the orchestrator, which copies the line here. This avoids three branches editing this orchestrator-owned file.
- D5. Track 1C works on one branch and the orchestrator splits it into three PR branches by path at Step 5 (the deliverables live in disjoint folders).

## Merge order (recommended, nothing is merged by the orchestrator)

1. 1C-1 export and members
2. 1A library
3. 1B
4. 1C-2 SIPP
5. 1C-3 harness
6. integration

## Acceptance gates (per track, all must pass)

- Tests: the track's test suite passes in a fresh virtual environment built from the repository's pinned requirements (`python3.12 -m venv`, `pip install -c constraints-routing.txt './integration[packets]'` for routing-side tracks; the forecast environment for 1B). Commands and exit codes are recorded in the progress log.
- Evidence: the track's `research/<track>/README.md` opens with its headline numbers, every number has a producing script and recorded seeds, hashes and host, and a "Scope and limits" section exists.
- Honesty: no README claims field validation, physical accuracy, or a universal speedup. Each use of "validated", "proves", "guarantees" and "safe" in the READMEs is checked.
- Style: no em dashes anywhere in new prose, comments, figure labels or commit messages. Figures exist as PNG and SVG with captions.
- Ownership: `git diff --name-only Main...<branch>` lies inside the track's allowance; the only shared touch point, `forecast/wildfire/rollout.py`, carries exactly the `trajectory_callback` kwarg (1C only) with a byte-identical-default test.
- Repository checks: `python tools/verify_release.py` still passes on the branch.

## Progress log

- 2026-10-29: Shared interfaces published at `docs/NEXT_INTERFACES.md`; prompts committed under `docs/next/prompts/`; plan written (orchestrator).
- 2026-10-29: Frozen Korean routing inputs fetched once and hash-verified (132 files, INPUT_FILES.json sha256 5d820b97740d879d2bc78a76d1b5854420793c927c6315f656dc1c2927b35235) at a shared read-only path for all tracks.
- 2026-10-29: Tracks 1A, 1B, 1C launched in parallel as background agents in separate git worktrees (branches `track/1a-flame-front-radiation`, `track/1b-forecast-v2`, `track/1c-routing-v2`).
