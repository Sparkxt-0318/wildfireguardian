"""Step-2 methods (PROTOCOL section 5). Every method: name, configs, fit(cfg, D, tr) -> model, predict(model, D, idx) -> s (km).
Sequential (adaptive) methods use only outcomes S_j with t_j + h <= t_i at row i (PROTOCOL 2.2)."""
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge

from lib import ALL, FC, OWN, S_FLOOR, fire_weights

FS = {"own": OWN, "fc": FC, "all": ALL}
Z90 = 1.2815515655446004
EPS = 0.375


# ------------------------------------------------------------------ 3. QUANTILE
class Quantile:
    """Gradient-boosted (and linear) quantile regression of S on a feature set."""
    name = "QUANTILE"

    def __init__(self, name="QUANTILE", configs=None):
        self.name = name
        if configs is None:
            configs = [dict(kind="gbm", fs=fs, tau=tau, depth=d, iters=it) for fs in ("own", "fc", "all")
                       for tau in (0.8, 0.9, 0.95) for d in (2, 3) for it in (100, 300)]
            configs += [dict(kind="lin", fs=fs, tau=tau) for fs in ("own", "fc", "all") for tau in (0.8, 0.9, 0.95)]
        self.configs = configs

    def fit(self, cfg, D, tr):
        cols = FS[cfg["fs"]]
        X = D.mat(cols, tr)
        y = D.S[tr]
        if cfg["kind"] == "gbm":
            m = HistGradientBoostingRegressor(loss="quantile", quantile=cfg["tau"], max_depth=cfg["depth"], learning_rate=0.05,
                                              max_iter=cfg["iters"], min_samples_leaf=200, random_state=20261119,
                                              early_stopping=False)
            m.fit(X, y)
            return ("gbm", cols, m)
        import statsmodels.api as sm
        mu, sd = X.mean(0), X.std(0) + 1e-9
        res = sm.QuantReg(y, np.column_stack([np.ones(len(X)), (X - mu) / sd])).fit(q=cfg["tau"], max_iter=500)
        return ("lin", cols, (mu, sd, res.params))

    def predict(self, model, D, idx):
        kind, cols, m = model
        X = D.mat(cols, idx)
        if kind == "gbm":
            return m.predict(X)
        mu, sd, p = m
        return np.column_stack([np.ones(len(X)), (X - mu) / sd]) @ p


# ------------------------------------------------------------------ 4. REGIME
class Tails:
    """Fire-weighted tail probabilities of the four issued-forecast variables, from training rows."""

    def __init__(self, D, tr):
        w = fire_weights(D.fid[tr])
        w = w / w.sum()
        self.t = []
        for c, sign in (("gust_ms", 1), ("w850_ms", 1), ("hdw", 1), ("rhmin_pct", -1)):
            v = sign * D.X[c][tr]
            o = np.argsort(v)
            self.t.append((c, sign, v[o], np.cumsum(w[o])))

    def z(self, D, idx):
        out = np.ones(len(idx))
        for c, sign, v, cw in self.t:
            x = sign * D.X[c][idx]
            # share of training hours with value >= x (at least as dangerous)
            k = np.searchsorted(v, x, side="left")
            p = 1.0 - np.where(k > 0, cw[np.maximum(k - 1, 0)], 0.0)
            out = np.minimum(out, p)
        return out


class Regime:
    """Two regimes chosen by the issued forecast only (never the fire's own past): s = 1 or m."""

    def __init__(self, name="REGIME", own=False):
        self.name, self.own = name, own
        self.configs = [dict(c=c, m=m) for c in (0.005, 0.01, 0.02, 0.05, 0.1, 0.2) for m in (1, 1.5, 2, 3, 5)]

    def fit(self, cfg, D, tr):
        tails = Tails(D, tr)
        body = None
        if self.own:
            body = HistGradientBoostingRegressor(loss="quantile", quantile=0.9, max_depth=2, learning_rate=0.05, max_iter=100,
                                                 min_samples_leaf=200, random_state=20261119, early_stopping=False)
            body.fit(D.mat(OWN, tr), D.S[tr])
        return dict(cfg=cfg, tails=tails, body=body)

    def predict(self, model, D, idx):
        z = model["tails"].z(D, idx)
        mult = np.where(z <= model["cfg"]["c"], model["cfg"]["m"], 1.0)
        base = np.ones(len(idx)) if model["body"] is None else np.maximum(model["body"].predict(D.mat(OWN, idx)), S_FLOOR)
        return base * mult


