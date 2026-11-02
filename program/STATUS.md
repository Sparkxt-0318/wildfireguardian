# Program status

*Updated after every step. Resume from this file alone: read it, then `program/CLAUDE.md`
(orchestration rules), then the folder `CLAUDE.md` files (track specs).*

## Now

- **Phase:** **Phase 1, Track C batch 2 (E1b, E2)**, approved 2026-11-02 (`DECISIONS.md`). New VM session
  (`vm boot 4169abd4`): batch 2's rows form a new table; the recorded 1750/1751 keep its bar at 1751.
  - E1b: done, **KILL** (worst of 5 = 1444 < 1751; B2 1749 in every seed of the same holds). Merged into
    `evacplan/phase0` (`11670593`).
  - E2 (column generation): debugging under the lock, then two interleaved holds with B2 seeds 5-9 (E1b used 0-4).
  - Then a proportional review (one reproduction agent, one reviewer) and checkpoint 4 (one page, at most 5 questions).
- **Updated:** 2026-11-02 (UTC).

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

| Agent | Track | Doing | Worktree / branch |
|---|---|---|---|
| E1b incremental certification | C | done: KILL (worst 1444 < 1751); oracle profile on L in its README; merged | `../wfg-exp-E1b`, `evacplan/exp-E1b-incremental-cert` |
| E2 column generation | C | set partitioning over itineraries, pricing on E4's network, bound when valid; final run ABAB with B2 (seeds 5-9) | `../wfg-exp-E2`, `evacplan/exp-E2-column-generation` |
| Orchestrator | C | harness: B2's default seed offset per hold instances, explicit offsets may not replace rows | `../wfg-evacplan` |

Batch 1 is closed (E1 → E1b; E3, E4 KEEP). The batch-1 experiment worktrees were removed (branches stay on origin).

## Blockers

1. Track A real-data work: data root, NIROPS perimeters, Choi et al. reconstructions and torch
   are not reachable from this cloud container (see "Host and data").
2. Track C Caldor instance: no Caldor road graph/hazards in the repo; OSM, CMS and geocoding
   hosts blocked.

## Next step

1. Wait for E2 (pre-registration, tests, smoke, two interleaved holds: S+M, then L; B2 seeds 5-9).
2. Merge E2 into `evacplan/phase0`; regenerate the leaderboard and run the suite under the lock; merge into
   `next/integration`; push.
3. Proportional review, fixes, push; checkpoint 4 (`program/reviews/checkpoint-4.md`, one page); stop.

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
- 2026-11-01 Wave 1 done.
  - Harness: implements the 2026-11-01 rules (`03b339e0`). The orchestrator then added the VM boot session to the host
    string (`c78721e6`): after a container restart this VM was 1.7-2.4× slower under the same label.
  - H0: SYNTHETIC dev hazards are much hotter than the Korean dev packets on dose_lower by its pre-registered rule, and
    cooler on dose_upper (rule 4). E1 therefore runs untuned (`DECISIONS.md`).
  - Track A: 2025 US fresh-holdout proposal written; it leaves decisions for Siyeong.
  - Wave 2 launched (E1, E3, E4), and the 5-seed baseline re-runs started.
- 2026-11-01 Baseline re-runs, part 1 (SYNTHETIC, dev, 60 s, this VM session `vm boot ff671362`):
  - full evacplan suite at `c78721e6`: 324 passed;
  - B2 × 5 seeds: 1749 in every repeat, 0 unresolved (`c888a87b`). The bar on this host is 1750 (recorded Phase 0
    observation) until the other baselines are in;
  - the 2 h background job was killed while queued behind E3 before noop/B0/B1/B3 started. Those four are queued
    again with a capped wait (`program/benchlock.py --wait-max`, `4c523622`).
- 2026-11-01 E4 (flow-over-time LP bound, bound only) returned: **KEEP** (`742575e3`, SYNTHETIC dev, 900 s per instance).
  - Valid on every check run: S bound ≥ B3 in all 12 B3 rows; 0 violations over 284 checked rows; tiny brute-force
    instance bound 5 = optimum.
  - First proven bounds on M: 160/168 and 144/149 on the two t75 instances (best plans 140, 139), closing 29 % and 50 %
    of the trivial gap; 25/27 on S-grid-t75-s103, below B3's 26. L: only the resource bound at 900 s (LPs too large).
  - Two test fixes (`7ba44700`) were not re-run under the lock; the post-merge suite covers them. About 30 s of the
    agent's debugging overlapped the start of E1's final run (08:15:40-08:17). Lock time about 63 min (1 h budget).
