# Three regions, one parameter set

**Round-3 PHASE 5 STEP 2-3 and STEP 4. Written 2026-08-02, REVISED the same day
after the DEM re-acquisition.**
Artifacts: [`multi_region_comparison.json`](../data/processed/multi_region_comparison.json),
`real_roads_real_hazard_{uiseong_andong_2025,uljin_samcheok_2022}.json`.

> ⚠ **This page has been recomputed twice on 2026-08-02, and every number
> changed both times.** First the DEMs were corrected — Uljin-Samcheok's raster
> filled the East Sea with a ramp to −497 m and that region trains every other
> fire's model ([`dem_defect_2026-08-02.md`](dem_defect_2026-08-02.md)), which
> moved Uiseong-Andong from 3.53 % to **24.73 %**. Then the Yeongdeok row was
> moved off `routing_demo.npz`, which the investigation identified as the
> surviving output of a run reverted on 2026-07-21
> ([`routing_demo_divergence.json`](../data/processed/routing_demo_divergence.json)),
> onto the canonical field — which moved Yeongdeok from 3.70 % to **9.17 %** and
> its core growth from +1.2 % to **+316.1 %**.
> **Do not cite any earlier figure from this page.** Superseded values survive
> only in the labelled before/after tables in §4 and §5.

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
| 영덕 2025 | 458 | 414 | 42 | 2 | 0 | **9.17 %** | 32.6 % | 1.803 | 9.43 | 25,900 ha | 4 |
| 의성·안동 2025 | 368 | 263 | 91 | 12 | 2 | **24.73 %** | 99.2 % | 2.390 | 7.45 | 3,275 ha | **0** |
| 울진·삼척 2022 | 393 | 377 | 3 | 10 | 3 | **0.76 %** | 81.5 % | 1.663 | 8.21 | 7,300 ha | 4 |

Units: road density km/km², node density nodes/km², envelope area = cells at
p ≥ 0.5 in the final hazard slice × 25 ha. `both_enter`, `naive_unreachable` and
`unclassified` are zero in all three regions and are omitted.

> ⚠ **영덕 절대 비율에 대한 단서** — 영덕 수치는 정본 화재 핵심의 **32.6 %만
> 덮는** 보행망에서 산출되었습니다. 나머지 3분의 2에 있는 출발지들의 거동은
> 측정되지 않았으며, 편향의 방향도 알려져 있지 않습니다. 지역 간 비교에서 영덕
> 행을 인용할 때는 이 열을 반드시 함께 제시하십시오.
> ([`walk_bbox_coverage.md`](walk_bbox_coverage.md) · 재취득하지 않기로 2026-08-02
> 확정) **짝지어진 대비는 영향받지 않습니다** — 두 arm이 같은 출발지를 쓰므로
> 표본 프레임이 상쇄됩니다.

**The Yeongdeok row is now the canonical-hazard run**, not a quotation. Until
2026-08-02 it quoted `real_roads_real_hazard_slope_60.json` col 3 (460 origins,
440 / 17 / 3). That arm consumed `routing_demo.npz`, which the investigation
identified as the output of a 2026-07-20 run reverted the next day — a field
whose own validation figures are HARD-forbidden retired values. The table now
uses [`real_roads_real_hazard_canonical.json`](../data/processed/real_roads_real_hazard_canonical.json),
run on the **same** 2026-07-24 snapshot network with the **same** parameters, so
440 / 17 / 3 → 414 / 42 / 2 is attributable to the hazard field alone.

Two superseded Yeongdeok readings are carried in the artifact as
`role: context`: that slope-60 arm, and the originally committed
459 = 438 + 18 + 3, whose 2026-07-23 network is also unrecoverable
([`DATA_LOSS_2026-07-24.md`](DATA_LOSS_2026-07-24.md)) and which therefore
differs from the primary row in **two** variables, not one.

