#!/usr/bin/env python
"""Export the WildfireGuardian demo data bundle from COMMITTED artifacts only.

This script READS committed pipeline outputs under ``data/processed/`` and writes
a single self-contained ``data/processed/demo_data.json`` that the offline demo
(``demo/wildfire_demo.html``) inlines. It invents nothing: every figure that will
appear on screen is copied from a committed file and carries a ``source`` string
naming that file and field. Recomputable summaries (mean-of-folds AUC and its std,
the self-evacuation-failure fraction) are RE-DERIVED here and asserted against the
committed values so the export is self-checking and reproducible.

Provenance guardrails enforced here (see the CodeFair brief):
  * ``footprint_iou_single_step`` (0.874) is NOT exported for display — it is
    report-blocked (dominated by shared burned area). The honest footprint figure
    is the forward-sim envelope IoU ~0.40, exported from ``yeongdeok_forward_sim``.
  * The model is scikit-learn ``HistGradientBoostingClassifier`` (seed 20250603).
    The word "XGBoost" never appears in the exported bundle.
  * The rescue layer's HAZARD and TERRAIN are SYNTHETIC (no FIRMS bundle present);
    its roads / refuges / depots are REAL OpenStreetMap. Both facts are exported
    verbatim from the committed provenance so the demo can label them honestly.
  * Geometry that is NOT committed (the predicted-front isochrone rings and the
    naive / future-aware evacuation route polylines live only in the git-ignored
    ``routing_demo.npz``, regenerable solely with the FIRMS/ERA5/DEM bundle) is
    reported as ``status: MISSING`` — never hand-faked.

Run:  python scripts/export_demo_data.py
Out:  data/processed/demo_data.json
"""

from __future__ import annotations

import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROC = REPO / "data" / "processed"
OUT = PROC / "demo_data.json"


def _load(name: str) -> dict:
    return json.loads((PROC / name).read_text())


def _src(name: str, field: str) -> str:
    return f"data/processed/{name}::{field}"


def _approx(a: float, b: float, tol: float = 5e-4) -> bool:
    return abs(a - b) <= tol


NPZ = PROC / "routing_demo.npz"
_NPZ_MISSING = "data/processed/routing_demo.npz (git-ignored bulk)"
_BUNDLE = "FIRMS/ERA5/DEM raw bundle (git-ignored; data.data_available()==False in a fresh clone)"


def _geometry_missing() -> tuple[None, dict]:
    """Honest MISSING marker for the S0-S3 geometry (never fabricate a front/route)."""
    status = {
        "fire_fronts": {
            "status": "MISSING",
            "what": "predicted-front isochrone rings for Yeongdeok",
            "lives_in": _NPZ_MISSING + " keys 'haz_stack' (float surfaces) + 'grid_extent' + 'haz_times'",
            "regenerate_needs": _BUNDLE + " via scripts/run_routing_integration.py (forward-sim requires it)",
            "note": "NOT fabricated. Only scalar summaries (areas, IoU, breadth) are committed "
                    "in yeongdeok_forward_sim.json; the polygon rings are not.",
        },
        "evac_routes": {
            "status": "MISSING",
            "what": "naive + future-aware evacuation route polylines for the headline origin",
            "lives_in": _NPZ_MISSING + " keys 'naive_xy' / 'fa_xy' / 'origin_xy' / 'shelters_xy'",
            "regenerate_needs": _BUNDLE + " (lattice network is built on the FIRMS-derived grid)",
            "note": "NOT fabricated. routing_demo.json commits only node ids + scalar route metrics.",
        },
    }
    return None, status


