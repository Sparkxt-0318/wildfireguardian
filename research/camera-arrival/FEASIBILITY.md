# Step 0 - Feasibility gate: GOFER fires x HPWREN cameras

**Credits.** Camera sites, view directions and archive: HPWREN (hpwren.ucsd.edu), UC San Diego (archived data CC BY-NC 4.0). *HPWREN data are not intended to be used as a decision-making tool, or as a replacement for such tools.* Fire perimeters: GOFER v0.2, Liu, T. et al., *GOES-Observed Fire Event Representation (GOFER) product for 28 California wildfires from 2019-2021*, Zenodo, doi:10.5281/zenodo.14642378 (version DOI, verified from the Zenodo record; concept DOI 10.5281/zenodo.8327264); method paper Liu et al. 2024, ESSD 16, 1395. DEM: AWS Terrain Tiles 'skadi' 1-arc-second (~30 m) elevation tiles (SRTM / USGS NED derived), https://s3.amazonaws.com/elevation-tiles-prod/skadi/.

## Verdict

**GATE: FAIL.** geometric_pass = false, gate_pass = false.

1. **Geometry fails, narrowly.** No fixed HPWREN camera sees at least 10% of any GOFER fire's final burned area at ground level, inside its own horizontal field of view. The best are `chino-n-mobo-c` and `wilson-e-mobo-c` on **Bobcat 2020**, at 7.7% and 7.7%. With the secondary +20 m target (flames or plume above the ground) these become 10.7% and 11.1%. The union of the two best Mount Wilson colour cameras (n+e) reaches 10.8% at ground level. Neither of these is the gate criterion, which is a single camera at ground level.
2. **The archive is not retrievable, for any candidate.** No 1-minute JPEGs exist for 2019-2021, and the image lists return HTTP 403. For Mount Wilson, 69Bravo and Green Peak, 3-hour MP4s exist for the Bobcat dates, with HEAD returning 200, but they are in S3 **DEEP_ARCHIVE**. A GET returns 403 until HPWREN restores them. Chino Hills and Iron Horse Vineyards return 403 for lists and videos on the dates probed, so we found no archive, and the camera may not have existed then.
3. Per the instructions, the work **stops at Step 0**. No non-GOFER fire was substituted.

## Method

