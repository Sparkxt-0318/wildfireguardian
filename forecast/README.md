<a id="workspace-guide"></a>

# wildfire

An importable Python workspace for two connected calculations:

1. Predict the probability that a currently unburned grid cell becomes burned
   during the **next hour**, using a saved environmental convolution model.
2. Convert that prediction into **expected incident radiant heat** under explicit
   fuel, combustion, burning-time and radiation assumptions.

The examples use the existing data and checkpoints. The burned-area data are
**retrospective reconstructions**, not hourly observations. A 375 m grid and
one-hour output spacing do not establish 375 m information content, one-hour
timing accuracy, or operational forecast skill. The radiation calculation has
not been calibrated against measured wildfire heat flux.

<a id="simple-layout"></a>

The maintained code is one `wildfire` package with **23 Python files**, grouped
by job. Data, saved experiments, demonstrations and historical documents have
separate top-level directories:

```text
wildfire/                         # Checkout root
├── wildfire/                     # All maintained Python implementation
├── data/                         # environment/, regions/, sources/, bitmaps/, records/
├── runs/                         # Prepared caches, checkpoints and saved experiments
├── demonstration/                # Probability/heat notebooks and saved example outputs
├── tests/                        # API, loader, probability and heat verification
├── documents/                    # Scientific documents and historical evidence
├── api_tutorial.ipynb            # Public API walkthrough
├── README.md
└── pyproject.toml                # One installation
```

| Job | Maintained files |
| --- | --- |
| Public interface and command dispatch | [__init__.py](wildfire/__init__.py), [api.py](wildfire/api.py), [__main__.py](wildfire/__main__.py) |
| All machine learning definitions; checkpoint loading | [models.py](wildfire/models.py) defines every learned model and fitted wrapper; [inference.py](wildfire/inference.py) loads saved checkpoints |
| Aligned data, input schema, coordinates and default paths | [data.py](wildfire/data.py), [schema.py](wildfire/schema.py), [coordinates.py](wildfire/coordinates.py), [paths.py](wildfire/paths.py) |
| Training-data preparation, common cohorts and cache integrity | [prepare.py](wildfire/prepare.py), [cohort.py](wildfire/cohort.py), [cache.py](wildfire/cache.py) |
| Training, search variants and shared runtime utilities | [train.py](wildfire/train.py), [search.py](wildfire/search.py), [utils.py](wildfire/utils.py) |
| Metrics, evaluation, reports and verification | [metrics.py](wildfire/metrics.py), [evaluate.py](wildfire/evaluate.py), [report.py](wildfire/report.py), [checks.py](wildfire/checks.py) |
| Environmental acquisition and reconstructed-data/bitmap export | [environment.py](wildfire/environment.py), [bundle.py](wildfire/bundle.py) |
| Radiation, fuel, residence duration and flame activity | [heat.py](wildfire/heat.py) |
| Runnable data, probability and heat examples | [examples.py](wildfire/examples.py) |

Use the public package for workflow access and `wildfire.models` for model
implementations:

```python
from wildfire import load_model, load_data
from wildfire.models import EnvironmentConditionedConvolution, PatchRandomForest
from wildfire.heat import ExpectedHeatFluxModel
```

Original publisher code in `data/sources`, frozen experiment source snapshots
in `runs`, and archived code in `documents/archive` remain provenance records.
Recorded local paths are resolved when files are read. If a cache names a missing
directory from an older checkout, the current inputs are used only after every
saved source size and SHA-256 matches. Saved records keep their original bytes.
Existing experiments retain their source hashes; resume them with their frozen
source snapshot when those hashes differ from the current implementation.
The [refactor verification record](documents/refactor_20261010.json) records the
file moves, preserved artifacts, tests, and checkpoint comparisons.

For a runnable walkthrough with tables and plots, open
[the API tutorial notebook](api_tutorial.ipynb). It covers wildfire prediction,
static Earth coordinates, sequences and batches, model save/reload, both heat
interfaces, verified exports, and optional training. A
[saved HTML preview](demonstration/api_tutorial/api_tutorial.html) and
[execution record](demonstration/api_tutorial/validation.json) are also included as historical artifacts from their recorded checkpoint. The active notebook uses the supported default checkpoint from the completed
`20261010_categorical_balanced_benchmark` run. Its weights differ from earlier
demonstrations; historical previews and results retain their original model identifiers.
The notebook uses the existing data and checkpoint, and creates a fresh output
directory under `demonstration/api_tutorial/runs/` each time it is run.

