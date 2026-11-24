"""F04 stage (b): run the finals checkpoint M548 ("mixed") on the Uiseong event (KFS_01) at 2025-03-25 09:00 UTC.

Run once with the forecast workspace's own code and pinned packages (Python 3.12, torch 2.5.1; see make_all.sh):

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$WILDFIRE .venv-model/bin/python src/F04_forecast.py

It writes build/F04_forecast.npz (committed); F04_overview.py only reads that file. Nothing is written inside the
workspace (no bytecode, no caches). Steps:
  1. load_model(M548 checkpoint) and check its SHA-256 against the matched observed evaluation's protocol.json;
  2. load_data(events=["KFS_01"], whole timeline) and select_time(2025-03-25T09:00:00Z), the F02 issue hour
     (18:00 KST). The current burned state in the sample is the retrospective reconstruction (Zenodo 21788344);
  3. WildfireModel.predict(sample): next-hour new-burn probability on the 237 x 79 grid (boundary 'zero', the API
     default);
  4. the four branch kernels at one cell: the unburned cell with the largest predicted probability inside the
     Uiseong-Andong planner region. Each branch kernel is multiplied by its global mixing coefficient, so the four
     maps add up to the combined kernel that enters rate = sum K * B (h^-1);
  5. checks: the rate rebuilt from the four kernels and the burned neighbours equals the model's own rate at that
     cell, and 1 - exp(-rate) equals its probability.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

WS = Path(os.environ.get("WILDFIRE", "/Users/jp/Desktop/wildfire"))
sys.path.insert(0, str(WS))
import torch  # noqa: E402
from wildfire.api import load_model  # noqa: E402
from wildfire.data import load_data, select_time  # noqa: E402

FIG = Path(__file__).resolve().parents[1]
CKPT = WS / "runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt"
PROTOCOL = WS / "runs/20261013_observed_merged/protocol.json"
T = "2025-03-25T09:00:00Z"
UA_BBOX = None


def main():
    sha = hashlib.sha256(CKPT.read_bytes()).hexdigest()
    want = json.loads(PROTOCOL.read_text())["checkpoint_sha256"]
    assert sha == want, (sha, want)
    test_events = json.loads(PROTOCOL.read_text())["checkpoint_test_events"]
    model = load_model(CKPT, device="cpu")
    ds = load_data(WS / "data/environment", events=["KFS_01"], sequence_length=None)
    assert len(ds) == 1
    sample = select_time(ds[0], T)
    pred = model.predict(sample)
    prob = np.asarray(pred.probability).reshape(sample["burned_area"].shape[-2:]).astype(np.float32)
    valid = np.asarray(pred.valid).reshape(prob.shape)
    rate = np.asarray(pred.rate).reshape(prob.shape)
    burned = np.asarray(sample["burned_area"]).reshape(prob.shape).astype(np.float32)
    tr = np.asarray(sample["affine_transform"], dtype=float).ravel()
    # the Uiseong-Andong planner region (scene.js regions.uiseong_andong_2025.grid, EPSG:5179) in this grid's cells
    rx0, ry0, rres, rw, rh = 1093875.0, 1815750.0, 375.0, 73, 65
    col0 = int(round((rx0 - tr[2]) / tr[0])) if abs(tr[1]) < 1e-9 else None
    row_top = int(round((ry0 + rh * rres - tr[5]) / tr[4])) if col0 is not None else None
    if col0 is None:          # affine stored as (a, b, c, d, e, f) with c, f the origin
        raise SystemExit("unexpected affine layout")
    region = np.zeros(prob.shape, bool)
    region[max(row_top, 0):row_top + rh, max(col0, 0):col0 + rw] = True
    cand = np.where(region & valid & (burned == 0) & np.isfinite(prob), prob, -1)
    r, c = np.unravel_index(int(np.argmax(cand)), prob.shape)
    # kernels at (r, c): the same normalized inputs the predictor uses
    feats, fvalid = model._sample_environment(sample)
    feats = torch.as_tensor(np.asarray(feats), dtype=model.predictor.mean.dtype)
    fvalid = None if fvalid is None else torch.as_tensor(np.asarray(fvalid), dtype=torch.bool)
    norm = (feats - model.predictor.mean) / model.predictor.std
    mixed = model.predictor.model
    with torch.inference_mode():
        branch = mixed.branch_kernel_rates(norm, fvalid, boundary="zero")
        w = mixed.mixing_weights().numpy()
    K = mixed.kernel_size
    kern = {}
    total = 0.0
    B = np.pad(burned, K // 2)[r:r + K, c:c + K]
    for i, size in enumerate(mixed.kernel_sizes):
        k = branch[size].numpy().reshape(-1, size * size, *prob.shape)[0, :, r, c].reshape(size, size) * w[i]
        kern[size] = k
        m = (K - size) // 2
        total += float(np.nansum(k * B[m:m + size, m:m + size]))
    assert np.isclose(total, rate[r, c], rtol=1e-4, atol=1e-9), (total, rate[r, c])
    assert np.isclose(1 - np.exp(-rate[r, c]), prob[r, c], rtol=1e-4, atol=1e-9)
    out = dict(probability=prob, valid=valid, burned=burned, rate=rate, affine=tr, cell=np.array([r, c]),
               region_rows_cols=np.array([row_top, col0, rh, rw]),
               mixing_weights=w.astype(np.float64), kernel_sizes=np.array(mixed.kernel_sizes))
    for size, k in kern.items():
        out[f"kernel_{size}"] = k.astype(np.float64)
        out[f"burned_{size}"] = B[(K - size) // 2:(K + size) // 2, (K - size) // 2:(K + size) // 2]
    meta = {"checkpoint": str(CKPT.relative_to(WS)), "checkpoint_sha256": sha, "event": "KFS_01", "time_utc": T,
            "kfs01_is_checkpoint_test_event": "KFS_01" in test_events, "boundary": "zero",
            "architecture": model.predictor.contract["architecture"], "channels": len(model.channel_names),
            "cell_rate_per_h": float(rate[r, c]), "cell_probability": float(prob[r, c]),
            "rate_rebuilt_from_kernels": total, "torch": torch.__version__, "numpy": np.__version__,
            "max_probability_region": float(prob[region & valid].max()),
            "cells_valid": int(valid.sum()), "cells_burned": int((burned == 1).sum())}
    out["meta_json"] = np.array(json.dumps(meta))
    np.savez_compressed(FIG / "build/F04_forecast.npz", **out)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