* Fires: the 28 GOFER v0.2 fires, using the final (last hourly) GOFER-Combined cumulative perimeter (`cache/gofer/final_perimeters.gpkg`).
* Cameras: 82 HPWREN sites and 503 cameras from `sites.js` (`outputs/hpwren_cameras.csv`). A site is a candidate if it lies within 60 km of the nearest point of the final perimeter. Distances are computed in EPSG:3310.
* Burned cells: each perimeter is rasterised on a 30 m grid in a camera-centred azimuthal-equidistant projection. A cell counts as burned if its centre lies inside the perimeter. The raster areas match the GOFER `farea` to within 0.1% (e.g. Bobcat 583.7 vs 583.9 km2, LNU 1540.0 vs 1538.8 km2).
* DEM: skadi 1-arcsec tiles, cached in `cache/dem/`, bilinearly interpolated.
* Line of sight: a polar sweep from the camera (`src/viewshed.py`), with rays every <=20 m of arc at maximum range and samples every 30 m along each ray. The apparent tangent is (z - d^2(1-k)/2R - z_cam)/d, with earth curvature R = 6371 km and refraction k = 0.13. A target is visible if its tangent is >= the running maximum of all ray samples up to range d - 30 m. Targets use their own DEM height, either at ground level (the gate) or at +20 m (secondary).
* Camera height z_cam is the DEM elevation at the listed site coordinate plus the mast height above ground (AGL) from HPWREN metadata. Sites with no AGL use an **assumed 10 m** (cynbk, latem, mlee, svct). Two sensitivity variants are reported: (a) the highest DEM point within 150 m of the listed position, since HPWREN says many coordinates are rounded, plus AGL; (b) the `sites.js` elevation plus AGL.
* Field of view: each fixed camera uses its own azimuth and horizontal FOV from `sites.js`. These are 90 deg for every n/e/s/w mobo camera here, and 75 deg for the Delphire cameras, so the 90 deg default was never needed. The FOV test is horizontal only; the vertical FOV was not modelled. A camera pointing away from the fire scores 0. PTZ (`*-axis`) cameras have no fixed view, so they are listed with the site-level any-direction fraction but **excluded from the gate**.
* **Visible burned fraction** = visible burned cells / all burned cells of the final perimeter. *In-FOV visible fraction* = (visible and inside the camera's horizontal FOV) / all burned cells. The gate uses the in-FOV ground fraction of a single fixed camera, with a threshold of 10%.
* Archive: `src/hpwren_archive.archive_exists` probes each camera with an in-FOV visible fraction > 0, and each PTZ camera at a site with visibility > 0. It uses the Pacific date of the fire's peak GOFER daily growth, block Q7 (18-21 PT, dusk/night). For each probe it GETs the image list and HEADs the video, and HEADs the first image only if a list exists. The two best fixed colour cameras were also probed on all 8 blocks of the peak date, and on Q7 of the first GOFER date. Requests were sequential and >=1.2 s apart, with User-Agent `research-poc-camera-arrival/0.1`. Every response is cached in `cache/http/` and was never refetched.
* Checks: `src/test_viewshed.py` has three synthetic tests, all passing. They cover the analytic shadow of a flat-topped ridge at 5050-10100 m, 100% agreement with a dense brute-force ray check on 400 random targets, and the curvature horizon at 12.10 km for a 10 m camera. Real-terrain spot checks compare the polar viewshed with brute-force line of sight (10-15 m steps) on 300 random burned cells for each of the top pairs:

| fire | site | n | agreement | polar visible | brute-force visible |
|---|---|---|---|---|---|
| Bobcat | wilson | 300 | 0.997 | 12.3% | 12.0% |
| Bobcat | chino | 300 | 0.997 | 7.7% | 8.0% |
| Kincade | ihvy | 300 | 1.000 | 3.7% | 3.7% |
| Glass | ihvy | 300 | 1.000 | 3.0% | 3.0% |
| Bobcat | 69bravo | 300 | 1.000 | 2.0% | 2.0% |
| Bobcat | dwpgm | 300 | 0.993 | 0.7% | 0.7% |
| Bobcat | svct | 300 | 1.000 | 0.3% | 0.3% |
| Bobcat | mlee | 300 | 1.000 | 1.0% | 1.0% |

Quick-look maps (gitignored): `cache/feasibility_quicklooks/<fire>__<site>.png`.

## Limitations of this gate

* Ground-surface line of sight is **conservative** for flames and glow, which rise above terrain, and for smoke plumes. It is also **optimistic** in other ways: it ignores vegetation and buildings, the vertical FOV, haze, image resolution, and the fact that a cell must be visible *while it burns*, not just on the final map.
* A 30 m DEM smooths summits and ridges. The camera position comes from rounded `sites.js` coordinates; see the sensitivity columns. Some `sites.js` elevations disagree strongly with the DEM: cynbk is listed at 1630, and 1630 ft is about 497 m, which matches the DEM's 494.5 m, so the value is probably in feet. d_lhlg is listed at 969 m against 578 m in the DEM. latem is listed at 0.
* GOFER perimeters are GOES-derived at about 2 km pixels. Their final areas differ from the official acres for some fires (Bobcat: GOFER 584 km2 vs official 469 km2), so the denominator is the GOFER burned area, not the true one.
* A 403 from HPWREN's S3/CDN does not distinguish 'missing' from 'forbidden'. Only one 3 h block per camera was probed, except for the two deep-checked cameras.

## GOFER fires (28)

Times are GOFER end-of-hour UTC, and the hourly labels are nominal. The bbox is the extent of the final perimeter (lon_min, lat_min, lon_max, lat_max).

| # | fire | year | first perimeter (UTC) | last perimeter (UTC) | final GOFER km2 | bbox | nearest HPWREN site within 60 km |
|---|---|---|---|---|---|---|---|
| 1 | Kincade | 2019 | 2019-10-24 05:00 | 2019-10-29 18:00 | 346.8 | -122.8913, 38.5395, -122.6555, 38.8077 | ihvy (14.2 km) |
| 2 | Walker | 2019 | 2019-09-04 22:00 | 2019-09-12 22:00 | 267.7 | -120.7120, 40.0042, -120.4627, 40.1727 | none |
| 3 | August Complex | 2020 | 2020-08-16 22:00 | 2020-10-16 22:00 | 4342.8 | -123.5296, 39.4351, -122.5518, 40.4448 | none |
| 4 | Bobcat | 2020 | 2020-09-06 20:00 | 2020-09-24 20:00 | 583.9 | -118.1078, 34.1562, -117.7575, 34.4845 | wilson (0.3 km), d_mwvp (6.4 km), mlee (24.0 km), chino (34.1 km), cynbk (40.0 km), svct (40.1 km), latem (44.8 km), dwpgm (45.0 km), 69bravo (52.2 km) |
| 5 | CZU Lightning Complex | 2020 | 2020-08-17 01:00 | 2020-08-22 05:00 | 283.0 | -122.3429, 37.0362, -122.1224, 37.2689 | d_lhlg (15.3 km) |
| 6 | Creek | 2020 | 2020-09-05 07:00 | 2020-11-09 20:00 | 1615.0 | -119.4773, 36.9845, -118.9540, 37.6412 | none |
| 7 | Dolan | 2020 | 2020-08-19 03:00 | 2020-09-17 02:00 | 501.5 | -121.6719, 35.9510, -121.2726, 36.2115 | none |
| 8 | Glass | 2020 | 2020-09-27 11:00 | 2020-10-05 07:00 | 352.5 | -122.6712, 38.4398, -122.4296, 38.6788 | ihvy (20.0 km) |
| 9 | July Complex | 2020 | 2020-07-22 22:00 | 2020-07-31 03:00 | 173.9 | -121.5555, 41.3495, -121.0713, 41.8215 | none |
| 10 | LNU Lightning Complex | 2020 | 2020-08-17 16:00 | 2020-08-28 21:00 | 1538.8 | -123.1087, 38.2938, -121.9854, 38.9442 | ihvy (10.9 km) |
| 11 | North Complex | 2020 | 2020-08-17 22:00 | 2020-10-01 16:00 | 1344.5 | -121.4760, 39.5102, -120.7565, 39.9445 | none |
| 12 | Red Salmon Complex | 2020 | 2020-07-27 23:00 | 2020-10-10 00:00 | 575.1 | -123.5700, 40.9776, -123.2313, 41.2470 | none |
| 13 | SCU Lightning Complex | 2020 | 2020-08-16 17:00 | 2020-08-31 03:00 | 1525.8 | -121.8610, 37.1036, -121.1666, 37.5918 | d_lhlg (30.4 km) |
| 14 | SQF Complex | 2020 | 2020-08-20 21:00 | 2020-10-07 20:00 | 786.4 | -118.8184, 36.0642, -118.2897, 36.3854 | none |
| 15 | Slater and Devil | 2020 | 2020-09-08 14:00 | 2020-09-22 03:00 | 697.0 | -123.7748, 41.7636, -123.1882, 42.0879 | none |
| 16 | W-5 Cold Springs | 2020 | 2020-08-18 21:00 | 2020-08-29 20:00 | 364.2 | -120.2965, 40.9865, -119.9278, 41.2349 | none |
| 17 | Zogg | 2020 | 2020-09-27 22:00 | 2020-09-30 20:00 | 222.8 | -122.7229, 40.2953, -122.5293, 40.5585 | none |
| 18 | Antelope | 2021 | 2021-08-01 21:00 | 2021-09-10 02:00 | 599.1 | -122.0132, 41.4523, -121.5277, 41.7577 | none |
| 19 | Beckwourth Complex | 2021 | 2021-07-01 00:00 | 2021-08-05 03:00 | 558.3 | -120.4048, 39.8255, -120.0050, 40.0864 | none |
| 20 | Caldor | 2021 | 2021-08-15 08:00 | 2021-09-10 03:00 | 994.1 | -120.6675, 38.5543, -119.9502, 38.8706 | none |
| 21 | Dixie | 2021 | 2021-07-14 06:00 | 2021-09-10 03:00 | 4389.2 | -121.5524, 39.8529, -120.1955, 40.6883 | none |
| 22 | KNP Complex | 2021 | 2021-09-10 18:00 | 2021-10-07 02:00 | 388.6 | -118.9585, 36.4267, -118.6742, 36.7317 | none |
| 23 | McCash | 2021 | 2021-08-01 08:00 | 2021-09-24 08:00 | 405.8 | -123.5035, 41.4236, -123.1860, 41.6917 | none |
| 24 | McFarland | 2021 | 2021-07-30 10:00 | 2021-08-25 22:00 | 567.0 | -123.1712, 40.1507, -122.7018, 40.3963 | none |
| 25 | Monument | 2021 | 2021-07-31 05:00 | 2021-09-17 20:00 | 922.5 | -123.4860, 40.5347, -123.0220, 40.9196 | none |
| 26 | River Complex | 2021 | 2021-08-01 05:00 | 2021-09-26 13:00 | 931.3 | -123.3068, 40.9497, -122.7009, 41.3427 | none |
| 27 | Tamarack | 2021 | 2021-07-04 21:00 | 2021-07-25 20:00 | 375.3 | -119.8860, 38.6087, -119.5312, 38.8140 | none |
| 28 | Windy | 2021 | 2021-09-10 03:00 | 2021-10-06 01:00 | 427.1 | -118.7240, 35.8374, -118.4748, 36.1069 | none |

14 fire x site pairs lie within 60 km, covering 6 fires. The other 22 fires (mostly northern California) have no HPWREN site within 60 km.

## Fire x site summary (all cameras at the site, any direction)

| fire | site | site to perimeter km | median km to burned cells | z_cam m (DEM + AGL) | visible ground | visible +20 m | sens: local max 150 m | sens: listed elev | best 2 colour cams (union, ground) |
|---|---|---|---|---|---|---|---|---|---|
| Bobcat | wilson | 0.27 | 19.5 | 1784 (1734 + 50) | 11.1% | 15.6% | 11.2% | 9.8% | 10.8% wilson-e-mobo-c+wilson-n-mobo-c |
| Bobcat | chino | 34.14 | 49.6 | 549 (541 + 8) | 7.7% | 10.7% | 7.7% | 7.7% | 7.7% chino-e-mobo-c+chino-n-mobo-c |
| Kincade | ihvy | 14.15 | 29.0 | 56 (43 + 13) | 4.8% | 7.4% | 9.3% | 7.5% | 4.8% ihvy-e-mobo-c+ihvy-n-mobo-c |
| Glass | ihvy | 19.98 | 33.6 | 56 (43 + 13) | 4.0% | 7.8% | 4.3% | 4.2% | 4.0% ihvy-e-mobo-c+ihvy-n-mobo-c |
| Bobcat | 69bravo | 52.19 | 71.6 | 751 (746 + 5) | 1.9% | 3.1% | 1.9% | 1.9% | 1.9% 69bravo-e-mobo-c+69bravo-n-mobo-c |
| Bobcat | dwpgm | 45.00 | 64.5 | 597 (582 + 15) | 1.5% | 2.5% | 1.5% | 1.5% | 1.5% dwpgm-e-mobo-c+dwpgm-n-mobo-c |
| Bobcat | svct | 40.09 | 59.6 | 596 (586 + 10 assumed) | 1.1% | 1.8% | 1.1% | 1.1% | 0.0%  |
| Bobcat | mlee | 24.02 | 43.9 | 528 (518 + 10 assumed) | 1.0% | 1.7% | 1.1% | 1.0% | 0.0%  |
| Bobcat | d_mwvp | 6.42 | 26.7 | 276 (273 + 3) | 0.5% | 0.9% | 0.6% | 0.5% | 0.0%  |
| Bobcat | cynbk | 39.99 | 59.6 | 504 (494 + 10 assumed) | 0.0% | 0.0% | 1.3% | 3.4% | 0.0%  |
| Bobcat | latem | 44.81 | 64.4 | 137 (127 + 10 assumed) | 0.0% | 0.0% | 0.0% | n/a | 0.0%  |
| CZU Lightning Complex | d_lhlg | 15.35 | 25.0 | 580 (578 + 2) | 0.0% | 0.0% | 0.0% | 7.1% | 0.0%  |
| LNU Lightning Complex | ihvy | 10.93 | 60.2 | 56 (43 + 13) | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% ihvy-e-mobo-c+ihvy-n-mobo-c |
| SCU Lightning Complex | d_lhlg | 30.45 | 52.1 | 580 (578 + 2) | 0.0% | 0.0% | 0.0% | 2.0% | 0.0%  |

## Full fire x camera table

`dist` = distance from the site to the nearest burned cell (km). `in-FOV` = burned cells that are inside this camera's horizontal FOV and visible, divided by all burned cells. The archive column gives the result of the probe; the exact HTTP statuses are in `outputs/feasibility_table.csv` (`archive_tried`) and `outputs/feasibility_archive.json`.

| fire | camera | kind | az / HFOV | dist km | site visible ground / +20 m | in-FOV burn share | in-FOV visible ground | in-FOV visible +20 m | sens local-max / listed | archive images for fire dates |
|---|---|---|---|---|---|---|---|---|---|---|
| Bobcat | chino-n-mobo-c | fixed-color | 0 / 90 | 34.2 | 7.7% / 10.7% | 100.0% | **7.7%** | 10.7% | 7.7% / 7.7% | no - list 403 and video 403 (no archive found / camera may not have existed) |
| Bobcat | chino-n-mobo-m | fixed-monochrome | 0 / 90 | 34.2 | 7.7% / 10.7% | 100.0% | **7.7%** | 10.7% | 7.7% / 7.7% | no - list 403 and video 403 (no archive found / camera may not have existed) |
| Bobcat | wilson-e-mobo-c | fixed-color | 90 / 90 | 0.3 | 11.1% / 15.6% | 54.7% | **7.7%** | 11.1% | 7.7% / 6.9% | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | wilson-e-mobo-m | fixed-monochrome | 90 / 90 | 0.3 | 11.1% / 15.6% | 54.7% | **7.7%** | 11.1% | 7.7% / 6.9% | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Kincade | ihvy-n-mobo-c | fixed-color | 0 / 90 | 14.2 | 4.8% / 7.4% | 95.7% | **4.8%** | 7.4% | 9.2% / 7.4% | no - list 403 and video 403 (no archive found / camera may not have existed) |
| Kincade | ihvy-n-mobo-m | fixed-monochrome | 0 / 90 | 14.2 | 4.8% / 7.4% | 95.7% | **4.8%** | 7.4% | 9.2% / 7.4% | no - list 403 and video 403 (no archive found / camera may not have existed) |
| Glass | ihvy-e-mobo-c | fixed-color | 90 / 90 | 20.0 | 4.0% / 7.8% | 100.0% | **4.0%** | 7.8% | 4.3% / 4.2% | no - list 403 and video 403 (no archive found / camera may not have existed) |
| Glass | ihvy-e-mobo-m | fixed-monochrome | 90 / 90 | 20.0 | 4.0% / 7.8% | 100.0% | **4.0%** | 7.8% | 4.3% / 4.2% | no - list 403 and video 403 (no archive found / camera may not have existed) |
| Bobcat | wilson-n-mobo-c | fixed-color | 0 / 90 | 0.3 | 11.1% / 15.6% | 44.2% | **3.1%** | 4.1% | 3.2% / 2.8% | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | wilson-n-mobo-m | fixed-monochrome | 0 / 90 | 0.3 | 11.1% / 15.6% | 44.2% | **3.1%** | 4.1% | 3.2% / 2.8% | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | 69bravo-e-mobo-c | fixed-color | 90 / 90 | 52.2 | 1.9% / 3.1% | 100.0% | **1.9%** | 3.1% | 1.9% / 1.9% | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | 69bravo-e-mobo-m | fixed-monochrome | 90 / 90 | 52.2 | 1.9% / 3.1% | 100.0% | **1.9%** | 3.1% | 1.9% / 1.9% | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | dwpgm-e-mobo-c | fixed-color | 90 / 90 | 45.0 | 1.5% / 2.5% | 100.0% | **1.5%** | 2.5% | 1.5% / 1.5% | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | dwpgm-e-mobo-m | fixed-monochrome | 90 / 90 | 45.0 | 1.5% / 2.5% | 100.0% | **1.5%** | 2.5% | 1.5% / 1.5% | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | wilson-s-mobo-c | fixed-color | 180 / 90 | 0.3 | 11.1% / 15.6% | 1.2% | **0.2%** | 0.4% | 0.2% / 0.2% | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | wilson-s-mobo-m | fixed-monochrome | 180 / 90 | 0.3 | 11.1% / 15.6% | 1.2% | **0.2%** | 0.4% | 0.2% / 0.2% | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | wilson-w-mobo-c | fixed-color | 270 / 90 | 0.3 | 11.1% / 15.6% | 0.1% | **0.0%** | 0.0% | 0.0% / 0.0% | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | wilson-w-mobo-m | fixed-monochrome | 270 / 90 | 0.3 | 11.1% / 15.6% | 0.1% | **0.0%** | 0.0% | 0.0% / 0.0% | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | chino-e-mobo-c | fixed-color | 90 / 90 | 34.2 | 7.7% / 10.7% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | chino-e-mobo-m | fixed-monochrome | 90 / 90 | 34.2 | 7.7% / 10.7% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | chino-s-mobo-c | fixed-color | 180 / 90 | 34.2 | 7.7% / 10.7% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | chino-s-mobo-m | fixed-monochrome | 180 / 90 | 34.2 | 7.7% / 10.7% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | chino-w-mobo-c | fixed-color | 270 / 90 | 34.2 | 7.7% / 10.7% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | chino-w-mobo-m | fixed-monochrome | 270 / 90 | 34.2 | 7.7% / 10.7% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Kincade | ihvy-e-mobo-c | fixed-color | 90 / 90 | 14.2 | 4.8% / 7.4% | 4.4% | **0.0%** | 0.0% | 0.1% / 0.0% | not checked (no visible burned cells in view) |
| Kincade | ihvy-e-mobo-m | fixed-monochrome | 90 / 90 | 14.2 | 4.8% / 7.4% | 4.4% | **0.0%** | 0.0% | 0.1% / 0.0% | not checked (no visible burned cells in view) |
| Kincade | ihvy-s-mobo-c | fixed-color | 180 / 90 | 14.2 | 4.8% / 7.4% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Kincade | ihvy-s-mobo-m | fixed-monochrome | 180 / 90 | 14.2 | 4.8% / 7.4% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Kincade | ihvy-w-mobo-c | fixed-color | 270 / 90 | 14.2 | 4.8% / 7.4% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Kincade | ihvy-w-mobo-m | fixed-monochrome | 270 / 90 | 14.2 | 4.8% / 7.4% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Glass | ihvy-n-mobo-c | fixed-color | 0 / 90 | 20.0 | 4.0% / 7.8% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Glass | ihvy-n-mobo-m | fixed-monochrome | 0 / 90 | 20.0 | 4.0% / 7.8% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Glass | ihvy-s-mobo-c | fixed-color | 180 / 90 | 20.0 | 4.0% / 7.8% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Glass | ihvy-s-mobo-m | fixed-monochrome | 180 / 90 | 20.0 | 4.0% / 7.8% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Glass | ihvy-w-mobo-c | fixed-color | 270 / 90 | 20.0 | 4.0% / 7.8% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Glass | ihvy-w-mobo-m | fixed-monochrome | 270 / 90 | 20.0 | 4.0% / 7.8% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | 69bravo-n-mobo-c | fixed-color | 0 / 90 | 52.2 | 1.9% / 3.1% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | 69bravo-n-mobo-m | fixed-monochrome | 0 / 90 | 52.2 | 1.9% / 3.1% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | 69bravo-s-mobo-c | fixed-color | 180 / 90 | 52.2 | 1.9% / 3.1% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | 69bravo-s-mobo-m | fixed-monochrome | 180 / 90 | 52.2 | 1.9% / 3.1% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | 69bravo-w-mobo-c | fixed-color | 270 / 90 | 52.2 | 1.9% / 3.1% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | 69bravo-w-mobo-m | fixed-monochrome | 270 / 90 | 52.2 | 1.9% / 3.1% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | dwpgm-n-mobo-c | fixed-color | 0 / 90 | 45.0 | 1.5% / 2.5% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | dwpgm-n-mobo-m | fixed-monochrome | 0 / 90 | 45.0 | 1.5% / 2.5% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | dwpgm-s-mobo-c | fixed-color | 180 / 90 | 45.0 | 1.5% / 2.5% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | dwpgm-s-mobo-m | fixed-monochrome | 180 / 90 | 45.0 | 1.5% / 2.5% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | dwpgm-w-mobo-c | fixed-color | 270 / 90 | 45.0 | 1.5% / 2.5% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | dwpgm-w-mobo-m | fixed-monochrome | 270 / 90 | 45.0 | 1.5% / 2.5% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | mwvp-n-delphire | fixed-experimental | 20 / 75 | 6.4 | 0.5% / 0.9% | 79.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | mwvp-nw-delphire | fixed-experimental | 340 / 75 | 6.4 | 0.5% / 0.9% | 6.2% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| CZU Lightning Complex | lhlg-s-delphire | fixed-experimental | 210 / 75 | 15.4 | 0.0% / 0.0% | 15.8% | **0.0%** | 0.0% | 0.0% / 0.6% | not checked (no visible burned cells in view) |
| CZU Lightning Complex | lhlg-w-delphire | fixed-experimental | 310 / 75 | 15.4 | 0.0% / 0.0% | 33.2% | **0.0%** | 0.0% | 0.0% / 1.7% | not checked (no visible burned cells in view) |
| LNU Lightning Complex | ihvy-n-mobo-c | fixed-color | 0 / 90 | 10.9 | 0.0% / 0.0% | 14.9% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| LNU Lightning Complex | ihvy-n-mobo-m | fixed-monochrome | 0 / 90 | 10.9 | 0.0% / 0.0% | 14.9% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| LNU Lightning Complex | ihvy-e-mobo-c | fixed-color | 90 / 90 | 10.9 | 0.0% / 0.0% | 85.1% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| LNU Lightning Complex | ihvy-e-mobo-m | fixed-monochrome | 90 / 90 | 10.9 | 0.0% / 0.0% | 85.1% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| LNU Lightning Complex | ihvy-s-mobo-c | fixed-color | 180 / 90 | 10.9 | 0.0% / 0.0% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| LNU Lightning Complex | ihvy-s-mobo-m | fixed-monochrome | 180 / 90 | 10.9 | 0.0% / 0.0% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| LNU Lightning Complex | ihvy-w-mobo-c | fixed-color | 270 / 90 | 10.9 | 0.0% / 0.0% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| LNU Lightning Complex | ihvy-w-mobo-m | fixed-monochrome | 270 / 90 | 10.9 | 0.0% / 0.0% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| SCU Lightning Complex | lhlg-s-delphire | fixed-experimental | 210 / 75 | 30.5 | 0.0% / 0.0% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| SCU Lightning Complex | lhlg-w-delphire | fixed-experimental | 310 / 75 | 30.5 | 0.0% / 0.0% | 0.0% | **0.0%** | 0.0% | 0.0% / 0.0% | not checked (no visible burned cells in view) |
| Bobcat | wilson-e-axis | ptz | PTZ | 0.3 | 11.1% / 15.6% | n/a | **n/a** | n/a | n/a / n/a | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | wilson-w-axis | ptz | PTZ | 0.3 | 11.1% / 15.6% | n/a | **n/a** | n/a | n/a / n/a | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | chino-n-axis | ptz | PTZ | 34.2 | 7.7% / 10.7% | n/a | **n/a** | n/a | n/a / n/a | no - list 403 and video 403 (no archive found / camera may not have existed) |
| Bobcat | chino-s-axis | ptz | PTZ | 34.2 | 7.7% / 10.7% | n/a | **n/a** | n/a | n/a / n/a | no - list 403 and video 403 (no archive found / camera may not have existed) |
| Kincade | ihvy-axis | ptz | PTZ | 14.2 | 4.8% / 7.4% | n/a | **n/a** | n/a | n/a / n/a | no - list 403 and video 403 (no archive found / camera may not have existed) |
| Glass | ihvy-axis | ptz | PTZ | 20.0 | 4.0% / 7.8% | n/a | **n/a** | n/a | n/a / n/a | no - list 403 and video 403 (no archive found / camera may not have existed) |
| Bobcat | 69bravo-w-axis | ptz | PTZ | 52.2 | 1.9% / 3.1% | n/a | **n/a** | n/a | n/a / n/a | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | 69bravo-e-axis | ptz | PTZ | 52.2 | 1.9% / 3.1% | n/a | **n/a** | n/a | n/a / n/a | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | dwpgm-n-axis | ptz | PTZ | 45.0 | 1.5% / 2.5% | n/a | **n/a** | n/a | n/a / n/a | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | dwpgm-s-axis | ptz | PTZ | 45.0 | 1.5% / 2.5% | n/a | **n/a** | n/a | n/a / n/a | no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore) |
| Bobcat | svct-1-axis | ptz | PTZ | 40.1 | 1.1% / 1.8% | n/a | **n/a** | n/a | n/a / n/a | no - list 403 and video 403 (no archive found / camera may not have existed) |
| Bobcat | svct-2-axis | ptz | PTZ | 40.1 | 1.1% / 1.8% | n/a | **n/a** | n/a | n/a / n/a | no - list 403 and video 403 (no archive found / camera may not have existed) |
| Bobcat | mlee-n-axis | ptz | PTZ | 24.0 | 1.0% / 1.7% | n/a | **n/a** | n/a | n/a / n/a | no - list 403 and video 403 (no archive found / camera may not have existed) |
| Bobcat | mlee-s-axis | ptz | PTZ | 24.0 | 1.0% / 1.7% | n/a | **n/a** | n/a | n/a / n/a | no - list 403 and video 403 (no archive found / camera may not have existed) |
| Bobcat | cynbk-1-axis | ptz | PTZ | 40.0 | 0.0% / 0.0% | n/a | **n/a** | n/a | n/a / n/a | not checked (no visible burned cells in view) |
| Bobcat | cynbk-2-axis | ptz | PTZ | 40.0 | 0.0% / 0.0% | n/a | **n/a** | n/a | n/a / n/a | not checked (no visible burned cells in view) |
| Bobcat | latem-1-axis | ptz | PTZ | 44.8 | 0.0% / 0.0% | n/a | **n/a** | n/a | n/a / n/a | not checked (no visible burned cells in view) |
| Bobcat | latem-2-axis | ptz | PTZ | 44.8 | 0.0% / 0.0% | n/a | **n/a** | n/a | n/a / n/a | not checked (no visible burned cells in view) |
| LNU Lightning Complex | ihvy-axis | ptz | PTZ | 10.9 | 0.0% / 0.0% | n/a | **n/a** | n/a | n/a / n/a | not checked (no visible burned cells in view) |

