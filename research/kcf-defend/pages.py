"""One page per issue hour, Korean and English (PROTOCOL §7). Usage: python3 pages.py RUNS_DIR"""
from __future__ import annotations

import csv, json, math, sys
from collections import defaultdict
from pathlib import Path

import aggregate as AG

HERE = AG.HERE
ROOT = AG.ROOT
sys.path.insert(0, str(ROOT))
from tools.explain_deadlines.roads import RoadGraph  # noqa: E402

NAMES = json.loads((HERE / "roadnames.json").read_text())
SIG = {}
for r in csv.DictReader(open(ROOT / "research/kcf-replay/per_place.csv")):
    SIG[r["place_id"]] = r["sigungu"]
REGION_KO = {"yeongdeok_2025": "영덕 격자", "uiseong_andong_2025": "의성·안동 격자"}
REGION_EN = {"yeongdeok_2025": "Yeongdeok grid", "uiseong_andong_2025": "Uiseong–Andong grid"}

GRAPH = {}
for reg in REGION_KO:
    raw = json.loads((ROOT / f"data/routing/graphs/{reg}/graph.json").read_text())
    g = RoadGraph(raw)
    ways = defaultdict(set)
    for e in raw["edges"]:
        for s in e["segments"]:
            ways[int(s["cell"])].add(str(e["source_way"]))
    GRAPH[reg] = (g.grid, ways)


def hav(a, b):
    lo1, la1, lo2, la2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


def nearest_place(ll):
    best = min(AG.PLACE.values(), key=lambda r: hav(ll, (float(r["lon"]), float(r["lat"]))))
    return best, hav(ll, (float(best["lon"]), float(best["lat"])))


def locate(cid, e):
    if e["type"] == "ROAD":
        reg = e["regions"][0]
        c = e["meta"][reg]["cell"]
        grid, ways = GRAPH[reg]
        x, y = grid.centre(c)
        ll = AG.TO_LL.transform(float(x), float(y))
        nm = []
        for w in sorted(ways[c]):
            v = NAMES.get(w)
            if v:
                for t in v["refs"] + ([v["name"]] if v["name"] else []):
                    if t not in nm:
                        nm.append(t)
        return ll, nm[:3], len(ways[c]), reg
    tx, ty = map(int, cid.split(":")[1].split("_"))
    ll = AG.TO_LL.transform((tx + 0.5) * 2000, (ty + 0.5) * 2000)
    nd = max(m.get("n_discs", 0) for m in e["meta"].values())
    return ll, [], nd, None


def pname(pid):
    r = AG.PLACE[pid]
    return f"{r['name'] or pid} ({SIG.get(pid, '')})"


