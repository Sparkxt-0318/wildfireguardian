## Results table

| Set | Method | Area at the calibrated margin (km2) | Achieved miss, 95% interval | Fires | Area read at exactly 10% miss (km2) | Run-days warned |
|---|---|---|---|---|---|---|
| California held-out | FIXED margin | 262.9 | 11.9% (7.6 to 17.1) | 12 | 290.9 | - |
| California held-out | QUANTILE (kcf-adaptive2) | 237.6 | 9.5% (8.0 to 11.1) | 12 | 231.8 | - |
| California held-out | TRACKER (kept version) | 225.6 | 10.2% (8.0 to 12.7) | 12 | 228.5 | 5 of 40 (b) |
| California held-out | TRACKER, hourly update off | 220.6 | 10.3% (7.8 to 13.3) | 12 | 225.8 | 5 of 40 (b) |
| California held-out | TRACKER, forecast input off | 228.9 | 9.8% (7.7 to 12.6) | 12 | 225.8 | 6 of 40 (b) |
| California held-out | TRACKER, archive input off | 225.5 | 10.1% (8.0 to 12.7) | 12 | 227.7 | 4 of 40 (b) |
| Korea, leave-one-fire-out | FIXED margin | 51.5 | 10.4% (2.8 to 19.8) | 12 | 56.4 | - |
| Korea, leave-one-fire-out | QUANTILE (kcf-adaptive2) | 67.7 | 9.9% (3.8 to 17.4) | 12 | 67.5 | - |
| Korea, leave-one-fire-out | TRACKER (kept version) | 83.6 | 10.9% (4.7 to 17.6) | 12 | 94.4 | 4 of 9 (a) |
| Korea, leave-one-fire-out | TRACKER, hourly update off | 67.6 | 12.2% (5.7 to 19.3) | 12 | 72.7 | 3 of 9 (a) |
| Korea, leave-one-fire-out | TRACKER, forecast input off | 82.7 | 9.9% (4.1 to 16.3) | 12 | 82.5 | 6 of 9 (a) |
| Korea, leave-one-fire-out | TRACKER, archive input off | 83.2 | 10.9% (4.8 to 17.6) | 12 | 93.9 | 4 of 9 (a) |
| Korea | Gust rule G (kcf-aloft) | - | - | 12 | - | 4 of 9 (a) |

## Ratios (paired fire bootstrap)

| Set | Comparison | Area ratio at calibrated margins (95%) | Ratio read at exactly 10% miss |
|---|---|---|---|
| California held-out | TRACKER / QUANTILE | 0.950 (0.888 to 0.993) | 0.986 |
| California held-out | TRACKER / FIXED | 0.858 (0.710 to 1.015) | 0.786 |
| California held-out | QUANTILE / FIXED | 0.904 (0.731 to 1.102) | 0.797 |
| California held-out | TRACKER / TRACKER-noupdate | 1.023 (0.960 to 1.079) | 1.012 |
| California held-out | TRACKER / TRACKER-nofc | 0.986 (0.954 to 1.040) | 1.012 |
| California held-out | TRACKER / TRACKER-noarchive | 1.000 (0.999 to 1.001) | 1.004 |
| California held-out | TRACKER-noupdate / FIXED | 0.839 (0.732 to 0.947) | 0.776 |
| California held-out | TRACKER-nofc / FIXED | 0.871 (0.729 to 1.028) | 0.776 |
| California held-out | TRACKER-noarchive / FIXED | 0.858 (0.709 to 1.014) | 0.783 |
| Korea | TRACKER / FIXED | 1.625 (1.044 to 2.092) | 1.672 |
| Korea | QUANTILE / FIXED | 1.315 (0.805 to 1.851) | 1.196 |
| Korea | TRACKER / QUANTILE | 1.236 (1.052 to 1.574) | 1.398 |
| Korea | TRACKER-noupdate / FIXED | 1.313 (0.998 to 1.602) | 1.289 |
| Korea | TRACKER-nofc / FIXED | 1.606 (1.135 to 1.993) | 1.462 |
| Korea | TRACKER-noarchive / FIXED | 1.617 (1.039 to 2.082) | 1.664 |
| Korea | TRACKER / TRACKER-noupdate | 1.238 (1.023 to 1.331) | 1.297 |
| Korea | TRACKER / TRACKER-nofc | 1.011 (0.876 to 1.095) | 1.144 |

