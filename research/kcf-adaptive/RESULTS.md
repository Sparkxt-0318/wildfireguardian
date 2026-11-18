# RESULTS (DRAFT until the Arm 1 leakage runs finish): does adapting to the fire's own recent behaviour help? (kcf-adaptive)

Rules: `PROTOCOL.md`, frozen at commit a7bf180 before any score in this folder was computed; two amendments
(7f57699), both registered before the scores they concern. Every number below is in `numbers.json` or
`derived/*.json`. Labels: MEASURED = computed here from data; ASSUMED = an input taken on trust;
NOT TESTED = not run, with the reason.

## Answer

**Does adaptation reduce over-prediction (area flagged per cell actually burned) without raising the miss rate?**

| Arm | Over-prediction | Miss rate | Verdict under the frozen rule |
|---|---|---|---|
| 1. Test-time adaptation of c651 (4 parameters) | down 10% (4.65 to 4.18) | up (0.844 to 0.849) | **trade-off, not help** |
| 2a. Wind-aligned shape, fixed size | down 0.5% at 5 h, 2.4% at 8 h | not higher | does not help at 5 h; **helps at 8 h** (small) |
| 2b. Adaptive size (circle or wind-aligned) | down 35% at 5 h, 37% at 8 h | up from 6.2% to 9.6% (5 h), 6.6% to 9.4% (8 h) | **trade-off, not help** |

No. In both arms the adaptation that cuts over-prediction does it by predicting less fire, and the miss rate
rises. The only change that lowered over-prediction without more misses is the wind-aligned shape at 8 h, and that
gain is about 2%.

Adaptation could not have seen the 25 March 2025 run coming (section 3). It learns from misses, and a miss is only
known 5 hours after the forecast that missed.

## 1. Arm 1: test-time adaptation of c651

Six held-out US fires, 273 windows, 1,705,079 cell-windows, 8,520 burned (0.50%). For each window the model was
fine-tuned on up to 8 of that fire's own earlier windows whose outcome was already known at the issue time, then
used to predict. Primary set: the 4 branch-mixing parameters. Secondary: those plus 164 output biases (168).
Total model size 210,344.

Reproduction gate (MEASURED): the unadapted model rebuilt here matches the committed c651 mean-field predictions
to 3.4e-7 per cell; Brier 0.0099001 against 0.0099002. Passes.

| Model | Brier | Area flagged per burned cell | Expected miss | Calibration error (ECE) |
|---|---|---|---|---|
| c651, not adapted | 0.009900 | 4.65 | 0.844 | 0.0196 |
| **Adapted, 4 parameters (primary)** | **0.008719** | **4.18** | **0.849** | **0.0172** |
| Adapted, 168 parameters | 0.008681 | 4.17 | 0.850 | 0.0172 |
| Output rescaled by one number (no weights) | 0.007508 | 3.55 | 0.863 | 0.0141 |
| Sensitivity: 4 parameters, penalty 0.001 | 0.006751 | 3.09 | 0.870 | 0.0119 |
| Sensitivity: 4 parameters, penalty 0.0001 | 0.005395 | 1.90 | 0.905 | 0.0063 |
| Persistence (no new burning) | 0.004997 | 0 | 1.000 | 0.0050 |

"Area flagged per burned cell" is the sum of predicted probability divided by cells that burned. "Expected miss"
is the share of burned cells' probability the forecast did not assign. Both are MEASURED.

Paired differences in Brier score, fire bootstrap, 10,000 draws:

| Comparison | Difference | 95% interval | Fires favouring |
|---|---|---|---|
| Adapted (4) minus not adapted | -0.00118 | -0.00292 to -0.00029 | 6 of 6 |
| Adapted (168) minus not adapted | -0.00122 | -0.00299 to -0.00031 | 6 of 6 |
| Adapted (4) minus persistence | +0.00372 | +0.00238 to +0.00578 | 0 of 6 |
| Penalty 0.0001 minus persistence | +0.00040 | +0.00012 to +0.00086 | 0 of 6 |

What this shows:

- Adaptation improves the Brier score and calibration on every fire. Most of the gain is one fire (Lava:
  0.0168 to 0.0113).
- Every adapted version moves the same way: it shrinks the forecast. Median branch weights fall to 0.97-0.99 of
  their starting value under the frozen penalty and to 0.42-0.78 under the weakest penalty. The fires taught the
  model that it predicts too much spread.
- Shrinking is the route towards persistence, which predicts nothing and still has the best Brier score. No adapted
  version beats it, including the weakest-penalty run.
- The miss rate rises with every step of shrinkage. At an equal 10% miss rate (threshold read from the same data,
  descriptive only) the primary run flags 51.5 cells per burned cell against 52.4 unadapted: the ranking of cells
  barely changes, only the level.
- 168 parameters add almost nothing over 4.
- Windows with at least one earlier window (267 of 273) give the same picture: -0.00121 (-0.00300 to -0.00030).

