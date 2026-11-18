# PROTOCOL: does forecast wind aloft warn of a fast run earlier or more reliably than the surface-gust rule? (kcf-aloft)

Frozen 2026-11-18, committed before any outcome of this study was computed: no rule state, lead time, warned or
missed count, burden count or second-model value existed when this was written. Changes after this commit go in
"Amendments" at the end, each with its reason and the time it was made.

**Question.** Since April 2025, Korean authorities widen the evacuation area when gusts of 20 m/s or more are
expected to persist. Across Korean fires, does a forecast of wind at 850 hPa warn of a fast run earlier, or more
reliably, than that surface-gust rule, and how many extra alarm days would it cost? If wind aloft does no better,
that is the result.

## 0. What was known when these rules were written (disclosure)

- **The 850 hPa predictor was already known to flag 25 March 2025.** `research/kcf-abstain/RESULTS.md` shows that the
  GFS forecast issued that morning had 32-33 m/s at 850 hPa at the 10-16 KST issue hours, with a forecast gust of
  23-24 m/s, while station gusts and prior spread showed nothing at 10-11 KST. That finding is the reason for this
  study. 25 March is therefore not an independent test, and every result is reported with and without it.
- **More than 25 March was known.** The same file prints, for every Korean fire-day, the number of 5 h margin
  misses and the day's largest forecast 850 hPa wind and forecast gust (window maxima). I read that table before
  writing this protocol. From it one can already see which fire-days had a run and roughly which days exceed a given
  850 hPa or gust value at some hour. So the day-level picture for the any-hour forms of the rules could be
  anticipated. **Not known when this was written:** the rule state at each hour, onset times and lead times, the
  effect of a persistence requirement, the hours before ignition, anything about the burden set, any second-model
  value other than the ECMWF 850 hPa wind on 25 March 2025, and any station gust outside 22-26 March 2025.
- **Before freezing, only these values were computed:** the California-only 850 hPa threshold of section 3 and, for
  context, how often each rule's any-hour form holds in the 28 California calibration fires
  (`research/kcf-abstain/derived/hours.csv.gz`, rows with role = calibration only). Archive listings and field
  names were checked for reachability (no values read), and one ISD station file (Andong 2025) was opened to see
  whether it carries gusts (it does not).
- Because of the second point, every choice below was made to leave as little discretion as possible: the gust
  threshold is the rule's own 20 m/s, the primary 850 hPa threshold is inherited from a number frozen in kcf-abstain
  before any Korean value was read, 25 and 30 m/s are fixed by the brief, and the rest are mechanical rules.

## 1. Units

### 1a. Fire set

Every Korean fire in `research/kcf-abstain/FIRES.md` (15 fires, rows 29-43) that has an hourly reach. The reach,
the fire's position at each hour and the issue hours are reused unchanged from
`research/kcf-abstain/derived/hours.csv.gz` (main at 16c0957). They are not recomputed (the Choi rasters are on
Zenodo, which this session cannot reach). A fire with no scored issue hour there is NOT TESTED, with that reason.

- **Reach.** S_5(t), the kcf-margin 5 h reach (5 km separate-fire rule), column `reach5_km`.
- **Run hour.** A scored issue hour t with S_5(t) > 3.75 km (the frozen kcf-margin margin R(5 h)). The fast spread
  happens somewhere in (t, t+5 h].
- **Fire-day.** A KST calendar day (UTC+9) on which the fire has at least one scored issue hour. A **run fire-day**
  has at least one run hour; its **first run hour** t1 is the earliest of that day.
- **Products.** KFS_01: the detection product (DET) on 25 March 2025, 00-23 KST, and the Choi raster on its other
  days (primary, as in kcf-abstain). All other fires: Choi rasters. Secondary: KFS_01 from the Choi raster on every
  day. The fire-day KFS_01 / 25 March is counted once.
- **Position.** P_t = `lat`, `lon` of the row (centroid of the known burned area at t). For the hours before a
  fire's first issue hour (needed for lead time), P is the position at the first issue hour.

### 1b. Burden set (no fire needed)

- **Points (ten, fixed now).** Positions of KMA synoptic stations, chosen for spread: coast and inland, north to
  south, five per province. Gangwon: Sokcho 38.2509 N 128.5647 E; Gangneung 37.7709 N 128.8681 E; Taebaek 37.1703 N
  128.9893 E; Chuncheon 37.9000 N 127.7333 E; Wonju 37.4381 N 127.9604 E. Gyeongbuk: Uljin 37.0000 N 129.4167 E;
  Yeongdeok 36.5333 N 129.4094 E; Pohang 36.0333 N 129.3833 E; Andong 36.5667 N 128.7000 E; Sangju 36.4167 N
  128.1500 E. (Eight are the coordinates in the NOAA ISD station files; Taebaek and Yeongdeok are not in ISD and are
  approximate station positions. The point, not the station, is what is fixed.)
