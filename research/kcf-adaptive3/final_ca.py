#!/usr/bin/env python3
"""The one final California run (PROTOCOL section 4, last bullet; target C).

Every method is fitted and calibrated on CA-DEV (16 fires) and applied once to CA-HELD (12 fires).
    python3 final_ca.py            # reads derived/kept.json (the configuration kept by the agent loop)
Output: derived/final_ca.json, derived/final_ca_rows.csv.gz
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import json
import numpy as np
import pandas as pd
from lib3 import *
from lib import per_fire_grid
from methods_base import Fixed
from methods2 import Quantile


def variants(kept):
    noarch = dict(kept, trans=[f for f in kept["trans"] if f != "arch"])
    return [("FIXED", Fixed()), ("QUANTILE", Quantile()),
            ("TRACKER", Tracker("TRACKER", kept)),
            ("TRACKER-noupdate", Tracker("TRACKER-noupdate", kept, update=False)),
            ("TRACKER-nofc", Tracker("TRACKER-nofc", kept, fc=False)),
            ("TRACKER-noarchive", Tracker("TRACKER-noarchive", noarch))]


def main():
    out = HERE / "derived" / "final_ca.json"
    if out.exists():
        raise SystemExit("final_ca.json exists: the final run is made once (PROTOCOL section 4)")
    kept = json.load(open(HERE / "derived" / "kept.json"))["cfg"]
    D = load()
    te = D.rows_of(D.held)
    res, rows, grids = {}, pd.DataFrame(dict(fire=D.fire[te], t_utc=D.df.t_utc.values[te], S=D.S[te])), {}
    for name, m in variants(kept):
        fit = fit_calibrate(m, D, D.dev)
        s = fit.s(D, te)
        fires, miss, area = per_fire_grid(D, te, s, fit.kappa)
        grids[name] = (miss, area)
        r = boot_summary(miss, area)
        r.update(kappa=fit.kappa, cfg=fit.cfg, per_fire_area=dict(zip(fires, area[:, 20].round(3).tolist())),
                 per_fire_miss=dict(zip(fires, miss[:, 20].round(4).tolist())))
        rows[f"q_{name}"] = fit.kappa * s
        if isinstance(m, Tracker):
            st = m.last
            rows[f"p_{name}"] = st["p"]
            sh, n, c, w = m2_warned(D, te, st["p"])
            r.update(run_days=n, warned=w, warn_threshold=c)
        res[name] = r
        print(name, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k in
                     ("miss", "miss_lo", "miss_hi", "area", "frontier_area", "kappa", "run_days", "warned")}, flush=True)
    for a, b in (("TRACKER", "QUANTILE"), ("TRACKER", "FIXED"), ("QUANTILE", "FIXED"), ("TRACKER", "TRACKER-noupdate"),
                 ("TRACKER", "TRACKER-nofc"), ("TRACKER", "TRACKER-noarchive"), ("TRACKER-noupdate", "FIXED"),
                 ("TRACKER-nofc", "FIXED"), ("TRACKER-noarchive", "FIXED")):
        r, lo, hi = ratio_ci(grids[a][1][:, 20], grids[b][1][:, 20])
        res[f"ratio {a} / {b}"] = dict(ratio=r, lo=lo, hi=hi,
                                       frontier_ratio=res[a]["frontier_area"] / res[b]["frontier_area"])
    res["n_hours"] = int(len(te))
    res["fires"] = D.held
    json.dump(res, open(out, "w"), indent=1)
    rows.round(4).to_csv(HERE / "derived" / "final_ca_rows.csv.gz", index=False)


if __name__ == "__main__":
    main()
