# RESULTS: published heat methods on the Gyeongbuk 2025 replay and the finals fires

Protocol: PROTOCOL.md (frozen at `aac1b282`, amendments A1-A7; A7 of 2026-11-20 changes the spread rate of cells burning at issue, see "A7" below). Method: METHOD.md. Every number is a model output;
none is a field measurement of heat at a road.

## In short

* **The safe distance is smaller than one 375 m cell almost everywhere.** At 7 kW/m2 it is below 375 m in every
  burned cell of all four reconstructed fires (10,955 + 1,937 + 153 + 80 cells, every fuel level; largest 320 m) and in
  every road cell the replay front reaches (7,644 cell-hours; median 25 m, 90th percentile 104 m, max 255 m). At
  2.5 kW/m2 it exceeds 375 m only in crown-fire cells (9 % of Uiseong cells; 0.2 % of replay front cells).
* So the heat term mostly changes **when** a road closes, by minutes: the lead d*/R is a median 2.4 min (90 %: 5.6
  min) at 4.7 kW/m2 on the replay. Its lateral reach rarely passes into the next cell.
* **On leave-by times it changes about as much as the old law, for a different reason.** Replay, 4.7 kW/m2: 337 of
  1,134 place-hours with a leave-now window move (median 3.7 min earlier, max 28 min) and 12 lose the window; the old
  law moves 350 (7 lost). The new and the old law disagree on 344: the new one is later in 174, earlier (or loses the
  window) in 170. Most of the shift
  in both comes from the 375 m cell rule (the front is placed at a neighbouring cell's near edge), not from radiation
  physics.
* **The finals packets (1 h): the artefact is mostly removed by A7, not entirely.** Before A7, 22 of 425 place-inputs lost
  their leave-now window under the new method at 4.7 kW/m2 (old law: 0), all from known-fire cells whose flat arrival
  field took the 150 m/min cap. After A7 (flat known-fire cells take the spread rate of the nearest real-gradient
  cells) **2 of 425 are lost** (1 at 7, 2 at 2.5) and 4 times change (was 24). **12 of the 20 recovered windows come
  from inputs in which no cell has a real gradient, so those cells get no flame at all (the rule's fallback), not from a
  rescaled flame**; 8 come from the donor rule. On the replay (panel A) A7 changes **3 of 1,134 leave-by times at 7
  kW/m2 and none at 4.7 or 2.5**: there the nearest real-gradient cells are themselves at the cap (41 % of the cells).
  See "A7" below for both tables.
* **Uncertainty**: over flame temperature 1090-1400 K, fuel low-high and four view factors the safe distance of a
  crown-fire cell spans 60-301 m (baseline 133 m), a surface-fire cell 7-29 m (12 m). Flame temperature matters most.
* **Checks**: Butler and Cohen's 4 H rule reproduced at 3.5 H (their 20 m front; Zárate et al. 3.8 H; Rossi et al.'s
  8 L for long fronts at 8.3 L); never below FDS (19-115x above its 1 m-cell radiometers; 1.2-1.7x a resolved propane
  burner); ICFME crown flames within a factor 1.7. The gate passed and the method is the road layer's `--heat`
  option, **left off by default** (section "Road layer").

## A7: cells burning at issue, before and after (2026-11-20)

PROTOCOL.md A7 (written before the rerun; the earlier results had been seen). **Problem:** a cell inside the known fire
at issue (arrival 0) has a flat arrival field, so section 3 gave it the 150 m/min cap and a ~50 m crown flame.
**Rule (one, no residence time):** such a cell takes the median spread rate of the 3 nearest cells with a real arrival
gradient (kcf_radiation/ros.py `rate_of_spread_with_source`); with no such cell in the input it gets no flame. The
burned-out-after-a-residence-time alternative was rejected because the age of the burn is not in the inputs (packets:
`known_burned` = "burned with unknown age"; replay rasters: 0 for every disc cell). Everything else is unchanged.

**Reproduction check (stated in advance).** The data folder "wildfire 3 (1)" and the environment rasters were not
reachable (DATA.md), so the rerun reads fuel group, wind and RH per road cell from the committed per-road-cell tables and
recovers air temperature from the recorded d*. Run with the old rule, the same script reproduces every main row of the
table below that was in RESULTS.md (panel A: 7,471 / 7,512 / 7,532 road cells, 330 / 337 / 342 times changed, 12 / 12 /
14 lost; panel B: 414 / 439 / 626 unreached cells, 24 / 24 / 28 changed, 22 / 22 / 25 lost; old law rows identical) and
the spread rate of every road cell (0 mismatches). The temperature fit leaves a d* residual above 0.05 m on 1,880 of
27,759 panel A and 36 of 3,422 panel B road-cell rows; this did not change any count of the old rows.

Old rule → new rule, same columns as "The table" (settings rows: see below):

**Panel A, Gyeongbuk replay** (1134 place-inputs with a leave-now window). Old rule = flat known-fire cells at the 150 m/min cap; new rule = nearest real-gradient spread rate (A7). Same columns as RESULTS.md.

| heat rule | road cells closed earlier (old → new) | unreached cells partly closed (old → new) | leave-by times changed (old → new) | windows lost (old → new) | shift median/max, min (old → new) | vs old law (old → new) |
|---|---|---|---|---|---|---|
| old law, 7 | 7644 → 7644 | 156 → 156 | 349 → 349 | 5 → 5 | 2.1/20.3 → 2.1/20.3 | - → - |
| old law, 4.7 | 7644 → 7644 | 166 → 166 | 350 → 350 | 7 → 7 | 3.1/27.9 → 3.1/27.9 | - → - |
| old law, 2.5 | 7644 → 7644 | 173 → 173 | 352 → 352 | 19 → 19 | 5.9/72.5 → 5.9/72.5 | - → - |
| baseline, 7 | 7471 → 7471 | 145 → 145 | 330 → 330 | 12 → 9 | 2.7/26.8 → 2.7/26.8 | 347 (165 later) → 347 (168 later) |
| baseline, 4.7 | 7512 → 7512 | 155 → 155 | 337 → 337 | 12 → 12 | 3.7/28.1 → 3.7/28.1 | 344 (174 later) → 344 (174 later) |
| baseline, 2.5 | 7532 → 7532 | 175 → 175 | 342 → 342 | 14 → 14 | 6.5/42.3 → 6.5/42.3 | 334 (163 later) → 334 (163 later) |

**Panel B, 15 finals packets** (425 place-inputs with a leave-now window). Old rule = flat known-fire cells at the 150 m/min cap; new rule = nearest real-gradient spread rate (A7). Same columns as RESULTS.md.

| heat rule | road cells closed earlier (old → new) | unreached cells partly closed (old → new) | leave-by times changed (old → new) | windows lost (old → new) | shift median/max, min (old → new) | vs old law (old → new) |
|---|---|---|---|---|---|---|
| old law, 7 | 20 → 20 | 326 → 326 | 2 → 2 | 0 → 0 | 2.2/2.2 → 2.2/2.2 | - → - |
| old law, 4.7 | 20 → 20 | 331 → 331 | 2 → 2 | 0 → 0 | 3.2/3.2 → 3.2/3.2 | - → - |
| old law, 2.5 | 20 → 20 | 347 → 347 | 3 → 3 | 1 → 1 | 6.0/6.0 → 6.0/6.0 | - → - |
| baseline, 7 | 20 → 20 | 414 → 276 | 24 → 3 | 22 → 1 | 1.4/2.2 → 1.4/2.2 | 24 (1 later) → 3 (1 later) |
| baseline, 4.7 | 20 → 20 | 439 → 279 | 24 → 4 | 22 → 2 | 1.9/3.2 → 1.9/3.2 | 24 (1 later) → 4 (1 later) |
| baseline, 2.5 | 20 → 20 | 626 → 313 | 28 → 5 | 25 → 2 | 5.7/22.2 → 5.7/22.2 | 27 (2 later) → 4 (2 later) |

What the fix did to the spread rate of road cells inside the known fire (cell-hours; `data/panels_a7/A7_fix_log.json`):

| panel | known-fire road cell-hours | flat gradient, rate from donors | no donor: no flame | rate of donor cells median (10-90 %) m/min | donor rate at the 150 cap | crown |
|---|---:|---:|---:|---|---:|---:|
| A | 20,115 | 19,422 | 0 | 138 (82-150) | 7,874 (41 %) | 10,251 |
| B | 3,402 | 2,601 | 787 (6 of 15 packets: Hongseong ×3, Miryang ×2, Yeongdeok 26 Mar 17:00 KST) | 13.7 (10.9-80.9) | 60 | 1,428 |

Every leave-by time that differs between the rules at the three thresholds (67 in all; the whole list with seconds is
`data/panels_a7/A7_leave_by_changes.csv`). "no window → X s" = the old rule left no leave-now window, the new rule
leaves a window ending X s after issue. All 67 are windows recovered by the fix; none got later or earlier:

| panel | region | issue (KST) | place | id | 7 kW/m2 old → new | 4.7 old → new | 2.5 old → new |
|---|---|---|---|---|---|---|---|
| A | uiseong_andong_2025 | 25 Mar 12:00 |  | osm:way/1372113459 | no window → 411 s | same | same |
| A | uiseong_andong_2025 | 25 Mar 13:00 |  | osm:way/1372113459 | no window → 411 s | same | same |
| A | uiseong_andong_2025 | 25 Mar 14:00 |  | osm:way/1372113459 | no window → 415 s | same | same |
| B | hongseong_2023 | 02 Apr 16:00 | 상황리 | osm:node/415159033 | no window → 2952 s | no window → 2952 s | no window → 2952 s |
| B | hongseong_2023 | 02 Apr 16:00 | 거차리 | osm:node/415159034 | no window → 2996 s | no window → 2996 s | no window → 2996 s |
| B | hongseong_2023 | 02 Apr 23:00 | 상황리 | osm:node/415159033 | no window → 2952 s | no window → 2952 s | no window → 2952 s |
| B | hongseong_2023 | 02 Apr 23:00 | 거차리 | osm:node/415159034 | no window → 2996 s | no window → 2996 s | no window → 2996 s |
| B | hongseong_2023 | 03 Apr 08:00 | 상황리 | osm:node/415159033 | no window → 2952 s | no window → 2952 s | no window → 2952 s |
| B | hongseong_2023 | 03 Apr 08:00 | 거차리 | osm:node/415159034 | no window → 2996 s | no window → 2996 s | no window → 2996 s |
| B | miryang_2022 | 01 Jun 11:00 | 무연리 | osm:node/415150771 | no window → 3207 s | no window → 3207 s | no window → 3207 s |
| B | miryang_2022 | 01 Jun 11:00 | 춘화리 | osm:node/415150789 | no window → 3239 s | no window → 3239 s | no window → 3239 s |
| B | miryang_2022 | 01 Jun 11:00 | 용지리 | osm:node/415150790 | same | same | no window → 3317 s |
| B | miryang_2022 | 01 Jun 17:00 | 무연리 | osm:node/415150771 | no window → 3207 s | no window → 3207 s | no window → 3207 s |
| B | miryang_2022 | 01 Jun 17:00 | 춘화리 | osm:node/415150789 | no window → 3239 s | no window → 3239 s | no window → 3239 s |
| B | miryang_2022 | 01 Jun 17:00 | 용지리 | osm:node/415150790 | same | same | no window → 3317 s |
| B | uiseong_andong_2025 | 24 Mar 18:00 | 금학리 | osm:node/415160343 | no window → 2969 s | no window → 2969 s | no window → 2969 s |
| B | uiseong_andong_2025 | 24 Mar 18:00 | 입암리 | osm:node/415160345 | no window → 3330 s | no window → 3330 s | no window → 3330 s |
| B | uiseong_andong_2025 | 26 Mar 02:00 | 망호리 | osm:node/415160466 | no window → 3041 s | no window → 3041 s | no window → 3041 s |
| B | uljin_2022 | 04 Mar 15:00 | 하당리 | osm:node/415155401 | no window → 3374 s | no window → 3374 s | no window → 3374 s |
| B | uljin_2022 | 04 Mar 15:00 | 소곡리 | osm:node/415155416 | no window → 3412 s | same | same |
| B | yeongdeok_2025 | 26 Mar 04:00 | 남산리 | osm:node/415160164 | no window → 3039 s | no window → 3039 s | no window → 3039 s |
| B | yeongdeok_2025 | 26 Mar 04:00 | 대탄리 | osm:node/415160205 | no window → 3301 s | no window → 3301 s | no window → 3301 s |
| B | yeongdeok_2025 | 26 Mar 08:00 | 남산리 | osm:node/415160164 | no window → 3039 s | no window → 3039 s | no window → 3039 s |
| B | yeongdeok_2025 | 26 Mar 08:00 | 대탄리 | osm:node/415160205 | no window → 3301 s | no window → 3301 s | no window → 3301 s |
| B | yeongdeok_2025 | 26 Mar 08:00 | 송천리 | osm:node/415160314 | same | same | no window → 3228 s |
| B | yeongdeok_2025 | 26 Mar 17:00 | 남산리 | osm:node/415160164 | no window → 3039 s | no window → 3039 s | no window → 3039 s |
| B | yeongdeok_2025 | 26 Mar 17:00 | 대탄리 | osm:node/415160205 | no window → 3301 s | no window → 3301 s | no window → 3301 s |

**What did not improve.**

* **Panel A is not changed at 4.7 or 2.5 kW/m2, and 12 windows are still lost at 4.7.** The replay field puts the first
  cell outside a detection disc a few minutes after issue, so the donors' own spread rate is the cap (41 % of the
  donor-rated cells; median 138 m/min) and the fix replaces the cap by the cap. The "silent" exploratory row (A6) loses 8.
