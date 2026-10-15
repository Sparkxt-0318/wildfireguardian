# Forecasting component ablation

## Experimental design

We evaluated the final environmental kernel model through 17 prespecified retraining configurations and three random seeds (7, 17 and 27), producing 51 completed fits. The full model combined independent 3×3, 5×5, 7×7 and 9×9 environmental CNN branches into a nonnegative transition rate. An exponential link converted this rate to the probability that a currently unburned cell became burned during the next hour. The 19 environmental inputs comprised temperature, two wind components, slope, tree cover and 14 biome indicators.

Every configuration used the same 158,561 complete training patches containing at least one burned neighbor within the 9×9 context. Smaller branch sets retained this complete input context and were evaluated on identical cell-hour identities; their comparisons therefore did not substitute different scale-dependent populations. Surviving hidden layers shared seeded initialization, while active output biases were reallocated to preserve the same initial aggregate rate per supported offset. Feature ablations set specified normalized model inputs to zero and retrained the model. They did not replace unknown data with observed zeros. All configurations retained the original inverse sampling weights for evaluation.

Each fit received 512 full-cohort AdamW optimizer steps. CNN branches used one hidden transformation of width 64, dropout 0.15, learning rate 0.1 and weight decay 0.01. The learning-rate schedule retained its original 4,096-step horizon, 32-step warmup and cosine decay. The best checkpoint was selected using population-weighted validation Brier score on the original common 3×3-contact cohort. Test outcomes were not used for checkpoint selection. The spatially constant control had no environmental neural layers or dropout. The frozen-mixing control fixed global branch coefficients at one; because branch magnitudes can absorb coefficient scaling, this tests optimization parameterization rather than an identifiable causal importance of each scale.

Training and validation comprised disjoint cell-hour rows from the same 25 development fires. The test partition contained eight fires absent from both development partitions. The primary 9×9-contact test population contained 45,391 sampled cell-hours, including 12,030 Korean cell-hours from two contributing fires, KFS_01 and KFS_04. The remaining six test fires were from the United States. Three training seeds measure optimization variation; they are not three additional fires or independent replications of the incidents.

An independently implemented scorer authenticated input and prediction identities and recalculated population-weighted Brier score, average precision, ROC-AUC, log loss, calibration and classification diagnostics. Classification thresholds maximized weighted F1 on the pooled validation 9×9-contact cohort and were fixed for test evaluation. Brier score was the primary probability-error measure; lower values indicate better squared probability error. Average precision assesses positive-class ranking and is reported alongside Brier to avoid interpreting a predominantly negative population through a single score.

## Component results

Table 1 reports the mean over the three trained seeds. The pooled population includes all eight test fires; Korean results describe the two contributing Korean fires. Average precision is shown for the pooled population. These scores concern reconstructed next-hour transition labels, not independently observed hourly fire progression.

**Table 1. Matched test component comparisons on the 9×9-contact population.**

| Configuration | Pooled Brier ↓ | Korean Brier ↓ | Pooled average precision ↑ |
|---|---:|---:|---:|
| Full multiscale model | 0.034290 | 0.138679 | 0.165063 |
| Single 9×9 branch | 0.032759 | 0.129552 | 0.320079 |
| Without weather inputs | 0.034663 | 0.140962 | 0.203367 |
| Without slope input | 0.035551 | 0.146658 | 0.195968 |
| Without tree-cover input | 0.038332 | 0.163246 | 0.164128 |
| Without biome inputs | 0.034075 | 0.137508 | 0.120209 |
| Without categorical loss balancing | 0.033733 | 0.135661 | 0.183851 |
| Frozen equal branch coefficients | 0.033006 | 0.130749 | 0.164672 |

The single 9×9 model had lower mean Brier scores and higher average precision than the full model on this test population. However, its whole-fire paired 95% bootstrap interval for the pooled Brier difference crossed zero. The experiment therefore does not establish that the multiscale design improves forecasting, nor does it establish a general superiority of the single-scale alternative. Removing weather, slope or tree cover increased mean Brier error, but their paired intervals also crossed zero. These comparisons identify directions of effect in this cohort without proving indispensable benefit for each input group.

**Table 2. Paired pooled Brier differences relative to the full model.** Negative differences favor the listed configuration. Intervals use 2,000 whole-fire paired bootstrap draws across eight fires, conditional on the fitted models, sampled rows and reconstructed labels. Intervals are not adjusted for the multiple component comparisons.

| Configuration | Brier difference | 95% bootstrap interval |
|---|---:|---:|
| Single 9×9 branch | −0.00153037 | [−0.00462920, 0.00001400] |
| Without weather inputs | 0.00037342 | [−0.00006804, 0.00117616] |
| Without slope input | 0.00126164 | [−0.00010645, 0.00402349] |
| Without tree-cover input | 0.00404221 | [−0.00005242, 0.01243095] |
| Without biome inputs | −0.00021468 | [−0.00060821, −0.00000242] |
| Without categorical loss balancing | −0.00055669 | [−0.00155955, −0.00002440] |
| Frozen equal branch coefficients | −0.00128387 | [−0.00399400, 0.00008980] |

