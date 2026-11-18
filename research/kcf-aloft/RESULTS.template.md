# RESULTS: does forecast wind aloft warn of a fast run earlier or more reliably than the surface-gust rule? (kcf-aloft)

**Answer (MEASURED; counts only; rules frozen in `PROTOCOL.md` at 9802a32 before any outcome was computed).**
In this fire set, no. At the cost of the gust rule, a wind-aloft trigger warned no more run fire-days and was not
consistently earlier. It warned more only at thresholds that fire on a large part of every spring.

- **The n.** 12 Korean fires with an hourly reach: 43 fire-days, 791 issue hours. Only **4 fires had a run**, on
  **9 fire-days** (55 run hours): Uiseong 22, 23, 25 and 26 March 2025; Uljin 4, 5 and 10 March 2022; Gangneung
  5 March 2022; Sancheong 22 March 2025. Fewer than 10 fires, so no rate is given anywhere.
- **The gust rule from forecasts (G)** was firing at the first run hour on **4 of the 9** run fire-days, with lead
  times of 0, 1, 12 and 21 h. It fired on none of the 34 fire-days without a run. In the burden set it fires on
  3.7 days per point and season (on 11.8 days of a season at one or more of the ten points).
- **Wind aloft at equal cost.** The 850 hPa threshold that fires on as many burden point-days as G is 29.7 m/s,
  0.3 m/s below the declared A30. It warned **3 of 9**: the same days as G except Gangneung, 5 March 2022.
  On the three days both warned it was level on one, 1 h earlier on one and 4 h later on one. Frozen verdict: **no better**;
  lead mixed.
- **A25** warned the same 4 days as G, 1-2 h earlier on each, for three times the alarm days (11.3 per point and
  season) and alarms on 5 of the 34 fire-days without a run.
- **A-cal, the California threshold (15.2 m/s)**, warned 8 of 9 and 3-7 h earlier than G. That holds without
  25 March (7 of 8) and with every fire left out in turn. But it fires on **55 of the 104 days of a season** at a
  point, on 74 days somewhere among the ten points, and on 19 of the 34 fire-days without a run. A threshold set
  on California fires describes an ordinary Korean spring day. It is not a usable trigger.
- **Adding A to G.** A-cal or G is the same as A-cal alone. A30 or G warned the same 4 days as G, up to 1 h
  earlier on three of them, for 4.5 alarm days per point and season against 3.7.
- **The observed-gust rule (G-obs)**, run for all 12 fires with every KMA ASOS station within 50 km (added
  2026-11-18 under amendment 2), was firing at the first run hour on **1 of the 9** run fire-days (Gangneung,
  5 March 2022, 1 h ahead) and missed 49 of the 55 run hours. It fired on none of the 34 fire-days without a run.
  At Uljin on 4 and 5 March 2022 no station within 50 km recorded more than 14 m/s while the fire ran.
  {{GOBS_BURDEN}}
- **25 March 2025.** G fired from 09 KST, one hour before the first run hour (10 KST), on the same forecast cycle
  and at the same hour as A30. A25 fired from 08 KST and A-cal from 02 KST. What gave no warning that morning was
  the **observed** gust: the first 20 m/s within 50 km of the fire was recorded at 14:48 (Gumi), so G-obs first
  fired at 15 KST, five hours after the first run hour. The forecast gust carried the warning that kcf-abstain
  found in the 850 hPa wind. Without 25 March the counts are G 3 of 8, A at equal cost 2 of 8, A25 3 of 8,
  A-cal 7 of 8, G-obs 1 of 8.
- **Five of the 9 run fire-days had no warning from G or from any A at 25 m/s or more:** Uiseong 22, 23 and
  26 March 2025, Sancheong 22 March 2025 and Uljin 10 March 2022. These runs came on forecast wind below either
  trigger.
- **Second model.** ECMWF IFS is reachable only for the 2023 and 2025 fires. On 25 March it put the 850 hPa wind at
  27.6 m/s where GFS had 32-33 m/s, so A30 did not fire in IFS at all, while its forecast gust (21-22 m/s) did
  pass 20 m/s. No second model could be read for the 2022 fires (section 6).
- **What this cannot settle.** With 9 run fire-days from 4 fires, 4 of 9 and 3 of 9 are indistinguishable (exact
  intervals 14-79% and 8-70% of days; sign test p = 1.0). The result is "no advantage seen at equal cost", not
  "wind aloft is worse".

