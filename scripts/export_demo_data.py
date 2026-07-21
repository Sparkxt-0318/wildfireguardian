#!/usr/bin/env python
"""Export the WildfireGuardian demo data bundle from COMMITTED artifacts only.

This script *reads* committed pipeline outputs and writes a single standalone
``data/processed/demo_data.json`` that the offline demo (``demo/wildfire_demo.html``)
inlines. It never re-runs the pipeline, never invents a number, and never renames
an upstream identifier/key. Every value it emits carries a ``source`` string
naming the committed file + field it came from.

It also *verifies* the headline recomputations (mean-of-folds AUC, its std, the
four-way split sum, the capacity supply identity) and prints a numbers-with-sources
table for review. Where a required geometry is NOT committed (and regenerating it
needs the git-ignored FIRMS/ERA5/SRTM/WorldCover bundle), it records the blocker
explicitly rather than fabricating a fire front or route.

Pure standard library (json / math / pathlib) so it runs with no third-party deps.

Run:  python scripts/export_demo_data.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROC = REPO / "data" / "processed"
VCAS = REPO / "data" / "validation_cases"
OUT = PROC / "demo_data.json"

# Files this exporter reads (all committed).
F_LOFO = PROC / "spread_v2_lofo.json"
F_ROUTING = PROC / "rescue_routing.json"        # REAL-OSM flip (hazard synthetic)
F_VERIFY_FC = PROC / "rescue_verify_fc.json"    # REAL-OSM flip fc sweep
F_CAPACITY = PROC / "rescue_capacity.json"      # REAL-OSM flip capacity sweep
F_SYN_CAP = PROC / "rescue_baseline_synthetic" / "rescue_capacity.json"   # synthetic baseline
F_SYN_FC = PROC / "rescue_baseline_synthetic" / "rescue_verify_fc.json"   # synthetic baseline
F_PERIM = VCAS / "yeongdeok_2025_perimeter_approx.geojson"  # OBSERVED-approx (not predicted)
F_GEOM = PROC / "demo_geometry.json"   # computed by scripts/build_demo_routes.py (real OSM routes)


def _load(p: Path) -> dict:
    return json.loads(p.read_text())


def rel(p: Path) -> str:
    return str(p.relative_to(REPO))


# Collect table rows for the review print-out: (label, value, source).
TABLE: list[tuple[str, str, str]] = []


def row(label: str, value: str, source: str) -> None:
    TABLE.append((label, value, source))


# ---------------------------------------------------------------------------
# 1. Prediction metrics  (spread_v2_lofo.json — REAL FIRMS data, seed 20250603)
# ---------------------------------------------------------------------------
def prediction_block() -> dict:
    d = _load(F_LOFO)
    src = rel(F_LOFO)

    per_fire = d["per_fire_auc"]
    folds = list(per_fire.values())
    n = len(folds)
    mean_folds = sum(folds) / n
    std_samp = math.sqrt(sum((x - mean_folds) ** 2 for x in folds) / (n - 1))

    # VERIFY the mean-of-folds recomputes to the reported 0.890 and std to 0.107.
    assert abs(mean_folds - 0.890) < 0.001, f"mean-of-folds {mean_folds} != 0.890"
    assert abs(std_samp - 0.107) < 0.001, f"std-of-folds {std_samp} != 0.107"

    pi = d["permutation_importance"]
    ranked = sorted(pi.items(), key=lambda kv: -kv[1])
    top_feat, top_imp = ranked[0]
    assert top_feat == "days_since_rain", f"top predictor is {top_feat}, not days_since_rain"

    ratio = d["severity_over_direction_ratio"]

    row("예측 AUC (pooled)", f"{d['pooled_auc']:.3f}", f"{src} :: pooled_auc")
    row("일반화 AUC (mean-of-folds ± std)",
        f"{mean_folds:.3f} ± {std_samp:.3f}",
        f"{src} :: mean(per_fire_auc)  [recomputed & verified]")
    row("원거리대(>3km) AUC", f"{d['far_band_auc']:.3f}", f"{src} :: far_band_auc")
    row("중거리대(1-3km) AUC", f"{d['mid_band_auc']:.3f}", f"{src} :: mid_band_auc")
    row("최중요 변수 (#1)", f"{top_feat} ({top_imp:.3f})",
        f"{src} :: permutation_importance (rank 1)")
    row("풍향 변수 중요도", f"{d['wind_alignment_importance']:.4f} (≈0)",
        f"{src} :: wind_alignment_importance")
    row("심각도 ≫ 풍향 비율", f"{ratio:.2f}  → ≈44×",
        f"{src} :: severity_over_direction_ratio")
    row("LOFO 폴드 수 / 학습 행수 / 양성",
        f"{n} fires / {d['n_rows']:,} / {d['n_positives']:,}",
        f"{src} :: fires_used, n_rows, n_positives")

    return {
        "model_line": "모델: HistGradientBoosting · Leave-One-Fire-Out 교차검증 (6개 실제 산불)",
        "seed": {"value": d["seed"], "source": f"{src} :: seed"},
        "pooled_auc": {"value": round(d["pooled_auc"], 4), "display": f"{d['pooled_auc']:.3f}",
                       "source": f"{src} :: pooled_auc"},
        "mean_of_folds_auc": {
            "value": round(mean_folds, 4), "display": f"{mean_folds:.3f}",
            "std": round(std_samp, 4), "std_display": f"{std_samp:.3f}",
            "recomputed_from": "mean/std(ddof=1) of per_fire_auc — verified == 0.890 ± 0.107",
            "source": f"{src} :: per_fire_auc"},
        "far_band_auc": {"value": round(d["far_band_auc"], 4),
                         "display": f"{d['far_band_auc']:.3f}",
                         "source": f"{src} :: far_band_auc"},
        "mid_band_auc": {"value": round(d["mid_band_auc"], 4),
                         "display": f"{d['mid_band_auc']:.3f}",
                         "source": f"{src} :: mid_band_auc"},
        "per_fire_auc": {"value": {k: round(v, 4) for k, v in per_fire.items()},
                         "source": f"{src} :: per_fire_auc"},
        "top_predictor": {"name": top_feat, "importance": round(top_imp, 4),
                          "source": f"{src} :: permutation_importance (rank 1)"},
        "wind_alignment_importance": {"value": round(d["wind_alignment_importance"], 4),
                                      "source": f"{src} :: wind_alignment_importance"},
        "severity_over_direction_ratio": {
            "value": round(ratio, 2), "display": "≈44×",
            "source": f"{src} :: severity_over_direction_ratio"},
        "finding_label": "화재-기상 심각도(건조도·습도·풍속) ≫ 풍향",
        # forward-sim envelope IoU (honest number). Kept out of the main view per brief;
        # available for a footnote. Single-step 0.874 is deliberately NOT exported.
        "forward_sim_iou_note": {
            "value": 0.40,
            "display": "≈0.40",
            "caveat": "전방 시뮬레이션 포락선 IoU (3-12h). 단일 스텝 0.874는 공유 연소면적이 지배 → 미표시.",
            "source": f"{rel(PROC / 'yeongdeok_forward_sim.json')} :: drift[].iou (steps 1-4 ≈ 0.37-0.40)"},
    }


# ---------------------------------------------------------------------------
# 2. Routing / rescue metrics  (REAL-OSM flip; fire HAZARD is synthetic)
# ---------------------------------------------------------------------------
def rescue_block() -> dict:
    routing = _load(F_ROUTING)
    fc = _load(F_VERIFY_FC)
    cap = _load(F_CAPACITY)
    syn_cap = _load(F_SYN_CAP)
    syn_fc = _load(F_SYN_FC)

    s_routing, s_fc, s_cap = rel(F_ROUTING), rel(F_VERIFY_FC), rel(F_CAPACITY)
    s_syn_cap, s_syn_fc = rel(F_SYN_CAP), rel(F_SYN_FC)

    # --- REAL flip ---
    n_origins = routing["n_origins"]                       # 439
    four = routing["four_way_counts"]
    assert routing["four_way_sums_to_n"], "four-way split does not sum to N"
    assert sum(four.values()) == n_origins

    needs = fc["needs_rescuer"]                             # baseline 167, 38.0%
    n_needs = needs["baseline"]
    needs_pct = needs["baseline_pct"]
    # cross-check needs == no_safe_pedestrian_route + no_surviving_vehicle_ingress
    assert n_needs == four["no_safe_pedestrian_route"] + four["no_surviving_vehicle_ingress"], \
        "needs_rescuer != no_walk + no_ingress"

    # capacity @ 8 units (REAL): rescued 24 / demand 167 = 14.4%
    cap_rows = cap["sweep_units_baseline_delay"]
    cap8 = next(r for r in cap_rows if r["n_rescue_units"] == 8)
    real_pct8 = cap8["pct_demand_met"]
    # supply identity: rescued ≈ units * floor(W/service)
    W = cap["baseline_config"]["assumed"]["responder_time_budget_min"]
    svc = cap["capacity_config_PoC"]["rescue_service_time_min"]
    per_unit = math.floor(W / svc)
    assert cap8["three_way"]["rescued_in_time"] == 8 * per_unit, "capacity supply identity broke"

    # --- SYNTHETIC baseline (the <10% figure lives here) ---
    syn_needs = syn_fc["needs_rescuer"]["baseline"]        # 264
    syn_n = syn_fc["n_origins"]                            # 452
    syn_needs_pct = syn_fc["needs_rescuer"]["baseline_pct"]
    syn_cap_rows = syn_cap["sweep_units_baseline_delay"]
    syn_cap8 = next(r for r in syn_cap_rows if r["n_rescue_units"] == 8)
    syn_pct8 = syn_cap8["pct_demand_met"]                  # 9.1

    # table
    row("(실데이터 도로망) 원점 수 N", f"{n_origins}", f"{s_routing} :: n_origins")
    row("스스로 대피 불가 (needs_rescuer)",
        f"{n_needs} / {n_origins} = {needs_pct:.1f}%",
        f"{s_fc} :: needs_rescuer.baseline / baseline_pct  [immobile f=0.30, walk cutoff 0.5]")
    row("  · 이동 불가(거동)/보행로 차단 분해",
        f"{routing['responder_exposure']['n_need_rescue_immobile']} / "
        f"{routing['responder_exposure']['n_need_rescue_walk_cut']}",
        f"{s_routing} :: responder_exposure.n_need_rescue_immobile/_walk_cut")
    row("  · 순수 도달 불가(도로 소실) 집합",
        f"{four['no_surviving_vehicle_ingress']} / {n_origins} = "
        f"{100*four['no_surviving_vehicle_ingress']/n_origins:.1f}%",
        f"{s_routing} :: four_way_counts.no_surviving_vehicle_ingress")
    row("구조 대원 8팀 → 수요 대비 (실데이터)",
        f"rescued {cap8['three_way']['rescued_in_time']} / {n_needs} = {real_pct8:.1f}%",
        f"{s_cap} :: sweep_units_baseline_delay[8].pct_demand_met")
    row("구조 대원 8팀 → 수요 대비 (합성 기준선)",
        f"rescued {syn_cap8['three_way']['rescued_in_time']} / {syn_needs} = {syn_pct8:.1f}%",
        f"{s_syn_cap} :: sweep_units_baseline_delay[8].pct_demand_met")
    row("적시 구조 공급 항등식",
        f"units × ⌊W/service⌋ = units × ⌊{W:.0f}/{svc:.0f}⌋ = units × {per_unit}",
        f"{s_cap} :: capacity_config_PoC (W={W:.0f}, service={svc:.0f})")

    def cap_curve(rows):
        return [{"units": r["n_rescue_units"],
                 "rescued_in_time": r["three_way"]["rescued_in_time"],
                 "pct_demand_met": r["pct_demand_met"]} for r in rows]

    return {
        "hazard_provenance_warning":
            "구조/용량 수치는 실제 OSM 도로망 위에서 계산되었으나, 화재 위험면(hazard)은 "
            "FIRMS 번들 부재로 합성(synthetic)입니다. 방향/대비는 견고하나 절대 수치는 예시입니다.",
        "real_flip": {
            "n_origins": {"value": n_origins, "source": f"{s_routing} :: n_origins"},
            "four_way_counts": {"value": four, "source": f"{s_routing} :: four_way_counts"},
            "needs_rescuer": {
                "value": n_needs, "pct": needs_pct,
                "display": f"{n_needs} / {n_origins} ({needs_pct:.1f}%)",
                "wording": "스스로 대피할 수 없는 주민 (거동 불가 30% 가정 + 보행로 차단)",
                "source": f"{s_fc} :: needs_rescuer.baseline / baseline_pct"},
            "geometry_unreachable": {
                "value": four["no_surviving_vehicle_ingress"],
                "pct": round(100 * four["no_surviving_vehicle_ingress"] / n_origins, 1),
                "wording": "순수 도달 불가 집합 (생존 도로 없음)",
                "source": f"{s_routing} :: four_way_counts.no_surviving_vehicle_ingress"},
            "capacity_curve": {"value": cap_curve(cap_rows),
                               "source": f"{s_cap} :: sweep_units_baseline_delay"},
            "capacity_8units_pct": {"value": real_pct8, "display": f"{real_pct8:.1f}%",
                                    "demand_denominator": n_needs,
                                    "source": f"{s_cap} :: sweep_units_baseline_delay[8]"},
            "geometry_ceiling_pct": {"value": cap.get("geometry_ceiling_pct"),
                                     "source": f"{s_cap} :: geometry_ceiling_pct"},
        },
        "synthetic_baseline": {
            "note": "flip 이전 합성-폴백 기준선 (data/processed/rescue_baseline_synthetic/). "
                    "브리프의 452 / 264(58%) / 8팀<10%(9.1%) 수치의 출처.",
            "n_origins": {"value": syn_n, "source": f"{s_syn_fc} :: n_origins"},
            "needs_rescuer": {"value": syn_needs, "pct": syn_needs_pct,
                              "display": f"{syn_needs} / {syn_n} ({syn_needs_pct:.1f}%)",
                              "source": f"{s_syn_fc} :: needs_rescuer.baseline / baseline_pct"},
            "capacity_8units_pct": {"value": syn_pct8, "display": f"{syn_pct8:.1f}%",
                                    "demand_denominator": syn_needs,
                                    "source": f"{s_syn_cap} :: sweep_units_baseline_delay[8]"},
        },
        "supply_identity": {"W_min": W, "service_min": svc, "rescues_per_unit": per_unit,
                            "source": f"{s_cap} :: capacity_config_PoC"},
    }


# ---------------------------------------------------------------------------
# 3. Geometry — real computed routes vs committed observed-approx front.
# ---------------------------------------------------------------------------
def geometry_block() -> dict:
    """Fold in the real computed route geometry (scripts/build_demo_routes.py).

    The spread_v2 PREDICTED front is FIRMS-locked and never fabricated. The demo's
    signature divergence is instead the REAL routing method computed on the live 영덕
    OSM walk network against the committed OBSERVED-APPROXIMATE front — every point
    is either committed or genuinely computed, none hand-drawn.
    """
    if not F_GEOM.exists():
        raise SystemExit(
            "missing data/processed/demo_geometry.json — run scripts/build_demo_routes.py first")
    g = _load(F_GEOM)
    s_geom = rel(F_GEOM)

    nfronts = len(g["fire_fronts"])
    nv = g["routes"]["naive"]
    fa = g["routes"]["future_aware"]

    row("화재 확산선 (관측 근사, 재투영)", f"{nfronts} isochrones",
        f"{s_geom} :: fire_fronts  (from {rel(F_PERIM)}, WGS84→EPSG:5179)")
    row("영덕 보행 도로망 (OSM) 규모",
        f"{g['meta']['graph_nodes']} nodes",
        f"{s_geom} :: meta.graph_source (OSMnx, EPSG:5179)")
    row("naive 경로 (화재 예측 없음)",
        f"{len(nv['polyline'])} pts · {nv['total_time_min']:.0f}min · 진입 t={nv['fail_time_min']:.0f}min → 대피 실패",
        f"{s_geom} :: routes.naive")
    row("future-aware 경로 (미래 인지)",
        f"{len(fa['polyline'])} pts · {fa['total_time_min']:.0f}min · 우회 +{fa['detour_min']:.0f}min → 대피 성공",
        f"{s_geom} :: routes.future_aware")
    row("프레임 내 구조 필요 점 / 대피소",
        f"{g['rescue_points_in_frame']['count']} / {g['refuges_in_frame']['count']}",
        f"{s_geom} :: rescue_points_in_frame / refuges_in_frame (from {rel(F_ROUTING)})")

    return {
        "note": "geometry from scripts/build_demo_routes.py (real OSM routes vs committed "
                "observed-approx front). See meta.front_provenance for the honest caveat.",
        "meta": g["meta"],
        "fire_fronts": g["fire_fronts"],
        "origin": g["origin"],
        "routes": g["routes"],
        "safe_zone_note": g["safe_zone_note"],
        "rescue_points_in_frame": g["rescue_points_in_frame"],
        "refuges_in_frame": g["refuges_in_frame"],
        "spread_v2_predicted_front_status": {
            "status": "NOT SHOWN — FIRMS-locked, never fabricated",
            "why": "The spread_v2 isochrone rings + the router's own polylines are written only to "
                   "the git-ignored routing_demo.npz; run_routing_integration.py aborts (return 2) "
                   "without the FIRMS bundle. yeongdeok_forward_sim.json holds only scalar "
                   "envelope_area_ha/breadth. So the drawn front is the committed observed-approx "
                   "reconstruction (labelled), and AUC 0.905 is shown as the model's validated skill, "
                   "never as a caption on the drawn front.",
            "committed_aggregate_result": {
                "note": "The real spread_v2 routing run's aggregate contrast IS committed (routing_demo.json):",
                "naive_exposure_probmin": 334.3, "future_aware_exposure_probmin": 23.1,
                "source": f"{rel(PROC / 'routing_demo.json')} :: headline.naive/future_aware.exposure"},
            "needs": "FIRMS(VIIRS+MODIS)+ERA5+SRTM+WorldCover → data/raw/firms/ (or WFG_FIRMS_DIR)"},
    }


def main() -> int:
    prediction = prediction_block()
    rescue = rescue_block()
    geometry = geometry_block()

    bundle = {
        "meta": {
            "title": "WildfireGuardian · 산불 골든타임 — demo data bundle",
            "generated_by": "scripts/export_demo_data.py (reads committed artifacts only)",
            "seed": 20250603,
            "reproducibility_line": "모든 수치는 커밋된 아티팩트에서 재생성됩니다.",
            "data_sources_line": ("NASA FIRMS(VIIRS+MODIS) · ERA5 · SRTM · ESA WorldCover / "
                                  "경로: 시간 확장 그래프 + Dijkstra(OSMnx) · Tobler(1993) 보행 보정"),
            "reconciliation": {
                "self_evac_failure_~40pct": {
                    "resolved_to": "REAL-OSM flip needs_rescuer = 167/439 = 38.0%",
                    "source": "rescue_verify_fc.json :: needs_rescuer.baseline / baseline_pct",
                    "note": "브리프의 '264/452=58%'는 flip 이전 합성 기준선. 실데이터 flip에서 38.0% ≈ 약 40%."},
                "rescue_coverage_resolved": {
                    "decision": "실데이터(real-OSM) flip 단일 데이터셋으로 일관 표기.",
                    "real_flip_8units": "24 / 167 = 14.4% (분모 167). 브리프의 '10% 미만'은 합성 "
                                        "기준선(9.1%, 분모 264)에서만 성립 → 혼용하지 않고 14.4%로 정직 표기.",
                    "source": "rescue_capacity.json :: sweep_units_baseline_delay[8]"},
                "predicted_front_geometry": {
                    "decision": "spread_v2 예측 확산선은 FIRMS 잠금 → 미표시(조작 금지). 대신 실제 OSM "
                                "도로망 위에서 관측-근사 확산선에 대해 경로를 실제 계산하여 시연.",
                    "source": "scripts/build_demo_routes.py :: demo_geometry.json"},
            },
        },
        "prediction": prediction,
        "rescue": rescue,
        "geometry": geometry,
    }

    OUT.write_text(json.dumps(bundle, ensure_ascii=False, indent=2))

    # ---- review print-out ----
    print("\n" + "=" * 92)
    print("STEP-0 NUMBERS-WITH-SOURCES  (every value that could appear on screen)")
    print("=" * 92)
    w1 = max(len(r[0]) for r in TABLE)
    w2 = max(len(r[1]) for r in TABLE)
    for label, value, source in TABLE:
        print(f"{label.ljust(w1)}  |  {value.ljust(w2)}  |  {source}")
    print("=" * 92)
    print(f"wrote {rel(OUT)}  ({OUT.stat().st_size:,} bytes)")
    print("\nRESOLUTIONS (see meta.reconciliation in the JSON):")
    print("  1. GEOMETRY: spread_v2 PREDICTED front is FIRMS-locked → never fabricated.")
    print("     Signature divergence = REAL routes computed on the live 영덕 OSM walk net")
    print("     vs the committed OBSERVED-APPROX front (labelled). AUC shown as model skill.")
    print("  2. RESCUE: anchored on the real-OSM flip (N=439). '스스로 대피 불가' = 38.0%")
    print("     (167/439). Capacity @ 8 teams shown honestly at its real 14.4% (not <10%,")
    print("     which was the superseded synthetic baseline).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
