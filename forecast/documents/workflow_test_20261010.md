# Complete workflow verification — 2026-10-10

**Result: passed on CPU, with zero unresolved failures.** The final unit suite passed **1,448 tests** in **58.94 seconds**, with 272 dependency-deprecation warnings. Every one of the **38 registered commands** has successful actual execution evidence; the installed wheel also passed all command help checks outside the checkout.

The runtime was Python 3.12.13 and PyTorch 2.5.1. Data-producing commands ran in fresh artifact directories with cached sources and blocked network access. Existing experiment inputs and scientific records were preserved.

## Execution sequence and evidence

| Step | Executed scope | Result |
|---|---|---|
| 1. Environmental acquisition and integrity | All nine acquisition stages on cached FishCreek sources; enrichment, validation, previews and inventory; biome regeneration for all 44 events with 490,452 independently checked pixel centres | Passed; 5,434 prior scientific files byte-identical and 87 additional source/metadata files unchanged |
| 2. Reconstruct and export | All five retained Korean regions, 1,277 hourly snapshots, 1,292 BMP exports with masks, exact-value sidecars, and affine/geographic checks | Passed on an explicit offline bundle fixture; rebuilt arrays equal retained arrays |
| 3. Load real data | All 44 events, 741 encoded channels, 72 raw source channels; the first two hours of every full grid plus targeted invalid-soil probes | Passed categorical/native and continuous/raw parity, masks, timing and coordinates |
| 4. Prepare and manage caches | Season and weighted cell-hour preparation, resplit, contact and country subsets, original-cache recovery/relocation, idempotence and corruption rejection | Passed; original source/cache hashes retained |
| 5. Fit through the public API | Full original cache: 199,185 training / 49,900 validation / 61,965 test rows; 3 CPU epochs | Passed; epoch 3 selected by validation; test excluded from selection |
| 6. Reload and independently verify | All 486 input source hashes; reproduce normalization/category weights and all three partition prediction files | Passed; maximum absolute CPU difference 3.57627869e-07, below 1e-6; real-grid save/reload exact |
| 7. Exercise every model family | 47 controlled synthetic fits: legacy convolution, all single-kernel architectures/supports, mixed and neural mixtures, RF3/RF5, native API trainer | Passed finite gradients, actual parameter updates, masks, contracts, metrics and 47 fresh-interpreter checkpoint loads |
| 8. Search, finalize and resume | Single: 40; scheduled: 40; mixed: 43; multiscale: 46; precision: 46; portable: 46 candidates. Small real cohorts; portable: 512/256/256 train/validation/test rows and 2 initial / 4 finalist epochs | Passed fitting, finalization and reports; five resumes used zero optimizer steps or forest fits, with exact predictions and unchanged histories; all 23 source hashes verified |
| 9. Evaluate and report | Native 3/5/7/9 fits, common-cohort evaluation, 16 random forest candidate fits, kernel report, comprehensive portable report with 75 metrics and 75 figures, and three compatible legacy extensions | Passed; selection remains validation-only and fitted/prediction archives unchanged |
| 10. Predict flames and heat | Six CLI scenarios plus probability/heat/flame exports from the newly trained real checkpoint; reopened NPZ, CSV and image files | Passed half-open activity, endpoint versus interval-mean occupancy, NaNs, bounds, radiant units, coordinates, and dose = mean flux × seconds |
| 11. Execute notebooks | All 36 computation cells; API optional training enabled; fresh directories | Passed in plain Python with display-only fallback; stored notebooks unchanged |
| 12. Test installed distribution | Rebuilt wheel installed outside the checkout; all 21 job modules imported; real-data load/example; 38 command help checks; package bytes compared to current source | Passed 41 command/import checks; large artifact trees excluded; dependency check passed |

The two representative training and heat figures were visually inspected for readable titles, legends, axes, units and scientific-scope labels.

## Defects fixed during testing

1. `check-model --output PATH` was rejected by the outer dispatcher although its handler supports the option. Removed the command from the argument-free pre-parser. The actual command now writes a passed verification report to a fresh path. Two regression tests check option forwarding, paths with spaces, argument restoration and help safety.
2. `inventory-data` could not locate the exact historic acquisition source whose hash is recorded in the saved biome report. The retained later archive had a compatibility wrapper and therefore a different hash. Recovered the byte-exact original, verified SHA-256 `3fe0f225aabdc76a3ad92a8643015c2136e30867f5c0c0f5d82a8c17d526cc23`, and added an archive named by that hash. The existing archive and saved report remain unchanged. The matcher accepts only source bytes whose actual hash matches the record and rejects malformed digests or tampered archives; nine regression cases cover this. The actual data-inventory command subsequently selected the canonical archive and passed.

