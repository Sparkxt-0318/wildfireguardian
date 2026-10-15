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
  - Fire mode plays approved wildfire clips in real time and analyses them as they play. Key A fades between the raw clip and the full overlay (ember trails, wind arrows, counters).
  - "Become an ember" (key M) is live: visitors hold up their phones showing a glowing ember page (`booth/ember/index.html`) at a standing spot 2.0 m from the MacBook's camera or a USB webcam. wfglink tracks up to six phones, each with a trail, an ID and a speed in m/s measured at 2.0 m, and draws the wind arrows from all of them.

## How to run

On the Mac, from a worktree of the branch (docs/SITTING1.md has every step):

```
git fetch origin claude/practical-rubin-5vu12u
git worktree add ~/wfglink-run origin/claude/practical-rubin-5vu12u
cd ~/wfglink-run/wfglink
./scripts/setup_mac.sh            # .venv with python.org Python 3.12, everything installed, data/raw created; safe to repeat
source .venv/bin/activate
python -m wfglink doctor          # one line per check (python, packages, fonts, screens), each OK or FAIL with a fix hint
```

Elsewhere (Linux, development): `python3.12 -m venv .venv`, then `.venv/bin/python -m pip install -r requirements.txt` and `.venv/bin/python -m pip install -e . --no-deps`.

Main commands (run from `wfglink/` with the environment on):

- `python -m wfglink live --synthetic`: the full booth screen on generated video.
- `python -m wfglink live`: the booth screen. It starts in fire mode on the approved clips of `booth/playlist.yaml`, played in real time and analysed as they play, in a loop; M switches to ember mode (the camera) and back. `--ember` starts in ember mode; `--fake-camera FILE` plays a recording as if it came from the camera (without a camera, ember mode shows generated phones). `--clip PATH` plays one video file or one clip settings file `data/clips/<id>.yaml`. `--screen auto|external|primary|NAME` (auto, the default: the external monitor when connected, else the MacBook), `--lang ko|en`, `--limits-screen NAME`.
- `./booth/booth.sh` (or double-click `booth/booth.command`): the booth for a whole day. It runs `live` under a supervisor, starting in fire mode with the playlist, keeps the Mac awake, restarts the app after a crash or hang, and logs to `logs/booth.log`. Keys: L language, T tracks, F field, G gate, Space pause, I limits card, A raw or analysed fire footage, M fire or ember mode, Esc then Esc again to quit (booth/BOOTH_RUNBOOK.md).
- `python -m wfglink cameras`: lists the cameras and the one the config picks (`camera.name`: auto picks a USB UVC webcam when one is connected, else the MacBook's camera; Continuity Camera and Desk View are never used). `--request` asks for camera permission (the macOS dialog) and prints the answer.
- `python -m wfglink calibrate`: the one-command calibration for ember mode. Hold the printed A4 target (`booth/ember/calibration_target_A4.pdf`, printed at 100 percent) flat at the standing spot, facing the camera. It writes the focal length and a calibration record to `configs/booth_local.yaml` and prints the equivalent field of view. `--distance-m D` is the target's distance from the camera (default `ember.distance_m`, 2.0 m, the standing spot); `--video FILE` runs it on a recording. Without a calibration, speeds use the camera's nominal field of view.
- `python -m wfglink record NAME [--seconds S]`: records the configured camera to `data/raw/NAME.mp4` (H.264) with a countdown on screen; sitting 1 records `ember_free` and `ember_ruler`. Nothing else in the booth records the camera.
- `python -m wfglink validate --suite ember`: the ember mode validation, on synthetic phone scenes with ground truth (`--phones N`), then on `data/raw/ember_free.*` and `data/raw/ember_ruler.*` when present (`--raw DIR`; `--path-m 1.0`, the length of the ruler path); writes `results/validation/ember_report.json`. `--suite core|mismatch|coverage` runs the synthetic suites of the fire footage (mismatch and coverage are held out and run once, with `--final`).
- `python scripts/mac_soak.py --hours 8`: the overnight soak of the booth screen with the playlist; logs fps and memory and prints a PASS or FAIL report at the end.
- `python -m wfglink process CLIP`: file mode, with tables, a summary JSON and an overlay video for one clip (a video file or `data/clips/<id>.yaml`).
- `python -m wfglink plausibility RUN_DIR --clip data/clips/<id>.yaml`: real-clip plausibility checks on a `process` run (plausibility.json, statuses also in summary.json); `label-tiles` and `label-score` make blind label tiles and score a run against them (docs/METHODS.md section 11).
- `python scripts/fetch_clips.py`: download the approved clips into `data/raw/` (resumes; skips what is there).
- `python -m wfglink demo-gate`: the headless check behind the demo builds (`scripts/tag_demo.sh`, DEMO_BUILDS.md): fire mode on synthetic video and on the playlist, and ember mode on generated phones.
- `booth/ember/index.html`: the phone page for ember mode, one self-contained file with no external requests. Publish it on GitHub Pages (or any static host) and show visitors its address at the standing spot.
- `booth/placards/`: print-ready A5 placards in Korean and English, "This is the sensor" for the dashcam stand and the limits card (`python scripts/make_placards.py` writes them).

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

2026-10-15: detector, tracker, velocity, exposure estimate, gate counts, the ember field, the booth screen with its supervisor and the synthetic generator are built and tested. The setup change of 2026-10-15 dropped the live camera of the first plan: the booth plays approved clips in real time and analyses them as they play, with the Mac setup, doctor and soak scripts and the placards. The booth change of 2026-10-15 drops the LED turntable test and adds the raw or analysed toggle (key A) and the "Become an ember" live mode (key M): a camera chosen by name, the phone page, the A4 calibration, and validation on synthetic phones and your recordings (PLAN.md section 4.4 and section 7). Real compressed video of bright scenes no longer floods the detector (the mirror test, docs/METHODS.md section 2), and file mode measures streak length with an edge-profile fit.

Core suite (synthetic, used for tuning; held-out headline numbers come later from the mismatch suite):

- Track speed is accurate wherever embers are tracked: median relative error 0.020 <!-- n:core.base.track_speed_med_rel_err --> and direction error 1.03 <!-- n:core.base.direction_med_err_deg --> degrees in the base case.
- Detection is limited by compression: half the embers are found at an SNR of 15.2 <!-- n:core.base.snr50 -->, so base-case F1 is 0.385 <!-- n:core.base.f1 --> while bright embers are found with recall 0.855 <!-- n:core.base.recall_bright -->. The plan's F1 goal is met only for bright embers (F1 0.907 <!-- n:core.snr-30.f1 --> in the high-SNR case).
- Counts are lower bounds: in every base clip the gate count lies between the bright-ember and all-visible truths (fraction 1.0 <!-- n:core.base.gate_between_bounds -->).
- The exposure estimate still declines on every core case (base value 0.0 <!-- n:core.base.exposure_ok -->): the new length fit recovers the faint ends of long streaks but does not make lengths proportional to true length. Streak speeds are not reported.

Figures: results/figures/core_completeness.png and core_case_errors.png.

## Records

- PLAN.md: the approved plan.
- LOG.md: append-only work log (Asia/Shanghai time).
- DEMO_BUILDS.md: the demo builds that passed the demo gate.
- results/NUMBERS.json: every quoted number with the script, config and git commit that produced it.
- data/SOURCES.md and data/clips.csv: provenance of every paper, dataset, clip and parameter.
- docs/PROMPT.md: the original prompt and later decisions, verbatim.
