"""Safety zone on every path where CO blocks a road cell (PROTOCOL.md Amendment 6). Run like perpath_export.py:

    cd WORKSPACE && PYTHONPATH=WORKSPACE python co_paths_zone_export.py --grid GRID_JSON --osm OSM_JSON --out export_v2

Writes export_v2/co_paths/path_NNNN.npz per selected path and export_v2/co_paths/selection.json.
Per path: fire_arrival_min [ny, nx] (the path's ignition minute; 0 at the cutoff; +inf never), co_first_min [ny, nx]
(first minute any CO window holds), max_radiant_375m_kw_m2, and the 5 m road points (terrain-plane receivers):
point_row/col/piece, point_first_min_residents/responders, point_dist_at_first_m_residents/responders, point_max_kw_m2.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import perpath_export as E  # noqa: E402
from safety_zone_fine import seg_distance  # noqa: E402

STEP, RADIUS = 5.0, 1000.0
THR = {"residents": 2500.0, "responders": 7000.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch", type=int, default=16)
    a = ap.parse_args()
    out = Path(a.out) / "co_paths"
    out.mkdir(parents=True, exist_ok=True)
    import wildfire.physical_hazards as PH
    from wildfire import monte_carlo_hazards as mch
    import osm_graph as G

    fronts, real = [], PH.SolidFlameFront

    def recorder(*args, **kw):
        f = real(*args, **kw)
        fronts.append(f)
        return f

    initial, spread, factory = E.setup(6)
    cap = []
    orig = mch._window_exposure
    mch._window_exposure = lambda *x, **k: cap.append((x, k))
    PH.SolidFlameFront = recorder
    try:
        spread.calculate_hazards(hours_later=list(range(6)), initial_activity=initial, physical_factory=factory,
                                 ignition_timing="uniform_within_step", timing_seed=E.SEED, time_step_s=60.,
                                 batch_size=E.BATCH_PIPELINE, activity_mode="probability_map")
    finally:
        mch._window_exposure = orig
        PH.SolidFlameFront = real
    phys = [c[0][6] for c in cap]
    ph = phys[0]
    p = ph.parameters_dict()
    tau, normal = p["atmospheric_transmissivity"], p["receiver_normal"]
    src = ph.source_flat_indices
    ny, nx = ph.receiver_shape
    ncell = ny * nx
    ground = ph.receiver_environment.ground_xyz_m.reshape(ny, nx, 3)
    gradient = np.asarray(ph.environment.terrain_gradient, float).reshape(ny, nx, 2)
    n_per = int(np.sum(np.asarray(ph.heat_release_w) > 0))
    fr = fronts[:n_per]
    centres = np.array([(np.asarray(f.base_start_xy_m) + np.asarray(f.base_end_xy_m)) / 2 for f in fr])
    cell_xy = ground.reshape(-1, 3)[src, :2]
    which = np.array([int(np.argmin(np.hypot(*(cell_xy - c).T))) for c in centres])
    assert len(set(which.tolist())) == len(fr)
    front_of = {int(s): fr[i] for i, s in enumerate(which)}
    centre_of = {int(s): centres[i] for i, s in enumerate(which)}

    grid = G.Grid.from_json(a.grid)
    graph, _, _, _ = G.build(a.osm, a.grid, "2024-08-23T00:00:00Z")
    road_mask = np.zeros((ny, nx), bool)
    xy = {nd["id"]: (nd["x"], nd["y"]) for nd in graph["nodes"]}
    pieces, seen = [], set()
    for e in graph["edges"]:
        for s_ in e["segments"]:
            r_, c_ = grid.router_to_raster(s_["cell"])
            road_mask[r_, c_] = True
        k = tuple(sorted((e["id"], e.get("reverse_edge") or e["id"])))
        if k not in seen:
            seen.add(k)
            pieces.append((k[0], np.array(xy[e["u"]], float), np.array(xy[e["v"]], float)))
    road_idx = np.flatnonzero(road_mask.ravel())

    pw = E.PathWeights(cap)
    P = pw.n
    edges = np.r_[np.arange(0., 3600., 60.), 3600.]
    T, nb = 360, 60
    first = np.asarray(spread.trajectories.select()[0])

    # pass 1: per-path CO at road cells; keep each selected path's first CO minute for every cell
    selected, co_first = [], {}
    for b0 in range(0, P, a.batch):
        paths = np.arange(b0, min(P, b0 + a.batch))
        co_all = np.empty((len(paths), T, ncell))
        for h in range(6):
            w = pw.weights(paths, h, edges)
            _, co = E.fields(phys[h], w, edges)
            co_all[:, h * nb:(h + 1) * nb] = co.reshape(len(paths), nb, ncell) / E.MG_M3_PER_PPM
        hit = np.zeros((len(paths), T, ncell), bool)
        for k, (wmin, lim) in E.CO_PPM.items():
            hit |= np.nan_to_num(E.trailing_means(co_all, wmin), nan=-np.inf) >= lim
        for i, pth in enumerate(paths):
            if hit[i][:, road_idx].any():
                selected.append(int(pth))
                fm = np.where(hit[i].any(axis=0), np.argmax(hit[i], axis=0).astype(float), np.inf)
                co_first[int(pth)] = fm.reshape(ny, nx)
    print("paths where CO blocks a road cell:", len(selected), selected, flush=True)

    def receivers(x, y):
        col = np.clip(((x - grid.x0) // grid.res).astype(int), 0, nx - 1)
        row = np.clip(((grid.ytop - y) // grid.res).astype(int), 0, ny - 1)
        g = gradient[row, col]
        zz = (ground[row, col, 2] + p["receiver_height_m"] + g[:, 0] * (x - ground[row, col, 0])
              + g[:, 1] * (y - ground[row, col, 1]))
        return np.column_stack((x, y, zz)), row, col

    for pth in selected:
        W = np.concatenate([pw.weights(np.array([pth]), h, edges)[0] for h in range(6)])   # [360, sources]
        rad375 = max(float(E.fields(phys[h], W[h * nb:(h + 1) * nb][None], edges)[0].max()) for h in range(6)) / 1000.
        ever = [int(s) for s in np.flatnonzero(W.max(axis=0) > 0) if int(s) in front_of]
        fc = np.array([centre_of[s] for s in ever])
        px, py, pid = [], [], []
        for i, (_, u, v) in enumerate(pieces):
            L = float(np.hypot(*(v - u)))
            if np.min(np.hypot(*(fc - (u + v) / 2).T)) > RADIUS + L / 2 + 400:
                continue
            t = np.linspace(0., 1., max(2, int(np.ceil(L / STEP)) + 1))
            px.append(u[0] + t * (v[0] - u[0]))
            py.append(u[1] + t * (v[1] - u[1]))
            pid.append(np.full(len(t), i))
        px, py, pid = np.concatenate(px), np.concatenate(py), np.concatenate(pid)
        R, prow, pcol = receivers(px, py)
        flux = np.zeros((T, len(px)), np.float32)
        for s in ever:
            f = front_of[s]
            near = np.hypot(px - centre_of[s][0], py - centre_of[s][1]) <= RADIUS
            if not near.any():
                continue
            v = np.zeros(len(px))
            v[near] = tau * f.emissive_power_w_m2 * np.nan_to_num(f.view_factor(R[near], normal), nan=0.)
            flux += W[:, s][:, None].astype(np.float32) * v[None].astype(np.float32)
        rec = {}
        for aud, thr in THR.items():
            hit = flux >= thr
            fm = np.where(hit.any(axis=0), np.argmax(hit, axis=0).astype(float), np.inf)
            dist = np.full(len(px), np.nan)
            for j in np.flatnonzero(np.isfinite(fm)):
                m = int(fm[j])
                burning = [s for s in ever if W[m, s] > 0]
                dist[j] = min(seg_distance(np.array([px[j]]), np.array([py[j]]),
                                           np.asarray(front_of[s].base_start_xy_m, float),
                                           np.asarray(front_of[s].base_end_xy_m, float))[0] for s in burning)
            rec["point_first_min_" + aud] = fm
            rec["point_dist_at_first_m_" + aud] = dist
        # the path's own fire arrival (as safety_zone_export.py)
        fa = np.full(ncell, np.inf)
        f0 = first[pth].ravel()[src]
        on = np.where(f0 == 0, 0.0, np.floor(pw.onset[pth] / 60.0))
        fa[src] = np.where((f0 == 0) | pw.occurrence[pth], on, np.inf)
        fa = np.where(fa >= T, np.inf, fa).reshape(ny, nx)
        np.savez_compressed(out / ("path_%04d.npz" % pth), path=np.int64(pth), fire_arrival_min=fa,
                            co_first_min=co_first[pth], max_radiant_375m_kw_m2=rad375,
                            point_row=prow, point_col=pcol, point_piece=pid, point_xy=np.column_stack((px, py)),
                            point_max_kw_m2=(flux.max(axis=0) / 1000).astype(np.float32),
                            piece_ids=np.array([k for k, _, _ in pieces]), **rec)
        print("path %d: road points %d, largest road flux %.2f kW/m2, points >= 2.5: %d, >= 7.0: %d, 375 m max %.3f"
              % (pth, len(px), flux.max() / 1000, int(np.isfinite(rec["point_first_min_residents"]).sum()),
                 int(np.isfinite(rec["point_first_min_responders"]).sum()), rad375), flush=True)
    (out / "selection.json").write_text(json.dumps({"rule": "PROTOCOL.md Amendment 6 item 1", "n_paths": P,
                                                     "selected": selected}, indent=1))


if __name__ == "__main__":
    main()
