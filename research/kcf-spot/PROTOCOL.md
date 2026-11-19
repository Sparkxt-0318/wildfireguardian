# PROTOCOL: a spot-fire layer for road cells, measured from satellite data (kcf-spot)

Committed before any result of this folder was computed. Later changes are logged in section 9 as amendments, each
with what had been seen when it was made.

**What had been seen when this was written.** The RESULTS.md and PROTOCOL.md of `kcf-adaptive4` (including its
25 March hour table and attribution shares), the SUMMARY and RESULTS of `kcf-idea-forecast`, the headline of
`kcf-validate/RESULTS.md`, the first rows of `kcf-validate/out/kec_official_closure_events.csv`,
`kcf-validate/out/vds/vds2_vs_model_RD.csv` and `kcf-roadcut/validation_table.csv`, the column names of
`kcf-abstain/derived/hours.csv.gz` and `kcf-adaptive4/derived/attribution_ca_dev.csv.gz` / `mar25.csv`, the
`product/wfg-roadlayer/INTERFACE.md`, and the file manifest of `harness-2026-11/data-fetch`. No detection, perimeter
or spot of this folder had been read. No literature result of step 1 had been read.

The user's data folder "wildfire 3 (1)" exists on this computer only as `~/Desktop/wildfire 3 (1).zip` (11 GB).
Its file list was read: it holds the earlier `wildfire` project (Choi et al. 2026 Zenodo 21788344 copy, Korean
region rasters, NIROPS Fish Creek, heat-model code and runs). It holds no `DATA_INDEX.md`, no key file, no FIRMS,
GOFER or Himawari data. Every input below is fetched without a key from the public sources the repository already
uses (`harness-2026-11/data-fetch/MANIFEST.md`). No key is read, printed or committed.

