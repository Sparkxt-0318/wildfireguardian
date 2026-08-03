# PHASE 8 — the operator screen

Round-3 PHASE 8. Written 2026-08-03.

`scripts/build_operator_screen.py` → `demo/operator_screen.html` ·
`tests/test_operator_screen.py` (26 tests)

```bash
python scripts/build_operator_screen.py          # rebuild from the latest run
open demo/operator_screen.html                   # or double-click it
```

---

## 0. What it is

One **self-contained HTML file**, opened from `file://`, that replays a PHASE-6
run in the order a judge needs to follow it:

> 탐지 → 위험면 → 경로 → 출동 목록

Nothing is fetched, nothing is stored, nothing is computed. Every number on the
screen came out of `run_live_detection.py` and is inlined at build time.

| | |
|---|---|
| size | ~125 KB, one file |
| network requests | **1** — the file itself |
| console errors | 0 |
| viewport | 1920×1080, **no scroll** (verified: `scrollHeight` 1080 = `innerHeight`) |
| full replay at 60× | **12 minutes** (720-minute prediction horizon) |

---

## 1. Layout

```
┌───────────────────────────────────────────────┬──────────────────┐
│  header: 재생 모드 · 클록 · 슬라이스 · 배속/일시정지          │                  │
├───────────────────────────────────────────────┤   출동 목록       │
│                                               │   44행           │
│   지도 (2/3, 1279 px)                          │   # · 위치 ·     │
│    · 위험 확률장, 이산 4밴드 + 배경             │   남은 시간 ·     │
│    · 화점 (탐지 시각에 등장)                    │   도달 가능      │
│    · 출발지 458개, 3색                          │  (1/3, 641 px)   │
│    · 경로 2개 (주민 대피 · 미래 인지)            │                  │
│    · 보행망 범위 (점선)                          │                  │
├───────────────────────────────────────────────┴──────────────────┤
│ 화점 탐지 · 기상 자료 · 보행망 커버리지 32.6% · 위험면 · 라우팅 소요  │
└──────────────────────────────────────────────────────────────────┘
```

All 44 dispatch rows fit without scrolling: 19.5 px per row, 880 px of table in
a 954 px pane.

---

## 2. The map is drawn, not fetched

**No tiles, no basemap, no CDN.** Coordinates are projected to EPSG:5179 at
build time — by `pyproj`, the same transformer the routing used — and written
into the file as SVG. The page does no geodesy; it draws numbers it was handed.

* **Hazard surface** — quantised into **four visible bands** (`0.10–0.30`,
  `0.30–0.50`, `0.50–0.70`, `0.70–1.00`) plus an implicit below-0.10 background,
  and **run-length encoded** by row. The field is sparse — 249 cells reach 0.10
  at t=0, 1,592 at t+720 — so all five slices cost ~40 KB rather than a raster.
  Discrete on purpose: a continuous ramp invites reading a precision the model
  does not have, and a judge who asks "what is that shade?" should get an
  interval. The ramp darkens as it saturates, so the order survives a
  black-and-white projector.
* **Origins** — all **458**, in three colours: 자력 대피 (blue, 414), 구조 필요
  (amber, 42), 도달 불가 (red, 2). Plotting only the 44 that need something would
  read as 44-of-44 instead of 44-of-458.
* **Routes** — two **real polylines** carried out of the run, for a
  `naive_into_FA_safe` origin: the fire-blind route (dashed red) walks into the
  fire, the future-aware route (cyan) does not. That is the project's central
  claim, drawn rather than asserted.
* **Walk-network bbox** — a dashed outline. The fire runs 45 km west; the
  network stops at the box. **This is what 32.6 % coverage looks like**, and
  showing it beats asking a judge to take a footer figure on trust.

---

## 3. The replay

One clock, in **minutes since the hazard field's t=0**. The detections and the
surface are two records of the same fire, so they share an axis rather than
being drawn against two.

| control | |
|---|---|
| **1× / 10× / 60×** | 12 h / 72 min / **12 min** total. Each button's tooltip states its own duration, and the header shows it, so nobody is surprised. |
| **일시정지** | freezes the clock. **Judges ask questions**; the screen has to stop. Resets and speed changes work while paused. |
| **처음부터** | back to the pre-roll, repaints immediately even while paused |

**Pre-roll.** The clock starts at **−25 분**. The field's t=0 *is* the first
overpass, so without a lead-in the screen opens mid-trigger and the
detection → surface → routes → list sequence is never visible. Those 25 minutes
are real and empty — nothing had been detected yet — and the clock says
`탐지 전 N분` rather than pretending otherwise.

**Sequence.** Hotspots appear at the minute they were detected (240 of them
across the window, newest emphasised). At a trigger the panel shows
**「계산 중 … 458개 출발지를 라우팅하고 있습니다」**, then the list fills from the
top, the origins colour in, and the two routes appear.

---

## 4. What is forbidden, and how it is enforced

| forbidden | enforcement |
|---|---|
| map tiles / basemap | no `<img>`, no external URL — asserted |
| external CDN | the only URL in the file is `http://www.w3.org/2000/svg`, an XML namespace identifier, never fetched |
| `localStorage` etc. | `localStorage`, `sessionStorage`, `indexedDB`, `serviceWorker` all absent from executable source — asserted individually |
| live polling | `FIRMS_MAP_KEY`, `api/area`, `firms.modaps`, `setInterval(` all absent. The **string** "FIRMS NRT" must still be present: it names the detection source on the status bar. |
| real computation | the page has no solver. Counts, rows, routes and timings are inlined from `RUN.json` / `viz.json`. |
| figures differing from the committed run | a test compares the screen's counts against `real_roads_real_hazard_canonical.json` — **458 / 414 / 42 / 2**. |

---

## 5. Where the data comes from

`viz.json`, written by the PHASE-6 pipeline into each run directory.

> ⚠ **`viz.json` is a visualisation artifact, deliberately separate from the
> operational ones.** Every sheet, broadcast script and SMS/email draft this
> project produces is **coordinate-free by requirement** — a 이장 navigates by
> place name. A map is nothing but coordinates. Keeping them in different files
> is what lets both rules hold at once. Do not merge `viz.json` into
> `MANIFEST.json`.

It costs no extra computation: both routes are already solved for every origin
and were previously discarded. `--collect-routes N` (default 12) retains the
polylines for N future-aware-only origins.

The dispatch rows carry **place labels only**, never coordinates — the same rule
the paper sheet follows, applied to the screen.

---

## 6. Rebuilding

```bash
python scripts/run_live_detection.py --replay --speed 0 --no-pdf   # ~25 s/trigger
python scripts/build_operator_screen.py
```

`--speed 0` runs the replay as fast as the machine allows, which is what you
want when you only need the artifacts. The screen's own 60× playback is set in
the page, not by the run.

---

## 7. Known limits

1. **Yeongdeok only.** The other two regions have hazard fields and snapshots,
   so extending is a config change plus a run, but their screens have not been
   built or checked.
2. **One route pair is drawn.** Twelve are inlined; the page shows the first.
   Making them selectable is a small change that was not asked for.
3. **1× is 12 hours.** That is the honest mapping of the field's horizon, not a
   defect. Use pause, not 1×, to hold a moment.
4. **The pre-roll is a presentation device.** 25 minutes of "nothing detected
   yet" is true, but it is chosen for legibility rather than derived from
   anything.
