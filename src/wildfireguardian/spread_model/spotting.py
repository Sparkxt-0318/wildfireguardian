"""Spotting: stochastic ember (firebrand) transport that jumps the front.

Session 6, Deliverable 3. Spotting — embers lofted by the plume, carried
downwind, igniting new fires ahead of the main front — is the mechanism
that produces the ~1–2 km front jumps observed in wind-driven Korean pine
fires and which neither surface nor contiguous crown spread can reproduce.

**Honesty note on the formula.** The Session-6 task brief specified
"Albini 1979 ... use the simplified form:" but the formula text was
truncated in the brief. We therefore implement the standard published
Albini (1979) firebrand-transport chain, documented here, rather than
guessing the intended one-liner:

1. **Flame length** from Byram intensity (Byram 1959; Alexander 1982):
   ``L = 0.0775 · I^0.46``  (m, I in kW/m).
2. **Loft height** ``z = loft_ratio · L`` — firebrands are lofted to a few
   flame-lengths by the convective plume (Albini 1979; Ellis 2000).
3. **Maximum spot distance** from a ballistic-glide drift:
   ``D_max = drift_coeff · U10 · sqrt(z / g)`` (m) — a lofted brand falls
   over a glide time scaling as ``sqrt(z/g)`` while drifting at ~the 10-m
   wind. Constants are calibrated to Albini-1979 magnitudes (hundreds of m
   to ~1.5 km for crown-fire flames at 10–30 m/s) and are flagged as
   heuristic.

References: Albini, F.A. (1979). *Spot fire distance from burning trees — a
predictive model.* USDA FS GTR INT-56. Ellis, P.F. (2000), PhD thesis ANU
(firebrand flight). Sardoy, N. et al. (2008), *Combust. Flame* 154
(firebrand transport).

The transport is **stochastic**: each active-crown cell launches embers at
a documented per-minute probability; landing distance is sampled in
``[0.3, 1.0]·D_max`` and direction within a cone about the wind. Seeded
for reproducibility.
"""

from __future__ import annotations

import math

import numpy as np

G = 9.81  # m/s²

#: Heuristic constants (flagged; calibrated to Albini 1979 magnitudes).
DEFAULT_LOFT_RATIO: float = 4.0
DEFAULT_DRIFT_COEFF: float = 22.0
#: Probability per minute that an active-crown cell launches an igniting ember.
DEFAULT_SPOT_PROB_PER_MIN: float = 0.02
#: Half-angle (deg) of the downwind cone embers are thrown into.
DEFAULT_SPOT_CONE_DEG: float = 25.0


def flame_length_m(byram_intensity_kw_m: float) -> float:
    """Byram/Alexander flame length, m. ``L = 0.0775 · I^0.46``."""
    if byram_intensity_kw_m <= 0.0:
        return 0.0
    return 0.0775 * byram_intensity_kw_m ** 0.46


def max_spot_distance(
    flame_length_m_val: float, u_10m_ms: float,
    loft_ratio: float = DEFAULT_LOFT_RATIO,
    drift_coeff: float = DEFAULT_DRIFT_COEFF,
) -> float:
    """Maximum downwind spotting distance, m (Albini-1979-calibrated heuristic).

    ``D_max = drift_coeff · U10 · sqrt(loft_ratio · L / g)``.
    """
    if flame_length_m_val <= 0.0 or u_10m_ms <= 0.0:
        return 0.0
    z = loft_ratio * flame_length_m_val
    return drift_coeff * u_10m_ms * math.sqrt(z / G)


def sample_spot_landing(
    rng: np.random.Generator, d_max_m: float, wind_to_deg: float,
    cone_half_deg: float = DEFAULT_SPOT_CONE_DEG,
) -> tuple[float, float]:
    """Sample one ember landing as (distance_m, bearing_deg).

    Distance is uniform in ``[0.3, 1.0]·D_max`` (most brands land short of
    the maximum); bearing is uniform within ``±cone_half_deg`` of the
    downwind direction.
    """
    d = rng.uniform(0.3 * d_max_m, d_max_m)
    bearing = wind_to_deg + rng.uniform(-cone_half_deg, cone_half_deg)
    return d, bearing % 360.0


def landing_cell(
    i: int, j: int, distance_m: float, bearing_deg: float, cell_size_m: float,
) -> tuple[int, int]:
    """Grid cell an ember lands in, given source (i, j) and (distance, bearing).

    Bearing is compass 'blowing toward' (0=N, 90=E). Returns (ni, nj) where
    i increases southward, j eastward.
    """
    r = math.radians(bearing_deg)
    de = math.sin(r) * distance_m   # east
    dn = math.cos(r) * distance_m   # north
    dj = int(round(de / cell_size_m))
    di = int(round(-dn / cell_size_m))   # north is -i
    return i + di, j + dj


__all__ = [
    "G",
    "DEFAULT_LOFT_RATIO",
    "DEFAULT_DRIFT_COEFF",
    "DEFAULT_SPOT_PROB_PER_MIN",
    "DEFAULT_SPOT_CONE_DEG",
    "flame_length_m",
    "max_spot_distance",
    "sample_spot_landing",
    "landing_cell",
]
