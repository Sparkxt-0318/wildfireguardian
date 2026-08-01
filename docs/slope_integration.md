# DEM slope on OSM walk edges — three axes real at once

**Artifacts:** `data/processed/real_roads_real_hazard_slope_{30,60,90}.json`
**Script:** `scripts/run_real_roads_real_hazard_slope.py`
**Module:** `src/wildfireguardian/routing/slope.py`
**Measured:** 2026-08-01 · config_hash `b97a4d73…`

## What this closes

The committed 459-origin run disclosed its own gap:

> "NO DEM slope correction on the OSM walk edges: edge times use a FLAT elderly
> walk speed."

Real roads, real hazard, flat terrain — in a county spanning −207 m to 1014 m.
This run supplies the third axis: **OSM road topology, the spread_v2
forward-simulated hazard, and SRTM terrain are now all real simultaneously.**

## Headline

> Slope raises walking time substantially — **+28.1 % uphill / +25.1 % downhill**
> across the network at the canonical 60 m sampling, with the longest evacuation
> walk going **283 → 444 minutes** — yet **the 6-bucket classification does not
> move at all**: 440 / 17 / 3 with flat timing and 440 / 17 / 3 with slope, at
> every sampling spacing and with or without clipping.
>
> That is a null result on the counts and a large effect on the times. It is not
> evidence that terrain is unimportant; it is evidence that **this hazard field
> cannot resolve it** (see *Why the counts do not move*).

## The three-column comparison

