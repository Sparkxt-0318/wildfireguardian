"""Part-a predictions from a refit checkpoint (orchestrator-approved 2026-11-12; for Owen's independent rerun harness
and Victor's part-a development tables). IN-SAMPLE, DEVELOPMENT-ONLY: part a is the training pool of every A1 §3.1
refit, so any score computed from these files is an in-sample fit statistic, never a test result.

Unchanged repo code only, called as forecast-v2 scored cohorts:
  * pipeline.Environment(data_root, work, input_sha256=pins from --input-manifest)  (same pins as the refit)
  * pipeline.perimeter_samples(event, perimeters, env, crop=False)                  (full rectangle, as cohort R)
  * survival.sample_forecast(model, sample) with model = pipeline.load_structured(checkpoint)
The scored mask per interval is score_cohorts.predict_case's producer support restricted to this one model:
score_mask & ~initial & all-finite environment & the model's own validity.

Output per fire: <out>/<event>.npz in score_cohorts' per-fire entry format
  interval (int64, index into t1/hours), row, col (int64), y (int8), p_<name> (float32),
  t1 (cutoff ISO strings), hours (float64), plus dist_m (float32: Euclidean distance between 375 m cell centres to
  the nearest cell of the cutoff mapped union; 0 on that union).
and <out>/SCORE_PARTA_RECEIPT.json (checkpoint sha, pins sha, script/pipeline/survival shas, events, per-fire counts,
skipped intervals with reasons, host, wall time, the in-sample notice).

    python score_parta.py --checkpoint CKPT --name d4_wind_rebuilt --data-root DATA/environment --perimeters PERIM \
        --input-manifest PINS.json --events TRAIN_EVENTS.txt --work W --out OUT [--threads 2]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
SCRIPTS = REPO / "research/forecast-v2/scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO / "forecast"))
NOTICE = "IN-SAMPLE, DEVELOPMENT-ONLY: part a is the refit training pool; scores from these files are fit statistics."
CELL_M = 375.0


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--perimeters", type=Path, required=True)
    ap.add_argument("--input-manifest", type=Path, required=True)
    ap.add_argument("--events", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    import torch
    from scipy.ndimage import distance_transform_edt
    torch.set_num_threads(a.threads)
    spec = importlib.util.spec_from_file_location("full_cohort_pipeline", SCRIPTS / "pipeline.py")
    P = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = P
    spec.loader.exec_module(P)
    from wildfire.survival import sample_forecast

    pins = json.loads(a.input_manifest.read_text())
    env = P.Environment(a.data_root, a.work / "env", input_sha256=pins)
    model = P.load_structured(a.checkpoint)
    events = [e.strip() for e in a.events.read_text().splitlines() if e.strip()]
    a.out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    per_fire, skipped = {}, []
    for event in events:
        if not (a.perimeters / event / "states.npz").exists():
            skipped.append(dict(event=event, reason="no perimeter states"))
            continue
        samples = P.perimeter_samples(event, a.perimeters, env, crop=False)
        cols = {k: [] for k in ("interval", "row", "col", "y", "p", "dist_m")}
        t1, hours = [], []
        for k, sample in enumerate(samples):
            with torch.no_grad():
                q, valid = sample_forecast(model, sample)
            q, valid = q.numpy(), valid.numpy()
            mask = sample.score_mask & ~sample.initial & np.isfinite(sample.environment).all(0) & valid
            if not mask.any():
                skipped.append(dict(event=event, t1=sample.t1, reason="empty supported population"))
                continue
            dist = (distance_transform_edt(~sample.initial) * CELL_M if sample.initial.any()
                    else np.full(sample.initial.shape, np.inf))
            r, c = np.nonzero(mask)
            idx = len(t1)
            t1.append(sample.t1)
            hours.append(float(sample.hours))
            cols["interval"].append(np.full(len(r), idx, np.int64))
            cols["row"].append(r.astype(np.int64))
            cols["col"].append(c.astype(np.int64))
            cols["y"].append(sample.endpoint[mask].astype(np.int8))
            cols["p"].append(q[mask].astype(np.float32))
            cols["dist_m"].append(dist[mask].astype(np.float32))
        if not t1:
            skipped.append(dict(event=event, reason="no scored interval"))
            continue
        arrays = {k: np.concatenate(v) for k, v in cols.items()}
        np.savez_compressed(a.out / f"{event}.npz", interval=arrays["interval"], row=arrays["row"], col=arrays["col"],
                            y=arrays["y"], **{f"p_{a.name}": arrays["p"]}, dist_m=arrays["dist_m"],
                            t1=np.array(t1), hours=np.array(hours))
        per_fire[event] = dict(intervals=len(t1), cells=int(len(arrays["y"])), positives=int(arrays["y"].sum()),
                               sha256=sha(a.out / f"{event}.npz"))
    receipt = dict(notice=NOTICE, name=a.name, checkpoint=str(a.checkpoint), checkpoint_sha256=sha(a.checkpoint),
                   input_manifest_sha256=sha(a.input_manifest), events_sha256=sha(a.events), n_events=len(events),
                   script_sha256=sha(__file__), pipeline_sha256=sha(SCRIPTS / "pipeline.py"),
                   survival_sha256=sha(REPO / "forecast/wildfire/survival.py"),
                   perimeter_manifest_sha256=sha(a.perimeters / "PERIMETER_MANIFEST.json"),
                   per_fire=per_fire, skipped=skipped, wall_seconds=time.perf_counter() - started,
                   host=dict(python=platform.python_version(), platform=platform.platform(), torch=torch.__version__,
                             numpy=np.__version__, threads=a.threads))
    (a.out / "SCORE_PARTA_RECEIPT.json").write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps(dict(fires=len(per_fire), skipped=len(skipped), cells=sum(v["cells"] for v in per_fire.values()),
                          wall_s=round(receipt["wall_seconds"], 1))))


if __name__ == "__main__":
    main()
