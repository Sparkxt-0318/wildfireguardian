# PROTOCOL: does a learned, fire-general forecast margin beat the fixed margin at equal miss rate? (kcf-adaptive2)

Frozen 2026-11-19, committed before any score, oracle value, learning curve, calibrated margin or area in this
folder was computed. Changes after this commit go in "Amendments" at the end, each with reason and time.

**Hard stop.** Sunday 22 November 2026, 12:00 Asia/Shanghai (04:00 UTC). Unfinished items are reported NOT RUN with the
reason. Pushed at least once per calendar day. **Step-1 gate** is decided within 6 hours of this commit.

## 0. Question and belief under test

`research/kcf-adaptive` found no gain from adapting a forecast to the fire's own past: over-prediction fell only when
misses rose (5 h miss 6.2% to 9.6%). The belief tested here is that it failed because (1) it adapted on each fire's own
past only, (2) it trained for average error, (3) it compared methods at unequal miss rates, (4) it had few fires.
General machine-learning methods are tried against a fixed margin and a persistence baseline, all compared at one miss rate.

### 0.1 Disclosure: what was known when these rules were written (MEASURED by reading, nothing recomputed)

- Read: `kcf-adaptive/RESULTS.md` and `PROTOCOL.md` (all numbers in them); `kcf-abstain/RESULTS.md` (including the
  25 March 2025 table: forecast gust 23 m/s, 850 hPa wind 32 m/s at 10-16 KST, reach 4.9 to 40.1 km, all hours missed by
  the fixed margin; and that a forecast-based abstain rule separated missed hours on the 28 calibration fires, AUROC 0.84);
  the `kcf-margin` protocol.
- Looked at (structure only): column names, row counts per product/role/model of `kcf-abstain/derived/hours.csv.gz`
  (69 fire series, 66,138 rows); marginal summary of its predictor columns. No outcome-by-method table was built.
- Not computed before this commit: any model fit, any per-fire oracle, any area, any learning curve, any calibration scale.
- Prior expectation (ASSUMED, written down to be checked): at equal miss rate a fixed-margin-plus-features model gains
  somewhere between 0 and 25% area; meta-learning and per-fire Kalman updates gain less than a global quantile model.

## 1. Data and splits (held out by fire, always)

**Unit of independence: the fire.** Every split, bootstrap and calibration is by fire. A fire never appears on both sides.

| set | fires | product | role |
|---|---|---|---|
| DEV | 28 GOFER v0.2 California fires 2019-21 (hourly GOES perimeters, Zenodo 14642378, sha256 96eca2e1...) | arrival grid, EPSG:3310, 375 m | **primary evaluation**, 7 outer folds |
| ARCHIVE | 19 US fires (6 held-out US2024 + 13 others) with Choi et al. 2026 kriged arrival rasters, Zenodo 21788344 | EPSG:5070, 375 m | extra training fires for item 5 only; never scored |
| KR | 12 Korean fires with Choi rasters (KFS_01 ... KFS_17 with at least one eligible hour) | EPSG:5179 | **sealed transfer test**, scored once, at the end |
| MAR25 | 25 March 2025, KFS_01, FIRMS VIIRS + Himawari AHI detection product (kcf-margin) | detections | reported separately, hour by hour |

The 10 Choi series that duplicate GOFER fires (`role = s3` in `kcf-abstain/derived/hours.csv.gz`) are dropped; the GOFER
version is the one used. KFS_01 appears in KR (Choi raster) and MAR25 (detections): it is one fire; whenever it is
held out, both versions are held out.

**Outer folds on DEV.** Fire name -> sha256 hex -> integer; sort ascending; fold = rank mod 7 (4 fires per fold).
All methods use these 7 folds. Every number for DEV is the pooled result of the 7 held-out folds.

**Nested rule.** Every choice (hyper-parameter, feature subset, threshold, shrinkage, number of steps) is made inside the
training fires of a fold by by-fire inner cross-validation (inner folds: training fires sorted by hash, 6 groups) using
the pooled criterion of section 3 at miss 10%. Grids are listed in section 5 and are the only values tried. No choice is
made on outer-fold or KR results.

