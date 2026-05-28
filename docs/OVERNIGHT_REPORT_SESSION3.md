# Overnight build session 3 — report

Date completed: 2026-05-28.

## TL;DR

**Tier 1 (all 5 deliverables) DONE. Tier 2 (both deliverables) DONE.**
**208/208 unit tests pass** (up from the 143 Session-2 baseline: +65 new,
0 regressions).

This session turned "designed system" into "system with quantitative
results." The Yeongdeok 2025 validation now runs on **real NASA SRTM 30 m
terrain** and produces honest IoU / Dice numbers against two baselines:
our model beats the persistence null model at every horizon and beats the
isotropic baseline at the 24 h horizon (it loses to isotropic at 1–6 h
because of a documented slow-initial-spread limitation). The LFMC × wind
2D heatmap (the writeup centerpiece) shows an **18×** spread-rate
amplification between typical-quiet and drought-Foehn conditions.

**Scientific-honesty status**: every synthetic / approximate / analog
input is explicitly tagged in code (xarray attrs, GeoJSON properties,
dataclass metadata) AND in the provenance table below. The DEM is real;
the wind, fuel raster, observed perimeter, and Korean fuel parameters are
NOT. We do not present any of them as confirmed-correct.

---

## 1. Status table

### TIER 1 — must produce results for June 13

| # | Deliverable | Status | One-line |
|---|-------------|--------|----------|
| 1 | Real SRTM DEM ingestion | **DONE** | `load_dem(source='srtm')` downloads + reprojects real NASA SRTMGL1 30 m; Yeongdeok terrain 0–820 m with East Sea at 0 m |
| 2 | KMA AWS wind | **DONE (synthetic fallback)** | `load_aws_wind`; KMA API path stubbed (no key), synthetic-historical reconstruction of March 2025 양강지풍 from public reporting, fully tagged |
| 3 | Approximate Yeongdeok perimeter | **DONE** | 11-feature wind-aligned ellipse time series, ~3,800 ha final, every feature tagged `provenance: approximate, reconstructed from public reporting` |
| 4 | End-to-end validation + baselines | **DONE** | `run_validation_with_baselines`; results JSON + notebook; our model beats persistence at all horizons, beats isotropic at 24 h (loses 1–6 h, documented) |
| 5 | LFMC × wind 2D heatmap | **DONE** | `lfmc_wind_sensitivity_heatmap.png`; 18× drought-Foehn-vs-quiet ratio |

### TIER 2 — nice to have (done because Tier 1 finished with tests green)

| # | Deliverable | Status | One-line |
|---|-------------|--------|----------|
| 6 | LFMC retrieval scaffold | **DONE** | `lfmc_model/retrieval.py`; Rao 2020 / Wang 2019 feature set + XGBoost; synthetic-fit R²≈0.79; tagged do-not-use-for-production |
| 7 | Smoke dispersion stub | **DONE** | `smoke_dispersion/gaussian_plume.py`; Pasquill-Gifford plume; `smoke_plume_demo.png`; labelled architecture-demo |

### TIER 3 — correctly NOT built this session

Real KFS shapefiles, real Sentinel-1 ingestion, full Korean-trained LFMC,
Uljin/Goseong validation, production smoke model. All listed as Round 2
(August) in `docs/BLOCKERS.md`.

---

## 2. Test results

```
$ python -m pytest tests/ -q
........................................................................ [ 34%]
........................................................................ [ 69%]
................................................................         [100%]
208 passed in 2.69s
```

| File | Tests | New in S3? |
|------|------:|:----------:|
| test_smoke.py | 15 | expanded import tree |
| test_rothermel.py | 12 | — |
| test_rothermel_multiclass.py | 19 | — |
| test_cellular_automaton.py | 12 | — |
| test_regions.py | 30 | — |
| test_firegrid_crs.py | 13 | — |
| test_raster_ingestion.py | 17 | 1 updated (SRTM no longer stubbed) |
| test_validation.py | 24 | — |
| **test_srtm_dem.py** | 12 | **new** |
| **test_weather.py** | 13 | **new** |
| **test_validation_session3.py** | 13 | **new** |
| **test_lfmc_retrieval.py** | 9 | **new** |
| **test_smoke_dispersion.py** | 10 | **new** |
| **Total** | **208** | **+65 vs 143 baseline** |

