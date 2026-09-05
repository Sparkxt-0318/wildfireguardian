#!/usr/bin/env python
"""Build and cache the Arm D dataset, one fire at a time (Session 10, Phase 4b).

Per-fire caching is not premature optimisation: the full build is several
minutes, and this session's execution environment kills any single command that
runs longer than about three. Each invocation builds whatever is still missing
and stops cleanly, so the work resumes rather than restarting.

    python scripts/arm_d_build.py            # build all missing fires
    python scripts/arm_d_build.py --fire yeongdeok_2025
    python scripts/arm_d_build.py --merge    # combine the per-fire caches

Writes ONLY under data/processed/arms/D/. No Arm A path is touched.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

ARM = "D"
OUT = REPO / "data" / "processed" / "arms" / ARM
CACHE = OUT / "per_fire"


def build_one(fid: str) -> dict:
    from wildfireguardian.spread_v2_armd.dataset import build_arm_d_dataset

    t0 = time.time()
    df, cadence = build_arm_d_dataset([fid])
    dt = time.time() - t0
    CACHE.mkdir(parents=True, exist_ok=True)
    with (CACHE / f"{fid}.pkl").open("wb") as fh:
        pickle.dump({"df": df, "cadence": cadence, "build_seconds": round(dt, 2)}, fh)
    return {"fire": fid, "rows": int(len(df)),
            "positives": int(df["label"].sum()) if len(df) else 0,
            "seconds": round(dt, 1)}


def merge() -> None:
    import pandas as pd

    from wildfireguardian.spread_v2_armd.dataset import ARM_D_ALL_FEATURE_COLUMNS
    from wildfireguardian.spread_v2_armd.features import ARM_D_FEATURE_COLUMNS

    parts, cadence, timings = [], {}, {}
    for p in sorted(CACHE.glob("*.pkl")):
        with p.open("rb") as fh:
            blob = pickle.load(fh)
        if len(blob["df"]):
            parts.append(blob["df"])
        cadence.update(blob["cadence"])
        timings[p.stem] = blob.get("build_seconds")
    if not parts:
        raise SystemExit("no per-fire caches found — run without --merge first")

    df = pd.concat(parts, ignore_index=True)
    with (OUT / "arm_d_dataset.pkl").open("wb") as fh:
        pickle.dump(df, fh)

    defined = {
        c: {
            "n_defined": int(df[c].notna().sum()),
            "share_defined": round(float(df[c].notna().mean()), 6),
        }
        for c in ARM_D_FEATURE_COLUMNS
    }
    summary = {
        "arm": ARM,
        "provenance": "derived",
        "n_rows": int(len(df)),
        "n_positives": int(df["label"].sum()),
        "fires_used": sorted(df["fire_id"].unique().tolist()),
        "feature_columns": list(ARM_D_ALL_FEATURE_COLUMNS),
        "n_features": len(ARM_D_ALL_FEATURE_COLUMNS),
        "arm_d_feature_definedness": defined,
        "rows_by_n_prior_overpasses": {
            str(int(k)): int(v)
            for k, v in df["n_prior_overpasses"].value_counts().sort_index().items()
        },
        "overpass_cadence_by_fire": cadence,
        "build_seconds_by_fire": timings,
    }
    (OUT / "arm_d_dataset_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in
                      ("n_rows", "n_positives", "fires_used", "n_features")}, indent=2))
    print(f"wrote {OUT/'arm_d_dataset.pkl'} and arm_d_dataset_summary.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fire", action="append", default=None)
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.merge:
        merge()
        return 0

    from wildfireguardian.spread_v2 import data as datamod

    all_fires = [m.id for m in datamod.list_fires()]
    if args.list:
        print("\n".join(all_fires))
        return 0

    wanted = args.fire or all_fires
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
