"""Sealed transfer test (PROTOCOL 1, 7): fit + calibrate every method on all 28 DEV fires, apply once to KR (Choi rasters,
12 Korean fires) and MAR25 (detection product, 25 March 2025). Run only after the DEV sweep is complete.

    python step2_final.py --h 5 --methods FIXED PERSIST ...
Output: derived/final/<method>_h<h>.npz with s, kappa for rows of products CHOI-KR and DET (nan elsewhere).
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import argparse, json, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from lib import *
from step2_run import registry


def job(args):
    name, h, work = args
    D = Data(h, work)
    dev = [f for f in D.fires if D.product[D.fire == f][0] == "GOFER"]
    t = time.time()
    m = registry()[name]()
    fit = fit_calibrate(m, D, dev)
    kr = np.flatnonzero([(p == "CHOI") and str(f).startswith("KFS") for p, f in zip(D.product, D.fire)])
    det = np.flatnonzero(D.product == "DET")
    rows = np.concatenate([kr, det])
    s = np.full(len(D.S), np.nan); s[rows] = fit.s(D, rows)
    return name, s, fit.kappa, fit.cfg, time.time() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--h", type=int, default=5)
    ap.add_argument("--work", default=os.environ.get("KCF2_WORK", "/tmp/w/work"))
    ap.add_argument("--methods", nargs="+", required=True)
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()
    out = Path("derived/final"); out.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(a.procs) as ex:
        for name, s, kap, cfg, dt in ex.map(job, [(m, a.h, a.work) for m in a.methods]):
            np.savez_compressed(out / f"{name}_h{a.h}.npz", s=s, kappa=np.array(kap))
            json.dump(dict(cfg=cfg, kappa=float(kap), seconds=round(dt, 1)), open(out / f"{name}_h{a.h}.json", "w"))
            print(f"{name} h{a.h} done {dt:.0f}s kappa={kap:.3f} cfg={cfg}", flush=True)


if __name__ == "__main__":
    main()
