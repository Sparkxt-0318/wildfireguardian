# Matched M548 and FARSITE evaluation against NIROPS observations

This workflow compares the original poster model **M548** and the authentic
FARSITE simulator on the **same Fish Creek area, initial fire map, endpoint,
grid, and ordered scoring cells**. It evaluates independently interpreted
aerial infrared survey perimeters rather than the published kriging
arrival-time reconstruction. Neither a real model evaluation nor final plots
have been run as part of preparing this code.

## Run it

From this repository, use the existing virtual environment:

```bash
.venv/bin/python -m wildfire acquire-observed-data

.venv/bin/python -m wildfire evaluate-observed \
  --event WY-BTF-002416_FishCreek \
  --cutoff 2024-08-22T08:02:00Z \
  --endpoint 2024-08-23T02:14:00Z \
  --hours 18.2 \
  --n-samples 1024 \
  --seed 0 \
  --trajectory-batch-size 32 \
  --threads 4 \
  --output-dir runs/20261012_observed_m548_farsite
```

The explicit `--hours` argument must match the exact interval between two
recorded survey timestamps. The default pair is **18 hours 12 minutes**,
or **1,092 minutes**, according to the publisher's UTC records. The 47 Fish
Creek records contain no consecutive exact six-hour pair. The user selected
the actual recorded survey interval. Changing only `--hours` without matching
real endpoint surveys raises an error; the evaluator never interpolates or
rounds reference polygons.

The data-acquisition command resumes the existing partial download, validates
the published size and SHA-256, extracts Fish Creek's 47 polygons, and writes
`data/sources/nirops_95rj5d379g_v1/FishCreek.geojson` and `provenance.json`.
The complete public ZIP is **1,387,524,228 bytes** (about 1.39 GB). Extraction
temporarily needs approximately **2.1 GB more** disk space for the merged
shapefile; those temporary files are removed afterward. The selected GeoJSON,
original record IDs, UTC times, and provenance remain available.

Progress displays are enabled by default: M548 shows completed coverage and
trajectory-block transitions with elapsed time and ETA; FARSITE shows a spinner
and elapsed time without an inferred percentage. Add **--no-progress** to
disable them. Both displays write to stderr and use sparse plain lines when
redirected to a log.

The minute-corrected FARSITE engine has already been built locally at
`tmp/farsite_observed_source/src/TestFARSITE`. If it is missing, the evaluation
builds it from the existing pinned original source. On a new checkout, first
run these commands; a C++ compiler and `make` are required:

```bash
.venv/bin/python -m wildfire build-farsite
.venv/bin/python -m wildfire.farsite_observed_build
```

Use a **new, empty output directory** for each evaluation; existing run data
are never overwritten. The original M548 checkpoint must match SHA-256
`c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843`.
The original FARSITE binary and previous poster figures remain preserved.

## Reference and model semantics

Let `c` be the initial survey timestamp and `e` the later survey timestamp.
At each endpoint, the reference map is the rasterization of the cumulative
union of this incident's survey polygons with timestamps no later than that
endpoint. The initial map contains **no later survey polygon**. Rasterization
uses original 375 m cell centers in the complete cached EPSG:5070 rectangle;
no prediction-driven region selection, pixel cropping, or interpolation is
applied. The interval is exactly `(c,e]` according to the published times.

Two quantities are scored:

- **Future newly mapped burns:** cells outside the initial cumulative survey
  union that enter the cumulative survey union by the endpoint. Initial mapped
  burns are excluded from this quantity's scoring cohort.
- **Total mapped burned occupancy:** all cells in the cumulative survey union
  at the endpoint, including the initial mapped burns.

NIROPS perimeters are observation-derived interpretations of aerial infrared
imagery. The dataset describes progression and response activity, not a complete
record of physical burned area. It does not provide a flight-coverage mask
certifying unburned status throughout the rectangle. Therefore, a reference
zero means **not mapped within the cumulative survey extent**, under the
experiment's incident-perimeter completeness assumption. It is not certified
absence of fire, heat, or burning. The report and plots state this distinction.
The preexisting event rectangle itself was selected retrospectively from event
extent, so this remains a retrospective case study.

The publisher harmonized timestamps to UTC and sometimes estimated missing or
inconsistent acquisition times from filenames, metadata, and supplementary maps.
Its table does not identify those estimated records separately. Exact timing in
this workflow means exact agreement with the **published survey timestamps**,
not exact knowledge of physical fire arrival or aircraft acquisition time.

