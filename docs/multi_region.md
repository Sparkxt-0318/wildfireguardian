# Three regions, one parameter set

**Round-3 PHASE 5 STEP 2-3 and STEP 4. Written 2026-08-02.**
Artifacts: [`multi_region_comparison.json`](../data/processed/multi_region_comparison.json),
`real_roads_real_hazard_{uiseong_andong_2025,uljin_samcheok_2022}.json`.

This comparison is in the **459 series**, which has **three buckets**, so the
quantity in every column below is *the share of scanned origins that reach
safety **only** on the future-aware route* — the fire-blind shortest path enters
the predicted hazard, the future-aware path does not. It is **not** a
cross-region comparison of the walk-failure rate **w**. `w` is an output of the
439 series, that series is bound to a synthetic hazard envelope with a
fabricated coastline, and it therefore cannot be computed for an inland region
at all. Anything below that reads like `w` is not `w`.

---

## 1. The table

Parameters are identical across all three: 60 m slope sampling (canonical),
distance-ranked routing, 600-minute budget, 10-minute time step, stride 18,
`p_cut` 0.5, slope clipped at ±60 %, `osmnx == 2.0.7`. They come from
`config/default.yaml` and no per-region override exists.

| region | origins | both_safe | FA-only | no_safe_route | over budget | **FA-only %** | envelope coverage | road density | node density | envelope area | depots |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 영덕 2025 | 460 | 440 | 17 | 3 | 0 | **3.70 %** | 50.4 % | 1.733 | 9.07 | 6,100 ha | 4 |
| 의성·안동 2025 | 368 | 346 | 13 | 0 | 9 | **3.53 %** | 98.9 % | 2.332 | 7.27 | 2,375 ha | **0** |
| 울진·삼척 2022 | 393 | 376 | 3 | 10 | 4 | **0.76 %** | 84.8 % | 1.601 | 7.90 | 6,575 ha | 4 |

Units: road density km/km², node density nodes/km², envelope area = cells at
p ≥ 0.5 in the final hazard slice × 25 ha. `both_enter`, `naive_unreachable` and
`unclassified` are zero in all three regions and are omitted.

**The Yeongdeok row is quoted, not re-run.** It is
`three_column_comparison.col3_jul24_slope` of
[`real_roads_real_hazard_slope_60.json`](../data/processed/real_roads_real_hazard_slope_60.json),
chosen because it is the arm whose parameters match the two new regions. The
originally committed flat reading — 459 = 438 + 18 + 3 — is carried in the
artifact as `role: context`; the gap between the two (459 vs 460 origins, 18 vs
17 FA-only) is **network drift**, not terrain, and the July-23 network behind
the committed reading is unrecoverable
([`DATA_LOSS_2026-07-24.md`](DATA_LOSS_2026-07-24.md)).

---

## 2. Read the covariates before the metric

The three regions differ on three axes **at the same time**:

| axis | spread | why it moves the metric |
|---|---|---|
| envelope coverage | 50.4 – 98.9 % | Yeongdeok's origins are drawn from the eastern half of its own predicted core; the two new bboxes are ignition-centred ([`walk_bbox_coverage.md`](walk_bbox_coverage.md)) |
| envelope area | 2,375 – 6,575 ha, **2.77×** | a bigger fire has more origins near it |
| node density | 7.27 – 9.07 /km² | the origin scan strides over **nodes** |

With n = 3 and three covariates moving together, no ranking on the FA-only
column is interpretable on its own. Do not produce one.

### The origin count needs two denominators, not one

Uiseong-Andong has the **highest** road-length density and the **lowest** node
density: long straight ways carried by few nodes. A stride-18 scan walks the
node list, so it is sensitive to exactly that difference.

| region | origins | per km of road | per 1,000 walk nodes |
|---|---:|---:|---:|
| 영덕 2025 | 460 | 0.285 | 54.5 |
| 의성·안동 2025 | 368 | **0.172** | 55.1 |
| 울진·삼척 2022 | 393 | 0.266 | 53.8 |

Normalised by **nodes** the three are within 2.4 % of each other — the scan is
doing exactly what it says. Normalised by **road length** Uiseong-Andong yields
40 % fewer origins per kilometre than Yeongdeok. So its origins are the sparser
sample **per kilometre of road**, and its denominator is not comparable to
Yeongdeok's in the way "919 km² vs 931 km²" suggests. Report both columns.

### One definition of envelope area, or none

The area column above is computed for all three regions from the hazard `npz`
that each routing run **actually read**, at p ≥ 0.5, final slice. Under that one
definition the spread is **2.77×**.

A figure of 27,900 ha for Yeongdeok appears in
[`yeongdeok_forward_sim.json`](../data/processed/yeongdeok_forward_sim.json) and
in prose derived from it. It is a different quantity from a different simulation
— its step-0 area is 6,225 ha where the routing field's is 6,025 ha. Combining
it with the two new regions' p ≥ 0.5 areas inflates the apparent spread from
2.77× to about 11.7×. **Use one definition or the other, never one of each.**

---

