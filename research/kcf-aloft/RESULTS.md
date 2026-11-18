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
- **25 March 2025.** G fired from 09 KST, one hour before the first run hour (10 KST), on the same forecast cycle
  and at the same hour as A30. A25 fired from 08 KST and A-cal from 02 KST. What gave no warning that morning was
  the **observed** gust (G-obs: silent until 19 KST). The forecast gust carried the warning that kcf-abstain found
  in the 850 hPa wind. Without 25 March the counts are G 3 of 8, A at equal cost 2 of 8, A25 3 of 8, A-cal 7 of 8.
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
behind the exact intervals. PARTIAL: G-obs (four stations, one fire). COARSE: seasons 2019-2020. All numbers are in
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
  - **G-obs**: KMA station gust >= 20 m/s in the hour ending at the issue hour, station within 50 km.
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

**all run fire-days**

| rule | run fire-days / fires | warned at the first run hour | warned >= 1 h ahead | lead times, h | run hours missed | alarm fire-days with no run | burden: alarm days per point and season | false-alarm days per point and season | days per season with an alarm at any of ten points |
|---|---|---|---|---|---|---|---|---|---|
| G | 9 / 4 | 4 of 9 (14-79%) | 3 of 9 (8-70%) | 0, 1, 12, 21 | 37 of 55 (53-79%) | 0 of 34 (0-10%) | 3.7 (3.1-4.3) | 3.3 (2.8-3.9) | 11.8 (8.6-15.6) |
| A-cal | 9 / 4 | 8 of 9 (52-100%) | 8 of 9 (52-100%) | 5, 8, 17, 22, 24, 24, 24, 24 | 10 of 55 (9-31%) | 19 of 34 (38-73%) | 55.1 (52.9-57.5) | 54.2 (52.0-56.6) | 73.8 (65.6-82.7) |
| A25 | 9 / 4 | 4 of 9 (14-79%) | 4 of 9 (14-79%) | 2, 2, 14, 23 | 37 of 55 (53-79%) | 5 of 34 (5-31%) | 11.3 (10.3-12.4) | 10.7 (9.7-11.8) | 28.0 (23.1-33.7) |
| A30 | 9 / 4 | 3 of 9 (8-70%) | 3 of 9 (8-70%) | 1, 1, 8 | 41 of 55 (61-85%) | 2 of 34 (1-20%) | 3.1 (2.6-3.7) | 2.8 (2.3-3.3) | 9.5 (6.7-13.0) |
| A+G | 9 / 4 | 8 of 9 (52-100%) | 8 of 9 (52-100%) | 5, 8, 17, 22, 24, 24, 24, 24 | 10 of 55 (9-31%) | 19 of 34 (38-73%) | 55.1 (52.9-57.5) | 54.2 (52.0-56.6) | 73.8 (65.6-82.7) |
| A25+G | 9 / 4 | 4 of 9 (14-79%) | 4 of 9 (14-79%) | 2, 2, 14, 23 | 34 of 55 (48-75%) | 5 of 34 (5-31%) | 11.6 (10.5-12.7) | 10.9 (9.9-12.0) | 28.2 (23.3-34.0) |
| A30+G | 9 / 4 | 4 of 9 (14-79%) | 4 of 9 (14-79%) | 1, 1, 13, 22 | 37 of 55 (53-79%) | 2 of 34 (1-20%) | 4.5 (3.9-5.2) | 4.1 (3.5-4.8) | 13.8 (10.4-17.9) |
| A-match | 9 / 4 | 3 of 9 (8-70%) | 3 of 9 (8-70%) | 1, 1, 8 | 41 of 55 (61-85%) | 2 of 34 (1-20%) | 3.4 (2.9-4.0) | 3.0 (2.5-3.6) | 11.0 (8.0-14.8) |

**without 25 March 2025**

| rule | run fire-days / fires | warned at the first run hour | warned >= 1 h ahead | lead times, h | run hours missed | alarm fire-days with no run | burden: alarm days per point and season | false-alarm days per point and season | days per season with an alarm at any of ten points |
|---|---|---|---|---|---|---|---|---|---|
| G | 8 / 4 | 3 of 8 (8-76%) | 2 of 8 (3-65%) | 0, 12, 21 | 31 of 42 (58-86%) | 0 of 34 (0-10%) | 3.7 (3.1-4.3) | 3.3 (2.8-3.9) | 11.8 (8.6-15.6) |
| A-cal | 8 / 4 | 7 of 8 (47-100%) | 7 of 8 (47-100%) | 5, 17, 22, 24, 24, 24, 24 | 10 of 42 (12-40%) | 19 of 34 (38-73%) | 55.1 (52.9-57.5) | 54.2 (52.0-56.6) | 73.8 (65.6-82.7) |
| A25 | 8 / 4 | 3 of 8 (8-76%) | 3 of 8 (8-76%) | 2, 14, 23 | 34 of 42 (66-91%) | 5 of 34 (5-31%) | 11.3 (10.3-12.4) | 10.7 (9.7-11.8) | 28.0 (23.1-33.7) |
| A30 | 8 / 4 | 2 of 8 (3-65%) | 2 of 8 (3-65%) | 1, 8 | 35 of 42 (69-93%) | 2 of 34 (1-20%) | 3.1 (2.6-3.7) | 2.8 (2.3-3.3) | 9.5 (6.7-13.0) |
| A+G | 8 / 4 | 7 of 8 (47-100%) | 7 of 8 (47-100%) | 5, 17, 22, 24, 24, 24, 24 | 10 of 42 (12-40%) | 19 of 34 (38-73%) | 55.1 (52.9-57.5) | 54.2 (52.0-56.6) | 73.8 (65.6-82.7) |
| A25+G | 8 / 4 | 3 of 8 (8-76%) | 3 of 8 (8-76%) | 2, 14, 23 | 31 of 42 (58-86%) | 5 of 34 (5-31%) | 11.6 (10.5-12.7) | 10.9 (9.9-12.0) | 28.2 (23.3-34.0) |
| A30+G | 8 / 4 | 3 of 8 (8-76%) | 3 of 8 (8-76%) | 1, 13, 22 | 31 of 42 (58-86%) | 2 of 34 (1-20%) | 4.5 (3.9-5.2) | 4.1 (3.5-4.8) | 13.8 (10.4-17.9) |
| A-match | 8 / 4 | 2 of 8 (3-65%) | 2 of 8 (3-65%) | 1, 8 | 35 of 42 (69-93%) | 2 of 34 (1-20%) | 3.4 (2.9-4.0) | 3.0 (2.5-3.6) | 11.0 (8.0-14.8) |

- A lead of 24 is the cap: the rule had been firing for at least 24 h.
- "Alarm fire-days with no run": A30 and A-match fired at Sancheong and Ulju on 25 March 2025, where neither fire
  ran. A25 fired on 5 such days (Sancheong 25 March; Ulju 24, 25 and 26 March; Uiseong 27 March). A-cal fired on
  19 of them, at 8 different fires.
- "False-alarm days" leave out the 41 burden point-days that had a fire-set run within 100 km. Fast fires outside
  the fire set are not known here, so their days are counted as false alarms.

## 3. Every run fire-day

Lead in hours; in brackets, the lead counted only from the fire's first issue hour. "no" = not firing at the first
run hour.

