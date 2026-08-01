"""Simulation-canvas resolution and boundary-contact checking.

Round-3 PHASE 1, item 2.

WHY THIS EXISTS
---------------
The forward simulation used to inherit its extent from ``ev.meta.bbox_wgs84`` —
whatever bbox happened to be in the git-ignored ``fire_manifest.json``. That
file was regenerated on 2026-07-23 and the committed hazard field stopped
reproducing (181x147 -> 125x119). Nothing raised. Nothing logged.

The canvas is now an explicit config parameter (``grid.simulation_bbox``), and
a fire that reaches the edge of its canvas is an ERROR rather than a quiet
truncation. A clipped envelope under-reports area, breadth and drift, and every
downstream routing decision inherits that under-report.

Two checks, deliberately different in severity:

* :func:`assert_envelope_within_grid` — RAISES. A fire touching the boundary
  means the reported numbers are wrong, not merely fragile.
* :func:`check_routing_clearance` — WARNS. Routing outside the hazard extent is
  clipped to p=0, which is optimistic; but it is a modelling limitation to
  disclose, not a corrupted result.
"""

from __future__ import annotations

import warnings

import numpy as np

from ..config import get as _cfg
from .grid import CoarseGrid


class GridBoundaryError(RuntimeError):
    """The forward-simulated envelope reached the edge of its grid."""


class RoutingClearanceWarning(UserWarning):
    """The routing extent sits too close to (or outside) the hazard grid."""


def resolve_simulation_bbox(
    fallback: tuple[float, float, float, float] | None = None,
) -> tuple[tuple[float, float, float, float], str]:
    """Return ``((W, S, E, N), provenance)`` for the simulation canvas.

    ``grid.simulation_bbox`` is either a key into the config's ``bbox:`` block
    (e.g. ``"fire_acquisition"``) or an explicit ``[W, S, E, N]`` list.
    """
    spec = _cfg("grid.simulation_bbox", "fire_acquisition")
    if isinstance(spec, (list, tuple)):
        if len(spec) != 4:
            raise ValueError(
                f"grid.simulation_bbox must be [W, S, E, N]; got {spec!r}")
        return tuple(float(v) for v in spec), "config grid.simulation_bbox (explicit)"

    key = f"bbox.{spec}.wgs84_wsen"
    bb = _cfg(key, None)
    if bb is None:
        if fallback is None:
            raise KeyError(
                f"grid.simulation_bbox={spec!r} does not resolve to {key} and no "
                "fallback was supplied.")
        return tuple(float(v) for v in fallback), "caller fallback (config key missing)"
    return tuple(float(v) for v in bb), f"config {key}"


def boundary_contact(
    surface: np.ndarray, *, p_threshold: float | None = None,
    margin_cells: int | None = None,
) -> dict:
    """Report whether ``surface`` reaches its own boundary ring.

    Returns a dict with the per-edge maxima so a caller can say *which* edge
    was hit, not merely that one was.
    """
    if p_threshold is None:
        p_threshold = float(_cfg("grid.boundary_check.p_threshold", 0.3))
    if margin_cells is None:
        margin_cells = int(_cfg("grid.boundary_check.margin_cells", 1))
    m = max(1, margin_cells)
    a = np.asarray(surface, float)
    edges = {
        "north": a[:m, :], "south": a[-m:, :],
        "west": a[:, :m], "east": a[:, -m:],
    }
    per_edge = {k: float(np.nanmax(v)) if v.size else float("-inf")
                for k, v in edges.items()}
    hit = sorted(k for k, v in per_edge.items() if v >= p_threshold)
    return {
        "reached": bool(hit),
        "edges_reached": hit,
        "max_p_per_edge": per_edge,
        "p_threshold": p_threshold,
        "margin_cells": m,
    }


def assert_envelope_within_grid(
    surfaces, *, grid: CoarseGrid | None = None, context: str = "forward simulation",
) -> list[dict]:
    """Raise :class:`GridBoundaryError` if any surface touches the boundary ring.

    ``surfaces`` is a sequence of 2-D probability arrays (one per time slice).
    Returns the per-slice reports when everything is clear, so callers can
    record the margin they actually had.
    """
    reports = []
    for i, s in enumerate(surfaces):
        r = boundary_contact(s)
        r["slice"] = i
        reports.append(r)

    if not _cfg("grid.boundary_check.enabled", True):
        return reports

    bad = [r for r in reports if r["reached"]]
    if bad:
        first = bad[0]
        detail = ", ".join(
            f"slice {r['slice']}: {'/'.join(r['edges_reached'])} "
            f"(max p {max(r['max_p_per_edge'][e] for e in r['edges_reached']):.3f})"
            for r in bad[:4])
        extent = ""
        if grid is not None:
            extent = (f"\n  current grid: {grid.nrows}x{grid.ncols} cells @ "
                      f"{grid.cell_size_m:g} m = "
                      f"{grid.ncols * grid.cell_size_m / 1000:.1f} x "
                      f"{grid.nrows * grid.cell_size_m / 1000:.1f} km")
        raise GridBoundaryError(
            f"{context} reached grid boundary — enlarge simulation_bbox.\n"
            f"  {len(bad)}/{len(reports)} time slice(s) touched the outer "
            f"{first['margin_cells']}-cell ring at p >= {first['p_threshold']}.\n"
            f"  {detail}{extent}\n"
            "  A clipped envelope under-reports area, breadth and drift, and every\n"
            "  downstream routing decision inherits that under-report.\n"
            "  Fix: widen config grid.simulation_bbox (currently "
            f"{resolve_simulation_bbox()[0]}).")
    return reports


def check_routing_clearance(
    routing_bbox_5179: tuple[float, float, float, float],
    grid: CoarseGrid, *, clearance_km: float | None = None,
) -> dict:
    """Warn if the routing extent is not comfortably inside the hazard grid.

    Nodes outside the hazard grid read p=0 — no extrapolation, but also no
    hazard. That is optimistic, so it must be visible.
    """
    if clearance_km is None:
        clearance_km = float(_cfg("grid.boundary_check.routing_clearance_km", 5.0))
    need = clearance_km * 1000.0
    rminx, rminy, rmaxx, rmaxy = routing_bbox_5179
    margins = {
        "west": rminx - grid.minx,
        "south": rminy - grid.miny,
        "east": grid.maxx - rmaxx,
        "north": grid.maxy - rmaxy,
    }
    tight = {k: v for k, v in margins.items() if v < need}
    report = {
        "clearance_required_m": need,
        "margins_m": margins,
        "margins_km": {k: round(v / 1000.0, 2) for k, v in margins.items()},
        "sides_below_clearance": sorted(tight),
        "outside_grid": sorted(k for k, v in margins.items() if v < 0),
        "ok": not tight,
    }
    if tight:
        worst = ", ".join(f"{k} {margins[k] / 1000:.2f} km" for k in sorted(tight))
        warnings.warn(
            f"routing extent is within {clearance_km:g} km of the hazard-grid edge "
            f"({worst}). Walk/drive nodes beyond the grid read p=0 — no hazard, "
            "no extrapolation — which is OPTIMISTIC. Widen "
            "config grid.simulation_bbox or disclose the clipped side.",
            RoutingClearanceWarning, stacklevel=2)
    return report


__all__ = [
    "GridBoundaryError", "RoutingClearanceWarning", "resolve_simulation_bbox",
    "boundary_contact", "assert_envelope_within_grid", "check_routing_clearance",
]
