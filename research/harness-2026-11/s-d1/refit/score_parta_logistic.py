"""Part-a producer for logistic_rebuilt (IN-SAMPLE, DEVELOPMENT-ONLY table). The fitted model is the pickle written
by `pipeline.py baselines` in the refit run (logistic.pkl, sha recorded); predictions use pipeline.logistic_predict with
env.terrain_gradient(event), exactly as score_cohorts.predict_case. Mask per interval: score_mask & ~initial &
all-finite environment & finite logistic features (logistic support, as score_cohorts.deterministic_support).
Output column p_logistic_rebuilt; same layout and receipt as score_parta.py; merge with merge_parta.py.

    python score_parta_logistic.py --logistic RUN/baselines/logistic.pkl --data-root ... --perimeters ... \
        --input-manifest PINS.json --events EVENTS.txt --work W --out OUT
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
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    for k in ("logistic", "data-root", "perimeters", "input-manifest", "events", "work", "out"):
        ap.add_argument(f"--{k}", type=Path, required=True)
    a = ap.parse_args()
    from scipy.ndimage import distance_transform_edt
    spec = importlib.util.spec_from_file_location("full_cohort_pipeline", SCRIPTS / "pipeline.py")
    P = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = P
    spec.loader.exec_module(P)
    import pickle
    logistic = pickle.loads(a.logistic.read_bytes())
    env = P.Environment(a.data_root, a.work / "env", input_sha256=json.loads(a.input_manifest.read_text()))
    events = [e.strip() for e in a.events.read_text().splitlines() if e.strip()]
    a.out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    per_fire, skipped = {}, []
    for event in events:
        if not (a.perimeters / event / "states.npz").exists():
            skipped.append(dict(event=event, reason="no perimeter states"))
            continue
        cols = {k: [] for k in ("interval", "row", "col", "y", "logistic", "dist_m")}
        grad = env.terrain_gradient(event)
        t1, hours = [], []
        for sample in P.perimeter_samples(event, a.perimeters, env, crop=False):
            q = P.logistic_predict(logistic, sample, env.names, grad)
            feats = P.logistic_features(sample, env.names, grad)
            support = np.isfinite(feats).all(1).reshape(sample.initial.shape)
            mask = sample.score_mask & ~sample.initial & np.isfinite(sample.environment).all(0) & support
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
            cols["row"].append(r.astype(np.int64)); cols["col"].append(c.astype(np.int64))
            cols["y"].append(sample.endpoint[mask].astype(np.int8))
            cols["logistic"].append(q[mask].astype(np.float32))
            cols["dist_m"].append(dist[mask].astype(np.float32))
        if not t1:
            skipped.append(dict(event=event, reason="no scored interval"))
            continue
        arr = {k: np.concatenate(v) for k, v in cols.items()}
        np.savez_compressed(a.out / f"{event}.npz", interval=arr["interval"], row=arr["row"], col=arr["col"], y=arr["y"],
                            p_logistic_rebuilt=arr["logistic"], dist_m=arr["dist_m"],
                            t1=np.array(t1), hours=np.array(hours))
        per_fire[event] = dict(intervals=len(t1), cells=int(len(arr["y"])), sha256=sha(a.out / f"{event}.npz"))
    receipt = dict(notice=NOTICE, names=["logistic_rebuilt"], logistic_sha256=sha(a.logistic),
                   input_manifest_sha256=sha(a.input_manifest),
                   events_sha256=sha(a.events), script_sha256=sha(__file__), pipeline_sha256=sha(SCRIPTS / "pipeline.py"),
                   baselines_sha256=sha(REPO / "forecast/wildfire/baselines.py"),
                   perimeter_manifest_sha256=sha(a.perimeters / "PERIMETER_MANIFEST.json"), per_fire=per_fire,
                   skipped=skipped, wall_seconds=time.perf_counter() - t0,
                   host=dict(python=platform.python_version(), platform=platform.platform(), numpy=np.__version__))
    (a.out / "SCORE_PARTA_RECEIPT.json").write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps(dict(fires=len(per_fire), skipped=len(skipped))))


if __name__ == "__main__":
    main()
