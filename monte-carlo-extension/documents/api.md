# Wildfire API: complete option reference

Load data and a model independently, then select a time for prediction:

```python
from wildfire import load_data, load_model, select_time
from wildfire.schema import TRAINING_SOURCE_CHANNELS

EVENT = "WY-BTF-002416_FishCreek"
CUTOFF = "2024-08-23T00:00:00Z"
with load_data(events=[EVENT], channels=TRAINING_SOURCE_CHANNELS,
               sequence_length=None, patch_size=None) as data:
    timeline = data[0]  # Every available time for this event, in one sample.
sample = select_time(timeline, CUTOFF)
model = load_model()
result = model.predict(sample)
fig, ax = result.plot()
```

`result` contains probabilities, validity, rates and optional geographic
coordinates. Inference uses current state and environmental inputs; outcomes
are read only for comparison or evaluation. This reference lists the
complete workflow options. The detailed model, radiation, fuel and residence
classes remain available from `wildfire.models`, `wildfire.heat` and the public
`wildfire` package.

For recursive spread, explicitly enter prediction and evaluation durations:

```python
from wildfire import evaluate_cumulative

HORIZONS_HOURS = [1, 3, 6, 12]
EVALUATION_HOURS = [1, 3, 6]  # Each duration must already be simulated.
cumulative = model.predict_cumulative(
    sample, hours=HORIZONS_HOURS, method="recursive",
    n_samples=1024, seed=0, trajectory_batch_size=32,
    missing_burned_area="unburned", environmental_forecast=None,
    boundary="zero",  # Recursive default: unburned cells outside the rectangle.
)
new_burn_report = evaluate_cumulative(
    cumulative, timeline, hours=EVALUATION_HOURS,
    quantity="new_burn", coverage="shared", threshold=0.5,
)
total_burned_report = cumulative.evaluate(
    timeline, hours=EVALUATION_HOURS, quantity="burned", coverage="shared",
)
```

The recursive default initializes missing cutoff burned states as unburned
inside the actual grid. Environmental gaps, padding and unavailable reference
labels remain unavailable. `patch_size=None` retains the original rectangular
event grid. Newly ignited cells can spread fire in the following hour, and
`burned_probability` includes initial burns. Ordinary one-hour `predict()`
remains analytic. Recursive mode defaults to unburned exterior padding, so
complete rectangular inputs retain valid edge coverage as the horizon grows.
The sections below define sampling uncertainty, optional
hourly forecasts, fixed-mode compatibility and the complete scoring protocol.
The model and result classes, `load_model`, `train_model` and
`evaluate_cumulative` can also be imported from `wildfire.api`; data loading
remains independent through `wildfire.load_data`.

## Load and inspect a model

`load_model(path=DEFAULT_CHECKPOINT, *, device="cpu")` and
`WildfireModel.from_checkpoint(path, *, device="cpu")` restore saved weights,
training-only normalization, ordered channels and categorical vocabularies.
Trusted local `PatchRandomForest` `.joblib` checkpoints are also supported;
their fitted estimator runs on CPU and retains its saved preprocessing.
`DEFAULT_CHECKPOINT` is defined in `wildfire.paths`; `DEFAULT_ROOT` is defined
in `wildfire.data` as an alias of `wildfire.paths.DATA_ROOT`.

| Option or attribute | Meaning |
| --- | --- |
| `path` | Supported checkpoint file; `load_model()` defaults to the maintained checkpoint. |
| `device` | For tensor checkpoints, `"cpu"`, `"cuda"`, `"mps"`, `"auto"`, or corresponding `torch.device`; `"auto"` checks CUDA, then MPS, then CPU. Forests support CPU, with `"auto"` resolving to CPU. |
| `model.to(device)` | Move resident tensor weights and normalization together; return the same model. Forests retain CPU execution. |
| `model.family` | `"exponential"`, `"mixture_exponential"`, or `"random_forest"`. |
| `model.channel_names` | Saved ordered input-channel tuple. |
| `model.contract` | Independent copy of checkpoint metadata. |
| `model.device` | Current inference device; random forests use CPU. |
| `model.checkpoint_path` | Loaded checkpoint path. |
| `model.checkpoint_sha256` | Checksum of the loaded checkpoint bytes. |
| `model.training_metrics` | Returned training report after `train_model` or `WildfireModel.train`; otherwise `None`. |
| `model.predictor` | Resident fitted numerical wrapper for advanced use. |

Supported checkpoint architectures are `EnvironmentConditionedConvolution`,
`LearnedNonnegativeKernel`, `MixedNonnegativeKernel`,
`NeuralMixedNonnegativeKernel`, `BayesianModelAverage`, and `PatchRandomForest`.
Retired signed checkpoints raise an explicit error.

The optional `baseline` dependency installs the required scikit-learn version
for forest loading:

```bash
.venv/bin/python -m pip install -e '.[baseline]'
```

Use the same rectangular prediction API for a saved forest:

```python
forest_model = load_model(
    "runs/20261010_categorical_balanced_benchmark/forests/rf3_depth8.joblib",
    device="cpu",
)
forest_result = forest_model.predict_cumulative(
    sample, hours=[6], n_samples=1024, seed=0,
    trajectory_batch_size=32, boundary="zero",
)
```

Forest grid prediction applies the saved training normalization when both
normalization vectors are embedded in checkpoint metadata. A standalone
`PatchRandomForest` checkpoint without those vectors retains the estimator's
preprocessed-input contract and uses identity preprocessing. Incomplete or
invalid normalization metadata is rejected. Named categorical channels are
validated before normalization. Forest probabilities are mean tree
probabilities at the fitted one-hour endpoint. `predict()` therefore accepts
only `dt_hours=1`; `method="fixed"` accepts only a one-hour horizon. Multi-hour
forest prediction uses `method="recursive"`, evaluating the same fitted forest
at each hour on binary states. A complete known neighborhood without a burned
source receives zero probability, and an already burned cell cannot ignite
again. An ordinary one-hour forest result reports an equivalent interval rate
`-log(1-q)` as a diagnostic, including infinity when `q=1`; this is not a fitted
hazard and cannot be used to extrapolate the forest to other durations. The
API does not sample a tree per trajectory. Joblib restores pickled objects: load only trusted local
files produced by a trusted process.

## Select data

Discover event identifiers and cutoff times without loading a model or opening
any rasters:

```python
from wildfire import available_events, available_cutoffs

EVENTS = available_events(sequence_length=2)
EVENT = EVENTS[0]
CUTOFFS = available_cutoffs(EVENT, sequence_length=2)
CUTOFF = CUTOFFS[0]
EVENTS_AT_CUTOFF = available_events(CUTOFF, sequence_length=2)
```

Check for an empty list before indexing when a dataset or filter might have no
matching selection. Discovery and data loading are standalone functions; they
do not require or belong to a model.

`available_events(cutoff=None, *, data_root=DEFAULT_ROOT, sequence_length=1)`
returns a `list[str]` of fire-event identifiers in catalog order. With
`cutoff=None`, it includes events having at least one complete sequence of the
requested length. With a cutoff, it includes only events having a complete
sequence beginning at that exact timestamp.

`available_cutoffs(event, *, data_root=DEFAULT_ROOT, sequence_length=1,
time_range=None)` returns a chronological `list[str]` of eligible sequence-start
cutoffs, normalized to UTC ISO timestamps ending in `Z`.

Timestamp inputs may be strings or `datetime` objects. Offset-aware inputs are
converted to UTC; naive inputs are interpreted as UTC. Exact cutoffs follow the
hourly grid anchored at the event's catalog start, without rounding to clock
hours. An off-grid or out-of-range cutoff matches no events. An unknown event
identifier in `available_cutoffs` raises `ValueError`; a known event with no
matching window returns `[]`. `sequence_length` must be a positive integer and
cannot be Boolean.

| Discovery option | Default | Meaning |
| --- | --- | --- |
| `event` | Required for `available_cutoffs` | One catalog fire-event identifier. |
| `cutoff` | `None` | Optional exact sequence-start timestamp for filtering events; use an explicit UTC offset. |
| `data_root` | `DEFAULT_ROOT` | Root containing the aligned environmental catalog. |
| `sequence_length` | `1` | Positive number of consecutive declared hourly snapshots required from a cutoff. Discovery excludes incomplete or temporally padded windows. |
| `time_range` | `None` | Inclusive `(start, end)` UTC bounds on sequence-start cutoffs, available only in `available_cutoffs`; later snapshots may extend beyond these bounds while remaining inside the event's catalog timestamps. |

These functions read metadata-declared timestamps, without raster reads or model
inference. A listed event/cutoff does not guarantee valid predictors at every
cell, available reconstructed outcomes at every cell, or active flames.
`sequence_length=2` retains a following-hour snapshot whose reconstructed outcome
can be aligned with the first prediction. The final prediction in any sequence
still needs a separately available forecast-endpoint label for comparison.

