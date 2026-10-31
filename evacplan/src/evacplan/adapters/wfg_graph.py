"""This repo's router road graph (``graph.json``, validated by ``wfg_latest.router_validation``) as
an evacplan :class:`~evacplan.schema.RoadGraph`.

Router graph facts (map 01 / ``validation._validate_graph``): nodes ``{id, x, y, waitable}`` in a
projected metre CRS (``"EPSG:5179"`` for the Korean study graphs); directed edges
``{id, u, v, travel_ticks, segments, reverse_edge, ...}`` whose geometry is the straight chord
u -> v (no polyline) traversed at constant speed; ``travel_ticks`` are hazard lattice steps
(``dt = 1 s`` in every recorded packet; the graph carries no ``dt``); ``forbidden_turns`` are
``[in_edge, out_edge]`` pairs (mostly U-turns away from dead ends); waiting only at ``waitable``
nodes; ``mid_edge_reversal`` is false in all study graphs (evacplan never reverses mid-edge).

The graph's ``grid`` (``x0``, ``y0`` = SOUTH edge, ``resolution``, ``width``, ``height``) is the
hazard grid of its packets; :func:`router_grid_transform` gives it in hazard_contract's north-up
affine form for alignment checks. OSM-derived graphs keep their ODbL attribution in provenance.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..schema import Edge, Node, RoadGraph


def router_grid_transform(graph: dict) -> tuple[float, float, float, float, float, float]:
    """The router grid as a north-up rasterio affine ``(res, 0, x0, 0, -res, y0 + height * res)``."""
    g = graph["grid"]
    res = float(g["resolution"])
    return (res, 0.0, float(g["x0"]), 0.0, -res, float(g["y0"]) + int(g["height"]) * res)


def _epsg(crs: str) -> int:
    auth, _, code = str(crs).partition(":")
    if auth.upper() != "EPSG" or not code.isdigit():
        raise ValueError(f"unsupported CRS {crs!r}: expected 'EPSG:<code>'")
    return int(code)


def from_wfg_graph(graph: dict | str | Path, *, dt_s: float = 1.0, validate: bool = True) -> RoadGraph:
    """Convert a router ``graph.json`` (dict or path).

    validate: run the router's own admission (``wfg_latest.router_validation.validation.validate_graph``:
    exact chord/grid segments, mutual reverse edges, turn rules) before converting. ``dt_s``: seconds
    per travel tick.
    """
    if isinstance(graph, (str, Path)):
        graph = json.loads(Path(graph).read_text())
    if not dt_s > 0:
        raise ValueError("dt_s must be > 0")
    if validate:
        from wfg_latest.router_validation.validation import validate_graph
        graph = validate_graph(graph)
    nodes = [Node(id=n["id"], x=float(n["x"]), y=float(n["y"]), waitable=bool(n["waitable"])) for n in graph["nodes"]]
    edges = [Edge(id=e["id"], u=e["u"], v=e["v"], travel_time_s=float(e["travel_ticks"]) * dt_s) for e in graph["edges"]]
    turns = [(str(a), str(b)) for a, b in graph.get("forbidden_turns", [])]
    src: dict[str, Any] = dict(graph.get("provenance") or {})
    provenance: dict[str, Any] = {
        "adapter": "evacplan.adapters.wfg_graph",
        "graph_revision": graph.get("revision"),
        "router_grid": graph.get("grid"),
        "router_grid_transform": list(router_grid_transform(graph)) if "grid" in graph else None,
        "mid_edge_reversal": bool(graph.get("mid_edge_reversal", False)),
        "dt_s": dt_s,
        "validated_by": "wfg_latest.router_validation.validation.validate_graph" if validate else None,
        "source": src,
    }
    lic = str(src.get("license", ""))
    if "ODbL" in lic or "OpenStreetMap" in str(src.get("source", "")):
        provenance["attribution"] = "Road data (c) OpenStreetMap contributors, ODbL 1.0"
    return RoadGraph(crs_epsg=_epsg(graph["crs"]), nodes=nodes, edges=edges, forbidden_turns=turns,
                     provenance=provenance)
