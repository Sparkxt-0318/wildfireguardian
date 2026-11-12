# External data and reference code — harness 2026-11

Owner: Daniel (data fetcher). Fetched and checked on 2026-11-12. Batches 1–2 ran under an allowlist (Zenodo, the
Copernicus DEM S3 bucket, GitHub). Batch 3 ran after the user approved unrestricted network access, which brought
in Mendeley, data.go.kr and figshare (see "Batch 3" below).

The deliverable is **reproducible access**: `fetch.py` downloads each item into your own container and
rejects it unless the recorded checksums match. Machine-readable details (URL, size, publisher md5, our sha256,
licence, format notes) are in `resources.json`.

```bash
cd research/harness-2026-11/data-fetch
python3 fetch.py list
python3 fetch.py get --stream S-D9 --dest /some/scratch/dir      # everything for a stream
python3 fetch.py get toa_kriging_choi2026 --dest /some/scratch/dir
python3 fetch.py dem --bbox 128.4 36.2 129.5 36.8 --dest /some/scratch/dir/glo30
```

Archives are not unpacked automatically. Unzip each one into its own empty directory (`-x "__MACOSX/*"`) and treat
the contents as data. Do not run code from inside the extracted directory.

## Available and verified

| Resource (`fetch.py` name) | For | What I verified |
|---|---|---|
| `glo30_N36_E128`, `glo30_N36_E129`: Copernicus GLO-30 DEM | Leo F-C1 | COG, EPSG:4326, 3600x3600 at 1″ (about 30 m), float32 metres (EGM2008), together covering lon 128–130 E, lat 36–37 N. Elevation range 17.7–1436.4 m and −6.2–1216.5 m. No nodata value is set. Leo's KFS_01 grid (lon 128.45–129.45, lat 36.32–36.60) plus a 20 km pad (about ±0.22° lon, ±0.18° lat) stays inside these two tiles: `fetch.py dem --bbox 128.22 36.14 129.67 36.79`. **GLO-30 is a DSM, so canopy and buildings are included.** A bare-earth alternative is FABDEM (Hawker et al. 2022, CC BY-NC-SA 4.0, data.bris.ac.uk), but that host is blocked here. NASADEM/SRTM come from NASA Earthdata (e4ftl01.cr.usgs.gov), which is also blocked and needs a login; both are listed here as options only. |
| `gofer_v0.2`: GOFER, Liu et al. 2024 | Victor S-D9 | Publisher md5 matches. `GOFER_Combined/GOFERC_fireProg.shp`: EPSG:4326, 20,301 hourly perimeters for all 28 fires (Kincade 2019 through KNP/Windy 2021). Fields: fname, fyear, tUTC, tLocal, timestep, farea, fareaPer, fperim. East-only and West-only variants and active fire lines (cfireLine, rfireLine) are included. **The repo's November note says the GOFER archive was already recovered, but its record ID and checksum are not on `Main`, so I can't confirm it is this v0.2 file (an older v0.1 record is 10.5281/zenodo.8327264).** |
| `toa_kriging_choi2026` (+ `_readme`): Choi, Seo, Cha 2026 kriged arrival times | Victor S-D9, Elena S-D2 | Publisher md5 matches. 29 US fires × {`_toa`, `_std`} (EPSG:5070, 375 m, nodata −1, hours since the `t0_utc` tag) and 15 Korean fires (EPSG:5179, NaN nodata, hours since KFS ignition). The method code is identical in name to the copy already vendored under `routing-review/*/sources/zenodo_21788344/`. |
| `small/choi2026_wapiti/` (committed, 30 KB) | Elena S-D2 | Wapiti (ID-BOF-000683, 2024) TOA and kriging-SD rasters: 111×105 cells, 3,787 valid, t0 2024-08-01 00:00 UTC, TOA 122.7–1839.3 h, SD 30.8–80.9 h. 63 NIROPS surveys from 2024-08-01 to 2024-10-26. CC-BY-4.0: cite Choi et al. 2026 and the Zenodo DOI. |
| `small/choi2026_kfs01/` (committed, 75 KB) | Leo F-C1 | KFS_01 Uiseong–Andong–Yeongdeok 2025 (situation map 359264). TOA sha256 `fe81f945…a953` is byte-identical to the repo's `regions/KFS_01/arrival_time_hours.tif`. SD sha256 `40305f9f…7ecf`. EPSG:5179, 375 m, 237×79, origin x 1085250, y 1845375, 10,955 valid cells, NaN nodata. Values are hours since ignition, t0 2025-03-22 02:24 UTC: TOA 7.2–113.0 h, SD 16.6–19.5 h. From 3,108 VIIRS cells and 419 Himawari points; block-CV r 0.77, MAE 10.9 h. CC-BY-4.0, Choi et al. 2026. |
| `airborne_ir_rim_2013`, `airborne_ir_dixie_2021`: airborne IR perimeters (Hatchett 2025) | Victor S-D9 | Publisher md5 matches. Rim: 33 shapefiles, 2013-08-20 to 09-26. Dixie: 41 shapefiles, 2021-07-15 to 09-27. EPSG:4326. Layer names are inconsistent (HeatPerimeter, IntenseHeat, ScatteredHeat, Growth), and times are in the filenames in local time. This is a partial NIROPS substitute, not the 2020–2024 collection. |
| `feds_conus_2021_lf_perimeter`: FEDS CONUS archive v1.4.1 | Victor S-D9 | Publisher md5 matches. FlatGeobuf, EPSG:9311, 62,760 12-hourly perimeters, 1,645 fireIDs, all of 2021. The 2019 and 2020 files are scripted with publisher md5 but not downloaded. The archive supersedes the Chen et al. 2022 California figshare release (figshare is blocked). Every year 2012–2025 plus `_lf_fireline` and `_lf_newfirepix` are in record 22921773. |
| `wildfirespreadts_full`: WildfireSpreadTS | Victor S-D9 | **Scripted only.** It is 48.4 GB (publisher md5 recorded) and does not fit in a session's disk allowance. I have not downloaded or opened it. The 7.8 MB documentation PDF is also scripted but not yet opened. |