`load_data(data_root=DEFAULT_ROOT, *, events=None, sequence_length=24,
temporal_stride=None, patch_size=None, channels=None, time_range=None,
daily_policy="completed_day", fill_value=0.0, max_open_files=64,
categorical_encoding="one_hot", categorical_classes=None)` returns an independent
`WildfireSequenceDataset`.

Set `sequence_length=None` to include the complete available hourly timeline of
each selected event in one sample per spatial tile. A `time_range` limits that
timeline before samples are formed. The default `sequence_length=24` retains
fixed-size windows; any positive integer requests windows of that many hourly
snapshots. No checkpoint is read and no schema is chosen by a model during
loading.

```python
from wildfire import load_data, select_time
from wildfire.schema import TRAINING_SOURCE_CHANNELS

with load_data(
    events=["WY-BTF-002416_FishCreek"],
    channels=TRAINING_SOURCE_CHANNELS,
    sequence_length=None,  # Explicit option: the complete available timeline.
    patch_size=None,  # Explicit option: the original full event rectangle.
) as data:
    timeline = data[0]

sample = select_time(timeline, "2024-08-23T00:00:00Z")
sample_by_index = select_time(timeline, index=48)  # The 49th loaded timestamp.
sequence = select_time(
    timeline, "2024-08-23T00:00:00Z", "2024-08-23T01:00:00Z",
)
```

Dataset construction reads the catalog and layer metadata lazily; indexing
materializes the selected sample's full time dimension and tensors. The sample
remains usable after the context manager closes cached raster readers.
`TRAINING_SOURCE_CHANNELS` is an independently defined selection of six source
fields used by the maintained example models; the biome field expands to 14
indicators, yielding 19 channels. Omit `channels` to load the complete bundle
schema, or choose another schema for exploration or another fitted model. Full
event timelines with the complete schema can be large; use explicit source
selection, `time_range`, `patch_size`, or fixed-size windows when appropriate.

| Loader option | Default | Meaning |
| --- | --- | --- |
| `data_root` | `DEFAULT_ROOT` | Aligned environmental dataset root. |
| `events` | `None` | All catalog events, or a nonempty sequence of distinct catalog identifiers. |
| `sequence_length` | `24` | Positive integer for fixed-size windows, with a temporally padded final window if necessary; `None` opts into the complete selected event timeline. |
| `temporal_stride` | `None` | Whole-timeline mode requires `None`; for fixed-size windows, `None` uses `sequence_length`, and an explicit stride must lie between 1 and that length. |
| `patch_size` | `None` | Full original event rectangle, including cells with unavailable arrival/burned-state labels; a positive integer requests square patches, and `(height, width)` requests rectangular patches. |
| `channels` | `None` | Bundle schema; source categorical names expand to full groups, or select individually encoded `source=code` channels. |
| `time_range` | `None` | Inclusive `(start, end)` UTC bounds on available input snapshots. Loading timestamps require an explicit UTC offset. |
| `daily_policy` | `"completed_day"` | Most recent completed source day; `"containing_day"` is available for retrospective alignment and can include information from later in that day. |
| `fill_value` | `0.0` | Finite storage fill; validity masks, rather than fill values, describe missingness. |
| `max_open_files` | `64` | Positive cache limit for raster readers. |
| `categorical_encoding` | `"one_hot"` | One-hot indicators, or `"raw"` scalar category codes. |
| `categorical_classes` | `None` | Frozen source-to-code vocabularies for one-hot loading; unavailable with raw encoding. |

The full-rectangle loader preserves environmental pixels outside the arrival
availability mask. That mask describes reference-label availability; it does
not crop the grid, mask environmental fields or define physical `pixel_valid`
support. Environmental fields retain their own source validity masks. A full
rectangle therefore need not have complete environmental coverage for every
event or channel. The probability demonstration audits its FishCreek grid
against the original grid metadata and verifies that all 19 selected features
are available over its 103-by-73 rectangle, including outside its arrival mask.

`select_time(sample, start=None, end=None, *, index=None)` selects from a loaded,
unbatched sample without opening files or consulting a model. Choose one of two
selection forms:

| Selection | Meaning |
| --- | --- |
| `select_time(sample, start)` | Select the one valid loaded timestamp `start`. |
| `select_time(sample, start, end)` | Select the inclusive interval from `start` to `end`; both endpoints must be valid loaded timestamps. |
| `select_time(sample, index=i)` | Select one zero-based position in this loaded sample; negative indices count from its end. |

Timestamp boundaries require explicit UTC offsets. `end` must not precede
`start`; unavailable boundaries raise `ValueError`. Index selection requires an
integer excluding booleans, raises `IndexError` for an out-of-range position,
and raises `ValueError` for temporal padding. Supplying neither selection form,
or combining `index` with `start` or `end`, raises `ValueError`. With a loaded
time length `T`, valid positional indices satisfy `-T <= i < T`; their timestamps
also must be valid. Positions are relative to this sample: applying `time_range`
before loading changes which timestamp has index 0.

The result keeps the time dimension: selecting one timestamp or position returns
a sample with time length 1. It slices all recognized temporal values and masks
consistently and retains static fields such as coordinates, arrival times and
georeferencing. The returned mapping shares tensor/array storage with the
original sample; selection itself does not modify it. Selection does not create
an observation or interpolate missing times. Batched inputs are not supported;
select a loaded event/tile before collating samples.

`WildfireSequenceDataset` exposes `len(dataset)`, `dataset[index]`,
`sample_location(index)`, `channel_names`, and `close()`. Input tensors remain on
CPU until prediction. `collate_fire_sequences(samples)` batches samples with a
common channel schema and pads differing time lengths and spatial rectangles;
`time_valid` and `pixel_valid` identify that padding.

## Predict and read the result

`model.predict(sample, *, dt_hours=1.0, boundary="unknown")` takes a sample or
collated batch. The mapping supplies channels, masks, geometry and any cutoff
metadata; overriding these sample fields in the call is an error. For a sample
mapping, the model selects its required channels by name and puts them into the
saved order at prediction time. A loader may supply a reordered schema or a
superset of required channels; missing required channels are an error. Features
and their masks are selected together, and the loaded sample is not modified.
Complete known categorical groups must be valid one-hot vectors. If the loader
includes a category absent from the checkpoint and that category is active, the
model marks its required group unavailable for that cell rather than treating
the category as an all-zero known vector. Bare arrays require the exact saved
channel order and use the following full interface:

```python
result = model.predict(
    burned_area, environmental_data,
    channel_names=channel_names,
    burned_area_valid=None, feature_valid=None,
    dt_hours=1.0, boundary="unknown",
    affine_transform=None, epsg=None,
    pixel_valid=None, time_valid=None,
)
```

| Option | Meaning |
| --- | --- |
| `burned_area` | Real binary cumulative state with shape `[..., 1, H, W]`; invalid entries are ignored. |
| `environmental_data` | Real raw physical inputs with shape `[..., C, H, W]`; leading and spatial dimensions match burned state. |
| `channel_names` | Required for bare arrays; exact saved channel order. A mapping supplies its own unique channel names, from which the model selects its required inputs. |
| `burned_area_valid` | Optional Boolean mask matching the complete burned-state shape. |
| `feature_valid` | Optional Boolean mask matching the complete environmental shape. |
| `dt_hours` | For exponential tensor models, a finite nonnegative scalar, or a numeric array/tensor matching every leading input dimension exactly. The trained horizon is one hour. Random forests require every duration to equal one hour. |
| `boundary` | `"unknown"` retains uncertainty from outside-grid sources; `"zero"` explicitly assumes no outside-grid contribution. Unknown interior cells remain unknown. |
| `affine_transform` | Six pixel-corner coefficients `(a, b, c, d, e, f)`; shared grid or one grid per batch item. |
| `epsg` | Source coordinate reference system; shared integer EPSG or one per batch item. Supply it together with the affine transform. |
| `pixel_valid` | Optional Boolean static spatial-padding mask; supports `[H,W]` or singleton-channel `[1,H,W]`, with batch dimensions when needed. Padded cells are excluded from current inputs and outputs, so they cannot supply burned neighbors or assumed zero source states. |
| `time_valid` | Optional Boolean mask matching leading time/batch dimensions; false times are excluded from inputs and outputs. Static coordinates remain independent of time padding. |

Omit both `affine_transform` and `epsg` when geographic output is unnecessary.
Supplying only one is an error. No probability is filled with zero merely
because a required input is unknown. Known already-burned cells have zero
first-new-burn probability. Fully known zero source neighborhoods also produce
structural zeros under the model's input/coverage contract.

