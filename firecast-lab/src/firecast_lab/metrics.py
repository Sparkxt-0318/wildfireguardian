"""Verification metrics for fire-spread forecasts, each scored on an explicit mask (definitions: METRICS.md).

Conventions
- ``y``: outcome, 1 = burned by the verification time, 0 = outside the mapped extent at that time.
- ``p``: forecast probability in [0, 1]. Ensembles put the member axis first: ``members[K, *y.shape]``.
- ``mask``: boolean, same shape as ``y``; True = scored. Values outside the mask are never used and may be NaN.
  Unknown labels and cells that a compared model does not support must be False in the mask: nothing is
  imputed. Inside the mask every value must be finite and in range, otherwise ``ValueError``.
- Arrival-time metrics use the hourly lattice of ``hourly_arrival``: 1..H = the hour after the cutoff in which
  the cell burns, H + 1 = not by the horizon (censored).

Reused from the frozen forecast package (``wildfire.baselines``): tie-grouped average precision, the pooled
``score`` (continuity with earlier studies) and ``paired_fire_bootstrap`` (whole-fire Brier differences).
"""
from __future__ import annotations

from typing import Callable

import numpy as np
from scipy import ndimage
from wildfire import baselines as _baselines

RELIABILITY_EDGES = (0.0, 0.001, 0.003, 0.01, 0.03, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0)
FSS_SIZES = (1, 3, 9, 17, 33)
SPREAD_SD_EDGES_H = (0.5, 1.0, 2.0, 4.0, 8.0)   # fixed spread rows: sd = 0, (0, 0.5), [0.5, 1), ..., [8, inf) hours
BOOTSTRAP_SEED = 20261029            # the default of wildfire.baselines.paired_fire_bootstrap


# ----------------------------------------------------------------------------------------------- validation
def _mask(mask, shape=None) -> np.ndarray:
    mask = np.asarray(mask)
    if mask.dtype != bool:
        raise TypeError("the scoring mask must be a boolean array")
    if shape is not None and mask.shape != tuple(shape):
        raise ValueError(f"mask shape {mask.shape} does not match the data shape {tuple(shape)}")
    if not mask.any():
        raise ValueError("empty scoring mask")
    return mask


def _inside(a, mask, name) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    if a.shape[a.ndim - mask.ndim:] != mask.shape:
        raise ValueError(f"{name} shape {a.shape} does not match the mask shape {mask.shape}")
    v = a[..., mask]
    if not np.isfinite(v).all():
        raise ValueError(f"{name} has NaN or infinite values inside the scoring mask")
    return v


def _outcomes(y, mask) -> np.ndarray:
    v = _inside(y, mask, "outcomes")
    if not np.isin(v, (0.0, 1.0)).all():
        raise ValueError("outcomes must be 0 or 1 inside the scoring mask")
    return v


def _probabilities(p, mask, name="forecast") -> np.ndarray:
    v = _inside(np.broadcast_to(np.asarray(p, dtype=np.float64), mask.shape), mask, name)
    if ((v < 0) | (v > 1)).any():
        raise ValueError(f"{name} probabilities must lie in [0, 1] inside the scoring mask")
    return v


def _yp(y, p, mask):
    mask = _mask(mask, np.shape(y))
    return _outcomes(y, mask), _probabilities(p, mask)


# ------------------------------------------------------------------------------------ probability forecasts
def brier(y, p, mask) -> float:
    """Mean squared difference between probability and outcome over the scored cells."""
    yv, pv = _yp(y, p, mask)
    return float(np.mean((pv - yv) ** 2))


def brier_skill(y, p, reference, mask) -> float:
    """``1 - BS(p) / BS(reference)``; positive favours ``p``. NaN when the reference Brier score is 0.

    ``reference`` is an array or a scalar. Persistence for the new-burn quantity is ``reference=0`` (its Brier
    score is the observed frequency); calibrated best dilation is passed as its probability field.
    """
    yv, pv = _yp(y, p, mask)
    rv = _probabilities(reference, np.asarray(mask), "reference")
    bs_ref = np.mean((rv - yv) ** 2)
    return float("nan") if bs_ref == 0 else float(1.0 - np.mean((pv - yv) ** 2) / bs_ref)


