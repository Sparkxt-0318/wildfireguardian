# evacplan assumptions (Problem v0, milestone C0-oracle)

Every modelling choice the schema, validator and oracle make. **Source**: *spec* (Problem v0
or the C0 task), *router* (reused from the single-vehicle router / whole-journey checker in
`integration/`), or *chosen* (decided here, listed under "Questions for Siyeong" when it matters).
The code is the definition: `src/evacplan/{schema,validate,oracle}.py`; the tests check each rule.

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
| 19 | Contact uses closed cells (the router's whole-road rule: corners and shared edges count) in every member; certain contact in any member → `model_no_route` (FLAME_CONTACT). Only contact at an instant up to the hazard horizon is certain; contact that happens only after it is `unresolved` (BEYOND_HORIZON). `hazard_contract` itself reports `contact=True, supported=False` there. | spec, router, chosen (horizon) |
| 20 | Peak, per leg and member: `flux_upper ≤ budget` passes, `flux_lower > budget` → `model_no_route` (PEAK_ABOVE_BUDGET), otherwise `unresolved` (PEAK_UNRESOLVED). Equality passes, as in the router. | spec, router |
| 21 | Dose, per member, cumulative over the vehicle's whole itinerary from its start: Σ `dose_upper` ≤ budget passes, Σ `dose_lower` > budget → `model_no_route` (DOSE_ABOVE_BUDGET), otherwise `unresolved` (DOSE_UNRESOLVED). This charges residents with dose received before they boarded, so it is conservative for occupants (a resident's dose ≤ the vehicle's). | spec |
| 22 | Unknown cells, the grid's outside and time after the horizon are unsupported → `unresolved`, never safe (program rule 4). | spec |
| 23 | Validator issues → `model_no_route` with cause `RESOURCE:<code>` from the start of the offending action. | spec |
| 24 | A vehicle's state never improves: after each leg it is the worst so far (model_no_route < unresolved < checked); its `cause` is the first reason that brought it to that level. After a certain violation, later legs are not queried (they cannot change any verdict). | spec |
| 25 | A trip ends with an unloading. Its residents are delivered iff the state at the end of that unloading is `checked` (every occupancy from the vehicle's start through it is checked in all K members). Residents still on board at the end are `model_no_route`. | spec |
| 26 | Residents no itinerary boards are reported as `not_planned`. That is not a verdict: proving that nobody can serve them is a planner's job (scoped `model_no_route` per facility, later milestone). | chosen |
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
