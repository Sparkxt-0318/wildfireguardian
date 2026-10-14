"""Matched M548/FARSITE evaluation against actual NIROPS survey perimeters.

Fire reference states are rasterized from dated, observation-derived polygons.
No kriging arrival or uncertainty raster is opened. All survey endpoints must
exist exactly; a minute-bearing interval uses hourly transitions followed by
one exact fractional interval. Existing public recursive API rules are unchanged.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import time

from affine import Affine
import numpy as np
import pandas as pd
from pyproj import Transformer
from rasterio.features import rasterize
from shapely.geometry import box, shape
from shapely.ops import transform as project_geometry, unary_union
import torch

from .api import load_model
from .cumulative import CumulativePrediction
from .cumulative_report import (
    INFERENCE_FIELDS, _CSV, _EntryStore, _pool, _safe, _schema, _score_case,
    _sha256, _write_json, case_seed,
)
from .data import load_data
from .farsite_evaluation import farsite_cumulative_prediction
from .farsite_inputs import FuelMoistureScenario, prepare_farsite_inputs
from .farsite_report import read_engine_output
from .paths import DATA_ROOT, RUNS, WORKSPACE
from .prediction import Prediction, _array
from .progress import Activity, ProgressBar
from .rollout import simulate, validate_controls


M548_CHECKPOINT = RUNS / "20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt"
M548_SHA256 = "c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843"
DEFAULT_OBSERVATIONS = WORKSPACE / "data/sources/nirops_95rj5d379g_v1/FishCreek.geojson"


@dataclass(frozen=True)
class ObservedEvaluationConfig:
    observations: Path = DEFAULT_OBSERVATIONS
    event: str = "WY-BTF-002416_FishCreek"
    cutoff: str = "2024-08-22T08:02:00Z"
    endpoint: str = "2024-08-23T02:14:00Z"
    hours: float | None = None
    checkpoint: Path = M548_CHECKPOINT
    data_root: Path = DATA_ROOT
    output_dir: Path = RUNS / "20261012_observed_m548_farsite"
    n_samples: int = 1024
    seed: int = 0
    trajectory_batch_size: int = 32
    threads: int = 4
    threshold: float = .5
    timestep_minutes: int = 1
    timeout_seconds: int = 1800
    plots: bool = True
    engine: Path | None = None
    progress: bool = True

    def __post_init__(self):
        for name in ("n_samples", "trajectory_batch_size", "threads", "timestep_minutes", "timeout_seconds"):
            value = getattr(self, name)
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer excluding booleans")
        if isinstance(self.seed, (bool, np.bool_)) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a nonnegative integer excluding booleans")
        if self.hours is not None and (isinstance(self.hours, (bool, np.bool_))
                or not isinstance(self.hours, (int, float)) or not math.isfinite(self.hours) or self.hours <= 0):
            raise ValueError("hours must be a finite positive number excluding booleans")
        if (isinstance(self.threshold, (bool, np.bool_)) or not math.isfinite(self.threshold)
                or not 0 <= self.threshold <= 1):
            raise ValueError("threshold must be finite and in [0,1]")


@dataclass(frozen=True)
class _ObservedCumulativePrediction(CumulativePrediction):
    """Align with an integer duration derived from the actual survey times.

    Some exact minute intervals cannot be represented as a float in hours
    whose multiplication by 3600 is exactly integral. This isolated adapter
    preserves the integer timestamp difference without relaxing the public
    cumulative container's strict fractional-second rejection.
    """
    duration_seconds: int = 0

    def __post_init__(self):
        super().__post_init__()
        if (len(self.hours) != 1 or len(self._predictions[0].probability.shape) != 4
                or not isinstance(self.duration_seconds, int) or self.duration_seconds <= 0
                or not math.isclose(self.hours[0] * 3600, self.duration_seconds, rel_tol=0, abs_tol=1e-7)):
            raise ValueError("Observed prediction requires one timeline horizon and its exact positive integer duration")

    def _aligned_burned_states(self, observed, *, hours):
        prediction = self.at(hours=hours)
        start, start_valid = prediction.aligned_burned_area(observed)
        end, end_valid = prediction._aligned_sample_field(
            observed, "burned_area", "burned_area_valid", offset_seconds=self.duration_seconds)
        return start, start_valid, end, end_valid


def _utc(value, name):
    result = pd.Timestamp(value)
    if result.tzinfo is None:
        raise ValueError(f"{name} must include an explicit UTC offset")
    result = result.tz_convert("UTC")
    if result != result.floor("min"):
        raise ValueError(f"{name} must identify a whole-minute observation time")
    return result


def survey_reference(path, grid, cutoff, endpoint):
    """Create absorbing cumulative mapped extent from real dated polygons.

    Polygon absence is a negative *mapped extent* outcome under an explicit
    incident-perimeter completeness assumption. It is not certified absence
    of heat or burning, and no survey coverage footprint is provided by NIROPS.
    The retained rectangular domain is fixed before comparison for both models.
    """
    raw = json.loads(Path(path).read_text())
    if raw.get("type") != "FeatureCollection" or not raw.get("features"):
        raise ValueError("Observed input must be a nonempty WGS84 GeoJSON FeatureCollection")
    cutoff, endpoint = _utc(cutoff, "cutoff"), _utc(endpoint, "endpoint")
    if endpoint <= cutoff:
        raise ValueError("endpoint must follow cutoff")
    projection = Transformer.from_crs(4326, int(grid["epsg"]), always_xy=True).transform
    surveys = []
    available_times = []
    for index, feature in enumerate(raw["features"]):
        properties = feature.get("properties", {})
        timestamp = _utc(properties["time_utc"], "survey time_utc")
        available_times.append(timestamp)
        if timestamp > endpoint:
            continue
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in ("Polygon", "MultiPolygon"):
            raise ValueError(f"Survey record {index} must have a valid nonempty polygon geometry")
        surveys.append((timestamp, project_geometry(projection, geometry), properties))
    surveys.sort(key=lambda item: item[0])
    for timestamp in (cutoff, endpoint):
        if timestamp not in available_times:
            raise ValueError(f"No actual NIROPS survey exists at exact requested endpoint {timestamp.isoformat()}; no interpolation is allowed")
    transform = Affine(*grid["transform"])
    height, width = int(grid["height"]), int(grid["width"])
    left, top = transform * (0, 0)
    right, bottom = transform * (width, height)
    domain = box(min(left, right), min(bottom, top), max(left, right), max(bottom, top))
    states, state_records = [], []
    for timestamp in (cutoff, endpoint):
        chosen = [(at, geometry, properties) for at, geometry, properties in surveys if at <= timestamp]
        cumulative = unary_union([geometry for _, geometry, _ in chosen])
        states.append(rasterize([(cumulative, 1)], out_shape=(height, width), transform=transform,
                                fill=0, all_touched=False, dtype="uint8"))
        state_records.append(dict(time_utc=timestamp.isoformat(), survey_count=len(chosen),
            source_record_ids=[properties.get("source_record_id") for _, _, properties in chosen],
            mapped_area_projected_m2=float(cumulative.area),
            mapped_area_inside_rectangle_m2=float(cumulative.intersection(domain).area),
            mapped_area_outside_rectangle_m2=float(cumulative.difference(domain).area),
            rasterized_mapped_cells=int(states[-1].sum())))
    if np.any(states[0] > states[1]):
        raise ValueError("Cumulative survey unions must be absorbing")
    references = dict(burned_area=torch.from_numpy(np.stack(states)[:, None].astype("float32")),
        burned_area_valid=torch.ones((2, 1, height, width), dtype=torch.bool),
        time_utc=torch.tensor([int(cutoff.timestamp()), int(endpoint.timestamp())]),
        time_valid=torch.ones(2, dtype=torch.bool), pixel_valid=torch.ones((1, height, width), dtype=torch.bool),
        affine_transform=torch.tensor(tuple(transform)[:6], dtype=torch.float64),
        epsg=torch.tensor(int(grid["epsg"])), event_id=grid["id"])
    audit = dict(path=str(Path(path).resolve()), sha256=_sha256(path),
        kind="independently interpreted NIROPS aerial infrared survey perimeters",
        physical_endpoint="cumulative mapped fire extent by survey time; not exact first ignition or active flame",
        rasterization="project to cached original CRS; cell center inside cumulative union, all_touched=False",
        cumulative_policy="union of this incident's survey polygons with acquisition time <= endpoint; no future polygon at cutoff",
        negative_policy="outside mapped union within fixed rectangle is not-mapped; interpreted as a negative mapped-extent outcome, not certified physically unburned",
        survey_coverage_footprint_available=False,
        timestamps_policy="original publisher harmonized UTC survey timestamps, possibly estimated by publisher; no interpolation or rounding",
        reconstructed_fire_labels_used=False, states=state_records,
        same_rectangle_for_both_models=True, original_shape=[height, width], epsg=int(grid["epsg"]),
        transform=list(transform)[:6], survey_count_available=len(raw["features"]))
    return references, audit


def observed_environment(model, config, reference):
    """Read only cutoff covariates; replace fire state with the initial survey."""
    cutoff = _utc(config.cutoff, "cutoff")
    source_time = cutoff.floor("h")
    with load_data(config.data_root, events=[config.event], sequence_length=1, patch_size=None,
                   time_range=(source_time.isoformat(), source_time.isoformat()),
                   include_fire_labels=False, daily_policy="completed_day", **_schema(model)) as dataset:
        if len(dataset) != 1:
            raise ValueError("Exactly one complete cutoff environmental snapshot is required")
        sample = dataset[0]
    for key in ("epsg", "affine_transform", "pixel_valid"):
        if not np.array_equal(_array(sample[key]), _array(reference[key])):
            raise ValueError(f"NIROPS and model environment geometries disagree: {key}")
    sample["burned_area"] = reference["burned_area"][:1].clone()
    sample["burned_area_valid"] = reference["burned_area_valid"][:1].clone()
    sample["time_utc"] = reference["time_utc"][:1].clone()
    return {key: value for key, value in sample.items() if key in INFERENCE_FIELDS}, source_time.isoformat()


def exact_survey_prediction(model, sample, hours, *, n_samples, seed, trajectory_batch_size,
                            progress_callback=None, cache_environment_kernels=True):
    """Use full hourly binary transitions and an exact final fractional step."""
    if model.family != "exponential":
        raise ValueError("This observed-duration extension currently requires a fitted exponential model")
    if not math.isclose(hours * 60, round(hours * 60), rel_tol=0, abs_tol=1e-8):
        raise ValueError("Observed prediction requires an exact whole-minute duration")
    validate_controls((float(math.ceil(hours)),), n_samples, seed, trajectory_batch_size)
    whole = int(math.floor(hours))
    durations = [1.0] * whole
    remainder = hours - whole
    if remainder > 1e-10:
        durations.append(remainder)
    inputs, geometry = model._prepare_prediction_inputs(sample)
    inputs, initialization = model._initialize_burned_area(inputs, geometry, "unburned")
    outputs = simulate(model.predictor, **inputs, hours=(float(hours),), n_samples=n_samples,
        seed=seed, trajectory_batch_size=trajectory_batch_size, boundary="zero",
        missing_burned_area="unburned", assumed_unburned_cells=initialization["assumed_unburned_cells"],
        step_durations=durations, progress_callback=progress_callback,
        cache_environment_kernels=cache_environment_kernels)
    output = outputs[0]
    details = output.pop("details")
    output["metadata"].update(initial_state_source="NIROPS observed cumulative perimeter",
                              exact_observed_endpoint=True)
    prediction = Prediction.from_details(details, dt_hours=hours, **geometry, **output)
    return _ObservedCumulativePrediction((float(hours),), (prediction,), int(round(hours * 60)) * 60)


def _markdown(report):
    p, audit = report["protocol"], report["observations"]
    lines = ["# M548 and FARSITE: matched NIROPS observation evaluation", "",
        f"Both models: **{p['event']}**, **{p['cutoff']} → {p['endpoint']}**, "
        f"**{p['hours']:g} hours ({p['duration_minutes']} minutes)**, identical original rectangle and shared scoring cells.", "",
        "The reference is directly rasterized from independently interpreted aerial infrared survey polygons. "
        "It does not use the published kriging arrival-time reconstruction. The initial state is the cumulative "
        "union of surveys available by the cutoff; the endpoint is the union available by the later survey.", "",
        "Outside the mapped union is a **not-mapped** outcome within this fixed incident rectangle. "
        "The source has no survey coverage-footprint mask and does not certify that every such cell was physically "
        "unburned. These scores measure agreement with mapped perimeter progression, not exact ignition, active flame, "
        "or complete physical burned area. Publisher timestamps are harmonized UTC and some may be estimated from metadata.", "",
        f"M548 uses {p['n_samples']:,} independent absorbing binary trajectories, seed {p['seed']}, "
        f"with steps {p['step_durations_hours']}. The final partial step uses the fitted exponential link. "
        "The public recursive API still requires whole-hour horizons. Monte Carlo intervals describe simulation error only.", "",
        "FARSITE is one deterministic scenario represented as 0/1 occupancy. All initial mapped polygon boundaries "
        "are assumed active. Dead/live fuel moisture remains the documented fixed scenario; weather repeats the cutoff "
        "spatial summary. M548 repeats its gridded cutoff covariates. Both use the last whole-hour environmental snapshot "
        "at or before the actual survey cutoff, without future environmental slices. The FARSITE copy corrects the "
        "legacy port's HHMM/minute parsing; the original engine and previous runs are preserved.", "",
        "The domain is the preexisting full cached event rectangle, selected retrospectively from event extent. "
        "This is a controlled retrospective experiment, not operational forecast validation. The default FishCreek "
        "case has no M548 training or validation cache rows. Neither model nor threshold is fitted on these two survey outcomes.", "",
        f"Classification threshold: {p['threshold']:g}; equal-weight grid cells. Initial mapped burns are excluded "
        "from future-new-burn scoring and included in total mapped occupancy.", "",
        "## Every reported score", "",
        "Exact log loss, KL, and Bhattacharyya distance retain infinity when a certain prediction contradicts a reference. "
        "Floored loss/KL use epsilon=1e-7 and are reported separately. Probability distances compare cellwise Bernoulli "
        "distributions on {0,1}; Wasserstein here is not geographic transport. Unsupported rank and empty-cohort metrics "
        "remain unavailable. For nonempty cohorts, zero-denominator precision, recall, F1, MCC, specificity, and "
        "intersection over union use the existing scorer's zero convention; examine the accompanying class counts.", ""]
    def number(value):
        if value is None:
            return "Unavailable"
        if isinstance(value, float):
            return f"{value:.10g}"
        return str(value)
    for quantity in ("new_burn", "burned"):
        lines += [f"### {'Future newly mapped burns' if quantity == 'new_burn' else 'Total mapped burned occupancy'}", ""]
        for cohort in ("shared_models", "native"):
            rows = [row for row in report["summary"] if row["quantity"] == quantity and row["cohort"] == cohort]
            lines += [f"#### {'Shared coverage — primary comparison' if cohort == 'shared_models' else 'Individual model coverage — diagnostic'}", "",
                      "| Score | M548 | FARSITE |", "|---|---:|---:|"]
            for section in ("metrics", "classification", "calibration"):
                keys = list(dict.fromkeys(key for row in rows for key in row[section]))
                for key in keys:
                    if any(isinstance(row[section].get(key), (dict, list)) for row in rows):
                        continue
                    lines.append(f"| {section}.{key} | " + " | ".join(number(row[section].get(key)) for row in rows) + " |")
            bins = [(row["model_id"], bin_row) for row in rows for bin_row in row["calibration"]["bins"]]
            if bins:
                keys = list(dict.fromkeys(key for _, bin_row in bins for key in bin_row))
                lines += ["", "Fixed calibration bins (lower inclusive; upper inclusion is explicit):", "",
                          "| Model | " + " | ".join(keys) + " |",
                          "|---|" + "---:|" * len(keys)]
                for model_id, bin_row in bins:
                    lines.append(f"| {model_id} | " + " | ".join(number(bin_row.get(key)) for key in keys) + " |")
            lines += [""]
    lines += ["", "## Observation provenance", "", f"GeoJSON SHA256: `{audit['sha256']}`.", "",
        "[NIROPS publisher dataset](https://data.mendeley.com/datasets/95rj5d379g/1), DOI 10.17632/95rj5d379g.1, CC BY 4.0. "
        "The source download metadata and polygon record IDs are preserved in the data directory and report.json.", "",
        "## Figures", ""]
    for stem, figure in report.get("plots", {}).get("figures", {}).items():
        png = figure["outputs"]["png"]["path"]
        svg = figure["outputs"]["svg"]["path"]
        lines += [f"### {stem.replace('_', ' ')}", "", figure["description"], "",
                  f"![{stem}]({png})", "", f"[PNG]({png}) · [SVG]({svg})", ""]
    return "\n".join(lines)


def run_observed_evaluation(config, *, _model=None):
    cutoff, endpoint = _utc(config.cutoff, "cutoff"), _utc(config.endpoint, "endpoint")
    minutes = int((endpoint - cutoff) / pd.Timedelta(minutes=1))
    if minutes <= 0:
        raise ValueError("Observed endpoint must follow cutoff")
    hours = minutes / 60
    if config.hours is not None and not math.isclose(config.hours, hours, rel_tol=0, abs_tol=1e-10):
        raise ValueError(f"Entered hours={config.hours} does not equal the actual survey interval {hours:g}; exact observed endpoints are required")
    validate_controls((float(math.ceil(hours)),), config.n_samples, config.seed, config.trajectory_batch_size)
    if _sha256(config.checkpoint) != M548_SHA256:
        raise ValueError("This comparison must retain the original poster M548 checkpoint")
    if not 0 <= config.threshold <= 1:
        raise ValueError("threshold must be in [0,1]")
    output = Path(config.output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Preserve existing results; output must be new or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    report = dict(status="running", output_dir=str(output), created_at_utc=datetime.now(timezone.utc).isoformat(),
                  models=[], summary=[], per_event=[], failures=[],
                  plot_context=dict(reference_label="NIROPS mapped-perimeter outcome fraction",
                                    reference_description="binary NIROPS mapped-perimeter outcome"))
    writers = {}
    try:
        torch.set_num_threads(config.threads)
        grid = json.loads((Path(config.data_root) / "regions" / config.event / "grid.json").read_text())
        reference, audit = survey_reference(config.observations, grid, cutoff, endpoint)
        provenance = Path(config.observations).parent / "provenance.json"
        if not provenance.exists():
            raise ValueError("NIROPS provenance.json is required; run acquire-observed-data first")
        publisher = json.loads(provenance.read_text())
        from .observed_data import ARCHIVE_SHA256, DOI
        matching_event = (publisher.get("incident_component") == config.event
                          if publisher.get("incident_component") is not None else
                          publisher.get("incident_number") == config.event.split("_", 1)[0])
        if (publisher.get("geojson_sha256") != audit["sha256"]
                or publisher.get("archive_sha256") != ARCHIVE_SHA256
                or publisher.get("dataset_doi") != DOI
                or not matching_event):
            raise ValueError("Observed polygons, selected incident, and pinned NIROPS provenance must agree")
        audit["publisher_provenance"] = publisher
        report["observations"] = audit
        model = load_model(config.checkpoint, device="cpu") if _model is None else _model
        sample, environment_time = observed_environment(model, config, reference)
        seed = case_seed(config.seed, config.event, cutoff.isoformat())
        durations = [1.0] * int(hours) + ([hours - int(hours)] if hours != int(hours) else [])
        protocol = dict(event=config.event, cutoff=cutoff.isoformat(), endpoint=endpoint.isoformat(),
            hours=hours, duration_minutes=minutes, method="matched_observed_perimeter",
            n_samples=config.n_samples, seed=config.seed, case_seed=seed,
            trajectory_batch_size=config.trajectory_batch_size, step_durations_hours=durations,
            threshold=config.threshold, full_rectangle=True, data_root=str(Path(config.data_root).resolve()),
            environment_policy="repeated_current", environmental_snapshot_time_utc=environment_time,
            boundary="zero", reference_policy="NIROPS cumulative mapped survey unions; exact acquired endpoints; no kriging or interpolation",
            primary_cohort="same ordered intersection of both model validities and fixed rectangle mapped-extent reference",
            negative_reference_assumption=audit["negative_policy"],
            probability_distance_space="per-cell Bernoulli {0,1}, unit outcome distance", plots=config.plots,
            cases=[dict(event=config.event, cutoff=cutoff.isoformat(), endpoint=endpoint.isoformat(), seed=seed)],
            implementation_sha256={name: _sha256(Path(__file__).with_name(name)) for name in
                ("observed_evaluation.py", "rollout.py", "data.py", "farsite_inputs.py", "metrics.py")})
        report["protocol"] = protocol
        _write_json(output / "protocol.json", protocol)
        np.savez_compressed(output / "reference.npz", **{key: _array(value) for key, value in reference.items()},
                            metadata_json=np.array(json.dumps(_safe(audit))))
        _write_json(output / "report.json", report)
        if not config.progress:
            print("FARSITE: preparing the same observed initial perimeter", flush=True)
        from .farsite_observed_build import build_observed_engine
        default_engine = WORKSPACE / "tmp/farsite_observed_source/src/TestFARSITE"
        engine = Path(config.engine) if config.engine else (default_engine if default_engine.exists() else build_observed_engine())
        engine = Path(engine).resolve()
        engine_manifest = json.loads((engine.parent.parent / "observed_build_manifest.json").read_text())
        if engine_manifest.get("executable_sha256") != _sha256(engine) or not engine_manifest.get("clock_loading_changes"):
            raise ValueError("Minute-preserving FARSITE engine must match its observed-clock manifest")
        prepared = prepare_farsite_inputs(config.event, cutoff.isoformat(), hours, output / "simulation",
            data_root=config.data_root, timestep_minutes=config.timestep_minutes,
            observed_initial=_array(reference["burned_area"])[0, 0],
            observed_initial_valid=_array(reference["burned_area_valid"])[0, 0],
            observed_initial_source=dict(path=audit["path"], sha256=audit["sha256"],
                                        derivation=audit["cumulative_policy"], time_utc=cutoff.isoformat()))
        if not prepared.environment_valid.all():
            raise ValueError("Full physical environmental coverage is required for this matched comparison")
        report["farsite_input_manifest"], report["engine"] = prepared.manifest, engine_manifest
        probe = Path(engine_manifest["native_clock_probe"])
        if _sha256(probe) != engine_manifest["native_clock_probe_sha256"]:
            raise ValueError("Native clock probe differs from its build manifest")
        checked = subprocess.run([str(probe), str(prepared.lcp_path), str(prepared.input_path)],
                                 capture_output=True, text=True, check=True, timeout=60)
        records = [line for line in checked.stdout.splitlines() if line.startswith('{"start_hhmm"')]
        if len(records) != 1:
            raise RuntimeError("Native clock probe did not return exactly one loaded-clock record")
        clock_verification = json.loads(records[0])
        start_local = datetime.fromisoformat(prepared.manifest["clock"]["start_local"])
        end_local = datetime.fromisoformat(prepared.manifest["clock"]["end_local"])
        if (clock_verification["start_hhmm"] != start_local.hour * 100 + start_local.minute
                or clock_verification["end_hhmm"] != end_local.hour * 100 + end_local.minute
                or clock_verification["duration_minutes"] != minutes):
            raise RuntimeError("Actual native clock does not match the two exact survey endpoints")
        report["native_clock_verification"] = clock_verification
        simulation = output / "simulation"
        _write_json(simulation / "clock_verification.json", clock_verification)
        _write_json(output / "report.json", report)
        if not config.progress:
            print(f"M548: simulating {config.n_samples} trajectories over {hours:g} hours", flush=True)
        model_started = time.monotonic()
        with ExitStack() as stack:
            bar = None
            def simulation_progress(completed, total):
                nonlocal bar
                if bar is None:
                    bar = stack.enter_context(ProgressBar(total, "M548 simulation steps", enabled=config.progress))
                bar.update(completed)
            mixed = exact_survey_prediction(model, sample, hours, n_samples=config.n_samples,
                seed=seed, trajectory_batch_size=config.trajectory_batch_size,
                progress_callback=simulation_progress if config.progress else None)
        np.savez_compressed(output / "m548_prediction.npz", **mixed.at(hours=hours).numpy())
        report["m548_inference_seconds"] = time.monotonic() - model_started
        _write_json(output / "report.json", report)
        if not config.progress:
            print("FARSITE: running the exact survey interval", flush=True)
        (simulation / "outputs").mkdir()
        (simulation / "command.txt").write_text("landscape.lcp scenario.input ignition.shp 0 outputs/farsite 1\n")
        with Activity("FARSITE simulation", enabled=config.progress), (simulation / "engine.log").open("w") as log:
            process = subprocess.run([str(engine), "command.txt"], cwd=simulation, stdout=log,
                                     stderr=subprocess.STDOUT, timeout=config.timeout_seconds, check=False)
            log.flush()
            if process.returncode or re.search(r"(?im)^\s*(?:error\b|.*LaunchFarsite failure)", (simulation / "engine.log").read_text(errors="replace")):
                raise RuntimeError("FARSITE execution failed; inspect simulation/engine.log")
        arrival, execution = read_engine_output(simulation, prepared, hours, clock_verification=clock_verification)
        report["farsite_execution"] = execution
        farsite = farsite_cumulative_prediction(arrival, sample, hours=[hours], arrival_origin_time_utc=cutoff.isoformat(),
            no_burn_value=-9999, coverage=prepared.environment_valid,
            _exact_duration_minutes=minutes,
            metadata=dict(observed_initial=True, fixed_moisture_scenario=prepared.manifest["fuel_moisture_scenario_percent"],
                          observed_clock_patch=engine_manifest["clock_assignment_correction"]))
        farsite = _ObservedCumulativePrediction(farsite.hours, farsite._predictions, minutes * 60)
        np.savez_compressed(output / "farsite_prediction.npz", **farsite.at(hours=hours).numpy(), arrival_minutes=arrival)
        report["models"] = [dict(model_id="M548", display_label="M548", architecture="MixedNonnegativeKernel",
            path=str(Path(config.checkpoint).resolve()), sha256=M548_SHA256),
            dict(model_id="FARSITE", display_label="FARSITE", architecture="FARSITE",
                 path=str(engine.resolve()), sha256=_sha256(engine))]
        predictions = (mixed, farsite)
        shared = np.logical_and.reduce([_array(prediction.at(hours=hours).valid) for prediction in predictions])
        scratch = output / "_entries"
        scratch.mkdir()
        stores = {}
        writers = {name: _CSV(output / name) for name in ("summary.csv", "per_event.csv", "per_cutoff.csv", "calibration.csv")}
        evaluations = {}
        for index, (record, prediction) in enumerate(zip(report["models"], predictions)):
            for quantity in ("new_burn", "burned"):
                native, native_entries = _score_case(prediction, reference, hours, quantity=quantity, threshold=config.threshold)
                matched, matched_entries = _score_case(prediction, reference, hours, quantity=quantity,
                                                       threshold=config.threshold, cohort_mask=shared)
                evaluations[f"{record['model_id']}_{quantity}"] = matched
                denominator = native["per_horizon"][0]["coverage"]["reference_eligible_cells"]
                counts = dict(reference_eligible_cells=denominator,
                    native_prediction_covered_cells=native["per_horizon"][0]["coverage"]["evaluated_cells"],
                    shared_evaluated_cells=matched["per_horizon"][0]["coverage"]["evaluated_cells"])
                for cohort, entries in (("native", native_entries), ("shared_models", matched_entries)):
                    store = _EntryStore(scratch / f"{index}_{cohort}_{quantity}.bin")
                    store.append(entries)
                    stores[index, cohort, quantity] = store
                    row = dict(model_id=record["model_id"], event="ALL", hours=hours, cohort=cohort,
                        quantity=quantity, **counts,
                        native_coverage_fraction=counts["native_prediction_covered_cells"] / denominator if denominator else None,
                        shared_retention_fraction=counts["shared_evaluated_cells"] / denominator if denominator else None,
                        **_pool([entries], config.threshold))
                    report["summary"].append(row)
                    report["per_event"].append(dict(row, event=config.event))
                    writers["summary.csv"].append(row)
                    writers["per_event.csv"].append(dict(row, event=config.event))
                    writers["per_cutoff.csv"].append(dict(row, event=config.event, cutoff=cutoff.isoformat(), endpoint=endpoint.isoformat()))
                    for entry in row["calibration"]["bins"]:
                        writers["calibration.csv"].append(dict(model_id=record["model_id"], event="ALL", quantity=quantity, cohort=cohort, **entry))
        report["evaluation"] = evaluations
        report["counts"] = dict(initial_mapped_cells=int(reference["burned_area"][0].sum()),
            endpoint_mapped_cells=int(reference["burned_area"][1].sum()),
            newly_mapped_cells=int((reference["burned_area"][1] - reference["burned_area"][0]).sum()),
            rectangle_cells=int(reference["pixel_valid"].sum()), shared_prediction_cells=int(shared.sum()))
        if config.plots:
            from .observed_report_plots import generate_observed_report_plots
            transform = Affine(*grid["transform"])
            left, top = transform * (0, 0)
            right, bottom = transform * (grid["width"], grid["height"])
            spatial = dict(initial_burned=_array(reference["burned_area"])[0, 0],
                observed_burned=_array(reference["burned_area"])[1, 0],
                observed_valid=np.ones(tuple(audit["original_shape"]), dtype=bool), shared_valid=shared[0, 0],
                predictions={record["model_id"]: dict(new_burn=_array(prediction.at(hours=hours).probability)[0, 0],
                    burned=_array(prediction.at(hours=hours).burned_probability)[0, 0])
                    for record, prediction in zip(report["models"], predictions)},
                extent=[left, right, bottom, top], coordinate_label=f"EPSG:{grid['epsg']} metres",
                description=f"{config.event} NIROPS mapped extent; {cutoff.isoformat()} → {endpoint.isoformat()}; {hours:g} h")
            report["plots"] = generate_observed_report_plots(_safe(report), output, stores=stores, spatial=spatial)
        shutil.rmtree(scratch)
        report["status"] = "complete"
        report["elapsed_seconds"] = time.monotonic() - started
        _write_json(output / "report.json", report)
        (output / "report.md").write_text(_markdown(_safe(report)))
        print(f"Observed evaluation complete: {output}", flush=True)
        return report
    except Exception as error:
        report["status"] = "failed"
        report["failures"].append(dict(error=f"{type(error).__name__}: {error}"))
        _write_json(output / "report.json", report)
        raise
    finally:
        for writer in writers.values():
            writer.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("observations", "checkpoint", "data_root", "output_dir", "engine"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, default=getattr(ObservedEvaluationConfig, name))
    for name in ("event", "cutoff", "endpoint"):
        parser.add_argument("--" + name, default=getattr(ObservedEvaluationConfig, name))
    for name in ("n_samples", "seed", "trajectory_batch_size", "threads", "timestep_minutes", "timeout_seconds"):
        parser.add_argument("--" + name.replace("_", "-"), type=int, default=getattr(ObservedEvaluationConfig, name))
    parser.add_argument("--threshold", type=float, default=.5)
    parser.add_argument("--hours", type=float, required=True, help="Explicit duration; must equal the exact interval between two real survey timestamps")
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--no-progress", action="store_true", help="Disable progress bars and FARSITE elapsed-time display")
    values = vars(parser.parse_args(argv))
    values["plots"] = not values.pop("no_plots")
    values["progress"] = not values.pop("no_progress")
    return run_observed_evaluation(ObservedEvaluationConfig(**values))


if __name__ == "__main__":
    main()
