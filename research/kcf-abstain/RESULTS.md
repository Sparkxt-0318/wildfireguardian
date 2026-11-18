# RESULTS: can the reach margin tell it is out of range, and withhold its number? (kcf-abstain)

**Answer (MEASURED; rules frozen in `PROTOCOL.md` at ef50d2a before any outcome was computed).**
Yes on 25 March 2025, but not specifically for that fire.
- **25 March 2025.** From GFS forecasts already issued at each hour, the frozen rule withholds the margin at **every issue
  hour from 10:00 to 20:00 KST (11 of 11)**. At the 10-16 KST issue hours the forecast 850 hPa wind for the next 8 h was
  32-33 m/s, beyond all 20,065 calibration hours. From 17 KST the trigger was the observed spread of the previous 3 h
  (12-32 km; beyond every calibration hour from 18 KST).
- **What gave no warning at 10-11 KST.** Prior-3 h spread was 0 km. Station gusts were below 10 m/s (`research/kcf-gust`).
  The warning was in the issued forecast, not in anything observed.
- **On the 28 California calibration fires** (leave-one-fire-out), the same rule withholds 4.9% of hours. The miss rate
  among the rest falls from 6.0% to 4.9% at 5 h, and from 6.4% to 5.2% at 8 h. The score separates missed hours by the
  frozen rule: AUROC 0.84 (95% CI 0.79-0.88) and 0.86 (0.81-0.89), n = 28 fires.
- **In Korea it flags a weather regime, not a dangerous hour** (counts only).
  - On 12 Korean fires it withheld 330 of 756 hours. That caught 40 of the 51 margin misses, but it also withheld 290
    hours in which the margin held, including 78 of 96 hours of the Ulju fire, which never missed.
  - It withheld whole or nearly whole windy days (4-5 March 2022, 24-25 March 2025) and little or nothing on calmer days.
- **On the 19 US test fires (Choi rasters) it transfers weakly.** It withholds 2.9% of hours and keeps 144 of the 200
  margin misses. The miss rate among kept hours is 0.5%, against 0.7% with no abstention.
- **Tail.** PENDING at this commit: the GEV parametric bootstrap (2,000 refits) is still running.

All numbers are in `numbers.json`; every table below is printed from it by `tables.py` (`derived/tables.md`). Hour-by-hour
rows for every fire are in `derived/hours.csv.gz`. Labels: MEASURED unless marked ASSUMED. No reanalysis was used, so no
number is ASSUMED PERFECT FORECAST.

## What was run (frozen; details in `PROTOCOL.md`)

- **Fires.** `FIRES.md`: 63 fires reconciled from the finals paper and the frozen registries. Only the 28 GOFER fires set
  anything. Every other fire only tests.
- **Reach.** The kcf-margin rule, unchanged: 5 km separate-fire rule, 5 h and 8 h. GOFER and the 25 March detection product
  reuse kcf-margin's committed values. The Choi kriged arrival rasters are computed here with kcf-margin's own code.
- **Margin.** The kcf-margin all-hours margin at the 10% target: R(5 h) = 3.75 km, R(8 h) = 5.03 km. On calibration fires
  it is the leave-one-fire-out R; the recomputation reproduces kcf-margin's committed LOFO miss rates exactly
  (0.061556 and 0.066184).
- **Predictors, issued forecasts only.**
  - Source: GFS 0.25 deg for every fire from 2021 (all Korean fires, 11 GOFER fires, the US 2021-2024 fires); HRRR 3 km,
    box-averaged onto the same 0.25 deg lattice, for US fires before 2021 (17 GOFER fires, CameronPeak, EastFork).
  - Timing: cycles 00/06/12/18 UTC, **assumed available 5 h after the cycle**, read at leads 6-18 h over the 8 h window
    (t, t+8].
  - Place: the four lattice points around the centroid of the fire's known burned area at the issue hour.
  - The five predictors: max 10 m gust, max 850 hPa wind, min 2 m RH, max HDW (surface form, ASSUMED simplification),
    prior-3 h spread.
- **Score.** For each predictor, the fire-weighted share of calibration hours at least as dangerous (high wind, gust, HDW,
  spread; low RH). The score is the minimum over the five. The system abstains when the score is at or below tau, the
  beta = 0.05 leave-one-fire-out quantile of the calibration scores (tau = 0.0107).

## 1. Calibration fires, leave-one-fire-out

