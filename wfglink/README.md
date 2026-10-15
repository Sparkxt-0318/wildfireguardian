# wfglink

wfglink measures glowing wildfire embers in ordinary video (dashcams, CCTV, phones) and turns them into counts, speeds, a gate flux and an ember-derived wind estimate. It is part of the WildfireGuardian project for Korea Code Fair 2026 and is fully isolated from the forecast and routing code in this repository.

## Why

During a wildfire nobody measures how many embers fly, where, or how fast, and nobody measures street-level wind inside communities. Spotting carried the March 2025 Uiseong fire front up to about 51 km to the Yeongdeok coast within about 12 hours (KFS and NIFOS analysis reported by Newsis, see data/SOURCES.md). NIST's Emberometer measures embers with four synchronized cameras, but only where it is installed before a fire. A glowing ember is a tracer particle, so any camera that films an ember storm has recorded ember activity. wfglink extracts it.

## What it produces

- Ember detections per frame, tracks and per-ember velocity (from tracking and from motion-blur streaks).
- Count rate, Cumulative Particle Count (gate) and Particle Number Flux (projected, 2D) through a virtual gate. The names mirror NIST, but NIST's quantities are per square meter through a 3D surface, so the two are analogous, not comparable.
- An ember-derived air velocity field, always labeled as an estimate because embers lag the air and fall.
- Pixels by default; meters only at a stated distance range.
- Parquet tables, a summary JSON per clip, an overlay video, and a live fullscreen booth screen with two modes:
  - Fire mode plays approved wildfire clips in real time and analyses them as they play. Key A fades between the raw clip and the full overlay (ember trails, wind arrows, counters); it acts on the fire footage only.
  - "Become an ember" (key M) is live: visitors hold up their phones showing a glowing ember page (`booth/ember/index.html`) over a floor mark 2.0 m from the MacBook's camera or a USB webcam. wfglink tracks up to three phones at once (more are ignored, with a small "max 3" note under the count), each with a trail, an ID and a speed in m/s measured at 2.0 m, and draws the wind arrows from all of them. The header reads "당신이 불티입니다 / You are an ember" in both languages; with the page's address set (`booth.ember_page_url`), a QR code of it shows below the picture.

## How to run

On the Mac, from a worktree of the branch (docs/SITTING1.md has every step):

```
git fetch origin claude/practical-rubin-5vu12u
git worktree add ~/wfglink-run origin/claude/practical-rubin-5vu12u
cd ~/wfglink-run/wfglink
./scripts/setup_mac.sh            # .venv with python.org Python 3.12, everything installed, data/raw created; safe to repeat
                                  # it also downloads the two booth clips and, on macOS, asks for camera permission (click Allow)
source .venv/bin/activate
python -m wfglink doctor          # one line per check, each ending in OK or FAIL (a FAIL with its fix hint on the same line)
```

Elsewhere (Linux, development): `python3.12 -m venv .venv`, then `.venv/bin/python -m pip install -r requirements.txt` and `.venv/bin/python -m pip install -e . --no-deps`.

`doctor` prints eight lines: the four the build manual names (python, packages, fonts, screens), then video, camera, data and clips; its exit code is 0 only when all eight are OK, and so is setup's. Offline, the clips line FAILs until the clips are downloaded.

Main commands (run from `wfglink/` with the environment on):

