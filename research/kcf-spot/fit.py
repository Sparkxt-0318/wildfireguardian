"""Step 3: fit P(cell lit by a spot within h | distance, angle to downwind, forecast gust) (PROTOCOL section 4).

    cloglog P = b0 + b1 log x + b2 U + b3 U log x + b4 log h + b5 cos a

Fire-weighted binomial likelihood (each fire's cells carry equal total weight), fitted by IRLS on cells binned by
distance, angle, lead and gust (0.5 m/s). Training: CA-DEV for California; CA-DEV + the other Korean fires for each
Korean fold and for 25 March (KFS_01 out of every fit). Primary outcome: confirmed spots.

    python fit.py --cells WORK/cells.pkl --spots derived/spots_all.csv --out derived
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_cells import AE, XE  # noqa: E402

sys.path.insert(0, str(HERE.parent / "kcf-adaptive4"))
import lib4  # noqa: E402

XMID = np.sqrt(XE[:-1] * XE[1:])
AMID = (AE[:-1] + AE[1:]) / 2
NBOOT = 1000
RNG = np.random.default_rng(20261119)
COEF = ["b0", "b1_logx", "b2_U", "b3_UlogX", "b4_logh", "b5_cosa"]


def design(d):
    lx = np.log(XMID[d.xbin.values])
    U = d.gust.values.astype(float)
    return np.c_[np.ones(len(d)), lx, U, U * lx, np.log(d.lead.values.astype(float)), np.cos(np.radians(AMID[d.abin.values]))]


def compress(cells, y="y_conf"):
    d = cells.copy()
    d["gust"] = (d.gust / 0.5).round() * 0.5
    g = d.groupby(["fire", "region", "xbin", "abin", "lead", "gust"], as_index=False, observed=True)[["n", y]].sum()
    return g.rename(columns={y: "y"})


def _dev(beta, X, y, n, w):
    mu = np.clip(-np.expm1(-np.exp(np.clip(X @ beta, -30, 5))), 1e-15, 1 - 1e-12)
    return -2 * np.sum(w * (y * np.log(mu) + (n - y) * np.log1p(-mu)))


def irls(X, y, n, w, it=100, beta=None):
    """Weighted binomial cloglog by IRLS with step-halving on the deviance. y, n counts; w row weights."""
    p_bar = max(y.sum() / n.sum(), 1e-9)
    if beta is None:
        beta = np.zeros(X.shape[1]); beta[0] = np.log(-np.log1p(-p_bar))
    dev = _dev(beta, X, y, n, w)
    for _ in range(it):
        eta = np.clip(X @ beta, -30, 5)
        e = np.exp(eta)
        mu = np.clip(-np.expm1(-e), 1e-15, 1 - 1e-12)
        dmu = np.maximum(e * np.exp(-e), 1e-300)
        var = mu * (1 - mu)
        W = w * n * dmu ** 2 / var
        z = eta + (y / n - mu) / dmu
        A = X.T @ (W[:, None] * X) + 1e-9 * np.eye(X.shape[1])
        step = np.linalg.solve(A, X.T @ (W * z)) - beta
        for _h in range(30):
            nb = beta + step
            nd = _dev(nb, X, y, n, w)
            if np.isfinite(nd) and nd <= dev + 1e-12 * abs(dev):
                break
            step = step / 2
        else:
            break
        conv = abs(dev - nd) < 1e-10 * max(abs(dev), 1e-30)
        beta, dev = nb, nd
        if conv:
            break
    return beta


def predict(beta, X):
    return -np.expm1(-np.exp(np.clip(X @ beta, -30, 5)))


def fire_weights(d):
    tot = d.groupby("fire").n.transform("sum").values.astype(float)
    return 1.0 / tot


def fit(d):
    return irls(design(d), d.y.values.astype(float), d.n.values.astype(float), fire_weights(d))


def boot_fit(d, nb=NBOOT):
    fires = d.fire.unique()
    parts = {f: g for f, g in d.groupby("fire")}
    base = fit(d)
    out = []
    for _ in range(nb):
        pick = RNG.choice(fires, len(fires), replace=True)
        # duplicates: each copy is a separate "fire" for weighting
        dd = pd.concat([parts[f].assign(fire=f"{f}#{i}") for i, f in enumerate(pick)], ignore_index=True)
        if dd.y.sum() == 0:
            continue
        out.append(irls(design(dd), dd.y.values.astype(float), dd.n.values.astype(float), fire_weights(dd), beta=base.copy()))
    return base, np.array(out)


# ---------------------------------------------------------------- published reference model (LITERATURE.md R0)
def albini_dmax_km(U_ms, I_kWm=10000.0, H_m=10.0):
    """Albini (1983) surface-fire maximum spot distance, BehavePlus spot.cpp form (LITERATURE.md section 1)."""
    U = np.asarray(U_ms, float) * 2.23694                          # mph, gust used as the 20-ft wind (assumption)
    I_B = I_kWm / 3.4613                                          # Btu/ft/s
    Lf = 0.45 * I_B ** 0.46                                       # ft
    I_B = (Lf / 0.45) ** (1 / 0.46)
    f = 322.0 * (0.474 * U) ** -1.01
    zF = 1.055 * np.sqrt(f * I_B)
    H = H_m * 3.2808
    Hc = np.maximum(H, 2.2 * zF ** 0.337 - 4.0)
    D = 0.000718 * U * np.sqrt(Hc) * (0.362 + 0.5 * np.sqrt(zF / Hc) * np.log(zF / Hc)) + 0.000278 * U * zF ** 0.643
    return D * 1.609344


def r0_median_km(U, I=10000.0, sigma=0.8):
    return albini_dmax_km(U, I) / np.exp(2.326 * sigma)


def r0_sf(x_km, U, I=10000.0, sigma=0.8):
    """P(landing distance > x) under the R0 lognormal."""
    return stats.lognorm.sf(x_km, s=sigma, scale=r0_median_km(U, I, sigma))


def empirical(cells, y="y_conf"):
    d = cells.copy()
    d["w"] = 1.0 / d.groupby("fire").n.transform("sum")
    d["dband"] = pd.cut(XMID[d.xbin.values], [1, 2, 3, 5, 8, 15.01], right=False,
                        labels=["1-2", "2-3", "3-5", "5-8", "8-15"])
    a = AMID[d.abin.values]
    d["sector"] = np.where(a <= 45, "down", np.where(a >= 135, "up", "cross"))
    d["gband"] = pd.cut(d.gust, [0, 10, 15, 20, 99], right=False, labels=["<10", "10-15", "15-20", ">=20"])
    d = d[d.lead.isin([1, 2, 5, 8]) & d.dband.notna()]
    d["wy"], d["wn"] = d.w * d[y], d.w * d.n
    g = d.groupby(["lead", "gband", "sector", "dband"], observed=True).agg(wy=("wy", "sum"), wn=("wn", "sum"),
                                                                          y=(y, "sum"), n=("n", "sum"),
                                                                          fires=("fire", "nunique"))
    g["P"] = g.wy / g.wn
    return g.reset_index()


def calib(beta, d):
    p = predict(beta, design(d))
    w = fire_weights(d) * d.n.values
    q = pd.qcut(p, 10, labels=False, duplicates="drop")
    rows = []
    for k in np.unique(q):
        m = q == k
        rows.append(dict(decile=int(k), pred=float(np.sum(p[m] * w[m]) / w[m].sum()),
                         obs=float(np.sum(d.y.values[m] / d.n.values[m] * w[m]) / w[m].sum()), cells=int(d.n.values[m].sum()),
                         lit=int(d.y.values[m].sum())))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", required=True)
    ap.add_argument("--spots", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--nboot", type=int, default=NBOOT)
    a = ap.parse_args()
    cells = pd.read_pickle(a.cells)
    cells = cells[cells.region.isin(["CA", "KR", "DET"])]
    names = sorted(cells[cells.region == "CA"].fire.unique())
    dev, held, _ = lib4.ca_split({n: None for n in names})
    res = dict(dev=dev, held=held)
    comp = {}
    for y in ("y_conf", "y_all"):
        comp[y] = compress(cells, y)
    # ---- primary fit for California held-out: CA-DEV only
    d_dev = comp["y_conf"][(comp["y_conf"].region == "CA") & comp["y_conf"].fire.isin(dev)]
    beta, B = boot_fit(d_dev, a.nboot)
    res["ca_fit"] = dict(beta=beta.tolist(), ci=np.quantile(B, [0.025, 0.975], axis=0).tolist(), nboot=len(B),
                         names=COEF, lit=int(d_dev.y.sum()), cells=int(d_dev.n.sum()))
    np.save(Path(a.out) / "fit_ca_boot.npy", B)
    # ---- all-spots (unconfirmed included) sensitivity
    d_dev_all = comp["y_all"][(comp["y_all"].region == "CA") & comp["y_all"].fire.isin(dev)]
    res["ca_fit_all"] = dict(beta=fit(d_dev_all).tolist(), names=COEF)
    # ---- Korean folds and 25 March
    kr_fires = sorted(comp["y_conf"][comp["y_conf"].region == "KR"].fire.unique())
    folds = {}
    for f in kr_fires + ["DET:KFS_01"]:
        hold = "KFS_01" if f.startswith("DET") else f
        tr = comp["y_conf"][((comp["y_conf"].region == "CA") & comp["y_conf"].fire.isin(dev))
                            | ((comp["y_conf"].region == "KR") & (comp["y_conf"].fire != hold))]
        folds[f] = fit(tr).tolist()
    res["kr_folds"] = folds
    # ---- calibration on held-out
    d_held = comp["y_conf"][(comp["y_conf"].region == "CA") & comp["y_conf"].fire.isin(held)]
    res["calib_ca_held"] = calib(beta, d_held)
    kr_rows = []
    for f in kr_fires:
        dk = comp["y_conf"][(comp["y_conf"].region == "KR") & (comp["y_conf"].fire == f)]
        dk = dk.assign(p=predict(np.array(folds[f]), design(dk)))
        kr_rows.append(dk)
    dk = pd.concat(kr_rows)
    w = fire_weights(dk) * dk.n.values
    res["kr_heldout_pred_vs_obs"] = dict(pred_lit=float((dk.p * dk.n).sum()), obs_lit=int(dk.y.sum()),
                                         pred_w=float(np.sum(dk.p * w) / w.sum()),
                                         obs_w=float(np.sum(dk.y / dk.n * w) / w.sum()))
    dd = comp["y_conf"][comp["y_conf"].region == "DET"]
    pd_ = predict(np.array(folds["DET:KFS_01"]), design(dd))
    res["det_pred_vs_obs"] = dict(pred_lit=float((pd_ * dd.n).sum()), obs_lit=int(dd.y.sum()), max_p=float(pd_.max()))
    held_p = predict(beta, design(d_held))
    res["ca_held_pred_vs_obs"] = dict(pred_lit=float((held_p * d_held.n).sum()), obs_lit=int(d_held.y.sum()))
    # ---- P at selected points (5 h lead, downwind)
    grid = []
    for U in (5, 10, 15, 20, 25):
        for x in (1.0, 2.0, 3.0, 5.0, 8.0, 12.0):
            X = np.array([[1, np.log(x), U, U * np.log(x), np.log(5.0), 1.0]])
            p = float(predict(beta, X)[0])
            pbs = -np.expm1(-np.exp(np.clip(B @ X[0], -30, 5)))
            grid.append(dict(U=U, x_km=x, P5h_down=p, lo=float(np.quantile(pbs, 0.025)), hi=float(np.quantile(pbs, 0.975)),
                             cells_per_ha=1 / 14.0625))
    res["P_grid_5h_downwind"] = grid
    # ---- empirical table
    emp = empirical(cells[(cells.region == "CA") & cells.fire.isin(dev)])
    emp.to_csv(Path(a.out) / "empirical_ca_dev.csv", index=False)
    emp_all = empirical(cells[cells.region == "CA"])
    emp_all.to_csv(Path(a.out) / "empirical_ca_all.csv", index=False)
    # ---- comparison with the published reference (R0 lognormal, Albini anchored)
    sp = pd.read_csv(a.spots)
    obs = sp[(sp.region == "CA") & sp.confirmed.astype(bool) & sp.fc_gust_ms.notna()]
    comp_rows = {}
    for name, sub in (("all sectors", obs), ("downwind", obs[obs.sector == "down"])):
        U = sub.fc_gust_ms.values
        x = sub.dist_km.values
        dmax = albini_dmax_km(U)
        dmax30 = albini_dmax_km(U, 30000.0)
        # conditional on x >= 1 km (the VIIRS d_min), R0 distribution of distance, mixed over the spots' gusts
        grid_x = np.linspace(1.0, 15.0, 561)
        cdf = np.zeros_like(grid_x)
        for u in U:
            s1 = r0_sf(1.0, u)
            cdf += (s1 - r0_sf(grid_x, u)) / max(s1, 1e-300)
        cdf /= len(U)
        ecdf = np.searchsorted(np.sort(x), grid_x, side="right") / len(x)
        comp_rows[name] = dict(n=int(len(sub)), share_beyond_albini_10MW=float(np.mean(x > dmax)),
                               share_beyond_albini_30MW=float(np.mean(x > dmax30)),
                               albini_10MW_km_q50=float(np.median(dmax)),
                               r0_P_beyond_1km_median=float(np.median(r0_sf(1.0, U))),
                               r0_P_beyond_4km_median=float(np.median(r0_sf(4.0, U))),
                               ks_vs_R0_conditional=float(np.max(np.abs(ecdf - cdf))),
                               r0_cond_median_km=float(grid_x[np.searchsorted(cdf, 0.5)]),
                               obs_median_km=float(np.median(x)))
    res["vs_published"] = comp_rows
    # distance decay implied by the fit: d log P / d log x at U (5 h, downwind) vs R0 tail slope at 3 km
    dec = []
    for U in (5, 10, 15, 20):
        b = beta
        slope_fit = b[1] + b[3] * U
        x = 3.0
        eps = 1e-3
        pdf = lambda xx: stats.lognorm.pdf(xx, s=0.8, scale=r0_median_km(U))
        slope_r0 = (np.log(pdf(x * (1 + eps))) - np.log(pdf(x))) / np.log(1 + eps)
        dec.append(dict(U=U, fit_dlogP_dlogx=float(slope_fit), r0_dlogpdf_dlogx_at3km=float(slope_r0)))
    res["decay"] = dec
    json.dump(res, open(Path(a.out) / "fit.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("calib_ca_held",)}, indent=1)[:6000])
    print("calib", json.dumps(res["calib_ca_held"]))


if __name__ == "__main__":
    main()
