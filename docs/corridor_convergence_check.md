# Corridor convergence check — 영덕 2025, deterministic (rules declared before the run)

**Status: rules declared 2026-09-15 before the run; §7 is appended by the run.**
Exploratory diagnostic. New filenames only; no committed artifact is modified, nothing
is registered in `docs/NUMBERS.json`, and nothing here goes on a judge-facing surface
(서식 1, 서식 2, the PPT, the booth material). Whether any result below is ever promoted
to a claimed contribution is a separate decision, to be taken after reading the result,
not before.

## 1. The question this answers, and the one it does not

**Answers:** in the committed 영덕 run, do the evacuation and rescue routes this system
produces *converge* — do many separate households get routed over the same few road
segments, and are any of those shared segments structural chokepoints (articulation
points or bridges) whose loss would cut more than one household off from every refuge or
depot it currently reaches? And of the shared segments, which ones ever sit inside the
fire's own forecast hazard envelope, so that the convergence is a *wildfire* finding
rather than a generic network fact?

**Does not answer:**

- **Whether the roads would actually jam.** Nothing here models capacity, flow,
  headway, queueing or congestion. An edge crossed by 40 households is reported as an
  edge crossed by 40 households, not as an edge that would be blocked. No vehicle count,
  no lane width, no travel-time penalty is computed from the tally, and none of the
  routes in the run were changed by it. Turning a convergence count into a delay needs a
  flow model this repository does not have (§3).
- **Whether real households would follow these routes.** Origins are the committed
  sampled walk-network candidates (stride 18), not households; the router's output is a
  recommendation, not observed behaviour.
- **Anything about the rescue-UNIT supply capacity layer.** `RescueCapacityConfig` /
  `capacity_triage` in `routing/rescue.py` rations *how many crews exist*. This check is
  about *road* convergence and is completely separate from it; that layer is untouched,
  unread and unaffected here.
- **Whether a chokepoint is worth treating.** No cost, no benefit, no intervention. The
  corridor-treatment atlas (`docs/corridor_treatment_atlas.md`) is the place where a
  treatment is evaluated; this document only locates convergence.

## 2. Why this is worth checking at all

Two reasons, one from the literature and one from a fire.

**(a) Road networks under evacuation are flow problems, not shortest-path problems.**
Coclite, Garavello and Piccoli, "Traffic flow on a road network," *SIAM Journal on
Mathematical Analysis* **36**(6), 2005, 1862–1886, set out the conservation-law
formulation for traffic on a network: each road carries a scalar conservation law and
the junctions are coupled by flux conditions, so the network's throughput is set at the
junctions, not along the links. The consequence that matters here is that a network
whose independently-computed routes all pass through one junction can have a throughput
far below the sum of the individual route capacities, and no per-route calculation can
see it. The pointer to this formulation for evacuation specifically came from a
September 2026 email exchange with HK Tan (UCLA, Bertozzi group) about their network-flow
model of the Lahaina evacuation. This repository's routers are per-household shortest /
exposure-minimising path solvers with no shared state (`routing/evacuation.py`,
`routing/rescue.py`), which is exactly the class of method that cannot see it. So the
minimum honest thing to do is to *measure the convergence* and say plainly that the flow
consequence is not modelled.

**(b) Lahaina, 2023.** In the August 2023 Lahaina fire, road closures and downed lines
funneled evacuating traffic onto a small number of routes, and vehicles backed up on a
street that the fire then surrounded; roughly half of the fire's deaths were
concentrated in a single neighbourhood of narrow, partly dead-end streets. Whatever the
final apportionment of cause, the structural shape of the failure — many independently
sensible evacuation decisions converging on one segment that the fire later reached — is
precisely what a per-household router cannot detect and what the tally in §4 and the
hazard test in §5 are built to detect.

Neither (a) nor (b) is evidence that 영덕 has this problem. They are the reason the
question is asked. §7 reports what was actually found, including "nothing", if that is
what came back.

## 3. Base scene and reproduction gate

The run uses the committed canonical 영덕 hazard
(`data/processed/routing_demo_canonical.npz`, the leave-one-fire-out forward simulation)
and the 2026-07-24 OSM snapshots in `data/snapshots/`, materialised exactly as
`scripts/run_rescue_routing_real_hazard.py` materialises them — the same scenario
builder, the same `RescueConfig`, the same origin scan (stride 18).

The raw FIRMS bundle the forward simulation needs is git-ignored and is not present in a
fresh checkout, so the hazard field cannot be re-simulated here. The gate is therefore
on the committed artifacts instead, and is checked **before anything is written**:

1. `routing_demo_canonical.npz` must hash to the SHA-256 recorded in
   `data/processed/rescue_routing_real_hazard.json` (`what_is_real.hazard_sha256`).
2. Re-running the resident and rescuer classification on that scenario must reproduce
   the committed run exactly: `n_origins` and all four `four_way_counts`.

Gate 2 is also the correctness check on this script: the route collection below is a
re-execution of the same calls `rescue_demo.run_pipeline` makes, so if the four-way split
did not come back identical, the routes would not be the pipeline's routes and the run
aborts.

## 4. What is tallied

**Routes collected.** For every origin the run produces, in the same order and with the
same configuration the pipeline uses:

- *resident walk routes* — `resident_policies(...)`, all three policies. The **deployed**
  tally uses policy (c) `future_aware_rescue` for every origin classified
  `already_safe` or `saved_by_rescue_reachable_refuge`, falling back to (a) `naive` for
  an `already_safe` origin whose (c) solve did not reach — that is, the route the system
  would actually hand the resident. The `naive` routes are tallied separately, as the
  status-quo comparison.
- *rescuer drive routes* — for every origin that needs a rescuer (immobile, or walk cut),
  the survival-aware `rescuer_reachable(...)` route depot → home, i.e. the route that
  ends up on the dispatch sheet. Homes with no surviving ingress contribute no route.

**Edge tally.** A route is a node path. For each consecutive node pair the undirected key
`(min(u,v), max(u,v))` is incremented, at most **once per household per edge** (a route
that doubles back over an edge counts once). The rank statistic is therefore the number
of **distinct households** whose route crosses the edge. Walk and drive networks are
tallied separately — they are different graphs with different node numbering — and also
combined by geometry for the figure only.

**Top-N.** N = 25 shared edges per network, by distinct households, ties broken by edge
length descending then node id.

## 5. The wildfire filter

A shared segment that the fire never approaches is a fact about the road network, not a
wildfire finding, and is reported as such but not counted as a result. For each top-N
edge the segment is sampled every 100 m (endpoints included) and, for **every** forecast
time slice, the hazard is read with the same `HazardSequence` sampler (`prob_at_points`, the vectorised form of `prob_at`) the routers
use. An edge is **fire-exposed** if any sample at any slice reaches `p ≥ 0.5` (the
committed resident walk cutoff, `RescueConfig.walk_cutoff`); the earliest such slice is
recorded. `p ≥ 0.7` (the vehicle cutoff) is recorded as well. Only fire-exposed edges are
reported as convergence findings.

The same filter is applied to the structural findings of §6: every articulation point or
bridge that cuts more than one household on the full network is probed the same way (a
node over its incident used-subgraph edges, an edge over itself). A structural chokepoint
the fire never approaches is reported, and reported as *not* a wildfire finding.

## 6. The structural test

Separately from the tally, on the **union-of-used-routes subgraph** of each network (every
node and edge that any collected route traverses this run, undirected), run
`networkx.articulation_points()` and `networkx.bridges()`.

**Every** articulation point and bridge is tested; there is no candidate budget. (One
candidate is cut from the graph once and connected components computed once, so each
household on it costs a dictionary lookup.)

For each articulation point and bridge, the reported quantity is the number of households
whose origin would be disconnected **from every refuge (walk) or depot (drive) it
currently reaches** by its removal. Reported only if that count is **> 1**.

Two graphs are tested, and both numbers are reported, because they answer different
questions:

- **used-subgraph** (declared above): the union of routes is thin, so almost every edge on
  a route with no parallel route is trivially a bridge there. This number over-reports and
  is reported only for completeness.
- **full-network**: the same candidate node/edge removed from the *whole* walk or drive
  network, then a plain connectivity test from the household's origin to its refuge/depot
  set. This is the honest chokepoint test — it says the terrain offers no detour at all,
  not merely that this run did not use one. The full-network number is the headline.

**Cross-check.** The top-N convergence edge list and the full-network chokepoint list are
intersected. Reported either way: an overlap means the two methods agree on the same
segments; a disjoint result means convergence-by-use and structural-necessity are finding
different things, which is itself the answer to "are these the same diagnostic?".

## 7. Result

_Appended by `scripts/run_corridor_convergence_check.py`. Artifact:
`data/processed/corridor_convergence/convergence_yeongdeok.json`._

_Run 2026-09-15T06:12:18Z at `82be349`; artifact `data/processed/corridor_convergence/convergence_yeongdeok.json`; figure `docs/figures/corridor_convergence_yeongdeok.png`; 6.4 min._

