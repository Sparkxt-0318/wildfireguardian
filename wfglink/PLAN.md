# wfglink plan: measuring embers and ember-derived wind from ordinary camera video

Version 4, 2026-10-15 (Asia/Shanghai). Version 4 replaces the five Mac check-ins with two hands-on sittings (section 9), moves every decision that waited on check B into config switches, and keeps the camera and app fallbacks ready before sitting 1. Version 3 was approved with changes on 2026-10-14. Version 2 added the fixes from an independent review covering measurement science, booth engineering and requirements coverage. Version 3 adds your six approval changes:
- dashcam (블랙박스) file-mode check;
- an always demo-ready tagged build;
- a schedule around your 18 October submission;
- clip decisions;
- booth screen priority;
- hardware substitutions.

## 1. Context

During a wildfire nobody measures how many embers fly, where, or how fast, and nobody measures street-level wind inside communities. Spotting (비화) carried the March 2025 Uiseong fire up to about 51 km from its western front to Ganggu port on the Yeongdeok coast within about 12 hours. That is KFS analysis with NIFOS mapping, reported by Newsis on 2025-03-27. It describes cumulative spread through repeated spotting, not one ember flight. NIST's Emberometer measures embers with four synchronized cameras and 3D particle tracking, but only where it is installed before a fire.

wfglink treats glowing embers as tracer particles in ordinary video: dashcams (블랙박스), CCTV and phones. It runs in two modes:
- File mode works on clips at full quality.
- Booth mode is camera-in-the-loop: the iPad plays a clip, the iPhone 13 films it over Continuity Camera, and the M4 Pro MacBook shows results fullscreen on the external monitor.

What scouting established:
- The repo has no video or OpenCV code, so wfglink starts from scratch and copies only conventions (exact pins, NUMBERS provenance, Korean-first booth screens, contrast and dash checks).
- The route logger is not in any git ref. It is an ESP32 + Quectel L76K GNSS device with planned CSV and GPX exports, and its schema exists only on your Mac.
- Your iPad Air has an LCD panel at 60 Hz with no PWM flicker per reviews.
- Continuity Camera probably cannot lock exposure from the Mac side (macOS exposes only lock or auto modes, and check A tests even that).
- The schedule is one week of continuous work by me, ending Wednesday 2026-10-21.

## 2. Ground rules

- Scope: everything stays inside `wfglink/`. Nothing outside it is created, edited, moved or deleted, and no forecast, routing or monte-carlo code is imported.
- Git:
  - `git add wfglink/` only, with commit messages prefixed `[wfglink]`.
  - No branch switching, stash, rebase, reset or force-push. On `.git/index.lock`, wait and retry.
  - Push to `claude/practical-rubin-5vu12u` (approved) and keep one draft PR to Main.
  - Demo tags, from M2 onward:
    - Each day I tag the latest commit that passes the demo gate as `wfglink-demo-YYYYMMDD` and push only that tag.
    - Demo gate: the live UI runs end to end for 60 s offscreen on the synthetic source and on one approved clip, with no errors, started by the single booth command.
    - The tag name and commit go into LOG.md each day.
    - If a later milestone breaks something, the previous tag is still a working demo.
  - Before every commit, `scripts/check_staged.py` fails if a staged file is a video or larger than 5 MB. I run it myself, because a git hook would live outside wfglink/.
- `.gitignore` covers: `.venv/`, `data/raw/`, `data/synthetic/`, `data/booth/`, `results/runs/`, `build/`, `dist/`, `*.app`, video extensions (mp4, mov, m4v, mkv, avi, webm) and caches.
- Python:
  - Python 3.12, venv at `wfglink/.venv`, exact pins in `requirements.txt`.
  - Pins: numpy, scipy, opencv-contrib-python-headless 4.14.x, PySide6 6.12, av (PyAV, bundles FFmpeg), pyarrow, pandas, pyyaml, matplotlib, pytest. On macOS only: pyobjc-framework-AVFoundation.
  - The headless OpenCV build avoids Qt clashes with PySide6, and 4.14 avoids the OpenCV 5.0 module restructure.
  - Tracking metrics are written in-house, because py-motmetrics breaks on NumPy 2.
- Records:
  - LOG.md, one entry per significant run, failures included. Each entry has a timestamp (ISO 8601, +08:00), goal, exact commands, parameters, results (with NUMBERS.json keys), decisions and next step.
  - docs/PROMPT.md holds the original prompt verbatim, then your later decisions verbatim with dates.
  - results/NUMBERS.json records, for each number, its value, unit, script, config path, config SHA-256, git commit, dirty flag, input hashes and timestamp.
  - data/SOURCES.md covers every clip, dataset, parameter and paper.
- Documentation checker: `scripts/check_docs.py` scans README, PLAN, LOG, METHODS, LIMITS, the runbook and UI strings. It fails on:
  - any result number without a NUMBERS.json key;
  - any entry with dirty=true;
  - any U+2014 or U+2013 dash.

  Literature values are cited in SOURCES.md, not NUMBERS.json.
- Writing and figures:
  - Plain English with no decorative formatting.
  - One matplotlib style: Okabe-Ito palette, axes labeled with units, Pretendard for Hangul.
  - Saved as 300 dpi PNG plus SVG. I open and inspect every figure.

## 3. Architecture

Data flow, shared by every mode through one `Pipeline` class:

1. Source (file, camera or synthetic) gives a frame and its true timestamp.
2. Booth mode only: screen rectification and frame-code decoding.
3. Detection.
4. Streak measurement.
5. Tracking.
6. Velocity.
7. Gate counts and flux.
8. Ember velocity field.
9. Optional metric scaling.
10. Outputs: tables, summary JSON, overlay video and the live dashboard.

