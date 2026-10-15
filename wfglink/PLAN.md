# wfglink plan: measuring embers and ember-derived wind from ordinary camera video

Version 6, 2026-10-15 (Asia/Shanghai). Version 6 follows your booth change of 2026-10-15: the LED turntable test is dropped completely (the led suite, its notes file and the turntable steps are gone); key A fades the fire footage between the raw clip and the full overlay; and a second booth mode, "Become an ember", tracks visitors' phones showing a glowing ember page through the MacBook's own camera or a USB webcam, with speeds in m/s measured at a 2.0 m standing spot (sections 1, 3, 4.4 and 7). The two sittings are now: sitting 1 (setup, camera and permission, the A4 calibration at the standing spot, the recordings `ember_free` and `ember_ruler`, validate, send files) and sitting 2 (update, booth, overnight soak, rehearsal). The target stays Monday 19 October, and the always demo-ready rule stays (section 9). Version 5 dropped the live camera of the earlier versions and made the booth real-time file playback. Version 4 replaced the five Mac check-ins with two hands-on sittings. Version 3 was approved with changes on 2026-10-14. Version 2 added the fixes from an independent review covering measurement science, booth engineering and requirements coverage. Version 3 adds your six approval changes:
- dashcam (블랙박스) file-mode check;
- an always demo-ready tagged build;
- a schedule around your 18 October submission;
- clip decisions;
- booth screen priority;
- hardware substitutions.

## 1. Context

During a wildfire nobody measures how many embers fly, where, or how fast, and nobody measures street-level wind inside communities. Spotting (비화) carried the March 2025 Uiseong fire up to about 51 km from its western front to Ganggu port on the Yeongdeok coast within about 12 hours. That is KFS analysis with NIFOS mapping, reported by Newsis on 2025-03-27. It describes cumulative spread through repeated spotting, not one ember flight. NIST's Emberometer measures embers with four synchronized cameras and 3D particle tracking, but only where it is installed before a fire.

