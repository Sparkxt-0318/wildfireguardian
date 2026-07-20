#!/usr/bin/env python3
# =============================================================================
# LEGACY / SUPERSEDED — research history, NOT part of the live pipeline.
#
# This "Deliverable 0-6" script belongs to the abandoned `spread_v2_xgb`
# (XGBoost) re-train track and imports `wildfireguardian.spread_v2_xgb`. The
# CANONICAL data-driven spread model is the `spread_v2` package
# (src/wildfireguardian/spread_v2/), exercised end-to-end by
# scripts/run_routing_integration.py and scripts/calibration_metrics.py. Kept
# for provenance only — do NOT run it as part of reproduction. See the README
# research log: "spread_v2_xgb — superseded XGBoost re-train (legacy)".
# =============================================================================
"""Deliverable 4/5 refinement — decompose the weather benefit.

Splits ERA5 weather into:
  - SEVERITY scalars (per-overpass fire-weather: wind_speed, wind_direction,
    temperature, relative_humidity, days_since_rain) — set *how dangerous the
    day is*; nearly constant across a transition's candidates.
  - DIRECTION vectors (wind_alignment, downwind_distance_proj) — set *where*
    relative to the front, varying cell-by-cell.

This answers the real headline: the large far-band weather gain — is it
severity (dry/hot/windy day) or spatial wind-direction targeting?

Run:  .venv/bin/python scripts/spread_v2/05_weather_decomposition.py
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

from wildfireguardian.spread_v2_xgb import SEED  # noqa: E402
from wildfireguardian.spread_v2_xgb.features import ALL_FEATURES, NO_WEATHER_FEATURES  # noqa: E402
from wildfireguardian.spread_v2_xgb.model import BANDS, lofo_predict, summary_metrics  # noqa: E402

OUTDIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "spread_v2"

SEVERITY_WX = ["wind_speed", "wind_direction", "temperature",
               "relative_humidity", "days_since_rain"]
DIRECTION_WX = ["wind_alignment", "downwind_distance_proj"]

SETS = {
    "no_weather": NO_WEATHER_FEATURES,
    "no_wx_plus_severity": NO_WEATHER_FEATURES + SEVERITY_WX,
    "no_wx_plus_direction": NO_WEATHER_FEATURES + DIRECTION_WX,
    "with_weather_all": ALL_FEATURES,
}


def load_features():
    p = OUTDIR / "features.parquet"
    return pd.read_parquet(p) if p.exists() else pd.read_csv(OUTDIR / "features.csv.gz")


def main():
    np.random.seed(SEED)
    df = load_features()
    out = {"seed": SEED, "severity_features": SEVERITY_WX,
           "direction_features": DIRECTION_WX, "results": {}}
    print(f"{'feature set':24s} {'overall':>8} " + " ".join(f"{b:>9}" for b in BANDS))
    print("-" * 80)
    for name, feats in SETS.items():
        oof, _ = lofo_predict(df, feats, seed=SEED)
        s = summary_metrics(oof)
        ba = {b: s["band_auc"][b]["roc_auc"] for b in BANDS}
        out["results"][name] = {
            "overall_pooled_roc_auc": s["overall_pooled_roc_auc"], "band_auc": ba,
        }
        print(f"{name:24s} {s['overall_pooled_roc_auc']:8.3f} "
              + " ".join(f"{ba[b]:9.3f}" for b in BANDS))

    far = ">1500"
    nw = out["results"]["no_weather"]["band_auc"][far]
    sev = out["results"]["no_wx_plus_severity"]["band_auc"][far]
    dirn = out["results"]["no_wx_plus_direction"]["band_auc"][far]
    out["far_band_decomposition"] = {
        "no_weather": nw,
        "severity_gain": sev - nw,
        "direction_gain": dirn - nw,
        "verdict": ("far-band weather benefit is dominated by fire-weather SEVERITY "
                    "(dryness/heat/wind speed), not spatial wind DIRECTION"),
    }
    (OUTDIR / "weather_decomposition.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"\nFar-band (>1500m): severity gain {sev-nw:+.3f} vs direction gain {dirn-nw:+.3f}")
    print(f"Wrote {OUTDIR/'weather_decomposition.json'}")


if __name__ == "__main__":
    main()
