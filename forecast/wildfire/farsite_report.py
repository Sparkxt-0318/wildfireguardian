"""Run authentic FARSITE and evaluate an explicitly timed fixed scenario.

The native simulator receives only the cutoff perimeter and cutoff physical
inputs. Reconstructed future arrivals are loaded separately for evaluation.
One deterministic scenario gives binary occupancy, not calibrated probability.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import math
from numbers import Integral
from pathlib import Path
import re
import shutil
import subprocess
import time

import numpy as np

from .catalog import _timestamp
from .cumulative_report import _CSV, _EntryStore, _safe, _sha256, _write_json
from .data import load_data, select_time
from .farsite_build import REVISION, ROOT, build_engine
from .farsite_evaluation import evaluate_farsite, summarize_farsite
from .farsite_inputs import FuelMoistureScenario, prepare_farsite_inputs
from .metrics import DISTANCE_FIELDS, LOG_LOSS_EPSILON
from .paths import DATA_ROOT, RUNS
from .prediction import _array


@dataclass(frozen=True)
class FarsiteEvaluationConfig:
    event: str = "WY-BTF-002416_FishCreek"
    cutoff: str = "2024-08-21T06:00:00Z"
    hours: int = 6
    data_root: Path = DATA_ROOT
    output_dir: Path | None = None
    engine: Path | None = None
    source_dir: Path | None = None
    moisture: FuelMoistureScenario = field(default_factory=FuelMoistureScenario)
    cloud_cover_percent: float = 0
    utc_offset_hours: float = -7
    boundary_padding: int = 1
    timestep_minutes: int = 15
    distance_resolution_m: float = 30
    perimeter_resolution_m: float = 60
    threshold: float = .5
    timeout_seconds: int = 900
    plots: bool = True
    plan_only: bool = False

    def __post_init__(self):
        for name in ("hours", "boundary_padding", "timestep_minutes", "timeout_seconds"):
            value = getattr(self, name)
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < 1:
                raise ValueError(f"{name} must be a positive integer excluding booleans")
        if (isinstance(self.threshold, (bool, np.bool_)) or not isinstance(self.threshold, (int, float))
                or not math.isfinite(self.threshold) or not 0 <= self.threshold <= 1):
            raise ValueError("threshold must be finite and between zero and one")
        cutoff = _timestamp(self.cutoff, "cutoff", require_offset=True)
        if cutoff.minute or cutoff.second or cutoff.microsecond:
            raise ValueError("cutoff must identify an exact whole UTC hour")
        if (isinstance(self.utc_offset_hours, (bool, np.bool_)) or not isinstance(self.utc_offset_hours, (int, float))
                or not math.isfinite(self.utc_offset_hours) or not float(self.utc_offset_hours).is_integer()):
            raise ValueError("utc_offset_hours must be a whole-hour offset; this native port cannot preserve start minutes")


def _load_reference(config):
    """Load original reference masks only after selecting exact case endpoints."""
    cutoff = _timestamp(config.cutoff, "cutoff", require_offset=True)
    endpoint = cutoff + timedelta(hours=int(config.hours))
    with load_data(config.data_root, events=[config.event], sequence_length=config.hours + 1,
                   channels=["weather.temperature_2m"], patch_size=None,
                   time_range=(cutoff.isoformat(), endpoint.isoformat()),
                   daily_policy="completed_day") as dataset:
        if len(dataset) != 1:
            raise ValueError("The event must contain exactly one complete requested cutoff/endpoint window")
        reference = dataset[0]
    expected = np.arange(int(cutoff.timestamp()), int(endpoint.timestamp()) + 1, 3600)
    if not np.array_equal(_array(reference["time_utc"]), expected) or not _array(reference["time_valid"]).all():
        raise ValueError("The reference must contain every exact UTC hour through the requested endpoint")
    return reference, select_time(reference, index=0)


def read_engine_output(simulation_dir, prepared, hours, *, prefix="outputs/farsite", clock_verification=None):
    """Validate native completion, exact clock, full grid, and arrival units.

    FARSITE may exit zero after input failure. Arrival and timing outputs are
    therefore mandatory. Its no-arrival sentinel means unburned on independently
    known input coverage, while arrivals beyond the endpoint remain future.
    Only the configured exterior buffer is removed, never the data rectangle.
    """
    simulation_dir = Path(simulation_dir)
    arrival_path = simulation_dir / f"{prefix}_ArrivalTime.asc"
    timings_path = simulation_dir / f"{prefix}_Timings.txt"
    for path in (arrival_path, timings_path):
        if not path.is_file():
            raise RuntimeError(f"FARSITE did not produce required output: {path.name}")
    timing = timings_path.read_text()
    verified_minutes = clock_verification is not None
    duration_minutes = 60 * hours
    if verified_minutes:
        start = datetime.fromisoformat(prepared.manifest["clock"]["start_local"])
        end = datetime.fromisoformat(prepared.manifest["clock"]["end_local"])
        if (clock_verification.get("start_hhmm") != start.hour * 100 + start.minute
                or clock_verification.get("end_hhmm") != end.hour * 100 + end.minute
                or not math.isclose(clock_verification.get("duration_minutes", -1), hours * 60, rel_tol=0, abs_tol=1e-6)):
            raise RuntimeError("Independent native clock probe disagrees with exact observed endpoints")
        duration_minutes = clock_verification["duration_minutes"]
    total = re.search(r"Total Sim Time:\s*([0-9.+eE-]+)", timing)
    if total is None or not math.isclose(float(total.group(1)), duration_minutes, rel_tol=0, abs_tol=1e-6):
        raise RuntimeError("FARSITE timing output does not confirm the complete requested duration")
    for label, clock_key in (("Farsite Start Time", "start_local"), ("Farsite End Time", "end_local")):
        local = datetime.fromisoformat(prepared.manifest["clock"][clock_key])
        # This legacy text writer omits the separate minute field. The patched
        # native reader's independent probe supplies it for observed runs.
        displayed_hhmm = local.hour * 100 if verified_minutes else int(local.strftime("%H%M"))
        wanted = (local.month, local.day, displayed_hhmm)
        found = re.search(rf"{label}:\s*(\d+)\s+(\d+)\s+(\d+)", timing)
        if found is None or tuple(map(int, found.groups())) != wanted:
            raise RuntimeError(f"FARSITE timing output has an unexpected {label.lower()}")
    for label, clock_key in (("Simulation Started", "start_local"), ("Simulation Ended", "end_local")):
        local = datetime.fromisoformat(prepared.manifest["clock"][clock_key])
        found = re.search(rf"{label}:\s*(\d+)/(\d+)\s+(\d+):(\d+)", timing)
        wanted = (local.month, local.day, local.hour, 0 if verified_minutes and label == "Simulation Started" else local.minute)
        actual = tuple(map(int, found.groups())) if found is not None else None
        # ConvertSimtimeToActualTime truncates its floating-point minutes, so
        # the printed final clock can be one minute below the exact duration.
        final_display_ok = False
        if verified_minutes and label == "Simulation Ended" and actual is not None:
            try:
                printed = local.replace(month=actual[0], day=actual[1], hour=actual[2], minute=actual[3])
                final_display_ok = abs((printed - local).total_seconds()) <= 60
            except ValueError:
                pass
        if found is None or actual != wanted and not final_display_ok:
            raise RuntimeError(f"FARSITE timing output does not confirm the actual {label.lower()} clock")
    elapsed = re.search(r"Elapsed Time:\s*(\d+)\s+(\d+):(\d+)", timing)
    printed_elapsed = (int(elapsed[1]) * 1440 + int(elapsed[2]) * 60 + int(elapsed[3])) if elapsed else -1
    if elapsed is None or abs(printed_elapsed - duration_minutes) > (1 if verified_minutes else 0):
        raise RuntimeError("FARSITE elapsed simulation clock does not confirm the complete requested duration")
    header = {}
    with arrival_path.open() as stream:
        for _ in range(6):
            parts = stream.readline().split()
            if len(parts) != 2 or parts[0].lower() in header:
                raise ValueError("FARSITE ASCII arrival header must have six distinct key/value rows")
            header[parts[0].lower()] = float(parts[1])
        required = {"ncols", "nrows", "xllcorner", "yllcorner", "cellsize", "nodata_value"}
        if set(header) != required or not all(math.isfinite(value) for value in header.values()):
            raise ValueError("Unexpected or nonfinite FARSITE ASCII arrival header")
        arrival = np.loadtxt(stream, dtype=np.float64, ndmin=2)
    shape = tuple(prepared.manifest["landscape"]["shape"])
    bounds = prepared.manifest["landscape"]["bounds"]
    transform = prepared.manifest["landscape"]["transform"]
    if (arrival.shape != shape or header["nrows"] != shape[0] or header["ncols"] != shape[1]
            or not np.allclose([header["xllcorner"], header["yllcorner"], header["cellsize"]],
                               [bounds[0], bounds[1], transform[0]], rtol=0, atol=1e-6)):
        raise ValueError("FARSITE arrival grid does not match the complete buffered input landscape")
    if header["nodata_value"] != -9999:
        raise ValueError("Unexpected FARSITE no-arrival sentinel; expected -9999")
    if np.any(~np.isfinite(arrival) | ((arrival < 0) & (arrival != -9999))):
        raise ValueError("FARSITE arrivals must be finite nonnegative minutes or the -9999 sentinel")
    padding = prepared.boundary_padding
    original = arrival[padding:-padding, padding:-padding] if padding else arrival.copy()
    if original.shape != tuple(prepared.original_shape):
        raise ValueError("Removing only exterior padding must restore the entire original rectangle")
    return original.copy(), dict(arrival_file=str(arrival_path), arrival_sha256=_sha256(arrival_path),
                                 timings_file=str(timings_path), timings_sha256=_sha256(timings_path),
                                 elapsed_minutes=float(total.group(1)), header=header,
                                 arrival_units="minutes since simulation cutoff",
                                 endpoint_selection=f"0 <= arrival <= {duration_minutes}",
                                 arrived_cells_after_endpoint=int(np.sum(original > duration_minutes)),
                                 native_clock_verification=clock_verification,
                                 legacy_minute_display_tolerance=1 if verified_minutes else 0)


def _engine_record(config):
    engine = Path(config.engine).resolve() if config.engine else (
        Path(config.source_dir or ROOT / "tmp/farsite_source").resolve() / "src/TestFARSITE")
    if not engine.is_file():
        if config.engine:
            raise FileNotFoundError(f"FARSITE engine does not exist: {engine}")
        engine = build_engine(config.source_dir)
    manifest_path = engine.parent.parent / "build_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("A provenance-bound build_manifest.json is required beside the engine source")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("revision") != REVISION or manifest.get("executable_sha256") != _sha256(engine):
        raise ValueError("FARSITE engine differs from its pinned source/build manifest")
    return engine, manifest


def _spatial_plot(output, prediction, reference, config, prepared):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, BoundaryNorm
    selected = prediction.at(hours=config.hours)
    start, start_valid, end, end_valid = prediction._aligned_burned_states(reference, hours=config.hours)
    known = start_valid & end_valid
    panels = [(_array(start), start_valid, "Burned at cutoff"),
              ((end == 1) & (start == 0), known, "Reference new burns"),
              (_array(selected.probability), _array(selected.valid), "FARSITE new burns"),
              (np.where(~known | ~_array(selected.valid), 0,
                        1 + 2 * ((end == 1) & (start == 0)).astype(int)
                        + (_array(selected.probability) == 1).astype(int)), known & _array(selected.valid), "New-burn agreement")]
    fig, axes = plt.subplots(2, 4, figsize=(16, 9), layout="constrained")
    colors = ListedColormap(["#d8d8d8", "#fff9e9", "#d04d36", "#4575b4", "#8645a8"])
    burned = (_array(start) == 1) | (end == 1) | (_array(selected.burned_probability) == 1)
    rows, cols = np.where(np.squeeze(burned))
    if len(rows):
        margin = 5
        zoom = (max(0, cols.min()-margin), min(prepared.original_shape[1], cols.max()+margin+1),
                max(0, rows.min()-margin), min(prepared.original_shape[0], rows.max()+margin+1))
    else:
        zoom = (0, prepared.original_shape[1], 0, prepared.original_shape[0])
    for col, (values, valid, label) in enumerate(panels):
        data = np.squeeze(np.where(valid, values if col == 3 else 1 + values, 0))
        for row in range(2):
            ax = axes[row, col]
            ax.imshow(data, cmap=colors, norm=BoundaryNorm(np.arange(-.5, 5.5), 5), interpolation="nearest")
            ax.set_title(label + (" — entire rectangle" if row == 0 else " — zoom for visibility"), fontsize=10)
            ax.set_xlabel("Original grid column"); ax.set_ylabel("Original grid row")
            if row:
                ax.set_xlim(zoom[0]-.5, zoom[1]-.5); ax.set_ylim(zoom[3]-.5, zoom[2]-.5)
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color=colors(i), label=label) for i, label in enumerate(
        ("Unavailable reference/domain", "Unburned / correct negative", "Burned / false positive",
         "False negative", "True positive"))], loc="outside lower center", ncol=5)
    fig.suptitle(f"{config.event} | {config.hours}-hour deterministic FARSITE scenario\n"
                 f"{prepared.manifest['cutoff_utc']} → {prepared.manifest['endpoint_utc']} | "
                 "375 m grid; original masks; no Monte Carlo intervals", fontsize=13)
    records = {}
    for extension in ("png", "svg"):
        path = output / "plots" / f"farsite_spread_maps.{extension}"
        fig.savefig(path, dpi=160)
        records[extension] = dict(path=path.relative_to(output).as_posix(), sha256=_sha256(path), size_bytes=path.stat().st_size)
    plt.close(fig)
    return dict(description="Entire original rectangle above; labeled zoom below. Reference and simulation masks remain distinct.",
                outputs=records, plotted_ids=["FARSITE-fixed-scenario"])


def _markdown(report):
    protocol = report["protocol"]
    scenario = report["input_manifest"]
    def number(value):
        if value is None: return "undefined"
        if isinstance(value, str): return "∞" if value == "infinity" else value
        return f"{value:.8g}" if isinstance(value, (int, float)) else str(value)
    lines = [f"# FARSITE {protocol['hours']}-hour evaluation", "",
             f"Status: **{report['status']}**. Event: **{protocol['event']}**. "
             f"UTC interval: **{protocol['cutoff']} → {protocol['endpoint']}**.", "",
             "This evaluates one deterministic scenario from the genuine public legacy FARSITE Unix port "
             f"at revision `{REVISION}`. It produces binary scenario occupancy, represented as probabilities 0 or 1; "
             "it does not estimate a calibrated fire probability or provide Monte Carlo intervals. "
             "The current official Windows distribution is a different release.", "",
             "This U.S. case has the physical LANDFIRE inputs needed by FARSITE. "
             "The earlier forest plots use a Korean case; plot style is shared, but scores cannot be ranked across those different cases.", "",
             "## Scenario and support", "",
             f"- Original rectangle: {scenario['original_shape'][0]} × {scenario['original_shape'][1]}, "
             f"EPSG:{scenario['original_epsg']}, 375 m cells. All original cells are retained. "
             f"An exterior buffer of {scenario['boundary_padding_cells']} unburned nonburnable cells is removed only after simulation.",
             "- Observed cumulative burned polygons at the cutoff are assumed to be initial active perimeters. "
             "This is a restart assumption; the data do not identify the active flame front.",
             "- Missing initial burned observations initialize as unburned. The input builder marks missing environmental cells unavailable "
             "and inserts artificial nonburnable barriers. The scored runner requires a complete environmental rectangle "
             "because barriers can affect spread beyond the missing cells. Coverage comes from inputs, never from the arrival sentinel.",
             f"- Fuel moisture scenario (%): `{json.dumps(scenario['fuel_moisture_scenario_percent'], sort_keys=True)}`. "
             "All six values are assumed, not observed. Native dead-fuel conditioning may subsequently evolve them.",
             f"- Cloud cover {scenario['cloud_cover_scenario_percent']}% is assumed. Spotting is disabled (probability zero).",
             "- Weather repeats the spatially summarized cutoff slice. No future weather or evaluation labels enter the engine. "
             "Wind is summarized as a vector and rotated from true north into projected grid north.",
             f"- Native solar/moisture clock uses fixed UTC{scenario['clock']['utc_offset_hours']:+g}, local standard time. "
             "Reported targets and exact endpoints use UTC.",
             "- Physical inputs are LANDFIRE 2016 fuel/canopy rasters aggregated to 375 m, Copernicus GLO-30 DSM terrain "
             "(including vegetation/buildings), and coarse ECMWF IFS weather summarized to a station. "
             "These are retrospective inputs and spatial approximations, not event-date field measurements.",
             "- Reference truth is the project's reconstructed hourly burned-state product with its original masks. "
             "It is not direct observation of every cell or active burning. Native/shared cohorts coincide for this single model.", "",
             "## Scores", "", "Future new burns exclude known initial burns; total burned occupancy includes them. "
             f"Equal-weight cell entries are pooled; classification uses caller threshold {protocol['threshold']:g}. "
             "No threshold is fitted here. Predictions cover the whole rectangle; only cells with the original known reference "
             "state are scored. Simulated burns outside known reference support are excluded, never converted to negative truth.", "",
             "| Quantity | Cohort | Evaluated | Positive truth | Brier | Exact log loss | Floored log loss | Average precision | ROC AUC |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in report["summary"]:
        m = row["metrics"]
        lines.append("| " + " | ".join(number(x) for x in (row["quantity"], row["cohort"],
            row["shared_evaluated_cells"] if row["cohort"] == "shared_models" else row["native_prediction_covered_cells"],
            m.get("positive_sample_count"), m.get("brier"), m.get("exact_negative_log_likelihood_mean"), m.get("clipped_log_loss"),
            m.get("average_precision"), m.get("roc_auc"))) + " |")
    fields = ("bernoulli_kl_divergence_mean", "floored_bernoulli_kl_divergence_mean", *DISTANCE_FIELDS)
    labels = ("Exact KL divergence", "Floored KL divergence", "Total variation distance", "Hellinger distance",
              "Jensen–Shannon divergence", "Jensen–Shannon distance", "Bhattacharyya distance",
              "Wasserstein-1 distance", "Wasserstein-2 distance")
    by_quantity = {row["quantity"]: row for row in report["summary"] if row["cohort"] == "native"}
    lines += ["", "| Quantity | TP | FP | TN | FN | Precision | Recall | F1 | MCC |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for quantity, row in by_quantity.items():
        c = row["classification"]
        lines.append("| " + " | ".join(number(x) for x in (quantity, c["tp"], c["fp"], c["tn"], c["fn"],
                                                           c["precision"], c["recall"], c["f1"], c["mcc"])) + " |")
    lines += ["", "## All nine probability distances", "",
              "Each is computed between the reference Bernoulli point mass and the scenario Bernoulli forecast per cell, "
              "then averaged over eligible entries. KL is D(reference || forecast). Hellinger and Jensen–Shannon distance "
              "are square-rooted per cell before averaging. Wasserstein distances use the binary outcome space {0,1} "
              "with unit ground distance; they are not geographic transport distances.", "",
              "Native and shared cohorts are identical here. Every cohort remains present in the CSV/JSON exports.", "",
              "| Distance | Future new burns | Total burned occupancy |", "|---|---:|---:|"]
    for label, key in zip(labels, fields):
        lines.append(f"| {label} | " + " | ".join(number(by_quantity[quantity]["metrics"].get(key))
                                                     for quantity in ("new_burn", "burned")) + " |")
    lines += ["", f"Exact KL, log loss, and Bhattacharyya distance are infinite when any binary prediction contradicts truth. "
              f"Separate floored values use epsilon={LOG_LOSS_EPSILON:g}; the report preserves both. "
              "Calibration figures summarize binary forecasts and do not establish probability calibration.", "",
              "## Figures", ""]
    for name, figure in report.get("plots", {}).get("figures", {}).items():
        png, svg = figure["outputs"]["png"]["path"], figure["outputs"]["svg"]["path"]
        lines += [f"### {name.replace('_', ' ')}", "", figure["description"], "", f"![{name}]({png})", "", f"[PNG]({png}) · [SVG]({svg})", ""]
    lines += ["## Provenance and files", "", "`report.json` and `protocol.json` retain case settings and source/engine hashes. "
              "`simulation/input_manifest.json` records physical input units, hashes, assumed values, and geometry. "
              "`simulation/outputs/` contains native arrival/perimeter/timing files; `simulation/engine.log` records execution. "
              "`prediction.npz` retains full rectangular probabilities, coverage, arrival minutes, original reference arrays, "
              "and JSON metadata. CSV files retain all distances, classification scores, and calibration bins.", "",
              "Source: [pinned public Unix port](https://github.com/mbedward/farsite/tree/" + REVISION + "). "
              "Official distribution: [USFS FARSITE](https://research.fs.usda.gov/firelab/products/dataandtools/farsite) "
              "and [FlamMap](https://research.fs.usda.gov/firelab/products/dataandtools/flammap).", ""]
    return "\n".join(lines)


def run_farsite_evaluation(config: FarsiteEvaluationConfig):
    started = time.monotonic()
    output = Path(config.output_dir or RUNS / f"farsite_{config.hours}h_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}").resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output directory is not empty; preserve existing results: {output}")
    output.mkdir(parents=True, exist_ok=True)
    report = dict(status="running", created_at_utc=datetime.now(timezone.utc).isoformat(), output_dir=str(output),
                  models=[], summary=[], per_event=[], failures=[])
    writers = {}
    try:
        reference, cutoff_sample = _load_reference(config)
        engine, engine_manifest = _engine_record(config)
        prepared = prepare_farsite_inputs(config.event, config.cutoff, config.hours, output / "simulation",
            data_root=config.data_root, moisture=config.moisture, cloud_cover_percent=config.cloud_cover_percent,
            utc_offset_hours=config.utc_offset_hours, boundary_padding=config.boundary_padding,
            timestep_minutes=config.timestep_minutes, distance_resolution_m=config.distance_resolution_m,
            perimeter_resolution_m=config.perimeter_resolution_m)
        original = np.squeeze(_array(cutoff_sample["burned_area"]))
        known = np.squeeze(_array(cutoff_sample["burned_area_valid"]))
        if (original.shape != prepared.original_shape or not np.array_equal(known, prepared.initial_burned_valid)
                or not np.array_equal(known & (original == 1), prepared.initial_burned.astype(bool))
                or not np.allclose(_array(cutoff_sample["affine_transform"]), tuple(prepared.transform)[:6], rtol=0, atol=1e-6)
                or int(_array(cutoff_sample["epsg"])) != prepared.epsg):
            raise ValueError("Native inputs and reference disagree on original geometry or cutoff burned state")
        # For missing physical inputs, barriers can change distant spread. Do not
        # claim unaffected predictive coverage without a domain-dependence bound.
        if not prepared.environment_valid.all():
            raise ValueError("This evaluator requires complete physical environmental coverage of the original rectangle; "
                             "artificial interior barriers can alter spread beyond the missing cells")
        protocol = dict(method="deterministic_farsite", hours=int(config.hours), event=config.event,
            cutoff=prepared.manifest["cutoff_utc"], endpoint=prepared.manifest["endpoint_utc"],
            threshold=config.threshold, split="explicit_retrospective_case", scenario_count=1,
            full_rectangle=True, uncertainty="No Monte Carlo intervals or probability calibration",
            reference_policy="original reconstructed truth masks and exact UTC endpoint",
            aggregation="pooled equal-weight eligible cell entries", primary_cohort="single-model native/shared identical",
            data_root=str(Path(config.data_root).resolve()), plots=config.plots, plan_only=config.plan_only,
            engine=engine_manifest, implementation_sha256={name: _sha256(Path(__file__).with_name(name)) for name in
                ("farsite_report.py", "farsite_inputs.py", "farsite_evaluation.py", "farsite_build.py",
                 "cumulative_report.py", "cumulative_report_plots.py", "cumulative_evaluation.py", "metrics.py")})
        report.update(protocol=protocol, input_manifest=prepared.manifest)
        record = dict(model_id="FARSITE-fixed-scenario", architecture="FARSITE", path=str(engine),
                      sha256=engine_manifest["executable_sha256"], contract=dict(architecture="FARSITE", revision=REVISION))
        report["models"] = [record]
        _write_json(output / "protocol.json", protocol)
        _write_json(output / "engine_build_manifest.json", engine_manifest)
        if config.plan_only:
            report["status"] = "planned"
        else:
            simulation = output / "simulation"
            (simulation / "outputs").mkdir()
            (simulation / "command.txt").write_text("landscape.lcp scenario.input ignition.shp 0 outputs/farsite 1\n")
            with (simulation / "engine.log").open("w") as log:
                process = subprocess.run([str(engine), "command.txt"], cwd=simulation,
                    stdout=log, stderr=subprocess.STDOUT, timeout=config.timeout_seconds, check=False)
            if process.returncode != 0:
                raise RuntimeError(f"FARSITE exited with status {process.returncode}; inspect simulation/engine.log")
            log_text = (simulation / "engine.log").read_text(errors="replace")
            if re.search(r"(?im)^\s*(?:error\b|.*LaunchFarsite failure)", log_text):
                raise RuntimeError("FARSITE reported an execution/input error; inspect simulation/engine.log")
            arrival, execution = read_engine_output(simulation, prepared, config.hours)
            report["execution"] = execution
            prediction, scores = evaluate_farsite(arrival, cutoff_sample, reference, hours=[config.hours],
                arrival_origin_time_utc=config.cutoff, no_burn_value=-9999, coverage=prepared.environment_valid,
                threshold=config.threshold, metadata=dict(engine_revision=REVISION,
                    scenario_manifest="simulation/input_manifest.json", scenario=prepared.manifest["scenario_kind"]))
            rows, entries = summarize_farsite(prediction, reference, hours=config.hours, model_id=record["model_id"], threshold=config.threshold)
            report["summary"] = rows
            report["per_event"] = [dict(row, event=config.event) for row in rows]
            report["per_cutoff"] = [dict(row, event=config.event, cutoff=protocol["cutoff"], endpoint=protocol["endpoint"]) for row in rows]
            report["evaluation"] = scores
            selected = prediction.at(hours=config.hours)
            report["scenario_counts"] = dict(initial_burned_cells=int(prepared.initial_burned.sum()),
                predicted_new_burned_cells=int(np.nansum(_array(selected.probability))),
                predicted_total_burned_cells=int(np.nansum(_array(selected.burned_probability))),
                environment_covered_cells=int(prepared.environment_valid.sum()))
            exported = selected.numpy()
            exported.update(arrival_time_minutes=arrival, reference_burned_area=_array(reference["burned_area"]).copy(),
                            reference_burned_area_valid=_array(reference["burned_area_valid"]).copy(),
                            reference_time_utc=_array(reference["time_utc"]).copy())
            np.savez_compressed(output / "prediction.npz", **exported)
            writers = {name: _CSV(output / name) for name in ("summary.csv", "per_event.csv", "per_cutoff.csv", "calibration.csv")}
            for key in ("summary", "per_event", "per_cutoff"):
                for row in report[key]: writers[f"{key}.csv"].append(row)
            for row in rows:
                for item in row["calibration"].get("bins", []):
                    writers["calibration.csv"].append(dict(model_id=row["model_id"], cohort=row["cohort"], quantity=row["quantity"], **item))
            if config.plots:
                from .cumulative_report_plots import generate_report_plots
                scratch = output / "_entries"
                scratch.mkdir()
                stores = {}
                for (cohort, quantity), values in entries.items():
                    store = _EntryStore(scratch / f"{cohort}_{quantity}.bin")
                    store.append(values)
                    stores[0, cohort, quantity] = store
                report["plots"] = generate_report_plots(_safe(report), output, stores=stores)
                report["plots"]["figures"]["farsite_spread_maps"] = _spatial_plot(output, prediction, reference, config, prepared)
                _write_json(output / "plots/manifest.json", report["plots"])
                shutil.rmtree(scratch)
            report["status"] = "complete"
        report["elapsed_seconds"] = time.monotonic() - started
        _write_json(output / "report.json", report)
        if report["status"] == "complete": (output / "report.md").write_text(_markdown(_safe(report)))
        return report
    except Exception as error:
        report["status"] = "failed"
        report["failures"].append(dict(error=f"{type(error).__name__}: {error}"))
        report["elapsed_seconds"] = time.monotonic() - started
        _write_json(output / "report.json", report)
        raise
    finally:
        for writer in writers.values(): writer.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", default=FarsiteEvaluationConfig.event)
    parser.add_argument("--cutoff", default=FarsiteEvaluationConfig.cutoff)
    parser.add_argument("--hours", type=int, default=6, help="Explicit positive whole-hour evaluation duration")
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--engine", type=Path)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--cloud-cover-percent", type=float, default=0)
    parser.add_argument("--utc-offset-hours", type=float, default=-7)
    parser.add_argument("--boundary-padding", type=int, default=1)
    parser.add_argument("--timestep-minutes", type=int, default=15)
    parser.add_argument("--distance-resolution-m", type=float, default=30)
    parser.add_argument("--perimeter-resolution-m", type=float, default=60)
    parser.add_argument("--threshold", type=float, default=.5)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    for key in FuelMoistureScenario.__dataclass_fields__:
        parser.add_argument("--" + key.replace("_", "-"), type=int, default=getattr(FuelMoistureScenario(), key))
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--plan-only", action="store_true", help="Prepare inputs and protocol without simulator execution or scores")
    options = vars(parser.parse_args(argv))
    moisture = FuelMoistureScenario(**{key: options.pop(key) for key in FuelMoistureScenario.__dataclass_fields__})
    options["plots"] = not options.pop("no_plots")
    result = run_farsite_evaluation(FarsiteEvaluationConfig(**options, moisture=moisture))
    print(f"FARSITE evaluation {result['status']}: {result['output_dir']}")
    return result


if __name__ == "__main__":
    main()
