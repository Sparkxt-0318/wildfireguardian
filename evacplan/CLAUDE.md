# evacplan/ — Track C: care-facility wildfire evacuation dispatch planner (main product, US first)

Core question: *"With these vehicles and drivers, in what order do we pick up these residents
from these facilities, each with boarding time, so that every leg of every trip is checked
against every fire scenario, and as many people as possible reach an open shelter before
roads close?"*

Host, data availability, worktree paths and blockers: see `program/STATUS.md`.

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

## What the repo already gives you

- A time-dependent single-vehicle router (`integration/`, package `wfg_latest`, kit v3; the
  opt-in request-window kit is in `experimental/window-routing/`). It searches a
  flame-contact-avoiding route, gets an earliest-arrival lower bound, then checks the complete
  journey (driving, waiting, destination stay) against flame contact, peak heat flux and
  cumulative exposure in every scenario. It returns exactly one of `checked_route`,
  `model_no_route` (scoped to the model and horizon) or `unresolved`. **`unresolved` is never
  safe.** That honesty rule is the product's core value; keep it everywhere.
- Hazards reach evacplan **only through `hazard_contract`** (`hazard_contract/` in this repo).
  Do not read hazard packets or forecast rasters directly.

## Problem v0 (refine with Siyeong if it doesn't fit — ask before changing it)

- **Inputs.** Road graph: directed, travel times, turn rules, permitted waiting. Facilities:
  location, residents by mobility class (ambulatory, wheelchair, bedbound), boarding time per
  class, release time (staff ready). Vehicles: depot, start time, seat capacity, wheelchair
  slots, stretcher slots, driver shift limit. Shelters: location, capacity by class, opening
  windows, unloading time. Hazard: a `hazard_contract` scenario set with K members.
- **Decision.** For each vehicle, a timed itinerary (multiple trips allowed).
- **Objective (lexicographic).** 1) maximize residents delivered via legs checked in all K
  members; 2) maximize minimum safety slack; 3) minimize vehicle-time.
- **Output.** A plan in which every pickup and leg carries one of the three states. Per
  facility: the latest time the first vehicle must arrive, the latest time the last vehicle
  must leave, and residents who cannot be served — reported as a scoped `model_no_route`,
  never hidden.

## Phase 0

1. Pydantic schema and JSON format for instances and solutions, with a validator.
2. **The oracle (milestone C0-oracle).** An itinerary checker built on `hazard_contract`:
   occupancy intervals per leg, wait, boarding and unloading; contact and flux integration in
   every member; three-state output. Reuse the router's concepts and code from
   `integration/`. Property tests: adding a constraint can never turn infeasible into
   feasible; unresolved never counts as delivered; unsupported hazard data leads to
   unresolved.
3. **Instance generators.** Synthetic: random geometric and grid road graphs with controllable
   tightness, sizes S (~2 facilities, 1–2 vehicles, 20–40 residents), M (~6 facilities, 3–5
   vehicles, ~150 residents), L (~15 facilities, 10 vehicles, ~600 residents). Real US
   region 1: Caldor Fire 2021, South Lake Tahoe — reuse the repo's Caldor/Rim road graph and
   hazards if usable, otherwise OSM via osmnx plus `from_perimeters` (record which in
   `program/DECISIONS.md`); facilities from the CMS Provider Data Catalog nursing-home
   provider file (name, address, certified beds), geocoded; residents and vehicles synthetic
   with a documented mobility mix and fleet (e.g. 8-seat vans with 2 wheelchair slots, 40-seat
   buses, ambulances). Everything goes in `evacplan/docs/ASSUMPTIONS.md`. Freeze the
   `dev`/`test` split.
4. **Harness.** `evacplan run --method X --set dev --budget-s 60` writes
   `results/<method>.csv` with instance, method, seed, delivered (checked), unresolved,
   model-no-route, makespan, minimum slack, runtime, best bound and gap (plus commit, config,
   host). It also regenerates `evacplan/LEADERBOARD.md`. Timed runs go through the bench lock.
5. **Baselines.** B0 independent: each facility planned alone (today's planner logic; shows
   the coordination gap). B1 greedy: earliest-deadline-first insertion. B2 OR-Tools VRPTW
   (pickup and delivery with capacities) using static windows from per-facility latest
   departures, then checked by the oracle. B3 exact: MIP on a time-expanded network, HiGHS,
   S instances only.

## Phase 1 backlog (this order unless Phase 0 results argue otherwise)

Each experiment states hypothesis, why it might work (the math), baseline to beat, metric,
budget and kill criterion.

- **E1** ALNS with the oracle in the loop (Ropke & Pisinger 2006): relaxed checks in the inner
  loop, full oracle on incumbents ("search cheaply, check expensively"; FIRE paper; Dellin &
  Srinivasa 2016).
- **E2** Column generation / branch-and-price: set partitioning over itineraries; pricing is a
  resource-constrained shortest path on the time-expanded hazard network (Irnich &
  Desaulniers 2005); LP bounds become optimality-gap certificates.
- **E3** Scenario robustness: feasible-in-all-K vs CVaR over members vs chance constraints;
  scenario approach (Campi & Garatti) linking K to a probabilistic feasibility guarantee.
- **E4** Dynamic-flow upper bound: quickest transshipment / temporally repeated flows
  (Ford–Fulkerson; Hoppe & Tardos). How tight vs achieved?
- **E5** Rolling-horizon replanning: hazard updates every 20 min (FireSat-like) vs ~12 h
  (VIIRS-like); residents gained and plan churn, with a churn penalty.
- **E6** Bus-evacuation and dial-a-ride formulations (Bish 2011; Goerigk et al.; Cordeau 2006).
- **U1** Backward reachability (Hamilton–Jacobi view): one backward time-dependent sweep from
  all shelters gives a latest-safe-departure field per node and time (deadlines, pruning,
  heuristics).
- **U2** Scheduling theory: vehicles as machines, pickups as jobs with release times and
  deadlines; Moore–Hodgson and EDF as heuristics and bounds.
- **U3** Rollout and MCTS (Bertsekas rollout) for sequential dispatch; compare with E5.
- **U4** Value of information: residents safely delivered vs forecast quality and update
  cadence (perturbed members, later Track A's real members).
- **U5** Learned insertion (Kool et al. 2019) — only if E1 and E2 plateau; must beat ALNS at
  equal time.
- **Free slot:** up to 3 of your own ideas, justified. Ask Siyeong before running them.

## Done (this stage)

Oracle, generators, harness and baselines B0–B3 work with tests passing; at least 4
experiments concluded; at least one method beats B2 on `dev` at equal time, with a bound-based
gap where available; `evacplan/demos/caldor_demo.ipynb` shows facilities, vehicles, the plan
on a map, per-facility deadlines, the three states, and the coordinated plan versus B0.
