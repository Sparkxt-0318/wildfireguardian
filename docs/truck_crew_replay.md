# Truck-crew replay of the 2025-03-25 영덕 fire: the rule, declared before the run

**Status: §1 to §3 pre-registered 2026-09-13 before `scripts/build_truck_crew_replay.py`
was run; §4 is appended by the run and nothing above the §4 line is edited afterwards.**
Built from `docs/auto/briefs/TRUCK_CREW_REPLAY.md` in a laptop session on `auto/dev`
(harness paused). Docs, `data/processed/`, `web/` and `outputs/` only; nothing registered
in `docs/NUMBERS.json`, nothing on a judge-facing surface.

This is a **replay of one committed forecast field against one committed observation**,
shown the way a waiting vehicle crew would read it. It is not a live tool, not a fleet
plan, and not a rescue count.

## 1. Population, and what one row is

The 주건물 population of WFG-275, read (never rewritten) from
`data/processed/building_origins_observed_grading_yeongdeok.json`: 19,250 routable main
buildings on 4,970 distinct walk nodes, of which the forecast partition puts 54 nodes
(190 buildings) in the **no-safe-route** class.

**Rescue-needing walk nodes** are the union of two sets, exactly as the rescue pipeline
defines the population that gets a vehicle instead of a walk:

- **(a) the no-safe-walk class** — the 54 `no_safe_route` nodes of the committed forecast
  partition. These are the nodes where the fire-blind walk enters the hazard and no
  future-aware walk reaches a refuge.
- **(b) the immobile draw** — `rescue_demo._immobile_homes` applied to the 4,970 building
  walk nodes, with the config's `immobile_fraction` (0.3) and `seed` (20250603). This is
  the same deterministic recipe, the same code and the same seed the committed pipeline
  uses on its 444 sampled origins; only the node list it draws from changes. The draw is a
  **modelling assumption about mobility, not a measurement of who lives there**, and it is
  the single largest assumption on this page.

**One row of the replay is one pickup, and a pickup is a drive node.** Each rescue-needing
walk node is snapped to the road network with `drive.nearest_node`; walk nodes that snap to
the same drive node are **one** pickup, and the buildings behind that pickup is the sum over
its walk nodes. This is declared here because the scheduler this build imports keys its
per-home outcome by drive node, so a population with repeated drive nodes would otherwise
order several separate trips to one road point and read them all off one outcome. Each
pickup records its representative walk node, the full list of walk nodes behind it, the
building count, and the median and maximum walk-to-road snap distance, so a reader can see
how far 「the vehicle arrived」 is from the buildings it is for.

## 2. The scheduler, the deadline and the abort rule

**Imported, not re-implemented.** The scheduler is `schedule()` from
`scripts/run_vehicle_pickup_intervention.py`, called unchanged, with its constants
(`T_LOAD` = 10 min, `T_UNLOAD` = 10 min, `MARGIN` = 12 min, `W` = 75 min). Routing,
snapping, corridor sampling, survival times and grading all come from
`src/wildfireguardian/routing/` and `scripts/regrade_three_way.py`.

- **Fleet.** *k* ∈ {4, 2, 6} vehicles, assigned round-robin to the four OSM depots
  (119안전센터 / fire-station points from the 2026-07-24 snapshot), all free at the config's
  dispatch delay *D* = 30 min. *k* = 4 is the headline case, one vehicle per depot.
- **Replay window.** 0 to 720 min, the horizon of the committed forecast field
  `haz_stack`. The clock on the screen is this window.
- **Deadline per pickup.** `min(node_survival_time(drive node, vehicle cutoff 0.7), 720)`:
  the earliest forecast minute the pickup's road point reaches the vehicle cutoff, or the
  end of the replay window, whichever comes first. A pickup whose road point never reaches
  the cutoff inside the window therefore carries the window's own deadline, 720. **This is
  a declared change from `docs/vehicle_pickup_intervention.md`**, which gives such a home
  no binding deadline and lets a vehicle keep working past the forecast horizon: a screen
  with a 720-minute clock cannot order, show or grade a trip that arrives after its clock
  ends, so it does not order one.
- **Trip.** Survival-aware ingress route from the vehicle's current location (its depot, or
  the refuge it last delivered to) departing at its free time, within *W* = 75 min per leg
  and never entering the vehicle cutoff; 10 min loading; survival-aware egress to the
  nearest rescue-reachable refuge departing after loading; 10 min unloading; the vehicle is
  then free at that refuge. One pickup per trip, no pooling.
