# Building-origin routes graded against the observed footprint, and the 190 no-safe-route buildings diagnosed

**Status: rules pre-registered 2026-09-13 before the run; §4 is appended by the run.**
Asked for by the author's reviewer on 2026-09-13 (tasks 1 and 2 of the note on
`docs/building_origins_juso_yeongdeok.md`). Docs and `data/processed/` only; nothing
registered, nothing on a judge-facing surface; harness paused.

## 1. Population and denominators

Exactly the WFG-275 population and rule (`docs/building_origins_juso_yeongdeok.md`): 19,959
주건물 inside the canonical box → 19,838 within 500 m of a walk node → 19,250 after the
committed origin filter → 4,970 distinct walk nodes, routed once per node on the slope-aware
DiGraph network; each building inherits its node's class. The 121 unsnappable and 588
origin-filtered buildings are reported as exclusions, never imputed. Buildings are not
verified occupied households.

## 2. Observed grading, same rule as `docs/regrade_three_way.md`

The three-way classification (admissible for all / indeterminate / inadmissible for all)
under the same declared bounds A1–A6, applied to the fire-blind and forecast-aware routes of
each node, and counted at node level and at building level (weights = buildings per node).
Paired fire-blind × forecast-aware at both levels.

**Sensitivity to A4 (never-detected cells treated as unaffected):** a second pass in which
every cell within one 500 m cell (8-neighbourhood) of any ever-detected cell is treated as
*possibly affected* — a route touching such a cell before it could be verified clear is
indeterminate rather than admissible. This is the detection floor's spatial half; the miss
allowance of §2 of the three-way page was its temporal half (moot for this event).

## 3. Diagnosis of the 54 no-safe-route nodes (190 buildings), rules

For each node whose forecast class is `no_safe_route` (fire-blind route reaches a refuge but
enters the forecast fire; the time-aware search finds no safe route within 600 min):

| check | what is measured | reading |
|---|---|---|
| snapping | per-building snap distance to the node; count > 200 m | a building far from the node is a map question, not an evacuation finding |
| connectivity | the fire-blind route reached a refuge (by definition of the class); refuge distance and walk time | disconnection is excluded by construction; recorded anyway |
| origin timing (forecast) | earliest forecast time the origin's own cell reaches the p_cut threshold, against the fire-blind walk time to the refuge | 「origin burns before it could arrive」 vs 「a corridor burns」 | <!-- collision-ok: 0.5 -->
| budget | the time-aware route re-run with 900 and 1,200 min budgets | reached ⇒ budget-bound, not fire-bound |
| threshold | the time-aware route re-run with p_cut 0.7 | reached ⇒ threshold-bound |
| observation | the fire-blind route's three-way class against the observed footprint; the origin cell's first detection | admissible-for-all ⇒ the forecast failure is not in the observation |
| vehicle access | `rescuer_reachable` from the four depots on the drive network at W = 75, D = 30 | an access route exists for the rescuer (not a completed transport) |

Categories (a node may carry several flags; the primary label is the first that applies):
**snap-suspect** (≥ half its buildings > 200 m), **budget-bound**, **threshold-bound**,
**forecast-only** (observation admissible for all), **origin-burns-first**,
**corridor-burns** (the rest). 「Credible failures」 = nodes that are none of snap-suspect,
budget-bound, threshold-bound or forecast-only.

## 4. Results

_(appended by `scripts/grade_building_origins_observed.py`; nothing above this line is edited after the run)_

⚠ *First run (2026-09-13T06:07Z, commit 0619826) was discarded before being committed: its A4-dilated pass let a touch of a neighbour-of-detected cell read as 「inadmissible」, stricter than §2 declares (「possibly affected」 ⇒ indeterminate). The base-A4 columns and the diagnosis were unaffected; the run below is the corrected one.*

_Run 2026-09-13T06:15:51Z at `0619826`; artifact `data/processed/building_origins_observed_grading_yeongdeok.json`; forecast partition nodes {'naive_into_FA_safe': 477, 'no_safe_route': 54, 'both_safe': 4439, 'other': 0} (WFG-275: 4439/477/54); 310 s._

### Observed grading (three-way, A4 base | A4 dilated)

