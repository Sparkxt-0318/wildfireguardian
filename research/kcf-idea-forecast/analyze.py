"""Frozen analysis (TEST.md).  python3 analyze.py power|ca|kr
power: inputs only.  ca: P1 + P2 on GOFER.  kr: P3 on Gyeongbuk (run only after the CA commit)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "kcf-margin"))
P = json.loads((HERE / "params.json").read_text())
SETS = list(P["sets"])
K = P["c"] * 3.6   # km per hour per (m/s)


def windows(pred, hs=(5, 8)):
    """Per fire and issue hour t: X1 and X2 (per set) over stamps t+1..t+h."""
    out = []
    for fire, s in pred.groupby("fire"):
        s = s.sort_values("t").reset_index(drop=True)
        for h in hs:
            d = pd.DataFrame({"fire": fire, "t": s.t, "h": h})
            a = K * s.wind_speed_10m
            fwd = lambda v: v[::-1].rolling(h, min_periods=h).sum()[::-1].shift(-1)
            d["X1"] = fwd(a)
            for n in SETS:
                d["X2_" + n] = fwd(a * s["F_" + n])
            for c in ("wind_speed_10m", "wind_speed_100m", "wind_gusts_10m"):
                d["max_" + c] = s[c][::-1].rolling(h, min_periods=h).max()[::-1].shift(-1)
            out.append(d.dropna(subset=["X1"]))
    d = pd.concat(out, ignore_index=True)
    for n in SETS:
        d["Fh_" + n] = np.where(d.X1 > 0, d["X2_" + n] / d.X1.where(d.X1 > 0, 1), 1.0)
    return d


def pinball_fit(S, X1, F, w, tau=0.9):
    lx, lf = np.log(X1), np.log(F)
    def loss(p):
        u = S - np.exp(p[0] + p[1] * lx + p[2] * lf)
        return float(np.sum(w * np.where(u >= 0, tau * u, (tau - 1) * u)))
    best = None
    for start in ([0, 1, 0], [0, 1, 1], [0.5, 0.5, 0.5], [-0.5, 1.5, 2]):
        r = minimize(loss, start, method="Nelder-Mead", options=dict(xatol=1e-4, fatol=1e-7, maxiter=4000))
        if best is None or r.fun < best.fun:
            best = r
    return best.x


def p1(d, setname, h, nboot=1000, seed=20261118):
    q = d[(d.h == h) & (d.X1 > 0)].copy()
    fires = sorted(q.fire.unique())
    idx = {f: np.flatnonzero(q.fire.values == f) for f in fires}
    S, X1, F = q.reach_km.values, q.X1.values, q["Fh_" + setname].values
    def fit(counts):
        w = np.zeros(len(q))
        for f, c in zip(fires, counts):
            if c:
                w[idx[f]] = c / len(idx[f])
        m = w > 0
        return pinball_fit(S[m], X1[m], F[m], w[m])
    est = fit(np.ones(len(fires)))
    rng = np.random.default_rng(seed)
    bs = np.array([fit(np.bincount(rng.integers(0, len(fires), len(fires)), minlength=len(fires))) for _ in range(nboot)])
    ci = np.percentile(bs, [2.5, 97.5], axis=0)
    return dict(set=setname, h=h, n_fires=len(fires), n_hours=int(len(q)), kappa=float(np.exp(est[0])), gamma=float(est[1]),
                beta=float(est[2]), kappa_ci=[float(np.exp(ci[0, 0])), float(np.exp(ci[1, 0]))],
                gamma_ci=[float(ci[0, 1]), float(ci[1, 1])], beta_ci=[float(ci[0, 2]), float(ci[1, 2])])


def fire_mean(q, col):
    return float(q.groupby("fire")[col].mean().mean())


def main():
    mode = sys.argv[1]
    if mode in ("power", "ca"):
        pred = pd.read_csv(HERE / "data/pred_ca.csv.gz", parse_dates=["t"])
        d = windows(pred)
        gr = pd.read_csv(HERE.parent / "kcf-margin/derived/gofer_reach.csv.gz", usecols=["fire", "t", "h"], parse_dates=["t"])
        d = d.merge(gr[gr.h.isin([5, 8])], on=["fire", "t", "h"])       # issue hours that kcf-margin scored (no reach read)
        pw = {}
        for n in SETS:
            q = d[(d.h == 5) & (d["Fh_" + n] >= 1.2)]
            pw[n] = dict(hours=int(len(q)), fires=int(q.fire.nunique()), by_fire=q.fire.value_counts().to_dict())
        pw["n_issue_hours_h5"] = int((d.h == 5).sum())
        if mode == "power":
            (HERE / "power.json").write_text(json.dumps(pw, indent=1)); print(json.dumps({k: (v if not isinstance(v, dict) else {a: b for a, b in v.items() if a != "by_fire"}) for k, v in pw.items()}, indent=1))
            print(d[d.h == 5][["X1"] + ["Fh_" + n for n in SETS]].describe(percentiles=[.5, .9, .99]).T.round(2)); return
        gr = pd.read_csv(HERE.parent / "kcf-margin/derived/gofer_reach.csv.gz", usecols=["fire", "t", "h", "reach_km"], parse_dates=["t"])
        d = d.merge(gr, on=["fire", "t", "h"])
        res = {"power": pw, "p1": [], "exceed": [], "p2": []}
        for h in (5, 8):
            for n in SETS:
                res["p1"].append(p1(d, n, h, nboot=1000 if (n == "primary") else 300)); print(res["p1"][-1], flush=True)
        for h in (5, 8):
            for n in SETS:
                q = d[d.h == h].copy(); q["e1"] = q.reach_km > q.X1; q["e2"] = q.reach_km > q["X2_" + n]
                for lab, m in (("F<1.2", q["Fh_" + n] < 1.2), ("F>=1.2", q["Fh_" + n] >= 1.2)):
                    s = q[m]
                    res["exceed"].append(dict(set=n, h=h, group=lab, hours=int(len(s)), fires=int(s.fire.nunique()),
                                              S_gt_X1=fire_mean(s, "e1") if len(s) else None, S_gt_X2=fire_mean(s, "e2") if len(s) else None,
                                              median_S=float(s.reach_km.median()) if len(s) else None, median_X1=float(s.X1.median()) if len(s) else None))
        from reach import conformal_R
        for h in (5, 8):
            q = d[d.h == h]; fires = sorted(q.fire.unique())
            for lab, col in (("constant", None), ("X1", "X1"), ("X2_primary", "X2_primary")):
                miss, marg = [], []
                for f in fires:
                    sc = [(g.reach_km / (np.maximum(g[col], 1.0) if col else 1.0)).values for ff, g in q.groupby("fire") if ff != f]
                    kap = conformal_R(sc, 0.10)[0]
                    g = q[q.fire == f]; R = kap * (np.maximum(g[col], 1.0) if col else 1.0)
                    miss.append(float(np.mean(g.reach_km.values > R))); marg.append(float(np.mean(R)))
                res["p2"].append(dict(h=h, margin=lab, lofo_miss=float(np.mean(miss)), mean_margin_km=float(np.mean(marg)),
                                      kappa_all=float(conformal_R([(g.reach_km / (np.maximum(g[col], 1.0) if col else 1.0)).values for _, g in q.groupby("fire")], 0.10)[0])))
                print(res["p2"][-1], flush=True)
        (HERE / "results_ca.json").write_text(json.dumps(res, indent=1))
        d.to_csv(HERE / "data/ca_joined.csv.gz", index=False)
    elif mode == "kr":
        pred = pd.read_csv(HERE / "data/pred_kr.csv.gz", parse_dates=["t"])
        d = windows(pred)
        g = pd.read_csv(HERE.parent / "kcf-margin/derived/gyeongbuk_reach.csv", parse_dates=["t_utc"])
        g = g[g.complete].rename(columns={"t_utc": "t"})
        d = d.drop(columns="fire").merge(g[["kst_hour", "t", "h", "reach_km"]], on=["t", "h"]).sort_values(["h", "kst_hour"])
        res = {"hours": d.round(3).assign(t=d.t.astype(str)).to_dict("records"), "counts": []}
        for h in (5, 8):
            q = d[d.h == h]
            row = dict(h=h, n=int(len(q)), miss_X1=int((q.reach_km > q.X1).sum()))
            for n in SETS:
                row["miss_X2_" + n] = int((q.reach_km > q["X2_" + n]).sum())
            res["counts"].append(row); print(row)
        res["peak_rate_kmh"] = {n: float((K * pred.wind_speed_10m * pred["F_" + n]).max()) for n in SETS}
        res["peak_rate_kmh"]["baseline"] = float((K * pred.wind_speed_10m).max())
        res["F_max"] = {n: float(pred["F_" + n].max()) for n in SETS}
        (HERE / "results_kr.json").write_text(json.dumps(res, indent=1))
        print(d[d.h == 5][["kst_hour", "reach_km", "X1", "X2_primary", "Fh_primary", "X2_ti0", "X2_gust"]].round(1).to_string(index=False))
        print(res["peak_rate_kmh"])


if __name__ == "__main__":
    main()
