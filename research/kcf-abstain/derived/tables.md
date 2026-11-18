## A. Calibration, leave-one-fire-out (beta = 0.05)

| arm | h | n fires | hours | abstention (fire-weighted, 95% CI) | miss among kept (95% CI) | miss with no abstention (95% CI) | pooled: abstained hours / miss rate among them | AUROC (95% CI) | Delta miss (95% CI) | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **primary** | 5 h | 28 | 20065 | 4.9% (0.3-20.4) | 4.9% (0.3-20.3) | 6.0% (0.5-21.9) | 732 / 18.7% | 0.84 (0.79-0.88) | -1.13 pts (-2.35 to -0.32) | separates |
| **primary** | 8 h | 28 | 19981 | 4.9% (0.3-20.3) | 5.2% (0.4-20.8) | 6.4% (0.7-22.5) | 725 / 20.4% | 0.86 (0.81-0.89) | -1.26 pts (-2.52 to -0.41) | separates |
| S1 two-sided | 5 h | 28 | 20065 | 5.0% (0.3-20.4) | 5.1% (0.3-20.7) | 6.0% (0.5-21.9) | 1001 / 8.1% | 0.73 (0.66-0.80) | -0.84 pts (-1.99 to -0.10) | separates |
| S1 two-sided | 8 h | 28 | 19981 | 4.9% (0.3-20.4) | 5.6% (0.4-21.4) | 6.4% (0.7-22.5) | 992 / 8.7% | 0.75 (0.69-0.82) | -0.83 pts (-2.05 to -0.06) | separates |
| S2 GFS-only (11 fires) | 5 h | 11 | 9923 | 4.1% (0.0-34.6) | 2.2% (0.0-31.9) | 2.7% (0.0-32.7) | 394 / 17.5% | 0.80 (0.74-0.85) | -0.54 pts (-1.01 to -0.15) | separates |
| S2 GFS-only (11 fires) | 8 h | 11 | 9890 | 4.0% (0.0-34.5) | 2.0% (0.0-31.7) | 2.6% (0.0-32.6) | 384 / 18.2% | 0.80 (0.74-0.86) | -0.60 pts (-1.13 to -0.15) | separates |

Fires with every hour abstained at beta = 0.05 (left out of the miss-among-kept mean): {'primary': {5: [], 8: []}, 'S1_two_sided': {5: [], 8: []}, 'S2_gfs_only': {5: [], 8: []}}

Abstained calibration hours by the predictor that gave the minimum tail probability (primary): {'prior3_km': 121, 'rhmin_pct': 208, 'gust_ms': 124, 'hdw': 235, 'w850_ms': 44}

## B. Risk-coverage points (primary, fire-weighted, leave-one-fire-out)

| beta | coverage 5 h | miss among kept 5 h | coverage 8 h | miss among kept 8 h |
|---|---|---|---|---|
| 0.00 | 100.0% | 6.0% | 100.0% | 6.4% |
| 0.01 | 99.0% | 5.4% | 99.0% | 5.8% |
| 0.02 | 98.1% | 5.2% | 98.1% | 5.7% |
| 0.05 | 95.1% | 4.9% | 95.1% | 5.2% |
| 0.10 | 90.1% | 4.0% | 90.1% | 4.4% |
| 0.20 | 79.9% | 2.7% | 79.9% | 2.6% |
| 0.30 | 70.0% | 1.7% | 70.1% | 1.8% |
| 0.50 | 50.1% | 0.6% | 50.2% | 0.5% |

No abstention (= random abstention): 5 h 6.0%, 8 h 6.4%.

## C. Thresholds for test fires

{'primary': 0.010728508563521567, 'S1_two_sided': 0.010806202902409448, 'S2_gfs_only': 0.00913473228596639}

## D. Test groups (counts; rates only where >= 10 fires)