L = {
 "ko": {
  "title": "{h}:00 KST 발령 — 산불 지연 시 대피 가능 시간이 가장 늘어나는 지점 (2025년 3월 25일 재현)",
  "warn": ("**재구성된 입력에 대한 모델 결과입니다. 실제로 사람들에게 일어난 일이 아닙니다. 어떤 진화 조치가 결과를 "
           "바꾸었을 것이라는 주장은 하지 않으며, 어떤 공무원이나 대원이 무엇을 했어야 한다는 주장도 하지 않습니다.**"),
  "conf": "구성: MEASURED 범위 곡선(3시간 확산 등급: {cls}), 예측 범위 8시간, 순위 기준 = 60분 지연. 인구: Meta HRSL 추정(거주 추정치, 당일 체류 인원 아님).",
  "state": "발령 시각 상태(174개 장소): 이미 알려진 화재 영역 안 {INSIDE}, 마지막 도로가 8시간 안에 끊김 {CUT}, 지금 출발 경로 없음 {NO_WINDOW}, 8시간 안에 끊기지 않음 {NOT_CUT_WITHIN_H}.",
  "what": ("각 후보 지점에서 화재 도달을 30/60/120분 늦추면, 각 마을이 아직 대피소까지 안전하게 떠날 수 있는 시간(F-3.1 마감 시간장)이 "
           "몇 분 늘어나는지 계산하고 인구로 가중해 합산했습니다(인·분). 도로 = 도로가 지나는 375 m 격자 한 칸, 전선 = 알려진 화재 영역의 2 km × 2 km 구간."),
  "th": "| 순위 | 유형 | 위치 | 인·분 30분 / 60분 / 120분 | 마을·분 (60분) | 도움 받는 마을 (60분, 늘어난 분) |",
  "road": "도로", "front": "전선",
  "near": "가장 가까운 장소 {n}, {d:.1f} km",
  "discs": "화재 탐지 원 {n}개",
  "none": "이 시각에는 지연으로 대피 가능 시간이 늘어나는 후보가 없습니다 (모든 마을이 이미 화재 영역 안이거나, 8시간 안에 도로가 끊기지 않음).",
  "stab": "**범위 곡선 간 안정성** (8시간, 60분): 위 10개 중 다른 곡선의 상위 10개에도 드는 수 — {ov}. MEASURED 5시간: {o5}/10. 비가중 순위: {ou}/10. 30분 순위: {o30}/10, 120분 순위: {o120}/10. 안정(다른 5개 곡선 중 4개 이상의 상위 10개): {st}.",
  "notm": "**모델에 없는 것**",
  "notm_items": [
   "대원·장비·항공기가 그 지점에 제때 **갈 수 있는지**, 그 지점을 **지킬 수 있는지**, 얼마나 오래 지킬 수 있는지. 지연은 단순히 가정한 값입니다.",
   "**항공기 제약**: 가용 대수, 왕복 시간, 바람·시정 제한, 야간 비행(3월 25일 저녁 대부분은 야간), 다른 화선에 투입된 헬기.",
   "**대원 안전**: 대피로, 안전지대, 고립 위험. 여기서 순위가 높은 지점이 대원을 보내서는 안 되는 곳일 수 있습니다.",
   "화재 거동: 지연은 범위 곡선을 균일하게 미루는 것뿐입니다. 비화, 지킨 구간을 돌아가는 확산, 재발화, 다른 화선에 대한 영향은 없습니다. 한 번에 한 지점만 지킵니다.",
   "대피 자체: 교통, 정체, 경보 전달, 이미 떠난 사람. 인구는 거주 추정치입니다.",
   "이미 화재 영역 안에 있는 마을은 이득이 0이며, 대피 가능 시간이 이미 예측 범위 끝까지 이어지는 마을도 이득이 0입니다. 이득은 8시간 범위에서 잘립니다.",
  ],
  "foot": "자료: research/kcf-defend (PROTOCOL.md, RESULTS.md, ranking.csv.gz). 좌표 WGS84.",
 },
 "en": {
  "title": "Issue {h}:00 KST — where delaying the fire would add the most safe departure time (25 March 2025 replay)",
  "warn": ("**Model output on reconstructed inputs. Not what happened to people. No claim is made that any suppression "
           "action would have changed any outcome, nor about what any official or crew should have done.**"),
  "conf": "Configuration: MEASURED reach curve (prior-3 h spread class: {cls}), 8 h horizon, ranked by the 60 min delay. Population: Meta HRSL estimate (residential estimate, not who was there that day).",
  "state": "State at issue (174 places): inside the known fire area {INSIDE}, last road cut within 8 h {CUT}, no route out now {NO_WINDOW}, not cut within 8 h {NOT_CUT_WITHIN_H}.",
  "what": ("For each candidate, fire arrival there is delayed by 30/60/120 min; the gain is the extra minutes in which each "
           "village can still leave and reach a shelter (F-3.1 deadline field), weighted by population and summed "
           "(person-minutes). Road = one 375 m routing cell with roads; front = a 2 km × 2 km section of the known fire area."),
  "th": "| Rank | Type | Location | Person-min 30 / 60 / 120 | Village-min (60) | Villages helped (60, minutes gained) |",
  "road": "road", "front": "front",
  "near": "nearest place {n}, {d:.1f} km",
  "discs": "{n} fire-detection discs",
  "none": "No candidate adds safe departure time at this hour (every village is inside the fire area or not cut within 8 h).",
  "stab": "**Stability across reach curves** (8 h, 60 min): of these ten, how many are also in each other curve's top ten — {ov}. MEASURED 5 h: {o5}/10. Unweighted ranking: {ou}/10. 30 min ranking: {o30}/10, 120 min ranking: {o120}/10. Stable (in the top ten of ≥ 4 of the other 5 curves): {st}.",
  "notm": "**Not modelled**",
  "notm_items": [
   "Whether a crew, engine or aircraft **can reach** the location in time, **hold** it, or for how long. The delay is simply imposed.",
   "**Aircraft limits**: availability, turnaround, wind and visibility limits, night flying (most of the 25 March evening is night), helicopters committed elsewhere.",
   "**Crew safety**: escape routes, safety zones, entrapment risk. A location ranked high here may be one no crew should be sent to.",
   "Fire behaviour: the delay uniformly postpones the reach curve. No spotting, no fire going around a held section, no re-ignition, no effect on other parts of the fire. One location held at a time.",
   "Evacuation itself: traffic, congestion, warning delivery, who has already left. Population is a residential estimate.",
   "Villages already inside the fire area cannot gain, nor can villages whose window already runs to the horizon. Gains are truncated at the 8 h horizon.",
  ],
  "foot": "Data: research/kcf-defend (PROTOCOL.md, RESULTS.md, ranking.csv.gz). Coordinates WGS84.",
 },
}


