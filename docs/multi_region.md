# Three regions, one parameter set

**Round-3 PHASE 5 STEP 2-3 and STEP 4. Written 2026-08-02, REVISED the same day
after the DEM re-acquisition.**
Artifacts: [`multi_region_comparison.json`](../data/processed/multi_region_comparison.json),
`real_roads_real_hazard_{uiseong_andong_2025,uljin_samcheok_2022}.json`.

> ⚠ **Every number on this page changed on 2026-08-02.** The first version was
> computed on hazard fields derived from a defective DEM: Uljin-Samcheok's
> raster filled the East Sea with a ramp down to −497 m, and that region sits in
> the shared leave-one-out training set for every other fire
> ([`dem_defect_2026-08-02.md`](dem_defect_2026-08-02.md)). After re-acquisition
> Uiseong-Andong's future-aware-only share moved from 3.53 % to **24.73 %**.
> **Do not cite the earlier figures.** The before/after tables are in §4.

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
| 의성·안동 2025 | 368 | 263 | 91 | 12 | 2 | **24.73 %** | 99.2 % | 2.332 | 7.27 | 3,275 ha | **0** |
| 울진·삼척 2022 | 393 | 377 | 3 | 10 | 3 | **0.76 %** | 81.5 % | 1.601 | 7.90 | 7,300 ha | 4 |

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
| envelope coverage | 50.4 – 99.2 % | Yeongdeok's origins are drawn from the eastern half of its own predicted core; the two new bboxes are ignition-centred ([`walk_bbox_coverage.md`](walk_bbox_coverage.md)) |
| envelope area | 3,275 – 7,300 ha, **2.23×** | a bigger fire has more origins near it |
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
definition the spread is **2.23×**.

A figure of 27,900 ha for Yeongdeok appears in
[`yeongdeok_forward_sim.json`](../data/processed/yeongdeok_forward_sim.json) and
in prose derived from it. It is a different quantity from a different simulation
— its step-0 area is 6,225 ha where the routing field's is 6,025 ha. Combining
it with the two new regions' p ≥ 0.5 areas inflates the apparent spread from
2.23× to about 8.5×. **Use one definition or the other, never one of each.**

---

## 3. Two things the new regions do that Yeongdeok did not

### 3.1 The 600-minute budget binds

`fa_exceeds_budget` — fire-blind route safe, future-aware router cannot finish
in time — is **0 for Yeongdeok at 600 minutes**, and that emptiness is asserted
in `tests/test_partition_categories.py`. It is **2** for Uiseong-Andong and
**3** for Uljin-Samcheok.

So the three-way split no longer accounts for every origin outside Yeongdeok.
The column is in the table above for that reason; dropping it would make
`both_safe + FA-only + no_safe_route` fail to sum to N without saying why.

### 3.2 Slope moves the counts

PHASE 2 found slope changed **nothing** for Yeongdeok: 440 / 17 / 3 flat *and*
slope. That null result does not carry.

| region | arm | both_safe | FA-only | no_safe | over budget |
|---|---|---:|---:|---:|---:|
| 의성·안동 | flat control | 266 | 96 | 6 | 0 |
| 의성·안동 | **slope 60 m** | **263** | **91** | **12** | **2** |
| 울진·삼척 | flat control | 380 | 4 | 9 | 0 |
| 울진·삼척 | **slope 60 m** | **377** | **3** | **10** | **3** |

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
budget pressure: 50 refuge POIs in Yeongdeok (5.37 per 100 km²) against 34 in
Uiseong-Andong (3.70) and 26 in Uljin-Samcheok (2.81). Fewer refuges over a
comparable area means longer walks and less headroom under a fixed budget. That
is *consistent with* what the arms show and is not established by them — three
regions cannot separate refuge density from everything else that differs. It is
the reading to test next, not the finding.

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

---

## 5. Does the future-aware route help more where the fire actually advances?

