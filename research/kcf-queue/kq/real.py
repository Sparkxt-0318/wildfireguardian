"""Real-data side of KQ-1: closure fields (kcf-replay MEASURED 8 h), the road graph of wfg-roadlayer, capacities,
demand. Reads only; no input file is changed."""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "product/wfg-roadlayer"))
sys.path.insert(0, str(ROOT / "research/kcf-replay"))
from wfg_roadlayer import cards, regiondata  # noqa: E402
import measured_arms as MA  # noqa: E402

from .solver import BIG, Ctx, Net  # noqa: E402

H, DWELL = 28800, 120
REGIONS = ["uiseong_andong_2025", "yeongdeok_2025"]
HOURS_UTC = list(range(3, 16))
_DISCS = None


def discs():
    global _DISCS
    if _DISCS is None:
        d = json.loads((ROOT / "research/kcf-replay/fire_discs.json").read_text())["discs"]
        _DISCS = [dict(x, t=datetime.fromisoformat(x["t_utc"])) for x in d]
    return _DISCS


class Reg:
    """One region: graph arrays that do not depend on the issue hour."""

    def __init__(self, rid):
        self.rid = rid
        self.region = regiondata.Region(rid, regiondata.default_cache())
        self.region.candidates(3)
        rd = self.road = self.region.road
        self.E, self.n = len(rd.tail), len(rd.node_ids)
        # per edge: segments as (cell, floor(D*z_end)); closure start of the edge = min over closed cells of b - floor(D*z)
        self.segfl = [[(c, (rd.D[j] * z.numerator) // z.denominator) for c, z in segs] for j, segs in enumerate(rd.seg)]
        self.cells_of_edge = [[c for c, _ in s] for s in self.segfl]
        W, res = rd.W, float(rd.res)
        x0, y0 = float(rd.x0), float(rd.y0)
        idx = np.arange(W * rd.H)
        self.cx = x0 + (idx % W + 0.5) * res
        self.cy = y0 + (idx // W + 0.5) * res
        _, self.ways = cards.load_edge_data(rid)
        self.hh = cards.load_households(rid)
        self.cls = [(self.ways.get(rd.source_way[j]) or {}).get("class") or "unmatched" for j in range(self.E)]
        self.sources = rd.source_way

    def closure(self, T):
        """{cell: closure second} as replay.run_one for the MEASURED arm, 8 h; and the distance array."""
        D = discs()
        sel = [x for x in D if x["t"] < T]
        d = np.full(self.cx.shape, np.inf)
        if sel:
            X = np.array([x["x"] for x in sel]); Y = np.array([x["y"] for x in sel]); R = np.array([x["r_m"] for x in sel])
            for i in range(0, len(sel), 2000):
                dd = np.sqrt((self.cx[:, None] - X[None, i:i + 2000]) ** 2 + (self.cy[:, None] - Y[None, i:i + 2000]) ** 2) - R[None, i:i + 2000]
                d = np.minimum(d, np.maximum(dd, 0).min(1))
        r5, r8, cls_, _ = MA.curve("MEASURED", D, T, 8)
        close = {}
        for c in np.nonzero(np.isfinite(d))[0]:
            s = MA.closure_s(r5, r8, float(d[c]))
            if s <= H:
                close[int(c)] = int(math.ceil(s))
        return close, d

    def net(self, close, cap_vph, rho, bin_s=60):
        """Net for one closure field and capacity table; `cap_vph` maps class -> veh/h."""
        rd = self.road
        lo = [BIG] * self.E
        for j in range(self.E):
            best = BIG
            for c, fl in self.segfl[j]:
                b = close.get(c)
                if b is not None:
                    v = max(b - fl, 0)
                    if v < best:
                        best = v
            if best <= H:
                lo[j] = best
        wcut = [close.get(c, BIG) for c in rd.node_cell]
        ncap = [max(1, (round(rho * 100) * cap_vph[self.cls[j]]) // 6000) for j in range(self.E)]
        return Net(self.n, rd.tail, rd.head, rd.D, lo, ncap, bin_s, rd.forbidden, wcut)

    def amax(self, close, node):
        b = close.get(self.road.node_cell[node])
        a = H - DWELL
        if b is not None:
            a = min(a, max(b - DWELL, 0) - 1)
        return a

    def village_ctx_args(self, close):
        """[(origin record, origin node, {shelter node: amax})] for every checkable origin with candidates."""
        out = []
        for o in self.region.origins:
            cands = self.region.cands.get(o["id"], [])
            if o["node"] is None or not o["checkable"] or not cands:
                continue
            sh = {s["node"]: self.amax(close, s["node"]) for s in cands}
            out.append((o, o["node"], sh))
        return out


def cap_table(p_other=800, base=None):
    """class -> veh/h from cards.toml classes (PROTOCOL 2, 4)."""
    t = cards.load_settings(None)["traffic"] if base is None else base
    out = {}
    for cls in set(cards.CLASS_CAP) | {"unclassified", "residential", "service", "track", "living_street", "unmatched", "path"}:
        key = cards.CLASS_CAP.get(cls)
        out[cls] = t[key] if key else p_other
    return out


def cap_for(cls_name, table, p_other):
    return table.get(cls_name, p_other)
