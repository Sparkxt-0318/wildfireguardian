# RESULTS v2: exposure per fire path as road-blocking times, Fish Creek (25 Nov 2026)

Protocol: `PROTOCOL.md` with **Amendment 2** (per-path heat and CO), written **after the v1 results were seen** and
committed before any per-path result (aecd25a0), and Amendments 3–5 for the safety-zone figure (a9915da8, c916df02,
074f7e63; 4 and 5 were written after the previous zone was seen, see below). Same case as v1: WY-BTF-002416_FishCreek,
cutoff 2024-08-23T00:00Z, hours 0–5, 375 m grid of 103 × 73 = 7,519 cells, **45,114 cell-hours**, the same 1,024
retained paths, the same OpenStreetMap roads (1,293 road cells, 350 routed origins), thresholds and sources. v1
(`RESULTS.md`, `RESULTS_all.pdf`, `out_earliest/`, `out_half/`, `export_6h/`) is unchanged.

## Headline

**Evaluated per fire path, at the main setting (a criterion blocks a cell once at least half of the 1,024 paths meet
it; fire arrival by half of the paths), exposure still blocks no cell and no road, and changes no last safe departure:
0 of 350 origins, for residents and for responders.** The reasons are now different for heat and CO. Radiant heat
never reaches 2.5 kW/m² at any cell in any path (largest 0.25 kW/m²): the pipeline's receivers are 375 m apart and a
burning cell gets no heat from its own flame, while 2.5 kW/m² is reached only within about 17 m of its 3 m flame.
CO does exceed AEGL-2 in single paths (up to 1,559 ppm over 10 min), almost always in a cell that is itself burning in
that path, but in at most 10.5 % of the paths at any cell. Only the "any path" level blocks roads: with the
half-of-paths fire reading it adds 13 road cells and makes 2 origins' last safe departure 70 and 71 min earlier; with
the earliest-path reading, the pairing fixed in advance, it adds nothing.

## Before the numbers: checks

| check | result |
|---|---|
| (c) the v2 run reproduces v1: pipeline hourly fields; both fire-arrival rasters; fire-only routing | 23 of 23 arrays identical; both rasters identical; fire-only road-layer results identical for both readings |
| (a) one path (no. 681, the most cells burning) as a probability-1 weight map through the pipeline's own `weighted_exposure_integrals` | 60 s radiant and CO fields identical in 6 of 6 hours; hourly integrals differ by 0.0 |
| (b) mean over the 1,024 paths of the per-path source weights against the v1 active-fire probabilities (n = 185,400 source-minutes) | 99.3 % within 3 standard errors; total 0.48 % below v1. Newly ignited cells: 99.2–99.8 % by hour. Cells burning at the cutoff: 98.0–100 %, their summed weights 0.8–2.7 % below v1 in every hour (each path reuses the same draws in every hour, so one sampling deviation repeats) |
| (b) mean over paths of the 60 s radiant flux against v1 (n = 2,052,917 cell-minutes with a nonzero standard error) | 99.9 % within 3 standard errors; hourly totals within 1.3 % (z between −0.83 and 0.20) |
| (b) mean over paths of the 60 s CO against v1 (n = 731,086 cell-minutes) | **90.6 % within 3 standard errors** (92.3 % where 100 or more paths reach the cell-minute), fewer than the 99.7 % a normal sampling error would give; hourly totals within 1.4 % (z between −0.86 and 0.25); largest difference 9.4 mg/m³ (8.2 ppm) against a largest v1 value of 34 mg/m³. CO is exactly linear in the weights (mean field = field of the mean weights, difference 3 × 10⁻¹⁴), so the gap comes from the weights of the cells burning at the cutoff (previous row); CO at a cell sums many of them, so its standard error is small and their shared deviation shows. Partly explained, not resolved; it concerns the mean, not any per-path value |
| (d) synthetic tests | 21 pass (13 v1, 8 new for the per-path rule) |

`diag_co_check.py` writes the CO diagnostic (`export_v2/diag_co_check.json`).

## 1. Cell-hours blocked by each criterion (n = 45,114 cell-hours)

v1 compared the expected field with the threshold (no level for heat and CO); v2 counts a cell-hour when the share of
paths meeting the criterion reaches the level in some minute of that hour. Number of cells in brackets.