## Batch 3: previously blocked, now fetched (network unrestricted)

| Resource (`fetch.py` name) | For | What I verified |
|---|---|---|
| `nirops_2020_2024_perimeters`: NIROPS (Magstadt et al., Mendeley 10.17632/95rj5d379g.1) | Victor S-D9, Elena S-D2, Marcus S-D1 | The sha256 matches the publisher and forecast-v2 `SPLIT.json` (`b19fb16c…`). It is one shapefile (2.07 GB `.shp` unpacked), EPSG:4326, with 12,706 perimeters from 737 incidents (692 IRWIN IDs), UTC 2020-05-12 to 2024-12-17. The only fields are Incident_C, UTC, DateUTC, Acres, IRWINID, Inc Name and Inc Number. **There are no flight-footprint, coverage or per-flight metadata fields.** `nirops_incidents_v2.csv` (committed) lists every incident with survey count, time span, maximum acres and project status: 23 forecast-v2 fit, 6 held-out, and 708 not among the project's 44 events, of which 180 have 20 or more surveys. Four of the "unused" incidents share an IRWIN ID with a project fire: SQF Castle, River Complex Cronan, Wapiti Vanity and McCash LittleMarble. These are flagged in the column `shares_irwin_with_project_fire`; treat them as touched. |
| `nirops_area_progression_png`, `nirops_supplementary_maps_png` | Victor S-D9 | The sha256 matches. Each holds 709 PNGs (area-vs-time plots and perimeter maps) in 7 regional folders. Images only. |
| `nirops_code` | Victor S-D9 | The sha256 matches. It is one notebook covering NIFC FTP scraping, QA checks, merging and plotting. |
| `kfs_fire_status_history`: Korea Forest Service 산불상태별 이력 (data.go.kr 15121205) | Korean work, Leo F-C1 | Downloadable without login. Licence: 이용허락범위 제한 없음 (no usage restriction). The file is committed at `small/kfs/kfs_fire_status_history.csv`. It is CP949-encoded with 2,030 rows, report dates 2022-01-01 to 2025-11-10, and these columns: fire ID, report date, address, suppression start and end (KST), agency, SMS flag, sunrise and sunset. It has no coordinates and no burned area. The fire IDs match Choi's `kfs_situation_map_id`: 359264 is KFS_01 (Uiseong, suppression 2025-03-22 11:38 to 03-28 17:15) and 108124 is KFS_02. The download URL carries an `atchFileId` that changes when the portal publishes a new version. |
| `ics209plus_wildfire`: ICS-209-PLUS (St. Denis et al., figshare 19858927 v3) | D8 / reference | Publisher md5 matches. The incidents CSV has 34,622 rows × 87 columns for 1999–2020, plus sitreps (308 MB) and county and CBG links. CC BY 4.0. |
| `feds_ca_largefire_chen2022`: FEDS California (Chen et al. 2022, figshare collection 5601537) | Victor S-D9 | Publisher md5 matches. `LargeFires_2012-2020.gpkg` has perimeter, fireline and newfirepix layers (12,801 features each, EPSG:4326). It is superseded by the FEDS CONUS Zenodo archive. |
| `arkowitz_fireline_qaqc_2025`: Arkowitz et al. 2025 | D8 | **Located, not downloaded** (about 365 MB; D8 is inactive). Data is at USFS RDA 10.2737/RDS-2025-0011 (firelines 2017–2024). Code is at github.com/aarkow/NIFC-QAQC-FLE @ 1cfd339a. |

