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

(none)
