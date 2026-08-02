#!/usr/bin/env python
"""Assemble the three-region 459-series comparison.

Round-3 PHASE 5 STEP 4.

Reads only committed artifacts — it re-runs nothing:

    data/processed/real_roads_real_hazard_slope_60.json   Yeongdeok, QUOTED
    data/processed/real_roads_real_hazard.json            Yeongdeok, QUOTED
    data/processed/real_roads_real_hazard_{region}.json   STEP 2-3
    data/processed/osm_completeness.json                  covariates
    data/processed/{routing_demo,hazard_*}.npz            hazard fields

WHY THE COVARIATES ARE NOT OPTIONAL
-----------------------------------
The three regions differ on three axes at once — envelope coverage 50.4-98.9 %,
hazard area 2.8x, node density 7.27-9.07 per km² — so a bare ranking on the
headline fraction is uninterpretable. Every covariate the run can measure is
carried into the same table, and the origin count is additionally normalised
against BOTH road length and node count, because Uiseong-Andong has the highest
road-length density and the LOWEST node density: long straight ways carried by
few nodes. A stride-18 node scan is sensitive to exactly that difference.

WHAT THIS SCRIPT REFUSES TO DO
------------------------------
n = 3. It computes associations and labels them a direction, never a
correlation, and emits no p-value. `interpretation_rules` in the output says so
in machine-readable form so a downstream reader cannot pick the number up
without the caveat.

Run:  python scripts/build_multi_region_comparison.py
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

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.spread_v2.extent import check_envelope_coverage  # noqa: E402
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402
from pyproj import Transformer  # noqa: E402

_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

PROCESSED = REPO / "data" / "processed"
COMPLETENESS = PROCESSED / "osm_completeness.json"

#: region -> the hazard npz the 459-series routing actually consumed.
HAZARD_NPZ = {
    "yeongdeok_2025": PROCESSED / "routing_demo.npz",
    "uiseong_andong_2025": PROCESSED / "hazard_uiseong_andong_2025.npz",
    "uljin_samcheok_2022": PROCESSED / "hazard_uljin_samcheok_2022.npz",
}

ORDER = ("yeongdeok_2025", "uiseong_andong_2025", "uljin_samcheok_2022")

LABEL_KR = {
    "yeongdeok_2025": "영덕 2025",
    "uiseong_andong_2025": "의성·안동 2025",
    "uljin_samcheok_2022": "울진·삼척 2022",
}


def _git() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return None


def hazard_facts(region: str, walk_bbox) -> dict:
    """Envelope area, core growth and walk-bbox coverage from ONE definition.

    All three come from the npz the routing run actually read, at p >= 0.5, so
    the column is like-for-like across regions. That matters: the 27,900 ha
    Yeongdeok figure quoted elsewhere comes from `yeongdeok_forward_sim.json`,
    a DIFFERENT simulation artifact whose step-0 area (6,225 ha) does not even
    match this field's (6,025 ha). Mixing the two inflates the cross-region
    spread from 2.8x to 11.7x. See `envelope_area_definition` in the output.
    """
    z = np.load(HAZARD_NPZ[region])
    haz = z["haz_stack"].astype(np.float32)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax,
                      cell_size_m=cell, nrows=haz.shape[1], ncols=haz.shape[2])
    ha_per_cell = cell * cell / 10_000.0
    cells = [int((haz[i] >= 0.5).sum()) for i in range(haz.shape[0])]

    xs, ys = [], []
    for lon, lat in ((walk_bbox[0], walk_bbox[1]), (walk_bbox[0], walk_bbox[3]),
                     (walk_bbox[2], walk_bbox[1]), (walk_bbox[2], walk_bbox[3])):
        x, y = _TO_5179.transform(lon, lat)
        xs.append(x); ys.append(y)
    rb = (min(xs), min(ys), max(xs), max(ys))
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cov = check_envelope_coverage(rb, haz[-1], grid, p_cut=0.5)

    return {
        "hazard_npz": str(HAZARD_NPZ[region].relative_to(REPO)),
        "grid_shape": list(haz.shape),
        "cell_size_m": cell,
        "cells_ge_0.5_per_slice": cells,
        "envelope_area_ha_final_slice": cells[-1] * ha_per_cell,
        "core_growth_pct_first_to_last": (cells[-1] / max(cells[0], 1) - 1.0) * 100.0,
        "envelope_coverage_final_slice": cov["coverage"],
        "envelope_coverage_cells": [cov["n_covered"], cov["n_core_cells"]],
    }


def yeongdeok_rows() -> list[dict]:
    """The two committed Yeongdeok readings. QUOTED — never re-derived here."""
    slope = json.loads((PROCESSED / "real_roads_real_hazard_slope_60.json").read_text())
    flat = json.loads((PROCESSED / "real_roads_real_hazard.json").read_text())
    col3 = slope["three_column_comparison"]["col3_jul24_slope"]
    return [
        {
            "role": "primary",
            "source_file": "data/processed/real_roads_real_hazard_slope_60.json",
            "source_path": "three_column_comparison.col3_jul24_slope",
            "arm": "slope 60 m / DiGraph (canonical)",
            "n_origins_scanned": col3["n_origins_scanned"],
            "counts": col3["counts"],
            "n_walk_nodes_in_graph": col3["n_nodes"],
            "why": "PARAMETER-MATCHED to the two new regions: same 60 m slope "
                   "sampling, same distance objective, same 600-minute budget, "
                   "same stride 18. This is the row that belongs in the table.",
        },
        {
            "role": "context",
            "source_file": "data/processed/real_roads_real_hazard.json",
            "source_path": "counts",
            "arm": "flat / undirected, 2026-07-23 network",
            "n_origins_scanned": flat["n_origins_scanned"],
            "counts": flat["counts"],
            "n_walk_nodes_in_graph": flat["network_source"]["n_nodes"],
            "why": "The originally committed 459 = 438 + 18 + 3. Its network was "
                   "overwritten on 2026-07-24 and is unrecoverable, so it is "
                   "quoted for continuity and is NOT the parameter-matched row. "
                   "The gap to the primary row (459 vs 460 origins, 18 vs 17 "
                   "FA-only) is NETWORK DRIFT, not terrain.",
        },
    ]


def spearman(a: list[float], b: list[float]) -> float:
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = float(pos + 1)
        return r
    return pearson(rank(a), rank(b))


def pearson(a: list[float], b: list[float]) -> float:
    a_, b_ = np.asarray(a, float), np.asarray(b, float)
    if a_.std() == 0 or b_.std() == 0:
        return float("nan")
    return float(np.corrcoef(a_, b_)[0, 1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(PROCESSED / "multi_region_comparison.json"))
    args = ap.parse_args()

    bboxes = _cfg("bbox.multi_region_walk_bbox", {}) or {}
    comp = {r["region"]: r for r in json.loads(COMPLETENESS.read_text())["regions"]}
    fs_counts = json.loads(COMPLETENESS.read_text())["fire_station_counts_by_extent"]

    rows: list[dict] = []
    for region in ORDER:
        cov = comp[region]
        hz = hazard_facts(region, bboxes[region])

        if region == "yeongdeok_2025":
            variants = yeongdeok_rows()
            primary = next(v for v in variants if v["role"] == "primary")
            responder = {"responder_side_available": cov["responder_side_available"],
                         "n_depot_pois": cov["depot_pois"], "computed": False}
            extra = {"quoted_not_rerun": True, "yeongdeok_variants": variants}
        else:
            src = PROCESSED / f"real_roads_real_hazard_{region}.json"
            if not src.exists():
                print(f"STOP: {src.relative_to(REPO)} missing — run STEP 2-3 first "
                      "(scripts/run_multi_region_routing.py).", file=sys.stderr)
                return 2
            d = json.loads(src.read_text())
            arm = d["arms"]["slope_digraph_canonical"]
            primary = {
                "role": "primary",
                "source_file": str(src.relative_to(REPO)),
                "source_path": "arms.slope_digraph_canonical",
                "arm": arm["label"],
                "n_origins_scanned": arm["n_origins_scanned"],
                "counts": arm["counts"],
                "n_walk_nodes_in_graph": arm["n_nodes"],
            }
            responder = {
                "responder_side_available": d["responder_side"]["responder_side_available"],
                "n_depot_pois": d["responder_side"]["n_depot_pois"],
                "computed": False,
                "status": d["responder_side"]["status"],
            }
            extra = {
                "quoted_not_rerun": False,
                "slope_changed_counts_vs_flat": d["slope_effect"]["counts_changed_vs_flat"],
                "flat_control_counts": d["slope_effect"]["flat_counts"],
                "dem_footprint": {
                    "n_nodes_outside_dem": d["preflight"]["dem_footprint"]["n_nodes_outside_dem"],
                    "frac_nodes_outside_dem": d["preflight"]["dem_footprint"]["frac_nodes_outside_dem"],
                },
                "dem_hole_origins": d.get("dem_hole_origins"),
            }

        n = primary["n_origins_scanned"]
        c = primary["counts"]
        # The fire-blind route is unsafe for these three buckets combined; the
        # future-aware router then either rescues the origin (naive_into_FA_safe)
        # or cannot (no_safe_route / both_enter). Splitting it this way matters:
        # a region where the fire overruns everything shows up as no_safe_route,
        # which DEPRESSES the headline fraction for the opposite of the obvious
        # reason.
        n_naive_unsafe = (c["naive_into_FA_safe"] + c["no_safe_route"]
                          + c["both_enter"])
        rows.append({
            "region": region,
            "label_kr": LABEL_KR[region],
            "walk_bbox_wgs84_wsen": list(bboxes[region]),
            "bbox_area_km2": cov["bbox_area_km2"],
            # -- the headline three-way split -------------------------------
            "n_origins_scanned": n,
            "both_safe": c["both_safe"],
            "future_aware_only_safe": c["naive_into_FA_safe"],
            "no_safe_route": c["no_safe_route"],
            "other_buckets": {k: v for k, v in c.items()
                              if k not in ("both_safe", "naive_into_FA_safe",
                                           "no_safe_route")},
            "fa_exceeds_budget": c["fa_exceeds_budget"],
            "future_aware_only_safe_fraction": c["naive_into_FA_safe"] / n,
            "future_aware_only_safe_pct": 100.0 * c["naive_into_FA_safe"] / n,
            # -- the decomposition ------------------------------------------
            "n_naive_route_unsafe": n_naive_unsafe,
            "naive_route_unsafe_pct": 100.0 * n_naive_unsafe / n,
            "future_aware_rescue_rate": (c["naive_into_FA_safe"] / n_naive_unsafe
                                         if n_naive_unsafe else None),
            "future_aware_rescue_rate_note":
                "share of the origins whose FIRE-BLIND route is unsafe that the "
                "future-aware router still gets to a refuge. Denominator is "
                "naive_into_FA_safe + no_safe_route + both_enter, so it is not "
                "diluted by the origins that were never in danger.",
            # -- covariates --------------------------------------------------
            "envelope_coverage_final_slice": hz["envelope_coverage_final_slice"],
            "road_density_km_per_km2": cov["road_density_km_per_km2"],
            "node_density_per_km2": cov["node_density_per_km2"],
            "walk_length_km": cov["walk_length_km"],
            "walk_nodes": cov["walk_nodes"],
            "geometry_edge_fraction": cov["geometry_edge_fraction"],
            "shelter_pois": cov["shelter_pois"],
            "envelope_area_ha": hz["envelope_area_ha_final_slice"],
            "core_growth_pct": hz["core_growth_pct_first_to_last"],
            "depot_pois": cov["depot_pois"],
            # -- normalised origin counts ------------------------------------
            "origins_per_road_km": n / cov["walk_length_km"],
            "origins_per_1000_walk_nodes": 1000.0 * n / cov["walk_nodes"],
            "origins_per_100km2": 100.0 * n / cov["bbox_area_km2"],
            "origin_retention_vs_stride": n / (cov["walk_nodes"] / 18.0),
            # -- provenance ---------------------------------------------------
            "responder_side": responder,
            "hazard_facts": hz,
            "primary_source": {k: primary[k] for k in
                               ("source_file", "source_path", "arm", "role")},
            **extra,
        })

    fa = [r["future_aware_only_safe_fraction"] for r in rows]
    associations = {}
    for key in ("envelope_coverage_final_slice", "road_density_km_per_km2",
                "node_density_per_km2", "envelope_area_ha", "core_growth_pct",
                "origins_per_road_km", "origins_per_1000_walk_nodes",
                "shelter_pois", "geometry_edge_fraction"):
        v = [r[key] for r in rows]
        associations[key] = {
            "values_in_region_order": v,
            "pearson_r": pearson(fa, v),
            "spearman_rho": spearman(fa, v),
            "same_ordering_as_fa_only": spearman(fa, v) == 1.0,
            "reverse_ordering_of_fa_only": spearman(fa, v) == -1.0,
        }

    areas = [r["envelope_area_ha"] for r in rows]
    doc = {
        "schema_version": 1,
        "title": "Multi-region 459-series routing comparison (3 regions)",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(),
        "config_hash": config_hash(),
        "n_regions": len(rows),
        "region_order": list(ORDER),

        "metric_definition": {
            "name": "future_aware_only_safe_fraction",
            "formula": "counts.naive_into_FA_safe / n_origins_scanned",
            "means": "share of scanned origins that reach safety ONLY on the "
                     "future-aware route — the fire-blind shortest path enters "
                     "the predicted hazard, the future-aware one does not",
            "series": "459 (real roads + real hazard), THREE buckets",
            "is_not": "This is NOT the walk-failure rate w. w is a 439-series "
                      "quantity, produced on a SYNTHETIC hazard envelope tied to "
                      "a fabricated coastline, and cannot be carried to an inland "
                      "region at all. Never label this column w.",
        },

        "parameters_identical_across_regions": {
            "slope_sampling_m": float(_cfg("pedestrian.slope_sampling_m", 60.0)),
            "max_abs_slope": float(_cfg("pedestrian.max_abs_slope", 0.60)),
            "routing_objective": "length_m (distance-ranked)",
            "p_cut": float(_cfg("pedestrian.walk_cutoff_p", 0.5)),
            "time_budget_min": float(_cfg("pedestrian.walk_budget_min", 600.0)),
            "time_step_min": float(_cfg("time.routing_time_step_min", 10.0)),
            "origin_scan_stride": int(_cfg("origin_scan.real_osm_stride", 18)),
            "osmnx_pin": "2.0.7",
            "source": "config/default.yaml — no per-region override exists",
        },

        "interpretation_rules": [
            "DO NOT rank the regions on future_aware_only_safe_fraction alone.",
            "Three covariates differ materially and simultaneously: envelope "
            "coverage 50.4-98.9 %, hazard envelope area 2.77x between the "
            "smallest and largest, node density 7.27-9.07 per km².",
            "Uiseong-Andong has the HIGHEST road-length density (2.332 km/km²) "
            "and the LOWEST node density (7.27/km²): long straight ways carried "
            "by few nodes. A stride-18 scan over NODES is sensitive to that, so "
            "the origin count is reported normalised against road length AND "
            "node count, not raw.",
            "n = 3. Associations below are ORDERINGS, not correlations. No "
            "p-value is computed and none should be inferred. Never write "
            "'X correlates with Y' from this table.",
            "Before attributing a difference to terrain or to road network, read "
            "the covariate columns. 'Regions differ' and 'mapping differs' are "
            "not separable at n = 3.",
            "Yeongdeok is QUOTED from its committed artifacts and was not "
            "re-run: its 2026-07-23 network is unrecoverable.",
        ],

        "envelope_area_definition": {
            "definition": "cells at p >= 0.5 in the FINAL slice of the hazard "
                          "npz the routing run actually read, x cell area",
            "computed_here_for_all_three": True,
            "values_ha": {r["region"]: r["envelope_area_ha"] for r in rows},
            "spread_max_over_min": max(areas) / min(areas),
            "warning": (
                "A 27,900 ha figure for Yeongdeok appears in "
                "data/processed/yeongdeok_forward_sim.json and in prose derived "
                "from it. It is NOT this quantity: that artifact is a different "
                "simulation whose step-0 area is 6,225 ha where this field's is "
                "6,025 ha. Combining it with the two new regions' p>=0.5 areas "
                "inflates the apparent spread from 2.77x to about 11.7x. Use one "
                "definition or the other, never one of each."),
        },

        "regions": rows,

        "associations_directional_only": {
            "n": len(rows),
            "warning": "n = 3. These are orderings. Reporting them as "
                       "correlations, or attaching significance, is wrong.",
            "no_p_values": True,
            "vs": "future_aware_only_safe_fraction",
            "by_covariate": associations,
        },

        "core_growth_vs_metric": {
            "question": "Does the future-aware route help more where the fire "
                        "core actually advances?",
            "why_it_matters": "The Round-2 documents record a limitation — the "
                              "459-series result is 'dominated by a quasi-static "
                              ">=0.5 core'. If the metric tracked core growth "
                              "across regions, that limitation would look like a "
                              "property of the Yeongdeok field rather than of the "
                              "method.",
            "core_growth_pct": {r["region"]: r["core_growth_pct"] for r in rows},
            "fa_only_pct": {r["region"]: r["future_aware_only_safe_pct"] for r in rows},
            "no_safe_route_pct": {
                r["region"]: 100.0 * r["no_safe_route"] / r["n_origins_scanned"]
                for r in rows},
            "naive_route_unsafe_pct": {
                r["region"]: r["naive_route_unsafe_pct"] for r in rows},
            "future_aware_rescue_rate": {
                r["region"]: r["future_aware_rescue_rate"] for r in rows},
            "same_ordering_as_fa_only": spearman(
                fa, [r["core_growth_pct"] for r in rows]) == 1.0,
            "spearman_rho_vs_fa_only": spearman(
                fa, [r["core_growth_pct"] for r in rows]),
            "spearman_rho_vs_no_safe_route": spearman(
                [r["no_safe_route"] / r["n_origins_scanned"] for r in rows],
                [r["core_growth_pct"] for r in rows]),
            "spearman_rho_vs_rescue_rate": spearman(
                [r["future_aware_rescue_rate"] or 0.0 for r in rows],
                [r["core_growth_pct"] for r in rows]),
            "finding": (
                "NOT SUPPORTED as stated. The headline fraction runs OPPOSITE to "
                "core growth: the fastest-advancing core (Uljin-Samcheok, +155 %) "
                "has the LOWEST future-aware-only share. The decomposition says "
                "why — where the core advances fastest, an unsafe fire-blind "
                "route more often has no safe alternative at all, so those "
                "origins land in no_safe_route instead of naive_into_FA_safe. "
                "The share of origins whose fire-blind route is unsafe is nearly "
                "FLAT across the three regions (4.35 / 3.53 / 3.31 %); what moves "
                "is whether the future-aware router can still rescue them "
                "(85 % / 100 % / 23 %)."),
            "verdict": (
                "This does NOT establish that the 'dominated by a quasi-static "
                "core' limitation was Yeongdeok-specific. It does establish that "
                "the two new fields are not quasi-static (+79 % and +155 % core "
                "growth) and that the method still runs on them — and it shows a "
                "failure mode Yeongdeok could not show, because a near-static "
                "core cannot overtake a walker."),
            "n_is_3": True,
        },

        "sources": {
            "yeongdeok_primary": "data/processed/real_roads_real_hazard_slope_60.json",
            "yeongdeok_context": "data/processed/real_roads_real_hazard.json",
            "uiseong_andong": "data/processed/real_roads_real_hazard_uiseong_andong_2025.json",
            "uljin_samcheok": "data/processed/real_roads_real_hazard_uljin_samcheok_2022.json",
            "covariates": "data/processed/osm_completeness.json",
            "fire_station_counts_by_extent": fs_counts,
        },
    }

    out = Path(args.out)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)}")
    hdr = (f"{'region':22s} {'N':>5s} {'both':>5s} {'FA':>4s} {'nosafe':>6s} "
           f"{'budg':>4s} {'FA%':>6s} {'cover':>6s} {'road':>6s} {'node':>6s} "
           f"{'ha':>7s} {'depot':>5s} {'or/km':>6s} {'or/kn':>6s}")
    print("\n" + hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['region']:22s} {r['n_origins_scanned']:5d} {r['both_safe']:5d} "
              f"{r['future_aware_only_safe']:4d} {r['no_safe_route']:6d} "
              f"{r['fa_exceeds_budget']:4d} "
              f"{r['future_aware_only_safe_pct']:6.2f} "
              f"{r['envelope_coverage_final_slice'] * 100:6.1f} "
              f"{r['road_density_km_per_km2']:6.3f} {r['node_density_per_km2']:6.2f} "
              f"{r['envelope_area_ha']:7.0f} {r['depot_pois']:5d} "
              f"{r['origins_per_road_km']:6.3f} "
              f"{r['origins_per_1000_walk_nodes']:6.2f}")
    print("\ndecomposition — the fire-blind route is unsafe for:")
    for r in rows:
        rr = r["future_aware_rescue_rate"]
        print(f"  {r['region']:22s} {r['n_naive_route_unsafe']:3d}/"
              f"{r['n_origins_scanned']:<4d} = {r['naive_route_unsafe_pct']:5.2f}%   "
              f"future-aware rescues {rr * 100 if rr is not None else float('nan'):5.1f}% of them   "
              f"(core growth {r['core_growth_pct']:+6.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