```
wfglink/
  README.md PLAN.md LOG.md pyproject.toml requirements.txt .gitignore
  configs/      default.yaml, booth.yaml, suites/*.yaml (every threshold lives in config)
  src/wfglink/  io/ screen/ detect/ track/ measure/ pipeline.py render/ outputs/ ui/ synth/ validate/ viz/ provenance.py cli.py
  scripts/      setup_mac.sh, mac_check_camera.py, mac_check_live.py, mac_soak.py, check_docs.py, check_staged.py, make_app.sh
  booth/        booth.command (double-click), booth.sh, BOOTH_RUNBOOK.md (ko/en)
  assets/fonts/ Pretendard OTF (SIL OFL 1.1) + license
  tests/        pytest unit and integration tests
  data/         SOURCES.md, clips.csv, clips/<clip_id>.yaml (tracked); raw/, booth/, synthetic/ (ignored)
  results/      NUMBERS.json, validation/, figures/ (tracked, small); runs/ (ignored)
  docs/         PROMPT.md, METHODS.md, LIMITS.md (ko/en), MAC_CHECKS.md
```

The CLI is `python -m wfglink` with these commands: `devices`, `doctor`, `synth`, `process`, `validate --suite core|mismatch|coverage|loop|led`, `live`, `booth-prep`, `calibrate` and `reproduce`. Every input and output path is a flag or config key, so the same commands run on your Mac.

### Modules

Parameters live in configs and METHODS.md.

| Module | Method |
|---|---|
| Input | Files: PyAV with true presentation timestamps (handles variable-frame-rate phone clips). Duplicated frames are detected by content (difference below noise) and excluded from velocity. Camera: permission is requested on the main thread through pyobjc before any thread starts, then `OPENCV_AVFOUNDATION_SKIP_AUTH=1` is set before importing cv2. The device is chosen by `isContinuityCamera` plus a saved uniqueID, with Desk View excluded. It maps to the OpenCV index by replicating OpenCV's sort order. PyAV avfoundation is the fallback path. |
| Detection | Luma background via an approximate running median (sign update, cost close to 1 ms). An exact median is a file-mode option. Then a white top-hat and a noise-relative threshold with hysteresis, then connected components. Big bright regions (flames, headlights) are masked, and anything static for more than 1 s is rejected. Color is only a confidence score, because 4:2:0 compression smears small blobs. Saturated blobs are flagged. |
| Streaks | Second moments of background-subtracted intensity in a dilated window, corrected for noise: L = sqrt(12(λ1 − λ2)). Orientation mod 180°. Collinear fragments (within 10°, gap no more than L/2) are merged first, so a dashed streak caused by in-exposure flicker stays one ember. |
| Tracking | In-house constant-velocity Kalman filter. The cost is Mahalanobis distance (gate chi-square 9.21) plus a penalty when streak and motion directions disagree. Hungarian assignment. A track confirms after 3 hits in 4 frames and may coast for 3 frames. |
| Velocity | Track: velocity from a Savitzky-Golay derivative against true timestamps, correcting the known gain. Streak: speed = L / T_exp. Exposure: T_exp in seconds comes from metadata when present. Otherwise it is a robust Deming regression through the origin of L on track speed, fitted over a rolling 10 s window on clean, fast, unflagged tracks only. Its uncertainty is carried as a shared error. Reporting: track-only, streak-only and fused speeds are reported separately. Fusion is used only for tracks shorter than 5 points. |
| Gate and flux | A line gate with crossing hysteresis counts each track once per direction. Count rate: crossings per second over the last 10 s. Cumulative Particle Count (gate): gross and net counts. Particle Number Flux (projected, 2D): crossings per second per unit gate length. The unit is per 100 native px when uncalibrated, per degree of view angle with intrinsics, or m⁻¹ s⁻¹ "at Z = ... m". Uncertainty: a moving-block bootstrap over 1 s bins, combined with the detection efficiency measured on synthetic data. The names mirror NIST as you asked, but the screen and docs state that they are analogous to, not comparable with, NIST CPC (m⁻²) and PNF (m⁻² s⁻¹), which use a 3D surface. |
| Ember velocity field | 16×9 cells. Each track contributes one sample per cell. Median, MAD rejection and the normalized median test across neighbors. Cells with fewer than 5 tracks are hidden. Cells with 5 to 9 are hatched with no confidence interval. Cells with 10 or more get a bootstrap confidence interval. Label: "Ember-derived air velocity (estimate)". Notes: the horizontal component is the wind proxy; the vertical component includes settling and is marked biased. |
| Calibration | Pixels by default. A ground-plane homography (from lane dashes or clicked points) only estimates camera height, pitch and focal length. It is never applied to airborne embers. Ember meters: m/px = Z/f, with an assumed distance interval [Z_min, Z_max] per clip, reported as the speed interval [v(Z_min), v(Z_max)]. That interval is kept separate from a Monte Carlo confidence interval for f and the clicked points. Korean lane-dash lengths: cited and checked before use. ChArUco intrinsics are deferred. |
| Outputs | Parquet tables (CSV by flag), summary JSON, and an H.264 overlay video. The overlay is drawn by the same QImage and QPainter renderer as the live UI, with no QPixmap, so it can run off the GUI thread. |

### UI: native PySide6, one process

Recommended over a local web app.
- Frame path: frames go from numpy to QImage to a custom QWidget. A web app would add a JPEG encode and decode per frame, a second process and a kiosk browser.
- Hangul: renders through QPainter with Pretendard, falling back to Apple SD Gothic Neo. OpenCV cannot draw Hangul.
- Display: Qt puts the window fullscreen on a chosen QScreen and handles monitor hot-plug.
- Offline: works offline by construction.
- One renderer: the same renderer draws the booth screen and the exported videos.
- Testable here: in headless mode (`QT_QPA_PLATFORM=offscreen`) I can render and inspect 1920×1080 screenshots in both languages.

Threads:
1. A capture thread fills a one-slot queue.
2. A processing thread emits an immutable Result, which owns its array and keeps it referenced next to its QImage, through a queued signal.
3. The GUI repaints only when a new Result arrives.

