# Data-Driven Fire-Spread Model — Per-Cell Ignition Probability

**Honest headline.** Across four well-observed Korean wildfires, a gradient-boosted
per-cell ignition classifier reaches a **leave-one-fire-out mean ROC-AUC of 0.748 ±
0.033** (predicting on fires it never saw). The skill is **not** merely "cells near
the fire burn": within the far distance band (cells 1.5–2 km from any active fire,
where raw proximity is uninformative) the full model still scores **AUC ≈ 0.74**,
while a distance-only baseline collapses toward chance (**≈ 0.60 mean, and 0.48–0.53
on the largest fires**). The single most important feature is **observed VIIRS Fire
Radiative Power (FRP)** — the intensity signal that the retired mechanistic
(Rothermel) model could not represent — followed by distance and by a data-derived
spread-direction proxy. Predicting the *exact* future footprint remains hard
(IoU ≈ 0.02–0.06 at a strict operating point); predicting *which* cells are at risk
is where the model legitimately succeeds.

All inputs are real public data — **NASA FIRMS** (VIIRS 375 m + MODIS 1 km active
fire), **SRTM** DEM (~30 m), **ESA WorldCover 2021** (10 m). No synthetic data.
Reproduce with:

```bash
python scripts/run_ignition_audit.py      # Deliverable 0
python scripts/run_ignition_pipeline.py    # Deliverables 1–6 (figures + results.json)
pytest tests/test_ignition_*.py            # tests
```

Random seed `20260530`; CRS **EPSG:5179** (Korea 2000 / Unified CS, metres); grid
**375 m** (one VIIRS I-band pixel); overpass clustering gap **60 min**; candidate
radius **2 km**. Figures in `docs/figures/ignition_model/`; machine-readable metrics
in `data/processed/ignition_model/results.json`.

---

## Why this approach (and what was retired)

A mechanistic Rothermel surface-fire cellular automaton captured only ~9 % of
observed burned area on Korean spring pine fires, because those fires are **crown-
and spotting-driven** — physics a surface model cannot represent. A later apparent
"fix" to 54 % was a bug (it confused dead surface fuel moisture, 40 %, with live
crown foliar moisture; the correct Korean value is 119 %, at which crowning
collapsed and capture returned to ~9 %). That path is retired.

This model instead **learns spread directly from observed fire progression**. The
satellites watched real fires that *did* crown and spot, so the learned signal
already contains that behaviour. We do **not** try to predict the exact future
perimeter (chaotic; too few fire-level examples). We predict, per currently-unburned
cell:

> **P(this cell ignites by the next satellite overpass | local conditions at or before now)**

a per-cell binary classification with thousands of examples, evaluated by ROC-AUC —
the metric operational fire science uses.

---

## Deliverable 0 — Data audit (run before any modelling)

8 fires were audited. The **critical finding** concerns fuel coverage: ESA
WorldCover is delivered in 3°×3° tiles split at **129°E**, and for fires straddling
that boundary only the western tile was clipped. We measured, per fire, the fraction
of detections falling inside the fuel raster's extent:

| fire | detections | overpasses* | span (h) | reported ha | **% det. in fuel** | burnable frac | decision |
|---|---:|---:|---:|---:|---:|---:|---|
| uljin_samcheok_2022 | 2372 | 29 | 254 | 16302 | **100 %** | 0.48† | **KEEP** |
| uiseong_andong_2025 | 4021 | 26 | 157 | 45000 | **89 %** | 0.94 | **KEEP** |
| hongseong_2023 (west coast) | 196 | 7 | 39 | 1454 | **100 %** | 0.86 | **KEEP** |
| miryang_2022 (late spring) | 74 | 5 | 63 | 763 | **100 %** | 0.94 | **KEEP** |
| yeongdeok_2025 | 2290 | 9 | 40 | 3800 | **9.3 %** | 0.98‡ | **FLAG — fuel-blind** |
| gangneung_donghae_2022 | 637 | 16 | 133 | 4000 | **5.0 %** | 0.88‡ | **FLAG — fuel-blind** |
| goseong_2019 | 114 | 1 | 1.7 | 700 | 100 % | 0.38 | **KEEP (sparse)** → 0 transitions |
| gangneung_2023 | 17 | 2 | 2.2 | 530 | 100 % | 0.50 | **DROP** |

