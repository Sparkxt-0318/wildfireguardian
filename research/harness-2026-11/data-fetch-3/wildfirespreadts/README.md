# WildfireSpreadTS (Gerard et al. 2023): per-fire header metadata, with no bulk download

Source: Zenodo record 8006177 (CC-BY-4.0), `WildfireSpreadTS.zip`, 48,359,369,821 bytes (md5 `dc1a04e63ccc70037b277d585b8fe761`). It is one zip laid out as `YEAR/fire_<GlobFire id>/YYYY-MM-DD.tif`, with 14,218 members (49.3 GB uncompressed). Zenodo honours HTTP Range, so `../remote_zip.py` can list or extract single fires. Use `--jobs 4` or fewer, because Zenodo answered 429 at 12 parallel requests.

`wsts_fire_headers.csv` has one row for each of the 607 fires: year, fire folder, number of days, first and last day, width/height, band count (23), the bounding box (x0, y0, x1, y1) and the EPSG code (32610 for all fires). It was made by `wsts_headers.py`. For each fire, the script inflates only the first ~64 KB of the first day's GeoTIFF and parses the TIFF and GeoTIFF tags. No imagery was downloaded.

| Year | Fires | Days | Compressed |
|---|---|---|---|
| 2018 | 176 | 3,773 | 13.61 GB |
| 2019 | 74 | 1,425 | 5.19 GB |
| 2020 | 201 | 4,292 | 15.52 GB |
| 2021 | 156 | 4,117 | 14.03 GB |

Per fire, compressed: min 29 MB, median 70 MB, max 291 MB. One day is a median 3.5 MB. Bands, from `WildfireSpreadTS_Documentation.pdf`, in order:
- 1–3: VIIRS M11, I2, I1
- 4–5: NDVI, EVI2
- 6–12: gridMET precipitation, wind speed, wind direction, Tmin, Tmax, ERC, specific humidity
- 13–15: slope, aspect, elevation
- 16: PDSI
- 17: MODIS land cover
- 18–22: GFS forecast precipitation, wind speed, wind direction, temperature, specific humidity
- 23: active fire (VNP14IMG, 24 h aggregation, medium and high confidence; non-detections are NaN)

The dataset prescribes no label; the baselines binarise the next day's active fire.