A single-kernel rate is held fixed over `dt_hours`; this is not recursive
propagation. Bayesian averaging combines component probabilities at the chosen
horizon, and its equivalent interval rate can depend on that horizon.

| `Prediction` field or method | Shape and meaning |
| --- | --- |
| `probability` | Tensor `[...,1,H,W]`, on the model device, containing `q`: probability of first new cumulative burning during the forecast interval. This is the plotted quantity. |
| `valid` | Matching Boolean probability mask. |
| `rate` | Matching nonnegative hourly rate `lambda` for the exponential model, or equivalent interval rate for a Bayesian average or one-hour random forest; a separate diagnostic. The forest value `-log(1-q)` is not a fitted temporal hazard. All recursive cumulative rates are NaN with `rate_valid=False`. |
| `rate_valid` | Matching Boolean rate mask; may differ from probability validity. |
| `coordinates` | Optional CPU float64 WGS84 `(latitude,longitude)` centers, `[H,W,2]` or `[B,H,W,2]`. Spatial padding is NaN; unavailable predictions retain real locations. |
| `time_utc` | Optional integer Unix-seconds cutoff array matching leading time/batch dimensions. Dataset samples supply it. |
| `dt_hours` | Forecast horizon scalar or array. |
| `event_id` | Optional event identifier or batch identifiers retained from the sample. |
| `burned_probability` | Optional matching tensor of total burned probability, including initial burns; supplied by cumulative prediction. |
| `mc_standard_error` | Optional matching Monte Carlo standard error of `probability`; supplied in recursive cumulative mode. |
| `confidence_lower`, `confidence_upper` | Optional matching pointwise nominal 95% Wilson bounds for `probability`; supplied in recursive cumulative mode. |
| `metadata` | Optional method and simulation configuration, with uncertainty interpretation. |
| `numpy()` | Independent CPU NumPy copies of numeric fields; missing optional fields are omitted. Available `metadata` is exported as JSON. |
| `plot(...)` | Probability matrix figure and axis. |
| `aligned_observations(sample)` | Full-shape NumPy target and validity arrays aligned to exact one-hour forecast endpoints. |
| `compare(...)` | Combined probability, next-hour event and previous burned-area figure by default; returns a figure and one-dimensional array of panel axes. |

## Cumulative new-burn probabilities at requested hours

`model.predict_cumulative(sample, *, hours, method="recursive", n_samples=1024,
seed=0, trajectory_batch_size=32, environmental_forecast=None,
missing_burned_area="unburned", **options)` returns one
`CumulativePrediction` for the specified horizons from the same current input.
For raw inputs, use
`model.predict_cumulative(burned_area, environmental_data, hours=hours, **options)`;
the channel, mask and geometry options are the same as `model.predict`.
Recursive mode defaults to `boundary="zero"`; ordinary prediction and fixed
mode retain `boundary="unknown"` unless explicitly overridden.
`hours` replaces `dt_hours`, so supplying `dt_hours` to this interface raises an
error.

```python
selected_sample = select_time(timeline, index=70)
cumulative_result = model.predict_cumulative(
    selected_sample, hours=[1, 3, 6, 12],
    method="recursive", n_samples=1024, seed=0, trajectory_batch_size=32,
    missing_burned_area="unburned", boundary="zero",
)
six_hour_result = cumulative_result.at(hours=6)
q_6h = six_hour_result.probability
total_burned_6h = six_hour_result.burned_probability
fig, ax = cumulative_result.plot(hours=6)
fig, axes = cumulative_result.compare(timeline, hours=6)
arrays = cumulative_result.numpy()
```

In recursive mode, `hours` accepts a positive finite integer-valued scalar or a
nonempty sequence of distinct positive finite integer-valued numbers; `3.0` is
accepted, but `0.5` is rejected before inference. Fixed mode accepts distinct
positive finite real horizons, including fractional values, for exponential
tensor checkpoints. Forest fixed mode accepts only the fitted one-hour
endpoint; multi-hour forest predictions use recursive mode. Boolean values are
not hours. Requested order is preserved. A scalar produces one horizon.
Methods select a requested horizon
by its value: `hours=6` selects six hours, not position 6. Their `index` retains
the ordinary time/batch selection rule within each base prediction.

| Cumulative option | Meaning |
| --- | --- |
| `method` | `"recursive"` by default; `"fixed"` selects the previous fixed-state calculation. |
| `n_samples` | Positive integer excluding booleans, default 1,024; number of independent trajectories. Values such as 256 and 4,096 trade runtime for simulation precision. |
| `seed` | Nonnegative integer excluding booleans, default 0; local sampling seed. Global random state is unchanged. |
| `trajectory_batch_size` | Positive integer excluding booleans, default 32; trajectories processed together to control memory use. |
| `environmental_forecast` | Optional mapping of hourly environmental inputs described below; rejected in fixed mode. |
| `missing_burned_area` | Recursive-only initial-state policy: `"unburned"` by default fills unavailable cutoff burned states as zero inside true pixel/time support; `"unknown"` keeps them unavailable. Environmental gaps and padding are never filled. |
| `boundary` | Recursive default `"zero"` assumes unburned cells outside the rectangle and existing zero model-context padding, preserving edge coverage when interior inputs are complete. Explicit `"unknown"` retains unavailable exterior context and may reduce valid coverage with each hour. Fixed mode defaults to `"unknown"`. |

Simulation controls and `missing_burned_area` have no effect in fixed mode;
ordinary prediction and fixed mode retain missing burned states as unknown.
Let `P` be the probability
shape returned by `model.predict` for the same inputs, and let `R` be the number
of requested horizons.

| `CumulativePrediction` field or method | Shape and meaning |
| --- | --- |
| `hours` | Tuple of `R` requested horizons in hours, preserving input order. |
| `probability`, `valid`, `rate`, `rate_valid` | Shape `(R, *P)`; one base prediction per requested horizon, with separate probability/rate masks. `probability` contains cumulative new-burn probability `q(h)`. Recursive rates are NaN with false `rate_valid`; fixed mode retains rate diagnostics. |
| `burned_probability` | Shape `(R, *P)`; total burned probability including cells already burned at the cutoff. It shares the probability validity mask. |
| `mc_standard_error`, `confidence_lower`, `confidence_upper` | Recursive-mode tensors of shape `(R, *P)`, with the probability validity mask and device. Absent in fixed mode. |
| `metadata` | Method, sampling configuration, environment policy and uncertainty interpretation. Recursive results also record `boundary`, `missing_burned_area` and the total `assumed_unburned_cells` cutoff-cell count before trajectory sampling. |
| `coordinates`, `time_utc`, `event_id` | Same geometry and cutoff metadata as a base prediction; no extra horizon dimension for static coordinates or cutoff times. |
| `at(hours=h)` | A standard `Prediction` for requested horizon `h`; its `dt_hours` is `h`, and it exposes that horizon's additional numerical fields and metadata. |
| `plot(hours=h, index=None, **options)` | Probability plot for `q(h)` with the ordinary matrix styling and base time/batch selection options. |
| `compare(observed, hours=h, index=None, **options)` | Combined `q(h)`, previous burned area and new-burn reference for the entire interval `(t, t + h hours]`. Uses the same layer/layout styling options as ordinary comparison. |
| `aligned_observations(sample, hours=h)` | Base-shape target and validity arrays for cumulative new burns, aligned using burned states at the exact cutoff and endpoint. |
| `numpy()` | Independent CPU NumPy arrays, including `hours`, horizon-stacked numerical fields and available metadata serialized as JSON. |
| `evaluate(observed, *, hours, quantity="new_burn", coverage="per_horizon", weight=None, threshold=0.5, cohort_mask=None)` | JSON-compatible protocol and per-horizon scores for explicitly selected durations; reference states are aligned at exact endpoints. |

The default recursive calculation starts each trajectory from the same
initialized binary cumulative burned state. It retains known cutoff states and
initializes unavailable burned-state entries (invalid or nonfinite values) as
unburned within true `pixel_valid` and `time_valid` support. This initialization
assumption does not modify the supplied sample. It leaves missing environmental
inputs and spatial/temporal padding unavailable. Set
`missing_burned_area="unknown"` to preserve the original unknown initial states.
The metadata count `assumed_unburned_cells` sums initialized cutoff-cell entries
across independent time/batch cutoffs, without multiplying by `n_samples`.
At hour `k`, the existing fitted predictor
supplies one-hour ignition probabilities conditional on that trajectory's
current state and the next interval's environmental inputs. Unburned cells draw
independent Bernoulli ignitions conditional on those inputs and the fitted model
component. All cells update simultaneously. A cell ignited during one hour can
become a source in the following hour; an already burned cell remains burned.
Probabilities are never fed back as fractional burned-state inputs.

