# PROTOCOL: does adapting to the fire's own recent behaviour help? (kcf-adaptive)

Frozen 2026-11-18, committed before any adapted prediction, adapted margin, directional score or wind value
was computed. Changes after this commit go in "Amendments" at the end, each with its reason and time.

**Question.** Two things in this repo are fixed once and then applied to every fire: the weights of forecast
checkpoint c651, and the circular reach margin R(h) of `research/kcf-margin`. Does adapting either one to the
fire in front of it, using only what that fire has already done, reduce over-prediction (area flagged per
cell actually burned) without raising the miss rate? If neither arm helps, that is the result.

**Hard stop.** Saturday 21 November 2026, 18:00 Asia/Shanghai (10:00 UTC). Anything not finished by then is
reported as NOT RUN with the reason. No rule below is changed to finish sooner.

## 0. Disclosure: what was known when these rules were written

- Read: the committed results of kcf-margin, kcf-gust and kcf-abstain (including every 25 March 2025 reach value
  and which hours failed), and of the frozen forecast study: c651_mc pooled Brier 0.0098522 against persistence
  0.0049968 on the six US fires, 273 windows (`harness-2026-11/S-D9/derive/C651_DEV.md`). These motivate the study.
- Opened: the 273 committed case files, for structure only (grid shapes, cut-off and end times, that each
  window's burned-at-cut-off set equals the previous window's end state: 235 of 235 consecutive pairs). The c651
  parameter list had not yet been printed (torch was still installing); section 2.3 names the sets by role.
- Not computed or looked at: any adapted prediction or score, any directional score, any wind value for any
  fire, any adaptive margin.
- Data reachable at the freeze: GOFER v0.2 and the Choi et al. 2026 rasters (Zenodo, checksums verified). The
  Open-Meteo archive answered HTTP 429 (shared daily quota exhausted). Section 6 fixes what happens if it stays so.

## 1. Prior work (searched 2026-11-18; the three closest)

Inspiration is test-time adaptation of model weights: SEAL (Zweiger et al., arXiv 2506.10943), where a model
produces its own fine-tuning data and updates, and SIA (arXiv 2605.27276), where an agent decides when to
update weights (LoRA) from task feedback. In fire science the same idea is called data assimilation with
parameter estimation. Closest works:

1. **Rochoux, Ricci, Lucor, Cuenot, Trouvé (2014)**, "Towards predictive data-driven simulations of wildfire
   spread - Part I: Reduced-cost Ensemble Kalman Filter based on a Polynomial Chaos surrogate model for parameter
   estimation", NHESS 14, 2951-2973, doi:10.5194/nhess-14-2951-2014. Rate-of-spread model parameters of a front
   solver (FIREFLY) are re-estimated from the fire's own observed front positions, then used to forecast. Tested
   on synthetic cases and one controlled grass burn. Closest to Arm 1 in logic: estimate a few parameters from
   this fire's past, then predict.
2. **Srivas, de Callafon, Crawl, Altintas (2017)**, "Data Assimilation of Wildfires with Fuel Adjustment Factors
   in FARSITE using Ensemble Kalman Filtering", ICCS 2017 DDCS workshop (extends their 2016 Procedia Computer
   Science 80, 897-908 paper; Subramanian et al., ICCS 2020, adds wind speed and direction). An operational
   simulator's per-fuel rate multipliers and its perimeter are updated from earlier observed perimeters of the
   same fire (2014 Cocos fire, 2016 Sand fire). Closest to Arm 1 in the kind of parameter adapted (a small set
   of rate multipliers).
3. **Cheng, Jin, Harrison, Quilodran-Casas, Prentice, Guo, Arcucci (2022)**, "Parameter Flexible Wildfire
   Prediction Using Machine Learning Techniques: Forward and Inverse Modelling", Remote Sensing 14(13), 3228,
   doi:10.3390/rs14133228. A learned surrogate of a fire simulator whose parameters are tuned online, by an
   inverse model with latent data assimilation, on fires not seen in training (two California fires, satellite
   observations). Closest to Arm 1 in setting: a learned spread model adapted at test time.

