# Fresh single-scale, linear mixed and neural mixed scheduling search

<!-- BEGIN EVALUATION BAR OVERVIEW -->
## Evaluation metrics at a glance

[Open all 75 metrics in the bar dashboard](evaluation/overview.html). Select a model and cohort to see training, validation, and test together. The static overview below uses the saved validation-selected model, **mlp K=7**.

![All evaluation metrics as bar charts](evaluation/figures/overview_common.png)

[Scalable overview (SVG)](evaluation/figures/overview_common.svg) · [Native-cohort overview](evaluation/figures/overview_native.png)
<!-- END EVALUATION BAR OVERVIEW -->

Validation selected **mlp 7x7** among the searched configurations. All test scores below were computed after selection.

Training and validation use disjoint cell-hour rows sampled from the pooled development fires. Validation can share fires, overlapping spatial contexts, and fire histories with training, so it evaluates within-fire cell-hour interpolation. The test partition retains its original whole fires, which are absent from training and validation.

Categorical optimization weights are fitted only on each learner's raw native training crop, using the original inverse-inclusion-weighted frequency of each category's presence anywhere in that crop. Bounded inverse-square-root rarity factors multiply the original population weights for neural optimization and forest fitting. Neural loss divides the optimization-weighted Brier by the optimization-weighted training burn frequency. Continuous feature normalization and global-rate initialization use population weights; one-hot inputs retain raw 0/1. All reported population Brier curves, validation selection, thresholds, and test metrics retain the original population weights. Post-update optimization-weighted training Brier is saved separately from population training Brier. Native and matched category-presence group diagnostics use original population weights; groups can overlap and never replace the pooled validation selection criterion. This training objective emphasizes rare categorical contexts; it does not guarantee improved category or population performance.

The target is a currently unburned cell becoming burned at exactly the next hourly snapshot. Contact uses the reconstructed current cumulative burned-area map; it does not mean an actively flaming cell.

Every candidate completed 512 full-batch epochs. One validation-selected candidate in each of six neural families continued, with optimizer and RNG state, to 4096 epochs. There was no early stopping. A saved prediction checkpoint can occur before the final epoch because selection minimizes validation Brier over the entire trajectory.

All fits are fresh. Constant kernels learn offset-specific rates; linear kernels map per-channel environmental patch means to nonnegative rates; MLP and residual MLP families use the same patch means; the existing CNN and new regularized CNN preserve full spatial environmental patches. Every kernel fixes its center to zero and computes q=1-exp(-sum(nonnegative offset rate × current burned neighbor)). Random forests are separate probability-classifier baselines, not learned rate kernels.

Training uses native K-contact rows from one frozen 9x9 sample cache and its original inverse inclusion weights. Native evaluation also uses K-contact. The matched comparison uses the exact same current 3x3-contact rows for every model, retaining the original weights. No-contact predictions are saved for every model; neural kernels return a valid structural zero, and forests may return nonzero probabilities.

Optimization is AdamW with full-batch categorical optimization-weighted Brier divided by optimization-weighted training prevalence, weight decay, optional dropout, and gradient norm clipping at 10. An epoch is one pass over every native training row and ONE optimizer step, with chunked gradient accumulation. The ten single-scale architecture/regularization settings at four kernel sizes and three linear mixed plus three neural mixed CNN settings (branch widths 16, 32, 64) are each crossed with peak learning rates **0.01, 0.05, 0.1** and schedules **constant, warmup_cosine**, giving 276 kernel candidates. Width, depth, dropout, and weight decay retain the prior joint search settings. The learning-rate/schedule subgrid is fully crossed; the architecture search remains finite and joint.

The fixed scheduling horizon is **4096 optimizer steps from the start of every candidate**, even when its initial fit stops after 512 steps. Continuing a finalist restores its AdamW and RNG states and resumes the original schedule. It does not start warmup again or rebase the cosine schedule. Warmup lasts 32 steps; the rate floor is 0.01 times the peak; optional restart cycles last 512 steps. The rate actually used is saved at every epoch as `learning_rate`, with a one-based `optimizer_step`.

Constant schedules always use the peak. Linear warmup uses peak × step / warmup_length. For a nonzero warmup, ordinary cosine uses floor + (peak − floor) × (1 + cos(π × (step − warmup_length)/(horizon − warmup_length)))/2 after warmup and reaches the floor at the fixed horizon. Without warmup its cosine progress is (step − 1)/(horizon − 1). Restart schedules use cycles with progress 0/(period − 1), …, (period − 1)/(period − 1) after warmup, then restart at the peak. Scheduling never consults validation or test scores.

Every variant of the same kernel/architecture/regularization setting shares its initial parameter checksum and random seed. AdamW's nominal weight-decay coefficient stays fixed within each comparison, but its per-step shrinkage multiplier is 1 − learning_rate × weight_decay, so changing rates or schedules also changes integrated parameter shrinkage. The controlled comparison below therefore measures the complete optimizer policy at fixed nominal regularization. It does not isolate learning rate from accumulated weight decay.

## Matched test comparison

| Model | Completed / selected epoch | Validation Brier | Test Brier | AP | ROC AUC | Exact NLL | F1 at validation threshold | MCC at validation threshold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| mlp 7x7; peak=0.05, warmup_cosine | 4096 / 442 | 0.025113 | 0.092241 | 0.305154 | 0.822139 | infinity | 0.449806 | 0.250256 |
| mlp 9x9; peak=0.05, warmup_cosine | 512 / 296 | 0.025198 | 0.084222 | 0.311075 | 0.827008 | infinity | 0.461841 | 0.384118 |
| residual_mlp 5x5; peak=0.01, constant | 4096 / 266 | 0.025231 | 0.087237 | 0.317205 | 0.823675 | infinity | 0.454378 | 0.351702 |
| residual_mlp 9x9; peak=0.05, constant | 512 / 316 | 0.025238 | 0.075090 | 0.332350 | 0.806653 | 0.284104 | 0.450888 | 0.144945 |
| mlp 5x5; peak=0.1, constant | 512 / 487 | 0.025246 | 0.077595 | 0.327553 | 0.814136 | infinity | 0.448340 | 0.356576 |
| residual_mlp 7x7; peak=0.05, constant | 512 / 113 | 0.025250 | 0.073860 | 0.332137 | 0.832899 | 0.262309 | 0.461923 | 0.355620 |
| mlp 3x3; peak=0.1, warmup_cosine | 512 / 128 | 0.025255 | 0.073541 | 0.371396 | 0.791118 | infinity | 0.468119 | 0.312156 |
| residual_mlp 3x3; peak=0.05, constant | 512 / 76 | 0.025330 | 0.073586 | 0.319948 | 0.824856 | 0.262911 | 0.444084 | 0.316649 |
| linear mixed (3x3, 5x5, 7x7, 9x9); peak=0.1, warmup_cosine | 4096 / 205 | 0.025458 | 0.083846 | 0.186957 | 0.533153 | infinity | 0.277677 | 0.071863 |
| cnn 3x3; peak=0.05, constant | 4096 / 8 | 0.025494 | 0.073497 | 0.318551 | 0.819662 | 0.266468 | 0.424596 | 0.358563 |
| cnn 7x7; peak=0.1, warmup_cosine | 512 / 426 | 0.025495 | 0.098384 | 0.198721 | 0.675048 | infinity | 0.308753 | 0.180630 |
| legacy 3x3; peak=0.05, constant | 4096 / 5 | 0.025507 | 0.072307 | 0.362688 | 0.839822 | 0.262126 | 0.453958 | 0.349064 |
| legacy 9x9; peak=0.1, warmup_cosine | 512 / 196 | 0.025547 | 0.085550 | 0.091679 | 0.323547 | infinity | 0.104512 | 0.002465 |
| neural mixed (3x3, 5x5, 7x7, 9x9); peak=0.05, warmup_cosine | 4096 / 73 | 0.025552 | 0.076920 | 0.277138 | 0.793708 | infinity | 0.427809 | 0.173585 |
| legacy 5x5; peak=0.1, warmup_cosine | 512 / 283 | 0.025615 | 0.096723 | 0.224499 | 0.697392 | infinity | 0.321748 | 0.193387 |
| cnn 5x5; peak=0.01, constant | 512 / 118 | 0.025683 | 0.079009 | 0.258687 | 0.763723 | infinity | 0.331242 | 0.269941 |
| cnn 9x9; peak=0.05, warmup_cosine | 512 / 437 | 0.025721 | 0.099082 | 0.223377 | 0.756678 | infinity | 0.311061 | 0.265660 |
| linear 3x3; peak=0.01, warmup_cosine | 512 / 19 | 0.025746 | 0.080701 | 0.188337 | 0.722170 | 0.312728 | 0.172310 | 0.197304 |
| constant 9x9; peak=0.1, constant | 512 / 512 | 0.025747 | 0.080587 | 0.147129 | 0.671186 | 0.326605 | 0.126733 | 0.158333 |
| constant 7x7; peak=0.1, constant | 512 / 512 | 0.025752 | 0.080543 | 0.150070 | 0.673611 | 0.326444 | 0.126636 | 0.158252 |
| constant 5x5; peak=0.1, warmup_cosine | 512 / 57 | 0.025760 | 0.080520 | 0.146457 | 0.672795 | 0.319310 | 0.126130 | 0.158191 |
| constant 3x3; peak=0.01, warmup_cosine | 512 / 1 | 0.025770 | 0.081430 | 0.138820 | 0.672556 | 0.322422 | 0.145817 | 0.157601 |
| linear 5x5; peak=0.1, constant | 512 / 13 | 0.025798 | 0.072257 | 0.314759 | 0.826251 | 0.255396 | 0.436955 | 0.321344 |
| linear 7x7; peak=0.05, constant | 512 / 29 | 0.025873 | 0.072619 | 0.314435 | 0.832187 | 0.256205 | 0.439644 | 0.329897 |
| legacy 7x7; peak=0.05, warmup_cosine | 512 / 9 | 0.025949 | 0.075406 | 0.337266 | 0.828431 | 0.280013 | 0.456447 | 0.410453 |
| linear 9x9; peak=0.05, constant | 512 / 33 | 0.026023 | 0.073134 | 0.307724 | 0.830560 | 0.257617 | 0.429816 | 0.380371 |
| random_forest 5x5 | trees | 0.026483 | 0.073185 | 0.284708 | 0.840512 | 0.246583 | 0.405905 | 0.301554 |
| random_forest 3x3 | trees | 0.026989 | 0.072259 | 0.278082 | 0.838127 | 0.243830 | 0.396690 | 0.305003 |

## Cohort sizes

| Split | Full prediction rows | 3x3 contact | 5x5 contact | 7x7 contact | 9x9 contact | Matched positives |
|---|---:|---:|---:|---:|---:|---:|
| train | 199185 | 89874 | 117500 | 139323 | 158561 | 56694 |
| validation | 49900 | 22528 | 29454 | 34980 | 39776 | 14170 |
| test | 61965 | 16807 | 26943 | 36287 | 45391 | 7378 |

## Native test comparison

These scores use different K-contact populations and therefore cannot rank kernel sizes fairly. Compare model families within the same K, or use the matched table above.

| Model | Native test Brier | Native AP | Native ROC AUC |
|---|---:|---:|---:|
| constant 3x3 | 0.081430 | 0.138820 | 0.672556 |
| constant 5x5 | 0.053204 | 0.134095 | 0.734628 |
| constant 7x7 | 0.040954 | 0.129927 | 0.763665 |
| constant 9x9 | 0.033385 | 0.123463 | 0.785607 |
| linear 3x3 | 0.080701 | 0.188337 | 0.722170 |
| linear 5x5 | 0.049612 | 0.248147 | 0.844015 |
| linear 7x7 | 0.038829 | 0.221181 | 0.857465 |
| linear 9x9 | 0.032489 | 0.200677 | 0.864573 |
| legacy 3x3 | 0.072307 | 0.362688 | 0.839822 |
| legacy 5x5 | 0.067163 | 0.188525 | 0.738877 |
| legacy 7x7 | 0.038778 | 0.252501 | 0.862282 |
| legacy 9x9 | 0.035010 | 0.052516 | 0.354573 |
| cnn 3x3 | 0.073497 | 0.318551 | 0.819662 |
| cnn 5x5 | 0.052361 | 0.221083 | 0.798906 |
| cnn 7x7 | 0.049242 | 0.160621 | 0.721591 |
| cnn 9x9 | 0.055351 | 0.130248 | 0.810624 |
| mlp 3x3 | 0.073541 | 0.371396 | 0.791118 |
| mlp 5x5 | 0.053151 | 0.266869 | 0.831066 |
| mlp 7x7 | 0.062649 | 0.184528 | 0.848430 |
| mlp 9x9 | 0.043491 | 0.173459 | 0.842735 |
| residual_mlp 3x3 | 0.073586 | 0.319948 | 0.824856 |
| residual_mlp 5x5 | 0.064764 | 0.245890 | 0.835413 |
| residual_mlp 7x7 | 0.040709 | 0.232828 | 0.853283 |
| residual_mlp 9x9 | 0.032614 | 0.237783 | 0.833882 |
| linear mixed (3x3, 5x5, 7x7, 9x9) | 0.034249 | 0.137381 | 0.723458 |
| neural mixed (3x3, 5x5, 7x7, 9x9) | 0.032220 | 0.208811 | 0.808391 |
| random_forest 3x3 | 0.072259 | 0.278082 | 0.838127 |
| random_forest 5x5 | 0.054535 | 0.200643 | 0.853246 |

## Controlled learning-rate and schedule comparison

Each row below fixes kernel size, architecture, dropout, weight decay, training rows, normalization, initialization, and seed. Every entry is its minimum matched validation Brier through the same first 512 steps. Later finalist outcomes are excluded from this table. Full candidate trajectories and end-of-budget values are in `learning_rate_comparison.csv` and `history.json`.

| Fixed base configuration | 0.01 constant | 0.01 warmup_cosine | 0.05 constant | 0.05 warmup_cosine | 0.1 constant | 0.1 warmup_cosine |
|---|---:|---:|---:|---:|---:|---:|
| k3_constant_00 | 0.025770 | 0.025770 | 0.025773 | 0.025770 | 0.025774 | 0.025770 |
| k3_linear_01 | 0.025746 | 0.025746 | 0.025747 | 0.025746 | 0.025761 | 0.025746 |
| k3_mlp_04 | 0.025628 | 0.025612 | 0.025697 | 0.025672 | 0.025612 | 0.025683 |
| k3_mlp_05 | 0.025575 | 0.025500 | 0.025482 | 0.025520 | 0.025592 | 0.025255 |
| k3_mlp_06 | 0.025452 | 0.025514 | 0.025452 | 0.025503 | 0.025916 | 0.025503 |
| k3_mlp_07 | 0.025583 | 0.025597 | 0.025478 | 0.025488 | 0.025324 | 0.025482 |
| k3_residual_mlp_08 | 0.025529 | 0.025514 | 0.025330 | 0.025404 | 0.025433 | 0.025413 |
| k3_residual_mlp_09 | 0.025500 | 0.025577 | 0.025796 | 0.025650 | 0.026032 | 0.025696 |
| k3_legacy_02 | 0.025549 | 0.025575 | 0.025507 | 0.025603 | 0.025776 | 0.025611 |
| k3_cnn_03 | 0.025662 | 0.025705 | 0.025494 | 0.025714 | 0.025767 | 0.025676 |
| k5_constant_00 | 0.025767 | 0.025768 | 0.025761 | 0.025761 | 0.025760 | 0.025760 |
| k5_linear_01 | 0.025934 | 0.025905 | 0.025846 | 0.025836 | 0.025798 | 0.025798 |
| k5_mlp_04 | 0.025727 | 0.025741 | 0.025603 | 0.025623 | 0.025485 | 0.025595 |
| k5_mlp_05 | 0.025583 | 0.025584 | 0.025654 | 0.025483 | 0.025246 | 0.025341 |
| k5_mlp_06 | 0.025587 | 0.025567 | 0.026005 | 0.025415 | 0.026057 | 0.025509 |
| k5_mlp_07 | 0.025569 | 0.025632 | 0.025329 | 0.025533 | 0.025577 | 0.025424 |
| k5_residual_mlp_08 | 0.025506 | 0.025474 | 0.025604 | 0.025354 | 0.025363 | 0.025529 |
| k5_residual_mlp_09 | 0.025231 | 0.025520 | 0.025987 | 0.025761 | 0.026033 | 0.025929 |
| k5_legacy_02 | 0.025809 | 0.025804 | 0.025782 | 0.025825 | 0.025996 | 0.025615 |
| k5_cnn_03 | 0.025683 | 0.025799 | 0.025993 | 0.025739 | 0.025979 | 0.025684 |
| k7_constant_00 | 0.025763 | 0.025764 | 0.025753 | 0.025753 | 0.025752 | 0.025752 |
| k7_linear_01 | 0.025923 | 0.025939 | 0.025873 | 0.025899 | 0.025923 | 0.025934 |
| k7_mlp_04 | 0.025964 | 0.025975 | 0.025910 | 0.025923 | 0.025954 | 0.025752 |
| k7_mlp_05 | 0.025542 | 0.025557 | 0.025441 | 0.025586 | 0.025386 | 0.025195 |
| k7_mlp_06 | 0.025574 | 0.025634 | 0.025750 | 0.025113 | 0.026159 | 0.025541 |
| k7_mlp_07 | 0.025677 | 0.025475 | 0.025336 | 0.025347 | 0.025340 | 0.025478 |
| k7_residual_mlp_08 | 0.025557 | 0.025573 | 0.025250 | 0.025273 | 0.025486 | 0.025399 |
| k7_residual_mlp_09 | 0.025629 | 0.025556 | 0.026113 | 0.025853 | 0.026131 | 0.026064 |
| k7_legacy_02 | 0.025964 | 0.025991 | 0.026133 | 0.025949 | 0.026115 | 0.025950 |
| k7_cnn_03 | 0.025868 | 0.025978 | 0.026135 | 0.025951 | 0.026122 | 0.025495 |
| k9_constant_00 | 0.025761 | 0.025763 | 0.025749 | 0.025749 | 0.025747 | 0.025748 |
| k9_linear_01 | 0.026151 | 0.026145 | 0.026023 | 0.026058 | 0.026047 | 0.026080 |
| k9_mlp_04 | 0.025773 | 0.025797 | 0.025718 | 0.025676 | 0.025885 | 0.025677 |
| k9_mlp_05 | 0.025947 | 0.025996 | 0.025665 | 0.026006 | 0.025285 | 0.025271 |
| k9_mlp_06 | 0.025609 | 0.025851 | 0.025628 | 0.025198 | 0.026180 | 0.025673 |
| k9_mlp_07 | 0.025514 | 0.025475 | 0.025487 | 0.025532 | 0.025878 | 0.025598 |
| k9_residual_mlp_08 | 0.025532 | 0.025605 | 0.025238 | 0.025533 | 0.025593 | 0.025591 |
| k9_residual_mlp_09 | 0.025798 | 0.025688 | 0.026182 | 0.026080 | 0.026170 | 0.026139 |
| k9_legacy_02 | 0.026076 | 0.026089 | 0.026106 | 0.026013 | 0.026194 | 0.025547 |
| k9_cnn_03 | 0.026121 | 0.026011 | 0.026203 | 0.025721 | 0.026177 | 0.026057 |
| mixed_3_5_7_9_00 | 0.025917 | 0.025931 | 0.026205 | 0.025941 | 0.026029 | 0.025925 |
| mixed_3_5_7_9_01 | 0.025923 | 0.025717 | 0.026200 | 0.025952 | 0.026175 | 0.025458 |
| mixed_3_5_7_9_02 | 0.026134 | 0.025835 | 0.026133 | 0.025673 | 0.026145 | 0.026049 |
| neural_mixed_3_5_7_9_00 | 0.025892 | 0.025924 | 0.026203 | 0.025940 | 0.026182 | 0.025927 |
| neural_mixed_3_5_7_9_01 | 0.025916 | 0.025900 | 0.026191 | 0.026039 | 0.026178 | 0.026041 |
| neural_mixed_3_5_7_9_02 | 0.026128 | 0.025859 | 0.026172 | 0.025552 | 0.026167 | 0.025735 |

## Mixed kernel model

Independent environmental CNN branches generate nonnegative kernels at 3x3, 5x5, 7x7, and 9x9. Each branch's center coefficient is zero. Global learned nonnegative scalar coefficients have unrestricted sum. Their burned-state convolution rates are linearly combined, and one exponential converts that sum into a probability: q_i = 1 - exp(-sum_K alpha_K r_i^(K)). This is not an average of branch probabilities.

Mixed-model training and native evaluation use current contact within the union 9x9 support. Matched evaluation uses the same centered 3x3-contact rows as all single-scale models. Smaller branches crop the central environmental and burned patches; they remain zero when only outer-ring neighbors are burned.

The selected checkpoint mixing coefficients are alpha_3=2.410562, alpha_5=0.3500186, alpha_7=0.2953854, alpha_9=0.07704739. These are jointly learned predictive coefficients. Rescaling a branch kernel and inversely rescaling its coefficient preserves the combined rate, so these weights alone do not measure uniquely identifiable or causal importance of a spatial scale.

Mixed initialization assigns overlap-adjusted branch offset rates so the initial effective 9x9 kernel has the same uniform per-offset rate as the fitted global baseline. All branches and mixing coefficients are optimized jointly; no separately fitted branch is frozen.

![Learned mixing coefficients](mixing_weight_curves.png)

## Neural mixed kernel model

The additional model feeds the four independent branch convolution rates, ordered 3x3/5x5/7x7/9x9, into a small neural combiner. It produces one nonnegative combined rate before one exponential, rather than four learned mixing weights. The exact scalar readout is lambda_i = (sum_K r_i^(K)) * softplus(MLP(r_i)); q_i = 1 - exp(-lambda_i). Multiplying by the total raw rate ensures exact zero whenever all branch inputs are zero.

The selected combiner is 4 -> 32 -> 1, with SiLU and dropout 0.15. Branches have hidden width 64, dropout 0.15; AdamW weight decay is 0.01. Its complete branch and combiner parameters are saved in the selected checkpoint. The final scalar gain initializes to one so its initial effective rate matches the same uniform global baseline.

The neural combined rate is nonlinear in the current burned map. An environmental kernel alone cannot represent that rate; branch_kernel_rates remain inspectable, while the model's combined rate is obtained through the full prediction or center/combined_rate methods. Native and matched evaluation use the same 9x9 union-contact and centered 3x3-contact conditions as the linear mixed model.


## Long-training observations

![Learning curves](learning_curves.png)

These panels show the six candidates selected for uninterrupted long training. A family/kernel winner in the test table can be a different, shorter candidate when it has a better validation checkpoint.

![Actual optimizer learning rates](learning_rate_curves.png)

The learning-rate panels plot rates read back from the saved per-step histories. Constant-rate controls remain available for interpreting delayed generalization without a changing learning rate. An improvement during rate decay, or after a restart, is associated with the chosen optimizer policy and alone does not establish grokking.

These curves show training and validation Brier under the same current 3x3-contact condition. Training and validation use disjoint cell-hour rows sampled from the pooled development fires. Validation can share fires, overlapping spatial contexts, and fire histories with training, so it evaluates within-fire cell-hour interpolation. The test partition retains its original whole fires, which are absent from training and validation. Native training Brier is also saved in each history. A decrease after epoch 512 is descriptive evidence of late validation improvement. Grokking requires a demonstrated memorization phase followed by delayed generalization; double descent requires a reproducible rise and subsequent fall around an interpolation regime. Neither is inferred automatically from a long run or a visually noisy curve. The references concern particular experimental settings and do not guarantee either phenomenon on reconstructed wildfire labels.

