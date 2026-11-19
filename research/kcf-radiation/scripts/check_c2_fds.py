"""C2: the solid-flame method against FDS (model-to-model; PROTOCOL.md 8).

(i) C064 grass fire (research/kcf-heat/data/b2_fds_compare.json): run-mean I, R, W from that file; Byram flame
length from I; Albini tilt with the 4.6 m/s run wind read as a 10 m wind (as the protocol treats forecast winds) and,
as a variant, as the midflame wind; receiver 1.5 m, facing the fire; distances from the leading edge (= flame base).
Settings: baseline (1200 K, tilted), T 1090 / 1400 K, planar, worst angle, with and without transmissivity
(RH 40 %, 20 C, ASSUMED for the run). Each FDS bin is compared at its geometric-mean distance.

(ii) Local FDS runs (owner folder, read only): the plane-layer verification value against its analytic reference, and
the 240 kW propane strip (0.4 x 1.2 m) at 0.6 / 1.6 / 2.6 m, calm, against a solid flame of the Heskestad height.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from kcf_radiation import fire, radiation, tilt  # noqa: E402

LOCAL_FDS = Path("/Users/jp/Documents/Codex/2026-11-16/work-autonomously-on-wildfireguardian-s-flame/outputs/fds_study")


def c064():
    d = json.loads((ROOT / "research/kcf-heat/data/b2_fds_compare.json").read_text())
    I, W, R = d["mean_intensity_kw_m"], d["mean_width_m"], d["spread_m_s"]
    L = float(fire.flame_length_byram(I))
    wind = 4.6
    th10 = float(tilt.flame_tilt(wind, L))  # open grass, surface fire: WAF 0.4
    thmid = float(tilt.albini_tilt(wind, L))
    settings = {
        "baseline_tilt_from_U10": dict(theta=th10, T=1200.0, kind="tilted", tau=True),
        "tilt_from_midflame_U": dict(theta=thmid, T=1200.0, kind="tilted", tau=True),
        "T1090": dict(theta=th10, T=1090.0, kind="tilted", tau=True),
        "T1400": dict(theta=th10, T=1400.0, kind="tilted", tau=True),
        "planar": dict(theta=th10, T=1200.0, kind="planar", tau=True),
        "worst_angle": dict(theta=th10, T=1200.0, kind="tilted_max", tau=True),
        "no_tau": dict(theta=th10, T=1200.0, kind="tilted", tau=False),
    }
    rows = []
    for b in d["bins"]:
        lo, hi = b["d_bin_m"]
        dm = math.sqrt(lo * hi)
        rec = {"d_bin_m": [lo, hi], "d_eval_m": round(dm, 2), "n": b["n"], "fds": b["fds_geomean"],
               "voxel": b["voxel_geomean"], "old_closed_form": b["cf_geomean"]}
        for name, s in settings.items():
            fl = radiation.Flame(L, s["theta"], W)
            dd = max(dm, radiation.D_MIN + (L * math.sin(s["theta"]) if s["kind"] == "tilted" else 0.0))
            kw = dict(T_flame_K=s["T"], vf_kind=s["kind"], z_r=1.5)
            if s["tau"]:
                kw.update(rh_pct=40.0, T_air_C=20.0)
            q = radiation.flux(dd, fl, **kw)
            rec[name] = round(q, 3)
            rec[name + "_over_fds"] = round(q / b["fds_geomean"], 2)
            rec[name + "_over_voxel"] = round(q / b["voxel_geomean"], 2)
        rows.append(rec)
    worst_low = min(r["baseline_tilt_from_U10_over_fds"] for r in rows if r["d_bin_m"][0] >= 1)
    return {"inputs": {"I_kw_m": I, "W_m": W, "R_m_s": R, "L_byram_m": round(L, 3), "tilt_deg_U10": round(math.degrees(th10), 1),
                       "tilt_deg_midflame": round(math.degrees(thmid), 1), "wind_m_s": wind},
            "bins": rows, "pass_not_below_fds": worst_low >= 1.0, "min_ratio_baseline_over_fds": worst_low}


def local_runs():
    out = {"available": LOCAL_FDS.is_dir()}
    if not out["available"]:
        return out
    out["plane_layer"] = {"fds_kw_m2": 2.9181759, "analytic_kw_m2": 2.897,
                          "source": "outputs/fds_study/FDS_AND_OBSERVATIONS.md (canonical run, 100 angles)"}
    # propane strip, calm, interval ending 3 s
    devc = {}
    p = LOCAL_FDS / "burner_runs/burner_calm_devc.csv"
    with open(p) as f:
        rd = csv.reader(f)
        units, names = next(rd), next(rd)
        last = None
        for row in rd:
            last = row
    for n, v in zip(names, last):
        devc[n] = float(v)
    Q = 240.0  # kW
    D = math.sqrt(4 * 0.4 * 1.2 / math.pi)  # equivalent diameter of the 0.4 x 1.2 m strip
    Hf = 0.235 * Q ** 0.4 - 1.02 * D  # Heskestad (1983) mean flame height
    chi = 0.30
    res = []
    for x in (0.6, 1.6, 2.6):
        # solid flame: rectangle 1.2 m wide (strip long side facing the gauges? the gauges face the 0.4 m end; both),
        # emissive power from chi Q spread over the flame sheet area (both faces), McGuire view factor
        out_x = {"x_m": x}
        for width in (0.4, 1.2):
            A = 2 * width * Hf + 2 * 0.4 * Hf
            E = chi * Q / max(A, 1e-6)
            F = radiation.vf.planar_mcguire(x, Hf, width, 0.5)
            out_x["solid_flame_W%.1f" % width] = round(E * F, 3)
        out_x["point_source_Modak"] = round(chi * Q / (4 * math.pi * (x ** 2 + (Hf / 2 - 0.5) ** 2)), 3)
        res.append(out_x)
    out["burner_calm"] = {"heskestad_height_m": round(Hf, 3), "D_eq_m": round(D, 3), "devc_last_row": devc, "model": res,
                          "note": "FDS values are interval averages ending ~3 s, not grid-converged (owner study)."}
    return out


def main():
    res = {"c064": c064(), "local": local_runs()}
    (HERE / "data/c2_fds.json").write_text(json.dumps(res, indent=1))
    c = res["c064"]
    print("inputs", c["inputs"])
    for r in c["bins"]:
        print(r["d_bin_m"], "FDS %.2f voxel %.2f | base %.2f (x%.1f FDS, x%.2f voxel) planar %.2f max %.2f T1090 %.2f T1400 %.2f" % (
            r["fds"], r["voxel"], r["baseline_tilt_from_U10"], r["baseline_tilt_from_U10_over_fds"], r["baseline_tilt_from_U10_over_voxel"],
            r["planar"], r["worst_angle"], r["T1090"], r["T1400"]))
    print("pass (not below FDS at d>=1 m):", c["pass_not_below_fds"], "min ratio", c["min_ratio_baseline_over_fds"])
    print(json.dumps(res["local"].get("burner_calm", {}), indent=0)[:1500])


if __name__ == "__main__":
    main()
