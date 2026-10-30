# Independent completed Wapiti artifact alignment

Immutable snapshot: `e48054fa420af0b0477070f496c88ebc16ed2b8a`.
Verdict: PASS for bounded saved-artifact alignment. All 12 actual consistency checks pass. No writer/aggregation defect was found in the inspected snapshot.

The preservation manifest and its exact 52-case membership match the pinned 6887 US timestamp inventory. Every case receipt has its expected case ID and four-field identity, immutable JSON hash, matching prediction-file hash and the same frozen assessment binding. The frozen assessment's selection/registry pointers and N/seed/batch/boundary settings match the known committed freeze. Each prediction NPZ contains exactly the 16 prescribed model columns and row/col/y arrays.

All 52 cases pass vector shape, integer coordinate, ordered/unique coordinate, rectangle-bound, binary-label, scored-mask hash and recorded count/reference-partition checks. Each model column has the required vector shape and finite in-range probability dtype. This is schema validation only; no probability histogram, mean, quality metric or ranking was calculated or inspected.

For every row/col/y/model column, the per-fire aggregate has exactly the same dtype, shape and payload bytes as concatenating the 52 case arrays in frozen timestamp order. Interval indices, cutoff t1 strings and duration hours align with those same records. The closed 17,331,815-byte aggregate matches SHA-256 `5a8058068965de251d0716e9da37f7278d93272cda12514f92f7356196069563`. The preservation manifest matches `e944d96f1b0568fb615a35482182133c13148cf4cc32d222a6dfe676f51e2507`.

The standalone checker acquired one exclusive HEAVY lease at a case boundary and released it on completion. No active process was interrupted or changed. This was an untimed functional audit with no runtime or speed conclusion. Python, NumPy, platform and lease timestamps are retained in ALIGNMENT_RESULT.json. All 107 inspected artifact hashes are retained for reproducibility. Blobs came directly from immutable Git objects, not live output paths or a directory crawl.

Separately, all 13 tiny synthetic schema/alignment controls pass. They include typed two-case concatenation plus corrupt prediction payload/dtype, interval, t1, hours, missing model columns, mask identity, count partition, nonfinite probability, duplicate coordinate and shape cases. No model or numerical forecast was executed.

The initial/endpoint/environment/source-mask/age/residence SHA fields are checked for valid receipt references and binding to the frozen assessment. Their original scientific input arrays were outside this authorization and were not independently rehashed or replayed. Equal saved fields are not independent model-prediction, raster-reference or physical-truth validation.

No Brier, AP, AUC, NLL, ECE, calibration, ranking, probability histogram or mean was computed or inspected; no figures were rendered. No model, scorer, forecast, Monte Carlo or native code ran. No other live US or Korean output was opened. The remaining 221 US cases and 33 Korean windows are outside this review; the full independent metric checker and 306-case census remain NOT_RUN. No tuning, promotion or early quality conclusion follows.

Evidence: check_alignment.py, ALIGNMENT_RESULT.json, run log/stderr and SYNTHETIC_ALIGNMENT_CONTROLS.json. Expected schema was supplied by the parent's Tier 2 verification of the existing independent checker's bounded cohort function; this standalone review makes no new structural scorer claim and imports none of its metric code. No track or integration files were edited.