The worker pre-scales frames to widget size × device pixel ratio, so drawing is 1:1. Capture and processing can also run in a child process that hands frames over in shared memory. Both modes are built before sitting 2, behind `live.worker_mode: thread | process`, so a jank result in check B is a config flip, not new code.

Design priority (your rule): the first five seconds must read as a finished product from 2 m away.
- Startup:
  - The app opens straight into fullscreen, with no splash, console or debug text.
  - Video with glowing tracks appears within 3 s.
  - Numbers fade in once the background model has warmed up, so no zeros or placeholders flash.
- Hierarchy: big numbers and glowing orange ember tracks (soft additive glow with short fading trails) dominate the screen.
- Sizes (checked in screenshot tests on a 1920×1080 frame):
  - main values at least 96 px tall;
  - card labels at least 28 px;
  - small tags at least 18 px.
- Colors:
  - black background, white type, secondary gray #8E8E93;
  - green #30D158 for every measured value (numbers, sparkline, direction rose, field arrows);
  - orange #FF9F0A only for embers and their tracks.
- Layout:
  - Video area on the left (about 70% of the width).
  - Four cards on the right:
    - 초당 통과 수 / Count rate
    - 누적 입자 수 (게이트) / Cumulative Particle Count (gate)
    - 입자 수 플럭스 (투영) / Particle Number Flux (projected)
    - 불티 속도 / Ember speed, with the direction rose
  - Underneath: a 60 s sparkline.
- Tags: "추정치 · Estimate" and "보정 안 됨 · Uncalibrated (px)" stay small but always visible, next to the values they qualify. The source and fps sit in a small status line.
- Limits card (ko/en): not on the main screen permanently. It appears on key I, or permanently on an optional second display (`--limits-screen`).
- Keys: L language, I limits, T tracks, F field, G gate, Space pause (file mode), Esc quit with confirm.
- Contrast is tested against WCAG AA.

### Frame rate and resolution targets

All values are measured and recorded in NUMBERS.json.
- Live capture: Continuity Camera at 1920×1080, 30 fps (`camera.fps`, set to 60 if check A shows the iPhone 13 offers it). The capture backend is chosen at start-up by `camera.backend: auto | pyav | opencv`. In auto mode each backend is tried in order and the first one delivering the requested size and rate wins, so check A results only change defaults.
- Live analysis: the rectified screen region at the camera's real pixel coverage (at most 1280×720). Whole-loop processing at most 15 ms median and 25 ms p95 on the M4 Pro, with the UI running, so 30 fps holds. ArUco markers are detected every 15 frames and locally in between. The erf streak refinement is off in live mode.
- File mode: native resolution by default (`--scale 0.5` is an opt-in preview). 1080p30 at real time or faster; 4K at native resolution at 8 fps or more.
- Linux container: timings are recorded only as reference, not as targets.

## 4. Validation

### 4.1 Synthetic generator

- Flows: uniform, linear shear and Rankine vortex for tuning. Lamb-Oseen vortex and random-mode turbulence are held out.
- Embers: quadratic-drag particles following the air (dv/dt = g − (g/Vt²)|v − u|(v − u)), with terminal velocity Vt of 1, 2.5, 5 and 8 m/s and a declared px/m at a reference depth. The ground truth therefore holds both ember velocity and air velocity, so the lag is measurable.
- Emission: gust-modulated (Cox process).
- Rendering:
  - Gaussian spots (σ 0.6 to 2 px), integrated SNR 3 to 30 in a PSF-matched aperture, orange glow.
  - Flicker between frames at 3 to 15 Hz (dropouts), and tumbling within an exposure at 30 Hz or more (dashed streaks).
  - Motion blur by sub-frame integration with exposure duty δ of 0.25, 0.5 and 1.
  - Night and smoky backgrounds, flame regions, static lights, headlights and sparks.
  - Poisson and read noise with gamma, Koschmieder haze, global flicker.
  - H.264 at CRF 18, 23, 28 and 35.
- Ground truth per frame and per particle: exposure start and end positions, ember and air velocity, visibility, true gate crossings.

| Suite | Use | Size and budget |
|---|---|---|
| core | Tuning only. One factor varied at a time around a base case: 720p30, CRF 23, SNR 10, δ 0.5, medium density, uniform flow. | 5 s clips, at most 150 clips, at most 2 CPU-hours |
| mismatch | Never tuned. Supplies the headline numbers. Contents: 3D particles with perspective and depth-dependent defocus; rolling shutter (10 to 30 ms readout); tumbling flicker; saturation and blooming; denoise and sharpening; an exposure step mid-clip; variable frame rate and duplicated frames; held-out flows. | About 60 clips |
| coverage | Never tuned. Tests confidence-interval coverage. | 200 independent 10 s clips at 640×360 |
| loop | Camera-in-the-loop simulator (4.3). | About 30 clips |
| spot | Format check: 1080p, 60 fps and H.265. | 10 clips |

### 4.2 Metrics and goals

Goals are fixed before measuring. Missed goals are reported with their reasons, separately for core and mismatch.

| Metric | Goal |
|---|---|
| Detection F1 (Hungarian match within 3 px, or within max(3, L/2) for streaks); recall counts visible truth outside flame masks | ≥ 0.90 at CRF 23 and SNR ≥ 5 |
| Median relative speed error, track speeds and streak speeds (L > 5 px) separately | ≤ 10% |
| Median direction error | ≤ 10° |
| Exposure T_exp relative error, at each δ | ≤ 10% |
| Cumulative Particle Count (gate) relative error | ≤ 10% |
| Particle Number Flux (projected) relative error | ≤ 10% |
| Confidence-interval coverage of true crossings (200 clips, Clopper-Pearson interval) | ≥ 90% |
| Tracking MOTA and ID switches | Reported |
| Field RMSE against the true ember field and the true air field | Reported, to show the lag |
| Live loop time | Section 3 targets |

### 4.3 Camera-in-the-loop (booth) robustness