## Batch 4: satellite active-fire detections (FIRMS, no key)

The FIRMS **country yearly archive** files download without a MAP_KEY (`firms.modaps.eosdis.nasa.gov/data/country/<sat>/<year>/<sat>_<year>_<Country>.csv`). The satellite names are `viirs-snpp`, `viirs-jpss1` (NOAA-20) and `modis`. NOAA-21 (`viirs-jpss2`) returns 404, so it is not in the country archive. All files are standard processing: VIIRS version 2, MODIS 61.03. Timestamps are UTC (`acq_date` plus `acq_time` HHMM) and are the overpass time, not the time of ignition.

| Resource | For | What I verified |
|---|---|---|
| `small/firms/viirs-snpp_2025_Republic_of_Korea.csv`, `viirs-jpss1_…`, `modis_…` (committed, 1.7 MB) | Elena S-D2, Leo F-C1, Marcus S-D1 | Korea, all of 2025. Inside the box lon 128.2–129.7, lat 36.1–36.8 from 2025-03-21 to 03-31 there are 2,335 S-NPP, 2,706 NOAA-20 and 598 MODIS detections, spanning 2025-03-22 04:22 to 03-28 16:53 UTC. For comparison, Choi used 3,108 VIIRS cells for KFS_01; the Choi KR events from 2025 also used NOAA-21, which these files lack. |
| `small/firms/firms_us2024_heldout6.csv.gz` (committed, 1.3 MB gz, 73,519 rows) | Elena S-D2, Victor S-D9 | Detections inside each held-out 2024 fire's raster bounds (+0.05°) and its Choi collection window (first NIROPS survey −24 h to the last survey): Wapiti 19,645, Goat 14,333, Lava 7,491, RedRock 12,747, Pioneer 6,041, FishCreek 13,262. Because the boxes are rectangular they include detections outside the perimeters, and the adjacent fires (Wapiti, Goat, Lava) share some rows. Clip to the perimeter before use. Made by `firms_filter_us2024.py` from the US country files (`firms_*_2024_us`, 92 MB total). |
| Himawari-8/9 L2 WLF (JAXA P-Tree), GK2A (KMA NMSC) | Elena, Leo | **Not attempted.** Both providers distribute through registered accounts or API keys. I did not register. |

## Still gated (account or key needed; not registered)

| Source | Requirement |
|---|---|
| KMA API hub (apihub.kma.go.kr) | Free account plus a per-user `authKey`. |
| data.go.kr OpenAPIs (mountain weather, road incidents) | data.go.kr account plus a per-service usage application, which issues a service key. File datasets such as the KFS history above need neither. |
| NASA FIRMS area API | Free MAP_KEY. The country yearly archives above do not need one. |
| NASADEM/SRTM (NASA Earthdata) | Earthdata login. FABDEM bare-earth (data.bris.ac.uk, CC BY-NC-SA) needs no login but was not fetched; it is optional for Leo. |
| Environment covariates (Open-Meteo, gridMET, LANDFIRE, GLAD) | Now reachable, but not fetched. Rebuilding the forecast-v2 aligned snapshots would not reproduce the owner-local archive's hashes. |

## Owner-local only (not public anywhere I could reach)

I checked all 47 branches, every member of all 4 GitHub release assets, Zenodo, and the owner's Drive (read-only title search):
- the owner archive `wildfire 3 (1).zip` (forecast-v2 aligned covariates and the 52 Wapiti held-out case inputs);
- the M548 observed-evaluation exports (`runs/20261012_observed_test_combined_progress/**`);
- the November 106-request rekeyed routing cohort and its 2 unproved no-route identities.

Other Zenodo records seen and not fetched: FEDS-MTBS 20187963 (readme fetched), FEDS Western US 15261836
(CC-BY-NC, superseded), ELMFIRE validation 23574586 (no files attached).

