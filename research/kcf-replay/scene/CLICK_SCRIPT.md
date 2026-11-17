# KCF replay 3D scene — presenter click script (one page, about 4½ minutes)

**Open** the `kcf-scene` folder on the laptop: `index.html` in **Chrome or Edge** (the tested engine). Online alternative, only after
the pull request is merged and the Pages deploy has run: `https://sparkxt-0318.github.io/wildfireguardian/kcf-scene/` (open it once
the day before, so the 9.1 MB first download is cached). Press **F11**. Loading took 20–23 s on a 4-core machine with **no GPU** and
34–43 s with its CPU slowed 4× as a slow-laptop stand-in (`MEASUREMENTS.md`); a laptop with a working GPU should be faster but was
not measured, so time one cold load on the presentation laptop the day before. A "No GPU in use" notice means hardware acceleration
is off. Top left must show **시험 데이터 · 평가 호스트 아님** and **reconstruction from the 2025 record** on every view.
**Fallback:** `kcf_scene_tour_90s.mp4` in the same folder (the three levels, 90 s, captioned).

| # | Do | Screen shows (all from committed files) | Say |
|---|---|---|---|
| 1 | Nothing (opens at **12:00**, level 1 Region) | Terrain 의성·안동–영덕; red = known fire area, 1,395 detections before 12:00; summary 142 LEAVE NOW (24 of them inside the fire area) · 32 VULNERABLE FIRST | "A reconstruction from the 2025 record, marked test data. Red is every satellite detection our rule keeps — FIRMS and Himawari, time-stamped before 12:00 — under a rule frozen before any outcome was computed." |
| 2 | **→** four times (12:00 → 16:00) | Violet road cells grow; 12 blue dots turn yellow (VULNERABLE FIRST 32 → 20) and more dots turn dark as the fire area reaches them (inside 24 → 48). At 16:00: 154 LEAVE NOW · 20 VULNERABLE FIRST. Hover any dot for its clock | "Every hour the screen is recomputed. A road cell closes when the fire, at 8.2 km/h — the running-fire stand-in, not the frozen R(h) — can reach it." |
| 3 | **2** (bookmark 지품리) | Level 2 Place. **Leave by 18:33**, LEAVE NOW, shelter 기사리마을회관, arrival 18:38, witness road in cyan | "The 16:00 screen would have told 지품리: leave by 18:33, this road, this shelter." |
| 4 | **C** (Check it) | Road re-walked edge by edge against the 16:00 closures: **PASS**, arrive 18:38:29, "same arrival second as committed" | "The button re-walks the road against every closure on the 16:00 screen, in the browser, and lands on the committed arrival second." |
| 5 | **L** (One minute later) | **FAIL**: leaving 18:34:40, cell 3128 closes 18:33:44 | "One minute later, the same road is cut." |
| 6 | Point at the panel | "route reached earlier by the reconstruction: **yes** (first cut 18:02)"; pink ◆ on the slider and the REPORTED list: 18:00 order + CBS, 18:25, 18:58, 19:04, 20:25 (뉴스로, SINGLE) | "We show where it fails: the full record reached this road at 18:02 — one of the 108 place-hours counted in RESULTS §5. Pink diamonds are reported times, single-source, not outcomes." |
| 7 | **D** (Drive it) | Level 3 Road: about 30 s chase view behind the vehicle, clock 18:33:40 → 18:38:29, ×10; dark red = detections before each moment, orange = those of the last hour; red warning: the vehicle is inside a detection disc and the record reached this road at 18:02 | "The drive starts at the departure second. The red box is the point: the 16:00 screen could not see what the satellites saw later. The arrival is the screen's projection, not an outcome." |
| 8 | **Esc**, then **→** **→** **→** | 17:00: leave by 18:18 · 18:00: **18:03** · 19:00: inside known fire area | "Each later screen leaves less time, until the place is inside the known fire area." |
| 9 | **←** (back to 18:00), then **R** | R(h) box turns blue: **MEASURED** · running class at 18:00: 7.6 km at 5 h, 10.0 km at 8 h. **Leave by 18:19**, "reached 18:02". Table "this screen under each R(h)": RUNNING 18:03 · MEASURED 18:19 · MEASURED+GUST 18:16 (PROVISIONAL) · WORST no safe departure · ORDINARY 19:24 | "This is the measured margin, frozen from 28 calibration fires (this running class: 27). It says 18:19, after the record reached the road; at 16:00 it gave 지품리 no step at all. On this fire the spread margins failed at every issue hour from 10 to 20 KST. One fire, one day: no rate is claimed." |
| 10 | **S**, then **H** | Sources panel: every file behind what is on screen; back to the region (H also returns to RUNNING) | "Every number on screen comes from a committed file; this panel names it." |

**Keys** ←/→ issue hour · Space play · 1–6 the six places of RESULTS §4 · C check · L one minute later · D drive · Esc back ·
H region (full reset: stops play, back to RUNNING) · R R(h) arm (RUNNING → MEASURED → MEASURED+GUST → WORST → ORDINARY) · S sources · ? about.
**If something goes wrong:** H. Reload (F5) restarts at 12:00. Deep link: `index.html?t=16:00&place=지품리`.
**Do not say:** "they would have been safe", "would have saved", "the fire arrived at …" ("latest safe departure" is the model's
name for a computed time; reported times are reports, not outcomes), and do not rank the R(h) arms ("MEASURED is better"): each is a
different R(h). MEASURED+GUST is PROVISIONAL (ERA5 gusts only; ≥ 20 m/s class = 9 fires). No victim is named anywhere in the scene.
**Not in the scene:** crossing view / REOPENED (no vehicle-unit log for this event; the frozen rule never reopens a road).
