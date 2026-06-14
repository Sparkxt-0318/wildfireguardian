# Data sources

WildfireGuardian relies entirely on **public** data. The repository does
not distribute any of it; users download datasets into `data/raw/` at
runtime using the ingestion helpers in `wildfireguardian.data_io`. None
of the runtime calls in this repository connect to remote sources without
explicit user opt-in.

The **canonical data-driven pipeline (`spread_v2`) uses four inputs**: NASA FIRMS
(VIIRS S-NPP/NOAA-20 + MODIS active fire), SRTM ~30 m DEM, ESA WorldCover 2021 (10 m
land cover → fuel burnability), and ECMWF ERA5 (reanalysis weather); the rescue
router adds OpenStreetMap walk/drive networks and 공공데이터포털 shelters/119 depots.
The **Sentinel-2 LFMC, KFS 임상도 fuel-model, and KMA-wind-field-for-CA entries below
belong to the earlier physics track** and are retained for reference, **not** as
current `spread_v2` inputs.

## Satellite

| Dataset | Provider | Use | Access | Auth |
|---------|----------|-----|--------|------|
| VIIRS S-NPP / NOAA-20 375 m active fire | NASA FIRMS | Real-time ignition detection | https://firms.modaps.eosdis.nasa.gov/api/ | MAP_KEY |
| MODIS Aqua/Terra MCD14ML | NASA FIRMS | Cross-check & historic ignitions | Same | MAP_KEY |
| Sentinel-2 L2A surface reflectance | Copernicus | LFMC retrieval (superseded physics track) | https://browser.dataspace.copernicus.eu/ | CDS account |
| Sentinel-3 SLSTR L2 FRP | Copernicus | Fire radiative power | Same | CDS account |

## Meteorology

| Dataset | Provider | Use | Access | Auth |
|---------|----------|-----|--------|------|
| KMA AWS hourly wind, RH, T | KMA | Spatial wind field for CA (superseded physics track) | https://data.kma.go.kr/ | service key |
| ERA5 single levels (10 m winds, 2 m T/q) | Copernicus C3S | **Canonical weather source for `spread_v2`** | CDS API | CDS account |
| GDAPS / KIM regional NWP | KMA | Short-range forecast wind | https://data.kma.go.kr/ | service key |

## Terrain — DEM

### Option A: NGII 국토지리정보원 (preferred for Korean operational use)

- **Dataset**: 1:5000 digital map (vector contour + spot heights) →
  rasterised to 5 m / 10 m / 30 m DEM.
- **Access**: https://map.ngii.go.kr/ → 국토정보플랫폼 → 디지털지도 →
  1:5000 vector contour. Free for research use.
- **Registration**: Korean residence required for full download; foreign
  researchers can request via the 국제협력 portal (slower).
- **License**: KOGL (Korea Open Government License) Type 1 — free
  redistribution as derived products with attribution.
- **What to do if blocked**: fall back to SRTM 30 m or COPDEM 30 m (below).
  Both are free and global; the loss of accuracy vs NGII is ~3-5 m
  vertical RMSE, acceptable for the model's slope / terrain features.
- **Where to put it**: ``data/raw/dem/ngii/<sheet>.tif`` (gridded GeoTIFF
  in EPSG:5179) or .shp for vector contours.

### Option B: SRTM (free global fallback)

- **Dataset**: NASA SRTM 30 m DEM (3-arc-second).
- **Access**: https://earthexplorer.usgs.gov/ (or AWS Open Data:
  ``s3://elevation-tiles-prod/``).
- **License**: Public domain.
- **Where to put it**: ``data/raw/dem/srtm/<tile>.hgt`` or .tif.

The `wildfireguardian.data_io.raster.load_dem` function tries
``source='ngii'`` → ``source='srtm'`` → ``source='synthetic'`` in order
when called with ``source='auto'``. Session 2 implements only the
synthetic path; the SRTM and NGII paths raise NotImplementedError with
clear instructions until Session 3.

## Fuel type — KFS 임상도

> *Superseded physics track.* The canonical `spread_v2` model derives fuel
> burnability from **ESA WorldCover** (see Landcover, below), not from KFS
> fuel-model codes. The 임상도 → fuel-model path below was for the Rothermel engine
> and is kept for reference.

- **Dataset**: 임상도 v1.4 (Korean Forest Service forest-stand-type map).
  Polygon shapefile with stand-level attributes: dominant species,
  age class, density, canopy closure.
- **Access**: https://map.forest.go.kr/forest/ → 임상정보 → 임상도.
  Requires Korean Forest Service registration; foreign researchers can
  apply via 국제협력 form.
- **License**: KOGL Type 1.
- **What to do if blocked**: ME 토지피복 v3 (Ministry of Environment land
  cover, below) provides 1-digit landcover that lets us infer "forest" vs
  "non-forest"; Session 2's synthetic-Korean-Pinus is a defensible
  fallback if no real fuel-type raster is available.
