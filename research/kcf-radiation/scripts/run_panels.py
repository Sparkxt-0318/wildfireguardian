"""Step 3: the heat term on every road cell and issue hour, and its effect on leave-by times
(PROTOCOL.md sections 6-7).

Panel A: Gyeongbuk 25 March 2025 replay, 13 issue hours x 2 regions (MEASURED arm, 8 h horizon GeoTIFFs).
Panel B: the finals forecast packets, 15 packets x 5 regions (1 h horizon).

For each input: spread rate from the full arrival grid; per road cell the fuel group, wind, RH and air temperature
at the cell's arrival hour; intensity, crown test, flame length, tilt, height, flux at the road from the adjacent
cell, safe distances at 7 / 4.7 / 2.5 kW/m2; closures and leave-by times for: no heat, the old kcf-heat law, and
the new method at each threshold. Low and high fuel levels are run for the counts as well.

    python scripts/run_panels.py --env ENV_REGIONS --replay DIR --packets DIR --graphs DIR --out DIR
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_radiation import closure, envdata, fuels, inputs, model, oldlaw, radiation, ros, routing  # noqa: E402
from kcf_radiation.protocol import R_MAX_M_S, R_MIN_M_S, BASELINE, THRESHOLDS  # noqa: E402

REGION_ENV = {"uiseong_andong_2025": "KFS_01", "yeongdeok_2025": "KFS_01", "uljin_2022": "KFS_02",
              "hongseong_2023": "KFS_05", "miryang_2022": "KFS_11"}


def env_at_cells(env, road, cells, when_utc):
    """Land-cover group, 10 m wind speed (m/s), RH (%), air temperature (C) per cell at its own hour."""
    xs, ys = inputs.cell_centres(road)
    r, c = np.divmod(np.asarray(cells), road.W)
    er, ec = env.cell_index(xs[r, c], ys[r, c])
    ok = er >= 0
    lc = np.where(ok, env.landcover[np.maximum(er, 0), np.maximum(ec, 0)], np.nan)
    groups = np.array([fuels.group_of(v) if np.isfinite(v) else "grass" for v in lc])
    U = np.full(len(cells), np.nan); RH = np.full(len(cells), np.nan); TA = np.full(len(cells), np.nan)
    for var, arr in (("wind_speed_10m", U), ("relative_humidity_2m", RH), ("temperature_2m", TA)):
        cache = {}
        for i, t in enumerate(when_utc):
            key = t.replace(minute=0, second=0, microsecond=0) + (timedelta(hours=1) if t.minute >= 30 else timedelta())
            if key not in cache:
                cache[key] = env.at_hour(var, key)[0]
            if ok[i]:
                arr[i] = cache[key][er[i], ec[i]]
    return groups, U, RH, TA, lc


def adjacent_exposure(road, A_grid, cells):
    """For each road cell: distance (m) from its road pieces to the nearest neighbouring cell that burns EARLIER,
    and that neighbour (or -1). Used for 'flux at the road from the adjacent cell'."""
    from kcf_radiation import roadgeom
    P = roadgeom.pieces(road)
    out_d, out_n = {}, {}
    by_cell = {}
    for i, c in enumerate(P["cell"].tolist()):
        by_cell.setdefault(c, []).append(i)
    for c in cells:
        rr, cc = divmod(c, road.W)
        a = A_grid[rr, cc]
        best, bn = math.inf, -1
        idx = by_cell.get(c, [])
        if not idx:
            continue
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == dc == 0:
                    continue
                r2, c2 = rr + dr, cc + dc
                if not (0 <= r2 < road.H and 0 <= c2 < road.W):
                    continue
                an = A_grid[r2, c2]
                if not (np.isfinite(an) and (not np.isfinite(a) or an < a)):
                    continue
                n = r2 * road.W + c2
                xmin, xmax, ymin, ymax = roadgeom.cell_rect_arrays(road, [n])
                d = roadgeom.segment_rect_distance(P["x0"][idx], P["y0"][idx], P["x1"][idx], P["y1"][idx],
                                                   xmin[0], xmax[0], ymin[0], ymax[0]).min()
                if d < best:
                    best, bn = float(d), n
        out_d[c], out_n[c] = best, bn
    return out_d, out_n


def one_input(kind, path, rid, issue, road_region, env, settings, workers=1):
    road = road_region.road
    if kind == "geotiff":
        A_grid, H = inputs.arrival_grid_geotiff(path, road)
    else:
        A_grid, H = inputs.arrival_grid_packet(path, road)
    H = int(math.floor(H))
    R_grid, rinfo = ros.rate_of_spread(np.where(np.isfinite(A_grid), A_grid, np.nan), float(road.res), R_MIN_M_S, R_MAX_M_S)
    arrival = {}
    for c in road.road_cells:
        v = A_grid[divmod(c, road.W)]
        if np.isfinite(v) and v <= H:
            arrival[c] = int(v)
    burning = sorted({int(r * road.W + c) for r, c in zip(*np.nonzero(np.isfinite(A_grid) & (A_grid <= H)))})
    # physics on every burning cell within the horizon (road cells need their neighbours too)
    when = [issue + timedelta(seconds=float(A_grid[divmod(c, road.W)])) for c in burning]
    groups, U, RH, TA, lc = env_at_cells(env, road, burning, when)
    Rb = np.array([R_grid[divmod(c, road.W)] for c in burning])
    phys = {}
    for name, st in settings.items():
        phys[name] = model.Evaluator(st).cells(Rb, groups, np.nan_to_num(U, nan=float(np.nanmedian(U) if np.isfinite(U).any() else 5.0)),
                                               np.nan_to_num(RH, nan=50.0), np.nan_to_num(TA, nan=10.0))
    idx = {c: i for i, c in enumerate(burning)}
    ros_d = {c: float(Rb[i]) for c, i in idx.items()}
    # closures
    variants = {"none": closure.HeatClosure(road, arrival, ros_d, {}, H=H)}
    for q in THRESHOLDS:
        variants["old_%g" % q] = closure.HeatClosure(road, arrival, {c: oldlaw.R_PACKET_M_S for c in burning},
                                                     {c: oldlaw.dstar_m(q) for c in burning}, H=H)
        for name in settings:
            ds = phys[name]["dstar_%g" % q]
            variants["%s_%g" % (name, q)] = closure.HeatClosure(road, arrival, ros_d, {c: float(ds[i]) for c, i in idx.items()}, H=H)
    leave = {}
    for vname, hc in variants.items():
        rows, _ = routing.leave_by(road_region, hc, workers=workers)
        leave[vname] = rows
    # per road cell table
    adj_d, adj_n = adjacent_exposure(road, A_grid, road.road_cells)
    base = phys["baseline"]
    cell_rows = []
    for c in road.road_cells:
        if c not in idx:
            continue
        i = idx[c]
        rec = {"region": rid, "issue_utc": issue.strftime("%Y-%m-%dT%H:%MZ"), "cell": c, "arrival_s": arrival.get(c),
               "ros_m_min": round(float(Rb[i]) * 60, 3), "lc_class": None if not np.isfinite(lc[i]) else int(lc[i]),
               "fuel_group": str(groups[i]), "wind10_m_s": None if not np.isfinite(U[i]) else round(float(U[i]), 2),
               "rh_pct": None if not np.isfinite(RH[i]) else round(float(RH[i]), 1),
               "I_surface_kw_m": round(float(base["I_surface"][i]), 1), "crown": bool(base["crown"][i]),
               "cfb": round(float(base["cfb"][i]), 3), "I_total_kw_m": round(float(base["I_total"][i]), 1),
               "flame_length_m": round(float(base["L"][i]), 2), "tilt_deg": round(math.degrees(float(base["theta"][i])), 1),
               "flame_height_m": round(float(base["H"][i]), 2)}
        for q in THRESHOLDS:
            d = float(base["dstar_%g" % q][i])
            rec["dstar_%g_m" % q] = round(d, 2)
            rec["lead_%g_s" % q] = round(d / float(Rb[i]), 1)
            for name in settings:
                if name != "baseline":
                    rec["dstar_%g_m_%s" % (q, name)] = round(float(phys[name]["dstar_%g" % q][i]), 2)
        # flux at the road when the earlier-burning adjacent cell is reached (front assumed at its nearest edge)
        dn, nn = adj_d.get(c, math.inf), adj_n.get(c, -1)
        if nn >= 0 and nn in idx:
            j = idx[nn]
            fl = radiation.Flame(float(base["L"][j]), float(base["theta"][j]), BASELINE.front_width_m)
            pw = float(np.nan_to_num(RH[j], nan=50.0)) / 100 * radiation.saturation_vapour_pressure_pa(float(np.nan_to_num(TA[j], nan=10.0)))
            dd = max(dn, radiation.D_MIN + (fl.L * math.sin(fl.theta) if BASELINE.vf_kind == "tilted" else 0.0))
            from kcf_radiation.table import _temp_for_pw
            q_adj = radiation.flux(dd, fl, T_flame_K=BASELINE.T_flame_K, emissivity=BASELINE.emissivity,
                                   vf_kind=BASELINE.vf_kind, z_r=BASELINE.receiver_height_m,
                                   rh_pct=100.0, T_air_C=_temp_for_pw(max(pw, 1.0)))
            rec["adjacent_distance_m"] = round(dn, 1)
            rec["flux_from_adjacent_kw_m2"] = round(q_adj, 3)
            rec["zone_from_adjacent"] = ("ge7" if q_adj >= 7 else "4.7-7" if q_adj >= 4.7 else "2.5-4.7" if q_adj >= 2.5 else "lt2.5")
        else:
            rec["adjacent_distance_m"] = None
            rec["flux_from_adjacent_kw_m2"] = None
            rec["zone_from_adjacent"] = None
        for vname, hc in variants.items():
            pcs = np.nonzero(hc.P["cell"] == c)[0]
            if pcs.size:
                b = hc.piece_close[pcs]
                rec["close_min_s_%s" % vname] = None if not np.isfinite(b).any() else int(np.nanmin(b))
        cell_rows.append(rec)
    # pieces outside burning cells closed by a neighbour's halo (count only)
    halo = {}
    for vname, hc in variants.items():
        halo[vname] = int(sum(1 for c, b in zip(hc.P["cell"].tolist(), hc.piece_close.tolist())
                              if math.isfinite(b) and c not in arrival))
    return {"region": rid, "issue_utc": issue.strftime("%Y-%m-%dT%H:%MZ"), "kind": kind, "path": str(path), "H": H,
            "ros_info": rinfo, "burning_cells": len(burning), "road_cells": len(road.road_cells),
            "road_cells_reached": len(arrival), "halo_pieces": halo, "leave": leave, "cells": cell_rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", type=Path, required=True)
    ap.add_argument("--replay", type=Path)
    ap.add_argument("--packets", type=Path)
    ap.add_argument("--graphs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    from kcf_radiation.protocol import SENSITIVITY_SETTINGS
    settings = {"baseline": BASELINE, **SENSITIVITY_SETTINGS}
    a.out.mkdir(parents=True, exist_ok=True)
    regions, envs = {}, {}
    jobs = []
    if a.replay:
        for p in sorted(a.replay.glob("fire_arrival_*_MEASURED_8h.tif")):
            issue = datetime.strptime(p.name.split("_")[2], "%Y%m%dT%H%MZ").replace(tzinfo=timezone.utc)
            for rid in ("uiseong_andong_2025", "yeongdeok_2025"):
                jobs.append(("A", "geotiff", p, rid, issue))
    if a.packets:
        for rid in ("uiseong_andong_2025", "yeongdeok_2025", "uljin_2022", "hongseong_2023", "miryang_2022"):
            for p in sorted((a.packets / rid).iterdir()):
                issue = datetime.strptime(p.name, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                jobs.append(("B", "packet", p, rid, issue))
    for panel, kind, p, rid, issue in jobs:
        if rid not in regions:
            regions[rid] = routing.AnyRegion(rid, a.graphs / rid / "graph.json")
        k = REGION_ENV[rid]
        if k not in envs:
            envs[k] = envdata.Environment(a.env / k)
        t0 = time.time()
        res = one_input(kind, p, rid, issue, regions[rid], envs[k], settings, workers=a.workers)
        res["panel"] = panel
        tag = "%s_%s_%s" % (panel, rid, issue.strftime("%Y%m%dT%H%MZ"))
        with gzip.open(a.out / (tag + ".json.gz"), "wt") as f:
            json.dump(res, f, default=lambda o: o.item() if hasattr(o, "item") else str(o))
        print(tag, "cells", len(res["cells"]), "wall %.1f s" % (time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