| group | h | fires | scored hours | abstained | margin missed | abstained & missed | abstained & held | kept & missed | kept & held | rates |
|---|---|---|---|---|---|---|---|---|---|---|
| US_choi_19 | 5 h | 19 | 29470 | 906 | 200 | 56 | 850 | 144 | 28420 | abstention 2.9% (0.0-22.5); miss among kept 0.5% (0.0-18.6); no abstention 0.7% (0.0-18.8) |
| US_choi_19 | 8 h | 19 | 29413 | 900 | 90 | 33 | 867 | 57 | 28456 | abstention 2.9% (0.0-22.5); miss among kept 0.2% (0.0-18.0); no abstention 0.3% (0.0-18.2) |
| US2024 | 5 h | 6 | 8444 | 76 | 59 | 6 | 70 | 53 | 8315 |  |
| US2024 | 8 h | 6 | 8426 | 76 | 24 | 5 | 71 | 19 | 8331 |  |
| Korea_choi | 5 h | 12 | 756 | 330 | 51 | 40 | 290 | 11 | 415 |  |
| Korea_choi | 8 h | 11 | 720 | 321 | 46 | 42 | 279 | 4 | 395 |  |
| Korea_25March_DET | 5 h | 1 | 23 | 21 | 13 | 13 | 8 | 0 | 2 |  |
| Korea_25March_DET | 8 h | 1 | 20 | 18 | 12 | 12 | 6 | 0 | 2 |  |

## E. Every test fire (counts)

| fire | product | forecast | issue hours | not scored | 5 h: scored / abstained / missed / abstained & missed | 8 h: scored / abstained / missed / abstained & missed |
|---|---|---|---|---|---|---|
| KFS_01 | CHOI | GFS | 102 | 3 | 99 / 72 / 27 / 21 | 96 / 69 / 24 / 23 |
| KFS_01 | DET | GFS | 24 | 0 | 23 / 21 / 13 / 13 | 20 / 18 / 12 / 12 |
| KFS_02 | CHOI | GFS | 189 | 3 | 186 / 39 / 14 / 9 | 183 / 39 / 10 / 7 |
| KFS_03 | CHOI | GFS | 69 | 3 | 66 / 24 / 5 / 5 | 63 / 24 / 8 / 8 |
| KFS_04 | CHOI | GFS | 169 | 3 | 166 / 103 / 5 / 5 | 163 / 103 / 4 / 4 |
| KFS_05 | CHOI | GFS | 34 | 3 | 31 / 0 / 0 / 0 | 28 / 0 / 0 / 0 |
| KFS_06 | CHOI | GFS | 99 | 3 | 96 / 78 / 0 / 0 | 93 / 75 / 0 / 0 |
| KFS_07 | CHOI | GFS | 21 | 3 | 18 / 8 / 0 / 0 | 15 / 8 / 0 / 0 |
| KFS_11 | CHOI | GFS | 42 | 3 | 39 / 0 / 0 / 0 | 36 / 0 / 0 / 0 |
| KFS_12 | CHOI | GFS | 7 | 3 | 4 / 4 / 0 / 0 | 1 / 1 / 0 / 0 |
| KFS_13 | CHOI | GFS | 38 | 3 | 35 / 0 / 0 / 0 | 32 / 0 / 0 / 0 |
| KFS_15 | CHOI | GFS | 6 | 3 | 3 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| KFS_17 | CHOI | GFS | 16 | 3 | 13 / 2 / 0 / 0 | 10 / 2 / 0 / 0 |
| CO-ARF-000636_CameronPeak | CHOI | HRRR | 1721 | 7 | 1714 / 273 / 39 / 14 | 1711 / 270 / 20 / 12 |
| ID-BOF-000683_Wapiti_Wapiti | CHOI | GFS | 1713 | 3 | 1710 / 18 / 12 / 0 | 1707 / 18 / 7 / 0 |
| ID-BOF-000904_Goat | CHOI | GFS | 1592 | 3 | 1589 / 6 / 9 / 0 | 1586 / 6 / 1 / 0 |
| ID-BOF-001080_Lava | CHOI | GFS | 1155 | 3 | 1152 / 0 / 15 / 0 | 1149 / 0 / 6 / 0 |
| ID-SCF-022105_Moose | CHOI | GFS | 2145 | 3 | 2142 / 9 / 9 / 5 | 2139 / 9 / 3 / 0 |
| ID-SCF-240202_RedRock | CHOI | GFS | 1121 | 3 | 1118 / 28 / 8 / 6 | 1115 / 28 / 6 / 5 |
| MT-BDF-006269_AlderCreek | CHOI | GFS | 2004 | 3 | 2001 / 11 / 5 / 0 | 1998 / 11 / 0 / 0 |
| MT-BDF-006272_TrailCreek | CHOI | GFS | 2067 | 3 | 2064 / 12 / 0 / 0 | 2061 / 12 / 0 / 0 |
| MT-LNF-000893_WestLolo | CHOI | GFS | 946 | 3 | 943 / 2 / 6 / 0 | 940 / 2 / 6 / 0 |
| NM-SNF-000027_HermitsPeak | CHOI | GFS | 1785 | 3 | 1782 / 335 / 38 / 31 | 1779 / 335 / 21 / 16 |
| OR-UMF-000659_GreenRidge | CHOI | GFS | 1604 | 3 | 1601 / 16 / 4 / 0 | 1598 / 16 / 0 / 0 |
| OR-UMP-000373_RoughPatchCpx | CHOI | GFS | 1206 | 3 | 1203 / 0 / 0 / 0 | 1200 / 0 / 0 / 0 |
| OR-UPF-000265_Jack | CHOI | GFS | 1776 | 3 | 1773 / 0 / 3 / 0 | 1770 / 0 / 0 / 0 |
| OR-UPF-000450_DevilsKnob | CHOI | GFS | 1254 | 3 | 1251 / 0 / 2 / 0 | 1248 / 0 / 2 / 0 |
| OR-WIF-220180_CedarCreek | CHOI | GFS | 1855 | 3 | 1852 / 0 / 21 / 0 | 1849 / 0 / 6 / 0 |
| UT-ASF-100340_EastFork | CHOI | HRRR | 1426 | 7 | 1419 / 172 / 6 / 0 | 1416 / 169 / 8 / 0 |
| WA-OWF-000453_SchneiderSprings | CHOI | GFS | 1284 | 3 | 1281 / 0 / 8 / 0 | 1278 / 0 / 0 / 0 |
| WA-SES-000173_Pioneer | CHOI | GFS | 1525 | 3 | 1522 / 0 / 0 / 0 | 1519 / 0 / 0 / 0 |
| WY-BTF-002416_FishCreek | CHOI | GFS | 1356 | 3 | 1353 / 24 / 15 / 0 | 1350 / 24 / 4 / 0 |

