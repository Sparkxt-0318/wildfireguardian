"""SYNTHETIC road-graph layouts for the instance generators (numpy only, deterministic).

Two layouts, both undirected and connected, with node coordinates in metres inside a
``width_m`` x ``height_m`` rectangle whose south-west corner is the origin:

* ``grid``: a jittered lattice with spacing ``spacing_m``; a fraction of the lattice roads is
  dropped (never disconnecting the graph), which leaves some dead ends.
* ``geo``: a random geometric graph: random points with a minimum spacing (dart throwing) joined
  by their Gabriel graph (an edge i-j iff no other point lies in the circle with diameter i-j),
  restricted to edges no longer than ``max_edge`` spacings; components are then joined by their
  shortest links. Gabriel graphs are planar and contain the Euclidean minimum spanning tree, so
  they look like road networks (no crossings, mean degree near 4).

:func:`to_road_graph` turns a layout into an evacplan :class:`~evacplan.schema.RoadGraph` with the
router's conventions (map 01 section 12, ``integration/`` study graphs): every road is two-way,
each direction is a straight chord u -> v traversed at constant speed with
``travel_time_s = ceil(length / speed)`` (whole seconds; the router's "40 km/h rounded up to 1 s
ticks"), U-turns are forbidden except at dead ends, and waiting is allowed at dead ends plus the
given site nodes (depots, facilities, shelters: assumed to have off-road parking).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..schema import Edge, Node, RoadGraph

KINDS = ("grid", "geo")
COORD_DECIMALS = 2          # node coordinates are rounded to 1 cm (stable across platforms)


@dataclass(frozen=True)
class Layout:
    """Undirected road layout: node coordinates ``xy [n, 2]`` and edges ``[m, 2]`` (i < j, sorted)."""

    xy: np.ndarray
    edges: np.ndarray
    kind: str

    @property
    def n(self) -> int:
        return int(self.xy.shape[0])

    def degree(self) -> np.ndarray:
        return np.bincount(self.edges.ravel(), minlength=self.n)

    def lengths(self) -> np.ndarray:
        d = self.xy[self.edges[:, 0]] - self.xy[self.edges[:, 1]]
        return np.hypot(d[:, 0], d[:, 1])


# ------------------------------------------------------------------------------ connectivity
def components(n: int, edges: np.ndarray) -> np.ndarray:
    """Component label per node (union-find)."""
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in edges.tolist():
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return np.array([find(a) for a in range(n)], dtype=np.int64)


def is_connected(n: int, edges: np.ndarray) -> bool:
    return n <= 1 or bool(np.all(components(n, edges) == 0))


def _normalise(edges) -> np.ndarray:
    e = np.asarray(edges, dtype=np.int64).reshape(-1, 2)
    e = np.sort(e, axis=1)
    e = np.unique(e, axis=0)
    return e[e[:, 0] != e[:, 1]]


def _join_components(xy: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Add the shortest links between components until the graph is connected (Kruskal)."""
    n = xy.shape[0]
    lab = components(n, edges)
    while np.unique(lab).size > 1:
        a = np.flatnonzero(lab == lab[0])
        b = np.flatnonzero(lab != lab[0])
        d = np.hypot(xy[a, None, 0] - xy[None, b, 0], xy[a, None, 1] - xy[None, b, 1])
        i, j = np.unravel_index(int(np.argmin(d)), d.shape)
        edges = _normalise(np.vstack([edges, [[a[i], b[j]]]]))
        lab = components(n, edges)
    return edges


# ----------------------------------------------------------------------------------- layouts
def grid_layout(rng: np.random.Generator, width_m: float, height_m: float, spacing_m: float, *,
                jitter: float = 0.2, drop: float = 0.12) -> Layout:
    """Jittered lattice; drops ``drop`` of the lattice roads without disconnecting the graph."""
    nx = int(math.floor(width_m / spacing_m)) + 1
    ny = int(math.floor(height_m / spacing_m)) + 1
    ox = (width_m - (nx - 1) * spacing_m) / 2.0
    oy = (height_m - (ny - 1) * spacing_m) / 2.0
    ii, jj = np.meshgrid(np.arange(nx), np.arange(ny), indexing="xy")
    base = np.column_stack([ox + ii.ravel() * spacing_m, oy + jj.ravel() * spacing_m])
    xy = base + rng.uniform(-jitter, jitter, size=base.shape) * spacing_m
    xy[:, 0] = np.clip(xy[:, 0], 0.0, width_m)
    xy[:, 1] = np.clip(xy[:, 1], 0.0, height_m)
    idx = np.arange(nx * ny).reshape(ny, nx)
    cand = np.vstack([np.column_stack([idx[:, :-1].ravel(), idx[:, 1:].ravel()]),
                      np.column_stack([idx[:-1, :].ravel(), idx[1:, :].ravel()])])
    keep = np.ones(len(cand), dtype=bool)
    target = int(round(drop * len(cand)))
    deg = np.bincount(cand.ravel(), minlength=nx * ny)
    removed = 0
    for k in rng.permutation(len(cand)).tolist():
        if removed >= target:
            break
        a, b = cand[k]
        if deg[a] <= 1 or deg[b] <= 1:
            continue
        keep[k] = False
        if is_connected(nx * ny, cand[keep]):
            deg[a] -= 1
            deg[b] -= 1
            removed += 1
        else:
            keep[k] = True
    return Layout(np.round(xy, COORD_DECIMALS), _normalise(cand[keep]), "grid")


