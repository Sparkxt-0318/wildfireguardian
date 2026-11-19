# RESULTS: a forecast margin that tracks the fire's state hour by hour (kcf-adaptive3)

Rules: `PROTOCOL.md`, committed at 0bf1917 before any result in this folder. No rule was changed afterwards; five
implementation notes were added at the end of the protocol. Every number is in `numbers.json` or `derived/`.
Labels: MEASURED unless marked; ASSUMED = taken on trust; NOT RUN = not done.

## Answer

An online two-state tracker (quiet or run), updated every hour from detections, with a forecast-driven transition and one
quantile margin per state, was built, tuned in a 20-proposal loop on 16 California fires, and run once on held-out fires.

| Target (10% miss rate, held-out fires) | Result | Verdict |
|---|---|---|
| A. Korean run fire-days warned at the gust rule's alarm burden: beat 4 of 9 | **4 of 9** (gust rule: 4 of 9) | **FAILED** |
| B. Flagged area on 12 Korean fires below the fixed margin, leave-one-fire-out | 83.6 km2 against 51.5 km2; ratio **1.62** (1.04 to 2.09) | **FAILED** |
| C. Flagged area on held-out California fires no worse than QUANTILE | 225.6 km2 against 237.6 km2; ratio **0.95** (0.89 to 0.99); 0.99 read at exactly 10% miss | **passed** |

**Two of three targets failed: A and B.**

What the numbers say beyond the verdicts:

1. **The idea did not work where it was aimed.** On Korea the tracker flags 62% more area than the fixed margin at the
   same miss rate, and more than QUANTILE (ratio 1.24, 1.05 to 1.57). It warned the same number of run fire-days as
   the gust rule, and it raised alarms on 11 of the 34 fire-days without a run, where the gust rule raised none.
2. **The California pass does not come from tracking the state.** With the hourly update switched off the same model
   needs no more area (220.6 km2; tracker / update-off = 1.02, 0.96 to 1.08), and with the forecast input switched off
   it also needs no more (228.9 km2; ratio 0.99, 0.95 to 1.04). On Korea the hourly update makes the margin worse
   (tracker / update-off = 1.24, 1.02 to 1.33). The gain over QUANTILE (5%, 1% at exactly equal miss) comes from
   fitting two quantile models, one on run hours and one on quiet hours, not from the filter.
3. **On 25 March 2025 the state moved before the spread, and the margin still missed.** The run probability crossed the
   alarm threshold at 09 KST, one hour before the first run hour, on the forecast alone (the same hour as the gust
   rule). But the issued margin was 3.5 to 10 km while the fire reached 5 to 40 km: 11 of the 12 hours from 09 to 20 KST
   were missed, the same as QUANTILE. The run-state margin itself tops out at 10 to 14 km, because no training fire
   ran like that day.
4. **The global archive added nothing measurable** (tracker / archive-off = 1.00 on California, 1.00 on Korea; same
   4 of 9).

**Read with care.** The Korean fires were already examined in kcf-adaptive2 and kcf-aloft, so this is not a first
look at them. Nine run fire-days (from 4 fires) and one 25 March are small samples: 4 of 9 and 5 of 9 cannot be told
apart, and no rate is given for either. All 28 California fires were scored in kcf-adaptive2; the 12 called held-out
here were held out of every fit and choice in this folder only.

## Results table

"Area" is the fire-weighted mean flagged area per issue hour at each method's calibrated margin. Miss intervals are
fire-cluster bootstraps (2,000 resamples). California held-out: 12 fires, 6,605 issue hours, models fitted and calibrated
on the 16 development fires. Korea: 12 fires, 756 issue hours, every model fitted without the scored fire.
(a) Warned at the day's first run hour at the gust rule's burden: the alarm threshold lets the model alarm on no more
burden point-days than the gust rule (169 of 4,950; 3.7 per point and season). The forecast-off row is **not** an
equal-burden number (section 2). (b) California: run fire-days warned at their first run hour when 10% of the
held-out fire-days without a run alarm; a different yardstick from (a), shown for the tracker rows only.

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

Ratios between methods (paired by fire):

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

- California: the tracker is lower than QUANTILE on 9 of the 12 held-out fires. Against the fixed margin its interval
  includes 1 (0.86, 0.71 to 1.02) at 12 fires; the fixed margin landed at 11.9% miss on these fires, and at exactly 10%
  the ratio is 0.79.