**KR and MAR25.** For these, every model is fitted on all 28 DEV fires (plus ARCHIVE where the method uses it), calibrated
by the same inner procedure, and applied once. Not used to choose anything.

**Horizons.** h = 5 h is primary. h = 8 h is a replication run through identical code for the methods that complete at 5 h.

**Eligible issue hours.** An issue hour t of a fire: the known set K_t = {arrival <= t} is non-empty, t + h <= the fire's
last arrival hour, at least 3 earlier hours exist, and every feature in section 2 is non-missing. The eligible set is
identical for all methods of one run.

## 2. Outcome, margin, area

- **Reach** S_t (km): kcf-margin rule, unchanged: the largest Euclidean distance from K_t of cells that burn in (t, t+h],
  after dropping 8-connected new-burn components whose nearest cell is more than 5 km from K_t; 0 if no spread.
  GOFER reach is reproduced from the shapefile and compared with the committed `kcf-margin/derived/gofer_reach.csv.gz`
  (gate: identical to 1e-6 km on all rows; if not, stop).
- **Margin.** A method outputs q_t >= 0 (km) at each issue hour using only information available at t (section 2.2).
  The flagged zone is the set of cells outside K_t whose distance to K_t is <= q_t.
- **Miss.** An issue hour is missed if S_t > q_t. **Miss rate of a fire** = share of its eligible hours missed.
  **Miss rate of a set** = mean over fires of the fire's miss rate (each fire weight 1).
- **Area.** A_t(q) = flagged zone area in km2, computed exactly from the arrival raster (distance transform of K_t, cell
  centres, padded 70 km; q capped at 60 km). **Area of a set** = mean over fires of (the fire's mean A_t over its
  eligible hours). This is the one area number everywhere, called "area".
- **The metric: area at a 10% miss rate.** Every method is brought to a 10% target by the one calibration rule of section 3;
  its area and its achieved held-out miss rate are reported together. Area is never compared between methods whose
  held-out miss rate intervals exclude 0.10 without saying so (section 4).

### 2.1 Features (fixed list; no other feature is used)

Own-past, from the arrival grid (observed at t): g1, g3, g6, g12, g24 = reach, as defined above, of cells that burned in
(t-k, t] from K_{t-k} (0 where t-k is before the fire's start); log(1 + area of K_t in km2); log(1 + hours since the fire's
first perimeter); sin and cos of local solar hour (UTC hour + longitude/15).
Forecast as issued: gust_ms, w850_ms, rhmin_pct, hdw from `kcf-abstain/derived/hours.csv.gz` (GFS 0.25 deg or HRRR, 4
lattice points around the centroid of K_t, cycles 00/06/12/18 UTC assumed available 5 h after cycle, read over the 8 h
after t; columns are the maxima, minimum for RH). Their provenance and 5 h availability delay are inherited, not re-checked.
Outcome history for adaptive methods: S_s for issue hours s with s + h <= t only.

### 2.2 What counts as available at t

Features of section 2.1 at t, the model fitted on training fires, and outcomes S_s with s + h <= t of the same fire.
Nothing else. No ERA5/ECMWF analysis, no reanalysis wind or gust, no value after t. Future-leak tests are in section 6.

## 3. Calibration, comparison and verdict rules

**One calibration rule for every method.** A method produces a positive score s_t (km) on each training-fire hour as an
out-of-fold prediction (inner by-fire folds); the margin is q_t = kappa * s_t. kappa is the smallest value such that the
fire-weighted miss rate over the training fires' out-of-fold hours is <= 0.10. The final model is then refitted on all
training fires and used with that kappa. FIXED has s_t = 1. This is the same rule for all methods, including oracle-free
adaptive ones (their out-of-fold predictions are produced with their adaptation running).

