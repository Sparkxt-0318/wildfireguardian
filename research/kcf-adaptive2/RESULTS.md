# RESULTS: can a general machine-learning forecast margin beat the fixed margin at equal miss rate? (kcf-adaptive2)

Rules: `PROTOCOL.md`, frozen at commit 28ece7a before any result in this folder; three amendments, two of them written after
seeing results (listed in section 8, with what was seen). Every number below is in `numbers.json` or `derived/`.
Labels: MEASURED = computed here from data; ORACLE = uses the fire's future, never a result for any method;
ASSUMED = an input taken on trust; NOT RUN = not done, with the reason.

## Answer

The belief was that `kcf-adaptive` failed because it (1) adapted on each fire's own past, (2) trained for average error,
(3) compared methods at unequal miss rates, and (4) had few fires. Tested at one metric (flagged area at a 10% miss rate, miss
rate checked on fires held out of every fit), the data say:

1. **Reason 2 (average error) is the one that holds.** A model trained with a quantile loss, using what is known at the issue
   hour, needs **15% less area than the fixed margin at the same 10% miss rate** (area ratio 0.846, 95% interval 0.737 to
   0.946; 28 held-out California fires; lower on 22 of 28 fires; still 0.78 when the three largest fires are left out).
2. **Reason 1 (own past) is half right, and the half matters.** The fire's recent growth is what carries that gain
   (own-past features alone: 0.861; issued forecast alone: 0.919; both: 0.846). But using the past as an *input to one global
   model* works, while *adapting a model to each fire* does not: the per-fire Kalman update is worse than its own
   non-adaptive twin (area ratio 1.19, interval 1.04 to 1.42) and worse than the fixed margin (1.50); Reptile meta-learning
   with test-time adaptation is no better than its own starting point (ratio 1.01, 0.97 to 1.06) and does not beat the fixed
   margin (0.97, 0.82 to 1.15). At 8 h adaptation is again never better than its twin and is significantly worse for META
   (1.022, 1.001 to 1.046), KALMAN (1.322, 1.161 to 1.555) and the covariate tail of EVT (1.134, 1.021 to 1.292).
3. **Reason 3 (unequal miss rates) is real but is not what hid a gain.** All 18 variants land at 9.6% to 10.9% held-out miss;
   comparing at the held-out 10% instead of the calibrated point changes no ranking. REGIME's apparent 5% gain is mostly its
   10.9% miss rate: at exactly 10% its area equals the fixed margin's (328.7 against 326.9 km2).
4. **Reason 4 (few fires) is not supported.** The learning curve is flat from 4 to 24 training fires (area ratio to the fixed
   margin 0.85 at every n), 19 more fires from another archive add nothing at 5 h (0.880 against 0.866 without) and a little at 8 h (0.949 of the model
   without them, 0.885 to 1.003: not distinguishable from 1), and a simulator adds nothing (0.904 at 5 h; worse at 8 h, 1.068).
5. **None of it transferred to Korea, and none of it saw 25 March 2025 coming.** With margins calibrated on California,
   every learned method flags more area than the fixed margin on 12 Korean fires, and on 25 March no margin larger than
   about 12 km was issued before the fire had been running 30 km reaches for hours.

The stop/go gate passed (the oracle that adapts a scale per fire-day using the future gains 24.5% area). It says the
headroom lies in *when* within a day the fire runs, not in which fire it is: the fire-level oracle gains nothing (section 1).

## Main table: area at a 10% miss rate, achieved miss rate, number of fires

Held-out California fires (GOFER), 5 h ahead, 20,065 issue hours, 7 outer folds by fire. "Area" is the fire-weighted mean flagged
area per issue hour (km2) of the margin each method calibrated to 10% on its training fires. The miss interval is a fire-cluster
bootstrap (2,000 resamples). The ratio columns are paired fire bootstraps. Verdicts follow PROTOCOL section 3: valid miss
(within 10% +/- 3 points and the interval contains 10%), then **helps** if the upper end of the ratio interval is below 1,
**material** if the point estimate is 0.90 or lower. The last column reads the area off the held-out frontier at exactly 10% miss
(descriptive; it uses held-out outcomes).

