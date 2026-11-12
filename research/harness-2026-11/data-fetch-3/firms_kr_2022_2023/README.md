# NASA FIRMS country archives, Republic of Korea, 2022 and 2023 (keyless)

These are the same product and format as `data-fetch/small/firms/*_2025_Republic_of_Korea.csv`. Columns: latitude, longitude, bright_ti4/brightness, scan, track, acq_date, acq_time (UTC HHMM), satellite, instrument, confidence, version, bright_ti5/bright_t31, frp, daynight, type. Fetched 2026-11-12:

    for y in 2022 2023; do for s in viirs-snpp viirs-jpss1 modis; do
      curl -fsS -A curl/8 -O "https://firms.modaps.eosdis.nasa.gov/data/country/$s/$y/${s}_${y}_Republic_of_Korea.csv"; done; done

FIRMS updates these archives, so a re-fetch can change the sha256. NOAA-21 is not in the country archive. Licence: NASA FIRMS open data; cite NASA FIRMS / LANCE.

| File | Rows | sha256 |
|---|---|---|
| viirs-snpp_2022_Republic_of_Korea.csv | 9,849 | `11189061…173f` |
| viirs-jpss1_2022_Republic_of_Korea.csv | 10,274 | `d4028494…a074` |
| modis_2022_Republic_of_Korea.csv | 1,165 | `6a830c89…2335` |
| viirs-snpp_2023_Republic_of_Korea.csv | 8,270 | `afca6bf5…68b6` |
| viirs-jpss1_2023_Republic_of_Korea.csv | 8,184 | `fdf0c330…53a7` |
| modis_2023_Republic_of_Korea.csv | 1,155 | `0d8a19fc…dc6b` |

## Detections inside each event's `bounds_wgs84` (forecast/data/environment/events.json), by date window

| Event | Window (acq_date) | VIIRS S-NPP | VIIRS NOAA-20 | MODIS |
|---|---|---|---|---|
| KFS_02 Uljin | 2022-03-03 to 03-14 | 1,151 (03-04 04:09 to 03-12 05:00) | 996 (03-04 03:19 to 03-12 04:09) | 195 |
| KFS_11 Miryang | 2022-05-30 to 06-04 | 45 (05-31 03:18 to 06-02 16:42) | 23 | 4 |
| KFS_05 Hongseong | 2023-04-01 to 04-05 | 83 (04-02 04:24 to 04-03 04:05) | 90 | 18 |

The rectangle is the event grid's WGS84 bounds only, with no buffer. Detections at the edge of the scan footprint can fall outside it.

## Arrival-time rasters for KFS_02, KFS_05 and KFS_11

These are in the Choi et al. 2026 Zenodo archive (10.5281/zenodo.21788344): `python3 data-fetch/fetch.py get toa_kriging_choi2026 --dest DIR`, then unzip `wildfire_toa_dataset_and_code.zip`, then `rasters_kr/<id>_pswt_ok_toa.tif` (and `_std.tif`). `environment inventory` copies each byte for byte to `regions/<id>/arrival_time_hours.tif`.

| Event | toa sha256 | std sha256 |
|---|---|---|
| KFS_02 | `31e13697…3f51` | `40ccb9e6…df2335` |
| KFS_05 | `e1d53967…540f` | `5bc7184e…ff1df` |
| KFS_11 | `a67b5eec…bf16` | `a4229523…a3d` |
