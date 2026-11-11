# Portable case contract (schema_version 1)

```bash
python3 cli.py --case INPUT.json --output RESULT.json
```

Paths may be absolute or relative. The result is written atomically (temporary file in the same directory, `fsync`, `os.replace`); the output directory is created if needed. Python 3.10+ standard library only, no network.

Exit codes: `0` a result was written (any planning status); `2` invalid input (an `INVALID_INPUT` result is still written); `3` internal error (an `UNRESOLVED` result with `INTERNAL_ERROR` is written).

Independently runnable examples: `examples/sample_case_shuttle.json` → `examples/sample_result_shuttle.json`, `examples/sample_case_parallel_delayed.json` → `examples/sample_result_parallel_delayed.json`, `fixtures/contract/missing_input.json` → `examples/sample_result_missing_input.json`. Exact field names and types are machine-readable in [`examples/trip_fields.json`](examples/trip_fields.json).

## Input

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `1` | required, exactly 1 |
| `case_id` | string | echoed in the result |
| `horizon_s` | int ≥ 0 | last second covered by the model; every edge exit and unloading end must be ≤ `horizon_s` (equality allowed) |
| `origin`, `destination` | string | distinct node names (nodes are implicit in edges) |
| `edges` | list | `{"id","u","v","travel_s","closed","unknown"}`; `travel_s` int ≥ 1; intervals `[start,end]` ints with `end ≥ start` |
| `vehicles` | list | `{"id","available_s","seats"}` |
| `groups` | list (≥ 1) | `{"id","people"}`, `people` ≥ 1 |
| `board_s`, `unload_s` | int ≥ 0 | boarding / unloading durations |
| `destination_window` | `[open, close]` | arrival ≥ `open`; unloading end ≤ `close` |
| `forbidden_turns` | list of `[in_edge_id, out_edge_id]` | consecutive pairs that may not be driven |
| `mode` | `"parallel"` \| `"shuttle"` | see below |

Optional presentation fields (`title`, `title_ko`, `note_ko`, `node_labels_ko`, `node_xy`, `provenance`, edge `length_m`, `name_ko`, vehicle/group `name_ko`) never change the computation. Unrecognised fields are ignored and listed in `assumptions`.

### Semantics

* Integer seconds from exercise origin. Driving edge `e` entered at `d` occupies `[d, d + travel_s)`.
* **Closed:** forbidden if `[d, d+travel_s)` has positive-duration overlap with a closed `[a, b]`, i.e. `max(d,a) < min(d+travel_s, b)`. Touching at an endpoint is allowed. Zero-length intervals therefore never block (noted in `assumptions`).
* **Unknown:** same overlap test. A **checked** (supported) schedule never overlaps an unknown interval. Unlisted times within the horizon are known and open.
* **Waiting** is allowed at every node (nodes are assumed supported and open) and keeps the incoming edge, so `forbidden_turns` apply to the next edge after any wait, and across shuttle legs (unloading and reloading included).
* **Boarding** lasts `board_s` and begins no earlier than vehicle availability (first trip) or return arrival (later trips). The planner places boarding to end exactly at departure, so any hold happens at the facility before residents board.
* **Arrival** at the destination counts only as an edge arrival with `open ≤ arrival` and `arrival + unload_s ≤ min(close, horizon_s)`. Waiting at the destination is not an arrival; a vehicle that would be early must arrive later by a road.
* **parallel:** group *i* uses vehicle *i*; one outbound trip each, no return. Extra vehicles stay idle (noted). A group without a vehicle is not covered — no vehicle is introduced (`NO_VEHICLE_ASSIGNED`).
* **shuttle:** exactly one vehicle (otherwise `INVALID_INPUT`) carries groups in listed order: outbound, unload, empty return, board, outbound, … ; no return after the last group.
* A group larger than its vehicle's seats cannot be carried (`CAPACITY`).
* Objective: minimise the final unloading end over fully supported legal schedules.

## Status