NOT TESTED (no eligible issue hour): {'KFS_09': 'no eligible issue hour (arrival span 2022-04-10 18:00:00 .. 2022-04-10 18:00:00 UTC is shorter than 5 h + 1)', 'KFS_14': 'no eligible issue hour (arrival span 2022-05-28 18:00:00 .. 2022-05-28 18:00:00 UTC is shorter than 5 h + 1)', 'KFS_16': 'no eligible issue hour (arrival span 2023-04-03 05:00:00 .. 2023-04-03 05:00:00 UTC is shorter than 5 h + 1)'}

## F. 25 March 2025, 10:00-20:00 KST (DET product; GFS as issued)

| KST | cycle (UTC) | gust m/s | 850 hPa m/s | min RH % | HDW | prior-3 h km | score s | abstain | lowest-p predictor | 5 h reach km (R 3.75) | 5 h | 8 h reach km (R 5.03) | 8 h |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10:00 | 03-24 18 | 23.0 | 32.3 | 16 | 223 | 0.00 | 0.0000 | **yes** | w850_ms | 4.9 | **missed** | 23.9 | **missed** |
| 11:00 | 03-24 18 | 23.0 | 32.3 | 16 | 223 | 0.00 | 0.0000 | **yes** | w850_ms | 6.6 | **missed** | 34.7 | **missed** |
| 12:00 | 03-24 18 | 23.0 | 32.3 | 16 | 223 | 2.25 | 0.0000 | **yes** | w850_ms | 12.4 | **missed** | 34.9 | **missed** |
| 13:00 | 03-24 18 | 23.0 | 32.3 | 16 | 223 | 2.25 | 0.0000 | **yes** | w850_ms | 23.9 | **missed** | 44.0 | **missed** |
| 14:00 | 03-25 00 | 23.8 | 33.2 | 18 | 229 | 2.25 | 0.0000 | **yes** | w850_ms | 34.7 | **missed** | 50.3 | **missed** |
| 15:00 | 03-25 00 | 23.8 | 33.2 | 21 | 226 | 4.89 | 0.0000 | **yes** | w850_ms | 32.9 | **missed** | 46.6 | **missed** |
| 16:00 | 03-25 00 | 23.8 | 33.2 | 27 | 196 | 6.56 | 0.0000 | **yes** | w850_ms | 40.1 | **missed** | 46.4 | **missed** |
| 17:00 | 03-25 00 | 21.9 | 28.1 | 37 | 112 | 11.92 | 0.0005 | **yes** | prior3_km | 38.6 | **missed** | 38.6 | **missed** |
| 18:00 | 03-25 00 | 16.7 | 26.8 | 37 | 58 | 22.33 | 0.0000 | **yes** | prior3_km | 27.3 | **missed** | 27.3 | **missed** |
| 19:00 | 03-25 00 | 16.1 | 26.8 | 37 | 53 | 32.26 | 0.0000 | **yes** | prior3_km | 20.3 | **missed** | 20.3 | **missed** |
| 20:00 | 03-25 06 | 14.1 | 24.8 | 36 | 45 | 23.47 | 0.0000 | **yes** | prior3_km | 15.7 | **missed** | n/a | not scored |

