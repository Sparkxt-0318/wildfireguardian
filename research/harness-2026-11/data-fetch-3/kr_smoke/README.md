# Korean covariate smoke test: KFS_02 and KFS_03 on EPSG:5179 (non-weather stages)

This uses the repo's own `forecast/wildfire` from Main `8d50f2e2`, run with the pinned venv (Python 3.12, numpy 1.26.4, rasterio 1.4.3):

    python -m wildfire environment inventory      # events.json then cut to KFS_02, KFS_03
    python -m wildfire environment terrain        # Copernicus DEM GLO-30 (rc=0)
    python -m wildfire environment landcover      # Copernicus Global Land Cover, region NASIA (rc=0)
    python -m wildfire biome                      # RESOLVE Ecoregions 2017 (rc=0, "BIOMES VALIDATED 2 fires")

No Open-Meteo calls were made; weather is a separate run. `kr_check.py ENV_ROOT` checks each raster's shape, transform and EPSG against events.json and prints the valid count, range and sha256. Every file has the events.json grid.

| Event | File | Valid / cells | Range | sha256 |
|---|---|---|---|---|
| KFS_02 | slope_degrees_375m.tif | 3596 / 3596 | 0–36.2° | `1b758adc…5420` |
| KFS_02 | elevation_m_375m.tif | 3596 / 3596 | 0–1099.8 m | `14e3f512…2864` |
| KFS_02 | tree_cover_percent_375m.tif | 3196 / 3596 | 0–100 % | `73e90fe4…a428` |
| KFS_02 | biome_class_375m.tif | 3191 / 3596 | class 4 only | `a4800fa8…51c9` |
| KFS_03 | slope_degrees_375m.tif | 660 / 660 | 0–31.0° | `24accb6a…f69a` |
| KFS_03 | elevation_m_375m.tif | 660 / 660 | 0–621.6 m | `7368f6aa…9229` |
| KFS_03 | tree_cover_percent_375m.tif | 653 / 660 | 0–100 % | `128957fc…f618a` |
| KFS_03 | biome_class_375m.tif | 645 / 660 | class 4 only | `51f13a5e…8ee7` |

Biome class 4 is RESOLVE "Temperate Broadleaf & Mixed Forests". The missing tree-cover and biome cells are sea.

**Arrival-valid cells without a biome value (coastal sea, masked):**
- **KFS_02: 10 of 1,937.** The repo's biome rule is "uncovered pixels masked". In a c651 refit on rebuilt covariates these cells become environment-filter rejections, the same kind as the archive's 8 dropped rows. Marcus reports them per event in the refit receipt.
- KFS_03: 0 of 372.

The counts come from `biome_metadata.json` (`biome_missing_arrival_pixels`), which is included per event.