* **Panel B still loses 2 windows at 4.7 (1 at 7, 2 at 2.5)**, both in Uljin 4 Mar 15:00 KST (소곡리 and the node
  415155415 at 4.7), from known-fire cells that now have a donor rate of 13-19 m/min but still a crown flame with d* of
  65-138 m. The A6 silent row loses none, so these come from radiation of known-fire cells that the rule keeps; I did
  not trace them further.
* **The part of the panel B gain that is not physics:** 12 of the 20 recovered windows (4.7 kW/m2) are in the 6 packets
  where no cell has a real gradient within the 1 h horizon, so the rule's fallback (no rate, no flame) applies and the
  known fire does not radiate at all. That is the A6 "silent" result for those packets, not a spread-rate estimate; a
  different fallback would give a different count.
* The rule keeps radiating from burned-out interior cells (conservative). Cells that are really out are not turned
  off; no residence time is used.
* **Sensitivity rows** (fuel low / high, 1090 / 1400 K, view factors, no transmissivity) were not rerun after A7: they
  are 8 settings × 41 inputs of routing (hours on 4 cores) and are left as in the pre-A7 table below, which is marked.
  Their panel B rows contain the artefact.

**Test.** `tests/test_known_fire.py`: fails if any known-fire cell with a flat or undefined gradient has the default-cap
provenance; a synthetic block checks the donor rates (15-30 m/min, not 150), cells outside the known fire keep the cap,
no donor gives no rate; and the two committed replay rasters (always) and all 15 finals packets (set
`WFG_ROUTING_INPUTS` to the fetched `data/routing`) are checked. 17 passed, 2 skipped in the default run (the packets case, and the existing closure test that needs
`data/routing`); 18 passed, 1 skipped with `WFG_ROUTING_INPUTS` set. The product suite (heat, vendoring) passes: 20 passed, 1 skipped. The old function still returns the cap (test of the artefact).

