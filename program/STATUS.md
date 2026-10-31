# Program status

*Updated after every step. Resume from this file alone: read it, then `program/CLAUDE.md`
(orchestration rules), then the folder `CLAUDE.md` files (track specs).*

## Now

- **Phase:** Phase 0. Setup and `hazard_contract` v1 are done (checkpoint 1 reported).
- **Updated:** 2026-10-31 (UTC).

## Host and data (important)

- **This program is running in a Claude Code cloud container, not on Siyeong's Mac.**
  Linux x86_64, 4 vCPU, 15 GB RAM, Python 3.12.3 at `/usr/bin/python3.12`, `uv` available.
- **Network:** only PyPI and GitHub (incl. release assets) are reachable. Blocked by the
  environment's network policy: `zenodo.org`, `data.mendeley.com`, `data.cms.gov`,
  `overpass-api.de`, `geocoding.geo.census.gov`, `download.pytorch.org`.
- **Environmental data root** (`events.json` + `regions/`): **not on this host.** The repo
  has only metadata: `forecast/data/environment/events.json` (44 events),
  `forecast/data/catalog.csv`, NIROPS catalog metadata for 6 fires. The full root lives on
  the Mac (paths recorded in provenance files point to `/Users/...`).
- **NIROPS archive:** not on this host (1.39 GB `NIROPS_2020_2024_R1_R6.zip` on the Mac;
  Mendeley DOI 10.17632/95rj5d379g.1).
- **c651 checkpoint:** present at
  `forecast/runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt`,
  SHA-256 `c651f672…1843` verified.
- **torch:** not installed (CPU wheel index blocked; PyPI Linux build is CUDA, >1 GB → needs
  approval). c651 inference cannot run here.
- **Caldor/Rim road graph + packets:** not in the repo (sealed study on the Mac). OSM and CMS
  downloads are blocked here.

## Branches and worktrees

| Path | Branch | Purpose |
|---|---|---|
| `/home/user/wildfireguardian` | `next/integration` | integration + `program/`, `hazard_contract/` |
| `/home/user/wfg-evacplan` | `evacplan/phase0` | Track C |
| `/home/user/wfg-firecast` | `firecast-lab/phase0` | Track A |

`claude/ecstatic-keller-fm31to` (this cloud session's designated branch) is kept equal to
`next/integration`.

## Agents

| Agent | Track | Doing | Worktree |
|---|---|---|---|
| codebase-map readers (4 + critic) | both | read-only maps (scratchpad `maps/01..04`) | main checkout (read-only) |
| Track C chain: ~~C1 oracle~~ → ~~C0 merge~~ → **C2 generators/harness** → C3a deadlines/B0/B1 → C3b B2/B3 + dev run | C | Phase 0 | `/home/user/wfg-evacplan` |
| Track A: ~~A1 splits/metrics~~ → ~~A1b members/baselines/producer~~ → **A2 decision metric** | A | Phase 0 (no real data here) | `/home/user/wfg-firecast` |

## Blockers

1. Track A real-data work: data root, NIROPS perimeters, Choi et al. reconstructions and torch
   are not reachable from this cloud container (see "Host and data").
2. Track C Caldor instance: no Caldor road graph/hazards in the repo; OSM, CMS and geocoding
   hosts blocked.

## Next step

Phase 0 of both tracks, then independent review and checkpoint 2 (stop and wait).

## Log

- 2026-10-31 Preflight done (see "Host and data"). `Main` = `origin/Main` = `0cd95db`.
- 2026-10-31 `next/integration` created from `Main`; ground-rules `CLAUDE.md` written in
  `program/`, `evacplan/`, `firecast-lab/`, `hazard_contract/`; bench lock added.
- 2026-10-31 Worktrees `../wfg-evacplan`, `../wfg-firecast` created; venvs built (evacplan: osmnx 2.1.1,
  OR-Tools 9.14, highspy, wfg_latest; firecast: scipy 1.13.1, scikit-image, rasterio, forecast
  `wildfire` without torch). `hazard_contract` installed editable in all three venvs.
- 2026-10-31 `hazard_contract` v1 committed (53 tests pass incl. real Uljin packet); decisions in
  `DECISIONS.md`. Track branches fast-forwarded onto it and pushed.
- 2026-10-31 Milestone **C0-oracle** merged into `next/integration` (`4bc6190`) after a clean-checkout
  check by a non-author agent.
- 2026-10-31 Independent adversarial review of `hazard_contract`: 12 confirmed findings (2 false-safe
  paths: filled polygon holes, float time drift in `query_uniform`), all fixed in 1.0.1 with
  regression tests (77 pass); merged into both track branches.
- 2026-10-31 Track A A1 (`a5fb3d2`): `SPLITS.json` committed first (dev 34 fires in 3 season folds; test =
  US 2024 + KR 2025, 10 fires, flagged not fresh; `fresh_holdout` locked and empty: NIROPS v1 ends 2024).
  `DATA_NOTES.md`: headline lead 24 h (Korean label MAE 7.65–12.18 h; 12 h diagnostic only); NIROPS is
  independent truth for timing, not extent; weather = archived IFS repeated from the cutoff; support
  masks must use cutoff-time information, never the reconstruction NoData mask (it leaks the final scar).
  Metrics + 3 km headline buffer. 61 tests.
- 2026-10-31 Track A A1b (`d428a1e`): coherent members (shared / Gaussian copula), baselines
  (persistence, tuned dilation, calibrated dilation, logistic), c651 wrapper (needs torch + Mac data),
  cross-fitted harness/CLI, producer to `hazard_contract`. 97 pass, 2 skip (no torch). No real-data
  numbers exist yet.