[Grokking paper](https://arxiv.org/abs/2201.02177) and [Deep Double Descent paper](https://arxiv.org/abs/1912.02292).

- legacy: best validation Brier through epoch 512=0.025507; after epoch 512=0.027149; selected epoch=5; minimum matched training Brier=0.023894.
- cnn: best validation Brier through epoch 512=0.025494; after epoch 512=0.028326; selected epoch=8; minimum matched training Brier=0.024292.
- mlp: best validation Brier through epoch 512=0.025113; after epoch 512=0.025827; selected epoch=442; minimum matched training Brier=0.023726.
- residual_mlp: best validation Brier through epoch 512=0.025231; after epoch 512=0.025893; selected epoch=266; minimum matched training Brier=0.024083.
- mixed: best validation Brier through epoch 512=0.025458; after epoch 512=0.027703; selected epoch=205; minimum matched training Brier=0.023742.
- neural_mixed: best validation Brier through epoch 512=0.025552; after epoch 512=0.029517; selected epoch=73; minimum matched training Brier=0.020321.

## Saved artifacts and limits

`protocol.json` binds all input cache hashes, source hashes and the prespecified search. `candidate_selection.json`, `finalist_selection.json` and `selection.json` record validation-only selection. Candidate folders contain the complete per-epoch histories, selected public checkpoints and resumable final optimizer/RNG states. `predictions/` retains probabilities for all base rows and matched identities/weights. `metrics.json` retains calibration, exact and clipped NLL, Bernoulli distances, KL, AP, PR AUC, F1 and MCC. Classification thresholds are selected independently on native and matched validation populations.

The training labels are retrospective reconstructions. Scores are inverse-inclusion-weighted sampled estimates, not exact full-grid population scores. No active-flame residence assumption was introduced. The search uses one seed and does not establish robustness, a globally best parameter setting, double descent, or grokking.

<!-- BEGIN COMPLETE PROBABILITY EVALUATION -->
## Complete evaluation metrics and graphs

All scalar fields in saved `metrics.json` are reported below, including nested classification metrics, weighted ECE, thresholds, and support diagnostics. Every metric has a grouped bar graph and numerical values for training, validation, and test. Newly added scalar evaluation fields are discovered automatically.

### All metrics at a glance

[Open the all-metric bar dashboard](evaluation/overview.html). Select any model and either the matched or native cohort; all 75 fields appear together. Use Larger charts for an expanded view. Each card retains raw values and its own scale. The initial model, **mlp K=7**, comes from the saved validation selection.

![All numeric fields as bar charts for the saved validation-selected model](evaluation/figures/overview_common.png)

[Scalable matched overview (SVG)](evaluation/figures/overview_common.svg) · [Native overview (PNG)](evaluation/figures/overview_native.png) · [Scalable native overview (SVG)](evaluation/figures/overview_native.svg)

**Comparison populations.** Matched results compare all models on identical current 3×3-contact rows with their original inverse inclusion weights. Native results use each model's own K-contact population; compare families within the same K. Full prediction coverage describes all base rows and is separate from both scoring populations. Training, validation, and test are reported separately; their split construction is defined by the saved training protocol. Each graph keeps these populations separate, with independent horizontal axis scales and a zero bar baseline.

**Probability reference.** For row i, yᵢ ∈ {0,1} is the reconstructed next-hour outcome, pᵢ ∈ [0,1] is the saved prediction, and wᵢ > 0 is its original sampling weight. The Bernoulli reference is Pᵢ=(1−yᵢ,yᵢ), the prediction is Qᵢ=(1−pᵢ,pᵢ), and every distance mean is Σᵢwᵢd(Pᵢ,Qᵢ)/Σᵢwᵢ. These compare predictions with binary empirical outcomes, not a known true conditional-probability field or two models. They do not measure spatial fire-front displacement. The endpoint is first-new-burning in the next hour, not currently active flame.

| Quantity per row | Definition |
|---|---|
| Exact KL | ΣₓPᵢ(x) ln(Pᵢ(x)/Qᵢ(x)); equals exact NLL for binary yᵢ |
| Floored KL | Same directed KL after clipping pᵢ to [ε,1−ε]; equals floored log loss for binary yᵢ; ε is reported below |
| Total variation | ½Σₓ&#124;Pᵢ(x)−Qᵢ(x)&#124; = &#124;yᵢ−pᵢ&#124; |
| Hellinger | √(½Σₓ(√Pᵢ(x)−√Qᵢ(x))²) |
| Jensen-Shannon divergence | ½KL(Pᵢ ∥ Mᵢ)+½KL(Qᵢ ∥ Mᵢ), Mᵢ=(Pᵢ+Qᵢ)/2 |
| Jensen-Shannon distance | Square root of each row's JS divergence, then weighted averaging |
| Bhattacharyya | −ln(Σₓ√(Pᵢ(x)Qᵢ(x))) |
| Wasserstein-1 / Wasserstein-2 | &#124;yᵢ−pᵢ&#124; / √&#124;yᵢ−pᵢ&#124; for support {0,1} with unit ground distance |

Natural logarithms give divergences and log loss in nats. Exact zero-probability failures remain +∞ in tables and graph status columns. N/A means the evaluator returned an undefined result; missing means that field was not saved for that model/split. Neither is changed to zero. Bounded distances may reward low probabilities in an imbalanced population; retain Brier, log loss, positive-class scores, ranking, and classification results when interpreting them. No test data are used to reselect models or thresholds.

**Classification.** Decisions use pᵢ ≥ threshold. Threshold 0.5 and the separately validation-selected F1 and MCC thresholds are reported explicitly and applied unchanged to all splits. TP, FP, TN, and FN are weighted population counts; precision=TP/(TP+FP), recall=TP/(TP+FN), F1=2TP/(2TP+FP+FN), and MCC=(TP·TN−FP·FN)/√((TP+FP)(TP+FN)(TN+FP)(TN+FN)). The evaluator assigns zero when a classification denominator is zero. Average precision is non-interpolated; PR AUC uses trapezoidal integration. They are different metrics.

[All metric cells as CSV](evaluation/metrics.csv) · [All reliability-bin values as CSV](evaluation/calibration_bins.csv) · [Cohort summaries as CSV](evaluation/cohorts.csv) · [Coverage and file hashes](evaluation/manifest.json)

### Probability scores

#### Weighted Brier score

Saved field: `brier`. Lower is better.

![Weighted Brier score across models and splits](evaluation/figures/001_brier.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.025772556 | 0.025770246 | 0.081429845 | 0.025772556 | 0.025770246 | 0.081429845 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.025734185 | 0.02576005 | 0.08051978 | 0.016103063 | 0.016112993 | 0.053203672 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.025722284 | 0.025751726 | 0.080542895 | 0.012227211 | 0.012234266 | 0.040954218 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.025717933 | 0.025747455 | 0.080587059 | 0.010112134 | 0.010117838 | 0.033385053 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.025740659 | 0.025746345 | 0.080701076 | 0.025740659 | 0.025746345 | 0.080701076 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.025594186 | 0.02579785 | 0.072257169 | 0.016024417 | 0.016139836 | 0.049611805 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.025534963 | 0.025873457 | 0.072619145 | 0.012146067 | 0.012296897 | 0.038828761 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.025500854 | 0.02602299 | 0.073134161 | 0.010034273 | 0.010233367 | 0.032489122 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.025480235 | 0.025507429 | 0.072307278 | 0.025480235 | 0.025507429 | 0.072307278 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.025546364 | 0.025614517 | 0.096723252 | 0.015988452 | 0.016084372 | 0.067162987 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.025792294 | 0.025948568 | 0.075406331 | 0.012270381 | 0.012335711 | 0.038777535 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.025536732 | 0.025547048 | 0.085549587 | 0.010046843 | 0.010256357 | 0.035009919 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.025491083 | 0.025493543 | 0.073497007 | 0.025491083 | 0.025493543 | 0.073497007 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.025333077 | 0.025683141 | 0.079008667 | 0.015859082 | 0.016059897 | 0.052360752 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.025380674 | 0.025494879 | 0.098383822 | 0.012051486 | 0.012104349 | 0.049242182 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.02533184 | 0.025720902 | 0.0990825 | 0.0099475628 | 0.010089521 | 0.055350711 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.025299933 | 0.025255257 | 0.073540958 | 0.025299933 | 0.025255257 | 0.073540958 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.025189043 | 0.025246245 | 0.077595193 | 0.015750844 | 0.015786318 | 0.053151161 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.024922647 | 0.025112952 | 0.092240741 | 0.011836941 | 0.011919406 | 0.06264904 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.024938083 | 0.025197973 | 0.084221855 | 0.0098051077 | 0.0098982074 | 0.043491469 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.025229663 | 0.025329777 | 0.073586338 | 0.025229663 | 0.025329777 | 0.073586338 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.025164122 | 0.025230682 | 0.08723683 | 0.015732389 | 0.015770516 | 0.064763926 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.025041929 | 0.025250192 | 0.073859634 | 0.011906204 | 0.011993206 | 0.040708846 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.024977518 | 0.025237954 | 0.075090101 | 0.0098227982 | 0.010018052 | 0.032613703 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.025403338 | 0.025458073 | 0.083845651 | 0.0099770851 | 0.0099914179 | 0.034248819 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.025283765 | 0.02555188 | 0.076920286 | 0.0099357463 | 0.010029041 | 0.032220379 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.024711573 | 0.026989427 | 0.072258896 | 0.024711573 | 0.026989427 | 0.072258896 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.024635472 | 0.026483046 | 0.073185296 | 0.015383845 | 0.016672055 | 0.054535402 |

#### Floored log loss (nats)

Saved field: `clipped_log_loss`. Lower is better.

![Floored log loss (nats) across models and splits](evaluation/figures/002_clipped_log_loss.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.11692524 | 0.11691807 | 0.32242209 | 0.11692524 | 0.11691807 | 0.32242209 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.11631024 | 0.11657498 | 0.31931025 | 0.076007079 | 0.076122113 | 0.24482469 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.1167232 | 0.11700243 | 0.32644351 | 0.061452315 | 0.061521256 | 0.22922452 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.11662756 | 0.11690974 | 0.32660481 | 0.051610425 | 0.051677105 | 0.19566403 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.11660971 | 0.1166654 | 0.31272843 | 0.11660971 | 0.1166654 | 0.31272843 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.11658676 | 0.11745505 | 0.25539624 | 0.075926465 | 0.076423189 | 0.18536345 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.11653839 | 0.11797187 | 0.25620492 | 0.058797528 | 0.059442728 | 0.15030488 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.11645172 | 0.11819852 | 0.25761718 | 0.049081523 | 0.049801073 | 0.12872419 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.11396072 | 0.11412986 | 0.26212617 | 0.11396072 | 0.11412986 | 0.26212617 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.13143538 | 0.13035267 | 0.65623925 | 0.086053545 | 0.085593549 | 0.48189959 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.12000547 | 0.12093099 | 0.28001292 | 0.060686089 | 0.061143155 | 0.15500335 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.1270588 | 0.12662474 | 0.99292069 | 0.053400084 | 0.056651573 | 0.43504967 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.11507752 | 0.11532758 | 0.26646838 | 0.11507752 | 0.11532758 | 0.26646838 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.11561113 | 0.11842484 | 0.30505167 | 0.076443546 | 0.07801283 | 0.22137172 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.12059542 | 0.12160878 | 0.69051058 | 0.061491995 | 0.061950139 | 0.37485716 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.11861604 | 0.12435831 | 0.71285963 | 0.050128578 | 0.052225619 | 0.48427862 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.1169909 | 0.11653584 | 0.33602801 | 0.1169909 | 0.11653584 | 0.33602801 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.11458179 | 0.11509097 | 0.30256724 | 0.078146968 | 0.078467679 | 0.24612057 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.11276275 | 0.11403675 | 0.66769205 | 0.058445282 | 0.059096616 | 0.53746685 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.11181093 | 0.11303507 | 0.42655041 | 0.049033083 | 0.049500868 | 0.28228368 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.1119622 | 0.11266719 | 0.26291055 | 0.1119622 | 0.11266719 | 0.26291055 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.11465613 | 0.11319386 | 0.51179511 | 0.077860435 | 0.077172355 | 0.41482318 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.11190013 | 0.11287829 | 0.26230913 | 0.058134137 | 0.05848162 | 0.17935759 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.11300369 | 0.11445229 | 0.28410387 | 0.049603115 | 0.050417864 | 0.17463898 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.12633771 | 0.12606045 | 0.68936702 | 0.060010766 | 0.059927272 | 0.31378747 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.11862067 | 0.12079524 | 0.30205658 | 0.055065982 | 0.055867764 | 0.19530786 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.11181879 | 0.11958554 | 0.24382983 | 0.11181879 | 0.11958554 | 0.24382983 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.11098315 | 0.11756888 | 0.24658301 | 0.072478657 | 0.077196669 | 0.18544418 |

#### Exact negative log likelihood (nats)

Saved field: `exact_negative_log_likelihood_mean`. Lower is better.

![Exact negative log likelihood (nats) across models and splits](evaluation/figures/003_exact_negative_log_likelihood_mean.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.11692524 | 0.11691807 | 0.32242209 | 0.11692524 | 0.11691807 | 0.32242209 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.11631024 | 0.11657498 | 0.31931025 | 0.076007079 | 0.076122113 | 0.24482469 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.1167232 | 0.11700243 | 0.32644351 | 0.061452315 | 0.061521256 | 0.22922452 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.11662756 | 0.11690974 | 0.32660481 | 0.051610425 | 0.051677105 | 0.19566403 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.11660971 | 0.1166654 | 0.31272843 | 0.11660971 | 0.1166654 | 0.31272843 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.11658676 | 0.11745505 | 0.25539624 | 0.075926465 | 0.076423189 | 0.18536345 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.11653839 | 0.11797187 | 0.25620492 | 0.058797528 | 0.059442728 | 0.15030488 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.11645172 | 0.11819852 | 0.25761718 | 0.049081523 | 0.049801073 | 0.12872419 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.11396072 | 0.11412986 | 0.26212617 | 0.11396072 | 0.11412986 | 0.26212617 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.12000547 | 0.12093099 | 0.28001292 | 0.060686089 | 0.061143155 | 0.15500335 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.11507752 | 0.11532758 | 0.26646838 | 0.11507752 | 0.11532758 | 0.26646838 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.11276275 | +∞ | +∞ | +∞ | +∞ | +∞ |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.1119622 | 0.11266719 | 0.26291055 | 0.1119622 | 0.11266719 | 0.26291055 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.11190013 | 0.11287829 | 0.26230913 | +∞ | +∞ | +∞ |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.11300369 | 0.11445229 | 0.28410387 | +∞ | +∞ | +∞ |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.11181879 | 0.11958554 | 0.24382983 | 0.11181879 | 0.11958554 | 0.24382983 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.11098315 | 0.11756888 | 0.24658301 | 0.072478657 | 0.077196669 | 0.18544418 |

#### Negative-class Brier score

Saved field: `negative_class_brier`. Lower is better.

![Negative-class Brier score across models and splits](evaluation/figures/004_negative_class_brier.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.0010978479 | 0.0011019136 | 0.0009442293 | 0.0010978479 | 0.0011019136 | 0.0009442293 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.0016458144 | 0.0016753116 | 0.0014182441 | 0.00095926789 | 0.00097609613 | 0.00075037325 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.0016381425 | 0.001671175 | 0.0014125071 | 0.00070398955 | 0.0007178198 | 0.000516678 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.0016108288 | 0.0016439526 | 0.0013907866 | 0.00056360275 | 0.00057490928 | 0.00038997766 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.0012438472 | 0.0012483069 | 0.0010250618 | 0.0012438472 | 0.0012483069 | 0.0010250618 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.0013803067 | 0.0015719784 | 0.009202554 | 0.00082791375 | 0.00093835526 | 0.0068112571 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.0013666144 | 0.0017068175 | 0.0084631428 | 0.00061596448 | 0.00076979762 | 0.0049849481 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.0013465408 | 0.0018621149 | 0.009829228 | 0.00050879567 | 0.00070756987 | 0.0048995622 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.00075733994 | 0.00080357237 | 0.0041136468 | 0.00075733994 | 0.00080357237 | 0.0041136468 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.001320617 | 0.0013409371 | 0.038527255 | 0.00077185445 | 0.00084375861 | 0.026546722 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.00097471244 | 0.0011518382 | 0.0025875743 | 0.00046243415 | 0.00054276186 | 0.0012866392 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.0013131928 | 0.001302327 | 0.0022650986 | 0.00048773675 | 0.00069042077 | 0.00080854025 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.0012027512 | 0.0012014282 | 0.0049396137 | 0.0012027512 | 0.0012014282 | 0.0049396137 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.0010778551 | 0.001452594 | 0.0015268367 | 0.00063550432 | 0.00085342647 | 0.00092972676 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.0012947733 | 0.0013733401 | 0.037682248 | 0.0005571803 | 0.00059061386 | 0.015600521 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.0013212612 | 0.001658085 | 0.037986273 | 0.00046307289 | 0.00058479542 | 0.028430147 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.0014442456 | 0.0013937071 | 0.010638096 | 0.0014442456 | 0.0013937071 | 0.010638096 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.001185553 | 0.0011948945 | 0.0095970981 | 0.00069219698 | 0.00069629257 | 0.0069853177 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.0011865007 | 0.0013114018 | 0.038514799 | 0.00051031107 | 0.00056373331 | 0.033409681 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.0011428346 | 0.0013618221 | 0.022117623 | 0.00040061184 | 0.00047696968 | 0.01571163 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.00096331322 | 0.0010605283 | 0.012052232 | 0.00096331322 | 0.0010605283 | 0.012052232 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.0010687426 | 0.001117483 | 0.030232051 | 0.00062634325 | 0.00065145598 | 0.025693252 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.0012917749 | 0.0014670744 | 0.016062872 | 0.00055611244 | 0.00063055153 | 0.0087982724 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.0014874696 | 0.0017353253 | 0.0085665392 | 0.00052219351 | 0.00071567103 | 0.0033807888 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.00070043843 | 0.00075237497 | 0.0060903383 | 0.00024623308 | 0.00026452033 | 0.0018920712 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.00077667302 | 0.0010116301 | 0.012031574 | 0.0002733343 | 0.00035544881 | 0.0036065117 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.0013019968 | 0.0036224681 | 0.019266721 | 0.0013019968 | 0.0036224681 | 0.019266721 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.00098232433 | 0.0028545886 | 0.017947993 | 0.00067320283 | 0.0019708818 | 0.017575417 |

#### Positive-class Brier score

Saved field: `positive_class_brier`. Lower is better.

![Positive-class Brier score across models and splits](evaluation/figures/005_positive_class_brier.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.91842036 | 0.91840728 | 0.92965228 | 0.91842036 | 0.91840728 | 0.92965228 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.89717029 | 0.89727943 | 0.91415566 | 0.90293454 | 0.90304262 | 0.92794462 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.89700538 | 0.89711958 | 0.91448284 | 0.9051823 | 0.90529224 | 0.93439699 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.89783177 | 0.89794581 | 0.91522134 | 0.90716089 | 0.90726795 | 0.93812156 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.9119528 | 0.91222121 | 0.92039128 | 0.9119528 | 0.91222121 | 0.92039128 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.90157077 | 0.9024242 | 0.73677763 | 0.90594251 | 0.90685365 | 0.76337801 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.89986439 | 0.90035647 | 0.74874692 | 0.90563437 | 0.90618094 | 0.78658714 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.89932253 | 0.90029741 | 0.74029268 | 0.90491719 | 0.90577296 | 0.7890045 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.91987128 | 0.91942995 | 0.79098685 | 0.91987128 | 0.91942995 | 0.79098685 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.90195229 | 0.90396722 | 0.71003968 | 0.90708331 | 0.9090911 | 0.74450287 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.92360879 | 0.92323176 | 0.84282921 | 0.92728937 | 0.92683546 | 0.86711599 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.90186277 | 0.90285549 | 0.9632688 | 0.90808905 | 0.90956951 | 0.97282369 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.90416112 | 0.90451695 | 0.79601019 | 0.90416112 | 0.90451695 | 0.79601019 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.9028053 | 0.90247868 | 0.89557478 | 0.90736266 | 0.90706606 | 0.9100537 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.89672741 | 0.89834592 | 0.73810604 | 0.90276585 | 0.90495205 | 0.79253415 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.8939537 | 0.89644704 | 0.74296389 | 0.90097985 | 0.90364809 | 0.79352202 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.88831834 | 0.88869843 | 0.73646213 | 0.88831834 | 0.88869843 | 0.73646213 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.89355446 | 0.89555748 | 0.79421405 | 0.89759601 | 0.89996955 | 0.82303894 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.88361645 | 0.88638501 | 0.65844812 | 0.88955782 | 0.89250993 | 0.70867483 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.88576999 | 0.88772207 | 0.73872641 | 0.89332224 | 0.89560794 | 0.80522438 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.90310445 | 0.90352576 | 0.72208246 | 0.90310445 | 0.90352576 | 0.72208246 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.89685378 | 0.89777993 | 0.68799923 | 0.90035321 | 0.90165498 | 0.71632865 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.8842425 | 0.88585527 | 0.68296861 | 0.89144516 | 0.89312516 | 0.74575349 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.87476835 | 0.87569339 | 0.77616913 | 0.88357975 | 0.88455386 | 0.83419043 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.91907103 | 0.91944722 | 0.90329395 | 0.92415416 | 0.92443686 | 0.92148218 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.91186778 | 0.91355418 | 0.76076995 | 0.91768314 | 0.9194631 | 0.81682264 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.87159117 | 0.87253557 | 0.63073323 | 0.87159117 | 0.87253557 | 0.63073323 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.88032666 | 0.88149164 | 0.65532061 | 0.87684954 | 0.87807094 | 0.67090106 |

### Probability distances

#### Bernoulli Bhattacharyya distance

Saved field: `bernoulli_bhattacharyya_distance_mean`. Lower is better.

![Bernoulli Bhattacharyya distance across models and splits](evaluation/figures/006_bernoulli_bhattacharyya_distance_mean.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.05846262 | 0.058459034 | 0.16121104 | 0.05846262 | 0.058459034 | 0.16121104 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.058155119 | 0.058287491 | 0.15965513 | 0.038003539 | 0.038061057 | 0.12241235 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.058361598 | 0.058501216 | 0.16322176 | 0.030726157 | 0.030760628 | 0.11461226 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.058313781 | 0.05845487 | 0.16330241 | 0.025805213 | 0.025838552 | 0.097832016 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.058304854 | 0.058332701 | 0.15636421 | 0.058304854 | 0.058332701 | 0.15636421 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.058293382 | 0.058727524 | 0.12769812 | 0.037963232 | 0.038211595 | 0.092681723 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.058269196 | 0.058985937 | 0.12810246 | 0.029398764 | 0.029721364 | 0.075152441 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.058225861 | 0.059099259 | 0.12880859 | 0.024540762 | 0.024900536 | 0.064362097 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.056980361 | 0.057064929 | 0.13106308 | 0.056980361 | 0.057064929 | 0.13106308 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.060002737 | 0.060465493 | 0.14000646 | 0.030343045 | 0.030571577 | 0.077501676 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.057538762 | 0.057663789 | 0.13323419 | 0.057538762 | 0.057663789 | 0.13323419 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.056381376 | +∞ | +∞ | +∞ | +∞ | +∞ |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.055981098 | 0.056333594 | 0.13145528 | 0.055981098 | 0.056333594 | 0.13145528 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.055950064 | 0.056439144 | 0.13115457 | +∞ | +∞ | +∞ |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.056501844 | 0.057226143 | 0.14205193 | +∞ | +∞ | +∞ |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.055909397 | 0.059792772 | 0.12191491 | 0.055909397 | 0.059792772 | 0.12191491 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.055491574 | 0.058784438 | 0.1232915 | 0.036239328 | 0.038598334 | 0.092722092 |

#### Bernoulli Hellinger distance

Saved field: `bernoulli_hellinger_distance_mean`. Lower is better.

![Bernoulli Hellinger distance across models and splits](evaluation/figures/007_bernoulli_hellinger_distance_mean.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.13690977 | 0.13683205 | 0.18074073 | 0.13690977 | 0.13683205 | 0.18074073 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.13806384 | 0.13816372 | 0.18000523 | 0.08878132 | 0.088924734 | 0.11446215 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.13393071 | 0.13395377 | 0.17596943 | 0.061676869 | 0.061691685 | 0.079848174 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.13369319 | 0.13372459 | 0.17587432 | 0.050967513 | 0.050987345 | 0.064035735 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.13959151 | 0.1394212 | 0.18175747 | 0.13959151 | 0.1394212 | 0.18175747 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.12964902 | 0.13050016 | 0.17885902 | 0.090746015 | 0.091297725 | 0.12981547 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.12871557 | 0.12998408 | 0.17675667 | 0.074680256 | 0.075642068 | 0.10487771 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.1288074 | 0.1300411 | 0.17792332 | 0.065936536 | 0.066882127 | 0.090124254 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.11972552 | 0.12002173 | 0.16659746 | 0.11972552 | 0.12002173 | 0.16659746 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.1200535 | 0.12039583 | 0.17677666 | 0.076837687 | 0.077226268 | 0.11687512 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.12177082 | 0.12317757 | 0.15958747 | 0.080193206 | 0.081185797 | 0.098978979 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.1243307 | 0.1241766 | 0.15900598 | 0.055857078 | 0.056213025 | 0.064491201 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.12793163 | 0.12757738 | 0.17106827 | 0.12793163 | 0.12757738 | 0.17106827 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.12704849 | 0.12821768 | 0.16935355 | 0.087453041 | 0.088192314 | 0.11360783 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.12623208 | 0.12640831 | 0.18730358 | 0.061813704 | 0.061985745 | 0.089530852 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.1192711 | 0.11969172 | 0.16670159 | 0.051376333 | 0.051672649 | 0.08359079 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.12294734 | 0.12281301 | 0.15992643 | 0.12294734 | 0.12281301 | 0.15992643 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.11861878 | 0.11859459 | 0.16453832 | 0.071605909 | 0.071608282 | 0.10401465 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.12137786 | 0.12211625 | 0.17702958 | 0.05703932 | 0.057536633 | 0.10039275 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.12167592 | 0.12219234 | 0.16761566 | 0.050560923 | 0.050890315 | 0.077110289 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.12110876 | 0.12195574 | 0.17221147 | 0.12110876 | 0.12195574 | 0.17221147 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.11697703 | 0.1181221 | 0.17169133 | 0.072144915 | 0.07282228 | 0.11668723 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.12208549 | 0.12307183 | 0.17079119 | 0.056866125 | 0.057345732 | 0.086425786 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.12620638 | 0.12766885 | 0.1719981 | 0.049329729 | 0.050066936 | 0.065578389 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.11106536 | 0.11119701 | 0.15171204 | 0.040535127 | 0.040561047 | 0.057363281 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.10738571 | 0.10944938 | 0.16054915 | 0.041790503 | 0.042513571 | 0.063091436 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.13513222 | 0.13990693 | 0.20140075 | 0.13513222 | 0.13990693 | 0.20140075 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.12624436 | 0.13103869 | 0.19344877 | 0.10089872 | 0.10481403 | 0.16274149 |

#### Bernoulli Jensen-Shannon distance

Saved field: `bernoulli_jensen_shannon_distance_mean`. Lower is better.

![Bernoulli Jensen-Shannon distance across models and splits](evaluation/figures/008_bernoulli_jensen_shannon_distance_mean.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.11508813 | 0.11502329 | 0.15354994 | 0.11508813 | 0.11502329 | 0.15354994 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.11611476 | 0.1161995 | 0.15297311 | 0.074611665 | 0.074731832 | 0.097072331 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.11266438 | 0.11268552 | 0.14956453 | 0.051857484 | 0.051870433 | 0.067676038 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.11246359 | 0.1124917 | 0.14948266 | 0.042847103 | 0.042864132 | 0.054242862 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.11734453 | 0.11720215 | 0.15445536 | 0.11734453 | 0.11720215 | 0.15445536 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.10900888 | 0.10972918 | 0.15209903 | 0.076198997 | 0.076664665 | 0.11018916 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.1082225 | 0.10929911 | 0.15035242 | 0.06265939 | 0.063469943 | 0.088926514 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.10829485 | 0.10935058 | 0.15135377 | 0.055294921 | 0.056093873 | 0.076361087 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.10068764 | 0.10093848 | 0.14172312 | 0.10068764 | 0.10093848 | 0.14172312 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.10096085 | 0.10125651 | 0.1497547 | 0.064572143 | 0.064904756 | 0.098894565 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.10236692 | 0.10355052 | 0.13587573 | 0.067227933 | 0.068060374 | 0.08387445 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.10456675 | 0.10444097 | 0.13361233 | 0.04688851 | 0.047185665 | 0.054075531 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.10758614 | 0.10729068 | 0.14553642 | 0.10758614 | 0.10729068 | 0.14553642 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.10683023 | 0.10781411 | 0.14406425 | 0.073443731 | 0.074065382 | 0.096446964 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.106175 | 0.10632495 | 0.15858188 | 0.051939692 | 0.052084235 | 0.075642154 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.10034799 | 0.10070005 | 0.14134438 | 0.043154035 | 0.043401382 | 0.070621361 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.10345471 | 0.10334523 | 0.13588496 | 0.10345471 | 0.10334523 | 0.13588496 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.09981827 | 0.099798506 | 0.14007707 | 0.060244957 | 0.060247139 | 0.088477752 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.10212212 | 0.10274617 | 0.14999947 | 0.047960553 | 0.048378341 | 0.084910185 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.10235489 | 0.10279987 | 0.14251447 | 0.042474886 | 0.042754251 | 0.065371168 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.10187493 | 0.10258795 | 0.14655135 | 0.10187493 | 0.10258795 | 0.14655135 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.098405562 | 0.099375118 | 0.14571046 | 0.060665297 | 0.061238488 | 0.098961541 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.10272209 | 0.10355745 | 0.14542449 | 0.047821249 | 0.04822656 | 0.07348877 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.10617514 | 0.10741136 | 0.14631374 | 0.041466215 | 0.042091789 | 0.055609508 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.093405431 | 0.093519312 | 0.12818136 | 0.034081571 | 0.034104371 | 0.048419411 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.090346526 | 0.092081725 | 0.13672319 | 0.035130541 | 0.035738377 | 0.05351886 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.11356834 | 0.11766264 | 0.17115336 | 0.11356834 | 0.11766264 | 0.17115336 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.10611447 | 0.11020891 | 0.16450115 | 0.084636949 | 0.087970519 | 0.13811918 |

#### Bernoulli Jensen-Shannon divergence (nats)

Saved field: `bernoulli_jensen_shannon_divergence_mean`. Lower is better.

![Bernoulli Jensen-Shannon divergence (nats) across models and splits](evaluation/figures/009_bernoulli_jensen_shannon_divergence_mean.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.026213977 | 0.026209441 | 0.062087313 | 0.026213977 | 0.026209441 | 0.062087313 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.027182693 | 0.027240741 | 0.062184537 | 0.016744456 | 0.016775711 | 0.040429834 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.026950037 | 0.02701409 | 0.06201834 | 0.012459662 | 0.012481813 | 0.030765103 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.02688231 | 0.026947562 | 0.062004126 | 0.010239467 | 0.010258019 | 0.024967297 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.026634646 | 0.026627062 | 0.061732087 | 0.026634646 | 0.026627062 | 0.061732087 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.025475457 | 0.025720074 | 0.057496866 | 0.016085857 | 0.016220195 | 0.039791139 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.025319405 | 0.025737768 | 0.057375927 | 0.012314359 | 0.012524071 | 0.03117745 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.02527 | 0.025766904 | 0.057858911 | 0.01029648 | 0.010521617 | 0.026149103 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.023834278 | 0.023925946 | 0.055585744 | 0.023834278 | 0.023925946 | 0.055585744 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.025005162 | 0.025133239 | 0.072176912 | 0.015434956 | 0.015551644 | 0.049449698 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.024385625 | 0.024694737 | 0.05632095 | 0.012388625 | 0.012556964 | 0.029679694 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.02552915 | 0.025541211 | 0.064608378 | 0.0099210735 | 0.01007353 | 0.025955376 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.025250512 | 0.025259905 | 0.057137872 | 0.025250512 | 0.025259905 | 0.057137872 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.025054021 | 0.025458232 | 0.059658962 | 0.015747646 | 0.015983315 | 0.039323157 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.025653209 | 0.025770551 | 0.074148859 | 0.011919573 | 0.011972912 | 0.036493654 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.024971996 | 0.025270725 | 0.072489635 | 0.0096332247 | 0.0097448745 | 0.039690091 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.025431704 | 0.02545247 | 0.05652637 | 0.025431704 | 0.02545247 | 0.05652637 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.02465029 | 0.024696909 | 0.058848927 | 0.015162967 | 0.015189628 | 0.03972539 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.024820078 | 0.025070595 | 0.069341319 | 0.011533221 | 0.011644388 | 0.045731926 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.024430229 | 0.024730952 | 0.062912378 | 0.0094166754 | 0.0095263991 | 0.03176073 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.024244674 | 0.024462687 | 0.057641473 | 0.024244674 | 0.024462687 | 0.057641473 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.023829943 | 0.024094946 | 0.065210249 | 0.014681169 | 0.014834848 | 0.047691762 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.024852225 | 0.025165985 | 0.057948528 | 0.011539788 | 0.011671674 | 0.031443996 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.025528164 | 0.025966826 | 0.058534878 | 0.0097654028 | 0.0099916075 | 0.024613368 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.023283323 | 0.023357329 | 0.061894239 | 0.0089407968 | 0.0089629012 | 0.025143155 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.02290659 | 0.023412903 | 0.058495517 | 0.0088442512 | 0.009022134 | 0.02426738 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.025274897 | 0.027346927 | 0.061108024 | 0.025274897 | 0.027346927 | 0.061108024 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.02402895 | 0.025900856 | 0.060202032 | 0.015950785 | 0.017330443 | 0.046503894 |

#### Exact Bernoulli KL divergence (nats)

Saved field: `bernoulli_kl_divergence_mean`. Lower is better.

![Exact Bernoulli KL divergence (nats) across models and splits](evaluation/figures/010_bernoulli_kl_divergence_mean.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.11692524 | 0.11691807 | 0.32242209 | 0.11692524 | 0.11691807 | 0.32242209 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.11631024 | 0.11657498 | 0.31931025 | 0.076007079 | 0.076122113 | 0.24482469 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.1167232 | 0.11700243 | 0.32644351 | 0.061452315 | 0.061521256 | 0.22922452 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.11662756 | 0.11690974 | 0.32660481 | 0.051610425 | 0.051677105 | 0.19566403 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.11660971 | 0.1166654 | 0.31272843 | 0.11660971 | 0.1166654 | 0.31272843 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.11658676 | 0.11745505 | 0.25539624 | 0.075926465 | 0.076423189 | 0.18536345 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.11653839 | 0.11797187 | 0.25620492 | 0.058797528 | 0.059442728 | 0.15030488 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.11645172 | 0.11819852 | 0.25761718 | 0.049081523 | 0.049801073 | 0.12872419 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.11396072 | 0.11412986 | 0.26212617 | 0.11396072 | 0.11412986 | 0.26212617 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.12000547 | 0.12093099 | 0.28001292 | 0.060686089 | 0.061143155 | 0.15500335 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.11507752 | 0.11532758 | 0.26646838 | 0.11507752 | 0.11532758 | 0.26646838 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.11276275 | +∞ | +∞ | +∞ | +∞ | +∞ |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.1119622 | 0.11266719 | 0.26291055 | 0.1119622 | 0.11266719 | 0.26291055 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.11190013 | 0.11287829 | 0.26230913 | +∞ | +∞ | +∞ |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.11300369 | 0.11445229 | 0.28410387 | +∞ | +∞ | +∞ |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | +∞ | +∞ | +∞ | +∞ | +∞ | +∞ |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.11181879 | 0.11958554 | 0.24382983 | 0.11181879 | 0.11958554 | 0.24382983 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.11098315 | 0.11756888 | 0.24658301 | 0.072478657 | 0.077196669 | 0.18544418 |

#### Bernoulli total variation distance

Saved field: `bernoulli_total_variation_distance_mean`. Lower is better.

![Bernoulli total variation distance across models and splits](evaluation/figures/011_bernoulli_total_variation_distance_mean.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.053884692 | 0.053875131 | 0.10817328 | 0.053884692 | 0.053875131 | 0.10817328 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.057454115 | 0.057608015 | 0.11054516 | 0.035016415 | 0.035102911 | 0.069861988 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.05677774 | 0.056947396 | 0.10993049 | 0.02579041 | 0.025852455 | 0.052237558 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.056555724 | 0.056728892 | 0.10978736 | 0.021108142 | 0.021160278 | 0.042058213 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.055354258 | 0.055321676 | 0.1086343 | 0.055354258 | 0.055321676 | 0.1086343 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.051984157 | 0.05258616 | 0.11111084 | 0.032825518 | 0.033154079 | 0.076563314 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.051558552 | 0.052599667 | 0.11022597 | 0.025194671 | 0.025728807 | 0.059637366 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.051407016 | 0.052560737 | 0.11143079 | 0.021155493 | 0.021702371 | 0.050003714 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.046812945 | 0.047084749 | 0.10283326 | 0.046812945 | 0.047084749 | 0.10283326 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.050418346 | 0.050798181 | 0.12161303 | 0.030797953 | 0.031110339 | 0.081656236 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.047944976 | 0.048781425 | 0.10070403 | 0.025024432 | 0.025491677 | 0.053112571 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.052234606 | 0.052277356 | 0.10556727 | 0.020049113 | 0.020285402 | 0.041300746 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.051480173 | 0.051494204 | 0.10678343 | 0.051480173 | 0.051494204 | 0.10678343 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.050892071 | 0.051779529 | 0.10502629 | 0.031915855 | 0.032436415 | 0.067975852 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.052835843 | 0.053080742 | 0.12607563 | 0.024174214 | 0.024283241 | 0.060356718 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.050850026 | 0.051328827 | 0.12016836 | 0.019322602 | 0.019504848 | 0.063223224 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.052490978 | 0.052605324 | 0.10249284 | 0.052490978 | 0.052605324 | 0.10249284 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.050070777 | 0.050146023 | 0.10665961 | 0.030439296 | 0.030479053 | 0.070030413 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.050855393 | 0.05144118 | 0.11938548 | 0.023262508 | 0.023522537 | 0.07508308 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.049663888 | 0.05039292 | 0.11148935 | 0.018834178 | 0.019099788 | 0.053454939 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.048605576 | 0.049186133 | 0.10963415 | 0.048605576 | 0.049186133 | 0.10963415 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.047324543 | 0.048142606 | 0.11326475 | 0.028827699 | 0.029302582 | 0.080802203 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.050985479 | 0.051780792 | 0.11128241 | 0.023284605 | 0.023619971 | 0.05849863 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.053198392 | 0.054346791 | 0.10948969 | 0.01996634 | 0.020518525 | 0.043311247 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.044978703 | 0.045161865 | 0.10226095 | 0.01696088 | 0.017017924 | 0.040956434 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.044094928 | 0.045414327 | 0.10788142 | 0.016756694 | 0.017220854 | 0.042946569 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.052280962 | 0.056817526 | 0.12679527 | 0.052280962 | 0.056817526 | 0.12679527 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.048371043 | 0.052744989 | 0.1223677 | 0.03294021 | 0.036227243 | 0.096987076 |

#### Bernoulli Wasserstein-1 distance

Saved field: `bernoulli_wasserstein_1_distance_mean`. Lower is better.

![Bernoulli Wasserstein-1 distance across models and splits](evaluation/figures/012_bernoulli_wasserstein_1_distance_mean.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.053884692 | 0.053875131 | 0.10817328 | 0.053884692 | 0.053875131 | 0.10817328 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.057454115 | 0.057608015 | 0.11054516 | 0.035016415 | 0.035102911 | 0.069861988 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.05677774 | 0.056947396 | 0.10993049 | 0.02579041 | 0.025852455 | 0.052237558 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.056555724 | 0.056728892 | 0.10978736 | 0.021108142 | 0.021160278 | 0.042058213 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.055354258 | 0.055321676 | 0.1086343 | 0.055354258 | 0.055321676 | 0.1086343 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.051984157 | 0.05258616 | 0.11111084 | 0.032825518 | 0.033154079 | 0.076563314 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.051558552 | 0.052599667 | 0.11022597 | 0.025194671 | 0.025728807 | 0.059637366 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.051407016 | 0.052560737 | 0.11143079 | 0.021155493 | 0.021702371 | 0.050003714 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.046812945 | 0.047084749 | 0.10283326 | 0.046812945 | 0.047084749 | 0.10283326 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.050418346 | 0.050798181 | 0.12161303 | 0.030797953 | 0.031110339 | 0.081656236 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.047944976 | 0.048781425 | 0.10070403 | 0.025024432 | 0.025491677 | 0.053112571 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.052234606 | 0.052277356 | 0.10556727 | 0.020049113 | 0.020285402 | 0.041300746 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.051480173 | 0.051494204 | 0.10678343 | 0.051480173 | 0.051494204 | 0.10678343 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.050892071 | 0.051779529 | 0.10502629 | 0.031915855 | 0.032436415 | 0.067975852 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.052835843 | 0.053080742 | 0.12607563 | 0.024174214 | 0.024283241 | 0.060356718 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.050850026 | 0.051328827 | 0.12016836 | 0.019322602 | 0.019504848 | 0.063223224 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.052490978 | 0.052605324 | 0.10249284 | 0.052490978 | 0.052605324 | 0.10249284 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.050070777 | 0.050146023 | 0.10665961 | 0.030439296 | 0.030479053 | 0.070030413 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.050855393 | 0.05144118 | 0.11938548 | 0.023262508 | 0.023522537 | 0.07508308 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.049663888 | 0.05039292 | 0.11148935 | 0.018834178 | 0.019099788 | 0.053454939 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.048605576 | 0.049186133 | 0.10963415 | 0.048605576 | 0.049186133 | 0.10963415 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.047324543 | 0.048142606 | 0.11326475 | 0.028827699 | 0.029302582 | 0.080802203 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.050985479 | 0.051780792 | 0.11128241 | 0.023284605 | 0.023619971 | 0.05849863 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.053198392 | 0.054346791 | 0.10948969 | 0.01996634 | 0.020518525 | 0.043311247 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.044978703 | 0.045161865 | 0.10226095 | 0.01696088 | 0.017017924 | 0.040956434 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.044094928 | 0.045414327 | 0.10788142 | 0.016756694 | 0.017220854 | 0.042946569 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.052280962 | 0.056817526 | 0.12679527 | 0.052280962 | 0.056817526 | 0.12679527 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.048371043 | 0.052744989 | 0.1223677 | 0.03294021 | 0.036227243 | 0.096987076 |

#### Bernoulli Wasserstein-2 distance

Saved field: `bernoulli_wasserstein_2_distance_mean`. Lower is better.

![Bernoulli Wasserstein-2 distance across models and splits](evaluation/figures/013_bernoulli_wasserstein_2_distance_mean.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.18524891 | 0.18513953 | 0.22951679 | 0.18524891 | 0.18513953 | 0.22951679 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.18702224 | 0.18715138 | 0.2290619 | 0.1203305 | 0.12052797 | 0.14427174 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.18117202 | 0.18119118 | 0.22323726 | 0.083219023 | 0.083236017 | 0.098969796 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.18083406 | 0.18086495 | 0.22307239 | 0.068754053 | 0.068778891 | 0.079063519 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.18909685 | 0.18885138 | 0.23152356 | 0.18909685 | 0.18885138 | 0.23152356 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.17501948 | 0.17616583 | 0.23199964 | 0.12305651 | 0.12380405 | 0.16887999 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.1737098 | 0.17540914 | 0.22889386 | 0.10159131 | 0.10290963 | 0.13665102 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.17384207 | 0.17545193 | 0.23043028 | 0.089916394 | 0.09120182 | 0.11763126 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.16098444 | 0.16139624 | 0.21401171 | 0.16098444 | 0.16139624 | 0.21401171 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.1613324 | 0.16181183 | 0.21648924 | 0.10330878 | 0.10384277 | 0.14150407 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.16362245 | 0.16556622 | 0.20271614 | 0.10926991 | 0.11065402 | 0.12780442 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.16747762 | 0.16726014 | 0.19232561 | 0.075638616 | 0.076056528 | 0.077595811 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.17268014 | 0.17217033 | 0.2200687 | 0.17268014 | 0.17217033 | 0.2200687 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.17143466 | 0.17295491 | 0.21475343 | 0.11845091 | 0.11942009 | 0.14373662 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.17027992 | 0.17048577 | 0.23084455 | 0.08342716 | 0.083649993 | 0.10900665 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.16042382 | 0.16085687 | 0.20135002 | 0.069347144 | 0.069707165 | 0.097954576 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.16574768 | 0.16557377 | 0.20314678 | 0.16574768 | 0.16557377 | 0.20314678 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.15962628 | 0.15956672 | 0.20903542 | 0.096108473 | 0.096096191 | 0.13019969 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.16363014 | 0.16460699 | 0.21910143 | 0.076777148 | 0.077450402 | 0.11954637 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.16404738 | 0.16470121 | 0.21037636 | 0.068270828 | 0.068708591 | 0.09421738 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.16311587 | 0.16427759 | 0.22197202 | 0.16311587 | 0.16427759 | 0.22197202 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.15724269 | 0.15885841 | 0.21413311 | 0.096832998 | 0.097788579 | 0.14305414 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.16463253 | 0.16596278 | 0.22015581 | 0.076527489 | 0.077178909 | 0.10969584 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.17049046 | 0.17247689 | 0.22077438 | 0.066539992 | 0.067529917 | 0.081997738 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.14858971 | 0.14875996 | 0.18466728 | 0.053919635 | 0.05395197 | 0.068631289 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.14347445 | 0.14629724 | 0.20379036 | 0.055729627 | 0.056718434 | 0.078626921 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.18312322 | 0.18925057 | 0.26497483 | 0.18312322 | 0.18925057 | 0.26497483 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.17051699 | 0.17680161 | 0.253321 | 0.13764549 | 0.14283783 | 0.21518776 |

#### Floored Bernoulli KL divergence (nats)

Saved field: `floored_bernoulli_kl_divergence_mean`. Lower is better.

![Floored Bernoulli KL divergence (nats) across models and splits](evaluation/figures/014_floored_bernoulli_kl_divergence_mean.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.11692524 | 0.11691807 | 0.32242209 | 0.11692524 | 0.11691807 | 0.32242209 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.11631024 | 0.11657498 | 0.31931025 | 0.076007079 | 0.076122113 | 0.24482469 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.1167232 | 0.11700243 | 0.32644351 | 0.061452315 | 0.061521256 | 0.22922452 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.11662756 | 0.11690974 | 0.32660481 | 0.051610425 | 0.051677105 | 0.19566403 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.11660971 | 0.1166654 | 0.31272843 | 0.11660971 | 0.1166654 | 0.31272843 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.11658676 | 0.11745505 | 0.25539624 | 0.075926465 | 0.076423189 | 0.18536345 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.11653839 | 0.11797187 | 0.25620492 | 0.058797528 | 0.059442728 | 0.15030488 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.11645172 | 0.11819852 | 0.25761718 | 0.049081523 | 0.049801073 | 0.12872419 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.11396072 | 0.11412986 | 0.26212617 | 0.11396072 | 0.11412986 | 0.26212617 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.13143538 | 0.13035267 | 0.65623925 | 0.086053545 | 0.085593549 | 0.48189959 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.12000547 | 0.12093099 | 0.28001292 | 0.060686089 | 0.061143155 | 0.15500335 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.1270588 | 0.12662474 | 0.99292069 | 0.053400084 | 0.056651573 | 0.43504967 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.11507752 | 0.11532758 | 0.26646838 | 0.11507752 | 0.11532758 | 0.26646838 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.11561113 | 0.11842484 | 0.30505167 | 0.076443546 | 0.07801283 | 0.22137172 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.12059542 | 0.12160878 | 0.69051058 | 0.061491995 | 0.061950139 | 0.37485716 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.11861604 | 0.12435831 | 0.71285963 | 0.050128578 | 0.052225619 | 0.48427862 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.1169909 | 0.11653584 | 0.33602801 | 0.1169909 | 0.11653584 | 0.33602801 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.11458179 | 0.11509097 | 0.30256724 | 0.078146968 | 0.078467679 | 0.24612057 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.11276275 | 0.11403675 | 0.66769205 | 0.058445282 | 0.059096616 | 0.53746685 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.11181093 | 0.11303507 | 0.42655041 | 0.049033083 | 0.049500868 | 0.28228368 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.1119622 | 0.11266719 | 0.26291055 | 0.1119622 | 0.11266719 | 0.26291055 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.11465613 | 0.11319386 | 0.51179511 | 0.077860435 | 0.077172355 | 0.41482318 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.11190013 | 0.11287829 | 0.26230913 | 0.058134137 | 0.05848162 | 0.17935759 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.11300369 | 0.11445229 | 0.28410387 | 0.049603115 | 0.050417864 | 0.17463898 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.12633771 | 0.12606045 | 0.68936702 | 0.060010766 | 0.059927272 | 0.31378747 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.11862067 | 0.12079524 | 0.30205658 | 0.055065982 | 0.055867764 | 0.19530786 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.11181879 | 0.11958554 | 0.24382983 | 0.11181879 | 0.11958554 | 0.24382983 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.11098315 | 0.11756888 | 0.24658301 | 0.072478657 | 0.077196669 | 0.18544418 |

### Ranking scores

#### Average precision (non-interpolated)

Saved field: `average_precision`. Higher is better.

![Average precision (non-interpolated) across models and splits](evaluation/figures/015_average_precision.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.055696602 | 0.055100931 | 0.13882003 | 0.055696602 | 0.055100931 | 0.13882003 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.061210368 | 0.059787431 | 0.14645712 | 0.058936238 | 0.057588421 | 0.13409458 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.062698931 | 0.060789157 | 0.15006989 | 0.059195652 | 0.05743314 | 0.12992717 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.06258887 | 0.060567678 | 0.14712864 | 0.058447475 | 0.056605453 | 0.12346268 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.06476942 | 0.063531916 | 0.18833733 | 0.06476942 | 0.063531916 | 0.18833733 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.078980992 | 0.070456465 | 0.31475877 | 0.075695826 | 0.067669548 | 0.24814682 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.083889193 | 0.069462737 | 0.31443469 | 0.07926462 | 0.065171108 | 0.22118147 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.086047086 | 0.069801071 | 0.30772426 | 0.080961246 | 0.064536686 | 0.20067695 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.09225204 | 0.089617274 | 0.36268763 | 0.09225204 | 0.089617274 | 0.36268763 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.077316792 | 0.074277093 | 0.22449888 | 0.073943269 | 0.070187686 | 0.18852465 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.067775755 | 0.06104073 | 0.33726649 | 0.062710196 | 0.056127024 | 0.25250143 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.073015153 | 0.068111471 | 0.091678974 | 0.069181296 | 0.0571724 | 0.05251623 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.083994577 | 0.085545343 | 0.31855053 | 0.083994577 | 0.085545343 | 0.31855053 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.098239112 | 0.077573441 | 0.25868749 | 0.094955309 | 0.075137308 | 0.22108296 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.079733265 | 0.073177254 | 0.19872125 | 0.077497299 | 0.070364345 | 0.1606209 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.08969175 | 0.072906302 | 0.22337735 | 0.086398194 | 0.069710283 | 0.13024762 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.099690023 | 0.096784807 | 0.37139608 | 0.099690023 | 0.096784807 | 0.37139608 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.10250807 | 0.099863333 | 0.32755312 | 0.10105255 | 0.097956856 | 0.26686852 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.12454065 | 0.10519888 | 0.30515419 | 0.12128137 | 0.10269967 | 0.18452756 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.12623648 | 0.10148934 | 0.31107529 | 0.12060262 | 0.09712574 | 0.17345878 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.10717127 | 0.095244608 | 0.3199477 | 0.10717127 | 0.095244608 | 0.3199477 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.11371194 | 0.10011134 | 0.31720545 | 0.1115996 | 0.098388657 | 0.2458899 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.11839128 | 0.10022545 | 0.33213661 | 0.1138674 | 0.096653176 | 0.2328284 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.12212485 | 0.1004796 | 0.33234966 | 0.11606768 | 0.090423688 | 0.23778276 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.09120223 | 0.085577098 | 0.18695727 | 0.08655273 | 0.081353403 | 0.13738055 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.1035895 | 0.084240942 | 0.27713797 | 0.098682561 | 0.080246531 | 0.20881077 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.14487609 | 0.082851686 | 0.27808245 | 0.14487609 | 0.082851686 | 0.27808245 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.1485451 | 0.085158367 | 0.2847081 | 0.14672174 | 0.082043329 | 0.20064307 |

#### Precision-recall AUC (trapezoidal)

Saved field: `precision_recall_auc`. Higher is better.

![Precision-recall AUC (trapezoidal) across models and splits](evaluation/figures/016_precision_recall_auc.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.072337775 | 0.072114224 | 0.14955101 | 0.072337775 | 0.072114224 | 0.14955101 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.06589919 | 0.06445939 | 0.14807134 | 0.063361888 | 0.061997572 | 0.13547929 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.065445875 | 0.063560158 | 0.15121483 | 0.061725559 | 0.05998496 | 0.13081961 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.064434298 | 0.062307787 | 0.14772214 | 0.060125144 | 0.058187297 | 0.12390535 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.064762062 | 0.063494096 | 0.18822851 | 0.064762062 | 0.063494096 | 0.18822851 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.078972601 | 0.070430422 | 0.31463218 | 0.075687813 | 0.067645266 | 0.24804602 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.083882573 | 0.069428089 | 0.314301 | 0.079258646 | 0.065139117 | 0.22108517 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.086041035 | 0.069780833 | 0.307592 | 0.080955963 | 0.064518752 | 0.20058852 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.092233848 | 0.089578822 | 0.3626111 | 0.092233848 | 0.089578822 | 0.3626111 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.079325053 | 0.074493955 | 0.25069796 | 0.075844246 | 0.070387714 | 0.21253875 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.067768837 | 0.061019857 | 0.33715578 | 0.062703788 | 0.056107571 | 0.2524182 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.073371721 | 0.068203593 | 0.079065731 | 0.07004505 | 0.060547971 | 0.04638643 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.083978632 | 0.08552599 | 0.31845272 | 0.083978632 | 0.08552599 | 0.31845272 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.098234853 | 0.077539458 | 0.25858747 | 0.094951381 | 0.075104987 | 0.22100124 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.080669079 | 0.074356125 | 0.22322057 | 0.078404053 | 0.071490801 | 0.17991057 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.089809817 | 0.075298564 | 0.25478047 | 0.086510428 | 0.072127192 | 0.15865168 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.099684127 | 0.096766613 | 0.37422473 | 0.099684127 | 0.096766613 | 0.37422473 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.10254008 | 0.099983028 | 0.32745195 | 0.10111577 | 0.09810062 | 0.26694564 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.12453635 | 0.10532411 | 0.34348239 | 0.12127936 | 0.10281856 | 0.22117775 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.12623156 | 0.10146817 | 0.32017438 | 0.12059849 | 0.097107435 | 0.1812947 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.107164 | 0.095221227 | 0.31985488 | 0.107164 | 0.095221227 | 0.31985488 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.11558452 | 0.10009322 | 0.33442578 | 0.11346639 | 0.09837234 | 0.26245264 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.1183854 | 0.10020227 | 0.33203818 | 0.11386271 | 0.096633035 | 0.23275829 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.12212011 | 0.10046239 | 0.33224721 | 0.11606443 | 0.090408117 | 0.23771532 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.091197116 | 0.085558965 | 0.18952254 | 0.087427462 | 0.082210009 | 0.14703774 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.10358409 | 0.084225164 | 0.27702294 | 0.098798887 | 0.080353387 | 0.20930975 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.14487366 | 0.082822285 | 0.27795949 | 0.14487366 | 0.082822285 | 0.27795949 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.14854186 | 0.085179323 | 0.28460874 | 0.14671899 | 0.082112906 | 0.20056816 |

#### ROC AUC

Saved field: `roc_auc`. Higher is better.

![ROC AUC across models and splits](evaluation/figures/017_roc_auc.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.70966984 | 0.70945579 | 0.67255582 | 0.70966984 | 0.70945579 | 0.67255582 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.7171023 | 0.71622704 | 0.67279496 | 0.80014863 | 0.79962181 | 0.73462844 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.72140405 | 0.72069937 | 0.67361132 | 0.83529051 | 0.83504762 | 0.76366515 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.72129975 | 0.7203541 | 0.67118633 | 0.85437416 | 0.85398225 | 0.78560702 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.71989656 | 0.71837945 | 0.72217027 | 0.71989656 | 0.71837945 | 0.72217027 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.70103888 | 0.69776046 | 0.82625142 | 0.78776646 | 0.78581328 | 0.84401498 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.69845724 | 0.69303236 | 0.83218727 | 0.82264876 | 0.82002078 | 0.85746526 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.69784055 | 0.69360282 | 0.83056001 | 0.84613296 | 0.84399271 | 0.86457275 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.7421715 | 0.74035686 | 0.83982156 | 0.7421715 | 0.74035686 | 0.83982156 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.69110491 | 0.68585816 | 0.69739232 | 0.76660181 | 0.76189276 | 0.73887697 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.651303 | 0.64485943 | 0.8284306 | 0.79092073 | 0.78647394 | 0.86228174 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.69623124 | 0.69597936 | 0.32354711 | 0.82186295 | 0.82138266 | 0.35457295 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.73018546 | 0.72812391 | 0.81966201 | 0.73018546 | 0.72812391 | 0.81966201 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.72410648 | 0.7205468 | 0.76372284 | 0.79749196 | 0.79574376 | 0.79890593 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.71050132 | 0.708407 | 0.67504755 | 0.82100614 | 0.81909383 | 0.72159113 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.71465159 | 0.7130156 | 0.75667826 | 0.84473804 | 0.84317607 | 0.81062358 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.75214702 | 0.74921052 | 0.79111794 | 0.75214702 | 0.74921052 | 0.79111794 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.74992172 | 0.74568524 | 0.81413578 | 0.82537365 | 0.82267262 | 0.83106578 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.75989296 | 0.75205203 | 0.82213867 | 0.85986518 | 0.85551481 | 0.84842986 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.75585519 | 0.75171867 | 0.82700754 | 0.8604369 | 0.85803296 | 0.84273533 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.757478 | 0.75069377 | 0.82485629 | 0.757478 | 0.75069377 | 0.82485629 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.75514974 | 0.7478238 | 0.82367527 | 0.81952477 | 0.81502699 | 0.83541326 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.7607281 | 0.75412793 | 0.83289949 | 0.85884287 | 0.85627652 | 0.85328317 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.75097608 | 0.74173423 | 0.80665289 | 0.86773379 | 0.86344252 | 0.83388179 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.70232302 | 0.70053701 | 0.533153 | 0.83921073 | 0.83892683 | 0.72345806 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.7159614 | 0.70446645 | 0.79370787 | 0.84435389 | 0.84003145 | 0.80839075 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.77350691 | 0.75677558 | 0.83812718 | 0.77350691 | 0.75677558 | 0.83812718 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.76657957 | 0.75067172 | 0.84051244 | 0.83728096 | 0.82357669 | 0.85324552 |

### Classification scores and confusion counts

#### classification at 0 5 / f1

Saved field: `classification_at_0_5.f1`. Higher is better.

![classification at 0 5 / f1 across models and splits](evaluation/figures/018_classification_at_0_5_f1.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.012449054 | 0.010801392 | 0.099711673 | 0.012435161 | 0.010981435 | 0.083372604 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.015125503 | 0.014129399 | 0.089567845 | 0.015145737 | 0.013532507 | 0.067867333 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.018789428 | 0.017224064 | 0.090892051 | 0.0192534 | 0.017780978 | 0.064990142 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.0014794435 | 0.0019734694 | 0.073020405 | 0.0014794435 | 0.0019734694 | 0.073020405 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.034474475 | 0.029698813 | 0.26934808 | 0.033263398 | 0.028316288 | 0.23596494 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.0058735384 | 0.0071724914 | 0.025936637 | 0.0054081002 | 0.006604079 | 0.020000249 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.020189288 | 0.01804322 | 0.0063870308 | 0.023319443 | 0.019876872 | 0.0052377127 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.0035888755 | 0.0039442175 | 0.05445135 | 0.0035888755 | 0.0039442175 | 0.05445135 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.018489069 | 0.019391339 | 0.012323658 | 0.018266647 | 0.019086918 | 0.010548282 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.027647441 | 0.024891406 | 0.2377984 | 0.029551053 | 0.025720635 | 0.20012436 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.030426755 | 0.025579296 | 0.22802123 | 0.032403503 | 0.027233944 | 0.14995867 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.024158251 | 0.024514871 | 0.21447758 | 0.024158251 | 0.024514871 | 0.21447758 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.02704698 | 0.023262548 | 0.10496204 | 0.029119878 | 0.024425729 | 0.091009527 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.044658882 | 0.040156003 | 0.28730383 | 0.0469582 | 0.042260293 | 0.20839521 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.034501336 | 0.03052153 | 0.16058788 | 0.036413437 | 0.031749925 | 0.10419871 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.016069632 | 0.016646359 | 0.15943617 | 0.016069632 | 0.016646359 | 0.15943617 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.035053378 | 0.032434561 | 0.2604115 | 0.037438291 | 0.034097472 | 0.22412131 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.024009486 | 0.020625878 | 0.18836974 | 0.024721688 | 0.021418626 | 0.14459665 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.036437143 | 0.033923502 | 0.10819743 | 0.037737002 | 0.034464983 | 0.082563403 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.028169891 | 0.027698518 | 0.051949977 | 0.029991534 | 0.029688586 | 0.038626305 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.023693684 | 0.021640489 | 0.1097906 | 0.025151358 | 0.022819473 | 0.08416034 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.061710457 | 0.056737103 | 0.15213549 | 0.061710457 | 0.056737103 | 0.15213549 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.063531099 | 0.056035513 | 0.13796703 | 0.072262493 | 0.063957435 | 0.10461915 |

#### classification at 0 5 / fn

Saved field: `classification_at_0_5.fn`. Descriptive; no universal better direction.

![classification at 0 5 / fn across models and splits](evaluation/figures/019_classification_at_0_5_fn.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 56694 | 14170 | 7378 | 60103 | 15023 | 8815 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 56694 | 14170 | 7378 | 61588 | 15394 | 9621 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 56338 | 14093 | 6948 | 59726 | 14940 | 8383 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 56261 | 14068 | 7001 | 61117 | 15288 | 9243 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 56154 | 14041 | 6989 | 61788 | 15450 | 9722 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 56652 | 14156 | 7088 | 56652 | 14156 | 7088 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 55692 | 13955 | 5738 | 59079 | 14804 | 7078 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 56527 | 14119 | 7280 | 61421 | 15343 | 9523 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 56115 | 14041 | 7354 | 61658 | 15436 | 10086 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 56592 | 14142 | 7162 | 56592 | 14142 | 7162 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 56165 | 14030 | 7332 | 59549 | 14877 | 8768 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 55899 | 13991 | 5969 | 60664 | 15193 | 8160 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 55815 | 13984 | 6040 | 61366 | 15378 | 8625 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 55999 | 13994 | 6381 | 55999 | 13994 | 6381 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 55916 | 14003 | 6925 | 59214 | 14837 | 8340 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 55398 | 13879 | 5637 | 60106 | 15061 | 7643 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 55698 | 13950 | 6575 | 61239 | 15344 | 9298 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 56234 | 14051 | 6631 | 56234 | 14051 | 6631 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 55675 | 13936 | 5897 | 58948 | 14762 | 7190 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 56004 | 14022 | 6445 | 60816 | 15227 | 8674 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 55640 | 13925 | 6907 | 61195 | 15316 | 9626 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 55884 | 13971 | 7169 | 61447 | 15361 | 9904 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 56014 | 14015 | 6885 | 61602 | 15416 | 9620 |
| random_forest K=3 (`rf3_depth8`) | 3 | 54889 | 13727 | 6572 | 54889 | 13727 | 6572 |
| random_forest K=5 (`rf5_depth8`) | 5 | 54834 | 13733 | 6674 | 57850 | 14494 | 8098 |

#### classification at 0 5 / fp

Saved field: `classification_at_0_5.fp`. Descriptive; no universal better direction.

![classification at 0 5 / fp across models and splits](evaluation/figures/020_classification_at_0_5_fp.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 143.0986 | 10.4212 | 816.8678 | 154.5198 | 10.4212 | 1116.1164 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 127.296 | 165.9812 | 663.1996 | 136.7172 | 165.9812 | 1140.3798 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 245.131 | 680.0436 | 792.6044 | 255.5522 | 680.0436 | 1528.5942 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 42.106 | 4.2106 | 274.9852 | 42.106 | 4.2106 | 274.9852 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 433.965 | 93.693 | 3159.5512 | 442.1756 | 226.1294 | 4170.5262 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 4.2106 | 0 | 80.878 | 4.2106 | 0 | 80.878 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 84.1502 | 0 | 113.2292 | 244.587 | 343.1124 | 169.8438 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 46.3166 | 0 | 339.6876 | 46.3166 | 0 | 339.6876 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0 | 129.4364 | 41.3156 | 0 | 129.4364 | 49.4034 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 20.8424 | 33.4742 | 3063.3742 | 23.8424 | 34.4742 | 3518.9208 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 205.0962 | 187.0118 | 3019.7494 | 207.0962 | 195.433 | 8244.4682 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 148.2788 | 12.6318 | 922.0092 | 148.2788 | 12.6318 | 922.0092 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 57.5272 | 20.8424 | 800.6922 | 65.9484 | 20.8424 | 1148.4676 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 49.966 | 32.4742 | 3000.5738 | 49.966 | 32.4742 | 7384.1614 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 46.8954 | 26.053 | 1819.755 | 47.8954 | 26.053 | 4715.1874 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 96.8438 | 8.4212 | 1245.5212 | 96.8438 | 8.4212 | 1245.5212 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 426.9032 | 25.053 | 2515.3058 | 443.535 | 25.053 | 4061.0756 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 93.2826 | 32.9042 | 1595.0498 | 95.2826 | 32.9042 | 2530.5056 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 105.0544 | 29.2636 | 857.3068 | 105.0544 | 372.376 | 1196.9944 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 4.2106 | 0 | 459.2018 | 4.2106 | 0 | 499.6408 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 25.2636 | 0 | 1109.7322 | 25.2636 | 0 | 1109.7322 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0 | 1002.8836 | 2411.8184 | 0 | 1002.8836 | 2411.8184 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0 | 990.2518 | 2123.337 | 0 | 990.2518 | 4174.8596 |

#### classification at 0 5 / mcc

Saved field: `classification_at_0_5.mcc`. Higher is better.

![classification at 0 5 / mcc across models and splits](evaluation/figures/021_classification_at_0_5_mcc.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.065292943 | 0.067996498 | 0.1118886 | 0.065680842 | 0.069325559 | 0.096469287 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.075180237 | 0.049325445 | 0.10901458 | 0.076214092 | 0.05043917 | 0.083812341 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.078855151 | 0.032133017 | 0.10227901 | 0.082116068 | 0.038468016 | 0.074990332 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.018448027 | 0.026961512 | 0.12394381 | 0.018448027 | 0.026961512 | 0.12394381 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.10827386 | 0.10021574 | 0.22157229 | 0.10738827 | 0.082515296 | 0.20404214 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.052841665 | 0.059183639 | 0.075220384 | 0.051084034 | 0.057192118 | 0.070366724 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.092790428 | 0.094133365 | 0.012600411 | 0.093510495 | 0.055531045 | 0.014489608 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.034264576 | 0.043851668 | 0.087020653 | 0.034264576 | 0.043851668 | 0.087020653 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.095299986 | 0.068891561 | 0.050129709 | 0.095205853 | 0.070102691 | 0.046414601 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.11525074 | 0.10125881 | 0.19114494 | 0.12013499 | 0.10467597 | 0.18604174 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.10991755 | 0.0776181 | 0.18193612 | 0.11644377 | 0.084595857 | 0.11959755 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.098588846 | 0.10600254 | 0.2336507 | 0.098588846 | 0.10600254 | 0.2336507 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.11130311 | 0.10064499 | 0.11935524 | 0.11622362 | 0.1044381 | 0.10482475 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.14624266 | 0.133709 | 0.24214451 | 0.15155531 | 0.13934037 | 0.17309478 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.12764133 | 0.11587285 | 0.13910054 | 0.13274729 | 0.12025287 | 0.085284305 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.080301609 | 0.087201515 | 0.1586027 | 0.080301609 | 0.087201515 | 0.1586027 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.10977549 | 0.12015366 | 0.22397191 | 0.11610095 | 0.12465841 | 0.19308733 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.10177827 | 0.090642308 | 0.17559466 | 0.10479761 | 0.094357947 | 0.14188515 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.12794415 | 0.12222349 | 0.11989163 | 0.13228795 | 0.086101948 | 0.10583535 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.11761119 | 0.11692412 | 0.071484358 | 0.12247147 | 0.12211364 | 0.070086458 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.10599127 | 0.10318707 | 0.10877742 | 0.11050769 | 0.10687065 | 0.11071638 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.17609018 | 0.090629958 | 0.1154037 | 0.17609018 | 0.090629958 | 0.1154037 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.1787552 | 0.089976747 | 0.10694153 | 0.19204034 | 0.10637889 | 0.070134331 |

#### classification at 0 5 / precision

Saved field: `classification_at_0_5.precision`. Higher is better.

![classification at 0 5 / precision across models and splits](evaluation/figures/022_classification_at_0_5_precision.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.71328591 | 0.88079322 | 0.34486415 | 0.70928684 | 0.8884493 | 0.27904878 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.7728058 | 0.38062372 | 0.36243044 | 0.77503154 | 0.38973282 | 0.24894957 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.68778331 | 0.15944753 | 0.3292134 | 0.70441091 | 0.17674612 | 0.20368888 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.49936984 | 0.76878302 | 0.51328778 | 0.49936984 | 0.76878302 | 0.51328778 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.6977886 | 0.69648486 | 0.34169862 | 0.69841566 | 0.49199177 | 0.2940317 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.9754069 | 1 | 0.54785943 | 0.9754069 | 1 | 0.54785943 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.87310537 | 1 | 0.17488989 | 0.75133161 | 0.31802039 | 0.13716459 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.68771803 | 1 | 0.38870761 | 0.68771803 | 1 | 0.38870761 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 1 | 0.51960314 | 0.52682453 | 1 | 0.53006792 | 0.48753467 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.97445291 | 0.84245523 | 0.31504519 | 0.97484561 | 0.8535967 | 0.29337816 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.81081365 | 0.49864374 | 0.30703923 | 0.83273012 | 0.52729221 | 0.1528903 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.82416397 | 0.93303462 | 0.51953894 | 0.82416397 | 0.93303462 | 0.51953894 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.93114862 | 0.88904316 | 0.36133271 | 0.93094035 | 0.89923536 | 0.2925836 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.96287722 | 0.89960807 | 0.36717767 | 0.96738439 | 0.91114503 | 0.211276 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.95503346 | 0.89411631 | 0.30616661 | 0.96028229 | 0.90630204 | 0.14737294 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.82608444 | 0.93391053 | 0.37490191 | 0.82608444 | 0.93391053 | 0.37490191 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.70474981 | 0.90329006 | 0.37059226 | 0.72253657 | 0.91241833 | 0.28578586 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.88090812 | 0.81811257 | 0.36905919 | 0.89013662 | 0.83540016 | 0.27232163 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.90936198 | 0.89330119 | 0.35458676 | 0.91962507 | 0.42920034 | 0.28919336 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.99482861 | 1 | 0.31277976 | 0.99558735 | 1 | 0.2949308 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.9641785 | 1 | 0.30759974 | 0.96920063 | 1 | 0.30759974 |
| random_forest K=3 (`rf3_depth8`) | 3 | 1 | 0.30638704 | 0.25048026 | 1 | 0.30638704 | 0.25048026 |
| random_forest K=5 (`rf5_depth8`) | 5 | 1 | 0.30618283 | 0.24899755 | 1 | 0.34819771 | 0.14657003 |

#### classification at 0 5 / recall

Saved field: `classification_at_0_5.recall`. Higher is better.

![classification at 0 5 / recall across models and splits](evaluation/figures/023_classification_at_0_5_recall.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.0062793241 | 0.0054340155 | 0.058281377 | 0.0062725654 | 0.0055248619 | 0.049007374 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.0076374925 | 0.0071983063 | 0.051097858 | 0.0076475937 | 0.0068857997 | 0.039289055 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.0095248174 | 0.0091037403 | 0.052724316 | 0.0097600846 | 0.0093613747 | 0.038663107 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.00074081913 | 0.00098800282 | 0.039306045 | 0.00074081913 | 0.00098800282 | 0.039306045 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.017673828 | 0.0151729 | 0.22228246 | 0.017037419 | 0.014577648 | 0.19705048 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.002945638 | 0.0035991531 | 0.013282732 | 0.0027115672 | 0.0033129791 | 0.010186051 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.010212721 | 0.0091037403 | 0.0032529141 | 0.011843518 | 0.010259041 | 0.0026698309 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.0017991322 | 0.0019760056 | 0.029276227 | 0.0017991322 | 0.0019760056 | 0.029276227 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.0093307934 | 0.0098800282 | 0.006234752 | 0.0092175099 | 0.0097184317 | 0.0053318208 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.014022648 | 0.012632322 | 0.19097316 | 0.015002923 | 0.013057035 | 0.15185532 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.015504286 | 0.013126323 | 0.18134996 | 0.01652323 | 0.013977943 | 0.14713735 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.012258793 | 0.012420607 | 0.13513147 | 0.012258793 | 0.012420607 | 0.13513147 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.013722793 | 0.011785462 | 0.061398753 | 0.014791275 | 0.012381016 | 0.053885423 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.022859562 | 0.020536344 | 0.23597181 | 0.024063129 | 0.021631805 | 0.20559193 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.017567997 | 0.015525759 | 0.10883708 | 0.018558585 | 0.016157989 | 0.08058934 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.0081137334 | 0.008398024 | 0.10124695 | 0.0081137334 | 0.008398024 | 0.10124695 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.017973683 | 0.016513761 | 0.20073191 | 0.019217011 | 0.017373361 | 0.18434487 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.0121706 | 0.010444601 | 0.12645703 | 0.012534909 | 0.010848382 | 0.098430517 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.018591033 | 0.017290049 | 0.063838439 | 0.019263747 | 0.017953321 | 0.048155839 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.014287226 | 0.014043754 | 0.02832746 | 0.015225091 | 0.015067966 | 0.020666469 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.011994215 | 0.010938603 | 0.066820276 | 0.012740997 | 0.011541421 | 0.048749135 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.031837584 | 0.031263232 | 0.1092437 | 0.031837584 | 0.031263232 | 0.1092437 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.032807705 | 0.030839802 | 0.095418813 | 0.03748565 | 0.035212674 | 0.081338627 |

#### classification at 0 5 / tn

Saved field: `classification_at_0_5.tn`. Descriptive; no universal better direction.

![classification at 0 5 / tn across models and splits](evaluation/figures/024_classification_at_0_5_tn.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 2050997.9 | 512749.17 | 77755.324 | 2050997.9 | 512749.17 | 77755.324 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 2050997.9 | 512749.17 | 77755.324 | 3519674.7 | 880255.94 | 147003.94 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 2050997.9 | 512749.17 | 77755.324 | 4772564.6 | 1193747.9 | 212570.12 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 2050997.9 | 512749.17 | 77755.324 | 5861964.3 | 1466211.7 | 277302 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 2050997.9 | 512749.17 | 77755.324 | 2050997.9 | 512749.17 | 77755.324 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 2050854.8 | 512738.75 | 76938.456 | 3519520.1 | 880245.52 | 145887.82 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 2050870.6 | 512583.19 | 77092.124 | 4772427.9 | 1193582 | 211429.74 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 2050752.8 | 512069.12 | 76962.719 | 5861708.7 | 1465531.7 | 275773.41 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 2050955.8 | 512744.96 | 77480.338 | 2050955.8 | 512744.96 | 77480.338 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 2050564 | 512655.48 | 74595.772 | 3519232.5 | 880029.81 | 142833.41 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 2050993.7 | 512749.17 | 77674.446 | 4772560.4 | 1193747.9 | 212489.24 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 2050913.8 | 512749.17 | 77642.094 | 5861719.7 | 1465868.6 | 277132.16 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 2050951.6 | 512749.17 | 77415.636 | 2050951.6 | 512749.17 | 77415.636 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 2050997.9 | 512619.73 | 77714.008 | 3519674.7 | 880126.5 | 146954.54 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 2050977.1 | 512715.69 | 74691.949 | 4772540.8 | 1193713.5 | 209051.2 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 2050792.8 | 512562.16 | 74735.574 | 5861757.2 | 1466016.3 | 269057.53 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 2050849.7 | 512736.54 | 76833.314 | 2050849.7 | 512736.54 | 76833.314 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 2050940.4 | 512728.33 | 76954.631 | 3519608.7 | 880235.1 | 145855.47 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 2050948 | 512716.69 | 74754.75 | 4772514.7 | 1193715.5 | 205185.96 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 2050951 | 512723.12 | 75935.569 | 5861916.4 | 1466185.7 | 272586.81 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 2050901.1 | 512740.75 | 76509.802 | 2050901.1 | 512740.75 | 76509.802 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 2050571 | 512724.12 | 75240.018 | 3519231.1 | 880230.89 | 142942.86 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 2050904.6 | 512716.26 | 76160.274 | 4772469.4 | 1193715 | 210039.62 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 2050892.9 | 512719.9 | 76898.017 | 5861859.2 | 1465839.3 | 276105.01 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 2050993.7 | 512749.17 | 77296.122 | 5861960.1 | 1466211.7 | 276802.36 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 2050972.7 | 512749.17 | 76645.591 | 5861939 | 1466211.7 | 276192.27 |
| random_forest K=3 (`rf3_depth8`) | 3 | 2050997.9 | 511746.28 | 75343.505 | 2050997.9 | 511746.28 | 75343.505 |
| random_forest K=5 (`rf5_depth8`) | 5 | 2050997.9 | 511758.92 | 75631.987 | 3519674.7 | 879265.69 | 142829.08 |

#### classification at 0 5 / tp

Saved field: `classification_at_0_5.tp`. Descriptive; no universal better direction.

![classification at 0 5 / tp across models and splits](evaluation/figures/025_classification_at_0_5_tp.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 356 | 77 | 430 | 377 | 83 | 432 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 433 | 102 | 377 | 471 | 106 | 378 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 540 | 129 | 389 | 609 | 146 | 391 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 42 | 14 | 290 | 42 | 14 | 290 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 1002 | 215 | 1640 | 1024 | 219 | 1737 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 167 | 51 | 98 | 167 | 51 | 98 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 579 | 129 | 24 | 739 | 160 | 27 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 102 | 28 | 216 | 102 | 28 | 216 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 529 | 140 | 46 | 554 | 146 | 47 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 795 | 179 | 1409 | 924 | 201 | 1461 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 879 | 186 | 1338 | 1031 | 218 | 1488 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 695 | 176 | 997 | 695 | 176 | 997 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 778 | 167 | 453 | 889 | 186 | 475 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 1296 | 291 | 1741 | 1482 | 333 | 1978 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 996 | 220 | 803 | 1158 | 252 | 815 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 460 | 119 | 747 | 460 | 119 | 747 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 1019 | 234 | 1481 | 1155 | 261 | 1625 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 690 | 148 | 933 | 772 | 167 | 947 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 1054 | 245 | 471 | 1202 | 280 | 487 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 810 | 199 | 209 | 950 | 235 | 209 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 680 | 155 | 493 | 795 | 180 | 493 |
| random_forest K=3 (`rf3_depth8`) | 3 | 1805 | 443 | 806 | 1805 | 443 | 806 |
| random_forest K=5 (`rf5_depth8`) | 5 | 1860 | 437 | 704 | 2253 | 529 | 717 |

#### classification at validation f1 threshold / f1

Saved field: `classification_at_validation_f1_threshold.f1`. Higher is better.

![classification at validation f1 threshold / f1 across models and splits](evaluation/figures/026_classification_at_validation_f1_threshold_f1.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.11481346 | 0.11832882 | 0.14581688 | 0.11481346 | 0.11832882 | 0.14581688 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.12595063 | 0.12533394 | 0.12613023 | 0.12388382 | 0.12328726 | 0.11165437 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.12632399 | 0.12596869 | 0.12663594 | 0.1233942 | 0.12307074 | 0.10535234 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.12691397 | 0.12638304 | 0.12673292 | 0.12351276 | 0.12302271 | 0.10169752 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.11740726 | 0.12581786 | 0.17231038 | 0.11740726 | 0.12581786 | 0.17231038 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.11195748 | 0.11681302 | 0.43695481 | 0.1099026 | 0.11426567 | 0.37784053 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.12402444 | 0.1201435 | 0.43964409 | 0.1204743 | 0.11633781 | 0.34937138 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.12070304 | 0.11786021 | 0.42981568 | 0.11465769 | 0.11212241 | 0.32196245 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.14079978 | 0.14038037 | 0.45395786 | 0.14079978 | 0.14038037 | 0.45395786 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.13081396 | 0.12704966 | 0.32174767 | 0.12878535 | 0.1248201 | 0.28816833 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.1126552 | 0.10821338 | 0.45644694 | 0.109401 | 0.10526156 | 0.36966272 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.13247229 | 0.12796613 | 0.10451186 | 0.12993664 | 0.12455885 | 0.08312902 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.13493858 | 0.13853761 | 0.42459558 | 0.13493858 | 0.13853761 | 0.42459558 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.12755784 | 0.13172624 | 0.33124207 | 0.1264122 | 0.13066521 | 0.30125851 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.13018149 | 0.12965355 | 0.30875251 | 0.12837368 | 0.12742712 | 0.26967846 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.14204159 | 0.13982805 | 0.31106114 | 0.13887267 | 0.13655719 | 0.20879752 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.14714761 | 0.1446712 | 0.46811865 | 0.14714761 | 0.1446712 | 0.46811865 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.14842897 | 0.1464134 | 0.44834023 | 0.1464889 | 0.14422714 | 0.39733564 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.15385128 | 0.14656603 | 0.44980578 | 0.15201422 | 0.14466982 | 0.33593451 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.16145168 | 0.15705073 | 0.46184137 | 0.15780517 | 0.15343646 | 0.32826263 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.14971815 | 0.14399963 | 0.44408365 | 0.14971815 | 0.14399963 | 0.44408365 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.15378361 | 0.14459647 | 0.45437783 | 0.15230662 | 0.14326369 | 0.39565701 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.15291133 | 0.14591231 | 0.4619235 | 0.15052944 | 0.14372408 | 0.37157204 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.15279838 | 0.14329392 | 0.45088842 | 0.14915118 | 0.13926233 | 0.37903764 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.12739608 | 0.12156263 | 0.27767659 | 0.12374814 | 0.11932325 | 0.22279981 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.14018372 | 0.11889909 | 0.4278091 | 0.1364401 | 0.11616167 | 0.35192817 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.15388355 | 0.13488608 | 0.39668961 | 0.15388355 | 0.13488608 | 0.39668961 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.15825919 | 0.13367074 | 0.40590527 | 0.14878759 | 0.12246431 | 0.31364283 |

#### classification at validation f1 threshold / fn

Saved field: `classification_at_validation_f1_threshold.fn`. Descriptive; no universal better direction.

![classification at validation f1 threshold / fn across models and splits](evaluation/figures/027_classification_at_validation_f1_threshold_fn.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 38699 | 9661 | 6313 | 38699 | 9661 | 6313 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 43826 | 10950 | 6679 | 47235 | 11803 | 8116 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 43675 | 10896 | 6675 | 48569 | 12120 | 8918 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 43552 | 10871 | 6674 | 49255 | 12297 | 9409 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 44057 | 11026 | 6430 | 44057 | 11026 | 6430 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 44523 | 11099 | 2623 | 47803 | 11924 | 3637 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 45266 | 11308 | 2786 | 49948 | 12485 | 4462 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 43854 | 10995 | 2674 | 48482 | 12149 | 4693 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 42634 | 10605 | 2976 | 42634 | 10605 | 2976 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 43904 | 10971 | 4627 | 47287 | 11818 | 5930 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 47255 | 11789 | 3513 | 51837 | 12928 | 5403 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 44706 | 11159 | 6820 | 50247 | 12553 | 9552 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 45323 | 11297 | 3569 | 45323 | 11297 | 3569 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 38550 | 9578 | 4553 | 41876 | 10408 | 5976 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 43287 | 10817 | 4802 | 48044 | 12019 | 6963 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 45674 | 11417 | 5121 | 51209 | 12807 | 7617 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 46211 | 11531 | 3963 | 46211 | 11531 | 3963 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 46290 | 11543 | 3985 | 49573 | 12371 | 5379 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 41989 | 10542 | 3275 | 46669 | 11721 | 5177 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 44850 | 11124 | 3532 | 50354 | 12507 | 6227 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 41396 | 10340 | 3017 | 41396 | 10340 | 3017 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 43230 | 10751 | 3255 | 46492 | 11571 | 4395 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 42176 | 10541 | 2739 | 46909 | 11728 | 4739 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 44920 | 11255 | 3649 | 49954 | 12521 | 6306 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 43997 | 11027 | 5314 | 44156 | 11086 | 7410 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 47913 | 12006 | 3325 | 53435 | 13392 | 5726 |
| random_forest K=3 (`rf3_depth8`) | 3 | 36348 | 9068 | 1807 | 36348 | 9068 | 1807 |
| random_forest K=5 (`rf5_depth8`) | 5 | 38444 | 9606 | 1863 | 40318 | 10064 | 2131 |

#### classification at validation f1 threshold / fp

Saved field: `classification_at_validation_f1_threshold.fp`. Descriptive; no universal better direction.

![classification at validation f1 threshold / fp across models and splits](evaluation/figures/028_classification_at_validation_f1_threshold_fp.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 238776 | 57532.357 | 6164.3622 | 238776 | 57532.357 | 6164.3622 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 134772.03 | 33992.73 | 3006.7818 | 134772.03 | 33992.73 | 3006.7818 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 136407.78 | 34537.171 | 3021.6934 | 136407.78 | 34537.171 | 3021.6934 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 137264.92 | 34737.373 | 3027.9784 | 137264.92 | 34737.373 | 3027.9784 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 145936.77 | 32663.008 | 2677.3996 | 145936.77 | 32663.008 | 2677.3996 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 148556.83 | 35338.754 | 9631.2644 | 151431.56 | 36120.013 | 13415.388 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 116164.27 | 30611.028 | 8919.6248 | 120008.23 | 31706.538 | 14753.043 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 143219.54 | 36532.384 | 9806.4522 | 166410.49 | 42443.369 | 18135.523 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 128962.22 | 33055.578 | 7613.8706 | 128962.22 | 33055.578 | 7613.8706 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 126060.88 | 32989.263 | 6971.3568 | 126109.85 | 33125.91 | 8323.0194 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 101440.27 | 27454.648 | 5692.1558 | 106922.62 | 28994.71 | 8981.8026 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 112306.79 | 29878.326 | 2742.2136 | 112467.23 | 30221.438 | 2823.0916 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 100470.94 | 24433.103 | 6754.779 | 100470.94 | 24433.103 | 6754.779 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 209644.7 | 50958.355 | 6854.0122 | 210044.06 | 51000.541 | 7193.6006 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 135872.99 | 34199.454 | 6732.5042 | 135876.99 | 34202.454 | 7433.3642 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 87451.825 | 22453.934 | 4876.6168 | 87541.015 | 22462.356 | 11299.33 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 75305.772 | 19673.729 | 3797.318 | 75305.772 | 19673.729 | 3797.318 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 73090.267 | 19087.693 | 4364.8266 | 73132.162 | 19100.325 | 5044.2018 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 119759.64 | 31708.696 | 6762.4294 | 119777.27 | 31710.696 | 12392.538 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 78180.822 | 21574.014 | 5431.0692 | 78191.244 | 21579.225 | 9677.1642 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 132365.32 | 35194.58 | 7901.4438 | 132365.32 | 35194.58 | 7901.4438 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 104945.19 | 29701.226 | 6646.8926 | 105017.56 | 29715.858 | 9107.5838 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 118675.82 | 31943.206 | 8068.577 | 118764.61 | 31954.417 | 11774.543 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 85643.577 | 23600.607 | 5433.6776 | 92010.848 | 25490.26 | 6167.715 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 129940.1 | 34396.97 | 5424.2152 | 214170.47 | 55486.981 | 11447.934 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 59803.457 | 20066.615 | 7516.7034 | 60010 | 20147.112 | 10431.224 |
| random_forest K=3 (`rf3_depth8`) | 3 | 187393.72 | 56377.024 | 15138.451 | 187393.72 | 56377.024 | 15138.451 |
| random_forest K=5 (`rf5_depth8`) | 5 | 155690.31 | 49553.196 | 14280.828 | 186061.6 | 61004.859 | 27122.73 |

#### classification at validation f1 threshold / mcc

Saved field: `classification_at_validation_f1_threshold.mcc`. Higher is better.

![classification at validation f1 threshold / mcc across models and splits](evaluation/figures/029_classification_at_validation_f1_threshold_mcc.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.099414719 | 0.10339571 | 0.065671866 | 0.099414719 | 0.10339571 | 0.065671866 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.10222296 | 0.10162554 | 0.077312498 | 0.11359358 | 0.11308387 | 0.089216756 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.10283252 | 0.10260286 | 0.077606869 | 0.11845689 | 0.11836033 | 0.093304305 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.10362343 | 0.10318099 | 0.077609734 | 0.12149137 | 0.12120948 | 0.095526434 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.093074109 | 0.10167219 | 0.13105245 | 0.093074109 | 0.10167219 | 0.13105245 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.086710309 | 0.091975094 | 0.39086319 | 0.099398114 | 0.10371088 | 0.35358279 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.098326377 | 0.094363116 | 0.39088201 | 0.11290279 | 0.10918823 | 0.3326419 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.096791411 | 0.093651376 | 0.38267134 | 0.11565177 | 0.11314628 | 0.3160705 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.1190854 | 0.11903259 | 0.40299632 | 0.1190854 | 0.11903259 | 0.40299632 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.10704582 | 0.10325019 | 0.25051651 | 0.11801526 | 0.11438032 | 0.2420156 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.084812397 | 0.080132982 | 0.40162039 | 0.099328673 | 0.095711582 | 0.34110403 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.10761472 | 0.10312762 | 0.058827811 | 0.12487446 | 0.12021262 | 0.077364152 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.10940353 | 0.11318935 | 0.36643612 | 0.10940353 | 0.11318935 | 0.36643612 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.11350393 | 0.11835386 | 0.26123159 | 0.12808713 | 0.13264169 | 0.25708678 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.10735977 | 0.10684819 | 0.2367107 | 0.12405499 | 0.12313606 | 0.23587206 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.11632585 | 0.11406823 | 0.2469348 | 0.13107849 | 0.12892517 | 0.17761441 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.1213304 | 0.1187854 | 0.41830889 | 0.1213304 | 0.1187854 | 0.41830889 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.12265669 | 0.12057965 | 0.39470273 | 0.13132538 | 0.12916624 | 0.36201393 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.13305157 | 0.12559158 | 0.39556225 | 0.14796725 | 0.14104239 | 0.31041451 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.13665145 | 0.13251708 | 0.40759134 | 0.14976106 | 0.14623682 | 0.30356503 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.13012697 | 0.12456737 | 0.39218239 | 0.13012697 | 0.12456737 | 0.39218239 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.13090735 | 0.12221311 | 0.40060937 | 0.14113378 | 0.13330581 | 0.36057775 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.1317999 | 0.12495576 | 0.41448567 | 0.14611804 | 0.14015026 | 0.34938441 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.12785027 | 0.11816821 | 0.39539221 | 0.14250842 | 0.13343206 | 0.35656221 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.10344246 | 0.097302312 | 0.20858735 | 0.13450807 | 0.13012741 | 0.19245728 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.11464179 | 0.09140252 | 0.37163644 | 0.12694551 | 0.10681528 | 0.33010491 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.14519611 | 0.12602771 | 0.36746542 | 0.14519611 | 0.12602771 | 0.36746542 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.14463561 | 0.12013626 | 0.37550319 | 0.15250154 | 0.12822168 | 0.32158426 |

#### classification at validation f1 threshold / precision

Saved field: `classification_at_validation_f1_threshold.precision`. Higher is better.

![classification at validation f1 threshold / precision across models and splits](evaluation/figures/030_classification_at_validation_f1_threshold_precision.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.070081902 | 0.072677327 | 0.1473159 | 0.070081902 | 0.072677327 | 0.1473159 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.087157937 | 0.086529529 | 0.18862417 | 0.087157937 | 0.086529529 | 0.18862417 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.087126284 | 0.086588168 | 0.18874037 | 0.087126284 | 0.086588168 | 0.18874037 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.087376296 | 0.086732771 | 0.18863989 | 0.087376296 | 0.086732771 | 0.18863989 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.079691615 | 0.087804041 | 0.26148842 | 0.079691615 | 0.087804041 | 0.26148842 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.075724286 | 0.07995365 | 0.33052361 | 0.075122962 | 0.079017797 | 0.27848609 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.089566557 | 0.085501677 | 0.3398555 | 0.088417441 | 0.084037406 | 0.25908943 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.082276291 | 0.079959939 | 0.32418011 | 0.077166017 | 0.075113799 | 0.23009466 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.098306401 | 0.097349637 | 0.36634882 | 0.098306401 | 0.097349637 | 0.36634882 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.092113207 | 0.088398827 | 0.28295608 | 0.092250652 | 0.088216893 | 0.25740498 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.085128625 | 0.079803863 | 0.40440902 | 0.083575021 | 0.078383482 | 0.31955023 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.096448126 | 0.091549459 | 0.16907997 | 0.097498555 | 0.091479074 | 0.16577565 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.10167027 | 0.10521457 | 0.36057172 | 0.10167027 | 0.10521457 | 0.36057172 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.079652764 | 0.082663738 | 0.29186863 | 0.079848053 | 0.082980404 | 0.28297748 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.089811099 | 0.089288439 | 0.27673619 | 0.090643222 | 0.089814493 | 0.26339353 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.11191018 | 0.10921598 | 0.3163893 | 0.11332028 | 0.11044952 | 0.18093079 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.12219548 | 0.1182733 | 0.47349548 | 0.12219548 | 0.1182733 | 0.47349548 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.12460736 | 0.12097799 | 0.43736476 | 0.12586335 | 0.121918 | 0.40517904 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.10935961 | 0.10266948 | 0.37761968 | 0.11076031 | 0.10380487 | 0.26394975 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.13156371 | 0.12372048 | 0.41457058 | 0.13346374 | 0.12522182 | 0.28651131 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.10360054 | 0.098143272 | 0.35563873 | 0.10360054 | 0.098143272 | 0.35563873 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.11370739 | 0.10322997 | 0.38282647 | 0.11473629 | 0.10407666 | 0.3267398 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.10899905 | 0.10201785 | 0.36505779 | 0.11000152 | 0.1029185 | 0.29309804 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.12086115 | 0.10993525 | 0.4069771 | 0.11912438 | 0.10764824 | 0.38166504 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.089016114 | 0.083724095 | 0.2756331 | 0.078485799 | 0.075170449 | 0.19101212 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.12803192 | 0.097343236 | 0.35031149 | 0.12993679 | 0.098608068 | 0.29605438 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.097939864 | 0.082987655 | 0.26900761 | 0.097939864 | 0.082987655 | 0.26900761 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.10492105 | 0.084335486 | 0.27859405 | 0.096115262 | 0.07517753 | 0.19771211 |

#### classification at validation f1 threshold / recall

Saved field: `classification_at_validation_f1_threshold.recall`. Higher is better.

![classification at validation f1 threshold / recall across models and splits](evaluation/figures/031_classification_at_validation_f1_threshold_recall.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.31740572 | 0.31820748 | 0.14434806 | 0.31740572 | 0.31820748 | 0.14434806 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.22697287 | 0.22724065 | 0.094741122 | 0.21409913 | 0.21433802 | 0.079296653 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.22963629 | 0.23105152 | 0.095283275 | 0.21138858 | 0.21268027 | 0.073069328 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.23180583 | 0.23281581 | 0.095418813 | 0.2106191 | 0.2115286 | 0.069613369 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.22289837 | 0.22187721 | 0.12849011 | 0.22289837 | 0.22187721 | 0.12849011 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.2146788 | 0.21672548 | 0.6444836 | 0.20464869 | 0.2062837 | 0.58740783 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.20157336 | 0.20197601 | 0.62239089 | 0.18899786 | 0.18896973 | 0.53622285 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.22647899 | 0.22406493 | 0.63757116 | 0.22300752 | 0.22101821 | 0.53594383 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.24799802 | 0.25158786 | 0.59663866 | 0.24799802 | 0.25158786 | 0.59663866 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.22559706 | 0.22575865 | 0.37286528 | 0.21323395 | 0.21333955 | 0.32728304 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.16649028 | 0.16803105 | 0.5238547 | 0.1583263 | 0.16019228 | 0.43841597 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.21145095 | 0.21249118 | 0.075630252 | 0.1947209 | 0.19511413 | 0.055473153 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.20056796 | 0.20275229 | 0.51626457 | 0.20056796 | 0.20275229 | 0.51626457 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.32003387 | 0.32406493 | 0.38289509 | 0.30326273 | 0.30719563 | 0.32206466 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.23648005 | 0.23662668 | 0.34914611 | 0.21991297 | 0.21924126 | 0.27627066 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.19437683 | 0.1942837 | 0.30590946 | 0.17930349 | 0.1788279 | 0.24681104 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.18490493 | 0.18623853 | 0.46286256 | 0.18490493 | 0.18623853 | 0.46286256 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.18351148 | 0.18539167 | 0.45988073 | 0.17519924 | 0.17652932 | 0.38979013 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.25937489 | 0.25603387 | 0.55611277 | 0.24223875 | 0.23859945 | 0.46190625 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.208911 | 0.21496119 | 0.52127948 | 0.19300607 | 0.19806361 | 0.38425789 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.26983455 | 0.27028934 | 0.59108159 | 0.26983455 | 0.27028934 | 0.59108159 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.23748545 | 0.2412844 | 0.55882353 | 0.22646124 | 0.229781 | 0.50141804 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.25607648 | 0.25610445 | 0.62876118 | 0.23834188 | 0.23814473 | 0.50743166 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.2076763 | 0.2057163 | 0.50542152 | 0.19941664 | 0.19716594 | 0.37644616 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.22395668 | 0.22180663 | 0.27975061 | 0.29233777 | 0.28917671 | 0.26727974 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.15488411 | 0.15271701 | 0.54933586 | 0.1436287 | 0.14131829 | 0.43379808 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.35887395 | 0.36005646 | 0.75508268 | 0.35887395 | 0.36005646 | 0.75508268 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.32190355 | 0.32208892 | 0.74749255 | 0.3291849 | 0.33009386 | 0.75825298 |

#### classification at validation f1 threshold / tn

Saved field: `classification_at_validation_f1_threshold.tn`. Descriptive; no universal better direction.

![classification at validation f1 threshold / tn across models and splits](evaluation/figures/032_classification_at_validation_f1_threshold_tn.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 1812221.9 | 455216.81 | 71590.961 | 1812221.9 | 455216.81 | 71590.961 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 1916225.9 | 478756.44 | 74748.542 | 3384902.6 | 846263.21 | 143997.16 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 1914590.2 | 478212 | 74733.63 | 4636156.9 | 1159210.8 | 209548.43 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 1913733 | 478011.8 | 74727.345 | 5724699.4 | 1431474.3 | 274274.02 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 1905061.2 | 480086.16 | 75077.924 | 1905061.2 | 480086.16 | 75077.924 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 1902441.1 | 477410.41 | 68124.059 | 3368243.1 | 844135.93 | 133588.55 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 1934833.7 | 482138.14 | 68835.699 | 4652556.4 | 1162041.4 | 197817.08 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 1907778.4 | 476216.78 | 67948.871 | 5695553.8 | 1423768.3 | 259166.48 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 1922035.7 | 479693.59 | 70141.453 | 1922035.7 | 479693.59 | 70141.453 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 1924937 | 479759.91 | 70783.967 | 3393564.8 | 847130.03 | 138680.92 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 1949557.7 | 485294.52 | 72063.168 | 4665642 | 1164753.2 | 203588.32 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 1938691.1 | 482870.84 | 75013.11 | 5749497.1 | 1435990.3 | 274478.91 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 1950527 | 488316.07 | 71000.545 | 1950527 | 488316.07 | 71000.545 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 1841353.2 | 461790.81 | 70901.311 | 3309630.6 | 829255.4 | 139810.34 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 1915124.9 | 478549.71 | 71022.819 | 4636687.7 | 1159545.5 | 205136.76 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 1963546.1 | 490295.23 | 72878.707 | 5774423.3 | 1443749.4 | 266002.67 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 1975692.2 | 493075.44 | 73958.006 | 1975692.2 | 493075.44 | 73958.006 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 1977907.7 | 493661.47 | 73390.497 | 3446542.5 | 861155.61 | 141959.74 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 1931238.3 | 481040.47 | 70992.894 | 4652787.4 | 1162037.2 | 200177.58 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 1972817.1 | 491175.15 | 72324.254 | 5783773 | 1444632.5 | 267624.84 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 1918632.6 | 477554.59 | 69853.88 | 1918632.6 | 477554.59 | 69853.88 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 1946052.7 | 483047.94 | 71108.431 | 3414657.1 | 850540.08 | 137896.36 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 1932322.1 | 480805.96 | 69686.747 | 4653800 | 1161793.5 | 200795.58 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 1965354.4 | 489148.56 | 72321.646 | 5769953.4 | 1440721.4 | 271134.28 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 1921057.8 | 478352.2 | 72331.108 | 5647793.8 | 1410724.7 | 265854.07 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 1991194.5 | 492682.55 | 70238.62 | 5801954.3 | 1446064.6 | 266870.78 |
| random_forest K=3 (`rf3_depth8`) | 3 | 1863604.2 | 456372.14 | 62616.873 | 1863604.2 | 456372.14 | 62616.873 |
| random_forest K=5 (`rf5_depth8`) | 5 | 1895307.6 | 463195.97 | 63474.495 | 3333613.1 | 819251.08 | 119881.21 |

#### classification at validation f1 threshold / tp

Saved field: `classification_at_validation_f1_threshold.tp`. Descriptive; no universal better direction.

![classification at validation f1 threshold / tp across models and splits](evaluation/figures/033_classification_at_validation_f1_threshold_tp.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 17995 | 4509 | 1065 | 17995 | 4509 | 1065 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 12868 | 3220 | 699 | 12868 | 3220 | 699 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 13019 | 3274 | 703 | 13019 | 3274 | 703 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 13142 | 3299 | 704 | 13142 | 3299 | 704 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 12637 | 3144 | 948 | 12637 | 3144 | 948 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 12171 | 3071 | 4755 | 12300 | 3099 | 5178 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 11428 | 2862 | 4592 | 11640 | 2909 | 5159 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 12840 | 3175 | 4704 | 13915 | 3447 | 5420 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 14060 | 3565 | 4402 | 14060 | 3565 | 4402 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 12790 | 3199 | 2751 | 12816 | 3205 | 2885 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 9439 | 2381 | 3865 | 9751 | 2466 | 4218 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 11988 | 3011 | 558 | 12150 | 3043 | 561 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 11371 | 2873 | 3809 | 11371 | 2873 | 3809 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 18144 | 4592 | 2825 | 18227 | 4615 | 2839 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 13407 | 3353 | 2576 | 13544 | 3375 | 2658 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 11020 | 2753 | 2257 | 11188 | 2789 | 2496 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 10483 | 2639 | 3415 | 10483 | 2639 | 3415 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 10404 | 2627 | 3393 | 10530 | 2652 | 3436 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 14705 | 3628 | 4103 | 14919 | 3673 | 4444 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 11844 | 3046 | 3846 | 12043 | 3089 | 3886 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 15298 | 3830 | 4361 | 15298 | 3830 | 4361 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 13464 | 3419 | 4123 | 13611 | 3452 | 4420 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 14518 | 3629 | 4639 | 14679 | 3666 | 4882 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 11774 | 2915 | 3729 | 12443 | 3075 | 3807 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 12697 | 3143 | 2064 | 18241 | 4510 | 2703 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 8781 | 2164 | 4053 | 8962 | 2204 | 4387 |
| random_forest K=3 (`rf3_depth8`) | 3 | 20346 | 5102 | 5571 | 20346 | 5102 | 5571 |
| random_forest K=5 (`rf5_depth8`) | 5 | 18250 | 4564 | 5515 | 19785 | 4959 | 6684 |

#### classification at validation mcc threshold / f1

Saved field: `classification_at_validation_mcc_threshold.f1`. Higher is better.

![classification at validation mcc threshold / f1 across models and splits](evaluation/figures/034_classification_at_validation_mcc_threshold_f1.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.10510681 | 0.1036199 | 0.24393364 | 0.10510681 | 0.1036199 | 0.24393364 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.10275087 | 0.10075578 | 0.2392225 | 0.10228842 | 0.10030928 | 0.22946477 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.10284348 | 0.10073596 | 0.23926803 | 0.10205455 | 0.10008465 | 0.22438169 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.10269698 | 0.10073362 | 0.23932014 | 0.10192682 | 0.099989796 | 0.22139851 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.10835103 | 0.10614869 | 0.27524846 | 0.10835103 | 0.10614869 | 0.27524846 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.094753187 | 0.096154909 | 0.34843603 | 0.086825162 | 0.086923802 | 0.28140637 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.095028323 | 0.094060292 | 0.35398266 | 0.077778875 | 0.078581139 | 0.24933769 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.11691128 | 0.11564405 | 0.42227805 | 0.072845974 | 0.074947603 | 0.22798674 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.11573367 | 0.11521179 | 0.38242765 | 0.11573367 | 0.11521179 | 0.38242765 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.10290052 | 0.10064072 | 0.26172099 | 0.10157525 | 0.099742492 | 0.24967217 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.11063405 | 0.10762511 | 0.46129238 | 0.082014251 | 0.082202624 | 0.33089552 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.10733203 | 0.1061858 | 0.12525724 | 0.10661598 | 0.10511905 | 0.1140127 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.12489406 | 0.12306784 | 0.40626474 | 0.12489406 | 0.12306784 | 0.40626474 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.12249941 | 0.12470073 | 0.33905869 | 0.10957439 | 0.1111071 | 0.30705589 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.10262351 | 0.10105559 | 0.24920365 | 0.10230211 | 0.10062559 | 0.23453842 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.11778588 | 0.11535587 | 0.32751663 | 0.11637531 | 0.11424499 | 0.2531407 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.11563509 | 0.11444886 | 0.35589057 | 0.11563509 | 0.11444886 | 0.35589057 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.12776003 | 0.12818052 | 0.40640364 | 0.11599695 | 0.11269484 | 0.34985429 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.047889921 | 0.042709476 | 0.29648672 | 0.11023512 | 0.10730804 | 0.28289862 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.12565629 | 0.1255083 | 0.42528988 | 0.12327447 | 0.12299225 | 0.3237055 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.11383588 | 0.11099396 | 0.3499039 | 0.11383588 | 0.11099396 | 0.3499039 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.1243985 | 0.12295423 | 0.38930255 | 0.1095324 | 0.10775628 | 0.31256072 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.12212244 | 0.11935069 | 0.38846513 | 0.107907 | 0.10656489 | 0.29982239 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.046170952 | 0.043208086 | 0.136522 | 0.10239466 | 0.10009548 | 0.28151287 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.028307032 | 0.028521739 | 0.052192055 | 0.092216139 | 0.093957147 | 0.19245817 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.03803056 | 0.034477857 | 0.20466984 | 0.087787594 | 0.087698345 | 0.2700266 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.11476221 | 0.11068148 | 0.32031136 | 0.11476221 | 0.11068148 | 0.32031136 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.11215676 | 0.10741637 | 0.31510897 | 0.10812799 | 0.10117512 | 0.26329339 |

#### classification at validation mcc threshold / fn

Saved field: `classification_at_validation_mcc_threshold.fn`. Descriptive; no universal better direction.

![classification at validation mcc threshold / fn across models and splits](evaluation/figures/035_classification_at_validation_mcc_threshold_fn.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 23902 | 5957 | 4138 | 23902 | 5957 | 4138 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 17955 | 4516 | 3336 | 21364 | 5369 | 4773 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 17964 | 4518 | 3336 | 22833 | 5740 | 5578 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 17938 | 4515 | 3335 | 23641 | 5941 | 6070 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 25333 | 6345 | 3922 | 25333 | 6345 | 3922 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 24431 | 6112 | 1623 | 21563 | 5412 | 2118 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 24194 | 6133 | 1523 | 18900 | 4766 | 2106 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 40349 | 10113 | 2390 | 16600 | 4126 | 2279 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 24926 | 6210 | 1961 | 24926 | 6210 | 1961 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 21381 | 5343 | 2898 | 24469 | 6114 | 4102 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 43546 | 10879 | 2993 | 34231 | 8494 | 3358 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 20955 | 5287 | 5775 | 26333 | 6636 | 8468 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 32958 | 8372 | 2670 | 32958 | 8372 | 2670 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 33640 | 8307 | 3969 | 29251 | 7254 | 4496 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 18187 | 4572 | 2669 | 22944 | 5774 | 4821 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 24266 | 6110 | 3207 | 29532 | 7434 | 5605 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 20609 | 5120 | 2359 | 20609 | 5120 | 2359 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 30594 | 7717 | 2789 | 26080 | 6573 | 3555 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 55301 | 13860 | 5559 | 23134 | 5833 | 3519 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 25451 | 6404 | 2356 | 30145 | 7594 | 4957 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 19097 | 4804 | 1878 | 19097 | 4804 | 1878 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 26694 | 6705 | 2155 | 21574 | 5384 | 2690 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 23180 | 5835 | 1948 | 21742 | 5471 | 3523 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 55349 | 13856 | 6764 | 21107 | 5284 | 4309 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 55880 | 13965 | 7168 | 23984 | 5954 | 6300 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 55587 | 13921 | 6281 | 22011 | 5510 | 4068 |
| random_forest K=3 (`rf3_depth8`) | 3 | 16660 | 4198 | 1056 | 16660 | 4198 | 1056 |
| random_forest K=5 (`rf5_depth8`) | 5 | 17642 | 4399 | 964 | 19174 | 4775 | 1188 |

#### classification at validation mcc threshold / fp

Saved field: `classification_at_validation_mcc_threshold.fp`. Descriptive; no universal better direction.

![classification at validation mcc threshold / fp across models and splits](evaluation/figures/036_classification_at_validation_mcc_threshold_fp.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 534488.79 | 136138.68 | 15946.602 | 534488.79 | 136138.68 | 15946.602 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 658604.42 | 167807.68 | 22372.808 | 658604.42 | 167807.68 | 22372.808 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 657759.35 | 167807.68 | 22366.377 | 659152.76 | 167868.71 | 22372.808 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 659314.15 | 167868.71 | 22366.377 | 659314.15 | 167868.71 | 22366.377 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 490822.76 | 125439.7 | 14277.857 | 490822.76 | 125439.7 | 14277.857 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 592033.29 | 145376.55 | 19900.323 | 789118.08 | 196502.21 | 32084.647 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 594812.6 | 148683.39 | 19847.716 | 993399.94 | 244475.48 | 43143.695 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 206574.74 | 51936.573 | 11258.245 | 1149171.3 | 279014.5 | 50776.295 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 460522.56 | 116050.3 | 15534.541 | 460522.56 | 116050.3 | 15534.541 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 594345.25 | 152419.07 | 22376.931 | 605890.63 | 154708.01 | 24225.506 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 167842.51 | 43695.732 | 7248.8032 | 578182.96 | 145583.85 | 21970.849 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 573519.18 | 144257.51 | 16614.327 | 578060.49 | 145917.38 | 17098.435 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 299668.15 | 74256.456 | 11091.005 | 299668.15 | 74256.456 | 11091.005 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 296645.64 | 74000.129 | 9321.6132 | 472169.31 | 117055.04 | 14997.687 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 655250.82 | 166186.85 | 25705.385 | 655255.82 | 166189.85 | 26510.46 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 461504.28 | 117511.48 | 13921.462 | 469548.53 | 119127.92 | 20995.556 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 531339.51 | 134929.24 | 15808.299 | 531339.51 | 134929.24 | 15808.299 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 325784.48 | 80063.123 | 10616.459 | 492492.89 | 126489.5 | 15994.662 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 88.0808 | 36.6848 | 3073.364 | 597630.37 | 153242.27 | 27416.129 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 409340.15 | 101816.78 | 11216.833 | 428606.12 | 106524.02 | 16587.116 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 566256.43 | 145229.95 | 18559.203 | 566256.43 | 145229.95 | 18559.203 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 395626.94 | 99792.297 | 14231.601 | 604885.84 | 154241.73 | 24252.385 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 458650.99 | 117167.42 | 15148.177 | 637090.82 | 160916.95 | 24958.415 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 222.7406 | 50.3166 | 1002.8872 | 702800.34 | 180135.27 | 25317.349 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 4.2106 | 0 | 459.2018 | 732297.97 | 180004.5 | 25698.194 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 415.3402 | 25.053 | 2244.7036 | 817301.45 | 204333.74 | 28615.367 |
| random_forest K=3 (`rf3_depth8`) | 3 | 600958.12 | 156050.75 | 25774.092 | 600958.12 | 156050.75 | 25774.092 |
| random_forest K=5 (`rf5_depth8`) | 5 | 600636.47 | 157986.57 | 26917.727 | 656015.29 | 177308.45 | 41493.37 |

#### classification at validation mcc threshold / mcc

Saved field: `classification_at_validation_mcc_threshold.mcc`. Higher is better.

![classification at validation mcc threshold / mcc across models and splits](evaluation/figures/037_classification_at_validation_mcc_threshold_mcc.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.11592928 | 0.11392968 | 0.15760115 | 0.11592928 | 0.11392968 | 0.15760115 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.12453627 | 0.12117849 | 0.15819132 | 0.1483932 | 0.14562715 | 0.1886202 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.12466201 | 0.12113052 | 0.15825222 | 0.15672394 | 0.15411042 | 0.19807509 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.12448764 | 0.1211515 | 0.15833301 | 0.16105457 | 0.15856912 | 0.20355126 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.11762023 | 0.1144676 | 0.19730389 | 0.11762023 | 0.1144676 | 0.19730389 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.099364357 | 0.10153164 | 0.32134419 | 0.12708904 | 0.12708762 | 0.28931792 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.10022583 | 0.098099772 | 0.32989656 | 0.13254487 | 0.13343558 | 0.28047578 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.098682669 | 0.097119801 | 0.38037066 | 0.13684932 | 0.14013407 | 0.27050785 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.12840684 | 0.12790716 | 0.34906403 | 0.12840684 | 0.12790716 | 0.34906403 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.11773724 | 0.11432304 | 0.19338715 | 0.14094839 | 0.13868552 | 0.21972519 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.086662359 | 0.083459095 | 0.4104528 | 0.10945071 | 0.11018736 | 0.3346551 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.12518012 | 0.12310951 | 0.002464878 | 0.16054031 | 0.15844115 | 0.07537213 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.12235123 | 0.1191359 | 0.35856329 | 0.12235123 | 0.1191359 | 0.35856329 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.11816961 | 0.12154782 | 0.26994074 | 0.14018146 | 0.14245393 | 0.2719579 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.12385332 | 0.12119266 | 0.18063041 | 0.1567845 | 0.15447576 | 0.21889364 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.132522 | 0.12895408 | 0.26566011 | 0.16365179 | 0.16100035 | 0.23977194 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.1376663 | 0.13632031 | 0.31215599 | 0.1376663 | 0.13632031 | 0.31215599 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.13080818 | 0.13067833 | 0.35657574 | 0.15458831 | 0.15034529 | 0.3284125 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.14974942 | 0.1375657 | 0.25025595 | 0.16560574 | 0.16183056 | 0.28733203 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.13985594 | 0.13930175 | 0.38411831 | 0.16913737 | 0.16830559 | 0.31355756 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.13850723 | 0.13420441 | 0.3166489 | 0.13850723 | 0.13420441 | 0.3166489 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.13551663 | 0.13346504 | 0.35170207 | 0.15699965 | 0.15491499 | 0.3089878 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.1405445 | 0.13660344 | 0.3556197 | 0.16595013 | 0.16408808 | 0.30311664 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.14014081 | 0.13577144 | 0.14494466 | 0.16691085 | 0.16415289 | 0.28616731 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.11790292 | 0.11867438 | 0.071863149 | 0.14890706 | 0.15135227 | 0.17261311 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.11636744 | 0.12433155 | 0.17358514 | 0.14732812 | 0.14716994 | 0.27981021 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.14529318 | 0.13908148 | 0.30500274 | 0.14529318 | 0.13908148 | 0.30500274 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.13933668 | 0.13245738 | 0.30155418 | 0.1604874 | 0.15173392 | 0.28987538 |

#### classification at validation mcc threshold / precision

Saved field: `classification_at_validation_mcc_threshold.precision`. Higher is better.

![classification at validation mcc threshold / precision across models and splits](evaluation/figures/038_classification_at_validation_mcc_threshold_precision.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.057805589 | 0.056895772 | 0.16886784 | 0.057805589 | 0.056895772 | 0.16886784 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.055552256 | 0.054400476 | 0.15302023 | 0.055552256 | 0.054400476 | 0.15302023 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.055607454 | 0.054389818 | 0.15305749 | 0.055530261 | 0.054381776 | 0.15305229 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.055518776 | 0.054387103 | 0.15308956 | 0.055518776 | 0.054387103 | 0.15308956 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.060057402 | 0.058717727 | 0.19488146 | 0.060057402 | 0.058717727 | 0.19488146 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.051678988 | 0.052517507 | 0.22431992 | 0.046565123 | 0.046629714 | 0.17268477 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.051808301 | 0.051282414 | 0.22779693 | 0.041201136 | 0.041661525 | 0.14834571 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.073322353 | 0.072454745 | 0.3070248 | 0.038324866 | 0.039485755 | 0.13366252 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.064530995 | 0.064188216 | 0.258549 | 0.064530995 | 0.064188216 | 0.258549 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.056082804 | 0.054742421 | 0.16680983 | 0.055545802 | 0.054450328 | 0.16286259 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.072644693 | 0.070041049 | 0.37691887 | 0.045177861 | 0.045250693 | 0.22182594 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.058659861 | 0.058005553 | 0.087993152 | 0.05872425 | 0.057852218 | 0.087764062 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.073394235 | 0.0724257 | 0.29799345 | 0.073394235 | 0.0724257 | 0.29799345 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.072111435 | 0.073413101 | 0.26777972 | 0.061333386 | 0.062239611 | 0.22358907 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.05550496 | 0.054600837 | 0.15482805 | 0.055691037 | 0.054718208 | 0.1533034 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.065652724 | 0.064186548 | 0.230538 | 0.065414241 | 0.06412134 | 0.17675966 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.063594362 | 0.062856285 | 0.2409818 | 0.063594362 | 0.062856285 | 0.2409818 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.074172068 | 0.074587253 | 0.30179951 | 0.064619132 | 0.062620655 | 0.24747512 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.94052938 | 0.894184 | 0.3718039 | 0.060454245 | 0.058727323 | 0.18205074 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.070912834 | 0.070868801 | 0.30925868 | 0.069982493 | 0.069870586 | 0.23713252 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.062261797 | 0.060583736 | 0.22860275 | 0.062261797 | 0.060583736 | 0.22860275 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.07048426 | 0.069598994 | 0.2684712 | 0.05988205 | 0.058817166 | 0.20163026 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.068095051 | 0.066413061 | 0.26387177 | 0.058862214 | 0.058083602 | 0.19635235 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.85792254 | 0.86188771 | 0.37974201 | 0.055490574 | 0.054146221 | 0.18649577 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.99485389 | 1 | 0.31380669 | 0.049840993 | 0.050841961 | 0.12920521 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.72716992 | 0.90858338 | 0.32827567 | 0.047087083 | 0.047038579 | 0.17440669 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.062456306 | 0.060064058 | 0.19697102 | 0.062456306 | 0.060064058 | 0.19697102 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.061048466 | 0.058244764 | 0.19242927 | 0.058726358 | 0.054639549 | 0.15527163 |

#### classification at validation mcc threshold / recall

Saved field: `classification_at_validation_mcc_threshold.recall`. Higher is better.

![classification at validation mcc threshold / recall across models and splits](evaluation/figures/039_classification_at_validation_mcc_threshold_recall.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.57840336 | 0.5796048 | 0.4391434 | 0.57840336 | 0.5796048 | 0.4391434 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.68329982 | 0.68129852 | 0.54784494 | 0.64454353 | 0.64261466 | 0.45853659 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.68314107 | 0.68115737 | 0.54784494 | 0.62926219 | 0.62712745 | 0.42022659 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.68359968 | 0.68136909 | 0.54798048 | 0.62111961 | 0.61906899 | 0.39978246 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.55316259 | 0.55222301 | 0.46841963 | 0.55316259 | 0.55222301 | 0.46841963 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.56907256 | 0.5686662 | 0.78002169 | 0.64123255 | 0.63975238 | 0.75972774 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.5732529 | 0.56718419 | 0.79357549 | 0.69312204 | 0.69039886 | 0.78110384 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.28830211 | 0.2863091 | 0.67606397 | 0.73396157 | 0.73544499 | 0.77464649 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.56034148 | 0.56175018 | 0.73420981 | 0.56034148 | 0.56175018 | 0.73420981 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.62287014 | 0.62293578 | 0.60721063 | 0.59288222 | 0.59302403 | 0.53465683 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.23191167 | 0.23225124 | 0.59433451 | 0.44419367 | 0.44822658 | 0.65097183 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.63038417 | 0.62688779 | 0.21726755 | 0.57797651 | 0.57450628 | 0.16266192 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.41866864 | 0.40917431 | 0.63811331 | 0.41866864 | 0.40917431 | 0.63811331 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.40663915 | 0.41376147 | 0.46204934 | 0.5133188 | 0.51714038 | 0.48996029 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.67920768 | 0.67734651 | 0.63824885 | 0.62745989 | 0.6249188 | 0.49890864 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.57198293 | 0.56880734 | 0.56532936 | 0.52670801 | 0.52333932 | 0.44576288 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.63648711 | 0.63867325 | 0.68026565 | 0.63648711 | 0.63867325 | 0.68026565 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.46036618 | 0.45539873 | 0.62198428 | 0.56607823 | 0.56247088 | 0.59671015 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.024570501 | 0.021877205 | 0.24654378 | 0.62437488 | 0.62108614 | 0.63423761 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.55108124 | 0.54805928 | 0.68067227 | 0.51688382 | 0.51308028 | 0.50983882 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.6631566 | 0.66097389 | 0.74545947 | 0.6631566 | 0.66097389 | 0.74545947 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.52915652 | 0.52681722 | 0.70791542 | 0.64104953 | 0.64161619 | 0.69483834 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.59113839 | 0.58821454 | 0.73597181 | 0.64697668 | 0.64460179 | 0.63382185 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.023723851 | 0.022159492 | 0.083220385 | 0.66173053 | 0.66119518 | 0.57391476 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.01435778 | 0.014467184 | 0.028462998 | 0.61562255 | 0.61823544 | 0.37703945 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.019525876 | 0.017572336 | 0.14868528 | 0.64724266 | 0.64670428 | 0.59774548 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.70614174 | 0.7037403 | 0.85687178 | 0.70614174 | 0.7037403 | 0.85687178 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.68882069 | 0.6895554 | 0.86934128 | 0.68098098 | 0.68215403 | 0.86522972 |

#### classification at validation mcc threshold / tn

Saved field: `classification_at_validation_mcc_threshold.tn`. Descriptive; no universal better direction.

![classification at validation mcc threshold / tn across models and splits](evaluation/figures/040_classification_at_validation_mcc_threshold_tn.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 1516509.1 | 376610.49 | 61808.722 | 1516509.1 | 376610.49 | 61808.722 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 1392393.5 | 344941.48 | 55382.515 | 2861070.2 | 712448.26 | 124631.13 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 1393238.6 | 344941.48 | 55388.946 | 4113411.9 | 1025879.2 | 190197.31 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 1391683.8 | 344880.46 | 55388.946 | 5202650.1 | 1298343 | 254935.62 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 1560175.2 | 387309.47 | 63477.466 | 1560175.2 | 387309.47 | 63477.466 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 1458964.6 | 367372.62 | 57855.001 | 2730556.6 | 683753.73 | 114919.29 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 1456185.3 | 364065.78 | 57907.607 | 3779164.7 | 949272.46 | 169426.43 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 1844423.2 | 460812.6 | 66497.079 | 4712793 | 1187197.2 | 226525.7 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 1590475.4 | 396698.87 | 62220.782 | 1590475.4 | 396698.87 | 62220.782 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 1456652.7 | 360330.1 | 55378.393 | 2913784 | 725547.93 | 122778.43 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 1883155.4 | 469053.44 | 70506.52 | 4194381.7 | 1048164.1 | 190599.27 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 1477478.7 | 368491.66 | 61140.997 | 5283903.8 | 1320294.3 | 260203.56 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 1751329.8 | 438492.71 | 66664.318 | 1751329.8 | 438492.71 | 66664.318 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 1754352.3 | 438749.04 | 68433.71 | 3047505.4 | 763200.9 | 132006.25 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 1395747.1 | 346562.32 | 52049.939 | 4117308.8 | 1027558.1 | 186059.66 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 1589493.6 | 395237.69 | 63833.861 | 5392415.8 | 1347083.8 | 256306.44 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 1519658.4 | 377819.93 | 61947.025 | 1519658.4 | 377819.93 | 61947.025 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 1725213.4 | 432686.05 | 67138.865 | 3027181.8 | 753766.44 | 131009.28 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 2050909.8 | 512712.48 | 74681.96 | 4174934.3 | 1040505.7 | 185153.99 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 1641657.8 | 410932.39 | 66538.491 | 5433358.2 | 1359687.7 | 260714.88 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 1484741.5 | 367519.22 | 59196.12 | 1484741.5 | 367519.22 | 59196.12 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 1655371 | 412956.87 | 63523.723 | 2914788.8 | 726014.21 | 122751.55 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 1592346.9 | 395581.75 | 62607.146 | 4135473.8 | 1032831 | 187611.71 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 2050775.2 | 512698.85 | 76752.436 | 5159164 | 1286076.4 | 251984.65 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 2050993.7 | 512749.17 | 77296.122 | 5129666.3 | 1286207.2 | 251603.81 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 2050582.6 | 512724.12 | 75510.62 | 5044662.8 | 1261878 | 248686.63 |
| random_forest K=3 (`rf3_depth8`) | 3 | 1450039.8 | 356698.42 | 51981.232 | 1450039.8 | 356698.42 | 51981.232 |
| random_forest K=5 (`rf5_depth8`) | 5 | 1450361.5 | 354762.6 | 50837.597 | 2863659.4 | 702947.49 | 105510.57 |

#### classification at validation mcc threshold / tp

Saved field: `classification_at_validation_mcc_threshold.tp`. Descriptive; no universal better direction.

![classification at validation mcc threshold / tp across models and splits](evaluation/figures/041_classification_at_validation_mcc_threshold_tp.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 32792 | 8213 | 3240 | 32792 | 8213 | 3240 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 38739 | 9654 | 4042 | 38739 | 9654 | 4042 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 38730 | 9652 | 4042 | 38755 | 9654 | 4043 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 38756 | 9655 | 4043 | 38756 | 9655 | 4043 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 31361 | 7825 | 3456 | 31361 | 7825 | 3456 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 32263 | 8058 | 5755 | 38540 | 9611 | 6697 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 32500 | 8037 | 5855 | 42688 | 10628 | 7515 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 16345 | 4057 | 4988 | 45797 | 11470 | 7834 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 31768 | 7960 | 5417 | 31768 | 7960 | 5417 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 35313 | 8827 | 4480 | 35634 | 8909 | 4713 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 13148 | 3291 | 4385 | 27357 | 6900 | 6263 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 35739 | 8883 | 1603 | 36064 | 8960 | 1645 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 23736 | 5798 | 4708 | 23736 | 5798 | 4708 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 23054 | 5863 | 3409 | 30852 | 7769 | 4319 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 38507 | 9598 | 4709 | 38644 | 9620 | 4800 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 32428 | 8060 | 4171 | 32865 | 8162 | 4508 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 36085 | 9050 | 5019 | 36085 | 9050 | 5019 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 26100 | 6453 | 4589 | 34023 | 8450 | 5260 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 1393 | 310 | 1819 | 38454 | 9561 | 6102 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 31243 | 7766 | 5022 | 32252 | 8002 | 5156 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 37597 | 9366 | 5500 | 37597 | 9366 | 5500 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 30000 | 7465 | 5223 | 38529 | 9639 | 6125 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 33514 | 8335 | 5430 | 39846 | 9923 | 6098 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 1345 | 314 | 614 | 41290 | 10312 | 5804 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 814 | 205 | 210 | 38413 | 9642 | 3813 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 1107 | 249 | 1097 | 40386 | 10086 | 6045 |
| random_forest K=3 (`rf3_depth8`) | 3 | 40034 | 9972 | 6322 | 40034 | 9972 | 6322 |
| random_forest K=5 (`rf5_depth8`) | 5 | 39052 | 9771 | 6414 | 40929 | 10248 | 7627 |

#### f1 at 0 5

Saved field: `f1_at_0_5`. Higher is better.

![f1 at 0 5 across models and splits](evaluation/figures/042_f1_at_0_5.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.012449054 | 0.010801392 | 0.099711673 | 0.012435161 | 0.010981435 | 0.083372604 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.015125503 | 0.014129399 | 0.089567845 | 0.015145737 | 0.013532507 | 0.067867333 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.018789428 | 0.017224064 | 0.090892051 | 0.0192534 | 0.017780978 | 0.064990142 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.0014794435 | 0.0019734694 | 0.073020405 | 0.0014794435 | 0.0019734694 | 0.073020405 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.034474475 | 0.029698813 | 0.26934808 | 0.033263398 | 0.028316288 | 0.23596494 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.0058735384 | 0.0071724914 | 0.025936637 | 0.0054081002 | 0.006604079 | 0.020000249 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.020189288 | 0.01804322 | 0.0063870308 | 0.023319443 | 0.019876872 | 0.0052377127 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.0035888755 | 0.0039442175 | 0.05445135 | 0.0035888755 | 0.0039442175 | 0.05445135 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.018489069 | 0.019391339 | 0.012323658 | 0.018266647 | 0.019086918 | 0.010548282 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.027647441 | 0.024891406 | 0.2377984 | 0.029551053 | 0.025720635 | 0.20012436 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.030426755 | 0.025579296 | 0.22802123 | 0.032403503 | 0.027233944 | 0.14995867 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.024158251 | 0.024514871 | 0.21447758 | 0.024158251 | 0.024514871 | 0.21447758 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.02704698 | 0.023262548 | 0.10496204 | 0.029119878 | 0.024425729 | 0.091009527 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.044658882 | 0.040156003 | 0.28730383 | 0.0469582 | 0.042260293 | 0.20839521 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.034501336 | 0.03052153 | 0.16058788 | 0.036413437 | 0.031749925 | 0.10419871 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.016069632 | 0.016646359 | 0.15943617 | 0.016069632 | 0.016646359 | 0.15943617 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.035053378 | 0.032434561 | 0.2604115 | 0.037438291 | 0.034097472 | 0.22412131 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.024009486 | 0.020625878 | 0.18836974 | 0.024721688 | 0.021418626 | 0.14459665 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.036437143 | 0.033923502 | 0.10819743 | 0.037737002 | 0.034464983 | 0.082563403 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.028169891 | 0.027698518 | 0.051949977 | 0.029991534 | 0.029688586 | 0.038626305 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.023693684 | 0.021640489 | 0.1097906 | 0.025151358 | 0.022819473 | 0.08416034 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.061710457 | 0.056737103 | 0.15213549 | 0.061710457 | 0.056737103 | 0.15213549 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.063531099 | 0.056035513 | 0.13796703 | 0.072262493 | 0.063957435 | 0.10461915 |

#### f1 at validation f1 threshold

Saved field: `f1_at_validation_f1_threshold`. Higher is better.

![f1 at validation f1 threshold across models and splits](evaluation/figures/043_f1_at_validation_f1_threshold.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.11481346 | 0.11832882 | 0.14581688 | 0.11481346 | 0.11832882 | 0.14581688 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.12595063 | 0.12533394 | 0.12613023 | 0.12388382 | 0.12328726 | 0.11165437 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.12632399 | 0.12596869 | 0.12663594 | 0.1233942 | 0.12307074 | 0.10535234 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.12691397 | 0.12638304 | 0.12673292 | 0.12351276 | 0.12302271 | 0.10169752 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.11740726 | 0.12581786 | 0.17231038 | 0.11740726 | 0.12581786 | 0.17231038 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.11195748 | 0.11681302 | 0.43695481 | 0.1099026 | 0.11426567 | 0.37784053 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.12402444 | 0.1201435 | 0.43964409 | 0.1204743 | 0.11633781 | 0.34937138 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.12070304 | 0.11786021 | 0.42981568 | 0.11465769 | 0.11212241 | 0.32196245 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.14079978 | 0.14038037 | 0.45395786 | 0.14079978 | 0.14038037 | 0.45395786 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.13081396 | 0.12704966 | 0.32174767 | 0.12878535 | 0.1248201 | 0.28816833 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.1126552 | 0.10821338 | 0.45644694 | 0.109401 | 0.10526156 | 0.36966272 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.13247229 | 0.12796613 | 0.10451186 | 0.12993664 | 0.12455885 | 0.08312902 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.13493858 | 0.13853761 | 0.42459558 | 0.13493858 | 0.13853761 | 0.42459558 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.12755784 | 0.13172624 | 0.33124207 | 0.1264122 | 0.13066521 | 0.30125851 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.13018149 | 0.12965355 | 0.30875251 | 0.12837368 | 0.12742712 | 0.26967846 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.14204159 | 0.13982805 | 0.31106114 | 0.13887267 | 0.13655719 | 0.20879752 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.14714761 | 0.1446712 | 0.46811865 | 0.14714761 | 0.1446712 | 0.46811865 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.14842897 | 0.1464134 | 0.44834023 | 0.1464889 | 0.14422714 | 0.39733564 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.15385128 | 0.14656603 | 0.44980578 | 0.15201422 | 0.14466982 | 0.33593451 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.16145168 | 0.15705073 | 0.46184137 | 0.15780517 | 0.15343646 | 0.32826263 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.14971815 | 0.14399963 | 0.44408365 | 0.14971815 | 0.14399963 | 0.44408365 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.15378361 | 0.14459647 | 0.45437783 | 0.15230662 | 0.14326369 | 0.39565701 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.15291133 | 0.14591231 | 0.4619235 | 0.15052944 | 0.14372408 | 0.37157204 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.15279838 | 0.14329392 | 0.45088842 | 0.14915118 | 0.13926233 | 0.37903764 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.12739608 | 0.12156263 | 0.27767659 | 0.12374814 | 0.11932325 | 0.22279981 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.14018372 | 0.11889909 | 0.4278091 | 0.1364401 | 0.11616167 | 0.35192817 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.15388355 | 0.13488608 | 0.39668961 | 0.15388355 | 0.13488608 | 0.39668961 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.15825919 | 0.13367074 | 0.40590527 | 0.14878759 | 0.12246431 | 0.31364283 |

#### f1 at validation mcc threshold

Saved field: `f1_at_validation_mcc_threshold`. Higher is better.

![f1 at validation mcc threshold across models and splits](evaluation/figures/044_f1_at_validation_mcc_threshold.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.10510681 | 0.1036199 | 0.24393364 | 0.10510681 | 0.1036199 | 0.24393364 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.10275087 | 0.10075578 | 0.2392225 | 0.10228842 | 0.10030928 | 0.22946477 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.10284348 | 0.10073596 | 0.23926803 | 0.10205455 | 0.10008465 | 0.22438169 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.10269698 | 0.10073362 | 0.23932014 | 0.10192682 | 0.099989796 | 0.22139851 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.10835103 | 0.10614869 | 0.27524846 | 0.10835103 | 0.10614869 | 0.27524846 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.094753187 | 0.096154909 | 0.34843603 | 0.086825162 | 0.086923802 | 0.28140637 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.095028323 | 0.094060292 | 0.35398266 | 0.077778875 | 0.078581139 | 0.24933769 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.11691128 | 0.11564405 | 0.42227805 | 0.072845974 | 0.074947603 | 0.22798674 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.11573367 | 0.11521179 | 0.38242765 | 0.11573367 | 0.11521179 | 0.38242765 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.10290052 | 0.10064072 | 0.26172099 | 0.10157525 | 0.099742492 | 0.24967217 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.11063405 | 0.10762511 | 0.46129238 | 0.082014251 | 0.082202624 | 0.33089552 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.10733203 | 0.1061858 | 0.12525724 | 0.10661598 | 0.10511905 | 0.1140127 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.12489406 | 0.12306784 | 0.40626474 | 0.12489406 | 0.12306784 | 0.40626474 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.12249941 | 0.12470073 | 0.33905869 | 0.10957439 | 0.1111071 | 0.30705589 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.10262351 | 0.10105559 | 0.24920365 | 0.10230211 | 0.10062559 | 0.23453842 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.11778588 | 0.11535587 | 0.32751663 | 0.11637531 | 0.11424499 | 0.2531407 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.11563509 | 0.11444886 | 0.35589057 | 0.11563509 | 0.11444886 | 0.35589057 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.12776003 | 0.12818052 | 0.40640364 | 0.11599695 | 0.11269484 | 0.34985429 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.047889921 | 0.042709476 | 0.29648672 | 0.11023512 | 0.10730804 | 0.28289862 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.12565629 | 0.1255083 | 0.42528988 | 0.12327447 | 0.12299225 | 0.3237055 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.11383588 | 0.11099396 | 0.3499039 | 0.11383588 | 0.11099396 | 0.3499039 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.1243985 | 0.12295423 | 0.38930255 | 0.1095324 | 0.10775628 | 0.31256072 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.12212244 | 0.11935069 | 0.38846513 | 0.107907 | 0.10656489 | 0.29982239 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.046170952 | 0.043208086 | 0.136522 | 0.10239466 | 0.10009548 | 0.28151287 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.028307032 | 0.028521739 | 0.052192055 | 0.092216139 | 0.093957147 | 0.19245817 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.03803056 | 0.034477857 | 0.20466984 | 0.087787594 | 0.087698345 | 0.2700266 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.11476221 | 0.11068148 | 0.32031136 | 0.11476221 | 0.11068148 | 0.32031136 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.11215676 | 0.10741637 | 0.31510897 | 0.10812799 | 0.10117512 | 0.26329339 |

#### mcc at 0 5

Saved field: `mcc_at_0_5`. Higher is better.

![mcc at 0 5 across models and splits](evaluation/figures/045_mcc_at_0_5.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.065292943 | 0.067996498 | 0.1118886 | 0.065680842 | 0.069325559 | 0.096469287 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.075180237 | 0.049325445 | 0.10901458 | 0.076214092 | 0.05043917 | 0.083812341 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.078855151 | 0.032133017 | 0.10227901 | 0.082116068 | 0.038468016 | 0.074990332 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.018448027 | 0.026961512 | 0.12394381 | 0.018448027 | 0.026961512 | 0.12394381 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.10827386 | 0.10021574 | 0.22157229 | 0.10738827 | 0.082515296 | 0.20404214 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.052841665 | 0.059183639 | 0.075220384 | 0.051084034 | 0.057192118 | 0.070366724 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.092790428 | 0.094133365 | 0.012600411 | 0.093510495 | 0.055531045 | 0.014489608 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.034264576 | 0.043851668 | 0.087020653 | 0.034264576 | 0.043851668 | 0.087020653 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.095299986 | 0.068891561 | 0.050129709 | 0.095205853 | 0.070102691 | 0.046414601 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.11525074 | 0.10125881 | 0.19114494 | 0.12013499 | 0.10467597 | 0.18604174 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.10991755 | 0.0776181 | 0.18193612 | 0.11644377 | 0.084595857 | 0.11959755 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.098588846 | 0.10600254 | 0.2336507 | 0.098588846 | 0.10600254 | 0.2336507 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.11130311 | 0.10064499 | 0.11935524 | 0.11622362 | 0.1044381 | 0.10482475 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.14624266 | 0.133709 | 0.24214451 | 0.15155531 | 0.13934037 | 0.17309478 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.12764133 | 0.11587285 | 0.13910054 | 0.13274729 | 0.12025287 | 0.085284305 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.080301609 | 0.087201515 | 0.1586027 | 0.080301609 | 0.087201515 | 0.1586027 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.10977549 | 0.12015366 | 0.22397191 | 0.11610095 | 0.12465841 | 0.19308733 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.10177827 | 0.090642308 | 0.17559466 | 0.10479761 | 0.094357947 | 0.14188515 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.12794415 | 0.12222349 | 0.11989163 | 0.13228795 | 0.086101948 | 0.10583535 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.11761119 | 0.11692412 | 0.071484358 | 0.12247147 | 0.12211364 | 0.070086458 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.10599127 | 0.10318707 | 0.10877742 | 0.11050769 | 0.10687065 | 0.11071638 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.17609018 | 0.090629958 | 0.1154037 | 0.17609018 | 0.090629958 | 0.1154037 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.1787552 | 0.089976747 | 0.10694153 | 0.19204034 | 0.10637889 | 0.070134331 |

#### mcc at validation f1 threshold

Saved field: `mcc_at_validation_f1_threshold`. Higher is better.

![mcc at validation f1 threshold across models and splits](evaluation/figures/046_mcc_at_validation_f1_threshold.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.099414719 | 0.10339571 | 0.065671866 | 0.099414719 | 0.10339571 | 0.065671866 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.10222296 | 0.10162554 | 0.077312498 | 0.11359358 | 0.11308387 | 0.089216756 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.10283252 | 0.10260286 | 0.077606869 | 0.11845689 | 0.11836033 | 0.093304305 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.10362343 | 0.10318099 | 0.077609734 | 0.12149137 | 0.12120948 | 0.095526434 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.093074109 | 0.10167219 | 0.13105245 | 0.093074109 | 0.10167219 | 0.13105245 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.086710309 | 0.091975094 | 0.39086319 | 0.099398114 | 0.10371088 | 0.35358279 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.098326377 | 0.094363116 | 0.39088201 | 0.11290279 | 0.10918823 | 0.3326419 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.096791411 | 0.093651376 | 0.38267134 | 0.11565177 | 0.11314628 | 0.3160705 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.1190854 | 0.11903259 | 0.40299632 | 0.1190854 | 0.11903259 | 0.40299632 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.10704582 | 0.10325019 | 0.25051651 | 0.11801526 | 0.11438032 | 0.2420156 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.084812397 | 0.080132982 | 0.40162039 | 0.099328673 | 0.095711582 | 0.34110403 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.10761472 | 0.10312762 | 0.058827811 | 0.12487446 | 0.12021262 | 0.077364152 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.10940353 | 0.11318935 | 0.36643612 | 0.10940353 | 0.11318935 | 0.36643612 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.11350393 | 0.11835386 | 0.26123159 | 0.12808713 | 0.13264169 | 0.25708678 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.10735977 | 0.10684819 | 0.2367107 | 0.12405499 | 0.12313606 | 0.23587206 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.11632585 | 0.11406823 | 0.2469348 | 0.13107849 | 0.12892517 | 0.17761441 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.1213304 | 0.1187854 | 0.41830889 | 0.1213304 | 0.1187854 | 0.41830889 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.12265669 | 0.12057965 | 0.39470273 | 0.13132538 | 0.12916624 | 0.36201393 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.13305157 | 0.12559158 | 0.39556225 | 0.14796725 | 0.14104239 | 0.31041451 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.13665145 | 0.13251708 | 0.40759134 | 0.14976106 | 0.14623682 | 0.30356503 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.13012697 | 0.12456737 | 0.39218239 | 0.13012697 | 0.12456737 | 0.39218239 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.13090735 | 0.12221311 | 0.40060937 | 0.14113378 | 0.13330581 | 0.36057775 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.1317999 | 0.12495576 | 0.41448567 | 0.14611804 | 0.14015026 | 0.34938441 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.12785027 | 0.11816821 | 0.39539221 | 0.14250842 | 0.13343206 | 0.35656221 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.10344246 | 0.097302312 | 0.20858735 | 0.13450807 | 0.13012741 | 0.19245728 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.11464179 | 0.09140252 | 0.37163644 | 0.12694551 | 0.10681528 | 0.33010491 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.14519611 | 0.12602771 | 0.36746542 | 0.14519611 | 0.12602771 | 0.36746542 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.14463561 | 0.12013626 | 0.37550319 | 0.15250154 | 0.12822168 | 0.32158426 |

#### mcc at validation mcc threshold

Saved field: `mcc_at_validation_mcc_threshold`. Higher is better.

![mcc at validation mcc threshold across models and splits](evaluation/figures/047_mcc_at_validation_mcc_threshold.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.11592928 | 0.11392968 | 0.15760115 | 0.11592928 | 0.11392968 | 0.15760115 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.12453627 | 0.12117849 | 0.15819132 | 0.1483932 | 0.14562715 | 0.1886202 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.12466201 | 0.12113052 | 0.15825222 | 0.15672394 | 0.15411042 | 0.19807509 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.12448764 | 0.1211515 | 0.15833301 | 0.16105457 | 0.15856912 | 0.20355126 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.11762023 | 0.1144676 | 0.19730389 | 0.11762023 | 0.1144676 | 0.19730389 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.099364357 | 0.10153164 | 0.32134419 | 0.12708904 | 0.12708762 | 0.28931792 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.10022583 | 0.098099772 | 0.32989656 | 0.13254487 | 0.13343558 | 0.28047578 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.098682669 | 0.097119801 | 0.38037066 | 0.13684932 | 0.14013407 | 0.27050785 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.12840684 | 0.12790716 | 0.34906403 | 0.12840684 | 0.12790716 | 0.34906403 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.11773724 | 0.11432304 | 0.19338715 | 0.14094839 | 0.13868552 | 0.21972519 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.086662359 | 0.083459095 | 0.4104528 | 0.10945071 | 0.11018736 | 0.3346551 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.12518012 | 0.12310951 | 0.002464878 | 0.16054031 | 0.15844115 | 0.07537213 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.12235123 | 0.1191359 | 0.35856329 | 0.12235123 | 0.1191359 | 0.35856329 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.11816961 | 0.12154782 | 0.26994074 | 0.14018146 | 0.14245393 | 0.2719579 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.12385332 | 0.12119266 | 0.18063041 | 0.1567845 | 0.15447576 | 0.21889364 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.132522 | 0.12895408 | 0.26566011 | 0.16365179 | 0.16100035 | 0.23977194 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.1376663 | 0.13632031 | 0.31215599 | 0.1376663 | 0.13632031 | 0.31215599 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.13080818 | 0.13067833 | 0.35657574 | 0.15458831 | 0.15034529 | 0.3284125 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.14974942 | 0.1375657 | 0.25025595 | 0.16560574 | 0.16183056 | 0.28733203 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.13985594 | 0.13930175 | 0.38411831 | 0.16913737 | 0.16830559 | 0.31355756 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.13850723 | 0.13420441 | 0.3166489 | 0.13850723 | 0.13420441 | 0.3166489 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.13551663 | 0.13346504 | 0.35170207 | 0.15699965 | 0.15491499 | 0.3089878 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.1405445 | 0.13660344 | 0.3556197 | 0.16595013 | 0.16408808 | 0.30311664 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.14014081 | 0.13577144 | 0.14494466 | 0.16691085 | 0.16415289 | 0.28616731 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.11790292 | 0.11867438 | 0.071863149 | 0.14890706 | 0.15135227 | 0.17261311 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.11636744 | 0.12433155 | 0.17358514 | 0.14732812 | 0.14716994 | 0.27981021 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.14529318 | 0.13908148 | 0.30500274 | 0.14529318 | 0.13908148 | 0.30500274 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.13933668 | 0.13245738 | 0.30155418 | 0.1604874 | 0.15173392 | 0.28987538 |

#### precision at 0 5

Saved field: `precision_at_0_5`. Higher is better.

![precision at 0 5 across models and splits](evaluation/figures/048_precision_at_0_5.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.71328591 | 0.88079322 | 0.34486415 | 0.70928684 | 0.8884493 | 0.27904878 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.7728058 | 0.38062372 | 0.36243044 | 0.77503154 | 0.38973282 | 0.24894957 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.68778331 | 0.15944753 | 0.3292134 | 0.70441091 | 0.17674612 | 0.20368888 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.49936984 | 0.76878302 | 0.51328778 | 0.49936984 | 0.76878302 | 0.51328778 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.6977886 | 0.69648486 | 0.34169862 | 0.69841566 | 0.49199177 | 0.2940317 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.9754069 | 1 | 0.54785943 | 0.9754069 | 1 | 0.54785943 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.87310537 | 1 | 0.17488989 | 0.75133161 | 0.31802039 | 0.13716459 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.68771803 | 1 | 0.38870761 | 0.68771803 | 1 | 0.38870761 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 1 | 0.51960314 | 0.52682453 | 1 | 0.53006792 | 0.48753467 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.97445291 | 0.84245523 | 0.31504519 | 0.97484561 | 0.8535967 | 0.29337816 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.81081365 | 0.49864374 | 0.30703923 | 0.83273012 | 0.52729221 | 0.1528903 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.82416397 | 0.93303462 | 0.51953894 | 0.82416397 | 0.93303462 | 0.51953894 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.93114862 | 0.88904316 | 0.36133271 | 0.93094035 | 0.89923536 | 0.2925836 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.96287722 | 0.89960807 | 0.36717767 | 0.96738439 | 0.91114503 | 0.211276 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.95503346 | 0.89411631 | 0.30616661 | 0.96028229 | 0.90630204 | 0.14737294 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.82608444 | 0.93391053 | 0.37490191 | 0.82608444 | 0.93391053 | 0.37490191 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.70474981 | 0.90329006 | 0.37059226 | 0.72253657 | 0.91241833 | 0.28578586 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.88090812 | 0.81811257 | 0.36905919 | 0.89013662 | 0.83540016 | 0.27232163 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.90936198 | 0.89330119 | 0.35458676 | 0.91962507 | 0.42920034 | 0.28919336 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.99482861 | 1 | 0.31277976 | 0.99558735 | 1 | 0.2949308 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.9641785 | 1 | 0.30759974 | 0.96920063 | 1 | 0.30759974 |
| random_forest K=3 (`rf3_depth8`) | 3 | 1 | 0.30638704 | 0.25048026 | 1 | 0.30638704 | 0.25048026 |
| random_forest K=5 (`rf5_depth8`) | 5 | 1 | 0.30618283 | 0.24899755 | 1 | 0.34819771 | 0.14657003 |

#### precision at validation f1 threshold

Saved field: `precision_at_validation_f1_threshold`. Higher is better.

![precision at validation f1 threshold across models and splits](evaluation/figures/049_precision_at_validation_f1_threshold.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.070081902 | 0.072677327 | 0.1473159 | 0.070081902 | 0.072677327 | 0.1473159 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.087157937 | 0.086529529 | 0.18862417 | 0.087157937 | 0.086529529 | 0.18862417 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.087126284 | 0.086588168 | 0.18874037 | 0.087126284 | 0.086588168 | 0.18874037 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.087376296 | 0.086732771 | 0.18863989 | 0.087376296 | 0.086732771 | 0.18863989 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.079691615 | 0.087804041 | 0.26148842 | 0.079691615 | 0.087804041 | 0.26148842 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.075724286 | 0.07995365 | 0.33052361 | 0.075122962 | 0.079017797 | 0.27848609 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.089566557 | 0.085501677 | 0.3398555 | 0.088417441 | 0.084037406 | 0.25908943 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.082276291 | 0.079959939 | 0.32418011 | 0.077166017 | 0.075113799 | 0.23009466 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.098306401 | 0.097349637 | 0.36634882 | 0.098306401 | 0.097349637 | 0.36634882 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.092113207 | 0.088398827 | 0.28295608 | 0.092250652 | 0.088216893 | 0.25740498 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.085128625 | 0.079803863 | 0.40440902 | 0.083575021 | 0.078383482 | 0.31955023 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.096448126 | 0.091549459 | 0.16907997 | 0.097498555 | 0.091479074 | 0.16577565 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.10167027 | 0.10521457 | 0.36057172 | 0.10167027 | 0.10521457 | 0.36057172 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.079652764 | 0.082663738 | 0.29186863 | 0.079848053 | 0.082980404 | 0.28297748 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.089811099 | 0.089288439 | 0.27673619 | 0.090643222 | 0.089814493 | 0.26339353 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.11191018 | 0.10921598 | 0.3163893 | 0.11332028 | 0.11044952 | 0.18093079 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.12219548 | 0.1182733 | 0.47349548 | 0.12219548 | 0.1182733 | 0.47349548 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.12460736 | 0.12097799 | 0.43736476 | 0.12586335 | 0.121918 | 0.40517904 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.10935961 | 0.10266948 | 0.37761968 | 0.11076031 | 0.10380487 | 0.26394975 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.13156371 | 0.12372048 | 0.41457058 | 0.13346374 | 0.12522182 | 0.28651131 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.10360054 | 0.098143272 | 0.35563873 | 0.10360054 | 0.098143272 | 0.35563873 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.11370739 | 0.10322997 | 0.38282647 | 0.11473629 | 0.10407666 | 0.3267398 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.10899905 | 0.10201785 | 0.36505779 | 0.11000152 | 0.1029185 | 0.29309804 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.12086115 | 0.10993525 | 0.4069771 | 0.11912438 | 0.10764824 | 0.38166504 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.089016114 | 0.083724095 | 0.2756331 | 0.078485799 | 0.075170449 | 0.19101212 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.12803192 | 0.097343236 | 0.35031149 | 0.12993679 | 0.098608068 | 0.29605438 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.097939864 | 0.082987655 | 0.26900761 | 0.097939864 | 0.082987655 | 0.26900761 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.10492105 | 0.084335486 | 0.27859405 | 0.096115262 | 0.07517753 | 0.19771211 |

#### recall at 0 5

Saved field: `recall_at_0_5`. Higher is better.

![recall at 0 5 across models and splits](evaluation/figures/050_recall_at_0_5.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.0062793241 | 0.0054340155 | 0.058281377 | 0.0062725654 | 0.0055248619 | 0.049007374 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.0076374925 | 0.0071983063 | 0.051097858 | 0.0076475937 | 0.0068857997 | 0.039289055 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.0095248174 | 0.0091037403 | 0.052724316 | 0.0097600846 | 0.0093613747 | 0.038663107 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.00074081913 | 0.00098800282 | 0.039306045 | 0.00074081913 | 0.00098800282 | 0.039306045 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.017673828 | 0.0151729 | 0.22228246 | 0.017037419 | 0.014577648 | 0.19705048 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.002945638 | 0.0035991531 | 0.013282732 | 0.0027115672 | 0.0033129791 | 0.010186051 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.010212721 | 0.0091037403 | 0.0032529141 | 0.011843518 | 0.010259041 | 0.0026698309 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.0017991322 | 0.0019760056 | 0.029276227 | 0.0017991322 | 0.0019760056 | 0.029276227 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.0093307934 | 0.0098800282 | 0.006234752 | 0.0092175099 | 0.0097184317 | 0.0053318208 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.014022648 | 0.012632322 | 0.19097316 | 0.015002923 | 0.013057035 | 0.15185532 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.015504286 | 0.013126323 | 0.18134996 | 0.01652323 | 0.013977943 | 0.14713735 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.012258793 | 0.012420607 | 0.13513147 | 0.012258793 | 0.012420607 | 0.13513147 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.013722793 | 0.011785462 | 0.061398753 | 0.014791275 | 0.012381016 | 0.053885423 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.022859562 | 0.020536344 | 0.23597181 | 0.024063129 | 0.021631805 | 0.20559193 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.017567997 | 0.015525759 | 0.10883708 | 0.018558585 | 0.016157989 | 0.08058934 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.0081137334 | 0.008398024 | 0.10124695 | 0.0081137334 | 0.008398024 | 0.10124695 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.017973683 | 0.016513761 | 0.20073191 | 0.019217011 | 0.017373361 | 0.18434487 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.0121706 | 0.010444601 | 0.12645703 | 0.012534909 | 0.010848382 | 0.098430517 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.018591033 | 0.017290049 | 0.063838439 | 0.019263747 | 0.017953321 | 0.048155839 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.014287226 | 0.014043754 | 0.02832746 | 0.015225091 | 0.015067966 | 0.020666469 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.011994215 | 0.010938603 | 0.066820276 | 0.012740997 | 0.011541421 | 0.048749135 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.031837584 | 0.031263232 | 0.1092437 | 0.031837584 | 0.031263232 | 0.1092437 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.032807705 | 0.030839802 | 0.095418813 | 0.03748565 | 0.035212674 | 0.081338627 |

#### recall at validation f1 threshold

Saved field: `recall_at_validation_f1_threshold`. Higher is better.

![recall at validation f1 threshold across models and splits](evaluation/figures/051_recall_at_validation_f1_threshold.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.31740572 | 0.31820748 | 0.14434806 | 0.31740572 | 0.31820748 | 0.14434806 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.22697287 | 0.22724065 | 0.094741122 | 0.21409913 | 0.21433802 | 0.079296653 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.22963629 | 0.23105152 | 0.095283275 | 0.21138858 | 0.21268027 | 0.073069328 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.23180583 | 0.23281581 | 0.095418813 | 0.2106191 | 0.2115286 | 0.069613369 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.22289837 | 0.22187721 | 0.12849011 | 0.22289837 | 0.22187721 | 0.12849011 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.2146788 | 0.21672548 | 0.6444836 | 0.20464869 | 0.2062837 | 0.58740783 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.20157336 | 0.20197601 | 0.62239089 | 0.18899786 | 0.18896973 | 0.53622285 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.22647899 | 0.22406493 | 0.63757116 | 0.22300752 | 0.22101821 | 0.53594383 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.24799802 | 0.25158786 | 0.59663866 | 0.24799802 | 0.25158786 | 0.59663866 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.22559706 | 0.22575865 | 0.37286528 | 0.21323395 | 0.21333955 | 0.32728304 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.16649028 | 0.16803105 | 0.5238547 | 0.1583263 | 0.16019228 | 0.43841597 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.21145095 | 0.21249118 | 0.075630252 | 0.1947209 | 0.19511413 | 0.055473153 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.20056796 | 0.20275229 | 0.51626457 | 0.20056796 | 0.20275229 | 0.51626457 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.32003387 | 0.32406493 | 0.38289509 | 0.30326273 | 0.30719563 | 0.32206466 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.23648005 | 0.23662668 | 0.34914611 | 0.21991297 | 0.21924126 | 0.27627066 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.19437683 | 0.1942837 | 0.30590946 | 0.17930349 | 0.1788279 | 0.24681104 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.18490493 | 0.18623853 | 0.46286256 | 0.18490493 | 0.18623853 | 0.46286256 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.18351148 | 0.18539167 | 0.45988073 | 0.17519924 | 0.17652932 | 0.38979013 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.25937489 | 0.25603387 | 0.55611277 | 0.24223875 | 0.23859945 | 0.46190625 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.208911 | 0.21496119 | 0.52127948 | 0.19300607 | 0.19806361 | 0.38425789 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.26983455 | 0.27028934 | 0.59108159 | 0.26983455 | 0.27028934 | 0.59108159 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.23748545 | 0.2412844 | 0.55882353 | 0.22646124 | 0.229781 | 0.50141804 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.25607648 | 0.25610445 | 0.62876118 | 0.23834188 | 0.23814473 | 0.50743166 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.2076763 | 0.2057163 | 0.50542152 | 0.19941664 | 0.19716594 | 0.37644616 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.22395668 | 0.22180663 | 0.27975061 | 0.29233777 | 0.28917671 | 0.26727974 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.15488411 | 0.15271701 | 0.54933586 | 0.1436287 | 0.14131829 | 0.43379808 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.35887395 | 0.36005646 | 0.75508268 | 0.35887395 | 0.36005646 | 0.75508268 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.32190355 | 0.32208892 | 0.74749255 | 0.3291849 | 0.33009386 | 0.75825298 |

### Calibration

#### Weighted expected calibration error

Saved field: `calibration.weighted_expected_calibration_error`. Lower is better.

![Weighted expected calibration error across models and splits](evaluation/figures/052_calibration_weighted_expected_calibration_error.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.0046525413 | 0.0050755483 | 0.058927046 | 0.0046525413 | 0.0050755483 | 0.058927046 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.0075471519 | 0.0076342825 | 0.055132894 | 0.0051583001 | 0.0052000323 | 0.039090839 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.0078859943 | 0.0080350368 | 0.055774252 | 0.0044276629 | 0.0044900317 | 0.031441638 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.0076172848 | 0.00775208 | 0.055985281 | 0.0036476703 | 0.0036932297 | 0.02607496 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.0057995017 | 0.0054306762 | 0.058270934 | 0.0057995017 | 0.0054306762 | 0.058270934 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.0028556787 | 0.0029388135 | 0.044460056 | 0.0017694447 | 0.0018295822 | 0.028384221 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.0021547773 | 0.0035134345 | 0.044817473 | 0.0011089195 | 0.0017041141 | 0.021671288 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.0023501369 | 0.0040257452 | 0.045123171 | 0.0012180443 | 0.0020154208 | 0.018670616 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.0059041614 | 0.0055354931 | 0.050716787 | 0.0059041614 | 0.0055354931 | 0.050716787 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.0068940647 | 0.0062226135 | 0.076912659 | 0.0048388433 | 0.0045328362 | 0.055943646 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.0045839074 | 0.0053602282 | 0.057674703 | 0.00093029705 | 0.0014054295 | 0.027761276 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.0059222979 | 0.0056913324 | 0.066616033 | 0.0025640502 | 0.0026697663 | 0.02907148 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.0025924434 | 0.0017750034 | 0.049342595 | 0.0025924434 | 0.0017750034 | 0.049342595 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.0031051939 | 0.0039145077 | 0.058959677 | 0.002085557 | 0.002559466 | 0.04035732 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.0052288692 | 0.0054667735 | 0.075728853 | 0.003111869 | 0.0032184284 | 0.040307928 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.0060822012 | 0.0060317001 | 0.083047266 | 0.0028021356 | 0.0027763229 | 0.050571497 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.0058004023 | 0.0046585443 | 0.052847421 | 0.0058004023 | 0.0046585443 | 0.052847421 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.0034238284 | 0.0035136909 | 0.057650007 | 0.0028996936 | 0.0029558356 | 0.041526369 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.0068884338 | 0.0062263163 | 0.071582926 | 0.003856711 | 0.0035589918 | 0.053525132 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.0038878908 | 0.0025210262 | 0.066797774 | 0.0020876734 | 0.0015931762 | 0.036895175 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.0036744474 | 0.0028038428 | 0.048078197 | 0.0036744474 | 0.0028038428 | 0.048078197 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.004767658 | 0.0041673515 | 0.06912081 | 0.0036757502 | 0.0033226879 | 0.05354337 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.0049196379 | 0.0042074064 | 0.04873271 | 0.0030204363 | 0.0026920981 | 0.028150991 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.0063324971 | 0.0064218827 | 0.052116822 | 0.003077827 | 0.0032529488 | 0.025404585 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.0062319686 | 0.0061429557 | 0.069729125 | 0.0031364437 | 0.0031005809 | 0.028894264 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.0069685644 | 0.0070033279 | 0.054708468 | 0.0032924569 | 0.0033124906 | 0.023915833 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.0056470554 | 0.0093073662 | 0.036470337 | 0.0056470554 | 0.0093073662 | 0.036470337 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.0083203829 | 0.011596487 | 0.040477081 | 0.0068738154 | 0.0093031628 | 0.027667052 |

### Cohort and support diagnostics

#### mean probability

Saved field: `mean_probability`. Descriptive; no universal better direction.

![mean probability across models and splits](evaluation/figures/053_mean_probability.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.029235651 | 0.029232409 | 0.027737021 | 0.029235651 | 0.029232409 | 0.027737021 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.033412325 | 0.033569035 | 0.031531172 | 0.019910005 | 0.020003082 | 0.017481231 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.032741443 | 0.03291377 | 0.030889814 | 0.014298291 | 0.014366904 | 0.011858922 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.032495642 | 0.032671485 | 0.030678785 | 0.011585819 | 0.01164341 | 0.0091110952 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.030889321 | 0.030855068 | 0.029039379 | 0.030889321 | 0.030855068 | 0.029039379 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.027937764 | 0.028514606 | 0.052037206 | 0.017738837 | 0.01805571 | 0.036071035 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.027590341 | 0.02861995 | 0.049604702 | 0.013765054 | 0.01429727 | 0.027278568 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.027494564 | 0.028625211 | 0.052021859 | 0.011732058 | 0.012275662 | 0.023701986 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.02216987 | 0.022461963 | 0.037467171 | 0.02216987 | 0.022461963 | 0.037467171 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.026665424 | 0.026940403 | 0.078303199 | 0.015873436 | 0.016125587 | 0.050084749 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.023233353 | 0.024090487 | 0.029193512 | 0.013269569 | 0.013752953 | 0.016168244 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.028321183 | 0.028312894 | 0.022419488 | 0.010634572 | 0.010845237 | 0.0071784637 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.027295567 | 0.027308474 | 0.040581969 | 0.027295567 | 0.027308474 | 0.040581969 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.026902701 | 0.027807397 | 0.028082508 | 0.016860126 | 0.017395339 | 0.016865313 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.02914734 | 0.029319334 | 0.077553261 | 0.012887516 | 0.012952997 | 0.032178708 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.027281298 | 0.027635105 | 0.070607544 | 0.010028388 | 0.010162228 | 0.040156874 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.028988205 | 0.029091242 | 0.049054565 | 0.028988205 | 0.029091242 | 0.049054565 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.026454936 | 0.026439964 | 0.042460613 | 0.015646086 | 0.015619737 | 0.026116408 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.027736208 | 0.028194508 | 0.081888218 | 0.012249486 | 0.012449541 | 0.052855058 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.026346687 | 0.026980772 | 0.056288444 | 0.0096311086 | 0.0098582914 | 0.027760529 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.024537628 | 0.025116678 | 0.053885981 | 0.024537628 | 0.025116678 | 0.053885981 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.023734304 | 0.024502478 | 0.069636444 | 0.014062325 | 0.014497385 | 0.049836511 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.027587378 | 0.028315104 | 0.061077828 | 0.012111765 | 0.012418641 | 0.029732072 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.030223899 | 0.03132139 | 0.046937358 | 0.010882851 | 0.01141861 | 0.015384864 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.020666649 | 0.020841786 | 0.026578405 | 0.0073958309 | 0.0074566343 | 0.0093176326 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.019930054 | 0.021176564 | 0.047247589 | 0.0072398177 | 0.0076775468 | 0.015799763 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.029538613 | 0.034042252 | 0.079621371 | 0.029538613 | 0.034042252 | 0.079621371 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.025366412 | 0.029687366 | 0.072409772 | 0.018686221 | 0.021944554 | 0.063040829 |

#### positive population weight

Saved field: `positive_population_weight`. Descriptive; no universal better direction.

![positive population weight across models and splits](evaluation/figures/054_positive_population_weight.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 56694 | 14170 | 7378 | 60103 | 15023 | 8815 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 56694 | 14170 | 7378 | 61588 | 15394 | 9621 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 56694 | 14170 | 7378 | 60103 | 15023 | 8815 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 56694 | 14170 | 7378 | 61588 | 15394 | 9621 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 56694 | 14170 | 7378 | 60103 | 15023 | 8815 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 56694 | 14170 | 7378 | 61588 | 15394 | 9621 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 56694 | 14170 | 7378 | 60103 | 15023 | 8815 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 56694 | 14170 | 7378 | 61588 | 15394 | 9621 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 56694 | 14170 | 7378 | 60103 | 15023 | 8815 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 56694 | 14170 | 7378 | 61588 | 15394 | 9621 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 56694 | 14170 | 7378 | 60103 | 15023 | 8815 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 56694 | 14170 | 7378 | 61588 | 15394 | 9621 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| random_forest K=3 (`rf3_depth8`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| random_forest K=5 (`rf5_depth8`) | 5 | 56694 | 14170 | 7378 | 60103 | 15023 | 8815 |

#### positive sample count

Saved field: `positive_sample_count`. Descriptive; no universal better direction.

![positive sample count across models and splits](evaluation/figures/055_positive_sample_count.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 56694 | 14170 | 7378 | 60103 | 15023 | 8815 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 56694 | 14170 | 7378 | 61588 | 15394 | 9621 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 56694 | 14170 | 7378 | 60103 | 15023 | 8815 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 56694 | 14170 | 7378 | 61588 | 15394 | 9621 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 56694 | 14170 | 7378 | 60103 | 15023 | 8815 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 56694 | 14170 | 7378 | 61588 | 15394 | 9621 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 56694 | 14170 | 7378 | 60103 | 15023 | 8815 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 56694 | 14170 | 7378 | 61588 | 15394 | 9621 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 56694 | 14170 | 7378 | 60103 | 15023 | 8815 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 56694 | 14170 | 7378 | 61588 | 15394 | 9621 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 56694 | 14170 | 7378 | 60103 | 15023 | 8815 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 56694 | 14170 | 7378 | 61588 | 15394 | 9621 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 56694 | 14170 | 7378 | 62397 | 15596 | 10113 |
| random_forest K=3 (`rf3_depth8`) | 3 | 56694 | 14170 | 7378 | 56694 | 14170 | 7378 |
| random_forest K=5 (`rf5_depth8`) | 5 | 56694 | 14170 | 7378 | 60103 | 15023 | 8815 |

#### represented population weight

Saved field: `represented_population_weight`. Descriptive; no universal better direction.

![represented population weight across models and splits](evaluation/figures/056_represented_population_weight.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 2107691.9 | 526919.17 | 85133.324 | 2107691.9 | 526919.17 | 85133.324 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 2107691.9 | 526919.17 | 85133.324 | 3579777.7 | 895278.94 | 155818.94 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 2107691.9 | 526919.17 | 85133.324 | 4834152.6 | 1209141.9 | 222191.12 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 2107691.9 | 526919.17 | 85133.324 | 5924361.3 | 1481807.7 | 287415 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 2107691.9 | 526919.17 | 85133.324 | 2107691.9 | 526919.17 | 85133.324 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 2107691.9 | 526919.17 | 85133.324 | 3579777.7 | 895278.94 | 155818.94 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 2107691.9 | 526919.17 | 85133.324 | 4834152.6 | 1209141.9 | 222191.12 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 2107691.9 | 526919.17 | 85133.324 | 5924361.3 | 1481807.7 | 287415 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 2107691.9 | 526919.17 | 85133.324 | 2107691.9 | 526919.17 | 85133.324 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 2107691.9 | 526919.17 | 85133.324 | 3579777.7 | 895278.94 | 155818.94 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 2107691.9 | 526919.17 | 85133.324 | 4834152.6 | 1209141.9 | 222191.12 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 2107691.9 | 526919.17 | 85133.324 | 5924361.3 | 1481807.7 | 287415 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 2107691.9 | 526919.17 | 85133.324 | 2107691.9 | 526919.17 | 85133.324 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 2107691.9 | 526919.17 | 85133.324 | 3579777.7 | 895278.94 | 155818.94 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 2107691.9 | 526919.17 | 85133.324 | 4834152.6 | 1209141.9 | 222191.12 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 2107691.9 | 526919.17 | 85133.324 | 5924361.3 | 1481807.7 | 287415 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 2107691.9 | 526919.17 | 85133.324 | 2107691.9 | 526919.17 | 85133.324 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 2107691.9 | 526919.17 | 85133.324 | 3579777.7 | 895278.94 | 155818.94 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 2107691.9 | 526919.17 | 85133.324 | 4834152.6 | 1209141.9 | 222191.12 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 2107691.9 | 526919.17 | 85133.324 | 5924361.3 | 1481807.7 | 287415 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 2107691.9 | 526919.17 | 85133.324 | 2107691.9 | 526919.17 | 85133.324 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 2107691.9 | 526919.17 | 85133.324 | 3579777.7 | 895278.94 | 155818.94 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 2107691.9 | 526919.17 | 85133.324 | 4834152.6 | 1209141.9 | 222191.12 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 2107691.9 | 526919.17 | 85133.324 | 5924361.3 | 1481807.7 | 287415 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 2107691.9 | 526919.17 | 85133.324 | 5924361.3 | 1481807.7 | 287415 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 2107691.9 | 526919.17 | 85133.324 | 5924361.3 | 1481807.7 | 287415 |
| random_forest K=3 (`rf3_depth8`) | 3 | 2107691.9 | 526919.17 | 85133.324 | 2107691.9 | 526919.17 | 85133.324 |
| random_forest K=5 (`rf5_depth8`) | 5 | 2107691.9 | 526919.17 | 85133.324 | 3579777.7 | 895278.94 | 155818.94 |

#### sample count

Saved field: `sample_count`. Descriptive; no universal better direction.

![sample count across models and splits](evaluation/figures/057_sample_count.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 89874 | 22528 | 16807 | 89874 | 22528 | 16807 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 89874 | 22528 | 16807 | 117500 | 29454 | 26943 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 89874 | 22528 | 16807 | 139323 | 34980 | 36287 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 89874 | 22528 | 16807 | 158561 | 39776 | 45391 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 89874 | 22528 | 16807 | 89874 | 22528 | 16807 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 89874 | 22528 | 16807 | 117500 | 29454 | 26943 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 89874 | 22528 | 16807 | 139323 | 34980 | 36287 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 89874 | 22528 | 16807 | 158561 | 39776 | 45391 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 89874 | 22528 | 16807 | 89874 | 22528 | 16807 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 89874 | 22528 | 16807 | 117500 | 29454 | 26943 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 89874 | 22528 | 16807 | 139323 | 34980 | 36287 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 89874 | 22528 | 16807 | 158561 | 39776 | 45391 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 89874 | 22528 | 16807 | 89874 | 22528 | 16807 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 89874 | 22528 | 16807 | 117500 | 29454 | 26943 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 89874 | 22528 | 16807 | 139323 | 34980 | 36287 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 89874 | 22528 | 16807 | 158561 | 39776 | 45391 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 89874 | 22528 | 16807 | 89874 | 22528 | 16807 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 89874 | 22528 | 16807 | 117500 | 29454 | 26943 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 89874 | 22528 | 16807 | 139323 | 34980 | 36287 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 89874 | 22528 | 16807 | 158561 | 39776 | 45391 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 89874 | 22528 | 16807 | 89874 | 22528 | 16807 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 89874 | 22528 | 16807 | 117500 | 29454 | 26943 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 89874 | 22528 | 16807 | 139323 | 34980 | 36287 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 89874 | 22528 | 16807 | 158561 | 39776 | 45391 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 89874 | 22528 | 16807 | 158561 | 39776 | 45391 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 89874 | 22528 | 16807 | 158561 | 39776 | 45391 |
| random_forest K=3 (`rf3_depth8`) | 3 | 89874 | 22528 | 16807 | 89874 | 22528 | 16807 |
| random_forest K=5 (`rf5_depth8`) | 5 | 89874 | 22528 | 16807 | 117500 | 29454 | 26943 |

#### sample positive fraction

Saved field: `sample_positive_fraction`. Descriptive; no universal better direction.

![sample positive fraction across models and splits](evaluation/figures/058_sample_positive_fraction.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.63081648 | 0.62899503 | 0.43898376 | 0.63081648 | 0.62899503 | 0.43898376 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.63081648 | 0.62899503 | 0.43898376 | 0.51151489 | 0.51004957 | 0.32717218 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.63081648 | 0.62899503 | 0.43898376 | 0.44205192 | 0.44008005 | 0.26513627 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.63081648 | 0.62899503 | 0.43898376 | 0.39352047 | 0.39209574 | 0.22279747 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.63081648 | 0.62899503 | 0.43898376 | 0.63081648 | 0.62899503 | 0.43898376 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.63081648 | 0.62899503 | 0.43898376 | 0.51151489 | 0.51004957 | 0.32717218 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.63081648 | 0.62899503 | 0.43898376 | 0.44205192 | 0.44008005 | 0.26513627 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.63081648 | 0.62899503 | 0.43898376 | 0.39352047 | 0.39209574 | 0.22279747 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.63081648 | 0.62899503 | 0.43898376 | 0.63081648 | 0.62899503 | 0.43898376 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.63081648 | 0.62899503 | 0.43898376 | 0.51151489 | 0.51004957 | 0.32717218 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.63081648 | 0.62899503 | 0.43898376 | 0.44205192 | 0.44008005 | 0.26513627 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.63081648 | 0.62899503 | 0.43898376 | 0.39352047 | 0.39209574 | 0.22279747 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.63081648 | 0.62899503 | 0.43898376 | 0.63081648 | 0.62899503 | 0.43898376 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.63081648 | 0.62899503 | 0.43898376 | 0.51151489 | 0.51004957 | 0.32717218 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.63081648 | 0.62899503 | 0.43898376 | 0.44205192 | 0.44008005 | 0.26513627 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.63081648 | 0.62899503 | 0.43898376 | 0.39352047 | 0.39209574 | 0.22279747 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.63081648 | 0.62899503 | 0.43898376 | 0.63081648 | 0.62899503 | 0.43898376 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.63081648 | 0.62899503 | 0.43898376 | 0.51151489 | 0.51004957 | 0.32717218 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.63081648 | 0.62899503 | 0.43898376 | 0.44205192 | 0.44008005 | 0.26513627 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.63081648 | 0.62899503 | 0.43898376 | 0.39352047 | 0.39209574 | 0.22279747 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.63081648 | 0.62899503 | 0.43898376 | 0.63081648 | 0.62899503 | 0.43898376 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.63081648 | 0.62899503 | 0.43898376 | 0.51151489 | 0.51004957 | 0.32717218 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.63081648 | 0.62899503 | 0.43898376 | 0.44205192 | 0.44008005 | 0.26513627 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.63081648 | 0.62899503 | 0.43898376 | 0.39352047 | 0.39209574 | 0.22279747 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.63081648 | 0.62899503 | 0.43898376 | 0.39352047 | 0.39209574 | 0.22279747 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.63081648 | 0.62899503 | 0.43898376 | 0.39352047 | 0.39209574 | 0.22279747 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.63081648 | 0.62899503 | 0.43898376 | 0.63081648 | 0.62899503 | 0.43898376 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.63081648 | 0.62899503 | 0.43898376 | 0.51151489 | 0.51004957 | 0.32717218 |

#### unsupported positive population weight

Saved field: `unsupported_positive_population_weight`. Descriptive; no universal better direction.

![unsupported positive population weight across models and splits](evaluation/figures/059_unsupported_positive_population_weight.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 1326 | 348 | 163 | 1639 | 423 | 240 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 1328 | 318 | 4278 | 1524 | 369 | 6511 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 30 | 10 | 1 | 98 | 27 | 5 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 631 | 157 | 114 | 785 | 192 | 295 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 5 | 4 | 5 | 36 | 15 | 17 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 141 | 40 | 77 | 141 | 40 | 77 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 71 | 15 | 9 | 836 | 199 | 141 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0 | 1 | 0 | 193 | 64 | 33 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 3 | 1 | 1 | 402 | 94 | 32 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 19 | 5 | 0 | 320 | 89 | 21 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0 | 0 | 0 | 56 | 9 | 12 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0 | 0 | 0 | 86 | 18 | 11 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 1227 | 286 | 1635 | 6739 | 1669 | 3095 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 49 | 12 | 9 | 3280 | 814 | 775 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |

#### unsupported positive sample count

Saved field: `unsupported_positive_sample_count`. Descriptive; no universal better direction.

![unsupported positive sample count across models and splits](evaluation/figures/060_unsupported_positive_sample_count.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 1326 | 348 | 163 | 1639 | 423 | 240 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 1328 | 318 | 4278 | 1524 | 369 | 6511 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 30 | 10 | 1 | 98 | 27 | 5 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 631 | 157 | 114 | 785 | 192 | 295 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 5 | 4 | 5 | 36 | 15 | 17 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 141 | 40 | 77 | 141 | 40 | 77 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 71 | 15 | 9 | 836 | 199 | 141 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0 | 1 | 0 | 193 | 64 | 33 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 3 | 1 | 1 | 402 | 94 | 32 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 19 | 5 | 0 | 320 | 89 | 21 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0 | 0 | 0 | 56 | 9 | 12 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0 | 0 | 0 | 86 | 18 | 11 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 1227 | 286 | 1635 | 6739 | 1669 | 3095 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 49 | 12 | 9 | 3280 | 814 | 775 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |

#### weighted prevalence

Saved field: `weighted_prevalence`. Descriptive; no universal better direction.

![weighted prevalence across models and splits](evaluation/figures/061_weighted_prevalence.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.026898618 | 0.02689217 | 0.086664066 | 0.026898618 | 0.02689217 | 0.086664066 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.026898618 | 0.02689217 | 0.086664066 | 0.01678959 | 0.016780245 | 0.05657207 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.026898618 | 0.02689217 | 0.086664066 | 0.012740185 | 0.012731342 | 0.04330056 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.026898618 | 0.02689217 | 0.086664066 | 0.010532275 | 0.010524982 | 0.035186055 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.026898618 | 0.02689217 | 0.086664066 | 0.026898618 | 0.02689217 | 0.086664066 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.026898618 | 0.02689217 | 0.086664066 | 0.01678959 | 0.016780245 | 0.05657207 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.026898618 | 0.02689217 | 0.086664066 | 0.012740185 | 0.012731342 | 0.04330056 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.026898618 | 0.02689217 | 0.086664066 | 0.010532275 | 0.010524982 | 0.035186055 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.026898618 | 0.02689217 | 0.086664066 | 0.026898618 | 0.02689217 | 0.086664066 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.026898618 | 0.02689217 | 0.086664066 | 0.01678959 | 0.016780245 | 0.05657207 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.026898618 | 0.02689217 | 0.086664066 | 0.012740185 | 0.012731342 | 0.04330056 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.026898618 | 0.02689217 | 0.086664066 | 0.010532275 | 0.010524982 | 0.035186055 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.026898618 | 0.02689217 | 0.086664066 | 0.026898618 | 0.02689217 | 0.086664066 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.026898618 | 0.02689217 | 0.086664066 | 0.01678959 | 0.016780245 | 0.05657207 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.026898618 | 0.02689217 | 0.086664066 | 0.012740185 | 0.012731342 | 0.04330056 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.026898618 | 0.02689217 | 0.086664066 | 0.010532275 | 0.010524982 | 0.035186055 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.026898618 | 0.02689217 | 0.086664066 | 0.026898618 | 0.02689217 | 0.086664066 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.026898618 | 0.02689217 | 0.086664066 | 0.01678959 | 0.016780245 | 0.05657207 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.026898618 | 0.02689217 | 0.086664066 | 0.012740185 | 0.012731342 | 0.04330056 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.026898618 | 0.02689217 | 0.086664066 | 0.010532275 | 0.010524982 | 0.035186055 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.026898618 | 0.02689217 | 0.086664066 | 0.026898618 | 0.02689217 | 0.086664066 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.026898618 | 0.02689217 | 0.086664066 | 0.01678959 | 0.016780245 | 0.05657207 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.026898618 | 0.02689217 | 0.086664066 | 0.012740185 | 0.012731342 | 0.04330056 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.026898618 | 0.02689217 | 0.086664066 | 0.010532275 | 0.010524982 | 0.035186055 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.026898618 | 0.02689217 | 0.086664066 | 0.010532275 | 0.010524982 | 0.035186055 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.026898618 | 0.02689217 | 0.086664066 | 0.010532275 | 0.010524982 | 0.035186055 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.026898618 | 0.02689217 | 0.086664066 | 0.026898618 | 0.02689217 | 0.086664066 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.026898618 | 0.02689217 | 0.086664066 | 0.01678959 | 0.016780245 | 0.05657207 |

#### wrong probability one negative sample count

Saved field: `wrong_probability_one_negative_sample_count`. Descriptive; no universal better direction.

![wrong probability one negative sample count across models and splits](evaluation/figures/062_wrong_probability_one_negative_sample_count.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 3 | 1 | 121 | 3 | 1 | 144 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0 | 0 | 1 | 1 | 1 | 1 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 3 | 3 | 149 | 4 | 3 | 157 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 1 | 2 | 212 | 1 | 2 | 524 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0 | 0 | 11 | 0 | 0 | 11 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 1 | 1 | 0 | 1 | 1 | 0 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0 | 1 | 223 | 0 | 1 | 463 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0 | 0 | 68 | 0 | 0 | 176 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 1 | 0 | 84 | 1 | 0 | 115 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0 | 0 | 18 | 0 | 0 | 18 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0 | 0 | 2 | 0 | 0 | 2 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |

#### zero contact population weight

Saved field: `zero_contact_population_weight`. Descriptive; no universal better direction.

![zero contact population weight across models and splits](evaluation/figures/063_zero_contact_population_weight.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |

#### zero contact positive fraction

Saved field: `zero_contact_positive_fraction`. Descriptive; no universal better direction.

![zero contact positive fraction across models and splits](evaluation/figures/064_zero_contact_positive_fraction.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |

#### zero contact positive population weight

Saved field: `zero_contact_positive_population_weight`. Descriptive; no universal better direction.

![zero contact positive population weight across models and splits](evaluation/figures/065_zero_contact_positive_population_weight.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |

#### zero contact positive sample count

Saved field: `zero_contact_positive_sample_count`. Descriptive; no universal better direction.

![zero contact positive sample count across models and splits](evaluation/figures/066_zero_contact_positive_sample_count.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0 | 0 | 0 | 0 | 0 | 0 |

### Thresholds and scoring configuration

#### classification at 0 5 / threshold

Saved field: `classification_at_0_5.threshold`. Descriptive; no universal better direction.

![classification at 0 5 / threshold across models and splits](evaluation/figures/067_classification_at_0_5_threshold.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |

#### classification at validation f1 threshold / threshold

Saved field: `classification_at_validation_f1_threshold.threshold`. Descriptive; no universal better direction.

![classification at validation f1 threshold / threshold across models and splits](evaluation/figures/068_classification_at_validation_f1_threshold_threshold.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.054297864 | 0.054297864 | 0.054297864 | 0.054297864 | 0.054297864 | 0.054297864 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.060897648 | 0.060897648 | 0.060897648 | 0.060897648 | 0.060897648 | 0.060897648 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.059054673 | 0.059054673 | 0.059054673 | 0.059054673 | 0.059054673 | 0.059054673 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.058142781 | 0.058142781 | 0.058142781 | 0.058142781 | 0.058142781 | 0.058142781 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.059079349 | 0.059079349 | 0.059079349 | 0.059079349 | 0.059079349 | 0.059079349 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.060842156 | 0.060842156 | 0.060842156 | 0.060842156 | 0.060842156 | 0.060842156 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.065915883 | 0.065915883 | 0.065915883 | 0.065915883 | 0.065915883 | 0.065915883 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.059676111 | 0.059676111 | 0.059676111 | 0.057670414 | 0.057670414 | 0.057670414 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.046022356 | 0.046022356 | 0.046022356 | 0.046022356 | 0.046022356 | 0.046022356 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.057578921 | 0.057578921 | 0.057578921 | 0.057578921 | 0.057578921 | 0.057578921 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.054273069 | 0.054273069 | 0.054273069 | 0.054273069 | 0.054273069 | 0.054273069 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.070144653 | 0.070144653 | 0.070144653 | 0.070144653 | 0.070144653 | 0.070144653 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.065211713 | 0.065211713 | 0.065211713 | 0.065211713 | 0.065211713 | 0.065211713 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.04916358 | 0.04916358 | 0.04916358 | 0.04916358 | 0.04916358 | 0.04916358 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.052939117 | 0.052939117 | 0.052939117 | 0.052939117 | 0.052939117 | 0.052939117 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.071145594 | 0.071145594 | 0.071145594 | 0.071145594 | 0.071145594 | 0.071145594 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.076186538 | 0.076186538 | 0.076186538 | 0.076186538 | 0.076186538 | 0.076186538 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.074469864 | 0.074469864 | 0.074469864 | 0.074469864 | 0.074469864 | 0.074469864 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.063084185 | 0.063084185 | 0.063084185 | 0.063084185 | 0.063084185 | 0.063084185 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.070657372 | 0.070657372 | 0.070657372 | 0.070657372 | 0.070657372 | 0.070657372 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.051772416 | 0.051772416 | 0.051772416 | 0.051772416 | 0.051772416 | 0.051772416 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.05544889 | 0.05544889 | 0.05544889 | 0.05544889 | 0.05544889 | 0.05544889 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.064703941 | 0.064703941 | 0.064703941 | 0.064703941 | 0.064703941 | 0.064703941 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.07521373 | 0.07521373 | 0.07521373 | 0.073994279 | 0.073994279 | 0.073994279 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.048711479 | 0.048711479 | 0.048711479 | 0.042155743 | 0.042155743 | 0.042155743 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.061564326 | 0.061564326 | 0.061564326 | 0.061564326 | 0.061564326 | 0.061564326 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.041938898 | 0.041938898 | 0.041938898 | 0.041938898 | 0.041938898 | 0.041938898 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.039663483 | 0.039663483 | 0.039663483 | 0.039400734 | 0.039400734 | 0.039400734 |

#### classification at validation mcc threshold / threshold

Saved field: `classification_at_validation_mcc_threshold.threshold`. Descriptive; no universal better direction.

![classification at validation mcc threshold / threshold across models and splits](evaluation/figures/069_classification_at_validation_mcc_threshold_threshold.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.043679476 | 0.043679476 | 0.043679476 | 0.043679476 | 0.043679476 | 0.043679476 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.036409736 | 0.036409736 | 0.036409736 | 0.036409736 | 0.036409736 | 0.036409736 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.033429742 | 0.033429742 | 0.033429742 | 0.033352137 | 0.033352137 | 0.033352137 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.032758653 | 0.032758653 | 0.032758653 | 0.032758653 | 0.032758653 | 0.032758653 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.042056799 | 0.042056799 | 0.042056799 | 0.042056799 | 0.042056799 | 0.042056799 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.031794012 | 0.031794012 | 0.031794012 | 0.026657403 | 0.026657403 | 0.026657403 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.03066051 | 0.03066051 | 0.03066051 | 0.021944761 | 0.021944761 | 0.021944761 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.050566196 | 0.050566196 | 0.050566196 | 0.019577682 | 0.019577682 | 0.019577682 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.030200064 | 0.030200064 | 0.030200064 | 0.030200064 | 0.030200064 | 0.030200064 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.036416352 | 0.036416352 | 0.036416352 | 0.030125797 | 0.030125797 | 0.030125797 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.04358834 | 0.04358834 | 0.04358834 | 0.026324928 | 0.026324928 | 0.026324928 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.042326212 | 0.042326212 | 0.042326212 | 0.03508085 | 0.03508085 | 0.03508085 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.046955645 | 0.046955645 | 0.046955645 | 0.046955645 | 0.046955645 | 0.046955645 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.043934762 | 0.043934762 | 0.043934762 | 0.036822677 | 0.036822677 | 0.036822677 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.029954255 | 0.029954255 | 0.029954255 | 0.029954255 | 0.029954255 | 0.029954255 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.038882077 | 0.038882077 | 0.038882077 | 0.036461473 | 0.036461473 | 0.036461473 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.040121973 | 0.040121973 | 0.040121973 | 0.040121973 | 0.040121973 | 0.040121973 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.047269464 | 0.047269464 | 0.047269464 | 0.037496507 | 0.037496507 | 0.037496507 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.39607579 | 0.39607579 | 0.39607579 | 0.039528489 | 0.039528489 | 0.039528489 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.039943695 | 0.039943695 | 0.039943695 | 0.038892686 | 0.038892686 | 0.038892686 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.033638299 | 0.033638299 | 0.033638299 | 0.033638299 | 0.033638299 | 0.033638299 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.03577888 | 0.03577888 | 0.03577888 | 0.029367745 | 0.029367745 | 0.029367745 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.041125834 | 0.041125834 | 0.041125834 | 0.034631908 | 0.034631908 | 0.034631908 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.34491378 | 0.34491378 | 0.34491378 | 0.037712991 | 0.037712991 | 0.037712991 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.48013121 | 0.48013121 | 0.48013121 | 0.022302687 | 0.022302687 | 0.022302687 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.32407922 | 0.32407922 | 0.32407922 | 0.019030273 | 0.019030273 | 0.019030273 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.030802253 | 0.030802253 | 0.030802253 | 0.030802253 | 0.030802253 | 0.030802253 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.027084587 | 0.027084587 | 0.027084587 | 0.026801016 | 0.026801016 | 0.026801016 |

#### log loss probability floor

Saved field: `log_loss_probability_floor`. Descriptive; no universal better direction.

![log loss probability floor across models and splits](evaluation/figures/070_log_loss_probability_floor.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| random_forest K=3 (`rf3_depth8`) | 3 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |
| random_forest K=5 (`rf5_depth8`) | 5 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 | 1e-07 |

#### validation f1 threshold

Saved field: `validation_f1_threshold`. Descriptive; no universal better direction.

![validation f1 threshold across models and splits](evaluation/figures/071_validation_f1_threshold.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.054297864 | 0.054297864 | 0.054297864 | 0.054297864 | 0.054297864 | 0.054297864 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.060897648 | 0.060897648 | 0.060897648 | 0.060897648 | 0.060897648 | 0.060897648 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.059054673 | 0.059054673 | 0.059054673 | 0.059054673 | 0.059054673 | 0.059054673 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.058142781 | 0.058142781 | 0.058142781 | 0.058142781 | 0.058142781 | 0.058142781 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.059079349 | 0.059079349 | 0.059079349 | 0.059079349 | 0.059079349 | 0.059079349 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.060842156 | 0.060842156 | 0.060842156 | 0.060842156 | 0.060842156 | 0.060842156 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.065915883 | 0.065915883 | 0.065915883 | 0.065915883 | 0.065915883 | 0.065915883 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.059676111 | 0.059676111 | 0.059676111 | 0.057670414 | 0.057670414 | 0.057670414 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.046022356 | 0.046022356 | 0.046022356 | 0.046022356 | 0.046022356 | 0.046022356 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.057578921 | 0.057578921 | 0.057578921 | 0.057578921 | 0.057578921 | 0.057578921 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.054273069 | 0.054273069 | 0.054273069 | 0.054273069 | 0.054273069 | 0.054273069 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.070144653 | 0.070144653 | 0.070144653 | 0.070144653 | 0.070144653 | 0.070144653 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.065211713 | 0.065211713 | 0.065211713 | 0.065211713 | 0.065211713 | 0.065211713 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.04916358 | 0.04916358 | 0.04916358 | 0.04916358 | 0.04916358 | 0.04916358 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.052939117 | 0.052939117 | 0.052939117 | 0.052939117 | 0.052939117 | 0.052939117 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.071145594 | 0.071145594 | 0.071145594 | 0.071145594 | 0.071145594 | 0.071145594 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.076186538 | 0.076186538 | 0.076186538 | 0.076186538 | 0.076186538 | 0.076186538 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.074469864 | 0.074469864 | 0.074469864 | 0.074469864 | 0.074469864 | 0.074469864 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.063084185 | 0.063084185 | 0.063084185 | 0.063084185 | 0.063084185 | 0.063084185 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.070657372 | 0.070657372 | 0.070657372 | 0.070657372 | 0.070657372 | 0.070657372 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.051772416 | 0.051772416 | 0.051772416 | 0.051772416 | 0.051772416 | 0.051772416 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.05544889 | 0.05544889 | 0.05544889 | 0.05544889 | 0.05544889 | 0.05544889 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.064703941 | 0.064703941 | 0.064703941 | 0.064703941 | 0.064703941 | 0.064703941 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.07521373 | 0.07521373 | 0.07521373 | 0.073994279 | 0.073994279 | 0.073994279 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.048711479 | 0.048711479 | 0.048711479 | 0.042155743 | 0.042155743 | 0.042155743 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.061564326 | 0.061564326 | 0.061564326 | 0.061564326 | 0.061564326 | 0.061564326 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.041938898 | 0.041938898 | 0.041938898 | 0.041938898 | 0.041938898 | 0.041938898 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.039663483 | 0.039663483 | 0.039663483 | 0.039400734 | 0.039400734 | 0.039400734 |

#### validation mcc threshold

Saved field: `validation_mcc_threshold`. Descriptive; no universal better direction.

![validation mcc threshold across models and splits](evaluation/figures/072_validation_mcc_threshold.png)

| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 3 | 0.043679476 | 0.043679476 | 0.043679476 | 0.043679476 | 0.043679476 | 0.043679476 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 5 | 0.036409736 | 0.036409736 | 0.036409736 | 0.036409736 | 0.036409736 | 0.036409736 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 7 | 0.033429742 | 0.033429742 | 0.033429742 | 0.033352137 | 0.033352137 | 0.033352137 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 9 | 0.032758653 | 0.032758653 | 0.032758653 | 0.032758653 | 0.032758653 | 0.032758653 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 3 | 0.042056799 | 0.042056799 | 0.042056799 | 0.042056799 | 0.042056799 | 0.042056799 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 5 | 0.031794012 | 0.031794012 | 0.031794012 | 0.026657403 | 0.026657403 | 0.026657403 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 7 | 0.03066051 | 0.03066051 | 0.03066051 | 0.021944761 | 0.021944761 | 0.021944761 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 9 | 0.050566196 | 0.050566196 | 0.050566196 | 0.019577682 | 0.019577682 | 0.019577682 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 3 | 0.030200064 | 0.030200064 | 0.030200064 | 0.030200064 | 0.030200064 | 0.030200064 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 5 | 0.036416352 | 0.036416352 | 0.036416352 | 0.030125797 | 0.030125797 | 0.030125797 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 7 | 0.04358834 | 0.04358834 | 0.04358834 | 0.026324928 | 0.026324928 | 0.026324928 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 9 | 0.042326212 | 0.042326212 | 0.042326212 | 0.03508085 | 0.03508085 | 0.03508085 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 3 | 0.046955645 | 0.046955645 | 0.046955645 | 0.046955645 | 0.046955645 | 0.046955645 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 5 | 0.043934762 | 0.043934762 | 0.043934762 | 0.036822677 | 0.036822677 | 0.036822677 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 7 | 0.029954255 | 0.029954255 | 0.029954255 | 0.029954255 | 0.029954255 | 0.029954255 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 9 | 0.038882077 | 0.038882077 | 0.038882077 | 0.036461473 | 0.036461473 | 0.036461473 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 3 | 0.040121973 | 0.040121973 | 0.040121973 | 0.040121973 | 0.040121973 | 0.040121973 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 5 | 0.047269464 | 0.047269464 | 0.047269464 | 0.037496507 | 0.037496507 | 0.037496507 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 7 | 0.39607579 | 0.39607579 | 0.39607579 | 0.039528489 | 0.039528489 | 0.039528489 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 9 | 0.039943695 | 0.039943695 | 0.039943695 | 0.038892686 | 0.038892686 | 0.038892686 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 3 | 0.033638299 | 0.033638299 | 0.033638299 | 0.033638299 | 0.033638299 | 0.033638299 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 5 | 0.03577888 | 0.03577888 | 0.03577888 | 0.029367745 | 0.029367745 | 0.029367745 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 7 | 0.041125834 | 0.041125834 | 0.041125834 | 0.034631908 | 0.034631908 | 0.034631908 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 9 | 0.34491378 | 0.34491378 | 0.34491378 | 0.037712991 | 0.037712991 | 0.037712991 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 9 | 0.48013121 | 0.48013121 | 0.48013121 | 0.022302687 | 0.022302687 | 0.022302687 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 9 | 0.32407922 | 0.32407922 | 0.32407922 | 0.019030273 | 0.019030273 | 0.019030273 |
| random_forest K=3 (`rf3_depth8`) | 3 | 0.030802253 | 0.030802253 | 0.030802253 | 0.030802253 | 0.030802253 | 0.030802253 |
| random_forest K=5 (`rf5_depth8`) | 5 | 0.027084587 | 0.027084587 | 0.027084587 | 0.026801016 | 0.026801016 | 0.026801016 |

### Full prediction coverage

#### coverage / no contact count

Saved field: `coverage.no_contact_count`. Descriptive; no universal better direction.

![coverage / no contact count across models and splits](evaluation/figures/073_coverage_no_contact_count.png)

| Model | Train: full rows | Validation: full rows | Test: full rows |
|---|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 109311 | 27372 | 45158 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 81685 | 20446 | 35022 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 59862 | 14920 | 25678 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 40624 | 10124 | 16574 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 109311 | 27372 | 45158 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 81685 | 20446 | 35022 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 59862 | 14920 | 25678 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 40624 | 10124 | 16574 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 109311 | 27372 | 45158 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 81685 | 20446 | 35022 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 59862 | 14920 | 25678 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 40624 | 10124 | 16574 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 109311 | 27372 | 45158 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 81685 | 20446 | 35022 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 59862 | 14920 | 25678 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 40624 | 10124 | 16574 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 109311 | 27372 | 45158 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 81685 | 20446 | 35022 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 59862 | 14920 | 25678 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 40624 | 10124 | 16574 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 109311 | 27372 | 45158 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 81685 | 20446 | 35022 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 59862 | 14920 | 25678 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 40624 | 10124 | 16574 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 40624 | 10124 | 16574 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 40624 | 10124 | 16574 |
| random_forest K=3 (`rf3_depth8`) | 109311 | 27372 | 45158 |
| random_forest K=5 (`rf5_depth8`) | 81685 | 20446 | 35022 |

#### coverage / no contact probability max

Saved field: `coverage.no_contact_probability_max`. Descriptive; no universal better direction.

![coverage / no contact probability max across models and splits](evaluation/figures/074_coverage_no_contact_probability_max.png)

| Model | Train: full rows | Validation: full rows | Test: full rows |
|---|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | -0 | -0 | -0 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | -0 | -0 | -0 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | -0 | -0 | -0 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | -0 | -0 | -0 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | -0 | -0 | -0 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | -0 | -0 | -0 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | -0 | -0 | -0 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | -0 | -0 | -0 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | -0 | -0 | -0 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | -0 | -0 | -0 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | -0 | -0 | -0 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | -0 | -0 | -0 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | -0 | -0 | -0 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | -0 | -0 | -0 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | -0 | -0 | -0 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | -0 | -0 | -0 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | -0 | -0 | -0 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | -0 | -0 | -0 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | -0 | -0 | -0 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | -0 | -0 | -0 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | -0 | -0 | -0 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | -0 | -0 | -0 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | -0 | -0 | -0 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | -0 | -0 | -0 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | -0 | -0 | -0 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | -0 | -0 | -0 |
| random_forest K=3 (`rf3_depth8`) | 1 | 1 | 0.73604862 |
| random_forest K=5 (`rf5_depth8`) | 1 | 1 | 0.82439406 |

#### coverage / predicted count

Saved field: `coverage.predicted_count`. Descriptive; no universal better direction.

![coverage / predicted count across models and splits](evaluation/figures/075_coverage_predicted_count.png)

| Model | Train: full rows | Validation: full rows | Test: full rows |
|---|---:|---:|---:|
| constant K=3 (`k3_constant_00_lr0.01_warmup_cosine`) | 199185 | 49900 | 61965 |
| constant K=5 (`k5_constant_00_lr0.1_warmup_cosine`) | 199185 | 49900 | 61965 |
| constant K=7 (`k7_constant_00_lr0.1_constant`) | 199185 | 49900 | 61965 |
| constant K=9 (`k9_constant_00_lr0.1_constant`) | 199185 | 49900 | 61965 |
| linear K=3 (`k3_linear_01_lr0.01_warmup_cosine`) | 199185 | 49900 | 61965 |
| linear K=5 (`k5_linear_01_lr0.1_constant`) | 199185 | 49900 | 61965 |
| linear K=7 (`k7_linear_01_lr0.05_constant`) | 199185 | 49900 | 61965 |
| linear K=9 (`k9_linear_01_lr0.05_constant`) | 199185 | 49900 | 61965 |
| legacy K=3 (`k3_legacy_02_lr0.05_constant`) | 199185 | 49900 | 61965 |
| legacy K=5 (`k5_legacy_02_lr0.1_warmup_cosine`) | 199185 | 49900 | 61965 |
| legacy K=7 (`k7_legacy_02_lr0.05_warmup_cosine`) | 199185 | 49900 | 61965 |
| legacy K=9 (`k9_legacy_02_lr0.1_warmup_cosine`) | 199185 | 49900 | 61965 |
| cnn K=3 (`k3_cnn_03_lr0.05_constant`) | 199185 | 49900 | 61965 |
| cnn K=5 (`k5_cnn_03_lr0.01_constant`) | 199185 | 49900 | 61965 |
| cnn K=7 (`k7_cnn_03_lr0.1_warmup_cosine`) | 199185 | 49900 | 61965 |
| cnn K=9 (`k9_cnn_03_lr0.05_warmup_cosine`) | 199185 | 49900 | 61965 |
| mlp K=3 (`k3_mlp_05_lr0.1_warmup_cosine`) | 199185 | 49900 | 61965 |
| mlp K=5 (`k5_mlp_05_lr0.1_constant`) | 199185 | 49900 | 61965 |
| mlp K=7 (`k7_mlp_06_lr0.05_warmup_cosine`) | 199185 | 49900 | 61965 |
| mlp K=9 (`k9_mlp_06_lr0.05_warmup_cosine`) | 199185 | 49900 | 61965 |
| residual_mlp K=3 (`k3_residual_mlp_08_lr0.05_constant`) | 199185 | 49900 | 61965 |
| residual_mlp K=5 (`k5_residual_mlp_09_lr0.01_constant`) | 199185 | 49900 | 61965 |
| residual_mlp K=7 (`k7_residual_mlp_08_lr0.05_constant`) | 199185 | 49900 | 61965 |
| residual_mlp K=9 (`k9_residual_mlp_08_lr0.05_constant`) | 199185 | 49900 | 61965 |
| mixed K=3+5+7+9 (`mixed_3_5_7_9_01_lr0.1_warmup_cosine`) | 199185 | 49900 | 61965 |
| neural_mixed K=3+5+7+9 (`neural_mixed_3_5_7_9_02_lr0.05_warmup_cosine`) | 199185 | 49900 | 61965 |
| random_forest K=3 (`rf3_depth8`) | 199185 | 49900 | 61965 |
| random_forest K=5 (`rf5_depth8`) | 199185 | 49900 | 61965 |

### Reliability curves and calibration bins

Each point is a populated, prespecified probability bin. Its horizontal coordinate is the weighted mean prediction and its vertical coordinate is the weighted observed outcome rate. Empty bins are retained in the bin CSV and create gaps in curves. The diagonal represents equal predicted and observed bin means. These are descriptive pooled summaries without confidence intervals or independent-cell assumptions. ECE is Σ_b(W_b/W)|p̄_b−ȳ_b| and appears above as a scalar metric.

![Weighted reliability by evaluation population](evaluation/figures/reliability_train.png)

![Weighted reliability by evaluation population](evaluation/figures/reliability_validation.png)

![Weighted reliability by evaluation population](evaluation/figures/reliability_test.png)

<!-- END COMPLETE PROBABILITY EVALUATION -->
