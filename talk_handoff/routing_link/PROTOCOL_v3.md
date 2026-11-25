# PROTOCOL v3: heat and toxic gases as the reason a road is blocked (written 25 Nov 2026, before any v3 result)

## 0. Why there is a v3, stated first

v1 and v2 (PROTOCOL.md with Amendments 1–6; RESULTS.md, RESULTS_v2.md) found that exposure blocks no road at the main
settings on Fish Creek. **This protocol is written after those results were seen, at the user's request, to change
the model so that heat and harmful gases can be the reason a road is blocked.** It is not a reanalysis of v1/v2;
those stay as they are. The reasons the earlier versions could not show heat or gas blocking were diagnosed before
this protocol (RESULTS_v2.md, "Why"):

1. **Fire arrival swallowed everything.** A whole 375 m cell was blocked from the first minute any part of it ignited,
   for the rest of the horizon. Heat and gas are strongest beside the flame, which always lay inside a cell already
   blocked.
2. **Flames were only surface flames, about 3 m tall,** drawn as one line through the cell centre; 2.5 kW/m² reached
   about 17 m. The pipeline has a crown-fire model, but the saved example leaves its inputs empty.
3. **Heat was radiant only.** The pipeline's own published thermal dose (radiant plus hot gas) was not used.
4. **CO was the only gas,** and its AEGL-2 limits are high relative to its dilution.
5. **The case has few roads near the fire** (at most 15 of 1,293 road cells).

Smoke visibility is **not** used to block in v3 (the user's priority is heat and harmful gases); it is reported only.
No threshold is lowered. Every value below is published and its source is named; where a choice is ours, it says so.

## 1. Question

On Fish Creek (Part A), and on a second fire chosen by the rule in section 9 (Part B, only after the user approves),
how often is a road blocked **because of heat or a harmful gas** before the flame itself reaches it, and how much does
that change the last safe departure of each origin?

## 2. What stays as in v2

Case and cutoff (WY-BTF-002416_FishCreek, 2024-08-23T00:00Z, hours 0–5), the 1,024 retained paths and their timing
draws, the 375 m grid, the pipeline and its environment (Amendment 1), the OSM roads and the road layer's own engine
(`route.py`, `product/wfg-roadlayer` unchanged), origins (360 junctions) and exits (59 map-edge points), the per-path
evaluation (Amendment 2 item 1). Fire is still the pipeline's forecast; nothing is calibrated to the observed fire.

## 3. Fire: a moving flame front inside the cell (replaces whole-cell fire arrival)

Each burning cell's flame is a straight front perpendicular to the pipeline's own spread direction of that cell
(`spread_direction_deg_ccw_from_x`, the same direction the pipeline uses to orient its flame), **moving across the
cell** instead of standing at the centre:

* It enters the cell at the cell's ignition time in that path (the pipeline's draw, Amendment 2), at the cell's
  upwind edge (the corner with the smallest projection on the spread direction), and moves at the pipeline's
  horizontal spread rate for that cell (`horizontal_spread_rate_m_s`, Rothermel/Behave via `EnvironmentalCellDuration`;
  where that is unresolved, the cell's projected width divided by the pipeline's traverse time from its fallback cell
  duration minus point residence). With crown fire (section 4), the crown spread rate applies.
* Its width is the cell's chord along the front at its current position; its height, emissive power and terrain are
  the pipeline's (Amendment 5 receivers on the terrain plane).
* It flames from front arrival for the pipeline's point residence time (`point_residence_s`), then that place stops
  flaming.
* **Flame contact:** a 5 m point on a road piece is blocked by fire from the minute the front reaches it. A road
  cell is blocked by fire from the first minute any 5 m point on a road piece in it is reached. This is the v3
  baseline ("fire alone").

Cells burning at the cutoff (first-burn step 0): the front is taken to have already crossed the cell; they flame for
the pipeline's sampled remaining lifetime as a line at the cell centre (as in v2) and are blocked by fire from minute 0.

## 4. Crown fire (the pipeline's own model, with Fish Creek's canopy layers)

