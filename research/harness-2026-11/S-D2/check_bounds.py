"""Post-hoc bound check on the pooled CV fits (orchestrator's share rule, applied after the pinned run started).

Rule (stated before the pinned results are read):
- FLAG a fit if >= 50% of its parameters sit at the 1e-9 floor.
- A flagged fit FAILS if a restart of the same objective from x0 in {0.005, 0.08} (the default start is 0.02)
  reaches an objective lower by more than 1e-6 relative. Otherwise it is a genuine boundary optimum and PASSES with
  the flag recorded.
- Any all-at-floor fit fails outright; the in-run guard already raises on it.
Per-fire in-sample fits (real_bracket_fit.json, verified) often have >= 50% at the floor, because one fire carries
no information on many offsets. So the share alone is not treated as a failure.

    python check_bounds.py --cv results/cv_part_a_pinned.json --brackets DIR --out results/check_bounds_pinned.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

import cv_part_a as C
import real_bracket_fit as F
import runenv

FLOOR = 1e-9
STARTS = (0.005, 0.08)


def objective(name, fires):
    if name == "composite":
        objs = [C._composite_objective(p, o) for p, o in fires]
        return lambda th: (sum(o(th)[0] for o in objs), np.sum([o(th)[1] for o in objs], axis=0))
    return None   # other estimators: only the share is reported (their fitters are not plain L-BFGS objectives)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cv", type=Path, required=True)
    ap.add_argument("--brackets", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=240.0)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    runenv.require_pinned()
    cv = json.loads(a.cv.read_text())
    res = {}
    for k, ths in cv["thetas"].items():
        train = [f for f in sum(cv["folds"], []) if f not in cv["folds"][int(k)]]
        fires = None
        for name, th in ths.items():
            th = np.asarray(th)
            share = float(np.mean(th <= FLOOR * (1 + 1e-6)))
            r = dict(share_at_floor=share, flagged=share >= 0.5, all_at_floor=bool(share == 1.0))
            if r["all_at_floor"]:
                r["verdict"] = "FAIL (all at floor)"
            elif r["flagged"]:
                f = objective(name, fires or [F.load_fire(a.brackets / f"{x}.npz", a.hours, 0) for x in train])
                if f is None:
                    r["verdict"] = "FLAGGED (no restart test for this estimator)"
                else:
                    f0 = f(th)[0]
                    best = min(minimize(f, np.full(len(th), s), jac=True, method="L-BFGS-B",
                                        bounds=[(FLOOR, None)] * len(th),
                                        options=dict(maxiter=3000, ftol=1e-12, gtol=1e-9)).fun for s in STARTS)
                    r.update(objective=float(f0), best_restart=float(best))
                    r["verdict"] = "FAIL (restart better)" if best < f0 - 1e-6 * abs(f0) else "PASS (boundary optimum)"
            else:
                r["verdict"] = "PASS"
            res.setdefault(k, {})[name] = r
    a.out.write_text(json.dumps(dict(command="python check_bounds.py " + " ".join(argv or sys.argv[1:]),
                                     env=runenv.info(), results=res), indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