Labels: MEASURED unless marked. ASSUMED: the 5 h availability delay, the persistence definition, the independence
behind the exact intervals, and that KMA reports every gust of 20 m/s or more. PARTIAL: the first G-obs run (four
stations, one fire), kept in section 7 for the record. COARSE: seasons 2019-2020. All numbers are in
`numbers.json`; every table below is printed from it by `tables.py` (`derived/tables.md`) and placed here by
`make_results.py`. Intervals in brackets are exact 95% intervals for the share behind a count (Clopper-Pearson) or
for a mean count (Poisson); they treat days as independent, which they are not, so they are too narrow.

## What was known beforehand (disclosure)

The 850 hPa predictor was already known to flag 25 March 2025 when the protocol was written: that finding in
`research/kcf-abstain` is why this study exists. I had also read kcf-abstain's table of every Korean fire-day with
its margin misses and its largest forecast 850 hPa wind and gust, so the day-level picture of the any-hour rules
could be anticipated. Hour-level timing, lead times, the persistence rule, the burden set and the second model
were not known. 25 March is therefore not an independent test; every count is given with and without it.

## 1. What was run (frozen; details in `PROTOCOL.md`)

- **Fire set.** Reach, position and issue hours reused unchanged from `research/kcf-abstain/derived/hours.csv.gz`.
  A **run hour** is an issue hour whose 5 h reach exceeds 3.75 km; the spread happens within the next 5 h. KFS_01
  uses the detection product on 25 March 2025 and the Choi raster on other days. KFS_09 Yanggu, KFS_14 Uljin (May)
  and KFS_16 Suncheon have no issue hour with a 5 h reach: NOT TESTED.
- **Forecasts.** GFS 0.25 deg as issued, cycles 00/06/12/18 UTC, assumed available 5 h after the cycle, valid
  hours t+1 to t+8, the four lattice points around the fire. Fetched again here; the window maxima reproduce
  kcf-abstain's committed values on all 1,584 Korean rows to 0.000005 m/s.
