# Forecast v2: complete current assessment, negative primary result

The frozen primary model does not meet the prespecified superiority rule. All 273 prespecified eligible US2024 intervals (0 < duration <= 48 h) across six aligned catalog events were scored on 1,705,079 common cell-interval entries, including 8,520 newly mapped cells. Its paired Brier interval against persistence includes zero, and its lowest-bin calibration gap exceeds best dilation. No checkpoint is promoted; integration continues to use c651.

Independent saved-result, full 306-case census, FARSITE, publication-figure and descriptive-interval replays passed within their stated scopes. Absolute Brier/AP intervals below come from the separate fixed-method supplement; canonical scores and the primary rule remain unchanged.

| Model | Pooled raw Brier [95%] | Pooled AP [95%] | BSS versus persistence [95%] | BSS versus best dilation [95%] |
| --- | ---: | ---: | ---: | ---: |
| persistence | 0.004996836 [0.002934556, 0.006682701] | 0.004997 [0.002935, 0.006683] | 0.000000 [0.000000, 0.000000] | 0.961101 [0.952417, 0.973486] |
| dilation_best | 0.128456805 [0.106092967, 0.147106772] | 0.021768 [0.015684, 0.025568] | -24.707629 [-36.715881, -20.015939] | 0.000000 [0.000000, 0.000000] |
| logistic | 0.004858686 [0.002888861, 0.006442863] | 0.042943 [0.029672, 0.056866] | 0.027647 [0.009296, 0.036725] | 0.962176 [0.954115, 0.973745] |
| c651_mc | 0.009852197 [0.006824477, 0.012621251] | 0.031741 [0.020801, 0.043490] | -0.971687 [-2.463978, -0.476494] | 0.923303 [0.897821, 0.941653] |
| d4_wind_seed0 | 0.004926886 [0.002923498, 0.006528268] | 0.054255 [0.037407, 0.078988] | 0.013999 [-0.006717, 0.025083] | 0.961646 [0.953340, 0.973496] |

The primary remains D4 with local wind canonicalization, selected on the fixed 23-fire development comparison before current assessment. The fixed training-selected dilation expands one cell per 8 h. Its poor current score is retained. No heldout ranking changes either choice.

Primary pooled Brier minus persistence is -0.0000699497, with a 95% whole-fire percentile interval [-0.0001376572, 0.0000228664]. Against best dilation the difference is -0.1235299184 [-0.1413969883, -0.1028528880]. Both use 10,000 resamples of six complete fires, seed 20261030; negative favours the primary. The superiority criterion is false.

## Calibration and reconstruction

All lowest-bin comparisons use the fixed [0,0.1) bin on the common assessment population, with each model's own bin membership. The counts, observed frequencies and prediction means below preserve the different bin memberships.

- c651_mc: n=1,571,841; prediction=0.004425543; mapped frequency=0.002308121; absolute gap=0.002117422.
- d4_wind_seed0: n=1,703,148; prediction=0.000785152; mapped frequency=0.004860999; absolute gap=0.004075846.
- persistence: n=1,705,079; prediction=0.000000000; mapped frequency=0.004996836; absolute gap=0.004996836.
- dilation_best: n=1,482,112; prediction=0.000000000; mapped frequency=0.001545767; absolute gap=0.001545767.

All 33 Korean2025 reconstruction windows across four catalog events were attempted. Twenty-six were scored on 1,792 supported entries with 404 positives; seven KFS_01 windows have no common supported cells. The cohort is HOLD. Its canonical metrics describe the supported subset, and its complete-cohort descriptive interval supplement remains unavailable. Korean reconstruction is never pooled with US mapped extent.

## Evidence and figures

The canonical report is RESULTS.json; per_fire.csv retains all 16 models, six fires and required metrics. The heldout_ablation object retains all seven intended variants on exact common cells. Development values are absolute scores on each model's own support; paired common-cell development contrasts are unavailable. Original report/figure bytes and original layout failures remain preserved. The publication set changes only Figure 3 margins and Figure 5 label wrapping, with identical statistics and example selection; the other three pairs are exact copies.