For Arm 2 no fire work was found that updates a spatial margin online from the fire's own misses. The nearest
is conformal risk control for pixel-level spread maps (arXiv 2603.22331: a fixed, not adaptive, miss bound).
The method is Gibbs and Candes (2021), "Adaptive conformal inference under distribution shift", NeurIPS 34.
The wind-driven ellipse with the source at its rear focus is the standard fire-shape model (Van Wagner 1969;
Anderson 1983); the length-to-breadth relation used is Alexander (1985) as in the Canadian FBP system.
What is not in these works, and is tested here: (a) adapting a few parameters of a learned kernel model by
gradient steps on the fire's own earlier survey intervals, scored on real held-out fires with a leakage test;
(b) online conformal resizing of a wind-shaped evacuation margin.

## 2. Arm 1: test-time adaptation of c651

### 2.1 Cohort and inputs

The 273 windows of the six held-out US 2024 fires exactly as committed in
`forecast/runs/20261030_perimeter_trained/execution_v3/heldout/cases` (Wapiti 52, Goat 42, Lava 47, RedRock 40,
Pioneer 55, FishCreek 37). A window has a cut-off (the **issue time**), an end time, scored cells (all cells of
the fire's rectangle not burned at cut-off; no cell is excluded in any window) and a label y per scored cell.

- **Burned state at cut-off** is taken from the committed case file: every rectangle cell that is not a scored
  cell. This is the frozen study's own input state.
- **Environment** is one snapshot per window at the cut-off hour floored to the hour (the committed
  `weather_hour`, never later than the cut-off), 19 channels as c651 reads them: 2 m temperature and 10 m wind
  (ECMWF IFS through the Open-Meteo archive, by `research/forecast-v2/scripts/rebuild_environment.py`), slope
  and tree cover and biome (`harness-2026-11/data-fetch/us2024_static`). The original aligned inputs are
  owner-local and cannot be reproduced byte for byte, so these are **REBUILT inputs**.
- **Reproduction gate (before any adapted score).** Unadapted c651, mean-field rollout, on the rebuilt inputs is
  compared cell by cell with the committed `p_c651_meanfield` on all 273 windows. Reported: maximum and median
  absolute difference and both pooled Brier scores. If the two pooled Brier scores differ by more than 2%
  (relative), every Arm 1 number is labelled **REBUILT-INPUT c651, not the scored c651**. The run continues
  either way; the paired comparison below is on identical inputs.

### 2.2 The rule that keeps the future out

For a window with issue time T, the **history** is that fire's windows whose end time is <= T. Only the
history (its cut-off states, its cut-off-hour environment snapshots, its labels) and the target window's own
cut-off state and cut-off-hour environment enter adaptation and prediction. The target window's labels, every
later window, and every weather hour after T do not. The rectangle and static layers are fixed per fire.
(Inherited caveat, not new here: the rectangle is the Choi grid, drawn around the final footprint.)

### 2.3 What is adapted, and how (fixed)

- **P4 (primary):** the four branch-mixing coefficients of c651 (`mixing_logits`; one nonnegative weight per
  kernel branch 3x3, 5x5, 7x7, 9x9). They set how fast the fire is expected to spread and over what reach.
- **P+ (secondary):** P4 plus the bias vector of the last layer of each branch's kernel generator (one number
  per kernel offset: 9 + 25 + 49 + 81 = 164), which lets the kernels take a fixed direction for this fire.
- Everything else in the 210,344-parameter checkpoint is frozen. Each window starts again from c651.
- History used: the **8 most recent** history windows (fewer if fewer exist). A window with no history is
  predicted by unadapted c651 and stays in every total.
- Objective: mean over the history windows of the window's Brier score (mean-field rollout from the window's
  cut-off to its end, c651's own step rule: whole hours then the remainder, absorbing, zero boundary), plus
  0.01 x squared distance of the adapted parameters from their c651 values.
- Optimiser: Adam, learning rate 0.05, 60 steps, float64, no early stopping, no per-fire tuning.
- Prediction: mean-field rollout of the adapted model on the target window.

### 2.4 Comparators

