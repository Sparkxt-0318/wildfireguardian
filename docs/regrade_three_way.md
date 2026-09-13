# Three-way re-grade against the observed footprint (WFG-213, second pass)

**Status: rule pre-registered 2026-09-13 before the run; §5 is appended by the run.**
Asked for by the author on 2026-09-13: can the committed routes be classified as
*admissible for every condition consistent with the declared evidence bounds*,
*inadmissible for every such condition*, or *indeterminate*, instead of the two step-hold
rules of `docs/regrade_against_observed.md`? This page declares the bounds first and then
reports what falls out. Docs and `data/processed/` only; nothing registered, nothing on a
judge-facing surface.

## 1. The evidence, exactly

`data/processed/routing_demo_canonical.npz` → `obs_stack`: the cumulative FIRMS-detected
footprint on the canonical 500 m grid at six observation times, 0 / 333 / 1005 / 1480 /
1812 / 2403 min after the routing clock's zero. It is monotone (a detected cell stays
detected). For a cell *c*, `first_seen(c)` is the earliest observation at which it is
detected; 27,213 of 28,236 cells are never detected through 2403 min. Of the detected
cells, 249 are detected at 0, **688 at 333**, 50 at 1005, 1 at 1480, 33 at 1812, 2 at
2403. The walk budget is 600 min, so the 0→333 interval carries almost all of the
classification.

The routes are the committed ones: fire-blind, forecast-aware and the 영덕 zero-buffer
present-perimeter arm (`docs/present_perimeter_yeongdeok.md`, a **different experiment**
from the stated 의성·안동 budgeted opponent of `docs/fair_opponent_line.md`), planned on the
forecast, departure 0, 458 origins. Nothing is re-planned.

## 2. Declared assumptions (the "evidence bounds")

- **A1 — detection is fire.** A detected cell was fire-affected at its detection time.
  (FIRMS false alarms are not modelled; `obs_stack` was built at the project's detection
  floor, `docs/detection_floor.md`.)
- **A2 — no verified absence.** A non-detection does not establish absence. The earliest
  time a cell first seen at *T_k* may have been fire-affected is bounded only by a
  declared **miss allowance *m***: the fire may have been present since *T_{k−1−m}*
  (with *T_{<0}* := 0). Three values are reported and none is chosen after the fact:
  *m* = 0 (detected at the first overpass after arrival), *m* = 1 (at most one overpass
  missed), *m* = ∞ (any time from 0; only A4 remains).