Both models receive the same rasterized initial survey map. M548 retains its
checkpoint preprocessing and runs 1,024 absorbing binary trajectories by
default. It makes 18 synchronous one-hour transitions followed by an exact
0.2-hour transition using its fitted exponential probability link. Newly
ignited cells contribute to spread in the next transition. This final partial
interval is a private evaluation extension; the ordinary public recursive
`predict_cumulative` interface still requires positive whole-hour horizons.

FARSITE runs one deterministic scenario, represented as a 0/1 occupancy map.
All initial mapped polygon boundaries are assumed active at restart. This is
not a calibrated FARSITE probability ensemble. Its documented fuel-moisture
scenario uses dead-fuel percentages 6/7/8 (1h/10h/100h), live herbaceous 60,
live woody 90, and foliar 100; cloud cover and spotting probability are zero.
These values are assumptions, not field observations.

Both models use the last cached whole-hour environmental snapshot at or before
the initial survey, **2024-08-22 08:00 UTC** for the default case. M548 repeats
its gridded cutoff covariates. FARSITE repeats its spatial station summary and
uses its physical landscape. No future environmental slices are read. The new
loader option `include_fire_labels=False` prevents opening reconstructed
arrival-time and uncertainty rasters. FARSITE's observed ignition path also
does not open reconstructed arrival labels.

The original FARSITE Unix port did not split parsed `HHMM` input times into its
separate hour and minute fields correctly. An isolated build corrects those
four assignments. An independent probe linked against the native reader checks
the actual loaded start, end, and 1,092-minute duration before simulation.
Legacy text summaries omit start minutes and can truncate a displayed final
minute; the exact native probe and numeric duration remain authoritative.
The code preserves source, executable, patch, and input hashes.

## Every metric and probability distance

`report.md`, `report.json`, and `summary.csv` include every scalar metric supplied
by the existing cumulative scorer for both quantities and both native/shared
cohorts. Calibration bins are included in `report.md`, `report.json`, and
`calibration.csv`. Shared model coverage is the primary comparison. No cells
are removed because a model makes an unfavorable prediction.

- Brier score, positive/negative-class Brier scores, mean predicted probability,
  prevalence, and counts/support diagnostics.
- Exact negative log likelihood, floored log loss, average precision,
  trapezoidal precision-recall AUC, and ROC AUC.
- Exact Bernoulli KL divergence, floored KL divergence, total variation,
  Hellinger distance, Jensen-Shannon divergence, Jensen-Shannon distance,
  Bhattacharyya distance, Wasserstein-1, and Wasserstein-2.
- TP, FP, TN, FN; precision, recall, F1, MCC, accuracy, specificity, balanced
  accuracy, and intersection over union at the explicit default threshold 0.5.
- Fixed-bin calibration counts, empirical mapped-extent fractions, and expected
  calibration error. Cells have equal evaluation weights; the two class-specific
  Brier scores and balanced accuracy explicitly describe class differences.

Exact infinite losses are retained, especially for deterministic FARSITE or
Monte Carlo probabilities equal to zero or one. Separate floored scores use
epsilon `1e-7`. Unsupported rank metrics and empty-cohort metrics remain
unavailable. For nonempty cohorts, classification diagnostics with a zero
denominator use the existing scorer's zero convention: precision, recall, F1,
MCC, specificity, and intersection over union. Counts and class support are
reported beside them. The classification threshold is not optimized on these
observations. M548's Monte Carlo intervals
describe simulation error, not uncertainty in the reference, model parameters,
or evaluation metrics.

These probability distances are cellwise distances between Bernoulli
distributions on `{0,1}` with unit outcome distance. Wasserstein-1/2 here do
**not** measure geographic displacement in metres.

## Generated files and plots

The completed output directory contains:

```text
report.md / report.json / protocol.json
summary.csv / per_event.csv / per_cutoff.csv / calibration.csv
reference.npz
m548_prediction.npz / farsite_prediction.npz
simulation/input_manifest.json / clock_verification.json
simulation/engine.log / outputs/
plots/manifest.json / model_index.csv
```

The previous report style is retained. **20 PNG/SVG figure pairs** cover both
quantities: metrics, all probability distances, reliability, ROC/PR curves,
coverage, event Brier scores, architecture summaries, eight classification
metrics, confusion matrices, and full-rectangle spatial comparison maps.
The reliability axis names the **NIROPS mapped-perimeter reference**. Both
models are identified by name and use identical ordered outcomes for curves.

Reference source: [Magstadt et al., NIROPS perimeter dataset, version 1](https://data.mendeley.com/datasets/95rj5d379g/1),
DOI `10.17632/95rj5d379g.1`, CC BY 4.0.
