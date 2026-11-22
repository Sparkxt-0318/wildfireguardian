# S-D9 part-a training pool: non-weather checkpoint (12 Nov 2026)

This is the checkpoint for **all 490 incidents of `PART_A_ALLOWLIST_FINAL.csv` @ 7db3cc0e**: 490 built, 0 failed. It was built in Daniel's container between 13:24 and 14:50 UTC. Weather is a separate checkpoint after the 13 Nov 00:12 UTC Open-Meteo run.

## Commands

`run_parta.sh` is included here, with the scratchpad path replaced by `$SCRATCH`.
1. For each allowlist row, in file order: `python build_nirops_event.py <ID> --shp NIROPS_2020_2024_R1_R6.shp --allowlist PART_A_ALLOWLIST_FINAL.csv --workspace WS`. This is `data-fetch/build_nirops_event.py` on Main (v1, `where=` filter).
2. `python -m wildfire environment terrain` (rc=0, 611 s), then `python -m wildfire environment landcover` (rc=0, 2993 s), then `python -m wildfire biome` (rc=0, 86 s). These use the repo's own `forecast/wildfire` from Main 8d50f2e2.
3. NIROPS shapefile: `.shp` sha256 `a14f391a…09b`, from the Mendeley zip `b19fb16c…5615`.

## Files

- `BUILD_LOG.csv`: one row per allowlist row (its line number in the CSV). Columns:
  - status (all OK; no error text) and incident;
  - grid h×w, start and end (A1 rule);
  - survey times, records, intervals ≤ 48 h, growth intervals, final mapped cells;
  - the regions and perimeters directories;
  - the sha256 of states.npz and perimeters.geojson;
  - a check that survey_states equals the builder masks (all True).
- **Set equality holds.** The allowlist (490 unique) = `regions/*` = `perimeters/*` = events.json ids = PERIMETER_MANIFEST events. The workspace holds no other incident directory: `data/environment/{events.json, biome_*, raw/<490 allowlisted ids>, regions/<490>, sources/}` and `data/perimeters/{<490>, PERIMETER_MANIFEST.json}`.
- `events.json`: the 490 event records (grid, transform, bounds, A1 window).
- `PERIMETER_MANIFEST.json`: per incident, the record and time counts, intervals, mapped cells and output sha256s. It also gives the shapefile sha and the builder script sha.
- `perimeters/<id>/states.npz`: the label states pipeline.py reads (times and states), 2.1 MB in total. The `perimeters.geojson` files (1.0 GB) and the region rasters (95 MB) are **not committed**. Their sha256 values are in `OUTPUT_MANIFEST.json`, which lists every output file in the workspace (28,327 files).
- Every region has `terrain/slope_degrees_375m.tif`, `vegetation/tree_cover_percent_375m.tif` and `biome/biome_class_375m.tif`. In all 490, every arrival-valid cell has a biome value.

## Rebuild one incident (for spot checks)

    python3 research/harness-2026-11/data-fetch-3/nirops_access/build_nirops_event_v2.py <ID> \
      --shp NIROPS_2020_2024_R1_R6.shp --allowlist PART_A_ALLOWLIST_FINAL.csv --workspace WS

v2 reads by fid through `nirops_access.py`. It gives byte-identical arrival, grid, labels, perimeters.geojson and states.npz, which was checked on 3 incidents. Compare the results with `perimeters/<id>/states.npz` here and with `OUTPUT_MANIFEST.json`.

The reads are listed in `../ACCESS_LOG.md`.
