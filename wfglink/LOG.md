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

## 2026-10-15T02:20+08:00 First demo build; synthetic generator reviewed and integrated

- Goal: the first daily demo build (M2) and the reviewed synthetic generator (M1).
- Commands:
  - `bash scripts/tag_demo.sh 60`: demo gate on an export of HEAD d1bcff0 (booth UI headless, 60 s on the synthetic source and 60 s on C5).
  - Workflow `wfglink-m1-build`, synth branch: one agent built `src/wfglink/synth/`, a second reviewed it adversarially and fixed what it found. `python -m pytest -q tests/test_synth_*.py`.
- Parameters: configs/default.yaml and configs/synth/base.yaml at the commits named.
- Results:
  - Demo gate passed on both sources with no errors. Build wfglink-demo-20261015 is commit d1bcff0, recorded in DEMO_BUILDS.md.
  - The tag was created locally, but this session's git proxy refuses tag pushes (an HTTP forbidden error). DEMO_BUILDS.md on the branch now carries every demo build with the one command that turns it into a real tag.
  - The review found and fixed seven generator defects. Two change the clips: rendered spot shape no longer depends on sub-pixel position (the old renderer made a static spot read as a short streak and biased short streak lengths), and the visibility floor now accounts for motion blur. The core suite generated before these fixes is discarded and regenerated.
  - Synthetic tests pass (one slow timing test skipped by default).
- Decisions:
  - Both behaviour changes accepted. The streak-length bias I measured on the old base clip is re-examined on the regenerated suite before anything is changed in the detector.
  - The demo clip stays C5 until C9 downloads; in the gate run C5 produced no gate crossings, so it shows tracks but weak numbers.
  - Encoder output is not bit-identical between runs (a property of libx264 at preset medium); truth tables and pre-compression frame hashes are exact. Accepted; results are reported over seeds.
- Next step: regenerate the core suite, tune the detector prefilter on it, record core numbers, then run the mismatch suite once.

## 2026-10-15T03:05+08:00 Detector defaults chosen on the core suite; sitting 2 kit; investigation workflow started

- Goal: choose detector defaults on the core suite (tuning set only), integrate the sitting 2 kit, and check the method and the validation code before recording any number.
- Commands:
  - `scripts/run_suite.py core --workers 3 --tag <tag> --set ...` for five variants: no prefilter (pf0); prefilter 0.8 px with seed floor 4 DN (pf08); prefilter 1.2 px (pf12); pf12 with streak refinement (pf12ref); prefilter 0.8 px with a 6 sigma seed (pf08k6). Outputs in results/runs/suite_core_<tag>/ (not tracked).
  - `scripts/figures_suite.py core --runs pf0 pf08` (results/figures/core_completeness_pf0_pf08.png and .svg, inspected).
  - `python -m pytest -q -m "slow or not slow"`: full suite with the new defaults and the sitting 2 kit.
  - Workflow `wfglink-investigate` (run wf_15f89577-638): five investigations in separate worktrees, each followed by an adversarial verifier.
- Parameters: configs/default.yaml at commit 328293f.
- Results:
  - These tuning runs ran while other source files were uncommitted, so their numbers are not recorded; recorded numbers will come from `scripts/run_from_head.sh` on a committed tree after the investigations.
  - Without a prefilter, compressed noise dominated the detections in every case except the lowest compression. Each prefilter variant removed most of them; the widest prefilter gave the lowest false-detection rate with the same F1 and bright-ember recall as the narrower variants, so it is the default (values under Decisions).
  - Streak refinement lengthened the short streaks that dominate the core suite and raised the exposure error, so it stays off by default.
  - The exposure estimate jumped between two values for the same clip across variants. Per-seed results showed two self-consistent solutions when predicted streaks are short; the estimator now declines there (minimum predicted length under Decisions). The underlying instability is one of the investigations.
  - Sitting 2 kit (agent-built): the simulator finds that the half-speed hold cannot reach the plan's clean-frame yield threshold with a scanning panel and a global-shutter camera, while every source frame is still analysed at least once. The dry run passes end to end. Full test suite passed.
- Decisions:
  - Detector defaults: detect.prefilter_sigma_px 1.2, detect.threshold.min_seed_dn 4; velocity.exposure.min_length_px 4; detect.streaks.refine off.
  - Before any number is recorded, a workflow audits the validation code with oracle inputs (truth fed in as perfect estimates must score perfectly), stabilises the exposure estimator, investigates dense-shower tracking, closes booth gaps (iPad paused state, process-mode stats, longer event history), and reviews the sitting 2 kit, including a coverage-based hold rule in place of the 0.8 yield rule.
  - The mismatch suite is generated but not evaluated until the method is final; it is evaluated once.
- Next step: apply the accepted fixes from the workflow, rerun the tests, record the core numbers from a committed tree, then evaluate the mismatch and coverage suites once.

## 2026-10-15T08:10+08:00 Investigation workflow integrated: oracle-audited metrics, honest exposure estimate, dense-scene tracking, booth gaps, sitting 2 review

- Goal: fix what the first core runs exposed before any number is recorded.
- Commands:
  - Workflow `wfglink-investigate` (run wf_15f89577-638): five investigators in separate git worktrees, each followed by an adversarial verifier that reapplied the patch, reran the evidence against an export of the unpatched commit, and accepted, fixed or rejected it. All five were accepted with fixes. Their reports and patches are kept in this session's scratch folder.
  - `git apply --3way` of the five verified patches; two conflicts in the simulator (pause support against the new panel physics) merged by hand; `python -m pytest -q -m "slow or not slow"`.
- Parameters: configs/default.yaml after this entry's commit (new keys for tracking, exposure, capture and sitting 2, each commented).
- Results:
  - Oracle audit: with the ground truth fed in as perfect estimates, detection, tracking, velocity, completeness and gate metrics score perfectly. Five scoring bugs were found and fixed before any number was recorded: the field truth covered unscored frames, case summaries took medians of signed errors, the gate truth counted crossings inside flame and headlight regions, CLEAR MOT persistence did not survive a dropout, and the bridged gate truth treated repeated frames as detections. Oracle tests now guard each of them.
  - Exposure: the old estimator's answers depended on its own previous answer (a staircase map with two stable fixed points). The new one fits once on fixed speed cuts and declines unless the answer is stable and lengths are shown proportional to speed. It now declines on the whole core suite, because measured streak lengths are not proportional to true length (a floor for short streaks, lost ends for long faint ones); with true lengths swapped in, it accepts and is accurate. Streak speeds are therefore not reported on the core suite until the length measurement is fixed.
  - Tracking: in dense showers most identity switches came from wrong associations while an ember flickered out, helped by a process noise far above what embers do. Per-track adaptive process noise, a density-limited gate, coasting over longer dropouts and gap filling reduced identity switches and false track points on every core case; the verifier calibrated the adaptation so noisy turning targets (LED turntable) do not fragment. C6 tracks no longer zig-zag.
  - Booth: a paused or absent iPad is detected from the frame codes and shown, and the chain falls back and recovers; process-mode reports carry pipeline stats and source events; the report keeps more events. I added a start-up grace after each camera reopen, after the verifier noted that a slow exposure settle would otherwise fail every reopen.
  - Sitting 2: the coverage claim holds (at the half-speed hold, coverage is complete exactly when the unclean time per content change is shorter than one camera frame, while the yield averages lower). Check B now measures coverage over camera restarts; the soak analysis and the --finish process handling were hardened; the runbook paths, the Video menu step and the Korean text were corrected.
  - Also mine: a content test for repeated frames from lossy re-encodes (the oracle verifier found that such repeats were analysed); the sitting 1 Video menu step moved to the live view; METHODS section 1 and PLAN section 17 (changes after approval) written.
- Decisions:
  - Booth hold rule is now coverage-based (PLAN section 17); the yield is still reported.
  - The next workflow fixes the streak length measurement (three independent approaches, judged and verified on the core suite only).
  - Core numbers are recorded only after that, from a committed tree with `scripts/run_from_head.sh`; the mismatch and coverage suites are generated and wait untouched.
- Next step: commit after the full test run, launch the streak-length workflow, then record core numbers and evaluate the held-out suites once.

## 2026-10-15T08:22+08:00 Core suite numbers recorded from a committed tree

- Goal: record the core (tuning) suite numbers from committed code, with clean provenance, before the streak-length fix and the held-out suites.
- Commands:
  - `bash wfglink/scripts/run_from_head.sh python scripts/run_suite.py core --no-generate --workers 2 --record` at commit c046cbd (log results/runs/record_core.log, not tracked). run_from_head exports HEAD with `git archive`, so every entry has git_dirty false.
  - `bash wfglink/scripts/run_from_head.sh python scripts/figures_suite.py core` at commit bf6b5c7: results/figures/core_completeness.png and core_case_errors.png (plus SVG), both inspected.
  - A diagnostic of the vertical field error on `base` seeds 0 and 1 (scratch script, nothing recorded from it).
