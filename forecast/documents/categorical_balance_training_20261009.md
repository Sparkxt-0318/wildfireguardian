# Categorical input imbalance: training method and verification

The implemented method increases the fitting influence of rare categorical input contexts. It also keeps one-hot indicators at raw 0/1 values, avoiding numerical amplification caused by standardizing rare indicators. Training-only factors are separate from the original inverse inclusion weights used for population evaluation.

## Why both changes are necessary

In the current weighted-stratified training cache, biome 5 accounts for approximately 98.89–98.98% of original-weighted input patch-pixel exposure across the native 3×3, 5×5, 7×7, and 9×9 contact cohorts. Biome 8 is observed only in surrounding input context; it never appears at a training target center. A target-center balancing rule would miss it.

Under the historical native 3×3 normalization, the present biome-8 one-hot indicator would have become approximately 2,514.57 because its training pixel frequency is extremely small. New fitting fixes one-hot means at zero and scales at one. Continuous channels still use original-population-weighted training moments across patch positions. Saved preprocessing remains bound to the fitted checkpoint and is used unchanged at inference.

## Explicit mathematical objects

For one learner, let `T` be its actual training cohort after native contact filtering and centered cropping. A row `i` is one fire/time/grid-cell identity. Its raw environmental patch has support `K×K`; its binary target `y_i` indicates that the currently unburned target cell becomes newly burned at the next hourly snapshot. Original inverse inclusion weight `w_i > 0` estimates represented population mass.

Let `G` be the number of categorical source fields. Source `g` has a fixed class vocabulary `C_g`. Define `I_igc = 1` when class `c` appears anywhere in row `i`'s raw cropped patch, and zero otherwise. A patch may contain several classes, so these presence groups overlap.

The fitted original-weighted presence frequency is

\[
f_{gc}=\frac{\sum_{i\in T}w_i I_{igc}}{\sum_{i\in T}w_i}.
\]

For observed classes, the prespecified raw rarity factor is

\[
r_{gc}=\min\left(10,\max(f_{gc},0.001)^{-1/2}\right).
\]

Unobserved vocabulary classes receive neutral factor one; they do not occur in fitted training patches. Each row averages across its distinct present classes within a source and then across sources:

\[
b_i=\frac{1}{G}\sum_{g=1}^{G}
\frac{\sum_{c\in C_g}I_{igc}r_{gc}}{\sum_{c\in C_g}I_{igc}},
\qquad
\mu=\frac{\sum_{i\in T}w_i b_i}{\sum_{i\in T}w_i},
\qquad
u_i=w_i\frac{b_i}{\mu}.
\]

For a schema without categorical sources, `b_i=1`. Complete one-hot groups ensure that every categorical source has at least one present class in each row. Distinct-class averaging means that repeating a category over more pixels within the same patch does not increase its factor. Averaging source factors avoids multiplicative amplification across categorical fields.

