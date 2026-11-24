"""Run the road layer's backward pass on Fish Creek for one blocking raster.

Everything that decides a route is the road layer's own code, imported unchanged from product/wfg-roadlayer:
the raster classification (fireinput._classify / _cell_reduce), the instance (engine.build_instance), the backward
passes (engine.run_passes) and the per-origin answer (engine.assemble: windows, last safe departure, cut). Only the
region is new: the Fish Creek graph from osm_graph.py, its origins, and the map-edge exits as destinations.

The road layer reads its Korean regions in EPSG:5179; here the graph and the raster share the Fish Creek grid
(EPSG:5070, 375 m), so a road cell is exactly one raster pixel and the exact-overlap rule reduces to that pixel.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROADLAYER = Path(__file__).resolve().parents[2] / "product" / "wfg-roadlayer"
sys.path.insert(0, str(ROADLAYER))
from wfg_roadlayer import engine, geotiff  # noqa: E402
from wfg_roadlayer import settings as settings_mod  # noqa: E402
from wfg_roadlayer.fireinput import _cell_reduce, _classify  # noqa: E402
from wfg_roadlayer.regiondata import RoadModel  # noqa: E402

from osm_graph import Grid  # noqa: E402


def closures_from_raster(path, road: RoadModel, grid: Grid):
    """{router cell: closure second} and the uncovered road cells, by the road layer's own rules."""
    r = geotiff.read(Path(path))
    if tuple(round(v, 6) for v in r.affine) != tuple(round(v, 6) for v in grid.affine) or r.epsg != grid.epsg:
        raise ValueError("raster is not on the Fish Creek grid: %s %s" % (r.affine, r.epsg))
    hmin = float(r.metadata["WFG_HORIZON_MIN"])
    H = int(round(hmin * 60))
    cov, sec = _classify(np.asarray(r.data, float), r.nodata, hmin, None, H)
    close_s, uncovered = {}, []
    for cell in road.road_cells:
        rr, cc = grid.router_to_raster(cell)
        m = _cell_reduce(cov[rr:rr + 1, cc:cc + 1], sec[rr:rr + 1, cc:cc + 1], H)
        if m is None:
            uncovered.append(cell)
        elif m <= H:
            close_s[cell] = m
    return close_s, uncovered, H, r.metadata


def run(graph: dict, origins: list, exits: list, raster, grid: Grid, workers: int = 1, settings_path=None):
    """Per-origin rows from engine.assemble, every exit a candidate destination."""
    cfg = settings_mod.load(settings_path)
    road = RoadModel(graph)
    close_s, uncovered, H, md = closures_from_raster(raster, road, grid)
    if uncovered:
        raise ValueError("%d road cells have no data in %s" % (len(uncovered), raster))
    ex = [dict(e, node=road.nidx[e["entry_node_id"]], id=e["id"]) for e in exits]
    orig = []
    for o in origins:
        orig.append(dict(o, node=road.nidx.get(o["entry_node_id"]) if o["checkable"] else None, vulnerable=False,
                         sigungu="", eupmyeon="", town_method="n/a"))
    cands = {o["id"]: ([e for e in ex if e["entry_node_id"] != o["entry_node_id"]] if o["node"] is not None else [])
             for o in orig}
    region = SimpleNamespace(id="fishcreek_2024", road=road, origins=orig, shelters=ex, cands=cands)
    fire = SimpleNamespace(horizon_s=H, uncovered_set=set())
    inst = engine.build_instance(road, close_s, H)
    dwell = cfg["routing"]["dwell_s"]
    jobs = []
    for e in ex:
        acc = engine.accept(road, close_s, e["node"], H, dwell)
        lst = [(o["node"], engine.origin_closure(road, close_s, o["node"], H)) for o in orig
               if o["node"] is not None and any(c["node"] == e["node"] for c in cands[o["id"]])]
        if lst:
            jobs.append((e["node"], acc, lst))
    try:
        results = engine.run_passes(road, inst, jobs, workers)
    except (PermissionError, OSError):  # no process pool allowed here (e.g. a sandbox): same passes, one process
        results = engine.run_passes(road, inst, jobs, 1)
    rows = engine.assemble(region, fire, cfg, inst, results, close_s)
    out = []
    for row in rows:
        o = row["origin"]
        rec = {"origin": o["id"], "name": o.get("name", ""), "category": o.get("category"),
               "refusal": row["refusal"][0] if row["refusal"] else None}
        if not row["refusal"]:
            rec.update(last_safe_departure_s=row["L"], cut_s=row["cut"], leave_by_s=row["leave_by"],
                       fire_arrival_entry_s=row["A"], windows=row["windows"],
                       exit_last=(row["last"]["shelter"]["id"] if row["last"] else None),
                       route_last_edges=([road.edge_ids[l[1]] for l in row["last"]["w_last"]["legs"] if l[0] == "EDGE"]
                                         if row["last"] and row["last"]["w_last"] else None))
        out.append(rec)
    info = {"horizon_s": H, "closed_road_cells": len(close_s), "road_cells": len(road.road_cells),
            "n_origins": len(orig), "n_exits": len(ex), "passes": len(jobs), "dwell_s": dwell, "raster_metadata": md}
    return out, info, close_s
