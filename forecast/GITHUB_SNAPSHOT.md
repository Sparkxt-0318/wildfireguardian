# Final forecast snapshot — 11 October 2026

This folder preserves the maintained source, tests, documentation, demonstrations and supported final checkpoint from `wildfire (2).zip`. Files listed in PUBLICATION_MANIFEST.json match the archive byte-for-byte. No model retraining or scientific changes were made for publication.

## Install

Use Python 3.12, then run from this folder:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,baseline]'
python -m pytest tests
```

## Data required for inference

The large `data/` tree, historical experiment caches, previous checkpoints, nested Git history and the original virtual environment are not included in this Git snapshot. To reproduce data-dependent examples, unpack the forecast archive locally and copy its `wildfire/data/` directory into this folder. Do not commit that directory. The original README describes the APIs, data contracts, training and heat calculations; its links to omitted data or historical runs require that local archive. This publication is code plus the final supported checkpoint, not the entire research dataset.

The final checkpoint is `runs/20261010_categorical_balanced_benchmark/candidates/k5_legacy_02_lr0.1_warmup_cosine/checkpoint.pt`. Existing demonstration outputs can use earlier checkpoints; their identifiers remain unchanged. Publishing this snapshot does not promote an experimental routing version or establish new benchmark results.
