"""Per-fire tables on the four reconstructed KFS fires (PROTOCOL.md 5 and 7.1): every burned 375 m cell gets R, fuel,
intensity, crown, flame length, tilt, height and d* at the three thresholds (baseline; fuel low and high), and the
FRP cross-check (Wooster et al. 2005) for detections within 1 h of the cell's arrival.

    python scripts/run_fires.py --env ENV_REGIONS --firms-2025 DIR --firms-2022-23 DIR --out DIR
"""
from __future__ import annotations

import argparse
import gzip
import csv
import json
import math
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_radiation import envdata, frp, fuels, model, ros  # noqa: E402
from kcf_radiation.protocol import BASELINE, R_MAX_M_S, R_MIN_M_S, SENSITIVITY_SETTINGS, THRESHOLDS  # noqa: E402

FIRES = {"KFS_01": ("Uiseong 2025", 2025), "KFS_02": ("Uljin 2022", 2022), "KFS_05": ("Hongseong 2023", 2023),
         "KFS_11": ("Miryang 2022", 2022)}


def q(v, p):
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    return [round(float(x), 2) for x in np.percentile(v, p)] if v.size else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", type=Path, required=True)
    ap.add_argument("--firms-2025", type=Path, required=True)
    ap.add_argument("--firms-2022-23", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    summary = {}
    for k, (name, year) in FIRES.items():
        env = envdata.Environment(a.env / k)
        t_s = env.arrival_h * 3600.0
        R, rinfo = ros.rate_of_spread(t_s, env.res, R_MIN_M_S, R_MAX_M_S)
        rr, cc = np.nonzero(np.isfinite(t_s))
        lc = env.landcover[rr, cc]
        groups = np.array([fuels.group_of(v) if np.isfinite(v) else "grass" for v in lc])
        U = np.zeros(rr.size); RH = np.zeros(rr.size); TA = np.zeros(rr.size)
        when = [env.t0 + timedelta(hours=float(env.arrival_h[r, c])) for r, c in zip(rr, cc)]
        for i, (r, c, t) in enumerate(zip(rr, cc, when)):
            U[i] = env.at_hour("wind_speed_10m", t)[0][r, c]
            RH[i] = env.at_hour("relative_humidity_2m", t)[0][r, c]
            TA[i] = env.at_hour("temperature_2m", t)[0][r, c]
        U = np.nan_to_num(U, nan=float(np.nanmedian(U))); RH = np.nan_to_num(RH, nan=50.0); TA = np.nan_to_num(TA, nan=10.0)
        Rc = R[rr, cc]
        res = {}
        for sname, st in {"baseline": BASELINE, "fuel_low": SENSITIVITY_SETTINGS["fuel_low"],
                          "fuel_high": SENSITIVITY_SETTINGS["fuel_high"]}.items():
            res[sname] = model.Evaluator(st).cells(Rc, groups, U, RH, TA)
        b = res["baseline"]
        fs = {"name": name, "cells": int(rr.size), "ros_info": rinfo, "ros_m_min_p10_50_90_99": q(Rc * 60, [10, 50, 90, 99]),
              "groups": {g: int((groups == g).sum()) for g in np.unique(groups)},
              "wind10_p10_50_90": q(U, [10, 50, 90])}
        for sname, r in res.items():
            d = {"crown_share": round(float(r["crown"].mean()), 3),
                 "I_total_kw_m_p10_50_90_99": q(r["I_total"], [10, 50, 90, 99]),
                 "L_m_p10_50_90_99": q(r["L"], [10, 50, 90, 99]), "H_m_p50_90": q(r["H"], [50, 90])}
            for th in THRESHOLDS:
                ds = r["dstar_%g" % th]
                d["dstar_%g_m_p50_90_99_max" % th] = q(ds, [50, 90, 99, 100])
                d["share_dstar_%g_below_375m" % th] = round(float((ds < 375.0).mean()), 4)
                d["lead_%g_s_p50_90_99" % th] = q(ds / Rc, [50, 90, 99])
            fs[sname] = d
        # per-cell table (baseline)
        with gzip.open(a.out / ("cells_%s.csv.gz" % k), "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(["row", "col", "arrival_h", "ros_m_min", "lc", "group", "wind10", "rh", "I_surface", "crown", "cfb",
                        "I_total", "L", "tilt_deg", "H"] + ["dstar_%g" % th for th in THRESHOLDS])
            for i in range(rr.size):
                w.writerow([int(rr[i]), int(cc[i]), round(float(env.arrival_h[rr[i], cc[i]]), 3), round(float(Rc[i]) * 60, 3),
                            None if not np.isfinite(lc[i]) else int(lc[i]), groups[i], round(float(U[i]), 2), round(float(RH[i]), 1),
                            round(float(b["I_surface"][i]), 1), int(b["crown"][i]), round(float(b["cfb"][i]), 3),
                            round(float(b["I_total"][i]), 1), round(float(b["L"][i]), 2), round(math.degrees(float(b["theta"][i])), 1),
                            round(float(b["H"][i]), 2)] + [round(float(b["dstar_%g" % th][i]), 2) for th in THRESHOLDS])
        # FRP
        files = sorted((a.firms_2025 if year == 2025 else a.firms_2022_23).glob("*_%d_Republic_of_Korea.csv" % year))
        det = frp.read_firms(files)
        xs, ys = tr.transform([d["lon"] for d in det], [d["lat"] for d in det])
        dr, dc = env.cell_index(np.array(xs), np.array(ys))
        pos = {(int(r), int(c)): i for i, (r, c) in enumerate(zip(rr, cc))}
        ratios = {s: [] for s in res}
        rows = []
        for d, r, c in zip(det, dr, dc):
            i = pos.get((int(r), int(c)))
            if i is None:
                continue
            ta = env.t0 + timedelta(hours=float(env.arrival_h[r, c]))
            if abs((d["t"] - ta).total_seconds()) > 3600 or d["frp_mw"] <= 0:
                continue
            Ifrp, Lf = frp.intensity_from_frp(d["frp_mw"], d["scan_km"], d["track_km"])
            for s in res:
                ratios[s].append(float(res[s]["I_total"][i]) / Ifrp)
            rows.append({"sat": d["sat"], "inst": d["instrument"], "frp_mw": d["frp_mw"], "I_frp": round(Ifrp, 1),
                         "I_model": round(float(b["I_total"][i]), 1), "group": groups[i], "crown": bool(b["crown"][i])})
        fs["frp"] = {"files": [p.name for p in files], "matched": len(rows),
                     "I_frp_kw_m_p10_50_90": q([r["I_frp"] for r in rows], [10, 50, 90])}
        for s, v in ratios.items():
            fs["frp"]["ratio_model_over_frp_%s_p10_50_90" % s] = q(v, [10, 50, 90])
        if rows:
            vi = np.array([r["I_frp"] for r in rows]); vm = np.array([r["I_model"] for r in rows])
            ok = (vi > 0) & (vm > 0)
            fs["frp"]["spearman_log"] = round(float(np.corrcoef(np.argsort(np.argsort(vi[ok])), np.argsort(np.argsort(vm[ok])))[0, 1]), 3)
        summary[k] = fs
        print(k, json.dumps({kk: fs[kk] for kk in ("cells", "ros_m_min_p10_50_90_99")}), flush=True)
    (a.out / "fires_summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
