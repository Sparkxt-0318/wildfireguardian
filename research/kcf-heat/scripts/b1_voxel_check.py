"""B.1: front metrics and voxel-sum radiometers from csiro-volume-dt5-120.npz, compared with the closed form, v2 and
the frozen cap. Model-to-model only.

    python scripts/b1_voxel_check.py FIRE_DATA_DIR OUT.json

FIRE_DATA_DIR is the study package's fire-data/ (needs csiro-volume-dt5-120.npz and
full-5s-evidence/Case_C064_crude_cat_hrr.csv). Quasi-steady window 30..80 s (the head reaches the end of the
fuel bed, x = 100 m, at about 85 s in this run).
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_heat import law, voxel, v2_adapter  # noqa: E402

WINDOW = (30.0, 80.0)
DISTANCES = (3.0, 8.0, 12.0, 20.0, 30.0)
S_DISTANCES = (6.0, 8.0, 10.0, 14.0, 18.0, 26.0, 36.0)
THRESHOLDS = (5.0, 20.0, 100.0)
PRIMARY_THRESHOLD = 20.0
RECEIVER_Z = 1.5
BRIEF = {"chi": 0.32, "intensity_kw_m": 4400.0, "spread_m_s": 1.33, "depth_m": 12.0, "half_width_m": 29.5,
         "voxel_kw_m2": {"3": 21.0, "8": 13.0, "12": 9.4, "20": 5.6, "30": 3.4}}


def radiant_fraction(hrr_csv):
    a = np.genfromtxt(hrr_csv, delimiter=",", skip_header=2)
    t, hrr, qr = a[:, 0], a[:, 1], a[:, 3]
    w = (t >= WINDOW[0]) & (t <= WINDOW[1])
    return float(-qr[w].sum() / hrr[w].sum()), {"rows": int(w.sum()), "min_ratio": float((-qr[w] / hrr[w]).min()),
                                                 "max_ratio": float((-qr[w] / hrr[w]).max())}


def main(fire_data, out):
    fire_data = Path(fire_data)
    npz = fire_data / "csiro-volume-dt5-120.npz"
    z = np.load(npz)
    h = z["hrrpuv_kw_m3"]; t = z["time_s"]; x = z["x_m"]; y = z["y_m"]; zz = z["z_m"]
    chi, chi_info = radiant_fraction(fire_data / "full-5s-evidence" / "Case_C064_crude_cat_hrr.csv")
    snaps = [k for k in range(len(t)) if WINDOW[0] <= t[k] <= WINDOW[1]]
    res = {"inputs": {"npz": str(npz), "npz_sha256": hashlib.sha256(npz.read_bytes()).hexdigest(),
                      "window_s": WINDOW, "snapshot_times_s": [float(t[k]) for k in snaps],
                      "receiver": {"y_m": 0.0, "z_m": RECEIVER_Z, "normal": [-1, 0, 0], "note": "faces the fire"}},
           "radiant_fraction": {"value": chi, **chi_info, "definition": "-sum(Q_RADI)/sum(HRR) over the window"},
           "by_threshold": {}}
    for thr in THRESHOLDS:
        mets = [voxel.front_metrics(h[k].astype(float), x, y, zz, threshold_kw_m3=thr) for k in snaps]
        R = voxel.spread_rate([t[k] for k in snaps], [m["le"] for m in mets])
        rows = []
        for k, m in zip(snaps, mets):
            hk = h[k].astype(float)
            a_half = m["effective_width"] / 2.0
            t_r = m["depth"] / R
            for d in DISTANCES:
                xr = m["le"] + d
                qv = voxel.voxel_flux(hk, x, y, zz, (xr, 0.0, RECEIVER_Z), chi=chi)
                s_geom = xr - m["centroid"]
                rows.append({"t": float(t[k]), "d": d, "voxel": qv,
                             "cf_long": law.line_flux(d, chi, m["intensity"] / R, R, t_r),
                             "cf_finite": law.line_flux(d, chi, m["intensity"] / R, R, t_r, a_half),
                             "cf_centroid_finite": law.line_flux_s(s_geom, chi, m["intensity"], a_half),
                             "s_centroid": s_geom, "le_minus_centroid": m["le"] - m["centroid"],
                             "v2_facing": v2_adapter.v2_flux(d, m["depth"], m["effective_width"], m["intensity"],
                                                             receiver_height_m=RECEIVER_Z)[0]})
        summ = {}
        for d in DISTANCES:
            r = [q for q in rows if q["d"] == d]
            g = lambda key: float(np.mean([q[key] for q in r]))
            ratio = lambda key: [float(np.min([q[key] / q["voxel"] for q in r])), float(np.mean([q[key] / q["voxel"] for q in r])),
                                 float(np.max([q[key] / q["voxel"] for q in r]))]
            summ[str(int(d))] = {"voxel_mean": g("voxel"), "voxel_min": float(min(q["voxel"] for q in r)),
                                 "voxel_max": float(max(q["voxel"] for q in r)),
                                 "cf_finite_mean": g("cf_finite"), "cf_long_mean": g("cf_long"), "v2_mean": g("v2_facing"),
                                 "ratio_cf_finite_min_mean_max": ratio("cf_finite"),
                                 "ratio_cf_long_min_mean_max": ratio("cf_long"),
                                 "ratio_cf_centroid_min_mean_max": ratio("cf_centroid_finite"),
                                 "ratio_v2_min_mean_max": ratio("v2_facing")}
        mean = lambda key: float(np.mean([m[key] for m in mets]))
        res["by_threshold"][str(int(thr))] = {
            "spread_m_s": R, "intensity_kw_m": mean("intensity"), "depth_m": mean("depth"),
            "residence_s": mean("depth") / R, "flame_height_m": mean("flame_height"),
            "effective_width_m": mean("effective_width"), "le_minus_centroid_m": mean("le") - mean("centroid"),
            "energy_kj_m2": mean("intensity") / R, "per_distance": summ, "rows": rows,
            "per_snapshot": [{"t": float(t[k]), **m} for k, m in zip(snaps, mets)]}
    # threshold-free comparison: receivers placed at distance s from the HRR-weighted centroid
    srows = []
    for k in snaps:
        hk = h[k].astype(float)
        m = voxel.front_metrics(hk, x, y, zz, threshold_kw_m3=PRIMARY_THRESHOLD)
        for s in S_DISTANCES:
            xr = m["centroid"] + s
            if xr - m["le"] < 0.5:      # keep receivers ahead of the primary leading edge
                continue
            qv = voxel.voxel_flux(hk, x, y, zz, (xr, 0.0, RECEIVER_Z), chi=chi)
            srows.append({"t": float(t[k]), "s": s, "voxel": qv, "cf_long": law.line_flux_s(s, chi, m["intensity"]),
                          "cf_finite": law.line_flux_s(s, chi, m["intensity"], m["effective_width"] / 2)})
    res["centroid_referenced"] = {}
    for s in S_DISTANCES:
        r = [q for q in srows if q["s"] == s]
        if r:
            res["centroid_referenced"][str(s)] = {
                "n": len(r), "voxel_mean": float(np.mean([q["voxel"] for q in r])),
                "ratio_cf_finite_mean": float(np.mean([q["cf_finite"] / q["voxel"] for q in r])),
                "ratio_cf_long_mean": float(np.mean([q["cf_long"] / q["voxel"] for q in r]))}
    # the brief's first-pass parameters, evaluated against its own voxel numbers and against ours
    b = BRIEF; prim = res["by_threshold"][str(int(PRIMARY_THRESHOLD))]["per_distance"]
    res["brief_check"] = {}
    for d in DISTANCES:
        cf = law.line_flux(d, b["chi"], b["intensity_kw_m"] / b["spread_m_s"], b["spread_m_s"], b["depth_m"] / b["spread_m_s"], b["half_width_m"])
        v2 = v2_adapter.v2_flux(d, b["depth_m"], 2 * b["half_width_m"], b["intensity_kw_m"], receiver_height_m=RECEIVER_Z)[0]
        res["brief_check"][str(int(d))] = {"cf_brief_params": cf, "v2_brief_params": v2,
                                           "brief_voxel": b["voxel_kw_m2"][str(int(d))], "our_voxel_thr20": prim[str(int(d))]["voxel_mean"],
                                           "cf_over_brief_voxel": cf / b["voxel_kw_m2"][str(int(d))],
                                           "v2_over_brief_voxel": v2 / b["voxel_kw_m2"][str(int(d))]}
    res["frozen_cap_packet_kw_m2"] = law.packet_frozen_cap()
    Path(out).write_text(json.dumps(res, indent=1) + "\n")
    p = res["by_threshold"][str(int(PRIMARY_THRESHOLD))]
    print(json.dumps({k: p[k] for k in ("spread_m_s", "intensity_kw_m", "depth_m", "residence_s", "flame_height_m",
                                        "effective_width_m", "le_minus_centroid_m")}, indent=1))
    print("chi", chi)
    for thr, pt in res["by_threshold"].items():
        print("thr", thr, " ".join("%s:%.1f cf/v=%.2f cflong/v=%.2f v2/v=%.2f" % (d, v["voxel_mean"], v["ratio_cf_finite_min_mean_max"][1],
                                                                            v["ratio_cf_long_min_mean_max"][1], v["ratio_v2_min_mean_max"][1])
                                   for d, v in pt["per_distance"].items()))
    print("centroid", json.dumps(res["centroid_referenced"]))
    print("brief", json.dumps(res["brief_check"]))


if __name__ == "__main__":
    main(*sys.argv[1:3])
