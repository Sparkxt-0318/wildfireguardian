# PHASE 8 — the operator screen

Round-3 PHASE 8. Written 2026-08-03.

`scripts/build_operator_screen.py` → `demo/operator_screen.html` ·
`tests/test_operator_screen.py` (66 tests)

```bash
python scripts/build_operator_screen.py --region uiseong_andong_2025
python scripts/build_operator_screen.py --region yeongdeok_2025
open outputs/live/screens/uiseong_andong_2025/operator_screen.html
```

---

## 0-A. Two screens, two jobs

They are built by the **same builder** from the **same pipeline**; only the
region differs. Keeping both is deliberate — one demonstrates the system, the
other demonstrates its limit, and a presentation that shows only the first is
selling something.

| | **의성·안동 2025** | **영덕 2025** |
|---|---|---|
| purpose | **시연용** — this is the demo | **한계 설명용** — this is the caveat |
| origins | 368 | 458 |
| 자력 대피 | 263 | 414 |
| **구조 필요 (FA-only)** | **91** (24.7 %) | 42 (9.2 %) |
| 도달 불가 | 12 + 2 over budget | 2 |
| **보행망 커버리지** | **99.2 %** | **32.6 %** |
| villages / actionable points | 65 / 105 | 29 / 44 |
| rows shown | 45 of 105, with 「… 외 60곳」 | 44 of 44 |
| 차고지 (depots in walk bbox) | **0** → responder side N/A | 4 |
| what the map shows | the network covers the fire, so the result is the region's | the fire runs 45 km **west out of the dashed box** — 32.6 % made visible |
| output | `outputs/live/screens/uiseong_andong_2025/` | `outputs/live/screens/yeongdeok_2025/` |

**의성·안동 leads.** Its walk network covers 99.2 % of the predicted core, so
its 91 future-aware-only origins are a statement about the region rather than
about a third of it. It is also the strongest result the project has: nearly
**seven times** Yeongdeok's future-aware-only share, on a field that actually
advances.

**영덕 follows, to show the limit.** Its dashed walk-bbox outline sits over a
fire that runs 45 km west, and two thirds of the predicted core falls outside
it. Every absolute Yeongdeok number on that screen is a rate on the covered
third. Saying so is easier when it can be pointed at.

> ⚠ Do not quote the two FA-only shares side by side as a ranking. n = 3, the
> covariates move together, and `HANDOFF_ROUND3.md` rule 14 forbids it. The
> honest statement is the one above: on a field that advances, the same method
> and parameters give a much larger benefit — not that the benefit rises with
> fire speed (Uljin-Samcheok advances fastest and benefits least).

### 의성·안동 has no responder side

Its ignition-centred 919 km² walk bbox contains **no `amenity=fire_station`
mapped in OSM**, so `build_dispatch_list` would have no depot to dispatch from.
The status bar says so:

> 이 지역은 walk bbox(919 km²) 내에 OSM에 매핑된 소방서가 없어 구조자 측
> 산출이 불가합니다 — 더 넓은 3,926 km² 범위에는 6곳

⚠ **Never shorten that to "의성·안동에는 소방서가 없습니다."** The statement is
about OSM mapping inside one bbox; the wider manifest bbox contains six
(`HANDOFF_ROUND3.md` rule 11). The line is generated from the depot count in
`viz.json`, so it appears automatically for any region with zero and never for
one with some.

**No responder route was removed, because none was ever drawn.** The 459 series
is resident-side for *every* region, Yeongdeok included: it contrasts a
fire-blind walking route with a future-aware one and never dispatches a vehicle.
The two lines on both maps are 주민 대피 경로 and 미래 인지 경로 — both are the
resident's. What changed for 의성·안동 is that the screen now *says* the
responder side is not applicable, rather than leaving its absence unexplained.

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

### Demo window — `--start-at` and `--paused-on-load`

A four-minute talk cannot spend twelve minutes replaying. `--start-at` opens the
screen at any point on the field's clock, and `--paused-on-load` opens it
frozen there, so the presenter starts it when they are ready to talk.