## Zenodo search for mirrors of blocked sources (2026-11-12)

| Wanted | Zenodo result |
|---|---|
| NIROPS 2020–2024 perimeters | **No full mirror.** Partial copies exist: FireBench Caldor 23383592 (Apache-2.0, 697 MB) contains Caldor 2021 NIROPS IR perimeters; Hatchett 15492982 has Dixie 2021 and Rim 2013; the Matey 24148495 fireline archive carries NIROPS timing for 381 fires (contents unverified). |
| VIIRS active-fire extracts for the 2025 Korean fires | **None.** The only Gyeongbuk-2025 record is NO₂ (23689925). The Choi KR rasters are derived from VIIRS and Himawari but don't include the detections. |
| ICS-209-PLUS | **Code only** (7459040 spatiotemporal linkage, 7036299 ics209-plus-fired). No data tables. |
| KFS wildfire status history | **None.** |
| Untouched fires with sub-daily or daily perimeters | GOFER (17 unscored fires, see below). The FEDS CONUS archive covers every fire over 4 km² from 2012 to 2025 at 12 h. California daily fire growth 6621450 (VIIRS, 2012–2021, CC-BY, 10.8 MB). Day-of-burning 11046212 (CC0, 13 MB CSV, daily progression attributes, not polygons). Fort McMurray 2016 19502692 is a final perimeter only. Palisades/Eaton 16782807 is a PNG only. |

## Overlap of GOFER and FEDS with fires already used (from the repo)

The project's 44 forecast events are the 29 Choi US and 15 Choi KR fires (`forecast/data/environment/events.json`).
`research/forecast-v2/SPLIT.json` puts 23 US fires in the fit set and holds out 6 US 2024 fires (Wapiti, Goat, Lava,
RedRock, Pioneer, FishCreek) and KFS_01/04/06/13. Its note says c651 was fit on KFS_02, KFS_03 and the 2020–2022 US
fit fires.

- **GOFER fires that are forecast fit fires (10 of 28, matched by name):** Dixie, River Complex, Antelope, August Complex, North Complex (PNF), Monument, Creek, SQF Complex, McCash, Red Salmon Complex.
- **GOFER fire used elsewhere:** Caldor is the routing Caldor/Rim engineering panel (`research/sipp-routing`, `research/next-combined`, `research/routing`). It is not a forecast scoring fire.
- **GOFER fires with no use found on Main (17):** Kincade, Walker, Bobcat, CZU Lightning, Dolan, Glass, July Complex, KNP Complex, LNU Lightning, McFarland, SCU Lightning, Slater and Devil, Tamarack, W-5 Cold Springs, Windy, Zogg, Beckwourth Complex. Caveat: I checked by name on `Main` only. The November GOFER recovery work and other branches may have touched them.
- **FEDS:** fireIDs carry no names, so I matched spatially. Each fire's final Choi footprint was intersected with the last FEDS perimeter of every fireID for the same year. See `feds_overlap.csv` for every match with at least 1 km² of overlap: all 29 Choi US fires for 2020, 2021, 2022 and 2024 (there is no 2023 US event). Every project US fire has one dominant FEDS fireID. FEDS 57413 merges Jack and DevilsKnob (2021). Any other FEDS fireID in those years has not been used by the project's forecast scoring.

## Reference code: read, do not copy

Shallow clones exist only in my scratch space. Nothing is copied into this repo. SHAs are the default-branch HEAD on 2026-11-12.

