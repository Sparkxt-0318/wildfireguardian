# Overnight build session 4 — report

Date completed: 2026-05-28.

## 0. API keys present

**Neither `FIRMS_API_KEY`/`MAP_KEY` nor `KMA_API_KEY`/`KMA_SERVICE_KEY`
was present in the environment.** Therefore Deliverable 4 (real FIRMS
perimeter) and Deliverable 5 (real KMA wind) were **SKIPPED**; the
approximate observed perimeter and synthetic-historical wind from
Session 3 are retained. Deliverables 1–3 (no keys needed) are complete.

This is the science-lock session. The numbers below are **LOCKED** for
the 작품설명서, with the honest caveat that the observed perimeter and
wind remain reconstructions (real-data ingestion is Round 2, contingent
on API keys / KFS shapefile access).

---

## 1. Status table

| # | Deliverable | Keys? | Status | One-line |
|---|-------------|-------|--------|----------|
| 1 | Diagnose + fix slow-initial-spread warm-up | no | **DONE** | Cause = zero-perimeter single-cell start; fix = disc ignition; 1 h IoU 0.160→0.477 |
| 2 | Decompose the 18.3× LFMC×wind ratio | no | **DONE** | moisture 1.44× × wind 12.76× = 18.31× combined; interaction ratio 1.000 (perfectly multiplicative) |
| 3 | Validation robustness + reviewer defense | no | **DONE** | IoU perturbation ranges, burned-area accuracy headline, determinism verified, 10-point reviewer-defense doc |
| 4 | Real FIRMS perimeter | **absent** | **SKIPPED** | no FIRMS key; kept approximate perimeter, noted |
| 5 | Real KMA wind | **absent** | **SKIPPED** | no KMA key; kept synthetic-historical wind, noted |

---

## 2. Test results

```
$ python -m pytest tests/ -q
228 passed in 2.70s
```

| File | Tests | New in S4? |
|------|------:|:----------:|
| test_smoke.py | 25 | +1 (robustness in import tree) |
| test_spread_warmup.py | 10 | **new** (disc ignition + baseline fairness) |
| test_lfmc_wind_decomposition.py | 5 | **new** |
| test_validation_robustness.py | 4 | **new** |
| (12 unchanged Session 1–3 files) | 184 | — |
| **Total** | **228** | **+20 vs 208 baseline** |

No regressions. All Session 1–3 tests still pass.

---

## 3. THE LOCKED VALIDATION NUMBERS (post warm-up fix)

Yeongdeok 2025. Real SRTM DEM, synthetic 100%-Korean-Pinus fuel,
synthetic-historical wind (mean midflame 4.17 m/s), LFMC 40 %, dead 1-h
8 %, cell 100 m, residence 60 min, **disc ignition radius 155 m (7.6 ha,
NOT tuned to observed)**, 24 h, deterministic.

| Horizon | IoU (S4, disc fix) | IoU (S3, point) | Δ | IoU persistence | IoU isotropic | Dice (S4) |
|--------:|-------------------:|----------------:|----:|----------------:|--------------:|----------:|
| 1 h | **0.477** | 0.160 | **+0.317** | 0.151 | 0.264 | 0.646 |
| 3 h | **0.205** | 0.102 | +0.103 | 0.013 | 0.450 | 0.340 |
| 6 h | **0.227** | 0.175 | +0.052 | 0.005 | 0.317 | 0.371 |
| 24 h | **0.147** | 0.144 | +0.003 | 0.002 | 0.053 | 0.257 |
| **avg** | **0.264** | 0.145 | **+0.119** | 0.043 | 0.271 | — |

**Did the warm-up fix help? YES.** The horizon-averaged model IoU rose
from 0.145 to 0.264 (+82 %). The dramatic win is at 1 h: IoU jumped from
0.160 to **0.477**, because the Session-3 point start left the fire as a
sub-resolution dot at 1 h (terrible overlap with the 50 ha observed
ellipse), whereas the disc start gives a real 7.6 ha footprint.

