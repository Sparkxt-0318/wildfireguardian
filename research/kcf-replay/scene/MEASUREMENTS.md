# KCF 3D scene: load time and checks (measured)

Measured 2026-11-17 13:17 UTC at commit `51776eb` by `research/kcf-replay/scene/tests/smoke.mjs`
(headless Chromium, Playwright, viewport 1600 × 900, device pixel ratio 1) on a cloud container with 4 vCPU
(Intel(R) Xeon(R) Processor @ 2.10GHz) and **no GPU**. WebGL there runs in software (ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)).
The scene detects a software renderer and switches to lite mode on its own; `?full` forces full quality.

**What these numbers are.** The unthrottled runs are this GPU-less container; the CPU ×4 runs stand in for a slow 2020 laptop
without a usable GPU, so read the 31–41 s class as the slow end. Here the GPU's work (drawing terrain, hillshade and the draped layers) runs on the
CPU in software; scripts parse in well under a second and selecting a place takes milliseconds of JavaScript (table), so the
rest of the time is drawing. A 2020 laptop with any integrated GPU does that drawing in hardware. No such laptop was available
to measure here, so no laptop figure is claimed: time a cold load once on the presentation laptop before the talk.

## Cold load (ready = first fully drawn frame with data, fonts and labels)

| run | mode | scripts parsed (s) | map load (s) | ready (s) | interaction |
|---|---|---|---|---|---|
| http cold | lite (auto) | 0.3 | 15.2 | 21.1 | |
| file:// cold | lite (auto) | 0.3 | 14.5 | 20.9 | |
| file:// cold, full quality (?full), no throttling | full | 0.4 | 14.2 | 21.1 | next issue hour → idle 6.7 s, select place 26 ms |
| http cold, CPU x4, 20 Mbit/s | lite (auto) | 8.9 | 32.1 | 41.0 | next issue hour → idle 7.9 s, select place 69 ms |
| file:// cold, CPU x4 | lite (auto) | 0.6 | 23.2 | 31.6 | next issue hour → idle 8.2 s, select place 94 ms |

"http" = served like GitHub Pages (`/wildfireguardian/kcf-scene/`) by a local server; "file://" = the folder opened from disk.
CPU ×4 = Chrome DevTools CPU throttling; 20 Mbit/s = DevTools network emulation (40 ms latency).

## Real time (same run, first page: http, lite (auto))

| run | wall (s) | frames | frame p50 (ms) | frame p95 (ms) | longest frame (ms) | longest task (ms) |
|---|---|---|---|---|---|---|
| level 3 drive, 지품리 16:00 (×10, about 30 s) | 41.2 | 16 | 2507 | 3298 | 3726 | 3708 |
| Play 12:00 → 24:00 (1 h per 3 s) | 37.4 | 50 | 761 | 882 | 923 | 920 |

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
| `data/scene.js` | 11.17 | 1.08 |
| `data/terrain.js` | 6.26 | 4.66 |
| `data/basemap.js` | 1.93 | 0.42 |
| `data/fonts.js` | 0.29 | 0.18 |
| **total** | **20.91** | **6.66** |

GitHub Pages serves gzip, so a first visit transfers about 6.66 MB (about 3 s at 20 Mbit/s,
11 s at 5 Mbit/s); a second visit comes from the browser cache. Offline (file://) nothing is downloaded.
Terrain dominates: base64 PNG tiles barely compress.

## Checks in the same run

* Labels: the test-data badge and "reconstruction from the 2025 record" visible in 45 of 45 views checked (region, place, check it, one minute later, drive, horizon-capped rows, both MEASURED arms).
* Numbers without a source tag in the panels: 0.
* Witness re-walk by the page's own code against every committed arrival second: MEASURED 1134/1134, MEASURED_GUST 1130/1130, ORDINARY 1135/1135, RUNNING 1093/1093, WORST 930/930 identical; departing 60 s later fails in 5422 of 5422: a road cell closes before the vehicle leaves it in 2226, the shelter cell closes during the dwell in 802, and arrival + dwell passes the 8 h horizon in 2394 (MEASURED 785, MEASURED_GUST 638, ORDINARY 971: the horizon-capped rows, state "not cut within 8 h", whose departure is the last one checked inside the horizon; not a closure).
* MEASURED arms (지품리, 18:00 screen): MEASURED: leave-by 18:19, Check it PASS, 5 rows in the each-R(h) table, button "R(h): MEASURED · running class at 18:00: 7.6 km at 5 h, 10.0…"; MEASURED_GUST: leave-by 18:16, Check it PASS, 5 rows in the each-R(h) table, button "R(h): MEASURED+GUST (PROVISIONAL) · gust ≥ 20 m/s class at 1…".
* Sources panel paths that are not files in the repository: 0 (of 13 checked).
* Page errors and requests leaving the page: 0.
