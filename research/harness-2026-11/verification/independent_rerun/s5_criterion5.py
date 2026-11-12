#!/usr/bin/env python3
"""Independent criterion-5 read (Owen), numpy only, sharing no code with sd9bench, wildfire or freeze/criterion5.py.

Rule (STAGE2_PINS, Iris and orchestrator 16:40Z): in the 4 km band (dist_m <= 4000 m), the candidate's lowest bin
[0, 0.1) (cells with p < 0.1) must have |observed frequency - mean prediction| no larger than that of EACH of
persistence, dilation_8h and logistic_rebuilt. An empty candidate bin, or all three reference bins empty, is
NOT EVALUABLE and counts as not met. An empty single reference bin imposes no bound. The count is printed beside
each gap. Descriptive only: a whole-fire bootstrap 95% interval of Gap(cand) - Gap(ref)
(default_rng(seed).integers(0, n_fires, (draws, n_fires)), fires in sorted order), with the number of undefined draws.

    python s5_criterion5.py --candidate NAME [--compare C5.json] FILES.npz...
"""
import argparse, json, math, sys
from pathlib import Path
import numpy as np

REFS = ("persistence", "dilation_8h", "logistic_rebuilt")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--compare", type=Path)
    ap.add_argument("--draws", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261030)
    a = ap.parse_args(argv)
    names = (a.candidate,) + REFS
    fires = sorted(Path(f).stem for f in a.files)
    per = {m: np.zeros((len(fires), 3)) for m in names}  # count, sum p, sum y over p < 0.1
    for i, f in enumerate(sorted(a.files, key=lambda x: Path(x).stem)):
        with np.load(f, allow_pickle=False) as z:
            band = z["dist_m"].astype(np.float64) <= 4000.0
            y = z["y"].astype(np.float64)[band]
            for m in names:
                p = z["p_" + m].astype(np.float64)[band]
                b = p < 0.1
                per[m][i] = (b.sum(), p[b].sum(), y[b].sum())
    def gap(t):
        return None if t[0] == 0 else abs(t[2] / t[0] - t[1] / t[0])
    tot = {m: per[m].sum(0) for m in names}
    g = {m: gap(tot[m]) for m in names}
    draw = np.random.default_rng(a.seed).integers(0, len(fires), size=(a.draws, len(fires)))
    def bgap(m):
        s = per[m][draw].sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(s[:, 0] > 0, np.abs(s[:, 2] / s[:, 0] - s[:, 1] / s[:, 0]), np.nan)
    bc = bgap(a.candidate)
    out = dict(candidate=a.candidate, gaps={m: dict(gap=g[m], count=int(tot[m][0])) for m in names}, comparisons={})
    bounds = []
    for r in REFS:
        d = bc - bgap(r); ok = d[~np.isnan(d)]
        le = None if g[a.candidate] is None or g[r] is None else g[a.candidate] <= g[r]
        if g[r] is not None:
            bounds.append(le)
        out["comparisons"][r] = dict(candidate_not_larger=le, interval=None if not len(ok) else np.quantile(ok, [.025, .975]).tolist(),
                                     undefined=int(np.isnan(d).sum()))
    if g[a.candidate] is None:
        out["verdict"] = "NOT EVALUABLE (empty candidate bin): not met"
    elif not bounds:
        out["verdict"] = "NOT EVALUABLE (all reference bins empty): not met"
    else:
        out["verdict"] = "met" if all(bounds) else "not met"
    for m in names:
        print(f"  {m:20s} count {out['gaps'][m]['count']:>9d}  gap {g[m]}")
    print("criterion 5:", out["verdict"])
    if a.compare:
        c = json.loads(a.compare.read_text()); bad = []
        if c["verdict"] != out["verdict"]:
            bad.append(("verdict", c["verdict"], out["verdict"]))
        for m in names:
            cm = c["per_model"][m]
            if cm["count"] != out["gaps"][m]["count"]:
                bad.append((m, "count", cm["count"], out["gaps"][m]["count"]))
            if (cm["gap"] is None) != (g[m] is None) or (g[m] is not None and not math.isclose(cm["gap"], g[m], rel_tol=1e-12, abs_tol=1e-15)):
                bad.append((m, "gap", cm["gap"], g[m]))
        for r in REFS:
            cc, oc = c["comparisons"][r], out["comparisons"][r]
            if cc["candidate_not_larger"] != oc["candidate_not_larger"] or cc["bootstrap_draws_undefined"] != oc["undefined"]:
                bad.append((r, "flag/undefined", cc["candidate_not_larger"], oc["candidate_not_larger"], cc["bootstrap_draws_undefined"], oc["undefined"]))
            ci, oi = cc["descriptive_bootstrap_95_interval_of_gap_difference"], oc["interval"]
            if (ci is None) != (oi is None) or (ci and not all(math.isclose(x, w, rel_tol=1e-9, abs_tol=1e-15) for x, w in zip(ci, oi))):
                bad.append((r, "interval", ci, oi))
        print("comparison with criterion5.py:", "AGREE" if not bad else bad)
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
