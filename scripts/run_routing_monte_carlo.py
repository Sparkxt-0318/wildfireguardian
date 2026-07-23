#!/usr/bin/env python
"""Routing Monte Carlo under prediction uncertainty (spread_v2, Yeongdeok 2025).

Measures whether the future-aware evacuation router still helps when the fire
prediction is wrong. AUDIT-style: imports the existing spread_v2 + routing logic
UNCHANGED and only adds this driver + ``scripts/mc_perturb.py``. No existing
identifier or dict key is renamed. No figures/documents are written.

Canonical model: spread_v2 = sklearn HistGradientBoostingClassifier, seed
20250603. The abandoned spread_v2_xgb build is never imported or referenced.

Definitions (see the task spec):
  f_hat        predicted per-cell/per-step ignition-probability field from
               spread_v2 under OBSERVED ERA5 drivers (what the router gets).
  f_prime_k    realisation k of the "true" fire: perturb drivers (Ensemble A) or
               refit on bootstrap fires (Ensemble B), re-run spread_v2, binarise.
  t_arrival_k  first time a cell is burned in f_prime_k (binarised at the SAME
               threshold as the footprint IoU metric, 0.5). Two variants:
               (primary) front-distance sub-step interpolation within each
               180-min step; (sensitivity) raw 180-min step boundary.
  t_walker     time the evacuee occupies a cell on a given route (departure=0).
  margin(route,k) = min over route cells of (t_arrival_k - t_walker). Negative =
               caught. All-never-burned route => +inf (non-exposed origin).

Routes: baseline (naive_route, fire-blind), forecast_aware (future_aware_route on
f_hat, the method under test), oracle (future_aware_route on the BINARISED f_prime_k
arrival field — routed AND scored on the same representation).

Run:  python scripts/run_routing_monte_carlo.py [--tier 1|2|3] [--pilot N] ...
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.ndimage import binary_dilation, distance_transform_edt
from scipy.ndimage import label as _ndlabel

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.spread_v2 import data, features, grid as gridmod  # noqa: E402
from wildfireguardian.spread_v2.features import StaticLayers  # noqa: E402
from wildfireguardian.spread_v2.model import (  # noqa: E402
    DEFAULT_SEED, IgnitionModelV2, footprint_iou_lofo, leave_one_fire_out,
)
from wildfireguardian.spread_v2.forward_sim import forward_simulate  # noqa: E402
from wildfireguardian.spread_v2.weather import weather_series_from_event  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.routing.evacuation import (  # noqa: E402
    build_evacuation_network, future_aware_route, naive_route,
)

import mc_perturb as P  # noqa: E402

FIRE = "yeongdeok_2025"
_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)


# ---------------------------------------------------------------------------
# small geometry helpers (nearest hazard-cell mapping, consistent with the
# HazardSequence bilinear sampler's cell-centre convention)
# ---------------------------------------------------------------------------
def cells_of(xs, ys, g: gridmod.CoarseGrid):
    xs = np.atleast_1d(np.asarray(xs, float)); ys = np.atleast_1d(np.asarray(ys, float))
    cols = np.clip(np.round((xs - g.minx) / g.cell_size_m - 0.5).astype(int), 0, g.ncols - 1)
    rows = np.clip(np.round((g.maxy - ys) / g.cell_size_m - 0.5).astype(int), 0, g.nrows - 1)
    return rows, cols


class ArrivalStepHazard:
    """Hazard interface backed by a binarised arrival-time field.

    ``prob_at(cell, t) = 1.0 iff t >= t_arrival[cell] else 0.0`` — a cell is
    impassable (>= p_cut) exactly at its ``t_arrival_k``. Implements the subset
    of the HazardSequence interface the router touches, so the oracle is routed
    AND scored on the identical binarised representation (reviewer condition 1).
    """

    def __init__(self, t_arrival_field: np.ndarray, g: gridmod.CoarseGrid, times_min):
        self.t = t_arrival_field
        self.grid = g
        self.times_min = np.asarray(times_min, float)

    def prob_at_points(self, xs, ys, t_min: float) -> np.ndarray:
        r, c = cells_of(xs, ys, self.grid)
        return (t_min >= self.t[r, c]).astype(float)

    def prob_at(self, x: float, y: float, t_min: float) -> float:
        return float(self.prob_at_points([x], [y], t_min)[0])


# ---------------------------------------------------------------------------
# arrival-time fields from a forward-sim (primary sub-step + raw sensitivity)
# ---------------------------------------------------------------------------
def arrival_fields(sim, threshold: float = 0.5):
    """Return (t_sub, t_raw) arrival-time fields (minutes) on the hazard grid.

    t_raw : first 180-min step at which the cumulative binarised footprint burns
            the cell (step boundary).
    t_sub : within that step, interpolate arrival by the cell's distance from the
            step-(s-1) burned FRONT (distance transform), normalised by the step's
            max front advance -- physically front-like sub-step timing, not
            linear-in-time. Documented as an explicit assumption.
    """
    steps = np.asarray(sim.step_minutes, float)
    B = [(H >= threshold) for H in sim.hazard]      # cumulative, monotone in s
    shape = B[0].shape
    t_raw = np.full(shape, np.inf)
    t_sub = np.full(shape, np.inf)
    t_raw[B[0]] = 0.0
    t_sub[B[0]] = 0.0
    cs = sim.grid.cell_size_m
    for s in range(1, len(B)):
        newly = B[s] & ~B[s - 1]
        if not newly.any():
            continue
        t_raw[newly] = steps[s]
        dist_m = distance_transform_edt(~B[s - 1]) * cs      # dist to step-(s-1) front
        d = dist_m[newly]
        dmax = float(d.max())
        if dmax <= 0.0:
            t_sub[newly] = steps[s]
        else:
            t_sub[newly] = steps[s - 1] + (d / dmax) * (steps[s] - steps[s - 1])
    return t_sub, t_raw


def dilated_masks(sim, threshold: float, radius_cells: int):
    """Per-step binarised footprint dilated by ``radius_cells`` (for exposure)."""
    out = []
    for H in sim.hazard:
        m = (H >= threshold)
        out.append(binary_dilation(m, iterations=radius_cells) if radius_cells > 0 else m)
    return out


# ---------------------------------------------------------------------------
# route scoring against a realisation's arrival field
# ---------------------------------------------------------------------------
def route_margin(route_rc, t_walker, t_field):
    """min over route cells of (t_arrival - t_walker); +inf if never exposed."""
    if route_rc.shape[0] == 0:
        return np.inf
    ta = t_field[route_rc[:, 0], route_rc[:, 1]]
    return float(np.min(ta - t_walker))


def route_exposure_min(route_rc, t_walker, dmasks, steps):
    """Approx minutes spent within 500 m of a burned cell (dilated footprint).

    For each edge, if the node at its start lies inside the 500 m-dilated
    footprint at that node's arrival time (nearest earlier forecast step), the
    edge's traversal time counts. Documented as an approximate exposure proxy.
    """
    n = route_rc.shape[0]
    if n < 2:
        return 0.0
    total = 0.0
    for i in range(n - 1):
        dt = t_walker[i + 1] - t_walker[i]
        s = int(np.searchsorted(steps, t_walker[i], side="right") - 1)
        s = min(max(s, 0), len(dmasks) - 1)
        if dmasks[s][route_rc[i, 0], route_rc[i, 1]]:
            total += dt
    return float(total)


# ---------------------------------------------------------------------------
# fixed (compute-once) block
# ---------------------------------------------------------------------------
def build_fixed(args) -> dict:
    seed = args.seed
    fire_ids = [m.id for m in data.list_fires()]
    print(f"[fixed] building dataset across {len(fire_ids)} fires ...", flush=True)
    ds = features.build_dataset(fire_ids, cell_size_m=args.hazard_cell_m, buffer_m=6000.0)

    gate = {}
    if not args.skip_gate:
        print("[fixed] LOFO gate (pooled AUC + footprint IoU) ...", flush=True)
        lofo = leave_one_fire_out(ds, seed=seed, compute_importance=False)
        fiou = footprint_iou_lofo(sorted(ds["fire_id"].unique()), ds, threshold=args.p_cut,
                                  seed=seed, cell_size_m=args.hazard_cell_m)
        gate = {"pooled_auc": lofo.pooled_auc, "far_band_auc": lofo.far_band_auc,
                "footprint_iou_model": fiou.model_iou, "footprint_iou_persistence": fiou.persistence_iou,
                "n_transitions": fiou.n_transitions}
        print(f"        pooled AUC={lofo.pooled_auc:.3f}  footprint IoU={fiou.model_iou:.3f}", flush=True)

    print(f"[fixed] fitting final model on fires != {FIRE} ...", flush=True)
    model = IgnitionModelV2(seed=seed).fit(ds[ds["fire_id"] != FIRE])
    ev = data.load_event(FIRE)
    ws = weather_series_from_event(ev)
    hg = gridmod.build_grid(ev.meta.bbox_wgs84, cell_size_m=args.hazard_cell_m)
    snaps = gridmod.overpass_snapshots(ev, hg, gap_minutes=90.0)
    hstatic = StaticLayers.from_event(ev, hg)
    sim_hat = forward_simulate(model, ev, hg, hstatic, snaps[0].cumulative_mask, snaps[0].time, ws,
                               n_steps=args.n_steps, step_hours=args.step_hours,
                               advance_threshold=args.advance_threshold)
    f_hat = HazardSequence.from_forward_sim(sim_hat)
    ign_xy = np.array(_TO_5179.transform(*ev.meta.ignition_lonlat), float)

    print("[fixed] building evacuation network ...", flush=True)
    rg = gridmod.build_grid(ev.meta.bbox_wgs84, cell_size_m=args.route_cell_m)
    relev = gridmod.elevation_on_grid(ev, rg)
    rburn = gridmod.burnable_fraction_on_grid(ev, rg)
    net = build_evacuation_network(rg, relev, rburn, flat_speed_ms=0.7)

    # Origin scan: EXACTLY run_routing_integration's stride-4 + 14 km-band, reach-
    # filtered against f_hat (documented 407-origin set), frozen here for all K.
    nodes = list(net.graph.nodes)
    cand = [n for i, n in enumerate(sorted(nodes)) if i % args.scan_stride == 0]
    origins = [n for n in cand
               if f_hat.prob_at(net.graph.nodes[n]["x"], net.graph.nodes[n]["y"], 0.0) < args.p_cut
               and abs(net.graph.nodes[n]["y"] - ign_xy[1]) < 14000]
    print(f"        network {net.graph.number_of_nodes()} nodes, {len(net.shelters)} shelters; "
          f"origins N={len(origins)}", flush=True)

    # Baseline + forecast_aware ONCE (routes fixed across realisations).
    print("[fixed] computing baseline + forecast_aware routes on f_hat ...", flush=True)
    # Baseline (fire-blind nearest-shelter shortest path). ONE multi-source
    # Dijkstra from all shelters gives every node its nearest-shelter distance +
    # path in a single run -- equivalent to naive_route's per-origin nearest-
    # shelter shortest path on this undirected graph, but ~N x faster.
    routes = {}
    n_base_fail = 0
    sdist, spaths = nx.multi_source_dijkstra(net.graph, set(net.shelters), weight="length_m")
    for n in origins:
        if n in spaths and len(spaths[n]) > 0:
            path = list(reversed(spaths[n]))          # shelter->..->origin => origin->..->shelter
            base = _route_rec(net, hg, path)
        else:
            base = _empty_rec()
        n_base_fail += (not base["reached"])
        routes[n] = {"baseline": base, "forecast_aware": None,
                     "dist_to_shelter_m": base["path_length_m"]}
    print(f"        baseline unreached={n_base_fail}; forecast_aware routes deferred "
          f"to the resumable FA stage", flush=True)

    return dict(seed=seed, model=model, ev=ev, ws=ws, hg=hg, snaps=snaps,
                hstatic=hstatic, sim_hat=sim_hat, f_hat=f_hat, ign_xy=ign_xy, net=net,
                origins=origins, routes=routes, paired=None, gate=gate,
                n_base_fail=n_base_fail, n_fa_fail=None, fire_ids=fire_ids, args=args,
                ds=ds, fa_done=False, fa_idx=0)


# ---------------------------------------------------------------------------
# realisation replay (baseline + forecast_aware) against one arrival field
# ---------------------------------------------------------------------------
def replay_fixed_routes(fx, t_field):
    """margins for baseline + forecast_aware over all origins vs one t_field."""
    out = {"baseline": {}, "forecast_aware": {}}
    for n in fx["origins"]:
        for kind in ("baseline", "forecast_aware"):
            rec = fx["routes"][n][kind]
            if not rec["reached"]:
                out[kind][n] = np.nan
            else:
                out[kind][n] = route_margin(rec["rc"], rec["t_walker"], t_field)
    return out


def _route_rec(net, hg, path):
    """Build a route record (cells, walker clock, length) from a node list."""
    xs = np.array([net.graph.nodes[m]["x"] for m in path], float)
    ys = np.array([net.graph.nodes[m]["y"] for m in path], float)
    rr, cc = cells_of(xs, ys, hg)
    arr = [0.0]
    for i in range(len(path) - 1):
        arr.append(arr[-1] + net.graph[path[i]][path[i + 1]]["time_min"])
    dist = sum(net.graph[path[i]][path[i + 1]]["length_m"] for i in range(len(path) - 1))
    return {"reached": True, "rc": np.stack([rr, cc], axis=1),
            "t_walker": np.asarray(arr, float), "path_length_m": float(dist),
            "route_nodes": list(path)}


def _empty_rec():
    return {"reached": False, "rc": np.empty((0, 2), int), "t_walker": np.empty(0),
            "path_length_m": 0.0, "route_nodes": []}


def perturbed_sim(fx, ws_pert):
    s = fx["snaps"]
    return forward_simulate(fx["model"], fx["ev"], fx["hg"], fx["hstatic"],
                            s[0].cumulative_mask, s[0].time, ws_pert,
                            n_steps=fx["args"].n_steps, step_hours=fx["args"].step_hours,
                            advance_threshold=fx["args"].advance_threshold)


def git_commit() -> dict:
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO).decode().strip())
        return {"sha": sha, "dirty": dirty}
    except Exception as e:  # pragma: no cover
        return {"sha": None, "dirty": None, "error": str(e)}


def pct_stats(a):
    a = np.asarray(a, float)
    finite = a[np.isfinite(a)]
    n_pos_inf = int(np.sum(np.isposinf(a)))
    if finite.size == 0:
        return {"n": int(a.size), "n_pos_inf": n_pos_inf, "median": None}
    return {"n": int(a.size), "n_finite": int(finite.size), "n_pos_inf": n_pos_inf,
            "median": float(np.median(finite)),
            "iqr": [float(np.percentile(finite, 25)), float(np.percentile(finite, 75))],
            "p5": float(np.percentile(finite, 5)), "p95": float(np.percentile(finite, 95))}


# ---------------------------------------------------------------------------
# Ensemble A (input uncertainty) + replay
# ---------------------------------------------------------------------------
def run_ensemble_A(fx, cfg, K, rng):
    origins = fx["origins"]; N = len(origins)
    oidx = {n: i for i, n in enumerate(origins)}
    steps = np.asarray(fx["sim_hat"].step_minutes, float)
    rad = max(1, int(round(500.0 / fx["hg"].cell_size_m)))
    # margin arrays: [K, N] for each (route x arrival-method)
    M = {k: np.full((K, N), np.nan) for k in
         ("base_sub", "fa_sub", "base_raw", "fa_raw")}
    EXP = {k: np.full((K, N), np.nan) for k in ("base", "fa")}
    CAUGHT = {k: np.zeros((K, N), bool) for k in ("base_sub", "fa_sub")}
    draws = []
    t_arr_cache = {}      # realisation index -> t_sub field (for oracle subsample)
    coherence = []
    for k in range(K):
        d = P.draw_perturbation(rng, cfg)
        draws.append(d)
        ws_p = P.perturb_weather(fx["ws"], d, cfg)
        sim = perturbed_sim(fx, ws_p)
        t_sub, t_raw = arrival_fields(sim, threshold=fx["args"].p_cut)
        dmasks = dilated_masks(sim, fx["args"].p_cut, rad)
        t_arr_cache[k] = t_sub
        # spatial coherence diagnostic (final-step footprint components)
        if k < 3:
            from scipy.ndimage import label as _label
            fin = sim.hazard[-1] >= fx["args"].p_cut
            coherence.append(int(_label(fin)[1]))
        for n in origins:
            i = oidx[n]
            for kind, msub, mraw, mexp, mc in (
                ("baseline", "base_sub", "base_raw", "base", "base_sub"),
                ("forecast_aware", "fa_sub", "fa_raw", "fa", "fa_sub")):
                rec = fx["routes"][n][kind]
                if not rec["reached"]:
                    continue
                ms = route_margin(rec["rc"], rec["t_walker"], t_sub)
                mr = route_margin(rec["rc"], rec["t_walker"], t_raw)
                M[msub][k, i] = ms
                M[mraw][k, i] = mr
                CAUGHT[mc][k, i] = ms < 0
                EXP[mexp][k, i] = route_exposure_min(rec["rc"], rec["t_walker"], dmasks, steps)
    return dict(M=M, EXP=EXP, CAUGHT=CAUGHT, draws=draws, t_arr_cache=t_arr_cache,
                coherence=coherence, oidx=oidx)


def summarise_A(fx, A, K):
    origins = fx["origins"]; paired = fx["paired"]; oidx = A["oidx"]
    pj = np.array([oidx[n] for n in paired], int)
    res = {}
    for route, sub in (("baseline", "base_sub"), ("forecast_aware", "fa_sub")):
        res[route] = {"margin_min_sub": pct_stats(A["M"][sub].ravel()),
                      "caught_rate": float(np.nanmean(A["CAUGHT"][sub].astype(float)))}
    # delta_margin (paired origins) at both arrival resolutions
    out_delta = {}
    for tag, bkey, fkey in (("sub", "base_sub", "fa_sub"), ("raw", "base_raw", "fa_raw")):
        base = A["M"][bkey][:, pj]; fa = A["M"][fkey][:, pj]
        worse = fa < base                      # inf-safe comparison
        both = base - fa                        # not used directly
        delta = fa - base
        finite = delta[np.isfinite(delta)]
        out_delta[tag] = {
            "n_pairs_times_K": int(base.size),
            "P_delta_margin_lt_0": float(np.mean(worse)),
            "delta_finite": (pct_stats(finite) if finite.size else {"n": 0}),
        }
    return res, out_delta, pj


# ---------------------------------------------------------------------------
# Oracle (Tier 2): route on the binarised arrival field, score on the same
# ---------------------------------------------------------------------------
def run_oracle(fx, A, sub_indices):
    origins = fx["origins"]; oidx = A["oidx"]; N = len(origins)
    args = fx["args"]
    steps = np.asarray(fx["sim_hat"].step_minutes, float)
    K = len(sub_indices)
    m_oracle = np.full((K, N), np.nan)
    m_fa_on_same = np.full((K, N), np.nan)   # forecast_aware margin on same realisations
    dominance_viol = 0; dominance_tot = 0
    for j, kidx in enumerate(sub_indices):
        t_sub = A["t_arr_cache"][kidx]
        hz = ArrivalStepHazard(t_sub, fx["hg"], steps)
        for n in origins:
            i = oidx[n]
            orc = future_aware_route(fx["net"], n, hz, departure_min=0.0,
                                     time_budget_min=args.time_budget_min, p_cut=args.p_cut,
                                     time_step_min=args.time_step_min)
            if orc.reached and len(orc.route) > 0:
                xs = np.array([fx["net"].graph.nodes[m]["x"] for m in orc.route], float)
                ys = np.array([fx["net"].graph.nodes[m]["y"] for m in orc.route], float)
                rr, cc = cells_of(xs, ys, fx["hg"])
                rc = np.stack([rr, cc], axis=1)
                tw = np.asarray(orc.arrival_times_min, float)
                m_oracle[j, i] = route_margin(rc, tw, t_sub)
            farec = fx["routes"][n]["forecast_aware"]
            if farec["reached"]:
                mf = route_margin(farec["rc"], farec["t_walker"], t_sub)
                m_fa_on_same[j, i] = mf
                if np.isfinite(m_oracle[j, i]) and np.isfinite(mf):
                    dominance_tot += 1
                    if m_oracle[j, i] < mf - 1e-6:
                        dominance_viol += 1
    gap = m_oracle - m_fa_on_same
    return dict(m_oracle=m_oracle, m_fa_on_same=m_fa_on_same,
                oracle_gap=pct_stats(gap[np.isfinite(gap)]),
                dominance_violations=dominance_viol, dominance_pairs=dominance_tot,
                dominance_violation_rate=(dominance_viol / dominance_tot if dominance_tot else None))


# ---------------------------------------------------------------------------
# Ensemble B (model uncertainty): bootstrap-resample training fires
# ---------------------------------------------------------------------------
def run_ensemble_B(fx, K, rng):
    ds = fx["ds"]; args = fx["args"]
    train_fires = [f for f in sorted(ds["fire_id"].unique()) if f != FIRE]
    origins = fx["origins"]; paired = fx["paired"]
    oidx = {n: i for i, n in enumerate(origins)}
    N = len(origins)
    M = {k: np.full((K, N), np.nan) for k in ("base_sub", "fa_sub")}
    uniq_counts = []; n_failed = 0
    for k in range(K):
        sample = list(rng.choice(train_fires, size=len(train_fires), replace=True))
        uniq_counts.append(len(set(sample)))
        rows = pd.concat([ds[ds["fire_id"] == f] for f in sample], ignore_index=True)
        try:
            if rows["label"].nunique() < 2:
                raise ValueError("single-class bootstrap")
            model_b = IgnitionModelV2(seed=fx["seed"]).fit(rows)
        except Exception:
            n_failed += 1
            continue
        s = fx["snaps"]
        sim = forward_simulate(model_b, fx["ev"], fx["hg"], fx["hstatic"],
                               s[0].cumulative_mask, s[0].time, fx["ws"],
                               n_steps=args.n_steps, step_hours=args.step_hours,
                               advance_threshold=args.advance_threshold)
        t_sub, _ = arrival_fields(sim, threshold=args.p_cut)
        for n in origins:
            i = oidx[n]
            for kind, key in (("baseline", "base_sub"), ("forecast_aware", "fa_sub")):
                rec = fx["routes"][n][kind]
                if rec["reached"]:
                    M[key][k, i] = route_margin(rec["rc"], rec["t_walker"], t_sub)
    pj = np.array([oidx[n] for n in paired], int)
    base = M["base_sub"][:, pj]; fa = M["fa_sub"][:, pj]
    delta = fa - base; finite = delta[np.isfinite(delta)]
    from collections import Counter
    return dict(
        unique_fire_count_distribution=dict(sorted(Counter(uniq_counts).items())),
        n_failed_fits=n_failed, K_effective=K - n_failed,
        P_delta_margin_lt_0=float(np.mean(fa < base)),
        delta_finite=(pct_stats(finite) if finite.size else {"n": 0}),
        margin_baseline=pct_stats(M["base_sub"].ravel()),
        margin_forecast_aware=pct_stats(M["fa_sub"].ravel()))


# ---------------------------------------------------------------------------
# distance-to-shelter quartile breakdown of delta_margin (Ensemble A, sub)
# ---------------------------------------------------------------------------
def quartile_breakdown(fx, A, pj):
    paired = fx["paired"]
    d2s = np.array([fx["routes"][n]["dist_to_shelter_m"] for n in paired], float)
    qs = np.percentile(d2s, [25, 50, 75])
    bands = np.digitize(d2s, qs)   # 0..3
    base = A["M"]["base_sub"][:, pj]; fa = A["M"]["fa_sub"][:, pj]
    out = {}
    for b in range(4):
        cols = np.where(bands == b)[0]
        if cols.size == 0:
            continue
        bb = base[:, cols]; ff = fa[:, cols]
        delta = ff - bb; finite = delta[np.isfinite(delta)]
        out[f"q{b+1}"] = {"n_origins": int(cols.size),
                          "dist_to_shelter_m_range": [float(d2s[cols].min()), float(d2s[cols].max())],
                          "P_delta_margin_lt_0": float(np.mean(ff < bb)),
                          "delta_finite": (pct_stats(finite) if finite.size else {"n": 0})}
    return {"quartile_edges_m": [float(x) for x in qs], "bands": out}


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--hazard-cell-m", type=float, default=500.0, dest="hazard_cell_m")
    ap.add_argument("--route-cell-m", type=float, default=750.0, dest="route_cell_m")
    ap.add_argument("--n-steps", type=int, default=4, dest="n_steps")
    ap.add_argument("--step-hours", type=float, default=3.0, dest="step_hours")
    ap.add_argument("--advance-threshold", type=float, default=0.3, dest="advance_threshold")
    ap.add_argument("--p-cut", type=float, default=0.5, dest="p_cut")
    ap.add_argument("--time-budget-min", type=float, default=600.0, dest="time_budget_min")
    ap.add_argument("--time-step-min", type=float, default=10.0, dest="time_step_min")
    ap.add_argument("--scan-stride", type=int, default=4, dest="scan_stride")
    ap.add_argument("--K-a", type=int, default=500, dest="K_a")
    ap.add_argument("--K-oracle", type=int, default=50, dest="K_oracle")
    ap.add_argument("--K-b", type=int, default=100, dest="K_b")
    ap.add_argument("--tier", type=int, default=3)
    ap.add_argument("--pilot", type=int, default=0, help="if >0, run only K=pilot Ensemble A for timing")
    ap.add_argument("--skip-gate", action="store_true", dest="skip_gate")
    ap.add_argument("--out", default=str(REPO / "data" / "processed"))
    ap.add_argument("--tag", default="")
    # resumable checkpoint harness (for the 45s/command sandbox cap)
    ap.add_argument("--resume-dir", default="", dest="resume_dir",
                    help="checkpoint dir; when set, run the resumable state machine")
    ap.add_argument("--budget-sec", type=float, default=38.0, dest="budget_sec")
    ap.add_argument("--outfile", default="", help="output json filename")
    ap.add_argument("--quarantine", action="store_true",
                    help="mark output REPORTABLE=false")
    ap.add_argument("--reason", default="", help="quarantine reason string")
    args = ap.parse_args()

    if not data.data_available():
        print("FIRMS/ERA5/DEM bundle not found; aborting.", file=sys.stderr)
        return 2

    t0 = time.time()
    cfg = P.load_config()

    if args.resume_dir:
        return run_resumable(args, cfg)

    fx = build_fixed(args)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    # ---- pilot: time Ensemble A only ----
    if args.pilot > 0:
        rng = np.random.default_rng(args.seed + 1)
        tA = time.time()
        A = run_ensemble_A(fx, cfg, args.pilot, rng)
        per = (time.time() - tA) / args.pilot
        print(f"\n[PILOT] Ensemble A: {args.pilot} realisations in {time.time()-tA:.1f}s "
              f"=> {per:.2f}s/realisation", flush=True)
        print(f"[PILOT] projected Ensemble A K=500: {per*500/60:.1f} min", flush=True)
        print(f"[PILOT] coherence (components, first 3): {A['coherence']}", flush=True)
        # quick oracle timing on 2 realisations
        tO = time.time()
        _ = run_oracle(fx, A, list(A['t_arr_cache'].keys())[:2])
        per_o = (time.time() - tO) / 2
        print(f"[PILOT] oracle: {per_o:.1f}s/realisation "
              f"=> projected K=50: {per_o*50/60:.1f} min", flush=True)
        print(f"[PILOT] N_origins={len(fx['origins'])} paired={len(fx['paired'])} "
              f"base_fail={fx['n_base_fail']} fa_fail={fx['n_fa_fail']}", flush=True)
        return 0

    result = {
        "model_id": "spread_v2", "seed": args.seed, "fire": FIRE,
        "n_origins": len(fx["origins"]), "n_paired": len(fx["paired"]),
        "baseline_unreached": fx["n_base_fail"], "forecast_aware_no_route": fx["n_fa_fail"],
        "binarisation_threshold": args.p_cut,
        "binarisation_threshold_source":
            "footprint_iou_lofo(threshold=args.p_cut) in run_routing_integration.py; "
            "--p-cut default 0.5 (same value as the router impassable cutoff)",
        "routing_time_step_min": args.time_step_min,
        "hazard_forecast_step_min": args.step_hours * 60.0,
        "arrival_time_primary": "front_distance_substep_interpolation",
        "arrival_time_sensitivity": "raw_180min_step_boundary",
        "config_mc_perturbation": cfg,
        "git_commit": git_commit(),
        "gate": fx["gate"],
        "scan_stride": args.scan_stride,
    }

    # ---- Tier 1 ----
    rng = np.random.default_rng(args.seed + 1)
    print(f"\n[Tier 1] Ensemble A K={args.K_a} ...", flush=True)
    tA = time.time()
    A = run_ensemble_A(fx, cfg, args.K_a, rng)
    result["runtime_ensemble_A_sec"] = round(time.time() - tA, 1)
    res_routes, delta, pj = summarise_A(fx, A, args.K_a)
    result["K_ensemble_A"] = args.K_a
    result["margins"] = res_routes
    result["delta_margin"] = delta
    result["spatial_coherence_components_first3"] = A["coherence"]

    # sanity check 2: degenerate ensemble (enabled=false => identity)
    print("[Tier 1] sanity check 2 (degenerate ensemble) ...", flush=True)
    cfg_off = json.loads(json.dumps(cfg)); cfg_off["enabled"] = False
    d0 = P.draw_perturbation(np.random.default_rng(0), cfg_off)
    ws0 = P.perturb_weather(fx["ws"], d0, cfg_off)
    ws_identical = all(np.array_equal(getattr(fx["ws"], f), getattr(ws0, f)) for f in
                       ("wind_speed_ms", "wind_toward_deg", "wind_u", "wind_v", "temp_c",
                        "rh_pct", "vpd_kpa", "days_since_rain", "precip_24h_mm"))
    sim0 = perturbed_sim(fx, ws0)
    haz_identical = all(np.array_equal(a, b) for a, b in zip(sim0.hazard, fx["sim_hat"].hazard))
    t_sub0, _ = arrival_fields(sim0, threshold=args.p_cut)
    # oracle vs forecast_aware exact equality on the degenerate realisation
    hz0 = ArrivalStepHazard(t_sub0, fx["hg"], np.asarray(fx["sim_hat"].step_minutes, float))
    eq = 0; tot = 0
    for n in fx["paired"][:60]:
        orc = future_aware_route(fx["net"], n, hz0, departure_min=0.0,
                                 time_budget_min=args.time_budget_min, p_cut=args.p_cut,
                                 time_step_min=args.time_step_min)
        fare = fx["routes"][n]["forecast_aware"]
        if orc.reached:
            xs = np.array([fx["net"].graph.nodes[m]["x"] for m in orc.route], float)
            ys = np.array([fx["net"].graph.nodes[m]["y"] for m in orc.route], float)
            rr, cc = cells_of(xs, ys, fx["hg"])
            mo = route_margin(np.stack([rr, cc], 1), np.asarray(orc.arrival_times_min, float), t_sub0)
            mf = route_margin(fare["rc"], fare["t_walker"], t_sub0)
            tot += 1
            if (np.isinf(mo) and np.isinf(mf)) or abs(mo - mf) < 1e-6:
                eq += 1
    result["sanity_check_2_degenerate"] = {
        "weather_identical_to_f_hat": bool(ws_identical),
        "hazard_identical_to_f_hat": bool(haz_identical),
        "oracle_eq_forecast_aware_frac": (eq / tot if tot else None),
        "n_checked": tot,
        "note": "enabled=false hard-disables every channel; f_hat must be reproduced exactly."}

    # sanity check 4: timestep alignment worked example
    n0 = fx["paired"][0]
    fare = fx["routes"][n0]["forecast_aware"]
    ex_k = 0
    t_sub_ex = A["t_arr_cache"][ex_k]
    ta = t_sub_ex[fare["rc"][:, 0], fare["rc"][:, 1]]
    j = int(np.argmin(ta - fare["t_walker"]))
    result["sanity_check_4_alignment"] = {
        "origin_node": int(n0), "realisation_index": ex_k,
        "clock": "minutes from forward-sim t0 = first overpass = departure_min(0); "
                 "t_walker and t_arrival share this zero",
        "binding_node_index_on_route": j,
        "t_walker_min": float(fare["t_walker"][j]),
        "t_arrival_min": (None if not np.isfinite(ta[j]) else float(ta[j])),
        "margin_at_binding_node_min": float(ta[j] - fare["t_walker"][j]),
        "route_margin_min": route_margin(fare["rc"], fare["t_walker"], t_sub_ex)}

    # ---- Tier 2: oracle ----
    if args.tier >= 2:
        print(f"\n[Tier 2] oracle K={args.K_oracle} ...", flush=True)
        sub_rng = np.random.default_rng(args.seed + 2)
        avail = list(A["t_arr_cache"].keys())
        Ko = min(args.K_oracle, len(avail))
        sub_idx = sorted(sub_rng.choice(avail, size=Ko, replace=False).tolist())
        tO = time.time()
        orc = run_oracle(fx, A, sub_idx)
        result["runtime_oracle_sec"] = round(time.time() - tO, 1)
        result["K_oracle"] = Ko
        result["oracle_subsample_indices"] = sub_idx
        result["oracle_gap"] = orc["oracle_gap"]
        result["method_value_note"] = "method value = margin(forecast_aware) - margin(baseline) = delta_margin above"
        result["sanity_check_1_oracle_dominance"] = {
            "violations": orc["dominance_violations"], "pairs": orc["dominance_pairs"],
            "violation_rate": orc["dominance_violation_rate"],
            "note": "oracle routed AND scored on the binarised arrival field; violations above ~1% indicate a bug"}

    # ---- Tier 3: Ensemble B + quartile breakdown ----
    if args.tier >= 3:
        print(f"\n[Tier 3] Ensemble B K={args.K_b} (bootstrap over training fires) ...", flush=True)
        rng_b = np.random.default_rng(args.seed + 3)
        tB = time.time()
        B = run_ensemble_B(fx, args.K_b, rng_b)
        result["runtime_ensemble_B_sec"] = round(time.time() - tB, 1)
        result["K_ensemble_B"] = args.K_b
        result["ensemble_B"] = B
        result["delta_margin_by_distance_quartile"] = quartile_breakdown(fx, A, pj)
        result["sanity_check_3_spatial_coherence"] = {
            "components_first3_realisations": A["coherence"],
            "note": "hundreds of components would indicate accidental per-cell Bernoulli sampling"}

    result["runtime_seconds"] = round(time.time() - t0, 1)

    # ---- write outputs ----
    tag = ("_" + args.tag) if args.tag else ""
    jpath = out / f"routing_monte_carlo{tag}.json"
    jpath.write_text(json.dumps(result, indent=2, default=str))
    # raw per-realisation margins (Ensemble A) to npz
    np.savez_compressed(
        out / f"routing_mc_raw{tag}.npz",
        origins=np.array(fx["origins"], int),
        paired=np.array(fx["paired"], int),
        A_base_sub=A["M"]["base_sub"], A_fa_sub=A["M"]["fa_sub"],
        A_base_raw=A["M"]["base_raw"], A_fa_raw=A["M"]["fa_raw"])
    print(f"\ndone in {result['runtime_seconds']}s. wrote {jpath.name} + routing_mc_raw{tag}.npz", flush=True)
    return 0


# ===========================================================================
# Resumable checkpoint harness (sandbox caps each command at ~45s and kills
# spawned processes on return, so work is done in bounded chunks across calls).
# Per-realisation seeding (default_rng([seed, k])) makes every chunk reproducible
# and order-independent; oracle re-derives its realisations from the same seeds
# instead of caching large fields.
# ===========================================================================
import pickle  # noqa: E402


def _ensA_realisation(fx, cfg, k, base_seed):
    rng = np.random.default_rng([base_seed, k])
    d = P.draw_perturbation(rng, cfg)
    ws_p = P.perturb_weather(fx["ws"], d, cfg)
    sim = perturbed_sim(fx, ws_p)
    t_sub, t_raw = arrival_fields(sim, fx["args"].p_cut)
    rad = max(1, int(round(500.0 / fx["hg"].cell_size_m)))
    dmasks = dilated_masks(sim, fx["args"].p_cut, rad)
    steps = np.asarray(fx["sim_hat"].step_minutes, float)
    N = len(fx["origins"])
    keys = ("base_sub", "fa_sub", "base_raw", "fa_raw", "exp_base", "exp_fa")
    out = {kk: np.full(N, np.nan) for kk in keys}
    for i, n in enumerate(fx["origins"]):
        for kind, ks, kr, ke in (("baseline", "base_sub", "base_raw", "exp_base"),
                                 ("forecast_aware", "fa_sub", "fa_raw", "exp_fa")):
            rec = fx["routes"][n][kind]
            if not rec["reached"]:
                continue
            out[ks][i] = route_margin(rec["rc"], rec["t_walker"], t_sub)
            out[kr][i] = route_margin(rec["rc"], rec["t_walker"], t_raw)
            out[ke][i] = route_exposure_min(rec["rc"], rec["t_walker"], dmasks, steps)
    comp = None
    if k < 3:
        from scipy.ndimage import label as _label
        comp = int(_label(sim.hazard[-1] >= fx["args"].p_cut)[1])
    return out, comp


def _oracle_realisation(fx, cfg, k, base_seed):
    rng = np.random.default_rng([base_seed, k])
    d = P.draw_perturbation(rng, cfg)
    ws_p = P.perturb_weather(fx["ws"], d, cfg)
    sim = perturbed_sim(fx, ws_p)
    t_sub, _ = arrival_fields(sim, fx["args"].p_cut)
    hz = ArrivalStepHazard(t_sub, fx["hg"], np.asarray(fx["sim_hat"].step_minutes, float))
    args = fx["args"]
    N = len(fx["origins"])
    mo = np.full(N, np.nan)
    mf = np.full(N, np.nan)
    for i, n in enumerate(fx["origins"]):
        orc = future_aware_route(fx["net"], n, hz, departure_min=0.0,
                                 time_budget_min=args.time_budget_min, p_cut=args.p_cut,
                                 time_step_min=args.time_step_min)
        if orc.reached and len(orc.route) > 0:
            xs = np.array([fx["net"].graph.nodes[m]["x"] for m in orc.route], float)
            ys = np.array([fx["net"].graph.nodes[m]["y"] for m in orc.route], float)
            rr, cc = cells_of(xs, ys, fx["hg"])
            mo[i] = route_margin(np.stack([rr, cc], 1), np.asarray(orc.arrival_times_min, float), t_sub)
        fare = fx["routes"][fx["origins"][i]]["forecast_aware"]
        if fare["reached"]:
            mf[i] = route_margin(fare["rc"], fare["t_walker"], t_sub)
    return mo, mf


def _ensB_realisation(fx, ds, k, base_seed):
    rng = np.random.default_rng([base_seed, k])
    train = [f for f in sorted(ds["fire_id"].unique()) if f != FIRE]
    sample = list(rng.choice(train, size=len(train), replace=True))
    uniq = len(set(sample))
    rows = pd.concat([ds[ds["fire_id"] == f] for f in sample], ignore_index=True)
    N = len(fx["origins"])
    if rows["label"].nunique() < 2:
        return None, uniq
    try:
        mb = IgnitionModelV2(seed=fx["seed"]).fit(rows)
    except Exception:
        return None, uniq
    s = fx["snaps"]
    sim = forward_simulate(mb, fx["ev"], fx["hg"], fx["hstatic"], s[0].cumulative_mask, s[0].time,
                           fx["ws"], n_steps=fx["args"].n_steps, step_hours=fx["args"].step_hours,
                           advance_threshold=fx["args"].advance_threshold)
    t_sub, _ = arrival_fields(sim, fx["args"].p_cut)
    bs = np.full(N, np.nan)
    fs = np.full(N, np.nan)
    for i, n in enumerate(fx["origins"]):
        for kind, arr in (("baseline", bs), ("forecast_aware", fs)):
            rec = fx["routes"][n][kind]
            if rec["reached"]:
                arr[i] = route_margin(rec["rc"], rec["t_walker"], t_sub)
    return (bs, fs), uniq


def get_fixed(args, cdir):
    fp = cdir / "fixed.pkl"
    if fp.exists():
        fx = pickle.load(open(fp, "rb"))
        fx["args"] = args
        return fx
    fx = build_fixed(args)
    ds = fx.pop("ds")
    ds.to_pickle(cdir / "ds.pkl")
    pickle.dump(fx, open(fp, "wb"))
    fx["ds"] = ds
    return fx


def run_resumable(args, cfg):
    cdir = Path(args.resume_dir)
    cdir.mkdir(parents=True, exist_ok=True)
    budget = args.budget_sec
    t0 = time.time()
    fx = get_fixed(args, cdir)

    def _pickle_fx():
        pickle.dump({k: v for k, v in fx.items() if k != "ds"}, open(cdir / "fixed.pkl", "wb"))

    # ---- stage FA (forecast_aware routes on f_hat, resumable) ----
    if not fx.get("fa_done"):
        origins = fx["origins"]
        fa_i = fx.get("fa_idx", 0)
        while fa_i < len(origins):
            n = origins[fa_i]
            fa = future_aware_route(fx["net"], n, fx["f_hat"], departure_min=0.0,
                                    time_budget_min=args.time_budget_min, p_cut=args.p_cut,
                                    time_step_min=args.time_step_min)
            fx["routes"][n]["forecast_aware"] = (
                _route_rec(fx["net"], fx["hg"], fa.route)
                if (fa.reached and len(fa.route) > 0) else _empty_rec())
            fa_i += 1
            if time.time() - t0 > budget:
                fx["fa_idx"] = fa_i
                _pickle_fx()
                print(f"[resume] stage FA: {fa_i}/{len(origins)} done "
                      f"(+{time.time()-t0:.0f}s this call)", flush=True)
                return
        fx["fa_idx"] = len(origins)
        fx["fa_done"] = True
        fx["n_fa_fail"] = int(sum(not fx["routes"][n]["forecast_aware"]["reached"] for n in origins))
        fx["paired"] = [n for n in origins if fx["routes"][n]["baseline"]["reached"]
                        and fx["routes"][n]["forecast_aware"]["reached"]]
        _pickle_fx()
        print(f"[resume] stage FA complete: n_fa_fail={fx['n_fa_fail']} "
              f"paired={len(fx['paired'])}", flush=True)

    N = len(fx["origins"])
    sp = cdir / "state.pkl"
    if sp.exists():
        st = pickle.load(open(sp, "rb"))
    else:
        st = {
            "stage": "A", "t_fixed_done": True,
            "A": {"done": np.zeros(args.K_a, bool), "coherence": [],
                  **{kk: np.full((args.K_a, N), np.nan) for kk in
                     ("base_sub", "fa_sub", "base_raw", "fa_raw", "exp_base", "exp_fa")}},
            "O": {"sub_idx": None, "done": None, "m_oracle": None, "m_fa": None},
            "B": {"done": np.zeros(args.K_b, bool), "uniq": [], "failed": 0,
                  "base_sub": np.full((args.K_b, N), np.nan),
                  "fa_sub": np.full((args.K_b, N), np.nan)},
            "runtime_A": 0.0, "runtime_O": 0.0, "runtime_B": 0.0,
        }

    def save():
        pickle.dump(st, open(sp, "wb"))

    # ---- stage A ----
    if st["stage"] == "A":
        for k in range(args.K_a):
            if st["A"]["done"][k]:
                continue
            out, comp = _ensA_realisation(fx, cfg, k, args.seed + 1)
            for kk in ("base_sub", "fa_sub", "base_raw", "fa_raw", "exp_base", "exp_fa"):
                st["A"][kk][k] = out[kk]
            if comp is not None:
                st["A"]["coherence"].append(comp)
            st["A"]["done"][k] = True
            st["runtime_A"] += 0  # wall added below
            if time.time() - t0 > budget:
                st["runtime_A"] += time.time() - t0
                save()
                print(f"[resume] stage A: {int(st['A']['done'].sum())}/{args.K_a} done "
                      f"(+{time.time()-t0:.0f}s this call)", flush=True)
                return
        st["runtime_A"] += time.time() - t0
        st["stage"] = "O" if args.tier >= 2 else "FINALIZE"
        save()

    tO0 = time.time()
    # ---- stage O (oracle) ----
    if st["stage"] == "O":
        if st["O"]["sub_idx"] is None:
            sub_rng = np.random.default_rng(args.seed + 2)
            Ko = min(args.K_oracle, args.K_a)
            st["O"]["sub_idx"] = sorted(sub_rng.choice(args.K_a, size=Ko, replace=False).tolist())
            st["O"]["done"] = np.zeros(Ko, bool)
            st["O"]["m_oracle"] = np.full((Ko, N), np.nan)
            st["O"]["m_fa"] = np.full((Ko, N), np.nan)
            save()
        for j, k in enumerate(st["O"]["sub_idx"]):
            if st["O"]["done"][j]:
                continue
            mo, mf = _oracle_realisation(fx, cfg, k, args.seed + 1)
            st["O"]["m_oracle"][j] = mo
            st["O"]["m_fa"][j] = mf
            st["O"]["done"][j] = True
            if time.time() - t0 > budget:
                st["runtime_O"] += time.time() - tO0
                save()
                print(f"[resume] stage O: {int(st['O']['done'].sum())}/{len(st['O']['sub_idx'])} done "
                      f"(+{time.time()-t0:.0f}s this call)", flush=True)
                return
        st["runtime_O"] += time.time() - tO0
        st["stage"] = "B" if args.tier >= 3 else "FINALIZE"
        save()

    tB0 = time.time()
    # ---- stage B (ensemble B) ----
    if st["stage"] == "B":
        ds = pd.read_pickle(cdir / "ds.pkl")
        for k in range(args.K_b):
            if st["B"]["done"][k]:
                continue
            res, uniq = _ensB_realisation(fx, ds, k, args.seed + 3)
            st["B"]["uniq"].append(int(uniq))
            if res is None:
                st["B"]["failed"] += 1
            else:
                st["B"]["base_sub"][k] = res[0]
                st["B"]["fa_sub"][k] = res[1]
            st["B"]["done"][k] = True
            if time.time() - t0 > budget:
                st["runtime_B"] += time.time() - tB0
                save()
                print(f"[resume] stage B: {int(st['B']['done'].sum())}/{args.K_b} done "
                      f"(+{time.time()-t0:.0f}s this call)", flush=True)
                return
        st["runtime_B"] += time.time() - tB0
        st["stage"] = "FINALIZE"
        save()

    # ---- finalize ----
    if st["stage"] == "FINALIZE":
        _finalize_resumable(fx, st, args, cfg, cdir)
        print("[resume] FINALIZE complete", flush=True)
    return


def _finalize_resumable(fx, st, args, cfg, cdir):
    origins = fx["origins"]
    paired = fx["paired"]
    oidx = {n: i for i, n in enumerate(origins)}
    pj = np.array([oidx[n] for n in paired], int)
    A = st["A"]

    def delta_block(base, fa):
        worse = fa < base
        with np.errstate(invalid="ignore"):   # inf - inf (both non-exposed) -> nan, filtered below
            delta = fa - base
        finite = delta[np.isfinite(delta)]
        return {"n_pairs_times_K": int(base.size),
                "P_delta_margin_lt_0": float(np.mean(worse)),
                "delta_finite": (pct_stats(finite) if finite.size else {"n": 0})}

    result = {
        "REPORTABLE": (not args.quarantine),
        "reason": (args.reason or None),
        "model_id": "spread_v2", "seed": args.seed, "fire": FIRE,
        "n_origins": len(origins), "n_paired": len(paired),
        "baseline_unreached": fx["n_base_fail"], "forecast_aware_no_route": fx["n_fa_fail"],
        "binarisation_threshold": args.p_cut,
        "binarisation_threshold_source":
            "footprint_iou_lofo(threshold=args.p_cut); --p-cut default 0.5 (== router impassable cutoff)",
        "routing_time_step_min": args.time_step_min,
        "hazard_forecast_step_min": args.step_hours * 60.0,
        "arrival_time_primary": "front_distance_substep_interpolation",
        "arrival_time_sensitivity": "raw_180min_step_boundary",
        "config_mc_perturbation": cfg,
        "git_commit": git_commit(),
        "gate": fx["gate"],
        "scan_stride": args.scan_stride,
        "K_ensemble_A": args.K_a,
        "runtime_seconds": {"ensemble_A": round(st["runtime_A"], 1),
                            "oracle": round(st["runtime_O"], 1),
                            "ensemble_B": round(st["runtime_B"], 1)},
        "spatial_coherence_components_first3": A["coherence"],
        "sanity_check_3_spatial_coherence": {
            "components_first3_realisations": A["coherence"],
            "f_hat_components": int(_ndlabel(fx["sim_hat"].hazard[-1] >= args.p_cut)[1]),
            "f_hat_burned_cells": int((fx["sim_hat"].hazard[-1] >= args.p_cut).sum()),
            "grid_shape": list(fx["sim_hat"].hazard[-1].shape),
            "note": "Compare realisation component counts to f_hat_components: if they match, the "
                    "fragmentation is a property of the spread_v2 footprint at this threshold (NOT "
                    "per-cell Bernoulli sampling, which is independently ruled out by sanity check 2 "
                    "reproducing f_hat exactly). Per-cell Bernoulli would give realisation counts far "
                    "ABOVE f_hat's."},
    }
    # margins per route + delta (both resolutions)
    result["margins"] = {
        "baseline": {"margin_min_sub": pct_stats(A["base_sub"].ravel()),
                     "caught_rate": float(np.nanmean((A["base_sub"] < 0).astype(float)))},
        "forecast_aware": {"margin_min_sub": pct_stats(A["fa_sub"].ravel()),
                           "caught_rate": float(np.nanmean((A["fa_sub"] < 0).astype(float)))},
    }
    result["delta_margin"] = {
        "sub": delta_block(A["base_sub"][:, pj], A["fa_sub"][:, pj]),
        "raw": delta_block(A["base_raw"][:, pj], A["fa_raw"][:, pj]),
    }

    # sanity check 2 (degenerate ensemble) + sanity check 4 (alignment)
    cfg_off = json.loads(json.dumps(cfg)); cfg_off["enabled"] = False
    d0 = P.draw_perturbation(np.random.default_rng(0), cfg_off)
    ws0 = P.perturb_weather(fx["ws"], d0, cfg_off)
    ws_identical = all(np.array_equal(getattr(fx["ws"], f), getattr(ws0, f)) for f in
                       ("wind_speed_ms", "wind_toward_deg", "wind_u", "wind_v", "temp_c",
                        "rh_pct", "vpd_kpa", "days_since_rain", "precip_24h_mm"))
    sim0 = perturbed_sim(fx, ws0)
    haz_identical = all(np.array_equal(a, b) for a, b in zip(sim0.hazard, fx["sim_hat"].hazard))
    t_sub0, _ = arrival_fields(sim0, threshold=args.p_cut)
    hz0 = ArrivalStepHazard(t_sub0, fx["hg"], np.asarray(fx["sim_hat"].step_minutes, float))
    eq = tot = 0
    for n in paired[:60]:
        orc = future_aware_route(fx["net"], n, hz0, departure_min=0.0,
                                 time_budget_min=args.time_budget_min, p_cut=args.p_cut,
                                 time_step_min=args.time_step_min)
        fare = fx["routes"][n]["forecast_aware"]
        if orc.reached:
            xs = np.array([fx["net"].graph.nodes[m]["x"] for m in orc.route], float)
            ys = np.array([fx["net"].graph.nodes[m]["y"] for m in orc.route], float)
            rr, cc = cells_of(xs, ys, fx["hg"])
            mo = route_margin(np.stack([rr, cc], 1), np.asarray(orc.arrival_times_min, float), t_sub0)
            mf = route_margin(fare["rc"], fare["t_walker"], t_sub0)
            tot += 1
            if (np.isinf(mo) and np.isinf(mf)) or abs(mo - mf) < 1e-6:
                eq += 1
    result["sanity_check_2_degenerate"] = {
        "weather_identical_to_f_hat": bool(ws_identical),
        "hazard_identical_to_f_hat": bool(haz_identical),
        "oracle_eq_forecast_aware_frac": (eq / tot if tot else None), "n_checked": tot}

    rng0 = np.random.default_rng([args.seed + 1, 0])
    d = P.draw_perturbation(rng0, cfg)
    sim_ex = perturbed_sim(fx, P.perturb_weather(fx["ws"], d, cfg))
    t_sub_ex, _ = arrival_fields(sim_ex, args.p_cut)
    # pick an origin whose forecast_aware route is actually fire-exposed (finite
    # margin) so the worked example shows both clocks with real numbers.
    n0 = paired[0]
    for cand in paired:
        rec_c = fx["routes"][cand]["forecast_aware"]
        m_c = route_margin(rec_c["rc"], rec_c["t_walker"], t_sub_ex)
        if np.isfinite(m_c):
            n0 = cand
            break
    fare = fx["routes"][n0]["forecast_aware"]
    ta = t_sub_ex[fare["rc"][:, 0], fare["rc"][:, 1]]
    jb = int(np.argmin(ta - fare["t_walker"]))
    result["sanity_check_4_alignment"] = {
        "origin_node": int(n0), "realisation_index": 0,
        "clock": "minutes from forward-sim t0 = first overpass = departure(0); "
                 "t_walker and t_arrival share this zero",
        "binding_node_index_on_route": jb,
        "t_walker_min": float(fare["t_walker"][jb]),
        "t_arrival_min": (None if not np.isfinite(ta[jb]) else float(ta[jb])),
        "margin_at_binding_node_min": float(ta[jb] - fare["t_walker"][jb]),
        "route_margin_min": route_margin(fare["rc"], fare["t_walker"], t_sub_ex)}

    # oracle (if run)
    if args.tier >= 2 and st["O"]["sub_idx"] is not None:
        mo = st["O"]["m_oracle"]; mf = st["O"]["m_fa"]
        both = np.isfinite(mo) & np.isfinite(mf)
        viol = int(np.sum(mo[both] < mf[both] - 1e-6)); pairs = int(both.sum())
        with np.errstate(invalid="ignore"):
            gap = (mo - mf)
        gap = gap[np.isfinite(gap)]
        oracle_caught = int(np.sum(mo[np.isfinite(mo)] < 0))
        fa_caught = int(np.sum(mf[np.isfinite(mf)] < 0))
        result["K_oracle"] = len(st["O"]["sub_idx"])
        result["oracle_subsample_indices"] = st["O"]["sub_idx"]
        result["oracle_gap"] = pct_stats(gap)
        result["sanity_check_1_oracle_dominance"] = {
            "margin_violations": viol, "pairs": pairs,
            "margin_violation_rate": (viol / pairs if pairs else None),
            "oracle_caught_count": oracle_caught, "oracle_finite": int(np.isfinite(mo).sum()),
            "forecast_aware_caught_count": fa_caught, "fa_finite": int(np.isfinite(mf).sum()),
            "note": "MARGIN-dominance is NOT expected to hold: future_aware_route minimises "
                    "cumulative EXPOSURE with an earliest-arrival tie-break, not the clearance "
                    "MARGIN. So the exposure-oracle can clear the fire with a smaller (still "
                    "positive) margin than forecast_aware. The dominance that DOES hold is on "
                    "caught-rate: the oracle is never caught (oracle_caught_count should be 0) "
                    "while forecast_aware sometimes is. A true margin-oracle would need a maximin "
                    "(bottleneck) router, which is a design choice flagged for review."}

    # ensemble B (if run)
    if args.tier >= 3 and int(st["B"]["done"].sum()) > 0:
        from collections import Counter
        base = st["B"]["base_sub"][:, pj]; fa = st["B"]["fa_sub"][:, pj]
        with np.errstate(invalid="ignore"):
            delta = fa - base
        finite = delta[np.isfinite(delta)]
        result["K_ensemble_B"] = args.K_b
        result["ensemble_B"] = {
            "unique_fire_count_distribution": dict(sorted(Counter(st["B"]["uniq"]).items())),
            "n_failed_fits": st["B"]["failed"], "K_effective": args.K_b - st["B"]["failed"],
            "P_delta_margin_lt_0": float(np.mean(fa < base)),
            "delta_finite": (pct_stats(finite) if finite.size else {"n": 0})}
        # distance quartile breakdown (Ensemble A, sub)
        d2s = np.array([fx["routes"][n]["dist_to_shelter_m"] for n in paired], float)
        qs = np.percentile(d2s, [25, 50, 75]); bands = np.digitize(d2s, qs)
        Ab = A["base_sub"][:, pj]; Af = A["fa_sub"][:, pj]
        qout = {}
        for b in range(4):
            cols = np.where(bands == b)[0]
            if cols.size == 0:
                continue
            bb = Ab[:, cols]; ff = Af[:, cols]
            with np.errstate(invalid="ignore"):
                dl = ff - bb
            fin = dl[np.isfinite(dl)]
            qout[f"q{b+1}"] = {"n_origins": int(cols.size),
                               "P_delta_margin_lt_0": float(np.mean(ff < bb)),
                               "delta_finite": (pct_stats(fin) if fin.size else {"n": 0})}
        result["delta_margin_by_distance_quartile"] = {"quartile_edges_m": [float(x) for x in qs], "bands": qout}

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    fname = args.outfile or "routing_monte_carlo.json"
    (out / fname).write_text(json.dumps(result, indent=2, default=str))
    np.savez_compressed(out / (fname.replace(".json", "") + "_raw.npz"),
                        origins=np.array(origins, int), paired=np.array(paired, int),
                        A_base_sub=A["base_sub"], A_fa_sub=A["fa_sub"],
                        A_base_raw=A["base_raw"], A_fa_raw=A["fa_raw"])
    print(f"[finalize] wrote {fname} (+ raw npz)", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