Explicitly, let `i` index cells, `m` index the `N = n_samples` trajectories,
`B_i^0` be the initialized cutoff state (including any assumed unburned cells),
and `B_i^{m,h}` be trajectory `m`'s state after `h`
hours. The output `probability` estimates

$$
\widehat F_i(h)=\frac{1}{N}\sum_{m=1}^{N}(1-B_i^0)B_i^{m,h},
\qquad
\widehat P_i^{\mathrm{burned}}(h)
=B_i^0+(1-B_i^0)\widehat F_i(h).
$$

The second quantity is `burned_probability`. Initially burned cells have exact
new-burn probability zero and total burned probability one. Each requested
horizon uses the same absorbing trajectories, so cumulative estimates are
nondecreasing on cells valid at both horizons. Existing leading time/batch
dimensions are independent prediction cutoffs, not rollout steps. For Bayesian
checkpoints, select one component per trajectory using the saved posterior
weights and retain it through the entire rollout, including its fitted
preprocessing. Resampling a component at every hour defines a different process
and is not used.

Local CPU random streams separate component selection from hourly ignition
draws. With the same seed, inputs and trajectory batch size, repeating a call
reproduces its results; reordering horizons or extending the maximum horizon
preserves earlier estimates. Increasing `n_samples` retains the trajectories
in the smaller simulation. A different batch size may produce a different
realization. Coverage propagates conservatively and intersects the coverage of
all supported Bayesian components, even if a component receives no sampled
trajectories. Unknown environmental inputs remain unavailable under either
boundary mode. Missing initial burned states also remain unavailable when
`missing_burned_area="unknown"`; the default fills them only during
initialization within real support. Coverage is never rescued merely because
every simulated trajectory happened to burn an unavailable cell. Counts always use the full
`n_samples` denominator. An unavailable, nonfinite or out-of-range sampled
transition on declared coverage raises an informative error.

Predictions retain the loaded grid's full spatial shape. Recursive mode now
defaults to `boundary="zero"`: outside-grid burned-state sources are unburned,
and exterior model-context entries use the existing zero padding. Environmental
context zeros are in the model's input space; a standardized zero is not
necessarily a raw physical zero. With complete interior inputs, exterior
padding does not erode edge coverage as the simulation advances. This
assumption supplies no burning outside the rectangle and does not model fire
entering from an exterior source.

Explicit `boundary="unknown"` makes outside-grid neighborhood inputs
unavailable. Its conservative coverage can move inward with each hour even
when all environmental pixels inside the rectangle are present; the arrays
still retain the full rectangle. Earlier saved demonstrations with gray borders
record that exterior assumption. Missing interior environmental inputs and
physical/time padding inside the supplied tensors remain unavailable under
both boundary settings. Their dependencies can still reduce coverage.

For valid cells, `mc_standard_error` is
`sqrt(probability * (1 - probability) / n_samples)`. Confidence bounds are
pointwise nominal 95% Wilson intervals with `z = 1.95996398454`. Known initial
burns have standard error zero and bounds `[0, 0]` for their exact new-burn
probability zero. With 1,024 trajectories, the largest theoretical standard
error is `1 / (2 * sqrt(1024)) = 0.015625`. These quantities describe Monte Carlo
error for expectations under the specified simulation process; they do not
establish calibration, observed fire geometry or longer-horizon forecast skill.
Ordinary `model.predict(sample)` continues to return its analytic one-hour
probability and keeps missing burned states unknown. The recursive one-hour
estimate agrees with the analytic predictor up to sampling error when both use
the same initialized inputs. With missing input states, recursive default
initialization can provide coverage that ordinary prediction does not provide.

Without `environmental_forecast`, current environmental conditions repeat for
every simulated hour. An optional caller-supplied forecast has this form:

```python
forecast = {
    "features": hourly_features,
    "channel_names": forecast_channel_names,
    "feature_valid": hourly_feature_valid,  # optional
}
cumulative_result = model.predict_cumulative(
    selected_sample, hours=[1, 3, 6], seed=0,
    environmental_forecast=forecast,
)
```

After selecting the checkpoint's named channels, `features` must have shape
`[S, *L, C, H, W]`, where `L` is the cutoff input's leading time/batch dimensions,
`C` is the checkpoint channel count, and `S >= max(hours)`. Slice zero supplies
the first interval `(t, t + 1 hour]`; slice one supplies the next interval.
Additional forecast slices are ignored. If provided, `feature_valid` must match
the complete feature shape before channel selection; it is selected with its
features. Named-channel selection and categorical validation follow the ordinary
prediction contract. Forecast-hour is a separate axis from cutoff time/batch.
Future outcome and arrival labels are never inputs to prediction.

For compatibility, `method="fixed"` holds the cutoff burned state, environment
and hourly rate fixed. For a known initially unburned cell,
`q(h) = 1 - exp(-lambda * h)`; known initial burns have `q(h) = 0` and total burned
probability one. Bayesian models average component probabilities separately at
each horizon, rather than compounding a one-hour mixture or exponentiating an
average rate. Fixed mode retains fractional horizons and rate diagnostics,
omits Monte Carlo fields and rejects `environmental_forecast`. The
single-horizon call `model.predict(sample, dt_hours=h)` retains this existing
analytic calculation.

For sample comparison, a reference cell is positive when it was unburned at
cutoff `t` and burned by exactly `t + h hours`. Both cumulative reference states
and their masks must be available. Missing timestamps or invalid states remain
unknown; the API does not substitute the nearest hourly label or fill missing
labels with zero. The previous burned-area layer uses the state at `t`. Bare
targets must already describe the same cumulative interval and grid.
The initial-state assumption affects simulation inputs only; reference state
masks and comparison targets are never imputed.

## Evaluate cumulative predictions

`evaluate_cumulative(result, observed, *, hours, quantity="new_burn",
coverage="per_horizon", weight=None, threshold=0.5, cohort_mask=None)` evaluates
an existing `CumulativePrediction` against a reference sample or collated batch.
`result.evaluate(observed, *, hours, ...)` is the equivalent method. Evaluation
reads reference states separately from prediction and does not change the
computed probabilities or infer another trajectory.

`hours` has no default. Enter a scalar duration for one report or distinct
durations for several reports; omitting it raises `TypeError`. Recursive
results contain positive whole-hour durations. Fixed-mode results can also
be evaluated at their already-computed fractional durations when reference
timestamps match the exact endpoint.

```python
from wildfire import evaluate_cumulative

new_burn_report = cumulative_result.evaluate(
    reference_timeline, hours=[1, 3, 6], quantity="new_burn",
    coverage="per_horizon", threshold=0.5,
)
burned_report = evaluate_cumulative(
    cumulative_result, reference_timeline, hours=6,
    quantity="burned", coverage="shared", threshold=0.5,
)
```

| Evaluation option | Meaning |
| --- | --- |
| `hours` | Required positive scalar or sequence of distinct durations already present in `result.hours`; preserves supplied order. Each selected endpoint is exactly `cutoff + hours * 3600` seconds. |
| `quantity` | `"new_burn"` scores `probability` against new burns after the cutoff; `"burned"` scores `burned_probability` against total burned state at the endpoint. |
| `coverage` | `"per_horizon"` scores each duration's eligible covered entries independently; `"shared"` intersects those entries over the selected durations before scoring each one. |
| `weight` | Optional finite nonnegative scalar, `[H,W]` spatial array or complete base probability-shape array without a horizon axis. The same weights apply at every selected duration. `None` uses equal cell/cutoff weights. Zero-weight entries are excluded. |
| `threshold` | Finite real scalar excluding booleans, default `0.5`; predicts positive when probability is at least this value. It is never selected or tuned from evaluated outcomes. |
| `cohort_mask` | Optional Boolean `[H,W]` spatial mask or complete base probability-shape mask without a horizon axis; restricts the evaluation cohort identically across selected durations. |

For `quantity="new_burn"`, an eligible reference entry has a known unburned
cutoff state and a known endpoint state. Its outcome is one exactly when the
endpoint state is burned. Initially burned entries are excluded. For
`quantity="burned"`, eligibility requires a known endpoint state and the outcome
is that endpoint's burned indicator; a known cutoff reference is unnecessary.
Neither quantity imposes a burned-neighbor-contact restriction. Simulation
assumptions about unavailable initial burned states never create known reference
labels. Physical/time support, reference alignment, the caller's mask, positive
weights and prediction validity determine the evaluated entries.
Total-burned evaluation requires `burned_probability` at every selected horizon.
Known cumulative reference states must not change from burned to unburned;
such a contradiction raises an error.
The two quantities evaluate different targets and cohorts. Total-burned scores
include initial burns retained with probability one; they are not directly
interchangeable with scores of new spread.

