# wfglink log

Append-only. Times are Asia/Shanghai (UTC+08:00). Each entry: goal, exact commands, parameters, results (numbers carry a NUMBERS.json key), decisions, next step. Failures are logged too.

## 2026-10-14T23:40+08:00 Planning and approval

- Goal: produce and get approval for the wfglink plan, then start section 15 (first actions).
- Commands:
  - `git rev-parse --show-toplevel` returned `/home/user/wildfireguardian`; branch `claude/practical-rubin-5vu12u`; README read.
  - Read-only research workflows (repo conventions, route logger search across all refs, science, computer vision, macOS platform), a licensed clip search with license verification, and a three-lens adversarial plan review. No files were written during planning.
- Parameters: none (planning only).
- Results:
  - Route logger: not present in any git ref; the repo only describes an ESP32 plus Quectel L76K GNSS device with planned CSV and GPX exports. Its schema is on the user's Mac.
  - Repo has no video or OpenCV code; wfglink copies only conventions.
  - Clip shortlist with verified licenses (PLAN.md section 13). No openly licensed Korean ember video was found.
  - No measured results yet, so no NUMBERS.json entries.
- Decisions (user, verbatim in docs/PROMPT.md): one week of continuous work; iPad Air and iPhone 13; push to the session branch with one draft PR; clips C1 to C13 approved, C10 tracking-only, C14 conditional, C15 pending KFS permission; dashcam file-mode check added; daily demo tags from M2; check A Thursday, check B Saturday; booth screen 2 m rule; any motorized platform for the LED test; black cloth hood.
- Decisions (mine, from the review): held-out mismatch suite supplies headline numbers; LED clips never used for tuning; ground homography never applied to airborne embers; approximate running median for live mode; booth clips with corner ArUco markers, Gray-coded frame index and held frames.
- Next step: scaffold (records, check scripts), Python 3.12 venv with pinned requirements, Qt offscreen and Pretendard smoke test, first commit and draft PR, then M0 Mac check A tooling.

## 2026-10-14T23:48+08:00 Scaffold and environment (M0 start)

- Goal: section 15 first actions: folder, records, guard scripts, pinned environment, smoke tests.
- Commands:
  - `python3.12 -m venv wfglink/.venv`, then `wfglink/.venv/bin/python -m pip install -r wfglink/requirements.txt` and `pip install -e wfglink --no-deps`.
  - First Qt import failed with `ImportError: libEGL.so.1`; fixed in the container (not the repo) with `apt-get install libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libglib2.0-0`.
  - Pretendard 1.3.9 taken from the npm tarball (SHA-256 in data/SOURCES.md); four weights vendored in assets/fonts with the OFL license.
  - `python -m wfglink doctor`, `python -m pytest -q`, `python3 scripts/check_staged.py`, `python3 scripts/check_docs.py`.
- Parameters: pins in requirements.txt (numpy 2.5.4, scipy 1.18.1, opencv-contrib-python-headless 4.14.0.94, PySide6 6.12.0, av 19.0.1, pyarrow 26.0.0, pandas 3.0.6, PyYAML 6.0.3, matplotlib 3.11.2, pytest 9.1.1, pyobjc-framework-AVFoundation 12.2.2 on macOS only). Full container environment in constraints-linux-x86_64.txt.
- Results:
  - doctor reports ok: Qt offscreen platform works, Pretendard resolves as the UI font, OpenCV ArUco is present, PyAV decodes H.264, HEVC, AV1 (libdav1d) and VP9 and encodes libx264.
  - The smoke tests pass, and check_docs flagged every planted error in a scratch copy (em dash, wrong tagged value, untagged result, dirty entry).
- Decisions: check_docs treats README "Current status" and LOG "Results" bullets as result sections; numbers there need a NUMBERS.json tag. A run is dirty only if wfglink src, configs, scripts, pyproject or requirements have uncommitted changes, so writing results does not dirty its own run.
- Next step: commit and push, open the draft PR, then build Mac check A tooling.

## 2026-10-15T00:02+08:00 Detector built; schedule changed to two sittings

- Goal: write the detector (M0), start the parallel M1 build, and adopt the user's two-sitting schedule.
- Commands:
  - Detector benchmark scratch script on rendered moving blobs and streaks at 1280x720 and 1920x1080; `python -m pytest -q`.
  - Workflow `wfglink-m1-build` (two implementation agents, each followed by an adversarial review agent): synthetic generator; tracker, velocity, exposure, gate and metrics. Still running at the time of this entry.
