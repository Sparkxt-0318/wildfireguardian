# Part-a fire-level CV: pinned (E3) vs unpinned (E1), every pooled number

Caveats: covariate-free, homogeneous, 25 part-a fires incl. 4 H-dev, not the neural refit.
Pinned env: {'python': '3.12.3', 'numpy': '1.26.4', 'scipy': '1.13.1', 'pandas': '2.2.3', 'scikit-learn': '1.5.2', 'torch': '2.5.1+cpu', 'pinned': True}
E1 composite is INVALID (floor collapse); its rows are struck and kept for the record only.
check_bounds (pinned): fold 0: plugin PASS, composite PASS, meanfield_nll PASS, mcem PASS; fold 1: plugin PASS, composite PASS, meanfield_nll PASS, mcem PASS; fold 2: plugin PASS, composite PASS, meanfield_nll PASS, mcem PASS; fold 3: plugin PASS, composite PASS, meanfield_nll PASS, mcem PASS; fold 4: plugin PASS, composite PASS, meanfield_nll PASS, mcem PASS


## cv_part_a pooled

| quantity | unpinned E1 | pinned E3 | pinned − unpinned |
|---|---|---|---|
| plugin.brier | 0.0569083 | 0.0569278 | 1.9541e-05 |
| plugin.pred_area | 21056.8 | 21059.5 | 2.71094 |
| plugin.lowbin_gap | 1.89726e-05 | 1.74104e-05 | -1.56226e-06 |
| plugin.lowbin_n | 1853 | 1851 | -2 |
| plugin.pos_below_1e5 | 0 | 0 | 0 |
| plugin.pos_below_1_1024 | 0 | 0 | 0 |
| plugin.pred_0-1km | 14996.1 | 15003 | 6.90625 |
| plugin.pred_1-2km | 2993.27 | 2993.27 | 0.00292969 |
| plugin.pred_2-4km | 3067.4 | 3063.21 | -4.19824 |
| composite.brier | ~~0.062702~~ (INVALID) | 0.0636893 | 0.000987394 |
| composite.pred_area | ~~3583.12~~ (INVALID) | 22511.6 | 18928.5 |
| composite.lowbin_gap | ~~0.0567357~~ (INVALID) | 0.0268885 | -0.0298473 |
| composite.lowbin_n | ~~343898~~ (INVALID) | 239201 | -104697 |
| composite.pos_below_1e5 | ~~19264~~ (INVALID) | 5578 | -13686 |
| composite.pos_below_1_1024 | ~~19264~~ (INVALID) | 5578 | -13686 |
| composite.pred_0-1km | ~~3545.65~~ (INVALID) | 22033.8 | 18488.1 |
| composite.pred_1-2km | ~~36.7266~~ (INVALID) | 470.996 | 434.27 |
| composite.pred_2-4km | ~~0.749023~~ (INVALID) | 6.83691 | 6.08789 |
| meanfield_nll.brier | 0.0579771 | 0.0579677 | -9.32944e-06 |
| meanfield_nll.pred_area | 22166.4 | 22154.1 | -12.248 |
| meanfield_nll.lowbin_gap | 0.00254068 | 0.00351229 | 0.000971612 |
| meanfield_nll.lowbin_n | 3256 | 3225 | -31 |
| meanfield_nll.pos_below_1e5 | 3 | 4 | 1 |
| meanfield_nll.pos_below_1_1024 | 3 | 4 | 1 |
| meanfield_nll.pred_0-1km | 17303.8 | 17295.2 | -8.60059 |
| meanfield_nll.pred_1-2km | 2961.36 | 2958.89 | -2.46973 |
| meanfield_nll.pred_2-4km | 1901.22 | 1900.04 | -1.17773 |
| mcem.brier | 0.0659775 | 0.0659965 | 1.89733e-05 |
| mcem.pred_area | 27003.8 | 26994.2 | -9.62598 |
| mcem.lowbin_gap | 0.0217912 | 0.0217693 | -2.18119e-05 |
| mcem.lowbin_n | 184708 | 184326 | -382 |
| mcem.pos_below_1e5 | 2610 | 2504 | -106 |
| mcem.pos_below_1_1024 | 2610 | 2504 | -106 |
| mcem.pred_0-1km | 25396.3 | 25386.6 | -9.65039 |
| mcem.pred_1-2km | 1486.44 | 1486.4 | -0.0410156 |
| mcem.pred_2-4km | 121.153 | 121.219 | 0.0654297 |

## brier_diff_vs_mcem

