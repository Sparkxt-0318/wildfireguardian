# PROTOCOL: a forecast margin that learns the fire's current state, hour by hour (kcf-adaptive3)

Frozen 2026-11-19, committed before any model fit, label count, margin, area or warning count in this folder was computed.
Later changes go in "Amendments" at the end, each with the time, the reason and **what had been seen** when it was made.

**Hard stop.** Monday 23 November 2026, 12:00 Asia/Shanghai. Unfinished items are reported NOT RUN with the reason.
Pushed at least once per calendar day.

## 0. Question

`kcf-adaptive2` found that a quantile model with the fire's recent growth as an input needs 15% less area than a fixed
margin in California, that adapting a model to each fire gains nothing (per-fire oracle 0%), and that an oracle
adapting per fire-day gains 24.5%. Nothing transferred to Korea. The idea tested here: track the fire's **current
state** (quiet or run) online, let the issued forecast move the state before any spread is seen, and issue a margin
that mixes one margin per state.

### 0.1 Disclosure: what was known when these rules were written

- Read in full: `kcf-adaptive2/RESULTS.md` (every number, including the Korea table and the hour-by-hour table of
  25 March 2025: reach 2.2 to 40.1 km, every non-extrapolating method missed 12 to 20 KST), `kcf-aloft/RESULTS.md`
  (the 9 Korean run fire-days by name, their first run hours, which 4 the gust rule warned and which 5 had no warning
  from any wind rule), and the head of `kcf-adaptive2/PROTOCOL.md`.
- **The Korean fires are not a first look.** Their outcomes under 18 methods were examined in kcf-adaptive2 and
  kcf-aloft. I know from the kcf-aloft day table that three of the nine run fire-days start at 00 KST as a run carries
  over midnight (Uiseong 23 and 26 March 2025, Uljin 5 March 2022). A tracker that is in "run" from detections can be
  firing at those hours without any foresight. This is why section 6 reports onset days separately.
- Looked at here before this commit (structure only): column names and row counts of the rebuilt hourly tables
  (50,314 eligible hours at 5 h: 20,065 GOFER, 30,226 Choi, 23 detection product); which GOFER fires fall in which
  kcf-adaptive2 fold (names only); the header and four rows of the Su & Yu global event file; the first 20 cycles of
  the Korean forecast fetch log (sizes only).
- Not computed before this commit: any state label count, emission table, transition fit, margin, area, miss rate,
  alarm score or burden count for any method in this folder.
- Prior expectation (ASSUMED, written to be checked): on California the tracker lands within a few percent of
  QUANTILE either way; on Korea, target A is reachable mainly through continuation days; target B is uncertain.

## 1. Data and splits (by fire, always)

| set | fires | role |
|---|---|---|
| CA-DEV | 16 GOFER v0.2 fires: kcf-adaptive2 outer folds 0 to 3 (CZU Lightning Complex, Caldor, Dolan, McCash; Dixie, KNP Complex, LNU Lightning Complex, North Complex; Monument, SQF Complex, Slater and Devil, Windy; August Complex, Beckwourth Complex, Kincade, Red Salmon Complex) | every fit and every choice of the agent loop (step 4) |
| CA-HELD | 12 GOFER fires: folds 4 to 6 (Bobcat, Glass, Walker, Zogg; Antelope, McFarland, River Complex, W-5 Cold Springs; Creek, July Complex, SCU Lightning Complex, Tamarack) | **one final run**, target C |
| KR | 12 Korean fires with Choi et al. 2026 arrival rasters, plus the detection product (FIRMS VIIRS + Himawari) for KFS_01 on 25 March 2025 | targets A and B, leave-one-fire-out, run once after the California final run |
| ARCHIVE | a global daily-perimeter archive (section 1.2) | training of one input of the transition model only; never scored |
| BURDEN | kcf-aloft's ten fixed points in Gangwon and Gyeongbuk, 1 Feb to 15 May, seasons 2021 (from 27 Feb) to 2025 | alarm burden for target A |

The fold assignment is the kcf-adaptive2 hash (sha256 of the fire name, rank mod 7); it was fixed there before any
result and is not chosen here. All 28 California fires were scored in kcf-adaptive2 by cross-validation, so CA-HELD is
held out of every fit and choice **in this folder**, not unseen by the project. Per-fire results of kcf-adaptive2 were
not opened before this commit.

