# WildfireGuardian — Architecture (skeleton)

> This document is a working skeleton. Sections marked **(TBD)** will be
> expanded in later sessions. Sections marked **(implemented)** correspond to
> code that already exists in `src/wildfireguardian/`.

## 1. Goals

WildfireGuardian must answer, for a given ignition event and a given user
located in the affected area:

1. **Where will the fire be in the next 1 / 3 / 6 hours?** (perimeter forecast
   with uncertainty)
2. **Will smoke reach this user, and at what PM2.5 exposure level?**
3. **What is the safest and feasible-for-elderly evacuation route, available
   right now?**
4. **How do we deliver that information through channels the user actually
   uses (SMS, village PA, mobile push)?**

## 2. Subsystem overview

```
        ┌───────────────┐
        │   Ingestion   │  satellites, KMA, OSM, DEM
        └───────┬───────┘
                │
        ┌───────▼───────┐
        │   Fuel state  │  LFMC retrieval, fuel-model raster
        └───────┬───────┘
                │
        ┌───────▼───────┐
        │  Spread core  │  Rothermel (point) + CA (raster) + Monte Carlo
        └───────┬───────┘
                │
   ┌────────────┼────────────┐
   │            │            │
┌──▼───┐  ┌─────▼─────┐  ┌───▼────┐
│Smoke │  │  Routing  │  │ Alerts │
└──────┘  └───────────┘  └────────┘
```

## 3. Module mapping

| Module                                  | Status        | Responsibility                                              |
|-----------------------------------------|---------------|-------------------------------------------------------------|
| `wildfireguardian.fire_detection`       | scaffold      | Pull NASA FIRMS hotspots, deduplicate, project to local CRS |
| `wildfireguardian.lfmc_model`           | scaffold      | Sentinel-2 → LFMC regression (XGBoost on NDWI/NDVI bands)   |
| `wildfireguardian.spread_model`         | **implemented** | Rothermel point model + Huygens-elliptical CA + MC ensemble |
| `wildfireguardian.smoke_dispersion`     | scaffold      | Gaussian plume + HYSPLIT coupling, PM2.5 exposure rasters   |
| `wildfireguardian.routing`              | scaffold      | Time-dependent Dijkstra on OSM with elderly speed profiles  |
| `wildfireguardian.delivery`             | scaffold      | Multi-channel alert dispatch (SMS, village PA, push)        |
| `wildfireguardian.validation`           | scaffold      | Retrospective scoring against the 2025 Yeongdeok event      |
| `wildfireguardian.data_io`              | scaffold      | Raster/vector I/O helpers, CRS handling, caching            |
| `wildfireguardian.utils`                | scaffold      | Logging, unit conversions, constants                        |

## 4. Coordinate reference systems (TBD)

- Input fire perimeters: WGS84 (EPSG:4326)
- Working CRS for raster math: EPSG:5179 (Korea 2000 / Unified CS), 30 m
  resolution, anchored to the KLIS national grid.
- Routing graph: re-projected to a local UTM zone per region.

## 5. Time discretisation (implemented for CA)

- CA simulation step: 1–5 minutes (configurable).
- Forecast horizons: 60 / 180 / 360 minutes.
- Monte Carlo ensemble size: target ≥ 100, typical demo 20–50.

## 6. Validation strategy (TBD)

Retrospective hindcast of the 영덕군 wildfire (March 22–28, 2025):

- Inputs: KMA AWS hourly wind from nearby stations, Sentinel-2 LFMC ≤ 7 days
  pre-event, KFS official perimeter polygons as ground truth.
- Skill scores: Sørensen–Dice on perimeter polygons at +1 h, +3 h, +6 h;
  Brier score on per-cell burn probability; lead-time-to-warning metric for
  selected village centroids.

## 7. Non-goals

- We do not attempt to model crown fire behaviour. Korean Pinus densiflora /
  Pinus thunbergii forests are crown-fire prone, and this is a known and
  documented limitation.
- We do not attempt real-time deployment in this competition cycle. All
  outputs are *hindcast* unless explicitly stated.
- We do not replace existing emergency dispatch authority. The system is a
  decision-support prototype, not an operational order.
