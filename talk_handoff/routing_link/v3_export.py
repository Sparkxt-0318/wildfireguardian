"""PROTOCOL_v3 Part A, Fish Creek: per-path flame contact, heat and gas at the roads. Run like perpath_export.py:

    cd WORKSPACE && PYTHONPATH=WORKSPACE python v3_export.py --grid GRID_JSON --osm OSM_JSON --fuel FUEL_DIR --out export_v3

FUEL_DIR is the data folder's Fish Creek fuel/ directory (read only). Writes export_v3/:
* crown.json, checks_v3.json
* per_path.npz   first blocking minute per path, criterion and road cell (+inf = never), lead distances of heat blocks
* counts.npz     paths in which each criterion holds, per minute and road cell (for the ensemble rule)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import perpath_export as E  # noqa: E402
import v3_physics as V  # noqa: E402

STEP, RADIUS, T, NB = 5.0, 1000.0, 360, 60
CRIT = ("contact", "wholecell", "h1_res", "h1_resp", "fed10", "fed30", "co", "acrolein", "hcn",
        "h1_res_s", "h1_resp_s", "fed10_s", "co_s", "acrolein_s", "hcn_s")


def setup():
    """The v1 inputs (export_fishcreek.py), also returning the duration estimate and its Rothermel inputs."""
    from wildfire import (CellBurningDuration, FlameResidenceTime, EnvironmentalCellDuration, LiveFuelMoisture,
                          HeatSmokeHazards, load_data, load_model)
    from wildfire.environmental_duration import DURATION_SOURCE_CHANNELS
    from wildfire.schema import TRAINING_SOURCE_CHANNELS, HAZARD_SOURCE_CHANNELS
    from demonstration.flame_danger.reference_inputs import load_reference_inputs

    reference = load_reference_inputs()
    parameters, archive, previous = reference.parameters, reference.archive, reference.selection
    model = load_model(device="cpu")
    channels = tuple(dict.fromkeys(TRAINING_SOURCE_CHANNELS + HAZARD_SOURCE_CHANNELS + DURATION_SOURCE_CHANNELS))
    with load_data(events=[previous["event"]], channels=channels, sequence_length=1, patch_size=None,
                   time_range=(previous["cutoff_utc"], previous["cutoff_utc"]), daily_policy="completed_day") as ds:
        sample = ds[0]
    for key in ("future_labels", "newly_burned_area", "future_burned_area", "next_burned_area"):
        sample.pop(key, None)
    rothermel_inputs = {}
    original = EnvironmentalCellDuration.estimate.__func__

    def capture(cls, environment, **kw):
        rothermel_inputs.update(kw, environment=environment)
        return original(cls, environment, **kw)

    EnvironmentalCellDuration.estimate = classmethod(capture)
    try:
        est = EnvironmentalCellDuration.from_sample(
            sample, live_moisture=LiveFuelMoisture.from_scott_burgan(previous["live_moisture_reference"]))
    finally:
        EnvironmentalCellDuration.estimate = classmethod(original)
    environment = est.environment
    residence, cell_duration = est.resolve(
        fallback_residence_time=FlameResidenceTime(archive["residence_duration_s"],
            {"source": "previously user-selected archived Fish Creek point-duration fallback for this example only"}),
        fallback_cell_burning_duration=CellBurningDuration(archive["cell_burning_duration_s"],
                                                           reference.cell_duration_provenance))
    front = np.where(est.resolved, (est.fields["spread_direction_deg_ccw_from_x"] + 90.) % 360.,
                     parameters.parameters_dict()["source_front_direction_deg_ccw_from_projected_x"])

    def factory(support, *, interval_start_s, interval_end_s):
        return HeatSmokeHazards(support, environment=environment, parameters=parameters,
                                fuel_load_kg_m2=reference.fuel_load_kg_m2, flame_height_m=reference.flame_height_m,
                                source_front_direction_deg_ccw_from_projected_x=front, unresolved_heat_policy="bounds")

    initial = model.predict_fire_activity_sample(
        sample, residence_time=residence, cell_burning_duration=cell_duration,
        initial_arrival_uncertainty=previous["initial_arrival_uncertainty"], boundary="zero",
        missing_burned_area="unburned")
    spread = model.predict_cumulative(sample, hours=list(range(1, 7)), n_samples=E.SAMPLES, seed=E.SEED,
                                      retain_trajectories=True, boundary="zero", missing_burned_area="unburned")
    return dict(initial=initial, spread=spread, factory=factory, est=est, residence=residence, front=front,
                environment=environment, parameters=parameters, reference=reference, rothermel=rothermel_inputs)


def fm10_spread_m_s(rin, cells):
    """Rothermel spread of fuel model 10 at the given cells, with the pipeline's own Behave call (section 4)."""
    import pyrothermel as backend
    from wildfire.environmental_duration import equilibrium_dead_fuel_moisture_percent
    env = rin["environment"]
    shape = env.shape

    def f(v):
        return np.broadcast_to(np.asarray(v, float), shape)
    rh, m100 = f(rin["relative_humidity_percent"]), f(rin["dead_fuel_moisture_100h_percent"])
    ch, cbh, cover = f(rin["canopy_height_m"]), f(rin["canopy_base_height_m"]), f(rin["canopy_cover_percent"])
    lm = rin["live_moisture"]
    herb, woody = f(lm.herbaceous_percent), f(lm.woody_percent)
    temp = env.ambient_temperature_k - 273.15
    fine = equilibrium_dead_fuel_moisture_percent(temp, rh)
    ratio = np.divide(ch - cbh, ch, out=np.zeros(shape), where=ch > 0.)
    speed = np.linalg.norm(env.wind_velocity_xy_m_s, axis=-1)
    east, north = np.moveaxis(env.wind_velocity_xy_m_s, -1, 0)
    from_bearing = (np.rad2deg(np.arctan2(east, north)) + 180.) % 360.
    aspect = np.where(env.slope_degrees == 0., 0., env.aspect_degrees)
    fuel = backend.FuelModel.from_existing(10)
    out = np.full(len(cells), np.nan)
    for j, (r, c) in enumerate(cells):
        i = (r, c)
        vals = [fine[i], m100[i], herb[i], woody[i], speed[i], from_bearing[i], ch[i], cover[i]]
        if not np.isfinite(vals).all():
            continue
        moisture = backend.MoistureScenario(fine[i] / 100., fine[i] / 100., m100[i] / 100., herb[i] / 100., woody[i] / 100.)
        run = backend.PyrothermelRun(fuel, moisture, speed[i] * 3.6, wind_input_mode="ten_meter",
                                     wind_direction=from_bearing[i], slope=env.slope_degrees[i], aspect=aspect[i],
                                     air_temperature=temp[i], canopy_height=ch[i], canopy_cover=cover[i] / 100.,
                                     canopy_ratio=ratio[i])
        out[j] = run.run_surface_fire_in_direction_of_max_spread()["spread_rate"] / 3.6
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--fuel", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--v2-co-paths", default=str(HERE / "export_v2" / "co_paths"))
    ap.add_argument("--limit-paths", type=int, default=0, help="smoke test only")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    import wildfire.physical_hazards as PH
    from wildfire import monte_carlo_hazards as mch
    from wildfire.hazard_parameters import CrownEmissionInputs
    from wildfire.canopy_inputs import CanopyStructure
    from wildfire.crown_fire import surface_fireline_intensity_kw_m, critical_crown_intensity_kw_m
    import osm_graph as G

    S = setup()
    fronts, real = [], PH.SolidFlameFront

    def recorder(*args, **kw):
        f = real(*args, **kw)
        fronts.append(f)
        return f

    cap = []
    orig = mch._window_exposure
    mch._window_exposure = lambda *x, **k: cap.append((x, k))
    PH.SolidFlameFront = recorder
    try:
        S["spread"].calculate_hazards(hours_later=list(range(6)), initial_activity=S["initial"],
                                      physical_factory=S["factory"], ignition_timing="uniform_within_step",
                                      timing_seed=E.SEED, time_step_s=60., batch_size=E.BATCH_PIPELINE,
                                      activity_mode="probability_map")
    finally:
        mch._window_exposure = orig
    ph = cap[0][0][6]
    support = cap[0][0][5]
    p = ph.parameters_dict()
    tau, normal = p["atmospheric_transmissivity"], p["receiver_normal"]
    src = ph.source_flat_indices
    ny, nx = ph.receiver_shape
    shape = (ny, nx)
    ground = ph.receiver_environment.ground_xyz_m.reshape(ny, nx, 3)
    gradient = np.asarray(ph.environment.terrain_gradient, float).reshape(ny, nx, 2)
    ambient_c = np.broadcast_to(np.asarray(ph.receiver_environment.ambient_temperature_k, float), shape) - 273.15
    n_surf = int(np.sum(np.asarray(ph.heat_release_w) > 0))
    surf_fronts = fronts[:n_surf]
    centres = np.array([(np.asarray(f.base_start_xy_m) + np.asarray(f.base_end_xy_m)) / 2 for f in surf_fronts])
    cell_xy = ground.reshape(-1, 3)[src, :2]
    which = np.array([int(np.argmin(np.hypot(*(cell_xy - c).T))) for c in centres])
    assert len(set(which.tolist())) == len(surf_fronts)
    surf_front_of = {int(s): surf_fronts[i] for i, s in enumerate(which)}
    grid = G.Grid.from_json(a.grid)
    rows, cols = np.divmod(src, nx)
    checks = {"protocol": "PROTOCOL_v3.md Part A"}

    # ---------- section 3: spread direction and rate per source cell ----------
    est = S["est"]
    duration = support.duration_s.ravel()[src]
    residence = np.broadcast_to(np.asarray(S["residence"].duration_s, float), shape).ravel()[src]
    sdir = np.deg2rad((np.asarray(S["front"], float) - 90.) % 360.).ravel()[src]
    dvec = np.column_stack((np.cos(sdir), np.sin(sdir)))
    corners = [V.cell_square(grid.x0, grid.ytop, grid.res, r, c) for r, c in zip(rows, cols)]
    entry = np.array([V.entry_offset_and_depth(cn, dv) for cn, dv in zip(corners, dvec)])
    s_entry, depth = entry[:, 0], entry[:, 1]
    traverse = np.maximum(duration - residence, 60.)
    checks["traverse_floor_60s_cells"] = int(np.sum(duration - residence < 60.))
    r_surf = depth / traverse
    hr = np.asarray(est.fields["horizontal_spread_rate_m_s"], float).ravel()[src]
    ok = np.isfinite(hr) & np.asarray(est.resolved).ravel()[src]
    checks["spread_rate_vs_pipeline_resolved_max_rel_diff"] = float(np.max(np.abs(r_surf[ok] - hr[ok]) / hr[ok])) if ok.any() else None
    checks["surface_spread_rate_m_s"] = {"min": float(r_surf.min()), "median": float(np.median(r_surf)), "max": float(r_surf.max())}

    # ---------- section 4: crown fire ----------
    canopy = CanopyStructure.from_unit_rasters(a.fuel, grid=support.activity.grid, shape=shape, epsg=5070)
    cbd = np.asarray(canopy.bulk_density_kg_m3, float)
    cbh = np.asarray(canopy.base_height_m, float)
    chh = np.asarray(canopy.height_m, float)
    cc = np.asarray(canopy.cover_percent, float)
    w_can = np.where(cc > 0, cbd * np.maximum(chh - cbh, 0.), 0.).ravel()[src]
    heat = np.asarray(S["parameters"].heat_for_grid(support.activity.grid, shape), float).ravel()[src]
    w_surf = (np.broadcast_to(np.asarray(S["reference"].fuel_load_kg_m2, float), shape).ravel()[src]
              * p["flaming_consumed_fraction"])
    i_surf = np.where(np.isfinite(heat), np.asarray(surface_fireline_intensity_kw_m(
        heat_of_combustion_j_kg=np.where(np.isfinite(heat), heat, 1.), flaming_consumed_fuel_kg_m2=w_surf,
        spread_rate_m_s=r_surf)), np.nan)
    i_crit = np.asarray(critical_crown_intensity_kw_m(canopy_base_height_m=cbh.ravel()[src],
                                                      foliar_moisture_percent=V.FOLIAR_MOISTURE_PERCENT))
    assert np.allclose(i_crit, V.van_wagner_critical_intensity_kw_m(cbh.ravel()[src]))
    init = (w_can > 0) & np.isfinite(i_surf) & (i_surf >= i_crit)
    r10 = np.full(len(src), np.nan)
    if init.any():
        r10[init] = fm10_spread_m_s(S["rothermel"], list(zip(rows[init], cols[init])))
    r_active = V.ROTHERMEL_CROWN_FACTOR * r10
    cbd_s = cbd.ravel()[src]
    sustained = init & np.isfinite(r_active) & (r_active >= V.VAN_WAGNER_MASS_FLOW / np.where(cbd_s > 0, cbd_s, np.inf))
    r_front = np.where(sustained, r_active, r_surf)
    crown = init & np.isfinite(r_front)
    i_tot = np.where(crown, np.nan_to_num(i_surf) * r_front / r_surf
                     + 1e-3 * V.FM10_HEAT_KJ_KG * 1e3 * w_can * r_front, 0.)
    l_crown = np.where(crown, V.thomas_flame_length_m(i_tot), 0.)
    crown_dur = np.where(crown, depth / r_front, 1.)
    crown_info = {"source_cells": int(len(src)), "canopy_cells_among_sources": int((w_can > 0).sum()),
                  "initiation_possible": int(init.sum()), "active_crown_sustained": int(sustained.sum()),
                  "passive_crown": int((init & ~sustained).sum()),
                  "crown_flame_length_m": ({"min": float(l_crown[crown].min()), "median": float(np.median(l_crown[crown])),
                                            "max": float(l_crown[crown].max())} if crown.any() else None),
                  "crown_fireline_intensity_kw_m": ({"min": float(i_tot[crown].min()), "max": float(i_tot[crown].max())}
                                                    if crown.any() else None),
                  "surface_intensity_kw_m": {"median": float(np.nanmedian(i_surf)), "max": float(np.nanmax(i_surf))},
                  "critical_intensity_kw_m": {"median": float(np.median(i_crit[w_can > 0])) if (w_can > 0).any() else None},
                  "thomas_check_38800_kw_m_m": float(V.thomas_flame_length_m(38800.)),
                  "front_rate_m_s_crown_cells": ({"min": float(r_front[crown].min()), "max": float(r_front[crown].max())}
                                                 if crown.any() else None)}
    (out / "crown.json").write_text(json.dumps(crown_info, indent=1))
    print("crown:", json.dumps(crown_info), flush=True)

    # the pipeline's own physical model for the crown phase (its kernels give crown CO and hot gas)
    def full(v, fill):
        m = np.full(ny * nx, fill, float)
        m[src] = v
        return m.reshape(shape)
    crown_ph = None
    if crown.any():
        fronts.clear()
        PH.SolidFlameFront = recorder
        try:
            crown_ph = PH.HeatSmokeHazards(
                support, environment=S["environment"], parameters=S["parameters"],
                fuel_load_kg_m2=S["reference"].fuel_load_kg_m2, flame_height_m=S["reference"].flame_height_m,
                crown_emissions=CrownEmissionInputs(
                    fuel_load_kg_m2=full(np.where(crown, w_can, 0.), 0.), consumed_fraction=1.0,
                    heat_of_combustion_j_kg=V.FM10_HEAT_KJ_KG * 1e3,
                    flame_height_m=full(np.where(crown, np.maximum(l_crown, 0.1), 1.0), 1.0),
                    flame_base_height_m=full(np.where(crown, cbh.ravel()[src], 0.), 0.),
                    radiative_fraction=p["radiative_fraction"], convective_fraction=p["convective_fraction"],
                    ember_fraction=0.0, pm25_emission_kg_per_kg_fuel=p["PM25_emission_kg_per_kg_fuel"],
                    co_emission_kg_per_kg_fuel=p["CO_emission_kg_per_kg_fuel"],
                    provenance={"protocol": "PROTOCOL_v3.md section 4", "canopy": "LANDFIRE 2016 CBD x (CH - CBH)",
                                "heat": "fuel model 10 heat content", "flame": "Thomas (1963) via Rothermel (1991)"}),
                crown_duration_s=full(crown_dur, 1.0),
                source_front_direction_deg_ccw_from_projected_x=S["front"], unresolved_heat_policy="bounds")
        finally:
            PH.SolidFlameFront = real
        crown_front_of = {}
        for f in fronts:
            c = (np.asarray(f.base_start_xy_m) + np.asarray(f.base_end_xy_m)) / 2
            crown_front_of[int(np.argmin(np.hypot(*(cell_xy - c).T)))] = f
        crown_E = np.array([crown_front_of[s].emissive_power_w_m2 if s in crown_front_of else 0. for s in range(len(src))])
    else:
        crown_E = np.zeros(len(src))

    # ---------- road points (5 m, terrain-plane receivers, Amendment 5) ----------
    graph, _, _, _ = G.build(a.osm, a.grid, "2024-08-23T00:00:00Z")
    xy = {nd["id"]: (nd["x"], nd["y"]) for nd in graph["nodes"]}
    road_mask = np.zeros(shape, bool)
    pieces, seen = [], set()
    for e in graph["edges"]:
        for s_ in e["segments"]:
            r_, c_ = grid.router_to_raster(s_["cell"])
            road_mask[r_, c_] = True
        k = tuple(sorted((e["id"], e.get("reverse_edge") or e["id"])))
        if k not in seen:
            seen.add(k)
            pieces.append((np.array(xy[e["u"]], float), np.array(xy[e["v"]], float)))
    rc_r, rc_c = np.nonzero(road_mask)
    road_index = -np.ones(shape, int)
    road_index[rc_r, rc_c] = np.arange(len(rc_r))
    n_road = len(rc_r)
    px, py = [], []
    for u, v in pieces:
        L = float(np.hypot(*(v - u)))
        mid = (u + v) / 2
        if np.min(np.hypot(*(cell_xy - mid).T)) > RADIUS + 300 + L / 2:
            continue
        t = np.linspace(0., 1., max(2, int(np.ceil(L / STEP)) + 1))
        px.append(u[0] + t * (v[0] - u[0]))
        py.append(u[1] + t * (v[1] - u[1]))
    px, py = np.concatenate(px), np.concatenate(py)
    pcol = np.clip(((px - grid.x0) // grid.res).astype(int), 0, nx - 1)
    prow = np.clip(((grid.ytop - py) // grid.res).astype(int), 0, ny - 1)
    keep = road_index[prow, pcol] >= 0
    px, py, prow, pcol = px[keep], py[keep], prow[keep], pcol[keep]
    g_ = gradient[prow, pcol]
    pz = (ground[prow, pcol, 2] + p["receiver_height_m"] + g_[:, 0] * (px - ground[prow, pcol, 0])
          + g_[:, 1] * (py - ground[prow, pcol, 1]))
    P3 = np.column_stack((px, py, pz))
    p_road = road_index[prow, pcol]
    n_pts = len(px)
    near = [np.flatnonzero(np.hypot(px - cell_xy[s, 0], py - cell_xy[s, 1]) <= RADIUS + 300) for s in range(len(src))]
    in_cell = [np.flatnonzero((prow == r) & (pcol == c)) for r, c in zip(rows, cols)]
    checks["road_points"] = int(n_pts)

    def plane_z(s, xy2):
        r, c = rows[s], cols[s]
        g = gradient[r, c]
        return ground[r, c, 2] + g[0] * (xy2[0] - ground[r, c, 0]) + g[1] * (xy2[1] - ground[r, c, 1])

    cache = {}

    def flux_at(s, k, phase):
        """Radiant flux (W/m2, unit weight) at the near points of source s, front k*STEP from its entry edge."""
        key = (s, k, phase)
        if key in cache:
            return cache[key]
        idx = near[s]
        if phase == "surf":
            ref, E_, base_h = surf_front_of.get(s), None, p["source_flame_base_height_m"]
            if ref is None:
                cache[key] = None
                return None
            E_, h = ref.emissive_power_w_m2, ref.flame_height_m
        else:
            E_, h, base_h = crown_E[s], max(l_crown[s], 0.1), cbh.ravel()[src][s]
            if E_ <= 0:
                cache[key] = None
                return None
        if k == "c":
            if phase == "surf":
                fr = ref
            else:
                fr = crown_front_of.get(s)
                if fr is None:
                    cache[key] = None
                    return None
        else:
            seg = V.chord(corners[s], dvec[s], s_entry[s] + min(k * STEP, depth[s] - 1e-6))
            if seg is None:
                cache[key] = None
                return None
            a_, b_ = seg
            fr = real(a_, b_, float(h), float(E_), base_elevation_m=float(plane_z(s, a_) + base_h),
                      base_end_elevation_m=float(plane_z(s, b_) + base_h))
        v = tau * E_ * np.nan_to_num(fr.view_factor(P3[idx], normal), nan=0.)
        cache[key] = v.astype(np.float32)
        return cache[key]

    # check: recorded surface fronts reproduce the pipeline's 375 m kernel; the rebuilt centre front matches the recorded one
    s0 = int(which[0])
    rec = ground.reshape(-1, 3).copy()
    rec[:, 2] += p["receiver_height_m"]
    f0 = surf_front_of[s0]
    checks["kernel_reproduction_max_abs_w_m2"] = float(np.max(np.abs(
        tau * f0.emissive_power_w_m2 * np.nan_to_num(f0.view_factor(rec, normal), nan=0.) - ph.radiant_kernel[s0])))
    diffs = []
    for s in list(surf_front_of)[:50]:
        fr = surf_front_of[s]
        seg = V.chord(corners[s], dvec[s], s_entry[s] + depth[s] / 2)
        a_, b_ = np.asarray(fr.base_start_xy_m), np.asarray(fr.base_end_xy_m)
        dd = min(np.hypot(*(seg[0] - a_)) + np.hypot(*(seg[1] - b_)), np.hypot(*(seg[0] - b_)) + np.hypot(*(seg[1] - a_)))
        zz = abs(plane_z(s, a_) + p["source_flame_base_height_m"] - fr.base_elevation_m)
        diffs.append((dd, zz))
    checks["rebuilt_centre_front_vs_pipeline"] = {"fronts": len(diffs), "endpoint_sum_max_m": float(max(d for d, _ in diffs)),
                                                  "base_elevation_max_abs_m": float(max(z for _, z in diffs))}

    # ---------- per path ----------
    pw = E.PathWeights(cap)
    Pn = a.limit_paths or pw.n
    edges = np.r_[np.arange(0., 3600., 60.), 3600.]
    first = np.asarray(S["spread"].trajectories.select()[0])
    rr_src = road_index.ravel()[src]            # road index of each source cell (-1 if none)
    road_flat = rc_r * nx + rc_c
    pos_road = {int(f): j for j, f in enumerate(road_flat)}
    src_pos = {int(f): j for j, f in enumerate(src)}
    K_co = ph.co_kernel[:, road_flat].astype(np.float64)
    K_t = ph.temperature_kernel[:, road_flat].astype(np.float64)
    if crown_ph is not None:
        Kc_co = crown_ph.co_kernel[:, road_flat].astype(np.float64)
        Kc_t = crown_ph.temperature_kernel[:, road_flat].astype(np.float64)
    amb = ambient_c[rc_r, rc_c]
    lim = {g: V.gas_limits_mg_m3(g) for g in ("co", "acrolein", "hcn")}
    first_min = np.full((Pn, len(CRIT), n_road), np.inf, np.float32)
    lead = np.full((Pn, 2, 3, n_road), np.nan, np.float32)   # [path, res/resp, (distance m, heat minute, contact minute), road]
    counts = np.zeros((len(CRIT), T, n_road), np.uint16)
    old_mask = pw.old
    mids = np.arange(T) * 60. + 30.
    starts, ends = np.arange(T) * 60., np.arange(T) * 60. + 60.
    for pth in range(Pn):
        W = np.concatenate([pw.weights(np.array([pth]), h, edges)[0] for h in range(6)])   # [360, sources]
        occ, on, ext = pw.occurrence[pth], pw.onset[pth], pw.extinction[pth]
        f0p = first[pth].ravel()[src]
        new = (f0p > 0) & occ
        # crown weights: front crossing time of new crown cells
        cw = np.zeros_like(W)
        if crown.any():
            cs = np.flatnonzero(crown & new)
            c_on, c_off = on[cs], on[cs] + crown_dur[cs]
            cw[:, cs] = np.clip(np.minimum(ends[:, None], c_off[None]) - np.maximum(starts[:, None], c_on[None]), 0., 60.) / 60.
        # radiant at road points, surface and crown
        q_s = np.zeros((T, n_pts), np.float32)
        q_c = np.zeros((T, n_pts), np.float32)
        active = np.flatnonzero(W.max(axis=0) > 0)
        for s in active:
            mins = np.flatnonzero(W[:, s] > 0)
            if old_mask[s] and f0p[s] == 0:
                groups = {"c": mins}
            else:
                pos = np.clip((mids[mins] - on[s]) * (r_front[s] if crown[s] else r_surf[s]), 0., depth[s])
                ks = np.minimum(np.round(pos / STEP).astype(int), int(depth[s] // STEP))
                groups = {int(k): mins[ks == k] for k in np.unique(ks)}
            for k, rows_m in groups.items():
                v = flux_at(s, k, "surf")
                if v is not None:
                    q_s[np.ix_(rows_m, near[s])] += W[rows_m, s][:, None].astype(np.float32) * v[None]
        for s in np.flatnonzero(cw.max(axis=0) > 0):
            mins = np.flatnonzero(cw[:, s] > 0)
            pos = np.clip((mids[mins] - on[s]) * r_front[s], 0., depth[s])
            ks = np.minimum(np.round(pos / STEP).astype(int), int(depth[s] // STEP))
            for k in np.unique(ks):
                rows_m = mins[ks == k]
                v = flux_at(s, int(k), "crown")
                if v is not None:
                    q_c[np.ix_(rows_m, near[s])] += cw[rows_m, s][:, None].astype(np.float32) * v[None]
        q_all, q_srf = (q_s + q_c) / 1000., q_s / 1000.
        # hot gas and gases at road cells
        tinc_s = W @ K_t
        co_s = W @ K_co
        if crown_ph is not None:
            tinc_all, co_all = tinc_s + cw @ Kc_t, co_s + cw @ Kc_co
        else:
            tinc_all, co_all = tinc_s, co_s
        # flame contact at road points; v2-style whole-cell arrival
        contact_pt = np.full(n_pts, np.inf)
        wholecell = np.full(n_road, np.inf)
        for s in np.flatnonzero((f0p == 0) | new):
            j = rr_src[s]
            if f0p[s] == 0:
                t_cell = 0.
                tc = np.zeros(len(in_cell[s]))
            else:
                t_cell = np.floor(on[s] / 60.)
                tc = np.floor(V.contact_time_s(np.column_stack((px[in_cell[s]], py[in_cell[s]])), on[s], dvec[s],
                                               s_entry[s], r_front[s] if crown[s] else r_surf[s]) / 60.)
            if j >= 0 and t_cell < T:
                wholecell[j] = min(wholecell[j], t_cell)
            if len(in_cell[s]):
                contact_pt[in_cell[s]] = np.minimum(contact_pt[in_cell[s]], tc)
        contact_pt = np.where(contact_pt >= T, np.inf, contact_pt)
        fm = {}
        holds = {}
        contact_road = np.full(n_road, np.inf)
        np.minimum.at(contact_road, p_road, contact_pt)
        fm["contact"], fm["wholecell"] = contact_road, wholecell
        holds["contact"] = np.arange(T)[:, None] >= contact_road[None]
        holds["wholecell"] = np.arange(T)[:, None] >= wholecell[None]
        for tag, q, tinc, co in (("", q_all, tinc_all, co_all), ("_s", q_srf, tinc_s, co_s)):
            gas_c = (amb[None] + tinc)[:, p_road]
            for aud, thr in V.RADIANT_THR_KW.items():
                name = ("h1_res" if aud == "residents" else "h1_resp") + tag
                hit = q >= thr
                hr_ = np.zeros((T, n_road), bool)
                for m in np.flatnonzero(hit.any(axis=1)):
                    hr_[m, np.unique(p_road[hit[m]])] = True
                holds[name] = hr_
                fm[name] = V.first_true(hr_)
                if tag == "":
                    fpt = V.first_true(hit)
                    i_aud = 0 if aud == "residents" else 1
                    for j in np.flatnonzero(np.isfinite(fm[name])):
                        m = int(fm[name][j])
                        cand = np.flatnonzero((p_road == j) & hit[m])
                        burning = [s for s in active if W[m, s] > 0] + [s for s in np.flatnonzero(cw[m] > 0)]
                        best = np.inf
                        for s in burning:
                            pos = (np.clip((mids[m] - on[s]) * (r_front[s] if crown[s] else r_surf[s]), 0., depth[s])
                                   if not (old_mask[s] and f0p[s] == 0) else depth[s] / 2)
                            seg = V.chord(corners[s], dvec[s], s_entry[s] + min(pos, depth[s] - 1e-6))
                            if seg is None:
                                continue
                            best = min(best, float(np.min(V.seg_distance(px[cand], py[cand], seg[0], seg[1]))))
                        lead[pth, i_aud, 0, j] = best
                        lead[pth, i_aud, 1, j] = m
                        lead[pth, i_aud, 2, j] = float(np.min(contact_pt[cand]))
            rate = V.fed_rate_per_min(q, gas_c)
            for w, name in ((10, "fed10"), (30, "fed30")):
                if tag == "_s" and w == 30:
                    continue
                win = np.nan_to_num(V.trailing_sum(rate, w), nan=-np.inf) >= V.FED_LIMIT
                hr_ = np.zeros((T, n_road), bool)
                for m in np.flatnonzero(win.any(axis=1)):
                    hr_[m, np.unique(p_road[win[m]])] = True
                holds[name + tag] = hr_
                fm[name + tag] = V.first_true(hr_)
            for gas in ("co", "acrolein", "hcn"):
                conc = V.gas_from_co(co, gas)
                hit = np.zeros((T, n_road), bool)
                for w, L in zip(V.WINDOWS_MIN, lim[gas]):
                    hit |= np.nan_to_num(V.trailing_sum(conc, w) / w, nan=-np.inf) >= L
                holds[gas + tag] = hit
                fm[gas + tag] = V.first_true(hit)
        for i, c in enumerate(CRIT):
            first_min[pth, i] = fm[c]
            counts[i] += holds[c].astype(np.uint16)
        if pth % 64 == 63 or pth == Pn - 1:
            print("  path %d/%d  %.0f s  cache %d" % (pth + 1, Pn, time.monotonic() - t0, len(cache)), flush=True)

    # ---------- check 1: regression to v2 (Amendment 6 paths): whole-cell arrival and CO (v2 ppm rule) ----------
    reg = {"paths_compared": 0, "wholecell_equal": 0, "co_v2_rule_equal": 0}
    v2dir = Path(a.v2_co_paths)
    if v2dir.exists():
        for f in sorted(v2dir.glob("path_*.npz")):
            z = np.load(f)
            pth = int(z["path"])
            if pth >= Pn:
                continue
            reg["paths_compared"] += 1
            wc = np.asarray(z["fire_arrival_min"], float)[rc_r, rc_c]
            reg["wholecell_equal"] += int(np.array_equal(np.where(np.isfinite(wc), wc, np.inf),
                                                         first_min[pth, CRIT.index("wholecell")].astype(float)))
            W = np.concatenate([pw.weights(np.array([pth]), h, edges)[0] for h in range(6)])
            ppm = (W @ K_co) / E.MG_M3_PER_PPM
            hit = np.zeros((T, n_road), bool)
            for k_, (wmin, limp) in E.CO_PPM.items():
                hit |= np.nan_to_num(V.trailing_sum(ppm, wmin) / wmin, nan=-np.inf) >= limp
            v2co = np.asarray(z["co_first_min"], float)[rc_r, rc_c]
            reg["co_v2_rule_equal"] += int(np.array_equal(V.first_true(hit), np.where(np.isfinite(v2co), v2co, np.inf)))
    checks["regression_to_v2"] = reg
    # check 3: gas scaling and the thermal-dose law as the pipeline writes it
    law = "integral dt_min * (1[q_rad>=2.5] q_rad_kW_m2**1.9/4.2 + max(T_C,0)**3.61/4.1e8)"
    from wildfire.danger_criteria import PublishedDangerCriteria
    checks["fed_law_matches_pipeline_metadata"] = PublishedDangerCriteria().metadata_dict()["thermal_law"] == law
    qs, ts = np.array([0., 2.4, 2.5, 7., 20.]), np.array([20., 50., 100., 150., 300.])
    checks["fed_rate_examples_per_min"] = V.fed_rate_per_min(qs, ts).tolist()
    checks["gas_scaling"] = {g: float(V.gas_from_co(1.0, g)) for g in ("acrolein", "hcn")}
    checks["gas_limits_mg_m3"] = {g: list(lim[g]) for g in lim}
    checks["n_paths"] = Pn
    checks["n_road_cells"] = n_road
    checks["elapsed_s"] = time.monotonic() - t0
    np.savez_compressed(out / "per_path.npz", criteria=np.array(CRIT), first_min=first_min, lead=lead,
                        road_row=rc_r, road_col=rc_c)
    np.savez_compressed(out / "counts.npz", criteria=np.array(CRIT), counts=counts, n_paths=np.int64(Pn),
                        road_row=rc_r, road_col=rc_c)
    (out / "checks_v3.json").write_text(json.dumps(checks, indent=1))
    print(json.dumps(checks, indent=1))


if __name__ == "__main__":
    main()
