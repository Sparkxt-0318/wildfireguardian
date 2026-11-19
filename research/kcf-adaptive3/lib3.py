"""kcf-adaptive3: the online quiet/run regime tracker (PROTOCOL section 2) and the dev metrics (section 4).

Data, calibration, area and bootstrap machinery are imported from kcf-adaptive2/lib.py unchanged.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "kcf-adaptive2"))
from lib import (ALL, FC, LAMS, NB, CELL_KM, OWN, S_FLOOR, TARGET, Data, boot_idx, boot_summary, evaluate,  # noqa: E402,F401
                 fire_weights, fit_calibrate, frontier_read, kappa_for, outer_folds, ratio_ci, run_outer)

WORK = os.environ.get("KCF3_WORK", "/home/user/kcf3data/work")
RUN_KM = 3.75
DEV_FOLDS = (0, 1, 2, 3)
HELD_FOLDS = (4, 5, 6)
ARCH_FILE = HERE / "derived" / "archive_propensity.json"
OBS_BINS = [0.0, 0.375, 0.75, 1.5, 3.0]          # o <= 0 | (0, .375] | (.375, .75] | (.75, 1.5] | (1.5, 3] | > 3

V0 = dict(trans=["gust_ms", "w850_ms", "rhmin_pct", "sin_h", "cos_h", "arch"], obs="g1", bins=OBS_BINS,
          mfeat=ALL, tau=0.9, depth=2, iters=100, leaf0=200, leaf1=50, mix="linear", C=1.0)


def load(h=5):
    D = Data(h, WORK)
    D.hour = (D.t.astype("datetime64[h]").astype(np.int64))
    D.z = (D.S > RUN_KM).astype(int)
    D.gofer = [f for f in D.fires if D.product[D.fire == f][0] == "GOFER"]
    fo = outer_folds(D.gofer)
    D.dev = [f for f in D.gofer if fo[f] in DEV_FOLDS]
    D.held = [f for f in D.gofer if fo[f] in HELD_FOLDS]
    D.dev_folds = {f: fo[f] for f in D.dev}
    D.kr = [f for f in D.fires if str(f).startswith("KFS")]
    return D


def arch_logit(gust, w850, rh):
    """Archive run-day propensity (logit) evaluated at an hour's forecast-window values. None if no archive model."""
    if not ARCH_FILE.exists():
        return None
    a = json.load(open(ARCH_FILE))
    X = (np.column_stack([gust, w850, rh]) - np.array(a["mu"])) / np.array(a["sd"])
    return a["b0"] + X @ np.array(a["b"])


def trans_matrix(D, idx, feats):
    cols = []
    for f in feats:
        if f == "arch":
            v = arch_logit(D.X["gust_ms"][idx], D.X["w850_ms"][idx], D.X["rhmin_pct"][idx])
            if v is None:
                raise RuntimeError("archive propensity requested but derived/archive_propensity.json is missing")
            cols.append(v)
        elif f.startswith("log_") and f[4:] in D.X:
            cols.append(np.log1p(np.maximum(D.X[f[4:]][idx], 0)))
        else:
            cols.append(D.X[f][idx])
    return np.column_stack(cols) if cols else np.zeros((len(idx), 0))


def _prev(D, idx):
    """For rows idx (sorted by fire, t): index into idx of the previous hour of the same fire, -1 if none; and gap hours."""
    fid, hr = D.fid[idx], D.hour[idx]
    same = np.r_[False, fid[1:] == fid[:-1]]
    gap = np.r_[0, hr[1:] - hr[:-1]]
    return same, gap