- **Season.** The official spring forest-fire caution period, 1 February to 15 May, KST days, 2019 to 2025
  (seven seasons; 104 days, 105 in 2020 and 2024). The autumn period is not counted.
- **Rule state.** At every whole KST hour of every season day, each rule is evaluated at each point exactly as for
  a fire, with the point in place of P_t.
- **Alarm day.** A point-day on which the rule fires at one or more of its 24 issue hours. A point-day with any
  issue hour that cannot be evaluated (missing forecast) is left out and counted.
- **False-alarm day.** An alarm day at a point, unless a fire of the fire set had a run hour on that KST day within
  100 km of the point. Fast fires that are not in the fire set (for example Goseong-Sokcho 2019, Gangneung 2023)
  are not known to this study, so their days count as false alarms; this is a stated limit.
- **What can be read as issued.** The reachable GFS 0.25 deg archive (AWS `noaa-gfs-bdp-pds`) starts 2021-01-01, and
  hourly lead times start some weeks into 2021 (the exact date is found by the fetch and reported). So the frozen
  rules can be evaluated for seasons 2021-2025 only, and 2021 only from the first day with hourly leads.
  **Seasons 2019 and 2020 cannot be read as specified.** They are covered only by the labelled coarse substitute
  S5 (section 6), never pooled with the others.

## 2. Forecasts as issued

The kcf-abstain rule, unchanged (`research/kcf-abstain/PROTOCOL.md` section 3):
- **GFS 0.25 deg**, cycles 00/06/12/18 UTC, **assumed available 5 h after the cycle**. Issue hour t uses c(t), the
  latest cycle with c + 5 h <= t, and reads the valid hours t+1 ... t+8 (lead times 6-18 h).
- **Where.** The four 0.25 deg lattice points at the corners of the lattice cell that contains P_t (or the burden
  point).
- Fields: `GUST:surface`, `UGRD` and `VGRD` at 850 mb, and `HGT` at 850 mb (section 5). The extracts are fetched
  again here by byte range (kcf-abstain did not commit them). **Reproduction check:** the 8 h window maxima of gust
  and 850 hPa wind computed here must equal the committed `gust_ms` and `w850_ms` of every Korean row of
  `hours.csv.gz` to 0.001 m/s. If they do not, the difference is reported before anything else.
- An issue hour whose window is incomplete (any valid hour, point or field missing) has no rule state; it is
  counted and never filled.

## 3. Rules (fixed; nothing is added or changed after this commit)

Notation at issue hour t: g(v) = the largest forecast gust over the four points at valid hour v; w(v) = the largest
forecast 850 hPa wind speed, sqrt(u^2 + v^2), over the four points at valid hour v; v runs over t+1 ... t+8.

- **G (forecast gust rule).** Fires at t if g(v) >= 20.0 m/s at **two consecutive hourly valid times** within
  t+1 ... t+8. *Definition of "persist", stated once:* the forecast gust stays at or above 20 m/s from one hourly
  forecast time to the next, so for at least one hour, somewhere on the four points around the fire. Reason: it is
  the weakest requirement that is more than a single forecast value. Press reports of the April 2025 rule give it
  without the word "persist" ("maximum instantaneous wind speed of 20 m/s or more in the area"); that reading is
  k = 1 in the sensitivity table. The official text could not be read from this session.
- **G-obs (observed gust, what an official sees).** Fires at t if a KMA ASOS station within 50 km of P_t recorded
  a maximum instantaneous gust >= 20 m/s in the hour ending at t. Conventions as kcf-gust amendment 3: hourly
  `GST_WS`, a record counts only if `GST_TM` is in (t - 1 h, t], whole m/s (truncated), no record = below 10 m/s.
  No persistence. **Data available to this session:** only the four stations committed in
  `research/kcf-gust/work/kma_asos_hourly.json` (Uiseong 278 at 36.3561 N 128.6886 E, Andong 136 at 36.5729 N
  128.7073 E, Cheongsong 276 at 36.4351 N 129.0401 E, Yeongdeok 277 at 36.5333 N 129.4094 E; approximate station
  positions), 22-26 March 2025 KST. The KMA key is not in this session and the KMA hosts are blocked, and neither
  NOAA ISD nor GSOD carries gusts for these stations. So G-obs is run for KFS_01 only and labelled PARTIAL (four
  stations); for every other fire and for the burden set it is **NOT RUN**, and nothing is substituted.