No regressions. Session 1 (39) + Session 2 (104) tests all still pass.

---

## 3. THE VALIDATION NUMBERS

Yeongdeok 2025 retrospective. Configuration: real SRTM DEM, synthetic
100%-Korean-Pinus fuel, synthetic-historical wind (mean midflame 4.17 m/s
from 282°), LFMC 40 %, dead 1-h 8 %, cell 100 m, residence 60 min,
24 h run. Compared to the **approximate** observed perimeter.

| Horizon | Observed (ha) | Our model (ha) | **IoU model** | IoU persistence | IoU isotropic | Dice model |
|--------:|--------------:|---------------:|--------------:|----------------:|--------------:|-----------:|
| 1 h | 50 | 8 | **0.160** | 0.020 | 0.411 | 0.276 |
| 3 h | 600 | 61 | **0.102** | 0.002 | 0.490 | 0.185 |
| 6 h | 1,500 | 271 | **0.175** | 0.001 | 0.344 | 0.298 |
| 24 h | 3,800 | 4,447 | **0.144** | 0.000 | 0.054 | 0.252 |

**Do we beat the baselines? — stated plainly:**

- **vs persistence (null model)**: YES, decisively, at every horizon —
  our model's IoU is 8× to 550× higher. Persistence stays at one cell.
- **vs isotropic (wind-ignorant circle)**: MIXED, and honestly so:
  - At **1 h, 3 h, and 6 h**: isotropic WINS (0.41 / 0.49 / 0.34 vs our
    0.16 / 0.10 / 0.18). Our cellular automaton has slow initial spread —
    the heat-accumulator needs several timesteps to ignite the first ring
    of neighbours, so in the first 6 hours we under-predict area badly
    (8 ha vs 50 ha; 61 ha vs 600 ha; 271 ha vs 1500 ha). A growing circle
    happens to fit the small early observed ellipse better than our
    too-small teardrop.
  - At **24 h**: our model WINS clearly (0.144 vs 0.054) — the isotropic
    circle has by now grown into a vast disk that massively overshoots the
    wind-elongated real burn, while our wind-aligned teardrop stays close
    to the elongated observed shape.

**Honest headline**: our model beats persistence everywhere and beats the
isotropic baseline at the 24 h horizon (the one that matters most for
total burned area). At the 1–6 h horizons the isotropic baseline is better
because our CA's initial spread is too slow — a real, documented
limitation (the heat-accumulator warm-up), not something we hid. Fixing
the warm-up is Session 4 priority #4.

**Total area at 24 h**: our model 4,447 ha vs observed-approx 3,800 ha —
within ~17 %, the right order of magnitude. This is the most defensible
single number: with real terrain + Korean Pinus fuel + reconstructed wind,
the model lands the 24-hour burned area within 20 % of the publicly
reported figure.

⚠️ **These IoU numbers compare two reconstructions** (our model vs an
approximate observed perimeter), NOT model-vs-ground-truth. Real KFS
perimeter validation is Round 2.

---

## 4. THE HEADLINE LFMC × WIND NUMBER

From `demo_lfmc_wind_heatmap.py`, Korean Pinus multi-class fuel, dead 1-h
moisture fixed at 12 % (typical Korean spring), slope 0°:

| Scenario | LFMC | midflame wind | **R (m/min)** |
|----------|-----:|--------------:|--------------:|
| Typical summer quiet | 80 % | 2 m/s | **2.33** |
| Yeongdeok 2025-like | 40 % | 4 m/s | **8.66** |
| Drought + Foehn | 40 % | 12 m/s | **42.66** |

- **R(LFMC 40 %, 12 m/s) / R(LFMC 80 %, 2 m/s) = 18.3×** ← the honest
  headline coupling number.
- R(LFMC 40 %, 4 m/s) / R(LFMC 80 %, 2 m/s) = 3.7× (the Yeongdeok-event
  point alone).

