"""Owen: independent recomputation of the S-D9 leak bound (arms L/L2) from the committed per-fold aggregates.

Written from LEAK_BOUND_PLAN.md rev 1-4 (claude/s-d9-leakbound), not from run_leakbound_L.py:
- per-fire SSE and n for base / L / L2, band (<= 4 km) and full, taken from fold_<k>_agg.json (5 files);
- pooled Brier = sum SSE / sum n; dBrier = aug - base;
- 95% whole-fire bootstrap over the union of held-out fires, paired, B = 2000, np.random.default_rng(20261030):
  computed two ways - (i) rng.integers(0, n, (B, n)), the natural reading; (ii) rng.choice per resample - to show
  the "material" label does not hinge on the resampling call;
- material = upper CI bound < 0 (arm L, band);
- [0, 0.1) calibration gap from the per-fire calib sums; coverage and receipts checked against committed inputs.

    python s-d9_leakbound_independent.py RUN_DIR
"""
import json
import sys
from pathlib import Path

import numpy as np


def main(run):
    run = Path(run)
    per_fire, folds_of = {}, {}
    for k in range(5):
        d = json.loads((run / f"fold_{k}_agg.json").read_text())
        for f, v in d["per_fire"].items():
            assert f not in per_fire, f"fire in two folds: {f}"
            per_fire[f] = v
            folds_of[f] = k
    lb = json.loads((run / "LEAK_BOUND.json").read_text())
    out = dict(fires=len(per_fire), per_fire_equals_report=per_fire == {f: {kk: vv for kk, vv in v.items()}
                                                                       for f, v in lb["per_fire"].items()})
    fires = sorted(per_fire)
    for arm in ("L", "L2"):
        for dom in ("band", "full"):
            n = np.array([per_fire[f][dom]["n"] for f in fires], float)
            sb = np.array([per_fire[f][dom]["base"]["sse"] for f in fires])
            sa = np.array([per_fire[f][dom][arm]["sse"] for f in fires])
            point = (sa.sum() - sb.sum()) / n.sum()
            rng = np.random.default_rng(20261030)
            idx = rng.integers(0, len(fires), size=(2000, len(fires)))
            b1 = (sa[idx].sum(1) - sb[idx].sum(1)) / n[idx].sum(1)
            rng2 = np.random.default_rng(20261030)
            b2 = []
            for _ in range(2000):
                j = rng2.choice(len(fires), size=len(fires), replace=True)
                b2.append((sa[j].sum() - sb[j].sum()) / n[j].sum())
            ci1, ci2 = np.percentile(b1, [2.5, 97.5]), np.percentile(b2, [2.5, 97.5])
            rep = lb["arms"][arm][dom]
            cal = {}
            for m in ("base", arm):
                c = sum(per_fire[f][dom][m]["calib_n"] for f in fires)
                gp = sum(per_fire[f][dom][m]["calib_sum_p"] for f in fires)
                gy = sum(per_fire[f][dom][m]["calib_sum_y"] for f in fires)
                cal[m] = (gp - gy) / c
            out[f"{arm}_{dom}"] = dict(
                cells=int(n.sum()), brier_base=sb.sum() / n.sum(), brier_aug=sa.sum() / n.sum(), delta=point,
                ci_integers=[float(x) for x in ci1], ci_choice=[float(x) for x in ci2],
                material_integers=bool(ci1[1] < 0), material_choice=bool(ci2[1] < 0),
                reported=dict(delta=rep["delta_brier"], ci=rep["ci95"], material=rep["material"], cells=rep["cells"]),
                delta_equal=bool(abs(point - rep["delta_brier"]) <= 1e-15),
                ci_equal=bool(np.allclose(ci1, rep["ci95"], rtol=0, atol=1e-15)),
                calib_gap=dict(base=cal["base"], aug=cal[arm]),
                calib_reported=dict(base=rep["calibration_lt_0_1"]["base"]["gap"], aug=rep["calibration_lt_0_1"]["augmented"]["gap"]),
                fires_better=int(((sa - sb) < 0).sum()))
    out["f1_coef_by_fold"] = lb["f1_coefficient_by_fold"]
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
