#!/usr/bin/env python
"""Quantify how spread out the origins are, and what that does to clustering.

Round-3, promoted from an observation made while generating operational output.

WHAT PROMPTED IT
----------------
Clustering the 174 origins needing rescue leaves 69.2 % of clusters holding a
single point at eps = 500 m — and widening to 1500 m only brings that to 45.2 %.
A parameter that refuses to help across a 6x range is not mistuned. It is
measuring something.

⚠ WHAT THIS IS A PROPERTY OF
----------------------------
**These are sampled ORIGINS, not households.** Origins are taken by walking the
OSM node list at a fixed stride, so their spatial distribution reflects ROAD
NETWORK STRUCTURE, not residential density. A stretch of road with many mapped
nodes yields many origins whether or not anyone lives there; a dense hamlet on
one short lane yields few. Every number below inherits that.

So this measures the sparsity of the sampled origin set. Whether Yeongdeok's
actual settlements are equally dispersed is a related but separate question that
this project has no household data to answer.

Run:  python scripts/analyse_cluster_sparsity.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.config import config_hash  # noqa: E402
from wildfireguardian.delivery.villages import cluster_points  # noqa: E402

FULL = REPO / "data" / "processed" / "rescue_routing_full.json"
OUT = REPO / "data" / "processed" / "cluster_sparsity.json"
EPS_SWEEP = [250.0, 500.0, 750.0, 1000.0, 1500.0, 2000.0, 3000.0]

RESCUE_CLASSES = ("no_safe_pedestrian_route", "no_surviving_vehicle_ingress")


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def nn_distances(xy: np.ndarray) -> np.ndarray:
    """Distance from each point to its nearest OTHER point, in metres."""
    if len(xy) < 2:
        return np.array([])
    d = np.hypot(xy[:, 0, None] - xy[None, :, 0], xy[:, 1, None] - xy[None, :, 1])
    np.fill_diagonal(d, np.inf)
    return d.min(axis=1)


def describe(d: np.ndarray) -> dict:
    if not len(d):
        return {"n": 0}
    return {
        "n": int(len(d)),
        "min_m": float(d.min()),
        "p25_m": float(np.percentile(d, 25)),
        "median_m": float(np.median(d)),
        "mean_m": float(d.mean()),
        "p90_m": float(np.percentile(d, 90)),
        "p99_m": float(np.percentile(d, 99)),
        "max_m": float(d.max()),
        "frac_beyond_500m": float((d > 500).mean()),
        "frac_beyond_1000m": float((d > 1000).mean()),
        "frac_beyond_1500m": float((d > 1500).mean()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    if not FULL.exists():
        print(f"STOP: missing {FULL}", file=sys.stderr)
        return 2
    data = json.loads(FULL.read_text(encoding="utf-8"))
    rows = data["origins_full"]

    all_xy = np.array([[r["x_5179"], r["y_5179"]] for r in rows], float)
    resc = [r for r in rows if r["four_way_class"] in RESCUE_CLASSES]
    resc_xy = np.array([[r["x_5179"], r["y_5179"]] for r in resc], float)
    print(f"all origins           : {len(all_xy)}")
    print(f"origins needing rescue: {len(resc_xy)}\n")

    nn_all = describe(nn_distances(all_xy))
    nn_res = describe(nn_distances(resc_xy))

    print("=== nearest-neighbour distance (m) ===")
    print(f"{'set':>26s} {'n':>5s} {'median':>8s} {'mean':>8s} {'p90':>8s} {'max':>9s}")
    for label, s in (("all origins (441)", nn_all),
                     ("needing rescue (174)", nn_res)):
        print(f"{label:>26s} {s['n']:5d} {s['median_m']:8.0f} {s['mean_m']:8.0f} "
              f"{s['p90_m']:8.0f} {s['max_m']:9.0f}")

    # --- eps sweep on the rescue subset (what the sheets actually cluster) ---
    pts = [{"x": float(x), "y": float(y)} for x, y in resc_xy]
    sweep = []
    print("\n=== eps sweep (origins needing rescue) ===")
    print(f"{'eps_m':>7s} {'clusters':>9s} {'singletons':>11s} {'single %':>9s} "
          f"{'max':>5s} {'mean size':>10s} {'largest %':>10s}")
    for eps in EPS_SWEEP:
        vs = cluster_points(pts, data["destinations"], eps_m=eps)
        sizes = [v.n_points for v in vs]
        single = sum(1 for s in sizes if s == 1)
        sweep.append({
            "eps_m": eps, "n_clusters": len(vs), "n_singletons": single,
            "singleton_fraction": single / len(vs),
            "max_cluster_size": max(sizes), "mean_cluster_size": float(np.mean(sizes)),
            "points_in_singletons": single,
            "fraction_of_points_isolated": single / len(pts),
            # Collapse indicator: once one cluster swallows most of the region it
            # is no longer a village, and a falling singleton fraction stops
            # meaning "better grouping".
            "largest_cluster_fraction": max(sizes) / len(pts),
        })
        print(f"{eps:7.0f} {len(vs):9d} {single:11d} {single/len(vs)*100:8.1f}% "
              f"{max(sizes):5d} {np.mean(sizes):10.2f} "
              f"{max(sizes)/len(pts)*100:9.1f}%")

    # A cluster holding more than a quarter of every rescue point in the county
    # is not a village-scale audience.
    COLLAPSE = 0.25
    usable = [s for s in sweep if s["largest_cluster_fraction"] <= COLLAPSE]
    min_single_usable = min((s["singleton_fraction"] for s in usable), default=None)
    never_below_40 = all(s["singleton_fraction"] > 0.40 for s in sweep)
    never_below_40_usable = (min_single_usable is not None
                             and min_single_usable > 0.40)

    doc = {
        "schema_version": 1,
        "title": "Origin sparsity and its effect on village clustering",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(), "config_hash": config_hash(),
        "source_file": str(FULL.relative_to(REPO)),
        "what_this_measures": (
            "The spatial dispersion of SAMPLED ORIGINS, not of households. "
            "Origins are taken by walking the OSM node list at a fixed stride, so "
            "their distribution reflects road-network structure, not residential "
            "density. Whether Yeongdeok's actual settlements are equally dispersed "
            "is a separate question this project has no household data to answer."),
        "nearest_neighbour_m": {
            "all_origins": nn_all,
            "origins_needing_rescue": nn_res,
            "comparison": {
                "median_ratio_rescue_over_all":
                    (nn_res["median_m"] / nn_all["median_m"]) if nn_all.get("median_m") else None,
                "rescue_more_dispersed": bool(nn_res["median_m"] > nn_all["median_m"]),
            },
        },
        "eps_sweep": sweep,
        "finding": {
            "singleton_fraction_never_below_40pct_any_eps": never_below_40,
            "singleton_fraction_never_below_40pct_usable_eps": never_below_40_usable,
            "collapse_threshold_largest_cluster_fraction": COLLAPSE,
            "usable_eps_m": [s["eps_m"] for s in usable],
            "min_singleton_fraction_within_usable_eps": min_single_usable,
            "eps_range_tested_m": [EPS_SWEEP[0], EPS_SWEEP[-1]],
            "statement": (
                "The singleton fraction falls monotonically from 83.9 % at 250 m to "
                "35.3 % at 2000 m, so it DOES drop below 40 % — but only once "
                "clustering has stopped being clustering: at 2000 m the largest "
                "cluster holds 91 of 174 points (52 %), and at 3000 m it holds 168 "
                "of 174 (97 %). Restricting to radii where no cluster exceeds "
                f"{COLLAPSE:.0%} of all rescue points, the singleton fraction never "
                "goes below 49.2 %. Dispersion is a measured property of the "
                "sampled origin set here, not an untuned parameter."),
        },
        "operational_implication": (
            "A village-level broadcast reaches a cluster. Where a cluster is one "
            "point, there is no village-level audience to reach — the channel and "
            "the geography do not line up. Recorded as an observation; no remedy "
            "is proposed here."),
        "caveat": "Snapshot-network (2026-07-24) values on 441 origins, separate "
                  "from the committed 439-origin figures.",
    }
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
    print(f"\nsingleton fraction > 40 % at EVERY eps tested : {never_below_40}")
    print(f"singleton fraction > 40 % at every USABLE eps  : {never_below_40_usable}"
          f"  (largest cluster <= {COLLAPSE:.0%} of points; "
          f"usable = {[int(s['eps_m']) for s in usable]} m)")
    print(f"minimum singleton fraction within usable eps   : "
          f"{min_single_usable:.1%}" if min_single_usable is not None else "")
    print("\nnearest-neighbour: origins needing rescue are "
          f"{nn_res['median_m']/nn_all['median_m']:.2f}x more dispersed than all "
          "origins (median)")
    o = Path(args.out)
    print(f"wrote {o.relative_to(REPO) if o.is_relative_to(REPO) else o}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
