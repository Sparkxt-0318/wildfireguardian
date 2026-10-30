"""Byram fireline intensity and a documented wind-tilt scenario.

I = H*w*R uses H in kJ/kg, w in kg/m2, R in m/s, giving kW/m.
L = 0.0775*I**0.46 is Byram's fuel-specific empirical relation.
Putnam's tilt relation, as reproduced by Weise and Biging (1996), Eq. 3,
is theta = atan(1.4*U/sqrt(g*L)). It is a scenario, not a Korean fit.
"""
from __future__ import annotations

import math
import numpy as np


def fireline_intensity(rate_m_s, consumed_fuel_kg_m2=1.0, heat_kj_kg=18608.0):
    values = [np.asarray(v, dtype=float) for v in (rate_m_s, consumed_fuel_kg_m2, heat_kj_kg)]
    if any(np.any(~np.isfinite(v) | (v < 0)) for v in values):
        raise ValueError("intensity inputs must be finite and nonnegative")
    return values[0] * values[1] * values[2]


def flame_length(intensity_kw_m):
    value = np.asarray(intensity_kw_m, dtype=float)
    if np.any(~np.isfinite(value) | (value < 0)):
        raise ValueError("intensity must be finite and nonnegative")
    return 0.0775 * value ** 0.46


def flame_geometry(length_m, wind_xy=(0.0, 0.0)):
    """Return vertical height, tilt radians and horizontal displacement of tip.

    Wind is the local horizontal vector in m/s. g=9.80665 m/s2 is conventional
    standard gravity. Zero wind gives an exactly vertical flame.
    """
    length = float(length_m)
    wind = np.asarray(wind_xy, dtype=float)
    if not math.isfinite(length) or length < 0 or wind.shape != (2,) or not np.isfinite(wind).all():
        raise ValueError("finite length and wind vector required")
    speed = float(np.linalg.norm(wind))
    angle = math.atan(1.4 * speed / math.sqrt(9.80665 * length)) if length > 0 else 0.0
    shift = wind / speed * length * math.sin(angle) if speed > 0 else np.zeros(2)
    return length * math.cos(angle), angle, tuple(shift)
