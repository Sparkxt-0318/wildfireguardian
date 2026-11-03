# Explainable leave-by deadlines (`wfg.explanation/1`)

For every origin (village or care facility) of the six recorded 2025 planner caches, this package answers
"why is the leave-by time (출발 마감) HH:MM?" and, for `model_no_route` origins, "why is there no checked route?" —
with a structured, re-checkable answer, or an explicit `not_explainable` when no reason can be established
rigorously. It never modifies routing, forecast or checking code; it reads the recorded results and the frozen inputs.

```sh
python3.12 -m venv .venv && .venv/bin/python -m pip install -c constraints-routing.txt './integration[packets]' pytest hypothesis==6.170.13
.venv/bin/python tools/fetch_routing_inputs.py                      # frozen graphs + hazard packets (SHA-verified)
.venv/bin/python -m tools.explain_deadlines generate                 # writes planner/public/data/explanations/*.json (~3 min)
.venv/bin/python -m tools.explain_deadlines check --tmp /tmp/wfg-x  # regenerate and compare (all but run stamps)
.venv/bin/python -m pytest -q tests/explain_deadlines                # hand-computed, property and real-data tests
```

The route checks shown by the planner are recorded results of the evaluated host; this tool runs no new route checks.
Everything else in an explanation is computed by this tool on the machine that runs it, which the files record
(`provenance.computed_on`, `provenance.evaluated_host`; section 10). The committed files were computed in a Linux x86_64
container: `evaluated_host` is `false`.

## 1 Inputs and identity (fail-closed)

| Input | Check before use |
|---|---|
| `planner/cache/<region>/<input>.json` | sha256 equals its `planner/cache/INDEX.json` entry |
| `data/routing/graphs/<region>/graph.json` | sha256 equals `INPUT_FILES.json` of the release archive and the `input_hashes.graph` of **every** cached route check and dispatch plan |
| `data/routing/latest_inputs_try02/packets/<region>/<input>/` (`HAZARD.json`, `REPORT.json`, `NATIVE_METADATA.json`, `constructed_arrays.npz`) | each sha256 equals `INPUT_FILES.json` and the `input_hashes` (`hazard`, `packet/*`) recorded by every cached route check; members equal `<scenario_set_id>:0..3`; `time_origin` equals the input time; every cached check is `recorded`/`full` with the same scenario set |
| `HAZARD.json` vs `constructed_arrays.npz` | for every member and cell the router's flame bins equal the npz phase with the writer's rounded-up extinction (`Packet.verify_consistency`) |
| time and grid | one routing tick is one second (`HAZARD.dt` = `REPORT` `routing_dt_s` = 1; graph `travel_ticks` positive integers); the scenario window is [0, `horizon_s`]; `REPORT` `affine_transform` and CRS equal the graph grid (the npz is read north-up on it); packet CRS equals the graph CRS |

Any mismatch stops the run before the file of that cache file is written (files of cache files processed earlier in the
same run are complete). So does any recorded route whose replay disagrees with its recorded result (section 5,
`replay_*`). Each output records the cache, packet and graph hashes, the number of cached jobs whose hashes were
verified, the generating commit (`code_commit`, `code_dirty`), the places file and where it was computed
(`computed_on`, `evaluated_host`).

## 2 The deadline being explained

`plans.py` mirrors `planner/src/api/cache.ts::cacheToModel` and `planner/src/domain/plan.ts::planFromAttempts`
line by line (dispatch attempts, re-checks replacing the attempt they re-ran, research route checks, "시간창 밖"
window skips, refused requests). D is the planner's `latestSafeDepartureS` (latest offset whose cell has any
`checked_route`), the shown route is the planner's `best` attempt at D (earliest arrival, then destination id) and
N = the next offset of the planner's sweep. `tests/planner/explain.test.ts` runs the planner's own TypeScript
`cacheToModel` on every recorded cache and asserts that each file's origins, verdict, D, N and shown route (job id and
destination) equal the planner's for all 530 origins; `tests/explain_deadlines/test_real_data.py` checks the same
against the Python mirror.

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
   min(len(bp)−2, bisect_right(bp, p)−1) (half-open bins, last bin closed at the horizon). Dwell, waits and the issue
   point use the node's cell.

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
| N `model_no_route` | per shelter, below | |

