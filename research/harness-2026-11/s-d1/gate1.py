"""Gate 1: sub-stepped CA (dt = 1/2^k h) converges to the first-passage sampler.

Mapping (verified in RESULTS.md section 1): the pair rate is the kernel coefficient K (1/h);
the CA uses P(ignite in dt) = 1 - exp(-dt * sum K * B) exactly as wildfire.models.

Distance between arrival-map distributions, evaluated at every whole hour t = 1..T, which
is a step endpoint for every dt:
  * L1    = mean over cells and hours of |F_CA(i,t) - F_FPP(i,t)|, F = P(cell i burned by t)
  * Linf  = max over cells and hours of the same quantity
  * W1    = Wasserstein-1 distance between the burned-area (new-cell count) distributions at T,
            divided by the FPP mean burned area
The noise floor is the same distance between two independent first-passage runs.

    python research/harness-2026-11/s-d1/gate1.py [--n 2000] [--kmax 5] [--regimes ...]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fpp import cellular_automaton, first_passage, stencil_offsets  # noqa: E402

SIZE = 40


def uniform_kernel(total, k=5):
    K = np.full((k * k, SIZE, SIZE), total / (k * k - 1))
    K[(k * k) // 2] = 0
    return K[None]


def heterogeneous_kernel(seed, wind_dirs, k=9, mean_total=0.6, wind_strength=1.5):
    """Lognormal per-cell/offset noise x wind alignment x distance decay x fuel patches.

    One kernel per entry of ``wind_dirs`` (radians; direction the fire spreads towards).
    """
    rng = np.random.default_rng(seed)
    offs = stencil_offsets(k).astype(float)
    dist = np.hypot(offs[:, 0], offs[:, 1])
    centre = dist == 0
    # fuel map: smooth random field, values in about [0.1, 3]
    f = rng.normal(size=(SIZE // 8, SIZE // 8))
    fuel = np.exp(np.kron(f, np.ones((8, 8))))
    noise = np.exp(0.5 * rng.normal(size=(k * k, SIZE, SIZE)))
    out = []
    for wd in wind_dirs:
        # source = target + offset, so spread direction (source -> target) is -offset
        spread = -offs
        cosang = np.where(centre, 0, (spread[:, 1] * np.cos(wd) + spread[:, 0] * np.sin(wd))
                          / np.where(centre, 1, dist))
        base = np.where(centre, 0, np.exp(wind_strength * cosang) * np.exp(-dist / 1.5))
        K = base[:, None, None] * noise * fuel[None]
        K *= mean_total / K.sum(axis=0).mean()
        K[centre] = 0
        out.append(K)
    return np.stack(out)


def regimes():
    return {
        "R1_slow_uniform5": dict(K=uniform_kernel(0.043), T=12),
        "R2_fast_uniform5": dict(K=uniform_kernel(1.0), T=8),
        "R3_heterogeneous9_static_wind": dict(K=heterogeneous_kernel(11, [0.0]), T=8),
        "R4_heterogeneous9_rotating_wind": dict(
            K=heterogeneous_kernel(12, [j * np.pi / 4 for j in range(8)]), T=8),
        # Scaled so that the rate of cells adjacent to the 3x3 ignition has median ~0.011/h,
        # the median adjacent-cell rate -log(1-q) of the c651 Fish Creek demo snapshot
        # (forecast/demonstration/heat_spatial_maps/20261013_fishcreek; max there 0.024/h).
        "R5_c651_magnitude_heterogeneous9": dict(K=heterogeneous_kernel(13, [0.0], mean_total=0.25), T=12),
    }


def distances(Fa, Fb, area_a, area_b, ref_mean):
    d = np.abs(Fa - Fb)
    qs = np.linspace(0, 1, 2001)[1:-1]
    w1 = np.abs(np.quantile(area_a, qs) - np.quantile(area_b, qs)).mean()
    return dict(L1=float(d.mean()), Linf=float(d.max()), W1_rel=float(w1 / max(ref_mean, 1e-9)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--kmax", type=int, default=5)
    ap.add_argument("--regimes", nargs="*", default=None)
    ap.add_argument("--out", default=str(Path(__file__).with_name("RESULTS_gate1.json")))
    args = ap.parse_args()
    init = np.zeros((SIZE, SIZE), bool)
    init[19:22, 19:22] = True
    first_passage(uniform_kernel(0.1)[:, :, :8, :8], init[16:24, 16:24], [1.0], n_samples=2, seed=0)
    allres = {}
    for name, spec in regimes().items():
        if args.regimes and name not in args.regimes:
            continue
        K, T = spec["K"], spec["T"]
        hours = np.arange(1, T + 1, dtype=float)
        res = dict(T=T, n=args.n, segments=int(K.shape[0]), kernel=int(np.sqrt(K.shape[1])),
                   mean_coefficient_sum=float(K.sum(axis=1).mean()), rows={})
        runs = {}
        for tag, seed in (("fpp_a", 1), ("fpp_b", 2)):
            t0 = time.perf_counter()
            c, arr = first_passage(K, init, hours, n_samples=args.n, seed=seed, keep_arrivals=args.n)
            sec = time.perf_counter() - t0
            area = ((arr <= T) & ~init).sum(axis=(1, 2))
            runs[tag] = (c / args.n, area, sec)
        ref_F, ref_area, _ = runs["fpp_a"]
        ref_mean = ref_area.mean()
        res["fpp_mean_area"] = float(ref_mean)
        res["fpp_seconds"] = runs["fpp_a"][2]
        res["noise_floor_fpp_vs_fpp"] = distances(runs["fpp_b"][0], ref_F, runs["fpp_b"][1], ref_area, ref_mean)
        print(f"== {name}: FPP mean area {ref_mean:.1f}, {runs['fpp_a'][2]:.2f}s; floor {res['noise_floor_fpp_vs_fpp']}", flush=True)
        for k in range(0, args.kmax + 1):
            m = 2 ** k
            t0 = time.perf_counter()
            c, tot = cellular_automaton(K, init, hours, dt=1 / m, n_samples=args.n, seed=100 + k,
                                        return_totals=True)
            sec = time.perf_counter() - t0
            dist = distances(c / args.n, ref_F, tot[-1], ref_area, ref_mean)
            res["rows"][f"dt=1/{m}"] = dict(**dist, mean_area=float(tot[-1].mean()), seconds=sec)
            print(f"   CA dt=1/{m:<3d} area {tot[-1].mean():8.1f}  L1 {dist['L1']:.4f}  Linf {dist['Linf']:.3f}"
                  f"  W1rel {dist['W1_rel']:.4f}  {sec:.1f}s", flush=True)
        allres[name] = res
        Path(args.out).write_text(json.dumps(allres, indent=1))


if __name__ == "__main__":
    main()
