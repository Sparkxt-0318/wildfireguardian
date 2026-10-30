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
sys.path.insert(0, str(HERE.parent))
import audit_fit_coverage as F
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
VARIANT_SET = {"base", "d4", "d4_wind", "ellipse", "burnout", "burnout_spotting", "mixed_base"}
EXPECTED_MODELS = {"c651_mc", "c651_meanfield", "persistence", "logistic", "dilation_best",
                   *(f"dilation_{k}h" for k in (1, 2, 4, 8)), *(v + "_seed0" for v in VARIANT_SET)}


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
    if not selection.get("frozen_before_heldout_scoring") or set(selection["checkpoints"]) != VARIANT_SET:
        raise ValueError("Complete frozen model identities are required before assessment")
    phase_evidence = F.saved_registry_admission(REPO, args.run, selection_path, selection, args.registry)
    for row in selection["checkpoints"].values():
        if sha(REPO / row["path"]) != row["sha256"]:
            raise ValueError("A frozen checkpoint changed")
    if set(selection.get("baselines", {})) != {"logistic", "logistic_parameters", "dilation_choice"}:
        raise ValueError("Exact fitted-baseline identities must be frozen with model selection")
    for name, filename in {"logistic": "logistic.pkl", "logistic_parameters": "logistic.json",
                           "dilation_choice": "dilation_choice.json"}.items():
        if sha(args.run / "baselines" / filename) != selection["baselines"][name]["sha256"]:
            raise ValueError("The baseline bytes actually executed differ from frozen model selection")
    for path, expected in selection["input_manifests_sha256"].items():
        if sha(args.data / path) != expected:
            raise ValueError("A frozen assessment input manifest changed")
    if sha(P.C651) != P.C651_SHA256 or phase_evidence["c651_sha256"] != sha(P.C651):
        raise ValueError("Integration checkpoint c651 changed")
    source = {str(p.relative_to(REPO)): sha(p) for p in (REPO / "forecast/wildfire").rglob("*")
              if p.is_file() and p.suffix in (".py", ".json")}
    source |= {str(p.relative_to(REPO)): sha(p) for p in [HERE, HERE.with_name("pipeline.py"), HERE.with_name("audit_fit_coverage.py")]}
    perimeter_manifest = args.data / "perimeters/PERIMETER_MANIFEST.json"
    geometry_path = REPO / "research/forecast-v2/GEOMETRY_AUDIT.json"
    if json.loads(geometry_path.read_text())["source_manifest_sha256"] != sha(perimeter_manifest):
        raise ValueError("Perimeter input manifest differs from the independently audited source phase")
    return dict(registry=phase_evidence["registry"], current_phase=phase_evidence["current_phase"], spotting_source_contract=phase_evidence["spotting_source_contract"],
                selection_sha256=sha(selection_path), checkpoints=selection["checkpoints"],
                c651_sha256=sha(P.C651), source_sha256=source,
                logistic_sha256=sha(args.run / "baselines/logistic.pkl"),
                dilation_choice_sha256=sha(args.run / "baselines/dilation_choice.json"),
                extraction_manifest_sha256=sha(args.data / "EXTRACTION_MANIFEST.json"),
                terrain_manifest_sha256=sha(args.data / "BASELINE_TERRAIN_MANIFEST.json"),
                perimeter_manifest_sha256=sha(perimeter_manifest), geometry_audit_sha256=sha(geometry_path),
                split_sha256=sha(REPO / "research/forecast-v2/SPLIT.json"),
                trajectories=1024, trajectory_batch_size=32, seed=0, boundary="zero",
                weather="cutoff repeated", cohort=args.cohort)


def source_identity(sample):
    age, residence = getattr(sample, "initial_age_hours", None), getattr(sample, "residence_hours", None)
    return dict(initial_sha256=array_sha(sample.initial), endpoint_sha256=array_sha(sample.endpoint),
        environmental_snapshot_sha256=array_sha(sample.environment), reference_mask_sha256=array_sha(sample.score_mask),
        initial_age_sha256=None if age is None else array_sha(age),
        residence_sha256=None if residence is None else array_sha(residence), rectangle=list(sample.initial.shape),
        reference_cells=int(sample.score_mask.sum()), weather_hour=pd.Timestamp(sample.t1).floor("h").isoformat())