The 18× is **multiplicative**: low LFMC raises reaction intensity (via the
moisture damping coefficient η_M) AND high wind raises the wind
coefficient φ_w. Neither factor alone gets near 18×; their product does.
This is exactly the regime that made March 2025 catastrophic — and the
2D heatmap (`docs/figures/lfmc_wind_sensitivity_heatmap.png`) makes it
visible at a glance.

---

## 5. Data provenance table

| Input | Status | Source | Tagged in code? |
|-------|--------|--------|-----------------|
| **DEM** | ✅ REAL | NASA SRTMGL1 30 m via AWS Mapzen archive | `dem.attrs['source']='srtm'`, `synthetic=False`, citation in attrs |
| Slope / aspect | ✅ REAL (derived) | Horn 1981 gradient on real SRTM | computed in `compute_slope_aspect` |
| **Wind** | ⚠️ SYNTHETIC | Reconstruction of March 2025 양강지풍 from public KMA/news reports | `WindSeries.synthetic=True`, `provenance` string |
| **Fuel-type raster** | ⚠️ SYNTHETIC | 100% Korean Pinus fill | `fuel.attrs['synthetic']=True` |
| **Korean Pinus fuel params** | ⚠️ ANALOG | FM10-adapted + Pinus morphology | `docs/methodology/korean_fuel_model.md`, flagged analog |
| **Observed perimeter** | ⚠️ APPROXIMATE | Wind-aligned ellipse from public reporting, ~3,800 ha | every GeoJSON feature `provenance` property |
| LFMC value (validation) | ⚠️ ASSUMED | 40 %, KFS post-event field estimate (public) | manifest |
| LFMC retrieval model | ⚠️ SYNTHETIC | Trained on synthetic data mimicking Rao 2020 | `metadata.do_not_use_for_production=True` |
| Smoke plume | ⚠️ DEMO | Textbook Pasquill-Gifford, coarse emission factor | figure caption + module docstring |
| Validation metrics code | ✅ REAL | Standard IoU/Dice/Brier (cited) | — |

**One-sentence honest summary**: the only real geophysical input in the
Yeongdeok validation is the terrain; everything else is a clearly-labelled
synthetic or approximate placeholder pending Round 2 data ingestion.

---

## 6. File inventory

### Created

```
scripts/build_yeongdeok_approx_perimeter.py
scripts/run_yeongdeok_validation.py

src/wildfireguardian/data_io/weather.py
src/wildfireguardian/lfmc_model/retrieval.py
src/wildfireguardian/smoke_dispersion/gaussian_plume.py
src/wildfireguardian/smoke_dispersion/demo_yeongdeok_plume.py
src/wildfireguardian/spread_model/demo_lfmc_wind_heatmap.py
src/wildfireguardian/validation/baselines.py

data/validation_cases/yeongdeok_2025_perimeter_approx.geojson  (approx, public-source)
data/processed/yeongdeok_2025_validation_results.json          (5 KB metrics artifact)

docs/figures/lfmc_wind_sensitivity_heatmap.png                 (writeup centerpiece)
docs/figures/smoke_plume_demo.png                              (architecture demo)
docs/OVERNIGHT_REPORT_SESSION3.md                              (this file)

notebooks/03_yeongdeok_real_validation.ipynb                   (submission artifact)

tests/test_srtm_dem.py            (12)
tests/test_weather.py             (13)
tests/test_validation_session3.py (13)
tests/test_lfmc_retrieval.py      (9)
tests/test_smoke_dispersion.py    (10)
```

### Modified

```
.gitignore                                              # whitelist validation results JSON
README.md                                               # Session 3 status + headline numbers
data/validation_cases/yeongdeok_2025.json               # point at approx perimeter
docs/BLOCKERS.md                                        # SRTM resolved; new Round-2 blockers
docs/methodology/lfmc.md                                # implemented scaffold section
src/wildfireguardian/data_io/raster.py                  # real SRTM ingestion + slope/aspect
src/wildfireguardian/lfmc_model/__init__.py             # export retrieval
src/wildfireguardian/smoke_dispersion/__init__.py       # export gaussian_plume
src/wildfireguardian/validation/__init__.py             # export baselines + with-baselines harness
src/wildfireguardian/validation/harness.py              # run_validation_with_baselines + observed series
tests/test_raster_ingestion.py                          # SRTM no longer "not implemented"
tests/test_smoke.py                                     # expanded import tree
```