**Every region in this table now runs on a hazard field built from the same
canonical dataset (151,904 rows / 2,989 positives) and the same corrected
DEMs.** Before this revision the table mixed two freshly simulated regions with
a Yeongdeok row from a reverted run, and was not a comparison at all.

---

## 2. Read the covariates before the metric

The three regions differ on three axes **at the same time**:

| axis | spread | why it moves the metric |
|---|---|---|
| envelope coverage | **32.6 – 99.2 %** | Yeongdeok's walk bbox now covers barely a third of its own predicted core — the core quadrupled and the bbox did not ([`walk_bbox_coverage.md`](walk_bbox_coverage.md)) |
| envelope area | 3,275 – 25,900 ha, **7.91×** | a bigger fire has more origins near it |
| node density | 7.45 – 9.43 /km² | the origin scan strides over **nodes** |

With n = 3 and three covariates moving together, no ranking on the FA-only
column is interpretable on its own. Do not produce one.

### The origin count needs two denominators, not one

Uiseong-Andong has the **highest** road-length density and the **lowest** node
density: long straight ways carried by few nodes. A stride-18 scan walks the
node list, so it is sensitive to exactly that difference.

| region | origins | per km of road | per 1,000 walk nodes |
|---|---:|---:|---:|
| 영덕 2025 | 458 | 0.284 | 54.3 |
| 의성·안동 2025 | 368 | **0.172** | 55.1 |
| 울진·삼척 2022 | 393 | 0.266 | 53.8 |

Normalised by **nodes** the three are within 2.4 % of each other — the scan is
doing exactly what it says. Normalised by **road length** Uiseong-Andong yields
40 % fewer origins per kilometre than Yeongdeok. So its origins are the sparser
sample **per kilometre of road**, and its denominator is not comparable to
Yeongdeok's in the way "896 km² vs 895 km²" suggests. Report both columns.

### ⚠ Two bbox areas are in circulation, and the operational text still carries the old one

Recorded 2026-08-03 (PHASE 13). `bbox_area_km2` used to project the four bbox
corners into EPSG:5179 and return the area of their axis-aligned bounding
RECTANGLE — strictly larger than the projected quadrilateral, and undefined
outside Korea at all. It is now geodesic on the WGS84 ellipsoid, and
`osm_completeness.json`, `multi_region_comparison.json` and the fifteen new
`mr_*` registry entries all carry the corrected values.

**The operator-facing text was deliberately NOT updated, and this is the record
of that decision.**

| quantity | planar (in the operational text) | geodesic (in the artifacts) | difference |
|---|---:|---:|---:|
| Uiseong-Andong walk bbox | **919 km²** | **896.5 km²** | 2.5 % |
| Uiseong-Andong manifest bbox | **3,926 km²** | **3,828.8 km²** | 2.5 % |

Those two figures appear in `live/pipeline.py`'s `status_ko`, in
`run_multi_region_routing.py`, in the mandated wording at
`docs/HANDOFF_ROUND3.md` §5 rule 11, and on every operator screen and A4 sheet
for that region. They are the stated basis of the **"no `amenity=fire_station`
is mapped in OSM inside this bbox"** statement.

⚠ **The zero-fire-station conclusion does not depend on which area is used.** It
is a count of features inside a bbox, and the bbox itself did not move — only the
number reported for its area. The statement remains valid verbatim, on either
figure. Changing the printed area would require re-confirming the whole
statement, its §5 rule and the tests that pin its phrasing, for a 2.5 % cosmetic
correction to a number that is not load-bearing for the claim. **Updating the
operational text is therefore a separate piece of work, deliberately deferred.**

Until it is done: quote the geodesic figure when citing the artifact, quote the
printed figure when quoting an operator sheet, and never present the two as a
discrepancy in the underlying data — they are one bbox measured two ways.

### One definition of envelope area, or none

The area column above is computed for all three regions from the hazard `npz`
that each routing run **actually read**, at p ≥ 0.5, final slice. Under that one
definition the spread is **7.91×**.