def validate_source_receipt(record, sample):
    if record.get("receipt_version") != "wfg.forecast-assessment-case/2":
        raise ValueError("Case receipt lacks current reference admission contract")
    for field, expected in source_identity(sample).items():
        if record.get(field) != expected:
            raise ValueError(f"Case receipt differs from current verified source: {field}")


def deterministic_support(sample, environment, c651, models, logistic):
    """Recompute current common support without replaying Monte Carlo samples."""
    mask = sample.score_mask & ~sample.initial & np.isfinite(sample.environment).all(0)
    for name, model in {"c651_meanfield": c651.predictor, **models}.items():
        with torch.no_grad():
            q, valid = sample_forecast(model, sample, use_burnout=name != "c651_meanfield",
                                       use_spotting=name != "c651_meanfield")
        probability, supported = q.numpy(), valid.numpy()
        if (supported.dtype != bool or supported.shape != sample.initial.shape
                or probability.shape != sample.initial.shape or not np.isfinite(probability[supported]).all()
                or ((probability[supported] < 0) | (probability[supported] > 1)).any()):
            raise ValueError("A model numerical failure cannot become a support exclusion")
        mask &= supported
    q = P.logistic_predict(logistic, sample, environment.names, environment.terrain_gradient(sample.event_id))
    features = P.logistic_features(sample, environment.names, environment.terrain_gradient(sample.event_id))
    logistic_support = np.isfinite(features).all(1).reshape(sample.initial.shape)
    if not np.isfinite(q[logistic_support]).all() or ((q[logistic_support] < 0) | (q[logistic_support] > 1)).any():
        raise ValueError("A logistic numerical failure cannot become an input-support exclusion")
    return mask & logistic_support


def validate_entries(path, record, sample, expected_mask):
    """Bind complete ordered coordinates and all model columns to current truth."""
    validate_source_receipt(record, sample)
    if sha(path) != record["sha256"] or array_sha(expected_mask) != record.get("scored_mask_sha256"):
        raise ValueError("Stored entries or complete common-support mask changed")
    expected_row, expected_col = np.nonzero(expected_mask)
    if not len(expected_row):
        raise ValueError("An empty supported population cannot be admitted as SCORED")
    with np.load(path, allow_pickle=False) as data:
        if set(data.files) != {"y", "row", "col", *("p_" + n for n in EXPECTED_MODELS)}:
            raise ValueError("All and only the complete expected model probability columns are required")
        row, col, y = data["row"], data["col"], data["y"]
        if row.dtype.kind not in "iu" or col.dtype.kind not in "iu":
            raise ValueError("Scored coordinates must be integer arrays")
        if (row.ndim != 1 or col.ndim != 1 or not np.array_equal(row, expected_row)
                or not np.array_equal(col, expected_col) or y.shape != expected_row.shape
                or not np.array_equal(y, sample.endpoint[expected_mask])):
            raise ValueError("Exact ordered source coordinates, full mask and endpoint labels are required")
        if record.get("scored_cells") != len(y) or record.get("positives") != int(y.sum()):
            raise ValueError("Case entry counts differ from actual source-bound entries")
        for name in EXPECTED_MODELS:
            p = data["p_" + name]
            if p.shape != y.shape or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
                raise ValueError("Every registered forecast must be finite in[0,1] on the exact same entries")


