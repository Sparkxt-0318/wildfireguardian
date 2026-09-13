# Corridor-treatment atlas — 영덕 2025, deterministic (rules pre-registered before the run)

**Status: rules declared 2026-09-14 before the run; §6 is appended by the run.** Asked
for by the author (「run the atlas here tonight, take it as far as it goes」). Laptop
session; harness paused; docs and `data/processed/` only; nothing registered, nothing on a
judge-facing surface. New filenames throughout; no committed artifact is modified.

## 1. The question this answers, and the one it does not

**Answers:** on the committed 영덕 forward-simulation model, if a strip of fuel along an
evacuation or vehicle-access corridor were made non-ignitable before the fire, which
strips would keep the most buildings walkable or reachable, how much do the strips
overlap or reinforce each other, and how do corridor-targeted strips compare with the
same amount of treatment placed by fire risk or at random?

**Does not answer:** whether real fuel treatments have these effects. The 「treatment」 is a
declared change to one model input (§3); its consequence is whatever the trained model
does with that input. No treatment history, no causal estimate, no ecological or smoke
cost. This is the deterministic precursor of the atlas program, not the program.

## 2. Base scene and reproduction gate

The canonical 영덕 hazard is rebuilt on this machine exactly as
`scripts/build_canonical_hazard.py` built it (canonical dataset 151,904 / 2,989; LOFO
model excluding 영덕; canvas 128.92–129.77 E, 36.1–36.9 N; 500 m; 4 × 3 h steps; advance
threshold 0.3). **Gate:** the rebuilt stack must match
`data/processed/routing_demo_canonical.npz` cell for cell (max abs diff < 1e-3) and the
building-origin partition must re-derive as 17,454 / 1,606 / 190 buildings on 4,970 nodes
(`docs/building_origins_juso_yeongdeok.md`). If either fails, nothing below is written.

Populations: the 19,250 routed 주건물 (walk side), the 4 OSM depots and the drive network
of the NH-057 scenario (vehicle side), the 50 OSM refuges.

## 3. What a treatment is

A treatment *T* is a set of 500 m cells. In those cells `burnable_frac` is set to **0**
before the forward simulation is re-run with the same model, weather, start state and
canvas. Under the model's own candidate rule (`require_burnable`, threshold 0.05) a treated
cell can never ignite; the fire can still reach cells beyond it, because the model's
distance and neighbourhood features do not require adjacency. That is the only mechanism
by which a strip is 「permeable」 here, and it is the model's, not a spotting model.
Sensitivity: the top three single treatments are re-run at `burnable_frac × 0.5`.

Cost proxy = number of treated cells (25 ha each). No monetary cost.

## 4. Candidate treatments, defined from the base run

**Conflict cells.** For every routed node, the cells its fire-blind shortest walk passes
through that reach p ≥ 0.5 by the walker's arrival time in the base forecast; and for every
node needing rescue (no safe walk at departure 0), the cells of the shortest-time drive
corridor from its nearest depot that reach the vehicle cutoff 0.7 by the responder's
arrival. Each conflict cell carries the buildings behind the routes that cross it.

**Corridor candidates.** Conflict cells are grouped into 8-connected components; a
component larger than **12 cells** is split by k-means on cell centres into chunks of at
most 12. The **20** chunks carrying the most buildings are the corridor candidates
`C01…C20`. (Chunks, not hand-drawn lines: every candidate is where a route actually meets
the forecast fire.)

**Controls, same cell count as the median candidate:** `R1–R3` random burnable cells
inside the fire's 720-min envelope (seeds 1, 2, 3); `H1` the highest-hazard burnable cells
outside the slice-0 footprint (risk-ranked placement, the proposal's first comparator);
`E1` the cells of the fire's own front at 180 min not already burning (a 「hold the line」
placement).

**Pairs.** After the single runs, the top five corridor candidates by buildings kept are
run in all ten pairs.

## 4b. Amendment after the smoke run (2026-09-14, before the sweep)