class Tracker:
    """fit(cfg, D, tr) -> model; predict(model, D, idx) -> s (km). idx must hold whole fires, sorted by (fire, t)."""

    def __init__(self, name="TRACKER", cfg=None, update=True, fc=True):
        self.name, self.update, self.fc = name, update, fc
        self.configs = [dict(V0, **(cfg or {}))]
        self.last = None

    # ---- fit
    def fit(self, cfg, D, tr):
        z = D.z[tr]
        w = fire_weights(D.fid[tr])
        same, gap = _prev(D, tr)
        pair = same & (gap == 1)
        zp = np.r_[0, z[:-1]]
        m = {"cfg": cfg}
        feats = cfg["trans"] if self.fc else []
        X = trans_matrix(D, tr, feats)
        mu, sd = (X.mean(0), X.std(0) + 1e-9) if X.shape[1] else (np.zeros(0), np.ones(0))
        m["mu"], m["sd"] = mu, sd
        for key, sel in (("enter", pair & (zp == 0)), ("stay", pair & (zp == 1))):
            y, ww = z[sel], w[sel]
            rate = float((ww * y).sum() / ww.sum()) if sel.any() else 0.5
            rate = min(max(rate, 1e-4), 1 - 1e-4)
            if X.shape[1] == 0 or y.min() == y.max():
                m[key] = ("const", rate)
            else:
                lr = LogisticRegression(C=cfg["C"], max_iter=2000)
                lr.fit((X[sel] - mu) / sd, y, sample_weight=ww * len(ww) / ww.sum())
                m[key] = ("lr", lr.intercept_[0], lr.coef_[0].copy())
        # emission table
        b = np.digitize(D.X[cfg["obs"]][tr], cfg["bins"], right=True)
        nb = len(cfg["bins"]) + 1
        e = np.ones((2, nb))
        for s in (0, 1):
            e[s] += np.bincount(b[z == s], minlength=nb)
        m["emis"] = e / e.sum(1, keepdims=True)
        # state margins
        Xm = D.mat(cfg["mfeat"], tr)
        for s, leaf in ((0, cfg["leaf0"]), (1, cfg["leaf1"])):
            sel = z == s
            if sel.sum() < 4 * leaf:
                m[f"m{s}"] = ("const", float(np.quantile(D.S[tr][sel], cfg["tau"])) if sel.any() else RUN_KM)
            else:
                g = HistGradientBoostingRegressor(loss="quantile", quantile=cfg["tau"], max_depth=cfg["depth"],
                                                  learning_rate=0.05, max_iter=cfg["iters"], min_samples_leaf=leaf,
                                                  random_state=20261119, early_stopping=False)
                g.fit(Xm[sel], D.S[tr][sel])
                m[f"m{s}"] = ("gbm", g)
        if cfg["mix"] == "quantile":      # residual-ratio tables for the exact mixture quantile
            m["resid"] = [np.sort(D.S[tr][z == s] / np.maximum(self._margin(m, s, Xm[z == s]), S_FLOOR)) for s in (0, 1)]
        return m

    @staticmethod
    def _margin(m, s, Xm):
        k = m[f"m{s}"]
        return np.full(len(Xm), k[1]) if k[0] == "const" else k[1].predict(Xm)

    def _prob(self, m, key, Xs):
        k = m[key]
        if k[0] == "const":
            return np.full(len(Xs), k[1])
        return 1.0 / (1.0 + np.exp(-(k[1] + Xs @ k[2])))

    # ---- online filter
    def states(self, m, D, idx, margins=True):
        """Returns dict of arrays over idx: enter, stay, prior (p_t|t-1), p (after the update), m0, m1."""
        cfg = m["cfg"]
        feats = cfg["trans"] if self.fc else []
        Xs = (trans_matrix(D, idx, feats) - m["mu"]) / m["sd"]
        enter, stay = self._prob(m, "enter", Xs), self._prob(m, "stay", Xs)
        b = np.digitize(D.X[cfg["obs"]][idx], cfg["bins"], right=True)
        e0, e1 = m["emis"][0][b] ** cfg.get("temper", 1.0), m["emis"][1][b] ** cfg.get("temper", 1.0)
        same, gap = _prev(D, idx)
        n = len(idx)
        prior, p = np.zeros(n), np.zeros(n)
        pp = 0.0
        for i in range(n):
            if not same[i]:
                pp, k = 0.0, 1
            else:
                k = int(max(gap[i], 1))
            for _ in range(min(k, 48)):
                pp = pp * stay[i] + (1 - pp) * enter[i]
            prior[i] = pp
            if self.update:
                num = pp * e1[i]
                pp = num / (num + (1 - pp) * e0[i])
            p[i] = pp
        out = dict(enter=enter, stay=stay, prior=prior, p=p)
        if margins:
            Xm = D.mat(cfg["mfeat"], idx)
            out.update(m0=self._margin(m, 0, Xm), m1=self._margin(m, 1, Xm))
        return out

    def predict(self, m, D, idx):
        st = self.states(m, D, idx)
        self.last = st
        cfg = m["cfg"]
        p, m0, m1 = st["p"], np.maximum(st["m0"], S_FLOOR), np.maximum(st["m1"], S_FLOOR)
        if cfg["mix"] == "linear":
            return (1 - p) * m0 + p * m1
        if cfg["mix"] == "max":
            return np.maximum(m0, p * m1)
        if cfg["mix"] == "geometric":
            return np.exp((1 - p) * np.log(m0) + p * np.log(m1))
        if cfg["mix"] == "quantile":   # tau-quantile of the two-state mixture of (margin x residual ratio)
            r0, r1 = m["resid"]
            out = np.empty(len(p))
            lo, hi = np.minimum(m0, m1) * 0.0, np.maximum(m0 * r0[-1], m1 * r1[-1]) + 1e-6
            for _ in range(40):
                mid = (lo + hi) / 2
                F = (1 - p) * np.searchsorted(r0, mid / m0, side="right") / len(r0) + \
                    p * np.searchsorted(r1, mid / m1, side="right") / len(r1)
                up = F < cfg["tau"]
                lo, hi = np.where(up, mid, lo), np.where(up, hi, mid)
            out[:] = hi
            return out
        raise ValueError(cfg["mix"])


