# Running and evaluating the FARSITE scenario

The workspace can run the authentic public FARSITE Unix-port source and score
its cumulative burned map at an explicitly entered duration. A single run
produces a deterministic scenario: each available cell has predicted burned
occupancy zero or one. These values are represented as degenerate Bernoulli
predictions so that the same classification, calibration, and probability
distance calculations used for the tensor and random-forest reports apply.
They are not calibrated fire-catching probabilities, and no Monte Carlo
standard errors or Wilson intervals are attached to this run.

## Engine identity and build

The integration uses the public
[mbedward/farsite Unix port](https://github.com/mbedward/farsite), pinned to
revision `4537d60ab013fa91d0b49d8efb385ffb1b3ddd13`. Its executable is built from
the upstream `Farsite5` implementation. This is a legacy source distribution;
the supported US Forest Service distribution includes FARSITE in FlamMap.
The official FlamMap desktop distribution runs on 64-bit Windows.
[US Forest Service FARSITE page](https://research.fs.usda.gov/firelab/products/dataandtools/farsite),
[US Forest Service FlamMap page](https://research.fs.usda.gov/firelab/products/dataandtools/flammap).

Run these commands from the workspace root:

```bash
.venv/bin/python -m wildfire build-farsite
```

Building requires Git, `make`, and a C++ compiler: Clang on macOS or GCC on
Linux. Initial source acquisition requires GitHub access. The default checkout
is `tmp/farsite_source`; the built executable is
`tmp/farsite_source/src/TestFARSITE`.

The build helper records the repository, exact revision, compiler, executable
SHA-256, and portability-patch SHA-256 in `build_manifest.json`. On macOS, the
patch replaces the upstream Linux backup-file copying API. Two invalid pointer
expressions are corrected for modern compiler compatibility. These documented
patches do not replace the fire-spread equations. The helper rejects additional
tracked source modifications. `build.log` and `portability.patch` retain the
build diagnostics and precise patch.

Optional build arguments are:

```bash
.venv/bin/python -m wildfire build-farsite \
  --source-dir tmp/farsite_source \
  --jobs 4 \
  --examples
```

`--examples` fetches the upstream flatland example inputs in addition to source.
It is not required to evaluate the cached FishCreek case.

## Six-hour evaluation command

This case uses cached U.S. landscape data for FishCreek, with a prediction
cutoff at `2024-08-21T06:00:00Z`. Change `EVAL_HOURS` to a positive whole number
of hours. Use a new or empty output directory to preserve previous results.

```bash
EVAL_HOURS=6

.venv/bin/python -m wildfire evaluate-farsite \
  --hours "$EVAL_HOURS" \
  --event WY-BTF-002416_FishCreek \
  --cutoff 2024-08-21T06:00:00Z \
  --output-dir "runs/my_farsite_${EVAL_HOURS}h"
```

For six hours, the exact endpoint is `2024-08-21T12:00:00Z`. Simulation and
reference alignment use that endpoint without rounding it to a later engine
time step. The input weather series includes an extra synthetic hour to support
native final-step integration; that does not extend the evaluation interval.

Additional evaluation controls are:

| Option | Default or purpose |
| --- | --- |
| `--data-root` | Cached environmental data root; normally `data/environment` |
| `--engine` | Optional existing `TestFARSITE`; it must match the pinned adjacent build manifest |
| `--source-dir` | Optional source checkout used to find or build the engine |
| `--dead-1h-percent`, `--dead-10h-percent`, `--dead-100h-percent` | Initial dead moisture: 6, 7, 8 |
| `--live-herb-percent`, `--live-woody-percent`, `--foliar-percent` | Live/foliar scenario moisture: 60, 90, 100 |
| `--cloud-cover-percent` | 0 |
| `--utc-offset-hours` | −7; explicit fixed whole-hour native clock offset; fractional offsets are rejected because this port cannot preserve start minutes |
| `--boundary-padding` | 1; a positive exterior buffer width in cells |
| `--timestep-minutes` | 15; at most 60 |
| `--distance-resolution-m`, `--perimeter-resolution-m` | 30, 60 |
| `--threshold` | 0.5; caller-selected classification threshold |
| `--timeout-seconds` | 900; maximum native execution duration |
| `--no-plots` | Omit PNG/SVG generation |
| `--plan-only` | Prepare physical input files, build provenance, and protocol without running the simulator or calculating scores |

For example, add `--plan-only` and use a different output directory to inspect
the declared inputs before execution. A planning directory is already populated
and cannot subsequently be reused as the scored output directory.

## Declared physical scenario

The landscape is assembled from eight cached physical layers on the original
375 m rectangle: elevation, slope, aspect, standard fire-behavior fuel-model
code, canopy cover, canopy height, canopy base height, and canopy bulk density.
These are the landscape themes documented by the
[US Forest Service FlamMap page](https://research.fs.usda.gov/firelab/products/dataandtools/flammap).
The cached fuel-model raster is the LANDFIRE 2016 FBFM40 layer. It is historical
landscape input for this scenario, not a newly measured 2024 fuel inventory.
No biome-to-fuel substitution is made. Unsupported standard fuel codes and
misaligned input rasters are rejected.

Terrain derives from the cached Copernicus GLO-30 digital surface model, whose
elevation can include vegetation and buildings; weather derives from the cached
coarse ECMWF IFS product mapped to this rectangle. These product-derived inputs
and their spatial aggregation are distinct from event-date field measurements.
The 30 m and 60 m native perimeter settings below do not increase the 375 m
landscape raster's physical resolution.

The defaults are explicit assumptions:

| Input | Default | Meaning |
| --- | ---: | --- |
| Dead 1-hour fuel moisture | 6% | Assumed initial percentage of dry fuel mass |
| Dead 10-hour fuel moisture | 7% | Assumed initial percentage of dry fuel mass |
| Dead 100-hour fuel moisture | 8% | Assumed initial percentage of dry fuel mass |
| Live herbaceous fuel moisture | 60% | Assumed scenario percentage |
| Live woody fuel moisture | 90% | Assumed scenario percentage |
| Foliar moisture | 100% | Assumed crown-fire scenario percentage |
| Cloud cover | 0% | Assumed clear-sky input |
| Spot ignition probability | 0 | Spotting disabled |
| Crown-fire method | Finney | Native engine setting |
| Native time step | 15 minutes | Integration setting; exact scoring endpoint still applies |
| Distance resolution | 30 m | Native perimeter-spread setting |
| Perimeter resolution | 60 m | Native perimeter-spread setting |
| Native processor count | 1 | Deterministic scenario execution setting |

The five supplied surface-moisture values are fixed **initialization inputs**.
Native dead-fuel conditioning may evolve dead moisture during the simulation;
the inputs should not be described as constant dead moisture throughout the
run. Live fuel moisture is a fixed scenario assumption. The distinction
between initial dead fuel moisture, conditioning, and live fuel moisture is
described in the
[official FARSITE weather-input documentation](https://owfflammaphelp62.firenet.gov/FARSITE/FARSITE_Wx_Inputs.htm).
None of these percentages is fitted to the evaluated endpoint or claimed to
be an event-date moisture observation.

The adapter reads only the cutoff weather slice. It averages temperature,
relative humidity, and precipitation over complete cells, and averages the
eastward/northward wind vector before obtaining wind speed and direction. This
single station summary is repeated through the simulation. Meteorological
direction is converted from true north to landscape grid north at the rectangle
centroid; metric units are passed through the native RAWS interface. This is a
spatially summarized, repeated-cutoff-weather scenario. It is not a gridded
wind simulation or a forecast weather ensemble.

The native solar and fuel-moisture clock uses an explicit fixed offset of
UTC−7, corresponding to Mountain Standard Time. For this example, the native
start is `2024-08-20T23:00:00-07:00`, and the six-hour native endpoint is
`2024-08-21T05:00:00-07:00`. This fixed standard-time convention is distinct from
the daylight-saving civil clock in August. The public case identities and
reference alignment remain in UTC.

Every polygon formed by the known cumulative burned cells at the cutoff is
supplied as an initial ignition perimeter. This is a **cutoff-perimeter restart
assumption**: it treats those boundaries as active at restart. A cumulative
burned raster does not establish the observed active flame front, fire age,
remaining combustible fuel, or suppression status. No reconstructed arrivals
after the cutoff are used to construct the ignition geometry or weather.

## Rectangle, missing data, and arrival import

The FishCreek rectangle is 103 rows × 73 columns. The engine receives one
additional nonburnable cell around each side, producing a 105 × 75 landscape.
The added exterior uses fuel model 99 and starts unburned. Import removes only
that known external buffer; all 103 × 73 original cells remain in the prediction
array. There is no inward cropping of the original environmental rectangle.

Missing initial burned observations are initialized as unburned on the real
rectangle. Missing environmental inputs remain unavailable. The engine treats
those gaps as artificial nonburnable barriers, and the corresponding returned
coverage cells remain false. This barrier assumption can also affect spread
around gaps; excluding their own cells from scoring does not eliminate that
scenario dependence. Source validity and assumptions remain in the input
manifest.

The **scored command requires complete physical environmental coverage** of the
original rectangle and rejects a case with any such gap. The lower-level input
builder can retain gaps and declare their mask, but that alone cannot bound the
effect of a barrier on fire arrival at other, known cells. The strict command
therefore does not report those partially supported runs as an evaluated model.

The native arrival raster uses minutes since the simulation start. The importer
requires its explicit UTC origin, a separate successful-domain coverage mask,
and the documented no-arrival sentinel `-9999`. Within known coverage, the
sentinel means that the simulator did not burn the cell by the completed run;
it is valid unburned output. Outside coverage it remains unavailable. Other
nonfinite or negative arrivals on declared coverage are rejected.

Let $B_i^0$ be the initialized binary cutoff state and $a_i$ the simulated
elapsed arrival in minutes. For a horizon $h>0$ hours, the imported fields are

$$
P_i^{\mathrm{burned}}(h)
=B_i^0\lor\mathbf1\{0\le a_i\le60h\},
\qquad
F_i(h)=(1-B_i^0)P_i^{\mathrm{burned}}(h).
$$

The arrival indicator is false for the no-arrival sentinel. Arrival zero is
included because it describes native ignition geometry. The union guarantees
that initial burned cells remain burned even if the engine's rasterization of
the polygon boundary differs slightly from the original raster. Their
future-new-burn probability is exactly zero, and total burned occupancy is
exactly one. Unknown or padded numerical outputs are NaN with false validity.

## Reference cohort and metrics

The reference is the cached retrospective reconstructed cumulative burned
state at the exact cutoff and endpoint. It is not a directly observed active
flame map. Its original observation-validity masks are retained; the simulator's
missing-initial-state initialization is not applied to reference truth.

New-burn evaluation uses cells known unburned at the cutoff and known at the
endpoint. Total-burned evaluation uses known endpoint states and includes
initial burns. Prediction coverage and padding are intersected with those
reference requirements. Known burned-to-unburned reference transitions are
rejected. There is no requirement that an evaluated cell initially contact a
burned neighbor.

The report uses the same pooled classification, Brier, log-loss, AP, ROC-AUC,
precision–recall, and fixed-bin reliability calculations as the learned-model
reports. A classification threshold of 0.5 gives the native zero/one scenario
classification. Reliability bins describe observed outcome frequency among
the scenario's zeros and ones; their existence does not establish probability
calibration. Undefined empty/single-class statistics remain explicitly
undefined.

All nine probability-distance fields are retained. For binary outcome $y$ and
prediction $p$, define $P=(1-y,y)$, $Q=(1-p,p)$, $M=(P+Q)/2$, and
$\mathrm{BC}(P,Q)=\sum_j\sqrt{P_jQ_j}$. Each reported value is an equal-entry
mean of the following per-cell quantity:

| Quantity | Definition |
| --- | --- |
| Exact KL divergence | $D_{\mathrm{KL}}(P\|Q)=\sum_{j:P_j>0}P_j\log(P_j/Q_j)$ |
| Floored KL divergence | The same directed KL after clipping $p$ to $[\varepsilon,1-\varepsilon]$, with $\varepsilon=10^{-7}$ |
| Total variation | $\tfrac12\sum_j|P_j-Q_j|=|y-p|$ |
| Hellinger distance | $\sqrt{1-\mathrm{BC}(P,Q)}$ |
| Jensen–Shannon divergence | $[D_{\mathrm{KL}}(P\|M)+D_{\mathrm{KL}}(Q\|M)]/2$ |
| Jensen–Shannon distance | Square root of each cell's Jensen–Shannon divergence |
| Bhattacharyya distance | $-\log\mathrm{BC}(P,Q)$ |
| Wasserstein-1 distance | $|y-p|$, with unit ground distance between outcomes 0 and 1 |
| Wasserstein-2 distance | $\sqrt{|y-p|}$, with the same ground distance |

Logarithms are natural. KL is directed from observed $P$ to predicted $Q$;
terms with $P_j=0$ contribute zero. A term with $P_j>0$ and $Q_j=0$ gives
infinity. Exact KL equals exact negative log likelihood for the binary target.
The square roots in Jensen–Shannon distance and Wasserstein-2 are taken before
pooling. These distances concern per-cell binary outcomes, not geographic
transport or distance between full joint fire-map distributions.

For deterministic $p\in\{0,1\}$ and error fraction $e$, Brier, total variation,
Hellinger, Wasserstein-1, and Wasserstein-2 all equal $e$. Jensen–Shannon
divergence equals $e\log2$ and its distance equals $e\sqrt{\log2}$. Exact KL/NLL
and Bhattacharyya distance equal zero for a perfect prediction and are infinite
if any positively weighted prediction is wrong. The report preserves those
infinities and separately labels the floored KL score; it does not smooth the
FARSITE map into artificial probabilities.

## Plot interpretation and comparison scope

The report uses the same PNG/SVG plot families as
`runs/20261011_forests_plots/plots`: pooled metrics, architecture summaries,
probability distances, reliability bins, per-event Brier scores, coverage, and
pooled ROC/PR curves, for both future new burns and total burned occupancy.
Plot labels identify the deterministic FARSITE scenario and do not claim a
trajectory sampling budget. A one-model architecture panel describes that one
scenario rather than a distribution of trained checkpoints.

With default plotting, there are 15 figures in both PNG and SVG: seven evaluation
figures for each of the two quantities, plus `farsite_spread_maps`. The spread
figure shows the entire original rectangle above a separately labeled visibility
zoom; the zoom does not change scoring support or saved prediction dimensions.

The output directory contains:

| File or directory | Contents |
| --- | --- |
| `report.md`, `report.json` | Written report, all metric/distance rows, protocol, execution status, and plot manifest |
| `protocol.json` | Exact UTC interval, duration, scenario identity, reference policy, and implementation hashes |
| `engine_build_manifest.json` | Pinned source/build identity and executable digest |
| `summary.csv`, `per_event.csv`, `per_cutoff.csv` | Scores for both quantities and native/shared cohorts; the cohorts coincide for a single scenario |
| `calibration.csv` | Fixed-bin descriptive reliability results |
| `prediction.npz` | Original rectangular prediction and validity fields, native arrival minutes, original reference states/masks/times, and JSON metadata |
| `simulation/input_manifest.json` | Full input units, geometry, source/generated-file hashes, clock, weather reduction, and assumptions |
| `simulation/landscape.lcp`, `scenario.input`, `ignition.*`, `cutoff_weather.raws` | Generated native landscape, scenario settings, cutoff perimeter, and repeated weather; all reside in `simulation/` |
| `simulation/command.txt`, `simulation/engine.log` | Native run command and execution diagnostics |
| `simulation/outputs/` | Raw arrival, perimeter, and timing outputs retained for auditing |
| `plots/` | PNG/SVG figures, `manifest.json`, and `model_index.csv` |

The evaluator validates native timing and arrival outputs in addition to the
process exit status: the engine can exit with code zero after an input error.
A failed run is recorded as failed in `report.json` rather than presented as a
completed scored scenario.

The previous saved 573-model demonstration evaluated KFS_06 in Korea at
`2025-03-24T03:00:00Z`, with a six-hour endpoint and eight trajectories per
learned model. This FARSITE example evaluates a different U.S. event and cutoff.
Scores from the two reports cannot directly rank FARSITE against those
checkpoints. The Korean cached data lack the required LANDFIRE physical fuel
layers, so the adapter rejects that event rather than assigning assumed fuel
models from biome classes.

A defensible direct comparison must run every participating model on the same
event, cutoff, endpoint, original grid, reference masks, and declared scenario.
It must recompute scores on the intersection of their prediction coverage.
If FARSITE uses a spatial station summary while learned models retain gridded
weather, that environmental representation difference must also be reported.
No scenario settings or classification thresholds should be fitted using the
evaluated endpoint.

The official
[FARSITE limitations and assumptions](https://owfflammaphelp62.firenet.gov/LegacyFARSITE/Tech_Limitations_and_Assumptions.htm)
describe sensitivity to fuels, weather, terrain, spatial resolution, and
propagated spread errors. This run evaluates the explicit cached-input restart
scenario against its retrospective reference; it does not establish
operational forecast skill or calibrated uncertainty.
