#!/usr/bin/env python3
"""Export hourly cumulative new-burn probability for the layer viewer (KFS_01, 의성·안동 2025).

Runs the forecast package's recursive Monte Carlo rollout (`model.predict_cumulative`,
method="recursive") with the maintained checkpoint (c651…, mixed 3/5/7/9) at each recorded
input time, for horizons 1..H hours, and saves per-hour cumulative probability F(h), total
burned probability, Monte Carlo standard error and validity on the native 375 m event grid.

Nothing is retrained and no forecasting code is modified; this only calls the public API.
It needs the aligned environmental data tree that is not published on GitHub
(forecast/README.md, "External inputs"). Run it where that tree exists:

    cd forecast
    .venv/bin/python /path/to/export_hourly_cumulative.py --data-root data/environment --out kfs01_hourly.npz

Environment for later hours (--env):
  recorded  (default) slice k of `environmental_forecast` is the recorded snapshot at t+k h,
            i.e. a retrospective run with the hourly inputs that were later recorded.
  persist   no environmental_forecast; the cutoff conditions repeat every hour (API default).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

CUTOFFS = ("2025-03-23T01:00:00Z", "2025-03-24T09:00:00Z", "2025-03-25T17:00:00Z")
EXPECTED_CHECKPOINT_PREFIX = "c651f6724fe6b036"


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_numpy(x):
    try:
        import torch
        if isinstance(x, torch.Tensor):
            return x.detach().cpu().numpy()
    except ImportError:
        pass
    return np.asarray(x)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", default=None, help="aligned environmental data root (default: forecast/data/environment)")
    ap.add_argument("--event", default="KFS_01")
    ap.add_argument("--cutoffs", nargs="+", default=list(CUTOFFS))
    ap.add_argument("--every", type=int, default=0,
                    help="instead of --cutoffs: every N hours from 2025-03-23T01:00Z to 2025-03-26T08:00Z (skips times without inputs)")
    ap.add_argument("--hours", type=int, default=12)
    ap.add_argument("--samples", type=int, default=1024, help="Monte Carlo trajectories (n_samples)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--batch", type=int, default=32, help="trajectory_batch_size")
    ap.add_argument("--env", choices=("recorded", "persist"), default="recorded")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--allow-other-checkpoint", action="store_true")
    ap.add_argument("--out", default="kfs01_hourly.npz")
    a = ap.parse_args(argv)

    from wildfire import load_data, load_model, select_time, available_cutoffs
    from wildfire.paths import DEFAULT_CHECKPOINT, DATA_ROOT
    from wildfire.schema import TRAINING_SOURCE_CHANNELS

    root = Path(a.data_root) if a.data_root else Path(DATA_ROOT)
    ckpt = Path(DEFAULT_CHECKPOINT)
    ck_sha = sha256(ckpt)
    if not ck_sha.startswith(EXPECTED_CHECKPOINT_PREFIX) and not a.allow_other_checkpoint:
        print(f"checkpoint {ckpt} is {ck_sha[:16]}, not c651; pass --allow-other-checkpoint to continue", file=sys.stderr)
        return 2
    H = a.hours
    need = H if a.env == "recorded" else 1
    ok = set(available_cutoffs(a.event, data_root=root, sequence_length=need))
    if a.every > 0:
        start = datetime(2025, 3, 23, 1, tzinfo=timezone.utc)
        grid = [iso(start + timedelta(hours=h)) for h in range(0, 80, a.every)]
        a.cutoffs = [c for c in grid if c in ok]
        print(f"{len(a.cutoffs)} cutoffs every {a.every} h ({len(grid) - len(a.cutoffs)} skipped without a complete {need}-hour input window)")
    for c in a.cutoffs:
        if c not in ok:
            print(f"cutoff {c} has no complete {need}-hour input window for {a.event} under {root}", file=sys.stderr)
            return 2

    model = load_model(device=a.device)
    out: dict[str, np.ndarray] = {}
    meta = dict(event=a.event, cutoffs=a.cutoffs, hours=list(range(1, H + 1)), n_samples=a.samples, seed=a.seed,
                trajectory_batch_size=a.batch, env=a.env, method="recursive", boundary="zero",
                missing_burned_area="unburned", checkpoint=str(ckpt), checkpoint_sha256=ck_sha,
                data_root=str(root), generated_at=iso(datetime.now(timezone.utc)), runs=[])
    with load_data(root, events=[a.event], channels=TRAINING_SOURCE_CHANNELS,
                   sequence_length=None, patch_size=None) as data:
        if len(data) != 1:
            print(f"expected one full-rectangle sample for {a.event}, got {len(data)}", file=sys.stderr)
            return 2
        timeline = data[0]
    for k, c in enumerate(a.cutoffs):
        t0 = datetime.strptime(c, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        sample = select_time(timeline, c)
        kw = dict(hours=list(range(1, H + 1)), method="recursive", n_samples=a.samples, seed=a.seed,
                  trajectory_batch_size=a.batch, boundary="zero", missing_burned_area="unburned")
        if a.env == "recorded":
            # slice 0 drives (t, t+1h] with the snapshot at t (as ordinary one-hour prediction does),
            # slice k drives (t+k, t+k+1] with the recorded snapshot at t+k.
            seq = select_time(timeline, c, iso(t0 + timedelta(hours=H - 1)))
            kw["environmental_forecast"] = {
                "features": seq["features"][:, None],
                "feature_valid": seq["feature_valid"][:, None],
                "channel_names": list(seq["channel_names"]),
            }
        started = time.time()
        res = model.predict_cumulative(sample, **kw)
        arr = res.numpy()
        secs = time.time() - started
        prob = to_numpy(arr["probability"]).reshape(H, *to_numpy(arr["probability"]).shape[-2:]).astype(np.float32)
        valid = to_numpy(arr["valid"]).reshape(prob.shape).astype(bool)
        se = to_numpy(arr["mc_standard_error"]).reshape(prob.shape).astype(np.float32)
        burned = to_numpy(arr.get("burned_probability", prob)).reshape(prob.shape).astype(np.float32)
        init = to_numpy(sample["burned_area"])[0, 0].astype(np.float32)
        out[f"c{k}_probability"] = prob
        out[f"c{k}_burned_probability"] = burned
        out[f"c{k}_mc_standard_error"] = se
        out[f"c{k}_valid"] = valid
        out[f"c{k}_initial_burned"] = init
        if k == 0:
            out["affine_transform"] = to_numpy(sample["affine_transform"]).astype(np.float64)
            out["epsg"] = np.array(int(to_numpy(sample["epsg"])))
        cells = valid.any(0).sum()
        exp_km2 = [float(np.nansum(np.where(valid[h], prob[h], 0)) * 0.140625) for h in range(H)]
        meta["runs"].append(dict(cutoff=c, seconds=round(secs, 1), valid_cells=int(cells), expected_new_km2=exp_km2,
                                 metadata=json.loads(str(arr["metadata_json"])) if "metadata_json" in arr else None))
        print(f"{c}: {secs:.0f}s, valid {cells} cells, expected new burn {exp_km2[0]:.2f} km² at 1 h → {exp_km2[-1]:.2f} km² at {H} h")
    out["meta_json"] = np.array(json.dumps(meta, ensure_ascii=False))
    np.savez_compressed(a.out, **out)
    print(f"wrote {a.out} ({Path(a.out).stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
