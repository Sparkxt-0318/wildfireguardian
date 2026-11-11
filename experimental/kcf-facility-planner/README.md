# KCF facility planner — vehicle-delay demonstration

Opt-in experimental planner for a Korea Code Fair interview. A judge changes one input — **“the second vehicle will arrive ten minutes late”** — and sees, for a **fictional** care facility, which group can still move, which road each vehicle can take at its actual traversal time, when the last group finishes unloading, and which part still needs a person to check.

Planning aid only. Fictional fixtures, no resident data, no real road status. Not for live evacuation decisions.

## Run (offline, Python 3.10+ standard library only)

```bash
cd experimental/kcf-facility-planner
python3 demo.py
```

Opens `http://127.0.0.1:8765/` (use `--no-browser`, `--port N`). No internet, map tiles, credentials or absolute paths. The page is Korean-first: pick **주 사례: 차량 2대** or **별도 사례: 차량 1대 왕복**, choose a delay (buttons 0–30 min or slider 0–60 min), and the planner recomputes both journeys. It shows status, final unloading, people with checked transport and people still awaiting it, the binding constraint, a before/after timeline (preparation, hold, boarding, travel, empty return, unloading, road constraints), per-vehicle schedule with availability distinct from departure, a schematic road diagram (not a map), and a human-check list.

Without a browser:

```bash
python3 demo.py --text --delay 10
```

```bash
python3 demo.py --text --case shuttle --delay 0
```

A single self-contained HTML (all 0–60 min delays precomputed by the planner, opens from `file://`):

```bash
python3 demo.py --export out/
```

## What the fictional two-vehicle fixture shows

`fixtures/demo_two_vehicle.json`: facility FAC → shelter SH; V1 available T+10:00, V2 T+15:00, 6 seats each, groups of 6; boarding and unloading 5 min; main road via the bridge (4.7 km) with a simulated fire restriction on 삼거리→하천교 from T+30:00; a detour (11.6 km) whose 우회 고개→저수지길 segment has an unknown (missing-forecast) interval T+46:40–T+55:00; horizon T+70:00; shelter accepts arrivals T+10:00–T+75:00.

| V2 delay | Status | Final unloading | What happens |
|---|---|---|---|
| 0 | CHECKED_ROUTE | T+35:00 | both vehicles on the main road |
| 5 min | CHECKED_ROUTE | T+40:00 | V2 leaves the restricted segment exactly at T+30:00 (touching allowed) — flagged as 0 s margin |
| **10 min** | **CHECKED_ROUTE** | **T+56:40** | main segment closed when V2 reaches it (T+32:00) → detour; 60 s margin to the unknown interval flagged |
| 15, 20 min | MISSING_INPUT | — | detour feasible only if the unknown interval is open; G1 (6 people) checked, G2 awaiting |
| 25 min | MODEL_SCOPED_NO_ROUTE | — | `OUT_OF_HORIZON` (would need time past T+70:00) and closures |
| 30 min | MODEL_SCOPED_NO_ROUTE | — | `DESTINATION_WINDOW` and closures; not out-of-horizon |

V1 is unchanged in every row. These values are produced by the planner and asserted in `tests/test_demo.py`.

**Separate one-vehicle shuttle case** (`fixtures/demo_shuttle.json`, horizon T+100:00): V1 carries G1, unloads, returns empty — via the detour, because the main road closes at T+30:00 and the U-turn at the shelter is forbidden — reloads G2 and drives out again: final unloading T+83:20. A 5-minute delay makes the return cross the unknown interval (MISSING_INPUT); 15 minutes leaves no schedule in the window. No second vehicle is ever introduced.

## Recorded historical example (provenance only)

The archived retrospective Uiseong–Andong exercise (two vehicles, six fictional residents each, no return, endpoints ≈ 4.5 km apart) changed from 602 s / 6.041 km to 1,288 s / 12.650 km under a conservative all-horizon modelled fire restriction; the restriction was simulated and final cumulative heat exposure was unresolved ([November research note](../../research/november-20261111/README.md)). Its source records (`FINAL_CASE.md`, `fl2_long_*`, `INDEPENDENT_REVIEW.md`) were not available in this environment, so that case is **not** replayed or recomputed here, and its numbers are not expected results of this time-dependent planner. The page shows them as labelled text only.

## Interface for other agents

```bash
python3 cli.py --case INPUT.json --output RESULT.json
```

Contract, statuses and exact field names: [SCHEMA.md](SCHEMA.md), [examples/trip_fields.json](examples/trip_fields.json). Examples: `examples/sample_case_*.json` with their `sample_result_*.json`. What is and is not checked: [CONSTRAINTS.md](CONSTRAINTS.md). Measurements: [MEASUREMENTS.md](MEASUREMENTS.md).

## How it works

* `kcf_planner/solver.py` — per leg, a time-dependent Dijkstra over incoming-edge states (waiting allowed, so earliest time per state dominates; turn rules use the incoming edge), with earliest-departure edge transitions under the `[entry, exit)` positive-overlap rule. Multi-leg shuttles are solved exactly by dynamic programming over the leg-end incoming edge. Supported view blocks closed + unknown; optimistic view blocks closed only. Waits are then moved as early as possible on the same road sequence, so residents wait at the facility rather than at a junction.
* `kcf_planner/planner.py` — status rules, partial coverage only with a witness, missing information, counterfactual diagnostics.
* `kcf_planner/replay.py` — independent witness replay from the raw JSON (shares no code with the solver); `kcf_planner/sipp_check.py` — cross-check of each leg with the existing `experimental/sipp-routing` module (`wfg_sipp` SIPP, brute-force lattice, journey predicate). A failing witness is withheld (`UNRESOLVED`).
* `tests/oracle.py` — second-by-second brute-force oracle used to check status, optimal final unloading and checked coverage on thousands of random cases.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

`KCF_RANDOM_CASES=20000` enlarges the random oracle comparison (default 1,500).

## Limits

Toy contract: no heat exposure (JS-9/JS-10), road capacity, vehicle interaction, destination capacity, node hazards, loading variability or real road data. Fictional fixtures only; the research scenario's thermal checks and limits remain separate and unresolved. Distances shown are fixture metadata, not computed from geometry.