The committed run's OSM network was overwritten on 2026-07-24 and is
unrecoverable ([`DATA_LOSS_2026-07-24.md`](DATA_LOSS_2026-07-24.md). A
two-column "before slope / after slope" table would attribute network drift to
the slope model, so:

| 항목 | 커밋값 (7-23 망, 평면) | 7-24 망, 평면 | 7-24 망, 경사 (60 m ★) |
|---|---:|---:|---:|
| 두 경로 모두 안전 | 438 | **440** | **440** |
| 미래 인지 경로만 안전 | 18 | **17** | **17** |
| 도달 불가 (no safe route) | 3 | **3** | **3** |
| `n_origins_scanned` | 459 | **460** | **460** |
| 평균 통과 시간 변화 | — | (기준) | **+26.6 %** |

* **Column 1 → 2 isolates network drift.** Quoted, never re-run. +1 origin,
  438 → 440 both-safe, 18 → 17 future-aware-only. Same magnitude as the
  independently measured drift experiment ([`network_drift.md`](network_drift.md)).
* **Column 2 → 3 isolates slope.** Same snapshot graph, osmnx pinned to 2.0.7
  (the version in the snapshot's `created_with`), same hazard, same seed. The
  only difference is edge timing.

## Sampling sensitivity — all three spacings, as required

| 표본 간격 | 두 경로 안전 | 미래 인지만 | 도달 불가 | 평균 \|경사\| | Δt 오르막 | Δt 내리막 | 비대칭 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 30 m | 440 | 17 | 3 | 9.98 % | +41.6 % | +39.2 % | 17.6 % |
| **60 m ★정본** | **440** | **17** | **3** | **8.18 %** | **+28.1 %** | **+25.1 %** | **20.0 %** |
| 90 m | 440 | 17 | 3 | 7.11 % | +22.7 % | +19.3 % | 20.7 % |

**The conclusion is identical at every spacing.** The choice of 60 m therefore
changes the reported *time* statistic by nearly a factor of two but changes no
reported *count*. That is the robustness evidence the three-way sweep was for.

Spacing is still not a free parameter: **never quote a time change without its
spacing.** 60 m is canonical because the SRTM raster is ~25 × 31 m per pixel —
30 m samples at or below one pixel and reads DEM noise as terrain, and 90 m
smooths real relief away.

## Why the counts do not move

Slope is unambiguously applied (29,092 sub-segments at 60 m, mean |slope|
8.18 %, per-direction edge times differing by up to 28.7 %). The classification
is nonetheless unchanged, for three compounding reasons:

1. **`naive_route` minimises DISTANCE, not time.** Its path is slope-invariant
   by construction. Measured: the naive path changed for **0 of 460** origins.
2. **The time budget is never exhausted.** The longest naive walk goes 283 → 444
   minutes against a 600-minute budget. Nobody crosses it.
3. **The hazard is quasi-static.** Five slices at 180-minute steps over 12 hours.
   Shifting an arrival time by tens of minutes rarely changes which slice a node
   is evaluated against. The committed run's own provenance already said results
   are *"dominated by the near-static ≥0.5 core, not front advance"*.

Route-level effect, 460 origins, 60 m:

| | mean | median | max |
|---|---:|---:|---:|
| naive walk time | +18.4 % | +11.6 % | +344.9 % |
| future-aware walk time | +15.9 % | +8.8 % | +828.7 % |

So the terrain signal is real and large at the level of *individual walks*; the
6-bucket partition simply is not the instrument that can see it. **Reporting
"438 → 440 → 440" without this explanation would misrepresent a null instrument
as a null effect.**

⚠ The brief anticipated that unreachability would *rise*. It did not rise and it
did not fall — it is invariant, across six independent arms (3 spacings × clipped
/ unclipped). Reported as measured.

## Direction: why the graph is now a DiGraph

Tobler is asymmetric. Uphill is always slower than downhill at equal |slope|,
and peak speed occurs at −5 % (gentle downhill), not on the flat:

| slope | speed (m/s) |
|---:|---:|
| +0.20 | 0.348 |
| 0.00 | 0.700 |
| **−0.05** | **0.834** (fastest) |
| −0.20 | 0.493 |

Measured on this network at 60 m: mean directional asymmetry **20.0 %** of flat
traversal time, and **56.6 % of edges** differ by more than 10 %. The pipeline
previously routed on an undirected `nx.Graph` (OSM's 22,276 directed edges
collapsed to 11,020), which cannot represent that.

Averaging the two directions was rejected because **residents evacuate outward
and responders drive inward over the same edges**: the average is wrong for both
parties in opposite directions, and the two errors cancel in aggregate — an
invisible failure, which is the exact class this round exists to remove.

### Regression gate

With flat timing, direction carries no information, so the DiGraph conversion
**must** change nothing. It is checked on every run and in the test suite:

```
flat / undirected (col 2)      N= 460  both_safe= 440  FA_only= 17  no_safe=  3
flat / DiGraph  (regression)   N= 460  both_safe= 440  FA_only= 17  no_safe=  3
-> DiGraph regression: PASS (identical)
```

`tests/test_slope_digraph.py` additionally asserts: DiGraph edges == 2 ×
undirected edges; **every** edge has its reverse (all 10,991 checked, not a
sample); flat times are symmetric edge-for-edge; and `length_m` is untouched by
slope.

### The 407-origin run already did something different

`build_evacuation_network` computes `dz = abs(elev[b] - elev[a])`, so every edge
is treated as uphill. Because Tobler's `|S + 0.05|` makes uphill the slower
direction, **the committed 407-origin run already applies the conservative
"slower direction" convention — implicitly, and without recording it.** This run
is direction-aware instead. The two conventions are stated rather than
reconciled; the 407 numbers are not restated here.

## Method

* **Sampling.** Each edge's polyline is resampled at *uniform arc-length*, not
  densified per vertex. Per-vertex densification leaves sub-segments shorter than
  one DEM pixel wherever OSM vertices are dense, and a sub-pixel baseline turns
  DEM noise into slope — measured that way the network's apparent maximum slope
  is **1055 %**. Uniform resampling gives every sub-segment the same baseline.
* **Geometry.** 67.0 % of edges (7,365 of 10,991) carry a `LineString`. OSM omits
  geometry where a way runs straight between its two nodes, so the remaining
  3,626 are interpolated straight — the intended reading, not a fallback. The
  split is recorded in every artifact.
* **Tobler.** `evacuation.elderly_speed_ms` is imported, never reimplemented, so
  slope handling is identical to the 407-origin run. A test asserts the function
  identity.
* **Input.** The walk graph is read from `data/snapshots/`, never `data/cache/`.

## Slope clipping — a defence, not a correction

`pedestrian.max_abs_slope: 0.60` bounds |rise/run| per sub-segment.

**This is a defence against DEM registration error, not a physical correction.**
Where a road crosses a bridge, a tunnel or a cutting, SRTM reports the terrain
surface rather than the roadbed, and the resulting "slope" is an artefact of
comparing a road position against a hillside elevation. Clipping bounds the
artefact; it does not make the value right.

Runs were done **with and without** clipping, as required:

| | clipped at 60 % | unclipped |
|---|---:|---:|
| counts (all spacings) | 440 / 17 / 3 | 440 / 17 / 3 |
| max reported \|slope\| | 60.0 % | 309.0 % |
| Δt forward, 60 m | +28.12 % | +28.12 % |
| clipped sub-segments, 60 m | 165 of 29,092 (0.567 %), on 106 edges | 0 |

**Clipping changes the reported slope statistic and nothing else — by
construction.** `elderly_speed_ms` has a floor (`_MIN_SPEED_MS = 0.15 m/s`) that
saturates at |slope| ≈ 44 % uphill and ≈ 54 % downhill. The 60 % clip sits above
both, so every clipped sub-segment was *already* pinned to the floor. The clip
therefore cannot alter traversal time.

That makes the clip honest but nearly inert. A clip below ~44 % would change
results; anyone lowering it must re-report. Worst raw slopes (all clipped to one
sub-segment each):

| edge | raw max \|slope\| | EPSG:5179 |
|---|---:|---|
| 11768368384→11768368391 | 309.0 % | 1174842, 1836287 |
| 11769621073→11769621226 | 152.7 % | 1167887, 1839648 |
| 12014304372→12014304373 | 144.9 % | 1168860, 1818136 |
| 11001087902→11001088348 | 137.9 % | 1158506, 1815087 |
| 12022819431→12022829577 | 128.0 % | 1172197, 1842149 |

## Edges most slowed by slope (60 m, top 5 of 10 in the artifact)

| rank | flat | uphill | Δ | downhill |
|---:|---:|---:|---:|---:|
| 1 | 15585 s | 25780 s | +10195 s (+65.4 %) | 24076 s |
| 2 | 12748 s | 20357 s | +7610 s (+59.7 %) | 19263 s |
| 3 | 3311 s | 9050 s | +5739 s (+173.4 %) | 8294 s |
| 4 | 8987 s | 13810 s | +4823 s (+53.7 %) | 12942 s |
| 5 | 2012 s | 6102 s | +4090 s (+203.3 %) | 4771 s |

## Reporting rules

* Quote the counts only as **440 / 17 / 3 on the 2026-07-24 network**. They are
  not the committed 438 / 18 / 3 and do not supersede them — the committed run's
  network no longer exists.
* Never quote a slope time-change without its sampling spacing.
* Do not write "slope had no effect". Write: slope raises walk times ~26 % but
  does not move this classification, because the classification is
  distance-ranked, budget-slack and quasi-static-hazard limited.
* Registered in [`NUMBERS.json`](NUMBERS.json) as `slope_*`, separate from the
  committed entries.

## What would make the counts move

A hazard with real front advance on the routing clock. The current field is 5
slices at 180-minute steps (~12× coarser than the rescue run's 15-minute
stepping), which is the stated Gate-B limitation of the committed run. Re-running
this comparison against a finer forward simulation is the obvious next
experiment; it is not done here.
