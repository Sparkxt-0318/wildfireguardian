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
2. **The California pass does not come from the hourly update.** With the hourly update switched off the same model
   needs no more area (220.6 km2; tracker / update-off = 1.02, 0.96 to 1.08), and with the forecast input switched off
   it also needs no more (228.9 km2; ratio 0.99, 0.95 to 1.04). On Korea the hourly update makes the margin worse
   (tracker / update-off = 1.24, 1.02 to 1.33). The gain over QUANTILE (5%, 1% at exactly equal miss) needs neither
   switch on its own. The version with both off was NOT RUN, so what the gain does come from is not isolated; the
   hourly state update, the point of this study, is not it.
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

{{Results table}}

Ratios between methods (paired by fire):

{{Ratios (paired fire bootstrap)}}

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

{{Target A detail}}

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

{{Korea, secondary rows}}

The straight California transfer repeats kcf-adaptive2: learned methods are conservative on Korea (2% to 5% miss) and
flag more area. Read at exactly 10% miss, none is below the fixed margin (52.1 km2).

## 4. 25 March 2025, hour by hour

Detection product (FIRMS VIIRS + Himawari), KFS_01 held out of every fit. Each row uses only what was available at that
hour: the forecast as issued (5 h availability delay, ASSUMED), growth seen up to that hour, and the model. "enter" is
the forecast-driven probability of moving from quiet to run; c is the alarm threshold from the burden set. Margins in
km; **M** = missed, h = held. One fire, one day: counts only.

{{25 March 2025, KFS_01 (model fitted without KFS_01)}}

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
