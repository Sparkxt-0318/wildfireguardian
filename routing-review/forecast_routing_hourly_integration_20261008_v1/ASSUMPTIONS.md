# Explicit hazard construction assumptions

Date: 8 October 2026, Asia/Shanghai. Engineering study on KFS_02 Uljin, not an independent validation fire. `EXPERIMENT_FREEZE.json` and V2 remain preserved; `EXPERIMENT_FREEZE_V3.json` is the effective comparison-panel freeze. Its thirteenth sensitivity is exploratory because it was added after an earlier engineering smoke route; see the timestamp correction below.

The original forecast and radiation modules are preserved under `candidate/mentor_runtime/`. The separate `candidate/hazard_constructor.py` constructs declared research realizations. Every construction records mode, content-derived assumption ID, parent input/checkpoint hashes, cutoff, support counts, scenario law and physical scope. Original marginal/mean outputs are never relabelled as these constructed fields.

## Prediction endpoint and mapping

The original loader thresholds `arrival_time_hours.tif` to construct a cumulative state at the cutoff. The target is next-hour crossing of that estimated arrival endpoint in an at-risk cell. This raster is a published retrospective kriging reconstruction using full event histories and final perimeters, informed by VIIRS/Himawari detection histories. It is neither a directly observed first-flame-ignition time nor independent Korean field ground truth. One-hour label sampling and 375 m raster cells do not establish one-hour/375 m observational accuracy.

Research mode assumes this endpoint can be mapped to a hypothetical flame ignition event at the drawn event time. This mapping is explicit and unvalidated. Timing sensitivities test consequences inside the construction; they do not validate the endpoint mapping. The signed direct-convolution predictor returns a raw score and clipped [0,1] evaluation view. We use that original view as Bernoulli marginals without claiming it is calibrated on these development snapshots. There is no new training, new target population or changed model eligibility.

## Strict mode

Strict construction returns `UNSUPPORTED` with all-false joint support and NaN flux. It retains absent joint flame scenarios, absent current active state, unknown emitting sources and native hourly-mean thermal semantics as separate reasons. A masked placeholder is not a zero-hazard assertion. Strict mode does not infer flame from a probability threshold or assume that NaN means a non-emitter.

## Research baseline

There are four equal-weight constructed scenarios and seed 20261008. Each cell has one Bernoulli first-event draw. Draws are independent between cells and scenarios; conditional event times are independent uniform on [0,3600) seconds. Known original probabilities are preserved. Unknown future probabilities receive the declared value 0.5 throughout the finite raster; this is an assumption assignment, not recovered data or statistical imputation. Known previously burned cells have first-new-event probability zero, independently of their current activity.

All known previously burned cells are assumed actively burning at cutoff, with 300 seconds remaining in a 300-second phase. This deliberately crude initial state is not a history reconstruction. Current activity at unknown current-state cells is assumed absent; their future events remain governed by the assigned marginal. Neither assumption is established by the final-extent mask. Strict mode retains this missing information. An actual observed current-fire channel can later replace the assumption with a new version and new checks.

The native hourly horizon is exactly 3600 seconds. Twelve 300-second intervals are a conservative numerical representation of these hypothetical events, not a new predictive resolution. Hazard coverage does not extend beyond the native hour, including destination dwell.

## Illustrative physical parameters

| Parameter | Baseline | Meaning |
|---|---:|---|
| Dry fuel load | 10 kg/m² | Fuel per entire source ground-cell area |
| Effective heat of combustion | 18,000,000 J/kg | Released energy per consumed dry-fuel mass |
| Consumed fraction | 0.10 | Fraction consumed in this modelled phase |
| Burning duration | 300 s | Constant source HRR during this phase |
| Radiative fraction | 0.30 | Fraction of source HRR emitted radiatively |
| Emission height | 5 m | Fixed source plane |
| Receiver height | 0 m | Upward-facing receiving plane |
| Atmospheric transmissivity | 1 | Uniform path-independent scalar |

The original formula gives conditional HRR density `10*0.1*18e6/300 = 60,000 W/m²`, and radiant source density 18,000 W/m². These are study anchors, not Korean measurements. The finite-cell radiation model computes the exact solid-angle transfer for uniform emitting parallelograms at fixed height to receiver cell centers. It includes all raster sources with no distance cutoff or kernel normalization. Outside-domain emission is excluded explicitly. Terrain shielding, convection, flame geometry, smoke-dependent path loss, human/vehicle shielding and uncertainty in physical parameters are not supplied by this model.

Each grid cell's flux is the cell-center value used as a spatially constant routing surrogate. The interval enclosure is temporal at those receiver positions; it is not a demonstrated spatial supremum over every continuous road position inside the 375 m cell. Flame contact is the binary constructed burning-source cell interpreted as contact throughout that cell. A real physical safety claim would require additional spatial and thermal validation.

## Conservative interval proof and limits

For a scenario, source `i` is active at time `t` with indicator `a_i(t)` and fixed nonnegative radiant density `r_i`. Let `K_ji>=0` be the original radiation transfer coefficient to receiver center `j`. Instantaneous flux is `F_j(t)=sum_i K_ji*r_i*a_i(t)`. On half-open interval `I_k=[b_k,b_(k+1))`, define `U_ik=1` exactly when source activity intersects `I_k`. Then `a_i(t)<=U_ik` for every `t in I_k`, so `F_j(t)<=sum_i K_ji*r_i*U_ik` by positivity. This covers ignitions/extinctions and every interior maximum. No endpoint sampling is used. Contact is the same source-union mask, so any contact in an interval forbids that interval's entire cell traversal/wait/dwell under the supplied routing contract.