For each shelter j with a checked route at D (the set C_D) at departure N, the first class that applies:

* `window_fire_free` — N + fastest fire-free road time (exact turn-restricted search, `roads.fastest_ticks`) + dwell
  > j's close (its arrival window, at most the hazard horizon). No route exists at all, fire or not.
* `flame_on_route` — the route checked at D, replayed rigidly shifted by Δ, first meets flame (rule above) on a
  moving segment (issue point, edge or wait). The binding item is that segment: `flame_time_s` = flame start in the
  cell in the fire scenarios (birth), `pass_time_at_deadline_s` = when the vehicle leaving at D leaves that cell's
  footprint, `slack_s` = their difference (the smallest over the contact pairs; contact at shift s starts exactly at
  s = birth − leave), `contact_time_s` = when the vehicle leaving at N meets the flame, `members` = members with
  contact on that segment at N; `slack_cell` is the cell of the smallest margin, `contact_cell` that of the earliest
  contact (equal in all 8 recorded items).
* `window_fire_detour` — `reach.flame_avoiding` finds no journey from N that reaches j by close − dwell. The
  relaxation keeps closed-footprint contact in every member for edge traversals and the issue point plus the router's
  movement rules, but allows waiting anywhere unchecked and ignores heat limits, so it contains every checked journey:
  "too late or unreachable even here" proves no checked route exists.
* `dwell` — the shifted route first meets flame during its stay at the shelter.
* `stay_blocked_without_shown_route_contact` — the shifted route meets no flame, yet every stay [a, a+dwell] the
  relaxation allows (a ≥ its earliest arrival, a + dwell ≤ close) meets flame.
* `open` — none of the above.

Shelters tried at N without a checked route at D (refused at D as well) are classed `window_fire_free`,
`flame_blocked` (relaxation late), `stay_blocked` or `open` by the same tests. A shelter is **proven** unreachable at N
for `window_fire_free`, a late relaxation, or a blocked stay. The candidate shelters are C_D and every shelter tried at
N (in the recorded data C_D is always among those tried at N); each is listed in `shelters_next` with its class,
close, fire-free end of the stay leaving at N and relaxed arrival.

**What keeps a later departure from working** (`deadline_cause`, over all candidate shelters):
`time_window` when none of them could be reached in time at N even without fire; `flames` when at least one would be
reached in time on a fire-free road but is proven unreachable on every flame-avoiding road (so without the fire a
later departure would work); null when neither is established. The origin's reason follows the shown route's class:

| shown route's class | `deadline_cause` | `reason_code` (`detail_code`) |
|---|---|---|
| `window_fire_free` | `time_window` | `window` (`window_fire_free`) |
| `window_fire_free` | `flames` | `no_flame_avoiding_route` (`other_shelters_flame_blocked`) |
| `window_fire_free` | null | `window` (`window_fire_free`), explained_partial |
| `window_fire_detour` | `flames` | `no_flame_avoiding_route` (`window_fire_detour`) |
| `flame_on_route` | `flames` | `flame_on_route` (`route_meets_flame_when_shifted`) |
| `dwell` | `flames` | `dwell_at_destination` (`stay_meets_flame`), always explained_partial |
| `stay_blocked_without_shown_route_contact`, `open`, unknown | — | `other` (that class, `refusal_not_reproduced`, `route_check_job_missing`, …), not_explainable |

Status is `explained` when every candidate shelter is proven and the cause is established, otherwise
`explained_partial` (and `not_explainable` for `other`).

`binding` holds one item per distinct first contact among the routes of C_D that are `flame_on_route`, the shown
route's item first (the UI reads only that one). Two routes share an item (`destination_ids`) only when every other
field of their items is identical (same road, times, members and leg); routes that reach the same burning road at
different times get separate items. Every route behind an item is validated on its own (section 5).

