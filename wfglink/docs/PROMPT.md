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

### 2026-10-15, strict phone-suite non-regression
Question: "The handoff requires ember-suite numbers not to worsen. The phone fix removes lamp over-counts and improves recall and identity switches, but median speed error rises slightly from 3.23% to 3.25% (still below the 10% goal). Should I keep working toward strict non-regression, or accept this documented tradeoff?"
Answer: "Keep strict non-regression"

### 2026-10-17, precision-first fire-ember verifier (task brief, verbatim)
Answer (uploaded task file wfglink-claude-code-high-precision-prompt.txt):

"Continue wfglink in Sparkxt-0318/wildfireguardian, draft PR #53. Implement and evaluate a precision-first fire-ember candidate verifier. This is an execution task: deliver a working opt-in prototype, a bounded comparison and an honest evidence report. Do not stop at proposing an architecture.

CONTEXT AND OBJECTIVE

The current prototype runs, but C5 detection quality is poor. We want substantially higher precision on genuine, image-visible ember observations, with useful recall and measured runtime performance. A larger model name or a passing UI gate is not the objective.

The recommended design is:
existing candidate detector -> short causal candidate/track verifier -> explicit acceptance decision -> accepted observations and measurements.

The learned verifier must distinguish actual ember candidates from the hard negatives that currently fool the system: fixtures, reflections, lights, flame/glare edges, moving background objects and compression artifacts. Preserve raw proposals so the verifier's effect remains measurable.

The submission is October 18, 2026; the booth is October 25. Keep this bounded and prioritize a reviewable software improvement. The dashcam/GNSS dock, optical-sync firmware, new hardware and forecasting/routing work are outside this task.

1. ESTABLISH THE BASELINE AND PRESERVE OWNERSHIP

- Read the applicable AGENTS.md/CLAUDE.md, wfglink/README.md, PLAN.md, recent LOG.md entries, docs/METHODS.md, docs/LIMITS.md and results/validation/continuation_20261015/RELEASE_README.txt. The old docs/handoff/HANDOFF.md is historical and contains superseded instructions; do not reapply its old patch.
- Inspect the current PR and local Git state. Expected last reviewed PR head: c91bc87e58ed6f7c32825e4a2b6d57d30a36cd90, branch claude/practical-rubin-5vu12u, base Main. Verify rather than assuming that this is still current.
- Published demo wfglink-demo-20261015-4 peels to tested application source 4d0092cb7808dc2fa4b2f6321ae9fd2ea5b95a53. Preserve that tag and its artifacts.
- Work only inside wfglink/. Never alter or import forecasting, routing or Monte Carlo code. Never modify root dependencies/configuration. Raw videos and large generated caches stay uncommitted.
- Preserve other people's changes. Do not switch branches, stash, reset, rebase, force-push or merge Main. If the checkout has advanced, account for the changes and use the existing branch without discarding work.
- When codebase-memory MCP is available, confirm the graph project and generation, use Tier 2 graph discovery, read exact material snippets, and check coverage for every relied-on path. Read missed/stale ranges directly. If the tools are unavailable, state that and use bounded exact-source inspection without claiming graph verification.
- Record the exact source, environment, configuration, input hashes and output locations before experiments. Keep frozen raw baseline reports separate from later summaries.

Current evidence, with distinct populations:

- C5 NIST imagery: 20 frames and 40 agent-labelled tiles, reused for development. Final TP=24, FP=168, FN=20: precision 12.5%, recall 54.55%. Earlier TP=10, FP=148, FN=34. These are frame/tile detection results, not final accepted-track precision.
- Synthetic phone development suite: median trailing-window relative speed error 3.228608%, with strict deterministic full-rate non-regression. Identity switches remain 5.206 per phone-minute, missing the goal.
- Previously frozen held-out synthetic fire base condition: median track-speed relative error 1.96%, conditional on successful tracking; frame recall 25.05%, F1 0.3867. Exposure acceptance and count-interval coverage were zero in that condition.
- Separate controlled bright-population count coverage: 200/200 clips. Do not generalize this to real footage or incomplete detection.
- Committed regression: 550 passed, 3 skipped; four short demo gates passed. Preserve failures and the actual scope of each check.

