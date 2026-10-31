# program/ — orchestration of the two-track program

This folder coordinates Track C (`evacplan/`, the main product) and Track A
(`firecast-lab/`, side project, at most ~20% of effort) through one shared interface
(`hazard_contract/`). Resume from `program/STATUS.md` alone if context is lost.

## Ground rules (identical in every program folder; they override this repo's older audit conventions)

1. **Allowed folders.** Create and edit files only in `evacplan/`, `firecast-lab/`,
   `hazard_contract/` and `program/`. Never edit, move or delete anything else: the rest of
   the repo is the frozen research release. Import from `integration/` (`wfg_latest`) and
   `forecast/` (`wildfire`) instead of copying them. Adding these tracks to CI needs
   Siyeong's approval.
2. **Light rigor, no bureaucracy.** Every result row records the git commit, seed, config and
   host. That's all. No SHA ledgers, custody receipts, gate JSON files, "HOLD" taxonomies or
   reviews of reviews. If you want a verification document, write a test instead.
3. **One feasibility oracle**, `evacplan.oracle`. It is the only code that may declare a
   vehicle itinerary `checked`, `model_no_route` (model-infeasible, scoped to model and
   horizon) or `unresolved`. Fast relaxed checks are allowed inside search loops, but final
   answers and Track A's decision metric go through the oracle.
4. **Unknown is not unburned.** Missing hazard data flows through as `unsupported`, which
   leads to `unresolved`. It never defaults to safe. `unresolved` never counts as safe or
   delivered.
5. **Splits before methods.** Track C: frozen `dev` and `test` instance sets. Track A:
   `firecast-lab/SPLITS.json`, split by whole fire, never by cell or window. Touch `test`
   sets or held-out fires only at milestones, after Siyeong approves. Track A reports
   uncertainty with whole-fire bootstrap intervals; repeated windows are not independent fires.
6. **Fair timing.** Agents may write code in parallel. Timed benchmark runs must not overlap
   other heavy computation: run them through the shared lock,
   `python program/benchlock.py -- <command>` (lock file `program/.bench.lock` in the main
   checkout, shared by all worktrees). Always compare methods at equal wall-clock budgets.
7. **Data and licenses.** Keep OSM attribution (ODbL). Choi et al. 2026 reconstructions and
   NIROPS perimeters are CC BY 4.0; CMS provider data is public. Label synthetic data as
   SYNTHETIC everywhere, including figures. Ask before any download over 1 GB, any scraping,
   or committing anything over 20 MB. Never commit raw rasters, weights or personal data
   (use the folder's `.gitignore`).
8. **Stack.** Python 3.12. Track C: numpy, networkx, osmnx, OR-Tools, HiGHS (`highspy`),
   pydantic, pytest, matplotlib. Track A: also PyTorch (CPU or Apple MPS), scipy,
   scikit-image, rasterio or xarray. CPU or MPS only. Ask before adding other major
   dependencies.
9. **Time-box.** Each experiment states its budget and ends with one decision: KEEP, KILL or
   ITERATE. Negative results are reported in the same format as positive ones.
10. **Git.** Never commit to or push `Main`. Never force-push. Never create GitHub repos. Push
    only `next/integration`, the track branches `evacplan/phase0` and `firecast-lab/phase0`,
    and short-lived experiment branches (`evacplan/exp-<ID>-<slug>`,
    `firecast-lab/exp-<ID>-<slug>`) to `origin`. Experiments merge into their track branch,
    track branches into `next/integration`; Siyeong merges `next/integration` into `Main`
    through pull requests. Commit small and often, with clear messages.

**Always ask Siyeong before:** changing either problem definition or the `hazard_contract`
interface; touching test sets or held-out fires; downloads over 1 GB; adding a major
dependency; any single run longer than 2 hours; editing anything outside the four folders;
opening a pull request to `Main`.

## Orchestration protocol

- **Coordination files** (on `next/integration`): `STATUS.md` (phase, what each agent is
  doing, blockers, next step — updated after every step), `DECISIONS.md` (dated decisions,
  one-line reason each), `LEADERBOARD.md` (links to each track's leaderboard),
  `reviews/` (one short markdown file per checkpoint review; no receipts).
- **Branches/worktrees.** `next/integration` (main checkout) ← `evacplan/phase0`
  (`../wfg-evacplan`) and `firecast-lab/phase0` (`../wfg-firecast`). Experiments get their
  own short-lived branch + worktree and merge back into their track branch.
- **Interface.** `hazard_contract` changes go through the orchestrator only, are recorded in
  `DECISIONS.md`, and bump the version.
- **Agents.** Each subagent gets: the relevant spec sections, its worktree path, an
  instruction to read its folder's `CLAUDE.md`, and returns a summary of at most 15 lines
  (what changed, test status, results, open questions). Subagents do not spawn further agents.
  Phase 0: one agent per track in parallel; Track C reaches milestone C0-oracle early and it
  is merged into `next/integration` as soon as it passes. Phase 1: at most 3 experiment agents
  at once, each in its own worktree; timed runs go through the bench lock.
- **Independent review at each checkpoint.** A fresh agent that did not write the code reruns
  the tests and one headline number from a clean checkout of the track branch, checks the
  three-state honesty rule, the splits and the equal-time comparisons, and reports
  discrepancies in one short file in `program/reviews/`.

## Experiment protocol (both tracks)

Each experiment gets `<track>/experiments/<ID>-slug/` with `README.md` (hypothesis, why it
might work, setup, baseline, metric, budget, results table, decision KEEP/KILL/ITERATE, next
step), `config.yaml`, `results.csv`, `figures/`. Dev data only. Afterwards add a summary of
at most 10 lines to `program/STATUS.md` and update the track leaderboard.

## Checkpoints (stop and wait for Siyeong)

1. After setup + `hazard_contract` v1: 10-line report (data root, branches/worktrees,
   interface summary). Continue into Phase 0 unless blocked.
2. After Phase 0 of both tracks + independent review: one combined report (both baseline
   leaderboards, oracle test results, data problems, assumptions to check, questions, proposed
   first 3 experiments per track). Then wait.
3. After each batch of up to 3 experiments: summary and leaderboard. Continue only if approved.

Out of scope now: UI, the HTTP API, authentication, cloud deployment, pitch material, and
changes to the frozen research folders.
