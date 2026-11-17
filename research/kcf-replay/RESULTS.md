# KCF replay, 25 March 2025, 12:00 to 24:00 KST: what the screen would have shown

**Headline.** Using only satellite fire detections time-stamped before each hour, the screen would have placed 142 of
the 174 planner places in the 5-hour "leave now" step at 12:00 KST and all 174 from 17:00 KST under the running-fire
stand-in (8.2 km/h), and in 108 of the 1,093 place-hours where it showed a latest safe departure the reconstructed fire
reached the route shown before that time.

This is a reconstruction of what a screen would have shown. It is not a claim about outcomes. It does not judge
anyone's decisions, and it names no victims. Every number below depends on a stand-in for R(h) (see 2). The frozen
R(h) from `research/kcf-margin` has since landed (PR 179) and is added as two further arms, MEASURED and MEASURED+GUST (2b). The
three stand-ins are unchanged. **The MEASURED+GUST arm is PROVISIONAL: its gust series is ERA5 only (KMA gave no hourly gust series),
and its gust >= 20 m/s class rests on 9 fires. KMA data.go.kr gave only daily maxima and hourly mean wind, no hourly gust, so no KMA series could drive the class (see research/kcf-gust/RESULTS.md).**

## 1 What fills the gap

The planner's Yeongdeok replay starts at 2025-03-25 19:00 UTC (04:00 KST on the 26th). This replay adds 13 issue times,
2025-03-25 03:00 to 15:00 UTC (12:00 to 24:00 KST), for all **174** checkable planner places: 90 in 영덕 (plus
neighbouring 영양 and 청송 villages in the same planner region) and 84 in 의성·안동, including 5 care facilities. For each
place, issue time, stand-in and horizon (5 h, 8 h) it gives:

* the government step;
* the latest safe departure;
* the shelter;
* the witness road (OSM way ids).

All of it comes from data time-stamped before the issue hour.

The rule was frozen before any outcome was computed, in [HOTSPOT_RULE.md](HOTSPOT_RULE.md), commit `796e91c`; the
rest of this directory came later. In outline:

* **Known fire area** = FIRMS VIIRS and MODIS detections plus Himawari-9 AHI hotspots so far.
  * AHI hotspot rule: B07 and B07−B14 each at least 10 K above the pixel's pre-ignition maximum for the same UTC hour,
    in two consecutive 2.5-min scans.
  * Each AHI hotspot is treated as "fire within 2 km".
* **Closure** of a road cell = issue time + distance / R.
* **Government step:** R(5 h) ≥ distance → 위험구역 (5 h), read here as "leave now". R(8 h) ≥ distance → 잠재적
  위험구역 (8 h), vulnerable people first.
* **Latest safe departure** comes from the F-3.1 deadline field (`deadline_field.core.backward`, one exact backward
  pass per shelter) over the planner's road graph, with the planner's own 3 candidate shelters per place.
  * The shelter sets reproduce the cached planner requests for 174 of 174 places.

## 2 R(h) stand-ins (labelled; not the frozen R(h))