## What a human would need to request from HPWREN (if the project wants to continue with GOFER)

Even after a restore, the best single-camera geometry is below the 10% gate at ground level. Going ahead would therefore need an explicit decision to relax the gate, for example to the +20 m flame target or to the Mount Wilson n+e pair. If that decision is made, the best data case is **Bobcat 2020 seen from Mount Wilson** (`wilson-e-mobo-c`, plus `wilson-n-mobo-c`; the `-m` monochrome twins exist as well). The cameras are 0.3 km from the perimeter, and the median distance to burned cells visible in the e-camera FOV is 11.3 km. 3 h MP4s exist (HEAD 200, DEEP_ARCHIVE) for all 8 blocks of 2020-09-18 and for Q7 of 2020-09-06. Note that the videos give 1 frame per minute only if they hold one frame per archived image; this is unverified until a restored file is inspected.

Request a Glacier restore of `https://cdn.hpwren.ucsd.edu/hpwren-cameras/wilson-e-mobo-c/2020/<YYYYMMDD>/Q<q>.mp4` (and the same paths for `wilson-n-mobo-c`). Make the request through HPWREN's contact page (https://www.hpwren.ucsd.edu/cameras/help.html). HPWREN says retrieval takes about 1 day. The blocks below are ranked by the GOFER new burned area that is terrain-visible inside the wilson-e FOV (`outputs/restore_plan_bobcat_wilson.csv`, from `src/s0_restore_plan.py`). Summed over the whole fire, this is 44.9 km2 for wilson-e and 18.4 km2 for wilson-n, out of 583.8 km2.