| fire | id | KST day | first run hour KST | run hours | G | A-cal | A25 | A30 | A-match | G-obs (PARTIAL) | run hours missed G / A-cal |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Uiseong | KFS_01 | 2025-03-22 | 22 | 2 | no | 24 h (3) | no | no | no | no | 2 / 0 |
| Uiseong | KFS_01 | 2025-03-23 | 00 | 9 | no | 24 h (5) | no | no | no | no | 9 / 5 |
| Uiseong | KFS_01 | 2025-03-25 | 10 | 13 | 1 h (1) | 8 h (8) | 2 h (2) | 1 h (1) | 1 h (1) | no | 6 / 0 |
| Uiseong | KFS_01 | 2025-03-26 | 00 | 5 | no | 22 h (22) | no | no | no | no | 5 / 0 |
| Uljin | KFS_02 | 2022-03-04 | 12 | 6 | 0 h (0) | 5 h (0) | 2 h (0) | 1 h (0) | 1 h (0) | NOT RUN | 0 / 0 |
| Uljin | KFS_02 | 2022-03-05 | 00 | 5 | 12 h (12) | 17 h (12) | 14 h (12) | 8 h (8) | 8 h (8) | NOT RUN | 4 / 0 |
| Uljin | KFS_02 | 2022-03-10 | 05 | 5 | no | no | no | no | no | NOT RUN | 5 / 5 |
| Gangneung | KFS_03 | 2022-03-05 | 08 | 5 | 21 h (6) | 24 h (6) | 23 h (6) | no | no | NOT RUN | 1 / 0 |
| Sancheong | KFS_04 | 2025-03-22 | 18 | 5 | no | 24 h (20) | no | no | no | NOT RUN | 5 / 0 |

- Uljin 4 March 2022 ran within an hour of ignition. G fired at the first run hour but not the hour before; every
  A rule had been firing for 1-5 h at that place before the fire existed.
- Uljin 10 March 2022: no rule fired. The forecast 850 hPa wind stayed below 15.2 m/s all day.

## 4. Verdicts (frozen wording), with and without 25 March, leave-one-fire-out

| rule | warned, rule vs G | without 25 March | leave-one-fire-out: rule minus G | warned by rule only / by G only (sign test) | more reliably | lead, rule minus G, h (days warned by both) | earlier |
|---|---|---|---|---|---|---|---|
| A-cal | 8 vs 4 of 9 | 7 vs 3 of 8 | +1 to +4 | 4 / 0 (p = 0.125) | A warned more run fire-days than G | +7, +5, +5, +3 | A earlier |
| A25 | 4 vs 4 of 9 | 3 vs 3 of 8 | +0 to +0 | 0 / 0 (p = 1.0) | no better | +1, +2, +2, +2 | A earlier |
| A30 | 3 vs 4 of 9 | 2 vs 3 of 8 | -1 to +0 | 0 / 1 (p = 1.0) | no better | +0, +1, -4 | mixed |
| A+G | 8 vs 4 of 9 | 7 vs 3 of 8 | +1 to +4 | 4 / 0 (p = 0.125) | A warned more run fire-days than G | +7, +5, +5, +3 | A earlier |
| A25+G | 4 vs 4 of 9 | 3 vs 3 of 8 | +0 to +0 | 0 / 0 (p = 1.0) | no better | +1, +2, +2, +2 | A earlier |
| A30+G | 4 vs 4 of 9 | 3 vs 3 of 8 | +0 to +0 | 0 / 0 (p = 1.0) | no better | +0, +1, +1, +1 | A earlier |
| A-match | 3 vs 4 of 9 | 2 vs 3 of 8 | -1 to +0 | 0 / 1 (p = 1.0) | no better | +0, +1, -4 | mixed |

| fire left out | run fire-days left | G | A-cal | A25 | A30 | A+G | A25+G | A30+G | A-match | alarm fire-days with no run, G / A-cal |
|---|---|---|---|---|---|---|---|---|---|---|
| KFS_01 | 5 | 3 | 4 | 3 | 2 | 4 | 3 | 3 | 2 | 0 / 17 of 32 |
| KFS_02 | 6 | 2 | 6 | 2 | 1 | 6 | 2 | 2 | 1 | 0 / 18 of 28 |
| KFS_03 | 8 | 3 | 7 | 3 | 3 | 7 | 3 | 3 | 3 | 0 / 18 of 32 |
| KFS_04 | 8 | 4 | 7 | 4 | 3 | 7 | 4 | 4 | 3 | 0 / 13 of 27 |
| KFS_05 | 9 | 4 | 8 | 4 | 3 | 8 | 4 | 4 | 3 | 0 / 19 of 32 |
| KFS_06 | 9 | 4 | 8 | 4 | 3 | 8 | 4 | 4 | 3 | 0 / 14 of 29 |
| KFS_07 | 9 | 4 | 8 | 4 | 3 | 8 | 4 | 4 | 3 | 0 / 17 of 32 |
| KFS_11 | 9 | 4 | 8 | 4 | 3 | 8 | 4 | 4 | 3 | 0 / 19 of 31 |
| KFS_12 | 9 | 4 | 8 | 4 | 3 | 8 | 4 | 4 | 3 | 0 / 18 of 33 |
| KFS_13 | 9 | 4 | 8 | 4 | 3 | 8 | 4 | 4 | 3 | 0 / 19 of 32 |
| KFS_15 | 9 | 4 | 8 | 4 | 3 | 8 | 4 | 4 | 3 | 0 / 19 of 33 |
| KFS_17 | 9 | 4 | 8 | 4 | 3 | 8 | 4 | 4 | 3 | 0 / 18 of 33 |

- The A-cal verdict ("warned more", "earlier") is robust in the frozen sense, and its cost is in section 2:
  15 times the alarm days of G.
- At equal cost (A-match) and at A30 the verdict is "no better". Leaving out Gangneung makes them equal to G
  (3 against 3); nothing makes them better.

## 5. Burden set, season by season