| label | R(h) | basis |
|---|---|---|
| ORDINARY | 0.341 km/h × h | PT-FireSprd median (the repo's reference spread rate) |
| RUNNING | 8.2 km/h × h | peak-period rate reported for this fire (Ajunews 2025-03-27, unnamed 산림 당국 official; YTN 2025-03-28, own satellite analysis). Not a named 산림청/국립산림과학원 release |
| WORST | 3 km + 8.2 km/h × h | RUNNING plus a 3 km spotting allowance (노컷뉴스 2025-10-02; 뉴스서울 says 2 km) |

## 2b MEASURED arms (added 2026-11-17; rule frozen first in [MEASURED_RULE.md](MEASURED_RULE.md), commit a4ff4f1c)

Same hotspot rule, 174 places, 13 issue hours, two horizons and score; only R(h) differs. R in km beyond the known fire area, 10% target,
28 GOFER fires, `research/kcf-margin/numbers.json`; closure curve linear through (0, 0), (5 h, R5), (8 h, R8) (the part below 5 h ASSUMED).

| label | R(5 h), R(8 h) km | class picked at each issue hour |
|---|---|---|
| MEASURED | quiet 2.6 / 3.5, slow 5.0 / 6.4, running 7.6 / 10.0 | prior-3 h spread of the known fire area: quiet 12-14 KST, slow 15, running 16-24 KST |
| MEASURED+GUST (**PROVISIONAL**, ERA5 only) | gust < 10: 2.6 / 3.0, 10-20: 4.7 / 5.9, **>= 20: 8.6 / 12.0 (9 fires)** | max gust over (T, T+H] at five points: >= 20 m/s (9 fires) at 12-22 KST, 10-20 m/s at 23-24 KST, for both horizons |

Both arms use one class per issue hour for all 174 places. Gust series and fetch times: `research/kcf-gust/RESULTS.md`.

## 3 Government step per issue hour (174 places, 8 h horizon; leave now / vulnerable first / none)

MEASURED+GUST is PROVISIONAL (ERA5 only); its >= 20 m/s class (12-22 KST) rests on 9 fires.

| issue KST | ORDINARY | RUNNING | WORST | MEASURED | MEASURED+GUST (PROVISIONAL) |
|---|---|---|---|---|---|
| 12:00 | 43 / 3 / 128 | 142 / 32 / 0 | 156 / 18 / 0 | 45 / 4 / 125 | 69 / 12 / 93 |
| 13:00 | 45 / 4 / 125 | 142 / 32 / 0 | 157 / 17 / 0 | 48 / 4 / 122 | 74 / 9 / 91 |
| 14:00 | 45 / 4 / 125 | 142 / 32 / 0 | 157 / 17 / 0 | 48 / 4 / 122 | 74 / 9 / 91 |
| 15:00 | 49 / 4 / 121 | 154 / 20 / 0 | 166 / 8 / 0 | 64 / 6 / 104 | 78 / 6 / 90 |
| 16:00 | 62 / 1 / 111 | 154 / 20 / 0 | 167 / 7 / 0 | 81 / 3 / 90 | 83 / 1 / 90 |
| 17:00 | 83 / 1 / 90 | 174 / 0 / 0 | 174 / 0 / 0 | 84 / 0 / 90 | 84 / 3 / 87 |
| 18:00 | 86 / 3 / 85 | 174 / 0 / 0 | 174 / 0 / 0 | 99 / 7 / 68 | 103 / 14 / 57 |
| 19:00 | 103 / 2 / 69 | 174 / 0 / 0 | 174 / 0 / 0 | 122 / 16 / 36 | 128 / 19 / 27 |
| 20:00 | 106 / 2 / 66 | 174 / 0 / 0 | 174 / 0 / 0 | 130 / 13 / 31 | 135 / 22 / 17 |
| 21:00 | 133 / 5 / 36 | 174 / 0 / 0 | 174 / 0 / 0 | 174 / 0 / 0 | 174 / 0 / 0 |
| 22:00 | 157 / 7 / 10 | 174 / 0 / 0 | 174 / 0 / 0 | 174 / 0 / 0 | 174 / 0 / 0 |
| 23:00 | 157 / 7 / 10 | 174 / 0 / 0 | 174 / 0 / 0 | 174 / 0 / 0 | 170 / 2 / 2 |
| 24:00 | 162 / 3 / 9 | 174 / 0 / 0 | 174 / 0 / 0 | 174 / 0 / 0 | 170 / 2 / 2 |

Of the 2,262 place-hours per configuration, 1,077 are inside the known fire area at the issue hour (distance 0, no
departure computed). These are mostly 의성·안동 places inside detections accumulated since 22 March.

## 4 Timeline: six named places

Files: [timeline.png](timeline.png) (all three stand-ins plus MEASURED and MEASURED+GUST, 8 h; the gust lane is labelled PROVISIONAL) and [named_places_timeline.csv](named_places_timeline.csv)
(every hour, stand-in and horizon, with the shelter). All documented times were re-read at their source on 2026-11-16
([SOURCES.md](SOURCES.md)). **Every one is single-source.**

Latest safe departure shown at each issue hour, RUNNING, 8 h (KST):

| place | 16:00 | 17:00 | 18:00 | 19:00 | 20:00 | 21:00 | documented |
|---|---|---|---|---|---|---|---|
| 화매리 (영양 석보면) | 18:47 | 18:38 | 18:25 | inside | inside | inside | ~18:00 이장 voice message; ~18:00 flames at the village edge (매일신문) |
| 지품리 (영덕 지품면) | 18:33 | 18:18 | 18:03 | inside | inside | inside | 18:00 지품면 order and CBS; 18:25 황장재 restriction CBS; 18:58 Route 34 (구미~황장) closed; 19:04 도계→영양 road closed; 20:25 power cut (뉴스로). No documented fire-arrival time |
| 옥류리 (영덕 지품면) | 19:58 | 19:41 | 19:24 | 19:19 | 20:07 | inside | 18:00 지품면 order; 18:52 옥류리 CBS (뉴스로). No documented fire-arrival time |
| 매정리 (영덕읍) | 21:10 | 20:53 | 20:36 | 20:37 | 21:21 | 21:17 | 19:30 order for all 9 읍·면; 21:00 county CBS (뉴스로); ~20:40 fire in the village, one resident's account (한국일보) |
| 노물리 (영덕읍) | 21:19 | 21:02 | 20:46 | 20:46 | 21:30 | 21:26 | 19:30, 21:00 (뉴스로); residents aware ~24:00 (대구신문) |
| 강구리 (강구면) | 20:44 | 20:32 | 20:25 | 20:42 | 21:29 | 21:37 | 21:58 Route 7 controlled at 송라 지경삼거리 (뉴스로); 00:07 text, fire ~00:37, 00:41 second text (경향신문, 면-level) |

MEASURED, 8 h (KST; "not cut" = no route cut inside the horizon; MEASURED+GUST is PROVISIONAL, ERA5 only, >= 20 m/s class = 9 fires):

| place | 16:00 | 17:00 | 18:00 | 19:00 | 20:00 | 21:00 |
|---|---|---|---|---|---|---|
| 화매리 | not cut | not cut | 20:27 | inside | inside | inside |
| 지품리 | not cut | not cut | 18:19 | inside | inside | inside |
| 옥류리 | not cut | not cut | not cut | 20:54 | 20:51 | inside |
| 매정리 | not cut | not cut | not cut | not cut | not cut | 22:50 |
| 노물리 | not cut | not cut | not cut | not cut | not cut | 23:36 |
| 강구리 | not cut | not cut | not cut | not cut | not cut | 00:26 |

MEASURED+GUST (PROVISIONAL), 8 h:

| place | 16:00 | 17:00 | 18:00 | 19:00 | 20:00 | 21:00 |
|---|---|---|---|---|---|---|
| 화매리 | not cut | not cut | 20:10 | inside | inside | inside |
| 지품리 | not cut | 23:51 | 18:16 | inside | inside | inside |
| 옥류리 | not cut | not cut | 01:46 | 20:41 | 20:45 | inside |
| 매정리 | not cut | not cut | not cut | not cut | 03:27 | 22:37 |
| 노물리 | not cut | not cut | not cut | not cut | not cut | 23:17 |
| 강구리 | not cut | not cut | not cut | not cut | not cut | 00:02 |

First leave-now step: RUNNING 12:00 (화매리, 지품리, 옥류리), 15:00 (강구리), 17:00 (매정리, 노물리); MEASURED and MEASURED+GUST 18:00 (화매리, 지품리), 19:00 (옥류리), 21:00 (매정리, 노물리, 강구리).
Under RUNNING, all six places are in the leave-now step from 17:00 KST. Before that, 매정리 and 노물리 are in the
vulnerable-first step until 17:00 and 강구리 until 15:00. Under ORDINARY, none of the six has a step before 18:00, except where the place is
already inside the known fire area.

UNVERIFIED, kept and not used: the 문화일보 column ("texts only at 9 pm", page refused the fetch) and 경정리 "~20:00
over the ridge" (no URL recorded).

## 5 Score (count only)

For each place-hour with a latest safe departure cut within the horizon, the question is whether the reconstructed fire
(all detections, including those after the issue hour) reached a cell of the witness route before that departure time.

| stand-in / horizon | place-hours with a latest safe departure | route reached earlier | places | places with ≥ 1 earlier |
|---|---|---|---|---|
| ORDINARY / 5 h | 118 | 44 | 51 | 34 |
| ORDINARY / 8 h | 164 | 73 | 72 | 50 |
| RUNNING / 5 h | 952 | 100 | 133 | 61 |
| RUNNING / 8 h | **1,093** | **108** | 133 | 61 |
| WORST / 5 h | 855 | 26 | 125 | 15 |
| WORST / 8 h | 930 | 26 | 125 | 15 |
| MEASURED / 5 h | 297 | 137 | 134 | 103 |
| MEASURED / 8 h | 349 | 181 | 140 | 114 |
| MEASURED+GUST / 5 h (PROVISIONAL; >= 20 m/s class = 9 fires) | 394 | 201 | 136 | 107 |
| MEASURED+GUST / 8 h (PROVISIONAL; >= 20 m/s class = 9 fires) | 492 | 280 | 138 | 112 |

Under the two MEASURED arms the margin is narrower than RUNNING until 21:00, so fewer routes are shown as cut within the horizon
and a larger share of those shown are reached earlier by the reconstruction (181 of 349 for MEASURED / 8 h against 108 of 1,093 for RUNNING / 8 h).
The counts are not comparable as a performance ranking: the denominators are different sets of place-hours.

The reconstruction ends with the data: AHI to 2025-03-25 17:57:30 UTC and FIRMS to 17:58 UTC (26 March 02:58 KST).
A route reached later than that is not counted.

## 6 Checks

* **Held-out AHI false-alarm check:** pre-ignition night, 21/22 March. **0** hotspots.
* **AHI vs FIRMS** (diagnostic; not a rule change; [ahi_firms_agreement.json](ahi_firms_agreement.json)):
  * 277 of 358 AHI hotspots have a FIRMS detection within 2 km at some time. AHI came first in 208 of those; median
    lead 4.5 h.
  * **81 of 358 (23 %) are never confirmed** by FIRMS in the data. These are UNCONFIRMED.
  * Daytime false alarms were not tested: no fire-free daytime window at the same hours exists after 20 March.
* **Witness re-check:** every witness road is re-walked from its departure second against the cell closures, and the
  dwell is checked at the shelter. **6,316 / 6,316 pass**, with identical arrival seconds; the MEASURED and MEASURED+GUST
  arms add **4,528 / 4,528 pass**.
* **F-3.1 certificate** (`check_fixed_point`) on 3 instances: 43,826, 111,924 and 111,924 states. **PASS**
  ([fixed_point.json](fixed_point.json)).
* **Planner shelter candidates:** identical to `planner/cache` requests for 174/174 places.

## 7 Limits (stated, not corrected)

* **MEASURED arms:** the class is one value per issue hour for all places; the prior-3 h spread is taken from detection discs (5 km
  separate-fire rule applied per disc, not per component); the closure curve below 5 h is ASSUMED linear. The gust class is
  ERA5 over the next H hours at five county-seat points (a perfect forecast, ASSUMED), not KMA observations, so MEASURED+GUST is
  PROVISIONAL, and its >= 20 m/s class rests on 9 fires. The margin was calibrated on 28 California fires; on this fire
  every frozen margin was exceeded at 10-20 KST (`research/kcf-margin/RESULTS.md`). One fire, one day: no rate is claimed.

* **Delivery latency is not modelled.** A detection counts from its overpass or scan time. FIRMS NRT delivery takes hours.
* **Closures are permanent.** A burned-out cell stays closed, so roads through earlier fire count as cut.
* **AHI covers only the KFS_01 grid** (448 pixels). The eastern edge of 영덕 and anything east of x = 1,174,125 is seen
  by FIRMS only. AHI starts at 2025-03-24 18:00 UTC.
* **Two readings are this replay's own:** the 5 h step as "leave now", and R(h) as a straight-line distance with no
  wind direction.
* **Routing scope:** no congestion, no return trips, and travel between a place and its 진입 지점 is not modelled (as in
  the planner).
* **Road names:** roads are OSM way ids; names are not resolved.
* **Planner cache** ([planner_cache/RUNNING_8h](planner_cache/RUNNING_8h); also [MEASURED_8h](planner_cache/MEASURED_8h) and
  [MEASURED_GUST_8h](planner_cache/MEASURED_GUST_8h), PROVISIONAL, written 17 Nov 2026 from a re-run of `replay.py` for those two
  arms at 8 h; every place-hour matches `per_place.csv` on the 30-minute grid, `tests/planner/replay.test.ts`):
  * Verdicts come from the field, not the Route-Check API, on a 30-minute grid.
  * The app labels the input "2025년 실제 산불 기록 기반 시나리오 재현" and shows its test-data badge
    (시험 데이터 · 평가 호스트 아님).
  * The planner draws the witness route line at each place-hour's leave-by time (1,093 of 1,093 place-hours; until
    17 Nov 2026 the static demo omitted it). The public demo lists this cache as its own scenario with an hour
    slider and the six named places (planner/README.md, "25 March 2025 replay").
