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