- **Rules.**
  - **G**: forecast gust >= 20 m/s at two consecutive hourly forecast times in the next 8 h ("persist" = lasts at
    least one hour).
  - **G-obs**: KMA ASOS station gust >= 20 m/s in the hour ending at the issue hour, any station within 50 km
    (2 to 10 stations per fire position; hourly values from KMA apihub, station positions from KMA's table).
  - **A-cal**: forecast 850 hPa wind above 15.2 m/s (the value at which kcf-abstain's frozen rule abstains on that
    predictor alone; set by the 28 California fires). **A25**, **A30**: 25 and 30 m/s. **A+G**: either.
  - **A-match** (secondary, my addition): the 850 hPa threshold that fires on as many burden point-days as G.
- **Warned** = the rule is firing at the day's first run hour. **Lead** = whole hours it had been firing without a
  break before that hour, capped at 24 h, counting hours before ignition at the fire's first position.
- **Burden set.** Ten fixed points in Gangwon and Gyeongbuk, every day of 1 February to 15 May. As-issued GFS with
  hourly lead times exists from 26 February 2021, so the counts cover **seasons 2022-2025 in full and 2021 from
  27 February**. Per-season means use the four full seasons. Seasons 2019 and 2020 could not be read as specified
  (section 9).

## 2. Per rule: fire set and burden

{{T1:1}}

{{T1:2}}

{{T1:3}}

{{T1:4}}

- A lead of 24 is the cap: the rule had been firing for at least 24 h.
- "Alarm fire-days with no run": A30 and A-match fired at Sancheong and Ulju on 25 March 2025, where neither fire
  ran. A25 fired on 5 such days (Sancheong 25 March; Ulju 24, 25 and 26 March; Uiseong 27 March). A-cal fired on
  19 of them, at 8 different fires.
- "False-alarm days" leave out the 41 burden point-days that had a fire-set run within 100 km. Fast fires outside
  the fire set are not known here, so their days are counted as false alarms.

## 3. Every run fire-day

Lead in hours; in brackets, the lead counted only from the fire's first issue hour. "no" = not firing at the first
run hour.

{{T2}}

- Uljin 4 March 2022 ran within an hour of ignition. G fired at the first run hour but not the hour before; every
  A rule had been firing for 1-5 h at that place before the fire existed.
- Uljin 10 March 2022: no rule fired. The forecast 850 hPa wind stayed below 15.2 m/s all day.

## 4. Verdicts (frozen wording), with and without 25 March, leave-one-fire-out

{{T4}}

{{T3}}

- The A-cal verdict ("warned more", "earlier") is robust in the frozen sense, and its cost is in section 2:
  15 times the alarm days of G.
- At equal cost (A-match) and at A30 the verdict is "no better". Leaving out Gangneung makes them equal to G
  (3 against 3); nothing makes them better.

## 5. Burden set, season by season

{{T5:1}}

{{T5:2}}

{{T5:3}}

- G fires mostly on the east coast (Pohang, Yeongdeok, Uljin, Gangneung: 5-9 days a season) and on one day in four
  seasons at each of Andong, Chuncheon and Wonju. A30 has the same pattern. A-cal fires about equally everywhere.
- 2025 had the most alarm days under every rule.

## 6. Second model: ECMWF IFS (cross-check; enters no verdict)

{{T10}}

- IFS reads the 850 hPa wind lower than GFS on the strongest days. With IFS, A30 warned no run fire-day of 2025
  and A25 warned 25 March only, with no lead.
- For the fires of 2022 (Uljin, Gangneung: 4 of the 9 run fire-days) no second issued model is reachable from this
  session: ECMWF open data start on 18 January 2023, and GEFS is the same model family as GFS.

## 7. 25 March 2025, hour by hour, and the observed gust

{{T9b:1}}

**G-obs from all stations within 50 km, every fire (amendment 2; added after the first results were merged).**

{{T13}}

- **Where it fired.** In the whole fire set G-obs fired at 13 issue hours: 11 at Gangneung on 5 March 2022 (gusts
  to 23 m/s), and 15 KST and 19 KST at Uiseong on 25 March 2025 (Gumi 20 m/s at 14:48; Cheongsong 25 m/s at
  18:15). It also fired before ignition at Gangneung (evening of 4 March 2022) and at Yeongdeok (16 February 2022).
- **Where it did not.** Uljin, 4-5 March 2022: the three or four stations within 50 km recorded at most 14 m/s.
  Uiseong on 22, 23 and 26 March and Sancheong on 22 March 2025: at most 17 m/s inside any hour. The forecast gust rule G warned three run
  fire-days that G-obs did not (Uljin 4 and 5 March 2022, Uiseong 25 March 2025) and G-obs warned none that G
  missed.
- **A limit of the station file (amendment 3, post hoc).** At the three-hourly stamps a row can show the largest
  gust of the previous 3-6 h in place of the hour's own, so an hour's gust can be hidden behind an earlier one.
  The frozen reading drops such rows. Counting every hidden hour as firing (an upper bound) changes 10 fire hours
  and leaves the count of warned run fire-days at 1 of 9.
- G-obs uses ASOS stations only. KMA's denser AWS network was not read (the key is approved for the ASOS hourly
  endpoint alone), so a gust between stations is not seen. Values are whole m/s.

**The first G-obs run (PARTIAL: four stations, Uiseong only), kept for the record.**

{{T9}}

- This was the only G-obs possible before the KMA key was provided: the four stations committed by kcf-gust. With
  all stations within 50 km the 25 March result gains one earlier firing hour (15 KST, from Gumi).

## 8. Sensitivity (declared; changes no verdict)

{{T6}}

- **Persistence.** With no persistence (k = 1, the wording in press reports of the rule), G warns the same 4 days
  and gains 1 h of lead on each, for 4.8 alarm days per point and season instead of 3.7 and 2 alarm fire-days
  without a run. Requiring 3, 4 or 6 consecutive hours loses run days (3, 2 and 1 of 9).
- **Window.** G at the same lattice point is identical to G. G on a 5 h window warns only 2 of 9: the look-ahead to
  8 h is what gives G its two short-lead warnings (25 March 2025 and Uljin 4 March 2022).
- **Persistence for A.** Requiring two consecutive hours drops A25 to 3 of 9 and A30 to 2 of 9.

**Threshold sweep (descriptive, post hoc reading; 9 run fire-days from 4 fires).**

{{T7}}

- At the low-alarm end, gust is at least as good as wind aloft: 4 of 9 costs 3.7 days with gust (20 m/s, 2 h) and
  9.3 days or more with the 850 hPa wind (26 m/s or lower).
- At the high-alarm end the order reverses: the 850 hPa wind reaches 8 of 9 at 18 m/s for 41 alarm days per point
  and season, where no gust threshold from 10 m/s up reaches more than 6 of 9. An alarm on 40 days of a 104-day
  season is not a trigger, and this is a reading of a sweep, not a tested rule.

