#!/usr/bin/env python
"""How much of this model's skill comes from instantaneous weather? — PHASE 14.

Run:  python scripts/measure_weather_dependency.py
Out:  data/processed/weather_dependency.json  ·  docs/weather_dependency.md

WHY IT EXISTS
-------------
PHASE 14 asked whether ERA5 (~5-day publication lag) could be replaced by forecast
data, and how much accuracy that would cost. Before acquiring anything, this
measures the CEILING on that cost: if the swappable weather features carried NO
information at all, how far would the LOFO AUC fall? A real forecast still carries
some information about those quantities, so its degradation cannot exceed this.

The answer decided the phase. See docs/weather_dependency.md.

If the six GFS-swappable weather features carried NO information at all, how far
would the LOFO AUC fall? GFS degradation cannot exceed that, because GFS still
carries some information about those same quantities.

⚠ READ-ONLY with respect to the repository. Every output goes to this scratch
directory. Nothing under data/processed is opened for writing.

Arms
----
A0  all 16 features                    reproduces the committed baseline (harness check)
A1  drop the 6 swappable               the ceiling, dimensionality reduced
A2  shuffle the 6 swappable            the ceiling, dimensionality preserved
A3  drop all 7 weather features        what the model is without weather at all
A4  drop days_since_rain only          is the #1 feature measuring rain or window length?
A5  drop wind_speed_ms only            the single largest swappable contributor
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "processed" / "weather_dependency.json"
CACHE = REPO / ".cache_weather_dependency.pkl"   # git-ignored scratch
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.spread_v2.features import FEATURE_COLUMNS, build_dataset  # noqa: E402
from wildfireguardian.spread_v2.model import DEFAULT_SEED, IgnitionModelV2, _safe_auc  # noqa: E402

#: Swapped when ERA5 -> GFS. days_since_rain is NOT here: the agreed design keeps
#: it on ERA5 (a forecast has no precipitation history before initialisation), so
#: it is not part of the contrast.
SWAPPABLE = ("wind_speed_ms", "temp_c", "rh_pct", "vpd_kpa",
             "precip_24h_mm", "wind_alignment")
WEATHER_ALL = (*SWAPPABLE, "days_since_rain")

ARMS = {
    "A0_all_16":            (),
    "A1_drop_swappable":    SWAPPABLE,
    "A2_shuffle_swappable": SWAPPABLE,          # handled specially
    "A3_drop_all_weather":  WEATHER_ALL,
    "A4_drop_days_since_rain": ("days_since_rain",),
    "A5_drop_wind_speed":   ("wind_speed_ms",),
}
SHUFFLE_ARMS = {"A2_shuffle_swappable"}


def lofo(ds: pd.DataFrame, cols: tuple[str, ...], *, shuffle: tuple[str, ...] = (),
         seed: int = DEFAULT_SEED) -> dict:
    """Mirror of model.leave_one_fire_out, with a feature subset / shuffle."""
    rng = np.random.default_rng(seed)
    fires = sorted(ds["fire_id"].unique())
    per_fire: dict[str, float | None] = {}
    parts: list[pd.DataFrame] = []

    work = ds
    if shuffle:
        work = ds.copy()
        for c in shuffle:
            work[c] = rng.permutation(work[c].to_numpy())

    for held in fires:
        train = work[work["fire_id"] != held]
        test = work[work["fire_id"] == held]
        if train["label"].nunique() < 2 or len(test) == 0:
            per_fire[held] = None
            continue
        m = IgnitionModelV2(seed=seed, feature_columns=cols).fit(train)
        p = m.predict_proba(test)
        per_fire[held] = _safe_auc(test["label"].to_numpy(), p)
        part = test[["fire_id", "label", "dist_band"]].copy()
        part["prob"] = p
        parts.append(part)

    oof = pd.concat(parts, ignore_index=True)
    vals = [v for v in per_fire.values() if v is not None]
    far = oof[oof["dist_band"] == "far"]
    return {
        "n_features": len(cols),
        "mean_of_folds": float(np.mean(vals)),
        "std_of_folds": float(np.std(vals, ddof=1)),
        "pooled": _safe_auc(oof["label"].to_numpy(), oof["prob"].to_numpy()),
        "far_band": _safe_auc(far["label"].to_numpy(), far["prob"].to_numpy()) if len(far) else None,
        "per_fire": per_fire,
    }


def main() -> int:
    cache = CACHE
    if cache.exists():
        ds = pd.read_pickle(cache)
        print(f"dataset from cache: {ds.shape}")
    else:
        from wildfireguardian.config import get as _cfg
        from wildfireguardian.spread_v2 import data as datamod
        t0 = time.time()
        # Identical to scripts/build_canonical_hazard.py:117-118 — same fire list,
        # same buffer — so A0 must reproduce the committed (151904, 2989).
        fire_ids = [m.id for m in datamod.list_fires()]
        ds = build_dataset(fire_ids,
                           buffer_m=float(_cfg("grid.feature_buffer_m", 6000.0)))
        ds.to_pickle(cache)
        print(f"dataset built in {time.time()-t0:.0f}s: {ds.shape}")

    n_rows, n_pos = len(ds), int(ds["label"].sum())
    print(f"  rows={n_rows:,}  positives={n_pos:,}  "
          f"(committed: 151,904 / 2,989 -> {'MATCH' if (n_rows, n_pos) == (151904, 2989) else 'DIFFERS'})")
    print(f"  fires: {sorted(ds['fire_id'].unique())}\n")

    out: dict[str, dict] = {}
    for name, drop in ARMS.items():
        shuffle = drop if name in SHUFFLE_ARMS else ()
        cols = FEATURE_COLUMNS if shuffle else tuple(c for c in FEATURE_COLUMNS if c not in drop)
        t0 = time.time()
        r = lofo(ds, cols, shuffle=shuffle)
        r["dropped" if not shuffle else "shuffled"] = list(drop)
        r["seconds"] = round(time.time() - t0, 1)
        out[name] = r
        print(f"{name:26} nfeat={r['n_features']:2}  "
              f"mean-of-folds={r['mean_of_folds']:.4f}  pooled={r['pooled']:.4f}  "
              f"({r['seconds']}s)")

    base = out["A0_all_16"]
    for name, r in out.items():
        r["delta_mean_of_folds_vs_A0"] = round(r["mean_of_folds"] - base["mean_of_folds"], 5)
        r["delta_pooled_vs_A0"] = round(r["pooled"] - base["pooled"], 5)
        r["per_fire_delta_vs_A0"] = {
            k: (None if (v is None or base["per_fire"].get(k) is None)
                else round(v - base["per_fire"][k], 5))
            for k, v in r["per_fire"].items()
        }

    rec = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "seed": DEFAULT_SEED, "n_rows": n_rows, "n_positives": n_pos,
           "swappable_features": list(SWAPPABLE), "arms": out}
    OUT.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
