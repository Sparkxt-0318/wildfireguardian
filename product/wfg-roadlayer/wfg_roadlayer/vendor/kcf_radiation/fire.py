"""Fire behaviour from rate of spread and fuel (METHOD.md sections 2-4). Units: m, s, kg, kJ, kW.

Every function is a published relation; the citation and its range are in METHOD.md and in the docstring.
Nothing here is fitted to this project's data.
"""
from __future__ import annotations

import math

import numpy as np


def byram_intensity(heat_kj_kg, consumed_kg_m2, ros_m_s):
    """Byram (1959) fireline intensity I = H w R (kW/m).
    H: heat yield (kJ/kg, Alexander 1982: ~18,000 kJ/kg after moisture and incomplete-combustion corrections);
    w: fuel consumed in the flaming front (kg/m2); R: rate of spread (m/s)."""
    return np.asarray(heat_kj_kg) * np.asarray(consumed_kg_m2) * np.asarray(ros_m_s)


def flame_length_byram(I_kw_m):
    """Byram (1959): L = 0.0775 I^0.46 (m; I in kW/m). Surface fires (FARSITE/FlamMap surface flame length)."""
    return 0.0775 * np.power(np.maximum(I_kw_m, 0.0), 0.46)


def flame_length_thomas(I_kw_m):
    """Thomas (1963): L = 0.0266 I^(2/3) (m; I in kW/m). Used for crown fires by FARSITE (Finney 1998) and
    FlamMap, after Rothermel (1991)."""
    return 0.0266 * np.power(np.maximum(I_kw_m, 0.0), 2.0 / 3.0)


def van_wagner_initiation_intensity(cbh_m, fmc_pct):
    """Van Wagner (1977) critical surface intensity for crown initiation:
    I0 = (0.010 * CBH * (460 + 25.9 * FMC))^1.5 (kW/m; CBH in m, FMC = foliar moisture content in %)."""
    return np.power(0.010 * np.asarray(cbh_m) * (460.0 + 25.9 * np.asarray(fmc_pct)), 1.5)


def van_wagner_active_ros(cbd_kg_m3):
    """Van Wagner (1977) critical spread rate for active crowning: R_active = 3.0 / CBD (m/min) -> m/s."""
    return (3.0 / np.asarray(cbd_kg_m3)) / 60.0


def crown_fraction_burned(ros_m_s, r_init_m_s, r_active_m_s):
    """Crown fraction burned, Van Wagner (1993) form as used by Scott and Reinhardt (2001, RMRS-RP-29, eq. 28-29):
    CFB = 1 - exp(-a_c (R - R'_init)), a_c = -ln(0.1) / (0.9 (R'_active - R'_init)); CFB = 0 below R'_init and
    1 at or above R'_active. Here R is the spread rate read from the arrival raster (see METHOD.md 3.3)."""
    R = np.asarray(ros_m_s, dtype=float)
    r0 = np.asarray(r_init_m_s, dtype=float)
    ra = np.asarray(r_active_m_s, dtype=float)
    span = np.maximum(ra - r0, 1e-12)
    ac = -math.log(0.1) / (0.9 * span)
    cfb = 1.0 - np.exp(-ac * (R - r0))
    cfb = np.where(R <= r0, 0.0, cfb)
    cfb = np.where(R >= ra, 1.0, cfb)
    return np.clip(cfb, 0.0, 1.0)


def fire_type_and_flame(ros_m_s, fuel, heat_kj_kg=18000.0):
    """Surface or crown fire, intensity and flame length for one fuel-parameter set (dict with keys
    surface_kg_m2, cfl_kg_m2, cbh_m, cbd_kg_m3, fmc_pct; canopy keys may be None for non-forest).

    Returns dict of arrays: I_surface, I0, crown (bool), cfb, I_total, L (m), law ('byram'|'thomas').
    Rule (FARSITE/FlamMap; Finney 1998, Scott and Reinhardt 2001): crown fire when I_surface >= I0; flame length
    then by Thomas (1963) from the total intensity H (w_surface + CFB * CFL) R, otherwise Byram (1959) from the
    surface intensity."""
    R = np.asarray(ros_m_s, dtype=float)
    Is = byram_intensity(heat_kj_kg, fuel["surface_kg_m2"], R)
    if fuel.get("cbh_m") is None or fuel.get("cfl_kg_m2") in (None, 0):
        L = flame_length_byram(Is)
        z = np.zeros_like(R)
        return {"I_surface": Is, "I0": np.full_like(R, np.inf), "crown": z.astype(bool), "cfb": z,
                "I_total": Is, "L": L, "thomas": z.astype(bool)}
    I0 = van_wagner_initiation_intensity(fuel["cbh_m"], fuel["fmc_pct"])
    crown = Is >= I0
    r_init = I0 / (heat_kj_kg * fuel["surface_kg_m2"])
    r_act = van_wagner_active_ros(fuel["cbd_kg_m3"])
    cfb = np.where(crown, crown_fraction_burned(R, r_init, r_act), 0.0)
    It = byram_intensity(heat_kj_kg, fuel["surface_kg_m2"] + cfb * fuel["cfl_kg_m2"], R)
    L = np.where(crown, flame_length_thomas(It), flame_length_byram(Is))
    return {"I_surface": Is, "I0": np.broadcast_to(I0, R.shape).astype(float), "crown": crown, "cfb": cfb,
            "I_total": It, "L": L, "thomas": crown}
