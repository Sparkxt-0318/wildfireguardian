"""Run one method through the 7 outer DEV folds (nested fit/calibrate), save held-out scores. PROTOCOL 1, 3, 5.

    python step2_run.py --method QUANTILE --h 5 [--work /tmp/w/work]
Output: derived/step2/<method>_h<h>.npz (s, kappa per DEV row, nan elsewhere) and .json (chosen configs per fold).
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import argparse, json, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from lib import *
import methods_base as mb
import methods2 as m2


def registry():
    q = lambda fs: [dict(kind=k, fs=f, tau=t, **extra) for f in fs for k, t, extra in
                    [("gbm", tau, dict(depth=d, iters=it)) for tau in (0.8, 0.9, 0.95) for d in (2, 3) for it in (100, 300)]
                    + [("lin", tau, {}) for tau in (0.8, 0.9, 0.95)]]
    return {
        "FIXED": mb.Fixed, "PERSIST": mb.Persist, "M_ref": mb.mref,
        "QUANTILE": lambda: m2.Quantile("QUANTILE"),
        "QUANTILE-own": lambda: m2.Quantile("QUANTILE-own", q(["own"])),
        "QUANTILE-fc": lambda: m2.Quantile("QUANTILE-fc", q(["fc"])),
        "REGIME": lambda: m2.Regime("REGIME"),
        "REGIME+own": lambda: m2.Regime("REGIME+own", own=True),
        "KALMAN": lambda: m2.Kalman("KALMAN"),
        "KALMAN-twin": lambda: m2.Kalman("KALMAN-twin", adapt=False),
        "META": lambda: m2.Meta("META", "meta"),
        "META-init": lambda: m2.Meta("META-init", "init"),
        "META-pooled": lambda: m2.Meta("META-pooled", "pooled"),
        "EVT": lambda: m2.EVT("EVT"),
        "EVT-twin": lambda: m2.EVT("EVT-twin", const_scale=True),
        "PRETRAIN-archive": lambda: m2.Pretrain("PRETRAIN-archive", m2.archive_source),
    }


def fold_job(args):
    name, h, work, k = args
    D = Data(h, work)
    dev = [f for f in D.fires if D.product[D.fire == f][0] == "GOFER"]
    folds = outer_folds(dev)
    te_f = [f for f in dev if folds[f] == k]
    tr_f = [f for f in dev if folds[f] != k]
    m = registry()[name]()
    t = time.time()
    fit = fit_calibrate(m, D, tr_f)
    te = D.rows_of(te_f)
    return k, te, fit.s(D, te), fit.kappa, fit.cfg, fit.oof_area, time.time() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", required=True)
    ap.add_argument("--h", type=int, default=5)
    ap.add_argument("--work", default="/tmp/w/work")
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()
    D = Data(a.h, a.work)
    s = np.full(len(D.S), np.nan); kap = np.full(len(D.S), np.nan); cfgs = {}
    with ProcessPoolExecutor(a.procs) as ex:
        for k, te, sk, kk, cfg, crit, dt in ex.map(fold_job, [(a.method, a.h, a.work, k) for k in range(7)]):
            s[te] = sk; kap[te] = kk; cfgs[k] = dict(cfg=cfg, kappa=float(kk), train_area=float(crit), seconds=round(dt, 1))
            print(f"[{a.method} h{a.h}] fold {k} {dt:.0f}s cfg={cfg} kappa={kk:.3f}", flush=True)
    out = Path("derived/step2"); out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / f"{a.method}_h{a.h}.npz", s=s, kappa=kap)
    json.dump(cfgs, open(out / f"{a.method}_h{a.h}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