Each held-out fire is scored against the other 27. Its threshold comes from nested leave-one-out scores within those 27,
and its margin is its kcf-margin LOFO R. Rates are fire-weighted means over fires; intervals are Clopper-Pearson on
n = 28 fires, as in kcf-margin. Bootstrap intervals resample fires (2,000, seed 20261118).

| arm | h | n fires | hours | abstention (95% CI) | miss among kept (95% CI) | miss, no abstention (95% CI) | abstained hours / miss rate among them (pooled) | AUROC (95% CI) | change in miss rate (95% CI) | frozen verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **primary** | 5 h | 28 | 20,065 | 4.9% (0.3-20.4) | **4.9%** (0.3-20.3) | 6.0% (0.5-21.9) | 732 / 18.7% | **0.84** (0.79-0.88) | -1.13 pts (-2.35 to -0.32) | **separates** |
| **primary** | 8 h | 28 | 19,981 | 4.9% (0.3-20.3) | **5.2%** (0.4-20.8) | 6.4% (0.7-22.5) | 725 / 20.4% | **0.86** (0.81-0.89) | -1.26 pts (-2.52 to -0.41) | **separates** |
| S1 two-sided | 5 h | 28 | 20,065 | 5.0% (0.3-20.4) | 5.1% (0.3-20.7) | 6.0% (0.5-21.9) | 1,001 / 8.1% | 0.73 (0.66-0.80) | -0.84 pts (-1.99 to -0.10) | separates |
| S1 two-sided | 8 h | 28 | 19,981 | 4.9% (0.3-20.4) | 5.6% (0.4-21.4) | 6.4% (0.7-22.5) | 992 / 8.7% | 0.75 (0.69-0.82) | -0.83 pts (-2.05 to -0.06) | separates |
| S2 GFS-only | 5 h | 11 | 9,923 | 4.1% (0.0-34.6) | 2.2% (0.0-31.9) | 2.7% (0.0-32.7) | 394 / 17.5% | 0.80 (0.74-0.85) | -0.54 pts (-1.01 to -0.15) | separates |
| S2 GFS-only | 8 h | 11 | 9,890 | 4.0% (0.0-34.5) | 2.0% (0.0-31.7) | 2.6% (0.0-32.6) | 384 / 18.2% | 0.80 (0.74-0.86) | -0.60 pts (-1.13 to -0.15) | separates |

- **What this means.** Pooled over hours at 5 h, the rule withholds 732 of 20,065 hours and 137 of the 720 misses are among
  them. The miss rate among withheld hours is 18.7%, against 3.6% over all hours pooled (6.0% fire-weighted). Withholding
  more removes more misses:
  at beta = 0.20 (80% coverage) the miss rate among kept hours is 2.7% at 5 h and 2.6% at 8 h (table below,
  `fig/risk_coverage.png`).
- **What triggers it in California.** HDW for 235 of the 732 withheld hours, min RH for 208, gust 124, prior-3 h spread 121,
  850 hPa wind 44. No fire had every hour withheld.
- **Secondary arms.** Both still separate.
  - The two-sided score (S1) is weaker. 623 of its 1,001 withheld hours are withheld only for a benign extreme (wind, gust
    or HDW below the 2nd percentile, or RH above the 98th), and the margin missed in 0.3% of them, against 18.7% of the
    primary rule's withheld hours (descriptive, from `derived/hours.csv.gz`).
  - Dropping the 17 HRRR fires (S2, 11 GFS fires) gives a similar AUROC (0.80), so the GFS/HRRR mix is not what makes it
    work.
- **Not scored.** 96 of 20,161 calibration hours: 84 are the first 3 h of each fire (no prior-3 h spread), and 12 come from
  one HRRR cycle (2020-10-08 06 UTC) with missing fields.

| beta | coverage 5 h | miss among kept 5 h | coverage 8 h | miss among kept 8 h |
|---|---|---|---|---|
| 0 (no abstention) | 100% | 6.0% | 100% | 6.4% |
| 0.01 | 99.0% | 5.4% | 99.0% | 5.8% |
| 0.05 (frozen) | 95.1% | 4.9% | 95.1% | 5.2% |
| 0.10 | 90.1% | 4.0% | 90.1% | 4.4% |
| 0.20 | 79.9% | 2.7% | 79.9% | 2.6% |
| 0.30 | 70.0% | 1.7% | 70.1% | 1.8% |
| 0.50 | 50.1% | 0.6% | 50.2% | 0.5% |

