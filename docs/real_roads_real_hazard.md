# Real roads + real hazard: closing the last "both synthetic-free" gap

## What this run is

Every earlier routing result in this project was real on **one** axis but synthetic on
the other:

| run | road topology | fire hazard | origins |
|-----|---------------|-------------|---------|
| routing-integration ("407 run") | **synthetic** slope-aware lattice | **real** spread_v2 forward-sim | 407 |
| rescue-routing ("~439 run") | **real** OpenStreetMap walk graph | **synthetic** severity-scaled envelope | ~439 |
| **this run** | **real** OpenStreetMap walk graph | **real** spread_v2 forward-sim | **459** |

This run is the third cell of that table — the one where **both** the streets people would
actually walk **and** the fire that threatens them are real. It closes the project's largest
stated limitation: that road topology and the fire-risk surface were never simultaneously real
(도로 위상과 화재 위험면이 동시에 실제인 검증).

It is **purely additive**: it writes new files only and does not touch, regenerate, or
overwrite any existing committed artifact (`rescue_routing.json`, `rescue_capacity.json`,
`routing_demo.json`, `spread_v2_lofo.json`, etc. are untouched).

## The two real inputs

**Roads (real).** The pedestrian network is downloaded from OpenStreetMap with OSMnx —
`ox.graph_from_bbox(bbox=(129.25, 36.30, 129.55, 36.60), network_type="walk")` over the
Yeongdeok 2025 extent — then reprojected to EPSG:5179 with `ox.project_graph`. That yields
**8,439 nodes / 11,015 edges** of real streets and paths. Refuges are also real OSM points
(`amenity=shelter`/`community_centre`, `leisure=park`): 50 POIs snap to **46 shelter nodes**
on the walk graph. Edge walk-times use the elderly flat speed (0.7 m/s); no terrain slope is
invented, because the OSM nodes carry no DEM.

**Hazard (real).** The threat surface is the real `spread_v2` forward-simulated
ignition-probability field for the held-out Yeongdeok fire, read from
`data/processed/routing_demo.npz` (`haz_stack` shape (5, 181, 147), times
[0, 180, 360, 540, 720] min, EPSG:5179 extent
[1130969.95, 1789870.46, 1204469.95, 1880370.46], 500 m cells). It is wrapped in the same
`HazardSequence` the router already consumes — constructed directly from
`(grid, times_min, surfaces)`, not via `from_forward_sim`, since we have the surfaces, not a
`ForwardSim` object. The router asks it one question, `prob_at(x, y, t_min)`, exactly as before.

Before use we sampled the object at the known routing origin (1153094.95, 1832745.46): it
returns a finite probability in [0, 1] (0.0 at t0), and every one of the 8,439 OSM nodes falls
**inside** the hazard extent (0 outside, 0.0 %), so no clipping or extrapolation was needed.

## How the routing works (plain language)

For each candidate home we compute two walks to safety and compare them:

- **naive** — the fire-blind shortest walk to the nearest refuge (the status quo);
- **future-aware** — the walk that minimises exposure to the *growing* hazard within a
  600-minute budget, allowed to pick a farther but safer refuge.

Each home lands in exactly one of six buckets that **partition** the scanned set (the count
sums are asserted to equal the number of origins, so nothing is silently dropped):
`naive_into_FA_safe`, `no_safe_route`, `both_safe`, `both_enter`, `naive_unreachable`,
`unclassified`. This is the corrected partition classifier from
`scripts/run_routing_integration.py`; the routing functions themselves
(`wildfireguardian.routing.evacuation.naive_route` / `future_aware_route`) are used unchanged.
We keep `p_cut = 0.5` and `time_budget = 600 min` so the method is directly comparable to the
407 run.

## Result

Scanning **459** origins (stride-18 sub-sample of the dense OSM graph, dropping the 10 already
above 0.5 hazard at t0):

| bucket | count |
|--------|------:|
| both_safe | 438 |
| naive_into_FA_safe | 18 |
| no_safe_route | 3 |
| both_enter | 0 |
| naive_unreachable | 0 |
| unclassified | 0 |

The partition holds (438 + 18 + 3 = 459). For **18** real homes the fire-blind route walks
*into* the advancing hazard while a future-aware detour reaches a refuge cleanly; the headline
origin cuts modelled exposure from 36.4 to 1.35 prob·min (−96 %) by walking farther to a
different real refuge. For **3** homes the hazard core overtakes every reachable refuge within
budget — a real, reported "no safe route" outcome, never imputed.

