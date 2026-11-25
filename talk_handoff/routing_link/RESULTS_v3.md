# RESULTS v3 Part A: heat and toxic gases as the reason a road is blocked, Fish Creek (25 Nov 2026)

Protocol: `PROTOCOL_v3.md` (1b2389f9, written before any v3 result), Part A only. **No amendment was made after the
results were seen** (section 12 is empty). Same case as v1 and v2: WY-BTF-002416_FishCreek, cutoff 2024-08-23T00:00Z,
hours 0–5, the same 1,024 retained paths, the same OpenStreetMap roads (1,293 road cells, 350 routed origins, 10
refused as in v1/v2). Road cells are now judged at **5,570 road points, 5 m apart**, within 1,300 m of a burning cell.
v1 and v2 files are unchanged. Part B (a second fire) has not been run and waits for approval.

## Headline

**Heat and gas now do block roads before the flame gets there, but on Fish Creek they still change no origin's last
safe departure.**

* **Main setting** (a criterion blocks a road cell once half of the 1,024 paths meet it, with the flame-contact time
  half of the paths give): **0 road cells blocked, by anything, and 0 of 350 origins change**, for residents and
  for responders. No road cell is reached by the flame in more than 8.1 % of the paths. No road cell meets a heat
  criterion in more than 4.1 % of them, and none meets a gas criterion in more than 3.9 %. So the 10 %, 50 % and 90 %
  levels all give nothing.
* **Each path on its own** (n = 1,024):
  * heat blocks a road cell before the flame touches it in **234 paths** (308 path-cells, 7 distinct road cells);
  * gas does so in **73 paths** (75 path-cells, 8 distinct road cells);
  * either heat or gas does so in **284 paths**.
  * Heat comes a median of **22 min** before flame contact at the cell (n = 142, range 4–239). Gas comes a median of
    181 min before (n = 30, range 32–242).
  * In 166 heat-blocked and 45 gas-blocked path-cells, the flame never reaches the road in that path at all.
  * Yet in **0 of 1,024 paths does any origin's last safe departure change**. Flame contact alone cuts an origin in
    only 1 path (no. 368, 2 origins), and adding heat and gas leaves that path's times as they were.
* **The only pairing that moves an origin** pairs the "any path" level for heat and gas with the half-of-paths flame
  contact.
  * It blocks 15 road cells (9 because of heat, 6 because of gas). It makes 2 origins' last safe departure
    **91 and 92 min earlier** (junctions osm:1049814569 and osm:158210457).
  * Heat alone gives the same 91 and 92 min. Gas alone gives 83 and 84 min.
  * Flame contact in any path, with no heat or gas at all, cuts the same 2 origins by the same 91 and 92 min.
  * With flame contact also read at "any path" (any, any), heat and gas change nothing (0 of 350). In v2 this pairing
    gave 70 and 71 min (CO, whole cell).

In plain words: heat and gas now act as a reason a road is blocked. The heat reason reaches the road about 9 m ahead
of the flame front (median, residents), which is consistent with the pipeline's short, low flames. On this fire the
roads the fire reaches are not ones any origin depends on in the 6 h horizon, except in one path. So no criterion,
heat, gas or flame, changes evacuation timing at the levels fixed in advance.

## Before the numbers: checks (PROTOCOL_v3 section 10)

| check | result |
|---|---|
| 1. regression to v2 (front at cell centre, whole-cell blocking, no crown, CO only) | 273 of 273 paths: whole-cell blocking identical, CO under the v2 rule identical |
| 2. recorded fronts reproduce the pipeline's 375 m radiant kernel | largest difference 4.3 × 10⁻⁷ W/m²; rebuilt centre fronts equal the pipeline's to 9 × 10⁻¹⁰ m (50 fronts) |
| surface spread rate from pyrothermel against the pipeline's | largest relative difference 1.1 × 10⁻¹² |
| 3. acrolein and HCN = CO × emission-factor ratio; thermal dose = the pipeline's `PublishedDangerCriteria` law | exact by construction and tested; the FED law string matches the pipeline metadata |
| 4. moving front on a synthetic cell | contact = entry + projected distance / rate; tested (straight and diagonal) |
| 5. crown: Thomas length at 38,800 kW/m | 30.49 m against Rothermel 1991 Table 4's 100 ft (30.48 m) |
| 6. synthetic tests | 29 pass (13 v1, 8 v2, 8 v3) |

