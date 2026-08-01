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

8 Korean fires ship in the bundle; 6 have usable ERA5 and ≥2 overpasses and
are used (gangneung_donghae_2022 has an empty ERA5 file; goseong_2019 has a
single overpass).

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
- **`days_since_rain` (dryness) is the #1 predictor; summed fire-weather
  severity importance is ~40× `wind_alignment`** — far-field skill comes from
  *severity*, not wind *direction*. (Severity is spatially uniform at ERA5's
  0.25° resolution, so it sets the reach *magnitude* across days/fires while
  geometry/terrain place it spatially.)
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
