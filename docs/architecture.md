# WildfireGuardian — Architecture

This document describes the system architecture as of Session 2 (May 2026).
Sections marked **(implemented)** correspond to working code; sections
marked **(planned)** describe the design intent for upcoming sessions.

## 1. Goals

WildfireGuardian must answer, for a given ignition event and a given user
located in the affected area:

1. **Where will the fire be in the next 1 / 3 / 6 / 24 hours?** (perimeter
   forecast with uncertainty)
2. **Will smoke reach this user, and at what PM2.5 exposure level?**
3. **What is the safest and feasible-for-elderly evacuation route, available
   right now?**
4. **How do we deliver that information through channels the user actually
   uses (SMS, village PA, mobile push)?**

The intervention is targeted: this system serves rural elderly Koreans in
the East Coast Pine Belt — a defined set of 시군 with high wildfire
frequency, high % 65+ population, and limited evacuation infrastructure.
See `docs/methodology/vulnerable_counties.md` for the deployment-target list.

## 2. Subsystem overview

```
   ┌──────────────────────────────────────────────────────────────────┐
   │  Geographic config:  RegionConfig (EPSG:5179, Korea operational) │
   │  Vulnerability:      WILDFIRE_VULNERABLE_COUNTIES (15 시군)      │
   └──────────────────────────────┬───────────────────────────────────┘
                                  │
   ┌──────────────────────────────▼───────────────────────────────────┐
   │     Raster ingestion   (data_io.raster)                          │
   │     - DEM      (NGII / SRTM / synthetic fallback)                │
   │     - Fuel     (KFS 임상도 / synthetic Korean Pinus)             │
   │     - Landcover (ME 토지피복 / synthetic forest)                 │
   └──────────────────────────────┬───────────────────────────────────┘
                                  │
   ┌──────────────────────────────▼───────────────────────────────────┐
   │       Spread engine:  Rothermel multi-class + Burgan 1979        │
   │       + CRS-aware FireGrid (Huygens-elliptical CA)               │
   │       + Monte Carlo ensemble                                     │
   └──────────────────────────────┬───────────────────────────────────┘
                                  │  perimeters + burn probability raster
   ┌──────────────────────────────▼───────────────────────────────────┐
   │     Validation:  IoU, Sørensen-Dice, Brier, lead-time gain       │
   │     against historical: Yeongdeok 2025, Uljin/Samcheok 2022,     │
   │                          Goseong 2019                            │
   └──────────────────────────────┬───────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────────┐
   ┌────▼────┐              ┌─────▼─────┐              ┌────────▼────┐
   │  Smoke  │              │  Routing  │              │   Alerts    │
   │ (Sess3) │              │  (Sess4)  │              │   (Sess4)   │
   └─────────┘              └───────────┘              └─────────────┘
```

## 3. Module mapping

| Module | Status | Responsibility |
|--------|--------|----------------|
| `wildfireguardian.fire_detection` | scaffold | Pull NASA FIRMS hotspots, deduplicate, project to local CRS |
| `wildfireguardian.lfmc_model` | scaffold | Sentinel-2 → LFMC regression (XGBoost on NDWI/NDVI bands) |
| `wildfireguardian.spread_model.rothermel` | **implemented (S2)** | Multi-class Rothermel + Burgan 1979 + Korean Pinus model |
| `wildfireguardian.spread_model.cellular_automaton` | **implemented (S2)** | CRS-aware Huygens-elliptical CA + Monte Carlo |
| `wildfireguardian.smoke_dispersion` | scaffold | Gaussian plume + HYSPLIT coupling |
| `wildfireguardian.routing` | scaffold | Time-dependent Dijkstra on OSM, elderly speed profiles |
| `wildfireguardian.delivery` | scaffold | Multi-channel alert dispatch |
| `wildfireguardian.validation` | **implemented (S2)** | Retrospective scoring; IoU / Sorensen-Dice / Brier / lead-time |
| `wildfireguardian.data_io.raster` | **implemented (S2, synthetic fallback)** | DEM / fuel / landcover ingestion |
| `wildfireguardian.utils.regions` | **implemented (S2)** | RegionConfig presets + CRS handling |
| `wildfireguardian.utils.vulnerability` | **implemented (S2, placeholder)** | Rural-elderly vulnerability scoring |
| `wildfireguardian.utils.units` | implemented | Imperial ↔ SI conversions for Rothermel |