Biome-input removal slightly improved pooled Brier error while reducing pooled average precision. Its categorical optimization weights still used the original biome information, so this is an input-only ablation. A separate joint control removed both biome inputs and categorical balancing; its pooled Brier score was 0.034341 and its paired interval crossed zero. The component study consequently does not show that biome information is unnecessary. It instead demonstrates that the input representation and its use in optimization must be distinguished.

The no-balancing configuration improved both pooled Brier and pooled average precision relative to the full model, with an unadjusted paired Brier interval below zero. This provides a cohort-specific reason to reassess categorical reweighting. Its interpretation remains retrospective and subject to the limited number of fires and multiple comparisons. No reliable Korean confidence interval was reported from only two contributing fires.

The final archived checkpoint was evaluated separately rather than averaged with the new fits. Its pooled and Korean Brier scores were 0.034181 and 0.137756, respectively. The training-only scalar neighbor-rate comparator achieved pooled Brier 0.034191, compared with 0.034290 for fresh full-model retraining; its paired difference interval included zero. Thus, a probability-error advantage over this simple comparator was not established. The full model had higher pooled average precision than that comparator (0.165063 versus 0.091967), but this descriptive ranking difference does not establish superiority on every metric or population.

A material probability failure occurred in the freshly retrained full-model seed 17: 2,794 Korean contact-population rows and 3,627 pooled contact-population rows received exact certainty for the outcome opposite to their reconstructed label. Consequently, exact negative log likelihood was infinite in both populations. The separately reported finite log-loss values clip probabilities at a floor of 10⁻⁷ and must not be interpreted as finite exact log likelihood. This failure concerns that retrained seed, not the unchanged selected archived checkpoint. It shows why squared probability error and ranking scores alone are insufficient to establish reliable probability estimates.

## Computational cost

Fits ran natively on the Mac using PyTorch 2.5.1 and MPS, in separate processes under the shared timing lease. The frozen execution environment explicitly enabled MPS fallback because a public verification operation was unsupported on MPS; the cached training computation used MPS. Training-process receipts recorded the following costs. These receipts were inspected by the scorer but were not independently timed by it.

| Configuration | Parameters | Recorded 512-step training phase | Process peak RSS |
|---|---:|---:|---:|
| Full multiscale model | 210,344 | 89.78–94.68 s | 5,219.70–5,682.03 MiB |
| Single 9×9 branch | 103,826 | 35.83–38.46 s | 5,018.94–5,426.81 MiB |

The training phase includes optimization, the original per-step training/validation evaluations and checkpoint persistence. Cache loading and fitted statistics precede this timer. Peak RSS covers the entire process, including data and preprocessing, and is not the model's parameter-memory footprint. Final validation/test prediction exports took 0.375–0.448 s for the full model and 0.376–0.485 s for the single 9×9 model; these timings include tensor preparation and compressed output. They are not latency measurements for a geographic forecast map and must not be combined with routing latency.

## Interpretation and scope

This study provides a reproducible, matched component analysis of the final forecasting package. It does not verify a multiscale forecasting advantage. The simpler 9×9 configuration is a promising efficiency and ranking candidate, while categorical weighting warrants reconsideration, but no selected production checkpoint was changed on the basis of these test results.

The labels reconstruct hourly burning inside eventual fire perimeters; they are not independent hourly observations. Much of the negative population consists of pre-arrival hours inside eventual burned areas. The scores therefore do not establish performance on a comprehensive surrounding unburned landscape. Inverse sampling weights estimate the represented eligible population; sampled cell-hours and overlapping spatial or temporal contexts do not constitute independent fires. The test partition was already present in the supplied research package, so these are retrospective component comparisons rather than a new untouched confirmation study. The Korean subset is dominated by one contributing fire and cannot establish broad Korean-event generalization. Probability discrimination, calibration, binary classification and computational cost should remain separate conclusions.

Separate completed assessments of recursive multi-hour forecasts and Monte Carlo precision are reported in [the dynamics section of ABLATION_RESULTS.md](ABLATION_RESULTS.md#recursive-forecasts-and-monte-carlo-precision), followed by [thermal parameter sensitivity](ABLATION_RESULTS.md#thermal-parameter-sensitivity). Those additional panels evaluate different questions and are not pooled with the component scores above. Incident radiation accuracy, forecast-to-routing outcomes and real-time operational accuracy are not established by these component scores.

## Local evidence supporting this text

- Frozen methods and source identities: [campaign/PROTOCOL.json](campaign/PROTOCOL.json).
- Independently recalculated component metrics: [independent_scoring/ARM_SUMMARY.csv](independent_scoring/ARM_SUMMARY.csv).
- Paired whole-fire uncertainty: [independent_scoring/PAIRED_EVENT_BOOTSTRAP.csv](independent_scoring/PAIRED_EVENT_BOOTSTRAP.csv).
- Per-fit measured cost scopes: [independent_scoring/COSTS.csv](independent_scoring/COSTS.csv).
- Partition and label audit: [independent_scoring/CACHE_AUDIT.json](independent_scoring/CACHE_AUDIT.json).
- Per-event breakdown: [independent_scoring/PER_EVENT_METRICS.csv](independent_scoring/PER_EVENT_METRICS.csv).

All numerical statements above are transcribed from existing frozen or independently scored records. No new experiment, numerical analysis, source modification or checkpoint selection was performed while preparing this companion.