There is newer LOCAL overnight evidence not yet in the PR. The run at
/Users/jp/Documents/Codex/2026-10-15/files-pasted-by-the-user-you/work/wfglink-native-review/logs/soak/20261016-0016/
completed 8.06 hours elapsed, with 7.75 hours recorded running. Median paint rate was 29.2 fps, p5 26.8; the fitted memory slope was about -2.9 MB/hour; processing errors were zero. Its OVERALL VERDICT WAS FAIL because four stale-heartbeat events triggered restarts late in the run. Raw booth logs corroborate four hang-triggered restarts. Cause is unresolved. If this Mac path is inaccessible, label this as owner/orchestrator-supplied local evidence, not an independently inspected run. Do not claim the overnight gate passed or silently weaken it.

2. USE THE LITERATURE CORRECTLY

Read these primary sources, extract the relevant methods, and record which parts you actually accessed:

- Bouvet et al., NIST TN 2093 (2020), and corresponding 2021 Emberometer work:
  https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2093.pdf
  https://doi.org/10.1007/s00348-021-03277-6
  Relevant: multiview/spatiotemporal correspondence, trajectory filtering and fragmentation. Its short/low-displacement trajectory rejection trades off against genuine slow firebrands. Four synchronized cameras supply evidence unavailable to a single ordinary camera. Do not turn a low spurious-trajectory fraction in one controlled case into a general detection-precision claim.

- Wessies, Bouvet and Link, Classification of Airborne Firebrand Combustion State Using a CNN (2023):
  https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=936170
  Relevant: lightweight/transfer-learned classification of small particle crops. Its approximately 95% accuracy distinguishes flaming from smoldering among already tracked firebrands; it does not classify ember versus background. The imaging system includes modified cameras and IR filters. Its weights/results are not a validated RGB ember detector.

- Methodology for detecting firebrand generation and the analysis of influential variables in quantification (2025):
  https://www.sciencedirect.com/science/article/pii/S0379711225002139
  https://doi.org/10.1016/j.firesaf.2025.104549
  Relevant: U-Net-based firebrand segmentation. The accessible abstract reports over 80% accuracy in wind-tunnel work; do not reinterpret that as precision, recall or independent field performance without the necessary definitions and full evidence.

- FIgLib and SmokeyNet (2022):
  https://arxiv.org/html/2112.08598
  Relevant: spatial/temporal context, difficult negatives and complete-fire splits. This is smoke detection, not individual-ember detection. Borrow evaluation and temporal-context ideas; do not use smoke classification as proof that a candidate is an ember or make visible smoke a mandatory detection gate.

- Shrivastava et al., Online Hard Example Mining (CVPR 2016):
  https://arxiv.org/abs/1604.03540
  Relevant: preferentially train on the difficult mistakes rather than overwhelming the learner with easy background. This is a general detection method, not an ember performance result.

State clearly which design choices are proposed adaptations. Do not promise that any paper's accuracy, mAP or position error transfers to wfglink.

3. AUDIT THE FAILURE BEFORE TRAINING

Reproduce the existing C5 development scoring with its original settings and provenance when the source data are available. Do not alter the matching radius, label-confidence rule, ROI or time interval to inflate the baseline. Preserve any inability to reproduce as an explicit discrepancy.

Create an inspectable error inventory with full-resolution crops, neighbouring frames, source times, candidate/track IDs and spatial context. Identify:
- true ember, fixture/light, reflection, flame/glare edge, moving non-ember, codec artifact;
- duplicate components or fragments, localization/matching errors, annotation uncertainty;
- whether each false proposal survives confirmation, appears in the display, or generates a count/gate crossing.

Human review and independently adjudicated labels are stronger evidence than agent-only labels. Agent-only results remain explicitly provisional. Do not automatically treat ambiguous annotations as background or silently remove them from the report.

Inspect the actual code. The reviewed path already has background subtraction, a compression-mirror test, multiscale proposals, Kalman/Hungarian association and static-track handling. It computes a warm-colour feature, but the inspected detector's final candidate filter is based on finite moments, geometry and large-region masking. Do not propose simply adding tracking/background subtraction as if they did not exist. A blanket warm-colour veto can reject genuine saturated or pale embers and will not reliably reject warm reflections.

4. BUILD A BOUNDED COMPARISON

Compare the unchanged baseline with exactly three candidate families:

A. A stricter rules-based verifier using informative existing features and measured temporal/background evidence.
B. A lightweight image-patch classifier using a target crop plus surrounding context.
C. A causal temporal verifier using recent candidate-centred crops/context and motion/background features.

For B/C, use actual development false positives as hard negatives, alongside independently labelled real positives. Synthetic augmentation can supplement real material, but cannot substitute for real evaluation. Keep all augmented crops/re-encodes from one recording in the same group. Deduplicate near-identical samples and avoid letting a persistent lamp dominate the training set through thousands of redundant frames.