The long-standing conflict with the 27,900 ha figure in
[`yeongdeok_forward_sim.json`](../data/processed/yeongdeok_forward_sim.json) has
largely dissolved. That file was never the odd one out: it belongs to the
canonical lineage, and the canonical routing field agrees with it — step-0 area
**6,225 ha in both**, final 25,900 ha against its 27,900 ha (7.7 % apart, the
residue of a re-fitted model and a widened canvas). What disagreed was
`routing_demo.npz` (6,025 → 6,100 ha), the reverted run's field, which is no
longer in this table.

---

## 3. Two things that do not carry over from the committed run

### 3.1 The 600-minute budget binds

`fa_exceeds_budget` — fire-blind route safe, future-aware router cannot finish
in time — is **0 for Yeongdeok at 600 minutes**, asserted in
`tests/test_partition_categories.py`, and it stays 0 on the canonical field. It
is **2** for Uiseong-Andong and **3** for Uljin-Samcheok.

So the three-way split no longer accounts for every origin outside Yeongdeok.
The column is in the table above for that reason; dropping it would make
`both_safe + FA-only + no_safe_route` fail to sum to N without saying why.

### 3.2 Slope moves the counts

PHASE 2 found slope changed **nothing** for Yeongdeok: 440 / 17 / 3 flat *and*
slope. That null result was obtained on the reverted run's near-static field and
does not survive it.

| region | arm | both_safe | FA-only | no_safe | over budget |
|---|---|---:|---:|---:|---:|
| 영덕 (reverted field, committed) | flat / slope | 440 / 440 | 17 / 17 | 3 / 3 | 0 / 0 |
| 영덕 | flat control | 415 | 41 | 2 | 0 |
| 영덕 | **slope 60 m** | **414** | **42** | **2** | **0** |
| 의성·안동 | flat control | 266 | 96 | 6 | 0 |
| 의성·안동 | **slope 60 m** | **263** | **91** | **12** | **2** |
| 울진·삼척 | flat control | 380 | 4 | 9 | 0 |
| 울진·삼척 | **slope 60 m** | **377** | **3** | **10** | **3** |

On the canonical field slope moves one Yeongdeok origin out of `both_safe` into
FA-only. One origin is not a result, but it is not zero either, and the
committed null was exactly zero. **The 30 / 60 / 90 m slope experiments have NOT
been re-run on the canonical field**; until they are, `slope_integration.md`'s
null result should be read as a property of the reverted field.

**It is not because the new regions are steeper.** They are not:

| region | mean \|slope\| | mean walk-time increase | directional asymmetry |
|---|---:|---:|---:|
| 영덕 2025 | 8.18 % | +26.6 % | 20.0 % |
| 의성·안동 2025 | **6.36 %** | **+15.1 %** | 17.0 % |
| 울진·삼척 2022 | 8.06 % | +23.7 % | 21.2 % |

Uiseong-Andong is the *gentlest* of the three and Uljin-Samcheok is close to
Yeongdeok, yet slope moves the counts in both and moved nothing in Yeongdeok.
The same slope penalty is landing on walks with less slack.

Unlike the pre-fix reading, slope now moves origins in **both** directions: in
Uiseong-Andong it pushes 5 out of FA-only and 6 into `no_safe_route`, and in
Uljin-Samcheok 1 out of FA-only and 1 into `no_safe_route`. Slower walking means
the fire reaches more of the network before the walker clears it, so terrain no
longer costs only budget — it costs reachable safety.

**Refuge density** remains the covariate most likely to explain the residual
budget pressure: 50 refuge POIs in Yeongdeok (5.58 per 100 km²) against 34 in
Uiseong-Andong (3.79) and 26 in Uljin-Samcheok (2.92). Fewer refuges over a
comparable area means longer walks and less headroom under a fixed budget. That
is *consistent with* what the arms show and is not established by them — three
regions cannot separate refuge density from everything else that differs. It is
the reading to test next, not the finding.

### ⚠ What the "shelter" layer actually contains