| Pacific date | block | GOFER new burned km2 | wilson-e new visible km2 | wilson-n new visible km2 |
|---|---|---|---|---|
| 2020-09-09 | Q2 | 9.17 | 4.01 | 0.00 |
| 2020-09-14 | Q6 | 14.85 | 3.96 | 0.00 |
| 2020-09-06 | Q5 | 11.37 | 3.30 | 0.00 |
| 2020-09-07 | Q1 | 10.21 | 2.93 | 0.00 |
| 2020-09-12 | Q8 | 9.12 | 2.78 | 0.00 |
| 2020-09-10 | Q8 | 5.76 | 2.11 | 0.00 |
| 2020-09-06 | Q6 | 6.58 | 1.91 | 0.00 |
| 2020-09-06 | Q8 | 6.49 | 1.75 | 0.00 |
| 2020-09-07 | Q8 | 10.84 | 1.72 | 0.00 |
| 2020-09-06 | Q7 | 11.71 | 1.62 | 0.00 |
| 2020-09-09 | Q3 | 16.49 | 1.61 | 0.00 |
| 2020-09-14 | Q7 | 8.05 | 1.53 | 2.05 |
| 2020-09-13 | Q5 | 5.50 | 1.34 | 0.00 |
| 2020-09-09 | Q7 | 12.30 | 1.08 | 0.00 |
| 2020-09-12 | Q6 | 2.31 | 1.07 | 0.00 |

