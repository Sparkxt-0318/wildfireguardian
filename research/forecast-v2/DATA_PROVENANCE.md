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

## Small source-archive supplements

The logistic comparator uses the aligned 375m elevation raster for all 44
events to calculate signed uphill/downhill slope along the nearest-fire
direction. These 44 files total 1,542,666 bytes. The separate
`BASELINE_TERRAIN_MANIFEST.json` has SHA-256
`0e8546d9d4d3bd19ab835e10c3951ef5762ba35eafd25e36e0c369211ad01aa2`.
No fitted-kernel input or original extraction-manifest byte changed. Elevation
inherits the source-specific rights limitation above; its raster tags identify
Copernicus DEM GLO-30 DSM, including vegetation and buildings, rather than
surveyed bare-earth ground elevation.

All 78 unique raster files referenced by the 30 historical deterministic
FARSITE scenarios were recovered separately into `farsite-inputs/`. Each
freshly extracted file matches the SHA-256 in the original scenario report.
The aggregate size is 74,923,354 bytes; `FARSITE_INPUTS_EXTRACTION.json` records
every source member and identity. `scripts/extract_supplements.py` rehashes the
entire source archive before repeating this recovery. `FARSITE_IDENTITIES.json`
also verifies all 30 exact initial and endpoint arrays against the current
consecutive-survey source arrays, as well as grids, cutoffs, seeds and sampling
configuration. This identity audit does not inspect or recompute forecast
quality. Historical M548 probabilities are not admitted into the new study.

The same archive contains the native observed-clock FARSITE source, supplied
patches, build manifest, licence, clock probe and executable. The task-local
`native-farsite/EXTRACTION_MANIFEST.json` pins 256 non-Git files, 6,532,653 bytes.
The recovered `src/TestFARSITE` SHA-256 is
`125a7df4ff1723ce9123f7b650fdbc69e285d9beaceea5523e11c5a3b5b9cfa3`,
matching the supplied observed-build manifest. This establishes recovered
binary identity; execution, reproducible rebuild and physical truth remain
separate gates. The bundled licence preserves the US government work notice,
attribution and restrictions stated in that source, rather than inventing an
MIT licence for FARSITE.

`scripts/audit_geometry.py` found 55 topologically invalid original or projected
records across the 29 US fires. Every affected raw rasterization reproduced its
stored cumulative arrays. A separately evaluated projected `make_valid`
polygonal-only sensitivity changed zero cell-survey entries at 375m. The actual
producer performed no explicit repairs or skipped records. Rasterio's structural
geometry check is weaker than topological validity; the supplied polygons can
therefore reach its rasterizer. This audit establishes stability under that
specific finite-grid repair, without establishing a physical polygon or complete
survey coverage. See the per-record reasons and hashes in `GEOMETRY_AUDIT.json`
and the [Rasterio rasterization contract](https://rasterio.readthedocs.io/en/stable/api/rasterio.features.html).