# ------------------------------------------------------------------ shared: per-fire sequential helpers
def fire_slices(D, idx):
    """Yield (positions into idx, rows of D) per fire, in time order (D is sorted by fire, t)."""
    fid = D.fid[idx]
    order = np.argsort(fid, kind="stable")
    sf = fid[order]
    cuts = np.flatnonzero(np.diff(sf)) + 1
    for part in np.split(order, cuts):
        part = part[np.argsort(idx[part], kind="stable")]
        yield part, idx[part]


def hours_of(D, rows):
    return (D.t[rows].astype("datetime64[h]").astype(np.int64))


# ------------------------------------------------------------------ 2. KALMAN
class Kalman:
    """Per-fire 3-parameter Kalman adaptation of a global ridge model of log(S + 0.375) (PROTOCOL 5.2 item 2)."""

    def __init__(self, name="KALMAN", adapt=True):
        self.name, self.adapt = name, adapt
        self.configs = [dict(ridge=r, Q=q) for r in (0.1, 1.0, 10.0) for q in (1e-4, 1e-3, 1e-2)]

    def fit(self, cfg, D, tr):
        X = D.mat(ALL, tr)
        mu, sd = X.mean(0), X.std(0) + 1e-9
        y = np.log(D.S[tr] + EPS)
        r = Ridge(alpha=cfg["ridge"]).fit((X - mu) / sd, y)
        res = y - r.predict((X - mu) / sd)
        w = np.log(D.X["w850_ms"][tr]); g = np.log1p(self._G(D, tr))
        return dict(cfg=cfg, mu=mu, sd=sd, ridge=r, R=float(res.var()), wm=(w.mean(), w.std() + 1e-9),
                    gm=(g.mean(), g.std() + 1e-9), P0=0.25)

    @staticmethod
    def _G(D, idx):
        return D.X["g3"][idx] * 5 / 3 if D.h == 5 else D.X["g6"][idx] * 8 / 6

    def _z(self, m, D, rows):
        w = (np.log(D.X["w850_ms"][rows]) - m["wm"][0]) / m["wm"][1]
        g = (np.log1p(self._G(D, rows)) - m["gm"][0]) / m["gm"][1]
        return np.column_stack([np.ones(len(rows)), w, g])

    def predict(self, m, D, idx, leak=False):
        out = np.zeros(len(idx))
        for pos, rows in fire_slices(D, idx):
            base = m["ridge"].predict((D.mat(ALL, rows) - m["mu"]) / m["sd"])
            Z = self._z(m, D, rows)
            y = np.log(D.S[rows] + EPS)
            th = np.zeros(3); P = np.eye(3) * m["P0"]
            Q = np.eye(3) * m["cfg"]["Q"]
            th_h = hours_of(D, rows)
            used = 0
            for i in range(len(rows)):
                if self.adapt:
                    lim = i + 1 if leak else i                      # leak=True: positive control (sees its own outcome)
                    while used < lim and (leak or th_h[used] + D.h <= th_h[i]):
                        z = Z[used]
                        P = P + Q
                        S_ = z @ P @ z + m["R"]
                        K = P @ z / S_
                        th = th + K * (y[used] - base[used] - z @ th)
                        P = P - np.outer(K, z) @ P
                        used += 1
                var = m["R"] + (Z[i] @ P @ Z[i] if self.adapt else 0.0)
                mu = base[i] + (Z[i] @ th if self.adapt else 0.0)
                out[pos[i]] = np.exp(mu + Z90 * np.sqrt(var)) - EPS
        return out


# ------------------------------------------------------------------ 1. META (Reptile)
def _init(arch, d, rng):
    if arch == "lin":
        return [np.zeros(d), np.zeros(())]
    return [rng.normal(0, 0.3, (d, 16)), np.zeros(16), rng.normal(0, 0.3, 16), np.zeros(())]


def _fwd(arch, p, X):
    if arch == "lin":
        return X @ p[0] + p[1], None
    h = np.tanh(X @ p[0] + p[1])
    return h @ p[2] + p[3], h