Threshold tau = 0.01073.

Secondary arms on the same hours (abstain flags): S1 two-sided [(10, True), (11, True), (12, True), (13, True), (14, True), (15, True), (16, True), (17, True), (18, True), (19, True), (20, True)] ; S2 GFS-only [(10, True), (11, True), (12, True), (13, True), (14, True), (15, True), (16, True), (17, True), (18, True), (19, True), (20, True)]

All 24 hours (00-23 KST): [(0, 0.0162, False), (1, 0.012, False), (2, 0.0086, True), (3, 0.0077, True), (4, 0.0077, True), (5, 0.0077, True), (6, 0.0057, True), (7, 0.0045, True), (8, 0.0037, True), (9, 0.0, True), (10, 0.0, True), (11, 0.0, True), (12, 0.0, True), (13, 0.0, True), (14, 0.0, True), (15, 0.0, True), (16, 0.0, True), (17, 0.0005, True), (18, 0.0, True), (19, 0.0, True), (20, 0.0, True), (21, 0.0, True), (22, 0.0, True), (23, 0.0, True)]

## G. S3 product cross-check (same fire, same issue hours, frozen R)

h = 5: n = 10 fires; miss rate GOFER 2.8% (0.0-35.0); Choi raster 2.4% (0.0-34.4)
  Dixie: hours 1372, miss GOFER 8.9%, Choi 8.5%, median reach GOFER 1.35 km, Choi 1.55 km
  River Complex: hours 1314, miss GOFER 0.8%, Choi 1.4%, median reach GOFER 0.00 km, Choi 0.53 km
  Antelope: hours 901, miss GOFER 3.1%, Choi 2.7%, median reach GOFER 0.00 km, Choi 0.38 km
  August Complex: hours 1412, miss GOFER 7.4%, Choi 4.6%, median reach GOFER 0.84 km, Choi 0.84 km
  North Complex: hours 1070, miss GOFER 2.8%, Choi 2.1%, median reach GOFER 0.00 km, Choi 0.53 km
  Monument: hours 1136, miss GOFER 0.4%, Choi 0.4%, median reach GOFER 0.00 km, Choi 0.53 km
  Creek: hours 1479, miss GOFER 2.4%, Choi 2.0%, median reach GOFER 0.00 km, Choi 0.53 km
  SQF Complex: hours 1088, miss GOFER 1.4%, Choi 1.4%, median reach GOFER 0.00 km, Choi 0.53 km
  McCash: hours 1287, miss GOFER 0.4%, Choi 0.4%, median reach GOFER 0.00 km, Choi 0.38 km
  Red Salmon Complex: hours 1768, miss GOFER 0.2%, Choi 0.3%, median reach GOFER 0.00 km, Choi 0.38 km