- `python -m wfglink live --synthetic`: the full booth screen on generated video.
- `python -m wfglink live`: the booth screen. It starts in fire mode on the approved clips of `booth/playlist.yaml`, played in real time and analysed as they play, in a loop; M switches to ember mode (the camera) and back. `--ember` starts in ember mode; `--fake-camera FILE` plays a recording as if it came from the camera, and with `--synthetic` ember mode plays generated phones. Without a camera or its permission, ember mode shows a message in both languages saying what is wrong and what to do (no camera found, camera access off, waiting for permission, could not start); M still returns to the fire footage, and the picture comes back by itself when the camera does. `--clip PATH` plays one video file or one clip settings file `data/clips/<id>.yaml`. `--screen auto|external|primary|NAME` (auto, the default: the external monitor when connected, else the MacBook), `--lang ko|en`, `--limits-screen NAME`.
- `./booth/booth.sh` (or double-click `booth/booth.command`): the booth for a whole day. It runs `live` under a supervisor, starting in fire mode with the playlist, keeps the Mac awake, restarts the app after a crash or hang, and logs to `logs/booth.log`. Keys: L language, T tracks, F field, G gate, Space pause, I limits card, A raw or analysed fire footage (fire mode only), M fire or ember mode, Esc then Esc again to quit (booth/BOOTH_RUNBOOK.md).
- `python -m wfglink cameras`: lists the cameras and the one the config picks (`camera.name`: auto picks a USB UVC webcam when one is connected, else the MacBook's camera; Continuity Camera and Desk View are never used; a dashcam in its USB "PC camera" (UVC) mode is a USB camera like any webcam, see the runbook's dashcam section, and `camera.mask` blanks a burned-in time or logo). `--request` asks for camera permission (the macOS dialog) and prints the answer; `--open 5` opens the camera for 5 s and prints the backend, size and frame rate it delivers.
- `python -m wfglink calibrate`: the one-command calibration for ember mode. Hold the printed A4 target (`booth/ember/calibration_target_A4.pdf`, printed at 100 percent) flat over the floor mark, where visitors hold their phones, facing the camera. It writes the focal length and a calibration record to `configs/booth_local.yaml` and prints the equivalent field of view; a result that does not become stable within 90 s is not written. `--distance-m D` is the target's distance from the camera (default `ember.distance_m`, 2.0 m, the standing spot); `--video FILE` runs it on a recording. Without a calibration, speeds use the camera's nominal field of view.
- `python -m wfglink record NAME [--seconds S] [--force]`: records the configured camera to `data/raw/NAME.mp4` (H.264) with a countdown on screen; sitting 1 records `ember_free` and `ember_ruler`. An existing recording is replaced only with `--force`; one cancelled with Esc is not kept. Nothing else in the booth records the camera.
- `python -m wfglink validate --suite ember`: the ember mode validation, on synthetic phone scenes with ground truth (`--scenes`, `--seconds`; the scenes the detector and tracker were tuned on, so not held out), then on `data/raw/ember_free.*` (`--phones N`: how many phones moved in that recording, default 1) and `data/raw/ember_ruler.*` (`--path-m 1.0`, the length of the ruler path) when present (`--raw DIR`); writes `results/validation/ember_report.json` and judges the recordings against the same goals. `--suite core|mismatch|coverage` runs the synthetic suites of the fire footage (mismatch and coverage are held out and run once, with `--final`).
- `python scripts/mac_soak.py --hours 8`: the overnight soak of the booth screen with the playlist; logs fps and memory and prints a PASS or FAIL report at the end. `python scripts/mac_soak.py --hours 2 -- --ember` soaks ember mode (2 h: memory growth is judged only from 2 h on) with the camera.
- `python -m wfglink process CLIP`: file mode, with tables, a summary JSON and an overlay video for one clip (a video file or `data/clips/<id>.yaml`).
- `python -m wfglink plausibility RUN_DIR --clip data/clips/<id>.yaml`: real-clip plausibility checks on a `process` run (plausibility.json, statuses also in summary.json); `label-tiles` and `label-score` make blind label tiles and score a run against them (docs/METHODS.md section 11).
- `python scripts/fetch_clips.py`: download the approved clips into `data/raw/` (resumes; skips a clip already in `data/raw`). The booth needs only the two playlist clips, which setup downloads.
- `python -m wfglink demo-gate`: the headless check behind the demo builds (`scripts/tag_demo.sh`, DEMO_BUILDS.md): fire mode on synthetic video and on the playlist, ember mode on generated phones (no more embers than phones), and the keys A, M and Space on the playlist.
- `booth/ember/index.html`: the phone page for ember mode, one self-contained file with no external requests. Publish it on GitHub Pages (or any static host) and put its address into `booth.ember_page_url` in `configs/booth_local.yaml`: the ember screen then shows a QR code of it, and `make_placards.py` makes its QR card.
- `booth/placards/`: print-ready A5 placards in Korean and English, "This is the sensor" for the dashcam stand, the limits card and, once the page's address is set, the ember page's QR card for the standing spot (`python scripts/make_placards.py` writes them).

For tonight with no new parts: run `./scripts/sitting1_tonight.sh` (docs/SITTING1_TONIGHT.md). It checks the approved fire clip and the built-in camera, serves the phone page over local Wi-Fi, runs A4 calibration into an isolated config, and writes a fresh pasteable report plus combined JSON. It preserves your normal booth settings. This smoke check does not validate measurement accuracy.

The two hands-on sittings on the Mac: docs/SITTING1.md (setup, camera and permission, the A4 calibration at the standing spot, the recordings, validate, send files) and docs/SITTING2.md (update, booth, overnight soak, rehearsal).

