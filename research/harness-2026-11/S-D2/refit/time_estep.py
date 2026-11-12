"""Time the d2_bracket E-step and M-step pieces against one mean-field training step (Iris's request).

Uses the real ``StructuredKernelModel`` (d4_wind settings: kernel 9, hidden 16, wind frame) on synthetic tensors of
realistic size. No data is read. Measured per window (one survey interval of ``--hours``):

* ``train_step``: the current pipeline's cost per interval: ``sample_forecast`` (mean field over hourly steps) plus
  the endpoint loss and backward;
* ``kernels``: one ``kernel_rates`` pass (no grad). The kernels depend on the environment only, so one pass serves
  every Gibbs sweep of the window;
* ``gibbs_sweep``: one full Gibbs sweep over the bracket cells of the window, with spatially varying kernels
  (``--new-cells`` latent arrivals, 80 offsets);
* ``mstep``: the complete-data log-likelihood through ``kernel_rates`` with backward.

    python time_estep.py --grid 120 --hours 24 --new-cells 800
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
import torch

from wildfire.models import StructuredKernelModel
from wildfire.survival import PerimeterSample, endpoint_brier, sample_forecast, sample_tensors

NAMES = None


def channel_names(n):
    base = ["weather.wind_eastward_10m", "weather.wind_northward_10m"] + [f"x{i}" for i in range(n - 2)]
    return base


def make_sample(H, W, hours, rng, channels):
    env = rng.normal(size=(channels, H, W)).astype(np.float32)
    initial = np.zeros((H, W), bool)
    initial[H // 2 - 8:H // 2 + 8, W // 2 - 8:W // 2 + 8] = True
    endpoint = initial.copy()
    endpoint[H // 2 - 20:H // 2 + 20, W // 2 - 20:W // 2 + 20] = True
    return PerimeterSample("SYN", "2020-01-01T00:00:00+00:00", float(hours), env, initial, endpoint, ~initial,
                           np.ones((H, W), np.float32), np.zeros((H, W), np.float32))


def gibbs_sweep(K, tau, cells, offs, lo, hi, step, rng):
    """One sweep over latent cells with spatially varying kernels K[d, i] (vectorised over candidate times)."""
    H, W = tau.shape
    flat_tau = tau.ravel()
    D = len(offs)
    for i in cells:
        r, c = divmod(int(i), W)
        x = np.arange(lo[i] + step / 2, hi[i], step)
        sr, sc = r - offs[:, 0], c - offs[:, 1]
        ok = (sr >= 0) & (sr < H) & (sc >= 0) & (sc < W)
        ts = flat_tau[sr[ok] * W + sc[ok]]
        kk = K[ok, i]
        lam = 1e-6 + (ts[None, :] < x[:, None]) @ kk
        Lam = np.clip(x[:, None] - ts[None, :], 0, None) @ kk
        logf = np.log(lam) - Lam
        tr, tc = r + offs[:, 0], c + offs[:, 1]
        okt = (tr >= 0) & (tr < H) & (tc >= 0) & (tc < W)
        for d in np.flatnonzero(okt):
            m = tr[d] * W + tc[d]
            tm = flat_tau[m]
            kd = K[d, m]
            if np.isfinite(tm):
                logf += np.log(1e-6 + kd * (x < tm)) - kd * np.clip(tm - x, 0, None)
            else:
                logf -= kd * np.clip(hi[i] - x, 0, None)
        logf -= logf.max()
        p = np.exp(logf)
        p /= p.sum()
        flat_tau[i] = x[rng.choice(len(x), p=p)]
    return flat_tau.reshape(H, W)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", type=int, default=120)
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--new-cells", type=int, default=800)
    ap.add_argument("--channels", type=int, default=19)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--step", type=float, default=0.25)
    a = ap.parse_args(argv)
    torch.set_num_threads(a.threads)
    rng = np.random.default_rng(0)
    names = channel_names(a.channels)
    model = StructuredKernelModel(a.channels, 9, 16, 0.0, channel_names=names,
                                  mean=torch.zeros(a.channels), std=torch.ones(a.channels),
                                  prior="free", frame="wind")
    model.initialize_rate(0.01)
    s = make_sample(a.grid, a.grid, a.hours, rng, a.channels)
    t = sample_tensors(s)
    out = {}
    # Current training step.
    t0 = time.perf_counter()
    p, valid = sample_forecast(model, s, tensors=t)
    loss, w = endpoint_brier(p, t["endpoint"], t["weight"], t["mask"] & valid)
    (loss / w).backward()
    out["train_step_s"] = time.perf_counter() - t0
    model.zero_grad()
    # Kernels (no grad).
    t0 = time.perf_counter()
    with torch.no_grad():
        K = model.kernel_rates(t["environment"], boundary="zero")[0].numpy()     # [D, H, W]
    out["kernels_s"] = time.perf_counter() - t0
    D = K.shape[0]
    k = int(round(D ** 0.5))
    rr = np.arange(k) - k // 2
    offs = np.stack(np.meshgrid(rr, rr, indexing="ij"), -1).reshape(-1, 2)
    Kf = np.nan_to_num(K.reshape(D, -1))
    # Latent cells: a ring of new cells inside the endpoint, bracket (0, hours].
    H = W = a.grid
    tau = np.where(s.initial, 0.0, np.inf)
    cand = np.flatnonzero((s.endpoint & ~s.initial).ravel())
    cells = rng.choice(cand, size=min(a.new_cells, len(cand)), replace=False)
    lo = np.zeros(H * W)
    hi = np.full(H * W, a.hours)
    tau_flat = tau.ravel()
    tau_flat[cells] = rng.uniform(0, a.hours, len(cells))
    t0 = time.perf_counter()
    gibbs_sweep(Kf, tau_flat.reshape(H, W), cells, offs, lo, hi, a.step, rng)
    out["gibbs_sweep_s"] = time.perf_counter() - t0
    # M-step: complete-data log-likelihood through kernel_rates (one pass with backward).
    t0 = time.perf_counter()
    Kt = model.kernel_rates(t["environment"], boundary="zero")[0].nan_to_num(0.0).reshape(D, -1)
    idx = torch.as_tensor(cells)
    lam = Kt[:, idx].sum(0) * 0.5 + 1e-6                     # placeholder active-source mask (cost-equivalent)
    expo = (Kt * 1.0).sum()
    ll = torch.log(lam).sum() - expo
    (-ll).backward()
    out["mstep_s"] = time.perf_counter() - t0
    out.update(grid=a.grid, hours=a.hours, new_cells=int(len(cells)), offsets=int(D), threads=a.threads,
               torch=torch.__version__)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
