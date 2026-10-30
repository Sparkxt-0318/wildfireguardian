"""Receipt-bound full-rectangle US2024 and Korean2025 assessment.

Run only after MODEL_SELECTION.json freezes all seven final checkpoints.
Per-case leases permit independent audits between complete numerical cases.
Korean reconstruction scores remain separate from NIROPS mapped-extent scores.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import pickle
import sys
import time

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "forecast"))
import numpy as np
import pandas as pd
import rasterio
import torch
from wildfire import baselines as B
from wildfire.api import load_model
from wildfire.survival import PerimeterSample, sample_forecast

spec = importlib.util.spec_from_file_location("full_cohort_pipeline", HERE.with_name("pipeline.py"))
P = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = P
spec.loader.exec_module(P)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array_sha(a):
    a = np.ascontiguousarray(a)
    return hashlib.sha256(str((a.shape, str(a.dtype))).encode() + a.tobytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def korean_samples(event, data, environment):
    """Every eligible fixed 12h window on finite original arrival cells."""
    with rasterio.open(data / "environment/regions" / event / "arrival_time_hours.tif") as source:
        arrival = source.read(1, masked=True).filled(np.nan).astype(float)
    metadata = environment.catalog[event]
    t0 = pd.Timestamp(metadata["t0_utc"])
    finite = np.isfinite(arrival)
    if not finite.any():
        return []
    samples = []
    for proposed in np.arange(np.floor(np.nanmin(arrival)), np.ceil(np.nanmax(arrival)), 12):
        cutoff = (t0 + pd.Timedelta(hours=float(proposed))).floor("h")
        if not environment.available_at(event, cutoff):
            continue
        elapsed = (cutoff - t0).total_seconds() / 3600
        initial = finite & (arrival <= elapsed)
        if not initial.any():
            continue
        samples.append(PerimeterSample(event, cutoff.isoformat(), 12., environment.at(event, cutoff), initial,
            finite & (arrival <= elapsed + 12), finite & ~initial, np.ones(arrival.shape),
            np.where(initial, elapsed - arrival, 0.), kind="kriged",
            meta=dict(t2=(cutoff + pd.Timedelta(hours=12)).isoformat(), start_hours=elapsed),
            residence_hours=environment.residence(event)))
    return samples


def identities(args):
    selection_path = REPO / "research/forecast-v2/MODEL_SELECTION.json"
    selection = json.loads(selection_path.read_text())
    if not selection.get("frozen_before_heldout_scoring") or set(selection["checkpoints"]) != set(P.VARIANTS):
        raise ValueError("Complete frozen model identities are required before assessment")
    for row in selection["checkpoints"].values():
        if sha(REPO / row["path"]) != row["sha256"]:
            raise ValueError("A frozen checkpoint changed")
    if sha(P.C651) != P.C651_SHA256:
        raise ValueError("Integration checkpoint c651 changed")
    source = {str(p.relative_to(REPO)): sha(p) for p in (REPO / "forecast/wildfire").glob("*.py")}
    source |= {str(p.relative_to(REPO)): sha(p) for p in [HERE, HERE.with_name("pipeline.py")]}
    return dict(selection_sha256=sha(selection_path), checkpoints=selection["checkpoints"],
                c651_sha256=sha(P.C651), source_sha256=source,
                logistic_sha256=sha(args.run / "baselines/logistic.pkl"),
                dilation_choice_sha256=sha(args.run / "baselines/dilation_choice.json"),
                extraction_manifest_sha256=sha(args.data / "EXTRACTION_MANIFEST.json"),
                terrain_manifest_sha256=sha(args.data / "BASELINE_TERRAIN_MANIFEST.json"),
                split_sha256=sha(REPO / "research/forecast-v2/SPLIT.json"),
                trajectories=1024, trajectory_batch_size=32, seed=0, boundary="zero",
                weather="cutoff repeated", cohort=args.cohort)


def predict_case(sample, environment, c651, models, logistic, best):
    predictions, valids, timings = {}, [], {}
    begin = time.perf_counter()
    p, valid = P.c651_monte_carlo(c651.predictor, sample, environment.names, 1024, 0)
    predictions["c651_mc"] = p
    valids.append(valid)
    timings["c651_mc"] = time.perf_counter() - begin
    for name, model in {"c651_meanfield": c651.predictor, **models}.items():
        begin = time.perf_counter()
        with torch.no_grad():
            q, v = sample_forecast(model, sample, use_burnout=name != "c651_meanfield",
                                   use_spotting=name != "c651_meanfield")
        predictions[name] = q.numpy()
        valids.append(v.numpy())
        timings[name] = time.perf_counter() - begin
    predictions["persistence"] = B.persistence(sample.initial)
    for rate in B.DILATION_HOURS:
        predictions[f"dilation_{rate}h"] = B.dilation(sample.initial, sample.hours, rate)
    predictions["dilation_best"] = predictions[f"dilation_{best}h"]
    predictions["logistic"] = P.logistic_predict(logistic, sample, environment.names,
                                                environment.terrain_gradient(sample.event_id))
    mask = sample.score_mask & np.isfinite(sample.environment).all(0) & np.logical_and.reduce(valids)
    for value in predictions.values():
        mask &= np.isfinite(value)
    return predictions, mask, timings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", choices=["us2024", "korea2025"], required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(2)
    frozen = identities(args)
    out = args.run / ("heldout" if args.cohort == "us2024" else "korean2025")
    out.mkdir(parents=True, exist_ok=True)
    frozen_path = out / "FROZEN_ASSESSMENT.json"
    if frozen_path.exists() and json.loads(frozen_path.read_text()) != frozen:
        raise ValueError("Preserve prior assessment output when source, models or inputs change")
    write(frozen_path, frozen)
    frozen_sha = sha(frozen_path)
    env = P.Environment(args.data / "environment", args.work / "env")
    events = P.SPLIT["held_out"]["us_2024" if args.cohort == "us2024" else "korean_2025"]
    c651 = load_model(P.C651, device="cpu")
    models = {v + "_seed0": P.load_structured(REPO / row["path"]) for v, row in frozen["checkpoints"].items()}
    logistic = pickle.loads((args.run / "baselines/logistic.pkl").read_bytes())
    best = json.loads((args.run / "baselines/dilation_choice.json").read_text())["best_hours_per_cell"]
    failures, all_receipts, timing_rows = [], [], []
    for event in events:
        samples = (P.perimeter_samples(event, args.data / "perimeters", env, crop=False)
                   if args.cohort == "us2024" else korean_samples(event, args.data, env))
        if not samples:
            failures.append(dict(event=event, reason="No eligible source intervals"))
        columns = {k: [] for k in ("interval", "row", "col", "y")}
        probabilities = {}
        for index, sample in enumerate(samples):
            case = dict(event=event, cutoff=sample.t1, endpoint=sample.meta["t2"], hours=sample.hours)
            cid = hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest()[:24]
            receipt_path, entries_path = out / "cases" / f"{cid}.json", out / "cases" / f"{cid}.npz"
            if receipt_path.exists():
                record = json.loads(receipt_path.read_text())
                if record["assessment_sha256"] != frozen_sha or record["case"] != case:
                    raise ValueError("Case receipt belongs to another assessment")
                if record["status"] != "SCORED" or sha(entries_path) != record["sha256"]:
                    raise ValueError("Failed, unavailable or changed case requires a new preserved assessment phase")
            else:
                if entries_path.exists():
                    raise ValueError("Unreceipted prediction file cannot be reused")
                record = dict(case=case, case_id=cid, assessment_sha256=frozen_sha,
                    initial_sha256=array_sha(sample.initial), endpoint_sha256=array_sha(sample.endpoint),
                    environmental_snapshot_sha256=array_sha(sample.environment),
                    reference_mask_sha256=array_sha(sample.score_mask), rectangle=list(sample.initial.shape),
                    reference_cells=int(sample.score_mask.sum()), weather_hour=pd.Timestamp(sample.t1).floor("h").isoformat())
                begin = time.perf_counter()
                try:
                    with Path("/tmp/wfg/HEAVY.lock").open("a+") as lock:
                        fcntl.flock(lock, fcntl.LOCK_EX)
                        predictions, mask, timings = predict_case(sample, env, c651, models, logistic, best)
                        fcntl.flock(lock, fcntl.LOCK_UN)
                    if not mask.any():
                        record.update(status="UNAVAILABLE", reason="No common supported cells")
                    else:
                        entries_path.parent.mkdir(exist_ok=True)
                        with entries_path.with_suffix(".tmp").open("wb") as stream:
                            np.savez_compressed(stream, y=sample.endpoint[mask].astype(np.int8),
                                row=np.nonzero(mask)[0], col=np.nonzero(mask)[1],
                                **{f"p_{name}": value[mask] for name, value in predictions.items()})
                        entries_path.with_suffix(".tmp").replace(entries_path)
                        record.update(status="SCORED", sha256=sha(entries_path), scored_cells=int(mask.sum()),
                                      positives=int(sample.endpoint[mask].sum()), excluded_cells=int((sample.score_mask & ~mask).sum()),
                                      scored_mask_sha256=array_sha(mask), model_seconds=timings)
                except Exception as error:
                    record.update(status="FAILED", error_type=type(error).__name__, reason=str(error))
                record.update(seconds=time.perf_counter() - begin, completed_utc=datetime.now(timezone.utc).isoformat())
                write(receipt_path, record)
            all_receipts.append(record)
            if record["status"] != "SCORED":
                failures.append(record)
                continue
            with np.load(entries_path, allow_pickle=False) as entries:
                for column in ("row", "col", "y"):
                    columns[column].append(entries[column])
                columns["interval"].append(np.full(len(entries["y"]), index))
                for name in entries.files:
                    if name.startswith("p_"):
                        probabilities.setdefault(name, []).append(entries[name])
            timing_rows.append(dict(event=event, interval=index, **record.get("model_seconds", {})))
            print(json.dumps(dict(case=case, status=record["status"], cells=record["scored_cells"])), flush=True)
        if columns["y"]:
            target = out / f"{event}.npz"
            with target.with_suffix(".tmp").open("wb") as stream:
                np.savez_compressed(stream, **{k: np.concatenate(v) for k, v in columns.items()},
                    **{k: np.concatenate(v) for k, v in probabilities.items()},
                    t1=np.array([s.t1 for s in samples]), hours=np.array([s.hours for s in samples]))
            target.with_suffix(".tmp").replace(target)
    write(out / "ASSESSMENT.json", dict(status="COMPLETE" if not failures else "HOLD", frozen_sha256=frozen_sha,
        events=events, cases=all_receipts, failed_or_unavailable=failures, host=P.host_record(), timings=timing_rows))
    if args.cohort == "us2024":
        write(args.run / "report_inputs.json", dict(perimeters=str(args.data / "perimeters"), data_root=str(args.data / "environment"),
            fitted_models=sorted(models), best_dilation_hours_per_cell=best, n_samples=1024, seed=0,
            frozen_assessment_sha256=frozen_sha, cohort="US2024 NIROPS mapped extent", data_manifest_sha256=frozen["extraction_manifest_sha256"]))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
