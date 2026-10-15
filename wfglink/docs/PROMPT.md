# Prompt and user decisions

This file holds the original prompt for wfglink verbatim, followed by every later decision from the user, also verbatim, with dates (Asia/Shanghai). Text in the decision log that is not quoted is a short description of the question that was asked; the quoted text is the user's own words.

## Original prompt (2026-10-14, verbatim)

You are in plan mode. Produce a plan only. Do not write code or create files until I approve.

# wfglink: measuring embers and wind from ordinary camera video

## Background
WildfireGuardian is my Korean wildfire project (spread prediction plus evacuation routing) for Korea Code Fair 2026, a coding competition, so the software is the core deliverable.

A key unsolved data gap in wildfire science: during real fires, nobody can measure how many embers are flying, where, and how fast, or the wind at street level inside communities. Embers (spotting) carried the March 2025 Uiseong fire about 51 km to Yeongdeok within 12 hours (Korea Forest Service analysis) and drive most house losses in wildland-urban interface fires. NIST's "emberometer" measures embers with four synchronized cameras and particle tracking velocimetry, but only where it is installed before a fire.

wfglink's idea: an ember is a glowing tracer particle, so any camera that films an ember storm (Korean dashcams, called 블랙박스, plus CCTV and phones) has recorded ember activity and air motion. From ordinary video, wfglink extracts:
1. Ember detections per frame (small, bright, warm-colored blobs or streaks against dark or smoky backgrounds, robust to video compression).
2. Tracks across frames and per-ember velocity, combining frame-to-frame tracking with streak analysis (streak length divided by exposure time gives speed, which makes 30 fps footage usable).
3. Ember count rate and number flux through a virtual gate. NIST reports Cumulative Particle Count and Particle Number Flux; mirror those names.
4. An ember-derived air velocity field (gridded mean ember velocity), labeled as an estimate because embers lag the air.
5. Optional pixel-to-meter scaling from a calibration target or known scene lengths such as lane markings. Uncalibrated outputs stay in pixels and are labeled that way.

## How it will be used
Korea Code Fair finals booth:
- An iPad plays a real fire clip. An iPhone on a mini tripod films the iPad (camera-in-the-loop, the way automotive teams test cameras against recorded roads) and streams to my MacBook Pro (M4 Pro) through Continuity Camera, with a USB webcam as fallback. wfglink processes the live feed and shows results on an external portable monitor.
- File mode: process recorded clips directly (dashcam SD card clips, downloaded footage) at full quality.
- The booth display must run all day offline, fullscreen, start with one command, and recover automatically if the camera disconnects.
- Design: black background, white type, green for measured values, orange for embers, minimal and clean (Apple-like). UI labels in Korean and English with a toggle. It must look like a finished product, not a debug window.

## What the plan must cover
1. Architecture and modules: input sources, detection, tracking, velocity, flux, air velocity field, calibration, outputs, UI. Recommend the UI approach (for example native Qt versus a local web app) and justify it for a fullscreen live display at 30 fps or better on an M4 Pro. State realistic frame rate and resolution targets.
2. Validation, since credibility depends on it:
   - A synthetic video generator with known ground truth: particle counts, velocity fields (uniform, shear, vortex), motion blur from exposure time, sensor noise, haze, flicker, compression. Metrics: detection precision and recall, velocity error, flux error.
   - Robustness to camera-in-the-loop artifacts (moiré, screen refresh flicker, rolling shutter, glare) with concrete mitigations.
   - Plausibility checks for real clips.
3. Data intake: folder layout for real clips, a provenance table (source, URL, date, permission or credit), and the kinds of clips I should collect (night, dashcam viewpoint, visible lane markings, Korean fires where possible).
4. Outputs: per-frame and per-track tables (CSV or Parquet), a summary JSON per clip, an overlay video export, and the live dashboard.
5. Stretch goal, scoped separately: moving-camera ego-motion compensation using background optical flow, and later GNSS speed and heading from my route logger (read the repo only to find its data format; do not modify it).
6. Milestones with time estimates, test plan, risks and mitigations, and everything I need to buy, record or provide.
7. Non-goals and the honest limits we should state at the booth (single-camera depth ambiguity, embers lagging the air, calibration uncertainty).