## 9. Height of 850 hPa against the ridges

{{T11}}

- 850 hPa sat at about 1,400-1,540 m. That is 400-620 m above the highest ground within 10 km of the Uiseong,
  Uljin and Gangneung fires, and **below** the Jirisan ridge at Sancheong (1,496 m within 10 km, 1,898 m within
  25 km). Near Gangneung and Sokcho the main Taebaek ridge within 25 km reaches or exceeds it.
- So the 850 hPa wind is the free-air wind several hundred metres above the ridge line of the east-coast fires,
  not the wind at the fire. GFS's own terrain at these lattice points is 0-760 m, far below the real ridges.

## 10. Seasons 2019 and 2020 (S5, COARSE; not pooled, no verdict)

The as-issued GFS 0.25 deg archive reachable here starts in 2021, so the frozen rules cannot be read for 2019 and
2020. The substitute is the operational GEFS control as issued (1 deg, lead times 6, 12, 18 h), a coarser run of an
older model version, with the any-time gust form only.

{{T12}}

- The bridge shows that the coarse sampling reads lower than the full-resolution rule at 25 and 30 m/s (for example
  6.9 against 11.1 days in 2022 at A25), so the 2019-2020 counts are likely low for those two.
- A-cal fires on 39-71 days per point and season in 2021-2025 (2021 from 27 February) and, in the coarse reading,
  on 43 and 61 days in 2019 and 2020.

## 11. Other secondary analyses

{{T8}}

- S1: with the Choi raster on 25 March, Uiseong's first run hour that day is 01 KST instead of 10 KST, before the
  gust forecast reached 20 m/s, so G warns 3 of 9 instead of 4.
- S6: counting only the hours kcf-abstain scored changes some lead times and no count of warned days.

## What this does not show

- **Not a rate, and not a general result.** 9 run fire-days from 4 fires, in two weather episodes (4-5 March 2022,
  22-26 March 2025) plus one day. Days of one fire are not independent.
- **Not the official rule as applied.** The official text was not read; "persist" is my definition. Officials use
  KMA forecasts and KMA stations, not GFS. GFS gust is a model diagnostic on a 0.25 deg grid.
- **Not the observed-gust rule as an official sees it.** G-obs reads ASOS stations only (2-10 within 50 km), in
  whole m/s, from a field that can hide a gust at three-hourly stamps. Officials also see AWS stations and their
  own reports.
- **Not seasons 2019-2020 as specified,** and season 2021 only from 27 February.
- **Not independent of 25 March.** The predictor was known to flag that day before the protocol.
- **Not a test of timing as experienced.** Issued forecasts are assumed available 5 h after the cycle. The run
  hour comes from a 5 h reach on kriged rasters (detections on 25 March), so "first run hour" is itself uncertain
  by an hour or more, and several lead times of 0-2 h sit inside that uncertainty.
- **Not a cost in evacuations.** A burden alarm day is a day the rule would fire if a fire were burning at that
  point. Fast fires outside the fire set (for example Goseong-Sokcho 2019, Gangneung 2023) are counted as false
  alarms.
- **Not a statement about what anyone should have done.**

## Not done

{{GOBS_NOT_DONE}}
- A second model for the 2022 fires.
- Seasons 2019-2020 under the frozen rules (S5 is a coarse substitute).

## Data and provenance

- **Reach, position, issue hours.** `research/kcf-abstain/derived/hours.csv.gz` (main at 16c0957), unchanged. Not
  recomputed: the Choi rasters are on Zenodo, which this session cannot reach.
- **GFS.** Issued GFS 0.25 deg from AWS `noaa-gfs-bdp-pds`, by byte range from each forecast hour's `.idx`:
  2,120 cycles, 70.9 GB read, fetched 2026-11-18 15:33-16:11 UTC. Every cycle is present. The only cycles with
  missing lead times are the 103 from 2021-01-31 06 UTC to 2021-02-25 18 UTC, where the archive holds 3-hourly
  leads only; those days are not evaluated (season 2021 starts on 27 February).
- **ECMWF IFS.** Open data from AWS `ecmwf-forecasts`: 1,255 cycles, 11.6 GB, fetched 15:39-16:48 UTC; 0.4 deg in
  2023, 0.25 deg from 1 February 2024; the gust field `10fg` is in the 2025 files only. The 26 cycles from
  2023-04-26 12 UTC to 2023-05-02 18 UTC are not in the bucket, so 7 days of season 2023 have no IFS reading.