| quantity | unpinned E1 | pinned E3 | pinned − unpinned |
|---|---|---|---|
| mcem_minus_plugin.point | 0.00906919 | 0.00906862 | -5.6774e-07 |
| mcem_minus_plugin.ci95_lo | 0.0056757 | 0.0056649 | -1.07986e-05 |
| mcem_minus_plugin.ci95_hi | 0.0123997 | 0.0124226 | 2.29171e-05 |
| mcem_minus_plugin.mcem_better_fires | 5/25 | 5/25 |  |
| mcem_minus_composite.point | ~~0.00327553~~ (INVALID) | 0.00230711 | -0.000968421 |
| mcem_minus_composite.ci95_lo | ~~-0.00173247~~ (INVALID) | 0.00107577 | 0.00280823 |
| mcem_minus_composite.ci95_hi | ~~0.00850668~~ (INVALID) | 0.00343956 | -0.00506712 |
| mcem_minus_composite.mcem_better_fires | ~~11/25~~ (INVALID) | 5/25 |  |
| mcem_minus_meanfield_nll.point | 0.00800042 | 0.00802872 | 2.83027e-05 |
| mcem_minus_meanfield_nll.ci95_lo | 0.00502996 | 0.00503409 | 4.13064e-06 |
| mcem_minus_meanfield_nll.ci95_hi | 0.0107313 | 0.0107774 | 4.61537e-05 |
| mcem_minus_meanfield_nll.mcem_better_fires | 4/25 | 5/25 |  |

## baselines pooled

| quantity | unpinned E1 | pinned E3 | pinned − unpinned |
|---|---|---|---|
| persistence.brier | 0.0646172 | 0.0646172 | 0 |
| persistence.brier_0-1km | 0.162152 | 0.162152 | 0 |
| persistence.brier_1-2km | 0.048447 | 0.048447 | 0 |
| persistence.brier_2-4km | 0.0233133 | 0.0233133 | 0 |
| dilation_1h.brier | 0.929215 | 0.929215 | 0 |
| dilation_1h.brier_0-1km | 0.837848 | 0.837848 | 0 |
| dilation_1h.brier_1-2km | 0.947158 | 0.947158 | 0 |
| dilation_1h.brier_2-4km | 0.966217 | 0.966217 | 0 |
| dilation_2h.brier | 0.91943 | 0.91943 | 0 |
| dilation_2h.brier_0-1km | 0.834223 | 0.834223 | 0 |
| dilation_2h.brier_1-2km | 0.94173 | 0.94173 | 0 |
| dilation_2h.brier_2-4km | 0.950572 | 0.950572 | 0 |
| dilation_4h.brier | 0.655095 | 0.655095 | 0 |
| dilation_4h.brier_0-1km | 0.829471 | 0.829471 | 0 |
| dilation_4h.brier_1-2km | 0.92282 | 0.92282 | 0 |
| dilation_4h.brier_2-4km | 0.401934 | 0.401934 | 0 |
| dilation_8h.brier | 0.341693 | 0.341693 | 0 |
| dilation_8h.brier_0-1km | 0.823293 | 0.823293 | 0 |
| dilation_8h.brier_1-2km | 0.384867 | 0.384867 | 0 |
| dilation_8h.brier_2-4km | 0.0633823 | 0.0633823 | 0 |
| dilation_best.brier | 0.341693 | 0.341693 | 0 |
| dilation_best.brier_0-1km | 0.823293 | 0.823293 | 0 |
| dilation_best.brier_1-2km | 0.384867 | 0.384867 | 0 |
| dilation_best.brier_2-4km | 0.0633823 | 0.0633823 | 0 |
| logistic_cf.brier | 0.0566464 | 0.0566464 | 5.46091e-15 |
| logistic_cf.brier_0-1km | 0.133377 | 0.133377 | 1.28786e-14 |
| logistic_cf.brier_1-2km | 0.0462556 | 0.0462556 | 5.50254e-15 |
| logistic_cf.brier_2-4km | 0.0227441 | 0.0227441 | 1.59248e-15 |
| plugin.brier | 0.0569083 | 0.0569278 | 1.9541e-05 |
| plugin.brier_0-1km | 0.134665 | 0.134731 | 6.51e-05 |
| plugin.brier_1-2km | 0.0463312 | 0.0463332 | 1.98804e-06 |
| plugin.brier_2-4km | 0.0225808 | 0.0225871 | 6.29261e-06 |
| composite.brier | ~~0.062702~~ (INVALID) | 0.0636893 | 0.000987394 |
| composite.brier_0-1km | ~~0.154516~~ (INVALID) | 0.159052 | 0.00453588 |
| composite.brier_1-2km | ~~0.04832~~ (INVALID) | 0.0478726 | -0.00044738 |
| composite.brier_2-4km | ~~0.0233128~~ (INVALID) | 0.0233092 | -3.61747e-06 |
| meanfield_nll.brier | 0.0579771 | 0.0579677 | -9.32944e-06 |
| meanfield_nll.brier_0-1km | 0.138255 | 0.138204 | -5.11722e-05 |
| meanfield_nll.brier_1-2km | 0.046707 | 0.0467157 | 8.79459e-06 |
| meanfield_nll.brier_2-4km | 0.0227485 | 0.0227501 | 1.62753e-06 |
| mcem.brier | 0.0659775 | 0.0659965 | 1.89733e-05 |
| mcem.brier_0-1km | 0.168756 | 0.168836 | 8.00243e-05 |
| mcem.brier_1-2km | 0.0476071 | 0.0476105 | 3.35141e-06 |
| mcem.brier_2-4km | 0.0232575 | 0.023254 | -3.55564e-06 |

