#!/usr/bin/env python3
"""Run the full data-driven ignition-probability pipeline (Deliverables 1-6).

    python scripts/run_ignition_pipeline.py [--rebuild]

Builds the per-fire spread sequences + feature table (cached), runs the
leave-one-fire-out cross-validation, the baselines, the feature-importance /
SHAP analysis, writes machine-readable results JSON, and renders the figures.
"""

from __future__ import annotations

import argparse
import json
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from wildfireguardian.ignition_model.config import DISTANCE_BAND_LABELS, PipelineConfig
from wildfireguardian.ignition_model.model import (
    assemble_dataset,
    baseline_distance_only,
    baseline_logistic_distslope,
    feature_importance,
    leave_one_fire_out,
)
from wildfireguardian.ignition_model.viz import (
    plot_conditional_auc,
    plot_feature_importance,
    plot_prediction_map,
    plot_roc_curves,
    setup_korean_font,
)


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="ignore cached features")
    args = ap.parse_args()

    config = PipelineConfig()
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.figure_dir.mkdir(parents=True, exist_ok=True)
    feat_path = config.output_dir / "features.parquet"

    # ---- features (Deliverables 1-2) ----
    import json as _json

    meta_path = config.output_dir / "dataset_meta.json"
    if feat_path.exists() and meta_path.exists() and not args.rebuild:
        print("[1/5] Loading cached features ...")
        import pandas as _pd

        data = _pd.read_parquet(feat_path)
        meta = _json.loads(meta_path.read_text())
        from wildfireguardian.ignition_model.grid import get_fire_sequence

        seqs = {fid: get_fire_sequence(fid, config) for fid in data["fire_id"].unique()}
    else:
        print("[1/5] Assembling features ...")
        data, meta, seqs = assemble_dataset(config, return_sequences=True)
        data.to_parquet(feat_path)
        meta_path.write_text(_json.dumps(meta, indent=2, default=_json_default))
    print(f"      {meta['total_candidates']} candidates, "
          f"{meta['total_positive']} positive ({100*meta['overall_positive_rate']:.2f}%)")

    # ---- leave-one-fire-out (Deliverable 3) ----
    print("[2/5] Leave-one-fire-out cross-validation ...")
    lofo = leave_one_fire_out(data, config)

    # ---- baselines (Deliverable 4) ----
    print("[3/5] Baselines ...")
    base_dist = baseline_distance_only(data, config)
    base_ls = baseline_logistic_distslope(data, config)

    # ---- feature importance (Deliverable 5) ----
    print("[4/5] Feature importance + SHAP ...")
    importance, _full_model = feature_importance(data, config, with_shap=True)

    # ---- assemble results ----
    results = {
        "provenance": "NASA FIRMS (VIIRS+MODIS) / SRTM DEM / ESA WorldCover 2021 -- all real",
        "config": {
            "cell_size_m": config.cell_size_m,
            "overpass_gap_minutes": config.overpass_gap_minutes,
            "candidate_radius_m": config.candidate_radius_m,
            "random_seed": config.random_seed,
            "headline_fires": list(config.headline_fires),
            "fuel_broken_fires": list(config.fuel_broken_fires),
            "dropped_fires": list(config.drop_fires),
        },
        "dataset": meta,
        "lofo": {k: v for k, v in lofo.items() if k != "oof"},
        "baseline_distance_only": base_dist,
        "baseline_logistic_distslope": base_ls,
        "feature_importance": importance,
    }
    out = config.output_dir / "results.json"
    out.write_text(json.dumps(results, indent=2, default=_json_default))
    lofo["oof"].to_parquet(config.output_dir / "oof_predictions.parquet")

    # ---- figures (Deliverable 6) ----
    print("[5/5] Figures ...")
    ok = setup_korean_font()
    if not ok:
        print("      (warning: Korean font not found; labels may render as boxes)")
    plot_roc_curves(lofo["oof"], lofo["per_fire"], config.figure_dir / "roc_curves.png")
    plot_feature_importance(importance, config.figure_dir / "feature_importance.png")
    plot_conditional_auc(lofo["per_fire"], DISTANCE_BAND_LABELS,
                         config.figure_dir / "conditional_auc.png")
    for fid in seqs:
        if fid in lofo["oof"]["fire_id"].unique():
            plot_prediction_map(seqs[fid], lofo["oof"], fid,
                                config.figure_dir / f"prediction_map_{fid}.png")

    # ---- console summary ----
    s = lofo["summary"]
    print("\n" + "=" * 72)
    print("HEADLINE")
    print("=" * 72)
    print(f"Mean leave-one-fire-out ROC-AUC (headline fires {s['headline_fires']}):")
    print(f"   {s['headline_mean_auc']:.3f} +/- {s['headline_std_auc']:.3f}")
    print(f"Mean PR-AUC: {s['headline_mean_pr_auc']:.3f}  "
          f"(prevalence ~{100*meta['overall_positive_rate']:.1f}%)")
    print(f"Far-band (>1500m) mean AUC: {s['headline_mean_auc_far_band']}")
    print("\nPer-fire (held-out):")
    hdr = f"{'fire':24s} {'n':>7s} {'pos':>5s} {'ROC-AUC':>8s} {'PR-AUC':>7s} {'Brier':>7s}  flags"
    print(hdr)
    print("-" * len(hdr))
    for fid, r in lofo["per_fire"].items():
        if "roc_auc" not in r:
            print(f"{fid:24s}  -- {r.get('skipped','skipped')}")
            continue
        flags = []
        if r["fuel_blind"]:
            flags.append("FUEL-BLIND")
        if r["sparse"]:
            flags.append("SPARSE")
        print(f"{fid:24s} {r['n']:7d} {r['n_pos']:5d} {r['roc_auc']:8.3f} "
              f"{r['pr_auc']:7.3f} {r['brier']:7.4f}  {','.join(flags)}")
    print(f"\nWrote {out}")
    print(f"Figures -> {config.figure_dir}")


if __name__ == "__main__":
    main()