**Achieved miss rate (held out).** Fire-weighted miss of the held-out fires; interval = fire-cluster bootstrap, 2,000
resamples, seed 20261119, percentile 95%. n fires always stated.

**Frontier-read area at 10%.** Descriptive only: kappa swept on the held-out fires; the area at exactly 10% held-out miss
by linear interpolation along the (miss, area) curve. It uses held-out outcomes and is never the primary number; it is
there so that no comparison depends on a method happening to land on 8% or 12%.

**Comparators.**
- FIXED: s_t = 1, so q = kappa, kappa at 10% (the kcf-margin margin recalibrated to 10%; also reported at its committed
  3.75 km / 6.2% value for reference).
- PERSIST: s_t = 0.375 + w * G(t), where G(t) is the observed reach over the previous h hours: for h = 5, g3 scaled by
  5/3; for h = 8, g6 scaled by 8/6. w is chosen from {0.5, 1, 2, 4} by inner CV; then kappa. It is the "next h hours look
  like the last h hours" forecast, calibrated to 10%.
- ZERO (reported, cannot reach 10%): q = 0; its miss rate is the share of hours with any spread.

**Verdict for a method M against a comparator C** (paired fire bootstrap, 2,000 resamples, seed 20261120, ratio of area):
- *valid*: held-out miss of M within 0.10 +/- 0.03 **and** its bootstrap interval contains 0.10. If not valid, M is
  labelled "miss not at target" and only its frontier-read area is discussed.
- **helps** vs C: valid, and the upper bound of the 95% interval of area(M)/area(C) is below 1.00.
- **material**: helps and the point estimate of area(M)/area(C) <= 0.90.
- **trade-off**: lower area but not valid (miss higher).
- otherwise **does not help**. A method that helps vs FIXED but not vs PERSIST is reported as such.
- Multiplicity: 6 families, 8 comparisons; no correction is applied; intervals are marginal and said to be.

## 4. Step 1: stop/go gate

### 4.1 (a) Oracle ceiling (cheating by design; labelled ORACLE, never a result for any method)

