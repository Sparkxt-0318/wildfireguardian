"""Compare saved tensor models and patch forests with recursive probabilities.

Run with ``python -m wildfire evaluate-cumulative --hours 6``. Canonical
checkpoint.pt and forest .joblib files in chosen roots define the model set.
Reference endpoints and shared model cohorts are identical across the comparison.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from numbers import Integral
from pathlib import Path
import platform
import shutil
import time

import numpy as np
import torch

from .api import load_model
from .catalog import available_cutoffs, available_events, _timestamp
from .cumulative import _interval_targets
from .cumulative_evaluation import _score
from .data import load_data, select_time
from .metrics import DISTANCE_FIELDS, LOG_LOSS_EPSILON
from .paths import DATA_ROOT, RUNS, WORKSPACE, resolve_recorded_path
from .prediction import _array, _support

DEFAULT_MODELS_ROOT = RUNS / "20261010_categorical_balanced_benchmark"
QUANTITIES = ("new_burn", "burned")
COHORTS = ("shared_models", "native")
INFERENCE_FIELDS = frozenset((
    "burned_area", "burned_area_valid", "features", "feature_valid",
    "channel_names", "pixel_valid", "time_valid", "time_utc",
    "affine_transform", "epsg", "event_id",
))
ENTRY_DTYPE = np.dtype([("y", "u1"), ("p", "<f8")])


@dataclass(frozen=True)
class EvaluationConfig:
    model_roots: tuple[Path, ...] = (DEFAULT_MODELS_ROOT,)
    checkpoints: tuple[Path, ...] = ()
    selection: str = "all"
    data_root: Path = DATA_ROOT
    output_dir: Path | None = None
    hours: int = 6
    n_samples: int = 1024
    seed: int = 0
    trajectory_batch_size: int = 32
    threads: int = 4
    device: str = "cpu"
    split: str = "test"
    events: tuple[str, ...] = ()
    cutoffs: tuple[str, ...] = ()
    stride_hours: int | None = None
    max_cutoffs_per_event: int | None = None
    threshold: float = 0.5
    save_predictions: bool = False
    plots: bool = True
    plan_only: bool = False

    def __post_init__(self):
        for name in ("hours", "n_samples", "trajectory_batch_size", "threads",
                     "stride_hours", "max_cutoffs_per_event"):
            value = getattr(self, name)
            if value is None and name in ("stride_hours", "max_cutoffs_per_event"):
                continue
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < 1:
                raise ValueError(f"{name} must be a positive integer excluding booleans")
        if isinstance(self.seed, (bool, np.bool_)) or not isinstance(self.seed, Integral) or self.seed < 0:
            raise ValueError("seed must be a nonnegative integer excluding booleans")
        if self.selection not in ("all", "best") or self.split not in ("test", "all"):
            raise ValueError("selection must be all/best and split must be test/all")
        if isinstance(self.threshold, (bool, np.bool_)) or not isinstance(self.threshold, (int, float)) or not math.isfinite(self.threshold):
            raise ValueError("threshold must be finite and numeric")
        if self.device not in ("cpu", "cuda", "mps", "auto"):
            raise ValueError("device must be cpu/cuda/mps/auto")
        for name in ("events", "cutoffs"):
            values = getattr(self, name)
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must be distinct")
        if self.cutoffs and self.max_cutoffs_per_event is not None:
            raise ValueError("Choose explicit cutoffs or max_cutoffs_per_event; a prefix limit cannot discard explicit requests")


def _sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _safe(value):
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.ndarray, torch.Tensor)):
        return _safe(_array(value).tolist())
    if isinstance(value, np.generic):
        return _safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return "infinity" if value > 0 else "-infinity" if value < 0 else None
    return value


def _write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(_safe(value), indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    temporary.replace(path)


def discover_checkpoints(roots, explicit=(), selection="all"):
    """Return distinct canonical paths; best mode checks registry content hashes."""
    if selection not in ("all", "best"):
        raise ValueError("selection must be all or best")
    paths = []
    for raw in roots:
        root = resolve_recorded_path(raw).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Model root does not exist: {root}")
        registry = root / "best_models.json"
        if selection == "best" and registry.exists():
            records = json.loads(registry.read_text())
            if not isinstance(records, dict):
                raise ValueError(f"Expected a model mapping in {registry}")
            for record in records.values():
                checkpoint = resolve_recorded_path(record["checkpoint"])
                if not checkpoint.is_absolute():
                    checkpoint = root / checkpoint
                checkpoint = checkpoint.resolve()
                if checkpoint.suffix not in (".pt", ".joblib"):
                    raise ValueError(f"Unsupported registry model format: {checkpoint}")
                expected = record.get("checkpoint_sha256")
                if expected is not None and _sha256(checkpoint) != expected:
                    raise ValueError(f"Registry checkpoint hash differs: {checkpoint}")
                paths.append(checkpoint)
        else:
            canonical = sorted([*root.rglob("checkpoint.pt"), *root.rglob("*.joblib")])
            if selection == 'best' and len(canonical) > 1:
                raise ValueError(f"Best selection requires best_models.json when a root has multiple checkpoints: {root}")
            paths.extend(canonical)
    paths.extend(resolve_recorded_path(path).resolve() for path in explicit)
    result = sorted(set(paths))
    if not result:
        raise ValueError("No tensor checkpoints or forest .joblib files found in the selected scope")
    return result


def case_seed(base, event, cutoff):
    """Stable local seed, independent of model order and case enumeration."""
    payload = json.dumps([int(base), event, cutoff], separators=(",", ":")).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little")


def _contracts(model):
    partition = getattr(model, "_evaluation_partition_contract", None)
    if partition is not None:
        return [partition]
    result = [model.contract]
    for component in getattr(model.predictor, "components", ()):
        result.append(component.contract)
    return result


def _forest_partitions(models, paths, roots):
    """Authenticate a forest's partition through its saved training-cache digest.

    Historical forest payloads retain normalization and a training-cache digest,
    but omit the event partition. A companion tensor contract with the identical
    saved digest and ordered input schema supplies that partition. Relocated
    cache metadata is never rehashed or treated as the historical training file.
    Forest normalization always comes from its own payload.
    """
    witnesses = [(model.contract, path) for model, path in zip(models, paths)
                 if model.contract["architecture"] != "PatchRandomForest"]
    result = {}
    scanned = set()
    schema_keys = ("channels", "categorical_encoding", "categorical_classes")
    def schema_signature(contract):
        channels = contract.get('channels', [])
        encoding = contract.get('categorical_encoding', 'one_hot' if any('=' in name for name in channels) else 'raw')
        return (channels, encoding, contract.get('categorical_classes') if encoding == 'one_hot' else None)

    for model, path in zip(models, paths):
        if model.contract["architecture"] != "PatchRandomForest":
            continue
        contract = model.contract
        metadata = model.predictor.forest.metadata
        digest = metadata.get("cache_metadata_sha256")

        def matches(candidate):
            return (isinstance(digest, str) and bool(digest)
                    and candidate.get("cache_metadata_sha256") == digest
                    and schema_signature(candidate) == schema_signature(contract)
                    and isinstance(candidate.get("splits"), dict) and bool(candidate["splits"]))

        # Check every owning experiment witness, even in best/explicit mode.
        # An unselected checkpoint must not contradict a selected partition.
        owners = [resolve_recorded_path(root).resolve() for root in roots
                  if path.is_relative_to(resolve_recorded_path(root).resolve())]
        if not owners:
            for parent in path.parents:
                if (parent / "best_models.json").is_file() or (parent / "protocol.json").is_file():
                    owners = [parent]
                    break
                if parent == WORKSPACE or parent == parent.parent:
                    break
        for owner in owners:
            if owner in scanned:
                continue
            scanned.add(owner)
            existing = {source for _, source in witnesses}
            for source in sorted(owner.rglob("checkpoint.pt")):
                if source in existing:
                    continue
                saved = torch.load(source, map_location="cpu", weights_only=True)
                candidate = saved.get("contract", {}) if isinstance(saved, dict) else {}
                witnesses.append((candidate, source))
        matching = [(candidate, source) for candidate, source in witnesses if matches(candidate)]
        if matching:
            partition, source = matching[0]
            if any(candidate["splits"] != partition["splits"] for candidate, _ in matching):
                raise ValueError(f"Conflicting saved partitions for forest training-cache digest: {path}")
            model._evaluation_partition_contract = partition
            result[path] = dict(policy="companion_checkpoint_matching_saved_cache_digest_and_schema",
                                source_checkpoint=str(source), source_sha256=_sha256(source),
                                cache_metadata_sha256=digest, matched_schema_fields=list(schema_keys),
                                normalization_source="forest_payload", splits=partition["splits"],
                                split_unit=partition.get("split_unit"))
        else:
            result[path] = dict(policy="unavailable", cache_metadata_sha256=digest,
                                normalization_source="forest_payload",
                                reason="No companion contract matches the saved training-cache digest and ordered schema")
    return result


def _test_events(model):
    sets = []
    for contract in _contracts(model):
        splits = contract.get("splits", {})
        sets.append({event for event, value in splits.items()
                     if value == "test" or isinstance(value, (list, tuple)) and set(value) == {"test"}})
    return set.intersection(*sets)


def _schema(model):
    contract = model.contract
    encoding = contract.get("categorical_encoding", "one_hot" if any("=" in channel for channel in model.channel_names) else "raw")
    return dict(channels=list(model.channel_names), categorical_encoding=encoding,
                categorical_classes=contract.get("categorical_classes") if encoding == "one_hot" else None)


def _load_case(model, event, cutoff, hours, data_root):
    endpoint = (_timestamp(cutoff, "cutoff", require_offset=True) + timedelta(hours=int(hours))).isoformat()
    dataset = load_data(data_root, events=[event], sequence_length=int(hours) + 1,
                        patch_size=None, time_range=(cutoff, endpoint),
                        daily_policy="completed_day", **_schema(model))
    try:
        if len(dataset) != 1:
            raise ValueError("A bounded case must contain exactly one full rectangular sequence")
        sample = dataset[0]
    finally:
        dataset.close()
    if len(sample["time_utc"]) != hours + 1 or not _array(sample["time_valid"]).all():
        raise ValueError(f"Incomplete reference interval: {event} at {cutoff}")
    return sample


def _cases(config, models):
    catalog = available_events(data_root=config.data_root)
    if config.split == "test" and any(not _test_events(model) for model in models):
        raise ValueError("A selected model has no authenticated exclusively held-out event partition; retain its matching companion checkpoint, or use --split all for an explicitly retrospective comparison")
    held_out = set.intersection(*(_test_events(model) for model in models))
    chosen = list(config.events) if config.events else [event for event in catalog if config.split == "all" or event in held_out]
    if not chosen or not set(chosen) <= set(catalog):
        raise ValueError("No available events selected, or an event is absent from the catalog")
    if config.split == "test" and not set(chosen) <= held_out:
        raise ValueError("Selected events are not exclusively held-out test events for every model/component; use --split all for an explicitly retrospective comparison")
    explicit = [_timestamp(value, "cutoff", require_offset=True).isoformat().replace("+00:00", "Z") for value in config.cutoffs]
    if len(set(explicit)) != len(explicit):
        raise ValueError("cutoffs must identify distinct timestamps")
    matched, cases = set(), []
    for event in chosen:
        starts = available_cutoffs(event, data_root=config.data_root, sequence_length=config.hours + 1)
        if explicit:
            selected = [value for value in starts if value in explicit]
            matched.update(selected)
        else:
            selected = starts[::config.stride_hours or config.hours]
        if config.max_cutoffs_per_event is not None:
            selected = selected[:config.max_cutoffs_per_event]
        for cutoff in selected:
            endpoint = (_timestamp(cutoff, "cutoff") + timedelta(hours=int(config.hours))).isoformat().replace("+00:00", "Z")
            cases.append(dict(event=event, cutoff=cutoff, endpoint=endpoint,
                              seed=case_seed(config.seed, event, cutoff)))
    if explicit and matched != set(explicit):
        raise ValueError("Every explicit cutoff must have an exact complete endpoint in at least one selected event")
    if not cases:
        raise ValueError("No complete cutoff/endpoint cases selected")
    return cases, held_out


def _assert_reference_equal(left, right):
    for key in ("event_id", "epsg", "affine_transform", "time_utc", "time_valid", "pixel_valid", "burned_area", "burned_area_valid"):
        if (key in left) != (key in right):
            raise ValueError(f"Models have different reference metadata: {key}")
        if key in left:
            a, b = _array(left[key]), _array(right[key])
            numeric = a.dtype.kind in 'fc' and b.dtype.kind in 'fc'
            if not np.array_equal(a, b, equal_nan=numeric):
                raise ValueError(f"Models have different reference data or geometry: {key}")


def _score_case(prediction, reference, hours, cohort_mask=None, quantity="new_burn", threshold=.5):
    report = prediction.evaluate(reference, hours=hours, quantity=quantity,
                                 threshold=threshold, cohort_mask=cohort_mask)
    forecast = prediction.at(hours=hours)
    shape = tuple(forecast.probability.shape)
    support, _, _ = _support(shape, forecast._pixel_valid, forecast._time_valid)
    start, start_valid, end, end_valid = prediction._aligned_burned_states(reference, hours=hours)
    if quantity == "new_burn":
        target, known = _interval_targets(start, start_valid, end, end_valid)
        known &= start == 0
        probability = forecast.probability
    else:
        target, known, probability = end, end_valid, forecast.burned_probability
    mask = support & known & _array(forecast.valid)
    if cohort_mask is not None:
        mask &= np.broadcast_to(cohort_mask, shape)
    entries = dict(y=np.asarray(target[mask], dtype=np.uint8),
                   p=np.asarray(_array(probability)[mask], dtype=np.float64))
    assert len(entries["y"]) == report["per_horizon"][0]["coverage"]["evaluated_cells"]
    return report, entries


def _pool(parts, threshold):
    """Recompute scores from entries; never average case-level rank metrics."""
    if len(parts) == 1:
        target, probability = parts[0]["y"], parts[0]["p"]
    else:
        target = np.concatenate([part["y"] for part in parts]) if parts else np.empty(0)
        probability = np.concatenate([part["p"] for part in parts]) if parts else np.empty(0)
    metrics, classification, calibration = _score(target, probability, np.ones(len(target)), threshold)
    return dict(metrics=metrics, classification=classification, calibration=calibration)


class _EntryStore:
    """Append selected entries to disk, bounding memory during case simulation."""
    def __init__(self, path):
        self.path, self.count = path, 0

    def append(self, entries):
        if not len(entries["y"]):
            return
        records = np.empty(len(entries["y"]), dtype=ENTRY_DTYPE)
        records["y"], records["p"] = entries["y"], entries["p"]
        with self.path.open("ab") as stream:
            records.tofile(stream)
        self.count += len(records)

    def entries(self, start=0):
        if self.count == start:
            return dict(y=np.empty(0, dtype=np.uint8), p=np.empty(0))
        records = np.memmap(self.path, mode="r", dtype=ENTRY_DTYPE, offset=start * ENTRY_DTYPE.itemsize, shape=(self.count - start,))
        return dict(y=records["y"], p=records["p"])


class _CSV:
    def __init__(self, path):
        self.stream = path.open("w", newline="")
        self.writer = None

    def append(self, row):
        flattened = {}
        for key, value in row.items():
            if isinstance(value, dict):
                flattened.update({f"{key}.{name}": _safe(item) for name, item in value.items()
                                  if name != 'classification_at_0_5'
                                  and not isinstance(item, (dict, list, tuple))})
            elif not isinstance(value, (list, tuple)):
                flattened[key] = _safe(value)
        if self.writer is None:
            self.writer = csv.DictWriter(self.stream, fieldnames=list(flattened))
            self.writer.writeheader()
        self.writer.writerow(flattened)
        self.stream.flush()

    def close(self):
        self.stream.close()


def _markdown(report):
    protocol = report.get("protocol", {})
    lines = [f"# Cumulative wildfire evaluation — {protocol.get('hours', '?')} hours", "",
             f"Status: **{report['status']}**. Models: {len(report.get('models', []))}; cases: {protocol.get('case_count', 0)}.", "",
             f"Simulation budget: {protocol.get('n_samples', '?')} trajectories per model/cutoff; base seed: {protocol.get('seed', '?')}; trajectory block size: {protocol.get('trajectory_batch_size', '?')}. Classification threshold: {protocol.get('threshold', '?')}. Tensor device: {protocol.get('device', '?')}; saved forests run on CPU.", "",
             "Each case retains the original rectangle. The simulation uses unburned exterior padding, initializes missing burned observations as unburned, and repeats cutoff environmental conditions. Missing environmental inputs remain unavailable.", "",
             "Primary scores use the intersection of model validity for each case, followed by original reference masks. New-burn scoring requires a known unburned cutoff and a known endpoint. Total burned occupancy includes initial burns. Pooled scores are recomputed from cell/cutoff entries with equal entry weights; they are not averages of event scores.", "",
             "The event partition is " + str(protocol.get('split', '?')) + "; exclusive held-out status is recorded per model. Thresholds and fitted model parameters are not selected using these results. Pointwise simulation intervals are not confidence intervals for evaluation metrics.", ""]
    if report.get("failures"):
        lines += ["## Failures", "", *[f"- {item.get('path', item.get('case', 'run'))}: {item['error']}" for item in report['failures']], ""]
    def value(item):
        return 'undefined' if item is None else f'{item:.6g}' if isinstance(item, (int, float)) else str(item)

    rows = [row for row in report.get("summary", []) if row["cohort"] == "shared_models" and row["quantity"] == "new_burn"]
    rows.sort(key=lambda row: (math.inf if row['metrics']['brier'] is None else row['metrics']['brier'], row['model_id']))
    if rows:
        lines += ["## Shared-cohort new-burn results", "", "Rows are ordered by pooled Brier score for display; this does not fit or select a model.", "",
                  "| Model | Entries | Positives | Brier | AP | ROC AUC | Exact NLL | F1 | Shared/reference coverage |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for row in rows:
            m, c = row['metrics'], row['classification']
            values = [row['model_id'], m['sample_count'], m['positive_sample_count'], m['brier'], m['average_precision'], m['roc_auc'], m['exact_negative_log_likelihood_mean'], c['f1'], row['shared_retention_fraction']]
            lines.append('| ' + ' | '.join(value(item) for item in values) + ' |')
        lines.append('')
    if report.get('summary'):
        fields = (('bernoulli_kl_divergence_mean', 'Exact KL'),
                  ('floored_bernoulli_kl_divergence_mean', 'Floored KL'),
                  *zip(DISTANCE_FIELDS, ('TV', 'Hellinger', 'JS divergence', 'JS distance',
                                        'Bhattacharyya', 'Wasserstein-1', 'Wasserstein-2')))
        lines += ['## Probability distances', '',
                  'Each row reports the equal-weight mean of a per-cell distance between the observed reference P = (1 − y, y) and prediction Q = (1 − p, p), on binary outcomes {0, 1}. KL is directed from P to Q. Natural logarithms give KL, JS divergence, and Bhattacharyya distance in nats; JS distance is in square-root nats. Wasserstein distances use unit distance between binary outcomes.', '',
                  f'Exact KL equals exact negative log likelihood for binary outcomes. Floored KL clips p to [{LOG_LOSS_EPSILON:g}, 1 − {LOG_LOSS_EPSILON:g}] and is reported separately. TV = Wasserstein-1 = |y − p|; Wasserstein-2 = sqrt(|y − p|). Hellinger = sqrt(1 − sum(sqrt(P Q))); JS divergence = (KL(P || M) + KL(Q || M))/2 with M = (P + Q)/2; JS distance is its per-cell square root; Bhattacharyya = −log(sum(sqrt(P Q))). Square roots are taken before pooling. Infinite and undefined values are preserved.', '',
                  'Shared cohorts allow comparison on identical reference entries across every model. Native cohorts describe each model’s own available entries. New burns exclude initial burns; burned occupancy includes them. These distances measure disagreement with observed outcomes rather than distance between two forecast models or spatial displacement.', '']
        for cohort in COHORTS:
            for quantity in QUANTITIES:
                selected = [row for row in report['summary'] if row['cohort'] == cohort and row['quantity'] == quantity]
                if not selected:
                    continue
                selected.sort(key=lambda row: row['model_id'])
                lines += [f"### {cohort}: {'future new burns' if quantity == 'new_burn' else 'total burned occupancy'}", '',
                          '| Model | Entries | ' + ' | '.join(label for _, label in fields) + ' |',
                          '| --- | ---: | ' + ' | '.join('---:' for _ in fields) + ' |']
                for row in selected:
                    metrics = row['metrics']
                    values = [row['model_id'], metrics['sample_count'], *[metrics.get(key) for key, _ in fields]]
                    lines.append('| ' + ' | '.join(value(item) for item in values) + ' |')
                lines.append('')
    plots = report.get('plots', {})
    if plots.get('figures'):
        lines += ['## Comparison plots', '', plots['display_selection'], '',
                  'Every model appears in the metric, architecture, and coverage overviews. Detailed plots identify their display subset in plots/manifest.json and plots/model_index.csv. Infinite and undefined scores use separate markers; plotted results are descriptive.', '']
        for name, figure in plots['figures'].items():
            png, svg = figure['outputs']['png']['path'], figure['outputs']['svg']['path']
            lines += [f"### {name.replace('_', ' ')}", '', figure['description'], '',
                      f"![{name.replace('_', ' ')}]({png})", '', f"[PNG]({png}) · [SVG]({svg})", '']
    lines += ['## Files', '', '- `report.json`: protocol, checkpoint hashes/contracts, pooled and event results, failures, and plot manifest.', '- `summary.csv`: pooled scores and every probability distance for shared and native cohorts, both probability quantities.', '- `per_event.csv` and `per_cutoff.csv`: corresponding diagnostic scores and distances.', '- `calibration.csv`: pooled/event calibration bins.', '- `protocol.json`: explicit settings and exact case identities.', '- `plots/`: default PNG/SVG figures, model index, and manifest; omit with `--no-plots`.', '- `predictions/`: optional full rectangular prediction arrays (`--save-predictions`).', '', 'Exact losses can be infinite for zero/one Monte Carlo estimates. Separately floored scores retain their explicit interpretation. Bernoulli distances concern binary outcomes at each cell, not geographic transport. This is evaluation of the recorded repeated-current-environment scenario.', '']
    return '\n'.join(lines)


def run_evaluation(config: EvaluationConfig):
    started = time.monotonic()
    output = (Path(config.output_dir) if config.output_dir else WORKSPACE / 'reports' / f"cumulative_{config.hours}h_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}").resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output directory is not empty; preserve existing results: {output}")
    output.mkdir(parents=True, exist_ok=True)
    report = dict(status='running', created_at_utc=datetime.now(timezone.utc).isoformat(), output_dir=str(output),
                  models=[], failures=[], summary=[], per_event=[])
    writers = {}
    context = {}
    try:
        paths = discover_checkpoints(config.model_roots, config.checkpoints, config.selection)
        torch.set_num_threads(int(config.threads))
        models = []
        for path in paths:
            context = dict(path=str(path))
            try:
                with torch.random.fork_rng(devices=[]):
                    model = load_model(path, device='cpu' if path.suffix == '.joblib' else config.device)
                model_id = path.relative_to(RUNS).as_posix() if path.is_relative_to(RUNS) else str(path)
                record = dict(model_id=model_id, path=str(path), sha256=_sha256(path),
                              architecture=model.contract['architecture'], channels=list(model.channel_names),
                              inference_device=str(model.device),
                              contract=model.contract, component_contracts=[c.contract for c in getattr(model.predictor, 'components', ())])
                report['models'].append(record)
                models.append(model)
            except Exception as error:
                report['failures'].append(dict(path=str(path), error=f'{type(error).__name__}: {error}'))
        if report['failures']:
            raise ValueError('Checkpoint preflight failed; no subset comparison was run. See report.json')
        partitions = _forest_partitions(models, paths, config.model_roots)
        for record, path in zip(report['models'], paths):
            if path in partitions:
                record['training_partition_provenance'] = partitions[path]
        cases, held_out = _cases(config, models)
        protocol = dict(hours=int(config.hours), method='recursive', boundary='zero', missing_burned_area='unburned',
                        environment_policy='repeated_current', n_samples=int(config.n_samples), seed=int(config.seed),
                        case_seed_policy='SHA256(base_seed,event,cutoff), same case seed across models',
                        trajectory_batch_size=int(config.trajectory_batch_size), threshold=config.threshold,
                        model_roots=[str(Path(path).resolve()) for path in config.model_roots], selection=config.selection,
                            models=[{key: record[key] for key in ('model_id', 'path', 'sha256', 'architecture', 'channels', 'inference_device')}
                                for record in report['models']],
                        data_root=str(Path(config.data_root).resolve()), data_catalog_sha256=_sha256(Path(config.data_root) / 'events.json'),
                        split=config.split, exclusive_common_test_events=sorted(held_out),
                        stride_hours=config.stride_hours or config.hours, max_cutoffs_per_event=config.max_cutoffs_per_event,
                        cases=cases, case_count=len(cases), model_count=len(models), model_case_count=len(cases) * len(models),
                        full_rectangle=True, patch_size=None, daily_policy='completed_day',
                        reference_policy='original masks, exact cutoff and endpoint; no initial contact restriction',
                        primary_cohort='intersection of every model validity per case, then reference eligibility',
                        native_cohort='model-specific prediction availability with original reference eligibility',
                        aggregation='pooled equal-weight cell/cutoff entries; recompute scores from entries',
                        probability_distance_space='per-cell Bernoulli binary outcomes with unit ground distance',
                        threshold_selection='caller supplied, never fitted here', save_predictions=config.save_predictions,
                        plan_only=config.plan_only, plots=config.plots, device=config.device, threads=config.threads,
                        implementation_sha256={path.name: _sha256(path) for path in
                            (Path(__file__), Path(__file__).with_name('rollout.py'),
                             Path(__file__).with_name('cumulative_evaluation.py'),
                             Path(__file__).with_name('forest_inference.py'),
                             Path(__file__).with_name('cumulative_report_plots.py'))},
                        software=dict(python=platform.python_version(), numpy=np.__version__, torch=torch.__version__))
        for record, model in zip(report['models'], models):
            record['event_split_membership'] = {event: [c.get('splits', {}).get(event) for c in _contracts(model)] for event in dict.fromkeys(case['event'] for case in cases)}
            record['all_selected_events_exclusively_test'] = {case['event'] for case in cases} <= _test_events(model)
        report['protocol'] = protocol
        _write_json(output / 'protocol.json', protocol)
        _write_json(output / 'report.json', report)
        if config.plan_only:
            report['status'] = 'planned'
        else:
            scratch = output / '_entries'
            scratch.mkdir()
            if config.save_predictions:
                (output / 'predictions').mkdir()
            writers = {name: _CSV(output / name) for name in ('summary.csv', 'per_event.csv', 'per_cutoff.csv', 'calibration.csv')}
            stores = {(index, cohort, quantity): _EntryStore(scratch / f'{index}_{cohort}_{quantity}.bin')
                      for index in range(len(models)) for cohort in COHORTS for quantity in QUANTITIES}
            totals = {(i, q): dict(reference_eligible_cells=0, native_prediction_covered_cells=0, shared_evaluated_cells=0)
                      for i in range(len(models)) for q in QUANTITIES}
            event_offsets = None
            event_totals = None

            def aggregate(event=None):
                result_rows = []
                for (i, cohort, quantity), store in stores.items():
                    entries = store.entries(0 if event is None else event_offsets[(i, cohort, quantity)])
                    scores = _pool([entries], config.threshold)
                    counts = (totals if event is None else event_totals)[(i, quantity)]
                    denominator = counts['reference_eligible_cells']
                    row = dict(model_id=report['models'][i]['model_id'], event=event or 'ALL', hours=config.hours,
                               cohort=cohort, quantity=quantity, **counts,
                               native_coverage_fraction=counts['native_prediction_covered_cells'] / denominator if denominator else None,
                               shared_retention_fraction=counts['shared_evaluated_cells'] / denominator if denominator else None, **scores)
                    result_rows.append(row)
                    writers['summary.csv' if event is None else 'per_event.csv'].append(row)
                    for bin_row in scores['calibration']['bins']:
                        writers['calibration.csv'].append(dict(model_id=row['model_id'], event=row['event'], hours=config.hours,
                                                              cohort=cohort, quantity=quantity, **bin_row))
                return result_rows

            for position, case in enumerate(cases):
                context = dict(case=case)
                if position == 0 or cases[position - 1]['event'] != case['event']:
                    event_offsets = {key: store.count for key, store in stores.items()}
                    event_totals = {key: dict.fromkeys(value, 0) for key, value in totals.items()}
                cache, predictions, references = {}, [], []
                for i, model in enumerate(models):
                    context = dict(case=case, path=report['models'][i]['path'], model_id=report['models'][i]['model_id'])
                    schema_key = json.dumps(_schema(model), sort_keys=True)
                    if schema_key not in cache:
                        cache[schema_key] = _load_case(model, case['event'], case['cutoff'], config.hours, config.data_root)
                    reference = cache[schema_key]
                    if references:
                        _assert_reference_equal(references[0], reference)
                    references.append(reference)
                    cutoff = select_time(reference, index=0)
                    inputs = {key: value for key, value in cutoff.items() if key in INFERENCE_FIELDS}
                    prediction = model.predict_cumulative(inputs, hours=[config.hours], method='recursive',
                                                         n_samples=config.n_samples, seed=case['seed'],
                                                         trajectory_batch_size=config.trajectory_batch_size,
                                                         boundary='zero', missing_burned_area='unburned')
                    predictions.append(prediction)
                common = np.logical_and.reduce([_array(p.at(hours=config.hours).valid) for p in predictions])
                shared_targets = {}
                for i, (prediction, reference) in enumerate(zip(predictions, references)):
                    context = dict(case=case, path=report['models'][i]['path'], model_id=report['models'][i]['model_id'])
                    for quantity in QUANTITIES:
                        native, native_entries = _score_case(prediction, reference, config.hours, quantity=quantity, threshold=config.threshold)
                        shared, shared_entries = _score_case(prediction, reference, config.hours, cohort_mask=common, quantity=quantity, threshold=config.threshold)
                        if quantity in shared_targets:
                            assert np.array_equal(shared_targets[quantity], shared_entries['y'])
                        shared_targets[quantity] = shared_entries['y']
                        native_row = native['per_horizon'][0]
                        shared_row = shared['per_horizon'][0]
                        counts = dict(reference_eligible_cells=native_row['coverage']['reference_eligible_cells'],
                                      native_prediction_covered_cells=native_row['coverage']['evaluated_cells'],
                                      shared_evaluated_cells=shared_row['coverage']['evaluated_cells'])
                        for target in (totals[(i, quantity)], event_totals[(i, quantity)]):
                            for key, value in counts.items():
                                target[key] += value
                        for cohort, result, entries in (('native', native, native_entries), ('shared_models', shared, shared_entries)):
                            row = result['per_horizon'][0]
                            stores[(i, cohort, quantity)].append(entries)
                            writers['per_cutoff.csv'].append(dict(model_id=report['models'][i]['model_id'], event=case['event'],
                                                                 cutoff=case['cutoff'], endpoint=case['endpoint'], seed=case['seed'],
                                                                 hours=config.hours, cohort=cohort, quantity=quantity,
                                                                 **counts, coverage=row['coverage'], metrics=row['metrics'], classification=row['classification']))
                if config.save_predictions:
                    selected = [p.at(hours=config.hours) for p in predictions]
                    np.savez_compressed(output / 'predictions' / f'{position:06d}.npz',
                                        probability=np.stack([_array(p.probability) for p in selected]),
                                        burned_probability=np.stack([_array(p.burned_probability) for p in selected]),
                                        valid=np.stack([_array(p.valid) for p in selected]), shared_valid=common,
                                        mc_standard_error=np.stack([_array(p.mc_standard_error) for p in selected]),
                                        confidence_lower=np.stack([_array(p.confidence_lower) for p in selected]),
                                        confidence_upper=np.stack([_array(p.confidence_upper) for p in selected]),
                                        coordinates=selected[0].coordinates if selected[0].coordinates is not None else np.empty((0, 2)),
                                        model_ids=np.asarray([r['model_id'] for r in report['models']]),
                                        case_json=np.asarray(json.dumps(case)), hours=np.asarray(config.hours))
                report['completed_cases'] = position + 1
                _write_json(output / 'progress.json', dict(status='running', completed_cases=position + 1, case_count=len(cases), latest_case=case))
                print(f"Case {position + 1}/{len(cases)}: {case['event']} {case['cutoff']} — {len(models)} models", flush=True)
                if position + 1 == len(cases) or cases[position + 1]['event'] != case['event']:
                    report['per_event'].extend(aggregate(case['event']))
            report['summary'] = aggregate()
            if config.plots:
                from .cumulative_report_plots import generate_report_plots
                context = dict(case='comparison plot generation')
                report['plots'] = generate_report_plots(_safe(report), output, stores=stores)
            shutil.rmtree(scratch)
            report['status'] = 'complete'
        report['elapsed_seconds'] = time.monotonic() - started
        _write_json(output / 'report.json', report)
        (output / 'report.md').write_text(_markdown(_safe(report)))
        _write_json(output / 'progress.json', dict(status=report['status'], completed_cases=report.get('completed_cases', 0), case_count=len(cases)))
        print(f"{report['status'].capitalize()}: {len(models)} models, {len(cases)} cases. Report: {output / 'report.md'}", flush=True)
        return _safe(report)
    except Exception as error:
        report['status'] = 'failed'
        report['elapsed_seconds'] = time.monotonic() - started
        if not report['failures']:
            report['failures'].append(dict(**context, error=f'{type(error).__name__}: {error}'))
        _write_json(output / 'report.json', report)
        (output / 'report.md').write_text(_markdown(_safe(report)))
        _write_json(output / 'progress.json', dict(status='failed', completed_cases=report.get('completed_cases', 0),
                                                  case_count=report.get('protocol', {}).get('case_count', 0),
                                                  failures=report['failures']))
        raise
    finally:
        for writer in writers.values():
            writer.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models-root', type=Path, action='append', help='Experiment root; repeat to include more roots. Default: current categorical benchmark.')
    parser.add_argument('--checkpoint', type=Path, action='append', default=[], help='Explicit tensor .pt or forest .joblib checkpoint; repeat. Without models-root, these replace root discovery.')
    parser.add_argument('--selection', choices=('all', 'best'), default='all', help='All canonical checkpoints, or saved best-model registry entries.')
    parser.add_argument('--data-root', type=Path, default=DATA_ROOT)
    parser.add_argument('--output-dir', type=Path, help='New/empty result directory; default is a fresh timestamped reports directory.')
    parser.add_argument('--hours', type=int, default=6, help='Positive whole-hour cumulative evaluation horizon (default: 6).')
    parser.add_argument('--n-samples', type=int, default=1024)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--trajectory-batch-size', type=int, default=32)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--device', choices=('cpu', 'cuda', 'mps', 'auto'), default='cpu', help='Tensor inference device; saved random forests always run on CPU.')
    parser.add_argument('--split', choices=('test', 'all'), default='test', help='Common exclusively held-out events, or explicit retrospective catalog scope.')
    parser.add_argument('--event', action='append', default=[])
    parser.add_argument('--cutoff', action='append', default=[], help='Exact timestamp with offset; repeat. Complete endpoints are required.')
    parser.add_argument('--stride-hours', type=int, help='Chronological cutoff stride; defaults to the chosen horizon.')
    parser.add_argument('--max-cutoffs-per-event', type=int, help='Optional chronological prefix limit for diagnostic runs.')
    parser.add_argument('--threshold', type=float, default=.5)
    parser.add_argument('--save-predictions', action='store_true')
    parser.add_argument('--no-plots', action='store_true', help='Skip comparison PNG/SVG generation (enabled by default).')
    parser.add_argument('--plan-only', action='store_true', help='Write checkpoint inventory and case plan without simulating.')
    args = parser.parse_args(argv)
    roots = tuple(args.models_root or (() if args.checkpoint else (DEFAULT_MODELS_ROOT,)))
    try:
        config = EvaluationConfig(model_roots=roots, checkpoints=tuple(args.checkpoint), selection=args.selection,
                                  data_root=args.data_root, output_dir=args.output_dir, hours=args.hours,
                                  n_samples=args.n_samples, seed=args.seed, trajectory_batch_size=args.trajectory_batch_size,
                                  threads=args.threads, device=args.device, split=args.split,
                                  events=tuple(args.event), cutoffs=tuple(args.cutoff), stride_hours=args.stride_hours,
                                  max_cutoffs_per_event=args.max_cutoffs_per_event, threshold=args.threshold,
                                  save_predictions=args.save_predictions, plots=not args.no_plots, plan_only=args.plan_only)
        return run_evaluation(config)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f"Evaluation failed: {error}\n")


if __name__ == '__main__':
    main()
