#!/usr/bin/env python
"""Session 22 Phase 4 — the operator page for refuge-placement recommendations.

    python scripts/build_refuge_placement_page.py

Writes ``web/refuge_placement.html``. The API mounts ``web/`` wholesale, so the
page is served at ``/refuge_placement.html`` alongside the console and
``/field`` with no routing change.

FORMAT IS THE ONE THE INTERVIEWED FIREFIGHTER ASKED FOR: readable in five
minutes, not forty charts. One block per recommendation, the assumptions
printed on the page itself rather than in a report nobody opens.

⚠ EVERY PAGE CARRIES THREE WARNINGS IN THE OUTPUT ITSELF, not only in the
report, because the page is what someone will actually read:

  1. **This optimises reachability, not fire safety.** The objective is "can
     these households walk there inside the window". It does not ask whether
     the refuge survives the fire. A refuge placed where the fire arrives is
     worse than useless.
  2. **It is a geometric recommendation, not a siting decision.** Land
     ownership, construction feasibility, building standards, budget, capacity,
     staffing and opening hours are not modelled.
  3. **The counts are provisional** — the 124-building OSM snapshot, not real
     footprints (Session 21 is blocked).

Self-contained: inline CSS, no scripts, no external references of any kind.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = REPO / "data" / "processed" / "vulnerability" / "placement_cache"
OUT = REPO / "web" / "refuge_placement.html"

N_PAGES = 3


def _wgs84(x, y):
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    lon, lat = tr.transform(float(x), float(y))
    return round(lat, 6), round(lon, 6)


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def build() -> str:
    opt = json.loads((CACHE / "opt_h240_c300.json").read_text(encoding="utf-8"))
    hz = json.loads((CACHE / "horizon_robustness.json").read_text(encoding="utf-8"))
    ver = json.loads((CACHE / "verification.json").read_text(encoding="utf-8"))
    sw = json.loads((CACHE / "clearance_sweep.json").read_text(encoding="utf-8"))

    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from vulnerability_sensitivity import load_yeongdeok
    res, _ = load_yeongdeok()
    bid = list(res["buildings"].ids)
    bxy = res["buildings"].xy

    base = opt["baseline"]
    surv = ver["survival_check"]
    parts = []

    for k, t in enumerate(opt["top"][:N_PAGES], 1):
        lat, lon = _wgs84(t["x"], t["y"])
        n_after = base["n_failing"] - t["n_saved"]
        rows = []
        for h in t["saved_households"]:
            hlat, hlon = _wgs84(bxy[h][0], bxy[h][1])
            rows.append(f"<tr><td>{h}</td><td class=mono>OSM {_esc(bid[h])}</td>"
                        f"<td class=mono>{hlat:.5f}, {hlon:.5f}</td></tr>")
        parts.append(f"""
<section class=rec>
  <h2>권장 임시 대피소 위치 #{k}</h2>
  <table class=kv>
    <tr><th>좌표 (WGS84)</th><td class=mono>{lat:.6f}, {lon:.6f}</td></tr>
    <tr><th>좌표 (EPSG:5179)</th><td class=mono>{t['x']:.1f}, {t['y']:.1f}</td></tr>
    <tr><th>현재 상태</th><td>{_esc(t['host_type'])} · 산림 연료까지
        <b>{t['distance_to_forest_fuel_m']:.0f} m</b> · 가장 가까운 건물까지
        {t['distance_to_nearest_building_m']:.0f} m · 기존 대피소까지
        <b>{t['distance_to_nearest_existing_refuge_m']/1000:.1f} km</b></td></tr>
    <tr><th>동등 후보 지점</th><td>{t['n_equivalent_nodes']}곳 — 같은 가구를
        구하는 인접 지점이 그만큼 있어 <b>배치 여유가 있습니다</b></td></tr>
  </table>

  <div class=headline>
    이 위치를 개설하면<br>
    대피 불가 가구 <b>{base['n_failing']} → {n_after}</b>
    (<b>{t['n_saved']}가구 개선</b>)<br>
    개선 가구 도보 시간 중앙값
    <b>{t['walk_min_before_median']:.0f}분 → {t['walk_min_after_median']:.0f}분</b>
  </div>

  <h3>개선되는 가구 {t['n_saved']}곳</h3>
  <p class=warn">⚠ 주소가 아니라 OSM 건물 ID 와 좌표입니다. 실제 주소는
     도로명주소 건물 데이터가 들어와야 붙습니다(Session 21, 미완).</p>
  <table class=hh><tr><th>가구 index</th><th>건물 ID</th><th>좌표</th></tr>
  {''.join(rows)}
  </table>