**Gate.** Canonical hazard sha256 `81b4e4d159daa7a8…` matches the committed run. Four-way split re-derived on 444 origins as {'saved_by_rescue_reachable_refuge': 29, 'already_safe': 281, 'no_safe_pedestrian_route': 132, 'no_surviving_vehicle_ingress': 2} — identical to the committed `rescue_routing_real_hazard.json`. Routes collected: 306 deployed resident walks, 307 naive walks, 132 rescuer drives (2 homes with no surviving ingress contribute no route).

### 7.0 Headline

- **walk**: convergence is real — the most-used single segment carries **138 of 306** routed households, and **44** articulation points/bridges cut more than one household from every refuge/depot it reaches even with the whole network available. The worst is edge `[11755003786, 11755003792]`, cutting **138** households. **None of them is a wildfire finding**: no full-network chokepoint and none of the top-25 convergence edges ever reaches p ≥ 0.5 at any forecast slice (worst chokepoint peaks at p = 0.0). Under §5 this is checked and ruled out for this fire on this terrain: the convergence exists, the fire does not go there.
- **drive**: convergence is real — the most-used single segment carries **79 of 132** routed households, and **44** articulation points/bridges cut more than one household from every refuge/depot it reaches even with the whole network available. The worst is node `437092394`, cutting **6** households. **None of them is a wildfire finding**: no full-network chokepoint and none of the top-25 convergence edges ever reaches p ≥ 0.5 at any forecast slice (worst chokepoint peaks at p = 0.0092). Under §5 this is checked and ruled out for this fire on this terrain: the convergence exists, the fire does not go there.
- **status quo vs deployed (walk)**: the fire-blind `naive` routes put at most 17 households on one segment and 2 of their top-25 shared segments are fire-exposed ([12032277584, 12048638534] — 17 households, p reaches 0.5633 by 180.0 min, [12048638534, 13418581843] — 17 households, p reaches 0.5633 by 180.0 min); the deployed future-aware routes put up to 138 on one segment and 0 of theirs are fire-exposed. So the router moves households off the shared segments the fire actually reaches and, in doing so, concentrates them harder on shared segments it does not. Both halves of that sentence are counts of routes, not of traffic (§1, §7.4).

### 7.1 Edge convergence

| route set | edges used | edges shared by ≥2 households | most households on one edge | fire-exposed in the top-25 |
|---|---:|---:|---:|---:|
| walk_deployed | 2475 | 1327 | 138 | 0 |
| walk_naive | 2319 | 1072 | 17 | 2 |
| drive_rescuer | 666 | 392 | 79 | 0 |

**walk_deployed — top shared segments that enter the forecast envelope (p ≥ 0.5 at some slice); 0 of 25 shown.**

None. Every one of this set's most-shared segments stays outside the forecast envelope at every slice, so none of them is a wildfire finding (§5).

**walk_naive — top shared segments that enter the forecast envelope (p ≥ 0.5 at some slice); 2 of 25 shown.**

| edge (u, v) | households | length m | max p (any slice) | first min p≥0.5 | first min p≥0.7 |
|---|---:|---:|---:|---:|---:|
| 12032277584–12048638534 | 17 | 438.8 | 0.5633 | 180.0 | — |
| 12048638534–13418581843 | 17 | 321.2 | 0.5633 | 180.0 | — |

**drive_rescuer — top shared segments that enter the forecast envelope (p ≥ 0.5 at some slice); 0 of 25 shown.**

None. Every one of this set's most-shared segments stays outside the forecast envelope at every slice, so none of them is a wildfire finding (§5).

### 7.2 Articulation points and bridges (§6)

| network | used subgraph nodes | edges | articulation points | bridges | tested | cutting >1 household |
|---|---:|---:|---:|---:|---:|---:|
| walk | 2461 | 2475 | 1952 | 2127 | 4079 | 2134 |
| drive | 668 | 666 | 585 | 666 | 1251 | 768 |

**walk network — candidates cutting more than one household.** 44 survive the full-network test (the headline, §6); 2090 more cut >1 household only in the thin union-of-routes subgraph, where a segment with no parallel route is trivially a bridge.