| Repo | SHA | Licence | Worth reading |
|---|---|---|---|
| PathPlanning/SIPP-IP | 77ca7491345c00b1cec7d0b88fe96cc561e0be25 | MIT | `src/SIPP1.cpp`, `SIPP2.cpp`, `SIPP-IP.cpp`: safe-interval generation from dynamic obstacles and interval projection. Closest to SIPP routing. |
| PathPlanning/SuboptimalSIPP | c358300bacddd48a9b295d9327bc6fe57216438f | **none** (all rights reserved: read only) | `aa_sipp.cpp`: bounded-suboptimal and any-angle SIPP variants. |
| lautenberger/elmfire | f4927b7ce68cb74eb0eb117085cc920782c8644e | AGPL-3.0 + Commons Clause (no selling) | Level-set fire spread and arrival-time rasters (1.3 GB repo). |
| berkeley-firelab/ELMFIRE_VnV_Suite | 050e5ccc58eba6c80621b81083a60f6b117de562 | **none** | Validation cases against observed perimeters; e.g. `cases/Validation/landscape_scale/knp_complex_2021/scripts/` stages GOFER perimeters. |
| pyregence/pyretechnics | e9f4c2730bc0d6a52f8ac7f53a9e8f30a402fd83 | Dual: AGPL-3.0 community / commercial | Scriptable Rothermel and eulerian spread, arrival-time outputs. |
| sustia-llc/firespread | 8b3c876a92a681c1d2ebbb2cc6d6c7cad62092d9 | Apache-2.0 / MIT | Minimum-travel-time (shortest-path) fire spread with seeded ensembles. New repo with few stars, so treat as unreviewed. |
| Earth-Information-System/fireatlas | bee8983f0e86a50de8879767410093f980c49cfe | **none** | FEDS algorithm v1.4.x: alpha-shape perimeters and 12-hourly fire tracking. |
| tianjialiu/GOFER | 8c0cc69a5dfb7900088cd4d3ae2263b78ffabdfa | MIT | GOFER perimeter, fire-line and spread-rate derivation (Earth Engine JS plus R). |
| lisestdenis/ics209plus | 0acf92dd8be933c8870a925c20d4e2fe38b628c2 | **none** | Builds ICS-209-PLUS from raw ICS-209 reports. |
| maxwellCcook/ics209-plus-fired | cd2b5a4d1b96637ab0b3ec8e315dbb93c4115fb1 | **none** | Links ICS-209-PLUS incidents to FIRED satellite events. |

Searches for certifying shortest-path checkers (LEDA-style) found nothing usable. The only hit,
`shawncalvinsnelling/AXEZENT-Robust-Shortest-Path-Verifier` (MIT, new, unreviewed), is not recommended without review.

## Incident metadata join for S-D9 (metadata only; no perimeters opened)

`incident_metadata.csv` has 733 rows keyed by `Incident_C`: the 704 incidents of S-D9 `cohort/COHORT_SPLIT.csv` @ cffd66c3, plus the 23 forecast-v2
fit fires and 6 held-out fires. `incident_metadata_join.py` regenerates it with
`python3 incident_metadata_join.py COHORT_SPLIT.csv nirops_incidents_v2.csv ics209-plus-wf_incidents_1999to2020.csv OUT.csv`.
- **Primary source:** NIFC WFIGS Incident Locations (services3.arcgis.com, public ArcGIS FeatureServer), joined by IRWIN ID. It matched 724 of 733; the 9 unmatched are all part a.
  `poo_lat`/`poo_lon` is the WFIGS point geometry (point of origin, EPSG:4326). `initial_lat`/`initial_lon` is the WFIGS InitialLatitude/Longitude
  (initial report location), which can lie about 20 km from the point of origin and is blank for 45 rows. `discovery_utc` is FireDiscoveryDateTime.
- **Cross-check:** ICS-209-PLUS (1999–2020 only), joined by POO state + 6-digit incident number + start year, keeping only unambiguous keys. It matched 149 incidents, all from 2020.
  Its POO agrees with WFIGS (median 0.001 km); 4 rows are over 10 km apart (maximum 91 km), see `ics209_vs_wfigs_poo_km`.
- For 13 incidents the WFIGS `discovery_utc` is later than the first NIROPS survey. These are left as published.
- `first_utc`/`last_utc` come from the NIROPS incident table (see "Pinned-file versions" below).

## Pinned-file versions (rule: a file another stream has pinned is never edited in place)

| Version | Path | sha256 | Where | Change |
|---|---|---|---|---|
| v1a | `nirops_incidents.csv` | `66581245…53b6` | commit 0cf39959 only | First version, including `max_acres`. |
| v1 | `nirops_incidents.csv` | `f2aae4b8…d9ca` | commit 3129ad59 only (**pinned by S-D9 COHORT_SPLIT**) | Added `shares_irwin_with_project_fire`. Still contains `max_acres` for all 737 incidents, including the sealed parts b, c and d. |
| v2 | `nirops_incidents_v2.csv` | `9cd9c260…030a` | branch head | Same rows and the other columns as v1, with **`max_acres` removed**. |

Commit 259ef5b4 edited `nirops_incidents.csv` in place (dropping `max_acres`), which broke S-D9's pin. It is now corrected: the edited table lives
under the new name `nirops_incidents_v2.csv`, and v1 is **deliberately not restored at the branch head**. That keeps sealed-set `max_acres` out
of anything merged to main; v1 remains retrievable byte-for-byte with `git show 3129ad59:research/harness-2026-11/data-fetch/nirops_incidents.csv`.