Cells whose traverse time hit the 60 s floor: 0. Per-path export: 419 s. Routing: 1,770 per-path road-layer runs over 12
processes. A run is reused when its road-cell blocking times match an earlier run in that path exactly. This happened
in 740 of 1,024 residents runs and all 1,024 responder runs.

## 1. Crown fire on this fire (crown.json, n = 515 source cells)

* 499 of the 515 cells have canopy. Van Wagner initiation is possible in **493**. Active crown fire is sustained in
  **0**, so all 493 burn as passive crown fire.
* Surface fireline intensity: median 1,434 kW/m, largest 6,027. Critical intensity: median 76 kW/m.
* Crown fireline intensity: 98–6,926 kW/m. Crown flame length (Thomas): 0.57–9.66 m, median 4.28 m.
* Front rate in crown cells: 0.0054–0.33 m/s.

## 2. Per criterion, each path on its own (n = 1,024 paths)

"Before contact" means the criterion blocks the road cell earlier than the flame front touches any road point in it.

| criterion | paths with a road cell blocked | path-cells blocked | paths with one before contact | path-cells before contact | of those, never contacted |
|---|---:|---:|---:|---:|---:|
| flame contact | 245 | 270 | – | – | – |
| whole cell (v1/v2 fire arrival) | 281 | 319 | 272 | 308 | 49 |
| H1 2.5 kW/m² (residents) | 253 | 426 | 241 | 328 | 156 |
| H1 7.0 kW/m² (responders) | 245 | 324 | 115 | 124 | 56 |
| H2 FED ≥ 0.3 in 10 min | 266 | 443 | 254 | 345 | 173 |
| H2 FED ≥ 0.3 in 30 min (sensitivity) | 276 | 460 | 264 | 361 | 190 |
| CO AEGL-2 | 273 | 308 | 194 | 210 | 41 |
| acrolein AEGL-2 | 294 | 334 | 218 | 235 | 64 |
| HCN AEGL-2 | **0** | 0 | 0 | 0 | 0 |

* HCN never reaches its AEGL-2 anywhere. This matches the expectation stated before the results: 7–15 times weaker
  than CO.
* Acrolein blocks in more paths than CO (294 against 273). This also matches the expectation: 1.24–1.43 times
  stronger.
* With the crown phase off, acrolein and CO block exactly the same 308 path-cells (section 5).
* **Residents and responders end up with identical blocking times on every road cell.** H2 applies to both, and the
  FED law reaches 0.3 in under a minute at 2.5 kW/m². So FED10 blocks wherever H1 2.5 does, and the 7.0 kW/m²
  responder threshold never decides. This follows from the protocol as written; it was not changed.

## 3. Attribution of every blocked road cell (residents; responders identical)

Tie order: flame, then heat, then gas.

| | path-cells | paths | distinct road cells |
|---|---:|---:|---:|
| flame contact first | 98 | – | – |
| heat first | 308 | 234 | 7 |
| gas first | 75 | 73 | 8 |

* Heat before contact, at the cell: median 22 min, IQR 21–38, range 4–239 (n = 142 path-cells that contact
  reaches). 166 heat-first path-cells are never reached by the flame in that path.
* Gas before contact: median 181 min, IQR 46–181, range 32–242 (n = 30). 45 gas-first path-cells are never reached
  by the flame.

## 4. How far ahead of the flame heat blocks a road (section 8 item 4)

At the road point that heat blocks first, the distance to the flame front at that minute, and the minutes from that
heat block to flame contact at the same point:

| audience | distance, m | minutes to contact at that point | heat-blocked points never contacted |
|---|---|---|---:|
| residents (2.5 kW/m²) | median 9.2, IQR 5.6–17.2, range 1.4–40.9 (n = 292) | median 3, IQR 2–3, range 1–272 (n = 140) | 152 |
| responders (7.0 kW/m²) | median 2.5, IQR 1.0–5.5, range 0.05–16.6 (n = 195) | median 0, IQR 0–1, range 0–92 (n = 142) | 53 |

The 22 min lead at the cell (section 3) is longer than the 3 min lead at the point. This is because the cell lead
compares the first heat block at any of its points with the first flame contact at any of its points. These are
often different points of the same 375 m cell.

## 5. Surface only against surface plus crown (sensitivity, residents)

| | surface + crown | surface only |
|---|---:|---:|
| paths with a heat-first road cell | 234 | 159 |
| heat-first path-cells | 308 | 179 |
| paths with a gas-first road cell | 73 | 147 |
| gas-first path-cells | 75 | 159 |
| paths with heat or gas first | 284 | 247 |
| paths where an origin changes | 0 | 0 |

