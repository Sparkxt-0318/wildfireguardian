# WildfireGuardian — Architecture

This document describes the system architecture. The **canonical, working spine is
the data-driven model**: `spread_v2` (sklearn `HistGradientBoostingClassifier`
per-cell ignition probability, LOFO-validated on six real fires) feeding the elderly- and rescue-aware evacuation
router. The mechanistic **Rothermel / cellular-automaton spread engine described in
§2–§3 is the project's *initial* track — now superseded** and kept as a research
record (see the README "Research log / superseded approaches" and
`docs/MODEL_CARD.md`). Smoke dispersion and the Sentinel-2 LFMC regression are
**research scaffolds, not current deliverables**.

## 1. Goals

WildfireGuardian must answer, for a given ignition event and a given user
located in the affected area:

1. **Where will the fire ignite next?** A data-driven per-cell ignition-probability
   surface (`spread_v2`) over the satellite-overpass horizon — calibrated
   probabilities, LOFO-validated generalization.
2. **What is the safest and feasible-for-elderly evacuation route, available right
   now?** (future-front-aware, time-dependent exposure cost)
3. **If a resident cannot self-evacuate, can a responder reach them — and who is
   genuinely unreachable?** (the rescue-aware layer: ingress-survival + triage)
4. **How do we deliver that through channels the user actually uses?** (SMS, village
   PA, mobile push)

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
   │   Spread model (CANONICAL):  spread_v2 per-cell P(ignite)        │
   │   HistGradientBoosting · LOFO-validated · calibrated probs      │
   │   — superseded initial track: Rothermel + Huygens CA (research)  │
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
   │ (scaf.) │              │  (impl.)  │              │   (scaf.)   │
   └─────────┘              └───────────┘              └─────────────┘
```

## 3. Module mapping

| Module | Status | Responsibility |
|--------|--------|----------------|
| `wildfireguardian.spread_v2` | **implemented (canonical, Build B)** | Data-driven per-cell `P(ignite)`; LOFO-validated; produced every reported number |
| `wildfireguardian.spread_v2_xgb` | **implemented** | Orientation-safe re-train of the data-driven build (the structural fix for the prior `uljin` orientation bug) |
| `wildfireguardian.routing` | **implemented** | Future-front-aware + rescue-aware time-dependent routing on OSM (elderly/responder profiles, ingress-survival, triage) |
| `wildfireguardian.validation` | **implemented** | LOFO scoring + DeLong / bootstrap / permutation stats; IoU / Brier / lead-time |
| `wildfireguardian.data_io.raster` | **implemented (synthetic fallback)** | DEM / fuel / landcover ingestion |
| `wildfireguardian.utils.regions` | **implemented** | RegionConfig presets + CRS handling |
| `wildfireguardian.utils.vulnerability` | **implemented (placeholder)** | Rural-elderly vulnerability scoring |
| `wildfireguardian.fire_detection` | scaffold | Pull NASA FIRMS hotspots, deduplicate, project to local CRS |
| `wildfireguardian.spread_model.rothermel` | superseded (research log) | Multi-class Rothermel + Burgan 1979 + Korean Pinus — the *initial* physics track; captured only ~9 % of burned area, motivating the data-driven pivot |
| `wildfireguardian.spread_model.cellular_automaton` | superseded (research log) | CRS-aware Huygens-elliptical CA + Monte Carlo (physics track) |
| `wildfireguardian.lfmc_model` | research scaffold | Sentinel-2 → LFMC regression — **not** part of the canonical pipeline |
| `wildfireguardian.smoke_dispersion` | research scaffold | Gaussian plume — **not** a current deliverable |
| `wildfireguardian.delivery` | scaffold | Multi-channel alert dispatch |
| `wildfireguardian.utils.units` | implemented | Imperial ↔ SI conversions (physics track) |

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

The **canonical `spread_v2` model is keyed to the satellite-overpass cadence**
(~60-min VIIRS passes): it predicts `P(ignite by the next overpass)` on the 375 m
grid. The finer-grained timings below belong to the **superseded CA track**:

- CA simulation step: 1–5 minutes (configurable; default 2 min at 100 m
  cell size for CFL stability).
- Snapshot interval: configurable; default 20–60 minutes.
- Forecast horizons: 60 / 180 / 360 / 1440 minutes (1 h / 3 h / 6 h / 24 h).
- Monte Carlo ensemble size: target ≥ 100, typical demo 20–50.

## 6. Validation strategy

The **canonical validation is leave-one-fire-out (LOFO)** for the data-driven
`spread_v2` model: six real Korean fires (gangneung_2023, hongseong_2023,
miryang_2022, uiseong_andong_2025, uljin_samcheok_2022, yeongdeok_2025), each held
out whole. Headline **mean-of-folds ROC-AUC 0.89** (range 0.68–0.97; pooled 0.905),
with per-fire DeLong CIs and a significance test vs 0.5, standard ML baselines on the
identical folds, and a forward-simulated footprint IoU ≈ 0.40 (Yeongdeok, 3–12 h).
Full numbers: `docs/MODEL_CARD.md`, `docs/auc_intervals.md`, `docs/baselines.md`.

The earlier physics track was scored against retrospective perimeter cases
(Yeongdeok 2025, Uljin/Samcheok 2022, Goseong 2019 — approximate manifests in
`data/validation_cases/`) with IoU / Sørensen-Dice / Brier; that track is the
superseded research record (`docs/methodology/validation_strategy.md`).

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

- The mechanistic (Rothermel surface) track did **not** capture crown fire /
  spotting — it reproduced only ~9 % of burned area, which is exactly what motivated
  the pivot to the data-driven `spread_v2` model. The data-driven model implicitly
  captures that crown/spotting-driven regime (forward-sim footprint IoU ≈ 0.40, ~4×
  the surface model). Background: `docs/BLOCKERS.md` and the README research log.
- We do not attempt real-time deployment in this competition cycle. All
  outputs are *hindcast* unless explicitly stated.
- We do not replace existing emergency dispatch authority. The system is
  a decision-support prototype, not an operational order.
- Urban districts (Seoul, Busan, Daegu, Incheon, Daejeon, Gwangju, Ulsan)
  are explicitly out of the deployment scope — they have adequate
  evacuation infrastructure and demographically different populations.
