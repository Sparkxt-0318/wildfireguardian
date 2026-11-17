"""B.2: FDS gas-phase radiometers vs distance-to-front, against the voxel sum on the SAME run, the closed form, v2 and
the frozen cap. Model-to-model only (FDS is not measurement).

    python scripts/b2_fds_compare.py RUN_DIR HRRPUV_1S.npz OUT.json [RUN_A_DEVC.csv]

RUN_DIR: the rerun (input.fds, *_devc.csv, *_hrr.csv). HRRPUV_1S.npz: stitch_fds_slice.py output (x >= 30 m, 1 s).
The front (leading edge, HRRPUV > 20 kW/m3 in |y| <= 2.5 m, as in B.1) is measured on every 1-s frame; device values
are interpolated to the frame times. A sample is used while the radiometer is ahead of the leading edge (d >= 1 m) and
the head is in the quasi-steady window (frame time 40..84 s; the head reaches the end of the fuel bed, x = 100 m, at
about 85 s). Voxel sums use only x >= 30 m (the slice extent); the truncation is quantified on the full-domain dt5
field in B.1's npz (reported as 'truncation_check').
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_heat import law, voxel, v2_adapter  # noqa: E402

RADIOMETERS = {"RAD_X102": 102.0, "RAD_X105": 105.0, "RAD_X108": 108.0, "RAD_X080": 80.0, "RAD_X090": 90.0}
REQUESTED = ("RAD_X102", "RAD_X105", "RAD_X108")
WINDOW = (40.0, 84.0)
THR = 20.0
Z_R = 1.5


def read_csv(p):
    lines = Path(p).read_text().splitlines()
    head = [h.strip() for h in lines[1].split(",")]
    a = np.array([[float(v) for v in l.split(",")] for l in lines[2:] if l.strip()])
    return head, a


def main(run_dir, vol_npz, out, run_a_devc=None):
    run = Path(run_dir)
    dh, dv = read_csv(next(run.glob("*_devc.csv")))
    hh, hv = read_csv(next(run.glob("*_hrr.csv")))
    t_d = dv[:, 0]
    w = (hv[:, 0] >= WINDOW[0]) & (hv[:, 0] <= WINDOW[1])
    chi = float(-hv[w, hh.index("Q_RADI")].sum() / hv[w, hh.index("HRR")].sum())
    z = np.load(vol_npz)
    h, t, x, y, zz = z["hrrpuv_kw_m3"], z["time_s"], z["x_m"], z["y_m"], z["z_m"]
    frames = [k for k in range(len(t)) if WINDOW[0] <= t[k] <= WINDOW[1]]
    mets = {k: voxel.front_metrics(h[k].astype(float), x, y, zz, threshold_kw_m3=THR) for k in frames}
    R = voxel.spread_rate([t[k] for k in frames], [mets[k]["le"] for k in frames])
    samples = []
    for k in frames:
        m = mets[k]; hk = h[k].astype(float)
        for name, xr in RADIOMETERS.items():
            d = xr - m["le"]
            if d < 1.0:
                continue
            fds = float(np.interp(t[k], t_d, dv[:, dh.index(name)]))
            qv = voxel.voxel_flux(hk, x, y, zz, (xr, 0.0, Z_R), chi=chi)
            a_half = m["effective_width"] / 2
            samples.append({
                "t": float(t[k]), "device": name, "requested": name in REQUESTED, "d": d, "fds": fds, "voxel": qv,
                "cf": law.line_flux(d, chi, m["intensity"] / R, R, m["depth"] / R, a_half),
                "cf_long": law.line_flux(d, chi, m["intensity"] / R, R, m["depth"] / R),
                "v2": v2_adapter.v2_flux(d, m["depth"], m["effective_width"], m["intensity"], receiver_height_m=Z_R)[0],
                "v2_lead": v2_adapter.v2_flux(d, m["depth"], m["effective_width"], m["intensity"], receiver_height_m=Z_R,
                                              panels=("leading",))[0],
                "le": m["le"], "intensity": m["intensity"], "depth": m["depth"], "width": m["effective_width"]})
    # binned summary
    bins = [(1, 3), (3, 5), (5, 8), (8, 12), (12, 16), (16, 22), (22, 30), (30, 40), (40, 60)]
    table = []
    for lo, hi in bins:
        r = [s for s in samples if lo <= s["d"] < hi]
        if not r:
            continue
        gm = lambda key: float(np.exp(np.mean([np.log(max(s[key], 1e-9)) for s in r])))
        rat = lambda key: float(np.exp(np.mean([np.log(s[key] / s["fds"]) for s in r if s["fds"] > 0])))
        table.append({"d_bin_m": [lo, hi], "n": len(r), "n_requested": sum(s["requested"] for s in r),
                      "fds_geomean": gm("fds"), "voxel_geomean": gm("voxel"), "cf_geomean": gm("cf"), "v2_geomean": gm("v2"),
                      "voxel_over_fds": rat("voxel"), "cf_over_fds": rat("cf"), "cf_long_over_fds": rat("cf_long"),
                      "v2_over_fds": rat("v2"), "v2_lead_over_fds": rat("v2_lead"),
                      "cap_over_fds": float(np.exp(np.mean([np.log(law.packet_frozen_cap() / s["fds"]) for s in r if s["fds"] > 0])))})
    res = {"run_dir": str(run), "volume_npz": str(vol_npz),
           "devc_sha256": hashlib.sha256(next(run.glob("*_devc.csv")).read_bytes()).hexdigest(),
           "radiant_fraction": chi, "spread_m_s": R, "window_s": WINDOW, "edge_threshold_kw_m3": THR,
           "mean_intensity_kw_m": float(np.mean([mets[k]["intensity"] for k in frames])),
           "mean_depth_m": float(np.mean([mets[k]["depth"] for k in frames])),
           "mean_width_m": float(np.mean([mets[k]["effective_width"] for k in frames])),
           "frozen_cap_kw_m2": law.packet_frozen_cap(), "bins": table, "samples": samples}
    if run_a_devc:
        ah, av = read_csv(run_a_devc)
        n = min(len(av), len(dv))
        res["run_A_vs_B_max_abs_diff"] = {c: float(np.max(np.abs(av[:n, ah.index(c)] - dv[:n, dh.index(c)])))
                                          for c in ["x", "D"] + list(RADIOMETERS)}
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    print("chi %.3f R %.3f I %.0f depth %.1f width %.1f samples %d" % (chi, R, res["mean_intensity_kw_m"], res["mean_depth_m"],
                                                                     res["mean_width_m"], len(samples)))
    for b in table:
        print("d %5s n %3d fds %7.2f vox %7.2f cf %7.2f v2 %7.2f | vox/fds %.2f cf/fds %.2f v2/fds %.2f v2lead/fds %.2f cap/fds %.3f" % (
            b["d_bin_m"], b["n"], b["fds_geomean"], b["voxel_geomean"], b["cf_geomean"], b["v2_geomean"], b["voxel_over_fds"],
            b["cf_over_fds"], b["v2_over_fds"], b["v2_lead_over_fds"], b["cap_over_fds"]))
    if run_a_devc:
        print("run A vs B max |diff|", res["run_A_vs_B_max_abs_diff"])


if __name__ == "__main__":
    main(*sys.argv[1:5])
