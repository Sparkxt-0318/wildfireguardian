#!/usr/bin/env python
"""Build the offline FIELD VIEW page (web/field_view.html) — SVG only.

Session 8, Phase 4. The interview described the radio-app-over-basestation
rail responders already carry — Korea's 재난안전통신망 (nationwide PS-LTE
public safety network, nationwide service since May 2021, unifying
경찰/소방/해경 with agency-specific applications). The architectural stance is
therefore: **format outputs as a feed for that existing rail, not a new
channel** — 재난안전통신망 연동을 상정하여 설계하였습니다 (designed on the
assumption of integration; never claimed as integrated, connected or
deployed).

Doctrinal framing: **LCES** (Lookouts, Communications, Escape routes, Safety
zones — Gleason 1991, *Fire Management Notes* 52(4); the NWCG standard). This
screen automates two of the four elements: a synthetic **lookout** (the
hazard field + isochrones) and an **escape-route monitor** (the ingress
corridor + the Phase-1b withdrawal trigger line + the Phase-1a margin).

Fully offline: one self-contained HTML file, inline SVG + CSS + inline JS,
no tile server, no CDN, no live API, no external font. The page passes the
same external-reference gate as every other screen.

Output: web/field_view.html  (served at GET /field by the console app)
Run:  python scripts/build_field_view.py
"""

from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash  # noqa: E402
from wildfireguardian.routing.margins import (  # noqa: E402
    round_trip_margin, withdrawal_trigger_line,
)
from wildfireguardian.routing.rescue import RescueConfig  # noqa: E402
from wildfireguardian.routing.rescue_demo import build_real_demo, run_pipeline  # noqa: E402

OUT = REPO / "web" / "field_view.html"

#: Isochrone offsets (min) from the display clock, per the Phase-4 brief.
ISO_OFFSETS = (30.0, 60.0, 90.0)


def _cells_at(hazard, t_min: float, cutoff: float) -> list[tuple[int, int]]:
    """Cells at/above ``cutoff`` at the forecast slice nearest ``t_min``."""
    idx = int(np.argmin(np.abs(hazard.times_min - t_min)))
    s = hazard.surfaces[idx]
    rows, cols = np.where(s >= cutoff)
    return list(zip(rows.tolist(), cols.tolist())), float(hazard.times_min[idx])