The peak GOFER growth day for Bobcat (2020-09-18, 165 km2) was mostly the northward run into the Antelope Valley side, and almost none of it is visible from Mount Wilson.

## Files

* Scripts: `src/s0_feasibility.py` (main), `src/viewshed.py`, `src/test_viewshed.py`, `src/s0_restore_plan.py`, `src/s0_write_feasibility_md.py`, `src/hpwren_archive.py`, `src/hpwren_common.py`.
* Outputs: `outputs/feasibility_table.csv` (fire x camera), `outputs/feasibility_pairs.csv` (fire x site), `outputs/feasibility_spotcheck.csv`, `outputs/feasibility_archive.json`, `outputs/feasibility_summary.json`, `outputs/feasibility_daily_growth.csv`, `outputs/restore_plan_bobcat_wilson.csv`.
* Gitignored: `cache/dem/` (skadi tiles), `cache/feasibility/*.npz` (cell-level visibility), `cache/feasibility_quicklooks/*.png`, `cache/http/` (HPWREN responses).

Reproduce: `python3 -I src/test_viewshed.py && python3 -I src/s0_feasibility.py && python3 -I src/s0_restore_plan.py && python3 -I src/s0_write_feasibility_md.py`.

## Independent audit (second agent, own code)

Scripts: `src/audit_s0_independent.py` (geometry, GOFER time handling) and `src/audit_s0_archive_probe.py` (archive). Neither imports `s0_feasibility.py`, `viewshed.py` or `hpwren_common.py`. Outputs: `outputs/audit_s0_independent.json`, `outputs/audit_s0_archive_probe.json`. Credits: HPWREN (hpwren.ucsd.edu), UC San Diego; GOFER v0.2 (doi:10.5281/zenodo.14642378); AWS skadi DEM.

