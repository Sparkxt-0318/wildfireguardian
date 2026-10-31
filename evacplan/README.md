# evacplan — Track C: care-facility wildfire evacuation dispatch planner

Status: Phase 0. Done: schema, validator and feasibility oracle (milestone **C0-oracle**); SYNTHETIC
instance generators, the frozen `dev`/`test` split and the benchmark harness; the latest-safe-departure sweep
with per-facility deadlines and unservable residents; baselines **B0** (independent), **B1** (EDF
insertion), **B2** (OR-Tools VRPTW with pickup and delivery and static windows) and **B3** (exact MIPs on a
time-expanded network with HiGHS, S instances, with a proven bound). Real US region 1 (Caldor Fire 2021,
South Lake Tahoe): builder written, build **BLOCKED** on the cloud container (no inputs, hosts blocked).
Rules and the problem definition: [`CLAUDE.md`](CLAUDE.md); every modelling choice:
[`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md); results: [`LEADERBOARD.md`](LEADERBOARD.md).

| module | what |
|---|---|
| `evacplan.schema` | Problem v0 `Instance` / `Solution` (pydantic v2), JSON I/O, hazard folder resolution |
| `evacplan.validate` | hazard-free validator: timeline of occupancies and issue codes (resources, times, paths) |
| `evacplan.oracle` | **the** oracle (program rule 3): `check_plan`, `check_itinerary`, `Oracle`; the RELAXED `RelaxedContactCheck` for search loops |
| `evacplan.generators` | SYNTHETIC instances: grid / random geometric roads, facilities, fleet, shelters, a `hazard_contract.synthetic` fire that threatens the facilities; deterministic from `(size, tightness, graph, seed)` |
| `evacplan.instances` | the frozen split (`instances/SPLIT.json`), fingerprints, the regenerated instance cache |
| `evacplan.reach` | RELAXED time-dependent reachability on the 1 s lattice (no states): departure masks, the backward latest-safe-departure sweep from all shelters (all K members, turn rules, waits, windows), witness routes, time-dependent A*, the certain-contact relaxation |
| `evacplan.deadlines` | per facility and class: `arrive_by_s` / `leave_by_s` confirmed by oracle probe trips, and residents no plan can serve (scoped `model_no_route`, declared by the oracle) |
| `evacplan.harness`, `evacplan.methods` | `evacplan run`: budgets, bench lock, oracle-checked result rows, per-facility rows, `LEADERBOARD.md` (with the best proven bound per instance); the method interface, `noop`, `b0_independent` (B0: every facility planned alone with today's planner logic, the shared fleet first come first served), `b1_greedy` (B1: earliest-deadline-first insertion with the sweep's deadlines), `b2_vrptw` (B2: OR-Tools VRPTW, pickup and delivery, per-class capacities, static windows from the latest departures), `b3_mip` (B3: relaxed MIP for the bound, restricted MIPs on coarse-to-fine grids for the plan, HiGHS in a child process; S instances only); aliases `B0`..`B3`; `methods.dispatch` (shared trip machinery), `methods.realize` (ASAP replay of stop sequences, B2/B3), `methods.timexp` (the time-expanded network and MIP), `methods.highs_worker` |
| `evacplan.regions` | real regions: OSM roads (osmnx), CMS nursing homes + geocoding, perimeters (`from_perimeters`), SYNTHETIC residents and fleet; `regions.caldor` |
| `evacplan.adapters.wfg_graph` | this repo's router `graph.json` → `RoadGraph` (router admission reused) |

Hazards come in only through `hazard_contract`. Every leg and trip gets exactly one of `checked`,
`model_no_route` (scoped to the hazard model, its K members and horizon) or `unresolved` (never safe,
never delivered).

## Harness

```sh
# timed runs hold the shared bench lock (taken by the harness itself, or by a parent benchlock.py)
.venv/bin/python program/benchlock.py --label evacplan-b2 -- \
    .venv/bin/evacplan run --method B2 --set dev --budget-s 60 --seeds 0      # also B0, B1, B3 (S only), noop
.venv/bin/evacplan leaderboard                 # regenerate LEADERBOARD.md from results/*.csv
.venv/bin/evacplan instances --set dev          # the frozen dev instances (add --materialize to cache them)
```

`results/<method>.csv` (git-ignored) has one row per instance, seed, budget and set: `instance, method,
seed, delivered_checked, unresolved, model_no_route, makespan_s, min_slack_s, runtime_s, best_bound, gap,
commit, config, host`. Every number comes from the oracle; `best_bound` is a method's proven upper bound on
the residents ANY plan can deliver (B3), and the leaderboard shows the smallest one per instance. `results/<method>.facilities.csv` (git-ignored)
has one row per instance, seed, facility and mobility class: the facility's deadlines (`arrive_by_s`: latest
first arrival, `leave_by_s`: latest last departure, both oracle-checked), the residents no plan can serve
(`unservable`, a scoped `model_no_route`), and this plan's delivered / unresolved / model_no_route / not planned
residents there. `--set test` is refused without `--allow-test`
(milestones only, after Siyeong approves). A method subclasses `evacplan.methods.Method` and is registered in
`evacplan.methods`; `Method.applicable(instance)` lets it skip instances (B3 beyond S: no row).

## Instances

`instances/SPLIT.json` was frozen before any method ran: `dev` and `test` each have 4 S + 4 M + 2 L
SYNTHETIC instances (disjoint seeds, same mix). They regenerate into `cache/instances/<id>/` (git-ignored)
and must match their fingerprints. The test suite (`tests/test_split.py`) regenerates and checks the dev
instances only; `EVACPLAN_MILESTONE=1` adds the test instances, for milestones only, after Siyeong approves
(program rule 5). One-off instances: `evacplan generate --size M --tightness 0.5 --graph geo --seed 7 --out DIR`.

`evacplan build-caldor` builds real US region 1 from a road GraphML, the CMS provider file, geocodes and
perimeters; without them it prints `BLOCKED` and exactly what it needs.

## Install and test

From the repository root of a clean checkout (Python 3.12), this reproduces the venv that produced the
results: the third-party packages pinned in [`requirements.lock`](requirements.lock) (among them ortools
9.14.6206, highspy 1.15.1, numpy 1.26.4), then the in-repo packages from this repository, never from an
index. `hazard_contract` and `evacplan` are installed editable without dependencies; `wfg_latest` (the
frozen `integration/` folder, used by the router-graph adapter) only goes on the path through a `.pth`
file, because `pip install -e` would write build files into a frozen folder. ortools must stay below 9.15
(`pyproject.toml` caps it): 9.15's Python wrapper rejects the list argument of `SetAllowedVehiclesForIndex`
and B2 crashes. The test suite takes about four minutes (B2 and B3 run with short budgets), so run it
through the bench lock:

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r evacplan/requirements.lock
uv pip install --python .venv/bin/python --no-deps -e hazard_contract -e evacplan
echo "$PWD/integration/src" > "$(.venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')/wfg_latest_src.pth"
.venv/bin/python program/benchlock.py --label evacplan-tests -- .venv/bin/python -m pytest evacplan/tests
```

The adapter tests read the fetched study graphs and packets from `$WFG_ROUTING_INPUTS` and skip when they
are absent; that data is never copied into the repo. Road data from OpenStreetMap is © OpenStreetMap
contributors (ODbL 1.0).