* **Inputs**, read only from the data folder (`fuel/`): LANDFIRE 2016 canopy bulk density (CBD), canopy base height
  (CBH), canopy height (CH), canopy cover, at 375 m. Available canopy fuel load = CBD × (CH − CBH) (Scott & Reinhardt
  2001, RMRS-RP-29: "for uniform stands, CBD can be computed as the available canopy fuel load" divided by canopy
  depth). Foliar moisture 100 % (the pipeline's referenced scenario, NWCG PMS 437).
* **Initiation and sustained spread:** the pipeline's `crown_fire` module, unchanged: Van Wagner critical intensity
  from CBH and foliar moisture, Byram surface intensity, critical mass-flow rate 0.05/CBD (Scott 2006, RMRS-RP-58).
* **Crown spread rate:** active crown spread R_active = 3.34 × R10 (Rothermel 1991, INT-RP-438: crown fires averaged
  3.34 times the fuel-model-10 surface prediction, SD 0.59; as used in Scott & Reinhardt 2001 eq. 7–8), with R10
  computed by the pipeline's Rothermel implementation for fuel model 10 at the cell's conditions. Where initiation
  holds but sustained spread does not (passive crown fire), the surface spread rate applies and the crown burns only
  as torching.
* **Crown flame:** fireline intensity I = H × w × R (Byram; the pipeline's `surface_fireline_intensity_kw_m` form)
  with surface plus available canopy fuel and the crown spread rate; flame length from **Thomas (1963)** as used by
  Rothermel (1991) for crown fires: L = 0.0266 · I^(2/3) m with I in kW/m (checked against Rothermel 1991 Table 4:
  38,800 kW/m ↔ 100 ft = 30.5 m). Flame base at CBH; flame taken vertical (no tilt; our choice, stated as a limit).
  The crown phase enters the pipeline's physical model through its own `CrownEmissionInputs` (radiative fraction,
  emissions and heat content from the pipeline's referenced defaults; consumed fraction 1 of available canopy fuel).
* Check reported before results: the number of cells where crown fire can initiate and where it can be sustained,
  and the range of crown flame lengths.

## 5. Heat criteria (at 5 m road points, per path, every minute)

* (H1) Radiant flux ≥ 2.5 kW/m² (residents) or ≥ 7.0 kW/m² (responders), from all surface and crown fronts flaming in
  that path and minute (as v1/v2; SOURCES.md).
* (H2) **Thermal dose FED ≥ 0.3 within any 10 min**, radiant plus hot-gas convection, with the pipeline's own published
  law (`danger_criteria.PublishedDangerCriteria`: CFAST Technical Reference eq. 6.7 / ABCB fire-safety verification
  handbook): dose rate per minute = 1[q ≥ 2.5] q^1.9 / 4.2 + T^3.61 / 4.1 × 10⁸ (q in kW/m², T gas temperature in °C).
  Radiant part at the road point; gas temperature from the pipeline's plume at the cell (ambient + its gas increment).
  **The 10 min window is our choice** (the pipeline integrates over the whole horizon for a stationary receiver; a road
  user does not stay six hours), matching the shortest AEGL window; 30 min is reported as sensitivity.

## 6. Gas criteria (per path, every minute, at the pipeline's 375 m receivers)

Rolling means over 10, 30 and 60 min, windows starting at or after the cutoff, against **AEGL-2 (final values only)**:

| gas | AEGL-2, 10 / 30 / 60 min | source | concentration |
|---|---|---|---|
| CO | 420 / 150 / 83 ppm (480 / 170 / 95 mg/m³) | US EPA AEGL page (final); NRC 2010 vol. 8 | the pipeline's CO field |
| Acrolein | 0.44 / 0.18 / 0.10 ppm | US EPA AEGL page, acrolein 107-02-8 (final), read 25 Nov 2026 | CO field × 0.34 / 113 |
| Hydrogen cyanide | 17 / 10 / 7.1 ppm | US EPA AEGL page, HCN 74-90-8 (final), read 25 Nov 2026 | CO field × 0.64 / 113 |

* The gas fields are the pipeline's CO plume scaled by the ratio of emission factors, because the pipeline's plume is
  linear in the emission factor. Emission factors: **Andreae (2019), ACP 19, 8523–8546, Table 1, temperate forest**:
  CO 113 g/kg (SD 50, N 47), acrolein 0.34 g/kg (SD 0.13, N 7), HCN 0.64 g/kg (SD 0.39, N 12). The ratio is taken
  within one source so that the pipeline's own CO emission factor is not mixed with another compilation's.
  ppm ↔ mg/m³ at 25 °C, 1 atm (24.45 L/mol; acrolein 56.06 g/mol, HCN 27.03 g/mol); CO uses the pipeline's NRC
  mass values.
* Formaldehyde is left out: its AEGL values are interim, not final.
* **Expectation stated before any result:** with these ratios, acrolein reaches its AEGL-2 at about 1.2–1.4 times
  lower dilution than CO (1.43, 1.24 and 1.25 times for 10, 30 and 60 min), and HCN at 7 to 15 times higher
  concentration; acrolein is therefore expected to add a little to CO, and HCN almost nothing. Gas concentrations stay at 375 m cell resolution (the pipeline's receivers), so gas blocks a
  whole road cell.
* PM2.5 and visibility are reported, never used to block.

## 7. Blocking rule and attribution

* **Per path:** each road cell is blocked from the earliest of: flame contact (section 3), H1 (audience threshold),
  H2, and any gas criterion. Each blocked road cell is labelled with the criterion that blocks it first (ties: flame
  contact, then heat, then gas). A road cell blocked by heat or gas before flame contact is **"blocked because of heat"**
  or **"because of gas"**.
* **Ensemble (as v2):** a criterion blocks a cell from the first minute its share of the 1,024 paths reaches 0.5
  (main), with flame contact by half of the paths as the paired fire reading; 0.1, 0.9 and "any path" (with flame
  contact by the earliest path) as sensitivity.
* No reopening (as v1/v2): once blocked, a road cell stays blocked to the horizon.

## 8. Routing and what is reported

* **Per path** (all 1,024 paths, sharded as in Amendment 6): the road layer with flame contact alone, and with flame
  contact plus heat and gas, for residents and responders. Where two runs give identical blocking times on every road
  cell, the second is reused and marked.
* **Ensemble:** the same at the share levels above.
* Reported, each with its n:
  1. per criterion: road cells blocked, and blocked before flame contact (because of it), per path (distribution over
     1,024 paths) and at each share level;
  2. attribution of every blocked road cell to flame contact, H1, H2, CO, acrolein or HCN;
  3. origins whose last safe departure changes (n = 350 routed), by how many minutes, flame contact alone against
     flame contact plus heat and gas, and which criterion caused it;
  4. how far ahead of the flame heat blocks a road: the distance from the blocked road point to the flame front at the
     blocking minute, and the minutes between the heat block and flame contact at that point;
  5. surface only against surface plus crown (sensitivity: the crown phase switched off);
  6. v1-style whole-cell fire arrival beside flame contact, so the effect of section 3 alone is visible.
* One figure in the v1 style: the road cells blocked because of heat and because of gas over the road network, with the
  routing change beside it.

## 9. Part B: a second case, only after the user approves

Selection rule, fixed now: among the regions in the pipeline workspace with LANDFIRE canopy layers, a cutoff the saved
model can run, and an OpenStreetMap road network, the fire whose earliest-path 6 h footprint from its first runnable
cutoff, buffered by 2 km, contains the most road length. Footprint and road length are computed before any exposure
result for that fire; the choice and the runner-up are reported. The same protocol applies unchanged. Korean cases
remain out (no fuel maps).

## 10. Checks before reading results

1. **Regression to v2:** with the front fixed at the cell centre, whole-cell blocking at ignition, no crown phase and
   CO only, the per-path fire-only routing reproduces v2 (Amendment 3–6 runs) exactly.
2. The recorded flame fronts reproduce the pipeline's 375 m radiant kernel (as in Amendment 4: within 10⁻⁶ W/m²).
3. The acrolein and HCN fields equal the CO field times their ratios exactly; the thermal dose equals the pipeline's
   `PublishedDangerCriteria` law on a synthetic input.
4. The moving front: on a synthetic cell, the contact time at a point equals entry time + projected distance / spread
   rate; the front leaves the cell after projected width / spread rate.
5. Crown: Thomas flame length reproduces Rothermel 1991 Table 4 at 38,800 kW/m; Van Wagner initiation counts reported.
6. Synthetic tests pass (v1/v2 plus new tests for sections 3–7).

## 11. Limits stated with every result

One or two fires; the forecast is uncalibrated; the moving front is a straight line at a uniform spread rate across a
375 m cell, an idealisation of the pipeline's cell-scale spread; crown flames are vertical and crown parameters are
LANDFIRE 2016, not measured at the event; gases are at 375 m resolution; emission ratios are means with wide spread
(acrolein SD 38 %, HCN SD 61 % of the mean); the 10 min thermal-dose window is our choice; AEGL and tenability limits
were made for the general public and for building occupants, not for people in vehicles; no reopening after a block;
weather for hours 1–5 held at the cutoff; no Korean case.

## 12. Amendments

Any change after a v3 result is seen is written here first, dated, saying what was seen and why.

### Amendment 1 (25 Nov 2026): how Part B is run. Written after the Part A results and before any Part B result

**What was seen.** After the user approved Part B, three things turned out to be missing that section 9 assumed:

* the pipeline workspace from the zip holds rasters for Fish Creek only; the other 27 US fires have only metadata
  there;
* Fish Creek's fire-specific inputs (whole-cell fuel, point residence, cell burning duration, flame height) come from
  an archived run (`demonstration/heat_spatial_maps/20261013_fishcreek`) whose generator script is not in the
  workspace;
* the road length rule needs OpenStreetMap for each candidate.

Nothing here changes a threshold, a level, a criterion or the selection rule.

1. **Data.** Part B reads the other fires from the user's data folder, `/Users/jp/Desktop/wildfire/data/environment`.
   It is read only: nothing is written there. Its `events.json` equals the workspace's. Check before use: Fish Creek
   at the Part A cutoff, loaded from both folders, gives identical arrays.
2. **Candidates and the first runnable cutoff.** The candidates are the 27 US fires other than Fish Creek; Korean fires
   stay out. A fire's first runnable cutoff is, in time order, the first hourly snapshot that meets three conditions:
   * at least one cell is burned and valid;
   * the saved model's cumulative forecast for hours 1–6 runs (1,024 paths, seed 20261122, as in Part A);
   * `EnvironmentalCellDuration.from_sample` runs.

   A fire with no such snapshot is reported and dropped.
3. **Footprint and road length.** The earliest-path 6 h footprint is the set of cells burned at the cutoff or reached
   by any path within 6 h, on valid coverage. This is `export_fishcreek.py`'s definition. It is buffered by 2 km
   (Euclidean, from cell polygons). Road length is the length of the road layer's graph edges (`osm_graph.build`,
   unchanged) inside the buffered footprint, each undirected segment counted once. OpenStreetMap is fetched with
   Fish Creek's Overpass query, `[date:]` set to the fire's cutoff:
   * for the selection, over the bounding box of the buffered footprint;
   * for the chosen fire, over its full grid, as for Fish Creek.

   The choice, the runner-up, and every candidate's road length are reported.
4. **Fire-specific inputs**, built with the pipeline's own constructors, following the recipe written in the archive's
   README and `summary.json`:
   * fuel: `EcologicalFuelMaps.from_fccs_rasters`, with scenario fuel = coverage × mapped + (1 − coverage) × 10 kg/m²,
     and 10 kg/m² where the loading is unreadable;
   * residence: `FlameResidenceTime.from_fbfm40_raster` with the 2,000 ft⁻¹ fallback SAV;
   * cell duration: `CellBurningDuration.from_front_crossing` at 0.09472 m/s, direction 0;
   * flame height: `FlameHeightEstimate.from_combustion`;
   * physical parameters: `HeatSmokeParameters.from_fuel_models` with the values in `fishcreek_reference.json`;
   * live moisture L2 and Gaussian arrival uncertainty, also as in that file.

   Check before use: the same recipe applied to Fish Creek is compared with the archived arrays, and the largest
   differences are reported. If it does not reproduce them exactly, Part B still uses the recipe, and the difference
   is stated with every Part B result.
5. **Size.** If the chosen fire's full grid makes the per-path export or the routing infeasible within a day on this
   machine, both use the grid window around the buffered footprint plus 10 km on every side. Routing exits are where
   roads leave that window. This is stated as a deviation if used.
