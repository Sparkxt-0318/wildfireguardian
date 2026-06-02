#!/usr/bin/env python3
"""Deliverable 5 — feature importance + the uljin attribution experiment.

(1) LOFO permutation importance (pooled-AUC drop when a feature is shuffled) and
    XGBoost gain importance from a full-data model. Head-to-head: real
    ``wind_alignment`` vs the ``v1_alignment`` observed-growth proxy; grouped
    importance (weather vs terrain vs intensity/proximity vs fuel).

(2) Attribution: does fixing uljin change the far-band result? We rebuild uljin's
    feature table under the *orientation bug* (gate vertically flipped — the exact
    candidate-bottom-up vs fuel-top-down mismatch), re-run the with-weather LOFO,
    and compare overall + far-band AUC. This isolates uljin's data quality.

Run:  .venv/bin/python scripts/spread_v2/04_importance.py
"""

from __future__ import annotations

import json
import sys
import warnings
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from wildfireguardian.spread_v2 import SEED  # noqa: E402
from wildfireguardian.spread_v2.candidates import iter_transitions  # noqa: E402
from wildfireguardian.spread_v2.dataset import get_fire  # noqa: E402
from wildfireguardian.spread_v2.detections import (  # noqa: E402
    build_observed_sequence, load_detections,
)
from wildfireguardian.spread_v2.era5 import WeatherSeries  # noqa: E402
from wildfireguardian.spread_v2.features import (  # noqa: E402
    ALL_FEATURES, build_feature_table,
)
from wildfireguardian.spread_v2.grid import Grid, build_region  # noqa: E402
from wildfireguardian.spread_v2.layers import build_static_layers  # noqa: E402
from wildfireguardian.spread_v2.model import (  # noqa: E402
    feature_group, lofo_predict, make_model, permutation_importance_lofo,
    summary_metrics,
)

OUTDIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "spread_v2"


def load_features():
    p = OUTDIR / "features.parquet"
    return pd.read_parquet(p) if p.exists() else pd.read_csv(OUTDIR / "features.csv.gz")


def rebuild_uljin_features(flip_gate: bool) -> pd.DataFrame:
    fire = get_fire("uljin_samcheok_2022")
    grid = Grid(build_region(fire))
    seq = build_observed_sequence(fire.fire_id, load_detections(fire.detections_csv), grid)
    static = build_static_layers(fire, grid)
    if flip_gate:
        # Reproduce the prior bug: candidate grid (bottom-up) vs fuel (top-down).
        bugged = np.flipud(static.burnable_gate) & static.in_fuel_bounds
        static = replace(static, burnable_gate=bugged)
    trs = iter_transitions(seq, static)
    weather = WeatherSeries.from_fire(fire)
    return build_feature_table(fire.fire_id, grid, seq, static, trs, weather)