`booth-prep` writes `data/booth/<clip>.mp4` plus a sidecar CSV mapping frame index to source timestamp. It changes the clip in three ways:
- Corner codes: each corner gets a 4x4 ArUco marker (about 96 source px) plus a Gray-coded 16-bit frame index with 2 parity bits. These overlay the corners of the original frame rather than adding a border, and the corners are masked from detection.
- Held frames: the prepared video is written at 30 fps with every source frame repeated `booth.hold_factor` times. The default is 2: each source frame stays on the 60 Hz panel for 4 refreshes (67 ms), which is 0.5× playback. booth-prep always writes both the 2× and the 3× file, so falling back to 1/3× after sitting 2 means flipping `booth.hold_factor` and playing the other file. The app measures the actual playback rate from the frame codes and labels it on screen ("0.5× 재생"). It also reports the clean-frame yield; 1/3× is the fallback if the yield is below 80%.
- Optional crop or zoom onto the ember region, which offsets the resolution lost to re-filming.

In booth mode only clean frames are analyzed: all 4 codes must agree and none may be gray. Velocity comes from track displacement over source-timestamp Δt. Streak speed and exposure estimation are off, because the iPhone's own exposure adds smear. When playback loops back to the start, the tracker resets and counts are reported per loop. An unprepared clip still runs, with an "unprepared clip" badge and 4 clicked corners, but it is never compared with file mode.

| Artifact | Mitigation |
|---|---|
| Moiré | Screen fills about 60 to 70% of the frame at a slight angle with mild defocus. The temporal background and top-hat remove static patterns. Tested in the loop suite. |
| Refresh and frame blending (60 Hz panel, free-running iPhone) | Held frames plus Gray codes: a blended frame shows gray bits and is skipped. |
| Rolling-shutter tearing (scan direction unknown) | The 4 corner codes disagree on a torn frame, which is dropped. Sitting 1 includes a 240 fps slow-motion clip of the iPad to confirm the scan direction. |
| PWM flicker | Not expected on the LCD iPad Air. Marker white and black cells normalize gain. |
| Glare | Black hood, matte protector, angle. Static glare is part of the loop suite. |
| Auto exposure and white balance drift | Gain normalized by the marker cells. Thresholds are relative to local noise. |
| Apple Reactions or other video effects inject fireworks | Turned off in the Video menu. If the .app is used, it ships with Reactions disabled by default. |

Loopback check: align the live and file-mode runs on the same clip by frame code. Use file mode at the rectified live resolution as a control. Match tracks and report live recall and precision against file mode, plus the median and IQR of per-track speed ratios.

### 4.4 Controlled real test with known speed

I'll copy NIST's punk-stick method: they measured 44.3 ± 1.9 cm/s against a predicted 44.3 cm/s. Ours puts three diffused orange LEDs at radii of about 3, 8 and 14 cm on a record turntable.
- The camera is mounted top-down; the ellipse axis ratio must be at least 0.99.
- The check is in px/s against ω·r_px, with r_px from an ellipse fit, so no scale is needed.
- ω is timed independently over 30 revolutions.
- A ruler in the LED plane checks m/px separately.
- LED clips are never used for tuning. A clip I debug on is named in LOG.md and excluded from the reported error.

Goal: median speed error ≤ 5%.

The same LED test is also filmed with your booth 블랙박스 dashcam, and its SD-card clips are processed in file mode. A short night drive you record with it serves as a hard negative. One table puts the dashcam beside the iPhone with these columns:
- LED detection precision and recall per frame;
- median and p90 speed error;
- the exposure estimate;
- false tracks per minute on the night drive.

That table is the evidence behind the "This is the sensor" exhibit. Dashcam overlays (timestamp, logo) are masked by config. Neither device's LED clips are ever used for tuning.

### 4.5 Real-clip plausibility checks

- Timing: timestamp gaps, variable frame rate and duplicated frames are flagged.
- Exposure: the T_exp estimate is stable over time and physically possible (no longer than one frame interval).
- Static lights: produce no counted tracks.
- Speed: flagged only if it exceeds 1.5 × the peak gust from the nearest KMA AWS (or NWS) station plus 8 m/s, at both Z_min and Z_max. Filkov et al. 2017 (0.1 to 10.5 m/s) is cited only as context from low-intensity fires.
- Direction: dominant direction compared with smoke drift I annotate by hand.
- Blind sample labels: I label embers before seeing detections, on 4×-enlarged 256 px tiles of 20 randomly sampled frames per clip. Results are tagged "agent-labeled" with a bootstrap over frames. You check 5 frames, which gives an inter-labeler F1.
- Determinism: identical tables on rerun. The overlay video is excluded across machines because font rendering differs.

## 5. Data intake

- Layout:
  - `data/raw/<clip_id>.<ext>`: never committed.
  - `data/clips/<clip_id>.yaml`: gate, ROI, Z interval, calibration points, time offset, split.
  - `data/clips.csv`: provenance table.
  - `data/SOURCES.md`: credits.
- Provenance columns: clip_id, title, source, page URL, media URL, license, credit line, permission notes, date recorded, date accessed, event and location, duration, resolution, fps, codec, SHA-256, camera type, viewpoint, day or night, moving or static, lane markings, ember visibility, split.
- Flow (your instruction): you approve the shortlist in section 13. I download only approved clips whose license and platform allow it, and record each in `clips.csv` and SOURCES.md within the hour. No YouTube downloads.
- Kinds of clips:
  - night ember storms;
  - dashcam viewpoints;
  - fixed CCTV-like cameras;
  - phones;
  - lane markings or known lengths;
  - Korean fires;
  - controlled firebrand experiments;
  - hard negatives: night driving, fog, sparks, rain or snow in headlights.

  Open sources have no openly licensed Korean ember video (section 13), so Korean footage needs permission or your own recordings.

## 6. Outputs

