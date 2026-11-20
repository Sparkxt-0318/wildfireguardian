# Data index (public copy)

Short copy of the private index kept with the data. No file paths to keys; no key values. Written 19 Nov 2026 from the file listing of the data archive "wildfire 3 (1)" (11.4 GB zip, 16.0 GB unpacked, entries dated 9 to 13 Oct 2026). Nothing was unpacked except catalogs and source sidecars.

## What the archive holds

| Dataset | What | Source | Dates | Area | Format | Size |
|---|---|---|---|---|---|---|
| Arrival-time rasters | Reconstructed hourly arrival time per 375 m cell and kriging SD. **Retrospective, not observed** | Zenodo 10.5281/zenodo.21788344 | fires 2020 to 2025 | 44 fires: 15 Korea, 29 US | GeoTIFF | 3.1 GB (`regions/`) |
| Hourly burned-area bitmaps | One bitmap per hour per region (289 to 361 snapshots) | Derived from the above | 2022-03 to 2025-04 | 5 Korean regions | BMP + world file | 48 MB |
| Fire perimeters | Independently mapped NIROPS perimeters | Mendeley Data 10.17632/95rj5d379g.1 (CC BY 4.0) | 2020 to 2024 | US regions R1 to R6 | zip, GeoJSON | 2.0 GB |
| Fuel loading and canopy structure | LANDFIRE-based loadings, canopy cover, base height | LANDFIRE 2016 | | 29 US events only | GeoTIFF | in `regions/` |
| Land cover, forest type | 13 cover layers and a forest-type class | Copernicus Global Land Service 100 m, 2019 | | 44 events | GeoTIFF | in `regions/` |
| Biome | Biome class | RESOLVE Ecoregions 2017 | | 44 events | GeoTIFF | in `regions/` |
| Canopy height | Forest height 2019, subset per event | GLAD / University of Maryland | 2019 | 44 events | GeoTIFF | in `raw/` (1.0 GB) |
| Terrain | 30 m DEM, slope, aspect, elevation, TPI at 375 m | Copernicus DEM GLO-30 | | 44 events | GeoTIFF | in `regions/` |
| Weather | Hourly series and 375 m gridded layers (wind, gust, RH, rain, soil moisture, boundary layer) | ECMWF IFS, ERA5 | per event window | 44 events | JSON, GeoTIFF | in `raw/`, `regions/` |
| Run outputs | Probability-model training runs, FARSITE comparison runs, reports | Built here | Oct 2026 | | mixed | about 4.5 GB |

## Not in the archive
Road networks, population or household data, raw satellite detections (FIRMS VIIRS/MODIS, AHI), a Korean fuel-model map, and API keys. No key file was found and no key value was found by a content search of 5,869 text files. Key names the repository expects: `DATA_GO_KR_KEY`, `KMA_API_KEY`, and a FIRMS map key.

## What the repository lacks
The raster data above are not in the repository: `forecast/data` holds only catalogs (164 KB). Road graphs are in `data/routing` and population in `research/kcf-defend`.

## Limits
Sizes come from the zip listing. Use by repo folder is inferred from file names and RESULTS text. The Google Drive copy was not compared with the zip.