The crown phase adds heat. With crown heat present, heat reaches many cells before gas does, so those cells move from
the gas column to the heat column.

## 6. Whole-cell fire arrival beside flame contact (section 8 item 6)

* Whole-cell arrival (v1/v2) blocks road cells in 281 paths (319 path-cells). Flame contact blocks them in 245 paths
  (270 path-cells).
* Where both block, whole-cell arrival is earlier by a median of 26 min (IQR 4–43, range 0–256, n = 270). In 49
  path-cells the fire enters the cell but the front never reaches its road.
* Origins cut: 1 path under either reading. The two readings differ in 1 path.

## 7. Ensemble (share levels, PROTOCOL_v3 section 7)

| heat/gas level | flame-contact level | road cells blocked | of which heat / gas | origins changed (of 350) |
|---|---|---:|---|---:|
| 0.5 (main) | 0.5 | 0 | 0 / 0 | **0** |
| 0.1 | 0.5 | 0 | 0 / 0 | 0 |
| 0.9 | 0.5 | 0 | 0 / 0 | 0 |
| any path | any path | 15 | 5 / 6 | 0 |
| 0.5 | any path | 15 | 0 / 0 | 0 |
| any path | 0.5 | 15 | 9 / 6 | **2** (91 and 92 min earlier) |

* Residents and responders are identical in every row.
* For the last row, routing was repeated with heat alone and with gas alone (`v3_report.py`, section 8 item 3).
  Heat alone: 2 origins, 91 and 92 min earlier. Gas alone: the same 2 origins, 83 and 84 min earlier.
* Flame contact at "any path" alone, against flame contact at 0.5, also gives the same 2 origins, 91 and 92 min
  earlier.
* Largest share of paths meeting each criterion at any road cell:
  * contact 8.1 %;
  * H1 1.7 %;
  * FED10 2.9 %;
  * FED30 4.1 %;
  * CO 3.9 %;
  * acrolein 3.9 %;
  * HCN 0.

## Figure

`fig_v3_heat_gas.{png,svg,pdf}`.

* **Left:** the road network with the 15 road cells the flame reaches in at least one path, and the road cells blocked
  because of heat (7) or because of gas (8) before the flame, in at least one path (residents). Marker size is the
  number of paths.
* **Right:** origins whose last safe departure changes, each path alone and at each ensemble pairing.

## Deviations from PROTOCOL_v3, stated plainly

1. PM2.5 and visibility were not recomputed for v3. The v2 values stand, and they are reported only, never used to
   block.
2. The crown phase covers only cells that ignite inside the horizon. Cells already burning at the cutoff have no
   crown phase.
3. Passive crown fire is modelled as burning the full canopy load (CBD × (CH − CBH)) at the surface front rate.
4. Crown gases and hot-gas temperature come from the pipeline's own `HeatSmokeHazards` crown phase.

## Limits (PROTOCOL_v3 section 11)

* One fire, and the forecast is uncalibrated.
* The moving front is a straight line at a uniform spread rate across a 375 m cell. This is an idealisation of the
  pipeline's cell-scale spread.
* Crown flames are vertical. Crown parameters are LANDFIRE 2016, not measured at the event.
* Gases are at 375 m resolution.
* Emission ratios are means with wide spread (acrolein SD 38 %, HCN SD 61 % of the mean).
* The 10 min thermal-dose window is our choice.
* AEGL and tenability limits were made for the general public and for building occupants, not for people in vehicles.
* No reopening after a block.
* Weather for hours 1–5 is held at the cutoff.
* No Korean case.
* On this fire, few roads lie in the paths' footprints. Only 15 road cells are ever touched by the flame, and flame
  contact cuts an origin in 1 of 1,024 paths. That limits what any blocking reason can change here. Part B's
  selection rule (the fire whose footprint holds the most road) is meant to test this.

## Files

* `v3_physics.py`, `v3_export.py`, `v3_route.py`, `v3_report.py`, `tests/test_v3.py`: code.
* `export_v3/` (`per_path.npz`, `counts.npz`, `crown.json`, `checks_v3.json`): per-path export.
* `out_v3/shard_*_of_12.json`, `out_v3/summary_v3.json`, `out_v3/report_v3.json`, `out_v3/ensemble/*.tif`: routing,
  totals, report numbers, ensemble rasters.
* `fig_v3_heat_gas.{png,svg,pdf}`, `RESULTS_all_v3.pdf`.
