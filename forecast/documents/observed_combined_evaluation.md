# Combined M548/FARSITE evaluation on observed test events

The command evaluates the original M548 checkpoint and authentic FARSITE on
every usable consecutive NIROPS survey interval from exclusively held-out
M548 test events. It also audits observation availability for all 44 local
events. Training and validation events cannot enter the evaluation.

The code is provided for the user to run. A plan is a read-only availability
audit; it does not run either model. A stored-results report recalculates scores
and plots from authenticated exports without running either model.

## Commands

Run from the repository root using the existing virtual environment. The
authentic NIROPS v1 ZIP is already present locally. If it is missing, acquire it
first:

~~~bash
.venv/bin/python -m wildfire acquire-observed-data
~~~

The full 324-interval evaluation is expensive. For a shorter diagnostic
comparison, select the shortest actual consecutive survey interval from each
eligible test event. Inspect that selection first:

~~~bash
.venv/bin/python -m wildfire evaluate-observed-combined \
  --intervals shortest \
  --n-samples 1024 \
  --seed 0 \
  --trajectory-batch-size 32 \
  --threads 4 \
  --reuse-results runs/20261012_observed_test_combined_progress \
  --output-dir runs/20261013_observed_test_shortest \
  --plan-only
~~~

Then run this six-interval test-only comparison by removing only the plan flag:

~~~bash
.venv/bin/python -m wildfire evaluate-observed-combined \
  --intervals shortest \
  --n-samples 1024 \
  --seed 0 \
  --trajectory-batch-size 32 \
  --threads 4 \
  --reuse-results runs/20261012_observed_test_combined_progress \
  --output-dir runs/20261013_observed_test_shortest
~~~

The shortest Wapiti interval is already complete in the source run and is reused.
The other five selected intervals will be simulated when the user runs this
command. Selection depends on the actual recorded durations and timestamps,
before inspecting predicted outcomes, scores, or saved success/failure status.
This is a smaller, different test cohort; it is not the full 324-interval result.

For the shortest single observed interval, use Fish Creek:

~~~bash
.venv/bin/python -m wildfire evaluate-observed-combined \
  --event WY-BTF-002416_FishCreek \
  --intervals shortest \
  --n-samples 1024 \
  --seed 0 \
  --trajectory-batch-size 32 \
  --threads 4 \
  --reuse-results runs/20261012_observed_test_combined_progress \
  --output-dir runs/20261013_observed_test_fishcreek_shortest
~~~

This interval is 4 hours 23 minutes, from 2024-09-09 02:15 UTC to 06:38 UTC.
Its duration remains the actual survey interval; no six-hour reference is invented.

To generate combined scores and plots using only the results already stored in
the interrupted source run, use:

~~~bash
.venv/bin/python -m wildfire evaluate-observed-combined \
  --intervals all \
  --n-samples 1024 \
  --seed 0 \
  --trajectory-batch-size 32 \
  --threads 4 \
  --reuse-results runs/20261012_observed_test_combined_progress \
  --report-only \
  --output-dir runs/20261013_observed_test_stored_report
~~~

For the audited 2026-10-13 source snapshot, this preserves the original plan of
324 intervals and scores its 25 completed Wapiti cases. The other 299 intervals
remain unavailable, failed, or incomplete. It executes zero new simulations,
does not extract surveys or build/run FARSITE, and writes a **partial** report
with exit status **1**. These available results cover Wapiti only; they do not
constitute completed validation on all six eligible test events. The command
still checks the original checkpoint, test split, source bindings and stored
exports before scoring.

To combine the two recent separated results, repeat the source option:

~~~bash
.venv/bin/python -m wildfire evaluate-observed-combined \
  --intervals all \
  --n-samples 1024 \
  --seed 0 \
  --trajectory-batch-size 32 \
  --threads 4 \
  --reuse-results runs/20261013_observed_stored_validation \
  --reuse-results runs/20261013_observed_test_shortest \
  --report-only \
  --output-dir runs/20261013_observed_merged
~~~