Recorded 2026-08-03 (PHASE 13 STEP 2). This is a **finding about the data, not a
defect**, and the tag set is deliberately unchanged — it is the set the committed
Yeongdeok numbers were produced with, and changing it would break the
identical-rule design. But the layer does not mean what its name suggests, and
every use of "refuge density" on this page has to be read with that in mind.

Split by tag, from the committed `shelters.geojson` snapshots:

| region | `amenity=shelter` | `amenity=community_centre` | `leisure=park` | total |
|---|---:|---:|---:|---:|
| Yeongdeok 2025 | 17 | **0** | 33 | 50 |
| Uiseong-Andong 2025 | 10 | 15 | 9 | 34 |
| Uljin-Samcheok 2022 | 7 | **0** | 19 | 26 |

Two things follow, and neither is what the column name implies.

**① It is mostly parks.** `leisure=park` is 66 % of Yeongdeok's layer and 73 % of
Uljin-Samcheok's. `amenity=community_centre` — the tag that would actually denote
a 마을회관, a building people can shelter *in* — returns **zero** in two of the
three regions. Only Uiseong-Andong has any, and there it is the largest limb.

**② The `amenity=shelter` features are 정자, not refuges.** Every one that carries
a `shelter_type` is a non-refuge type: Yeongdeok 16 of 17 `gazebo`, Uiseong-Andong
10 of 10 `gazebo`, Uljin-Samcheok 6 `gazebo` + 1 `lean_to`. These are village
pavilions and roadside rain shelters. They are real gathering points in rural
Korea and their coordinates are real, but `amenity=shelter` in OSM means a roofed
structure, not an evacuation destination.

There is no downstream filtering: `read_poi_snapshot` in
`scripts/run_multi_region_routing.py` turns **every** feature in the file into a
`Destination(kind="shelter")` with no check on `shelter_type`, capacity or
building type, and `live/pipeline.py` feeds those straight to the router as
`net.shelters`.

**What this costs the comparison.** A cross-region "refuge density" contrast is
substantially a contrast in **park-polygon mapping convention**, not in refuge
supply. That cuts in both directions and must be stated whenever the column is
used: it weakens any claim that a low-density region is short of refuges, and it
weakens any claim that a high-density one is adequately served. The routing
result itself is unaffected — the destinations are real coordinates that a walker
can reach — but the *interpretation* of the density covariate is not the one the
name invites.

This matters most for any future cross-country comparison, where the same
measurement would be comparing two countries' park-mapping habits.

Every region's flat control arm is reported beside its slope arm in the
artifact, so this is a measured contrast rather than an inference.

---

## 4. The DEM defect — found, fixed, and it moved the results

The first version of this page reported that Uljin-Samcheok's DEM stopped
4.4 km north of its own walk bbox, that 405 of 7,300 walk nodes were being timed
flat, and that the effect on the reported buckets was bounded because all 23
affected origins were `both_safe`. All of that was true. It was also the smaller
half of the problem.

Re-acquiring the raster (`scripts/acquire_region_dem.py`, OpenTopography
SRTMGL1, 2026-08-02) revealed that the old Uljin-Samcheok file **filled the East
Sea with a linear ramp down to −497 m** — 49 % of the raster carried a negative
elevation — while agreeing with the fresh product **exactly over land**. Forensics
in [`dem_defect_2026-08-02.md`](dem_defect_2026-08-02.md).

Because `run_forward_sim_region.py` trains leave-one-fire-out on **one shared
feature dataset**, Uljin-Samcheok's fictitious sea slope was training data for
every other fire's model. That, not its own terrain, is why fixing it moved
Uiseong-Andong.

### 4.1 Before and after — inputs