The return value is a JSON-compatible dictionary with `protocol` and
`per_horizon`. Each row contains `hours`, `coverage`, `metrics`,
`classification` and `calibration`. Horizons are separate reports: no combined
score pools them. Scores aggregate the selected cell/cutoff entries within each
horizon, using the supplied weights. The protocol records the choices needed
to interpret the report. Entries without an exact endpoint are excluded. If no
eligible entries remain, scores are unavailable (`None`, serialized as JSON
`null`), rather than substituting the nearest timestamp or labeling missing
cells as unburned.

Coverage distinguishes the reference-eligible entries, that horizon's own
prediction-covered entries, and the entries actually evaluated after an
optional shared intersection. Counts and weight totals are reported separately.
`coverage_fraction` is evaluated weight divided by reference-eligible weight;
`prediction_coverage_fraction` uses the horizon's own prediction-covered weight
instead. A fraction is `None` when its denominator is zero. Reports also count
initially burned exclusions, zero-weight exclusions and
`excluded_by_shared_coverage_cells`. Shared coverage uses the same entries for
every selected horizon of the same quantity, while their outcomes can differ.

Probability metrics include overall and class-specific Brier scores, exact
negative log likelihood, separately clipped log loss, average precision,
ROC AUC, trapezoidal PR AUC, and exact/floored Bernoulli KL. AP and trapezoidal
PR AUC are distinct measures. Exact scores retain endpoint probabilities zero
and one. A positive observation with probability zero, or a negative observation
with probability one, gives exact NLL/KL `"infinity"`. Clipped/floored scores
change the evaluated probability to `[1e-7, 1 - 1e-7]` and are reported separately.
Rank scores and other scores can be `None` when their required classes or
denominators are unavailable.

For every evaluated entry `i`, let `y_i` be its binary observed outcome,
`p_i` its predicted probability, and `w_i > 0` its weight. The empirical
reference and prediction are the two-point distributions
`P_i = (1 - y_i, y_i)` and `Q_i = (1 - p_i, p_i)`. Exact
`KL(P_i || Q_i)` equals that entry's negative log likelihood because a binary
observed label gives a reference distribution of zero entropy. The seven
distance fields are weighted means of the following per-entry quantities:

| Quantity | Per-entry definition | Units |
| --- | --- | --- |
| Total variation | `abs(y_i - p_i)`. | Dimensionless |
| Hellinger | `sqrt(0.5 * sum((sqrt(P_i) - sqrt(Q_i)) ** 2))`. | Dimensionless |
| Jensen–Shannon divergence | `0.5 * KL(P_i \|\| M_i) + 0.5 * KL(Q_i \|\| M_i)`, with `M_i = (P_i + Q_i) / 2` and natural logarithms. | Nats |
| Jensen–Shannon distance | Square root of the per-entry Jensen–Shannon divergence. | Square-root nats |
| Bhattacharyya distance | `-log(sum(sqrt(P_i * Q_i)))`; disjoint support gives `"infinity"`. | Nats |
| Wasserstein-1 | `abs(y_i - p_i)` on binary support `{0,1}` with unit ground distance. | Unit binary-outcome ground distance |
| Wasserstein-2 | `sqrt(abs(y_i - p_i))` on that same binary support. | Unit binary-outcome ground distance |

Every distance mean is `sum(w_i * d_i) / sum(w_i)`; square roots are taken per
entry before averaging. These are disagreements with observed binary outcomes,
not geographic transport distances, comparisons between two fitted models or
distances between joint distributions of entire fire maps.

The classification block reports weighted TP/FP/TN/FN, precision, recall, F1,
MCC, accuracy, specificity, balanced accuracy and intersection-over-union at the
given threshold. The calibration block supplies fixed descriptive reliability
bins with edges `[0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1]` and weighted expected
calibration error (ECE). Those bins are not fitted from the evaluated outcomes.
The metrics block also retains `classification_at_0_5` and the `*_at_0_5`
scores at threshold `0.5`; the separate classification block uses the supplied
threshold. Nonempty-cohort classification scores with zero denominators use
zero, including degenerate MCC and intersection-over-union. An empty cohort
has zero confusion counts, unavailable classification scores, an empty
calibration-bin list and unavailable ECE.
Prediction Monte Carlo standard errors and Wilson bounds describe simulation
error of individual cell probabilities; they do not provide metric confidence
intervals or establish independent observations among neighboring cells.

## Evaluate all saved models from the command line

`python -m wildfire evaluate-cumulative` generates cumulative predictions,
evaluates saved models against exact endpoint references, and generates report
plots. Run from the workspace
root, entering the duration explicitly in the command:

```bash
.venv/bin/python -m wildfire evaluate-cumulative \
  --hours 6 \
  --output-dir reports/cumulative_6h
```

`--hours` selects one positive whole-hour recursive horizon; edit its value to
change the prediction and evaluation interval together. The default root is
`runs/20261010_categorical_balanced_benchmark`, and default `--selection all`
discovers every canonical `checkpoint.pt` and saved random-forest `.joblib`
artifact beneath that root. The currently supplied root contains 284 tensor
checkpoints and six forests, for 290 models. Optimizer/resume payloads and
round-trip tensor copies with other filenames are outside that discovery rule.

For every supplied real-data model across the two trained searches
and the Bayesian experiment, use all three roots:

```bash
.venv/bin/python -m wildfire evaluate-cumulative \
  --hours 6 \
  --models-root runs/20261010_categorical_balanced_benchmark \
  --models-root runs/20261009_multiscale_mps_lr_0p001_0p01_0p1_floor_0p1 \
  --models-root runs/20261011_bayesian_kernel_average \
  --selection all \
  --output-dir reports/cumulative_6h_all_models_with_forests
```

Those roots currently contain 284, 276 and 1 canonical tensor checkpoints,
respectively, and six, six and zero random forests: 573 models in total,
including 561 tensor checkpoints and 12 forests. They exclude the synthetic workflow artifacts in
`runs/workflow_test_20261010`. Model discovery is explicit scope, not a new
statistical model-selection step. No fitting or threshold selection uses the
evaluated outcomes.

| Runner option | Meaning and default |
| --- | --- |
| `--hours` | Positive whole-hour duration used for both recursive prediction and exact endpoint evaluation; CLI default `6`. Enter it explicitly to record the desired duration in your command. |
| `--models-root` | Repeatable experiment directory. The default is the current categorical benchmark above. |
| `--checkpoint` | Repeatable explicit saved tensor or forest checkpoint path. Without `--models-root`, explicit paths replace default root discovery. |
| `--selection` | `all` by default: canonical tensor checkpoints and saved forests under each chosen root. `best` uses saved `best_models.json` entries for both types; without a registry, exactly one canonical artifact is required. A multiple-model root without a registry raises an error. |
| `--data-root` | Aligned event-data root; defaults to the workspace's `data/environment`. |
| `--split` | `test` by default: common exclusively held-out events declared by every selected model and supported Bayesian component. Forest split provenance is validated before use. `all` uses retrospective catalog events and makes no held-out claim. |
| `--event` | Repeatable event identifier restricting the selected event set. |
| `--cutoff` | Repeatable exact UTC cutoff. Its start and endpoint must lie on the event's hourly grid and be available without temporal padding. |
| `--stride-hours` | Chronological cutoff spacing; defaults to the duration supplied with `--hours`. |
| `--max-cutoffs-per-event` | Optional positive limit on the chronological prefix retained for each event; a bounded diagnostic rather than an exhaustive evaluation. Cannot be combined with explicit `--cutoff` requests. |
| `--plan-only` | Writes the model/case inventory and protocol without trajectory simulation or evaluation scores. |
| `--n-samples` | Independent trajectories per cutoff; default `1024`. |
| `--seed` | Local nonnegative random seed; default `0`. |
| `--trajectory-batch-size` | Trajectories processed together; default `32`. |
| `--threads` | Torch CPU threads; default `4`. |
| `--device` | Tensor inference device; default `cpu`. Forest estimation runs on CPU and its actual device is recorded. |
| `--threshold` | Fixed classification threshold; default `0.5`, never tuned from the evaluated reference outcomes. |
| `--output-dir` | New or empty destination for report and protocol artifacts. Nonempty directories are rejected. Omitting it creates a fresh timestamped reports directory. |
| `--save-predictions` | Also saves compressed full-rectangle arrays per case, with a model axis. |
| `--no-plots` | Skip report figures. By default, figures are generated in PNG and SVG formats and linked in the readable report. |

The current real-data tensor and forest checkpoints, including the Bayesian checkpoint, have the
same ten exclusively held-out test events. Their common six-hour cases number
11,135 at hourly stride or 1,860 at the default six-hour stride, based on catalog
time support before cell-level coverage checks. Catalog availability alone does
not establish reference or predictor validity. Use a planning run to inspect
the exact selected inventory before an exhaustive simulation:

