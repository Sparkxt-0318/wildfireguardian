"""Twin experiment runner (PROTOCOL.md section 3). Usage:
  python3 run_twin.py check            # the twin's system-raster builder equals build_example_raster's committed raster (real discs)
  python3 run_twin.py make WORK        # truth, detections, rasters for the 24 pairs (seeds 0-11 x two issue times)
  python3 run_twin.py run WORK         # roadlayer on truth / system / control rasters, resumable
  python3 run_twin.py score WORK OUT   # tables -> OUT/twin_cells.csv, twin_places.csv, twin_summary.json
"""
from __future__ import annotations

import csv, json, math, subprocess, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO / "research/kcf-replay")); sys.path.insert(0, str(REPO / "product/wfg-roadlayer"))
import measured_arms as MA  # noqa: E402
import twin_lib as TL  # noqa: E402
from wfg_roadlayer import geotiff  # noqa: E402

SEEDS = list(range(12))
T_IGN = datetime(2025, 3, 24, 12, 0, tzinfo=timezone.utc)
ISSUE_OFFSETS_H = (24, 36)
HORIZON_S = 8 * 3600
REGION = "yeongdeok_2025"
ARMS = ("truth", "system", "control")


def system_minutes(discs, T):
    """Re-implementation of product/wfg-roadlayer/examples/build_example_raster.py on the roadlayer lattice. Returns [H,W] south-up minutes."""
    r5, r8, cls, info = MA.curve("MEASURED", discs, T, HORIZON_S // 3600)
    sel = [x for x in discs if x["t"] < T]
    CX, CY = TL.cell_xy()
    cx, cy = CX.ravel(), CY.ravel()
    d = np.full(cx.shape, np.inf)
    if sel:
        Xd = np.array([x["x"] for x in sel]); Yd = np.array([x["y"] for x in sel]); Rd = np.array([x["r_m"] for x in sel])
        for i in range(0, len(sel), 2000):
            dd = np.sqrt((cx[:, None] - Xd[None, i:i + 2000]) ** 2 + (cy[:, None] - Yd[None, i:i + 2000]) ** 2) - Rd[None, i:i + 2000]
            d = np.minimum(d, np.maximum(dd, 0).min(1))
    minutes = np.full(cx.shape, np.inf)
    for k in range(cx.size):
        if np.isfinite(d[k]):
            s = MA.closure_s(r5, r8, float(d[k]))
            if s <= HORIZON_S:
                minutes[k] = int(math.ceil(s)) / 60.0
    return minutes.reshape(TL.H, TL.W), {"class": cls, "R5_km": r5 / 1000, "R8_km": r8 / 1000, "discs_before_T": len(sel)}


def truth_minutes(arrival_s, T):
    rel = arrival_s - (T - T_IGN).total_seconds()
    m = rel / 60.0
    m = np.where(m > HORIZON_S / 60.0, np.inf, m)
    return m


def write_tif(path, minutes, T, source):
    grid = minutes[::-1]  # north-up
    md = {"WFG_ISSUE_TIME": T.strftime("%Y-%m-%dT%H:%M:%SZ"), "WFG_HORIZON_MIN": "480", "WFG_UNITS": "minutes", "WFG_SOURCE": source}
    geotiff.write(path, grid, (TL.RES, 0.0, TL.X0, 0.0, -TL.RES, TL.Y0 + TL.RES * TL.H), 5179, nodata=float("nan"), metadata=md)


def check():
    T = datetime(2025, 3, 25, 9, 0, tzinfo=timezone.utc)
    discs = [dict(x, t=datetime.fromisoformat(x["t_utc"])) for x in json.loads((REPO / "research/kcf-replay/fire_discs.json").read_text())["discs"]]
    # the committed example raster covers x0 1093875, 214 x 67, the same lattice as TL
    m, info = system_minutes(discs, T)
    ref = geotiff.read(REPO / "product/wfg-roadlayer/examples/fire_arrival_20250325T0900Z_MEASURED_8h.tif").data[::-1]
    same = np.array_equal(np.isinf(m), np.isinf(ref)) and np.allclose(m[np.isfinite(m)], ref[np.isfinite(ref)], atol=0, rtol=0)
    print("builder equals committed example raster:", same, info, "finite cells", int(np.isfinite(m).sum()))
    if not same:
        raise SystemExit("MISMATCH: the twin's system-raster builder differs from build_example_raster; stop")


def pairs():
    return [(s, h) for s in SEEDS for h in ISSUE_OFFSETS_H]


def make(work):
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    sch = TL.pass_schedule(REPO / "research/kcf-replay/fire_discs.json")
    meta = {"schedule_min_utc": sch, "PARAMS": TL.PARAMS, "DET": TL.DET, "pairs": []}
    for seed in SEEDS:
        tr = TL.simulate(seed, T_IGN)
        arr = tr["arrival_s"]
        np.save(work / f"truth_arrival_s_seed{seed}.npy", arr)
        t_end = T_IGN + timedelta(hours=max(ISSUE_OFFSETS_H))
        dets = {"system": TL.detections(arr, T_IGN, t_end, sch, seed, perfect=False),
                "control": TL.detections(arr, T_IGN, t_end, sch, seed, perfect=True)}
        for h in ISSUE_OFFSETS_H:
            T = T_IGN + timedelta(hours=h)
            tag = f"s{seed}_h{h}"
            write_tif(work / f"truth_{tag}.tif", truth_minutes(arr, T), T, f"twin truth seed {seed}")
            row = {"seed": seed, "issue_offset_h": h, "issue_utc": T.strftime("%Y-%m-%dT%H:%M:%SZ"), "v0_kmh": tr["v0_kmh"],
                   "wind_deg": tr["wind_deg"], "shift_deg": tr["shift_deg"], "t_shift_h": tr["t_shift_h"], "ignition_cell": tr["ignition_cell"]}
            for arm in ("system", "control"):
                m, info = system_minutes(dets[arm], T)
                write_tif(work / f"{arm}_{tag}.tif", m, T, f"twin {arm} (detections only) seed {seed}")
                row[arm] = dict(info, n_discs_total=len(dets[arm]))
            tm = truth_minutes(arr, T)
            row["truth_cells_burning_at_T"] = int((tm <= 0).sum()); row["truth_cells_reach_within_8h"] = int(((tm > 0) & np.isfinite(tm)).sum())
            meta["pairs"].append(row)
            print(tag, row["system"], row["truth_cells_burning_at_T"], row["truth_cells_reach_within_8h"], flush=True)
    (work / "make.json").write_text(json.dumps(meta, indent=1, default=str))


def run(work, arms=ARMS):
    work = Path(work)
    for seed, h in pairs():
        T = T_IGN + timedelta(hours=h); tag = f"s{seed}_h{h}"
        for arm in arms:
            out = work / "rl" / f"{arm}_{tag}"
            if (out / "run.json").exists():
                continue
            t = time.time()
            iso = T.strftime("%Y-%m-%dT%H:%M+00:00")
            cmd = [sys.executable, str(REPO / "product/wfg-roadlayer/roadlayer.py"), "run", "--region", REGION, "--issue-time", iso, "--as-of", iso,
                   "--raster", str(work / f"{arm}_{tag}.tif"), "--out", str(out), "--workers", "4"]
            p = subprocess.run(cmd, capture_output=True, text=True)
            (work / "rl").mkdir(exist_ok=True)
            (work / "rl" / f"{arm}_{tag}.log").write_text(p.stdout + "\n" + p.stderr)
            print(arm, tag, "exit", p.returncode, round(time.time() - t), "s", flush=True)


def read_places(d):
    f = next((Path(d) / "en").glob("villages_road_cut_*.csv"))
    rows = list(csv.DictReader(open(f, encoding="utf-8-sig")))
    out = {}
    for r in rows:
        def num(k):
            v = r.get(k, "")
            return float(v) if v not in ("", None) else None
        out[r["place id"]] = {"name": r["village or facility"], "status": r["road status"], "refusal": r["refusal reason"],
                              "cut_s": num("road cut (s after issue)"), "arrival_s": num("fire arrival (s after issue)"),
                              "leave_by_s": num("leave by (s after issue)"), "stage_now": r["stage now"]}
    return out


def score(work, out):
    work, out = Path(work), Path(out); out.mkdir(parents=True, exist_ok=True)
    meta = json.loads((work / "make.json").read_text())
    cells, places = [], []
    for p in meta["pairs"]:
        seed, h = p["seed"], p["issue_offset_h"]; T = T_IGN + timedelta(hours=h); tag = f"s{seed}_h{h}"
        arr = np.load(work / f"truth_arrival_s_seed{seed}.npy"); tm = truth_minutes(arr, T)
        burning = tm <= 0
        reach = (tm > 0) & np.isfinite(tm)
        for arm in ("system", "control"):
            sm = geotiff.read(work / f"{arm}_{tag}.tif").data[::-1]
            err = sm - tm
            fin = reach & np.isfinite(sm)
            late = reach & (~np.isfinite(sm) | (sm > tm))
            late15 = reach & (~np.isfinite(sm) | (sm - tm >= 15)); late60 = reach & (~np.isfinite(sm) | (sm - tm >= 60))
            false_reach = ~burning & ~reach & np.isfinite(sm)  # system finite <= 8 h, truth later or never
            sys_known_not_burning = (~burning) & np.isfinite(sm) & (sm <= 0)
            e = err[fin]
            cells.append({"seed": seed, "issue_offset_h": h, "arm": arm, "true_reach_cells": int(reach.sum()), "late": int(late.sum()),
                          "late_ge15": int(late15.sum()), "late_ge60": int(late60.sum()), "system_absent": int((reach & ~np.isfinite(sm)).sum()),
                          "finite_both": int(fin.sum()), "err_median_min": float(np.median(e)) if e.size else None,
                          "err_p10_min": float(np.percentile(e, 10)) if e.size else None, "err_p90_min": float(np.percentile(e, 90)) if e.size else None,
                          "false_reach_cells": int(false_reach.sum()), "system_known_but_truth_not_burning": int(sys_known_not_burning.sum()),
                          "truth_burning_at_T": int(burning.sum())})
        T_res = read_places(work / "rl" / f"truth_{tag}")
        for arm in ("system", "control"):
            S_res = read_places(work / "rl" / f"{arm}_{tag}")
            for pid, t in T_res.items():
                s = S_res.get(pid)
                if s is None:
                    continue
                refused = bool(t["refusal"] or s["refusal"])
                t_cut = t["cut_s"] is not None; s_cut = s["cut_s"] is not None
                row = {"seed": seed, "issue_offset_h": h, "arm": arm, "place": pid, "name": t["name"], "refused": refused,
                       "truth_status": t["status"], "system_status": s["status"], "truth_cut_s": t["cut_s"], "system_cut_s": s["cut_s"],
                       "truth_arrival_s": t["arrival_s"], "system_arrival_s": s["arrival_s"]}
                row["true_state"] = "REFUSED" if refused else ("CUT" if t_cut else "NOT_CUT")
                row["system_state"] = "REFUSED" if refused else ("CUT" if s_cut else "NOT_CUT")
                places.append(row)
    cols = list(cells[0].keys())
    with open(out / "twin_cells.csv", "w", newline="") as f:
        w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(cells)
    with open(out / "twin_places.csv", "w", newline="") as f:
        w = csv.DictWriter(f, list(places[0].keys())); w.writeheader(); w.writerows(places)
    print(len(cells), "cell rows", len(places), "place rows")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "check": check()
    elif cmd == "make": make(sys.argv[2])
    elif cmd == "run": run(sys.argv[2], tuple(sys.argv[3].split(",")) if len(sys.argv) > 3 else ARMS)
    elif cmd == "score": score(sys.argv[2], sys.argv[3])