Horizon h = 5 h only. Eligible issue hours, reach S_t, flagged area A_t(q), the fire-weighted miss rate and the
fire-weighted area are those of kcf-adaptive2 PROTOCOL sections 1 to 2, rebuilt by its `build_data.py` from the same
Zenodo files (GOFER 14642378, Choi 21788344) and imported from its `lib.py`. Features available at issue hour t: its
section 2.1 list (own-past g1, g3, g6, g12, g24, log area, log age, sin/cos solar hour; issued forecast gust_ms,
w850_ms, rhmin_pct, hdw over the next 8 h with the 5 h availability delay, inherited from kcf-abstain).

### 1.1 Frozen state labels

- **Run hour**: an issue hour whose 5 h reach exceeds 3.75 km (the kcf-margin R(5 h); the kcf-aloft run-hour rule).
  State label z_t = 1 for a run hour, 0 otherwise ("quiet").
- **Run fire-day** (hourly fires): a local day (KST for Korea, UTC-8 for California) with at least one run hour.
  For Korea the nine run fire-days and their first run hours are those of `kcf-aloft/derived/fire_hours.csv.gz`.
- **Run fire-day (ARCHIVE, daily perimeters)**: day d of a fire is "run" if the daily reach exceeds 3.75 km, where
  daily reach = the largest distance from any vertex of the area newly burned on day d to the area burned on all
  earlier days of the same fire (equal-area projection). A fire's first burn day has no earlier area and is dropped.
  Fires are kept if they burned on at least 3 days and at least 10 km2 in total. Every other kept day is "quiet".
  The threshold is the hourly one on purpose (one number in the study); a day is longer than 5 h, so archive run-days
  are more common than hourly ones, which is stated wherever they are used.

### 1.2 The archive

Tried in this order; the first that downloads and has per-day geometry is used: Su & Yu 2012-2025 VIIRS events
(Zenodo 21807914), GlobFire v3 daily (PANGAEA 943975), FIRED (CU Scholar). Known at freeze time: Su & Yu downloads but
is an event table without daily geometry (seen from its header), so it cannot give fire-day labels; FIRED's host
answers 403; GlobFire's 2021 file is being restored from tape by the host. Issued GFS on the open NOAA bucket starts in
2021, so only **archive year 2021** can be paired with a forecast as issued. If no archive with daily geometry is in
hand 24 hours before the hard stop, the archive input is dropped, RESULTS says so, and nothing else changes.
Simulated fires are not used.

Archive forecast: GFS 0.25 deg, cycles 00 and 12 UTC, leads 6, 9, 12, 15 h (every valid time comes from the most
recent 12-hourly cycle at lead 6 to 15 h); the four lattice points around the day's centroid; day maximum of gust and
850 hPa wind speed and day minimum of 2 m relative humidity over the 8 valid times of the local solar day.

## 2. The model: TRACKER (version 0, before the agent loop)

Two hidden states per fire, quiet (0) and run (1). p_t = probability of run at issue hour t.

1. **Transition, from the issued forecast.** enter_t = P(z_t = 1 | z_{t-1} = 0, x_t) and stay_t = P(z_t = 1 | z_{t-1} = 1, x_t),
   two logistic regressions (L2, C = 1, standardised inputs, each fire weight 1) fitted on the labelled consecutive
   hours of the training fires. x_t = gust_ms, w850_ms, rhmin_pct (the issued forecast window), sin and cos of the
   local solar hour, and a_t = the archive propensity: the logit of a logistic regression of the archive run-day label
   on the day's gust, 850 hPa wind and humidity, evaluated at hour t's forecast-window values. Prediction step:
   p_{t|t-1} = p_{t-1} stay_t + (1 - p_{t-1}) enter_t. Before the fire's first hour p = 0. Over a gap of k missing
   hours the prediction step is applied k times with the current hour's probabilities.
2. **Hourly update, from detections.** o_t = g1_t, the reach of what burned in the last hour as seen by the arrival
   product at t (growth since the last scan). Its distribution per state is a table over six bins (0; up to 0.375;
   0.75; 1.5; 3 km; above), counted on training fires with one added to each cell.
   p_t = p_{t|t-1} e_1(o_t) / [p_{t|t-1} e_1(o_t) + (1 - p_{t|t-1}) e_0(o_t)].
3. **One margin per state.** m_0 and m_1: gradient-boosted quantile regressions of S at tau = 0.9 (the target miss
   rate) on the 13 features, fitted on the quiet-labelled and on the run-labelled training hours (depth 2, 100
   iterations, learning rate 0.05, minimum leaf 200 for quiet and 50 for run).
