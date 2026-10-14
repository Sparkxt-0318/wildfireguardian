# Korean observation availability audit

Checked on **2026-10-12 (Korea Standard Time)** against the 15 Korean events in `data/environment/events.json`. The accompanying JSON gives one record for every event, source identifiers, required FARSITE layers, and NASA granule URLs. This is an availability audit; no Korean model evaluation or satellite-granule download was run.

The cached Korean arrival rasters are retrospective reconstructions. The publisher's deposit contains derived rasters and results but excludes raw detections and Korean final perimeters. Its README explicitly distinguishes these products from independent spread predictions. The accompanying paper describes final Korean damage perimeters and internal cross-validation, and reports no aerial or field arrival-time reference for the Korean application. These statements apply to this publication's data, rather than proving that no other Korean observations exist. [Publisher article](https://www.mdpi.com/2072-4292/18/19/3321), [publisher deposit](https://zenodo.org/records/21788344).

**A separate observation-derived satellite reference is available in principle for all 15 events.** Public NASA LAADS listings were checked directly: the MODIS MCD64A1 Collection 6.1 `h28v05` granules exist for every month touched by these events. This tile covers every cached Korean rectangle. These are monthly files with an estimated burn **day**, at a nominal 500 m reporting resolution. Their values do not supply minute-accurate perimeters. Existence of a covering file does not establish that the particular fire was detected or that every rectangle cell has usable quality. No such pixel-level claim is made here. [NASA product description](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/MCD64A1), [NASA Collection 6.1 user guide](https://www.earthdata.nasa.gov/s3fs-public/2025-04/MCD64_User_Guide_V61.pdf).

For a future satellite-reference evaluation, retain the burn-date uncertainty, land/valid-data QA flags, shortened mapping period, and first/last reliable mapping days. An unmapped pixel remains unknown. The relevant quantity is satellite-mapped cumulative burn membership at daily endpoints. Resampling the product to 375 m would not improve its native information. A six-hour endpoint cannot be established from an ordinal burn day without an additional timing assumption. MODIS combines reflectance and MODIS active-fire observations; this differs from the VIIRS/Himawari inputs listed for the cached Korean reconstruction, but remains an algorithm-derived satellite reference rather than field truth.

| Local event | Locality | Ignition date (KST) | KFS situation-map record | Covering MODIS files verified | Dated aerial/field progression verified | Current M548–FARSITE eligibility |
|---|---|---|---:|---|---|---|
| KFS_01 | Uiseong | 2025-03-22 | 359264 | March 2025 | No | Excluded |
| KFS_02 | Uljin | 2022-03-04 | 108124 | March 2022 | No | Excluded |
| KFS_03 | Gangneung | 2022-03-05 | 108684 | March 2022 | No | Excluded |
| KFS_04 | Sancheong | 2025-03-21 | 358944 | March 2025 | No | Excluded |
| KFS_05 | Hongseong | 2023-04-02 | 190204 | April 2023 | No | Excluded |
| KFS_06 | Ulju | 2025-03-22 | 359324 | March 2025 | No | Excluded |
| KFS_07 | Geumsan | 2023-04-02 | 190384 | April 2023 | No | Excluded |
| KFS_09 | Yanggu | 2022-04-10 | 123704 | April 2022 | No | Excluded |
| KFS_11 | Miryang | 2022-05-31 | 136224 | May 2022, June 2022 | No | Excluded |
| KFS_12 | Yeongdeok | 2022-02-15 | 103884 | February 2022 | No | Excluded |
| KFS_13 | Buk-gu | 2025-04-28 | 376804 | April 2025 | No | Excluded |
| KFS_14 | Uljin | 2022-05-28 | 135784 | May 2022 | No | Excluded |
| KFS_15 | Gunwi | 2022-04-10 | 123364 | April 2022 | No | Excluded |
| KFS_16 | Suncheon | 2023-04-03 | 190849 | April 2023 | No | Excluded |
| KFS_17 | Hapcheon | 2023-03-08 | 178624 | March 2023 | No | Excluded |

The KFS identifiers above are copied from the archived `results/kr_events_21.csv`; they identify the publication's source situation-map records, and are not direct download URLs. “No” in the progression column means **not verified or acquired by this audit**. The official KFS portal exposes incident timing, location, status, situation maps, and statistics; no publicly downloadable time-indexed, full-coverage progression vector archive was verified there. The public-data API describes occurrence and suppression statistics, which cannot supply per-cell cumulative burn labels. [KFS National Forestfire Information System](https://fd.forest.go.kr/), [KFS occurrence statistics API metadata](https://www.data.go.kr/catalog/3070842/openapi.json).

NASA FIRMS also distributes real active-fire detections, and JAXA P-Tree provides the Himawari wildfire product. Their existence is relevant to observation availability, but a hotspot at an overpass is not cumulative burned occupancy. No detection does not establish an unburned negative without an appropriate observation/quality model. VIIRS/Himawari detections were also used in the reconstruction that supplied training labels. They must not be substituted into the perimeter benchmark and called independent hourly burned-area truth. Historic downloads can require provider registration or Earthdata authorization; none was supplied or entered during this audit. [NASA FIRMS active-fire archive](https://firms.modaps.eosdis.nasa.gov/content/active_fire/), [JAXA Himawari Monitor](https://www.eorc.jaxa.jp/ptree/).

Each Korean region has the three required terrain rasters, but **all five physical fuel/canopy rasters required by the current FARSITE adapter are absent**: fire behavior fuel model, canopy cover, canopy height, canopy base height, and canopy bulk density. The adapter rejects non-U.S. events for this reason. Ordinary vegetation categories cannot be silently converted into calibrated FARSITE fuel models. A published Korean study constructs nine fuel models and fits spread adjustments to observed satellite perimeters; its raw data are available **on request**, and no reusable full-coverage raster download was verified. No request was sent to its authors. [Korean fuel-model study](https://www.mdpi.com/2072-4292/17/16/2824).

Consequently, all 15 Korean events are excluded from the **current M548–FARSITE dated-perimeter comparison**, with both reasons recorded: no acquired eligible progression perimeter series and no cached physical FARSITE fuel/canopy layers. This exclusion does not erase the verified availability of coarser observation-derived MODIS references. Their use would require a separate reference adapter, pixel-quality inspection, daily endpoint conventions, and adequate Korean FARSITE fuels.
