"""Heat flux adaptor: closed-form line-source law (research/kcf-heat) and the FDS C064 reference values.

Closed form (used to decide)
----------------------------
``research/kcf-heat/kcf_heat/law.py`` is loaded by file path (``crossing._repo.kcf_law()``), never copied. Its
``line_flux_s(s, chi, I, a)`` collapses the flaming zone of depth D = R * t_r into an isotropic line source of
power chi * I per metre at the zone centroid; a receiver facing it at distance s receives
q = chi * I / (2 pi s) * a / sqrt(a^2 + s^2) [kW/m2] (the finite-front factor is 1 for a long front).
Here the receiver is at distance d [m] ahead of the leading edge, so s = d + D/2.
Inside the flame (d = 0) the same law gives chi * I / (pi * D), the repo's contact convention (exposure.py uses
it inside a flaming cell). Assumptions: steady straight front, receiver on the centreline facing the front,
no atmospheric absorption, no shielding by the vehicle, chi = 0.30 default (wfg_latest POLICY).

FDS reference (shown, never used to decide)
-------------------------------------------
``research/kcf-heat/data/b2_fds_compare.json`` holds FDS C064 radiometer fluxes ahead of the front, binned by d;
the per-bin geometric means are interpolated linearly in log(q) against the bin centre, and scaled linearly by
I / 4473 kW/m (the FDS run's mean intensity). In-flame reference: the C064 radiometers inside the fuel bed,
RAD_X080 max 78.2 and RAD_X090 max 62.6 kW/m2 (research/kcf-heat/data/fds_rerun/C064_kcf_radiometers_devc.csv),
scaled by I / 4473; the larger one is used. Linear scaling with I is an assumption, not an FDS result.
Every value returned here is labelled "FDS C064 reference, not a measurement".
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, Tuple

from . import _repo

DEFAULT_CHI = 0.30
FDS_LABEL = "FDS C064 reference, not a measurement"
FDS_MEAN_INTENSITY_KW_M = 4473.083179774065           # b2_fds_compare.json mean_intensity_kw_m
FDS_IN_FLAME_MAX_KW_M2 = {"RAD_X080": 78.239, "RAD_X090": 62.615}


def _finite_pos(v, name):
    if not (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0):
        raise ValueError("%s must be finite and > 0, got %r" % (name, v))


def closed_form_line_flux(d_m: float, depth_m: float, intensity_kw_m: float, chi: float = DEFAULT_CHI,
                          half_width_m: Optional[float] = None) -> float:
    """Closed-form flux [kW/m2] at distance d_m >= 0 ahead of (or behind) a flaming zone of depth depth_m.

    Calls kcf-heat ``law.line_flux_s(s = d + depth/2, chi, intensity, half_width)``.
    """
    if not (isinstance(d_m, (int, float)) and math.isfinite(d_m) and d_m >= 0):
        raise ValueError("d_m must be finite and >= 0, got %r" % (d_m,))
    _finite_pos(depth_m, "depth_m")
    _finite_pos(intensity_kw_m, "intensity_kw_m")
    _finite_pos(chi, "chi")
    law = _repo.kcf_law()
    return float(law.line_flux_s(d_m + depth_m / 2.0, chi, intensity_kw_m, half_width_m))


def in_flame_flux(depth_m: float, intensity_kw_m: float, chi: float = DEFAULT_CHI) -> float:
    """In-flame flux [kW/m2] = closed form at d = 0 = chi * I / (pi * D) (long front)."""
    return closed_form_line_flux(0.0, depth_m, intensity_kw_m, chi, None)


@dataclass(frozen=True)
class FdsReference:
    q_kw_m2: float
    d_m: float
    intensity_kw_m: float
    scale: float                 # I / 4473
    extrapolated: bool
    label: str = FDS_LABEL


@lru_cache(maxsize=1)
def _fds_table() -> Tuple[Tuple[float, ...], Tuple[float, ...], float]:
    """(d centres, log q geomeans, in-flame max) from b2_fds_compare.json; d = 0 anchored to the in-flame max."""
    with open(_repo.B2_FDS_COMPARE, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    pts = []
    for b in data["bins"]:
        lo, hi = b["d_bin_m"]
        q = float(b["fds_geomean"])
        if q > 0 and math.isfinite(q):
            pts.append((0.5 * (float(lo) + float(hi)), math.log(q)))
    pts.sort()
    q_in = max(FDS_IN_FLAME_MAX_KW_M2.values())
    d = (0.0,) + tuple(p[0] for p in pts)
    lq = (math.log(q_in),) + tuple(p[1] for p in pts)
    return d, lq, float(data.get("mean_intensity_kw_m", FDS_MEAN_INTENSITY_KW_M))


def fds_reference(d_m: float, intensity_kw_m: float) -> FdsReference:
    """FDS C064 reference flux [kW/m2] at distance d_m ahead of the leading edge, scaled by I / 4473.

    d = 0 returns the in-flame radiometer reference. Beyond the last bin centre the last log-linear segment is
    extrapolated and flagged.
    """
    if not (isinstance(d_m, (int, float)) and math.isfinite(d_m) and d_m >= 0):
        raise ValueError("d_m must be finite and >= 0, got %r" % (d_m,))
    _finite_pos(intensity_kw_m, "intensity_kw_m")
    ds, lq, i_ref = _fds_table()
    scale = intensity_kw_m / i_ref
    extrap = d_m > ds[-1]
    if extrap:
        slope = (lq[-1] - lq[-2]) / (ds[-1] - ds[-2])
        val = lq[-1] + slope * (d_m - ds[-1])
    else:
        k = 1
        while ds[k] < d_m:
            k += 1
        f = (d_m - ds[k - 1]) / (ds[k] - ds[k - 1])
        val = lq[k - 1] + f * (lq[k] - lq[k - 1])
    return FdsReference(q_kw_m2=math.exp(val) * scale, d_m=float(d_m), intensity_kw_m=float(intensity_kw_m),
                        scale=scale, extrapolated=extrap)


def fds_in_flame_reference(intensity_kw_m: float) -> FdsReference:
    """In-flame FDS C064 reference (max of RAD_X080 78.2 and RAD_X090 62.6 kW/m2) scaled by I / 4473."""
    return fds_reference(0.0, intensity_kw_m)


def fds_bins() -> List[dict]:
    """The reference points used (for the UI), labelled."""
    ds, lq, i_ref = _fds_table()
    return [{"d_m": d, "q_kw_m2": math.exp(v), "intensity_ref_kw_m": i_ref, "label": FDS_LABEL}
            for d, v in zip(ds, lq)]


def compare(d_m: float, depth_m: float, intensity_kw_m: float, chi: float = DEFAULT_CHI) -> dict:
    """Closed form vs FDS reference at one distance (for the UI heat panel)."""
    ref = fds_reference(d_m, intensity_kw_m)
    return {"d_m": d_m, "closed_form_kw_m2": closed_form_line_flux(d_m, depth_m, intensity_kw_m, chi),
            "fds_ref_kw_m2": ref.q_kw_m2, "fds_ref_extrapolated": ref.extrapolated, "fds_label": FDS_LABEL}