- **Policy.** Earliest-deadline-first over pickups; each pickup takes the vehicle with the
  earliest feasible arrival; an arrival must satisfy `arrival + 12 ≤ deadline`. No
  re-planning and no look-ahead. Deterministic.
  ⚠ *Clarification added 2026-09-13 after a 60-pickup smoke run of the build script and
  before the reported run; it names a consequence of the rule above and changes nothing in
  it.* The deadline binds the **arrival at the pickup**, not the end of the round trip, so a
  trip ordered at minute 700 can finish unloading after minute 720. Trips whose delivery
  completes after the clock ends are counted and reported separately rather than dropped.
- **Corridor closing minute (forecast).** For the trip's **actual** ingress route, the
  earliest forecast time slice at which any point sampled along it at 150 m spacing reaches
  the vehicle cutoff: `corridor_survival_time(sample_corridor_points(...), 0.7)`. The egress
  route's closing minute is computed the same way. `inf` means the corridor does not close
  inside the forecast window.
- **Margin.** `closing − arrival` for the ingress leg, which is the `closing_window_min` of
  the pipeline's own `IngressResult`. Separately, and labelled separately, each pickup
  records the depot-anchored round-trip margin `round_trip_margin` under the config's
  `same_route` egress doctrine, which is the stricter reading a commander is given
  elsewhere in this repository.
- **Abort rule.** The latest minute the crew may still be at the pickup is
  **`abort_min = closing − 12`**, with `closing` the ingress corridor's forecast closing
  minute and 12 the config's responder safety margin. If the trip's arrival minute is
  later than `abort_min`, **the screen cancels the trip itself**: it is counted
  aborted-by-rule and is never counted as reached. A trip whose corridor does not close
  inside the window has no abort minute and cannot be aborted by this rule. The rule is
  checked after the scheduler has assigned the trip, because the scheduler's own feasibility
  test looks at the pickup's own road point, while this one looks at the whole corridor the
  vehicle drove.
- **Fallback corridor.** For each pickup, `ingress_corridor` is run from each of the four
  depots. The primary is the reachable corridor with the smallest responder ETA; the
  fallback is the next such corridor from a **different depot drive node**, if one exists.
  Both are recorded with their ETA and closing minute. The fallback is shown to the crew;
  it never re-plans the trip and never enters a count.

## 3. The grading rule, declared before the run

Every ingress and every egress leg of every ordered trip is graded against the observed
FIRMS footprint `obs_stack` in the same npz, under the assumptions **A1 to A6 of
`docs/regrade_three_way.md` §2**, with one extension:

- **A6′ — departure is the trip's departure minute.** A6 sets presence time at a node to
  departure 0 plus the cumulative edge times of the route. Here presence time is the
  **trip's own departure minute** plus the cumulative edge times, because a truck-crew trip
  does not start at zero. This is implemented by shifting the observation clock
  (`first_seen` and the six observation times) by the departure minute and calling
  `regrade_three_way.classify_route` **unchanged**. The shift moves every observation and
  every presence time by the same amount and preserves the index of each observation, so
  the classification is the same function of absolute times that A1 to A6 define.

Each leg therefore carries `admissible_all` / `indeterminate` / `inadmissible_all` /
`unsupported` under each miss allowance *m* ∈ {0, 1, ∞}, exactly as the committed re-grade
reports them, and no *m* is chosen after the fact.

**The four counts the finals may quote, defined here before they were measured:**

| count | definition |
|---|---|
| **trips ordered, N** | trips the scheduler assigns inside the replay window |
| **aborted-by-rule, K** | of N, trips whose arrival minute is later than `abort_min = closing − 12`. The screen cancels these; they are never counted as reached |
| **reached before the observed closure, M** | of the N − K trips that were not aborted, those whose pickup cell was **either** never detected in `obs_stack` through 2403 min **or** first detected strictly later than the arrival minute |
| **not reached** | the remainder, N − K − M: the observed footprint had already reached the pickup's cell by the minute the trip arrived |

N = K + M + not-reached by construction. The success line the finals may carry is filled
from exactly these three measured numbers and from nothing else.

⚠ **Two further counts are reported beside them, and the success line may not be quoted
without the first.** *Added 2026-09-13 after the same smoke run and before the reported run;
this adds what is reported, and changes none of the four definitions above.*

- **trips with an inadmissible ingress leg (m = 0)**: ordered trips whose **driven corridor**
  passes through a cell the observation says was already detected by the minute the vehicle
  was in it. 「Reached before the observed closure」 is a statement about the **pickup's own
  cell** only, and a trip can satisfy it while the road it drove was, by the same
  observation, already inside the footprint. The egress legs are counted the same way.