- **A3 — persistence.** Once fire-affected, a cell counts as hazardous for the rest of the
  walk window (the cumulative footprint, the model's own p ≥ 0.5 convention). A burned-over
  cell may in fact be passable; **this classifies fire exposure under the model's own
  admissibility rule, not road passability.** Heat, smoke and road damage are not observed.
- **A4 — never-detected means not fire-affected in the window.** Cells with no detection
  through 2403 min are treated as never hazardous. This is an assumption, not verified
  absence; it is what every rule that reads `obs_stack` must assume, and it is where the
  detection floor enters.
- **A5 — spatial sampling.** Exposure is sampled at route **nodes**, in the 500 m cell that
  contains each node (cell membership). Edge interiors are not sampled (`docs/oracle_gap.md`
  records the same limit for the forecast grading). Nodes outside the grid are
  **unsupported** and counted separately.
  ⚠ *Correction, written after the run (2026-09-13):* the first draft of this line said
  「exactly as `_evaluate_path` samples the forecast」. That was wrong about the grader, not
  about this rule: `HazardSequence.prob_at` interpolates **bilinearly between cell centres**,
  so a node near the edge of a detected cell with undetected neighbours reads below 0.5
  there. The rule as pre-registered and as run is cell membership, which is the stricter
  reading of a binary footprint; §6 reconciles it with the first pass, which went through
  the interpolating grader.
- **A6 — temporal sampling.** Presence time at node *i* is departure 0 plus the cumulative
  edge times of the committed route (flat or slope-adjusted as the arm was run).

## 3. The classification (per route that reached a refuge on the forecast, within budget)

Let *t_i* be the presence time at node *i* and *c_i* its cell.

| class | condition |
|---|---|
| **inadmissible for all** | ∃ *i*: `first_seen(c_i)` ≤ *t_i* — fire verified present by then (A1, A3) |
| **admissible for all (m)** | ∀ *i*: `c_i` never detected (A4) **or** *t_i* < earliest_m(c_i) = *T_{k−1−m}* |
| **indeterminate (m)** | neither: some node stands in a cell inside [earliest_m, first_seen) |
| not reached / over budget | the committed plan itself failed (from the forecast run) |
| unsupported | a node lies outside the hazard grid |

Under *m* = ∞, earliest = 0 for every detected cell, so "admissible for all" means the
route never touches a cell detected at any time through 2403 min. Under *m* = 0 the
"will be seen" rule of the first pass is recovered up to its ε; "seen so far" is exactly the
complement of "inadmissible for all". The first pass's two rules are therefore the two
edges of this classification and are kept beside it.

## 4. What is reported

Counts per arm and per *m* over 458 origins with the four classes above plus
not-reached; the paired table fire-blind × forecast-aware; the 42 forecast-only origins by
class; and the count of routes that are admissible for all under *m* = 0 but indeterminate
under *m* = 1, which is the number that one more overpass would settle. What would tighten
the bounds: a second sensor with a shorter revisit between 0 and 333 min (GK2A,
`docs/detection_floor.md`), an independent road-closure record, and any observed-absence
product; none exists in the repository.

## 5. Results

_(appended by `scripts/regrade_three_way.py`; nothing above this line is edited after the run)_

_Run 2026-09-13T03:02:29Z at `e96471c`; artifact `data/processed/regrade_three_way_yeongdeok.json`; partition re-derived as 414 / 42 / 2; 458 origins each row._

| arm | m | admissible for all | indeterminate | inadmissible for all | unsupported | not reached |
|---|---|---:|---:|---:|---:|---:|
| fire-blind | 0 | 329 | 91 | 38 | 0 | 0 |
| fire-blind | 1 | 329 | 91 | 38 | 0 | 0 |
| fire-blind | inf | 329 | 91 | 38 | 0 | 0 |
| forecast-aware | 0 | 351 | 86 | 19 | 0 | 2 |
| forecast-aware | 1 | 351 | 86 | 19 | 0 | 2 |
| forecast-aware | inf | 351 | 86 | 19 | 0 | 2 |
| present perimeter (영덕, 0 buffer) | 0 | 331 | 103 | 22 | 0 | 2 |
| present perimeter (영덕, 0 buffer) | 1 | 331 | 103 | 22 | 0 | 2 |
| present perimeter (영덕, 0 buffer) | inf | 331 | 103 | 22 | 0 | 2 |

The 42 forecast-only origins, forecast-aware route:

- m = 0: admissible 9, indeterminate 16, inadmissible 17, not reached 0
- m = 1: admissible 9, indeterminate 16, inadmissible 17, not reached 0
- m = inf: admissible 9, indeterminate 16, inadmissible 17, not reached 0

Paired fire-blind × forecast-aware (class of fire-blind route | class of forecast-aware route):

- m = 0: admissible_all|admissible_all = 329, inadmissible_all|admissible_all = 8, inadmissible_all|inadmissible_all = 19, inadmissible_all|indeterminate = 9, inadmissible_all|not_reached = 2, indeterminate|admissible_all = 14, indeterminate|indeterminate = 77
- m = 1: admissible_all|admissible_all = 329, inadmissible_all|admissible_all = 8, inadmissible_all|inadmissible_all = 19, inadmissible_all|indeterminate = 9, inadmissible_all|not_reached = 2, indeterminate|admissible_all = 14, indeterminate|indeterminate = 77
- m = inf: admissible_all|admissible_all = 329, inadmissible_all|admissible_all = 8, inadmissible_all|inadmissible_all = 19, inadmissible_all|indeterminate = 9, inadmissible_all|not_reached = 2, indeterminate|admissible_all = 14, indeterminate|indeterminate = 77

Routes admissible under m = 0 but indeterminate under m = 1 (what one more overpass between 0 and 333 min would settle): fire-blind 0, forecast-aware 0, present perimeter 0.

Reading: the count of routes 「inadmissible for all」 is the same under every m, because it rests on A1 alone; what m moves is the split of the remainder between 「admissible」 and 「indeterminate」. Under m = ∞ nothing that touches a cell detected at any time through 2403 min can be called admissible, which is the honest floor without an absence product. These are repository measurements of the committed routes under the declared assumptions; none is a safety rate.

## 6. Reading, and two corrections to the first pass

- **The miss allowance *m* is moot for this event.** Every route touch of a detected cell
  inside the 600-min window is a touch of a cell first seen at 333 min (earliest possible
  time 0 under *m* = 0 already) or later at ≥ 333 min; no route stands in a cell first seen at
  1005 min before 333 min. So *m* = 0, 1 and ∞ give identical tables, and the whole
  indeterminate class is the 0→333 min gap between the ignition-time detection and the
  first overpass. That gap is the evidence needed: one observation inside it.
- **The first pass was softer than a binary footprint warrants.** `docs/regrade_against_observed.md`
  graded through `HazardSequence`, which interpolates the 0/1 footprint bilinearly between
  cell centres; its 「seen so far」 count of 456 forecast-aware routes safe corresponds to
  **437** here (458 − 19 inadmissible − 2 not reached) under cell membership. The first-pass
  table is kept as the record; this page is the reading to quote, and it is the less
  favourable one.
- **Of the 42 forecast-only origins, 17 forecast-aware routes are inadmissible for all**:
  they stand, at their own arrival time, in a cell FIRMS had already detected. 9 are
  admissible under every declared bound and 16 sit in the indeterminate gap. Paired: the
  forecast-aware route is admissible where the fire-blind one is inadmissible for 8 origins
  and indeterminate-vs-inadmissible for 9; the reverse (fire-blind admissible, forecast-aware
  not) occurs 0 times. So the direction of the forecast's help survives; its size does not,
  and 17 of the 42 point the other way.
- What none of this is: a passability measurement (A3), a survival rate, or a statement
  about the 의성·안동 comparator, which was not re-graded (no observed footprint is committed
  for that region).