## 3. Two things the new regions do that Yeongdeok did not

### 3.1 The 600-minute budget binds

`fa_exceeds_budget` — fire-blind route safe, future-aware router cannot finish
in time — is **0 for Yeongdeok at 600 minutes**, and that emptiness is asserted
in `tests/test_partition_categories.py`. It is **9** for Uiseong-Andong and
**4** for Uljin-Samcheok.

So the three-way split no longer accounts for every origin outside Yeongdeok.
The column is in the table above for that reason; dropping it would make
`both_safe + FA-only + no_safe_route` fail to sum to N without saying why.

### 3.2 Slope moves the counts

PHASE 2 found slope changed **nothing** for Yeongdeok: 440 / 17 / 3 flat *and*
slope. That null result does not carry.

| region | arm | both_safe | FA-only | no_safe | over budget |
|---|---|---:|---:|---:|---:|
| 의성·안동 | flat control | 354 | 13 | 0 | 1 |
| 의성·안동 | **slope 60 m** | **346** | **13** | **0** | **9** |
| 울진·삼척 | flat control | 380 | 4 | 9 | 0 |
| 울진·삼척 | **slope 60 m** | **376** | **3** | **10** | **4** |

**It is not because the new regions are steeper.** They are not:

| region | mean \|slope\| | mean walk-time increase | directional asymmetry |
|---|---:|---:|---:|
| 영덕 2025 | 8.18 % | +26.6 % | 20.0 % |
| 의성·안동 2025 | **7.03 %** | **+19.6 %** | 16.2 % |
| 울진·삼척 2022 | 8.18 % | +26.6 % | 19.6 % |

Uljin-Samcheok's terrain statistics are indistinguishable from Yeongdeok's and
Uiseong-Andong's are *gentler*, yet slope moves the counts in both and moved
nothing in Yeongdeok. So the same slope penalty is landing on walks with less
slack.

The flat control arms say the same thing before any terrain is applied:
Uiseong-Andong already has **1** origin over the 600-minute budget with flat
timing, Yeongdeok has **0**. The origins that move are the ones that were
already close to the bound.

What differs between the regions is **refuge density**: 50 refuge POIs in
Yeongdeok (5.37 per 100 km²) against 34 in Uiseong-Andong (3.70) and 26 in
Uljin-Samcheok (2.81). Fewer refuges over a comparable area means longer walks
and less headroom under a fixed budget. That is *consistent with* what the arms
show and is not established by them — three regions cannot separate refuge
density from everything else that differs. It is offered as the reading to test
next, not as the finding.

The effect is a *budget* effect either way: origins move into
`fa_exceeds_budget`, not into the hazard. PHASE 2-C-2 showed failure rising
12.6× as the budget tightens ([`budget_sweep.md`](budget_sweep.md)); here the
budget is fixed and the walk lengthens into it.

Every region's flat control arm is reported beside its slope arm in the
artifact, so this is a measured contrast rather than an inference.

---

## 4. ⚠ Uljin-Samcheok's DEM does not cover its own walk bbox

The SRTM raster `uljin_samcheok_2022_dem.tif` spans 36.85 – 37.45 °N. The walk
bbox starts at **36.81 °N**. The southern 0.04° — about 4.4 km along the whole
width — has **no elevation data**.

| | |
|---|---|
| walk nodes outside the DEM | **405 of 7,300 = 5.55 %** |
| elevation samples reading nodata | 2,189 of 35,492 = 6.2 % |
| undirected edges affected | 504 of 9,132 = 5.5 % |
| **scanned origins in the strip** | **23 of 393** |
| their bucket membership | **all 23 in `both_safe`** |

A sample outside the raster reads nodata, and `build_walk_network` then times
that sub-segment as **flat**. The fallback was silent; it is now counted
(`slope_stats.dem_sampling`) precisely so it cannot be silent again.

**What this does and does not damage.** Part of the Uljin-Samcheok "slope" arm
is a flat arm. But all 23 affected origins land in `both_safe`, so the FA-only
(3) and `no_safe_route` (10) counts — the two the comparison turns on — are not
drawn from the strip. The flat control arm in the same artifact bounds the
effect from the other side.

**Why it was not fixed here.** Fixing it means acquiring new SRTM tiles, and no
other DEM in `data/raw/firms_data/` covers 36.75 – 36.85 °N. Acquisition is a
STEP 2-2 action with its own snapshot and provenance requirements, not something
to slip into an analysis run. It is recorded as an open item instead.

---

## 5. Does the future-aware route help more where the fire actually advances?

The question is live because the Round-2 documents record a limitation: the
459-series result is *dominated by a quasi-static ≥ 0.5 core*. Core growth over
the 12-hour horizon is +1.2 % for Yeongdeok, **+79.2 %** for Uiseong-Andong and
**+155.3 %** for Uljin-Samcheok, so the two new fields are decisively not
quasi-static.

**The answer as posed is no.** The ordering is exactly reversed — Spearman
ρ = −1 between core growth and the FA-only share:

