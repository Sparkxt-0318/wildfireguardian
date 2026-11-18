# Overlap: road-structure flags vs earliest replay cut-off

모델 출력 · 참고용 · 명령 아님 / Model output · advisory · not an order

Check: do the places flagged single-exit or dangerous-road coincide with the places where the replay shows the
earliest road cut-off? Counts only.

Replay: research/kcf-replay/per_place.csv, MEASURED arm, 8 h horizon, 13 issue hours 12:00-24:00 KST (the arm the
worked example reproduces). A place's earliest cut-off = the earliest over the hours of: the issue hour when the
state is INSIDE_KNOWN_FIRE_AREA or NO_SAFE_DEPARTURE (cut at or before it), or latest_safe_departure + 1 min when it
is LATEST_SAFE_DEPARTURE. NOT_CUT_WITHIN_H at every hour = no cut-off in the replay.

"Earliest cut-off" places = within each region, the places whose earliest cut-off is at or before the first quartile
(25th percentile, lower value) of the earliest cut-offs of all its checkable places (never-cut places count as
latest). Regions are kept apart because the fire reaches 영덕 six hours after 의성·안동.

| flag | region | places | flagged | earliest cut-off | both | flagged only | earliest only | neither | both if unrelated |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| single_exit | uiseong_andong_2025 | 84 | 58 | 34 | **27** | 31 | 7 | 19 | 23.5 |
| single_exit | yeongdeok_2025 | 90 | 55 | 23 | **19** | 36 | 4 | 31 | 14.1 |
| single_exit | all | 174 | 113 | 57 | **46** | 67 | 11 | 50 | 37.0 |
| dangerous_road | uiseong_andong_2025 | 84 | 2 | 34 | **0** | 2 | 34 | 48 | 0.8 |
| dangerous_road | yeongdeok_2025 | 90 | 3 | 23 | **0** | 3 | 23 | 64 | 0.8 |
| dangerous_road | all | 174 | 5 | 57 | **0** | 5 | 57 | 112 | 1.6 |
| either | uiseong_andong_2025 | 84 | 60 | 34 | **27** | 33 | 7 | 17 | 24.3 |
| either | yeongdeok_2025 | 90 | 58 | 23 | **19** | 39 | 4 | 28 | 14.8 |
| either | all | 174 | 118 | 57 | **46** | 72 | 11 | 45 | 38.7 |

Earliest cut-off = at or before the region's first quartile: uiseong_andong_2025 03-25 12:00, yeongdeok_2025 03-25 20:44 (KST).
