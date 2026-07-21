#!/usr/bin/env python
"""ML baselines vs the canonical model on the spread_v2 LOFO task (priority 4).

Runs **logistic regression** and **random forest** as leave-one-fire-out
comparators to the canonical gradient-boosted model on the **identical 16
features, identical fold set, identical seed (20250603)** — a controlled
comparison answering "you only beat a bad physics model". Reports mean-of-folds
AUC ± SD and pooled AUC side by side. Hyperparameters are reasonable documented
defaults (see `validation/ml_baselines.default_models`); **nothing is tuned** —
neither the baselines (to lose) nor the GBM (to win).

Honest interpretation is the point: if the GBM only marginally beats random
forest, say so and pivot "technical excellence" to what is actually true
(calibrated probabilities, speed, the severity≫direction interpretability), not a
large accuracy win.

Like `scripts/auc_intervals.py`, this needs the (git-ignored) FIRMS/ERA5/DEM
bundle to rebuild the LOFO dataset; absent it the script STOPs (exit 2) rather
than fabricate numbers.

Run:  python scripts/ml_baselines.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
PROC = REPO / "data" / "processed"

CANON_REFERENCE = {"mean_of_folds": 0.901, "pooled": 0.8666547831321919}


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=20250603)
    ap.add_argument("--hazard-cell-m", type=float, default=500.0)
    ap.add_argument("--out", default=str(PROC / "ml_baselines.json"))
    args = ap.parse_args()

    from wildfireguardian.spread_v2 import data, features
    from wildfireguardian.validation.ml_baselines import lofo_compare

    if not data.data_available():
        print("=" * 78, file=sys.stderr)
        print("STOP (exit 2): FIRMS/ERA5/DEM bundle absent — cannot rebuild the LOFO\n"
              "dataset, so the baseline comparison cannot run. Provide the data via\n"
              "  unzip firms_data.zip -d data/raw/   (or set $WFG_FIRMS_DIR)  and re-run.\n"
              "No AUCs are reported without it (that would be fabrication). The\n"
              "comparator is unit-tested in tests/test_ml_baselines.py.", file=sys.stderr)
        print("=" * 78, file=sys.stderr)
        return 2

    print("[1/2] rebuilding LOFO dataset (identical features/folds/seed) ...")
    fire_ids = [m.id for m in data.list_fires()]
    ds = features.build_dataset(fire_ids, cell_size_m=args.hazard_cell_m, buffer_m=6000.0)
    print(f"      {len(ds)} rows, {int(ds['label'].sum())} positives, "
          f"{ds['fire_id'].nunique()} fires; seed {args.seed}")

    print("[2/2] leave-one-fire-out: logistic / random_forest / hist_gbm ...")
    res = lofo_compare(ds, seed=args.seed)
    rows = {name: r.as_dict() for name, r in res.items()}

    order = ["hist_gbm", "random_forest", "logistic"]
    print("\n  model          | mean-of-folds ± SD | pooled")
    for name in order:
        r = rows[name]
        print(f"  {name:<14} | {r['mean_of_folds']:.3f} ± {r['sd']:.3f}      | {r['pooled_auc']}")
    print(f"  (canonical reference: mean-of-folds {CANON_REFERENCE['mean_of_folds']}, "
          f"pooled {CANON_REFERENCE['pooled']:.3f})")

    gbm = rows["hist_gbm"]["mean_of_folds"]
    rf = rows["random_forest"]["mean_of_folds"]
    margin = gbm - rf
    verdict = ("MARGINAL over random forest — pivot the 'technical excellence' claim to "
               "calibrated probabilities + speed + severity≫direction interpretability, "
               "NOT a large accuracy win." if margin < 0.03 else
               "GBM leads random forest by a clear margin on mean-of-folds.")
    print(f"\n  GBM − RF mean-of-folds margin = {margin:+.3f}  →  {verdict}")

    out = {"seed": args.seed, "models": rows, "canonical_reference": CANON_REFERENCE,
           "gbm_minus_rf_mean_of_folds": round(margin, 4), "interpretation": verdict,
           "note": "identical 16 features / folds / seed; hyperparameters untuned"}
    Path(args.out).write_text(json.dumps(out, indent=2, default=str))
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
