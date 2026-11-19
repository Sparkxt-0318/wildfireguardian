"""Shared machinery for kcf-adaptive4 (PROTOCOL sections 1 to 6). No result is computed on import."""
import hashlib
from itertools import combinations
from math import factorial
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ABSTAIN = HERE.parent / "kcf-abstain"
WORK = HERE / "WORK"
CELL_KM = 0.375
NB = 160
TARGET = 0.10
TAU = 0.90
LEADS = np.arange(1, 9)
NL = 8
WIN = 8                       # hours in the forecast wind window (kcf-abstain)
RUN_KM = 3.75
OWN = ["g1", "g3", "g6", "g12", "g24", "log_area", "log_age", "sin_h", "cos_h"]
FC = ["gust_ms", "w850_ms", "rhmin_pct", "hdw"]
ALL = OWN + FC
TERMS = ("wind", "k", "start", "timing")
SEED = 20261119

CA_DEV_FOLDS = (0, 1, 2, 3)


def hash_rank(names):
    key = {n: int(hashlib.sha256(n.encode()).hexdigest(), 16) for n in names}
    order = sorted(names, key=lambda n: key[n])
    return {n: i for i, n in enumerate(order)}


# ------------------------------------------------------------------ data
class Fire:
    """One fire series on a dense hourly axis. Arrays are [T] or [T, 8]; NaN where there is no row."""

    def __init__(self, name, product, g, truth):
        self.name, self.product = name, product
        t = pd.to_datetime(g.t_utc)
        t0 = t.min()
        idx = ((t - t0) / pd.Timedelta(hours=1)).round().astype(int).values
        T = int(idx.max()) + 1
        self.T, self.t0 = T, t0
        self.t = t0 + pd.to_timedelta(np.arange(T), unit="h")
        self.has = np.zeros(T, bool)
        self.has[idx] = True

        def dense(col, fill=np.nan):
            a = np.full(T, fill, float)
            a[idx] = g[col].values.astype(float)
            return a

        self.S = np.column_stack([dense(f"reach{h}_km") for h in LEADS])
        if f"sreach1_km" in g and g["sreach1_km"].notna().any():
            self.Ss = np.column_stack([dense(f"sreach{h}_km") for h in LEADS])
            self.deficit = dense("start_deficit_km", 0.0)
            self.start_measurable = True
        else:
            self.Ss = self.S.copy()
            self.deficit = np.zeros(T)
            self.start_measurable = False
        self.X = {c: dense(c) for c in ALL}
        self.lon = float(g.lon.mean())
        self.cidx = np.full(T, -1, int)
        self.cidx[idx] = g.cidx.values
        self.age = dense("age_h")
        fc_ok = np.all([np.isfinite(self.X[c]) for c in FC], axis=0)
        self.elig = np.isfinite(self.S) & (self.age >= 3)[:, None] & fc_ok[:, None]
        # local solar day id
        sol = self.t + pd.to_timedelta(self.lon / 15.0, unit="h")
        self.day = np.asarray(sol.floor("D").astype("int64") // (86400 * 10 ** 9))
        kst = self.t + pd.Timedelta(hours=9)
        self.kst_day = np.asarray(kst.strftime("%Y-%m-%d"))
        self.kst_hour = np.asarray(kst.hour)
        # truth wind, hourly, on an axis from t0 - 24 h to t0 + T + 24 h
        tw = truth[truth.fire == name].copy()
        tw["t"] = pd.to_datetime(tw.t_utc)
        tw = tw.set_index("t")
        ax = pd.date_range(t0 - pd.Timedelta(hours=24), periods=T + 48, freq="1h")
        self.obs = {v: tw[c].reindex(ax).values.astype(float) for v, c in
                    (("gust_ms", "era5_gust_ms"), ("w850_ms", "hf_w850_ms"))}
        self.obs_off = 24

    def obs8(self, var):
        """Truth wind window (m/s) for every hour, cached."""
        if not hasattr(self, "_obs8"):
            self._obs8 = {}
        if var not in self._obs8:
            self._obs8[var] = np.array([self.obs_window(var, i) for i in range(self.T)])
        return self._obs8[var]

    def obs_window(self, var, i, upto=None):
        """Truth wind reduced like the forecast: max over hours i+1..i+8, optionally only hours <= upto."""
        a = self.obs[var]
        lo = i + 1 + self.obs_off
        hi = i + WIN + self.obs_off
        if upto is not None:
            hi = min(hi, upto + self.obs_off)
        if hi < lo:
            return np.nan
        seg = a[lo:hi + 1]
        return np.nan if np.isnan(seg).all() else float(np.nanmax(seg))


def load(work=WORK):
    """Returns dict name -> Fire for the sets 'CA' (GOFER), 'KR' (Choi), 'DET', and the area curves."""
    parts, curves, off = [], [], 0
    for s in ("gofer", "choi", "det"):
        if not (Path(work) / f"hours_geom_{s}.csv.gz").exists():
            continue
        g = pd.read_csv(Path(work) / f"hours_geom_{s}.csv.gz")
        c = np.load(Path(work) / f"areacurve_{s}.npy")
        g["cidx"] = np.arange(len(g)) + off
        off += len(g)
        parts.append(g)
        curves.append(c)
    g = pd.concat(parts, ignore_index=True)
    cur = np.concatenate(curves)
    curve = np.concatenate([np.zeros((len(cur), 1), np.float32), cur], axis=1)
    f = pd.read_csv(ABSTAIN / "derived/hours.csv.gz", low_memory=False)
    f = f[f.role != "s3"][["fire", "product", "t_utc", "lat", "lon"] + FC]
    m = g.merge(f, on=["fire", "product", "t_utc"], how="left")
    hour = pd.to_datetime(m.t_utc).dt.hour + pd.to_datetime(m.t_utc).dt.minute / 60
    sol = (hour + m.lon / 15.0) % 24
    m["sin_h"] = np.sin(2 * np.pi * sol / 24)
    m["cos_h"] = np.cos(2 * np.pi * sol / 24)
    m["log_area"] = np.log1p(m.area_known_km2)
    m["log_age"] = np.log1p(m.age_h)
    truth = pd.read_csv(HERE / "derived/truth_wind.csv.gz")
    fires = {"CA": {}, "KR": {}, "DET": {}}
    for (name, prod), gg in m.groupby(["fire", "product"], sort=True):
        key = {"GOFER": "CA", "CHOI": "KR", "DET": "DET"}[prod]
        gg = gg[gg.lon.notna()]
        if len(gg):
            fires[key][name] = Fire(name, prod, gg, truth)
    return fires, curve


def ca_split(fires_ca):
    r = hash_rank(list(fires_ca))
    fold = {n: r[n] % 7 for n in fires_ca}
    dev = sorted(n for n in fires_ca if fold[n] in CA_DEV_FOLDS)
    held = sorted(n for n in fires_ca if fold[n] not in CA_DEV_FOLDS)
    return dev, held, fold


def area_of(curve, cidx, q):
    """Flagged area km2 at margin q for curve rows cidx (linear between 0.375 km bins, cap 60 km)."""
    u = np.clip(np.asarray(q, float) / CELL_KM, 0, NB)
    lo = np.minimum(np.floor(u).astype(int), NB - 1)
    fr = u - lo
    c = curve[cidx]
    r = np.arange(len(cidx))
    return c[r, lo] * (1 - fr) + c[r, lo + 1] * fr


# ------------------------------------------------------------------ weighted statistics
def wquantile(r, w, p):
    """Smallest value v with weight(r > v)/total <= 1 - p."""
    o = np.argsort(r, kind="stable")
    r, w = r[o], w[o]
    c = np.cumsum(w) / w.sum()
    j = np.searchsorted(c, p - 1e-12, side="left")
    return float(r[min(j, len(r) - 1)])


def stack(fl, getter, h):
    """Concatenate per-fire arrays over eligible hours of lead index h. Returns values, fire weights, fire ids."""
    v, w, fid = [], [], []
    for k, f in enumerate(fl):
        e = f.elig[:, h]
        x = getter(f)[e]
        if len(x):
            v.append(x)
            w.append(np.full(len(x), 1.0 / len(x)))
            fid.append(np.full(len(x), k))
    if not v:
        return np.zeros(0), np.zeros(0), np.zeros(0, int)
    return np.concatenate(v), np.concatenate(w), np.concatenate(fid)


def kappa_for(fl, score, h, target=TARGET):
    """Smallest kappa with fire-weighted miss of q = kappa * score at most target (score: fire -> [T])."""
    r, w, _ = stack(fl, lambda f: f.S[:, h] / np.maximum(score(f), 1e-9), h)
    return wquantile(r, w, 1 - target)


def pinball(S, q, tau=TAU):
    d = S - q
    return np.where(d > 0, tau * d, (tau - 1) * d)


# ------------------------------------------------------------------ models (each returns fire -> q[T, 8])
def wind_kmh(f, var, truth=False):
    return (f.obs8(var) if truth else f.X[var]) * 3.6


def fit_base(train, var, truth=False):
    """k_h: fire-weighted pinball minimiser at tau 0.9 of S against k * W * h, then kappa to a 10% miss.
    truth=True fits the same model on the truth wind (hours without a truth value are left out)."""
    ks = np.zeros(NL)
    for h in range(NL):
        x, w, _ = stack(train, lambda f: wind_kmh(f, var, truth) * LEADS[h], h)
        S, _, _ = stack(train, lambda f: f.S[:, h], h)
        ok = np.isfinite(x) & (x > 0)
        if not ok.any():
            ks[h] = np.nan
            continue
        k0 = wquantile(S[ok] / x[ok], (w * x)[ok], TAU)   # pinball minimiser of a one-parameter line
        if k0 <= 0:
            k0 = 1e-6
        kap = wquantile(S[ok] / (k0 * x[ok]), w[ok], 1 - TARGET)
        ks[h] = k0 * kap if kap > 0 else k0
    return ks


def wind_scale(train, var, ks):
    """k fitted on the truth wind divided by k fitted on the forecast wind, per lead (PROTOCOL amendment 2)."""
    ko = fit_base(train, var, truth=True)
    return np.where(np.isfinite(ko), ko / np.asarray(ks), 1.0)


def fit_base_onek(train, var):
    """One k for all leads, calibrated on leads 1..8 pooled (fire-weighted over all eligible (t, h))."""
    r, w = [], []
    for f in train:
        e = f.elig
        x = wind_kmh(f, var)[:, None] * LEADS[None, :]
        if e.any():
            r.append((f.S / x)[e])
            w.append(np.full(e.sum(), 1.0 / e.sum()))
    return wquantile(np.concatenate(r), np.concatenate(w), 1 - TARGET)


def q_base(f, ks, var):
    return wind_kmh(f, var)[:, None] * LEADS[None, :] * np.asarray(ks)[None, :]


def fit_fixed(train):
    return np.array([kappa_for(train, lambda f: np.ones(f.T), h) for h in range(NL)])


def q_fixed(f, c):
    return np.broadcast_to(c[None, :], (f.T, NL)).copy()


def _mat(f, cols):
    return np.column_stack([f.X[c] for c in cols])


def fit_quantile(train, n_inner=4):
    """Gradient-boosted 0.9-quantile per lead on ALL features (kcf-adaptive2 chosen settings), kappa from
    by-fire out-of-fold scores, then refit on all training fires."""
    from sklearn.ensemble import HistGradientBoostingRegressor

    def gbm():
        return HistGradientBoostingRegressor(loss="quantile", quantile=0.9, max_depth=3, learning_rate=0.05,
                                             max_iter=100, min_samples_leaf=200, random_state=SEED,
                                             early_stopping=False)
    names = [f.name + "|" + f.product for f in train]
    r = hash_rank(names)
    grp = np.array([r[n] % n_inner for n in names])
    models = []
    for h in range(NL):
        oof = {}
        for g in range(n_inner):
            tr = [f for f, gg in zip(train, grp) if gg != g]
            va = [f for f, gg in zip(train, grp) if gg == g]
            if not va or not tr:
                continue
            X = np.concatenate([_mat(f, ALL)[f.elig[:, h]] for f in tr])
            y = np.concatenate([f.S[f.elig[:, h], h] for f in tr])
            m = gbm().fit(X, y)
            for f in va:
                s = np.full(f.T, np.nan)
                e = f.elig[:, h]
                if e.any():
                    s[e] = np.maximum(m.predict(_mat(f, ALL)[e]), 0.1)
                oof[id(f)] = s
        kap = kappa_for(train, lambda f: oof[id(f)], h)
        X = np.concatenate([_mat(f, ALL)[f.elig[:, h]] for f in train])
        y = np.concatenate([f.S[f.elig[:, h], h] for f in train])
        models.append((gbm().fit(X, y), kap))
    return models


def q_quantile(f, models):
    q = np.full((f.T, NL), np.nan)
    for h, (m, kap) in enumerate(models):
        e = f.elig[:, h]
        if e.any():
            q[e, h] = kap * np.maximum(m.predict(_mat(f, ALL)[e]), 0.1)
    return q


# ------------------------------------------------------------------ attribution (PROTOCOL section 3)
_SUBSETS = [c for r in range(5) for c in combinations(range(4), r)]
_SHAP_W = {(len(s)): factorial(len(s)) * factorial(4 - len(s) - 1) / factorial(4) for s in _SUBSETS if len(s) < 4}


def shapley(S, Ss, qpool, rW, rT, rWT, mk):
    """Exact Shapley shares of the four terms for arrays of misses.

    hold(T) = [S or Ss] <= qpool * [mk] * [1 | rW | rT | rWT]; terms ordered (wind, k, start, timing).
    Returns shares [n, 4] and v_all [n] (1 if all four swaps together give a hold)."""
    n = len(S)
    v = {}
    for sub in _SUBSETS:
        w, k, st, tm = (0 in sub), (1 in sub), (2 in sub), (3 in sub)
        fac = rWT if (w and tm) else rW if w else rT if tm else np.ones(n)
        q = qpool * fac * (mk if k else 1.0)
        v[sub] = ((Ss if st else S) <= q).astype(float)
    sh = np.zeros((n, 4))
    for i in range(4):
        for sub in _SUBSETS:
            if i in sub:
                continue
            wi = _SHAP_W[len(sub)]
            sh[:, i] += wi * (v[tuple(sorted(sub + (i,)))] - v[sub])
    return sh, v[(0, 1, 2, 3)]


def spearman(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 6:
        return np.nan
    ra = pd.Series(a[ok]).rank().values
    rb = pd.Series(b[ok]).rank().values
    if ra.std() == 0 or rb.std() == 0:
        return np.nan
    return float(np.corrcoef(ra, rb)[0, 1])


def best_lag(w, y, rows, maxlag=6, upto=None):
    """Lag d in -maxlag..maxlag maximising Spearman(w[rows + d], y[rows]); ties -> smallest |d|; undefined -> 0."""
    best, bd = -np.inf, 0
    for d in sorted(range(-maxlag, maxlag + 1), key=abs):
        j = rows + d
        ok = (j >= 0) & (j < len(w))
        if upto is not None:
            ok &= j <= upto
        if ok.sum() < 6:
            continue
        c = spearman(w[j[ok]], y[rows[ok]])
        if np.isfinite(c) and c > best + 1e-12:
            best, bd = c, d
    return bd


def offline_truths(f, ks, var, wscale):
    """Truth versions of the four terms for every (t, h) of one fire (uses the fire's future: ORACLE inputs).

    Returns dict of [T, 8] arrays: rW (truth wind / forecast wind), rT (lagged / unlagged forecast wind),
    rWT (lagged truth / forecast), mk (fire-day own k / pooled k), lag."""
    T = f.T
    W = wind_kmh(f, var)
    Wobs = f.obs8(var) * 3.6
    rW = (Wobs / W)[:, None] * np.asarray(wscale)[None, :]
    rT = np.ones((T, NL))
    rWT = rW.copy()
    mk = np.ones((T, NL))
    lag = np.zeros((T, NL), int)
    days = np.unique(f.day)
    for h in range(NL):
        e = f.elig[:, h]
        r = f.S[:, h] / (W * LEADS[h])
        for d in days:
            rows = np.flatnonzero(e & (f.day == d))
            if len(rows) == 0:
                continue
            dl = best_lag(W, f.S[:, h], rows)
            lag[rows, h] = dl
            j = np.clip(rows + dl, 0, T - 1)
            wl = np.where(np.isfinite(W[j]), W[j], W[rows])
            rT[rows, h] = wl / W[rows]
            wol = np.where(np.isfinite(Wobs[j]), Wobs[j], Wobs[rows])
            rWT[rows, h] = wscale[h] * wol / W[rows]
            allrows = np.flatnonzero(e)
            for i in rows:
                oth = rows[np.abs(rows - i) >= LEADS[h]]
                if len(oth) < 6:
                    oth = allrows[np.abs(allrows - i) >= LEADS[h]]
                if len(oth):
                    mk[i, h] = np.quantile(r[oth], 0.9, method="inverted_cdf") / ks[h]
    return dict(rW=rW, rT=rT, rWT=rWT, mk=mk, lag=lag, Wobs=Wobs)


# ------------------------------------------------------------------ online correction (PROTOCOL section 4)
def correct(f, ks, var, mode, L=12, H=6, return_state=False, wscale=None):
    """Sequential margins q[T, 8] for one fire. mode: 'none' | 'targeted' | 'all'.

    At hour i only outcomes of issues (j, h) with j + h <= i, truth wind for hours <= i and the start evidence at
    hours <= i are used."""
    T = f.T
    W = wind_kmh(f, var)
    wscale = np.ones(NL) if wscale is None else np.asarray(wscale)
    qpool = W[:, None] * LEADS[None, :] * np.asarray(ks)[None, :]
    if mode == "none":
        return (qpool, None) if return_state else qpool
    q = np.full((T, NL), np.nan)
    dec = 0.5 ** (1.0 / H)
    b, m, dadd, hold = 1.0, 1.0, 0.0, 0            # wind multiplier, k multiplier, start add (km), timing hold (h)
    state = np.zeros((T, 6))                        # b, m, dadd, hold, blamed (-1 none), n matured misses
    obs = f.obs[var]
    for i in range(T):
        j0 = max(0, i - L)
        js = np.arange(j0, i)
        blamed = -1
        nm = 0
        if len(js):
            hh = np.arange(NL)
            mat = (js[:, None] + LEADS[None, :] <= i) & f.elig[js]                 # matured and eligible
            if mat.any():
                jj, hi = np.nonzero(mat)
                jj = js[jj]
                S = f.S[jj, hi]
                Ss = np.where(f.start_measurable, f.Ss[jj, hi], S)
                qp = qpool[jj, hi]
                rho = S / qp
                miss = rho > 1
                nm = int(miss.sum())
                # online truths
                wobs = np.array([f.obs_window(var, int(j), upto=i) for j in np.unique(jj)]) * 3.6
                wmap = dict(zip(np.unique(jj).tolist(), wobs))
                rWj = wscale[hi] * np.array([wmap[int(j)] for j in jj]) / W[jj]
                rWj = np.where(np.isfinite(rWj), rWj, 1.0)
                # lag: correlate the wind term with the matured mean spread rate per issue hour
                uj = np.unique(jj)
                y = np.full(T, np.nan)
                for u in uj:
                    sel = jj == u
                    y[u] = np.mean(S[sel] / LEADS[hi[sel]])
                dl = best_lag(W, y, uj, upto=i) if len(uj) >= 6 else 0
                jl = np.clip(jj + dl, 0, i)
                wl = np.where(np.isfinite(W[jl]), W[jl], W[jj])
                rTj = wl / W[jj]
                rWTj = rWj * rTj
                if nm:
                    mi = np.flatnonzero(miss)
                    mk = np.ones(len(mi))
                    for a, x in enumerate(mi):
                        nov = (jj + LEADS[hi] <= jj[x]) | (jj >= jj[x] + LEADS[hi[x]])
                        if nov.sum() >= 6:
                            mk[a] = max(1.0, np.quantile(rho[nov], 0.9, method="inverted_cdf"))
                        else:
                            mk[a] = max(1.0, np.quantile(rho, 0.9, method="inverted_cdf"))
                    sh, _ = shapley(S[mi], Ss[mi], qp[mi], rWj[mi], rTj[mi], rWTj[mi], mk)
                    tot = sh.sum(0)
                    if tot.max() > 0:
                        blamed = int(np.argmax(tot))
                # window estimates of each correction
                full = jj + WIN <= i
                b_w = float(np.clip(np.mean(rWj[full]), 0.5, 3.0)) if full.any() else 1.0
                m_w = float(max(1.0, np.quantile(rho, 0.9, method="inverted_cdf")))
                d_w = float(f.deficit[i]) if f.start_measurable and np.isfinite(f.deficit[i]) else 0.0
                h_w = abs(int(dl))
                # decay everything, then refresh what this arm updates
                b = 1.0 + (b - 1.0) * dec
                m = 1.0 + (m - 1.0) * dec
                dadd *= dec
                hold = hold - 1 if hold > 0 else 0
                if mode == "all":
                    b, m, dadd, hold = b_w, max(m, m_w), max(dadd, d_w), max(hold, h_w)
                elif blamed == 0:
                    b = max(b, b_w)
                elif blamed == 1:
                    m = max(m, m_w)
                elif blamed == 2:
                    dadd = max(dadd, d_w)
                elif blamed == 3:
                    hold = max(hold, h_w)
        wt = W[i]
        if hold > 0:
            seg = W[max(0, i - hold):i + 1]
            if np.isfinite(seg).any():
                wt = np.nanmax(seg)
        q[i] = np.asarray(ks) * LEADS * wt * b * m + dadd
        state[i] = (b, m, dadd, hold, blamed, nm)
    q = np.where(np.isfinite(qpool), q, np.nan)
    return (q, state) if return_state else q


# ------------------------------------------------------------------ evaluation
def per_fire(fl, qs, curve, h, kappa=1.0):
    """Per fire: miss rate, mean area, mean pinball, mean shortfall on misses, mean excess on holds, n hours."""
    out = []
    for f, q in zip(fl, qs):
        e = f.elig[:, h] & np.isfinite(q[:, h])
        if not e.any():
            out.append((np.nan,) * 5 + (0,))
            continue
        S = f.S[e, h]
        qq = kappa * q[e, h]
        miss = S > qq
        ar = area_of(curve, f.cidx[e], np.minimum(qq, NB * CELL_KM))
        out.append((miss.mean(), ar.mean(), pinball(S, qq).mean(),
                    (S - qq)[miss].mean() if miss.any() else 0.0,
                    (qq - S)[~miss].mean() if (~miss).any() else 0.0, int(e.sum())))
    return np.array(out, float)


def boot(n, B=2000, seed=SEED):
    return np.random.default_rng(seed).integers(0, n, size=(B, n))


def ci(x, bi=None):
    """Mean over fires with a fire-bootstrap 95% interval (NaN fires dropped)."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return (np.nan, np.nan, np.nan)
    b = boot(len(x))
    m = x[b].mean(1)
    return float(x.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def ratio_ci(a, c):
    ok = np.isfinite(a) & np.isfinite(c)
    a, c = a[ok], c[ok]
    b = boot(len(a), seed=SEED + 1)
    r = a[b].mean(1) / c[b].mean(1)
    return float(a.mean() / c.mean()), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))


def diff_ci(a, c):
    ok = np.isfinite(a) & np.isfinite(c)
    d = (a - c)[ok]
    b = boot(len(d), seed=SEED + 2)
    m = d[b].mean(1)
    return float(d.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def frontier_area(fl, qs, curve, h, target=TARGET):
    """Area at exactly `target` held-out miss, by sweeping a common scale (descriptive)."""
    lams = np.exp(np.linspace(np.log(0.1), np.log(10.0), 93))
    ms, ars = [], []
    for lam in lams:
        pf = per_fire(fl, qs, curve, h, lam)
        ms.append(np.nanmean(pf[:, 0]))
        ars.append(np.nanmean(pf[:, 1]))
    ms, ars = np.array(ms), np.array(ars)
    if ms.min() > target or ms.max() < target:
        return np.nan
    o = np.argsort(ms)
    return float(np.interp(target, ms[o], ars[o]))