Use a small supported model and minimal pinned dependencies. Specify a finite epoch/wall-time budget, fixed configurations, seeds and early-stopping rules before training. At most two predetermined seeds per learned family; no open-ended architecture search. If training data are inadequate, still complete the interfaces, rule baseline, dataset tooling and reproducible training/evaluation commands, and state why learned results are provisional or unavailable. Do not present a randomly initialized or untrained verifier as a finished detector.

Use only past/current frames in live mode and report the confirmation delay. If a separate offline bidirectional mode is useful, label its use of future frames and score it separately. Camera motion requires registration or an explicit unsupported state; a fixed-camera background rule must not be silently applied to moving dashcam footage. Unresolvable or out-of-distribution candidates should be withheld with a reason.

5. INTEGRATE WITHOUT DAMAGING THE EXISTING DEMO

- Deliver a named opt-in high-precision mode. Keep the legacy default and existing published demo intact during this task.
- Keep the phone detector/tracker, velocity estimator and calibration behavior unchanged. Verify the exact existing deterministic phone non-regression contract, not merely a rounded median or a relaxed tolerance.
- Retain raw proposals and the original frame-detection metrics. Add explicit states such as candidate, method-accepted, rejected and insufficient evidence. "Accepted" means accepted by this method, not independently proven to be a true ember.
- Only accepted tracks may feed the new mode's counts, gate crossings and measurement summaries. All consumers must use the same acceptance decision.
- Define acceptance transitions, fragmentation handling and count timing. If confirmation occurs after a crossing, specify whether bounded retrospective reporting is supported; retain the original event timestamp and separate it from the decision/reporting time. Never create a fictitious speed or crossing time from confirmation latency.
- Preserve original timestamps and units. A classifier cannot establish ember depth, physical scale, exposure or wind accuracy. C10 remains tracking-only throughout overlays, tables and summaries.
- Batch patch inference and bound history/queues. If the processing budget is exceeded, report incomplete analysis/abstention; do not silently drop difficult targets while claiming complete counts.
- Keep model weights/caches ignored unless repository policy explicitly permits a small licensed model artifact. Record acquisition/training commands, licenses and hashes. The mode must report unavailable weights clearly, with no silent fallback to calling raw proposals accepted embers. Offline operation should be reproducible once the declared assets are present.

6. FREEZE A FRESH EVALUATION PROTOCOL

Before final scoring, save and hash a protocol with data manifests, source identity, observability rules, matching criteria, metrics, operating thresholds and the validation-selection rule.

Use approved, provenance-recorded footage. No YouTube downloading, invented permissions or unrequested contact with authors/agencies. Inspect existing permissions before acquisition or model training. If additional approval, annotation or recordings are unavailable, keep the test status unavailable rather than manufacturing data.

Separate training/development, threshold calibration/selection and a sealed final test. Group by complete recording, physical camera/deployment and incident. Overlapping segments, alternate resolutions and re-encodes must never cross groups. Include a genuinely unseen-camera evaluation when available. C5 remains development evidence.

The OLD mismatch and coverage suites have already been scored once. Do not retune on, regenerate, overwrite or rerun them for this new method. New method claims need a new, separately identified evaluation population.

Annotate observable targets independently of the model, using neighbouring frames and full-resolution context. Do not define eligibility by whether a target passes the verifier's minimum track length, brightness or confidence. Score all annotated observable targets, with separately reported size/visibility/camera strata and ambiguity sensitivity. A narrowly supported operating envelope must be explicit and fixed before final scoring.

Use predeclared one-to-one matching at two levels:
- Frame detections: precision/recall with a justified tiny-target location tolerance.
- Accepted tracks: precision/recall with fixed temporal support and spatial criteria. Duplicate fragments cannot each become a true positive for the same ground-truth trajectory; report fragmentation and identity switches separately.

Also report unique false accepted tracks/minute, false gate crossings/minute and time occupied by false tracks. One persistent false lamp must not look harmless because it counts as one event. Rejections and abstentions remain misses for recall. Zero accepted predictions means precision is undefined and the capability has not passed.

7. TARGETS AND EVIDENCE STATUS

Initial engineering targets for the declared final-test population:
- Accepted-track precision >=99%.
- Accepted-track recall >=50% over independently annotated observable tracks.
- False accepted tracks <=0.1/minute on representative negative footage; also report false gate crossings and persistent false-track time.

