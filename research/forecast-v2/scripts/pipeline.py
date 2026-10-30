"""Track 1B pipeline: samples, development folds, final fits and held-out scoring.

Every command reads the data root (``events.json`` plus aligned rasters in
the ``wildfire.data`` layout), the perimeter states written by
``prepare_perimeters.py`` and the immutable ``SPLIT.json``. Outputs go to
``--work`` (outside git) and small records to ``--run`` (a run directory).

Commands
    samples   cache cutoff environments and interval samples
    fold      fit one variant on a leave-one-year-out development fold
    final     fit one variant on all fit fires for a fixed number of epochs
    heldout   score baselines, c651 (Monte Carlo and mean field) and fitted
              models on the held-out 2024 intervals (run once)
    compare   mean field versus Monte Carlo on 12 cutoffs

Threads are capped at 2 (shared host). See README.md for exact invocations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pickle
import platform
import sys
import time
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "forecast"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402

from wildfire import baselines as B  # noqa: E402
from wildfire.survival import (  # noqa: E402
    PerimeterSample, ages_from_states, biome_balance_factors, consecutive_intervals, evaluate_samples,
    fit_mean_field, fit_normalization, kriging_weight, sample_forecast, step_durations,
)

SPLIT = json.loads((HERE.parents[1] / "SPLIT.json").read_text())
SOURCE_CHANNELS = ["weather.temperature_2m", "weather.wind_eastward_10m", "weather.wind_northward_10m",
                   "terrain.slope_degrees", "vegetation.tree_cover_percent", "biome.biome_class"]
CLASSES = {"biome.biome_class": list(range(1, 15))}
C651 = REPO / "forecast/runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt"
C651_SHA256 = "c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843"
MARGIN = 10
VARIANTS = {
    "base": dict(prior="free", frame="none", d4=False),
    "d4": dict(prior="free", frame="none", d4=True),
    "d4_wind": dict(prior="free", frame="wind", d4=True),
    "ellipse": dict(prior="ellipse", frame="none", d4=False),
    "burnout": dict(prior="free", frame="none", d4=False, residence_hours=6.0),
    "burnout_spotting": dict(prior="free", frame="none", d4=False, residence_hours=6.0, spotting_radius=15),
    "mixed_base": dict(prior="free", frame="none", d4=False, mixed=True),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def host_record() -> dict:
    load = os.getloadavg()
    return dict(python=platform.python_version(), torch=torch.__version__, numpy=np.__version__,
                platform=platform.platform(), cpu_count=os.cpu_count(), torch_threads=torch.get_num_threads(),
                load_average_1_5_15=list(load),
                note="Current execution host; heavy numerical runs share an exclusive advisory lock. Timings are host-specific")


class Environment:
    """Covariates rederived from pinned sources; cache values never establish truth."""

    def __init__(self, data_root: Path, cache: Path, input_sha256=None):
        self.root, self.cache = Path(data_root).resolve(), Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        if input_sha256 is None:
            manifest = self.root.parent / "EXTRACTION_MANIFEST.json"
            expected = json.loads((HERE.parents[1] / "RUN_PROTOCOL.json").read_text())["data_manifest_sha256"]
            if not manifest.exists() or sha256(manifest) != expected:
                raise ValueError("Environmental sources need the frozen input manifest; a cache is not source evidence")
            self._pins = {r["path"]: r["sha256"] for r in json.loads(manifest.read_text())["members"]}
            terrain = self.root.parent / "BASELINE_TERRAIN_MANIFEST.json"
            if terrain.exists():
                if sha256(terrain) != "0e8546d9d4d3bd19ab835e10c3951ef5762ba35eafd25e36e0c369211ad01aa2":
                    raise ValueError("Frozen directional-terrain manifest identity changed")
                self._pins.update({r["path"]: r["sha256"] for r in json.loads(terrain.read_text())["files"]})
        else:
            self._pins = dict(input_sha256)
        self._verified, self._memory = {}, {}
        self._verify_path(self.root / "events.json")
        self.names = tuple(SOURCE_CHANNELS[:-1] + [f"biome.biome_class={c}" for c in CLASSES["biome.biome_class"]])
        self.catalog = {e["id"]: e for e in json.loads((self.root / "events.json").read_text())}
        self._residence = {}
        self._terrain_gradients = {}

    def _verify_path(self, path):
        path = path.resolve()
        if not path.is_relative_to(self.root.parent):
            raise ValueError("Source input escaped its declared root")
        relative = str(path.relative_to(self.root.parent))
        if relative not in self._pins or not path.is_file():
            raise ValueError(f"Required environmental input is absent or unpinned: {relative}")
        stat = path.stat()
        stamp = (stat.st_size, stat.st_mtime_ns)
        if self._verified.get(relative) != stamp:
            if sha256(path) != self._pins[relative]:
                raise ValueError(f"Environmental source identity changed: {relative}")
            self._verified[relative] = stamp

    def _verify_sources(self, event):
        if event not in self.catalog:
            raise ValueError("Unknown event identity")
        paths = list(self.root.iterdir()) + list((self.root / "regions" / event).rglob("*"))
        for path in paths:
            if path.is_file() and path.suffix.lower() in (".tif", ".tiff", ".json", ".csv", ".txt", ".npz"):
                self._verify_path(path)

    def available_at(self, event, hour):
        record = self.catalog[event]
        return pd.Timestamp(record["start_utc"]) <= hour <= pd.Timestamp(record["end_utc"])

    def terrain_gradient(self, event):
        """East/north elevation gradient from the separately hashed baseline supplement."""
        if event not in self._terrain_gradients:
            import rasterio
            path = self.root.parent / "baseline-terrain" / event / "elevation_m_375m.tif"
            self._verify_path(path)
            with rasterio.open(path) as source:
                if not source.crs.is_projected or abs(source.crs.linear_units_factor[1] - 1) > 1e-12:
                    raise ValueError("Directional slope requires a projected grid measured in metres")
                elevation = source.read(1, masked=True).filled(np.nan).astype(float)
                row, col = np.gradient(elevation)
                t = source.transform
                inverse = np.linalg.inv(np.array([[t.a, t.b], [t.d, t.e]]).T)
                east = inverse[0, 0] * col + inverse[0, 1] * row
                north = inverse[1, 0] * col + inverse[1, 1] * row
            self._terrain_gradients[event] = east, north
        return self._terrain_gradients[event]

    def residence(self, event):
        """Point duration from supported FBFM40 cells; declared 6h fallback elsewhere."""
        self._verify_sources(event)
        if event in self._residence:
            return self._residence[event]
        import rasterio
        from wildfire.heat import FlameResidenceTime
        path = self.root / "regions" / event / "fuel/landfire_2016_fbfm40_375m.tif"
        if not path.exists():
            self._residence[event] = None
            return None
        with rasterio.open(path) as source:
            codes = source.read(1, masked=True).filled(0)
        supported = np.isin(codes, list(range(101, 110)) + list(range(121, 125)) + list(range(141, 150))
                            + list(range(161, 166)) + list(range(181, 190)) + list(range(201, 205)))
        duration = np.full(codes.shape, 6.0, dtype=np.float32)
        for code in np.unique(codes[supported]):
            seconds = float(np.asarray(FlameResidenceTime.from_fbfm40(int(code)).duration_s))
            duration[codes == code] = seconds / 3600
        self._residence[event] = duration
        return duration

    def at(self, event: str, hour: pd.Timestamp) -> np.ndarray:
        self._verify_sources(event)
        key = self.cache / f"{event}_{hour.strftime('%Y%m%dT%H')}.npz"
        memory_key = event, hour.isoformat()
        if memory_key in self._memory:
            return self._memory[memory_key].copy()
        from wildfire.data import load_data
        iso = hour.isoformat()
        with load_data(self.root, events=[event], sequence_length=1, patch_size=None, time_range=(iso, iso),
                       include_fire_labels=False, channels=SOURCE_CHANNELS, categorical_classes=CLASSES) as ds:
            if len(ds) != 1:
                raise ValueError(f"Expected one snapshot for {event} at {iso}")
            sample = ds[0]
            names = ds.channel_names
        raw = np.where(sample["feature_valid"][0].numpy(), sample["features"][0].numpy(), np.nan).astype(np.float32)
        if tuple(names) != self.names:
            raise ValueError("Executed source channel schema differs from the fixed model inputs")
        if key.exists():
            with np.load(key, allow_pickle=False) as stored:
                if (tuple(str(n) for n in stored["names"]) != self.names or stored["raw"].dtype != raw.dtype
                        or not np.array_equal(stored["raw"], raw, equal_nan=True)):
                    raise ValueError(f"Cached environmental values differ from verified source recomputation: {key}")
        else:
            np.savez_compressed(key, raw=raw, names=np.array(names))
        self._memory[memory_key] = raw.copy()
        return raw.copy()


def crop_box(*masks: np.ndarray, margin: int = MARGIN):
    union = np.zeros_like(masks[0], dtype=bool)
    for m in masks:
        union |= m.astype(bool)
    h, w = union.shape
    if not union.any():
        return slice(0, h), slice(0, w)
    rows, cols = np.flatnonzero(union.any(1)), np.flatnonzero(union.any(0))
    return (slice(max(0, rows[0] - margin), min(h, rows[-1] + margin + 1)),
            slice(max(0, cols[0] - margin), min(w, cols[-1] + margin + 1)))


def cropped(sample: PerimeterSample) -> PerimeterSample:
    # A future endpoint must not choose the training input domain.
    r, c = crop_box(sample.initial)
    return PerimeterSample(sample.event_id, sample.t1, sample.hours, sample.environment[:, r, c].copy(),
                           sample.initial[r, c].copy(), sample.endpoint[r, c].copy(), sample.score_mask[r, c].copy(),
                           sample.label_weight[r, c].copy(), sample.initial_age_hours[r, c].copy(), sample.kind,
                           sample.weather, dict(sample.meta, crop=[r.start, r.stop, c.start, c.stop]),
                           None if sample.residence_hours is None else sample.residence_hours[r, c].copy())


def perimeter_samples(event: str, perimeters: Path, env: Environment, *, crop: bool,
                      max_intervals: int | None = None) -> list[PerimeterSample]:
    manifest_path = perimeters / "PERIMETER_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    states_path = perimeters / event / "states.npz"
    if sha256(states_path) != manifest["events"][event]["states_sha256"]:
        raise ValueError("Perimeter reference identity differs from its source manifest")
    data = np.load(states_path, allow_pickle=False)
    times = list(pd.to_datetime(data["times"], utc=True))
    states = data["states"].astype(bool)
    result = []
    for i, j, hours in consecutive_intervals(times, 48.0):
        if not env.available_at(event, times[i].floor("h")):
            continue
        raw = env.at(event, times[i].floor("h"))
        initial, endpoint = states[i], states[j]
        age = ages_from_states(times, states.astype(np.uint8), i)
        sample = PerimeterSample(
            event, times[i].isoformat(), hours, raw, initial, endpoint, ~initial,
            np.ones(initial.shape, np.float32), np.nan_to_num(age, nan=0.0).astype(np.float32),
            meta=dict(t2=times[j].isoformat(), interval_index=i,
                      residence_policy="FBFM40 point duration where supported, declared 6h otherwise"),
            residence_hours=env.residence(event))
        result.append(cropped(sample) if crop else sample)
        if max_intervals is not None and len(result) >= max_intervals:
            break
    return result


def kriged_samples(event: str, data_root: Path, env: Environment, *, window: float = 12.0,
                   every: float = 12.0, max_intervals: int | None = None) -> list[PerimeterSample]:
    import rasterio
    if hasattr(env, "_verify_sources"):
        env._verify_sources(event)
    region = data_root / "regions" / event
    with rasterio.open(region / "arrival_time_hours.tif") as src:
        arrival = src.read(1, masked=True).filled(np.nan).astype(np.float64)
    with rasterio.open(region / "kriging_std_hours.tif") as src:
        std = src.read(1, masked=True).filled(np.nan).astype(np.float64)
    events = {e["id"]: e for e in json.loads((data_root / "events.json").read_text())}
    e = events[event]
    t0 = pd.Timestamp(e["t0_utc"])
    start, end = pd.Timestamp(e["start_utc"]), pd.Timestamp(e["end_utc"])
    finite = np.isfinite(arrival)
    if not finite.any():
        return []
    result = []
    for t in np.arange(math.floor(np.nanmin(arrival)), math.ceil(np.nanmax(arrival)), every):
        hour = (t0 + pd.Timedelta(hours=float(t))).floor("h")
        # Initial and endpoint labels use the exact declared cutoff, not the
        # later unfloored proposed time from which this weather hour came.
        t = (hour - t0).total_seconds() / 3600
        if hour < start or hour > end:
            continue
        initial = finite & (arrival <= t)
        endpoint = finite & (arrival <= t + window)
        if not initial.any():
            continue
        age = np.where(initial, t - arrival, 0.0)
        sample = PerimeterSample(event, hour.isoformat(), window, env.at(event, hour), initial, endpoint, finite & ~initial,
                                 kriging_weight(std, window).astype(np.float32), age.astype(np.float32),
                                 kind="kriged", meta=dict(start_hours=float(t)), residence_hours=env.residence(event))
        result.append(cropped(sample))
        if max_intervals is not None and len(result) >= max_intervals:
            break
    return result


def load_or_build(work: Path, name: str, builder):
    path = work / "samples" / f"{name}.pkl"
    # Recompute from authenticated originals even on a cache hit. A cache's
    # self-reported hash or metadata cannot authenticate scientific inputs.
    value = builder()
    identity = sample_list_identity(value)
    if path.exists():
        stored = pickle.loads(path.read_bytes())
        if sample_list_identity(stored) != identity:
            raise ValueError(f"Cached training samples differ from verified source recomputation: {path}")
        result = value
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pickle.dumps(value, protocol=5))
        result = value
    with (work / "cache_authentication.jsonl").open("a") as audit:
        audit.write(json.dumps(dict(cache=str(path), cache_sha256=sha256(path), fresh_sample_identity=identity,
            samples=len(value), status="MATCHES_RECOMPUTED_SOURCES", checked_utc=pd.Timestamp.now(tz="UTC").isoformat())) + "\n")
    return result


def sample_list_identity(samples):
    """Exact values, dtype, shape, ordering and metadata of every sample field."""
    from dataclasses import fields
    digest = hashlib.sha256()
    for sample in samples:
        for field in fields(PerimeterSample):
            value = getattr(sample, field.name, None)
            digest.update(field.name.encode())
            if isinstance(value, np.ndarray):
                value = np.ascontiguousarray(value)
                digest.update(str((value.shape, str(value.dtype))).encode())
                digest.update(value.tobytes())
            else:
                digest.update(json.dumps(value, sort_keys=True, default=lambda v: v.item()).encode())
    return digest.hexdigest()


def build_model(variant: str, train: list[PerimeterSample], names, seed: int, hidden: int):
    from wildfire.models import StructuredKernelModel
    spec = VARIANTS[variant]
    mean, std = fit_normalization(train, names)
    torch.manual_seed(seed)
    model = StructuredKernelModel(len(names), 9, hidden, 0.0, channel_names=names, mean=mean, std=std,
                                  prior=spec["prior"], frame=spec["frame"],
                                  residence_hours=spec.get("residence_hours"),
                                  spotting_radius=spec.get("spotting_radius", 0))
    positives = sum(float((s.endpoint & s.score_mask).sum()) for s in train if s.kind == "perimeter")
    cells = sum(float(s.score_mask.sum()) for s in train if s.kind == "perimeter")
    hours = np.mean([s.hours for s in train if s.kind == "perimeter"])
    # Start near a rate that reproduces the training prevalence for one burned neighbour.
    model.initialize_rate(max(-math.log1p(-min(positives / max(cells, 1), 0.5)) / hours, 1e-4))
    return model


def fit_samples(args, events: list[str], env: Environment, *, mixed: bool) -> list[PerimeterSample]:
    limit = args.max_fit_intervals_per_fire if args.max_fit_intervals_per_fire > 0 else None
    samples = []
    for event in events:
        samples += load_or_build(args.work, f"perimeter_crop_first{args.max_fit_intervals_per_fire}_{event}",
                                 lambda e=event: perimeter_samples(e, args.perimeters, env, crop=True,
                                                 max_intervals=limit))
    if mixed:
        for event in events + SPLIT["fit"]["korean_kriged_only"]:
            if (args.data_root / "regions" / event).exists():
                samples += load_or_build(args.work, f"kriged_utc_v2_first{args.max_fit_intervals_per_fire}_{event}",
                                         lambda e=event: kriged_samples(e, args.data_root, env,
                                                         max_intervals=limit))
    return samples


def available(args, events):
    known = {e["id"] for e in json.loads((args.data_root / "events.json").read_text())}
    return [e for e in events if e in known and (args.perimeters / e / "states.npz").exists()]


def balance_for(train, names):
    channels = {int(n.split("=")[1]): i for i, n in enumerate(names) if n.startswith("biome.biome_class=")}
    counts = {}
    for s in train:
        env = s.environment[:, s.score_mask]
        for code, i in channels.items():
            counts[code] = counts.get(code, 0.0) + float((env[i] == 1).sum())
    counts = {k: v for k, v in counts.items() if v > 0}
    return biome_balance_factors(counts), channels


def command_fold(args):
    torch.set_num_threads(args.threads)
    env = Environment(args.data_root, args.work / "env")
    spec = VARIANTS[args.variant]
    folds = SPLIT["development_folds"]["folds"]
    validation_events = available(args, folds[args.fold])
    train_events = available(args, [e for f, ev in folds.items() if f != args.fold for e in ev])
    train = fit_samples(args, train_events, env, mixed=spec.get("mixed", False))
    validation = fit_samples(args, validation_events, env, mixed=False)
    names = env.names
    model = build_model(args.variant, train, names, args.seed, args.hidden)
    balance, channels = balance_for(train, names) if args.balance else (None, None)
    out = args.run / "folds" / f"{args.variant}_fold{args.fold}_seed{args.seed}{args.artifact_suffix}"
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    log = open(out / "log.jsonl", "w")
    result = fit_mean_field(model, train, validation, epochs=args.epochs, learning_rate=args.lr, seed=args.seed,
                            patience=args.patience, d4=spec["d4"], samples_per_step=args.samples_per_step,
                            balance=balance, biome_channels=channels,
                            intervals_per_epoch=args.intervals_per_epoch or None, validate_each_epoch=False,
                            log=lambda line: (print(line, flush=True), log.write(line + "\n"), log.flush()))
    elapsed = time.perf_counter() - started
    scores = evaluate_samples(model, validation)
    per_fire = {e: evaluate_samples(model, [s for s in validation if s.event_id == e]) for e in validation_events}
    record = dict(variant=args.variant, spec=spec, fold=args.fold, seed=args.seed, hidden=args.hidden,
                  train_events=train_events, validation_events=validation_events,
                  train_samples=len(train), validation_samples=len(validation),
                  validation=scores, validation_per_fire=per_fire, fit=result, fit_seconds=elapsed,
                  parameters=sum(p.numel() for p in model.parameters()), configuration=model.configuration(),
                  smoulder=None if model.smoulder() is None else float(model.smoulder()),
                  host=host_record(), data_root=str(args.data_root), data_manifest_sha256=args.data_manifest_sha256)
    (out / "result.json").write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps(dict(variant=args.variant, fold=args.fold, seed=args.seed, brier=scores["brier"],
                          seconds=elapsed)), flush=True)


def command_final(args):
    torch.set_num_threads(args.threads)
    env = Environment(args.data_root, args.work / "env")
    spec = VARIANTS[args.variant]
    train_events = available(args, SPLIT["fit"]["us_perimeter_and_kriged"])
    train = fit_samples(args, train_events, env, mixed=spec.get("mixed", False))
    names = env.names
    model = build_model(args.variant, train, names, args.seed, args.hidden)
    balance, channels = balance_for(train, names) if args.balance else (None, None)
    out = args.run / "final" / f"{args.variant}_seed{args.seed}"
    out.mkdir(parents=True, exist_ok=True)
    runtime = {}
    fit_input_manifest = None
    intended_kriged_fit_events = None
    if spec.get("mixed", False):
        import audit_fit_coverage as coverage
        expected = coverage.expected_membership(REPO, args.data_root.parent)
        manifest = coverage.capture_sample_manifest(train, regime="mixed",
                    producer_source_sha256=coverage.producer_sources(REPO), input_sha256=expected["input_sha256"])
        manifest_path = out / "input_manifest.json"
        coverage.write_new(manifest_path, manifest)
        fit_input_manifest = dict(path=str(manifest_path.relative_to(REPO)), sha256=sha256(manifest_path))
        intended_kriged_fit_events = expected["intended_kriged_fit_events"]
        runtime = dict(runtime_case_id_fn=coverage.case_id, runtime_object_sha_fn=coverage.object_sha,
                       runtime_sample_manifest_sha256=fit_input_manifest["sha256"])
    started = time.perf_counter()
    result = fit_mean_field(model, train, [], epochs=args.epochs, learning_rate=args.lr, seed=args.seed,
                            d4=spec["d4"], samples_per_step=args.samples_per_step, balance=balance,
                            biome_channels=channels, intervals_per_epoch=args.intervals_per_epoch or None,
                            validate_each_epoch=False, **runtime)
    elapsed = time.perf_counter() - started
    checkpoint = out / "checkpoint.pt"
    torch.save(dict(configuration=model.configuration(), state_dict=model.state_dict(), variant=args.variant,
                    spec=spec, seed=args.seed, epochs=args.epochs, train_events=train_events), checkpoint)
    record = dict(variant=args.variant, seed=args.seed, epochs=args.epochs, fit=result, fit_seconds=elapsed,
                  train_events=train_events, train_samples=len(train), checkpoint_sha256=sha256(checkpoint),
                  parameters=sum(p.numel() for p in model.parameters()), host=host_record(),
                  data_root=str(args.data_root), data_manifest_sha256=args.data_manifest_sha256)
    if fit_input_manifest is not None:
        record.update(fit_input_manifest=fit_input_manifest, intended_kriged_fit_events=intended_kriged_fit_events)
    (out / "result.json").write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps(dict(variant=args.variant, seed=args.seed, checkpoint_sha256=record["checkpoint_sha256"])))


def load_structured(path: Path):
    from wildfire.models import StructuredKernelModel
    saved = torch.load(path, map_location="cpu", weights_only=False)
    cfg = saved["configuration"]
    model = StructuredKernelModel(cfg["in_channels"], cfg["kernel_size"], cfg["hidden_channels"], cfg["dropout"],
                                  channel_names=cfg["channel_names"], prior=cfg["prior"], frame=cfg["frame"],
                                  residence_hours=cfg["residence_hours"], spotting_radius=cfg["spotting_radius"],
                                  wind_adjustment_factor=cfg["wind_adjustment_factor"])
    model.load_state_dict(saved["state_dict"])
    return model.eval()


def c651_monte_carlo(predictor, sample: PerimeterSample, names, n_samples: int, seed: int):
    from wildfire.cumulative_report import case_seed
    from wildfire.rollout import simulate
    env = torch.from_numpy(sample.environment)[None]
    fv = torch.isfinite(env)
    env = torch.where(fv, env, torch.zeros_like(env))
    burned = torch.from_numpy(sample.initial.astype(np.float32))[None, None]
    durations = step_durations(sample.hours)
    outputs = simulate(predictor, burned, env, channel_names=names,
                       burned_area_valid=torch.ones_like(burned, dtype=torch.bool), feature_valid=fv,
                       hours=(float(sum(durations)),), n_samples=n_samples,
                       seed=case_seed(seed, sample.event_id, sample.t1), trajectory_batch_size=32,
                       boundary="zero", missing_burned_area="unburned", step_durations=durations,
                       cache_environment_kernels=True)
    details = outputs[0]["details"]
    return details.probability[0, 0].numpy(), details.valid[0, 0].numpy()


def command_heldout(args):
    """Score every model on the held-out 2024 intervals (full rectangles)."""
    torch.set_num_threads(args.threads)
    from wildfire.api import load_model
    if sha256(C651) != C651_SHA256:
        raise SystemExit("c651 checkpoint hash mismatch")
    env = Environment(args.data_root, args.work / "env")
    events = available(args, SPLIT["held_out"]["us_2024"])
    if args.events:
        events = [e for e in events if e in args.events]
    c651 = load_model(C651, device="cpu")
    fitted = {path.parent.name: load_structured(path) for path in sorted((args.run / "final").glob("*/checkpoint.pt"))}
    logistic = pickle.loads((args.run / "baselines" / "logistic.pkl").read_bytes())
    best_k = json.loads((args.run / "baselines" / "dilation_choice.json").read_text())["best_hours_per_cell"]
    out = args.run / "heldout"
    out.mkdir(parents=True, exist_ok=True)
    (args.run / "report_inputs.json").write_text(json.dumps(dict(
        perimeters=str(args.perimeters), data_root=str(args.data_root),
        data_manifest_sha256=args.data_manifest_sha256, fitted_models=sorted(fitted),
        best_dilation_hours_per_cell=best_k, n_samples=args.n_samples, seed=args.seed), indent=1) + "\n")
    timings = []
    for event in events:
        target = out / f"{event}.npz"
        if target.exists():
            continue
        samples = load_or_build(args.work, f"perimeter_full_{event}",
                                lambda e=event: perimeter_samples(e, args.perimeters, env, crop=False))
        names = env.names
        columns = {k: [] for k in ("interval", "row", "col", "y")}
        predictions: dict[str, list] = {}
        for index, sample in enumerate(samples):
            preds, valids = {}, []
            started = time.perf_counter()
            p, v = c651_monte_carlo(c651.predictor, sample, names, args.n_samples, args.seed)
            timings.append(dict(event=event, interval=index, model="c651_mc", hours=sample.hours,
                                seconds=time.perf_counter() - started, cells=int(p.size)))
            preds["c651_mc"], valids = p, [v]
            started = time.perf_counter()
            with torch.no_grad():
                q, w = sample_forecast(c651.predictor, sample, use_burnout=False, use_spotting=False)
            timings.append(dict(event=event, interval=index, model="c651_meanfield", hours=sample.hours,
                                seconds=time.perf_counter() - started, cells=int(p.size)))
            preds["c651_meanfield"] = q.numpy()
            valids.append(w.numpy())
            for name, model in fitted.items():
                with torch.no_grad():
                    q, w = sample_forecast(model, sample)
                preds[name] = q.numpy()
                valids.append(w.numpy())
            preds["persistence"] = B.persistence(sample.initial)
            for k in B.DILATION_HOURS:
                preds[f"dilation_{k}h"] = B.dilation(sample.initial, sample.hours, k)
            preds["dilation_best"] = preds[f"dilation_{best_k}h"]
            preds["logistic"] = logistic_predict(logistic, sample, names, env.terrain_gradient(event))
            known_env = np.isfinite(sample.environment).all(axis=0)
            mask = (~sample.initial) & known_env & np.logical_and.reduce(valids)
            for name in preds:
                mask &= np.isfinite(preds[name])
            rows, cols = np.nonzero(mask)
            columns["interval"].append(np.full(len(rows), index))
            columns["row"].append(rows)
            columns["col"].append(cols)
            columns["y"].append(sample.endpoint[mask].astype(np.int8))
            for name, value in preds.items():
                predictions.setdefault(name, []).append(value[mask].astype(np.float64))
            print(json.dumps(dict(event=event, interval=index, hours=sample.hours, cells=int(mask.sum()),
                                  positives=int(sample.endpoint[mask].sum()))), flush=True)
        np.savez_compressed(target, **{k: np.concatenate(v) for k, v in columns.items()},
                            **{f"p_{k}": np.concatenate(v) for k, v in predictions.items()},
                            t1=np.array([s.t1 for s in samples]), hours=np.array([s.hours for s in samples]))
    (out / f"timings_{int(time.time())}.json").write_text(json.dumps(dict(host=host_record(), rows=timings)) + "\n")


def logistic_features(sample: PerimeterSample, names, elevation_gradient) -> np.ndarray:
    i = {n: k for k, n in enumerate(names)}
    biome = np.zeros(sample.initial.shape)
    for code in range(1, 15):
        biome = np.where(sample.environment[i[f"biome.biome_class={code}"]] == 1, code, biome)
    if "crop" in sample.meta:
        r0, r1, c0, c1 = sample.meta["crop"]
        elevation_gradient = tuple(g[r0:r1, c0:c1] for g in elevation_gradient)
    return B.hand_features(sample.initial, sample.hours,
                           np.nan_to_num(sample.environment[i["weather.wind_eastward_10m"]]),
                           np.nan_to_num(sample.environment[i["weather.wind_northward_10m"]]),
                           sample.environment[i["terrain.slope_degrees"]], biome, list(range(1, 15)),
                           elevation_gradient=elevation_gradient)


def logistic_predict(fitted, sample, names, elevation_gradient):
    features = logistic_features(sample, names, elevation_gradient)
    finite = np.isfinite(features).all(1)
    probability = np.full(len(features), np.nan)
    probability[finite] = B.predict_logistic(fitted, features[finite])
    return probability.reshape(sample.initial.shape)


def command_baselines(args):
    """Fit the logistic regression and choose the dilation rate on fit fires only."""
    env = Environment(args.data_root, args.work / "env")
    events = available(args, SPLIT["fit"]["us_perimeter_and_kriged"])
    train = fit_samples(args, events, env, mixed=False)
    names = env.names
    rng = np.random.default_rng(args.seed)
    xs, ys = [], []
    dilation_sq = {k: [0.0, 0] for k in B.DILATION_HOURS}
    for sample in train:
        feats = logistic_features(sample, names, env.terrain_gradient(sample.event_id))
        mask = sample.score_mask.ravel()
        mask = mask & np.isfinite(sample.environment).all(axis=0).ravel() & np.isfinite(feats).all(axis=1)
        y = sample.endpoint.ravel()[mask]
        x = feats[mask]
        keep = (y == 1) | (rng.random(len(y)) < args.negative_fraction)
        xs.append(x[keep])
        ys.append(y[keep])
        for k in B.DILATION_HOURS:
            d = B.dilation(sample.initial, sample.hours, k).ravel()[mask]
            dilation_sq[k][0] += float(((d - sample.endpoint.ravel()[mask]) ** 2).sum())
            dilation_sq[k][1] += int(mask.sum())
    x, y = np.concatenate(xs), np.concatenate(ys)
    weights = np.where(y == 1, 1.0, 1.0 / args.negative_fraction)
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler().fit(x, sample_weight=weights)
    model = LogisticRegression(max_iter=3000, random_state=args.seed)
    model.fit(scaler.transform(x), y.astype(int), sample_weight=weights)
    out = args.run / "baselines"
    out.mkdir(parents=True, exist_ok=True)
    (out / "logistic.pkl").write_bytes(pickle.dumps((scaler, model)))
    scores = {k: v[0] / max(v[1], 1) for k, v in dilation_sq.items()}
    choice = B.choose_dilation(scores)
    (out / "dilation_choice.json").write_text(json.dumps(dict(
        training_pooled_brier_cropped=scores, best_hours_per_cell=choice, fit_events=events,
        note="chosen on fit fires only (cropped training rectangles); no held-out data used"), indent=1) + "\n")
    (out / "logistic.json").write_text(json.dumps(dict(
        coefficients=model.coef_.tolist(), intercept=model.intercept_.tolist(), rows=int(len(y)),
        positives=int(y.sum()), negative_fraction=args.negative_fraction, seed=args.seed,
        features=["log1p(distance)", "distance/hours", "alignment", "alignment*speed", "speed", "directional_slope_degrees/45",
                  "log(hours)"] + [f"biome={c}" for c in range(1, 15)],
        weighting="negatives subsampled at the stated fraction and weighted by its inverse"), indent=1) + "\n")
    print(json.dumps(dict(best_dilation=choice, scores=scores)))


COMPARE_HOURS = (1, 3, 6, 12, 24)


def compare_cases(args, env: Environment) -> list[dict]:
    """Twelve label-free cutoffs on fit fires: 6 Korean (kriged state), 6 US (NIROPS state).

    Korean: KFS_02 at the 25/50/75 % arrival quantiles, KFS_03 at 33/67 %,
    KFS_05 at 50 %. US: two fit fires per development year drawn with seed
    20261029, each at its middle survey time whose next interval is <= 48 h.
    Only timestamps and arrival quantiles choose cutoffs (no outcome is read).
    """
    import rasterio
    cases = []
    events = {e["id"]: e for e in json.loads((args.data_root / "events.json").read_text())}
    for event, quantiles in (("KFS_02", (0.25, 0.5, 0.75)), ("KFS_03", (1 / 3, 2 / 3)), ("KFS_05", (0.5,))):
        if event not in events:
            continue
        with rasterio.open(args.data_root / "regions" / event / "arrival_time_hours.tif") as src:
            arrival = src.read(1, masked=True).filled(np.nan).astype(np.float64)
        e = events[event]
        for q in quantiles:
            t = math.floor(float(np.nanquantile(arrival, q)))
            hour = (pd.Timestamp(e["t0_utc"]) + pd.Timedelta(hours=t)).floor("h")
            t = (hour - pd.Timestamp(e["t0_utc"])).total_seconds() / 3600
            initial = np.isfinite(arrival) & (arrival <= t)
            later = {h: np.isfinite(arrival) & (arrival <= t + h) for h in COMPARE_HOURS}
            cases.append(dict(country="KR", event=event, cutoff=hour, initial=initial, labels=later,
                              label_valid=np.isfinite(arrival),
                              label_kind="kriged reconstruction (not observed)"))
    rng = np.random.default_rng(20261029)
    for year, fires in SPLIT["development_folds"]["folds"].items():
        fires = available(args, fires)
        for event in rng.choice(sorted(fires), size=min(2, len(fires)), replace=False):
            data = np.load(args.perimeters / event / "states.npz")
            times = list(pd.to_datetime(data["times"], utc=True))
            intervals = consecutive_intervals(times, 48.0)
            i, j, hours = intervals[len(intervals) // 2]
            states = data["states"].astype(bool)
            cases.append(dict(country="US", event=str(event), cutoff=times[i], initial=states[i],
                              survey_hours=hours, survey_label=states[j], labels={},
                              label_kind="NIROPS mapped extent at the next survey"))
    return cases


def compare_fields(p_mc, p_mf, mask, label=None, label_valid=None):
    """Summarize a declared shared field, retaining empty support as unavailable."""
    a, b = p_mc[mask], p_mf[mask]
    active = np.maximum(a, b) > 1e-3
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Shared comparison support must contain finite probabilities")
    result = dict(status="COMPARABLE" if len(a) else "UNAVAILABLE_SHARED_SUPPORT", cells=int(mask.sum()),
        active_cells=int(active.sum()), rmse_all=float(np.sqrt(np.mean((a - b) ** 2))) if len(a) else None,
        rmse_active=float(np.sqrt(np.mean((a[active] - b[active]) ** 2))) if active.any() else None,
        mean_mc=float(a.mean()) if len(a) else None, mean_mf=float(b.mean()) if len(a) else None,
        expected_new_cells_mc=float(a.sum()) if len(a) else None, expected_new_cells_mf=float(b.sum()) if len(a) else None,
        max_abs_difference=float(np.abs(a - b).max()) if len(a) else None)
    if label is not None:
        supported = mask if label_valid is None else mask & label_valid
        y = label[supported].astype(float)
        if not np.isfinite(y).all() or not np.isin(y, (0, 1)).all():
            raise ValueError("Scored reference labels must be finite and binary")
        result.update(reference_status="SCORED" if len(y) else "UNAVAILABLE_REFERENCE_SUPPORT", label_cells=len(y),
            positives=int(y.sum()) if len(y) else None,
            brier_mc=float(np.mean((p_mc[supported] - y) ** 2)) if len(y) else None,
            brier_mf=float(np.mean((p_mf[supported] - y) ** 2)) if len(y) else None,
            brier_persistence=float(np.mean(y ** 2)) if len(y) else None)
    return result


def command_compare(args):
    """Mean field versus c651 Monte Carlo (1,024 trajectories) on twelve cutoffs."""
    from wildfire.api import load_model
    from wildfire.meanfield import propagate_mean_field
    from wildfire.rollout import simulate
    torch.set_num_threads(args.threads)
    env = Environment(args.data_root, args.work / "env")
    model = load_model(C651, device="cpu")
    out = args.run / "meanfield_vs_mc"
    if args.compare_case_index is not None:
        out = out / f"case_{args.compare_case_index:02d}"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    cases = compare_cases(args, env)
    frozen = json.loads((HERE.parents[1] / "RUN_PROTOCOL.json").read_text())["mean_field_compare"]["cases"]
    if len(cases) != len(frozen):
        raise ValueError("Mean-field comparison must retain all twelve frozen cutoffs")
    for case_index, (case, identity) in enumerate(zip(cases, frozen)):
        if (case["event"] != identity["event"] or case["cutoff"].isoformat() != identity["cutoff"]
                or hashlib.sha256(case["initial"].tobytes()).hexdigest() != identity["initial_sha256"]):
            raise ValueError("Frozen comparison cutoff or initial state changed")
        if args.compare_case_index is not None and case_index != args.compare_case_index:
            continue
        raw = env.at(case["event"], case["cutoff"].floor("h"))
        e = torch.from_numpy(raw)[None]
        fv = torch.isfinite(e)
        e = torch.where(fv, e, torch.zeros_like(e))
        burned = torch.from_numpy(case["initial"].astype(np.float32))[None, None]
        ones = torch.ones_like(burned, dtype=torch.bool)
        horizons = [("fixed", float(h), [1.0] * h) for h in COMPARE_HOURS]
        if case["country"] == "US":
            horizons.append(("survey", case["survey_hours"], step_durations(case["survey_hours"])))
        # One recursive call produces every whole-hour endpoint, avoiding
        # repeated simulation of identical trajectory prefixes.
        started = time.perf_counter()
        mc_joint = model.predict_cumulative(burned, e, channel_names=env.names,
                            burned_area_valid=ones, feature_valid=fv, hours=COMPARE_HOURS,
                            n_samples=args.n_samples, seed=args.seed, trajectory_batch_size=32,
                            boundary="zero", missing_burned_area="unburned")
        mc_joint_seconds = time.perf_counter() - started
        started = time.perf_counter()
        with torch.no_grad():
            mf_joint = propagate_mean_field(model.predictor, burned, e, [1.] * max(COMPARE_HOURS),
                                            channel_names=env.names, p0_valid=ones,
                                            feature_valid=fv, boundary="zero")
        mf_joint_seconds = time.perf_counter() - started
        for kind, hours, durations in horizons:
            if kind == "fixed":
                mc = mc_joint.at(hours=int(hours))
                mf = mf_joint
                mf_index = int(hours) - 1
                mc_seconds, mf_seconds = mc_joint_seconds, mf_joint_seconds
            else:
                started = time.perf_counter()
                mc = simulate(model.predictor, burned, e, channel_names=env.names, burned_area_valid=ones,
                              feature_valid=fv, hours=(float(sum(durations)),), n_samples=args.n_samples,
                              seed=args.seed, trajectory_batch_size=32, boundary="zero",
                              missing_burned_area="unburned", step_durations=durations,
                              cache_environment_kernels=True)[0]["details"]
                mc_seconds = time.perf_counter() - started
                started = time.perf_counter()
                with torch.no_grad():
                    mf = propagate_mean_field(model.predictor, burned, e, durations, channel_names=env.names,
                                              p0_valid=ones, feature_valid=fv, boundary="zero")
                mf_seconds = time.perf_counter() - started
                mf_index = -1
            p_mc, v_mc = mc.probability[0, 0].numpy(), mc.valid[0, 0].numpy()
            p_mf, v_mf = mf.new_burn_probability[mf_index][0, 0].numpy(), mf.valid[mf_index][0, 0].numpy()
            mask = v_mc & v_mf & ~case["initial"]
            if not np.array_equal(v_mc, v_mf):
                raise AssertionError("Mean-field and Monte Carlo validity differ")
            label = case["labels"].get(int(hours)) if kind == "fixed" else case["survey_label"]
            row = dict(country=case["country"], event=case["event"], cutoff=case["cutoff"].isoformat(),
                       horizon_kind=kind, hours=hours,
                       mc_seconds=mc_seconds, mf_seconds=mf_seconds, n_samples=args.n_samples, seed=args.seed,
                       timing_scope="one joint 24h call, shared across five horizon rows" if kind == "fixed" else "one fractional survey-endpoint call")
            row.update(compare_fields(p_mc, p_mf, mask, label, case.get("label_valid")))
            if label is not None:
                row.update(label_kind=case["label_kind"])
            rows.append(row)
            print(json.dumps(row), flush=True)
    pd.DataFrame(rows).to_csv(out / "meanfield_vs_mc.csv", index=False)
    (out / "meanfield_vs_mc.json").write_text(json.dumps(dict(rows=rows, host=host_record(),
                                                              checkpoint_sha256=C651_SHA256), indent=1, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fold", "final", "baselines", "heldout", "compare"])
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--perimeters", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--data-manifest-sha256", default=None)
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="base")
    parser.add_argument("--fold", choices=["2020", "2021", "2022"], default="2022")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--compare-case-index", type=int, choices=range(12), default=None,
                        help="Run one unchanged frozen cutoff, enabling per-cutoff resource leases")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--intervals-per-epoch", type=int, default=160)
    parser.add_argument("--max-fit-intervals-per-fire", type=int, default=3,
                        help="Earliest timestamp-selected development intervals per fire; 0 uses all eligible fit intervals")
    parser.add_argument("--patience", type=int, default=2)
    parser.add_argument("--lr", type=float, default=3e-3)
    parser.add_argument("--hidden", type=int, default=16)
    parser.add_argument("--samples-per-step", type=int, default=4)
    parser.add_argument("--balance", action="store_true")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--n-samples", type=int, default=1024)
    parser.add_argument("--negative-fraction", type=float, default=0.05)
    parser.add_argument("--events", nargs="*", default=None)
    parser.add_argument("--artifact-suffix", default="")
    args = parser.parse_args()
    args.threads = min(args.threads, 2)
    dict(fold=command_fold, final=command_final, baselines=command_baselines, heldout=command_heldout,
         compare=command_compare)[args.command](args)


if __name__ == "__main__":
    main()
