# evacplan — Track C: care-facility wildfire evacuation dispatch planner

Status: milestone **C0-oracle** (schema, validator, feasibility oracle). Generators, harness and
baselines come next. Rules and the problem definition: [`CLAUDE.md`](CLAUDE.md); every modelling
choice: [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md).

| module | what |
|---|---|
| `evacplan.schema` | Problem v0 `Instance` / `Solution` (pydantic v2), JSON I/O, hazard folder resolution |
| `evacplan.validate` | hazard-free validator: timeline of occupancies and issue codes (resources, times, paths) |
| `evacplan.oracle` | **the** oracle (program rule 3): `check_plan`, `check_itinerary`, `Oracle`; the RELAXED `RelaxedContactCheck` for search loops |
| `evacplan.adapters.wfg_graph` | this repo's router `graph.json` → `RoadGraph` (router admission reused) |

Hazards come in only through `hazard_contract`. Every leg and trip gets exactly one of `checked`,
`model_no_route` (scoped to the hazard model, its K members and horizon) or `unresolved` (never safe,
never delivered).

```python
from evacplan import check_plan, load_instance, load_scenario_set, load_solution
inst = load_instance("instance.json")             # hazard folder is relative to this file
result = check_plan(inst, load_scenario_set(inst), load_solution("solution.json"))
print(result.summary(), result.scope.model_version)
```

Install (editable, into the worktree venv; `hazard_contract` and `wfg_latest` are installed from
this repo, not from an index) and test:

```sh
uv pip install --python .venv/bin/python --no-deps -e evacplan
.venv/bin/python -m pytest evacplan/tests
```

The adapter tests read the fetched study graphs and packets from `$WFG_ROUTING_INPUTS` and skip
when they are absent; that data is never copied into the repo.