- Parameters: configs/default.yaml detect section; grow threshold raised to 3.0 sigma, noise subsample 4, moment window dilation 1 px (lowest noise for the same bias across 8 noise seeds in a scratch comparison).
- Results:
  - Detector unit tests pass (positions, streak lengths, flame exclusion, noise, exposure step, saturation, warm color). Timing and accuracy figures will be recorded in NUMBERS.json by the validation suite, not quoted here yet.
  - First detector draft was far too slow because of full-frame scans (scipy ndimage per-label reductions, numpy nonzero); rewritten to use uint8 OpenCV operations on the full frame and pixel lists per component.
  - Two test failures were my own test geometry (streaks too faint, and a streak longer than its per-frame displacement, which is physically impossible); two were real detector issues (saturation flag diluted by component tails; ring-only color reads background for small embers) and were fixed.
- Decisions:
  - User schedule change (verbatim in docs/PROMPT.md): two sittings. Sitting 1 when parts arrive (install, check A, all recordings); sitting 2 on the final evening (check B, overnight soak, rehearsal next morning). One script, one checklist and one combined JSON report per sitting.
  - PLAN.md is now version 4: section 9 rewritten. Hardware-dependent choices became config switches with safe defaults: camera.backend, camera.fps, booth.launcher, booth.hold_factor, live.worker_mode, ui.screen.
  - Camera backends (PyAV and OpenCV) with automatic fallback, the py2app alias app and the process worker mode are built before the sittings, so late sittings cause no rework.
- Next step: capture backends with fallback and a fake camera, the reconnecting source, the app-build script, then the sitting 1 kit.

## 2026-10-15T00:33+08:00 Capture layer, app fallback and the sitting 1 kit

- Goal: everything sitting 1 needs, ready before your parts arrive, with no rework if check A comes late.
- Commands:
  - `python -m pytest -q tests/test_capture.py tests/test_sitting.py` (the sitting tests include an end-to-end `python -m wfglink sitting1 --dry-run` on stand-in clips).
  - Scratch runs of the live check window offscreen on the synthetic source.
- Parameters: capture chain thresholds in configs/default.yaml (capture section); stand-in LED turntable clips at 33 1/3 and 45 rpm; stand-in 240 fps panel clips with known vertical and horizontal scan.
- Results:
  - Capture chain tests pass: a disconnected camera falls back to the webcam and returns after sustained health; a frozen camera is replaced by labelled replay; with no camera, replay runs while the camera is retried with backoff; file timestamps stay continuous across the loop seam.
  - Sitting 1 dry run passes end to end: all steps done, every LED stand-in passes its alignment and visibility check, the panel scan axis is recovered for both directions, and the night drive is correctly deferred.
- Failures found and fixed on the way:
  - A worker attribute named _stop shadowed threading.Thread._stop and broke join.
  - The synthetic demo source was too slow until it moved to per-channel OpenCV operations at reduced resolution for flames and halos.
  - The LED alignment check was biased by ring selection and by one stray detection; it now selects the outermost ring and rejects off-ellipse points.
  - Detector: long bright streaks of fast embers were rejected as "large regions". Large now means big and thick; thin streaks up to max_streak_area_px are kept (configs/default.yaml).
- Decisions:
  - The panel analysis reports the apparent sweep (panel scan minus camera readout); only the scan axis is used.
  - configs/booth_local.yaml holds machine switches written by the sittings and is gitignored; load_config(local=True) applies it.
  - The LED speed analysis and night-drive analysis plug into the sitting once the tracker lands; until then the sitting records "pending" and I analyse the uploaded files.
- Next step: integrate and review the M1 agents' work (synthetic generator, tracker, velocity, exposure, gate, metrics); LED analysis module; first validation numbers.

## 2026-10-15T00:57+08:00 Tracker, velocity, exposure and gate modules integrated; booth app and demo gate

- Goal: integrate the reviewed M1 measurement modules, then run the live booth UI end to end on the real pipeline (M2).
- Commands:
  - Workflow `wfglink-m1-build`, track branch: one agent built `track/`, `measure/velocity.py`, `measure/exposure.py`, `measure/gate.py`, `validate/match.py` and `validate/metrics.py`; a second agent reviewed them adversarially and fixed what it found.
  - `python -m pytest -q` (all non-slow tests), then the slow tests, including `python -m wfglink booth --source synthetic --duration 6` in both worker modes.
  - `python -m wfglink demo-gate --seconds 20` (scratch run, offscreen).
