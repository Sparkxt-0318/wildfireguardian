# spread_v2 — data-driven per-cell ignition model

`spread_v2` predicts, for each ~0.5 km cell, **P(detected as burning by the
next satellite overpass)** from real data. It is the probabilistic hazard the
evacuation router consumes. It is **not** the mechanistic Rothermel model in
`spread_model/` — that one is a physics simulation; this one is learned from
observed fire behaviour.

## Why this exists

The routing brief assumes a `spread_v2` model already in the repo. It did not:
prior sessions deferred it as "Round-2 work pending real Korean fire data."
That data (`firms_data.zip`) is now available, so this package builds it.

## Data provenance (all REAL observational data)

| Layer | Source | Notes |
|---|---|---|
| Active-fire detections | NASA FIRMS (MODIS + VIIRS) | a *detection* product — an observed lower bound on burned area, not a burn-scar map; first detection can lag true ignition by days |
| Elevation | SRTM-class DEM, EPSG:4326 ~30 m | reprojected to the coarse grid |
| Land cover / fuel | ESA WorldCover, ~10 m | burnability via `data_layers_manifest.json`; class 80 = sea |
| Weather | ERA5 reanalysis, 0.25°, 3-hourly | `u10,v10,t2m,d2m,tp` → wind, RH, VPD, dryness |

8 Korean fires ship in the bundle; 6 have usable ERA5 and ≥2 overpass
CLUSTERS and are used (gangneung_donghae_2022 has an empty ERA5 file;
goseong_2019 yields one cluster).

⚠ **CORRECTED 2026-08-03 (PHASE 13 STEP 2). `goseong_2019` does not have "a
single overpass" — it has four acquisitions, and the 90-minute clustering rule
merges them.** The earlier wording attributed the exclusion to the data. It is a
property of the threshold.

Its acquisitions are 16:48 (NOAA-20), 17:34 (Aqua), 17:38 (S-NPP), 18:28
(NOAA-20) — gaps of 46, 4 and 50 minutes. `cluster_overpasses` in `grid.py` is
single-linkage (`np.cumsum(gaps > gap_minutes)`), so a chain of sub-threshold
gaps collapses however far it spans. All three gaps are under 90 minutes, so the
chain becomes ONE cluster, there is no (t → t+1) transition pair, and the fire
contributes zero training rows.

**The 16:48 and 18:28 NOAA-20 acquisitions are exactly 100 minutes apart — one
full orbital period.** They are genuinely consecutive orbits, which is the
double coverage expected at goseong's 38.35 °N, and the intervening Aqua and
S-NPP passes are what bridge them under the threshold. At 30 minutes the fire
splits into three clusters.

This is not confined to goseong. Across the shipped bundle the 90-minute rule
merges distinct passes everywhere — `uljin_samcheok_2022` has 75 distinct
acquisition times collapsing to 27 clusters, and cluster time spans reach 201
minutes (`hongseong_2023`), i.e. a "near-instantaneous overpass" that is three
hours wide. Cluster counts at 90 / 60 / 30 minutes: uljin 27/29/53, uiseong
19/26/29, gangneung_donghae 15/16/31, yeongdeok 6/9/9, hongseong 5/7/12,
miryang 5/5/10, gangneung_2023 2/2/2, goseong 1/1/3.

The 90-minute value is a hardcoded default in `grid.py` with no config key, and
the superseded `spread_v2_xgb` track uses 60 minutes instead. Nothing here has
been changed — the committed model, its training set and its reported AUC are
all conditioned on 90 minutes, and moving it would move them. This note exists
so the exclusion is not read as a fact about goseong.

## Pipeline

```
data.py        load detections / DEM / fuel / ERA5 per fire
grid.py        coarse EPSG:5179 grid; reproject layers; cluster overpasses
weather.py     ERA5 → severity features (days_since_rain, RH, VPD, wind speed)
features.py    per-cell next-overpass rows for each overpass transition
model.py       gradient-boosted classifier + leave-one-fire-out (LOFO)
forward_sim.py iterate the model into a time-sequenced hazard surface
```

## Headline results (leave-one-fire-out, fully out-of-sample)

- **Mean-of-folds ROC-AUC ≈ 0.89** (range 0.68–0.97 across 6 fires; the 0.68 fold,
  `gangneung_2023`, has ~17 detections) — the generalization figure. The pooled
  out-of-fold AUC ≈ **0.91** and far-band (>3 km) AUC ≈ **0.88** are *pooled*
  (concatenated held-out predictions), not the mean-of-folds. Canonical numbers:
  `docs/MODEL_CARD.md`.

  ⚠ **`leave_one_fire_out` produces `per_fire_auc` over folds of highly unequal
  size, and the mean over them gives each fold an equal vote.** The largest fold
  holds 208.9× the rows of the smallest (`uiseong_andong_2025` 54.47 % of all
  rows; `gangneung_2023` 0.26 %, with 8 positive cells). **Pooled AUC is the
  primary metric** — it weights each row once. Anything quoting the
  mean-of-folds must carry `docs/fold_sizes.md` with it. Note that
  `permutation_importance` in the same artifact is NOT affected: it is
  aggregated as a ROW-weighted average across folds, deliberately.

  ⚠ **Read pooled AUC to three significant figures.** The fourth digit is not
  stable across platforms (measured drift 0.0064 pooled, 0.0307 far-band —
  `docs/platform_drift.json`, `docs/MODEL_CARD.md`).
- **`days_since_rain` (dryness) ranks #1 in permutation importance; summed
  fire-weather severity importance is ~44× `wind_alignment`** — a measured
  ratio whose original reading, *"far-field skill comes from severity, not
  wind direction"*, is **WITHDRAWN as not established**
  (`docs/MODEL_CARD.md`, permutation-importance section): the comparison sets
  a six-feature sum against one variable, ERA5's 0.25° grid cannot resolve
  the wind it is about, and the ratio is a single point estimate. PHASE 14
  further measured that *dropping* the #1 feature RAISES out-of-fold AUC
  (`docs/weather_dependency.md` §②). What remains true: severity is spatially
  near-uniform at 0.25°, so it can only set reach *magnitude* across
  days/fires while geometry/terrain place it spatially.
- Forward simulation produces a **broad** (~60°) reach envelope that **drifts**
  from observed as compounding error accumulates; the forward-sim envelope IoU
  settles at **~0.40** over 3–12 h (the honest footprint figure — *not* the 0.874  <!-- forbidden-ok: 0.874 -->
  single-step IoU, which measures "next overpass given the current burn").

Regenerate: `python scripts/run_routing_integration.py`.

## Honesty / limitations

Proof-of-concept of the prediction→routing method on one anchor fire, **not**
an operational system. FIRMS labels under-count and the 0.5 km cell over-counts
area; forward-sim error compounds; overpass-scale time resolution is hours, not
minutes. See `docs/ROUTING_INTEGRATION_REPORT.md`.
