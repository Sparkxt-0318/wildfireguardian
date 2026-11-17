"""KCF hour-by-hour replay, 2025-03-25 03:00-15:00 UTC (12:00-24:00 KST). Rule: HOTSPOT_RULE.md @ 796e91c.

For every planner place (174 checkable villages and care facilities, 영덕 + 의성·안동), every issue hour T, every R(h)
stand-in and horizon H in {5 h, 8 h}:
  * government step (LEAVE_NOW / PREPARE_VULNERABLE_FIRST / none) from the distance of the place's entry cell to the
    known fire area at T;
  * latest safe departure from the F-3.1 deadline field (deadline_field.core.backward, one pass per shelter) with
    permanent road-cell closures at T + R^-1(distance);
  * the shelter attaining it and a witness road (deadline_field.core.witness_greedy).

Usage: python3 replay.py fire_discs.json OUT_DIR [--regions ...] [--standins ...] [--workers N]
"""
from __future__ import annotations

import argparse, json, math, sys, time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta, timezone
from fractions import Fraction as F
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research/harness-2026-11/F-3.1"))
sys.path.insert(0, str(ROOT))
from deadline_field import core, intervals as iv  # noqa: E402
from tools.explain_deadlines.roads import RoadGraph  # noqa: E402
from tools.explain_deadlines.geometry import ceil_q, exact  # noqa: E402
import measured_arms as MA  # noqa: E402

ISSUES = [datetime(2025, 3, 25, h, 0, tzinfo=timezone.utc) for h in range(3, 16)]
STANDINS = {  # R(h) in metres; frozen in HOTSPOT_RULE.md
    "ORDINARY": (0.0, 341.0),
    "RUNNING": (0.0, 8200.0),
    "WORST": (3000.0, 8200.0),
}
HORIZONS = {"5h": 5 * 3600, "8h": 8 * 3600}
DWELL = 120
K = 3


def reach_m(standin, hours):
    a, v = STANDINS[standin]
    return a + v * hours


def closure_s(standin, d_m):
    """Seconds after issue at which a cell at distance d_m from the known fire area closes."""
    a, v = STANDINS[standin]
    return max(0.0, d_m - a) / v * 3600.0


