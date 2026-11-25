# PROTOCOL: exposure fields as road-blocking times (Fish Creek)

Written and committed before any result. Nothing below may be changed after a result is seen; a change goes in an
amendment section at the end, dated, with the reason, before the result it affects is computed.

This task replaces the earlier "no new runs" instruction for this task alone.

## 1. Question

When the exposure fields (radiant heat, CO, visibility) block road cells, how much earlier than fire arrival alone
does a road become impassable, and how much does each origin's last safe departure time move?

## 2. Inputs (unchanged)

| input | what | where |
|---|---|---|
| exposure pipeline | `wildfire/exposure_calculations.py` with the next-hour and later-hour orchestrators, run with the settings of the saved example `demonstration/flame_danger/physical_exposure/` (`report.json`, `activity_explanation.json`) | forecast and physics workspace `/Users/jp/Desktop/wildfire` (read only) |
| case | WY-BTF-002416_FishCreek, cutoff 2024-08-23T00:00:00Z (timeline index 48), 375 m source/receiver grid, the grid's own CRS | same |
| settings | exactly those of the saved example: Scott–Burgan L2 live moisture (herbaceous 60 %, woody 90 %), Gaussian arrival model with the supplied kriging standard deviations conditioned on the reconstructed burned footprint, visibility limit 10 m, the example's time bins, Monte Carlo sample count and seed, unresolved crown and ember contributions left unresolved, no ember-caused spread | same |
| hours | h = 0, 1, …, H − 1, consecutive whole hours from the cutoff, H = as many as the saved forecast supports, at least 6. If the saved forecast supports fewer than 6, that is reported and the run stops there | |
| fire arrival | the per-cell fire-arrival raster the road layer reads today (fire arrival plus the road layer's existing handling; nothing added or removed) | the saved forecast, exported in the road layer's format |
| roads | OpenStreetMap roads for the Fish Creek grid extent, snapshot time recorded | Overpass API / Geofabrik |
| road layer | `product/wfg-roadlayer` on Main (backward pass, last safe departure per origin), unchanged settings | this repository |

No model setting is changed. If the pipeline cannot run for a given hour, that hour is reported as missing and no
value is filled in.

## 3. Blocking rule

All times are minutes from the issue time (the cutoff). Hour h covers [60h, 60h + 60) min. A cell is **blocked** from
the start of the first hour h in which any criterion below holds (time resolution: one hour; the start of the hour is
used, so a block is never reported later than the hour it occurs in). A blocked cell stays blocked to the end of the
horizon (the road layer's residents' default: no reopening).

### (a) Radiant heat

The hour's largest binwise incident radiant flux q″r (the pipeline's weighted field, eq. 2 of the session summary,
in kW/m²) at the receiver cell:

