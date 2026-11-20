"""One A4 page per 읍·면 with the fragility columns (run --fragility): villages sorted by how little extra fire
reach their route out tolerates if they leave now."""
from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import fmt
from .pdfsheet import FLAG_BG, GREY, HEAD_BG, RED, _esc, _styles
from .report import village_name

T = {
    "ko": {
        "title": "%s %s · 지금 출발하면 얼마나 견디나 (취약도)",
        "meta": "발표 %s KST · 예측 범위 %s시간 · 입력 화재 도달 래스터 기준 · 가장 취약한 마을부터",
        "cols": ["#", "마을·시설", "출발 마감", "견디는 추가 확산 (km)", "먼저 끊기는 도로 (확산)", "견디는 시각 오차 (분)", "먼저 끊기는 도로 (시각)", "세대 · 65세+ · 위험 건물"],
        "pop": "세대 %s(추정) · 65세+ %s(추정) · 위험 건물 %d/%d채(OSM 하한) · 불이 닿는 칸 세대 %s(추정)",
        "head": "추가 확산 1 km 미만에서 지금 출발 경로가 끊기는 곳 %d곳 · 지금 출발 경로가 이미 없는 곳 %d곳",
        "none": "경로 없음", "to_end": "범위 끝까지", "already": "발표 시각 이전", "refused": "계산 거부: %s", "ge": "%s 이상",
        "notes": [
            "세대·65세 이상: 읍·면·동 주민등록 통계(MOIS 2025-02, 측정)를 법정리 수로 균등 분할한 마을 값(추정). 위험 건물: OSM에 올라 있는 건물 중 예측 범위 안 불이 닿는 375 m 칸에 있는 수(하한이며 건물 간 불 번짐은 계산하지 않음).",
            "견디는 추가 확산: 화재가 입력 래스터보다 매 순간 이만큼(km) 더 멀리 번져도 지금 출발하면 안전한 경로가 남는 최대 거리 (0.125 km 간격, 최대 15 km). 래스터의 각 칸을 반경 안의 가장 이른 도달 시각으로 바꾸어 계산합니다.",
            "견디는 시각 오차: 모든 도로·마을·대피소의 차단이 이만큼(분) 더 일찍 일어나도 지금 출발 경로가 남는 최대 시간 (1분 간격). 먼저 끊기는 도로: 그 한계에서 남는 경로 중 차량이 지나는 시각과 차단 시각의 차이가 가장 작은 도로.",
            "방법: research/kcf-robust (출발 시각 고정, 차단 수준별 최단 도착 탐색, 이분 탐색). 혼잡과 마을↔진입 지점 이동은 모델 밖. 모델 출력이며 실제로 일어난 일에 대한 주장이 아닙니다.",
        ],
        "footer": "%s · 취약도 · 쪽 1/1",
    },
    "en": {
        "title": "%s %s · How much error a departure now tolerates (fragility)",
        "meta": "Issued %s KST · horizon %s h · relative to the input fire-arrival raster · most fragile first",
        "cols": ["#", "Village / facility", "Leave by", "Tolerated extra reach (km)", "Road that fails first (reach)",
                 "Tolerated timing error (min)", "Road that fails first (timing)", "Households · aged 65+ · buildings at risk"],
        "pop": "households %s (est.) · 65+ %s (est.) · at risk %d of %d bldgs (OSM, lower bound) · households in reached cells %s (est.)",
        "head": "%d place(s) whose route out now fails under less than 1 km of extra reach · %d with no safe route now",
        "none": "no route", "to_end": "to horizon end", "already": "before issue", "refused": "refused: %s", "ge": ">= %s",
        "notes": [
            "Households, aged 65+: 읍·면·동 register counts (MOIS 2025-02, measured) split equally over the 법정리 (village figure estimated). Buildings at risk: buildings mapped in OSM that stand in a 375 m cell the fire reaches within the horizon (lower bound; no fire spread between buildings).",
            "Tolerated extra reach: the largest distance (km) the fire may spread beyond the input raster, at every moment, while a safe route out still exists for leaving now (0.125 km steps, up to 15 km). Each raster pixel takes the earliest arrival within that radius.",
            "Tolerated timing error: the largest time (min) by which every road, village and shelter closure may come earlier while a safe route out still exists for leaving now (1 min steps). Road that fails first: on the route that still works at that limit, the road with the least time between the vehicle entering it and its closure.",
            "Method: research/kcf-robust (fixed departure, earliest-arrival search per closure level, bisection). Congestion and travel between a village and its entry point are outside the model. Model output, not a claim about what happened.",
        ],
        "footer": "%s · fragility · page 1/1",
    },
}


def _key(row, frag):
    if row["refusal"]:
        return (3, 0, row["origin"]["id"])
    f = frag.get(row["origin"]["id"]) or {}
    r = f.get("reach_km")
    if r is None:
        return (0, 0, row["origin"]["id"])
    return (1, r, row["origin"]["id"])


