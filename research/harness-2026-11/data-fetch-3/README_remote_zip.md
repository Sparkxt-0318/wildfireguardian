# remote_zip.py: reading the owner archive without downloading it

`remote_zip.py` reads a large remote zip through HTTP Range requests. It uses only the standard library.

- `list` reads the central directory.
- `sha256` streams the whole file through a hash without writing it.
- `extract` fetches only the members whose names match a glob and checks each one's CRC-32.

The owner archive ("wildfire 3.zip", 11,447,285,600 bytes) was checked on 2026-11-12. Its sha256 is `b9e000e8661128416fe7561690f78b1955d5a32189ac71536c1cd4110cd5dd65`, the value recorded in `research/forecast-v2/DATA_PROVENANCE.md`.

**Rules:**
- The archive link is private to the team. It is passed only with `--url` or the `REMOTE_ZIP_URL` environment variable, and is never written into this repository: not in a script, manifest, README, log, PR or comment. Ask the data fetcher or the orchestrator for it.
- Extracted archive contents are not committed. Only derived statistics are, such as `archive_vs_rebuild/`.
- The member listing is not committed, because some members record the owner's local paths.
- Read only what a stream has asked for. Do not extract `.git/`, `.venv/` or `__MACOSX/`.

    export REMOTE_ZIP_URL='<link, from a message>'
    python3 remote_zip.py extract --jobs 12 --dest ARCH 'wildfire/data/environment/regions/MT-BDF-006269_AlderCreek/*'

Throughput here was about 10 small members per second with 12 jobs. The full `wildfire/data/environment/` tree (6,339 files, 4.49 GB) took about 25 min. Checked against the archive's own `file_manifest.json`, 5,676 files match by sha256. Two kinds of exception:
- `.DS_Store` differs.
- 8 listed scripts and readmes are absent from the zip.

## archive_vs_rebuild/

`cmp_region.py ARCHIVE_REGION REBUILD_REGION OUT.csv` compares every GeoTIFF of one region, cell by cell. It writes derived statistics only.

`AlderCreek_archive_vs_rebuild.csv` is the S-D9 A1 item-14 static-channel check. It compares MT-BDF-006269_AlderCreek in the archive against the rebuild made by `data-fetch/rebuild_env.sh` (repo `environment.py`, pinned venv). Of the 66 archive rasters:
- 13 have identical bytes;
- 22 have identical values but different encoding;
- 9 differ only by float rounding (max |Δ| < 1e-4);
- 22 are not rebuilt: the weather/ layers and GLAD canopy height 2019.

| Channel | Mask | Cells differing | Max abs Δ | Mean abs Δ | Median | p95 |
|---|---|---|---|---|---|---|
| slope_degrees | equal | 564 / 3796 | 5.7e-6° | 2.3e-7° | 0 | 1.9e-6° |
| tree_cover_percent | equal | 0 / 3796 | 0 | 0 | 0 | 0 |

So the earlier "differing" static layers differ in GeoTIFF encoding, not in values. The weather comparison (temperature_2m and the wind components) follows once the rebuilt AlderCreek weather exists.
