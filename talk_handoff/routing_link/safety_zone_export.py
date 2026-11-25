"""One path, one minute: the data for the safety-zone figure (PROTOCOL.md Amendment 3). Run like perpath_export.py:

    cd WORKSPACE && PYTHONPATH=WORKSPACE python safety_zone_export.py --out export_v2

Writes export_v2/safety_zone_path.npz:
* path, minute (the Amendment 3 rule), burned_cells_by_path [1024]
* radiant_kw_m2 [360, ny, nx]  that path's 60 s radiant flux
* burning [360, ny, nx]        weight > 0 in that path and minute
* fire_arrival_min [ny, nx]    that path's ignition minute (0 at the cutoff, +inf never)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import perpath_export as E  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from wildfire import monte_carlo_hazards as mch
    initial, spread, factory = E.setup(6)
    cap = []
    original = mch._window_exposure

    def capture(*args, **kw):
        cap.append((args, kw))  # only the pipeline's support and physics are needed; one call for all six hours,
        # as in v1/v2, so every hour has the same source set

    mch._window_exposure = capture
    try:
        spread.calculate_hazards(hours_later=list(range(6)), initial_activity=initial, physical_factory=factory,
                                 ignition_timing="uniform_within_step", timing_seed=E.SEED, time_step_s=60.,
                                 batch_size=E.BATCH_PIPELINE, activity_mode="probability_map")
    finally:
        mch._window_exposure = original
    pw = E.PathWeights(cap)
    first = np.asarray(spread.trajectories.select()[0])
    H, (ny, nx) = 6, first.shape[1:]
    burned = ((first >= 0) & (first <= H)).reshape(len(first), -1).sum(axis=1)
    med = np.median(burned)
    path = int(np.argmin(np.abs(burned - med)))          # lowest index on a tie
    edges = np.r_[np.arange(0., 3600., 60.), 3600.]
    rad, burn = [], []
    for h in range(H):
        w = pw.weights(np.array([path]), h, edges)
        r, _ = E.fields(cap[h][0][6], w, edges)
        rad.append(r[0].reshape(60, ny, nx) / 1000.)
        b = np.zeros((60, ny * nx), bool)
        b[:, pw.source] = w[0] > 0
        burn.append(b.reshape(60, ny, nx))
    rad, burn = np.concatenate(rad), np.concatenate(burn)
    minute = int(np.argmax(burn.reshape(len(burn), -1).sum(axis=1)))   # earliest on a tie
    fa = np.full(ny * nx, np.inf)
    src = pw.source
    occ = pw.occurrence[path]
    on = np.where(first[path].ravel()[src] == 0, 0.0, np.floor(pw.onset[path] / 60.0))
    # cells burned at the cutoff are 0 as in v1 (burning or burnt at issue), whether or not still flaming
    fa[src] = np.where((first[path].ravel()[src] == 0) | occ, on, np.inf)
    fa = np.where(fa >= 60 * H, np.inf, fa).reshape(ny, nx)
    np.savez_compressed(Path(a.out) / "safety_zone_path.npz", path=np.int64(path), minute=np.int64(minute),
                        burned_cells_by_path=burned, median_burned_cells=med, radiant_kw_m2=rad.astype(np.float32),
                        burning=burn, fire_arrival_min=fa)
    print("path", path, "burned cells", int(burned[path]), "median", med, "minute", minute,
          "cells burning then", int(burn[minute].sum()))


if __name__ == "__main__":
    main()