| rule | season | days evaluated | alarm point-days | mean alarm days per point | lowest point | highest point | days with an alarm at any point | false-alarm point-days |
|---|---|---|---|---|---|---|---|---|
| G | 2021 | 78 of 104 | 22 | 2.2 | Andong 0 | Yeongdeok 8 | 10 | 22 |
| G | 2022 | 104 of 104 | 46 | 4.6 | Andong 0 | Pohang 12 | 15 | 37 |
| G | 2023 | 104 of 104 | 26 | 2.6 | Andong 0 | Yeongdeok 6 | 7 | 26 |
| G | 2024 | 105 of 105 | 19 | 1.9 | Andong 0 | Pohang 4 | 7 | 19 |
| G | 2025 | 104 of 104 | 56 | 5.6 | Andong 1 | Pohang 13 | 18 | 50 |
| A-cal | 2021 | 78 of 104 | 389 | 38.9 | Wonju 32 | Yeongdeok 48 | 50 | 389 |
| A-cal | 2022 | 104 of 104 | 554 | 55.4 | Wonju 47 | Sokcho 65 | 77 | 541 |
| A-cal | 2023 | 104 of 104 | 472 | 47.2 | Wonju 41 | Sokcho 53 | 63 | 472 |
| A-cal | 2024 | 105 of 105 | 475 | 47.5 | Chuncheon 40 | Yeongdeok 57 | 67 | 475 |
| A-cal | 2025 | 104 of 104 | 705 | 70.5 | Chuncheon 65 | Pohang 75 | 88 | 681 |
| A25 | 2021 | 78 of 104 | 80 | 8.0 | Chuncheon 1 | Pohang 13 | 21 | 80 |
| A25 | 2022 | 104 of 104 | 111 | 11.1 | Chuncheon 3 | Pohang 22 | 26 | 100 |
| A25 | 2023 | 104 of 104 | 87 | 8.7 | Wonju 5 | Yeongdeok 15 | 17 | 87 |
| A25 | 2024 | 105 of 105 | 95 | 9.5 | Chuncheon 3 | Yeongdeok 18 | 27 | 95 |
| A25 | 2025 | 104 of 104 | 159 | 15.9 | Chuncheon 2 | Pohang 33 | 42 | 146 |
| A30 | 2021 | 78 of 104 | 25 | 2.5 | Chuncheon 0 | Yeongdeok 7 | 12 | 25 |
| A30 | 2022 | 104 of 104 | 26 | 2.6 | Andong 0 | Pohang 8 | 10 | 19 |
| A30 | 2023 | 104 of 104 | 28 | 2.8 | Chuncheon 0 | Pohang 6 | 8 | 28 |
| A30 | 2024 | 105 of 105 | 26 | 2.6 | Chuncheon 0 | Yeongdeok 6 | 8 | 26 |
| A30 | 2025 | 104 of 104 | 43 | 4.3 | Chuncheon 0 | Yeongdeok 9 | 12 | 37 |
| A+G | 2021 | 78 of 104 | 389 | 38.9 | Wonju 32 | Yeongdeok 48 | 50 | 389 |
| A+G | 2022 | 104 of 104 | 554 | 55.4 | Wonju 47 | Sokcho 65 | 77 | 541 |
| A+G | 2023 | 104 of 104 | 472 | 47.2 | Wonju 41 | Sokcho 53 | 63 | 472 |
| A+G | 2024 | 105 of 105 | 475 | 47.5 | Chuncheon 40 | Yeongdeok 57 | 67 | 475 |
| A+G | 2025 | 104 of 104 | 705 | 70.5 | Chuncheon 65 | Pohang 75 | 88 | 681 |
| A25+G | 2021 | 78 of 104 | 84 | 8.4 | Chuncheon 1 | Pohang 13 | 22 | 84 |
| A25+G | 2022 | 104 of 104 | 117 | 11.7 | Chuncheon 3 | Pohang 22 | 26 | 106 |
| A25+G | 2023 | 104 of 104 | 88 | 8.8 | Wonju 5 | Yeongdeok 15 | 17 | 88 |
| A25+G | 2024 | 105 of 105 | 95 | 9.5 | Chuncheon 3 | Yeongdeok 18 | 27 | 95 |
| A25+G | 2025 | 104 of 104 | 162 | 16.2 | Chuncheon 3 | Pohang 34 | 43 | 149 |
| A30+G | 2021 | 78 of 104 | 34 | 3.4 | Chuncheon 0 | Yeongdeok 11 | 14 | 34 |
| A30+G | 2022 | 104 of 104 | 50 | 5.0 | Andong 0 | Pohang 14 | 16 | 41 |
| A30+G | 2023 | 104 of 104 | 31 | 3.1 | Chuncheon 0 | Pohang 6 | 8 | 31 |
| A30+G | 2024 | 105 of 105 | 34 | 3.4 | Chuncheon 0 | Yeongdeok 8 | 11 | 34 |
| A30+G | 2025 | 104 of 104 | 65 | 6.5 | Chuncheon 1 | Pohang 14 | 20 | 59 |
| A-match | 2021 | 78 of 104 | 27 | 2.7 | Chuncheon 0 | Yeongdeok 9 | 12 | 27 |
| A-match | 2022 | 104 of 104 | 28 | 2.8 | Andong 0 | Pohang 9 | 11 | 20 |
| A-match | 2023 | 104 of 104 | 31 | 3.1 | Wonju 0 | Pohang 6 | 8 | 31 |
| A-match | 2024 | 105 of 105 | 28 | 2.8 | Chuncheon 0 | Yeongdeok 6 | 8 | 28 |
| A-match | 2025 | 104 of 104 | 49 | 4.9 | Chuncheon 0 | Yeongdeok 10 | 17 | 41 |

By point, alarm days per full season (mean):

| rule | Andong | Chuncheon | Gangneung | Pohang | Sangju | Sokcho | Taebaek | Uljin | Wonju | Yeongdeok |
|---|---|---|---|---|---|---|---|---|---|---|
| G | 0.2 | 0.2 | 5.2 | 8.5 | 1.2 | 3.5 | 4.0 | 5.5 | 0.2 | 8.0 |
| A-cal | 53.8 | 50.2 | 57.2 | 58.5 | 56.0 | 57.2 | 55.2 | 53.2 | 48.5 | 61.5 |
| A25 | 7.5 | 3.5 | 13.2 | 20.5 | 10.2 | 11.2 | 5.8 | 14.8 | 4.5 | 21.8 |
| A30 | 1.5 | 0.0 | 4.5 | 6.0 | 1.8 | 3.8 | 1.8 | 4.8 | 0.0 | 6.8 |
| A+G | 53.8 | 50.2 | 57.2 | 58.5 | 56.0 | 57.2 | 55.2 | 53.2 | 48.5 | 61.5 |
| A25+G | 7.5 | 3.8 | 13.8 | 20.8 | 10.2 | 11.8 | 6.8 | 14.8 | 4.5 | 21.8 |
| A30+G | 1.5 | 0.2 | 5.8 | 10.2 | 2.0 | 5.0 | 4.2 | 6.5 | 0.2 | 9.2 |
| A-match | 1.5 | 0.2 | 4.5 | 7.0 | 2.0 | 4.0 | 2.0 | 5.5 | 0.2 | 7.0 |

- G fires mostly on the east coast (Pohang, Yeongdeok, Uljin, Gangneung: 5-9 days a season) and on one day in four
  seasons at each of Andong, Chuncheon and Wonju. A30 has the same pattern. A-cal fires about equally everywhere.
- 2025 had the most alarm days under every rule.

## 6. Second model: ECMWF IFS (cross-check; enters no verdict)

Fires with IFS: KFS_01, KFS_04, KFS_05, KFS_06, KFS_07, KFS_13, KFS_17. Without: KFS_02, KFS_03, KFS_11, KFS_12, KFS_15. Issue hours 478, without IFS 0. IFS minus GFS at the same times: median -0.54 m/s, 5th-95th percentile -3.92 to 2.64, correlation 0.949.