## The table, before A7 (as run for PR #228; panel B rows contain the artefact, the A7 section above has the corrected main rows)

Leave-by changes against no heat, per heat rule and threshold q* (kW/m2). Panel A: Gyeongbuk replay, 13 issue
hours 12:00-24:00 KST x 2 regions, 8 h horizon; 27,759 road cell-hours, of which 20,115 are inside the known fire at
issue and 7,644 are reached later; 1,134 place-hours with a leave-now window. Panel B: the 15 finals packets
(Uiseong-Andong, Yeongdeok 2025; Uljin, Miryang 2022; Hongseong 2023), 1 h horizon; 3,422 road cell-hours, 3,402 at
issue, 20 reached later; 425 place-inputs with a leave-now window. "Road cells closed earlier": reached road
cell-hours whose earliest road piece closes before the contact rule. "Unreached cells": road cells the fire never
reaches inside the horizon in which some piece is closed by heat. Shift: minutes, over the changed leave-by times
that keep a window. Last column: leave-by times that differ from the old law at the same threshold (how many of them
are later than the old law's).

| panel | heat rule, q* | road cells closed earlier | unreached cells partly closed | leave-by times changed | windows lost | shift median / max (min) | vs old law |
|---|---|---:|---:|---:|---:|---|---|
| A replay | old law, 7 | 7,644 | 156 | 349 | 5 | 2.1 / 20.3 | – |
| A replay | old law, 4.7 | 7,644 | 166 | 350 | 7 | 3.1 / 27.9 | – |
| A replay | old law, 2.5 | 7,644 | 173 | 352 | 19 | 5.9 / 72.5 | – |
| A replay | **new, 7** | 7,471 | 145 | 330 | 12 | 2.7 / 26.8 | 347 (165 later) |
| A replay | **new, 4.7** | 7,512 | 155 | 337 | 12 | 3.7 / 28.1 | 344 (174 later) |
| A replay | **new, 2.5** | 7,532 | 175 | 342 | 14 | 6.5 / 42.3 | 334 (163 later) |
| A replay | new 4.7, fuel low | 6,644 | 133 | 268 | 12 | 2.4 / 26.2 | 342 (271 later) |
| A replay | new 4.7, fuel high | 7,640 | 180 | 350 | 14 | 5.2 / 42.6 | 345 (144 later) |
| A replay | new 4.7, 1090 K | 7,488 | 145 | 333 | 12 | 2.7 / 26.9 | 343 (232 later) |
| A replay | new 4.7, 1400 K | 7,532 | 175 | 342 | 14 | 6.5 / 42.2 | 347 (110 later) |
| A replay | new 4.7, worst angle | 7,644 | 179 | 352 | 12 | 4.9 / 41.3 | 345 (153 later) |
| A replay | new 4.7, vertical plane | 7,644 | 179 | 352 | 12 | 4.8 / 41.2 | 345 (155 later) |
| A replay | new 4.7, Mudan cylinder | 7,644 | 175 | 352 | 12 | 3.9 / 28.7 | 345 (162 later) |
| A replay | new 4.7, no transmissivity | 7,513 | 156 | 337 | 13 | 4.7 / 29.1 | 345 (153 later) |
| A replay | new 4.7, known-fire cells silent (EXPLORATORY, not in protocol) | 7,512 | 155 | 337 | 8 | 3.7 / 28.1 | – |
| B packets | old law, 7 | 20 | 326 | 2 | 0 | 2.2 / 2.2 | – |
| B packets | old law, 4.7 | 20 | 331 | 2 | 0 | 3.2 / 3.2 | – |
| B packets | old law, 2.5 | 20 | 347 | 3 | 1 | 6.0 / 6.0 | – |
| B packets | **new, 7** | 20 | 414 | 24 | 22 | 1.4 / 2.2 | 24 (1 later) |
| B packets | **new, 4.7** | 20 | 439 | 24 | 22 | 1.9 / 3.2 | 24 (1 later) |
| B packets | **new, 2.5** | 20 | 626 | 28 | 25 | 5.7 / 22.2 | 27 (2 later) |
| B packets | new 4.7, fuel low | 20 | 420 | 22 | 20 | 1.0 / 1.6 | 22 (2 later) |
| B packets | new 4.7, fuel high | 20 | 497 | 27 | 24 | 3.8 / 22.1 | 27 (1 later) |
| B packets | new 4.7, 1090 K | 20 | 415 | 24 | 22 | 1.4 / 2.3 | 24 (2 later) |
| B packets | new 4.7, 1400 K | 20 | 624 | 28 | 25 | 5.6 / 22.2 | 28 (1 later) |
| B packets | new 4.7, worst angle | 20 | 441 | 25 | 22 | 3.3 / 22.0 | 25 (1 later) |
| B packets | new 4.7, vertical plane | 20 | 438 | 24 | 22 | 1.9 / 3.2 | 24 (1 later) |
| B packets | new 4.7, Mudan cylinder | 20 | 417 | 24 | 22 | 1.8 / 3.0 | 24 (2 later) |
| B packets | new 4.7, no transmissivity | 20 | 519 | 27 | 24 | 3.7 / 22.1 | 27 (1 later) |
| B packets | new 4.7, known-fire cells silent (EXPLORATORY, not in protocol) | 12 | 22 | 1 | 0 | 3.2 / 3.2 | – |

## Checks (step 2): gate for the road layer = C1, C2 and C3 pass

* **C1, Butler and Cohen (1998), amended A1** (20 m front, 1200 K, emissivity 1, vertical flame, no attenuation).
  Linear fit of d(7 kW/m2) on flame height for H = 1-10 m: **3.54 H** (they: 4 H, -11 %). Zárate et al. (2008), same
  geometry: 3.8 H at 7 and 4.8 H at 4.7 kW/m2; here 3.54 H (-7 %) and 4.44 H (-8 %). Long front (W/L > 50): **8.34 L**
  (Rossi et al. 2011: 8 L, +4 %). **Pass.** With a fixed 20 m width d/H falls with H (6.2 at 2 m, 4.3 at 5 m, 3.1 at
  10 m, 2.1 at 20 m), so the "4 x flame height" rule holds for fronts a few times wider than the flame is tall; a long
  front needs about 8 x flame length. Implementation: McGuire's closed form equals the numerical integral at zero tilt
  (< 1e-4), Mudan's cylinder equals direct integration (< 1 %), flux decreasing in d; 11 tests pass.
* **C2, FDS (model-to-model).** C064 grass fire (I = 4.47 MW/m, 60 m head): the solid flame is **19-115x above** FDS's
  radiometers at 1-60 m and 1.2-3.6x above the unattenuated voxel sum of the same run (1.2-1.9x beyond 5 m); the old
  closed form was 6-109x above FDS. **Pass** (never on the unsafe side). Local FDS: the plane-layer verification
  reads 2.918 vs 2.897 kW/m2 analytic (+0.7 %); a 240 kW propane strip, calm, gives 5.18 / 1.70 / 0.69 kW/m2 at
  0.6 / 1.6 / 2.6 m against 8.9-9.7 / 2.0-2.8 / 0.8-1.2 for the solid flame, **1.2-1.7x** (FDS not grid-converged).
  So the 20-100x gap appears in FDS's coarse vegetation run, not on a resolved flame.
* **C3, flame length vs observations.** ICFME crown fires (Stocks et al. 2004; 11 plots, 13,400-93,500 kW/m, flame
  fronts 25-40 m high): Thomas from the reported intensities gives 15-55 m, worst factor **1.67**; the full chain
  from the reported spread rates with this study's pine fuel (middle) gives 15-41 m, worst factor **1.65** (low fuel:
  3.1; high: 1.31). **Pass.** Surface fires, range only (A4): grass at RxCADRE spread rates 0.8-3.6 m vs observed
  heights 0.3-1.8 m; pine litter 0.6-2.3 m vs about 0.5 m (Nelson and Adkins 1986). Both high, the safe side.
