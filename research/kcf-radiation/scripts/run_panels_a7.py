"""PROTOCOL A7 rerun: panels A and B under the old rule (flat known-fire cells get the 150 m/min cap) and the new rule
(nearest real-gradient spread rate), side by side, from one process per input so that identical closures are routed once.

Environment per road cell (fuel group, 10 m wind, RH) comes from the committed per-road-cell tables
data/panels/road_cells_panel_{A,B}.csv.gz; air temperature is recovered per cell from the recorded baseline d* at the
three thresholds (PROTOCOL A7, "Method of the rerun"). Output: OUT/old/<tag>.json.gz and OUT/new/<tag>.json.gz in the
format scripts/summarize.py reads, plus OUT/fix_log.json (per input: spread-rate provenance counts, no-donor cells).

    python scripts/run_panels_a7.py --replay DIR --packets DIR --graphs DIR --out DIR [--workers N] [--regions ...]
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_radiation import closure, inputs, model, oldlaw, ros, routing  # noqa: E402
from kcf_radiation.protocol import BASELINE, R_MAX_M_S, R_MIN_M_S, SENSITIVITY_SETTINGS, THRESHOLDS  # noqa: E402

ROUTED_SENS_Q = 4.7
CELLS_CSV = {"A": HERE / "data/panels/road_cells_panel_A.csv.gz", "B": HERE / "data/panels/road_cells_panel_B.csv.gz"}
_ENV = {}


def load_env(panel):
    """(region, issue_utc) -> {cell: dict(fuel, U, RH, rec_d, ros_rec, arrival)}"""
    if panel in _ENV:
        return _ENV[panel]
    out = defaultdict(dict)
    with gzip.open(CELLS_CSV[panel], "rt", newline="") as f:
        for r in csv.DictReader(f):
            fl = lambda k: float(r[k]) if r[k] != "" else float("nan")
            out[(r["region"], r["issue_utc"])][int(r["cell"])] = {
                "fuel": r["fuel_group"], "U": fl("wind10_m_s"), "RH": fl("rh_pct"), "ros_rec": fl("ros_m_min"),
                "rec_d": (fl("dstar_7_m"), fl("dstar_4.7_m"), fl("dstar_2.5_m")), "arrival": r["arrival_s"]}
    _ENV[panel] = out
    return out


def infer_temperature(rows):
    """Per-row air temperature (C) that reproduces the recorded baseline d* at 7 / 4.7 / 2.5 (old rule, recorded R)."""
    if not rows:
        return np.zeros(0), np.zeros(0)
    keys = {}
    for i, r in enumerate(rows):
        keys.setdefault((r["fuel"], r["ros_rec"], r["U"], r["RH"], r["rec_d"]), []).append(i)
    uk = list(keys)
    R = np.array([k[1] for k in uk]) / 60.0
    grp = np.array([k[0] for k in uk])
    U = np.nan_to_num(np.array([k[2] for k in uk]), nan=5.0)
    RH = np.nan_to_num(np.array([k[3] for k in uk]), nan=50.0)
    rec = np.array([k[4] for k in uk])
    ev = model.Evaluator(BASELINE)
    Ts = list(range(-10, 36, 1))
    err = np.zeros((len(Ts), len(uk)))
    for j, T in enumerate(Ts):
        ph = ev.cells(R, grp, U, RH, np.full(len(uk), float(T)))
        d = np.stack([ph["dstar_7"], ph["dstar_4.7"], ph["dstar_2.5"]], axis=1)
        err[j] = np.abs(d - rec).sum(axis=1)
    best = err.min(axis=0)
    Tfit = np.zeros(len(uk))
    for u in range(len(uk)):
        ok = np.nonzero(err[:, u] <= best[u] + 0.03)[0]
        Tfit[u] = float(np.median([Ts[j] for j in ok]))
    out = np.zeros(len(rows))
    for u, k in enumerate(uk):
        for i in keys[k]:
            out[i] = Tfit[u]
    return out, best


def physics(R_m_s, groups, U, RH, TA, settings):
    phys = {}
    if len(R_m_s) == 0:
        z = np.zeros(0)
        for name, st in settings.items():
            phys[name] = {k: z for k in ("crown", "L", "H", "dstar_7", "dstar_4.7", "dstar_2.5")}
        return phys
    for name, st in settings.items():
        if name != "baseline":
            st = replace(st, thresholds=(ROUTED_SENS_Q,))
        ok = np.isfinite(R_m_s)
        Rf = np.where(ok, R_m_s, 1.0)
        ph = model.Evaluator(st).cells(Rf, groups, U, RH, TA)
        for k in [k for k in ph if k.startswith("dstar_")]:
            ph[k] = np.where(ok, ph[k], 0.0)   # no spread rate (no donor): no flame, d* = 0
        phys[name] = ph
    return phys


def one_input(job):
    panel, kind, path, rid, issue, graphs, workers, with_sens = job
    t0 = time.time()
    region = routing.AnyRegion(rid, Path(graphs) / rid / "graph.json")
    road = region.road
    A_grid, H = (inputs.arrival_grid_geotiff if kind == "geotiff" else inputs.arrival_grid_packet)(path, road)
    H = int(math.floor(H))
    A_fin = np.where(np.isfinite(A_grid), A_grid, np.nan)
    known = np.isfinite(A_grid) & (A_grid == 0)
    arrival = {}
    for c in road.road_cells:
        v = A_grid[divmod(c, road.W)]
        if np.isfinite(v) and v <= H:
            arrival[c] = int(v)
    cells = sorted(arrival)
    key = (rid, issue.strftime("%Y-%m-%dT%H:%MZ"))
    env = load_env(panel)[key]
    missing = [c for c in cells if c not in env]
    if missing or len(env) != len(cells):
        raise RuntimeError("cell table mismatch for %s: %d missing, %d vs %d" % (key, len(missing), len(env), len(cells)))
    rows = [env[c] for c in cells]
    TA, fit_err = infer_temperature(rows)
    groups = np.array([r["fuel"] for r in rows])
    U = np.nan_to_num(np.array([r["U"] for r in rows]), nan=float(np.nanmedian([r["U"] for r in rows]) if any(np.isfinite(r["U"]) for r in rows) else 5.0))
    RH = np.nan_to_num(np.array([r["RH"] for r in rows]), nan=50.0)
    settings = {"baseline": BASELINE, **(SENSITIVITY_SETTINGS if with_sens else {})}

    g_grid = ros.gradient_magnitude(A_fin, float(road.res))
    real_grad = np.isfinite(g_grid) & (g_grid > 0)
    R_old, info_old = ros.rate_of_spread(A_fin, float(road.res), R_MIN_M_S, R_MAX_M_S)
    R_new, info_new, src = ros.rate_of_spread_with_source(A_fin, float(road.res), R_MIN_M_S, R_MAX_M_S, known_fire=known)
    # recorded spread rate check (old rule)
    Rc_old = np.array([R_old[divmod(c, road.W)] for c in cells])
    rec_R = np.array([r["ros_rec"] for r in rows]) / 60.0
    ros_mismatch = int(np.sum(np.abs(Rc_old - rec_R) > 2e-5))

    results, leave_all, memo = {}, {}, {}
    for rule, Rg in (("old", R_old), ("new", R_new)):
        Rc = np.array([Rg[divmod(c, road.W)] for c in cells])
        phys = physics(Rc, groups, U, RH, TA, settings)
        ros_d = {c: float(Rc[i]) for i, c in enumerate(cells)}
        variants = {"none": closure.HeatClosure(road, arrival, ros_d, {}, H=H)}
        for q in THRESHOLDS:
            variants["old_%g" % q] = closure.HeatClosure(road, arrival, {c: oldlaw.R_PACKET_M_S for c in cells},
                                                         {c: oldlaw.dstar_m(q) for c in cells}, H=H)
            for name in settings:
                if name != "baseline" and q != ROUTED_SENS_Q:
                    continue
                ds = phys[name]["dstar_%g" % q]
                variants["%s_%g" % (name, q)] = closure.HeatClosure(road, arrival, ros_d, {c: float(ds[i]) for i, c in enumerate(cells)}, H=H)
        leave = {}
        for vname, hc in variants.items():
            k = hash((tuple(map(tuple, hc.edge_blocks())), tuple(map(tuple, hc.wait_blocks())), hc.node_close.tobytes()))
            if k not in memo:
                memo[k], _ = routing.leave_by(region, hc, workers=workers)
            leave[vname] = memo[k]
        base = phys["baseline"]
        cell_rows = []
        for i, c in enumerate(cells):
            rec = {"region": rid, "issue_utc": key[1], "cell": c, "arrival_s": arrival[c],
                   "ros_m_min": round(float(Rc[i]) * 60, 3) if np.isfinite(Rc[i]) else None,
                   "fuel_group": str(groups[i]), "known_fire": bool(known[divmod(c, road.W)]),
                   "ros_source": int(src[divmod(c, road.W)]) if rule == "new" else (0 if real_grad[divmod(c, road.W)] else 2),
                   "crown": bool(base["crown"][i]), "flame_length_m": round(float(base["L"][i]), 2),
                   "flame_height_m": round(float(base["H"][i]), 2), "T_air_fit_C": float(TA[i])}
            for q in THRESHOLDS:
                d = float(base["dstar_%g" % q][i])
                rec["dstar_%g_m" % q] = round(d, 2)
                rec["lead_%g_s" % q] = round(d / float(Rc[i]), 1) if np.isfinite(Rc[i]) else 0.0
            for name in settings:
                if name != "baseline":
                    rec["dstar_%g_m_%s" % (ROUTED_SENS_Q, name)] = round(float(phys[name]["dstar_%g" % ROUTED_SENS_Q][i]), 2)
            pcs = {}
            for vname, hc in variants.items():
                pp = np.nonzero(hc.P["cell"] == c)[0]
                if pp.size:
                    b = hc.piece_close[pp]
                    rec["close_min_s_%s" % vname] = None if not np.isfinite(b).any() else int(np.nanmin(b))
            cell_rows.append(rec)
        halo, halo_cells = {}, {}
        for vname, hc in variants.items():
            hit = [c for c, b in zip(hc.P["cell"].tolist(), hc.piece_close.tolist()) if math.isfinite(b) and c not in arrival]
            halo[vname] = len(hit)
            halo_cells[vname] = sorted(set(hit))
        results[rule] = {"region": rid, "issue_utc": key[1], "kind": kind, "path": str(path), "H": H, "panel": panel,
                         "road_cells_reached": len(arrival), "halo_pieces": halo, "halo_cells": halo_cells,
                         "leave": leave, "cells": cell_rows, "ros_info": info_old if rule == "old" else info_new}
    flatk = [(c, int(src[divmod(c, road.W)])) for c in cells if known[divmod(c, road.W)] and not real_grad[divmod(c, road.W)]]
    log = {"panel": panel, "region": rid, "issue_utc": key[1], "road_cells": len(cells), "road_cells_known_fire": int(sum(1 for c in cells if known[divmod(c, road.W)])),
           "road_cells_known_fire_flat": len(flatk), "road_flat_known_src_counts": {str(s): sum(1 for _, x in flatk if x == s) for s in {x for _, x in flatk}},
           "info_old": info_old, "info_new": info_new, "ros_rec_mismatch_cells": ros_mismatch, "T_fit_residual_max_m": float(fit_err.max()) if fit_err.size else 0.0,
           "T_fit_residual_cells_gt_0.05": int((fit_err > 0.05).sum()), "wall_s": round(time.time() - t0, 1)}
    return panel, rid, issue, results, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", type=Path)
    ap.add_argument("--packets", type=Path)
    ap.add_argument("--graphs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=4, help="processes over inputs")
    ap.add_argument("--regions", nargs="*")
    ap.add_argument("--panels", default="AB")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--no-sens", action="store_true", help="route only none / old law / baseline at the three thresholds")
    a = ap.parse_args()
    jobs = []
    if a.replay and "A" in a.panels:
        for p in sorted(a.replay.glob("fire_arrival_*_MEASURED_8h.tif")):
            issue = datetime.strptime(p.name.split("_")[2], "%Y%m%dT%H%MZ").replace(tzinfo=timezone.utc)
            for rid in ("uiseong_andong_2025", "yeongdeok_2025"):
                jobs.append(("A", "geotiff", p, rid, issue, a.graphs, 1, not a.no_sens))
    if a.packets and "B" in a.panels:
        for rid in ("uiseong_andong_2025", "yeongdeok_2025", "uljin_2022", "hongseong_2023", "miryang_2022"):
            for p in sorted((a.packets / rid).iterdir()):
                issue = datetime.strptime(p.name, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                jobs.append(("B", "packet", p, rid, issue, a.graphs, 1, not a.no_sens))
    if a.regions:
        jobs = [j for j in jobs if j[3] in a.regions]
    for d in ("old", "new", "log"):
        (a.out / d).mkdir(parents=True, exist_ok=True)
    def tag(j):
        return "%s_%s_%s" % (j[0], j[3], j[4].strftime("%Y%m%dT%H%MZ"))
    if a.skip_existing:
        jobs = [j for j in jobs if not (a.out / "new" / (tag(j) + ".json.gz")).is_file()]
    print(len(jobs), "inputs", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(one_input, j) for j in jobs]
        for fu in as_completed(futs):
            panel, rid, issue, results, log = fu.result()
            tg = "%s_%s_%s" % (panel, rid, issue.strftime("%Y%m%dT%H%MZ"))
            for rule in ("old", "new"):
                with gzip.open(a.out / rule / (tg + ".json.gz"), "wt") as f:
                    json.dump(results[rule], f, default=lambda o: o.item() if hasattr(o, "item") else str(o))
            (a.out / "log" / (tg + ".json")).write_text(json.dumps(log, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
            print(tg, "wall %.0f s" % log["wall_s"], "known flat road cells", log["road_cells_known_fire_flat"], "ros mismatch", log["ros_rec_mismatch_cells"], flush=True)


if __name__ == "__main__":
    main()