\* clustered at a 60-min gap; differs from the manifest's "distinct overpass-hours"
which counts clock-hours. †uljin's bbox includes open sea (East Sea), which is
non-burnable and drags the fraction down — expected for a coastal fire. ‡the high
burnable fraction is computed over only the narrow covered sliver and is **not**
representative of the fire area.

**Decisions and reasoning.**

- **yeongdeok_2025 (9.3 %) and gangneung_donghae_2022 (5.0 %) → fuel-blind.** Both
  fires sit almost entirely *east* of 129°E; their fuel rasters cover only a thin
  western sliver (e.g. yeongdeok fuel spans lon 128.95–129.00 while the fire spreads
  to 129.45). We did **not** silently proceed. We handle fuel **per cell**: a cell
  outside fuel coverage gets `NaN` fuel features, and the `is_burnable` **hard gate**
  fires only on *known* non-burnable cells. XGBoost ingests `NaN` natively, so these
  two fires are predicted "fuel-blind." Their held-out scores are reported but
  **excluded from the headline mean**. (We keep yeongdeok because it is the project's
  flagship case — average victim age 84 — and it is honest to show how the model does
  there *without* fuel data rather than to drop it.)
- **gangneung_2023 → dropped.** 2 overpasses / 17 detections cannot show spread.
- **goseong_2019 → kept but yields nothing.** Its 114 detections fall in a single
  ~100-min afternoon multi-satellite window (16:48–18:28, sub-gaps 46/4/50 min). At a
  physically defensible 60-min overpass clustering this is **one epoch → zero
  transitions**, so goseong contributes no samples. Splitting it would model
  sensor-timing artefacts, not fire spread.

Timestamps parse and order correctly for all fires.

---

## Deliverable 1 — Observed spread sequence

Detections are projected to EPSG:5179, binned onto a 375 m grid, and grouped into
overpass epochs (60-min gap). For each epoch we build the cumulative burned mask;
cells that flip unburned→burned between epochs are the positive targets.

**Area sanity check** (cumulative burned area is monotone for every fire by
construction; VIIRS 375 m pixels over-estimate area — reported, not "fixed"):

| fire | observed ha (VIIRS) | reported ha | ratio | note |
|---|---:|---:|---:|---|
| uljin_samcheok_2022 | 16425 | 16302 | **1.01** | near-perfect |
| gangneung_donghae_2022 | 4598 | 4000 | 1.15 | expected over-estimate |
| hongseong_2023 | 1617 | 1454 | 1.11 | expected over-estimate |
| miryang_2022 | 703 | 763 | 0.92 | slight under (sparse detections) |
| goseong_2019 | 1139 | 700 | 1.63 | small fire, pixel coarseness |
| uiseong_andong_2025 | 31880 | 45000 | 0.71 | under — not every pixel of a 45 000 ha fire is caught each pass |
| **yeongdeok_2025** | 19547 | 3800 | **5.14** | **flag:** the FIRMS detections span the wider March-2025 Yeongnam outbreak (lon 128.95–129.45), far larger than the 3 800 ha "Yeongdeok" headline figure. A data-provenance caveat, not a model input. |

---

## Deliverable 2 — Features

For each overpass→overpass transition, candidate cells = currently-unburned cells
within **2 km** of any burning cell. The 2 km radius is validated by its **capture
rate** — the fraction of true new ignitions that fall inside the band: **0.76–1.00
per fire** (mean ≈ 0.90), i.e. the candidate framing misses only ~10 % of ignitions
(long-range spotting), which it cannot represent from local features anyway.

**Pooled dataset: 176 310 candidate cells, 4 369 positive (2.48 %).** Per fire:

| fire | transitions | candidates | positives | positive rate | capture |
|---|---:|---:|---:|---:|---:|
| uiseong_andong_2025 | 25 | 95089 | 1956 | 2.06 % | 0.90 |
| yeongdeok_2025 | 8 | 35322 | 1110 | 3.14 % | 0.99 |
| uljin_samcheok_2022 | 28 | 30166 | 921 | 3.05 % | 0.97 |
| gangneung_donghae_2022 | 15 | 12687 | 274 | 2.16 % | 0.88 |
| hongseong_2023 | 6 | 2003 | 77 | 3.84 % | 0.76 |
| miryang_2022 | 4 | 1043 | 31 | 2.97 % | 1.00 |

The 15 model features each encode a known mechanism (no opaque features):

- **Proximity / geometry:** `dist_to_nearest_burning_m`, `n_burning_within_500m`,
  `n_burning_within_1000m`.