def load_scenario_geometry(route: dict, p_cut: float = 0.5):
    """Emit the REAL S0-S3 geometry from routing_demo.npz, or a MISSING marker.

    Fire fronts are iso-contours (level ``p_cut``) of the committed forward-sim
    hazard surfaces ``haz_stack`` on the EPSG:5179 north-up grid; routes are the
    committed lattice polylines. Everything is normalized into a single padded
    [0,1]^2 frame (content bbox of all layers) with y flipped so north is up.
    The naive route's failure point is the first node whose committed hazard
    (``naive_node_haz``) reaches ``p_cut`` — read from the arrays, not guessed.
    """
    if not NPZ.exists():
        return _geometry_missing()

    import numpy as np
    from skimage import measure

    z = np.load(NPZ)
    minx, miny, maxx, maxy, cell = (float(v) for v in z["grid_extent"])
    haz_times = np.asarray(z["haz_times"], float)
    haz_stack = np.asarray(z["haz_stack"], float)       # (n_surfaces, nrows, ncols)
    naive_xy = np.asarray(z["naive_xy"], float)
    fa_xy = np.asarray(z["fa_xy"], float)
    origin_xy = np.asarray(z["origin_xy"], float)
    naive_haz = np.asarray(z["naive_node_haz"], float)
    shelters = np.asarray(z["shelters_xy"], float) if "shelters_xy" in z.files else None
    ign = np.asarray(z["ign_xy"], float) if "ign_xy" in z.files else None

    def rc_to_xy(rc):  # (row,col) sub-pixel -> EPSG:5179 cell-centre coords
        x = minx + (rc[:, 1] + 0.5) * cell
        y = maxy - (rc[:, 0] + 0.5) * cell
        return np.column_stack([x, y])

    # pick up to 6 representative isochrone timesteps (always include first + last)
    n_surf = haz_stack.shape[0]
    k = min(6, n_surf)
    idx = sorted(set(np.linspace(0, n_surf - 1, k).round().astype(int).tolist()))
    fronts = []
    for i in idx:
        rings = []
        for c in measure.find_contours(haz_stack[i], p_cut):
            if len(c) >= 4:
                rings.append(rc_to_xy(c))
        if rings:
            tmax = float(haz_times.max()) or 1.0
            fronts.append({"i": int(i), "t_min": float(haz_times[i]),
                           "t_norm": round(float(haz_times[i]) / tmax, 4), "rings": rings})

    # failure point: first naive node whose committed hazard reaches p_cut
    hit = np.where(naive_haz >= p_cut)[0]
    fail_idx = int(hit[0]) if len(hit) else int(np.argmax(naive_haz))
    failure_xy = naive_xy[fail_idx]

    # single content bbox for all S0-S3 layers, padded, then normalize (y up)
    allpts = [naive_xy, fa_xy, origin_xy.reshape(1, 2)]
    allpts += [r for f in fronts for r in f["rings"]]
    if shelters is not None and len(shelters):
        allpts.append(shelters)
    P = np.vstack(allpts)
    bx0, by0 = P[:, 0].min(), P[:, 1].min()
    bx1, by1 = P[:, 0].max(), P[:, 1].max()
    mx, my = (bx1 - bx0) * 0.06, (by1 - by0) * 0.06
    bx0, by0, bx1, by1 = bx0 - mx, by0 - my, bx1 + mx, by1 + my

    def nz(pts):
        pts = np.atleast_2d(pts)
        nx = (pts[:, 0] - bx0) / (bx1 - bx0)
        ny = (by1 - pts[:, 1]) / (by1 - by0)   # flip: north (high y) -> top
        return [[round(float(a), 5), round(float(b), 5)] for a, b in zip(nx, ny)]

    geom = {
        "present": True,
        "crs": "EPSG:5179",
        "bbox_5179": [round(bx0, 1), round(by0, 1), round(bx1, 1), round(by1, 1)],
        "normalization": "all S0-S3 layers mapped into one padded [0,1]^2 content bbox; y flipped (north=top)",
        "hazard_provenance": "REAL spread_v2 forward-sim on held-out Yeongdeok (out-of-sample)",
        "front_level": p_cut,
        "fire_fronts": [{"t_min": f["t_min"], "t_norm": f["t_norm"],
                         "rings": [nz(r) for r in f["rings"]]} for f in fronts],
        "routes": {"naive": nz(naive_xy), "future_aware": nz(fa_xy)},
        "origin": nz(origin_xy)[0],
        "failure_point": nz(failure_xy)[0],
        "shelters": nz(shelters) if shelters is not None and len(shelters) else [],
        "ignition": nz(ign)[0] if ign is not None else None,
        "source": "data/processed/routing_demo.npz "
                  "(haz_stack/haz_times/grid_extent/naive_xy/fa_xy/origin_xy/naive_node_haz/shelters_xy)",
    }
    status = {"fire_fronts": {"status": "PRESENT", "source": geom["source"]},
              "evac_routes": {"status": "PRESENT", "source": geom["source"]}}
    return geom, status


