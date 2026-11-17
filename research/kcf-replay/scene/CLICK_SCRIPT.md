# KCF replay 3D scene — presenter click script (one page, about 4 minutes)

**Open** `https://sparkxt-0318.github.io/wildfireguardian/kcf-scene/` — or offline: the `kcf-scene` folder on the laptop, double-click
`index.html`. Press **F11**. Wait until the loading screen goes: 17–20 s measured on a machine with **no GPU** (upper bound; `MEASUREMENTS.md`). Time one cold load on the presentation laptop the day before. A "No GPU in use" notice means hardware acceleration is off: turn it on or use the fallback. Top left must show
**시험 데이터 · 평가 호스트 아님** and **reconstruction from the 2025 record**; they stay on every view.
**Fallback:** play `research/kcf-replay/scene/kcf_scene_tour_90s.mp4` (copy it next to the folder) (same three levels, 90 s, captioned).

| # | Do | Screen shows (all from committed files) | Say |
|---|---|---|---|
| 1 | Nothing (opens at **12:00**, level 1 Region) | Terrain 의성·안동–영덕; red = known fire area, 1,395 detections before 12:00; summary 142 LEAVE NOW · 32 VULNERABLE FIRST | "A reconstruction from the 2025 record, marked test data. Red is every satellite detection time-stamped before 12:00, under a rule frozen before any outcome was computed." |
| 2 | **→** four times (12:00 → 16:00) | Violet road cells close; more dots turn yellow; at 16:00: 154 LEAVE NOW · 20 VULNERABLE FIRST · 48 inside | "Every hour the screen is recomputed. A road cell closes at issue time plus distance over 8.2 km/h — the running-fire stand-in, not the frozen R(h)." |
| 3 | **2** (bookmark 지품리) | Level 2 Place. **Leave by 18:33**, LEAVE NOW, shelter 기사리마을회관, arrival 18:38, witness road in cyan | "The 16:00 screen would have told 지품리: leave by 18:33, this road, this shelter." |
| 4 | **C** (Check it) | Road re-walked edge by edge: **PASS**, arrive 18:38:29, "same arrival second as committed" | "The button re-walks the road against every closure, in the browser — and lands on the committed arrival second." |
| 5 | **L** (One minute later) | **FAIL**: leaving 18:34:40, cell 3128 closes 18:33:44 | "One minute later, the same road is cut." |
| 6 | Point at the panel | "route reached earlier by the reconstruction: **yes** (first cut 18:02)"; pink ◆ on the slider and the REPORTED list: 18:00 order + CBS, 18:25, 18:58, 19:04, 20:25 (뉴스로, SINGLE) | "We show where it fails: the full record reached this road at 18:02 — one of the 108 place-hours counted in RESULTS §5. Pink diamonds are reported times, single-source, not outcomes." |
| 7 | **D** (Drive it) | Level 3 Road: about 30 s chase view behind the vehicle, clock 18:33:40 → 18:38:29, ×10; orange = detections before each moment | "The drive starts at the departure second; the fire is what the satellites had seen at each moment." |
| 8 | **Esc**, then **→** **→** **→** | 17:00: leave by 18:18 · 18:00: **18:03** · 19:00: inside known fire area | "Each later screen leaves less time, until the place is inside the known fire area." |
| 9 | **S**, then **H** | Sources panel: every file behind what is on screen; back to the region | "Every number on screen comes from a committed file; this panel names it." |

**Keys** ←/→ issue hour · Space play · 1–6 the six places of RESULTS §4 · C check · L one minute later · D drive · Esc back ·
H region · R stand-in (RUNNING / WORST / ORDINARY) · S sources · ? about.
**If something goes wrong:** Esc twice, then H. Reload (F5) restarts at 12:00. Deep link: `index.html?t=16:00&place=지품리`.
**Do not say:** "would have saved", "safe", "the fire arrived at …" (reported times are reports, not outcomes). No victim is named
anywhere in the scene. **Not in the scene:** crossing view / REOPENED (no vehicle-unit log for this event), MEASURED arms (not run).