## 4. Coordinate reference systems

- **Working CRS for all raster math**: EPSG:5179 (Korea 2000 / Unified CS).
  This is the de facto Korean operational CRS; NGII, KFS, MOIS, and KMA
  all default to it.
- **Input ignition points**: WGS84 (EPSG:4326) — converted at the boundary.
- **GeoJSON exports**: WGS84 (EPSG:4326) per RFC 7946. The CRS-aware
  `FireGrid.to_wgs84_perimeter()` does this reprojection.
- **GeoTIFF exports**: EPSG:5179. The `FireGrid.to_geotiff()` writes
  state rasters with proper CRS metadata.
- **Routing graph** (Session 4): regional UTM zone or EPSG:5179 — TBD per
  region.

All conversions live in `wildfireguardian.utils.regions` via `pyproj`.
No other module performs CRS arithmetic.

## 5. Time discretisation

- CA simulation step: 1–5 minutes (configurable; default 2 min at 100 m
  cell size for CFL stability).
- Snapshot interval: configurable; default 20–60 minutes.
- Forecast horizons: 60 / 180 / 360 / 1440 minutes (1 h / 3 h / 6 h / 24 h).
- Monte Carlo ensemble size: target ≥ 100, typical demo 20–50.

## 6. Validation strategy

See `docs/methodology/validation_strategy.md` for the full discussion.
Three retrospective cases provide the scientific defense:

1. **Yeongdeok 2025** (March 22–28, ~3,800 ha) — primary case.
2. **Uljin/Samcheok 2022** (March 4–13, ~16,000 ha) — scale validation.
3. **Goseong 2019** (April 4–6, ~2,800 ha) — wind-driven night fire.

All three sit in the East Coast Pine Belt; all three have approximate
public manifests in `data/validation_cases/`. Session 3 will ingest real
KFS perimeter shapefiles to replace the stubs.

Metrics: IoU, Sørensen-Dice, symmetric-difference area in km², Brier
score (with Monte Carlo ensemble in Session 3), lead-time gain vs.
historical 재난문자, temporal-area RMSE at 1 h / 3 h / 6 h / 24 h.

## 7. Vulnerability framing

The system is specifically built to protect rural elderly Koreans in
high-fire-frequency, sparse-infrastructure 시군. The deployment target
is the 15-county East Coast Pine Belt; Session 2 ships placeholder
vulnerability scores (Session 3 will ingest KOSIS/KFS/MOIS real data).

This focus is not an architectural detail; it informs:

- **Which regions** the validation harness exercises.
- **What time horizons** matter most (rural elderly move slowly; we care
  about 1–3 h lead-time more than 30-min).
- **What alert channels** the delivery module must support (SMS + village
  PA take precedence over mobile push for this population).
- **What evacuation profiles** the routing graph uses (slower walking
  speeds, longer dwell time, preference for paved roads).

## 8. Non-goals

- We do not attempt to model crown fire behaviour. Korean Pinus densiflora
  / Pinus thunbergii forests are crown-fire prone, and this is a known
  and documented limitation in `docs/BLOCKERS.md`.
- We do not attempt real-time deployment in this competition cycle. All
  outputs are *hindcast* unless explicitly stated.
- We do not replace existing emergency dispatch authority. The system is
  a decision-support prototype, not an operational order.
- Urban districts (Seoul, Busan, Daegu, Incheon, Daejeon, Gwangju, Ulsan)
  are explicitly out of the deployment scope — they have adequate
  evacuation infrastructure and demographically different populations.
