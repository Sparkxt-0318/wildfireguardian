# PROTOCOL: can the margin tell it is out of range, and abstain? (kcf-abstain)

Frozen 2026-11-18, committed before any abstention score, threshold, new reach value or tail fit was computed.
Changes after this commit go in "Amendments" at the end, each with its reason and the time it was made.

**Question.** At an hourly issue time, using only what was available then, can the reach-margin system
(`research/kcf-margin`) tell that it is outside the conditions it was calibrated on, and withhold its number?
The margin held on average over 28 California fires and failed on 25 March 2025 at every issue hour from
10 to 20 KST. Prior-3 h spread gave no warning there, and observed and reanalysis gusts gave none either
(`research/kcf-gust`). If nothing separates the missed hours, that is the result.

## 0. What was known when these rules were written (disclosure)

- The kcf-margin and kcf-gust RESULTS, including the 25 March reach values, the hours that failed, and the
  KMA and ERA5 gusts on 22-26 March 2025, had been read. That is the motivation for the study, not an input to it.
- As a decoder test, one GFS message set was decoded and printed at Uiseong (36.35 N, 128.70 E), cycle
  2025-03-25 00 UTC, lead 6 h: 2 m temperature, 2 m RH, 10 m wind, 850 hPa wind. No other Korean predictor value
  was looked at. No GOFER predictor value was looked at, apart from region-wide minimum/median/maximum of two
  test cycles (2021-08-01 00 UTC GFS, 2020-08-20 00 UTC HRRR) to check units and coverage.
- The five predictors were fixed by the brief. The forecast source, availability delay, location rule, score,
  threshold level and evaluation below were chosen on general grounds before any score existed. None of them
  is changed after this commit, whatever the Korean result.

## 1. Fires and their roles

The frozen list is `FIRES.md`. Roles:
- **Calibration fires (the only fires that set anything):** the 28 GOFER fires of kcf-margin. They set the margin
  R (already frozen there), the reference distribution of the out-of-range score, and the abstention threshold.
- **Test fires (never set a predictor, score or threshold):** every other fire in `FIRES.md` that has an hourly
  arrival product. This includes all Korean fires and the six US2024 fires.
- A catalog fire that is also a GOFER fire (10 fires, `FIRES.md`) is a calibration fire. Its Choi arrival raster is
  used only in the product cross-check of section 7 (S3), never as a test.

## 2. Outcome: realised reach and whether the margin held

**Reach, the kcf-margin method, unchanged** (`research/kcf-margin/reach.py`, imported, not copied).
Known set K_t = {cells with arrival A <= t}; new cells N = {t < A <= t+h}; 375 m cells, cell-centre values;
N split into 8-connected components; a component whose nearest cell is more than 5 km from K_t is a separate fire
and is left out; reach S_h(t) = max over the remaining cells of the Euclidean distance (km) from cell centre to the
nearest cell centre of K_t, 0 if none. Horizons h = 5 and 8 h. Issue hours: every whole hour t with non-empty K_t
and t + h <= the last arrival hour of the product.

**Arrival products** (one per fire; labelled in every table):
1. GOFER hourly perimeters (28 calibration fires): reach reused from `research/kcf-margin/derived/gofer_reach.csv.gz`
   (commit 0ead891). Not recomputed.
2. Gyeongbuk 25 March 2025, issue hours 00-23 KST: FIRMS VIIRS + Himawari AHI detection union, reused from
   `research/kcf-margin/derived/gyeongbuk_reach.csv` (commit 0ead891), only rows flagged `complete` are scored.
   These are detections, not perimeters (ASSUMED proxy, as in kcf-margin).
3. Choi et al. 2026 kriged time-of-arrival rasters (Zenodo 21788344, sha256 612edf5f...; 15 Korean, 29 US
   catalog fires): computed here with the same rule. A(c) = t0 + TOA(c) h on the UTC clock (t0 from the raster tag),
   cells outside the final perimeter never burn, issue hours are whole UTC hours. These are retrospective
   reconstructions kriged from satellite detections inside the final perimeter, smooth in time, not hourly
   observations. For KFS_01 the detection product (2) is primary on 25 March 00-23 KST and the raster is shown
   beside it; on the other days of KFS_01 the raster is the only product.

**Margin tested.** The kcf-margin all-hours margin at the 10% target, `numbers.json` -> `table`, fire set all28:
R(5 h) = 3.75 km, R(8 h) = 5.031152949374527 km. On test fires this frozen R is used. On calibration fires,
leave-one-fire-out: the held-out fire's R_f(h) is recomputed with kcf-margin's own `conformal_R` on the other 27
fires (2,000 draws, seed 20261116, fires in sorted order, exactly as `calibrate.py::lofo`). The recomputation must
reproduce the committed LOFO miss rates 0.0616 (5 h) and 0.0662 (8 h); if it does not, everything stops and the
difference is reported. **The margin held** at an issue hour if S_h(t) <= R; otherwise it **missed**.

## 3. Predictors (fixed set of five, nothing added after this commit)

For issue hour t (UTC, on the hour):