def predict_case(sample, environment, c651, models, logistic, best):
    predictions, valids, timings, named_validities = {}, [], {}, {}
    begin = time.perf_counter()
    p, valid = P.c651_monte_carlo(c651.predictor, sample, environment.names, 1024, 0)
    predictions["c651_mc"] = p
    named_validities["c651_mc"] = valid
    valids.append(valid)
    timings["c651_mc"] = time.perf_counter() - begin
    for name, model in {"c651_meanfield": c651.predictor, **models}.items():
        begin = time.perf_counter()
        with torch.no_grad():
            q, v = sample_forecast(model, sample, use_burnout=name != "c651_meanfield",
                                   use_spotting=name != "c651_meanfield")
        predictions[name] = q.numpy()
        named_validities[name] = v.numpy()
        valids.append(v.numpy())
        timings[name] = time.perf_counter() - begin
    predictions["persistence"] = B.persistence(sample.initial)
    for rate in B.DILATION_HOURS:
        predictions[f"dilation_{rate}h"] = B.dilation(sample.initial, sample.hours, rate)
    predictions["dilation_best"] = predictions[f"dilation_{best}h"]
    predictions["logistic"] = P.logistic_predict(logistic, sample, environment.names,
                                                environment.terrain_gradient(sample.event_id))
    for name, supported in named_validities.items():
        value = predictions[name]
        if (supported.dtype != bool or supported.shape != sample.initial.shape or value.shape != sample.initial.shape
                or not np.isfinite(value[supported]).all() or ((value[supported] < 0) | (value[supported] > 1)).any()):
            raise ValueError(f"{name} numerical failure on declared valid support cannot trim the scored population")
    start = time.perf_counter()
    mask = deterministic_support(sample, environment, c651, models, logistic)
    timings["admission_support_replay"] = time.perf_counter() - start
    producer_support = sample.score_mask & ~sample.initial & np.isfinite(sample.environment).all(0) & np.logical_and.reduce(valids)
    # Logistic covariate availability is independently part of deterministic_support.
    producer_support &= np.isfinite(predictions["logistic"])
    if not np.array_equal(producer_support, mask):
        raise ValueError("Fresh Monte Carlo/model support differs from independently reconstructed deterministic support")
    for name, value in predictions.items():
        if value.shape != mask.shape or not np.isfinite(value[mask]).all() or ((value[mask] < 0) | (value[mask] > 1)).any():
            raise ValueError("Fresh model nonfinite output cannot become a scoring exclusion")
    return predictions, mask, timings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", choices=["us2024", "korea2025"], required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=REPO / "research/forecast-v2/BLIND_REGISTRY.json")
    args = parser.parse_args()
    torch.set_num_threads(2)
    frozen = identities(args)
    if set(frozen.get("checkpoints", {})) != VARIANT_SET:
        raise ValueError("Assessment requires all seven fixed model variants")
    out = args.run / ("heldout" if args.cohort == "us2024" else "korean2025")
    out.mkdir(parents=True, exist_ok=True)
    frozen_path = out / "FROZEN_ASSESSMENT.json"
    if frozen_path.exists() and json.loads(frozen_path.read_text()) != frozen:
        raise ValueError("Preserve prior assessment output when source, models or inputs change")
    write(frozen_path, frozen)
    frozen_sha = sha(frozen_path)
    env = P.Environment(args.data / "environment", args.work / "env")
    events = P.SPLIT["held_out"]["us_2024" if args.cohort == "us2024" else "korean_2025"]
    if {p.stem for p in out.glob("*.npz")} - set(events):
        raise ValueError("Unlisted per-fire prediction files cannot enter an assessment")
    c651 = load_model(P.C651, device="cpu")
    models = {v + "_seed0": P.load_structured(REPO / row["path"]) for v, row in frozen["checkpoints"].items()}
    logistic_bytes = (args.run / "baselines/logistic.pkl").read_bytes()
    dilation_bytes = (args.run / "baselines/dilation_choice.json").read_bytes()
    if (hashlib.sha256(logistic_bytes).hexdigest() != frozen["logistic_sha256"]
            or hashlib.sha256(dilation_bytes).hexdigest() != frozen["dilation_choice_sha256"]):
        raise ValueError("Actually loaded baseline bytes changed after identity admission")
    logistic = pickle.loads(logistic_bytes)
    best = json.loads(dilation_bytes)["best_hours_per_cell"]
    failures, all_receipts, timing_rows, output_files, seen_case_ids = [], [], [], {}, set()
    for event in events:
        metadata = env.catalog.get(event, {})
        expected_year, expected_country = (2024, "US") if args.cohort == "us2024" else (2025, "KR")
        if metadata.get("year") != expected_year or metadata.get("country") != expected_country:
            raise ValueError("Assessment fire year or evidence class differs from the frozen cohort")
        samples = (P.perimeter_samples(event, args.data / "perimeters", env, crop=False)
                   if args.cohort == "us2024" else korean_samples(event, args.data, env))
        if not samples:
            failures.append(dict(event=event, reason="No eligible source intervals"))
        columns = {k: [] for k in ("interval", "row", "col", "y")}
        probabilities = {}
        for index, sample in enumerate(samples):
            case = dict(event=event, cutoff=sample.t1, endpoint=sample.meta["t2"], hours=sample.hours)
            cid = hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest()[:24]
            if cid in seen_case_ids:
                raise ValueError("Every eligible source interval must occur exactly once")
            seen_case_ids.add(cid)
            receipt_path, entries_path = out / "cases" / f"{cid}.json", out / "cases" / f"{cid}.npz"
            if receipt_path.exists():
                record = json.loads(receipt_path.read_text())
                if record["assessment_sha256"] != frozen_sha or record["case"] != case:
                    raise ValueError("Case receipt belongs to another assessment")
                if (record["status"] not in ("SCORED", "UNAVAILABLE")
                        or record["status"] == "SCORED" and sha(entries_path) != record["sha256"]):
                    raise ValueError("Failed, unavailable or changed case requires a new preserved assessment phase")
                validate_source_receipt(record, sample)
                with Path("/tmp/wfg/HEAVY.lock").open("a+") as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    expected_mask = deterministic_support(sample, env, c651, models, logistic)
                    fcntl.flock(lock, fcntl.LOCK_UN)
                if record["status"] == "SCORED":
                    validate_entries(entries_path, record, sample, expected_mask)
                elif expected_mask.any() or entries_path.exists() or record.get("scored_cells") != 0:
                    raise ValueError("An unavailable outcome contradicts current complete source support")
            else:
                if entries_path.exists():
                    raise ValueError("Unreceipted prediction file cannot be reused")
                record = dict(case=case, case_id=cid, assessment_sha256=frozen_sha,
                    receipt_version="wfg.forecast-assessment-case/2", **source_identity(sample))
                begin = time.perf_counter()
                try:
                    with Path("/tmp/wfg/HEAVY.lock").open("a+") as lock:
                        fcntl.flock(lock, fcntl.LOCK_EX)
                        predictions, mask, timings = predict_case(sample, env, c651, models, logistic, best)
                        fcntl.flock(lock, fcntl.LOCK_UN)
                    if not mask.any():
                        record.update(status="UNAVAILABLE", reason="No common supported cells", scored_cells=0,
                                      scored_mask_sha256=array_sha(mask), model_seconds=timings)
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
                        validate_entries(entries_path, record, sample, mask)
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
            payload = {**{k: np.concatenate(v) for k, v in columns.items()},
                       **{k: np.concatenate(v) for k, v in probabilities.items()},
                       "t1": np.array([s.t1 for s in samples]), "hours": np.array([s.hours for s in samples])}
            if target.exists():
                with np.load(target, allow_pickle=False) as old:
                    if set(old.files) != payload.keys() or any(old[k].dtype != v.dtype or not np.array_equal(old[k], v)
                                                             for k, v in payload.items()):
                        raise ValueError("Existing aggregate differs from source-authenticated case entries; preserve it")
            else:
                with target.with_suffix(".tmp").open("wb") as stream:
                    np.savez_compressed(stream, **payload)
                target.with_suffix(".tmp").replace(target)
            output_files[target.name] = sha(target)
    expected_case_ids = {r["case_id"] for r in all_receipts}
    expected_scored_ids = {r["case_id"] for r in all_receipts if r["status"] == "SCORED"}
    if ({p.stem for p in (out / "cases").glob("*.npz")} != expected_scored_ids
            or {p.stem for p in (out / "cases").glob("*.json")} != expected_case_ids):
        raise ValueError("Unlisted or missing case artifacts cannot enter a completed assessment")
    write(out / "ASSESSMENT.json", dict(status="COMPLETE" if not failures else "HOLD", frozen_sha256=frozen_sha,
        receipt_version="wfg.forecast-assessment/2", per_fire_files=output_files,
        events=events, cases=all_receipts, failed_or_unavailable=failures, host=P.host_record(), timings=timing_rows))
    if args.cohort == "us2024":
        write(args.run / "report_inputs.json", dict(perimeters=str(args.data / "perimeters"), data_root=str(args.data / "environment"),
            fitted_models=sorted(models), best_dilation_hours_per_cell=best, n_samples=1024, seed=0,
            frozen_assessment_sha256=frozen_sha, cohort="US2024 NIROPS mapped extent", data_manifest_sha256=frozen["extraction_manifest_sha256"]))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