| Method | Family | Area at 10% target (km2) | Achieved miss, 95% interval | Fires | Area / FIXED (95%) | Verdict | Area read at held-out 10% |
|---|---|---|---|---|---|---|---|
| FIXED | baseline | 328.9 | 9.8% (6.9 to 13.3) | 28 | 1.000 (1.000 to 1.000) | - | 326.9 |
| PERSIST | baseline | 483.1 | 9.9% (8.8 to 11.2) | 28 | 1.469 (1.256 to 1.690) | does not help | 481.2 |
| QUANTILE | 3 quantile loss | 278.4 | 9.7% (8.6 to 11.1) | 28 | 0.846 (0.737 to 0.946) | helps (material) | 274.6 |
| QUANTILE-own | 3 (own-past features only) | 283.2 | 10.0% (8.8 to 11.5) | 28 | 0.861 (0.748 to 0.970) | helps (material) | 283.3 |
| QUANTILE-fc | 3/4 (issued-forecast features only) | 302.2 | 10.0% (7.8 to 12.7) | 28 | 0.919 (0.857 to 0.990) | helps | 302.7 |
| REGIME | 4 forecast regime | 312.1 | 10.9% (8.0 to 14.4) | 28 | 0.949 (0.923 to 0.976) | helps | 328.7 |
| REGIME+own | 4 regime + own-past quantile | 282.9 | 10.1% (8.8 to 11.7) | 28 | 0.860 (0.753 to 0.963) | helps (material) | 285.0 |
| EVT | 6 peaks over threshold | 288.2 | 10.0% (8.7 to 11.5) | 28 | 0.876 (0.754 to 0.999) | helps (material) | 287.6 |
| EVT-twin | 6 (constant-scale twin) | 278.4 | 10.1% (8.9 to 11.6) | 28 | 0.846 (0.739 to 0.945) | helps (material) | 279.5 |
| PRETRAIN-archive | 5 pretrain: 19 archive fires | 289.3 | 9.9% (8.7 to 11.2) | 28 | 0.880 (0.765 to 0.985) | helps (material) | 287.3 |
| PRETRAIN-sim | 5 pretrain: simulated fires | 297.2 | 10.0% (8.6 to 11.5) | 28 | 0.904 (0.802 to 0.999) | helps | 296.7 |
| PRETRAIN-both | 5 pretrain: both | 287.0 | 10.0% (8.7 to 11.4) | 28 | 0.873 (0.755 to 0.986) | helps (material) | 287.5 |
| M_ref | reference GBM, no tuning | 284.9 | 9.8% (8.6 to 11.2) | 28 | 0.866 (0.745 to 0.976) | helps (material) | 281.8 |
| META | 1 meta-learning, adapted | 318.7 | 10.1% (8.5 to 12.0) | 28 | 0.969 (0.820 to 1.152) | does not help | 320.4 |
| META-init | 1 (meta-init, no adaptation) | 314.2 | 9.9% (8.4 to 11.7) | 28 | 0.955 (0.810 to 1.116) | does not help | 312.9 |
| META-pooled | 1 (pooled net, no adaptation) | 359.4 | 9.6% (8.1 to 11.3) | 28 | 1.093 (0.877 to 1.352) | does not help | 350.7 |
| KALMAN | 2 per-fire Kalman, adapted | 493.1 | 9.8% (8.6 to 11.1) | 28 | 1.499 (1.085 to 2.004) | does not help | 489.1 |
| KALMAN-twin | 2 (twin, no adaptation) | 415.4 | 10.0% (8.7 to 11.3) | 28 | 1.263 (0.935 to 1.677) | does not help | 414.7 |

**Which methods failed.** PERSIST (last h hours repeated), KALMAN (per-fire Kalman adaptation), KALMAN-twin (its non-adaptive
base), META (Reptile with adaptation), META-init and META-pooled (the same networks without adaptation) **do not help**: their
ratio intervals include 1 or lie above it. KALMAN is the clearest failure: its predictive distribution is Gaussian in log
reach, so its 90% quantile explodes when the inputs are unusual (section 4). Pretraining on archive fires, on simulated
fires, or on both does not beat the same model trained without them (section 3). EVT's tail model adds nothing over its
constant-scale twin (1.035, 0.996 to 1.086). The forecast-regime rule alone (REGIME) passes the frozen rule but its gain
vanishes at equal miss (above). Nothing was tuned after a held-out result was seen.