**Method.** For each pair, 2500 random points were drawn uniformly by area inside the final GOFER-Combined perimeter, read directly from `GOFERC_fireProg.shp` (seed 20261111). The script draws a straight camera-to-target profile every 15 m on a separately written `.hgt` reader with bilinear interpolation. It applies curvature with k = 0.13, and a target is visible if its elevation angle is at least the maximum angle of the profile up to d - 30 m. The FOV test uses the geodesic azimuth against the sites.js azimuth +- HFOV/2. Distances are geodesic, to the perimeter boundary densified every 30 m.

| check | original gate | audit | agree? |
|---|---|---|---|
| (a) site coords in sites.js: wilson / chino / ihvy | 34.22451,-118.05867 / 33.91384,-117.73829 / 38.45651,-122.89894 | identical (re-parsed) | yes |
| (b) site to perimeter: wilson-Bobcat / chino-Bobcat / ihvy-Kincade / ihvy-Glass | 0.27 / 34.14 / 14.15 / 20.01 km | 0.27 / 34.14 / 14.15 / 20.01 km | yes |
| (c) wilson-e-mobo-c in-FOV visible, ground (+20 m) | 7.69% (11.06%) | 7.00% [95% CI 6.0-8.0] (10.64%) | yes, within 0.7 pp |
| (c) chino-n-mobo-c in-FOV visible, ground (+20 m) | 7.74% (10.71%) | 7.36% [6.3-8.4] (10.48%) | yes, within 0.4 pp |
| (c) ihvy-n-mobo-c / Kincade, ground | 4.84% | 4.40% [3.6-5.2] | yes |
| (c) ihvy-e-mobo-c / Glass, ground | 4.03% | 4.04% [3.3-4.8] | yes |
| (c) wilson site any direction / wilson n+e union, ground | 11.09% / 10.83% | 10.56% [9.4-11.8] / 10.44% | yes |
| (d) bearing to burn centroid vs camera view (az +- 45) | - | wilson-e 45.6 deg (at the FOV edge; 54% of the burn is in FOV), chino-n 339.5 (whole burn 320-356 in FOV), ihvy-n/Kincade 24.6, ihvy-e/Glass 72.4 | consistent |
| fires with an HPWREN sites.js site within 60 km | 6 of 28 | 6 of 28 (same sites) | yes |