- **A (wind aloft).** Fires at t if max over v of w(v) is above a threshold.
  - **A-cal (primary), threshold from the California calibration fires only.** A-cal fires when the 8 h window
    maximum of the 850 hPa wind has a fire-weighted tail probability, among the 28 California calibration fires, at
    or below the abstention threshold tau = 0.010728508563521567 that kcf-abstain froze (commit ef50d2a) before any
    Korean value was read. This is exactly "kcf-abstain's rule abstains on account of the 850 hPa wind alone".
    Computed now from the 20,065 scored calibration hours: **A-cal fires when the window maximum exceeds
    15.20023 m/s** (the largest calibration value whose tail probability is above tau; the next value, 15.21336 m/s,
    is the first that fires). In California this holds in 70 hours of 4 fires (fire-weighted 1.06% of hours);
    the any-hour gust >= 20 m/s holds in 87 hours of 4 fires (0.87%). All of those hours are HRRR fires.
  - **A25, A30 (declared in the brief).** Window maximum >= 25.0 m/s and >= 30.0 m/s. (The largest calibration
    value is 30.06 m/s, so A30 is, to 0.06 m/s, "beyond every calibration hour".)
  - A has no persistence requirement (the brief gives none); persistence for A is in the sensitivity table.
- **A+G.** Fires if A-cal or G fires. Also reported: A25 or G, A30 or G.

**Sensitivity table (declared now, reported in full, cannot change a verdict).**
- G with k = 1, 2 (primary), 3, 4 and 6 consecutive hourly valid times; G with k = 2 at the same lattice point;
  G (k = 2) on a 5 h window (valid hours t+1 ... t+5).
- A-cal, A25 and A30 with k = 1 (primary), 2 and 3 consecutive hourly valid times.
- Threshold sweep, descriptive: gust from 10 to 30 m/s and 850 hPa wind from 10 to 40 m/s in steps of 1 m/s
  (k = 2 and k = 1 for gust, k = 1 for wind aloft), each with its fire-set and burden-set counts.
- **S-match (secondary, my addition, not in the brief).** A at the 850 hPa threshold at which A fires on the same
  number of burden point-days (seasons 2021-2025, all ten points) as G: the smallest threshold on a 0.1 m/s grid
  whose alarm point-days do not exceed G's. It is fixed by the burden set alone, which contains no fire outcome, and
  its value is unknown now. Purpose: compare the two rules at equal cost. Undefined if G has no alarm point-day.

No threshold is chosen or changed after a Korean outcome is seen. A-cal, 25, 30 and 20 m/s are final.

## 4. Metrics (per rule)

Rule states are computed for every issue hour of each fire and for the 24 h before its first issue hour.

- **M1 Warned.** A run fire-day is warned if the rule is firing at its first run hour t1 (a forecast available at
  t1 says so, before the spread of (t1, t1 + 5 h]). Count k of n run fire-days.
- **M2 Lead time.** L = the number of whole hours immediately before t1 through which the rule fired without a
  break, capped at 24 h. L = 0 if it first fires at t1. Undefined (not warned) if it is not firing at t1. Reported
  per run fire-day, twice: counting hours before ignition (primary; the rule would already be in force for any fire
  at that place), and counted only from the fire's first issue hour. "Warned at least 1 h ahead" (L >= 1) is counted
  beside M1.
- **M3 Run hours missed.** Run hours at which the rule is not firing, of all run hours.
- **M4 Alarm fire-days without a run.** Fire-days with no run hour on which the rule fired at one or more scored
  issue hours, of all such fire-days.
- **M5 Burden.** Alarm days and false-alarm days per season, per point (section 1b): each season's count at each
  point, the mean over the ten points with its smallest and largest point, and the number of season days on which
  the rule fires at one or more of the ten points.
- **Lapsed-warning variant (sensitivity).** Warned if the rule fired at any issue hour in [t1 - 12 h, t1].

**Intervals and what is not computed.**
- Counts only. No rate is computed from fewer than 10 fires, and the fire set has fewer than 10 fires with a run.
- Each count k of n is given with its exact (Clopper-Pearson) 95% interval for the underlying proportion. It treats
  fire-days as independent, which they are not (days of one fire share its weather), so it is too narrow; the
  number of fires behind each count is stated beside it.
- Per-season burden counts are listed season by season. The mean per season carries an exact Poisson (Garwood) 95%
  interval on the total, which assumes independent days (windy days cluster, so again too narrow; ASSUMED).
- A against G on run fire-days: the two discordant counts (warned by A only, by G only) and the exact two-sided
  sign-test p value, with the same caveat.
