"""End to end, PROTOCOL.md sections 4, 6, 7 and 8. Run from this folder:

    python3 run_all.py --hours EXPORT_DIR --fire fire_arrival_minutes.tif --grid GRID_JSON --osm OSM_JSON

EXPORT_DIR holds hour_00.npz, hour_01.npz, ... written from the exposure pipeline's saved run, one per forecast hour,
with the keys of blocking.HourFields (bin_edges_s, p_vis, pm25_ug_m3, q_rad_kw_m2 or thermal_j_m2, thermal_resolved,
co_mg_m3 or co_mean_mg_m3), arrays on the Fish Creek grid, rows north-down. The fire-arrival raster is the one the road
layer reads today (minutes from the issue time, INTERFACE.md format) on the same grid.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blocking as B  # noqa: E402
import osm_graph as G  # noqa: E402
import route as R  # noqa: E402
from wfg_roadlayer import geotiff  # noqa: E402  (path set by route)

ASSUMPTION = ("ASSUMPTION: visibility criterion uses the 10 m building-egress reference (Purser & McAllister, SFPE "
              "Handbook) and a probability level chosen by us, not a published value")
ISSUE = "2024-08-23T00:00:00Z"
ARRAYS = ("bin_edges_s", "p_vis", "pm25_ug_m3", "q_rad_kw_m2", "thermal_j_m2", "thermal_resolved", "co_mg_m3", "co_mean_mg_m3")


def load_hours(d):
    files = sorted(Path(d).glob("hour_*.npz"))
    hours = []
    for k, f in enumerate(files):
        if f.name != "hour_%02d.npz" % k:
            break  # consecutive hours only
        z = np.load(f, allow_pickle=False)
        hours.append(B.HourFields(**{a: (z[a] if a in z.files else None) for a in ARRAYS}))
    return hours


def write_raster(path, arr, grid, H_hours, source, extra=None):
    md = {"WFG_ISSUE_TIME": ISSUE, "WFG_HORIZON_MIN": int(60 * H_hours), "WFG_UNITS": "minutes", "WFG_SOURCE": source}
    md.update(extra or {})
    geotiff.write(path, np.asarray(arr, float), grid.affine, grid.epsg, nodata=float("nan"), dtype="float32", metadata=md)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", required=True)
    ap.add_argument("--fire", required=True)
    ap.add_argument("--grid", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--snapshot", default=ISSUE)
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out)
    (out / "rasters").mkdir(parents=True, exist_ok=True)
    (out / "routing").mkdir(parents=True, exist_ok=True)
    grid = G.Grid.from_json(a.grid)

    hours = load_hours(a.hours)
    Hh = len(hours)
    summary = {"n_hours": Hh, "hours_rule": "consecutive hours supported by the saved forecast", "notes": []}
    if Hh < 6:
        summary["notes"].append("FEWER THAN 6 HOURS (%d): protocol says report and stop" % Hh)
        (out / "summary.json").write_text(json.dumps(summary, indent=1))
        print("only %d consecutive hours; stopping as the protocol says" % Hh)
        return 2

    crit, computed, unresolved, notes = B.criteria_by_hour(hours)
    summary["notes"] += notes
    fire = np.asarray(geotiff.read(a.fire).data, float)
    fire_cut = np.where(fire > 60 * Hh, np.inf, fire)  # beyond the exposure horizon = not inside it
    n_cells = int(computed.any(axis=0).sum())
    n_cell_hours = int(computed.sum())
    fire_ch = B.blocked_cell_hours(fire_cut, Hh) & computed

    counts = {k: int((v & computed).sum()) for k, v in crit.items()}
    counts["radiant_unresolved_not_blocked"] = int((unresolved & computed).sum())
    summary.update(n_cells=n_cells, n_cell_hours=n_cell_hours, criterion_cell_hours=counts,
                   fire_blocked_cell_hours=int(fire_ch.sum()))
    pm = np.stack([np.asarray(h.pm25_ug_m3, float) for h in hours])
    summary["pm25_reported_not_used"] = {"max_ug_m3": float(np.nanmax(pm)), "cell_hours_above_0": int(np.nansum(pm > 0)),
                                         "n_cell_hours": n_cell_hours}

    raster = {}
    for aud in B.AUDIENCES:
        for lv in B.VIS_LEVELS:
            tag = "%s_vis%02d" % (aud, round(lv * 100))
            exp = B.first_blocked_minutes(B.audience_rule(crit, aud, lv), computed)
            comb = B.earlier_of(exp, fire_cut)
            extra = {"WFG_BLOCK_RULE": "PROTOCOL.md s3, %s, radiant %.1f kW/m2, CO AEGL-2, visibility p>=%.1f" %
                     (aud, B.RADIANT_KW_M2[aud], lv), "WFG_ASSUMPTION": ASSUMPTION}
            p1 = out / "rasters" / ("exposure_first_blocked_%s.tif" % tag)
            p2 = out / "rasters" / ("earliest_fire_or_exposure_%s.tif" % tag)
            write_raster(p1, exp, grid, Hh, "routing_link exposure blocking", extra)
            write_raster(p2, comb, grid, Hh, "routing_link earlier of exposure blocking and fire arrival", extra)
            raster[tag] = (exp, comb, p2)
            comb_ch = B.blocked_cell_hours(comb, Hh) & computed
            summary.setdefault("added_cell_hours", {})[tag] = {
                "exposure_blocked_not_fire": int((comb_ch & ~fire_ch).sum()), "n_cell_hours": n_cell_hours,
                "cells_blocked_earlier_than_fire": int(np.sum(np.nan_to_num(exp, nan=np.inf) < np.nan_to_num(fire_cut, nan=np.inf))),
                "n_cells": n_cells}
    pf = out / "rasters" / "fire_arrival_only.tif"
    write_raster(pf, fire_cut, grid, Hh, "fire arrival as the road layer reads it, cut to the exposure horizon")

    graph, origins, exits, meta = G.build(a.osm, a.grid, a.snapshot)
    (out / "routing" / "graph.json").write_text(json.dumps(graph))
    (out / "routing" / "origins_exits.json").write_text(json.dumps({"origins": origins, "exits": exits, "meta": meta}, indent=1))
    summary["routing"] = {"origin_rule": meta["origin_rule"], "exit_rule": meta["exit_rule"], "n_origins": len(origins),
                          "n_exits": len(exits), "n_nodes": len(graph["nodes"]), "n_edges": len(graph["edges"])}
    base, info, _ = R.run(graph, origins, exits, pf, grid, workers=a.workers)
    (out / "routing" / "fire_only.json").write_text(json.dumps({"rows": base, "info": info}, default=str))
    L0 = {r["origin"]: r for r in base}
    for tag, (_, _, p2) in raster.items():
        rows, info, _ = R.run(graph, origins, exits, p2, grid, workers=a.workers)
        (out / "routing" / ("fire_plus_exposure_%s.json" % tag)).write_text(json.dumps({"rows": rows, "info": info}, default=str))
        ok = [r for r in rows if r["refusal"] is None and L0[r["origin"]]["refusal"] is None]
        d = []
        H = info["horizon_s"]
        for r in ok:
            l0, l1 = L0[r["origin"]]["last_safe_departure_s"], r["last_safe_departure_s"]
            c0, c1 = L0[r["origin"]]["cut_s"], r["cut_s"]
            if (l0, c0) != (l1, c1):
                # no departure at all counts from the issue time (-1 s); no cut inside the horizon from the horizon
                v0 = H if c0 is None else (-1 if l0 is None else l0)
                v1 = H if c1 is None else (-1 if l1 is None else l1)
                d.append((v0 - v1) / 60.0)
        summary.setdefault("origins", {})[tag] = {
            "n_origins_routed": len(ok), "n_changed": len(d),
            "earlier_by_min_median": float(np.median(d)) if d else 0.0,
            "earlier_by_min_largest": float(np.max(d)) if d else 0.0,
            "refused": sum(1 for r in rows if r["refusal"])}
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    import figure
    figure.make(graph, grid, fire_cut, raster["residents_vis50"][1], out / "fig_blocked_cells")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