def page(lang, h, J, R, M, stab, numbers):
    T = L[lang]
    C = M[("MEASURED", "8h", h)]
    rows = R[("MEASURED", "8h", h, 60)][:10]
    cls = J[("yeongdeok_2025", "MEASURED", "8h", h)]["arm_class"]
    st = numbers["place_states"][f"MEASURED/8h/{h + 9:02d}"]
    out = [f"# {T['title'].format(h=f'{h + 9:02d}')}", "", T["warn"], "",
           T["conf"].format(cls=f"{cls[0]}, {cls[1]:.1f} km" if cls and cls[1] is not None else (cls[0] if cls else "-")),
           "", T["state"].format(**{k: st.get(k, 0) for k in ("INSIDE", "CUT", "NO_WINDOW", "NOT_CUT_WITHIN_H")}), "",
           T["what"], ""]
    if not rows:
        out += [T["none"], ""]
    else:
        out += [T["th"], "|---|---|---|---|---|---|"]
        for i, (cid, B, U, n) in enumerate(rows, 1):
            e = C[cid]
            ll, nm, k, reg = locate(cid, e)
            npl, dd = nearest_place(ll)
            loc = f"{ll[1]:.4f} N, {ll[0]:.4f} E; " + T["near"].format(n=pname(npl["place_id"]), d=dd / 1000)
            if e["type"] == "ROAD":
                loc += "; " + (REGION_KO if lang == "ko" else REGION_EN)[reg]
                if nm:
                    loc += "; " + ", ".join(nm)
            else:
                loc += "; " + T["discs"].format(n=k)
            pm = " / ".join(f"{score_d(e, D)[0]:,.0f}" for D in (30, 60, 120))
            g = e["gains"][60]
            helped = ", ".join(f"{pname(p)} +{s / 60:.0f}" for p, s in sorted(g.items(), key=lambda x: -AG.POP[x[0]] * x[1])[:6])
            if len(g) > 6:
                helped += f" (+{len(g) - 6})"
            out.append(f"| {i} | {T['road'] if e['type'] == 'ROAD' else T['front']} | {loc} | {pm} | {U:,.0f} | {n}: {helped} |")
        out.append("")
        s = stab[h]
        ov = ", ".join(f"{a} {v}/10" for a, v in s["overlap_8h_d60"].items())
        out += [T["stab"].format(ov=ov, o5=s["overlap_measured_5h"], ou=s["overlap_unweighted"], o30=s["overlap_d30"],
                                 o120=s["overlap_d120"], st=", ".join(str(s["primary_top10"].index(c) + 1) for c in s["stable"]) or "—"), ""]
    out += [T["notm"], ""] + [f"* {x}" for x in T["notm_items"]] + ["", f"<sub>{T['foot']}</sub>", ""]
    return "\n".join(out)


def score_d(e, D):
    return AG.score(e["gains"][D])


def main(runs):
    J, R, M, stab, numbers = AG.main(runs)
    d = HERE / "pages"
    d.mkdir(exist_ok=True)
    for h in AG.HOURS:
        for lang in ("ko", "en"):
            (d / f"{h + 9:02d}00_KST.{lang}.md").write_text(page(lang, h, J, R, M, stab, numbers))
    print("pages written", len(list(d.glob("*.md"))))


if __name__ == "__main__":
    main(sys.argv[1])