| File | Contents |
|---|---|
| detections.parquet | frame, t, x, y, area, peak, sum, L, θ, color score, flags, track_id |
| frames.parquet | frame, t, source index, detections, active tracks, count rate, CPC gross/net, PNF, clean/duplicate/blend/torn flags, T_exp, processing ms |
| tracks.parquet | track_id, start/end, points, u, v, speeds (track, streak, fused), direction, residual, crossings, flags |
| field.parquet | window, cell, u, v, n_tracks, CI |
| summary.json | input SHA-256, metadata, config hash, git commit, versions, units and calibration state, totals with CIs, T_exp, plausibility flags, warnings |
| overlay.mp4 | H.264, drawn by the live renderer |

Live recording of the same tables is off by default. When on, ParquetWriter flushes every 10 s.

## 7. Booth operation

- One command: `wfglink/booth/booth.sh`, or double-click `booth.command` in Terminal. It runs `caffeinate`, then supervises the app:
  - exit 0 (Esc confirmed) stops it;
  - crashes restart with backoff of 2 to 60 s;
  - logs rotate at 10 MB × 5 files, plus a heartbeat JSON with fps, source state and memory.
- No launchd: it would change the camera-permission owner.
- The app-build fallback is ready before sitting 1. If check A sees zero frames from Terminal (newer macOS wants `NSCameraUseContinuityCameraDeviceType`), the sitting 1 script builds a py2app alias-mode `.app` in seconds and reruns the camera test inside it automatically. `booth.launcher: terminal | app` selects which one the booth command starts. It sets NSCameraUsageDescription, NSCameraUseContinuityCameraDeviceType=true and NSCameraReactionEffectGesturesEnabledDefault=false. PyInstaller is the last resort. The camera permission must be re-granted after each rebuild.
- "This is the sensor" exhibit: the booth dashcam sits on display. Its LED and night-drive results (4.4) open on a key press or on the second display.
- Source health: a source is healthy only when the markers are locked and the decoded index advances. A paused iPad shows "iPad 정지 · iPad paused".
- Source chain:
  1. iPhone.
  2. USB webcam, mounted next to it and aimed at the iPad.
  3. File replay with a full-width "녹화 재생 · REPLAY, not live" band and separate counters.

  It switches back to a camera only after 5 s of continuous health.
- Runbook:
  - Wired Continuity Camera with the Wi-Fi and Bluetooth radios on but joined to no network.
  - Same Apple Account, Trust This Computer accepted.
  - Personal Hotspot off; Focus on for iPhone and Mac; automatic updates off.
  - iPad: Auto-Brightness, True Tone and Night Shift off, Auto-Lock Never, Guided Access with loop playback.
  - Video menu effects off.
  - iPhone case off, out of the sun.
  - A 10-minute setup checklist and failure procedures.

## 8. Stretch goals (only after the core works)

S1, moving camera:
- KLT features on the background, with embers and flames masked, and a forward-backward check.
- USAC_MAGSAC homography from distant features.
- This removes rotation and shake only, and results are labeled "rotation-compensated, camera-relative". Forward motion leaves depth-dependent parallax.
- Gate and field pause when uncompensated ego-motion is high.
- Validated on synthetic rotation and shake.

S2, GNSS from the route logger (read-only use of its exports):
- A GPX reader (WGS84, UTC) and a CSV reader driven by a column-mapping YAML, with units declared, never guessed.
- Time sync by manual offset (film the logger screen or press its event button) or by cross-correlating speed with background flow.
- Outputs: per-frame speed and heading, compass bearings for a forward dashcam, and a bound on the translation bias.
- Design only this week unless you send a sample export.

## 9. Milestones

Times are Asia/Shanghai. Your hands-on work happens in two sittings (your schedule change of 2026-10-15). I keep building without blocking on you. Every decision that depends on your hardware is a config switch with a safe default, so a late sitting causes no rework.

Your Korea Code Fair submission deadline is Sun 18 October. The demo tags from M2 onward are ready if you want to show wfglink in that submission.

| When | Deliverables | Done when |
|---|---|---|
| M0 Wed 14 night | Scaffold, records, environment, detector; capture backends (PyAV and OpenCV) with automatic fallback and a fake camera for tests; reconnecting source; app-build script | Smoke and detector tests pass here |
| M1 Thu 15 | Synthetic generator v1 with ground truth; tracker; velocity; exposure estimator; gate counts; metrics; first numbers; approved clips downloaded (C1 when you share it); sitting 1 kit complete (script, checklist, iPad panel test video, LED and dashcam analysis) | Sitting 1 kit passes a dry run here on synthetic and file stand-ins |
| M2 Fri 16 | Finished-looking live UI on the real pipeline (ko/en, 2 m design rules); thread and process worker modes; watchdog and source chain; booth.sh; booth-prep with codes and both hold factors; demo gate and first demo tag | First `wfglink-demo-*` tag pushed and logged |
| M3 Sat 17 | Streaks and exposure in the pipeline; ember field; flux CIs; Parquet, JSON and overlay export; core and mismatch suites with figures | Headline numbers from the mismatch suite |
| M4 Sun 18 | Loop simulator and loop suite; calibration; side-by-side dashcam and iPhone LED report (4.4), run as soon as sitting 1 files arrive; first real-clip runs | One real clip fully processed; LED report runs on a synthetic stand-in |
| M5 Mon 19 | Coverage suite; plausibility; METHODS, LIMITS, runbook, README; profiling; sitting 2 kit complete | `reproduce` regenerates everything; sitting 2 kit passes a dry run here |
| M6 Tue 20 | Results from sitting 1 folded in; S1; S2 only with a logger export. Sitting 2 in the evening (if it is on Tue 20). | Sitting 2 report received and the soak started |
| M7 Wed 21 | Rehearsal in the morning; fixes and config flips from sitting 2; freeze, final checks | Clean tree, checks green, final demo tag pushed |