```bash
.venv/bin/python -m wildfire evaluate-cumulative \
  --hours 6 \
  --plan-only \
  --output-dir reports/cumulative_6h_plan
```

For a bounded real-event diagnostic, add `--event KFS_06
--max-cutoffs-per-event 1`. To use a specific cutoff, supply `--event` and
`--cutoff` together; the duration's exact endpoint must be available. The
runner does not substitute nearest timestamps or silently use padded tails.
Explicit cutoffs cannot be combined with `--max-cutoffs-per-event`: the runner
rejects a limit that could silently discard a requested case. The single
Bayesian checkpoint root supports `--selection best` without a registry;
multiple-checkpoint roots require their saved `best_models.json` for that mode.
Explicit `--split all` permits retrospective training/validation cases and
records this distinction in the protocol.

These forest checkpoints save a training-cache metadata digest and ordered
channels, but do not embed event split membership. The runner therefore
finds a companion tensor contract with the identical saved cache digest and
ordered schema, requires all matching witnesses to agree on split membership,
and records the witness checkpoint's path and content hash. This recovers the
forest's partition evidence without treating edited relocation paths in a
current cache metadata file as the original training payload. If no verified
partition witness is available, default `--split test` fails before scoring.
A standalone forest without partition provenance can be evaluated with an
explicit `--split all`, which makes no held-out claim. Each forest keeps its
own saved normalization; the companion supplies partition evidence only.

Inputs retain complete event rectangles (`patch_size=None`). The runner passes
only the selected cutoff's state, environmental inputs and masks to recursive
prediction. Missing initial burned states are assumed unburned, outside-grid
sources use `boundary="zero"`, and interior environmental gaps remain
unavailable. Current conditions repeat throughout the simulated interval.
Saved forests retain their fitted trees, frozen patch layout and normalization;
each trajectory uses the forest's mean one-hour probability at each transition.
Forest trees are not sampled as posterior components and no model is retrained.
Endpoint reference states are read only for evaluation and retain their
original validity masks; no missing reference state is converted to unburned.

For each case, the primary comparison intersects prediction validity across
models and then applies original reference eligibility for the selected
quantity. New-burn eligibility requires a known unburned cutoff and a known
endpoint; total-burned eligibility requires a known endpoint. There is no
initial-neighbor-contact restriction. Native per-model coverage diagnostics
remain visible so the shared cohort does not conceal a model's coverage loss.
Across cases or within one event, the runner recomputes metrics from pooled
equal-weight cell/cutoff entries; it does not average nonlinear case-level
scores such as AP, ROC AUC or F1. Shared coverage concerns models in this runner;
the API's `coverage="shared"` concerns horizons in an existing result.

`report.md` presents the model comparison and its scope. `report.json` contains
the machine-readable results; `protocol.json` records the selected models,
cases, horizon, environment/initialization/boundary policy and sampling controls.
`summary.csv`, `per_event.csv`, `per_cutoff.csv` and `calibration.csv` supply
pooled, event, case and calibration rows. The readable report and score exports
include exact KL, separately floored KL, total variation, Hellinger,
Jensen–Shannon divergence, Jensen–Shannon distance, Bhattacharyya,
Wasserstein-1 and Wasserstein-2. Every model has distance rows for both
`shared_models` and `native` cohorts, separately for future new burns and total
burned occupancy. The definitions above apply per cell before pooling; exact
KL uses natural logarithms and is measured in nats. Infinite values are
preserved, while an empty or mathematically undefined result is labeled
undefined in the readable report and encoded as JSON null. `--save-predictions` adds selected
full-rectangle arrays under `predictions/`, in one compressed NPZ file per case.
Its model axis identifies each model's `probability`, `burned_probability`,
`valid`, `mc_standard_error`, `confidence_lower` and `confidence_upper` fields.
It also saves the shared validity mask, static coordinates, model identifiers,
hour duration and case JSON metadata. A new or empty output directory is
required; existing report artifacts are not overwritten. Failed or unsupported
model entries must be read alongside the
scope and coverage records, rather than interpreted as scored models.
Tensor or forest checkpoint preflight failures stop the comparison before
scoring a subset; failures are preserved in the report. A failure during simulation
also stops the run and records its failed status and completed case count.

Report figures are generated from the evaluated shared-model cohort by default.
`plots/model_index.csv` maps short figure labels to complete model paths and
architectures. Both PNG and SVG are saved for each figure. For each quantity,
`new_burn` and `burned`, the figure basenames are `<quantity>_metrics`,
`<quantity>_architectures`, `<quantity>_distances`, `<quantity>_reliability`,
`<quantity>_event_brier`, `<quantity>_coverage`, and `<quantity>_curves`.
These display pooled probability/classification scores, architecture
representatives, Bernoulli probability distances, calibration, event-level
Brier scores, native/shared coverage, and ROC/precision-recall curves. Large
comparisons show every model in metrics, architecture and coverage figures.
Distances and event Brier display at most 20 representatives; reliability and
ROC/precision-recall display at most eight. Representatives include the best
Brier model from each architecture before filling remaining places by Brier,
with deterministic model-identifier tie breaking. RF and Bayesian
architectures are retained when the display limit is smaller than the number
of architectures. The manifest identifies both shown and omitted model IDs,
and the complete tables retain every scored model. This display ranking does not
change the model inventory, refit a model or select classification thresholds.
Curves use complete pooled entries and are omitted in a planning run. The
figure manifest is recorded in `report.json`; `report.md` embeds the saved PNG
figures. `--no-plots` disables figure generation. Bernoulli distances are
comparisons at individual cells, not geographic distances. Evaluation-score
figures do not show confidence intervals: pointwise Monte Carlo intervals
describe uncertainty in the simulated probabilities, not in aggregate scores.

The metrics and Bernoulli distances have the definitions above. Initially
burned occupancy and future new burning remain distinct targets. Exact NLL/KL
can be infinite when a finite Monte Carlo estimate is zero on a positive
reference cell; separately clipped scores remain labeled. These reports are
retrospective comparisons under the declared repeated-current-environment
simulation. Monte Carlo bounds describe individual probability estimation
error and do not establish independent observations, calibration or operational
forecast skill.

## Plotting and event comparison

`result.plot(*, index=None, **options)` displays **`q = result.probability`** and
uses its validity mask. It defaults to probability limits 0–1 and labels its
colorbar accordingly. For ordinary or fixed-mode exponential predictions, at known unburned cells,
`q = 1 - exp(-lambda * dt_hours)`, where `lambda = result.rate` has units h⁻¹.
Known already-burned cells have `q = 0`. Bayesian models average component
probabilities and expose the equivalent interval rate described above.
Recursive cumulative plots display the estimated first-new-burn probabilities
from the rollout; their rates are unavailable.
Its `index` addresses **already computed predictions**, not the original loaded
timeline. For example, a prediction from one selected timestamp has shape
`[1, 1, H, W]`: `result.plot()` and `result.plot(index=0)` both work, while
`result.plot(index=48)` raises `IndexError`. To choose another loaded position,
select it first and run prediction on that selection:

```python
selected_sample = select_time(timeline, index=48)
selected_result = model.predict(selected_sample)
fig, ax = selected_result.plot()  # One predicted time; index=0 is also valid.
fig, axes = selected_result.compare(timeline)  # One combined panel by default.
```

For the full FishCreek timeline, source position 48 has cutoff
`2024-08-23T00:00:00Z` and the prediction covers the following hour. Comparison
finds its reconstructed outcome at `2024-08-23T01:00:00Z` in `timeline`.

For a multi-time prediction with probability shape `[T, 1, H, W]`, use
`result.plot(index=t)`. For a batched prediction with shape `[B, T, 1, H, W]`, use
`result.plot(index=(b, t))`. `compare(..., index=...)` selects the same prediction
dimensions after outcome alignment. These indices are zero-based and accept
negative positions; they must be within the corresponding prediction dimensions.

`plot_matrix(matrix, ...)` is the standalone interface for arbitrary matrices,
including heat, rates or input layers:

```python
from wildfire import plot_matrix, plot_comparison

fig, ax = plot_matrix(matrix, valid=validity, title="My matrix")
fig, axes = plot_comparison(probability_matrix, binary_target_matrix)
```

