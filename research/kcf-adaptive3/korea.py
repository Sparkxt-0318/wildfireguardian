#!/usr/bin/env python3
"""Korea, leave-one-fire-out (PROTOCOL sections 5 and 6: targets A and B, and 25 March 2025). Run once, after final_ca.py.

    python3 korea.py --burden derived/burden_hours.csv.gz
Output: derived/korea.json, derived/korea_rows.csv.gz, derived/korea_alarm_hours.csv.gz, derived/mar25.csv
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import argparse
import json
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from lib3 import *
from lib import per_fire_grid
from methods_base import Fixed
from methods2 import Quantile

ALOFT = HERE.parent / "kcf-aloft" / "derived" / "fire_hours.csv.gz"
G = {}


class BurdenD:
    """The ten burden points as pseudo-fires with no detections: growth 0, area 0, age 0 (PROTOCOL section 6)."""

    def __init__(self, path):
        b = pd.read_csv(path)
        b["series"] = b.season.astype(str) + "|" + b.point
        b = b.sort_values(["series", "t_utc"]).reset_index(drop=True)
        self.df = b
        self.ok = b[["gust_ms", "w850_ms", "rhmin_pct"]].notna().all(axis=1).values
        t = pd.to_datetime(b.t_utc)
        sol = (t.dt.hour + b.lon / 15.0) % 24
        self.X = {c: np.zeros(len(b)) for c in ALL}
        for c in ("gust_ms", "w850_ms", "rhmin_pct"):
            self.X[c] = b[c].values.astype(float)
        self.X["hdw"] = np.full(len(b), np.nan)
        self.X["sin_h"], self.X["cos_h"] = np.sin(2 * np.pi * sol / 24).values, np.cos(2 * np.pi * sol / 24).values
        self.fid = pd.factorize(b.series)[0]
        self.hour = t.values.astype("datetime64[h]").astype(np.int64)

    def day_max(self, score):
        """Per complete point-day (24 hours with a forecast): max score and max g_k2."""
        d = self.df.assign(score=score, ok=self.ok)
        g = d.groupby(["season", "point", "kst_day"]).agg(n=("ok", "sum"), score=("score", "max"), g=("g_k2", "max"))
        return g[g.n == 24]


def init():
    G["D"] = load_all()
    G["kept"] = json.load(open(HERE / "derived" / "kept.json"))["cfg"]
    G["qcfg"] = json.load(open(HERE / "derived" / "final_ca.json"))["QUANTILE"]["cfg"]


def methods():
    kept = G["kept"]
    noarch = dict(kept, trans=[f for f in kept["trans"] if f != "arch"])
    return {"FIXED": Fixed(), "QUANTILE": Quantile(configs=[G["qcfg"]]),
            "TRACKER": Tracker("TRACKER", kept), "TRACKER-noupdate": Tracker("TRACKER-noupdate", kept, update=False),
            "TRACKER-nofc": Tracker("TRACKER-nofc", kept, fc=False), "TRACKER-noarchive": Tracker("TRACKER-noarchive", noarch)}


def rows_train(D, fires):
    """Eligible rows; GOFER for California, Choi raster for Korea (the detection product is never trained on)."""
    s = set(fires)
    return np.flatnonzero(D.elig & np.isin(D.product, ["GOFER", "CHOI"]) & np.array([f in s for f in D.fire]))


def primary_rows(D, fire):
    a = pd.read_csv(ALOFT)
    a = a[(a.timeline == "primary") & a.issue & (a.fire == fire)][["fire", "product", "t_utc", "kst_day", "kst_hour", "run"]]
    key = {(f, p, t): i for i, (f, p, t) in enumerate(zip(D.fire, D.product, D.df.t_utc.values))}
    idx = np.array([key[(f, p, t)] for f, p, t in zip(a.fire, a["product"], a.t_utc)])
    o = np.argsort(D.hour[idx], kind="stable")
    return idx[o], a.iloc[o].reset_index(drop=True)


def job(args):
    """One left-out fire i and one method: kappa from the other 11 (models without i and j), then score i."""
    i, name = args
    if not G:
        init()
    if "B" not in G and os.environ.get("KCF3_BURDEN"):
        G["B"] = BurdenD(os.environ["KCF3_BURDEN"])
    D = G["D"]
    m = methods()[name]
    cfg = m.configs[0]
    others = [f for f in D.kr if f != i]
    S, s, fid = [], [], []
    for j in others:
        tr = rows_train(D, D.gofer + [f for f in others if f != j])
        te = rows_train(D, [j])
        mdl = m.fit(cfg, D, tr)
        s.append(np.maximum(m.predict(mdl, D, te), S_FLOOR)); S.append(D.S[te]); fid.append(D.fid[te])
    kappa = kappa_for(np.concatenate(S), np.concatenate(s), np.concatenate(fid))
    mdl = m.fit(cfg, D, rows_train(D, D.gofer + others))
    te = rows_train(D, [i])
    out = dict(fire=i, name=name, kappa=kappa, te=te, s=np.maximum(m.predict(mdl, D, te), S_FLOOR))
    if isinstance(m, Tracker):
        pidx, meta = primary_rows(D, i)
        sp = np.maximum(m.predict(mdl, D, pidx), S_FLOOR)
        st = m.last
        out.update(pidx=pidx, meta=meta, sp=sp, st={k: st[k] for k in st})
        if "B" in G:                       # burden: the same model with no detections
            B = G["B"]
            twin = Tracker(name, cfg, update=False, fc=m.fc)
            p = np.full(len(B.fid), np.nan)
            ok = np.flatnonzero(B.ok)
            p[ok] = twin.states(mdl, B, ok, margins=False)["p"]
            out["burden"] = B.day_max(p)
    else:
        pidx, meta = primary_rows(D, i)
        out.update(pidx=pidx, meta=meta, sp=np.maximum(m.predict(mdl, D, pidx), S_FLOOR))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--burden", required=True)
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()
    out = HERE / "derived" / "korea.json"
    if out.exists():
        raise SystemExit("korea.json exists: the Korean run is made once")
    os.environ["KCF3_BURDEN"] = a.burden
    init()
    D = G["D"]
    names = list(methods())
    jobs = [(i, n) for n in names for i in D.kr]
    with ProcessPoolExecutor(a.procs) as ex:
        results = list(ex.map(job, jobs))
    res = {"fires": D.kr}
    # ---------------- target B
    grids = {}
    rowsB = []
    for n in names:
        rs = [r for r in results if r["name"] == n]
        te = np.concatenate([r["te"] for r in rs])
        s = np.concatenate([r["s"] for r in rs])
        kap = np.concatenate([np.full(len(r["te"]), r["kappa"]) for r in rs])
        o = np.argsort(te)
        te, s, kap = te[o], s[o], kap[o]
        full_s, full_k = np.full(len(D.S), np.nan), np.full(len(D.S), np.nan)
        full_s[te], full_k[te] = s, kap
        fires, miss, area = evaluate(D, te, full_s, full_k)
        grids[n] = (miss, area)
        r = boot_summary(miss, area)
        r.update(n_hours=int(len(te)), missed_hours=int((D.S[te] > kap * s).sum()),
                 kappa={x["fire"]: round(x["kappa"], 4) for x in rs},
                 per_fire_area=dict(zip(fires, area[:, 20].round(3).tolist())),
                 per_fire_miss=dict(zip(fires, miss[:, 20].round(4).tolist())))
        res[n] = r
        rowsB.append(pd.DataFrame(dict(method=n, fire=D.fire[te], t_utc=D.df.t_utc.values[te], S=D.S[te], q=kap * s)))
    for x, y in (("TRACKER", "FIXED"), ("QUANTILE", "FIXED"), ("TRACKER", "QUANTILE"), ("TRACKER-noupdate", "FIXED"),
                 ("TRACKER-nofc", "FIXED"), ("TRACKER-noarchive", "FIXED"), ("TRACKER", "TRACKER-noupdate"),
                 ("TRACKER", "TRACKER-nofc")):
        r, lo, hi = ratio_ci(grids[x][1][:, 20], grids[y][1][:, 20])
        res[f"ratio {x} / {y}"] = dict(ratio=r, lo=lo, hi=hi, frontier_ratio=res[x]["frontier_area"] / res[y]["frontier_area"])
    pd.concat(rowsB).round(4).to_csv(HERE / "derived" / "korea_rows.csv.gz", index=False)
    # ---------------- secondary rows: California-fitted model, (a) kappa recalibrated leave-one-fire-out, (b) straight
    D2 = load()
    te2 = np.flatnonzero(np.isin(D2.fire, D2.kr) & (D2.product == "CHOI"))
    for n, m in methods().items():
        fit = fit_calibrate(m, D2, D2.gofer) if n != "QUANTILE" else fit_calibrate(Quantile(), D2, D2.gofer)
        s2 = fit.s(D2, te2)
        fires, miss, area = per_fire_grid(D2, te2, s2, fit.kappa)
        res[f"CA-transfer {n}"] = dict(boot_summary(miss, area), kappa=fit.kappa)
        kap = np.zeros(len(te2))
        for f in D2.kr:
            oth = D2.fire[te2] != f
            kap[~oth] = kappa_for(D2.S[te2][oth], s2[oth], D2.fid[te2][oth])
        fs, fk = np.full(len(D2.S), np.nan), np.full(len(D2.S), np.nan)
        fs[te2], fk[te2] = s2, kap
        fires, miss, area = evaluate(D2, te2, fs, fk)
        res[f"CA-fit LOFO-kappa {n}"] = boot_summary(miss, area)
    # ---------------- target A
    alarm_rows = []
    for n in [x for x in names if x.startswith("TRACKER")]:
        days, nrun_alarm, nquiet = [], 0, 0
        gcount = None
        for r in [x for x in results if x["name"] == n]:
            b = r["burden"]
            NG = int((b.g >= 20.0).sum())
            sc = np.sort(b.score.values)[::-1]
            c = float(np.nextafter(sc[NG], np.inf)) if NG < len(sc) else -np.inf      # at most NG point-days at or above c
            full = b.reset_index()
            full = full[full.season >= 2022]
            gcount = dict(point_days=int(len(b)), G_alarm_point_days=NG,
                          G_per_point_season_2022_2025=float((full.g >= 20).sum() / 40.0))
            meta = r["meta"].assign(p=r["st"]["p"], prior=r["st"]["prior"], enter=r["st"]["enter"], c=c, method=n)
            alarm_rows.append(meta)
            hr = D.hour[r["pidx"]]
            for day, g in meta.groupby("kst_day"):
                if g.run.any():
                    k = g.index[g.run.values][0]
                    prev = meta[(hr >= hr[k] - 6) & (hr < hr[k])]
                    days.append(dict(fire=r["fire"], kst_day=day, first_run_kst=int(meta.kst_hour[k]), p=float(meta.p[k]),
                                     prior=float(meta.prior[k]), c=c, warned=bool(meta.p[k] >= c),
                                     onset=not bool(prev.run.any()), tracker_model_alarm_point_days=int((b.score >= c).sum())))
                else:
                    nquiet += 1
                    nrun_alarm += int((g.p >= c).any())
        d = pd.DataFrame(days)
        res[f"A {n}"] = dict(run_days=int(len(d)), warned=int(d.warned.sum()), onset_days=int(d.onset.sum()),
                             warned_onset=int((d.warned & d.onset).sum()),
                             warned_without_25_march=int(d[d.kst_day != "2025-03-25"].warned.sum()),
                             no_run_fire_days=nquiet, alarms_on_no_run_fire_days=nrun_alarm, burden=gcount, days=days)
    pd.concat(alarm_rows).round(5).to_csv(HERE / "derived" / "korea_alarm_hours.csv.gz", index=False)
    # ---------------- 25 March 2025
    tab = None
    for n in names:
        r = [x for x in results if x["name"] == n and x["fire"] == "KFS_01"][0]
        meta = r["meta"]
        sel = ((meta.kst_day == "2025-03-25") & meta.kst_hour.between(9, 20)).values
        idx = r["pidx"][sel]
        q = r["kappa"] * r["sp"][sel]
        if tab is None:
            tab = pd.DataFrame(dict(kst_hour=meta.kst_hour[sel].values, product=D.product[idx], reach_km=D.S[idx],
                                    gust_ms=D.X["gust_ms"][idx], w850_ms=D.X["w850_ms"][idx], rhmin_pct=D.X["rhmin_pct"][idx],
                                    o_g1_km=D.X["g1"][idx]))
        tab[f"q_{n}"] = q
        tab[f"miss_{n}"] = (D.S[idx] > q).astype(int)
        tab[f"area_{n}"] = D.area(idx, np.minimum(q, NB * CELL_KM))
        if "st" in r:
            for k in ("enter", "stay", "prior", "p", "m0", "m1"):
                tab[f"{k}_{n}"] = r["st"][k][sel]
            a_ = res[f"A {n}"]["days"]
            tab[f"c_{n}"] = [x["c"] for x in a_ if x["fire"] == "KFS_01"][0]
    tab.round(4).to_csv(HERE / "derived" / "mar25.csv", index=False)
    json.dump(res, open(out, "w"), indent=1)
    for n in names:
        print(n, {k: round(v, 4) for k, v in res[n].items() if isinstance(v, float)}, res.get(f"A {n}", {}).get("warned"))


if __name__ == "__main__":
    main()