4. **Issued margin.** s_t = (1 - p_t) m_0(x_t) + p_t m_1(x_t), floored at 0.1 km, then q_t = kappa s_t with the one
   calibration rule of kcf-adaptive2 section 3: out-of-fold s on the training fires (the whole tracker refitted in
   each inner fold, six by-fire groups), kappa the smallest value with fire-weighted out-of-fold miss at most 10%.

Labels of the fire being forecast are never used online: the filter reads only o and the forecast. Leakage tests:
L1, changing any outcome or feature after hour t leaves p_t and q_t unchanged; L2, the tracker's output on a fire is
unchanged when that fire's labels are scrambled.

**Comparators (step 3).** All calibrated by the same rule on the same training fires.
- FIXED: s = 1.
- QUANTILE: the kcf-adaptive2 class unchanged (its 45-configuration grid, chosen by inner cross-validation).
- TRACKER-noupdate: the same fitted tracker with step 2 switched off (p moves by the forecast alone).
- TRACKER-nofc: the same model with gust, 850 hPa wind, humidity, hour and the archive input removed from the
  transition (enter and stay are two constants), refitted.
- TRACKER-noarchive (extra row): a_t removed, refitted.

## 3. The one metric and the verdict rules

**Metric: flagged area at a 10% miss rate, miss checked on fires held out of every fit.** For each method: area at its
calibrated margin with the achieved held-out miss and a fire-cluster bootstrap interval (2,000 resamples, seed
20261119), and the area read off the held-out frontier at exactly 10% miss (kappa swept on the held-out fires;
descriptive, it uses held-out outcomes; kcf-adaptive2 showed it is needed to stop unequal miss rates creating a gain).
Ratios between methods: paired fire bootstrap, seed 20261120. A miss rate is **valid** if within 10% +/- 3 points and
its interval contains 10%.

## 4. Step 4: bounded agent loop (CA-DEV only)

- At most **20 proposals** after version 0. A proposal changes features or model code of TRACKER (inputs of the
  transition, the observation and its table, the state margins, the mixing rule, hyper-parameters). It may not change
  the splits, the labels of section 1.1, the calibration rule, the metric, the comparators or the targets.
- Each proposal is scored on CA-DEV only by 4-fold by-fire cross-validation (the four kcf-adaptive2 folds, 12 fires
  train, 4 test, calibration inside the 12):
  - **M1** = area read at exactly 10% cross-validated miss (km2; lower is better).
  - **M2** = run fire-days warned at a fixed false-alarm level: alarm score p_t; threshold = the smallest c at which at
    most 10% of the CA-DEV fire-days without a run have any hour with p_t >= c; M2 = the share of CA-DEV run fire-days
    with p_t >= c at their first run hour (higher is better).
- **Kept** if M1 falls by at least 1% of the current best while M2 does not fall, or M2 rises while M1 does not rise
  by more than 1%. Otherwise discarded. Each proposal is compared with the current kept version.
- Every proposal is logged in `PROPOSALS.md` with its reason, M1, M2 and kept or not, including version 0 and failures
  to run. CA-HELD, KR and BURDEN are not read by the loop. Proposals are written by me (the agent) from CA-DEV
  diagnostics only.
- Then **one final run**: the kept version and the comparators are fitted and calibrated on CA-DEV and applied once
  to CA-HELD; then the Korean runs of section 5 and 6 once. No tuning afterwards.

## 5. Korea: leave-one-fire-out (target B)

