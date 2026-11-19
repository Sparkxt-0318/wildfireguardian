"""Toy fire simulator for PRETRAIN-sim (PROTOCOL 5.2 item 5b). Parameters are FIXED a priori (not tuned to any DEV fire).

Time-stepped elliptical-kernel spread on a 375 m grid: hourly head rate of spread from wind speed and relative humidity
(ROS = R0 * exp(-0.04 (RH - 30)) * (1 + 0.35 U^1.3) km/h), length-to-breadth from Alexander (1985) as in kcf-adaptive, a
per-fire lognormal rate multiplier, a random burnable-fuel mask (about 80% burnable), a slowly drifting wind direction and
occasional spot fires (more likely in high gust). Weather: AR(1) log wind with a diurnal cycle and rare multi-day wind events;
RH with a diurnal cycle. Issued-forecast features = true weather maxima over the next 8 h times lognormal noise (sd 0.2).
Features and the reach outcome come from the SAME code as the real fires (build_data.process).

    python sim_fires.py --n 400 --out /tmp/w/work/sim.csv.gz
"""
import os
import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_data as bd  # noqa: E402
from reach import NEVER  # noqa: E402

N = 224
HOURS = 200
CELL = 0.375


def kernel(rhead_cells, lb, ang):
    r = int(np.ceil(rhead_cells)) + 1
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    th = np.arctan2(yy, xx) - ang
    d = np.hypot(yy, xx)
    e = np.sqrt(max(1 - 1 / lb ** 2, 0.0))
    reach = rhead_cells * (1 - e) / (1 - e * np.cos(th))
    return d <= reach