1. **Unadapted c651, mean-field, same rebuilt inputs** (the paired comparator).
2. **Persistence** (no new burning; p = 0).
3. For context only (different inputs, not paired): committed `p_c651_mc` and `p_c651_meanfield`.
4. **Output-level adaptation (1-F), always run.** No weights change. The committed `p_c651_meanfield` is
   rescaled as p' = 1 - (1 - p)^c with one number c > 0 (a multiplier on the cumulative hazard), fitted on the
   same history by the same Brier objective with penalty 0.01 (ln c)^2, c in [e^-5, e^5]. Its comparator is the
   committed `p_c651_meanfield`. It is labelled OUTPUT-LEVEL and is not the requested test; it is the fallback
   of section 6 and shows what a one-number rate correction buys.

### 2.5 Scores

Population: all 273 windows, all scored cells (the frozen study's 1,705,079 entries), pooled.
- **Brier score**, pooled. Paired differences with a whole-fire bootstrap (10,000 draws, seed 20261030,
  6 fires, the convention of S-D9). Per-fire values listed. Also on the 267 windows that have history.
- **Calibration:** reliability table on bins [0, 0.001), [0.001, 0.01), [0.01, 0.1), [0.1, 0.5), [0.5, 1]
  (count, mean prediction, observed frequency); expected calibration error on those bins; the lowest-bin gap;
  and the ratio (sum of predictions) / (number of burned cells).
- **Over-prediction and misses.** Primary, threshold-free: expected area flagged per cell burned = sum of p
  over scored cells / number of burned cells; expected miss rate = mean of (1 - p) over burned cells.
  Secondary: flagging p >= 0.01, 0.05, 0.1, 0.5: flagged cells per burned cell and share of burned cells not
  flagged; and flagged cells per burned cell at the thresholds where each model misses 10% and 20% of burned
  cells (thresholds read from the same data, so descriptive only).

### 2.6 Verdict rule (Arm 1)

Adaptation **helps** if, for P4 against comparator 1: the bootstrap 95% interval of the Brier difference lies
below 0, the expected area flagged per cell burned is lower, and the expected miss rate is not higher.
If area is lower but misses are higher: **trade-off, not help**. Otherwise: **does not help**. Separately
stated: whether adapted c651 beats persistence on Brier (interval below 0), which unadapted c651 did not.

### 2.7 Leakage test (run on all 273 windows, both parameter sets)

- **L1, structure.** Adaptation receives a history object built by one function that drops every window ending
  after T and raises if asked otherwise. Unit-tested.
- **L2, future-scramble invariance.** Everything at or after each window's issue time is replaced: the target
  window's labels and every later window's labels are redrawn at random, later windows' cut-off states are
  redrawn, and environment snapshots after T are replaced by noise. Adaptation and prediction are run again.
  **Pass** = adapted parameters and predictions identical to the unscrambled run in every window (bitwise).
- **L3, positive control.** A deliberately leaky variant (the target window is added to its own history) is put
  through L2. It must **fail** L2. Its score is printed once, labelled LEAKY, NOT A RESULT, to show what leakage
  would have looked like.
If L2 fails for the real method, Arm 1 results are withheld until fixed.

### 2.8 25 March 2025 and Arm 1

The frozen Korean cohort holds no scorable c651 window on 25 March KST: the KFS_01 windows starting 24 March
21:00 and 25 March 09:00 UTC are UNAVAILABLE ("no common supported cells"). Arm 1 is therefore **NOT TESTED** on
25 March, and no substitute is built. 1-F is run on the 26 scored Korean windows as a descriptive check only.

## 3. Arm 2: adaptive directional margin

### 3.1 Fires, reach, issue hours (kcf-margin, unchanged)

- **Calibration fires:** the 28 GOFER v0.2 fires, EPSG:3310, 375 m cells, hourly cumulative perimeters, the
  kcf-margin 5 km separate-fire rule, horizons h = 5 and 8 h, issue hours as kcf-margin. `reach.py` is imported,
  not copied. Evaluation is leave-one-fire-out (LOFO).
- **Korean fires, test only:** every Korean fire with a Choi et al. arrival raster and at least one eligible
  issue hour (the kcf-abstain rule and code), and **25 March 2025** on the kcf-margin detection product
  (FIRMS VIIRS + Himawari AHI, issue hours 00-23 KST, rows flagged complete). Nothing Korean sets anything.
- **Gate:** the fixed circular arm must reproduce kcf-margin's committed R (3.75 km, 5.03 km at 10%) and LOFO
  miss rates (0.0616, 0.0662). If not, stop and report.

### 3.2 Wind (what is known at the issue hour)

W_t = ERA5 10 m wind speed and direction (Open-Meteo archive) at the centroid of the fire's **first** known
burned set, **at the issue hour t only**, held fixed over the window. ASSUMED: reanalysis at the issue hour
stands in for an observation available then. No wind value after t is used by any headline arm.
Sensitivity, labelled **ASSUMED PERFECT FORECAST**: the mean wind vector over (t, t+h].

### 3.3 Shape

Downwind direction d (the way the air moves). Elongation from Alexander (1985):
LB = min(1 + 8.729 (1 - exp(-0.030 U))^2.155, 8), U in km/h; e = sqrt(1 - 1/LB^2).
Reach in direction theta (angle from d), per unit size:
g(theta) = (1 - k) + k (1 - e) / (1 - e cos theta), 0 < g <= 1, g(0) = 1.
k = 0 is the circle; k = 1 is the fire ellipse with the source cell at its rear focus.
- **Zone of size q:** every cell x outside K_t for which some known cell c has |x - c| <= q g(angle of x - c).
  Built as a raster dilation of K_t by that shape (cell centres), so the zone and the score agree exactly.
- **Score of an issue hour:** the smallest q whose zone contains every spread cell of (t, t+h]; 0 if no spread.
  For k = 0 this is the kcf-margin reach.
- **k is chosen without the held-out fire:** from {0.25, 0.5, 0.75, 1.0}, the value with the smallest
  fire-weighted mean flagged area over the 27 training fires' hours when each shape is sized by its own static
  conformal q (10% target, h = 5 h). Korean fires use the k chosen on all 28. One k for both horizons and all
  targets. The chosen k is reported per fold.

### 3.4 Size

- **Static:** kcf-margin's `conformal_R` on the arm's scores (one random hour per fire, 2,000 draws, seed
  20261116, median), from the other 27 fires (all 28 for Korean fires).
- **Adaptive (ACI, Gibbs and Candes 2021), with honest delay.** Each fire starts at a_1 = alpha. The outcome
  of the margin issued at hour s is known only at s + h. At issue hour t, for every earlier issue hour s whose
  outcome has just become known (s + h <= t, not yet used): a <- a + gamma (alpha - err_s), err_s = 1 if that
  margin was exceeded, else 0. The size is q_t = Q(1 - a_t), where Q is the fire-weighted quantile of the
  calibration fires' pooled hourly scores (each fire's hours share weight 1). a_t >= 1 gives q = 0. a_t <= 0
  gives the largest calibration score (**saturated**; plain ACI would flag everything; saturated hours are
  counted and the ACI long-run guarantee does not cover them). a_t itself is not clipped.
  gamma = 0.005 (the published default) is the headline. Sensitivity: gamma = 0.02 and 0.05.