def _grad(arch, p, X, y, tau):
    f, h = _fwd(arch, p, X)
    df = ((f > y).astype(float) - tau) / len(y)
    if arch == "lin":
        return [X.T @ df, df.sum()]
    dh = np.outer(df, p[2]) * (1 - h ** 2)
    return [X.T @ dh, dh.sum(0), h.T @ df, df.sum()]


def _copy(p):
    return [a.copy() for a in p]


def _sgd(arch, p, X, y, tau, steps, lr):
    p = _copy(p)
    for _ in range(steps):
        g = _grad(arch, p, X, y, tau)
        for a, b in zip(p, g):
            a -= lr * b
    return p


class Meta:
    """Reptile meta-learning of a quantile model of log(S + 0.375); adapted every 6 h on the last 48 outcome-known hours."""

    def __init__(self, name="META", mode="meta"):
        self.name, self.mode = name, mode        # mode: "meta" (adapt), "init" (meta-init, no adaptation), "pooled"
        self.configs = [dict(tau=t, arch=a) for t in (0.8, 0.9, 0.95) for a in ("lin", "mlp")]

    _CACHE = {}

    def fit(self, cfg, D, tr):
        key = (cfg["arch"], cfg["tau"], self.mode == "pooled", tr.tobytes())
        if key not in Meta._CACHE:
            if len(Meta._CACHE) > 64:
                Meta._CACHE.clear()
            Meta._CACHE[key] = self._fit(cfg, D, tr)
        return Meta._CACHE[key]

    def _fit(self, cfg, D, tr):
        arch, tau = cfg["arch"], cfg["tau"]
        X = D.mat(ALL, tr); mu, sd = X.mean(0), X.std(0) + 1e-9
        Xs = (X - mu) / sd
        y = np.log(D.S[tr] + EPS)
        rng = np.random.default_rng(20261119)
        p = _init(arch, Xs.shape[1], rng)
        # pooled pinball pre-fit (Adam, full batch): the "pooled" twin and the starting point of Reptile
        mom = [np.zeros_like(a) for a in p]; v = [np.zeros_like(a) for a in p]
        if arch == "lin":
            p[1] = np.quantile(y, tau)
        else:
            p[3] = np.quantile(y, tau)
        for t in range(1, 401):
            g = _grad(arch, p, Xs, y, tau)
            for k, (a, b) in enumerate(zip(p, g)):
                mom[k] = 0.9 * mom[k] + 0.1 * b; v[k] = 0.999 * v[k] + 0.001 * b * b
                a -= 0.02 * (mom[k] / (1 - 0.9 ** t)) / (np.sqrt(v[k] / (1 - 0.999 ** t)) + 1e-8)
        if self.mode != "pooled":
            fires = np.unique(D.fid[tr])
            starts = {f: np.flatnonzero(D.fid[tr] == f) for f in fires}
            for it in range(2000):
                delta = [np.zeros_like(a) for a in p]
                for _ in range(8):
                    f = fires[rng.integers(len(fires))]
                    r = starts[f]
                    s0 = rng.integers(0, max(len(r) - 48, 1))
                    w = r[s0:s0 + 48]
                    q = _copy(p)
                    for _ in range(5):
                        b = w[rng.integers(0, len(w), 16)]
                        g = _grad(arch, q, Xs[b], y[b], tau)
                        for a, gg in zip(q, g):
                            a -= 0.01 * gg
                    for d_, a, b in zip(delta, q, p):
                        d_ += (a - b) / 8
                for a, d_ in zip(p, delta):
                    a += 0.1 * d_
        return dict(cfg=cfg, p=p, mu=mu, sd=sd)

    def predict(self, m, D, idx):
        arch, tau = m["cfg"]["arch"], m["cfg"]["tau"]
        out = np.zeros(len(idx))
        for pos, rows in fire_slices(D, idx):
            Xs = (D.mat(ALL, rows) - m["mu"]) / m["sd"]
            if self.mode != "meta":
                out[pos] = np.exp(_fwd(arch, m["p"], Xs)[0]) - EPS
                continue
            y = np.log(D.S[rows] + EPS)
            th = hours_of(D, rows)
            blk = (th - th[0]) // 6
            p = m["p"]
            for b in np.unique(blk):
                cur = np.flatnonzero(blk == b)
                t0 = th[cur[0]]
                known = np.flatnonzero((th + D.h <= t0) & (th > t0 - D.h - 48))
                q = _sgd(arch, p, Xs[known], y[known], tau, 5, 0.01) if len(known) >= 8 else p
                out[pos[cur]] = np.exp(_fwd(arch, q, Xs[cur])[0]) - EPS
        return out