| criterion | v1 | v2, share 0.5 (main) | v2, 0.1 | v2, 0.9 | v2, any path |
|---|---|---|---|---|---|
| radiant ≥ 2.5 kW/m² (residents) | 0 | **0** | 0 | 0 | 0 |
| radiant ≥ 7.0 kW/m² (responders) | 0 | **0** | 0 | 0 | 0 |
| CO, 10 min ≥ 420 ppm | 0 | **0** | 0 | 0 | 634 (172 cells) |
| CO, 30 min ≥ 150 ppm | 0 | **0** | 1 (1 cell) | 0 | 1,894 (433 cells) |
| CO, 60 min ≥ 83 ppm | 0 | **0** | 1 (1 cell) | 0 | 2,049 (448 cells) |
| visibility ≤ 10 m | 0 at 0.5; 2 at 0.1; 0 at 0.9 | **0** | 2 (1 cell) | 0 | 1,715 (407 cells) |

### Largest value reached in 6 h

| quantity | v1, expected field | v2, largest in any path | v2, largest in the median path |
|---|---|---|---|
| radiant flux, 60 s | 0.013 kW/m² | **0.25 kW/m²** | 0.008 kW/m² |
| CO | 29.7 ppm (60 s bin) | **1,559 ppm (10 min), 1,179 ppm (30 min), 645 ppm (60 min)** | 1.1 ppm (each window) |
| largest share of paths meeting the criterion | visibility 0.108 | radiant 0 and 0; CO 10/30/60 min 0.049 / 0.105 / 0.105; visibility 0.108 | |

Median path: for each cell and hour, the median over the 1,024 paths of that path's peak; the table gives the
largest such median. 90th-percentile path, same reading: radiant 0.06 kW/m², CO 338 / 274 / 235 ppm.

## 2. Road cells blocked within 6 h (n = 1,293 road cells)

In brackets: road cells blocked that fire arrival alone does not block. v1 column: visibility level 0.5.

| fire reading | audience | v1 | v2, 0.5 (main) | v2, 0.1 | v2, 0.9 | v2, any path |
|---|---|---|---|---|---|---|
| half of paths (main) | fire only | 0 | 0 | 0 | 0 | 0 |
| half of paths (main) | residents | 0 | **0 (+0)** | 0 (+0) | 0 (+0) | 13 (+13) |
| half of paths (main) | responders | 0 | **0 (+0)** | 0 (+0) | 0 (+0) | 13 (+13) |
| earliest path | fire only | 15 | 15 | 15 | 15 | 15 |
| earliest path | residents | 15 | 15 (+0) | 15 (+0) | 15 (+0) | 15 (+0) |
| earliest path | responders | 15 | 15 (+0) | 15 (+0) | 15 (+0) | 15 (+0) |

## 3. Origins whose last safe departure changes (n = 350 routed origins; 10 of 360 refused NO_ROAD_PATH in every run)

Against fire arrival alone with the same reading. Pairings fixed in Amendment 2: main = 0.5 with half of paths;
"any path" with earliest path.

| fire reading | audience | v1 | v2, 0.5 (main) | v2, 0.1 | v2, 0.9 | v2, any path |
|---|---|---|---|---|---|---|
| half of paths | residents | 0 | **0** | 0 | 0 | 2 (69.9 and 70.9 min earlier) |
| half of paths | responders | 0 | **0** | 0 | 0 | 2 (69.9 and 70.9 min earlier) |
| earliest path | residents | 0 | 0 | 0 | 0 | **0** (paired setting) |
| earliest path | responders | 0 | 0 | 0 | 0 | **0** (paired setting) |

Heat plays no part in any of these changes (it blocks no cell); the two origins change because of CO in a single path.

## 4. Cell-hours that exposure adds to fire arrival (n = 45,114; cells blocked earlier than fire, n = 7,519)

| fire reading | audience | v1 (visibility 0.5) | v2, 0.5 (main) | v2, 0.1 | v2, 0.9 | v2, any path |
|---|---|---|---|---|---|---|
| half of paths | residents | 0 | **0** (0 cells) | 3 (2 cells) | 0 | 1,422 (274 cells) |
| half of paths | responders | 0 | **0** (0 cells) | 3 (2 cells) | 0 | 1,422 (274 cells) |
| earliest path | residents | 0 | 0 | 0 | 0 | 0 |
| earliest path | responders | 0 | 0 | 0 | 0 | 0 |