- **Reference row:** static Q(1 - alpha) (gamma = 0), to separate adaptation from the change of quantile rule.
- **Secondary, unbounded tracker:** ln q <- ln q + eta (err - alpha), same delay, started at the static q;
  eta = 0.05 and 0.2. It can grow past the calibration range, which ACI on a finite calibration set cannot.

### 3.5 Arms

| arm | shape | size |
|---|---|---|
| FIXED-CIRC (the baseline, kcf-margin) | circle | static |
| FIXED-DIR | wind-aligned | static |
| ADAPT-CIRC | circle | ACI |
| **ADAPT-DIR (the proposal)** | wind-aligned | ACI |

Targets alpha = 0.10 (headline) and 0.20. Horizons 5 h and 8 h.

### 3.6 Scores

Per fire f, over its issue hours: flagged area A_t = cells of the zone outside K_t; spread cells n_t.
- **Over-prediction:** OP_f = sum of A_t / sum of n_t (area flagged per cell actually burned). Reported as
  the fire-weighted mean over fires with any spread, and pooled. Mean flagged area per hour (km2) beside it.
- **Miss rate:** hour level, as kcf-margin (share of the fire's hours with a spread cell outside the zone;
  fire-weighted mean; Clopper-Pearson 95% on the sum of fractions over n fires). Cell level: share of spread
  cells outside the zone.
