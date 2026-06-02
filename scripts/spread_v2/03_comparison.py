#!/usr/bin/env python3
"""Deliverable 4 — model comparison: distance-only / no-weather / with-weather.

Each feature set is evaluated under LOFO on two fire sets:
  (A) full usable set (6 fires, incl. gangneung_donghae with weather = NaN)
  (B) clean weather-complete subset (5 fires with valid ERA5)

Headline: does real ERA5 wind help, overall vs in the far band, over the
weather-free model (which already carries the v1 observed-growth proxy)?
Compared against the prior run's 0.781 overall / 0.63-0.66 far-band.

Run:  .venv/bin/python scripts/spread_v2/03_comparison.py
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
from wildfireguardian.spread_v2.features import (  # noqa: E402
    ALL_FEATURES, DISTANCE_ONLY_FEATURES, NO_WEATHER_FEATURES,
)
from wildfireguardian.spread_v2.model import BANDS, lofo_predict, summary_metrics  # noqa: E402

OUTDIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "spread_v2"

FEATURE_SETS = {
    "distance_only": DISTANCE_ONLY_FEATURES,
    "no_weather": NO_WEATHER_FEATURES,
    "with_weather": ALL_FEATURES,
}


def load_features():
    p = OUTDIR / "features.parquet"
    return pd.read_parquet(p) if p.exists() else pd.read_csv(OUTDIR / "features.csv.gz")


def run_set(df, label, fire_subset=None):
    if fire_subset is not None:
        df = df[df["fire_id"].isin(fire_subset)]
    res = {}
    for name, feats in FEATURE_SETS.items():
        oof, _ = lofo_predict(df, feats, seed=SEED)
        s = summary_metrics(oof)
        res[name] = {
            "overall_pooled_roc_auc": s["overall_pooled_roc_auc"],
            "overall_pooled_pr_auc": s["overall_pooled_pr_auc"],
            "mean_fire_roc_auc": s["mean_fire_roc_auc"],
            "std_fire_roc_auc": s["std_fire_roc_auc"],
            "band_auc": {b: s["band_auc"][b]["roc_auc"] for b in BANDS},
        }
    return res


def main():
    np.random.seed(SEED)
    df = load_features()
    all_fires = sorted(df["fire_id"].unique())
    weather_complete = sorted(
        df.groupby("fire_id")["wind_speed"].apply(lambda s: s.notna().all())
        .loc[lambda x: x].index
    )

    out = {
        "seed": SEED,
        "fire_set_A_full": all_fires,
        "fire_set_B_weather_complete": weather_complete,
        "results": {
            "A_full_usable": run_set(df, "A", all_fires),
            "B_weather_complete": run_set(df, "B", weather_complete),
        },
        "prior_run_reference": {"overall_roc_auc": 0.781, "far_band_roc_auc": [0.63, 0.66]},
    }
    (OUTDIR / "comparison_metrics.json").write_text(json.dumps(out, indent=2, default=float))

    def show(title, res):
        print("\n" + "=" * 86)
        print(title)
        print("=" * 86)
        hdr = f"{'feature set':16s} {'overall':>8} {'PR-AUC':>7} {'meanfire':>9} " + \
              " ".join(f"{b:>9}" for b in BANDS)
        print(hdr)
        print("-" * 86)
        for name in FEATURE_SETS:
            r = res[name]
            ba = r["band_auc"]
            print(f"{name:16s} {r['overall_pooled_roc_auc']:8.3f} "
                  f"{r['overall_pooled_pr_auc']:7.3f} {r['mean_fire_roc_auc']:9.3f} "
                  + " ".join(f"{ba[b]:9.3f}" for b in BANDS))
        # deltas
        nw, ww = res["no_weather"], res["with_weather"]
        d_over = ww["overall_pooled_roc_auc"] - nw["overall_pooled_roc_auc"]
        d_far = ww["band_auc"][">1500"] - nw["band_auc"][">1500"]
        print("-" * 86)
        print(f"  Δ(with-weather − no-weather): overall {d_over:+.3f}, "
              f">1500m far-band {d_far:+.3f}")

    show("DELIVERABLE 4A — full usable set (6 fires; gangneung_donghae weather=NaN)",
         out["results"]["A_full_usable"])
    show("DELIVERABLE 4B — clean weather-complete subset (5 fires)",
         out["results"]["B_weather_complete"])
    print(f"\nprior run reference: overall 0.781, far-band 0.63–0.66")
    print(f"Wrote {OUTDIR/'comparison_metrics.json'}")


if __name__ == "__main__":
    main()