| region | | nodata samples | walk nodes outside DEM | sim-grid cells mean-filled | envelope area | cells ≥ 0.5 per slice | coverage |
|---|---|---:|---:|---:|---:|---|---:|
| 의성·안동 | before | 0.002 % | 0 | **10.03 %** | 2,375 ha | 53, 63, 71, 86, 95 | 98.9 % |
| 의성·안동 | **after** | **0.000 %** | **0** | **0.00 %** | **3,275 ha** | **53, 80, 101, 121, 131** | **99.2 %** |
| 울진·삼척 | before | **6.168 %** | **405** | **15.58 %** | 6,575 ha | 103, 149, 199, 249, 263 | 84.8 % |
| 울진·삼척 | **after** | **0.000 %** | **0** | **0.00 %** | **7,300 ha** | **103, 150, 211, 274, 292** | **81.5 %** |

Uljin-Samcheok's coverage *fell* (84.8 → 81.5 %) because its predicted envelope
grew past the walk bbox, not because the bbox changed. Both regions still clear
the 5 km grid-clearance requirement on every side, and the boundary guard is
clear on every slice.

### 4.2 Before and after — routing

| region | | origins | both_safe | FA-only | no_safe | over budget | FA-only % |
|---|---|---:|---:|---:|---:|---:|---:|
| 의성·안동 | before | 368 | 346 | 13 | 0 | 9 | 3.53 % |
| 의성·안동 | **after** | 368 | **263** | **91** | **12** | **2** | **24.73 %** |
| 울진·삼척 | before | 393 | 376 | 3 | 10 | 4 | 0.76 % |
| 울진·삼척 | **after** | 393 | **377** | **3** | **10** | **3** | **0.76 %** |

**The counts changed, so that is the result** — but not where the symptom was.

* **Uljin-Samcheok**, the region with the visible defect (405 flat-timed nodes,
  6.17 % nodata), moved by **one origin**: `both_safe` 376 → 377, over-budget
  4 → 3. FA-only and `no_safe_route` are identical. Its roads are inland, so the
  ramp-filled sea and the missing southern strip were never where people walk.
  For this region the earlier bound held and "no material effect" is confirmed.
* **Uiseong-Andong**, which had *no* walk-network defect at all — zero nodes
  outside its DEM, 0.002 % nodata — moved by a factor of **seven**. Its hazard
  field changed because the model that produced it was trained on the corrupted
  region.

The lesson is in that inversion. The bound reported earlier was computed on the
layer where the defect was visible, and the damage was on a layer where it was
not. A per-region DEM check cannot catch a shared-training-set contamination;
only re-running with a clean input can.

### 4.3 The guard that now exists

`config/default.yaml`:

```yaml
dem:
  nodata_warn_fraction: 0.01
  nodata_stop_fraction: 0.05
```

The routing run measures the fraction of edge elevation samples that read
nodata; above the stop threshold it **exits 5 and writes nothing**.
`--acknowledge-dem-gap` overrides it and *records* the override in the artifact
(`dem_adequacy.acknowledged_via_flag`) rather than suppressing it. Both regions
now pass at 0.000 % with no flag.

This catches the coverage failure. It does **not** catch the content failure —
a ramp-filled sea is fully-populated data. The rule that catches that one is in
[`dem_defect_2026-08-02.md`](dem_defect_2026-08-02.md) §5: a coastal DEM whose
minimum is a large negative number is reporting a void fill, not bathymetry.

### 4.4 Yeongdeok's envelope coverage collapsed to 32.6 %

A consequence of moving the Yeongdeok row onto the canonical field, recorded
here because it changes how §5's Yeongdeok numbers must be read.

| | committed (reverted field) | canonical |
|---|---:|---:|
| core cells at p ≥ 0.5, final slice | 244 | **1,036** |
| of those, inside the walk bbox | 123 | **338** |
| **coverage** | **50.4 %** | **32.6 %** |

The walk bbox did not move. The core quadrupled, and the bbox now misses two
thirds of it. So the 44 origins whose fire-blind route is unsafe are drawn from
a third of the predicted fire, and the direction of that bias is still
unmeasured ([`walk_bbox_coverage.md`](walk_bbox_coverage.md), which now leads
with 32.6 % and retains the superseded 50.4 % as a labelled historical record).