For each DEV fire the oracle sees the fire's whole outcome series including the future. It sets, within blocks of the
fire, a scale kappa_b so that the block's own miss rate is as close to 0.10 from below as the discrete values allow (the
block's reach quantile; q = kappa_b * s_t). Area and miss are then computed as above, the miss rate of the set is ~0.10
by construction.
- **O-fire**: one block = the whole fire.
- **O-day**: blocks of 24 consecutive eligible hours (calendar-free, from the fire's first eligible hour).
- **O-6h**: blocks of 6 hours (the finest; it ignores the worst hour of every block and is shown to demonstrate that the
  ceiling grows without bound as the block shrinks).
- Each with s_t = 1 (fixed shape; oracle versions of FIXED) and with s_t = the global model of section 5.3 fitted by the
  outer folds (oracle on top of a learned shape).
- **Control O-random**: same block sizes, but blocks are formed from randomly drawn hours of the same fire (seed 20261121).
  Its gain measures optimism of fitting a per-block quantile in-sample with no temporal structure; the gap O-day minus
  O-random is the time-structure headroom.

**Gate statistic.** Gain = 1 - area(O-day, s=1) / area(FIXED at 10%), at h = 5 h, DEV, 28 fires (pooled over outer folds;
FIXED is calibrated in the outer folds). **Pass if Gain >= 0.10** (point estimate). Fire-bootstrap interval for Gain and the
other oracles are reported next to it. O-day is chosen as the gate because 24 h is the shortest block that a real method
with an h-hour outcome delay could track at all, and the diurnal cycle of fire weather; O-fire and O-6h bound it
from below and above.
**If Gain < 0.10: write RESULTS.md as the result (oracle, learning curve, comparators) and stop. Step 2 is then not run.**
If the gate passes, a further read-out is made but does not stop anything: whether O-fire also gains >= 0.10 and whether
the O-day gain exceeds the O-random control by at least 0.05; both are reported in RESULTS.md as the reason to read any
later gain with care.

### 4.2 (b) Learning curve

For n in {4, 8, 12, 16, 20, 24} training fires: in each outer fold draw 10 random subsets of size n (seed 20261122) from
the 24 training fires, fit the reference model M_ref (section 5.3 with fixed hyper-parameters, no tuning) and
the comparators, calibrate by the section 3 rule using leave-one-fire-out predictions inside the n fires, and score on the
4 held-out fires. Reported: held-out area (fire-weighted over all folds, averaged over subsets), achieved miss, and
frontier-read area, with n; plus the slope of log(area ratio to FIXED) against log n, fitted over n = 8..24, as the
indicator of whether more fires would still help. Learning-curve results are descriptive and do not change any
rule.

## 5. Step 2: methods (only if the gate passes)

All score s_t > 0 then calibration of section 3. Every method has a **non-adaptive twin** where it adapts, so that adaptation
and model are separated. Features: F-own = own-past block; F-fc = forecast block; F-all = both.

5.1 **Reference grid used by several methods**: inner-CV selects over lists below; ties broken by smaller area, then by
the first listed value.

5.2 Methods:
1. **META (Reptile; MAML-first-order if Reptile fails to train).** Model: linear and 1-hidden-layer (16 units, tanh)
   predictors of log(S + 0.375) with pinball loss at tau; inputs F-all standardised. Meta-training tasks: (fire, 72 h
   window) pairs from training fires; inner loop: 5 SGD steps of rate 0.01 on the support (the up-to-48 most recent
   outcome-known hours before the window's query start), query = next 6 hours; Reptile outer step 0.1, 2,000 meta-iterations.
   Test: every 6 hours the model is adapted from the meta-initialisation with the same 5 steps on the 48 most recent
   outcome-known hours (s + h <= t) and used for the next 6 issue hours. Twin: the meta-initialisation without adaptation,
   and the same net trained by ordinary pooled pinball loss. tau in {0.8, 0.9, 0.95}; architecture in {linear, MLP}.
2. **KALMAN (low-dimensional per-fire adaptation).** Base: ridge regression of y = log(S + 0.375) on F-all fitted on
   training fires (ridge in {0.1, 1, 10}). Per fire, three parameters theta = (level offset = spread-rate multiplier, slope on
   standardised log forecast 850 hPa wind, slope on standardised log g_h) with prior N(0, P0), random walk with process
   variance Q in {1e-4, 1e-3, 1e-2}, observation noise variance from training residuals; the update at issue hour t uses the
   outcome y_s of every s with s + h <= t. Predictive distribution Gaussian; s_t = its 0.9 quantile mapped back through
   exp; calibration of section 3. (The "wind-alignment factor" of the task text is not testable at the scalar-reach level
   of this study: kcf-adaptive found direction carries almost nothing; the wind-speed slope replaces it. Stated, not hidden.)
   Twin: the base with theta = 0.
3. **QUANTILE.** Gradient-boosted quantile regression (scikit-learn HistGradientBoosting, loss "quantile") of S on F-own,
   F-fc, F-all, targeting tau in {0.8, 0.9, 0.95} (misses weighted 4:1, 9:1, 19:1 over over-prediction), max_depth in {2, 3},
   learning rate 0.05, iterations in {100, 300}, min samples per leaf 200; plus linear quantile regression on the same
   features (statsmodels/scikit QuantileRegressor with L1 alpha 1e-4). Fire-clustered by-fire inner CV only. Reference model
   **M_ref** of the learning curve and of the O-oracles: GBM, F-all, tau 0.9, depth 3, 300 iterations (fixed, no tuning).
4. **REGIME (forecast-selected two-regime).** An index z_t = max over the four forecast variables of their training-fire
   fire-weighted tail probabilities (as in kcf-abstain: share of training hours at least as dangerous) is computed from the
   issued forecast only. Regime 2 if z_t <= c, c in {0.005, 0.01, 0.02, 0.05, 0.1, 0.2}; each regime gets its own constant
   margin (s_t = 1 in regime 1, s_t = m in regime 2, m in {1, 1.5, 2, 3, 5} chosen jointly with c), then kappa. No feature
   of the fire's own past enters the regime choice. Variants: + own-past quantile model inside each regime (QUANTILE on
   F-own).
5. **PRETRAIN.** (a) ARCHIVE: M_ref fitted on ARCHIVE fires (19 US Choi fires; and for the KR test also none of KR) then
   fine-tuned on the training DEV fires (50 more boosting iterations, learning rate 0.02, warm start), against M_ref on DEV
   alone. (b) SIMULATED: a documented toy simulator (time-stepped elliptical-kernel spread on a 375 m grid, AR(1) wind,
   diurnal RH, ROS from a fixed wind/RH/fuel-moisture law; 400 simulated fires, 200 hours; features generated with the same
   definitions, forecast features = true weather plus noise) is pretrained, then fine-tuned as in (a). (c) both. If the
   simulator is not written in time: (b) NOT RUN. FIRED and GlobFire are not reachable (hosts are not on this
   environment's allow-list; and both are daily products, which cannot give an hourly 5 h reach); they are not used.
6. **EVT (peaks over threshold).** Hurdle model. P(S > u | x): logistic regression on F-all, u in {1.5, 3} km chosen by
   inner CV. Exceedance S - u: generalised Pareto with log-scale linear in F-all and a constant shape xi (maximum likelihood
   on training-fire exceedances; xi clipped to [0, 0.5]). The 0.9 quantile of the mixture at x is s_t: if P(S > u | x) >= 0.10 it
   is the solution of P(S > u | x) * (1 + xi (q - u) / sigma(x))^(-1/xi) = 0.10; otherwise it is min(u, the QUANTILE F-all
   tau 0.9 prediction). Then kappa. Twin: GPD with constant scale.

Hyper-parameters not named here are library defaults. Seeds: numpy 20261119 + fold index.

5.3 Compute rule: if a method cannot finish for all 7 folds by the hard stop, it is reported on the folds completed,
named, and not pooled as complete.

## 6. Leakage and sanity tests (run before any method result is read)

- L1 (structure). The function that builds features for hour t is unit-tested: values at t depend only on rasters at hours
  <= t and forecast columns of hour t; outcome history is cut at s + h <= t. Test: replace all arrival values > t by noise and
  confirm identical features.
- L2 (future scramble for adaptive methods, as in kcf-adaptive). Replace outcomes of hours s with s + h > t by noise;
  predictions for hour t must be bitwise identical, for META and KALMAN, on at least 5 fires.
- L3 (positive control). A deliberately leaky KALMAN (observation of S_t itself at t) must fail L2 and its score is printed once as LEAKY, NOT A RESULT.
- L4 (reproduction). GOFER reach reproduced; FIXED at the committed 3.75 km reproduces the committed LOFO miss rate
  (6.16%) when calibrated in LOFO form.

## 7. MAR25 (25 March 2025 KST, issue hours 00-23, h = 5 and 8)

Every method (calibrated on all 28 DEV fires, models fitted on DEV (and ARCHIVE where the method uses it); KFS_01 is in
neither) is run at every issue hour using only features and outcomes available at that hour (own-past from the detection
product; forecast as issued in the kcf-abstain table). Reported per hour: q (km), reach, held or missed, and area; summary
counts per method (hours missed, mean area). One fire, one day: counts only, no rate or interval is claimed. A method with
a feature outside the training range is reported as is (trees saturate, linear models extrapolate); no clipping is added
after seeing the result.

## 8. Reporting

`RESULTS.md` has **one main table**: method, area at 10% miss rate, achieved miss rate with interval, number of fires
(plus the ratio to FIXED with its interval and the verdict). Failed methods are named as failed. Everything is labelled
MEASURED, ASSUMED, ORACLE, or NOT RUN with the reason. All numbers live in `numbers.json`. A data source that cannot be
reached is reported and skipped.

## Amendments

(none yet)
