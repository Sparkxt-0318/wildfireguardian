# wfglink

wfglink measures glowing wildfire embers in ordinary video (dashcams, CCTV, phones) and turns them into counts, speeds, a gate flux and an ember-derived wind estimate. It is part of the WildfireGuardian project for Korea Code Fair 2026 and is fully isolated from the forecast and routing code in this repository.

## Why

During a wildfire nobody measures how many embers fly, where, or how fast, and nobody measures street-level wind inside communities. Spotting carried the March 2025 Uiseong fire front up to about 51 km to the Yeongdeok coast within about 12 hours (KFS and NIFOS analysis reported by Newsis, see data/SOURCES.md). NIST's Emberometer measures embers with four synchronized cameras, but only where it is installed before a fire. A glowing ember is a tracer particle, so any camera that films an ember storm has recorded ember activity. wfglink extracts it.

## What it produces

- Ember detections per frame, tracks and per-ember velocity (from tracking and from motion-blur streaks).
- Count rate, Cumulative Particle Count (gate) and Particle Number Flux (projected, 2D) through a virtual gate. The names mirror NIST, but NIST's quantities are per square meter through a 3D surface, so the two are analogous, not comparable.
- An ember-derived air velocity field, always labeled as an estimate because embers lag the air and fall.
- Pixels by default; meters only at a stated distance range.
- Parquet tables, a summary JSON per clip, an overlay video, and a live fullscreen dashboard for the booth.

## How to run

Setup (Python 3.12; on the Mac, `scripts/sitting1.sh` does all of this):

```
python3.12 -m venv wfglink/.venv
source wfglink/.venv/bin/activate
python -m pip install -r wfglink/requirements.txt
python -m pip install -e wfglink --no-deps
python -m wfglink doctor
```

Main commands (run from `wfglink/`):

- `bash booth/booth.sh`: the booth for a whole day (fullscreen on the external monitor, camera chain iPhone, webcam, labelled replay, synthetic; restarts itself after a crash or hang; Esc twice quits). Keys: L language, I limits card, T tracks, F field, G gate.
- `python -m wfglink booth --source synthetic|file:PATH|camera`: one booth session without the supervisor.
- `python -m wfglink booth-prep CLIP`: prepare a clip for the booth (corner frame codes, held frames, timing sidecar).
- `python -m wfglink demo-gate`: the headless check behind the daily `wfglink-demo-YYYYMMDD` tags (`scripts/tag_demo.sh`).
- `bash scripts/sitting1.sh`: the first hands-on sitting on the Mac (docs/SITTING1.md).
- `.venv/bin/python scripts/run_suite.py core|mismatch`: generate and evaluate a synthetic validation suite.

## Current status

2026-10-15: capture chain with fallbacks, detector, tracker, velocity, exposure estimate, gate counts, the booth app with its supervisor, booth-prep, the sitting 1 kit and the synthetic generator are built and tested. Validation numbers are being produced on the synthetic core suite; none are quoted yet.

## Records

- PLAN.md: the approved plan.
- LOG.md: append-only work log (Asia/Shanghai time).
- results/NUMBERS.json: every quoted number with the script, config and git commit that produced it.
- data/SOURCES.md and data/clips.csv: provenance of every paper, dataset, clip and parameter.
- docs/PROMPT.md: the original prompt and later decisions, verbatim.