All 30 stored FARSITE scenarios remain in FARSITE_SCORES.json: 29 common-subset comparisons and one interval longer than 48 h retained unavailable. No native execution occurs. Each native horizon/right-censor rule is authenticated. These deterministic station-weather, nonburnable-padded scenarios differ from current spatial-cutoff-weather/zero-exterior forecasts and never supply a full-cohort superiority claim.

The 12 fixed mean-field/MC cutoffs produce all 66 required rows: 56 have shared known support and 10 remain unavailable. Figure 4 keeps all horizon positions and missing points. Six dependent Korean cutoffs represent three catalog events. Active means either probability exceeds 0.001, not physical flaming. Five fixed-horizon rows reuse one joint 24 h API call per cutoff; six US survey-endpoint calls are separate. Call costs exclude preparation/model loading/lease wait and are host-specific. Multi-step mean field is a closure approximation, not exact Monte Carlo expectation.

## Scope and limits

Use the fresh pinned work/venv-forecast interpreter, NumPy 1.26.4, SciPy 1.13.1, sklearn 1.5.2, torch 2.5.1, CPU threads 2. Exact commands, seeds, hosts, input/checkpoint/source hashes, exits and application lease bookends are in executions/. Freeze 6887 precedes first inference, and all 223 frozen files remain unchanged through both cohort commands and subsequent reporting. US exit 0 and KR exit 1 are retained separately. The final regression has 3,507 passing tests and 367 release identities. Separately, the descriptive tool passed 77 invented-data relocation tests and independent source/arithmetic controls. Counts from different suites are not pooled.

Targets are mapped extent or arrival reconstruction, not flames. No complete survey coverage footprint is available. Archived event rectangles and cutoff weather are retrospective, with operational as-of availability unestablished. Weather repeats from cutoff. Unknown support remains unknown, including the seven unavailable Korean windows. Small aligned cohorts, one archive, a finite three-epoch budget, one development/training seed, and one 1,024-trajectory MC realization limit inference. Whole-fire intervals condition on these fixed predictions, support and references, not training-seed uncertainty.

Point fuel residence, an hourly lattice, midpoint ignition and initial-age proxies are coarse; short residence can alias the source schedule. Local learned smouldering can persist indefinitely, without an energy-conservation or physical-extinction law. Spotting is emitted only during the flaming window and uses a coarse domain-mean wind scenario; prior smouldering-inclusive runs are retained as historical variants. Invalid-geometry sensitivity changed zero labels on the declared 375 m cell-centre grids, which does not validate physical boundaries or survey coverage. No physical-flame, evacuation-safety, calibrated-joint-forecast or universal-speed claim follows.

The exact seven final checkpoints and existing c651 are frozen in MODEL_SELECTION.json, BLIND_REGISTRY.json and the prospective protocol. The protocol is READY_FOR_OWNER_REGISTRATION; actual 2026 execution remains NOT_READY. Future release chronology, independent ignition-year evidence and independent documentary clearance remain prerequisites. No OSF registration, future-data access, default promotion or merge is performed.

## Fit population and fixed budget

The fire/year split was frozen before fitting: 23 aligned US fit events from 2020-2023, with no aligned 2023 event available, and Korean reconstruction inputs through 2023 for the mixed regime. All 2024 US events and all 2025 Korean events were withheld from development. SPLIT.json retains every included event and exclusion.

All 21 intended development fits and seven final fits completed. Development uses the predeclared first three eligible intervals per fire/source kind and three year folds. Each of six pure final variants used all 1,303 eligible perimeter inputs for each of three epochs. Mixed training adds 3,088 SD-weighted hourly reconstruction inputs: 4,391 attempts per epoch, 4,376 optimizer updates and 15 explicitly logged source-unsupported windows. Attempted coverage differs from optimizer coverage; no unsupported batch becomes a zero-error result.