- **Differences against FIXED-CIRC:** paired fire bootstrap, 2,000 resamples, seed 20261119.
- **At equal miss rate:** every arm is also run at alpha in {0.02, 0.05, 0.10, 0.15, 0.20, 0.30}; over-prediction
  is compared at equal realised hour-level miss rate by linear interpolation along each arm's curve.
- Fastest hours: miss rate in the top decile of prior-3 h spread (kcf-margin definition i).
- Korean fires: counts per fire (hours, misses, flagged area, burned cells), never a rate for one fire.

### 3.7 Verdict rule (Arm 2), per horizon at alpha = 0.10

An arm **helps** if its over-prediction difference against FIXED-CIRC has a 95% interval below 0 and its
fire-weighted hour-level miss rate is not higher than FIXED-CIRC's. Lower area with a higher miss rate is a
**trade-off, not help**; the equal-miss comparison then says which way it falls. Otherwise **does not help**.
The 2 x 2 design says whether any gain comes from the shape, from the adaptation, or from both.

### 3.8 25 March 2025, reported separately

Hour by hour for issue hours 00-23 KST on the detection product, all four arms plus the unbounded tracker:
size, zone area, held or missed. Because the detection product covers only that day, the adaptive state at
00 KST is run two ways: cold start (a = alpha), and warm start from the adaptive state reached at that hour on
the KFS_01 Choi raster (which begins 22 March). **"Could adaptation have seen the run coming"** is answered by:
(i) the first issue hour at which each adaptive arm's size differs from its starting size, against the first
missed hour; (ii) whether any adaptive arm held at an hour where FIXED-CIRC missed; (iii) the hour, if any,
from which an adaptive arm holds again. An arm that only grows after its own misses become known did not see
it coming; that is stated as such.

## 4. Labels

Every number is MEASURED (computed here from data) or ASSUMED (an input or proxy). No guarantee is claimed
for any single fire or hour. n is always stated; the unit is the fire (6 in Arm 1, 28 in Arm 2).

## 5. Tests and reproduction

`tests/`: leakage L1 and the L2/L3 machinery on a synthetic fire; ACI update and delay (a margin's outcome is
never used before s + h); shape (g(0) = 1, k = 0 equals the Euclidean reach, zone and score agree); and the
kcf-margin reproduction gate. `run_all.sh` regenerates every number; all numbers live in `numbers.json`.

## 6. If data cannot be obtained before the hard stop

- **Open-Meteo unavailable for the six US fires' weather:** weight-level Arm 1 (P4, P+) is NOT RUN. 1-F
  (output-level, needs no weather) is then the only Arm 1 result and is labelled as not the requested test.
- **Open-Meteo unavailable for wind:** FIXED-DIR and ADAPT-DIR are NOT RUN. FIXED-CIRC and ADAPT-CIRC (which
  need no wind) are run and reported. No other wind source is substituted after the freeze without an amendment
  made before any directional score is computed.
- A partial fetch (some fires) is reported on the fires obtained, named, and never pooled as if complete.

## Amendments

1. **2026-11-18 16:15 UTC, before any weight-level score existed.** While the first adaptation runs were
   starting, their progress lines showed the fitted offsets of the mixing coefficients in the first few windows
   (about 0.001 to 0.04 in size). No prediction of an adapted model had been scored or looked at. The offsets are
   small because the frozen penalty (0.01 x squared distance) is in absolute units while the Brier objective is
   of order 0.01, so the penalty dominates. **Nothing frozen is changed:** P4 and P+ with penalty 0.01 remain the
   primary and secondary results and the verdict rule of 2.6 applies to P4 at 0.01 only. **Added, labelled
   SENSITIVITY (not part of the verdict):** P4 with penalty 0.001 and with penalty 0.0001, everything else as
   frozen. They show whether a looser leash changes the answer. The leakage test L2 covers the same code path
   (the penalty is one number in the objective) and is not repeated for them.
2. **2026-11-18, consequence of the frozen rules, not a change.** With 27 fires, split conformal has no finite
   static size at the 2% target (it needs at least 49 fires). Static arms at alpha = 0.02 are reported as NOT
   ATTAINABLE; the equal-miss curve of the static arms uses 0.05 to 0.30.
