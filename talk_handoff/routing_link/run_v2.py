"""Amendment 2 end to end: per-path shares -> blocking rasters -> road layer, v1 beside v2. Run from this folder:

    python3 run_v2.py --v2 export_v2 --v1 export_6h --grid GRID_JSON --osm data/fishcreek_osm_20240823.json.gz --out out_v2

Reads the per-path counts (perpath_export.py), the v1 hourly visibility share (same 1,024 paths), both v1 fire-arrival
rasters and the v1 summaries (out_earliest/, out_half/, unchanged). Writes out_v2/ (rasters, routing JSON, summary_v2.json)
and the figure fig_blocked_cells_v2.{png,svg,pdf}.
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
import perpath_rule as PR  # noqa: E402
import route as R  # noqa: E402
from wfg_roadlayer import geotiff  # noqa: E402
from wfg_roadlayer.regiondata import RoadModel  # noqa: E402

ISSUE = "2024-08-23T00:00:00Z"
FIRE = ("earliest", "half")
CRIT = ("radiant_2p5", "radiant_7p0", "co_10", "co_30", "co_60", "vis")
V1_CRIT = {"radiant_2p5": "radiant_residents", "radiant_7p0": "radiant_responders", "co_10": "co_10min",
           "co_30": "co_30min", "co_60": "co_60min"}
V1_VIS = {"p10": "vis_p10", "p50": "vis_p50", "p90": "vis_p90"}
DIAG = 375.0 * np.sqrt(2.0)


def write_raster(path, arr, grid, hours, source, extra):
    md = {"WFG_ISSUE_TIME": ISSUE, "WFG_HORIZON_MIN": int(60 * hours), "WFG_UNITS": "minutes", "WFG_SOURCE": source}
    md.update(extra)
    geotiff.write(path, np.asarray(arr, float), grid.affine, grid.epsg, nodata=float("nan"), dtype="float32", metadata=md)


def origin_changes(L0, rows, H):
    ok = [r for r in rows if r["refusal"] is None and L0[r["origin"]]["refusal"] is None]
    d = []
    for r in ok:
        l0, l1 = L0[r["origin"]]["last_safe_departure_s"], r["last_safe_departure_s"]
        c0, c1 = L0[r["origin"]]["cut_s"], r["cut_s"]
        if (l0, c0) != (l1, c1):  # same convention as run_all.py
            v0 = H if c0 is None else (-1 if l0 is None else l0)
            v1 = H if c1 is None else (-1 if l1 is None else l1)
            d.append((v0 - v1) / 60.0)
    return {"n_origins_routed": len(ok), "n_changed": len(d), "earlier_by_min": sorted(float(x) for x in d),
            "earlier_by_min_median": float(np.median(d)) if d else 0.0,
            "earlier_by_min_largest": float(np.max(d)) if d else 0.0,
            "refused": sum(1 for r in rows if r["refusal"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2", required=True)
    ap.add_argument("--v1", required=True)
    ap.add_argument("--grid", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--out", default=str(HERE / "out_v2"))
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    v2, v1, out = Path(a.v2), Path(a.v1), Path(a.out)
    (out / "rasters").mkdir(parents=True, exist_ok=True)
    (out / "routing").mkdir(parents=True, exist_ok=True)
    grid = G.Grid.from_json(a.grid)

    cz = np.load(v2 / "counts.npz")
    n = int(cz["n_paths"])
    counts = {k: cz[k] for k in CRIT if k != "vis"}
    T = counts["radiant_2p5"].shape[0]
    Hh = T // 60
    ny, nx = counts["radiant_2p5"].shape[1:]
    pv = np.stack([np.load(v1 / ("hour_%02d.npz" % h))["p_vis"] for h in range(Hh)])
    assert np.allclose(pv * n, np.rint(pv * n), atol=1e-6), "p_vis is not a count of the same paths"
    vis_counts = np.repeat(np.rint(pv * n), 60, axis=0)                # hourly share holds for each minute
    v1s = {f: json.loads((HERE / ("out_%s" % f) / "summary.json").read_text()) for f in FIRE}
    v1checks = json.loads((v1 / "checks.json").read_text())
    peaks = np.load(v2 / "peaks.npz")
    dist = {k: v for k, v in np.load(v2 / "distances.npz").items()}
    chk2 = json.loads((v2 / "checks_v2.json").read_text())
    n_cells, n_ch = ny * nx, ny * nx * Hh

    S = {"n_paths": n, "n_hours": Hh, "n_cells": n_cells, "n_cell_hours": n_ch, "checks_v2": chk2}

    # ---- criteria: cell-hours, largest values, first minutes ----
    firsts, ch = {}, {}
    for lv in PR.LEVELS:
        firsts[lv] = {k: PR.first_minute(c, n, lv) for k, c in counts.items()}
        firsts[lv]["vis"] = PR.vis_first_minute(pv, lv, n)
        ch[lv] = {k: int(PR.holds_by_hour(c, n, lv, Hh).sum()) for k, c in counts.items()}
        ch[lv]["vis"] = int(PR.holds_by_hour(vis_counts, n, lv, Hh).sum())
        ch[lv]["cells"] = {k: int(np.isfinite(firsts[lv][k]).sum()) for k in CRIT}
    v1crit = v1s["earliest"]["criterion_cell_hours"]
    S["criterion_cell_hours"] = {"v2": ch, "v1": {
        **{k: v1crit[v] for k, v in V1_CRIT.items()},
        **{"vis_%s" % lv: v1crit[v] for lv, v in V1_VIS.items()}}}
    hrs = ["hour_%d" % h for h in range(Hh)]
    S["largest"] = {
        "v1": {"radiant_kw_m2": max(v1checks[h]["max_binwise_radiant_kw_m2"] for h in hrs),
               "co_60s_ppm": max(v1checks[h]["max_binwise_co_ppm"] for h in hrs),
               "vis_share": max(v1checks[h]["max_visibility_probability"] for h in hrs)},
        "v2_any_path": {"radiant_kw_m2": float(np.nanmax(peaks["radiant_kw_m2_max"])),
                        "co10_ppm": float(np.nanmax(peaks["co10_ppm_max"])),
                        "co30_ppm": float(np.nanmax(peaks["co30_ppm_max"])),
                        "co60_ppm": float(np.nanmax(peaks["co60_ppm_max"]))},
        "v2_median_path": {"radiant_kw_m2": float(np.nanmax(peaks["radiant_kw_m2_q50"])),
                           "co10_ppm": float(np.nanmax(peaks["co10_ppm_q50"])),
                           "co30_ppm": float(np.nanmax(peaks["co30_ppm_q50"])),
                           "co60_ppm": float(np.nanmax(peaks["co60_ppm_q50"]))},
        "v2_largest_share": {**{k: float(c.max()) / n for k, c in counts.items()}, "vis": float(pv.max())},
        "v2_largest_by_hour_any_path": {"radiant_kw_m2": [float(np.nanmax(peaks["radiant_kw_m2_max"][h])) for h in range(Hh)],
                                        "co10_ppm": [float(np.nanmax(peaks["co10_ppm_max"][h])) for h in range(Hh)]},
    }

    # ---- sampling error at blocked cells ----
    se = {}
    for lv in ("p10", "p50", "p90"):
        val = PR.LEVEL_VALUE[lv]
        rec = {}
        for k, c in counts.items():
            f = firsts[lv][k]
            cells = np.flatnonzero(np.isfinite(f).ravel())
            if not len(cells):
                rec[k] = {"cells": 0}
                continue
            kk = c.reshape(T, -1)[f.ravel()[cells].astype(int), cells]
            lo, hi = PR.wilson(kk, n)
            rec[k] = {"cells": int(len(cells)), "interval_includes_level": int(np.sum(lo <= val)),
                      "widest_half_width": float(np.max(hi - lo) / 2)}
        se[lv] = rec
    S["sampling_error_wilson95"] = se

    # ---- road layer ----
    graph, origins, exits, meta = G.build(a.osm, a.grid, ISSUE)
    (out / "routing" / "origins_exits.json").write_text(json.dumps({"origins": origins, "exits": exits, "meta": meta}, indent=1))
    road = RoadModel(graph)
    road_rc = sorted({grid.router_to_raster(c) for c in road.road_cells})
    road_mask = np.zeros((ny, nx), bool)
    for r_, c_ in road_rc:
        road_mask[r_, c_] = True
    S["road_cells"] = int(road_mask.sum())
    fire = {}
    runs = {}
    for f in FIRE:
        arr = np.asarray(geotiff.read(v1 / ("fire_arrival_%s.tif" % f)).data, float)
        fire[f] = np.where(arr > 60 * Hh, np.inf, arr)
        pf = out / "rasters" / ("fire_arrival_only_%s.tif" % f)
        write_raster(pf, fire[f], grid, Hh, "fire arrival (%s reading), cut to the exposure horizon" % f, {})
        rows, info, close0 = R.run(graph, origins, exits, pf, grid, workers=a.workers)
        (out / "routing" / ("fire_only_%s.json" % f)).write_text(json.dumps({"rows": rows, "info": info}, default=str))
        v1_fire = json.loads((HERE / ("out_%s" % f) / "routing" / "fire_only.json").read_text())
        key = lambda r: (r["origin"], r.get("last_safe_departure_s"), r.get("cut_s"), r["refusal"])  # noqa: E731
        same = [key(r) for r in rows] == [key(r) for r in v1_fire["rows"]]
        runs[f] = {"fire_only": {"road_cells_blocked": info["closed_road_cells"], "equal_to_v1": bool(same),
                                 "fire_cell_hours": int(PR.minute_to_hours(fire[f], Hh).sum())}}
        L0 = {r["origin"]: r for r in rows}
        fire_h = PR.minute_to_hours(np.where(np.isnan(fire[f]), np.inf, fire[f]), Hh)
        for aud in PR.AUDIENCES:
            for lv in PR.LEVELS:
                exp = PR.audience_first_minute(firsts[lv], aud)
                comb = B.earlier_of(exp, fire[f])
                tag = "%s_%s_%s" % (f, aud, lv)
                p2 = out / "rasters" / ("earliest_fire_or_exposure_%s.tif" % tag)
                write_raster(p2, comb, grid, Hh, "routing_link v2: earlier of per-path exposure share and fire arrival",
                             {"WFG_BLOCK_RULE": "PROTOCOL.md Amendment 2, %s, share of %d paths %s, radiant %s, CO AEGL-2, "
                              "visibility 10 m; fire reading %s" % (aud, n, lv, PR.RADIANT_FOR[aud], f)})
                rows2, info2, close2 = R.run(graph, origins, exits, p2, grid, workers=a.workers)
                (out / "routing" / ("fire_plus_exposure_%s.json" % tag)).write_text(
                    json.dumps({"rows": rows2, "info": info2}, default=str))
                comb_h = PR.minute_to_hours(comb, Hh)
                fcut = np.where(np.isnan(fire[f]), np.inf, fire[f])
                earlier = exp < fcut
                runs[f]["%s_%s" % (aud, lv)] = {
                    "road_cells_blocked": info2["closed_road_cells"],
                    "road_cells_added_by_exposure": int(sum(1 for c in close2 if c not in close0)),
                    "road_cells_earlier_than_fire": int(sum(1 for c in close2 if close2[c] < close0.get(c, np.inf))),
                    "added_cell_hours": int((comb_h & ~fire_h).sum()),
                    "cells_blocked_earlier_than_fire": int(earlier.sum()),
                    "road_cells_exposure_earlier_than_fire": int((earlier & road_mask).sum()),
                    "origins": origin_changes(L0, rows2, info2["horizon_s"])}
                print(f, aud, lv, runs[f]["%s_%s" % (aud, lv)]["road_cells_blocked"],
                      runs[f]["%s_%s" % (aud, lv)]["origins"]["n_changed"], flush=True)
    S["runs"] = runs
    S["runs_v1"] = {f: {"fire_only_road_cells": json.loads((HERE / ("out_%s" % f) / "routing" / "fire_only.json")
                                                          .read_text())["info"]["closed_road_cells"],
                        **{tag: {"road_cells_blocked": json.loads((HERE / ("out_%s" % f) / "routing" /
                                                                    ("fire_plus_exposure_%s.json" % tag)).read_text())["info"]["closed_road_cells"],
                                 "added_cell_hours": v1s[f]["added_cell_hours"][tag]["exposure_blocked_not_fire"],
                                 "origins_changed": v1s[f]["origins"][tag]["n_changed"]}
                           for tag in v1s[f]["origins"]}} for f in FIRE}

    # ---- distance to the nearest burning cell (Amendment 2 item 7) ----
    D = {}
    lvl, crit_, rr, cc = dist["level"], dist["criterion"], dist["row"], dist["col"]
    for lv in PR.LEVELS:
        D[lv] = {}
        for k in ("radiant_2p5", "radiant_7p0", "co_10", "co_30", "co_60"):
            m = (lvl == lv) & (crit_ == k)
            if not m.any():
                D[lv][k] = {"cells": 0}
                continue
            med = dist["dist_median_m"][m]
            onroad = road_mask[rr[m], cc[m]]
            D[lv][k] = {"cells": int(m.sum()), "road_cells": int(onroad.sum()),
                        "median_of_cell_medians_m": float(np.median(med)),
                        "largest_cell_median_m": float(np.max(med)),
                        "largest_distance_any_path_m": float(np.max(dist["dist_max_m"][m])),
                        "cells_median_0_m": int(np.sum(med == 0)),
                        "cells_median_within_one_cell": int(np.sum(med <= DIAG + 1e-6)),
                        "cells_median_beyond_one_cell": int(np.sum(med > DIAG + 1e-6))}
            if onroad.any():
                D[lv][k]["road"] = [{"row": int(r_), "col": int(c_), "minute": int(mi), "share": float(sh),
                                     "n_paths": int(npth), "median_m": float(md), "min_m": float(mn), "max_m": float(mx)}
                                    for r_, c_, mi, sh, npth, md, mn, mx in zip(
                                        rr[m][onroad], cc[m][onroad], dist["minute"][m][onroad], dist["share"][m][onroad],
                                        dist["n_paths"][m][onroad], med[onroad], dist["dist_min_m"][m][onroad],
                                        dist["dist_max_m"][m][onroad])]
    S["distance_to_burning_cell"] = D

    (out / "summary_v2.json").write_text(json.dumps(S, indent=1))
    import figure
    main_comb = B.earlier_of(PR.audience_first_minute(firsts[PR.MAIN], "residents"), fire["half"])
    figure.make(graph, grid, fire["half"], main_comb, HERE / "fig_blocked_cells_v2",
                horizon_label="6 h from 2024-08-23T00:00Z", fire_label="Blocked by fire arrival (half of 1,024 paths)",
                exposure_label="Added by exposure (residents, share of paths ≥ 0.5*)",
                note="*0.5 share of paths: our choice; visibility 10 m: building-egress assumption")
    print(json.dumps({k: S[k] for k in ("criterion_cell_hours", "largest")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