## Folder layout

- `src/wfglink/`: the package (input, playback and camera, detection, tracking, measurement, pipeline, ember mode in `ember/`, rendering, UI, synthetic generator, validation, doctor, soak).
- `configs/`: `default.yaml` (every threshold, commented) and the suite configs. `configs/booth_local.yaml` (not tracked) holds machine-specific switches and the A4 calibration.
- `booth/`: `booth.sh`, `booth.command`, `playlist.yaml`, `ember/` (the phone page `index.html` and the A4 calibration target), `placards/` and BOOTH_RUNBOOK.md.
- `scripts/`: `setup_mac.sh`, `mac_soak.py`, `fetch_clips.py`, `run_suite.py`, `make_placards.py`, `make_calibration_target.py`, `check_docs.py`, `check_staged.py`, `tag_demo.sh`.
- `data/`: SOURCES.md, clips.csv, clips_manifest.yaml, `clips/<id>.yaml`; `raw/` (the clips and your ember recordings, never committed).
- `results/`: NUMBERS.json, `validation/`, `figures/`; `runs/` (not tracked).
- `docs/`: PROMPT.md, METHODS.md, LIMITS.md, SITTING1.md, SITTING2.md.
- `logs/`: the booth log and heartbeat (not tracked).

## Current status

2026-10-15: both booth modes, the supervisor, calibration and recording commands are built. Tonight's smoke check and the exact manual differences are in [one forwardable block](docs/SITTING1_FORWARDABLE.txt). Actual phone recordings, camera measurement accuracy, purchased UVC hardware and the overnight booth soak remain unvalidated. The complete committed-source regression at 4d0092c has 550 <!-- n:continuation.final_tests.passed --> passed, 0 <!-- n:continuation.final_tests.failed --> failed and 3 <!-- n:continuation.final_tests.skipped --> skipped tests. The skips concern real permission, a host-specific CA fixture and the optional timing check. All unchanged daily demo-gate runs pass. [wfglink-demo-20261015-4](https://github.com/Sparkxt-0318/wildfireguardian/tree/wfglink-demo-20261015-4/wfglink) is published and verified against the tested source.

The phone repair protects learned lamp ownership after source-reported cadence gaps, lets eligible stationary background tracks complete confirmation before unseen phones, and requires bright-background reacquisition to fit the prediction's base plus speed reach. Every tested cached full-rate history, legacy track field and deterministic quality/speed/ruler result matches the original tracker exactly. The standing median trailing-window relative speed error remains 3.228608% <!-- n:continuation.ember.speed_median_percent -->. The identity-switch rate remains 5.206 <!-- n:continuation.ember.id_switches_per_phone_per_min --> per phone minute and still misses its goal. The 60 s <!-- n:continuation.stride.seconds --> replay lifts the diagnostic cap to 6 <!-- n:continuation.stride.max_tracks -->: strides one and two have 0 <!-- n:continuation.stride.1.over_three_frames --> <!-- n:continuation.stride.2.over_three_frames --> excess-count frames; stride three has 1 <!-- n:continuation.stride.3.over_three_frames --> of 600 <!-- n:continuation.stride.3.frames -->, plus 3 <!-- n:continuation.stride.3.lamp_frames --> geometric lamp-region flags. These flags are a proximity heuristic, not a direct ownership oracle. A phone that stops or reverses while hidden over bright background can still be rejected or fragmented; overlap errors remain. Processing-time changes are retained separately from deterministic equality.

The mode-switch memory unit check uses controlled full-resolution fire inputs with the real player/pipeline and explicit release checks. Evolving-fire diagnostics exceed its RSS-growth budget even without mode switches, while reachable image storage barely changes. The actual application working-set bound remains unresolved; the controlled lifecycle pass is not whole-application memory validation.

File mode now detects at coarser scales on large frames. Exact comparisons against the handoff code preserve the tested small-frame and live paths, including C6; the existing core records below are retained. The merge is heuristic, and coarse centroid uncertainty is not separately calibrated. High-resolution verification F1 is 0.371 <!-- n:continuation.hires.base.f1 --> for far embers, 0.744 <!-- n:continuation.hires.kind-near.f1 --> for near embers and 0.623 <!-- n:continuation.hires.kind-mixed.f1 --> for mixed sizes. These are empirical checks, with substantial misses remaining.