The three development spotting phases and one full spotting phase were rerun fresh under the corrected flaming-only emitter law with the same frozen budget/seeds. Earlier smouldering-inclusive phases remain historical and do not satisfy intended completeness. Historical pure membership is source-derived schedule inference bound to immutable producer/cache identities; newly instrumented mixed attempted IDs are runtime evidence. The canonical [FIT_COVERAGE.json](FIT_COVERAGE.json) passed all intended phases. This is conditional source/cache evidence, not universal loader equivalence.

Development selection uses equal-fire Brier. Pooled development and equal-fire values have different weights. Exact common scored coordinates were not saved, so no paired common-cell development effect is inferred.

| Variant | Mean fire Brier, selection criterion | Pooled Brier | Parameters |
| --- | ---: | ---: | ---: |
| Base | 0.040321559 | 0.043309534 | 26,018 |
| D4 | 0.038817948 | 0.046971023 | 26,018 |
| D4 with local wind | 0.037495116 | 0.040814821 | 26,018 |
| Ellipse prior | 0.041327574 | 0.045037051 | 26,018 |
| Burnout | 0.038401654 | 0.042176448 | 26,019 |
| Burnout with flaming-only spotting | 0.038446229 | 0.042240116 | 26,023 |
| Mixed training | 0.046886875 | 0.046095678 | 26,018 |

## Measured call totals and model sizes


| Measured call group | Calls per method | MC seconds | MF seconds |
| --- | ---: | ---: | ---: |
| Joint 24 h, reused by five horizon rows | 12 | 6615.072762 | 1.208495 |
| Separate fractional US survey endpoint | 6 | 794.039478 | 0.790442 |

Fixed-horizon MC uses public predict_cumulative with kernel caching disabled; the separate fractional helper enables it. These are distinct execution paths, not uniform per-horizon timings. Timing excludes preparation, model load and lease waits.

| Intended final variant | Parameters |
| --- | ---: |
| base | 26,018 |
| d4 | 26,018 |
| d4_wind | 26,018 |
| ellipse | 26,018 |
| burnout | 26,019 |
| burnout_spotting | 26,023 |
| mixed_base | 26,018 |

Recorded host: macOS 27.0.1 arm64, Python 3.12.1; two configured numerical threads.

## Heldout structural comparisons

These are fixed secondary comparisons on the same US common cells. They do not reselect the primary. Negative difference favours the variant.

| Variant | US pooled Brier | AP | Brier minus base [whole-fire 95%] |
| --- | ---: | ---: | --- |
| base | 0.004904044 | 0.047286 | Reference |
| D4 | 0.004936285 | 0.048222 | 0.000032241 [-0.000058394, 0.000098065] |
| D4 with local wind | 0.004926886 | 0.054255 | 0.000022843 [-0.000026116, 0.000055524] |
| Ellipse | 0.004912258 | 0.051190 | 0.000008215 [-0.000047929, 0.000053409] |
| Burnout | 0.004900736 | 0.050460 | -0.000003308 [-0.000052436, 0.000034102] |
| Flaming-only spotting | 0.004890845 | 0.048201 | -0.000013198 [-0.000064181, 0.000025272] |
| Mixed training | 0.010599952 | 0.036961 | 0.005695908 [0.003168432, 0.007740852] |

All intervals use 10,000 whole-fire resamples of six fires, seed 20261030, conditional on fixed predictions. The separate descriptive interval supplement supplies absolute Brier/AP intervals without changing these contrasts.

The separate supplement retains all 16 models, five pooled diagnostic intervals and 32 paired AP comparisons, using the same 10,000 draw matrix and original multiplicity frequencies. All current US draws are defined. Korean complete-cohort intervals remain null. These descriptive intervals condition on the six frozen fire predictions and reference populations. The raw c651 Brier interval belongs to stored-probability Brier; its separate MC-variance-corrected point is not assigned that interval.

## Per-fire common-cell Brier