The smoke run (base gate passed exactly: field max abs diff 0, partition 17,454 / 1,606 /
190) found **29 conflict cells in 5 components**, every one of them **adjacent to the
footprint already burning at detection** (Chebyshev distance 1.0–1.4 cells). Two things
follow that §4 did not anticipate:

- A one-cell strip cannot register in the committed grader: `HazardSequence` interpolates
  bilinearly between 500 m cell centres, so a point 250 m into a treated cell whose
  neighbour burns reads p = 0.5. The first family-A run (12 cells, 731 buildings behind
  it) kept 0 buildings for that reason. This is a **resolution finding**, recorded as such.
- There are only six family-A candidates, not twenty, because the walk routes meet the
  forecast fire only in that ring (most walks end before the 180-min slice).

Declared before the sweep, in addition to §4: **family B** = each family-A chunk dilated by
one cell (burnable, not burning at t0; strips ≥ 3 cells wide); **family P** = the whole
perimeter band of burnable cells within 1 and within 2 cells of the t0 footprint (an upper
bound on what any perimeter treatment can do, at its full cost); **W** = the best family-B
candidate dilated by two cells (a width check). Pairs, the triple and the ×0.5 sensitivity
are run on family B. Controls are sized to the median family-B candidate. Family A is still
run and reported.

## 5. What is measured per run (all against the base)

- **Walk:** building-level classes (both safe / forecast-aware only / no safe route) on the
  treated forecast; `kept_walkable` = reduction in no-safe-route buildings;
  `kept_simple` = increase in buildings whose shortest walk is safe.
- **Vehicle:** for the base needs-rescue nodes, `rescuer_reachable` at W = 75, D = 30 on the
  treated hazard; `kept_reachable` = buildings whose node becomes reachable.
- **Corridor time:** for each candidate's own corridor, the survival time of the treated
  strip's cells and of the routes through it (minutes gained).
- **Envelope:** cells ≥ 0.5 at 720 min, and the count of burning cells *beyond* the treated
  strip (did the fire go around or over it).
- **Interaction** for pairs: `effect(A∪B) − effect(A) − effect(B)` in buildings; positive =
  reinforcing, negative = redundant.
- **Ranking:** buildings kept per treated cell; a greedy budget curve over the singles,
  corrected by measured pair interactions where available.

Outcomes are forecast-graded (the treated forecast is graded on itself, like the committed
arms); the observed footprint cannot grade a counterfactual. Denominators, exclusions and
the reproduction gate are reported first.

## 6. Results

_(appended by `scripts/run_corridor_treatment_atlas.py`; nothing above this line is edited after the run)_

_Run 2026-09-13T19:50:31Z at `be4774d`; artifact `data/processed/corridor_treatment_atlas/atlas_yeongdeok.json` (per-run records under `runs/`); base field reproduced (max abs diff 0.0e+00); building partition {'both_safe': 17454, 'naive_into_FA_safe': 1606, 'no_safe_route': 190}; 4970 nodes / 19250 buildings; 5 min; figures `docs/figures/atlas_*.png`._

Conflict cells 29 in 5 components → 6 chunks; 15 candidates; control size 8 cells. Base: needs-rescue nodes 54, vehicle-reachable buildings 142, envelope cells ≥ 0.5 per slice [249, 692, 952, 981, 1036].

### Single treatments (buildings, vs base; primary = kept walkable + kept reachable)

