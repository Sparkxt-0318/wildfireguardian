"""Owen: independent re-aggregation of the S-D2 three-arm state family (RULE_state_family.md @ d0c7f0ad).

Written from the rule text, not from cv_state_family.py. numpy only for the arms and statistics.
Inputs: stage-1 per-fire grid checkpoints ({mcem,plugin}_fold{k}.fire{i}.npz with p_grid [8, cells], y, dist, n),
the committed pinned CV JSON (folds; per-fire plug-in / MCEM Brier and cell counts give the comparator SSE),
and logistic_cf per-fire SSE (from cv_baselines, verified in row 47) passed as a JSON {fire: sse}.

    python s-d2_state_family_aggregate_independent.py CKPT_DIR CV_PINNED.json LOGISTIC_SSE.json COMMITTED_RESULT.json
"""
import json
import sys
from pathlib import Path

import numpy as np

GRID = np.array([1 / 16, 1 / 8, 1 / 4, 1 / 2, 1, 2, 4, 8])
EPS = 1.0 / 513
RHOS, KAPPAS = (0, 0.25, 0.5, 0.75, 0.9), (1, 10, 100, 1000)


def bern_ll(p, y):
    p = np.clip(p, EPS, 1 - EPS)
    return np.where(y > 0, np.log(p), np.log(1 - p))


def per_interval(pg, y, n):
    """sum and mean log-likelihood per interval, for every grid value: shapes [J, 8]."""
    ll = bern_ll(pg, y[None, :])
    edges = np.concatenate([[0], np.cumsum(n)])
    s = np.stack([ll[:, edges[j]:edges[j + 1]].sum(1) for j in range(len(n))])
    return s, s / np.asarray(n)[:, None]


def em(L, iters=5000):
    pi = np.ones(L.shape[1]) / L.shape[1]
    for _ in range(iters):
        a = L + np.log(np.maximum(pi, 1e-300))
        a -= a.max(1, keepdims=True)
        r = np.exp(a)
        r /= r.sum(1, keepdims=True)
        new = r.mean(0)
        if np.max(np.abs(new - pi)) < 1e-13:
            break
        pi = new
    return new


def lag1_pred(pg, n, mean_ll, pi, rho, kappa):
    edges = np.concatenate([[0], np.cumsum(n)])
    out = np.empty(pg.shape[1])
    for j in range(len(n)):
        if j == 0:
            w = pi
        else:
            lq = np.log(np.maximum(pi, 1e-300)) + kappa * mean_ll[j - 1]
            q = np.exp(lq - lq.max())
            w = rho * q / q.sum() + (1 - rho) * pi
        out[edges[j]:edges[j + 1]] = w @ pg[:, edges[j]:edges[j + 1]]
    return out


def main(ckpt, cvp, lsse, committed):
    cv = json.loads(Path(cvp).read_text())
    log_sse = json.loads(Path(lsse).read_text())
    ref = json.loads(Path(committed).read_text())
    folds = cv["folds"]
    fires = [f for fs in folds for f in fs]
    G = {}
    for k, fs in enumerate(folds):
        for i, f in enumerate(fs):
            for kern in ("mcem", "plugin"):
                z = np.load(Path(ckpt) / f"{kern}_fold{k}.fire{i}.npz")
                G[kern, f] = (z["p_grid"].astype(np.float64), z["y"].astype(float), z["n"])
            assert np.array_equal(G["mcem", f][1], G["plugin", f][1]) and np.array_equal(G["mcem", f][2], G["plugin", f][2])
    LL = {key: per_interval(*G[key]) for key in G}
    sse = {"plugin": {}, "mcem": {}, "logistic_cf": {}, "persistence": {}}
    for f in fires:
        y, n = G["mcem", f][1], len(G["mcem", f][1])
        for m in ("plugin", "mcem"):
            pf = cv["per_fire"][f][m]
            assert pf["cells"] == n, (f, m, pf["cells"], n)
            sse[m][f] = pf["brier"] * n
        sse["logistic_cf"][f] = log_sse[f]
        sse["persistence"][f] = float(y.sum())
    for arm in ("mcem_state_wide", "plugin_state_wide", "mcem_lag1_wide"):
        sse[arm] = {}
    choice = {}
    for k, fs in enumerate(folds):
        other = [f for f in fires if f not in fs]
        pis = {kern: em(np.concatenate([LL[kern, f][0] for f in other])) for kern in ("mcem", "plugin")}
        for f in fs:
            for kern in ("mcem", "plugin"):
                pg, y, _ = G[kern, f]
                sse[f"{kern}_state_wide"][f] = float(((pis[kern] @ pg - y) ** 2).sum())
        best = max(((sum(bern_ll(lag1_pred(G["mcem", f][0], G["mcem", f][2], LL["mcem", f][1], pis["mcem"], r, kp),
                                 G["mcem", f][1]).sum() for f in other), r, kp) for r in RHOS for kp in KAPPAS))
        choice[k] = best[1:]
        for f in fs:
            pg, y, n = G["mcem", f]
            sse["mcem_lag1_wide"][f] = float(((lag1_pred(pg, n, LL["mcem", f][1], pis["mcem"], *best[1:]) - y) ** 2).sum())
    N = np.array([len(G["mcem", f][1]) for f in fires], float)
    E = {m: np.array([sse[m][f] for f in fires]) for m in sse}
    draws = np.random.default_rng(20261112).integers(0, len(fires), (10_000, len(fires)))
    flips = np.random.default_rng(20261112).choice([-1.0, 1.0], size=(10_000, len(fires)))
    worst = 0.0
    print("arm                    pooled    committed")
    for m in E:
        b = E[m].sum() / N.sum()
        c = ref["pooled"].get(m, {}).get("brier")
        worst = max(worst, abs(b - c)) if c is not None else worst
        print(f"{m:22s} {b:.6f}  {c}")
    qual = {}
    for arm in ("mcem_state_wide", "mcem_lag1_wide", "plugin_state_wide"):
        ok = True
        for r in ("plugin", "logistic_cf", "mcem", "persistence"):
            d = E[arm] - E[r]
            bs = d[draws].sum(1) / N[draws].sum(1)
            ci = np.percentile(bs, [2.5, 97.5])
            p = (1 + (np.abs((flips * d).sum(1)) >= abs(d.sum())).sum()) / 10_001
            c = ref["comparisons"][f"{arm}_minus_{r}"]
            print(f"{arm} - {r}: {d.sum() / N.sum():+.5f} [{ci[0]:+.5f}, {ci[1]:+.5f}] p {p:.4f} "
                  f"| committed {c['point']:+.5f} {c['ci95']} p {c['signflip_p']:.4f}")
            if r in ("plugin", "logistic_cf"):
                ok &= bool(ci[1] < 0 and p < 0.05 / 3)
        qual[arm] = ok
    print("lag1 choice", choice, "committed", ref["lag1_choice"])
    print("qualifies", qual, "committed", ref["qualifies"], "max |pooled diff|", worst)


if __name__ == "__main__":
    main(*sys.argv[1:5])