Deferred unless ahead of schedule: erf streak refinement, four-frame tracking, IDF1, H.265 beyond the spot check, ChArUco intrinsics, property-based tests, PyInstaller. If time slips, I protect this order: core measurement with synthetic validation and file mode; live UI with reconnect; loop robustness; real clips; calibration polish; stretch goals.

### Your two sittings

Each sitting has one script, one checklist and one combined JSON report. Run the scripts from a separate worktree so your other sessions' checkout is never switched: `git fetch origin claude/practical-rubin-5vu12u && git worktree add ~/wfglink-run origin/claude/practical-rubin-5vu12u`. Refresh it before a sitting with `git -C ~/wfglink-run checkout --detach origin/claude/practical-rubin-5vu12u` after a fetch.

Sitting 1, as soon as your parts arrive (you tell me the date). About 60 to 75 minutes. Script `scripts/sitting1.sh`, checklist `docs/SITTING1.md`. Steps, in order:
1. Preflight and install.
2. Check A:
   - camera list, formats and exposure-lock probe;
   - capture through each backend (automatic `.app` retry if Terminal gets zero frames, plus the USB webcam if plugged in);
   - fullscreen feed on the external monitor;
   - whole-loop timing.
3. Guided recordings. The script says exactly what to record, how, and for how long, then renames and checks each file:
   - iPhone LED turntable clips at both speeds, plus the ruler clip, with your stopwatch timings typed in;
   - the same LED set filmed with the 블랙박스;
   - a short dashcam night drive (optional; it can be added later with one command);
   - a 240 fps slow-motion clip of the iPad playing a panel test video I provide.
4. Local analysis of the recordings: LED speed error per device, iPad scan direction, false tracks on the night drive.
5. Packaging. One upload folder with the renamed files, SHA-256 hashes and `report_sitting1.json`, plus upload instructions (Drive, Dropbox or iCloud link) and a short summary to paste to me.

Sitting 2, the final evening, with the rehearsal the next morning. Script `scripts/sitting2.sh`, checklist `docs/SITTING2.md`. Steps, in order:
1. Check B, the booth loop with the iPad from the latest demo tag:
   - clean-frame yield at hold factor 2, retried at 3 if below 80%;
   - thread and process worker timing;
   - unplug and replug test;
   - fullscreen placement on the monitor.
2. The script writes the recommended config flips into `configs/booth_local.yaml` and starts the overnight soak (check C) with them.
3. In the morning: press Esc or run `scripts/sitting2.sh --finish`. The soak stops and the combined `report_sitting2.json` is written (soak fps, memory slope, reconnects, iPhone heat if the iPhone reports it).
4. The rehearsal follows `booth/BOOTH_RUNBOOK.md`.

Decisions that wait on your hardware, each a config switch with a safe default:

| Switch | Default | Set by |
|---|---|---|
| `camera.backend` | auto | Sitting 1 (check A) |
| `camera.fps` | 30 | Sitting 1 (check A) |
| `booth.launcher` | terminal | Sitting 1 (check A) |
| `booth.hold_factor` | 2 | Sitting 2 (check B) |
| `live.worker_mode` | thread | Sitting 2 (check B) |
| `ui.screen` | external | Sitting 2 (check B) |

## 10. Test plan

- Unit:
  - flow fields;
  - renderer (blur length = |v|·δ·Δt within 0.1 px when noise-free);
  - streak estimator;
  - Kalman filter and assignment;
  - gate crossings with no double counts under jitter;
  - bootstrap intervals;
  - normalized median test;
  - Z/f scaling;
  - Gray-code round trip through H.264;
  - i18n keys complete in both languages;
  - contrast ≥ 4.5:1;
  - Pretendard actually loaded (QFontInfo family check);
  - no QPixmap in the renderer;
  - no em dashes.
- Integration:
  - a synthetic clip through `process` with regression thresholds;
  - determinism;
  - a fake camera that stops, freezes or returns, which must recover within 5 s;
  - offscreen screenshots in both languages with a text-overflow check.
- Soak: a 1 h synthetic live run here with random disconnects, then check C on the Mac.
- Docs: `check_docs.py` and `check_staged.py` before every commit.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Continuity Camera gives zero frames from Terminal | PyAV and OpenCV backends with automatic fallback; py2app alias app built and retried automatically in sitting 1; USB webcam; all ready before sitting 1 |
| Sittings happen late (parts delivery, final evening) | Nothing blocks on them: hardware-dependent choices are config switches with safe defaults; fake-camera and synthetic tests stand in until then |
| iPhone auto exposure hunts on a dark clip | Marker-cell gain normalization; relative thresholds; track-only velocity in booth mode |
| Re-filming loses small embers | Crop or zoom in booth-prep; loss measured by the loopback check |
| Synthetic validation is self-confirming | Held-out mismatch suite supplies the headline numbers; LED test is never tuned |
| No openly licensed Korean ember footage | Synthetic data, LED and US federal footage; ask KFS for permission; gap stated plainly |
| No ground truth on real clips | Blind sample labels and plausibility checks; claims limited accordingly |
| Python too slow | Approximate median, sparse ArUco, frames dropped rather than queued; process split if needed |
| Qt fullscreen lands on the wrong screen | Screen chosen by name; frameless fallback; rehearsal |
| iPhone 13 heats up over a full day | Case off, shade, charging cable, fps watched in check C |
| One-week schedule | Deferred list and priority order; stretch goals cut first |
| Overclaiming | METHODS and LIMITS docs; units and "estimate" labels on screen; NUMBERS provenance |

## 12. What I need from you

Buy:
- Lightning to USB-C cable for the iPhone 13.
- A phone clamp, if your mini tripod lacks one.
- A rigid iPad stand, plus a charger and cable for the iPad.
- The booth 블랙박스 dashcam (you are buying it), with its SD card and a card reader.
- Black cloth for a glare hood.
- A matte iPad protector (optional).
- A 1080p30 UVC webcam.
- A cable or hub for the monitor, and a power strip.
- Three small battery orange LEDs, with tracing paper as a diffuser.
- A record turntable, or any motorized rotating platform. Its speed is timed independently, so it need not be exact.
- A tape measure.