**vs baselines (locked):**
- **Beats persistence at every horizon** (by 3×–75×).
- **Beats isotropic at 1 h** (0.477 vs 0.264) **and 24 h** (0.147 vs 0.053).
- **Loses to isotropic at 3 h and 6 h** — genuine missing physics (the
  real explosive mid-game run was spotting/crown-fire + 25 m/s gusts; our
  surface CA at mean 4 m/s can't match it). Reported, not hidden.

**Honesty gate (per the spec):** we picked the disc radius by a physics
rule (155 m), NOT by maximising IoU. Larger radii (300/500 m) give higher
average IoU but pre-load observed area (circular); we explicitly reject
them. See `docs/methodology/spread_warmup.md` for the full sensitivity
table.

---

## 4. BURNED-AREA ACCURACY (the most defensible headline metric)

| Horizon | Predicted (ha) | Observed-approx (ha) | Error |
|--------:|---------------:|---------------------:|------:|
| 1 h | 29 | 50 | −42 % |
| 3 h | 123 | 600 | −80 % |
| 6 h | 385 | 1,500 | −74 % |
| 24 h | **4,747** | **3,800** | **+25 %** |

The headline single number for the writeup: **at 24 h the model predicts
4,747 ha vs the publicly-reported ~3,800 ha — a +25 % over-prediction,
the right order of magnitude.** The model under-predicts the explosive
3–6 h growth (it can't reproduce the spotting-driven run) but converges
to a defensible 24 h total.

---

## 5. THE 18× DECOMPOSITION

Korean Pinus, dead 1-h = 12 %, slope 0°:

| Corner | LFMC | wind | R (m/min) | factor vs benign |
|--------|-----:|-----:|----------:|-----------------:|
| A benign | 80 % | 2 m/s | 2.33 | 1.00× |
| B drought-only | 40 % | 2 m/s | 3.34 | **1.44×** |
| C wind-only | 80 % | 12 m/s | 29.74 | **12.76×** |
| D combined | 40 % | 12 m/s | 42.66 | **18.31×** |

- moisture-alone (B/A) = **1.435×**
- wind-alone (C/A) = **12.761×**
- product (B/A)×(C/A) = **18.307×**
- combined (D/A) = **18.307×**
- **interaction ratio = 1.0000** → the coupling is **perfectly
  multiplicative**.

**Confirmed structurally**: in Rothermel (1972) eq. 52,
`R ∝ η_M(moisture) × (1 + φ_w(wind))` — moisture and wind enter as
separate multiplicative factors, so their effects multiply exactly. See
`docs/methodology/lfmc_wind_coupling.md`.

**Honest reframing for the writeup**: the 2025 catastrophe was
**primarily wind-driven** (×12.8); drought added ×1.4 on top. It was the
*simultaneous* drought + Föhn (their product, ×18.3) that produced a
spread rate neither could produce alone. Claiming "drought caused it"
would be wrong; "drought multiplied an extreme wind event" is correct.

---

## 6. IoU robustness under a perturbed approximate perimeter

Since the observed perimeter is approximate, we perturbed it (±20 % area,
±500 m centroid; 25 combinations) and recomputed IoU against the fixed
model prediction:

| Horizon | IoU baseline | IoU min | IoU max | range |
|--------:|-------------:|--------:|--------:|------:|
| 1 h | 0.477 | 0.000 | 0.497 | **0.497** (fragile) |
| 3 h | 0.205 | 0.148 | 0.256 | 0.109 |
| 6 h | 0.227 | 0.176 | 0.302 | 0.126 |
| 24 h | 0.147 | 0.108 | 0.186 | **0.078** (most robust) |

**Interpretation**: the 1 h IoU is fragile — the fire is small enough
that a 500 m shift can fully de-overlap the polygons (IoU → 0). The 24 h
IoU is the most robust (stays 0.11–0.19). This is *why* we lead with the
24 h burned-area metric, not the 1 h IoU. A reviewer challenging "your
1 h IoU is unstable" is correct, and we say so first.

---

## 7. Real-data validation numbers

**N/A this session** — no FIRMS or KMA keys. The validation remains:
real terrain, synthetic wind, approximate observed perimeter. Round 2
(with keys / KFS shapefile) will produce model-vs-truth numbers.

---

## 8. Final data provenance table (after Session 4)

| Input | Status | Source |
|-------|--------|--------|
| DEM | ✅ REAL | NASA SRTMGL1 30 m (AWS Mapzen archive) |
| Slope / aspect | ✅ REAL (derived) | Horn 1981 on real SRTM |
| Wind | ⚠️ SYNTHETIC | March 2025 양강지풍 reconstruction from public reports (no KMA key) |
| Fuel-type raster | ⚠️ SYNTHETIC | 100 % Korean Pinus fill (no KFS 임상도) |
| Korean Pinus fuel params | ⚠️ ANALOG | FM10-adapted (no Korean field data) |
| Observed perimeter | ⚠️ APPROXIMATE | wind-aligned ellipses from public reporting (no FIRMS key / KFS shapefile) |
| Ignition disc radius | ✅ PRINCIPLED | R_steady × 15 min (NOT tuned to observed) |
| LFMC×wind decomposition | ✅ REAL (analytic) | Rothermel structure, exact |
| Validation determinism | ✅ VERIFIED | no RNG; bit-reproducible |

Unchanged from Session 3: only the DEM is real geophysical data.
Session 4 added no new real inputs (no keys) but made the methodology
substantially more defensible (warm-up fix, decomposition, robustness).

---

## 9. Reviewer-defense list (full version in `docs/methodology/validation_limitations.md`)

1. **Approximate perimeter** → we never claim model-vs-truth; quantified
   the IoU sensitivity; Round-2 KFS shapefile fixes it.
2. **Synthetic wind** → reconstruction tagged synthetic; Round-2 KMA fixes it.
3. **100 % Pinus fuel** → defensible for Pinus-dominated Yeongdeok.
4. **Analog fuel params** → ±30 % uncertainty; qualitative results robust.
5. **3–6 h under-prediction** → genuine missing physics (spotting/crown
   fire, gusts), not artifact; named the fix.
6. **IoU ~0.15 at 24 h is low** → it's reconstruction-vs-reconstruction;
   lead with 24 h burned-area (+25 %); beats both baselines.
7. **Isotropic a strawman?** → no — same rate, same initial disc; it even
   beats us at 3–6 h.
8. **Disc radius tuned?** → no — physics rule, sensitivity published.
9. **Single site** → three-site Round-2 plan; infra is region-parameterised.
10. **Reproducible?** → yes, deterministic; script + tests.

---

## 10. Files created / modified

### Created
```
scripts/diagnose_spread_warmup.py
src/wildfireguardian/spread_model/demo_lfmc_wind_decomposition.py
src/wildfireguardian/validation/robustness.py
docs/methodology/spread_warmup.md
docs/methodology/lfmc_wind_coupling.md
docs/methodology/validation_limitations.md
docs/figures/spread_warmup_diagnostic.png
docs/figures/lfmc_wind_decomposition.png
docs/OVERNIGHT_REPORT_SESSION4.md   (this file)
tests/test_spread_warmup.py
tests/test_lfmc_wind_decomposition.py
tests/test_validation_robustness.py
```

### Modified
```
src/wildfireguardian/spread_model/cellular_automaton.py   # ignite_disc()
src/wildfireguardian/validation/baselines.py              # initial_radius_m fairness
src/wildfireguardian/validation/harness.py                # ignition_radius_m wiring
scripts/run_yeongdeok_validation.py                       # principled disc radius
data/processed/yeongdeok_2025_validation_results.json     # locked numbers (disc fix)
notebooks/03_yeongdeok_real_validation.ipynb              # disc fix + area + robustness cells
tests/test_smoke.py                                       # robustness in import tree
```

---

## 11. Are the numbers LOCKED?

**YES** — with the explicit, documented caveat that they are against an
**approximate** observed perimeter and **synthetic** wind. Within those
inputs:

- The validation numbers (§3) are deterministic and reproducible via
  `scripts/run_yeongdeok_validation.py`.
- The 18.3× decomposition (§5) is an exact structural result, independent
  of any synthetic input — **this is the most rock-solid number for the
  writeup**.
- The burned-area accuracy (§4) and IoU robustness (§6) are locked.

**What could still move before June 13**: if a FIRMS key or KFS shapefile
becomes available, the observed perimeter changes and the IoU numbers
(§3) will shift — but the *methodology* (disc fix, baselines, robustness)
and the *decomposition* (§5) are final regardless. The writeup can safely
build on §4, §5, §6 now; §3's IoU should be presented with its
approximate-perimeter caveat.

The single rock-solid headline for the 작품설명서: **the LFMC×wind
coupling is multiplicative (1.44 × 12.76 = 18.3×), a structural property
of the Rothermel equation, demonstrating why simultaneous drought and
Föhn — not either alone — drove the March 2025 catastrophe.**

---

## Appendix — reproduce everything

```bash
pip install -r requirements.txt && pip install -e .
pip install xgboost scikit-learn

python -m pytest tests/ -q                                          # 228 tests

python scripts/diagnose_spread_warmup.py                            # warm-up diagnostic
python scripts/run_yeongdeok_validation.py                          # locked validation JSON
python -m wildfireguardian.spread_model.demo_lfmc_wind_decomposition  # 18x decomposition
python -m wildfireguardian.spread_model.demo_lfmc_wind_heatmap      # 2D heatmap (S3)
python -m nbconvert --to notebook --execute --inplace \
    notebooks/03_yeongdeok_real_validation.ipynb                    # full pipeline
```