- Parameters: configs/default.yaml at c046cbd (config SHA-256 in each NUMBERS.json entry); three seeds per case.
- Results:
  - Detection: in the `base` case F1 is 0.386 <!-- n:core.base.f1 --> with precision 0.88 <!-- n:core.base.precision --> and recall 0.246 <!-- n:core.base.recall -->; recall on bright embers is 0.855 <!-- n:core.base.recall_bright -->. Half the embers are found at an SNR of 15.2 <!-- n:core.base.snr50 -->, so most embers of the base case lie below the detection limit. Only `snr-30` meets the plan's F1 goal, at 0.907 <!-- n:core.snr-30.f1 -->; the goal at low SNR is missed and is reported as missed.
  - False detections: 3.05 <!-- n:core.base.fp_per_mpx_frame --> per megapixel per frame in `base` and 0.12 <!-- n:core.crf-18.fp_per_mpx_frame --> in `crf-18`, so most of them come from compression.
  - Track velocity: the median relative speed error is 0.020 <!-- n:core.base.track_speed_med_rel_err --> in `base` with a median direction error of 1.01 <!-- n:core.base.direction_med_err_deg --> degrees, inside the goal in every case with tracks except `crf-28` at 0.205 <!-- n:core.crf-28.track_speed_med_rel_err --> and `snr-3` at 0.427 <!-- n:core.snr-3.track_speed_med_rel_err -->.
  - Tracking: MOTA is 0.243 <!-- n:core.base.mota --> in `base` (limited by missed faint embers) and 0.952 <!-- n:core.snr-30.mota --> in `snr-30`. Dense showers still switch identities: 204 <!-- n:core.density-high.id_switches --> per clip in `density-high` against 45 <!-- n:core.base.id_switches --> in `base`.
  - Counts: the gross gate count is low by a relative 0.735 <!-- n:core.base.cpc_gross_rel_err --> in `base`, because faint embers are not detected; its interval holds the truth in a fraction 0.0 <!-- n:core.base.cpc_gross_in_ci --> of `base` clips. Every `base` clip's count lies between the bright-ember truth and the all-visible truth (fraction 1.0 <!-- n:core.base.gate_between_bounds -->), which supports stating counts as lower bounds. In `snr-30` the error is 0.086 <!-- n:core.snr-30.cpc_gross_rel_err --> and the interval holds the truth in a fraction 1.0 <!-- n:core.snr-30.cpc_gross_in_ci --> of clips.
  - Exposure: the estimator declined in every case (`base` value 0.0 <!-- n:core.base.exposure_ok -->), as expected until streak lengths are proportional to true length; streak speeds are therefore not reported.
  - Field: in `base` the horizontal field error is 2.08 <!-- n:core.base.field_rmse_ember_u --> px/s and the vertical one 39.96 <!-- n:core.base.field_rmse_ember_v --> px/s. The diagnostic showed the vertical error is not a scoring bug: each cell mixes embers of four terminal velocities, so a cell's median depends on which embers are detected, while the overall medians agree. This is the vertical bias already stated in METHODS and LIMITS. In uniform flow the ember and air errors for the horizontal component are equal by construction (no lag in steady uniform flow); they differ in `flow-shear`, at 5.14 <!-- n:core.flow-shear.field_rmse_ember_u --> px/s against the ember field and 10.30 <!-- n:core.flow-shear.field_rmse_air_u --> px/s against the air field, which is the lag the field is meant to show.
  - Figures: the case errors figure said "n/a" where the exposure estimator declined; it now says "declined" (and "no tracks" where no track qualified), with a test.
- Decisions:
  - These are tuning numbers. Headline numbers will come from the mismatch suite, evaluated once after the streak-length fix.
  - No retuning on these numbers: the detection limit is set by compression, and the README states it.
- Next step: review and apply the streak-length workflow result, rerun the tests, re-record the core numbers, then evaluate the mismatch and coverage suites once.

## 2026-10-15T08:50+08:00 Demo build on 1c57833; pipeline counters in the booth heartbeat for the soak

- Goal: keep a demo build on the latest commit, and make the overnight soak show whether the booth kept measuring, not only whether it kept painting.
- Commands:
  - `bash wfglink/scripts/tag_demo.sh 60` (log results/runs/tag_demo_20261015b.log, not tracked).
  - `python -m pytest -q tests/test_sitting2.py -k "pipeline or sample_row or soak"`; `python -m pytest -q -m "slow or not slow" tests/test_pipeline.py tests/test_booth_app.py -k "booth_mode_through or runs_end_to_end"`; `python -m pytest -q -m "slow or not slow" tests/test_sitting2.py`.
- Parameters: new key `sitting2.analysis_stall_s` (180 s).
- Results:
  - Demo gate passed on 1c57833 with no errors on the synthetic source and on C5, so `wfglink-demo-20261015-2` is recorded in DEMO_BUILDS.md (the tag push is refused by the session's git proxy, as before). The clip run painted fewer frames than the morning build because the container was heavily loaded by the coverage generation and the streak workflow.
  - The heartbeat now carries the active pipeline's counters (frames received, analysed, repeated, unclean, without codes, loops, source frames shown). The soak analysis compares them between samples of one app instance on one source and reports the share of frames read clean, the source coverage, and stalls: stretches of at least `sitting2.analysis_stall_s` in which frames arrived but none was analysed, or none arrived. Any stall fails the soak, since a paused or hidden iPad should make the booth switch source within seconds. Older CSVs without the counters still analyse ("not enough data" for this part).
  - New and extended tests pass. The sitting 2 dry run failed its check B coverage assertion during this run; the change does not touch the coverage computation, and the dry run's simulated camera runs in real time, so CPU starvation is the likely cause. A control run of the same test on the committed HEAD under the same load is running.
- Decisions: a soak stall is a failure, not a warning.
- Next step: read the control result; if the dry run also fails at HEAD under load, rerun both when the load drops and record the outcome here.

## 2026-10-15T09:40+08:00 First full real-clip run (C5) fails: compression flicker floods the detector

- Goal: process C5 (NIST Emberometer lab clip, left half, development split) in file mode from a committed tree and inspect the overlay.
- Commands:
  - `bash wfglink/scripts/run_from_head.sh python -m wfglink process data/clips/C5_nist_emberometer.yaml --out results/runs/process/C5_head` at 1c57833 (aborted) and at 72017fa (completed; outputs in results/runs/process/C5_head, not tracked).
  - Diagnostics in scratch scripts: global frame-to-frame shift by phase correlation, detection counts per frame against the source keyframes, booth-style downscaled analysis on a few seconds of C5.
  - Control for the sitting 2 dry run: the same test on an export of the committed HEAD under the same load.
- Parameters: configs/default.yaml at 72017fa.
- Results:
  - The first attempt aborted in the overlay writer after the first pass: Qt found no display. File mode now selects the offscreen platform itself when no Qt application exists; a test runs the writer with no display variables set (it fails on the old code).
  - The completed run is wrong in a way the synthetic suites never showed. Thousands of detections per frame lie along the edges of static structures (frames, people, floor pans), tens of thousands of short moving tracks result, and the gate's net count is exactly zero, the signature of jitter rather than embers. The real embers, a few dozen bright orange streaks per frame, are drowned.
  - Causes established: the camera is static and the brightness steady, so neither motion nor flicker of the lights; the clip is almost free of sensor noise, so the per-tile noise maps give nearly zero in flat areas and the seed threshold sits on its floor; compression error at edges passes it, and the detection count jumps with the encoder's quality cycle and decays between jumps. Booth-style downscaled analysis floods the same way, so the booth demo on C5 is not presentable until this is fixed.
  - The sitting 2 dry run fails the same coverage assertion on the committed HEAD under the same load, so that failure is load-dependent and not caused by the heartbeat change.
- Decisions:
  - Workflow `wfglink-real-scene-fp` (run wf_74e1a089-3d3): three independent detector fixes (a per-pixel temporal noise estimate, an edge-aware noise model, a free choice), each reported on one protocol (C5 and C6 counts and rendered frames, retention of bright orange embers, the synthetic core suite with limits on F1 and the detection limit, cost), then judged and adversarially verified. C5 and C6 are development clips for checking; parameters come from the synthetic core suite and physical reasoning.
  - Workflow `wfglink-plausibility` (run wf_3dda84e9-2f4) builds the plan 4.5 checks and the blind label tool in parallel.
  - The core numbers will be recorded again after the detector change; the held-out suites stay untouched.
- Next step: review the judged detector fix, reprocess C5 and C6 and inspect the overlays, rerun the demo gate, then rerun the sitting 2 dry run when the machine is quiet.

## 2026-10-15T10:30+08:00 Setup change (user decision): no live camera; the booth is real-time file playback

- Goal: carry out the user's decision of 2026-10-15 (verbatim in docs/PROMPT.md): drop the iPhone, iPad, USB webcam and Continuity Camera, the booth-prep frame codes and held frames, the loop suite, the loopback check and the camera checks, and limit 6; the booth plays approved clips in real time and analyses them as they play, fullscreen on the external monitor when connected, else on the MacBook; the LED turntable is filmed top-down with the dashcam. The user's build manual names exact commands and files, which must exist as written.
- Commands: workflow `wfglink-setup-change` (run wf_c2488d87-860), four builders in separate worktrees with disjoint files and one shared interface contract:
  - booth: `python -m wfglink live` (playlist by default, `--synthetic`, `--clip`), a real-time playlist source (booth/playlist.yaml) that skips frames rather than lag, Space pause, screen choice with hot-plug, booth.sh and booth.command without the app launcher, and removal of the camera path (camera sources and permission, booth-prep, frame codes, screen check, loop simulator, check A, the old sitting kits);
  - led: `python -m wfglink validate --suite led` reading data/raw/led_33rpm, led_45rpm, led_ruler, room_test and night_drive (split parts _a, _b) and data/raw/led_notes.yaml, with date-stamp masking, the plan's scale-free check and the user's mm/s formula side by side, and results/validation/led_report.json;
  - mac: scripts/setup_mac.sh (idempotent), `python -m wfglink doctor` (one line per check), scripts/mac_soak.py (PASS or FAIL), and A5 placards in booth/placards/ (Korean and English);
  - docs: PLAN.md version 5, the two new sitting checklists, the runbook, README, LIMITS and METHODS.
- Parameters: none yet.
- Results: none yet; the three workflows already running (streak length, real-scene false detections, plausibility checks) continue, since file-mode measurement and the booth's live analysis still depend on them.
- Decisions:
  - The old camera-era plan text is replaced in PLAN.md (version 5) rather than kept beside the new one, with a section 17 entry; the earlier text stays in git history.
  - The plan's scale-free LED check (image speed against the angular rate times each ring's fitted radius) stays the primary error, and the user's formula (2 pi times the LED radius times the timed turns over the time) is reported beside it in mm/s.
  - Target: everything ready for Monday 19 October; Tuesday 20 and Wednesday 21 become buffer.