def main() -> int:
    print("[1/3] building REAL scenario (arm-B networks; synthetic hazard) ...")
    cfg = RescueConfig(use_osm=True)
    scenario = build_real_demo(cfg)
    results = run_pipeline(scenario, cfg)
    if not results.dispatch:
        print("STOP: no dispatch mission to display", file=sys.stderr)
        return 2

    # Display mission: the most urgent dispatch entry whose round-trip margin
    # is still positive — i.e. the mission where the withdrawal trigger line
    # is an open decision. (The most urgent entry outright often has a
    # negative margin — that is the Phase-1 finding — but a screen built to
    # show the trigger line should show a mission that still has one. The
    # choice is recorded on the page.)
    depot_nodes = [scenario.drive.nearest_node(d.x, d.y) for d in scenario.depots]
    e = m = None
    import math as _math
    for cand in results.dispatch:
        mm = round_trip_margin(scenario.drive, depot_nodes[cand.depot_index],
                               cand.home_node, scenario.hazard, cfg,
                               depot_index=cand.depot_index)
        if _math.isfinite(mm.margin_minutes) and mm.margin_minutes > 0:
            e, m = cand, mm
            break
    if e is None:                       # every margin non-positive: show No.1
        e = results.dispatch[0]
        m = round_trip_margin(scenario.drive, depot_nodes[e.depot_index],
                              e.home_node, scenario.hazard, cfg,
                              depot_index=e.depot_index)
    depot_node = depot_nodes[e.depot_index]
    trigger = withdrawal_trigger_line(scenario.hazard, cfg, m)

    # Mission corridor geometry (shortest-time drive path, as in the margin).
    import networkx as nx
    _, path = nx.single_source_dijkstra(scenario.drive.graph, depot_node,
                                        target=e.home_node, weight="time_min")
    corridor = [scenario.drive.node_xy(n) for n in path]

    g = scenario.hazard_grid
    W, H = 960.0, 640.0

    def sx(x: float) -> float:
        return (x - g.minx) / (g.maxx - g.minx) * W

    def sy(y: float) -> float:
        return (g.maxy - y) / (g.maxy - g.miny) * H

    def cell_rects(cells, fill, opacity, extra="", grid=None) -> str:
        gg = grid or g
        cw = gg.cell_size_m / (g.maxx - g.minx) * W
        ch = gg.cell_size_m / (g.maxy - g.miny) * H
        parts = []
        for r, c in cells:
            x, y = gg.center_xy(r, c)
            parts.append(f'<rect x="{sx(x) - cw / 2:.1f}" '
                         f'y="{sy(y) - ch / 2:.1f}" width="{cw:.1f}" '
                         f'height="{ch:.1f}" fill="{fill}" '
                         f'opacity="{opacity}" {extra}/>')
        return "".join(parts)

    # Land / sea from the scenario terrain (labelled synthetic). The terrain
    # arrays live on the ROUTE grid, not the hazard grid.
    rg = scenario.route_grid
    land = scenario.burnable_frac > 0.05
    sea_cells = [(r, c) for r in range(rg.nrows) for c in range(rg.ncols)
                 if not land[r, c]]

    front_cells, front_t = _cells_at(scenario.hazard, 0.0, cfg.vehicle_cutoff)
    iso_layers = []
    for off in ISO_OFFSETS:
        cells, t_used = _cells_at(scenario.hazard, off, cfg.vehicle_cutoff)
        iso_layers.append((off, t_used, cells))

    ign_x, ign_y = scenario.ignition_xy
    # Mock GPS: 60 % along the corridor. CLEARLY a mock, labelled on screen.
    k = max(0, int(0.6 * (len(corridor) - 1)))
    gps_x, gps_y = corridor[k]

    corridor_pts = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in corridor)

    iso_colors = ("#f4a261", "#e76f51", "#c1121f")
    svg = [f'<svg viewBox="0 0 {W:.0f} {H:.0f}" role="img" '
           f'aria-label="현장 보기(모의)" '
           f'style="width:100%;height:auto;background:#10251c">']
    svg.append(cell_rects(sea_cells, "#123a5c", "0.9", grid=rg))
    for (off, _t, cells), col in zip(reversed(iso_layers), reversed(iso_colors)):
        svg.append(cell_rects(cells, col, "0.45"))
    svg.append(cell_rects(front_cells, "#ff3b30", "0.85"))
    if trigger.cells_rc:
        svg.append(cell_rects(trigger.cells_rc, "none", "1.0",
                              extra='stroke="#b073ff" stroke-width="2" '
                                    'stroke-dasharray="4 3"'))
    svg.append(f'<polyline points="{corridor_pts}" fill="none" '
               f'stroke="#7fd8be" stroke-width="3"/>')
    svg.append(f'<circle cx="{sx(ign_x):.1f}" cy="{sy(ign_y):.1f}" r="9" '
               f'fill="#ffd166" stroke="#c1121f" stroke-width="3"/>')
    dx, dy = scenario.drive.node_xy(depot_node)
    svg.append(f'<rect x="{sx(dx)-7:.1f}" y="{sy(dy)-7:.1f}" width="14" '
               f'height="14" fill="#4cc9f0"/>')
    svg.append(f'<rect x="{sx(e.x)-6:.1f}" y="{sy(e.y)-6:.1f}" width="12" '
               f'height="12" fill="#ffffff" stroke="#000" stroke-width="2"/>')
    svg.append(f'<circle cx="{sx(gps_x):.1f}" cy="{sy(gps_y):.1f}" r="8" '
               f'fill="#2ec4b6" stroke="#ffffff" stroke-width="3"/>')
    svg.append(f'<text x="{sx(gps_x)+12:.1f}" y="{sy(gps_y)+4:.1f}" '
               f'fill="#e8fff6" font-size="15">현 위치(모의 GPS)</text>')
    svg.append(f'<text x="{sx(ign_x)+12:.1f}" y="{sy(ign_y)-8:.1f}" '
               f'fill="#ffe9a8" font-size="15">화점</text>')
    svg.append("</svg>")

    rank = results.dispatch.index(e) + 1
    margin_disp = ("∞" if not np.isfinite(m.margin_minutes)
                   else f"{m.margin_minutes:.0f}")
    trigger_note = escape(trigger.note or "")
    adv = next((a for a in results.advisories
                if a["home_node"] == e.home_node), None)
    rec = escape(adv["recommendation"]) if adv else "—"

    legend_iso = " · ".join(f"{int(off)}분" for off in ISO_OFFSETS)

    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>WildfireGuardian — 현장 보기 (모의)</title>