Re-drawing Yeongdeok's walk bbox around the canonical envelope would fix the
coverage but break continuity with every committed 439- and 459-series figure.
**Decided and closed 2026-08-03: it is not re-drawn.** The bbox and the
simulation canvas are coupled, so re-drawing means re-simulating and re-running
canonical steps 1–3; the price of not doing so is exactly one thing — absolute
rates carry a caveat — and every paired contrast stays valid, because both arms
share the origins. `HANDOFF_ROUND3.md` §2-A is the decision record.

---

## 5. Does the future-aware route help more where the fire actually advances?

**The question has lost its premise.** It was asked because Yeongdeok's core
looked quasi-static (+1.2 % over 12 h) while the two new regions advanced. On
the canonical field Yeongdeok's core advances **fastest of the three**. There is
no static region left to contrast against.

| region | core growth | FA-only % | no_safe_route % | fire-blind route unsafe | future-aware rescues |
|---|---:|---:|---:|---:|---:|
| 영덕 2025 | **+316.1 %** | 9.17 % | 0.44 % | 44 / 458 = 9.61 % | **95.5 %** |
| 의성·안동 2025 | +147.2 % | **24.73 %** | 3.26 % | 103 / 368 = **27.99 %** | 88.3 % |
| 울진·삼척 2022 | +183.5 % | 0.76 % | 2.54 % | 13 / 393 = 3.31 % | **23.1 %** |

All three fires advance by 147–316 %, and their future-aware-only shares span
**32×** with no ordering that tracks growth.

> ⚠ **영덕 절대 비율에 대한 단서** — 영덕 수치는 정본 화재 핵심의 **32.6 %만
> 덮는** 보행망에서 산출되었습니다. 나머지 3분의 2에 있는 출발지들의 거동은
> 측정되지 않았으며, 편향의 방향도 알려져 있지 않습니다. 지역 간 비교에서 영덕
> 행을 인용할 때는 이 열을 반드시 함께 제시하십시오.
> ([`walk_bbox_coverage.md`](walk_bbox_coverage.md) · 재취득하지 않기로 2026-08-02
> 확정) **짝지어진 대비는 영향받지 않습니다** — 두 arm이 같은 출발지를 쓰므로
> 표본 프레임이 상쇄됩니다.

### The rank statistic is not usable here, and we can now show why

Spearman ρ between core growth and the FA-only share has been computed three
times today, on inputs that changed drastically each time:

| recomputation | core growth | FA-only % | ρ |
|---|---|---|---:|
| (a) pre-DEM-fix | 1.2 / 79.2 / 155.3 | 3.70 / 3.53 / 0.76 | **−1.0** |
| (b) corrected DEMs, Yeongdeok on the reverted field | 1.2 / 147.2 / 183.5 | 3.70 / 24.73 / 0.76 | **−0.5** |
| (c) corrected DEMs, Yeongdeok canonical — this table | **316.1** / 147.2 / 183.5 | **9.17** / 24.73 / 0.76 | **−0.5** |

Between (b) and (c) Yeongdeok went from the slowest-advancing region to the
fastest — a complete reversal of its rank — and ρ did not move. At n = 3 there
are six possible orderings and ρ can therefore take only four values
(±1, ±0.5). It has almost no resolution, and it did not track a change that
inverted the data. **Do not report a trend from it in either direction.** That
instability is the finding about the statistic, not about the fires.

### What survives

**The "quasi-static core" limitation was a property of the reverted field, not
of the Yeongdeok fire.** The Round-2 documents describe the 459-series result as
dominated by a near-static ≥ 0.5 core; on the canonical field that same fire's
core quadruples. The limitation as written does not describe the canonical
Yeongdeok field at all.

**The method's benefit varies 32× across three regions whose cores all advance.**
Whatever governs it, fire speed is not sufficient to explain it. The covariates
that do differ are envelope coverage (32.6 / 99.2 / 81.5 %), refuge density
(5.58 / 3.79 / 2.92 per 100 km²) and the fire's geometry relative to the road
network — Uljin-Samcheok's runs along a coastal corridor with the sea on one
side, which removes half the escape directions. **n = 3 separates none of them.**