- Parameters: configs/default.yaml track, gate, velocity and validate sections (new keys from the agents are documented there); live.worker_mode thread and process.
- Results:
  - The review agent found and fixed eight defects. The worst: the gate-count metric scored a correctly working counter as too high when embers flicker out for a frame, because true crossings bridged by a coasting track were not counted.
  - Booth app runs end to end offscreen in both worker modes with no errors; the demo gate passes on the synthetic source and on the NIST Emberometer clip (C5). Frame rates in this container are reference only and are not recorded.
  - Found and fixed: the gate counter kept every event and per-track state forever, so a booth day would slow down and grow in memory. Finished tracks are now forgotten and events older than two minutes are folded into archived totals; a test checks the totals stay exact.
  - The process worker needs the `__main__` guard because the spawned child imports the module again.
- Decisions:
  - Booth mode analyses only clean frames in source time; a backward frame index means the clip looped, which restarts tracker and counts.
  - The demo gate clip is C5 until C9 (night sparks) downloads; C5 has bright lab lights that produce some false detections.
- Next step: LED turntable and night-drive analysis for sitting 1; then the synthetic core suite for the first numbers.

## 2026-10-15T01:50+08:00 LED and night-drive analysis, booth supervisor, first look at the synthetic base clip

- Goal: finish the sitting 1 analysis (LED speed, dashcam night drive), the booth-day supervisor, and a file-mode evaluation runner for the synthetic suites.
- Commands:
  - `python -m pytest -q -m "slow or not slow"` (all tests, including the sitting 1 dry run, which now runs the LED analysis on stand-ins).
  - `bash booth/booth.sh --source synthetic --duration 12` offscreen, and `tests/test_booth_supervisor.py` with a scripted crash, hang and clean exit.
  - Scratch evaluations of one base-case synthetic clip (core suite, seed 0) with `wfglink.validate.suite.evaluate_clip`, with and without a Gaussian prefilter, and a seed-threshold sweep.
- Parameters: configs/default.yaml at commit 019bac3; prefilter and thresholds varied only in scratch runs.
- Results:
  - LED analysis recovers the stand-in truth (speed, exposure, detection) for a straight and a slightly tilted camera; the numbers will be recorded by `scripts/led_standin_check.py` once the source tree is clean.
  - Fixed on the stand-ins: saturation is now flagged on the brightest color channel. Orange LEDs and embers clip red while luma stays below the level, and the flattened profile made short streaks too long without any flag.
  - Fixed: without an exposure estimate the tracker never started fast embers whose streaks cover half the frame interval; `track.birth_duty_min` now assumes at least half.
  - Fixed: repeated-frame detection compared 64x36 thumbnails, which dropped real frames of a static night scene with a few small embers. It now counts changed pixels at full resolution.
  - Fixed: streaks for streak speed were chosen by measured length, which kept short streaks with positive length noise; they are now chosen by predicted length.
  - Base clip findings, to be confirmed on the whole core suite before any number is quoted: compressed noise is heavy-tailed, so most raw detections at the default thresholds were noise; a light Gaussian prefilter (matched filter) removed most of them at the same recall. Most embers in the base case are fainter than the detector's limit after compression, so recall over all visible embers stays low; completeness against ember SNR is now reported.
- Decisions:
  - Detection is reported three ways: F1 over all visible embers (the plan's goal), completeness against SNR with the SNR at 50 percent completeness, and false detections per megapixel per frame.
  - Gate counts are checked against two truths: all visible embers (an upper bound for what a camera can count) and bright embers only (a lower bound).
  - Wikimedia returns HTTP 429 to this container's shared address; sitting 1 now downloads the approved clips on the Mac in the background and links them into the upload folder.
  - Mismatch suite defined (configs/suites/mismatch.yaml, 60 clips, seeds 100 to 104, never tuned). The generator cannot render 3D perspective with depth-dependent defocus; the defocus case uses one defocus for every ember.
- Next step: evaluate the whole core suite with the prefilter off and on, choose detector defaults on the core suite only, record core numbers, then run the mismatch suite once.
