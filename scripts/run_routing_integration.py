#!/usr/bin/env python
"""End-to-end routing-spine demonstration on the Yeongdeok 2025 fire.

Pipeline (all on REAL data; Yeongdeok is held out of model training so its
hazard is genuinely out-of-sample):

  1. Build the spread_v2 dataset across all fires; run leave-one-fire-out
     validation (AUC, far-band AUC, permutation importance, footprint IoU).
  2. Train the final model on every fire EXCEPT Yeongdeok; forward-simulate
     the Yeongdeok hazard from its first observed overpass; quantify drift.
  3. Build the evacuation network on the real Yeongdeok extent; scan origins
     for the headline contrast (naive walks into the future reach; future-
     aware detours); also surface a "no safe route" origin.
  4. Dump metrics (JSON) and arrays (NPZ) for the figure script + report.

Run:  python scripts/run_routing_integration.py
Outputs under data/processed/ (git-ignored bulk; small JSON summaries kept).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from pyproj import Transformer

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.spread_v2 import data, features, grid as gridmod  # noqa: E402
from wildfireguardian.spread_v2.features import StaticLayers  # noqa: E402
from wildfireguardian.spread_v2.model import (  # noqa: E402
    DEFAULT_SEED,
    IgnitionModelV2,
    footprint_iou_lofo,
    leave_one_fire_out,
)
from wildfireguardian.spread_v2.forward_sim import (  # noqa: E402
    drift_vs_observed,
    envelope_breadth_deg,
    forward_simulate,
)
from wildfireguardian.spread_v2.weather import weather_series_from_event  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.routing.evacuation import (  # noqa: E402
    build_evacuation_network,
    future_aware_route,
    naive_route,
)

_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)


def _route_xy(net, route):
    return np.array([[net.graph.nodes[n]["x"], net.graph.nodes[n]["y"]] for n in route], float)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fire", default="yeongdeok_2025")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--hazard-cell-m", type=float, default=500.0)
    ap.add_argument("--route-cell-m", type=float, default=750.0)
    # 3 h steps sit inside the model's real overpass-gap training range
    # (~3-12 h); shorter steps extrapolate the dt_hours feature below that
    # range and the envelope barely grows. The HazardSequence interpolates
    # between these surfaces for the finer-grained routing clock.
    ap.add_argument("--n-steps", type=int, default=4)
    ap.add_argument("--step-hours", type=float, default=3.0)
    ap.add_argument("--advance-threshold", type=float, default=0.3)
    ap.add_argument("--p-cut", type=float, default=0.5)
    ap.add_argument("--time-budget-min", type=float, default=600.0)
    ap.add_argument("--time-step-min", type=float, default=10.0)
    ap.add_argument("--scan-stride", type=int, default=4, help="sub-sample stride for the origin scan")
    ap.add_argument("--out", default=str(REPO / "data" / "processed"))
    args = ap.parse_args()

    if not data.data_available():
        print("FIRMS dataset not found; set $WFG_FIRMS_DIR or unzip firms_data.zip "
              "into data/raw/firms/. Aborting.", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    fire_ids = [m.id for m in data.list_fires()]

    # ---- 1. dataset + LOFO -------------------------------------------------
    print("[1/4] building dataset + leave-one-fire-out validation ...")
    ds = features.build_dataset(fire_ids, cell_size_m=args.hazard_cell_m, buffer_m=6000.0)
    lofo = leave_one_fire_out(ds, seed=args.seed, compute_importance=True)
    fiou = footprint_iou_lofo(sorted(ds["fire_id"].unique()), ds, threshold=args.p_cut,
                              seed=args.seed, cell_size_m=args.hazard_cell_m)
    sev = sum(lofo.permutation_importance.get(f, 0.0) for f in features.SEVERITY_FEATURES)
    align = lofo.permutation_importance.get("wind_alignment", 0.0)
    lofo_summary = {
        "seed": args.seed,
        "n_rows": int(len(ds)),
        "n_positives": int(ds["label"].sum()),
        "fires_used": sorted(ds["fire_id"].unique()),
        "pooled_auc": lofo.pooled_auc,
        "mid_band_auc": lofo.mid_band_auc,
        "far_band_auc": lofo.far_band_auc,
        "per_fire_auc": lofo.per_fire_auc,
        "permutation_importance": lofo.permutation_importance,
        "severity_importance_sum": sev,
        "wind_alignment_importance": align,
        "severity_over_direction_ratio": (sev / align) if align > 0 else None,
        "footprint_iou_single_step": {
            "model": fiou.model_iou, "persistence": fiou.persistence_iou,
            "ratio_vs_persistence": fiou.ratio, "n_transitions": fiou.n_transitions,
        },
    }
    (out / "spread_v2_lofo.json").write_text(json.dumps(lofo_summary, indent=2))
    print(f"      pooled AUC={lofo.pooled_auc:.3f}  far-band AUC={lofo.far_band_auc:.3f}  "
          f"severity/direction={lofo_summary['severity_over_direction_ratio']:.1f}x")

    # ---- 2. forward-simulate the held-out fire's hazard --------------------
    print(f"[2/4] forward-simulating {args.fire} hazard (out-of-sample) ...")
    model = IgnitionModelV2(seed=args.seed).fit(ds[ds["fire_id"] != args.fire])
    ev = data.load_event(args.fire)
    ws = weather_series_from_event(ev)
    hg = gridmod.build_grid(ev.meta.bbox_wgs84, cell_size_m=args.hazard_cell_m)
    snaps = gridmod.overpass_snapshots(ev, hg, gap_minutes=90.0)
    hstatic = StaticLayers.from_event(ev, hg)
    sim = forward_simulate(model, ev, hg, hstatic, snaps[0].cumulative_mask, snaps[0].time, ws,
                           n_steps=args.n_steps, step_hours=args.step_hours,
                           advance_threshold=args.advance_threshold)
    hazard = HazardSequence.from_forward_sim(sim)
    ign_xy = np.array(_TO_5179.transform(*ev.meta.ignition_lonlat), float)
    drift = drift_vs_observed(sim, snaps, p_cut=args.p_cut)
    breadth = [envelope_breadth_deg(sim, s, tuple(ign_xy), p_cut=0.3) for s in range(sim.n_steps)]
    fwd_summary = {
        "fire": args.fire,
        "start_time": str(sim.start_time),
        "n_steps": sim.n_steps,
        "step_hours": args.step_hours,
        "advance_threshold": args.advance_threshold,
        "horizon_min": hazard.horizon_min,
        "drift": [d.__dict__ for d in drift],
        "envelope_breadth_deg": breadth,
        "envelope_area_ha": [sim.envelope_area_ha(s, args.p_cut) for s in range(sim.n_steps)],
    }
    (out / "yeongdeok_forward_sim.json").write_text(json.dumps(fwd_summary, indent=2, default=str))
    print("      drift IoU by step: " + ", ".join(f"{d.iou:.2f}" for d in drift) +
          f"  | envelope {fwd_summary['envelope_area_ha'][0]:.0f}->"
          f"{fwd_summary['envelope_area_ha'][-1]:.0f} ha, breadth ~{breadth[-1]:.0f} deg")

    # ---- 3. routing network + origin scan ---------------------------------
    print("[3/4] building evacuation network + scanning origins ...")
    rg = gridmod.build_grid(ev.meta.bbox_wgs84, cell_size_m=args.route_cell_m)
    relev = gridmod.elevation_on_grid(ev, rg)
    rburn = gridmod.burnable_fraction_on_grid(ev, rg)
    net = build_evacuation_network(rg, relev, rburn, flat_speed_ms=0.7)
    shelters_xy = np.array([[net.graph.nodes[s]["x"], net.graph.nodes[s]["y"]] for s in net.shelters], float)

    nodes = list(net.graph.nodes)
    cand = [n for i, n in enumerate(sorted(nodes)) if i % args.scan_stride == 0]
    # Focus on origins not already in the fire and roughly in the fire's reach.
    cand = [n for n in cand
            if hazard.prob_at(net.graph.nodes[n]["x"], net.graph.nodes[n]["y"], 0.0) < args.p_cut
            and abs(net.graph.nodes[n]["y"] - ign_xy[1]) < 14000]
    print(f"      network: {net.graph.number_of_nodes()} nodes, {len(net.shelters)} shelters; "
          f"scanning {len(cand)} origins ...")

    classes = {"naive_into_FA_safe": [], "no_safe_route": [], "both_safe": [], "both_enter": []}
    best_headline = None
    best_gain = -np.inf
    no_safe_example = None
    for n in cand:
        nv = naive_route(net, n, hazard, departure_min=0.0, p_cut=args.p_cut)
        fa = future_aware_route(net, n, hazard, departure_min=0.0,
                                time_budget_min=args.time_budget_min, p_cut=args.p_cut,
                                time_step_min=args.time_step_min)
        if not nv.reached:
            continue
        if nv.enters_hazard and fa.reached and not fa.enters_hazard:
            classes["naive_into_FA_safe"].append(n)
            gain = nv.exposure - fa.exposure
            if gain > best_gain:
                best_gain, best_headline = gain, (n, nv, fa)
        elif nv.enters_hazard and not fa.reached:
            classes["no_safe_route"].append(n)
            if no_safe_example is None:
                no_safe_example = (n, nv, fa)
        elif not nv.enters_hazard and fa.reached and not fa.enters_hazard:
            classes["both_safe"].append(n)
        elif nv.enters_hazard and fa.enters_hazard:
            classes["both_enter"].append(n)

    if best_headline is None:
        print("      WARNING: no clean headline origin found; using highest-exposure naive case")
        # Fallback: pick the naive route with the most exposure that FA improves.
        # (Should not happen on Yeongdeok with default params.)
        return 1
    origin, nv, fa = best_headline
    print(f"      headline origin {origin}: naive exposure {nv.exposure:.1f} (enters={nv.enters_hazard}) "
          f"-> future-aware {fa.exposure:.1f} (enters={fa.enters_hazard})")

    scan_summary = {
        "p_cut": args.p_cut, "time_budget_min": args.time_budget_min,
        "n_origins_scanned": len(cand),
        "counts": {k: len(v) for k, v in classes.items()},
        "headline": {
            "origin_node": int(origin),
            "origin_xy_5179": _route_xy(net, [origin])[0].tolist(),
            "naive": nv.as_dict(),
            "future_aware": fa.as_dict(),
            "exposure_reduction_abs": nv.exposure - fa.exposure,
            "exposure_reduction_pct": (100.0 * (nv.exposure - fa.exposure) / nv.exposure
                                       if nv.exposure > 0 else None),
        },
    }
    if no_safe_example is not None:
        nn, nnv, nfa = no_safe_example
        scan_summary["no_safe_route_example"] = {
            "origin_node": int(nn), "naive": nnv.as_dict(), "future_aware": nfa.as_dict(),
        }
    (out / "routing_demo.json").write_text(json.dumps(scan_summary, indent=2))

    # ---- 4. dump arrays for figures ---------------------------------------
    print("[4/4] writing arrays for figures ...")
    obs_stack = np.array([op.cumulative_mask for op in snaps], dtype=np.uint8)
    obs_times = np.array([(op.time - snaps[0].time).total_seconds() / 60.0 for op in snaps], float)
    np.savez_compressed(
        out / "routing_demo.npz",
        grid_extent=np.array([hg.minx, hg.miny, hg.maxx, hg.maxy, hg.cell_size_m], float),
        haz_times=hazard.times_min,
        haz_stack=np.array(hazard.surfaces, dtype=np.float32),
        obs_times=obs_times,
        obs_stack=obs_stack,
        ign_xy=ign_xy,
        shelters_xy=shelters_xy,
        naive_xy=_route_xy(net, nv.route),
        fa_xy=_route_xy(net, fa.route),
        origin_xy=_route_xy(net, [origin])[0],
        naive_node_haz=np.array(nv.node_hazard, float),
        naive_arrivals=np.array(nv.arrival_times_min, float),
        fa_node_haz=np.array(fa.node_hazard, float),
        fa_arrivals=np.array(fa.arrival_times_min, float),
    )
    print(f"done. wrote {out}/spread_v2_lofo.json, yeongdeok_forward_sim.json, "
          f"routing_demo.json, routing_demo.npz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