Random abstention keeps the miss rate at 6.0% / 6.4% at every coverage. The full curve (beta 0 to 1 in steps of 0.01, with the
oracle) is in `numbers.json` -> `calibration_lofo.primary.h5|h8.risk_coverage`.

## 2. 25 March 2025, 10:00-20:00 KST (Gyeongbuk, KFS_01; detection product, n = 1 fire, counts only)

The score is computed against all 28 calibration fires (tau = 0.0107). Forecasts are GFS as issued, with a 5 h availability
delay. Reach comes from detections (kcf-margin; detections, not perimeters: ASSUMED proxy).

| KST | GFS cycle (UTC) | gust m/s | 850 hPa m/s | min RH % | HDW | prior-3 h km | score s | abstains | lowest predictor | 5 h reach km (R 3.75) | 5 h margin | 8 h reach km (R 5.03) | 8 h margin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10:00 | 24 Mar 18 | 23.0 | 32.3 | 16 | 223 | 0.00 | 0 | **yes** | 850 hPa wind | 4.9 | missed | 23.9 | missed |
| 11:00 | 24 Mar 18 | 23.0 | 32.3 | 16 | 223 | 0.00 | 0 | **yes** | 850 hPa wind | 6.6 | missed | 34.7 | missed |
| 12:00 | 24 Mar 18 | 23.0 | 32.3 | 16 | 223 | 2.25 | 0 | **yes** | 850 hPa wind | 12.4 | missed | 34.9 | missed |
| 13:00 | 24 Mar 18 | 23.0 | 32.3 | 16 | 223 | 2.25 | 0 | **yes** | 850 hPa wind | 23.9 | missed | 44.0 | missed |
| 14:00 | 25 Mar 00 | 23.8 | 33.2 | 18 | 229 | 2.25 | 0 | **yes** | 850 hPa wind | 34.7 | missed | 50.3 | missed |
| 15:00 | 25 Mar 00 | 23.8 | 33.2 | 21 | 226 | 4.89 | 0 | **yes** | 850 hPa wind | 32.9 | missed | 46.6 | missed |
| 16:00 | 25 Mar 00 | 23.8 | 33.2 | 27 | 196 | 6.56 | 0 | **yes** | 850 hPa wind | 40.1 | missed | 46.4 | missed |
| 17:00 | 25 Mar 00 | 21.9 | 28.1 | 37 | 112 | 11.92 | 0.0005 | **yes** | prior-3 h spread | 38.6 | missed | 38.6 | missed |
| 18:00 | 25 Mar 00 | 16.7 | 26.8 | 37 | 58 | 22.33 | 0 | **yes** | prior-3 h spread | 27.3 | missed | 27.3 | missed |
| 19:00 | 25 Mar 00 | 16.1 | 26.8 | 37 | 53 | 32.26 | 0 | **yes** | prior-3 h spread | 20.3 | missed | 20.3 | missed |
| 20:00 | 25 Mar 06 | 14.1 | 24.8 | 36 | 45 | 23.47 | 0 | **yes** | prior-3 h spread | 15.7 | missed | - | not scored (AHI coverage ends) |

- **10:00-20:00 KST.** The rule withholds the margin at all 11 hours; the 5 h margin missed at all 11, and the 8 h margin
  at all 10 scored hours.
- **Why.** Until 16 KST the trigger is the forecast 850 hPa wind. Its maximum over the next 8 h (32.3 m/s from the 18 UTC
  run, 33.2 m/s from 00 UTC) is above every calibration hour; the highest calibration value is 30.1 m/s (Kincade, a
  Diablo-wind event), and the fire-weighted 99th percentile is 15.3 m/s (descriptive values from
  `derived/ecmwf_crosscheck.json`). From 17 KST the trigger is the observed spread of the previous 3 h: 11.9 km at
  17 KST (rarer than all but 0.05% of calibration hours, fire-weighted), then 22-32 km, beyond every calibration hour
  (largest 16.0 km, North Complex). The forecast gust (23.0-23.8 m/s) was above the calibration 99th percentile
  (19.0 m/s) as well.
- **The quiet morning.** At 10 and 11 KST nothing observed was unusual: spread 0 km, station gusts under 10 m/s, KMA's
  first gust of 20 m/s or more at 18:15 KST (`research/kcf-gust`). The forecast for the next 8 h already showed wind
  outside California's range.