The audit is about 0.4-0.7 pp lower than the polar sweep on the three cases where they differ. No single fixed camera reaches 10% at ground level, and all the 95% upper bounds are at or below 8.4%. **The geometric FAIL is confirmed.** The audit draws on the same rounded sites.js coordinates and the same DEM, so it does not test those inputs.

**(e) Archive.** All requests were sequential, 1.5 s apart, with a generic User-Agent, and cached in `cache/audit_http/`.
* `wilson-e-mobo-c/2020/20200909/20200909_wilson-e-mobo-c_Q2.txt` returned **403**.
* A HEAD on `.../20200909/Q2.mp4` returned **200**, with `x-amz-storage-class: DEEP_ARCHIVE` and 49,529,516 bytes. This is the top-ranked restore block, and the original gate had not probed it.
* Positive control on the same camera and the same URL templates: the 2026-11-10 Q5 list returned 200 with 180 entries at a median gap of 60 s. One JPEG from it (`MTA/wilson-e-mobo-c/large/20261110/Q5/1794346255.jpg`) returned 200. It is a real JPEG (FF D8 FF magic), 3072 x 2048 px. The filename epoch is 13:30:55 PST, the EXIF time is 21:30:56 (UTC) and Last-Modified is 21:31:03 GMT.

So the URL scheme is right. The 2020 403s are not caused by a wrong path. **The archive FAIL is confirmed**: no 2019-2021 imagery can be downloaded, only DEEP_ARCHIVE MP4 objects exist, and HPWREN's help FAQ says "after 90 days, images are deleted and the corresponding 3h videos are archived in S3 Glacier". Whether a restored MP4 holds 1 frame per minute is still unverified. 49.5 MB per 3 h block is consistent with about 180 frames, but that is not proof.

