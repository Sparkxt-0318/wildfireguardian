"""Pure-noise calibration of lag_persistence_v2 on the REAL fire structure (Iris, Owen).

The rank and log-ratio values of every fire are replaced by iid N(0, 1) draws. The same fires, interval counts, run
structure and interval indices as the real displacement file are kept. The exact procedure of lag_persistence_v2 is
then run (observed r minus the mean within-fire permutation null) for lag 1, 2, 3 and detrended lag 1. The mean
excess over --sims noise datasets must be about 0. A nonzero mean is a bias of the procedure, not a finding.

    python lag_null_probe.py --input results/displacement_mcem.json --out results/lag_null_probe.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

import lag_persistence_v2 as L


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--sims", type=int, default=300)
    ap.add_argument("--perms", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20261112)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    d = json.loads(a.input.read_text())
    res = {}
    for drop in (False, True):
        base = L.fire_series(d, np.random.default_rng(a.seed), drop)
        for lag, det in ((1, False), (2, False), (3, False), (1, True)):
            rng = np.random.default_rng([a.seed, lag, det, drop])
            fires = sorted(f for f in base if len(L.pairs_for(base[f], lag)))
            ex = []
            for _ in range(a.sims):
                per = {f: dict(base[f], rank=rng.normal(size=len(base[f]["rank"]))) for f in fires}
                obs = L.stat(per, fires, "rank", lag, det, False)
                null = np.mean([L.stat(per, fires, "rank", lag, det, False, rng) for _ in range(a.perms)])
                ex.append(obs - null)
            ex = np.array(ex)
            key = f"{'no_detached|' if drop else ''}lag{lag}{'_detrended' if det else ''}"
            res[key] = dict(fires=len(fires), excess_mean=float(ex.mean()), excess_sd=float(ex.std()),
                            se_of_mean=float(ex.std() / np.sqrt(len(ex))))
            print(key, {k: round(v, 4) if isinstance(v, float) else v for k, v in res[key].items()}, flush=True)
    a.out.write_text(json.dumps(dict(command="python lag_null_probe.py " + " ".join(argv or sys.argv[1:]),
                                     results=res), indent=1))


if __name__ == "__main__":
    main()
