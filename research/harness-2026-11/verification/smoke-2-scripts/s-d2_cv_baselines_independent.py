"""Owen: independent baseline reconstruction for cv_baselines (persistence, dilation_k, dilation_best, logistic_cf)."""
import json, sys, numpy as np
from pathlib import Path
from scipy.ndimage import distance_transform_edt
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, str(Path(sys.argv[1]).resolve().parents[2] / "forecast"))
import real_bracket_fit as F, synthetic as S
from wildfire.baselines import dilation, choose_dilation, fit_logistic, predict_logistic
BR, CV, OUT = Path(sys.argv[2]), json.load(open(sys.argv[3])), sys.argv[4]
CELL, BAND = 375.0, 4000.0
def cells(f):
    p, obs = F.load_fire(BR / f"{f}.npz", 240.0, 0); z = np.load(BR / f"{f}.npz"); h, w = z["first_survey"].shape
    real = np.zeros((p.n, p.n), bool); real[:h, :w] = True; real = real.ravel()
    hi = np.where(obs["burned"], obs["hi"], S.INF); out = []
    for a, b in zip(obs["surveys"][:-1], obs["surveys"][1:]):
        st = hi <= a
        if not st.any(): continue
        dgrid = distance_transform_edt(~st.reshape(p.n, p.n)).ravel()
        pop = real & ~st & (dgrid * CELL <= BAND)
        out.append(dict(st=st.reshape(p.n, p.n), pop=pop, y=((hi > a) & (hi <= b))[pop].astype(float), d=dgrid[pop], T=float(b - a)))
    return out
folds = CV["folds"]; allf = sum(folds, []); C = {f: cells(f) for f in allf}
def X(rows): return np.concatenate([np.stack([np.log1p(np.minimum(r["d"], 40)), np.minimum(r["d"], 40) / max(r["T"], 1e-9), np.full(len(r["d"]), np.log(r["T"]))], 1) for r in rows])
def dil(rows, k): return np.concatenate([dilation(r["st"], r["T"], k).ravel()[r["pop"]] for r in rows])
res = {}
for k, fs in enumerate(folds):
    tr = [f for f in allf if f not in fs]; ytr = np.concatenate([r["y"] for f in tr for r in C[f]])
    sc = {kk: float(np.mean((np.concatenate([dil(C[f], kk) for f in tr]) - ytr) ** 2)) for kk in (1, 2, 4, 8)}
    kb = choose_dilation(sc); lg = fit_logistic(np.concatenate([X(C[f]) for f in tr]), ytr, seed=0)
    for f in fs:
        rows = C[f]; y = np.concatenate([r["y"] for r in rows]); dm = np.concatenate([r["d"] for r in rows]) * CELL
        preds = {"persistence": np.zeros(len(y)), "dilation_8h": dil(rows, 8), "dilation_best": dil(rows, kb), "logistic_cf": predict_logistic(lg, X(rows))}
        res[f] = {"n": int(len(y)), "pos": int(y.sum()), "kbest": kb,
                  "err": {m: float(np.sum((p - y) ** 2)) for m, p in preds.items()},
                  "band": {m: [float(np.sum(((p - y) ** 2)[(dm > lo) & (dm <= hi)])) for lo, hi in ((0, 1000), (1000, 2000), (2000, 4000))] for m, p in preds.items()}}
    print("fold", k, "kbest", kb, flush=True)
json.dump(res, open(OUT, "w"))
