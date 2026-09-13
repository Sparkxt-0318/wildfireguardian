# Evacuation feasibility phase diagram — 영덕, real hazard (deterministic sensitivity study)

**Status: grid and definitions pre-declared 2026-09-13 before the run; §5 is appended by the
run.** Asked for by the author for the 2026-10-16 freeze. Docs and `data/processed/` only;
nothing registered, nothing on a judge-facing surface. This is a **deterministic sensitivity
study on one committed hazard field**: no ensemble, no probability over scenarios, and no
claim of robustness to anything not varied here.

## 1. What is varied, and what is held

Base scene: exactly the NH-057 real-hazard scenario (`scripts/run_rescue_routing_real_hazard.py`):
the canonical 영덕 LOFO forward simulation as hazard (500 m, 0–720 min), the 2026-07-24 OSM
snapshots for walk and drive networks, 50 OSM refuges, 4 OSM depots, 444 sampled walk-node
origins, the config's immobile draw (seed-fixed, 133 of 444). All of that is held.

| axis | values | what it is |
|---|---|---|
| **preparation delay d** (residents) | 0, 30, 60, 90, 120 min | residents leave home at *t = d* instead of 0; the hazard clock does not move. Kept ≤ 120 so that *d* + the 600-min walk budget ≤ the 720-min forecast horizon (beyond the horizon `HazardSequence` clamps to the last surface, a lower bound on risk; that regime is not entered). |
| **responder budget W** | 45, 60, 75, 90, 120 min | `responder_time_budget_min`: the survival-aware vehicle router's time budget from a depot. 75 is the committed value. |
| **corridor closure L** | 0, 1, 2, 3 | cumulative closures of the *L* most-used ingress corridors (§2). |
| dispatch delay D (slice) | 30 (all cells), 60 and 90 at W = 75 | `responder_dispatch_delay_min`: when vehicles leave the depot. Separated from *d* so 「when people leave」 and 「when help leaves」 are not one knob. |

Simulation horizon is **not** an axis: the forecast horizon stays 720 min in every cell.

## 2. Corridor closures, defined before the run

From the baseline cell (d = 0, D = 30, W = 75, L = 0), every home that needs rescue gets
its survival-aware ingress route (`rescuer_reachable`). Drive edges are ranked by the number
of homes whose route uses them. Corridor points are chosen greedily down that ranking as
the midpoints of edges at least **2,000 m** from every corridor point already chosen; the
first three are corridors 1–3. **Closure level L removes every walk and drive edge with an
endpoint within R = 200 m of corridor points 1…L** (a road cut, applied to both networks).
Nothing else changes. A robustness slice repeats L = 1 with R = 300 m.

## 3. What 「served」 means here, and what it does not

Per origin, the pipeline's own four-way class (`FOUR_WAY_CLASSES`), computed with the
pipeline's own helpers at the cell's parameters:

- `already_safe`: mobile, fire-blind shortest walk reaches a refuge without entering the
  hazard, departing at *d*, within 600 min;
- `saved_by_rescue_reachable_refuge`: mobile, only the time-aware walk to a
  *rescue-reachable* refuge does so (refuge reachability = the direct-corridor screen at D);
- `no_safe_pedestrian_route`: needs rescue (immobile, or no safe walk), **and** some depot's
  survival-aware vehicle route reaches the home within W without entering the vehicle cutoff;
- `no_surviving_vehicle_ingress`: needs rescue and no such route exists.

**「Served」 = the first three. It means 「a walk-out exists」 or 「a survival-aware ingress
route exists」. It does NOT mean a completed transport:** the pipeline does not occupy a
vehicle for pickup, loading, egress or unloading, and vehicles are not counted against each
other (`docs/dispatch_ordering.md` records this). So the responder axis reads as *access
feasibility*, never *rescue capacity*. The resident axis reads as *walk feasibility under
the model's own exposure rule*, not survival.

Outcome bookkeeping per cell: the four classes; `unsupported` = origins whose node lies
outside the hazard grid (the sampler returns 0 there, which must not read as safe); the
routers have no timeout — an exhausted search is `no_safe_pedestrian_route`/`no_surviving_vehicle_ingress`
by construction, and that is stated rather than hidden; wall time per cell is recorded.

**No-fire control:** the same grid with a zero hazard field. Whatever remains unserved
there is accessibility (network, budget, closure, immobility), not fire. The
fire-attributable part of a cell is its difference from the control.

**Comparator:** the stated fair opponent (`docs/fair_opponent_line.md`, 의성·안동 budgeted
arm) is a walk-side planner on another region; it is not applicable to a responder-budget
axis and is not re-run here. The walk side's own comparators live in `docs/regrade_three_way.md`.

## 4. Discretisation and support checks, pre-declared

- time step 5 vs 10 min for the time-expanded routers at (d = 60, W = 75, L = 1), all
  classes must agree within the count of origins whose route changes;