| `plot_matrix` option | Default | Meaning |
| --- | --- | --- |
| `valid` | `None` | Boolean mask of the exact complete input shape. `result.plot` supplies this automatically. |
| `index` | `None` | Integer or tuple of integers, excluding booleans, selecting a prefix of leading dimensions; any remaining leading dimensions must be singleton. Indices are zero-based; negative positions count from the end. Use time index `t` for `[T,1,H,W]`, or `(b,t)` for `[B,T,1,H,W]`. For `result.plot`, these are prediction positions. |
| `ax` | `None` | Existing Matplotlib axis; otherwise create a figure and axis. |
| `title` | `None` | Panel title; `result.plot` supplies a probability title. |
| `cmap` | `"viridis"` | Matplotlib colormap. |
| `vmin`, `vmax` | `None`, `None` | Generic matrix color limits; `result.plot` defaults to `0`, `1`. |
| `colorbar` | `True` | Show a colorbar. |
| `colorbar_label` | `None` | Colorbar quantity/units label. |
| `unknown_color` | `"#d9d9d9"` | Color for masked, nonfinite or explicitly invalid entries. |
| `origin` | `"upper"` | Raster origin convention. |
| `figsize` | `(6,5)` | Size in inches when creating a figure. |
| Additional keywords | None | Forwarded to Matplotlib `imshow`, such as `interpolation`, `aspect`, `extent`, or `alpha`. |

Matrix plots use rows and columns by default. An `extent` describes the
caller-supplied rectangular plotting coordinates. It does not convert a rotated
or curved geographic grid into a rectangular latitude/longitude map.

`result.compare(observed, *, observed_valid=None, burned_area=None,
burned_area_valid=None, index=None, mode="overlay", **options)` accepts either an
hourly sample/batch or an already aligned binary
matrix. Full arrays must match the probability shape exactly; a two-dimensional
matrix can describe only the matrix selected by `index`. For sample mappings,
their own outcome and current-state masks apply. Omit `observed_valid`,
`burned_area` and `burned_area_valid` for a sample mapping: the fields are aligned
automatically.

The default is one combined plot. The background shows predicted next-hour
new-burn probability `q = result.probability` on a fixed 0–1 scale. A translucent brown layer shows the cumulative
area already burned at the prediction cutoff, and hollow cyan markers show cells
newly burned during the forecast interval. Marker interiors preserve the
underlying probability color or unavailable gray. The current burned area provides historical
context; it does not describe instantaneous active flames.

The plot retains the full selected grid extent, including cells with unavailable
probabilities. `result.compare` automatically outlines the prediction sample's
physical `pixel_valid` region with a boundary labeled "Loaded region". This
spatial region is independent of prediction validity. Supply `region_valid` to
override the region; standalone `plot_comparison` draws a boundary when this
option is supplied.

Hourly labels stamped at `s` represent arrivals in `(s−3600,s]`. A one-hour
prediction stamped at `t` represents first new burning in `(t,t+3600]`, so only
an observed label stamped at **exactly `t+3600`** is eligible. The previous burned
area uses `burned_area` at **exactly `t`**. Missing reference timestamps
remain NaN/false for the affected layer. Event identifiers and georeferencing must agree. Duplicate
valid outcome timestamps raise an error. Sample comparison requires
`dt_hours=1`; for other horizons provide explicitly aligned interval targets.

```python
sequence = select_time(
    timeline, "2024-08-23T00:00:00Z", "2024-08-23T01:00:00Z",
)
result = model.predict(sequence)
fig, axes = result.compare(sequence, index=0)
```

The second prediction in this two-step sequence has no subsequent endpoint
label in the same sequence. Compare against the full loaded `timeline`, or select
a longer sequence, to include its forecast endpoint label. Reconstructed dataset events are retrospective
reference outcomes. Bare matrices require the caller to establish the same
forecast interval and spatial grid; valid target values must be exactly 0 or 1.
For a selected 2D target, an optional previous burned-area matrix and its mask
also have the selected 2D shape:

```python
fig, axes = result.compare(
    sequence["newly_burned_area"][1, 0],
    observed_valid=sequence["burned_area_valid"][1, 0],
    burned_area=sequence["burned_area"][0, 0],
    burned_area_valid=sequence["burned_area_valid"][0, 0],
    index=0,
)
```

In this example, sequence position 1 must be exactly one hour after position 0.
The previous burned area is optional for bare targets. When supplying full arrays,
both reference fields and their masks must have the complete probability shape.

The standalone `plot_comparison(probability, observed, ...)` requires identical
full array shapes and applies no timestamp alignment. Its options also apply
to `result.compare`:

| Comparison option | Default | Meaning |
| --- | --- | --- |
| `valid` | `None` | Complete-shape Boolean probability mask; `result.compare` supplies it. |
| `observed_valid` | `None` | Complete-shape Boolean event mask, or a 2D mask for a selected 2D target in `result.compare`. |
| `index` | `None` | Same matrix-selection rule as `plot_matrix`. |
| `burned_area` | `None` | Optional binary cumulative state at the prediction cutoff. `result.compare(sample)` aligns this automatically. For standalone plotting it must match the complete probability shape. |
| `burned_area_valid` | `None` | Complete-shape Boolean previous burned-area mask, or a selected 2D mask with a 2D bare target in `result.compare`. |
| `mode` | `"overlay"` | One combined panel by default. `"side_by_side"`: event and probability panels; `"both"`: those panels plus the combined panel. |
| `axes` | `None` | Existing panel axes in the selected layout; otherwise create them. |
| `titles` | `None` | Panel titles; supplied as an appropriate sequence, or one string for overlay. `result.compare(sample)` labels reconstruction explicitly. |
| `figsize` | `None` | Optional figure size; automatic size depends on panel count. |
| `cmap` | `"viridis"` | Probability colormap. |
| `unknown_color` | `"#d9d9d9"` | Unavailable probability display, and unavailable outcomes in the separate event panel. |
| `event_color` | `"#00e5ff"` | Color for positive events and their markers. |
| `event_label` | `"Newly burned in forecast interval"` | Legend label for positive reference events. Sample comparison supplies the next-hour or requested cumulative-horizon wording automatically. |
| `burned_color` | `"#8b5a2b"` | Color for area already burned at the cutoff. |
| `burned_alpha` | `0.65` | Opacity of the previous burned-area layer, between 0 and 1. |
| `marker` | `"o"` | Positive-event marker shape in overlays. |
| `marker_size` | `18` | Marker area in points squared. |
| `marker_facecolor` | `"none"` | Hollow next-hour event markers by default, preserving the underlying color inside; supply a Matplotlib color for filled markers. |
| `region_valid` | `None` | Boolean mask with selected `[H,W]` shape or the complete probability shape. Draws the physical loaded-region boundary while retaining the full grid extent. `result.compare` supplies its `pixel_valid` region automatically unless overridden. |
| `region_color` | `"#586a7a"` | Color of the loaded-region boundary. |
| `colorbar` | `True` | Probability colorbar. |
| Additional keywords | None | Forwarded to `imshow`; `vmin`, `vmax`, and `norm` cannot override the fixed 0–1 probability range. |

Every layer retains its own validity mask. The combined plot displays available
probabilities even where outcomes are unknown, marks known positive target events
even where probability is unavailable, and shows known previously burned cells
independently of both. It does not threshold the probabilities. Missing reference
values are omitted from their own layers; absence of a cyan marker therefore
does not establish a negative outcome where the reference is unknown. Close
returned figures with `plt.close(fig)` when generating many plots.

## Training and saving

`train_model(prepared_data, output_dir, *, family="exponential", config=None)`
uses an existing cache with `metadata.json`, `train.npz`,
`validation.npz` and `test.npz`. The cache fixes channels, categorical vocabulary,
kernel geometry and partition membership. Only the exponential trainer is
available through this convenience function. `WildfireModel.train(...)` retains
the same options as a compatibility entry point. Existing dedicated
training/search workflows retain their architecture and scientific controls.

Preparation, fitting and checkpoint loading are separate operations:

```python
from wildfire import prepare_training_data, train_model, load_model

prepared = prepare_training_data("runs/new_experiment/prepared", kernel_size=5)
trained = train_model(prepared, "runs/new_experiment/fitted")
restored = load_model(trained.checkpoint_path)
```

`prepare_training_data(output_dir, *, data_root=DEFAULT_ROOT,
channels=TRAINING_SOURCE_CHANNELS, kernel_size=3,
contact_negatives_per_event=5000, no_contact_negatives_per_event=2000, seed=7,
split_policy="weighted-cell-hour", validation_fraction=0.2, split_seed=7,
chunk_hours=None)` reads aligned event data independently of any fitted model,
writes a prepared cache, and returns its `Path`. `train_model` fits that cache;
it does not read the environmental rasters again.