For each Korean fire i (KFS_01's raster and detection series are one fire): every part of each method is fitted on
all 28 California fires plus the other 11 Korean fires (each fire weight 1; the archive input as fitted), with the
kept configuration from step 4 and, for QUANTILE, the configuration chosen on CA-DEV. kappa is set on the other 11
Korean fires: their scores come from models fitted without fire i and without the scored fire, and kappa is the
smallest value with fire-weighted miss at most 10% on those 11. Fire i is then scored. Area and miss are over the 12
fires' Choi-raster issue hours (756 expected); FIXED is calibrated the same way. Also reported, as secondary rows:
the California-fitted model with only kappa recalibrated leave-one-fire-out, and the straight California transfer.

## 6. Targets (all at a 10% miss rate checked on held-out fires)

**A. Korean run fire-days warned at the alarm burden of the gust rule: more than 4 of 9.**
- Alarm score: the tracker's p_t for fire i from the leave-one-fire-out model of section 5, run over every issue hour
  of the fire in `kcf-abstain/derived/hours.csv.gz` (kcf-aloft's primary timeline: detection product on 25 March 2025).
- Burden: the forecast as issued is fetched again for BURDEN with humidity added. At a burden point there is no fire,
  so the score is the same model run with no detections (prediction step only) through every hour of the season. An
  alarm day is a KST day with the score at or above c at any hour. G (forecast gust >= 20 m/s at two consecutive hours
  of the next 8) is recomputed on the same hours and must reproduce kcf-aloft's 3.7 alarm days per point and season
  within 0.2, else stop and report. For each left-out fire, c is the smallest threshold whose alarm point-days do not
  exceed G's.
- Warned = score >= c at the day's first run hour (kcf-aloft's nine days and hours).
- **Pass A**: at least 5 of 9 warned. Reported beside it and not hidden: alarms on the 34 fire-days without a run
  (G: 0); the count on **onset days** only (first run hour not preceded by a run hour of the same fire in the previous
  6 h); the same count for TRACKER-noupdate (forecast only, exactly equal burden by construction) and TRACKER-nofc; and
  the counts without 25 March. **Strict A** additionally requires no more alarms on no-run fire-days than G, and is
  reported as a separate line. The burden set cannot charge for alarms raised by detections; that limit is stated.

**B. Flagged area on the 12 Korean fires below the fixed margin, leave-one-fire-out.**
**Pass B**: TRACKER's miss is valid, area(TRACKER) / area(FIXED) < 1 at the calibrated margins, and < 1 read at exactly
10% miss. The paired interval is reported; a pass whose interval includes 1 is called "lower, not distinguishable".

**C. Flagged area on CA-HELD no worse than QUANTILE.**
**Pass C**: TRACKER's miss is valid, area(TRACKER) / area(QUANTILE) <= 1 at the calibrated margins, and <= 1 read at
exactly 10% miss. Paired interval reported; if its lower end is above 1, "worse".

**25 March 2025.** For each issue hour 09 to 20 KST: the forecast inputs, o_t, enter_t, p_{t|t-1}, p_t, m_0, m_1, the
issued margin and the reach, from the model fitted without KFS_01, using only information available at that hour.
Counts only; no rate.

## 7. Reporting

One results table: method, area, achieved miss with interval, fires, run-days warned. RESULTS.md states that the Korean
fires were already examined, that nine run-days and one 25 March are small samples, and which targets failed. Every
number is written to `numbers.json` by code. Labels: MEASURED, ASSUMED, ORACLE, NOT RUN.

## Amendments

(none at freeze; implementation notes follow)

No rule, split, label, metric or target was changed after the freeze. The notes below record choices the frozen text
left open and the order in which things were seen. Written 2026-11-19 after all runs.

1. **Order of first looks on CA-DEV.** Before the archive input existed, the tracker without it (the comparator
   TRACKER-noarchive) was scored on CA-DEV to check the code (M1 342.7, M2 19 of 72), and one diagnostic of its state
   probability was printed (reliability by bin, emission table, AUC of single inputs). Proposals 1 to 6 were written
   from that diagnostic. Version 0 was scored afterwards (M1 342.7). FIXED, QUANTILE and version 0 with the update
   or the forecast off were also scored on CA-DEV before the loop (`derived/dev_log.jsonl`).
2. **Archive.** GlobFire v3, year file 2021 (PANGAEA 943975), 42,593 fires kept of 929,479. Distances are computed in
   a local plane around each fire rather than a formal equal-area projection. GlobFire's burn date is taken as the
   local day. 31,126 of 415,480 fire-days have no issued forecast (before 1 January 2021 or one of 5 cycles missing
   from the NOAA bucket in February 2021) and are not used. Su & Yu has no daily geometry; FIRED answered 403.
3. **Burden set.** A burden point is run as a fire with no detections: every own-past input 0. For TRACKER-nofc the
   score at a burden point is one constant, so the burden set puts no limit on it; its warning count is not an
   equal-burden number and is reported only with that statement.
4. **Alarm timeline.** Target A uses every issue hour of kcf-aloft's primary timeline (791), including 36 hours with
   fewer than 3 earlier hours, which kcf-adaptive2's eligibility drops; the area and miss of target B use the 756
   eligible hours. Models are fitted on eligible hours only.
5. **Filter detail.** A gap in a fire's hours is bridged by at most 48 prediction steps.
