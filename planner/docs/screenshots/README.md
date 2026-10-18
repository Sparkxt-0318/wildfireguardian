# 화면 스크린샷 (Screenshots)

Re-shot 2026-10-18 (KST) from the **booth cache** (`planner/cache/`), which was computed on the evaluated host (Apple M5 Pro, native macOS, 13 API workers, real Route-Check API v1.8.0) on 2026-10-18. No API was connected while shooting (`오프라인 · 캐시 사용`), so every result on screen comes from that cache. Each screen exists at 1440x900 and 1920x1080 (`NN-<state>-<WxH>.png`), captured with `scripts/screenshots.mjs` (state list and deep links in `manifest.json`).

| File | What it shows | Data source |
|---|---|---|
| 01-main-uiseong | 의성·안동, input 2025-03-23 10:00 KST, nothing selected (85 checked · 1 model no-route · 2 unresolved origins) | booth cache |
| 02-main-yeongdeok | 영덕, first recorded input | booth cache |
| 03-origin-route | Recorded mission FL2 origin: deadline 18:20 on a checked route (green), dashed travel-only comparison, departure timeline | booth cache |
| 04-english | English UI | booth cache |
| 05-about | About panel | booth cache |
| 06-plan-sheet | Plan-sheet preview (one A4 page per origin) | booth cache |
| 07-export | Export dialog (GeoJSON / KML / CSV) | booth cache |
| 08-drawn-zones | Drawn-zone mode with the recorded-footprint preset; drawn zones are always evaluated live, so with no API the screen says so and computes nothing | none (zones are user assumptions) |

`09-live-recompute` is not shot here: the script triggers computation only against the MOCK, never a real API.

`mock/` keeps the earlier set shot against the MOCK server (recorded results only, MOCK badge visible), including the live-recompute, drawn-zone assumptions and offline-empty states.
