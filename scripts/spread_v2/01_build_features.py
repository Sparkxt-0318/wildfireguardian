#!/usr/bin/env python3
# =============================================================================
# LEGACY / SUPERSEDED — research history, NOT part of the live pipeline.
#
# This "Deliverable 0-6" script belongs to the abandoned `spread_v2_xgb`
# forbidden-ok: XGBoost
# (XGBoost) re-train track and imports `wildfireguardian.spread_v2_xgb`. The
# CANONICAL data-driven spread model is the `spread_v2` package
# (src/wildfireguardian/spread_v2/), exercised end-to-end by
# scripts/run_routing_integration.py and scripts/calibration_metrics.py. Kept
# for provenance only — do NOT run it as part of reproduction. See the README
# research log: "spread_v2_xgb — superseded XGBoost re-train (legacy)".
# =============================================================================
"""Deliverables 1 & 2 — observed spread sequences + feature table.

For each *usable* fire (>= 2 overpass transitions and >= 20 positive cells):
  1. Build the monotone observed spread sequence (Deliverable 1): per-overpass
     cumulative burned area, observed-vs-reported area, monotonicity check.
  2. Assemble the full candidate feature table (Deliverable 2) and report the
     class balance.

Outputs (data/processed/spread_v2/):
  - features.parquet  — full candidate table for all usable fires (gitignored)
  - spread_sequences.json — Deliverable 1 summary (committed)
  - class_balance.json    — Deliverable 2 summary (committed)

Run:  .venv/bin/python scripts/spread_v2/01_build_features.py
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from wildfireguardian.spread_v2_xgb import SEED  # noqa: E402
from wildfireguardian.spread_v2_xgb.candidates import iter_transitions  # noqa: E402
from wildfireguardian.spread_v2_xgb.dataset import all_fires  # noqa: E402
from wildfireguardian.spread_v2_xgb.detections import (  # noqa: E402
    build_observed_sequence, load_detections,
)
from wildfireguardian.spread_v2_xgb.era5 import WeatherSeries  # noqa: E402
from wildfireguardian.spread_v2_xgb.features import (  # noqa: E402
    ALL_FEATURES, WEATHER, build_feature_table,
)
from wildfireguardian.spread_v2_xgb.grid import Grid, build_region  # noqa: E402
from wildfireguardian.spread_v2_xgb.layers import build_static_layers  # noqa: E402

OUTDIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "spread_v2"
MIN_TRANSITIONS = 2
MIN_POSITIVES = 20


def summarize_sequence(fire, grid, seq, transitions):
    """Deliverable 1 summary for one fire's observed spread sequence."""
    cum_areas = [float(m.sum()) * grid.cell_area_m2 / 1e4 for m in seq.cumulative]
    monotone = all(
        seq.cumulative[i + 1].sum() >= seq.cumulative[i].sum()
        for i in range(len(seq.cumulative) - 1)
    )
    seq_summary = {
        "fire_id": fire.fire_id,
        "n_overpasses": seq.n_overpasses,
        "n_transitions": len(transitions),
        "overpass_times": [str(o.time) for o in seq.overpasses],
        "overpass_new_detections": [int(o.n_detections) for o in seq.overpasses],
        "cumulative_area_ha": [round(a, 1) for a in cum_areas],
        "monotone_masks": bool(monotone),
        "observed_final_area_ha": round(cum_areas[-1], 1) if cum_areas else 0.0,
        "reported_ha": fire.reported_ha,
        "observed_vs_reported": round(cum_areas[-1] / fire.reported_ha, 3) if cum_areas else None,
        "transition_dt_hours": [round(t.dt_hours, 2) for t in transitions],
    }
    return seq_summary


def main():
    np.random.seed(SEED)
    fires = all_fires()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    seqs, tables, balance = [], [], []
    usable, skipped = [], []

    for fid, fire in fires.items():
        print(f"[features] {fid} …", flush=True)
        grid = Grid(build_region(fire))
        df = load_detections(fire.detections_csv)
        seq = build_observed_sequence(fid, df, grid)
        static = build_static_layers(fire, grid)
        trs = iter_transitions(seq, static)
        n_pos = sum(int(t.labels.sum()) for t in trs)
        if len(trs) < MIN_TRANSITIONS or n_pos < MIN_POSITIVES:
            skipped.append({"fire_id": fid, "n_transitions": len(trs), "n_positives": n_pos,
                            "reason": "too few transitions/positives for a LOFO fold"})
            print(f"  SKIP ({len(trs)} transitions, {n_pos} positives)")
            continue

        weather = WeatherSeries.from_fire(fire) if fire.has_era5 else None
        seqs.append(summarize_sequence(fire, grid, seq, trs))
        table = build_feature_table(fid, grid, seq, static, trs, weather)
        tables.append(table)
        usable.append(fid)
        has_w = weather is not None
        n = len(table)
        p = int(table["label"].sum())
        balance.append({
            "fire_id": fid, "candidates": n, "positives": p,
            "prevalence": round(p / n, 4), "has_era5": bool(has_w),
        })
        print(f"  OK  candidates={n} positives={p} prevalence={p/n:.3%} era5={has_w}")

    import pandas as pd
    full = pd.concat(tables, ignore_index=True)
    # Persist feature table (parquet if available, else compressed CSV).
    try:
        full.to_parquet(OUTDIR / "features.parquet", index=False)
        feat_path = "features.parquet"
    except Exception:
        full.to_csv(OUTDIR / "features.csv.gz", index=False, compression="gzip")
        feat_path = "features.csv.gz"

    tot_n, tot_p = len(full), int(full["label"].sum())
    weather_complete = [b["fire_id"] for b in balance if b["has_era5"]]

    (OUTDIR / "spread_sequences.json").write_text(json.dumps({
        "seed": SEED, "sequences": seqs,
    }, indent=2))
    (OUTDIR / "class_balance.json").write_text(json.dumps({
        "seed": SEED,
        "feature_table": feat_path,
        "n_features": len(ALL_FEATURES),
        "feature_names": ALL_FEATURES,
        "weather_features": WEATHER,
        "usable_fires": usable,
        "weather_complete_fires": weather_complete,
        "skipped_fires": skipped,
        "overall": {"candidates": tot_n, "positives": tot_p,
                    "prevalence": round(tot_p / tot_n, 4)},
        "per_fire": balance,
    }, indent=2))

    print("\n" + "=" * 80)
    print(f"USABLE FIRES ({len(usable)}): {usable}")
    print(f"WEATHER-COMPLETE ({len(weather_complete)}): {weather_complete}")
    print(f"SKIPPED: {[s['fire_id'] for s in skipped]}")
    print(f"OVERALL: {tot_n} candidates, {tot_p} positives, "
          f"prevalence {tot_p/tot_n:.3%}")
    print(f"Wrote {feat_path}, spread_sequences.json, class_balance.json")


if __name__ == "__main__":
    main()