![Equal-miss frontier](fig/fig1_frontier.png)

## 1. Step 1 gate: oracle ceiling and learning curve

All ORACLE rows use the fire's future hours and are not a result for any method. Gain = 1 - area(oracle) / area(FIXED at 10%),
FIXED area 329 km2 at 9.8% miss. Blocks are consecutive eligible hours of one fire; "random" draws the same block sizes
from random hours of the same fire (the control for in-sample optimism). Scale only (shape s = 1).

| Oracle (scale per block) | Miss | Area | Gain vs FIXED (95%) | Same with random blocks |
|---|---|---|---|---|
| O-fire | 9.1% | 366 | -11.2% (-30.5 to +7.6) | -11.2% |
| O-day | 9.2% | 248 | +24.5% (+9.1 to +40.5) | -0.5% |
| O-6h | 9.2% | 151 | +54.1% (+43.7 to +65.6) | +14.8% |

- **The pre-registered gate statistic is O-day, per-fire budget: gain 24.5% (9.1 to 40.5), above the 10% threshold. Gate passed.**
- Its random-block control gains -0.5%, so the gain is time structure, not fitting 10% quantiles in-sample.
- O-fire (one scale per fire) gains **-11%**: giving every fire its own 10% is a worse use of the miss budget than one pooled
  margin. Fire-level adaptation has no headroom here.
- The gain grows without bound as blocks shrink (O-6h: 54%, and 14.8% even with random blocks). A ceiling that adapts
  every few hours is not informative; the 24 h block is the one the gate was fixed on, in the protocol, before any value.
- Amendment 2 (after seeing the above): the per-fire budget oracle is not a ceiling because it does worse than the
  non-adaptive M_ref when stacked on M_ref (291 against 285 km2). The pooled-budget oracle (minimum area subject to 10% miss
  over all fires, a constant scale is a feasible point) is reported beside it: O-day 59.0% (46.4 to 68.7) with random-block
  control 28.9%; O-fire 14.4% (-5.6 to 34.8). Both versions pass the gate; no decision rests on the second.
- Against it, the best causal method here, QUANTILE, gains 15.4% against the same baseline.

**Learning curve** (M_ref = gradient-boosted 90% quantile, fixed settings, no tuning; training fires drawn at random from the 24
available in each fold, 10 draws per size except n = 24):

| Training fires | Miss FIXED / PERSIST / M_ref | Area FIXED (km2) | Area M_ref (km2) | M_ref / FIXED at the calibrated margin (95%) | M_ref / FIXED read at held-out 10% |
|---|---|---|---|---|---|
| 4 | 10.4% / 9.8% / 10.0% | 343 | 299 | 0.873 (0.781 to 0.979) | 0.848 |
| 8 | 10.9% / 9.7% / 9.6% | 319 | 293 | 0.919 (0.806 to 1.039) | 0.851 |
| 12 | 10.1% / 9.8% / 9.3% | 331 | 296 | 0.894 (0.777 to 1.006) | 0.851 |
| 16 | 9.9% / 9.7% / 9.6% | 332 | 289 | 0.871 (0.754 to 0.980) | 0.852 |
| 20 | 9.8% / 9.7% / 9.4% | 333 | 290 | 0.871 (0.753 to 0.986) | 0.849 |
| 24 | 9.8% / 9.9% / 9.8% | 329 | 285 | 0.866 (0.744 to 0.975) | 0.862 |

The ratio of M_ref to FIXED read at held-out 10% miss is 0.85 at every size. The slope of log ratio against log n over n = 8..24 is
+0.007 (flat); the fire-bootstrap interval of the same slope on the calibrated area is -0.109 to +0.001. Skill saturates by
about 8 fires, so more fires of this kind is not the missing ingredient. (n = 4 to 6 use leave-one-fire-out calibration inside the
subset, per Amendment 2.) ![Learning curve](fig/fig2_learning_curve.png)

## 2. What does adapting to the fire add? (paired by fire, same held-out fires)

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