wfglink treats glowing embers as tracer particles in ordinary video: dashcams (블랙박스), CCTV and phones. It runs in two ways:
- File mode works on clips at full quality.
- The booth is one fullscreen app on the M4 Pro MacBook, on the external monitor when one is connected, otherwise on the MacBook's own screen. It has two modes, and key M switches between them (your booth change of 2026-10-15):
  - Fire mode, where the booth starts, is real-time file playback (your setup change of 2026-10-15): the approved clips of a playlist play at their own speed and each frame is analysed live as it plays. Nothing is filmed off a screen. Key A fades between the raw footage and the full overlay (ember trails, wind arrows, counters) in about 0.5 s; the booth starts with the overlay on.
  - "Become an ember" (당신이 불티입니다) is live: visitors open a web page on their phone that fills the screen with a glowing orange ember, stand on a floor mark 2.0 m from the camera (the MacBook's own camera or a USB webcam) and move the phone. wfglink tracks the phones as it tracks embers, up to 6 at once: each gets a trail, an ID and a speed in m/s measured at 2.0 m, and the wind arrows come from all tracked phones. Visitors see the method work on themselves: their phone is the ember.

The booth dashcam stays on its stand next to the screen as the "This is the sensor" exhibit: the kind of ordinary camera wfglink reads.

What scouting established:
- The repo has no video or OpenCV code, so wfglink starts from scratch and copies only conventions (exact pins, NUMBERS provenance, Korean-first booth screens, contrast and dash checks).
- The route logger is not in any git ref. It is an ESP32 + Quectel L76K GNSS device with planned CSV and GPX exports, and its schema exists only on your Mac.
- The schedule is one week of continuous work by me. Everything is ready by Monday 19 October; Tuesday 20 and Wednesday 21 are buffer.

## 2. Ground rules

- Scope: everything stays inside `wfglink/`. Nothing outside it is created, edited, moved or deleted, and no forecast, routing or monte-carlo code is imported.
- Git:
  - `git add wfglink/` only, with commit messages prefixed `[wfglink]`.
  - No branch switching, stash, rebase, reset or force-push. On `.git/index.lock`, wait and retry.
  - Push to `claude/practical-rubin-5vu12u` (approved) and keep one draft PR to Main.
  - Demo tags, from M2 onward:
    - Each day I tag the latest commit that passes the demo gate as `wfglink-demo-YYYYMMDD` and push only that tag.
    - Demo gate: the live UI runs end to end for 60 s offscreen on synthetic video, on the booth playlist and in ember mode on generated phones (no camera needed), with no errors, started by the single booth command.
    - The tag name and commit go into LOG.md each day.
    - If a later milestone breaks something, the previous tag is still a working demo.
  - Before every commit, `scripts/check_staged.py` fails if a staged file is a video or larger than 5 MB. I run it myself, because a git hook would live outside wfglink/.
- `.gitignore` covers: `.venv/`, `data/raw/`, `data/synthetic/`, `data/booth/`, `results/runs/`, `build/`, `dist/`, `*.app`, video extensions (mp4, mov, m4v, mkv, avi, webm) and caches.
- Python:
  - Python 3.12, venv at `wfglink/.venv`, exact pins in `requirements.txt`.
  - Pins: numpy, scipy, opencv-contrib-python-headless 4.14.x (its ArUco module reads the A4 calibration target), PySide6 6.12, av (PyAV, bundles FFmpeg), pyarrow, pandas, pyyaml, matplotlib, pytest. On macOS only: pyobjc with its AVFoundation framework, for the camera permission and the camera names in ember mode.
  - On the Mac, `scripts/setup_mac.sh` creates the venv with Python 3.12 from python.org and installs the pins; it is safe to run again.
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

Data flow of the fire footage, shared by file mode and the booth's fire mode through one `Pipeline` class:

1. Source (a file, the real-time playlist player of the booth, or synthetic video) gives a frame and its true timestamp.
2. Detection.
3. Streak measurement.
4. Tracking.
5. Velocity.
6. Gate counts and flux.
7. Ember velocity field.
8. Optional metric scaling.
9. Outputs: tables, summary JSON, overlay video and the live dashboard.

Ember mode has its own `EmberPipeline` (`src/wfglink/ember/`), tuned for phone screens: a camera frame, mirrored so that a visitor moving right moves right on screen; detection of the phones' embers; tracking of at most 6; speeds in m/s at the standing distance; and the ember velocity field from all tracked phones. It fills the same `LiveState` the booth screen draws, so both modes share one renderer and one design.

```
wfglink/
  README.md PLAN.md LOG.md DEMO_BUILDS.md pyproject.toml requirements.txt .gitignore
  configs/      default.yaml, suites/*.yaml, synth/*.yaml (every threshold lives in config)
  src/wfglink/  io/ (files, playlist, camera) detect/ track/ measure/ ember/ pipeline.py render/ outputs/ ui/ synth/ validate/ viz/ soak.py doctor.py provenance.py cli.py
  scripts/      setup_mac.sh, mac_soak.py, fetch_clips.py, run_suite.py, make_placards.py, make_calibration_target.py, check_docs.py, check_staged.py, tag_demo.sh
  booth/        booth.sh, booth.command (double-click), playlist.yaml, ember/ (index.html, the phone page; calibration_target_A4.pdf), placards/ (A5, ko and en), BOOTH_RUNBOOK.md (ko/en)
  assets/fonts/ Pretendard OTF (SIL OFL 1.1) + license
  tests/        pytest unit and integration tests
  data/         SOURCES.md, clips.csv, clips_manifest.yaml, clips/<clip_id>.yaml (tracked); raw/ (clips and your ember recordings), synthetic/ (ignored)
  results/      NUMBERS.json, validation/, figures/ (tracked, small); runs/ (ignored)
  docs/         PROMPT.md, METHODS.md, LIMITS.md (ko/en), SITTING1.md, SITTING2.md
```

The CLI is `python -m wfglink` with these commands: `doctor`, `live`, `process`, `plausibility`, `label-tiles`, `label-score`, `validate --suite core|mismatch|coverage|ember`, `demo-gate`, `cameras`, `calibrate`, `record`, `synth` and `reproduce`. Every input and output path is a flag or config key, so the same commands run on your Mac.

- `live [--synthetic | --playlist FILE | --clip PATH] [--ember] [--fake-camera FILE] [--screen auto|external|primary|NAME] [--lang ko|en] [--limits-screen NAME]` is the booth screen. It starts in fire mode on the playlist (`booth/playlist.yaml`, config `booth.playlist`) unless a source flag names other footage; `--ember` starts it in ember mode. In ember mode without a camera, or with `--fake-camera FILE`, it shows generated phones, or that file, as if they came from a camera.
- `doctor` prints one line per check (Python, packages, fonts, screens), each ending in OK or FAIL with a fix hint.
- `cameras [--request]` lists the cameras (name, kind, usable or why not) and the one the config picks; `--request` asks for camera permission (the macOS dialog) and prints the answer.
- `calibrate [--distance-m D] [--video FILE]` is the one-command calibration with the printed A4 target held at the standing spot (section 7).
- `record NAME [--seconds S]` records the configured camera to `data/raw/NAME.mp4` (H.264), with a countdown on screen.
- `validate --suite ember` is the ember mode validation (4.4); `--suite core|mismatch|coverage` are the synthetic suites of the fire footage (4.1).

### Modules

Parameters live in configs and METHODS.md.

| Module | Method |
|---|---|
| Input | Files: PyAV with true presentation timestamps (handles variable-frame-rate phone and dashcam clips). Duplicated frames are detected by content (difference below noise) and excluded from velocity. Booth playback: a player thread decodes the playlist's clips and paces their frames against a monotonic clock, so each clip plays at its own speed. It keeps only the newest frame (a one-slot buffer): when the analysis is busy, frames are skipped, never queued, so the picture never lags. Each clip plays over its approved segments, cropped to its region of interest, and a cut restarts the tracks. A missing clip is skipped; when nothing can play, synthetic video plays with its tag. Synthetic: the generator renders frames live. |
| Detection | Luma background via an approximate running median (sign update, cost close to 1 ms). An exact median is a file-mode option. Then a white top-hat and a noise-relative threshold with hysteresis, then connected components. Big bright regions (flames, headlights) are masked, and anything static for more than 1 s is rejected. Color is only a confidence score, because 4:2:0 compression smears small blobs. Saturated blobs are flagged. |
| Streaks | Second moments of background-subtracted intensity in a dilated window, corrected for noise: L = sqrt(12(λ1 − λ2)). Orientation mod 180°. Collinear fragments (within 10°, gap no more than L/2) are merged first, so a dashed streak caused by in-exposure flicker stays one ember. |
| Tracking | In-house constant-velocity Kalman filter. The cost is Mahalanobis distance (gate chi-square 9.21) plus a penalty when streak and motion directions disagree. Hungarian assignment. A track confirms after 3 hits in 4 frames and may coast for 3 frames. |
| Velocity | Track: velocity from a Savitzky-Golay derivative against true timestamps, correcting the known gain. Streak: speed = L / T_exp. Exposure: T_exp in seconds comes from metadata when present. Otherwise it is a robust Deming regression through the origin of L on track speed, fitted over a rolling 10 s window on clean, fast, unflagged tracks only. Its uncertainty is carried as a shared error. Reporting: track-only, streak-only and fused speeds are reported separately. Fusion is used only for tracks shorter than 5 points. |
| Gate and flux | A line gate with crossing hysteresis counts each track once per direction. Count rate: crossings per second over the last 10 s. Cumulative Particle Count (gate): gross and net counts. Particle Number Flux (projected, 2D): crossings per second per unit gate length. The unit is per 100 native px when uncalibrated, per degree of view angle with intrinsics, or m⁻¹ s⁻¹ "at Z = ... m". Uncertainty: a moving-block bootstrap over 1 s bins, combined with the detection efficiency measured on synthetic data. The names mirror NIST as you asked, but the screen and docs state that they are analogous to, not comparable with, NIST CPC (m⁻²) and PNF (m⁻² s⁻¹), which use a 3D surface. |
| Ember velocity field | 16×9 cells. Each track contributes one sample per cell. Median, MAD rejection and the normalized median test across neighbors. Cells with fewer than 5 tracks are hidden. Cells with 5 to 9 are hatched with no confidence interval. Cells with 10 or more get a bootstrap confidence interval. Label: "Ember-derived air velocity (estimate)". Notes: the horizontal component is the wind proxy; the vertical component includes settling and is marked biased. |
| Calibration | Pixels by default. A ground-plane homography (from lane dashes or clicked points) only estimates camera height, pitch and focal length. It is never applied to airborne embers. Ember meters: m/px = Z/f, with an assumed distance interval [Z_min, Z_max] per clip, reported as the speed interval [v(Z_min), v(Z_max)]. That interval is kept separate from a Monte Carlo confidence interval for f and the clicked points. Korean lane-dash lengths: cited and checked before use. ChArUco intrinsics are deferred. |
| Outputs | Parquet tables (CSV by flag), summary JSON, and an H.264 overlay video. The overlay is drawn by the same QImage and QPainter renderer as the live UI, with no QPixmap, so it can run off the GUI thread. |
| Camera (ember mode only) | `io/camera.py`. The devices come from AVFoundation on macOS (name, unique ID, kind: built-in, USB, Continuity Camera, Desk View or other) and map to OpenCV's indices. Continuity Camera and Desk View devices are never used, so an iPhone nearby is never picked. `camera.name` is auto (a USB UVC webcam when one is connected, else the built-in camera) or part of a device name. Camera permission is requested on the main thread before any capture thread starts, on first use or ahead of time with `cameras --request`. Frames come at `camera.width` × `camera.height` and `camera.fps` (1280×720 at 30 by default) with monotonic timestamps; after a failure the camera is reopened with backoff. A fake camera plays a file or generated phones like a camera (tests, the demo gate, Linux). |
| Ember pipeline (ember mode) | `ember/`. Tuned for phone screens 1 to 3 m away indoors. The frame is mirrored (`ember.mirror`), then the phones' embers are detected and tracked, at most `ember.max_tracks` (6) at once, each with a trail, an ID and a speed; room lights and other static bright objects never become tracks. The speed card shows the median over the embers on screen. The wind arrows come from all tracks of the last `ember.field_window_s`, and a cell shows with at least `ember.field_min_tracks` tracks. |
| Scale in ember mode | m/s at the standing distance Z = `ember.distance_m` (default 2.0 m): m/px = Z / f, labelled "measured at 2.0 m". The focal length f in px (`camera.focal_px`) comes from the A4 calibration; without one it comes from the camera's nominal horizontal field of view (`camera.hfov_deg`) and is marked uncalibrated (`calibrated` false). A phone nearer or farther than the standing spot shows a speed wrong in proportion (limit 1). |
| A4 calibration | `calibrate`: a printed A4 target (`booth/ember/calibration_target_A4.pdf`, made by `scripts/make_calibration_target.py`: four ArUco markers at known positions, a 100 mm line to check the print scale, "print at 100 percent") is held flat at the standing spot, facing the camera. The camera shows fullscreen on the Mac; the markers are detected and f follows from their known spacing at Z, averaged until stable. `camera.focal_px` and an `ember.calibration` record (date, camera name, size, f, m per px at Z, target) go into `configs/booth_local.yaml`, and the equivalent horizontal field of view is printed as a check. `--video FILE` runs it on a recording. |
| Ember page | `booth/ember/index.html`, one self-contained file with no external requests, so it works from GitHub Pages or any static host. A black background and a centred glowing disc (radius 0.36 of the screen's shorter side; a radial gradient: #FFF1D6 at the centre, #FFC266 at 18 percent, #FF8A1F at 45 percent, orange at 35 percent opacity at 70 percent, transparent at the edge) with a slight, smooth flicker (brightness 0.85 to 1.0, scale 0.97 to 1.0, at about 2 to 6 Hz). It keeps the screen awake where the browser allows (Screen Wake Lock, which needs HTTPS) and shows a short ko/en instruction that fades out after 3 s. |

### UI: native PySide6, one process

Recommended over a local web app.
- Frame path: frames go from numpy to QImage to a custom QWidget. A web app would add a JPEG encode and decode per frame, a second process and a kiosk browser.
- Hangul: renders through QPainter with Pretendard, falling back to Apple SD Gothic Neo. OpenCV cannot draw Hangul.
- Display: Qt puts the window fullscreen on a chosen QScreen and handles monitor hot-plug. With `--screen auto` (the default) the booth goes to the external monitor when one is connected, else to the MacBook's own screen, and moves when a monitor is plugged in or out.
- Offline: works offline by construction.
- One renderer: the same renderer draws the booth screen and the exported videos.
- Testable here: in headless mode (`QT_QPA_PLATFORM=offscreen`) I can render and inspect 1920×1080 screenshots in both languages.

Threads:
1. A playback thread (the real-time player, in fire mode) or a camera thread (ember mode) fills a one-slot buffer with the newest frame.
2. A processing thread takes the newest frame whenever it is free and emits an immutable Result, which owns its array and keeps it referenced next to its QImage, through a queued signal.
3. The GUI repaints only when a new Result arrives.

The worker pre-scales frames to widget size × device pixel ratio, so drawing is 1:1. Playback and processing can also run in a child process that hands frames over in shared memory. Both ways exist behind `live.worker_mode: thread | process` (thread is the default), so a Mac that cannot keep up is a config flip, not new code.

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
  - Ember mode keeps this design: the camera picture with the phones' glowing trails and IDs on the left; the header "당신이 불티입니다 / You are an ember"; the live count of embers; each ember's speed in m/s, marked "measured at 2.0 m"; and the wind arrows from all tracked phones.
- Tags: "추정치 · Estimate" and "보정 안 됨 · Uncalibrated (px)" stay small but always visible, next to the values they qualify. The clip's name and credit line, and the fps, sit in a small status line. Synthetic video always carries "합성 영상 · 실측 아님 · Synthetic video · not measured".
- Limits card (ko/en): not on the main screen permanently. It appears on key I, or permanently on an optional second display (`--limits-screen`), and is printed as an A5 placard for the booth.
- Keys: L language, T tracks, F field, G gate, Space pause (playback and analysis hold), I limits card, A raw or analysed (the fire footage fades between the raw clip and the full overlay over `ui.raw_fade_s`, 0.5 s; the booth starts analysed), M fire or ember mode (the booth starts in fire mode), Esc quit with confirm (Esc, then Esc again).
- Contrast is tested against WCAG AA.

### Frame rate and resolution targets

All values are measured and recorded in NUMBERS.json.
- Booth playback: each clip plays in real time at its own frame rate (the approved clips are 25 to 30 fps). Frames are analysed and shown at most 1280 px wide and 1280×720 pixels (`live.analysis_max_width`, `live.analysis_max_pixels`); larger frames, such as 4K clips, are scaled down while they are decoded.
- Target on the M4 Pro: every played frame analysed and painted, so the analysed rate equals the clip's frame rate (30 fps for a 30 fps clip), with whole-loop processing at most 15 ms median and 25 ms p95 with the UI running. When the analysis cannot keep up, frames are skipped rather than queued; when decoding alone is slower than real time, the clock restarts at the current frame and the clip plays on slower. The overnight soak logs the rate all night (section 7).
- Ember mode: the camera's frames (1280×720 at 30 fps by default) are analysed and painted as they arrive, newest first; a frame the analysis cannot take is skipped, never queued, so the trails follow the phones without lag.
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
| spot | Format check: 1080p, 60 fps and H.265. | 10 clips |
| ember | Ember mode (4.4): synthetic phone scenes with ground truth, then your two recordings. Never used for numbers about real embers. | Generated from fixed seeds on each run |

The loop suite (a camera-in-the-loop simulator) is dropped with the live camera (4.3).

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
| Live analysis time during playback and in ember mode | Section 3 targets |

### 4.3 Camera in the loop (dropped)

Dropped by your decision of 2026-10-15: the booth now plays the clip files themselves, so there is no re-filmed screen to test (no frame codes, held frames, loop suite or loopback check).

### 4.4 Ember mode validation (synthetic phones and your recordings)

The LED turntable test is dropped (your booth change of 2026-10-15). Ember mode is checked with `python -m wfglink validate --suite ember [--raw DIR] [--phones N] [--path-m 1.0]`, which writes `results/validation/ember_report.json` and prints a short summary. The goals are fixed before measuring; missed goals are reported with their reasons.

Synthetic phone scenes, generated from fixed seeds with ground truth: phone screens showing the ember page's disc and flicker, 1 to 3 m from a camera with the booth camera's field of view, moving, turning, crossing and resting, up to six at once (`--phones N`), in a room with lights and other static bright objects, with camera noise.

| Metric | Goal |
|---|---|
| Detection recall of the phones on screen | ≥ 0.95 |
| Tracks on room lights and other static bright objects | None |
| Identity switches | ≤ 1 per phone per minute |
| Speed error at the standing distance (median relative error of the m/s speeds, phones at 2.0 m) | ≤ 10% |
| Detection precision and false tracks per minute | Reported |

Your recordings (sitting 1), made with `python -m wfglink record NAME` on the booth camera after the A4 calibration, at the standing spot, with the page open on your phone:
- `ember_free`: you move the phone freely at the standing spot for about a minute. With one phone in view, every track that is not your phone is a false track, and a new track while the phone stays in view is an identity switch; the report gives detection and tracking quality from these.
- `ember_ruler`: the known motion. A 1 m path is marked at the standing spot, across the camera's view and at the standing distance: two tape marks 100 cm apart on the front edge of a table placed there. The phone rests at the 0 mark, is moved to the 100 cm mark in about 1 s, and rests again. The move time is taken from the video (the phone leaves rest and comes to rest), so no stopwatch is needed. Truth: 1 m (`--path-m`) in that time. Measured: the tracked distance in m at the calibrated scale, and the mean speed over the move. Both are reported against the same 10% goal as the synthetic phones.

The recordings never tune anything; a recording used for debugging is named in LOG.md and left out of the reported numbers. Ember mode checks the booth's own measurement of phones; it is not counted as validation of real ember measurement (limit 5).

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
  - `data/raw/ember_free.mp4`, `data/raw/ember_ruler.mp4`: your ember mode recordings (4.4), never committed.
  - `data/clips/<clip_id>.yaml`: gate, ROI, approved segments, Z interval, calibration points, time offset, split.
  - `booth/playlist.yaml`: the approved clips the booth plays, by clip id (section 7).
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
| frames.parquet | frame, t, source index, detections, active tracks, count rate, CPC gross/net, PNF, duplicate flag, T_exp, processing ms |
| tracks.parquet | track_id, start/end, points, u, v, speeds (track, streak, fused), direction, residual, crossings, flags |
| field.parquet | window, cell, u, v, n_tracks, CI |
| summary.json | input SHA-256, metadata, config hash, git commit, versions, units and calibration state, totals with CIs, T_exp, plausibility flags, warnings |
| overlay.mp4 | H.264, drawn by the live renderer |

Live recording of the same tables is off by default. When on, ParquetWriter flushes every 10 s.

Ember mode stores no camera picture: it is shown live and dropped. Only `record` writes video (`data/raw/NAME.mp4`), `calibrate` writes the calibration into `configs/booth_local.yaml`, and `validate --suite ember` writes `results/validation/ember_report.json`.

## 7. Booth operation

- One command, from `~/wfglink-run/wfglink` on the Mac: `./booth/booth.sh`, or double-click `booth/booth.command` in Finder, which runs the same in Terminal. It keeps the Mac awake with `caffeinate` and supervises `python -m wfglink live --heartbeat logs/heartbeat.json`, passing on any live options (for example `--lang en` or `--screen NAME`):
  - Esc, then Esc again in the app (a prompt shows after the first), is a clean exit: the supervisor stops too and exits 0;
  - a crash, any other exit, or a hang restarts the app after 2 s, doubling up to 60 s while it keeps failing quickly; a hang is a heartbeat older than 30 s, or no new analysed frame for 90 s while playback is not paused;
  - Control-C in Terminal, or SIGTERM, stops the app and the supervisor (exit code 130);
  - logs: `logs/booth.log`, rotated at 10 MB × 5 files; the app rewrites `logs/heartbeat.json` every 2 s (status, fps, the clip playing, pause, memory, pipeline counters, the mode, raw or analysed, and the camera state).
- No `.app` launcher and no launchd: the one command is enough. The booth runs in Terminal, so Terminal is the app that holds the camera permission.
- Two modes. The booth starts in fire mode; M switches to ember mode and back.
- Fire mode, the playlist: `booth/playlist.yaml` (config `booth.playlist`) lists approved clips by their settings file `data/clips/<id>.yaml`. Each clip plays in real time over its approved segments, cropped to its region of interest, and the playlist loops for ever. Every clip start resets the counts, so the numbers on screen belong to the clip playing (`booth.reset_per_clip`). A clip whose file is not in `data/raw/` is skipped and tried again on the next loop; when nothing can play, synthetic video plays with its "not measured" tag, so the screen is never black. The status line names the clip and its credit line. `live --clip PATH` plays one clip and `live --synthetic` plays generated video.
- Fire mode, raw or analysed: A fades the fire footage from the full overlay (ember trails, wind arrows, counters) to the raw clip over `ui.raw_fade_s` (0.5 s), and A again fades it back. The booth starts analysed.
- Ember mode, "Become an ember":
  - Camera: `camera.name` in the config, auto by default (a USB UVC webcam when one is connected, else the MacBook's own camera), or part of a device name as `python -m wfglink cameras` lists them. Continuity Camera (an iPhone) and Desk View are never used. The camera faces the standing spot from the booth table or the top of the monitor, with no window or bright lamp in its view if possible.
  - Permission: macOS asks once whether Terminal may use the camera. Sitting 1 answers it with `python -m wfglink cameras --request`, so the booth day never stops at a dialog. Without a camera or without permission, ember mode shows generated phones instead, so the screen is never black, and the heartbeat's camera state says what is wrong.
  - Video effects off: Center Stage, Portrait, Studio Light, Background and Reactions crop, blur or draw on the picture, and Center Stage changes the scale. They are switched off in the Video menu (the green camera icon in the menu bar while the camera is in use).
  - The page: visitors open the ember page (`booth/ember/index.html`, on GitHub Pages; any static host works) on their phone from the address on a card at the standing spot, turn the screen brightness up, and hold the phone with the screen to the camera. The page keeps the screen awake where the browser allows and shows a short ko/en instruction that fades after 3 s.
  - Standing spot: a tape mark on the floor `ember.distance_m` (2.0 m) from the camera lens, measured with the tape measure, straight in front of the camera. Speeds are in m/s, marked "measured at 2.0 m"; a phone held much nearer or farther shows a speed wrong in proportion (limit 1).
  - Calibration: `python -m wfglink calibrate` with the printed A4 target held flat at the standing spot, facing the camera; in sitting 1, and again whenever the camera, its place or its resolution changes. It writes the result into `configs/booth_local.yaml`. Without it, the scale comes from the camera's nominal field of view.
  - Privacy: the camera picture is shown live, mirrored, and never stored or sent. Nothing is recorded in the booth unless the operator runs `python -m wfglink record`.
- Screen: `--screen auto` (the default, `ui.screen`) puts the booth fullscreen on the external monitor when one is connected, else on the MacBook's own screen. Plugging the monitor in or out moves the booth there by itself. `external`, `primary` or a screen name (as `doctor` lists it) override the choice. `--limits-screen NAME` keeps the limits card on a second screen.
- Keys: L language, T tracks, F field, G gate, Space pause (playback and analysis hold; Space again resumes), I limits card, A raw or analysed fire footage, M fire or ember mode, Esc then Esc again to quit.
- "This is the sensor" exhibit: the booth dashcam on its stand next to the screen, with its A5 placard from `booth/placards/` (Korean and English): the kind of ordinary camera wfglink reads, and what wfglink measures from such video. The limits card is printed as an A5 placard too; it takes its text from the same strings as the screen's limits card, so paper and screen agree.
- Overnight soak: `python scripts/mac_soak.py --hours 8` runs the booth exactly as on the day (through `booth.sh`, in fire mode with the playlist) for 8 hours, samples the heartbeat (fps, memory) into `logs/soak/`, and prints a PASS or FAIL report at the end, or when stopped with Control-C. Its checks (paint rate, memory growth, restarts and hangs, analysis stalls, errors) and their thresholds are commented keys in the config's `soak:` section.
- Runbook: `booth/BOOTH_RUNBOOK.md` (ko/en) covers the setup checklist (the floor mark and the page's address card included), both modes and every key, plugging the monitor, recalibrating with the A4 target, what to do when the camera shows nothing or permission is missing, when the screen freezes or the app restarts, and the placards.

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

Times are Asia/Shanghai. The target is Monday 19 October: everything built, tested and documented for the booth, both modes included. Tuesday 20 and Wednesday 21 are buffer. Your hands-on work happens in two sittings. I keep building without blocking on you, and what depends on your hardware is a config switch with a safe default, so a late sitting causes no rework.

Your Korea Code Fair submission deadline is Sun 18 October. The demo builds (DEMO_BUILDS.md) are ready if you want to show wfglink in that submission.

Always demo-ready (your rule): each day I record the latest build that passes the demo gate (section 2) in DEMO_BUILDS.md and LOG.md, so a later break never leaves you without a working demo. The booth change is built in separate worktrees and merged only when its tests and the demo gate pass; until then the previous build stays the demo.

M0 (Wed 14 night: scaffold, records, environment, detector) is done.

| When | Deliverables | Done when |
|---|---|---|
| M1 Thu 15 | Synthetic generator with ground truth, tracker, velocity, exposure estimator, gate counts, metrics and the core numbers (done); booth screen and demo builds (done); the setup change: the real-time playlist player, screen choice and hot-plug, Space pause, `booth.sh`, `setup_mac.sh`, `doctor`, `mac_soak.py` and the placards (done). The booth change: the LED test removed; key A; ember mode with the camera and its permission (`cameras`), the ember pipeline, the page, the A4 target and `calibrate`, `record`, `validate --suite ember` on synthetic phones, and the ember screen with key M; this plan, both sitting checklists and the runbook | The four parts are merged and their tests pass here; the demo gate passes on synthetic video, on the playlist and in ember mode on generated phones; the page passes its check in headless Chromium |
| M2 Fri 16 | Fix for the false detections on bright real scenes (LOG, 2026-10-15T09:40); streak length fix and exposure in the pipeline; ember field; flux CIs; each playlist clip checked on the booth screen, raw and analysed; ember mode checked against the 4.4 goals on synthetic phones | The playlist clips look right on the booth screen; the ember goals are met or their misses explained; demo build logged |
| M3 Sat 17 | Core and mismatch suites with figures; plausibility checks (4.5); calibration | Headline numbers from the mismatch suite |
| M4 Sun 18 | Your submission deadline. Coverage suite; profiling of playback, analysis and ember mode; METHODS, LIMITS, runbook, README; your ember recordings folded in as soon as the sitting 1 files arrive | `reproduce` regenerates everything |
| M5 Mon 19 (target) | Freeze: final checks and final demo build; ready for sitting 2 | Clean tree, checks green, final demo build recorded |
| Tue 20, Wed 21 | Buffer: results from the sittings folded in, fixes after the rehearsal; S1; S2 only with a logger export | Nothing from the sittings left open |

Deferred unless ahead of schedule: erf streak refinement, four-frame tracking, IDF1, H.265 beyond the spot check, ChArUco intrinsics, property-based tests. If time slips, I protect this order: core measurement with synthetic validation and file mode; the booth playback screen with its supervisor and key A; ember mode (camera, tracking, the page, calibration); real clips; calibration polish; stretch goals.

### Your two sittings

Each sitting has a checklist, and every command in it exists as written. Run everything from a separate worktree, so your other sessions' checkout is never switched:

```
git fetch origin claude/practical-rubin-5vu12u
git worktree add ~/wfglink-run origin/claude/practical-rubin-5vu12u
```

Later updates:

```
git -C ~/wfglink-run fetch origin
git -C ~/wfglink-run checkout --detach origin/claude/practical-rubin-5vu12u
```

Sitting 1, as soon as your parts arrive (you tell me the date): setup, camera and permission, the A4 calibration at the standing spot, the recordings, validate, send files. Checklist `docs/SITTING1.md`, about 90 minutes.
1. Setup: the worktree; `cd ~/wfglink-run/wfglink`; `./scripts/setup_mac.sh`; `source .venv/bin/activate`; `python -m wfglink doctor` (every line ends in OK); `python -m wfglink live --synthetic` (the full booth screen on generated video; each fire-mode key once, A included). The approved clips start downloading in a second window (`python scripts/fetch_clips.py`), so the booth has them in sitting 2.
2. Camera and permission: the USB webcam plugged in if you use one; `python -m wfglink cameras --request` (allow Terminal to use the camera; it prints the answer, the cameras and the one the config picks); `python -m wfglink live --ember` to see the camera picture and switch the video effects off.
3. The page: `booth/ember/index.html` published on GitHub Pages and opened on your phone.
4. The A4 calibration at the standing spot: the camera where it will stand at the booth; a tape mark on the floor 2.0 m from the lens; the A4 target printed at 100 percent, its 100 mm line checked with a ruler; `python -m wfglink calibrate` while you hold the target flat at the mark, facing the camera.
5. Recordings at the standing spot, with the page on your phone: `python -m wfglink record ember_free --seconds 60` (the phone moved freely) and `python -m wfglink record ember_ruler --seconds 15` (the 1 m path: at rest on 0, to 100 cm in about 1 s, at rest).
6. Validate: `python -m wfglink validate --suite ember` prints a short summary and writes `results/validation/ember_report.json`; then `python -m wfglink live --ember` with your phone at the mark (M to fire mode and back, Esc twice).
7. Send files: `ember_report.json`, the two recordings and `configs/booth_local.yaml` through one share link, with the page's address.

Sitting 2, the final evening before the booth (from Mon 19, once everything is ready), with the rehearsal the next morning: update, booth, overnight soak, rehearsal. Checklist `docs/SITTING2.md`.
1. Update: the two update commands above; `./scripts/setup_mac.sh` again (safe to repeat); `python -m wfglink doctor`; the clip download again, which fetches only what is new. The A5 placards printed.
2. Booth: `./booth/booth.sh` on the external monitor; each key once in fire mode (L, T, F, G, Space, I, A); M to ember mode with a phone at the floor mark, then M back; the monitor unplugged and plugged back in; Esc twice.
3. Overnight soak: `python scripts/mac_soak.py --hours 8`. In the morning it has printed a PASS or FAIL report, which you paste to me.
4. Rehearsal: `booth/BOOTH_RUNBOOK.md` from a cold start, with both modes, the floor mark, the page's address card, and the dashcam and its placard on the table.

What remains a switch, each with a safe default:

| Switch | Default | Set by |
|---|---|---|
| `ui.screen` (or `--screen`) | auto: the external monitor when connected, else the MacBook's screen | Sitting 2, only if the booth lands on the wrong screen |
| `live.worker_mode` | thread | Sitting 2, only if the soak shows the analysis falling behind |
| `booth/playlist.yaml` | approved clips I have checked on the booth screen | Me; C1 joins when you share it |
| `camera.name` | auto: a USB UVC webcam when connected, else the MacBook's camera | Sitting 1, only if `cameras` shows the wrong pick |
| `ember.distance_m` | 2.0 m, the floor mark | Only if the booth space needs another distance: set it, move the floor mark and calibrate again with `--distance-m` |
| `camera.focal_px` and `ember.calibration` | none: the scale comes from the nominal field of view (`camera.hfov_deg`) | `calibrate`, in sitting 1 and after any camera change |

Machine-specific switches go in `configs/booth_local.yaml`, which is not tracked and which the booth reads on top of the defaults.

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
  - i18n keys complete in both languages, with limits 1 to 5 in both;
  - contrast ≥ 4.5:1;
  - Pretendard actually loaded (QFontInfo family check);
  - no QPixmap in the renderer;
  - no em dashes.
- Booth playback:
  - the player paces frames in real time, drops late frames instead of queuing them, restarts its clock when decoding falls behind, keeps segments and cuts apart, skips a missing clip and falls back to synthetic video when nothing plays;
  - Space pause holds playback and analysis;
  - screen choice with fake screens: external when present, else the built-in screen, and a move on hot-plug;
  - the supervisor (`booth.sh`) with a fake app: clean exit gives 0, a crash or a hang restarts with backoff, SIGTERM or SIGINT gives 130; checked with `bash -n` here, since caffeinate exists only on macOS.
- Booth modes and keys: A fades between raw and analysed over `ui.raw_fade_s` and the booth starts analysed; M switches between fire and ember mode and the booth starts in fire mode; the heartbeat carries the mode, raw and the camera state; offscreen screenshots of the ember screen in both languages.
- Mac scripts: `setup_mac.sh` run twice gives the same result (with fakes here); `doctor` prints one line per check ending in OK or FAIL; `mac_soak.py` on a short run gives a PASS or FAIL report; the placards render at A5 in both languages with limits 1 to 5.
- Camera: device lists from fakes (Continuity Camera and Desk View never usable; auto picks a USB webcam over the built-in camera; a name picks by part of the device name); every permission answer handled, and `unsupported` off macOS; a camera that fails is reopened with backoff; the fake camera plays a file and generated phones in real time.
- Ember mode: the 4.4 goals on synthetic phone scenes as regression tests (smaller scenes); static bright objects never tracked; at most six tracks; the mirror; the `LiveState` fields; `calibrate --video` on a rendered A4 target at a known distance recovers the focal length; `record` writes H.264 from a fake camera; `validate --suite ember` without the recordings runs the synthetic part alone.
- The ember page, in headless Chromium: no external requests (also when opened from a local file), the disc as specified, brightness and scale within the flicker ranges, the instruction gone after 3 s, and a wake lock requested where the browser offers one.
- Integration:
  - a synthetic clip through `process` with regression thresholds;
  - determinism;
  - offscreen screenshots in both languages with a text-overflow check;
  - the demo gate: `live` for 60 s on synthetic video, on the playlist and in ember mode on generated phones.
- Soak: a short synthetic live run here, then `python scripts/mac_soak.py --hours 8` with the playlist on the Mac in sitting 2.
- Docs: `check_docs.py` and `check_staged.py` before every commit.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Sittings happen late (parts delivery, final evening) | Nothing blocks on them: the remaining switches have safe defaults; synthetic phones and the fake camera stand in until then |
| Playback cannot keep up on the Mac (4K decoding, slow analysis) | Frames scaled down while decoding; late frames dropped, never queued; the clock restarts instead of racing; thread or process worker; the rate is logged in the heartbeat and checked all night by the soak; 4K clips can be cut to their approved segments and region |
| A playlist clip is missing on the Mac (download failed, C1 not shared yet) | Missing clips are skipped and retried every loop; synthetic video with its tag when nothing plays, so the screen is never black; the clip download resumes when run again; C5 and C6 come from NIST, not the rate-limited Wikimedia |
| False detections on bright real scenes (compression flicker, LOG 2026-10-15T09:40) | Detector fix in progress; only clips checked on the booth screen go into the playlist |
| Synthetic validation is self-confirming | Held-out mismatch suite supplies the headline numbers; your ember recordings never tune anything |
| No openly licensed Korean ember footage | Synthetic data and US federal footage; ask KFS for permission; gap stated plainly |
| No ground truth on real clips | Blind sample labels and plausibility checks; claims limited accordingly |
| Python too slow | Approximate median, frames dropped rather than queued, analysis at most 1280 px wide; process split if needed |
| Qt fullscreen lands on the wrong screen | Automatic choice with hot-plug; screen by name with `--screen`; rehearsal |
| Camera permission missing on the booth day (never asked, denied, or given to another terminal app) | Asked in sitting 1 with `cameras --request`; the booth always runs in Terminal, the app that holds the permission; the runbook says how to allow it in System Settings; without a camera, ember mode shows generated phones, so the screen is never black |
| macOS offers an iPhone as camera (Continuity Camera), or a video effect changes the picture (Center Stage crops and pans, Reactions draw on it) | Continuity Camera and Desk View are never usable and the camera is chosen by name; the video effects are switched off in sitting 1 and checked in the runbook |
| Webcam auto exposure: a dark room makes the camera brighten and smear the phones, a bright one darkens them | The page is bright on black; the booth lights stay steady, with no window or lamp facing the camera; detection and tracking are checked on your `ember_free` recording with the booth camera, and again in the rehearsal |
| A dim phone (auto brightness, low power mode) or a tilted one is lost | Visitors turn the brightness up and hold the screen to the camera (the runbook says to help); the identity-switch goal of 4.4 covers short losses |
| Room lights, windows, screens and reflections look like bright blobs | They do not move, and static bright objects never become tracks (a 4.4 goal); the camera faces away from windows and ceiling lights where possible |
| People's clothing and accessories (white or orange clothes, reflective strips, a watch catching the light) move with the visitors | Detection is tuned to phone screens showing the ember page at 1 to 3 m (4.4); at most six tracks; the rehearsal checks it with people in front of the camera |
| Privacy of the camera image (visitors' faces on the booth screen) | The picture is shown live and never stored or sent; nothing is recorded in the booth unless the operator runs `record`; only your own sitting 1 recordings are kept, in `data/raw` (never committed) |
| Visitors cannot open the page (no network at the venue, a long address) | One self-contained file: once loaded it needs no network; the address (or a QR code of it) on a card at the standing spot; a spare phone with the page open |
| Visitors stand nearer or farther than the floor mark | Speeds are marked "measured at 2.0 m"; the floor mark is easy to see; limit 1 states the effect |
| One-week schedule | Deferred list and priority order; stretch goals cut first |
| Overclaiming | METHODS and LIMITS docs; units and "estimate" labels on screen; NUMBERS provenance |

## 12. What I need from you

Buy or have ready:
- The booth 블랙박스 dashcam on its stand, for the "This is the sensor" exhibit (no SD-card recordings are needed any more).
- A USB UVC webcam, optional: the MacBook's own camera is the default. Any standard USB webcam works; an iPhone or Continuity Camera is never used.
- The A4 calibration target, `booth/ember/calibration_target_A4.pdf`, printed at 100 percent (actual size) and fixed to stiff card so it stays flat.
- Tape for the standing spot on the floor and for the two marks of the 1 m path, a tape measure, and a ruler to check the target's 100 mm line.
- A table (or a bench or a long box) at least 1.2 m long, whose front edge carries the 1 m path at the standing spot.
- A phone or two to test with, with the page open and the screen brightness up.
- GitHub Pages for the page: a GitHub repository with Pages turned on, holding `booth/ember/index.html` (any static host works too), and its address on a card at the standing spot.
- The external monitor and its cable (optional: without it the booth runs on the MacBook's screen).
- A power strip.
- The A5 placards from `booth/placards/` (Korean and English), printed: "This is the sensor" for the dashcam stand, and the limits card.

Install: Python 3.12 from python.org on the Mac (`scripts/setup_mac.sh` uses it).

Record (in sitting 1, step by step in `docs/SITTING1.md`), with the booth camera after the A4 calibration, at the standing spot, with the page open on your phone. The record command writes the files into `data/raw/` itself:
- `ember_free`: about a minute of you moving the phone freely (`python -m wfglink record ember_free --seconds 60`);
- `ember_ruler`: the phone at rest on the 0 mark of the 1 m path, moved to the 100 cm mark in about 1 s, at rest again (`python -m wfglink record ember_ruler --seconds 15`).

Provide:
- C1 (the proposed booth clip): download it with a free DVIDS account and share a link when you have time. Until then, the booth plays the other approved clips in the playlist.
- The KFS decision on C15, when it arrives.
- The output of `python -m wfglink doctor` and `python -m wfglink cameras` from sitting 1 (macOS, Python, the screens and the cameras).
- From sitting 1: `results/validation/ember_report.json`, the two recordings and `configs/booth_local.yaml` (the calibration record) through one share link (Drive, Dropbox or iCloud), and the page's GitHub Pages address.
- From sitting 2: the PASS or FAIL report of the overnight soak.
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
- storing or identifying visitors: ember mode shows the camera live and stores no picture;
- cloud upload;
- connecting to the forecast or routing code;
- modifying the route logger;
- Windows support.

Limits, in LIMITS.md, on the ko/en booth card (key I) and on the printed A5 limits placard. There are five; the sixth (the re-filmed screen) went with the setup change of 2026-10-15:
1. One camera cannot see depth. Speeds and flux are projections onto the picture. Meters per second hold only at the stated distance range; an ember twice as far away is twice as fast as shown.
2. Embers are not air. They respond to gusts with a delay of roughly 0.25 to 0.8 s (terminal velocity divided by g) and fall at about 2.5 to 8 m/s (Ellis 2010, unburnt eucalypt bark; burning embers get lighter). So the arrows are a smoothed, lagged wind estimate. The vertical component is biased downward, and there is no estimate where there are no embers.
3. Calibration is uncertain. Road markings only scale the road surface. An ember 1 m above the road, seen by a camera 1.3 m high, would be placed about 4.3 times too far away. That is why wfglink scales embers by an assumed distance range and shows the range.
4. We count only what glows and is visible, so counts are lower bounds. Our flux is per length of a line in the picture, not NIST's per square meter.
5. Validated on synthetic video and plausibility checks; not side by side with a NIST Emberometer in a real fire.

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
- The ember report (`validate --suite ember`) meets or honestly misses the 4.4 goals on synthetic phones, with reasons, and gives detection and tracking quality on `ember_free` and the speed error on `ember_ruler`.
- The ember page opens from GitHub Pages on a phone and makes no external requests (checked in headless Chromium here).
- Screenshots in both languages are inspected.
- `python -m wfglink doctor` ends every line in OK on the Mac, and `python -m wfglink cameras --request` reports the camera permission as authorized.
- The overnight soak (`python scripts/mac_soak.py --hours 8`) on the Mac reports PASS: the booth kept playing and analysing the playlist in real time all night, recovering by itself from any crash.
- The runbook has been rehearsed once, with both booth modes and every key, A and M included.

## 17. Changes after approval

The text above is the approved plan with your three decisions of 2026-10-15 (the two sittings, the setup change, then the booth change) written in; these are the departures, each with its reason and the LOG entry that records it.

- **Booth change (user decision, 2026-10-15).** You dropped the LED turntable test completely, so these went: the led suite (`validate --suite led`), its notes file and template (`led_notes.yaml`), the rig and the turntable with their recordings (`led_33rpm`, `led_45rpm`, `led_ruler`, `room_test`, `night_drive`) and their steps in sitting 1, the LED line on the sensor placard, and the LED in limit 5. In their place: key A fades the fire footage between the raw clip and the full overlay over about 0.5 s (the booth starts analysed); and "Become an ember" (key M; the booth starts in fire mode) brings a camera back for this mode only: the MacBook's camera or a USB UVC webcam chosen by name, never an iPhone or Continuity Camera, with camera permission asked properly on first use; a self-contained phone page (`booth/ember/index.html`) for GitHub Pages; tracking of up to six phones 1 to 3 m away, each with a trail, an ID and a speed; m/s at a 2.0 m standing spot with a one-command A4 calibration; and validation on synthetic phones and your two recordings (4.4). The known-speed check moves from the turntable to a phone moved along a measured 1 m path, with the move time taken from the video. Sitting 1 is now setup, camera and permission, the A4 calibration, the recordings, validate and send files. Why: your decision. The target stays Monday 19 October, and the always demo-ready rule stays (LOG, 2026-10-15T12:40).

- **Setup change (user decision, 2026-10-15).** You dropped the live camera entirely, so these went: the iPhone, the iPad, the USB webcam and Continuity Camera; the camera chain, camera permission and the `.app` launcher; booth-prep with its corner frame codes and held frames; the screen check, the loop simulator and loop suite, and the loopback check; check A and check B (the camera checks) and the 240 fps panel clip; and limit 6 (the re-filmed screen). The overnight soak stays, as `scripts/mac_soak.py`. Why: your decision. It also removes what re-filming a screen cost: artefacts (moiré, refresh blending, tearing, exposure drift) that had to be engineered around and then disclosed as a limit, and a booth that depended on a cable, an Apple Account and two more devices. The booth now plays the approved clips in real time and analyses them as they play, fullscreen on the external monitor when one is connected, else on the MacBook (section 7). The LED turntable is filmed top-down with the booth dashcam only (4.4), and your build manual's commands exist as written: `./scripts/setup_mac.sh`, `python -m wfglink doctor`, `python -m wfglink live --synthetic`, `python -m wfglink validate --suite led`, `./booth/booth.sh` and `booth/booth.command`, `python scripts/mac_soak.py --hours 8`, and the A5 placards in `booth/placards/`. Your hands-on work is sitting 1 (setup, dashcam, LED rig, recordings, validate, send files) and sitting 2 (update, booth, overnight soak, rehearsal); the target stays Monday 19 October (LOG, 2026-10-15T10:30). The LED parts of this entry (the turntable filmed with the dashcam, `validate --suite led`, the dashcam, LED rig and recordings in sitting 1) are obsolete since the booth change above, and a camera returns for ember mode only (the MacBook's or a USB webcam, with its permission; never an iPhone, iPad or Continuity Camera); kept as a record.

- **Detection.** A Gaussian prefilter (matched filter) before thresholding is now the default (`detect.prefilter_sigma_px`). Compressed video noise is heavy tailed, and without it most detections were compression artefacts. Chosen on the core suite only (LOG, 2026-10-15T03:05).
- **Saturation** is flagged on the brightest color channel, not luma (orange embers clip red first).
- **Exposure time.** The estimator no longer iterates its own point selection (that gave two self-consistent answers with short streaks). It fits once on fixed speed cuts and declines, with a stated reason, unless the answer is stable and the streak lengths are shown to be proportional to speed. On the synthetic core suite it declines every clip, because measured streak lengths are not yet proportional to true length (a floor for short streaks, lost ends for long faint ones). Fixing the length measurement (the erf or segment model fit deferred in section 9) is now a task.
- **Streak length (file mode).** File mode now measures streak length with the erf edge-profile fit (`detect.streaks.method: erf`, METHODS section 2), chosen from three approaches on the core suite; `method: moments` restores the earlier lengths exactly, and live mode keeps the moments. The fit recovers most of the faint ends of long streaks that the threshold cut off. It does not remove the floor of short streaks (in some cases it is slightly higher than with moments), and the exposure estimator still declines every core clip tested, so streak speeds are still not reported there. The next step is outside the length method: an exposure estimator that tolerates per-point length noise, or a motion axis taken from the track.
- **Tracking.** Process noise adapts per track (wide for turning targets such as the LED turntable, narrow for smooth embers), the search gate is limited by the local detection density, coasting is up to 5 frames instead of 3, and coasted gaps are filled by a cubic curve in file mode. Dense showers had many identity switches from wrong associations during flicker dropouts.
- **Repeated frames** are detected by changed pixels at full resolution and, for lossy re-encodes, by the embers not having moved; thumbnail differences dropped real frames of night scenes.
- **Booth hold rule (sections 4.3 and 9).** Obsolete since the setup change of 2026-10-15 (no held frames, no check B); kept as a record. The 80 percent clean-frame yield rule is replaced by a coverage rule (`sitting2.hold_rule: coverage`). With a scanning 60 Hz panel and a global-shutter camera, the clean-frame yield at hold 2 is close to 1.0 or to 0.5 depending on the camera's phase and averages below 0.8 over phases, while every source frame is still read clean at least once whenever the unclean time per content change is shorter than one camera frame. Check B now measures source coverage over several camera restarts (new phases) and keeps hold 2 only when every window covers the clip and spare clean views show margin; otherwise hold 3. The yield is still reported, and `hold_rule: yield` restores the old rule.
- **Source health in booth mode (section 7).** Obsolete since the setup change of 2026-10-15 (no live camera); kept as a record. It was implemented as written: a live camera must keep reading advancing frame codes; a paused iPad shows "iPad 정지 · iPad paused" and the chain falls back.
- **Demo tags.** This cloud session's git proxy refuses tag pushes, so each passing build is recorded in DEMO_BUILDS.md on the branch with the command that makes the tag.
- **Validation metrics.** An oracle audit (truth fed in as perfect estimates) found and fixed scoring bugs before any number was recorded: the field truth window, signed medians in summaries, gate truth inside flame regions, CLEAR MOT persistence across dropouts, and repeated frames in the bridged gate truth. Detection is also reported as completeness against ember SNR, and counts are checked between the bright-ember and all-visible truths.