h = 8: n = 10 fires; miss rate GOFER 2.8% (0.0-35.0); Choi raster 1.7% (0.0-33.5)
  Dixie: hours 1369, miss GOFER 9.9%, Choi 5.4%, median reach GOFER 1.91 km, Choi 2.02 km
  River Complex: hours 1311, miss GOFER 1.1%, Choi 0.5%, median reach GOFER 0.00 km, Choi 0.75 km
  Antelope: hours 898, miss GOFER 3.6%, Choi 3.0%, median reach GOFER 0.00 km, Choi 0.53 km
  August Complex: hours 1409, miss GOFER 6.2%, Choi 4.4%, median reach GOFER 1.50 km, Choi 1.12 km
  North Complex: hours 1067, miss GOFER 2.7%, Choi 1.4%, median reach GOFER 0.00 km, Choi 0.75 km
  Monument: hours 1133, miss GOFER 0.2%, Choi 0.4%, median reach GOFER 0.53 km, Choi 0.75 km
  Creek: hours 1476, miss GOFER 2.2%, Choi 1.2%, median reach GOFER 0.38 km, Choi 0.75 km
  SQF Complex: hours 1085, miss GOFER 1.0%, Choi 0.4%, median reach GOFER 0.38 km, Choi 0.84 km
  McCash: hours 1284, miss GOFER 0.6%, Choi 0.5%, median reach GOFER 0.00 km, Choi 0.53 km
  Red Salmon Complex: hours 1765, miss GOFER 0.1%, Choi 0.0%, median reach GOFER 0.00 km, Choi 0.53 km

## H. Tail (GEV on 28 per-fire maximum 5 h reaches)

{
 "gev_mle": {
  "mu": 7.813175835722584,
  "sigma": 2.9646302891648197,
  "xi": -0.07025743206353459,
  "loglik": -73.58961987585502,
  "xi_ci95_profile": [
   -0.34,
   0.25
  ],
  "upper_endpoint_km": 50.00985456550979
 },
 "p40": {
  "mle": 1.2772380930670124e-09,
  "ci95_profile": [
   0.0,
   0.006210225215027265
  ],
  "ci95_parametric_bootstrap": [
   0.0,
   0.0026455534175972746
  ],
  "bootstrap_share_exactly_zero": 0.5175,
  "bootstrap": {
   "resamples": 2000,
   "seed": 20261118
  }
 },
 "T40_fires": {
  "mle": 782939379.4532977,
  "ci95_profile": [
   161.02475600727624,
   null
  ]
 },
 "fires_needed_to_bound": {
  "at_mle": 2345476766,
  "at_ci_upper_p": 481,
  "at_ci_lower_p": null,
  "rule": "n = ceil(ln 0.05 / ln(1 - p40)): fires with no exceedance needed for a one-sided 95% upper bound at p40 (about 3 / p40)"
 },
 "trust": {
  "T40_interval_finite": false,
  "verdict": "fit cannot bound the 40 km return period with 28 fires (profile interval for p40 reaches 0)"
 }
}
largest: 17.33538649698933 ratio: 2.307418989876394

## I. Calibration hours not scored

{'issue_hours': 20161, 'scored': 20065, 'prior3_undefined': 84, 'forecast_missing': 12, 'by_note': {'ok': 20149, 'missing:gust,w850,rh,hdw': 12}}

## J. Korean fires day by day (KST days; Choi rasters; 5 h; counts)

