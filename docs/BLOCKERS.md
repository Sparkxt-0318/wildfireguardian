# Known limitations & blockers

This document records issues encountered during overnight builds that the
next session (or the human collaborator) will need to address. Each entry
is honest about what was tried, what didn't work, and what would be
needed to close it out.

---

## ✅ RESOLVED in Session 2

### BLOCKERS-1: Single-class Rothermel vs. multi-class BehavePlus  ✅ RESOLVED

**Status**: RESOLVED in Session 2.

**Resolution**: implemented Andrews 2018 multi-class weighting in
`src/wildfireguardian/spread_model/rothermel/spread.py::compute_multi_class_spread_rate`.
Multi-class FM10 R0 dropped from 4.6 ft/min (single-class, 2.3× published
overestimate) to 2.06 ft/min (within Andrews 2018 Table 7 published band
of 1.5–2.2 ft/min). See `tests/test_rothermel_multiclass.py::
test_multi_class_reproduces_andrews_2018_table7` for the assertions.

The Session 1 single-class `FuelModel` API is preserved for back-compat;
all Session 1 tests (`tests/test_rothermel.py`) still pass.

### BLOCKERS-2: No real geographic CRS  ✅ RESOLVED

**Status**: RESOLVED in Session 2.

**Resolution**: `FireGrid.from_region(region_config, cell_size_m)` now
constructs a grid sized and anchored to EPSG:5179. Outputs:

- `FireGrid.perimeter()` returns coordinates in EPSG:5179 metres.
- `FireGrid.perimeter_geodataframe()` returns a GeoDataFrame with proper CRS.
- `FireGrid.to_wgs84_perimeter()` reprojects to EPSG:4326 for GeoJSON.
- `FireGrid.to_geotiff(path)` writes EPSG:5179 GeoTIFF.

The Yeongdeok demo (`demo_yeongdeok_synthetic.py`) now uses
`YEONGDEOK_2025` and emits a CRS-tagged GeoJSON with WGS84 lon/lat coords
per RFC 7946.

---

## Still open — Session 2 still has known limits

### 3. Huygens elliptical wavelet flank ratio is small at moderate winds

**Status**: known, documented (carried from Session 1).

**Issue**: with the Anderson 1983 length-to-breadth ratio capped at
`LB_MAX = 3.0`, the eccentricity is ≈ 0.943 and the flank-rate is ≈ 5.7 %
of head-rate.

**Consequence**: in the cellular automaton, lateral spread is much slower
than downwind spread.

**To close**: optional spotting / crown-fire ignition would dominate
lateral spread in real wind-driven fires; or replace the universal
Anderson 1983 correlation with a per-fuel-model LB correlation
(Cruz & Alexander 2010). Either is a Session 4 task.

### 4. CA does not split wind and slope into a vector sum

**Status**: known simplification (carried from Session 1).

**Issue**: FARSITE combines wind and slope vectorially into an effective
direction of maximum spread (Finney 1998 §2.2.4). Our implementation
uses the wind direction alone for the ellipse major axis; slope
contributes only to the scalar R_max via Rothermel's φ_s.

**Consequence**: on steep terrain with cross-wind, the fire elongates
along the wind axis rather than along the combined vector.

**To close**: implement Finney 1998 eq. 14–17. Half a day of work.

---

## New in Session 2 — data ingestion blockers for Session 3

### 5. KFS perimeter shapefiles are not yet ingested

**What's needed**: the official KFS post-event perimeter polygons for the
three validation cases (영덕 2025, 울진/삼척 2022, 고성 2019).

**Why**: the validation harness's IoU / Sørensen-Dice / Brier metrics all
compare predicted to observed perimeter polygons. Session 2 uses stub
manifests in `data/validation_cases/*.json` with approximate ignition
points and total burn area only — the actual shapefile path is `null`.

**Expected impact**: until real perimeters are ingested, the metric
values produced by `validation.run_validation()` are not scientifically
meaningful. The pipeline runs end-to-end (see
`tests/test_validation.py::test_harness_runs_end_to_end_on_synthetic_yeongdeok`)
but the numbers are structural placeholders.

**Suggested next steps**:
1. Request KFS post-event perimeter shapefile via KFS 산불방지과 (forest
   fire prevention division).
2. Drop the shapefile under `data/raw/perimeters/<event>/`.
3. Update each manifest's `observed_perimeters_path` field.
4. Re-run `notebooks/02_yeongdeok_validation_dryrun.ipynb` and confirm
   IoU / Sørensen-Dice numbers are now defensible.

### 6. NGII DEM access is not yet wired up

**What's needed**: NGII 1:5000 digital map → 30 m DEM in EPSG:5179 for
each validation region.

**Why**: synthetic DEM is currently the only working source in
`data_io.raster.load_dem`. Slope and aspect from the synthetic DEM are
NOT representative of the real Yeongdeok / Uljin / Goseong terrain — and
slope drives Rothermel φ_s, which can change spread rates by ≥ 2× on
steep terrain.