| rule | source | warned | without 25 March | lead times, h | run hours missed | alarm fire-days with no run |
|---|---|---|---|---|---|---|
| A-cal | IFS | 5 of 5 (48-100%) | 4 of 4 (40-100%) | 6, 8, 20, 24, 24 | 8 of 34 (11-41%) | 15 of 21 (48-89%) |
| A-cal | GFS at the same 3-hourly times | 5 of 5 (48-100%) | 4 of 4 (40-100%) | 3, 8, 17, 24, 24 | 7 of 34 (9-38%) | 16 of 21 (53-92%) |
| A-cal | GFS hourly (primary) | 5 of 5 (48-100%) | 4 of 4 (40-100%) | 8, 22, 24, 24, 24 | 5 of 34 (5-31%) | 16 of 21 (53-92%) |
| A25 | IFS | 1 of 5 (0-72%) | 0 of 4 (0-60%) | 0 | 26 of 34 (59-89%) | 3 of 21 (3-36%) |
| A25 | GFS at the same 3-hourly times | 1 of 5 (0-72%) | 0 of 4 (0-60%) | 0 | 24 of 34 (52-85%) | 2 of 21 (1-30%) |
| A25 | GFS hourly (primary) | 1 of 5 (0-72%) | 0 of 4 (0-60%) | 2 | 24 of 34 (52-85%) | 5 of 21 (8-47%) |
| A30 | IFS | 0 of 5 (0-52%) | 0 of 4 (0-60%) | - | 34 of 34 (90-100%) | 0 of 21 (0-16%) |
| A30 | GFS at the same 3-hourly times | 0 of 5 (0-52%) | 0 of 4 (0-60%) | - | 34 of 34 (90-100%) | 1 of 21 (0-24%) |
| A30 | GFS hourly (primary) | 1 of 5 (0-72%) | 0 of 4 (0-60%) | 1 | 27 of 34 (62-91%) | 2 of 21 (1-30%) |

| rule | issue hours: both fire | IFS only | GFS hourly only | neither |
|---|---|---|---|---|
| A-cal | 228 | 14 | 47 | 189 |
| A25 | 30 | 1 | 27 | 420 |
| A30 | 0 | 0 | 21 | 457 |

Forecast gust >= 20 m/s at any step, fires KFS_01, KFS_04, KFS_06, KFS_13: IFS warned 1 of 5 (0-72%), GFS hourly (k = 1) 1 of 5 (0-72%); without 25 March 0 of 4 (0-60%) and 0 of 4 (0-60%).

| 25 March KST | IFS 10fg m/s | GFS gust m/s | IFS 850 hPa m/s | GFS 850 hPa m/s |
|---|---|---|---|---|
| 10 | 21.3 | 23.0 | 27.6 | 32.3 |
| 11 | 21.3 | 23.0 | 27.6 | 32.3 |
| 12 | 21.3 | 23.0 | 27.6 | 32.3 |
| 13 | 21.3 | 23.0 | 27.6 | 32.3 |
| 14 | 21.9 | 23.8 | 27.6 | 33.2 |
| 15 | 21.9 | 23.8 | 27.6 | 33.2 |
| 16 | 21.9 | 23.8 | 27.6 | 33.2 |

Burden: 3060 of 3130 point-days complete in all three readings; incomplete IFS point-days by season {'2023': 70, '2024': 0, '2025': 0}.

| rule | season | days | IFS: alarm days per point | GFS at the same times | GFS hourly |
|---|---|---|---|---|---|
| A-cal | 2023 | 97 | 38.2 | 39.9 | 43.1 |
| A-cal | 2024 | 105 | 43.6 | 45.3 | 47.5 |
| A-cal | 2025 | 104 | 66.2 | 67.7 | 70.5 |
| A25 | 2023 | 97 | 3.8 | 5.8 | 6.7 |
| A25 | 2024 | 105 | 7.4 | 7.9 | 9.5 |
| A25 | 2025 | 104 | 12.2 | 13.7 | 15.9 |
| A30 | 2023 | 97 | 1.1 | 1.4 | 1.8 |
| A30 | 2024 | 105 | 1.8 | 1.9 | 2.6 |
| A30 | 2025 | 104 | 2.0 | 3.6 | 4.3 |

| rule | point-days: both | IFS only | GFS hourly only | neither |
|---|---|---|---|---|
| A-cal | 1417 | 63 | 194 | 1386 |
| A25 | 191 | 43 | 130 | 2696 |
| A30 | 38 | 11 | 49 | 2962 |

- IFS reads the 850 hPa wind lower than GFS on the strongest days. With IFS, A30 warned no run fire-day of 2025
  and A25 warned 25 March only, with no lead.
- For the fires of 2022 (Uljin, Gangneung: 4 of the 9 run fire-days) no second issued model is reachable from this
  session: ECMWF open data start on 18 January 2023, and GEFS is the same model family as GFS.

## 7. 25 March 2025, hour by hour, and the observed gust

| KST | GFS cycle (UTC) | forecast gust, any hour m/s | gust held 2 h m/s | 850 hPa m/s | G | A-cal | A25 | A30 | G-obs | 5 h reach km | run hour |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 00 | 03-24 06 | 3.1 | 1.3 | 13.7 | no | no | no | no | no | 0.8 |  |
| 01 | 03-24 06 | 3.5 | 2.0 | 14.7 | no | no | no | no | no | 0.8 |  |
| 02 | 03-24 12 | 6.2 | 3.8 | 16.0 | no | **fires** | no | no | no | 0.8 |  |
| 03 | 03-24 12 | 9.9 | 6.2 | 16.7 | no | **fires** | no | no | no | 0.4 |  |
| 04 | 03-24 12 | 11.6 | 9.9 | 16.7 | no | **fires** | no | no | no | 0.0 |  |
| 05 | 03-24 12 | 12.3 | 11.6 | 16.7 | no | **fires** | no | no | no | 0.0 |  |
| 06 | 03-24 12 | 17.8 | 12.3 | 19.1 | no | **fires** | no | no | no | 0.0 |  |
| 07 | 03-24 12 | 19.5 | 17.8 | 23.0 | no | **fires** | no | no | no | 2.2 |  |
| 08 | 03-24 18 | 21.6 | 18.9 | 25.1 | no | **fires** | **fires** | no | no | 2.2 |  |
| 09 | 03-24 18 | 23.0 | 21.6 | 32.3 | **fires** | **fires** | **fires** | **fires** | no | 2.2 |  |
| 10 | 03-24 18 | 23.0 | 21.6 | 32.3 | **fires** | **fires** | **fires** | **fires** | no | 4.9 | yes |
| 11 | 03-24 18 | 23.0 | 21.6 | 32.3 | **fires** | **fires** | **fires** | **fires** | no | 6.6 | yes |
| 12 | 03-24 18 | 23.0 | 21.6 | 32.3 | **fires** | **fires** | **fires** | **fires** | no | 12.4 | yes |
| 13 | 03-24 18 | 23.0 | 21.6 | 32.3 | **fires** | **fires** | **fires** | **fires** | no | 23.9 | yes |
| 14 | 03-25 00 | 23.8 | 21.9 | 33.2 | **fires** | **fires** | **fires** | **fires** | no | 34.7 | yes |
| 15 | 03-25 00 | 23.8 | 21.9 | 33.2 | **fires** | **fires** | **fires** | **fires** | no | 32.9 | yes |
| 16 | 03-25 00 | 23.8 | 21.9 | 33.2 | **fires** | **fires** | **fires** | **fires** | no | 40.1 | yes |
| 17 | 03-25 00 | 21.9 | 16.7 | 28.1 | no | **fires** | **fires** | no | no | 38.6 | yes |
| 18 | 03-25 00 | 16.7 | 16.1 | 26.8 | no | **fires** | **fires** | no | no | 27.3 | yes |
| 19 | 03-25 00 | 16.1 | 14.7 | 26.8 | no | **fires** | **fires** | no | **fires** | 20.3 | yes |
| 20 | 03-25 06 | 14.1 | 13.9 | 24.8 | no | **fires** | no | no | no | 15.7 | yes |
| 21 | 03-25 06 | 14.1 | 13.9 | 23.4 | no | **fires** | no | no | no | 6.5 | yes |
| 22 | 03-25 06 | 14.1 | 13.9 | 23.4 | no | **fires** | no | no | no | 4.9 | yes |
| 23 | 03-25 06 | 14.1 | 13.9 | 23.4 | no | **fires** | no | no | no | - |  |