- **Observed intensity (VIIRS FRP):** `frp_sum_1000m`, `frp_max_1000m`,
  `nearest_burning_frp`.
- **Terrain (SRTM):** `slope_deg`, `slope_alignment` (cos angle between the cell's
  uphill direction and the fire→cell bearing — upslope spread), `elevation_rel_m`.
- **Fuel (WorldCover):** `burnable_frac_nbhd_1000m`, one-hots `fuel_tree`,
  `fuel_shrub`, `fuel_grass`, `fuel_crop`. `is_burnable` itself is the **hard gate**
  (non-burnable cells removed from candidates), not a model feature.
- **Data-derived directionality:** `directional_alignment` = alignment of the cell to
  the fire's **own recent growth vector** (centroid shift of cells burned at epoch *t*
  vs earlier). **This is a proxy for wind-driven directionality inferred from the fire
  itself — NOT a weather input.**

**Leakage discipline:** every feature uses only information available at or before the
transition start; in particular the directionality proxy uses past growth only, never
the *t+1* target. A unit test asserts neighbour-counts at *t* reflect only cells
burned by *t*.

---

## Deliverable 3 — Leave-one-fire-out cross-validation

**Model:** `XGBClassifier`, deliberately standard/conservative hyper-parameters,
**not** tuned against held-out AUC: `n_estimators=300, max_depth=4,
learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
reg_lambda=1`, no `scale_pos_weight` (keeps probabilities honest for the Brier score;
AUC/PR-AUC are rank-based and unaffected). XGBoost is used partly because it ingests
the fuel-blind `NaN` columns natively.

**Protocol:** for each fire, train on **all other fires**, predict the held-out fire.
goseong contributes no samples (above) and gangneung_2023 is dropped, leaving 6
held-out evaluations.

| held-out fire | n | positives | **ROC-AUC** | **PR-AUC** | **Brier** | flag |
|---|---:|---:|---:|---:|---:|---|
| uiseong_andong_2025 | 95089 | 1956 | **0.787** | 0.069 | 0.0200 | |
| yeongdeok_2025 | 35322 | 1110 | **0.779** | 0.079 | 0.0310 | fuel-blind |
| uljin_samcheok_2022 | 30166 | 921 | **0.774** | 0.072 | 0.0332 | |
| gangneung_donghae_2022 | 12687 | 274 | **0.772** | 0.046 | 0.0213 | fuel-blind |
| miryang_2022 | 1043 | 31 | **0.718** | 0.059 | 0.0292 | small (31 pos) |
| hongseong_2023 (W coast) | 2003 | 77 | **0.711** | 0.077 | 0.0369 | out-of-region |

**Headline (4 fully-featured fires uljin, uiseong, hongseong, miryang): ROC-AUC 0.748
± 0.033, PR-AUC 0.069** (random baseline = prevalence ≈ 0.025, so a ~2.8× lift).
Across all 6 evaluated fires the mean is 0.757. Notes that matter:

- The **fuel-blind** fires (yeongdeok 0.779, gangneung_donghae 0.772) score *among the
  highest* — the missing fuel features cost little here because proximity, FRP and the
  directional proxy carry the prediction. An honest, slightly surprising result.
- **hongseong** (west coast, ~250 km from the east-coast training fires) at 0.711 is
  genuine cross-region generalisation: a model trained only on east/south fires
  predicts a west-coast fire it never saw, above chance and not far below the others.
- Brier scores are low (0.020–0.037), consistent with calibrated low-probability
  predictions at 2–3 % prevalence.

### Conditional AUC by distance band (the key honesty metric)

Proximity is trivially predictive; the meaningful question is discrimination **among
cells at similar distance**. AUC *within* each distance-to-fire band:

| held-out fire | ≤375 m | 375–750 m | 750–1500 m | >1500 m |
|---|---:|---:|---:|---:|
| uiseong_andong_2025 | 0.708 | 0.694 | 0.756 | **0.769** |
| uljin_samcheok_2022 | 0.755 | 0.743 | 0.733 | **0.740** |
| yeongdeok_2025 | 0.648 | 0.676 | 0.785 | **0.755** |
| gangneung_donghae_2022 | 0.597 | 0.593 | 0.801 | **0.764** |
| hongseong_2023 | 0.647 | 0.601 | 0.685 | **0.727** |
| miryang_2022 | 0.579 | 0.614 | 0.633 | 0.713¹ |

¹ only 2 positives in miryang's far band — unreliable.

