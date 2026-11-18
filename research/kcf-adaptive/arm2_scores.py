"""Arm 2, stage A: per issue hour, the size each shape would have needed (PROTOCOL 3.3).

For every fire, horizon and issue hour: spread cells (kcf-margin 5 km rule), the circular score (= the
kcf-margin reach, checked against the committed value), and the wind-aligned scores for k in KS with the
issue-hour wind. Per-cell scores are kept for the cell-level miss rate. A second set of hour scores uses the
mean wind over (t, t+h] (ASSUMED PERFECT FORECAST, sensitivity only).

    python arm2_scores.py --work WORK --choi CHOI_DIR --wind derived/wind.csv.gz --out WORK/arm2_scores
"""
import argparse
import pickle
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

import fires as F
import margin as M

SEP_KM = 5.0


def wind_lookup(wind: pd.DataFrame, f: F.Fire):
    w = wind[wind.fire == f.name].set_index("t").sort_index()
    if w.empty:
        raise KeyError(f"no wind for {f.name}")
    return w


def score_fire(args):
    f, w = args
    t0 = time.time()
    out = dict(name=f.name, product=f.product, role=f.role, h={})
    hours = sorted(set(int(t) for h in F.HORIZONS for t in f.issue[h]))
    by_h = {h: set(int(t) for t in f.issue[h]) for h in F.HORIZONS}
    rec = {h: dict(t=[], n_spread=[], known=[], circ=[], dir=[], dir_pf=[], speed=[], dirfrom=[], speed_pf=[], dirfrom_pf=[], cells_circ=[],
                   cells_dir=[], ptr=[0], gate=[]) for h in F.HORIZONS}
    prev_n, dist = -1, None
    for t in hours:
        known = f.A <= t
        kn = int(known.sum())
        if kn != prev_n:
            dist = M.dist_km(known)
            prev_n = kn
        ts = f.time(t)
        sp, dr = float(w.speed_kmh[ts]), float(w.dir_from_deg[ts])
        d, e = M.downwind_unit(dr), float(M.eccentricity(sp))
        for h in F.HORIZONS:
            if t not in by_h[h]:
                continue
            new = (f.A > t) & (f.A <= t + h)
            r, dvals, mask = M.component_reach(known, new, (SEP_KM,), dist=dist)
            reach = r[SEP_KM]
            R = rec[h]
            if t in f.committed.get(h, {}):
                R["gate"].append(abs(reach - f.committed[h][t]))
            rc = np.argwhere(mask) if mask.any() else np.zeros((0, 2), int)
            cs = M.cell_scores(known, rc, d, e)                           # [4, n]
            nxt = w.loc[ts + pd.Timedelta(hours=1): ts + pd.Timedelta(hours=h)]
            if len(nxt) != h:
                raise ValueError(f"{f.name}: wind missing in ({ts}, +{h} h]")
            spf, dpf = M.mean_wind(nxt.speed_kmh.to_numpy(), nxt.dir_from_deg.to_numpy())
            cpf = M.cell_scores(known, rc, M.downwind_unit(dpf), float(M.eccentricity(spf)))
            R["t"].append(t); R["n_spread"].append(len(rc)); R["known"].append(kn); R["circ"].append(reach)
            R["dir"].append(cs.max(axis=1) if len(rc) else np.zeros(len(M.KS)))
            R["dir_pf"].append(cpf.max(axis=1) if len(rc) else np.zeros(len(M.KS)))
            R["speed"].append(sp); R["dirfrom"].append(dr); R["speed_pf"].append(spf); R["dirfrom_pf"].append(dpf)
            R["cells_circ"].append(dist[mask].astype(np.float32)); R["cells_dir"].append(cs.astype(np.float32))
            R["ptr"].append(R["ptr"][-1] + len(rc))
    for h in F.HORIZONS:
        R = rec[h]
        out["h"][h] = dict(
            t=np.array(R["t"], int), n_spread=np.array(R["n_spread"], int), known=np.array(R["known"], int),
            circ=np.array(R["circ"], float), dir=np.array(R["dir"], float).reshape(-1, len(M.KS)),
            dir_pf=np.array(R["dir_pf"], float).reshape(-1, len(M.KS)), speed=np.array(R["speed"], float),
            dirfrom=np.array(R["dirfrom"], float), speed_pf=np.array(R["speed_pf"], float),
            dirfrom_pf=np.array(R["dirfrom_pf"], float), ptr=np.array(R["ptr"], int),
            cells_circ=np.concatenate(R["cells_circ"]) if R["cells_circ"] else np.zeros(0, np.float32),
            cells_dir=np.concatenate(R["cells_dir"], axis=1) if R["cells_dir"] else np.zeros((len(M.KS), 0), np.float32),
            gate_max_abs_diff=float(max(R["gate"])) if R["gate"] else None, gate_n=len(R["gate"]),
            complete=np.array([f.complete.get(h, {}).get(t, True) for t in R["t"]], bool))
    out["seconds"] = time.time() - t0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--choi", required=True, type=Path)
    ap.add_argument("--wind", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--fires", nargs="*")
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    wind = pd.read_csv(a.wind, parse_dates=["t"])
    kr, skipped = F.choi_kr(a.choi)
    allf = F.gofer(a.work) + kr + [F.det()]
    if a.fires:
        allf = [f for f in allf if f.name in a.fires]
    todo = [f for f in allf if not (a.out / f"{f.name.replace(' ', '_')}.pkl").exists()]
    todo.sort(key=lambda f: -int((f.A != F.NEVER).sum()) * len(f.issue[5]))
    jobs = [(f, wind_lookup(wind, f)) for f in todo]
    with ProcessPoolExecutor(a.jobs) as ex:
        for res in ex.map(score_fire, jobs, chunksize=1):
            pickle.dump(res, open(a.out / f"{res['name'].replace(' ', '_')}.pkl", "wb"))
            g = [res["h"][h]["gate_max_abs_diff"] for h in F.HORIZONS]
            print(f"{res['name']:28s} hours {len(res['h'][5]['t'])}/{len(res['h'][8]['t'])} "
                  f"reach vs committed max |diff| {g} {res['seconds']:.0f}s", flush=True)
    (a.out / "skipped.txt").write_text("\n".join(f"{k}: {v}" for k, v in skipped.items()) + "\n")


if __name__ == "__main__":
    main()
