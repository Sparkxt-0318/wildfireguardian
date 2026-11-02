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
| `evacplan.harness`, `evacplan.methods` | `evacplan run`: budgets, bench lock, oracle-checked result rows, per-facility rows, `LEADERBOARD.md` (with the best proven bound per instance); the method interface, `noop`, `b0_independent` (B0: every facility planned alone with today's planner logic, the shared fleet first come first served), `b1_greedy` (B1: earliest-deadline-first insertion with the sweep's deadlines), `b2_vrptw` (B2: OR-Tools VRPTW, pickup and delivery, per-class capacities, static windows from the latest departures), `b3_mip` (B3: relaxed MIP for the bound, restricted MIPs on coarse-to-fine grids for the plan, HiGHS in a child process; S instances only); aliases `B0`..`B3`; `e4_flow_bound` (E4, bound only: a flow-over-time LP bound on the residents any plan can deliver, every size, certified by weak duality; `methods.flow_bound`, `methods.lp_worker`); `methods.dispatch` (shared trip machinery), `methods.realize` (ASAP replay of stop sequences, B2/B3), `methods.timexp` (the time-expanded network and MIP), `methods.highs_worker` |
| `evacplan.regions` | real regions: OSM roads (osmnx), CMS nursing homes + geocoding, perimeters (`from_perimeters`), SYNTHETIC residents and fleet; `regions.caldor` |
| `evacplan.adapters.wfg_graph` | this repo's router `graph.json` → `RoadGraph` (router admission reused) |

Hazards come in only through `hazard_contract`. Every leg and trip gets exactly one of `checked`,
`model_no_route` (scoped to the hazard model, its K members and horizon) or `unresolved` (never safe,
never delivered).

## Harness

```sh
# timed runs hold the shared bench lock (taken by the harness itself, or by a parent benchlock.py), one method
# per lock acquisition, on a quiet machine. Comparison rule (program/DECISIONS.md, 2026-11-01): every method runs
# 5 repeats (seeds 0-4) at the same budget; --repeats 5 is short for --seeds 0 1 2 3 4
for m in noop b0_independent b1_greedy b2_vrptw b3_mip; do         # B3 runs on S instances only
  .venv/bin/python program/benchlock.py --label "evacplan-$m" -- \
      .venv/bin/evacplan run --method "$m" --set dev --budget-s 60 --repeats 5
done
.venv/bin/evacplan leaderboard                 # regenerate LEADERBOARD.md and figures/ from results/*.csv
.venv/bin/evacplan instances --set dev          # the frozen dev instances (add --materialize to cache them)
```

