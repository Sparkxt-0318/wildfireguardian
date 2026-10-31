# evacplan — Track C: care-facility wildfire evacuation dispatch planner

Status: Phase 0. Done: schema, validator and feasibility oracle (milestone **C0-oracle**); SYNTHETIC
instance generators, the frozen `dev`/`test` split and the benchmark harness. Real US region 1 (Caldor Fire
2021, South Lake Tahoe): builder written, build **BLOCKED** on the cloud container (no inputs, hosts
blocked). Baselines B0-B3 come next. Rules and the problem definition: [`CLAUDE.md`](CLAUDE.md); every
modelling choice: [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md); results: [`LEADERBOARD.md`](LEADERBOARD.md).

| module | what |
|---|---|
| `evacplan.schema` | Problem v0 `Instance` / `Solution` (pydantic v2), JSON I/O, hazard folder resolution |
| `evacplan.validate` | hazard-free validator: timeline of occupancies and issue codes (resources, times, paths) |
| `evacplan.oracle` | **the** oracle (program rule 3): `check_plan`, `check_itinerary`, `Oracle`; the RELAXED `RelaxedContactCheck` for search loops |
| `evacplan.generators` | SYNTHETIC instances: grid / random geometric roads, facilities, fleet, shelters, a `hazard_contract.synthetic` fire that threatens the facilities; deterministic from `(size, tightness, graph, seed)` |
| `evacplan.instances` | the frozen split (`instances/SPLIT.json`), fingerprints, the regenerated instance cache |
| `evacplan.harness`, `evacplan.methods` | `evacplan run`: budgets, bench lock, oracle-checked result rows, `LEADERBOARD.md`; the method interface and `noop` |
| `evacplan.regions` | real regions: OSM roads (osmnx), CMS nursing homes + geocoding, perimeters (`from_perimeters`), SYNTHETIC residents and fleet; `regions.caldor` |
| `evacplan.adapters.wfg_graph` | this repo's router `graph.json` → `RoadGraph` (router admission reused) |

Hazards come in only through `hazard_contract`. Every leg and trip gets exactly one of `checked`,
`model_no_route` (scoped to the hazard model, its K members and horizon) or `unresolved` (never safe,
never delivered).

## Harness

```sh
# timed runs hold the shared bench lock (taken by the harness itself, or by a parent benchlock.py)
.venv/bin/python program/benchlock.py --label evacplan-noop -- \
    .venv/bin/evacplan run --method noop --set dev --budget-s 60 --seeds 0
.venv/bin/evacplan leaderboard                 # regenerate LEADERBOARD.md from results/*.csv
.venv/bin/evacplan instances --set dev          # the frozen dev instances (add --materialize to cache them)
```

`results/<method>.csv` (git-ignored) has one row per instance, seed, budget and set: `instance, method,
seed, delivered_checked, unresolved, model_no_route, makespan_s, min_slack_s, runtime_s, best_bound, gap,
commit, config, host`. Every number comes from the oracle. `--set test` is refused without `--allow-test`
(milestones only, after Siyeong approves). A method subclasses `evacplan.methods.Method` and is registered in
`evacplan.methods`.

## Instances

`instances/SPLIT.json` was frozen before any method ran: `dev` and `test` each have 4 S + 4 M + 2 L
SYNTHETIC instances (disjoint seeds, same mix). They regenerate into `cache/instances/<id>/` (git-ignored)
and must match their fingerprints. One-off instances: `evacplan generate --size M --tightness 0.5 --graph geo
--seed 7 --out DIR`.

`evacplan build-caldor` builds real US region 1 from a road GraphML, the CMS provider file, geocodes and
perimeters; without them it prints `BLOCKED` and exactly what it needs.

## Install and test

Editable, into the worktree venv (`hazard_contract` and `wfg_latest` are installed from this repo, not
from an index); the test suite takes about a minute, so run it through the bench lock:

```sh
uv pip install --python .venv/bin/python --no-deps -e evacplan
.venv/bin/python program/benchlock.py --label evacplan-tests -- .venv/bin/python -m pytest evacplan/tests
```

The adapter tests read the fetched study graphs and packets from `$WFG_ROUTING_INPUTS` and skip when they
are absent; that data is never copied into the repo. Road data from OpenStreetMap is © OpenStreetMap
contributors (ODbL 1.0).