# ------------------------------------------------------------------ 6. EVT
class EVT:
    """Hurdle + generalised Pareto tail (peaks over threshold) with covariate-dependent scale."""

    def __init__(self, name="EVT", const_scale=False):
        self.name, self.const = name, const_scale
        self.configs = [dict(u=u) for u in (1.5, 3.0)]
        self._body = {}

    def fit(self, cfg, D, tr):
        u = cfg["u"]
        X = D.mat(ALL, tr); mu, sd = X.mean(0), X.std(0) + 1e-9
        Xs = (X - mu) / sd
        S = D.S[tr]
        ev = S > u
        clf = LogisticRegression(C=1.0, max_iter=500).fit(Xs, ev)
        Xe = np.column_stack([np.ones(ev.sum()), Xs[ev]]); ye = S[ev] - u
        if self.const:
            Xe = Xe[:, :1]
        d = Xe.shape[1]

        def nll(par):
            b, a = par[:d], par[d]
            xi = 0.5 * expit(a) + 1e-6
            sig = np.exp(np.clip(Xe @ b, -8, 8))
            z = 1 + xi * ye / sig
            return float((np.log(sig) + (1 + 1 / xi) * np.log(z)).sum() + 0.5 * 1e-3 * (b[1:] ** 2).sum())

        x0 = np.zeros(d + 1); x0[0] = np.log(max(ye.mean(), 0.1)); x0[d] = -1.0
        res = minimize(nll, x0, method="L-BFGS-B", options=dict(maxiter=300))
        body = HistGradientBoostingRegressor(loss="quantile", quantile=0.9, max_depth=3, learning_rate=0.05, max_iter=300,
                                             min_samples_leaf=200, random_state=20261119, early_stopping=False).fit(X, S)
        return dict(cfg=cfg, mu=mu, sd=sd, clf=clf, par=res.x, d=d, body=body, n_exc=int(ev.sum()))

    def predict(self, m, D, idx):
        u = m["cfg"]["u"]
        X = D.mat(ALL, idx); Xs = (X - m["mu"]) / m["sd"]
        pu = m["clf"].predict_proba(Xs)[:, 1]
        d = m["d"]
        Xe = np.column_stack([np.ones(len(idx)), Xs])[:, :d]
        sig = np.exp(np.clip(Xe @ m["par"][:d], -8, 8))
        xi = 0.5 * expit(m["par"][d]) + 1e-6
        ratio = np.maximum(pu / 0.10, 1e-12)
        qt = u + sig / xi * (ratio ** xi - 1)
        body = np.minimum(u, m["body"].predict(X))
        return np.where(pu >= 0.10, qt, body)


# ------------------------------------------------------------------ 5. PRETRAIN (archive; simulated added later)
_PRE_CACHE = {}


class Pretrain:
    """M_ref pretrained on extra fires, then fine-tuned on the training DEV fires (warm start)."""

    def __init__(self, name, source_fn):
        self.name, self.source_fn = name, source_fn
        self.configs = [dict(tau=0.9, depth=3, iters=300, ft=50)]

    def _pre(self, D, key):
        if key not in _PRE_CACHE:
            Xp, yp = self.source_fn(D)
            m = HistGradientBoostingRegressor(loss="quantile", quantile=0.9, max_depth=3, learning_rate=0.05, max_iter=300,
                                              min_samples_leaf=200, random_state=20261119, early_stopping=False, warm_start=True)
            m.fit(Xp, yp)
            _PRE_CACHE[key] = m
        return _PRE_CACHE[key]

    def fit(self, cfg, D, tr):
        import copy
        m = copy.deepcopy(self._pre(D, self.name))
        m.set_params(max_iter=cfg["iters"] + cfg["ft"], learning_rate=0.02)
        m.fit(D.mat(ALL, tr), D.S[tr])
        return m

    def predict(self, m, D, idx):
        return m.predict(D.mat(ALL, idx))


def archive_source(D):
    rows = np.flatnonzero((D.product == "CHOI") & ~np.array([str(f).startswith("KFS") for f in D.fire]))
    return D.mat(ALL, rows), D.S[rows]
