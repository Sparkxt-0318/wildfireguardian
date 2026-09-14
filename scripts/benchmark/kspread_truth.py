#!/usr/bin/env python
"""Truth for K-SPREAD-2025, built under the declared bounds of ``docs/regrade_three_way.md`` §2.

The protocol (``docs/benchmark/K_SPREAD_2025.md`` §4) says truth is the cumulative FIRMS
detections at the first overpass at or after T0 + h, classed per cell as **detected**,
**indeterminate** or **not detected**, and that scoring never interpolates detections into
smooth truth. The bounds that make those three words mean something are A1-A6 of
``docs/regrade_three_way.md``, and the reference implementation of the classification is
``scripts/regrade_three_way.py``: :func:`first_seen_grid`, :func:`earliest` and
``classify_route``.

⚠ **This module is a transcription of that reference, not a second opinion.**
:func:`first_seen_grid` and :func:`earliest` below are the reference functions, and
``tests/test_kspread_scorer.py`` asserts, against the committed
``data/processed/routing_demo_canonical.npz``, that they return exactly what
``scripts/regrade_three_way.py`` returns, and that :func:`node_truth` reproduces
``classify_route``'s ``class_m0`` verdict on a synthetic network. They are transcribed
rather than imported because importing ``regrade_three_way`` pulls in the whole routing
stack, and a unit test of the truth rule should not need it; the equivalence test is what
makes the transcription checkable instead of merely asserted.

THE HORIZON CLASSES, DERIVED
----------------------------
Let the overpass times be ``T_0 < T_1 < ...`` and ``first_seen(c)`` the earliest overpass
at which cell *c* is detected (``inf`` if never). Under A2 with miss allowance *m*, the
earliest time *c* could have been fire-affected is ``earliest_m(c)``. At horizon time *H*:

===================  ======================================================
class                condition
===================  ======================================================
detected             ``first_seen(c) <= H``                       (A1)
indeterminate        ``earliest_m(c) <= H < first_seen(c)``       (A2)
not detected         ``H < earliest_m(c)``, never-detected included (A4)
===================  ======================================================

At *m* = 0 this is character for character the protocol's own wording. ``earliest_0`` for a
cell first seen at ``T_k`` is ``T_{k-1}``, so ``indeterminate`` is exactly 「first detected
in the gap between the last overpass before T0 + h and the first after」, and ``detected``
is exactly 「the cumulative detections at the first overpass at or after T0 + h」 minus that
gap. ``tests/test_kspread_scorer.py`` asserts the two readings agree cell for cell.

A4 is an assumption and not verified absence: a 「not detected」 cell is one the observation
does not place in the fire, not one the observation places outside it.
"""
from __future__ import annotations

import math

import numpy as np

#: Miss allowances reported, in the reference implementation's own spelling.
MISS = [0, 1, "inf"]

#: Class labels, fixed so every artifact and every test spells them the same way.
DETECTED, INDETERMINATE, NOT_DETECTED = "detected", "indeterminate", "not_detected"
CLASSES = (DETECTED, INDETERMINATE, NOT_DETECTED)


def first_seen_grid(z):
    """``(first_seen, overpass_times)`` from a committed npz holding ``obs_stack``/``obs_times``.

    Transcribed from ``scripts/regrade_three_way.py``. ``first_seen`` is ``inf`` where the
    cell is never detected through the last overpass.
    """
    obs = z["obs_stack"]
    t = np.asarray(z["obs_times"], float)
    fs = np.full(obs.shape[1:], np.inf)
    for i in range(len(t) - 1, -1, -1):
        fs[obs[i] == 1] = t[i]
    return fs, t


def earliest(first, t, m):
    """Earliest possible fire-affected time for a cell first seen at ``first`` (A2).

    Transcribed from ``scripts/regrade_three_way.py``.
    """
    if not np.isfinite(first):
        return np.inf
    k = int(np.where(t == first)[0][0])
    if m == "inf":
        return 0.0
    j = k - 1 - int(m)
    return float(t[j]) if j >= 0 else 0.0


def earliest_grid(fs, t, m):
    """:func:`earliest` applied cellwise; ``inf`` where the cell is never detected."""
    out = np.full(fs.shape, np.inf)
    for v in np.unique(fs[np.isfinite(fs)]):
        out[fs == v] = earliest(float(v), t, m)
    return out


def horizon_truth(fs, t, horizon_min: float, m=0) -> dict[str, np.ndarray]:
    """Per-cell truth masks at ``horizon_min`` under miss allowance ``m``.

    Returns boolean grids keyed by :data:`CLASSES`; the three partition the grid.
    """
    e = earliest_grid(fs, t, m)
    detected = fs <= horizon_min
    indeterminate = (~detected) & (e <= horizon_min)
    not_detected = ~(detected | indeterminate)
    return {DETECTED: detected, INDETERMINATE: indeterminate, NOT_DETECTED: not_detected}


def horizon_truth_from_overpasses(fs, t, horizon_min: float) -> dict[str, np.ndarray]:
    """The protocol §4 wording, read directly, as an independent check on :func:`horizon_truth`.

    「the cumulative FIRMS detections at the first overpass at or after T0 + h」 with the
    cells 「first detected in the gap between the last overpass before T0 + h and the first
    after」 held out as indeterminate. Equals ``horizon_truth(..., m=0)``; the test asserts it.
    """
    after = t[t >= horizon_min]
    k_after = float(after[0]) if len(after) else math.inf
    before = t[t < horizon_min]
    t_before = float(before[-1]) if len(before) else -math.inf
    detected = fs <= horizon_min
    indeterminate = (fs == k_after) & (k_after > horizon_min) & (fs > t_before)
    not_detected = ~(detected | indeterminate)
    return {DETECTED: detected, INDETERMINATE: indeterminate, NOT_DETECTED: not_detected}


def cell_index(x: float, y: float, extent) -> tuple[int, int] | None:
    """A5 cell membership: the grid cell containing an EPSG:5179 point, or ``None`` if outside.

    The floor arithmetic is ``classify_route``'s, unchanged. Cell membership, not the
    router's bilinear sampler — ``docs/regrade_three_way.md`` §A5 records why the two
    differ and that this is the stricter reading of a binary footprint.
    """
    xmin, ymin, xmax, ymax, cell, nrows, ncols = extent
    col = int(math.floor((x - xmin) / cell))
    row = int(math.floor((ymax - y) / cell))
    if 0 <= col < ncols and 0 <= row < nrows:
        return row, col
    return None


def node_truth(x: float, y: float, fs, t, extent, m=0) -> dict:
    """Observed arrival bounds at one road node, under A1-A5.

    ``observed_min`` is the first detection of the node's cell (``inf`` if never detected);
    ``earliest_min`` is A2's lower bound on when the fire could have been there.
    ``supported`` is False for a node outside the grid, which is never scored.
    """
    rc = cell_index(x, y, extent)
    if rc is None:
        return {"supported": False, "observed_min": math.inf, "earliest_min": math.inf}
    f = float(fs[rc])
    return {"supported": True, "observed_min": f, "earliest_min": earliest(f, t, m)}


__all__ = [
    "CLASSES", "DETECTED", "INDETERMINATE", "MISS", "NOT_DETECTED",
    "cell_index", "earliest", "earliest_grid", "first_seen_grid",
    "horizon_truth", "horizon_truth_from_overpasses", "node_truth",
]