## 5. Distance from each blocked cell to the nearest cell burning in the same path (Amendment 2 item 7)

**Main setting: no cell is blocked by radiant heat or CO, so there is no road cell to measure.** As fixed in the
amendment, the same distances for every cell blocked by heat or CO at each level (each cell: median over the paths in
which the criterion holds at its first blocked minute; "within one cell" = up to 530 m, the diagonal neighbour):

| level | criterion | cells blocked | of which road cells | cell itself burning (median 0 m) | within one cell (incl. itself) | beyond one cell |
|---|---|---|---|---|---|---|
| 0.5, 0.9 | any | 0 | 0 | | | |
| 0.1 | CO 30 min, CO 60 min | 1 each | 0 | 1 | 1 | 0 |
| any path | radiant (both) | 0 | 0 | | | |
| any path | CO 10 min | 172 | 4 | 170 | 170 | 2 |
| any path | CO 30 min | 433 | 12 | 410 | 415 | 18 |
| any path | CO 60 min | 448 | 13 | 383 | 388 | 60 |

"Beyond one cell" includes paths in which no cell burns at that minute any more (a 30 or 60 min CO mean outlasts its
source). Each of the 13 road cells blocked by CO at "any path" is first blocked in a path in which that road cell is
itself burning (distance 0). For one of them (row 33, column 34) the 60 min criterion, which holds later (minute 59),
does so in 2 paths whose nearest burning cell is 1,677 and 1,875 m away: a 60 min mean outlasting its source. **Heat
blocks nothing at any distance, including the cell next to the flame.**

## 6. Sampling error of the share (Wilson 95 %, n = 1,024 paths)

At 0.5 and 0.9 no cell is blocked by heat or CO. At 0.1, the one cell blocked by CO (30 and 60 min) has a share whose
95 % interval includes 0.1 (half-width 0.018): it is at the edge of the level. All 1,024 paths were used (a timing
probe gave about 1 s per 32 paths per hour), so no subset and no subset error.

## 7. Safety zone in one path (Amendments 3–5; `fig_safety_zone.{png,svg,pdf}`)

Rule fixed before its data (Amendment 3): the path whose burned area at 6 h is closest to the median (path 0, 200
cells; median 200) and the minute at which that path has the most cells burning (minute 59, 00:59Z, 8 cells). Peak
values in that path at that place and time, not averages over paths. Routing compares that path's own fire arrival
with fire arrival plus the zone over the six hours.

| receivers | zone ≥ 2.5 kW/m² (residents) | zone ≥ 7.0 kW/m² (responders) | road pieces inside (2.5 / 7.0) | origins changed, residents / responders (n = 350) |
|---|---|---|---|---|
| 375 m grid, the pipeline's own receivers (Amendment 3) | **empty** (largest flux 0.072 kW/m² at that minute, 0.12 in 6 h) | empty | 0 / 0 | 0 / 0 |
| 5 m, one height per 375 m cell (Amendment 4) | up to 17.9 m from a flame front; 32,225 m² | up to 6.2 m; 6,850 m² | 0 / 0 | 0 / 0 |
| 5 m, on the pipeline's terrain plane (Amendment 5; the figure) | **up to 16.7 m from a flame front; 60,975 m²** | **up to 5.8 m; 20,500 m²** | **0 / 0** | **0 / 0** |

Fire arrival alone in that path blocks 1 road cell and cuts no origin within 6 h. The 59 road pieces near that path's
burning cells come no closer than the zones: their largest flux in 6 h is 0.69 kW/m². The 5 m evaluation uses the
pipeline's own flame fronts, recorded as it built them; they reproduce its 375 m kernel to 4 × 10⁻⁷ W/m².

Amendments 4 and 5 were written **after** the previous zone was seen. The 375 m zone was empty, which led to Amendment
4. The Amendment 4 zone covered only the middle of each front, because its receivers sat at one height per cell while
the flame base follows the slope (it rises or falls by up to 64 m across a front); that led to Amendment 5. No
threshold, path or minute was changed.

## Why the result changes, and why it does not