| fire | KST day | scored hours | abstained | 5 h misses | misses abstained | max 5 h reach km | max forecast 850 hPa m/s | max forecast gust m/s |
|---|---|---|---|---|---|---|---|---|
| KFS_01 | 2025-03-22 | 2 | 2 | 2 | 2 | 7.6 | 20.0 | 12.3 |
| KFS_01 | 2025-03-23 | 24 | 10 | 9 | 4 | 9.3 | 18.8 | 10.1 |
| KFS_01 | 2025-03-24 | 24 | 18 | 0 | 0 | 1.2 | 21.6 | 16.7 |
| KFS_01 | 2025-03-25 | 24 | 22 | 11 | 10 | 45.0 | 33.2 | 23.8 |
| KFS_01 | 2025-03-26 | 24 | 19 | 5 | 5 | 44.2 | 26.1 | 16.3 |
| KFS_01 | 2025-03-27 | 1 | 1 | 0 | 0 | 0.5 | 26.1 | 16.1 |
| KFS_02 | 2022-03-04 | 9 | 9 | 4 | 4 | 9.4 | 33.3 | 25.6 |
| KFS_02 | 2022-03-05 | 24 | 24 | 5 | 5 | 7.2 | 32.8 | 25.6 |
| KFS_02 | 2022-03-06 | 24 | 6 | 0 | 0 | 1.7 | 21.0 | 14.0 |
| KFS_02 | 2022-03-07 | 24 | 0 | 0 | 0 | 2.5 | 10.7 | 7.3 |
| KFS_02 | 2022-03-08 | 24 | 0 | 0 | 0 | 0.8 | 9.1 | 5.7 |
| KFS_02 | 2022-03-09 | 24 | 0 | 0 | 0 | 0.8 | 8.3 | 9.6 |
| KFS_02 | 2022-03-10 | 24 | 0 | 5 | 0 | 4.8 | 10.7 | 9.6 |
| KFS_02 | 2022-03-11 | 24 | 0 | 0 | 0 | 1.1 | 12.2 | 7.9 |
| KFS_02 | 2022-03-12 | 9 | 0 | 0 | 0 | 0.8 | 11.7 | 6.6 |
| KFS_03 | 2022-03-05 | 19 | 19 | 5 | 5 | 5.7 | 29.9 | 21.8 |
| KFS_03 | 2022-03-06 | 24 | 5 | 0 | 0 | 1.1 | 21.4 | 14.0 |
| KFS_03 | 2022-03-07 | 23 | 0 | 0 | 0 | 0.4 | 11.3 | 5.9 |
| KFS_04 | 2025-03-22 | 23 | 23 | 5 | 5 | 5.2 | 21.8 | 12.9 |
| KFS_04 | 2025-03-23 | 24 | 10 | 0 | 0 | 2.0 | 19.0 | 7.6 |
| KFS_04 | 2025-03-24 | 24 | 22 | 0 | 0 | 0.8 | 23.5 | 17.4 |
| KFS_04 | 2025-03-25 | 24 | 24 | 0 | 0 | 1.2 | 30.2 | 19.3 |
| KFS_04 | 2025-03-26 | 24 | 17 | 0 | 0 | 1.9 | 23.7 | 6.6 |
| KFS_04 | 2025-03-27 | 24 | 7 | 0 | 0 | 0.8 | 23.7 | 8.3 |
| KFS_04 | 2025-03-28 | 23 | 0 | 0 | 0 | 0.8 | 14.4 | 11.4 |
| KFS_05 | 2023-04-02 | 8 | 0 | 0 | 0 | 1.4 | 11.5 | 12.7 |
| KFS_05 | 2023-04-03 | 23 | 0 | 0 | 0 | 2.1 | 11.2 | 13.4 |
| KFS_06 | 2025-03-22 | 7 | 7 | 0 | 0 | 1.1 | 18.8 | 15.2 |
| KFS_06 | 2025-03-23 | 24 | 9 | 0 | 0 | 0.8 | 18.0 | 15.5 |
| KFS_06 | 2025-03-24 | 24 | 24 | 0 | 0 | 0.8 | 26.6 | 20.1 |
| KFS_06 | 2025-03-25 | 24 | 24 | 0 | 0 | 1.1 | 31.9 | 20.0 |
| KFS_06 | 2025-03-26 | 17 | 14 | 0 | 0 | 1.1 | 26.4 | 15.9 |
| KFS_07 | 2023-04-02 | 7 | 6 | 0 | 0 | 1.9 | 15.9 | 15.1 |
| KFS_07 | 2023-04-03 | 11 | 2 | 0 | 0 | 1.7 | 15.7 | 13.4 |
| KFS_11 | 2022-05-31 | 8 | 0 | 0 | 0 | 1.1 | 9.9 | 6.5 |
| KFS_11 | 2022-06-01 | 24 | 0 | 0 | 0 | 1.5 | 10.3 | 7.8 |
| KFS_11 | 2022-06-02 | 7 | 0 | 0 | 0 | 0.8 | 6.7 | 3.8 |
| KFS_12 | 2022-02-16 | 4 | 4 | 0 | 0 | 1.5 | 23.9 | 16.9 |
| KFS_13 | 2025-04-29 | 21 | 0 | 0 | 0 | 0.5 | 10.1 | 7.0 |
| KFS_13 | 2025-04-30 | 14 | 0 | 0 | 0 | 0.4 | 12.3 | 9.2 |
| KFS_15 | 2022-04-11 | 3 | 0 | 0 | 0 | 1.9 | 12.0 | 5.5 |
| KFS_17 | 2023-03-09 | 13 | 2 | 0 | 0 | 0.8 | 16.6 | 9.7 |
