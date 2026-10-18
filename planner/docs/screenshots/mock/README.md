# MOCK 화면 스크린샷 (earlier set)

Re-shot 2026-10-18 (KST) against the **MOCK** server (`http://127.0.0.1:8765/v1`, recorded results only; the MOCK badge is visible in every image). Each screen exists at 1440x900 and 1920x1080 (`NN-<state>-<WxH>.png`).

| File | What it shows | Data source | Date |
|---|---|---|---|
| 01-main-uiseong | 의성·안동, recorded scenario 2025-03-24 18:00 KST, nothing selected | MOCK | 2026-10-18 |
| 02-origin-fl2-route | Recorded mission FL2 origin: checked route (green) + dashed travel-only comparison + timeline | MOCK | 2026-10-18 |
| 03-village-entry | A village (감계리) selected, showing the 진입 지점 distance (197 m); status 미확인 | MOCK | 2026-10-18 |
| 04-yeongdeok-fd1-no-route | 영덕 recorded mission FD1 selected (모델상 경로 없음 at 04:00) | MOCK | 2026-10-18 |
| 05-english | English UI (FL2 selected) | MOCK | 2026-10-18 |
| 06-about | About panel | MOCK | 2026-10-18 |
| 07-plansheet | Plan-sheet preview (one A4 page per origin, FL2) | MOCK | 2026-10-18 |
| 07b-plansheet-printed-page-A4 | One page of the printed PDF (FL2, A4; page 87 of 87 of the all-origins PDF), rasterised at 110 dpi (one size) | MOCK | 2026-10-18 |
| 08-export | Export dialog (GeoJSON / KML / CSV) | MOCK | 2026-10-18 |
| 09-drawn-zones-preset | Drawn-zone mode, recorded-footprint preset, 5 h / 8 h zones, Set/Go tags in the list | MOCK (zones are user assumptions) | 2026-10-18 |
| 10-drawn-assumptions | Drawn-zone mode with the API assumptions panel (MOCK) | MOCK | 2026-10-18 |
| 11-live-recompute | Live recompute in progress (0/6 checks) | MOCK | 2026-10-18 |
| 12-offline | API unreachable (requests blocked); no cache loaded, so the honest empty state | none | 2026-10-18 |

**Note.** These images use the MOCK server, which replays recorded results only. Most OSM villages therefore show **미확인 (unresolved)**, never safe, until the booth cache computed on the M5 Pro is loaded. Linux/MOCK output is not the booth cache.
