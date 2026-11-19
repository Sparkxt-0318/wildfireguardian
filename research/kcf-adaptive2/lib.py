"""Shared machinery for kcf-adaptive2 (PROTOCOL sections 1-3). No result is computed here."""
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ABSTAIN = HERE.parent / "kcf-abstain"
CELL_KM = 0.375
NB = 160
TARGET = 0.10
S_FLOOR = 0.1          # km; scores s_t are floored here so that S/s is defined (PROTOCOL amendment 2)
LAMS = np.exp(np.linspace(np.log(0.25), np.log(4.0), 41))   # sweep multipliers for kappa; LAMS[20] == 1
L1 = 20

OWN = ["g1", "g3", "g6", "g12", "g24", "log_area", "log_age", "sin_h", "cos_h"]
FC = ["gust_ms", "w850_ms", "rhmin_pct", "hdw"]
ALL = OWN + FC


class Data:
    """Eligible issue hours for one horizon, all products, sorted by (fire, t)."""

    def __init__(self, h, work):
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
        ok = m.S.notna() & (m.age_h >= 3) & m[FC + ["lon"]].notna().all(axis=1)
        m = m[ok].sort_values(["fire", "t_utc"]).reset_index(drop=True)
        self.df = m
        self.S = m.S.values.astype(float)
        self.curve = np.concatenate([np.zeros((len(cur), 1), np.float32), cur], axis=1)[m.cidx.values]  # n x (NB+1)
        self.fire = m.fire.values
        self.product = m["product"].values
        self.fires = list(dict.fromkeys(self.fire))
        self.fid = np.array([self.fires.index(x) for x in self.fire])
        self.X = {c: m[c].values.astype(float) for c in ALL}
        self.t = pd.to_datetime(m.t_utc).values

    def mat(self, cols, idx=None):
        a = np.column_stack([self.X[c] for c in cols])
        return a if idx is None else a[idx]

    def rows_of(self, fires):
        s = set(fires)
        return np.flatnonzero([f in s for f in self.fire])

    def area(self, idx, q):
        """Flagged area km2 for margin q (km) at rows idx; exact curve, linear between 0.375 km bins, cap 60 km."""
        u = np.clip(np.asarray(q, float) / CELL_KM, 0, NB)
        lo = np.minimum(np.floor(u).astype(int), NB - 1)
        fr = u - lo
        c = self.curve[idx]
        r = np.arange(len(idx))
        return c[r, lo] * (1 - fr) + c[r, lo + 1] * fr


def hash_rank(names):
    key = {n: int(hashlib.sha256(n.encode()).hexdigest(), 16) for n in names}
    order = sorted(names, key=lambda n: key[n])
    return {n: i for i, n in enumerate(order)}


def outer_folds(fires, k=7):
    r = hash_rank(list(fires))
    return {n: r[n] % k for n in fires}


def fire_weights(fid):
    """Weight 1/n_f per row so that each fire counts once; returns weights normalised to sum to n_fires."""
    cnt = np.bincount(fid)
    return 1.0 / cnt[fid]


def wquantile_upper(r, w, p):
    """Smallest k with weight(r > k)/total <= 1 - p  (the p-quantile from below)."""
    o = np.argsort(r, kind="stable")
    r, w = r[o], w[o]
    c = np.cumsum(w) / w.sum()
    j = np.searchsorted(c, p - 1e-12, side="left")
    return r[min(j, len(r) - 1)]


def kappa_for(S, s, fid, target=TARGET):
    """Smallest kappa with fire-weighted miss rate of q = kappa * s at most `target`."""
    r = S / np.maximum(s, S_FLOOR)
    return float(wquantile_upper(r, fire_weights(fid), 1 - target))


def per_fire_grid(D, idx, s, kappa, lams=LAMS):
    """Per fire (in idx), miss rate and mean area at q = lam * kappa * s for each lam. Returns fires, miss[F,L], area[F,L]."""
    fid = D.fid[idx]
    fl = np.unique(fid)
    S = D.S[idx]
    miss = np.zeros((len(fl), len(lams)))
    area = np.zeros((len(fl), len(lams)))
    for j, lam in enumerate(lams):
        q = lam * kappa * s
        mi = (S > q).astype(float)
        ar = D.area(idx, np.minimum(q, NB * CELL_KM))
        for i, f in enumerate(fl):
            sel = fid == f
            miss[i, j] = mi[sel].mean()
            area[i, j] = ar[sel].mean()
    return [D.fires[f] for f in fl], miss, area


def frontier_read(miss, area, target=TARGET):
    """Area at held-out miss == target by linear interpolation along the lam sweep (fire-weighted means)."""
    m = miss.mean(0)
    a = area.mean(0)
    if m.min() > target or m.max() < target:
        return np.nan
    o = np.argsort(m)
    return float(np.interp(target, m[o], a[o]))


def boot_idx(n, B, seed):
    rng = np.random.default_rng(seed)
    return rng.integers(0, n, size=(B, n))


