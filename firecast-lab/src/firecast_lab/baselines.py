"""Phase 0 baselines: cutoff information -> cumulative probabilities -> K coherent members (``members``).

| name                | ``cum[l]`` = P(burned by lead hour l)                                  | fitted on training windows |
|---------------------|------------------------------------------------------------------------|----------------------------|
| persistence         | the cutoff state                                                       | nothing                    |
| dilation            | Chebyshev distance to the burned set <= floor(l / k), i.e. ``wildfire.baselines.dilation`` | k: least pooled Brier at the lead (``choose_dilation``) |
| calibrated_dilation | isotonic non-increasing map of that distance per lead, then a running max over leads; the bar to beat | the maps |
| logistic            | logistic regression on ``wildfire.baselines.hand_features`` (distance to the front, wind alignment, slope, lead) | weighted coefficients |
| c651                | its own Monte Carlo trajectories (``firecast_lab.c651``)               | nothing; in-sample on 25 dev fires |

``fit`` sees only the windows it is given; cross-fitting by whole-fire folds is the harness's job. Fitting rows are
the scored cells of each training window (``Window.fitting_rows``), so a baseline is calibrated on the population
it is scored on; the headline domain of a training fire comes from that fire's own final perimeter, never from the
predicted fire's. ``probabilities`` sees only the cutoff inputs (``data.Cutoff``), never the outcome.

Why calibrated dilation is the bar to beat: the best 0/1 dilation is one monotone step function of the Chebyshev
distance; the isotonic map is the best monotone function of the same distance on the training fires, so it refines
the tuned dilation and calibrates it.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage
from scipy.optimize import isotonic_regression
from wildfire import baselines as wb

from firecast_lab import metrics
from firecast_lab.data import Cutoff, Window, case_seed
from firecast_lab.members import coherent_members

DILATION_CANDIDATES = tuple(sorted(set(wb.DILATION_HOURS) | {3, 6, 12, 16, 24}))   # hours per cell
FIT_LEADS = (1, 2, 3, 6, 12, 18, 24)
NO_WEATHER = "none: cutoff burned state only"
CUTOFF_WIND = ("ECMWF IFS archive via Open-Meteo: 10 m wind at the cutoff hour, repeated over the horizon "
               "(persistence weather)")


def front_distance(burned) -> np.ndarray:
    """Chebyshev distance (cells) to the nearest burned cell: ``d`` steps of 3x3 dilation reach exactly the cells
    with distance <= d. +inf everywhere when nothing is burned."""
    burned = np.asarray(burned, dtype=bool)
    if not burned.any():
        return np.full(burned.shape, np.inf)
    return ndimage.distance_transform_cdt(~burned, metric="chessboard").astype(np.float64)


class DistanceTable:
    """Fitting rows pooled by Chebyshev distance d to the cutoff front: ``counts[a, d]`` cells whose arrival falls in
    lead hour a = 1..L (L + 1: not by the horizon). Sufficient statistics of every distance-only baseline."""

    def __init__(self, lead_h: int):
        self.lead_h = int(lead_h)
        self.counts = np.zeros((self.lead_h + 2, 0))

    @classmethod
    def of(cls, windows) -> "DistanceTable":
        """One pass over any iterable of windows sharing one lead."""
        table = None
        for w in windows:
            if table is None:
                table = cls(w.lead_h)
            elif w.lead_h != table.lead_h:
                raise ValueError("training windows must share one lead")
            table.add(w)
        if table is None or table.counts.sum() == 0:
            raise ValueError("no fitting rows in the training windows")
        return table

    def add(self, window: Window) -> None:
        rows = window.fitting_rows
        d = front_distance(window.inputs.burned)[rows]
        if d.size == 0 or not np.isfinite(d).all():
            return                                          # no scored cell, or no front at this cutoff
        a = metrics.hourly_arrival(window.outcome_h[rows], self.lead_h).astype(int)
        d = d.astype(int)
        grown = np.zeros((self.lead_h + 2, max(self.counts.shape[1], d.max() + 1)))
        grown[:, :self.counts.shape[1]] = self.counts
        np.add.at(grown, (a, d), 1.0)
        self.counts = grown

    @property
    def cells(self) -> np.ndarray:
        return self.counts.sum(axis=0)

    def burned_by(self, lead: int) -> np.ndarray:
        return self.counts[1:lead + 1].sum(axis=0)

    def brier_of_radius(self, radius: float) -> float:
        """Pooled Brier at the lead of the 0/1 forecast "new burn iff distance <= radius"."""
        n, y = self.cells, self.burned_by(self.lead_h)
        inside = np.arange(n.size) <= radius
        return float(((n - y)[inside].sum() + y[~inside].sum()) / n.sum())


def _radius(lead: float, hours_per_cell: float) -> float:
    return math.floor(lead / hours_per_cell + 1e-9)        # the step rule of wildfire.baselines.dilation


class Persistence:
    """No new burn: every member is the cutoff state."""

    name, weather_source = "persistence", NO_WEATHER

    def fit(self, windows) -> "Persistence":
        return self

    def probabilities(self, inputs: Cutoff, lead_h: int):
        cum = np.repeat(inputs.burned[None].astype(np.float64), lead_h + 1, axis=0)
        return cum, np.ones(inputs.shape, dtype=bool)

    def describe(self) -> dict:
        return {}


class Dilation:
    """The cutoff state grown by one cell (8-neighbourhood) per ``hours_per_cell``; k tuned on training fires."""

    name, weather_source = "dilation", NO_WEATHER

    def __init__(self, hours_per_cell: float | None = None, candidates=DILATION_CANDIDATES):
        self.hours_per_cell, self.candidates, self.training_brier = hours_per_cell, tuple(candidates), None

    def fit(self, windows) -> "Dilation":
        table = DistanceTable.of(windows)
        self.training_brier = {k: table.brier_of_radius(_radius(table.lead_h, k)) for k in self.candidates}
        self.hours_per_cell = wb.choose_dilation(self.training_brier)
        return self

    def probabilities(self, inputs: Cutoff, lead_h: int):
        if self.hours_per_cell is None:
            raise RuntimeError("fit the dilation (or give hours_per_cell) first")
        radius = np.array([_radius(lead, self.hours_per_cell) for lead in range(lead_h + 1)])
        cum = (front_distance(inputs.burned)[None] <= radius[:, None, None]).astype(np.float64)
        return cum, np.ones(inputs.shape, dtype=bool)

    def describe(self) -> dict:
        return dict(hours_per_cell=self.hours_per_cell, training_brier=self.training_brier)


class CalibratedDilation:
    """Isotonic (non-increasing) calibration of the Chebyshev distance to the front, per lead hour, made
    non-decreasing in lead by a running maximum. Unseen distances interpolate; beyond the largest one, its value."""

    name, weather_source = "calibrated_dilation", NO_WEATHER

    def __init__(self):
        self.lead_h = self.distance = self.rate = None

    def fit(self, windows) -> "CalibratedDilation":
        table = DistanceTable.of(windows)
        n = table.cells
        seen = n > 0
        self.lead_h, self.distance = table.lead_h, np.flatnonzero(seen).astype(np.float64)
        self.rate = np.stack([isotonic_regression(table.burned_by(lead)[seen] / n[seen], weights=n[seen],
                                                  increasing=False).x for lead in range(1, table.lead_h + 1)])
        return self

    def probabilities(self, inputs: Cutoff, lead_h: int):
        if self.rate is None or lead_h > self.lead_h:
            raise RuntimeError(f"fit the calibration for a lead of at least {lead_h} h first")
        d = front_distance(inputs.burned)
        cum = np.empty((lead_h + 1, *inputs.shape))
        cum[0] = inputs.burned
        for lead in range(1, lead_h + 1):
            cum[lead] = np.interp(d, self.distance, self.rate[lead - 1])
        cum = np.maximum.accumulate(np.clip(cum, 0.0, 1.0), axis=0)
        cum[:, inputs.burned] = 1.0
        return cum, np.ones(inputs.shape, dtype=bool)

    def describe(self) -> dict:
        """The fitted rate at the lead for the 16 nearest distances (cells), as a summary for result rows."""
        if self.rate is None:
            return {}
        return dict(lead_h=self.lead_h, rate_at_lead={int(d): round(float(r), 6)
                                                      for d, r in zip(self.distance[:16], self.rate[-1][:16])})


def lead_features(base: np.ndarray, lead: float) -> np.ndarray:
    """``wildfire.baselines.hand_features`` at ``lead`` from its value at 1 h: only the columns d / hours (1) and
    log(hours) (6) depend on the lead (pinned by a test against hand_features itself)."""
    out = base.copy()
    out[:, 1] = base[:, 1] / lead
    out[:, 6] = math.log(lead)
    return out


class Logistic:
    """Logistic regression on distance to the front, wind alignment and slope (``hand_features``, no biome), fitted
    on rows sampled per window and lead (at most ``rows_per_class`` per class, weighted back to the full count)."""

    name, weather_source = "logistic", CUTOFF_WIND

    def __init__(self, rows_per_class: int = 200, fit_leads=FIT_LEADS, seed: int = 0, C: float = 1.0):
        self.rows_per_class, self.fit_leads, self.seed, self.C = rows_per_class, tuple(fit_leads), seed, C
        self.fitted = None

    @staticmethod
    def _base(inputs: Cutoff) -> np.ndarray:
        if inputs.wind_u is None or inputs.wind_v is None or inputs.slope is None:
            raise ValueError("the logistic baseline needs wind and slope (load windows with inputs=True)")
        return wb.hand_features(inputs.burned, 1.0, inputs.wind_u, inputs.wind_v, inputs.slope, None, ())

    def fit(self, windows) -> "Logistic":
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler

        xs, ys, ws = [], [], []
        for w in windows:
            rows = w.fitting_rows.ravel()
            if not rows.any():
                continue
            base = self._base(w.inputs)
            rng = np.random.default_rng([self.seed, case_seed(self.seed, w.fire, w.cutoff_utc)])
            for lead in sorted({lead for lead in self.fit_leads if lead <= w.lead_h} | {w.lead_h}):
                label = ((w.outcome_h > 0) & (w.outcome_h <= lead)).ravel()
                for cls in (True, False):
                    idx = np.flatnonzero(rows & (label == cls))
                    take = rng.choice(idx, size=min(idx.size, self.rows_per_class), replace=False)
                    if take.size:
                        xs.append(lead_features(base[take], lead))
                        ys.append(np.full(take.size, cls))
                        ws.append(np.full(take.size, idx.size / take.size))
        y = np.concatenate(ys) if ys else np.zeros(0, bool)
        if y.all() or not y.any():
            raise ValueError("the logistic baseline needs both burned and unburned training rows")
        x, w = np.concatenate(xs), np.concatenate(ws)
        scaler = StandardScaler().fit(x, sample_weight=w)
        model = LogisticRegression(C=self.C, max_iter=2000, random_state=self.seed)
        self.fitted = (scaler, model.fit(scaler.transform(x), y, sample_weight=w))
        return self

    def probabilities(self, inputs: Cutoff, lead_h: int):
        if self.fitted is None:
            raise RuntimeError("fit the logistic baseline first")
        ok = inputs.inputs_valid
        base = self._base(inputs)[ok.ravel()]
        cum = np.zeros((lead_h + 1, *inputs.shape))
        for lead in range(1, lead_h + 1):
            cum[lead][ok] = wb.predict_logistic(self.fitted, lead_features(base, lead))
        cum = np.maximum.accumulate(cum, axis=0)
        supported = ok | inputs.burned                  # a burned cell needs no input
        cum[:, inputs.burned] = 1.0
        cum[:, ~supported] = np.nan
        return cum, supported

    def describe(self) -> dict:
        if self.fitted is None:
            return {}
        scaler, model = self.fitted
        return dict(coef=[round(float(c), 6) for c in model.coef_[0]], intercept=round(float(model.intercept_[0]), 6),
                    rows_per_class=self.rows_per_class, fit_leads=list(self.fit_leads))


BASELINES = ("persistence", "dilation", "calibrated_dilation", "logistic", "c651")


def make(name: str, **options):
    """A fresh baseline by name (``c651`` needs ``root``; it is imported lazily)."""
    if name == "c651":
        from firecast_lab.c651 import C651
        return C651(**options)
    classes = dict(persistence=Persistence, dilation=Dilation, calibrated_dilation=CalibratedDilation,
                   logistic=Logistic)
    if name not in classes:
        raise ValueError(f"unknown baseline {name!r}; choose from {BASELINES}")
    return classes[name](**options)


def forecast(model, window: Window, *, K: int, seed: int, coupling: str = "shared",
             length_cells: float | None = None) -> tuple[np.ndarray, np.ndarray | None]:
    """K coherent member arrival fields for one window and, for probability baselines, P(burned by the lead)
    (None for models with their own members, i.e. c651).

    Threshold baselines share the window's uniform fields (common random numbers: same seed, coupling and K give the
    same fields), so paired differences between baselines carry less Monte Carlo noise."""
    if hasattr(model, "members"):
        return model.members(window, K=K, seed=seed), None
    cum, _ = model.probabilities(window.inputs, window.lead_h)
    hours = coherent_members(cum, K, seed=case_seed(seed, window.fire, window.cutoff_utc), coupling=coupling,
                             length_cells=length_cells, initial_h=window.inputs.initial_h)
    return hours, cum[-1]


def members(model, window: Window, **options) -> np.ndarray:
    """``forecast(...)[0]``: the K member arrival fields only."""
    return forecast(model, window, **options)[0]