<style>
  body {{ margin:0; background:#0b1f17; color:#e8fff6;
         font-family:'AppleSDGothicNeo','Malgun Gothic',sans-serif; }}
  header {{ padding:14px 20px 6px; }} h1 {{ font-size:20px; margin:0; }}
  .sub {{ color:#9ad0bd; font-size:13px; margin-top:4px; }}
  .wrap {{ display:flex; gap:16px; padding:12px 20px 20px; flex-wrap:wrap; }}
  .map {{ flex:3; min-width:480px; }}
  .panel {{ flex:1; min-width:260px; background:#122b21; border-radius:10px;
            padding:14px 16px; }}
  .margin {{ font-size:44px; font-weight:700; }}
  .margin.neg {{ color:#ff6b6b; }} .margin.pos {{ color:#7fd8be; }}
  .k {{ color:#9ad0bd; font-size:12px; }} .v {{ font-size:15px; margin-bottom:8px; }}
  .legend {{ font-size:12px; color:#cfeee2; margin-top:8px; line-height:1.7; }}
  .foot {{ padding:0 20px 18px; color:#87b3a4; font-size:12px; line-height:1.6; }}
  .sw {{ display:inline-block; width:10px; height:10px; margin-right:4px; }}
</style>
</head>
<body>
<header>
  <h1>현장 보기 — 출동 {rank}순위 임무 (모의 화면 · 왕복 여유가 남은 최상위
  임무를 표시)</h1>
  <div class="sub">재난안전통신망 연동을 상정하여 설계하였습니다 — 연동·배포된
  시스템이 아니며, 대원이 이미 휴대한 단말의 피드 형식을 모사한 화면입니다.
  LCES(Gleason 1991) 중 감시(Lookouts)와 탈출로(Escape routes) 두 요소를
  자동화합니다.</div>
</header>
<div class="wrap">
  <div class="map">{''.join(svg)}
  <div class="legend">
    <span class="sw" style="background:#ff3b30"></span>현재 화선(모형 컷오프 초과)
    <span class="sw" style="background:#f4a261"></span>예측 확산 {legend_iso} 등시선
    <span class="sw" style="background:#b073ff"></span>철수 트리거 라인(계획 단위)
    <span class="sw" style="background:#7fd8be"></span>진입 경로
    <span class="sw" style="background:#4cc9f0"></span>출동 거점
    <span class="sw" style="background:#ffffff"></span>구조 대상 가옥
  </div>
  </div>
  <div class="panel">
    <div class="k">왕복 여유 (계획 단위 · 분)</div>
    <div class="margin {'neg' if (np.isfinite(m.margin_minutes) and m.margin_minutes <= 0) else 'pos'}"
         id="margin" data-margin="{margin_disp}">{margin_disp}</div>
    <div class="k">권고</div><div class="v">{rec}</div>
    <div class="k">진입 소요(출동지연 포함)</div><div class="v">{m.eta_in_min:.0f}분</div>
    <div class="k">현장 체류(가정값)</div><div class="v">{m.t_load_min:.0f}분 (assumed)</div>
    <div class="k">복귀 정책</div><div class="v">동일 경로 복귀(자문 진술 기반 원칙)</div>
    <div class="k">트리거 라인</div><div class="v">{trigger_note or '표시됨(보라 점선)'}</div>
    <div class="k">유의</div>
    <div class="v">위험장 시간 해상도는 위성 재방문 주기(시간 단위)입니다 —
    본 화면은 계획 지원용이며 분 단위 전술 판단용이 아닙니다.</div>
  </div>
</div>
<div class="foot">
  자료 계보: 도로망 OSM(실측 지오메트리) · 위험장/지형 합성(라벨됨) · GPS 모의 ·
  생성 스크립트 scripts/build_field_view.py · config {config_hash()[:12]} ·
  본 화면의 어떤 요소도 외부 서버를 호출하지 않습니다.
</div>
<script>
/* 계획-단위 카운트다운: 표시값은 분 단위 왕복 여유. 시간 해상도 주의 문구가
   함께 표시되며, 초 단위 정밀도를 시사하지 않도록 분 단위로만 감소시킵니다. */
(function () {{
  var el = document.getElementById("margin");
  var v = parseFloat(el.getAttribute("data-margin"));
  if (!isFinite(v)) return;
  setInterval(function () {{
    v -= 1; el.textContent = v.toFixed(0);
    if (v <= 0) el.className = "margin neg";
  }}, 60000);
}})();
</script>
</body>
</html>
"""
    OUT.write_text(html, encoding="utf-8")
    meta = {
        "mission_home_node": int(e.home_node),
        "margin_minutes": (None if not np.isfinite(m.margin_minutes)
                           else round(float(m.margin_minutes), 2)),
        "trigger_cells": len(trigger.cells_rc),
        "front_slice_min": front_t,
    }
    print(f"[3/3] wrote {OUT}  {json.dumps(meta, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