C5 development evidence uses 20 <!-- n:continuation.C5.after.frames --> frames and 40 <!-- n:continuation.C5.after.tiles_scored --> tiles labelled by agents. Recall rises from 0.2273 <!-- n:continuation.C5.before.recall.value --> to 0.5455 <!-- n:continuation.C5.after.recall.value -->, and precision from 0.0633 <!-- n:continuation.C5.before.precision.value --> to 0.1250 <!-- n:continuation.C5.after.precision.value -->. False positives also rise from 148 <!-- n:continuation.C5.before.fp --> to 168 <!-- n:continuation.C5.after.fp -->. The new F1 is 0.2034 <!-- n:continuation.C5.after.f1.value -->, with a 95% <!-- n:continuation.C5.after.ci_percent --> frame-bootstrap interval 0.0558 <!-- n:continuation.C5.after.f1.lo --> to 0.3321 <!-- n:continuation.C5.after.f1.hi -->. Precision remains poor; fixtures, reflections, captions and long suspect associations are visible in real overlays. This repeatedly used development sample is not held-out or physical validation. C5 exposure stability flags; C6 timing flags repeated frames. Speed and direction plausibility are not applicable without the missing physical metadata. C10 now shows tracking only in its overlay, tables and summary; physical checks are not applicable, and same-scope determinism passes.

The frozen fire method was evaluated once on 60 <!-- n:continuation.mismatch.clips --> mismatch clips and 200 <!-- n:continuation.coverage.clips --> coverage clips, with 0 <!-- n:continuation.mismatch.errors --> and 0 <!-- n:continuation.coverage.errors --> clip errors, respectively. Source and input custody, complete per-clip results and receipts are saved in `results/validation/continuation_20261015/`; [the evidence guide](results/validation/continuation_20261015/RELEASE_README.txt) separates every source and validation scope. No held-out result was used to tune the method.

| Held-out mismatch case | Detection F1 | Recall | Median track-speed relative error |
|---|---|---|---|
| Base | 0.3867 <!-- n:mismatch.base.f1 --> | 0.2505 <!-- n:mismatch.base.recall --> | 0.0196 <!-- n:mismatch.base.track_speed_med_rel_err --> |
| Phone processing | 0.1331 <!-- n:mismatch.conditions-phone_processing.f1 --> | 0.0741 <!-- n:mismatch.conditions-phone_processing.recall --> | 0.0869 <!-- n:mismatch.conditions-phone_processing.track_speed_med_rel_err --> |
| Smoky haze | 0.0793 <!-- n:mismatch.conditions-smoky_haze.f1 --> | 0.0414 <!-- n:mismatch.conditions-smoky_haze.recall --> | 0.0258 <!-- n:mismatch.conditions-smoky_haze.track_speed_med_rel_err --> |

Detection misses its overall goal, and speed error is conditional on successful tracking. The mismatch base exposure-success fraction is 0.0 <!-- n:mismatch.base.exposure_ok -->; usable streak speeds remain unavailable. Its count-interval coverage fraction is also 0.0 <!-- n:mismatch.base.cpc_gross_in_ci -->. The separate bright-ember coverage suite covers truth in 200 <!-- n:continuation.coverage.k --> of 200 <!-- n:continuation.coverage.n --> independent clips, fraction 1.0 <!-- n:continuation.coverage.fraction --> with exact 95% <!-- n:continuation.coverage.ci_percent --> Clopper-Pearson interval 0.981725 <!-- n:continuation.coverage.lo --> to 1.0 <!-- n:continuation.coverage.hi -->. This meets its predeclared point-coverage goal of 0.90 <!-- n:continuation.coverage.goal --> for that controlled population; it does not establish interval calibration under incomplete detection or on real footage.

Core suite (synthetic development/tuning material): base track-speed relative error 0.020 <!-- n:core.base.track_speed_med_rel_err -->, direction error 1.03 <!-- n:core.base.direction_med_err_deg --> degrees, detection F1 0.385 <!-- n:core.base.f1 --> and bright-ember recall 0.855 <!-- n:core.base.recall_bright -->. The exposure estimate declines throughout the core suite (base success fraction 0.0 <!-- n:core.base.exposure_ok -->). Figures remain in `results/figures/`.

## Records

- PLAN.md: the approved plan.
- LOG.md: append-only work log (Asia/Shanghai time).
- DEMO_BUILDS.md: the demo builds that passed the demo gate.
- results/NUMBERS.json: every quoted number with the script, config and git commit that produced it.
- data/SOURCES.md and data/clips.csv: provenance of every paper, dataset, clip and parameter.
- docs/PROMPT.md: the original prompt and later decisions, verbatim.
