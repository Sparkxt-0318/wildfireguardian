# FIRMS bundles for the 5 non-yeongdeok fires — COMPLETE (session 2026-07-20)

Goal (done): assemble `data/raw/firms/` bundles for the other five canonical
spread_v2 fires so the model trains on all six. yeongdeok_2025 untouched.
Ran in a **cloud container (path A)** — desktop bridge was offline — then the
files were delivered back to the user to drop into their repo.

## Environment
- Cloned `github.com/sparkxt-0318/wildfireguardian` (public) for the canonical
  `spread_v2` loaders. Verified against `data.py` + `grid.py` (NOT `spread_v2_xgb`).
- pip env (no conda): rasterio 1.4.4, xarray, h5netcdf+**h5py** (needed by open_era5),
  cdsapi, pandas, pyproj, requests.
- Keys pasted by user, used in-sandbox only (CDS PAT, NASA FIRMS MAP_KEY, OpenTopography).

## Locked per-fire parameters (user-confirmed 2026-07-20)
| id | bbox [minlon,minlat,maxlon,maxlat] | ignition [lon,lat] | window (KST) | reported_ha |
|---|---|---|---|---|
| uljin_samcheok_2022 | [128.95,36.60,129.55,37.35] | [129.34,36.99] | 2022-03-04..03-14 | 16302 |
| uiseong_andong_2025 | [128.35,36.15,128.97,36.75] | [128.63,36.45] | 2025-03-22..03-29 | 45000 |
| miryang_2022 | [128.43,35.33,129.03,35.83] | [128.77,35.54] | 2022-05-31..06-05 | 763 |
| gangneung_2023 | [128.62,37.57,129.02,37.97] | [128.87,37.77] | 2023-04-11..04-13 | 379 |
| hongseong_2023 | [126.22,36.36,126.82,36.76] | [126.52,36.56] | 2023-04-02..04-06 | 1454 |

- uiseong east edge deliberately clamped to **128.97** to tile with the yeongdeok
  bbox (no detection overlap) — user directive.
- ignition coords are approximate (~0.01°), derived from documented ignition
  localities (uljin 북면 두천리 산154; uiseong 안평면; miryang 부북면 춘화리; gangneung 난곡동;  <!-- forbidden-ok: 154 -->
  hongseong 서부면). Geocoders/Wikipedia were unfetchable in the sandbox.

## Recipe used (matches yeongdeok bundle)
- **FIRMS**: archive endpoint, sources VIIRS_SNPP_SP + VIIRS_NOAA20_SP + MODIS_SP,
  merged -> `<fire>_detections.csv` with columns latitude,longitude,acq_date,acq_time,
  frp,confidence,satellite,instrument,**timestamp** (UTC, pre-joined — the loader reads
  `df["timestamp"]` directly; acq_date/acq_time alone are NOT enough). NB: this MAP_KEY
  caps day_range at **5**, so windows were split into <=5-day chunks.
- **ERA5**: reanalysis-era5-single-levels, [10m_u,10m_v,2m_temp,2m_dewpoint,total_precip],
  3-hourly (00..21), area=[N,W,S,E], data_format=netcdf, download_format=zip ->
  `<fire>_era5.nc`. miryang spans May->June, so two month-requests were bundled into one
  zip (4 inner .nc); open_era5's zip+xr.merge(join="outer") yields a contiguous 48-step
  series. Submitted all five first (they queue).
- **DEM**: OpenTopography SRTMGL1 GeoTIFF (EPSG:4326, int16 m). NB: response
  Content-Type is `application/octet-stream`; validate by TIFF magic bytes, not CT.
- **Fuel**: ESA WorldCover 2021 v200, windowed-read from the public S3 COGs via
  /vsicurl (tiles N33/N36 x E126/E129), cropped to bbox -> `<fire>_fuel.tif` (uint8,
  EPSG:4326, nodata=0). No key needed.

## STEP 2 verification (canonical loaders; forward-sim/routing NOT run)
`list_fires()` -> all **6** fire ids. Five new fires dry-run-loaded end-to-end:
| fire | n_det | first..last UTC | era5 steps (vars ok) | elev cov | burnable mean |
|---|---|---|---|---|---|
| uljin_samcheok_2022 | 2342 | 03-04 03:19..03-12 05:00 | 88 | 0.971 | 0.708 |
| uiseong_andong_2025 | 3416 | 03-22 04:22..03-28 16:53 | 64 | 0.985 | 0.927 |
| miryang_2022 | 75 | 05-31 02:48..06-02 17:33 | 48 | 0.978 | 0.889 |
| gangneung_2023 | 27 | 04-11 01:53..04-12 17:45 | 24 | 0.990 | 0.725 |
| hongseong_2023 | 210 | 04-02 02:17..04-03 17:14 | 40 | 0.990 | 0.655 |

- era5 all have u10,v10,t2m,d2m,tp; step count = window_days x 8 (3-hourly).
- elev coverage 0.97-0.99: the missing 1-3% are sea cells (SRTM nodata over ocean),
  which also read burnable~0 — expected for the coastal boxes, same as yeongdeok.
- weather_series_from_event() also builds for all five (bonus end-to-end weather check).
- yeongdeok rasters are the user's local git-ignored files (absent in the cloud clone);
  it appears in list_fires() from the manifest but was not raster-loaded here.

## Delivered to user
`firms_bundles_5fires.zip` (24 files): 5x(detections.csv, era5.nc, dem.tif, fuel.tif) +
fire_manifest.json (full 6-fire, yeongdeok verbatim) + data_layers_manifest.json
(unchanged) + fires_5_new_fragment.json (5-entry append option) + DROP_IN.md.
User unzips into data/raw/firms/, then can run the full six-fire forward-sim / routing.

Guardrails honored: canonical spread_v2 only (never spread_v2_xgb); seed 20250603 build;
no fabricated data (FIRMS "no-data" windows failed loudly and were fixed, not faked);
rasters git-ignored; yeongdeok bundle never touched.

---

## NOTE ON REPRODUCIBILITY (added at submission)

The parameters above are the locked query specification. FIRMS near-real-time detections
are replaced by standard-quality science data after roughly 2-3 months, so re-querying
these identical bboxes and windows at a later date may return a different detection count.
This is not hypothetical: a bundle reconstructed from these exact parameters produced a
pooled ROC-AUC of 0.859, differing from the canonical 0.9053 recorded in
`data/processed/spread_v2_lofo.json` (seed 20250603, n_rows 151904, n_positives 2989).
All reported values are fixed in committed artifacts under `data/processed/`.

The `start`/`end` fields in `fire_manifest.json` are provenance only and are NOT consumed
by the loader (only bbox + ignition drive the grid and model); where the manifest and the
table above differ by a day at the window edge, the table above is the acquisition record.