- 2026-11-01 E1 (ALNS, oracle in the loop, untuned) returned: **KILL** (`59e19b30`, SYNTHETIC dev, 60 s × 5 seeds, this VM
  session).
  - Totals 1445/1444/1446/1443/1444: median 1444 [1443-1446], worst 1443 ≤ bar 1750 (B2 1749 × 5). 0 unresolved,
    0 over budget.
  - S and M: matches or beats every baseline (S 109 vs B2 108, M 605 vs 597; M-grid-t75-s107 147-150 vs 140).
  - L: 0 iterations. Certifying a full L plan inside the budget takes 33-41 s and E1 reserves 1.5× (pre-registered),
    so it returns B1's plan (335, 395 vs B2 516, 528). Seen in profiling outside the split; kept as pre-registered.
  - Question for Siyeong: certification inside vs outside the 60 s budget (B2's plan is certified outside it).
- 2026-11-01 E3 (scenario robustness, default margin) returned: **KEEP** (`5f0959f7`, SYNTHETIC dev).
  - Plans checked in all 8 members fail in fresh members of the same hazard model: 3.89 % of delivered residents
    (B1) and 7.6 % of plans; concentrated on M-grid-t75-s107 (37-39 %). All failures are flame contact.
  - Margin by the pre-registered rule: 1 min at α = 5 % (keeps 91 % of B1, 97 % of B2); none ≤ 60 min certified at
    α = 1 % (Korn-Graubard alone: 30 min). Per slack bin, about 30 min keeps every bin ≤ 5 %.
  - More fresh members cut violation about like 1/K but claim fewer residents (expected safe deliveries unchanged).
- 2026-11-01 Baselines completed on this VM session (`397e3f0b`): noop 0, B0 1157, B1 1353, B3 103-104 of 115 on S, in
  every repeat, 0 unresolved; best-of-baselines total 1750, bar 1750. E4, E1 and E3 merged into `evacplan/phase0`;
  leaderboard regenerated (`434959f8`). Post-merge suite: 375 passed, 1 failed (E1's budget test: the B1 warm start alone
  fills a 1.5 s budget); the test now asserts the guarantee E1 has (`18841678`, E1's code unchanged; three green runs).
  Merged into `next/integration` (`e8a5604e`). Independent review started on `18841678`.
- 2026-11-01 Independent review of batch 1 returned (R0 reproduction, 5 reviewers and 35 verifiers: 41 agents; review of
  `evacplan/phase0` @ `18841678` and `firecast-lab/phase0` @ `58ce939e`). All headlines reproduced. 32 discrepancies:
  - confirmed major: E1's approved 2-iteration budget had been cut by the orchestrator's brief without a record, so E1
    is ITERATE (1 of 2), not KILL (`DECISIONS.md`);
  - rule 5: evacplan's adapter tests read the KR-2025 road graphs and packet grid metadata (R0: major; verifier: minor);
  - rule 6: about 3 min of agents' work outside the lock overlapped B2's 5-seed hold (05:03-05:55), about 20 s E1's
    final run, about 27 s E3's compute hold; no reported number was affected;
  - the rest minor: the bar was 1750, not Siyeong's 1751; a recorded observation could define a bar without B2 rows;
    over-budget rows got verdicts; E4's PDLP diagnostics; stale or inexact README text in E1, E3, E4, H0 and the
    Track A proposal; E3's margin certificate covers only the 10 dev instances.
  - Corrections to earlier log entries: E1 is ITERATE (not KILL); its tiny-budget overrun comes from its setup (Reach
    and the latest-departure sweep), not the B1 loop; E3's "1/K" trend rests on one instance; E4's lock hold was
    59.6 min plus about 3 min of unlocked work.
- 2026-11-01 B2 × 5 re-run in one quiet hold (14:56-15:49 UTC, commit `18841678`, `/proc` sampler: every other process
  4.7 % of one core in all, almost entirely the agent harness): 1726/1737/1737/1737/1721, median 1737 [1721-1737],
  0 unresolved. B2's search found 14-28 % fewer solutions (means over seeds) on 9 of 10 instances than in the morning
  hold, with nothing else running: the VM's speed drifts within a session (L-geo 500-516 instead of 528). The rows
  replace the morning ones; the bar stays 1751 (recorded observations). Same-session comparisons hours apart therefore
  carry a speed uncertainty; proposed for batch 2: B2 interleaved with each challenger in one hold, and a speed probe
  in every row.
- 2026-11-01 Fixes committed and merged: Track C `cbbc8490` (code, tests, docs), `b0bd9b7d` (B2's quiet rows),
  `262ac6c6` (leaderboard, E1 and E4 outputs regenerated under the lock), `9d2ae36f` (README corrections); Track A
  `ed5a4b4b`. Suites: evacplan 377 passed with the real-data tests on (dev fires only), hazard_contract 76; on the merge,
  program 6 and the lock-related evacplan tests 43 passed. A B1 calibration took 7-18 % less time at 16:00 than its
  seed-0 rows of 09:15-09:20 (suggestive: B1's seeds already vary within one hold). Three agents verified the
  checkpoint-3 report and the review file against the repository before publication. Checkpoint 3 written; stopped.
- 2026-11-02 Siyeong answered checkpoint 3 (`DECISIONS.md`): E1b and E2 approved; certification outside the budget with
  a time-to-certified-plan metric; 30-min provisional default margin; B2 interleaved with each challenger; proportional
  reviews and one-page checkpoints. The container restarted (new VM session `4169abd4`). E1b and E2 agents launched.
- 2026-11-02 E1b **KILL**: worst of 5 = 1444 < 1751 (B2 1749 in every seed of the same two holds at commit `dae67e86`).
  S and M: +1 and +8 over B2 with every trip oracle-checked in the loop. L: −181 and −133, because certifying one
  changed L plan in the loop costs 32-36 s; in 6 of 10 L runs the certify trigger fired late (E1's prior 0.01 s per leg
  vs ~20 ms measured) and B1's plan was returned. Oracle profile on L (B1's plans): cold `check_plan` 30-31 s, 89 %
  hazard_contract queries (48 % per-member flux and dose bounds, 25 % cell geometry), 10 % exact leg slack. Time to
  certified plan 66.3 s for both. Merged into `evacplan/phase0` (`11670593`). E2 told to use B2 seeds 5-9.
