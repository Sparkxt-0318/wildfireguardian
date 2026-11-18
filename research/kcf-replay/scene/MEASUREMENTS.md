# KCF 3D scene: load time and checks (measured)

Measured 2026-11-18 00:23 UTC at commit `f14830a` by `research/kcf-replay/scene/tests/smoke.mjs`
(headless Chromium, Playwright, viewport 1600 × 900, device pixel ratio 1) on a cloud container with 4 vCPU
(Intel(R) Xeon(R) Processor @ 2.10GHz) and **no GPU**. WebGL there runs in software (ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)).
The scene detects a software renderer and switches to lite mode on its own; `?full` forces full quality.

**What these numbers are.** The unthrottled runs are this GPU-less container; the CPU ×4 runs stand in for a slow 2020 laptop
without a usable GPU, so read the 33–44 s class as the slow end. Here the GPU's work (drawing terrain, hillshade and the draped layers) runs on the
CPU in software; without network throttling scripts parse in well under a second and selecting a place takes milliseconds of JavaScript (table), so the
rest of the time is drawing. A 2020 laptop with any integrated GPU does that drawing in hardware. No such laptop was available
to measure here, so no laptop figure is claimed: time a cold load once on the presentation laptop before the talk.

## Cold load (ready = first fully drawn frame with data, fonts and labels)

| run | mode | scripts parsed (s) | map load (s) | ready (s) | interaction |
|---|---|---|---|---|---|
| http cold | lite (auto) | 0.4 | 12.7 | 19.2 | |
| file:// cold | lite (auto) | 0.4 | 13.3 | 20.8 | |
| file:// cold, full quality (?full), no throttling | full | 0.4 | 14.1 | 22.9 | next issue hour → idle 9.1 s, select place 13 ms |
| http cold, CPU x4, 20 Mbit/s | lite (auto) | 10.3 | 32.6 | 43.4 | next issue hour → idle 10.3 s, select place 56 ms |
| file:// cold, CPU x4 | lite (auto) | 0.6 | 22.8 | 33.7 | next issue hour → idle 10.2 s, select place 69 ms |

"http" = served like GitHub Pages (`/wildfireguardian/kcf-scene/`) by a local server; "file://" = the folder opened from disk.
CPU ×4 = Chrome DevTools CPU throttling; 20 Mbit/s = DevTools network emulation (40 ms latency).
The local server sends every file uncompressed, so the 20 Mbit/s run downloads all 23.93 MB and its "scripts parsed" time is mostly
that download; GitHub Pages sends gzip (6.83 MB, see Payload), so that run overstates the download about 3.5×.

## Real time (same run, first page: http, lite (auto))

| run | wall (s) | frames | frame p50 (ms) | frame p95 (ms) | longest frame (ms) | longest task (ms) |
|---|---|---|---|---|---|---|
| level 3 drive, 지품리 16:00 (×10, about 30 s) | 49.7 | 14 | 3522 | 4045 | 4395 | 4374 |
| Play 12:00 → 24:00 (1 h per 3 s) | 37.5 | 39 | 995 | 1117 | 1205 | 1188 |

Frame times here are software rendering; they show the scene keeps drawing (no frame stuck for the whole drive), not the frame
rate a GPU gives. The longest task is main-thread JavaScript plus software GL; the scene's own work per drive frame is a camera
move, a few filter changes per second and a marker move.

## Payload

| file | raw MB | gzip MB |
|---|---|---|
| `index.html` | 0.00 | 0.00 |
| `app.js` | 0.10 | 0.03 |
| `style.css` | 0.02 | 0.00 |
| `vendor/maplibre-gl.js` | 1.06 | 0.28 |
| `vendor/maplibre-gl.css` | 0.07 | 0.01 |
| `data/scene.js` | 14.19 | 1.24 |
| `data/terrain.js` | 6.26 | 4.66 |
| `data/basemap.js` | 1.93 | 0.42 |
| `data/fonts.js` | 0.29 | 0.18 |
| **total** | **23.93** | **6.83** |

GitHub Pages serves gzip, so a first visit transfers about 6.83 MB (about 3 s at 20 Mbit/s,
11 s at 5 Mbit/s); a second visit comes from the browser cache. Offline (file://) nothing is downloaded.
Terrain dominates: base64 PNG tiles barely compress.

## Checks in the same run

* Labels: the test-data badge and "reconstruction from the 2025 record" visible in 49 of 49 views checked (region, place, check it, one minute later, drive, horizon-capped rows, all three MEASURED arms).
* Numbers without a source tag in the panels: 0.
* Witness re-walk by the page's own code against every committed arrival second: MEASURED 1134/1134, MEASURED_GUST 1130/1130, MEASURED_GUST_KMA 1130/1130, ORDINARY 1135/1135, RUNNING 1093/1093, WORST 930/930 identical; departing 60 s later fails in 6552 of 6552: a road cell closes before the vehicle leaves it in 2626, the shelter cell closes during the dwell in 884, and arrival + dwell passes the 8 h horizon in 3042 (MEASURED 785, MEASURED_GUST 638, MEASURED_GUST_KMA 648, ORDINARY 971: the horizon-capped rows, state "not cut within 8 h", whose departure is the last one checked inside the horizon; not a closure).
* MEASURED arms (지품리, 18:00 screen): MEASURED: leave-by 18:19, Check it PASS, 6 rows in the each-R(h) table, planner strip 3 shelter rows, button "R(h): MEASURED · running class at 18:00: 7.6 km at 5 h, 10.0…"; MEASURED_GUST: leave-by 18:16, Check it PASS, 6 rows in the each-R(h) table, planner strip 3 shelter rows, button "R(h): MEASURED+GUST (ERA5, PROVISIONAL) · gust ≥ 20 m/s clas…"; MEASURED_GUST_KMA: leave-by 18:16, Check it PASS, 6 rows in the each-R(h) table, planner strip none (no cache), button "R(h): MEASURED+GUST (KMA) · gust ≥ 20 m/s class at 18:00: 8.…".
* Sources panel paths that are not files in the repository: 0 (of 13 checked).
* Page errors and requests leaving the page: 0.