### Why these counts are smaller than the 407 run's — and why that is *good* news

The 407-origin run (real hazard on the **synthetic** 8-connected lattice) split
56 / 88 / 240 (naive_into_FA_safe / no_safe_route / both_safe). This run splits 18 / 3 / 438.
Far fewer origins need future-aware help (18 vs 56) and **far** fewer are trapped (3 vs 88).
That is not the method weakening — it is the real street network being much more evacuable than
the synthetic lattice. On the real OSM graph, connectivity is denser and there are 46 real
refuge nodes, so most homes have a clean route and only a handful are genuinely boxed in. Read
the other way round: **the synthetic 8-connected lattice was pessimistic** about real-world
evacuability. The method's value still shows — on 18 real homes the fire-blind route walks into
the fire while the future-aware route detours cleanly — and the 3 trapped homes remain real,
reported outcomes.

### The partition is *complete* here (a methodological improvement)

438 + 18 + 3 = **459 exactly**, with `naive_unreachable = 0` and `unclassified = 0`: every
scanned origin lands in exactly one bucket, and the run asserts it. The 407 run classified only
56 + 88 + 240 = 384 of its 407 scanned origins — a **23-origin gap**. The six-bucket partition
used here (adding `naive_unreachable` and `unclassified` as explicit sinks) provably accounts
for 100 % of scanned origins and closes that gap. This is a real improvement in the accounting,
independent of the road/hazard sources.

## Honesty: the temporal-resolution caveat (GATE B)

This is a genuine methodological difference, recorded here and in the JSON provenance, not
hidden. The real npz hazard has **5 slices at 180-minute steps**; the synthetic hazard used by
the ~439-origin rescue run has **15 slices at 15-minute steps** — about **12× finer**.
`HazardSequence` interpolates linearly in time, so the run is valid, but the effective time
resolution is much coarser, and the ≥0.5 hazard core is nearly static across the npz frames
(241 → 244 cells over 12 h; what grows is a diffuse sub-0.3 halo, 241 → 262). Consequences:

- results are dominated by the near-static high-probability core rather than by front advance;
- this run is **not** directly comparable to the ~439-origin rescue run on timing-sensitive
  quantities.

So this should be read as the **third cell of the real/synthetic axis table** — a proof that
the whole pipeline runs end-to-end with *both* inputs real — and **not** as a drop-in
replacement for either earlier analysis. Contrasts (naive vs future-aware) remain the robust
result; absolute magnitudes stay illustrative.

## What is still synthetic or assumed here

Being explicit, because "both real" refers to the road topology and the hazard surface — not to
every input:

- **Walk timing has no slope correction.** The OSM walk edges are timed at a **flat** elderly
  speed (0.7 m/s), distance ÷ speed. The other runs build their walk lattice with **Tobler
  slope correction** (`build_evacuation_network`), so uphill/downhill segments cost more or
  less time. The OSM nodes here carry no attached DEM, so no per-node slope is invented — which
  is honest, but it is a genuine methodological difference from the other runs and is disclosed
  as such, not just glossed as "flat speed."
- **Elderly walk speed (0.7 m/s)** is a literature/assumed constant.
- **Origins** are seeded sampled candidates; real per-household elderly-home locations are
  private.

## A self-correction that belongs in the record

An intermediate scratch run reported **21 / 3 / 435**; the reproducible script reports
**18 / 3 / 438**. The cause: the intermediate run round-tripped the OSM graph through GraphML
and **relabeled** node ids to `0..N-1`. Because the stride-18 origin sub-sample is taken over
`sorted(node_ids)`, relabeling changed *which* 459 origins were sampled, shifting three origins
between `naive_into_FA_safe` and `both_safe`; `no_safe_route` (3) and the partition total (459)
were unaffected. The **canonical** figures are the reproducible script's **18 / 3 / 438**,
which samples over the real OSM node ids exactly as the repo's `rescue_demo._scan_origins` does.
`scripts/run_real_roads_real_hazard.py` regenerates them deterministically; the relabeled
`21 / 3 / 435` numbers are superseded.

## Reproduce

```
python scripts/run_real_roads_real_hazard.py
```

Needs network access for the one-time OSMnx download (cached under the configured OSM cache
dir) and the git-ignored `data/processed/routing_demo.npz` present in the working tree. Writes
`data/processed/real_roads_real_hazard.json`. If OSMnx cannot reach the network the script
**stops and reports** rather than falling back to a synthetic lattice.
