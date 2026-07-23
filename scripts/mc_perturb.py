#!/usr/bin/env python
"""Driver-perturbation helper for the routing Monte Carlo (Ensemble A).

ADDITIVE ONLY. Imports and calls the existing spread_v2 weather code unchanged;
constructs a NEW perturbed :class:`WeatherSeries` per realisation and never
mutates the input or any existing identifier / dict key.

One *systematic bias* draw per realisation, held constant across the whole
domain AND across every timestep of the series (reanalysis error is spatially
and temporally correlated at these scales), per ``configs/mc_perturbation.json``.
NOT an independent per-cell / per-timestep draw.

VPD handling (reviewer condition 2): ``vpd_kpa`` is a model feature derived
from temperature and dewpoint. After perturbing ``temp_c`` and ``rh_pct`` we
reconstruct dewpoint from the perturbed ``(T, RH)`` using the repository's OWN
Magnus saturation-vapour-pressure function and recompute VPD by calling the
repository function :func:`weather.vpd_kpa`. No re-implemented ``es`` formula is
used, so there is no silent train/inference offset.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import numpy as np

from wildfireguardian.spread_v2 import weather as W
from wildfireguardian.spread_v2.weather import WeatherSeries

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "configs" / "mc_perturbation.json"


def load_config(path=DEFAULT_CONFIG) -> dict:
    return json.loads(Path(path).read_text())


def _dewpoint_c_from_T_RH(temp_c: np.ndarray, rh_pct: np.ndarray) -> np.ndarray:
    """Reconstruct dewpoint (deg C) from temperature and RH via the repo Magnus fn.

    Inverts ``RH = 100 * es(Td) / es(T)`` using the repository's own
    ``_sat_vapour_pressure_hpa`` and Magnus coefficients, so the resulting VPD
    matches the coefficients that generated the training features exactly.
    """
    es_T = W._sat_vapour_pressure_hpa(temp_c)          # hPa
    rh_safe = np.clip(rh_pct, 1e-6, 100.0)             # floor only for the log
    ea = (rh_safe / 100.0) * es_T                      # hPa
    z = np.log(ea / 6.1094)
    return W._MAGNUS_B * z / (W._MAGNUS_A - z)


def draw_perturbation(rng: np.random.Generator, cfg: dict) -> dict:
    """One systematic-bias draw (scalars) for a single realisation.

    Returns the concrete per-channel offsets/factors actually applied, so a
    caller can log them. When ``cfg['enabled']`` is false every channel is an
    exact identity (factor 1.0 / offset 0), which is what sanity check 2 uses.
    """
    ch = cfg["channels"]
    if not cfg.get("enabled", True):
        return {"enabled": False, "wind_speed_factor": 1.0, "wind_dir_delta_deg": 0.0,
                "rh_delta_pp": 0.0, "days_since_rain_delta": 0, "temp_delta_c": 0.0}
    return {
        "enabled": True,
        "wind_speed_factor": float(np.exp(rng.normal(0.0, ch["wind_speed_ms"]["sigma"]))),
        "wind_dir_delta_deg": float(rng.normal(0.0, ch["wind_direction_deg"]["sigma"])),
        "rh_delta_pp": float(rng.normal(0.0, ch["rh_pct"]["sigma"])),
        "days_since_rain_delta": int(rng.choice(ch["days_since_rain"]["values"])),
        "temp_delta_c": float(rng.normal(0.0, ch["temp_c"]["sigma"])),
    }


def perturb_weather(ws: WeatherSeries, draw: dict, cfg: dict) -> WeatherSeries:
    """Return a NEW WeatherSeries with the systematic-bias ``draw`` applied.

    The input ``ws`` is not mutated. When ``draw['enabled']`` is false the
    result is an exact element-wise copy of ``ws`` (identity), guaranteeing the
    degenerate-ensemble sanity check.
    """
    # Identity fast-path (degenerate ensemble / master flag off).
    if not draw.get("enabled", True):
        return dataclasses.replace(
            ws,
            wind_speed_ms=ws.wind_speed_ms.copy(),
            wind_toward_deg=ws.wind_toward_deg.copy(),
            wind_u=ws.wind_u.copy(), wind_v=ws.wind_v.copy(),
            temp_c=ws.temp_c.copy(), rh_pct=ws.rh_pct.copy(),
            vpd_kpa=ws.vpd_kpa.copy(),
            days_since_rain=ws.days_since_rain.copy(),
            precip_24h_mm=ws.precip_24h_mm.copy(),
        )

    ch = cfg["channels"]
    # --- wind speed: multiplicative lognormal (direction unchanged here) ------
    new_speed = ws.wind_speed_ms * draw["wind_speed_factor"]
    # --- wind direction: additive rotation of bearing + unit vector -----------
    new_toward = (ws.wind_toward_deg + draw["wind_dir_delta_deg"]) % 360.0
    tr = np.radians(new_toward)
    # toward_deg = atan2(u, v)  =>  unit east = sin(toward), unit north = cos(toward)
    new_u = np.sin(tr)
    new_v = np.cos(tr)
    # --- relative humidity: additive normal, clipped ---------------------------
    rh_clip = ch["rh_pct"]["clip"]
    new_rh = np.clip(ws.rh_pct + draw["rh_delta_pp"], rh_clip[0], rh_clip[1])
    # --- temperature: additive normal ------------------------------------------
    new_temp_c = ws.temp_c + draw["temp_delta_c"]
    # --- days since rain: additive integer, clipped at 0 -----------------------
    new_dsr = np.clip(ws.days_since_rain + draw["days_since_rain_delta"],
                      ch["days_since_rain"]["clip_min"], None)
    # --- VPD: recompute via the REPO function on reconstructed dewpoint --------
    td_c = _dewpoint_c_from_T_RH(new_temp_c, new_rh)
    new_vpd = W.vpd_kpa(new_temp_c + 273.15, td_c + 273.15)

    return dataclasses.replace(
        ws,
        wind_speed_ms=new_speed,
        wind_toward_deg=new_toward,
        wind_u=new_u, wind_v=new_v,
        temp_c=new_temp_c, rh_pct=new_rh, vpd_kpa=new_vpd,
        days_since_rain=new_dsr,
        precip_24h_mm=ws.precip_24h_mm.copy(),  # unperturbed per the driver table
    )


__all__ = ["load_config", "draw_perturbation", "perturb_weather", "DEFAULT_CONFIG"]
