# Data provenance (track 1B)

No downloaded archive is committed. Everything below lives outside the worktree under `/home/user/wfg-shared/forecast-data/` on the execution host.

| Item | Source | Licence | SHA-256 | Size | Use |
|---|---|---|---|---|---|
| `NIROPS_2020_2024_R1_R6.zip` | Magstadt et al. (2026), Mendeley Data 10.17632/95rj5d379g.1, `https://data.mendeley.com/public-files/datasets/95rj5d379g/files/e9caf5e3-dcd1-4633-98a9-7f857d110b29/file_downloaded` | CC BY 4.0 | `b19fb16ce2792d9a9c01f1768d09962566b0f3cada8d1f23a9851ab3fce75615` (equals the value pinned in `forecast/wildfire/observed_data.py`) | 1,387,524,228 B | survey perimeters for training (2020 to 2022 fires) and held-out scoring (2024 fires) |
| `NIROPS_2020_2024_R1_R6.shp` (unpacked member) | same archive | CC BY 4.0 | `a14f391ae0e2f75a1d218aed91ad03eb35bfc311a4909021f9fe1f6310fdf09b` (equals the member hash recorded in the repository's NIROPS catalog provenance) | 2,067,807,444 B | read by `scripts/prepare_perimeters.py` |
| `wildfire_toa_dataset_and_code.zip` | Choi et al. (2026), Zenodo 10.5281/zenodo.21788344, `https://zenodo.org/api/records/21788344/files/wildfire_toa_dataset_and_code.zip/content` | CC BY 4.0 (data), MIT (code) | `612edf5f879d8fe874ae20e9d49d0be5de477e6f8c3101b434f1642d5b19ebad` (equals `forecast/data/source_manifest.json`) | 1,522,020 B | 375 m grids, arrival-time and kriging-SD rasters (mixed regime labels), event tables for `SPLIT.json` |
| `README.md` of the Zenodo record | same record | CC BY 4.0 | `7c0c3adbbc16fce210174e249934350e89effe07d6cfa2cb26d02bc8723c3fb2` (equals the manifest) | 6,938 B | documentation only |

Derived files (outside git): `perimeters/<event>/{perimeters.geojson, states.npz}` and `perimeters/PERIMETER_MANIFEST.json` from `scripts/prepare_perimeters.py`; the manifest records the shapefile hash, the script hash and the hash of every derived file. The manifest's own hash is recorded in `RESULTS.json`.

## Environmental inputs

The private forecast data tree (`events.json` plus aligned rasters, the `--data-root` of the released workflows) is not in the repository. Its path, size and the SHA-256 of its manifest are recorded in `RESULTS.json` and in every run record (`data_manifest_sha256`) once it is attached.

A public rebuild of the six c651 source channels was attempted first with `scripts/rebuild_environment.py`, from the sources named in `forecast/wildfire/environment.py`. The weather stage never completed: the Open-Meteo archive answered "Daily API request limit exceeded" for the shared egress address. The client waited politely and did not try to get around the limit. On the orchestrator's instruction (the human will attach the real tree) the rebuild was stopped. The partial static layers were deleted, and no rebuilt raster is used or cited anywhere. The script stays in the repository as a record of the attempt.

## FIXTURE root

`scripts/make_fixture.py` writes a synthetic data root (real grids, windows and Zenodo label rasters; synthetic weather, slope, tree cover and biome values) used only to exercise the pipeline. Any number computed on it is labelled FIXTURE and is not evidence.