- **With and without 25 March** (the fire-day KFS_01 / 2025-03-25 removed), and **leave-one-fire-out** (every count
  recomputed with each fire removed in turn; the range is reported and each fire that changes a verdict is named).

**Verdicts (frozen wording; A-cal against G unless stated).**
- *More reliably.* "A warned more run fire-days than G" only if M1(A) > M1(G) in the full set, without 25 March,
  and in every leave-one-fire-out set. "No better" if M1(A) <= M1(G) in the full set. Anything else: "not robust",
  naming the fire-day or fire it depends on.
- *Earlier.* On run fire-days warned by both: "A earlier" only if L(A) >= L(G) on all of them and L(A) > L(G) on at
  least one, with and without 25 March. "No earlier" if L(A) <= L(G) on all. Anything else is described.
- *Cost.* The burden counts of A and G are stated next to both verdicts, always.
- *At equal cost.* The same two verdicts for S-match against G. This is the comparison that says whether wind
  aloft adds information beyond firing more often.
- The same verdicts are printed for A25, A30 and A+G against G, as counts.

## 5. Second model and the height of 850 hPa

- **Second model: ECMWF IFS open data** (AWS `ecmwf-forecasts`; 0.4 deg from 2023-01-18, 0.25 deg from 2024),
  3-hourly steps, the same cycle rule (c + 5 h <= t; the real open-data release is later, about 7-9 h after the
  cycle, so this checks the model, not the timing). Read at the four points of the model's own lattice cell around
  P_t; the window is the 3-hourly valid times in (t, t + 8 h] (two or three). Rules: A-cal, A25, A30 with the same
  thresholds; for 2025 also the any-step gust >= 20 m/s (`10fg`, a 3 h maximum, k = 1 form; not in the 2023 files).
  - Fire set: fires from 2023-01-18 on (the 2023 and 2025 fires). **Not available for the 2022 fires** (Uljin,
    Gangneung, Yanggu, Gunwi, Yeongdeok, Miryang, Uljin May); no other independent issued model for 2022 is
    reachable from this session, and that is reported as such.
  - Burden set: seasons 2023 (from 1 February), 2024 and 2025, rule A only.
  - Beside it, GFS thinned to the same 3-hourly valid times, to separate the model from the sampling.
  - It is a cross-check: agreement and disagreement are reported; it does not enter a verdict.
- **Height.** For each fire and each burden point: the GFS forecast geopotential height of 850 hPa (median, minimum
  and maximum over the hours read), the highest ground within 10 km and within 25 km (SRTM 1 arc-second tiles, AWS
  `elevation-tiles-prod`; for a fire, around every P_t), and the GFS model terrain at the four lattice points.
  Reported as metres and as the gap between 850 hPa and the local ridge.

## 6. Secondary analyses, declared now

- **S1** KFS_01 from the Choi raster on every day (section 1a).
- **S2** The sensitivity table and S-match of section 3; the lapsed-warning variant of section 4.
- **S3** The second model (section 5).
- **S4** The fire set's hours pooled, as counts: a 2 x 2 of rule firing against run hour, per rule.
- **S5 Seasons 2019 and 2020, coarse substitute, labelled COARSE in every table.** The operational GEFS control
  forecast as issued (AWS `noaa-gefs-pds`, 1 deg, lead times 6, 12 and 18 h only): 850 hPa wind for A, `GUST` for
  the any-hour form of G (persistence cannot be evaluated on 6-hourly values). Same cycle rule; the four 1 deg
  points around the burden point; the valid times of the window that exist. To show what the coarse sampling does,
  GFS 2021-2025 is degraded to the same sampling (1 deg points, leads 6, 12, 18) and its counts are put beside the
  full-resolution counts. S5 is never pooled with seasons 2021-2025 and enters no verdict. If it is not finished by
  the hard stop it is reported as not done.

## 7. Reporting

- Labels: MEASURED (computed here or reused from a committed file), ASSUMED (an input, proxy or simplification),
  PARTIAL, COARSE, NOT RUN.
- Deliverables in `research/kcf-aloft/`: `PROTOCOL.md`, `RESULTS.md`, `numbers.json`, one figure (lead time per
  run fire-day, G and A-cal), a one-page note in Korean and English, "What a wind-aloft trigger would add to the
  gust rule" (the result, the n, what it does not show), and the scripts and unit tests that make them.
- Nothing here says what anyone should have done on any day.
- Hard stop: Saturday 21 November 2026, 12:00 Shanghai time (04:00 UTC). Whatever is finished by then is reported
  as finished; the rest is reported as not done.

## Amendments