| rule | run fire-days | warned | without 25 March | warned, lapsed counted | run hours missed | alarm fire-days with no run | issue hours firing: run / no run | issue hours with no station data |
|---|---|---|---|---|---|---|---|---|
| G-obs, within 50km | 4 | 0 of 4 (0-60%) | 0 of 3 (0-71%) | 1 of 4 (1-81%) | 28 of 29 (82-100%) | 0 of 2 (0-84%) | 1 / 0 | 1 |
| G-obs, all four stations | 4 | 0 of 4 (0-60%) | 0 of 3 (0-71%) | 1 of 4 (1-81%) | 26 of 29 (73-98%) | 0 of 2 (0-84%) | 3 / 0 | 1 |
| G (same fire) | 4 | 1 of 4 (1-81%) | 0 of 3 (0-71%) | 2 of 4 (7-93%) | 22 of 29 (56-90%) | 0 of 2 (0-84%) |  |  |
| A-cal (same fire) | 4 | 4 of 4 (40-100%) | 3 of 3 (29-100%) | 4 of 4 (40-100%) | 5 of 29 (6-36%) | 2 of 2 (16-100%) |  |  |
| A25 (same fire) | 4 | 1 of 4 (1-81%) | 0 of 3 (0-71%) | 2 of 4 (7-93%) | 19 of 29 (46-82%) | 1 of 2 (1-99%) |  |  |
| A30 (same fire) | 4 | 1 of 4 (1-81%) | 0 of 3 (0-71%) | 2 of 4 (7-93%) | 22 of 29 (56-90%) | 0 of 2 (0-84%) |  |  |
| A+G (same fire) | 4 | 4 of 4 (40-100%) | 3 of 3 (29-100%) | 4 of 4 (40-100%) | 5 of 29 (6-36%) | 2 of 2 (16-100%) |  |  |
| A25+G (same fire) | 4 | 1 of 4 (1-81%) | 0 of 3 (0-71%) | 2 of 4 (7-93%) | 19 of 29 (46-82%) | 1 of 2 (1-99%) |  |  |
| A30+G (same fire) | 4 | 1 of 4 (1-81%) | 0 of 3 (0-71%) | 2 of 4 (7-93%) | 22 of 29 (56-90%) | 0 of 2 (0-84%) |  |  |
| A-match (same fire) | 4 | 1 of 4 (1-81%) | 0 of 3 (0-71%) | 2 of 4 (7-93%) | 22 of 29 (56-90%) | 0 of 2 (0-84%) |  |  |

- G-obs is PARTIAL: four KMA stations (Uiseong, Andong, Cheongsong, Yeongdeok), 22-26 March 2025, the only station
  gusts committed in the repo. It fired at one issue hour (19 KST on 25 March, after Cheongsong's 25 m/s at
  18:15). It warned none of Uiseong's four run fire-days.
- **G-obs is NOT RUN for every other fire and for the burden set.** The KMA key is not in this session, the KMA
  hosts are blocked by its network policy, and NOAA ISD and GSOD carry no gust for these stations (checked). Nothing
  was substituted.

## 8. Sensitivity (declared; changes no verdict)

| rule | warned | without 25 March | lead times, h | run hours missed | alarm fire-days with no run | burden: alarm days per point and season | days per season, any point |
|---|---|---|---|---|---|---|---|
| G k=1 | 4 of 9 (14-79%) | 3 of 8 (8-76%) | 1, 2, 13, 22 | 35 of 55 (50-76%) | 2 of 34 (1-20%) | 4.8 (4.1-5.5) | 15.8 (12.1-20.1) |
| G k=2 (primary) | 4 of 9 (14-79%) | 3 of 8 (8-76%) | 0, 1, 12, 21 | 37 of 55 (53-79%) | 0 of 34 (0-10%) | 3.7 (3.1-4.3) | 11.8 (8.6-15.6) |
| G k=3 | 3 of 9 (8-70%) | 2 of 8 (3-65%) | 0, 11, 20 | 40 of 55 (59-84%) | 0 of 34 (0-10%) | 2.8 (2.3-3.3) | 9.5 (6.7-13.0) |
| G k=4 | 2 of 9 (3-60%) | 2 of 8 (3-65%) | 9, 19 | 48 of 55 (76-95%) | 0 of 34 (0-10%) | 2.1 (1.7-2.6) | 7.2 (4.9-10.4) |
| G k=6 | 1 of 9 (0-48%) | 1 of 8 (0-53%) | 7 | 50 of 55 (80-97%) | 0 of 34 (0-10%) | 1.2 (0.9-1.6) | 4.8 (2.9-7.4) |
| G k=2 same point | 4 of 9 (14-79%) | 3 of 8 (8-76%) | 0, 1, 12, 21 | 37 of 55 (53-79%) | 0 of 34 (0-10%) | 3.7 (3.1-4.3) | 11.8 (8.6-15.6) |
| G k=2, 5 h window | 2 of 9 (3-60%) | 2 of 8 (3-65%) | 8, 17 | 41 of 55 (61-85%) | 0 of 34 (0-10%) | 3.2 (2.7-3.8) | 11.0 (8.0-14.8) |
| A-cal k=1 (primary) | 8 of 9 (52-100%) | 7 of 8 (47-100%) | 5, 8, 17, 22, 24, 24, 24, 24 | 10 of 55 (9-31%) | 19 of 34 (38-73%) | 55.1 (52.9-57.5) | 73.8 (65.6-82.7) |
| A-cal k=2 | 8 of 9 (52-100%) | 7 of 8 (47-100%) | 3, 7, 9, 15, 21, 24, 24, 24 | 11 of 55 (10-33%) | 19 of 34 (38-73%) | 52.2 (50.0-54.5) | 70.8 (62.8-79.5) |
| A-cal k=3 | 8 of 9 (52-100%) | 7 of 8 (47-100%) | 2, 2, 8, 14, 16, 24, 24, 24 | 12 of 55 (12-35%) | 18 of 34 (35-70%) | 49.0 (46.8-51.2) | 67.5 (59.7-76.0) |
| A25 k=1 (primary) | 4 of 9 (14-79%) | 3 of 8 (8-76%) | 2, 2, 14, 23 | 37 of 55 (53-79%) | 5 of 34 (5-31%) | 11.3 (10.3-12.4) | 28.0 (23.1-33.7) |
| A25 k=2 | 3 of 9 (8-70%) | 2 of 8 (3-65%) | 1, 1, 13 | 38 of 55 (55-81%) | 2 of 34 (1-20%) | 9.4 (8.4-10.4) | 25.0 (20.3-30.4) |
| A25 k=3 | 3 of 9 (8-70%) | 2 of 8 (3-65%) | 0, 0, 12 | 39 of 55 (57-82%) | 2 of 34 (1-20%) | 7.8 (6.9-8.7) | 22.5 (18.1-27.7) |
| A30 k=1 (primary) | 3 of 9 (8-70%) | 2 of 8 (3-65%) | 1, 1, 8 | 41 of 55 (61-85%) | 2 of 34 (1-20%) | 3.1 (2.6-3.7) | 9.5 (6.7-13.0) |
| A30 k=2 | 2 of 9 (3-60%) | 2 of 8 (3-65%) | 0, 7 | 48 of 55 (76-95%) | 1 of 34 (0-15%) | 2.5 (2.0-3.0) | 8.8 (6.1-12.2) |
| A30 k=3 | 1 of 9 (0-48%) | 1 of 8 (0-53%) | 6 | 49 of 55 (78-96%) | 0 of 34 (0-10%) | 1.8 (1.4-2.2) | 7.0 (4.7-10.1) |