| audience | threshold | source |
|---|---|---|
| residents | q″r ≥ **2.5 kW/m²** | tenability limit for unprotected skin: below it tolerable for 30 min or longer, above it severe pain within seconds (Purser & McAllister 2016, SFPE Handbook ch. 63; see §5) |
| responders | q″r ≥ **7.0 kW/m²** | Butler and Cohen 1998: exposed skin reaches a second-degree burn in under 90 s (see §5; the meaning is Butler's, not "protective clothing") |

Where the pipeline marks thermal inputs unresolved (`thermal_inputs_resolved` False), the known contribution is a
lower bound: the cell is blocked if the known contribution alone meets the threshold; otherwise it is not blocked and
is counted separately as "unresolved, not blocked".

If the pipeline saves only the accumulated thermal energy E (J/m²) and not binwise flux, the hour's mean flux E/3600 s
is used, which can only be lower than the binwise peak; this is then stated as a lower bound in every output.

### (b) Carbon monoxide, AEGL-2 (final)

Binwise CO concentration is converted from mg/m³ to ppm with the AEGL document's own factor, 1 ppm = 1.145 mg/m³
(NRC 2010, vol. 8). Running
means over windows of 10, 30 and 60 min are taken along the time bins (a window may cross an hour boundary; it
counts for the hour in which it ends). The criterion holds if any window mean meets the AEGL-2 value for its length:

| averaging time | AEGL-2 |
|---|---|
| 10 min | **420 ppm** |
| 30 min | **150 ppm** |
| 60 min | **83 ppm** |

If the pipeline saves only the hourly mean, only the 60 min check is made, and the 10 and 30 min checks are reported
as "not computable from the saved output" (an hourly mean is a lower bound on the largest 10 or 30 min mean inside
it, so this can only miss blocks, never add them).

### (c) Visibility (ASSUMPTION)

The criterion holds if the pipeline's sampled probability that visibility falls to 10 m or less during the hour
(eq. 4 of the session summary) is **at least 0.5**.

**Assumption, labelled in every output:** 10 m is a building-egress reference (see §5), not a driving-visibility
standard, and the 0.5 probability level is our choice, not a published value. The run is repeated with 0.1 and 0.9
as a sensitivity check.

### PM2.5

Reported (hourly mean, largest cell value, cells above zero), **never used to block**.

### Audiences

* residents: (a) at 2.5 kW/m², (b), (c)
* responders: (a) at 7.0 kW/m², (b), (c)

The CO and visibility criteria are the same for both audiences.

## 4. Outputs

In `talk_handoff/routing_link/`:

* per audience, a raster of the **first blocked time from exposure** (minutes from issue time; +Inf where no
  criterion holds within the horizon), and a raster of the **earlier of that and fire arrival**;
* both in the format of `product/wfg-roadlayer/INTERFACE.md`: one-band float32 GeoTIFF, minutes from the issue time,
  ≤ 0 = blocked at issue, +Inf = not blocked inside the horizon, NaN = not computed, EPSG code in the GeoKeys, GDAL
  metadata `WFG_ISSUE_TIME`, `WFG_HORIZON_MIN` (= 60 H), `WFG_UNITS=minutes`, `WFG_SOURCE`;
* the visibility sensitivity rasters at 0.1 and 0.9.

## 5. Threshold sources

Full citations, what each source says the value means, and what could not be opened are in `SOURCES.md` (this
folder, same commit). Short form:

| value | source | primary read? |
|---|---|---|
| CO AEGL-2 420 / 150 / 83 ppm (10 / 30 / 60 min), final | NRC (2010) *AEGLs for Selected Airborne Chemicals* vol. 8, App. 2, doi:10.17226/12770; US EPA AEGL page | yes, both; values match |
| 2.5 kW/m² | Purser & McAllister (2016) SFPE Handbook 5th ed. ch. 63, doi:10.1007/978-1-4939-2565-0_63 | no (paywalled); value confirmed in Engineers Australia (2014) and SCDF (2022) |
| 7.0 kW/m² | Butler & Cohen (1998) *IJWF* 8(2):73–77, doi:10.1071/WF9980073 | no (not reachable); value confirmed in Butler (2014) *IJWF* 23:295–308 |
| visibility 10 m | Purser & McAllister (2016), large-enclosure egress criterion; not Jin (1978) | no (paywalled); confirmed in Gager & Dominguez (2016) and Engineers Australia (2014) |
| p ≥ 0.5 | our choice | n/a |

No number was changed by the check.

## 6. Road-layer runs

The road layer is run on Fish Creek with OpenStreetMap roads, at least twice per audience:

1. fire arrival only;
2. fire arrival plus exposure (the "earlier of" raster).

Origins: populated places and shelters from OpenStreetMap inside the grid extent. If there are none, road junctions
are the origins and the points where roads leave the map edge are the exits; this is stated in every output.

## 7. What is reported (RESULTS.md), each number with its sample size

1. Cell-hours blocked by each criterion (radiant 2.5, radiant 7.0, CO 10/30/60 min, visibility at 0.5), out of the
   number of cell-hours computed.
2. Cell-hours blocked by exposure that fire arrival had not already blocked.
3. Origins whose last safe departure changes, out of the number of origins; the change in minutes (median, largest).
4. Items 1–3 again under visibility levels 0.1 and 0.9.
5. PM2.5 summary (not a block).

A zero is reported as zero.

## 8. Figure

One figure: the map of cells blocked by fire alone and the cells exposure adds, with the roads. Colours: ink
#1A1A1A, grey #6B6B6B, blue #2F5D8A with light tints, deep red #8A362F; transparent background; no title inside. A
road is "blocked", never "closes".

## 9. Limits stated with every result

One fire; uncalibrated exposure; thresholds made for buildings or workplaces, not for people in vehicles; no Korean
case, because Korea has no fuel maps.

## Amendments

### Amendment 1 (24 Nov 2026, before any result)

Written after the pipeline arrived and before it was run for this task. Nothing below changes a threshold, an
audience, a criterion or a model setting; it fixes choices the protocol left open.

1. **Where the pipeline came from.** The user supplied `/Users/jp/Desktop/wildfire4.zip` (sha256
   `cfaa4dace7032404a8c1ed7bba866319a4ebe0d7257df0b623ed89585bd35a57`), a copy of the forecast and physics workspace
   with the 23 Nov 2026 code. Only the code, the Fish Creek data, the checkpoint and the saved example were unpacked,
   into a scratch folder outside both repositories; nothing in the zip or in `/Users/jp/Desktop/wildfire` is written.
   File hashes: `exposure_calculations.py` 4c5c861c…, `monte_carlo_hazards.py` dca25f75…, `physical_exposure.py`
   f7a55209…, `physical_exposure_example.py` 05708182…, saved `mapping.npz` c0a73a39…, checkpoint c651f672… (equal to
   the `checkpoint_sha256` in the saved `report.json`). The workspace's own Python environment inside the zip cannot be
   loaded here (macOS refuses its unsigned libraries after download), so the pinned versions from its
   `pyproject.toml` (Python 3.12, numpy 1.26.4, torch 2.5.1, pyrothermel 0.1.4, …) are installed fresh.
2. **Six hours.** The saved example covers one hour, [0, 1] h after the cutoff. Hours h = 0 … 5 use the pipeline's
   own later-hour path (README "Later hours"; `predict_cumulative(..., retain_trajectories=True)` with hours 1 … 6,
   then `calculate_hazards(hours_later=h)`), with the example's settings: 1024 samples, seed 20261122, 60 s time bins,
   Scott–Burgan L2, Gaussian arrival uncertainty, `boundary="zero"`, `missing_burned_area="unburned"`,
   `activity_mode="probability_map"`, the example's physical factory (same fuel load, flame height, parameters, front
   direction, `unresolved_heat_policy="bounds"`). The later-hour path asks for an explicit within-hour ignition
   timing; `uniform_within_step` is used because the one-hour path's own model is "uniform conditional first ignition
   in the forecast interval". The timing seed is the example's seed. The later-hour weather is the cutoff weather held
   constant (the pipeline's behaviour without an `environmental_forecast`); this is a limit, stated in RESULTS.md.
   Check reported: hour 0 from this path against the saved one-hour example.
3. **Binwise radiant flux and CO.** The saved outputs are hourly totals. The 60 s bin fields are read from the same
   probability-weighted superposition the pipeline integrates (`fields_from_activity` on the identical weights and
   bins, inside `weighted_exposure_integrals`); nothing is recomputed differently. Check reported: their time
   integrals equal the pipeline's hourly radiant energy and mean CO.
4. **Radiant criterion uses radiant flux only** (the threshold is an incident radiant flux), not radiant plus
   convective energy. Unresolved = the pipeline's unresolved radiant inputs; the known part is a lower bound (§3a).
   Binwise CO is "not computable" where the pipeline marks CO inputs unresolved.
5. **Visibility.** The probability is the pipeline's `visibility_danger_probability`. Where the pipeline leaves it
   undefined (unknown PM inputs), its `visibility_probability_lower` is used as a lower bound, and the number of such
   cell-hours is reported.
6. **Fire arrival from the forecast.** The forecast is an ensemble of 1024 retained paths; INTERFACE.md says the
   exporter reduces an ensemble to one arrival, e.g. the earliest member. Main run: **earliest member**, a cell's
   arrival is the start of the first hour in which any retained path burns it (60(k − 1) min for first-burn step k);
   cells burned at the cutoff are 0 (burning or burnt at issue); cells no path reaches within 6 h are not reached.
   Sensitivity, reported beside it: the start of the first hour by which at least half the paths have burned the cell.
   Both are cut to the 6 h exposure horizon.

### Amendment 2 (25 Nov 2026, AFTER the first results were seen)

**This amendment is made after the first results (RESULTS.md, commit 0dad5b82) were seen.** Those results showed
that radiant heat and CO were compared with their thresholds as probability-weighted expected fields: each source
cell's contribution was multiplied by its probability of burning, and no source weight exceeded 0.14. A limit made for
a person beside a real flame was therefore tested against a diluted average, while visibility was already evaluated
in each sampled path. This amendment makes heat and CO consistent with visibility. It was asked for by the user after
reading those results. It changes no threshold, no source, no audience, no fire reading, no road and no case. Every
v1 file and result is kept unchanged; the new results go to `RESULTS_v2.md`, `RESULTS_all_v2.pdf` and new folders.
The probability levels below were fixed before any per-path result was computed and are not tuned afterwards.

1. **Per-path exposure.** For each of the 1,024 retained paths of the v1 forecast (same spread run, seed 20261122,
   same initial activity, same physical factory, same 60 s bins, hours 0–5), the 60 s radiant flux and CO fields are
   computed from the cells burning in that path only, through the pipeline's own `fields_from_activity` (same
   kernels: same burn duration, flame and plume models). A source cell's weight in a bin is the fraction of that
   60 s bin during which it burns in that path: 1 in every minute it burns throughout, 0 when it does not burn, and a
   fraction only in its ignition and extinction minutes. This is the binary path's own time mean, the same
   quantity the pipeline's probability map averages, so the mean over paths estimates the v1 fields. Each path's
   ignition time inside its hour, whether a cell burning at the cutoff is still flaming, and its remaining lifetime
   are the pipeline's own draws for that path (the same `timing_seed` streams that produced v1 visibility), not new
   draws.