* **Heat: the grid, not the averaging.** v1's zero came from probability weighting (source weights ≤ 0.14). Per path
  the weights are 1, and the largest flux rises 19-fold, from 0.013 to 0.25 kW/m², but stays far below 2.5. The
  pipeline draws each burning cell's flame as one front 379 m wide (median) and about 3 m tall, with a realistic
  emissive power (median 59 kW/m², largest 332). Its receivers are the 375 m cell centres, and a burning cell's own
  receiver gets 0 by design ("direct contact is covered by the footprint event"). So the nearest receiver that counts is
  375 m away, where the flux is at most 0.22 kW/m² (median 0.013). Evaluated at 5 m, the same fronts reach 2.5 kW/m²
  only within about 17 m and 7.0 kW/m² within about 6 m. On this grid, radiant heat can block a road only through fire
  arrival itself (`export_v2/diag_radiant.json`).
* **CO: rare, and local.** Per path, CO exceeds every AEGL-2 window somewhere (up to 1,559 ppm over 10 min), almost
  always in a cell that is itself burning in that path. No cell meets a CO criterion in more than 10.5 % of the paths,
  so the main level (0.5) blocks nothing. Only "any path" (one path in 1,024 is enough) blocks roads, and with the
  earliest-path fire reading those cells are already blocked by fire.
* **Visibility** was already per path in v1; its shares are unchanged.

## Limits

* One fire, one cutoff, six hours; no Korean case, because Korea has no fuel maps.
* **Amendments 2, 4 and 5 were written after earlier results were seen** (Amendment 2 at the user's request after v1;
  4 and 5 after the previous safety zone). Thresholds, sources, levels and pairings were not changed after any per-path
  result.
* Exposure is uncalibrated: the saved example's physical inputs ("not field-calibrated"); the Gaussian arrival
  uncertainty is an uncalibrated interpretation; crown fire and embers are unresolved and not included.
* **The 375 m grid cannot resolve radiant heat thresholds.** The pipeline's flame is a line front through the cell
  centre, its receivers are cell centres, and a cell's own receiver gets no heat; zero heat blocking is a property of
  that geometry, not evidence that roads beside a flame are safe. The 5 m zone is an extension beyond the grid the
  pipeline runs on; where a real front lies inside a 375 m cell is not known, so 5 m distances from roads to fronts are
  model geometry.
* CO in a burning cell comes from that cell's own plume at a receiver inside the source cell; how well the plume model
  holds that close to the source is not tested here.
* Check (b) for CO is only partly explained (above).
* Per-path weights are fractional in a cell's ignition and extinction minutes (the minute's mean), so a block can come
  up to one minute later than an instantaneous peak would give. Visibility is still evaluated per hour.
* Weather for hours 1–5 is the cutoff weather held constant.
* The thresholds were made for buildings and workplaces (building-egress tenability; AEGL general-population limits),
  not for people in vehicles. The visibility criterion and the 0.5 level are assumptions.
* No populated place or shelter in the OpenStreetMap extract: origins are 360 road junctions, exits the 59 map-edge
  points; whether the Overpass mirror applied the 2024-08-23 date filter is not verified.
* The safety-zone figure shows one possible fire, chosen by a rule, at one minute; it is not the forecast.

## Files

| path | what |
|---|---|
| `RESULTS_all_v2.pdf` | every v2 result, check and limit in one file, v1 beside v2, both figures |
| `fig_blocked_cells_v2.{png,svg,pdf}` | main setting: fire arrival by half of the paths, residents, share 0.5 (exposure adds none) |
| `fig_safety_zone.{png,svg,pdf}` | the safety zone in one path at one minute, and the routing change beside it |
| `export_v2/` | `counts.npz` (paths meeting each criterion per minute and cell), `peaks.npz`, `distances.npz`, `checks_v2.json`, `diag_co_check.json`, `diag_radiant.json`, safety-zone path and 5 m data |
| `out_v2/` | `summary_v2.json`, every v2 blocking raster, road-layer results per run; `out_v2/safety_zone/` the same for the figure |
| `perpath_export.py`, `perpath_rule.py`, `run_v2.py`, `safety_zone_export.py`, `safety_zone_fine.py`, `safety_zone.py`, `build_report_v2.py`, `diag_co_check.py`, `diag_radiant.py` | reproduce (README) |
