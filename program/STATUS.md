# Program status

*Updated after every step. Resume from this file alone: read it, then `program/CLAUDE.md`
(orchestration rules), then the folder `CLAUDE.md` files (track specs).*

## Now

- **Phase:** **Phase 1, Track C batch 1 (E1, E4, E3)**, approved 2026-11-01 (answers in `DECISIONS.md`).
  - Wave 1: harness for the new rules plus the 5-repeat baseline reruns, the H0 hazard-intensity panel, and the
    Track A fresh-holdout proposal.
  - Wave 2: E1, E4 and E3.
  - Then the independent review, and checkpoint 3 (stop and wait for Siyeong).
- **Updated:** 2026-11-01 (UTC).

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
`next/integration`. The two `hazard_contract` test fixes (`32735e36`, `efa43039`) are on `next/integration` only.
Merge `next/integration` into both track branches before Phase 1 work starts there.

## Agents

| Agent | Track | Doing | Worktree |
|---|---|---|---|
| codebase-map readers (4 + critic) | both | read-only maps (scratchpad `maps/01..04`) | main checkout (read-only) |
| Track C chain: ~~C1 oracle~~ → ~~C0 merge~~ → ~~C2 generators/harness~~ → ~~C3a deadlines/B0/B1~~ → ~~C3b B2/B3 + dev run~~ → ~~review fixes~~ — Phase 0 done (`1373bb3f`) | C | idle (checkpoint 2) | `/home/user/wfg-evacplan` |
| ~~Phase 0 reviewers + adversarial verifiers~~ (done) | both | → `program/reviews/phase0-review.md` | scratchpad (removed) |
| ~~Fix agents (one per track)~~ (done) | both | every confirmed finding fixed with a regression test | own worktrees |
| Track A: ~~A1~~ → ~~A1b~~ → ~~A2 decision metric~~ → ~~review fixes~~ — Phase 0 code done (`9a74994b`); real-data runs blocked | A | idle (checkpoint 2) | `/home/user/wfg-firecast` |

## Blockers

1. Track A real-data work: data root, NIROPS perimeters, Choi et al. reconstructions and torch
   are not reachable from this cloud container (see "Host and data").
2. Track C Caldor instance: no Caldor road graph/hazards in the repo; OSM, CMS and geocoding
   hosts blocked.

## Next step

1. **Wave 0** (orchestrator): record the answers; merge `next/integration` into both track branches.
2. **Wave 1**, three agents:
   - C-infra in `../wfg-evacplan`: 5 repeats with median and range, the B2 bar and verdict, tables split per host,
     margin columns and plot; then the baselines × 5 seeds through the bench lock.
   - H0 in `../wfg-exp-H0`, branch `evacplan/exp-H0-hazard-intensity`: SYNTHETIC vs Korean dev flux and dose
     distributions, with a pre-registered "much hotter" test.
   - A-fresh in `../wfg-firecast`: proposal for a 2025 US truth source.
3. **Wave 2**, three agents, each in its own worktree and `exp-` branch: E1 (ALNS; held if H0 finds the SYNTHETIC
   hazards much hotter), E4 (flow bound) and E3 (scenario robustness and default margin).
4. Independent review, then the checkpoint 3 report. **Stop and wait for Siyeong.**

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
- 2026-10-31 Track C C2 (`b868d4a`): SYNTHETIC generators (grid / random geometric), split frozen
  before any method (dev and test: 4 S + 4 M + 2 L each), harness `evacplan run`, noop plumbing row,
  Caldor builder written but BLOCKED (no OSM/CMS/geocoder access; no fabricated instance).
- 2026-10-31 Track A A2 (`821ceb4`): decision metric on the oracle (cutoff-only fixed requests; truth =
  envelope perimeters / reconstruction isochrones; false-safe, miss, clearance, false-unsafe with
  whole-fire bootstrap; K-curves for shared and copula couplings). 117 pass. Estimated cost ~80 min
  per model for the 17 Korean dev windows that have road graphs (Uljin, Hongseong, Miryang).
- 2026-10-31 Track C C3a (`511154d`): latest-safe-departure sweep (`reach.py`), per-facility deadlines
  (`deadlines.py`, oracle-confirmed probe trips; unservable only when proven), B0 independent, B1 EDF
  insertion. 237 pass.
- 2026-10-31 Track C C3b (`3104800`): B2 OR-Tools VRPTW, B3 HiGHS MIP (S only, child process because
  OR-Tools bundles an older libhighs), realizer. 261 pass (~4 min; run through the bench lock).
  Dev, 60 s, seed 0, commit `957e672`, SYNTHETIC: B2 1683/1975 (85.2%, 67 unresolved on one dose-limited
  bus), B1 1353 (68.5%), B0 1157 (58.6%), B3 104/115 on S (mean gap 0.083). Caldor still blocked.
- 2026-10-31 Independent Phase 0 review (fresh reviewer + adversarial verifier per track, clean checkouts):
  no critical findings. Confirmed major: B2's dev total varies 1682–1750 with search depth (one instance
  flips 155/0 ↔ 88/67); `ortools` unpinned (9.15 crashes B2); Korean decision truth calls partly burned
  edge cells never-burning (false-safe biased low); Track A run rows lack most spec metrics. B1 reproduces
  exactly; accounting identity holds on every row; three-state rule, splits and equal time pass.
- 2026-10-31 Trial merge of both tracks onto `next/integration`: no conflicts; firecast-lab passes against
  the new evacplan (116 passed, 3 skipped). Fixed here: hazard_contract `np.trapz` test (numpy 2),
  real-packet test skips when its folder is missing. Decisions recorded (comparison rule: 3 repeats,
  "beats B2" = min > B2's max; ortools cap + lock files; scikit-learn/hypothesis; test-fire metadata).
- 2026-10-31 Fix round, one agent per track. Every confirmed review finding is fixed with a regression test
  (Track C `590a4b49`, Track A `9a74994b`). Track C reran every method on dev at 60 s × 3 repeats at clean
  commit `b43990bb` (SYNTHETIC):
  - B0 1157, B1 1353, noop 0;
  - B2 1682 with 68 unresolved, identical across repeats; the review's run got 1750 / 0, which is the interim bar;
  - B3 103.7 of 115 on S.
  The Track C result rows are now committed (`1373bb3f`).
- 2026-10-31 Both track branches merged into `next/integration`. All suites pass on the merge in venvs built from
  each track's `requirements.lock`: evacplan 310, hazard_contract 76, firecast-lab 125 + 3 skipped, program 2.
  Checkpoint 2 report written; waiting for Siyeong.
- 2026-11-01 Siyeong answered checkpoint 2 (`DECISIONS.md`): data access deferred (stay in the cloud, invent nothing);
  batch 1 E1/E4/E3 approved; new comparison rule (5 repeats, median and range, worst of 5 must exceed both 1750 and
  1751, host in every row, never compare across hosts); dose distributions vs the Korean panel before tuning; margin
  columns at slack ≥ 0/5/15/30 min plus a plot; scikit-learn and hypothesis approved; test-fire metadata kept;
  fresh-holdout truth source to be proposed.
