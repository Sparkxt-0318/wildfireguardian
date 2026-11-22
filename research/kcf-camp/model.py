"""Shared pieces (PROTOCOL §3-§5): times, projection, the road graph, the four closure variants, statistics."""
from __future__ import annotations

import csv, json, math, random, sys
from pathlib import Path

import numpy as np
from pyproj import Transformer

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "product/wfg-roadlayer"))
from wfg_roadlayer import regiondata  # noqa: E402

TO_UTM = Transformer.from_crs(4326, 32610, always_xy=True)
TO_LL = Transformer.from_crs(32610, 4326, always_xy=True)
VARIANTS = ("M0", "M30", "MR", "MR_running")
R_ALL = (3800.0, 5000.0)       # research/kcf-margin all hours, 10 %: R(5 h), R(8 h) in m
R_RUN = (7600.0, 10000.0)      # running class
HOLD_M, HOLD_MIN, TOL_MIN, MATCH_M = 500.0, 60.0, 15.0, 375.0


def minutes(day: str, hhmm: str) -> float:
    h, m = hhmm.split(":")
    return {"11-08": 0, "11-09": 1440}[day] + int(h) * 60 + int(m)


def hhmm(t: float) -> str:
    if not math.isfinite(t):
        return ""
    d, r = divmod(int(round(t)), 1440)
    return ("" if d == 0 else "11-%02d " % (8 + d)) + "%02d:%02d" % divmod(r, 60)


def closure_min(R5, R8, d_m):
    """research/kcf-replay/measured_arms.closure_s in minutes: (0,0)-(5 h,R5)-(8 h,R8) linear, beyond R8 never."""
    if d_m <= R5:
        return d_m / R5 * 300.0
    if d_m <= R8:
        return 300.0 + (d_m - R5) / (R8 - R5) * 180.0
    return math.inf


class Graph:
    def __init__(self, path):
        self.raw = json.load(open(path))
        self.road = regiondata.RoadModel(self.raw)
        g = self.raw["grid"]
        self.x0, self.y0, self.res, self.W, self.H = g["x0"], g["y0"], g["resolution"], g["width"], g["height"]
        self.road_cells = np.array(sorted(self.road.road_cells))
        self.rc_xy = np.array([self.centre(c) for c in self.road_cells])
        self.road_set = set(int(c) for c in self.road_cells)

    def cell(self, x, y):
        c, r = int((x - self.x0) // self.res), int((y - self.y0) // self.res)
        return r * self.W + c if (0 <= c < self.W and 0 <= r < self.H) else None

    def centre(self, c):
        r, cc = divmod(int(c), self.W)
        return (self.x0 + (cc + 0.5) * self.res, self.y0 + (r + 0.5) * self.res)

    def match(self, x, y):
        """PROTOCOL §5: own cell if a road cell, else nearest road cell centre within 375 m, else None."""
        c = self.cell(x, y)
        if c is not None and c in self.road_set:
            return c, "own_cell"
        d = np.hypot(self.rc_xy[:, 0] - x, self.rc_xy[:, 1] - y)
        k = int(np.argmin(d))
        return (int(self.road_cells[k]), "nearest_%dm" % round(d[k])) if d[k] <= MATCH_M else (None, "not_placed")


class Field:
    """Closure minutes of a cell under each variant, from a list of fire-arrival observations [(x, y, t)]."""

    def __init__(self, G: Graph, obs):
        first = {}
        for x, y, t in obs:
            c = G.cell(x, y)
            if c is not None and t < first.get(c, math.inf):
                first[c] = t
        self.G = G
        self.first = first
        self.cells = np.array(list(first.keys()), dtype=int)
        self.t = np.array([first[c] for c in self.cells], float)
        self.xy = np.array([G.centre(c) for c in self.cells]) if len(self.cells) else np.zeros((0, 2))

    def closure(self, c, variant):
        if variant in ("M0", "M30"):
            t0 = self.first.get(int(c), math.inf)
            return t0 - 30.0 if variant == "M30" else t0
        if not len(self.cells):
            return math.inf
        R5, R8 = R_ALL if variant == "MR" else R_RUN
        x, y = self.G.centre(c)
        d = np.hypot(self.xy[:, 0] - x, self.xy[:, 1] - y)
        ok = d <= R8
        if not ok.any():
            return math.inf
        return float(min(ti + closure_min(R5, R8, di) for ti, di in zip(self.t[ok], d[ok])))


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(max(0.0, c - h), 3), round(min(1.0, c + h), 3))


def boot_median(vals, B=2000, seed=0):
    v = [x for x in vals if math.isfinite(x)]
    if not v:
        return {"n": 0, "median": None, "ci95": None, "iqr": None}
    rnd = random.Random(seed)
    meds = sorted(float(np.median([v[rnd.randrange(len(v))] for _ in v])) for _ in range(B))
    return {"n": len(v), "median": round(float(np.median(v)), 1), "ci95": [round(meds[int(0.025 * B)], 1), round(meds[int(0.975 * B) - 1], 1)],
            "iqr": [round(float(np.percentile(v, 25)), 1), round(float(np.percentile(v, 75)), 1)]}


def verdict(rate_ci, thr, good_if_ge=True, n=0, nmin=10):
    lo, hi = rate_ci
    if n < nmin or lo is None:
        return "INCONCLUSIVE"
    if lo <= thr <= hi:
        return "INCONCLUSIVE"
    above = lo > thr
    return "PASS" if above == good_if_ge else "FAIL"


def read_csv(p):
    return list(csv.DictReader(open(p, encoding="utf-8")))


def write_csv(p, rows, cols=None):
    cols = cols or list(rows[0].keys())
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
