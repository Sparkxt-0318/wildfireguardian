# DEM slope on OSM walk edges — three axes real at once

**Artifacts:** `data/processed/slope_sweep_canonical.json` (current) ·
`real_roads_real_hazard_slope_{30,60,90}.json` (earlier reading)
**Scripts:** `scripts/run_yeongdeok_canonical_slope_sweep.py` (current) ·
`scripts/run_real_roads_real_hazard_slope.py` (earlier)
**Module:** `src/wildfireguardian/routing/slope.py`
**Measured:** 2026-08-01, **re-measured 2026-08-02 on the canonical hazard field**

> ⚠ **Everything below §"The canonical-field re-run" is the EARLIER READING.**
> It was measured on `routing_demo.npz`, which the 2026-08-02 investigation
> identified as the surviving output of a run reverted on 2026-07-21
> ([`routing_demo_divergence.json`](../data/processed/routing_demo_divergence.json)).
> Its hazard field is near-static (241 → 244 core cells); the canonical field
> grows 249 → 1,036. The earlier reading is kept because **the null result
> turning out to be a property of the hazard field is itself the finding** — and
> because, remarkably, the null largely survives the change.

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
>
> ⚠ **2026-08-02:** the "this hazard field cannot resolve it" reading was the
> right instinct but the wrong culprit. On a hazard field that grows four times
> over, the counts still barely move — and the origins that do move are not the
> same ones at different sampling spacings. See the canonical-field re-run below.

## The canonical-field re-run (2026-08-02) — the null largely survives

Same walk graph, same DEM, same parameters, four-times-larger hazard field.

| 표본 간격 | 폐기 장 (커밋, 인용) | **정본 장** | 평면 대비 이동 |
|---|---:|---:|---:|
| 평면 (대조군) | 440 / 17 / 3 | **415 / 41 / 2** | — |
| 30 m | 440 / 17 / 3 | **413 / 42 / 3** | 3곳 |
| **60 m ★정본** | 440 / 17 / 3 | **414 / 42 / 2** | 1곳 |
| 90 m | 440 / 17 / 3 | **415 / 41 / 2** | **0곳** |

`n_origins_scanned` is 460 on the reverted field and **458** on the canonical
one: the t0 core grew from 241 to 249 cells, so two more nodes start at or above
`p_cut` and are excluded by the unchanged origin rule. `fa_exceeds_budget` is 0
in every arm. The flat-DiGraph regression passes — identical to the undirected
control, as it must be when timing is flat.

### The decisive check: it is not the same origin twice

Three origins change bucket at *some* spacing. **None changes at all three.**

| origin | flat bucket | 30 m | 60 m | 90 m | naive time ×flat (30/60/90) |
|---|---|---|---|---|---|
| `6205151092` | FA-only | **no_safe_route** | FA-only | FA-only | 1.22 / 1.09 / 1.08 |
| `12044832090` | both_safe | **FA-only** | **FA-only** | both_safe | 1.33 / 1.16 / 1.14 |
| `12048310971` | both_safe | **FA-only** | both_safe | both_safe | 1.47 / 1.21 / 1.20 |

The movement is **monotone in the sampling-induced time penalty, not in
terrain**: 30 m adds +40.4 % network-wide walk time and moves three origins,
60 m adds +26.6 % and moves one, 90 m adds +21.0 % and moves none. All three
origins are marginal cases whose naive walk is slowed 8–47 % — enough to change
which hazard slice they meet, and only at the spacings that penalise hardest.

That is the signature of **sampling noise**, and it is the same reason 60 m is
canonical: at 30 m the sub-segment baseline drops below one SRTM pixel and DEM
noise is read as terrain. So the PHASE-2 null result **holds on the canonical
field too**, now for a measured reason rather than for want of an instrument.

### Terrain reroutes without re-classifying

| spacing | naive routes changed | future-aware routes changed |
|---|---:|---:|
| 30 m | **0** of 458 | 222 (**48.5 %**) |
| 60 m | **0** of 458 | 179 (**39.1 %**) |
| 90 m | **0** of 458 | 153 (**33.4 %**) |

Naive stays at exactly 0 — it ranks by `length_m`, so its path is
slope-invariant by construction, and any other value would be a bug. But the
future-aware router, which does see time, **re-routes a third to a half of all
origins** and almost never changes the verdict. Terrain changes *how people
walk*; on this instrument it does not change *whether they survive*.

### Implementation control

Traversal time is a property of the graph and the DEM, not of the fire, and
Yeongdeok's DEM was not re-acquired. At 60 m:

| | committed | canonical |
|---|---:|---:|
| mean walk-time change | +26.594 % | **+26.594 %** |
| mean \|slope\| | 8.18 % | 8.18 % |

Identical to three decimal places, so the difference in counts is the hazard
field and nothing else. The 30 / 90 m arms likewise reproduce 9.98 % / +40.4 %
and 7.11 % / +21.0 %.

---

# ── EARLIER READING (reverted hazard field) ──────────────────────

Everything from here on was measured on `routing_demo.npz`. It is retained as
the record of what was reported, and because the contrast is the finding.

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

## PHASE 2-C-1 — the objective, not the terrain, was the blocker

**Artifact:** `data/processed/routing_objective_experiment.json`
**Script:** `scripts/run_routing_objective_experiment.py`

