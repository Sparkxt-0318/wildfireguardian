"""Twin experiment library (PROTOCOL.md section 5): a simulator is the truth; the system sees only satellite-like detections.

Truth: minimum-travel-time (Dijkstra / eikonal-type) spread on the 375 m KFS_01 lattice used by product/wfg-roadlayer, with a
wind-driven elliptical speed law (Richards), diurnal speed, correlated spatial speed field, one wind shift, and random
spotting edges. It is NOT FARSITE and shares no code or parameter with research/kcf-margin or research/kcf-replay.

Detections: generated from the truth only, with the real overpass schedule shape of research/kcf-replay/fire_discs.json
(sensor families, time-of-day clusters, disc radii of HOTSPOT_RULE.md), detection probabilities and cloud blocking set in
PROTOCOL.md section 5 (ASSUMED values, fixed before any system output).
"""
from __future__ import annotations

import heapq
import math
from datetime import datetime, timedelta, timezone

import numpy as np
from scipy.ndimage import gaussian_filter

X0, Y0, RES, W, H = 1093875.0, 1815750.0, 375.0, 214, 67
HOUR = 3600.0
# 16-neighbour stencil (8 neighbours + 8 knight moves) to reduce lattice anisotropy
STENCIL = [(dr, dc) for dr in range(-2, 3) for dc in range(-2, 3)
           if (dr, dc) != (0, 0) and math.gcd(abs(dr), abs(dc)) == 1]

PARAMS = dict(
    v0_median_kmh=2.0, v0_sigma=0.5,          # per-seed head-fire speed at g(t)=1, lognormal
    field_sigma=0.35, field_corr_cells=4.0,    # spatial speed multiplier, lognormal, Gaussian-correlated
    lb=2.5,                                    # length-to-breadth ratio of the spread ellipse
    wind_dir_deg=(-20.0, 20.0),                # wind blows toward east +-20 deg (deg counter-clockwise from +x)
    wind_shift_deg=40.0, wind_shift_hours=(6.0, 18.0),
    spot_prob=0.02, spot_dist_km=(1.0, 3.0), spot_cone_deg=20.0, spot_delay_h=(0.25, 1.0),
    flaming_h=2.0,                             # a cell counts as burning (detectable) for this long after arrival
)


def cell_xy():
    cx = X0 + (np.arange(W) + 0.5) * RES
    cy = Y0 + (np.arange(H) + 0.5) * RES
    return np.meshgrid(cx, cy)  # arrays [H, W]


def diurnal(t_utc: datetime):
    h = (t_utc + timedelta(hours=9)).hour + (t_utc + timedelta(hours=9)).minute / 60.0
    return 0.35 + 0.65 * max(0.0, math.sin(math.pi * (h - 9.0) / 12.0)) if 9.0 <= h <= 21.0 else 0.35


def simulate(seed: int, t_ign: datetime, P=PARAMS):
    """Return dict: arrival [H,W] seconds after t_ign (inf = never within 96 h), plus the drawn parameters."""
    rng = np.random.default_rng([seed, 20261118])
    v0 = P["v0_median_kmh"] * math.exp(P["v0_sigma"] * rng.standard_normal()) * 1000.0 / HOUR  # m/s
    z = gaussian_filter(rng.standard_normal((H, W)), P["field_corr_cells"])
    z = (z - z.mean()) / z.std()
    f = np.exp(P["field_sigma"] * z)            # lognormal spatial speed multiplier, correlated over ~field_corr_cells
    th0 = math.radians(rng.uniform(*P["wind_dir_deg"]))  # direction of spread, deg counter-clockwise from +x (east)
    shift = math.radians(P["wind_shift_deg"] * rng.choice([-1.0, 1.0]))
    t_shift = rng.uniform(*P["wind_shift_hours"]) * HOUR
    ign_c = int(rng.integers(int((1115000 - X0) / RES), int((1135000 - X0) / RES)))
    ign_r = int(rng.integers(int((1822000 - Y0) / RES), int((1834000 - Y0) / RES)))
    e = math.sqrt(1.0 - 1.0 / P["lb"] ** 2)
    n = H * W
    spot_flag = rng.random(n) < P["spot_prob"]
    spot_d = rng.uniform(*P["spot_dist_km"], n) * 1000.0
    spot_a = np.radians(rng.uniform(-P["spot_cone_deg"], P["spot_cone_deg"], n))
    spot_t = rng.uniform(*P["spot_delay_h"], n) * HOUR
    ft = f.ravel()
    arr = np.full(n, np.inf)
    s = ign_r * W + ign_c
    arr[s] = 0.0
    heap = [(0.0, s)]
    ang = {k: math.atan2(k[0], k[1]) for k in STENCIL}
    dist = {k: RES * math.hypot(*k) for k in STENCIL}
    while heap:
        t, u = heapq.heappop(heap)
        if t > arr[u]:
            continue
        if t > 96 * HOUR:
            break
        r, c = divmod(u, W)
        tu = t_ign + timedelta(seconds=t)
        g = diurnal(tu)
        th = th0 + (shift if t >= t_shift else 0.0)
        vhead = v0 * g * ft[u]
        for k in STENCIL:
            r2, c2 = r + k[0], c + k[1]
            if not (0 <= r2 < H and 0 <= c2 < W):
                continue
            phi = ang[k] - th
            v = vhead * (1 - e) / (1 - e * math.cos(phi))
            v = max(v, 0.02 * v0)
            t2 = t + dist[k] / v
            v_ = r2 * W + c2
            if t2 < arr[v_]:
                arr[v_] = t2
                heapq.heappush(heap, (t2, v_))
        if spot_flag[u]:
            a = th + spot_a[u]
            c2 = c + int(round(spot_d[u] * math.cos(a) / RES))
            r2 = r + int(round(spot_d[u] * math.sin(a) / RES))
            if 0 <= r2 < H and 0 <= c2 < W:
                t2 = t + spot_t[u]
                v_ = r2 * W + c2
                if t2 < arr[v_]:
                    arr[v_] = t2
                    heapq.heappush(heap, (t2, v_))
    return {"arrival_s": arr.reshape(H, W), "v0_kmh": v0 * HOUR / 1000.0, "wind_deg": math.degrees(th0),
            "shift_deg": math.degrees(shift), "t_shift_h": t_shift / HOUR, "ignition_cell": (ign_r, ign_c)}