Lapsed-warning variant (fired at any hour in the 12 h up to the first run hour):

| rule | warned (primary) | warned (lapsed counted) |
|---|---|---|
| G | 4 of 9 (14-79%) | 5 of 9 (21-86%) |
| A-cal | 8 of 9 (52-100%) | 8 of 9 (52-100%) |
| A25 | 4 of 9 (14-79%) | 5 of 9 (21-86%) |
| A30 | 3 of 9 (8-70%) | 5 of 9 (21-86%) |
| A+G | 8 of 9 (52-100%) | 8 of 9 (52-100%) |
| A25+G | 4 of 9 (14-79%) | 5 of 9 (21-86%) |
| A30+G | 4 of 9 (14-79%) | 5 of 9 (21-86%) |
| A-match | 3 of 9 (8-70%) | 5 of 9 (21-86%) |

- **Persistence.** With no persistence (k = 1, the wording in press reports of the rule), G warns the same 4 days
  and gains 1 h of lead on each, for 4.8 alarm days per point and season instead of 3.7 and 2 alarm fire-days
  without a run. Requiring 3, 4 or 6 consecutive hours loses run days (3, 2 and 1 of 9).
- **Window.** G at the same lattice point is identical to G. G on a 5 h window warns only 2 of 9: the look-ahead to
  8 h is what gives G its two short-lead warnings (25 March 2025 and Uljin 4 March 2022).
- **Persistence for A.** Requiring two consecutive hours drops A25 to 3 of 9 and A30 to 2 of 9.

**Threshold sweep (descriptive, post hoc reading; 9 run fire-days from 4 fires).**

**forecast gust, two consecutive hours (k = 2)**

| threshold m/s | warned of run fire-days | without 25 March | run hours missed | alarm fire-days with no run | burden: alarm days per point and season | burden point-days |
|---|---|---|---|---|---|---|
| 10 | 6 of 9 | 5 | 22 of 55 | 17 of 34 | 54.27 | 2599 |
| 12 | 5 of 9 | 4 | 23 of 55 | 15 of 34 | 39.08 | 1862 |
| 14 | 4 of 9 | 3 | 29 of 55 | 10 of 34 | 25.77 | 1216 |
| 15 | 4 of 9 | 3 | 30 of 55 | 8 of 34 | 20.9 | 986 |
| 16 | 4 of 9 | 3 | 30 of 55 | 6 of 34 | 15.85 | 740 |
| 18 | 4 of 9 | 3 | 32 of 55 | 2 of 34 | 8.07 | 387 |
| 20 | 4 of 9 | 3 | 37 of 55 | 0 of 34 | 3.67 | 169 |
| 22 | 1 of 9 | 1 | 50 of 55 | 0 of 34 | 1.35 | 65 |
| 24 | 0 of 9 | 0 | 51 of 55 | 0 of 34 | 0.47 | 21 |
| 25 | 0 of 9 | 0 | 51 of 55 | 0 of 34 | 0.38 | 17 |
| 26 | 0 of 9 | 0 | 55 of 55 | 0 of 34 | 0.25 | 12 |
| 28 | 0 of 9 | 0 | 55 of 55 | 0 of 34 | 0.15 | 6 |
| 30 | 0 of 9 | 0 | 55 of 55 | 0 of 34 | 0.12 | 5 |

**forecast gust, any hour (k = 1)**

| threshold m/s | warned of run fire-days | without 25 March | run hours missed | alarm fire-days with no run | burden: alarm days per point and season | burden point-days |
|---|---|---|---|---|---|---|
| 10 | 6 of 9 | 5 | 18 of 55 | 17 of 34 | 59.35 | 2834 |
| 12 | 6 of 9 | 5 | 21 of 55 | 16 of 34 | 42.9 | 2060 |
| 14 | 5 of 9 | 4 | 24 of 55 | 13 of 34 | 29.6 | 1409 |
| 15 | 4 of 9 | 3 | 28 of 55 | 11 of 34 | 23.9 | 1131 |
| 16 | 4 of 9 | 3 | 29 of 55 | 8 of 34 | 18.98 | 892 |
| 18 | 4 of 9 | 3 | 31 of 55 | 3 of 34 | 10.12 | 478 |
| 20 | 4 of 9 | 3 | 35 of 55 | 2 of 34 | 4.78 | 225 |
| 22 | 2 of 9 | 1 | 42 of 55 | 0 of 34 | 2.15 | 100 |
| 24 | 1 of 9 | 1 | 50 of 55 | 0 of 34 | 0.72 | 31 |
| 25 | 1 of 9 | 1 | 50 of 55 | 0 of 34 | 0.53 | 23 |
| 26 | 0 of 9 | 0 | 55 of 55 | 0 of 34 | 0.4 | 18 |
| 28 | 0 of 9 | 0 | 55 of 55 | 0 of 34 | 0.2 | 9 |
| 30 | 0 of 9 | 0 | 55 of 55 | 0 of 34 | 0.12 | 5 |

**forecast 850 hPa wind, any hour**

| threshold m/s | warned of run fire-days | without 25 March | run hours missed | alarm fire-days with no run | burden: alarm days per point and season | burden point-days |
|---|---|---|---|---|---|---|
| 10 | 8 of 9 | 7 | 6 of 55 | 30 of 34 | 81.75 | 3893 |
| 12 | 8 of 9 | 7 | 10 of 55 | 22 of 34 | 70.92 | 3381 |
| 14 | 8 of 9 | 7 | 10 of 55 | 20 of 34 | 61.23 | 2892 |
| 15 | 8 of 9 | 7 | 10 of 55 | 19 of 34 | 55.98 | 2635 |
| 16 | 8 of 9 | 7 | 10 of 55 | 17 of 34 | 50.9 | 2383 |
| 18 | 8 of 9 | 7 | 11 of 55 | 16 of 34 | 40.8 | 1898 |
| 20 | 6 of 9 | 5 | 22 of 55 | 13 of 34 | 31.7 | 1480 |
| 22 | 5 of 9 | 4 | 25 of 55 | 10 of 34 | 22.12 | 1042 |
| 24 | 4 of 9 | 3 | 32 of 55 | 5 of 34 | 14.35 | 684 |
| 25 | 4 of 9 | 3 | 37 of 55 | 5 of 34 | 11.3 | 532 |
| 26 | 4 of 9 | 3 | 37 of 55 | 5 of 34 | 9.28 | 436 |
| 28 | 3 of 9 | 2 | 40 of 55 | 2 of 34 | 5.45 | 263 |
| 30 | 3 of 9 | 2 | 41 of 55 | 2 of 34 | 3.08 | 148 |
| 32 | 2 of 9 | 1 | 43 of 55 | 0 of 34 | 1.57 | 72 |
| 34 | 0 of 9 | 0 | 55 of 55 | 0 of 34 | 0.8 | 34 |
| 36 | 0 of 9 | 0 | 55 of 55 | 0 of 34 | 0.42 | 17 |
| 38 | 0 of 9 | 0 | 55 of 55 | 0 of 34 | 0.07 | 3 |
| 40 | 0 of 9 | 0 | 55 of 55 | 0 of 34 | 0.03 | 1 |

