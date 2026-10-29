"""Fireline intensity, flame length, flame height and tilt.

* Byram fireline intensity I = H w R (kW/m) with H the heat content (kJ/kg, default 18,608 kJ/kg, the FBFM40 nominal
  value of the frozen export), w the fuel consumed in the flaming front (kg/m2, default 0.1 x 10 = 1.0 kg/m2, the
  export's flaming-phase consumption; a per-cell [H, W] array is accepted, for example from LANDFIRE/FCCS loadings) and
  R the rate of spread (m/s).
* Byram (1959) flame length L = 0.0775 I^0.46 (L in m, I in kW/m).
* Tilt: tan(theta) = 1.4 U / sqrt(g L) (Froude-number form for wind-driven surface fires, attributed to Nelson and
  Adkins 1986; the coefficient was not verified against the paper here). Flame height L cos(theta), lean L sin(theta)
  in the wind direction. Without a wind field (every frozen routing packet) the flame is vertical: height = L.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any, Mapping

import numpy as np

from . import provenance as PV


@dataclass(frozen=True)
class FuelParameters:
    heat_content_kj_kg: Any = PV.HEAT_CONTENT_KJ_KG
    consumed_kg_m2: Any = PV.FLAMING_CONSUMPTION_KG_M2
    emissive_power_kw_m2: Any = PV.EMISSIVE_POWER_SURFACE_KW_M2
    residence_s: Any = PV.POINT_RESIDENCE_S
    wind_u_m_s: Any = None              # eastward wind component, scalar or [H, W]; None = no wind field
    wind_v_m_s: Any = None              # northward
    transmissivity: float = PV.ATMOSPHERIC_TRANSMISSIVITY
    receiver_height_m: float = PV.RECEIVER_HEIGHT_M
    cutoff_radius_m: float = PV.CUTOFF_RADIUS_M
    r_max_m_s: float = PV.MAX_SPREAD_RATE_M_S
    tilt_coefficient: float = PV.TILT_COEFFICIENT
    flame_height_scale: float = 1.0     # sensitivity multiplier on the Byram flame length (1.0 = Byram)

    @classmethod
    def coerce(cls, fuel):
        if fuel is None:
            return cls()
        if isinstance(fuel, cls):
            return fuel
        if isinstance(fuel, Mapping):
            names = {f.name for f in fields(cls)}
            unknown = set(fuel) - names
            if unknown:
                raise ValueError("unknown fuel parameters: %s" % sorted(unknown))
            return cls(**dict(fuel))
        raise TypeError("fuel must be FuelParameters, a mapping or None")

    def with_(self, **kw):
        return replace(self, **kw)

    def at(self, name, r, c):
        v = getattr(self, name)
        if v is None:
            return None
        a = np.asarray(v, dtype=float)
        if a.ndim == 0:
            return np.full(np.shape(r), float(a))
        return a[r, c]

    def max_of(self, name):
        v = getattr(self, name)
        return None if v is None else float(np.max(np.asarray(v, dtype=float)))

    @property
    def has_wind(self):
        return self.wind_u_m_s is not None and self.wind_v_m_s is not None


def byram_intensity_kw_m(R_m_s, heat_content_kj_kg=PV.HEAT_CONTENT_KJ_KG, consumed_kg_m2=PV.FLAMING_CONSUMPTION_KG_M2):
    return np.asarray(heat_content_kj_kg, float) * np.asarray(consumed_kg_m2, float) * np.asarray(R_m_s, float)


def byram_flame_length_m(intensity_kw_m):
    I = np.maximum(np.asarray(intensity_kw_m, float), 0.0)
    return PV.BYRAM_FLAME_LENGTH_COEFF * I ** PV.BYRAM_FLAME_LENGTH_EXPONENT


def tilt_angle_rad(flame_length_m, wind_speed_m_s, coefficient=PV.TILT_COEFFICIENT):
    L = np.asarray(flame_length_m, float)
    U = np.abs(np.asarray(wind_speed_m_s, float))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(L > 0, coefficient * U / np.sqrt(PV.GRAVITY_M_S2 * np.maximum(L, 1e-300)), 0.0)
    return np.arctan(t)


def flame_geometry(pieces, fuel):
    """Per-piece intensity (kW/m), flame length (m), height (m), tilt (rad), lean unit vector and E (kW/m2)."""
    fuel = FuelParameters.coerce(fuel)
    r, c = pieces["host_r"], pieces["host_c"]
    Hc = fuel.at("heat_content_kj_kg", r, c)
    w = fuel.at("consumed_kg_m2", r, c)
    E = fuel.at("emissive_power_kw_m2", r, c)
    I = byram_intensity_kw_m(pieces["R"], Hc, w)
    L = byram_flame_length_m(I) * fuel.flame_height_scale
    if fuel.has_wind:
        u = fuel.at("wind_u_m_s", r, c); v = fuel.at("wind_v_m_s", r, c)
        U = np.hypot(u, v)
        th = tilt_angle_rad(L, U, fuel.tilt_coefficient)
        with np.errstate(divide="ignore", invalid="ignore"):
            lx = np.where(U > 0, u / U, 0.0); ly = np.where(U > 0, v / U, 0.0)
    else:
        th = np.zeros_like(L); lx = np.zeros_like(L); ly = np.zeros_like(L)
    return {"intensity": I, "length": L, "height": L * np.cos(th), "reach": L * np.sin(th), "tilt": th,
            "lean_x": lx, "lean_y": ly, "E": E}


def max_flame_extent(R_upper, r, c, fuel):
    """Upper bounds of flame height and horizontal lean for rate <= R_upper in host cells (r, c)."""
    fuel = FuelParameters.coerce(fuel)
    Hc = fuel.at("heat_content_kj_kg", r, c)
    w = fuel.at("consumed_kg_m2", r, c)
    L = byram_flame_length_m(byram_intensity_kw_m(R_upper, Hc, w)) * fuel.flame_height_scale
    # height L cos(theta) <= L; lean L sin(theta) <= L sin(theta_max) with theta_max from the host wind (theta grows with
    # U and decreases with L, but sin(theta) <= 1 makes L an unconditional bound; use the exact maximum when windless)
    reach = np.zeros_like(L) if not fuel.has_wind else L
    return L, reach