**Expected impact**: until NGII DEM is ingested, model spread rates may
be systematically wrong for the validation cases — too slow in real
mountainous terrain, too fast in real flat terrain. Until then, all
validation numbers should be tagged as "synthetic-DEM".

**Suggested next steps**:
1. Register with NGII (https://map.ngii.go.kr/). Korean residence is
   ideal; foreign researchers can apply via 국제협력.
2. Download 1:5000 contour vector tiles for each validation region.
3. Implement the rasterise-to-EPSG:5179 path in `load_dem(source='ngii')`.
4. As an interim, NASA SRTM 30 m global is free and adequate; implement
   `load_dem(source='srtm')` first.

### 7. KFS 임상도 access is not yet wired up

**What's needed**: KFS 임상도 v1.4 (forest type map) for each validation
region.

**Why**: synthetic fuel-type raster assumes 100 % Korean Pinus
everywhere, which is correct in the Pinus belt but wrong in mixed
hardwood stands. Real validation requires the actual fuel type at each
cell — Pinus densiflora → KP_PINE, Quercus → FM9, mixed → FM10.

**Expected impact**: Yeongdeok and Uljin are predominantly Pinus, so the
synthetic fallback is qualitatively OK there. For mixed-stand Round 2+
regions (Central Mountain Belt) the synthetic is wrong.

**Suggested next steps**:
1. Register at https://map.forest.go.kr.
2. Download 임상도 v1.4 vector for each validation region.
3. Implement the species-code → fuel-model lookup in
   `load_fuel_type(source='kfs_impsangdo')`.

### 8. KOSIS / KFS / MOIS data for real vulnerability scoring

**What's needed**: the three sub-score inputs that drive
`vulnerability_score()`:

- KOSIS 시군구별 65세 이상 독거노인 통계 (rural elderly).
- KFS 시군구별 산불발생 건수 2010-2024 (fire frequency).
- MOIS 시군구별 대피소 시설 현황 (shelter density / response time).

**Why**: Session 2 uses placeholder values (clearly tagged as such with
`placeholder=True` on every `VulnerabilityScore`). The deployment-target
list `WILDFIRE_VULNERABLE_COUNTIES` is therefore plausible but not
authoritative.

**Expected impact**: low priority for the scientific defence (the
framework is what matters, not the exact numbers); high priority for
making concrete claims about "% of vulnerable Koreans covered" in the
submission narrative.

**Suggested next steps**:
1. Pull KOSIS aggregated 시군구별 인구통계 via OpenAPI.
2. Pull KFS 산불통계 annual reports.
3. Pull MOIS 안전지표 통계.
4. Replace `_PLACEHOLDER_SCORES` in `src/wildfireguardian/utils/vulnerability.py`.

### 9. KMA AWS access for Uljin / Goseong dates is not wired up

**What's needed**: KMA AWS (Automated Weather Station) hourly wind /
RH / T data for March 2019, March 2022, March 2025 within the
validation-case bboxes.

**Why**: The validation harness currently uses a single uniform
`WindField` for the whole region. Real validation needs spatially
varying winds interpolated from KMA AWS stations to reproduce the
observed wind regime.

**Expected impact**: medium. Wind matters a lot for Rothermel; a uniform
wind is the largest source of model-vs-observed discrepancy after the
fuel-type raster.

**Suggested next steps**:
1. Register at https://data.kma.go.kr/, request a service key.
2. Download hourly AWS data for the three event windows.
3. Implement an IDW or kriging interpolator that produces a spatial
   wind field on demand — `data_io.weather.load_kma_aws_interpolated(...)`.
4. Subclass `WindField` to wrap it spatially.

### 10. Korean fuel parameters are still analog values

**What's needed**: published Korean field-measured fuel-load and SAV
data for Pinus densiflora stands.

**Why**: the `KOREAN_PINUS` model in
`src/wildfireguardian/spread_model/rothermel/fuel_model.py` uses values
adapted from FM10 + qualitative Pinus densiflora morphology. They are
flagged as analog in `docs/methodology/korean_fuel_model.md`.

**Expected impact**: low to medium. Order-of-magnitude spread rates are
right; absolute values may shift by ±30 % once real Korean field data
replaces the analog.

**Suggested next steps**:
1. Search KFRI (Korea Forest Research Institute) publications for Lee et
   al. 2002 fuel-load surveys.
2. Search KIFM (Korean Institute of Fire Mathematical Modeling) for
   stand-level Pinus densiflora fuel parameter tables.
3. Replace the analog values in `_make_korean_pinus_fuel()`.

---

## Genuine blockers

**None.** All five Session 2 deliverables complete; all 143 unit tests
pass. Pipeline runs end-to-end with synthetic data; real-data ingestion
is a Session 3 deliverable, not a Session 2 blocker.
