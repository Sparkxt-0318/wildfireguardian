# Reproducing the six-fire real-data pipeline (재현 안내)

This document is a **fresh-clone → verified-result** recipe for a judge. It shows
how to assemble the six-fire data bundle that the canonical `spread_v2` pipeline
consumes, then run it and confirm the headline number.

> **Expected headline (traceable to a committed artifact).** After assembling the
> bundle and running `scripts/run_routing_integration.py`, the leave-one-fire-out
> (LOFO) **pooled out-of-fold ROC-AUC = `0.9053277489374548` (≈ 0.905)**, with
> **mean-of-folds ≈ 0.890** (range 0.68–0.97). This is the value committed in
> [`data/processed/spread_v2_lofo.json`](../data/processed/spread_v2_lofo.json)
> under `seed = 20250603`, and it is what every other document in the repo
> (`README.md`, `docs/MODEL_CARD.md`) reports. The pipeline is byte-deterministic
> under this seed.
>
> `scripts/calibration_metrics.py` re-derives the same LOFO out-of-fold
> predictions and **gates** the regenerated GBM pooled AUC against this committed
> `0.9053277489374548` (tolerance 1e-4) — if your fresh run disagrees, the script
> prints a drift warning, which is the signal to reconcile your bundle before
> trusting downstream numbers.