Point values below use the full declared US population. All 16 models and other metrics remain in per_fire.csv; these rows do not attach per-fire confidence intervals.

| Catalog event | Entries | Positives | Persistence | Best dilation | c651 MC | Frozen primary |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ID-BOF-000683_Wapiti_Wapiti | 494,121 | 3,744 | 0.007577091 | 0.143104624 | 0.010949225 | 0.007403745 |
| ID-BOF-000904_Goat | 191,108 | 438 | 0.002291898 | 0.085019989 | 0.005686087 | 0.002151056 |
| ID-BOF-001080_Lava | 258,470 | 662 | 0.002561226 | 0.113142724 | 0.016514520 | 0.002676491 |
| ID-SCF-240202_RedRock | 282,428 | 962 | 0.003406178 | 0.100779668 | 0.005118989 | 0.003347304 |
| WA-SES-000173_Pioneer | 251,039 | 956 | 0.003808173 | 0.142874215 | 0.008392509 | 0.003777098 |
| WY-BTF-002416_FishCreek | 227,913 | 1,758 | 0.007713470 | 0.168906556 | 0.010884743 | 0.007660538 |

## Stored FARSITE scenario subset

These points use the 29 matched scenario intervals and their common cells, separately from the 273-interval headline population. Weather, boundary and deterministic/stochastic differences remain explicit.

| Comparator | Matched-subset Brier | AP |
| --- | ---: | ---: |
| farsite_scenario | 0.029121208 | 0.053529 |
| c651_mc | 0.008687029 | 0.117214 |
| d4_wind_seed0 | 0.009027472 | 0.102604 |

The independent stored-result review does not reauthenticate original native ASC files or native timing. No native run or full-cohort FARSITE superiority claim follows.

## Mathematical implementation

Brier is a proper score, not a likelihood. Endpoint Bernoulli NLL is a diagnostic under the hazard/mean-field approximation. The continuous update is `p_next = p + (1-p) * (1-exp(-dt*lambda))`, using the maintained model kernel path and explicit validity. A binary single-step test matches the Monte Carlo transition expectation to 1e-9; multi-step mean field is a closure approximation. Unknown support is never filled with a known zero.

D4 uses 90-degree rotations and flips. Local wind canonicalization uses bilinear rotation and is approximate. The elliptical prior uses the documented Anderson relation with midflame wind in metres per second and a nonnegative learned residual. Burnout separates a finite flaming window from learned older-cell smouldering; only flaming cells emit the long-range branch. These are structural model assumptions, not field-validated combustion laws.

## Figures and detailed evidence

The publication pairs are separate from the immutable original render. Both formats were reviewed; the original clipping evidence and failed first publication-label render remain available.

- 1. Reliability, all 16 fixed models: [PNG](publication-render/20261031_v2/fig01_reliability_all_models.png), [SVG](publication-render/20261031_v2/fig01_reliability_all_models.svg).
- 2. Per-fire common-cell Brier: [PNG](publication-render/20261031_v2/fig02_per_fire_brier_paired.png), [SVG](publication-render/20261031_v2/fig02_per_fire_brier_paired.svg).
- 3. Heldout structural contrasts versus base: [PNG](publication-render/20261031_v2/fig03_ablation_forest_plot.png), [SVG](publication-render/20261031_v2/fig03_ablation_forest_plot.svg).
- 4. Approximation agreement and missing support: [PNG](publication-render/20261031_v2/fig04_meanfield_vs_mc_rmse_by_horizon.png), [SVG](publication-render/20261031_v2/fig04_meanfield_vs_mc_rmse_by_horizon.svg).
- 5. Same-window mapped extent and cumulative forecasts: [PNG](publication-render/20261031_v2/fig05_example_forecast_vs_perimeter.png), [SVG](publication-render/20261031_v2/fig05_example_forecast_vs_perimeter.svg).