Keep it concise and concrete; I will review it before approving. After approval, your first actions are: create wfglink/, save the approved plan to wfglink/PLAN.md, save this prompt verbatim to wfglink/docs/PROMPT.md, and add the first LOG.md entry.

## Working rules (three Claude Code sessions run in this repo at the same time)
- You are at the root of my WildfireGuardian repository. Confirm with `git rev-parse --show-toplevel` and a quick look at the README before starting.
- Work only inside wfglink/. Do not create, edit, move or delete anything outside it, including root files such as README, .gitignore or requirements. Reading the rest of the repo is fine.
- Do not modify or import the existing forecasting code. This work is isolated; copy ideas, not modules.
- Git: never switch branches, stash, rebase, reset or push. Stage only your folder (`git add wfglink/`), never `git add -A` or `git add .`. Commit at meaningful checkpoints with messages starting with [wfglink]. If you see a .git/index.lock error, another session is committing: wait a few seconds and retry.
- Python: use your own virtual environment at wfglink/.venv, list dependencies in wfglink/requirements.txt, and add wfglink/.gitignore for .venv, caches and large raw data. The machine is a MacBook Pro (M4 Pro, macOS); prefer packages that install cleanly on Apple Silicon.

## Record-keeping (required)
Keep these current inside wfglink/:
- README.md: what this is, why it exists, how to run everything, current status.
- LOG.md: append-only, dated entries in Asia/Shanghai time. Each entry: goal, exact commands, parameters, results with numbers, decisions, next step. Log every significant run, including failures.
- results/NUMBERS.json: every number quoted in README, PLAN or LOG summaries, with the script, config and git commit that produced it.
- data/SOURCES.md: provenance for every external dataset, clip, parameter and paper (source, URL, date accessed, license or permission).
- docs/PROMPT.md: this prompt, verbatim.
- Writing: plain, clear English, no em dashes, standard Markdown without decorative formatting.
- Figures: professional on the first try. Consistent style, readable font sizes, labeled axes with units, colorblind-safe palette, no clutter. Save PNG at 300 dpi plus SVG. Open and inspect every figure after saving, and fix anything cramped, clipped or overlapping before moving on.

## Later decisions (verbatim user answers)

### 2026-10-14, schedule
Question asked: when are the finals (booth day)?
Answer: "finish everything within one week. However, you can stay on for the entire one week period, no turning off. Fully continuous work."

### 2026-10-14, booth hardware
Question asked: which iPad will play the clip?
Answer: "I have an ipad air."

Question asked: which iPhone will film the iPad?
Answer: "I have an iphone 13"

### 2026-10-14, git push
Question asked: the session runs in a cloud container that is deleted when the session ends; how should commits reach the user's Mac?
Answer (selected option): "Push to my branch (Recommended)". The option text was: push [wfglink] commits only to claude/practical-rubin-5vu12u and open one draft PR to Main; no other branch is touched.

### 2026-10-14, Mac testing
Question asked: will the user be available to run short Mac checks during the week?
Answer: "how long will that be? Depends on how long it needs me to work on it"

### 2026-10-14, real clips
Question asked: how will real fire clips reach the cloud container?
Answer: "Go with option 4, then option 1's mechanics. Search Wikimedia Commons, government and agency sources (Korea Forest Service, NIFOS, US agencies such as USFS, NIST, CAL FIRE) and other openly licensed footage for ember and spotting clips, and give me a short list to approve with source, license, length and why each is useful. Once I approve, download the approved clips into gitignored wfglink/data/raw/ and record each one in data/SOURCES.md. Skip anything whose platform terms or license forbid downloading or redistribution. Never commit raw video. Until real clips are approved, build and tune against the synthetic generator and the LED validation clips I record. Final booth runs happen on my Mac in file mode and live mode, so keep every path configurable."

### 2026-10-14, plan approval
Answer: "Approved with these changes:

1. Real dashcam data: I will buy the booth 블랙박스. Add a file-mode check on its own SD-card clips: the LED turntable filmed with the dashcam, plus a short night drive I record as a hard negative. Report detection and speed error for the dashcam clip next to the iPhone result, so the "This is the sensor" exhibit is backed by data. Add it to M4 and to section 12.

