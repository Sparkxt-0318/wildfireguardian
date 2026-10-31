# evacplan assumptions (Problem v0: oracle, generators, split, harness, deadlines, baselines B0-B3, real region 1)

Every modelling choice the schema, validator and oracle make. **Source**: *spec* (Problem v0
or the C0 task), *router* (reused from the single-vehicle router / whole-journey checker in
`integration/`), or *chosen* (decided here, listed under "Questions for Siyeong" when it matters).
The code is the definition: `src/evacplan/{schema,validate,oracle,reach,deadlines}.py` and
`src/evacplan/methods/`; the tests check each rule.

## Time, space, labels

| # | Assumption | Source |
|---|---|---|
| 1 | Instance times are seconds; hazard time = instance time + `hazard.t0_offset_s` (seconds after the scenario set's issue time). | spec |
| 2 | Coordinates are metres in the hazard CRS. The oracle refuses a graph whose `crs_epsg` differs from the scenario set's. | chosen |
| 3 | Times compare with a tolerance of 1 µs (`TIME_TOL_S`) for departures, release, windows and shifts. Hazard queries use exact times. | chosen |
| 4 | A result is labelled `SYNTHETIC` if the instance or the scenario set is synthetic. | spec |

## Roads and vehicle motion

| # | Assumption | Source |
|---|---|---|
| 5 | Edge geometry is the given polyline u→v or, by default, the straight chord u→v; end vertices are snapped to the node coordinates. | spec, router |
| 6 | A vehicle moves uniformly along each edge over the closed interval [depart, arrive]; edge travel times are fixed (no congestion, no time-dependent speeds, no interaction between vehicles on roads). | router |
| 7 | Waiting only at `waitable` nodes. A drive departing after the vehicle is free leaves an implicit idle at the current node, which obeys the same rule (gaps under 1 µs excepted) and is checked against the hazard like a wait. Instance builders should mark depot, facility and shelter nodes waitable when the site has off-road parking. | router (waits), chosen (idles) |
| 8 | Turn restrictions are forbidden `[in_edge, out_edge]` pairs. The heading persists through waits and idles (router: a WAIT keeps the incoming edge) and resets at boarding and unloading stops (the vehicle enters the site and may leave in any direction). | router, chosen |
| 9 | No mid-edge positions or reversals. | router |

## People, vehicles, sites

| # | Assumption | Source |
|---|---|---|
| 10 | Mobility class → vehicle space one to one: ambulatory → seat, wheelchair → wheelchair slot, bedbound → stretcher slot; no substitution. Seats exclude the driver. | chosen |
| 11 | Boarding takes Σ count × boarding time per class, starts when the previous action ends, and must not start before the facility's release time. Unloading likewise with the shelter's unloading times. | spec, chosen |
| 12 | Shelter opening windows are closed intervals; an unloading [start, end] must lie inside one window (the router's destination-stay rule). | router |
| 13 | Shelter capacity is per class and cumulative over the plan, shared by all vehicles, first come first served by unloading start (ties: itinerary order, then action order). Every stated unloading consumes capacity, valid or not, so tightening any constraint can only add issues. | chosen |
| 14 | Residents are anonymous within (facility, class). Boarding more than live there is `OVERBOARDED` (someone boarded twice; first come first served). Unloading takes residents first in, first out per class; this only affects per-facility reporting. | chosen |
| 15 | Shift limit: end of the last action − `start_s` ≤ `shift_limit_s`, flagged at the first action that ends late. Vehicles need not return to their depot. | chosen |
| 16 | Several vehicles may be at one site at once (no loading-bay limit). | chosen |
| 17 | Residents are modelled from boarding on. Their exposure while still inside a facility is **not** checked. | spec (gap, see Q1) |

## The oracle (`evacplan.oracle`)

| # | Assumption | Source |
|---|---|---|
| 18 | Legs: each edge is uniform motion queried with `ScenarioSet.query_uniform`; idles, waits, boardings and unloadings are the node as a stationary point over the closed interval (`ScenarioSet.query`). A vehicle is checked from its `start_s` at its depot through its last action. | spec, router |
| 19 | Contact uses closed cells (the router's whole-road rule: corners and shared edges count) in every member; certain contact in any member → `model_no_route` (FLAME_CONTACT). Only contact at an instant up to the hazard horizon is certain; contact that happens only after it is `unresolved` (BEYOND_HORIZON). `hazard_contract` itself reports `contact=True, supported=False` there. Since `hazard_contract` 1.0.1, uniform-motion pieces are widened by a floating-point tolerance (about 1e-12 s relative) for contact, so a touch at an exact boundary instant (a cell stops burning at the entry instant or ignites at the exit instant) counts as contact. | spec, router, chosen (horizon) |
| 20 | Peak, per leg and member: `flux_upper ≤ budget` passes, `flux_lower > budget` → `model_no_route` (PEAK_ABOVE_BUDGET), otherwise `unresolved` (PEAK_UNRESOLVED). Equality passes, as in the router. | spec, router |
| 21 | Dose, per member, cumulative over the vehicle's whole itinerary from its start: Σ `dose_upper` ≤ budget passes, Σ `dose_lower` > budget → `model_no_route` (DOSE_ABOVE_BUDGET), otherwise `unresolved` (DOSE_UNRESOLVED). This charges residents with dose received before they boarded, so it is conservative for occupants (a resident's dose ≤ the vehicle's). | spec |
| 22 | Unknown cells, the grid's outside and time after the horizon are unsupported → `unresolved`, never safe (program rule 4). | spec |
| 23 | Validator issues → `model_no_route` with cause `RESOURCE:<code>` from the start of the offending action. | spec |
| 24 | A vehicle's state never improves: after each leg it is the worst so far (model_no_route < unresolved < checked); its `cause` is the first reason that brought it to that level. After a certain violation, later legs are not queried (they cannot change any verdict). | spec |
| 25 | A trip ends with an unloading. Its residents are delivered iff the state at the end of that unloading is `checked` (every occupancy from the vehicle's start through it is checked in all K members). Residents still on board at the end are `model_no_route`. | spec |
| 26 | Residents no itinerary boards are reported as `not_planned`. That is not a verdict: proving that nobody can serve them is a planner's job, done per facility and class by `evacplan.deadlines` (#71: scoped `model_no_route`, `unservable` in the harness). | chosen |
| 27 | Safety slack of a checked leg: the largest uniform delay that keeps it contact-free in all members, exact from the cells' burning intervals (min over touched cells of ignition − last touch), capped at horizon − leg end. Plan `min_slack_s` = min over the legs up to each vehicle's last delivered trip. | spec |
| 28 | Vehicle time = Σ (end of last action − `start_s`) over itineraries; makespan = latest action end. | chosen |
| 29 | Every plan result carries its scope: oracle version, contract version, hazard model version, source, K, issue time, offset, horizon (hazard and instance clocks), budgets, flux model and the rules above. | spec |

## The RELAXED check

| # | Assumption | Source |
|---|---|---|
| 30 | `RelaxedContactCheck` is contact only (no flux, no dose, no verdict on resources) with the oracle's occupancies, closed cells and horizon scope: `blocked` implies the oracle rejects the leg; `uncertain` equals "some member unsupported". It returns no state and must not be used for final answers. | spec |

## Router graph adapter (`evacplan.adapters.wfg_graph`)

| # | Assumption | Source |
|---|---|---|
| 31 | `travel_time_s = travel_ticks × dt_s` with `dt_s = 1` (every study packet's lattice); geometry = straight chord; admission by the router's own `validate_graph`; the graph's `grid` is the packets' affine (checked on all study graphs); OSM graphs keep "© OpenStreetMap contributors, ODbL" in provenance. | router |

## Synthetic generator (`evacplan.generators.synthetic`, version `evacplan.synthetic/1`)

| # | Assumption | Source |
|---|---|---|
| 32 | Every generated instance is SYNTHETIC: `Instance.synthetic`, the id and name prefix `SYNTHETIC-`, provenance labels, the hazard's `synthetic`, `source="synthetic"` and `weather_source="SYNTHETIC"`, facility and shelter names. | spec |
| 33 | Deterministic from the config `(size, tightness, graph, seed)`: one numpy `SeedSequence` stream per component keyed by (seed, size, graph, component). Tightness enters no stream, so roads, sites, residents, boarding and unloading times, vehicle types, depots, start times, the fire's direction and its member perturbations are the same at every tightness level. | chosen |
| 34 | Space: abstract metres in EPSG:3310 with the road region's south-west corner at the origin (no real place); issue time 2000-01-01T00:00Z (a neutral date); instance clock = hazard clock (offset 0). Hazard grid: 375 m cells (the study packets' resolution) covering the roads plus 2 cells, and 4 km of wildland to the west. | chosen |
| 35 | Roads, `grid`: a lattice with 750 m spacing, nodes jittered by up to 20 % of the spacing, 12 % of the roads dropped without disconnecting the graph. `geo`: a random geometric graph: points thrown at one per (750 m)² with at least 450 m between them, joined by their Gabriel graph (edges up to 1500 m; planar, contains the minimum spanning tree), then joined by shortest links if needed. All roads are two-way. | chosen |
| 36 | The router's road conventions: straight chords, `travel_time_s = ceil(length / 40 km/h)` in whole seconds, U-turns forbidden except at dead ends, waiting only at dead ends and at site nodes (depots, facilities and shelters are assumed to have off-road parking). | router |
| 37 | Sizes (region, facilities, residents, vehicles at loose → tight, shelters, depots, horizon): S 7.5 × 6 km, 2, 20–40, 2 → 1, 2, 1, 3 h; M 12 × 9 km, 6, 130–170, 5 → 3, 3, 2, 4 h; L 18 × 13.5 km, 15, 550–650, 12 → 8 (10 at t = 0.5), 4, 3, 6 h. | spec (counts), chosen (rest) |
| 38 | Facilities: nodes in the central band (30–65 % of the width, 12–88 % of the height), spread apart; ids F01… from west to east; 60 % skilled nursing (SNF), 40 % assisted living (ALF); sizes 3 + a Dirichlet(4) multinomial share of the total. | chosen |
| 39 | Mobility classes are the space a resident needs IN THE VEHICLE (a wheelchair user who can transfer to a seat is ambulatory). Mix (ambulatory, wheelchair, bedbound): SNF 0.75 / 0.18 / 0.07, ALF 0.90 / 0.09 / 0.01, drawn per facility (multinomial). These are placeholders, not measured shares. | chosen (Q8) |
| 40 | Per-resident boarding 45 / 150 / 360 s and unloading 30 / 90 / 240 s (ambulatory / wheelchair / bedbound), times a per-facility or per-shelter factor in [0.8, 1.25], rounded to seconds. | chosen |
| 41 | Shelters: S1 is medical (every class; bedbound capacity 1.3 × all bedbound + 1), the others general (no stretchers); ambulatory and wheelchair capacity split by Dirichlet(3) weights at 1.3 × the residents of the class (+5 and +2 per shelter); S1 opens at 0, the others at 0, 0, 15 or 30 min; all close at 48 h. | chosen |
| 42 | Fleet types (seats, wheelchair slots, stretchers; driver excluded): van 8 / 2 / 0, bus 40 / 2 / 0 (lift-equipped: the 2 wheelchair slots go beyond the spec's "40-seat bus"), ambulance 1 / 0 / 1. Per-size ordered lists: S van, ambulance; M bus, van, ambulance, van, ambulance; L bus, van, ambulance, van, ambulance, van, bus, ambulance, van, van, ambulance, van. Vehicles start at depots (round robin) after a 0–15 min mobilisation delay (whole minutes). | spec (types), chosen (Q9) |
| 43 | Fire: `hazard_contract.synthetic` with K = 8 members (rate CV 0.25, direction SD 15°, smooth noise SD 0.2 over ~8 cells, head ratio 3), ignited 1 h before issue and spreading east ± 20° towards the facilities. The ignition sits on the line behind the most upwind facility, placed by bisection on the realized members so that the earliest arrival at any facility node over all members equals the lead (± 1 s). | spec (threaten the facilities), chosen |
| 44 | Persistent burning: every ignited cell burns until 48 h after ignition, i.e. through the horizon, so burned roads and facilities stay closed ("before roads close"; per-facility deadlines exist). The flux uses the repo packets' heat-source parameters (scalar T = 3970 s), so a cell keeps emitting at the flaming rate while it burns: conservative for dose near burned areas. In calibration (seeds 9001+) contact-free routes collected under 1 kJ/m² against the 100 kJ/m² budget: contact decides. | chosen (Q7) |
| 45 | Ignition times are floored to whole seconds (outward) and coordinates rounded to 1 cm, so an instance regenerates bit-identically on another platform (one ulp of a transcendental function cannot change it). | chosen |
| 46 | Budgets: peak 10 kW/m², dose 100 kJ/m² per member (the router API defaults). | router |
| 47 | Tightness `t` in [0, 1], linear: lead (earliest fire arrival at any facility) 150 → 30 min; head rate of spread 0.08 → 0.30 m/s; release time per facility = u × (5 → 45 min) with u ~ U(0, 1) from the layout, rounded to minutes; driver shift limit (100 → 50 %) × horizon, rounded to minutes; fleet = the first `min + round((max − min)(1 − t))` vehicles of the size's list. | spec (knobs), chosen (values) |
| 48 | Shelters (the east 18 % of the region) and depots (the eastern third) do not depend on tightness: candidates are ranked by how late the layout's most aggressive fire (t = 1) reaches them (their own cells and incident roads), then spread apart. Diagnostics report any site the fire reaches; at t ≤ 0.75 this happened only for a few S layouts in the last ~17 min of the horizon, and never in the frozen split (a test checks it). | chosen |
| 49 | Provenance carries the config, the tightness parameters and diagnostics: realized lead, fire arrival per facility, per shelter and depot (with incident roads), residents by class, fleet space, ignition point. | chosen |

## Frozen split (`evacplan/instances/SPLIT.json`, `evacplan.instances`)

| # | Assumption | Source |
|---|---|---|
| 50 | Frozen on 2026-10-31 before any method ran: `dev` and `test` each hold 4 S + 4 M + 2 L, grid and geo roads, tightness 0.25 and 0.75 for S and M and 0.5 for L; dev seeds 101–110, test seeds 201–210. Generator calibration looked only at layouts and hazards of seeds 9000+, never at a method's result. | spec |
| 51 | Instances are not committed. They regenerate into `evacplan/cache/instances/<id>/` (git-ignored) and must match the frozen fingerprint: sha256 of the canonical instance JSON, the hazard meta JSON and the hazard arrays. A mismatch (the generator, `hazard_contract.synthetic` or numpy's Generator streams changed) is refused as generator drift. | chosen |
| 52 | `test` is refused by the harness without `--allow-test` (milestones only, after Siyeong approves); tests check that no result row, cached instance or leaderboard line mentions a test instance. | spec |

## Harness (`evacplan run`, `evacplan.harness`)

| # | Assumption | Source |
|---|---|---|
| 53 | `evacplan run --method X --set dev --budget-s B [--seeds …]`: each instance and seed gets B seconds of wall clock for `Method.solve(instance, scenario_set, budget_s, seed, deadline)`; the oracle then checks the returned plan (not timed). Instances are regenerated before timing starts. | spec |
| 54 | Columns: `delivered_checked`, `unresolved`, `model_no_route` = the oracle's `delivered_total`, `unresolved_total`, `model_no_route_total` (residents); residents no itinerary boards are "not planned" (the rest). `makespan_s`, `min_slack_s` from the oracle (empty when undefined). `runtime_s` = the method's wall clock. `best_bound` = the method's proven upper bound on delivered residents (empty: none); `gap = (best_bound − delivered_checked) / best_bound` (0 if the bound is 0). `seed` = the method's seed; `commit` = git HEAD (`+dirty` if `evacplan/`, `hazard_contract/` or `program/` has uncommitted changes, untracked files included, other than the generated leaderboard); `config` = compact JSON (set, budget, method config, instance generator config and fingerprint, label, the oracle version, the `hazard_contract` format `CONTRACT_VERSION`, and `versions`: the installed `hazard_contract.__version__`, numpy, ortools and highspy, read from the installed distributions); `host`. | spec, chosen |
| 55 | Rows are upserted by (set, budget, instance, method, seed). `results/` (CSVs, plans and oracle results) is git-ignored; `LEADERBOARD.md` is committed and regenerated after every run: one table per set and budget (methods are only compared at equal budgets), a label column (SYNTHETIC), over-budget runs counted. | spec, chosen |
| 56 | Timed runs hold the shared bench lock (`program/benchlock.py`, loaded by path). `--lock auto` (default) skips acquiring when a parent process already holds it (`benchlock.py -- evacplan run …`), which would otherwise deadlock. | spec, chosen |
| 57 | A method's own claims (`MethodResult.info`) are never scored; `noop` returns the empty plan and only tests the plumbing. | spec |

## Latest-safe-departure sweep and per-facility deadlines (`evacplan.reach`, `evacplan.deadlines`)

| # | Assumption | Source |
|---|---|---|
| 66 | Every decision is on the whole-second lattice of the instance clock, from 0 to Hi = ⌊horizon − offset⌋: the oracle never checks an occupancy that ends after the horizon, so nothing later can be delivered. Travel times, per-resident boarding and unloading times and vehicle starts must be whole seconds (`LatticeError` otherwise; the generators and the router graphs are); windows, release times and shifts are rounded inwards. | router (1 s lattice), chosen |
| 67 | Two relaxations of the oracle's leg rule, built from the oracle's own contact records (uniform motion, closed cells, the same instants). POSITIVE ("usable"): no touched cell burns at any instant of the occupancy in any member (touch intervals widened by 1 µs), every touched cell is supported, the geometry stays inside the grid, the leg ends by the horizon; contact only, so the oracle may still reject a usable leg on peak or dose, never on contact, support or horizon. NEGATIVE ("not certainly blocked"): a departure is blocked only by certain contact in some member whose first instant is by the horizon (narrowed by 1 µs); unknown cells are passable. Tests check both against `hazard_contract` and the oracle. | spec (relaxed checks inside searches), chosen |
| 68 | The sweep is a backward dynamic programme over (state, second). States: the edge just traversed (the heading, for turn rules) and a fresh heading at each facility (after boarding). Moves: allowed successors usable at that second. Waits: 1 s at a waitable node with a usable stay, keeping the heading. Target: unloading ONE resident of the class at a shelter that accepts it (capacity > 0), inside an opening window, with a usable stay, by the horizon. All classes and all K members at once; exact on the lattice for any hazard (no monotonicity assumed); cross-checked against a plain recursion and a forward brute force. `Reach.departure_field` keeps a fresh state at every node and returns the per-node field (the latest second a vehicle there can still leave and deliver). | spec (U1 backward reachability), chosen |
| 69 | Per facility and class: `leave_by_s` = the latest second t ≥ release + one boarding from which the sweep reaches a target and at which the boarding stay [t − b, t] at the facility is usable; `arrive_by_s` = `leave_by_s` − b, with b the boarding time of ONE resident of the class. They are the latest times the last vehicle can leave and the first vehicle can arrive and still serve someone of that class; a full load boards longer. The facility summary takes the earliest class `arrive_by_s` and the latest class `leave_by_s`. | spec, chosen (Q14) |
| 70 | Every deadline is confirmed by the oracle: a probe vehicle that starts at the facility boards one resident from `arrive_by_s`, leaves at `leave_by_s` on the sweep's witness route (prefer unloading, then a move that makes progress towards a shelter in free-flow time, then waiting, then any move) and unloads. If the oracle does not check it, earlier departures are tried (up to 6, stepping back 1, 2, 4, … s); otherwise the class is `unresolved`. | spec (final answers from the oracle) |
| 71 | Residents no plan can serve are a scoped `model_no_route` (`UNSERVABLE:<reason>`, declared by the oracle), for a whole class at a facility, in this order: `NO_SHELTER_CAPACITY` (no shelter accepts the class); `NO_VEHICLE_SPACE` (no vehicle has room for it); `NO_ROUTE` (in the NEGATIVE relaxation, with waits anywhere, no turn rules and one resident's unloading, no departure at or after release + one boarding reaches an open shelter by the horizon); `NO_VEHICLE_IN_TIME` (every vehicle with room either cannot reach the facility in that relaxation early enough to board and leave by the relaxation's latest departure, or cannot finish one trip within its shift, using the free-flow time to the nearest accepting shelter plus unloading as a lower bound); `NO_TRIP_BY_HORIZON` (#74). Each relaxation refusal is attributed to the weakest level of the relaxation that still refuses: with certain contact and the horizon (`NO_ROUTE` / `NO_VEHICLE_IN_TIME`, detail "certain-contact relaxation"), with no fire but the horizon (`NO_TRIP_BY_HORIZON`), with neither fire nor horizon (graph, windows, release and shifts alone: `NO_ROUTE` / `NO_VEHICLE_IN_TIME`, detail "no fire and no horizon involved"). Partial shortfalls (only some residents of a class) are not claimed. | spec, chosen |
| 72 | `NO_ROUTE`, `NO_VEHICLE_IN_TIME` and `NO_TRIP_BY_HORIZON` are certified only when the 1 s lattice is complete for the relaxation: every supported cell that starts burning by the horizon keeps burning through it (feasible departures are then down-sets, so flooring the times of any continuous-time trip to whole seconds keeps it feasible) and every instance time is a whole second. Otherwise they are `unresolved` (`RELAXATION_INCOMPLETE:<reason>`). The oracle verifies these conditions, and the resource claims, itself. | chosen (soundness) |
| 73 | No usable route but no certain refusal (unknown cells, or turn rules, waits or windows that only the relaxation can satisfy) is `unresolved`, never `model_no_route`. A class that is unservable for lack of vehicles (`NO_VEHICLE_IN_TIME`) still reports its checked deadline. | spec (rule 4) |
| 74 | A delivery needs every leg checked by the horizon, so "cannot be delivered by the horizon" is a `model_no_route` scoped to the horizon (as the router's `PROVEN_INFEASIBLE` is scoped to its horizon), while a single trip that runs past the horizon stays `unresolved` in the oracle. A refusal that needs no fire (even with nothing burning no trip ends by the horizon, while without the horizon one would) has its own cause, `NO_TRIP_BY_HORIZON`, with a detail that names the horizon and not the certain-contact relaxation; it stays `model_no_route` scoped to the horizon until Siyeong answers Q12 (the alternative is `unresolved`, BEYOND_HORIZON, as the oracle rates such a trip). | router, chosen (Q12) |

## Baselines (`evacplan.methods`: `b0_independent`, `b1_greedy`)

| # | Assumption | Source |
|---|---|---|
| 75 | Both baselines plan on the POSITIVE masks only (contact-free in all K members, supported, by the horizon) under the validator's rules (capacities, release, windows, shifts, waits, turn rules); the harness checks every plan with the oracle. A trip: approach → wait for release (waitable facility) → board → route to a shelter → wait for its window (waitable shelter) → unload. Routes: the free-flow shortest turn-aware path if usable at once, else a time-dependent A* with waits (exact when arriving earlier is never worse). Vehicles need not return to their depots; one shelter per trip; no local search. | chosen |
| 76 | B0 reproduces today's planner (`planner/README.md`, `planner/docs/ARCHITECTURE.md` §6, `api/dispatch.py`) per facility: departure offsets every 600 s over [0, horizon), the 3 nearest shelters by straight-line distance with distinct nodes, one route check per offset and shelter with a 120 s stay inside an opening window (a RELAXED check here: the time-dependent router), "checked if any shelter is checked", and the deadline = the latest offset of the contiguous checked run (`latest_contiguous_checked_depart_offset_s`). It adds only what a facility must know: shelters must accept every class of the load, boarding starts at release, and a trip leaves at a checked offset by the deadline for the checked shelter with the earliest arrival. | spec (planner logic), chosen |
| 77 | B0's "no coordination": each facility is planned alone with the whole fleet and every shelter's full capacity (trip by trip, the vehicle that can leave with a load earliest takes it; a load fills each class's own space); its trips become bookings (vehicle, load, requested pickup = boarding start); the shared fleet then serves all bookings first come first served by requested pickup (ties: facility id), re-timed from where each vehicle actually is; a booking that can no longer leave by its facility's deadline, or find a checked shelter with room, is dropped (those residents are not planned). The measured gap includes double-booking, the lack of deadline awareness and the planner's 10 min grid. | chosen (Q13) |
| 78 | B1: deadlines from one sweep (per facility and class, #69 without the probe); jobs (facility, class) earliest deadline first; each job is appended to the vehicle with the cheapest insertion, the least added vehicle time per resident moved (ties: earliest departure, then vehicle id; `vehicle_rule="earliest"` uses the earliest departure); the load is the job's class up to the vehicle's space, topped up with the facility's other classes in deadline order as far as every loaded class still leaves by its deadline; the shelter (accepting every loaded class, with room) is the one where unloading ends first. A job no vehicle can serve any more is dropped. | spec (B1), chosen |
| 79 | Both are deterministic (the seed is recorded but unused) and stop adding trips at 95 % of the budget. Optional oracle repair (`repair=true`, default off): cut an itinerary before its first trip the oracle does not check; a vehicle's state never improves, so this only relabels those residents as not planned. On dev every planned trip was checked. | chosen |

## Baselines B2 and B3 (`evacplan.methods`: `b2_vrptw`, `b3_mip`; shared `methods.realize`)

| # | Assumption | Source |
|---|---|---|
| 81 | Realization (B2, B3): a model's per-vehicle stop sequence (unloadings and boardings per stop) is replayed as soon as possible on the POSITIVE masks: earliest-arrival time-dependent route to each stop, wait for the release or the window at waitable sites, unload then board in the stop's order, under the validator's rules. Residents move in units (one class, boarded together, unloaded at one or more later stops). An impossible boarding drops its units; an impossible unloading drops its units and re-realizes the vehicle from its start; a stop where nothing is done is skipped with its approach, so every kept stop resets the heading (turn rules). Vehicles are realized in instance order against shared shelter capacity and residents left. | chosen |
| 82 | B2 static model: requests = residents per (facility, class) with a latest departure (the sweep of #78), in chunks of `q` plus a binary remainder, `q` = the smallest space for the class among vehicles with room for at least two (else 1), capped so a chunk boards between release and deadline; one pickup node per chunk (service = its boarding), one delivery alternative per shelter that accepts the class and has room for the chunk (service = its unloading), `AddPickupAndDeliverySets` (if picked up, delivered once, later, by the same vehicle); a start node per vehicle at its depot and a free end. | spec (B2), chosen |
| 83 | B2 time: turn-aware free-flow shortest-path times between sites (the hazard is not in the travel times); windows: vehicle start >= `start_s`, route end <= min(horizon, start + shift), pickup start in [release, latest departure - chunk boarding] (the static window from the per-facility latest departures), delivery start inside an opening window with the unloading done by the horizon; waiting allowed anywhere in the static model. Capacities: one dimension per class (seats, wheelchair slots, stretchers). Shelter capacity per class: a constraint on the active delivery alternatives. | spec (B2), chosen |
| 84 | B2 objective and search: `BIG` (= 10 x vehicles x (horizon + 1)) per resident not served + total free-flow travel time (vehicle time as the tie-break); parallel cheapest insertion, then guided local search until the budget minus a reserve (0.5 s + 3 % of the budget + 4 ms per chunk) for realization. OR-Tools routing is single-threaded and seedless; time-limited results can vary with machine load. The plan is realized (#81) and checked by the oracle in the harness; optional oracle repair (`repair=true`, default off, as #79: on L the oracle takes about 20 s, and cutting only relabels unresolved residents as not planned). On dev at 60 s every B2 trip was checked except one bus on M-geo-t25-s106: 67 residents `DOSE_UNRESOLVED` (Q18). | spec (B2), chosen |
| 85 | B3 grid and network: times `tau_k = k delta` (default `delta` = 180 s) up to the last whole second of the horizon; locations = distinct nodes of facilities, shelters and depots; moves only into facility or shelter locations (from a depot only to facilities: the vehicle starts empty); waits; an end at a shelter location or at the start; nodes not on any path from the start to a node where unloading is possible are pruned. Variables per vehicle (S instances: 1-2 vehicles): binary arcs and end, per-class loads ON the arcs (load <= space x arc), integer boardings and unloadings at nodes, a continuous stay-time bank per location; shared rows: residents per facility and class, shelter capacity per class. Actions sit at the node where the vehicle leaves or ends (any stay's actions can be deferred to its last node); objective: residents unloaded. | spec (B3), chosen |
| 86 | B3 bank: boardings and unloadings at a node draw `count x seconds per resident` from the bank; it accrues the usable part of each wait arc (after the facility's release, inside the shelter's window) and an arrival credit, and empties when the vehicle leaves. RESTRICTED model (primal): a move leaves at `tau_k` on the POSITIVE earliest-arrival route and arrives at `ceil(a / delta)`, idling at the destination meanwhile (waitable, usable stay), the usable part of that idle being the credit; waits need a waitable node and a usable stay; boarding at `tau_k >= release`, unloading inside a window. Every restricted solution is realizable (#81 can only arrive earlier when cells never stop burning). | chosen |
| 87 | B3 RELAXED model (bound): a move from `i` at `tau_k` arrives at `floor(EA / delta)` with EA the NEGATIVE-relaxation earliest arrival (#67: only certain contact blocks, waiting anywhere, no turn rules); waits are free; an arrival at `a` credits the rest of its cell plus the part of it before the release/opening, minus 1 s, or `delta - 1` if the release/opening is still ahead (with whole-second times a stay that leaves in the cell of node `kd` ends by `tau_kd + delta - 1`); accruals use the earliest release and any window; actions allowed at `k` when `[tau_k, tau_k + delta)` meets the release/window. Any oracle-accepted plan maps into it (times floored), so its MIP dual bound bounds every plan. Certified only on a complete 1 s lattice (#72) with `delta` <= the shortest free-flow time between active locations; if every instance time is a multiple of `delta` it is exact on the grid (moves round up, no credit). | chosen (soundness) |
| 88 | B3 solve: the relaxed MIP first (30 % of the time left; its LP relaxation is solved first by interior point so a bound exists even if the root does not finish), `best_bound` = floor(min(relaxed dual bound, its LP bound, resource bound)), the resource bound = residents of classes some vehicle and shelter can take, up to the shelters' room (always valid; the only bound when the relaxation is not certified). Then the restricted MIP on grids 4, 2, 1 x `delta` (shares 0.2/0.3/0.5 of the rest), each capped by `best_bound` (stop when reached), each incumbent lifted onto the next grid as a MIP start (exact: the grids nest). Every incumbent, including the relaxed one, is realized (#81); the plan with the most residents realized is returned. HiGHS: `mip_abs_gap` 0.999 (integer objective), heuristic effort 0.3, one thread; it runs in a child process because the OR-Tools wheel bundles an ABI-incompatible `libhighs.so.1` (HiGHS 1.11 vs `highspy` 1.15; the loader keeps whichever is loaded first). S instances only (<= 3 facilities, <= 2 vehicles, <= 60 residents); the harness writes no row for others. Results depend on how far HiGHS gets within the budget. On dev S at 60 s every B3 trip was checked; bounds 23, 39, 26, 26 (all equal to the resource bound), proven optimal on S-grid-t25-s101. | spec (B3), chosen |
| 89 | Fair timing: every method runs single-threaded (B2's OR-Tools routing; B3's HiGHS with `threads=1`; B3's child-process start-up and I/O count in its runtime). | chosen (rule 6) |

## Harness per-facility output

| # | Assumption | Source |
|---|---|---|
| 80 | `results/<method>.facilities.csv` (git-ignored, next to `results/<method>.csv`): one row per instance, seed, budget, set, facility and mobility class with residents: the oracle-declared deadline state and cause, `arrive_by_s`, `leave_by_s`, the probe's shelter, `unservable` (= the class's residents if `model_no_route`, else 0), and this plan's delivered / unresolved / model_no_route (trips plus residents left on board) / not planned residents of that facility and class, its first boarding start and last departure after boarding, plus commit, config and host. Deadlines are computed once per instance outside the timed region and kept as `<id>.deadlines.json` with the plans. The leaderboard adds the unservable count. | spec, chosen |

## Real US region 1: Caldor Fire 2021, South Lake Tahoe (`evacplan.regions`) — BLOCKED here

Status (2026-10-31): **BLOCKED on the cloud container.** The repo has no Caldor road graph, facility list
or perimeters (the sealed Caldor study is on Siyeong's Mac) and the hosts below are refused by the network
policy (proxy CONNECT 403). The builder is written and tested offline on hand-made FIXTURE inputs; no Caldor
instance was built and no synthetic data stands in for it. `evacplan build-caldor` prints exactly what is
missing:

* OSM road graph: host `overpass-api.de` (osmnx, `--online`), or `--graph` a GraphML saved with
  `osmnx.save_graphml(osmnx.graph_from_bbox(bbox=(-120.15, 38.70, -119.70, 39.12), network_type="drive"))`;
* CMS nursing-home provider file: host `data.cms.gov` (Provider Data Catalog dataset `4pq5-n9py`), or
  `--cms NH_ProviderInfo_<MonYYYY>.csv`;
* facility coordinates: host `geocoding.geo.census.gov` (Census batch geocoder), or `--geocodes` CSV
  (`ccn,lat,lon`); not needed if the CMS file carries Latitude/Longitude;
* fire perimeters: `--perimeters` GeoJSON of timestamped Caldor perimeters from the issue time to the planning
  horizon (about 2021-08-29 to 2021-08-31), e.g. NIROPS IR perimeters (`data.mendeley.com`, DOI
  10.17632/95rj5d379g.1; the 1.39 GB `NIROPS_2020_2024_R1_R6.zip` is on the Mac) or the NIFC/WFIGS history.

Alternative: the sealed study's Caldor `graph.json` and hazard packets (on the Mac) through
`evacplan.adapters.wfg_graph.from_wfg_graph` and `hazard_contract.from_wfg_packet`. The repo has no usable
Caldor/Rim graph or hazards, so the builder uses OSM + `from_perimeters` (to be recorded in `program/DECISIONS.md`).

| # | Assumption | Source |
|---|---|---|
| 58 | Region bbox (lon/lat) W −120.15, S 38.70, E −119.70, N 39.12: South Lake Tahoe, Meyers, Christmas Valley, Stateline, Kingsbury Grade, US-50 to Spooner Summit and the west of Carson Valley. CRS EPSG:3310 (California Albers, the sealed study's CRS). | chosen (to confirm) |
| 59 | Roads: OSM drivable roads via osmnx 2.1 (`graph_from_bbox`, `network_type="drive"`, simplified, `truncate_by_edge`), the largest strongly connected component; the OSM polyline is kept as edge geometry (the router used chords); travel time `ceil(length / 40 km/h)` (router) or osmnx's speed imputation (`speed="osm"`); U-turns on the same OSM way forbidden except at dead ends; OSM turn restrictions are not loaded (osmnx does not parse restriction relations); waiting at dead ends and sites; "© OpenStreetMap contributors, ODbL 1.0" in provenance. | router, chosen |
| 60 | Facilities: CMS provider file (headers matched by aliases across releases), providers in CA and NV inside the bbox; located by the file's own coordinates, else the geocodes CSV, else the Census batch geocoder (`Match` rows only; ties and misses are reported, never guessed); snapped to the nearest road node within 500 m (else reported and dropped). Facility ids `CMS-<CCN>`, names from CMS (public data). | spec, chosen |
| 61 | Residents: the CMS average number of residents per day (a real count), else 0.75 × certified beds; split into classes by the SNF mix of #39 with largest-remainder rounding (SYNTHETIC, deterministic); boarding and unloading times as #40 (no factor); release time 0 (staff ready at the order). | chosen (to confirm) |
| 62 | Shelters: a JSON list of receiving sites when given (real data). Otherwise SYNTHETIC safe-zone exits: on each safe side (east and north; the fire came from the south-west), the outermost node on a major road (motorway, trunk, primary) within 2 km of that side of the road graph; unlimited capacity, open 48 h, unloading as #40. | chosen (Q11) |
| 63 | Fleet (SYNTHETIC): one facility van (8 seats, 2 wheelchair slots) per facility, ready at 0; a mutual-aid pool staged at the first exit, arriving after 30 min: one bus per 80 ambulatory residents and one ambulance per 4 bedbound residents; shift limit 8 h. | spec (types), chosen (numbers, Q11) |
| 64 | Fire: timestamped perimeters (GeoJSON, WGS84, features with equal times merged) → `hazard_contract.from_perimeters` on a 375 m grid covering the roads plus 3 cells; K = 4 `stratified` members (`envelope` is the conservative alternative); persistent burning (48 h) and the packet heat parameters as #44; horizon = the last perimeter; cells outside the last perimeter do not burn within it (the perimeter is taken as the complete fire boundary; `mapped_mask` can mark unmapped areas unsupported). Issue time default 2021-08-30T18:00Z (30 Aug 2021, the day South Lake Tahoe was ordered to evacuate; the exact time is to be confirmed). | spec, chosen (to confirm) |
| 65 | The instance is labelled SYNTHETIC (synthetic residents' mobility, fleet and, by default, shelters) although roads, facilities and the fire are real data; its provenance says which parts are which. | spec |

## Questions for Siyeong

1. **Facility exposure before boarding (#17).** A vehicle arriving after the fire has swept a facility
   still "rescues" its residents. Should residents waiting at a facility be checked as a stationary
   occupancy from plan start until boarding (which would turn late pickups into `model_no_route`)?
2. **Turn context at stops (#8)** resets at boarding/unloading. Keep, or treat stops like waits?
3. **No space substitution (#10).** Should ambulatory residents be allowed in wheelchair slots, or
   wheelchair users transfer to seats?
4. **Contact after the horizon (#19)** is `unresolved`, not `model_no_route`. Agree?
5. **Dose per vehicle (#21)** vs per resident from boarding (less conservative, needs per-resident
   tracking)?
6. Under the repo heat law the 10 kW/m² peak budget never binds (flux ≤ 0.703 kW/m²); contact and
   dose decide. Under rule 4, 32–100 % of the Korean road cells are unsupported, so Korean packets
   mostly give `unresolved` (by design).
7. **Persistent burning (#44, #64).** Burned cells stay closed through the horizon, which gives per-facility
   deadlines ("before roads close"); emission continues at the flaming rate (conservative dose). The study
   packets burn 66 min instead, under which a vehicle can wait for the front to pass and, with #17, still
   "rescue" the residents of a burned facility. Keep persistent burning?
8. **Mobility mix (#39).** Classes by space needed in the vehicle; SNF 75/18/7 %, ALF 90/9/1 % are placeholders.
   Replace with measured shares (e.g. from CMS MDS summaries)?
9. **Buses with 2 wheelchair slots (#42)?** And is one stretcher per ambulance right?
10. **Objective.** Counting residents equally favours ambulatory residents (a bus trip moves 40, an ambulance trip
    moves 1). Weight classes, or also report delivered per class?
11. **Caldor (#58–#64).** Bbox, issue time, safe-side exits as shelters and the mutual-aid fleet are choices to
    confirm; which perimeters to use (NIROPS from the Mac?), or the sealed study's graph and packets instead.
12. **Unservable vs not planned (#71, #74).** Only residents that no plan can serve (a whole class at a facility,
    proved by resource facts or the certain-contact relaxation) are reported as scoped `model_no_route`; residents a
    plan merely leaves behind stay "not planned" (calling them `model_no_route` would overstate what is known).
    Agree? Also: "cannot be delivered by the horizon" is `model_no_route` scoped to the horizon (as the router's
    refusal), although a single trip past the horizon is `unresolved`. Refusals that need no fire at all carry their own
    cause, `NO_TRIP_BY_HORIZON` (#74), so they can be told apart, or re-labelled `unresolved` (BEYOND_HORIZON) if you prefer.
13. **B0's "no coordination" (#77).** Every facility plans alone with the whole fleet and the shared fleet serves the
    resulting bookings first come first served. The alternative status quo is a static split of the fleet (each
    vehicle dedicated to one facility), which leaves facilities without a vehicle whenever there are more facilities
    than vehicles. Which one matches the practice you want to compare against? B0 also keeps the planner's 10 min
    departure grid; a 1 min grid (`step_s=60`) would isolate the coordination gap.
14. **Deadline definitions (#69).** `arrive_by_s` / `leave_by_s` are per class for ONE resident (the latest first
    arrival and last departure that can still serve someone). A "whole facility out by" time needs the fleet and is
    a plan property (the facility CSV reports each plan's first boarding and last departure). OK?
15. **B2's static model (#82-#84).** Travel times are free-flow and the hazard enters only through the pickup windows (the
    per-facility latest departures), as the spec says; the realization then re-routes on the time-dependent network and
    drops what no longer fits. Should B2 also see hazard-aware static times (e.g. the earliest contact-free arrival at
    the window's start)? That would make it a stronger baseline to beat.
16. **B3's bound (#87, #88)** is valid for every plan but loose on the dev S instances: at 60 s it equals the resource bound
    on all 4 (23, 39, 26, 26; B3's gap 0-19 %, mean 8.3 %); a finer grid tightens the relaxation but the MIP then does not
    finish in 60 s. Is a bound scoped to B3's grid (tighter, but not a bound for other methods) of any use, or only the
    certified one (current)?
17. **Single-threaded methods (#89)** for equal resources at equal wall clock. OK, or allow solvers their default threads?
18. **Dose-aware planning (#67, #84).** The planners' masks are contact-only. On dev at 60 s, B2's plan for M-geo-t25-s106
    boards about 30 residents onto the bus in one 25 min stay at a facility near the fire; the oracle cannot certify the
    cumulative dose there (upper bound 127 kJ/m² against the 100 kJ/m² budget in one member), so 67 residents are
    `unresolved` (never delivered); at a 20 s budget the same instance had all 155 checked. Give the planners a cheap dose
    estimate (e.g. a per-node flux bound in the masks), or leave dose to oracle-in-the-loop methods (E1)?