def reliability(y, p, mask, edges=RELIABILITY_EDGES) -> list[dict]:
    """Reliability-diagram rows: one row for p == 0 exactly, then bins [lower, upper) over p > 0 (last bin closed).

    Each row: lower, upper, count, forecast_sum, observed_sum, mean_forecast, observed_frequency (None if empty).
    """
    yv, pv = _yp(y, p, mask)
    edges = np.asarray(edges, dtype=np.float64)
    if edges[0] != 0 or edges[-1] != 1 or not (np.diff(edges) > 0).all():
        raise ValueError("edges must increase strictly from 0 to 1")
    zero = pv == 0
    index = np.clip(np.searchsorted(edges, pv, side="right") - 1, 0, len(edges) - 2)
    groups = [(0.0, 0.0, zero)] + [(edges[b], edges[b + 1], (index == b) & ~zero) for b in range(len(edges) - 1)]
    rows = []
    for lower, upper, use in groups:
        n = int(use.sum())
        rows.append(dict(lower=float(lower), upper=float(upper), count=n,
                         forecast_sum=float(pv[use].sum()), observed_sum=float(yv[use].sum()),
                         mean_forecast=float(pv[use].mean()) if n else None,
                         observed_frequency=float(yv[use].mean()) if n else None))
    return rows


def _ece_of(rows: list[dict]) -> float:
    return sum(abs(r["forecast_sum"] - r["observed_sum"]) for r in rows) / sum(r["count"] for r in rows)


def ece(y, p, mask, edges=RELIABILITY_EDGES) -> float:
    """Expected calibration error over the reliability rows: sum over rows of |forecast_sum - observed_sum| / N."""
    return _ece_of(reliability(y, p, mask, edges))


def reliability_from_sums(count, forecast_sum, observed_sum, edges=RELIABILITY_EDGES) -> list[dict]:
    """``reliability`` rows from per-row sums pooled over windows (the sums of ``reliability`` rows add exactly)."""
    edges = np.asarray(edges, dtype=np.float64)
    bounds = [(0.0, 0.0)] + list(zip(edges[:-1], edges[1:]))
    if not len(count) == len(forecast_sum) == len(observed_sum) == len(bounds):
        raise ValueError(f"reliability sums need {len(bounds)} rows (p == 0, then the bins of the edges)")
    rows = []
    for (lower, upper), n, f, o in zip(bounds, count, forecast_sum, observed_sum):
        n = int(n)
        rows.append(dict(lower=float(lower), upper=float(upper), count=n, forecast_sum=float(f), observed_sum=float(o),
                         mean_forecast=float(f) / n if n else None, observed_frequency=float(o) / n if n else None))
    return rows


def ece_from_sums(count, forecast_sum, observed_sum) -> np.ndarray:
    """ECE from per-row sums ``[..., rows]`` (vectorized over leading axes, for ``fire_bootstrap``)."""
    count, f, o = (np.asarray(a, dtype=np.float64) for a in (count, forecast_sum, observed_sum))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.abs(f - o).sum(axis=-1) / count.sum(axis=-1)


def average_precision(y, p, mask) -> float:
    """Step-wise average precision, tied forecasts grouped (``wildfire.baselines``). NaN without positives."""
    yv, pv = _yp(y, p, mask)
    value = _baselines._average_precision(yv, pv)
    return float("nan") if value is None else float(value)