2. Always demo-ready: from M2 onward, keep a tagged build that runs the live UI end to end (synthetic or approved clip) with one command, even if later milestones slip. Note the tag in LOG.md each day.

3. Scheduling: my Korea Code Fair submission deadline is Oct 18 and I am finishing other hardware before then. Keep check A on Thursday if possible; check B may move to Saturday. Plan around that.

4. Clips: approve C1 to C13. Exclude C10 from all speed and flux metrics (its timebase is 4x slow motion); use it only to stress tracking. Keep C14 only if it contains real ember footage. C15 stays pending; I am requesting KFS permission now.

5. Booth screen priority: the first five seconds must read as a finished product from 2 m away. Big numbers and glowing tracks dominate; "Estimate" and "Uncalibrated" tags stay small but always visible; the full limits card appears on a key press or on a secondary display, not permanently on the main screen.

6. Hardware: any motorized rotating platform is fine for the LED test if a record turntable is hard to get, since you time the rotation independently. Use black cloth rather than foam board for the glare hood.

Everything else as written. Proceed with section 15."

Note on the LED clips: the approved plan (section 4.4, written after an independent review) keeps LED clips out of tuning so that they remain an honest validation; the user approved the plan with "Everything else as written".

### 2026-10-15, schedule change: two sittings
Answer: "Schedule change: I want my hands-on work in two sittings instead of five.

Sitting 1 (as soon as my parts arrive; I will tell you the date): install, check A, and every recording at once: LED turntable clips (both speeds, plus the ruler clip, with stopwatch timings), the same LED test filmed with the 블랙박스, a short night drive with the dashcam if possible, and the 240 fps slow-motion clip of the iPad screen. Prepare one script and one checklist for this sitting that runs the checks in order, tells me exactly what to record and how to name and upload each file, and writes a single combined JSON report. Target about 60 to 75 minutes.

Sitting 2 (final evening): check B, then start the overnight soak (check C), with the rehearsal the next morning. Same deal: one script, one checklist, one combined report.

Until sitting 1 happens, keep building without blocking on me. Assume Continuity Camera might fail and keep the USB webcam and app-build fallbacks ready, so a late check A does not cause rework. Move any decision that depended on check B (such as 0.5x versus 1/3x playback) to a config switch that is easy to flip after sitting 2. Update PLAN.md and LOG.md with the new schedule."

### 2026-10-15, setup change: no live camera; booth is real-time file playback
Answer: "Setup change, decided by me: drop the live camera entirely. No iPhone, iPad, USB webcam or Continuity Camera; no booth-prep frame codes, held frames, loop suite, loopback check or camera checks; remove limit 6 (re-filmed screen). Booth mode is now real-time file playback: approved clips are analyzed live as they play, fullscreen on the external monitor if one is connected, otherwise on the MacBook. The LED turntable test is filmed top-down with the dashcam, not the iPhone.

I am following a build manual that names these exact commands and files. Make them exist exactly like this (or tell me precisely what differs so I can fix the manual):