- **Same day, all hours.** The rule withholds at 22 of 24 issue hours (00 and 01 KST are kept). At 5 h, 23 hours are
  scored: 21 withheld (13 misses and 8 hours in which the margin held, 02-09 KST), and 2 kept, both held. At 8 h, 20
  scored: 18 withheld (12 missed, 6 held), 2 kept and held. Both secondary arms (S1, S2) also withhold all 11 hours from
  10 to 20 KST.
- **The Choi raster of the same fire on the same hours** (secondary product): the rule withholds 22 of 24 hours of
  25 March KST. Of that day's 11 misses at 5 h, 10 are withheld. The one kept is 01 KST (reach 4.0 km against 3.75 km;
  score 0.012, just above tau).
- **POST HOC check of the 850 hPa wind** (PROTOCOL amendment 1; changes nothing). ECMWF IFS 0.25 deg, same cycles and
  lattice points, 3-hourly steps: maximum 27.6 m/s for the 10-17 KST issue hours, where GFS at the same valid times gives
  26.1-28.1 m/s. The GFS 32-33 m/s maxima fall between IFS output steps. Both models put the 850 hPa wind far above the
  calibration 99th percentile. Details in `derived/ecmwf_crosscheck.json`.

## 3. Every other fire, hour by hour

Each test fire's hours are scored against all 28 calibration fires with the frozen R and tau. The 2 x 2 counts per fire are
below; the row for every hour is in `derived/hours.csv.gz` (`abstain`, `held5`, `held8`, the five predictors and their tail
probabilities).

**Groups** (Korea and US2024: counts only; the 19 US test fires: rates, n = 19):

| group | h | fires | scored hours | withheld | margin missed | withheld & missed | withheld & held | kept & missed | kept & held |
|---|---|---|---|---|---|---|---|---|---|
| Korea, Choi rasters | 5 h | 12 | 756 | 330 | 51 | 40 | 290 | 11 | 415 |
| Korea, Choi rasters | 8 h | 11 | 720 | 321 | 46 | 42 | 279 | 4 | 395 |
| Korea, 25 March detections | 5 h | 1 | 23 | 21 | 13 | 13 | 8 | 0 | 2 |
| Korea, 25 March detections | 8 h | 1 | 20 | 18 | 12 | 12 | 6 | 0 | 2 |
| US2024 | 5 h | 6 | 8,444 | 76 | 59 | 6 | 70 | 53 | 8,315 |
| US2024 | 8 h | 6 | 8,426 | 76 | 24 | 5 | 71 | 19 | 8,331 |
| US test fires (19) | 5 h | 19 | 29,470 | 906 | 200 | 56 | 850 | 144 | 28,420 |
| US test fires (19) | 8 h | 19 | 29,413 | 900 | 90 | 33 | 867 | 57 | 28,456 |

- **US test fires (n = 19, fire-weighted).** Abstention 2.9% (95% CI 0.0-22.5). Miss rate among kept hours 0.5% (0.0-18.6),
  against 0.7% (0.0-18.8) with no abstention at 5 h; at 8 h 0.2% (0.0-18.0) against 0.3% (0.0-18.2). The Choi rasters miss
  the margin rarely (they are kriged and smooth; see S3 below), and the rule catches few of those misses. It withholds most
  at CameronPeak (273 hours, HRRR), HermitsPeak (335, a spring fire in New Mexico) and EastFork (172, HRRR).
- **Korea.** The rule withholds whole or nearly whole windy days and little or nothing on calmer days (day-by-day table
  below).
  - 4-5 March 2022 at Uljin and Gangneung: every hour withheld (850 hPa wind up to 33 m/s); all 14 misses of those two days
    caught.
  - Uljin from 6 March: almost nothing withheld. Its 5 misses on 10 March were kept (reach up to 4.8 km, forecast
    850 hPa wind 10.7 m/s).
  - Late March 2025: Uiseong, Sancheong and Ulju withheld for most hours. Sancheong (no misses after 22 March) and Ulju
    (no misses at all) were withheld as heavily as Uiseong, which ran 40 km.