`model_no_route` origin: every attempted (offset, shelter) must be proven by the relaxation (turn restrictions also
dropped), else `other` (`refusal_not_reproduced`). If no attempt could finish in time even without fire, the reason is
`window` (`no_route_even_without_fire`, cause `time_window`). Otherwise the cause is `flames`: if no shelter is
reachable within the hazard window and every road leaving the flame-free reachable area is flame-blocked (none cut by
time), the reason is `all_exits_blocked` and `exits` lists those roads (edges from a reached node to a node never
reached; `reached_at_s` = earliest time the vehicle can be there; each is flame-blocked for every start second from
then until the window ends; departing later cannot help because the relaxation may wait at the start); otherwise
`no_flame_avoiding_route` (`no_flame_avoiding_route_fits_window`). **The literal "first edges out of the entry point"
are open in 10 of the 11 recorded `model_no_route` origins (in the 11th one of its two first edges is in flame at
departure); the blockage lies further out, so the exits reported are the roads where the flame-free area ends.**
`unresolved` origins: `not_explainable` (`origin_unresolved`), with their attempt verdicts.

## 5 Validation (counts in every file's `summary.validation`)

Per-origin assertions (a failure withdraws that origin's explanation: `not_explainable`, `validation_failed:<ids>`).
Counts are origins (an origin passes when every instance passes); a, b and kit_b run once per route behind a binding
item (21 routes for the 8 `flame_on_route` origins).

| id | assertion (exact arithmetic) | applicable / passed / failed origins (all 6 files) |
|---|---|---|
| a | at D the route is clear on the binding segment in every member and leaves every contact cell before the flame arrives (0 < slack ≤ Δ) | 8 / 8 / 0 |
| a_route | every route checked at D is flame-free along its whole journey at its recorded times (re-verifies packet identification) | 507 / 507 / 0 |
| b | at N the shifted route meets flame on the binding segment in exactly the stated members, and on no earlier segment (either rule) | 8 / 8 / 0 |
| c | every event time (deadline, next offset, flame, contact and pass times) lies in the packet's [valid_from, valid_until] | 517 / 517 / 0 |
| w | per candidate shelter: "out of reach even without fire" also holds with an independent node Dijkstra lower bound that ignores turn restrictions; "a fire-free road would fit" re-derived by a separate turn-restricted search; flame-avoiding claims re-derived by the relaxation (also without turn restrictions); `deadline_cause` follows from these claims | 150 / 150 / 0 |
| e | every exit is startable before the window ends yet flame-blocked at every start second; no road leaving the area cut by time; every attempt proven; fire-free fit (cause `flames`) or the node lower bound (`no_route_even_without_fire`) re-derived | 11 / 11 / 0 |
| kit_a_route | the kit's frozen independent checker (`runner/ffi_independent_checker.py`, sha256 pinned in `CANDIDATE_MANIFEST.json`; reads the npz, not `HAZARD.json`): `whole_road_contact` CLEAR and router-conservative `centre_model` without contact for every route checked at D | 507 / 507 / 0 |
| kit_b | the same checker on the shifted route truncated after the binding leg: earliest witness per member on the binding segment, exact contact time equal, same member set | 8 / 8 / 0 |

Route replays of the whole cache file (`validate.replay_recorded_routes`; counted in **routes**, `"unit": "route"`,
with the same `applicable`/`passed`/`failed` fields plus the named counts). Each route is rebuilt exactly (its legs
must hash to the recorded `route_sha256`) and replayed at its own recorded times — issue point, every leg and the
destination stay — with both contact rules of section 3. Any mismatch, or a route that cannot be rebuilt or compared
(`not_replayed`), **stops the run and nothing is written for that file**: it would mean the replay semantics differ
from the evaluated checker, which must then be fixed; routes are never filtered out.

| id | what is replayed and required | per file (uiseong_andong_2025 03-23T01, 03-24T09, 03-25T17; yeongdeok_2025 03-25T19, 03-25T23, 03-26T08) | all 6 files |
|---|---|---|---|
| `replay_checked_routes` | **every** `route_checks` entry with verdict `checked_route` (not only those at a deadline, which `a_route` covers): no contact in any member under either rule — `routes` / `contact_free` / `mismatches` | 1,188 / 1,158 / 1,029 / 1,400 / 1,486 / 1,510 routes, all contact-free | 7,771 / 7,771 / 0 |
| `replay_travel_only` | **every** `travel_only` route (router policy `travel_only`: flame contact not enforced): per member, contact under either rule must equal the API's recorded `result.full_policy_assessment.per_scenario[<member>].contact` (`api/runner.py`: the kit's exact-phase centre model OR a `whole_road_contact` witness), and the closed-rule status (`CLEAR` / `DEFINITE_CONTACT`) its `whole_road_contact` — `routes` / `matches` / `mismatches`; `member_flags` compared; `with_contact` = routes with recorded contact in some member | 85 / 85 / 73 / 84 / 91 / 89 routes, all matching; with contact 1 / 8 / 1 / 0 / 0 / 0 | 507 / 507 / 0 (2,028 member flags; 10 routes with contact) |