**The skill does not collapse with distance — it is flat-to-rising.** Compare the far
band (>1500 m) of the full model vs the distance-only baseline:

| | far-band AUC (>1500 m) |
|---|---:|
| **Full model, headline mean** | **0.737** |
| Distance-only baseline, headline mean | 0.598 |
| Distance-only on uljin / uiseong / yeongdeok | 0.484 / 0.534 / 0.476 (≈ chance) |

On the largest, most reliable fires, raw distance is essentially **random** once you
restrict to a narrow far band, yet the full model holds ~0.74. That residual skill
comes from FRP, the directional proxy, terrain and fuel — exactly the "skill beyond
proximity" this evaluation was built to test. See
`docs/figures/ignition_model/conditional_auc.png`.

### Footprint reconstruction (continuity with the mechanistic ~9 %)

At a **prevalence-matched** operating point (call exactly as many cells positive as
actually ignited — a non-tuned threshold):

| held-out fire | IoU@K | recall@K | recall@2K | recall@3K |
|---|---:|---:|---:|---:|
| uiseong_andong_2025 | 0.060 | 0.113 | 0.194 | 0.268 |
| yeongdeok_2025 | 0.042 | 0.080 | 0.178 | 0.284 |
| hongseong_2023 | 0.062 | 0.117 | 0.182 | 0.234 |
| uljin_samcheok_2022 | 0.020 | 0.040 | 0.128 | 0.235 |
| gangneung_donghae_2022 | 0.019 | 0.036 | 0.066 | 0.102 |
| miryang_2022 | 0.016 | 0.032 | 0.032 | 0.194 |

**Honest reading.** Exact-cell IoU is low (0.02–0.06): pinpointing *which* of many
similar near-fire cells ignites next is the chaotic part, and a high AUC does not make
it easy. Relaxing the budget to 3× (`recall@3K`) captures ~10–28 % of new-ignition
cells. A **direct comparison to the mechanistic ~9 % is apples-to-oranges**: that
number came from a *free-running* simulation from ignition, whereas this is a
*next-overpass* per-cell classifier scored teacher-forced (given the observed front).
The defensible claim is not "we beat 9 % footprint capture" but "we have a *validated
per-cell ranking skill* (AUC ≈ 0.75, far-band ≈ 0.74) that the mechanistic model never
demonstrated."

---

## Deliverable 4 — Baseline comparison

Same leave-one-fire-out protocol for: (a) a parameter-free **distance-only** ranking
(closer = more likely), and (b) a **logistic regression on distance + slope** terms.

Mean ROC-AUC (headline fires):

| model | mean ROC-AUC |
|---|---:|
| distance-only | 0.701 |
| logistic (distance + slope + slope-alignment + elevation) | 0.739 |
| **full XGBoost (15 features)** | **0.748** |

**Plainly stated:** the full model **beats distance-alone clearly** (+0.047 mean, and
far more inside distance bands — see above), but only **marginally beats the simple
distance+slope logistic baseline on the headline mean** (0.748 vs 0.739). That margin
is misleading because it is dragged down by the two tiny fires:

- On the **data-rich** fires the full model wins decisively: uljin 0.660→0.774
  (distance) / 0.698→0.774 (logistic); uiseong 0.705→0.787 / 0.727→0.787.
- On the **smallest** fire, **miryang** (31 positives), the simple logistic baseline
  (0.833) actually **beats** the full model (0.718): with that little data the richer
  feature set overfits relative to a 4-parameter model, and miryang's late-spring
  southern regime differs from the spring east-coast training fires. We report this
  rather than hide it.

So: proximity matters, but it is not the whole story — the extra features add real,
distance-independent skill on every fire with enough data to learn from.

---

## Deliverable 5 — Feature importance as a finding

Gain-based importance (full pooled fit); SHAP mean-|value| agrees on the top group.

| rank | feature | gain | mechanism |
|---:|---|---:|---|
| 1 | **frp_sum_1000m** | 0.203 | local **observed fire intensity** |
| 2 | dist_to_nearest_burning_m | 0.099 | proximity |
| 3 | **directional_alignment** | 0.091 | data-derived spread direction (wind proxy) |
| 4 | n_burning_within_1000m | 0.089 | local fire density |
| 5 | burnable_frac_nbhd_1000m | 0.070 | fuel continuity |
| 6 | nearest_burning_frp | 0.066 | intensity of the nearest front |
| 7 | fuel_grass | 0.062 | cured-grass flashiness |
| 8 | frp_max_1000m | 0.061 | peak local intensity |
| 9 | fuel_tree | 0.058 | timber/crown fuel |
| 10 | n_burning_within_500m | 0.052 | immediate fire density |
| 11–12 | fuel_shrub, fuel_crop | 0.037, 0.035 | fuel type |
| 13 | slope_deg | 0.030 | slope steepness |
| 14 | elevation_rel_m | 0.024 | relative elevation |
| 15 | slope_alignment | 0.023 | upslope spread |