- Setup: git worktree at ~/wfglink-run from origin/claude/practical-rubin-5vu12u (your plan's commands). ./scripts/setup_mac.sh creates .venv with python.org Python 3.12, installs everything and creates data/raw. Running it again must be safe.
- python -m wfglink doctor: one line per check (python, packages, fonts, screens), each ending in OK or FAIL with a fix hint.
- python -m wfglink live --synthetic: the full booth screen on generated video.
- python -m wfglink validate --suite led: reads data/raw/led_33rpm.*, led_45rpm.*, led_ruler.* (any of .mp4 .mov .ts .avi; recordings split across loop files are named _a, _b) and data/raw/led_notes.yaml with keys dashcam_model, file_type, resolution, fps, date_stamp ("off" or where it sits, which you then mask), wdr_hdr, camera_height_cm, led_radius_mm (list of 3), turns_timed, time_33rpm_s, time_45rpm_s. True speed = 2π × radius × turns_timed / time. Prints LEDs tracked per clip and the median speed error, and writes results/validation/led_report.json. Goal median error ≤ 5%. Also accept room_test.* and night_drive.* in data/raw (night_drive is a hard negative: report false counts per minute).
- ./booth/booth.sh and booth/booth.command: plays the approved clip playlist in a loop through wfglink, keeps the Mac awake, restarts on crash. Keys: L, T, F, G, Space, Esc with confirm.
- python scripts/mac_soak.py --hours 8: runs the booth screen with the playlist, logs fps and memory, and prints a PASS or FAIL report at the end.
- Also make print-ready A5 placards in booth/placards/ (Korean and English): "This is the sensor" for the dashcam stand and the limits card.

My hands-on work is now two sittings: sitting 1 (setup, dashcam, LED rig, recordings, validate, send files) as soon as parts arrive, and sitting 2 on the final evening (update, booth, overnight soak, rehearsal). Keep the Monday Oct 19 target and update PLAN.md and LOG.md with this change."

### 2026-10-15, booth change: LED test dropped; raw/analysed toggle; "Become an ember" live mode
Answer: "Booth change, decided by me: drop the LED turntable test completely (and remove the led suite, led_notes.yaml and the turntable steps). Add two booth features instead.

1. Raw / analyzed toggle: one key (A) fades the fire footage between the raw clip and the full overlay (ember trails, wind arrows, counters) over about 0.5 s. The booth starts in analyzed mode.

2. "Become an ember" live mode:
- Live camera input: the MacBook built-in camera or a USB UVC webcam, chosen by name in config. Request camera permission properly on first run. No iPhone and no Continuity Camera.
- Write a single self-contained HTML page (booth/ember/index.html, no external requests) that fills a phone screen with a glowing orange ember that flickers slightly, keeps the screen awake where the browser allows, and shows a short ko/en instruction overlay that fades out after 3 s. It must look polished: black background, soft glow, no clutter. I will host it on GitHub Pages; make the page work from any static host.
- Tracking tuned for phone screens 1 to 3 m away indoors, up to 6 at once, rejecting room lights and other static bright objects. Each tracked phone gets a trail, an ID and a speed.
- Calibration: speeds in m/s at a fixed standing distance set in config (default 2.0 m), from the camera's field of view, labeled "measured at 2.0 m". Provide a one-command calibration using a printed A4 target held at the standing spot.
- Screen: the same design as the fire mode, with a header "당신이 불티입니다 / You are an ember", live count of embers, per-ember speeds and the wind arrows computed from all tracked phones. Key M switches between fire footage mode and live ember mode; the booth starts in fire mode.
- Validation: test with synthetic phone-like blobs and with a clip I record of me moving my phone at the standing spot; report detection and tracking quality, and measure speed against a known motion if possible (for example, a phone moved along a ruler-marked 1 m path in a timed 1 s).

Update PLAN.md, LOG.md, the README and the booth runbook. Keep the Monday Oct 19 target, and the always-demo-ready rule."

### 2026-10-15, sitting 1 tonight; booth limits; dashcam as a UVC camera
Answer: "Good work. Three requests:

1. Give me a sitting 1 I can run TONIGHT with no new parts: the MacBook's built-in camera plus my iPhone. Exact commands in order: setup, doctor, fire mode on an approved clip, ember mode with the built-in camera, the A4 calibration (I'll print the target), and opening the phone page locally on my iPhone over the same Wi-Fi if GitHub Pages isn't set up yet. One checklist, one combined report I can paste back. Also tell me exactly how to publish booth/ember/index.html on GitHub Pages in this repo (or a separate repo if that's cleaner) and set its address for the QR code.

2. Booth limits: cap ember mode at 3 tracked phones (extra phones are ignored, with a small "max 3" note). In fire mode, if the scale fix isn't validated by Saturday, use pre-scaled half-resolution booth copies of the clips, since that detects more embers.

3. Camera input: also support a dashcam in USB "PC camera" (UVC) mode as the live source, selected by name like any webcam. I may buy one so the booth camera is a real dashcam.

When the verification fixes are done, send me the exact command list and every difference from my manual, as one block I can forward."
