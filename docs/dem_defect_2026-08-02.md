# The Uljin-Samcheok DEM was filling the East Sea with a ramp

**Found 2026-08-02, while re-acquiring the DEM to close a coverage gap.**
Artifacts: [`dem_acquisition.json`](../data/processed/dem_acquisition.json),
snapshots `srtm-dem_*.tif`.

The re-acquisition was requested to fix a *coverage* problem. It uncovered a
*content* problem in the same raster, and the content problem is the larger of
the two.

---

## 1. What was wrong

`data/raw/firms_data/uljin_samcheok_2022_dem.tif`, as it stood before
2026-08-02, agreed with the freshly fetched SRTMGL1 product **exactly over
land** and diverged progressively **over the East Sea**:

| longitude band | old median elevation | new median | median difference |
|---|---:|---:|---:|
| 129.120 – 129.176 | 614.5 m | 614.0 m | **0.0 m** |
| 129.178 – 129.234 | 531.0 m | 532.0 m | **0.0 m** |
| 129.235 – 129.291 | 294.0 m | 293.0 m | **0.0 m** |
| 129.293 – 129.349 | 120.0 m | 119.0 m | +1.0 m |
| 129.351 – 129.407 | −30.0 m | 0.0 m | +31.0 m |
| 129.409 – 129.465 | −71.0 m | 0.0 m | +71.0 m |
| 129.466 – 129.522 | −116.0 m | 0.0 m | +116.0 m |
| 129.524 – 129.580 | −180.0 m | 0.0 m | +180.0 m |

**28,076 of 57,600 sampled cells — 49 % of the raster — carried a negative
elevation**, reaching **−497 m**, on a linear ramp descending away from the
coastline. The re-fetched raster has exactly one sample below zero (−1 m).

This is a void-fill artifact: SRTM has no data over water, and whatever produced
the original file interpolated across the ocean from the coastline outward
instead of leaving it as nodata or clamping it to sea level.

Uiseong-Andong is inland and has no such defect: over its whole footprint the
old and new rasters agree with a **median difference of 0 m** and a mean of
−0.13 m. Its only problem was the missing southern strip.

## 2. Two other differences, both benign

* **Registration.** The old rasters' pixel *edges* sat on round bbox values
  (129.10000); the new ones sit half a pixel off (129.0798611), which is the
  native SRTM pixel-centre convention. The old files had therefore been
  resampled onto a rounded box — consistent with their `float32` dtype against
  the new `int16`. This shifts sampled elevations by a fraction of a pixel and
  is visible as a ±7 m scatter with zero median in Uiseong-Andong.
* **Extent.** The new rasters are larger by design; see
  [`multi_region.md`](multi_region.md) §4.

## 3. What it contaminated

### Directly: the two regions' hazard fields

`spread_v2` reprojects the DEM onto the simulation grid and derives elevation
and slope features from it. Uljin-Samcheok's simulation grid includes the sea,
so ~half its cells carried a fictitious descending slope.

### Indirectly, and this is the part that matters: **every other fire's model**

`run_forward_sim_region.py` builds **one shared feature dataset over all fires**
and then fits leave-the-target-fire-out. Uljin-Samcheok is in the training set
for every other fire. Its ramp-filled sea was therefore training data for every
model in the set.

That is why fixing Uiseong-Andong's DEM — whose own defect was a small missing
strip far from its fire — moved its predicted envelope by **+38 %** (95 → 131
core cells) and its future-aware-only share from **3.53 % to 24.73 %**. The
change did not come from Uiseong-Andong's own terrain. It came from the
training set.

### ⚠ Not yet assessed: `spread_v2_lofo.json`

`data/processed/spread_v2_lofo.json` — the artifact behind the headline
mean-of-folds AUC — is built over exactly this six-fire set:

```
gangneung_2023, hongseong_2023, miryang_2022,
uiseong_andong_2025, uljin_samcheok_2022, yeongdeok_2025
```

so **every fold was trained on the ramp-filled Uljin-Samcheok features**,
including the Yeongdeok fold.

**Nothing has been re-run.** That artifact is committed Round-2 evidence and is
protected by `HANDOFF_ROUND3.md` §5.2; re-running it is a deliberate decision
with consequences for figures the submission already cites, not a side effect of
an analysis session. It is recorded as an open item, with the honest statement
of scope: the defect is in a *training input*, so its effect on the AUC is
unmeasured and could be in either direction.

The same caveat applies to `routing_demo.npz` and every Yeongdeok number derived
from it.

## 4. What was done

`scripts/acquire_region_dem.py` re-fetched both regions from the OpenTopography
Global DEM API (`demtype=SRTMGL1`, GeoTIFF, EPSG:4326) on the union of walk
bbox, simulation canvas and previous raster, validated 1-arc-second resolution
and full coverage before installing, and snapshotted the bytes into
`data/snapshots/` as `srtm-dem_*.tif`.

Yeongdeok's DEM was **not** re-acquired — it is an input to committed artifacts
(`HANDOFF_ROUND3.md` §5.4). It *was* snapshotted, so its bytes are now
preserved rather than merely digested.

`make snapshot-verify` now reports **DRIFTED** for the two replaced rasters
against their old digest-only `firms-bundle` records. That is the drift detector
working: the old digest describes the file that used to be there, the new
`srtm-dem_*` entry describes the one that is there now, and both records are
true of their own moment.

## 5. Rules

1. **Never quote a pre-2026-08-02 Uljin-Samcheok elevation, slope or hazard
   figure** without saying that its DEM filled the sea with a ramp to −497 m.
2. **Never assume a DEM defect is local to its own region.** The training set is
   shared; this one moved a different region's headline by a factor of seven.
3. A DEM whose minimum is a large negative number over a coastal footprint is
   reporting a void fill, not bathymetry. Check `min` before trusting a raster.
