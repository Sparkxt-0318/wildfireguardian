# Program status

*Updated after every step. Resume from this file alone: read it, then `program/CLAUDE.md`
(orchestration rules), then the folder `CLAUDE.md` files (track specs).*

## Now

- **Phase:** Setup (branches, worktrees, venvs, coordination files) → next `hazard_contract` v1.
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
| codebase-map readers (4 + critic) | both | read-only map of packets, router, forecast API, splits | main checkout (read-only) |

## Blockers

1. Track A real-data work: data root, NIROPS perimeters, Choi et al. reconstructions and torch
   are not reachable from this cloud container (see "Host and data").
2. Track C Caldor instance: no Caldor road graph/hazards in the repo; OSM, CMS and geocoding
   hosts blocked.

## Next step

Finish setup, write `hazard_contract` v1 with tests, push branches, checkpoint-1 report.

## Log

- 2026-10-31 Preflight done (see "Host and data"). `Main` = `origin/Main` = `0cd95db`.
- 2026-10-31 `next/integration` created from `Main`; ground-rules `CLAUDE.md` written in
  `program/`, `evacplan/`, `firecast-lab/`, `hazard_contract/`; bench lock added.