The normalized row factor is `a_i=b_i/μ`. With the default cap, `1≤b_i≤10`, `1≤μ≤10`, and `0.1≤a_i≤10`. The sum of optimization weights `u_i` equals the original weight sum up to floating-point rounding. This is a bounded rarity-emphasis heuristic; it does not make every categorical group equally frequent. Bounding influence is a deliberate safeguard because reweighting can increase estimation variance, as discussed in [Robust Importance Weighting for Covariate Shift](https://proceedings.mlr.press/v108/li20b/li20b.pdf). This local heuristic is not an implementation of that paper's density-ratio method.

## Training objective and evaluation

For predicted next-hour probability `q_θ(X_i)`, define the optimization-weighted prevalence

\[
\pi_u=\frac{\sum_{i\in T}u_i y_i}{\sum_{i\in T}u_i}.
\]

The normalized full-cohort training objective is

\[
L(\theta)=\frac{\sum_{i\in T}u_i\bigl(q_\theta(X_i)-y_i\bigr)^2}
{\left(\sum_{i\in T}u_i\right)\pi_u}.
\]

Search trainers implement this with chunked gradient accumulation and one AdamW step per full epoch. The API/exponential trainer retains its existing shuffled minibatch Adam schedule and uses the corresponding `mean((u/mean(u))*(q-y)^2)/π_u` minibatch objective. Dividing by `π_u` is one common scale for the cohort; it is not outcome-class weighting.

Category frequencies are fitted using only raw training inputs, the input schema, and original population weights. Fitting factors does not read targets, validation inputs, test inputs, or model parameters. Factors are fitted separately on each model's actual native support and reused across architecture/rate/schedule candidates and finalist continuations for that support. Search random forests receive the same optimization weights at fitting, without an additional target-class balancing rule.

Continuous normalization, descriptive marginal/global-rate baselines, and initialization retain original population weights. Population train/validation/test Brier, calibration, classification threshold selection, and checkpoint/hyperparameter selection also retain those original weights. The held-out split is unchanged. Optimization-weighted training Brier is saved separately from population training Brier.

For an unrestricted probability function, a positive input-only factor preserves the conditional squared-loss optimum. If `η(x)=E[Y|X=x]`, then

\[
\mathbb E[a(X)(q-Y)^2\mid X=x]
=a(x)\bigl[(q-\eta(x))^2+\eta(x)(1-\eta(x))\bigr],
\]

which is minimized at `q=η(x)` because `a(x)>0`. Finite model capacity, regularization, and optimization can still change probability calibration or population error. This argument is not a performance guarantee. Importance weighting changes the empirical fitting objective, and selecting/evaluating a predictor requires specifying the intended evaluation distribution; see [Sugiyama, Krauledat, and Müller (2007)](https://jmlr.org/papers/volume8/sugiyama07a/sugiyama07a.pdf).

## Actual training-data effect

The following measurements use the unchanged prepared training arrays. “Biome-8 rows” means input patches containing biome 8, not target centers in that biome. These are sampled cell-hour rows and may have overlapping spatial or temporal contexts.

| Native support | Biome-8 rows | Positive target rows among them | Combined biome-8 optimization weight amplification | Actual row-factor range |
|---|---:|---:|---:|---:|
| 3×3 | 1 | 1 | 5.00879× | 0.91378–9.10380 |
| 5×5 | 13 | 11 | 5.00605× | 0.91219–9.09990 |
| 7×7 | 35 | 26 | 4.97913× | 0.90685–9.05140 |
| 9×9 | 104 | 52 | 4.93257× | 0.89826–8.96688 |

The factors increase the combined influence of biome-8 contexts by approximately five times. The original inverse inclusion weights remain intact; adjusted weights are used only for optimization. Exact category counts, original and effective presence frequencies, patch-pixel exposure, supporting events, effective sample sizes, and weight checksums are in `categorical_balance_training_20261009.json`.

The native 3×3 cohort has just one biome-8 training row, and it has a positive target. Reweighting cannot create independent evidence for that category. The category is supplied by only Moose and HermitsPeak across the larger supports. Current native 3×3 validation has no biome-8 rows, and native 5×5 validation has only two, both positive. These supports cannot establish reliable biome-8 calibration.

Weight concentration increases: for native 9×9, the original weight effective sample size is approximately 40,882 and the optimization weight effective sample size is approximately 29,138. The optimization-weighted marginal next-hour frequency also changes, from approximately 1.05323% to 1.26566%, because categorical inputs and targets are associated. This is why original-population validation and calibration remain necessary. The weights do not directly depend on the individual target outcome.

## Controls, artifacts, and compatibility

`TrainingConfig` and the API/exponential CLI default to inverse-square-root categorical balancing. The four direct kernel-search families use the same defaults, including both mixed-kernel learners. The portable launcher inherits those settings and now chooses a fresh default output directory.

```python
TrainingConfig(
    categorical_balance="inverse-sqrt",
    categorical_balance_min_frequency=0.001,
    categorical_balance_max_factor=10.0,
)
```

The corresponding CLI options are `--categorical-balance`, `--categorical-balance-min-frequency`, and `--categorical-balance-max-factor`. `categorical_balance="none"` or `--categorical-balance none` disables only the loss adjustment; one-hot indicators still retain the new raw 0/1 preprocessing. The disabled mode is available as a control for otherwise identical fresh experiments.

A fresh API fit saves `categorical_balance.json` and embeds its fitted audit in the checkpoint contract. Search fits save `categorical_balance/kK.json` for each native support and bind settings, frequencies, original/effective weight digests, and row identities in protocol, summaries, checkpoints, and continuation state. Altered settings, reports, or saved balance contracts are rejected on resume or finalization. Low-level candidate fitting also rejects normalization arrays that contradict the raw-one-hot contract.

Per-category population Brier, represented mass, and sampled/positive support counts are saved in `metrics.json`. Native and common cohorts are separate in search results. Category-presence groups overlap and are explicitly nonadditive; absent categories have null error metrics. These diagnostics do not replace the prespecified pooled population validation criterion.

Original prepared NPZ files and historical fitted models were preserved. Old checkpoints continue to apply their own saved preprocessing. Existing completed experiments retain their original source/data bindings; new training methods use fresh output directories. The same changed code and tests are mirrored in both workspace copies.

## Verification boundary

Independent hand-calculation tests cover rarity factors, distinct-class/source averaging, normalization, caps/floors, unchanged original weights, input/label separation, and population-weighted group metrics. Integration tests fit small active categorical fixtures through the public API, all four neural searches, and all four search forest paths. They verify that enabled weighting changes fitted parameters, that raw one-hot preprocessing is saved/reloaded, that population scores retain their original weights, and that altered audit/resume contracts are rejected.

The actual dataset audit computes input distributions and weights; it does not fit a probability model. No full production-data model retraining was started. Passing these fixtures establishes implementation behavior, not improved predictive accuracy or physical wildfire validation.

Final regression: **891 tests passed, 8 skipped** in 54.28 seconds. The 272 warnings are plotting dependency deprecations. A real-cache multiscale configuration check verified all 486 source-file hashes, the row-split contract, and the enabled balancing settings without invoking training. Exact final source/test hashes and both cache copies' unchanged checksums are saved in `categorical_balance_verification_20261009.json`.
