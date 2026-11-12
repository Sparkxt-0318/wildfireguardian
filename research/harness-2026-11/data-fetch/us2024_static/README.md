# US2024 held-out fires: rebuilt static layers on the forecast-v2 rectangles

There is one `<event>_static.npz` per fire (Wapiti, Goat, Lava, RedRock, Pioneer, FishCreek). They were packed by `../pack_static_layers.py` from a
`rebuild_env.sh --project` run on 2026-11-12, using the repo's own `forecast/wildfire/environment.py`.

Arrays are `[height, width]` on the Choi/forecast-v2 grid (EPSG:5070, 375 m), the same grid the stored heldout cases index with `row`/`col`.
Checked: all 273 committed heldout cases (`forecast/runs/20261030_perimeter_trained/execution_v3/heldout/cases`) have the same
`rectangle` and in-range indices.

| key | meaning |
|---|---|
| `fbfm40` | LANDFIRE 2016 Remap FBFM40 code (mode-resampled from 30 m). 91–99 are non-burnable classes. This is the code `FlameResidenceTime.from_fbfm40` reads. |
| `biome` | RESOLVE 2017 BIOME_NUM (the `biome.biome_class` channel). |
| `slope_degrees`, `tree_cover_percent` | Model source channels (Copernicus DEM GLO-30; Copernicus Global Land Cover 2019). |
| `elevation_m` | Copernicus DEM GLO-30 (a DSM). |
| `*_valid`, `all_static_valid` | Not nodata and finite, the same rule as `forecast/wildfire/data.py`. All six fires are 100 % valid on every layer. |

**Archive equivalence (A1 item 14):** biome is byte-identical to the archive wherever an archive hash exists. Slope and tree cover are UNAVAILABLE
(bytes differ, values not recoverable). FBFM40 has no direct check: the raw `landfire_2016_fbfm40` file differs in bytes on the 3 rebuilt fit fires,
while the derived canopy layers built from the sibling LANDFIRE rasters match exactly.
**Not included:** temperature and wind (Open-Meteo quota). They will be added after the 00:00 UTC reset using
`research/forecast-v2/scripts/rebuild_environment.py` (slim weather).