Verdict (PROTOCOL 2.6): Brier interval below zero, area lower, expected miss higher: **trade-off, not help**.
The two weaker-penalty runs are sensitivity only (Amendment 1) and do not change the verdict; they make the
trade-off steeper, not better.

### Leakage test

DRAFT, runs still computing. So far (MEASURED): with everything at or after the issue time replaced by noise
(labels, later fire states, later weather), the 4-parameter method gives bitwise identical parameters and
predictions on 273 of 273 windows. The 168-parameter rerun and the leaky positive control are not finished.

### Korea and 25 March (Arm 1)

The weight-level adaptation was run on the six US fires only, as the task specifies. Arm 1 is NOT TESTED on
25 March: the frozen Korean cohort holds no scorable c651 window that day (the two KFS_01 windows are UNAVAILABLE,
"no common supported cells"; PROTOCOL 2.8), and no substitute was built. The output-level rescale was run on the 26 committed Korean windows (4 fires), descriptive only:
Brier 0.1751 adapted, 0.1741 unadapted, 0.2255 persistence. No gain.

## 2. Arm 2: adaptive directional margin

28 California fires (leave-one-fire-out), 20,161 issue hours at 5 h and 20,077 at 8 h. Target miss rate 10%.
Reproduction gate (MEASURED): the fixed circle reproduces kcf-margin exactly (3.75 km and 5.03 km; miss 6.16% and
6.62%).

- Shape: the margin is stretched downwind using the wind at the issue hour (reanalysis wind at the fire, ASSUMED to
  stand in for what a forecaster would know). Strength k chosen inside each fold from 0.25, 0.5, 0.75, 1.
- Size: adaptive conformal inference, updated hourly from the fire's own misses, which are only known h hours
  later. Step 0.005 (frozen); 0.02 and 0.05 are sensitivity.

| 5 h ahead | Issue hours missed | Area per burned cell | Change in area per burned cell (95%) | Verdict |
|---|---|---|---|---|
| Fixed circle (baseline) | 6.16% | 75.8 | | |
| Fixed wind-aligned | 6.15% | 75.4 | -0.4 (-1.0 to +0.4) | does not help |
| Adaptive circle | 9.56% | 49.2 | -26.6 (-38.6 to -15.6) | trade-off |
| Adaptive wind-aligned | 9.58% | 49.5 | -26.3 | trade-off |

| 8 h ahead | Issue hours missed | Area per burned cell | Change in area per burned cell (95%) | Verdict |
|---|---|---|---|---|
| Fixed circle (baseline) | 6.62% | 66.2 | | |
| Fixed wind-aligned | 6.38% | 64.6 | -1.6 (-2.2 to -1.0) | helps |
| Adaptive circle | 9.39% | 41.9 | -24.4 | trade-off |
| Adaptive wind-aligned | 9.35% | 41.4 | -24.8 | trade-off |

What this shows:

- **Shape.** The fold always chose the weakest stretch (k = 0.25, 29 of 29 folds); stronger stretches flag more
  area, not less (mean 452, 484, 537, 810 km2 for k = 0.25 to 1, against 458 for the circle). Replacing the issue-hour
  wind with the wind that actually blew did not help either. Wind direction at this scale carries little
  information about where these perimeters grow.
- **Size.** The adaptive margin is smaller on average (2.8 km against 3.7 km at 5 h) because it aims at the 10%
  target, which the fixed margin overshoots on the safe side (6.2%). The misses it adds are 3.4 points (1.8 to 4.7),
  on 25 of 28 fires.
- **Equal miss rate.** Comparing each arm with a fixed circle shrunk to the same miss rate, the adaptive circle
  still flags less: -13.3 (-19.1 to -6.7) at 5 h and -12.2 (-20.6 to -3.1) at 8 h. A fixed circle simply
  recalibrated to the fire-weighted 10% target recovers -5.2 and -4.0 of that. So roughly a third to a half of the
  apparent saving is recalibration, and the rest is real adaptation to quiet periods.