Everything here is **public** data. The repository distributes **no** raw
geospatial data; the raw bundle and bulk rasters are git-ignored (see
[§7](#7-what-is-committed-vs-what-you-regenerate)). Only small result JSON
summaries are committed.

---

## 1. Prerequisites

```bash
git clone https://github.com/sparkxt-0318/wildfireguardian
cd wildfireguardian
python -m venv .venv && . .venv/bin/activate     # Python >= 3.10
pip install -e ".[ml,geospatial,routing]"        # or: pip install -r requirements.txt
```

Core dependencies for the LOFO + calibration path: `numpy scipy pandas
scikit-learn matplotlib` plus the geospatial stack used to rebuild the dataset
(`pyproj rasterio xarray h5netcdf shapely`). The routing demo additionally uses
`networkx` (+ `osmnx` for the OSM-backed rescue variant).

---

## 2. Credentials

Copy `.env.example` → `.env` and fill in two keys (the other entries are optional
for this pipeline):

| Variable | Where to get it |
|---|---|
| `NASA_FIRMS_MAP_KEY` | https://firms.modaps.eosdis.nasa.gov/api/area/ (free MAP_KEY) |
| `CDSAPI_URL` / `CDSAPI_KEY` | https://cds.climate.copernicus.eu/ — register, then a `UID:KEY` pair (also written to `~/.cdsapirc`) |

`.env` is git-ignored — never commit real keys.

---

## 3. The six-fire manifest (bbox / window / ignition)

The canonical per-fire records live in `data/raw/firms/fire_manifest.json`, which
**ships inside the git-ignored bundle** (`firms_data.zip`) and is therefore *not*
in a fresh clone. The bounding boxes and date windows below are the exact values
preserved in the committed, git-tracked
[`data/processed/spread_v2/audit.json`](../data/processed/spread_v2/audit.json);
they are what you must reproduce the manifest with.

| Fire `id` | Name | bbox (WGS84 `minlon,minlat,maxlon,maxlat`) | Date window | Ignition `lon,lat` |
|---|---|---|---|---|
| `gangneung_2023` | 2023 강릉(경포) / Gangneung | `128.75, 37.70, 129.05, 37.95` | 2023-04-11 … 2023-04-13 | *bundle manifest* † |
| `hongseong_2023` | 2023 홍성 / Hongseong | `126.45, 36.50, 126.85, 36.90` | 2023-04-02 … 2023-04-05 | *bundle manifest* † |
| `miryang_2022` | 2022 밀양 / Miryang | `128.65, 35.40, 129.05, 35.75` | 2022-05-31 … 2022-06-05 | *bundle manifest* † |
| `uiseong_andong_2025` | 2025 의성-안동 / Uiseong-Andong | `128.40, 36.20, 129.10, 36.75` | 2025-03-22 … 2025-03-28 | *bundle manifest* † |
| `uljin_samcheok_2022` | 2022 울진-삼척 / Uljin-Samcheok | `129.10, 36.85, 129.60, 37.45` | 2022-03-04 … 2022-03-14 | `129.32, 37.00` ‡ |
| `yeongdeok_2025` | 2025 영덕 / Yeongdeok | `128.95, 36.20, 129.60, 36.75` | 2025-03-22 … 2025-03-28 | `129.37, 36.50` ‡ |

- **†** The ignition `[lon, lat]` for these four fires exists **only** in the
  git-ignored `fire_manifest.json` and is deliberately **not reproduced here**
  (it is not committed anywhere in the repo — do not guess it).
- **‡** Committed **approximate** ignition points, from
  [`data/validation_cases/uljin_samcheok_2022.json`](../data/validation_cases/uljin_samcheok_2022.json)
  and [`data/validation_cases/yeongdeok_2025.json`](../data/validation_cases/yeongdeok_2025.json)
  (`observed_ignition_point_wgs84`, flagged "approximate" in each file's
  provenance). FIRMS is a *detection* product, so the first detection can lag true
  ignition by days (Yeongdeok ignited 2025-03-22 but the first FIRMS hit is
  2025-03-25); treat the footprint as an observed lower bound.

The analysis grid is fixed at **375 m in EPSG:5179** (Korea 2000 / Unified TM)
regardless of each layer's native resolution.

### `fire_manifest.json` schema (author this during acquisition)

One object per fire under a top-level `"fires"` list, consumed by
`src/wildfireguardian/spread_v2/data.py` (`list_fires`):

```json
{
  "fires": [
    {
      "id": "yeongdeok_2025",
      "name": "2025 영덕 / Yeongdeok",
      "bbox": [128.95, 36.20, 129.60, 36.75],
      "start": "2025-03-22",
      "end":   "2025-03-28",
      "ignition": [129.37, 36.50],
      "reported_ha": 0,
      "n_detections": 0,
      "notes": ""
    }
  ]
}
```

---

## 4. Assemble the bundle — four layers per fire

For **each** fire, clip every layer to that fire's `bbox` and write it into
`data/raw/firms/` with the exact filename pattern. The four per-fire files plus
the two manifests are the complete bundle.

| File | Source | Product / schema |
|---|---|---|
| `<id>_detections.csv` | **NASA FIRMS** archive (MODIS + VIIRS) | columns: `latitude, longitude, acq_date, acq_time, frp, confidence, satellite, instrument, timestamp` (pre-joined UTC ISO-8601 `timestamp`) |
| `<id>_era5.nc` | **Copernicus CDS ERA5 single-levels** | CDS zip of two HDF5 NetCDFs: instant `u10, v10, t2m, d2m` + accum `tp` |
| `<id>_dem.tif` | **SRTMGL1 ~30 m** (OpenTopography / EarthExplorer) | single-band float elevation, EPSG:4326 |
| `<id>_fuel.tif` | **ESA WorldCover 2021** (10 m) | land-cover class codes, uint8, EPSG:4326 |

### 4a. NASA FIRMS active-fire detections

Query the FIRMS **Area API** for each fire's bbox and date window. Because these
are historic events (2019/2022/2025), use the **archive / standard-processing
(`_SP`) sources** rather than the near-real-time (`_NRT`) ones:

```
https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{minLon,minLat,maxLon,maxLat}/{dayRange}/{startDate}
# SOURCE ∈ { VIIRS_SNPP_SP, VIIRS_NOAA20_SP, MODIS_SP }
```

> ⚠️ The exact `_SP` source strings and Area-API path shape are **FIRMS provider
> conventions, not documented in this repo** — confirm them against the current
> FIRMS API docs. Merge the VIIRS SNPP + NOAA-20 (+ MODIS) rows, add a UTC
> `timestamp` column, and write `<id>_detections.csv`. Downstream, detections are
> clustered into overpasses by a 60-minute gap rule and snapped to the 375 m grid.

### 4b. Copernicus CDS ERA5 single-levels (weather)

Dataset `reanalysis-era5-single-levels`, one request per fire:

```python
import cdsapi
c = cdsapi.Client()
c.retrieve("reanalysis-era5-single-levels", {
    "product_type": "reanalysis",
    "variable": ["10m_u_component_of_wind", "10m_v_component_of_wind",
                 "2m_temperature", "2m_dewpoint_temperature", "total_precipitation"],
    "area": [maxlat, minlon, minlat, maxlon],   # N, W, S, E  (the fire bbox)
    "grid": [0.25, 0.25],
    "date": "2025-03-22/2025-03-28",            # the fire window
    "time": [f"{h:02d}:00" for h in range(24)], # see cadence note below
    "format": "netcdf",
}, "data/raw/firms/yeongdeok_2025_era5.nc")
```

- The reader (`spread_v2/data.py::open_era5`) detects the CDS zip (`PK` magic) and
  merges the `instant` + `accum` streams; it tolerates a **0-byte** `era5.nc` (a
  failed CDS retrieval is handled downstream as `weather = NaN`).
- **Cadence note:** the code comments are inconsistent (hourly in
  `spread_v2_xgb/era5.py`, "3-hourly" in `spread_v2/data.py`). The `days_since_rain`
  derivation assumes hourly cadence, so request **hourly** and document it.

### 4c. DEM — SRTMGL1 ~30 m

Fetch a single-band float GeoTIFF (EPSG:4326) clipped to each bbox, e.g. via the
OpenTopography Global DEM API:

```
https://portal.opentopography.org/API/globaldem?demtype=SRTMGL1&south={minlat}&north={maxlat}&west={minlon}&east={maxlon}&outputFormat=GTiff&API_Key={KEY}
```

> ⚠️ The OpenTopography `demtype=SRTMGL1` endpoint + `API_Key` is a **provider
> convention, not in this repo** — verify against OpenTopography docs. (The repo's
> in-code SRTM loader `data_io/raster.py` uses a different source — the AWS-Mapzen
> `elevation-tiles-prod` `.hgt.gz` archive, reprojected to EPSG:5179 — which is an
> alternate DEM path, not the per-fire bundle raster.) SRTMGL1 is **1-arc-second**
> (~30 m); the "3-arc-second" line in `docs/data_sources.md` is a doc error.

### 4d. ESA WorldCover 2021 (fuel burnability)

Fetch the ESA WorldCover **2021 (v200)** 10 m land-cover tiles from
https://esa-worldcover.org/, clip to each bbox, and write `<id>_fuel.tif` as
uint8 class codes (EPSG:4326). The class → burnable map (shipped in
`data_layers_manifest.json`, with this hard-coded fallback in
`spread_v2/data.py`):

```
burnable = {10:1, 20:1, 30:1, 40:1, 50:0, 60:0, 70:0, 80:0, 90:1, 95:1, 100:1}
# 10 tree 20 shrub 30 grass 40 crop 90 herb-wetland 95 mangrove 100 moss = burn;
# 50 built 60 bare 70 snow/ice 80 water = no-burn.  Cell burns if >= 0.5 burnable.
```

### 4e. Author `data_layers_manifest.json`

Alongside `fire_manifest.json`, write `data_layers_manifest.json` carrying the
top-level `worldcover_burnable_map` (the map above) and per-fire raster
paths/shapes + `burnable_frac`.

### 4f. Place the bundle

Put all files at `data/raw/firms/` (or point `$WFG_FIRMS_DIR` at the directory):

```bash
unzip firms_data.zip -d data/raw/        # or: export WFG_FIRMS_DIR=/path/to/firms
python -c "import sys; sys.path.insert(0,'src'); from wildfireguardian.spread_v2 import data; print('data_available:', data.data_available()); print([m.id for m in data.list_fires()])"
```

`data_available()` must print `True` and list the six fire ids.

---

## 5. Run the pipeline

```bash
# 1) LOFO validation + Yeongdeok forward-sim + routing demo (the headline)
python scripts/run_routing_integration.py
#   → data/processed/spread_v2_lofo.json        (pooled AUC 0.905, per-fire AUCs)
#   → data/processed/yeongdeok_forward_sim.json (out-of-sample hazard drift)
#   → data/processed/routing_demo.json/.npz     (naive vs future-aware routes)

# 2) Probability calibration — canonical GBM vs random-forest / logistic baselines
python scripts/calibration_metrics.py
#   → data/processed/spread_v2_lofo_oof.csv.gz + lofo_oof_{random_forest,logistic}.csv.gz
#   → data/processed/calibration_metrics.json   (Brier / ECE, 15 equal-count bins)
#   → docs/figures/calibration_reliability.png  (reliability diagram)
```

`calibration_metrics.py` knobs: `--seed` (default `20250603`), `--n-bins`
(default `15`), `--isotonic-splits` (default `5`), `--no-fig`. Both scripts
**STOP cleanly (exit 2)** — never fabricate numbers — if the bundle is absent.

### Expected results (from the committed JSONs)

| Artifact | Key number | Committed value |
|---|---|---|
| `spread_v2_lofo.json` | pooled OOF AUC | **0.9053277489374548** |
| `spread_v2_lofo.json` | mean-of-folds AUC | ≈ 0.890 (per-fire 0.682–0.974) |
| `spread_v2_lofo.json` | far-band AUC | 0.8765583120330634 |
| `spread_v2_lofo.json` | severity ÷ direction importance | 43.69× |
| `yeongdeok_forward_sim.json` | envelope area, step 0 → 4 | 6225 → 27900 ha (5 × 3 h) |
| `routing_demo.json` | headline exposure reduction | −93.1 % (334.3 → 23.1) |
| `routing_demo.json` | origins scanned / no-safe-route | 407 / 88 |
| `calibration_metrics.json` | Brier / ECE (GBM, RF, logistic) | *regenerated — report as it falls* |

---

## 6. Verify (determinism + consistency gates)

```bash
# Full suite (data-dependent tests self-skip if a layer/cache is absent)
python -m pytest -q

# Calibration regeneration determinism (skips if bundle/JSON absent)
python -m pytest tests/test_calibration_metrics.py -v
```

Two built-in guards protect against a silently-wrong bundle:

1. `calibration_metrics.py` re-derives the GBM OOF and **asserts** its pooled AUC
   matches the committed `0.9053277489374548` (Δ ≤ 1e-4), warning on drift.
2. `test_calibration_metrics.py` re-runs `compute_payload` twice and asserts the
   payload is **byte-identical** and reproduces the committed
   `calibration_metrics.json` when both the bundle and that JSON are present.

---

## 7. What is committed vs what you regenerate

`.gitignore` policy: **result JSON summaries are tracked; raw data and bulk
arrays/rasters are ignored.**

- **Committed** (verifiable in a fresh clone): `spread_v2_lofo.json`,
  `yeongdeok_forward_sim.json`, `routing_demo.json`, `data/processed/spread_v2/*.json`
  (incl. `audit.json`), the rescue-routing JSONs, and — once you generate them —
  `calibration_metrics.json` + the OOF `*.csv.gz` frames (all whitelisted).
- **Ignored** (regenerated from the bundle): everything under `data/raw/**`
  (the FIRMS/ERA5/DEM/fuel bundle + `fire_manifest.json`), `*.npz` figure arrays,
  and all rasters (`*.tif`, `*.nc`, …).