- **Where to put it**: ``data/raw/fuel/kfs_impsangdo/`` shapefile.
- **Refinement path**: stand-species codes → fuel-model codes via a
  lookup table (e.g., 소나무 / Pinus densiflora codes → KP_PINE; 참나무 /
  Quercus codes → FM9; 침엽 / mixed → FM10). Session 3 task.

## Landcover

| Dataset | Provider | Use | Access |
|---------|----------|-----|--------|
| 환경부 토지피복지도 v3 | ME (환경부) | Fuel-model fallback when 임상도 unavailable | https://egis.me.go.kr/ |
| ESA WorldCover 10 m | ESA | Global fallback | https://esa-worldcover.org/ |

## Roads & population

| Dataset | Provider | Use | Access |
|---------|----------|-----|--------|
| OSM road network | OpenStreetMap | Evacuation routing graph | https://www.openstreetmap.org/ |
| 행정안전부 주민등록 연령별 인구 통계 | MOIS | Rural-elderly density | https://mois.go.kr/ |
| KOSIS 시군구별 65세 이상 독거노인 | KOSIS | Solitary-elderly density | https://kosis.kr/ |
| SK Telecom Floating Population (sample) | KOSIS | Diurnal exposure adjustment | https://kosis.kr/ |

## Rescue-aware routing inputs (walk/drive networks, refuges, depots)

The rescue-aware evacuation router (`wildfireguardian.routing.rescue`) needs a
**drive** network (responders) in addition to the **walk** network (residents),
plus candidate refuges and responder depots. Each has a real-source loader **and**
a clearly-labelled synthetic fallback so the pipeline runs end-to-end offline; the
loader tags every record `source = "real" | "synthetic"`.

| Dataset | Provider | Use | Access | Real-source loader |
|---------|----------|-----|--------|--------------------|
| OSM `walk` + `drive` networks | OpenStreetMap (via OSMnx) | Pedestrian + vehicle routing graphs (reprojected to EPSG:5179, disk-cached) | https://www.openstreetmap.org/ | `rescue.load_drive_network(..., use_osm=True)` |
| 대피소·긴급대피장소 (전국 대피소 표준데이터) | 행정안전부 / 공공데이터포털 | Candidate refuges (shelter-in-refuge destinations) | https://www.data.go.kr/ | `rescue.load_shelters` (GeoJSON/CSV at `cfg.shelters_path`) |
| 119안전센터 현황 / OSM `amenity=fire_station` | 소방청 / 공공데이터포털 / OSM | Responder depots | https://www.data.go.kr/ | `rescue.load_depots` (GeoJSON/CSV at `cfg.depots_path`) |

When no `shelters_path`/`depots_path` is configured and `use_osm=False` (the
default, offline), the demo (`routing.rescue_demo`) substitutes **synthetic**
coastal assembly nodes + inland open-space refuges, synthetic near-town depots, a
synthetic growing hazard envelope, and an 8-connected lattice on the real 영덕
extent — all tagged synthetic and listed in `rescue_routing.json::provenance`.
KOGL (Korea Open Government License) attribution applies to the Korean open data
exactly as for the other datasets above.

## Wildfire validation — KFS perimeter shapefiles

| Event | Dataset | Provider | Access |
|-------|---------|----------|--------|
| 영덕 2025-03 | KFS post-event perimeter | KFS | KFS post-event report PDF + accompanying shapefile (request via KFS 산불방지과) |
| 울진/삼척 2022-03 | KFS final report perimeter | KFS | KFS 2022 final report |
| 고성/속초 2019-04 | KFS final report perimeter | KFS | KFS 2019 final report |

For Session 2, these perimeter polygons are **stub manifests** in
``data/validation_cases/*.json`` with approximate ignition points and
official-warning timelines reconstructed from public news coverage. Real
KFS shapefiles need to be ingested in Session 3 to enable Sørensen-Dice
and IoU validation.

## Vulnerability scoring inputs (Session 3 ingestion)

The placeholder vulnerability scores in
``src/wildfireguardian/utils/vulnerability.py`` will be replaced with real
data from:

- **KOSIS 65세 이상 독거노인 통계** for `rural_elderly_density`.
- **KFS 시군구별 산불발생 건수 2010-2024** for `fire_frequency_score`.
- **MOIS 지진/산불 대피소 시설 현황** for `infrastructure_score`
  (inverse — fewer shelters → higher vulnerability).

All three are public; all three require registration; all three are
explicitly catalogued in ``docs/BLOCKERS.md``.

## Licensing & attribution

All datasets listed here are public for non-commercial research. Each
ingestion helper in `wildfireguardian.data_io` emits the proper
attribution line in the output product metadata. Never redistribute raw
NASA FIRMS or Sentinel imagery; redistribute derived products only, with
provenance.

For Korean datasets covered by KOGL (Korea Open Government License),
attribution must include:

- The producing agency (NGII / KFS / KMA / ME / MOIS).
- The dataset name + version.
- The license URL: https://www.kogl.or.kr/info/license.do
