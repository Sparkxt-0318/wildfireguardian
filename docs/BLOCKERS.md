# Known limitations & blockers

This document records issues encountered during overnight builds that the
next session (or the human collaborator) will need to address. Each entry
is honest about what was tried, what didn't work, and what would be
needed to close it out.

---

## Session 7 (diagnostic) — the crown result was a bug

### ✅ FIXED: crown foliar-moisture conflation (the "54 %" artifact)
The Session-6 crown trigger fed the surface drought-LFMC (40 %) into the
Van Wagner tree-crown check; live crowns are ~119 % (measured). Fixed by
decoupling `crown_foliar_moisture_pct`. **Corrected result: crown
initiation ~0 %, 24-h capture ~9 %** (was the artifact 54 %). See
`docs/OVERNIGHT_REPORT_SESSION7.md`.

### ⚠️ RE-OPENED (the real bottleneck): surface fire too weak to crown
With realistic foliar moisture, the WAF-corrected surface intensity
(I_B ≲ 1500 kW/m) never reaches the Van Wagner critical intensity (1686
kW/m at CBH 4 m). So the surface→crown trigger alone cannot reproduce the
(real, crown-driven) 2025 event. **The limiting factor is the surface
intensity, not the crown threshold** — re-attack via real gusty KMA wind
and a re-examination of the WAF / provisional surface fuel. This is the #1
scientific gap, restored from Session 5.

### Finding (not a blocker): crown initiation is CBH-sensitive
Capture ~9 % at measured CBH (3.6–5.2 m), ~27 % at CBH 2 m. Stand structure
governs crown potential — documented as a contribution, with an uncertainty
band replacing the point estimate.

---

## Session 6 (fire-type physics) — progress and remaining gaps

### ✅ ADDRESSED: surface-only model missed ~90 % (the S5 #1 gap)
Added crown fire (Van Wagner 1977 + Cruz/Alexander 2005), spotting (Albini
1979), topographic wind (Föhn heuristic), and a rule-based regime
classifier. 24 h area capture 9 % → **54 %** (crown) / 59 % (spotting), IoU
0.086 → **0.295**. Crown fire is the dominant recovery (32 % of cells reach
active crown). See `docs/OVERNIGHT_REPORT_SESSION6.md`.

### ⚠️ STILL OPEN — early-front under-prediction (1–3 h)
Capture stays ≤ 1 % in the first 3 h across all configs. The CA needs time
to develop crowning and the real fire's early explosive run isn't captured.
**Fix:** faster crown onset + real gusty wind time series.

### ⚠️ STILL OPEN — over-prediction / no containment
Crown over-predicts 24 h area by +38 %; spotting by +104 %. There is no
suppression / fuel-break / containment model, so spotting runs away.
**Fix:** a containment model or a Monte-Carlo burn-probability framing to
restore precision (IoU peaked at ~0.30).

### Heuristic / provisional pieces added this session (flagged)
- Topographic-wind coefficients (k_slope, channel gain, lee factor) are
  cited heuristics, not calibrated to Korean obs.
- Albini spotting constants (loft ratio, drift coeff) are calibrated to
  magnitude, not validated.
- Korean canopy CBH/CBD/FMC are measured (Lee et al. 2018); the Rothermel
  *surface* bed remains provisional (carried from S5).

---

## Session 5 (mentor refocus) — resolved, corrected, and newly-exposed

### ✅ RESOLVED: missing Wind Adjustment Factor (the root wind bug)
Rothermel needs **midflame** wind; the code fed raw 10-m / station wind into
φ_w, inflating the wind factor to ~115×. `spread_model/wind.py` now applies
the Andrews 2012 WAF (closed Korean pine canopy WAF ≈ 0.10), giving a
corrected wind factor ~5×. All wind now routes through this conversion.

### ✅ CORRECTED (retracted): tautological "multiplicative coupling"
The Session-4 "interaction ratio = 1.000" was a tautology (Rothermel is
separable). Replaced by the dimensional cross-partial ∂²R/∂M∂U and the
marginal wind effect ∂R/∂U (`spread_model/interaction.py`,
`docs/methodology/interaction.md`).

### ⚠️ NEWLY EXPOSED (genuine, unresolved): surface model under-predicts ~90%
With physically-correct midflame wind, the Rothermel **surface** model
under-predicts the Yeongdeok front by ~90 % at every horizon. The real run
was crown/spotting-driven. **Fix needed**: a crown-fire / spotting ignition
module on top of the surface model. This is the #1 scientific gap. Until
then the spread model is insufficient to predict this event, and the
routing spine must be fed a better front than the surface model produces.

### ⚠️ PROVISIONAL: Korean surface fuel bed (not measured)
Live moisture (119 %) and canopy structure are measured (Lee et al. 2018);
the Rothermel surface bed (litter load 0.7 kg/m², depth 0.08 m, SAV
6000 m⁻¹, dead m_x 0.30) is a flagged best-estimate. **Fix needed**: Korean
surface-litter field data (KFRI/NIFoS ground-fuel surveys).

### Carried forward (need data access / a later session)
- Real KFS perimeter shapefile (validation ground truth still approximate).
- Real KMA AWS wind (still synthetic-historical reconstruction; no key).
- Real Sentinel-1/2 + Korean LFMC labels for the retrieval model.
- Real OSM pedestrian network for routing (synthetic grid used offline).
- Real fire+weather data for the empirical super-multiplicativity test
  (`empirical_interaction.py` is a synthetic-data scaffold only).

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

## ✅ RESOLVED in Session 4

### Slow-initial-spread warm-up  ✅ RESOLVED

**Status**: RESOLVED in Session 4.