## Target A detail

| Method | Warned of 9 | Onset days warned | Warned without 25 March | Alarms on the no-run fire-days | Model alarm point-days in the burden set (range over left-out fires) | G alarm point-days |
|---|---|---|---|---|---|---|
| TRACKER (kept version) | 4 | 2 of 6 | 3 of 8 | 11 of 34 | 169 to 169 | 169 |
| TRACKER, hourly update off | 3 | 2 of 6 | 2 of 8 | 3 of 34 | 169 to 169 | 169 |
| TRACKER, forecast input off | 6 | 3 of 6 | 6 of 8 | 29 of 34 | 0 to 0 | 169 |
| TRACKER, archive input off | 4 | 2 of 6 | 3 of 8 | 11 of 34 | 169 to 169 | 169 |

### Every run fire-day (TRACKER; noupdate; nofc)

| Fire | KST day | First run hour | Onset | p at that hour | threshold c | Warned | p (update off) | Warned (update off) | Warned (forecast off) | G (kcf-aloft) |
|---|---|---|---|---|---|---|---|---|---|---|
| KFS_01 | 2025-03-22 | 22 | yes | 0.024 | 0.132 | no | 0.016 | no | no | no |
| KFS_01 | 2025-03-23 | 00 | no | 0.022 | 0.132 | no | 0.011 | no | yes | no |
| KFS_01 | 2025-03-25 | 10 | yes | 0.215 | 0.132 | yes | 0.342 | yes | no | yes |
| KFS_01 | 2025-03-26 | 00 | no | 0.401 | 0.132 | yes | 0.077 | no | yes | no |
| KFS_02 | 2022-03-04 | 12 | yes | 0.079 | 0.158 | no | 0.105 | no | no | yes |
| KFS_02 | 2022-03-05 | 00 | no | 0.635 | 0.158 | yes | 0.391 | yes | yes | yes |
| KFS_02 | 2022-03-10 | 05 | yes | 0.040 | 0.158 | no | 0.015 | no | yes | no |
| KFS_03 | 2022-03-05 | 08 | yes | 0.347 | 0.151 | yes | 0.194 | yes | yes | yes |
| KFS_04 | 2025-03-22 | 18 | yes | 0.134 | 0.167 | no | 0.067 | no | yes | no |

## Korea, secondary rows

| Method | Row | Area (km2) | Miss, 95% interval | Area read at 10% |
|---|---|---|---|---|
| FIXED margin | California-fitted, kappa leave-one-fire-out | 51.5 | 10.4% (2.8 to 19.8) | 56.4 |
| FIXED margin | California-fitted and calibrated | 90.3 | 4.5% (0.5 to 10.4) | 52.1 |
| QUANTILE (kcf-adaptive2) | California-fitted, kappa leave-one-fire-out | 60.0 | 10.6% (4.7 to 16.8) | 63.2 |
| QUANTILE (kcf-adaptive2) | California-fitted and calibrated | 141.7 | 3.0% (0.7 to 5.9) | 62.8 |
| TRACKER (kept version) | California-fitted, kappa leave-one-fire-out | 68.4 | 9.8% (4.7 to 15.9) | 68.2 |
| TRACKER (kept version) | California-fitted and calibrated | 138.4 | 2.3% (0.2 to 5.9) | 69.0 |
| TRACKER, hourly update off | California-fitted, kappa leave-one-fire-out | 61.9 | 11.1% (4.9 to 18.3) | 65.2 |
| TRACKER, hourly update off | California-fitted and calibrated | 120.2 | 2.6% (0.3 to 6.6) | 64.1 |
| TRACKER, forecast input off | California-fitted, kappa leave-one-fire-out | 76.7 | 11.5% (3.5 to 20.9) | 81.0 |
| TRACKER, forecast input off | California-fitted and calibrated | 110.4 | 5.2% (1.3 to 10.0) | 81.2 |
| TRACKER, archive input off | California-fitted, kappa leave-one-fire-out | 67.4 | 10.3% (4.9 to 16.5) | 68.4 |
| TRACKER, archive input off | California-fitted and calibrated | 140.8 | 2.3% (0.2 to 5.9) | 70.1 |

## 25 March 2025, KFS_01 (model fitted without KFS_01)

