"""Interval-censored survival training on mapped perimeters and kriged labels.

A perimeter survey pair says that a cell outside the initial mapped extent at
``t1`` was inside the mapped extent by ``t2``, not when it ignited. Under the
hazard model the probability of that event is the survival product over the
interval, which the mean field evaluates step by step:

    P(burned by t2 | state at t1) = 1 - prod_k exp(-dt_k * lambda_k),

for a single fixed source exactly, and in the mean-field approximation for
spreading fires. Training minimizes the endpoint Brier score of the mean-field
``p_{t2}`` against the mapped endpoint on initially unburned known cells; the
clipped negative log likelihood is reported as a diagnostic.

Mixed regime: the Zenodo arrival-time reconstruction gives windows
``(t, t + L]`` with initial state ``arrival <= t`` and label
``arrival <= t + L``; each cell's weight is down-weighted by its kriging
standard deviation, ``w = 1 / (1 + (sd / L)^2)``, so a label whose timing is
uncertain compared with the window counts less.

All tensors here are ``float32`` or ``float64`` torch tensors; no data are
read at import. Perimeter rasterization reuses the cell-centre rule of
``observed_evaluation.survey_reference``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np
import torch
from torch import Tensor

from .meanfield import propagate_mean_field

LOG_FLOOR = 1e-7

__all__ = [
    "PerimeterSample", "step_durations", "survey_states", "consecutive_intervals",
    "ages_from_states", "kriging_weight", "kriged_windows", "endpoint_brier", "clipped_nll",
    "sample_forecast", "biome_balance_factors",
]


def step_durations(hours: float) -> list[float]:
    """Whole hourly steps then one exact fractional step (the rollout's private rule)."""
    if not math.isfinite(hours) or hours <= 0:
        raise ValueError("hours must be finite and positive")
    whole = int(math.floor(hours + 1e-12))
    durations = [1.0] * whole
    remainder = hours - whole
    if remainder > 1e-9:
        durations.append(remainder)
    return durations


def survey_states(features: Sequence[dict], grid: dict) -> tuple[list, np.ndarray]:
    """Cumulative mapped extent at every distinct survey time on an event grid.

    Returns ``(times, states[S, H, W] uint8)``; the state at time t is the union
    of all polygons with acquisition time <= t, rasterized at cell centres
    (``all_touched=False``) after projecting to the grid CRS, exactly as in
    ``observed_evaluation.survey_reference``.
    """
    import pandas as pd
    from affine import Affine
    from pyproj import Transformer
    from rasterio.features import rasterize
    from shapely.geometry import shape
    from shapely.ops import transform as project_geometry, unary_union

    projection = Transformer.from_crs(4326, int(grid["epsg"]), always_xy=True).transform
    by_time: dict = {}
    for feature in features:
        timestamp = pd.Timestamp(feature["properties"]["time_utc"]).tz_convert("UTC")
        by_time.setdefault(timestamp, []).append(project_geometry(projection, shape(feature["geometry"])))
    times = sorted(by_time)
    transform = Affine(*grid["transform"])
    height, width = int(grid["height"]), int(grid["width"])
    states = np.zeros((len(times), height, width), dtype=np.uint8)
    previous = np.zeros((height, width), dtype=np.uint8)
    for index, time in enumerate(times):
        # A cell centre lies in the union of all polygons up to t exactly when it
        # lies in the union up to the previous time or in one of this time's
        # polygons, so the cumulative raster is built incrementally.
        union = unary_union(by_time[time])
        current = rasterize([(union, 1)], out_shape=(height, width), transform=transform,
                            fill=0, all_touched=False, dtype="uint8")
        previous = np.maximum(previous, current)
        states[index] = previous
    if np.any(states[:-1] > states[1:]):
        raise ValueError("Cumulative survey unions must be absorbing")
    return times, states


def consecutive_intervals(times: Sequence, max_hours: float = 48.0) -> list[tuple[int, int, float]]:
    """Label-free interval rule of SPLIT.json: consecutive times, 0 < duration <= max_hours."""
    result = []
    for i in range(len(times) - 1):
        hours = (times[i + 1] - times[i]).total_seconds() / 3600
        if 0 < hours <= max_hours + 1e-9:
            result.append((i, i + 1, hours))
    return result


def ages_from_states(times: Sequence, states: np.ndarray, index: int) -> np.ndarray:
    """Age (hours) at survey ``index`` of every mapped cell, from its first appearance.

    A cell first mapped at survey j > 0 is assigned the midpoint of
    (t_{j-1}, t_j] as ignition time; cells in the first survey get age zero
    at that survey (no earlier information). Unmapped cells get NaN.
    """
    now = times[index]
    age = np.full(states.shape[1:], np.nan, dtype=np.float64)
    for j in range(index + 1):
        new = states[j].astype(bool) if j == 0 else (states[j] > states[j - 1])
        if j == 0:
            ignition = times[0]
            value = (now - ignition).total_seconds() / 3600
        else:
            midpoint = times[j - 1] + (times[j] - times[j - 1]) / 2
            value = (now - midpoint).total_seconds() / 3600
        age[new & np.isnan(age)] = value
    return age


def kriging_weight(sd_hours: np.ndarray, window_hours: float) -> np.ndarray:
    """Down-weight timing uncertainty; missing SD gives zero weight, not certainty."""
    if not math.isfinite(window_hours) or window_hours <= 0:
        raise ValueError("window_hours must be finite and positive")
    if np.any(np.isfinite(sd_hours) & (sd_hours < 0)):
        raise ValueError("kriging SD must be nonnegative")
    known = np.isfinite(sd_hours)
    sd = np.where(known, sd_hours, 0.0)
    return np.where(known, 1.0 / (1.0 + (sd / window_hours) ** 2), 0.0)


def kriged_windows(arrival_hours: np.ndarray, start_hours: Sequence[float], window_hours: float):
    """Initial and endpoint states of kriged windows on one grid.

    ``arrival_hours`` is NaN outside the reconstructed final perimeter (never
    burned in the record, a known zero), which is how the released pipeline
    reads the label raster. Yields ``(t, initial, endpoint)`` boolean arrays.
    """
    finite = np.isfinite(arrival_hours)
    for t in start_hours:
        initial = finite & (arrival_hours <= t)
        endpoint = finite & (arrival_hours <= t + window_hours)
        yield t, initial, endpoint


@dataclass
class PerimeterSample:
    """One interval: raw environment at the cutoff and the mapped endpoint.

    Arrays are numpy on the (cropped) event grid. ``label_weight`` is one for
    perimeters and the kriging weight for kriged windows; ``score_mask`` marks
    known, initially unburned cells that enter the loss.
    """

    event_id: str
    t1: str
    hours: float
    environment: np.ndarray  # [C, H, W] raw, NaN where unknown
    initial: np.ndarray  # [H, W] bool
    endpoint: np.ndarray  # [H, W] bool
    score_mask: np.ndarray  # [H, W] bool
    label_weight: np.ndarray  # [H, W] float
    initial_age_hours: np.ndarray  # [H, W] float, 0 where unknown
    kind: str = "perimeter"  # or "kriged"
    weather: str = "cutoff_repeated"
    meta: dict[str, Any] = field(default_factory=dict)
    residence_hours: np.ndarray | None = None


def sample_forecast(model, sample: PerimeterSample, *, dtype=torch.float32, use_burnout: bool = True,
                    use_spotting: bool = True, environment: np.ndarray | None = None,
                    tensors: dict | None = None):
    """Mean-field endpoint new-burn probability ``[H, W]`` and validity for a sample."""
    t = tensors or sample_tensors(sample, dtype)
    env = t["environment"] if environment is None else torch.as_tensor(environment, dtype=dtype)[None]
    feature_valid = torch.isfinite(env)
    env = torch.where(feature_valid, env, torch.zeros_like(env))
    burnout = model.flaming_window() if use_burnout and hasattr(model, "flaming_window") else None
    if burnout is not None and sample.residence_hours is not None:
        from .burnout import FlamingWindow
        burnout = FlamingWindow(torch.as_tensor(sample.residence_hours, dtype=dtype), model.smoulder())
    spotting = None
    if use_spotting and getattr(model, "spotting_radius", 0):
        spot_env = env
        # The branch direction is a domain mean, so remote missing wind is a
        # global dependency, independent of its finite source transport radius.
        wind_valid = feature_valid[..., list(model.wind_index), :, :]
        global_wind_valid = wind_valid.all(dim=(-3, -2, -1), keepdim=True)

        def spotting(source, step):
            rate = model.spot_rate(source, spot_env, boundary="zero")
            # Zero is only an internal placeholder for an unavailable branch.
            # global_feature_valid removes its unobserved targets from support.
            if bool(global_wind_valid.all()):
                return rate
            return torch.where(global_wind_valid, rate, torch.zeros_like(rate))
        spotting.source_radius = model.spotting_radius
        spotting.global_feature_valid = global_wind_valid
        spotting.source_mode = "flaming_only"
    result = propagate_mean_field(model, t["initial"], env, step_durations(sample.hours),
                                  channel_names=getattr(model, "channel_names", None),
                                  p0_valid=torch.ones_like(t["initial"], dtype=torch.bool),
                                  feature_valid=feature_valid, boundary="zero", burnout=burnout,
                                  initial_age_hours=t["age"], extra_rate_fn=spotting)
    return result.new_burn_probability[-1][0, 0], result.valid[-1][0, 0]


def sample_tensors(sample: PerimeterSample, dtype=torch.float32) -> dict:
    return dict(
        environment=torch.as_tensor(sample.environment, dtype=dtype)[None],
        initial=torch.as_tensor(sample.initial, dtype=dtype)[None, None],
        age=torch.as_tensor(np.nan_to_num(sample.initial_age_hours, nan=0.0), dtype=dtype)[None, None],
        endpoint=torch.as_tensor(sample.endpoint, dtype=dtype),
        mask=torch.as_tensor(sample.score_mask),
        weight=torch.as_tensor(sample.label_weight, dtype=dtype),
    )


def endpoint_brier(probability: Tensor, label: Tensor, weight: Tensor, mask: Tensor) -> tuple[Tensor, Tensor]:
    """Return ``(sum w (p - y)^2, sum w)`` over masked cells (NaN-safe)."""
    use = mask & torch.isfinite(probability)
    if bool((use & (~torch.isfinite(label) | ((label != 0) & (label != 1)))).any()):
        raise ValueError("Scored endpoint labels must be binary and finite")
    if bool((use & (~torch.isfinite(weight) | (weight < 0))).any()):
        raise ValueError("Scored weights must be finite and nonnegative")
    p = torch.where(use, probability, torch.zeros_like(probability))
    label = torch.where(use, label, torch.zeros_like(label))
    w = torch.where(use, weight, torch.zeros_like(weight))
    return (w * (p - label).square()).sum(), w.sum()


def clipped_nll(probability: Tensor, label: Tensor, weight: Tensor, mask: Tensor) -> tuple[Tensor, Tensor]:
    use = mask & torch.isfinite(probability)
    if bool((use & (~torch.isfinite(label) | ((label != 0) & (label != 1)))).any()):
        raise ValueError("Scored endpoint labels must be binary and finite")
    if bool((use & (~torch.isfinite(weight) | (weight < 0))).any()):
        raise ValueError("Scored weights must be finite and nonnegative")
    label = torch.where(use, label, torch.zeros_like(label))
    p = torch.where(use, probability, torch.full_like(probability, 0.5)).clamp(LOG_FLOOR, 1 - LOG_FLOOR)
    w = torch.where(use, weight, torch.zeros_like(weight))
    loss = -(label * torch.log(p) + (1 - label) * torch.log1p(-p))
    return (w * loss).sum(), w.sum()


def biome_balance_factors(class_counts: dict[int, float], *, min_frequency: float = 0.001,
                          max_factor: float = 10.0) -> dict[int, float]:
    """Training-only inverse-square-root class emphasis with weighted mean one.

    The same mode, floor and cap as ``metrics.fit_categorical_balance``
    defaults (inverse-sqrt, 0.001, 10), applied to cell counts by biome.
    """
    total = float(sum(class_counts.values()))
    if total <= 0:
        return {}
    raw = {code: min(max_factor, 1.0 / math.sqrt(max(count / total, min_frequency)))
           for code, count in class_counts.items()}
    mean = sum(raw[c] * class_counts[c] for c in raw) / total
    return {code: value / mean for code, value in raw.items()}


# Fitting
# -------

def fit_normalization(samples: Sequence[PerimeterSample], channel_names: Sequence[str]):
    """Training-only channel moments over scored cells; one-hot channels keep 0/1."""
    c = len(channel_names)
    total = np.zeros(c)
    square = np.zeros(c)
    count = np.zeros(c)
    for sample in samples:
        env = sample.environment.reshape(c, -1)[:, sample.score_mask.ravel()].astype(np.float64)
        finite = np.isfinite(env)
        total += np.where(finite, env, 0).sum(axis=1)
        square += np.where(finite, env ** 2, 0).sum(axis=1)
        count += finite.sum(axis=1)
    mean = total / np.maximum(count, 1)
    std = np.sqrt(np.maximum(square / np.maximum(count, 1) - mean ** 2, 0))
    std = np.where(std > 1e-6, std, 1.0)
    for i, name in enumerate(channel_names):
        if "=" in name:
            mean[i], std[i] = 0.0, 1.0
    return torch.tensor(mean, dtype=torch.float32), torch.tensor(std, dtype=torch.float32)


def augment(sample: PerimeterSample, k: int, flip: bool, wind_index: tuple[int, int]) -> PerimeterSample:
    """Exact D4 copy of a sample (spatial arrays move, wind vectors transform)."""
    from .canonical import d4_sample
    env, initial, endpoint, mask, weight, age = d4_sample(
        torch.from_numpy(sample.environment), wind_index, k, flip,
        torch.from_numpy(sample.initial), torch.from_numpy(sample.endpoint),
        torch.from_numpy(sample.score_mask), torch.from_numpy(sample.label_weight),
        torch.from_numpy(sample.initial_age_hours))
    residence = None
    if sample.residence_hours is not None:
        from .canonical import d4_spatial
        residence = d4_spatial(torch.from_numpy(sample.residence_hours), k, flip).numpy()
    return PerimeterSample(sample.event_id, sample.t1, sample.hours, env.numpy(), initial.numpy(),
                           endpoint.numpy(), mask.numpy(), weight.numpy(), age.numpy(), sample.kind,
                           sample.weather, dict(sample.meta, d4=[k, flip]), residence)


def evaluate_samples(model, samples: Sequence[PerimeterSample]) -> dict:
    """Pooled endpoint Brier and clipped NLL of the mean field on scored cells."""
    model.eval()
    sq = nll = weight = 0.0
    with torch.no_grad():
        for sample in samples:
            t = sample_tensors(sample)
            p, valid = sample_forecast(model, sample, tensors=t)
            mask = t["mask"] & valid
            a, w = endpoint_brier(p, t["endpoint"], t["weight"], mask)
            b, _ = clipped_nll(p, t["endpoint"], t["weight"], mask)
            sq, nll, weight = sq + float(a), nll + float(b), weight + float(w)
    if weight <= 0:
        raise ValueError("No supported positive-weight cells remain for evaluation")
    return dict(brier=sq / weight, clipped_nll=nll / weight, weight=weight)


def fit_mean_field(model, train: Sequence[PerimeterSample], validation: Sequence[PerimeterSample], *,
                   epochs: int = 8, learning_rate: float = 3e-3, weight_decay: float = 1e-4,
                   seed: int = 0, patience: int = 3, d4: bool = False, samples_per_step: int = 4,
                   balance: dict[int, float] | None = None, biome_channels: dict[int, int] | None = None,
                   intervals_per_epoch: int | None = None, validate_each_epoch: bool = True,
                   runtime_case_id_fn=None, runtime_object_sha_fn=None,
                   runtime_sample_manifest_sha256: str | None = None,
                   log=print) -> dict:
    """Minimize the interval-censored endpoint Brier through the mean field.

    One optimizer step pools ``samples_per_step`` intervals: the loss is
    ``sum w (p - y)^2 / sum w`` divided by the training prevalence (the
    scaling used by ``train.py``). With ``intervals_per_epoch`` an epoch is a
    random draw (without replacement) of that many intervals. Selection:
    minimum pooled validation Brier on the validation fires of the current
    development fold, or, with ``validate_each_epoch=False``, the last epoch
    (fixed budget; validation scored once at the end). Returns the history;
    the selected state is loaded into ``model``.
    """
    import copy
    import json
    import time
    if not train or epochs < 1 or samples_per_step < 1:
        raise ValueError("Fitting requires nonempty training samples and positive budgets")
    recording = runtime_case_id_fn is not None
    if any(value is not None for value in (runtime_case_id_fn, runtime_object_sha_fn,
                                           runtime_sample_manifest_sha256)) and not (
            callable(runtime_case_id_fn) and callable(runtime_object_sha_fn)
            and isinstance(runtime_sample_manifest_sha256, str)
            and len(runtime_sample_manifest_sha256) == 64):
        raise ValueError("Runtime membership requires both identity callbacks and a prefit manifest hash")
    runtime_epochs = []
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    positives = sum(float((s.endpoint & s.score_mask).sum()) for s in train)
    cells = sum(float(s.score_mask.sum()) for s in train)
    prevalence = max(positives / max(cells, 1.0), 1e-6)
    optimizer = torch.optim.Adam([p for p in model.parameters() if p.requires_grad],
                                 lr=learning_rate, weight_decay=weight_decay)
    history, best, best_state, stale = [], math.inf, copy.deepcopy(model.state_dict()), 0
    for epoch in range(1, epochs + 1):
        started = time.perf_counter()
        model.train()
        order = rng.permutation(len(train))
        if intervals_per_epoch is not None:
            order = order[:intervals_per_epoch]
        running = 0.0
        skipped, optimizer_steps = [], 0
        attempted_ids, skipped_ids = [], []
        for start in range(0, len(order), samples_per_step):
            optimizer.zero_grad(set_to_none=True)
            w_total = 0.0
            losses = []
            for index in order[start:start + samples_per_step]:
                sample = train[index]
                if recording:
                    original_case_id = runtime_case_id_fn(sample)
                    attempted_ids.append(original_case_id)
                if d4:
                    k, flip = int(rng.integers(4)), bool(rng.integers(2))
                    sample = augment(sample, k, flip, model.wind_index)
                t = sample_tensors(sample)
                weight = t["weight"]
                if balance and biome_channels:
                    factor = torch.ones_like(weight)
                    for code, channel in biome_channels.items():
                        factor = torch.where(t["environment"][0, channel] == 1,
                                             torch.full_like(factor, balance.get(code, 1.0)), factor)
                    weight = weight * factor
                p, valid = sample_forecast(model, sample, tensors=t)
                a, w = endpoint_brier(p, t["endpoint"], weight, t["mask"] & valid)
                if float(w) <= 0:
                    skipped.append(dict(event=sample.event_id, cutoff=sample.t1,
                                        reason="no_supported_positive_weight_cells"))
                    if recording:
                        skipped_ids.append(original_case_id)
                    continue
                losses.append(a)
                w_total += float(w)
            if w_total <= 0:
                continue
            loss = torch.stack(losses).sum() / w_total / prevalence
            if not bool(torch.isfinite(loss)):
                raise RuntimeError(f"Nonfinite training loss at epoch {epoch}")
            loss.backward()
            optimizer.step()
            optimizer_steps += 1
            running += float(loss) * len(losses)
        if optimizer_steps == 0:
            raise ValueError("No supported positive-weight cells remain in the training epoch")
        if recording:
            runtime_epochs.append(dict(epoch=epoch, attempted_case_ids=attempted_ids,
                                       attempted_case_ids_sha256=runtime_object_sha_fn(attempted_ids),
                                       skipped_case_ids=skipped_ids, optimizer_steps=optimizer_steps))
        if not validate_each_epoch:
            record = dict(epoch=epoch, train_scaled_loss=running / max(len(order), 1),
                          seconds=time.perf_counter() - started, selected=epoch == epochs,
                          optimizer_steps=optimizer_steps, skipped_unsupported_intervals=skipped)
            history.append(record)
            log(json.dumps(record))
            continue
        scores = evaluate_samples(model, validation) if validation else dict(brier=float("nan"))
        record = dict(epoch=epoch, train_scaled_loss=running / max(len(order), 1),
                      validation_brier=scores["brier"], validation_clipped_nll=scores.get("clipped_nll"),
                      seconds=time.perf_counter() - started, optimizer_steps=optimizer_steps,
                      skipped_unsupported_intervals=skipped)
        improved = bool(validation) and scores["brier"] < best
        if improved or not validation:
            best, best_state, stale = scores["brier"], copy.deepcopy(model.state_dict()), 0
        else:
            stale += 1
        record["selected"] = bool(improved or not validation)
        history.append(record)
        log(json.dumps(record))
        if validation and stale >= patience:
            break
    if not validate_each_epoch:
        result = dict(history=history, best_validation_brier=None, train_prevalence=prevalence)
    else:
        model.load_state_dict(best_state)
        result = dict(history=history, best_validation_brier=best, train_prevalence=prevalence)
    if recording:
        result["runtime_membership"] = dict(schema="wfg.forecast-fit-runtime-membership/1",
                                            sample_manifest_sha256=runtime_sample_manifest_sha256,
                                            epochs=runtime_epochs)
    return result