```bash
python scripts/build_operator_screen.py --region uiseong_andong_2025 --list-triggers
#   trigger 1: t+77 min
#   trigger 2: t+463 min

python scripts/build_operator_screen.py --region uiseong_andong_2025 \
    --start-at 47 --paused-on-load \
    --out outputs/live/screens/uiseong_andong_2025_demo.html
```

**`outputs/live/screens/uiseong_andong_2025_demo.html`** is that file. At 60×
one wall-clock second is one field minute, so its 60-second window is:

| wall clock | field time | what is on screen |
|---:|---:|---|
| 0 s | t+47 | opens **paused** — surface, 49 hotspots, no list yet |
| 0–30 s | t+47 → t+77 | detections keep arriving |
| **30 s** | **t+77** | **트리거** — 「계산 중」 |
| 30–42 s | t+77 → t+89 | 계산 중 |
| 42–60 s | t+89 → t+107 | origins colour in, routes appear, list fills |
| 60 s | t+107 | 45 rows + 「… 외 60곳」, complete |

Then pause and take questions; 재생 continues to t+463 for the second trigger.

The fill is a **fixed duration** (18 field minutes) rather than a fixed rate, so
the beat is the same length for Yeongdeok's 44 rows and Uiseong-Andong's
45-of-105. That is what makes trigger → complete list exactly 30 s at 60×, and
therefore a 60-second window possible at all.

### Moving the start point reproduces the state exactly

The requirement is that a screen opened at t+110 is identical to one played from
the beginning and scrubbed there. It holds **structurally**: everything drawn is
a pure function of `t`, and `T_START` appears in exactly three places — the
definition, the clock's initial value, and the reset target. It never enters the
hazard, hotspot or row logic, so both paths run the same `render()`.

Verified by building at nine start points and comparing the rendered DOM against
the state computed independently from the payload:

| t | slice | hotspots | 계산 중 | rows |
|---:|---:|---:|---|---:|
| 0 | 1/5 | 23 | no | 0 |
| 47 | 1/5 | 49 | no | 0 |
| **77** | 1/5 | 77 | **yes** | 0 |
| 89 | 1/5 | 77 | no | 0 |
| 95 | 1/5 | 77 | no | 15 |
| 110 | 1/5 | 77 | no | 45 + overflow |
| 200 | 2/5 | 77 | no | 45 + overflow |
| 463 | 3/5 | 101 | no | 45 + overflow |
| 500 | 3/5 | 101 | no | 45 + overflow |

Every one matched, including the hotspot fade pattern — 100 dimmed and 1 current
at t+463, which is exactly what sequential play produces.

> ⚠ **`--start-at` overrides `--skip-preroll`.** An explicit start point is
> where you meant to be; the pre-roll is only a default lead-in.

> ⚠ **Trigger times come from the run's OVERPASS moments, not from hotspot
> arrival times.** A trigger fires when an overpass completes and its batch is
> diffed against the seen-set. For Yeongdeok the two coincide (every detection
> in overpass 0 shares one timestamp); for 의성·안동 they are **77 minutes
> apart**, and an earlier version showed 「계산 중」 at t=0 for a run that did
> not route until t+77.

> ⚠ **`requestAnimationFrame` does not run in a hidden tab**, so the replay
> freezes if the window is backgrounded and resumes where it left off — no time
> jump. Harmless in a demo, and worth knowing if the screen ever looks stuck.

**`--skip-preroll`** builds a variant that starts at the moment of detection:

```bash
python scripts/build_operator_screen.py --region uiseong_andong_2025 --skip-preroll
```

At 60× the pre-roll costs **25 seconds** of wall clock, and a four-minute talk
may not have it to spend on an empty map. The trade is that the screen opens
mid-trigger, so the "nothing detected yet → first detection" beat is lost. Both
variants are built for 의성·안동; the flag changes one number in the payload and
nothing else.

| | with pre-roll | `--skip-preroll` |
|---|---:|---:|
| total at 60× | **12.4 min** | **12.0 min** |
| total at 10× | 74.5 min | 72.0 min |
| opens on | empty map, `탐지 전 25분` | first detection, `+000분` |

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
