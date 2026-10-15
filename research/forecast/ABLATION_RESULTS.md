# Final forecast ablation results

**All 51 frozen fits and the planned dynamics/thermal evaluations completed. The selected final checkpoint remains unchanged.**

This is a retrospective component study of the supplied final archive. It does not select a replacement for the integration model. The four-scale architecture was not shown to outperform its smaller alternatives.

## Evidence identity and sample size

- Authoritative archive: `wildfire 3 (1).zip`, SHA-256 `b9e000e8661128416fe7561690f78b1955d5a32189ac71536c1cd4110cd5dd65`.
- Selected checkpoint: `c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843`.
- 17 variants × three prespecified seeds = 51 independently fitted models, 512 optimizer steps each. Every final and initial checkpoint, prediction export and full fitting history is retained.
- Training: 199,185 saved cell-hours across 25 fires; all variants fit the same 158,561 native-9-contact rows. Validation: 49,900 saved cell-hours across those development fires. Test: 61,965 saved cell-hours from eight held-out fires.
- Primary native-9-contact test population: 45,391 sampled rows across eight fires; 12,030 Korean rows across Uiseong (KFS_01) and Sancheong (KFS_04). Their inverse-inclusion-weight masses are 287,415 and 47,469, respectively. These are weighted cell-hour populations, not additional independent fires.
- Separate dynamics panel: three prespecified cutoffs from each of Ulju (KFS_06) and Bukgu (KFS_13), two incidents total. They have no saved hourly-patch test rows.

## Component comparison

Weighted Brier error is the weighted mean squared difference between forecast probability and reconstructed binary next-hour outcome; lower is better. AP is average precision. Values below average three separately scored seeds; the original checkpoint and no-learning baselines have one export. No ensemble is substituted.

| Variant | Korean Brier ↓ | Eight-fire Brier ↓ | Korean AP ↑ | Korean F1 ↑ |
|---|---:|---:|---:|---:|
| Full 3/5/7/9 model | 0.138679 | 0.034290 | 0.2473 | 0.2385 |
| 3×3 only | 0.145554 | 0.035441 | 0.3005 | 0.4354 |
| 5×5 only | 0.135640 | 0.033865 | 0.3673 | 0.2264 |
| 7×7 only | 0.134304 | 0.033536 | 0.3467 | 0.2587 |
| 9×9 only | 0.129552 | 0.032759 | 0.4352 | 0.4407 |
| Without 3×3 | 0.132002 | 0.033139 | 0.3114 | 0.3372 |
| Without 5×5 | 0.147760 | 0.035743 | 0.2413 | 0.2367 |
| Without 7×7 | 0.137652 | 0.034077 | 0.3392 | 0.4088 |
| Without 9×9 | 0.141982 | 0.034770 | 0.3325 | 0.2735 |
| No temperature/wind input | 0.140962 | 0.034663 | 0.3000 | 0.3564 |
| No slope input | 0.146658 | 0.035551 | 0.2853 | 0.3722 |
| No tree-cover input | 0.163246 | 0.038332 | 0.2364 | 0.2319 |
| No biome input | 0.137508 | 0.034075 | 0.3862 | 0.0782 |
| No category balancing | 0.135661 | 0.033733 | 0.3849 | 0.2430 |
| Fixed mixing gains = 1 | 0.130749 | 0.033006 | 0.2611 | 0.2687 |
| Environment-independent kernels | 0.135191 | 0.033417 | 0.4801 | 0.0423 |
| No biome input or balancing | 0.139205 | 0.034341 | 0.2756 | 0.0587 |
| Zero probability baseline | 0.142240 | 0.035186 | 0.1422 | 0.0000 |
| Training-prevalence baseline | 0.139355 | 0.034556 | 0.1422 | 0.2491 |
| Global-neighbor baseline | 0.137999 | 0.034191 | 0.3922 | 0.1671 |
| Selected original checkpoint | 0.137756 | 0.034181 | 0.2325 | 0.0752 |

Classification thresholds were selected on pooled validation contact-9 rows and held fixed for test; F1 is threshold-dependent and is not a universal accuracy percentage.

## Main findings and uncertainty

- The 9×9-only model reduced mean Brier error by **6.58% on the two Korean fires** and **4.46% on the eight-fire pool**, compared with fresh full-model fits under the same training policy. The pooled paired Brier difference was −0.00153037, with a whole-fire bootstrap 95% interval of [−0.00462920, +0.00001400]. It includes zero. This is a promising descriptive result, not established general superiority or an instruction to replace the selected checkpoint.
- Removing tree cover increased Korean mean Brier error **17.72%**, removing slope increased it **5.75%**, and removing weather increased it **1.65%**. These are averages under one fitting policy; seed variation is substantial and the corresponding pooled uncertainty intervals include zero. They do not establish universal causal importance.
- Biome-input removal, category-balancing removal and fixed mixing gains did not worsen the primary mean Brier scores here. The data do not support claiming that every component improves prediction. Input-only biome removal retains biome-derived loss weights; the joint arm removes both.
- The environment-independent spatial kernel also outperformed the full model on Korean mean Brier and AP. The full model had lower Korean AP than the simpler global-neighbor baseline. Low Brier error alone is therefore insufficient to assert that environmental complexity or the proposed scale mixture is beneficial.
- Full-model seed 17 assigned certainty-wrong probabilities on **2,794 Korean and 3,627 pooled contact-9 rows**, giving infinite exact log loss. Floored log loss is reported separately and must not conceal that failure. The selected original checkpoint is a separate export and is not this retrained seed.
- The all-row test prevalence is approximately 0.34% after weighting; predicting no new burning achieves about 99.66% ordinary accuracy. We report Brier, AP, recall, calibration and per-fire results instead of promoting this trivial accuracy score.
- The two-fire Korean result has no reliable incident-generalization interval. Eight-fire intervals are exploratory, conditional on this fixed cohort, and unadjusted for multiple component comparisons.

