#!/usr/bin/env python
"""Build and cache the Arm E dataset (Session 12 Phase 2a).

Arm A's 16 columns come from calling ``spread_v2.features`` itself, so they are
bit-identical to Arm A's dataset by construction; Arm E's columns are joined
one-to-one onto them. Nothing in ``spread_v2`` is modified.

Slope source is the Phase 1 gate decision: native ~30 m SRTM aggregated to the
500 m cell as the Rothermel-forcing-equivalent effective slope, which measured
2.6-3.0x steeper than the 500 m-baseline slope the model currently carries.

    python scripts/arm_e_build.py            # build all missing fires
    python scripts/arm_e_build.py --merge

Writes ONLY under data/processed/arms/E/.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

OUT = REPO / "data" / "processed" / "arms" / "E"
CACHE = OUT / "per_fire"


def build_one(fid: str) -> dict:
    import pandas as pd

    from wildfireguardian.spread_v2 import data as datamod
    from wildfireguardian.spread_v2 import grid as gridmod
    from wildfireguardian.spread_v2.features import StaticLayers, build_transition_frame
    from wildfireguardian.spread_v2.weather import weather_series_from_event
    from wildfireguardian.spread_v2_arme.features import arm_e_columns
    from wildfireguardian.spread_v2_arme.terrain import (
        DEFAULT_SUBDIVISION, native_slope_stats)

    t0 = time.time()
    ev = datamod.load_event(fid)
    ws = weather_series_from_event(ev)
    if ws is None:
        return {"fire": fid, "rows": 0, "positives": 0, "seconds": 0.0,
                "skipped": "no ERA5"}
    g = gridmod.build_grid(ev.meta.bbox_wgs84, cell_size_m=gridmod.DEFAULT_CELL_M)
    snaps = gridmod.overpass_snapshots(ev, g, gap_minutes=90.0)
    if len(snaps) < 2:
        return {"fire": fid, "rows": 0, "positives": 0, "seconds": 0.0,
                "skipped": "<2 overpasses"}

    static = StaticLayers.from_event(ev, g)
    arm_a = build_transition_frame(ev, g, static, snaps, ws, buffer_m=6000.0)
    if arm_a.empty:
        return {"fire": fid, "rows": 0, "positives": 0, "seconds": 0.0,
                "skipped": "no transitions"}

    elev = gridmod.elevation_on_grid(ev, g)
    native = native_slope_stats(ev, g, DEFAULT_SUBDIVISION)["effective"]
    by_index = {op.index: k for k, op in enumerate(snaps)}

    parts = []
    for op_from, chunk in arm_a.groupby("op_from", sort=True):
        k = by_index.get(int(op_from))
        if k is None:
            continue
        rows = chunk["row"].to_numpy()
        cols = chunk["col"].to_numpy()
        cols_e = arm_e_columns(rows, cols, snaps[k].cumulative_mask,
                               elev, native, g.cell_size_m)
        part = chunk[["fire_id", "op_from", "row", "col"]].copy()
        for name, vals in cols_e.items():
            part[name] = vals
        parts.append(part)

    arm_e = pd.concat(parts, ignore_index=True)
    merged = arm_a.merge(arm_e, on=["fire_id", "op_from", "row", "col"],
                         how="left", validate="one_to_one")
    assert len(merged) == len(arm_a), "Arm E join changed the Arm A row count"

    dt = time.time() - t0
    CACHE.mkdir(parents=True, exist_ok=True)
    with (CACHE / f"{fid}.pkl").open("wb") as fh:
        pickle.dump({"df": merged, "build_seconds": round(dt, 2)}, fh)
    return {"fire": fid, "rows": int(len(merged)),
            "positives": int(merged["label"].sum()), "seconds": round(dt, 1)}


def merge() -> None:
    import pandas as pd

    from wildfireguardian.spread_v2.features import FEATURE_COLUMNS
    from wildfireguardian.spread_v2_arme.features import (
        ARM_E_FEATURE_COLUMNS, SMOOTH_WINDOWS_M)

    parts, timings = [], {}
    for p in sorted(CACHE.glob("*.pkl")):
        with p.open("rb") as fh:
            blob = pickle.load(fh)
        if len(blob["df"]):
            parts.append(blob["df"])
        timings[p.stem] = blob.get("build_seconds")
    if not parts:
        raise SystemExit("no per-fire caches — run without --merge first")

    df = pd.concat(parts, ignore_index=True)
    with (OUT / "arm_e_dataset.pkl").open("wb") as fh:
        pickle.dump(df, fh)

    corr_targets = ["slope_deg", "elev_above_source_m", "wind_alignment",
                    "dist_to_fire_m", "native_slope_deg", "slope_forcing"]
    sub = df[["upslope_alignment", *corr_targets]].astype("float64")
    corrs = {c: (None if sub[c].std() == 0 else
                 round(float(sub["upslope_alignment"].corr(sub[c])), 4))
             for c in corr_targets}

    summary = {
        "arm": "E",
        "provenance": "derived",
        "slope_source": "native ~30 m SRTM -> 500 m effective slope "
                        "(arctan(sqrt(mean(tan^2))))",
        "n_rows": int(len(df)),
        "n_positives": int(df["label"].sum()),
        "fires_used": sorted(df["fire_id"].unique().tolist()),
        "feature_columns": list(FEATURE_COLUMNS) + list(ARM_E_FEATURE_COLUMNS),
        "n_features": len(FEATURE_COLUMNS) + len(ARM_E_FEATURE_COLUMNS),
        "definedness": {
            c: {"n_defined": int(df[c].notna().sum()),
                "share_defined": round(float(df[c].notna().mean()), 6)}
            for c in (*ARM_E_FEATURE_COLUMNS, "native_slope_deg")},
        "upslope_alignment_correlations": corrs,
        "smoothing_columns": [f"upslope_alignment_s{int(w)}" for w in SMOOTH_WINDOWS_M],
        "native_slope_deg_distribution": {
            k: round(float(v), 3) for k, v in
            zip(("mean", "median", "p25", "p75", "max"),
                (df["native_slope_deg"].mean(), df["native_slope_deg"].median(),
                 df["native_slope_deg"].quantile(.25),
                 df["native_slope_deg"].quantile(.75),
                 df["native_slope_deg"].max()))},
        "build_seconds_by_fire": timings,
    }
    (OUT / "arm_e_dataset_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in
                      ("n_rows", "n_positives", "n_features",
                       "upslope_alignment_correlations",
                       "native_slope_deg_distribution")}, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fire", action="append", default=None)
    ap.add_argument("--merge", action="store_true")
    args = ap.parse_args()

    if args.merge:
        merge()
        return 0

    committed = json.loads(
        (REPO / "data/processed/spread_v2_lofo.json").read_text(encoding="utf-8"))
    wanted = args.fire or sorted(committed["per_fire_auc"])
    CACHE.mkdir(parents=True, exist_ok=True)
    for fid in wanted:
        if (CACHE / f"{fid}.pkl").exists():
            print(f"cached   {fid}")
            continue
        print(f"building {fid} ...", flush=True)
        print("  " + json.dumps(build_one(fid)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
