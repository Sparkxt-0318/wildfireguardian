# External data acquisition — status as of 2026-09-14

Supersedes the six-item table in `docs/auto/briefs/DATA_VERIFICATION_REPORT.md` (2026-09-13),
which found all six items missing. Four are now obtained and two remain. Every key lives at
`~/.config/wildfireguardian/*.key` (mode 600) on the author's machine and appears nowhere in
this repository.

| # | item | status | evidence |
|---|---|---|---|
| 1 | KMA API Hub key | **partial** | Key obtained and it authenticates. Every endpoint tried returns `403 활용신청이 필요한 API 입니다` — on apihub each API needs its own 활용신청 after registration. Author must apply per-API (AWS 매분자료, ASOS, 단기예보). |
| 2 | KMA bulk AWS/ASOS, March 2025 | **partial** | Second attempt reached the right month (2025-03-20/21) but returned exactly one day per download, and neither ASOS 시간자료 nor AWS 시간자료 carries 최대순간풍속 — that element belongs to the 일자료 product, not the hourly one. Station numbers ARE confirmed: 영덕 277, 안동 136, 의성 278, 울진 130, all ASOS. |
| 3 | 산악기상관측망 | **done, and it exceeded the spec** | Key approved 2026-09-14. **History confirmed**: 94 경북 stations return real observations for the fire window. 15,792 hourly rows + a minute-resolution night pulled. `docs/mountain_weather_yeongdeok.md`. |
| 4 | 임상도 1:5000 경상북도 | **done** | 2025 edition, EPSG:5179, 771,803 polygons in two shapefiles, all requested attributes present. `data/raw/forest_type_map/MANIFEST.json`. Clip-to-box not yet run. |
| 5 | 산불발생통계 API | **done** | Key approved; call for 2025-03-22..03-31 returns 76 fires including the three 의성 ignitions (52,707.3 / 46,575.2 / 134.24 ha) and 안동 수상. No 영덕 ignition row, exactly as the committed CSV said — 영덕 burned by spread. |
| 6 | 정보공개청구 to 국립산림과학원 | **not filed** | Author's action. The only route to a literal head-to-head against the national system's own issued 확산예측도. |

## What items 1 and 2 still need

**Item 1.** On https://apihub.kma.go.kr, after login, open each API's page and press 활용신청
(AWS 매분자료 is listed as 「K10. 자동기상관측장비(AWS) 매분자료」). The key already held then
works; nothing new to store.

**Item 2.** Two separate corrections, and the second is the one that was misdiagnosed on
2026-09-13:
1. the 자료 tab returns one day per request, so the March window needs either repeated
   requests or the **파일셋** tab (`...selectAsosRltmList.do?pgmNo=36&tabNo=1`);
2. **최대순간풍속 is not an hourly element.** It lives in ASOS **일자료** (daily), with
   최대순간풍속 풍향 and 최대순간풍속 시각 beside it. The hourly download was never going to
   carry it, however the element boxes were set.

⚠ Item 2 is now **less urgent than it was**, because item 3 delivered a denser wind record
than ASOS ever could (94 경북 stations at 10 m against 14 ASOS stations). ASOS 일자료 is still
worth one download for the single headline 최대순간풍속 figure per station per day, which is
the number the agency and the press quote.