- [1. Install and check the environment](#install)
- [2. Run the saved-model example](#quick-example)
- [3. Load a model and one data snapshot](#load-and-predict)
- [4. Export and plot the prediction](#export-and-plot)
- [5. Save and reload model parameters](#save-and-reload)
- [6. Calculate expected radiant heat](#heat-guide)
- [Estimate active surface-flame locations](#active-flames)
- [7. Train a new model](#train-a-model)
- [Data, tensors and model contracts](#data-guide)
- [Saved results and their limits](#completed-reports)
- [Commands, files and source records](#workflows)
- [Verification and common problems](#verification)

## 1. Install and check the environment

<a id="install"></a>

Run shell commands from your checkout directory containing this README and
`pyproject.toml`. The directory name and absolute path can differ between machines:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,baseline]'
```

Use **Python 3.12**. The complete workspace specifies `>=3.12,<3.13` and retains
the pinned dependencies, including PyTorch 2.5.1. If a compatible environment is
already active, run only the installation command.

The full kernel search includes random-forest baselines. The `baseline` extra
installs the pinned `scikit-learn==1.5.2` and its `joblib` dependency; the `test`
extra alone does not install them. For an existing environment missing these
packages, run `python -m pip install -e '.[baseline]'` before the search. Check
the same interpreter with `python -c 'import sklearn, joblib; print(sklearn.__version__, joblib.__version__)'`.
After a missing-baseline error, retain the completed neural checkpoints and
resume with the exact saved protocol options. The `forests` and then `finalize`
stages can finish the experiment without rerunning its neural training stage.

Check that Python can import the public interface:

```sh
python -c 'import sys, torch; from wildfire import load_model; print(sys.version.split()[0], torch.__version__)'
```

An editable installation can use the workspace's data and checkpoints. A wheel
contains Python code and the radiation source-reference metadata; it does not
contain the large rasters, prepared caches, checkpoints or notebooks. When using
a wheel from another directory, supply the actual data and checkpoint paths.

The same installation provides `wildfire.heat`. Its radiation-only numerical
implementation uses NumPy; raster loading, geographic coordinate conversion and
checkpoint integration import their additional dependencies when requested.

## 2. Run the saved-model example

<a id="quick-example"></a>

This command loads the supported nonnegative exponential 5×5 checkpoint selected
from the completed `20261010_categorical_balanced_benchmark` run and one held-out
FishCreek snapshot at `2024-08-23T00:00:00Z`. The checkpoint is
`runs/20261010_categorical_balanced_benchmark/candidates/k5_legacy_02_lr0.1_warmup_cosine/checkpoint.pt`;
[paths.py](wildfire/paths.py) defines it as `DEFAULT_CHECKPOINT`. It performs
inference without training or downloading:

```sh
python -m wildfire example --device cpu
```

With the included checkpoint and snapshot, current inference reports:

| Field | Value |
| --- | --- |
| Model family | `exponential` |
| Environmental inputs | 19 ordered channels |
| Probability shape | `[1, 1, 103, 73]` = `[time, channel, row, column]` |
| Geographic coordinate shape | `[103, 73, 2]` = `[row, column, coordinate]`; final axis is `(latitude, longitude)` in degrees |
| Valid probability values | 1,246 |
| Unknown probability values | 6,273 |
| Maximum known probability | 0.07078481465578079 |

The 1,246 valid values describe available prediction coverage, not classification
accuracy. They include 1,021 structural zeros for known-unburned targets whose
complete source neighborhoods are all known unburned. Unknown values remain NaN
and have a false validity mask. These coverage counts describe the currently selected checkpoint and snapshot;
they do not establish that its weights or probabilities equal an earlier model.
Saved historical demonstration artifacts retain the results and model identities
of their recorded runs.

The earlier [structural-zero verification record](demonstration/zero_ignition_prediction/verification.json)
and its [prediction arrays](demonstration/zero_ignition_prediction/prediction.npz)
remain historical artifacts from their recorded checkpoint. The active
[burn-probability notebook](demonstration/probability.ipynb)
checks the supported exponential models' no-contact zeros and contact-only
evaluation cohorts.

For illustrative heat calculations and an array export, choose a new directory:

```sh
DEMO_DIR="$(mktemp -d "${TMPDIR:-/tmp}/wildfire-demo.XXXXXX")"
python -m wildfire example \
  --device cpu --heat --output "$DEMO_DIR/prediction.npz"
```

The optional output file must not already exist. Use `--help` to change the
checkpoint, data root, event, cutoff time or device. The heat parameters used by
this example are illustrative; [Step 6](#heat-guide) explains their meaning.
The `--heat` path reads aligned FBFM40 reference-fuel durations and uses sample
arrival ages for existing burning. It explicitly records the 2000 ft⁻¹ fallback
scenario for unsupported fuel classes. For a supplied uniform-duration scenario
or an event without that raster, add `--burning-duration-s 120`; the value is
numeric seconds and is recorded as a caller assumption.

## 3. Load a model and one data snapshot

<a id="load-and-predict"></a>
<a id="python-interfaces"></a>

Run the Python blocks in Steps 3–6 **in order in the same Python session**, or
copy them into one script. Start that session from the workspace root. All
variables are defined below; these steps reuse `model`, `sample` and `OUTPUT_DIR`.

### 3.1 Identify the saved artifacts

```python
from pathlib import Path
from wildfire import load_model
from wildfire.paths import DEFAULT_CHECKPOINT

ROOT = Path.cwd()
DATA_ROOT = ROOT / "data/environment"
RUNS = ROOT / "runs"
CHECKPOINT = DEFAULT_CHECKPOINT
EVENT = "WY-BTF-002416_FishCreek"
CUTOFF = "2024-08-23T00:00:00Z"

assert CHECKPOINT.is_file(), "Start Python from the workspace root."
model = load_model(CHECKPOINT, device="cpu")
print(model.family, len(model.channel_names), model.device)
```

Expected output: `exponential 19 cpu`. `load_model` restores the supported
checkpoint's saved parameters, normalization, channel
order and categorical vocabulary. `device="auto"` selects an available CUDA
device, then MPS, then CPU; explicit `"cuda"` or `"mps"` requires that device.

### 3.2 Read exactly one aligned snapshot

```python
selection = dict(
    events=[EVENT],
    sequence_length=1,
    time_range=(CUTOFF, CUTOFF),
)
with model.load_data(DATA_ROOT, **selection) as dataset:
    assert len(dataset) == 1
    sample = dataset[0]

print(tuple(sample["burned_area"].shape))
print(tuple(sample["features"].shape))
assert tuple(sample["channel_names"]) == model.channel_names
```

Expected shapes are `(1, 1, 103, 73)` for the current cumulative burned state
and `(1, 19, 103, 73)` for environmental features. The context manager closes
cached raster readers; the returned sample tensors remain usable afterward.

Use `model.load_data` for fitted-model inference. It fixes the saved channel
order and category definitions. Do not pass a new `channels` selection to this
method or manually normalize its raw physical inputs.

### 3.3 Predict the next-hour transition

```python
probability_tensor, coordinate_tensor = model.predict_sample(sample)
probability = probability_tensor.cpu().numpy()
coordinates = coordinate_tensor.numpy()

# Request the additional masks and family-specific diagnostics separately.
result = model.predict_sample_details(sample)
valid = result.valid.cpu().numpy()
rate = result.rate.cpu().numpy()  # nonnegative hourly rate, in h⁻¹

print(probability.shape)
print(coordinates.shape)
print("cell (row=50, column=35):", coordinates[50, 35])
print("valid:", int(valid.sum()), "unknown:", int((~valid).sum()))
assert probability.shape == (1, 1, 103, 73)
assert coordinates.shape == probability.shape[-2:] + (2,)
```

`predict_sample` returns a tuple `(prediction_matrix, coordinate_matrix)`.
The prediction is a probability tensor on the selected model device. Coordinates
are a CPU `torch.float64` tensor with shape `(H, W, 2)` for one snapshot or
sequence. The final axis is `(latitude, longitude)`, in WGS84 degrees
(EPSG:4326). The grid is fixed across time, so its coordinate matrix has no time
or prediction-channel dimension. Thus `coordinates[row, column]` locates the
center of the cell represented by `probability[t, 0, row, column]` at every time
index `t`. A collated batch returns coordinates with shape `(B, H, W, 2)`,
allowing a different fixed grid for each batch item.

Coordinates are computed from the sample's affine transform and source CRS;
the input projected coordinates are not simply relabeled as latitude/longitude.
Real grid cells retain their coordinates even if a prediction is unavailable.
Coordinates for spatially padded pixels are NaN. Temporal padding does not
change this static coordinate matrix; `time_valid` and the input validity masks
identify unavailable time samples separately.

`predict_sample_details` returns the previous rich result with `probability` and
`valid`, plus `rate` and `rate_valid` for the exponential family. Rates are
nonnegative and measured in h⁻¹. Use `probability` for probability calculations.
Both prediction interfaces consume current inputs and their masks; they do not consume future
outcomes or arrival labels.

For your own arrays, the equivalent call is:

```python
manual_probability, manual_coordinates = model.predict(
    sample["burned_area"],
    sample["features"],
    channel_names=sample["channel_names"],
    burned_area_valid=sample["burned_area_valid"],
    feature_valid=sample["feature_valid"],
    affine_transform=sample["affine_transform"],
    epsg=sample["epsg"],
    pixel_valid=sample.get("pixel_valid"),
)
```

Supply boolean masks with the same shapes as their respective inputs. Preserve
the saved channel order and raw physical units; saved normalization is applied
once inside the model. The tuple-returning `predict` requires the source
`affine_transform` and `epsg`; those are supplied automatically by
`predict_sample`. Pass `pixel_valid` to exclude spatial padding from coordinates,
and preserve the input validity masks for spatial and temporal padding in
predictions. The optional `time_valid` argument remains accepted for compatibility;
it does not affect static coordinates. `predict_details` returns masks and model
diagnostics without requiring geographic metadata. `predict_proba` is the
probability-only convenience method.

## 4. Export and plot the prediction

<a id="export-and-plot"></a>

Create a new output directory and save probabilities with masks and coordinates:

```python
import tempfile
import numpy as np

OUTPUT_DIR = Path(tempfile.mkdtemp(prefix="wildfire-readme-"))
np.savez_compressed(
    OUTPUT_DIR / "probability.npz",
    probability=probability,
    valid=valid,
    rate_h_inverse=rate,
    coordinates_latitude_longitude_deg=coordinates,
    source_coordinates_xy_m=sample["coordinates"].numpy(),
    affine_transform=sample["affine_transform"].numpy(),
    epsg=sample["epsg"].numpy(),
)
print(OUTPUT_DIR)
```

The exported `coordinates_latitude_longitude_deg` has shape `[H, W, 2]`
and stores geographic pixel-center `(latitude, longitude)` in degrees. Its row
and column indices align with `probability` at every time step.
`source_coordinates_xy_m` preserves the loader's original
shape `[2, H, W]`: projected pixel-center `x` then `y`, in metres.
`affine_transform` contains the six pixel-corner affine coefficients; `epsg`
identifies that source coordinate reference system. These retain placement
independently of the following plot, whose axes are pixel indices.

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

probability_map = np.ma.masked_where(~valid[0, 0], probability[0, 0])
fig, ax = plt.subplots()
image = ax.imshow(probability_map, vmin=0.0, vmax=1.0, cmap="magma")
ax.set(title="Next-hour new-burn probability", xlabel="Column", ylabel="Row")
fig.colorbar(image, ax=ax, label="Probability")
fig.savefig(OUTPUT_DIR / "probability.png", dpi=150, bbox_inches="tight")
plt.close(fig)
```

Masked cells are unavailable predictions. Filling them with zero would change
their meaning to a known zero probability.

## 5. Save and reload model parameters

<a id="save-and-reload"></a>

```python
import torch

saved_checkpoint = model.save(OUTPUT_DIR / "model.pt")
reloaded = load_model(saved_checkpoint, device="cpu")
reloaded_probability, reloaded_coordinates = reloaded.predict_sample(sample)
torch.testing.assert_close(
    probability_tensor,
    reloaded_probability,
    rtol=0.0,
    atol=0.0,
    equal_nan=True,
)
torch.testing.assert_close(
    coordinate_tensor,
    reloaded_coordinates,
    rtol=0.0,
    atol=0.0,
    equal_nan=True,
)
```

Saving includes resident parameters, training-only preprocessing statistics,
channel/category metadata and the original checkpoint fields. It does not fit
anything. An existing destination raises `FileExistsError` unless you explicitly
call `model.save(path, overwrite=True)`.

## 6. Calculate expected radiant heat

<a id="heat-guide"></a>

New burning during the next hour and active burning at a particular instant are
different quantities. The composed model assumes ignition time is uniform within
the forecast hour, conditional on new ignition, and burning lasts for a supplied
duration. This timing assumption comes from the heat calculation, not from the
trained probability model.

For a new-ignition probability $q_i$, forecast duration $D=3600$ seconds and
burning duration $T_i>0$, define $r_i=\min(T_i/D,1)$. The assumed mean and endpoint
active-burning probabilities are

$$
\overline p_i^{\mathrm{new}}=q_i\left(r_i-\frac{r_i^2}{2}\right),
\qquad p_i^{\mathrm{new}}(D)=q_i r_i.
$$

Mean incident flux uses the mean occupancy; endpoint flux uses the endpoint
occupancy. Supplied initial activity $p_i^0$ with remaining duration $R_i\ge0$
has mean occupancy $p_i^0\min(R_i/D,1)$ and endpoint occupancy
$p_i^0\mathbf 1_{\{R_i>D\}}$. Extinction exactly at $D$ contributes zero at that endpoint.

For an already-burned cell with supplied arrival time $a_i$ and current time
$t_0$ in seconds from the same origin, the heat model derives

$$
p_i^0=\mathbf 1_{\{a_i\le t_0<a_i+T_i\}},\qquad
R_i=\max\{T_i-(t_0-a_i),0\}.
$$

Thus an old burned cell contributes only for its remaining burning time. Its
activity at the prediction endpoint $t_0+D$ is
$\mathbf 1_{\{a_i\le t_0+D<a_i+T_i\}}$. The model sets its first-new-burning
probability to zero. Current and new-burning contributions occupy disjoint
cells, so their mean and endpoint probabilities can be added.

### 6.1 Specify the physical assumptions

Reuse the one-snapshot `sample` and fitted `model` from Step 3:

```python
from wildfire.heat import AffineGrid, CombustionParameters, FlameResidenceTime

grid = AffineGrid(tuple(sample["affine_transform"].tolist()))
residence = FlameResidenceTime.from_fbfm40_raster(
    DATA_ROOT / "regions" / EVENT / "fuel" / "landfire_2016_fbfm40_375m.tif",
    grid=grid,
    expected_shape=tuple(sample["burned_area"].shape[-2:]),
    epsg=int(sample["epsg"]),
    # Explicit scenario for missing/unsupported/nonburnable classes.
    # The provenance reports how many cells use this assumption.
    fallback_sav_m_inv=2000.0 / 0.3048,
)
combustion = CombustionParameters.from_flame_residence(
    residence,
    fuel_load_kg_m2=1.0,
    heat_of_combustion_j_kg=18_000_000.0,
    consumed_fraction=0.10,
)
heat_model = model.heat_model(
    grid=grid,
    epsg=int(sample["epsg"]),
    combustion=combustion,
    residence_time=residence,
    radiative_fraction=0.3,
    emission_height_m=5.0,
    receiver_height_m=0.0,
    atmospheric_transmissivity=1.0,
)
```

Duration now varies by cell using reference fuel classes and the residence
relation described in [Section 6.4](#active-flames). The raster reader checks
shape, affine transform and CRS, performs no resampling, and records its source
checksum. Omit `fallback_sav_m_inv` to reject missing, unsupported or nonburnable
classes. An explicit fallback is a scenario; it does not establish combustible
fuel in such cells. The data do not supply measured per-cell extinction times.

The other numbers are **illustrative assumptions**, not measured parameters for
FishCreek. The consumed fraction refers to the modeled emitting phase. Dry fuel loading is per entire ground-cell area; partial burning
requires a correspondingly adjusted loading or source density. Effective heat
of combustion is in J/kg, duration is in seconds, and source/receiver heights
share a metric height datum. Source height must exceed receiver height.

### 6.2 Calculate and interpret the outputs

```python
heat_matrix, heat_coordinates = heat_model.predict_sample(sample)
print("heat shape:", heat_matrix.shape)  # (103, 73), W/m²
print("coordinate shape:", heat_coordinates.shape)  # (103, 73, 2)

# Inspect incomplete coverage, bounds, energy and other physical diagnostics.
heat = heat_model.predict_sample_details(sample)
print("complete expected heat:", heat.complete)
print("activity at the cutoff:", heat.initial_active_burning_probability)
print("remaining burning seconds:", heat.initial_remaining_burning_duration_s)
print("activity at the next-hour endpoint:", heat.endpoint_flame_map().probability)

np.savez_compressed(
    OUTPUT_DIR / "heat.npz",
    complete=heat.complete,
    mean_flux_w_m2=heat_matrix,
    coordinates_latitude_longitude_deg=heat_coordinates,
    known_source_flux_w_m2=heat.known_source_heat_flux_w_m2,
    lower_flux_w_m2=heat.heat_flux_lower_bound_w_m2,
    upper_flux_w_m2=heat.heat_flux_upper_bound_w_m2,
    energy_j_m2=heat.expected_incident_energy_j_m2,
    lower_energy_j_m2=heat.incident_energy_lower_bound_j_m2,
    upper_energy_j_m2=heat.incident_energy_upper_bound_j_m2,
    initial_active_probability=heat.initial_active_burning_probability,
    remaining_burning_duration_s=heat.initial_remaining_burning_duration_s,
    initial_burning_valid=heat.initial_burning_valid,
    mean_active_valid=heat.active_burning_valid,
    endpoint_active_probability=heat.endpoint_active_burning_probability,
    endpoint_active_valid=heat.endpoint_active_burning_valid,
    endpoint_flux_w_m2=heat.expected_endpoint_heat_flux_w_m2,
    residence_duration_s=residence.duration_s,
)
```

The heat prediction also returns a tuple `(prediction_matrix, coordinate_matrix)`.
Both members are NumPy arrays: the first is the expected mean incident radiant
heat flux in W/m², with shape `(H, W)`; the second has shape `(H, W, 2)` and
float64 WGS84 `(latitude, longitude)` values in degrees. Thus
`heat_coordinates[row, column]` is the geographic center of the receiver cell
represented by `heat_matrix[row, column]`.

The remaining spatial diagnostic arrays have shape `(H, W)`; here that is
`(103, 73)`. Use `predict_sample_details`, `predict_details`, or
`predict_from_new_burn_probability_details` to obtain the rich heat result.
The corresponding default methods return the heat/coordinates tuple. A raw
heat prediction requires a configured source `epsg`; sample prediction reads
the sample's EPSG and checks it against the configured grid and CRS. The heat
calculation requires a projected source CRS whose horizontal units are metres.

The example has unresolved emitting sources, so `heat.complete` is `False`. Complete expected
flux and energy can remain NaN even at receivers with valid local probability,
because an unknown source elsewhere can contribute radiation.

| Output | Meaning |
| --- | --- |
| `expected_heat_flux_w_m2` | Mean full supplied-domain incident radiant flux over the next hour, W/m² |
| `known_source_heat_flux_w_m2` | Contribution from known modeled sources, W/m² |
| `heat_flux_lower_bound_w_m2`, `heat_flux_upper_bound_w_m2` | Bounds for unknown new-burn probability and, when arrival timing is used, unknown existing-fire age |
| `expected_incident_energy_j_m2` | Mean expected flux × 3,600 seconds, J/m² |
| `incident_energy_lower_bound_j_m2`, `incident_energy_upper_bound_j_m2` | Corresponding interval-energy bounds, J/m² |
| `initial_active_burning_probability`, `initial_remaining_burning_duration_s` | Cutoff activity and remaining seconds inferred from arrival/duration, or supplied explicitly |
| `initial_burning_valid` | Whether cutoff activity and remaining duration are resolved within the selected calculation scope |
| `active_burning_valid`, `endpoint_active_burning_valid` | Separate validity of mean activity and endpoint activity; new-burn validity alone does not resolve an unknown existing-fire age |
| `expected_endpoint_heat_flux_w_m2`, `endpoint_complete` | Instantaneous endpoint flux in W/m² and whether all contributing source activity is resolved at the endpoint |

The bounds hold under the supplied combustion, timing and radiation assumptions.
They do not cover outside-domain fires, parameter uncertainty, convection or
unmodeled heat mechanisms. Existing fire is included only on known already-burned
support; the bounds do not model existing fire hidden by unknown cumulative-state
coverage. The known-source contribution is not a complete
heat prediction when coverage is missing.

By default, `heat_model.predict_sample(sample)` and its details method use
`arrival_hours`, `arrival_valid` and `elapsed_hours` when available, converting
hours to seconds. Arrival times affect only known already-burned cells; the
checkpoint still uses current burned state and environmental inputs for new
ignition. Future-arrival values and next-hour labels do not replace its forecast.
The existing bundle supplies retrospective arrival estimates, so this is a
nominal reconstructed-arrival scenario. Arrival uncertainty is not integrated
out, and the result does not establish observed current flaming or exact extinction.

Missing arrival on a known burned cell leaves its cutoff activity and mean
occupancy unknown. Its remaining time lies in $[0,T_i]$, so its mean-occupancy
upper bound is $\min(T_i/D,1)$. Its endpoint activity is known zero when
$T_i\le D$; otherwise its endpoint upper bound is one. Missing age therefore
can leave mean heat incomplete even when endpoint heat is resolved. Missing
arrival on an unburned cell adds no existing-fire contribution.

Set `initial_burning_from_arrival=False` to exclude sample arrival timing.
Samples without arrival/elapsed data retain the new-ignition-only scope;
partial timing fields raise an error. If independently known, supply
`initial_active_burning_probability` and `initial_remaining_burning_duration_s`
to `heat_model.predict_sample`; these override automatic sample timing, and
positive present-active probabilities must be restricted to known already-burned
cells. Raw-array calls accept `arrival_time_s`, `current_time_s`, and optional
`arrival_valid`; the saved-probability bridge also requires `already_burned_mask`.
All raw times must share an origin and be numeric seconds. An explicit
`unknown_new_burn_probability` fills unsupported predictions as caller-supplied
estimates, recorded separately from original model predictions.

### 6.3 Use active-burning probabilities without a wildfire checkpoint

This independent example requires only the radiation package and NumPy:

```python
import numpy as np
from wildfire.heat import AffineGrid, CombustionParameters, ExpectedHeatFluxModel

active_probability = np.array([[0.0, 0.4, 0.0], [0.1, 0.8, 0.2]])
synthetic_combustion = CombustionParameters(
    fuel_load_kg_m2=1.0,
    heat_of_combustion_j_kg=18_000_000.0,
    burning_duration_s=120.0,
)
radiation = ExpectedHeatFluxModel(
    grid=AffineGrid.from_cell_size(
        cell_size_m=10.0,
        origin_xy_m=(1_000_000.0, 2_000_000.0),
        row_direction=-1,
    ),
    epsg=5179,
    heat_release_rate_density_w_m2=synthetic_combustion.heat_release_rate_density_w_m2,
    radiative_fraction=0.3,
    emission_height_m=5.0,
)
incident_flux, incident_coordinates = radiation.predict(active_probability)
print(incident_flux.shape)  # (2, 3), W/m²
print(incident_coordinates.shape)  # (2, 3, 2), (latitude, longitude) degrees

# The previous rich result is available when additional diagnostics are needed.
instantaneous = radiation.predict_details(active_probability)
```

This illustrative grid is georeferenced in Korea's metric EPSG:5179 projection;
its first pixel corner is the explicitly supplied projected origin. The returned
coordinates locate receiver pixel centers in WGS84. For an explicitly local
synthetic grid with no Earth reference, use `predict_details` without `epsg`.

Here probabilities describe active burning at one stated instant and must be
complete, finite and in `[0, 1]`. `predict_at_points` supports arbitrary
horizontal receiver coordinates in the same metric plane and returns a tuple
of flux values with shape `(N,)` and geographic receiver coordinates with shape
`(N, 2)`, again ordered `(latitude, longitude)` in degrees. Use
`predict_at_points_details` for its rich result or a local grid without a CRS.
Same-grid flux is a point evaluation at each receiver cell center, not a
receiver-area average.

Let $p_i$ be the instantaneous probability of active burning in source cell $i$,
and let $x$ be a horizontal receiver point. With conditional heat-release density
$Q_i$, radiative fraction $\chi_i$,
transmission $\tau$ and source-cell solid angle $\Omega_i(x)$, the model uses

$$
\mathbb E[q''(x)]=\tau\sum_i p_i\chi_iQ_i\frac{\Omega_i(x)}{4\pi},
\qquad Q_i=\frac{w_i f_i H_{c,i}}{T_i}.
$$

Here $w_i$ is dry fuel loading, $f_i$ consumed fraction, $H_{c,i}$ effective heat
of combustion and $T_i$ burning duration. Linearity of this expectation does not
require cell independence. Marginal probabilities alone cannot determine heat
variance, quantiles or exceedance probabilities. The operator integrates each
uniformly emitting elevated cell footprint; it assumes isotropic radiation and
upward-facing horizontal receivers. It does not model vertical receivers,
directional flames, terrain occlusion or convective heating.

Optional `EcologicalFuelMaps.from_fccs_rasters` reads aligned LANDFIRE reference
fuel loadings and coverage. `combustion_parameters` converts them to combustion
inputs. Partial mapped coverage requires an explicit loading assumption for the
unmapped portion; unknown fuel is not zero fuel. Reference fuelbeds are not
event-date field measurements. The reader checks grid/CRS alignment and converts
U.S. short tons per acre to kg/m². See the [radiation source references](wildfire/heat_sources.json)
and [temporal implementation](wildfire/heat.py) for the source record
and complete timing contract.

### 6.4 Estimate active surface-flame locations

<a id="active-flames"></a>

The literature calls the time a passing flame front spends at one fixed fuel
location **flaming residence time**. It differs from time since ignition,
cumulative burned area, smoldering duration, and the time during which some part
of a 375 m cell contains a flame. The implemented model estimates surface-flame
activity at representative grid locations under explicit fuel and timing
assumptions. It does not recover observed flame geometry.

Run the saved-checkpoint example without training or downloading data:

```sh
python -m wildfire flames \
  --output demonstration/heat/active_flame_demo \
  --min-probability 0.001 \
  --fallback-sav-ft-inv 2000
```

The example uses the existing FishCreek cutoff, LANDFIRE 2016 fuel classes,
Scott–Burgan's 40 standard fuel models, and Anderson's residence relation. It
exports `active_flame_arrays.npz`, `active_flame_maps.png`, `summary.json`, and
three coordinate tables:

| File | Meaning |
| --- | --- |
| `nominal_current_positions.csv` | Active centers under retrospective point-arrival times at the cutoff |
| `forecast_endpoint_candidates.csv` | New-ignition endpoint centers meeting the explicitly supplied probability threshold |
| `forecast_probability_locations.csv` | Every positive endpoint probability, ranked from largest to smallest; these are probability estimates, not detected flames |

CSV columns include zero-based row/column, projected x/y in metres, EPSG,
longitude/latitude, probability, query timestamp, and whether the residence
duration used an explicit fallback scenario. Unsupported/nonburnable fuel
classes have no implicit residence duration. The example explicitly supplies
2000 ft⁻¹ as a scenario for them and identifies those cells in outputs. This
fallback does not establish combustible fuel in a mapped nonburnable cell.
Omit `fallback_sav_m_inv` in the public constructor to reject unsupported codes.

For a complete supplied characteristic particle surface-area-to-volume ratio
$\sigma_i$ in m⁻¹, the implemented relation is

$$
\tau_i = \frac{384\cdot60/0.3048}{\sigma_i}
       = \frac{75\,590.5511811}{\sigma_i}\quad\text{seconds}.
$$

The original equation uses minutes and ft⁻¹. For example, 2000 ft⁻¹ means
`2000 / 0.3048` m⁻¹ and gives 11.52 seconds. Cell width is not particle diameter.
The [research record](documents/flame_residence_literature.md) explains the
primary sources, fuel catalog, surface-area weighting, and applicability.

```python
import numpy as np
from wildfire.heat import (
    AffineGrid, FlameResidenceTime,
    active_flames_from_arrival, forecast_active_flames,
)

grid = AffineGrid.from_cell_size(375.0)
residence = FlameResidenceTime.from_surface_area_to_volume(2000.0 / 0.3048)

# All times share this example's arbitrary origin and are numeric seconds.
arrival_s = np.array([[95.0, 80.0, np.nan]])
current = active_flames_from_arrival(arrival_s, residence, 100.0, grid=grid)
positions = current.positions(min_probability=1.0)
print(positions.cells_rc)           # [[0 0]]
print(positions.coordinates_xy_m)   # [[187.5 187.5]]
print(current.remaining_duration_s) # [[6.52 0.0 nan]]

# q is probability of first NEW burning during the next hour.
q = np.array([[0.8, 0.2, np.nan]])
forecast = forecast_active_flames(q, residence, 3600.0, grid=grid)
print(forecast.endpoint.probability) # [[0.00256 0.00064 nan]]
print(forecast.endpoint.positions(min_probability=0.001).cells_rc) # [[0 0]]
```

For known or supplied point-arrival time $a_i$, activity is
$\mathbf{1}\{a_i\le t<a_i+\tau_i\}$. At exact extinction the location becomes
inactive; unknown arrival remains unknown. The separate forecast assumes
arrival is uniform within the hour conditional on first new burning. With
$D=3600$ seconds and $r_i=\min(\tau_i/D,1)$, endpoint flame probability is
$q_i r_i$ and mean occupancy is $q_i(r_i-r_i^2/2)$. These additional timing
assumptions are not learned or calibrated active-flame observations.

Use `model.predict_active_flames_sample(sample, residence_time=residence)` on
one dataset snapshot to connect the saved model to this conversion. It reads
current state/environment, grid and timestamp; it does not read arrival or
future-label fields. Existing flames require separate age information. The
explicit `active_flames_from_arrival` call is the retrospective alternative.

`FlameResidenceTime.from_fbfm40(codes)` derives the characteristic SAV from
the source fuel-class parameters. `from_particle_diameter(diameter_m)` provides
Anderson's particle relation; `from_eucalypt_wood_diameter(diameter_mm)` provides
Burrows's laboratory jarrah-twig relation, restricted to 1–16 mm. These methods
describe different experimental quantities. No one duration or biomass/biome
lookup covers all trailing or intermittent visible flames.

To keep flame activity and conditional heat emission consistent, build
`CombustionParameters.from_flame_residence(residence, fuel_load_kg_m2=...,
heat_of_combustion_j_kg=..., consumed_fraction=...)`, then pass both `combustion`
and `residence_time=residence` to `model.heat_model`. The consumed fraction must
refer to the modeled flaming phase. `heat_result.endpoint_flame_map()` exposes
the endpoint probabilities and position selection from the same heat bridge.

For an end-to-end heat example with fuel-derived durations and existing-fire
arrival ages, run:

```sh
python -m wildfire heat \
  --output demonstration/heat/duration_aware_demo
```

This uses the saved checkpoint
without fitting, retains source checksums and fallback assumptions, and exports
cutoff/remaining/endpoint activity alongside heat and energy bounds.

At the default FishCreek cutoff, the residence scenario gives no nominal active
centers and no forecast centers reaching the example's 0.001 threshold. This
does not establish absence of real flames. Its reconstructed arrival kriging
standard deviation ranges from 32.78 to 246.67 hours (median 87.61 hours),
far larger than seconds-long residence. The full probability map and all
positive-probability coordinates are retained. These outputs are scenario
estimates, not evidence of operational active-flame detection skill.

## 7. Train a new model

<a id="train-a-model"></a>

Training is optional: inference in Steps 2–6 uses saved models. The following
example stands alone and runs from the workspace root. It uses the existing
contact-filtered 5×5 prepared cache. The default family is `exponential`.

### 7.1 Fit from an existing prepared cache

```python
from pathlib import Path
import tempfile
from wildfire import TrainingConfig, WildfireModel

prepared = Path(
    "runs/"
    "20261009_weighted_stratified_split/prepared_all"
)
experiment = Path(tempfile.mkdtemp(prefix="wildfire-training-"))
trained = WildfireModel.train(
    prepared_data=prepared,
    output_dir=experiment / "fitted",
    family="exponential",
    config=TrainingConfig(epochs=30, patience=6, batch_size=1024, device="cpu"),
)
exported = trained.save(experiment / "model.pt")
print(exported)
print(trained.training_metrics.keys())
```

The cache contains `metadata.json`, `train.npz`, `validation.npz` and `test.npz`.
Metadata fixes the kernel size, input schema, explicit split unit and partition memberships. The
trainer fits normalization on training rows, selects the best checkpoint using
validation, then reports test scores. `trained` contains that selected checkpoint;
`training_metrics` contains the returned evaluation record.

The exponential family optimizes weighted squared error on probabilities.
Validation and test use the same probability link. Sampling weights are retained.
Changing `epochs`, `device` or another setting creates a new experiment rather
than reproducing the saved report exactly. A training directory must be new or
empty; the example creates a fresh temporary experiment directory.

### 7.2 Prepare a new cache when data or kernel support changes

This separate workflow prepares all events and can take substantially longer
than inference. It retains the prepared cache's declared split and negative
sampling scheme, then excludes targets without current burned-neighbor contact
from every partition:

```sh
RUN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/wildfire-prepare.XXXXXX")"
python -m wildfire prepare \
  --data-root data/environment \
  --kernel-size 5 --output-dir "$RUN_DIR/prepared_all"
python -m wildfire filter-contact \
  --source-dir "$RUN_DIR/prepared_all" --output-dir "$RUN_DIR/prepared"
echo "$RUN_DIR/prepared"
```

Pass the printed prepared-directory path to `WildfireModel.train`. Changing a saved checkpoint's
channel order, category definitions or preprocessing is not a substitute for
preparing and fitting a new model. Training defaults use five continuous inputs
plus fourteen fixed one-hot biome indicators, giving 19 channels.

### Weighted stratified training and validation

Fresh `prepare` commands now default to `--split-policy weighted-cell-hour`,
`--validation-fraction 0.2`, and `--split-seed 7`. Negative sampling still uses
its independent `--seed`; original labels and inverse inclusion weights are
retained. Use `--split-policy season` to reproduce the historical seasonal
partition design.

To repartition an existing original cache without processing rasters again:

```sh
python -m wildfire resplit \
  --source-dir runs/20261007_1h_kernel_sweep/9x9/prepared_all \
  --output-dir runs/20261009_weighted_stratified_split/prepared_all \
  --validation-fraction 0.2 --seed 7
```

This pools only the original training and validation cell-hours. Strata use
next-hour outcome, the smallest current-contact neighborhood, and categorical
values present in each supported environmental crop. Seeded random row order
and weight balancing target 20% of each stratum's represented population in
validation. The target applies to original inverse inclusion weights, rather
than only sampled row counts. A singleton stratum stays in training. Training
must contain every categorical value appearing in the pooled data and fixed
test inputs; coverage is checked both on full patches and on contact-eligible
rows at each kernel size. A test-only category makes the operation fail rather
than move a test fire into training.

`test.npz` is copied byte-for-byte, and every original test fire remains
exclusive to test. All original rows, features, outcomes, and weights are
retained. Training and validation share fires but have disjoint cell-hour
identities; nearby cells, hours, and overlapping patches can occur across
those two partitions. Validation therefore measures held-out cell-hours
within represented fires. Test retains the original whole-fire, later-season
holdout. Matching outcome frequency does not equalize environmental difficulty.

The new cache includes `metadata.json` and `resplit.json` with categorical
coverage, weighted frequencies by contact support, original and new event
memberships, parent checksums, and exact row/weight/test preservation checks.
Fresh preparation also retains the extraction metadata. Repartitioning does
not fit or reuse a model, preprocessing statistics, or optimizer state.

Standard kernel-search defaults use the new cache and fresh output directories.
For a supplied cache, run the multiscale search directly:

```sh
python -m wildfire search-multiscale run \
  --cache runs/20261009_weighted_stratified_split/prepared_all \
  --output runs/new_weighted_experiment \
  --device mps
```

Use a new experiment directory: old checkpoints, normalization, scores, and
resume protocols belong to their original split and frozen source version.
Original-cache recovery and portable relocation still verify their historical
checksum bindings; a new split cache is supplied directly to the search.

### Categorical input imbalance during fitting

New training defaults to `categorical_balance="inverse-sqrt"` in `TrainingConfig`,
and `--categorical-balance inverse-sqrt` in the training and search commands.
This adjusts optimization weights for categorical **inputs**. Original cached
inverse inclusion weights still define normalization of continuous channels,
population metrics, validation checkpoint/hyperparameter selection, calibration,
and classification threshold selection.

For each learner's actual raw native input crop, categorical frequency is the
original-weighted fraction of training rows whose patch contains a class anywhere.
The raw class factor is `min(10, max(frequency, 0.001)**(-0.5))` for observed
classes. Each row averages factors over its distinct present classes, then over
categorical source fields, and divides by the original-weighted mean row factor.
Multiplying the original weight by this normalized factor yields the optimization
weight. The factor uses training inputs only, with no outcome-dependent weighting
and no validation or test frequencies. This is capped emphasis on rare contexts;
it does not make every category equally frequent.

Categorical one-hot channels now retain raw 0/1 values (`mean=0`, `scale=1`).
Only continuous channels use training-only population-weighted standardization.
This prevents rare indicators from becoming very large merely because their
training frequency is small. Saved preprocessing is applied unchanged at inference.

The optimizer minimizes Brier using the adjusted weights, with its stated
optimization-weighted prevalence scale. Population training Brier and adjusted
training Brier are saved separately. Neural learners and search random forests
use the same category adjustment for a given native support. Global-rate
initialization and descriptive baselines retain the original population weights.
Per-category diagnostics in `metrics.json` use original weights and represent
patches containing a class; these groups overlap and are not additive.

Every fresh training run saves a `categorical_balance.json` audit; search runs
save one under `categorical_balance/kK.json` for each native kernel size. Settings,
raw/effective category frequencies, weight checksums, support, and fitted factors
are bound into checkpoint or experiment metadata. Altered settings or reports
cannot silently resume an existing search. Use a fresh output directory.

To disable only the categorical loss adjustment, set
`TrainingConfig(categorical_balance="none")` or pass `--categorical-balance none`.
`--categorical-balance-min-frequency` and `--categorical-balance-max-factor`
control the frequency floor and raw per-category cap. Disabling the adjustment
retains the new raw one-hot preprocessing.

The [training-distribution audit](documents/categorical_balance_training_20261009.json)
records the measured imbalance and resulting weights for the current cache.
The [method and verification report](documents/categorical_balance_training_20261009.md)
explains the objective and its limits. Biome 8 occurs only in surrounding context,
not target centers, and has just one training row in the native 3x3 cohort;
weighting cannot create additional examples or establish reliable calibration.

### 7.3 Search nonnegative kernel learners over longer training budgets

All search modules in sections 7.3–7.6 accept a complete 9x9 input cache.
Their current default is
`runs/20261009_weighted_stratified_split/prepared_all/`,
containing `metadata.json`, `train.npz`, `validation.npz`, and `test.npz`.
It retains no-contact rows; each search applies its own contact training and
evaluation conditions. Training and validation contain disjoint cell-hours
from the pooled development fires; test retains the original exclusive fires.
The cache is a data dependency, not part of the Python source installation.
Deleting the experiment folders can remove it.

The original seasonal cache, retained independently of the current demonstration checkpoint, at
`runs/20261007_1h_kernel_sweep/9x9/prepared_all/`
is the source for the `resplit` command above. If that original cache is missing
and the sibling `WildfireGuardian.zip` archive is available, restore its exact
four files:

```sh
OPENBLAS_NUM_THREADS=1 .venv/bin/python -m wildfire recover-cache
```

The recovery tool checks the original SHA-256 bindings, all source-file hashes,
and array headers before promoting a staged directory. It leaves existing
partial caches and incompatible run protocols intact and extracts no unrelated
archive files. It does not train a model or restore an optimizer checkpoint.
Its default archive is the project ZIP beside this workspace; use `--archive`
for another location. Repeating it verifies an already restored original cache.
After recovery, run `resplit` as shown above to create the weighted default
cache before starting a new search. Recovery alone retains the seasonal split.

Alternatively, prepare a **fresh** weighted cache from the environmental data:

```sh
OPENBLAS_NUM_THREADS=1 .venv/bin/python -m wildfire prepare \
  --data-root data/environment \
  --kernel-size 9 --seed 7 \
  --contact-negatives-per-event 5000 --no-contact-negatives-per-event 2000 \
  --output-dir runs/new_search_cache/prepared_all
```

Pass that directory with `--cache` and choose a new `--output` for training.
Do not run `filter-contact` on this shared cache. Fresh preparation is not a
byte-identical recovery and cannot silently replace the data bound to an
existing resume protocol. To resume an interrupted search, retain its
`protocol.json` and candidate `last.pt` states as well as the four input files,
then repeat the same training command with the unchanged source version.
The ZIP restores the historical original cache; a missing weighted cache or
optimizer state requires its own matching backup to resume an existing run.

The runnable search uses `wildfire.search.Search` to retrain constant,
linear, legacy convolutional, convolutional neural network, multilayer
perceptron, and residual multilayer perceptron kernel learners. Each produces
nonnegative off-center kernel rates with the same exponential probability link.
The full configuration covers 3×3, 5×5, 7×7, and 9×9 kernels and initial budgets
of 512 epochs. It extends the validation-selected configuration in each neural
family to a full 4,096-epoch budget with no early stopping. Neural
configurations search width, depth, learning rate, weight decay and dropout
as applicable. Random forests with 3×3 and 5×5 inputs are freshly fitted
as additional probability baselines. The full-budget search is prepared for
you to run; it has not been executed as part of the code verification.

```sh
.venv/bin/python -m wildfire search run --device mps
```

The default plan contains **40 fresh kernel fits**: ten joint configurations
for each of four kernel sizes. Every initial fit runs 512 full-batch epochs.
The best common-validation configuration across kernel sizes in each of the
four neural families continues from its last optimizer and random state to
4,096 total epochs. The other candidates retain their complete 512-epoch
histories. The selected checkpoint minimizes validation Brier over the entire
completed trajectory; it may precede the last training epoch. There are also
six fresh forest candidates: 100 trees, depths 8/15/unrestricted, for 3×3 and
5×5 inputs. The final report compares 26 selected model/kernel combinations.

An epoch is one pass over all native contact training rows and **one AdamW
optimizer step**, with chunked gradient accumulation. Neural regularization
includes weight decay, optional dropout, and gradient norm clipping at 10.
The searched widths are 8/16/32/128; depths are 1/2/3/4; dropout is 0 or 0.15;
weight decay ranges from 0 to 0.1. The exact joint configurations are defined
in [candidate_plan](wildfire/search.py)
and frozen into the run's protocol. This is a designed joint search rather
than the full Cartesian product of those parameter values.

Run from the workspace root in the compatible Python 3.12 environment. Use
`--device cpu` when MPS is unavailable. The `run` command carries out neural
training, random-forest fitting and final comparisons in sequence. The `smoke`
command exercises the same workflow with small verification budgets and saves
its report under
`runs/20261009_unsigned_kernel_smoke_weighted_stratified_categorical_balanced/`.
The historical original-split smoke report: `runs/20261009_unsigned_kernel_smoke/report.md` (historical file not included in this checkout)
records the earlier execution check; it does not describe a weighted-split run
or establish full-budget performance.
The `train`, `forests` and `finalize` subcommands expose the individual stages;
append `--help` to inspect their arguments.

You can rerun the verification separately:

```sh
.venv/bin/python -m wildfire search smoke --device mps
```

Use `--output /absolute/path/to/new_run` for an independent experiment.
Rerunning the same full command resumes committed optimizer states on the
same device and skips completed candidates. It checks input and source
hashes and rejects changes to the seed, epoch budgets, or selected checkpoints.
Use a new output directory after changing data, code, or training settings.
For example, `--epochs 1000 --finalist-epochs 10000 --seed 19 --output
/absolute/path/to/new_run` creates a separate longer run. Forest fitting uses
the optional `baseline` dependency; it is available in the current environment
and can be installed into another compatible environment with `pip install
-e '.[baseline]'`.

The full command defaults to
`runs/20261009_unsigned_kernel_search_weighted_stratified_categorical_balanced/`
and generates its
weighted-split experiment report (`runs/20261009_unsigned_kernel_search_weighted_stratified_categorical_balanced/report.md`),
frozen search protocol (`runs/20261009_unsigned_kernel_search_weighted_stratified_categorical_balanced/protocol.json`),
and learning curves (`runs/20261009_unsigned_kernel_search_weighted_stratified_categorical_balanced/learning_curves.png`).
Those full-run artifacts will be available after the run completes. They
record the exact configuration grid, completed epochs, regularization,
validation selection and held-out evaluation. “Best” means best validation
score among the searched configurations, rather than an optimum over all
possible architectures or hyperparameters. Train-only normalization and
declared partition memberships remain frozen. Validation measures held-out
cell-hours within development fires; test measures the original held-out fires.
Comparison metrics use the same contact-conditioned target rows for every
model; no-contact neighborhoods remain supported by full-grid inference.

The output directory also contains:

| File or directory | Contents |
|---|---|
| `best_models.json` | Best searched hyperparameters, selected epoch, checkpoint path and SHA-256 for each family/kernel size |
| `selection.json` | The selected model/kernel combinations and overall validation winner; test never selects a model |
| `candidates/<id>/checkpoint.pt` | Selected neural parameters, input contract and frozen training-only normalization |
| `candidates/<id>/last.pt` | Last committed model, AdamW and CPU/device RNG states for continuation |
| `candidates/<id>/history.json` | Every epoch's matched and native training/validation Brier, gradient/parameter norms and selection decisions |
| `forests/` | Fitted forest parameters and their saved preprocessing, search settings and validation scores |
| `metrics.json`, `metrics.csv` | Contact-conditioned Brier, AP, ROC AUC, PR AUC, clipped/exact NLL, F1/MCC, Bernoulli distances, KL and calibration |
| `classification_thresholds.json` | Independently selected native and matched validation thresholds, then held fixed on test |
| `predictions/` | Probabilities for all base rows, including no-contact rows, plus contact indices and common labels/weights/identities |
| `source_snapshot/`, `protocol.json` | Exact executed source copies, frozen configuration, source/cache hashes and data provenance |
| `partition_verification.json` | Exact cell-hour separation and test-fire exclusion checks; training/validation fire overlap is reported explicitly |
| `complete.json` | Successful completion and integrity checks; created after all evaluation/report stages pass |

Load a selected kernel without fitting any preprocessing:

```python
import json
from pathlib import Path
from wildfire.inference import load_trained_model

run = ROOT / "runs/20261009_unsigned_kernel_search_weighted_stratified_categorical_balanced"
best = json.loads((run / "best_models.json").read_text())
selected = load_trained_model(best["mlp_k5"]["checkpoint"], device="cpu")
prediction = selected(
    burned_area, environmental_data,
    channel_names=selected.channel_names,
    burned_area_valid=burned_area_valid,
    feature_valid=feature_valid,
    dt_hours=1.0,
)
```

`burned_area` has shape `[..., 1, H, W]`; `environmental_data` has shape
`[..., C, H, W]` in the saved channel order. The two optional masks are boolean
tensors matching those inputs. Use raw environmental values; the saved model
applies its frozen normalization. Known complete no-contact neighborhoods
produce valid zero probabilities; missing context remains unavailable.

Training and native metrics use at least one already-burned off-center source
inside the model's K×K support. The fair cross-kernel comparison uses the same
original 9×9 cache rows with a burned neighbor inside centered 3×3. Its original
inverse inclusion weights are preserved. Native scores across different kernel
sizes describe different populations and should not rank those sizes directly.

An epoch-wise double-descent claim requires a held-out error curve that falls,
then rises, then falls again during training. A capacity-wise double-descent
claim requires an analogous pattern across model capacity under comparable
training conditions. Grokking refers to delayed generalization after the
training task has already been learned. Longer training and regularization
make these patterns inspectable; they do not guarantee that either pattern
appears. Assess those claims from the full run's curves and report after
completion; smoke training cannot establish delayed generalization.

### 7.4 Compare higher learning rates and schedules in a fresh run

The separate [scheduled search](wildfire/search.py)
compares peak learning rates **0.001, 0.003, 0.01, and 0.03** under constant
and warmup/cosine schedules. It uses the weighted default cache and a fresh
output directory. Historical original-split outputs and their frozen source
snapshots remain preserved:

```sh
PYTORCH_ENABLE_MPS_FALLBACK=1 OPENBLAS_NUM_THREADS=1 \
.venv/bin/python -m wildfire search-scheduled run \
  --device mps \
  --learning-rates 0.001 0.003 0.01 0.03 \
  --schedules constant warmup_cosine \
  --warmup-epochs 32 \
  --minimum-lr-factor 0.01 \
  --epochs 512 \
  --finalist-epochs 4096 \
  --seed 7
```

Each of the original ten architecture/regularization configurations at each
kernel size is crossed with all four peak rates and both schedules: **320
fresh kernel candidates**, plus six forest candidates. Each candidate uses
the same data, weighted normalization, nominal weight decay, dropout and
seeded initialization as the other rate/schedule variants of its fixed base
configuration. The per-variant initialization fingerprint is saved. This
isolates rate/schedule changes within each base configuration rather than
confounding a larger rate with a different network or dropout setting.

| Schedule | Exact behavior |
|---|---|
| `constant` | Uses the specified learning rate for every optimizer step |
| `warmup_cosine` | Increases from peak/32 at step 1 to the peak at step 32, then decays with a cosine to 1% of the peak at step 4,096 |
| `warmup_cosine_restarts` | Optional: after warmup, repeats 512-step cosine cycles from peak to floor, then returns to peak; optimizer moments and model parameters are retained |

To include restarts, use `--schedules constant warmup_cosine
warmup_cosine_restarts --restart-period 512`. This expands the initial search
to 480 candidates. You may explicitly select fewer schedules or rates for a
smaller experiment. Use a new `--output` directory after changing settings.

The scheduling horizon is fixed at `--finalist-epochs` **before the first
step** of every candidate. Continuing a selected candidate after its first
512 epochs keeps the same schedule; it does not restart warmup or stretch a
previously completed cosine. All training budgets still complete without
early stopping. History records the actual learning rate and optimizer-step
number for every epoch. The selected checkpoint and resumable state retain
the complete schedule configuration.

Results are saved under
`runs/20261009_scheduled_learning_rate_search_weighted_stratified_categorical_balanced/`.
The new report includes controlled comparisons at the same initial epoch
budget, full finalist learning curves and actual learning-rate curves, in
addition to the usual selected parameters, full prediction arrays and native/
matched evaluation metrics. The scheduled full experiment is for you to run;
short execution checks do not establish which rate or schedule performs best.
The default continues one selected candidate per neural family to 4,096
epochs; it does not extend every constant/cosine pair to that budget. Late
improvement during a changing learning rate alone does not establish grokking.
The same-budget rate/schedule comparison is the first-stage comparison.

For a short real-data execution check:

```sh
.venv/bin/python -m wildfire search-scheduled smoke --device mps
```

Smoke verification uses 2 initial epochs, a fixed 4-epoch horizon, 1 warmup
epoch and 2-step optional restart cycles. Its default output is
`runs/20261009_scheduled_learning_rate_smoke_weighted_stratified_categorical_balanced/`.
Its report explicitly marks its scores as execution checks. The full default
retains 512/4,096 epochs.

The [historical original-split diagnostic](documents/kernel_training_diagnostic_20261009/report.md)
shows that the original completed long runs continue reducing training Brier
while validation Brier worsens. Continued training improvement does not prove
the learning rate is too small. The fresh search measures whether larger rates
or scheduling improve optimization and validation on held-out cell-hours. In
AdamW, per-step weight decay multiplies parameters by `1 - actual_lr *
weight_decay`, so keeping nominal weight decay fixed does not make integrated
shrinkage identical across different rates or schedules.

### 7.5 Mixed kernels: combine rates before the exponential

The [mixed model](wildfire/models.py)
jointly learns independent environmental CNN branches at **3x3, 5x5, 7x7,
and 9x9**, plus one global nonnegative coefficient for each branch. The
coefficients have an unrestricted sum, as requested. Let `B[i+delta]` be the
current binary cumulative burned state at a source offset, and let
`K[k,i,delta] >= 0` be the hourly rate generated by branch `k` for target `i`.
Every branch fixes its center coefficient to zero. For a known currently
unburned target, the model computes:

```text
r[k,i] = sum_delta K[k,i,delta] * B[i+delta]
alpha[k] = softplus(mixing_logit[k])
lambda[i] = sum_k alpha[k] * r[k,i]
q[i] = 1 - exp(-lambda[i])                  # one-hour prediction
```

The linear combination therefore acts on the **convolution rates before one
exponential**. The branch probabilities are not averaged. Branch kernels and
mixing coefficients are trained jointly. At initialization, overlapping
offsets share their contribution so the combined 9x9 effective kernel starts
at the same uniform offset rate as the fitted global baseline; four branches
do not multiply that initial rate by four.

Run the new search from the project root:

```sh
PYTORCH_ENABLE_MPS_FALLBACK=1 OPENBLAS_NUM_THREADS=1 \
.venv/bin/python -m wildfire search-mixed run \
  --device mps \
  --learning-rates 0.001 0.003 0.01 0.03 \
  --schedules constant warmup_cosine \
  --warmup-epochs 32 \
  --minimum-lr-factor 0.01 \
  --epochs 512 \
  --finalist-epochs 4096 \
  --seed 7
```

This fresh search retains the previous 320 single-scale configurations and
adds **24 mixed candidates**: three CNN settings, four peak learning rates,
and two schedules. The mixed settings use hidden widths 16/32/64, dropout
0/0.15/0.15, and AdamW weight decay 0.0001/0.001/0.01, respectively. Every
branch in a mixed candidate uses that candidate's width and dropout. All
344 candidates complete 512 epochs. One validation-selected finalist per
neural family, now **five including mixed**, continues to 4,096 epochs.
No early stopping is used. Six forest candidates remain separate baselines.
Adding `warmup_cosine_restarts` to `--schedules` yields 516 kernel candidates.
The fixed horizon, saved optimizer/RNG state, and actual-rate history follow
the scheduling contract in section 7.4.

Mixed training and native evaluation use contact within the **union 9x9
support**. The matched comparison still uses exactly the same centered
3x3-contact rows for every model. All prediction rows, including no-contact
rows, are saved. The mixed model returns zero for known no-contact inputs,
and retains unknown source/environment masks. Its complete environmental
availability range is 9x9. Smaller branches use their own centered patches.

Results go to
`runs/20261009_mixed_kernel_search_weighted_stratified_categorical_balanced/`.
The search saves 27 selected models (24 single-scale, one mixed, two forest),
their best searched configurations/checkpoints, native/matched metrics,
classification thresholds selected on validation, and all-row predictions.
`best_models.json["mixed_k9"]` records the mixed checkpoint, branch sizes,
and selected mixing coefficients; `k9` denotes the largest support.
Histories retain every epoch's coefficients, and `mixing_weight_curves.png`
shows the extended mixed finalist. The equal-budget rate/schedule table uses
only the first 512 epochs for every candidate.

Saved mixed checkpoints load through the existing public interfaces:

```python
from wildfire import WildfireModel
from wildfire import load_trained_model

forecast = WildfireModel.from_checkpoint(mixed_checkpoint_path, device="cpu")
predictor = load_trained_model(mixed_checkpoint_path, device="cpu")
```

Both loaders use the saved channel order and normalization; no preprocessing
is refitted. The heat integration also accepts this checkpoint architecture.
The model, loader and search are additive files, preserving the earlier
searches' frozen source hashes and saved results.

For a reduced real-data execution check:

```sh
PYTORCH_ENABLE_MPS_FALLBACK=1 OPENBLAS_NUM_THREADS=1 \
.venv/bin/python -m wildfire search-mixed smoke --device mps
```

The short check defaults to
`runs/20261009_mixed_kernel_smoke_weighted_stratified_categorical_balanced/`
and uses two initial epochs, four finalist epochs, and reduced trees/data.
Its report marks the scores as execution verification. The full
512/4,096-epoch experiment is for the user to run. Learned mixing coefficients
alone are not uniquely interpretable scale importance: changing a branch's
rate amplitude and inversely changing its coefficient preserves the combined
rate. The finite single-seed search does not establish a global optimum,
grokking, or double descent.

### 7.6 Additional neural combiner over multiscale convolution outputs

The [neural mixed model](wildfire/models.py)
uses the same four independent kernel branches and passes their **raw
convolution rates** to a small neural network. It returns one combined
nonnegative rate, with exact zero when all four branch inputs are zero.
For `r = (r[3], r[5], r[7], r[9])`, its exact readout is:

```text
f_theta(r) = Linear(hidden -> 1)(Dropout(SiLU(Linear(4 -> hidden)(r))))
lambda = (r[3] + r[5] + r[7] + r[9]) * softplus(f_theta(r))
q = 1 - exp(-lambda)                       # one-hour prediction
```

Multiplying the positive scalar response by the total raw rate gives a
smooth zero-preserving readout; a learned bias cannot create a new-burn rate
when every branch rate is zero. All branch and combiner parameters train
jointly. The final affine output starts at a constant unit gain, and branch
offsets account for overlap, so its initial combined rate matches the same
global uniform-offset baseline as the linear mixed model. The combiner has
one hidden layer, with widths 8, 16, or 32 in the search. It reads raw rates,
not probabilities. This neural combination permits nonlinear interactions
and does not impose monotonicity in the branch rates.

Use the combined search to compare **both** multiscale models with the
single-scale models. This example chooses peak learning rates 0.01 and 0.1;
replace them with any nonempty list of distinct, finite, positive rates:

```sh
cd "/Users/movinggk/Documents/영재멘토/wildfire"

PYTORCH_ENABLE_MPS_FALLBACK=1 OPENBLAS_NUM_THREADS=1 \
.venv/bin/python -m wildfire search-multiscale run \
  --cache runs/20261009_weighted_stratified_split/prepared_all \
  --output runs/20261010_categorical_balanced_benchmark \
  --run-policy auto \
  --device mps \
  --learning-rates 0.01 0.1 \
  --schedules constant warmup_cosine \
  --warmup-epochs 32 \
  --minimum-lr-factor 0.01 \
  --epochs 512 \
  --finalist-epochs 4096 \
  --categorical-balance inverse-sqrt \
  --categorical-balance-min-frequency 0.001 \
  --categorical-balance-max-factor 10 \
  --forest-trees 100 \
  --seed 7 \
  --threads 4
```

In a multiline shell command, each continuation is a **single backslash as
the final character on its line**, with no spaces or other characters after
it. Use `--device cpu` if MPS is unavailable.

The direct multiscale command accepts three run policies:

| `--run-policy` | Behavior |
|---|---|
| `auto` (default) | Resumes when the full configuration, input cache, training code, and training device match. A changed request uses an independent deterministic sibling directory named `<output-name>__config_<12hex>`. Repeating that changed request resumes its matching directory. |
| `resume` | Requires the requested experiment to match its saved configuration and integrity bindings; a change is rejected. |
| `new` | Starts a fresh experiment for that invocation, preserving earlier results. The `run` stage uses that same fresh directory for neural training, forest fitting, and finalization. |

The command prints the **actual output directory** before executing the
selected stage. Keep that path when continuing a run or using its individual
`train`, `forests`, and `finalize` stages for a full experiment. When you keep
the same requested `--output`, returning to a previously used configuration
resumes its matching original or sibling directory, provided the cache,
training code, and device still match. Automatic routing preserves earlier
protocols, checkpoints, and reports; it does not merge configurations or relax
the integrity checks of an existing experiment.

For a new experiment, setup checks every environmental source listed in the
cache manifest against its frozen SHA-256 hash. It first tries the complete
`data/environment` directory in the current
checkout, then falls back to the cache's recorded `data_root`. It accepts a
root only when all listed files exist and match; it does not combine partial
copies or change the expected hashes. The new `protocol.json` records the
accepted absolute path as `verified_data_root`. This source-location check
preserves the prepared cache bytes, labels, and original sampling weights.

There are 46 fixed kernel/architecture/regularization settings, each crossed
with the supplied rates and schedules. The two-rate, two-schedule example
therefore trains **184 kernel candidates**. With the default four rates
`0.001 0.003 0.01 0.03` and two schedules, the grid contains 320 single-scale,
24 linear mixed, and 24 neural mixed candidates. The neural mixed candidates
use these joint regularization settings:

| Branch hidden width | Branch dropout | Combiner hidden width | Combiner dropout | AdamW weight decay |
|---:|---:|---:|---:|---:|
| 16 | 0 | 8 | 0 | 0.0001 |
| 32 | 0.15 | 16 | 0.10 | 0.001 |
| 64 | 0.15 | 32 | 0.15 | 0.01 |

All kernel candidates complete 512 epochs in this example. One validation-selected
candidate in each of six neural families continues to 4,096 epochs without
early stopping. Six forest candidates are fitted as before. The default
four-rate grid has **368 kernel candidates**; adding cosine restarts to that
grid gives 552. Scheduling horizons, continuation,
validation-only selection, and the equal first-stage comparison follow the
same contract as section 7.4.

Results go to the printed output directory. When `--output` is omitted, the
requested default is
`runs/20261009_multiscale_kernel_search_weighted_stratified_categorical_balanced/`.
The final comparison saves **28 selected models**: 24 single-scale, one
linear mixed, one neural mixed, and two forest models. The new selection is
`best_models.json["neural_mixed_k9"]`; its checkpoint saves every branch and
combiner parameter, their configuration, selected epoch, and frozen channel
normalization. Reports retain native/matched metrics, calibration, validation
thresholds, same-budget rate/schedule comparisons, all-row predictions, and
the six extended learning/rate trajectories. The linear mixed coefficient
history remains available separately.

The neural rate depends nonlinearly on the current burned-source pattern, so
it has no combined offset kernel determined by environmental inputs alone.
Inspect `branch_kernel_rates` for the independent kernels,
`branch_convolution_rates` for their burned-state rate maps, and the returned
prediction's `rate` for the neural combination. Calling its `kernel_rates`
method without burned inputs raises an explicit error. Center-patch methods
and `combined_rate` also expose the intermediate calculation.

Training and native evaluation use the union 9x9 contact range. The matched
comparison retains the identical current 3x3-contact rows, and predictions
still cover no-contact inputs with structural zero. Public model loaders,
save/reload, and heat integration accept the new checkpoint without fitting
preprocessing. Earlier scheduled and linear mixed source snapshots and results remain
in their saved experiment directories; current implementations share
`models.py`, `inference.py` and `search.py`.

For a reduced real-data execution check, replace `run` with `smoke`; its default
output is
`runs/20261009_multiscale_kernel_smoke_weighted_stratified_categorical_balanced/`.
The full 512/4,096-epoch search is for the user to run; reduced execution-check
scores do not establish model performance or a globally best parameter setting.

For a copied checkout on another machine, use the portable entry point. It
finds the original prepared cache in `runs` and environmental data in
`data/environment` relative to the installed module location, verifies every source hash, and creates a separate
cache with the current root. No absolute macOS or Linux path is required:

```sh
.venv/bin/python -m wildfire search-portable run \
  --device auto \
  --learning-rates 0.001 0.003 0.01 0.03 \
  --schedules constant warmup_cosine \
  --warmup-epochs 32 \
  --minimum-lr-factor 0.01 \
  --epochs 512 \
  --finalist-epochs 4096 \
  --seed 7
```

`auto` selects available CUDA, then MPS, then CPU. Explicit `--device cuda`,
`--device mps`, and `--device cpu` are supported; an unavailable explicit backend
fails before creating a cache. The entry configures MPS CPU fallback before
importing PyTorch, and sets an OpenBLAS thread default of one, preserving any
explicit environment values. CUDA/MPS require a compatible PyTorch build and
hardware; CPU supports machines without those GPUs. Use a Python 3.12 environment
created on each machine rather than copying a virtual environment between OSes.
On Windows, invoke `.venv\Scripts\python.exe`, or activate the environment and
use this platform-neutral one-line command:

```text
python -m wildfire search-portable run --device auto
```

Copy the original `prepared_all` cache and the complete original
`data/environment` directory with the project. The portable launcher verifies
the four original cache hashes and all 486 relative source-file hashes. It copies
the three NPZ files byte-for-byte and changes only `metadata.data_root`, saving
`relocation.json` in the clone. Labels, sampling weights, channel schema, split
definitions, source hashes, the original cache, and frozen training sources are
preserved. Relocation does not inspect held-out array values. A missing or
changed source must be replaced by its matching original file; do not disable
integrity checking or overwrite the expected hash.

The clone goes under `9x9/prepared_portable/<data-root-path-id>/`. Default full-run
outputs go under
`runs/20261009_multiscale_kernel_search_<device>_categorical_balanced_portable/<cache-path-id>/`.
Smoke outputs use `kernel_smoke` instead. These path-derived subdirectories
prevent a copied project from reusing a protocol bound to another cache location.
The resolved cache and output paths are printed before training. Repeating the
same command on the same machine verifies the clone and resumes the same run.
An MPS optimizer checkpoint cannot resume on CUDA under the existing same-device
contract; a different backend starts a separate experiment.

For data kept outside the checkout, use `--data-root /path/to/data/environment`
and `--cache /path/to/original/prepared_all`. `--portable-cache` and `--output`
override the clone and experiment destinations. Explicit output directories must
still match any existing frozen protocol. Use `smoke` in place of `run` for a
short end-to-end execution check, or use `--check-only` to verify relocation and
the full experiment setup without training.

The `python -m wildfire relocate-cache` command also supports
manual relocation with `--data-root`, `--source-cache`, and `--output-cache`.
Its default output is `9x9/prepared_relocated`; use that new cache with a fresh
experiment output directory because the root replacement changes metadata SHA.

## Data, tensors and model contracts

<a id="data-guide"></a>

The published archive supplies arrival-time and kriging-standard-deviation
rasters for **15 Korean and 29 U.S. fires**. Each reconstructed cumulative burned
state is obtained by comparing estimated arrival time with the snapshot time
inside the known final perimeter. Arrival origins are event-specific and recorded
in metadata. The data reconstruct burning order within that perimeter; they do
not establish spread beyond it. Read NoData from raster metadata: some valid U.S.
arrival times are negative.

The Korean matching-event internal timing MAEs are approximately 7.7–12.2 hours;
kriging standard deviations are model-based uncertainty, not calibrated confidence
intervals. Regional area tables count valid 375 m supports at 14.0625 ha per cell;
these approximate raster areas need not equal administrative forest-damage areas.
Hourly masks use `1` estimated burned, `0` estimated not yet burned inside the
reconstruction mask, and `255` unavailable. Origins and UTC/KST band tags remain
in the regional metadata. These products are not independent validation against
the satellite detections used to construct them.

<a id="environment-guide"></a>
<a id="biome-guide"></a>

Environmental inputs retain the original rectangular 375 m grid, affine transform
and CRS: EPSG:5179 in Korea and EPSG:5070 in the U.S. Environmental rectangles are
not masked to the future final burned perimeter. Native information scale remains
that of each source: roughly 9 km hourly IFS weather, 0.25° hourly ERA5 mixing
depth, daily roughly 4 km gridMET fuel moisture, and finer static terrain/vegetation
products. U.S. LANDFIRE fuel layers and global RESOLVE biome classes retain their
coverage masks. Resampling does not create finer observations. Biome has a fixed
14-class one-hot representation; the loader's full default schema expands
72 source fields into 741 channels. The fitted models here use a 19-channel subset.

Rain/precipitation amounts describe the preceding hour, and shortwave radiation
is a preceding-hour mean. Rolling rain totals use 24, 168 and 720 hours; missing
intervals invalidate a total. gridMET days end at 07:00 UTC. Meteorological wind
direction is the direction from which wind blows, clockwise from geographic north;
east/north components are `u = -speed sin(direction)`, `v = -speed cos(direction)`.
Projected terrain directions require the corresponding grid-convergence treatment.

Categorical classes use mode aggregation; numeric coverage and height use valid-pixel
area-weighted averages. Biome labels use polygon membership at pixel centers and
preserve uncovered cells. The published biome legend and per-fire coverage remain
in the files linked below. FCCS fuel loading is looked up at native 30 m pixels
before aggregation; unmatched and zero-coded fuelbeds remain missing. Relative
humidity, canopy height and vegetation-continuity proxies are not measured dry fuel
mass or live/fine fuel moisture. Static source epochs and missingness remain part
of the interpretation.

### Load a custom sequence for exploration

<a id="loader-guide"></a>

This example follows Step 3 and selects two raw environmental fields without
binding them to a fitted model:

```python
from wildfire import load_data

with load_data(
    DATA_ROOT,
    events=[EVENT],
    sequence_length=2,
    time_range=(CUTOFF, "2024-08-23T01:00:00Z"),
    channels=["weather.temperature_2m", "terrain.slope_degrees"],
) as dataset:
    sequence = dataset[0]
    print(tuple(sequence["features"].shape))  # (2, 2, 103, 73)
```

This custom schema is for exploration or a model trained on those inputs. It is
not compatible with the saved 19-channel checkpoint. For batching with that
checkpoint, reuse its saved schema:

```python
from torch.utils.data import DataLoader
from wildfire import collate_fire_sequences

with model.load_data(DATA_ROOT, **selection) as dataset:
    loader = DataLoader(
        dataset, batch_size=1, shuffle=False, num_workers=0,
        collate_fn=collate_fire_sequences,
    )
    batch = next(iter(loader))
batch_probability, batch_coordinates = model.predict_sample(batch)
print(tuple(batch_probability.shape))  # (1, 1, 1, 103, 73)
print(tuple(batch_coordinates.shape))  # (1, 103, 73, 2)
```

| Object | One sequence | Collated batch |
| --- | --- | --- |
| Environmental values and mask | `[T, C, H, W]` | `[B, T, C, H, W]` |
| Burned state, its mask and prediction | `[T, 1, H, W]` | `[B, T, 1, H, W]` |
| WGS84 `(latitude, longitude)` coordinates | `[H, W, 2]` | `[B, H, W, 2]` |
| Heat integration input | One snapshot with singleton leading dimensions | Select one snapshot before heat integration |

Here `T` is time steps, `C` environmental channels, `H` rows, `W` columns and `B`
batch size. `time_valid` distinguishes padded time steps; `pixel_valid` describes
spatial padding, not observation coverage. Coordinates remain fixed across valid
and padded time steps; `batch_coordinates[b, row, column]` locates the cell for
`batch_probability[b, t, 0, row, column]` at each time index `t`.
Environmental and burned-state masks describe their respective known values.
Daily fields default to the most recent
completed source day, rather than a future-containing daily average. That rule
does not establish real-time publication availability. Daily and static fields
do not become new hourly observations when repeated across a sequence.

`feature_quality` distinguishes source-out-of-range (1), source-missing (2), absent
channel (3), spatial padding (4), time padding (5), and unknown category (6);
zero denotes valid data. Flagged negative source soil-moisture values remain in
the raw records and are rejected by the loader's validity masks. New numeric
rasters use NoData −9999; original arrival rasters retain their source convention.
One-hot groups have one active class and all class masks true at known pixels;
missing groups have all-zero indicators and false masks. Numeric fill zero alone
does not determine validity. `source_interval_start_utc` and
`source_interval_end_utc` record dynamic support in Unix seconds.

### Probability model definitions

<a id="probability-guide"></a>

The exponential family produces nonnegative environmental-neighborhood rates
for neighboring burned cells. Let $i$ index target cells, $\delta$ range over
offsets within the configured kernel, and $E$ denote the current environmental
inputs. For known current cumulative burned state $B_i\in\{0,1\}$,

$$
\lambda_i=\sum_{\delta\ne0}k_{i,\delta}(E)B_{i+\delta},
\qquad k_{i,\delta}\ge0,
\qquad p_i=(1-B_i)\bigl(1-e^{-\Delta t\lambda_i}\bigr).
$$

Rates are in h⁻¹ and $\Delta t$ is in hours. The trained endpoint is exactly one
hour. Other exponential horizons rescale the frozen rate mathematically and have
not been independently trained or validated as other forecast endpoints.

The supported kernels are nonnegative. The center contribution is zero, and
learned parameters are shared across locations while each kernel depends on
that location's environmental neighborhood. Current cumulative burned cells
are source indicators; they do not identify an active flame front. Unknown
context and unknown boundaries can invalidate a prediction.

All training and evaluation comparisons condition on an unburned target with
at least one current burned neighbor within the model's kernel. A shared
comparison cohort must satisfy that requirement for every compared kernel and
must have adequate context for every compared model. Native cohorts differ by
kernel and are reported separately; their scores cannot be compared as if they
used identical targets.

At inference, a known-unburned target with a complete, all-unburned source
neighborhood receives a valid probability of zero when the required input
context is available. Every source indicator is zero, so the
exponential rate is zero. This structural result is retained even when
the saved training contract requires burned-neighbor contact; it is not a new
empirical calibration result. These cells are excluded as training targets;
training still uses only eligible patches with at least one burned neighbor.
The structural-zero inference rule adds no training samples or loss terms.
Having no *known* burned neighbor is insufficient
when one or more source states are unknown. Such cells retain their unknown
prediction, as do unknown boundaries under `boundary="unknown"`.

The offset convention is cross-correlation: coefficient `(dy, dx)` multiplies
`B[row + dy, column + dx]`, without reversing the kernel. Increasing an exponential
horizon freezes the current source map and rate; one call does not propagate
through newly burned intermediate cells. There is no spontaneous-ignition term.
`boundary="zero"` explicitly assumes outside-raster zeros in the model input
space; standardized environmental zero need not be raw physical zero. Interior
missing values remain unknown under either boundary setting. An exponential
prediction can be known zero for an already-burned cell even when its rate is
unavailable, so `valid` and `rate_valid` need not agree.

### Bitmap exports

<a id="bitmap-guide"></a>

The existing bitmap bundle has 1,380 BMP files with geographic sidecars. For
categorical burned masks, palette indices are `0` unburned, `1` burned and `255`
NoData; RGB intensities are not those categorical values. Continuous images are
quantized displays, with exact values in `.values.npy`. World files use
upper-left **pixel-center** coordinates; `.coordinates.npz` retains projected
`x`, `y`, longitude and latitude arrays. With world-file coefficients written as
`A, D, B, E, C, F`, zero-based row `i` and column `j` have center coordinates
`x = A*j + B*i + C`, `y = D*j + E*i + F`. The `.prj` file records the CRS, and
each image's JSON records its palette, numeric range, source and timestamp.
Read exact continuous values from `.values.npy` and validity from index 255;
do not infer validity from the sign of an arrival value. The [bitmap catalog](data/bitmaps/catalog.csv)
and [export manifest](data/bitmaps/manifest.json) retain the
complete file inventory and verification details.

## Saved results and their limits

<a id="completed-reports"></a>

The active saved-model example uses the nonnegative exponential 5×5 checkpoint
from the 2026-10-07 kernel sweep. That sweep compared exponential 3×3, 5×5,
7×7, and 9×9 kernels on a common weighted cohort with complete 9×9 context
and current burned-neighbor contact within its central 3×3 support. Every
scored target therefore has a burned neighbor within every compared kernel.
The shared validation cohort contains three U.S. fires and no Korean fires;
the shared test cohort contains eight fires. Kernel size was selected using
validation.

| Model | Common validation Brier ↓ | Common test Brier ↓ | Common test exact log loss ↓ |
| --- | --- | --- | --- |
| Exponential 3×3 reference | 0.018686 | 0.067219 | 0.242273 |
| Exponential 5×5, selected within its family | 0.018592 | 0.069587 | 0.249690 |

The validation-selected 5×5 model has higher test Brier than the 3×3 reference.
Native populations differ by kernel, and changing both training population and
capacity prevents isolating a causal effect of kernel size. These historical
scores do not establish performance for a newly trained model.

The signed direct-convolution model is retired from the active API, training
commands, defaults and demonstrations. Loading an old signed checkpoint raises
an explicit retirement error. Its earlier experiment records and rendered
outputs are preserved as historical evidence; they are not current deployment
recommendations.

| Experiment | Saved report |
| --- | --- |
| <a id="report-five-input"></a>Five continuous inputs, 3×3 | Training report: `runs/20261007_1h_contact_only/report.md` (historical file not included in this checkout) |
| <a id="report-biome-3x3"></a>Pooled biome one-hot inputs, 3×3 | Training report: `runs/20261007_1h_biome_onehot_pooled/report.md` (historical file not included in this checkout) |
| <a id="report-exponential-kernels"></a>Exponential four-kernel comparison | Common-cohort report: `runs/20261007_1h_kernel_sweep/comparison_report.md` (historical file not included in this checkout) |
| <a id="report-exponential-5x5"></a>Exponential 5×5 | Native training report: `runs/20261007_1h_kernel_sweep/5x5/report.md` (historical file not included in this checkout) |
| <a id="report-exponential-7x7"></a>Exponential 7×7 | Native training report: `runs/20261007_1h_kernel_sweep/7x7/report.md` (historical file not included in this checkout) |
| <a id="report-exponential-9x9"></a>Exponential 9×9 | Native training report: `runs/20261007_1h_kernel_sweep/9x9/report.md` (historical file not included in this checkout) |
| Retired signed experiment, historical | Original paired report: `runs/20261007_1h_direct_convolution_signed/comparison_report.md` (historical file not included in this checkout) |
| <a id="report-published-baseline"></a>Published-family random forest, historical | Original baseline report: `runs/20261009_huot_random_forest_baseline_extended/report.md` (historical file not included in this checkout) |

The original random-forest report adapts the neighborhood random forest from
[Huot et al. (2022), *Next Day Wildfire Spread*](https://arxiv.org/abs/2112.02447)
to one-hour cumulative burned transitions. Its source records explain the
changes in target, weighting and spatial inputs; published numerical scores
are not imported. It includes a retired signed reference, so its numerical
ranking is historical.

Brier and exact Bernoulli log loss are the primary probability scores. Exact
log loss is infinite when a positive-weight observed outcome receives zero
probability. The floored log loss is a separately labeled diagnostic. For
binary outcome labels, empirical Bernoulli KL equals exact log loss.
Classification thresholds for F1 and MCC must be selected on validation and
then held fixed on test. Average precision and trapezoidal PR AUC are distinct
metrics. Additional Bernoulli distances remain in the full saved reports.

The random forest also provides an importable patch prediction interface:

```python
import numpy as np
from wildfire.models import PatchRandomForest

RUNS = ROOT / "runs"
forest = PatchRandomForest.load(
    RUNS / "20261009_huot_random_forest_baseline_extended/rf_5.joblib"
)
with np.load(RUNS / "20261009_weighted_stratified_split/prepared_all/test.npz") as cache:
    probability = forest.predict_probability(
        cache["environment"][:3], cache["burned"][:3],
        channel_names=forest.channel_names, dt_hours=1.0,
    )
assert probability.shape == (3,)
```

The forest's `fit`, `predict_probability`, `save` and `load` preserve channel
order, feature positions and the one-hour contract. The kernel-search interface
and its new experiment report document current candidate selection and learning
curves; historical scores above are never reused as newly trained results.

## Commands, files and source records

<a id="workflows"></a>
<a id="organization"></a>

`python -m wildfire --help` lists all workflows. After
installation, `wildfire` is equivalent. Append `--help` to an individual command
to inspect its arguments before an acquisition, reconstruction or new experiment.
For alternatives separated by `/` in the table, reuse the full
`python -m wildfire` prefix for each subcommand.

| Task | Command |
| --- | --- |
| Inspect an aligned sequence | `python -m wildfire load --events KFS_01 --sequence-length 2 --batch-size 1` |
| Prepare / filter training data | `python -m wildfire prepare --help` / `filter-contact --help` |
| Train the exponential model | `python -m wildfire train --help` |
| Search kernel learners, refit forests and finalize comparisons | `python -m wildfire search --help` |
| Compare saved exponential predictions | `python -m wildfire evaluate --help` |
| Generate reports | `python -m wildfire report --help` / `report-kernels --help` |
| Verify saved exponential runs | `python -m wildfire verify --help` |
| Environmental acquisition / validation | `python -m wildfire environment --help` |
| Biome acquisition / bitmap export / reconstruction | `python -m wildfire biome --help` / `bitmaps --help` / `build-bundle --help` |
| Integrated heat demonstration | `python -m wildfire heat --help` or `wildfire-heat --help` |

All workflows use the command interface above. Model loading, data access,
prediction, training and saving are exposed by `wildfire.api` and re-exported
from `wildfire`. Every machine learning model is defined in `wildfire.models`;
heat and flame calculations live in `wildfire.heat`. The [file map near the top](#simple-layout)
lists each maintained Python file and its job. Saved source snapshots inside
`runs` and publisher code inside `data/sources` retain their original names as
historical evidence.

This README is the maintained guide for the unified package. The overlapping
component guides have been removed. Saved experiment reports remain with their
runs, and the publisher's README and checksum manifest remain in the intact
extracted archive. Legacy content is excluded from this guide and from the
documentation cleanup. Detailed input inventories and coverage are available here:

| Subject | Source record or implementation |
| --- | --- |
| Hourly reconstruction and acquisition | [Regional catalog](data/catalog.csv), [source manifest](data/source_manifest.json), [archive checks](data/records/archive_validation.json) |
| Environmental products and coverage | [Event catalog](data/environment/catalog.csv), [requirements coverage](data/environment/requirements_coverage.csv), [source-quality checks](data/environment/physical_weather_range_checks.csv) |
| Biome classification | [Code/name/color legend](data/environment/biome_classes.json), [per-fire coverage](data/environment/biome_coverage.csv) |
| Tensor layout and channel schema | [Sequence loader](wildfire/data.py), [training input schema](wildfire/schema.py) |
| Fitted model contracts | [Exponential inference](wildfire/inference.py), [public API](wildfire/api.py) |
| Radiation, timing and fuel | [Physics source references](wildfire/heat_sources.json), [radiation operator](wildfire/heat.py), [timing conversion](wildfire/heat.py), [ecological loading](wildfire/heat.py) |

<a id="published-source-documents"></a>
<a id="source-readme"></a>
<a id="source-manifest"></a>

Published source: [Zenodo record 21788344](https://zenodo.org/records/21788344),
DOI [10.5281/zenodo.21788344](https://doi.org/10.5281/zenodo.21788344), by Chulhyun
Choi, Hyunjin Seo and Jaegyu Cha. The complete [publisher README](data/sources/zenodo_21788344/extracted/README.md)
is retained inside the archive; its identical separately downloaded copy has
been removed. The source manifest preserves the original download URL,
checksums and the current canonical path.
The [published manifest](data/sources/zenodo_21788344/extracted/MANIFEST.md)
retains all 131 file checksum entries. Derived source products are CC BY 4.0;
the publisher identifies its source code as MIT. Retain each environmental
provider's attribution and license when redistributing derived rasters.

For interactive exploration, use the [probability-map notebook](demonstration/probability.ipynb)
or the [integrated heat notebook](demonstration/heat.ipynb).
Notebook dependencies are optional:

```sh
python -m pip install -e '.[notebook]'
python -m jupyterlab demonstration/probability.ipynb
```

## Verification and common problems

<a id="verification"></a>
<a id="documentation-coverage"></a>

Run the active suite from the workspace root:

```sh
python -m pytest -q
```

For a focused check, use `python -m pytest tests/test_api.py -q`,
`python -m pytest tests/loader -q`, `python -m pytest tests/probability -q`,
or `python -m pytest tests/heat -q`.

The [unsigned demonstration verification](documents/unsigned_demo_validation.json)
records 97 passing focused API/heat tests and successful executions of the API,
burn-probability and heat notebooks. It verifies the supported saved exponential
checkpoint, retirement errors, new nonnegative-kernel dispatch, no-contact
prediction support and contact-conditioned notebook evaluation. It does not
claim that the full 512/4,096-epoch search has been run.

| Symptom | Check or correction |
| --- | --- |
| PyTorch 2.5.1 has no compatible wheel | Use Python 3.12 for the complete workspace; retain the pinned framework version. |
| A checkpoint/data path is missing | Start from the workspace root, or pass absolute artifact paths for an installed wheel. |
| Input channels are rejected | Load data with `model.load_data`; preserve the saved schema and supply raw physical values. |
| Predictions contain NaN | Inspect the validity masks and current neighborhood coverage; missing values are not zeros. |
| Heat is incomplete despite some valid predictions | Unknown emitting cells can affect every receiver; inspect known-source contributions and bounds. |
| A saved output or training directory already exists | Choose a new path; checkpoint overwrite requires explicit `overwrite=True`. |
| Worker or OpenMP shared-memory errors in a restricted runner | Use an execution environment that permits operating-system shared memory; use `num_workers=0` when worker processes are unavailable. |
| A sequence contains padded time steps | Use `time_valid` and observation masks; padded entries are not observations. |

The [API verification record](documents/api_validation.json) records the earlier
436-test result, both training paths, all twelve saved checkpoint comparisons,
installed-package checks and the reported shared-memory diagnosis. The
[refactor record](documents/refactor_validation.json) preserves the earlier
compatibility and artifact checks. The
[documentation integration record](documents/readme_integration.json) describes
the previous full-length README snapshot; its checksum is historical. The
[step-by-step guide verification](documents/readme_guide_validation.json) records
the preceding guide snapshot and its executed examples. The
[documentation cleanup record](documents/documentation_cleanup.json) maps removed
documents to their canonical sections or retained source file. Historical file
inventories keep their original hashes; the cleanup record explains intentional
documentation removals without resealing the earlier scientific evidence. Historical test
results and technical checks do not establish new forecasting or heat-measurement skill.
