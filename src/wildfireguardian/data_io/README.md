# `data_io` — geospatial I/O and caching

**Status**: scaffold only.

**Purpose**: shield the rest of the codebase from the messy details of
reading and writing the project's geospatial inputs and outputs.

**Inputs**: paths or URLs to GeoTIFF, NetCDF, shapefile, GeoJSON.

**Outputs**: in-memory arrays / GeoDataFrames in a canonical project CRS
(EPSG:5179 for Korea-wide work).

**Algorithmic basis**: thin wrappers over `rasterio`, `xarray`, and
`geopandas` with explicit, project-wide handling of CRS reprojection,
no-data masking, and a content-hash-keyed disk cache under
`data/cache/`.
