# Reproducing the delivered forecast ablation evidence

The portable evidence archive contains the selected source/cache assets, original final checkpoint, all 51 fit exports and failed/continued execution evidence. It excludes the installed virtual environment and the unrelated contents of the 11 GB original archive. Original recorded absolute paths remain in immutable declarations; the score replay resolves the extracted folder without editing those records.

## Verify and replay existing scores

Use Python 3.12.14 and the pinned versions in `REQUIREMENTS_EXECUTION.txt`. For score-only replay, NumPy, SciPy and scikit-learn are needed; torch/geospatial dependencies are for original fitting/forecast execution. Install dependencies in your own environment. Installation may use a network connection; dependency wheels are not bundled.

From the extracted folder:

```bash
python3 code/verify_delivery.py --study .
python3 code/replay_saved_scores.py --study . --output /tmp/wfg-forecast-score-replay-new
```

The output path must not already exist. The replay authenticates the original frozen protocol, cache, IDs, selected checkpoint and saved predictions; recomputes 2,000-draw whole-fire intervals; and compares every scoring CSV byte-for-byte. It does not train, run the forecast or select another checkpoint. These results are deterministic arithmetic replay, not new timing measurements.

Original native invocation receipts are in `native_execution/`, `main_scoring_execution/` and `dynamics_v2_execution/`. `CAMPAIGN_QUEUE.json` and both original/V2 dynamics plans preserve exact arguments and hashes. Re-running fitting or dynamics would be a new separately labelled execution and must use fresh directories; it is not required to reproduce the published score tables.

## Evidence that depends on original custody

`review/FINAL_EVIDENCE_VERIFICATION.json` records original-source and 11 GB archive preservation. The original archive is not needed for portable scoring; verifying its custody independently requires that same archive. The frozen plans reference original native input paths for audit. Do not rewrite their bytes to claim an identical frozen campaign. Selected raw Korean inputs and prepared patch caches are bundled, not fetched at runtime.

`figures/` has PNG and SVG figures. Figure whiskers/dots describe seed variability, not incident-generalization confidence. Cost receipts preserve training host and phase scope; scores cannot validate a deployment latency claim.