- At the low-alarm end, gust is at least as good as wind aloft: 4 of 9 costs 3.7 days with gust (20 m/s, 2 h) and
  9.3 days or more with the 850 hPa wind (26 m/s or lower).
- At the high-alarm end the order reverses: the 850 hPa wind reaches 8 of 9 at 18 m/s for 41 alarm days per point
  and season, where no gust threshold from 10 m/s up reaches more than 6 of 9. An alarm on 40 days of a 104-day
  season is not a trigger, and this is a reading of a sweep, not a tested rule.

## 9. Height of 850 hPa against the ridges

| place | id | highest ground within 10 km | within 25 km | 850 hPa height, median (range) | 850 hPa above the 10 km ridge | above the 25 km ridge | smallest gap, 25 km | GFS model terrain at the 4 points |
|---|---|---|---|---|---|---|---|---|
| Uiseong | KFS_01 | 782 | 925 | 1403 (1358-1460) | 621 | 478 | 433 | 146-262 |
| Uljin | KFS_02 | 1044 | 1259 | 1459 (1354-1506) | 415 | 200 | 95 | 0-458 |
| Gangneung | KFS_03 | 1023 | 1406 | 1439 (1351-1459) | 416 | 33 | -55 | 1-449 |
| Sancheong | KFS_04 | 1496 | 1898 | 1420 (1370-1472) | -76 | -478 | -528 | 155-551 |
| Hongseong | KFS_05 | 361 | 781 | 1541 (1518-1549) | 1180 | 760 | 737 | 30-128 |
| Ulju | KFS_06 | 785 | 1152 | 1423 (1376-1470) | 638 | 271 | 224 | 0-156 |
| Geumsan | KFS_07 | 645 | 891 | 1523 (1515-1541) | 878 | 632 | 624 | 133-343 |
| Miryang | KFS_11 | 922 | 1224 | 1451 (1435-1463) | 529 | 227 | 211 | 134-230 |
| Yeongdeok | KFS_12 | 572 | 929 | 1400 (1400-1404) | 828 | 471 | 471 | 0-380 |
| Buk-gu | KFS_13 | 651 | 1180 | 1484 (1436-1504) | 833 | 304 | 256 | 178-270 |
| Gunwi | KFS_15 | 875 | 1180 | 1501 (1500-1504) | 626 | 321 | 320 | 207-443 |
| Hapcheon | KFS_17 | 1121 | 1410 | 1481 (1475-1496) | 360 | 71 | 65 | 160-498 |
| Sokcho | burden point | 939 | 1701 | 1466 (1266-1588) | 527 | -235 | -435 | 0-316 |
| Gangneung | burden point | 863 | 1451 | 1468 (1272-1589) | 606 | 18 | -179 | 1-551 |
| Taebaek | burden point | 1565 | 1565 | 1472 (1293-1590) | -93 | -93 | -272 | 568-757 |
| Chuncheon | burden point | 891 | 1460 | 1471 (1285-1588) | 580 | 11 | -175 | 245-484 |
| Wonju | burden point | 1019 | 1258 | 1473 (1289-1589) | 454 | 215 | 31 | 160-436 |
| Uljin | burden point | 431 | 1165 | 1472 (1290-1591) | 1041 | 307 | 125 | 0-458 |
| Yeongdeok | burden point | 566 | 987 | 1474 (1294-1592) | 908 | 487 | 307 | 6-464 |
| Pohang | burden point | 335 | 866 | 1478 (1297-1592) | 1142 | 612 | 431 | 0-380 |
| Andong | burden point | 552 | 859 | 1475 (1293-1591) | 923 | 616 | 434 | 163-283 |
| Sangju | burden point | 783 | 881 | 1478 (1292-1590) | 695 | 597 | 411 | 121-311 |

- 850 hPa sat at about 1,400-1,540 m. That is 400-620 m above the highest ground within 10 km of the Uiseong,
  Uljin and Gangneung fires, and **below** the Jirisan ridge at Sancheong (1,496 m within 10 km, 1,898 m within
  25 km). Near Gangneung and Sokcho the main Taebaek ridge within 25 km reaches or exceeds it.
- So the 850 hPa wind is the free-air wind several hundred metres above the ridge line of the east-coast fires,
  not the wind at the fire. GFS's own terrain at these lattice points is 0-760 m, far below the real ridges.

## 10. Seasons 2019 and 2020 (S5, COARSE; not pooled, no verdict)

The as-issued GFS 0.25 deg archive reachable here starts in 2021, so the frozen rules cannot be read for 2019 and
2020. The substitute is the operational GEFS control as issued (1 deg, lead times 6, 12, 18 h), a coarser run of an
older model version, with the any-time gust form only.

Point-days 2090; wind complete 2090; gust complete 2070.

| rule (coarse) | season | days | alarm point-days | alarm days per point | days with an alarm at any point |
|---|---|---|---|---|---|
| A-cal | 2019 | 104 | 432 | 43.2 | 57 |
| A-cal | 2020 | 105 | 605 | 60.5 | 72 |
| A25 | 2019 | 104 | 45 | 4.5 | 7 |
| A25 | 2020 | 105 | 97 | 9.7 | 18 |
| A30 | 2019 | 104 | 1 | 0.1 | 1 |
| A30 | 2020 | 105 | 23 | 2.3 | 4 |
| G k=1 (any time) | 2019 | 102 | 15 | 1.5 | 4 |
| G k=1 (any time) | 2020 | 105 | 83 | 8.3 | 17 |

Bridge: GFS 2021-2025 on the same 4950 point-days, coarse sampling against full resolution (alarm days per point):

