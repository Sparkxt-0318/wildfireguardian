# wfglink

wfglink measures glowing wildfire embers in ordinary video (dashcams, CCTV, phones) and turns them into counts, speeds, a gate flux and an ember-derived wind estimate. It is part of the WildfireGuardian project for Korea Code Fair 2026 and is fully isolated from the forecast and routing code in this repository.

## Why

During a wildfire nobody measures how many embers fly, where, or how fast, and nobody measures street-level wind inside communities. Spotting carried the March 2025 Uiseong fire front up to about 51 km to the Yeongdeok coast within about 12 hours (KFS and NIFOS analysis reported by Newsis, see data/SOURCES.md). NIST's Emberometer measures embers with four synchronized cameras, but only where it is installed before a fire. A glowing ember is a tracer particle, so any camera that films an ember storm has recorded ember activity. wfglink extracts it.

## What it produces

- Ember detections per frame, tracks and per-ember velocity (from tracking and from motion-blur streaks).
- Count rate, Cumulative Particle Count (gate) and Particle Number Flux (projected, 2D) through a virtual gate. The names mirror NIST, but NIST's quantities are per square meter through a 3D surface, so the two are analogous, not comparable.
- An ember-derived air velocity field, always labeled as an estimate because embers lag the air and fall.
- Pixels by default; meters only at a stated distance range.
- Parquet tables, a summary JSON per clip, an overlay video, and a live fullscreen dashboard for the booth, which plays approved clips in real time and analyses them as they play.

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
- `python -m wfglink live`: the booth screen on the approved clips of `booth/playlist.yaml`, played in real time and analysed as they play, in a loop. `--clip PATH` plays one video file or one clip settings file `data/clips/<id>.yaml`. `--screen auto|external|primary|NAME` (auto, the default: the external monitor when connected, else the MacBook), `--lang ko|en`, `--limits-screen NAME`.
- `./booth/booth.sh` (or double-click `booth/booth.command`): the booth for a whole day. It runs `live` with the playlist under a supervisor, keeps the Mac awake, restarts the app after a crash or hang, and logs to `logs/booth.log`. Keys: L language, T tracks, F field, G gate, Space pause, I limits card, Esc then Esc again to quit (booth/BOOTH_RUNBOOK.md).
- `python -m wfglink validate --suite led`: the dashcam LED turntable test on `data/raw/led_33rpm.*`, `led_45rpm.*`, `led_ruler.*`, `room_test.*` and `night_drive.*` with `data/raw/led_notes.yaml` (from `data/led_notes_template.yaml`); writes `results/validation/led_report.json`. `--suite core|mismatch|coverage` runs the synthetic suites (mismatch and coverage are held out and run once, with `--final`).
- `python scripts/mac_soak.py --hours 8`: the overnight soak of the booth screen with the playlist; logs fps and memory and prints a PASS or FAIL report at the end.
- `python -m wfglink process CLIP`: file mode, with tables, a summary JSON and an overlay video for one clip (a video file or `data/clips/<id>.yaml`).
- `python -m wfglink plausibility RUN_DIR --clip data/clips/<id>.yaml`: real-clip plausibility checks on a `process` run (plausibility.json, statuses also in summary.json); `label-tiles` and `label-score` make blind label tiles and score a run against them (docs/METHODS.md section 11).
- `python scripts/fetch_clips.py`: download the approved clips into `data/raw/` (resumes; skips what is there).
- `python -m wfglink demo-gate`: the headless check behind the demo builds (`scripts/tag_demo.sh`, DEMO_BUILDS.md).
- `booth/placards/`: print-ready A5 placards in Korean and English, "This is the sensor" for the dashcam stand and the limits card.

The two hands-on sittings on the Mac: docs/SITTING1.md (setup, dashcam, LED rig, recordings, validate, send files) and docs/SITTING2.md (update, booth, overnight soak, rehearsal).

## Folder layout

- `src/wfglink/`: the package (input and playback, detection, tracking, measurement, pipeline, rendering, UI, synthetic generator, validation, doctor, soak).
- `configs/`: `default.yaml` (every threshold, commented) and the suite configs. `configs/booth_local.yaml` (not tracked) holds machine-specific switches.
- `booth/`: `booth.sh`, `booth.command`, `playlist.yaml`, `placards/` and BOOTH_RUNBOOK.md.
- `scripts/`: `setup_mac.sh`, `mac_soak.py`, `fetch_clips.py`, `run_suite.py`, `check_docs.py`, `check_staged.py`, `tag_demo.sh`.
- `data/`: SOURCES.md, clips.csv, clips_manifest.yaml, `clips/<id>.yaml`, `led_notes_template.yaml`; `raw/` (videos and the LED notes, never committed).
- `results/`: NUMBERS.json, `validation/`, `figures/`; `runs/` (not tracked).
- `docs/`: PROMPT.md, METHODS.md, LIMITS.md, SITTING1.md, SITTING2.md.
- `logs/`: the booth log and heartbeat (not tracked).

## Current status

2026-10-15: detector, tracker, velocity, exposure estimate, gate counts, the ember field, the booth screen with its supervisor and the synthetic generator are built and tested. The setup change of 2026-10-15 drops the live camera: the booth now plays approved clips in real time and analyses them as they play, and the LED test is filmed with the dashcam. The playback booth, the dashcam LED suite, the Mac setup, doctor and soak scripts and the placards replace the camera chain, booth-prep, the camera-in-the-loop simulator and the old sitting kits.

Core suite (synthetic, used for tuning; held-out headline numbers come later from the mismatch suite):

- Track speed is accurate wherever embers are tracked: median relative error 0.020 <!-- n:core.base.track_speed_med_rel_err --> and direction error 1.01 <!-- n:core.base.direction_med_err_deg --> degrees in the base case.
- Detection is limited by compression: half the embers are found at an SNR of 15.2 <!-- n:core.base.snr50 -->, so base-case F1 is 0.386 <!-- n:core.base.f1 --> while bright embers are found with recall 0.855 <!-- n:core.base.recall_bright -->. The plan's F1 goal is met only for bright embers (F1 0.907 <!-- n:core.snr-30.f1 --> in the high-SNR case).
- Counts are lower bounds: in every base clip the gate count lies between the bright-ember and all-visible truths (fraction 1.0 <!-- n:core.base.gate_between_bounds -->).
- The exposure estimate declines on every core case (base value 0.0 <!-- n:core.base.exposure_ok -->) until streak lengths are measured in proportion to true length; that fix is in progress. Streak speeds are not reported until then.

Figures: results/figures/core_completeness.png and core_case_errors.png.

## Records

- PLAN.md: the approved plan.
- LOG.md: append-only work log (Asia/Shanghai time).
- DEMO_BUILDS.md: the demo builds that passed the demo gate.
- results/NUMBERS.json: every quoted number with the script, config and git commit that produced it.
- data/SOURCES.md and data/clips.csv: provenance of every paper, dataset, clip and parameter.
- docs/PROMPT.md: the original prompt and later decisions, verbatim.
