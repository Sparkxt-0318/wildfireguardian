"""One A4 page per 읍·면: villages sorted by earliest road cut-off, readable in 30 seconds."""
from __future__ import annotations

import io
from pathlib import Path

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import fmt
from .engine import sort_key
from .report import village_name

rl_config.invariant = 1  # reproducible bytes (no creation date, fixed document id)

RED = colors.HexColor("#B00020")
AMBER = colors.HexColor("#A15C00")
GREY = colors.HexColor("#555555")
FLAG_BG = colors.HexColor("#FDE7EA")
HEAD_BG = colors.HexColor("#E8E8E8")

_FONTS = {}


def register_fonts(paths: dict):
    if not _FONTS:
        pdfmetrics.registerFont(TTFont("Nanum", str(paths["NanumGothic.ttf"])))
        pdfmetrics.registerFont(TTFont("NanumBold", str(paths["NanumGothicBold.ttf"])))
        _FONTS["ok"] = True


T = {
    "ko": {
        "title": "%s %s · 마을별 마지막 도로 차단 시각",
        "meta": "발표 %s KST · 예측 범위 %s시간 (%s까지) · 기준 시각(as-of) %s KST%s · 단계 기준: 화재 도달까지 %s시간 이하 즉시 실행, %s시간 이하 실행대기, 그 외 준비",
        "replay": " (재현: 운영자가 지정)",
        "cols": ["#", "마을·시설", "현재 단계", "출발 마감", "마지막 도로 차단", "화재 도달", "차단→도달 (분)", "경고", "마지막 출발 대피소 (이동 분)"],
        "head_flag": "먼저 확인: 도로가 '즉시 실행' 단계 전에 끊기는 곳 %d곳 (경고 '예')",
        "head_noflag": "'즉시 실행' 단계 전에 도로가 끊기는 곳 없음",
        "head_first": "가장 먼저 끊김: %s — 도로 %s, 화재 %s",
        "head_none": "예측 범위 안에서 도로가 끊기는 마을 없음",
        "head_gap": "도로가 화재 도달보다 먼저 끊기는 곳 %d곳 (가장 큰 간격: %s %d분)",
        "head_gap0": "도로가 화재 도달보다 먼저 끊기는 곳 없음",
        "none": "없음", "nocut": "차단 없음", "to_end": "범위 끝까지", "already": "발표 시각 이전", "at_issue": "이미 도달", "beyond": "범위 밖", "at_issue_head": "이미 도달", "beyond_head": "범위 안 도달 없음",
        "yes": "예", "no": "-", "unk": "판단 불가", "refused": "계산 거부: %s",
        "notes": [
            "출발 마감: 이 시각까지 출발하면 후보 대피소(가까운 %d곳) 중 하나로 가는 경로가 모델상 확인됩니다 (분 단위 내림). 마지막 도로 차단: 이 시각부터 모든 경로가 모델상 끊깁니다. '차단 없음' = 예측 범위 안에서 끊기지 않음.",
            "화재 도달: 마을 진입 지점이 있는 375 m 셀에 화재가 처음 닿는 시각. 경고 '예': 도로가 끊기는 순간에도 화재 도달까지 %s시간보다 많이 남아 단계가 아직 '즉시 실행'이 아님. † 읍·면 추정.",
            "입력: %s · 도로망 OSM %s · 마을·대피소 OSM %s. 방법: F-3.1 마감 필드 (research/kcf-theorem), 연소 셀은 도달 후 계속 폐쇄, 대피소 체류 %d초, 혼잡·마을↔진입 지점 이동은 모델 밖.",
            "인증서: certificates/villages/<장소 ID>.json — 같은 폴더의 verify_certificate.py 로 이 도구 없이 다시 검증할 수 있습니다.",
        ],
        "footer": "%s · 쪽 1/1",
        "assume": "운영자 가정: 화재 자료가 없는 도로 셀 %d개를 '도달 없음'으로 처리함.",
    },
    "en": {
        "title": "%s %s · Last road out by village",
        "meta": "Issued %s KST · horizon %s h (to %s) · as-of %s KST%s · stages: %s h or less to fire arrival = execute now, %s h or less = standby, otherwise prepare",
        "replay": " (replay: set by the operator)",
        "cols": ["#", "Village / facility", "Stage now", "Leave by", "Last road out cut", "Fire arrival", "Cut→arrival (min)", "Flag", "Shelter for the last departure (travel min)"],
        "head_flag": "Check first: %d place(s) where the road is cut before the 'execute now' stage (flag 'yes')",
        "head_noflag": "No place where the road is cut before the 'execute now' stage",
        "head_first": "First road cut: %s — road %s, fire %s",
        "head_none": "No village's road is cut within the horizon",
        "head_gap": "%d place(s) where the road is cut before the fire arrives (largest gap: %s, %d min)",
        "head_gap0": "No place where the road is cut before the fire arrives",
        "none": "none", "nocut": "not cut", "to_end": "to horizon end", "already": "before issue", "at_issue": "already", "beyond": "beyond", "at_issue_head": "already there", "beyond_head": "not within the horizon",
        "yes": "yes", "no": "-", "unk": "cannot tell", "refused": "refused: %s",
        "notes": [
            "Leave by: departing up to this time, the model finds a route to one of the %d nearest candidate shelters (rounded down to the minute). Last road out cut: from this time every route is cut in the model. 'not cut' = not cut within the horizon.",
            "Fire arrival: first fire arrival in the 375 m cell of the village's road entry point. Flag 'yes': when the road is cut, more than %s h remain until fire arrival, so the stage is not yet 'execute now'. † town estimated.",
            "Inputs: %s · roads OSM %s · villages and shelters OSM %s. Method: F-3.1 deadline field (research/kcf-theorem); a burning cell stays closed after arrival; %d s stay at the shelter; congestion and travel between a village and its entry point are outside the model.",
            "Certificates: certificates/villages/<place id>.json — re-verify without this tool with verify_certificate.py in the same folder.",
        ],
        "footer": "%s · page 1/1",
        "assume": "Operator assumption: %d road cells with no fire data were read as 'not reached'.",
    },
}


