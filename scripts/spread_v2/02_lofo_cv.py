#!/usr/bin/env python3
"""Deliverable 3 — leave-one-fire-out cross-validation (with-weather model).

Per-fire ROC-AUC / PR-AUC / Brier (+ mean ± std), pooled out-of-fold AUC
overall and by distance band (0-375 / 375-750 / 750-1500 / >1500 m), and
per-fire footprint IoU / capture vs the observed final perimeter (mechanistic
CA baseline ≈ 9 % IoU).

Run:  .venv/bin/python scripts/spread_v2/02_lofo_cv.py
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from wildfireguardian.spread_v2 import SEED  # noqa: E402
from wildfireguardian.spread_v2.dataset import get_fire  # noqa: E402
from wildfireguardian.spread_v2.detections import (  # noqa: E402
    build_observed_sequence, load_detections,
)
from wildfireguardian.spread_v2.features import ALL_FEATURES  # noqa: E402
from wildfireguardian.spread_v2.grid import Grid, build_region  # noqa: E402
from wildfireguardian.spread_v2.model import (  # noqa: E402
    footprint_metrics, lofo_predict, summary_metrics,
)

OUTDIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "spread_v2"


def load_features() -> pd.DataFrame:
    p = OUTDIR / "features.parquet"
    if p.exists():
        return pd.read_parquet(p)
    return pd.read_csv(OUTDIR / "features.csv.gz")


def rebuild_sequences(fire_ids):
    """Rebuild observed sequences + grids (for footprint metrics) — no fuel raster."""
    seqs, grids = {}, {}
    for fid in fire_ids:
        fire = get_fire(fid)
        grid = Grid(build_region(fire))
        seq = build_observed_sequence(fid, load_detections(fire.detections_csv), grid)
        seqs[fid] = seq
        grids[fid] = grid
    return seqs, grids


def main():
    np.random.seed(SEED)
    df = load_features()
    fires = sorted(df["fire_id"].unique())
    print(f"LOFO over {len(fires)} fires: {fires}")
    print(f"Features ({len(ALL_FEATURES)}): {ALL_FEATURES}")

    oof, _models = lofo_predict(df, ALL_FEATURES, seed=SEED)
    summary = summary_metrics(oof)

    seqs, grids = rebuild_sequences(fires)
    fp = footprint_metrics(oof, seqs, grids)

    out = {
        "seed": SEED,
        "model": "with-weather (all 18 features)",
        "fires": fires,
        "summary": summary,
        "footprint": fp.to_dict(orient="records"),
        "footprint_mean_iou": round(float(fp["iou"].mean()), 4),
        "footprint_mean_capture": round(float(fp["capture"].mean()), 4),
        "mechanistic_baseline_iou": 0.09,
    }
    (OUTDIR / "lofo_metrics.json").write_text(json.dumps(out, indent=2, default=float))

    # ---- printed report ----
    print("\n" + "=" * 78)
    print("DELIVERABLE 3 — LOFO CV (with-weather, 18 features)")
    print("=" * 78)
    print(f"{'fire':24s} {'n':>7} {'pos':>5} {'ROC-AUC':>8} {'PR-AUC':>7} {'Brier':>7}")
    print("-" * 78)
    for r in summary["per_fire"]:
        print(f"{r['fire_id']:24s} {r['n']:7d} {r['positives']:5d} "
              f"{r['roc_auc']:8.3f} {r['pr_auc']:7.3f} {r['brier']:7.4f}")
    print("-" * 78)
    print(f"{'mean ± std (per fire)':24s} {'':7} {'':5} "
          f"{summary['mean_fire_roc_auc']:8.3f} {summary['mean_fire_pr_auc']:7.3f} "
          f"{summary['mean_fire_brier']:7.4f}")
    print(f"  ± std ROC-AUC = {summary['std_fire_roc_auc']:.3f}")
    print(f"\nPOOLED out-of-fold: ROC-AUC={summary['overall_pooled_roc_auc']:.3f}  "
          f"PR-AUC={summary['overall_pooled_pr_auc']:.3f}  "
          f"Brier={summary['overall_pooled_brier']:.4f}")
    print("\nConditional ROC-AUC by distance band:")
    for b, v in summary["band_auc"].items():
        print(f"  {b:10s} AUC={v['roc_auc']:.3f}  (n={v['n']}, pos={v['positives']})")
    print("\nFootprint (top-N at observed budget) vs observed final perimeter:")
    print(fp.to_string(index=False))
    print(f"\n  mean IoU={out['footprint_mean_iou']:.3f}  "
          f"mean capture={out['footprint_mean_capture']:.3f}  "
          f"(mechanistic CA baseline ≈ 0.09 IoU)")
    print(f"\nWrote {OUTDIR/'lofo_metrics.json'}")


if __name__ == "__main__":
    main()
