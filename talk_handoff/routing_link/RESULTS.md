# RESULTS: exposure fields as road-blocking times, Fish Creek (25 Nov 2026)

Protocol: `PROTOCOL.md` (frozen before any result, dec54b5b) with Amendment 1 (before any result, fba2474b).
Case: WY-BTF-002416_FishCreek, cutoff 2024-08-23T00:00Z, hours 0–5 after the cutoff, 375 m grid of 103 × 73 =
7,519 cells, so **45,114 cell-hours**. Roads: OpenStreetMap, 1,293 road cells, 12,670 nodes, 25,436 road pieces.

## Headline

**At the protocol's settings, exposure blocks no cell and no road, and changes no last safe departure: 0 of
350 origins, for residents and for responders.** Radiant heat and CO never come near their thresholds. The only
criterion that holds anywhere is visibility at the 0.1 sensitivity level: one cell (not on a road), for 2
cell-hours.

## Before the numbers: checks

| check | result |
|---|---|
| saved one-hour example rerun in this environment | identical, 38 of 38 arrays bit for bit |
| 60 s radiant and CO fields, integrated over each hour, against the pipeline's hourly totals (6 hours) | difference 0.0 J/m² and 0.0 mg/m³ in every hour |
| hour 0 from the six-hour path against the saved one-hour example (1,024 sampled paths against exact probabilities) | correlation 0.998 (PM2.5, CO), 0.9999 (heat), 0.959 (visibility probability); largest visibility probability 0.0547 against 0.0537 |
| visibility probability left undefined by the pipeline (lower bound used instead) | 0 cell-hours |
| radiant or CO inputs unresolved | 0 cells in every hour |
| 13 synthetic tests | pass |

## 1. Cell-hours blocked by each criterion (n = 45,114 cell-hours)

| criterion | threshold | cell-hours blocked | largest value reached in 6 h |
|---|---|---|---|
| (a) radiant heat, residents | 2.5 kW/m² | **0** | 0.013 kW/m² (60 s bin) |
| (a) radiant heat, responders | 7.0 kW/m² | **0** | 0.013 kW/m² |
| (b) CO, 10 min mean | 420 ppm | **0** | below 30 ppm (largest 60 s bin 29.7 ppm) |
| (b) CO, 30 min mean | 150 ppm | **0** | below 30 ppm |
| (b) CO, 60 min mean | 83 ppm | **0** | below 30 ppm |
| (c) visibility ≤ 10 m, probability ≥ 0.5 (assumption) | 0.5 | **0** | probability 0.108 |
| (c) same, sensitivity 0.1 | 0.1 | **2** (1 cell, hours 4 and 5; p = 0.108, 0.104) | |
| (c) same, sensitivity 0.9 | 0.9 | **0** | |
| radiant unresolved and not blocked | | 0 | |

Largest visibility probability by hour: 0.055, 0.054, 0.078, 0.094, 0.108, 0.104. Largest 60 s CO bin by hour
(ppm): 18.6, 19.9, 25.9, 28.9, 29.7, 29.6. Largest 60 s radiant bin by hour (kW/m²): 0.011, 0.010, 0.012, 0.012, 0.013,
0.013.

## 2. Fire arrival alone (two reductions of the 1,024-path ensemble, Amendment 1 item 6)

| | earliest path (main) | half of paths (sensitivity) |
|---|---|---|
| cells blocked within 6 h (n = 7,519) | 515 (191 burned at the cutoff + 324 reached) | 191 (burned at the cutoff; no cell reached by half the paths) |
| cell-hours blocked (n = 45,114) | 2,822 | 1,146 |
| road cells blocked (n = 1,293) | 15 | 0 |
| origins with a cut inside 6 h (n = 350 routed) | 2, last safe departure 177.1 and 178.1 min after the cutoff | 0 |

## 3. What exposure adds to fire arrival

Cell-hours blocked by exposure that fire arrival had not already blocked (n = 45,114 cell-hours), and origins whose
last safe departure changes (n = 350 routed origins; 10 of the 360 junctions have no road to the map edge and are
refused by the road layer in every run):

| audience, visibility level | fire = earliest path: added cell-hours | origins changed | fire = half of paths: added cell-hours | origins changed |
|---|---|---|---|---|
| residents, 0.5 (main) | **0** | **0** (median 0, largest 0 min) | **0** | **0** |
| residents, 0.1 | 0 | 0 | 2 (1 cell blocked earlier than fire; not a road cell) | 0 |
| residents, 0.9 | 0 | 0 | 0 | 0 |
| responders, 0.5 (main) | **0** | **0** | **0** | **0** |
| responders, 0.1 | 0 | 0 | 2 (same cell) | 0 |
| responders, 0.9 | 0 | 0 | 0 | 0 |

The one cell blocked at the 0.1 level (row 27, column 28) is one that the earliest path already burns in hour 0,
so under the main fire reduction exposure adds nothing even there.

## 4. PM2.5 (reported, never used to block)

Hourly mean PM2.5 is above zero in 12,477 of 45,114 cell-hours; the largest hourly mean is 7,548 µg/m³ (hour 5).
Largest hourly mean by hour (µg/m³): 4,184; 3,853; 5,750; 7,169; 7,487; 7,548.

## Why exposure blocks nothing here

The pipeline's heat and gas fields are **probability-weighted** (README, "Danger estimation"): each source cell's
contribution is multiplied by its probability of burning during the time bin, and no source cell's probability
exceeds 0.14 in any 60 s bin of the six hours (0.125, 0.116, 0.111, 0.105, 0.113, 0.140 by hour). A threshold made for a person next to a real flame is therefore compared with an expected field, which is
diluted wherever the fire is uncertain. The visibility probability is the exception: it comes from 1,024 sampled
fire histories, not a weighted average, and it still stays below 0.11 everywhere. These zeros say that the forecast's
expected heat and CO, and its sampled visibility, do not reach the published values on Fish Creek roads in these six
hours. They do not say that a person on a road next to the actual flame front would be safe.

## Limits

* One fire, one cutoff, six hours.
* Exposure is uncalibrated: the physical inputs are the saved example's selected scenario (README: "not
  field-calibrated"); the Gaussian arrival uncertainty is an uncalibrated interpretation; crown fire and embers are
  unresolved in the pipeline and not included.
* The fields are probability-weighted expectations (see above), not the exposure in any one fire history.
* Weather for hours 1–5 is the cutoff weather held constant (the pipeline has no weather forecast here).
* The thresholds were made for buildings and workplaces (tenability for building egress; AEGL general-population
  exposure limits), not for people in vehicles. The visibility criterion is an assumption: 10 m is a
  building-egress reference and the 0.5 probability level is our choice.
* No Korean case, because Korea has no fuel maps.
* No populated place or shelter in the OSM extract: origins are road junctions and exits are the map edge. Whether
  the Overpass mirror applied the 2024-08-23 date filter is not verified (`data/OSM_SOURCE.json`).
* The fire-arrival reduction matters more than exposure: earliest path blocks 15 road cells, half of paths blocks
  none.

## Files

| path | what |
|---|---|
| `fig_blocked_cells.{png,svg,pdf}` | the figure: earliest-path fire arrival, residents, visibility 0.5 (exposure adds none) |
| `out_earliest/`, `out_half/` | `summary.json`, all blocking rasters (road-layer format), road-layer results per run (`graph.json` regenerable, not committed) |
| `export_6h/` | the six hourly exposure files, both fire-arrival rasters, `checks.json`, the pipeline's own hourly fields |
| `export_fishcreek.py`, `run_all.py` | reproduce: see README |
