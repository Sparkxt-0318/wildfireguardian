"""Soft hourly arrival labels from a kriged arrival-time mean and standard deviation.

The default training pipeline (``forecast/wildfire/data.py`` and
``forecast/wildfire/prepare.py``) labels cell ``i`` as newly burned in the hour
``(t-1, t]`` when the kriged arrival mean satisfies ``t-1 < mu_i <= t``.  This
module replaces that hard indicator by the probability of the same event under
an arrival time ``tau_i ~ Normal(mu_i, sd_i)``, optionally truncated to a
support interval (for example the event acquisition window) and optionally
conditioned on the cell still being unburned at the start of the hour.

Conventions match the loader: windows are half-open on the left, ``(a, b]``.
With ``sd == 0`` the result is exactly the hard indicator, so the soft label is
a strict generalisation.  All functions are pure NumPy/SciPy and read no data.

The kriging standard deviation is documented upstream as "model kriging
standard deviation, hours; not calibrated confidence interval"
(``forecast/wildfire/bundle.py``).  Treating it as the scale of a Gaussian
arrival-time error is a modelling assumption, not an established property.
"""
from __future__ import annotations

import numpy as np
from scipy.special import ndtr

__all__ = ["normal_interval_probability", "soft_window_labels", "hard_window_labels",
           "soft_next_hour_targets"]


def _as_float(x):
    return np.asarray(x, dtype=np.float64)


def normal_interval_probability(a, b, mean, sd):
    """P(a < tau <= b) for tau ~ Normal(mean, sd), elementwise and broadcast.

    ``sd == 0`` gives the exact indicator ``a < mean <= b``.  Upper-tail
    intervals are evaluated on the reflected side so that small probabilities
    far above the mean are not lost to cancellation.  ``a`` may be ``-inf``
    and ``b`` may be ``+inf``.  Invalid inputs (non-finite mean, negative or
    non-finite sd) give NaN.
    """
    a, b, mean, sd = np.broadcast_arrays(_as_float(a), _as_float(b), _as_float(mean), _as_float(sd))
    out = np.full(a.shape, np.nan)
    valid = np.isfinite(mean) & np.isfinite(sd) & (sd >= 0)
    if np.any(valid & (b < a)):
        raise ValueError("interval upper bound below lower bound")
    hard = valid & (sd == 0)
    out[hard] = ((a[hard] < mean[hard]) & (mean[hard] <= b[hard])).astype(np.float64)
    soft = valid & (sd > 0)
    if soft.any():
        m, s = mean[soft], sd[soft]
        za, zb = (a[soft] - m) / s, (b[soft] - m) / s
        upper = za > 0
        p = np.where(upper, ndtr(-za) - ndtr(-zb), ndtr(zb) - ndtr(za))
        out[soft] = np.clip(p, 0.0, 1.0)
    return out


def soft_window_labels(mean, sd, edges, *, support=None, conditional=False):
    """Probability that arrival falls in each window ``(edges[k], edges[k+1]]``.

    Parameters
    ----------
    mean, sd : array_like, same shape ``S`` (hours, same origin as ``edges``).
    edges : 1-D increasing array of length ``K+1``.
    support : optional ``(lo, hi)``.  The normal is truncated to ``(lo, hi]``
        and renormalised, so windows covering ``(lo, hi]`` sum to one.  Use
        this to keep mass inside the period during which arrival is known to
        have occurred (for example a finite reconstruction inside the event
        window).  Cells whose truncated mass is zero give NaN.
    conditional : if true, return the discrete hazard
        ``P(edges[k] < tau <= edges[k+1] | tau > edges[k])``, the target for
        a next-hour row that is only formed while the cell is unburned.
        Windows whose survival is zero give NaN (the cell is not at risk).

    Returns an array of shape ``(K, *S)``.
    """
    edges = _as_float(edges)
    if edges.ndim != 1 or len(edges) < 2 or np.any(np.diff(edges) <= 0):
        raise ValueError("edges must be a strictly increasing 1-D array of length >= 2")
    mean, sd = np.broadcast_arrays(_as_float(mean), _as_float(sd))
    shape = (len(edges) - 1,) + mean.shape
    lo_e = edges[:-1].reshape((-1,) + (1,) * mean.ndim)
    hi_e = edges[1:].reshape((-1,) + (1,) * mean.ndim)
    if support is not None:
        lo, hi = map(float, support)
        if not hi > lo:
            raise ValueError("support must satisfy hi > lo")
        a = np.clip(lo_e, lo, hi)
        b = np.clip(hi_e, lo, hi)
        mass = normal_interval_probability(lo, hi, mean, sd)
    else:
        a, b = lo_e, hi_e
        mass = np.ones(mean.shape)
    p = normal_interval_probability(np.broadcast_to(a, shape), np.broadcast_to(b, shape), mean, sd)
    with np.errstate(invalid="ignore", divide="ignore"):
        p = np.where(mass > 0, p / mass, np.nan)
        if conditional:
            upper = hi if support is not None else np.inf
            start = np.broadcast_to(a, shape)
            survival = normal_interval_probability(start, upper, mean, sd)
            survival = np.where(mass > 0, survival / mass, np.nan)
            p = np.where(survival > 0, p / np.where(survival > 0, survival, 1.0), np.nan)
            p = np.clip(p, 0.0, 1.0)
    return p


def hard_window_labels(mean, edges):
    """The loader's hard newly-burned indicator ``edges[k] < mean <= edges[k+1]``.

    Non-finite ``mean`` (no reconstructed arrival) gives zero, as in
    ``forecast/wildfire/data.py``, where unknown cells are masked separately.
    """
    edges = _as_float(edges)
    mean = _as_float(mean)
    lo = edges[:-1].reshape((-1,) + (1,) * mean.ndim)
    hi = edges[1:].reshape((-1,) + (1,) * mean.ndim)
    return ((mean > lo) & (mean <= hi) & np.isfinite(mean)).astype(np.float64)


def soft_next_hour_targets(mean, sd, hour_start, *, support=None, conditional=False, width=1.0):
    """Per-row soft target for prepared next-hour rows.

    ``mean``, ``sd`` and ``hour_start`` are 1-D row arrays (the cell's kriged
    mean/sd and the row's elapsed start hour).  Returns P(t < tau <= t+width)
    (or the conditional hazard), the drop-in replacement for the hard
    ``target`` written by ``prepare_event``.
    """
    mean, sd, t = np.broadcast_arrays(_as_float(mean), _as_float(sd), _as_float(hour_start))
    a, b = t, t + width
    if support is not None:
        lo, hi = map(float, support)
        a, b = np.clip(a, lo, hi), np.clip(b, lo, hi)
        mass = normal_interval_probability(lo, hi, mean, sd)
        upper = hi
    else:
        mass = np.ones(mean.shape)
        upper = np.inf
    p = normal_interval_probability(a, b, mean, sd)
    with np.errstate(invalid="ignore", divide="ignore"):
        p = np.where(mass > 0, p / mass, np.nan)
        if conditional:
            surv = normal_interval_probability(a, upper, mean, sd)
            surv = np.where(mass > 0, surv / mass, np.nan)
            p = np.where(surv > 0, np.clip(p / np.where(surv > 0, surv, 1.0), 0.0, 1.0), np.nan)
    return p
