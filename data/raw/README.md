# `data/raw/` — FIRMS / ERA5 / DEM acquisition parameters

The raw FIRMS/ERA5/DEM bundle that the `spread_v2` model trains on is **git-ignored**
and does not ship in this repository. This file records the exact query parameters so the
bundle can be rebuilt. Every value below is sourced solely from two committed provenance files:

- `docs/data_provenance/fire_manifest.json` — all six canonical fires (the loader manifest)
- `docs/data_provenance/claude_firms_bundle_5fires_2026-07-20.md` — acquisition record for the
  five non-yeongdeok fires

## Canonical fires (6)

bbox key order = `[minlon, minlat, maxlon, maxlat]` (W, S, E, N); ignition = `[lon, lat]`.
Windows are KST. `start` / `end` / `reported_ha` are **provenance only** — only **bbox + ignition**
drive the grid and the model.

| id | bbox [minlon, minlat, maxlon, maxlat] | ignition [lon, lat] | window (KST) | reported_ha |
|---|---|---|---|---|
| gangneung_2023 | [128.62, 37.57, 129.02, 37.97] | [128.87, 37.77] | 2023-04-11..04-13 | 379 |
| hongseong_2023 | [126.22, 36.36, 126.82, 36.76] | [126.52, 36.56] | 2023-04-02..04-06 | 1454 |
| miryang_2022 | [128.43, 35.33, 129.03, 35.83] | [128.77, 35.54] | 2022-05-31..06-05 | 763 |
| uiseong_andong_2025 | [128.35, 36.15, 128.97, 36.75] | [128.63, 36.45] | 2025-03-22..03-29 | 45000 |
| uljin_samcheok_2022 | [128.95, 36.60, 129.55, 37.35] | [129.34, 36.99] | 2022-03-04..03-14 | 16302 |
| yeongdeok_2025 | [128.97, 36.10, 129.77, 36.90] | [129.37, 36.50] | 2025-03-22..03-27 | 3800 |

Notes (from the provenance files):

- Ignition coordinates are approximate (~0.01°), derived from documented ignition localities
  (uljin 북면 두천리 산154; uiseong 안평면; miryang 부북면 춘화리; gangneung 난곡동; hongseong 서부면).
- The uiseong east edge is deliberately clamped to **128.97** to tile with the yeongdeok bbox
  (no detection overlap).
- The yeongdeok window is taken from the manifest (`start` 2025-03-22T12:15+09:00,
  `end` 2025-03-27T00:00+09:00). For the other five fires, the acquisition-record table is
  authoritative where it differs from the manifest by a day at the window edge.

## Product versions

- **FIRMS** — active-fire **archive** endpoint; sources **VIIRS S-NPP (`VIIRS_SNPP_SP`) +
  VIIRS NOAA-20 (`VIIRS_NOAA20_SP`) + MODIS (`MODIS_SP`)**, merged per fire into
  `<fire>_detections.csv` with a pre-joined UTC `timestamp` column (the loader reads
  `df["timestamp"]` directly). The FIRMS `MAP_KEY` caps `day_range` at 5, so windows were split
  into ≤ 5-day chunks.
- **DEM** — **SRTM GL1 30 m via OpenTopography** (`SRTMGL1` GeoTIFF, **EPSG:4326**, int16 m).
  The response Content-Type is `application/octet-stream`; validate by TIFF magic bytes, not
  Content-Type.
- **Fuel** — **ESA WorldCover 2021 v200**, 10 m class codes (**EPSG:4326, uint8**, nodata=0),
  windowed-read from the public S3 COGs via `/vsicurl` (tiles N33/N36 × E126/E129), cropped to
  bbox. No key required.
- **Weather** — **ECMWF ERA5** `reanalysis-era5-single-levels` via **Copernicus CDS**; five
  variables: **10 m u-wind, 10 m v-wind, 2 m temperature, 2 m dewpoint, total precipitation**;
  3-hourly (00..21), `data_format=netcdf`.

## Acquisition procedure

The committed scripts `scripts/get_era5.py`, `scripts/get_fuel.py`, and `scripts/merge_firms.py`
are a **worked example for a single fire — `yeongdeok_2025`** — with the bbox hardcoded as
`128.97, 36.10, 129.77, 36.90`. The **remaining five fires are acquired by the identical
procedure**, substituting that fire's row from the table above (bbox, ignition, window). DEM
tiles are fetched from OpenTopography SRTMGL1 as described above. They are not a six-fire
pipeline; each is the one-fire exemplar re-run per fire.

Rebuilt layers must land in **`data/raw/firms/`** — per fire: `<fire>_detections.csv`,
`<fire>_era5.nc`, `<fire>_dem.tif`, `<fire>_fuel.tif`, plus `fire_manifest.json`. The loader
resolves this directory in `src/wildfireguardian/spread_v2/data.py::find_data_dir`
(candidates `data/raw/firms/firms_data`, `data/raw/firms`, `data/raw/firms_data`; or set
`$WFG_FIRMS_DIR`).

## Reproducibility caveat (FIRMS NRT → science-quality)

> NOTE: FIRMS near-real-time detections are replaced by standard-quality science data after
> roughly 2–3 months. Re-querying the identical bbox and window at a later date may return a
> different detection count than the bundle that produced the committed results. All reported
> values are fixed in committed artifacts under data/processed/.

This is not hypothetical: a bundle **reconstructed from these exact parameters produced a pooled
ROC-AUC of 0.859**, differing from the canonical **0.9053** recorded in
`data/processed/spread_v2_lofo.json`. Re-acquired detections are therefore **not** guaranteed to
reproduce the canonical result — the committed artifacts under `data/processed/` are the record.

## Canonical dataset fingerprint

A rebuild can be checked against the canonical leave-one-fire-out dataset:

- seed **20250603**
- n_rows **151904**
- n_positives **2989**
- pooled ROC-AUC **0.9053**
- six fires: `gangneung_2023`, `hongseong_2023`, `miryang_2022`, `uiseong_andong_2025`,
  `uljin_samcheok_2022`, `yeongdeok_2025`
- source `data/processed/spread_v2_lofo.json`