### Not committed (gitignored, regenerable)

```
data/raw/dem/srtm/N36E129.hgt(.gz)   # 25 MB real SRTM tile — auto-downloaded on demand
data/cache/*.nc                       # raster cache
```

---

## 7. Honest limitations — what a reviewer could challenge

1. **"Your IoU is only 0.14 — that's poor."** Correct, and we say so. But
   (a) it's against an *approximate* observed perimeter, not KFS ground
   truth, so it measures reconstruction-vs-reconstruction; (b) the 24-h
   total burned area is within 17 % of the reported figure, which is the
   more defensible number; (c) we beat persistence by 100× and isotropic
   at 24 h.

2. **"The wind is made up."** Yes — it's a public-reporting reconstruction
   of the 양강지풍 episode, tagged synthetic everywhere. Real KMA AWS is
   Round 2. The qualitative pattern (sustained westerly, peak Mar 22-23)
   matches reporting.

3. **"100% Korean Pinus everywhere is unrealistic."** Correct. Yeongdeok
   is predominantly Pinus so it's a defensible first approximation, but
   real KFS 임상도 stand classification is Round 2.

4. **"Korean Pinus fuel parameters are guessed."** They are FM10-adapted
   analog values, explicitly flagged. Order-of-magnitude right; absolute
   values may move ±30 % with real Korean field data.

5. **"Initial spread is too slow."** Real, documented CA limitation (the
   heat-accumulator warm-up). The isotropic baseline beats us at 1-3 h.
   We report this rather than hiding it.

6. **"LFMC retrieval model isn't real."** Correct — it's a methodology
   scaffold trained on synthetic data, tagged `do_not_use_for_production`.
   It demonstrates the pipeline; real Korean training data is Round 2.

7. **"Smoke model isn't validated."** Correct — Gaussian plume is an
   architecture demo, labelled as such.

8. **LB cap of 3.0** still makes our fire less elongated than reality
   (carried BLOCKERS-3), contributing to the 24-h over-prediction of area.

---

## 8. Session 4 priorities

In priority order for the June 13 deadline (writeup needs results locked
~June 8):

1. **Ingest the real KFS Yeongdeok perimeter shapefile.** This is the
   single highest-value action — it turns every IoU number from
   "reconstruction-vs-reconstruction" into "model-vs-truth." Request via
   KFS 산불방지과.

2. **Real KMA AWS wind for March 2025.** Replace the synthetic-historical
   reconstruction. Register for a data.kma.go.kr key, implement
   `load_aws_wind(source='kma')`.

3. **KFS 임상도 fuel-type raster.** Replace the 100%-Pinus synthetic with
   real stand classification.

4. **Tune the CA initial-spread warm-up.** The slow 1-3 h spread is the
   biggest model deficiency vs baselines; consider seeding the
   heat-accumulator or a sub-grid initial-ignition kernel.

5. **Korean field fuel parameters.** Search KFRI / KIFM literature; replace
   the FM10-analog Korean Pinus values.

6. **Uljin/Samcheok 2022 + Goseong 2019 validation** once 1-3 are in place
   — gives the three-site validation backbone for the writeup.

If only #1 and #2 land before June 8, the submission has a defensible
"real terrain + real wind + real perimeter, synthetic fuel" validation —
a strong planning-stage result.

---

## Appendix — reproduce the headline artifacts

```bash
pip install -r requirements.txt && pip install -e .
pip install xgboost scikit-learn          # for the LFMC scaffold

# all tests (208)
python -m pytest tests/ -q

# headline validation numbers → data/processed/yeongdeok_2025_validation_results.json
python scripts/run_yeongdeok_validation.py

# centerpiece figure → docs/figures/lfmc_wind_sensitivity_heatmap.png
python -m wildfireguardian.spread_model.demo_lfmc_wind_heatmap

# smoke demo → docs/figures/smoke_plume_demo.png
python -m wildfireguardian.smoke_dispersion.demo_yeongdeok_plume

# rebuild the approximate perimeter (if needed)
python scripts/build_yeongdeok_approx_perimeter.py
```
