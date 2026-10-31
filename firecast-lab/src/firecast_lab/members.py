"""Spatially coherent scenario members from per-cell cumulative burn probabilities.

Input ``cum[L + 1, H, W]``: the probability that a cell has burned by lead hour ``l`` after the cutoff
(``l = 0`` is the cutoff state, ``l = L`` the horizon). It must not decrease with ``l``; NaN = unknown.

Output: member arrival fields ``hours[K, H, W]``, in hours after the cutoff:

    (l - 1, l]   first burns in lead hour l            +inf   not burned by the horizon L
    initial_h    burned at the cutoff (default 0.0)    NaN    unknown (wherever ``cum`` is NaN)

Rule. Member k has burned cell x by lead l iff ``U_k(x) <= cum[l, x]``, with ONE uniform field ``U_k`` per member
shared by every lead. Arrival is therefore monotone by construction, and P(member burned by l) = ``cum[l]``
exactly: marginals are reproduced up to the Monte Carlo error of K members. Inside the hour the arrival inverts the
piecewise-linear CDF through the hourly values (uniform timing within the hour, driven by the same ``U_k``), so
``ceil(hours)`` is exactly the hourly lattice that ``metrics.hourly_arrival`` scores.

Couplings: how ``U_k`` varies in space. Both have exactly uniform marginals.

- ``shared``: one uniform per member for every cell (comonotone). Member k is the super-level set
  ``{cum >= U_k}``: nested, maximally coherent members. A set of cells stays clear in a member with probability
  ``1 - max(cum over the set)``, the smallest union probability the marginals allow, so ``shared`` is the LEAST
  conservative coupling for "every member clear".
- ``copula``: ``U_k = Phi(Z_k)``, ``Z_k`` a stationary unit-variance Gaussian field with correlation
  ``exp(-r^2 / (2 L^2))`` at a distance of r cells. The correlation length L is declared and recorded.
  L -> infinity recovers ``shared``; L -> 0 tends to independent cells, the most conservative coupling, whose
  speckled members are not spatially coherent.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage, special

COUPLINGS = ("shared", "copula")


def check_cum(cum) -> np.ndarray:
    """Validate cumulative probabilities ``[L + 1, H, W]``; returns them as float64."""
    cum = np.asarray(cum, dtype=np.float64)
    if cum.ndim != 3 or cum.shape[0] < 2:
        raise ValueError("cum must have shape [L + 1, H, W] with L >= 1 (lead 0 is the cutoff state)")
    known = ~np.isnan(cum)
    if (known != known[0]).any():
        raise ValueError("a cell must be unknown (NaN) at every lead or at none")
    v = cum[:, known[0]]
    if ((v < 0) | (v > 1)).any():
        raise ValueError("probabilities must lie in [0, 1]")
    if (np.diff(v, axis=0) < 0).any():
        raise ValueError("cumulative probabilities must not decrease with lead")
    return cum


def _initial(cum: np.ndarray, initial_h) -> np.ndarray:
    if initial_h is None:
        return np.zeros(cum.shape[1:])
    initial = np.asarray(initial_h, dtype=np.float64)
    if initial.shape != cum.shape[1:]:
        raise ValueError("initial_h must have the grid shape")
    with np.errstate(invalid="ignore"):
        if (initial[cum[0] > 0] > 0).any():
            raise ValueError("initial_h (arrival of cells burned at the cutoff) must be <= 0 hours after the cutoff")
    return initial


def _threshold_one(cum: np.ndarray, u, initial: np.ndarray) -> np.ndarray:
    """Arrival hours of one member from its uniform field ``u`` (scalar or ``[H, W]``, in (0, 1])."""
    last = cum.shape[0] - 1
    lead = (cum < u).sum(axis=0)                    # first lead l with u <= cum[l]; last + 1 means never
    lo = np.take_along_axis(cum, np.clip(lead - 1, 0, last)[None], 0)[0]
    hi = np.take_along_axis(cum, np.clip(lead, 0, last)[None], 0)[0]
    with np.errstate(invalid="ignore", divide="ignore"):
        t = lead - 1 + (u - lo) / (hi - lo)         # hi > lo whenever 1 <= lead <= last
    t = np.maximum(t, np.nextafter(lead - 1.0, np.inf))   # keep (l - 1, l] after rounding
    hours = np.where(lead == 0, initial, np.where(lead > last, np.inf, t))
    hours[np.isnan(cum[0])] = np.nan
    return hours


def threshold(cum, uniforms, initial_h=None) -> np.ndarray:
    """Member arrival hours ``[K, H, W]`` from explicit uniform fields ``[K, H, W]`` in (0, 1] (module doc)."""
    cum = check_cum(cum)
    u = np.asarray(uniforms, dtype=np.float64)
    if u.ndim != 3 or u.shape[1:] != cum.shape[1:]:
        raise ValueError("uniforms must have shape [K, H, W] on the grid of cum")
    if ((u <= 0) | (u > 1)).any():
        raise ValueError("uniforms must lie in (0, 1]")
    initial = _initial(cum, initial_h)
    return np.stack([_threshold_one(cum, uk, initial) for uk in u])


def gaussian_field(shape, length_cells: float, rng: np.random.Generator) -> np.ndarray:
    """Unit-variance stationary Gaussian field, correlation ``exp(-r^2 / (2 L^2))`` at a distance of r cells.

    White noise smoothed by a Gaussian kernel of sd ``L / sqrt(2)`` (the kernel convolved with itself has sd L).
    The noise is drawn on a grid padded beyond the kernel radius, so every cell sees the whole kernel: the field is
    stationary up to the grid edge, with variance exactly the sum of the squared kernel weights.
    """
    if not np.isfinite(length_cells) or not length_cells > 0:
        raise ValueError("the correlation length must be a positive number of cells")
    sigma = length_cells / np.sqrt(2.0)
    pad = int(np.ceil(4.0 * sigma)) + 1             # >= gaussian_filter's radius int(4 sigma + 0.5)
    impulse = np.zeros((2 * pad + 1, 2 * pad + 1))
    impulse[pad, pad] = 1.0
    norm = np.sqrt((ndimage.gaussian_filter(impulse, sigma, mode="constant") ** 2).sum())
    h, w = shape
    noise = rng.standard_normal((h + 2 * pad, w + 2 * pad))
    return ndimage.gaussian_filter(noise, sigma, mode="constant")[pad:pad + h, pad:pad + w] / norm


def coherent_members(cum, K: int, *, seed, coupling: str = "shared", length_cells: float | None = None,
                     initial_h=None) -> np.ndarray:
    """K coherent member arrival fields ``[K, H, W]`` (module doc). Deterministic given ``seed``."""
    cum = check_cum(cum)
    if not (isinstance(K, (int, np.integer)) and K >= 1):
        raise ValueError("K must be a positive integer")
    if coupling not in COUPLINGS:
        raise ValueError(f"coupling must be one of {COUPLINGS}")
    if coupling == "copula" and length_cells is None:
        raise ValueError("the Gaussian copula needs a declared correlation length (length_cells)")
    initial = _initial(cum, initial_h)
    rng = np.random.default_rng(seed)
    hours = np.empty((K, *cum.shape[1:]))
    for k in range(K):
        if coupling == "shared":
            u = 1.0 - rng.random()                  # (0, 1]: u <= 0 never happens, so cum = 0 never burns
        else:
            u = np.clip(special.ndtr(gaussian_field(cum.shape[1:], length_cells, rng)),
                        np.finfo(np.float64).tiny, 1.0)
        hours[k] = _threshold_one(cum, u, initial)
    return hours


def burned_by(hours, lead_h: float) -> np.ndarray:
    """Share of members that newly burn each cell by ``lead_h`` (``0 < hours <= lead_h``); NaN where unknown."""
    hours = np.asarray(hours, dtype=np.float64)
    with np.errstate(invalid="ignore"):
        p = ((hours > 0) & (hours <= lead_h)).mean(axis=0)
    return np.where(np.isnan(hours).any(axis=0), np.nan, p)
