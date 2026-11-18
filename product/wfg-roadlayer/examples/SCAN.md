# Every hour of the 25 March 2025 replay

모델 출력 · 참고용 · 명령 아님 / Model output · advisory · not an order.

Output of `python3 examples/scan_replay_hours.py --workers 4` (about 25 minutes on 4 cores): the tool run on each of the
13 replay hours (12:00–24:00 KST) for both regions, with the fire-arrival raster that `build_example_raster.py` builds
for that hour (research/kcf-replay, MEASURED arm, 8 h horizon), as a replay (`--as-of` = issue time). Counts are
villages and care facilities with a number (refused places excluded: 2 in 의성·안동, 1 in 영덕). "Largest gap" is
the most minutes between the last road out being cut and the fire reaching the village.

The 349 place-hours with a road cut inside the horizon are the 349 of `research/kcf-replay/RESULTS.md` §5
(MEASURED / 8 h). The flag ("road cut before 즉시 실행") is "yes" once, at 동변리 12:00, which is why the worked example
uses 12:00 for 의성·안동. "Cannot tell" means the fire does not reach the village inside the horizon and less than 5 h of
horizon remain after the cut.

| issue KST | region | cut at issue | cut inside 8 h | not cut | flag yes | flag cannot tell | largest gap (min, village) |
|---|---|---:|---:|---:|---:|---:|---|
| 12:00 | uiseong_andong_2025 | 34 | 16 | 34 | 1 | 1 | 326, Dongbyeon-ri (동변리) |
| 13:00 | uiseong_andong_2025 | 36 | 17 | 31 | 0 | 1 | 193, Changgil-ri (창길리) |
| 14:00 | uiseong_andong_2025 | 39 | 14 | 31 | 0 | 1 | 199, Dongbyeon-ri (동변리) |
| 15:00 | uiseong_andong_2025 | 44 | 28 | 12 | 0 | 3 | 101, Gukgok-ri (국곡리) |
| 16:00 | uiseong_andong_2025 | 55 | 29 | 0 | 0 | 0 | 115, Haa-ri (하아리) |
| 17:00 | uiseong_andong_2025 | 80 | 4 | 0 | 0 | 0 | 100, Cheonjeon-ri (천전리) |
| 18:00 | uiseong_andong_2025 | 82 | 2 | 0 | 0 | 0 | 8, Bunto-ri (분토리) |
| 19:00 | uiseong_andong_2025 | 82 | 2 | 0 | 0 | 0 | 8, Bunto-ri (분토리) |
| 20:00 | uiseong_andong_2025 | 82 | 2 | 0 | 0 | 0 | 8, Bunto-ri (분토리) |
| 21:00 | uiseong_andong_2025 | 82 | 2 | 0 | 0 | 0 | 8, Bunto-ri (분토리) |
| 22:00 | uiseong_andong_2025 | 82 | 2 | 0 | 0 | 0 | 8, Bunto-ri (분토리) |
| 23:00 | uiseong_andong_2025 | 82 | 2 | 0 | 0 | 0 | 8, Bunto-ri (분토리) |
| 24:00 | uiseong_andong_2025 | 82 | 2 | 0 | 0 | 0 | 8, Bunto-ri (분토리) |
| 12:00 | yeongdeok_2025 | 0 | 0 | 90 | 0 | 0 | – |
| 13:00 | yeongdeok_2025 | 0 | 0 | 90 | 0 | 0 | – |
| 14:00 | yeongdeok_2025 | 0 | 0 | 90 | 0 | 0 | – |
| 15:00 | yeongdeok_2025 | 0 | 0 | 90 | 0 | 0 | – |
| 16:00 | yeongdeok_2025 | 0 | 0 | 90 | 0 | 0 | – |
| 17:00 | yeongdeok_2025 | 0 | 0 | 90 | 0 | 0 | – |
| 18:00 | yeongdeok_2025 | 0 | 22 | 68 | 0 | 0 | 159, Samui-ri (삼의리) |
| 19:00 | yeongdeok_2025 | 14 | 39 | 37 | 0 | 0 | 225, Naeryong-ri (내룡리) |
| 20:00 | yeongdeok_2025 | 18 | 40 | 32 | 0 | 0 | 203, Naeryong-ri (내룡리) |
| 21:00 | yeongdeok_2025 | 38 | 52 | 0 | 0 | 0 | 172, Naeryong-ri (내룡리) |
| 22:00 | yeongdeok_2025 | 63 | 27 | 0 | 0 | 0 | 172, Naeryong-ri (내룡리) |
| 23:00 | yeongdeok_2025 | 63 | 27 | 0 | 0 | 0 | 172, Naeryong-ri (내룡리) |
| 24:00 | yeongdeok_2025 | 70 | 20 | 0 | 0 | 0 | 172, Naeryong-ri (내룡리) |

place-hours: cut at issue 1128, cut inside 8 h 349, not cut 785; flag yes 1, cannot tell 6
