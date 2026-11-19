"""Virtual vehicle unit in the FDS C064 grass fire: compute virtual readings at 10, 20, 30 m and run the pipeline.

    cd apps/crossing && .venv/bin/python -m virtual_fds.run [--fire-data DIR] [--out virtual_fds/outputs] [--quick]

SIMULATED end to end (FDS model fields -> modelled sensor physics -> crossing modules). Outputs in --out:
results.json, results.csv, fig_*.png, thermal_frames.npz. See REPORT.md for the assumptions and the numbers.
--quick: one decision time and no optics sensitivity runs (for a fast smoke test of the script).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from crossing import _repo
from crossing import heat as heat_mod
from crossing.fuels import C064_GRASS

from . import fields as F
from . import lwir, pipeline as pl, plate as pt, radar_path as rp

DISTANCES_M = (10.0, 20.0, 30.0)
MAIN_RADAR = "cfg_default_clutter_dry"
GEOM: Dict[str, dict] = {}                   # filled from the CLI configs in main()
SNAP_TIMES_S = (40, 45, 50, 55, 60, 65, 70, 75, 80)
DECISION_TIMES_S = (50.0, 53.0, 56.0)
TRACK_WINDOW_S = 8.0
REFLECTOR_BEHIND_TE_M = 5.0
REFLECTOR_Z_M = 1.0
SENS_TIMES_S = (45, 60, 75)
SENS_KAPPA = (0.03, 0.30)
C064 = {"chi": None, "R": None, "I": None, "D": None, "width": None}      # filled from b2_fds_compare.json
OUT_DEFAULT = Path(__file__).resolve().parent / "outputs"


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return v if math.isfinite(v) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    return o


def ground_metrics(f: F.Field, thr: float = 20.0) -> Optional[dict]:
    """Leading/trailing edge from the two lowest cell layers only (z < 2 m): the flame BASE the camera sees."""
    return F.voxel().front_metrics(f.hrr[:2].astype(float), f.x, f.y, f.z[:2], threshold_kw_m3=thr)


def log(msg):
    print("[virtual_fds %6.1fs] %s" % (time.time() - T0, msg), flush=True)


T0 = time.time()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fire-data", default=os.environ.get("C064_FIRE_DATA", str(F.DEFAULT_FIRE_DATA)))
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--no-hash", action="store_true", help="skip sha256 of the out-of-repo npz files")
    args = ap.parse_args(argv)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    fd = F.FireData(args.fire_data)
    if not fd.available:
        print("fire data not found in %s (need %s and %s)" % (fd.dir, F.DT5_NAME, F.ROI_NAME), file=sys.stderr)
        return 2
    b2 = pt.b2()
    C064.update(chi=b2["radiant_fraction"], R=b2["spread_m_s"], I=b2["mean_intensity_kw_m"], D=b2["mean_depth_m"],
                width=b2["mean_width_m"])
    res: Dict = {"label": "SIMULATED: virtual vehicle unit in the FDS C064 model; not a measurement",
                 "c064_params_from_b2": dict(C064)}

    # ------------------------------------------------------------------ provenance
    prov = {"fire_data_dir": str(fd.dir), "files": {}}
    for p in (fd.dt5_path, fd.roi_path):
        prov["files"][p.name] = {"path": str(p), "bytes": p.stat().st_size,
                                 "sha256": None if args.no_hash else F.sha256(p)}
    for p in (_repo.C064_DEVC, _repo.B2_FDS_COMPARE):
        prov["files"][p.name] = {"path": str(p.relative_to(_repo.REPO)), "sha256": F.sha256(p)}
    prov["roi_vs_dt5_identity"] = fd.check_roi_identity()
    GEOM.update(default=rp.cfg_geometry(rp.DEFAULT_CFG), short=rp.cfg_geometry(rp.SHORT_CFG),
                long_fine=rp.cfg_geometry(rp.LONG_FINE_CFG))
    prov["radar_configs"] = dict(GEOM)
    res["radar_main_case"] = {"variant": MAIN_RADAR, "config": GEOM["default"]["cfg"],
                              "note": "SIMULATED; bins/spacing/max range/lambda read from the config file; clutter per "
                                      "bin scaled by bin length (+%.1f dB vs 0.0488 m bins)" % (
                                          10 * math.log10(GEOM["default"]["range_res_m"] / rp.CLUTTER_REF_RES_M))}
    res["provenance"] = prov
    log("provenance done: %s" % prov["roi_vs_dt5_identity"])

    # ------------------------------------------------------------------ truth on the 5 s frames
    t5 = fd.dt5_times()
    snap_k = [int(np.argmin(np.abs(t5 - ts))) for ts in SNAP_TIMES_S]
    win_k = [k for k in range(len(t5)) if pt.WINDOW_S[0] <= t5[k] <= pt.WINDOW_S[1]]
    truth5 = {}
    for k in win_k:
        f = fd.dt5_field(k)
        tm = F.truth_metrics(f)
        tm["ground20"] = ground_metrics(f)
        truth5[k] = tm
    le5 = [truth5[k]["20"]["le"] for k in win_k]
    tt5 = [float(t5[k]) for k in win_k]
    truth = {"dt5_frames": [{"t_s": float(t5[k]), **{("thr" + key): (None if v is None else
             {kk: v[kk] for kk in ("le", "te", "depth", "flame_height", "intensity", "centroid")})
             for key, v in truth5[k].items()}} for k in win_k]}
    for thr in ("5", "20", "100"):
        dep = [truth5[k][thr]["depth"] for k in win_k]
        fh = [truth5[k][thr]["flame_height"] for k in win_k]
        lek = [truth5[k][thr]["le"] for k in win_k]
        truth["thr" + thr] = {"depth_mean_m": float(np.mean(dep)), "depth_min_m": float(np.min(dep)),
                              "depth_max_m": float(np.max(dep)), "flame_height_mean_m": float(np.mean(fh)),
                              "spread_m_s": F.spread_fit(tt5, lek)}
    gd = [truth5[k]["ground20"]["depth"] for k in win_k]
    truth["ground20"] = {"depth_mean_m": float(np.mean(gd)),
                         "le_offset_mean_m": float(np.mean([truth5[k]["20"]["le"] - truth5[k]["ground20"]["le"]
                                                            for k in win_k]))}
    truth["intensity_mean_kw_m"] = float(np.mean([truth5[k]["20"]["intensity"] for k in win_k]))
    head, devc = pt.read_devc()
    wd = (devc[:, 0] >= pt.WINDOW_S[0]) & (devc[:, 0] <= pt.WINDOW_S[1])
    truth["fds_fire_depth_device"] = {"mean_m": float(devc[wd, head.index("D")].mean()),
                                      "min_m": float(devc[wd, head.index("D")].min()),
                                      "max_m": float(devc[wd, head.index("D")].max()),
                                      "note": "FDS DEVC QUANTITY='FIRE DEPTH' on the line y=0, z=0.1; its definition "
                                              "is FDS's own and was not checked here"}
    truth["b2"] = {"spread_m_s": C064["R"], "intensity_kw_m": C064["I"], "depth_mean_m": C064["D"],
                   "width_m": C064["width"], "chi": C064["chi"]}
    truth["brief_depth_m"] = 12.0
    res["truth"] = truth
    log("truth: depth20 mean %.2f m, R %.3f m/s" % (truth["thr20"]["depth_mean_m"], truth["thr20"]["spread_m_s"]))

    # ------------------------------------------------------------------ snapshot set (5 s frames)
    snaps = []
    thermal_save = {}
    for k in snap_k:
        f = fd.dt5_field(k)
        tm = truth5[k]
        gm = tm["ground20"]
        le = tm["20"]["le"]
        vsamp = F.Sampler(f, f.temp_k, outside=[f.t_ambient_k])
        for d in DISTANCES_M:
            xv = le + d
            ob = pl.observe(f, xv)
            row = {"t_s": float(f.t), "d_nominal_m": d, **ob.summary(), "le_m": le, "le_ground_m": gm["le"],
                   "te_m": tm["20"]["te"], "depth_true_m": tm["20"]["depth"], "flame_height_true_m": tm["20"]["flame_height"],
                   "d_true_m": d, "d_true_ground_m": xv - gm["le"]}
            for zz in (1.5, 2.5):
                row["voxel_kw_m2_z%.1f" % zz] = F.voxel().voxel_flux(f.hrr.astype(float), f.x, f.y, f.z, (xv, 0.0, zz),
                                                                     chi=C064["chi"])
                row["gas_temp_c_z%.1f" % zz] = float(vsamp.sample([xv], [0.0], [zz])[0][0] - 273.15)
            snaps.append(row)
            if abs(f.t - 60.0) < 1.0:
                thermal_save["d%02d_t60" % int(d)] = (ob.temps_k - 273.15).astype(np.float16)
        log("snapshot t=%.0f done" % f.t)
    res["snapshots"] = snaps

    # snapshot-based estimator a (world track over the 5 s frames, vehicle re-placed per frame) and b
    snap_depth = {}
    for d in DISTANCES_M:
        rows = [r for r in snaps if r["d_nominal_m"] == d and r["near_edge_x_world_m"] is not None]
        track = [(r["t_s"], r["near_edge_x_world_m"]) for r in rows]
        a = pl.dp.spread_burn(track, C064_GRASS)
        hs = [r["flame_height_m"] for r in rows if r["flame_height_m"] is not None]
        b = pl.dp.byram(float(np.median(hs)) if hs else None, C064_GRASS)
        comb = pl.dp.combine([a, b])
        snap_depth["%g" % d] = {"a_spread_burn": a.to_dict(), "b_byram_median_height": b.to_dict(),
                                "combined": pl.depth_row(comb, C064["D"]),
                                "near_edge_error_m": [r["near_edge_m"] - r["d_true_m"] for r in rows],
                                "near_edge_error_vs_ground_m": [r["near_edge_m"] - r["d_true_ground_m"] for r in rows],
                                "flame_height_m": hs}
    res["snapshot_depth"] = snap_depth

    # optics sensitivity
    sens = []
    if not args.quick:
        for ts in SENS_TIMES_S:
            k = int(np.argmin(np.abs(t5 - ts)))
            f = fd.dt5_field(k)
            le = truth5[k]["20"]["le"]
            for kg in SENS_KAPPA:
                for d in DISTANCES_M:
                    ob = pl.observe(f, le + d, params=lwir.OpticsParams(kappa_gas0=kg))
                    s = ob.summary()
                    sens.append({"t_s": float(f.t), "kappa_gas0": kg, "d_nominal_m": d, "near_edge_m": s["near_edge_m"],
                                 "flame_height_m": s["flame_height_m"], "flame_pixels": s["flame_pixels"],
                                 "byram_depth_m": pl.dp.byram(s["flame_height_m"], C064_GRASS).value_m})
            log("sensitivity t=%.0f done" % f.t)
    res["optics_sensitivity"] = sens

    # ------------------------------------------------------------------ 1 s sequences (ROI composite)
    t1 = fd.roi_times()
    comp_cache: Dict[int, F.Field] = {}
    tm_cache: Dict[int, dict] = {}

    def comp(k):
        if k not in comp_cache:
            comp_cache[k] = fd.compose(k, C064["R"])
            tm_cache[k] = {"20": comp_cache[k].metrics(20.0), "5": comp_cache[k].metrics(5.0),
                           "100": comp_cache[k].metrics(100.0), "ground20": ground_metrics(comp_cache[k])}
        return comp_cache[k]

    seqs = []
    radar_fig = {}
    dec_times = DECISION_TIMES_S[:1] if args.quick else DECISION_TIMES_S
    for t_end in dec_times:
        k_end = int(np.argmin(np.abs(t1 - t_end)))
        ks = [k for k in range(len(t1)) if t1[k_end] - TRACK_WINDOW_S - 0.2 <= t1[k] <= t1[k_end]]
        for k in ks:
            comp(k)
        te_end = tm_cache[k_end]["20"]["te"]; le_end = tm_cache[k_end]["20"]["le"]
        for d in DISTANCES_M:
            xv = le_end + d
            obs = [pl.observe(comp_cache[k], xv) for k in ks]
            track = [(o.t, o.x_vehicle - o.near_edge.d_m) for o in obs if o.near_edge is not None]
            last = obs[-1]
            ne_d = last.near_edge.d_m if last.near_edge is not None else None
            ne_slant = math.hypot(ne_d, pl.CAMERA_HEIGHT_M) if ne_d is not None else None
            x_ref = te_end - REFLECTOR_BEHIND_TE_M
            radar = {}
            tt = [float(t1[k]) for k in ks]
            kw = dict(x_r=xv, x_ref=x_ref, z_ref=REFLECTOR_Z_M)
            # MAIN = the unit's default CLI config (bins / spacing / max range / lambda read from the file); the
            # others are labelled side cases. Phases are computed per bin geometry (spacing, count, lambda).
            variants = {
                MAIN_RADAR: (rp.Scene.from_cfg(GEOM["default"], **kw), "dry"),
                "cfg_default_clutter_wet": (rp.Scene.from_cfg(GEOM["default"], **kw), "wet"),
                "cfg_default_reflector_only_dry": (rp.Scene.from_cfg(GEOM["default"], ground_clutter=False, **kw), "dry"),
                "cfg_default_clutter_unscaled_dry": (rp.Scene.from_cfg(GEOM["default"], scale_clutter=False, **kw), "dry"),
                "cfg_long_fine_clutter_dry": (rp.Scene.from_cfg(GEOM["long_fine"], **kw), "dry"),
                "cfg_short22.5m_clutter_dry": (rp.Scene.from_cfg(GEOM["short"], **kw), "dry"),
                "virtual60m_0.0488m_clutter_dry": (rp.Scene(label="virtual 60 m, 0.0488 m bins, 61.8 GHz (no config)",
                                                            **kw), "dry"),
            }
            phase_cache: Dict[tuple, list] = {}
            for name, (sc, which) in variants.items():
                key = (sc.range_res_m, sc.n_bins, sc.lambda_m, which)
                if key not in phase_cache:
                    phase_cache[key] = [rp.excess_phase(comp_cache[k], sc, wet=(which == "wet")) for k in ks]
            runs = {}
            for name, (sc, which) in variants.items():
                ph = phase_cache[(sc.range_res_m, sc.n_bins, sc.lambda_m, which)]
                run = runs[name] = rp.run_detector(tt, ph, sc, ne_slant, seed=int(100 * d + t_end))
                st = run.state
                pb = st.per_bin or {}
                fz = pb.get("flicker_phase_z")
                # ceiling as the app forms it: horizontal distances, far echo assumed at ground level
                # (crossing/pipeline.py); the slant-range difference is kept for comparison only.
                est_c_det = pl.ceiling_like_app(ne_slant, st.far_echo_m, sc.range_res_m)
                est_c_slant = pl.dp.radar_ceiling(ne_slant, st.far_echo_m, sc.range_res_m)
                est_d = pl.dp.flicker_extent(fz, ne_slant, sc.range_res_m) if fz is not None else None
                est_d_or = pl.dp.flicker_extent(run.oracle_z, ne_slant, sc.range_res_m)
                gap20 = max(1, int(round(20 * 0.0488 / sc.range_res_m)))       # ~0.98 m of gap at any spacing
                est_d_or_gap = pl.dp.flicker_extent(run.oracle_z, ne_slant, sc.range_res_m, max_gap_bins=gap20)
                rph = [v for v in (run.reflector_phase_series or []) if v is not None]
                oz = run.oracle_z
                beyond = sc.ranges > (ne_slant or 0.0)
                radar[name] = {"status": st.status, "reason": st.reason, "far_echo_m": st.far_echo_m,
                               "flicker_phase_z_max": st.flicker_phase_z, "flicker_phase_rad_max": st.flicker_phase_rad,
                               "noise_db": st.noise_db, "n_frames": st.n_frames, "effect_bins": len(st.effect_ranges_m),
                               "effect_range_min_m": min(st.effect_ranges_m) if st.effect_ranges_m else None,
                               "effect_range_max_m": max(st.effect_ranges_m) if st.effect_ranges_m else None,
                               "reflector_range_m": sc.reflector_range, "reflector_in_range": sc.reflector_bin is not None,
                               "reflector_phase_series_rad": run.reflector_phase_series if sc.reflector_bin is not None else None,
                               "ceiling_from_detector_far_echo": est_c_det.to_dict(),
                               "ceiling_geometry": "horizontal distances as crossing/pipeline.py forms them (far "
                                                   "echo assumed at ground level, radar %.1f m); reflector at z = "
                                                   "%.1f m" % (sc.h_r, sc.z_ref),
                               "ceiling_slant_difference_m": est_c_slant.value_m if est_c_slant.valid else None,
                               "reflector_horizontal_true_m": abs(sc.x_r - sc.x_ref) if sc.x_ref is not None else None,
                               "flicker_extent": None if est_d is None else est_d.to_dict(),
                               "oracle_flicker_extent": est_d_or.to_dict(),
                               "oracle_flicker_extent_gap_m1": est_d_or_gap.to_dict(),
                               "oracle_flicker_extent_gap_bins": gap20,
                               "oracle_z_flagged_beyond_near_edge": int(np.sum(np.nan_to_num(oz[beyond], nan=-1) >= 4.0)),
                               "oracle_z_scored_beyond_near_edge": int(np.sum(np.isfinite(oz[beyond]))),
                               "reflector_excess_phase_rad": None if not rph else {
                                   "min": float(np.min(rph)), "max": float(np.max(rph)),
                                   "framediff_circstd": float(rp._circ_std(np.diff(rph))) if len(rph) > 1 else None},
                               "max_range_m": sc.max_range_m, "range_res_m": sc.range_res_m, "n_bins": sc.n_bins,
                               "lambda_m": sc.lambda_m, "clutter_g0_db": sc.clutter_g0_db,
                               "ground_clutter": sc.ground_clutter, "scene": sc.label, "wet": which == "wet",
                               "noise_rise_db": st.noise_rise_db, "n_control_bins": st.n_control_bins,
                               "control_z_median": st.control_z_median, "effect_s": st.effect_s,
                               "label": "SIMULATED"}
                if name == MAIN_RADAR and abs(t_end - DECISION_TIMES_S[-1 if not args.quick else 0]) < 1e-6:
                    radar_fig["%g" % d] = {"range_m": sc.ranges, "z": np.asarray(fz if fz is not None else [], dtype=float),
                                           "oracle_z": run.oracle_z,
                                           "true_flicker_rad": run.flicker_phase_rad_true, "near_edge_slant_m": ne_slant,
                                           "le_slant_m": math.hypot(d, pl.CAMERA_HEIGHT_M),
                                           "te_slant_m": math.hypot(xv - te_end, pl.CAMERA_HEIGHT_M),
                                           "reflector_m": sc.reflector_range}
            main_r = radar[MAIN_RADAR]
            main_sc = variants[MAIN_RADAR][0]
            # estimators on the MAIN radar config: c as the brief asks = reflector geometry (true reflector slant
            # range, quantised to the config's bin); d from the clutter flicker; d' from the oracle z
            fz_main = (runs[MAIN_RADAR].state.per_bin or {}).get("flicker_phase_z")
            far_ref = (main_sc.reflector_bin * main_sc.range_res_m) if main_sc.reflector_bin is not None else None
            ests = pl.estimates(track, last, C064_GRASS, far_echo_slant_m=far_ref,
                                near_edge_slant_m=ne_slant, flicker_z=fz_main, range_res_m=main_sc.range_res_m)
            ests["d_flicker_extent_oracle"] = pl.dp.flicker_extent(runs[MAIN_RADAR].oracle_z, ne_slant,
                                                                   main_sc.range_res_m)
            combs = pl.combine_variants(ests)
            inten = pl.dp.intensity(last.flame_height, ests["a_spread_burn"], C064_GRASS)
            depth_true = tm_cache[k_end]["20"]["depth"]
            seqs.append({
                "t_end_s": float(t1[k_end]), "d_nominal_m": d, "x_vehicle_m": xv, "frames": len(ks),
                "truth_end": {kk: (None if v is None else {q: v[q] for q in ("le", "te", "depth", "flame_height")})
                              for kk, v in tm_cache[k_end].items()},
                "truth_window_depth20_mean_m": float(np.mean([tm_cache[k]["20"]["depth"] for k in ks])),
                "truth_window_spread_m_s": F.spread_fit([float(t1[k]) for k in ks], [tm_cache[k]["20"]["le"] for k in ks]),
                "observations": [o.summary() for o in obs],
                "d_true_end_m": xv - le_end, "d_true_ground_end_m": xv - tm_cache[k_end]["ground20"]["le"],
                "near_edge_end_m": ne_d, "near_edge_slant_m": ne_slant,
                "track": track, "radar": radar,
                "estimates": {kk: v.to_dict() for kk, v in ests.items()},
                "combined": {kk: pl.depth_row(v, C064["D"]) for kk, v in combs.items()},
                "combined_vs_instant_truth": {kk: pl.depth_row(v, depth_true) for kk, v in combs.items()},
                "radar_fusion_flame": pl_fuse(main_r["status"], last.flame_at_boresight, main_r["reason"]),
                "intensity": inten.to_dict(),
            })
            log("sequence t_end=%.0f d=%g: near edge %s, depth %s" % (
                t1[k_end], d, None if ne_d is None else round(ne_d, 2),
                seqs[-1]["combined"]["default(a+b)"].get("depth_m")))
    res["sequences"] = seqs

    # ------------------------------------------------------------------ flux at 10 / 20 / 30 m
    samples = pt.radiometer_samples(head, devc)
    flux = {"radiometer_at_d": [pt.radiometer_at(samples, d) for d in DISTANCES_M],
            "b2_bins": [{"d_bin_m": b["d_bin_m"], "n": b["n"], "fds_geomean": b["fds_geomean"], "cf_geomean": b["cf_geomean"],
                         "voxel_geomean": b["voxel_geomean"]} for b in b2["bins"]],
            "closed_form": [], "voxel_snapshots": [], "n_radiometer_samples": len(samples)}
    for d in DISTANCES_M:
        cf_fin = heat_mod.closed_form_line_flux(d, C064["D"], C064["I"], C064["chi"], C064["width"] / 2.0)
        cf_long = heat_mod.closed_form_line_flux(d, C064["D"], C064["I"], C064["chi"], None)
        ref = heat_mod.fds_reference(d, C064["I"])
        rows = [r for r in snaps if r["d_nominal_m"] == d]
        vox = {zz: [r["voxel_kw_m2_z%.1f" % zz] for r in rows] for zz in (1.5, 2.5)}
        gas = {zz: [r["gas_temp_c_z%.1f" % zz] for r in rows] for zz in (1.5, 2.5)}
        flux["closed_form"].append({"d_m": d, "finite_front_kw_m2": cf_fin, "long_front_kw_m2": cf_long,
                                    "crossing_heat_fds_reference_kw_m2": ref.q_kw_m2})
        flux["voxel_snapshots"].append({"d_m": d, **{("z%.1f" % zz): {"mean": float(np.mean(v)), "min": float(np.min(v)),
                                                                        "max": float(np.max(v))} for zz, v in vox.items()},
                                        **{("gas_temp_c_z%.1f" % zz): {"mean": float(np.mean(v)), "max": float(np.max(v))}
                                           for zz, v in gas.items()},
                                        # convective heating of a plate still at ambient (32 C) by the FDS gas at its
                                        # position: h (T_gas - 32 C); h = 12 (fit default) and 25 W/m2K (windy). Estimate.
                                        **{("conv_est_kw_m2_z2.5_h%d" % h): h * (float(np.mean(gas[2.5])) - 32.0) / 1000.0
                                           for h in (12, 25)}})
    # plate round trip on the RAD_X102 position
    t_le, le_b2 = pt.le_track_b2(b2)
    xdev = pt.RADIOMETERS["RAD_X102"]
    wsel = (devc[:, 0] >= pt.WINDOW_S[0]) & (devc[:, 0] <= pt.WINDOW_S[1])
    td = devc[wsel, 0]
    q_rad = devc[wsel, head.index("RAD_X102")]
    d_of_t = xdev - np.interp(td, t_le, le_b2)
    q_cf = np.array([heat_mod.closed_form_line_flux(max(dd, 0.0), C064["D"], C064["I"], C064["chi"], C064["width"] / 2)
                     for dd in d_of_t])
    vt, vq = [], []
    for k in win_k:
        f = fd.dt5_field(k)
        vt.append(float(t5[k]))
        vq.append(F.voxel().voxel_flux(f.hrr.astype(float), f.x, f.y, f.z, (xdev, 0.0, 1.5), chi=C064["chi"]))
    q_vox = np.exp(np.interp(td, vt, np.log(np.maximum(vq, 1e-6))))
    t_at = {}
    for d in DISTANCES_M:
        idx = np.flatnonzero(d_of_t <= d)
        t_at["%g" % d] = float(td[idx[0]]) if idx.size else None
    plate_res = {}
    plate_fig = {}
    for name, q in (("fds_radiometer_RAD_X102", q_rad), ("closed_form_finite", q_cf), ("voxel_z1.5", q_vox)):
        pr = pt.simulate_plate(td, q, air_c=32.0, seed=11)
        plate_res[name] = {"%g" % d: (pt.recovered_at(pr, t_at["%g" % d], 1.0) if t_at["%g" % d] else None)
                           for d in DISTANCES_M}
        plate_res[name]["10s_means"] = {"%g" % d: (pt.recovered_at(pr, t_at["%g" % d], 5.0) if t_at["%g" % d] else None)
                                        for d in DISTANCES_M}
        plate_fig[name] = pr
    flux["plate_round_trip"] = {"device_x_m": xdev, "z_m": 1.5, "times_at_d_s": t_at, "results": plate_res,
                                "loss_model": {"h_w_m2k": 12.0, "eps": 0.95}, "noise_c": 0.12, "quant_c": 0.25,
                                "fs_hz": 10.0, "window_s": 1.0}
    res["flux"] = flux
    log("flux done")

    # ------------------------------------------------------------------ attenuation estimates
    fv_max = max(float(fd.dt5_field(k).soot.max()) for k in win_k) / lwir.SOOT_DENSITY
    att = {"lambda_m": rp.LAMBDA_M, "soot_fv_max": fv_max, "soot_loss_db_per_m_at_fv_max": rp.soot_loss_db_per_m(fv_max),
           "soot_two_way_db_over_depth": 2 * rp.soot_loss_db_per_m(fv_max) * C064["D"],
           "plasma_table": [{"n_e_m3": ne, "nu_s": nu, "db_per_m_one_way": rp.plasma_loss_db_per_m(ne, nu),
                             "two_way_db_over_depth": 2 * C064["D"] * rp.plasma_loss_db_per_m(ne, nu)}
                            for ne in (1e15, 1e16, 1e17) for nu in (1e11, 1e12)]}
    res["radar_attenuation_estimates"] = att

    # ------------------------------------------------------------------ write
    (out / "results.json").write_text(json.dumps(_clean(res), indent=1) + "\n")
    write_csv(out / "results.csv", res)
    np.savez_compressed(out / "thermal_frames.npz", **thermal_save,
                        note=np.array("SIMULATED virtual TC001 frames, apparent temperature C, float16, dt5 t=60 s"))
    figures(out, res, thermal_save, radar_fig, plate_fig, td, d_of_t, samples)
    log("written to %s" % out)
    return 0


def pl_fuse(radar_status: str, thermal_flag: bool, radar_reason: str = "") -> dict:
    from crossing.radar_flame import RadarState, fuse_flame
    st = fuse_flame(RadarState(status=radar_status, reason=radar_reason), thermal_flag)
    return {"status": st.status, "reason": st.reason}


def write_csv(path: Path, res: dict) -> None:
    rows = []
    for s in res["sequences"]:
        base = {"set": "1s_sequence", "t_end_s": round(s["t_end_s"], 2), "d_nominal_m": s["d_nominal_m"]}
        rows.append({**base, "quantity": "near_edge_m", "value": s["near_edge_end_m"], "truth": s["d_true_end_m"],
                     "truth_alt": s["d_true_ground_end_m"]})
        h = s["observations"][-1]
        rows.append({**base, "quantity": "flame_height_m", "value": h["flame_height_m"],
                     "truth": s["truth_end"]["20"]["flame_height"]})
        for k, e in s["estimates"].items():
            rows.append({**base, "quantity": "est_" + k, "value": e["value_m"], "lo": e["lo_m"], "hi": e["hi_m"],
                         "valid": e["valid"], "truth": res["truth"]["b2"]["depth_mean_m"], "note": e["reason"]})
        for k, c in s["combined"].items():
            rows.append({**base, "quantity": "depth_" + k, "value": c.get("depth_m"), "lo": c.get("lo_m"),
                         "hi": c.get("hi_m"), "valid": c.get("valid"), "truth": res["truth"]["b2"]["depth_mean_m"],
                         "covers_truth": c.get("covers_truth"), "truth_alt": s["truth_end"]["20"]["depth"]})
        for k, r in s["radar"].items():
            rows.append({**base, "quantity": "radar_" + k, "value": r["flicker_phase_z_max"], "note": r["status"],
                         "truth": r["reflector_range_m"], "truth_alt": r["far_echo_m"]})
    for f in res["flux"]["radiometer_at_d"]:
        rows.append({"set": "flux", "d_nominal_m": f["d_m"], "quantity": "fds_radiometer_geomean_kw_m2",
                     "value": f["geomean_kw_m2"], "lo": f["min_kw_m2"], "hi": f["max_kw_m2"], "note": "n=%d" % f["n"]})
    for f in res["flux"]["closed_form"]:
        rows.append({"set": "flux", "d_nominal_m": f["d_m"], "quantity": "closed_form_finite_kw_m2", "value": f["finite_front_kw_m2"]})
        rows.append({"set": "flux", "d_nominal_m": f["d_m"], "quantity": "closed_form_long_kw_m2", "value": f["long_front_kw_m2"]})
    for f in res["flux"]["voxel_snapshots"]:
        for zz in ("z1.5", "z2.5"):
            rows.append({"set": "flux", "d_nominal_m": f["d_m"], "quantity": "voxel_kw_m2_" + zz, "value": f[zz]["mean"],
                         "lo": f[zz]["min"], "hi": f[zz]["max"]})
    for name, r in res["flux"]["plate_round_trip"]["results"].items():
        for d in ("10", "20", "30"):
            v = r.get(d)
            if v and v.get("n"):
                rows.append({"set": "plate", "d_nominal_m": float(d), "quantity": "plate_" + name, "value": v["q_recovered_kw_m2"],
                             "truth": v["q_input_kw_m2"], "note": "rms %.3f" % v["rms_error_kw_m2"]})
    cols = ["set", "t_end_s", "d_nominal_m", "quantity", "value", "lo", "hi", "valid", "truth", "truth_alt",
            "covers_truth", "note"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: _fmt(r.get(c)) for c in cols})


def _fmt(v):
    if isinstance(v, float):
        return "" if not math.isfinite(v) else "%.6g" % v
    return "" if v is None else v


def figures(out: Path, res: dict, thermal_save: dict, radar_fig: dict, plate_fig: dict, td, d_of_t, samples) -> None:
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(os.environ.get("TMPDIR", "/tmp"), "mpl"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # thermal
    if thermal_save:
        keys = sorted(thermal_save)
        fig, axs = plt.subplots(1, len(keys), figsize=(3.4 * len(keys) + 1.2, 2.9), constrained_layout=True)
        axs = np.atleast_1d(axs)
        for ax, k in zip(axs, keys):
            a = thermal_save[k].astype(float)
            im = ax.imshow(a, cmap="inferno", vmin=-20, vmax=550)
            ax.contour(a >= 300.0, [0.5], colors="c", linewidths=0.8)
            ax.set_title("%s m ahead, t=60 s" % k[1:3], fontsize=9); ax.set_xticks([]); ax.set_yticks([])
        fig.colorbar(im, ax=axs.tolist(), label="apparent C (TC001 low gain, capped 550)", shrink=0.8)
        fig.suptitle("SIMULATED virtual TC001 in FDS C064 (cyan: >= 300 C flame mask)", fontsize=9)
        fig.savefig(out / "fig_thermal.png", dpi=75); plt.close(fig)
    # flux
    fl = res["flux"]
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ds = np.array([s["d"] for s in samples]); qs = np.array([s["q"] for s in samples])
    ax.scatter(ds, np.maximum(qs, 1e-3), s=4, c="0.6", label="FDS radiometers z=1.5 m (0.5 s, 40-84 s)")
    dd = np.linspace(1, 50, 100)
    ax.plot(dd, [heat_mod.closed_form_line_flux(x, C064["D"], C064["I"], C064["chi"], C064["width"] / 2) for x in dd],
            label="closed form, finite front")
    ax.plot(dd, [heat_mod.closed_form_line_flux(x, C064["D"], C064["I"], C064["chi"], None) for x in dd], "--",
            label="closed form, long front")
    for zz, mk in (("z1.5", "s"), ("z2.5", "^")):
        ax.plot([v["d_m"] for v in fl["voxel_snapshots"]], [v[zz]["mean"] for v in fl["voxel_snapshots"]], mk,
                label="voxel sum %s (5 s frames)" % zz)
    ax.plot([v["d_m"] for v in fl["radiometer_at_d"]], [v["geomean_kw_m2"] for v in fl["radiometer_at_d"]], "ko",
            label="FDS radiometer geomean at d +- 2 m")
    pr = fl["plate_round_trip"]["results"]["fds_radiometer_RAD_X102"]["10s_means"]
    ks = [k for k in ("10", "20", "30") if pr.get(k) and pr[k].get("q_recovered_kw_m2", -1) > 0]
    ax.plot([float(k) for k in ks], [pr[k]["q_recovered_kw_m2"] for k in ks], "rx", ms=9,
            label="virtual plate recovered, 10 s mean (RAD_X102 input)")
    pc = fl["plate_round_trip"]["results"]["closed_form_finite"]["10s_means"]
    ks = [k for k in ("10", "20", "30") if pc.get(k) and pc[k].get("q_recovered_kw_m2", -1) > 0]
    ax.plot([float(k) for k in ks], [pc[k]["q_recovered_kw_m2"] for k in ks], "b+", ms=9,
            label="virtual plate recovered, 10 s mean (closed-form input)")
    ax.set_yscale("log"); ax.set_xlabel("distance ahead of leading edge d (m)"); ax.set_ylabel("kW/m2")
    ax.set_title("SIMULATED flux ahead of the C064 head", fontsize=9); ax.legend(fontsize=6); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(out / "fig_flux.png", dpi=80); plt.close(fig)
    # plate
    fig, axs = plt.subplots(2, 1, figsize=(6.2, 4.6), sharex=True)
    for name, p in plate_fig.items():
        axs[0].plot(p.t, p.plate_true_c, label=name)
        axs[1].plot(p.q_est_t, p.q_est, lw=0.6, label=name + " recovered")
        axs[1].plot(p.t, p.q_true, "k", lw=0.5)
    axs[0].set_ylabel("plate C"); axs[1].set_ylabel("kW/m2 (black: input)"); axs[1].set_xlabel("FDS time (s)")
    axs[0].legend(fontsize=6); axs[1].set_ylim(-2, 20); axs[0].set_title("SIMULATED copper plate at x=102 m, z=1.5 m", fontsize=9)
    fig.tight_layout(); fig.savefig(out / "fig_plate.png", dpi=80); plt.close(fig)
    # radar
    if radar_fig:
        fig, axs = plt.subplots(len(radar_fig), 1, figsize=(6.4, 2.2 * len(radar_fig)), sharex=True)
        axs = np.atleast_1d(axs)
        for ax, (d, r) in zip(axs, sorted(radar_fig.items(), key=lambda kv: float(kv[0]))):
            ax.plot(r["range_m"], r["true_flicker_rad"], "0.5", lw=0.6, label="noise-free phase flicker (rad)")
            if r["z"].size:
                ax.plot(r["range_m"], r["z"], "b.", ms=2, label="detector flicker_phase_z")
            ax.plot(r["range_m"], r["oracle_z"], "m", lw=0.5, label="oracle z (true SNR, local adapter)")
            ax.axhline(4.0, color="b", ls=":", lw=0.6)
            for x, c, lab in ((r["near_edge_slant_m"], "r", "thermal near edge"), (r["le_slant_m"], "orange", "le (20 kW/m3)"),
                              (r["te_slant_m"], "g", "te"), (r["reflector_m"], "k", "reflector")):
                if x is not None:
                    ax.axvline(x, color=c, lw=0.8, label=lab)
            ax.set_ylabel("d=%s m" % d); ax.grid(alpha=0.3)
        axs[0].legend(fontsize=6, ncol=3); axs[-1].set_xlabel("slant range (m)")
        axs[0].set_title("SIMULATED 60 GHz phase flicker per range bin (1 s FDS frames, %s)" % GEOM["default"]["cfg"].split("/")[-1],
                         fontsize=9)
        fig.tight_layout(); fig.savefig(out / "fig_radar.png", dpi=80); plt.close(fig)
    # depth
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    tr = res["truth"]
    ax.axhspan(tr["thr100"]["depth_mean_m"], tr["thr5"]["depth_mean_m"], color="0.9", label="truth 100-5 kW/m3 edge")
    ax.axhline(tr["thr20"]["depth_mean_m"], color="k", lw=1, label="truth 20 kW/m3 (5 s mean)")
    off = {"a_spread_burn": -1.0, "b_byram": -0.6, "c_radar_ceiling": -0.2, "d_flicker_extent": 0.2,
           "d_flicker_extent_oracle": 0.6}
    cols = {"a_spread_burn": "C0", "b_byram": "C1", "c_radar_ceiling": "C2", "d_flicker_extent": "C3",
            "d_flicker_extent_oracle": "C4"}
    for s in res["sequences"]:
        x0 = s["d_nominal_m"] + (s["t_end_s"] - 53.0) * 0.12
        for k, dx in off.items():
            e = s["estimates"].get(k)
            if e and e["valid"]:
                ax.errorbar(x0 + dx, e["value_m"], yerr=[[e["value_m"] - e["lo_m"]], [e["hi_m"] - e["value_m"]]], fmt="o",
                            ms=3, color=cols[k], lw=0.7)
        c = s["combined"]["default(a+b)"]
        if c.get("valid"):
            ax.errorbar(x0 + 1.0, c["depth_m"], yerr=[[c["depth_m"] - c["lo_m"]], [c["hi_m"] - c["depth_m"]]], fmt="s", ms=4,
                        color="m", lw=1.2)
    for k, cc in cols.items():
        ax.plot([], [], "o", color=cc, label=k)
    ax.plot([], [], "s", color="m", label="combined (a+b), 90 %")
    ax.set_xlabel("nominal distance (m)"); ax.set_ylabel("depth (m)"); ax.set_yscale("log")
    ax.set_title("SIMULATED depth estimates vs FDS truth (1 s sequences)", fontsize=9); ax.legend(fontsize=6, ncol=2)
    fig.tight_layout(); fig.savefig(out / "fig_depth.png", dpi=80); plt.close(fig)


if __name__ == "__main__":
    sys.exit(main())
