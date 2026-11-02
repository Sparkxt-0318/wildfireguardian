# Explainable leave-by deadlines (`wfg.explanation/1`)

For every origin (village or care facility) of the six recorded 2025 planner caches, this package answers
"why is the leave-by time (출발 마감) HH:MM?" and, for `model_no_route` origins, "why is there no checked route?" —
with a structured, re-checkable answer, or an explicit `not_explainable` when no reason can be established
rigorously. It never modifies routing, forecast or checking code; it reads the recorded results and the frozen inputs.

```sh
python3.12 -m venv .venv && .venv/bin/python -m pip install -c constraints-routing.txt './integration[packets]' pytest hypothesis==6.170.13
.venv/bin/python tools/fetch_routing_inputs.py                      # frozen graphs + hazard packets (SHA-verified)
.venv/bin/python -m tools.explain_deadlines generate                 # writes planner/public/data/explanations/*.json (~2 min)
.venv/bin/python -m tools.explain_deadlines check --tmp /tmp/wfg-x  # regenerate and compare (all but run stamps)
.venv/bin/python -m pytest -q tests/explain_deadlines                # hand-computed, property and real-data tests
```

## 1 Inputs and identity (fail-closed)

| Input | Check before use |
|---|---|
| `planner/cache/<region>/<input>.json` | sha256 equals its `planner/cache/INDEX.json` entry |
| `data/routing/graphs/<region>/graph.json` | sha256 equals `INPUT_FILES.json` of the release archive and the `input_hashes.graph` of **every** cached route check and dispatch plan |
| `data/routing/latest_inputs_try02/packets/<region>/<input>/` (`HAZARD.json`, `REPORT.json`, `NATIVE_METADATA.json`, `constructed_arrays.npz`) | each sha256 equals `INPUT_FILES.json` and the `input_hashes` (`hazard`, `packet/*`) recorded by every cached route check; members equal `<scenario_set_id>:0..3`; `time_origin` equals the input time; every cached check is `recorded`/`full` with the same scenario set |
| `HAZARD.json` vs `constructed_arrays.npz` | for every member and cell the router's flame bins equal the npz phase with the writer's rounded-up extinction (`Packet.verify_consistency`) |

Any mismatch stops the run; nothing is written. Each output records the cache, packet and graph hashes, the number of
cached jobs whose hashes were verified, the generating commit (`code_commit`, `code_dirty`) and the places file.

## 2 The deadline being explained

`plans.py` mirrors `planner/src/api/cache.ts::cacheToModel` and `planner/src/domain/plan.ts::planFromAttempts`
line by line (dispatch attempts, re-checks replacing the attempt they re-ran, research route checks, "시간창 밖"
window skips, refused requests). D is the planner's `latestSafeDepartureS` (latest offset whose cell has any
`checked_route`), the shown route is the planner's `best` attempt at D (earliest arrival, then destination id) and
N = the next offset of the planner's sweep. The real-data test asserts these equal the planner's values for all 530
origins.