The question is live because the Round-2 documents record a limitation: the
459-series result is *dominated by a quasi-static ≥ 0.5 core*. Core growth over
the 12-hour horizon is +1.2 % for Yeongdeok, **+147.2 %** for Uiseong-Andong and
**+183.5 %** for Uljin-Samcheok, so the two new fields are decisively not
quasi-static.

> ⚠ The pre-fix version of this section reported that the hypothesis was
> refuted, on the strength of a near-flat fire-blind-risk column
> (4.35 / 3.53 / 3.31 %). That column was an artifact of the contaminated
> hazard field. It now reads **4.35 / 27.99 / 3.31 %** and the refutation does
> not stand either. Neither does its opposite.

| region | core growth | FA-only % | no_safe_route % | fire-blind route unsafe | future-aware rescues |
|---|---:|---:|---:|---:|---:|
| 영덕 2025 | +1.2 % | 3.70 % | 0.65 % | 20 / 460 = 4.35 % | **85.0 %** |
| 의성·안동 2025 | +147.2 % | **24.73 %** | 3.26 % | 103 / 368 = **27.99 %** | **88.3 %** |
| 울진·삼척 2022 | +183.5 % | 0.76 % | 2.54 % | 13 / 393 = 3.31 % | **23.1 %** |

**At n = 3 nothing orders cleanly.** Spearman ρ between core growth and the
FA-only share is −0.5; against the rescue rate it is also −0.5. Two of three
regions support the hypothesis strongly and the third contradicts it strongly.
No ordering statement is available and none should be made.

### What can be said

**Uiseong-Andong is the strongest evidence the project has that the method
matters.** A fast-advancing core (+147 %) inside a walk bbox that covers 99.2 %
of it produces a fire-blind route that is unsafe for **28 % of origins**, and
the future-aware router still reaches a refuge for **88 %** of those. Yeongdeok,
whose core barely moves, produces 4.35 % and 85 %. That is the contrast the
Yeongdeok-only result could not show, and it is a **result**, not a limitation.

**Uljin-Samcheok is the strongest evidence of the method's ceiling.** Its core
advances fastest of the three, yet only 3.31 % of origins have an unsafe
fire-blind route and the future-aware router rescues only **23 %** of those.
Where it cannot help, it is because the fire overtakes every walking route, not
because the naive route was already fine.

**What separates them is not core growth.** Candidate covariates that do differ:
envelope coverage (99.2 % vs 81.5 %), refuge density (3.70 vs 2.81 per 100 km²),
and the geometry of the fire relative to the road network — Uljin-Samcheok's
fire runs along a coastal corridor with the sea on one side, which removes half
the escape directions. None of these is separable at n = 3.

### So what does this settle about the Round-2 limitation?

The "quasi-static core" limitation was **real and consequential**: on a field
that actually advances, the same method and the same parameters produce a
future-aware-only share nearly **seven times** Yeongdeok's. Yeongdeok understated
the method's benefit.

It does **not** follow that the benefit rises with fire speed. Uljin-Samcheok
advances faster still and shows the smallest benefit of the three. Both
statements are in the artifact; neither is a trend.

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
| hazard | `data/processed/hazard_{region}.npz`, **re-simulated 2026-08-02** on the corrected DEMs |
| terrain | `data/raw/firms_data/{region}_dem.tif` — **re-acquired 2026-08-02**, OpenTopography SRTMGL1, snapshotted as `srtm-dem_*.tif` (bytes stored, not digest-only) |
| Yeongdeok | **quoted from committed artifacts, never re-run.** Its DEM was NOT re-acquired; the runner refuses `--regions yeongdeok_2025` and aborts with exit 4 if any protected Yeongdeok artifact changes byte-for-byte during a run |

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
   when the DEM was corrected; Uiseong-Andong's headline moved sevenfold. The
   superseded values survive only in §4's before/after tables, labelled
   "before".
8. **Never claim the benefit rises with fire speed.** Uiseong-Andong (+147 %
   core growth) shows the largest benefit and Uljin-Samcheok (+183 %) the
   smallest. §5.
