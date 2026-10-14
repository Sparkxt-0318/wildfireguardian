# Forecast source update — 14 October 2026

This folder contains the maintained source, tests, API tutorial, supplied scientific documentation, selected small provenance records, saved heat examples and default checkpoint from `wildfire 3 (1).zip`. Large input datasets, virtual environments and historical run caches are supplied separately. This is a source and saved-model publication; no retraining was performed for the upload.

`PUBLICATION_MANIFEST.json` binds each selected incoming file to its archive SHA-256 and published SHA-256. The original README was adapted only to add the snapshot notice and migration pointer, and correct the missing bibliography link/count. Original ignore rules are preserved as `SOURCE_ORIGINAL.gitignore`; publication exclusions remain in `.gitignore`. The preceding publication manifest is preserved at `documents/archive/github_forecast_20261011/PUBLICATION_MANIFEST.json`.

## What changed

- Referenced fuel heat content, explicit flaming-phase fuel consumption, radiative-fraction inputs and optional atmospheric attenuation: [heat parameter methodology](documents/heat_parameter_models.md).
- Whole-cell burning duration, distinct from point flame residence, with a shared arrival-age rule for ongoing burning. Cell duration uses explicitly selected spread speed/direction and keeps total phase energy fixed.
- Recursive multi-hour prediction and cumulative forecast APIs.
- Observed-survey acquisition and M548/FARSITE comparisons: [observed evaluation](documents/observed_evaluation.md), [combined evaluation](documents/observed_combined_evaluation.md), and [Korean observation availability](documents/korean_observation_availability_20261012.md).
- Supplied [heat-map example](demonstration/heat_spatial_maps/20261013_fishcreek/README.md). This is a Fish Creek reference-scenario example, separate from Korean routing experiments.

## Current checkpoint

Default path:

```text
runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt
```

SHA-256: `c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843`.

The saved model uses `MixedNonnegativeKernel`, 19 input channels and 3/5/7/9 kernel branches. The preceding `k5_legacy_02_lr0.1_warmup_cosine` checkpoint remains in Git as a historical artifact; the new default path selects the mixed model. The observed-comparison workflow authenticates the exact mixed checkpoint and will reject substitution of the older checkpoint.

## Install

Use a separate Python 3.12 environment. From this folder:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,baseline]'
python -m pytest tests
```

These are the supplied installation/test instructions, not a claim that the complete pinned installation or test suite was rerun during this publication. See [README.md](README.md) and [API documentation](documents/api.md) for executable workflows and unit/coordinate contracts.

## API migration

This update changes some public return types and defaults. It is not a drop-in replacement for a previously frozen integration:

- `model.predict(...)` returns a `Prediction` object. Use its named fields or the documented `predict_sample(...)` / `predict_coordinates(...)` tuple adapters where applicable.
- Load data through the public `wildfire.load_data(...)` interface rather than the removed `wildfire.api.load_data` or `model.load_data` methods.
- Prediction defaults now use zero boundary padding and unburned missing-state policy. Select policies explicitly when comparing with a prior version; conservative callers can set `boundary='unknown'` and `missing_burned_area='unknown'`. These defaults do not establish physical observations of unknown cells.
- Supplying point `residence_time` enables cell-crossing duration by default. Existing callers that intend the point-duration scenario must explicitly use `use_cell_burning_duration=False`.

Existing active routing studies retain their sealed source, checkpoint, bridge and inputs. Publishing this folder does not migrate those studies or assign their prior results to the updated forecast. Any subsequent routing integration must declare the checkpoint, policies and duration interpretation it uses.

## External inputs and reproduction

Ordinary inference requires the aligned event environmental inputs described in the supplied README. Copy the archive's `wildfire/data/` locally or pass explicit paths; metadata catalogs alone do not replace the rasters. Do not commit the large local data tree.

The observed-combined comparison additionally requires authenticated original split arrays at `runs/20261009_weighted_stratified_split/prepared_all/`, appropriate observed survey products, environmental/FARSITE inputs and the documented native FARSITE executable/build. Those assets and historical saved-run exports are not included here. `--reuse-results` commands require their separately supplied exports. The observed comparison and thermal parameter adapters are different workflows; observed perimeter scores do not themselves measure incident heat flux.

Existing demonstration outputs and old validation reports retained from earlier publications concern their own recorded versions. New supplied validation records are author-reported evidence and have not been independently rerun as part of this upload.

## Publication checks

- All 142 incoming Python files passed syntax parsing.
- Nineteen bounded geometry, invalid-speed and nominal heat-content smoke checks passed on native macOS with CPython 3.12.14 / NumPy 2.3.5. This is not the package's pinned NumPy environment or a full forecast/routing test.
- Selected incoming file identities and checkpoint identity were verified. Credential-pattern screening found no matches in the selected source/text files.
- The supplied 88-entry [project bibliography](documents/wildfire_references.bib) and 14-entry [heat bibliography](documents/heat_parameter_models.bib) are included; counts are separate and may overlap.

No forecast inference, training, full routing benchmark, or default routing promotion was performed for this Git publication.