- closure radius 200 vs 300 m at L = 1;
- map support: the count of origins and refuge nodes outside the hazard grid; the count of
  depots whose node is cut by a closure (a closure that removes a depot is reported, not
  silently routed around);
- destination selection: refuge counts (all / rescue-reachable) per (L, D), so a boundary
  driven by refuge loss is visible as such.

A boundary is called a property of the scene only if it survives these; otherwise it is
reported as a discretisation or support artifact.

## 4b. Amendment after run 1 (2026-09-13, before run 2)

Run 1 (`data/processed/feasibility_phase_diagram_yeongdeok_run1_endpoint_rule.json`,
figures `docs/figures/phase_diagram_run1_endpoint_rule_*.png`) implemented §2's closure
as 「remove every edge with an **endpoint** within R of the corridor point」. Two things
that rule did that §2 did not intend, both found by reading run 1's own bookkeeping:

- **closure 2 removed nothing**: corridor 2's edge is longer than 2R, so no node lies within
  200 m of its midpoint and the corridor itself survived; L = 2 equalled L = 1 exactly;
- **closure 1 isolated depots 2 and 3** (their only edges lie within 200 m of corridor 1),
  so 「close corridor 1」 was also 「close two fire stations」.

Run 2 changes only the geometric test: an edge is removed if the **segment** passes within R
of a corridor point, so the corridor edge itself is always cut. Everything else in §1–§4
stands. Run 1 is kept as the record; it is not the result to quote. Both runs' outcome
ranges are reported side by side in §5.

## 5. Results

_(appended by `scripts/run_feasibility_phase_diagram.py`; nothing above this line is edited after the run)_

### Run 1 (endpoint rule; superseded by run 2, kept as record)

_Run 2026-09-13T03:38:24Z at `e96471c`; artifact `data/processed/feasibility_phase_diagram_yeongdeok_run1_endpoint_rule.json` (renamed after the run); 444 origins per cell (0 unsupported excluded), 133 immobile; figures `docs/figures/phase_diagram_run1_endpoint_rule_*.png`; 1878 s._

See the artifact for the full tables; unserved ranged 2–9 of 444 across the grid, needs-rescue 134–139, and L = 1 ≡ L = 2 for the reason given in §4b.

### Run 2 (segment-distance closure rule)

_Run 2026-09-13T04:11:49Z at `e96471c`; artifact `data/processed/feasibility_phase_diagram_yeongdeok.json`; 444 origins per cell (0 unsupported excluded), 133 immobile; figures `docs/figures/phase_diagram_*.png`; 1880 s._

Corridors (from baseline ingress usage): 1: edge [7878950980, 12011651425] used by 79 homes; 2: edge [436912482, 5535636106] used by 65 homes; 3: edge [414668537, 436912563] used by 63 homes.
Edges removed per closure: L0_R200 walk 0 / drive 0, L1_R200 walk 26 / drive 9, L2_R200 walk 27 / drive 10, L3_R200 walk 74 / drive 28, L1_R300 walk 38 / drive 11. Depots isolated: {"L0_R200": [], "L1_R200": [2, 3], "L2_R200": [2, 3], "L3_R200": [2, 3], "L1_R300": [2, 3]}.

### Unserved origins (no survival-aware ingress) — rows d, columns W

**closure L = 0**

| d \ W | 45 | 60 | 75 | 90 | 120 | no-fire control (d=0) |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 4 (need 134) | 2 (need 134) | 2 (need 134) | 2 (need 134) | 2 (need 134) | 0/0/0/0/0 |
| 30 | 4 (need 134) | 2 (need 134) | 2 (need 134) | 2 (need 134) | 2 (need 134) | 0/0/0/0/0 |
| 60 | 4 (need 135) | 2 (need 135) | 2 (need 135) | 2 (need 135) | 2 (need 135) | 0/0/0/0/0 |
| 90 | 5 (need 137) | 3 (need 137) | 3 (need 137) | 3 (need 137) | 3 (need 137) | 0/0/0/0/0 |
| 120 | 5 (need 138) | 3 (need 138) | 3 (need 138) | 3 (need 138) | 3 (need 138) | 0/0/0/0/0 |

**closure L = 1**

| d \ W | 45 | 60 | 75 | 90 | 120 | no-fire control (d=0) |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 4 (need 134) | 2 (need 134) | 2 (need 134) | 2 (need 134) | 2 (need 134) | 0/0/0/0/0 |
| 30 | 4 (need 134) | 2 (need 134) | 2 (need 134) | 2 (need 134) | 2 (need 134) | 0/0/0/0/0 |
| 60 | 4 (need 135) | 2 (need 135) | 2 (need 135) | 2 (need 135) | 2 (need 135) | 0/0/0/0/0 |
| 90 | 5 (need 137) | 3 (need 137) | 3 (need 137) | 3 (need 137) | 3 (need 137) | 0/0/0/0/0 |
| 120 | 5 (need 138) | 3 (need 138) | 3 (need 138) | 3 (need 138) | 3 (need 138) | 0/0/0/0/0 |