- **GEFS (S5).** Control forecast from AWS `noaa-gefs-pds`: 838 cycles, 0.5 GB. One cycle (2019-02-19 06 UTC) has
  no gust file in the archive (20 point-days without the coarse gust).
- **Station gusts.** KMA apihub `kma_sfctm2.php` (ASOS hourly, all stations, one call per KST hour), fetched
  2026-11-18 from 22:58 UTC with a key held outside the repo and never logged: {{KMA_FETCH}} Every gust record is
  in `derived/kma_gust_records.csv.gz`; station positions are KMA's data-wiki table as of 2023-09-01
  (`derived/kma_asos_stations.csv`). The first, four-station run used `research/kcf-gust/work/kma_asos_hourly.json`.
- **Terrain.** SRTM 1 arc-second tiles from AWS `elevation-tiles-prod`.
- **Committed here.** `derived/fire_hours.csv.gz` (every fire hour with its rule levels), `derived/burden_days.csv.gz`
  (every point-day), the IFS and coarse day tables, `derived/tables.md`, `numbers.json`. Fetch logs with per-cycle
  times are summarised in `numbers.json` -> `meta.fetch`.
- **Tests.** `tests/` has 20 tests: the rule and metric code against brute force; an independent recount of the
  run fire-days, run hours, the A-rule counts (from kcf-abstain's committed window maxima) and the burden counts;
  and the headline statements of this file and the note against `numbers.json`.

## Reproduce

```bash
W=WORK_DIR
python3 fetch_gfs.py --out $W/nwp --seasons 2021 2022 2023 2024 2025 --ranges 2022-02-12T00:2022-02-17T06 \
  2022-03-02T00:2022-03-12T18 2022-04-08T00:2022-04-11T18 2022-05-26T00:2022-06-02T18 2023-03-06T00:2023-03-09T18 \
  2023-03-31T00:2023-04-04T06 2025-03-19T00:2025-04-01T00 2025-04-26T00:2025-04-30T18
python3 fetch_ifs.py --out $W/nwp --seasons 2023 2024 2025 --ranges 2023-03-06T00:2023-03-09T18 2023-03-31T00:2023-04-04T06 \
  2025-03-19T00:2025-04-01T00 2025-04-26T00:2025-04-30T18
python3 fetch_gefs.py --out $W/nwp --seasons 2019 2020
python3 fire_set.py --nwp $W/nwp/gfs_KOR --out derived/fire_hours.csv.gz
python3 burden.py --nwp $W/nwp/gfs_KOR --seasons 2021 2022 2023 2024 2025 --out derived/burden_days.csv.gz
KMA_KEY_FILE=/path/to/key python3 fetch_kma.py --out $W/kma_hours.jsonl --fire derived/fire_hours.csv.gz \
  --seasons 2025 2024 2023 2022 2021 2020 2019
python3 gobs.py --kma $W/kma_hours.jsonl --fire derived/fire_hours.csv.gz --out-dir derived
python3 analyze.py --fire derived/fire_hours.csv.gz --burden derived/burden_days.csv.gz --out derived/analysis.json
python3 crosscheck_ifs.py --ifs $W/nwp/ifs_KOR --gfs $W/nwp/gfs_KOR --fire derived/fire_hours.csv.gz \
  --burden derived/burden_days.csv.gz --out derived/ifs_crosscheck.json
python3 height.py --fire derived/fire_hours.csv.gz --burden derived/burden_days.csv.gz --tiles $W/tiles --out derived/height.json
python3 coarse.py --gefs $W/nwp/gefs_KOR --burden derived/burden_days.csv.gz --out derived/coarse_s5.json
python3 make_numbers.py --nwp $W/nwp --out numbers.json
python3 tables.py numbers.json > derived/tables.md && python3 make_results.py
python3 figure.py --numbers numbers.json --out fig/lead_time.png
python3 -m pytest -q tests
```

Needs numpy, pandas, scipy, pygrib, matplotlib, and network access to the AWS open-data buckets `noaa-gfs-bdp-pds`,
`noaa-gefs-pds`, `ecmwf-forecasts` and `elevation-tiles-prod`, and to `apihub.kma.go.kr` with a KMA key approved for
`kma_sfctm2.php`. The forecast extracts (about 80 GB of GRIB byte
ranges read, 0.3 GB kept) stay outside git.