| id | family | cells | buildings behind routes crossing it | kept walkable | kept reachable | kept simple (shortest walk safe) | primary | per cell | envelope Δ cells (720) | burning beyond strip |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P2 | P | 1611 | — | 0 | 0 | 329 | 0 | 0.0 | -787 | 0 |
| P1 | P | 1030 | — | 0 | 0 | 329 | 0 | 0.0 | -787 | 0 |
| B01 | B | 34 | 731 | 0 | 0 | 325 | 0 | 0.0 | -16 | 1 |
| W01 | W | 63 | — | 0 | 0 | 325 | 0 | 0.0 | -37 | 0 |
| C01 | A | 12 | 731 | 0 | 0 | 309 | 0 | 0.0 | -4 | 0 |
| B02 | B | 33 | 138 | 0 | 0 | 7 | 0 | 0.0 | -22 | 1 |
| C02 | A | 12 | 138 | 0 | 0 | 0 | 0 | 0.0 | -11 | 6 |
| C03 | A | 2 | 73 | 0 | 0 | 0 | 0 | 0.0 | -2 | 9 |
| B03 | B | 9 | 73 | 0 | 0 | 0 | 0 | 0.0 | -6 | 0 |
| C04 | A | 1 | 32 | 0 | 0 | 0 | 0 | 0.0 | 0 | 2 |
| B04 | B | 6 | 32 | 0 | 0 | 0 | 0 | 0.0 | -2 | 5 |
| C05 | A | 1 | 11 | 0 | 0 | 0 | 0 | 0.0 | -1 | 6 |
| B05 | B | 7 | 11 | 0 | 0 | 0 | 0 | 0.0 | -6 | 9 |
| C06 | A | 1 | 1 | 0 | 0 | 0 | 0 | 0.0 | -1 | 5 |
| B06 | B | 6 | 1 | 0 | 0 | 0 | 0 | 0.0 | -3 | 9 |
| R1 | control | 8 | — | 0 | 0 | 0 | 0 | 0.0 | -7 | 3 |
| R2 | control | 8 | — | 0 | 0 | 0 | 0 | 0.0 | -10 | 21 |
| R3 | control | 8 | — | 0 | 0 | 0 | 0 | 0.0 | -14 | 15 |
| H1 | control | 8 | — | 0 | 0 | 0 | 0 | 0.0 | -9 | 0 |
| E1 | control | 0 | — | 0 | 0 | 0 | 0 | 0.0 | 0 | 0 |

### Pairs among the top five (interaction = pair − sum of singles, buildings)

| pair | cells | pair primary | sum of singles | interaction |
|---|---:|---:|---:|---:|
| B01+B02 | 62 | 0 | 0 | +0 |
| B01+B03 | 43 | 0 | 0 | +0 |
| B01+B04 | 40 | 0 | 0 | +0 |
| B01+B05 | 39 | 0 | 0 | +0 |
| B02+B03 | 42 | 0 | 0 | +0 |
| B02+B04 | 39 | 0 | 0 | +0 |
| B02+B05 | 38 | 0 | 0 | +0 |
| B03+B04 | 15 | 0 | 0 | +0 |
| B03+B05 | 16 | 0 | 0 | +0 |
| B04+B05 | 13 | 0 | 0 | +0 |

Triple B01+B02+B03: primary 0 vs sum of singles 0.

### Sensitivity (burnable × 0.5 instead of 0)

- B01x0.5: primary 0 (walkable 0, reachable 0)
- B02x0.5: primary 0 (walkable 0, reachable 0)
- B03x0.5: primary 0 (walkable 0, reachable 0)

### Greedy budget curve (singles, pair-corrected where measured)

| k | added | cumulative cells | cumulative primary (estimate) |
|---|---|---:|---:|
| 1 | P2 | 1611 | 0 |
| 2 | P1 | 2641 | 0 |
| 3 | B01 | 2675 | 0 |
| 4 | W01 | 2738 | 0 |
| 5 | C01 | 2750 | 0 |

### Secondary outcome: buildings whose shortest walk becomes safe (`kept_simple`)

The pre-declared primary is zero for every run (§7). This ranks the declared secondary outcome.

| id | family | cells | kept simple | per cell |
|---|---|---:|---:|---:|
| P2 | P | 1611 | 329 | 0.2 |
| P1 | P | 1030 | 329 | 0.32 |
| B01 | B | 34 | 325 | 9.56 |
| W01 | W | 63 | 325 | 5.16 |
| C01 | A | 12 | 309 | 25.75 |
| B02 | B | 33 | 7 | 0.21 |

