# Data provenance and current-host input custody

All scientific inputs in this run were recovered from the owner's local
`/Users/jp/Downloads/wildfire 3 (1).zip`. The complete archive was freshly
stream-hashed, SHA-256
`b9e000e8661128416fe7561690f78b1955d5a32189ac71536c1cd4110cd5dd65`.
No external environmental raster or perimeter archive was downloaded for this
execution. The initial metadata-only directories were not used as raster data.

The task-local extraction is outside Git at
`work/data/forecast-v2/`. Its `EXTRACTION_MANIFEST.json` records each archive
member, its extracted byte count, CRC and SHA-256. Zip CRC checks completed while
reading; the archive hash and nested NIROPS archive hash also matched their
pinned source identities. This manifest includes all required aligned source
channels, weather completeness metadata, grids, arrival/SD rasters and fuel
maps. Raw scientific inputs are not duplicated into this branch.

| Input | Primary source | Rights record | Identity |
|---|---|---|---|
| NIROPS 2020 to 2024 survey archive | Magstadt et al., Mendeley DOI 10.17632/95rj5d379g.1 | CC BY 4.0 in publisher snapshot and supplied provenance | SHA-256 b19fb16ce2792d9a9c01f1768d09962566b0f3cada8d1f23a9851ab3fce75615 |
| Arrival-time reconstructions and kriging SD | Choi et al., Zenodo DOI 10.5281/zenodo.21788344 | CC BY 4.0 data, MIT source code in supplied release metadata | SHA-256 612edf5f879d8fe874ae20e9d49d0be5de477e6f8c3101b434f1642d5b19ebad for nested archive |
| Aligned environmental covariates | Source-supplied event tree, per-layer source metadata in the recovered archive | Upstream rights are source-specific; this task did not independently re-audit every provider licence | Every extracted file is pinned in the extraction manifest |
| Existing observed c651/FARSITE predictions | Source-supplied frozen observed-evaluation runs | Reused research outputs, retained with per-case original provenance | Every extracted output is pinned in historical_observed/MANIFEST.json |

The existing predictions are reference material. They are not automatically
admitted as matching current comparisons. Checkpoint, seed, block size, cutoff,
weather, grid, support, reference masks and exact ordered scored cells must match
before reuse. A historical model score never becomes a new independently
measured score merely by copying it.

The year/fire split is frozen separately in SPLIT.json. All target data remain
in their original evidence class: NIROPS cumulative mapped extent, retrospective
kriging reconstruction, or deterministic FARSITE scenario. NIROPS outside-union
cells inside the fixed rectangle are not-mapped reference negatives, with no
complete survey coverage footprint. Reconstruction SD missingness receives zero
training weight rather than the confidence of an exact label.

FBFM40 maps are available for the US event trees. Supported standard codes use
`FlameResidenceTime.from_fbfm40`; missing or unsupported codes retain the explicit
six-hour fallback source scenario. That fallback is not a physical assertion
about nonburnable terrain or a measured residence time. Point duration combined
with hourly synchronous updates and midpoint ignition is a coarse numerical
approximation; its limitations must remain visible in burnout comparisons.

All producers, selections, subset and full-fit phases, host information and
failed commands are recorded with source and input identities in executions/.
No new checkpoint changes the selected c651 integration default.
