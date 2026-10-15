# Forecasting ablation methodology

## Scope and model identity

This study evaluates the final forecasting package supplied in `wildfire 3 (1).zip`, with its source, checkpoint, prepared data and configuration identities retained. The maintained next-hour predictor is a `MixedNonnegativeKernel` with environmental CNN branches at 3 × 3, 5 × 5, 7 × 7 and 9 × 9 scales. Branches generate nonnegative spatial rates from current environmental information and the current cumulative burned state. Their weighted rates are combined before an exponential link produces new-burning probabilities. The existing final checkpoint is evaluated separately from newly retrained variants.

## Controlled component removals

Seventeen variants are fitted: the full model; each of four single-scale models; four models omitting one scale; models removing weather, slope, tree-cover or biome inputs; a model without categorical optimization balancing; a joint removal of biome inputs and categorical balancing; frozen mixing gains; and environment-independent learned spatial kernels. Feature-removal variants set the selected standardized inputs to zero during both fitting and prediction, retaining the original input slots and parameter dimensions. They test access to information rather than the deployment cost of a smaller input tensor. Weather comprises temperature and both wind components; biome comprises fourteen one-hot indicators.

All scale variants retain the same complete 9 × 9 input and availability contract. Smaller scales can legitimately assign zero probability when burning sources lie outside their support. Such cells remain in the common test population. Shared hidden weights begin from the same seeded full-model initialization, while output rates are reallocated after pruning to preserve the original uniform initial rate on supported offsets. Frozen mixing gains equal one; independent branch amplitudes remain trainable, so this is an optimization parameterization control, not enforced equal scale importance. The biome-input-only variant retains biome-derived optimization weights; the joint removal separates that influence.

## Fitting and model selection

Every variant uses all 158,561 native-9-contact training rows and 512 full-batch AdamW steps. Three prespecified seeds, 7, 17 and 27, are paired across variants. The original fitting configuration uses width 64, dropout 0.15 where the architecture permits it, peak learning rate 0.1 and weight decay 0.01. The warmup-cosine schedule retains its original 4,096-step horizon, 32-step warmup and 0.01 minimum-rate factor. No test score selects weights, thresholds or hyperparameters. Checkpoints minimize the original population-weighted common-3-contact validation Brier score over the fixed trajectory; the final training state and every validation history are preserved. Normalization, optimization balancing and no-learning rate baselines are fitted from training only.

The archive provides 199,185 sampled training cell-hours and 49,900 validation cell-hours across 25 development fires. Training and validation identities are disjoint but share fires and nearby spatial/temporal contexts. The test cache contains 61,965 sampled cell-hours from eight entirely held-out fires, including Korean events KFS_01 (Uiseong) and KFS_04 (Sancheong). Two additionally declared Korean test events have no saved cache rows. This existing partition has been examined historically, so the study is a retrospective component ablation, not a newly hidden confirmation test.

## Probability and classification evaluation

The two primary comparisons are weighted Brier error on the same 9 × 9 contact test cells for Korea and for all eight contributing fires. All-row and common-3-contact results, individual-fire results and event-macro summaries are secondary. Original inverse inclusion-probability weights account for sampled negatives:

\[
\mathrm{Brier}=\frac{\sum_i w_i(p_i-y_i)^2}{\sum_i w_i},
\]

where each row's predicted probability is \(p_i\), reconstructed binary next-hour outcome is \(y_i\), and original sampling weight is \(w_i\). Lower error is better. The independent scorer also reports weighted average precision, ROC AUC, class-specific Brier error, fixed-bin calibration and log loss. Exact infinite log loss remains explicit when a positive outcome receives probability zero; log loss floored at \(10^{-7}\) is a separate numerical diagnostic. Classification thresholds maximize weighted F1 on pooled validation contact-9 cells only, and are then fixed for test precision, recall, F1, IoU and balanced accuracy.

Metrics are computed for each seed and averaged afterward; averaged predictions are not substituted as a new ensemble. Paired loss differences use identical rows and seeds. Whole-fire bootstrap intervals across eight test fires are descriptive and conditional on these models and reconstructed labels. Two-fire Korean differences receive no purported reliable incident-generalization confidence interval. Ordinary accuracy is secondary because a no-new-burning classifier achieves approximately 99.66% on the weighted all-row test population.

## Dynamics and thermal sensitivity

A separate timestamp-selected panel uses three cutoffs each from held-out KFS_06 and KFS_13. Seventy-two recursive forecasts compare 32, 128, 512 and 1,024 Monte Carlo trajectories across three seeds, with 1-, 3- and 6-hour outputs. Six fixed-initial-state forecasts test the consequence of recursive fire-state feedback. Same-seed estimates share trajectory prefixes; the 1,024 estimate is a correlated numerical comparator, not probability truth. Between-seed variation and coverage are retained. A separately declared common-mask analysis checks comparability before interpreting fixed-versus-recursive score differences.

Thirty-two thermal parameter scenarios hold new-burning probabilities fixed and vary one physical assumption at a time. These evaluate response and numerical invariants, including conserved phase energy and linearity in consumed mass, radiative fraction and scalar transmission. They describe known-source contributions under stated reference parameters, rather than measured Korean receiver heat or thermal predictive accuracy.

## Evidence and reproducibility

Every fit runs in a fresh native macOS process under the existing shared computation lease. MPS computation uses the declared CPU fallback required by a PyTorch 2.5.1 public-verification operation. Reported fit time includes fitting, validation and persistence; complete command time also includes startup, loading and training-only statistics. Host RSS and endpoint MPS allocations have distinct scopes. Model inference on the saved validation/test patch exports is not single-map forecasting latency.

The independent scorer imports no project scoring implementation. It authenticates all 51 planned exports, selected checkpoint identities, source/cache bindings, complete ordered row identities and unchanged original labels/weights. Original and failed preflight evidence is preserved. No source in the supplied package, published default, repository branch or prior campaign is changed.

The target is retrospective reconstructed hourly burning on known eventual-event support, with negatives largely representing earlier hours of eventual burned cells. These observations support conditional timing comparisons; they do not establish external-landscape false-alarm performance or independent continuous flame truth. Prediction accuracy, numerical Monte Carlo precision and thermal response sensitivity remain separate outcomes.