The travel-only comparison is not trivially "all clear": the 10 routes with recorded contact are reproduced in exactly
the recorded members. Both flags reduce to the closed rule: a centre-model contact (exact phases on the router's cell
pieces) is always a closed-rule contact, and a router-rule contact is one too except inside the sub-ulp gap between a
phase's exact expiry and the router's rounded-up extinction. A member with a router-rule contact only (inside that gap)
would show up in these counts: on a travel-only route as a mismatch (the replay flag, either rule, set; the recorded
flag, which reduces to the closed rule, clear), on a checked route as a contact. With 0 mismatches and every checked
route contact-free, no recorded route falls there.
Source: each file's `summary.validation`, written by `python -m tools.explain_deadlines generate`;
`tests/explain_deadlines/test_real_data.py` recounts the routes from the cache files (with the routing inputs
installed) and `tests/explain_deadlines/test_committed_files.py` checks these totals from the committed files alone.

## 6 Labels

The routing graph's edges carry an OSM way id (`source_way`) but no `name`/`ref`, and `planner/data/osm` holds places
and facilities, not roads, so no road name can be established from repository data. Items therefore name the nearest
OSM `place=*` node with a name (`label_source: nearest_place`; `place_osm_id`, `place_kind` = its `place` value) or are
`unnamed` (with the road node) when no named place lies within 5 km. `place_distance_m` is the straight-line distance in
metres (EPSG:5179, rounded) from the road point the item is about (binding: where the vehicle leaving at N first meets
the flame; exits: where a traversal started at `reached_at_s` first meets it) to that place node; it is not a distance
along the road and the place is not the road's name. `place_is_origin` is true when that place is the origin itself (16
of the 25 items written; all 25 are villages, 399–1,885 m). `label_en` is OSM `name:en` or null (never
transliterated). `osm_way_id` lets a reader look the road up. The UI writes "a road about {dist} from {name}" ("this
village" for the origin itself).

## 7 Output schema `wfg.explanation/1`

One file per cache file: `planner/public/data/explanations/<region_id>__<inputYYYYMMDDTHHMMSSZ>.json`. All times are
seconds after `input_time`.

| Field | Meaning |
|---|---|
| `schema`, `region_id`, `input_time`, `scenario_set_id` | identity (equal to the cache file) |
| `provenance` | `cache_file`, `cache_sha256`, `packet_dir`, `packet_hashes`, `graph_sha256`, `code_commit`, `code_dirty`, `generated_at`, `computed_on` (`platform`, `system`, `machine`, `python`, `numpy`, `pyproj` of the generating run), `evaluated_host` (section 10), plus `generator`, `graph_revision`, `inputs_release`, `places_file`/`places_sha256`, `hash_checks`, `kit_checker_sha256`, `horizon_s`, `members`, `contact_rule` |
| `summary` | `origins`, `explained`, `explained_partial`, `not_explainable`, `by_reason`, `by_status_reason`, `by_detail`, `validation` (per-origin assertion counts and the route-level `replay_*` entries, section 5) |
| `origins.<id>` | keyed exactly as the planner keys origins |
| `.status` | `explained` · `explained_partial` · `not_explainable` |
| `.verdict_summary` | the planner's best verdict: `checked_route` · `model_no_route` · `unresolved` |
| `.deadline_offset_s`, `.next_offset_s` | D and N (null when absent) |
| `.next_verdict` | `model_no_route` · `unresolved` · `window` (시간창 밖) · null |
| `.reason_code` | `flame_on_route` · `no_flame_avoiding_route` · `all_exits_blocked` · `dwell_at_destination` · `unresolved_next` · `window` · `no_later_offset` · `other` |
| `.detail_code` | `route_meets_flame_when_shifted`; `window_fire_detour`, `other_shelters_flame_blocked`, `no_flame_avoiding_route_fits_window`; `flame_free_area_closed`, `entry_point_in_flame`; `stay_meets_flame`; `next_offset_unresolved`; `window_fire_free`, `outside_recorded_arrival_window`, `no_route_even_without_fire`; `last_checked_offset`; for `other`: `origin_unresolved`, `refusal_not_reproduced`, `stay_blocked_without_shown_route_contact`, `route_check_job_missing`, `route_reconstruction_failed: …`, `recorded_route_contact`, `rule_subset_violation`, `several_start_nodes`, `validation_failed:<ids>` |
| `.deadline_cause` | `time_window` · `flames` · null (section 4) |
| `.shelters_next[]` | per candidate shelter at N: `destination_id`, `checked_at_deadline`, `tried_next`, `class`, `proven`, `close_s`, `dwell_s`, `fire_free_fits`, `fire_free_end_s` (null: no road within the hour), `flame_avoiding_arrival_s` |
| `.binding[]`, `.exits[]` | items: `edge_id`, `osm_way_id`, `label_ko`, `label_en`, `label_source`, `place_osm_id`, `place_kind`, `place_distance_m`, `place_is_origin`, `near_node_id`, `point` [lon, lat], `flame_time_s`, `contact_time_s`, `members` (scenario suffixes 0–3), `members_total`, `pass_time_at_deadline_s`, `slack_s` (null for exits), `segment` (`edge`/`issue`/`wait`/`dwell`); binding also `leg_index`, `destination_ids`, `rules`, `contact_cell`, `slack_cell`; exits also `reached_at_s` |
| `.window` | the shown shelter: `close_s`, `dwell_s`, `fire_free`, `fastest_end_s` (fire-free earliest end of the stay leaving at N), `flame_avoiding_arrival_s` (relaxed arrival within the horizon, else null), `limit` (`scenario_window` · `arrival_window`), `horizon_s` |
| `.deadline_route` | the shown route: `route_check_job_id`, `destination_id`, `departure_s`, `arrival_s`, `dwell_s`, `route_sha256`, `raw_status` |
| `.checked_at_deadline`, `.proven_unreachable_next`, `.destination_classes`, `.next_attempts`, `.next_attempt_verdicts`, `.attempt_verdicts`, `.reachable_nodes`, `.first_offset_s`, `.origin_kind` | supporting counts and classes |
| `.checks` | assertion results that applied to this origin (all `true` in the committed files) |
| `.notes` | audit codes, not shown in the UI |

## 8 Results (the six recorded 2025 caches, 530 origins)

| region / input (UTC) | origins | explained | partial | not_expl. | flame_on_route | no_flame_avoiding_route | window | all_exits_blocked | no_later_offset | unresolved_next | other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| uiseong_andong_2025 2025-03-23T01:00Z | 86 | 86 | 0 | 0 | 5 | 0 | 44 | 1 | 36 | 0 | 0 |
| uiseong_andong_2025 2025-03-24T09:00Z | 85 | 84 | 0 | 1 | 3 | 7 | 38 | 0 | 36 | 1 | 0 |
| uiseong_andong_2025 2025-03-25T17:00Z | 85 | 80 | 0 | 5 | 0 | 1 | 41 | 7 | 31 | 0 | 5 |
| yeongdeok_2025 2025-03-25T19:00Z | 92 | 87 | 0 | 5 | 0 | 1 | 3 | 2 | 81 | 0 | 5 |
| yeongdeok_2025 2025-03-25T23:00Z | 91 | 90 | 0 | 1 | 0 | 0 | 4 | 0 | 86 | 1 | 0 |
| yeongdeok_2025 2025-03-26T08:00Z | 91 | 89 | 0 | 2 | 0 | 0 | 4 | 0 | 85 | 0 | 2 |
| **total** | **530** | **516** | **0** | **14** | **8** | **9** | **134** | **10** | **355** | **2** | **12** |

`no_flame_avoiding_route` = 6 `window_fire_detour` + 2 `other_shelters_flame_blocked` + 1
`no_flame_avoiding_route_fits_window`; `window` = 134 `window_fire_free`; `other` = 12 `origin_unresolved`. No
`dwell_at_destination` case occurs. **Most leave-by times in these recorded replays are not set by flames in the fire
scenarios**: 355 are simply the last departure checked (50 min after the input time) and for 134 no candidate shelter
(checked at D or tried at N) could be reached in time from N even on fire-free roads (`deadline_cause` `time_window`).
Flames are the cause for 27 (16 leave-by times, 11 no-route origins; `deadline_cause` `flames`): a flame contact on the shown route binds 8 deadlines (each in 1
of 4 members, from first-new ignitions); for 6 the shown shelter is reachable on a fire-free road but on no
flame-avoiding one (in 5 of them not within the hour at all); for 2 the shown shelter is out of reach even without fire
while other candidates are blocked by the flames (하령리 `osm:node/415160436`, 2025-03-24T09Z: two shelters with a
route at D; 명진리 `osm:node/415160460`, 2025-03-25T17Z: a shelter refused at D as well); 1 `model_no_route` origin
has no flame-avoiding route that fits the window, and 10 are cut off by fire already burning at the input time (4 of
4 members).

## 9 Limitations

- Explanations are model-relative: four scenario members drawn independently per cell from the forecast, a
  scalar present-fire enclosure, a one-hour hazard horizon, OSM roads at an assumed 40 km/h; not observations.
- `flame_on_route` is a counterfactual about the shown route; that no other route exists at N rests on the
  relaxation proof (and on the API's recorded refusal), not on the replay alone.
- `deadline_cause` is a but-for statement over the candidate shelters the planner tried (checked at D or tried at N):
  `flames` means one of them would be reached in time without the fire; shelters the planner never tried are not
  considered, and "without the fire" also drops heat limits.
- Heat limits (10 kW/m², 100 kJ/m²) never needed to be invoked: every recorded refusal here is reproduced by contact
  and timing alone. A refusal that only heat limits explain would be reported `not_explainable`.
- Only the route checks being explained are recorded results of the evaluated host. The explanations themselves —
  contact replays, road times, flame-avoiding arrivals, exits — are computed by this tool, and the committed files were
  computed in a Linux x86_64 container, not on the evaluated host (section 10).
- Road names are not available from repository data (section 6).

## 10 Recorded and computed

| Value in an explanation | Where it comes from |
|---|---|
| verdicts per departure time and shelter, the leave-by time D and the next checked time N, the recorded routes (vertex times, edges, waits), arrival windows and dwell; the travel-only routes and their `full_policy_assessment` | **recorded**: the route checks in `planner/cache`, computed on the evaluated native macOS arm64 host (`host` in `planner/cache/INDEX.json`); read as recorded and never recomputed — this tool runs no new route checks |
| flame birth and expiry per member and cell, the one-hour scenario window | **forecast data**: the frozen hazard packet the checks used (hash-verified, section 1) |
| contact replays: every recorded route at its own times (section 5), the route checked at D shifted to N (`binding`: `contact_time_s`, `members`, `pass_time_at_deadline_s`, `slack_s`), the destination stay | **computed by this tool** (exact arithmetic, section 3) |
| fire-free fastest road times (`fastest_end_s`, `fire_free_end_s`, `fire_free_fits`), flame-avoiding relaxed arrivals and proofs (`flame_avoiding_arrival_s`, `proven`, the classes of section 4), exits (`exits[]`, `reached_at_s`), labels and distances | **computed by this tool** from the road graph (with the packet) |

The machine that computed them is recorded in `provenance.computed_on`. `provenance.evaluated_host` is `false` unless
`generate --evaluated-host` is given; that flag is refused unless the run is native macOS arm64
(`platform.system()` `Darwin`, `platform.machine()` `arm64`; otherwise the command stops with a one-line error and exit
status 2 before reading or writing anything), and it is meant only for a run on the evaluated host
itself — the platform check cannot tell that machine from another Mac, so the flag is the operator's statement. The
committed files were generated in a Linux x86_64 container (`computed_on`: `Linux-6.18.44-fc-v230-x86_64-with-glibc2.39`,
Python 3.12.3, numpy 1.26.4, pyproj 3.7.0), so `evaluated_host` is `false`. `check` compares every field except the run
stamps `generated_at`, `code_commit`, `code_dirty` and `computed_on` (it prints both hosts when they differ);
`evaluated_host` is compared.

## 11 How the planner words it (`planner/src/features/explain`)

- **Recorded vs computed.** Every sentence that rests on a value this tool computed — road times from the road graph,
  flame-avoiding arrivals, replay contact and pass times, the exits and everything said about them (the same OSM way,
  cells burning at the input time) — ends with `*` after its full stop, and so does every item of the exit list (a
  computed exit with its place distance and member count, e.g. "A road about 797 m from Guam-ri (this village): 4/4
  scenarios*"; the count of further exits likewise). The panel explains the mark ("* Computed for this explanation
  from the road graph and the fire scenarios, not a recorded check." / "* 기록된 점검이 아니라 이 설명을 위해 도로망과
  화재 시나리오로 계산한 값입니다.") and always says where the file was computed: "Computed for this explanation on
  Linux x86_64, not on the evaluated host: the recorded route checks are replayed against the same hazard packet; no
  new route checks were run." The A4 plan sheet prints both once per sheet, in the explanation section's footer after
  the forecast basis, when a printed row carries the mark: "* Computed on Linux x86_64 (not the evaluated host); not a
  recorded or new route check." / "* 평가 호스트가 아닌 Linux x86_64에서 계산한 값이며, 기록된 점검도 새 경로 점검도
  아닙니다." (one line on every sheet; rows from files computed on different hosts would get one note per host).
  Sentences that only restate recorded results (the last checked time, a "시간창 밖" skip, an unresolved next time or
  origin, a withdrawn explanation) carry no mark; the member dots and their caption repeat the k of n of the marked
  sentence they illustrate. The evaluated host is named only when `evaluated_host` is true and `computed_on` is macOS
  (Darwin) arm64. `tests/planner/explain.test.ts` checks every template and, for all 530 committed origins in both
  languages, every sentence and exit-list item.
- **Labels.** `explained` reads "Explained (replay of recorded checks)" / "설명됨(기록된 점검 재현)", `explained_partial`
  "Partly explained (replay of recorded checks)" / "부분 설명(기록된 점검 재현)": replays of recorded checks against
  the same forecast scenarios, not a verification of what happens on the ground.
- **Scope.** Beyond a leave-by time D only the next checked departure N is evaluated, so a time-window conclusion
  names it: "At the next checked departure, {next}, the trip to every one of these shelters falls outside the one-hour
  scenario range, so this leave-by time is set by that range, not by predicted flames." Nothing is claimed about times
  between D and N. An entry point in flames is stated for the first checked departure and "at least one of the fire
  scenarios" (the relaxation's test).
