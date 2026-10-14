"""Audit all events and pool matched M548/FARSITE observations on test events.

Only exclusively held-out M548 events are evaluated. References are authentic
NIROPS mapped perimeters at actual survey times, never kriging arrival labels.
Planning, resumable case execution, and combined scoring are separate stages.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import tempfile

import numpy as np

from .api import load_model
from .cumulative_report import _CSV, _EntryStore, _pool, _safe, _sha256, _test_events, _write_json, case_seed
from .observed_data import ARCHIVE_NAME, ARCHIVE_SHA256, DEFAULT_DIRECTORY
from .observed_evaluation import M548_CHECKPOINT, M548_SHA256, ObservedEvaluationConfig, run_observed_evaluation
from .observed_inventory import DEFAULT_PREPARED, build_inventory
from .paths import DATA_ROOT, RUNS, WORKSPACE
from .progress import Activity, ProgressBar


# Original benchmark arrays and the byte-verified sibling metadata copy kept
# during consolidation. Both metadata versions describe the same array files;
# their old absolute source paths differ. The saved checkpoint's partition is
# additionally authoritative for every event that can enter this evaluation.
FROZEN_SPLIT_SHA256 = {
    "train.npz": "44ecb4fea32c866d7ee702765f505cdef93d2d4d5e959ba02d0432eb5cb80a11",
    "validation.npz": "36c3d4f53782fe0694249a7cff3eb6835115d6f511a4424e800b75a3aca45ef8",
    "test.npz": "e36391d77a6e5909ad4dfae8de4d14c50d6da28a4caf18409f1f0b19cbef8e0e",
}
COPIED_METADATA_SHA256 = "3f1a68e28217d198d32c705b3753e79624690dc8bc224dceb5428b10e850e7bf"


@dataclass(frozen=True)
class CombinedObservedConfig:
    data_root: Path = DATA_ROOT
    archive: Path = DEFAULT_DIRECTORY / ARCHIVE_NAME
    prepared_directory: Path = DEFAULT_PREPARED
    observations_dir: Path = DEFAULT_DIRECTORY / "catalog"
    checkpoint: Path = M548_CHECKPOINT
    output_dir: Path = RUNS / "20261012_observed_test_combined"
    events: tuple[str, ...] = ()
    intervals: str = "all"
    hours: float | None = None
    max_intervals_per_event: int | None = None
    max_hours: float | None = None
    reuse_results: Path | None = None
    additional_reuse_results: tuple[Path, ...] = ()
    report_only: bool = False
    n_samples: int = 1024
    seed: int = 0
    trajectory_batch_size: int = 32
    threads: int = 4
    threshold: float = .5
    timestep_minutes: int = 1
    timeout_seconds: int = 1800
    engine: Path | None = None
    plots: bool = True
    case_plots: bool = False
    plan_only: bool = False
    retry_failed: bool = False
    progress: bool = True

    def __post_init__(self):
        ObservedEvaluationConfig(n_samples=self.n_samples, seed=self.seed,
            trajectory_batch_size=self.trajectory_batch_size, threads=self.threads,
            threshold=self.threshold, timestep_minutes=self.timestep_minutes,
            timeout_seconds=self.timeout_seconds, hours=self.hours)
        if self.intervals not in ("all", "first", "shortest"):
            raise ValueError("intervals must be all, first or shortest")
        if len(set(self.events)) != len(self.events):
            raise ValueError("events must be distinct")
        limit = self.max_intervals_per_event
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
            raise ValueError("max_intervals_per_event must be a positive integer")
        if self.max_hours is not None and (isinstance(self.max_hours, (bool, np.bool_))
                or not isinstance(self.max_hours, (int, float)) or not math.isfinite(self.max_hours)
                or self.max_hours <= 0):
            raise ValueError("max_hours must be a finite positive number excluding booleans")
        if self.report_only and self.reuse_results is None:
            raise ValueError("report_only requires reuse_results pointing to a saved combined run")
        if self.additional_reuse_results and self.reuse_results is None:
            raise ValueError("additional_reuse_results requires a primary reuse_results source")
        sources = (() if self.reuse_results is None else (self.reuse_results,)) + tuple(self.additional_reuse_results)
        if len({Path(path).resolve() for path in sources}) != len(sources):
            raise ValueError("Stored result sources must be distinct")
        for directory in sources:
            source, target = Path(directory).resolve(), Path(self.output_dir).resolve()
            if source == target or target.is_relative_to(source) or source.is_relative_to(target):
                raise ValueError("reuse_results and output_dir must be separate directories; source results remain immutable")


def select_cases(inventory, config):
    """Select using source availability and saved partitions, never outcomes."""
    events = {row["event_id"]: row for row in inventory["events"]}
    unknown = set(config.events) - set(events)
    if unknown:
        raise ValueError(f"Unknown requested events: {sorted(unknown)}")
    cases, selected, exclusions = [], [], []
    for event_id, row in sorted(events.items()):
        reasons = list(row["exclusion_reasons"])
        counts = row["m548_partition"]
        if (row["m548_exposure"] != "held_out_event" or counts["train"]
                or counts["validation"] or not counts["test"]
                or event_id not in inventory["m548_checkpoint_test_events"]):
            reasons.append("Not an exclusively held-out M548 test event")
        if config.events and event_id not in config.events:
            reasons.append("Outside explicitly requested event subset")
        if reasons or not row["eligible"]:
            exclusions.append(dict(event_id=event_id, reasons=reasons))
            continue
        pairs = sorted(row["consecutive_intervals"], key=lambda item: item["cutoff_utc"])
        if config.hours is not None:
            pairs = [pair for pair in pairs if abs(pair["hours"] - config.hours) <= 1e-10]
        if config.max_hours is not None:
            pairs = [pair for pair in pairs if pair["hours"] <= config.max_hours + 1e-10]
        if config.intervals == "first":
            pairs = pairs[:1]
        elif config.intervals == "shortest":
            pairs = sorted(pairs, key=lambda pair: (pair["hours"], pair["cutoff_utc"], pair["endpoint_utc"]))
            pairs = pairs[:config.max_intervals_per_event or 1]
        if config.max_intervals_per_event is not None and config.intervals != "shortest":
            pairs = pairs[:config.max_intervals_per_event]
        if not pairs:
            exclusions.append(dict(event_id=event_id, reasons=["No observed interval matches the explicit duration/selection"]))
            continue
        selected.append(row)
        for pair in pairs:
            identity = f"{event_id}|{pair['cutoff_utc']}|{pair['endpoint_utc']}"
            cases.append(dict(event=event_id, case_id=hashlib.sha256(identity.encode()).hexdigest()[:20],
                cutoff=pair["cutoff_utc"], endpoint=pair["endpoint_utc"],
                hours=pair["hours"], duration_minutes=pair["duration_minutes"],
                source_record_ids=row["source_record_ids"],
                m548_exposure=row["m548_exposure"]))
    if config.events:
        rejected = set(config.events) - {row["event_id"] for row in selected}
        if rejected:
            details = [row for row in exclusions if row["event_id"] in rejected]
            raise ValueError(f"Requested events are unavailable or not test-only: {details}")
    return cases, selected, exclusions


def _authenticate_partition(model, inventory, prepared_directory):
    """Authenticate saved arrays, metadata version and checkpoint test split."""
    source = inventory["m548_split_source"]
    metadata_hash = source["source_files"]["metadata.json"]
    if metadata_hash not in (model.contract.get("cache_metadata_sha256"), COPIED_METADATA_SHA256):
        raise ValueError("Prepared metadata does not match an authenticated M548 benchmark version")
    hashes = {name: _sha256(Path(prepared_directory) / name) for name in FROZEN_SPLIT_SHA256}
    if hashes != FROZEN_SPLIT_SHA256:
        raise ValueError("Prepared split arrays differ from the original M548 benchmark")
    declared = sorted(_test_events(model))
    if not declared:
        raise ValueError("M548 has no saved exclusively held-out event declarations")
    inventory["m548_checkpoint_test_events"] = declared
    inventory["m548_authenticated_split_sha256"] = hashes


def _source_binding(config, selected):
    """Bind all covariates without reading reconstructed fire-outcome rasters."""
    sources = {}
    for row in selected:
        region = Path(config.data_root) / "regions" / row["event_id"]
        for path in sorted(region.rglob("*")):
            if (path.is_file() and path.suffix in (".tif", ".csv", ".json")
                    and path.name not in ("arrival_time_hours.tif", "kriging_std_hours.tif")):
                sources[str(path.relative_to(Path(config.data_root)))] = _sha256(path)
    return sources


def _include_korean_source_audit(inventory):
    """Retain verified coarser reference availability without scoring it."""
    path = WORKSPACE / "documents/korean_observation_availability_20261012.json"
    if not path.exists() or not any(row.get("country") == "KR" for row in inventory["events"]):
        return
    audit = json.loads(path.read_text())
    by_event = {row["event"]: row for row in audit["events"]}
    inventory["other_observation_audit"] = dict(path=str(path), sha256=_sha256(path),
        checked_on_client_date_kst=audit["checked_on_client_date_kst"],
        sources=audit["sources"], pixel_quality_inspected=False,
        scope="Coarser MODIS file availability, not an acquired subdaily reference or a FARSITE fuel substitute")
    for row in inventory["events"]:
        extra = by_event.get(row["event_id"])
        if extra:
            row["coarser_satellite_reference"] = extra["nasa_modis_observation_reference"]
            row["independent_progression_audit"] = extra["independent_aerial_or_field_progression"]
            row["active_fire_observation_audit"] = extra["active_fire_observations"]


def _protocol(config, inventory, cases, selected):
    options = asdict(config)
    for name in ("plan_only", "retry_failed", "progress"):
        options.pop(name)
    implementation = {}
    for name in ("observed_combined.py", "observed_inventory.py", "observed_catalog_data.py",
                 "observed_evaluation.py", "observed_reuse.py", "observed_data.py", "rollout.py", "rollout_cache.py", "api.py", "inference.py",
                 "models.py", "prediction.py", "cumulative.py", "schema.py", "coordinates.py",
                 "cumulative_report.py", "cohort.py", "utils.py", "paths.py",
                 "progress.py",
                 "data.py", "farsite_inputs.py", "farsite_evaluation.py", "farsite_report.py",
                 "farsite_build.py", "farsite_observed_build.py", "metrics.py", "cumulative_evaluation.py",
                 "observed_report_plots.py", "cumulative_report_plots.py"):
        implementation[name] = _sha256(Path(__file__).with_name(name))
    return _safe(dict(schema_version=1, configuration=options, split="test_only",
        checkpoint_sha256=M548_SHA256, archive_sha256=ARCHIVE_SHA256,
        partition_binding=inventory["m548_split_source"],
        checkpoint_test_events=inventory["m548_checkpoint_test_events"],
        authenticated_split_sha256=inventory["m548_authenticated_split_sha256"], cases=cases,
        other_observation_audit=inventory.get("other_observation_audit"),
        input_sha256=_source_binding(config, selected), implementation_sha256=implementation,
        selection_policy="test-only availability and time selection; shortest mode ranks duration/cutoff/endpoint before outcome or saved execution status",
        pooling="equal-weight cell-interval entries concatenated before scoring; no averaging case-level AUC or calibration",
        initial_burn_policy="exclude initial mapped burns from new-burn scoring; include them in total occupancy",
        interval_policy="actual published survey times; hourly M548 transitions plus exact final partial transition",
        reference_policy="NIROPS cumulative component-specific mapped unions; not certified physical negatives",
        n_samples=config.n_samples, threshold=config.threshold, hours="variable actual survey intervals",
        method="matched_observed_test", test_only=True))


def _bind_output(output, protocol):
    path = output / "protocol.json"
    if path.exists():
        if json.loads(path.read_text()) != protocol:
            raise ValueError("Existing run is bound to different settings, sources, or code; choose a new output directory")
    else:
        if output.exists() and any(output.iterdir()):
            raise ValueError("Output must be empty or an authenticated matching combined run")
        output.mkdir(parents=True, exist_ok=True)
        _write_json(path, protocol)


def _write_availability(output, inventory, exclusions):
    _write_json(output / "availability.json", inventory)
    reasons = {row["event_id"]: row["reasons"] for row in exclusions}
    rows = []
    for row in inventory["events"]:
        flat = {}
        for key, value in row.items():
            if key in ("consecutive_intervals", "survey_times_utc",
                       "survey_times_in_cached_window", "matching_evidence", "source_record_ids"):
                continue
            parts = {f"{key}.{name}": item for name, item in value.items()} if isinstance(value, dict) else {key: value}
            for name, item in parts.items():
                flat[name] = json.dumps(_safe(item), ensure_ascii=False) if isinstance(item, (dict, list)) else item
        flat["test_evaluation_exclusions"] = json.dumps(reasons.get(row["event_id"], []))
        rows.append(flat)
    # Country-specific source audits have different fields. Use their union,
    # rather than letting the first event determine the complete CSV schema.
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with (output / "availability.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _read_npz(path):
    with np.load(path, allow_pickle=False) as saved:
        return {key: saved[key].copy() for key in saved.files}


def case_entries(case_dir, case, config):
    """Validate saved counts/uncertainty and recover identical scoring cohorts."""
    reference = _read_npz(case_dir / "reference.npz")
    predictions = [_read_npz(case_dir / name) for name in ("m548_prediction.npz", "farsite_prediction.npz")]
    if (reference["burned_area"].ndim != 4 or reference["burned_area"].shape[:2] != (2, 1)
            or reference["time_utc"][1] - reference["time_utc"][0] != case["duration_minutes"] * 60):
        raise ValueError("Saved reference does not match the exact case interval")
    initial_valid, endpoint_valid = reference["burned_area_valid"][:, 0].astype(bool)
    raw_initial, raw_endpoint = reference["burned_area"][:, 0]
    for state, known in ((raw_initial, initial_valid), (raw_endpoint, endpoint_valid)):
        if np.any(known & (~np.isfinite(state) | ((state != 0) & (state != 1)))):
            raise ValueError("Known mapped reference states must be finite and binary")
    initial, endpoint = (raw_initial == 1) & initial_valid, (raw_endpoint == 1) & endpoint_valid
    if np.any(initial_valid & endpoint_valid & initial & ~endpoint):
        raise ValueError("Cumulative mapped reference must not retreat")
    shape = (1, 1) + initial.shape
    for prediction in predictions:
        for field in ("probability", "burned_probability", "valid"):
            if prediction[field].shape != shape:
                raise ValueError(f"Saved prediction has wrong full-rectangle shape: {field}")
        if prediction["valid"].dtype.kind != "b":
            raise ValueError("Saved prediction validity must be boolean")
        if (int(prediction["time_utc"][0]) != int(reference["time_utc"][0])
                or abs(float(prediction["dt_hours"]) - case["hours"]) > 1e-10):
            raise ValueError("Saved prediction time/horizon disagrees with the case")
        valid = prediction["valid"][0, 0]
        for field in ("probability", "burned_probability"):
            values = prediction[field][0, 0][valid]
            if not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
                raise ValueError("Unavailable or invalid probability on declared saved coverage")
        if (np.any(prediction["probability"][0, 0][valid & initial] != 0)
                or np.any(prediction["burned_probability"][0, 0][valid & initial] != 1)):
            raise ValueError("Initial burns must have zero new-burn and unit total probability")
        if not np.array_equal(prediction["probability"][0, 0][valid & ~initial],
                              prediction["burned_probability"][0, 0][valid & ~initial]):
            raise ValueError("New-burn and total probabilities must agree on initially unburned cells")
    farsite_values = predictions[1]["probability"][predictions[1]["valid"]]
    if (json.loads(str(predictions[1]["metadata_json"])).get("method") != "farsite_deterministic"
            or np.any((farsite_values != 0) & (farsite_values != 1))):
        raise ValueError("FARSITE must retain one deterministic scenario's binary occupancy")
    mixed = predictions[0]
    metadata = json.loads(str(mixed["metadata_json"]))
    expected_seed = case_seed(config.seed, case["event"], case["cutoff"])
    if (metadata.get("method") != "recursive" or metadata.get("n_samples") != config.n_samples
            or metadata.get("trajectory_batch_size") != config.trajectory_batch_size
            or metadata.get("seed") != expected_seed or metadata.get("uncertainty_kind") != "monte_carlo"):
        raise ValueError("M548 must be a recursive Monte Carlo result with the configured sample count and seed")
    valid = mixed["valid"]
    p = mixed["probability"][valid]
    lattice_error = float(np.max(np.abs(p * config.n_samples - np.rint(p * config.n_samples)))) if p.size else 0.
    if lattice_error > 1e-4:
        raise ValueError("M548 probabilities do not equal empirical trajectory counts divided by n_samples")
    if not np.allclose(mixed["mc_standard_error"][valid], np.sqrt(p * (1 - p) / config.n_samples), rtol=1e-5, atol=1e-7):
        raise ValueError("M548 saved Monte Carlo standard errors do not match its trajectory counts")
    for field in ("confidence_lower", "confidence_upper"):
        if (mixed[field].shape != shape or not np.isfinite(mixed[field][valid]).all()
                or np.any((mixed[field][valid] < 0) | (mixed[field][valid] > 1))):
            raise ValueError("M548 Monte Carlo confidence bounds are missing or invalid")
    if (np.any(mixed["confidence_lower"][valid] > p) or np.any(mixed["confidence_upper"][valid] < p)
            or np.any(mixed["rate_valid"]) or not np.isnan(mixed["rate"]).all()):
        raise ValueError("M548 cumulative simulation fields violate their uncertainty/rate contract")
    common = predictions[0]["valid"][0, 0] & predictions[1]["valid"][0, 0]
    entries, counts = {}, {}
    for quantity in ("new_burn", "burned"):
        eligible = initial_valid & endpoint_valid
        if quantity == "new_burn":
            eligible &= ~initial
        target = endpoint if quantity == "burned" else endpoint & ~initial
        counts[quantity] = dict(reference_eligible_cells=int(eligible.sum()),
                               shared_evaluated_cells=int((eligible & common).sum()))
        for index, prediction in enumerate(predictions):
            native = prediction["valid"][0, 0]
            probability = prediction["burned_probability" if quantity == "burned" else "probability"][0, 0]
            for cohort, mask in (("native", native), ("shared_models", common)):
                selected = eligible & mask
                entries[index, cohort, quantity] = dict(y=target[selected].astype(np.uint8), p=probability[selected])
    return entries, counts, dict(method="recursive", n_samples=config.n_samples, seed=expected_seed,
        trajectory_batch_size=config.trajectory_batch_size, count_lattice_max_error=lattice_error,
        empirical_counts_verified=True, mc_standard_error_verified=True,
        update="binary absorbing synchronous transitions; subsequent-hour spread from new burns")


def _case_manifest(case_dir):
    return {name: _sha256(case_dir / name) for name in
            ("report.json", "reference.npz", "m548_prediction.npz", "farsite_prediction.npz")}


def _validate_resume(case_dir, case, config):
    report = json.loads((case_dir / "report.json").read_text())
    protocol = report.get("protocol", {})
    if (report.get("status") != "complete" or protocol.get("event") != case["event"]
            or protocol.get("cutoff") != case["cutoff"] or protocol.get("endpoint") != case["endpoint"]
            or protocol.get("n_samples") != config.n_samples or protocol.get("seed") != config.seed
            or protocol.get("trajectory_batch_size") != config.trajectory_batch_size
            or protocol.get("threshold") != config.threshold):
        raise ValueError("Existing case does not match the configured completed evaluation")
    manifest_path = case_dir / "combined_case_manifest.json"
    if not manifest_path.exists() or json.loads(manifest_path.read_text()) != _case_manifest(case_dir):
        raise ValueError("Existing case outputs do not match their combined-run checksum manifest")


def _reuse_case(sources, case, case_dir):
    """Copy one unique authentic result; differing duplicate exports are errors."""
    from .observed_reuse import MissingStoredCase
    available, unavailable = [], []
    for source in sources:
        try:
            verified = source.validate_case(case)
        except MissingStoredCase as error:
            unavailable.append(f"{source.directory}: {error}")
        else:
            available.append((source, verified))
    if not available:
        raise MissingStoredCase(case["case_id"], "unavailable", "; ".join(unavailable))
    manifest = available[0][1]["manifest"]
    if any(verified["manifest"] != manifest for _, verified in available[1:]):
        raise ValueError(f"Conflicting stored exports for duplicate case {case['case_id']}; no result was selected")
    provenance = available[0][0].copy_case(case, case_dir)
    provenance["matching_sources"] = [source.binding for source, _ in available]
    provenance["duplicate_policy"] = "Count an identical event/cutoff/endpoint once; reject conflicting exports"
    _write_json(case_dir / "reuse_provenance.json", provenance)
    return provenance


def _markdown(report):
    lines = ["# M548 and FARSITE: combined observed-perimeter test evaluation", "",
        f"Status: **{report['status']}**. Completed matched intervals: **{report['completed_case_count']}** "
        f"of **{report['planned_case_count']}**; events represented: **{len(report['completed_events'])}**.", "",
        f"Stored paired results reused: **{report.get('reused_case_count', 0)}**. "
        f"New successful model simulations in this invocation: **{report.get('newly_simulated_case_count', 0)}**. "
        f"Stored-only reporting: **{report.get('report_only', False)}**.", "",
        f"Authenticated stored sources: **{report.get('stored_source_count', 0)}**. "
        f"Identical overlapping cases counted once: **{report.get('duplicate_case_count', 0)}**.", "",
        "Reused exports retain their original implementation and source provenance. "
        "An interrupted source run can contribute completed cases, while failed or missing intervals "
        "remain explicit. Stored-only results describe the available completed subset; they do not "
        "establish completed evaluation of every planned event or interval.", "",
        "Every evaluated event has zero saved M548 training and validation rows and positive test rows. "
        "All availability exclusions and execution failures are retained. This is retrospective test-event evaluation "
        "on component-specific NIROPS mapped extents, not operational validation or certified physical burned area.", "",
        "M548 uses recursive Monte Carlo binary trajectories; all included results pass the configured count-lattice "
        "and standard-error checks. FARSITE uses one fixed moisture scenario and returns deterministic 0/1 occupancy. "
        "Both models use the same cutoff survey union, endpoint, original rectangle, and ordered shared cohort.", "",
        "Intervals have their actual published durations. Pooled scores use equal-weight cell-interval entries, "
        "so larger rectangles and more observed intervals contribute more entries. Repeated cells are correlated; "
        "no independent-observation or metric-confidence-interval claim is made. Case AUCs and calibration errors "
        "are not averaged. Per-event diagnostics and interval durations are exported separately.", "",
        "A negative reference means not mapped inside the cumulative component survey union; NIROPS supplies no "
        "flight-footprint mask certifying unburned cells. Initial burns are excluded from new-burn scoring and included "
        "in total occupancy. Missing environmental coverage remains unavailable.", "",
        "Exact log loss, KL and Bhattacharyya distance retain infinity. Floored scores use epsilon 1e-7. "
        "Unsupported rank/empty-cohort scores are unavailable; zero-denominator classification diagnostics in "
        "nonempty cohorts use the existing scorer's zero convention. Bernoulli distances concern {0,1}, "
        "not geographic transport.", "", "## Combined scores", ""]
    def number(value):
        return "Unavailable" if value is None else f"{value:.10g}" if isinstance(value, float) else str(value)
    for quantity in ("new_burn", "burned"):
        for cohort in ("shared_models", "native"):
            rows = [row for row in report["summary"] if row["quantity"] == quantity and row["cohort"] == cohort]
            if not rows:
                continue
            lines += [f"### {quantity} — {cohort}", "", "| Score | M548 | FARSITE |", "|---|---:|---:|"]
            for section in ("metrics", "classification", "calibration"):
                for key in dict.fromkeys(key for row in rows for key in row[section]):
                    if any(isinstance(row[section].get(key), (dict, list)) for row in rows):
                        continue
                    lines.append(f"| {section}.{key} | " + " | ".join(number(row[section].get(key)) for row in rows) + " |")
            lines += ["", "Fixed calibration bins are exported in calibration.csv and report.json.", ""]
    lines += ["## Failures", ""]
    if report.get("fatal_error"):
        lines += [f"Fatal error: {report['fatal_error']}", ""]
    lines += [f"- {row['event']} {row['cutoff']} → {row['endpoint']}: {row['error']}" for row in report["failures"]] or ["None.", ""]
    lines += ["", "## Figures", ""]
    for stem, figure in report.get("plots", {}).get("figures", {}).items():
        lines += [f"### {stem.replace('_', ' ')}", "", figure["description"], "",
                  f"![{stem}]({figure['outputs']['png']['path']})", "",
                  f"[SVG]({figure['outputs']['svg']['path']})", ""]
    return "\n".join(lines)


def run_combined(config):
    with Activity("Checking test split and observation availability", enabled=config.progress):
        if _sha256(config.checkpoint) != M548_SHA256:
            raise ValueError("Combined comparison requires the original M548 checkpoint")
        model = load_model(config.checkpoint, device="cpu")
        inventory = build_inventory(config.data_root, archive=config.archive,
                                    prepared_directory=config.prepared_directory)
        _authenticate_partition(model, inventory, config.prepared_directory)
        _include_korean_source_audit(inventory)
        cases, selected, exclusions = select_cases(inventory, config)
        if not cases:
            raise ValueError("No observed intervals meet test-only availability and explicit selection")
        protocol = _protocol(config, inventory, cases, selected)
        from .observed_reuse import authenticate_reuse, MissingStoredCase
        directories = (() if config.reuse_results is None else (config.reuse_results,)) + config.additional_reuse_results
        from dataclasses import replace
        reuse_sources = [authenticate_reuse(replace(config, reuse_results=directory,
            additional_reuse_results=()), protocol) for directory in directories]
        if reuse_sources:
            protocol["reuse_source_binding"] = reuse_sources[0].binding
            if len(reuse_sources) > 1:
                protocol["additional_reuse_source_bindings"] = [source.binding for source in reuse_sources[1:]]
    output = Path(config.output_dir).resolve()
    _bind_output(output, protocol)
    _write_availability(output, inventory, exclusions)
    report = dict(status="planned", protocol=protocol, output_dir=str(output), models=[],
        planned_case_count=len(cases), completed_case_count=0, completed_events=[],
        reused_case_count=0, newly_simulated_case_count=0, reused_predictions=[],
        stored_source_count=len(reuse_sources), duplicate_case_count=0, duplicate_cases=[],
        report_only=config.report_only,
        summary=[], per_event=[], failures=[], exclusions=exclusions, monte_carlo_checks=[],
        plot_context=dict(reference_label="NIROPS mapped-perimeter outcome fraction",
            reference_description="binary NIROPS mapped-perimeter outcome",
            interval_label="actual survey intervals", process_label="combined held-out test evaluation"))
    _write_json(output / "report.json", report)
    if config.plan_only:
        (output / "report.md").write_text(_markdown(report))
        print(f"Planned {len(cases)} actual survey intervals on {len(selected)} exclusively held-out events; no models run.", flush=True)
        return report
    observations, engine = None, config.engine

    def prepare_simulation():
        nonlocal observations, engine
        if observations is None:
            from .observed_catalog_data import extract_catalog
            with Activity("Extracting test-event survey polygons", enabled=config.progress):
                observations = extract_catalog(config.archive, selected, config.observations_dir)
        if engine is None:
            from .farsite_observed_build import build_observed_engine
            engine = build_observed_engine()
    writers = {name: _CSV(output / name) for name in
               ("summary.csv", "per_event.csv", "per_cutoff.csv", "calibration.csv", "intervals.csv")}
    (output / "cases").mkdir(exist_ok=True)
    try:
        with ProgressBar(len(cases), "Test survey intervals", enabled=config.progress) as progress, tempfile.TemporaryDirectory(prefix=".pooled-", dir=output) as temporary:
            scratch = Path(temporary)
            stores = {(index, cohort, quantity): _EntryStore(scratch / f"{index}_{cohort}_{quantity}.bin")
                      for index in range(2) for cohort in ("native", "shared_models")
                      for quantity in ("new_burn", "burned")}
            event_stores, coverage = {}, {}
            for position, case in enumerate(cases, 1):
                progress.set_description(f"Test intervals: {case['event']}")
                case_dir = output / "cases" / case["case_id"]
                committing = False
                newly_simulated = False
                try:
                    if case_dir.exists():
                        state_path = case_dir / "report.json"
                        state = json.loads(state_path.read_text()).get("status") if state_path.exists() else "incomplete"
                        if state != "complete":
                            if not config.retry_failed:
                                raise RuntimeError("Existing failed/incomplete case retained; use --retry-failed to retry it")
                            suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                            case_dir.rename(case_dir.with_name(f"{case_dir.name}.failed-{suffix}"))
                        else:
                            _validate_resume(case_dir, case, config)
                    if not case_dir.exists() and reuse_sources:
                        try:
                            _reuse_case(reuse_sources, case, case_dir)
                        except MissingStoredCase:
                            if config.report_only:
                                raise
                    if not case_dir.exists():
                        if config.report_only:
                            raise MissingStoredCase(case["case_id"], "missing", "No authenticated completed stored result is available")
                        prepare_simulation()
                        result = run_observed_evaluation(ObservedEvaluationConfig(
                            observations=observations[case["event"]], event=case["event"],
                            cutoff=case["cutoff"], endpoint=case["endpoint"], hours=case["hours"],
                            checkpoint=config.checkpoint, data_root=config.data_root, output_dir=case_dir,
                            n_samples=config.n_samples, seed=config.seed,
                            trajectory_batch_size=config.trajectory_batch_size, threads=config.threads,
                            threshold=config.threshold, timestep_minutes=config.timestep_minutes,
                            timeout_seconds=config.timeout_seconds, plots=config.case_plots, engine=engine,
                            progress=config.progress), _model=model)
                        if result["status"] != "complete":
                            raise RuntimeError("Case evaluator did not complete")
                        _write_json(case_dir / "combined_case_manifest.json", _case_manifest(case_dir))
                        newly_simulated = True
                    entries, counts, mc = case_entries(case_dir, case, config)
                    case_report = json.loads((case_dir / "report.json").read_text())
                    if not report["models"]:
                        report["models"] = case_report["models"]
                    elif case_report["models"] != report["models"]:
                        raise ValueError("A case uses different model identities; it cannot enter pooled scores")
                    # Finish validation and score calculations before changing
                    # pooled state. A failure during the later commit aborts
                    # the whole run; it must never be labeled an excluded case
                    # whose entries nevertheless enter combined metrics.
                    case_rows = {key: dict(model_id=report["models"][key[0]]["model_id"],
                        event=case["event"], cutoff=case["cutoff"], endpoint=case["endpoint"],
                        hours=case["hours"], cohort=key[1], quantity=key[2],
                        **_pool([part], config.threshold)) for key, part in entries.items()}
                    committing = True
                    report["monte_carlo_checks"].append(dict(event=case["event"], cutoff=case["cutoff"], **mc))
                    for key, part in entries.items():
                        index, cohort, quantity = key
                        stores[key].append(part)
                        event_key = (case["event"],) + key
                        if event_key not in event_stores:
                            event_stores[event_key] = _EntryStore(scratch / f"event_{case['event']}_{index}_{cohort}_{quantity}.bin")
                        event_stores[event_key].append(part)
                        for group in ("ALL", case["event"]):
                            counter = coverage.setdefault((group,) + key,
                                dict(reference_eligible_cells=0, evaluated_cells=0, shared_evaluated_cells=0))
                            counter["reference_eligible_cells"] += counts[quantity]["reference_eligible_cells"]
                            counter["evaluated_cells"] += len(part["y"])
                            counter["shared_evaluated_cells"] += counts[quantity]["shared_evaluated_cells"]
                        writers["per_cutoff.csv"].append(case_rows[key])
                    report["completed_case_count"] += 1
                    provenance_path = case_dir / "reuse_provenance.json"
                    if provenance_path.exists():
                        report["reused_case_count"] += 1
                        provenance = json.loads(provenance_path.read_text())
                        report["reused_predictions"].append(provenance)
                        if len(provenance.get("matching_sources", [])) > 1:
                            report["duplicate_case_count"] += 1
                            report["duplicate_cases"].append(dict(case_id=case["case_id"],
                                event=case["event"], cutoff=case["cutoff"], endpoint=case["endpoint"],
                                sources=provenance["matching_sources"]))
                    if newly_simulated:
                        report["newly_simulated_case_count"] += 1
                    if case["event"] not in report["completed_events"]:
                        report["completed_events"].append(case["event"])
                    writers["intervals.csv"].append(dict(event=case["event"], cutoff=case["cutoff"],
                        endpoint=case["endpoint"], duration_minutes=case["duration_minutes"],
                        error="", status="complete", directory=str(case_dir)))
                except Exception as error:
                    if committing:
                        raise
                    failure = dict(event=case["event"], cutoff=case["cutoff"], endpoint=case["endpoint"],
                        duration_minutes=case["duration_minutes"], error=f"{type(error).__name__}: {error}")
                    report["failures"].append(failure)
                    writers["intervals.csv"].append(dict(failure, status="failed", directory=str(case_dir)))
                report["status"] = "running"
                _write_json(output / "report.json", report)
                progress.update(position, description=f"Test intervals ({report['completed_case_count']} complete, {len(report['failures'])} failed)")
                if not config.progress:
                    print(f"Interval {position}/{len(cases)}: {case['event']}; completed {report['completed_case_count']}, failed {len(report['failures'])}", flush=True)
            progress.close()
            with Activity("Pooling test evaluation metrics", enabled=config.progress):
                for event in (["ALL"] + report["completed_events"] if report["completed_case_count"] else []):
                    for key in stores:
                        index, cohort, quantity = key
                        source = stores[key] if event == "ALL" else event_stores.get((event,) + key)
                        if source is None:
                            continue
                        stats = coverage.get((event,) + key, dict(reference_eligible_cells=0, evaluated_cells=0, shared_evaluated_cells=0))
                        denominator = stats["reference_eligible_cells"]
                        native = coverage.get((event, index, "native", quantity), {}).get("evaluated_cells", 0)
                        row = dict(model_id=report["models"][index]["model_id"], event=event, cohort=cohort,
                            quantity=quantity, hours="actual_intervals", **stats, native_prediction_covered_cells=native,
                            native_coverage_fraction=native / denominator if denominator else None,
                            shared_retention_fraction=stats["shared_evaluated_cells"] / denominator if denominator else None,
                            **_pool([source.entries()], config.threshold))
                        report["summary" if event == "ALL" else "per_event"].append(row)
                        writers["summary.csv" if event == "ALL" else "per_event.csv"].append(row)
                        for bin_row in row["calibration"]["bins"]:
                            writers["calibration.csv"].append(dict(model_id=row["model_id"], event=event,
                                cohort=cohort, quantity=quantity, **bin_row))
            if config.plots and report["completed_case_count"]:
                from .observed_report_plots import generate_observed_report_plots
                with Activity("Generating combined plots", enabled=config.progress):
                    report["plots"] = generate_observed_report_plots(_safe(report), output, stores=stores)
        report["status"] = ("complete" if not report["failures"] else
                            "partial" if report["completed_case_count"] else "failed")
        _write_json(output / "report.json", report)
        (output / "report.md").write_text(_markdown(_safe(report)))
        print(f"Combined report {report['status']}: {output / 'report.md'}", flush=True)
        return report
    except BaseException as error:
        report["status"] = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
        report["fatal_error"] = f"{type(error).__name__}: {error}"
        _write_json(output / "report.json", report)
        (output / "report.md").write_text(_markdown(_safe(report)))
        raise
    finally:
        for writer in writers.values():
            writer.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("data_root", "archive", "prepared_directory", "observations_dir", "checkpoint", "output_dir", "engine"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, default=getattr(CombinedObservedConfig, name))
    parser.add_argument("--reuse-results", type=Path, action="append", default=[],
                        help="Authenticate a saved result directory; repeat to merge sources, counting identical cases once")
    parser.add_argument("--event", action="append", default=[])
    parser.add_argument("--intervals", choices=("all", "first", "shortest"), default="all",
                        help="shortest selects one minimum-duration observed interval per eligible test event (or K with --max-intervals-per-event)")
    parser.add_argument("--hours", type=float, help="Optional exact-duration filter; no endpoint interpolation")
    parser.add_argument("--max-intervals-per-event", type=int)
    parser.add_argument("--max-hours", type=float, help="Keep only observed intervals at most this long; no interpolation")
    for name in ("n_samples", "seed", "trajectory_batch_size", "threads", "timestep_minutes", "timeout_seconds"):
        parser.add_argument("--" + name.replace("_", "-"), type=int, default=getattr(CombinedObservedConfig, name))
    parser.add_argument("--threshold", type=float, default=.5)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--report-only", action="store_true", help="Score and plot authenticated stored cases only; never simulate missing cases")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--case-plots", action="store_true")
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--no-progress", action="store_true", help="Disable progress bars and elapsed-time displays")
    options = vars(parser.parse_args(argv))
    sources = options.pop("reuse_results")
    options["reuse_results"] = sources[0] if sources else None
    options["additional_reuse_results"] = tuple(sources[1:])
    options["events"] = tuple(options.pop("event"))
    options["plots"] = not options.pop("no_plots")
    options["progress"] = not options.pop("no_progress")
    result = run_combined(CombinedObservedConfig(**options))
    if result["status"] in ("failed", "partial"):
        raise SystemExit(1)
    return result


if __name__ == "__main__":
    main()