Routes: the cache stores vertex times, node ids, edge ids and merged waits, not legs. `plans.reconstruct_legs`
rebuilds the router's legs (`EDGE` per edge; a run of 1 s `WAIT` legs per wait) and accepts them only if their
canonical hash equals the recorded `route_sha256` (the router's own `canonical({legs, destination, arrival})`).
All 7,771 cached checked routes (3 of them with waits) rebuild exactly; there is no ambiguity left to resolve.

## 3 Contact rule (replicated exactly)

A recorded `checked_route` passed two contact tests; a journey meets flame if **either** finds contact in **any**
of the four members (every member must be clear, so "k of 4" counts the members that block it):

1. **Closed footprint** — the mandatory runtime whole-road check, `integration/kit/routing_candidate/baseline/contact_first.py`
   (`check_contact`), segments from `mission_contract.prepare_mission`: ISSUE (start point at departure), every EDGE
   leg (straight chord u→v over [start, end]), every WAIT leg, DWELL (destination point over [arrival, arrival+dwell];
   the request's `exposure_scope` is `including_dwell`). For each burning cell whose **closed** 375 m rectangle meets
   the closed segment (`clip_closed_rectangle`), the **closed** occupancy [enter, leave] meets the **half-open** phase
   [birth, expiry) iff w = max(enter, birth) ≤ leave and w < expiry; w is the contact time. Present fire burns on
   [0, R) (`initial_remaining_s`, scalar max-remaining enclosure), a first-new ignition at b on [b, b+T). Exact
   rationals throughout. `api/runner.py` turns any non-`CLEAR` result into `unresolved`.
2. **Router cells** — `routing-package/routing/core.py` (`edge_occupancies`, `evaluate_occupancy`) on `HAZARD.json`:
   the chord is cut at interior grid lines, each open piece belongs to the cell of its midpoint and each cut point to
   its floor cell; an occupancy (cell, [lo, hi]) is sampled at lo, hi and every breakpoint strictly inside, bin
   min(n−1, bisect_right(bp, p)−1) (half-open bins, last bin closed at the horizon). Dwell, waits and the issue point
   use the node's cell.

Every router occupancy lies inside its cell's closed rectangle during a sub-interval of that cell's closed-rule
occupancy, so router contact implies closed contact (property-tested). The closed rule therefore decides the first
contact; `rules` in each item reports which rules see it. Contacts are only claimed at times ≤ the hazard horizon.

## 4 Classification

Checked origin with deadline D and next offset N = D + Δ:

| Situation at N | `reason_code` (`detail_code`) | `status` |
|---|---|---|
| no later offset (D is the last checked time) | `no_later_offset` (`last_checked_offset`) | explained |
| N is a "시간창 밖" cell: max(N, open) + dwell > close even with zero travel | `window` (`outside_recorded_arrival_window`) | explained |
| N `unresolved` | `unresolved_next` — stated plainly, never turned into a reason | not_explainable |
| N `model_no_route` | per shelter checked at D, below | |

For each shelter j with a checked route at D (the set C_D) at departure N:

* `window_fire_free` — N + fastest fire-free road time (exact turn-restricted search, `roads.fastest_ticks`) + dwell
  > window close. No route exists at all, fire or not.
* `flame_on_route` — the route checked at D, replayed rigidly shifted by Δ, first meets flame (rule above) on a
  moving segment. The binding item is that segment: `flame_time_s` = predicted flame start in the cell (birth),
  `pass_time_at_deadline_s` = when the vehicle leaving at D leaves that cell's footprint, `slack_s` = their difference
  (the smallest over the contact pairs; contact at shift s starts exactly at s = birth − leave), `contact_time_s` =
  when the vehicle leaving at N meets the flame, `members` = members with contact on that segment at N.
* `window_fire_detour` — `reach.flame_avoiding` finds no journey from N that reaches j by close − dwell. The
  relaxation keeps closed-footprint contact in every member for edge traversals and the issue point plus the router's
  movement rules, but allows waiting anywhere unchecked and ignores heat limits, so it contains every checked journey:
  "too late or unreachable even here" proves no checked route exists.
* `dwell` — the relaxation arrives in time but every stay [a, a+dwell] it allows meets flame.
* `open` — none of the above.

j is **proven** unreachable at N for `window_fire_free`, a late relaxation, or a blocked stay. The origin's reason is
the class of the shown route (`window` for both window classes); status is `explained` when every shelter of C_D is
proven, `explained_partial` otherwise or for `dwell_at_destination`, `not_explainable` (`refusal_not_reproduced`)
for `open`. Shelters attempted at N but without a checked route at D were already refused at D and are not part of
the change from D to N.

`model_no_route` origin: every attempted (offset, shelter) must be proven by the relaxation (turn restrictions also
dropped). If no shelter is reachable within the hazard window and the flame-free reachable area is closed by flame
alone (no edge cut by time), the reason is `all_exits_blocked`; `exits` lists every road leaving that area
(`reached_at_s` = earliest time the vehicle can be there; each is flame-blocked for every start second from then until
the window ends; departing later cannot help because the relaxation may wait at the start). Otherwise the reason is
`window` (`no_flame_avoiding_route_fits_window`). **The literal "first edges out of the entry point" are open in 10 of
the 11 recorded `model_no_route` origins; the blockage lies further out, so the exits reported are the roads where the
flame-free area ends.** `unresolved` origins: `not_explainable` (`origin_unresolved`), with their attempt verdicts.

## 5 Validation (counts in every file's `summary.validation`; a failure withdraws the explanation)

| id | assertion (exact arithmetic) | applicable / passed / failed (all 6 files) |
|---|---|---|
| a | at D the shown route is clear on the binding segment in every member and leaves every contact cell before the flame arrives (0 < slack ≤ Δ) | 8 / 8 / 0 |
| a_route | every route checked at D is flame-free along its whole journey at its recorded times (re-verifies packet identification) | 507 / 507 / 0 |
| b | at N the shifted route meets flame on the binding segment in exactly the stated members, and on no earlier segment (either rule) | 8 / 8 / 0 |
| c | every event time (deadline, next offset, flame, contact and pass times) lies in the packet's [valid_from, valid_until] | 517 / 517 / 0 |
| w | window claims re-derived; fire-free claims also hold with an independent node Dijkstra lower bound that ignores turn restrictions | 150 / 150 / 0 |
| e | every exit is startable before the window ends yet flame-blocked at every start second; no edge cut by time; every attempt proven | 11 / 11 / 0 |
| kit_a_route | the kit's frozen independent checker (`runner/ffi_independent_checker.py`, sha256 pinned in `CANDIDATE_MANIFEST.json`; reads the npz, not `HAZARD.json`): `whole_road_contact` CLEAR and router-conservative `centre_model` without contact for every route checked at D | 507 / 507 / 0 |
| kit_b | the same checker on the shifted route truncated after the binding leg: earliest witness per member on the binding segment, exact contact time equal, same member set | 8 / 8 / 0 |

## 6 Labels

The routing graph's edges carry an OSM way id (`source_way`) but no `name`/`ref`, and `planner/data/osm` holds places
and facilities, not roads, so no road name can be established from repository data. Items therefore name the nearest
OSM `place=*` (village, hamlet, town, …) with its distance from the contact point (`label_source: nearest_place`,
`place_osm_id`, `place_distance_m`; 399–1,885 m for the 25 items written), or `unnamed` with the road node beyond
5 km. `label_en` is OSM `name:en` or null (never transliterated). `osm_way_id` lets a reader look the road up.

## 7 Output schema `wfg.explanation/1`

One file per cache file: `planner/public/data/explanations/<region_id>__<inputYYYYMMDDTHHMMSSZ>.json`. All times are
seconds after `input_time`.

| Field | Meaning |
|---|---|
| `schema`, `region_id`, `input_time`, `scenario_set_id` | identity (equal to the cache file) |
| `provenance` | `cache_file`, `cache_sha256`, `packet_dir`, `packet_hashes`, `graph_sha256`, `code_commit`, `code_dirty`, `generated_at`, plus `graph_revision`, `inputs_release`, `places_file`/`places_sha256`, `hash_checks`, `kit_checker_sha256`, `horizon_s`, `members`, `contact_rule` |
| `summary` | `origins`, `explained`, `explained_partial`, `not_explainable`, `by_reason`, `by_status_reason`, `by_detail`, `validation` |
| `origins.<id>` | keyed exactly as the planner keys origins |
| `.status` | `explained` · `explained_partial` · `not_explainable` |
| `.verdict_summary` | the planner's best verdict: `checked_route` · `model_no_route` · `unresolved` |
| `.deadline_offset_s`, `.next_offset_s` | D and N (null when absent) |
| `.next_verdict` | `model_no_route` · `unresolved` · `window` (시간창 밖) · null |
| `.reason_code` | `flame_on_route` · `all_exits_blocked` · `dwell_at_destination` · `unresolved_next` · `window` · `no_later_offset` · `other` |
| `.detail_code` | finer machine code (sections 4, 5) |
| `.binding[]`, `.exits[]` | items: `edge_id`, `osm_way_id`, `label_ko`, `label_en`, `label_source`, `place_osm_id`, `place_distance_m`, `near_node_id`, `point` [lon, lat], `flame_time_s`, `contact_time_s`, `members` (scenario suffixes 0–3), `members_total`, `pass_time_at_deadline_s`, `slack_s` (null for exits), `segment` (`edge`/`issue`/`wait`/`dwell`); binding also `leg_index`, `destination_ids`, `rules`; exits also `reached_at_s` |
| `.window` | `close_s`, `dwell_s`, `fire_free`, `fastest_end_s` (fire-free earliest end of the stay leaving at N), `flame_avoiding_arrival_s` (relaxed arrival within the horizon, else null), `limit` (`scenario_window` · `arrival_window`), `horizon_s` |
| `.deadline_route` | the shown route: `route_check_job_id`, `destination_id`, `departure_s`, `arrival_s`, `dwell_s`, `route_sha256`, `raw_status` |
| `.checked_at_deadline`, `.proven_unreachable_next`, `.destination_classes`, `.next_attempts`, `.next_attempt_verdicts`, `.attempt_verdicts`, `.reachable_nodes`, `.first_offset_s`, `.origin_kind` | supporting counts and classes |
| `.checks` | assertion results that applied to this origin (all `true` in the committed files) |
| `.notes` | audit codes, not shown in the UI |

## 8 Results (the six recorded 2025 caches, 530 origins)

| region / input (UTC) | origins | explained | partial | not_expl. | flame_on_route | window | all_exits_blocked | no_later_offset | unresolved_next | other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| uiseong_andong_2025 2025-03-23T01:00Z | 86 | 86 | 0 | 0 | 5 | 44 | 1 | 36 | 0 | 0 |
| uiseong_andong_2025 2025-03-24T09:00Z | 85 | 84 | 0 | 1 | 3 | 45 | 0 | 36 | 1 | 0 |
| uiseong_andong_2025 2025-03-25T17:00Z | 85 | 80 | 0 | 5 | 0 | 42 | 7 | 31 | 0 | 5 |
| yeongdeok_2025 2025-03-25T19:00Z | 92 | 87 | 0 | 5 | 0 | 4 | 2 | 81 | 0 | 5 |
| yeongdeok_2025 2025-03-25T23:00Z | 91 | 90 | 0 | 1 | 0 | 4 | 0 | 86 | 1 | 0 |
| yeongdeok_2025 2025-03-26T08:00Z | 91 | 89 | 0 | 2 | 0 | 4 | 0 | 85 | 0 | 2 |
| **total** | **530** | **516** | **0** | **14** | **8** | **143** | **10** | **355** | **2** | **12** |

`window` = 136 `window_fire_free` + 6 `window_fire_detour` + 1 `no_flame_avoiding_route_fits_window`; `other` = 12
`origin_unresolved`. No `dwell_at_destination` case occurs. **Most leave-by times in these recorded replays are set by
the one-hour scenario range, not by a predicted flame**: 355 are simply the last departure checked (50 min after the
input time) and 136 cannot finish the 2-minute stay before the window ends even on fire-free roads. A predicted
flame contact on the shown route binds 8 deadlines (each in 1 of 4 members, from first-new ignitions); flame-forced
detours that no longer fit bind 7; 10 `model_no_route` origins are cut off by fire already burning at the input
time (4 of 4 members).

## 9 Limitations

- Explanations are model-relative: four scenario members drawn independently per cell from the forecast, a
  scalar present-fire enclosure, a one-hour hazard horizon, OSM roads at an assumed 40 km/h; not observations.
- `flame_on_route` is a counterfactual about the shown route; that no other route exists at N rests on the
  relaxation proof (and on the API's recorded refusal), not on the replay alone.
- Heat limits (10 kW/m², 100 kJ/m²) never needed to be invoked: every recorded refusal here is reproduced by contact
  and timing alone. A refusal that only heat limits explain would be reported `not_explainable`.
- Results computed on the evaluated macOS host are explained as recorded; nothing is recomputed.
- Road names are not available from repository data (section 6).