Using the fire's past as an input (QUANTILE-own against FIXED) lowers area by 14%. Updating a model per fire on top of that
does not: META against META-init, KALMAN against its twin, and nothing is gained by the extra 'forecast' features once the
past is in (QUANTILE against QUANTILE-own: 0.983, 0.947 to 1.026).

## 3. The six method families, one line each (details in PROTOCOL section 5)

1. **Meta-learning (Reptile).** Does not help (0.969, 0.820 to 1.152). The meta-initialisation without adaptation (0.955) is as
   good; the pooled network it started from (1.093) is worse, so meta-training itself helped a little and adaptation not at all.
2. **Low-dimensional per-fire update (Kalman).** Fails: 1.499 (1.085 to 2.004), worse than its non-adaptive twin (1.263).
   The wind-alignment factor of the task text was not testable on a scalar reach and was replaced by a wind-speed slope.
3. **Quantile loss at the target.** Helps, material: 0.846 (0.737 to 0.946). Linear and boosted models were both available to
   inner cross-validation; inner cross-validation chose boosted trees on all features at tau 0.9 (depth 2 or 3, 100 iterations) in all 7 folds (`derived/step2/QUANTILE_h5.json`).
4. **Forecast regime.** REGIME helps on the frozen rule (0.949, 0.923 to 0.976) but only through a 10.9% miss rate; at equal miss
   it is equal to FIXED. Adding an own-past quantile model inside each regime (REGIME+own, 0.860) gives the same as QUANTILE-own
   (0.999, 0.988 to 1.011): the forecast regime adds nothing once the past is in.
5. **Pretraining.** Archive (19 US Choi fires): 0.880. Simulated fires: 0.904. Both: 0.873. Without pretraining (M_ref): 0.866.
   None beats it (paired ratios 1.015, 1.043, 1.007 with intervals that include 1). The simulator is a toy (section 7).
   FIRED and GlobFire could not be used (section 7).
6. **Peaks over threshold.** EVT 0.876 (0.754 to 0.999) against its constant-scale twin 0.846: no gain from covariates in the
   tail. On 25 March it extrapolates the scale (margins up to 69 km), see section 5.

## 4. Why KALMAN fails (MEASURED description, not tuned)

KALMAN is a ridge regression of log(reach + 0.375) on all features with a Gaussian predictive 90% quantile. Its non-adaptive
twin is already worse than the fixed margin (1.263), because exponentiating a Gaussian quantile in log space overshoots on
the many hours when the regression is wrong by a factor; the per-fire update then moves the offset in the wrong direction as often
as the right one (13 of 28 fires lower, median per-fire ratio 1.04). This is a failure of this implementation, not a proof
that no Kalman update could work; it was not changed after the result was seen.

## 5. Sealed transfer test: Korea, and 25 March 2025

Models were fitted and calibrated on all 28 California fires (the archive too, for PRETRAIN-archive and -both) and applied once.
KR = 12 Korean fires with Choi arrival rasters, 756 issue hours, one product different from GOFER (kriged arrival times).