| Preparation option | Default | Meaning |
| --- | --- | --- |
| `output_dir` | Required | Destination for the prepared cache; use a new or empty directory. |
| `data_root` | `DEFAULT_ROOT` | Root of the aligned environmental catalog and rasters. |
| `channels` | `TRAINING_SOURCE_CHANNELS` | Ordered source fields; categorical fields expand into complete one-hot groups. |
| `kernel_size` | `3` | Odd spatial patch width of at least 3 cells. |
| `contact_negatives_per_event` | `5000` | Maximum sampled negative targets per event with current burned-neighbor contact. |
| `no_contact_negatives_per_event` | `2000` | Maximum sampled negative targets per event without current burned-neighbor contact. |
| `seed` | `7` | Negative-sampling seed. |
| `split_policy` | `"weighted-cell-hour"` | Weighted stratified training/validation cell-hours; `"season"` selects the historical seasonal partition. |
| `validation_fraction` | `0.2` | Requested validation share under the weighted-cell-hour policy; strictly between 0 and 1. |
| `split_seed` | `7` | Training/validation split seed, independent of negative sampling. |
| `chunk_hours` | `None` | Read each event's complete available timeline during extraction; a positive integer uses bounded temporal chunks. |

Fresh `prepare` commands use the same independent preparation workflow and
complete event timelines by default. Pass `--chunk-hours 24` to the command, or
`chunk_hours=24` to `prepare_training_data`, for bounded temporal chunks while
covering the same hourly inputs and next-hour targets. This preparation setting
is separate from `load_data`'s 24-hour default window size. Preparing a cache
creates input data and partitions; it does not train a model.

`config=None` creates the following `TrainingConfig`:

| Field | Default | Constraint or meaning |
| --- | --- | --- |
| `epochs` | `30` | Positive maximum number of epochs. |
| `patience` | `6` | Positive early-stopping patience. |
| `batch_size` | `1024` | Positive patch batch size. |
| `hidden_channels` | `16` | Positive network width. |
| `learning_rate` | `0.001` | Finite positive optimizer rate. |
| `weight_decay` | `0.0001` | Finite nonnegative decay. |
| `seed` | `7` | Integer in `[0,2**64)`, excluding Boolean values. |
| `threads` | `4` | Positive CPU thread count; previous thread count is restored afterward. |
| `device` | `"cpu"` | `"cpu"`, `"cuda"`, `"mps"`, or `"auto"`. |
| `categorical_balance` | `"inverse-sqrt"` | Training-only category-presence adjustment; `"none"` disables it. |
| `categorical_balance_min_frequency` | `0.001` | Frequency floor for fitted category-presence weights. |
| `categorical_balance_max_factor` | `10.0` | Cap for category-presence weights. |

Integer settings exclude Boolean values. Normalization is fitted on training
rows, checkpoint selection uses validation, and the test report follows
selection. Validation and test metrics retain the original population weights.
`output_dir` must be new or empty.

`model.save(path, *, overwrite=False)` atomically saves resident parameters,
saved preprocessing and checkpoint metadata. Existing files are protected unless
`overwrite=True` is explicit. Saving performs no training or normalization fit.

## Heat and flame options

Heat and flame methods retain their complete physical options. Their data model
remains distinct from first-new-burn probability: cumulative burned state does
not imply currently active flame.

`model.heat_model(**physical_parameters)` reuses resident fitted weights. Its
parameters are those of `WildfireHeatModel`:

| Physical parameter | Default | Meaning |
| --- | --- | --- |
| `grid` | Required | `AffineGrid` with coordinates in metres. |
| `combustion` | Required | `CombustionParameters`: fuel loading, effective heat yield, consumed fraction and burning duration. |
| `radiative_fraction` | Required | Scalar or spatial source fraction. |
| `emission_height_m` | Required | Source height in metres. |
| `receiver_height_m` | `0.0` | Upward-facing receiver height in the same height datum. |
| `atmospheric_transmissivity` | `1.0` | Uniform path-independent scenario factor. |
| `interval_s` | `3600.0` | The maintained fitted endpoint must be exactly 3600 seconds. |
| `residence_time` | `None` | Optional `FlameResidenceTime` consistent with combustion duration. |
| `epsg` | `None` | Optional projected metric CRS for geographic outputs. |

The composed API supplies checkpoint/checksum/schema provenance automatically.
A directly constructed `WildfireHeatModel` additionally accepts
`predictor_provenance=None` for its own metadata dictionary.

`WildfireHeatModel.from_checkpoint(path, *, device="cpu",
**physical_parameters)` loads the same saved contracts for direct heat
integration. `heat_model.predict_sample(sample, *,
initial_burning_from_arrival=True, **current_burning)` accepts one spatial
snapshot, and its `predict_sample_details` counterpart retains all diagnostics.
Unlike `WildfireModel.predict(sample)`, the composed heat sample route requires
features in the exact saved checkpoint channel order. The independent
`TRAINING_SOURCE_CHANNELS` selection in the examples provides that order for the
maintained checkpoint; explicitly arrange channels before heat integration when
using another loader schema.

| Heat prediction option | Default | Meaning |
| --- | --- | --- |
| `initial_burning_from_arrival` | `True` for samples | Use sample arrival age and configured duration on known already-burned cells; set false to exclude sample timing. |
| `channel_names` | Required for raw inputs | Saved environmental channel order. |
| `burned_area_valid`, `feature_valid` | `None` | Complete-shape Boolean raw-input masks. |
| `initial_active_burning_probability` | `None` | Explicit present activity probability on known already-burned support. |
| `initial_remaining_burning_duration_s` | `None` | Remaining present-fire emission duration. |
| `arrival_time_s`, `current_time_s` | `None` | Alternative arrival/current times in seconds from a common origin. |
| `arrival_valid` | `None` | Arrival availability mask. |
| `unknown_new_burn_probability` | `None` | Separately justified probability estimate for unsupported cells; recorded as supplied estimates, rather than original predictions. |
| `probability_valid` | `None` for probability bridge | Validity of an externally supplied new-burn probability matrix. |
| `already_burned_mask` | `None` for probability bridge | Known old support, with first-new-burn probability zero. |

`heat_model.predict(burned_area, environmental_data, ...)` uses raw current
inputs. `heat_model.predict_from_new_burn_probability(new_burn_probability,
...)` uses a previously computed one-hour probability matrix and the bridge
options above. Every route has a corresponding `*_details` method. Regular
methods return `(expected_heat_flux_w_m2, coordinates)`; detailed methods retain
mean/endpoint activity, full/known-source heat, uncertainty bounds, incident
energy, coverage masks, completeness and provenance. Geographic tuple output
requires the relevant projected metric EPSG. A local grid can use the detailed
methods without geographic coordinates.

For active surface flames,
`model.predict_active_flames(burned_area, environmental_data, *, channel_names,
residence_time, grid, burned_area_valid=None, feature_valid=None)` forecasts one
snapshot. `model.predict_active_flames_sample(sample, *, residence_time)` uses
sample geometry and requires one valid, unpadded snapshot.
`result.endpoint.positions(min_probability=...)` selects centers with an
explicit threshold. `heat_details.endpoint_flame_map()` also includes continuing
old fire under the heat scenario. Retrospective arrival scenarios can be
computed explicitly through `active_flames_from_arrival(...)`.

The standalone `ExpectedHeatFluxModel` accepts `grid`,
`heat_release_rate_density_w_m2`, `radiative_fraction`, `emission_height_m`,
`receiver_height_m=0.0`, `atmospheric_transmissivity=1.0`, and `epsg=None`.
`predict(active_burning_probability)` describes instantaneous radiation from a
complete active-probability matrix. `predict_at_points(...)` accepts projected
receiver points and uses `target_chunk_size=128` and `source_chunk_size=1024`
to bound temporary arrays. Receiver height stays on the constructor's common
plane. Detailed counterparts return physical diagnostics. Fuel maps, combustion constructors,
residence scenarios, dose/power conversions and trapezoidal heat integration
remain in `wildfire.heat`. See the [heat guide](../README.md#heat-guide) and
[physical implementation](../wildfire/heat.py) for their scientific definitions.

## Migrating an existing caller

The recommended `model.predict(...)` now returns `Prediction`; replace raw
`probability, coordinates = model.predict(...)` with:

```python
result = model.predict(burned_area, environmental_data, **options)
probability, coordinates = result.probability, result.coordinates
```

`predict_coordinates(...)` retains the explicit raw-array tuple contract.
`predict_sample(...)` retains its sample tuple contract;
`predict_details(...)` and `predict_sample_details(...)` retain the low-level
`BurnProbability` diagnostic result; `predict_proba(...)` retains the
probability-only tensor. These adapters preserve existing numerical options,
while the new structured call adds result metadata, plotting and comparison.

Loading and catalog discovery have been removed from `WildfireModel`. Replace
`model.sample(event, cutoff)` with independent loading followed by
`select_time(timeline, cutoff)`, and replace `model.load_data(...)` with
`load_data(...)`. Import `available_events` and `available_cutoffs` directly from
`wildfire`. The loader retains the 24-hour window default; pass
`sequence_length=None` to request a complete selected event timeline.
