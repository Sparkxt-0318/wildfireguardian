"""Arm 2, stages B-D: sizes (static, ACI, tracker), flagged areas, scores and verdicts (PROTOCOL 3.4-3.8).

    python arm2_eval.py --work WORK --choi CHOI_DIR --scores WORK/arm2_scores --out derived/arm2.json
"""
import argparse
import hashlib
import json
import math
import pickle
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

import fires as F
import margin as M
from reach import clopper_pearson, conformal_R

ALPHAS = (0.02, 0.05, 0.10, 0.15, 0.20, 0.30)
HEAD = 0.10
SENS_ALPHAS = (0.10, 0.20)
GAMMA, GAMMAS_SENS, ETAS = 0.005, (0.02, 0.05), (0.05, 0.2)
DRAWS = 2000
BOOT, BOOT_SEED = 2000, 20261119
CELL_KM2 = M.CELL_KM ** 2
NK = len(M.KS)


def fname(name):
    return name.replace(" ", "_")


def sc(S, name, h, shape):
    """Hourly scores of a fire for a shape: 'circ', ('dir', ki) or ('pf', ki)."""
    d = S[name]["h"][h]
    if shape == "circ":
        return d["circ"]
    return d["dir" if shape[0] == "dir" else "dir_pf"][:, shape[1]]


# ------------------------------------------------------------------ areas (worker)
def area_worker(args):
    """requests: h -> list of (key, kind, ki, variant, q array over that fire's issue hours). Returns key -> cells."""
    f, d_by_h, requests = args
    out = {(h, key): np.full(len(d_by_h[h]["t"]), np.nan) for h in requests for key, *_ in requests[h]}
    index = {h: {int(t): i for i, t in enumerate(d_by_h[h]["t"])} for h in requests}
    hours = sorted(set(t for h in requests for t in index[h]))
    for t in hours:
        known = f.A <= t
        kn = int(known.sum())
        cache = {}
        for h in requests:
            i = index[h].get(t)
            if i is None:
                continue
            d = d_by_h[h]
            circ = [(key, q[i]) for key, kind, ki, var, q in requests[h] if kind == "circ" and np.isfinite(q[i])]
            if circ:
                areas = M.circle_areas(known, [q for _, q in circ])
                for (key, _), a in zip(circ, areas):
                    out[(h, key)][i] = a
            for key, kind, ki, var, q in requests[h]:
                if kind != "dir" or not np.isfinite(q[i]):
                    continue
                sp, dr = (d["speed"][i], d["dirfrom"][i]) if var == "obs" else (d["speed_pf"][i], d["dirfrom_pf"][i])
                ck = (round(float(q[i]), 9), ki, var if var == "obs" else (var, h))
                if ck not in cache:
                    z, _ = M.zone(known, float(q[i]), M.downwind_unit(dr), float(M.eccentricity(sp)), M.KS[ki])
                    cache[ck] = int(z.sum()) - kn
                out[(h, key)][i] = cache[ck]
    return f.name, out


