#!/usr/bin/env python
"""Corridor-treatment atlas, 영덕 2025, deterministic. Rules: docs/corridor_treatment_atlas.md
(pre-registered). Resumable: each run's result is cached under
data/processed/corridor_treatment_atlas/runs/<id>.json and skipped if present.

    python scripts/run_corridor_treatment_atlas.py [--smoke] [--only C01,R1]
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.buildings import load_buildings  # noqa: E402
from wildfireguardian.config import get as _cfg  # noqa: E402
from wildfireguardian.routing.evacuation import future_aware_route, naive_route  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.routing.rescue import RescueConfig, assess_ingress, rescuer_reachable  # noqa: E402
from wildfireguardian.routing.slope import build_walk_network, load_snapshot_graph  # noqa: E402
from wildfireguardian.spread_v2 import data, features as feat, grid as gridmod  # noqa: E402
from wildfireguardian.spread_v2.features import StaticLayers  # noqa: E402
from wildfireguardian.spread_v2.forward_sim import forward_simulate  # noqa: E402
from wildfireguardian.spread_v2.model import IgnitionModelV2  # noqa: E402
from wildfireguardian.spread_v2.weather import weather_series_from_event  # noqa: E402

from run_building_origin_routing import origin_filter  # noqa: E402
from run_multi_region_routing import read_poi_snapshot, snapshot_for  # noqa: E402
from run_real_roads_real_hazard_slope import REAL_OSM_SCAN_STRIDE  # noqa: E402
from run_rescue_routing_full import materialise_snapshots  # noqa: E402
from run_rescue_routing_real_hazard import build_scenario  # noqa: E402

OUTDIR = REPO / "data/processed/corridor_treatment_atlas"
RUNS = OUTDIR / "runs"
DOC = REPO / "docs/corridor_treatment_atlas.md"
FIG = REPO / "docs/figures"
NPZ = REPO / "data/processed/routing_demo_canonical.npz"
FIRE = "yeongdeok_2025"
BBOX = (128.92, 36.1, 129.77, 36.9)
CELL, N_STEPS, STEP_H, ADV = 500.0, 4, 3.0, 0.3
P_CUT, BUDGET, STEP, MAX_SNAP = 0.5, 600.0, 10.0, 500.0
V_CUT, W_MIN, D_MIN = 0.7, 75.0, 30.0
MAX_CHUNK, N_CANDIDATES, N_PAIR_TOP, N_SENS = 12, 20, 5, 3
EXPECTED_BUILDINGS = {"both_safe": 17454, "naive_into_FA_safe": 1606, "no_safe_route": 190}


# ----------------------------------------------------------------------------- helpers
def cell_of(g, x, y):
    return int(math.floor((g.maxy - y) / g.cell_size_m)), int(math.floor((x - g.minx) / g.cell_size_m))


def path_cells(net, path, g, spacing=100.0):
    """Samples along a node path every `spacing` m: ((row, col), x, y, arrival_min)."""
    out = []
    t = 0.0
    for a, b in zip(path[:-1], path[1:]):
        ax, ay = net.node_xy(a); bx, by = net.node_xy(b)
        dt = float(net.graph[a][b]["time_min"]); L = math.hypot(bx - ax, by - ay)
        n = max(1, int(L // spacing))
        for i in range(n + 1):
            f = i / n; x = ax + f * (bx - ax); y = ay + f * (by - ay)
            out.append((cell_of(g, x, y), x, y, t + f * dt))
        t += dt
    if len(path) == 1:
        x, y = net.node_xy(path[0]); out.append((cell_of(g, x, y), x, y, 0.0))
    return out


def hazard_at(stack, times, rc, t):
    """Step-wise (no interpolation) hazard of cell rc at time t: last slice at or before t."""
    i = int(np.searchsorted(times, t, side="right")) - 1
    i = max(0, min(i, len(times) - 1))
    r, c = rc
    if 0 <= r < stack.shape[1] and 0 <= c < stack.shape[2]:
        return float(stack[i, r, c])
    return 0.0


def components(cells):
    """8-connected components of a set of (r, c)."""
    cells = set(cells); comps = []
    while cells:
        seed = cells.pop(); stack = [seed]; comp = [seed]
        while stack:
            r, c = stack.pop()
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    n = (r + dr, c + dc)
                    if n in cells:
                        cells.remove(n); stack.append(n); comp.append(n)
        comps.append(sorted(comp))
    return comps


def split_chunks(comp, max_size, seed=0):
    if len(comp) <= max_size:
        return [comp]
    from sklearn.cluster import KMeans
    k = int(math.ceil(len(comp) / max_size))
    X = np.array(comp, dtype=float)
    lab = KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(X)
    return [sorted(tuple(map(int, X[i])) for i in np.where(lab == j)[0]) for j in range(k)]


# ----------------------------------------------------------------------------- setup
class Atlas:
    def __init__(self):
        t0 = time.monotonic()
        fire_ids = [m.id for m in data.list_fires()]
        ds = feat.build_dataset(fire_ids, cell_size_m=CELL, buffer_m=float(_cfg("grid.feature_buffer_m", 6000.0)))
        assert (len(ds), int(ds["label"].sum())) == (151904, 2989), "not the canonical dataset"
        self.model = IgnitionModelV2(seed=int(_cfg("seeds.canonical", 20250603))).fit(ds[ds["fire_id"] != FIRE])
        self.ev = data.load_event(FIRE); self.ws = weather_series_from_event(self.ev)
        self.hg = gridmod.build_grid(BBOX, cell_size_m=CELL)
        snaps = gridmod.overpass_snapshots(self.ev, self.hg, gap_minutes=90.0)
        self.static = StaticLayers.from_event(self.ev, self.hg)
        self.initial_active = snaps[0].cumulative_mask; self.start_time = snaps[0].time
        self.base_hz = self.simulate(None)
        ref = np.load(NPZ)["haz_stack"]
        self.base_stack = np.array(self.base_hz.surfaces, dtype=np.float32)
        self.base_maxdiff = float(np.abs(self.base_stack - ref).max())
        assert self.base_maxdiff < 1e-3, f"base does not reproduce the committed field: {self.base_maxdiff}"
        self.times = np.asarray(self.base_hz.times_min, float)
        print(f"[setup] model + base field reproduced (max diff {self.base_maxdiff:.2e}) {time.monotonic()-t0:.0f}s", flush=True)

        # walk network + buildings (WFG-275 population)
        G = load_snapshot_graph(snapshot_for(FIRE, "walk"))
        self.net, _ = build_walk_network(G, REPO / f"data/raw/firms_data/{FIRE}_dem.tif", sampling_m=60.0, max_abs_slope=0.6, directed=True, apply_slope=True)
        dests, _ = read_poi_snapshot(snapshot_for(FIRE, "shelters"), kind="shelter")
        self.net.shelters = {self.net.nearest_node(d.x, d.y) for d in dests}
        self.refuges_xy = [(d.x, d.y) for d in dests]
        bld = load_buildings(FIRE, source="juso_main", repo=REPO)
        n = len(bld); snap_node = np.empty(n, dtype=object); snap_dist = np.empty(n)
        for i in range(n):
            x, y = float(bld.xy[i, 0]), float(bld.xy[i, 1]); nid = self.net.nearest_node(x, y); nx_, ny_ = self.net.node_xy(nid)
            snap_node[i] = nid; snap_dist[i] = math.hypot(nx_ - x, ny_ - y)
        z = np.load(NPZ); haz = z["haz_stack"].astype(np.float32); ext = [float(v) for v in z["grid_extent"]]
        keep, _, _ = origin_filter(bld.xy, haz, ext, P_CUT)
        routable = (snap_dist <= MAX_SNAP) & keep
        r_nodes = snap_node[np.where(routable)[0]].astype(np.int64)
        uniq, counts = np.unique(r_nodes, return_counts=True)
        self.nodes = [int(v) for v in uniq]; self.w = {int(a): int(b) for a, b in zip(uniq, counts)}
        self.n_buildings = int(routable.sum())
        print(f"[setup] walk net {self.net.graph.number_of_nodes()} nodes; {len(self.nodes)} routed nodes / {self.n_buildings} buildings {time.monotonic()-t0:.0f}s", flush=True)

        # drive network + depots (NH-057 scenario), only the network and depots are used
        tmp = Path(tempfile.mkdtemp(prefix="wfg-atlas-"))
        try:
            materialise_snapshots(tmp / FIRE)
            cfg = RescueConfig(use_osm=True, osm_cache_dir=str(tmp), scan_stride=REAL_OSM_SCAN_STRIDE)
            sc = build_scenario(cfg)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.drive = sc.drive; self.depots_xy = [(d.x, d.y) for d in sc.depots]
        self.depot_nodes = [self.drive.nearest_node(d.x, d.y) for d in sc.depots]
        self.cfg = replace(cfg, responder_time_budget_min=W_MIN, responder_dispatch_delay_min=D_MIN, vehicle_cutoff=V_CUT)
        print(f"[setup] drive net {self.drive.graph.number_of_nodes()} nodes, {len(self.depot_nodes)} depots {time.monotonic()-t0:.0f}s", flush=True)

    def simulate(self, treated_cells, factor=0.0):
        b = self.static.burnable_frac.copy()
        if treated_cells:
            rr = np.array([c[0] for c in treated_cells]); cc = np.array([c[1] for c in treated_cells])
            b[rr, cc] = b[rr, cc] * factor
        st = StaticLayers(elevation=self.static.elevation, slope=self.static.slope, burnable_frac=b)
        sim = forward_simulate(self.model, self.ev, self.hg, st, self.initial_active, self.start_time, self.ws,
                               n_steps=N_STEPS, step_hours=STEP_H, advance_threshold=ADV)
        return HazardSequence.from_forward_sim(sim)

    # ---- one evaluation ------------------------------------------------------------
    def walk_classes(self, hz):
        out = {}
        for n in self.nodes:
            nv = naive_route(self.net, n, hz, departure_min=0.0, p_cut=P_CUT, objective="length_m")
            fa = future_aware_route(self.net, n, hz, departure_min=0.0, time_budget_min=BUDGET, p_cut=P_CUT, time_step_min=STEP)
            if not nv.reached: k = "naive_unreachable"
            elif nv.enters_hazard and fa.reached and not fa.enters_hazard: k = "naive_into_FA_safe"
            elif nv.enters_hazard and not fa.reached: k = "no_safe_route"
            elif not nv.enters_hazard and fa.reached and not fa.enters_hazard: k = "both_safe"
            elif nv.enters_hazard and fa.enters_hazard: k = "both_enter"
            elif not nv.enters_hazard and not fa.reached: k = "fa_exceeds_budget"
            else: k = "unclassified"
            out[n] = (k, nv)
        return out

    def vehicle(self, hz, nodes):
        res = {}
        for n in nodes:
            hd = self.drive.nearest_node(*self.net.node_xy(n))
            ok, rt, dep = rescuer_reachable(self.drive, self.depot_nodes, hd, hz, self.cfg)
            res[n] = {"reachable": bool(ok), "depot": dep, "eta_min": (None if rt is None else round(D_MIN + rt.total_time_min, 1))}
        return res

    def evaluate(self, run_id, cells, factor=0.0, base=None):
        p = RUNS / f"{run_id}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        t0 = time.monotonic()
        hz = self.simulate(cells, factor) if cells is not None else self.base_hz
        stack = np.array(hz.surfaces, dtype=np.float32)
        cls = self.walk_classes(hz)
        counts_b = {}; counts_n = {}
        for n, (k, _) in cls.items():
            counts_b[k] = counts_b.get(k, 0) + self.w[n]; counts_n[k] = counts_n.get(k, 0) + 1
        need = [n for n, (k, _) in cls.items() if k == "no_safe_route"]
        base_need = need if base is None else base["needs_rescue_nodes"]
        veh = self.vehicle(hz, sorted(set(base_need)))
        rec = {"run_id": run_id, "n_cells": (len(cells) if cells else 0), "factor": factor,
               "cells": ([list(c) for c in cells] if cells else []),
               "buildings": counts_b, "nodes": counts_n, "needs_rescue_nodes": need,
               "vehicle_reachable_nodes": sum(1 for v in veh.values() if v["reachable"]),
               "vehicle_reachable_buildings": sum(self.w[n] for n, v in veh.items() if v["reachable"]),
               "vehicle": {str(n): v for n, v in veh.items()},
               "envelope_cells_ge05": [int((stack[i] >= 0.5).sum()) for i in range(stack.shape[0])],
               "walk_class_by_node": {str(n): k for n, (k, _) in cls.items()},
               "seconds": round(time.monotonic() - t0, 1)}
        if cells:
            rr = np.array([c[0] for c in cells]); cc = np.array([c[1] for c in cells])
            rec["treated_cells_burning_at_720"] = int((stack[-1, rr, cc] >= 0.5).sum())
            # did the fire get beyond the strip: burning cells at 720 within 3 km of the strip that
            # are farther from the ignition footprint than the strip's farthest cell
            ign = np.argwhere(self.initial_active)
            def dmin(pt): return float(np.min(np.hypot(ign[:, 0] - pt[0], ign[:, 1] - pt[1])))
            strip_far = max(dmin(c) for c in cells)
            burning = np.argwhere(stack[-1] >= 0.5)
            beyond = 0
            for b in burning:
                if np.min(np.hypot(rr - b[0], cc - b[1])) <= 6 and dmin(b) > strip_far:
                    beyond += 1
            rec["burning_beyond_strip_within_3km"] = beyond
            b0 = self.base_stack[-1] >= 0.5
            rec["envelope_change_cells_720"] = int((stack[-1] >= 0.5).sum() - b0.sum())
        if base is not None:
            rec["kept_walkable"] = base["buildings"].get("no_safe_route", 0) - counts_b.get("no_safe_route", 0)
            rec["kept_simple"] = counts_b.get("both_safe", 0) - base["buildings"].get("both_safe", 0)
            rec["kept_reachable"] = rec["vehicle_reachable_buildings"] - base["vehicle_reachable_buildings"]
            rec["fa_only_change"] = counts_b.get("naive_into_FA_safe", 0) - base["buildings"].get("naive_into_FA_safe", 0)
            rec["primary"] = rec["kept_walkable"] + rec["kept_reachable"]
            rec["per_cell"] = round(rec["primary"] / max(1, rec["n_cells"]), 2)
        RUNS.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[run] {run_id}: cells {rec['n_cells']} → buildings {counts_b} vehicle {rec['vehicle_reachable_buildings']} "
              f"{'kept_walkable=%s kept_reachable=%s kept_simple=%s' % (rec.get('kept_walkable'), rec.get('kept_reachable'), rec.get('kept_simple')) if base else ''} {rec['seconds']}s", flush=True)
        return rec

    # ---- candidates ----------------------------------------------------------------
    def candidates(self, base_cls):
        g = self.hg
        conflict = {}   # cell -> set of nodes whose route meets fire there
        def inside(rc): return 0 <= rc[0] < g.nrows and 0 <= rc[1] < g.ncols
        # the router's own sampler (bilinear in space, linear in time), so a conflict cell is
        # exactly where _evaluate_path would mark the route as entering the hazard
        for n, (k, nv) in base_cls.items():
            if not nv.reached:
                continue
            for rc, x, y, t in path_cells(self.net, list(nv.route), g):
                if inside(rc) and not self.initial_active[rc] and self.base_hz.prob_at(x, y, t) >= P_CUT:
                    conflict.setdefault(rc, set()).add(n)
        need = [n for n, (k, _) in base_cls.items() if k == "no_safe_route"]
        for n in need:
            hd = self.drive.nearest_node(*self.net.node_xy(n))
            ing = assess_ingress(self.drive, self.depot_nodes, hd, self.base_hz, self.cfg)
            if ing.corridor_nodes:
                for rc, x, y, t in path_cells(self.drive, list(ing.corridor_nodes), g):
                    if inside(rc) and not self.initial_active[rc] and self.base_hz.prob_at(x, y, D_MIN + t) >= V_CUT:
                        conflict.setdefault(rc, set()).add(n)
        comps = components(list(conflict))
        chunks = []
        for comp in comps:
            for ch in split_chunks(comp, MAX_CHUNK):
                nodes = set().union(*(conflict[c] for c in ch))
                chunks.append({"cells": ch, "n_nodes": len(nodes), "buildings_affected": sum(self.w[n] for n in nodes)})
        chunks.sort(key=lambda d: (-d["buildings_affected"], -len(d["cells"])))
        cands = {f"C{i+1:02d}": d for i, d in enumerate(chunks[:N_CANDIDATES])}
        return cands, len(conflict), len(comps), len(chunks)

    def dilate_chunk(self, cells, k=1):
        """Cells within Chebyshev distance k of the chunk, burnable, not burning at t0."""
        g = self.hg; b = self.static.burnable_frac; out = set()
        for (r, c) in cells:
            for dr in range(-k, k + 1):
                for dc in range(-k, k + 1):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < g.nrows and 0 <= cc < g.ncols and b[rr, cc] > 0.05 and not self.initial_active[rr, cc]:
                        out.add((rr, cc))
        return sorted(out)

    def ring(self, k=2):
        """All burnable cells within Chebyshev distance k of the t0 footprint, not burning at t0."""
        g = self.hg; b = self.static.burnable_frac; out = set()
        for (r, c) in np.argwhere(self.initial_active):
            for dr in range(-k, k + 1):
                for dc in range(-k, k + 1):
                    rr, cc = int(r + dr), int(c + dc)
                    if 0 <= rr < g.nrows and 0 <= cc < g.ncols and b[rr, cc] > 0.05 and not self.initial_active[rr, cc]:
                        out.add((rr, cc))
        return sorted(out)

    def controls(self, m):
        b = self.static.burnable_frac; H = self.base_stack
        env = (H[-1] >= 0.5) & (~self.initial_active) & (b > 0.05)
        pool = [tuple(map(int, rc)) for rc in np.argwhere(env)]
        out = {}
        for s in (1, 2, 3):
            rng = np.random.default_rng(s); idx = rng.choice(len(pool), size=min(m, len(pool)), replace=False)
            out[f"R{s}"] = {"cells": sorted(pool[i] for i in idx), "rule": f"random burnable cells inside the 720-min envelope, seed {s}"}
        front = (H[1] < 0.5) & (b > 0.05) & (~self.initial_active)
        cand = [(float(H[2, r, c]), (int(r), int(c))) for r, c in np.argwhere(front)]
        cand.sort(key=lambda x: -x[0]); out["H1"] = {"cells": sorted(rc for _, rc in cand[:m]), "rule": "highest hazard at 360 min among cells not yet ≥0.5 at 180 min (risk-ranked front)"}
        line = (H[1] >= 0.3) & (H[1] < 0.5) & (b > 0.05) & (~self.initial_active)
        cand2 = [(float(H[1, r, c]), (int(r), int(c))) for r, c in np.argwhere(line)]
        cand2.sort(key=lambda x: -x[0]); out["E1"] = {"cells": sorted(rc for _, rc in cand2[:m]), "rule": "cells in the 0.3–0.5 band at 180 min (hold-the-line at 3 h)"}
        return out


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--smoke", action="store_true"); ap.add_argument("--only", default="")
    args = ap.parse_args()
    t_all = time.monotonic()
    A = Atlas()
    base = A.evaluate("BASE", None)
    got = {k: base["buildings"].get(k, 0) for k in EXPECTED_BUILDINGS}
    assert got == EXPECTED_BUILDINGS, f"reproduction gate failed: {got} != {EXPECTED_BUILDINGS}"
    print(f"[gate] building partition reproduced {got}; needs-rescue nodes {len(base['needs_rescue_nodes'])}, vehicle-reachable buildings {base['vehicle_reachable_buildings']}", flush=True)
    base_cls = A.walk_classes(A.base_hz) if not (RUNS / "BASE_cls.json").exists() else None
    if base_cls is not None:
        (RUNS / "BASE_cls.json").write_text(json.dumps({str(n): k for n, (k, _) in base_cls.items()}), encoding="utf-8")
    candsA, n_conf, n_comp, n_chunks = A.candidates(base_cls or A.walk_classes(A.base_hz))
    # families (amendment §4b): A = conflict chunks as declared; B = A dilated by one cell;
    # W = A dilated by two cells (top-1 only, width check); P = the whole perimeter band
    cands = {}
    for k, d in candsA.items():
        cands[k] = dict(d, family="A")
        cands[k.replace("C", "B", 1)] = {"cells": A.dilate_chunk(d["cells"], 1), "n_nodes": d["n_nodes"], "buildings_affected": d["buildings_affected"], "family": "B", "parent": k}
    cands["P2"] = {"cells": A.ring(2), "n_nodes": None, "buildings_affected": None, "family": "P", "rule": "all burnable cells within 2 cells of the t0 footprint"}
    cands["P1"] = {"cells": A.ring(1), "n_nodes": None, "buildings_affected": None, "family": "P", "rule": "all burnable cells within 1 cell of the t0 footprint"}
    sizesB = [len(d["cells"]) for k, d in cands.items() if d["family"] == "B"]; m = int(np.median(sizesB)) if sizesB else 8
    ctrls = A.controls(m)
    plan = {"candidates": cands, "controls": ctrls, "n_conflict_cells": n_conf, "n_components": n_comp, "n_chunks": n_chunks, "control_size": m,
            "families": {"A": "conflict chunks (declared §4)", "B": "A dilated by one cell (amendment §4b)", "P": "perimeter bands (amendment §4b)", "W": "top B candidate dilated by two cells (width check)"}}
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[plan] conflict cells {n_conf}, components {n_comp}, chunks {n_chunks}; A {len(candsA)} (sizes {[len(d['cells']) for d in candsA.values()]}), B sizes {sizesB}, P {len(cands['P1']['cells'])}/{len(cands['P2']['cells'])} cells, control size {m}", flush=True)
    order = [k for k in cands if cands[k]["family"] == "B"] + [k for k in cands if cands[k]["family"] == "A"] + ["P1", "P2"] + list(ctrls)
    if args.only: order = [o for o in order if o in args.only.split(",")]
    if args.smoke: order = order[:1] + [k for k in order if k.startswith("R")][:1]
    results = {"BASE": base}
    for rid in order:
        cells = [tuple(c) for c in (cands.get(rid) or ctrls.get(rid))["cells"]]
        results[rid] = A.evaluate(rid, cells, base=base)
    if args.smoke or args.only:
        print("smoke done"); return 0
    singlesB = sorted([k for k in cands if cands[k]["family"] == "B"], key=lambda r: (-results[r]["primary"], -results[r]["kept_simple"]))
    top = singlesB[:N_PAIR_TOP]
    if top:
        w2 = A.dilate_chunk(candsA[top[0].replace("B", "C", 1)]["cells"], 2)
        cands["W" + top[0][1:]] = {"cells": w2, "family": "W", "parent": top[0]}
        results["W" + top[0][1:]] = A.evaluate("W" + top[0][1:], [tuple(c) for c in w2], base=base)
    for i in range(len(top)):
        for j in range(i + 1, len(top)):
            a, b = top[i], top[j]; cells = sorted(set(map(tuple, cands[a]["cells"])) | set(map(tuple, cands[b]["cells"])))
            results[f"{a}+{b}"] = A.evaluate(f"{a}+{b}", cells, base=base)
    if len(top) >= 3:
        cells = sorted(set().union(*(set(map(tuple, cands[t]["cells"])) for t in top[:3])))
        results["+".join(top[:3])] = A.evaluate("+".join(top[:3]), cells, base=base)
    for t in singlesB[:N_SENS]:
        results[f"{t}x0.5"] = A.evaluate(f"{t}x0.5", [tuple(c) for c in cands[t]["cells"]], factor=0.5, base=base)
    singles = sorted([k for k in cands if cands[k]["family"] in ("A", "B", "P", "W") and k in results], key=lambda r: (-results[r]["primary"], -results[r]["kept_simple"]))
    summarise(A, cands, ctrls, results, singles, top, plan, t_all)
    return 0


def summarise(A, cands, ctrls, results, singles, top, plan, t_all):
    base = results["BASE"]
    def row(rid):
        r = results[rid]; return {"id": rid, "family": (cands.get(rid) or {}).get("family", "control"), "cells": r["n_cells"], "kept_walkable": r["kept_walkable"], "kept_reachable": r["kept_reachable"], "kept_simple": r["kept_simple"], "primary": r["primary"], "per_cell": r["per_cell"], "envelope_change": r.get("envelope_change_cells_720", 0), "beyond": r.get("burning_beyond_strip_within_3km", 0), "buildings_affected": (cands.get(rid) or {}).get("buildings_affected")}
    single_rows = [row(r) for r in singles]; ctrl_rows = [row(r) for r in ctrls]
    pairs = []
    for i in range(len(top)):
        for j in range(i + 1, len(top)):
            a, b = top[i], top[j]; k = f"{a}+{b}"
            if k in results:
                inter = results[k]["primary"] - results[a]["primary"] - results[b]["primary"]
                pairs.append({"pair": k, "primary": results[k]["primary"], "sum_of_singles": results[a]["primary"] + results[b]["primary"], "interaction": inter, "cells": results[k]["n_cells"]})
    trip = "+".join(top[:3]); triple = None
    if trip in results:
        triple = {"triple": trip, "primary": results[trip]["primary"], "sum_of_singles": sum(results[t]["primary"] for t in top[:3])}
    sens = [{"id": k, "primary": results[k]["primary"], "kept_walkable": results[k]["kept_walkable"], "kept_reachable": results[k]["kept_reachable"]} for k in results if k.endswith("x0.5")]
    # greedy budget curve over singles with measured pair corrections
    chosen, curve, total = [], [], 0
    pair_inter = {p["pair"]: p["interaction"] for p in pairs}
    remaining = list(singles)
    for _ in range(min(5, len(remaining))):
        best, bestv = None, -1e9
        for r in remaining:
            v = results[r]["primary"] + sum(pair_inter.get(f"{min(r, c)}+{max(r, c)}", pair_inter.get(f"{c}+{r}", pair_inter.get(f"{r}+{c}", 0))) for c in chosen)
            if v > bestv: best, bestv = r, v
        chosen.append(best); remaining.remove(best); total += bestv
        curve.append({"k": len(chosen), "added": best, "cells_cum": sum(results[c]["n_cells"] for c in chosen), "primary_cum_estimate": int(total), "interaction_terms_measured": sum(1 for c in chosen[:-1] if any(k2 in pair_inter for k2 in (f"{c}+{best}", f"{best}+{c}")))})
    # secondary analysis (declared §5 as kept_simple): the outcome that moved
    singles_s = sorted([r for r in singles], key=lambda r: -results[r]["kept_simple"])
    pairs_s = []
    for p in pairs:
        a, b = p["pair"].split("+")
        pairs_s.append({"pair": p["pair"], "cells": p["cells"], "kept_simple": results[p["pair"]]["kept_simple"], "sum_of_singles": results[a]["kept_simple"] + results[b]["kept_simple"], "interaction": results[p["pair"]]["kept_simple"] - results[a]["kept_simple"] - results[b]["kept_simple"]})
    trip_s = None
    if trip in results:
        trip_s = {"triple": trip, "kept_simple": results[trip]["kept_simple"], "sum_of_singles": sum(results[t]["kept_simple"] for t in top[:3])}
    sens_s = [{"id": k, "kept_simple": results[k]["kept_simple"], "kept_simple_at_zero": results[k[:-4]]["kept_simple"]} for k in results if k.endswith("x0.5")]
    eff = [{"id": r, "family": cands[r].get("family"), "cells": results[r]["n_cells"], "kept_simple": results[r]["kept_simple"], "per_cell": round(results[r]["kept_simple"] / max(1, results[r]["n_cells"]), 2)} for r in singles_s]
    out = {"schema_version": 1, "title": "Corridor-treatment atlas, 영덕 2025 (deterministic, forecast-graded)",
           "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
           "rule_doc": "docs/corridor_treatment_atlas.md §1-§5 (pre-registered)",
           "reproduction": {"base_field_max_abs_diff": A.base_maxdiff, "base_buildings": base["buildings"], "n_nodes": len(A.nodes), "n_buildings": A.n_buildings},
           "plan": {k: v for k, v in plan.items() if k != "candidates"}, "candidates": cands, "controls": {k: {"rule": v["rule"], "n_cells": len(v["cells"])} for k, v in ctrls.items()},
           "base": {"buildings": base["buildings"], "needs_rescue_nodes": len(base["needs_rescue_nodes"]), "vehicle_reachable_buildings": base["vehicle_reachable_buildings"], "envelope_cells_ge05": base["envelope_cells_ge05"]},
           "singles": single_rows, "controls_results": ctrl_rows, "pairs": pairs, "triple": triple, "sensitivity_x0_5": sens, "greedy_budget_curve": curve,
           "secondary_kept_simple": {"note": "the pre-declared primary (kept walkable + kept reachable) is zero for every run; this block ranks the declared secondary outcome, buildings whose shortest walk becomes safe", "singles": eff, "pairs": pairs_s, "triple": trip_s, "sensitivity_x0_5": sens_s},
           "seconds_total": round(time.monotonic() - t_all, 1)}
    (OUTDIR / "atlas_yeongdeok.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    figures(A, cands, ctrls, results, singles, pairs, top)
    L = ["", f"_Run {out['generated_utc']} at `{out['git_commit'][:7]}`; artifact `data/processed/corridor_treatment_atlas/atlas_yeongdeok.json` (per-run records under `runs/`); base field reproduced (max abs diff {A.base_maxdiff:.1e}); building partition {base['buildings']}; {len(A.nodes)} nodes / {A.n_buildings} buildings; {out['seconds_total']/60:.0f} min; figures `docs/figures/atlas_*.png`._", "",
         f"Conflict cells {plan['n_conflict_cells']} in {plan['n_components']} components → {plan['n_chunks']} chunks; {len(cands)} candidates; control size {plan['control_size']} cells. Base: needs-rescue nodes {len(base['needs_rescue_nodes'])}, vehicle-reachable buildings {base['vehicle_reachable_buildings']}, envelope cells ≥ 0.5 per slice {base['envelope_cells_ge05']}.", "",
         "### Single treatments (buildings, vs base; primary = kept walkable + kept reachable)", "",
         "| id | family | cells | buildings behind routes crossing it | kept walkable | kept reachable | kept simple (shortest walk safe) | primary | per cell | envelope Δ cells (720) | burning beyond strip |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in single_rows + ctrl_rows:
        L.append(f"| {r['id']} | {r['family']} | {r['cells']} | {r['buildings_affected'] if r['buildings_affected'] is not None else '—'} | {r['kept_walkable']} | {r['kept_reachable']} | {r['kept_simple']} | {r['primary']} | {r['per_cell']} | {r['envelope_change']} | {r['beyond']} |")
    L += ["", "### Pairs among the top five (interaction = pair − sum of singles, buildings)", "", "| pair | cells | pair primary | sum of singles | interaction |", "|---|---:|---:|---:|---:|"]
    for p in pairs: L.append(f"| {p['pair']} | {p['cells']} | {p['primary']} | {p['sum_of_singles']} | {p['interaction']:+d} |")
    if triple: L.append(f"\nTriple {triple['triple']}: primary {triple['primary']} vs sum of singles {triple['sum_of_singles']}.")
    L += ["", "### Sensitivity (burnable × 0.5 instead of 0)", ""] + [f"- {s['id']}: primary {s['primary']} (walkable {s['kept_walkable']}, reachable {s['kept_reachable']})" for s in sens]
    L += ["", "### Greedy budget curve (singles, pair-corrected where measured)", "", "| k | added | cumulative cells | cumulative primary (estimate) |", "|---|---|---:|---:|"] + [f"| {c['k']} | {c['added']} | {c['cells_cum']} | {c['primary_cum_estimate']} |" for c in curve]
    L += ["", "### Secondary outcome: buildings whose shortest walk becomes safe (`kept_simple`)", "",
          "The pre-declared primary is zero for every run (§7). This ranks the declared secondary outcome.", "",
          "| id | family | cells | kept simple | per cell |", "|---|---|---:|---:|---:|"] + [f"| {e['id']} | {e['family']} | {e['cells']} | {e['kept_simple']} | {e['per_cell']} |" for e in eff if e["kept_simple"] > 0]
    L += ["", "| pair | cells | pair kept simple | sum of singles | interaction |", "|---|---:|---:|---:|---:|"] + [f"| {p['pair']} | {p['cells']} | {p['kept_simple']} | {p['sum_of_singles']} | {p['interaction']:+d} |" for p in pairs_s]
    if trip_s: L.append(f"\nTriple {trip_s['triple']}: kept simple {trip_s['kept_simple']} vs sum of singles {trip_s['sum_of_singles']}.")
    L += [""] + [f"- {x['id']}: kept simple {x['kept_simple']} (at burnable 0: {x['kept_simple_at_zero']})" for x in sens_s]
    DOC.write_text(DOC.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L), flush=True)


def figures(A, cands, ctrls, results, singles, pairs, top):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIG.mkdir(exist_ok=True)
    g = A.hg; H = A.base_stack
    fig, ax = plt.subplots(figsize=(9, 10))
    ext = [g.minx, g.maxx, g.miny, g.maxy]
    ax.imshow(np.where(A.initial_active, 1.0, np.nan), extent=ext, origin="upper", cmap="Greys", vmin=0, vmax=1.4, alpha=0.9)
    ax.contour(np.linspace(g.minx + 250, g.maxx - 250, g.ncols), np.linspace(g.maxy - 250, g.miny + 250, g.nrows), H[-1], levels=[0.5], colors="firebrick", linewidths=1.2)
    ax.contour(np.linspace(g.minx + 250, g.maxx - 250, g.ncols), np.linspace(g.maxy - 250, g.miny + 250, g.nrows), H[1], levels=[0.5], colors="orange", linewidths=0.8)
    drawn = [r for r in singles if cands[r].get("family") in ("B", "A")]
    vals = [results[r]["kept_simple"] / max(1, results[r]["n_cells"]) for r in drawn] or [0.0]; vmax = max(1e-9, max(vals))
    cmap = plt.get_cmap("viridis")
    for r in drawn:
        v = (results[r]["kept_simple"] / max(1, results[r]["n_cells"])) / vmax
        for (rr, cc) in cands[r]["cells"]:
            ax.add_patch(plt.Rectangle((g.minx + cc * g.cell_size_m, g.maxy - (rr + 1) * g.cell_size_m), g.cell_size_m, g.cell_size_m, color=cmap(v), alpha=0.85, lw=0))
        c0 = cands[r]["cells"][len(cands[r]["cells"]) // 2]
        ax.text(g.minx + (c0[1] + 0.5) * g.cell_size_m, g.maxy - (c0[0] + 0.5) * g.cell_size_m, r, fontsize=6, color="black", ha="center")
    ax.scatter([x for x, _ in A.refuges_xy], [y for _, y in A.refuges_xy], s=8, c="dodgerblue", label="refuges")
    ax.scatter([x for x, _ in A.depots_xy], [y for _, y in A.depots_xy], s=30, marker="^", c="black", label="depots")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, vmax)); fig.colorbar(sm, ax=ax, shrink=0.6, label="buildings whose shortest walk becomes safe, per treated cell")
    ax.set_title("Corridor-treatment atlas, Yeongdeok 2025 (deterministic, forecast-graded)\nred: base envelope p≥0.5 at 720 min; orange: at 180 min; grey: burning at t0", fontsize=9)
    ax.set_xlim(g.minx, g.maxx); ax.set_ylim(g.miny, g.maxy); ax.set_aspect("equal"); ax.legend(loc="lower left", fontsize=7)
    fig.savefig(FIG / "atlas_map_yeongdeok.png", dpi=140, bbox_inches="tight"); plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 4))
    ids = singles + list(ctrls); vals = [results[r]["kept_simple"] for r in ids]; cols = [{"A": "steelblue", "B": "navy", "P": "darkorange", "W": "purple"}.get(cands.get(r, {}).get("family"), "grey") for r in ids]
    ax.bar(ids, vals, color=cols); ax.set_ylabel("buildings whose shortest walk becomes safe (kept_simple)"); ax.tick_params(axis="x", rotation=90, labelsize=7)
    ax.set_title("single treatments (blue: corridor candidates; grey: controls R1-3 random, H1 risk-ranked, E1 hold-the-line)", fontsize=9)
    fig.savefig(FIG / "atlas_singles_yeongdeok.png", dpi=140, bbox_inches="tight"); plt.close(fig)
    if pairs:
        M = np.full((len(top), len(top)), np.nan)
        for p in pairs:
            a, b = p["pair"].split("+"); i, j = top.index(a), top.index(b); M[i, j] = M[j, i] = results[p["pair"]]["kept_simple"] - results[a]["kept_simple"] - results[b]["kept_simple"]
        fig, ax = plt.subplots(figsize=(4.5, 4)); im = ax.imshow(M, cmap="RdBu", vmin=-np.nanmax(np.abs(M)) if np.nanmax(np.abs(M)) > 0 else -1, vmax=np.nanmax(np.abs(M)) if np.nanmax(np.abs(M)) > 0 else 1)
        ax.set_xticks(range(len(top))); ax.set_xticklabels(top); ax.set_yticks(range(len(top))); ax.set_yticklabels(top)
        for i in range(len(top)):
            for j in range(len(top)):
                if not np.isnan(M[i, j]): ax.text(j, i, f"{int(M[i, j]):+d}", ha="center", va="center", fontsize=8)
        fig.colorbar(im, ax=ax, label="interaction (buildings)"); ax.set_title("pair interaction on kept_simple: + reinforcing, − redundant", fontsize=9)
        fig.savefig(FIG / "atlas_interactions_yeongdeok.png", dpi=140, bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
