#!/usr/bin/env python
"""Probability-calibration measurement: canonical spread_v2 GBM vs baselines.

Turns the Round-1 문서's **확률 보정** (calibration) claim into evidence. On the
**leave-one-fire-out out-of-fold** predictions of the canonical GBM (spread_v2,
HistGradientBoosting, seed 20250603) and its controlled baselines (random forest,
logistic) — identical 16 features / identical folds / identical seed, the same
machinery as ``scripts/ml_baselines.py`` — it computes, on pooled OOF and
per-fold:

- Brier score,
- Expected Calibration Error (15 equal-count / equal-mass bins),
- reliability-curve data (mean predicted vs observed frequency per bin),

plus a **supplementary** per-fold isotonic recalibration of the GBM (fit on the
train fires only, applied to the held-out fire) reported next to raw. It writes
``data/processed/calibration_metrics.json`` (every number in the figure/report),
the per-model OOF frames, and ``docs/figures/calibration_reliability.png``.

MEASUREMENT ONLY: nothing here modifies the model, forward-sim, or routing. The
isotonic probabilities are **not** wired into forward-sim/routing this round
(that would change every routing number — noted as future work).

Like ``scripts/ml_baselines.py`` / ``scripts/auc_intervals.py`` this needs the
git-ignored FIRMS/ERA5/DEM bundle to rebuild the LOFO dataset; absent it the
script STOPs (exit 2) rather than fabricate numbers.

Run:  python scripts/calibration_metrics.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
PROC = REPO / "data" / "processed"
FIGS = REPO / "docs" / "figures"

#: Canonical seed (== spread_v2.model.DEFAULT_SEED); validated at run time.
CANONICAL_SEED = 20250603

#: The canonical GBM's committed pooled out-of-fold AUC (data/processed/
#: spread_v2_lofo.json) — a consistency guard that the regenerated OOF is the
#: canonical model on the canonical fold set, not something drifted.
REFERENCE_POOLED_AUC = 0.9053277489374548

OOF_GBM = PROC / "spread_v2_lofo_oof.csv.gz"
OOF_RF = PROC / "lofo_oof_random_forest.csv.gz"
OOF_LOGIT = PROC / "lofo_oof_logistic.csv.gz"
OUT_JSON = PROC / "calibration_metrics.json"
OUT_FIG = FIGS / "calibration_reliability.png"


def _relpath(p: Path) -> str:
    """Repo-relative path when possible, else the plain string (robust to
    output dirs pointed outside the repo, e.g. in tests)."""
    try:
        return str(Path(p).relative_to(REPO))
    except ValueError:
        return str(p)


def _pooled_auc(oof) -> float | None:
    from sklearn.metrics import roc_auc_score
    y = oof["label"].to_numpy()
    if y.min() == y.max():
        return None
    return float(roc_auc_score(y, oof["prob"].to_numpy()))


def compute_payload(
    ds, *, seed: int = CANONICAL_SEED, n_bins: int = 15, isotonic_splits: int = 5,
) -> dict:
    """Pure compute: LOFO OOF → calibration metrics → rounded JSON payload.

    No file I/O and no plotting, so ``main()`` and the determinism test share
    one code path. Returns ``{"payload", "oof", "reports", "isotonic", "gbm_auc"}``.

    - ``hist_gbm`` OOF comes from the canonical ``leave_one_fire_out`` pipeline;
    - ``random_forest`` / ``logistic`` OOF from the ``ml_baselines`` machinery on
      the identical folds / features / seed;
    - each scored on **out-of-fold** rows only (a model never sees its own fire).
    """
    from wildfireguardian.spread_v2 import features
    from wildfireguardian.spread_v2.model import leave_one_fire_out
    from wildfireguardian.validation import calibration as cal
    from wildfireguardian.validation.ml_baselines import default_models, lofo_oof_predictions

    gbm_oof = leave_one_fire_out(ds, seed=seed, compute_importance=False).oof
    base_models = {k: default_models(seed)[k] for k in ("random_forest", "logistic")}
    base_oof = lofo_oof_predictions(ds, models=base_models, seed=seed)
    oof = {"hist_gbm": gbm_oof,
           "random_forest": base_oof["random_forest"],
           "logistic": base_oof["logistic"]}

    reports = {name: cal.calibration_report(df, n_bins=n_bins) for name, df in oof.items()}
    iso_oof = cal.isotonic_oof_gbm(ds, seed=seed, n_splits=isotonic_splits)
    isotonic = cal.isotonic_summary(iso_oof, n_bins=n_bins)
    gbm_auc = _pooled_auc(gbm_oof)
    fires_used = sorted(ds["fire_id"].unique())

    meta = {
        "dataset": {
            "n_rows": int(len(ds)),
            "n_positives": int(ds["label"].sum()),
            "base_rate": float(ds["label"].mean()),
            "fires": fires_used,
            "n_fires": len(fires_used),
            "features": list(features.FEATURE_COLUMNS),
        },
        "oof_files": {
            "hist_gbm": _relpath(OOF_GBM),
            "random_forest": _relpath(OOF_RF),
            "logistic": _relpath(OOF_LOGIT),
        },
        "reference": {
            "committed_pooled_auc": REFERENCE_POOLED_AUC,
            "regenerated_gbm_pooled_auc": gbm_auc,
        },
    }
    payload = cal.assemble_metrics(reports, isotonic, meta=meta, seed=seed, n_bins=n_bins)
    return {"payload": payload, "oof": oof, "reports": reports,
            "isotonic": isotonic, "gbm_auc": gbm_auc}


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=20250603)
    ap.add_argument("--hazard-cell-m", type=float, default=500.0)
    ap.add_argument("--buffer-m", type=float, default=6000.0)
    ap.add_argument("--n-bins", type=int, default=15)
    ap.add_argument("--isotonic-splits", type=int, default=5)
    ap.add_argument("--no-fig", action="store_true", help="skip the PNG")
    ap.add_argument("--out", default=str(OUT_JSON))
    args = ap.parse_args()

    from wildfireguardian.spread_v2 import data, features
    from wildfireguardian.spread_v2.model import DEFAULT_SEED
    from wildfireguardian.validation import calibration as cal

    if args.seed != DEFAULT_SEED:
        print(f"[warn] --seed {args.seed} != canonical {DEFAULT_SEED}; "
              "results will not match the committed reference.", file=sys.stderr)

    if not data.data_available():
        print("=" * 78, file=sys.stderr)
        print(
            "STOP (exit 2): FIRMS/ERA5/DEM bundle absent — cannot rebuild the LOFO\n"
            "dataset, so out-of-fold predictions cannot be regenerated and NO\n"
            "calibration numbers are reported (that would be fabrication). Provide\n"
            "the data and re-run:\n"
            "  unzip firms_data.zip -d data/raw/     (or: export WFG_FIRMS_DIR=/path)\n"
            "  python scripts/calibration_metrics.py\n"
            "The metric functions are unit-tested in tests/test_calibration_metrics.py.",
            file=sys.stderr)
        print("=" * 78, file=sys.stderr)
        return 2

    # -- 1. rebuild the LOFO dataset (identical to scripts/ml_baselines.py) -----
    print("[1/5] rebuilding LOFO dataset (identical features/folds/seed) ...")
    fire_ids = [m.id for m in data.list_fires()]
    ds = features.build_dataset(fire_ids, cell_size_m=args.hazard_cell_m,
                                buffer_m=args.buffer_m)
    print(f"      {len(ds)} rows, {int(ds['label'].sum())} positives, "
          f"{ds['fire_id'].nunique()} fires; seed {args.seed}")

    # -- 2-5. OOF predictions → calibration metrics → isotonic → JSON payload ---
    print("[2/5] out-of-fold predictions: GBM (leave_one_fire_out) + "
          "random_forest / logistic (ml_baselines) ...")
    print(f"[3/5] Brier / ECE ({args.n_bins} equal-count bins) / reliability ...")
    print("[4/5] SUPPLEMENTARY — per-fold isotonic recalibration of the GBM ...")
    res = compute_payload(ds, seed=args.seed, n_bins=args.n_bins,
                          isotonic_splits=args.isotonic_splits)
    payload, oof, reports, isotonic = (
        res["payload"], res["oof"], res["reports"], res["isotonic"])
    gbm_auc = res["gbm_auc"]

    # Consistency guard: the regenerated GBM OOF must reproduce the committed AUC.
    if gbm_auc is not None and abs(gbm_auc - REFERENCE_POOLED_AUC) > 1e-4:
        print(f"[warn] GBM pooled AUC {gbm_auc:.6f} != committed reference "
              f"{REFERENCE_POOLED_AUC:.6f} (Δ={gbm_auc - REFERENCE_POOLED_AUC:+.2e}); "
              "the dataset/folds may have drifted.", file=sys.stderr)

    # persist OOF frames (git-tracked; see .gitignore whitelist)
    PROC.mkdir(parents=True, exist_ok=True)
    oof["hist_gbm"].to_csv(OOF_GBM, index=False)
    oof["random_forest"].to_csv(OOF_RF, index=False)
    oof["logistic"].to_csv(OOF_LOGIT, index=False)
    print(f"      wrote {OOF_GBM.name}, {OOF_RF.name}, {OOF_LOGIT.name}")

    Path(args.out).write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(f"[5/5] wrote {args.out}")

    if not args.no_fig:
        cal.make_reliability_figure(reports, OUT_FIG)
        print(f"      wrote {OUT_FIG}")

    # -- printed report (no spin: state which model calibrates best) ------------
    print("\n" + "=" * 78)
    print("CALIBRATION — pooled out-of-fold (lower Brier / ECE = better calibrated)")
    print("=" * 78)
    print(f"  {'model':<14} | {'Brier':>9} | {'ECE':>9} | {'per-fold Brier µ±σ':>22}")
    for name in ("hist_gbm", "random_forest", "logistic"):
        r = reports[name]
        pf = r["per_fold"]
        print(f"  {name:<14} | {r['pooled']['brier']:9.5f} | {r['pooled']['ece']:9.5f} | "
              f"{pf['brier_mean']:9.5f} ± {pf['brier_sd']:.5f}")
    best_brier = min(reports, key=lambda k: reports[k]["pooled"]["brier"])
    best_ece = min(reports, key=lambda k: reports[k]["pooled"]["ece"])
    print(f"\n  best pooled Brier: {best_brier}   |   best pooled ECE: {best_ece}")
    if best_brier != "hist_gbm" or best_ece != "hist_gbm":
        print("  NOTE: a baseline calibrates at least as well as the GBM on this "
              "metric —\n        report it plainly, do not spin.")
    ir, ip = isotonic["raw"], isotonic["post"]
    print(f"\n  supplementary isotonic (GBM): Brier {ir['pooled_brier']:.5f} -> "
          f"{ip['pooled_brier']:.5f}   ECE {ir['pooled_ece']:.5f} -> {ip['pooled_ece']:.5f}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