Labels used in RESULTS.md: MEASURED, ORACLE (uses the fire's future; never a result for a method), ASSUMED,
NOT RUN.

## 1. Data

| set | fires | detections used to find spots | front (burned set) | role |
|---|---|---|---|---|
| CA-DEV | the 16 GOFER v0.2 fires of kcf-adaptive4 (`lib4.ca_split`, folds 0 to 3) | FIRMS VIIRS S-NPP + NOAA-20 (country archive, confidence not low) and GOFER hourly perimeters | GOFER perimeter + earlier VIIRS | every fit and every choice |
| CA-HELD | the 12 GOFER fires of kcf-adaptive4 (folds 4 to 6) | same | same | scored once after the freeze |
| KR | the Korean fires of Choi et al. 2026 (Zenodo 21788344) with VIIRS detections; the 12 fires scored in kcf-adaptive4 are the scored set | FIRMS VIIRS S-NPP + NOAA-20 (Korea country archive) | earlier VIIRS (+ Himawari where fetched) | leave-one-fire-out |
| DET | KFS_01 (Uiseong-Andong-Yeongdeok), 22 to 25 March 2025 | FIRMS VIIRS + Himawari-9 AHI hourly hotspots (B07 >= 320 K and B07 - B14 >= 25 K in >= 2 scans of the hour, the kcf-margin rule; files already in `harness-2026-11/data-fetch-2/ahi_kfs01`) | earlier detections | out of every fit; target 1 |

- Himawari for the other Korean fires: attempted with the repository's keyless AHI fetcher (NOAA open bucket) for the
  first 48 h of each fire if the fetch is practical; otherwise NOT RUN and stated.
- Airborne infrared perimeters (Hatchett 2025, Zenodo; Dixie 2021, Rim 2013) are used only to count how many spots
  a high-resolution map shows that VIIRS and GOFER do not (section 2.6). Dixie is also a GOFER fire.
- Forecast wind speed: kcf-abstain `derived/hours.csv.gz` surface gust as issued (GFS or HRRR, maximum over the next
  8 h at the fire), unchanged; the same value as kcf-adaptive4. Wind direction: ERA5 10 m wind direction at the fire,
  hourly, from the Open-Meteo archive. **The direction is a reanalysis standing in for a forecast direction
  (ASSUMED);** issued forecast direction is not in the committed tables. ERA5 10 m wind speed is recorded beside it.
- Terrain: elevation from the Open-Meteo elevation service (Copernicus DEM, 90 m) at the source point, the spot and
  every 375 m along the straight path between them.
- Roads: `product/wfg-roadlayer` road cells (375 m, EPSG:5179) for uiseong_andong_2025 and yeongdeok_2025.
- Closures: `kcf-validate/out/kec_official_closure_events.csv` (official KEC times) and the road-closure rows of
  `kcf-roadcut/validation_table.csv` (REPORTED news times), with the road cells they name.

## 2. Definitions

### 2.1 Grid, looks, burned set

- Grid: 375 m cells (kcf-margin `CELL_KM`), EPSG:5179 in Korea, EPSG:5070 in California.
- A **look** is one snapshot: one VIIRS overpass (detections of one satellite within 10 minutes), one GOFER hourly
  perimeter, or one AHI hour. Each detection marks its cell (VIIRS) or every cell its 2 km pixel covers (AHI);
  a GOFER perimeter marks the cells whose centre it contains.
- **Burned set before a look at time t**, B(t): every cell marked by any look strictly earlier than t (GOFER
  perimeters are cumulative; detections are added as seen).

### 2.2 What counts as a spot fire

In a look at time t, take the cells it marks that are not in B(t) ("new cells"), and group them into clusters with a
linkage distance of 1 cell for VIIRS (8-connectivity) and 1 pixel (2 km) for AHI and GOFER. A cluster is the
**front** if it lies within d_min of B(t) or of another front cluster of the same look; otherwise it is a
**candidate spot** if all of the following hold:

1. its distance to B(t) is at least **d_min = 1.0 km for VIIRS** (at least one undetected 375 m cell between pixel
   footprints) and **4.0 km for AHI and GOFER** (at least one undetected 2 km pixel);
2. its distance to B(t) is at most **d_max = 15 km** (beyond that it is counted as a separate fire; spots beyond
   the kcf-margin 5 km separate-fire rule are flagged as such);
3. its centroid is outside the convex hull of B(t) (an unburned island lighting up inside the fire is not ahead of
   the front);
4. B(t) is not empty and the fire's first look was at least 3 h earlier (no spots before a front exists).

A candidate spot is **confirmed** if at least one cell on the straight line between the cluster and the nearest
cell of B(t) (the gap) is marked by a later look of any system: the gap burned after the spot, so it was unburned
when the spot was seen. Otherwise it is **unconfirmed** (the gap was never marked: unburned, or burned and not
detected). Both are reported; **confirmed spots are primary.**

Cells marked in later looks that link (by the same linkage) only to spot-born cells and not to the front are also
**spot-born**, until they link to the front. A cell is **lit before the main front** if it is spot-born.

### 2.3 Recorded for every spot

Fire, look time and system, distance to B(t) (km, nearest cell to nearest cell), size (cells), bearing from the
nearest B(t) cell to the cluster centroid, angle between that bearing and the downwind direction (ERA5 direction
+ 180 deg, at the look hour), forecast gust (m/s), ERA5 10 m speed and direction, local hour, elevation of source
and spot, mean slope along the path, highest point on the path above the higher end (a ridge crossing if > 50 m),
confirmation, and whether another system saw it within 1 h.

**Downwind** = angle within 45 deg of downwind; **upwind** = within 45 deg of upwind; otherwise crosswind.
Candidates that are not spots (independent ignitions, gaps in detection along a continuous front, geolocation error)
are assumed not to prefer downwind over upwind; the **background-corrected spot count** is downwind minus upwind.
(Gaps along a moving front do prefer downwind; the confirmation test of 2.2 is what guards against them.)

### 2.4 Issue hours and the fitted quantity

Issue hours t are the hourly issue hours of kcf-adaptive4 (eligible at lead h: fire age >= 3 h, forecast present).
For each issue hour, each cell c not in B(t) within 15 km of B(t), with distance x(c) and angle a(c) to downwind,
the outcome is

    Y(c, t, h) = 1 if c is spot-born and first marked in (t, t + h], else 0.

The quantity fitted in step 3 is P(Y = 1 | x, a, U, h), U = forecast gust. The road layer of step 4 is this
probability at each road cell.

### 2.5 Satellite detection limit

For each system, the share of spots it would miss is estimated two ways: (a) against the airborne infrared maps
(Dixie 2021, Rim 2013): detached burning polygons ahead of the main IR perimeter at least d_min away, and whether
VIIRS (within 6 h after the flight) or GOFER (within 1 h) marked them; reported by polygon area class; (b) the size
distribution of the spots found here, and the published detection limits gathered in step 1. Where (a) and (b)
disagree both are given.

## 3. Step 2: measurement

Report, by region (CA, KR, DET) and system: number of candidate and confirmed spots, number per 100 fire-hours,
distance distribution (median, 90th percentile, maximum), downwind / crosswind / upwind counts and the background
-corrected count, wind at the time, terrain (ridge crossings, elevation change), local hour, and the miss estimate
of 2.5. Everything with fire-bootstrap 95% intervals (1,000 resamples) where more than one fire contributes.

## 4. Step 3: fit

- **Empirical:** P by distance band (1-2, 2-3, 3-5, 5-8, 8-15 km), sector (downwind, cross, upwind), gust band
  (< 10, 10-15, 15-20, >= 20 m/s) and lead (1, 2, 5, 8 h), fire-weighted (each fire's cells weighted equally),
  with fire-bootstrap intervals.
- **Parametric (primary):** a complementary log-log model fitted on CA-DEV plus, for Korea, the training Korean
  fires of each leave-one-fire-out fold:

      cloglog P = b0 + b1 log x + b2 U + b3 U log x + b4 log h + b5 cos a

  (cloglog keeps the hazard reading: P = 1 - exp(-h^b4 exp(...)).) Fitted by fire-weighted likelihood; intervals by
  fire bootstrap. Calibration is checked on held-out fires by decile of predicted P.
- **Comparison with a published model:** the lognormal landing-distance model of Sardoy et al. (2008) and the
  Albini maximum spotting distance, with the parameters recommended in `LITERATURE.md` (written in step 1, before
  step 3 is run). Compared: the distance distribution of confirmed spots (conditional on a spot) against the
  published distribution at the observed wind (Kolmogorov-Smirnov distance and the share of spots beyond the
  published 99th percentile / Albini maximum).

## 5. Step 4: road layer

For each road cell and issue hour: P(lit before the main front within h) from the parametric fit with the issue
hour's forecast gust, ERA5 direction (ASSUMED as the forecast direction), and distance and angle from B(t).
Zones: P >= 0.10, >= 0.30, >= 0.50. Output as a raster beside the road layer; never a single hard line.

## 6. Step 5: tests (held-out fires; 5 h lead unless stated)

Margins compared at the same target: every combined model is calibrated so that its fire-weighted miss rate on its
training fires is 10% (the kcf-adaptive2 rule), then scored on held-out fires. Miss at (t, h): a cell that arrives in
(t, t + h] (by the kcf-margin reach rule, components farther than 5 km from K_t excluded) lies outside the flagged
region. FIXED = the fixed margin of kcf-adaptive4 (a constant buffer per lead). **FIXED+SPOT(p)** = a fixed buffer
c_h, recalibrated to a 10% miss rate with the layer present, united with every cell where P >= p. Primary p = 0.10;
p = 0.30 and 0.50 and p* (the p that gives the smallest training area at a 10% miss rate) are reported.
Flagged area = area of the buffer union the zone, capped at 60 km from B(t) (the kcf-adaptive4 cap).

1. **25 March 2025, 09 to 20 KST (12 issue hours, DET).** Hours held by FIXED+SPOT(0.10) against FIXED, and the mean
   flagged area. **Pass: at least 4 of 12 held** (more than the 3 of 12 of the best calibrated model of
   kcf-adaptive4, BASE-gust), with the mean flagged area reported against BASE-gust's 1,839 km2 and RULE's 11,481 km2.
   FIXED held 1 of 12 in kcf-adaptive4 (09 KST, reach 2.2 km against 2.5 km); the user's brief says none; the held
   count for FIXED is recomputed here and both are reported.
2. **Flagged area, Korea and California held-out.** Ratio of FIXED+SPOT(0.10) area to FIXED area at a 10% miss rate
   (read at exactly 10% held-out miss, as kcf-adaptive4 "area read at exactly 10% miss"), fire-bootstrap interval.
   **Pass: ratio at or below 1.00 in both regions** (the layer buys the same miss rate for no more area).
3. **Closures.** For each official (KEC) or reported closure on a road with cells in the roadlayer grid, find whether
   the main front (DET arrival, 375 m) had reached any cell of that road section at the closure time. For the
   closures the front had not reached: is any cell of the section inside the P >= 0.10 zone at the last issue hour
   before the closure (h = time to closure, rounded up, at most 8 h)? FIXED's buffer is reported the same way.
   **Pass: at least half of the unreached closures are inside the zone, and more of them than inside FIXED's buffer
   alone.** Closures are not caused only by fire on the road (smoke, precaution); a miss is not proof of error.
4. **Unexplained misses (kcf-adaptive4).** Take the misses kcf-adaptive4 left unexplained at 5 h (v_all = 0 in its
   attribution files: CA-DEV, CA-HELD, KR Choi hours, 25 March). (a) ORACLE ceiling: share of them that are held if
   spot-born cells (as observed here) are removed from the reach. (b) Method: share held if the margin with all
   four truths is united with the P >= 0.10 zone. **Pass: (b) lowers the unexplained share by at least a third
   (relative) in the pooled held-out set, with a fire-bootstrap interval excluding zero.** Where spots cannot be
   observed on those hours (the Choi product is a kriged later perimeter), the share is reported as not measurable,
   not as zero.

**Every failed test is stated as failed in RESULTS.md.** If test 1 or test 2 passes, the layer is added to
`product/wfg-roadlayer` as an option, off by default.

## 7. Statistics

Fire-bootstrap 95% intervals (1,000 resamples) for every rate and ratio. No correction for multiple comparisons.
25 March is one event on one fire: held hours are counts, not rates.

## 8. What is frozen and in what order

1. This protocol (commit before any spot is found).
2. LITERATURE.md (step 1) before step 3 is run.
3. Steps 2 and 3 on all data (the measurement is descriptive and uses no outcome of the tests); the fit uses CA-DEV
   and Korean training folds only.
4. The fit and its settings are frozen in a commit before any held-out California fire, held-out Korean fold or
   25 March is scored in step 5.

## 9. Amendments

### Amendment 1 (before any spot was found)

Seen: the code of `kcf-margin/score_gofer.py` and `kcf-adaptive4/build4.py`; the Choi `kr_events_21.csv` table
(fire list, VIIRS and Himawari input counts); download sizes. No detection had been processed. Changes:

1. California grid is EPSG:3310 (the kcf-margin / kcf-adaptive4 GOFER grid, 375 m), padded by 16 km so spots up to
   15 km beyond the final perimeter are on the grid, instead of EPSG:5070.
2. **Confirmation by a later look of the same system.** GOFER (GOES) perimeters lag VIIRS (kcf-adaptive4 found VIIRS
   saw fire before GOFER on 40% of missed hours), so a later GOFER perimeter filling the gap behind a VIIRS cluster
   does not show that the gap was unburned when VIIRS saw the cluster. A VIIRS candidate is confirmed only by a later
   VIIRS mark in the gap, a GOFER candidate by a later GOFER perimeter, an AHI candidate by a later AHI hour. The
   any-system count is recorded beside it.
3. **Recency.** A look is searched for spots only if the fire was seen by any look no more than 2 h earlier; clusters
   of other looks are labelled "unsearched" and added to the burned set. Between looks 3 to 12 h apart (VIIRS alone)
   an ordinary front moves more than d_min, and its new position would read as detached.
4. Clusters within d_min of an earlier separate fire (> 15 km) are part of that separate fire, not spots.
5. Also recorded for every spot: the distance to the front as seen in the same look (earlier front cells plus this
   look's front clusters), beside the protocol distance to B(t).

### Amendment 2 (step 5 implementation; items 1-4 written into the test code before any test was scored, item 5 after)

Seen before items 1-4: all of steps 2 and 3 (spot counts, the frozen fit and its held-out calibration, the 25 March
reach rows of the geometry pass, which reproduce kcf-adaptive4). Not seen: any miss rate, area or held hour of a
combined margin.

1. **Calibration sets for the margin c** follow kcf-adaptive4: CA-HELD is scored with c from CA-DEV; each Korean fire
   with c from the 28 California fires and the 11 other Korean fires; 25 March with c from the 28 California and 12
   Korean fires. The spot layer of a training fire uses that fire's own fit (California: the CA-DEV fit; Korean fires:
   their leave-one-out fit), not refits per fold: the Korean fold coefficients differ by less than 0.02 in every term.
2. **Thresholds.** Besides p = 0.10, 0.30, 0.50 and p*, the zone is scored at p = 0.03, 0.01, 0.003, 0.001, 0.0003 and
   0.0001, and p* is chosen among all of them on CA-DEV.
3. **Test 3 geometry.** Interchange coordinates are not in the repository offline (the Overture segment files are not
   present and no parquet reader can be installed here). A closed section is approximated by every cell of its route
   number inside the region's road grid (stated per closure in `derived/test3_closures.csv`). The closures used are
   the five official KEC closures of 25 March inside the detection product's span and the four reported local-road
   controls of kcf-roadcut that can be located by route number (RD9 to RD12).
4. **Test 4 (b)** unites the zone with kcf-adaptive4's issued margin q of the missed hour, not with the margin under all
   four truths: the all-truth margin is not stored in its attribution files.
5. **After the results: a vacuous pass is not a pass.** At p = 0.10 the zone contains no cell on any fire-hour, so
   FIXED+SPOT(0.10) is FIXED and its area ratio is 1.000 by construction. The pass rule of test 2 ("at or below 1.00")
   is met only in this empty sense. RESULTS.md reports it as **not passed** and gives the number, and the layer is not
   added to `product/wfg-roadlayer` on the strength of it. This reading was chosen after seeing the result.