(SHAP top-5: frp_sum_1000m, dist_to_nearest_burning_m, nearest_burning_frp,
n_burning_within_1000m, directional_alignment.)

**Physical interpretation.**

1. **FRP (observed intensity) dominates — above distance.** This is the headline
   scientific finding. The three FRP features together (≈ 0.33 of total gain) outweigh
   all proximity features. Physically: a hot, high-FRP front is actively crowning /
   spotting and ignites neighbours fast. **FRP directly observes the crown/spotting
   intensity that the mechanistic surface model could not represent** — which is
   precisely why the data-driven approach works where Rothermel failed.
2. **The data-derived spread direction is #3** — with no weather inputs, the fire's
   own recent growth vector is a strong directionality signal, validating the
   wind-proxy idea. It is *not* a weather feature, and replacing it with real wind is
   the obvious next step.
3. **Terrain ranks low** (slope, elevation, slope-alignment together ≈ 0.077). This is
   **lower than classical fire science would predict** — upslope preference is a
   textbook driver. In these **wind- and crown-driven Korean spring fires**, fire
   intensity and the already-established spread direction dominate over local slope;
   strong synoptic winds (the Yeongdong foehn, etc.) overwhelm terrain steering at the
   375 m / multi-hour scale we observe. A genuine discussion point, and a caution
   against over-weighting slope in Korean operational models.

---

## Deliverable 6 — Figures

- `conditional_auc.png` — AUC within each distance band, per fire (the honesty metric).
- `roc_curves.png` — overlaid leave-one-fire-out ROC curves.
- `feature_importance.png` — gain bar chart.
- `prediction_map_<fire>.png` — predicted ignition probability vs actual new ignitions
  for each held-out fire's most-active transition (Korean + English labels).

---

## Honest limitations

- **Temporal sparsity.** 4–29 usable transitions per fire; the small fires (hongseong
  6, miryang 4) give noisy AUC estimates, and miryang's far-band AUC rests on 2
  positives. goseong (1.7 h) yields nothing.
- **375 m resolution** is the floor; sub-pixel ignition and exact perimeters are
  unresolvable, which is why footprint IoU is low even at AUC ≈ 0.75.
- **No weather/wind yet.** Directionality is inferred from the fire's own growth, not
  measured. This is the biggest scientific gap.
- **Only 6 fires** contribute to cross-validation. Generalisation is encouraging
  (hongseong) but the sample of *fires* is small; confidence intervals on the mean AUC
  are wide.
- **Two fuel-blind fires** (yeongdeok, gangneung_donghae) due to the WorldCover 129°E
  tile clip; their fuel mechanism is unobserved.
- **yeongdeok area provenance** (5.14× reported) suggests its detections include the
  broader outbreak — its labels are still valid ignitions, but it is not a clean
  3 800 ha "Yeongdeok-only" fire.
- **Exact-footprint prediction is not solved** and is not claimed to be; the model is a
  risk-ranking tool, not a deterministic perimeter forecast.

## What the next iteration (ERA5) would likely improve

Adding **ERA5 hourly wind (speed + direction), relative humidity, temperature and a
dryness/VPD index** should help most where this version is weakest:

- Replace the *data-derived* `directional_alignment` (currently feature #3) with
  **measured wind direction**, which should sharpen far-band and cross-fire skill and
  remove a circular dependence on the fire's own past.
- **Humidity / dryness** would give the model the fuel-moisture axis it currently
  lacks entirely, and is the most plausible route to fixing the **miryang** failure
  (a late-spring fire in a different moisture regime than the spring training fires).
- Wind speed would let the model distinguish slow-creeping from wind-blasted fronts,
  likely lifting recall at a fixed false-positive budget (the footprint metric).

A second high-value, weather-free improvement: **back-fill the WorldCover 129°E tile**
to de-blind yeongdeok and gangneung_donghae, and gather more fires (especially
non-spring and non-east-coast) to tighten the cross-fire confidence interval.