- Korea: every learned method needs more area than the fixed margin. The excess is concentrated in the largest fire:
  KFS_01 Uiseong 445 km2 for the tracker against 170 for the fixed margin (which misses 49% of that fire's hours while
  the tracker misses 25%); KFS_02 Uljin 189 against 127. On 6 of the 12 fires the tracker's area is below the fixed
  margin's. The fire-weighted mean is what the protocol fixed, and on it the tracker loses.
- Adding the 11 other Korean fires to the training set did not help the tracker: fitted on California only, with only
  the scale recalibrated leave-one-fire-out, it needs 68.4 km2 (table in section 3), against 83.6 when refitted with
  Korean fires. Both are above the fixed margin's 51.5.

## 1. What was built (details in `PROTOCOL.md` section 2, code in `lib3.py`)

- Two hidden states per fire. Label used for training only: a run hour is an issue hour whose 5 h reach exceeds
  3.75 km (3.4% of development hours; 81 run onsets on the 16 development fires).
- Every hour: a prediction step with enter and stay probabilities from logistic regressions on the issued forecast
  (gust, 850 hPa wind, humidity over the next 8 h), hour of day and an archive propensity; then an update from the
  growth seen in the last hour.
- One gradient-boosted 90% quantile model per state; the issued margin is their blend by the run probability, then
  one scale factor calibrated to a 10% miss rate on training fires.
- Comparators: the fixed margin; QUANTILE from kcf-adaptive2, unchanged; the tracker with the hourly update off; the
  tracker with the forecast input off; and the tracker without the archive input.
- Leakage tests pass (`tests/test_leak.py`): nothing after hour t changes the output at t; scrambling the scored
  fire's own labels changes nothing.

**Data.** GOFER (28 California fires, hourly) rebuilt from Zenodo with kcf-adaptive2's code. Korea: the 12 fires with
Choi et al. arrival rasters and the detection product for 25 March 2025. **Global archive: GlobFire v3, year 2021**
(PANGAEA): 42,593 fires with at least 3 burn days and 10 km2, 415,480 fire-days, of which 384,354 could be paired with
a GFS forecast as issued; 36,492 (9.5%) are run days by the frozen rule (daily reach above 3.75 km). The archive enters
only as one input of the transition. **Sources that could not be used:** FIRED (the host answered 403 to this
environment); the Su & Yu VIIRS event set downloads but is one row per fire with no daily geometry, so it cannot label
fire-days; no VIIRS-based daily atlas with global coverage was found. Only 2021 was used because as-issued GFS on the
open NOAA bucket starts in 2021 and GlobFire ends in 2021. GlobFire is MODIS burned area with burn dates of a day or
more uncertainty, a much blunter product than GOFER. **No simulated fires were used.**

**Agent loop** (`PROPOSALS.md`, all 20 logged). Four changes were kept: tempering the update (likelihood exponent 0.5,
then 0.25), a coarser observation table, and stronger regularisation of the transition. Development area fell from
342.7 to 324.0 km2 and development run-days warned rose from 19 to 30 of 72. Sixteen were discarded, among them an
exact mixture quantile, 3 h growth as the observation, recent growth or a forecast ramp in the transition, tree-based
transitions and larger margin models. The clearest signal in the loop pointed away from the idea: every step that
weakened the hourly update lowered the area, and version 0 with the update off (320.2) already beat every later
version on area.

## 2. Target A in detail

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

- The tracker warned 4 of 9: three of the gust rule's four days (not Uljin 4 March 2022, which ran within an hour of
  ignition) plus Uiseong 26 March 2025, a 00 KST continuation of a run already under way. On the 6 onset days it warned
  2; the gust rule warned 3 of those 6.
- Five run fire-days were not warned by the tracker: Uiseong 22 and 23 March 2025, Uljin 4 and 10 March 2022 and
  Sancheong 22 March 2025. Four of them were warned by neither rule (the gust rule did warn Uljin 4 March). On the days with low forecast wind the forecast gives the state no push,
  and the growth seen in the hour before a run starts is usually zero.