2. **Criteria per path.** Per path, cell and minute: radiant flux ≥ 2.5 kW/m² (residents) or ≥ 7.0 kW/m²
   (responders) in that minute; CO trailing means over 10, 30 and 60 min ending at the end of that minute ≥ 420,
   150, 83 ppm (only windows that start at or after the cutoff; 1 ppm = 1.145 mg/m³). Visibility is unchanged: the
   pipeline's per-path event "visibility ≤ 10 m at some time in the hour", so its share is the v1 probability and it
   holds for every minute of that hour. For each criterion, cell and minute the **share of the 1,024 paths** in which
   it holds is recorded.
3. **Blocking rule.** A criterion blocks a cell from the first minute its share reaches the level: **0.5 (main)**;
   sensitivity 0.1, 0.9 and **"any path"** (share > 0). Each criterion is tested separately; a cell is blocked by
   exposure from the earliest minute any criterion blocks it (radiant at the audience's threshold, any CO window,
   visibility), and in the road layer from the earlier of that minute and fire arrival. Radiant and CO block from the
   start of the minute; visibility, defined per hour, from the start of its hour (as in v1).
4. **Pairing with fire arrival.** Main: share 0.5 with the half-of-paths fire reading. Paired sensitivity: "any path"
   with the earliest-path fire reading. All four levels are also run with both fire readings and reported as a grid.