- Next step: integrate the four patches, run the full tests, verify with a separate workflow, then give the user the exact list of any differences from the manual.

## 2026-10-15T12:40+08:00 Setup change integrated; then the booth change (LED test dropped, raw/analysed toggle, "Become an ember" live mode)

- Goal: integrate the setup change of 2026-10-15 (playback booth without cameras), then carry out the user's next decision of the same day (verbatim in docs/PROMPT.md): drop the LED turntable test, add a raw/analysed toggle (key A) and a "Become an ember" live mode (camera, phones showing an ember page, tracking, calibration at a 2.0 m standing distance, validation), keeping the Monday 19 October target and the always-demo-ready rule.
- Commands:
  - Integration of the four setup-change patches (workflow wf_c2488d87-860) and the plausibility patch (workflow wf_3dda84e9-2f4) with `git apply --3way`; conflicts in cli.py, METHODS.md and README.md merged by hand; `python -m pytest -q -m "slow or not slow"` on the integrated tree; commits c943806, 5f82d10, 44fcbf9.
  - A frame-by-frame check of the approved clip segments (frame differences, brightness of NIST's overlay region, contact sheets).
  - Workflow `wfglink-setup-verify` (run wf_d129c456-f60) started on 5f82d10 and stopped before any verifier returned, because the booth change replaces the parts it checks; its four lenses move to the verification after the next build.
  - Workflow `wfglink-blind-labels` (run wf_af73a938-500): seven labellers, each first calibrated on twelve synthetic tiles with hidden truth, then C5 and C6 tiles (C6 to be relabelled, see below).
  - Workflow `wfglink-ember-mode` (run wf_42471a85-bef): four builders (camera input and ember pipeline with calibration, synthetic phone scenes and validation; booth screen with keys A and M; the phone page; LED removal and documents) under one interface contract.
- Parameters: configs/default.yaml at 44fcbf9.
- Results:
  - The full suite passed on the integrated tree except one booth test whose key presses were timed from start-up; on a loaded machine a late timer let the "too late" Esc land inside the confirm window. The presses are now timed from the previous press.
  - A live screenshot on C6 showed the Shutterstock dragon graphic, which is not NIST footage. The frame-by-frame check found both approved segments wrong: C6's took in the end of the graphic and the start of an uncredited still, and C5's took in the first frames of NIST's overlay. The first check had used a contact sheet with frames seconds apart. Some C6 label tiles came from the uncredited still, so the C6 tiles will be drawn again on the corrected segment and labelled again; no C5 tile is affected.
- Decisions:
  - Clip segments, from the frame-by-frame check (the clip settings files carry the details): C6 now 17.05 to 22.55 s (the graphic ends at 16.72 s, the still begins at 22.62 s; it was 14 to 24 s); C5 now ends at 19.35 s (the overlay starts at 19.40 s; it was 19.5 s).
  - The LED turntable test, the led suite and the notes template go; limit 5 no longer mentions the LED. The known-speed check moves to ember mode: a phone moved along a measured 1 m path at the standing spot, with the move time taken from the video.
  - Ember mode is the only place a camera returns; it never uses an iPhone or Continuity Camera, and nothing is recorded in the booth unless the operator runs the record command.
- Next step: integrate the four ember-mode patches, regenerate the placards with the new limit 5, run the full tests, verify with a separate workflow (the user's commands, both booth modes, ember tracking, the page in Chromium, the documents), run the demo gate, and reply to the user with the exact commands.

## 2026-10-15T13:30+08:00 Streak length: the erf edge-profile fit becomes the file-mode length (a partial fix)

- Goal: make measured streak length proportional to true length so the exposure estimate can accept and streak speeds can be reported.
- Commands: workflow `wfglink-streak-length` (run wf_87e4a266-43e): three independent methods (a full 2D model fit, an edge-profile fit along the axis, and a free choice that became a noise-weighted moment correction), each on one shared protocol (length ratio by true-length bin on seven core cases, the downstream exposure estimate on 21 core clips, cost, tests), a judge who joined the three caches on the same detections, and an adversarial verifier who recomputed the protocol from fresh detector runs. `git apply --3way` of the verified patch; tests/test_streaks.py, test_detect.py, test_exposure.py, test_pipeline.py, test_process.py; check_docs.
- Parameters: new keys under detect.streaks (method erf, and the erf block, each commented).
- Results:
  - The edge-profile fit (method erf) recovers most of the faint ends of long streaks: in the bins that decide the exposure fit its length ratios move close to one, its spread is the narrowest of the three, and its bias barely depends on ember brightness. It does not remove the floor for short streaks, which stays as it was or is slightly worse in some cases.
  - Downstream nothing changes yet: the exposure estimate still declines on every core clip tested, with every method, so streak speeds remain unreported. On full-exposure clips the method rescales the lengths rather than making them proportional.
  - The patch as built crashed file mode on C5 (one OpenCV call received more rows than it accepts when the flooded detector gave thousands of detections); the verifier split the call and added a regression test. Tracking, detection and the booth are unchanged: the method runs in file mode only.
  - Known behaviours, documented in METHODS: a length of zero when the detector's axis is far off, saturated streaks measured long (they are flagged and kept out of the exposure fit), and the gamma of the camera's tone curve as an assumption.
- Decisions: erf is the file-mode default. The next step for the exposure estimate is a fit that tolerates per-point length noise, or a motion axis taken from the track; it is not started before the held-out suites are evaluated, since the plan protects the core measurement first.
- Next step: integrate the ember-mode build and the real-scene detector fix, record the core numbers again, then evaluate the held-out suites once.

## 2026-10-15T14:10+08:00 Real-scene false detections: the mirror test against compression error

- Goal: stop the detector flooding real compressed video of bright, static, textured scenes (C5) without losing faint embers on dark backgrounds.
- Commands: workflow `wfglink-real-scene-fp` (run wf_74e1a089-3d3): three independent fixes (a per-pixel temporal noise estimate, an edge-aware noise model, and a free choice that became the mirror test) on one protocol (C5 segments in file mode and booth-style analysis with rendered frames, retention of bright orange embers, C6, the synthetic core suite with limits on F1 and the detection limit, cost), a judge, and an adversarial verifier who reproduced every number against an export of the unpatched commit and tried to break the method. `git apply --3way`; METHODS step lists merged by hand; tests/test_detect.py, test_pipeline.py, test_streaks.py, test_process.py; check_docs; a booth screenshot of C5 at 1920x1080 (inspected).
- Parameters: new keys under detect.mirror (enabled, block_px, count, ratio, cap_dn), each commented.
- Results:
  - The mirror test uses the dark lobes of the negative residual as a local reference for compression error: embers only add light, while the encoder's error comes in bright and dark pairs. Where dark lobes cluster, a seed must exceed a multiple of the strongest of them, with a fixed ceiling, so a bright ember always passes. It has no history and follows the encoder's quality cycle frame by frame.
  - On C5 the false detections, the false moving tracks and the gate crossings fall by an order of magnitude in both file mode and booth-style analysis, quality jumps no longer stand out, and every bright orange track is kept. The booth screenshot now shows the falling embers with their trails and a downward direction, with scattered faint points left on the steel frame, the people and the water pans.
  - The synthetic core suite is unchanged within the protocol's limits.
  - Costs: in a dense real shower (C6) a share of faint detections is lost where the shower's moving edge leaves dark lobes; the added time per 1280x720 frame is somewhat above the two-millisecond target; a boolean mask crash found by the verifier was fixed.
- Decisions: the mirror test is on by default. The remaining faint points on C5 are a display question for the booth (draw only confirmed tracks), decided at the ember-mode integration. Core numbers are recorded again from this commit, then the held-out suites are evaluated once.
- Next step: record the core numbers again, evaluate the mismatch and coverage suites once, score C5 against the blind labels before and after this change.

## 2026-10-15T15:20+08:00 Ember mode integrated; core numbers recorded again; C5 shows a scale problem in file mode

- Goal: integrate the booth change (LED test removed, key A, "Become an ember" with key M), record the core numbers again after the mirror test and the streak-length fit, and check C5 against the blind labels.
- Commands:
  - `git apply --3way` of the four ember-mode patches (workflow wf_42471a85-bef): the docs patch first (it removes the LED code), core's patch without its duplicate deletions, then booth and page; cli.py merged by hand; the demo gate's ember run switched to core's generated scene; placards regenerated (`scripts/make_placards.py`) and inspected; commit 7832de2.
  - `live --ember` with no camera, and `record ember_demo --fake-camera booth` then `live --ember --fake-camera` at 1920x1080, screenshots inspected.
  - `bash wfglink/scripts/run_from_head.sh python scripts/run_suite.py core --no-generate --workers 2 --record` at dba7734; `scripts/figures_suite.py core` (inspected).
  - `label-score` of the C5 run made before the mirror test against the agent labels; a diagnostic running the current detector on five labelled C5 frames at native and at half resolution (scratch script).
- Parameters: configs/default.yaml at dba7734 (core numbers) and 7832de2 (booth).
- Results:
  - Ember mode works end to end on generated phones: each tracked phone gets an ID, a speed in m/s labelled as measured at the standing distance, and a trail; the panel shows the live count and per-ember speeds, and the wind arrows come from the phones; ceiling lights, the TV and the lamp make no tracks. Without a camera it shows a calm message with what to do and the way back to fire mode. None of the macOS camera code has run on a Mac yet.
  - Core numbers at dba7734 barely move: base-case F1 0.385 <!-- n:core.base.f1 -->, detection limit at an SNR of 15.2 <!-- n:core.base.snr50 -->, track speed error 0.020 <!-- n:core.base.track_speed_med_rel_err -->; the exposure estimate still declines on every case.
  - NUMBERS.json now keeps the earlier values of a key in its history when a key is recorded again, so earlier LOG entries still match the values they quoted; README and the plan quote the current value (scripts/check_docs.py).
  - C5 against the blind labels, before the mirror test: precision was tiny (the flood) and recall low. The labelled embers on C5 are large, bright, defocused streaks close to the camera, and at native 4K resolution the detector misses most of them while it finds most at half resolution. So file mode at native resolution is wrong for near-camera embers in high-resolution video; the booth, which analyses at reduced size, is not affected.
- Decisions: the next workflow fixes the analysis scale of file mode (a resolution cap or multi-scale detection, with coordinates reported in source pixels), judged on the C5 labels, the synthetic suites and cost; the held-out suites wait for it, since it changes the method.
- Next step: the scale workflow and the verification of the ember booth (the user's commands, both modes, the page, the documents).

## 2026-10-15T15:50+08:00 Demo build with both booth modes; full suite on the ember integration

- Goal: keep a demo build on the latest commit (always demo-ready) and confirm the integrated tree.
- Commands: `python -m pytest -q -m "slow or not slow"` on the ember-mode integration; `bash wfglink/scripts/tag_demo.sh 60` at 161612e (log results/runs/tag_demo_20261015c.log, not tracked).
- Parameters: configs/default.yaml at 161612e.
- Results:
  - The full suite passed on the integration (the opt-in 720p timing check skipped as usual).
  - The demo gate now runs fire mode on synthetic video and on the playlist, and ember mode on a generated phone scene; all three runs passed with no errors, so `wfglink-demo-20261015-3` is recorded in DEMO_BUILDS.md (the tag push is refused by the session's git proxy, as before).
- Decisions: none.
- Next step: the ember-booth verification and the file-mode scale workflow.

## 2026-10-15T17:30+08:00 C10 tracking stress run (tracking only)

- Goal: run the sparkler clip (4x slow motion; user decision: tracking only) through file mode.
- Commands: `bash wfglink/scripts/run_from_head.sh python -m wfglink process data/clips/C10_sparkler.yaml --no-overlay --out results/runs/process/C10_head` at 6bcab7d (outputs not tracked).
- Parameters: configs/default.yaml at 6bcab7d; segment 40 to 60 s.
- Results: the run completed; the summary keeps tracks and drops speeds, counts and flux with the stated reason, as the clip settings ask. Nothing is quoted from it: it has no ground truth and is a stress test only.
- Decisions: an overlay check of a short C10 segment follows once the file-mode scale change lands, since that changes how 4K clips are analysed.
- Next step: integrate the booth verification fixes and the scale workflow.

## 2026-10-15T17:30+08:00 Fixes after the booth verification

- Goal: fix what the independent verification of the booth change found (the manual's commands, both booth modes, ember tracking and the camera code, the page and the documents), and add the two display features decided after looking at the screens.
- Commands: verification workflow (lenses manual, booth, ember, docs) on 6bcab7d; fixes in a separate worktree; `python -m pytest` on the touched test files, tests/test_smoke.py and `scripts/check_docs.py`; the ember suite on the cached scenes (scratch); the default demo scene `LiveScene("booth", seed 1)` through EmberPipeline at full and at half rate (scratch scripts); C5 through the booth's fire-mode analysis with every detection drawn and with confirmed tracks only (screenshots at one, three, five and nine seconds, inspected); `scripts/make_placards.py` (cards inspected, QR codes decoded with OpenCV); the page in headless Chromium (no request other than the page itself).
- Parameters: new keys ember.track.pin_reach_m, jump_m, jump_m_s, rest_protect_s, light_rest_s; ember.background.light_frames and light_frac; validate.ember.persistent_run_s; ui.show_unconfirmed; demo_gate.ember_over_max; certifi pinned for macOS in requirements.txt.
- Results:
  - The default demo scene showed its desk lamp as an ember, at no speed, for most of every run, so the live count was one too high. The cause: a phone ember sweeping past the lamp took the lamp's detection while the lamp was hidden by a passer-by, and the background under a shown ember is never learned, so the stuck ember never ended. The earlier LOG entry's "the lamp make no tracks" was wrong. Now a hidden static light waits at its own place and is assigned together with the embers, an ember that comes to rest where the light map was already bright ends after a short rest, the background is learned under an ember resting for a long time, and a jump such as a TV cut no longer counts as motion. In the same scene a lamp now carries a number only for short moments after a phone sweeps right past it, and the count stays at or below the phones in view nearly all the time; the synthetic ember suite is unchanged within noise (recall, precision, speed error, no static-light tracks).
  - The ID-switch goal of plan section 4.4 is missed on the synthetic phones, by a wide margin, mostly in the six-phone crowd, where phones overlap in the picture, merge into one blob and are told apart by position alone when they part. The report now also gives persistent switches (one-frame flips left out) and says that these scenes are the tuning set. Handling merges is the next tracker step.
  - Fire mode now draws only the points of confirmed, moving tracks: on C5 the scattered faint points on the steel frame, the people and the water pans are gone, roughly half of the points per frame; the counts, rates and speeds are identical with and without.
  - Key A acts on the fire footage only (pressing A then M had left the ember screen without its header, count and speeds); the ember header shows both languages; the ember screen shows the page's QR code and address when booth.ember_page_url is set, and make_placards.py makes an A5 QR card from it.
  - The clip download failed on python.org's macOS Python, which has no certificates until its "Install Certificates" step; it now trusts certifi's bundle, and setup checks the clips' hosts with the venv's own Python.
  - PyAV's avfoundation open can wait forever for a first frame (FFmpeg has no timeout there), so it now runs in a helper thread with a timeout, after which that camera opens with OpenCV; names FFmpeg could mistake go to OpenCV directly. M back to fire mode no longer waits for a camera that is still opening, and a permission dialog at an M press no longer stops the screen.
  - Documents: without a camera, ember mode shows a message, not generated phones (README, PLAN, METHODS, runbook and SITTING2 said otherwise); setup asks for the camera and downloads the two booth clips; doctor prints one line per check with its fix; `record --force` remakes a recording; the A4 target, the phones and the ruler share one plane over the floor mark; the Korean sensor card no longer says the booth reads this dashcam.
- Decisions: the demo gate's ember run fails when the count of embers exceeds the scene's phones in more than one percent of its frames (a rare short event after a phone sweeps past the lamp remains, so a strict maximum would fail at random); the gate gains a keys run with the real ember pipeline. A held-out ember set (new layouts, dim phones, moving warm distractors) is still to be built and run once.
- Next step: a demo build on the merged commit; then the file-mode scale workflow and the held-out ember set.

## 2026-10-15T18:40+08:00 Recheck fixes, booth limits and the dashcam as a camera

- Goal: fix what the recheck of the verification fixes still found, and carry out your three requests of 2026-10-15 (sitting 1 tonight, booth limits, a dashcam in USB "PC camera" mode).
- Commands: `git apply --exclude=wfglink/LOG.md` of the fixer's patch (its LOG entry appended above by hand, since HEAD had moved on); `python -m pytest -q tests/test_ember.py tests/test_camera.py`; `python -m wfglink demo-gate --seconds 30` and `--seconds 60`; `scripts/check_docs.py`; ember screens rendered offscreen with six phones in view (inspected).
- Parameters: ember.max_tracks 3 (was 6); new keys validate.ember.max_tracks 6 and camera.mask; the demo gate lifts the cap to 6 for its own runs.
- Results:
  - A retake with `record --force` cancelled with Esc deleted the earlier good recording. Frames now go to a hidden side file that replaces the recording only when it completes; a test covers the cancelled retake.
  - Ember mode tracks at most three phones (ember.max_tracks); further phones are not shown, and the count card carries a small "최대 N개 · max N" note (N = ember.max_tracks) (both languages). The synthetic validation still runs the tracker with up to six phones, so the tracker is tested beyond the booth's cap.
  - A dashcam in USB "PC camera" mode is a USB UVC camera to wfglink: tests with dashcam-like names (with and without a transport code, and a name starting with a digit, which goes to OpenCV because FFmpeg would read it as an index) show it classified as usb, picked by auto ahead of the built-in camera and by part of its name. camera.mask blanks a burned-in time or logo before detection.
  - Smaller fixes: the DEMO_BUILDS code fence; the runbook's missing-clip fix uses setup (two booth clips) instead of fetching every clip; the QR card step makes only the QR card, so the tracked placards are not rewritten; the QR code is one filled path, with no seams between modules; the generated phone scene has one label; doctor's help lists the camera check; the optional ember soak is two hours, since memory growth is judged only from two hours on.
- Decisions:
  - Fire mode at the booth already analyses C5 at about half resolution: the booth scales every frame to at most live.analysis_max_pixels, which for C5's crop (1920 by 2160) is a factor of 0.47, and C6 (540 by 360) plays at its own size. So the fallback you set for Saturday, half-resolution booth copies, is in effect without copies; copies would only lower decoding cost, and the soak's paint rate will show whether that matters.
  - The demo gate judges the ember count with the cap lifted (its scene has exactly three phones, so the cap would hide a lamp taken for an ember) and now also judges the ember part of the keys run.
- Next: the full test suite and the demo gate on the committed tree; the forwardable command list for you; then the scale workflow's result for file mode.

## 2026-10-15T19:20+08:00 Demo gate: the lamp over-count depends on the analysis rate

- Goal: find why the demo gate's ember runs fail on the count check (more embers than the scene's phones), which the verification's runs had passed.
- Commands: `python -m wfglink demo-gate --seconds 30` and `--seconds 60` on 2d87bf3 (this container, with the scale workflow running at the same time); the gate's generated booth scene replayed frame by frame through EmberPipeline with the cap lifted, analysing every frame, every second and every third (scratch script); the same with ember.track.light_rest_s set lower (scratch, not adopted).
- Parameters: defaults; scratch variants of ember.track.light_rest_s only.
- Results:
  - Both gate runs failed only on the ember count: the synthetic, playlist and paint checks passed, with no errors. The keys run failed the same check.
  - Replayed at the full frame rate the scene never shows more embers than phones. With every second or third frame analysed, as on a loaded machine, a phone sweeping past the desk lamp hands its ember to the lamp now and then, and the stuck ember (not moving, on the lamp) stays until the light-rest rule ends it after ember.track.light_rest_s.
  - A shorter light rest reduces the over-count but does not remove it, so the cause is the hand-off at lower rates, not the rest time.
- Decisions: no setting changed; the booth's cap of three phones means the screen never shows more than three, but at a low analysis rate a lamp can hold one slot for about a second. Next tracker step: refuse a hand-off from a moving ember to a blob on the light map. The gate's result on the Mac (the rate of the real machine) decides whether that is urgent; the demo build of 161612e stays the last tagged working demo until a gate passes.

## 2026-10-15T19:21:29+08:00 Continuation bootstrap on the Mac host

- Goal: resume the handoff in an isolated checkout of the required branch, preserving the other checkouts and all files outside wfglink.
- Commands:
  - `python3.12 -m venv .venv`; `.venv/bin/python -m pip install -r requirements.txt` (interrupted during slow downloads); `uv pip install --python .venv/bin/python --cache-dir .venv/cache -r requirements.txt` (interrupted after transfers restarted).
  - `uv pip compile --python .venv/bin/python --cache-dir .venv/cache requirements.txt -o .venv/resolved.txt`; `.venv/bin/python results/runs/download_wheels.py`, `results/runs/priority_wheels.py` and `results/runs/priority_qt.py` (ignored bootstrap helpers and logs).
  - `uv pip install --python .venv/bin/python --cache-dir .venv/cache --no-index --find-links .venv/wheels -r requirements.txt`; `.venv/bin/python -m pip install -e . --no-deps`; `uv pip check --python .venv/bin/python`; `.venv/bin/python -m pip freeze > results/runs/environment_20261015.txt`.
  - The standard-library download functions from `scripts/fetch_clips.py` fetched the approved booth clips before package installation finished; `.venv/bin/python scripts/fetch_clips.py --only C5_nist_emberometer C6_nist_dragon` then checked them against the recorded hashes. `.venv/bin/python scripts/fetch_clips.py --only C10_sparkler` fetched the approved tracking-only clip.
- Parameters: requirements.txt unchanged; resolved official PyPI wheels for this host; bounded HTTP byte ranges with SHA-256 checked against PyPI metadata; system CA bundle for the bootstrap requests. Bootstrap helpers and logs stay in ignored local folders.
- Results:
  - The exact pinned environment installed and its dependency consistency check passed. The earlier long-transfer attempts restarted instead of completing; bounded transfers completed with verified digests. A direct standard-library certificate probe failed with python.org defaults and succeeded with the system CA bundle; TLS verification stayed enabled.
  - The booth clips match their existing recorded hashes. The sparkler download also matches its existing metadata. Raw videos remain ignored. The CSV writer now keeps line feeds when metadata is rewritten on this host.
  - The native PyAV and OpenCV wheels warn about duplicate AVFoundation class names when loaded together. Synthetic processing continues, but this does not validate actual camera capture.
- Decisions: preserve the required pins and keep the changes inside wfglink. Camera permission, calibration accuracy and the overnight hardware soak still need the user's sitting reports.
- Next: complete the count fix and scale verification, run the full tests and committed-tree demo gate, then the real-clip and held-out checks.

## 2026-10-15T19:33:41+08:00 File-mode and tonight-script checkpoint; phone candidate held

- Goal: preserve the independently checked scale and sitting-script repairs while the phone change remains unaccepted under the user's strict non-regression decision.
- Commands:
  - `git apply --exclude=wfglink/PLAN.md --exclude=wfglink/docs/METHODS.md wfglink/docs/handoff/multiscale_unverified.patch`; the document hunks applied separately; material source defects repaired after review.
  - `.venv/bin/python -m pytest -q tests/test_multiscale.py tests/test_pipeline.py tests/test_streaks.py tests/test_process.py`; `.venv/bin/python -m pytest -q tests/test_sitting1_tonight.py`.
  - `.venv/bin/python results/runs/multiscale_review_20261015/verify_720p_compatibility.py` and its `--clip data/raw/C6_nist_dragon.mp4 --start-s 17.05 --end-s 22.55 --frames 10000` invocation; evidence and paired tables in that folder.
  - `bash -n scripts/run_from_head.sh scripts/tag_demo.sh scripts/sitting1_tonight.sh`; `python scripts/check_docs.py`; `git diff --check`.
- Parameters: scale thresholds unchanged from the supplied patch; exact handoff Pipeline and Detector source loaded for compatibility comparisons. The comparison runner seeds both NumPy and OpenCV. Tonight uses its own built-in-camera override and fresh report folder.
- Results:
  - Focused scale and sitting-script tests passed. Within each tested mode, old and new detections, active/final tracks, state, repeat decisions and counters agree exactly on the shared generated input and on the approved C6 lab segment. The first harness attempt failed a cross-mode input-hash check because OpenCV's global noise generator was not seeded; that failed attempt is retained, and the seeded rerun passes.
  - The scale review found and repaired lost source saturation, changed repeat decisions, quarter-scale rounding, stale shape state, and replacement logic using an intermediate level that had found nothing. These are bounded source and synthetic checks, not physical accuracy or throughput validation.
  - Tonight's script preserves booth settings, selects the built-in camera, shows its local URL before waiting, and records fresh combined reports including skipped, failed and interrupted steps. Mocked tests cover unhealthy app reports even when the app exits successfully. No camera or publication was invoked.
  - An initial whole-repository archive triggered unrelated lazy blob downloads in this partial clone and was interrupted. The export helpers now archive the wfglink subtree directly; the baseline export then completed. Demo tag names also honor the existing build ledger after a fresh checkout.
- Decisions: the supplied scale patch is integrated and removed. The phone candidate and its tests/diagnostic stay outside this checkpoint until the strict regression requirement is met. The existing demo ledger remains the reference until a committed-tree gate passes.
- Next: full tests and real-clip checks on this checkpoint, and continued phone repair. Held-out input generation uses the unchanged generator from a clean handoff export; no held-out scores are used for development.

## 2026-10-15T19:46:22+08:00 Mac regression failures and repairs

- Goal: run the complete committed checkpoint and repair every failure before release.
- Commands: `bash scripts/run_from_head.sh python -m pytest -q` at f9e72c2; focused camera and missing-camera checks; QR scan checks; placard and synthetic-render regressions; gamma endpoint equivalence controls. Logs are under `results/runs/`, including `full_pytest_f9e72c2.log`, `camera_fixture_review_20261015.log`, `platform_fixes_focused.log` and `qr_gamma_regression.log`.
- Parameters: the pinned Mac runtime, offscreen Qt, and the committed checkpoint export for the complete run. Focused repairs ran in the working tree.
- Results:
  - The complete run failed on QR scan rendering, camera fixtures that assumed a host without cameras, and the gamma black endpoint. Its failure log is preserved. The missing-camera fixture reached the real Mac camera during that failed run; it is now explicitly isolated in both worker modes.
  - QR path simplification dropped module edges at fractional coordinates on this raster backend. Filling the original winding path preserves the code, and the original scan assertions pass for screen and placard outputs.
  - The timeout fixture supplied inconsistent camera identities and hit the ambiguity refusal before the intended timeout. It now supplies one consistent device and always releases its fake blocked open. The original fallback assertions pass.
  - The gamma implementation now preserves exact black even when the SIMD power operation returns a tiny positive value. Fixed input controls retain every positive-pixel result and every quantized pixel; the focused render regressions pass.
- Decisions: keep the failed complete run and repeat the complete suite on the final committed source. These repairs do not establish actual camera measurement accuracy or an overnight soak.
- Next: finish the independent file checks and strict phone non-regression repair, then rerun the release gate.

## 2026-10-15T19:49:40+08:00 Preserve the concurrent handoff update

- Goal: integrate the remote branch update without discarding either continuation.
- Commands: normal branch push (rejected because the remote had advanced); fetch; merge without auto-commit; inspect the renamed patch and resolve the QR change; original QR scan regressions.
- Parameters: remote fc4db83 and local platform checkpoint; no branch switch, reset, rebase or force-push.
- Results:
  - The remote update preserved a revised historical handoff and renamed the already integrated patch. Its patch difference adds output documentation, which is now reflected in the plan. The redundant patch remains removed.
  - Both QR fixes are retained: direct winding-path fill and crisp module edges. The original screen and placard scan checks pass.
  - The handoff now identifies itself as historical, so its host-specific scratch results cannot be mistaken for this continuation's measurements.
- Decisions: preserve remote history and all working repairs. The frozen held-out evaluation continues from its original exported source and inputs.
- Next: commit this merge, finish the remaining bounded repairs, and publish the completed branch normally.

## 2026-10-15T19:53:11+08:00 Enforce the slow-motion tracking-only restriction

- Goal: inspect the C10 overlay and enforce its approved measurement restriction throughout file outputs.
- Commands: committed C10 process/overlay and plausibility checks at f9e72c2; focused process and plausibility regressions; independent source review; rendered Korean and English restriction notices. Evidence is under `results/runs/real_review/`.
- Parameters: the approved C10 segment with a short overlay inspection; unchanged default detector and tracker settings.
- Results:
  - The original summary omitted measurements, but the overlay still displayed speed, rate, crossing counts and flux. Export tables and deterministic reruns also retained those quantities. This failed restriction is preserved in the original outputs.
  - The repair applies the restriction to the overlay, table columns, summary units and labels, exposure handling, plausibility verdicts and deterministic reruns. Positions, track identities and detection geometry remain available. Old measurement exports and old plausibility reports are cleared when a restricted output directory is reused.
  - The focused regressions pass, including normal file mode, actual restricted-path reruns and rejection of a prior unrestricted determinism result. Independent review found a stale-report leak, which was repaired and tested. The bilingual restriction notice is readable.
- Decisions: keep the original C10 failure as evidence and rerender from the committed repair before calling the inspection complete. The C5 and C6 visual false positives remain unresolved; deterministic output is not physical validation.
- Next: inspect the repaired real C10 overlay and complete the strict phone repair and final release checks.

## 2026-10-15T19:57:54+08:00 Strict phone non-regression repair

- Goal: remove the undersampled lamp handoff while preserving every deterministic full-rate phone-suite result, as the user required.
- Commands: fixed cached phone-suite replays against the original source; exact observation and legacy-track hashes; uncapped stride replay; analytical polynomial/noise controls; focused tracker/camera tests. Evidence is in `results/runs/ember_guard/`, especially `cadence_candidate_status.json`, `fullrate_comparison.json`, `prototype_comparison.json` and `cadence_final_stride.json`.
- Parameters: unchanged detector, acquisition thresholds and trailing-window velocity estimator. The new association episode uses source-reported cadence, not requested camera FPS.
- Results:
  - Earlier broad ownership guards improved some detection and identity metrics but regressed the standing-speed median. Polynomial display trials also changed other speed diagnostics. They were rejected under the user's strict requirement; their outputs remain preserved.
  - The accepted implementation hardens association only after a reported-cadence gap creates ambiguity with a learned light. It pins each competing light's old home and diameter, assigns light blobs one to one, and reserves candidate reappearance blobs from those lights. An episode ends on recovery, expiry or loss of competition.
  - The final comparison exactly preserves all tested full-rate observation histories, legacy track fields, quality, speed and ruler metrics. Wall-clock and processing-time measurements are retained in the reports but excluded from deterministic equality. The uncapped replay removes the reproduced sparse-cadence excess counts and lamp tracks. Focused tests pass.
  - Missing or invalid source cadence cannot start protection. Backend-reported cadence is not proof of physical frame drops. Existing full-rate overlap contamination and the identity-switch goal miss remain.
- Decisions: accept this bounded undersampling repair, retain the existing velocity estimator, and preserve every rejected candidate. The checked source hashes are in the comparison report.
- Next: run the complete suite and official phone checks on this committed source, then the full demo gate and daily tag.

## 2026-10-15T20:03:14+08:00 Frozen fire suites and real-clip evidence

- Goal: complete the approved file-mode verification and the one-time held-out headline measurements without tuning on their results.
- Commands: committed-tree C5/C6 process and label-score commands; C10 process/overlay and plausibility before and after its restriction repair; `validate --suite mismatch --final --no-generate --workers 2 --tag final_f9e72c2 --record` followed once by the corresponding coverage command; `scripts/run_suite.py hires --workers 2 --tag verification_f9e72c2`. The final suite driver, exact commands, input manifests, source hashes and receipts are preserved in `results/validation/continuation_20261015/`.
- Parameters: frozen fire detector/config at f9e72c2, pre-generated inputs from the clean handoff generator, and serialized registry writers. Later phone and tracking-only output repairs do not retune that fire method. The separate gamma endpoint source repair does not replace these frozen assets.
- Results:
  - Mismatch completed 60 <!-- n:continuation.mismatch.clips --> clips with 0 <!-- n:continuation.mismatch.errors --> errors; coverage completed 200 <!-- n:continuation.coverage.clips --> clips with 0 <!-- n:continuation.coverage.errors --> errors. Each was scored once; complete per-clip rows were checked before interpreting the aggregates.
  - Mismatch base detection F1 is 0.3867 <!-- n:mismatch.base.f1 -->, recall 0.2505 <!-- n:mismatch.base.recall --> and conditional track-speed relative error 0.0196 <!-- n:mismatch.base.track_speed_med_rel_err -->. The exposure-success and count-interval coverage fractions are both 0.0 <!-- n:mismatch.base.exposure_ok --> <!-- n:mismatch.base.cpc_gross_in_ci -->. Detection and exposure goals remain missed.
  - The controlled bright-ember coverage suite covers 200 <!-- n:continuation.coverage.k --> of 200 <!-- n:continuation.coverage.n --> independent clips, fraction 1.0 <!-- n:continuation.coverage.fraction --> with exact Clopper-Pearson interval 0.981725 <!-- n:continuation.coverage.lo --> to 1.0 <!-- n:continuation.coverage.hi -->. It meets the fixed point-coverage goal of 0.90 <!-- n:continuation.coverage.goal --> for that population only. It is not evidence of coverage under incomplete detection or on real video.
  - C5's fixed agent-labelled sample has 20 <!-- n:continuation.C5.after.frames --> frames and 40 <!-- n:continuation.C5.after.tiles_scored --> tiles. True positives rise from 10 <!-- n:continuation.C5.before.tp --> to 24 <!-- n:continuation.C5.after.tp -->, misses fall from 34 <!-- n:continuation.C5.before.fn --> to 20 <!-- n:continuation.C5.after.fn -->, and false positives rise from 148 <!-- n:continuation.C5.before.fp --> to 168 <!-- n:continuation.C5.after.fp -->. Precision is 0.1250 <!-- n:continuation.C5.after.precision.value --> and recall 0.5455 <!-- n:continuation.C5.after.recall.value --> after the change. This remains poor detection on a repeatedly used development sample; old handoff scratch counts are not assigned to this Mac run.
  - High-resolution verification F1 is 0.371 <!-- n:continuation.hires.base.f1 --> for far embers, 0.744 <!-- n:continuation.hires.kind-near.f1 --> for near embers and 0.623 <!-- n:continuation.hires.kind-mixed.f1 --> for mixed sizes. No thresholds were adjusted after reading these results. Exact tested native/live outputs match the handoff implementation; core records are retained.
  - C5 exposure stability flags, and C6 timing flags repeats. Missing physical metadata leaves real speed/direction checks not applicable. The repaired encoded C10 overlay and exported geometry retain tracks without physical readouts, and same-scope deterministic reruns pass. All original failed outputs are preserved.
- Decisions: keep every missed goal and the bright-population coverage boundary visible in README. Save small sealed reports and source custody in the repository; never commit raw footage.
- Next: complete the final committed-source test and demo gate, record their outcome, and hand over the exact sitting instructions for physical validation.

## 2026-10-15T20:06:13+08:00 Final committed-source regression and phone checks

- Goal: verify the accepted source after every bounded repair and retain strict phone-suite non-regression.
- Commands: `bash scripts/run_from_head.sh python -m pytest -q`; `validate --suite ember` with a fresh report; `scripts/check_ember_stride.py --seconds 40` with its diagnostic cap lifted; `scripts/record_continuation.py` on saved sealed reports. Every command used the d640408 source export. Exact logs and JSON are in `results/validation/continuation_20261015/`.
- Parameters: pinned Darwin arm runtime, offscreen Qt, default measurement config, cached phone tuning clips and original speed estimator. Number recording reads existing reports without rescoring held-out clips.
- Results:
  - The initial committed run had 486 <!-- n:continuation.initial_tests.passed --> passed, 6 <!-- n:continuation.initial_tests.failed --> failed and 3 <!-- n:continuation.initial_tests.skipped --> skipped tests. Its complete failure log remains preserved. The final committed run has 529 <!-- n:continuation.final_tests.passed --> passed, 0 <!-- n:continuation.final_tests.failed --> failed and 3 <!-- n:continuation.final_tests.skipped --> skipped tests. Skips cover real Mac permission, a missing host-specific CA fixture and the optional timing check.
  - The exact standing median trailing-window relative speed error remains 3.228608% <!-- n:continuation.ember.speed_median_percent -->. Every tested deterministic full-rate quality, instantaneous/depth speed diagnostic and ruler result matches the original source. Timing/provenance fields are explicitly excluded from equality and remain saved.
  - The uncapped sparse replay has 0 <!-- n:continuation.stride.2.over_three_frames --> excess-count frames and 0 <!-- n:continuation.stride.2.lamp_frames --> lamp frames over 600 <!-- n:continuation.stride.2.frames --> analysed frames. The other tested strides also have no excess-count or lamp frames. This is a synthetic regression, not a real-camera accuracy claim.
  - The identity-switch rate remains 5.206 <!-- n:continuation.ember.id_switches_per_phone_per_min --> per phone minute and misses its original goal. Actual phone and ruler recordings are missing. These unresolved results are not converted into passes.
- Decisions: preserve strict deterministic phone quality without changing the estimator, and publish the failed and successful checks together.
- Next: finish the full daily demo gate, verify the tag's remote identity and publish the final records with the forwardable sitting instructions.

## 2026-10-15T20:10:39+08:00 Daily demo gate failed on the accepted phone candidate

- Goal: verify the complete live UI before creating a daily demo tag.
- Commands: `bash scripts/tag_demo.sh 60` on the d640408 export. Original outputs are copied intact to `results/runs/demo_gate_d640408_failed/`; the report and source-context receipt are also in the durable continuation bundle.
- Parameters: the original scene, timing, count tolerance and diagnostic cap lift. No gate or scene setting was relaxed.
- Results:
  - The synthetic fire, approved playlist and key runs passed. Live ember mode exceeded its count tolerance, so the command failed and no tag was created. The short deterministic replay did not cover this live timing counterexample.
  - The full committed regression and strict cached phone-suite comparison still pass, but they do not establish demo readiness. The candidate is therefore held for release. The failed report's Git fields reflect its temporary export without repository metadata; the separate receipt binds the actual tested source.
- Decisions: preserve this failed gate and keep the original tolerance, scene and strict non-regression requirement. Do not publish a successful daily build from this attempt.
- Next: capture the live sample timing and ownership trace, repair the bounded association error, then rerun the strict checks and full gate.

## 2026-10-15T20:27:06+08:00 Late background handoff repair and longer regression

- Goal: remove the late demo-gate counterexample while keeping strict phone-suite non-regression.
- Commands: the source-bound cached full-rate comparison and deterministic long replay in `results/runs/ember_guard/uncertainty_candidate/`; targeted tracker controls in `tests/test_ember.py`; independent source review. The replay script now defaults to the full daily-gate duration.
- Parameters: existing confirmation, motion, background and count thresholds; unchanged speed estimator and demo-gate tolerance. Source candidate track SHA-256 is 54dbe435dd6a09d66fffb8a0dc92413705009dc01c1c45e4d2fc752e8a27435e. The demo export now carries its tested commit into provenance, and the saved-report recorder verifies every supplied phone-source hash.
- Results:
  - The trace found an unseen phone taking a newly appearing TV/background blob before that blob had a confirmed static owner. A pending background object now completes an eligible stationary confirmation atomically before unseen phones; already seen phones keep first choice. A separate background reacquisition check excludes reach gained solely from growing uncertainty.
  - Every tested cached full-rate history, legacy track field and deterministic quality/speed/ruler result remains exactly equal to the original tracker. The longer replay removes the sustained late over-count while preserving a brief residual fragment and geometric lamp-region flags rather than hiding them with the display cap.
  - Focused controls pass for current confirmation windows, exact blob consumption, paused phones and prediction-consistent bright-background returns. Independent review found no remaining code blocker. A phone that stops or reverses while hidden over bright background can still be rejected or fragmented; this bounded association prior is not universal occlusion recovery.
- Decisions: retain strict non-regression and the original gate, preserve the failed attempt and every residual, and keep the release held until committed-source checks pass.
- Next: run the complete committed-source regression, official phone suite, long uncapped replay and unchanged daily demo gate; create a demo tag only on success.

## 2026-10-15T20:34:24+08:00 Full regression found mode-switch memory growth

- Goal: verify the revised phone source before any daily demo tag.
- Commands: `TMPDIR=results/runs/tmp MPLCONFIGDIR=.venv/mpl QT_QPA_PLATFORM=offscreen bash scripts/run_from_head.sh python -m pytest -q` on 963b4c6; saved-report number recording without rerunning tests. The original log, readable normalized copy and exact reconstruction archive are preserved in the durable continuation bundle.
- Parameters: pinned Mac runtime, unchanged full test selection, original mode-switch memory limit and frozen phone source. No live-gate tolerance was relaxed.
- Results:
  - The complete run has 549 <!-- n:continuation.failed_memory_tests.passed --> passed, 1 <!-- n:continuation.failed_memory_tests.failed --> failed and 3 <!-- n:continuation.failed_memory_tests.skipped --> skipped tests. The only failure is the repeated mode-switch memory check; every tracker control passes.
  - Process RSS growth is 68.734375 MiB <!-- n:continuation.failed_memory_tests.rss_growth_mib --> against the original 40 MiB <!-- n:continuation.failed_memory_tests.rss_growth_limit_mib --> limit. This run does not pass the release regression gate.
- Decisions: preserve the failed run, keep the memory assertion unchanged and hold release while locating retained memory. A passing phone comparison cannot override a failed application check.
- Next: distinguish engine retention from test-fixture retention, repair the demonstrated cause and rerun committed-source checks before the daily demo gate.

## 2026-10-15T20:51:38+08:00 Separate mode lifetime retention from evolving fire allocations

- Goal: repair the demonstrated memory-test confound without changing the accepted measurement algorithms or hiding the failed actual-fire result.
- Commands: isolated original memory test; matched saved-fire-frame replay without modes or cameras; retained-array/weak-reference accounting; full-resolution corpus lifecycle checks and a retained-camera-payload mutation. Small diagnostic reports, raw-log reconstruction archives and their source manifests are in the continuation bundle.
- Parameters: real Player, LiveAnalyser and fire Pipeline; original resolution; original warm-up entries, measured switches, total entries and RSS limit. The bounded corpus covers one configured noise-update period, every input is observed by the ready analyser before the baseline, and RSS is sampled at completed source-read boundaries. No RSS-adaptive warm-up or production config change is used.
- Results:
  - The original assertion also fails on the exact saved fire frames without any mode switches. Reachable image storage barely changes, and scalar track history cannot explain that RSS change. Initial readiness, first map refresh and matching read-boundary probes were each insufficient on the evolving input; those failures are preserved. A native-allocation cause is not claimed.
  - The purpose-specific lifecycle fixture passes in repeated fresh processes while retaining the original RSS assertion. Explicit weak references verify released camera sources, assets, images, analysers and feeds. Deliberately retaining a closed camera payload makes the check fail, so the new release assertions are not vacuous.
  - Product code, phone histories and the speed estimator remain unchanged. The actual evolving-fire working-set bound and overnight soak remain unresolved; a lifecycle unit pass does not turn them into application memory validation.
- Decisions: accept only the bounded lifecycle-test repair, preserve all actual-fire failures and scope limits, and repeat the complete committed-source checks before tagging.
- Next: full regression, official phone suite, long uncapped replay and the unchanged daily UI gate.

## 2026-10-15T21:01:46+08:00 Clean release regression and official strict phone validation

- Goal: verify the committed release source after the lifecycle-test repair and preserve strict phone non-regression.
- Commands: `bash scripts/run_from_head.sh python -m pytest -q`; `validate --suite ember --out results/runs/ember_guard/release_4d0092c_ember_report.json`; `scripts/check_ember_stride.py --seconds 60`; saved-report recording with `scripts/record_continuation.py`. Each ran from the 4d0092c export. Complete passing and failed logs remain in the durable evidence bundle.
- Parameters: pinned Mac runtime, offscreen Qt, default measurement settings, full original gate duration, diagnostic count cap lifted and unchanged phone/source hashes. The numeric recorder only reads saved fire reports; no held-out evaluation is repeated.
- Results:
  - The complete committed-source run passes with 550 <!-- n:continuation.final_tests.passed --> passed, 0 <!-- n:continuation.final_tests.failed --> failed and 3 <!-- n:continuation.final_tests.skipped --> skipped tests. The documented lifecycle fixture is bounded unit evidence; actual evolving-fire working-set memory remains unresolved.
  - Official phone quality and speed values exactly match the prior strict report. The exact standing trailing-window median remains 3.228608% <!-- n:continuation.ember.speed_median_percent -->, and every saved full-rate history and deterministic quality/speed/ruler result remains equal to the original tracker. Timing differences are retained without treating them as a controlled performance comparison.
  - The clean long replay has 0 <!-- n:continuation.stride.2.over_three_frames --> excess-count frames over 900 <!-- n:continuation.stride.2.frames --> analysed frames at stride two. At stride three it retains 1 <!-- n:continuation.stride.3.over_three_frames --> of 600 <!-- n:continuation.stride.3.frames --> excess-count frames and 3 <!-- n:continuation.stride.3.lamp_frames --> geometric lamp-region flags. These flags are a proximity heuristic, not a direct ownership oracle. The sustained late TV/background over-count is removed.
  - The identity-switch rate remains 5.206 <!-- n:continuation.ember.id_switches_per_phone_per_min --> per phone minute and misses its goal. Actual phone and ruler recordings are missing. Those limits and hidden abrupt-stop/reversal fragmentation remain explicit.
- Decisions: retain the strict source and all residual/failure evidence. The fire method and once-only held-out results are unchanged.
- Next: finish the unchanged daily UI gate and publish a demo build only if it passes.

## 2026-10-15T21:07:18+08:00 Daily demo gate passes and remote tag is verified

- Goal: publish the tested daily demo and complete the continuation handoff.
- Commands: `TMPDIR=results/runs/tmp MPLCONFIGDIR=.venv/mpl bash scripts/tag_demo.sh 60` at 4d0092c; `git ls-remote origin 'refs/tags/wfglink-demo-20261015-4*'`; direct inspection of every gate capture and the wide-layout fixtures. Reports, original log, screenshots, remote refs and tag-object receipt are in the sealed continuation bundle.
- Parameters: original scene, count tolerance, keyboard sequence and diagnostic cap lift; committed export with explicit clean Git provenance. No gate or held-out protocol was changed.
- Results:
  - Every daily mode passes the 60 s <!-- n:continuation.demo.seconds --> gate: synthetic fire has 1802 <!-- n:continuation.demo.synthetic.frames --> analysed frames, the approved playlist 1786 <!-- n:continuation.demo.playlist.frames -->, generated phones 1792 <!-- n:continuation.demo.ember.frames --> and the keyboard sequence 1696 <!-- n:continuation.demo.keys.frames -->. Application error counts are 0 <!-- n:continuation.demo.synthetic.error_count --> <!-- n:continuation.demo.playlist.error_count --> <!-- n:continuation.demo.ember.error_count --> <!-- n:continuation.demo.keys.error_count --> in every mode.
  - Both generated-phone runs have 0 <!-- n:continuation.demo.ember.over_three_frames --> <!-- n:continuation.demo.keys.over_three_frames --> excess-count frames. The main phone run's maximum count is 3 <!-- n:continuation.demo.ember.max_ember_count -->, with the diagnostic cap still lifted. Sparse deterministic replay residuals remain separately reported.
  - Tag `wfglink-demo-20261015-4` was pushed successfully. Its remote annotated tag peels to the exact tested 4d0092c commit. The daily ledger records the actual publication outcome.
  - Generated-data and uncalibrated labels are visible. Narrow gate captures truncate long sidebar units; the wide layout fixtures remain legible. The real C5 overlay retains false fixture/reflection tracks and suspect associations, consistent with its poor labelled precision. These captures are not physical validation.
- Decisions: publish the passing daily build with failed attempts, strict non-regression evidence and every remaining limit preserved. Keep the PR a draft on the same branch, without merging Main.
- Next: run the forwardable sitting instructions and return the combined report; later physical recordings and the overnight soak remain required. No further held-out scoring is authorized by this handoff.
