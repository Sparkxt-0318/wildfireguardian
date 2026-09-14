<!-- 2026-09-15, HQ rebase onto the WC-022 head: this page predates WC-022; §10c already states that every earlier field wording on it means the committed hindcast field. The five spellings are licensed as dated records rather than rewritten, because §1–§3b are pre-registration text. -->
# Truck-crew replay of the 2025-03-25 영덕 fire: the rule, declared before the run

**Status: §1 to §3 pre-registered 2026-09-13 before `scripts/build_truck_crew_replay.py`
was run; §4 is appended by the run and nothing above the §4 line is edited afterwards.**
Built from `docs/auto/briefs/TRUCK_CREW_REPLAY.md` in a laptop session on `auto/dev`
(harness paused). Docs, `data/processed/`, `web/` and `outputs/` only; nothing registered
in `docs/NUMBERS.json`, nothing on a judge-facing surface.

<!-- forbidden-ok: wc022-forecast-field -->
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
<!-- forbidden-ok: wc022-forecast-field -->
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
<!-- forbidden-ok: wc022-forecast-field -->
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

⚠ *Label added 2026-09-14 on HQ's instruction (`docs/auto/briefs/TRUCK_CREW_REPLAY_DECISIONS.md` decision 2): this section is the **slice-boundary version** of the abort rule, kept as the record. §6 declares the v2 rule and §7 carries its numbers. **No number in this section was changed.***

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
- ⚠ **The field this replay stands on is now known to be flattered by a training leak, and
  that was measured after this page was written.** `docs/leakfree_fold.md` (G3 / WFG-032,
  run the same day) refits the 영덕 fold with 의성·안동 excluded from training, because the two
  are one fire complex and part of the 의성·안동 detections lie inside the 영덕 acquisition
  box. Its finding: the leak-free field is **roughly half the size** of the canonical one by
  the end of the window, with a per-slice core IoU of about 0.51 against it, and it
  **under-predicts** this fire's growth against the observation.

  Every deadline, corridor closing minute, margin and abort minute on this page is read off
  `haz_stack` of the **canonical** npz, which is the leaked field. **Nothing on this page was
  re-run on the leak-free field, so what the counts in §4 would become is unmeasured and is
  not guessed at here.** Two things can be said without running it. The direction is not
  obvious: a smaller field closes fewer corridors, which would tend to order *more* trips and
  fire the abort rule *less*, but it would also move which pickups carry a binding deadline.
  And the part of §4 that is least exposed is the observed grading, for the reason
  `docs/leakfree_fold.md` §4 gives about its own numbers: the observation does not depend on
  which field planned the route. The 30-of-52 inadmissible ingress corridors are a statement
  about FIRMS and the driven geometry, not about the forecast. Re-running this replay on the
  leak-free field is filed as an open question rather than done here, because the brief
  specifies the canonical field and changing it is not a lap's call.
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

## 6. The v2 rules, declared before the v2 run (2026-09-14)

**Status: §6 pre-registered before `scripts/build_truck_crew_replay_v2.py` was run; §7 is
appended by that run.** These are HQ's answers to the v1 report, transcribed from
`docs/auto/briefs/TRUCK_CREW_REPLAY_DECISIONS.md`; the wording of the rules is theirs, the
implementation and the honesty of the report are this build's. §1 to §5 are untouched.

### 6a. The abort rule, rebuilt on the vehicle's own passage (decision 2)

§2's abort rule asked when the corridor *as a whole* first reaches the vehicle cutoff, and
§5 recorded what that produced: it fired 12 times out of 13 on corridors already cut at
minute 0, and only once on a corridor closing mid-mission. The v2 rule asks the question the
crew actually has:

- Sample the trip's **actual ingress route** at 150 m, as before.
- For each sampled point *i*, let **T_i** be the minute that point reaches the vehicle
  cutoff (0.7), **interpolated linearly in time between the five forecast slices**.
  `HazardSequence.prob_at_points` interpolates linearly in time, so T_i is solved exactly
  from the two bracketing slice values; it is a continuous minute, never a slice index.
  T_i is `inf` where the point never reaches the cutoff inside the window.