| rule | season | days | coarse sampling | full resolution (hourly, 0.25 deg) |
|---|---|---|---|---|
| A-cal | 2021 | 78 | 36.8 | 38.9 |
| A-cal | 2022 | 104 | 50.5 | 55.4 |
| A-cal | 2023 | 104 | 44.9 | 47.2 |
| A-cal | 2024 | 105 | 45.0 | 47.5 |
| A-cal | 2025 | 104 | 68.0 | 70.5 |
| A25 | 2021 | 78 | 5.7 | 8.0 |
| A25 | 2022 | 104 | 6.9 | 11.1 |
| A25 | 2023 | 104 | 6.4 | 8.7 |
| A25 | 2024 | 105 | 6.7 | 9.5 |
| A25 | 2025 | 104 | 9.6 | 15.9 |
| A30 | 2021 | 78 | 1.7 | 2.5 |
| A30 | 2022 | 104 | 0.0 | 2.6 |
| A30 | 2023 | 104 | 1.0 | 2.8 |
| A30 | 2024 | 105 | 1.8 | 2.6 |
| A30 | 2025 | 104 | 2.0 | 4.3 |
| G k=1 (any time) | 2021 | 78 | 2.8 | 3.4 |
| G k=1 (any time) | 2022 | 104 | 4.4 | 5.2 |
| G k=1 (any time) | 2023 | 104 | 2.1 | 3.4 |
| G k=1 (any time) | 2024 | 105 | 4.8 | 3.1 |
| G k=1 (any time) | 2025 | 104 | 5.6 | 7.4 |

- The bridge shows that the coarse sampling reads lower than the full-resolution rule at 25 and 30 m/s (for example
  6.9 against 11.1 days in 2022 at A25), so the 2019-2020 counts are likely low for those two.
- A-cal fires on 39-71 days per point and season in 2021-2025 (2021 from 27 February) and, in the coarse reading,
  on 43 and 61 days in 2019 and 2020.

## 11. Other secondary analyses

| variant | rule | run fire-days | warned | without 25 March | lead times, h | run hours missed | alarm fire-days with no run |
|---|---|---|---|---|---|---|---|
| S1 KFS_01 from the Choi raster on every day | G | 9 | 3 of 9 (8-70%) | 3 of 8 (8-76%) | 0, 12, 21 | 41 of 53 (64-88%) | 0 of 34 (0-10%) |
| S1 KFS_01 from the Choi raster on every day | A-cal | 9 | 7 of 9 (40-97%) | 7 of 8 (47-100%) | 5, 17, 22, 24, 24, 24, 24 | 11 of 53 (11-34%) | 19 of 34 (38-73%) |
| S1 KFS_01 from the Choi raster on every day | A25 | 9 | 3 of 9 (8-70%) | 3 of 8 (8-76%) | 2, 14, 23 | 42 of 53 (66-89%) | 5 of 34 (5-31%) |
| S1 KFS_01 from the Choi raster on every day | A30 | 9 | 2 of 9 (3-60%) | 2 of 8 (3-65%) | 1, 8 | 45 of 53 (72-93%) | 2 of 34 (1-20%) |
| S1 KFS_01 from the Choi raster on every day | A+G | 9 | 7 of 9 (40-97%) | 7 of 8 (47-100%) | 5, 17, 22, 24, 24, 24, 24 | 11 of 53 (11-34%) | 19 of 34 (38-73%) |
| S1 KFS_01 from the Choi raster on every day | A25+G | 9 | 3 of 9 (8-70%) | 3 of 8 (8-76%) | 2, 14, 23 | 39 of 53 (60-85%) | 5 of 34 (5-31%) |
| S1 KFS_01 from the Choi raster on every day | A30+G | 9 | 3 of 9 (8-70%) | 3 of 8 (8-76%) | 1, 13, 22 | 41 of 53 (64-88%) | 2 of 34 (1-20%) |
| S1 KFS_01 from the Choi raster on every day | A-match | 9 | 2 of 9 (3-60%) | 2 of 8 (3-65%) | 1, 8 | 45 of 53 (72-93%) | 2 of 34 (1-20%) |
| S6 kcf-abstain's scored hours only | G | 9 | 4 of 9 (14-79%) | 3 of 8 (8-76%) | 1, 8, 12, 21 | 37 of 53 (56-82%) | 0 of 33 (0-11%) |
| S6 kcf-abstain's scored hours only | A-cal | 9 | 8 of 9 (52-100%) | 7 of 8 (47-100%) | 8, 13, 17, 22, 24, 24, 24, 24 | 10 of 53 (9-32%) | 18 of 33 (36-72%) |
| S6 kcf-abstain's scored hours only | A25 | 9 | 4 of 9 (14-79%) | 3 of 8 (8-76%) | 2, 10, 14, 23 | 37 of 53 (56-82%) | 5 of 33 (5-32%) |
| S6 kcf-abstain's scored hours only | A30 | 9 | 3 of 9 (8-70%) | 2 of 8 (3-65%) | 1, 4, 8 | 41 of 53 (64-88%) | 2 of 33 (1-20%) |
| S6 kcf-abstain's scored hours only | A+G | 9 | 8 of 9 (52-100%) | 7 of 8 (47-100%) | 8, 13, 17, 22, 24, 24, 24, 24 | 10 of 53 (9-32%) | 18 of 33 (36-72%) |
| S6 kcf-abstain's scored hours only | A25+G | 9 | 4 of 9 (14-79%) | 3 of 8 (8-76%) | 2, 10, 14, 23 | 34 of 53 (50-77%) | 5 of 33 (5-32%) |
| S6 kcf-abstain's scored hours only | A30+G | 9 | 4 of 9 (14-79%) | 3 of 8 (8-76%) | 1, 9, 13, 22 | 37 of 53 (56-82%) | 2 of 33 (1-20%) |
| S6 kcf-abstain's scored hours only | A-match | 9 | 3 of 9 (8-70%) | 2 of 8 (3-65%) | 1, 4, 8 | 41 of 53 (64-88%) | 2 of 33 (1-20%) |

S4 pooled issue hours (counts):

| rule | fires and run hour | fires, no run | silent and run hour | silent, no run |
|---|---|---|---|---|
| G | 18 | 20 | 37 | 716 |
| A-cal | 45 | 306 | 10 | 430 |
| A25 | 18 | 66 | 37 | 670 |
| A30 | 14 | 28 | 41 | 708 |
| A+G | 45 | 306 | 10 | 430 |
| A25+G | 21 | 66 | 34 | 670 |
| A30+G | 18 | 33 | 37 | 703 |
| A-match | 14 | 33 | 41 | 703 |

- S1: with the Choi raster on 25 March, Uiseong's first run hour that day is 01 KST instead of 10 KST, before the
  gust forecast reached 20 m/s, so G warns 3 of 9 instead of 4.
- S6: counting only the hours kcf-abstain scored changes some lead times and no count of warned days.

## What this does not show

- **Not a rate, and not a general result.** 9 run fire-days from 4 fires, in two weather episodes (4-5 March 2022,
  22-26 March 2025) plus one day. Days of one fire are not independent.
- **Not the official rule as applied.** The official text was not read; "persist" is my definition. Officials use
  KMA forecasts and KMA stations, not GFS. GFS gust is a model diagnostic on a 0.25 deg grid.
- **Not the observed-gust rule.** G-obs ran on one fire with four stations.
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

- G-obs beyond KFS_01 (no KMA key or host in this session).
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
- **Station gusts.** `research/kcf-gust/work/kma_asos_hourly.json` (KMA ASOS hourly, four stations, 22-26 March
  2025), with kcf-gust's amendment-3 conventions.
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
`noaa-gefs-pds`, `ecmwf-forecasts` and `elevation-tiles-prod`. The forecast extracts (about 80 GB of GRIB byte
ranges read, 0.3 GB kept) stay outside git.
