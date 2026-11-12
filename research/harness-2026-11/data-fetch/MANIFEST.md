# External data and reference code — harness 2026-11

Owner: Daniel (data fetcher). Fetched and checked 2026-11-12 from a cloud session whose network allows
zenodo.org, the Copernicus DEM S3 bucket, GitHub (git) and package registries, and blocks the rest (see the
Blocked table below).

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
| `glo30_N36_E128`, `glo30_N36_E129`: Copernicus GLO-30 DEM | Leo F-C1 | COG, EPSG:4326, 3600x3600 at 1″ (about 30 m), float32 metres (EGM2008), together covering lon 128–130 E, lat 36–37 N. Elevation range 17.7–1436.4 m and −6.2–1216.5 m. No nodata value is set. The bbox still needs confirming from the planner cache (`fetch.py dem --bbox` picks the tiles). |
| `gofer_v0.2`: GOFER, Liu et al. 2024 | Victor S-D9 | Publisher md5 matches. `GOFER_Combined/GOFERC_fireProg.shp`: EPSG:4326, 20,301 hourly perimeters for all 28 fires (Kincade 2019 through KNP/Windy 2021). Fields: fname, fyear, tUTC, tLocal, timestep, farea, fareaPer, fperim. East-only and West-only variants and active fire lines (cfireLine, rfireLine) are included. **The repo's November note says the GOFER archive was already recovered, but its record ID and checksum are not on `Main`, so I can't confirm it is this v0.2 file (an older v0.1 record is 10.5281/zenodo.8327264).** |
| `toa_kriging_choi2026` (+ `_readme`): Choi, Seo, Cha 2026 kriged arrival times | Victor S-D9, Elena S-D2 | Publisher md5 matches. 29 US fires × {`_toa`, `_std`} (EPSG:5070, 375 m, nodata −1, hours since the `t0_utc` tag) and 15 Korean fires (EPSG:5179, NaN nodata, hours since KFS ignition). The method code is identical in name to the copy already vendored under `routing-review/*/sources/zenodo_21788344/`. |
| `small/choi2026_wapiti/` (committed, 30 KB) | Elena S-D2 | Wapiti (ID-BOF-000683, 2024) TOA and kriging-SD rasters: 111×105 cells, 3,787 valid, t0 2024-08-01 00:00 UTC, TOA 122.7–1839.3 h, SD 30.8–80.9 h. 63 NIROPS surveys from 2024-08-01 to 2024-10-26. CC-BY-4.0: cite Choi et al. 2026 and the Zenodo DOI. |
| `airborne_ir_rim_2013`, `airborne_ir_dixie_2021`: airborne IR perimeters (Hatchett 2025) | Victor S-D9 | Publisher md5 matches. Rim: 33 shapefiles, 2013-08-20 to 09-26. Dixie: 41 shapefiles, 2021-07-15 to 09-27. EPSG:4326. Layer names are inconsistent (HeatPerimeter, IntenseHeat, ScatteredHeat, Growth), and times are in the filenames in local time. This is a partial NIROPS substitute, not the 2020–2024 collection. |
| `feds_conus_2021_lf_perimeter`: FEDS CONUS archive v1.4.1 | Victor S-D9 | Publisher md5 matches. FlatGeobuf, EPSG:9311, 62,760 12-hourly perimeters, 1,645 fireIDs, all of 2021. The 2019 and 2020 files are scripted with publisher md5 but not downloaded. The archive supersedes the Chen et al. 2022 California figshare release (figshare is blocked). Every year 2012–2025 plus `_lf_fireline` and `_lf_newfirepix` are in record 22921773. |
| `wildfirespreadts_full`: WildfireSpreadTS | Victor S-D9 | **Scripted only.** It is 48.4 GB (publisher md5 recorded) and does not fit in a session's disk allowance. I have not downloaded or opened it. The 7.8 MB documentation PDF is also scripted but not yet opened. |

## Gated or blocked: not fetched

I did not work around any of these. Each "blocked" row is a `CONNECT tunnel failed, response 403` from this
environment's egress proxy.

| Need | Source | Status |
|---|---|---|
| NIROPS perimeters 2020–2024 plus flight-coverage metadata | Magstadt et al., Mendeley Data 10.17632/95rj5d379g.1 (CC-BY, cited by Choi 2026); ftp.wildfire.gov NIROPS archive | **Blocked**: data.mendeley.com, ftp.wildfire.gov |
| FEDS California archive (Chen et al. 2022) | figshare 10.6084/m9.figshare.c.5601537 | **Blocked**: figshare.com and ndownloader.figshare.com. Superseded by the FEDS CONUS Zenodo archive above. |
| Papers: GOFER ESSD and Choi 2026 article | doi.org, mdpi.com | **Blocked**. The Zenodo READMEs carry the needed format details. |
| KFS wildfire status history | data.go.kr dataset 15121205 | **Blocked**: www.data.go.kr. I can't confirm from here whether the file download needs login. |
| KMA API hub (weather) | apihub.kma.go.kr | **Blocked**. It also requires a free account and a per-user auth key (`authKey` query parameter). I have not registered. |
| KMA open data portal | data.kma.go.kr | **Blocked**. Account needed for bulk download. |
| Mountain weather (KFS/NIFoS) | www.forest.go.kr, www.nifos.go.kr; the API is distributed via data.go.kr | **Blocked**. data.go.kr OpenAPI services need a data.go.kr account and a per-service usage application, which issues a service key. |
| Road incident feed | ITS/data.go.kr OpenAPI | **Blocked**. Same data.go.kr key process as above; not verified. |
| NASA FIRMS active fire | firms.modaps.eosdis.nasa.gov | **Blocked**. The area API needs a free MAP_KEY. |
| ICS-209-PLUS data tables | figshare (St. Denis et al.) | **Blocked**. The code repositories are listed below. |
| Fireline dataset, Arkowitz et al. 2025 | — | **Not found.** Zenodo and GitHub search found no matching record or repo (GitHub user `arkowitz` exists, but this session can't list its repos). I need a DOI or URL. Zenodo 24148495 ("When Do Firelines Hold?", Matey et al., 1.25 GB, CC-BY) is a different but related dataset and has not been downloaded. |

Other Zenodo records seen and not fetched: FEDS-MTBS 20187963 (readme fetched), FEDS Western US 15261836
(CC-BY-NC, superseded), FireBench Caldor 23383592 (Apache-2.0, 697 MB), ELMFIRE validation 23574586 (no files
attached).

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
