"""Build a fit file in the real_bracket_fit.json layout in which each fire's thetas are its LEAVE-FIRE-OUT kernels.

Each fire gets the pooled kernels fitted on the other four folds in results/cv_part_a.json. The fire order is
kept from real_bracket_fit.json, so displacement_diag's per-fire simulation seeds (5150 + i) are unchanged and the
only difference from the in-sample run is the kernel (Iris's point 2: in-sample kernels absorb each fire's level).

    python fold_kernel_fit.py --fit results/real_bracket_fit.json --cv results/cv_part_a.json \
        --out results/fold_kernel_fit.json
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

NAME = {"plugin": "plugin", "bracket_composite": "composite", "meanfield_nll": "meanfield_nll", "mcem": "mcem"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", type=Path, required=True)
    ap.add_argument("--cv", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    fit, cv = json.loads(a.fit.read_text()), json.loads(a.cv.read_text())
    fold_of = {f: k for k, fs in enumerate(cv["folds"]) for f in fs}
    out = copy.deepcopy(fit)
    for fr in out["fires"]:
        k = str(fold_of[fr["fire"]])
        for est, cvname in NAME.items():
            fr["estimators"][est] = dict(theta=cv["thetas"][k][cvname], source=f"cv fold {k} (held out)")
        fr["fold"] = int(k)
    out["kernels"] = "leave-fire-out pooled kernels from " + str(a.cv)
    out["command"] = "python fold_kernel_fit.py " + " ".join(argv or sys.argv[1:])
    a.out.write_text(json.dumps(out, indent=1))
    print(len(out["fires"]), "fires written")


if __name__ == "__main__":
    main()