- **trips delivering at the pickup's own road node**: the scheduler's nearest
  rescue-reachable refuge is sometimes the pickup's own drive node, which makes the egress
  leg zero minutes long. Counted so that a zero-length delivery is visible rather than
  flattering the timings.

**What「reached」 does and does not mean.** It means the observed 500 m footprint had not yet
been detected at the pickup's cell when the model's trip arrived there, under A1 to A6 and
A4 in particular (a cell never detected is treated as never fire-affected). It does not mean
a vehicle was there, that a road was passable, or that anyone was moved.

## 3b. What this page and this screen do NOT show

- **Buildings are not households.** Every count on this page is buildings and road points.
  Nobody in this repository knows who is inside them.
- The **immobile draw is an assumption** (§1b), not a register of mobility need. Change the
  fraction or the seed and the population changes.
- **One pickup per trip**; no vehicle capacity in persons, no queues, no road capacity, no
  depot staffing, no acknowledgement latency, no traffic.
- The **deadline is the forecast's**, not the fire's. The forecast field is the committed
  leave-one-fire-out forward simulation, and its errors are this screen's errors.
- The **observation is FIRMS at 500 m** at six times, graded under declared bounds. It is
  not a fire-line map.
- **영덕 only**, one fire, one field, one observation. Nothing here transfers to another
  fire without being run again.
- The **5 h and 8 h markers are the Ready-Set-Go doctrine's lead times**
  (국립산림과학원 briefing, 2026-02-12; `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md`
  §Update 2026-09-10) drawn on this replay's forward clock so the crew can see them. The
  doctrine counts those hours **backwards from the fire line's arrival**; this clock counts
  **forwards from the forecast's zero**. They are not the same axis, and the markers are
  **not** a zoning of any kind. No figure from that note is registered here.
- The buttons on the screen write **local timestamps into the browser's own storage**. They
  are a crew's own record, they reach no server, and they are not evidence of anything.

## 4. Results

_(appended by `scripts/build_truck_crew_replay.py`; nothing above this line is edited after the run)_

_Run 2026-09-13T16:12:50Z at `bb820d6`; artifacts `data/processed/truck_crew_replay_yeongdeok.json`, `web/truck_crew_replay.html`, `outputs/truck_crew_replay/20260913T160454Z/` (24 files); 476 s._

**Population.** 1530 rescue-needing walk nodes (54 in the no-safe-walk class, 1491 in the immobile draw, overlapping) out of 4970 building walk nodes; they snap onto **774 pickups** (road points) carrying 5865 buildings. 756 walk nodes share a pickup with another. 124 of the pickups stand in a cell FIRMS ever detected.

| fleet | trips ordered | reached before observed closure | not reached | aborted by rule | buildings behind ordered trips | last delivery (min) |
|---|---:|---:|---:|---:|---:|---:|
| 2 | 26 | 21 | 3 | 2 | 286 | 719.31 |
| 4 | 52 | 42 | 7 | 3 | 504 | 721.23 |
| 6 | 74 | 60 | 6 | 8 | 673 | 720.79 |

**The count the success line does not carry.** At k = 4, 30 of the 52 ordered trips drove an ingress corridor that passes through a cell the observation says was already detected by the time the vehicle was in it (`inadmissible_all`, m = 0), and 17 did so on the way out. 「Reached before the observed closure」 is a statement about the pickup's own cell and says nothing about the road the vehicle took to get there. The two counts travel together or neither is quoted.

2 of the ordered trips deliver to a refuge that snaps to the pickup's own road node, so their egress leg is zero minutes long; 2 complete their delivery after minute 720, because the deadline binds the arrival at the pickup and not the end of the round trip (§2).

Pickup outcomes at k = 4 (the scheduler's own classes over all 774 pickups): completed 52, missed 722.

Observed class of the ordered trips' legs at k = 4 (A1 to A6 plus A6', docs/regrade_three_way.md §2):

- ingress, m = 0: admissible_all 10, inadmissible_all 30, indeterminate 12
- ingress, m = 1: admissible_all 10, inadmissible_all 30, indeterminate 12
- ingress, m = inf: admissible_all 10, inadmissible_all 30, indeterminate 12
- egress, m = 0: admissible_all 30, inadmissible_all 17, indeterminate 5
- egress, m = 1: admissible_all 30, inadmissible_all 17, indeterminate 5
- egress, m = inf: admissible_all 30, inadmissible_all 17, indeterminate 5

**Success line, filled with the measured numbers (k = 4):**

「2025년 3월 25일 영덕 실제 화재에서, 이 화면이 4대의 차량에 내린 52건의 출동 지시 중 42건은 위성이 관측한 화선이 도달하기 전에 도착했고, 3건은 이 화면이 스스로 중단 규칙으로 취소했다.」

