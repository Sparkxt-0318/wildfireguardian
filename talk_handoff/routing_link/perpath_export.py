"""Per-path radiant heat and CO for Fish Creek, hours 0-5 (PROTOCOL.md Amendment 2). Run like export_fishcreek.py:

    cd WORKSPACE && PYTHONPATH=WORKSPACE python perpath_export.py --out EXPORT_V2_DIR [--v1 export_6h] [--paths 1024]

The forecast, inputs and physical factory are the v1 ones (export_fishcreek.py, unchanged). The pipeline's own
calculate_hazards is run once as in v1, and its per-hour support and physical model are taken from inside it, so the
source identities, kernels, initial activity and timing draws are the pipeline's. For each retained path, a source's
weight in a 60 s bin is the fraction of the bin during which it burns in that path (Amendment 2 item 1).

Writes:
* counts.npz       paths in which each criterion holds, per minute and cell: radiant_2p5, radiant_7p0, co_10, co_30,
                   co_60 [360, ny, nx] uint16; n_paths
* peaks.npz        per path, hour and cell, the largest 60 s radiant flux (kW/m2) and largest 10/30/60 min CO mean (ppm),
                   summarised over paths: max, q50, q90 [6, ny, nx]
* distances.npz    for every cell blocked by radiant or CO at each share level: its first blocked minute and, over the
                   paths in which the criterion holds then, the distance to the nearest burning cell (median, min, max)
* checks_v2.json   Amendment 2 item 6 (a)-(c)
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

SEED = 20261122
SAMPLES = 1024
BATCH_PIPELINE = 8          # the v1 batch size; the timing draws are taken in the same order
MG_M3_PER_PPM = 1.145
RAD_W_M2 = {"radiant_2p5": 2500.0, "radiant_7p0": 7000.0}
CO_PPM = {"co_10": (10, 420.0), "co_30": (30, 150.0), "co_60": (60, 83.0)}
CRITERIA = tuple(RAD_W_M2) + tuple(CO_PPM)
LEVELS = {"any": None, "p10": 0.1, "p50": 0.5, "p90": 0.9}


def setup(hours):
    """The v1 inputs, unchanged (export_fishcreek.py lines 49-78)."""
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
        assert len(ds) == 1
        sample = ds[0]
    for key in ("future_labels", "newly_burned_area", "future_burned_area", "next_burned_area"):
        sample.pop(key, None)
    est = EnvironmentalCellDuration.from_sample(
        sample, live_moisture=LiveFuelMoisture.from_scott_burgan(previous["live_moisture_reference"]))
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
    spread = model.predict_cumulative(sample, hours=list(range(1, hours + 1)), n_samples=SAMPLES, seed=SEED,
                                      retain_trajectories=True, boundary="zero", missing_burned_area="unburned")
    return initial, spread, factory


class PathWeights:
    """Each path's fractional 60 s source weights, from the pipeline's own timing draws for that path."""

    def __init__(self, cap):
        self.cap = cap                                   # one (args, kwargs) of _window_exposure per hour
        (_, first, steps, earlier, later, support, physical), kw = cap[0]
        self.steps, self.earlier = steps, earlier
        self.support = support
        self.source = support.source_flat_indices
        self.duration = support.duration_s.ravel()[self.source]
        self.p0 = support.activity.initial_active_probability.ravel()[self.source]
        self.remaining = support.activity.initial_remaining_duration_s.ravel()[self.source]
        self.old = self.p0 > 0.
        assert kw["ignition_timing"] == "uniform_within_step" and kw["timing_seed"] == SEED
        n, cells = len(first), int(np.prod(first.shape[-2:]))
        # the pipeline recreates both streams for each window, so every hour sees the same draws for a path
        timing_rng, initial_rng = (np.random.default_rng(c) for c in
                                   np.random.SeedSequence([SEED, 0x4D434841]).spawn(2))
        arr, ini, ext = [], [], []
        for b in range(0, n, BATCH_PIPELINE):
            size = min(BATCH_PIPELINE, n - b)
            au = timing_rng.random((size, cells))[:, self.source]
            iu = initial_rng.random((size, cells))[:, self.source]
            arr.append(au)
            ini.append(iu)
            if support.initial_arrival_model is not None:
                ext.append(support.initial_arrival_model.sample_remaining(au, support.duration_s, self.source))
        arrival_uniform, initial_uniform = np.concatenate(arr), np.concatenate(ini)
        self.occurrence = steps > 0
        self.occurrence[:, self.old] = initial_uniform[:, self.old] < self.p0[self.old]
        self.onset = earlier + 3600. * arrival_uniform
        self.onset[:, self.old] = 0.
        self.extinction = self.onset + self.duration
        self.extinction[:, self.old] = self.remaining[self.old]
        if ext:
            self.extinction[:, self.old] = np.concatenate(ext)[:, self.old]
        self.n = n

    def weights(self, paths, hour, edges):
        """[len(paths), bins, sources] fraction of each bin during which the source burns in that path."""
        b0 = hour * 3600. + edges[:-1][None, :, None]
        b1 = hour * 3600. + edges[1:][None, :, None]
        on, off = self.onset[paths][:, None, :], self.extinction[paths][:, None, :]
        overlap = np.clip(np.minimum(off, b1) - np.maximum(on, b0), 0., None) / (b1 - b0)
        return np.where(self.occurrence[paths][:, None, :], np.clip(overlap, 0., 1.), 0.)


def fields(physical, w, edges):
    from wildfire.hazards import HazardTimeline
    tl = HazardTimeline(physical.receiver_grid, physical.receiver_shape, edges, np.full(len(w), 1. / len(w)),
                        {"source": "per-path fractional activity (routing_link Amendment 2)"})
    f = physical.fields_from_activity(w, tl, quantities=("radiant", "co"))
    rad, co = f.lower_bounds["radiant"], f.lower_bounds["co"]
    if np.isnan(f["radiant"]).any() or np.isnan(f["co"]).any():
        raise RuntimeError("unresolved radiant or CO input in a path: Amendment 1 item 4 would apply; not expected")
    return rad, co


def trailing_means(co_ppm, w):
    """[P, T, cells] -> mean over the w bins ending at each bin (NaN where the window starts before the cutoff)."""
    c = np.cumsum(co_ppm, axis=1, dtype=np.float64)
    out = np.full(co_ppm.shape, np.nan)
    out[:, w - 1] = c[:, w - 1] / w
    out[:, w:] = (c[:, w:] - c[:, :-w]) / w
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--v1", required=True, help="the v1 export folder (export_6h)")
    ap.add_argument("--hours", type=int, default=6)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--limit-paths", type=int, default=0, help="smoke test only: first N paths (never for results)")
    a = ap.parse_args()
    out, v1 = Path(a.out), Path(a.v1)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    from wildfire import monte_carlo_hazards as mch
    from wildfire.exposure_calculations import weighted_exposure_integrals

    print("setup (v1 inputs and spread)", flush=True)
    initial, spread, factory = setup(a.hours)
    cap = []
    original = mch._window_exposure

    def capture(*args, **kw):
        cap.append((args, kw))
        return original(*args, **kw)

    mch._window_exposure = capture
    try:
        multi = spread.calculate_hazards(hours_later=list(range(a.hours)), initial_activity=initial,
                                         physical_factory=factory, ignition_timing="uniform_within_step",
                                         timing_seed=SEED, time_step_s=60., batch_size=BATCH_PIPELINE,
                                         activity_mode="probability_map")
    finally:
        mch._window_exposure = original
    H = a.hours
    edges = np.r_[np.arange(0., 3600., 60.), 3600.]
    nb = len(edges) - 1
    T = H * nb
    phys = [c[0][6] for c in cap]
    shape = phys[0].receiver_shape
    ncell = int(np.prod(shape))
    checks = {"n_paths": None, "seed": SEED, "rule": "PROTOCOL.md Amendment 2"}

    # (c) the run reproduces v1: pipeline fields equal, retained paths give the same fire-arrival rasters
    with np.load(v1 / "pipeline_fields.npz") as z:
        mine = multi.numpy()
        same = {k: bool(np.array_equal(np.asarray(mine[k]), z[k], equal_nan=True)) for k in z.files
                if k != "metadata_json" and k in mine}
        checks["c_pipeline_fields_equal_v1"] = {"arrays": len(same), "equal": sum(same.values()),
                                                "unequal": [k for k, v in same.items() if not v]}
    first = np.asarray(spread.trajectories.select()[0])
    burned0 = first[0] == 0
    reached = (first > 0) & (first <= H)
    kmin = np.where(reached.any(axis=0), np.where(reached, first, 10 ** 6).min(axis=0), 0)
    earliest = np.where(burned0, 0.0, np.where(reached.any(axis=0), 60.0 * (kmin - 1), np.inf))
    half = np.full(first.shape[1:], np.inf)
    for k in range(H, 0, -1):
        half = np.where(((first > 0) & (first <= k)).mean(axis=0) >= 0.5, 60.0 * (k - 1), half)
    half = np.where(burned0, 0.0, half)
    import rasterio
    fa = {}
    for name, arr in (("earliest", earliest), ("half", half)):
        with rasterio.open(v1 / ("fire_arrival_%s.tif" % name)) as r:
            old = r.read(1).astype(float)
        fa[name] = bool(np.array_equal(old, arr.astype(np.float32).astype(float), equal_nan=True))
    checks["c_fire_arrival_equal_v1"] = fa

    pw = PathWeights(cap)
    P = a.limit_paths or pw.n
    checks["n_paths"] = P
    src = pw.source
    ny, nx = shape
    rr, cc = np.divmod(src, nx)

    counts = {k: np.zeros((T, ncell), np.uint16) for k in CRITERIA}
    peak = {k: np.zeros((P, H, ncell), np.float32) for k in ("radiant_kw_m2", "co10_ppm", "co30_ppm", "co60_ppm")}
    # (b) running sums for the mean over paths
    s_w, q_w = np.zeros((H, nb, len(src))), np.zeros((H, nb, len(src)))
    tot = {"radiant": np.zeros((P, H)), "co": np.zeros((P, H))}   # per path, sum over cells and bins
    s_rad, q_rad = np.zeros((H, nb, ncell)), np.zeros((H, nb, ncell))
    s_co, q_co = np.zeros((H, nb, ncell)), np.zeros((H, nb, ncell))
    check_path = int(np.argmax(pw.occurrence[:P].sum(axis=1)))
    checks["a_one_path"] = {"path": check_path}
    print("per-path fields, %d paths, batch %d" % (P, a.batch), flush=True)
    for b0 in range(0, P, a.batch):
        paths = np.arange(b0, min(P, b0 + a.batch))
        rad_all = np.empty((len(paths), T, ncell), np.float32)
        co_all = np.empty((len(paths), T, ncell), np.float64)
        for h in range(H):
            w = pw.weights(paths, h, edges)
            rad, co = fields(phys[h], w, edges)
            rad = rad.reshape(len(paths), nb, ncell)
            co = co.reshape(len(paths), nb, ncell)
            rad_all[:, h * nb:(h + 1) * nb] = rad
            co_all[:, h * nb:(h + 1) * nb] = co / MG_M3_PER_PPM
            s_w[h] += w.sum(axis=0)
            q_w[h] += (w ** 2).sum(axis=0)
            tot["radiant"][paths, h] = rad.sum(axis=(1, 2))
            tot["co"][paths, h] = co.sum(axis=(1, 2))
            s_rad[h] += rad.sum(axis=0)
            q_rad[h] += (rad ** 2).sum(axis=0)
            s_co[h] += co.sum(axis=0)
            q_co[h] += (co ** 2).sum(axis=0)
            if check_path in paths:
                i = int(np.flatnonzero(paths == check_path)[0])
                integ, unres = weighted_exposure_integrals(phys[h], w[i], edges)
                dt = np.diff(edges)[:, None, None]
                checks["a_one_path"]["hour_%d" % h] = {
                    "radiant_integral_max_abs_diff_j_m2": float(np.max(np.abs(
                        np.sum(rad[i].reshape(nb, ny, nx) * dt, axis=0) - integ["radiant"]))),
                    "radiant_integral_max_j_m2": float(np.max(integ["radiant"])),
                    "co_integral_max_abs_diff": float(np.max(np.abs(
                        np.sum(co[i].reshape(nb, ny, nx) * dt, axis=0) - integ["co"]))),
                    "co_integral_max": float(np.max(integ["co"]))}
                from wildfire.hazards import HazardTimeline
                tl = HazardTimeline(phys[h].receiver_grid, shape, edges, [1.], {"source": "check"})
                f1 = phys[h].fields_from_activity(w[i][None], tl, quantities=("radiant", "co"))
                checks["a_one_path"]["hour_%d" % h]["binwise_equal"] = bool(
                    np.array_equal(f1.lower_bounds["radiant"][0].reshape(nb, ncell), rad[i])
                    and np.array_equal(f1.lower_bounds["co"][0].reshape(nb, ncell), co[i]))
            for i, p in enumerate(paths):
                peak["radiant_kw_m2"][p, h] = rad[i].max(axis=0) / 1000.
        for k, thr in RAD_W_M2.items():
            counts[k] += (rad_all >= thr).sum(axis=0).astype(np.uint16)
        for k, (wmin, lim) in CO_PPM.items():
            m = trailing_means(co_all, wmin)
            counts[k] += (np.nan_to_num(m, nan=-np.inf) >= lim).sum(axis=0).astype(np.uint16)
            pk = np.nan_to_num(m, nan=-np.inf).reshape(len(paths), H, nb, ncell).max(axis=2)
            peak["co%d_ppm" % wmin][paths] = np.where(np.isfinite(pk), pk, np.nan)
        print("  paths %d/%d  %.0f s" % (paths[-1] + 1, P, time.monotonic() - t0), flush=True)

    # (b) mean over paths against v1
    pipe = multi.numpy()
    b = {}
    act = np.asarray(pipe["active_fire_probability"]).reshape(H, nb, -1)[:, :, src]
    mw = s_w / P
    sw = np.sqrt(np.maximum(q_w / P - mw ** 2, 0.) / (P - 1))
    dw = np.abs(mw - act)
    b["weights"] = {"bins_x_sources": int(dw.size), "largest_abs_diff": float(dw.max()), "largest_v1": float(act.max()),
                    "share_within_3_se_where_se_pos": float(np.mean(dw[sw > 0] <= 3 * sw[sw > 0])),
                    "se_zero_but_v1_pos": int(np.sum((sw == 0) & (act > 0))),
                    "largest_v1_where_se_zero": float(act[(sw == 0)].max()) if np.any(sw == 0) else 0.0,
                    "total_rel_diff": float(abs(mw.sum() - act.sum()) / act.sum())}
    for name, s, q, key, scale in (("radiant", s_rad, q_rad, "q_rad_kw_m2", 1000.), ("co", s_co, q_co, "co_mg_m3", 1.)):
        mean = s / P
        se = np.sqrt(np.maximum(q / P - mean ** 2, 0.) / (P - 1))
        v1f = np.stack([np.load(v1 / ("hour_%02d.npz" % h))[key].reshape(nb, ncell) * scale for h in range(H)])
        d = np.abs(mean - v1f)
        pos = se > 0
        tot_m, tot_v = mean.sum(axis=(1, 2)), v1f.sum(axis=(1, 2))
        tot_se = tot[name].std(axis=0, ddof=1) / np.sqrt(P)
        b[name] = {"cell_bins_with_se_pos": int(pos.sum()),
                   "share_within_3_se_where_se_pos": float(np.mean(d[pos] <= 3 * se[pos])),
                   "share_within_2_se_where_se_pos": float(np.mean(d[pos] <= 2 * se[pos])),
                   "se_zero_but_v1_pos": int(np.sum(~pos & (v1f > 0))),
                   "largest_v1_where_se_zero": float(v1f[~pos].max()) if np.any(~pos) else 0.0,
                   "largest_abs_diff": float(d.max()), "largest_v1": float(v1f.max()),
                   "hourly_total_rel_diff": [float(abs(tot_m[h] - tot_v[h]) / tot_v[h]) for h in range(H)],
                   "hourly_total_z": [float((tot_m[h] - tot_v[h]) / tot_se[h]) for h in range(H)]}
    checks["b_mean_over_paths_vs_v1"] = b

    n = np.float64(P)
    np.savez_compressed(out / "counts.npz", n_paths=np.int64(P), minute_edges=np.arange(T + 1, dtype=np.int64),
                        **{k: v.reshape(T, ny, nx) for k, v in counts.items()})
    summ = {}
    for k, v in peak.items():
        vv = v.astype(np.float64)
        summ[k + "_max"] = np.nanmax(vv, axis=0).reshape(H, ny, nx)
        summ[k + "_q50"] = np.nanquantile(vv, 0.5, axis=0).reshape(H, ny, nx)
        summ[k + "_q90"] = np.nanquantile(vv, 0.9, axis=0).reshape(H, ny, nx)
    np.savez_compressed(out / "peaks.npz", **summ)

    # distance to the nearest burning cell (Amendment 2 item 7), second pass over the paths
    targets = []                                  # (level, criterion, cell, minute)
    for lv, val in LEVELS.items():
        need = 1 if val is None else int(np.ceil(val * n - 1e-9))
        for k in CRITERIA:
            hit = counts[k] >= need
            anyc = hit.any(axis=0)
            fm = np.argmax(hit, axis=0)
            for cell in np.flatnonzero(anyc):
                targets.append((lv, k, int(cell), int(fm[cell])))
    print("distance targets:", len(targets), flush=True)
    res = {t: [] for t in targets}
    by_minute = {}
    for t in targets:
        by_minute.setdefault(t[3], []).append(t)
    tr, tc = np.divmod(np.array([t[2] for t in targets]), nx) if targets else (np.array([]), np.array([]))
    dist_all = (np.hypot((tr[:, None] - rr[None]) * 375., (tc[:, None] - cc[None]) * 375.) if targets else None)
    tindex = {t: i for i, t in enumerate(targets)}
    if targets:
        for b0 in range(0, P, a.batch):
            paths = np.arange(b0, min(P, b0 + a.batch))
            rad_all = np.empty((len(paths), T, ncell), np.float32)
            co_all = np.empty((len(paths), T, ncell), np.float64)
            burn = np.empty((len(paths), T, len(src)), bool)
            for h in range(H):
                w = pw.weights(paths, h, edges)
                rad, co = fields(phys[h], w, edges)
                rad_all[:, h * nb:(h + 1) * nb] = rad.reshape(len(paths), nb, ncell)
                co_all[:, h * nb:(h + 1) * nb] = co.reshape(len(paths), nb, ncell) / MG_M3_PER_PPM
                burn[:, h * nb:(h + 1) * nb] = w > 0
            means = {k: trailing_means(co_all, wmin) for k, (wmin, _) in CO_PPM.items()}
            for minute, ts in by_minute.items():
                for t in ts:
                    lv, k, cell, _ = t
                    if k in RAD_W_M2:
                        holds = rad_all[:, minute, cell] >= RAD_W_M2[k]
                    else:
                        holds = np.nan_to_num(means[k][:, minute, cell], nan=-np.inf) >= CO_PPM[k][1]
                    if holds.any():
                        dmin = np.where(burn[holds, minute], dist_all[tindex[t]][None], np.inf).min(axis=1)
                        res[t].extend(dmin.tolist())
        print("distances done %.0f s" % (time.monotonic() - t0), flush=True)
    rec = {"level": [], "criterion": [], "row": [], "col": [], "minute": [], "n_paths": [], "share": [],
           "dist_median_m": [], "dist_min_m": [], "dist_max_m": []}
    for t in targets:
        lv, k, cell, minute = t
        d = np.array(res[t])
        rec["level"].append(lv)
        rec["criterion"].append(k)
        rec["row"].append(cell // nx)
        rec["col"].append(cell % nx)
        rec["minute"].append(minute)
        rec["n_paths"].append(len(d))
        rec["share"].append(float(counts[k][minute, cell]) / P)
        rec["dist_median_m"].append(float(np.median(d)) if len(d) else np.nan)
        rec["dist_min_m"].append(float(d.min()) if len(d) else np.nan)
        rec["dist_max_m"].append(float(d.max()) if len(d) else np.nan)
        assert len(d) == counts[k][minute, cell], (t, len(d), counts[k][minute, cell])
    np.savez_compressed(out / "distances.npz", **{k: np.array(v) for k, v in rec.items()})
    checks["distance_targets"] = len(targets)
    checks["elapsed_s"] = time.monotonic() - t0
    (out / "checks_v2.json").write_text(json.dumps(checks, indent=1))
    print(json.dumps(checks, indent=1))


if __name__ == "__main__":
    main()