def build(path: Path, lang: str, county: str, town: str, rows, ctx, frag) -> int:
    t = T[lang]
    issue = ctx["issue"]
    rows = sorted(rows, key=lambda r: _key(r, frag))
    for fs in (8.6, 8.0, 7.4, 6.8, 6.2, 5.6, 5.0):
        S = _styles(fs)
        P = lambda s, st="cell": Paragraph(s, S[st])  # noqa: E731
        story = [Table([[Paragraph(fmt.NOTICE[lang], S["notice"])], [Paragraph(_esc(fmt.NOTICE_LONG[lang]), S["notice2"])]],
                       colWidths=[186 * mm], style=TableStyle([("BOX", (0, 0), (-1, -1), 1.4, RED),
                                                               ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)])),
                 Spacer(1, 3 * mm), Paragraph(_esc(t["title"] % (county, town)), S["title"]),
                 Paragraph(_esc(t["meta"] % (fmt.full(fmt.t_floor(issue, 0)), "%g" % (ctx["horizon_s"] / 3600))), S["meta"]),
                 Spacer(1, 2 * mm)]
        fr = [frag.get(r["origin"]["id"]) for r in rows if not r["refusal"]]
        weak = sum(1 for f in fr if f and f.get("reach_km") is not None and f["reach_km"] < 1.0)
        none = sum(1 for f in fr if f and f.get("reach_km") is None and not f.get("reach_note"))
        story.append(Table([[Paragraph(_esc(t["head"] % (weak, none)), S["leadred" if weak or none else "lead"])]], colWidths=[186 * mm],
                           style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F4F4"))])))
        story.append(Spacer(1, 2.5 * mm))
        data = [[Paragraph(_esc(c), S["head"]) for c in t["cols"]]]
        style = [("BACKGROUND", (0, 0), (-1, 0), HEAD_BG), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#999999")),
                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 1.2),
                 ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]
        for i, r in enumerate(rows, start=1):
            name = _esc(village_name(r["origin"], lang))
            if r["refusal"]:
                data.append([P(str(i)), P(name), P(_esc(t["refused"] % r["refusal"][1 if lang == "ko" else 2]), "grey"), "", "", "", "", ""])
                style.append(("SPAN", (2, i), (-1, i)))
                continue
            f = frag.get(r["origin"]["id"]) or {}
            if r["cut"] is None:
                leave = t["to_end"]
            elif r["cut"] == 0:
                leave = t["already"]
            else:
                leave = fmt.hm_markup(fmt.t_floor(issue, r["leave_by"]), issue, lang) if r["leave_by"] is not None else t["none"]
            if f.get("reach_note"):
                rk = "-"
            elif f.get("reach_km") is None:
                rk = t["none"]
            else:
                rk = "%.3f" % f["reach_km"]
                rk = t["ge"] % rk if f["reach_censored"] else rk
            if f.get("timing_s") is None:
                tm = t["none"]
            else:
                tm = "%d" % (f["timing_s"] // 60)
                tm = t["ge"] % tm if f["timing_censored"] else tm
            rb = f.get("reach_binding") if not f.get("reach_censored") else None
            tb = f.get("timing_binding") if not f.get("timing_censored") else None
            pe = f.get("people")
            pop = (t["pop"] % ("%d" % round(pe["demo"]["households"]), "—" if pe["demo"]["residents65"] is None else "%d" % round(pe["demo"]["residents65"]),
                               pe["risk"]["at_risk"], pe["risk"]["mapped"], "%d" % round(pe["risk"]["households_at_risk"]))) if pe else ""
            hot = f.get("reach_km") is None or (f.get("reach_km") is not None and f["reach_km"] < 1.0)
            data.append([P(str(i)), P(name, "bold" if hot else "cell"), P(leave), P(rk, "redbold" if hot else "bold"),
                         P(_esc(rb["label"]) if rb else ""), P(tm, "bold"), P(_esc(tb["label"]) if tb else ""), P(_esc(pop))])
            if hot:
                style.append(("BACKGROUND", (0, i), (-1, i), FLAG_BG))
        story.append(Table(data, colWidths=[w * mm for w in (6, 30, 16, 20, 34, 20, 34, 26)], repeatRows=1, style=TableStyle(style)))
        story.append(Spacer(1, 2.5 * mm))
        for s in t["notes"]:
            story.append(Paragraph(_esc(s), S["note"]))
        pages = []

        def on_page(canv, doc):
            pages.append(1)
            canv.saveState()
            canv.setFont("NanumBold", 8)
            canv.setFillColor(RED)
            canv.drawString(12 * mm, 8 * mm, fmt.NOTICE[lang])
            canv.setFont("Nanum", 7)
            canv.setFillColor(GREY)
            canv.drawRightString(198 * mm, 8 * mm, t["footer"] % ctx["run_label"])
            canv.restoreState()

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=10 * mm, bottomMargin=14 * mm,
                                title="%s %s fragility" % (county, town), author="wfg-roadlayer", subject=fmt.NOTICE[lang],
                                creator="wfg-roadlayer", producer="wfg-roadlayer (reportlab)")
        doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
        if len(pages) == 1:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(buf.getvalue())
            return fs
    raise RuntimeError("fragility sheet %s %s does not fit on one A4 page (%d rows)" % (county, town, len(rows)))
