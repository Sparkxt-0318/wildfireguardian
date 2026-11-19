"""The whole chain for a set of cells: spread rate -> fuel -> intensity -> crown test -> flame length -> tilt and
height -> safe distance at each threshold (METHOD.md sections 1-5; parameters frozen in PROTOCOL.md section 4).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import fire, fuels, radiation, table, tilt


@dataclass(frozen=True)
class Setting:
    """One evaluation setting. The baseline is PROTOCOL.md section 4.7; the sensitivity runs change one field."""
    level: str = "middle"            # fuel level: low | middle | high
    T_flame_K: float = 1200.0
    emissivity: float = 1.0
    vf_kind: str = "tilted"          # planar | tilted | tilted_max | cylinder
    transmissivity: bool = True
    heat_kj_kg: float = 18000.0
    front_width_m: float = 375.0
    receiver_height_m: float = 1.5
    thresholds: tuple = (7.0, 4.7, 2.5)
    tilt_law: str = "baseline"


class Evaluator:
    def __init__(self, s: Setting):
        self.s = s
        self.caches = {q: table.DstarCache(q, s.T_flame_K, s.emissivity, s.vf_kind, W=s.front_width_m,
                                           z_r=s.receiver_height_m, transmissivity=s.transmissivity)
                       for q in s.thresholds}

    def cells(self, ros_m_s, groups, wind10_m_s, rh_pct, t_air_c):
        """Arrays over cells. Returns dict of arrays (I_surface, crown, cfb, I_total, L, theta, H, dstar_<q>)."""
        s = self.s
        R = np.asarray(ros_m_s, dtype=float)
        n = R.size
        out = {k: np.zeros(n) for k in ("I_surface", "I0", "cfb", "I_total", "L", "theta", "H")}
        out["crown"] = np.zeros(n, dtype=bool)
        groups = np.asarray(groups)
        for g in np.unique(groups):
            m = groups == g
            p = fuels.params(str(g), s.level)
            r = fire.fire_type_and_flame(R[m], p, heat_kj_kg=s.heat_kj_kg)
            for k in ("I_surface", "I0", "cfb", "I_total", "L"):
                out[k][m] = r[k]
            out["crown"][m] = r["crown"]
        sheltered = np.isin(groups, ("conifer", "broadleaf", "mixed"))
        th = tilt.flame_tilt(np.asarray(wind10_m_s, dtype=float), out["L"], out["I_total"], sheltered=sheltered,
                             crown=out["crown"], law=s.tilt_law)
        out["theta"] = th
        out["H"] = out["L"] * np.cos(th)
        pw = np.asarray(rh_pct, dtype=float) / 100.0 * np.vectorize(radiation.saturation_vapour_pressure_pa, otypes=[float])(np.asarray(t_air_c, dtype=float))
        for q, cache in self.caches.items():
            out["dstar_%g" % q] = cache(out["L"], th, pw)
        return out
