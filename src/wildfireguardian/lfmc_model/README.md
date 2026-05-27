# `lfmc_model` — Live Fuel Moisture Content retrieval

**Status**: scaffold only.

**Purpose**: estimate per-pixel live fuel moisture content (LFMC, % of dry
mass) from Sentinel-2 surface reflectance, for use as the fuel-moisture
input to the Rothermel spread model.

**Inputs**: Sentinel-2 L2A bands (B04, B08, B8A, B11, B12) plus topographic
predictors (slope, aspect, elevation) on a 20-m grid.

**Outputs**: an LFMC raster (% dry mass) at Sentinel-2 native resolution,
gap-filled to a daily grid by exponentially weighted moving average.

**Algorithmic basis**: gradient-boosted regression (XGBoost) trained on the
Globe-LFMC 2.0 in-situ database (Yebra et al. 2024), restricted to Korean
biome analogues. NDWI = (B8A − B11) / (B8A + B11) is the strongest single
predictor; NBR, NDVI, and topographic covariates add information.
