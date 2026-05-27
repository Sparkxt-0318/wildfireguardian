# `fire_detection` — satellite hotspot ingestion

**Status**: scaffold only.

**Purpose**: pull near-real-time and historical active-fire detections from
NASA FIRMS (VIIRS S-NPP / NOAA-20 at 375 m, MODIS Aqua/Terra at 1 km),
deduplicate cross-sensor and cross-overpass redundancy, and emit a clean
table of candidate ignitions usable by the spread model.

**Inputs**: a bounding box (Korea Peninsula by default), a time window, and a
NASA FIRMS MAP_KEY (loaded from `.env`).

**Outputs**: `geopandas.GeoDataFrame` of ignition candidates with columns
`(lat, lon, acq_datetime_utc, satellite, confidence, frp_mw)`, deduplicated
to one record per spatial cluster per 1 h.

**Algorithmic basis**: the FIRMS active fire detection thresholds use a
contextual brightness-temperature test (Giglio et al. 2003 for MODIS;
Schroeder et al. 2014 for VIIRS 375 m). We do not re-implement the detection
algorithm itself; we consume the published per-pixel product and filter on
confidence ≥ "nominal".
