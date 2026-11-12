"""Load and validate scored cell-interval entries.

File contract: one ``<fire>.npz`` per fire, in the same layout as the
forecast-v2 held-out files
(``forecast/runs/20261030_perimeter_trained/execution_v3/heldout``).

Required arrays, all of length N (entries):
  interval  int    index into the per-interval arrays below
  y         int8   1 if the cell newly burned (mapped) by the endpoint, else 0
  p_<name>  float  predicted probability in [0, 1], one array per predictor

Required arrays of length K (intervals):
  hours     float  interval duration (cutoff to endpoint), the forecast horizon

Optional arrays:
  row, col                 int    grid position (length N)
  t1                       str    cutoff time per interval (length K)
  dist_m                   float  distance from the cell centre to the nearest
                                  cell burned at cutoff (length N); enables
                                  at-risk band strata
  area_samples_<name>      float  K x M simulated new-burn cell counts per
                                  interval; enables burned-area CRPS for that
                                  predictor

Every file must carry the same set of ``p_`` predictors. A file that breaks the
contract raises ValueError; nothing is silently dropped or repaired.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Entries:
    fire: np.ndarray            # str, length N
    interval: np.ndarray        # int, length N (fire-local interval index)
    hours: np.ndarray           # float, length N (horizon of each entry's interval)
    y: np.ndarray               # float64, length N
    predictions: dict[str, np.ndarray]
    dist_m: np.ndarray | None = None
    area_samples: dict[str, dict[str, np.ndarray]] = field(default_factory=dict)  # name -> fire -> K x M
    area_observed: dict[str, np.ndarray] = field(default_factory=dict)            # fire -> K observed counts

    def subset(self, mask: np.ndarray) -> "Entries":
        return Entries(
            fire=self.fire[mask], interval=self.interval[mask], hours=self.hours[mask], y=self.y[mask],
            predictions={k: v[mask] for k, v in self.predictions.items()},
            dist_m=None if self.dist_m is None else self.dist_m[mask],
        )

    def as_baselines_entries(self) -> dict:
        """The dict layout that ``wildfire.baselines.score_entries`` expects."""
        return dict(fire=self.fire, y=self.y, interval=self.interval, predictions=self.predictions)


def _check(cond: bool, path: Path, message: str) -> None:
    if not cond:
        raise ValueError(f"{path.name}: {message}")


def load(paths, predictors: list[str] | None = None) -> Entries:
    """Concatenate per-fire files. ``predictors`` restricts and orders the predictors kept."""
    paths = sorted(Path(p) for p in paths)
    if not paths:
        raise ValueError("no entry files given")
    fires, intervals, hours, ys, dists = [], [], [], [], []
    preds: dict[str, list[np.ndarray]] = {}
    names = None
    have_dist = None
    area_samples: dict[str, dict[str, np.ndarray]] = {}
    area_observed: dict[str, np.ndarray] = {}
    seen = set()
    for path in paths:
        fire = path.stem
        _check(fire not in seen, path, "duplicate fire")
        seen.add(fire)
        with np.load(path, allow_pickle=False) as z:
            for key in ("interval", "y", "hours"):
                _check(key in z.files, path, f"missing required array '{key}'")
            y = z["y"]
            n = len(y)
            _check(set(np.unique(y)).issubset({0, 1}), path, "y must be 0/1")
            interval = z["interval"].astype(np.int64)
            k_hours = z["hours"].astype(np.float64)
            _check(len(interval) == n, path, "interval length differs from y")
            _check(n == 0 or (interval.min() >= 0 and interval.max() < len(k_hours)), path,
                   "interval index outside the hours array")
            _check(bool(np.isfinite(k_hours).all() and (k_hours > 0).all()), path, "hours must be finite and > 0")
            current = sorted(k[2:] for k in z.files if k.startswith("p_"))
            if names is None:
                names = current
            _check(current == names, path, f"predictors {current} differ from {names}")
            for name in names:
                p = z[f"p_{name}"].astype(np.float64)
                _check(len(p) == n, path, f"p_{name} length differs from y")
                _check(bool(np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all()), path,
                       f"p_{name} must be finite in [0, 1]")
                preds.setdefault(name, []).append(p)
            file_has_dist = "dist_m" in z.files
            if have_dist is None:
                have_dist = file_has_dist
            _check(file_has_dist == have_dist, path, "dist_m present in some files only")
            if file_has_dist:
                d = z["dist_m"].astype(np.float64)
                _check(len(d) == n and bool(np.isfinite(d).all()) and bool((d >= 0).all()), path,
                       "dist_m must be finite, >= 0 and length N")
                dists.append(d)
            observed = np.bincount(interval, weights=y.astype(np.float64), minlength=len(k_hours))
            area_observed[fire] = observed
            for key in z.files:
                if key.startswith("area_samples_"):
                    s = z[key].astype(np.float64)
                    _check(s.ndim == 2 and s.shape[0] == len(k_hours) and s.shape[1] > 0, path,
                           f"{key} must be K x M")
                    _check(bool(np.isfinite(s).all() and (s >= 0).all()), path, f"{key} must be finite >= 0")
                    area_samples.setdefault(key[len("area_samples_"):], {})[fire] = s
        fires.append(np.full(n, fire))
        intervals.append(interval)
        hours.append(k_hours[interval])
        ys.append(y.astype(np.float64))
    if predictors is not None:
        missing = [p for p in predictors if p not in names]
        if missing:
            raise ValueError(f"requested predictors not in files: {missing}")
        names = list(predictors)
    for name, per_fire in area_samples.items():
        if set(per_fire) != seen:
            raise ValueError(f"area_samples_{name} present for some fires only")
    return Entries(
        fire=np.concatenate(fires), interval=np.concatenate(intervals), hours=np.concatenate(hours),
        y=np.concatenate(ys), predictions={k: np.concatenate(preds[k]) for k in names},
        dist_m=np.concatenate(dists) if have_dist else None,
        area_samples=area_samples, area_observed=area_observed,
    )