| fire | 5 h: scored / withheld / missed / withheld & missed | 8 h: same |
|---|---|---|
| KFS_01 Uiseong (Choi) | 99 / 72 / 27 / 21 | 96 / 69 / 24 / 23 |
| KFS_01 Uiseong (25 March detections) | 23 / 21 / 13 / 13 | 20 / 18 / 12 / 12 |
| KFS_02 Uljin | 186 / 39 / 14 / 9 | 183 / 39 / 10 / 7 |
| KFS_03 Gangneung | 66 / 24 / 5 / 5 | 63 / 24 / 8 / 8 |
| KFS_04 Sancheong | 166 / 103 / 5 / 5 | 163 / 103 / 4 / 4 |
| KFS_05 Hongseong | 31 / 0 / 0 / 0 | 28 / 0 / 0 / 0 |
| KFS_06 Ulju | 96 / 78 / 0 / 0 | 93 / 75 / 0 / 0 |
| KFS_07 Geumsan | 18 / 8 / 0 / 0 | 15 / 8 / 0 / 0 |
| KFS_11 Miryang | 39 / 0 / 0 / 0 | 36 / 0 / 0 / 0 |
| KFS_12 Yeongdeok (2022) | 4 / 4 / 0 / 0 | 1 / 1 / 0 / 0 |
| KFS_13 Buk-gu | 35 / 0 / 0 / 0 | 32 / 0 / 0 / 0 |
| KFS_15 Gunwi | 3 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| KFS_17 Hapcheon | 13 / 2 / 0 / 0 | 10 / 2 / 0 / 0 |
| Wapiti (US2024) | 1,710 / 18 / 12 / 0 | 1,707 / 18 / 7 / 0 |
| Goat (US2024) | 1,589 / 6 / 9 / 0 | 1,586 / 6 / 1 / 0 |
| Lava (US2024) | 1,152 / 0 / 15 / 0 | 1,149 / 0 / 6 / 0 |
| RedRock (US2024) | 1,118 / 28 / 8 / 6 | 1,115 / 28 / 6 / 5 |
| Pioneer (US2024) | 1,522 / 0 / 0 / 0 | 1,519 / 0 / 0 / 0 |
| FishCreek (US2024) | 1,353 / 24 / 15 / 0 | 1,350 / 24 / 4 / 0 |
| CameronPeak (HRRR) | 1,714 / 273 / 39 / 14 | 1,711 / 270 / 20 / 12 |
| EastFork (HRRR) | 1,419 / 172 / 6 / 0 | 1,416 / 169 / 8 / 0 |
| AlderCreek | 2,001 / 11 / 5 / 0 | 1,998 / 11 / 0 / 0 |
| TrailCreek | 2,064 / 12 / 0 / 0 | 2,061 / 12 / 0 / 0 |
| WestLolo | 943 / 2 / 6 / 0 | 940 / 2 / 6 / 0 |
| GreenRidge | 1,601 / 16 / 4 / 0 | 1,598 / 16 / 0 / 0 |
| RoughPatchCpx | 1,203 / 0 / 0 / 0 | 1,200 / 0 / 0 / 0 |
| Jack | 1,773 / 0 / 3 / 0 | 1,770 / 0 / 0 / 0 |
| DevilsKnob | 1,251 / 0 / 2 / 0 | 1,248 / 0 / 2 / 0 |
| SchneiderSprings | 1,281 / 0 / 8 / 0 | 1,278 / 0 / 0 / 0 |
| Moose | 2,142 / 9 / 9 / 5 | 2,139 / 9 / 3 / 0 |
| HermitsPeak | 1,782 / 335 / 38 / 31 | 1,779 / 335 / 21 / 16 |
| CedarCreek | 1,852 / 0 / 21 / 0 | 1,849 / 0 / 6 / 0 |

Every test fire's first 3 issue hours are not scored (no prior-3 h spread), and 4 more at CameronPeak and EastFork (the
HRRR cycle with missing fields).

**Korean fires day by day** (KST days, Choi rasters, 5 h, counts):

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

**NOT TESTED.** KFS_09 Yanggu, KFS_14 Uljin (May 2022) and KFS_16 Suncheon: the whole fire arrives within one hour, so no
issue hour has a complete 5 h window. Rim 2013: no hourly arrival product (`FIRES.md`). The 10 catalog fires that are also
GOFER fires are calibration fires; their Choi rasters are used only in S3. NIROPS survey intervals (US2024's 273, Wapiti's
25), Korea2025's 33 twelve-hour windows and the 273 routing receipts are not tested as cases; their fires are tested hour
by hour above.