These are targets, not promised results. The 50% track-recall target is not comparable to the old 25.05% frame recall. Report the precision-recall curve and accepted-output coverage, not just a selected attractive point. Do not lower these targets after observing results to manufacture a pass.

Distinguish a point-estimate target from statistical validation. Report uncertainty using independent recording/camera groups. A claimed validated 99% precision needs adequate independent evidence, including a defensible one-sided lower confidence bound. Hundreds of correlated frames are not hundreds of independent trials. If samples or annotation quality cannot support the claim, use INSUFFICIENT_EVIDENCE even if observed precision is 100%.

Select the candidate and acceptance threshold on validation/calibration material only. Freeze the selected source, weights, thresholds and protocol, then score the new sealed test once. Preserve failed results. Subsequent improvement requires a new test population rather than silently recycling the inspected final test.

Measure performance separately from accuracy:
- Fixed source, resolution, cadence, device/backend and dropped-frame policy.
- Actual analysis throughput, median/p95 processing latency, source-to-result latency, confirmation delay, queue/backlog behavior and peak/sustained memory.
- Preserve the existing median paint >=20 fps and p5 >=10 fps criteria for live checks. An initial latency target is p95 source-to-accepted-result <=250 ms at the declared configuration; log misses and any speed/accuracy tradeoff.
- A fast isolated model call or 30 fps camera capture is not end-to-end throughput evidence.

8. REGRESSION AND RELIABILITY

Run meaningful tests for the new acceptance/counting path, model-unavailable behavior, causality, timestamps, ambiguous candidates, duplicates and bounded retained state. Include deliberate failure controls proving that the metrics catch an empty detector, a persistent false light and duplicate accepted tracks.

Run the relevant existing tests, strict phone non-regression, complete regression and unchanged four-mode demo gate on the final committed source. Preserve skips/failures and report the actual new totals; do not quote the old 550 as a new run.

Accuracy and reliability are separate gates. The existing failed overnight soak remains failed until its cause is understood and a qualifying rerun passes. Carry that failure into the report; do not turn the negative memory slope into an application-wide memory-bound claim. Do not let soak diagnosis expand into an unrelated refactor. Run any long candidate soak serially on the Mac using unchanged criteria, or mark it NOT_RUN when the host/time is unavailable. Never run competing training, heavy benchmarks or a second booth instance during a qualifying soak; do not stop other owners' jobs without authorization.

9. DELIVERABLES AND PUBLICATION

Deliver:
1. Working opt-in mode with exact launch/process commands, configuration and reproducible model/data preparation.
2. Baseline false-positive audit and inspectable example sequences with credits/provenance.
3. Frozen protocol and grouped data manifests, with annotation provenance and rights status.
4. Baseline/rules/image/temporal comparison at matched recall or stated operating points, including runtime cost and uncertainty.
5. Raw frame metrics and accepted-track/count metrics kept separate.
6. Source/weight/config/input hashes and a compact evidence manifest.
7. A concise status table for implementation, data, annotation, accuracy, speed, phone non-regression, demo, reliability and default promotion. Use PASSED, FAILED, NOT_RUN, PROVISIONAL or INSUFFICIENT_EVIDENCE as appropriate.
8. Updated README/METHODS/LIMITS and append-only LOG explaining the final behavior and every missed goal. Preserve historical reports. Put small durable reports under a new wfglink/results/validation/precision_<run-id>/ directory and large/temporary/raw artifacts in ignored run directories.

Follow existing numeric provenance rules: every numerical README/LOG result must have a NUMBERS.json record and its required citation tag. Use plain English without em/en dashes.

Before each commit, run the repository's wfglink staged-file and documentation guards from the directory expected by the scripts. Stage only wfglink/ paths. Commit meaningful checkpoints with [wfglink] messages and push normally to the existing draft PR #53. Do not overwrite the published demo tag, merge the PR, or promote the high-precision mode to the default in this task. Give a promotion recommendation tied to the evidence instead.

Finish with a self-contained report: what was built; exact source identity; commands; measured gains and regressions; per-population limitations; failed/unresolved gates; and the next highest-value missing evidence. If fresh data or human labels are missing, deliver the usable prototype and evaluation tooling, identify the exact missing inputs, and make no high-precision validation claim.

Proceed autonomously with routine implementation decisions. Keep the work bounded, preserve the existing demo, and optimize for demonstrated precision at useful recall rather than an attractive headline.
"

Question: "The plan is written. Should I start?" (options: proceed as planned; minimum deliverable only; proceed but skip USFS data)
Answer: "Proceed as planned (Recommended)"
