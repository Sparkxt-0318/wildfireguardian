"""SYNTHETIC logged CSV for test A (Bunsen), used only to test a_bunsen_analyse. Not a measurement.

Forward model (stated, seeded): a 30 mm, 1 mm copper disc obeys C dT/dt = alpha*q - [h (T-Ta) + eps sigma (T^4-Ta^4)]
with TRUE h and eps below (the analysis does not know them), is sampled at 10 Hz, quantised to 0.25 C, with white
read noise, a slow room-air drift, a constant plate-minus-air thermocouple offset, and per-run distance jitter. The
true flux is chi_true x one of the bunsen_models curves, so the answer the analysis must recover is known.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Optional

import numpy as np

from . import bunsen_models as bm
from crossing.flux import SIGMA, C_TO_K

SYNTH_SHEET = {"gas": "methane", "gas_flow_l_min": 1.0, "lhv_mj_m3": 33.9, "combustion_efficiency": 1.0, "chi": 0.10,
               "chi_range": [0.03, 0.20], "flame_diameter_m": 0.02, "flame_height_m": 0.12,
               "plate": {"diameter_m": 0.03, "thickness_m": 0.001, "rho": 8960.0, "cp": 385.0, "absorptivity": 0.95,
                         "emissivity": 0.95}, "q_rel_uncertainty": 0.10}


def _simulate(rng, q_fn, t_end, t_on, shield_off_s, T0, Ta0, h, eps, alpha, spec_C, hz=10.0, offset=0.3,
              noise=0.08, drift_k_per_s=0.0004, heat_until=None, heat_flux=0.0, t_start=-30.0):
    dt = 1.0 / hz
    t = np.arange(t_start, t_end, dt)
    T = np.empty_like(t); Ta = Ta0 + drift_k_per_s * (t - t[0])
    T[0] = T0 + C_TO_K
    for i in range(1, len(t)):
        q = 0.0
        if t_on is not None and t_on <= t[i] < t_on + shield_off_s:
            q = q_fn
        if heat_until is not None and t[i] < heat_until:
            q = heat_flux
        Tk, Tak = T[i - 1], Ta[i - 1] + C_TO_K
        loss = h * (Tk - Tak) + eps * SIGMA * (Tk ** 4 - Tak ** 4)
        T[i] = Tk + dt * (alpha * q * 1000.0 - loss) / spec_C
    Tc = T - C_TO_K
    meas = np.round((Tc + offset + rng.normal(0, noise, t.size)) / 0.25) * 0.25
    air = np.round((Ta + rng.normal(0, noise, t.size)) / 0.25) * 0.25
    return t, meas, air


def make(path, truth: str = "closed_form", chi_true: float = 0.08, seed: int = 7, distances=(0.10, 0.15, 0.20, 0.30, 0.40),
         repeats: int = 3, h_true: float = 14.0, eps_true: float = 0.95, alpha_true: float = 0.95, convective_kw_m2: float = 0.0,
         run_s: float = 60.0, sheet: Optional[dict] = None, overheat_at: Optional[float] = None):
    """Write the synthetic log; returns the truth dict."""
    sheet = dict(SYNTH_SHEET if sheet is None else sheet)
    rng = np.random.default_rng(seed)
    Q = bm.power_kw(sheet["gas_flow_l_min"], sheet["lhv_mj_m3"])
    flame = bm.Flame(q_kw=Q, height_m=sheet["flame_height_m"], diameter_m=sheet["flame_diameter_m"])
    C = 8960.0 * 385.0 * 0.001
    rows, truth_q = [], {}
    for k in range(2):                                    # two cool-down runs from ~55 C
        t, p, a = _simulate(rng, 0.0, 300.0, None, 0, 55.0 + 2 * k, 21.0 + 0.2 * k, h_true, eps_true, alpha_true, C, t_start=0.0)
        for ti, pi, ai in zip(t, p, a):
            rows.append(dict(run_id="cool%d" % (k + 1), kind="cooldown", distance_m="", repeat=k + 1, t_s=round(ti, 3),
                             plate_c=pi, air_c=ai))
    for d in distances:
        for rep in range(1, repeats + 1):
            d_real = d + rng.normal(0, 0.002)
            q_true = chi_true * bm.CURVES[truth](d_real, flame) + convective_kw_m2
            if overheat_at is not None and abs(d - overheat_at) < 1e-9 and rep == 1:
                q_true = 40.0                                  # a run that blows through the 70 C limit
            T0 = 21.0 + rng.uniform(-0.3, 0.8)
            t, p, a = _simulate(rng, q_true, 150.0, 0.0, run_s, T0, 21.0 + rng.normal(0, 0.3), h_true, eps_true,
                                alpha_true, C)
            truth_q[(d, rep)] = q_true
            for ti, pi, ai in zip(t, p, a):
                rows.append(dict(run_id="r%.2f_%d" % (d, rep), kind="exposure", distance_m=d, repeat=rep,
                                 t_s=round(ti, 3), plate_c=pi, air_c=ai))
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, ["run_id", "kind", "distance_m", "repeat", "t_s", "plate_c", "air_c"])
        w.writeheader(); w.writerows(rows)
    return {"truth": truth, "chi_true": chi_true, "q_kw": Q, "q_true": truth_q, "h_true": h_true, "sheet": sheet}