* **C4, sensitivity** (Uiseong median conditions; d* at 7 kW/m2, baseline then range): pine crown fire at 30 m/min
  (L 23 m) 133 m, 60-301 m over all settings; by flame temperature 98-204, fuel 101-160, view factor 104-134,
  transmissivity 133-167. Pine surface fire at 3 m/min (L 1.6 m): 12 m, 7-29 m. Grass at 14 m/min (L 1.9 m): 14 m,
  0-40 m. On the panels the sensitivity rows of the table move the replay count between 268 and 352 of 1,134.

## The four reconstructed fires (per-cell tables in `data/fires/`)

Every burned 375 m cell of the KFS arrival reconstructions at its arrival hour, middle fuel:

* **Uiseong 2025** (10,955 cells; R median 13 m/min, 10 % at the 150 m/min cap; 34 % crown): flame length median
  3.3 m, 90 % 40 m, max 68 m; d*(7) median 24 m, 90 % 197 m, max 277 m (fuel high 320 m); lead d*(7)/R median 2.4 min.
* **Uljin 2022** (1,937 cells; R median 1.7 m/min; 20 % crown): L median 1.2 m, max 42 m; d*(7) median 9 m, max 281 m.
* **Hongseong 2023** (153 cells; 18 % crown): L median 1.1 m, max 35 m; d*(7) median 8 m, max 199 m.
* **Miryang 2022** (80 cells; 5 % crown): L median 0.8 m, max 6.7 m; d*(7) median 11 m, max 63 m.
* d*(7) < 375 m in **100 %** of cells in all four fires at every fuel level; d*(2.5) < 375 m in 91 % (Uiseong), 99 %,
  100 %, 100 %.
