# KCF 3D scene: load time and checks (measured)

Measured 2026-11-17 03:57 UTC at commit `754caab` by `research/kcf-replay/scene/tests/smoke.mjs`
(headless Chromium, Playwright, viewport 1600 × 900, device pixel ratio 1) on a cloud container with 4 vCPU
(Intel(R) Xeon(R) Processor @ 2.10GHz) and **no GPU**. WebGL there runs in software (ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)).
The scene detects a software renderer and switches to lite mode on its own; `?full` forces full quality.

**Read these numbers as an upper bound.** Here the GPU's work (drawing terrain, hillshade and the draped layers) runs on the
CPU in software; scripts parse in well under a second and selecting a place takes milliseconds of JavaScript (table), so the
rest of the time is drawing. A 2020 laptop with any integrated GPU does that drawing in hardware. No such laptop was available
to measure here, so no laptop figure is claimed: time a cold load once on the presentation laptop before the talk.

## Cold load (ready = first fully drawn frame with data, fonts and labels)

| run | mode | scripts parsed (s) | map load (s) | ready (s) | interaction |
|---|---|---|---|---|---|
| http cold | lite (auto) | 0.3 | 12.8 | 18.4 | |
| file:// cold | lite (auto) | 0.3 | 12.4 | 17.5 | |
| file:// cold, full quality (?full), no throttling | full | 0.3 | 13.5 | 19.5 | next issue hour → idle 6.0 s, select place 21 ms |
| http cold, CPU x4, 20 Mbit/s | lite (auto) | 8.9 | 29.1 | 37.1 | next issue hour → idle 7.9 s, select place 60 ms |
| file:// cold, CPU x4 | lite (auto) | 0.5 | 20.8 | 28.7 | next issue hour → idle 8.4 s, select place 58 ms |

"http" = served like GitHub Pages (`/wildfireguardian/kcf-scene/`) by a local server; "file://" = the folder opened from disk.
CPU ×4 = Chrome DevTools CPU throttling; 20 Mbit/s = DevTools network emulation (40 ms latency).

## Payload

| file | raw MB | gzip MB |
|---|---|---|
| `index.html` | 0.00 | 0.00 |
| `app.js` | 0.08 | 0.03 |
| `style.css` | 0.01 | 0.00 |
| `vendor/maplibre-gl.js` | 1.06 | 0.28 |
| `vendor/maplibre-gl.css` | 0.07 | 0.01 |
| `data/scene.js` | 7.99 | 0.80 |
| `data/terrain.js` | 9.44 | 7.07 |
| `data/basemap.js` | 1.93 | 0.42 |
| `data/fonts.js` | 0.29 | 0.18 |
| **total** | **20.88** | **8.80** |

GitHub Pages serves gzip, so a first visit transfers about 8.80 MB (about 4 s at 20 Mbit/s,
14 s at 5 Mbit/s); a second visit comes from the browser cache. Offline (file://) nothing is downloaded.
Terrain dominates: base64 PNG tiles barely compress.

## Checks in the same run

* Labels: the test-data badge and "reconstruction from the 2025 record" visible in 37 of 37 views checked (region, place, check it, one minute later, drive, horizon-capped rows).
* Numbers without a source tag in the panels: 0.
* Witness re-walk by the page's own code against every committed arrival second: ORDINARY 1135/1135, RUNNING 1093/1093, WORST 930/930 identical; departing 60 s later fails on the same road in 3158 of 3158.
* Sources panel paths that are not files in the repository: 0 (of 11 checked).
* Page errors and requests leaving the page: 0.