def simulate_one(args):
    seed = args
    rng = np.random.default_rng(seed)
    # fuel mask: smoothed noise thresholded to ~80% burnable
    f = ndimage.gaussian_filter(rng.normal(size=(N, N)), 2.0)
    burnable = f > np.quantile(f, 0.20)
    # weather
    t0 = rng.integers(0, 24)
    h = np.arange(HOURS + 8)
    loc = (t0 + h) % 24
    u0 = rng.lognormal(np.log(1.8), 0.4)
    z = np.zeros(len(h)); z[0] = rng.normal(0, 0.3)
    for i in range(1, len(h)):
        z[i] = 0.95 * z[i - 1] + rng.normal(0, 0.15)
    U = u0 * np.exp(z) * (1 + 0.4 * np.sin(2 * np.pi * (loc - 9) / 24))
    if rng.random() < 0.3:
        s = rng.integers(10, HOURS - 30); L = rng.integers(12, 48)
        U[s:s + L] *= rng.uniform(2.0, 3.5)
    U = np.clip(U, 0.5, 35)
    rh0 = rng.uniform(20, 50)
    RH = np.clip(rh0 + 15 * np.sin(2 * np.pi * (loc - 3) / 24) + rng.normal(0, 3, len(h)), 3, 95)
    gust = U * rng.lognormal(0.45, 0.08) * (1 + 0.1 * rng.normal(size=len(h)).clip(-2, 2))
    w850 = 1.15 * U * np.exp(0.8 * z[::-1] * 0 + rng.normal(0, 0.15, len(h)))
    hdw = 2.5 * (1 - RH / 100) * gust * 5
    # fire
    mult = rng.lognormal(0, 0.6)
    ang = rng.uniform(0, 2 * np.pi)
    A = np.full((N, N), NEVER, np.int32)
    A[N // 2, N // 2] = 0
    burned = np.zeros((N, N), bool); burned[N // 2, N // 2] = True
    front = burned.copy()
    for t in range(1, HOURS):
        ang += rng.normal(0, 0.15)
        ros = 0.07 * np.exp(-0.04 * (RH[t] - 30)) * (1 + 0.35 * U[t] ** 1.3) * mult        # km/h
        lb = min(1 + 8.729 * (1 - np.exp(-0.030 * U[t] * 3.6)) ** 2.155, 8)
        rc = ros / CELL
        step = np.zeros_like(burned)
        done = 0.0
        # sub-steps keep the hop below 6 cells
        nsub = max(1, int(np.ceil(rc / 6)))
        cur = front
        new_all = np.zeros_like(burned)
        for _ in range(nsub):
            k = kernel(rc / nsub, lb, ang)
            grown = ndimage.binary_dilation(cur, structure=k) & burnable & ~burned & ~new_all
            keep = rng.random(grown.shape) < 0.9
            grown &= keep
            new_all |= grown
            cur = grown | cur
        # spotting
        if rng.random() < min(0.02 * (gust[t] / 10) ** 2, 0.5) and burned.any():
            ys, xs = np.nonzero(front if front.any() else burned)
            j = rng.integers(len(ys))
            d = rng.exponential(1.5 * gust[t] / 10) / CELL
            yy = int(ys[j] + d * np.sin(ang)); xx = int(xs[j] + d * np.cos(ang))
            if 2 <= yy < N - 2 and 2 <= xx < N - 2 and burnable[yy, xx] and not burned[yy, xx]:
                new_all[yy, xx] = True
        if not new_all.any():
            # keep the fire alive in the quiet hours by letting the front persist
            front = burned & ndimage.binary_dilation(~burned)
            continue
        A[new_all] = t
        burned |= new_all
        front = ndimage.binary_dilation(new_all, iterations=1) & burned | (front & ndimage.binary_dilation(~burned))
        ys, xs = np.nonzero(new_all)
        if ys.min() < 6 or xs.min() < 6 or ys.max() > N - 7 or xs.max() > N - 7:
            T = t
            break
    else:
        T = HOURS - 1
    first = 0
    last = int(A[A != NEVER].max())
    if last - 5 < 10:
        return seed, pd.DataFrame()
    rows, _ = bd.process(A, first, last, lambda t: pd.Timestamp("2020-01-01") + pd.Timedelta(hours=int(t)), False)
    df = pd.DataFrame(rows)
    ti = df.t_idx.values
    nz = lambda a, sd: a * rng.lognormal(0, sd, len(df))
    mx = lambda a: np.array([a[t + 1:t + 9].max() for t in ti])
    mn = lambda a: np.array([a[t + 1:t + 9].min() for t in ti])
    df["gust_ms"] = nz(mx(gust), 0.2); df["w850_ms"] = nz(mx(w850), 0.2)
    df["rhmin_pct"] = np.clip(nz(mn(RH), 0.1), 3, 97); df["hdw"] = nz(mx(hdw), 0.25)
    sol = loc[ti] + 0.0
    df["sin_h"] = np.sin(2 * np.pi * sol / 24); df["cos_h"] = np.cos(2 * np.pi * sol / 24)
    df["log_area"] = np.log1p(df.area_known_km2); df["log_age"] = np.log1p(df.age_h)
    df["S"] = df["reach5_km"]
    df["fire"] = f"SIM{seed}"
    return seed, df[df.age_h >= 3].dropna(subset=["S"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--out", default=os.path.join(os.environ.get("KCF2_WORK", "/tmp/w/work"), "sim.csv.gz"))
    ap.add_argument("--procs", type=int, default=2)
    a = ap.parse_args()
    parts = []
    with ProcessPoolExecutor(a.procs) as ex:
        for seed, df in ex.map(simulate_one, [20261200 + i for i in range(a.n)], chunksize=4):
            if len(df):
                parts.append(df)
    d = pd.concat(parts, ignore_index=True)
    d.to_csv(a.out, index=False)
    print(len(parts), "fires", len(d), "hours")
    print(d[["S", "g3", "gust_ms", "w850_ms", "rhmin_pct", "hdw", "area_known_km2"]].describe(percentiles=[.5, .9, .99]).T.to_string())


if __name__ == "__main__":
    main()