- **Where the misses go.** In the fastest tenth of hours (by the fire's previous 3 h of growth) the fixed circle
  misses 17.5% and the adaptive circle 26.2% at 5 h (17.1% and 22.6% at 8 h). Cell-level miss goes from 8.4% to
  11.5%. The adaptive margin saves area when the fire is quiet and gives it back when the fire runs.
- **Faster steps do not fix this.** Step 0.05 sits at the ceiling (the largest reach seen in calibration) for 2,591
  of 20,161 hours at 5 h and 4,283 of 20,077 at 8 h, and flags more area than the fixed circle (102 and 171 per
  burned cell) with a miss rate still above it (9.3% and 9.5%). Step 0.02: 62 and 80 per burned cell, miss 9.2%
  and 9.3%.

Verdict (PROTOCOL 3.7): adaptive size is a **trade-off, not help** at both horizons. The wind-aligned shape with
fixed size **does not help** at 5 h and **helps** at 8 h by 1.6 cells per burned cell (2.4%).

Figure: `fig/fig2_arm2_frontier.png`.

### Korean fires (test only)

12 fires, 792 issue hours at 5 h, 756 at 8 h. KFS_09, KFS_14 and KFS_16 are NOT TESTED (arrival data span 0 h, no
issue hour). Nothing was tuned on these fires; k = 0.25 and all sizes come from the 28 calibration fires.

| | 5 h: hours missed | 5 h: area per burned cell | 8 h: hours missed | 8 h: area per burned cell |
|---|---|---|---|---|
| Fixed circle | 53 of 792 | 15.3 | 51 of 756 | 13.2 |
| Fixed wind-aligned | 56 | 14.3 | 62 | 12.2 |
| Adaptive circle | 55 | 14.8 | 64 | 13.5 |
| Adaptive wind-aligned | 56 | 14.2 | 71 | 17.5 |

No arm reduces area without adding missed hours. At 8 h the adaptive arms miss more and flag as much or more.
Misses come from the same 4 of the 12 fires in these arms; the fire that includes 25 March (KFS_01) gives 27 of the
fixed circle's 53 missed hours at 5 h.

## 3. 25 March 2025 (Gyeongbuk), reported separately

5 h ahead, 23 complete issue hours. What the fire did, in km beyond the known burned area over the next 5 h, for
issue hours 10 to 20 KST: 4.9, 6.6, 12.4, 23.9, 34.7, 32.9, 40.1, 38.6, 27.3, 20.3, 15.7. The largest reach ever
seen in the 28 calibration fires is 17.3 km (20.4 km wind-aligned).

| Margin | Hours missed | Which (KST) | Largest size reached |
|---|---|---|---|
| Fixed circle, 3.75 km | 13 | 10-22 | 3.75 km |
| Fixed wind-aligned | 13 | 10-22 | 4.2 km |
| Adaptive circle, frozen step | 13 | 10-22 | 3.5 km |
| Adaptive wind-aligned, frozen step | 13 | 10-22 | 3.9 km |
| Adaptive circle, started from the fire's earlier days | 12 | 10-21 | 6.1 km |
| Adaptive circle, step 0.05 (sensitivity) | 10 | 10-19 | 17.3 km (the ceiling) |
| Unbounded tracker, 0.2 (secondary) | 11 | 10-20 | 15.5 km |

**Could adaptation have seen the run coming? No.**

- The frozen adaptive margin missed the same 13 hours as the fixed one and was smaller than it when the run began
  (it had been shrinking through the quiet morning).
- A miss at 10 KST is only confirmed at 15 KST. By then the fire was already reaching 33 km in 5 h. Every adaptive
  variant first holds only after the peak: the fastest one from 20 KST, when the fire was slowing.
- The only variant that holds at 10 KST is the fast-step one started from earlier days, and it holds because of
  leftover inflation from earlier misses (5.5 km against a 4.9 km reach), then misses 11-19 KST.
- No margin learned from these 28 fires can cover a 40 km reach: the ceiling is 17.3 km.
- Wind direction did not help: the wind-aligned margins missed the same hours.

At 8 h the picture is the same: fixed misses 12 of 20 complete hours (8-19 KST), frozen adaptive 13.

Arm 1 on 25 March: NOT TESTED (section 1).

Figure: `fig/fig3_march25.png`.

## 4. Limits

- Six US fires and 28 California fires; intervals are fire bootstraps and are wide. One fire (Lava) carries most of
  the Arm 1 gain.
- Arm 1 uses the mean-field rollout of c651, not the Monte Carlo one (Brier 0.009900 against 0.009852 committed).
- The penalty, learning rate and step count of Arm 1 were fixed in advance and not tuned; the sensitivity runs show
  the result depends strongly on the penalty, always along the same trade-off.
- Arm 2 wind is reanalysis at one point per fire-hour (ASSUMED representative). Gusts and terrain channelling are
  not in it.
- Korean results are test-only; half the fixed-margin misses come from one fire.
- The miss target of 2% is NOT ATTAINABLE with 27 calibration fires per fold (Amendment 2).

## 5. Prior work

Closest three (details and how this differs: PROTOCOL section 1): Rochoux et al. 2014 (NHESS 14, 2951),
Srivas et al. 2017 (ICCS), Cheng et al. 2022 (Remote Sensing 14, 3228). Adaptive conformal inference: Gibbs and
Candes 2021. Inspiration: SEAL (arXiv 2506.10943), SIA (arXiv 2605.27276).

## 6. Reproduce

    bash run_all.sh WORKDIR        # about 25 CPU-hours; needs zenodo.org and archive-api.open-meteo.com
    python -m pytest -q tests      # 18 tests