**Forecast source, fixed order per fire.**
1. **GFS 0.25 deg** (NCEP; AWS NODD `noaa-gfs-bdp-pds`, archive from 2021-01-01): every fire whose issue hours are
   on or after 2021-01-01. This covers every Korean fire, the US2024 fires, the 2021-2022 US fires, and the 11
   GOFER fires of 2021. GFS is the only issued forecast reachable here that covers both California and Korea.
2. **HRRR 3 km** (NOAA; AWS `noaa-hrrr-bdp-pds`, archive from 2014-07-30): US fires before 2021 (the 17 GOFER fires
   of 2019-2020 and the 2020 catalog fires CameronPeak and EastFork), where GFS cannot be obtained here (the
   reachable GFS archives start 2021-01-01; NCEI and NCAR RDA are blocked by this environment's network policy).
3. **Reanalysis**, only if neither can be obtained for a fire; every number from it is labelled
   **ASSUMED PERFECT FORECAST**. No fire with an hourly arrival product needs it (Rim 2013 has none, `FIRES.md`).

**Cycle and availability delay.** Cycles 00, 06, 12 and 18 UTC, for both models. A cycle is assumed available
**5 h after its nominal time** (GFS 0.25 deg products are posted about 3.5-4 h after the cycle; HRRR about 1-1.5 h).
The issue hour uses c(t) = the latest such cycle with c + 5 h <= t, so the window (t, t+8] is read at lead times
6-18 h. For HRRR this is deliberately not the freshest hourly cycle: it reads both models from the same cycles at
the same leads, so the calibration reference is not a mix of lead times. This is conservative (older forecasts than
were available). It is a stated deviation from "the latest cycle available" for HRRR only.

**Where.** P_t = centroid of the fire's known burned set K_t at the issue hour, from the same arrival product as the
fire's reach (GOFER: K_t on kcf-margin's EPSG:3310 375 m raster of the GOFER perimeters; Choi rasters: cells with
A <= t). For 25 March 2025 (product 2) the Himawari part of K_t is not rebuilt here, so P_t is the centroid of the
VIIRS part of the same known set: FIRMS S-NPP and NOAA-20 detections, confidence not 'l', inside kcf-margin's
`score_gyeongbuk.py` box, counted from the whole hour after acquisition (as there). "Near the fire" = the **four
0.25 deg lattice points at the corners of the lattice cell containing P_t**. GFS is read at those points. HRRR is
first averaged over the HRRR cells whose centres round to each lattice point (a 0.25 x 0.25 deg box), so both
models are read on the same lattice (`fetch_nwp.py`; vector components are averaged before speeds are formed).