The saved 25 Wapiti cases and the six shortest-event cases share one identical
Wapiti interval. Their union therefore has **30 unique intervals** across six
held-out test events: 25 Wapiti intervals and one for each other event. Identical
event/cutoff/endpoint cases are counted once; conflicting duplicate exports are
rejected. Every source is authenticated, including the complete parent chain
for historical predictions copied into a newer reporting run. The original
case reports, references, predictions, and inference provenance are preserved.

Scores are recomputed from concatenated cell-interval entries, rather than
averaging the two reports' metrics. The 18 PNG/SVG combined figure pairs are
regenerated. This command runs zero new model simulations. It retains all 324
planned observed intervals and reports the other **294** as unavailable or
incomplete, so its status is **partial** and exit status is **1**. All six events
are represented, but Wapiti contributes more intervals; the completed subset
does not have the same event weighting or coverage as a full evaluation.

To continue the full evaluation with the updated implementation, retain all
intervals and use a fresh destination:

~~~bash
.venv/bin/python -m wildfire evaluate-observed-combined \
  --intervals all \
  --n-samples 1024 \
  --seed 0 \
  --trajectory-batch-size 32 \
  --threads 4 \
  --reuse-results runs/20261012_observed_test_combined_progress \
  --output-dir runs/20261013_observed_test_all
~~~

This reuses authenticated completed cases and calculates the remaining selected
intervals. The old source directory is preserved. The 2026-10-12 commands wrote
to that directory under the earlier implementation; rerunning those old commands
with edited code is rejected by its recorded code hashes. Use the source through
**--reuse-results** and write current results to a fresh directory.

Progress is enabled by default. The outer bar counts processed survey intervals,
including verified resumed cases and failures, and shows separate success/failure
counts. The M548 bar counts completed coverage and trajectory-block transitions;
it includes the full configured final block even when only some trajectories
enter the estimate. Both bars show elapsed time and count-based ETA. Intervals
and transitions can have different costs, so ETA is an estimate of remaining
time, not a guarantee.

FARSITE displays a spinner and elapsed time because the native engine supplies
no reliable percentage. Availability checks, survey extraction, pooled scoring,
and plot generation also display elapsed-time status. Displays use stderr,
refresh in place in a terminal, and write sparse plain lines when redirected.
Add **--no-progress** to disable these displays. This flag does not alter random
draws or results and can be changed when resuming the same implementation.

Each completed interval is saved separately. Repeating the same command verifies
and reuses completed case outputs; it does not simulate them again. Add
**--retry-failed** to retry failed or incomplete cases. Their old directories are
retained with a dated suffix. A partial or failed comparison exits with status 1
and records every failure; it does not claim that every planned case succeeded.

The output directory is bound to configuration, checkpoint, split, observation
archive, environmental inputs, and implementation hashes. Use a new output
directory when changing settings, inputs, or code. Planning and execution can
share a directory when all settings except the plan flag are identical.
The commands above use fresh output directories to preserve the previously
interrupted run bound to the earlier implementation.

Optional controls:

- **--event EVENT_ID**, repeated as needed, selects a subset of eligible test
  events. An unavailable event or any training/validation event raises an error.
- **--intervals first** selects the first chronological pair per eligible event.
- **--intervals shortest** selects one pair per eligible event, ordered by actual
  duration, then cutoff and endpoint timestamps to resolve ties deterministically.
- **--max-intervals-per-event N** selects N shortest pairs per event with
  **--intervals shortest**. With **--intervals all**, it selects the first N
  chronological pairs. Use a fresh directory for a different selected cohort.
- **--max-hours H** retains only actual survey pairs whose duration is at most H
  hours, before ranking or applying the per-event limit. It does not interpolate
  endpoints. Events with no remaining pair are excluded; an explicitly requested
  event with no eligible pair raises an error.
- **--hours H** retains only survey pairs whose actual duration is exactly H
  hours. It does not interpolate reference polygons or round times. There is no
  exact six-hour consecutive pair in the current eligible test data.