The three numbers in that sentence are `trips_ordered`, `reached_before_observed_closure` and `aborted_by_rule` of the `k4` run in the artifact, defined in §3 before the run. Nothing in it is registered in `docs/NUMBERS.json` and nothing in it is on a judge-facing surface.

## 5. Reading (written after the run)

- **The screen orders trips for a small fraction of the population it is built from, and
  the binding constraint is the clock, not the fleet.** 774 pickups carry the 1,530
  rescue-needing walk nodes; four vehicles order 52 trips inside the 720-minute window and
  722 pickups are never reached. Doubling the fleet from 2 to 4 doubles the trips (26 to
  52) and 4 to 6 nearly doubles them again (52 to 74), so nothing saturates: every vehicle
  is busy until the clock ends. This is the opposite of
  `docs/vehicle_pickup_intervention.md`'s finding on the 24 credible failures, where
  access bound and fleet size changed nothing, and the two are consistent: that population
  was tiny and unreachable, this one is large and reachable but far larger than any fleet
  in this window.
- **The headline count and the corridor count disagree, and the corridor count is the
  uncomfortable one.** At *k* = 4 the screen says 42 of 52 trips arrived before the
  observed footprint reached the pickup's own cell. It also says **30 of those 52 drove a
  corridor that the same observation puts inside the footprint at the minute the vehicle
  was in it**, and 20 of the 42 「reached」 trips are among them. A sentence that quotes the
  42 without the 30 would be true about the pickups and misleading about the fire.
- **The abort rule almost never fires as designed, and where it fires it is mostly
  diagnosing a trip that should not have been ordered.** Across the three fleets 13 trips
  are aborted. **12 of them have an ingress corridor whose forecast closing minute is 0**:
  the corridor was already at the vehicle cutoff before the replay started, so the abort
  minute is negative and the rule is really saying 「this trip was never feasible」. Exactly
  **one** trip, at *k* = 6, is aborted the way the rule was written for: the corridor closes
  at 180 min, the abort minute is 168, and the vehicle would have arrived at 200.6. The
  reason is that the corridor closing minute is sampled along the driven line at 150 m,
  while the router that planned the trip tests cell membership at route **nodes**; the
  finer sampling catches an edge interior the router never looked at
  (`docs/oracle_gap.md` records the same gap for the forecast grading). The abort rule as
  declared is therefore doing two jobs, and only one of them is the job it was written for.
- **The forecast's time resolution is coarser than the rule is written in.** `haz_stack`
  has five slices: 0, 180, 360, 540 and 720 min. Every finite closing minute in this run is
  therefore 0 or 180, and every abort minute is −12 or 168. 「Closing − 12」 reads like a
  measured minute and is a slice boundary minus a constant. A crew reading 168 should read
  it as 「before the 180-minute slice」, not as 12 minutes of warning.
- **The miss allowance does not discriminate inside this window.** The observation has six
  times, of which only 0 and 333 min fall inside the 720-minute replay, so *m* = 0, 1 and ∞
  give identical class counts for every leg. The three-way grading is doing real work at
  the boundary between 「admissible」 and 「indeterminate」 over the walk window and no work at
  all over a truck shift. That is a property of the overpass schedule, not of the rule.
- **Two structural weaknesses in the inputs, both visible on the screen.** The four OSM
  depots snap to **two** distinct drive nodes, so a fallback corridor from a different depot
  road node exists for only 17 of the 52 trips, and at *k* = 2 both vehicles start at the
  same node. And 7 of the 52 ordered trips have a median walk-to-road snap of 300 m or
  more, one of them 1.8 km: for those,「the vehicle arrived」 means it reached a road that far
  from the buildings the pickup counts.
- **The build ran twice, and the second run is the one recorded above.** The first run
  (`20260913T154627Z`) recorded `data/processed/building_origin_routing_juso_main_yeongdeok.json`
  as its building input; that spelling made `scripts/build_artifact_manifest.py` attribute the
  regeneration of two artifacts this build only READS to this build, so the script was changed
  to read the building layer's path out of the population artifact instead and the build was
  re-run. Comparing the two artifacts field by field, **everything except `generated_utc`,
  `stamp`, `seconds` and that one input string is identical**, which is the reproducibility
  check this page would otherwise not have. The first run's stamped output directory was
  removed before anything was committed; nothing committed was overwritten.
- **What this is.** A deterministic replay of one committed forecast against one committed
  observation, in the form a waiting crew would read. It is evidence about what this
  repository's own forecast and routing would have told a crew on 2025-03-25, graded
  afterwards. It is not a rescue count, not a fleet plan and not a claim that any vehicle
  could have driven any of these roads.