5. **Number of paths.** All 1,024 (a timing probe on random weights, before any criterion was evaluated, gave about
   1 s per 32 paths per hour). If that fails, a random subset of 128 paths with a recorded seed is used and said so
   in NEEDS.md. Sampling error is reported either way: Wilson 95 % interval of the share at each blocked cell.
6. **Checks, reported before the results.** (a) One path as a probability-1 weight map through the pipeline's own
   `weighted_exposure_integrals` gives the same 60 s fields and hourly integrals as the per-path computation for that
   path. (b) The mean over paths of the per-path weights and of the 60 s radiant and CO fields reproduces the v1
   active-fire probabilities and v1 fields within sampling error (difference against 3 standard errors of the path
   mean; largest relative difference of hourly totals). (c) The retained paths are identical to v1 (both fire-arrival
   rasters rebuilt and compared). (d) The synthetic tests still pass, with new tests for the per-path rule.
7. **Distance to the flame.** For the main setting, for each road cell blocked by radiant heat or CO, the distance
   from that cell's centre to the nearest cell burning in the same path and minute (0 if the cell itself burns),
   over the paths in which the criterion holds at the cell's first blocked minute: median, smallest and largest. So
   that the question is answered even if no road cell is blocked, the same distances are reported for all cells
   blocked by radiant heat or CO at each level.
