#!/usr/bin/env python
"""Did sea cells get into the training set, and did they flatter the AUC?

Round-3, follow-up to the 2026-08-02 DEM defect
(``docs/dem_defect_2026-08-02.md``).

THE HYPOTHESIS UNDER TEST
-------------------------
The pre-2026-08-02 Uljin-Samcheok raster filled the East Sea with a ramp down to
−497 m. A grid cell over open water is an "easy negative": nothing there can
ignite, and a model that learns *elevation below zero implies no ignition* gets
those rows right for free. If enough of them are in the pooled negative class,
the reported AUC is optimistic — not because the model is wrong, but because the
test set contains rows no method could get wrong.

WHAT IT MEASURES
----------------
1. How many dataset rows carry ``elevation_m < 0``, overall and per fire, and
   what their label composition is.
2. The same counts under the CORRECTED rasters, so the change is attributable.
3. Leave-one-fire-out AUC with those rows **excluded**, against the same LOFO
   with them included — one variable, same seed, same features.

An affirmative result means the headline AUC is inflated. A null result is
equally reportable and is stated as such: it would mean sea cells were present
but not doing the work.

Writes ``data/processed/dem_negative_elevation_audit.json``. Touches no
committed artifact.

Run:  python scripts/audit_negative_elevation.py --old-dem-dir /path/to/old
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.spread_v2 import data, features  # noqa: E402
from wildfireguardian.spread_v2.model import leave_one_fire_out  # noqa: E402


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def build(data_dir: str | None, cell_m: float, buffer_m: float):
    """Build the pooled feature dataset against a specific FIRMS directory."""
    prev = os.environ.get("WFG_FIRMS_DIR")
    if data_dir:
        os.environ["WFG_FIRMS_DIR"] = str(data_dir)
    try:
        # find_data_dir() is deliberately uncached, so the swap takes effect.
        fire_ids = [m.id for m in data.list_fires()]
        ds = features.build_dataset(fire_ids, cell_size_m=cell_m, buffer_m=buffer_m)
    finally:
        if prev is None:
            os.environ.pop("WFG_FIRMS_DIR", None)
        else:
            os.environ["WFG_FIRMS_DIR"] = prev
    return ds


def profile(ds) -> dict:
    """Row counts and label composition, overall and per fire, at elev < 0."""
    neg = ds["elevation_m"] < 0.0
    lab = ds["label"].astype(int)
    out = {
        "n_rows": int(len(ds)),
        "n_positives": int(lab.sum()),
        "n_rows_negative_elevation": int(neg.sum()),
        "frac_rows_negative_elevation": float(neg.mean()),
        "min_elevation_m": float(ds["elevation_m"].min()),
        "negative_elevation_rows": {
            "n_positive": int(lab[neg].sum()),
            "n_negative": int((~lab.astype(bool))[neg].sum()),
            "positive_rate": float(lab[neg].mean()) if neg.any() else None,
        },
        "all_rows_positive_rate": float(lab.mean()),
        "per_fire": {},
    }
    for fid, g in ds.groupby("fire_id"):
        gneg = g["elevation_m"] < 0.0
        glab = g["label"].astype(int)
        out["per_fire"][str(fid)] = {
            "n_rows": int(len(g)),
            "n_negative_elevation": int(gneg.sum()),
            "frac_negative_elevation": float(gneg.mean()),
            "min_elevation_m": float(g["elevation_m"].min()),
            "n_positives_in_negative_elevation": int(glab[gneg].sum()),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old-dem-dir", default=None,
                    help="FIRMS directory holding the PRE-2026-08-02 rasters. "
                         "Omit to profile only the current ones.")
    ap.add_argument("--seed", type=int, default=int(_cfg("seeds.canonical", 20250603)))
    # 500 m, NOT the rescue pipeline's 375 m. This must match
    # run_routing_integration.py or the dataset is not the one the committed
    # LOFO was computed on (151,904 rows / 2,989 positives at 500 m; 280,786 /
    # 4,344 at 375 m — a different experiment answering a different question).
    ap.add_argument("--cell-m", type=float,
                    default=float(_cfg("grid.routing_integration_hazard_cell_m", 500.0)))
    ap.add_argument("--buffer-m", type=float, default=float(_cfg("grid.feature_buffer_m", 6000.0)))
    ap.add_argument("--out", default=str(REPO / "data/processed/dem_negative_elevation_audit.json"))
    args = ap.parse_args()

    doc = {
        "schema_version": 1,
        "title": "Are sea cells inflating the reported AUC?",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(),
        "config_hash": config_hash(),
        "seed": args.seed,
        "hypothesis": (
            "A grid cell over open water is an EASY NEGATIVE. The pre-2026-08-02 "
            "Uljin-Samcheok raster filled the sea with a ramp to -497 m, so if "
            "those rows are in the pooled negatives the reported AUC is "
            "optimistic."),
        "arms": {},
    }

    arms = [("corrected_dem", None)]
    if args.old_dem_dir:
        arms.insert(0, ("old_dem", args.old_dem_dir))

    for name, ddir in arms:
        print(f"\n=== arm: {name} ===")
        ds = build(ddir, args.cell_m, args.buffer_m)
        prof = profile(ds)
        print(f"  rows {prof['n_rows']:,}  positives {prof['n_positives']:,}  "
              f"min elevation {prof['min_elevation_m']:.1f} m")
        print(f"  rows with elevation < 0: {prof['n_rows_negative_elevation']:,} "
              f"({prof['frac_rows_negative_elevation'] * 100:.2f} %), of which "
              f"{prof['negative_elevation_rows']['n_positive']} are POSITIVE")

        print("  LOFO with every row (the committed configuration) ...")
        full = leave_one_fire_out(ds, seed=args.seed, compute_importance=False)
        keep = ds[ds["elevation_m"] >= 0.0]
        print(f"  LOFO excluding negative-elevation rows "
              f"({len(ds) - len(keep):,} dropped) ...")
        filt = leave_one_fire_out(keep, seed=args.seed, compute_importance=False)

        def _auc_block(res):
            return {"pooled_auc": res.pooled_auc,
                    "mid_band_auc": res.mid_band_auc,
                    "far_band_auc": res.far_band_auc,
                    "per_fire_auc": res.per_fire_auc,
                    "mean_of_folds_auc": (
                        float(np.mean([v for v in res.per_fire_auc.values()
                                       if v is not None]))
                        if any(v is not None for v in res.per_fire_auc.values())
                        else None)}

        a_full, a_filt = _auc_block(full), _auc_block(filt)
        delta = {
            "pooled_auc": (None if a_full["pooled_auc"] is None or a_filt["pooled_auc"] is None
                           else a_filt["pooled_auc"] - a_full["pooled_auc"]),
            "mean_of_folds_auc": (None if a_full["mean_of_folds_auc"] is None
                                  or a_filt["mean_of_folds_auc"] is None
                                  else a_filt["mean_of_folds_auc"] - a_full["mean_of_folds_auc"]),
            "per_fire_auc": {
                k: (None if a_full["per_fire_auc"].get(k) is None
                    or a_filt["per_fire_auc"].get(k) is None
                    else a_filt["per_fire_auc"][k] - a_full["per_fire_auc"][k])
                for k in a_full["per_fire_auc"]},
        }
        doc["arms"][name] = {
            "firms_dir": str(ddir) if ddir else "repo default (data/raw/firms_data)",
            "profile": prof,
            "lofo_all_rows": a_full,
            "lofo_excluding_negative_elevation": a_filt,
            "delta_excluding_minus_all": delta,
            "n_rows_dropped": int(len(ds) - len(keep)),
        }
        print(f"  pooled AUC  all rows {a_full['pooled_auc']:.4f}  ->  "
              f"excluding {a_filt['pooled_auc']:.4f}  "
              f"(delta {delta['pooled_auc']:+.4f})")
        print(f"  mean-of-folds all rows {a_full['mean_of_folds_auc']:.4f}  ->  "
              f"excluding {a_filt['mean_of_folds_auc']:.4f}  "
              f"(delta {delta['mean_of_folds_auc']:+.4f})")

    doc["reading_rule"] = (
        "A NEGATIVE delta (AUC falls once sea cells are removed) supports the "
        "hypothesis: the committed figure was flattered by easy negatives. A "
        "delta near zero refutes it, and that refutation is a result, not an "
        "absence of one. Report whichever occurred.")
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
    print(f"\nwrote {Path(args.out).relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