def run_areas(fires, S, requests, cache_dir, tag, jobs):
    """requests: name -> h -> list. Cached on disk by content hash."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    res, todo = {}, []
    for f in fires:
        if f.name not in requests:
            continue
        hsh = hashlib.sha256()
        for h in sorted(requests[f.name]):
            for key, kind, ki, var, q in requests[f.name][h]:
                hsh.update(repr((h, key, kind, ki, var)).encode()); hsh.update(np.asarray(q, float).tobytes())
        path = cache_dir / f"{tag}_{fname(f.name)}_{hsh.hexdigest()[:16]}.pkl"
        if path.exists():
            res[f.name] = pickle.load(open(path, "rb"))
        else:
            todo.append((f, path))
    todo.sort(key=lambda fp: -int((fp[0].A != F.NEVER).sum()) * len(fp[0].issue[5]))
    with ProcessPoolExecutor(jobs) as ex:
        args = [(f, S[f.name]["h"], requests[f.name]) for f, _ in todo]
        for (f, path), (name, out) in zip(todo, ex.map(area_worker, args, chunksize=1)):
            pickle.dump(out, open(path, "wb"))
            res[name] = out
            print(f"  areas[{tag}] {name}", flush=True)
    return res


# ------------------------------------------------------------------ per-fire record of one arm
def fire_record(d, score, q, area, cells=None, sat=None):
    """d: stage-A dict of the fire/horizon; score, q, area: per issue hour. Only complete hours count."""
    ok = d["complete"] & np.isfinite(q)
    miss = (score > q) & ok
    rec = dict(hours=int(ok.sum()), miss_hours=int(miss.sum()), area_cells=float(np.nansum(area[ok])),
               burned_cells=int(d["n_spread"][ok].sum()), mean_q_km=float(np.mean(q[ok])) if ok.any() else None,
               saturated_hours=int(sat[ok].sum()) if sat is not None else 0)
    if cells is not None:
        cnt = np.diff(d["ptr"])
        qq = np.repeat(np.where(ok, q, np.inf), cnt)
        rec["missed_cells"] = int((cells > qq).sum())
    rec["miss"] = rec["miss_hours"] / rec["hours"] if rec["hours"] else None
    rec["op"] = rec["area_cells"] / rec["burned_cells"] if rec["burned_cells"] else None
    rec["mean_area_km2"] = rec["area_cells"] * CELL_KM2 / rec["hours"] if rec["hours"] else None
    return rec


def aggregate(recs):
    """recs: fire -> record. Fire-weighted and pooled summaries."""
    names = [n for n in sorted(recs) if recs[n]["hours"]]
    m = np.array([recs[n]["miss"] for n in names])
    op_names = [n for n in names if recs[n]["burned_cells"]]
    op = np.array([recs[n]["op"] for n in op_names])
    A = sum(recs[n]["area_cells"] for n in names)
    B = sum(recs[n]["burned_cells"] for n in names)
    H = sum(recs[n]["hours"] for n in names)
    out = dict(n_fires=len(names), hours=H, miss_fire_weighted=float(m.mean()),
               miss_ci95=list(clopper_pearson(float(m.sum()), len(names))),
               miss_pooled_hours=sum(recs[n]["miss_hours"] for n in names) / H,
               fires_with_any_miss=int((m > 0).sum()),
               op_fire_weighted=float(op.mean()), op_n_fires=len(op_names), op_pooled=A / B,
               mean_area_km2_fire_weighted=float(np.mean([recs[n]["mean_area_km2"] for n in names])),
               mean_q_km_fire_weighted=float(np.mean([recs[n]["mean_q_km"] for n in names])),
               saturated_hours=sum(recs[n]["saturated_hours"] for n in names))
    if all("missed_cells" in recs[n] for n in names):
        out["cell_miss_pooled"] = sum(recs[n]["missed_cells"] for n in names) / B
        out["cell_miss_fire_weighted"] = float(np.mean([recs[n]["missed_cells"] / recs[n]["burned_cells"]
                                                        for n in op_names]))
    return out


def boot_diff(recs_a, recs_b, rng_idx, names):
    """Paired fire bootstrap of fire-weighted differences a - b."""
    ma = np.array([recs_a[n]["miss"] for n in names]); mb = np.array([recs_b[n]["miss"] for n in names])
    oa = np.array([recs_a[n]["op"] for n in names]); ob = np.array([recs_b[n]["op"] for n in names])
    aa = np.array([recs_a[n]["mean_area_km2"] for n in names]); ab = np.array([recs_b[n]["mean_area_km2"] for n in names])
    out = {}
    for key, a, b in (("miss", ma, mb), ("op", oa, ob), ("mean_area_km2", aa, ab)):
        boot = a[rng_idx].mean(1) - b[rng_idx].mean(1)
        out[key] = dict(point=float(a.mean() - b.mean()), ci95=np.quantile(boot, [.025, .975]).tolist(),
                        fires_lower=int((a < b).sum()), fires_higher=int((a > b).sum()))
    out["op_relative"] = dict(point=float(oa.mean() / ob.mean() - 1),
                              ci95=np.quantile(oa[rng_idx].mean(1) / ob[rng_idx].mean(1) - 1, [.025, .975]).tolist())
    return out


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--choi", required=True, type=Path)
    ap.add_argument("--scores", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    t_start = time.time()
    kr, skipped = F.choi_kr(a.choi)
    det = F.det()
    cal = F.gofer(a.work)
    allf = cal + kr + [det]
    S = {f.name: pickle.load(open(a.scores / f"{fname(f.name)}.pkl", "rb")) for f in allf}
    cal_names = sorted(f.name for f in cal)
    by_name = {f.name: f for f in allf}
    folds = cal_names + ["ALL"]
    train = {f: [g for g in cal_names if g != f] for f in cal_names}
    train["ALL"] = cal_names
    shapes = ["circ"] + [("dir", i) for i in range(NK)] + [("pf", i) for i in range(NK)]
    res = dict(meta=dict(alphas=ALPHAS, headline_alpha=HEAD, gamma=GAMMA, gammas_sensitivity=GAMMAS_SENS,
                         etas=ETAS, ks=M.KS, draws=DRAWS, bootstrap=BOOT, bootstrap_seed=BOOT_SEED,
                         calibration_fires=len(cal_names), korean_fires=[f.name for f in kr],
                         korean_not_tested=skipped))

    # ---- reach reproduction (stage A) and static sizes
    res["gate_reach"] = {n: {str(h): S[n]["h"][h]["gate_max_abs_diff"] for h in F.HORIZONS} for n in S}
    worst = max(v for d in res["gate_reach"].values() for v in d.values() if v is not None)
    if worst > 1e-9:
        raise SystemExit(f"GATE FAILED: reach differs from the committed values by {worst}")
    R = {}
    for fold in folds:
        for h in F.HORIZONS:
            for shp in shapes:
                arrs = [sc(S, g, h, shp) for g in train[fold]]
                for al in ALPHAS:
                    R[(fold, h, shp, al)] = conformal_R(arrs, al, DRAWS)[0]
    km = json.load(open(F.MARGIN / "numbers.json"))
    gate = {}
    for h in F.HORIZONS:
        row = next(r for r in km["table"] if r["fire_set"] == "all28" and r["h"] == h and r["cls"] == "all"
                   and r["alpha"] == HEAD)
        lofo = float(np.mean([np.mean(sc(S, f, h, "circ") > R[(f, h, "circ", HEAD)]) for f in cal_names]))
        gate[str(h)] = dict(R_km=R[("ALL", h, "circ", HEAD)], R_km_committed=row["R_km"], lofo_miss=lofo,
                            lofo_miss_committed=row["lofo_miss"])
        if abs(gate[str(h)]["R_km"] - row["R_km"]) > 1e-9 or abs(lofo - row["lofo_miss"]) > 1e-9:
            raise SystemExit(f"GATE FAILED: kcf-margin not reproduced at h={h}: {gate[str(h)]}")
    res["gate_kcf_margin"] = gate
    print("gate ok", gate, flush=True)

    # ---- choice of k per fold (h = 5, alpha = 0.10), without the held-out fire
    req = {}
    for g in cal_names:
        n = len(S[g]["h"][5]["t"])
        lst = []
        for ki in range(NK):
            for q in sorted(set(R[(fold, 5, ("dir", ki), HEAD)] for fold in folds if fold == "ALL" or fold != g)):
                lst.append((("sel", ki, round(q, 9)), "dir", ki, "obs", np.full(n, q)))
        for q in sorted(set(R[(fold, 5, "circ", HEAD)] for fold in folds if fold == "ALL" or fold != g)):
            lst.append((("selc", round(q, 9)), "circ", None, "obs", np.full(n, q)))
        req[g] = {5: lst}
    print("selection dilations per fire-hour:", {g: len(v[5]) for g, v in list(req.items())[:3]}, flush=True)
    sel_area = run_areas(cal, S, req, a.work / "arm2_area_cache", "sel", a.jobs)
    ksel, sel_table = {}, {}
    for fold in folds:
        means = []
        for ki in range(NK):
            q = round(R[(fold, 5, ("dir", ki), HEAD)], 9)
            means.append(float(np.mean([np.mean(sel_area[g][(5, ("sel", ki, q))]) for g in train[fold]])) * CELL_KM2)
        qc = round(R[(fold, 5, "circ", HEAD)], 9)
        circ = float(np.mean([np.mean(sel_area[g][(5, ("selc", qc))]) for g in train[fold]])) * CELL_KM2
        ksel[fold] = int(np.argmin(means))
        sel_table[fold] = dict(mean_area_km2_by_k=dict(zip(map(str, M.KS), means)), circle_mean_area_km2=circ,
                               chosen_k=M.KS[ksel[fold]],
                               static_q_km_by_k={str(M.KS[ki]): R[(fold, 5, ("dir", ki), HEAD)] for ki in range(NK)})
    res["k_selection"] = sel_table
    print("k chosen:", {f: M.KS[k] for f, k in ksel.items()}, flush=True)

    # ---- sizes for every arm
    arms = {}       # name -> h -> key -> dict(q, kind, ki, var, shape, sat)
    warm = {}       # (h, key) -> state on the KFS_01 Choi raster at the DET start hour

    def build(name, fold, h, a0=None, q0=None, suffix=""):
        d = S[name]["h"][h]
        t = d["t"]
        ki = ksel[fold]
        out = {}
        spec = dict(CIRC=("circ", "circ", None, "obs"), DIR=(("dir", ki), "dir", ki, "obs"),
                    DIRPF=(("pf", ki), "dir", ki, "pf"))
        for tag, (shp, kind, kk, var) in spec.items():
            score = np.where(d["complete"], sc(S, name, h, shp), np.nan)
            Qw = M.WeightedQuantile([sc(S, g, h, shp) for g in train[fold]])
            for al in ALPHAS:
                if tag == "DIRPF" and al != HEAD:
                    continue
                base = dict(kind=kind, ki=kk, var=var, shape=shp)
                qs = R[(fold, h, shp, al)]
                if not suffix:
                    out[(f"FIXED-{tag}", al, None)] = dict(base, q=np.full(len(t), qs))
                    out[(f"REF-{tag}", al, None)] = dict(base, q=np.full(len(t), Qw(1 - al)[0]))
                gammas = (GAMMA,) + (GAMMAS_SENS if (al in SENS_ALPHAS and tag != "DIRPF") else ())
                for gm in gammas:
                    key = (f"ADAPT-{tag}", al, gm)
                    a_start = None if a0 is None else a0.get((h, key))
                    q, au, sat = M.aci(t, score, h, al, gm, Qw, a0=a_start)
                    out[(key[0] + suffix, al, gm)] = dict(base, q=q, sat=sat, a=au)
                if al in SENS_ALPHAS and tag != "DIRPF" and math.isfinite(qs) and qs > 0:
                    for eta in ETAS:
                        key = (f"TRACK-{tag}", al, eta)
                        start = qs if q0 is None else q0.get((h, key), qs)
                        out[(key[0] + suffix, al, eta)] = dict(base, q=M.tracker(t, score, h, al, eta, start))
        return out

    for f in allf:
        fold = f.name if f.role == "calibration" else "ALL"
        arms[f.name] = {h: build(f.name, fold, h) for h in F.HORIZONS}
    # warm start of 25 March from the state reached on the KFS_01 Choi raster at the same UTC hour
    k1 = by_name["KFS_01"]
    a0, q0 = {}, {}
    for h in F.HORIZONS:
        t_det0 = det.time(det.issue[h][0])
        tt = [k1.time(t) for t in S["KFS_01"]["h"][h]["t"]]
        if t_det0 in tt:
            i = tt.index(t_det0)
            for key, v in arms["KFS_01"][h].items():
                if key[0].startswith("ADAPT"):
                    a0[(h, key)] = float(v["a"][i])
                if key[0].startswith("TRACK"):
                    q0[(h, key)] = float(v["q"][i])
    res["march25_warm_start_available"] = {str(h): any(k[0] == h for k in a0) for h in F.HORIZONS}
    for h in F.HORIZONS:
        arms[det.name][h].update(build(det.name, "ALL", h, a0=a0, q0=q0, suffix="|warm"))

    # ---- areas
    req = {}
    for f in allf:
        req[f.name] = {h: [(key, v["kind"], v["ki"], v["var"], v["q"]) for key, v in arms[f.name][h].items()]
                       for h in F.HORIZONS}
    areas = run_areas(allf, S, req, a.work / "arm2_area_cache", "arms", a.jobs)

    def record(name, h, key):
        v, d = arms[name][h][key], S[name]["h"][h]
        score = sc(S, name, h, v["shape"])
        cells = None
        if v["var"] == "obs":
            cells = d["cells_circ"] if v["kind"] == "circ" else d["cells_dir"][v["ki"]]
        return fire_record(d, score, v["q"], areas[name][(h, key)], cells, v.get("sat"))

    # ---- calibration fires, leave-one-fire-out
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, len(cal_names), size=(BOOT, len(cal_names)))
    reach_tab = pd.read_csv(F.MARGIN / "derived/gofer_reach.csv.gz")
    p3 = reach_tab[reach_tab.h == 3][["fire", "t_idx", "reach_km"]].rename(columns={"reach_km": "prior3"})
    p3["t_idx"] += 3
    lofo = {}
    keys = sorted(arms[cal_names[0]][5], key=lambda k: (k[0], k[1], k[2] or 0))
    for h in F.HORIZONS:
        lofo[str(h)] = {}
        recs = {key: {n: record(n, h, key) for n in cal_names} for key in keys}
        # fastest decile of prior-3 h spread (kcf-margin definition i)
        rows = reach_tab[reach_tab.h == h].merge(p3, on=["fire", "t_idx"], how="left")
        thr = float(np.quantile(rows.prior3.dropna(), 0.9))
        fast = {n: set(g.t_idx[g.prior3 >= thr].astype(int)) for n, g in rows.groupby("fire")}
        for key in keys:
            arm, al, par = key
            if not all(recs[key][n]["mean_q_km"] is not None and math.isfinite(recs[key][n]["mean_q_km"])
                       for n in cal_names):
                lofo[str(h)][f"{arm}|{al}|{par}"] = dict(not_attainable="static size is infinite with 27 fires at this target")
                continue
            ag = aggregate(recs[key])
            base = recs.get(("FIXED-CIRC", al, None))
            if base and key != ("FIXED-CIRC", al, None) and all(base[n]["mean_q_km"] is not None and
                                                                 math.isfinite(base[n]["mean_q_km"]) for n in cal_names):
                ag["vs_FIXED_CIRC"] = boot_diff(recs[key], base, idx, cal_names)
            fm = []
            for n in cal_names:
                d = S[n]["h"][h]
                selh = np.array([int(t) in fast.get(n, ()) for t in d["t"]])
                if selh.any():
                    v = arms[n][h][key]
                    fm.append(float(np.mean(sc(S, n, h, v["shape"])[selh] > v["q"][selh])))
            ag["fastest_decile_prior3"] = dict(threshold_km=thr, n_fires=len(fm), miss_fire_weighted=float(np.mean(fm)),
                                               ci95=list(clopper_pearson(float(np.sum(fm)), len(fm))))
            ag["per_fire"] = {n: {k: recs[key][n][k] for k in ("hours", "miss", "op", "mean_area_km2", "mean_q_km",
                                                               "saturated_hours")} for n in cal_names}
            lofo[str(h)][f"{arm}|{al}|{par}"] = ag
        # over-prediction at equal realised miss rate, against the FIXED-CIRC curve
        eq = {}
        bal = [al for al in ALPHAS if "miss_fire_weighted" in lofo[str(h)][f"FIXED-CIRC|{al}|None"]]
        bm = np.array([[recs[("FIXED-CIRC", al, None)][n]["miss"] for n in cal_names] for al in bal])
        bo = np.array([[recs[("FIXED-CIRC", al, None)][n]["op"] for n in cal_names] for al in bal])

        def base_op_at(m, sel=None):
            x = bm.mean(1) if sel is None else bm[:, sel].mean(1)
            y = bo.mean(1) if sel is None else bo[:, sel].mean(1)
            o = np.argsort(x)
            if m < x[o][0] or m > x[o][-1]:
                return math.nan
            return float(np.interp(m, x[o], y[o]))
        for arm, par in (("FIXED-DIR", None), ("ADAPT-CIRC", GAMMA), ("ADAPT-DIR", GAMMA), ("REF-CIRC", None),
                         ("REF-DIR", None)):
            for al in (HEAD, 0.20):
                r = recs[(arm, al, par)]
                m = np.array([r[n]["miss"] for n in cal_names]); o = np.array([r[n]["op"] for n in cal_names])
                point = o.mean() - base_op_at(m.mean())
                boot = np.array([o[s].mean() - base_op_at(m[s].mean(), s) for s in idx])
                eq[f"{arm}|{al}"] = dict(arm_miss=float(m.mean()), arm_op=float(o.mean()),
                                         fixed_circ_op_at_same_miss=base_op_at(m.mean()),
                                         difference=None if math.isnan(point) else float(point),
                                         ci95=None if np.isnan(boot).mean() > 0.05 else np.nanquantile(boot, [.025, .975]).tolist(),
                                         resamples_outside_curve=float(np.isnan(boot).mean()))
        lofo[str(h)]["equal_miss_vs_FIXED_CIRC"] = eq
    res["lofo"] = lofo

    # ---- verdicts (PROTOCOL 3.7)
    verdict = {}
    for h in F.HORIZONS:
        base = lofo[str(h)][f"FIXED-CIRC|{HEAD}|None"]
        for arm, par in (("FIXED-DIR", None), ("ADAPT-CIRC", GAMMA), ("ADAPT-DIR", GAMMA)):
            ag = lofo[str(h)][f"{arm}|{HEAD}|{par}"]
            d = ag["vs_FIXED_CIRC"]
            lower_area = d["op"]["ci95"][1] < 0
            not_more_miss = ag["miss_fire_weighted"] <= base["miss_fire_weighted"]
            v = "helps" if lower_area and not_more_miss else ("trade-off, not help" if lower_area else "does not help")
            verdict[f"{arm}|{h}h"] = dict(verdict=v, op=ag["op_fire_weighted"], op_fixed_circ=base["op_fire_weighted"],
                                         op_difference=d["op"], miss=ag["miss_fire_weighted"],
                                         miss_fixed_circ=base["miss_fire_weighted"], miss_difference=d["miss"],
                                         equal_miss=lofo[str(h)]["equal_miss_vs_FIXED_CIRC"].get(f"{arm}|{HEAD}"))
    res["verdict_arm2"] = verdict

    # ---- Korean fires: counts only
    korea = {}
    show = [("FIXED-CIRC", None), ("FIXED-DIR", None), ("ADAPT-CIRC", GAMMA), ("ADAPT-DIR", GAMMA),
            ("ADAPT-CIRC", 0.05), ("ADAPT-DIR", 0.05), ("TRACK-CIRC", 0.2), ("TRACK-DIR", 0.2)]
    for h in F.HORIZONS:
        korea[str(h)] = {}
        for al in SENS_ALPHAS:
            for arm, par in show:
                key = (arm, al, par)
                per = {f.name: record(f.name, h, key) for f in kr}
                tot = {k: sum(per[n][k] for n in per) for k in ("hours", "miss_hours", "area_cells", "burned_cells",
                                                                "missed_cells", "saturated_hours")}
                tot["fires_with_any_miss"] = sum(1 for n in per if per[n]["miss_hours"])
                tot["area_per_burned_cell_pooled"] = tot["area_cells"] / tot["burned_cells"]
                korea[str(h)][f"{arm}|{al}|{par}"] = dict(total=tot, per_fire=per)
    res["korea"] = korea
    res["korea_chosen_k"] = M.KS[ksel["ALL"]]

    # ---- 25 March 2025, hour by hour
    m25 = {}
    for h in F.HORIZONS:
        d = S[det.name]["h"][h]
        rows = []
        cols = [("FIXED-CIRC", HEAD, None), ("FIXED-DIR", HEAD, None), ("ADAPT-CIRC", HEAD, GAMMA),
                ("ADAPT-DIR", HEAD, GAMMA), ("ADAPT-CIRC|warm", HEAD, GAMMA), ("ADAPT-DIR|warm", HEAD, GAMMA),
                ("ADAPT-CIRC", HEAD, 0.05), ("ADAPT-DIR", HEAD, 0.05), ("ADAPT-CIRC|warm", HEAD, 0.05),
                ("ADAPT-DIR|warm", HEAD, 0.05), ("TRACK-CIRC", HEAD, 0.2), ("TRACK-DIR", HEAD, 0.2),
                ("TRACK-CIRC|warm", HEAD, 0.2), ("TRACK-DIR|warm", HEAD, 0.2), ("TRACK-CIRC", HEAD, 0.05),
                ("TRACK-DIR", HEAD, 0.05), ("FIXED-DIRPF", HEAD, None), ("ADAPT-DIRPF", HEAD, GAMMA)]
        cols = [c for c in cols if c in arms[det.name][h]]
        for i, t in enumerate(d["t"]):
            row = dict(kst_hour=i, t_utc=str(det.time(t)), complete=bool(d["complete"][i]), burned_cells=int(d["n_spread"][i]),
                       reach_km=float(d["circ"][i]), dir_score_km=float(d["dir"][i, ksel["ALL"]]),
                       wind_kmh=float(d["speed"][i]), wind_from_deg=float(d["dirfrom"][i]),
                       wind_next_h_mean_kmh=float(d["speed_pf"][i]), length_to_breadth=float(M.length_to_breadth(d["speed"][i])))
            for c in cols:
                v = arms[det.name][h][c]
                s = sc(S, det.name, h, v["shape"])[i]
                row["|".join(map(str, c))] = dict(q_km=float(v["q"][i]), area_km2=float(areas[det.name][(h, c)][i] * CELL_KM2),
                                                  missed=bool(s > v["q"][i]) if d["complete"][i] else None,
                                                  saturated=bool(v["sat"][i]) if "sat" in v else None)
            rows.append(row)
        summ = {}
        for c in cols:
            v = arms[det.name][h][c]
            s = sc(S, det.name, h, v["shape"])
            ok = d["complete"]
            miss = (s > v["q"]) & ok
            changed = np.flatnonzero(np.abs(v["q"] - v["q"][0]) > 1e-12)
            summ["|".join(map(str, c))] = dict(
                complete_hours=int(ok.sum()), missed_hours=int(miss.sum()),
                missed_kst_hours=[int(i) for i in np.flatnonzero(miss)],
                first_missed_kst_hour=int(np.flatnonzero(miss)[0]) if miss.any() else None,
                first_kst_hour_size_changed=int(changed[0]) if len(changed) else None,
                held_where_FIXED_CIRC_missed=[int(i) for i in np.flatnonzero(
                    ok & ~miss & (sc(S, det.name, h, "circ") > arms[det.name][h][("FIXED-CIRC", HEAD, None)]["q"]))],
                max_q_km=float(v["q"].max()), area_km2_sum_complete=float(np.nansum(areas[det.name][(h, c)][ok]) * CELL_KM2),
                burned_cells=int(d["n_spread"][ok].sum()))
        m25[str(h)] = dict(hours=rows, summary=summ, max_calibration_score_km=dict(
            circle=float(max(sc(S, g, h, "circ").max() for g in cal_names)),
            wind_aligned=float(max(sc(S, g, h, ("dir", ksel["ALL"])).max() for g in cal_names))))
    res["march25"] = m25
    res["seconds"] = time.time() - t_start
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1, default=float) + "\n")

    for h in F.HORIZONS:
        print(f"--- h = {h} h, alpha = {HEAD} (LOFO, {len(cal_names)} fires)")
        for arm, par in (("FIXED-CIRC", None), ("REF-CIRC", None), ("FIXED-DIR", None), ("REF-DIR", None),
                         ("ADAPT-CIRC", GAMMA), ("ADAPT-DIR", GAMMA), ("ADAPT-CIRC", 0.05), ("ADAPT-DIR", 0.05),
                         ("TRACK-CIRC", 0.2), ("TRACK-DIR", 0.2), ("FIXED-DIRPF", None), ("ADAPT-DIRPF", GAMMA)):
            ag = lofo[str(h)].get(f"{arm}|{HEAD}|{par}")
            if not ag or "miss_fire_weighted" not in ag:
                continue
            dd = ag.get("vs_FIXED_CIRC")
            extra = (f" dOP {dd['op']['point']:+.1f} [{dd['op']['ci95'][0]:+.1f},{dd['op']['ci95'][1]:+.1f}]"
                     f" dmiss {dd['miss']['point']:+.4f} [{dd['miss']['ci95'][0]:+.4f},{dd['miss']['ci95'][1]:+.4f}]") if dd else ""
            print(f"{arm:12s} {str(par):6s} miss {ag['miss_fire_weighted']:.4f} OP {ag['op_fire_weighted']:8.1f} "
                  f"pooled {ag['op_pooled']:7.1f} area {ag['mean_area_km2_fire_weighted']:7.1f} km2 "
                  f"q {ag['mean_q_km_fire_weighted']:.2f} sat {ag['saturated_hours']}{extra}")
    print(json.dumps(res["verdict_arm2"], indent=1, default=float)[:3000])


if __name__ == "__main__":
    main()
