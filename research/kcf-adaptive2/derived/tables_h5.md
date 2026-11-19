### DEV, h = 5 h, 28 GOFER fires, 20,065 issue hours, 7 outer folds by fire

| Method | Family | Area at 10% target (km2) | Achieved miss, 95% interval | Fires | Area / FIXED (95%) | Area / PERSIST (95%) | Verdict vs FIXED | Area read at held-out 10% |
|---|---|---|---|---|---|---|---|---|
| FIXED | baseline | 328.9 | 9.8% (6.9 to 13.3) | 28 | 1.000 (1.000 to 1.000) | 0.681 (0.592 to 0.796) | - | 326.9 |
| PERSIST | baseline | 483.1 | 9.9% (8.8 to 11.2) | 28 | 1.469 (1.256 to 1.690) | 1.000 (1.000 to 1.000) | does not help | 481.2 |
| QUANTILE | 3 quantile loss | 278.4 | 9.7% (8.6 to 11.1) | 28 | 0.846 (0.737 to 0.946) | 0.576 (0.549 to 0.608) | helps (material) | 274.6 |
| QUANTILE-own | 3 (own-past features only) | 283.2 | 10.0% (8.8 to 11.5) | 28 | 0.861 (0.748 to 0.970) | 0.586 (0.559 to 0.613) | helps (material) | 283.3 |
| QUANTILE-fc | 3/4 (issued-forecast features only) | 302.2 | 10.0% (7.8 to 12.7) | 28 | 0.919 (0.857 to 0.990) | 0.626 (0.556 to 0.718) | helps | 302.7 |
| REGIME | 4 forecast regime | 312.1 | 10.9% (8.0 to 14.4) | 28 | 0.949 (0.923 to 0.976) | 0.646 (0.567 to 0.749) | helps | 328.7 |
| REGIME+own | 4 regime + own-past quantile | 282.9 | 10.1% (8.8 to 11.7) | 28 | 0.860 (0.753 to 0.963) | 0.586 (0.558 to 0.614) | helps (material) | 285.0 |
| EVT | 6 peaks over threshold | 288.2 | 10.0% (8.7 to 11.5) | 28 | 0.876 (0.754 to 0.999) | 0.597 (0.558 to 0.645) | helps (material) | 287.6 |
| EVT-twin | 6 (constant-scale twin) | 278.4 | 10.1% (8.9 to 11.6) | 28 | 0.846 (0.739 to 0.945) | 0.576 (0.545 to 0.612) | helps (material) | 279.5 |
| PRETRAIN-archive | 5 pretrain: 19 archive fires | 289.3 | 9.9% (8.7 to 11.2) | 28 | 0.880 (0.765 to 0.985) | 0.599 (0.570 to 0.628) | helps (material) | 287.3 |
| PRETRAIN-sim | 5 pretrain: simulated fires | 297.2 | 10.0% (8.6 to 11.5) | 28 | 0.904 (0.802 to 0.999) | 0.615 (0.581 to 0.653) | helps | 296.7 |
| PRETRAIN-both | 5 pretrain: both | 287.0 | 10.0% (8.7 to 11.4) | 28 | 0.873 (0.755 to 0.986) | 0.594 (0.569 to 0.621) | helps (material) | 287.5 |
| M_ref | reference GBM, no tuning | 284.9 | 9.8% (8.6 to 11.2) | 28 | 0.866 (0.745 to 0.976) | 0.590 (0.556 to 0.631) | helps (material) | 281.8 |
| META | 1 meta-learning, adapted | 318.7 | 10.1% (8.5 to 12.0) | 28 | 0.969 (0.820 to 1.152) | 0.660 (0.602 to 0.725) | does not help | 320.4 |
| META-init | 1 (meta-init, no adaptation) | 314.2 | 9.9% (8.4 to 11.7) | 28 | 0.955 (0.810 to 1.116) | 0.650 (0.600 to 0.710) | does not help | 312.9 |
| META-pooled | 1 (pooled net, no adaptation) | 359.4 | 9.6% (8.1 to 11.3) | 28 | 1.093 (0.877 to 1.352) | 0.744 (0.645 to 0.855) | does not help | 350.7 |
| KALMAN | 2 per-fire Kalman, adapted | 493.1 | 9.8% (8.6 to 11.1) | 28 | 1.499 (1.085 to 2.004) | 1.021 (0.836 to 1.212) | does not help | 489.1 |
| KALMAN-twin | 2 (twin, no adaptation) | 415.4 | 10.0% (8.7 to 11.3) | 28 | 1.263 (0.935 to 1.677) | 0.860 (0.720 to 1.030) | does not help | 414.7 |

### Does adapting to the fire help, against the same model without adaptation (paired by fire)

| Adapted | Twin | Area adapted / twin (95%) | Reading |
|---|---|---|---|
| META | META-init | 1.014 (0.969 to 1.057) | no difference |
| META | META-pooled | 0.887 (0.816 to 0.960) | lower |
| KALMAN | KALMAN-twin | 1.187 (1.036 to 1.419) | higher |
| EVT | EVT-twin | 1.035 (0.996 to 1.086) | no difference |
| QUANTILE | QUANTILE-own | 0.983 (0.947 to 1.026) | no difference |
| QUANTILE-own | FIXED | 0.861 (0.748 to 0.970) | lower |
| QUANTILE | QUANTILE-fc | 0.921 (0.828 to 1.006) | no difference |
| PRETRAIN-archive | M_ref | 1.015 (0.967 to 1.060) | no difference |
| PRETRAIN-sim | M_ref | 1.043 (0.988 to 1.101) | no difference |
| PRETRAIN-both | M_ref | 1.007 (0.957 to 1.056) | no difference |
| REGIME+own | QUANTILE-own | 0.999 (0.988 to 1.011) | no difference |