def _dart_throw(rng: np.random.Generator, width_m: float, height_m: float, n_target: int, r_min: float,
                tries_per_point: int = 30) -> np.ndarray:
    cand = rng.uniform(0.0, 1.0, size=(n_target * tries_per_point, 2)) * np.array([width_m, height_m])
    pts = np.empty((n_target, 2))
    k = 0
    r2 = r_min * r_min
    for p in cand:
        if k and np.min((pts[:k, 0] - p[0]) ** 2 + (pts[:k, 1] - p[1]) ** 2) < r2:
            continue
        pts[k] = p
        k += 1
        if k == n_target:
            break
    return pts[:k]


def gabriel_edges(xy: np.ndarray, max_len: float) -> np.ndarray:
    """Gabriel-graph edges no longer than ``max_len`` (exact test against every point)."""
    n = xy.shape[0]
    d = np.hypot(xy[:, None, 0] - xy[None, :, 0], xy[:, None, 1] - xy[None, :, 1])
    i, j = np.nonzero(np.triu(d <= max_len, k=1))
    keep = np.ones(i.size, dtype=bool)
    for s in range(0, i.size, 4096):
        a, b = i[s:s + 4096], j[s:s + 4096]
        mid = 0.5 * (xy[a] + xy[b])
        rad2 = 0.25 * d[a, b] ** 2
        dist2 = (xy[None, :, 0] - mid[:, None, 0]) ** 2 + (xy[None, :, 1] - mid[:, None, 1]) ** 2
        dist2[np.arange(a.size), a] = np.inf
        dist2[np.arange(a.size), b] = np.inf
        keep[s:s + 4096] = ~np.any(dist2 < rad2[:, None] * (1.0 - 1e-12), axis=1)
    return _normalise(np.column_stack([i[keep], j[keep]])) if n > 1 else np.zeros((0, 2), dtype=np.int64)


def geo_layout(rng: np.random.Generator, width_m: float, height_m: float, spacing_m: float, *,
               min_frac: float = 0.6, max_edge: float = 2.0) -> Layout:
    """Random points (same density as the lattice, minimum spacing ``min_frac`` spacings) joined
    by their Gabriel graph, edges up to ``max_edge`` spacings, then made connected."""
    n_target = int(round(width_m * height_m / spacing_m ** 2))
    xy = np.round(_dart_throw(rng, width_m, height_m, n_target, min_frac * spacing_m), COORD_DECIMALS)
    edges = gabriel_edges(xy, max_edge * spacing_m)
    edges = _join_components(xy, edges)
    return Layout(xy, edges, "geo")


def make_layout(kind: str, rng: np.random.Generator, width_m: float, height_m: float, spacing_m: float) -> Layout:
    if kind == "grid":
        return grid_layout(rng, width_m, height_m, spacing_m)
    if kind == "geo":
        return geo_layout(rng, width_m, height_m, spacing_m)
    raise ValueError(f"unknown graph kind {kind!r}; expected one of {KINDS}")


# ------------------------------------------------------------------------------ road graph
def node_id(i: int) -> str:
    return f"n{i}"


def edge_id(i: int, j: int) -> str:
    return f"n{i}>n{j}"


def to_road_graph(layout: Layout, *, crs_epsg: int, offset_xy: tuple[float, float] = (0.0, 0.0),
                  speed_kmh: float = 40.0, waitable_sites=(), provenance: dict | None = None) -> RoadGraph:
    """Two-way roads as directed chords with the router's conventions (see the module docstring).

    ``offset_xy`` shifts every coordinate (the layout's origin in the hazard CRS);
    ``waitable_sites`` are node indices that may be waited at besides the dead ends."""
    if not speed_kmh > 0:
        raise ValueError("speed_kmh must be > 0")
    v = speed_kmh / 3.6
    deg = layout.degree()
    sites = {int(i) for i in waitable_sites}
    xy = np.round(layout.xy + np.asarray(offset_xy, dtype=float), COORD_DECIMALS)
    nodes = [Node(id=node_id(i), x=float(xy[i, 0]), y=float(xy[i, 1]), waitable=bool(deg[i] == 1 or i in sites))
             for i in range(layout.n)]
    edges: list[Edge] = []
    turns: list[tuple[str, str]] = []
    for (a, b), length in zip(layout.edges.tolist(), layout.lengths().tolist()):
        tt = float(max(1, math.ceil(length / v)))
        edges.append(Edge(id=edge_id(a, b), u=node_id(a), v=node_id(b), travel_time_s=tt))
        edges.append(Edge(id=edge_id(b, a), u=node_id(b), v=node_id(a), travel_time_s=tt))
        if deg[b] >= 2:                              # no U-turn at b unless b is a dead end
            turns.append((edge_id(a, b), edge_id(b, a)))
        if deg[a] >= 2:
            turns.append((edge_id(b, a), edge_id(a, b)))
    prov = {"layout": layout.kind, "speed_kmh": speed_kmh, "travel_time": "ceil(chord length / speed), whole seconds",
            "turns": "U-turns forbidden except at dead ends", "waitable": "dead ends and site nodes",
            **(provenance or {})}
    return RoadGraph(crs_epsg=crs_epsg, nodes=nodes, edges=edges, forbidden_turns=turns, provenance=prov)
