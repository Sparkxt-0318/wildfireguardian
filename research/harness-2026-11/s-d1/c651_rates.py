"""Where does the fitted c651 kernel sit between the toy's slow and fast regimes? (sizing proxy)

Two measurements, both labelled:
(A) REAL INPUT, one snapshot: the c651 Fish Creek demonstration
    (forecast/demonstration/heat_spatial_maps/20261013_fishcreek, checkpoint c651f672...),
    rate = -log(1 - q) at unburned cells adjacent to (ring 1) or 2-4 cells from the burned set.
(B) PROXY, synthetic inputs: the c651 checkpoint's kernel generator evaluated on spatially uniform
    9x9 environmental patches over a grid of raw covariates (temperature, wind speed/direction, slope,
    tree cover, each of the 14 biomes). Reported: total coefficient sum (rate of a fully surrounded
    target), half-plane sum facing the wind (a straight front upwind of the target) and the max single
    coefficient. Uniform patches are not real environments; this is a range check only.

    python research/harness-2026-11/s-d1/c651_rates.py
"""
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "forecast"))
from wildfire.inference import load_trained_model  # noqa: E402

CKPT = REPO / "forecast/runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt"


def real_snapshot():
    from scipy.ndimage import binary_dilation
    z = np.load(REPO / "forecast/demonstration/heat_spatial_maps/20261013_fishcreek/spatial_matrices.npz")
    q = z["new_burn_probability"].astype(float)
    v = z["new_burn_probability_valid"]
    b = z["current_burned_state"] == 1
    lam = -np.log1p(-np.clip(q, 0, 1 - 1e-12))
    ring1 = binary_dilation(b) & ~b & v
    ring24 = binary_dilation(b, iterations=4) & ~binary_dilation(b) & v
    return {name: dict(cells=int(m.sum()), rate_q50_q90_q99_max=[float(x) for x in np.quantile(lam[m], [0.5, 0.9, 0.99, 1])])
            for name, m in (("adjacent_ring1", ring1), ("ring2_to_4", ring24))}


@torch.inference_mode()
def proxy():
    tm = load_trained_model(CKPT)
    model = tm.model if hasattr(tm, "model") else tm.module
    mean = tm.normalization_mean if hasattr(tm, "normalization_mean") else tm.mean
    std = tm.normalization_std if hasattr(tm, "normalization_std") else tm.std
    model.eval()
    k = model.kernel_size
    r = k // 2
    offs = np.array([(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1)])
    rows = []
    temps, speeds, dirs, slopes, trees = [5, 20, 35], [0, 5, 10, 15], [0, np.pi / 2], [0, 15, 35], [0, 50, 100]
    for T, S, D, SL, TC, biome in itertools.product(temps, speeds, dirs, slopes, trees, range(1, 15)):
        raw = np.zeros(19)
        raw[:5] = [T, S * np.cos(D), S * np.sin(D), SL, TC]
        raw[4 + biome] = 1.0
        x = ((torch.tensor(raw, dtype=mean.dtype) - mean.reshape(-1)) / std.reshape(-1)).reshape(19)
        patch = x[None, :, None, None].expand(1, 19, k, k).contiguous()
        K = model._kernels(patch)[0, :, r, r].double().numpy()
        # Source s = target + offset; spread direction source->target is -offset. Sources upwind of the
        # target are those with offset pointing against the wind: offset . wind_dir < 0.
        # Wind blows towards (u, v) = (east, north); on a north-up grid rows increase southwards,
        # so the downwind direction in (dy, dx) is (-sin D, cos D).
        wdir = np.array([-np.sin(D), np.cos(D)])
        upwind = (offs @ wdir) < 0
        rows.append(dict(temperature=T, wind_speed=S, wind_dir=float(D), slope=SL, tree_cover=TC, biome=biome,
                         total=float(K.sum()), upwind_half=float(K[upwind].sum()), max_single=float(K.max())))
    tot = np.array([x["total"] for x in rows])
    half = np.array([x["upwind_half"] for x in rows])
    top = sorted(rows, key=lambda x: -x["total"])[:5]
    return dict(n_patches=len(rows),
                total_q50_q90_q99_max=[float(x) for x in np.quantile(tot, [0.5, 0.9, 0.99, 1])],
                upwind_half_q50_q90_q99_max=[float(x) for x in np.quantile(half, [0.5, 0.9, 0.99, 1])],
                share_total_above_0p043=float((tot > 0.043).mean()), share_total_above_1=float((tot > 1).mean()),
                top5=top)


def main():
    out = dict(real_fishcreek_snapshot=real_snapshot(), proxy_uniform_patches=proxy(),
               toy_regimes_coefficient_sum_per_h=dict(slow=0.043, fast=1.0))
    print(json.dumps({k: (v if k != "proxy_uniform_patches" else {kk: vv for kk, vv in v.items() if kk != "top5"})
                      for k, v in out.items()}, indent=1))
    Path(__file__).with_name("RESULTS_c651_rates.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
