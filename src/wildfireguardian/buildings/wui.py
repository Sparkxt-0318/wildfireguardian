"""Wildland–urban interface classification of building footprints.

Session 8, Phase 2a. Operational definition: Radeloff et al. (2005,
*Ecological Applications* 15(3)) distinguish **intermix** (housing
interspersed within wildland vegetation) from **interface** (housing adjacent
to but not within vegetation). This module implements the building-level
parameterisation used by this project: a building centroid is *interface* at
threshold ``D`` iff it is NOT inside a wildland-vegetation polygon and lies
within ``D`` metres of one; it is *intermix* iff it is inside one.

⚠ Radeloff's census-block constants (6.17 housing units/km², 2.4 km buffer)
are US block-level operationalisations and are deliberately NOT transplanted;
``D`` is this project's parameter and is swept, never presented as the
Radeloff value.
"""

from __future__ import annotations

import numpy as np

from ..config import get as _cfg

#: Default interface distance threshold (m) and its sweep. Parameters of THIS
#: project's building-level form of the Radeloff interface concept.
WUI_INTERFACE_DISTANCE_M: float = float(
    _cfg("building_origins.wui_interface_distance_m", 100.0))
WUI_INTERFACE_DISTANCE_SWEEP_M: tuple[float, ...] = tuple(
    float(v) for v in _cfg("building_origins.wui_interface_distance_sweep_m",
                           (50.0, 100.0, 200.0)))


def wui_distances(xy: np.ndarray, veg_geoms: list) -> dict:
    """Distance from each point to the nearest vegetation polygon (EPSG:5179).

    Parameters
    ----------
    xy : (N, 2) array of EPSG:5179 building centroids.
    veg_geoms : list of shapely (Multi)Polygons, EPSG:5179.

    Returns ``{"dist_m": (N,) float, "inside": (N,) bool}`` where ``inside``
    marks intermix (centroid within a polygon; distance 0).
    """
    from shapely.geometry import Point
    from shapely.strtree import STRtree

    geoms = list(veg_geoms)
    if not geoms:
        raise ValueError("no vegetation polygons — the WUI definition is "
                         "undefined without a wildland layer")
    tree = STRtree(geoms)
    n = len(xy)
    dist = np.empty(n)
    inside = np.zeros(n, dtype=bool)
    for i in range(n):
        pt = Point(float(xy[i, 0]), float(xy[i, 1]))
        g = geoms[int(tree.nearest(pt))]
        d = float(pt.distance(g))
        dist[i] = d
        if d == 0.0 and g.contains(pt):
            inside[i] = True
    return {"dist_m": dist, "inside": inside}


def interface_mask(cls: dict, d_m: float) -> np.ndarray:
    """Interface selection at threshold ``d_m``: near vegetation, not within."""
    return (~cls["inside"]) & (cls["dist_m"] <= float(d_m))


__all__ = ["WUI_INTERFACE_DISTANCE_M", "WUI_INTERFACE_DISTANCE_SWEEP_M",
           "wui_distances", "interface_mask"]