8. **Reported, v1 beside v2:** cell-hours blocked per criterion (n = 45,114), largest value reached (largest in any
   path, and largest share), road cells blocked (n = 1,293), origins whose last safe departure changes and by how
   many minutes (n = 350 routed), for residents and responders, at each level and fire reading. One figure in the
   v1 style (main setting).

### Amendment 3 (25 Nov 2026, safety-zone figure; written before the figure's data were computed)

Asked for by the user after Amendment 2. It adds one figure and one routing comparison; it changes nothing in v1 or
in the Amendment 2 results. Thresholds unchanged (2.5 kW/m² residents, 7.0 kW/m² responders).

1. **One path, one minute, chosen by a fixed rule, not by looking.** Path: among the 1,024 retained paths, the one
   whose number of burned cells at the end of hour 6 is closest to the median (lowest index on a tie). Minute: the
   minute in hours 0–5 in which that path has the most cells burning (earliest on a tie).
2. **Zone.** That path's own 60 s radiant flux (Amendment 2 item 1, weight 1 for a cell burning through the minute),
   at that minute: zone ≥ 2.5 kW/m² and zone ≥ 7.0 kW/m², cellwise on the 375 m grid. These are the peak values in
   that path at that place and time, not averages over paths. A road piece is inside a zone if any cell it crosses is
   in the zone.
3. **Routing.** In the same path, over the full six hours: fire arrival alone = that path's own ignition minute of
   each cell (0 for cells burning or burnt at the cutoff, as in v1); fire plus safety zone = the earlier of that and
   the first minute the path's radiant flux at the cell reaches the audience's threshold. Reported for residents and
   responders: road cells blocked, origins whose last safe departure changes (n = routed origins) and by how many
   minutes.
4. One figure: the zone map (left) and the routing change (right), v1 style (five colours, transparent, no title,
   "blocked", never "closes"). It shows one possible fire, not the forecast.

### Amendment 4 (25 Nov 2026, AFTER the Amendment 3 zone was seen to be empty)

**Written after seeing that the Amendment 3 zone is empty**, and after a diagnostic (`diag_radiant.py`) showed why:
the pipeline draws each burning cell's flame as one line front through the cell centre (median width 379 m, flame
height about 3 m, median emissive power 59 kW/m²), receivers sit only at cell centres, and a cell's own receiver gets
0 by design ("direct contact is covered by the footprint event"). The nearest receiver that counts is 375 m away, where
the largest flux is 0.22 kW/m². On the 375 m grid neither 2.5 nor 7.0 kW/m² can be reached anywhere. The Amendment 3
result (empty zone, no routing change) is kept and reported. This amendment adds a finer evaluation of the **same**
flame fronts; thresholds, path, minute and roads are unchanged.