| Method | Area at the California-calibrated margin (km2) | Miss, 95% interval | Missed hours | Area / FIXED (95%) | Area read at held-out 10% |
|---|---|---|---|---|---|
| FIXED | 90.3 | 4.5% (0.5 to 10.4) | 61 of 756 | 1.00 (1.00 to 1.00) | 52.1 |
| PERSIST | 212.2 | 2.7% (0.4 to 5.6) | 37 of 756 | 2.35 (1.31 to 3.35) | 132.5 |
| QUANTILE | 141.7 | 3.0% (0.7 to 5.9) | 38 of 756 | 1.57 (1.20 to 1.90) | 62.8 |
| QUANTILE-own | 122.3 | 3.4% (0.9 to 6.6) | 43 of 756 | 1.35 (0.99 to 1.64) | 75.2 |
| QUANTILE-fc | 147.5 | 2.2% (0.3 to 5.6) | 31 of 756 | 1.63 (1.32 to 1.93) | 70.6 |
| REGIME | 114.8 | 3.8% (0.5 to 8.8) | 52 of 756 | 1.27 (1.17 to 1.38) | 50.2 |
| REGIME+own | 147.4 | 3.3% (0.9 to 6.0) | 37 of 756 | 1.63 (1.07 to 2.08) | 79.4 |
| EVT | 192.7 | 2.4% (0.3 to 5.9) | 32 of 756 | 2.13 (1.18 to 3.03) | 107.5 |
| EVT-twin | 153.2 | 2.5% (0.3 to 5.9) | 34 of 756 | 1.70 (1.17 to 2.15) | 74.9 |
| PRETRAIN-archive | 114.5 | 3.5% (0.9 to 6.5) | 39 of 756 | 1.27 (0.81 to 1.62) | 72.8 |
| PRETRAIN-sim | 98.1 | 11.1% (5.7 to 17.0) | 56 of 756 | 1.09 (0.77 to 1.36) | 103.5 |
| PRETRAIN-both | 121.9 | 3.8% (1.0 to 7.2) | 45 of 756 | 1.35 (0.94 to 1.73) | 74.4 |
| M_ref | 166.7 | 2.5% (0.7 to 4.6) | 31 of 756 | 1.84 (1.34 to 2.28) | 63.8 |
| META | 179.1 | 4.2% (1.3 to 7.4) | 59 of 756 | 1.98 (1.25 to 2.58) | 124.4 |
| META-init | 272.1 | 5.0% (0.8 to 11.3) | 30 of 756 | 3.01 (1.08 to 5.15) | 208.8 |
| META-pooled | 176.7 | 4.1% (1.2 to 7.4) | 58 of 756 | 1.96 (1.27 to 2.55) | 110.4 |
| KALMAN | 513.5 | 6.2% (2.4 to 11.1) | 52 of 756 | 5.68 (1.59 to 9.36) | 326.5 |
| KALMAN-twin | 350.7 | 9.7% (4.7 to 15.9) | 59 of 756 | 3.88 (0.71 to 7.43) | 344.0 |

- Every learned method flags **more** area than the fixed margin at the California-calibrated 10%. Most miss less than the
  fixed margin on Korea (2% to 4% against 4.5%), so they are conservative where Korea is calmer. At the held-out 10% (last
  column) none beats FIXED either (FIXED 52.1 km2; REGIME 50.2 is the lowest). This is **no transfer**. Why is not tested here
  (the product, the climate and the fire regime all differ).

### 25 March 2025 (Gyeongbuk, KFS_01), hour by hour, 5 h ahead

Detection product (FIRMS VIIRS + Himawari AHI), 23 complete issue hours. Margin q at each issue hour uses only the features
and outcomes available at that hour (forecast as issued with the 5 h availability delay; reach history from the detection
product). Counts only: one fire, one day. Area is capped at q = 60 km, so the very large margins below cap at that value.

