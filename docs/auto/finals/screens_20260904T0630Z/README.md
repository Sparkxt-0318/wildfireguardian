# 결선 화면 v2 — 확인 스크린샷 (2026-09-04, WFG-017)

`web/finals.html` at commit `a562045`, opened from `file://` in headless Chromium
(1600x1000, `/opt/pw-browsers/chromium-1194`), intro dismissed with Esc.

These are a **record of the lap looking at what it shipped**, not a test. The
automated smoke of this screen is backlog row WFG-009.

| file | what |
|---|---|
| `1_live.png` | LIVE (act 1) |
| `2_system.png` | SYSTEM |
| `3_evidence.png` | EVIDENCE, top of the grid |
| `4_reliability.png` | RELIABILITY, top of the grid |
| `5_card_operating.png` | new card: 운영점 |
| `6_card_detection.png` | new card: 탐지 바닥 |
| `7_card_horizon.png` | new card: 240분 지평 |
| `8_card_refuge.png` | new card: 대피 지점 배치 |
| `9_card_reconciliation.png` | new RELIABILITY card: 제출본과 정본 |

Two requests fail when the page loads: `intro-forest-loop.mp4` and
`ambient-documentary.mp3`. Both are the git-ignored demo media in
`web/demo-media/`, which the screen is designed to work without
(`tests/test_finals_screen.py::test_media_is_optional_by_construction`). The
vendored fonts under `web/assets/fonts/` all load.