</section>""")

    hz_rows = "".join(
        f"<tr><td>{r['horizon_min']:.0f}분</td><td>{r['n_failing']}</td>"
        f"<td>{r['best_n_saved']}</td><td>{r['k1']} → {r['k2']}</td>"
        f"<td>{r['n_unsavable']}</td></tr>" for r in hz["by_horizon"])
    sw_rows = "".join(
        f"<tr><td>{r['clearance_m']:.0f} m</td><td>{r['n_candidates']}</td>"
        f"<td>{r['best_n_saved']}</td></tr>" for r in sw["sweep"])

    return f"""<!doctype html>
<meta charset="utf-8">
<title>임시 대피소 배치 권장 — 영덕</title>
<style>
 body{{font:15px/1.65 system-ui,-apple-system,"Noto Sans KR",sans-serif;
      max-width:900px;margin:0 auto;padding:28px 20px;color:#16202a}}
 h1{{font-size:24px;margin:0 0 6px}} h2{{font-size:19px;margin:0 0 12px}}
 h3{{font-size:15px;margin:20px 0 6px}}
 .mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}}
 .rec{{border:1px solid #d3dae2;border-radius:10px;padding:20px;margin:22px 0}}
 .headline{{background:#eef4fb;border-left:4px solid #2f6fb5;padding:14px 16px;
           margin:16px 0;font-size:16px;line-height:1.9}}
 table{{border-collapse:collapse;width:100%;margin:8px 0}}
 td,th{{border:1px solid #dde3ea;padding:6px 9px;text-align:left;font-size:13px;
       vertical-align:top}}
 th{{background:#f5f8fb;font-weight:600;white-space:nowrap}}
 .kv th{{width:170px}}
 .warn{{background:#fff6e6;border-left:4px solid #d98b13;padding:12px 14px;
       margin:14px 0;font-size:13.5px}}
 .stop{{background:#fdecec;border-left:4px solid #c0392b;padding:14px 16px;
       margin:18px 0}}
 .assume{{background:#f6f7f9;border:1px dashed #c6ced8;padding:12px 14px;
         margin:14px 0;font-size:13px}}
 footer{{margin-top:34px;padding-top:14px;border-top:1px solid #dde3ea;
        font-size:12.5px;color:#5b6773}}
</style>

<h1>임시 대피소 배치 권장 — 영덕</h1>
<p>현재 <b>{base['n_households']}가구 중 {base['n_failing']}가구</b>가 평가
지평 안에 어떤 생존 대피소에도 도달하지 못합니다. 기존 대피소는
{base['n_existing_refuges']}곳입니다.</p>

<div class=stop>
 <b>⚠ 이것은 도달 가능성 최적화이지 화재 안전 최적화가 아닙니다.</b><br>
 목적함수는 <b>“이 가구들이 창 안에 걸어서 도착할 수 있는가”</b> 하나뿐이며,
 <b>그 대피소가 불을 견디는지는 묻지 않습니다.</b> 불이 도달하는 자리에 놓인
 대피소는 없느니만 못합니다. 생존 여부는 아래에서 <b>따로</b> 검사했습니다.
</div>

<div class=stop>
 <b>⚠ 이것은 기하학적 권장이지 입지 결정이 아닙니다.</b><br>
 토지 소유, 시공 가능성, 건축 기준, 예산, 수용 인원, 상주 인력, 개방 시간은
 <b>하나도 모형에 없습니다.</b> 말할 수 있는 것은 딱 이것입니다 —
 <i>“현재 가정 하에서, 이 위치에 임시 대피소를 두면 N가구가 도보 대피 가능
 범위 안으로 들어옵니다.”</i>
</div>

<div class=warn>
 <b>⚠ 모든 가구 수는 잠정입니다.</b> 실제 건물 데이터(도로명주소)가 아니라
 <b>OSM 124동 스냅숏</b> 위의 값입니다. 같은 질의가 Mati 에서 1,763동,
 Paradise 에서 988동을 돌려주는 데 비해 영덕은 74–124동으로, 농촌 한국에서
 OSM 건물 커버리지는 희소합니다. 실제 footprint 가 들어오면 <b>모든 수치가
 움직입니다.</b>
</div>

{''.join(parts)}

<h2>대피소를 하나 더 지으면?</h2>
<table><tr><th>지평</th><th>현재 실패</th><th>1개로 개선</th>
<th>1개 → 2개</th><th>어떤 배치로도 불가</th></tr>{hz_rows}</table>
<p><b>지평 240분에서 1개가 20가구, 2개가 24가구 전부</b>를 커버하고
<b>3번째는 0가구</b>를 더합니다. 한 곳만 잘 놓아도 대부분이 해결된다는 뜻입니다.</p>

<div class=warn>
 <b>⚠ 권장 위치는 지평에 따라 달라집니다.</b> 60·120·240분에서 최적 지점이
 서로 다르고, 구하는 가구 집합의 Jaccard 는 60분 대 240분에서 <b>0.435</b>에
 그칩니다. <b>이 권장은 “240분 지평에서의 권장”이며 지평과 분리해 인용할 수
 없습니다.</b>
</div>

<h2>“산에서 멀리” 기준을 바꾸면?</h2>
<table><tr><th>산림 연료 이격</th><th>후보 지점</th><th>1개로 개선</th></tr>
{sw_rows}</table>
<p>이격 기준을 0 m 에서 500 m 까지 올리면 후보는 7,651 → 498곳으로 줄지만
<b>1순위 권장이 구하는 가구 집합은 네 기준에서 모두 동일</b>합니다. 답이
기준선 위치의 산물이 아니라는 뜻입니다.</p>

<h2>검증</h2>
<ul>
 <li><b>빠른 탐색이 전체 층과 일치합니다.</b> 1순위 후보를 실제 위험원
     (타원, 발화 4개 × 시나리오 3개)으로 다시 돌린 결과 구해지는 가구 집합이
     <b>완전히 동일</b>했습니다(차집합 양쪽 0). 취약도 평균
     {ver['full_layer_verification']['vulnerability_mean_before']} →
     {ver['full_layer_verification']['vulnerability_mean_after']}.</li>
 <li><b>불이 권장 지점에 도달하는가 — {surv['n_site_scenario_evaluations']}회
     평가 중 {surv['n_reached_by_fire']}회.</b> 즉 <b>생존 필터가 구속하지
     않습니다.</b> ⚠ 이것은 “안전하다”는 보증이 아니라 <b>이 시나리오
     집합에서 이 필터가 아무것도 걸러내지 않았다</b>는 사실입니다.</li>
</ul>

<div class=assume>
 <b>전제</b> — 평가 지평 <b>240분</b>(산불통계 2,008건 근거, 기본값 불변) ·
 보행 속도 <b>고령자 0.7 m/s</b>(경사 보정) · 대피소 <b>상시 개방·수용 가능</b>
 가정 · 발화 4곳 × 기상 시나리오 3종 · 대피소 생존 판정 p_cut 0.5 ·
 도보 이동만(차량 없음).
</div>

<footer>
WildfireGuardian · Session 22 · 영덕 2025 · 이 페이지는 외부 요청을 하지
않습니다(오프라인 동작). 산출:
<span class=mono>data/processed/vulnerability/placement_cache/</span> ·
재현: <span class=mono>python scripts/refuge_placement.py --optimize</span>
</footer>
"""


def main() -> int:
    html = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} ({len(html.encode('utf-8'))/1024:.1f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