The union can combine sources that never burn simultaneously. Its flux therefore can exceed the true supremum, and any-contact can block travel before/after the short real contact inside a bin. A feasible witness respects an overestimate for this constructed discretized model; a refusal cannot establish infeasibility under a finer event representation. Search optimality is relative to the interval surrogate and finite scenario set.

The proof is exact-arithmetic for the delivered physical operator. The original implementation uses float64 FFT convolution and solid-angle arithmetic. The constructor adds `1e-8*max(1,interval_peak)` W/m² and rounds upward once as a numerical guard. Independent direct summation and area-quadrature tests check agreement/enclosure. This is not a machine-verified interval arithmetic certificate for geometry/FFT roundoff; that limitation remains explicit.

## Expected occupancy check

For event probability `q`, conditional uniform ignition `T~Uniform[0,H)` and residence `D`, the expected occupied duration inside the horizon is `q*(d-d²/(2H))` with `d=min(D,H)`. Divide by `H` for mean occupancy. Current-active occupancy is its remaining duration divided by `H`. The construction makes current and new sources disjoint at known burned cells. Applying the original linear radiation operator to this occupancy gives analytical expected hourly flux under the uniform construction. Probability is applied once; scenario flux uses Boolean active sources rather than expected flux. The conservative interval upper fields are intentionally not expected means.

Four scenarios are not exhaustive and supply no real-fire coverage, chance constraint, calibration or independence guarantee. Equal weights are the declared finite study law; admissibility across these four members remains model-conditional.

## Frozen sensitivity panel and correction record

All cases use the same seed, source grid and original hourly forecasts at 03:00, 06:00 and 12:00 UTC on 4 March 2022. One dimension changes from baseline, except the dependent remaining-duration adjustment required to keep the same phase energy budget.

| Variant | Declared change |
|---|---|
| baseline | Values above |
| missing_zero | Unknown future q=0; explicitly assumed absence of future events |
| missing_one | Unknown future q=1; every unknown future source has an event |
| comonotone | Shared occurrence uniform per scenario; nested Bernoulli event sets, same cell marginals; conditional timing remains independent |
| timing_early | Every realized new event starts at 0 seconds |
| timing_late | Every realized new event starts at `nextafter(3600,0)` seconds |
| current_cold | Previously burned cells assumed inactive; remaining duration zero |
| current_short | Known previously burned cells active for 150 seconds |
| current_unknown_active | Every unknown current-state cell assumed active for 300 seconds; its constructed first-new q=0 to keep sources disjoint; raw forecast unchanged |
| fuel_half | 5 kg/m² dry fuel load |
| fuel_double | 20 kg/m² dry fuel load |
| duration_short | New phase 180 seconds; current remaining 180 seconds as the same-phase consistency rule |
| duration_long | New phase 600 seconds; current remaining remains 300 seconds |

The original freeze proposed `current_long=900` seconds at HRR normalized to a 300-second phase. The independent reviewer rejected it before route outcomes: it spends three copies of that stated phase energy budget. The unchanged original freeze records that rejected proposal. Effective freeze V2 replaces it with `current_short=150`; it also sets remaining 180 in the 180-second phase. Config validation rejects remaining duration greater than total phase duration. These are internal consistency repairs, not selection from routing results. The ranges are a sensitivity design, not calibrated plausible confidence intervals.

Freeze V3 adds an adversarial initial-state alternative on the 1,659 unknown current-state cells, before the comparison panel but after an earlier engineering smoke route. This tests the baseline's unknown-current-cold assumption. It presumes a hypothetical pre-cutoff event and current activity, not a recovered burned label. For source disjointness, those assumed-current cells have constructed first-new q=0 while original q/masks remain separate and unchanged. All 13 variants are fixed for the comparison panel; finite alternatives do not establish coverage of all possible initial states.

Timestamp correction: V2 was written at 17:02:15 UTC; the first native smoke construction was recorded at 17:04:23 UTC; V3 was written at 17:05:37 UTC on 7 October 2026 (8 October in Asia/Shanghai). Thus V3's additional `current_unknown_active` variant is post-smoke exploratory, not registered before every routing outcome. Earlier statements saying simply "before routing outcomes" were too broad. Original freezes remain unchanged. The original twelve variants, seeds, graph queries and budgets were fixed before the first route outcome; no outcome-driven budget or query changes were made. `evidence/PROTOCOL_TIMELINE_CORRECTION.json` records this limitation.

## Updates and provenance

Scenario IDs include the parent snapshot and construction assumption identity. A new cutoff constructs new realizations; reusing seeds does not establish a shared physical history. Integration must use the separately documented conservative exposure-history transfer or reject a remapping. Dose cannot be reset. Native file generation time, historical cutoff and assumed replay availability are separate fields. The reconstructed burned input uses future final extent/full history, so a causally ordered replay clock does not make that input historically live evidence.

Units: native flux is W/m²; adapter divides by 1000 to kW/m². Multiplying kW/m² by seconds gives kJ/m². Router budgets and thresholds remain the supplied contract values; this study does not invent a firefighter clinical exposure limit.