**Issue (found in Session 3)**: the CA lost to the isotropic baseline at
1 h / 3 h / 6 h because a single-cell ignition has zero perimeter and
therefore takes one full cell-ring-time (~11 min at 100 m) before any
spread, and the effective rate only reaches ~91 % of steady-state by
60 min.

**Resolution**: `FireGrid.ignite_disc()` initialises the fire from a
finite established front (standard FARSITE practice). The validation uses
a principled radius (head rate × 15-min establishment ≈ 155 m, NOT tuned
to observed). 1 h IoU rose 0.160 → 0.477; horizon-averaged IoU 0.145 →
0.264. Baselines get the same initial disc for fairness. Full diagnosis
and sensitivity in `docs/methodology/spread_warmup.md`.

**Remaining (not a warm-up issue)**: the 3–6 h under-prediction is genuine
missing physics (spotting / crown fire, gusts), documented in
`docs/methodology/validation_limitations.md` — candidate Round-2 feature.

---

## ✅ PARTIALLY RESOLVED in Session 3

### BLOCKERS-6 (DEM): SRTM path implemented  ✅ (SRTM done, NGII pending)

**Status**: SRTM RESOLVED in Session 3; NGII still pending.

**Resolution**: `data_io.raster.load_dem(source='srtm')` now downloads and
ingests real NASA SRTMGL1 (30 m) tiles from the AWS Mapzen archive
(no auth required), reprojects to EPSG:5179, and derives slope/aspect via
the Horn (1981) gradient method. The Yeongdeok validation now runs on REAL
terrain (0–820 m, with the East Sea correctly at 0 m). NGII 1:5000 Korean
DEM (higher accuracy) remains a Round-2 enhancement; SRTM is an adequate
free fallback for Rothermel slope.

### BLOCKERS-2b (validation numbers): produced  ✅

**Status**: RESOLVED in Session 3 (with honest provenance caveats).

**Resolution**: `scripts/run_yeongdeok_validation.py` produces
`data/processed/yeongdeok_2025_validation_results.json` with IoU /
Sørensen-Dice at 1/3/6/24 h for our model vs persistence + isotropic
baselines. The numbers are honest: our model beats persistence at all
horizons and beats isotropic at 6 h and 24 h, but the inputs are still
mostly synthetic/approximate (see new blockers below).

---

## New in Session 2 — data ingestion blockers (status updated in Session 3)

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

### 9. KMA AWS access — synthetic reconstruction in place, real data pending

**Status update (Session 3)**: `data_io.weather.load_aws_wind` now exists
with a `synthetic_historical` path that reconstructs the March 2025
Yeongdeok 양강지풍 wind regime from PUBLIC reporting (clearly tagged
`synthetic=True`). The real KMA Open API path raises NotImplementedError
because no API key is configured.

**What's still needed**: KMA AWS hourly wind / RH / T data for March 2019,
March 2022, March 2025 within the validation-case bboxes, plus a spatial
interpolator (the current `WindField` is uniform).

**Expected impact**: medium-high. Wind matters a lot for Rothermel; the
synthetic reconstruction captures the qualitative pattern (sustained
westerly 양강지풍) but is not the actual time series. This is the largest
remaining model-vs-observed discrepancy after the fuel raster.

**Suggested next steps**:
1. Register at https://data.kma.go.kr/, request a service key; set the
   `WILDFIREGUARDIAN_KMA_API_KEY` env var.
2. Implement the HourlyObservation endpoint in `load_aws_wind(source='kma')`.
3. Add an IDW/kriging interpolator → spatial `WindField` subclass.

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

## New in Session 3 — Round 2 (August) data blockers

### 11. KFS 임상도 fuel-type raster (carried from BLOCKERS-7)

Still pending. The Yeongdeok validation uses a synthetic 100%-Korean-Pinus
fuel raster. Real KFS 임상도 stand classification is needed to assign
mixed-stand fuel models. See BLOCKERS-7 above.

### 12. Sentinel-1/2 + MODIS for real LFMC retrieval

**What's needed**: Sentinel-1 GRD (VV/VH), Sentinel-2 L2A (NDVI/NDMI/NBR),
MODIS NDVI, and Globe-LFMC 2.0 + Korean field LFMC labels.

**Why**: Session 3 implemented the LFMC retrieval scaffold
(`lfmc_model.retrieval`) but trains it on a CLEARLY-LABELLED synthetic
dataset. The trained model is tagged `do_not_use_for_production=True`.

**Expected impact**: medium. Currently LFMC is a manifest-supplied
constant (40 % for the Yeongdeok case); a real retrieval would give a
spatially-varying LFMC field.

**Suggested next steps**: see `docs/methodology/lfmc.md` Round-2 plan.

### 13. HYSPLIT / CMAQ coupling for production smoke

**What's needed**: a real atmospheric transport model for the smoke
dispersion module.

**Why**: Session 3 implemented a Gaussian-plume (Pasquill-Gifford) smoke
model (`smoke_dispersion.gaussian_plume`) as an ARCHITECTURE DEMONSTRATION.
It is not validated science — it uses textbook dispersion coefficients and
a coarse area×emission-factor source model.

**Expected impact**: low for the June 13 submission (smoke is a secondary
output); higher for the routing-penalty raster that depends on PM2.5.

---

## Genuine blockers

**None.** Session 3 Tier 1 + Tier 2 complete; all 208 unit tests pass.
The Yeongdeok validation runs end-to-end on REAL SRTM terrain and produces
honest IoU/Dice numbers vs two baselines. The remaining gaps (real KFS
perimeter, real KMA wind, real KFS fuel, Korean field fuel parameters)
are data-ingestion tasks deferred to Round 2 (August), not code blockers.