def haversine_m(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


def planner_candidates(features):
    """planner/scripts/precompute.py::dispatch_requests: K nearest shelters (straight line) with distinct entry nodes."""
    shelters = [f for f in features if f["properties"]["role"] == "destination" and f["properties"]["checkable"]]
    origins = [f for f in features if f["properties"]["role"] == "origin" and f["properties"]["checkable"]]
    out = {}
    for o in origins:
        oc = o["geometry"]["coordinates"]
        cand = [s for s in shelters if s["properties"]["entry"]["node"] != o["properties"]["entry"]["node"]]
        near, seen = [], set()
        for s in sorted(cand, key=lambda s: (haversine_m(oc, s["geometry"]["coordinates"]), s["properties"]["id"])):
            n = s["properties"]["entry"]["node"]
            if n in seen:
                continue
            seen.add(n); near.append(s)
            if len(near) >= K:
                break
        out[o["properties"]["id"]] = (o, near)
    return out


class Region:
    def __init__(self, region):
        self.region = region
        raw = json.loads((ROOT / f"data/routing/graphs/{region}/graph.json").read_text())
        self.g = RoadGraph(raw)
        self.grid = self.g.grid
        self.node_ids = list(self.g.node_xy)
        self.nidx = {n: i for i, n in enumerate(self.node_ids)}
        # router segments per edge: (cell, z_end) -- the edge occupies cell c over [t + D*z_a, t + D*z_b]
        self.seg = []
        for e in raw["edges"]:
            self.seg.append([(int(s["cell"]), F(s["end"]).limit_denominator(10 ** 9) if not isinstance(s["end"], int) else F(s["end"]))
                             for s in e["segments"]])
        self.node_cell = [self.grid.cell_of(*self.g.xy(n)) for n in self.node_ids]
        g = self.grid
        cx = np.array([float(g.centre(c)[0]) for c in range(g.W * g.H)])
        cy = np.array([float(g.centre(c)[1]) for c in range(g.W * g.H)])
        self.cxy = (cx, cy)
        feats = json.loads((ROOT / f"planner/public/data/regions/{region}/places.geojson").read_text())["features"]
        self.cands = planner_candidates(feats)
        self.base = core.Instance(H=8 * 3600, n_nodes=len(self.node_ids), tail=[self.nidx[u] for u in self.g.u],
                                  head=[self.nidx[v] for v in self.g.v], D=list(self.g.ticks),
                                  waitable=[self.g.waitable[n] for n in self.node_ids], forbidden=set(self.g.forbidden))
        self.inc_by_node = {}
        for j, v in enumerate(self.base.head):
            self.inc_by_node.setdefault(v, []).append(j)

    def cell_distance(self, discs, T):
        cx, cy = self.cxy
        d = np.full(cx.shape, np.inf)
        sel = [x for x in discs if x["t"] < T]
        if not sel:
            return d
        X = np.array([x["x"] for x in sel]); Y = np.array([x["y"] for x in sel]); Rr = np.array([x["r_m"] for x in sel])
        for i in range(0, len(sel), 2000):
            dd = np.sqrt((cx[:, None] - X[None, i:i + 2000]) ** 2 + (cy[:, None] - Y[None, i:i + 2000]) ** 2) - Rr[None, i:i + 2000]
            d = np.minimum(d, np.maximum(dd, 0).min(1))
        return d

    def instance(self, close_s, H):
        """F-3.1 Instance with cell closures {cell: integer second}: phase [b, beyond H) under the router rule."""
        inst = self.base
        B = []
        for j, segs in enumerate(self.seg):
            Dq = F(inst.D[j]); lo = None
            for c, zb in segs:
                b = close_s.get(c)
                if b is None:
                    continue
                s = max(ceil_q(F(b) - Dq * zb), 0)
                lo = s if lo is None else min(lo, s)
            B.append([(lo, H)] if lo is not None and lo <= H else [])
        W = []
        for v, c in enumerate(self.node_cell):
            b = close_s.get(c)
            W.append([(max(b - 1, 0), H)] if (inst.waitable[v] and b is not None and b - 1 <= H) else [])
        return core.Instance(H=H, n_nodes=inst.n_nodes, tail=inst.tail, head=inst.head, D=inst.D, waitable=inst.waitable,
                             forbidden=inst.forbidden, B=B, W=W)

    def accept(self, close_s, node, H):
        b = close_s.get(self.node_cell[node])
        acc = (0, H - DWELL)
        if b is not None:
            acc = iv.subtract(acc, [(max(b - DWELL, 0), H)])
            return acc
        return [acc]


def run_one(args):
    region, standin, hz, T_iso, discs_path = args
    t0 = time.time()
    R = REG[region]
    H = HORIZONS[hz]
    T = datetime.fromisoformat(T_iso)
    discs = DISCS
    dist = R.cell_distance(discs, T)
    close_s = {}
    arm = None
    if standin in MA.ARMS:  # MEASURED_RULE.md: class fixed per (T, H); one curve for all places
        r5, r8, cls_, info = MA.curve(standin, discs, T, H // 3600)
        arm = (r5, r8)
    for c in range(len(dist)):
        if np.isfinite(dist[c]):
            s = MA.closure_s(r5, r8, float(dist[c])) if arm else closure_s(standin, float(dist[c]))
            if s <= H:
                close_s[c] = int(math.ceil(s))
    inst = R.instance(close_s, H)
    # shelters used by any origin
    shelters = {}
    for oid, (o, near) in R.cands.items():
        for s in near:
            shelters.setdefault(s["properties"]["entry"]["node"], []).append(oid)
    E = len(inst.tail)
    best = {}
    sets = {}
    for snode, oids in shelters.items():
        sn = R.nidx[snode]
        acc = R.accept(close_s, sn, H)
        inst.A = [[] for _ in range(E)]
        for j in R.inc_by_node.get(sn, []):
            inst.A[j] = list(acc)
        inst.AN = {}
        for oid in set(oids):
            o = R.cands[oid][0]
            on = R.nidx[o["properties"]["entry"]["node"]]
            b = close_s.get(R.node_cell[on])
            inst.IB = {on: [(b, H)] if b is not None else []}
        fld = core.backward(inst)
        for oid in set(oids):
            o, near = R.cands[oid]
            on = R.nidx[o["properties"]["entry"]["node"]]
            b = close_s.get(R.node_cell[on])
            inst.IB = {on: [(b, H)] if b is not None else []}
            S = core.issue_set(fld, on)
            sets.setdefault(oid, {})[snode] = [list(p) for p in S]
            if not S:
                continue
            ld = S[-1][1]
            contiguous = S[0][1] if S[0][0] == 0 else None
            prev = best.get(oid)
            if prev is None or ld > prev["ld_s"]:
                wit = core.witness_greedy(fld, on, ld)
                edges = [leg[1] for leg in wit[1] if leg[0] == "EDGE"] if wit else []
                shelter = next(s for s in near if s["properties"]["entry"]["node"] == snode)
                best[oid] = {"ld_s": ld, "contiguous_end_s": contiguous, "pieces": len(S), "shelter_id": shelter["properties"]["id"],
                             "shelter_name": shelter["properties"].get("name"), "arrival_s": wit[0] if wit else None,
                             "route_edges": edges}
    rows = []
    for oid, (o, near) in R.cands.items():
        on = R.nidx[o["properties"]["entry"]["node"]]
        d = float(dist[R.node_cell[on]])
        q5, q8 = arm if arm else (reach_m(standin, 5), reach_m(standin, 8))
        step = "LEAVE_NOW" if q5 >= d else ("PREPARE_VULNERABLE_FIRST" if q8 >= d else "NONE")
        b = best.get(oid)
        r = {"region": region, "place_id": oid, "standin": standin, "horizon": hz, "issue_utc": T_iso,
             "dist_known_fire_m": None if not np.isfinite(d) else round(d, 1), "step": step,
             "sets_by_shelter_node": sets.get(oid, {}),
             "fire_free_travel_s": None}
        if b:
            route_cells = sorted({c for j in b["route_edges"] for c, _ in R.seg[j]})
            free_ld = H - DWELL - (b["arrival_s"] - b["ld_s"]) if b["arrival_s"] is not None else None
            r.update({k: b[k] for k in ("ld_s", "contiguous_end_s", "pieces", "shelter_id", "shelter_name", "arrival_s")})
            # cut within H: some road cell on the attaining shelter's field closes inside H and binds; detected as LD
            # strictly below the fire-free cap for the witness travel time
            r["cut_within_H"] = bool(free_ld is not None and b["ld_s"] < free_ld)
            r["route_edges"] = [R.g.edge_ids[j] for j in b["route_edges"]]
            r["route_cells"] = route_cells
        else:
            r.update({"ld_s": None, "cut_within_H": None, "shelter_id": None})
        rows.append(r)
    return {"region": region, "standin": standin, "horizon": hz, "issue_utc": T_iso, "rows": rows,
            "closed_cells": len(close_s), "arm_class": (cls_, info) if arm else None, "wall_s": round(time.time() - t0, 1),
            "close_s": {str(k): v for k, v in close_s.items()}}


REG = {}
DISCS = []


def init(regions, discs_path):
    global DISCS
    for r in regions:
        REG[r] = Region(r)
    d = json.loads(Path(discs_path).read_text())["discs"]
    DISCS = [dict(x, t=datetime.fromisoformat(x["t_utc"])) for x in d]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("discs"); ap.add_argument("out")
    ap.add_argument("--regions", nargs="+", default=["yeongdeok_2025", "uiseong_andong_2025"])
    ap.add_argument("--standins", nargs="+", default=list(STANDINS) + list(MA.ARMS))
    ap.add_argument("--horizons", nargs="+", default=list(HORIZONS))
    ap.add_argument("--issues", nargs="+", type=int, default=list(range(3, 16)))
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    jobs = [(r, s, h, datetime(2025, 3, 25, i, tzinfo=timezone.utc).isoformat(), a.discs)
            for r in a.regions for s in a.standins for h in a.horizons for i in a.issues]
    jobs = [j for j in jobs if not (out / f"{j[0]}__{j[1]}__{j[2]}__{j[3][11:13]}.json").exists()]
    print(len(jobs), "jobs", flush=True)
    with ProcessPoolExecutor(a.workers, initializer=init, initargs=(a.regions, a.discs)) as ex:
        for res in ex.map(run_one, jobs):
            p = out / f"{res['region']}__{res['standin']}__{res['horizon']}__{res['issue_utc'][11:13]}.json"
            p.write_text(json.dumps(res))
            n = sum(r["ld_s"] is not None for r in res["rows"])
            print(p.name, "closed", res["closed_cells"], "with LD", n, "/", len(res["rows"]), res["wall_s"], "s", flush=True)


if __name__ == "__main__":
    main()
