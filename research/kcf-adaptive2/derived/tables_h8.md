### DEV, h = 8 h, 28 GOFER fires, 19,981 issue hours, 7 outer folds by fire

| Method | Family | Area at 10% target (km2) | Achieved miss, 95% interval | Fires | Area / FIXED (95%) | Area / PERSIST (95%) | Verdict vs FIXED | Area read at held-out 10% |
|---|---|---|---|---|---|---|---|---|
| FIXED | baseline | 433.0 | 10.0% (6.5 to 14.3) | 28 | 1.000 (1.000 to 1.000) | 0.505 (0.432 to 0.599) | - | 433.4 |
| PERSIST | baseline | 856.5 | 9.3% (7.9 to 10.6) | 28 | 1.978 (1.671 to 2.314) | 1.000 (1.000 to 1.000) | does not help | 829.8 |
| QUANTILE | 3 quantile loss | 379.6 | 10.0% (8.6 to 11.5) | 28 | 0.877 (0.762 to 0.991) | 0.443 (0.418 to 0.471) | helps (material) | 379.0 |
| QUANTILE-own | 3 (own-past features only) | 394.0 | 9.8% (8.3 to 11.4) | 28 | 0.910 (0.796 to 1.029) | 0.460 (0.433 to 0.488) | does not help | 391.2 |
| QUANTILE-fc | 3/4 (issued-forecast features only) | 392.5 | 10.0% (7.7 to 12.8) | 28 | 0.907 (0.835 to 0.988) | 0.458 (0.404 to 0.526) | helps | 392.4 |
| REGIME | 4 forecast regime | 396.7 | 11.2% (7.6 to 15.9) | 28 | 0.916 (0.879 to 0.958) | 0.463 (0.398 to 0.545) | helps | 428.4 |
| REGIME+own | 4 regime + own-past quantile | 393.8 | 9.7% (8.3 to 11.3) | 28 | 0.910 (0.798 to 1.026) | 0.460 (0.433 to 0.488) | does not help | 389.4 |
| EVT | 6 peaks over threshold | 433.3 | 9.7% (8.1 to 11.3) | 28 | 1.001 (0.832 to 1.202) | 0.506 (0.463 to 0.569) | does not help | 427.3 |
| EVT-twin | 6 (constant-scale twin) | 382.1 | 10.9% (9.0 to 13.0) | 28 | 0.882 (0.779 to 0.980) | 0.446 (0.410 to 0.483) | helps (material) | 395.6 |
| PRETRAIN-archive | 5 pretrain: 19 archive fires | 388.5 | 9.9% (8.3 to 11.7) | 28 | 0.897 (0.779 to 1.013) | 0.454 (0.421 to 0.485) | does not help | 386.2 |
| PRETRAIN-sim | 5 pretrain: simulated fires | 437.2 | 10.0% (8.3 to 11.9) | 28 | 1.010 (0.899 to 1.124) | 0.510 (0.475 to 0.550) | does not help | 436.3 |
| PRETRAIN-both | 5 pretrain: both | 395.2 | 10.0% (8.4 to 11.9) | 28 | 0.913 (0.785 to 1.048) | 0.461 (0.437 to 0.487) | does not help | 394.5 |
| M_ref | reference GBM, no tuning | 409.2 | 9.7% (8.2 to 11.3) | 28 | 0.945 (0.810 to 1.086) | 0.478 (0.450 to 0.510) | does not help | 402.5 |
| META | 1 meta-learning, adapted | 429.3 | 9.8% (8.0 to 11.8) | 28 | 0.991 (0.832 to 1.185) | 0.501 (0.463 to 0.540) | does not help | 424.7 |
| META-init | 1 (meta-init, no adaptation) | 419.8 | 9.7% (7.9 to 11.9) | 28 | 0.970 (0.822 to 1.144) | 0.490 (0.456 to 0.524) | does not help | 414.5 |
| META-pooled | 1 (pooled net, no adaptation) | 451.8 | 9.6% (7.9 to 11.5) | 28 | 1.043 (0.902 to 1.215) | 0.527 (0.465 to 0.605) | does not help | 441.4 |
| KALMAN | 2 per-fire Kalman, adapted | 771.9 | 10.0% (8.3 to 12.1) | 28 | 1.783 (1.270 to 2.408) | 0.901 (0.739 to 1.049) | does not help | 774.1 |
| KALMAN-twin | 2 (twin, no adaptation) | 584.0 | 9.9% (8.4 to 11.4) | 28 | 1.349 (0.983 to 1.801) | 0.682 (0.570 to 0.803) | does not help | 580.5 |

### Does adapting to the fire help, against the same model without adaptation (paired by fire)

| Adapted | Twin | Area adapted / twin (95%) | Reading |
|---|---|---|---|
| META | META-init | 1.022 (1.001 to 1.046) | higher |
| META | META-pooled | 0.950 (0.821 to 1.106) | no difference |
| KALMAN | KALMAN-twin | 1.322 (1.161 to 1.555) | higher |
| EVT | EVT-twin | 1.134 (1.021 to 1.292) | higher |
| QUANTILE | QUANTILE-own | 0.963 (0.928 to 1.008) | no difference |
| QUANTILE-own | FIXED | 0.910 (0.796 to 1.029) | no difference |
| QUANTILE | QUANTILE-fc | 0.967 (0.873 to 1.056) | no difference |
| PRETRAIN-archive | M_ref | 0.949 (0.885 to 1.003) | no difference |
| PRETRAIN-sim | M_ref | 1.068 (1.007 to 1.137) | higher |
| PRETRAIN-both | M_ref | 0.966 (0.914 to 1.011) | no difference |
| REGIME+own | QUANTILE-own | 0.999 (0.993 to 1.006) | no difference |