def level_counts(y, level, mask, levels: int) -> tuple[np.ndarray, np.ndarray]:
    """Scored cells and positives per integer forecast level ``0 .. levels - 1`` (e.g. the number of members that
    burn a cell, for a K-member share with ``levels = K + 1``). Sums pool over windows; see
    ``average_precision_from_counts``."""
    mask = _mask(mask, np.shape(y))
    yv = _outcomes(y, mask)
    lv = _inside(level, mask, "levels")
    if ((lv != np.round(lv)) | (lv < 0) | (lv >= levels)).any():
        raise ValueError(f"levels must be integers 0..{levels - 1} inside the scoring mask")
    lv = lv.astype(int)
    return np.bincount(lv, minlength=levels), np.bincount(lv, weights=yv, minlength=levels).round().astype(int)


def average_precision_from_counts(cells, positives) -> np.ndarray:
    """``average_precision`` from cells and positives per forecast level, levels in increasing forecast order
    (``level_counts``). Exact, not binned, when each level is one forecast value (a K-member share): cells of one
    level are one tie group. Vectorized over leading axes (for ``fire_bootstrap``); NaN without positives."""
    c = np.asarray(cells, dtype=np.float64)[..., ::-1]
    t = np.asarray(positives, dtype=np.float64)[..., ::-1]
    seen, hits = np.cumsum(c, axis=-1), np.cumsum(t, axis=-1)
    precision = np.where(seen > 0, hits / np.where(seen > 0, seen, 1.0), 0.0)     # at the end of each tie group
    total = t.sum(axis=-1)
    return np.where(total > 0, (precision * t).sum(axis=-1) / np.where(total > 0, total, 1.0), np.nan)


def summary(y, p, mask, *, reference=None, edges=RELIABILITY_EDGES) -> dict:
    """Pooled scores on one mask: ``wildfire.baselines.score`` fields plus base rate, ECE, reliability rows and,
    if ``reference`` is given, the Brier skill against it. ``bss_vs_persistence`` comes from ``score``."""
    yv, pv = _yp(y, p, mask)
    out = _baselines.score(yv, pv)
    rows = reliability(y, p, mask, edges)
    out.update(base_rate=float(yv.mean()), ece=_ece_of(rows), reliability=rows)
    if reference is not None:
        out["brier_skill_vs_reference"] = brier_skill(y, p, reference, mask)
    return out


