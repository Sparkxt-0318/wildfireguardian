"""Straight-front helpers for the physics validation, built only from the library's public primitives."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experimental/flame-front-radiation/src"))

import wfg_flamefront as W  # noqa: E402
from wfg_flamefront.law_v2 import view_factors_pairs  # noqa: E402
from wfg_flamefront.solidflame import panel_vertices  # noqa: E402

SIGMA = W.constants.STEFAN_BOLTZMANN_W_M2_K4
E_1200K = SIGMA * 1200.0 ** 4 / 1000.0          # kW/m2, blackbody at 1200 K


def flame_length_from_intensity(I_kw_m):
    return float(W.byram_flame_length_m(I_kw_m))


def straight_front_flux(d, height, E=100.0, length=1e5, receiver="worst_case", receiver_z=0.0, lean=0.0,
                        tau_a=1.0, n_pieces=1):
    """Flux (kW/m2) at ground distance d from the middle of a straight front lying along x at y = d.

    ``lean`` > 0 tilts the flame top toward the receiver (negative: away). The front is split into ``n_pieces``
    panels to mimic the library's piecewise emitter (identical for a straight front)."""
    xs = np.linspace(-length / 2, length / 2, n_pieces + 1)
    V = panel_vertices(xs[:-1], np.full(n_pieces, d), xs[1:], np.full(n_pieces, d), np.full(n_pieces, height),
                       0.0, -lean, 0.0)
    P = np.tile([0.0, 0.0, receiver_z], (n_pieces, 1))
    rec = receiver if receiver == "worst_case" else ("vertical_facing", math.pi / 2)
    F = view_factors_pairs(P, V, rec)
    return float(tau_a * E * F.sum())


def distance_for_flux(target, height, **kw):
    lo, hi = 0.01, 5000.0
    if straight_front_flux(lo, height, **kw) < target:
        return 0.0
    for _ in range(80):
        mid = math.sqrt(lo * hi)
        if straight_front_flux(mid, height, **kw) > target:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)