# -------------------------------------------------------------------- dev metrics (PROTOCOL section 4)
def local_day(D, idx, offset_h):
    return ((D.hour[idx] + offset_h) // 24).astype(np.int64)


def m2_warned(D, idx, score, offset_h=-8, far=0.10):
    """Share of run fire-days whose first run hour has score >= c; c = smallest threshold at which at most `far`
    of the fire-days without a run have any hour with score >= c. Returns (share, n_run_days, c, warned)."""
    df = pd.DataFrame(dict(f=D.fid[idx], d=local_day(D, idx, offset_h), h=D.hour[idx], z=D.z[idx], s=score))
    g = df.groupby(["f", "d"])
    run = g.z.max()
    mx = g.s.max()
    quiet_max = np.sort(mx[run == 0].values)
    nq = len(quiet_max)
    allowed = int(np.floor(far * nq))
    c = np.nextafter(quiet_max[nq - allowed - 1], np.inf) if allowed < nq else -np.inf
    first = df[df.z == 1].sort_values("h").groupby(["f", "d"]).first()
    warned = int((first.s >= c).sum())
    return warned / max(len(first), 1), int(len(first)), float(c), warned


def dev_cv(D, method, verbose=False):
    """4-fold by-fire CV on CA-DEV. Returns dict(M1 frontier area at 10%, calibrated area, miss, M2...)."""
    s, k, cfgs = run_outer(method, D, D.dev_folds, verbose=verbose)
    idx = D.rows_of(D.dev)
    fires, miss, area = evaluate(D, idx, s, k)
    out = dict(M1=frontier_read(miss, area), **boot_summary(miss, area))
    if isinstance(method, Tracker):
        # out-of-fold state probabilities for M2 (refit per fold, as in run_outer)
        p = np.full(len(D.S), np.nan)
        for kf in sorted(set(D.dev_folds.values())):
            te = D.rows_of([f for f in D.dev if D.dev_folds[f] == kf])
            tr = D.rows_of([f for f in D.dev if D.dev_folds[f] != kf])
            mdl = method.fit(method.configs[0], D, tr)
            p[te] = method.states(mdl, D, te)["p"]
        sh, n, c, w = m2_warned(D, idx, p[idx])
        out.update(M2=sh, run_days=n, warned=w, c=c)
    return out


# -------------------------------------------------------------------- all issue hours (no age filter), for Korea
class DataAll(Data):
    """kcf-adaptive2 Data without the 'at least 3 earlier hours' filter (needed for the alarm timeline of target A).
    self.elig marks the rows that kcf-adaptive2 calls eligible."""

    def __init__(self, h, work):
        from lib import ABSTAIN
        self.h = h
        g = pd.read_csv(Path(work) / "hours_geom.csv.gz")
        g["cidx"] = np.arange(len(g))
        cur = np.load(Path(work) / "areacurve.npy")
        f = pd.read_csv(ABSTAIN / "derived/hours.csv.gz", low_memory=False)
        f = f[f.role != "s3"][["fire", "product", "t_utc", "lat", "lon", "gust_ms", "w850_ms", "rhmin_pct", "hdw"]]
        m = g.merge(f, on=["fire", "product", "t_utc"], how="left")
        m["S"] = m[f"reach{h}_km"]
        hour = pd.to_datetime(m.t_utc).dt.hour + pd.to_datetime(m.t_utc).dt.minute / 60
        sol = (hour + m.lon / 15.0) % 24
        m["sin_h"] = np.sin(2 * np.pi * sol / 24)
        m["cos_h"] = np.cos(2 * np.pi * sol / 24)
        m["log_area"] = np.log1p(m.area_known_km2)
        m["log_age"] = np.log1p(m.age_h)
        ok = m.S.notna() & m[FC + ["lon"]].notna().all(axis=1)
        m = m[ok].sort_values(["fire", "t_utc", "product"]).reset_index(drop=True)
        self.df = m
        self.elig = (m.age_h >= 3).values
        self.S = m.S.values.astype(float)
        self.curve = np.concatenate([np.zeros((len(cur), 1), np.float32), cur], axis=1)[m.cidx.values]
        self.fire = m.fire.values
        self.product = m["product"].values
        self.fires = list(dict.fromkeys(self.fire))
        self.fid = np.array([self.fires.index(x) for x in self.fire])
        self.X = {c: m[c].values.astype(float) for c in ALL}
        self.t = pd.to_datetime(m.t_utc).values


def load_all(h=5):
    D = DataAll(h, WORK)
    D.hour = D.t.astype("datetime64[h]").astype(np.int64)
    D.z = (D.S > RUN_KM).astype(int)
    D.gofer = [f for f in D.fires if D.product[D.fire == f][0] == "GOFER"]
    fo = outer_folds(D.gofer)
    D.dev = [f for f in D.gofer if fo[f] in DEV_FOLDS]
    D.held = [f for f in D.gofer if fo[f] in HELD_FOLDS]
    D.kr = sorted(f for f in D.fires if str(f).startswith("KFS"))
    return D
