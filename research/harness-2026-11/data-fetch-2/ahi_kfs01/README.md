# Himawari-9 AHI band 7 / band 14 over the KFS_01 grid, 2025-03-24 18:00 to 2025-03-25 18:00 UTC (keyless)

**Source:** NOAA Open Data Dissemination, public AWS bucket `noaa-himawari9`, `AHI-L1b-Japan` (no account or key; JMA data
redistributed by NOAA, https://registry.opendata.aws/noaa-himawari/). The Japan-area product covers Korea with four scans per 10 minutes
(JP01–JP04, nominal 2.5-min cadence) at 2 km for bands 7 (3.9 µm) and 14 (11.2 µm).
**Made with** `research/harness-2026-11/data-fetch/fetch_ahi_kfs01.py` (satpy 0.54 `ahi_hsd` reader, calibrated brightness temperature):
`fetch_ahi_kfs01.py --start 2025-03-24T18:00 --end 2025-03-25T18:00 --work DIR --out X.npz --csv X.csv.gz`.
The run took about 11 min and downloaded about 1 GB of raw files, streamed and deleted as it went.

| File | sha256 | Content |
|---|---|---|
| `kfs01_ahi_20250324T18_20250325T18.npz` | `63dfc2b6…6712` | `scan_start_utc`/`scan_end_utc`/`scan_id`/`slot` [576]; `lat`, `lon`, `x5179`, `y5179`, `line`, `column` [448]; `b07_K`, `b14_K`, `b07_minus_b14_K` [576 × 448]; `missing` (empty) |
| `kfs01_ahi_20250324T18_20250325T18.csv.gz` | `bb8aca25…7ff1` | Long table: scan_start_utc, scan_id, lat, lon, b07_K, b07_minus_b14_K (258,048 rows) |

- **Coverage:** 576 of 576 scans, none missing. There are 448 AHI pixels whose centres fall inside the KFS_01 export grid (EPSG:5179 x 1085250–1174125,
  y 1815750–1845375). No NaN values.
- **Times:** `scan_start_utc` is the nominal start of each 2.5-min Japan-area scan. The actual line time over Korea is within that scan.
- **Saturation:** band 7 saturates near **400.1 K** in 174 of 576 scans, spanning 2025-03-25 05:50–14:35 UTC. Treat B07 ≥ 399.9 K as saturated (a lower bound).
- **Geolocation:** pixel centres are the nominal AHI fixed grid (about 2 km at nadir, coarser at 36° N). There is no parallax or terrain correction.
- No hotspot thresholding has been applied; that is left to the consumers.