def _cells(row, lang, ctx, styles):
    t = T[lang]
    o = row["origin"]
    issue = ctx["issue"]
    name = _esc(village_name(o, lang)) + (" †" if o["town_method"] != "legal_ri_unique" else "")
    if o["vulnerable"] or o["category"] in ("nursing_home", "social_facility"):
        name += " (취약)" if lang == "ko" else " (vulnerable)"
    P = lambda s, st="cell": Paragraph(s, styles[st])  # noqa: E731
    if row["refusal"]:
        return [P(name), P(_esc(t["refused"] % row["refusal"][1 if lang == "ko" else 2]), "grey")] + [""] * 6, False
    def hmf(dt, ref):
        return fmt.hm_markup(dt, ref, lang)
    sn = row["stage_now"]
    stage = fmt.STAGE[sn][lang] if sn else t["unk"]
    stage_st = {"즉시 실행": "red", "실행대기": "amber"}.get(sn, "cell")
    cut = row["cut"]
    if cut is None:
        leave = t["to_end"]
    else:
        leave = hmf(fmt.t_floor(issue, row["leave_by"]), issue) if row["leave_by"] is not None else t["none"]
    if cut is None:
        cut_s = t["nocut"]
    elif cut == 0:
        cut_s = t["already"]
    else:
        cut_s = hmf(fmt.t_floor(issue, cut), issue)
    A = row["A"]
    if A is None:
        arr = t["beyond"]
    elif A == 0:
        arr = t["at_issue"]
    else:
        arr = hmf(fmt.t_floor(issue, A), issue)
    if cut is None:
        gap = ""
    elif row["gap"] is not None:
        gap = str(fmt.minutes_floor(row["gap"]))
    else:
        gap = ">%d" % fmt.minutes_floor(ctx["horizon_s"] - cut)
    flag = {True: t["yes"], False: t["no"], None: t["unk"]}[row["flag"]]
    sh = ""
    if row["last"] is not None:
        p = row["last"]
        nm = p["shelter"]["name"] or p["shelter"]["id"]
        if lang == "en":
            nm = fmt.place_en(nm)
        sh = "%s (%d)" % (_esc(nm), -(-(p["w_last"]["arrival"] - p["L"]) // 60))
    return [P(name, "bold" if row["flag"] else "cell"), P(stage, stage_st), P(leave, "bold"), P(cut_s, "bold"), P(arr),
            P(gap), P(flag, "redbold" if row["flag"] else "cell"), P(sh)], bool(row["flag"])


def _styles(fs):
    base = ParagraphStyle("cell", fontName="Nanum", fontSize=fs, leading=fs * 1.18, alignment=TA_LEFT)
    return {
        "cell": base,
        "bold": ParagraphStyle("b", parent=base, fontName="NanumBold"),
        "red": ParagraphStyle("r", parent=base, fontName="NanumBold", textColor=RED),
        "redbold": ParagraphStyle("rb", parent=base, fontName="NanumBold", textColor=RED),
        "amber": ParagraphStyle("a", parent=base, fontName="NanumBold", textColor=AMBER),
        "grey": ParagraphStyle("g", parent=base, textColor=GREY),
        "head": ParagraphStyle("h", parent=base, fontName="NanumBold"),
        "title": ParagraphStyle("t", fontName="NanumBold", fontSize=15, leading=19),
        "meta": ParagraphStyle("m", fontName="Nanum", fontSize=7.2, leading=9, textColor=GREY),
        "lead": ParagraphStyle("l", fontName="NanumBold", fontSize=10.5, leading=13.5),
        "leadred": ParagraphStyle("lr", fontName="NanumBold", fontSize=10.5, leading=13.5, textColor=RED),
        "note": ParagraphStyle("n", fontName="Nanum", fontSize=6.6, leading=8.3, textColor=GREY),
        "notice": ParagraphStyle("x", fontName="NanumBold", fontSize=12.5, leading=15, textColor=RED, alignment=1),
        "notice2": ParagraphStyle("x2", fontName="Nanum", fontSize=7, leading=9, alignment=1),
    }


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build(path: Path, lang: str, county: str, town: str, rows, ctx) -> int:
    """Write one sheet; returns the font size used. Raises if the sheet cannot fit on one A4 page."""
    t = T[lang]
    rows = sorted(rows, key=sort_key)
    issue = ctx["issue"]
    H = ctx["horizon_s"]
    st = ctx["settings"]["stage"]
    for fs in (8.6, 8.0, 7.4, 6.8, 6.2, 5.6, 5.0):
        S = _styles(fs)
        story = []
        story.append(Table([[Paragraph(fmt.NOTICE[lang], S["notice"])], [Paragraph(_esc(fmt.NOTICE_LONG[lang]), S["notice2"])]],
                           colWidths=[186 * mm], style=TableStyle([("BOX", (0, 0), (-1, -1), 1.4, RED),
                                                                   ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)])))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(_esc(t["title"] % (county, town)), S["title"]))
        def hmf(dt, ref):
            return fmt.hm_markup(dt, ref, lang)
        story.append(Paragraph(_esc(t["meta"] % (fmt.full(fmt.t_floor(issue, 0)), "%g" % (H / 3600), fmt.full(fmt.t_floor(issue, H)),
                                                 fmt.full(fmt.kst(ctx["as_of"]).replace(second=0, microsecond=0)),
                                                 t["replay"] if ctx["as_of_given"] else "", "%g" % st["immediate_hours"],
                                                 "%g" % st["standby_hours"])), S["meta"]))
        story.append(Spacer(1, 2 * mm))
        flagged = [r for r in rows if not r["refusal"] and r["flag"]]
        cutrows = [r for r in rows if not r["refusal"] and r["cut"] is not None]
        lead = [Paragraph(_esc(t["head_flag"] % len(flagged)), S["leadred"]) if flagged else Paragraph(_esc(t["head_noflag"]), S["lead"])]
        if cutrows:
            r0 = cutrows[0]
            when = t["already"] if r0["cut"] == 0 else hmf(fmt.t_floor(issue, r0["cut"]), issue)
            arr = t["beyond_head"] if r0["A"] is None else (t["at_issue_head"] if r0["A"] == 0 else hmf(fmt.t_floor(issue, r0["A"]), issue))
            lead.append(Paragraph(t["head_first"] % (_esc(village_name(r0["origin"], lang)), when, arr), S["lead"]))
        else:
            lead.append(Paragraph(_esc(t["head_none"]), S["lead"]))
        gaps = [r for r in cutrows if (r["gap"] is not None and r["gap"] >= 60) or (r["gap"] is None and r["A"] is None)]
        if gaps:
            big = max(gaps, key=lambda r: (r["gap"] if r["gap"] is not None else ctx["horizon_s"] - r["cut"]))
            g = big["gap"] if big["gap"] is not None else ctx["horizon_s"] - big["cut"]
            lead.append(Paragraph(_esc(t["head_gap"] % (len(gaps), village_name(big["origin"], lang), fmt.minutes_floor(g))), S["lead"]))
        else:
            lead.append(Paragraph(_esc(t["head_gap0"]), S["lead"]))
        story.append(Table([[x] for x in lead], colWidths=[186 * mm], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F4F4")), ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)])))
        story.append(Spacer(1, 2.5 * mm))
        data = [[Paragraph(_esc(c), S["head"]) for c in t["cols"]]]
        style = [("BACKGROUND", (0, 0), (-1, 0), HEAD_BG), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#999999")),
                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 1.2),
                 ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]
        for i, r in enumerate(rows, start=1):
            cells, hot = _cells(r, lang, ctx, S)
            data.append([Paragraph(str(i), S["cell"])] + cells)
            if hot:
                style.append(("BACKGROUND", (0, i), (-1, i), FLAG_BG))
            if r["refusal"]:
                style.append(("SPAN", (2, i), (-1, i)))
        widths = [6, 33, 18, 18, 18, 17, 15, 12, 49]
        story.append(Table(data, colWidths=[w * mm for w in widths], repeatRows=1, style=TableStyle(style)))
        story.append(Spacer(1, 2.5 * mm))
        n = t["notes"]
        notes = [n[0] % ctx["settings"]["routing"]["shelters_per_village"], n[1] % ("%g" % st["immediate_hours"]),
                 n[2] % (ctx["fire_label"], ctx["road_date"], ctx["places_date"], ctx["settings"]["routing"]["dwell_s"]), n[3]]
        if ctx.get("assumed_uncovered"):
            notes.insert(0, t["assume"] % ctx["assumed_uncovered"])
        for s in notes:
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
                                title="%s %s" % (county, town), author="wfg-roadlayer", subject=fmt.NOTICE[lang],
                                creator="wfg-roadlayer", producer="wfg-roadlayer (reportlab)")
        doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
        if len(pages) == 1:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(buf.getvalue())
            return fs
    raise RuntimeError("sheet %s %s does not fit on one A4 page (%d rows)" % (county, town, len(rows)))