def boot_summary(miss, area, B=2000, seed=20261119):
    """miss, area: [F,L] per-fire; returns dict with point and percentile intervals at lam=1 (index L1)."""
    F = miss.shape[0]
    bi = boot_idx(F, B, seed)
    m = miss[bi, L1].mean(1)
    a = area[bi, L1].mean(1)
    return dict(miss=float(miss[:, L1].mean()), miss_lo=float(np.percentile(m, 2.5)), miss_hi=float(np.percentile(m, 97.5)),
                area=float(area[:, L1].mean()), area_lo=float(np.percentile(a, 2.5)), area_hi=float(np.percentile(a, 97.5)),
                frontier_area=frontier_read(miss, area), n_fires=int(F))


def ratio_ci(area_m, area_c, B=2000, seed=20261120, ratio_of_means=True):
    """Paired fire bootstrap of mean(area_m)/mean(area_c). area_*: per-fire arrays on the same fires."""
    F = len(area_m)
    bi = boot_idx(F, B, seed)
    r = area_m[bi].mean(1) / area_c[bi].mean(1)
    return float(area_m.mean() / area_c.mean()), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))


def verdict(sm, ratio, lo, hi):
    valid = abs(sm["miss"] - TARGET) <= 0.03 and sm["miss_lo"] <= TARGET <= sm["miss_hi"]
    if not valid:
        return "trade-off" if ratio < 1 and sm["miss"] > TARGET else "miss not at target"
    if hi < 1.0:
        return "helps (material)" if ratio <= 0.90 else "helps"
    return "does not help"


# ---------------------------------------------------------------- generic nested fit / calibrate
class Fitted:
    def __init__(self, method, cfg, model, kappa, oof_area):
        self.method, self.cfg, self.model, self.kappa, self.oof_area = method, cfg, model, kappa, oof_area

    def s(self, D, idx):
        return np.maximum(self.method.predict(self.model, D, idx), S_FLOOR)

    def q(self, D, idx):
        return self.kappa * self.s(D, idx)


def inner_groups(fires, k):
    r = hash_rank(list(fires))
    return {n: r[n] % k for n in fires}


def fit_calibrate(method, D, train_fires, k_inner=6, return_oof=False):
    """Nested: choose cfg by by-fire inner CV on `train_fires`, calibrate kappa on the OOF scores, refit on all."""
    tr = D.rows_of(train_fires)
    k = min(k_inner, len(train_fires))
    grp = inner_groups(train_fires, k)
    g_of_row = np.array([grp[f] for f in D.fire[tr]])
    best = None
    for cfg in method.configs:
        oof = np.zeros(len(tr))
        for g in range(k):
            va = g_of_row == g
            if not va.any() or va.all():
                continue
            model = method.fit(cfg, D, tr[~va])
            oof[va] = np.maximum(method.predict(model, D, tr[va]), S_FLOOR)
        kap = kappa_for(D.S[tr], oof, D.fid[tr])
        ar = D.area(tr, np.minimum(kap * oof, NB * CELL_KM))
        w = fire_weights(D.fid[tr])
        crit = float((ar * w).sum() / w.sum())
        if best is None or crit < best[0] - 1e-12:
            best = (crit, cfg, kap, oof)
    crit, cfg, kap, oof = best
    model = method.fit(cfg, D, tr)
    f = Fitted(method, cfg, model, kap, crit)
    if return_oof:
        return f, tr, oof
    return f


def run_outer(method, D, folds, fold_ids=None, k_inner=6, verbose=True):
    """Pooled held-out result over the outer folds. Returns per-row s (held-out), kappa per row, fitted configs."""
    s_all = np.full(len(D.S), np.nan)
    k_all = np.full(len(D.S), np.nan)
    cfgs = {}
    dev = [f for f in D.fires if folds.get(f) is not None]
    for k in sorted(set(folds.values())) if fold_ids is None else fold_ids:
        te_f = [f for f in dev if folds[f] == k]
        tr_f = [f for f in dev if folds[f] != k]
        fit = fit_calibrate(method, D, tr_f, k_inner)
        te = D.rows_of(te_f)
        s_all[te] = fit.s(D, te)
        k_all[te] = fit.kappa
        cfgs[int(k)] = dict(cfg=fit.cfg, kappa=fit.kappa, train_area=fit.oof_area)
        if verbose:
            print(f"  [{method.name}] fold {k} cfg={fit.cfg} kappa={fit.kappa:.3f}", flush=True)
    return s_all, k_all, cfgs


def evaluate(D, idx, s, kappa_row):
    """Per-fire miss/area grids for held-out rows; kappa is per row (it varies by outer fold)."""
    fid = D.fid[idx]
    fl = np.unique(fid)
    S = D.S[idx]
    miss = np.zeros((len(fl), len(LAMS)))
    area = np.zeros((len(fl), len(LAMS)))
    for j, lam in enumerate(LAMS):
        q = lam * kappa_row[idx] * s[idx]
        mi = (S > q).astype(float)
        ar = D.area(idx, np.minimum(q, NB * CELL_KM))
        for i, f in enumerate(fl):
            sel = fid == f
            miss[i, j] = mi[sel].mean()
            area[i, j] = ar[sel].mean()
    return [D.fires[f] for f in fl], miss, area
