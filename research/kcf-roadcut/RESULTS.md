# kcf-roadcut — results: how much earlier is the last road cut than the village is reached?

**Every number here is model output on reconstructed inputs. It is not what happened to people.** Nothing here is a
claim about what any official should have done. The Korea Forest Service rule is *read* here (assumptions in §4); its
system is not reproduced.

Protocol: `PROTOCOL.md`, frozen at `e8947dc` before any outcome was computed; amendments 1 (`9b16a3a`) and 2 (`67afec0`)
were both made before any validation comparison or test was run. Main at `896bd41` (PR #193). Run 2026-11-18,
10:37–13:30 UTC.

## 0 Headline (primary configuration fixed in advance: kcf-replay, MEASURED arm, 8 h horizon)

*Model output on reconstructed inputs. Not what happened to people.*

Units: 174 places × 13 issue hours (25 Mar 2025, 12:00–24:00 KST) = 2,262 place-hours.

* **States:**
  * 1,077 are INSIDE: the place's entry point is already inside the known fire area at the issue hour, so there is no gap.
  * 785 are not cut within 8 h.
  * 349 are CUT.
  * 51 have NO_WINDOW: not inside, but no departure works at the issue hour.
* **The road is cut before the village is reached (count A):** **154 place-hours at 68 of 174 places**. These are the
  103 CUT place-hours whose last window ends on a road cell, plus the 51 NO_WINDOW place-hours. In another 79 CUT
  place-hours the window ends at the shelter (the destination closes first; counted separately). In the other 167 CUT
  place-hours the window ends on the village's own cell.
* **The gap, T_village − T_road, over the 343 exact gaps at 136 places:**
  * Median **1.2 min**; 10th–90th percentile 0.2–29.3 min.
  * Largest **326.8 min**: 동변리 (의성군), 12:00 issue. The shelter ends that window.
  * 57 further place-hours give only a lower bound; the largest is 256.3 min.
* **The median is small by construction.** Where the village's own cell ends the window (n = 167), the "gap" is only the
  time needed to leave that cell: median 0.3 min, maximum 1.8 min. That is not a finding (PROTOCOL §2.4).
* **Where a road cell ends the window (n = 97 exact),** the road is cut a median **11.8 min** before the village is
  reached, with a maximum of **159.6 min** (삼의리, 영양군, 18:00 issue).
* **Gap thresholds:**

  | | gap ≥ 5 min | gap ≥ 15 min | gap ≥ 30 min | gap ≥ 60 min |
  |---|---|---|---|---|
  | exact gaps (place-hours) | 118 | 77 | 33 | 18 |
  | adding lower bounds | 167 | 118 | 67 | 40 |

* **Holes in the windows:** none. In all 27,144 place-hours of every arm and horizon, the merged window set of every
  place is a single interval, so "end of the last window" is "end of the window". Family M is a prefix by
  construction (no holes possible).
* **Under the 5 h / 8 h reading (§3):**
  * **12 place-hours at 10 places** are "prepare" (8) or nothing (4) while the model's last road out closes within 5 h (P5).
  * **6 place-hours at 4 places** are nothing while the last road closes within 8 h (P8): 구계리 (의성군) at 12:00,
    13:00 and 14:00, and 상아리, 인금리 and 하아리 (안동시) at 15:00.
  * No P5 or P8 place-hour in the primary configuration is a NO_WINDOW case. The list is in §3.3.
* **Across all arms (8 h):**
  * Count A runs from 102 place-hours at 47 places (ORDINARY) to 521 at 121 places (WORST).
  * P5 runs from 5 (WORST) to 19 (MEASURED_GUST_KMA).
  * P8 runs from 0 (RUNNING, WORST) to 17 (ORDINARY).
  * The fast arms (RUNNING, WORST) put nearly every place's village within 5 h, so they leave almost nothing in the
    "prepare" or "nothing" steps.
* **Validation** (§5) **is weak and mostly uninformative.** Every record is REPORTED (news), and most were seen only as
  search-snippet text.
  * **Expressways (8 records):** the model already had the in-grid section "closed" at the issue hour. Its known fire
    area touched those routes from 23–24 March, while the recorded closures are on 25–26 March.
  * **Local roads (4 records):** MEASURED closes two of them 20 and 30 min *after* the recorded time and **misses**
    the other two (not closed by 01:00).
  * **Burned area:** the model's "reached" area covers every assessable cell of both grids, against ≈ 45 % burned on
    the Sentinel-2 map. This over-coverage starts in the fire input (2 km discs around hotspots), not in the spread
    arm.

So, to the question "how much earlier?": in this model, when the last road out is cut before the village is reached, it
is usually cut minutes before (median 11.8 min in the primary configuration, 2.8–34.0 min across arms); at a few
places it is hours. At 68 of 174 places this happens at least once during the 13 issue hours. None of these times has
been shown to match what happened on the roads.

## 1 What was computed (summary of the protocol)

* **R** (kcf-replay):
  * For each place, issue hour T, arm and horizon H, the departure-window set is the union over the place's 3 planner
    shelters of the F-3.1 issue sets, merged.
  * T_road = the end of the last window.
  * T_village = the closure time of the place's own entry cell under the same arm. This is "fire within reach of the
    entry point" by the arm's closure rule, the same rule that closes road cells. It is not a physical flame-arrival
    time.
  * The binding cell (PROTOCOL §2.4) is the minimum-slack closure on the witness route at T_road.
* **M** (multi-hour F-DYN HEADLINE run, `no_reentry/2`):
  * The window is [T, T + leave_by_s].
  * T_village comes from the Choi 2026 TOA raster (kriged_mean) or from `firms_variants` (firms_early). The envelope is
    taken as firms_early (ASSUMED reading).
  * The rasters are rebuilt here from committed inputs, not read from the F-DYN packets, which are not on Main.
  * 3,132 rows (amendment 2a).
* **Reproduction:** `replay.py` was rerun unchanged (312 jobs). `analyze.py` on the rerun gives a `per_place.csv`
  identical to the committed one in **every column of all 27,144 rows**, with 0 keys present in only one of the two
  (`repro_check.json` checked the 7 protocol columns; a full-column diff also gave 0 differences). Only the row order
  differs, so the file SHA-256 differs.
  * The SHA-256 of the 312 raw run files and the intermediate files (which stay in scratch because of their size)
    are in `runs_sha256.txt`.
* **Integrity checks** (`numbers.json` → `checks`):
  * The step from T_village equals the committed `government_step` in every R 8 h row: 0 mismatches.
  * No M row is INSIDE by the raster while having a route in the run: 0.

## 2 All configurations

MEASURED_GUST (ERA5) is **PROVISIONAL** (marked †). Both gust arms' ≥ 20 m/s class rests on 9 fires. R and M are never
pooled. In M, "cut before reached" can only be read as gap ≥ 5 min or NO_WINDOW, because M has no committed witness
routes.

### 2.1 States, binding cell and count A

*Model output on reconstructed inputs. Not what happened to people.*

| family / arm / horizon | place-hours (places) | INSIDE | NOT_CUT_WITHIN_H | CUT | NO_WINDOW | CUT ending on road / village / shelter | count A: place-hours (places) | gap ≥ 5 min or NO_WINDOW: place-hours (places) |
|---|---|---|---|---|---|---|---|---|
| R / MEASURED / 8h | 2262 (174) | 1077 | 785 | 349 | 51 | 103 / 167 / 79 | 154 (68) | 175 (65) |
| R / MEASURED / 5h | 2262 (174) | 1077 | 837 | 297 | 51 | 88 / 132 / 77 | 139 (64) | 161 (62) |
| R / ORDINARY / 8h | 2262 (174) | 1077 | 971 | 164 | 50 | 52 / 69 / 43 | 102 (47) | 134 (53) |
| R / ORDINARY / 5h | 2262 (174) | 1077 | 1017 | 118 | 50 | 38 / 47 / 33 | 88 (42) | 111 (46) |
| R / RUNNING / 8h | 2262 (174) | 1077 | 0 | 1093 | 92 | 313 / 338 / 442 | 405 (91) | 292 (69) |
| R / RUNNING / 5h | 2262 (174) | 1077 | 141 | 952 | 92 | 276 / 320 / 356 | 368 (91) | 271 (69) |
| R / WORST / 8h | 2262 (174) | 1077 | 0 | 930 | 255 | 266 / 293 / 371 | 521 (121) | 418 (115) |
| R / WORST / 5h | 2262 (174) | 1077 | 75 | 855 | 255 | 247 / 285 / 323 | 502 (121) | 402 (115) |
| R / MEASURED_GUST_KMA / 8h | 2262 (174) | 1077 | 648 | 482 | 55 | 165 / 232 / 85 | 220 (80) | 238 (76) |
| R / MEASURED_GUST_KMA / 5h | 2262 (174) | 1077 | 781 | 351 | 53 | 116 / 166 / 69 | 169 (74) | 186 (71) |
| R / MEASURED_GUST / 8h † | 2262 (174) | 1077 | 638 | 492 | 55 | 169 / 234 / 89 | 224 (80) | 241 (76) |
| R / MEASURED_GUST / 5h † | 2262 (174) | 1077 | 736 | 394 | 55 | 139 / 183 / 72 | 194 (74) | 205 (70) |
| M / kriged_mean / 8h | 522 (174) | 191 | 245 | 41 | 45 | no witness routes | – | 75 (50) |
| M / kriged_mean / 5h | 522 (174) | 191 | 247 | 39 | 45 | no witness routes | – | 73 (50) |
| M / firms_early / 8h | 522 (174) | 200 | 239 | 21 | 62 | no witness routes | – | 80 (56) |
| M / firms_early / 5h | 522 (174) | 200 | 240 | 20 | 62 | no witness routes | – | 79 (56) |
| M / envelope / 8h | 522 (174) | 200 | 239 | 21 | 62 | no witness routes | – | 80 (56) |
| M / envelope / 5h | 522 (174) | 200 | 240 | 20 | 62 | no witness routes | – | 79 (56) |

### 2.2 Gap distribution (minutes; exact gaps only in median/percentiles/max; lower bounds counted separately)

*Model output on reconstructed inputs. Not what happened to people.*

| family / arm / horizon | exact gaps n (places) | median | p10 | p90 | max | lower bounds n | largest lower bound | > 0 | ≥ 5 | ≥ 15 | ≥ 30 | ≥ 60 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R / MEASURED / 8h | 343 (136) | 1.2 | 0.2 | 29.3 | 326.8 | 57 | 256.3 | 343 / 400 | 118 / 167 | 77 / 118 | 33 / 67 | 18 / 40 |
| R / MEASURED / 5h | 286 (130) | 1.8 | 0.2 | 25.0 | 203.7 | 62 | 293.5 | 286 / 348 | 100 / 153 | 60 / 104 | 23 / 59 | 11 / 31 |
| R / ORDINARY / 8h | 148 (67) | 2.3 | 0.1 | 72.0 | 426.7 | 66 | 480.0 | 148 / 214 | 68 / 131 | 62 / 120 | 47 / 101 | 23 / 69 |
| R / ORDINARY / 5h | 103 (46) | 2.2 | 0.1 | 59.6 | 257.1 | 65 | 300.0 | 103 / 168 | 46 / 108 | 42 / 95 | 30 / 78 | 10 / 50 |
| R / RUNNING / 8h | 1093 (133) | 1.6 | 0.3 | 6.5 | 48.6 | 92 | 45.5 | 1093 / 1185 | 200 / 231 | 47 / 55 | 25 / 30 | 0 / 0 |
| R / RUNNING / 5h | 952 (133) | 1.5 | 0.2 | 7.1 | 48.6 | 92 | 45.5 | 952 / 1044 | 179 / 210 | 47 / 55 | 25 / 30 | 0 / 0 |
| R / WORST / 8h | 930 (125) | 1.5 | 0.2 | 6.1 | 42.2 | 255 | 40.8 | 930 / 971 | 163 / 177 | 37 / 43 | 20 / 22 | 0 / 0 |
| R / WORST / 5h | 854 (125) | 1.4 | 0.2 | 6.3 | 42.2 | 256 | 40.8 | 854 / 896 | 147 / 161 | 37 / 43 | 20 / 22 | 0 / 0 |
| R / MEASURED_GUST_KMA / 8h | 466 (138) | 1.0 | 0.1 | 34.6 | 181.8 | 71 | 406.3 | 466 / 537 | 167 / 227 | 106 / 149 | 54 / 82 | 29 / 40 |
| R / MEASURED_GUST_KMA / 5h | 338 (136) | 1.2 | 0.1 | 29.2 | 181.8 | 66 | 226.3 | 338 / 404 | 120 / 175 | 69 / 114 | 32 / 63 | 18 / 32 |
| R / MEASURED_GUST / 8h † | 480 (138) | 1.2 | 0.1 | 34.4 | 272.5 | 67 | 102.2 | 480 / 547 | 174 / 230 | 110 / 149 | 52 / 75 | 28 / 35 |
| R / MEASURED_GUST / 5h † | 380 (135) | 1.2 | 0.1 | 26.7 | 181.8 | 69 | 266.5 | 380 / 449 | 136 / 194 | 78 / 123 | 30 / 59 | 15 / 27 |
| M / kriged_mean / 8h | 19 (19) | 3.2 | 1.3 | 26.3 | 52.9 | 67 | 480.0 | 19 / 86 | 8 / 74 | 5 / 66 | 2 / 62 | 0 / 48 |
| M / kriged_mean / 5h | 19 (19) | 3.2 | 1.3 | 26.3 | 52.9 | 65 | 300.0 | 19 / 84 | 8 / 72 | 5 / 64 | 2 / 60 | 0 / 47 |
| M / firms_early / 8h | 4 (4) | 6.5 | 2.9 | 183.2 | 257.5 | 79 | 480.0 | 4 / 83 | 2 / 79 | 1 / 70 | 1 / 64 | 1 / 54 |
| M / firms_early / 5h | 3 (3) | 3.2 | 2.9 | 8.5 | 9.9 | 79 | 300.0 | 3 / 82 | 1 / 78 | 0 / 69 | 0 / 63 | 0 / 54 |
| M / envelope / 8h | 4 (4) | 6.5 | 2.9 | 183.2 | 257.5 | 79 | 480.0 | 4 / 83 | 2 / 79 | 1 / 70 | 1 / 64 | 1 / 54 |
| M / envelope / 5h | 3 (3) | 3.2 | 2.9 | 8.5 | 9.9 | 79 | 300.0 | 3 / 82 | 1 / 78 | 0 / 69 | 0 / 63 | 0 / 54 |

Threshold columns: place-hours with an exact gap at or above the threshold / the same plus lower bounds at or above it (a lower bound at or above a threshold means the true gap is too).

### 2.3 Exact gap by what ends the last window (R, minutes)

*Model output on reconstructed inputs. Not what happened to people.*

| arm / horizon | road cell: n, median, max | village's own cell: n, median, max | shelter: n, median, max |
|---|---|---|---|
| MEASURED / 8h | 97, 11.8, 159.6 | 167, 0.3, 1.8 | 79, 15.2, 326.8 |
| MEASURED / 5h | 81, 10.0, 66.4 | 132, 0.3, 1.7 | 73, 14.6, 203.7 |
| ORDINARY / 8h | 46, 34.0, 426.7 | 69, 0.3, 1.2 | 33, 58.3, 289.8 |
| ORDINARY / 5h | 35, 34.0, 137.5 | 47, 0.3, 1.2 | 21, 17.4, 257.1 |
| RUNNING / 8h | 313, 2.9, 42.2 | 338, 0.4, 1.2 | 442, 2.8, 48.6 |
| RUNNING / 5h | 276, 3.0, 42.2 | 320, 0.4, 1.2 | 356, 2.8, 48.6 |
| WORST / 8h | 266, 2.8, 42.2 | 293, 0.4, 1.2 | 371, 2.9, 39.5 |
| WORST / 5h | 247, 2.9, 42.2 | 285, 0.4, 1.2 | 322, 2.8, 39.5 |
| MEASURED_GUST_KMA / 8h | 158, 13.1, 174.1 | 232, 0.3, 1.8 | 76, 13.1, 181.8 |
| MEASURED_GUST_KMA / 5h | 108, 10.7, 135.2 | 166, 0.3, 1.8 | 64, 14.1, 181.8 |
| MEASURED_GUST † / 8h | 162, 12.3, 174.1 | 234, 0.4, 1.8 | 84, 13.1, 272.5 |
| MEASURED_GUST † / 5h | 128, 10.7, 135.2 | 183, 0.3, 1.8 | 69, 13.2, 181.8 |

No CUT place-hour had binding UNCLEAR (minimum slack > 60 s) in any configuration.

### 2.4 Places with the largest gaps (primary configuration)

*Model output on reconstructed inputs. Not what happened to people.*

Ten places with the largest exact gap (R, MEASURED, 8 h), each at the issue hour of its largest gap:

| place (시군) | issue (KST) | T_road − issue (min) | T_village − issue (min) | gap (min) | last window ends on | exact gaps at this place: n, median |
|---|---|---|---|---|---|---|
| 동변리 (의성군) | 12:00 | 6.5 | 333.3 | 326.8 | SHELTER_CELL | 2, 260.0 |
| 내룡리 (청송군) | 19:00 | 147.4 | 372.7 | 225.2 | SHELTER_CELL | 7, 172.6 |
| 사촌리 (의성군) | 12:00 | 10.6 | 180.9 | 170.3 | SHELTER_CELL | 2, 170.3 |
| 삼의리 (영양군) | 18:00 | 159.0 | 318.6 | 159.6 | ROAD_CELL | 1, 159.6 |
| 서변리 (의성군) | 12:00 | 10.9 | 146.5 | 135.6 | SHELTER_CELL | 2, 135.6 |
| 국곡리 (안동시) | 15:00 | 324.8 | 426.1 | 101.3 | ROAD_CELL | 2, 63.6 |
| 광연리 (안동시) | 12:00 | 286.9 | 378.8 | 91.9 | ROAD_CELL | 3, 30.0 |
| 송리리 (안동시) | 16:00 | 43.4 | 109.8 | 66.4 | ROAD_CELL | 2, 54.6 |
| 용상3구경로당 (안동시) | 16:00 | 252.6 | 317.4 | 64.8 | SHELTER_CELL | 1, 64.8 |
| 옥계리 (영덕군) | 20:00 | 380.9 | 435.6 | 54.6 | ROAD_CELL | 6, 4.5 |

The figure `gap_per_place.png` shows every place-hour of the primary configuration. It has one row per place (150
places with at least one CUT or NO_WINDOW hour; the 24 others are INSIDE at every issue hour). Colour shows what
ends the last window. Open triangles are lower bounds.

![gap per place](gap_per_place.png)

### 2.5 Family M: caveats specific to it

*Model output on reconstructed inputs. Not what happened to people.*

* **Very few exact gaps:** 19 place-hours under kriged_mean and 4 under firms_early (8 h). Most CUT rows have
  T_village beyond the horizon.
* **Arrival can be late against the records.** For the four 영덕 local-road records, the Choi raster puts the fire
  ≈ 400 min later than the recorded closure (§5.1, last column). M's T_village can therefore be late.
* **Most M NO_WINDOW rows may not be fire-limited.** Under kriged_mean / 8 h there are 45 NO_WINDOW rows:
  * 30 carry the F-DYN flag `possibly_road_limited`: the route may exist beyond the loaded graph.
  * 38 are `lost_route_depends_on_no_reentry`: no route only because of the no-re-entry rule.
* **Consequence for P8:** of M's P8 = 58 place-hours (kriged_mean), 27 are `possibly_road_limited` NO_WINDOW rows, 9 are
  fire-limited NO_WINDOW rows, and 22 are CUT. So M's P5 / P8 counts mostly reflect those flags, not the
  village-versus-road contrast.
* **One row disagrees with itself:** under kriged_mean, one NO_WINDOW row is flagged `origin_point_in_flame_at_departure`
  while its raster T_village is after T. It is reported as is.

## 3 The government rule as applied here

### 3.1 Assumptions (all ASSUMED; this is a reading, not the Korea Forest Service system)

Source of the rule: YTN, 2025-04-16, as cited in `research/kcf-replay/SOURCES.md` (REPORTED). Where the fire line is
known, areas the fire can reach within 5 h are 위험구역 and within 8 h 잠재적 위험구역.

1. "Leave now" = the 5 h zone; "prepare" = the 8 h zone (vulnerable people pre-evacuate). The source does not map
   zones to these words.
2. The reach time is counted to the place's entry point, i.e. T_village.
3. The reach time is computed **with the same arm or variant as the road model**, from the same known fire area at T.
   This isolates village versus road. It does not reproduce the Korea Forest Service's spread estimate, data, timing
   or delivery.
4. The designation is made at each issue hour (R) or start (M) and acts at once, with no notification or mobilisation
   time.
5. In M, the step uses the raster T_village without censoring at H, and INSIDE counts as "leave now". R uses the
   committed `government_step`, which equals the step from T_village in all 8 h rows.

**Definitions:**
* **P5** = told "prepare" or nothing, while the last road closes within 5 h (or there is no window at T).
* **P8** = told nothing, while the last road closes within 8 h (or there is no window).

Both are counted on the 8 h runs. P5 is also counted on the 5 h runs.

### 3.2 Counts

*Model output on reconstructed inputs. Not what happened to people.*

| family / arm / horizon | P5 place-hours (places) | P5 by step | P5 of which NO_WINDOW | P8 place-hours (places) | P8 of which NO_WINDOW | all steps LEAVE_NOW / PREPARE / NONE |
|---|---|---|---|---|---|---|
| R / MEASURED / 8h | 12 (10) | NONE 4, PREPARE 8 | 0 | 6 (4) | 0 | 1417 / 57 / 788 |
| R / MEASURED / 5h | 11 (9) | NONE 4, PREPARE 7 | 0 | 8 h runs only | – | 1417 / 57 / 788 |
| R / ORDINARY / 8h | 16 (7) | NONE 8, PREPARE 8 | 2 | 17 (8) | 1 | 1231 / 46 / 985 |
| R / ORDINARY / 5h | 17 (8) | NONE 8, PREPARE 9 | 2 | 8 h runs only | – | 1231 / 46 / 985 |
| R / RUNNING / 8h | 8 (3) | PREPARE 8 | 0 | 0 (0) | 0 | 2126 / 136 / 0 |
| R / RUNNING / 5h | 0 (0) | – | 0 | 8 h runs only | – | 2126 / 136 / 0 |
| R / WORST / 8h | 5 (4) | PREPARE 5 | 0 | 0 (0) | 0 | 2195 / 67 / 0 |
| R / WORST / 5h | 1 (1) | PREPARE 1 | 0 | 8 h runs only | – | 2195 / 67 / 0 |
| R / MEASURED_GUST_KMA / 8h | 19 (14) | NONE 4, PREPARE 15 | 0 | 16 (10) | 0 | 1504 / 97 / 661 |
| R / MEASURED_GUST_KMA / 5h | 13 (10) | NONE 5, PREPARE 8 | 0 | 8 h runs only | – | 1472 / 79 / 711 |
| R / MEASURED_GUST / 8h † | 16 (12) | PREPARE 16 | 0 | 12 (8) | 0 | 1516 / 99 / 647 |
| R / MEASURED_GUST / 5h † | 14 (10) | PREPARE 14 | 0 | 8 h runs only | – | 1516 / 99 / 647 |
| M / kriged_mean / 8h | 43 (27) | NONE 43 | 36 | 58 (35) | 36 | 219 / 0 / 303 |
| M / kriged_mean / 5h | 56 (35) | NONE 56 | 36 | 8 h runs only | – | 219 / 0 / 303 |
| M / firms_early / 8h | 44 (27) | NONE 43, PREPARE 1 | 41 | 58 (35) | 41 | 224 / 1 / 297 |
| M / firms_early / 5h | 58 (36) | NONE 57, PREPARE 1 | 41 | 8 h runs only | – | 224 / 1 / 297 |
| M / envelope / 8h | 44 (27) | NONE 43, PREPARE 1 | 41 | 58 (35) | 41 | 224 / 1 / 297 |
| M / envelope / 5h | 58 (36) | NONE 57, PREPARE 1 | 41 | 8 h runs only | – | 224 / 1 / 297 |

### 3.3 The primary configuration's P5 / P8 place-hours

*Model output on reconstructed inputs. Not what happened to people.*

| place (시군) | category | issue (KST) | step under the reading | T_road − issue (min) | T_village − issue (min) | last window ends on | in |
|---|---|---|---|---|---|---|---|
| 광연리 (안동시) | village | 12:00 | PREPARE | 287 | 379 | ROAD_CELL | P5 |
| 구계리 (의성군) | village | 12:00 | NONE | 258 | > 480 (beyond 8 h) | ROAD_CELL | P5, P8 |
| 동변리 (의성군) | village | 12:00 | PREPARE | 6 | 333 | SHELTER_CELL | P5 |
| 구계리 (의성군) | village | 13:00 | NONE | 249 | > 480 (beyond 8 h) | ROAD_CELL | P5, P8 |
| 구계리 (의성군) | village | 14:00 | NONE | 249 | > 480 (beyond 8 h) | ROAD_CELL | P5, P8 |
| 광음리 (안동시) | village | 15:00 | PREPARE | 281 | 325 | ROAD_CELL | P5 |
| 상아리 (안동시) | village | 15:00 | NONE | 410 | > 480 (beyond 8 h) | ROAD_CELL | P8 |
| 송리리 (안동시) | village | 15:00 | PREPARE | 280 | 323 | ROAD_CELL | P5 |
| 인금리 (안동시) | village | 15:00 | NONE | 224 | > 480 (beyond 8 h) | ROAD_CELL | P5, P8 |
| 하아리 (안동시) | village | 15:00 | NONE | 404 | > 480 (beyond 8 h) | ROAD_CELL | P8 |
| 용상3구경로당 (안동시) | social_facility (vulnerable) | 16:00 | PREPARE | 253 | 317 | SHELTER_CELL | P5 |
| 삼의리 (영양군) | village | 18:00 | PREPARE | 159 | 319 | ROAD_CELL | P5 |
| 내룡리 (청송군) | village | 19:00 | PREPARE | 147 | 373 | SHELTER_CELL | P5 |
| 옥산리 (영덕군) | village | 20:00 | PREPARE | 295 | 324 | SHELTER_CELL | P5 |

## 4 Ronchi et al. (2023) verification tests

Ronchi E, Wahlqvist J, Ardinge A, Rohaert A, Gwynne SMV, Rein G, Mitchell H, Kalogeropoulos N, Kinateder M, Bénichou
N, Kuligowski E, Kimball A. *The verification of wildland–urban interface fire evacuation models.* Natural Hazards
117(2):1493–1519 (2023). doi:10.1007/s11069-023-05913-2. Full text read via PMC (PMC10220130, eutils efetch XML),
retrieved 2026-11-18 10:41:15 UTC.

**What could and could not be read:**
* The supplement (`11069_2023_5913_MOESM1_ESM.docx`), which holds the full per-test geometries, could not be fetched:
  PMC returned a CAPTCHA, and Springer and the FPRF report are unreachable from this session. The geometries are
  therefore built from the main-text descriptions.
* The paper sets **no pass criterion**: "it is here left up to the model user to judge if a given testing result is
  acceptable". Here, PASS means the model's result equals the hand calculation under the model's own assumptions,
  exactly in integer seconds (amendment 2d).

*Synthetic test instances, not the 2025 fire: model output on constructed inputs, not what happened to people.*

**How the tests were run:** through the unchanged `deadline_field.core` plus the replay closure functions
(`ronchi_tests.py`, `ronchi_tests.json`).

| test | what it checks | verdict | detail |
|---|---|---|---|
| T.1a | single vehicle, one road type | **PASS** | 1000 m at 50 km/h: arrival 72 s = hand; departure set [0, 3408] = hand |
| T.1b | single vehicle, several road types | **PASS** | 1000 m at 50 + 2000 m at 80 + 500 m at 30 km/h: 222 s = hand |
| T.12 | forced destination | **PASS** | forced to the far shelter (5 km at 60 km/h): 300 s via edge 1 = hand |
| WT.1 | route loss | **PASS** | the short route's road is lost at 600 s: the short route is used to departure 479 s, then the long route (720 s); set [0, 3240] = hand |
| WT.3 | loss of shelter / exit | **PASS** | shelter 1 cell closes at 1000 s (120 s dwell): its set is [0, 789], shelter 2 [0, 3120] = hand |
| B.1 | homogeneous spread (base case) | **PASS (weak for MEASURED)** | 4 communities equidistant from a point ignition: equal arrivals = distance / R for ORDINARY, RUNNING, WORST. For MEASURED, the communities (10.6 km) lie beyond its 8 h reach (3.5 / 10 km), so the test only shows all four agree on "never reached". |
| P.1–P.4, PT.1 | pedestrians, households, response curve | not applicable | no pedestrians, households or pre-evacuation behaviour |
| T.2–T.11, T.13–T.15 | traffic, lanes, visibility, crashes, intersections, demand | not applicable | single vehicles, fixed edge times, no traffic flow |
| WT.2, WT.4 | lane reversal, refuge capacity | not applicable | no lanes; shelters have no capacity |
| B.2–B.5 | fuel, wind, valley, heterogeneous | not applicable | no fuel, wind or slope input; reach is isotropic |

Of the 29 codes, 6 apply and all 6 pass; the other 23 are not applicable (reasons in `ronchi_tests.json`).

**Extra check, not counted as T.14:** the T.14 geometry with a single vehicle and no traffic (4000 m at 120 km/h vs
2000 m at 30 km/h) gives 120 s by the fast route, matching the hand calculation. The paper's 122 s includes WUI-NITY's
traffic model and is not comparable.

**Harness bug:** the B.1 harness at first compared `inf − inf` (NaN) for never-reached points and failed for that
reason. It was fixed to an exact equality comparison against the hand-computed closure before the result was recorded.
The model code was not changed.

## 5 Validation against records the model never used

*Model output on reconstructed inputs. Not what happened to people.*

**How the records were found:** web searches on 2026-11-18, 10:38–10:47 UTC; sources and retrieval times are in
`records_raw/`.

**Every record is REPORTED** (news media). Korean news, government and Wikipedia hosts are blocked from this session.
Every record except the 뉴스로 영덕군 log is search-result text only, **not a page read in full**. The 뉴스로 log was
read in full on 2026-11-16 (per `research/kcf-replay/SOURCES.md`) and is one outlet's transcription of the county's
log.

**Conflicts between records** (reported, not resolved):
* 중앙선 의성IC–예천IC closure: 18:00 (outlet unidentified), 22:00 (to 풍기, 한국경제/Yonhap) and 26 Mar 07:55 (뉴시스).
* The 서산영덕선 closure is reported both as "안동JC~청송IC" and as "~청송JC".
* First 영덕 wildfire text: 18:00 (CBS, per 뉴스로) or 21:00 (메트로신문).
* 지품면 order: 16:30 (대구MBC, 면장) or 18:00 (county log).
* The 911 control text: 19:09 (아시아경제) or 19:04 (뉴스로 entry for 도계→영양).

**How records were placed on the road graph** (amendment 2b):
* Roads are located by joining OSM way ids to Overture Maps 2026-10-21.0 route refs.
* Towns are the Overture locality polygons. 안동 and 의성 use web-search 법정리 lists instead (flagged).
* Model times are read at the latest issue hour at least 1 h before the record (roads) or at or before the order time
  (orders). Error = model − recorded.

### 5.1 Road closures and village fire-arrival accounts — the validation table (`validation_table.csv`)

*Model output on reconstructed inputs. Not what happened to people.* Records are REPORTED (news; search-snippet text unless 'full page'). Error = model − recorded, minutes.

| id | record | recorded (KST, 2025) | source (access; retrieved UTC) | issue used (KST) | where on the model graph | MEASURED | RUNNING | ORDINARY | WORST | GUST_KMA | GUST † | hotspot reconstruction | Choi TOA (M input) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RD1 | 서산영덕선 안동JC~청송IC both ways, closure (도로공사) | 03-25 15:30 | 머니투데이 (mt.co.kr) <https://www.mt.co.kr/policy/2025/03/25/2025032516313321381> (snippet; 2026-11-18T10:39) | 03-25 14:00 | route 30: all in-grid cells east of 안동JC | 03-25 14:00 (closed at issue: error ≤ -90) | 03-25 14:00 (closed at issue: error ≤ -90) | 03-25 14:00 (closed at issue: error ≤ -90) | 03-25 14:00 (closed at issue: error ≤ -90) | 03-25 14:00 (closed at issue: error ≤ -90) | 03-25 14:00 (closed at issue: error ≤ -90) | 03-24 12:44 (-1606) | 03-24 17:21 (-1328) |
| RD2 | 서산영덕선 서의성IC~영덕IC both ways, closure | 03-25 17:00 | 서울신문 (m.seoul.co.kr), article '안동·청송 대피령… 천년고찰 고운사도 불탔다' <https://m.seoul.co.kr/news/2025/03/26/20250326001006> (snippet; 2026-11-18T10:42) | 03-25 16:00 | route 30: all in-grid cells | 03-25 16:00 (closed at issue: error ≤ -60) | 03-25 16:00 (closed at issue: error ≤ -60) | 03-25 16:00 (closed at issue: error ≤ -60) | 03-25 16:00 (closed at issue: error ≤ -60) | 03-25 16:00 (closed at issue: error ≤ -60) | 03-25 16:00 (closed at issue: error ≤ -60) | 03-23 03:23 (-3697) | 03-24 16:25 (-1474) |
| RD3 | 중앙선 의성IC~서안동IC both ways, closure | 03-25 17:00 | 서울신문 (m.seoul.co.kr), article '안동·청송 대피령… 천년고찰 고운사도 불탔다' <https://m.seoul.co.kr/news/2025/03/26/20250326001006> (snippet; 2026-11-18T10:42) | 03-25 16:00 | route 55: all in-grid cells | 03-25 16:00 (closed at issue: error ≤ -60) | 03-25 16:00 (closed at issue: error ≤ -60) | 03-25 16:00 (closed at issue: error ≤ -60) | 03-25 16:00 (closed at issue: error ≤ -60) | 03-25 16:00 (closed at issue: error ≤ -60) | 03-25 16:00 (closed at issue: error ≤ -60) | 03-25 01:28 (-932) | 03-25 14:17 (-163) |
| RD4 | 중앙선 의성IC~예천IC, closure 'from 18:00' (outlet unidentified) | 03-25 18:00 | UNIDENTIFIED  (snippet; 2026-11-18T10:41) | 03-25 17:00 | route 55: all in-grid cells | 03-25 17:00 (closed at issue: error ≤ -60) | 03-25 17:00 (closed at issue: error ≤ -60) | 03-25 17:00 (closed at issue: error ≤ -60) | 03-25 17:00 (closed at issue: error ≤ -60) | 03-25 17:00 (closed at issue: error ≤ -60) | 03-25 17:00 (closed at issue: error ≤ -60) | 03-25 01:28 (-992) | 03-25 14:17 (-223) |
| RD5 | 서산영덕선 동상주IC~영덕IC, closure 'from 18:00' (outlet unidentified) | 03-25 18:00 | UNIDENTIFIED  (snippet; 2026-11-18T10:41) | 03-25 17:00 | route 30: all in-grid cells | 03-25 17:00 (closed at issue: error ≤ -60) | 03-25 17:00 (closed at issue: error ≤ -60) | 03-25 17:00 (closed at issue: error ≤ -60) | 03-25 17:00 (closed at issue: error ≤ -60) | 03-25 17:00 (closed at issue: error ≤ -60) | 03-25 17:00 (closed at issue: error ≤ -60) | 03-23 03:23 (-3757) | 03-24 16:25 (-1534) |
| RD6 | 서산영덕선 동상주IC~영덕IC both ways, closure | 03-25 22:00 | 한국경제 (hankyung.com), apparently Yonhap copy (Yonhap photo caption) <https://www.hankyung.com/article/2025032583907> (snippet; 2026-11-18T10:39) | 03-25 21:00 | route 30: all in-grid cells | 03-25 21:00 (closed at issue: error ≤ -60) | 03-25 21:00 (closed at issue: error ≤ -60) | 03-25 21:00 (closed at issue: error ≤ -60) | 03-25 21:00 (closed at issue: error ≤ -60) | 03-25 21:00 (closed at issue: error ≤ -60) | 03-25 21:00 (closed at issue: error ≤ -60) | 03-23 03:23 (-3997) | 03-24 16:25 (-1774) |
| RD7 | 중앙선 의성IC~풍기IC both ways, closure | 03-25 22:00 | 한국경제 (hankyung.com), apparently Yonhap copy (Yonhap photo caption) <https://www.hankyung.com/article/2025032583907> (snippet; 2026-11-18T10:39) | 03-25 21:00 | route 55: all in-grid cells | 03-25 21:00 (closed at issue: error ≤ -60) | 03-25 21:00 (closed at issue: error ≤ -60) | 03-25 21:00 (closed at issue: error ≤ -60) | 03-25 21:00 (closed at issue: error ≤ -60) | 03-25 21:00 (closed at issue: error ≤ -60) | 03-25 21:00 (closed at issue: error ≤ -60) | 03-25 01:28 (-1232) | 03-25 14:17 (-463) |
| RD8 | 중앙선 의성IC~예천IC both ways, closure 'from 07:55' | 03-26 07:55 | 뉴시스 (newsis), '중앙고속도로 의성IC~예천IC 양방향 전면 통제' <https://mobile.newsis.com/view/NISX20250326_0003114647> (snippet; 2026-11-18T10:42) | 03-26 00:00 | route 55: all in-grid cells | 03-26 00:00 (closed at issue: error ≤ -475) | 03-26 00:00 (closed at issue: error ≤ -475) | 03-26 00:00 (closed at issue: error ≤ -475) | 03-26 00:00 (closed at issue: error ≤ -475) | 03-26 00:00 (closed at issue: error ≤ -475) | 03-26 00:00 (closed at issue: error ≤ -475) | 03-25 01:28 (-1827) | 03-25 14:17 (-1058) |
| RD9 | 지방도 911 지품면 황장리~석보면 화매리, control (time of the county text) | 03-25 19:09 | 아시아경제 English edition (asiae.co.kr/en), 'Mega Wildfire Spreads to Yeongyang and Yeongdeok.. <https://www.asiae.co.kr/en/article/2025032520253844170> (snippet; 2026-11-18T10:43) | 03-25 18:00 | shortest path 황장리→화매리, 620 edges; share on route 34 0.15, 911 0.82 | 03-25 19:29 (+20) | 03-25 18:16 (-52) | 03-26 00:37 (+329) | 03-25 18:00 (closed at issue: error ≤ -69) | 03-25 19:18 (+10) | 03-25 19:18 (+10) | 03-25 18:02 (-66) | 03-26 01:53 (404) |
| RD10 | 황장재 통행제한 (CBS time) | 03-25 18:25 | 뉴스로 (영덕군 조치사항 log, one outlet) <https://www.newsro.kr/articles/832886> (full page; 2026-11-16 (page) | 03-25 17:00 | route-34 cells in 지품면 west of 황장리 (284 edges) | MISS: not closed by 03-26 01:00 | 03-25 18:14 (-11) | MISS: not closed by 03-26 01:00 | 03-25 17:52 (-33) | 03-25 23:22 (+297) | 03-25 23:22 (+297) | 03-25 18:00 (-25) | 03-26 01:53 (448) |
| RD11 | 국도 34 (구미~황장) 교통 통제 | 03-25 18:58 | 뉴스로 (영덕군 조치사항 log, one outlet) <https://www.newsro.kr/articles/832886> (full page; 2026-11-16 (page) | 03-25 17:00 | shortest path 구미리→황장리, 1115 edges; share on route 34 0.71, 911 0.0 | MISS: not closed by 03-26 01:00 | 03-25 18:26 (-31) | MISS: not closed by 03-26 01:00 | 03-25 18:04 (-53) | 03-26 00:51 (+353) | 03-26 00:51 (+353) | 03-25 18:02 (-56) | 03-26 01:44 (406) |
| RD12 | 지품면 도계 → 영양 방향 도로통제 | 03-25 19:04 | 뉴스로 (영덕군 조치사항 log, one outlet) <https://www.newsro.kr/articles/832886> (full page; 2026-11-16 (page) | 03-25 18:00 | shortest path 도계리→화매리, 1444 edges; share on route 34 0.42, 911 0.35 | 03-25 19:33 (+30) | 03-25 18:17 (-47) | 03-26 00:56 (+353) | 03-25 18:00 (closed at issue: error ≤ -64) | 03-25 19:22 (+19) | 03-25 19:22 (+19) | 03-25 18:02 (-62) | 03-26 01:45 (402) |
| RD13 | 국도 7 송라면 지경삼거리 → 영덕 방향 교통 통제 | 03-25 21:58 | 뉴스로 (영덕군 조치사항 log, one outlet) <https://www.newsro.kr/articles/832886> (full page; 2026-11-16 (page) | – | NOT COMPARED: outside model domain (포항 송라면, south of the 영덕 grid) |  |  |  |  |  |  | – | – |
| VA1 | 매정리: fire in the village, one resident's account (20:30 + 10 min, derived) | 03-25 20:40 | 한국일보 2025-03-27, https://www.hankookilbo.com/news/article/A2025032714350000238  (snippet; 2026-11-16 (SOUR) | 03-25 19:00 | 1 | MISS: not reached by 03-26 03:00 | 03-25 20:38 (-2) | MISS: not reached by 03-26 03:00 | 03-25 20:16 (-24) | MISS: not reached by 03-26 03:00 | MISS: not reached by 03-26 03:00 | – | – |
| VA2 | 화매리: '화염이 마을 가장자리까지' ~18:00 | 03-25 18:00 | 매일신문 2025-03-26, https://www.imaeil.com/page/view/2025032616432400355  (snippet; 2026-11-16 (SOUR) | 03-25 17:00 | 1 | MISS: not reached by 03-26 01:00 | 03-25 18:42 (+43) | MISS: not reached by 03-26 01:00 | 03-25 18:20 (+21) | MISS: not reached by 03-26 01:00 | MISS: not reached by 03-26 01:00 | – | – |
| VA3 | 강구리: 면-level: fire ~30 min after the 00:07 text (derived) | 03-26 00:37 | 경향신문 2025-03-26, https://www.khan.co.kr/article/202503261311001  (snippet; 2026-11-16 (SOUR) | 03-25 23:00 | 1 | 03-25 23:09 (-88) | 03-25 23:01 (-95) | 03-25 23:40 (-57) | 03-25 23:00 (-97) | 03-25 23:26 (-71) | 03-25 23:14 (-82) | – | – |

Notes:
* "closed at issue (error ≤ bound)": the model already had the road closed at the issue hour, so the error is at most
  issue − recorded.
* Reconstruction: the first time the hotspot-disc fire area (no spread) touches the road.
* Choi TOA: the earliest kriged arrival on those cells (the M family's input).
* MISS: not closed (or not reached) by the end of the 8 h horizon.

**Error summary, as measured** (a median is given only where n ≥ 3 compared):

| arm | compared | MISS | closed at issue | not compared | median error (min) | \|error\| ≤ 30 / ≤ 60 min |
|---|---|---|---|---|---|---|
| MEASURED | 2 (+20, +30) | 2 (RD10, RD11) | 8 | 1 (RD13, outside domain) | – (n < 3) | – |
| RUNNING | 4 | 0 | 8 | 1 | −39 (range −52 … −11) | 1 / 4 of 4 |
| ORDINARY | 2 (+329, +353) | 2 | 8 | 1 | – | – |
| WORST | 2 (−33, −53) | 0 | 10 | 1 | – | – |
| MEASURED_GUST_KMA | 4 | 0 | 8 | 1 | +158 (+10, +19, +297, +353) | 2 / 2 of 4 |
| MEASURED_GUST † | 4 | 0 | 8 | 1 | +158 (same values) | 2 / 2 of 4 |

**Reading, as measured:**
* **Expressways (RD1–RD8):** every arm has every section closed at the issue hour.
  * Under the frozen location rule, a section closes at the first cut anywhere on the route inside the grid. The known
    fire area (2 km discs around hotspots) first touches route 30 on 23 Mar 03:23 KST and route 55 on 25 Mar 01:28
    KST.
  * Those are 15–67 h before the recorded closures. These comparisons say only that the model would have treated
    these routes as cut well before they were reported closed. They do not test closure timing.
* **The four 영덕 local roads (RD9–RD12):**
  * MEASURED: two comparisons late (+20, +30 min), two misses.
  * RUNNING: 11–52 min early in all four.
  * The hotspot reconstruction alone is 25–66 min early.
* **Village accounts (VA1–VA3, single-source, REPORTED):**
  * MEASURED misses 매정리 and 화매리, and is 88 min early at 강구리 (a 면-level account).
  * RUNNING is −2, +43 and −95 min.

### 5.2 Evacuation orders per town

*Model output on reconstructed inputs. Not what happened to people.* Records are REPORTED.

| id | order | recorded (KST, 2025) | source (access) | issue used | places | MEASURED: steps; states; median T_road; order − median T_road (min) | RUNNING: same |
|---|---|---|---|---|---|---|---|
| EV1 | 안동시 어담리, 금계리, 인금리 | 03-25 15:31 | 머니투데이 <https://www.mt.co.kr/policy/2025/03/25/2025032516313321381> (snippet) | 03-25 15:00 | 2 | LEAVE_NOW 1, NONE 1; CUT 2; 03-25 18:13; -163 | LEAVE_NOW 2; CUT 2; 03-25 15:18; 12 |
| EV2 | 의성군 단촌면 | 03-25 16:14 | 뉴스타파 <https://newstapa.org/article/Z7eDJ> (snippet) | 03-25 16:00 | 9 | LEAVE_NOW 9; INSIDE 8, NO_WINDOW 1; –; – | LEAVE_NOW 9; INSIDE 8, NO_WINDOW 1; –; – |
| EV3 | 영덕군 지품면 | 03-25 16:30 | 대구MBC <https://dgmbc.com/NewsArticle/628364> (snippet) | 03-25 16:00 | 19 | NONE 19; NOT_CUT_WITHIN_H 19; –; – | LEAVE_NOW 19; CUT 19; 03-25 19:25; -176 |
| EV4 | 안동시 하회리 | 03-25 16:55 | 세계일보 <https://www.segye.com/newsView/20250325516986> (snippet) | 03-25 16:00 | 0 | –; –; –; – | –; –; –; – |
| EV5 | 안동시 (whole county) | 03-25 17:00 | 아시아경제 (English edition); YTN <https://www.asiae.co.kr/en/article/2025032614215723715> (snippet) | 03-25 17:00 | 37 | LEAVE_NOW 37; CUT 1, NO_WINDOW 5, INSIDE 31; 03-25 17:28; -28 | LEAVE_NOW 37; CUT 1, NO_WINDOW 5, INSIDE 31; 03-25 17:02; -2 |
| EV6 | 청송군 (whole county) | 03-25 17:44 | 쿠키뉴스 <https://www.kukinews.com/article/view/kuk202503250280> (snippet) | 03-25 17:00 | 3 | NONE 3; NOT_CUT_WITHIN_H 3; –; – | LEAVE_NOW 3; CUT 3; 03-25 18:17; -33 |
| EV7 | 영덕군 지품면, 달산면 | 03-25 18:00 | 뉴스로 (영덕군 조치사항 log, one outlet) <https://www.newsro.kr/articles/832886> (full page) | 03-25 18:00 | 30 | LEAVE_NOW 10, NONE 15, PREPARE 5; CUT 15, NOT_CUT_WITHIN_H 15; 03-25 21:45; -225 | LEAVE_NOW 30; CUT 30; 03-25 19:09; -69 |
| EV8 | 영양군 석보면 | 03-25 18:47 | Korean outlet not pinned (snippet surfaced am <https://kbmaeil.com/article/202503250913432> (snippet) | 03-25 18:00 | 5 | PREPARE 1, LEAVE_NOW 4; CUT 5; 03-25 20:27; -101 | LEAVE_NOW 5; CUT 5; 03-25 18:23; 23 |
| EV9 | 영덕군 옥류리 | 03-25 18:52 | 뉴스로 (영덕군 조치사항 log, one outlet) <https://www.newsro.kr/articles/832886> (full page) | 03-25 18:00 | 1 | NONE 1; NOT_CUT_WITHIN_H 1; –; – | LEAVE_NOW 1; CUT 1; 03-25 19:24; -32 |
| EV10 | 영덕군 대리 | 03-25 19:18 | 뉴스로 (영덕군 조치사항 log, one outlet) <https://www.newsro.kr/articles/832886> (full page) | 03-25 19:00 | 1 | LEAVE_NOW 1; CUT 1; 03-25 19:08; 10 | LEAVE_NOW 1; NO_WINDOW 1; –; – |
| EV11 | 영덕군 (whole county) | 03-25 19:30 | 뉴스로 (영덕군 조치사항 log, one outlet) <https://www.newsro.kr/articles/832886> (full page) | 03-25 19:00 | 82 | NONE 36, PREPARE 14, LEAVE_NOW 32; NOT_CUT_WITHIN_H 37, CUT 36, INSIDE 9; 03-25 22:47; -198 | LEAVE_NOW 82; CUT 72, INSIDE 9, NO_WINDOW 1; 03-25 20:13; -43 |
| EV12 | 영덕군 창수면 | 03-25 19:40 | 뉴스로 (영덕군 조치사항 log, one outlet) <https://www.newsro.kr/articles/832886> (full page) | 03-25 19:00 | 1 | LEAVE_NOW 1; CUT 1; 03-25 22:05; -145 | LEAVE_NOW 1; CUT 1; 03-25 19:33; 6 |
| EV13 | 영덕군 (whole county) | 03-25 21:00 | 뉴스로 (영덕군 조치사항 log, one outlet) <https://www.newsro.kr/articles/832886> (full page) | 03-25 21:00 | 82 | LEAVE_NOW 82; CUT 49, INSIDE 32, NO_WINDOW 1; 03-25 23:09; -130 | LEAVE_NOW 82; CUT 46, INSIDE 32, NO_WINDOW 4; 03-25 21:23; -24 |

Each cell shows, at the issue hour used: the model's steps; its states; the median T_road over CUT places; and the
order time minus that median T_road (negative = the order came before the model's last road closed).

* 하회리 (EV4) is not a planner place.
* 18 further order records were excluded, with reasons (no clock time, 24 or 26 March, duplicates, not an order); the
  list is in `validation.json` → `evacuation_excluded`.
* Excluded road records: R2 (a duplicate with a conflicting end point), R6 (no time), R8 (a reopening), R10 (a status
  snapshot) and a 24 March record.

### 5.3 Burned area (Sentinel-2 dNBR) versus model "reached"

**Map:**
* Sentinel-2 L2A from the AWS open bucket `sentinel-cogs`, read 2026-11-18 10:46–10:53 UTC.
* 52SEF (영덕 grid): 2025-03-14 → 2025-04-08. 52SDF (의성·안동 grid): 2025-03-14 → 2025-04-28.
* Burned pixel: dNBR ≥ 0.10 (primary) or ≥ 0.27 (sensitivity). A cell (375 m) is burned if ≥ 25 % of its valid pixels
  are burned.

**Burned area inside the routing grids:**

| grid | dNBR ≥ 0.10 | dNBR ≥ 0.27 | cells burned / unburned / not assessable (0.10) |
|---|---|---|---|
| 영덕 | 211.7 km² | 101.1 km² | 1,854 / 2,580 / 323 |
| 의성·안동 | 236.0 km² | 174.1 km² | 2,147 / 2,302 / 296 |

**Plausibility only:**
* The 산림청 provisional damage area (2025-04-18, REPORTED via 경향신문, 농민신문 and 데일리한국; the korea.kr release
  itself was not read) is 99,289 ha over 의성, 안동, 청송, 영양 and 영덕 (28,853 / 26,709 / 20,655 / 6,864 / 16,208 ha).
* The two grids cover only part of those counties: 448 km² = 44,767 ha at dNBR ≥ 0.10, inside the grids only.
* GWIS via GDACS gives 28,203 ha (last update 2025-04-01).

**No published burned-area map could be downloaded.** NASA Earth Observatory offers images only; OPERA DIST-ALERT and
MCD64A1 need an Earthdata login; no Copernicus EMS or Charter activation was found. So the Sentinel-2 map above is the
only map.

*Model output on reconstructed inputs. Not what happened to people.*

| comparison | hit | miss | false alarm | correct negative | not assessable |
|---|---|---|---|---|---|
| places: R/MEASURED/8h/dNBR>=0.1 | 55 | 0 | 117 | 0 | 2 |
| places: R/RUNNING/8h/dNBR>=0.1 | 55 | 0 | 117 | 0 | 2 |
| places: R/ORDINARY/8h/dNBR>=0.1 | 55 | 0 | 108 | 9 | 2 |
| places: R/WORST/8h/dNBR>=0.1 | 55 | 0 | 117 | 0 | 2 |
| places: R/MEASURED_GUST_KMA/8h/dNBR>=0.1 | 55 | 0 | 117 | 0 | 2 |
| places: R/MEASURED_GUST/8h/dNBR>=0.1 | 55 | 0 | 117 | 0 | 2 |
| places: M/kriged_mean/8h/dNBR>=0.1 | 53 | 2 | 54 | 63 | 2 |
| places: M/firms_early/8h/dNBR>=0.1 | 53 | 2 | 55 | 62 | 2 |
| places: M/envelope/8h/dNBR>=0.1 | 53 | 2 | 55 | 62 | 2 |
| places: R/MEASURED/8h/dNBR>=0.27 | 28 | 0 | 144 | 0 | 2 |
| places: R/RUNNING/8h/dNBR>=0.27 | 28 | 0 | 144 | 0 | 2 |
| places: R/ORDINARY/8h/dNBR>=0.27 | 28 | 0 | 135 | 9 | 2 |
| places: R/WORST/8h/dNBR>=0.27 | 28 | 0 | 144 | 0 | 2 |
| places: R/MEASURED_GUST_KMA/8h/dNBR>=0.27 | 28 | 0 | 144 | 0 | 2 |
| places: R/MEASURED_GUST/8h/dNBR>=0.27 | 28 | 0 | 144 | 0 | 2 |
| places: M/kriged_mean/8h/dNBR>=0.27 | 27 | 1 | 80 | 64 | 2 |
| places: M/firms_early/8h/dNBR>=0.27 | 27 | 1 | 81 | 63 | 2 |
| places: M/envelope/8h/dNBR>=0.27 | 27 | 1 | 81 | 63 | 2 |
| cells: R/MEASURED/8h@24:00KST/dNBR>=0.1 | 4001 | 0 | 4882 | 0 | 619 |
| cells: R/RUNNING/8h@24:00KST/dNBR>=0.1 | 4001 | 0 | 4882 | 0 | 619 |
| cells: R/ORDINARY/8h@24:00KST/dNBR>=0.1 | 3994 | 7 | 4396 | 486 | 619 |
| cells: R/WORST/8h@24:00KST/dNBR>=0.1 | 4001 | 0 | 4882 | 0 | 619 |
| cells: R/MEASURED_GUST_KMA/8h@24:00KST/dNBR>=0.1 | 3996 | 5 | 4438 | 444 | 619 |
| cells: R/MEASURED_GUST/8h@24:00KST/dNBR>=0.1 | 4000 | 1 | 4817 | 65 | 619 |
| cells: reconstruction (all detections to 26 Mar 02:58 KST)/dNBR>=0.1 | 3988 | 13 | 3823 | 1059 | 619 |
| cells: R/MEASURED/8h@24:00KST/dNBR>=0.27 | 2871 | 0 | 6012 | 0 | 619 |
| cells: R/RUNNING/8h@24:00KST/dNBR>=0.27 | 2871 | 0 | 6012 | 0 | 619 |
| cells: R/ORDINARY/8h@24:00KST/dNBR>=0.27 | 2871 | 0 | 5519 | 493 | 619 |
| cells: R/WORST/8h@24:00KST/dNBR>=0.27 | 2871 | 0 | 6012 | 0 | 619 |
| cells: R/MEASURED_GUST_KMA/8h@24:00KST/dNBR>=0.27 | 2871 | 0 | 5563 | 449 | 619 |
| cells: R/MEASURED_GUST/8h@24:00KST/dNBR>=0.27 | 2871 | 0 | 5946 | 66 | 619 |
| cells: reconstruction (all detections to 26 Mar 02:58 KST)/dNBR>=0.27 | 2871 | 0 | 4940 | 1072 | 619 |

hit = model reached & burned; miss = not reached & burned; false alarm = reached & not burned; correct negative = neither. Places: 174 entry cells. Cells: all cells of both grids.

**Reading, as measured:**
* **Places:**
  * Every arm of R except ORDINARY "reaches" all 172 assessable places, either INSIDE or with T_village within 8 h at
    some issue hour. The places include all 55 burned ones, but 117 places (0.10) or 144 (0.27) whose entry cell is
    not burned are reached too: no miss, many false alarms. ORDINARY leaves 9 unburned places unreached.
  * M is more selective: 53 hits, 2 misses, 54 false alarms and 63 correct negatives (kriged_mean, 0.10).
* **Cells** (R, 24:00 issue, closed by T + 8 h): MEASURED, RUNNING and WORST close every assessable cell of both grids
  (8,883).
* **The over-coverage is already in the fire input.** The hotspot reconstruction with no spread at all (every detection
  up to 26 Mar 02:58 KST) marks 7,811 cells, of which 3,823 are unburned at 0.10.
* **This is not a test of arrival times.** A model closure means "fire within reach", not "this cell burns", and the
  post-fire scenes come 2–5 weeks later.

**Map limits:**
* The 52SDF post-fire scene is late April, so vegetation green-up and cropland change can show as dNBR; some
  southern 의성·안동 patches may be such change.
* 0.10 is a low threshold. At 0.27 the mapped area roughly halves in 영덕.

## 6 Limits

* **The inputs are reconstructions:**
  * the fire comes from satellite hotspots with 2 km discs (AHI) and FIRMS;
  * the spread comes from stand-in or measured-rate arms with isotropic reach and no fuel, wind or slope;
  * the roads come from OSM, with speeds capped at 40 km/h;
  * all of it is inside two 375 m routing grids.
* **The gap is between two closures under the same rule.** T_village is the closure of the village's own cell under
  the arm's rule ("fire within reach"), not a flame-arrival time.
* **Family M's arrival rasters were rebuilt here** from committed inputs, not read from the F-DYN packets. The envelope
  = firms_early is an assumed reading.
* **The government reading is ours** (§3.1). It uses the model's own reach time, not the Korea Forest Service estimate,
  and assumes the designation acts at once.
* **Records are REPORTED and mostly snippet-level.** None comes from an official archive. Record times conflict (§5).
  Expressway records can only be compared at section level.
* **Location rules for some records are approximations:**
  * 황장재 and 도계→영양 are located by path, not coordinates;
  * 안동 and 의성 towns come from web-search lists;
  * 7 of 174 places got no town.

## 7 Files

| file | what |
|---|---|
| `PROTOCOL.md` | frozen protocol + 2 amendments |
| `RESULTS.md` | this file (built from `RESULTS.template.md` by `build_results.py`) |
| `numbers.json` | every headline number, all configurations, place-level summaries, checks |
| `per_unit.csv.gz` | every place-hour row of R and M with windows (KST), per-shelter windows, state, gap or bound, binding |
| `gap_per_place.png` | the one figure (primary configuration) |
| `validation_table.csv` | the one validation table (roads, village accounts, evacuation orders; all arms) |
| `validation.json` | validation detail incl. burned-area 2×2 tables, exclusions, place → town |
| `ronchi_tests.json` | Ronchi tests: geometry, expected, got, verdict |
| `repro_check.json`, `runs_sha256.txt` | reproduction check; SHA-256 of raw run files and intermediates |
| `records_raw/` | records as found, with source, access level and retrieval time |
| scripts | `replay_gaps.py`, `multihour.py`, `burned_area.py`, `aggregate.py`, `validation.py`, `figure.py`, `ronchi_tests.py`, `repro_check.py`, `build_results.py` |

**How to reproduce (paths relative to the repository root; `$S` = a scratch directory):**
1. `cd research/kcf-replay && python3 replay.py fire_discs.json $S/runs --workers 4`
2. `python3 research/kcf-roadcut/replay_gaps.py $S/runs $S/R.json`
3. `python3 research/kcf-roadcut/multihour.py $S/multihour.json`
4. `python3 research/kcf-roadcut/burned_area.py $S/s2 $S/burned_area.json`
5. `aggregate.py`, `validation.py` and `figure.py` as in their docstrings.