| KST | reach (km) | FIXED | PERSIST | QUANTILE | REGIME | EVT | META | KALMAN | PRETRAIN-archive |
|---|---|---|---|---|---|---|---|---|---|
| 08 | 2.2 | 2.9 h | 1.4 **M** | 4.3 h | 3.6 h | 5.4 h | 2.0 **M** | 7.9 h | 3.1 h |
| 09 | 2.2 | 2.9 h | 1.4 **M** | 4.4 h | 3.6 h | 5.6 h | 2.1 **M** | 9.8 h | 3.4 h |
| 10 | 4.9 | 2.9 **M** | 1.4 **M** | 4.5 **M** | 3.6 **M** | 5.7 h | 2.2 **M** | 9.2 h | 3.3 **M** |
| 11 | 6.6 | 2.9 **M** | 1.4 **M** | 4.5 **M** | 3.6 **M** | 5.8 **M** | 2.4 **M** | 8.0 h | 3.3 **M** |
| 12 | 12.4 | 2.9 **M** | 8.1 **M** | 6.8 **M** | 3.6 **M** | 7.0 **M** | 6.9 **M** | 15.9 h | 6.8 **M** |
| 13 | 23.9 | 2.9 **M** | 8.1 **M** | 6.9 **M** | 3.6 **M** | 7.3 **M** | 7.9 **M** | 15.4 **M** | 6.8 **M** |
| 14 | 34.7 | 2.9 **M** | 8.1 **M** | 6.2 **M** | 3.6 **M** | 7.5 **M** | 6.7 **M** | 9.1 **M** | 6.0 **M** |
| 15 | 32.9 | 2.9 **M** | 16.0 **M** | 9.7 **M** | 3.6 **M** | 9.8 **M** | 9.5 **M** | 28.5 **M** | 8.0 **M** |
| 16 | 40.1 | 2.9 **M** | 21.1 **M** | 10.1 **M** | 3.6 **M** | 11.8 **M** | 9.7 **M** | 47.4 h | 8.0 **M** |
| 17 | 38.6 | 2.9 **M** | 37.2 **M** | 10.0 **M** | 3.6 **M** | 16.8 **M** | 9.1 **M** | 197.2 h | 7.3 **M** |
| 18 | 27.3 | 2.9 **M** | 68.4 h | 10.0 **M** | 3.6 **M** | 33.4 h | 9.6 **M** | 3,078 h | 7.8 **M** |
| 19 | 20.3 | 2.9 **M** | 98.3 h | 9.9 **M** | 3.6 **M** | 69.5 h | 9.6 **M** | 21,539 h | 7.2 **M** |
| 20 | 15.7 | 2.9 **M** | 71.9 h | 9.4 **M** | 3.6 **M** | 41.7 h | 9.6 **M** | 2,835 h | 7.2 **M** |
| 21 | 6.5 | 2.9 **M** | 64.8 h | 9.4 h | 3.6 **M** | 58.7 h | 9.6 h | 7,066 h | 7.2 h |
| 22 | 4.9 | 2.9 **M** | 61.4 h | 9.2 h | 3.6 **M** | 65.4 h | 9.8 h | 4,205 h | 7.1 h |

| Method | Hours missed of 23 | Missed during 10-20 KST (the run) of 11 | Mean flagged area (km2, capped at q = 60 km) | Largest margin (km) |
|---|---|---|---|---|
| FIXED | 13 | 11 | 588 | 2.9 |
| PERSIST | 11 | 8 | 6788 | 98.3 |
| QUANTILE | 11 | 11 | 1523 | 10.1 |
| QUANTILE-own | 11 | 11 | 1241 | 9.0 |
| QUANTILE-fc | 10 | 9 | 1506 | 8.8 |
| REGIME | 13 | 11 | 773 | 3.6 |
| REGIME+own | 10 | 10 | 1823 | 12.6 |
| EVT | 7 | 7 | 5495 | 69.5 |
| EVT-twin | 9 | 9 | 1531 | 7.8 |
| PRETRAIN-archive | 11 | 11 | 1272 | 8.0 |
| PRETRAIN-sim | 13 | 11 | 1022 | 8.3 |
| PRETRAIN-both | 10 | 10 | 1529 | 10.5 |
| M_ref | 10 | 10 | 1876 | 12.8 |
| META | 16 | 11 | 1395 | 9.8 |
| META-init | 4 | 4 | 8041 | 1,065.7 |
| META-pooled | 15 | 11 | 1416 | 9.9 |
| KALMAN | 3 | 3 | 8362 | 21,539.5 |
| KALMAN-twin | 4 | 4 | 8295 | 14,362.0 |

- **Nothing saw it coming.** At 10 and 11 KST (reach 4.9 and 6.6 km) several margins held (9 of 18 at 10 KST, 4 at 11 KST), but
  the reach was still small. From 12 KST (reach 12 to 40 km) only three methods ever held: KALMAN, KALMAN-twin and META-init,
  the ones whose margin extrapolates (next point), and **no method held at 13, 14 or 15 KST** (reach 24, 35, 33 km). Leaving out
  KALMAN, META-init and PERSIST (which follows the observed reach), no margin exceeded 12 km before 16 KST.
- **The methods that held later did so by growing after the fact.** PERSIST and EVT hold from 17 to 18 KST because their
  margin is a function of the reach already seen (observed growth over the previous hours). KALMAN's margin reaches 21,539 km at 19 KST (an extrapolation of a
  log-linear model on features outside the training range); META-init reaches 1,066 km. These are failures of
  extrapolation, not forecasts: no clipping was added, per PROTOCOL section 7.
