"""Far share of the fitted kernel per estimator on the 25 part-a fires (reads results/real_bracket_fit.json).

far_share = Σ_(Chebyshev ≥ 2) k / Σ k over the 24 offsets of radius 2 (θ[0] is the background k0 and is excluded);
the same definition as run_shape_recovery.far_share. Reported: median, mean and IQR over fires, per estimator.
These are in-sample, per-fire fits (one kernel per fire).

    python real_far_share.py --fit results/real_bracket_fit.json --out results/real_far_share.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

import synthetic as S
from run_shape_recovery import far_share


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", type=Path, default=Path("results/real_bracket_fit.json"))
    ap.add_argument("--out", type=Path, default=Path("results/real_far_share.json"))
    a = ap.parse_args(argv)
    d = json.loads(a.fit.read_text())
    offs = S.offsets(2)
    res = {}
    for est in ("plugin", "bracket_composite", "meanfield_nll", "mcem"):
        v = np.array([far_share(f["estimators"][est]["theta"], offs) for f in d["fires"]])
        res[est] = dict(median=float(np.median(v)), mean=float(v.mean()), q25=float(np.percentile(v, 25)),
                        q75=float(np.percentile(v, 75)), per_fire={f["fire"]: float(x) for f, x in zip(d["fires"], v)})
    a.out.write_text(json.dumps(dict(command="python real_far_share.py " + " ".join(argv or sys.argv[1:]),
                                     fires=len(d["fires"]), results=res), indent=1))
    print({k: {kk: round(vv, 3) for kk, vv in v.items() if kk != "per_fire"} for k, v in res.items()})


if __name__ == "__main__":
    main()