**(f) GOFER time handling.** `tUTC` is the end of the hour. `tLocal - tUTC` = -7 h for every row of Bobcat, Kincade and Glass, which matches America/Los_Angeles (PDT) at all times. First and last times match the table above. The peak Pacific growth day matches the gate for Bobcat (2020-09-18, 165.4 km2) and Kincade (2019-10-27, 185.4 km2). For **Glass the peak day depends on convention**: assigning each hour by its midpoint (the gate's convention) gives 2020-09-27 (149.2 km2), while assigning it by its end time gives 2020-09-28 (179.6 km2). The 09-28 midpoint total is 143.9 km2. Only 2020-09-27 Q7 was probed for ihvy/Glass. This does not change the verdict, because ihvy fails geometrically at 4%.

**(g) Statements in this file.** The numbers above and the restore-plan figures were reproduced or traced to outputs. Peak-day growth visible from wilson-e totals 1.4 km2 of 165 km2, and the centroid of the 09-18 growth lies north of the fire centroid, which supports "mostly northward, almost none visible". Two limitations were not stated before:
1. `sites.js` and `calibration.js` describe the **2026** network. A camera's position and pointing in 2019-2021 may differ. Current calibration yaw is within 2.5 deg of nominal for these cameras, and ihvy has a pitch of about -8 deg. Any site removed since 2021 is not in the 60 km search at all.
2. FEASIBILITY.md is regenerated by `src/s0_write_feasibility_md.py`. A rerun would drop this section, so it must be re-appended.

**Audit verdict:** gate_pass = false confirmed, and geometric_pass = false confirmed. No corrections to the original numbers were needed.