`results/<method>.csv` (committed with the leaderboard) has one row per instance, seed, budget, set and host: `instance,
method, seed, delivered_checked, unresolved, model_no_route, makespan_s, min_slack_s, delivered_slack_ge_0m,
delivered_slack_ge_5m, delivered_slack_ge_15m, delivered_slack_ge_30m, runtime_s, best_bound, gap, commit, config, host`.
Delivered, unresolved and model_no_route (and every per-facility state) come from the
oracle; `best_bound` and `gap` come from a method's own proof (B3: a proven upper bound on the residents ANY plan
can deliver; the leaderboard shows the smallest one per instance); `runtime_s` is the harness's clock around the
method's solve. `results/<method>.facilities.csv` (committed; plans and oracle results in `results/runs/` are not)
has one row per instance, seed, facility and mobility class: the facility's deadlines (`arrive_by_s`: latest
first arrival, `leave_by_s`: latest last departure, both oracle-checked), the residents no plan can serve
(`unservable`, a scoped `model_no_route`), and this plan's delivered / unresolved / model_no_route / not planned
residents there. `--set test` is refused without `--allow-test`
(milestones only, after Siyeong approves). A method subclasses `evacplan.methods.Method` and is registered in
`evacplan.methods`; `Method.applicable(instance)` lets it skip instances (B3 beyond S: no row). A bound-only
method (`Method.bound_only`, e.g. `e4_flow_bound`) plans nothing: its rows say `bound_only` in their config, its
bounds feed the best-bound column of every table of the same set and host (any budget) and its own bounds table
(runtime, gap to the best plan), and it is left out of the method table, the verdicts and the margin figure
(`docs/ASSUMPTIONS.md` #94).

**Comparing with B2 (batch 2 on).** Timed comparisons run B2 interleaved with the challenger in one bench-lock hold:
`evacplan run --method X --interleave-with b2_vrptw --set dev --budget-s 60 --repeats 5 [--instances ...]` alternates
B2 and X per instance and seed (ABAB) and times a fixed workload before every pair (the speed check,
`results/speed/speed_check.csv`). By default B2's seeds continue after its rows on the hold's instances, so each hold
adds B2 repeats; an explicit `--partner-seed-offset` may not replace B2 rows, and a hold may not replace X's rows
unless `--replace` is given (`docs/ASSUMPTIONS.md` #96). In a table with interleaved holds, X gets a verdict only if
each of its rows has a B2 row in the same hold and pair. Every row also records how long the final oracle
certification took (`certify_s`, a fresh oracle, outside the budget); the leaderboard shows **mean time to certified
plan**, the mean of runtime + certification. A hold must finish within the 2 h job limit: on the cloud VM run the 8 S
and M instances and the 2 L instances as two holds.

**Safety margins.** `delivered_slack_ge_Xm` counts the residents delivered with a safety slack of at least X minutes:
the smallest oracle leg slack over their vehicle's legs from the start of its itinerary through the unloading that
delivers them, each leg capped at the time left before the hazard horizon (`docs/ASSUMPTIONS.md` #91).
`delivered_slack_ge_0m` equals `delivered_checked`, and the row's `config` holds the whole curve
(`delivered_by_margin_min`, 0-60 min). The problem definition is unchanged: delivered counts every checked trip. The
leaderboard adds slack ≥ 5, 15 and 30 min (30 min is the provisional default robust count, DECISIONS 2026-11-02),
and each table gets a figure of residents delivered vs required margin
(`figures/margin_<set>_<budget>s_<host-slug>.png`, regenerated by `evacplan run` and `evacplan leaderboard`).

**Hosts.** Every row records its host: host name, OS, machine, CPU model, CPU count and Python version
(`docs/ASSUMPTIONS.md` #92). Rows are upserted by (set, budget, instance, method, seed, host), and the leaderboard
renders one table per set, budget and host. Rows of different hosts are never pooled or compared, and times are
never compared across hosts. On a virtual machine (a cloud container) the host string ends with the VM's boot
session, so each container session is its own host: run the baselines and the methods compared with them in one
session (ASSUMPTIONS #92). When the work moves to another machine (the Mac), re-run the baselines there.

**Beating B2.** Under each table the leaderboard prints the bar: max(B2 best observed, best-of-baselines total).
B2 best observed is the best B2 per-seed total covering every instance; the best-of-baselines total sums, over the
set's instances, the most residents any of B0-B3 delivered. A recorded observation of an earlier session of the same
cloud VM (`docs/recorded_observations.json`: the Phase 0 review's B2 run, 1750, and the best-of-baselines total 1751 of
the rows at `b43990bb`, both on dev at 60 s) raises the matching part, but only when this session's own rows define
it: without B2 rows covering every instance in the session there is no bar. On this cloud VM the dev bar at 60 s is
therefore at least 1751, as Siyeong stated it. A method beats B2 only if it has at least 5 repeats, each covering
every instance, none of its rows over the budget, and its worst per-seed total exceeds the bar (`docs/ASSUMPTIONS.md`
#90, #93).

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
and B2 crashes. The editable installs write git-ignored `src/*.egg-info` folders into `evacplan/` and
`hazard_contract/`, nothing else. The test suite takes about ten minutes on the cloud VM (B2, B3, E1 and E4 run with
short budgets), so it runs only through the bench lock: started any other way it exits with code 75 and says why
(`tests/conftest.py`; `EVACPLAN_TESTS_UNLOCKED=1` lets a light selection run while nobody holds the lock):

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r evacplan/requirements.lock
uv pip install --python .venv/bin/python --no-deps -e hazard_contract -e evacplan
echo "$PWD/integration/src" > "$(.venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')/wfg_latest_src.pth"
.venv/bin/python program/benchlock.py --label evacplan-tests -- .venv/bin/python -m pytest evacplan/tests
```

The adapter tests read the fetched study graphs and packets from `$WFG_ROUTING_INPUTS` (no default
location) and skip, saying why, when the variable is unset or the folder has no `graphs/`; that data is never
copied into the repo. Road data from OpenStreetMap is © OpenStreetMap
contributors (ODbL 1.0).