## Computational cost

| Fresh model | Mean fit/validation/persistence time | Parameters | Mean saved-prediction export time | Mean lifetime host RSS |
|---|---:|---:|---:|---:|
| Full mixture | 92.76 s | 210,344 | 0.420 s | 5,388 MiB |
| 9×9 only | 37.18 s | 103,826 | 0.423 s | 5,209 MiB |

The 9×9 arm used **59.92% less measured fitting time** and **50.64% fewer parameters**. The export time did not improve. Fitting time includes fitting, validation and checkpoint persistence but excludes process startup, source/cache loading and training-only statistics. Export time includes saved validation/test patch prediction, preparation and writing; it is not one-map forecast latency. RSS includes the whole training process and is not total GPU memory. Timings are author process receipts on the native Mac, not independently retimed performance measurements. MPS used the declared CPU fallback required by a PyTorch operation.

## Recursive forecasts and Monte Carlo precision

All 72 recursive calls completed: six cutoffs × four trajectory counts (32, 128, 512, 1,024) × three seeds. Six fixed-state forecasts are represented by five new calls and one authenticated reuse from the original failed scorer attempt. The reused call has null inference timing. The independent common-mask checker found identical validity masks for every fixed/recursive comparison.

| Horizon | Fixed-state new-burning Brier | Recursive Brier, 1,024 trajectories, seed mean | Eligible cutoff-cell pairs | Positive pairs |
|---|---:|---:|---:|---:|
| 1 h | 0.010352 | 0.010357 | 194 | 2 |
| 3 h | 0.091954 | 0.091898 | 194 | 18 |
| 6 h | 0.125130 | 0.125041 | 194 | 25 |

These pooled, unweighted cutoff-cell comparisons reuse two incidents and are not independent samples. Recursive-state feedback made only small score changes on this panel and did not demonstrate a general accuracy benefit. Fixed-state exact log loss is infinite at all three pooled horizons: 2, 15 and 18 observed positive pairs received probability zero. The 1,024-trajectory recursive outputs retained these failures. A finite Monte Carlo estimate of zero is not proof of zero true model probability.

Average absolute difference from the same-seed 1,024-trajectory numerical comparator fell from **0.00991 at 32**, to **0.00463 at 128**, to **0.00181 at 512** trajectories. These averages cover the 54 case/seed/horizon comparisons per trajectory count. The comparator shares trajectory prefixes and is not truth; this demonstrates numerical convergence, not incident predictive accuracy.

## Thermal parameter sensitivity

The 32 planned scenarios completed on two cutoffs. Twelve numerical controls passed, covering zero-radiation output, nonnegative finite output and proportional response to consumed mass, radiative fraction and scalar transmission. Changing burning duration retained phase energy while changing how much energy occurred within the one-hour window. These are model-response checks rather than parameter fitting or thermal accuracy measurement. Original scenario choices are recorded in `DYNAMICS_PROTOCOL.md`; no routing thresholds were changed.

## Failure preservation and completion accounting

The original 55-command queue completed the archived-model export, 51 fits and training-only baselines (53 commands), then failed in the optional dynamics companion scorer because a singleton forecast batch axis did not match reference-array indexing. Its final independent-scoring command was NOT_RUN in that queue. Both outcomes remain recorded.

A separate main-scoring continuation completed the original scoring and final evidence checks. A separately hashed and independently source-reviewed V2 dynamics continuation normalized only the explicitly understood prediction batch axis and reused the successfully saved first fixed forecast. It completed the remaining original recursive, fixed and thermal work. The original queue, declarations, failed outputs and source files remain unchanged. There are **no unfinished planned scientific arms, no interrupted fits and no discarded scored fit outcomes**; completion is across these disclosed phases, not an uninterrupted original queue.

## Independent checks and publication boundaries

- All 51 predicted row identities, order, source/cache/checkpoint bindings and selected validation minima were checked. A second evidence checker recomputed **459 Brier scores with maximum discrepancy 0.0**. All 1,303 selected original source/assets and the supplied archive retained their hashes.
- Independent metric controls and original preflight failures are preserved. Dynamics output hashes, V2 plan identity and common masks were independently checked.
- The targets are retrospective reconstructed hourly burning within supported eventual-event perimeters. Training/validation share development fires; the held-out partition has been used historically, so this is not a newly hidden confirmation test. It does not establish external-landscape specificity or continuous flame timing.
- This study neither evaluates routing resolution nor demonstrates a novel routing algorithm, Rothermel superiority, operational safety, or calibrated model probabilities over all Korean fires.
- The integration checkpoint remains `c651f672…bd1843`. No new fitted model was adopted, no published default changed, and nothing was merged, pushed or deployed.

## Inspectable evidence

- `FORECAST_ABLATION_METHODS.md`: complete methodology.
- `FORECAST_ABLATION_RESULTS_PAPER.md`: concise English paper companion.
- `independent_scoring/`: seed, event, cohort, calibration, cost and bootstrap tables.
- `campaign/jobs/`: all initial/selected/final checkpoints, histories and raw predictions.
- `dynamics_v2/` and `review/dynamics_common_mask_v2/`: complete dynamics/thermal results and independent common-mask scores.
- `review/`: source reviews, evidence verification and interpretation checks.
- `figures/`: editable SVG and high-resolution PNG figures.
- `REPRODUCE.md`, `DELIVERY_MANIFEST.json`: reproduction and final custody.