- The tree models saturate at about 10 km (QUANTILE, M_ref, PRETRAIN) and miss the same 11 hours as the fixed margin.
- The issued forecast did carry the warning: forecast 850 hPa wind of 32 m/s at 10-16 KST against a California maximum of
  30 m/s (`kcf-abstain`). The models that use it (QUANTILE-fc: 10 missed) did not turn it into a large margin, because
  a model fitted on California cannot learn a value it never saw. Abstaining (`kcf-abstain`) is the tool that used it.

## 6. h = 8 replication (identical code, DEV)

| Method | Family | Area at 10% target (km2) | Achieved miss, 95% interval | Fires | Area / FIXED (95%) | Verdict | Area read at held-out 10% |
|---|---|---|---|---|---|---|---|
| FIXED | baseline | 433.0 | 10.0% (6.5 to 14.3) | 28 | 1.000 (1.000 to 1.000) | - | 433.4 |
| PERSIST | baseline | 856.5 | 9.3% (7.9 to 10.6) | 28 | 1.978 (1.671 to 2.314) | does not help | 829.8 |
| QUANTILE | 3 quantile loss | 379.6 | 10.0% (8.6 to 11.5) | 28 | 0.877 (0.762 to 0.991) | helps (material) | 379.0 |
| QUANTILE-own | 3 (own-past features only) | 394.0 | 9.8% (8.3 to 11.4) | 28 | 0.910 (0.796 to 1.029) | does not help | 391.2 |
| QUANTILE-fc | 3/4 (issued-forecast features only) | 392.5 | 10.0% (7.7 to 12.8) | 28 | 0.907 (0.835 to 0.988) | helps | 392.4 |
| REGIME | 4 forecast regime | 396.7 | 11.2% (7.6 to 15.9) | 28 | 0.916 (0.879 to 0.958) | helps | 428.4 |
| REGIME+own | 4 regime + own-past quantile | 393.8 | 9.7% (8.3 to 11.3) | 28 | 0.910 (0.798 to 1.026) | does not help | 389.4 |
| EVT | 6 peaks over threshold | 433.3 | 9.7% (8.1 to 11.3) | 28 | 1.001 (0.832 to 1.202) | does not help | 427.3 |
| EVT-twin | 6 (constant-scale twin) | 382.1 | 10.9% (9.0 to 13.0) | 28 | 0.882 (0.779 to 0.980) | helps (material) | 395.6 |
| PRETRAIN-archive | 5 pretrain: 19 archive fires | 388.5 | 9.9% (8.3 to 11.7) | 28 | 0.897 (0.779 to 1.013) | does not help | 386.2 |
| PRETRAIN-sim | 5 pretrain: simulated fires | 437.2 | 10.0% (8.3 to 11.9) | 28 | 1.010 (0.899 to 1.124) | does not help | 436.3 |
| PRETRAIN-both | 5 pretrain: both | 395.2 | 10.0% (8.4 to 11.9) | 28 | 0.913 (0.785 to 1.048) | does not help | 394.5 |
| M_ref | reference GBM, no tuning | 409.2 | 9.7% (8.2 to 11.3) | 28 | 0.945 (0.810 to 1.086) | does not help | 402.5 |
| META | 1 meta-learning, adapted | 429.3 | 9.8% (8.0 to 11.8) | 28 | 0.991 (0.832 to 1.185) | does not help | 424.7 |
| META-init | 1 (meta-init, no adaptation) | 419.8 | 9.7% (7.9 to 11.9) | 28 | 0.970 (0.822 to 1.144) | does not help | 414.5 |
| META-pooled | 1 (pooled net, no adaptation) | 451.8 | 9.6% (7.9 to 11.5) | 28 | 1.043 (0.902 to 1.215) | does not help | 441.4 |
| KALMAN | 2 per-fire Kalman, adapted | 771.9 | 10.0% (8.3 to 12.1) | 28 | 1.783 (1.270 to 2.408) | does not help | 774.1 |
| KALMAN-twin | 2 (twin, no adaptation) | 584.0 | 9.9% (8.4 to 11.4) | 28 | 1.349 (0.983 to 1.801) | does not help | 580.5 |

The h = 8 run uses identical code and the same 28 fires. Oracle and learning curve were run at h = 5 only.