| Status | Meaning | `final_unload_s` |
|---|---|---|
| `CHECKED_ROUTE` | every group has a fully supported, legal witness in `trips` (optimal final unloading) | int |
| `MISSING_INPUT` | no supported schedule exists (proved), but one exists if unknown intervals were open; witness in `conditional_trips`, every touched unknown interval in `missing_information` | null |
| `MODEL_SCOPED_NO_ROUTE` | no legal schedule even with every unknown interval open (exhaustive within this model) | null |
| `UNRESOLVED` | label cap / time limit before a proof, an internal error, or an emitted witness failed the independent replay (`WITNESS_REPLAY_FAILED`) — never a no-route claim | null |
| `INVALID_INPUT` | malformed input; `reason` names the rule | null |

`reason_codes` for `MODEL_SCOPED_NO_ROUTE` separate explanations: `CAPACITY`, `NO_VEHICLE_ASSIGNED`, `DESTINATION_WINDOW_TOO_SHORT`, `OUT_OF_HORIZON` (a schedule would exist only by using time past `horizon_s`, which is outside the model), `DESTINATION_WINDOW` (only a later window close would help), `CLOSURES_BLOCK_ALL_ROUTES`, `CLOSURES_AND_TIME_LIMITS`, `NO_PATH_IN_ROAD_MODEL`. They come from clearly labelled hypothetical counterfactual runs in `diagnostics`. `PARTIAL_SUPPORTED_COVERAGE` is added whenever some, but not all, groups have a witness in `trips`.

Coverage: `people_with_checked_transport` counts only groups that have a supported outbound trip in `trips`; when the status is not `CHECKED_ROUTE` these are a witnessed subset (for shuttle, the longest deliverable prefix of the listed order). `people_awaiting_checked_transport = people_total − people_with_checked_transport`.

## Result trip fields

`vehicle_id`, `kind` (`outbound` | `empty_return`), `group_id` (null for returns), `people`, `seats`, `start_node`, `end_node`, `incoming_edge_at_start`, `ready_s`, `boarding_start_s`, `boarding_end_s`, `departure_s`, `arrival_s`, `unloading_start_s`, `unloading_end_s` (boarding/unloading null for returns), `edges` = ordered `{edge_id, from, to, entry_s, exit_s}`, `waits`, `binding_constraints`, `uses_unknown_input`, `trip_id`, optional `length_m`. See `examples/trip_fields.json`.

Every result also carries `verification.independent_replay` (rules R-* in [CONSTRAINTS.md](CONSTRAINTS.md)) and `verification.wfg_sipp` (cross-check with the repository's SIPP module). A witness that fails either is withheld: status becomes `UNRESOLVED` with `gated_from_status`.

Options: `--max-labels N` (default 2,000,000 settled labels), `--time-limit S`, `--no-crosscheck` (skips wfg_sipp; replay always runs).

## Interpretation notes (documented choices on ambiguous points)

* **Self-loops / re-entry:** any edge into the destination is a road arrival. A vehicle that is early may leave and re-enter (including via a self-loop edge `C→C` if the input lists one); that traversal is a new admission arrival. Waiting alone never is.
* **`INVALID_INPUT`** is a fifth status used only for malformed input (with exit code 2); `groups_total`/`people_total` are null then because the input could not be trusted. Shuttle mode with zero or several vehicles is invalid input rather than a silent choice of vehicle.
* **Reason codes with several failing groups:** structural codes (`CAPACITY`, `NO_VEHICLE_ASSIGNED`) are always reported; counterfactual codes describe the whole case, so a second group's time-related cause may be visible only in `failures`.
* **MISSING_INPUT witness:** vehicles that already have a supported schedule keep it inside `conditional_trips`; only the remaining vehicles rely on unknown intervals, and `missing_information` lists exactly the unknown intervals that witness touches (as listed in the input, not merged).
* Counterfactual diagnostics share the label cap and remaining time limit; if they are cut short the code is `DIAGNOSTICS_INCOMPLETE` (the no-route result itself remains proved).
