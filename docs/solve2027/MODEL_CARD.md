# Model card: forecast checkpoint c651

The forecast is WildfireGuardian's only learned component; routing and checking are search-and-check algorithms ([README](../../README.md#how-the-system-works)). This card describes checkpoint c651 as it is on `Main`. Every number is copied from the linked file.

| | |
|---|---|
| Identity | SHA-256 `c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843` ([docs/RELEASE_IDENTITY.json](../RELEASE_IDENTITY.json)) |
| File | `forecast/runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt`, the package's `DEFAULT_CHECKPOINT` ([forecast/wildfire/paths.py](../../forecast/wildfire/paths.py)) |
| Architecture | `MixedNonnegativeKernel`: 3×3, 5×5, 7×7 and 9×9 environmental CNN rate branches, "giving maximum 9×9 context"; 19 ordered environmental input channels ([forecast/README.md](../../forecast/README.md#quick-example)); `trainable_parameters` 210344 (training record below) |
| Output | Next-hour new-burn probability per 375 m cell, EPSG:5179 ([planner architecture §1](../../planner/docs/ARCHITECTURE.md#1-fixed-facts-do-not-change)) |
| Used by | `wfg_latest` 1.0.0 with kit v3, the frozen research reference. The Route-Check API serves recorded c651 outputs and "does not re-run the forecast" ([api/README.md](../../api/README.md#what-it-is)) |

## Intended use

- Turn the current burned area and environmental inputs into next-hour new-burn probabilities. The integration then draws scenario members from them, and every candidate journey is checked against those members ([decision card](DECISION_CARD.md)).
- Retrospective research and pre-season planning. Every planner screen states: "Planning aid only — not for live evacuation operations."

**Out of scope:** live forecasting or evacuation command; flame-timing or perimeter truth ("A 375 m grid and one-hour output spacing do not establish 375 m information content, one-hour timing accuracy, or operational forecast skill"); measured heat ("The radiation calculation has not been calibrated against measured wildfire heat flux") ([forecast/README.md](../../forecast/README.md)).

## Inputs

The model reads the current cumulative burned state plus 19 ordered environmental channels. The ablation methods list their families: weather ("temperature and both wind components"), slope, tree cover and biome ("fourteen one-hot indicators") ([methods](../../research/forecast/FORECAST_ABLATION_METHODS.md#controlled-component-removals)). Rate kernels act on currently burned neighbours: "A completely unburned source neighborhood receives structural-zero probability when required environmental context is available" ([forecast/README.md](../../forecast/README.md#quick-example)). External environmental rasters are not bundled ([data and rights](../DATA_AND_RIGHTS.md)).

## Training and evaluation data

- **c651's own training record** (entry `mixed_3_5_7_9_02_lr0.1_warmup_cosine` in [candidate_selection.json](../../forecast/runs/20261010_categorical_balanced_benchmark/candidate_selection.json)): `trainable_parameters` 210344, `train_sample_count` 158561, `validation_native_sample_count` 39776, `epochs_completed` 512, `best_epoch` 5, `validation_common_brier` 0.02604917580813561, `test_used_for_selection` false.
- **Data partition** ([methods](../../research/forecast/FORECAST_ABLATION_METHODS.md#fitting-and-model-selection)): "199,185 sampled training cell-hours and 49,900 validation cell-hours across 25 development fires"; the test cache holds "61,965 sampled cell-hours from eight entirely held-out fires, including Korean events KFS_01 (Uiseong) and KFS_04 (Sancheong)". The partition "has been examined historically, so the study is a retrospective component ablation, not a newly hidden confirmation test". KFS_01 is also the fire group of the planner's two demo regions ([planner architecture §1](../../planner/docs/ARCHITECTURE.md#1-fixed-facts-do-not-change)).
- **Labels** are "retrospective reconstructed hourly burning", not observations ([evidence handoff](../../research/forecast/FORECAST_EVIDENCE_HANDOFF.md)).
- **Selection record.** c651 is one of the 276 kernel candidates of its benchmark run, whose report states "Validation selected **mlp 7x7** among the searched configurations" ([report](../../forecast/runs/20261010_categorical_balanced_benchmark/report.md)). c651 is the configured default; this card does not reconstruct why it was chosen.

## Metrics, exactly as recorded

Held-out test cells with a burned cell inside their 9×9 neighbourhood (the native-9-contact population: "45,391 sampled rows across eight fires; 12,030 Korean rows across Uiseong (KFS_01) and Sancheong (KFS_04)"), from the [frozen forecast ablation](../../research/forecast/ABLATION_RESULTS.md#component-comparison):

| Model | Korean Brier ↓ | Eight-fire Brier ↓ | Korean AP ↑ | Korean F1 ↑ |
|---|---:|---:|---:|---:|
| **Selected original checkpoint (c651)** | **0.137756** | **0.034181** | **0.2325** | **0.0752** |
| Zero probability baseline | 0.142240 | 0.035186 | 0.1422 | 0.0000 |
| Training-prevalence baseline | 0.139355 | 0.034556 | 0.1422 | 0.2491 |
| Global-neighbor baseline | 0.137999 | 0.034191 | 0.3922 | 0.1671 |
| Full 3/5/7/9 model, fresh fits | 0.138679 | 0.034290 | 0.2473 | 0.2385 |
| 9×9 only, fresh fits | 0.129552 | 0.032759 | 0.4352 | 0.4407 |

- Fresh-fit rows "average three separately scored seeds; the original checkpoint and no-learning baselines have one export". "F1 is threshold-dependent and is not a universal accuracy percentage."
- c651's Brier scores are below the three no-learning baselines by small margins. Its Korean AP is below the global-neighbor baseline's, and its Korean F1 is below the training-prevalence baseline's.
- **Four-scale superiority is not established.** "The four-scale architecture was not shown to outperform its smaller alternatives." The 9×9-only model's pooled paired Brier difference against fresh full-model fits was −0.00153037, with a whole-fire bootstrap 95% interval of [−0.00462920, +0.00001400] that "includes zero". The Korean comparison rests on two fires: "The two-fire Korean result has no reliable incident-generalization interval."
- Accuracy is not a useful score here: "predicting no new burning achieves about 99.66% ordinary accuracy".

## The failed primary superiority criterion (a different model)

A later frozen forecasting study selected a different model, `d4_wind` (checkpoint `33c5b3cfc1332940a905da80b9414d0a5a91aad06d8797b46dc151e893de48a3` in [RESULTS.json](../../research/next-combined/canonical-summary-691cc162/RESULTS.json)), to test whether it beats simple baselines. On "six US fires / 273 windows" it had raw Brier 0.0049268862 and AP 0.05425462. Its Brier-difference interval against persistence, [-0.0001376572, +0.0000228664], includes zero. Its lowest-bin calibration gap, 0.00407585, is worse than best dilation's 0.00154577. "**The frozen primary superiority criterion is false**". The Korean cohort retains "33 windows: 26 scored and seven unavailable" ([README](../../README.md#forecast-evidence), [combined assessment](../../research/next-combined/README.md)). There was "no checkpoint promotion", so c651 remains the default. These are **not** c651's metrics.

## How the forecast reaches the route checks

Each check uses "one scenario set of 4 members". Besides the fire already burning at the input time, each member's new ignitions are independent per-cell draws from c651's next-hour probabilities, at uniform times within the one-hour horizon (`draw_ignitions` in [bridge.py](../../integration/src/wfg_latest/bridge.py)). In the 15 evaluated routing windows, "native-q validity ranges 6.4–73.3%; explicitly assigned missing-q zero ranges 26.7–93.6%". The report adds that "seven of 15 windows contain no positive native future q, and eight contain no sampled new ignition in all four members" ([independent report](../../research/routing/INDEPENDENT_REPORT.v1.md#scientific-interface-and-limits)). In those windows the checked hazard comes from the fire already burning, not from forecast ignitions.

## Limitations

- Reconstructed labels, few held-out Korean fires and a historically examined partition (above).
- No spotting beyond the 9×9 context: an unburned neighbourhood gets structural-zero probability.
- Radiation and heat: flame-front radiation v2 is under "**Physics HOLD**" ([README](../../README.md#current-research-status)); heat parameters are uncalibrated.
- The routing horizon is one hour after each recorded input time.
- General forecast superiority is not established, by this card's ablation or by the later study.

## Ethical considerations

- **Purpose versus evidence.** The project aims to help plan earlier assistance for residents who need more time to evacuate, including older adults. "The elderly-focused social contribution remains a motivation, not a measured reduction in injuries or deaths" ([future extensions](../FUTURE_EXTENSIONS.md)).
- **Over-trust.** A forecast that misses where fire spreads can let a route pass the model check. The system therefore keeps three verdicts, never calls a route safe, never counts `unresolved` toward a deadline, and is labelled a planning aid, not for live evacuation operations.
- **Data and privacy.** Road data are OpenStreetMap-derived under the ODbL with attribution. Real device recordings and personal data are excluded ([data and rights](../DATA_AND_RIGHTS.md)).
- **Open validation needs.** Testing with intended users and responders is future work: "Operational evaluation" in [docs/FUTURE_EXTENSIONS.md](../FUTURE_EXTENSIONS.md).
