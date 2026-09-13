#!/usr/bin/env python
"""Probe for the corridor-treatment atlas: reproduce the canonical 영덕 forward simulation
on this machine and time each stage. Writes only .auto/atlas_base.pkl (git-ignored cache of
the fitted model, event, weather, grid, static layers) and prints timings. Compares the
reproduced hazard stack to the committed data/processed/routing_demo_canonical.npz.

    python scripts/atlas_base_probe.py
"""
from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.config import get as _cfg  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.spread_v2 import data, features, grid as gridmod  # noqa: E402
from wildfireguardian.spread_v2.features import StaticLayers  # noqa: E402
from wildfireguardian.spread_v2.forward_sim import forward_simulate  # noqa: E402
from wildfireguardian.spread_v2.model import IgnitionModelV2  # noqa: E402
from wildfireguardian.spread_v2.weather import weather_series_from_event  # noqa: E402

CACHE = REPO / ".auto" / "atlas_base.pkl"
FIRE = "yeongdeok_2025"
BBOX = (128.92, 36.1, 129.77, 36.9)      # canonical final canvas (canonical_hazard.json)
CELL, N_STEPS, STEP_H, ADV = 500.0, 4, 3.0, 0.3


def main() -> int:
    t0 = time.monotonic()
    fire_ids = [m.id for m in data.list_fires()]
    ds = features.build_dataset(fire_ids, cell_size_m=CELL, buffer_m=float(_cfg("grid.feature_buffer_m", 6000.0)))
    print(f"dataset {len(ds):,} rows {int(ds['label'].sum()):,} pos  {time.monotonic()-t0:.0f}s", flush=True)
    assert (len(ds), int(ds["label"].sum())) == (151904, 2989), "not the canonical dataset"
    t1 = time.monotonic()
    model = IgnitionModelV2(seed=int(_cfg("seeds.canonical", 20250603))).fit(ds[ds["fire_id"] != FIRE])
    print(f"fit {time.monotonic()-t1:.0f}s", flush=True)
    ev = data.load_event(FIRE); ws = weather_series_from_event(ev)
    hg = gridmod.build_grid(BBOX, cell_size_m=CELL)
    snaps = gridmod.overpass_snapshots(ev, hg, gap_minutes=90.0)
    static = StaticLayers.from_event(ev, hg)
    t2 = time.monotonic()
    sim = forward_simulate(model, ev, hg, static, snaps[0].cumulative_mask, snaps[0].time, ws,
                           n_steps=N_STEPS, step_hours=STEP_H, advance_threshold=ADV)
    hz = HazardSequence.from_forward_sim(sim)
    print(f"forward sim {time.monotonic()-t2:.0f}s  grid {hg.nrows}x{hg.ncols}", flush=True)
    stack = np.array(hz.surfaces, dtype=np.float32)
    z = np.load(REPO / "data/processed/routing_demo_canonical.npz")
    ref = z["haz_stack"]
    print("shape", stack.shape, "ref", ref.shape)
    if stack.shape == ref.shape:
        d = np.abs(stack - ref); print(f"max abs diff {d.max():.4f}, mean {d.mean():.6f}, cells>=0.5 per slice {[int((stack[i]>=0.5).sum()) for i in range(stack.shape[0])]} ref {[int((ref[i]>=0.5).sum()) for i in range(ref.shape[0])]}")
    CACHE.parent.mkdir(exist_ok=True)
    with CACHE.open("wb") as fh:
        pickle.dump({"model": model, "fire": FIRE, "bbox": BBOX, "cell": CELL, "n_steps": N_STEPS, "step_h": STEP_H, "adv": ADV,
                     "burnable_frac": static.burnable_frac, "elevation": static.elevation, "slope": static.slope,
                     "initial_active": snaps[0].cumulative_mask, "start_time": snaps[0].time,
                     "grid_extent": [hg.minx, hg.miny, hg.maxx, hg.maxy, hg.cell_size_m, hg.nrows, hg.ncols],
                     "base_stack": stack, "max_abs_diff_vs_committed": float(np.abs(stack - ref).max()) if stack.shape == ref.shape else None}, fh)
    print("cached", CACHE, f"total {time.monotonic()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