- **--n-samples N** changes the M548 trajectory budget; 1024 is the default.
  **--seed**, **--trajectory-batch-size**, and **--threads** are configurable.
  Stored exports from the source above require its original 1024-trajectory
  configuration. For a fresh 256-trajectory run, use a new output directory
  without that **--reuse-results** source; budgets are not silently mixed.
- **--reuse-results SOURCE_DIRECTORY** authenticates compatible completed
  exports from an earlier run and copies them into the new output. The source is
  immutable. Repeat the option to merge multiple sources. Matching cases with
  identical four-file export manifests enter once; conflicting duplicates are
  rejected. Reused historical cases retain authenticated parent provenance.
  Checkpoint, archive, saved partition, selected covariates, exact
  component/interval identity, Monte Carlo controls, native engine and clock,
  reference provenance, and export checksums are checked. Only the current or
  explicitly pinned historical prediction implementation is accepted. Historical
  predictions retain their original inference provenance and are labeled as
  stored historical results; they are not relabeled as newly simulated output.
- **--report-only**, with **--reuse-results**, generates metrics and combined
  plots from completed stored exports only. Missing or incompatible cases do not
  trigger model execution. The selected planned cohort and every missing/failure
  entry remain visible, and incomplete coverage produces a nonzero exit status.
- **--case-plots** additionally writes 20 PNG/SVG figure pairs for each newly
  simulated interval, including spatial comparison maps. Reused exports do not
  regenerate missing case plots. The 18 pooled combined figure pairs are
  generated from both reused and newly simulated results unless **--no-plots**
  is supplied.
- **--threshold T** changes the classification diagnostic threshold, default
  0.5. The runner does not select a threshold from test outcomes.
- **--timestep-minutes**, **--timeout-seconds**, and **--engine** control FARSITE.
  The default timestep is one minute and timeout is 1800 seconds per case.

The original M548 checkpoint and authenticated prepared split are required.
Default paths are supplied. Use **--help** to inspect all path overrides. A
different checkpoint or modified split is rejected by this comparison command.
If the isolated minute-corrected FARSITE engine is missing, it is built from
the existing pinned source; building requires a C++ compiler and make. The
existing original engine and previous reports are preserved.

## Availability and strict test membership

The audit checks all 29 U.S. and 15 Korean event directories. The NIROPS archive
contains exact incident-component matches for all 29 U.S. events, but only
six have positive saved test counts and zero training and validation counts:

| Test event | Survey times in cached window | Consecutive intervals | Saved test rows |
|---|---:|---:|---:|
| Wapiti | 63 | 62 | 7,993 |
| Goat | 52 | 51 | 7,151 |
| Lava | 58 | 57 | 8,439 |
| Red Rock | 47 | 46 | 7,404 |
| Pioneer | 63 | 62 | 7,068 |
| Fish Creek | 47 | 46 | 7,398 |
| Total | 330 | 324 | 45,453 |

The actual durations range from 4 hours 23 minutes to 122 hours 55 minutes.
Together the cases require 10,534 hourly/final-partial M548 transitions per
trajectory, with 1024 trajectories per case by default. Completed cases are
retained so a long run can resume without repeating their simulations.

The shortest-pair selection uses these six actual intervals:

| Test event | Shortest duration | Rectangle cells |
|---|---:|---:|
| Wapiti | 12 h 46 min | 11,655 |
| Goat | 18 h 18 min | 4,964 |
| Lava | 19 h 50 min | 6,545 |
| Red Rock | 17 h | 7,812 |
| Pioneer | 15 h 3 min | 5,280 |
| Fish Creek | 4 h 23 min | 7,519 |

At the same trajectory budget, its rectangle-cell × hourly/final-partial-step
count is **631,610**, compared with **77,664,795** for all 324 intervals:
approximately **0.813%** of the full selection's Monte Carlo work surrogate.
This estimate excludes kernel preparation, reference preparation, FARSITE,
scoring, and plotting. It is not a wall-clock guarantee or evidence that the
smaller cohort estimates the full cohort's evaluation performance.

These counts describe candidates selected before geometry rasterization,
initial-fire, environmental-coverage, and native-simulation checks. The number
of successfully evaluated intervals can be smaller; the report records that
number and each failure.

