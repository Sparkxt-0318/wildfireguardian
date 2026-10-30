"""Reference forecasts and scoring for perimeter-interval evaluation.

Every model is scored on exactly the same cells: known cells of the event
rectangle outside the initial mapped extent, intersected with the validity of
every compared model. Baselines:

- persistence: no new burn (probability zero everywhere);
- dilation(k): the initial extent grown by one cell (8-neighbourhood, i.e.
  Chebyshev distance) per ``k`` hours, ``floor(T / k)`` cells for an interval
  of ``T`` hours, as a 0/1 forecast; the best ``k`` is chosen on training
  fires only;
- logistic regression on hand features (distance to the nearest burned cell,
  wind alignment of that direction, slope, biome indicators, interval hours).

Metrics: Brier, Brier skill score against persistence, average precision,
ROC AUC, fixed-bin expected calibration error (ten equal-width bins), clipped
negative log likelihood (floor 1e-7), per-fire values and a paired bootstrap
that resamples whole fires (never cells).
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np
from scipy import ndimage

LOG_FLOOR = 1e-7
DILATION_HOURS = (1, 2, 4, 8)
BINS = np.linspace(0.0, 1.0, 11)

__all__ = [
    "persistence", "dilation", "nearest_burned_features", "hand_features", "fit_logistic",
    "predict_logistic", "score", "calibration_table", "per_fire_scores", "paired_fire_bootstrap",
    "choose_dilation",
]


def persistence(initial: np.ndarray) -> np.ndarray:
    return np.zeros(initial.shape, dtype=np.float64)


def dilation(initial: np.ndarray, hours: float, hours_per_cell: float) -> np.ndarray:
    """0/1 new-burn forecast: cells within Chebyshev distance floor(T/k) of the extent."""
    steps = int(math.floor(hours / hours_per_cell + 1e-9))
    burned = initial.astype(bool)
    if steps <= 0 or not burned.any():
        return np.zeros(burned.shape, dtype=np.float64)
    grown = ndimage.binary_dilation(burned, structure=np.ones((3, 3), bool), iterations=steps)
    return (grown & ~burned).astype(np.float64)


def nearest_burned_features(initial: np.ndarray):
    """Distance (cells) to the nearest burned cell and the unit direction from it."""
    burned = initial.astype(bool)
    if not burned.any():
        h, w = burned.shape
        inf = np.full((h, w), np.inf)
        return inf, np.zeros((h, w)), np.zeros((h, w))
    distance, (rows, cols) = ndimage.distance_transform_edt(~burned, return_indices=True)
    rr, cc = np.indices(burned.shape)
    north = -(rr - rows).astype(np.float64)  # row increases southward
    east = (cc - cols).astype(np.float64)
    norm = np.hypot(east, north)
    with np.errstate(invalid="ignore", divide="ignore"):
        east = np.where(norm > 0, east / norm, 0.0)
        north = np.where(norm > 0, north / norm, 0.0)
    return distance, east, north


def hand_features(initial: np.ndarray, hours: float, u: np.ndarray, v: np.ndarray,
                  slope: np.ndarray, biome: np.ndarray | None, biome_codes: Sequence[int],
                  max_distance: float = 40.0) -> np.ndarray:
    """``[H*W, F]`` features: log distance, alignment, slope, interactions, biome one-hot."""
    distance, east, north = nearest_burned_features(initial)
    speed = np.hypot(u, v)
    with np.errstate(invalid="ignore", divide="ignore"):
        alignment = np.where(speed > 1e-9, (east * u + north * v) / speed, 0.0)
    d = np.minimum(distance, max_distance)
    columns = [np.log1p(d), d / max(hours, 1e-9), alignment, alignment * speed, speed,
               np.nan_to_num(slope, nan=0.0) / 45.0, np.full(d.shape, math.log(hours))]
    if biome is not None:
        columns += [(biome == code).astype(np.float64) for code in biome_codes]
    return np.stack([c.astype(np.float64).ravel() for c in columns], axis=1)


def fit_logistic(features: np.ndarray, labels: np.ndarray, *, seed: int = 0, C: float = 1.0):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler().fit(features)
    model = LogisticRegression(C=C, max_iter=2000, random_state=seed)
    model.fit(scaler.transform(features), labels.astype(int))
    return scaler, model


def predict_logistic(fitted, features: np.ndarray) -> np.ndarray:
    scaler, model = fitted
    return model.predict_proba(scaler.transform(features))[:, 1]


def _average_precision(y: np.ndarray, p: np.ndarray) -> float | None:
    if y.sum() == 0:
        return None
    order = np.argsort(-p, kind="mergesort")
    y, p = y[order], p[order]
    # Group tied scores: precision is evaluated at the end of each tie group.
    distinct = np.r_[np.flatnonzero(np.diff(p)), len(p) - 1]
    tp = np.cumsum(y)[distinct]
    fp = (distinct + 1) - tp
    precision = tp / (tp + fp)
    recall = tp / y.sum()
    previous = np.r_[0.0, recall[:-1]]
    return float(np.sum((recall - previous) * precision))


def _auc(y: np.ndarray, p: np.ndarray) -> float | None:
    positives, negatives = y.sum(), len(y) - y.sum()
    if positives == 0 or negatives == 0:
        return None
    from scipy.stats import rankdata
    ranks = rankdata(p)
    return float((ranks[y == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def calibration_table(y: np.ndarray, p: np.ndarray) -> list[dict]:
    index = np.clip(np.digitize(p, BINS[1:-1], right=False), 0, len(BINS) - 2)
    rows = []
    for b in range(len(BINS) - 1):
        use = index == b
        n = int(use.sum())
        rows.append(dict(lower=float(BINS[b]), upper=float(BINS[b + 1]), count=n,
                         share=n / len(y) if len(y) else None,
                         mean_prediction=float(p[use].mean()) if n else None,
                         observed_frequency=float(y[use].mean()) if n else None))
    return rows


def score(y: np.ndarray, p: np.ndarray) -> dict:
    """Pooled scores on equally weighted cell-interval entries."""
    y = np.asarray(y, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    if y.shape != p.shape or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Scores need matching finite probabilities in [0, 1]")
    brier = float(np.mean((p - y) ** 2)) if len(y) else None
    persistence_brier = float(np.mean(y ** 2)) if len(y) else None
    clipped = np.clip(p, LOG_FLOOR, 1 - LOG_FLOOR)
    table = calibration_table(y, p)
    ece = sum(row["count"] * abs(row["mean_prediction"] - row["observed_frequency"])
              for row in table if row["count"]) / len(y) if len(y) else None
    lowest = table[0]
    return dict(entries=int(len(y)), positives=int(y.sum()), brier=brier,
                bss_vs_persistence=(1 - brier / persistence_brier) if persistence_brier else None,
                average_precision=_average_precision(y, p), roc_auc=_auc(y, p), ece_10_bins=ece,
                clipped_nll=float(np.mean(-(y * np.log(clipped) + (1 - y) * np.log1p(-clipped)))) if len(y) else None,
                exact_zero_probability_positives=int(((p == 0) & (y == 1)).sum()),
                lowest_bin=lowest, calibration=table)


def per_fire_scores(fire: np.ndarray, y: np.ndarray, p: np.ndarray) -> dict:
    return {str(f): score(y[fire == f], p[fire == f]) for f in np.unique(fire)}


def paired_fire_bootstrap(fire: np.ndarray, y: np.ndarray, candidate: np.ndarray, reference: np.ndarray,
                          *, draws: int = 10000, seed: int = 20261029) -> dict:
    """Brier(candidate) - Brier(reference), resampling whole fires with replacement.

    Each draw pools the squared errors of the drawn fires (a fire drawn twice
    counts twice). Negative favours the candidate. The interval is a
    percentile interval conditional on the fixed models and mapped labels.
    """
    fires = np.unique(fire)
    sq_c = (candidate - y) ** 2
    sq_r = (reference - y) ** 2
    sums = np.array([sq_c[fire == f].sum() - sq_r[fire == f].sum() for f in fires])
    counts = np.array([(fire == f).sum() for f in fires], dtype=np.float64)
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(fires), size=(draws, len(fires)))
    values = sums[sampled].sum(axis=1) / counts[sampled].sum(axis=1)
    lower, upper = np.quantile(values, [0.025, 0.975])
    per_fire = {str(f): float(s / c) for f, s, c in zip(fires, sums, counts)}
    return dict(point_difference=float(sums.sum() / counts.sum()),
                percentile_95_interval=[float(lower), float(upper)],
                excludes_zero=bool(upper < 0 or lower > 0), fires=len(fires), draws=draws, seed=seed,
                per_fire_difference=per_fire,
                fires_favouring_candidate=int(sum(1 for value in per_fire.values() if value < 0)),
                definition="candidate Brier minus reference Brier; negative favours the candidate; whole fires resampled")


def choose_dilation(training_scores: dict[int, float]) -> int:
    """Best hours-per-cell by pooled training Brier (ties: the slower growth)."""
    return min(training_scores, key=lambda k: (training_scores[k], -k))


def load_scored_entries(directory) -> dict:
    """Concatenate per-fire ``<event>.npz`` entry files written by the held-out scorer.

    Each file holds the common cohort of one fire: ``y``, ``interval`` and one
    ``p_<model>`` array per model on exactly the same entries.
    """
    from pathlib import Path
    files = sorted(Path(directory).glob("*.npz"))
    if not files:
        raise FileNotFoundError(f"No scored entry files in {directory}")
    fire, y, interval, models = [], [], [], {}
    names = None
    for path in files:
        data = np.load(path)
        current = sorted(k[2:] for k in data.files if k.startswith("p_"))
        if names is None:
            names = current
        if current != names:
            raise ValueError(f"{path.name} does not score the same models")
        fire.append(np.full(len(data["y"]), path.stem))
        y.append(data["y"].astype(np.float64))
        interval.append(data["interval"])
        for name in names:
            models.setdefault(name, []).append(data[f"p_{name}"].astype(np.float64))
    return dict(fire=np.concatenate(fire), y=np.concatenate(y), interval=np.concatenate(interval),
                predictions={k: np.concatenate(v) for k, v in models.items()})


def score_entries(entries: dict, *, references=("persistence", "dilation_best"), draws: int = 10000,
                  seed: int = 20261029) -> dict:
    """Pooled, per-fire and fire-paired comparisons for every model."""
    fire, y = entries["fire"], entries["y"]
    result = dict(models={}, paired={}, fires=sorted(set(fire.tolist())), entries=int(len(y)),
                  positives=int(y.sum()))
    for name, p in entries["predictions"].items():
        result["models"][name] = dict(pooled=score(y, p), per_fire=per_fire_scores(fire, y, p))
    for name, p in entries["predictions"].items():
        for reference in references:
            if reference in entries["predictions"] and reference != name:
                result["paired"][f"{name}__vs__{reference}"] = paired_fire_bootstrap(
                    fire, y, p, entries["predictions"][reference], draws=draws, seed=seed)
    return result