## baselines paired

| quantity | unpinned E1 | pinned E3 | pinned − unpinned |
|---|---|---|---|
| persistence_minus_plugin.point | 0.0077089 | 0.00768936 | -1.9541e-05 |
| persistence_minus_plugin.ci95_lo | 0.00419466 | 0.00417485 | -1.98104e-05 |
| persistence_minus_plugin.ci95_hi | 0.0114661 | 0.0114533 | -1.2753e-05 |
| persistence_minus_plugin.better_fires | 6/25 | 6/25 |  |
| dilation_1h_minus_plugin.point | 0.872307 | 0.872287 | -1.9541e-05 |
| dilation_1h_minus_plugin.ci95_lo | 0.832785 | 0.832761 | -2.45126e-05 |
| dilation_1h_minus_plugin.ci95_hi | 0.903193 | 0.903178 | -1.52491e-05 |
| dilation_1h_minus_plugin.better_fires | 0/25 | 0/25 |  |
| dilation_2h_minus_plugin.point | 0.862521 | 0.862502 | -1.9541e-05 |
| dilation_2h_minus_plugin.ci95_lo | 0.820311 | 0.82029 | -2.08139e-05 |
| dilation_2h_minus_plugin.ci95_hi | 0.894134 | 0.894108 | -2.52232e-05 |
| dilation_2h_minus_plugin.better_fires | 0/25 | 0/25 |  |
| dilation_4h_minus_plugin.point | 0.598187 | 0.598167 | -1.9541e-05 |
| dilation_4h_minus_plugin.ci95_lo | 0.555403 | 0.555388 | -1.49664e-05 |
| dilation_4h_minus_plugin.ci95_hi | 0.640138 | 0.640128 | -9.69757e-06 |
| dilation_4h_minus_plugin.better_fires | 0/25 | 0/25 |  |
| dilation_8h_minus_plugin.point | 0.284785 | 0.284765 | -1.9541e-05 |
| dilation_8h_minus_plugin.ci95_lo | 0.250159 | 0.25014 | -1.93359e-05 |
| dilation_8h_minus_plugin.ci95_hi | 0.318668 | 0.318654 | -1.46247e-05 |
| dilation_8h_minus_plugin.better_fires | 0/25 | 0/25 |  |
| dilation_best_minus_plugin.point | 0.284785 | 0.284765 | -1.9541e-05 |
| dilation_best_minus_plugin.ci95_lo | 0.250159 | 0.25014 | -1.93359e-05 |
| dilation_best_minus_plugin.ci95_hi | 0.318668 | 0.318654 | -1.46247e-05 |
| dilation_best_minus_plugin.better_fires | 0/25 | 0/25 |  |
| logistic_cf_minus_plugin.point | -0.000261925 | -0.000281466 | -1.9541e-05 |
| logistic_cf_minus_plugin.ci95_lo | -0.000742442 | -0.000769738 | -2.72958e-05 |
| logistic_cf_minus_plugin.ci95_hi | 0.000268094 | 0.000252878 | -1.52167e-05 |
| logistic_cf_minus_plugin.better_fires | 17/25 | 17/25 |  |
| composite_minus_plugin.point | ~~0.00579366~~ (INVALID) | 0.00676151 | 0.000967853 |
| composite_minus_plugin.ci95_lo | ~~0.00295097~~ (INVALID) | 0.00439486 | 0.00144388 |
| composite_minus_plugin.ci95_hi | ~~0.00880204~~ (INVALID) | 0.00906303 | 0.000260988 |
| composite_minus_plugin.better_fires | ~~7/25~~ (INVALID) | 4/25 |  |
| meanfield_nll_minus_plugin.point | 0.00106877 | 0.0010399 | -2.88704e-05 |
| meanfield_nll_minus_plugin.ci95_lo | 0.000451305 | 0.000421255 | -3.00508e-05 |
| meanfield_nll_minus_plugin.ci95_hi | 0.00165139 | 0.00162975 | -2.16421e-05 |
| meanfield_nll_minus_plugin.better_fires | 7/25 | 8/25 |  |
| mcem_minus_plugin.point | 0.00906919 | 0.00906862 | -5.6774e-07 |
| mcem_minus_plugin.ci95_lo | 0.00563041 | 0.00560025 | -3.01542e-05 |
| mcem_minus_plugin.ci95_hi | 0.0123407 | 0.0123657 | 2.50548e-05 |
| mcem_minus_plugin.better_fires | 5/25 | 5/25 |  |
| persistence_minus_mcem.point | -0.00136029 | -0.00137926 | -1.89733e-05 |
| persistence_minus_mcem.ci95_lo | -0.00776293 | -0.00780127 | -3.83487e-05 |
| persistence_minus_mcem.ci95_hi | 0.00543348 | 0.00542312 | -1.03595e-05 |
| persistence_minus_mcem.better_fires | 13/25 | 13/25 |  |
| dilation_1h_minus_mcem.point | 0.863237 | 0.863218 | -1.89733e-05 |
| dilation_1h_minus_mcem.ci95_lo | 0.826359 | 0.82634 | -1.9429e-05 |
| dilation_1h_minus_mcem.ci95_hi | 0.892257 | 0.892249 | -8.301e-06 |
| dilation_1h_minus_mcem.better_fires | 0/25 | 0/25 |  |
| dilation_2h_minus_mcem.point | 0.853452 | 0.853433 | -1.89733e-05 |
| dilation_2h_minus_mcem.ci95_lo | 0.813572 | 0.813551 | -2.11226e-05 |
| dilation_2h_minus_mcem.ci95_hi | 0.883077 | 0.883046 | -3.11249e-05 |
| dilation_2h_minus_mcem.better_fires | 0/25 | 0/25 |  |
| dilation_4h_minus_mcem.point | 0.589117 | 0.589098 | -1.89733e-05 |
| dilation_4h_minus_mcem.ci95_lo | 0.549052 | 0.549051 | -7.23212e-07 |
| dilation_4h_minus_mcem.ci95_hi | 0.628373 | 0.628322 | -5.12834e-05 |
| dilation_4h_minus_mcem.better_fires | 0/25 | 0/25 |  |
| dilation_8h_minus_mcem.point | 0.275716 | 0.275697 | -1.89733e-05 |
| dilation_8h_minus_mcem.ci95_lo | 0.243972 | 0.243975 | 3.07213e-06 |
| dilation_8h_minus_mcem.ci95_hi | 0.306935 | 0.306867 | -6.81717e-05 |
| dilation_8h_minus_mcem.better_fires | 0/25 | 0/25 |  |
| dilation_best_minus_mcem.point | 0.275716 | 0.275697 | -1.89733e-05 |
| dilation_best_minus_mcem.ci95_lo | 0.243972 | 0.243975 | 3.07213e-06 |
| dilation_best_minus_mcem.ci95_hi | 0.306935 | 0.306867 | -6.81717e-05 |
| dilation_best_minus_mcem.better_fires | 0/25 | 0/25 |  |
| logistic_cf_minus_mcem.point | -0.00933112 | -0.00935009 | -1.89733e-05 |
| logistic_cf_minus_mcem.ci95_lo | -0.0127875 | -0.0128365 | -4.89878e-05 |
| logistic_cf_minus_mcem.ci95_hi | -0.00571555 | -0.00571697 | -1.42255e-06 |
| logistic_cf_minus_mcem.better_fires | 20/25 | 20/25 |  |
| plugin_minus_mcem.point | -0.00906919 | -0.00906862 | 5.6774e-07 |
| plugin_minus_mcem.ci95_lo | -0.0123407 | -0.0123657 | -2.50548e-05 |
| plugin_minus_mcem.ci95_hi | -0.00563041 | -0.00560025 | 3.01542e-05 |
| plugin_minus_mcem.better_fires | 20/25 | 20/25 |  |
| composite_minus_mcem.point | ~~-0.00327553~~ (INVALID) | -0.00230711 | 0.000968421 |
| composite_minus_mcem.ci95_lo | ~~-0.0084459~~ (INVALID) | -0.00343788 | 0.00500801 |
| composite_minus_mcem.ci95_hi | ~~0.00183323~~ (INVALID) | -0.00109193 | -0.00292515 |
| composite_minus_mcem.better_fires | ~~14/25~~ (INVALID) | 20/25 |  |
| meanfield_nll_minus_mcem.point | -0.00800042 | -0.00802872 | -2.83027e-05 |
| meanfield_nll_minus_mcem.ci95_lo | -0.0107517 | -0.0108049 | -5.31709e-05 |
| meanfield_nll_minus_mcem.ci95_hi | -0.00514099 | -0.00514251 | -1.5249e-06 |
| meanfield_nll_minus_mcem.better_fires | 21/25 | 20/25 |  |