- The equal burden holds only where there is no fire. At the fires the tracker was in alarm on 24% of all issue hours
  and on 11 of the 34 fire-days without a run (among them Uiseong 24 and 27 March 2025, Sancheong 24 and 25 March 2025).
  The burden set cannot charge for alarms raised by detections. Strict A (no more such alarms than the gust rule's 0)
  fails as well.
- With the update off (forecast only, a like-for-like comparison with the gust rule) the model warned 3 of 9, with 3
  alarms on no-run fire-days.
- With the forecast off the model warned 6 of 9, but its score at a burden point is a constant, so the burden set
  does not constrain it: it alarmed on 29 of the 34 no-run fire-days. That is not a warning rule.

## 3. Korea, secondary rows (as fixed in PROTOCOL section 5)

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

The straight California transfer repeats kcf-adaptive2: learned methods are conservative on Korea (2% to 5% miss) and
flag more area. Read at exactly 10% miss, none is below the fixed margin (52.1 km2).

## 4. 25 March 2025, hour by hour

Detection product (FIRMS VIIRS + Himawari), KFS_01 held out of every fit. Each row uses only what was available at that
hour: the forecast as issued (5 h availability delay, ASSUMED), growth seen up to that hour, and the model. "enter" is
the forecast-driven probability of moving from quiet to run; c is the alarm threshold from the burden set. Margins in
km; **M** = missed, h = held. One fire, one day: counts only.

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

- The forecast moved the state first: the run probability rose from 0.03 at 04 KST to 0.17 at 09 KST with no growth
  observed, and the alarm was on from 09 KST. It had also been on from 09 to 20 KST the day before, without a run.
- At 10 and 11 KST the update pulled the probability **down** (0.27 to 0.21, 0.31 to 0.25) because no growth had been
  detected in the last hour, while the fire was already reaching 5 to 7 km in the next five. The detection product lags
  the fire front that morning; the update trusted it.
- The probability reached 0.47 at 12 KST and stayed between 0.5 and 0.7. It never approached 1, a consequence of the
  tempering the loop kept.
- Even at probability 1 the margin would have missed: the run-state margin was 10 to 14 km against a reach of 12 to
  40 km from 12 to 19 KST. The size of that day lies outside every training fire.

## 5. Limits

- Small samples: 12 held-out California fires, 12 Korean fires, 9 run fire-days from 4 fires, one 25 March. Intervals
  are fire bootstraps with no correction for the number of comparisons.
- Not a first look: section "Read with care" above.
- Target A's equal-burden construction charges only forecast-driven alarms (burden points have no fire).
- The threshold for a run day in the archive is the hourly one (3.75 km) applied to a whole day, so archive run days
  are a looser event than hourly run hours.
- The forecast inputs and their 5 h availability delay are inherited from kcf-abstain and kcf-aloft (ASSUMED). The
  gust rule's burden was recomputed here and reproduces kcf-aloft (3.675 against 3.7 alarm days per point and season;
  identical levels on the 1,820 point-days compared).
- The tracker is one implementation: a tabulated emission, logistic transitions, a linear blend. Its failure is not a
  proof that no state tracker could work. What the ablations do show is that, with these data, the hourly growth
  observation adds nothing beyond having recent growth as an input of the margin model, which QUANTILE already has.
- NOT RUN: 8 h horizon; FIRED; any second forecast model.

## 6. Reproduce

    # needs zenodo.org, download.pangaea.de, noaa-gfs-bdp-pds.s3.amazonaws.com
    python ../kcf-adaptive2/build_data.py --gofer DATA/gofer/GOFER --choi DATA/choi --out WORK   # export KCF3_WORK=WORK
    python build_archive.py --shp DATA/Daily_GlobFirev3_GWIS_MCD64A1__2021.shp --out derived/archive_days.csv.gz
    python fetch_archive_gfs.py --out GFS2021 --start 2020-12-31 --end 2022-01-02
    python archive_features.py --gfs GFS2021 --fit
    python propose.py 0 "version 0" '{}'            # then proposals 1..20 as logged in derived/proposals.jsonl
    python final_ca.py                              # once
    python fetch_burden.py --out NWP --seasons 2021 2022 2023 2024 2025
    python burden_hours.py --nwp NWP/gfs_KOR --seasons 2021 2022 2023 2024 2025 --out derived/burden_hours.csv.gz
    python korea.py --burden derived/burden_hours.csv.gz    # once
    python make_numbers.py; python make_proposals.py; python make_results.py; python -m pytest -q tests
