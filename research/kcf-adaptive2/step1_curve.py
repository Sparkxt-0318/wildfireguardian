"""Step 1(b): learning curve, held-out skill vs number of training fires (PROTOCOL 4.2). Writes derived/step1_curve.json."""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import json, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from lib import *
import methods_base as mb

NS = (4, 8, 12, 16, 20, 24)
NSUB = 10
WORK = "/tmp/w/work"


def task(args):
    n, k, sub = args
    D = Data(5, WORK)
    dev_f = [f for f in D.fires if D.product[D.fire == f][0] == "GOFER"]
    folds = outer_folds(dev_f)
    te_f = [f for f in dev_f if folds[f] == k]
    tr_all = sorted(f for f in dev_f if folds[f] != k)
    rng = np.random.default_rng(20261122 + 1000 * n + 10 * k + sub)
    tr_f = list(rng.choice(tr_all, size=n, replace=False)) if n < len(tr_all) else tr_all
    te = D.rows_of(te_f)
    out = {}
    for m in (mb.Fixed(), mb.Persist(), mb.mref()):
        fit = fit_calibrate(m, D, tr_f)
        s = fit.s(D, te)
        fl, miss, area = evaluate(D, te, _full(D, te, s), np.full(len(D.S), fit.kappa))
        out[m.name] = dict(fires=fl, miss=miss.tolist(), area=area.tolist())
    return n, k, sub, out


def _full(D, te, s):
    a = np.zeros(len(D.S)); a[te] = s; return a


def main():
    tasks = [(n, k, sub) for n in NS for k in range(7) for sub in range(NSUB if n < 24 else 1)]
    res = {}
    with ProcessPoolExecutor(4) as ex:
        for i, (n, k, sub, out) in enumerate(ex.map(task, tasks, chunksize=1)):
            res.setdefault(n, []).append((k, sub, out))
            if i % 20 == 0:
                print(i, len(tasks), flush=True)
    summ = {}
    for n, lst in res.items():
        summ[n] = {}
        nsub = max(s for _, s, _ in lst) + 1
        for name in ("FIXED", "PERSIST", "M_ref"):
            # per subset: pool the 28 fires' (miss, area) grids over folds; then average across subsets
            ms, as_ = [], []
            for sub in range(nsub):
                fl, mm, aa = [], [], []
                for k, s, out in lst:
                    if s == sub:
                        fl += out[name]["fires"]; mm.append(np.array(out[name]["miss"])); aa.append(np.array(out[name]["area"]))
                ms.append(np.concatenate(mm)); as_.append(np.concatenate(aa))
            ms = np.array(ms); as_ = np.array(as_)          # [sub, fires, L]
            summ[n][name] = dict(miss=ms[:, :, L1].mean(), area=as_[:, :, L1].mean(),
                                 frontier=float(np.mean([frontier_read(m, a) for m, a in zip(ms, as_)])),
                                 miss_per_sub=ms[:, :, L1].mean(1).tolist(), area_per_sub=as_[:, :, L1].mean(1).tolist(),
                                 area_per_fire=as_[:, :, L1].mean(0).tolist(), miss_per_fire=ms[:, :, L1].mean(0).tolist(),
                                 front_grid_miss=ms.mean((0, 1)).tolist(), front_grid_area=as_.mean((0, 1)).tolist())
        print(n, {k: (round(v["miss"], 4), round(v["area"], 1), round(v["frontier"], 1)) for k, v in summ[n].items()}, flush=True)
    json.dump({str(k): v for k, v in summ.items()}, open("derived/step1_curve.json", "w"))


if __name__ == "__main__":
    main()