def main() -> int:
    lofo = _load("spread_v2_lofo.json")
    fwd = _load("yeongdeok_forward_sim.json")
    route = _load("routing_demo.json")
    rescue = _load("rescue_routing.json")
    cap = _load("rescue_capacity.json")

    # ---------------------------------------------------------------- prediction
    per_fire = lofo["per_fire_auc"]
    fold_vals = list(per_fire.values())
    n = len(fold_vals)
    mean_folds = sum(fold_vals) / n
    var = sum((v - mean_folds) ** 2 for v in fold_vals) / (n - 1)  # sample std (ddof=1)
    std_folds = math.sqrt(var)
    # self-check against the display targets in the brief
    assert _approx(mean_folds, 0.890, 1e-3), mean_folds
    assert _approx(std_folds, 0.107, 1e-3), std_folds
    assert _approx(lofo["pooled_auc"], 0.905, 1e-3), lofo["pooled_auc"]

    imp = lofo["permutation_importance"]
    top_feat = max(imp, key=imp.get)
    assert top_feat == "days_since_rain", top_feat

    prediction = {
        "pooled_auc": {"value": round(lofo["pooled_auc"], 3),
                       "raw": lofo["pooled_auc"],
                       "source": _src("spread_v2_lofo.json", "pooled_auc")},
        "mean_of_folds_auc": {"value": round(mean_folds, 3), "std": round(std_folds, 3),
                              "raw_mean": mean_folds, "raw_std": std_folds,
                              "recomputed_from": "per_fire_auc (mean; sample std, ddof=1)",
                              "source": _src("spread_v2_lofo.json", "per_fire_auc")},
        "far_band_auc": {"value": round(lofo["far_band_auc"], 3),
                         "raw": lofo["far_band_auc"],
                         "note": "AUC on the far band (cells not adjacent to current fire) — the hard, out-ahead case",
                         "source": _src("spread_v2_lofo.json", "far_band_auc")},
        "per_fire_auc": {"value": {k: round(v, 3) for k, v in per_fire.items()},
                         "source": _src("spread_v2_lofo.json", "per_fire_auc")},
        "top_predictor": {"value": top_feat, "importance": round(imp[top_feat], 4), "rank": 1,
                          "source": _src("spread_v2_lofo.json", "permutation_importance")},
        "severity_over_direction_ratio": {"value": round(lofo["severity_over_direction_ratio"], 2),
                                           "display": "≈44×",
                                           "note": "severity feature importance sum / wind_alignment importance",
                                           "source": _src("spread_v2_lofo.json", "severity_over_direction_ratio")},
        "wind_alignment_importance": {"value": round(lofo["wind_alignment_importance"], 4),
                                      "note": "near-zero — wind DIRECTION barely matters vs severity",
                                      "source": _src("spread_v2_lofo.json", "wind_alignment_importance")},
        # report-blocked; kept for the record with display=False so it is never shown
        "footprint_iou_single_step_REPORT_BLOCKED": {
            "value": round(lofo["footprint_iou_single_step"]["model"], 3), "display": False,
            "reason": "dominated by shared burned area (next overpass GIVEN current burn); report-blocked",
            "source": _src("spread_v2_lofo.json", "footprint_iou_single_step.model")},
    }

    # -------------------------------------------------------------- forward-sim
    drift = fwd["drift"]
    iou_by_step = [round(d["iou"], 3) for d in drift]
    honest_iou = sum(d["iou"] for d in drift[1:]) / (len(drift) - 1)  # steps 1..4 (3-12 h)
    forward_sim = {
        "envelope_area_ha": [round(a) for a in fwd["envelope_area_ha"]],
        "drift_iou_per_step": iou_by_step,
        "step_hours": fwd["step_hours"],
        "horizon_min": fwd["horizon_min"],
        "honest_envelope_iou": {"value": round(honest_iou, 2), "display": "≈0.40",
                                "note": "forward-sim envelope IoU vs observed at 3-12 h (steps 1-4); "
                                        "the honest footprint figure (NOT the report-blocked 0.874)",
                                "source": _src("yeongdeok_forward_sim.json", "drift[1:].iou")},
        "source": _src("yeongdeok_forward_sim.json", "drift / envelope_area_ha"),
    }

    # ----------------------------------------------------------- routing headline
    # REAL out-of-sample spread-model hazard; scalars only (route polylines and
    # front rings are NOT committed — see geometry_status below).
    h = route["headline"]
    routing_headline = {
        "hazard_provenance": "REAL spread_v2 forward-sim on held-out Yeongdeok (out-of-sample)",
        "origin_xy_5179": h["origin_xy_5179"],
        "naive": {"total_distance_m": h["naive"]["total_distance_m"],
                  "exposure": round(h["naive"]["exposure"], 2),
                  "max_hazard": h["naive"]["max_hazard"],
                  "enters_hazard": h["naive"]["enters_hazard"],
                  "reached": h["naive"]["reached"]},
        "future_aware": {"total_distance_m": h["future_aware"]["total_distance_m"],
                         "exposure": round(h["future_aware"]["exposure"], 2),
                         "max_hazard": h["future_aware"]["max_hazard"],
                         "enters_hazard": h["future_aware"]["enters_hazard"],
                         "reached": h["future_aware"]["reached"]},
        "exposure_reduction_pct": round(h["exposure_reduction_pct"], 1),
        "scan_counts": {"n_origins_scanned": route["n_origins_scanned"], **route["counts"]},
        "source": _src("routing_demo.json", "headline / counts"),
    }

    # ------------------------------------------------------------------- rescue
    fw = rescue["four_way_counts"]
    re_exp = rescue["responder_exposure"]
    n_orig = rescue["n_origins"]
    n_need = re_exp["n_need_rescue"]
    # reconcile: needs-rescuer == no-safe-pedestrian + no-surviving-vehicle-ingress
    assert n_need == fw["no_safe_pedestrian_route"] + fw["no_surviving_vehicle_ingress"], n_need
    assert n_need == re_exp["n_need_rescue_immobile"] + re_exp["n_need_rescue_walk_cut"], n_need
    assert sum(fw.values()) == n_orig, fw
    self_evac_fail_pct = 100.0 * n_need / n_orig

    sweep = [{"units": c["n_rescue_units"],
              "rescued_in_time": c["three_way"]["rescued_in_time"],
              "capacity_deferred": c["three_way"]["capacity_deferred"],
              "geometry_unreachable": c["three_way"]["geometry_unreachable"],
              "pct_demand_met": c["pct_demand_met"]}
             for c in cap["sweep_units_baseline_delay"]]

    rescue_block = {
        "honesty": rescue["provenance"]["honesty"],
        "sources_map": rescue["provenance"]["sources"],  # hazard/terrain = synthetic; roads/refuges = osm
        "n_origins": n_orig,
        "already_safe": fw["already_safe"],
        "saved_by_rescue_reachable_refuge": fw["saved_by_rescue_reachable_refuge"],
        "no_safe_pedestrian_route": fw["no_safe_pedestrian_route"],
        "no_surviving_vehicle_ingress": fw["no_surviving_vehicle_ingress"],
        "n_needs_rescuer": n_need,
        "needs_rescuer_immobile": re_exp["n_need_rescue_immobile"],
        "needs_rescuer_walk_cut": re_exp["n_need_rescue_walk_cut"],
        "self_evac_fail": {"value_pct": round(self_evac_fail_pct, 1),
                           "numerator": n_need, "denominator": n_orig,
                           "note": "share of sampled origins that cannot self-evacuate on foot "
                                   "(needs-rescuer / all sampled origins)",
                           "source": _src("rescue_routing.json", "responder_exposure.n_need_rescue / n_origins")},
        "n_refuges": rescue["n_refuges"],
        "n_refuges_rescue_reachable": rescue["n_refuges_rescue_reachable"],
        "capacity_sweep": sweep,
        "capacity_config_PoC": cap["capacity_config_PoC"],
        "capacity_note": "PoC supply parameters, NOT measured Yeongdeok fire-service capacity; "
                         "the deliverable is the demand-supply CURVE, never a 'lives saved' figure",
        "source": "data/processed/rescue_routing.json + data/processed/rescue_capacity.json",
    }

    # ---------------------------------------------------- rescue points geometry
    # REAL OpenStreetMap coordinates (EPSG:5179), classified by a SYNTHETIC hazard.
    dest = rescue["destinations"]
    disp = rescue["dispatch_top20"]
    unr = rescue["unreachable_homes"]
    xs = [p["x"] for p in dest + disp + unr]
    ys = [p["y"] for p in dest + disp + unr]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    pad = 0.06  # normalized padding so points do not sit on the frame edge

    def norm(x: float, y: float) -> list:
        nx = (x - minx) / (maxx - minx)
        ny = (maxy - y) / (maxy - miny)  # flip so EPSG north -> top of screen
        nx = pad + nx * (1 - 2 * pad)
        ny = pad + ny * (1 - 2 * pad)
        return [round(nx, 5), round(ny, 5)]

    rescue_points = {
        "crs": "EPSG:5179",
        "bbox_5179": [round(minx, 1), round(miny, 1), round(maxx, 1), round(maxy, 1)],
        "normalization": "x,y mapped into [0,1]^2 within bbox_5179 (padded); y flipped so north is up (ny=0)",
        "hazard_provenance": "SYNTHETIC hazard (no FIRMS bundle); point locations are REAL OpenStreetMap",
        "refuges": [{"xy": norm(p["x"], p["y"]), "rescue_reachable": p["rescue_reachable"]}
                    for p in dest],
        "demand_homes": [{"xy": norm(p["x"], p["y"]),
                          "closing_window_min": round(p["closing_window_min"], 1)}
                         for p in disp],
        "unreachable_homes": [{"xy": norm(p["x"], p["y"])} for p in unr],
        "source": _src("rescue_routing.json", "destinations / dispatch_top20 / unreachable_homes"),
    }

    # ------------------------------------------------- scenario geometry (S0-S3)
    # REAL spread-model isochrone rings + REAL evac route polylines, IF the
    # git-ignored routing_demo.npz has been supplied. Otherwise reported MISSING
    # (never fabricated). See load_scenario_geometry() for the exact provenance.
    scenario_geometry, geometry_status = load_scenario_geometry(route, p_cut=0.5)

    bundle = {
        "meta": {
            "generated_by": "scripts/export_demo_data.py",
            "reads_committed_artifacts_only": True,
            "reproducibility": "All displayed numbers copied from committed files; mean-of-folds "
                               "AUC/std and self-evac-fail fraction re-derived and asserted here.",
            "model": "HistGradientBoostingClassifier (scikit-learn)",
            "model_source": "src/wildfireguardian/spread_v2/model.py",
            "seed": lofo["seed"],
            "cv": "Leave-One-Fire-Out",
            "fires_used": lofo["fires_used"],
            "n_rows": lofo["n_rows"],
            "n_positives": lofo["n_positives"],
            "data_sources_label": "NASA FIRMS(VIIRS+MODIS) · ERA5 · SRTM · ESA WorldCover / "
                                  "경로: 시간 확장 그래프 + Dijkstra(OSMnx) · Tobler(1993) 보행 보정",
        },
        "prediction": prediction,
        "forward_sim": forward_sim,
        "routing_headline": routing_headline,
        "scenario_geometry": scenario_geometry,
        "rescue": rescue_block,
        "rescue_points": rescue_points,
        "geometry_status": geometry_status,
    }

    OUT.write_text(json.dumps(bundle, ensure_ascii=False, indent=2))
    print(f"wrote {OUT.relative_to(REPO)}  ({OUT.stat().st_size} bytes)")
    print(f"  prediction: pooled AUC {prediction['pooled_auc']['value']}, "
          f"mean-of-folds {prediction['mean_of_folds_auc']['value']}±"
          f"{prediction['mean_of_folds_auc']['std']}, far-band {prediction['far_band_auc']['value']}")
    print(f"  rescue: {n_need}/{n_orig} = {self_evac_fail_pct:.1f}% cannot self-evacuate; "
          f"8 units meet {sweep[-1]['pct_demand_met']}% of demand")
    ff = geometry_status["fire_fronts"]["status"]
    er = geometry_status["evac_routes"]["status"]
    if scenario_geometry:
        nfr = sum(len(f["rings"]) for f in scenario_geometry["fire_fronts"])
        print(f"  scenario_geometry: fire_fronts={ff} ({len(scenario_geometry['fire_fronts'])} "
              f"timesteps, {nfr} rings), evac_routes={er} "
              f"(naive {len(scenario_geometry['routes']['naive'])} pts, "
              f"future_aware {len(scenario_geometry['routes']['future_aware'])} pts)")
    else:
        print(f"  scenario_geometry: fire_fronts={ff}, evac_routes={er} "
              f"(supply data/processed/routing_demo.npz to populate — see geometry_status in JSON)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