| level | arm | admissible for all | indeterminate | inadmissible for all | not reached |
|---|---|---:|---:|---:|---:|
| nodes | fire_blind | 3567 \| 3018 | 936 \| 1485 | 467 \| 467 | 0 |
| nodes | forecast_aware | 3868 \| 3185 | 872 \| 1555 | 176 \| 176 | 54 |
| buildings | fire_blind | 13837 \| 11447 | 3793 \| 6183 | 1620 \| 1620 | 0 |
| buildings | forecast_aware | 15024 \| 12003 | 3362 \| 6383 | 674 \| 674 | 190 |

Paired fire-blind × forecast-aware, buildings, A4 base: admissible_all|admissible_all = 13823, admissible_all|inadmissible_all = 7, admissible_all|indeterminate = 7, inadmissible_all|admissible_all = 350, inadmissible_all|inadmissible_all = 655, inadmissible_all|indeterminate = 425, inadmissible_all|not_reached = 190, indeterminate|admissible_all = 851, indeterminate|inadmissible_all = 12, indeterminate|indeterminate = 2930
Paired, buildings, A4 dilated: admissible_all|admissible_all = 11447, inadmissible_all|admissible_all = 234, inadmissible_all|inadmissible_all = 655, inadmissible_all|indeterminate = 541, inadmissible_all|not_reached = 190, indeterminate|admissible_all = 322, indeterminate|inadmissible_all = 19, indeterminate|indeterminate = 5842

Forecast-only class (1,606 buildings / 477 nodes), forecast-aware route observed: base admissible 373, indeterminate 629, inadmissible 604; dilated 321 / 681 / 604.

### Diagnosis of the no-safe-route nodes

| primary category | nodes | buildings |
|---|---:|---:|
| corridor-burns | 21 | 71 |
| threshold-bound | 18 | 62 |
| snap-suspect | 12 | 54 |
| origin-burns-first | 3 | 3 |

Credible failures (none of snap-suspect / budget-bound / threshold-bound / forecast-only): **24 nodes, 74 buildings**; of these a survival-aware vehicle route from some depot exists (W = 75, D = 30) for 9 nodes / 40 buildings; the origin cell was itself detected at some overpass for 17 of them.

Flag counts over all no-safe-route nodes: snap-suspect: 12, budget-bound: 0, threshold-bound: 24, forecast-only: 0, origin-burns-first: 17, corridor-burns: 21.

Ten largest nodes:

| node | buildings | snap med/max m | fire-blind time | origin cutoff (forecast) | first hazard node time | observed class | origin first seen | vehicle W75 | flags |
|---|---:|---|---:|---:|---:|---|---|---|---|
| 11993250273 | 17 | 306.9/392.4 | 221.2 | None | 46.9 | inadmissible_all | None | True | snap-suspect, threshold-bound |
| 11993250521 | 13 | 42.2/61.8 | 213.8 | None | 32.1 | inadmissible_all | None | True | threshold-bound |
| 11993250491 | 12 | 422.7/475.9 | 206.8 | 180.0 | 25.1 | inadmissible_all | 0.0 | True | snap-suspect, threshold-bound, origin-burns-first |
| 11993250490 | 9 | 97.6/221.6 | 206.5 | 180.0 | 24.8 | inadmissible_all | 333.0 | True | threshold-bound, origin-burns-first |
| 11999560831 | 9 | 85.5/211.6 | 214.5 | None | 32.7 | inadmissible_all | None | True | threshold-bound |
| 11910553952 | 8 | 11.3/18.8 | 113.4 | None | 4.0 | inadmissible_all | 333.0 | True | corridor-burns |
| 11910553953 | 7 | 15.1/21.4 | 112.1 | None | 2.8 | inadmissible_all | 333.0 | True | corridor-burns |
| 11910553954 | 7 | 15.1/20.2 | 113.1 | None | 3.7 | inadmissible_all | 333.0 | True | corridor-burns |
| 11835362721 | 6 | 19.4/77.8 | 58.2 | 180.0 | 3.9 | inadmissible_all | None | True | threshold-bound |
| 11993250508 | 6 | 36.8/73.9 | 211.3 | 180.0 | 29.6 | inadmissible_all | None | True | threshold-bound, origin-burns-first |
