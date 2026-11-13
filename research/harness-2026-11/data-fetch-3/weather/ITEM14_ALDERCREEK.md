# Item 14: AlderCreek weather, rebuild vs owner archive

- **Event:** MT-BDF-006269_AlderCreek.
- **Rebuild:** night-1 weather step, envpilot workspace, finished 2026-11-13T00:15:31Z.
- **Compared:** the three channels the model reads, over every cell and every band (2,139 hours, 2021-07-10T00Z onward) of the 375 m rasters, plus the node-index raster and the band/time table:

| file | owner sha256[:16] | rebuild sha256[:16] |
|---|---|---|
| temperature_2m_375m.tif | 893cd2ec4ab4307d | 893cd2ec4ab4307d |
| wind_eastward_10m_375m.tif | 9a6f883dd9e60497 | 9a6f883dd9e60497 |
| wind_northward_10m_375m.tif | 5fe739b87fe04eda | 5fe739b87fe04eda |
| ecmwf_ifs_node_index_375m.tif | 541a8fbca436671e | 541a8fbca436671e |
| ecmwf_ifs_bands.csv | c3152cf0e1020115 | c3152cf0e1020115 |

- **Result:** all five files are byte-identical, so |Δ| = 0 for every cell and hour.
  - Median |Δ| = 0 K / 0 m/s; p95 |Δ| = 0 K / 0 m/s.
  - Thresholds were median ≤ 1 K or 1 m/s, p95 ≤ 3 K or 3 m/s.
  - **PASS.**
- **Caveat:** this shows that the slim rebuild reproduces the owner's values for the three model-read channels and their time axis. It says nothing about the channels the slim rebuild does not produce: RH, precipitation, ERA5 BLH and the rest.
