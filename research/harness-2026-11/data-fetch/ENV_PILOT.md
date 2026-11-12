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

## Follow-ups (2026-11-12, later)

**Encoding hypothesis: tested, not confirmed.** The raw `landfire_2016_*` rasters and the derived canopy layers are written by the same
`write_tif` (deflate, predictor 3, 128 px tiles), and the vendored 8 October acquirer is identical apart from variable names.
`canopy_cover_percent = landfire_2016_cc × 1.0` matches the committed hash and holds real data (3,796 cells, 2,190 distinct values). The rebuilt raw CC
pixel values are therefore identical to the owner's, yet the raw file's hash differs. Re-encoding the rebuilt CC, slope and tree-cover arrays did
**not** reproduce any committed hash with:
- 792 GDAL 3.9.3 creation-option and tag variants (deflate, lzw, zstd, none; predictor 1, 2, 3; tiled or not; 128/256/512 blocks; z-levels; three tag sets);
- 5 dtypes (float32, float64, int16, int32, uint8);
- rasterio 1.3.9 to 1.4.4 Linux wheels, covering GDAL 3.6.4, 3.8.4, 3.9.2, 3.9.3 and 3.10.3.

The difference is outside the pixel values for CC and is not reproducible on Linux. The remaining candidate is the owner's macOS build at the
time the raw layers were first written, which I can't test here. For slope and tree cover there is no derived layer to prove value equality.

**Open-Meteo load per fire.** This follows the published rule (open-meteo.com pricing FAQ): a request is counted fractionally above 10 variables or above 2
weeks per location. I computed the locations with the repo's own `o1280_locations`/`era5_locations` and summed per location. The model is ECMWF IFS
(10 variables, start −30 d to end) plus ERA5 boundary layer (1 variable).

| Fire | IFS locations / days / HTTP requests / weighted calls | ERA5 locations / days / weighted calls |
|---|---|---|
| Blue2 | 5 / 60 / 1 / 21 | 1 / 30 / 2 |
| MossMountain_Chalk | 6 / 115 / 1 / 49 | 4 / 85 / 24 |
| Homestead_Salmon33 | 2 / 121 / 1 / 17 | 1 / 91 / 7 |
| AlderCreek | 11 / 120 / 1 / 94 | 4 / 90 / 26 |
| Wapiti | 30 / 117 / 3 / 251 | 9 / 87 / 56 |
| Dixie (largest) | 192 / 123 / 16 / 1,687 | 36 / 93 / 239 |
| KFS_01 | 48 / 35 / 4 / 120 | 10 / 5 / 10 |

All 44 project events together come to about 10,700 weighted calls, which exceeds the free 10,000/day. Small part-a fires cost about 20–75 each, so a few dozen fit in one
day's quota. **The quota is per IP, and this egress IP was already exhausted at my first request (by whom is unknown)**, so feasibility depends on the reset and on
shared use. The same FAQ also states that "historical … APIs require the Professional API Plan or higher", which conflicts with the free-tier
terms; the user should check this before relying on the free archive. A retry once after 00:00 UTC is scheduled.

**GLAD canopy height (Potapov et al. 2021).** No mirror was found. Zenodo 4008406 holds only the preprint PDF. glad.umd.edu and glad.geog.umd.edu both
fail TLS (the emSign root is untrusted here), and there is no plain-HTTP route (DNS fails on port 80 through the proxy). The other route is the Earth Engine
community catalog, which needs an account. Product substitutes such as ETH Global Canopy Height 2020 (Zenodo 17456991) would be a scientific change, not a mirror.
This layer is not among the S-D9 six channels and not in AlderCreek's FIT_COVERAGE list, so it waits for the user's trust decision.
**Checksum plan if a mirror appears:** compare the full-tile sha256 against glad.umd.edu once trusted. Failing that, compare windowed pixel
statistics on 3 fit-fire grids against a GLAD-host read made after the trust decision.