Install: Python 3.12 from python.org on the Mac.

Record (all in sitting 1, guided step by step by `scripts/sitting1.sh`):
- LED turntable clips, top-down, dark room, with LEDs at about 3, 8 and 14 cm radius:
  - two clips of 20 s each at two speeds;
  - one 10 s clip with a ruler lying in the LED plane;
  - time 30 revolutions with a stopwatch for each speed.

  Record this set twice: once with the iPhone 13 at 30 fps and once with the booth dashcam. Share the dashcam's original SD-card files untouched.
- A short night drive (2 to 5 min, no fire) recorded with the booth dashcam, as a hard negative. It also gives lane geometry. Optional in sitting 1; it can be added later with `scripts/sitting1.sh --add night_drive`.
- A 240 fps slow-motion clip (about 5 s) of the iPad playing the panel test video, to measure the panel's scan direction.

Provide:
- C1 (the proposed booth clip): download it with a free DVIDS account and share a link when you have time. Until then, booth demos use C5, C9 or synthetic clips.
- The KFS decision on C15, when it arrives.
- Your macOS version and the monitor resolution.
- The two sitting reports (paste the short summary; the full JSON is in the upload folder).
- One share link (Drive, Dropbox or iCloud) to the sitting 1 upload folder.
- For S2: a sample CSV and GPX export plus the schema document from `field_route_logger_planning_20261003_v1/prearrival_20261003_v2/` on your Mac.
- If you want Korean footage: a permission request to KFS for the Pohang 2013 video, or your own clips.

## 13. Clip shortlist (please approve or strike)

Licenses, sizes and lengths were checked from source pages and APIs on 2026-10-14. No video was downloaded or watched. "Embers seen" means a reviewer saw embers in a poster or thumbnail frame; everything else is unverified until downloaded.

Your decisions (2026-10-14):
- C1 to C13 are approved.
- C10 is excluded from all speed and flux metrics, because its timebase is 4× slow motion. It is used only to stress tracking (flagged `metrics: tracking_only` in its clip YAML).
- C14 is kept only if it contains real ember footage. Otherwise it is deleted and logged.
- C15 is pending while you request KFS permission.

| ID | Clip | Source and license | Length, format | Role and why | Status |
|---|---|---|---|---|---|
| C1 | Night firing operation, Timber Fire, 2026-08-28 (DVIDS 1021370, 81 s cut) | USFS via DVIDS, public domain (no endorsement implied) | 82 s, 4K 29.97 fps, 95 MB | Best real night ember shower in a WUI setting (embers seen). This is my proposed booth clip. DVIDS terms need a free account, so you download it and share a link. I will not use the embed stream. | Approved |
| C2 | Holding the Line on the Dolan Fire, 2020 | US Army via Commons, public domain | 200 s, 720p30, 32 MB | Description says embers jumped a road. I'll find usable segments frame by frame. | Approved |
| C3 | Kaiser Canyon Fire extreme behavior, 2026 | USFS via Commons, public domain | 24 s, 1080p30, 18 MB | Wind-driven crown fire, likely daytime. Positive or hard case. | Approved |
| C4 | Madeira forest fire filmed from road ER110, 2017 | Strinder via Commons, CC BY 3.0 | 59 s, 1080p25, 23 MB | Wind-driven fire filmed from a road. | Approved |
| C5 | NIST Emberometer video, 2021 | NIST, public domain | 40 s, 4K30, 50 MB | Controlled ember stream (embers seen) shown next to NIST's own 3D tracks. Qualitative check of track shape. Split-screen. | Approved |
| C6 | NIST Dragon firebrand generator, 2014 (lab part only) | NIST, public domain; the Shutterstock graphic is cut | about 10 s usable, 540×360, 3 MB | Dense controlled shower (embers seen). | Approved |
| C7 | USFS RDS-2022-0071, tree-burn firebrand videos (Hudson and Blunck) | USFS archive, free use with citation | 30 videos in a 30 GB zip | Real lofted embers with images of every collected ember. I fetch only 2 or 3 files using HTTP range reads. | Approved |
| C8 | USFS RDS-2021-0069, in-fire videos (Rim Fire part) | USFS archive, free use with citation | 30 to 60 s highlights, 3.5 GB zip | Fixed CCTV-like cameras on real wildfire fronts (spotting per metadata). Subset only. | Approved |
| C9 | Peterfeuer bonfire with flying sparks, Leonstein, 2026 | Commons, CC BY-SA 4.0 | 28 s, 1080p25 night, 73 MB | Night sparks across a road at real time with a known lens. Ember-like positive. | Approved |
| C10 | Sparkler in 4K | Commons, CC BY-SA 3.0 | 144 s, 4K, 4× slow motion, 136 MB | Dense spark streaks to stress the tracker. Its timebase differs from real time. | Approved |
| C11 | Foggy Ljubljana night dashcam | Commons, CC BY 3.0 | 26 min, 1080p, 264 MB | Real 블랙박스-type hard negative with fog halos and visible lane markings. False alarms per hour. | Approved |
| C12 | Wonju road driving dashcam, 2020 | Commons, CC0 | 182 s, 1080p, 254 MB | Only Korean vehicle-view clip found. Korean lane-marking geometry; no-fire baseline. | Approved |
| C13 | Cars at night (SF) and sparks while cutting a roof | Commons, CC BY 3.0 and CC BY 4.0 | 160 s and 13 s | Hard negatives: headlights, and short spark streaks. | Approved |
| C14 | CFA "Description of Ember Attacks" | Commons, CC BY 3.0, license review pending | 175 s, 720p30, 51 MB | May be narration rather than footage. Kept only if it contains real ember footage. | Approved only if real ember footage |
| C15 | KFS Pohang Balsan-ri night suppression video, 2013 | 산림청, no KOGL mark, so permission is needed | 243 s, 13 MB | The only Korean agency night wildfire video found. Use only if you get written KFS permission. | Pending (KFS permission) |

