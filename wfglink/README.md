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
- `python -m wfglink plausibility RUN_DIR --clip data/clips/<id>.yaml`: real-clip plausibility checks on a `process` run (plausibility.json, statuses also in summary.json); `label-tiles` and `label-score` make blind label tiles and score a run against them (docs/METHODS.md section 11).

## Current status

2026-10-15: capture chain with fallbacks, detector, tracker, velocity, exposure estimate, gate counts, the ember field, the booth app with its supervisor, booth-prep, the sitting 1 and sitting 2 kits, the camera-in-the-loop simulator and the synthetic generator are built and tested.

Core suite (synthetic, used for tuning; held-out headline numbers come later from the mismatch suite):

- Track speed is accurate wherever embers are tracked: median relative error 0.020 <!-- n:core.base.track_speed_med_rel_err --> and direction error 1.01 <!-- n:core.base.direction_med_err_deg --> degrees in the base case.
- Detection is limited by compression: half the embers are found at an SNR of 15.2 <!-- n:core.base.snr50 -->, so base-case F1 is 0.386 <!-- n:core.base.f1 --> while bright embers are found with recall 0.855 <!-- n:core.base.recall_bright -->. The plan's F1 goal is met only for bright embers (F1 0.907 <!-- n:core.snr-30.f1 --> in the high-SNR case).
- Counts are lower bounds: in every base clip the gate count lies between the bright-ember and all-visible truths (fraction 1.0 <!-- n:core.base.gate_between_bounds -->).
- The exposure estimate declines on every core case (base value 0.0 <!-- n:core.base.exposure_ok -->) until streak lengths are measured in proportion to true length; that fix is in progress. Streak speeds are not reported until then.

Figures: results/figures/core_completeness.png and core_case_errors.png.

## Records

- PLAN.md: the approved plan.
- LOG.md: append-only work log (Asia/Shanghai time).
- results/NUMBERS.json: every quoted number with the script, config and git commit that produced it.
- data/SOURCES.md and data/clips.csv: provenance of every paper, dataset, clip and parameter.
- docs/PROMPT.md: the original prompt and later decisions, verbatim.