The runner verifies the original M548 checkpoint SHA-256, all three original
prepared-array SHA-256 values, and checkpoint test-event membership. It accepts
the original cache metadata or the independently byte-verified consolidation
copy, whose old absolute source paths differ. Merely assigning a new directory
or an event name to a test split cannot bypass these checks.

Test membership is enforced at the event level. The observed survey pairs are
a new reference set within exclusively held-out events, rather than the
original one-hour cache rows. The saved test-row counts above establish
partition representation; they are not the number of evaluated cell-intervals.

Monthly MODIS MCD64A1 granules covering the area and month of all 15 Korean
events are available. This observation-derived product has approximately
500 m resolution and daily burn dates. The source audit verified granule
listings, not fire-specific detections or valid reference pixels.
These products cannot supply the subdaily NIROPS reference used here.
No authentic, usable subdaily progression perimeter archive has been acquired
for these Korean events, and their five FARSITE fuel/canopy inputs are absent.
KFS_01 and KFS_04 have saved test rows but fail those requirements; KFS_06 and
KFS_13 are declared test events but have no rows in the saved prepared arrays.
The audit retains these exclusions and coarser observation candidates rather
than presenting a Korean paired-model result.

See [the complete Korean source audit](korean_observation_availability_20261012.md)
and the generated availability JSON/CSV for event-specific evidence.

## Reference, time, and model semantics

The reference is the cell-center rasterization of cumulative, component-specific
NIROPS survey polygon unions on each original 375 m rectangle. Only polygons
published no later than the initial cutoff enter the initial map. The endpoint
uses polygons published no later than its survey timestamp. Component matching
keeps sibling fires that share an incident number separate.

Both models receive the same initial survey map, original rectangle, and exact
interval. The interval duration is derived from the two published UTC survey
times, in integer minutes. M548 makes synchronous one-hour transitions followed,
when necessary, by the exact final partial-hour transition through the existing
exponential link. FARSITE's native input reader is checked against the same
minute duration. The public recursive prediction API still requires positive
whole-hour horizons; partial hours here are an observed-evaluation extension.

M548 already uses Monte Carlo. It evolves binary absorbing states, and a newly
burned cell becomes a source in the following transition. The runner checks
every included export's recursive metadata, trajectory count, case-derived
seed, block size, empirical count lattice, standard errors, and confidence
bounds. Fixed-input predictions or incompatible exports are rejected. Eight
dedicated tests exercise the actual mixed 3/5/7/9 model wrapper and recursive
engine. The existing Fish Creek result also has probabilities exactly equal
to integer burn counts divided by 1024 on all 7519 valid cells.

For the original M548 checkpoint with repeated cutoff environmental conditions,
the runner now caches the fitted environmental preprocessing and generated
spatial kernels instead of recalculating them at every trajectory transition.
State updates still use the original configured full-block batch shape, binary
absorbing states, synchronous spread, and the same random streams. Verification
preserves the original Monte Carlo outputs bit for bit. A repeated-transition
microbenchmark using synthetic inputs with the actual checkpoint measured
approximately **12.6–17.7 times** faster transition evaluation. This measures
that kernel/transition calculation, not the complete observed evaluation's
wall-clock speed, and does not promise the same improvement for FARSITE,
preparation, reporting, other model families, or changing environmental forecasts.

FARSITE is one deterministic scenario, represented by 0/1 occupancy probabilities,
not a calibrated probability ensemble. The documented moisture scenario is
dead 1h/10h/100h: 6/7/8 percent; live herbaceous: 60 percent; live woody:
90 percent; foliar: 100 percent. Cloud cover and spotting probability are zero.
Initial mapped boundaries are treated as active at restart. These are scenario
assumptions, not measured moisture or active-flame observations.

Both models repeat environmental conditions from the last cached whole-hour
snapshot at or before each cutoff. No future covariates or reconstructed arrival
labels enter either prediction. Complete covariate files are hashed to bind
provenance, while prediction uses only the cutoff snapshot. Missing initial burned states are initialized unburned;
missing environmental inputs retain unavailable coverage. Exterior cells are
padded unburned, preserving the complete rectangular output size.