**The five predictors** (maximum or minimum over the 4 points and the 8 valid hours t+1 ... t+8):
1. `gust` = max 10 m wind gust (GRIB `GUST:surface`), m/s.
2. `w850` = max 850 hPa wind speed, sqrt(u^2 + v^2), m/s (values under ground are the model's own extrapolation).
3. `rhmin` = min 2 m relative humidity, %.
4. `hdw` = max Hot-Dry-Windy index in its surface form: (10 m wind speed, m/s) x (2 m vapour pressure deficit, hPa),
   VPD = e_s(T)(1 - RH/100), e_s = 6.112 exp(17.67 T / (T + 243.5)) hPa, T in deg C. Srock et al. (2018) take the
   maxima over the lowest 50 hPa; the surface form is an ASSUMED simplification, used identically for all fires.
5. `prior3` = prior-3 h spread, km: the reach from K_{t-3} to cells with t-3 < A <= t under the same 5 km rule
   (kcf-margin class b). GOFER: `reach_km` of row (t-3, h = 3) in `gofer_reach.csv.gz`; 25 March: `prior3_km`;
   Choi rasters: computed. Undefined when K_{t-3} is empty.

**Missing data.** A predictor needs all 8 valid hours of its fields at all 4 points from cycle c(t). If any is
missing, or `prior3` is undefined, the hour gets no score; it is counted and listed per fire, never filled.

## 4. Out-of-range score and abstention rule

**Danger direction**, fixed from fire-weather physics before any data: high `gust`, high `w850`, low `rhmin`,
high `hdw`, high `prior3`.

**Score (primary).** For a reference set of F fires, predictor j and value x, the fire-weighted one-sided tail
probability is p_j(x) = (1/F) sum over reference fires g of (share of g's scored hours with a value at least as
extreme as x, ties included). The score is s = min over the five predictors of p_j. Small s = further outside the
calibration conditions in a dangerous direction. s = 0 means beyond every reference hour on some predictor.

**Threshold.** beta = 0.05. Leave-one-fire-out scores on the calibration fires: each calibration fire g is scored
against the other calibration fires. tau = the largest score value at which the fire-weighted share of these
scores <= tau is still <= beta (each fire's hours share weight 1/F). **The system abstains at an issue hour when
s <= tau.** For a test fire, the reference set is all 28 calibration fires and tau comes from their 28
leave-one-out score sets. One rule for both horizons: the score uses the 8 h window and is the same at 5 h and 8 h.

**Secondary score (S1, reported, no say in the conclusion):** two-sided, p_j = min(1, 2 min(P(X >= x), P(X <= x))),
same threshold rule.

## 5. Evaluation on the calibration fires (leave-one-fire-out)

For each held-out GOFER fire f (outer fold): the score reference is the other 27 fires; the threshold tau_f is set
by the rule above from nested leave-one-out scores within those 27 (each g != f scored against the other 26);
R_f(h) is the kcf-margin LOFO margin. On f's scored issue hours:
- abstention rate a_f = share abstained;
- miss rate among hours not abstained m_f = share of retained hours with S > R_f (undefined if none retained);
- for comparison, miss rate with no abstention.

Reported for h = 5 and 8: fire-weighted means over fires (n stated; fires with no retained hour are listed and left
out of the miss-rate mean), Clopper-Pearson 95% on k = sum of fractions of n fires (as kcf-margin), and pooled-hour
values. The **risk-coverage curve**: beta from 0 to 1 in steps of 0.01, each point computed leave-one-fire-out as
above; coverage = fire-weighted share retained, risk = fire-weighted miss rate among retained hours. Shown with the
no-abstention risk (random abstention has the same expected risk) and the oracle that abstains on misses first.

**Does the score separate the missed hours? (decision rule, per horizon)**
- AUROC of -s for misses on the outer-fold hours, each hour weighted 1/(n_f F).
- Delta = (fire-weighted miss rate among retained at beta = 0.05) - (fire-weighted miss rate with no abstention).
- 95% intervals for both from 2,000 fire-bootstrap resamples (seed 20261118), thresholds held as computed.
- **Separates** if the AUROC interval lies above 0.5 and the Delta interval lies below 0. **Does not separate** if
  the AUROC interval contains 0.5. Anything else is reported as partial, with the numbers.

Descriptive: for each abstained hour, which predictor gave the minimum p_j.

## 6. Test fires, hour by hour

For every test fire and scored issue hour: the score against all 28 calibration fires, abstain (s <= tau), the reach,
R (frozen), held or missed. Per fire: the 2 x 2 counts (abstained / not x held / missed) per horizon, hours not
scored and why. Groups: Korea (15 catalog fires + the 25 March detection product), **counts only, no rates**;
US2024 (6 fires), counts only (fewer than 10 fires); US Choi-raster test fires (19 fires: 6 US2024 + 13 development
fires not in GOFER), fire-weighted rates with Clopper-Pearson intervals as in section 5. No rate is computed from
fewer than 10 fires anywhere. **25 March 2025, 10:00-20:00 KST**, each hour explicitly: the five predictors, the
cycle used, each p_j, s, tau, abstain or not, 5 h and 8 h reach, R, held or missed.

## 7. Secondary analyses, declared now (reported in full; none can change the primary conclusion)

- **S1** Two-sided score (section 4).
- **S2** GFS-only calibration: reference and thresholds from the 11 GOFER fires of 2021 only (all GFS); the same
  leave-one-fire-out evaluation (11 fires, rates allowed) and the same 25 March hour table. Purpose: remove the
  GFS/HRRR mix from the reference.
- **S3** Product cross-check on the 10 fires that have both GOFER perimeters and a Choi raster: margin miss rate
  of the frozen R under each product over the same issue hours (fire-weighted, n = 10). Purpose: show how much a
  test result on a Choi raster can differ from GOFER for reasons of product alone.

## 8. Tail question

Per-fire maximum 5 h reach (5 km rule) of the 28 calibration fires, from `gofer_reach.csv.gz`. Fit a GEV by maximum
likelihood (`scipy.stats.genextreme`, shape xi = -c). Report xi with its 95% profile-likelihood interval, and the
**return period of 40 km**: T40 = 1/p40 fires, p40 = P(per-fire maximum > 40 km), with a 95% profile-likelihood
interval for p40 (parametrised through p40 directly) and a parametric bootstrap (2,000 refits, seed 20261118) beside
it. Fires needed to bound an event that rare: n = ceil(ln 0.05 / ln(1 - p40)), the number of fires with no
exceedance that would put a one-sided 95% upper bound at p40 (about 3/p40); given at the estimate and at the
interval ends. **Trust rule:** T40 is reported as a number only if its 95% profile interval is finite at both ends.
If the interval for p40 reaches 0 (a bounded tail ending below 40 km cannot be excluded), the report says the fit
cannot bound it, and gives xi's interval and the extrapolation ratio (40 km / largest observed maximum) instead.

## 9. Reporting

- Labels: MEASURED (computed here or reused from a committed file) or ASSUMED (an input, proxy or simplification).
  Reanalysis would be ASSUMED PERFECT FORECAST (none is planned).
- Counts only for Korea. No rate from fewer than 10 fires. n fires is stated beside every rate.
- Deliverables in this directory: `PROTOCOL.md`, `FIRES.md`, `RESULTS.md`, `numbers.json`, one risk-coverage figure,
  one 25 March timeline figure, the per-hour table, and the scripts that make them.
- Hard stop: Saturday 21 November 2026, 18:00 Shanghai time. Whatever is finished by then is reported as finished;
  the rest is reported as not done.

## Amendments
