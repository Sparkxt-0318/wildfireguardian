"""Frozen 2026 reference-cohort validation and receipt-bound metric scoring.

References come from pinned full-rectangle source arrays. No prepared mask can
select the scored population. Run this script inside the verified source tree.
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
import platform
import sys
import time

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "forecast"))
import numpy as np
import pandas as pd
import torch
from wildfire import baselines as B
from wildfire.api import load_model
from wildfire.survival import PerimeterSample, ages_from_states, consecutive_intervals

VARIANTS = ["base", "d4", "d4_wind", "ellipse", "burnout", "burnout_spotting", "mixed_base"]
MODEL_NAMES = {"c651_mc", *(v + "_seed0" for v in VARIANTS)}
C651_SHA = "c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843"
DEADLINE = pd.Timestamp("2027-12-31T23:59:00Z")
RECEIPT_VERSION = "wfg.forecast-blind-run/2"
BASELINE_NAMES = {"persistence", "logistic", "dilation_best", *(f"dilation_{k}h" for k in (1, 2, 4, 8))}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path, obj):
    temporary = Path(str(path) + ".tmp")
    temporary.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Manifest paths must stay inside their declared root")
    return path


def key(case):
    return (case["event"], pd.Timestamp(case["cutoff"]).isoformat(), pd.Timestamp(case["endpoint"]).isoformat())


def checked_input(root, cohort, relative):
    if relative not in cohort["input_sha256"]:
        raise ValueError(f"Required reference input is not pinned: {relative}")
    path = inside(root, relative)
    if sha(path) != cohort["input_sha256"][relative]:
        raise ValueError(f"Input identity changed: {relative}")
    return path


def reference_cases(root, cohort):
    """Derive all eligible cases from the complete pinned 2026 event catalog."""
    catalog = json.loads(checked_input(root, cohort, "environment/events.json").read_text())
    events = [e for e in catalog if e["year"] == 2026]
    expected, references = [], {}
    for event in events:
        name = event["id"]
        checked_input(root, cohort, f"baseline-terrain/{name}/elevation_m_375m.tif")
        if pd.Timestamp(event["t0_utc"]).year != 2026 or event["country"] not in ("US", "KR"):
            raise ValueError("Fire year and evidence class must agree with source metadata")
        shape = (event["height"], event["width"])
        start, end = pd.Timestamp(event["start_utc"]), pd.Timestamp(event["end_utc"])
        if event["country"] == "US":
            path = checked_input(root, cohort, f"perimeters/{name}/states.npz")
            with np.load(path, allow_pickle=False) as data:
                times = list(pd.to_datetime(data["times"], utc=True))
                states = data["states"].copy()
            if states.shape != (len(times), *shape) or not np.isin(states, (0, 1)).all():
                raise ValueError("NIROPS states must be binary full-rectangle arrays")
            if any(times[i] >= times[i + 1] for i in range(len(times) - 1)) or np.any(states[:-1] > states[1:]):
                raise ValueError("NIROPS states must be ordered cumulative survey unions")
            for i, j, hours in consecutive_intervals(times, 48):
                if not start <= times[i].floor("h") <= end:
                    continue
                case = dict(event=name, cutoff=times[i].isoformat(), endpoint=times[j].isoformat(), year=2026,
                            reference_kind="nirops_mapped_extent")
                initial = states[i].astype(bool)
                references[key(case)] = dict(initial=initial, endpoint=states[j].astype(bool), mask=~initial,
                                             age=np.nan_to_num(ages_from_states(times, states, i), nan=0),
                                             hours=hours, event=event)
                expected.append(case)
        else:
            import rasterio
            path = checked_input(root, cohort, f"environment/regions/{name}/arrival_time_hours.tif")
            with rasterio.open(path) as source:
                arrival = source.read(1, masked=True).filled(np.nan).astype(float)
            finite = np.isfinite(arrival)
            if arrival.shape != shape or not finite.any():
                raise ValueError("Reconstruction source is unavailable or has a different rectangle")
            t0 = pd.Timestamp(event["t0_utc"])
            for proposed in np.arange(np.floor(np.nanmin(arrival)), np.ceil(np.nanmax(arrival)), 12):
                cutoff = (t0 + pd.Timedelta(hours=float(proposed))).floor("h")
                if not start <= cutoff <= end:
                    continue
                elapsed = (cutoff - t0).total_seconds() / 3600
                initial = finite & (arrival <= elapsed)
                if not initial.any():
                    continue
                case = dict(event=name, cutoff=cutoff.isoformat(), endpoint=(cutoff + pd.Timedelta(hours=12)).isoformat(),
                            year=2026, reference_kind="korean_arrival_reconstruction")
                references[key(case)] = dict(initial=initial, endpoint=finite & (arrival <= elapsed + 12),
                                             mask=finite & ~initial, age=np.where(initial, elapsed - arrival, 0),
                                             hours=12., event=event)
                expected.append(case)
    return expected, references


def validate(registry_path, cohort_path, model_root, input_root):
    if model_root.resolve() != REPO:
        raise ValueError("Execute the script inside the exact verified source tree, also after relocation")
    registry, cohort = json.loads(registry_path.read_text()), json.loads(cohort_path.read_text())
    if registry.get("status") != "FROZEN" or set(registry.get("models", {})) != MODEL_NAMES:
        raise ValueError("The exact frozen eight-model registry is required")
    if registry.get("selected_model") not in MODEL_NAMES - {"c651_mc"}:
        raise ValueError("Primary selection must be one of the seven development-selected variants")
    if registry["models"]["c651_mc"]["sha256"] != C651_SHA or registry.get("best_dilation_hours_per_cell") not in (1, 2, 4, 8):
        raise ValueError("Frozen comparator identity or dilation choice is invalid")
    required = {str(p.relative_to(REPO)) for p in (REPO / "forecast/wildfire").rglob("*")
                if p.is_file() and p.suffix in (".py", ".json")}
    required |= {"research/forecast-v2/scripts/pipeline.py", "research/forecast-v2/scripts/blind_test.py",
                 "research/forecast-v2/SPLIT.json"}
    if not required <= registry.get("producer_source_sha256", {}).keys():
        raise ValueError("The complete executed forecast source closure must be pinned")
    for item in [*registry["models"].values(), registry["logistic"]]:
        if sha(inside(model_root, item["path"])) != item["sha256"]:
            raise ValueError("Frozen model or baseline bytes changed")
    for path, expected in registry["producer_source_sha256"].items():
        if sha(inside(model_root, path)) != expected:
            raise ValueError(f"Executed source identity changed: {path}")
    if cohort.get("registry_sha256") != sha(registry_path):
        raise ValueError("Cohort is not bound to this exact registry")
    required_inputs = {str(p.relative_to(input_root)) for p in (input_root / "environment").rglob("*")
                       if p.is_file() and p.suffix.lower() in (".tif", ".tiff", ".json", ".csv", ".txt", ".npz")}
    required_inputs |= {str(p.relative_to(input_root)) for p in (input_root / "baseline-terrain").rglob("*.tif")}
    if not required_inputs <= cohort.get("input_sha256", {}).keys():
        raise ValueError("All executed environmental inputs and metadata must be pinned")
    for path, expected in cohort.get("input_sha256", {}).items():
        if sha(inside(input_root, path)) != expected:
            raise ValueError(f"Blind input bytes changed: {path}")
    release = pd.Timestamp(cohort["source_release_utc"])
    if release.tzinfo is None or release > DEADLINE:
        raise ValueError("Source release does not satisfy the fixed deadline")
    registration = cohort.get("registration", {})
    registered = pd.Timestamp(registration["registered_utc"])
    if (not str(registration.get("url", "")).startswith("https://osf.io/")
            or registration.get("registry_sha256") != sha(registry_path)
            or registered.tzinfo is None or registered >= release):
        raise ValueError("Owner registration must pin this registry before source release")
    expected, references = reference_cases(input_root, cohort)
    observed = cohort.get("cases", [])
    if (not expected or len({key(c) for c in observed}) != len(observed)
            or {key(c) for c in observed} != {key(c) for c in expected}):
        raise ValueError("Cohort must include exactly all eligible source cases")
    by_key = {key(c): c for c in expected}
    for case in observed:
        if case.get("year") != 2026 or case["reference_kind"] != by_key[key(case)]["reference_kind"]:
            raise ValueError("Declared year or evidence class differs from source metadata")
    return registry, cohort, references


def validation_identity(registry, cohort):
    """Bind a validated run to its complete source, checkpoint and input closure."""
    return dict(producer_source_sha256=registry["producer_source_sha256"],
                model_sha256={n: r["sha256"] for n, r in registry["models"].items()},
                logistic_sha256=registry["logistic"]["sha256"], input_sha256=cohort["input_sha256"])


def load_pipeline():
    """Load the numerical producer only after custody validation succeeds."""
    spec = importlib.util.spec_from_file_location("frozen_forecast_v2_pipeline", HERE.with_name("pipeline.py"))
    pipeline = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = pipeline
    spec.loader.exec_module(pipeline)
    return pipeline


def load_runtime(args, registry, cohort):
    pipeline = load_pipeline()
    torch.set_num_threads(2)
    environment = pipeline.Environment(args.input_root / "environment", args.entries / "environment_cache"
                                       if hasattr(args, "entries") else args.out / "environment_cache",
                                       cohort["input_sha256"])
    c651 = load_model(inside(args.model_root, registry["models"]["c651_mc"]["path"]), device="cpu")
    models = {n: pipeline.load_structured(inside(args.model_root, r["path"]))
              for n, r in registry["models"].items() if n != "c651_mc"}
    logistic = pickle.loads(inside(args.model_root, registry["logistic"]["path"]).read_bytes())
    return pipeline, environment, c651, models, logistic


def source_sample(case, source, environment):
    raw = environment.at(case["event"], pd.Timestamp(case["cutoff"]).floor("h"))
    shape = (source["event"]["height"], source["event"]["width"])
    if raw.ndim != 3 or raw.shape[-2:] != shape:
        raise ValueError("Forecast and reference rectangles differ")
    return PerimeterSample(case["event"], case["cutoff"], source["hours"], raw,
                           source["initial"], source["endpoint"], source["mask"], np.ones(shape), source["age"],
                           kind="perimeter" if case["reference_kind"] == "nirops_mapped_extent" else "kriged",
                           residence_hours=environment.residence(case["event"]))


def deterministic_fields(runtime, sample, registry):
    """Derive support from model validity without resampling Monte Carlo trajectories.

    The c651 mean-field validity uses exactly the recursive Monte Carlo envelope.
    The numeric c651 mean-field values are not substituted for its stored forecast.
    """
    pipeline, environment, c651, models, logistic = runtime
    predictions, validities = {}, []
    with torch.no_grad():
        _, supported = pipeline.sample_forecast(c651.predictor, sample, use_burnout=False, use_spotting=False)
        validities.append(supported.numpy())
        for name, model in models.items():
            value, supported = pipeline.sample_forecast(model, sample)
            predictions[name] = value.numpy()
            validities.append(supported.numpy())
    predictions["persistence"] = B.persistence(sample.initial)
    for rate in B.DILATION_HOURS:
        predictions[f"dilation_{rate}h"] = B.dilation(sample.initial, sample.hours, rate)
    predictions["dilation_best"] = predictions[f"dilation_{registry['best_dilation_hours_per_cell']}h"]
    predictions["logistic"] = pipeline.logistic_predict(logistic, sample, environment.names,
                                                       environment.terrain_gradient(sample.event_id))
    mask = sample.score_mask & ~sample.initial & np.isfinite(sample.environment).all(0)
    for valid in validities:
        if valid.shape != mask.shape or valid.dtype != np.bool_:
            raise ValueError("Model validity must be a boolean full-rectangle mask")
        mask &= valid
    for value in predictions.values():
        if value.shape != mask.shape:
            raise ValueError("Model predictions must match the source rectangle")
        mask &= np.isfinite(value)
    return predictions, mask


def heavy_lock():
    path = Path("/tmp/wfg/HEAVY.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a+")


def run(args):
    registry, cohort, references = validate(args.registry, args.cohort, args.model_root, args.input_root)
    if args.out.exists() and any(args.out.iterdir()):
        raise FileExistsError("Use a new directory and preserve previous blind predictions")
    (args.out / "cases").mkdir(parents=True)
    runtime = load_runtime(args, registry, cohort)
    pipeline, environment, c651, _, _ = runtime
    records = []
    for case in cohort["cases"]:
        identity = hashlib.sha256(json.dumps(key(case)).encode()).hexdigest()[:24]
        record = dict(case=case, case_id=identity, status="RUNNING", seed=0, trajectories=1024, trajectory_batch_size=32)
        started = time.perf_counter()
        try:
            source = references[key(case)]
            sample = source_sample(case, source, environment)
            with heavy_lock() as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                predictions, mask = deterministic_fields(runtime, sample, registry)
                predictions["c651_mc"], valid = pipeline.c651_monte_carlo(c651.predictor, sample, environment.names, 1024, 0)
                # The deterministic envelope must agree with MC support; numeric
                # failure cannot quietly remove additional scored coordinates.
                if (valid.shape != mask.shape or valid.dtype != np.bool_
                        or predictions["c651_mc"].shape != mask.shape or not np.all(valid[mask])):
                    raise ValueError("Monte Carlo validity differs from deterministic common support")
                if not np.isfinite(predictions["c651_mc"][mask]).all():
                    raise ValueError("Monte Carlo prediction is nonfinite on deterministic common support")
            record.update(reference_cells=int(source["mask"].sum()), scored_cells=int(mask.sum()),
                          excluded_cells=int((source["mask"] & ~mask).sum()))
            if mask.any():
                path = args.out / "cases" / f"{identity}.npz"
                with path.with_suffix(".tmp").open("wb") as stream:
                    np.savez_compressed(stream, y=sample.endpoint[mask], row=np.nonzero(mask)[0], col=np.nonzero(mask)[1],
                                        **{f"p_{n}": v[mask] for n, v in predictions.items()})
                path.with_suffix(".tmp").replace(path)
                record.update(status="SCORED", file=str(path.relative_to(args.out)), sha256=sha(path))
            else:
                record.update(status="UNAVAILABLE", reason="no common supported cells")
        except Exception as error:
            record.update(status="FAILED", error_type=type(error).__name__, reason=str(error))
        record["seconds"] = time.perf_counter() - started
        records.append(record)
        write(args.out / "cases" / f"{identity}.json", record)
    write(args.out / "RECEIPT.json", dict(receipt_version=RECEIPT_VERSION,
                                         registry_sha256=sha(args.registry), cohort_sha256=sha(args.cohort),
                                         validated_identity=validation_identity(registry, cohort), cases=records,
                                         host=dict(platform=platform.platform(), python=platform.python_version(),
                                                   torch=torch.__version__, numpy=np.__version__),
                                         completed_utc=datetime.now(timezone.utc).isoformat()))


def primary_decision(result, selected, complete=False):
    comparisons = {ref: result["paired"][f"{selected}__vs__{ref}"]["percentile_95_interval"][1] < 0
                   for ref in ("persistence", "dilation_best")}
    bins = {n: result["models"][n]["pooled"]["lowest_bin"] for n in (selected, "persistence", "dilation_best")}
    gaps = {n: abs(r["mean_prediction"] - r["observed_frequency"]) if r["count"] else None for n, r in bins.items()}
    calibration = gaps[selected] is not None and all(gaps[n] is not None and gaps[selected] <= gaps[n]
                                                    for n in ("persistence", "dilation_best"))
    enough = len(result["fires"]) >= 10
    return dict(complete_cohort_pass=complete,
                brier_comparisons_pass={n: complete and passed for n, passed in comparisons.items()},
                lowest_bin_gaps=gaps, calibration_pass=complete and calibration,
                minimum_fire_count_pass=complete and enough,
                statistical_superiority_criteria_pass=complete and enough and calibration and all(comparisons.values()),
                descriptive_subset_criteria=dict(brier_comparisons=comparisons, calibration=calibration,
                                                 minimum_fire_count=enough))


def score(args):
    registry, cohort, references = validate(args.registry, args.cohort, args.model_root, args.input_root)
    receipt = json.loads((args.entries / "RECEIPT.json").read_text())
    if (receipt.get("receipt_version") != RECEIPT_VERSION
            or receipt.get("validated_identity") != validation_identity(registry, cohort)
            or receipt.get("registry_sha256") != sha(args.registry) or receipt.get("cohort_sha256") != sha(args.cohort)):
        raise ValueError("Validated predictions must bind the exact source, checkpoints, inputs, registry and cohort")
    if sorted(key(r["case"]) for r in receipt["cases"]) != sorted(key(c) for c in cohort["cases"]):
        raise ValueError("Every cohort case requires exactly one outcome receipt")
    expected_cases = {key(case): case for case in cohort["cases"]}
    if any(r["case"] != expected_cases[key(r["case"])] for r in receipt["cases"]):
        raise ValueError("Case receipts must match the exact validated cohort metadata")
    listed = [r["file"] for r in receipt["cases"] if r["status"] == "SCORED"]
    actual = {str(p.relative_to(args.entries)) for p in (args.entries / "cases").glob("*.npz")}
    if len(set(listed)) != len(listed) or actual != set(listed):
        raise ValueError("Unlisted, reused or missing prediction files cannot enter scoring")
    grouped = {"nirops_mapped_extent": [], "korean_arrival_reconstruction": []}
    runtime = None
    for record in receipt["cases"]:
        if record["status"] not in ("SCORED", "FAILED", "UNAVAILABLE"):
            raise ValueError("Every case must have a final outcome status")
        if record["status"] == "FAILED":
            continue
        if runtime is None:
            runtime = load_runtime(args, registry, cohort)
        source = references[key(record["case"])]
        sample = source_sample(record["case"], source, runtime[1])
        with heavy_lock() as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            _, mask = deterministic_fields(runtime, sample, registry)
        counts = dict(reference_cells=int(source["mask"].sum()), scored_cells=int(mask.sum()),
                      excluded_cells=int((source["mask"] & ~mask).sum()))
        if any(record.get(name) != value for name, value in counts.items()):
            raise ValueError("Case counts must match the full source-derived common support")
        if record["status"] == "UNAVAILABLE":
            if mask.any():
                raise ValueError("Unavailable case has source-derived supported cells")
            continue
        if not mask.any():
            raise ValueError("Scored case has no source-derived common support")
        path = inside(args.entries, record["file"])
        if sha(path) != record["sha256"]:
            raise ValueError("Stored predictions changed")
        with np.load(path, allow_pickle=False) as data:
            required = MODEL_NAMES | BASELINE_NAMES
            if set(data.files) != {"y", "row", "col"} | {"p_" + n for n in required}:
                raise ValueError("Exact registered prediction models and coordinate columns are required")
            row, col, y = data["row"], data["col"], data["y"]
            expected_row, expected_col = np.nonzero(mask)
            h, w = mask.shape
            if (row.ndim != 1 or col.ndim != 1 or y.ndim != 1
                    or not np.issubdtype(row.dtype, np.integer) or not np.issubdtype(col.dtype, np.integer)
                    or np.any(row < 0) or np.any(row >= h) or np.any(col < 0) or np.any(col >= w)
                    or not np.array_equal(row, expected_row) or not np.array_equal(col, expected_col)):
                raise ValueError("Integer ordered coordinates must equal the full source-derived common support")
            if not np.array_equal(y, source["endpoint"][mask]):
                raise ValueError("Endpoint labels must match the pinned source at every scored coordinate")
            predictions = {n: data["p_" + n].copy() for n in required}
            if any(p.shape != y.shape or not np.isfinite(p).all() or np.any((p < 0) | (p > 1))
                   for p in predictions.values()):
                raise ValueError("Every registered probability must be finite, in [0,1] and cover the full common support")
            grouped[record["case"]["reference_kind"]].append((record, y.copy(), predictions))
    complete = all(r["status"] == "SCORED" for r in receipt["cases"])
    results = {}
    for kind, rows in grouped.items():
        if not rows:
            results[kind] = dict(status="UNAVAILABLE", complete_cohort_pass=False,
                                 decision=dict(complete_cohort_pass=False, statistical_superiority_criteria_pass=False))
            continue
        entries = dict(fire=np.concatenate([np.full(len(y), r["case"]["event"]) for r, y, _ in rows]),
                       y=np.concatenate([y for _, y, _ in rows]),
                       predictions={n: np.concatenate([p[n] for _, _, p in rows]) for n in rows[0][2]})
        result = B.score_entries(entries, draws=10000, seed=20261030)
        dilation = result["models"]["dilation_best"]
        for name, data in result["models"].items():
            db = dilation["pooled"]["brier"]
            data["pooled"]["bss_vs_best_dilation"] = 1 - data["pooled"]["brier"] / db if db else None
            p, y = entries["predictions"][name], entries["y"]
            wrong = int(((p == 0) & (y == 1) | (p == 1) & (y == 0)).sum())
            exact = None if wrong else float((-np.log(p[y == 1]).sum() - np.log1p(-p[y == 0]).sum()) / len(y))
            data["pooled"]["exact_nll"] = dict(value=exact, infinite=bool(wrong), certainty_wrong_entries=wrong)
            for fire, per_fire in data["per_fire"].items():
                dbf = dilation["per_fire"][fire]["brier"]
                per_fire["bss_vs_best_dilation"] = 1 - per_fire["brier"] / dbf if dbf else None
        result["decision"] = (primary_decision(result, registry["selected_model"], complete=complete)
                              if kind == "nirops_mapped_extent" else dict(secondary_descriptive_only=True, complete_cohort_pass=complete))
        result["status"] = ("INCOMPLETE_COHORT" if not complete else
                            "INCONCLUSIVE" if len(result["fires"]) < 10 else "SCORED_PENDING_RELOCATION_REPLAY")
        result["statistics_scope"] = "complete_cohort" if complete else "descriptive_scored_subset_only"
        results[kind] = result
    write(args.out, dict(registry_sha256=sha(args.registry), cohort_sha256=sha(args.cohort),
                         run_receipt_sha256=sha(args.entries / "RECEIPT.json"),
                         validated_identity=validation_identity(registry, cohort), selected_model=registry["selected_model"],
                         results=results, failed_cases=[r for r in receipt["cases"] if r["status"] == "FAILED"],
                         unavailable_cases=[r for r in receipt["cases"] if r["status"] == "UNAVAILABLE"],
                         complete_cohort_pass=complete, superiority_claim_permitted=False,
                         completion=("NOT_COMPLETE_UNTIL_INDEPENDENT_RELOCATED_SCORE_REPLAY" if complete else "INCOMPLETE_COHORT")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "run"):
        p = sub.add_parser(name)
        p.add_argument("--registry", type=Path, required=True)
        p.add_argument("--cohort", type=Path, required=True)
        p.add_argument("--model-root", type=Path, default=REPO)
        p.add_argument("--input-root", type=Path, required=True)
        if name == "run":
            p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("score")
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--cohort", type=Path, required=True)
    p.add_argument("--model-root", type=Path, required=True)
    p.add_argument("--input-root", type=Path, required=True)
    p.add_argument("--entries", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "validate":
        validate(args.registry, args.cohort, args.model_root, args.input_root)
        print("Frozen source, cohort and model identities matched")
    else:
        {"run": run, "score": score}[args.command](args)


if __name__ == "__main__":
    main()
