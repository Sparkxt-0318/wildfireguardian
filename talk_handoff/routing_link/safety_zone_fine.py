"""The Amendment 3 path and minute with receivers at 5 m (PROTOCOL.md Amendment 4). Run like perpath_export.py:

    cd WORKSPACE && PYTHONPATH=WORKSPACE python safety_zone_fine.py --grid GRID_JSON --osm OSM_JSON --out export_v2

The pipeline's own flame-front objects are recorded as its physical model builds them (SolidFlameFront, unchanged),
then evaluated at more receivers: flux = transmissivity x emissive power x view factor, summed over the fronts burning
in that path with the Amendment 2 weights. Receivers: 1.7 m above the ground of the containing 375 m cell.
Writes export_v2/safety_zone_fine.npz.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import perpath_export as E  # noqa: E402

STEP = 5.0
RADIUS = 1000.0
THR = {"residents": 2500.0, "responders": 7000.0}


def seg_distance(px, py, a, b):
    """Horizontal distance from points to segment a-b."""
    d = b - a
    t = np.clip(((px - a[0]) * d[0] + (py - a[1]) * d[1]) / (d @ d), 0., 1.)
    return np.hypot(px - (a[0] + t * d[0]), py - (a[1] + t * d[1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--terrain-plane", action="store_true",
                    help="Amendment 5: receiver height on the cell's terrain plane instead of one height per cell")
    a = ap.parse_args()
    import wildfire.physical_hazards as PH
    from wildfire import monte_carlo_hazards as mch

    fronts = []
    real = PH.SolidFlameFront

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
    ph = cap[0][0][6]
    p = ph.parameters_dict()
    tau = p["atmospheric_transmissivity"]
    normal = p["receiver_normal"]
    src = ph.source_flat_indices
    ny, nx = ph.receiver_shape
    ground = ph.receiver_environment.ground_xyz_m.reshape(ny, nx, 3)
    # fronts are built once per hour (six identical physical models); map the first set to sources by centre
    n_per = int(np.sum(np.asarray(ph.heat_release_w) > 0))
    fr = fronts[:n_per]
    centres = np.array([(np.asarray(f.base_start_xy_m) + np.asarray(f.base_end_xy_m)) / 2 for f in fr])
    cell_xy = ground.reshape(-1, 3)[src, :2]
    which = np.array([int(np.argmin(np.hypot(*(cell_xy - c).T))) for c in centres])
    assert len(set(which.tolist())) == len(fr), "front-to-source mapping is not one to one"
    match = float(np.max(np.hypot(*(cell_xy[which] - centres).T)))
    front_of = {int(s): fr[i] for i, s in enumerate(which)}
    # the recorded fronts reproduce the pipeline's 375 m kernel
    s0 = int(which[0])
    rec = ground.reshape(-1, 3).copy()
    rec[:, 2] += p["receiver_height_m"]
    vf = np.nan_to_num(front_of[s0].view_factor(rec, normal), nan=0.)
    kernel_diff = float(np.max(np.abs(tau * front_of[s0].emissive_power_w_m2 * vf - ph.radiant_kernel[s0])))

    z = np.load(Path(a.out) / "safety_zone_path.npz")
    path, minute = int(z["path"]), int(z["minute"])
    pw = E.PathWeights(cap)
    edges = np.r_[np.arange(0., 3600., 60.), 3600.]
    W = np.concatenate([pw.weights(np.array([path]), h, edges)[0] for h in range(6)])   # [360, sources]
    ever = np.flatnonzero(W.max(axis=0) > 0)
    ever = [int(s) for s in ever if s in front_of]

    import osm_graph as G
    grid = G.Grid.from_json(a.grid)
    graph, origins, exits, meta = G.build(a.osm, a.grid, "2024-08-23T00:00:00Z")
    xy = {nd["id"]: (nd["x"], nd["y"]) for nd in graph["nodes"]}
    pieces, seen = [], set()
    for e in graph["edges"]:
        k = tuple(sorted((e["id"], e.get("reverse_edge") or e["id"])))
        if k in seen:
            continue
        seen.add(k)
        pieces.append((k[0], np.array(xy[e["u"]], float), np.array(xy[e["v"]], float)))
    # 5 m points on road pieces near any front that burns in this path
    fc = np.array([centres[list(which).index(s)] for s in ever])
    px, py, pid = [], [], []
    for i, (_, u, v) in enumerate(pieces):
        L = float(np.hypot(*(v - u)))
        mid = (u + v) / 2
        if np.min(np.hypot(*(fc - mid).T)) > RADIUS + L / 2 + 400:
            continue
        t = np.linspace(0., 1., max(2, int(np.ceil(L / STEP)) + 1))
        px.append(u[0] + t * (v[0] - u[0]))
        py.append(u[1] + t * (v[1] - u[1]))
        pid.append(np.full(len(t), i))
    px, py, pid = np.concatenate(px), np.concatenate(py), np.concatenate(pid)

    gradient = np.asarray(ph.environment.terrain_gradient, float).reshape(ny, nx, 2)

    def receivers(x, y):
        col = np.clip(((x - grid.x0) // grid.res).astype(int), 0, nx - 1)
        row = np.clip(((grid.ytop - y) // grid.res).astype(int), 0, ny - 1)
        zz = ground[row, col, 2] + p["receiver_height_m"]
        if a.terrain_plane:
            g = gradient[row, col]
            zz = zz + g[:, 0] * (x - ground[row, col, 0]) + g[:, 1] * (y - ground[row, col, 1])
        return np.column_stack((x, y, zz)), row, col

    R, prow, pcol = receivers(px, py)
    flux_src = {}
    for s in ever:
        f = front_of[s]
        c = (np.asarray(f.base_start_xy_m) + np.asarray(f.base_end_xy_m)) / 2
        near = np.hypot(px - c[0], py - c[1]) <= RADIUS
        v = np.zeros(len(px))
        v[near] = tau * f.emissive_power_w_m2 * np.nan_to_num(f.view_factor(R[near], normal), nan=0.)
        flux_src[s] = v
    road_flux = np.zeros((W.shape[0], len(px)), np.float32)
    for s in ever:
        road_flux += W[:, s][:, None].astype(np.float32) * flux_src[s][None].astype(np.float32)
    first = {}
    for aud, thr in THR.items():
        hit = road_flux >= thr
        first[aud] = np.where(hit.any(axis=0), np.argmax(hit, axis=0).astype(float), np.inf)

    # 5 m raster around the fronts burning at the chosen minute
    burn_now = [s for s in ever if W[minute, s] > 0]
    bc = np.array([centres[list(which).index(s)] for s in burn_now])
    x0, x1 = bc[:, 0].min() - 600, bc[:, 0].max() + 600
    y0, y1 = bc[:, 1].min() - 600, bc[:, 1].max() + 600
    gx = np.arange(x0, x1, STEP) + STEP / 2
    gy = np.arange(y1, y0, -STEP) - STEP / 2
    XX, YY = np.meshgrid(gx, gy)
    Rg, _, _ = receivers(XX.ravel(), YY.ravel())
    zone = np.zeros(len(Rg))
    dist = np.full(len(Rg), np.inf)
    for s in burn_now:
        f = front_of[s]
        zone += W[minute, s] * tau * f.emissive_power_w_m2 * np.nan_to_num(f.view_factor(Rg, normal), nan=0.)
        dist = np.minimum(dist, seg_distance(Rg[:, 0], Rg[:, 1], np.asarray(f.base_start_xy_m, float),
                                             np.asarray(f.base_end_xy_m, float)))
    zone = zone.reshape(XX.shape)
    dist = dist.reshape(XX.shape)
    now = road_flux[minute]
    np.savez_compressed(
        Path(a.out) / ("safety_zone_fine_plane.npz" if a.terrain_plane else "safety_zone_fine.npz"),
        receiver_height_rule=np.array("terrain plane of the cell (Amendment 5)" if a.terrain_plane
                                      else "one height per cell (Amendment 4)"), path=np.int64(path), minute=np.int64(minute), step_m=STEP,
        front_source_match_m=match, kernel_reproduction_max_abs_w_m2=kernel_diff,
        raster_flux_kw_m2=(zone / 1000).astype(np.float32), raster_extent=np.array([x0, x1, y0, y1]),
        raster_dist_to_front_m=dist.astype(np.float32),
        fronts_now=np.array([[*np.asarray(front_of[s].base_start_xy_m), *np.asarray(front_of[s].base_end_xy_m),
                              front_of[s].flame_height_m, front_of[s].emissive_power_w_m2, W[minute, s],
                              front_of[s].base_elevation_m, float(front_of[s].vertices_m[1, 2]),
                              float(ground.reshape(-1, 3)[src[s], 2])]
                             for s in burn_now]),
        fronts_now_columns=np.array(["x0", "y0", "x1", "y1", "flame_height_m", "emissive_w_m2", "weight",
                                     "base_start_elev_m", "base_end_elev_m", "cell_ground_m"]),
        piece_ids=np.array([k for k, _, _ in pieces]), point_piece=pid, point_xy=np.column_stack((px, py)),
        point_row=prow, point_col=pcol, point_flux_now_kw_m2=(now / 1000).astype(np.float32),
        point_first_min_residents=first["residents"], point_first_min_responders=first["responders"],
        point_max_flux_6h_kw_m2=(road_flux.max(axis=0) / 1000).astype(np.float32))
    for aud, thr in THR.items():
        m = zone >= thr
        print(aud, "zone 5 m cells", int(m.sum()), "largest distance from a front line (m)",
              float(dist[m].max()) if m.any() else None, "road points now", int(np.sum(now >= thr)),
              "road points ever", int(np.isfinite(first[aud]).sum()))
    print("fronts burning now", len(burn_now), "largest flux now kW/m2", float(zone.max() / 1000),
          "kernel reproduction", kernel_diff, "match m", match)


if __name__ == "__main__":
    main()