1. **2026-11-18 15:36 UTC (commit 556f842; the first version of this line said 15:50 by mistake), before any rule state or outcome was computed (only the column layout of `hours.csv.gz`
   had been looked at).** Clarification of "scored issue hour" in sections 1a and 4. It means a row of
   `hours.csv.gz` that has a 5 h reach (`reach5_km` present; for the detection product, the rows kcf-margin flags
   complete). This includes the first three issue hours of each fire, which kcf-abstain left without an abstention
   score only because its prior-3 h spread predictor is undefined there; that predictor plays no part here, and a
   fire's first hours are where a warning matters most. **S6 (new secondary):** every fire-set count is also given
   on kcf-abstain's scored hours only, so the effect of this reading is visible. Fires with a reach but fewer rows:
   none is dropped by either reading.

2. **2026-11-18 22:57 UTC. Made after every other result of this study had been computed and published (RESULTS.md,
   merged), and before any KMA station value beyond the kcf-gust file was fetched or read.** A KMA apihub key became
   available, so G-obs can now be run as frozen in section 3. What was checked first, by status codes, column names
   and station ids only (no gust value read): the key is approved for `kma_sfctm2.php` alone (ASOS hourly, one call
   per KST hour, `stn=0` returns all 95-97 ASOS stations); the station-list, period and daily endpoints answer 403;
   about four calls in ten time out and succeed on retry. Rules fixed now:
   - **Data.** `kma_sfctm2.php?tm=YYYYMMDDHH00&stn=0` for every KST hour needed; columns `STN`, `GST WS`, `GST TM`.
     Conventions unchanged from section 3 (kcf-gust amendment 3). An hour that still fails after 8 tries is listed
     and left unevaluated, never filled. The key is read from a file outside the repo and is never logged.
   - **Stations.** Every ASOS station in the response. Coordinates from KMA's data-wiki station table (as of
     2023-09-01; saved as `derived/kma_asos_stations.csv`). A station counts for a place if its great-circle distance
     is at most 50 km. Station moves between 2019 and 2025 are not tracked (stated limit).
   - **State at an hour.** Known if one or more stations within 50 km have a row at that stamp; fires if any of
     them has a gust >= 20 m/s recorded inside the hour ending at the stamp. Unknown otherwise.
   - **Fire set.** Every hour of every fire's primary timeline, including the 24 h before its first issue hour,
     for all 12 fires. KFS_01 is evaluated again with all stations within 50 km; the four-station PARTIAL result
     already reported stays in the record beside it.
   - **Burden set.** The same ten points, the point in place of P_t. A point-day is evaluated if all 24 stamps
     (00:00 to 23:00 KST) are known; an alarm day has one or more firing stamps. Observations do not depend on the
     forecast archive, so all seven seasons 2019-2025 can be read. Fetch order: 2025, 2024, 2023, 2022 (the four
     full seasons of the forecast rules; the per-season mean beside G and A uses these four), then 2021, 2020, 2019.
     The burden needs about 17,500 calls plus retries; whatever is complete at the hard stop is reported and the
     rest is NOT RUN.
   - **Reported.** G-obs in the same per-rule table (M1-M5), with and without 25 March and leave-one-fire-out, and
     the frozen comparison counts of G against G-obs and of each A rule against G-obs. These are descriptive: the
     frozen verdicts of section 4 stay A against G. The data-quality counts of kcf-gust amendment 3 (share of hours
     with no record, smallest recorded gust, records timed outside their hour) are reported for the new file.
   - Nothing else changes. No threshold, window or definition of any rule is touched.

3. **2026-11-18 23:11 UTC. Post hoc, after the fire-set station values had been read. No rule changed.** The new
   file shows what the hourly gust field is: at the three-hourly stamps (00, 03, ... 21 KST) a row can carry the
   largest gust of the previous 3 to 6 h in place of the hour's own (3,062 of 9,100 records in the fire-set hours
   are timed outside their hour, all at those stamps, none older than 6 h; 96 of them are 20 m/s or more, and every
   one of those repeats a record that was counted in its own hour). The frozen convention drops such a record, so
   at those stamps an hour's own gust of 20 m/s or more can be hidden behind an earlier, larger one, and G-obs can
   read "not firing" when it was. This cannot remove an alarm day or delay the first firing hour of an episode; it
   can break a run of firing hours and miss a later hour. The frozen reading stays primary. Beside it a **post hoc
   upper bound** is reported in which every such hidden hour counts as firing. Also found: the smallest recorded
   gust is 7 m/s, not the 10 m/s kcf-gust inferred from five days; "no record" therefore means "no gust reported",
   and that a gust of 20 m/s or more is always reported is ASSUMED.
