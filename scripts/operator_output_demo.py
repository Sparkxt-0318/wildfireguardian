#!/usr/bin/env python
"""Operator-facing output mockup from the real 영덕 PoC dispatch (priority 5).

Answers "복지사는 노트북으로 뭘 보나요? 엑셀이 나오나요, 대시보드인가요?": the system's
delivery layer is people (가족·복지사·지자체), but its operator-facing **output had no
visible form** in the docs. This renders the concrete artifact an operator
receives, generated from the **actual rescue PoC pipeline** (not hand-faked):

  1. a **prioritized dispatch table** (operator/responder view): home id, outcome
     class (rescued_in_time / capacity_deferred / geometry_unreachable — from the
     Task-1 capacity layer), assigned 집결지/대피처, recommended road direction,
     responder ETA, and urgency (closing window);
  2. a **per-resident SMS** (Korean, short, imperative — not 합니다체), auto-filled
     from the actual route: a self-evacuating resident, a rescued immobile
     resident, and (honestly) a capacity-deferred one.

Outputs: docs/figures/operator_output.png  +  docs/operator_output_sample.txt

*** Illustrative output of the research pipeline on synthetic-and-tagged geometry
— NOT a deployed product/UI, NOT real residents. *** Names are placeholders
(○○○); a deployment fills them from the operator's resident registry.

Run:  python scripts/operator_output_demo.py
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.routing.rescue import (  # noqa: E402
    RescueCapacityConfig,
    RescueConfig,
    capacity_triage,
)
from wildfireguardian.routing.rescue_demo import build_synthetic_demo, run_pipeline  # noqa: E402

FIG = REPO / "docs" / "figures"
TXT = REPO / "docs" / "operator_output_sample.txt"

_COMPASS_KR = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"]
_COMPASS_EN = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _setup_font():
    from matplotlib import font_manager as fm
    import matplotlib.pyplot as plt
    for p in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"):
        if os.path.exists(p):
            fm.fontManager.addfont(p)
            plt.rcParams["font.family"] = fm.FontProperties(fname=p).get_name()
            break
    plt.rcParams["axes.unicode_minus"] = False


def _bearing(x0, y0, x1, y1) -> tuple[str, str]:
    """Korean + English 8-point compass direction from (x0,y0) toward (x1,y1)."""
    ang = math.degrees(math.atan2(x1 - x0, y1 - y0)) % 360.0   # 0=N, 90=E (planar 5179)
    k = int((ang + 22.5) // 45) % 8
    return _COMPASS_KR[k], _COMPASS_EN[k]


def _nearest_dest_name(scenario, x, y) -> tuple[str, str]:
    """Friendly bilingual label for the refuge nearest (x, y)."""
    best, bd = None, math.inf
    for d in scenario.destinations:
        dd = (d.x - x) ** 2 + (d.y - y) ** 2
        if dd < bd:
            best, bd = d, dd
    if best is None:
        return "집결지 / refuge", "shelter"
    kind_kr = "해안 집결지" if best.kind == "shelter" else "내륙 대피처"
    kind_en = "coastal refuge" if best.kind == "shelter" else "inland refuge"
    idx = "".join(ch for ch in best.name if ch.isdigit()) or "?"
    return f"{kind_kr} {idx} / {kind_en} {idx} (합성/synthetic)", best.kind


# ---------------------------------------------------------------------------
# Build representative cases from the REAL pipeline output
# ---------------------------------------------------------------------------


def build_cases(scenario, results, triage):
    """Two-three representative operator/resident cases from the actual run."""
    depots = scenario.depots
    by_node = {o.home_node: o for o in triage.outcomes}

    # (1) a self-evacuating resident routed to a rescue-reachable refuge (saved).
    saved = None
    ex = results.examples
    if ex.get("resident_origin_xy") and ex.get("resident_rescue_xy"):
        ox, oy = ex["resident_origin_xy"]
        route = ex["resident_rescue_xy"]
        rx, ry = route[-1]
        dkr, den = _bearing(ox, oy, rx, ry)
        ref_kr, _ = _nearest_dest_name(scenario, rx, ry)
        dist_m = sum(math.dist(route[i], route[i + 1]) for i in range(len(route) - 1))
        walk_min = (dist_m / scenario.cfg.elderly_walk_speed_ms) / 60.0
        saved = {"kind": "self_evac", "outcome": "saved_by_rescue_reachable_refuge",
                 "dir_kr": dkr, "dir_en": den, "refuge": ref_kr,
                 "dist_m": dist_m, "walk_min": walk_min,
                 "exposure": ex.get("resident_rescue_exposure")}

    # (2) the most-urgent rescued_in_time dispatch home (immobile, rescuer en route).
    rescued = None
    for o in triage.outcomes:
        if o.outcome == "rescued_in_time":
            depot = depots[o.depot_index] if o.depot_index is not None else None
            dkr, den = (_bearing(o.x, o.y, depot.x, depot.y) if depot else ("동", "E"))
            rescued = {"kind": "rescued", "outcome": o.outcome, "home_node": o.home_node,
                       "eta": o.responder_eta_min, "arrival": o.arrival_min,
                       "window": o.closing_window_min, "unit": o.assigned_unit,
                       "dir_kr": dkr, "dir_en": den}
            break

    # (3) a capacity-deferred home (honest — a surviving route exists but no unit in time).
    deferred = None
    for o in triage.outcomes:
        if o.outcome == "capacity_deferred":
            depot = depots[o.depot_index] if o.depot_index is not None else None
            dkr, den = (_bearing(o.x, o.y, depot.x, depot.y) if depot else ("동", "E"))
            deferred = {"kind": "deferred", "outcome": o.outcome, "home_node": o.home_node,
                        "eta": o.responder_eta_min, "window": o.closing_window_min,
                        "dir_kr": dkr, "dir_en": den}
            break

    return saved, rescued, deferred


def sms_for(case) -> str:
    """A short, imperative Korean SMS (not 합니다체), auto-filled from the route."""
    if case is None:
        return ""
    if case["kind"] == "self_evac":
        return (f"○○○님, 지금 바로 {case['dir_kr']}쪽 {case['refuge'].split(' / ')[0]}(으)로 "
                f"대피하세요. 도보 약 {case['walk_min']:.0f}분. 길 안내: 집 앞 큰길을 따라 "
                f"{case['dir_kr']}쪽으로 이동. 산불 접근 중, 지체 말고 출발하세요.")
    if case["kind"] == "rescued":
        return (f"○○○님, 구조대가 약 {case['eta']:.0f}분 뒤 도착 예정입니다. 문 닫고 집 안에서 "
                f"대기하세요. 움직일 수 있으면 {case['dir_kr']}쪽 도로변으로 나와 기다리세요. "
                f"전화 받을 수 있게 해 두세요.")
    # deferred — honest, no false ETA
    return (f"○○○님, 구조 요청이 접수됐습니다. 지금은 구조대가 부족해 대기 중입니다. 가능하면 "
            f"이웃·가족과 함께 {case['dir_kr']}쪽으로 대피를 시도하고, 어려우면 집에서 가장 "
            f"안전한 곳에 머무르며 연락을 유지하세요.")


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

_OUTCOME_KR = {"rescued_in_time": "제때 구조", "capacity_deferred": "용량 초과 보류",
               "geometry_unreachable": "접근로 차단"}
_OUTCOME_COLOR = {"rescued_in_time": "#10b981", "capacity_deferred": "#f59e0b",
                  "geometry_unreachable": "#dc2626",
                  "saved_by_rescue_reachable_refuge": "#2563eb"}


def dispatch_rows(scenario, results, triage, n=7):
    """Operator/responder dispatch-table rows from the real triage outcomes."""
    rows = []
    depots = scenario.depots
    for o in triage.outcomes[:n]:
        depot = depots[o.depot_index] if o.depot_index is not None else None
        dkr, den = (_bearing(o.x, o.y, depot.x, depot.y) if depot else ("-", "-"))
        rows.append([
            f"#{o.home_node}",
            f"{_OUTCOME_KR[o.outcome]}\n{o.outcome}",
            (f"구조대 {o.assigned_unit}호 → 자택\nunit {o.assigned_unit} → home"
             if o.outcome == "rescued_in_time" else "추가 자원 필요\nneeds more units"),
            f"{dkr} / {den}",
            f"{o.responder_eta_min:.0f}",
            f"{o.closing_window_min:.0f}",
        ])
    # one honest geometry-unreachable row (no surviving corridor)
    if results.unreachable_homes:
        u = results.unreachable_homes[0]
        rows.append([f"#{u['home_node']}",
                     f"{_OUTCOME_KR['geometry_unreachable']}\ngeometry_unreachable",
                     "광역/항공 지원 요청\nescalate (air/region)", "-", "-",
                     (f"{u['best_closing_window_min']:.0f}"
                      if u.get("best_closing_window_min") is not None else "-")])
    return rows


def render(scenario, results, triage, cases):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _setup_font()

    fig = plt.figure(figsize=(16, 8.5), constrained_layout=True)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 1.0])

    # ---- left: operator dispatch table ----
    axL = fig.add_subplot(gs[0, 0]); axL.axis("off")
    cap = triage
    axL.set_title(
        f"구조 우선순위 출동표 (운영자/복지사 화면)  /  Prioritized dispatch table (operator view)\n"
        f"구조 필요 {cap.n_dispatch + len(results.unreachable_homes)}가구 · 차량 {cap.n_rescue_units}대 · "
        f"제때구조 {cap.n_rescued_in_time} / 보류 {cap.n_capacity_deferred} / 접근불가 "
        f"{len(results.unreachable_homes)}",
        fontsize=10.5, loc="left")
    headers = ["가옥\nhome", "분류\noutcome", "배정·집결지\nassignment",
               "방향\ndir", "ETA\n(분)", "잔여창\nclose(분)"]
    rows = dispatch_rows(scenario, results, triage)
    tbl = axL.table(cellText=rows, colLabels=headers, loc="center", cellLoc="left",
                    colWidths=[0.13, 0.24, 0.30, 0.12, 0.10, 0.11])
    tbl.auto_set_font_size(False); tbl.set_fontsize(8.2); tbl.scale(1, 2.4)
    for j in range(len(headers)):
        c = tbl[0, j]; c.set_facecolor("#1f2937"); c.set_text_props(color="white", fontweight="bold")
    for i, o in enumerate(list(triage.outcomes[:7]) + ([1] if results.unreachable_homes else []), start=1):
        oc = (o.outcome if hasattr(o, "outcome") else "geometry_unreachable")
        tbl[i, 1].set_facecolor(_OUTCOME_COLOR[oc]); tbl[i, 1].set_text_props(color="white")

    # ---- right: SMS cards ----
    axR = fig.add_subplot(gs[0, 1]); axR.axis("off")
    axR.set_title("자동 생성 주민 안내 문자 (예시)  /  Auto-generated resident SMS (examples)",
                  fontsize=10.5, loc="left")
    cards = [(c, t) for c, t in zip(cases, ("자력 대피 / self-evacuate",
                                            "구조대 출동 / rescuer dispatched",
                                            "용량 초과 보류 / capacity-deferred")) if c]
    y = 0.94
    for case, tag in cards:
        col = _OUTCOME_COLOR[case["outcome"]]
        axR.add_patch(plt.Rectangle((0.02, y - 0.27), 0.96, 0.25, transform=axR.transAxes,
                                    facecolor="#f8fafc", edgecolor=col, lw=2.0, zorder=1))
        axR.text(0.05, y - 0.03, f"▌{tag}", transform=axR.transAxes, fontsize=9.5,
                 color=col, fontweight="bold", va="top")
        axR.text(0.05, y - 0.085, _wrap(sms_for(case), 34), transform=axR.transAxes,
                 fontsize=9.0, va="top", family=plt.rcParams["font.family"])
        y -= 0.30

    fig.suptitle("영덕 PoC 운영자 출력 예시 (연구 파이프라인 산출물 · 합성/태깅 지형 · 실제 제품 아님)  /  "
                 "Yeongdeok PoC operator output — illustrative pipeline output on "
                 "synthetic-and-tagged geometry, NOT a deployed product",
                 fontsize=11.5)
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / "operator_output.png", dpi=135, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / "operator_output.png")


def _wrap(s, width):
    out, line = [], ""
    for tok in s.split(" "):
        if len(line) + len(tok) + 1 > width:
            out.append(line); line = tok
        else:
            line = (line + " " + tok).strip()
    if line:
        out.append(line)
    return "\n".join(out)


def write_text(scenario, results, triage, cases):
    lines = [
        "영덕 구조 PoC — 운영자 출력 예시 / Yeongdeok rescue PoC — operator output sample",
        "*** 연구 파이프라인의 예시 산출물입니다. 합성·태깅 지형, 실제 주민 아님, 배포 제품 아님. ***",
        "*** Illustrative output of the research pipeline on synthetic-and-tagged geometry;",
        "    not real residents, not a deployed product. Names shown as ○○○ (filled from",
        "    the operator's resident registry in a deployment). ***",
        "",
        f"capacity (PoC, not measured): {triage.n_rescue_units} units, "
        f"{triage.rescue_service_time_min:.0f} min/rescue, window {triage.window_min:.0f} min",
        f"needs-rescuer {triage.n_dispatch + len(results.unreachable_homes)} = "
        f"rescued_in_time {triage.n_rescued_in_time} + capacity_deferred "
        f"{triage.n_capacity_deferred} + geometry_unreachable {len(results.unreachable_homes)}",
        "",
        "=== PRIORITIZED DISPATCH TABLE (operator/responder view) ===",
        f"{'home':>10} | {'outcome':<22} | {'dir':<4} | {'ETA':>4} | {'close':>5} | assignment",
    ]
    depots = scenario.depots
    for o in triage.outcomes[:10]:
        depot = depots[o.depot_index] if o.depot_index is not None else None
        _, den = (_bearing(o.x, o.y, depot.x, depot.y) if depot else ("-", "-"))
        assign = (f"unit {o.assigned_unit} -> home" if o.outcome == "rescued_in_time"
                  else "needs more units")
        lines.append(f"{('#'+str(o.home_node)):>10} | {o.outcome:<22} | {den:<4} | "
                     f"{o.responder_eta_min:>4.0f} | {o.closing_window_min:>5.0f} | {assign}")
    if results.unreachable_homes:
        u = results.unreachable_homes[0]
        lines.append(f"{('#'+str(u['home_node'])):>10} | {'geometry_unreachable':<22} | "
                     f"{'-':<4} | {'-':>4} | {'-':>5} | escalate (air/region support)")
    lines += ["", "=== AUTO-GENERATED RESIDENT SMS (examples) ==="]
    for case, tag in zip(cases, ("self-evacuate", "rescuer dispatched", "capacity-deferred")):
        if case:
            lines += [f"[{tag} | {case['outcome']}]", sms_for(case), ""]
    TXT.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", TXT)


def main() -> int:
    print("Building 영덕 rescue PoC (baseline, full origin set) ...")
    cfg = RescueConfig()
    scenario = build_synthetic_demo(cfg)
    results = run_pipeline(scenario, cfg)
    triage = capacity_triage(results.dispatch, cfg,
                             RescueCapacityConfig(n_rescue_units=3, rescue_service_time_min=25.0))
    print(f"  dispatch {triage.n_dispatch}: rescued {triage.n_rescued_in_time} / "
          f"deferred {triage.n_capacity_deferred}; geometry-unreachable "
          f"{len(results.unreachable_homes)}")
    cases = build_cases(scenario, results, triage)
    render(scenario, results, triage, cases)
    write_text(scenario, results, triage, cases)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
