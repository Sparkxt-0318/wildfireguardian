"""Safety-zone figure and routing in one path (PROTOCOL.md Amendment 3). Run from this folder:

    python3 safety_zone.py --grid GRID_JSON --osm data/fishcreek_osm_20240823.json.gz

Reads export_v2/safety_zone_path.npz (safety_zone_export.py). Writes out_v2/safety_zone/ (rasters, routing JSON,
summary.json) and fig_safety_zone.{png,svg,pdf}.
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
from run_v2 import origin_changes, write_raster  # noqa: E402

INK, GREY, BLUE, RED = "#1A1A1A", "#6B6B6B", "#2F5D8A", "#8A362F"
TINT_LIGHT, TINT_MID = "#C5D3E3", "#7E9BBD"   # tints of 2F5D8A
THR = {"residents": 2.5, "responders": 7.0}


def first_minute(rad, thr):
    hit = rad >= thr
    return np.where(hit.any(axis=0), np.argmax(hit, axis=0).astype(float), np.inf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--out", default=str(HERE / "out_v2" / "safety_zone"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    z = np.load(HERE / "export_v2" / "safety_zone_path.npz")
    path, minute = int(z["path"]), int(z["minute"])
    rad, burning, fire = z["radiant_kw_m2"].astype(float), z["burning"], z["fire_arrival_min"].astype(float)
    T = rad.shape[0]
    Hh = T // 60
    grid = G.Grid.from_json(a.grid)
    graph, origins, exits, meta = G.build(a.osm, a.grid, "2024-08-23T00:00:00Z")

    S = {"path": path, "minute": minute, "rule": "PROTOCOL.md Amendment 3",
         "burned_cells_in_path": int(z["burned_cells_by_path"][path]), "median_burned_cells": float(z["median_burned_cells"]),
         "cells_burning_at_minute": int(burning[minute].sum()),
         "largest_flux_at_minute_kw_m2": float(rad[minute].max()), "largest_flux_6h_kw_m2": float(rad.max())}
    zone = {aud: rad[minute] >= thr for aud, thr in THR.items()}
    S["zone_cells_at_minute"] = {aud: int(m.sum()) for aud, m in zone.items()}
    S["zone_cells_not_burning_at_minute"] = {aud: int((m & ~burning[minute]).sum()) for aud, m in zone.items()}

    # road pieces inside each zone (undirected: a way segment and its reverse count once)
    pieces = {}
    for e in graph["edges"]:
        key = tuple(sorted((e["id"], e.get("reverse_edge") or e["id"])))
        cells = [grid.router_to_raster(s["cell"]) for s in e["segments"]]
        pieces.setdefault(key, (e, cells))
    inside = {aud: [k for k, (_, cells) in pieces.items() if any(zone[aud][r, c] for r, c in cells)] for aud in THR}
    S["road_pieces"] = len(pieces)
    S["road_pieces_inside_zone"] = {aud: len(v) for aud, v in inside.items()}
    S["road_km_inside_zone"] = {aud: round(sum(pieces[k][0]["length_m"] for k in v) / 1000, 2) for aud, v in inside.items()}

    # routing in this path: fire alone against fire plus safety zone, over the six hours
    pf = out / "fire_arrival_path.tif"
    write_raster(pf, fire, grid, Hh, "routing_link Amendment 3: ignition minute in retained path %d" % path, {})
    rows0, info0, close0 = R.run(graph, origins, exits, pf, grid, workers=1)
    (out / "fire_only.json").write_text(json.dumps({"rows": rows0, "info": info0}, default=str))
    L0 = {r["origin"]: r for r in rows0}
    S["fire_only"] = {"road_cells_blocked": info0["closed_road_cells"],
                      "origins_routed": sum(1 for r in rows0 if r["refusal"] is None),
                      "origins_with_cut": sum(1 for r in rows0 if r["refusal"] is None and r["cut_s"] is not None)}
    changes = {}
    for aud, thr in THR.items():
        comb = B.earlier_of(first_minute(rad, thr), fire)
        p2 = out / ("fire_plus_zone_%s.tif" % aud)
        write_raster(p2, comb, grid, Hh, "routing_link Amendment 3: earlier of path ignition and radiant >= %.1f kW/m2" % thr,
                     {"WFG_BLOCK_RULE": "Amendment 3, path %d, %s, radiant %.1f kW/m2 in that path" % (path, aud, thr)})
        rows, info, close = R.run(graph, origins, exits, p2, grid, workers=1)
        (out / ("fire_plus_zone_%s.json" % aud)).write_text(json.dumps({"rows": rows, "info": info}, default=str))
        oc = origin_changes(L0, rows, info["horizon_s"])
        S[aud] = {"road_cells_blocked": info["closed_road_cells"],
                  "road_cells_added_by_zone": sum(1 for c in close if c not in close0),
                  "road_cells_earlier_than_fire": sum(1 for c in close if close[c] < close0.get(c, np.inf)),
                  "origins": oc}
        changes[aud] = oc
    # Amendments 4 and 5: the same flame fronts at 5 m receivers along the roads
    changes_fine = {}
    for key, fname, tag in (("fine", "safety_zone_fine.npz", "zone5m"), ("plane", "safety_zone_fine_plane.npz", "zone5m_plane")):
        fz = np.load(HERE / "export_v2" / fname)
        S[key] = {"receiver_height_rule": str(fz["receiver_height_rule"]) if "receiver_height_rule" in fz.files else
                  "one height per cell (Amendment 4)",
                  "step_m": float(fz["step_m"]), "kernel_reproduction_max_abs_w_m2": float(fz["kernel_reproduction_max_abs_w_m2"]),
                  "largest_flux_at_minute_kw_m2": float(fz["raster_flux_kw_m2"].max()),
                  "road_points": int(len(fz["point_piece"])), "road_pieces_evaluated": int(len(np.unique(fz["point_piece"]))),
                  "largest_road_flux_6h_kw_m2": float(fz["point_max_flux_6h_kw_m2"].max())}
        rz, dz = fz["raster_flux_kw_m2"], fz["raster_dist_to_front_m"]
        changes_fine[key] = {}
        for aud, thr in THR.items():
            m = rz >= thr
            now_in = fz["point_flux_now_kw_m2"] >= thr
            cell_first = np.full(fire.shape, np.inf)
            pf_min = fz["point_first_min_%s" % aud]
            for r_, c_, t_ in zip(fz["point_row"], fz["point_col"], pf_min):
                cell_first[r_, c_] = min(cell_first[r_, c_], t_)
            comb = B.earlier_of(cell_first, fire)
            p2 = out / ("fire_plus_%s_%s.tif" % (tag, aud))
            write_raster(p2, comb, grid, Hh, "routing_link %s: earlier of path ignition and 5 m road-point radiant >= %.1f kW/m2"
                         % (S[key]["receiver_height_rule"], thr),
                         {"WFG_BLOCK_RULE": "path %d, %s, radiant %.1f kW/m2 at 5 m road points" % (path, aud, thr)})
            rows, info, close = R.run(graph, origins, exits, p2, grid, workers=1)
            (out / ("fire_plus_%s_%s.json" % (tag, aud))).write_text(json.dumps({"rows": rows, "info": info}, default=str))
            oc = origin_changes(L0, rows, info["horizon_s"])
            changes_fine[key][aud] = oc
            S[key][aud] = {"zone_area_m2_at_minute": float(m.sum() * fz["step_m"] ** 2),
                           "largest_distance_from_front_line_m": float(dz[m].max()) if m.any() else None,
                           "road_pieces_inside_zone_at_minute": int(len(np.unique(fz["point_piece"][now_in]))),
                           "road_pieces_inside_zone_any_minute": int(len(np.unique(fz["point_piece"][np.isfinite(pf_min)]))),
                           "road_cells_blocked": info["closed_road_cells"],
                           "road_cells_added_by_zone": sum(1 for c in close if c not in close0),
                           "origins": oc}
    fz = np.load(HERE / "export_v2" / "safety_zone_fine_plane.npz")
    (out / "summary.json").write_text(json.dumps(S, indent=1))
    figure(graph, grid, fz, minute, path, changes, changes_fine["plane"], S)
    print(json.dumps(S, indent=1))


def figure(graph, grid, fz, minute, path, changes, changes_fine, S):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch, Rectangle

    rz = fz["raster_flux_kw_m2"]
    x0, x1, y0, y1 = (float(v) for v in fz["raster_extent"])
    cls = np.full(rz.shape, np.nan)
    cls[rz >= THR["residents"]] = 1
    cls[rz >= THR["responders"]] = 2
    fronts = fz["fronts_now"]
    fig = plt.figure(figsize=(10.5, 5.9), dpi=300)
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0.06, 0.25, 0.48, 0.72])
    bx = fig.add_axes([0.62, 0.25, 0.36, 0.72])
    for a_ in (ax, bx):
        a_.patch.set_alpha(0)
        for s_ in a_.spines.values():
            s_.set_color(GREY)
        a_.tick_params(colors=GREY, labelsize=7)

    def draw(axis, lw_scale=1.0, cells=True):
        if cells:  # the 375 m grid the pipeline runs on
            gx = grid.x0 + grid.res * np.arange(int(np.floor((x0 - grid.x0) / grid.res)), int(np.ceil((x1 - grid.x0) / grid.res)) + 1)
            gy = grid.ytop - grid.res * np.arange(int(np.floor((grid.ytop - y1) / grid.res)), int(np.ceil((grid.ytop - y0) / grid.res)) + 1)
            for v in gx:
                axis.axvline(v / 1000, color=GREY, lw=0.2, alpha=0.25, zorder=0)
            for v in gy:
                axis.axhline(v / 1000, color=GREY, lw=0.2, alpha=0.25, zorder=0)
        gx5 = np.linspace(x0, x1, rz.shape[1] + 1)[:-1] + (x1 - x0) / rz.shape[1] / 2
        gy5 = np.linspace(y1, y0, rz.shape[0] + 1)[:-1] - (y1 - y0) / rz.shape[0] / 2
        axis.contourf(gx5 / 1000, gy5 / 1000, rz, levels=[THR["residents"], THR["responders"], np.inf],
                      colors=[TINT_LIGHT, TINT_MID], zorder=1)
        xy = {nd["id"]: (nd["x"] / 1000, nd["y"] / 1000) for nd in graph["nodes"]}
        seen = set()
        for e in graph["edges"]:
            k = tuple(sorted((e["id"], e.get("reverse_edge") or e["id"])))
            if k in seen:
                continue
            seen.add(k)
            (xa, ya), (xb, yb) = xy[e["u"]], xy[e["v"]]
            axis.plot([xa, xb], [ya, yb], color=INK, lw=0.6 * lw_scale, solid_capstyle="round", zorder=3)
        for f in fronts:
            axis.plot([f[0] / 1000, f[2] / 1000], [f[1] / 1000, f[3] / 1000], color=RED, lw=1.2 * lw_scale, zorder=2)

    draw(ax)
    ax.set_xlim(x0 / 1000, x1 / 1000)
    ax.set_ylim(y0 / 1000, y1 / 1000)
    ax.set_aspect("equal")
    ax.set_xlabel("x (km, EPSG:5070)", color=GREY, fontsize=8)
    ax.set_ylabel("y (km, EPSG:5070)", color=GREY, fontsize=8)
    # inset: 120 m around the middle of the most powerful burning front
    k = int(np.argmax(fronts[:, 5] * fronts[:, 6]))
    cx, cy = (fronts[k, 0] + fronts[k, 2]) / 2, (fronts[k, 1] + fronts[k, 3]) / 2
    half = 60.0
    ins = ax.inset_axes([0.6, 0.04, 0.38, 0.38])
    ins.patch.set_alpha(0.0)
    draw(ins, lw_scale=1.6, cells=False)
    ins.set_xlim((cx - half) / 1000, (cx + half) / 1000)
    ins.set_ylim((cy - half) / 1000, (cy + half) / 1000)
    ins.set_aspect("equal")
    ins.set_xticks([])
    ins.set_yticks([])
    for s_ in ins.spines.values():
        s_.set_color(INK)
    ins.plot([(cx - half + 8) / 1000, (cx - half + 28) / 1000], [(cy - half + 8) / 1000] * 2, color=INK, lw=1.2)
    ins.text((cx - half + 18) / 1000, (cy - half + 11) / 1000, "20 m", ha="center", fontsize=6, color=INK)
    ax.add_patch(Rectangle(((cx - half) / 1000, (cy - half) / 1000), 2 * half / 1000, 2 * half / 1000,
                           fill=False, edgecolor=INK, lw=0.6, zorder=5))
    F = S["plane"]
    h = [Line2D([0], [0], color=RED, lw=1.4, label="Flame front burning in this path (%d), as the pipeline draws it" % len(fronts)),
         Patch(facecolor=TINT_LIGHT, edgecolor="none", label="Radiant ≥ 2.5 kW/m² (residents): up to %.0f m from a front"
               % F["residents"]["largest_distance_from_front_line_m"]),
         Patch(facecolor=TINT_MID, edgecolor="none", label="Radiant ≥ 7.0 kW/m² (responders): up to %.0f m from a front"
               % F["responders"]["largest_distance_from_front_line_m"]),
         Line2D([0], [0], color=INK, lw=0.8, label="Road (OpenStreetMap); road pieces inside a zone: %d (2.5), %d (7.0)"
                % (F["residents"]["road_pieces_inside_zone_at_minute"], F["responders"]["road_pieces_inside_zone_at_minute"])),
         Line2D([0], [0], color=GREY, lw=0.4, alpha=0.6, label="375 m grid of the forecast")]
    leg = ax.legend(handles=h, loc="upper left", bbox_to_anchor=(0.0, -0.1), fontsize=6.3, frameon=False)
    for t in leg.get_texts():
        t.set_color(INK)
    ax.text(0.01, 0.99, "path %d of 1,024, minute %d after the cutoff (%02d:%02dZ)" % (path, minute, minute // 60, minute % 60),
            transform=ax.transAxes, va="top", ha="left", fontsize=6.3, color=INK)

    # right: routing in the same path, fire arrival alone against fire arrival plus the safety zone
    rows = [("5 m receivers", "residents", changes_fine), ("5 m receivers", "responders", changes_fine),
            ("375 m grid", "residents", changes), ("375 m grid", "responders", changes)]
    xmax = 1.0
    for _, aud, ch in rows:
        if ch[aud]["n_changed"]:
            xmax = max(xmax, max(ch[aud]["earlier_by_min"]))
    rng = np.random.default_rng(0)
    for i, (lab, aud, ch) in enumerate(rows):
        y = len(rows) - 1 - i
        o = ch[aud]
        d = np.array(o["earlier_by_min"], float)
        if len(d):
            bx.scatter(d, y + rng.uniform(-0.15, 0.15, len(d)), s=9, color=RED, edgecolors="none", zorder=3)
        else:
            bx.scatter([0], [y], s=14, facecolors="none", edgecolors=GREY, zorder=3, clip_on=False)
        txt = ("%d of %d origins earlier, median %.0f, largest %.0f min" % (
            o["n_changed"], o["n_origins_routed"], o["earlier_by_min_median"], o["earlier_by_min_largest"])
            if o["n_changed"] else "0 of %d origins change" % o["n_origins_routed"])
        bx.text(0.08, y + 0.22, "%s, %s (%.1f kW/m²): %s" % (lab, aud, THR[aud], txt), fontsize=6.3, color=INK,
                transform=bx.get_yaxis_transform(), ha="left")
    bx.set_yticks([])
    bx.set_ylim(-0.7, len(rows) - 0.3)
    bx.set_xlim(-0.05 * xmax, xmax * 1.1)
    fo = S["fire_only"]
    bx.text(0.08, -0.45, "Fire arrival alone in this path: %d road cell%s blocked, %d of %d origins cut within 6 h"
            % (fo["road_cells_blocked"], "" if fo["road_cells_blocked"] == 1 else "s", fo["origins_with_cut"],
               fo["origins_routed"]), fontsize=6.3, color=GREY, transform=bx.get_yaxis_transform(), ha="left")
    bx.set_xlabel("last safe departure, minutes earlier than with\nfire arrival alone (same path)", color=GREY, fontsize=7.5)
    bx.axvline(0, color=GREY, lw=0.5)
    fig.text(0.01, 0.012, "One possible fire (retained path %d of 1,024), not the forecast. Peak values in that path at that place "
             "and time. 5 m: the pipeline's own flame fronts evaluated at receivers finer than the 375 m grid it runs on, 1.7 m above "
             "its terrain plane; "
             "375 m: the pipeline's receivers (zone empty). A road piece in a zone is blocked." % path,
             color=GREY, fontsize=5.6, wrap=True)
    for e in ("png", "svg", "pdf"):
        fig.savefig(HERE / ("fig_safety_zone.%s" % e), transparent=True)
    plt.close(fig)


if __name__ == "__main__":
    main()