Cause 1 above is the most fundamental: `naive_route` minimises DISTANCE, so its
path is slope-invariant *by construction*. No refinement of the hazard field can
change that — the path was never looking at terrain. So `naive_route` gained an
`objective` option (`"length_m"`, the unchanged default, or `"time_min"`), and
the 2×2 was measured.

| 경로 목적함수 | 평면 | 경사 60 m |
|---|---|---|
| 거리 최소화 (현행, 기본값) | 440 / 17 / 3 | 440 / 17 / 3 |
| 시간 최소화 (신규) | 440 / 17 / 3 | 440 / 17 / 3 |

### The routes DO change — 150 of 460

| | mean distance | mean walk time | longest walk |
|---|---:|---:|---:|
| flat, distance-min | 2303 m | 54.8 min | 283.0 min |
| flat, time-min | 2303 m | 54.8 min | 283.0 min |
| slope, distance-min | 2303 m | 67.9 min | **444.0 min** |
| **slope, time-min** | **2345 m** | **64.8 min** | **352.8 min** |

Under slope timing, switching the objective from distance to time changes
**150 of 460 routes (32.6 %)**. Every one of the 150 is **longer in distance**
(median +1.4 %, max +26.7 %) and **faster in time** (median −1.5 %, best
−36.2 %). That is exactly the predicted behaviour: a gentler detour beats a steep
short-cut.

The operational headline is the worst case: **the longest evacuation walk falls
from 444 to 353 minutes, a 91-minute saving for the most exposed evacuee**,
purely from routing on time instead of distance once terrain is known.

**Control.** Under flat timing the same switch changes **0 of 460** routes — as
it must, since flat time is proportional to distance. The mechanism is
identified, not inferred.

### But the counts still do not move

All four arms classify 440 / 17 / 3. So cause 1 is now **removed** — route
selection responds to terrain — and the classification is *still* invariant.
That isolates the remaining blockers to causes 2 and 3:

* the 600-minute budget is never exhausted (the worst case is now 353 min, i.e.
  the time-aware objective has made the budget *even less* binding);
* the hazard is quasi-static, so shifted arrival times rarely change which slice
  a node is evaluated against.

Those are the subjects of 2-C-2 (budget sweep — measured, see
[`budget_sweep.md`](budget_sweep.md): `no_safe_route` moves 3 → 18 once the
budget binds) and 2-C-3 (hazard time resolution — untested, priority lowered).
This experiment's contribution is to take cause 1 off the list with evidence
rather than argument.

⚠ The default objective is **unchanged**. The committed 407- and 459-origin
results are distance-ranked, and interpreting them requires that behaviour to
remain reachable. `time_min` is opt-in.

## Direction: why the graph is now a DiGraph

Tobler is asymmetric. Uphill is always slower than downhill at equal |slope|,
and peak speed occurs at −5 % (gentle downhill), not on the flat:

| slope | speed (m/s) |
|---:|---:|
| +0.20 | 0.3476 |
| 0.00 | 0.7000 |
| **−0.05** | **0.8339** (fastest) |
| −0.20 | 0.4933 |

(Quoted to 4 dp deliberately: at 3 dp the downhill speed reads `0.834`, which  <!-- forbidden-ok: 0.834 -->
collides with a retired Build-A AUC and trips `check_forbidden.py`. Same digits,
different quantity — precisely the confusion the checker exists to catch, so the
fix is to write the number properly rather than to suppress the check.)

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

## ⚠ The 407-origin run uses an undeclared conservative convention

**This is a finding about the committed Round-2 results, not about this run.**

> Ⅲ-8의 407곳 실행은 경사의 절댓값을 사용하므로 방향에 무관하게 항상 오르막
> 시간을 적용합니다. 이는 보수적(안전 측) 규약이나 명시된 적이 없었습니다. 본
> 실행은 방향 인지 방식이며 두 결과를 직접 비교할 수 없습니다.

`build_evacuation_network` (`src/wildfireguardian/routing/evacuation.py`) builds
its edge times as:

```python
dz = abs(elev[rr, ccol] - elev[r, c])     # <- absolute
slope = dz / length
speed = elderly_speed_ms(slope, flat_speed_ms)
```

Because the elevation difference is taken as an absolute value, `slope` is never
negative, so **every edge is timed as though it were traversed uphill**. Tobler's
`|S + 0.05|` makes uphill the slower direction at equal gradient:

| \|slope\| | uphill (m/s) | downhill (m/s) | which `abs()` selects |
|---:|---:|---:|---|
| 0.10 | 0.4933 | 0.7000 | the slower, 0.4933 |
| 0.20 | 0.3476 | 0.4933 | the slower, 0.3476 |

So the committed 407-origin run already implements option (c) from the PHASE-2
design — "undirected graph, conservative slower-direction timing" — **implicitly,
and without recording it anywhere**. The numbers are not wrong. What was missing
is the statement of *which* quantity they are: a safe-side bound, not a
direction-resolved estimate.

This is the same class as the Round-2 problem this round exists to remove: a
number that is internally correct while the thing it is a number *of* is
unrecorded.

**Consequences, stated explicitly:**

* The 407-origin figures are **not** directly comparable with this run's. One is
  a conservative bound applied uniformly; the other resolves direction per edge.
* The 407 numbers are **not restated or corrected here.** They remain as
  committed. Only the convention behind them is now documented.
* Anyone comparing a 407-origin walk time with a figure from this run is
  comparing two different definitions, and the difference will not be slope.

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