Reading (h = 8): only QUANTILE (0.877), QUANTILE-fc (0.907), REGIME (0.916, at a 11.2% miss rate: at held-out 10% its area is 428.4 against
FIXED's 433.4, no gain) and EVT-twin (0.882, 10.9% miss, read at held-out 10%: 395.6, ratio 0.91) pass the frozen rule. Every
adaptive method fails again. The gain from using the fire's recent growth and the forecast as inputs to one global model is
therefore real at both horizons but smaller at 8 h, and its size depends on which model and features are used. Paired
comparisons against the twins at h = 8 are in `derived/tables_h8.md`.

## 7. Limits

- 28 fires. Intervals are fire bootstraps (marginal, no multiplicity correction over 18 variants and about 40 comparisons); several
  verdicts are close to the edge (EVT 0.999, PRETRAIN-sim 0.999 on the upper bound).
- The 10% miss rate is hour-level and fire-weighted; area is the fire-weighted mean of per-fire mean areas, so a few large fires
  weigh more. The gain is lower on 22 of 28 fires and 0.78 without the 3 largest-area fires (`derived/per_fire_robustness_h5.json`).
  The worst fires were Kincade and Zogg (wind-driven).
- Forecast features are inherited from `kcf-abstain` (GFS or HRRR as issued, 5 h availability ASSUMED, read over 8 h also for
  h = 5). Own-past features come from the GOFER or Choi arrival grids; the Choi rasters are kriged and smoother than GOFER.
- The simulator for PRETRAIN-sim is a toy (elliptical-kernel spread, AR(1) wind, fixed a priori; its constants were set in three passes
  by comparing marginals with the archive fires, never with the 28 DEV fires). A better simulator could behave differently;
  this one did not help.
- FIRED and GlobFire were **not used**: their hosts are not on this environment's allow-list. Both are also daily products, which
  cannot give an hourly 5 h reach. The 19 US Choi fires are the larger archive that was available (NOT RUN: FIRED, GlobFire).
- The oracle numbers depend on block length and on Amendment 2, which was written after the first oracle values were seen.
- No result here says anything about margin placement by direction (wind alignment is not testable on a scalar reach).

## 8. Amendments (also in `PROTOCOL.md`)

1. Before any oracle value: the per-fire miss budget carries over between blocks (a literal 10% quantile is impossible for
   blocks under 10 hours).
2. After the first oracle values were seen: the pooled-budget oracle added beside the pre-registered one (it is the true ceiling),
   with implementation details (score floor 0.1 km, inner groups min(6, n), reach reproduction tolerance 1e-5 km).
3. Before any REGIME result was read: the regime index is the minimum, not the maximum, over the four tail probabilities
   (as in `kcf-abstain`); plus statsmodels QuantReg, warm-start detail, EVT body, Kalman prior and the list of extra
   ablation rows.

## 9. Reproduce

    # data: GOFER v0.2 (Zenodo 14642378) and Choi et al. 2026 (Zenodo 21788344); both need zenodo.org
    python build_data.py --gofer DATA/gofer/GOFER --choi DATA/choi --out WORK        # 1 minute
    python step1_oracle.py; python step1_pooled.py; python step1_curve.py            # oracle ceiling and learning curve
    python sim_fires.py --n 400 --out WORK/sim.csv.gz                                  # simulated fires
    bash run_step2.sh                                                                 # dev sweep, h = 5 (H=8 for h = 8)
    python step2_final.py --methods ...; python final_report.py 5                      # sealed Korea + 25 March
    python make_tables.py 5; python make_tables_final.py; python figures.py; python make_numbers.py
    python -m pytest -q tests                                                         # leakage tests L1, L2, L3

Scripts read WORK (the arrival grids, area curves and simulated fires; about 40 MB) from the environment variable `KCF2_WORK`.
Leakage tests: L1 (features at hour t ignore everything after t) passes; L2 (scrambling outcomes not yet known at hour t leaves
the predictions of META and KALMAN bitwise identical) passes; L3 (a deliberately leaky Kalman) fails L2 as it must; L4 (the
committed kcf-margin reach and its 6.16% leave-one-fire-out miss) reproduces: 0.06156 on the committed hours, 0.0601 on the 20,065
eligible hours.