* **FRP cross-check** (Wooster et al. 2005, detections within 1 h of arrival): the model's intensity is above the
  FRP-implied one in most pixels; median ratio 341 (Uiseong, 1,159 detections), 7.4 (Uljin, 830), 6.1 (Hongseong,
  88), 4.2 (Miryang, 19); rank correlation -0.30 to 0.33. FRP-implied intensities are 30-285 kW/m at the median:
  a 375-750 m pixel averages flaming and smouldering parts, a front rarely fills it at the overpass, and smoke and
  saturation hide flames (Johnston et al. 2017 found FRP per front length the weakest route to Byram's intensity).
  The Uiseong ratio also reflects spread rates from a kriged arrival field that includes spotting. The check neither
  corroborates the model's intensities nor shows them too low.

## Panels: what else the runs show

* Replay front cells (7,644 cell-hours reached after issue): R 9 / 25 / 27 m/min (10 / 50 / 90 %; the MEASURED reach
  curve's speed), 46 % crown; flame length 3.6 / 21 / 60 m (50 / 90 % / max), height 3.4 / 15 / 55 m; d* at 7 / 4.7 /
  2.5 kW/m2: median 25 / 36 / 63 m, 90 % 104 / 139 / 212 m, max 255 / 319 / 445 m; share below 375 m 100 / 100 /
  99.8 %. Lead at 4.7: median 2.4 min, 90 % 5.6, max 8.5.
* Flux at the road when the earlier-burning neighbour cell is reached (front at its nearest edge; 7,644 cells with
  such a neighbour): >= 7 kW/m2 for 6,285, 4.7-7 for 157, 2.5-4.7 for 195, below 2.5 for 1,007. Median 63 kW/m2. That
  is the 375 m rule at work: a road within a few metres of a cell edge is inside the flame zone when the neighbour
  is "reached", whatever the physics.
* Why the old and the new law move about the same number of leave-by times: in both, a road piece near the edge of a
  burning neighbour closes when that neighbour is first reached, up to an hour before its own cell (median 15 min for
  either law). That shift is set by the cell size and the reach curve, not by the radiation model. The radiation
  model decides only the in-cell lead (new: d*/R, median 2.4 min at 4.7; old: T* = 3.1 min at 4.7, independent of R)
  and how far the halo reaches (new: tens to hundreds of metres; old: 11-33 m).
* Panel B, the 22 lost windows (before A7): every one was caused by cells inside the known fire area at issue (arrival
  0, a flat field, so R = the 150 m/min cap and a crown flame of ~50 m), with d* of ~290 m closing nearby road pieces at
  second 0. A7 replaces the cap there (2 lost windows remain; see "A7").

## Road layer (step 4)

The gate passed, so the method is in `product/wfg-roadlayer` as the heat option (`--heat`, `--heat-threshold
7|4.7|2.5`; settings `[heat]`), vendored byte for byte from `kcf_radiation/` (tested). Road pieces close by the rule of
PROTOCOL section 6; the certificates carry the per-piece and per-node closure seconds, and the standalone verifier
re-derives the masks from them (all certificates of a heat run verify). With heat off every output is byte-identical
to before (golden tests; only the verifier script's own hash changed). The old law was never in the road layer, so
"replacing" it means the heat option is this method and nothing else.

**Default: off.** The protocol says off unless it changes answers. It does change answers (337 of 1,134 replay
leave-by times at 4.7 kW/m2), but the changes are driven by the 375 m cell rule (the old law, with a halo of 11-33 m,
changes as many) and, in the packets before A7, almost entirely by the capped spread rate of the known fire area. After
A7 the cap is gone from the known fire (the `--heat` path of the road layer uses the same rule, vendored byte for byte),
but 12 of the 20 packet windows it recovered come from a no-data fallback, 2 windows are still lost, and on the replay
the effect of the fix is nil at 4.7 kW/m2. **The default stays off**: the 375 m cell rule still sets most of the timing
change, and a rule for the burned-out interior needs the age of the burn, which the inputs do not hold. An arrival grid
finer than 375 m would also be needed. Both would be new protocol work.

## Limits

* **Fuel data quality.** Copernicus 2019 land cover stands in for a fuel map; Korean crown-fuel values come from a
  few Gyeongbuk stands; mixed forest is an assumption. Fuel load moves a crown cell's d* by about 1.6x.
* **375 m resolution.** Arrival and spread rate are cell values, and the position of the front inside a cell is
  unknown. The safe distance is below the cell size almost everywhere, so the cell rule, not the radiation model,
  sets most of the timing change.
* **Radiation only.** No convection (Zárate et al. add 20 % to distances for it), no flame contact beyond the cell
  rule, no embers or spot fires, no smoke.
* **Spread rate** read from interpolated (KFS) or screening (replay) arrival fields, capped at 150 m/min. Since A7, flat
  fields inside the known fire area take the rate of the nearest real-gradient cells (no cap), or no flame where the
  input has none; flat cells outside the known fire keep the cap.
* **Weather**: one ECMWF wind per hour at ~9 km, no gusts; slope not used.
* **Thresholds** are for people outside a vehicle (firefighters in clothing, emergency workers, skin); none is
  validated for vehicle occupants.
* **Data**: the folder named in the brief could not be reached (again on 2026-11-20: no computer attached, and the Drive
  connector available here cannot read files); inputs come from an earlier release of the same workspace (DATA.md). The A7
  rerun uses per-road-cell fuel, wind and RH from the committed tables and a recovered air temperature (see "A7").