Excluded:
- ALERTCalifornia clips: CC BY-NC-ND, which forbids derived clips.
- YouTube-only NIST, IBHS and CFA copies.
- Commons time-lapses: useless for motion.

Korean ember footage: none with an open license exists in these sources. The KTV archive may hold 2025 footage under its 2025 public-use declaration, but it needs a login and approval. Your options are a KFS or KTV permission request, or your own recordings. Wikimedia downloads are rate-limited from this network, so I download one file at a time and wait 10 minutes after any HTTP 429. The approved set without the USFS archives is about 1.1 GB, kept in `data/raw/`.

## 14. Non-goals and the honest limits we state at the booth

Non-goals:
- multi-camera 3D or depth estimation;
- ember size, mass or temperature;
- training a deep-learning detector;
- daytime ember claims;
- alerts or any safety function;
- cloud upload;
- connecting to the forecast or routing code;
- modifying the route logger;
- Windows support.

Limits, in LIMITS.md and on a ko/en booth card:
1. One camera cannot see depth. Speeds and flux are projections onto the picture. Meters per second hold only at the stated distance range; an ember twice as far away is twice as fast as shown.
2. Embers are not air. They respond to gusts with a delay of roughly 0.25 to 0.8 s (terminal velocity divided by g) and fall at about 2.5 to 8 m/s (Ellis 2010, unburnt eucalypt bark; burning embers get lighter). So the arrows are a smoothed, lagged wind estimate. The vertical component is biased downward, and there is no estimate where there are no embers.
3. Calibration is uncertain. Road markings only scale the road surface. An ember 1 m above the road, seen by a camera 1.3 m high, would be placed about 4.3 times too far away. That is why wfglink scales embers by an assumed distance range and shows the range.
4. We count only what glows and is visible, so counts are lower bounds. Our flux is per length of a line in the picture, not NIST's per square meter.
5. Validation covers synthetic video (including a held-out mismatch suite), a known-speed LED and plausibility checks. It has not been compared with an Emberometer in a real fire.
6. The booth shows a re-filmed screen at 0.5× speed. We measure how much that changes the results.

## 15. First actions after approval

1. Run `git rev-parse --show-toplevel` and check the README.
2. Create `wfglink/`.
3. Save this plan as `wfglink/PLAN.md`, and the prompt verbatim plus your later decisions as `wfglink/docs/PROMPT.md`.
4. Write the first LOG.md entry.
5. Add `.gitignore`, a README skeleton, SOURCES.md, an empty NUMBERS.json and the check scripts.
6. Create the venv, install the pins and run the smoke tests.
7. Commit `[wfglink] scaffold`, push, open the draft PR and subscribe to it.
8. Continue with M0.

## 16. Verification

- From a clean checkout, `python -m wfglink reproduce` regenerates every number and figure.
- `check_docs.py` passes and pytest is green.
- Mismatch-suite results meet or honestly miss the 4.2 goals, with reasons.
- The LED error is reported.
- Screenshots in both languages are inspected.
- Sitting reports (checks A to C) show 30 fps or more live, with automatic recovery.
- The runbook has been rehearsed once.

## 17. Changes after approval

The approved text above stays as it was; these are the departures, each with its reason and the LOG entry that records it.

- **Detection.** A Gaussian prefilter (matched filter) before thresholding is now the default (`detect.prefilter_sigma_px`). Compressed video noise is heavy tailed, and without it most detections were compression artefacts. Chosen on the core suite only (LOG, 2026-10-15T03:05).
- **Saturation** is flagged on the brightest color channel, not luma (orange embers clip red first).
- **Exposure time.** The estimator no longer iterates its own point selection (that gave two self-consistent answers with short streaks). It fits once on fixed speed cuts and declines, with a stated reason, unless the answer is stable and the streak lengths are shown to be proportional to speed. On the synthetic core suite it declines every clip, because measured streak lengths are not yet proportional to true length (a floor for short streaks, lost ends for long faint ones). Fixing the length measurement (the erf or segment model fit deferred in section 9) is now a task.
- **Tracking.** Process noise adapts per track (wide for turning targets such as the LED turntable, narrow for smooth embers), the search gate is limited by the local detection density, coasting is up to 5 frames instead of 3, and coasted gaps are filled by a cubic curve in file mode. Dense showers had many identity switches from wrong associations during flicker dropouts.
- **Repeated frames** are detected by changed pixels at full resolution and, for lossy re-encodes, by the embers not having moved; thumbnail differences dropped real frames of night scenes.
- **Booth hold rule (sections 4.3 and 9).** The 80 percent clean-frame yield rule is replaced by a coverage rule (`sitting2.hold_rule: coverage`). With a scanning 60 Hz panel and a global-shutter camera, the clean-frame yield at hold 2 is close to 1.0 or to 0.5 depending on the camera's phase and averages below 0.8 over phases, while every source frame is still read clean at least once whenever the unclean time per content change is shorter than one camera frame. Check B now measures source coverage over several camera restarts (new phases) and keeps hold 2 only when every window covers the clip and spare clean views show margin; otherwise hold 3. The yield is still reported, and `hold_rule: yield` restores the old rule.
- **Source health in booth mode (section 7)** is implemented as written: a live camera must keep reading advancing frame codes; a paused iPad shows "iPad 정지 · iPad paused" and the chain falls back.
- **Demo tags.** This cloud session's git proxy refuses tag pushes, so each passing build is recorded in DEMO_BUILDS.md on the branch with the command that makes the tag.
- **Validation metrics.** An oracle audit (truth fed in as perfect estimates) found and fixed scoring bugs before any number was recorded: the field truth window, signed medians in summaries, gate truth inside flame regions, CLEAR MOT persistence across dropouts, and repeated frames in the bridged gate truth. Detection is also reported as completeness against ember SNR, and counts are checked between the bright-ember and all-visible truths.
