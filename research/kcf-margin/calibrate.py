"""Calibrate R(h) per class by split conformal over fires, evaluate leave-one-fire-out (PROTOCOL.md).

    python calibrate.py --work WORK --out numbers.json
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from reach import clopper_pearson, conformal_R  # noqa: E402

ALPHAS = (0.10, 0.20)
H_MAIN = (5, 8)
DRAWS = 2000
QUIET, RUNNING = 1.0, 3.0          # km in the last 3 h (PROTOCOL class b)
GUST_EDGES = (10.0, 20.0)          # m/s (PROTOCOL class c)
CLASSES = ("all", "quiet", "slow", "running", "gust<10", "gust10-20", "gust>=20")


def M(v, **kw):
    return dict(value=v, label="MEASURED", **kw)


def load(work):
    df = pd.read_csv(Path(work) / "gofer_reach.csv.gz")
    df["t"] = pd.to_datetime(df["t"])
    p3 = df[df.h == 3][["fire", "t_idx", "reach_km"]].rename(columns={"reach_km": "prior3_km"})
    p3["t_idx"] += 3
    df = df.merge(p3, on=["fire", "t_idx"], how="left")
    gust = pd.read_csv(Path(work) / "gofer_gusts.csv.gz", parse_dates=["t"])
    gmax = []
    for fire, g in df.groupby("fire"):
        s = gust[gust.fire == fire].set_index("t")["gust_ms"].sort_index()
        for h, gh in g.groupby("h"):
            # max over (t, t+h]: rolling max of the h hours ending at t+h, shifted to t
            roll = s.rolling(h, min_periods=h).max()
            vals = roll.reindex(gh["t"] + pd.Timedelta(hours=h)).to_numpy()
            gmax.append(pd.Series(vals, index=gh.index))
    df["gust_max_ms"] = pd.concat(gmax)
    df["complex"] = df.fire.str.contains("Complex")
    return df


def class_mask(df, c):
    if c == "all":
        return pd.Series(True, index=df.index)
    if c == "quiet":
        return df.prior3_km < QUIET
    if c == "slow":
        return (df.prior3_km >= QUIET) & (df.prior3_km < RUNNING)
    if c == "running":
        return df.prior3_km >= RUNNING
    if c == "gust<10":
        return df.gust_max_ms < GUST_EDGES[0]
    if c == "gust10-20":
        return (df.gust_max_ms >= GUST_EDGES[0]) & (df.gust_max_ms < GUST_EDGES[1])
    if c == "gust>=20":
        return df.gust_max_ms >= GUST_EDGES[1]
    raise KeyError(c)


def by_fire(d, col="reach_km"):
    return {f: g[col].to_numpy() for f, g in d.groupby("fire")}


def lofo(scores, alpha, draws=DRAWS):
    """Per held-out fire: R from the other fires, miss fraction on all its hours."""
    fires = sorted(scores)
    out = {}
    for f in fires:
        R, _, n = conformal_R([scores[g] for g in fires if g != f], alpha, draws)
        out[f] = (R, float(np.mean(scores[f] > R)), n)
    return out


def summarise_lofo(lo):
    m = np.array([v[1] for v in lo.values()])
    n = len(m)
    k = float(m.sum())
    lo_, hi_ = clopper_pearson(k, n)
    return dict(miss_rate=float(m.mean()) if n else math.nan, ci95=[lo_, hi_], n_fires=n,
                fires_with_any_miss=int((m > 0).sum()))


def fastest_miss(d, lo, key, q=0.9):
    """Miss rate on the fastest 10% of hours (pooled decile of `key`), using each fire's LOFO R."""
    thr = float(np.quantile(d[key].dropna(), q))
    sel = d[d[key] >= thr]
    miss = sel.apply(lambda r: r["reach_km"] > lo[r["fire"]][0], axis=1)
    per = miss.groupby(sel["fire"]).mean()
    k = float(per.sum())
    return dict(threshold_km=thr, hours=int(len(sel)), miss_rate_hours_pooled=float(miss.mean()),
                miss_rate_fire_weighted=float(per.mean()), n_fires=int(len(per)),
                ci95_fire_weighted=list(clopper_pearson(k, len(per))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    work = Path(a.work)
    df = load(work)
    res = dict(meta=dict(
        data="GOFER v0.2, 28 California fires 2019-2021, hourly perimeters", draws=DRAWS, seed=20261116,
        calibration="one random issue hour per fire, split conformal, median R over draws; claim is per random hour "
                    "of a random fire, on average over fires like these",
        issue_hours_all=M(int(len(df[df.h == 5]))), fires=M(int(df.fire.nunique())),
        complex_fires=sorted(df[df.complex].fire.unique().tolist()),
        gust_source=dict(value="ERA5 wind_gusts_10m via Open-Meteo archive at final-perimeter centroid, max over "
                         "(t, t+h]; reanalysis as a perfect-forecast proxy", label="ASSUMED")))
    table = []
    lofo_store = {}
    for fset in ("all28", "noComplex"):
        dsub = df if fset == "all28" else df[~df.complex]
        for h in H_MAIN:
            dh = dsub[dsub.h == h]
            for c in CLASSES:
                dc = dh[class_mask(dh, c)]
                sc = by_fire(dc)
                for al in ALPHAS:
                    R, Rs, n = conformal_R(list(sc.values()), al, DRAWS)
                    lo = lofo(sc, al)
                    s = summarise_lofo(lo)
                    row = dict(fire_set=fset, h=h, cls=c, alpha=al, R_km=R, R_draw_iqr=[float(np.quantile(Rs, .25)),
                               float(np.quantile(Rs, .75))] if np.isfinite(R) else None,
                               n_fires=n, hours=int(len(dc)), lofo_miss=s["miss_rate"], lofo_ci95=s["ci95"],
                               fires_with_any_miss=s["fires_with_any_miss"], label="MEASURED")
                    if c == "all":
                        row["fastest10_prior3"] = fastest_miss(dc, lo, "prior3_km")
                        row["fastest10_realised"] = fastest_miss(dc, lo, "reach_km")
                        lofo_store[(fset, h, al)] = {f: v[0] for f, v in lo.items()}
                    table.append(row)
                    print(fset, h, c, al, f"R={R:.2f} n={n} hours={len(dc)} lofo={s['miss_rate']:.3f} "
                          f"CI={s['ci95'][0]:.3f}-{s['ci95'][1]:.3f}", flush=True)
    res["table"] = table

    # sensitivity: separation rule (class all, all 28)
    sens = []
    for col in ("reach_sep2_km", "reach_nosep_km"):
        for h in H_MAIN:
            dh = df[df.h == h]
            for al in ALPHAS:
                sc = by_fire(dh, col)
                R, _, n = conformal_R(list(sc.values()), al, DRAWS)
                s = summarise_lofo(lofo(sc, al))
                sens.append(dict(rule=col, h=h, alpha=al, R_km=R, n_fires=n, lofo_miss=s["miss_rate"],
                                 lofo_ci95=s["ci95"], label="MEASURED"))
    res["sensitivity_separation_rule"] = sens

    # worst-hour-per-fire reference (what NOT to do)
    worst = {}
    for h in H_MAIN:
        w = df[df.h == h].groupby("fire").reach_km.max().to_numpy()
        worst[str(h)] = M(float(np.quantile(w, 0.9)), n_fires=len(w), what="90th pct over fires of each fire's worst hour")
        dh = df[df.h == h]
        worst[f"max_any_issue_hour_{h}h"] = M(float(dh.reach_km.max()), fire=str(dh.loc[dh.reach_km.idxmax(), "fire"]),
                                              nosep=float(dh.reach_nosep_km.max()))
        worst[f"nosep_q90_of_fire_worst_{h}h"] = M(float(np.quantile(dh.groupby("fire").reach_nosep_km.max(), 0.9)))
    res["worst_hour_reference_km"] = worst

    # miss rate vs target curve (class all, both fire sets)
    curve = []
    for fset in ("all28", "noComplex"):
        dsub = df if fset == "all28" else df[~df.complex]
        for h in H_MAIN:
            sc = by_fire(dsub[dsub.h == h])
            for al in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30):
                s = summarise_lofo(lofo(sc, al, draws=500))
                curve.append(dict(fire_set=fset, h=h, alpha=al, lofo_miss=s["miss_rate"], ci95=s["ci95"],
                                  n_fires=s["n_fires"], label="MEASURED"))
    res["miss_vs_target"] = curve

    # frozen R for longer horizons (for NIROPS) - class all, all 28
    longR = {}
    for h in sorted(df.h.unique()):
        sc = by_fire(df[df.h == h])
        longR[str(h)] = {str(al): conformal_R(list(sc.values()), al, DRAWS)[0] for al in ALPHAS}
    longR["label"] = "MEASURED (class all, 28 fires, km)"
    res["frozen_R_by_horizon_all28"] = longR
    res["prior_expectations_5h_90pct_km"] = dict(all=5, quiet=2, running=9, label="ASSUMED (rough pass, to confirm)")
    res["class_edges"] = dict(prior3_km=[QUIET, RUNNING], gust_ms=list(GUST_EDGES), separate_fire_km=5.0, label="ASSUMED (protocol)")
    Path(a.out).write_text(json.dumps(res, indent=1, default=float))
    pd.to_pickle(lofo_store, work / "lofo_R.pkl")


if __name__ == "__main__":
    main()