| region | core growth | FA-only % | no_safe_route % |
|---|---:|---:|---:|
| 영덕 2025 | +1.2 % | 3.70 % | 0.65 % |
| 의성·안동 2025 | +79.2 % | 3.53 % | 0.00 % |
| 울진·삼척 2022 | +155.3 % | **0.76 %** | **2.54 %** |

ρ = −1 over three points is an ordering, not a correlation. No p-value exists
for it and none should be inferred.

### The decomposition says why, and it is not "no benefit"

Split the metric. Of the origins whose **fire-blind** route is unsafe
(`FA-only + no_safe_route + both_enter`), how many does the future-aware router
still get to a refuge?

| region | fire-blind route unsafe | future-aware rescues | core growth |
|---|---:|---:|---:|
| 영덕 2025 | 20 / 460 = 4.35 % | 17 → **85.0 %** | +1.2 % |
| 의성·안동 2025 | 13 / 368 = 3.53 % | 13 → **100 %** | +79.2 % |
| 울진·삼척 2022 | 13 / 393 = 3.31 % | 3 → **23.1 %** | +155.3 % |

The share of origins in danger from a fire-blind route is nearly **flat** across
the three (4.35 / 3.53 / 3.31 %). What moves is whether an alternative still
exists. Where the core advances fastest, unsafe origins fall into
`no_safe_route` instead of into the future-aware bucket — the fire overtakes
every route, not just the naive one.

These rates sit on denominators of 13 to 20 origins and therefore move in large
steps. Treat the ordering as the observation; do not quote 100 % as a capability.

### So what does this settle about the Round-2 limitation?

**It does not show that "dominated by a quasi-static core" was a Yeongdeok
peculiarity.** The FA-only share does not rise with core growth, so the obvious
version of that claim is unsupported.

**It does show two things.** First, the method runs unchanged on fields that
advance by +79 % and +155 %, which the Yeongdeok field could not test. Second,
it exposes a failure mode a near-static core structurally cannot produce: a fire
that outruns every available route. That failure mode is worth more than a
confirmation would have been, and it belongs in the limitations section rather
than the results section.

---

## 6. Uiseong-Andong: the responder side is *not applicable*

Uiseong-Andong's ignition-centred 919 km² walk bbox contains **no
`amenity=fire_station` mapped in OpenStreetMap**; the wider 3,926 km² manifest
bbox contains **six**
([`osm_completeness.json`](../data/processed/osm_completeness.json)).

발화점 중심 919 km² 범위 내에 OSM에 매핑된 fire_station이 없으며, 더 넓은
3,926 km² 범위에는 6곳이 있습니다.

**Never write "Uiseong-Andong has no fire stations."** The statement is about
this bbox and about OSM coverage. It is not a statement about the county's fire
service.

The consequence for this comparison is small and must still be stated exactly:
`responder_side_available: false` is recorded for that region, meaning the
responder side **could not be computed**, which is *not applicable* — **never
zero dispatches**. The 459 series is resident-side only for **every** region,
Yeongdeok included: it contrasts a fire-blind walk with a future-aware walk and
never dispatches a vehicle. So the comparison metric is unaffected, and the
artifacts carry `responder_side.computed: false` for all three regions rather
than implying the other two were run differently.

---

## 7. Provenance

| | |
|---|---|
| walk graphs | `data/snapshots/osm-walk_*.graphml.gz`, resolved through `MANIFEST.json`. **`data/cache/` is never read** — it is git-ignored and is how the July-23 graph was lost |
| refuges / depots | `data/snapshots/osm-{shelters,depots}_*.geojson`, byte-identical to the cache copies |
| hazard | `data/processed/hazard_{region}.npz` from STEP 2-1 |
| terrain | `data/raw/firms_data/{region}_dem.tif` (SRTM) |
| Yeongdeok | **quoted from committed artifacts, never re-run.** The runner refuses `--regions yeongdeok_2025` and aborts with exit 4 if any protected Yeongdeok artifact changes byte-for-byte during a run |

Both new regions **reproduce exactly**: re-running
`scripts/run_multi_region_routing.py` into a scratch directory regenerated every
bucket count, every bucket membership list and every slope statistic
identically. Unlike the Yeongdeok 459 series, these regions' networks were never
overwritten.

Structural checks passed per region and are recorded in the artifacts, not just
asserted here: envelope coverage, boundary contact (clear on every slice, max
edge p = 0.000), grid clearance (≥ 5.73 km on every side), walk nodes inside the
hazard grid (0 outside for both regions), and the flat-DiGraph regression
(identical to the undirected control, as it must be when timing is flat).

---

## 8. Rules for quoting anything on this page

1. Never rank the regions on the FA-only column alone.
2. Never carry a number here without its covariates: coverage, envelope area,
   node density.
3. n = 3. Orderings only. Never write "X correlates with Y" from this table.
4. Never call this quantity `w`, and never compare it to a 439-series figure.
5. Never write "Uiseong-Andong has no fire stations." See §6.
6. Never quote Uljin-Samcheok's slope arm without §4.
7. Yeongdeok's numbers here are quotations. They are not a new measurement and
   must not be presented as one.