1. **Receivers at 5 m.** For the Amendment 3 path and minute, the pipeline's own flame-front objects (built inside its
   physical model, recorded unchanged: position, width, height, emissive power, terrain) are evaluated at receivers
   1.7 m above the ground of the containing cell, on a 5 m raster around the burning cells and at points every 5 m
   along every road piece within 1 km of a burning cell. Flux = transmissivity × power × view factor, summed over the
   burning fronts with the Amendment 2 weights, exactly as the pipeline's kernel does, only at more receivers. Receivers
   on or behind a front's line (undefined in the pipeline) are left out, as the pipeline leaves them out.
2. **Zone and road pieces.** Zone ≥ 2.5 and ≥ 7.0 kW/m² at that minute; a road piece is inside if any of its 5 m
   points is. Reported: largest distance from a front line at which each threshold is reached, road pieces and road
   length inside each zone.
3. **Routing in the same path.** A road cell is blocked from the first minute any 5 m point on a road piece inside
   that cell reaches the audience's threshold; combined with the path's own fire arrival by the earlier time, exactly
   as in Amendment 3 item 3. Reported beside Amendment 3: road cells blocked, origins whose last safe departure
   changes and by how many minutes.
4. The figure shows the 5 m zone (left) and both routing comparisons (right); its caption says the zone uses the
   pipeline's flame fronts at receivers finer than the grid the pipeline runs on.

### Amendment 5 (25 Nov 2026, AFTER the Amendment 4 zone was seen)

**Written after seeing the Amendment 4 zone.** It covered only the middle stretch of each 380 m flame front. The
reason, checked on the eight fronts burning at the chosen minute: the pipeline puts each front's base on the cell's
terrain plane, so the base rises or falls by up to 64 m across the front, while Amendment 4 put every 5 m receiver at
one height per 375 m cell (the cell's ground + 1.7 m). Away from the middle the receivers therefore sat metres above
or below a flame 2–3.6 m tall. This is an artefact of the 5 m extension, not of the pipeline (its receivers are at cell
centres, where the two heights agree). Amendment 4 results are kept and reported.

1. **Receivers on the terrain plane.** Same as Amendment 4, except that a 5 m receiver's height is the containing
   cell's ground + the pipeline's own terrain gradient of that cell × the horizontal offset from the cell centre +
   1.7 m: the same plane the pipeline uses for the flame base.
2. Same zone, road-piece, distance and routing outputs as Amendment 4, reported beside them. The figure's left panel
   shows this zone; both distances are given.

### Amendment 6 (25 Nov 2026, safety zone on the paths where CO blocks roads; written before computing it)

Asked for by the user after v2 showed that CO blocks road cells only in single paths. Thresholds, receivers and roads
unchanged.

1. **Paths.** Every retained path in which some CO criterion (10, 30 or 60 min AEGL-2, per path as in Amendment 2)
   holds at some road cell at some minute of hours 0–5. Their number is reported.
2. **Safety zone in each path.** As Amendment 5: the pipeline's own flame fronts burning in that path, receivers every
   5 m along every road piece within 1 km of a front that burns in that path, 1.7 m above the cell's terrain plane,
   all 360 minutes. A road cell is blocked by the zone from the first minute a 5 m point on a road piece in it reaches
   2.5 kW/m² (residents) or 7.0 kW/m² (responders). For each such point, the distance to the nearest front line
   burning in that minute is reported. The largest 375 m radiant flux in the path is reported too.
3. **Routing in each path.** (i) the path's own fire arrival alone (Amendment 3 item 3); (ii) plus the safety zone;
   (iii) plus CO in that path (each cell blocked from the first minute any CO window holds there in that path);
   (iv) plus CO and the safety zone. Reported per path and in total: road cells blocked, road pieces inside the zone,
   origins whose last safe departure changes against (i) and by how many minutes, and what the zone adds to CO
   ((iv) against (iii)). Where two runs give the same closures on every road cell, the road layer's answer is the same
   by construction and is reused, and that is said.