Figure 5 is the frozen median-positive-growth example, not a score-selected illustration. Its display crop uses initial/later mapped extent; forecasting and scoring used the full fixed rectangle. All panels share the same window and 0..1 colour scale. Figure 4's missing points remain missing; its cutoff min/max band is not a confidence interval.

Full-precision canonical scores and all 16 per-fire tables are in [RESULTS.json](RESULTS.json) and [per_fire.csv](per_fire.csv). Separately specified absolute diagnostic intervals and paired AP descriptors are in [DESCRIPTIVE_INTERVALS.json](supplements/current_descriptive_intervals_output_20261031_v2/DESCRIPTIVE_INTERVALS.json). Their exact 10000x6 draw matrix has 445 observed multiplicity vectors with all original frequencies restored. [REQUIREMENTS_STATUS.json](REQUIREMENTS_STATUS.json) maps every mandatory run, baseline, ablation, metric and figure; [GATE_HISTORY.json](GATE_HISTORY.json) retains prior failures beside explicit resolutions.

## Commands and provenance

The execution receipts record the exact historical commands; existing output directories refuse replacement. They are not instructions to overwrite a completed run. Source, checkpoint, data and per-case hashes, seeds and host are retained with each attempt.

```sh
# Fresh pinned environment used by this study:
PY=../venv-forecast/bin/python
export PYTHONPATH=forecast PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
# Recorded finite fitting phases, with original attempts preserved:
"$PY" research/forecast-v2/scripts/run_campaign.py fits --attempt 3
"$PY" research/forecast-v2/scripts/run_campaign.py spotting-repair --attempt 5
"$PY" research/forecast-v2/scripts/run_campaign.py baselines --attempt 3
"$PY" research/forecast-v2/scripts/run_campaign.py compare --attempt 6
# Each original cohort command has its own receipt and exit:
"$PY" research/forecast-v2/scripts/score_cohorts.py --cohort us2024 --data "$DATA" --work "$DATA/campaign-work" --run "$RUN" --registry research/forecast-v2/BLIND_REGISTRY.json
"$PY" research/forecast-v2/scripts/score_cohorts.py --cohort korea2025 --data "$DATA" --work "$DATA/campaign-work" --run "$RUN" --registry research/forecast-v2/BLIND_REGISTRY.json
# Stored-output comparison and canonical reporting:
"$PY" research/forecast-v2/scripts/audit_farsite.py --data "$DATA" --assessment "$RUN/heldout" --out research/forecast-v2/FARSITE_SCORES.json
"$PY" research/forecast-v2/scripts/report.py --run "$RUN" --out research/forecast-v2
```

`DATA` is the verified task-local `work/data/forecast-v2`; `RUN` is `forecast/runs/20261030_perimeter_trained/execution_v3`. The source-supplied archive/member/NIROPS/Zenodo hashes and licenses are in [DATA_PROVENANCE.md](DATA_PROVENANCE.md). The literal executed sidecar command, including its exogenous authorization SHA, is preserved in [its execution receipt](executions/current_descriptive_intervals_actual_v2.json). A new guarded replay requires a new exclusive destination and explicitly bound authorization. The first sidecar attempt refused missing inventory bindings before array decode/output creation; its log, authorization and corrected closure remain preserved.

The prospective [registration protocol](../../forecast/documents/preregistration_blind_test.md) remains byte-identical to the pre-inference freeze. The current descriptive supplement was specified after that freeze and before final quality interpretation; it does not retroactively become an original scoring method or change the predeclared primary rule. Historical source-derived schedules, new mixed runtime attempted IDs and explicitly unsupported windows remain distinct evidence.

The final [source-packaging manifest](SOURCE_PACKAGING_POST_ASSESSMENT_20261031.json) preserves 235 receipt-bound source path/hash identities, including all retired spotting producers, with no unresolved source. It is a historical producer archive, not a substitute for the separate 223-file freeze, 654-input authorization or canonical/sidecar artifact bookends. [DELIVERY_INDEX.json](DELIVERY_INDEX.json) links the final metadata and review scopes.