| KST | reach 5 h (km) | fc gust | fc 850 hPa wind | fc RH min | growth last hour (km) | enter | p before update | p after | c | alarm | m quiet | m run | TRACKER margin | FIXED | QUANTILE | update off | forecast off |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 09 | 2.2 | 23.0 | 32.3 | 16 | 0.00 | 0.132 | 0.221 | 0.172 | 0.132 | yes | 2.6 | 9.7 | 3.5 h | 1.6 **M** | 3.0 h | 4.0 h | 2.5 h |
| 10 | 4.9 | 23.0 | 32.3 | 16 | 0.00 | 0.146 | 0.272 | 0.215 | 0.132 | yes | 2.6 | 9.7 | 3.8 **M** | 1.6 **M** | 3.0 **M** | 4.5 **M** | 2.5 **M** |
| 11 | 6.6 | 23.0 | 32.3 | 16 | 0.00 | 0.159 | 0.312 | 0.250 | 0.132 | yes | 2.6 | 9.8 | 4.0 **M** | 1.6 **M** | 3.1 **M** | 4.9 **M** | 2.5 **M** |
| 12 | 12.4 | 23.0 | 32.3 | 16 | 2.25 | 0.170 | 0.344 | 0.473 | 0.132 | yes | 3.3 | 10.2 | 6.0 **M** | 1.6 **M** | 4.4 **M** | 5.8 **M** | 3.3 **M** |
| 13 | 23.9 | 23.0 | 32.3 | 16 | 2.19 | 0.178 | 0.501 | 0.632 | 0.132 | yes | 3.3 | 10.3 | 7.0 **M** | 1.6 **M** | 4.5 **M** | 6.0 **M** | 3.5 **M** |
| 14 | 34.7 | 23.8 | 33.2 | 18 | 0.00 | 0.188 | 0.611 | 0.535 | 0.132 | yes | 3.0 | 10.0 | 6.1 **M** | 1.6 **M** | 4.0 **M** | 5.9 **M** | 3.1 **M** |
| 15 | 32.9 | 23.8 | 33.2 | 21 | 4.14 | 0.156 | 0.527 | 0.656 | 0.132 | yes | 3.6 | 11.0 | 7.7 **M** | 1.6 **M** | 6.4 **M** | 6.6 **M** | 3.8 **M** |
| 16 | 40.1 | 23.8 | 33.2 | 27 | 6.56 | 0.106 | 0.587 | 0.709 | 0.132 | yes | 3.6 | 12.1 | 8.8 **M** | 1.6 **M** | 6.7 **M** | 6.9 **M** | 4.2 **M** |
| 17 | 38.6 | 21.9 | 28.1 | 37 | 9.38 | 0.038 | 0.590 | 0.712 | 0.132 | yes | 3.3 | 14.0 | 10.0 **M** | 1.6 **M** | 6.7 **M** | 6.9 **M** | 4.6 **M** |
| 18 | 27.3 | 16.7 | 26.8 | 37 | 12.65 | 0.013 | 0.554 | 0.680 | 0.132 | yes | 3.3 | 11.4 | 8.0 **M** | 1.6 **M** | 6.6 **M** | 5.3 **M** | 4.5 **M** |
| 19 | 20.3 | 16.1 | 26.8 | 37 | 10.82 | 0.011 | 0.524 | 0.653 | 0.132 | yes | 3.3 | 11.4 | 7.8 **M** | 1.6 **M** | 6.6 **M** | 4.8 **M** | 4.9 **M** |
| 20 | 15.7 | 14.1 | 24.8 | 36 | 5.21 | 0.007 | 0.492 | 0.624 | 0.132 | yes | 3.1 | 10.5 | 7.1 **M** | 1.6 **M** | 6.0 **M** | 4.1 **M** | 5.0 **M** |

| Method | Hours missed of 12 (09 to 20 KST) | Largest margin (km) | Mean flagged area (km2) |
|---|---|---|---|
| FIXED margin | 12 | 1.6 | 332 |
| QUANTILE (kcf-adaptive2) | 11 | 6.7 | 1197 |
| TRACKER (kept version) | 11 | 10.0 | 1605 |
| TRACKER, hourly update off | 11 | 6.9 | 1261 |
| TRACKER, forecast input off | 11 | 5.0 | 828 |
| TRACKER, archive input off | 11 | 9.9 | 1585 |
