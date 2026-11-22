# DATA: inputs of kcf-radiation and where they came from

## The data folder named in the brief

The brief points to a folder "wildfire 3 (1)" on this computer (the same as "wildfire 3" in the Google Drive folder
"wildfireguardian"). **It could not be found from where this study ran.** A search of the home folder (to depth 6,
outside `~/Library`), Spotlight, `~/Library/CloudStorage` (only OneDrive is mounted; Google Drive is not) and
`~/Downloads` found no folder or archive of that name. The repository records an archive `wildfire 3 (1).zip`
(SHA-256 `b9e000e8…`, `research/forecast-v2/DATA_PROVENANCE.md`) that is no longer in `~/Downloads`. No
`DATA_INDEX.md` was found. No key was needed or read: every source below is either in the repository or public.

What was used instead:

| input | source | used for |
|---|---|---|
| Reconstructed arrival time, land cover, canopy height, slope, hourly ECMWF IFS wind, RH and temperature at 375 m for KFS_01 (Uiseong 2025, covering both 2025 routing regions), KFS_02 (Uljin 2022), KFS_05 (Hongseong 2023), KFS_11 (Miryang 2022) | `data/environment/regions/<KFS id>/` inside the owner-local archive `~/Downloads/wildfire (2).zip` (an earlier release of the same forecast workspace, files dated 2026-10-07..10; SHA-256 of each file used is in `data/env_inputs.json`). Extracted to scratch, not committed. | fuel class, canopy, wind, humidity per cell and hour; ROS of the reconstructed fires |
| Finals forecast packets: 15 packets, 5 regions (`uiseong_andong_2025`, `yeongdeok_2025`, `uljin_2022`, `hongseong_2023`, `miryang_2022`), 1 h horizon | `data/routing/latest_inputs_try02/packets/` (frozen routing inputs, `python tools/fetch_routing_inputs.py`) | leave-by panel B |
| Gyeongbuk 25 March 2025 replay rasters, 13 issue hours 12:00-24:00 KST, MEASURED arm, 8 h horizon | built by `product/wfg-roadlayer/examples/build_example_raster.py --issue <hour>` (research/kcf-replay, no new science) | leave-by panel A |
| Road graphs | `data/routing/graphs/<region>/graph.json` (SHA-256 in `data/routing/INPUT_FILES.json`) | road pieces |
| Villages, facilities, shelters | `planner/public/data/regions/<region>/places.geojson` | origins and shelters |
| VIIRS (S-NPP, NOAA-20 = "viirs-jpss1") and MODIS active fires with FRP, Republic of Korea, 2022, 2023 | NASA FIRMS public yearly country files, `https://firms.modaps.eosdis.nasa.gov/data/country/<sensor>/<year>/<sensor>_<year>_Republic_of_Korea.csv`, downloaded 2026-11-19 without a key (SHA-256 in `data/frp_inputs.json`) | FRP cross-check |
| Same, 2025 | `research/harness-2026-11/data-fetch/small/firms/` (in git) | FRP cross-check |
| FDS C064 grass-fire radiometry | `research/kcf-heat/data/b2_fds_compare.json` (in git) | check 2 |
| Local FDS runs (plane-layer verification, propane strip burner) | `/Users/jp/Documents/Codex/2026-11-16/work-autonomously-on-wildfireguardian-s-flame/outputs/fds_study/` (owner-local, read only) | check 2 |

The environment rasters are indicators, not measured fuel: land cover is a 2019 100 m classification, canopy height a
2019 GEDI-Landsat model, wind an ~9 km forecast-model field resampled to 375 m. METHOD.md section 9 states what this
does to the answers.

## A7 rerun (2026-11-20)

The folder "wildfire 3 (1)" was tried again and still could not be reached (no computer attached; the Drive connector in
the session has no file-read tool; a Drive file link supplied later could not be opened either). Used: the 15 packets and
road graphs from the public release (`tools/fetch_routing_inputs.py`, hash verified), the 13 replay rasters rebuilt with
`build_example_raster.py` (03:00 UTC byte-identical to the committed one), and fuel group, wind and RH per road cell from
`data/panels/road_cells_panel_{A,B}.csv.gz`. Air temperature is recovered per cell from the recorded d*. The environment
rasters themselves were not available. No key was read.