| pair | cells | pair kept simple | sum of singles | interaction |
|---|---:|---:|---:|---:|
| B01+B02 | 62 | 329 | 332 | -3 |
| B01+B03 | 43 | 325 | 325 | +0 |
| B01+B04 | 40 | 325 | 325 | +0 |
| B01+B05 | 39 | 325 | 325 | +0 |
| B02+B03 | 42 | 7 | 7 | +0 |
| B02+B04 | 39 | 7 | 7 | +0 |
| B02+B05 | 38 | 7 | 7 | +0 |
| B03+B04 | 15 | 0 | 0 | +0 |
| B03+B05 | 16 | 0 | 0 | +0 |
| B04+B05 | 13 | 0 | 0 | +0 |

Triple B01+B02+B03: kept simple 329 vs sum of singles 332.

- B01x0.5: kept simple 325 (at burnable 0: 325)
- B02x0.5: kept simple 3 (at burnable 0: 7)
- B03x0.5: kept simple 0 (at burnable 0: 0)

## 7. Reading (written after the sweep; 34 runs, all cached under `runs/`)

**The pre-declared primary outcome is zero for every treatment.** No strip, band, pair,
triple, control or sensitivity run changes the no-safe-route class (190 buildings) or the
vehicle-access class (142 of 190 reachable). Those two classes are therefore not
about spread at all on this fire: they are set by where the fire already was when the
satellite first saw it (the t0 footprint, 249 cells) and by the origins' own cells. A
pre-fire treatment of the perimeter cannot move them.

**The secondary outcome moves, and it is concentrated in one place.** Treating the whole
one-cell band around the t0 footprint (P1, 1,030 cells, 258 km²) makes the shortest walk
safe for **329** buildings, and the two-cell band (P2, 1,611 cells) adds nothing. One
12-cell chunk on the fire's eastern flank (C01, 3 km², where 731 buildings' shortest walks
cross the fire) captures **309** of those 329; dilated to 34 cells (B01) 325; to 63 cells
(W01) still 325. The remaining five chunks and all controls (random, risk-ranked) give 0
to 7. Pairs are additive or slightly redundant (B01+B02: −3); nothing reinforces. At half
strength (burnable × 0.5) C01's dilated form keeps its 325; B02 falls from 7 to 3.

**What 329 means against the forecast's own class.** 1,606 buildings reach a refuge only on
the time-aware walk. Even with the fire stopped at its t0 perimeter, 1,277 of them still
need the time-aware route, because their shortest walk crosses ground that was already
burning at detection. So on this fire, at this detection time, **a perimeter treatment can
substitute for the forecast for at most 20 % of the buildings the forecast helps**, and
94 % of that maximum sits in 3 km² on one flank. That is the atlas result, and the map
shows it.

**Three corrections and limits found by the run itself.**

- §4b attributed the first zero to bilinear grading of a one-cell strip. The cause was
  narrower: that smoke candidate was a single cell under the earlier (step-wise) conflict
  rule. A one-cell-wide, 12-cell chunk (C01) does register. The width families B and W are
  kept as run; they show width adds 16 buildings and then nothing.
- Under P1 the modelled fire does not advance at all (envelope 249 cells at every slice):
  once the adjacent ring cannot ignite, the trained model predicts nothing beyond it. The
  model is adjacency-driven and has no spotting; a real fire under 27 m/s gusts would not
  stop at a 500 m band. Every treatment effect here inherits that property.
- The E1 control resolved to zero cells: at 180 min the forecast front is sharp enough that
  no burnable, not-yet-burning cell sits in the 0.3–0.5 band. Reported as void.

**Not shown:** any real treatment effect (this is one model input changed); costs, smoke,
ecology; anything observed (the treated forecast is graded on itself); departures later
than 0 (where later fronts would matter); vehicle occupancy; households; other fires. The
next honest step is the same experiment on a gust-aware 100 m model, where a strip can be
narrower than a village and spotting can be represented.
