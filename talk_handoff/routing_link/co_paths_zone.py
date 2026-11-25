"""Route each path where CO blocks a road four ways (PROTOCOL.md Amendment 6 item 3). Run from this folder:

    python3 co_paths_zone.py --grid GRID_JSON --osm data/fishcreek_osm_20240823.json.gz

Reads export_v2/co_paths/*.npz (co_paths_zone_export.py). Writes out_v2/co_paths/summary.json.
Runs per path: (i) fire alone, (ii) + safety zone, (iii) + CO, (iv) + CO + safety zone, for residents and responders.
A run whose blocking times on every road cell equal those of an earlier run gives the same road-layer answer by
construction; it is reused and marked "reused".
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blocking as B  # noqa: E402
import osm_graph as G  # noqa: E402
import route as R  # noqa: E402
from run_v2 import origin_changes, write_raster  # noqa: E402
from wfg_roadlayer.regiondata import RoadModel  # noqa: E402

AUD = ("residents", "responders")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--out", default=str(HERE / "out_v2" / "co_paths"))
    ap.add_argument("--shard", default="0/1", help="i/n: run every n-th path starting at i (parallel processes)")
    ap.add_argument("--merge", action="store_true", help="merge shard files into summary.json")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sel = json.loads((HERE / "export_v2" / "co_paths" / "selection.json").read_text())
    grid = G.Grid.from_json(a.grid)
    graph, origins, exits, _ = G.build(a.osm, a.grid, "2024-08-23T00:00:00Z")
    road = RoadModel(graph)
    road_rc = sorted({grid.router_to_raster(c) for c in road.road_cells})
    rr = np.array([r for r, _ in road_rc])
    cc = np.array([c for _, c in road_rc])
    tmp = Path(tempfile.mkdtemp())
    S = {"rule": "PROTOCOL.md Amendment 6", "n_paths": sel["n_paths"], "selected": sel["selected"], "paths": {}}
    if a.merge:
        for f in sorted(out.glob("shard_*.json")):
            S["paths"].update(json.loads(f.read_text()))
        assert sorted(int(k) for k in S["paths"]) == sorted(sel["selected"]), "shards incomplete"
    i_sh, n_sh = (int(v) for v in a.shard.split("/"))
    todo = [] if a.merge else sel["selected"][i_sh::n_sh]
    for pth in todo:
        z = np.load(HERE / "export_v2" / "co_paths" / ("path_%04d.npz" % pth))
        fire, co = z["fire_arrival_min"].astype(float), z["co_first_min"].astype(float)
        ny, nx = fire.shape
        zone = {}
        for aud in AUD:
            cf = np.full((ny, nx), np.inf)
            for r_, c_, t_ in zip(z["point_row"], z["point_col"], z["point_first_min_" + aud]):
                cf[r_, c_] = min(cf[r_, c_], t_)
            zone[aud] = cf
        cache = []  # (road-cell key, rows, info)

        def run(arr, label):
            key = np.nan_to_num(np.asarray(arr, float)[rr, cc], nan=np.inf).tobytes()
            for k, rows, info in cache:
                if k == key:
                    return rows, info, True
            p2 = tmp / ("p%d_%s.tif" % (pth, label))
            write_raster(p2, arr, grid, 6, "routing_link Amendment 6, path %d, %s" % (pth, label), {})
            rows, info, _ = R.run(graph, origins, exits, p2, grid, workers=1)
            cache.append((key, rows, info))
            return rows, info, False

        rows0, info0, _ = run(fire, "fire")
        L0 = {r["origin"]: r for r in rows0}
        H = info0["horizon_s"]
        rec = {"fire_only": {"road_cells_blocked": info0["closed_road_cells"],
                             "origins_with_cut": sum(1 for r in rows0 if r["refusal"] is None and r["cut_s"] is not None)},
               "max_radiant_375m_kw_m2": float(z["max_radiant_375m_kw_m2"]),
               "road_points": int(len(z["point_piece"])), "largest_road_flux_kw_m2": float(z["point_max_kw_m2"].max()),
               "co_road_cells": int(np.isfinite(co[rr, cc]).sum()),
               "co_road_cells_before_fire": int(np.sum(co[rr, cc] < np.where(np.isnan(fire[rr, cc]), np.inf, fire[rr, cc])))}
        rowsC, infoC, reusedC = run(B.earlier_of(co, fire), "co")
        LC = {r["origin"]: r for r in rowsC}
        rec["plus_co"] = {"road_cells_blocked": infoC["closed_road_cells"], "reused": reusedC,
                          "origins": origin_changes(L0, rowsC, H)}
        for aud in AUD:
            fm = z["point_first_min_" + aud]
            hit = np.isfinite(fm)
            d = z["point_dist_at_first_m_" + aud][hit]
            rowsZ, infoZ, reusedZ = run(B.earlier_of(zone[aud], fire), "zone_" + aud)
            rowsD, infoD, reusedD = run(B.earlier_of(np.minimum(zone[aud], co), fire), "co_zone_" + aud)
            rec[aud] = {"road_points_in_zone": int(hit.sum()),
                        "road_pieces_in_zone": int(len(np.unique(z["point_piece"][hit]))),
                        "road_cells_in_zone": int(np.isfinite(zone[aud][rr, cc]).sum()),
                        "road_cells_in_zone_before_fire": int(np.sum(zone[aud][rr, cc] < np.where(
                            np.isnan(fire[rr, cc]), np.inf, fire[rr, cc]))),
                        "distance_to_front_m": ({"min": float(d.min()), "median": float(np.median(d)), "max": float(d.max())}
                                                if len(d) else None),
                        "plus_zone": {"road_cells_blocked": infoZ["closed_road_cells"], "reused": reusedZ,
                                      "origins": origin_changes(L0, rowsZ, H)},
                        "plus_co_and_zone": {"road_cells_blocked": infoD["closed_road_cells"], "reused": reusedD,
                                             "origins_vs_fire": origin_changes(L0, rowsD, H),
                                             "origins_vs_co": origin_changes(LC, rowsD, H)}}
        S["paths"][str(pth)] = rec
        print("path", pth, rec["fire_only"], "co road", rec["co_road_cells"], "co changes", rec["plus_co"]["origins"]["n_changed"],
              {aud: (rec[aud]["road_cells_in_zone"], rec[aud]["plus_zone"]["origins"]["n_changed"],
                     rec[aud]["plus_co_and_zone"]["origins_vs_co"]["n_changed"]) for aud in AUD}, flush=True)
    if not a.merge:
        (out / ("shard_%d_of_%d.json" % (i_sh, n_sh))).write_text(json.dumps(S["paths"], indent=1))
        return
    P = S["paths"].values()
    S["totals"] = {
        "paths": len(S["paths"]),
        "co_road_cells_union": None,
        "paths_where_co_changes_an_origin": sum(1 for r in P if r["plus_co"]["origins"]["n_changed"]),
        **{aud: {"paths_with_a_road_point_in_zone": sum(1 for r in P if r[aud]["road_points_in_zone"]),
                 "paths_with_a_road_cell_blocked_by_zone": sum(1 for r in P if r[aud]["road_cells_in_zone"]),
                 "paths_where_zone_changes_an_origin": sum(1 for r in P if r[aud]["plus_zone"]["origins"]["n_changed"]),
                 "paths_where_zone_adds_to_co": sum(1 for r in P if r[aud]["plus_co_and_zone"]["origins_vs_co"]["n_changed"]),
                 "largest_minutes_earlier_by_zone": max([r[aud]["plus_zone"]["origins"]["earlier_by_min_largest"] for r in P] + [0.0])}
           for aud in AUD}}
    u = set()
    for pth in sel["selected"]:
        co = np.load(HERE / "export_v2" / "co_paths" / ("path_%04d.npz" % pth))["co_first_min"]
        u |= {(int(r_), int(c_)) for r_, c_ in zip(rr, cc) if np.isfinite(co[r_, c_])}
    S["totals"]["co_road_cells_union"] = len(u)
    (out / "summary.json").write_text(json.dumps(S, indent=1))
    print(json.dumps(S["totals"], indent=1))


if __name__ == "__main__":
    main()
