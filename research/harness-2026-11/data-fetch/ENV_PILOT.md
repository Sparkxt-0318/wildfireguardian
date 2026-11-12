# Environment-covariate rebuild pilot (2026-11-12)

**Fire:** MT-BDF-006269_AlderCreek. It is a forecast-v2 fit fire that is already exposed, chosen because it is small (150 km², a 73×52 grid).

**Method:** I ran the repo's own acquirer (`forecast/wildfire/environment.py`) unmodified, in an isolated copy outside git, with Python 3.12 and the pinned
dependencies (numpy 1.26.4, rasterio 1.4.3 with GDAL 3.9.3, pyproj 3.7.0). The Choi archive came from `fetch.py get toa_kriging_choi2026`.
Every file was compared by sha256 against `research/next-combined/canonical-coverage-owner-ab7fda8d/FIT_COVERAGE.json`.

| Stage (`python -m wildfire …`) | Host | Result | Time |
|---|---|---|---|
| `environment inventory` | — (local Choi archive) | OK. `arrival_time_hours.tif` and `kriging_std_hours.tif` **match**. `events.json` differs only in the last float digit of 33 WGS84 bounds. | 1 s |
| `environment weather` (ECMWF IFS) | archive-api.open-meteo.com | **FAILED.** HTTP 429 "Daily API request limit" on the first request. The shared egress IP is already over the free quota. The code stops by design ("Do not bypass the service limit"). | — |
| `environment boundary_layer` (ERA5) | archive-api.open-meteo.com | **FAILED** (same 429). | — |
| `environment terrain` | copernicus-dem-30m S3 | OK. `complete.json` matches; `slope_degrees_375m.tif` differs. | 4 s |
| `environment canopy` | glad.geog.umd.edu | **FAILED.** TLS verify error: the server chain ends at "emSign Root CA - G1", which is not in this container's trust bundle. Not bypassed. | — |
| `environment gridmet` | tds-proxy.nkn.uidaho.edu | OK. fm100 and fm1000 band CSVs **match**. | 2 s |
| `environment landfire` | lfps.usgs.gov | OK. The 7 raw `landfire_2016_*` rasters differ. | 24 s |
| `environment landcover` | zenodo.org (PROBA-V LC100) | OK. `tree_cover_percent_375m.tif` differs. | 28 s |
| `biome` (all 44 fires) | storage.googleapis.com (376 MB, cached once) | OK. Both biome files **match**. | 9 s |
| `enrich-data` | www.landfire.gov | OK after manually placing `sources/LF_ConsumeLoadings.csv` (sha256 `1621b8e3…`), which the code reads but does not download. 7 fuel files **match**; ladder, overstory and total loading differ. | 1 s |

**Tally against the committed hashes (35 files):** 16 match, 12 differ, and 7 are missing (all weather). The 12 that differ are slope, tree cover, the 7 raw LANDFIRE
products, 3 fuel loadings and grid.json. There are no tags with timestamps. The derived canopy products match while their raw LANDFIRE inputs
differ, which points to a GDAL encoding or version difference (the owner's macOS run used unknown GDAL builds) rather than different values. This is unverified, because
the repo keeps only hashes, not the reference rasters.

**Cost per fire:** about 70 s of acquisition (excluding weather) and under 1 MB of outputs. The one-time sources are 376 MB of ecoregions plus 3.4 MB of the LANDFIRE CSV.

**What blocks a full rebuild:**
1. Open-Meteo weather (the hourly drivers). The options are to retry after the daily reset (the quota is shared with whoever else uses this egress IP) or a paid Open-Meteo API key, which is the user's decision.
2. GLAD canopy height. This needs a trust decision on the emSign root, which is the user's or admin's call, or an alternative mirror.
3. Byte-identity with the owner archive is not reachable. A rebuild yields a new, self-consistent input set, not the hashes in `FIT_COVERAGE.json`.