**closure L = 2**

| d \ W | 45 | 60 | 75 | 90 | 120 | no-fire control (d=0) |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 4 (need 134) | 2 (need 134) | 2 (need 134) | 2 (need 134) | 2 (need 134) | 0/0/0/0/0 |
| 30 | 4 (need 134) | 2 (need 134) | 2 (need 134) | 2 (need 134) | 2 (need 134) | 0/0/0/0/0 |
| 60 | 4 (need 135) | 2 (need 135) | 2 (need 135) | 2 (need 135) | 2 (need 135) | 0/0/0/0/0 |
| 90 | 5 (need 137) | 3 (need 137) | 3 (need 137) | 3 (need 137) | 3 (need 137) | 0/0/0/0/0 |
| 120 | 5 (need 138) | 3 (need 138) | 3 (need 138) | 3 (need 138) | 3 (need 138) | 0/0/0/0/0 |

**closure L = 3**

| d \ W | 45 | 60 | 75 | 90 | 120 | no-fire control (d=0) |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 8 (need 135) | 4 (need 135) | 3 (need 135) | 3 (need 135) | 3 (need 135) | 1/1/1/1/1 |
| 30 | 8 (need 135) | 4 (need 135) | 3 (need 135) | 3 (need 135) | 3 (need 135) | 1/1/1/1/1 |
| 60 | 8 (need 136) | 4 (need 136) | 3 (need 136) | 3 (need 136) | 3 (need 136) | 1/1/1/1/1 |
| 90 | 9 (need 138) | 5 (need 138) | 4 (need 138) | 4 (need 138) | 4 (need 138) | 1/1/1/1/1 |
| 120 | 9 (need 139) | 5 (need 139) | 4 (need 139) | 4 (need 139) | 4 (need 139) | 1/1/1/1/1 |

### Dispatch-delay slice (W = 75, d = 0)

| L | D=30 | D=60 | D=90 |
|---|---:|---:|---:|
| 0 | 2 | 2 | 2 |
| 1 | 2 | 2 | 2 |
| 2 | 2 | 2 | 2 |
| 3 | 3 | 3 | 3 |

### Checks

- time step 5 vs 10 min at (d=60, W=75, L=1): unserved 2 vs 2; needs rescue 135 vs 135.
- cut radius 300 vs 200 m at L=1: unserved 3 vs 2 (d=0), 3 vs 2 (d=60).
- rescue-reachable refuge WALK NODES (distinct; two refuges can share a node) / safe refuges per closure at D=30: L0: 27/50, L1: 17/50, L2: 17/50, L3: 16/50 of 50.
- timeouts: none (the routers have none; budget exhaustion is the infeasible outcome).

## 6. Reading (written after run 2)

- **No phase boundary inside the declared grid.** Unserved (no survival-aware ingress) moves
  from 2 to 9 of 444 over the whole grid (1.6 points of the population); needs-rescue from
  134 to 139. Every cell is within a handful of origins of every other.
- **Why.** The needs-rescue class is the immobile draw (133 of 134 at d = 0): the fire adds at
  most 6 walk-cut origins within 120 min of delay. And for nearly every home that needs a
  vehicle, some depot's survival-aware route reaches it within 45 min, so W ≥ 60 never binds.
  Closure 3 (all three corridors, 74 walk / 28 drive edges) adds one to three unserved; the
  closures also isolate depots 2 and 3, and the outcome still barely moves, because depots 0
  and 1 cover. The dispatch-delay slice (30 / 60 / 90) changes nothing.
- **The control separates the parts.** The no-fire control is 0 unserved (1 under closure 3),
  so the 2–9 unserved are fire-attributable, and the ~440 served are accessibility. What the
  fire adds on this scene is small and separable; what makes the community 「infeasible」 in
  the model is not on any of these three axes.
- **What that means for the definition, not just the scene.** 「Served」 here is access
  feasibility: a survival-aware route exists. The pipeline has no vehicle occupancy, no
  capacity and no completed-transport outcome (`docs/dispatch_ordering.md`), so a resource
  axis *cannot* show a boundary in it; a budget that binds nothing and a fleet that is never
  counted against itself will look feasible. The responder side needs an occupancy and
  capacity model before a resource phase diagram can be a result. That is the honest
  negative finding of this study.
- **Checks.** Time step 5 vs 10 min: identical. Cut radius 300 vs 200 m at L = 1: one more
  unserved (3 vs 2), the same size as the whole closure effect, so the closure axis is at
  the resolution of the cut geometry, not above it. Rescue-reachable refuge walk nodes drop
  27 → 17 → 17 → 16 with closure, without moving the resident classes, because refuges are
  plentiful (50). No timeouts; no unsupported origins.
- **Not shown:** robustness to anything not varied (hazard realisation, map, spotting,
  destination status, assistance demand); rescue capacity; buildings as origins (the 444 are
  sampled walk nodes; the 주건물 population of `docs/building_origins_juso_yeongdeok.md`
  was not run through the responder side).