# --------------------------------------------------------------------------------- Fractions Skill Score
def neighbourhood_fraction(field, mask, n: int) -> np.ndarray:
    """Mean of ``field`` over the scored cells of the n x n window around each cell (NaN where there are none).

    Cells outside the mask or outside the grid belong to no window; ``field`` may be NaN outside the mask.
    """
    if n < 1 or n % 2 == 0:
        raise ValueError("the neighbourhood size must be a positive odd number of cells")
    mask = np.asarray(mask, dtype=bool)
    values = np.where(mask, np.asarray(field, dtype=np.float64), 0.0)
    total = ndimage.uniform_filter(values, size=n, mode="constant", cval=0.0)
    count = ndimage.uniform_filter(mask.astype(np.float64), size=n, mode="constant", cval=0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(count > 0.5 / n**2, np.clip(total / count, 0.0, 1.0), np.nan)


def fss_terms(y, p, mask, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Per scored cell: ``(Pf - Po)^2`` and ``Pf^2 + Po^2`` from the n x n masked fractions (Roberts & Lean 2008).

    Pool windows and fires by summing both terms; FSS = 1 - sum(first) / sum(second).
    """
    _yp(y, p, mask)
    mask = np.asarray(mask)
    pf = neighbourhood_fraction(p, mask, n)[mask]
    po = neighbourhood_fraction(y, mask, n)[mask]
    return (pf - po) ** 2, pf ** 2 + po ** 2


def fss(y, p, mask, n: int) -> float:
    """Fractions Skill Score at neighbourhood size n (cells). NaN when forecast and outcome are both all zero."""
    num, den = fss_terms(y, p, mask, n)
    return float("nan") if den.sum() == 0 else float(1.0 - num.sum() / den.sum())


def fss_scales(y, p, mask, sizes=FSS_SIZES) -> dict[int, float]:
    return {int(n): fss(y, p, mask, n) for n in sizes}


def fss_useful(observed_fraction: float) -> float:
    """Roberts & Lean's 'useful' level 0.5 + f0 / 2, with f0 the observed fraction over the domain."""
    return 0.5 + observed_fraction / 2.0


# ------------------------------------------------------------------------------- ensembles and arrival time
def hourly_arrival(hours_after_cutoff, horizon_h: int) -> np.ndarray:
    """Map arrival times (hours after the cutoff) to the scoring lattice.

    (h - 1, h] -> h for h = 1..horizon; later or never (+inf) -> horizon + 1 (censored); at or before the cutoff
    -> 0 (not in the new-burn cohort); NaN (unknown) stays NaN.
    """
    a = np.asarray(hours_after_cutoff, dtype=np.float64)
    with np.errstate(invalid="ignore"):
        out = np.where(a > horizon_h, horizon_h + 1.0, np.ceil(a))
        return np.where(a <= 0, 0.0, out)


def _members(members, obs, mask):
    mask = _mask(mask, np.shape(obs))
    x, o = _inside(members, mask, "members"), _inside(obs, mask, "observations")
    if x.ndim != 2:
        raise ValueError("members must have shape [K, *obs.shape]")
    return x, o


def _lattice(members, obs, mask, horizon_h: int):
    x, o = _members(members, obs, mask)
    for v, name in ((x, "members"), (o, "observations")):
        if ((v != np.round(v)) | (v < 1) | (v > horizon_h + 1)).any():
            raise ValueError(f"{name} must be lattice arrival hours 1..{horizon_h + 1} inside the scoring mask "
                             "(cells burned at the cutoff are not in the scored cohort)")
    return x, o


def crps_arrival_terms(members, obs, mask, horizon_h: int, *, fair: bool = False) -> np.ndarray:
    """Per scored cell, the CRPS (hours) of the member arrival distribution, censored at the horizon.

    ``CRPS = sum_{i=1..H} (F_i - 1{obs <= i})^2 * 1 h`` with ``F_i`` the share of members burned by hour i: the
    Brier scores of "burned by hour i" summed over the hourly leads. ``fair=True`` subtracts
    ``F_i (1 - F_i) / (K - 1)`` per lead (Ferro 2014), which removes the penalty on small ensembles.
    """
    x, o = _lattice(members, obs, mask, horizon_h)
    k = x.shape[0]
    if fair and k < 2:
        raise ValueError("the fair CRPS needs at least two members")
    total = np.zeros(o.shape)
    for i in range(1, horizon_h + 1):
        f = (x <= i).mean(axis=0)
        total += (f - (o <= i)) ** 2
        if fair:
            total -= f * (1.0 - f) / (k - 1)
    return total


def crps_arrival(members, obs, mask, horizon_h: int, *, fair: bool = False) -> float:
    return float(crps_arrival_terms(members, obs, mask, horizon_h, fair=fair).mean())


def rank_histogram(members, obs, mask, *, seed: int) -> dict:
    """Counts of the observation's rank among the K members (0..K); ties broken uniformly at random (Hamill 2001).

    ``fully_tied`` counts cells where every member equals the observation: their ranks are uniform by
    construction, so many of them flatten the histogram without showing calibration.
    """
    x, o = _members(members, obs, mask)
    below, ties = (x < o).sum(axis=0), (x == o).sum(axis=0)
    rank = below + np.random.default_rng(seed).integers(0, ties + 1)
    return dict(counts=np.bincount(rank, minlength=x.shape[0] + 1).tolist(), cells=int(o.size),
                fully_tied=int((ties == x.shape[0]).sum()), seed=int(seed))


def spread_skill_terms(members, obs, mask) -> tuple[np.ndarray, np.ndarray]:
    """Per scored cell: the unbiased member variance ``s^2`` and the squared error of the ensemble mean. Both sums
    pool over windows (``spread_skill_from_sums``)."""
    x, o = _members(members, obs, mask)
    if x.shape[0] < 2:
        raise ValueError("spread needs at least two members")
    return x.var(axis=0, ddof=1), (x.mean(axis=0) - o) ** 2


def spread_rows(var, sd_edges_h=SPREAD_SD_EDGES_H) -> np.ndarray:
    """Fixed spread row of each cell from its member variance: 0 for sd = 0, then (0, e_1), [e_1, e_2), ..., [e_n,
    inf) with ``e = sd_edges_h`` (hours). Unlike equal-count groups, fixed rows pool over windows by summing."""
    edges = np.asarray(sd_edges_h, dtype=np.float64)
    if not (edges > 0).all() or not (np.diff(edges) > 0).all():
        raise ValueError("spread edges must be positive and increasing")
    sd = np.sqrt(np.asarray(var, dtype=np.float64))
    return np.where(sd == 0, 0, 1 + np.searchsorted(edges, sd, side="right"))


def spread_row_bounds(sd_edges_h=SPREAD_SD_EDGES_H) -> list[tuple[float, float]]:
    """``(lower, upper)`` member sd (hours) of each fixed spread row; the first row is sd = 0 exactly."""
    edges = [float(e) for e in sd_edges_h]
    return [(0.0, 0.0), (0.0, edges[0])] + list(zip(edges, edges[1:] + [float("inf")]))


def spread_skill_from_sums(members: int, var_sum, err2_sum) -> np.ndarray:
    """Spread-skill ratio ``sqrt((K + 1) / K * sum s^2 / sum err^2)`` from pooled sums (vectorized over leading axes,
    for ``fire_bootstrap``; NaN or inf where the error sum is 0)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.sqrt((members + 1) / members * np.asarray(var_sum, float) / np.asarray(err2_sum, float))


def spread_row(k: int, n, var_sum, err2_sum, **bounds) -> dict:
    """One spread-skill row of ``n`` cells from its sums (K = ``k`` members); empty rows have None values."""
    if not n:
        return dict(**bounds, cells=0, spread=None, rmse=None, ratio=None)
    spread, rmse = float(np.sqrt((k + 1) / k * var_sum / n)), float(np.sqrt(err2_sum / n))
    return dict(**bounds, cells=int(n), spread=spread, rmse=rmse, ratio=spread / rmse if rmse > 0 else float("nan"))


def spread_skill(members, obs, mask, *, bins: int = 10, sd_edges_h=None) -> dict:
    """Ensemble spread against the error of the ensemble mean (Fortin et al. 2014).

    If the observation behaves like one more member, ``E[(mean - obs)^2] = (K + 1) / K * E[s^2]`` with ``s^2`` the
    unbiased member variance. ``spread = sqrt((K + 1) / K * mean s^2)``; ``ratio = spread / rmse``: 1 consistent,
    below 1 overconfident, above 1 overdispersed. Rows: equal-count groups of cells sorted by ``s^2``, or with
    ``sd_edges_h`` the fixed spread rows of ``spread_rows`` (the rows that pooled result rows carry).
    """
    var, err2 = spread_skill_terms(members, obs, mask)
    k = np.shape(members)[0]
    if sd_edges_h is None:
        groups = [g for g in np.array_split(np.argsort(var, kind="stable"), bins) if len(g)]
        rows = [spread_row(k, len(g), var[g].sum(), err2[g].sum()) for g in groups]
    else:
        index = spread_rows(var, sd_edges_h)
        rows = [spread_row(k, int((index == i).sum()), var[index == i].sum(), err2[index == i].sum(), lower=lo,
                            upper=hi) for i, (lo, hi) in enumerate(spread_row_bounds(sd_edges_h))]
    return dict(**spread_row(k, var.size, var.sum(), err2.sum()), members=k, rows=rows)


# -------------------------------------------------------------------------------- whole-fire bootstrap
def fire_bootstrap(fire, terms, statistic: Callable[[np.ndarray], np.ndarray], *, draws: int = 10000,
                   seed: int = BOOTSTRAP_SEED, level: float = 0.95, block_elements: int = 4_000_000) -> dict:
    """Whole-fire bootstrap of ``statistic`` applied to pooled additive per-entry terms.

    ``fire[n]``: the fire of each scored entry (cell x window); ``terms[n, m]``: additive terms such as squared
    errors; ``statistic`` maps summed terms ``[..., m]`` to the metric and must be vectorized over leading axes.
    Each draw resamples whole fires with replacement and pools their sums (a fire drawn twice counts twice), as
    ``wildfire.baselines.paired_fire_bootstrap`` does. Percentile interval over the defined draws;
    ``undefined_draws`` counts draws where the statistic is NaN or infinite. Draws are pooled in blocks of at most
    ``block_elements`` gathered values (bounded memory for many terms); the result does not depend on the block size.
    """
    fire = np.asarray(fire)
    terms = np.asarray(terms, dtype=np.float64)
    terms = terms[:, None] if terms.ndim == 1 else terms
    if terms.shape[0] != fire.shape[0] or fire.ndim != 1:
        raise ValueError("fire must be a vector with one entry per row of terms")
    if not np.isfinite(terms).all():
        raise ValueError("terms must be finite")
    fires, inverse = np.unique(fire, return_inverse=True)
    sums = np.zeros((len(fires), terms.shape[1]))
    np.add.at(sums, inverse, terms)
    sampled = np.random.default_rng(seed).integers(0, len(fires), size=(draws, len(fires)))
    step = max(1, int(block_elements) // max(1, sampled.shape[1] * sums.shape[1]))
    with np.errstate(invalid="ignore", divide="ignore"):
        values = np.concatenate([np.asarray(statistic(sums[sampled[i:i + step]].sum(axis=1)), dtype=np.float64)
                                 .reshape(-1) for i in range(0, draws, step)]) if draws else np.zeros(0)
        point = float(statistic(sums.sum(axis=0)))
    defined = np.isfinite(values)
    lower, upper = (np.quantile(values[defined], [(1 - level) / 2, (1 + level) / 2]) if defined.any()
                    else (np.nan, np.nan))
    return dict(point=point, interval=[float(lower), float(upper)], level=level,
                excludes_zero=bool(lower > 0 or upper < 0), fires=int(len(fires)), draws=int(draws),
                seed=int(seed), undefined_draws=int((~defined).sum()))


def _fire_ids(fire, y, mask) -> np.ndarray:
    fire = np.asarray(fire)
    if fire.shape != np.shape(y):
        raise ValueError("fire must hold one fire id per entry of y")
    return fire[np.asarray(mask)]


def paired_brier_bootstrap(fire, y, p, reference, mask, *, draws: int = 10000, seed: int = BOOTSTRAP_SEED) -> dict:
    """Brier(p) - Brier(reference) with a whole-fire percentile interval: ``wildfire.baselines.paired_fire_bootstrap``
    on the scored entries. Negative favours ``p``."""
    yv, pv = _yp(y, p, mask)
    mask = np.asarray(mask)
    rv = _probabilities(reference, mask, "reference")
    return _baselines.paired_fire_bootstrap(_fire_ids(fire, y, mask), yv, pv, rv, draws=draws, seed=seed)


def brier_skill_bootstrap(fire, y, p, reference, mask, *, draws: int = 10000, seed: int = BOOTSTRAP_SEED) -> dict:
    """Brier skill of ``p`` against ``reference`` with a whole-fire percentile interval. With the same seed it uses
    the same draws as ``paired_brier_bootstrap``, and in every draw the skill is positive exactly when the Brier
    difference is negative."""
    yv, pv = _yp(y, p, mask)
    mask = np.asarray(mask)
    rv = _probabilities(reference, mask, "reference")
    terms = np.stack([(pv - yv) ** 2, (rv - yv) ** 2], axis=1)
    return fire_bootstrap(_fire_ids(fire, y, mask), terms, lambda s: 1.0 - s[..., 0] / s[..., 1],
                          draws=draws, seed=seed)