**Uljin-Samcheok remains the ceiling case.** Only 3.31 % of its origins have an
unsafe fire-blind route, and the future-aware router rescues 23.1 % of those —
the lowest by a wide margin. Where it cannot help, the fire has overtaken every
walking route, not merely the naive one.

**Yeongdeok's rescue rate is now the highest (95.5 %)**, on the largest
denominator it has ever had (44 origins). Read it against its coverage: those 44
origins are drawn from a walk bbox covering **a third** of the predicted core,
so the sample they represent is the most spatially biased of the three (§4.4).

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
| hazard | `hazard_{region}.npz` for the two new regions and `routing_demo_canonical.npz` for Yeongdeok — all **re-simulated 2026-08-02** on the corrected DEMs from the canonical 151,904-row dataset |
| terrain | `data/raw/firms_data/{region}_dem.tif` — **re-acquired 2026-08-02**, OpenTopography SRTMGL1, snapshotted as `srtm-dem_*.tif` (bytes stored, not digest-only) |
| Yeongdeok | **re-run on the canonical field** by `scripts/run_yeongdeok_canonical_routing.py`, which imports the origin rule and the classifier from the committed slope runner so they cannot drift. Its DEM was NOT re-acquired. `routing_demo.npz`, `real_roads_real_hazard.json` and `real_roads_real_hazard_slope_60.json` are digest-checked before and after every run and are unchanged |

Both new regions **reproduce exactly**: re-running
`scripts/run_multi_region_routing.py` into a scratch directory regenerated every
bucket count, every bucket membership list and every slope statistic
identically. Unlike the Yeongdeok 459 series, these regions' networks were never
overwritten.

Structural checks passed per region and are recorded in the artifacts, not just
asserted here: envelope coverage, boundary contact (clear on every slice, max
edge p = 0.000), grid clearance (≥ 5.73 km on every side), walk nodes inside the
hazard grid (0 outside for both regions), **DEM adequacy (0.000 % nodata, no
acknowledgement flag)**, and the flat-DiGraph regression (identical to the
undirected control, as it must be when timing is flat).

⚠ `make snapshot-verify` reports **DRIFTED** for the two replaced DEMs against
their old digest-only `firms-bundle` records, and exits 0. That is correct: the
old digest describes the raster that used to be at that path, the new
`srtm-dem_*` snapshot describes the one that is there now, and both records are
true of their own moment. A silent "ok" would have been the bug.

---

## 8. Rules for quoting anything on this page

1. Never rank the regions on the FA-only column alone.
2. Never carry a number here without its covariates: coverage, envelope area,
   node density.
3. n = 3. Orderings only. Never write "X correlates with Y" from this table.
4. Never call this quantity `w`, and never compare it to a 439-series figure.
5. Never write "Uiseong-Andong has no fire stations." See §6.
6. Yeongdeok's numbers here are quotations. They are not a new measurement and
   must not be presented as one.
7. **Never cite a pre-2026-08-02 figure from this page.** Every number moved
   twice: once when the DEMs were corrected, once when Yeongdeok moved off the
   reverted run's hazard field. Superseded values survive only in the labelled
   before/after tables in §4 and §5.
8. **Never claim the benefit rises or falls with fire speed.** All three cores
   advance by 147–316 % and the benefit spans 32× with no matching ordering.
   §5.
9. **Never quote Spearman ρ from this table as a trend.** At n = 3 it takes one
   of four values and it did not move when Yeongdeok's rank inverted. §5.
10. **Never repeat "the core is quasi-static (241 → 244)".** That is a property
    of the reverted 2026-07-20 field, not of the Yeongdeok fire; on the
    canonical field the same fire's core quadruples.
11. **The PHASE-2 slope null result and the PHASE-2-C objective and budget
    sweeps have NOT been re-run on the canonical field.** Do not present them
    beside this table as though they had.
