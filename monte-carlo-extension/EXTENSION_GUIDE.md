# Monte Carlo forecast extension

An additive source snapshot from `wildfire 2.zip`, separate from the frozen `forecast/` package. It implements recursive, synchronous hourly binary spread, cumulative probabilities, Monte Carlo error estimates and mixed-model evaluation. No training or routing promotion was performed for publication.

## Install in a separate environment

Both snapshots install a package named `wildfire`. Do not install both into the same environment.

```sh
cd monte-carlo-extension
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,baseline]'
python -m pytest tests
```

The supplemental archive contains no model weights. To use the final supported checkpoint published next door:

```sh
mkdir -p runs/20261010_categorical_balanced_benchmark/candidates/k5_legacy_02_lr0.1_warmup_cosine
cp ../forecast/runs/20261010_categorical_balanced_benchmark/candidates/k5_legacy_02_lr0.1_warmup_cosine/checkpoint.pt runs/20261010_categorical_balanced_benchmark/candidates/k5_legacy_02_lr0.1_warmup_cosine/
```

Supply the corresponding local `data/` directory from the original forecast workspace. Large datasets, environments and Git history are not published. The source README explains `predict_cumulative`, its controls, masks and public API. Checkpoint compatibility/inference must be checked in the chosen environment before relying on outputs.

## Included results

`runs/20261011_forests_plots/` includes report.md, raw CSV metrics, protocol and comparison figures. The 57 MB full report.json is omitted. Historical checkpoints for all 573 compared models are not included. Source validation records report 2,104 passing tests; these were not rerun for this GitHub publication.

The comparison is a six-hour functional diagnostic on one KFS_06 cutoff, with eight trajectories per model, 51 new-burn reference entries and four positives. Monte Carlo intervals quantify simulation error, not forecast accuracy. The current API aggregates trajectories; exporting individual histories for routing is planned experimental work and is not implemented by this publication.

`SOURCE_MANIFEST.json` records exact original file hashes. Frozen final forecast and existing routing files are preserved.