def main():
    np.random.seed(SEED)
    df = load_features()

    # ---- (1a) gain importance from a full-data with-weather model ----
    model = make_model(SEED)
    model.fit(df[ALL_FEATURES], df["label"])
    gain = model.get_booster().get_score(importance_type="gain")
    gain_imp = pd.DataFrame(
        [{"feature": f, "gain": gain.get(f, 0.0)} for f in ALL_FEATURES]
    ).sort_values("gain", ascending=False)
    tot = gain_imp["gain"].sum()
    gain_imp["gain_frac"] = gain_imp["gain"] / tot

    # ---- (1b) LOFO permutation importance (the honest one) ----
    base_oof, fold_models = lofo_predict(df, ALL_FEATURES, seed=SEED)
    perm = permutation_importance_lofo(
        df, ALL_FEATURES, fold_models, base_oof, seed=SEED, n_repeats=5
    )

    # grouped permutation importance
    perm["group"] = perm["feature"].map(feature_group)
    grouped = perm.groupby("group")["auc_drop_mean"].sum().sort_values(ascending=False)

    # ---- (2) uljin attribution ----
    others = df[df["fire_id"] != "uljin_samcheok_2022"]
    print("[attrib] rebuilding uljin under the orientation bug …", flush=True)
    uljin_bug = rebuild_uljin_features(flip_gate=True)
    df_bugged = pd.concat([others, uljin_bug], ignore_index=True)
    oof_fix = base_oof
    oof_bug, _ = lofo_predict(df_bugged, ALL_FEATURES, seed=SEED)
    s_fix, s_bug = summary_metrics(oof_fix), summary_metrics(oof_bug)
    attribution = {
        "uljin_positives_fixed": int(df[df.fire_id == "uljin_samcheok_2022"]["label"].sum()),
        "uljin_positives_bugged": int(uljin_bug["label"].sum()),
        "overall_auc_fixed": s_fix["overall_pooled_roc_auc"],
        "overall_auc_bugged": s_bug["overall_pooled_roc_auc"],
        "far_band_auc_fixed": s_fix["band_auc"][">1500"]["roc_auc"],
        "far_band_auc_bugged": s_bug["band_auc"][">1500"]["roc_auc"],
    }

    out = {
        "seed": SEED,
        "gain_importance": gain_imp.to_dict(orient="records"),
        "permutation_importance": perm.drop(columns="group").to_dict(orient="records"),
        "grouped_permutation_importance": grouped.to_dict(),
        "wind_vs_v1_proxy": {
            "wind_alignment_perm": float(perm.loc[perm.feature == "wind_alignment", "auc_drop_mean"].iloc[0]),
            "v1_alignment_perm": float(perm.loc[perm.feature == "v1_alignment", "auc_drop_mean"].iloc[0]),
            "wind_alignment_gain_frac": float(gain_imp.loc[gain_imp.feature == "wind_alignment", "gain_frac"].iloc[0]),
            "v1_alignment_gain_frac": float(gain_imp.loc[gain_imp.feature == "v1_alignment", "gain_frac"].iloc[0]),
        },
        "uljin_attribution": attribution,
    }
    (OUTDIR / "importance_metrics.json").write_text(json.dumps(out, indent=2, default=float))

    # ---- printed report ----
    print("\n" + "=" * 70)
    print("DELIVERABLE 5 — FEATURE IMPORTANCE")
    print("=" * 70)
    print("\nLOFO permutation importance (pooled ROC-AUC drop when shuffled):")
    print(f"{'feature':26s} {'AUC drop':>10} {'±std':>7}  group")
    for _, r in perm.iterrows():
        print(f"  {r['feature']:24s} {r['auc_drop_mean']:10.4f} {r['auc_drop_std']:7.4f}  {r['group']}")
    print("\nGrouped permutation importance (Σ AUC drop):")
    for g, v in grouped.items():
        print(f"  {g:22s} {v:.4f}")
    print("\nReal wind_alignment vs v1 observed-growth proxy:")
    wv = out["wind_vs_v1_proxy"]
    print(f"  wind_alignment : perm AUC-drop {wv['wind_alignment_perm']:.4f}, gain {wv['wind_alignment_gain_frac']:.3f}")
    print(f"  v1_alignment   : perm AUC-drop {wv['v1_alignment_perm']:.4f}, gain {wv['v1_alignment_gain_frac']:.3f}")
    print("\nTop gain importance:")
    for _, r in gain_imp.head(8).iterrows():
        print(f"  {r['feature']:24s} gain_frac={r['gain_frac']:.3f}")
    print("\n" + "=" * 70)
    print("ULJIN ATTRIBUTION — does fixing the orientation bug change it?")
    print("=" * 70)
    a = attribution
    print(f"  uljin positives:  fixed={a['uljin_positives_fixed']}  "
          f"bugged(flip)={a['uljin_positives_bugged']}")
    print(f"  overall pooled AUC:  fixed={a['overall_auc_fixed']:.3f}  "
          f"bugged={a['overall_auc_bugged']:.3f}  Δ={a['overall_auc_fixed']-a['overall_auc_bugged']:+.3f}")
    print(f"  far-band (>1500m) AUC: fixed={a['far_band_auc_fixed']:.3f}  "
          f"bugged={a['far_band_auc_bugged']:.3f}  Δ={a['far_band_auc_fixed']-a['far_band_auc_bugged']:+.3f}")
    print(f"\nWrote {OUTDIR/'importance_metrics.json'}")


if __name__ == "__main__":
    main()