| kind | id | households on it | cut (used subgraph) | cut (full network) | max p any slice | fire-exposed |
|---|---|---:|---:|---:|---:|---|
| edge | [11755003786, 11755003792] | 138 | 138 | 138 | 0.0 | no |
| node | 11755003786 | 138 | 138 | 138 | 0.0006 | no |
| edge | [12000064438, 12000161817] | 7 | 7 | 7 | 0.0 | no |
| edge | [437090984, 7377497628] | 7 | 7 | 7 | 0.0001 | no |
| node | 12000064438 | 7 | 7 | 7 | 0.0 | no |
| node | 12000161817 | 7 | 7 | 7 | 0.0 | no |
| node | 437090984 | 7 | 7 | 7 | 0.0001 | no |
| node | 7377497628 | 7 | 7 | 7 | 0.0001 | no |
| edge | [10281901255, 11685186169] | 4 | 4 | 4 | 0.0 | no |
| edge | [437091036, 11764332604] | 4 | 4 | 4 | 0.0 | no |
| edge | [437091036, 11764332749] | 4 | 4 | 4 | 0.0 | no |
| node | 10281901255 | 4 | 4 | 4 | 0.0 | no |
| node | 11764332604 | 4 | 4 | 4 | 0.0 | no |
| node | 11764332749 | 4 | 4 | 4 | 0.0 | no |
| node | 437091036 | 4 | 4 | 4 | 0.0 | no |
| edge | [11731499564, 11731499565] | 2 | 2 | 2 | 0.0 | no |
| edge | [11731499608, 11731499609] | 2 | 2 | 2 | 0.0 | no |
| edge | [11731499609, 11731499651] | 2 | 2 | 2 | 0.0 | no |
| edge | [11741886897, 11747142975] | 2 | 2 | 2 | 0.0 | no |
| edge | [11741886924, 11747142975] | 2 | 2 | 2 | 0.0 | no |

**drive network — candidates cutting more than one household.** 44 survive the full-network test (the headline, §6); 724 more cut >1 household only in the thin union-of-routes subgraph, where a segment with no parallel route is trivially a bridge.

| kind | id | households on it | cut (used subgraph) | cut (full network) | max p any slice | fire-exposed |
|---|---|---:|---:|---:|---:|---|
| node | 437092394 | 15 | 15 | 6 | 0.0092 | no |
| edge | [437092353, 10002101333] | 6 | 6 | 6 | 0.0001 | no |
| edge | [437092364, 10002101333] | 6 | 6 | 6 | 0.0001 | no |
| edge | [437092364, 12043427209] | 6 | 6 | 6 | 0.0009 | no |
| edge | [437092388, 12043427209] | 6 | 6 | 6 | 0.0091 | no |
| edge | [437092388, 437092394] | 6 | 6 | 6 | 0.0091 | no |
| node | 10002101333 | 6 | 6 | 6 | 0.0001 | no |
| node | 12043427209 | 6 | 6 | 6 | 0.0091 | no |
| node | 437092353 | 6 | 6 | 6 | 0.0001 | no |
| node | 437092364 | 6 | 6 | 6 | 0.0009 | no |
| node | 437092388 | 6 | 6 | 6 | 0.0091 | no |
| edge | [437090983, 5536595856] | 5 | 5 | 5 | 0.0003 | no |
| edge | [437092348, 12116791091] | 5 | 5 | 5 | 0.0 | no |
| edge | [437092348, 437092353] | 5 | 5 | 5 | 0.0 | no |
| node | 12116791091 | 5 | 5 | 5 | 0.0 | no |
| node | 437092348 | 5 | 5 | 5 | 0.0 | no |
| node | 5536595856 | 5 | 5 | 5 | 0.0003 | no |
| node | 437090983 | 5 | 4 | 4 | 0.0009 | no |
| edge | [437261791, 9591760265] | 4 | 4 | 4 | 0.0048 | no |
| node | 9591760265 | 4 | 4 | 4 | 0.0048 | no |

### 7.3 Cross-check: are the two methods finding the same thing? (§6)

- **walk**: 25 top convergence edges vs 19 full-network chokepoint edges and 25 chokepoint nodes. Overlap: edges in both [[11755003786, 11755003792]]; chokepoint nodes lying on a top edge [11755003786]
- **drive**: 25 top convergence edges vs 19 full-network chokepoint edges and 25 chokepoint nodes. No overlap — convergence-by-use and structural necessity are finding different segments in this terrain.

### 7.4 What this does and does not license

Every count above is a count of routes over a segment. It is **not** a delay, a queue, a capacity breach or a congestion estimate; no such quantity is computed anywhere in this run, and no route was changed by it (§1). A segment listed here is a place a flow model *would have to be applied* to say anything about throughput — the Coclite–Garavello–Piccoli junction formulation (§2a) is the class of model that would be needed, and this repository does not contain one. The rescue-UNIT supply capacity layer is a different layer and is unaffected.