NIROPS maps are interpretations of aerial infrared observations. A reference
zero means not mapped inside the cumulative component union under a perimeter
completeness assumption. The publisher supplies no flight-footprint mask proving
physical unburned status throughout the rectangle. Some acquisition timestamps
were harmonized or estimated by the publisher without per-record flags.
The rectangle was selected retrospectively from event extent. These results
are retrospective held-out-event evidence against mapped perimeters.

The source is [NIROPS v1 on Mendeley Data](https://data.mendeley.com/datasets/95rj5d379g/1),
DOI 10.17632/95rj5d379g.1. The archive's recorded size and SHA-256 are verified.
Extraction uses one pass and temporarily requires approximately 2.1 GB additional
space; its six selected component exports and provenance are retained.

## Combined scoring and every metric

The two scored quantities are future newly mapped burns, excluding initial
mapped burns from the scoring cohort, and total mapped burned occupancy,
including initial mapped burns. Shared model coverage is the primary comparison;
native model coverage is also reported.

Combined scores are calculated from concatenated, equal-weight cell-interval
entries. The runner does not average interval AUCs, log losses, or calibration
errors. A cell repeated across intervals contributes once in each interval;
larger rectangles and more frequently surveyed events contribute more entries.
These entries are correlated. No independence claim or confidence interval for
evaluation metrics is made. Per-event and per-cutoff results show heterogeneity.

Every available scalar is exported, including:

- Brier score, positive/negative-class Brier scores, mean prediction, prevalence,
  and sample/support counts.
- Exact negative log likelihood, floored log loss, average precision,
  trapezoidal precision-recall AUC, and ROC AUC.
- Bernoulli KL, floored KL, total variation, Hellinger, Jensen-Shannon divergence
  and distance, Bhattacharyya, Wasserstein-1, and Wasserstein-2.
- TP, FP, TN, FN; precision, recall, F1, MCC, accuracy, specificity, balanced
  accuracy, and intersection over union at the configured threshold.
- Calibration bins and expected calibration error; reference eligibility,
  native coverage, shared coverage, and retention counts/fractions.

Exact infinite scores are retained. Floored scores use epsilon 1e-7 and are
labeled separately. Unsupported rank/empty-cohort scores remain unavailable.
Zero-denominator classification scores in nonempty cohorts use the existing
scorer's zero convention. Cellwise Bernoulli Wasserstein distances use outcome
distance on {0,1}; they do not measure geographic displacement in metres.

M548's standard errors and Wilson bounds describe pointwise simulation error,
not model-parameter, observation, or evaluation-metric uncertainty.

## Outputs and figures

~~~text
availability.json / availability.csv
protocol.json
report.md / report.json
summary.csv / per_event.csv / per_cutoff.csv / calibration.csv
intervals.csv
cases/<case-id>/report.json
cases/<case-id>/reference.npz
cases/<case-id>/m548_prediction.npz
cases/<case-id>/farsite_prediction.npz
cases/<case-id>/combined_case_manifest.json
cases/<case-id>/protocol.json
cases/<case-id>/reuse_provenance.json       # reused cases
cases/<case-id>/simulation/                # newly simulated cases
plots/manifest.json / model_index.csv
~~~

The readable report includes all scalar scores and figures. JSON and CSV exports
also include calibration bins. Every planned interval's success/failure is
recorded. Interrupted runs retain completed outputs for authenticated resume.

The combined result has **18 PNG/SVG figure pairs** in the previous report style:
metrics, distances, reliability, ROC/PR curves, event Brier scores, architectures,
coverage, eight classification diagnostics, and confusion matrices for both
quantities. Titles state that intervals are actual survey intervals. Reliability
axes identify the NIROPS mapped-perimeter reference.

Geographically separate events have no meaningful single shared spatial map.
Use **--case-plots** for the 20 figure pairs per newly simulated interval,
including its full-rectangle spatial comparison. This option can generate many
files for 324 intervals. Stored-only reports regenerate the 18 pooled figure
pairs; they do not run either model or recreate unavailable individual case maps.