- Let **t_i** be the travel minute from the route's start to that point, read off the
  sampler's own construction (it lays points evenly along each segment).
- Departing at minute *d*, the vehicle is at point *i* at *d + t_i*, so the trip is safe iff
<!-- forbidden-ok: wc022-forecast-field -->
  `d + t_i < T_i` for every *i*. The forecast field is monotone in time on this scene
  (checked: no cell's probability ever falls), so the binding constraint is
  **`d* = min_i (T_i − t_i)`**, the latest safe departure, and
  **`abort_min = d* − 12`** with 12 the config's responder safety margin.
- A trip is **aborted by rule v2** iff its actual departure minute is later than
  `abort_min`. A route on which every T_i is `inf` has no abort minute and cannot be
  aborted by this rule.

⚠ **v1 and v2 abort minutes are not the same quantity and must never be compared as if they
were.** v1's is the latest minute to be *at the pickup*; v2's is the latest minute to
*leave the start*. §7 prints both counts side by side for exactly that reason.

### 6b. Four populations, so a config assumption stops driving the headline (decision 3)

The 30 % immobile draw is an assumption about mobility, not a measurement, and in v1 it
supplied almost the whole population. v2 runs four and reports all four:

| key | population | role |
|---|---|---|
| `core_credible` | the diagnosis's **credible** no-safe-walk nodes, which contain the 10-node cluster | honest core (3a) |
| `no_safe_walk` | every node in the forecast partition's **no-safe-route** class | honest core (3b) |
| `immobile_10pct` | the pipeline's own deterministic draw at 0.10, plus the no-safe-walk class | labelled sensitivity (3c) |
| `immobile_30pct` | the same draw at 0.30 (this is v1's population) | labelled sensitivity (3c) |

The two honest-core populations are run at *k* = 4, 2 and 6; the two sensitivity
populations at *k* = 4 only, because they are the expensive ones and the fleet sweep already
has its answer from v1. **Any finals sentence is written from the honest-core populations
only**, and per decision 1 no sentence is quotable at all yet.

### 6c. A leak-free field arm beside the canonical one (decision 6)

Every population is also run on `data/processed/routing_demo_leakfree.npz`, the refit that
excludes 의성·안동 from training (`docs/leakfree_fold.md`). The canonical field **stays the
base**; the leak-free run is a sensitivity arm, reported side by side, and the author
decides whether the base ever moves. The observation is unchanged between the two files
(`obs_stack` is byte-identical, checked), so the grading clock never depends on which
forecast planned the route.

### 6d. What v2 does not change

The scheduler, the deadline, the trip structure, the fleet policy, the grading rule A1 to
A6 and A6', and every caveat in §3b. The v1 artifact, page and outputs are not rewritten:
new results get new filenames.

## 7. Results, v2 (appended by `scripts/build_truck_crew_replay_v2.py`; nothing in §6 is edited after the run)

_Run 2026-09-14T10:54:50Z at `a3a2b73`; artifact `data/processed/truck_crew_replay_v2_yeongdeok.json`; 926 s._

**Populations** (pickups are road points; a walk node that shares a road point with another is one pickup):

| field | population | walk nodes | pickups | buildings |
|---|---|---:|---:|---:|
| canonical | core_credible | 24 | 12 | 74 |
| canonical | no_safe_walk | 54 | 28 | 190 |
| canonical | immobile_10pct | 549 | 394 | 2220 |
| canonical | immobile_30pct | 1530 | 774 | 5865 |
| leakfree | core_credible | 24 | 12 | 74 |
| leakfree | no_safe_walk | 54 | 28 | 190 |
| leakfree | immobile_10pct | 549 | 394 | 2220 |
| leakfree | immobile_30pct | 1530 | 774 | 5865 |

**The four counts under the v2 abort rule**, with v1's abort count beside them so the change in the rule is visible:

| field | population | k | ordered | reached | not reached | aborted (v2) | aborted (v1, slice) | no abort minute | ingress inadmissible (m = 0) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| canonical | core_credible | 2 | 6 | 4 | 0 | 2 | 2 | 3 | 1 |
| canonical | core_credible | 4 | 6 | 4 | 0 | 2 | 2 | 4 | 1 |
| canonical | core_credible | 6 | 6 | 4 | 0 | 2 | 2 | 4 | 1 |
| canonical | immobile_10pct | 4 | 48 | 40 | 0 | 8 | 7 | 36 | 17 |
| canonical | immobile_30pct | 4 | 52 | 41 | 6 | 5 | 3 | 42 | 30 |
| canonical | no_safe_walk | 2 | 20 | 6 | 2 | 12 | 11 | 7 | 12 |
| canonical | no_safe_walk | 4 | 21 | 8 | 1 | 12 | 11 | 6 | 12 |
| canonical | no_safe_walk | 6 | 21 | 9 | 1 | 11 | 10 | 3 | 11 |
| leakfree | core_credible | 2 | 6 | 4 | 0 | 2 | 2 | 4 | 1 |
| leakfree | core_credible | 4 | 6 | 4 | 0 | 2 | 2 | 4 | 1 |
| leakfree | core_credible | 6 | 6 | 4 | 0 | 2 | 2 | 4 | 1 |
| leakfree | immobile_10pct | 4 | 52 | 49 | 1 | 2 | 5 | 47 | 17 |
| leakfree | immobile_30pct | 4 | 54 | 51 | 3 | 0 | 0 | 51 | 19 |
| leakfree | no_safe_walk | 2 | 21 | 6 | 6 | 9 | 9 | 12 | 16 |
| leakfree | no_safe_walk | 4 | 21 | 9 | 3 | 9 | 9 | 12 | 11 |
| leakfree | no_safe_walk | 6 | 21 | 9 | 3 | 9 | 9 | 12 | 11 |

The success line is **not** filled here: HQ decision 1 says it is not quotable, and decision 3 says the finals sentence is written from the two honest-core populations only. The numbers above are the record, not a claim.

## 8. Reading of the v2 run (written after it)

- ⚠ **The v2 abort rule is better than v1 and it does not fix what it was asked to fix.**
  Decision 2 was written because v1 fired 12 times out of 13 on corridors already cut at
  minute 0 rather than on corridors closing mid-mission. Across the 16 v2 runs there are
  **89 aborts, of which 81 have a latest-safe-departure of zero or less** — that is, the
  route was already compromised before the vehicle could leave — and only **8 are the
  mid-mission case the rule was rebuilt for**, where a real departure window existed and
  the trip missed it. v1 on the same trips fires 86 times. So the rule is now expressed in
  continuous minutes, it is consistent with the router's own test, and it catches eight
  genuine cases instead of about one; the dominant class is unchanged. **This is reported
  as a partial result, not as the repair decision 2 hoped for.**
- **Why the class persists, and it is the same gap twice.** The router plans on **cell
  membership at route nodes**; the abort rule samples the driven line every 150 m and reads
  the field with `prob_at_points`, which interpolates **bilinearly in space**. An edge
  interior between two admissible nodes can therefore sit above the cutoff from minute 0.
  `docs/oracle_gap.md` records this gap for the forecast grading and §5 recorded it for v1;
  v2 measures it again under a stricter rule. Closing it needs the router and the abort
  rule to sample the same way, which is a change to the router and not a lap's call.
- **The honest-core populations are much smaller and much less flattering than v1's
  headline.** At *k* = 4 on the canonical field: `core_credible` orders **6** trips, 4 of
  which arrive before the observed footprint reaches the pickup cell, 2 aborted;
  `no_safe_walk` orders **21**, of which **8** arrive, 1 does not, and **12 are aborted by
  the rule**. v1's 52-ordered / 42-reached line came almost entirely from the 30 % immobile
  draw, which decision 3 correctly refused to let drive the headline. On the population
  this project can actually defend, more than half the orders are cancelled by the screen's
  own rule.
- **The fleet sweep is flat on the honest core.** `core_credible` gives 6 / 4 / 2 at
  *k* = 2, 4 and 6 alike, and `no_safe_walk` moves only from 20 to 21 orders. As in
  `docs/vehicle_pickup_intervention.md`, access binds and vehicles do not.
- **The leak-free arm confirms §5's prediction about direction, and barely touches the
  honest core.** §5 said a smaller field would close fewer corridors and so order more trips
  and fire the abort rule less, while warning the direction was not obvious. It holds where
  the field does most of the work: at *k* = 4 the 30 % immobile arm goes from 52 ordered /
  41 reached / 5 aborted on the canonical field to **54 / 51 / 0** on the leak-free one.
  But on `core_credible` the two fields give **identical** counts (6 / 4 / 2), and on
  `no_safe_walk` they differ modestly (8 reached / 12 aborted → 9 reached / 9 aborted).
  **The populations the finals would quote are the ones least sensitive to the leak**,
  which is the most reassuring thing in this run. The canonical field remains the base.
- **What is still not quotable.** Per decision 1, nothing here goes on a judge-facing
  surface and no success line is filled. Whenever one is, it is written from
  `core_credible` and `no_safe_walk` only, and it travels with the corridor count in the
  same sentence. The corridor counts remain the uncomfortable half: 12 of 21 `no_safe_walk`
  ingress legs at *k* = 4 are `inadmissible_all` on the observation.
- **What v2 does not touch.** Everything in §3b still holds. Buildings are not households,
  the deadline is the forecast's, the observation is FIRMS at 500 m, and this is 영덕 only.

## 9. What the benchmark found about this page's field (2026-09-14, after §8)

`docs/benchmark/results_v0.1.md` landed on `auto/dev` after §8 was written and says two
things that bear directly on every number above. Neither was known when §1 to §3b were
pre-registered, and neither is a reason to change them; they are recorded here because a
page that did not say them would be claiming more than it can.

- ⚠ **The field this replay stands on is a hindcast, not a forecast.**
  `spread_v2.forward_sim.forward_simulate` advances each step with ERA5 reanalysis at times
  **after T0**, so under the project's own benchmark protocol the committed 영덕 field is in
  the **hindcast track**. It is a reconstruction of what the fire did with the weather that
  actually occurred, not something anyone could have issued at minute 0. **Everywhere this
  page says 「the forecast」 — the deadline, the corridor closing minute, the margin, the
  abort minute — it should be read as 「the reconstruction」.** No crew could have held these
  numbers at minute 0. This does not make the replay worthless: it remains a faithful test
  of what the routing and decision layer do *given* a field, which is the layer this project
  contributes. It does mean the screen is not evidence that a forecast was available.
- ⚠ **On roads, almost everything this field says, it says at minute 0.**
  The benchmark measured that at road nodes the field differs from 「nothing spreads」 by
  three nodes at p ≥ 0.5. Asked at the **vehicle cutoff on the drive network**
  (`scripts/measure_field_road_closure.py`, artifact
  `data/processed/field_road_closure_yeongdeok.json`), the answer is starker:

  | field | drive nodes at or above 0.7 at t = 0 | drive nodes the field adds later |
  |---|---:|---:|
  | canonical | 37 | **9** |
  | leak-free | 37 | **0** |

  Of 1,664 drive nodes, the canonical field closes **nine** during the whole 720-minute
  window, and the leak-free field closes **none**. So this page's central quantity — a
  corridor that closes *during* the mission — rests on nine road points on the canonical
  field and does not exist at all on the leak-free one.

**This is the explanation §8 was missing.** The 81-of-89 aborts that are 「never safe to
depart」, and the leak-free arm's zero aborts at *k* = 4, are not two separate puzzles: the
field has almost no dynamic road-closure content on this scene, so the abort rule has almost
nothing to fire on except what is already true before the clock starts. Rebuilding the rule
a third time would not change that; the limit is in the field, not the rule. **That is the
honest ceiling on the truck-crew replay as a timeline, and it should be said out loud before
any part of this reaches a judge.**

## 10. The line-sampled router arm, declared before it ran (2026-09-14)

**Status: §10 pre-registered before `scripts/build_truck_crew_replay_linesampled.py` was
run; §11 is appended by that run.** HQ's round-two answer 1. *HQ's instruction called this
「§7」; this page already had §7 to §9 when the instruction was written, so the arm is
pre-registered here as §10 and nothing was renumbered.*

### 10a. What the arm changes, and what it must not

§8 measured that 81 of 89 v2 aborts are the 「never safe to depart」 class, and §9 found why:
the router tests **cell membership at route nodes** while the abort rule reads the
**interpolated field along the driven line every 150 m**, so an edge interior between two
admissible nodes can be over the cutoff from minute 0. HQ's decision: **do not change
`rescuer_route`.** Instead, add one arm in which the router's own hazard test reads the same
line the abort rule reads, and report the difference. The mismatch is a property of the
router; measuring it is the finding.

- **New function, nothing edited.** `rescue.rescuer_route_line_sampled`, beside
  `rescuer_route`, which is untouched and remains the committed router.
- **The test.** `rescue.edge_line_closing_minutes` gives, per directed edge, the latest clock
  `E_e` at which the edge may be **entered** with every 150 m sampled point still below the
  vehicle cutoff: `E_e = min_j (T_j − t_j)` over that edge's sampled points, with `T_j` the
  cutoff-crossing minute interpolated linearly in time between the forecast slices and `t_j`
  the travel time from the edge's start to that point. This is the **abort rule v2 at edge
  scale**, and its definition and name are unchanged.
- **The router.** An edge is admissible iff the vehicle enters it at or before `E_e`. Because
  the field is monotone in time on this scene (checked, §6a) arriving earlier is never worse,
  so Dijkstra on travel time with the constraint checked at relaxation returns the quickest
  line-admissible route. Budget, cutoff, spacing, dispatch delay: all the config's, unchanged.
- **How the arm is run without editing the scheduler.** The identical scheduler
  (`run_vehicle_pickup_intervention.schedule`) and the identical build path are used, with the
  name `rescuer_route` **bound** to `rescuer_route_line_sampled` in the two modules that call
  it, for the duration of the arm only. Neither module is edited, and the binding is recorded
  in the artifact.

### 10b. What is run, and what is reported

Three populations — `core_credible`, `no_safe_walk`, `immobile_30pct` (v1's population) — on
**both** fields, canonical and leak-free, so the table is canonical/leak-free × v2/line-sampled.
The two honest-core populations at *k* = 2, 4 and 6; `immobile_30pct` at *k* = 4, matching §7's
shape. Artifact: `data/processed/truck_crew_replay_yeongdeok_v2_linesampled.json`.

Reported beside §7's v2 numbers, for each cell of that table: **trips ordered, reached before
the observed closure, not reached, aborted by rule**, plus the count of trips with no abort
minute and the ingress legs graded `inadmissible_all` at *m* = 0. The abort rule applied to
this arm's trips is **v2, unchanged** — only the router differs.

### 10c. The word 「forecast」 on this page

`docs/benchmark/results_v0.1.md` §2 and `docs/auto/briefs/K_SPREAD_BENCHMARK_REPORT.md` §4a
establish that `forward_simulate` advances each step with ERA5 reanalysis at times after T0, so
the committed field is a **hindcast** under the project's own protocol. **Throughout this page,
including §1 to §9 which are pre-registration and appended results and are therefore not
<!-- forbidden-ok: wc022-forecast-field -->
rewritten, 「the forecast field」 means「the committed hindcast field (canonical)」 and 「the
forecast's deadline」 means the deadline that field implies.** Per
`docs/auto/briefs/HINDCAST_CORRECTION.md` A1 the *method* keeps its name: 「forecast-aware
routing」 names a router that consumes a time-varying field, which is true however the field was
made. What is corrected is the description of the **field**, never the method, the classes or
the keys. This paragraph governs every earlier mention on this page.

## 11. Results, line-sampled arm (appended by `scripts/build_truck_crew_replay_linesampled.py`; §10 is not edited after the run)

_Run 2026-09-14T13:01:44Z at `494618f`; artifact `data/processed/truck_crew_replay_yeongdeok_v2_linesampled.json`; 42 s._

**How much of the road network the line test cuts**, before any trip is planned:

| field | directed edges | ever close | already cut at t = 0 |
|---|---:|---:|---:|
| canonical | 4638 | 94 | 46 |
| leakfree | 4638 | 54 | 46 |

**The four counts, line-sampled router beside the v2 (cell-membership) router.** Same scheduler, same abort rule v2, same populations; only the router's admissibility test differs.

| field | population | k | arm | ordered | reached | not reached | aborted | no abort minute | ingress inadmissible (m = 0) |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|
| canonical | core_credible | 2 | **line-sampled** | 4 | 4 | 0 | 0 | 4 | 0 |
| canonical | core_credible | 2 | v2 (cell) | 6 | 4 | 0 | 2 | 3 | 1 |
| canonical | core_credible | 4 | **line-sampled** | 4 | 4 | 0 | 0 | 4 | 0 |
| canonical | core_credible | 4 | v2 (cell) | 6 | 4 | 0 | 2 | 4 | 1 |
| canonical | core_credible | 6 | **line-sampled** | 4 | 4 | 0 | 0 | 4 | 0 |
| canonical | core_credible | 6 | v2 (cell) | 6 | 4 | 0 | 2 | 4 | 1 |
| canonical | immobile_30pct | 4 | **line-sampled** | 55 | 51 | 4 | 0 | 48 | 24 |
| canonical | immobile_30pct | 4 | v2 (cell) | 52 | 41 | 6 | 5 | 42 | 30 |
| canonical | no_safe_walk | 2 | **line-sampled** | 11 | 9 | 1 | 1 | 6 | 4 |
| canonical | no_safe_walk | 2 | v2 (cell) | 20 | 6 | 2 | 12 | 7 | 12 |
| canonical | no_safe_walk | 4 | **line-sampled** | 11 | 9 | 1 | 1 | 6 | 4 |
| canonical | no_safe_walk | 4 | v2 (cell) | 21 | 8 | 1 | 12 | 6 | 12 |
| canonical | no_safe_walk | 6 | **line-sampled** | 11 | 9 | 1 | 1 | 7 | 3 |
| canonical | no_safe_walk | 6 | v2 (cell) | 21 | 9 | 1 | 11 | 3 | 11 |
| leakfree | core_credible | 2 | **line-sampled** | 4 | 4 | 0 | 0 | 4 | 0 |
| leakfree | core_credible | 2 | v2 (cell) | 6 | 4 | 0 | 2 | 4 | 1 |
| leakfree | core_credible | 4 | **line-sampled** | 4 | 4 | 0 | 0 | 4 | 0 |
| leakfree | core_credible | 4 | v2 (cell) | 6 | 4 | 0 | 2 | 4 | 1 |
| leakfree | core_credible | 6 | **line-sampled** | 4 | 4 | 0 | 0 | 4 | 0 |
| leakfree | core_credible | 6 | v2 (cell) | 6 | 4 | 0 | 2 | 4 | 1 |
| leakfree | immobile_30pct | 4 | **line-sampled** | 55 | 51 | 4 | 0 | 52 | 19 |
| leakfree | immobile_30pct | 4 | v2 (cell) | 54 | 51 | 3 | 0 | 51 | 19 |
| leakfree | no_safe_walk | 2 | **line-sampled** | 12 | 8 | 3 | 1 | 11 | 6 |
| leakfree | no_safe_walk | 2 | v2 (cell) | 21 | 6 | 6 | 9 | 12 | 16 |
| leakfree | no_safe_walk | 4 | **line-sampled** | 12 | 9 | 3 | 0 | 12 | 4 |
| leakfree | no_safe_walk | 4 | v2 (cell) | 21 | 9 | 3 | 9 | 12 | 11 |
| leakfree | no_safe_walk | 6 | **line-sampled** | 12 | 9 | 3 | 0 | 12 | 3 |
| leakfree | no_safe_walk | 6 | v2 (cell) | 21 | 9 | 3 | 9 | 12 | 11 |

Nothing here is quotable (HQ decision 1). The committed field is a hindcast (§10c), so these counts measure what the routing method gains from a given spread field, not the accuracy of a forecast.

## 12. Reading of the line-sampled arm (written after it)

- **The aborts were the router's mistake, not the fire's.** Giving the router the same 150 m
  line test the abort rule uses collapses the abort count almost to nothing: on the canonical
  field at *k* = 4, `no_safe_walk` goes from **12 aborts to 1**, `core_credible` from 2 to 0,
  `immobile_30pct` from 5 to 0. §8 asked whether the 81-of-89 「never safe to depart」 class was
  a property of the field or of the rule. The answer this arm gives is **neither: it was a
  property of the router.** The committed router planned trips down lines it had not looked at,
  and the abort rule then cancelled them. When the two agree, there is almost nothing to cancel.
- **The price is that far fewer trips are ordered at all.** `no_safe_walk` at *k* = 4 orders
  **21** trips under the committed router and **11** under the line-sampled one; `core_credible`
  6 and 4. The pickups that vanish do not become reachable — they move from 「ordered, then
  aborted」 to 「never ordered」. **That is the more honest bookkeeping and it is a worse
  headline**, which is the usual direction for this project.
- **What does not move is the number that mattered.** 「Reached before the observed closure」 is
  **8** under the committed router and **9** under the line-sampled one for `no_safe_walk` at
  *k* = 4; on `core_credible` it is 4 under both, on every fleet size and on both fields. The
  trips this screen would actually have completed are the same trips; what changes is how many
  doomed orders travel beside them. **A reader who only ever saw the 「reached」 count would not
  have noticed the defect, which is the argument for printing all four counts.**
- **The ingress legs the observation condemns roughly halve.** `no_safe_walk` at *k* = 4 goes
  from **12** `inadmissible_all` ingress legs to **4**; `immobile_30pct` from 30 to 24. The
  line test refuses some of the corridors FIRMS says were already burning. It does not refuse
  all of them, because the two tests answer different questions: the router reads the committed
  hindcast field, the grading reads the observation, and §9's point stands that the field has
  almost no dynamic road content to read.
- **The line test cuts about two per cent of the road network, and half of that at minute 0.**
  Of 4,638 directed edges, **94 ever close** on the canonical field and **54** on the leak-free
  one; **46 are already cut at t = 0 on both**. So the difference between the two fields, on the
  roads a vehicle can actually use, is **40 edges** — and the difference between either field
  and 「nothing closes after minute 0」 is 48 and 8 edges respectively. This is §9's finding at
  edge resolution and it is the ceiling on everything above.
- **What this does not license.** Nothing here says the line-sampled router is the right router.
  It says the committed router's admissibility test and this page's abort rule disagree, that
  the disagreement explains the abort counts, and that fixing it lowers the headline while
  leaving 「reached」 alone. Whether `rescuer_route` should change is HQ's call and
  `docs/oracle_gap.md` is where that argument belongs; §10a records that HQ said not to change
  it, and it was not changed.