## 4. S3: how much of a test result is the product, not the fire

Same 10 fires, same issue hours, frozen R. GOFER perimeters against Choi rasters, fire-weighted, n = 10:

| h | miss rate on GOFER (95% CI) | miss rate on Choi (95% CI) |
|---|---|---|
| 5 h | 2.8% (0.0-35.0) | 2.4% (0.0-34.4) |
| 8 h | 2.8% (0.0-35.0) | 1.7% (0.0-33.5) |

The Choi rasters give slightly lower miss rates than GOFER on the same fires. Their median reach is higher (0.4-0.5 km
where GOFER's is 0), because kriging spreads growth smoothly over the hours. So the low miss rates on the US test fires
are partly the product. Per-fire values are in `numbers.json` -> `S3_product_crosscheck`.

## 5. Tail question: how rare is a 40 km reach?

PENDING at this commit: the GEV parametric bootstrap (2,000 refits) is still running. `evt.py` writes `derived/evt.json`; this section and `numbers.json` follow when it finishes.

## Data and provenance

- **Reach.** GOFER (28 calibration fires) and 25 March 2025 (detection product) are reused unchanged from
  `research/kcf-margin/derived/` (commit 0ead891). The GOFER arrival rasters were rebuilt from the GOFER v0.2 archive
  (Zenodo 14642378, sha256 96eca2e1..., verified) only to locate the fire at each hour; they reproduce 168 randomly
  chosen committed reach values to 0.000000 km. Choi et al. 2026 rasters (Zenodo 21788344, sha256 612edf5f..., verified;
  the KFS_01 raster is byte-identical to the copy committed in `research/harness-2026-11/data-fetch/small/choi2026_kfs01/`)
  give the reach of every other fire, computed here with kcf-margin's `component_reach` (5 km rule).
- **Forecasts.** Issued GFS 0.25° and HRRR runs from the NOAA Open Data Dissemination buckets on AWS, fetched by byte range
  from each forecast hour's `.idx` (7 fields x 13 leads per cycle). `derived/forecast_fetch_log.json` lists every model and
  region with its cycles, bytes, fetch times (UTC) and any cycle with a missing field. Nothing is filled; an hour whose
  forecast is incomplete gets no score.
- **Not in the repo.** The 3.1 GB of lattice extracts (from about 199 GB of GRIB byte ranges streamed: GFS Korea 11.1 GB, GFS US 132.9 GB, HRRR 55.4 GB) stay outside git; `run_all.sh` rebuilds them.

## Limits

- **Calibration set.** 28 large California fires, 2019-2021, mapped hourly from GOES at about 2 km. The fire is the unit
  (hours within a fire are not independent), so every interval is over 28 fires and is wide. The score's reference is
  what these 28 fires looked like in the forecasts; "out of range" means out of their range, nothing more.
- **Two forecast models in the reference.** 17 calibration fires are read from HRRR and 11 from GFS, because the reachable
  GFS archive starts in 2021 and HRRR does not cover Korea. HRRR is averaged onto the GFS lattice and read at the same
  cycles and leads, but the two models still differ (S2 removes HRRR from the reference).
- **Lead times.** The 5 h availability delay and 6-hourly cycles are conservative for HRRR (real availability about
  1-1.5 h, hourly cycles). A forecaster with the freshest runs would have seen somewhat better forecasts.
- **HDW** is the surface form (10 m wind x 2 m VPD), not Srock et al.'s lowest-50 hPa form.
- **Where the fire is.** One point per hour (the centroid of the known burned area) and the four 0.25° lattice points
  around it. A long fire's active front can lie away from its centroid.
- **Test products differ from GOFER.** Choi rasters are kriged inside the final perimeter from satellite detections and
  use detections after the issue hour; S3 measures how much that alone changes the miss rate. The 25 March product is
  detections, not perimeters (kcf-margin's caveats apply).
- **Korea** is one country, 15 catalog fires plus one detection product; counts only.

## Reproduce

```bash
research/kcf-abstain/run_all.sh WORK_DIR
```

It verifies and unpacks the two Zenodo archives, streams the forecast byte ranges (about 199 GB read, 3.1 GB kept),
rebuilds every derived file, `numbers.json` and both figures, and runs `tests/` (4 unit tests of the score, threshold and
AUROC against brute force). The tables in this file are printed by `python3 tables.py numbers.json`.