Only `wildfire/__main__.py` and `wildfire/environment.py` changed among the 23 maintained Python implementation files. Model definitions, training/evaluation calculations, and original input/checkpoint artifacts retain their pre-test source/content hashes.

## Interpretation and limits

These are functional, integrity and mathematical-consistency checks. The broad model/search sweeps use small or synthetic cohorts and short training; their smoke-report scores are not full-data performance estimates. The three-epoch full-real-data trial verifies execution and reload behavior, rather than reproducing the prior long benchmark. Exact infinite negative log likelihood for positive no-contact labels remains recorded; unavailable prediction/heat source support stays masked/NaN and retains bounds.

The loader audit rereads the first two hours of every event. The inventory verifies 5,434 scientific files by hash and retains 976,577 previous band checks; it does not newly reread all those bands. Live downloads, credential handling, endpoint availability/retries and network latency were not tested. CUDA and MPS were unavailable. Jupyter kernel/display rendering was not tested; notebook computation cells ran in plain Python with display-only substitutes.

The bundle fixture recovered region specifications from retained metadata and used actual arrival/uncertainty rasters. Missing historic MODIS/environment payloads remain absent and their placeholder legacy directories/manifests are explicitly marked as fixtures. The inventory's fixture manifest is not a newly sealed manifest for the original dataset. Every data-producing command's exact output-root substitutions are recorded.

The single-run `report` command requires contact-only prepared rows; the `filter-contact → train → verify → report` sequence passed. Historical `add-kl`, `add-distances` and `add-classification` commands require compatible `metrics_before_*.json` / `output_sha256_before_*.json` snapshots. They passed on explicit legacy migration fixtures preserving forests and predictions; new comparisons already include these metrics.

## Reproduce and inspect

Run the full tests from the checkout with OS shared-memory access available:

```sh
OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q
```

The detailed machine-readable aggregate is [workflow_test_20261010.json](/Users/movinggk/Documents/영재멘토/wildfire/documents/workflow_test_20261010.json). All saved inputs, outputs, logs, scripts, checkpoints and figures for these checks are under `/Users/movinggk/Documents/영재멘토/wildfire/runs/workflow_test_20261010`. The verification scripts create or expect isolated outputs; preserve the recorded runs and choose fresh directories when repeating writing steps. Existing populated outputs and incompatible frozen-source resumes are deliberately rejected.

| Evidence | Record |
|---|---|
| root | [root_verification.json](/Users/movinggk/Documents/영재멘토/wildfire/runs/workflow_test_20261010/root_verification.json) |
| unit test log | [pytest_final.log](/Users/movinggk/Documents/영재멘토/wildfire/runs/workflow_test_20261010/pytest_final.log) |
| unit test xml | [pytest_final.xml](/Users/movinggk/Documents/영재멘토/wildfire/runs/workflow_test_20261010/pytest_final.xml) |
| command coverage | [command_coverage.json](/Users/movinggk/Documents/영재멘토/wildfire/runs/workflow_test_20261010/command_coverage.json) |
| models | [verification.json](/Users/movinggk/Documents/영재멘토/wildfire/runs/workflow_test_20261010/models/run_01/verification.json) |
| fresh interpreter reload | [reload_verification.json](/Users/movinggk/Documents/영재멘토/wildfire/runs/workflow_test_20261010/models/run_01/reload_verification.json) |
| notebooks | [verification.json](/Users/movinggk/Documents/영재멘토/wildfire/runs/workflow_test_20261010/notebooks/verification.json) |
| native cli training reporting | [verification.json](/Users/movinggk/Documents/영재멘토/wildfire/runs/workflow_test_20261010/training_cli/verification.json) |
| new real model heat bridge | [verification.json](/Users/movinggk/Documents/영재멘토/wildfire/runs/workflow_test_20261010/new_model_heat/verification.json) |
| search | [verification_final.json](/Users/movinggk/Documents/영재멘토/wildfire/runs/workflow_test_20261010/search/verification_final.json) |
| heat data | [verification.json](/Users/movinggk/Documents/영재멘토/wildfire/runs/workflow_test_20261010/heat_data/run-n3qjjsem/verification.json) |
| installed wheel | [verification.json](/Users/movinggk/Documents/영재멘토/wildfire/runs/workflow_test_20261010/package_final/verification.json) |
| historical source recovery | [historical_source_recovery.json](/Users/movinggk/Documents/영재멘토/wildfire/runs/workflow_test_20261010/historical_source_recovery.json) |
| actual historical source resolution | [historical_source_actual_resolution.json](/Users/movinggk/Documents/영재멘토/wildfire/runs/workflow_test_20261010/historical_source_actual_resolution.json) |

Source hashes, record hashes, exact commands, fixture scopes, expected refusals and retained initial failures are recorded in the JSON files.
