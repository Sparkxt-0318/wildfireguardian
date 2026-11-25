"""PROTOCOL_v3 section 9 + Amendment 1 items 1-3, model part: first runnable cutoff and earliest-path 6 h footprint.

Run in the pipeline environment from the workspace root, one fire per call (so fires can run in parallel):

    python partb_select.py --event CA-BTU-009205_Dixie --out OUT_DIR [--data /Users/jp/Desktop/wildfire/data/environment]

The data folder is only read. Writes OUT_DIR/<event>.npz (footprint, earliest, valid, transform, epsg) and
OUT_DIR/<event>.json (cutoff, how it was found, counts). Road length is computed afterwards by partb_roads.py.
"""
from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path

import numpy as np

DATA = "/Users/jp/Desktop/wildfire/data/environment"
SEED, SAMPLES, HOURS = 20261122, 1024, 6
MAX_TRIES = 48
FUTURE = ("future_labels", "newly_burned_area", "future_burned_area", "next_burned_area")


def burned_count(s):
    ba = np.asarray(s["burned_area"], float)
    v = np.asarray(s["burned_area_valid"], bool) if "burned_area_valid" in s else np.ones_like(ba, bool)
    return int(((ba > 0) & v).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--data", default=DATA)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()

    from wildfire import EnvironmentalCellDuration, LiveFuelMoisture, load_data, load_model
    from wildfire.environmental_duration import DURATION_SOURCE_CHANNELS
    from wildfire.schema import TRAINING_SOURCE_CHANNELS, HAZARD_SOURCE_CHANNELS

    channels = tuple(dict.fromkeys(TRAINING_SOURCE_CHANNELS + HAZARD_SOURCE_CHANNELS + DURATION_SOURCE_CHANNELS))
    model = load_model(device="cpu")
    rec = {"event": a.event, "data_root": a.data, "rule": "PROTOCOL_v3 Amendment 1 item 2", "tries": []}
    with load_data(a.data, events=[a.event], channels=channels, sequence_length=1, patch_size=None,
                   daily_policy="completed_day") as ds:
        n = len(ds)
        rec["n_snapshots"] = n
        # burned area is cumulative: binary search for the first snapshot with a burned, valid cell
        lo, hi = 0, n - 1
        if burned_count(ds[hi]) == 0:
            rec["status"] = "no burned cell in any snapshot"
        else:
            while lo < hi:
                mid = (lo + hi) // 2
                if burned_count(ds[mid]) > 0:
                    hi = mid
                else:
                    lo = mid + 1
            rec["first_burned_index"] = lo
            # monotonicity spot check: the snapshot before has none
            rec["first_burned_previous_has_none"] = bool(lo == 0 or burned_count(ds[lo - 1]) == 0)
            found = None
            for i in range(lo, min(n, lo + MAX_TRIES)):
                s = dict(ds[i])
                t_utc = int(np.asarray(s["time_utc"]).ravel()[0])
                for k in FUTURE:
                    s.pop(k, None)
                try:
                    if burned_count(s) == 0:
                        raise ValueError("no burned valid cell")
                    EnvironmentalCellDuration.from_sample(s, live_moisture=LiveFuelMoisture.from_scott_burgan("L2"))
                    spread = model.predict_cumulative(s, hours=list(range(1, HOURS + 1)), n_samples=SAMPLES, seed=SEED,
                                                      retain_trajectories=True, boundary="zero",
                                                      missing_burned_area="unburned")
                    found = (i, t_utc, s, spread)
                    rec["tries"].append({"index": i, "time_utc": t_utc, "ok": True})
                    break
                except Exception as e:  # noqa: BLE001 - recorded, the rule moves to the next snapshot
                    rec["tries"].append({"index": i, "time_utc": t_utc, "ok": False,
                                         "error": "%s: %s" % (type(e).__name__, str(e)[:300])})
            if found is None:
                rec["status"] = "no runnable cutoff within %d snapshots of the first burned one" % MAX_TRIES
            else:
                i, t_utc, s, spread = found
                first, valid, transform, epsg = spread.trajectories.select()
                first = np.asarray(first)
                burned0 = first[0] == 0
                reached = (first > 0) & (first <= HOURS)
                kmin = np.where(reached.any(axis=0), np.where(reached, first, 10 ** 6).min(axis=0), 0)
                earliest = np.where(burned0, 0.0, np.where(reached.any(axis=0), 60.0 * (kmin - 1), np.inf))
                vcov = np.asarray(valid)[: HOURS + 1].all(axis=0)
                foot = np.isfinite(earliest) & vcov
                np.savez_compressed(out / ("%s.npz" % a.event), footprint=foot, earliest_min=np.where(vcov, earliest, np.nan),
                                    valid=vcov, transform=np.asarray(transform, float), epsg=np.asarray(int(epsg)))
                rec.update(status="ok", cutoff_index=i, cutoff_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_utc)),
                           shape=list(foot.shape), burned_at_cutoff=int((burned0 & vcov).sum()),
                           reached_by_any_path=int((np.isfinite(earliest) & ~burned0 & vcov).sum()),
                           footprint_cells=int(foot.sum()), valid_cells=int(vcov.sum()))
    rec["elapsed_s"] = round(time.monotonic() - t0, 1)
    (out / ("%s.json" % a.event)).write_text(json.dumps(rec, indent=1))
    print(json.dumps({k: v for k, v in rec.items() if k != "tries"}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
