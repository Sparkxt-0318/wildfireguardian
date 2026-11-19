"""One row per village, in Korean and in English, shared by the CSV and the A4 sheets."""
from __future__ import annotations

import csv
import io
import re

from . import fmt
from .engine import sort_key

TOWN_METHOD = {
    "legal_ri_unique": ("확정 (법정리 이름)", "established (legal-ri name)"),
    "legal_ri_ambiguous_nearest": ("추정 (같은 이름 법정리 여럿; 가까운 마을 기준)", "estimate (duplicate legal-ri name; nearest villages)"),
    "name_contains_legal": ("추정 (이름 속 법정리·동)", "estimate (legal name inside the place name)"),
    "nearest_established": ("추정 (가까운 마을 기준)", "estimate (nearest established villages)"),
    "unknown": ("미확인", "unknown"),
}
CATEGORY = {"village": ("마을", "village"), "hamlet": ("마을(소규모)", "hamlet"),
            "nursing_home": ("요양시설", "nursing home"), "social_facility": ("복지시설", "social facility")}

COLUMNS = [
    ("county", "시군", "county"),
    ("town", "읍면동", "town (eup/myeon/dong)"),
    ("town_basis", "읍면동 판정", "town assignment"),
    ("village", "마을·시설", "village or facility"),
    ("type", "구분", "type"),
    ("stage_now", "현재 단계", "stage now"),
    ("fire_arrival", "화재 도달 (KST)", "fire arrival (KST)"),
    ("stage_immediate_at", "'즉시 실행' 전환 시각 (KST)", "becomes 'execute now' at (KST)"),
    ("windows", "안전 출발 가능 시간대 (KST)", "safe departure windows (KST)"),
    ("windows_by_shelter", "대피소별 안전 출발 시간대 (KST)", "safe departure windows by shelter (KST)"),
    ("leave_by", "출발 마감 (KST)", "leave by (KST)"),
    ("road_cut", "마지막 도로 차단 (KST)", "last road out cut (KST)"),
    ("road_status", "도로 차단 상태", "road status"),
    ("gap_min", "도로 차단 후 화재 도달까지 (분)", "minutes from road cut to fire arrival"),
    ("stage_at_cut", "도로 차단 시점의 단계", "stage when the road is cut"),
    ("flag", "경고: '즉시 실행' 전에 도로 차단", "flag: road cut before 'execute now'"),
    ("shelter_last", "마지막 출발 시 대피소", "shelter for the last departure"),
    ("travel_last_min", "마지막 출발 시 이동 (분)", "travel for the last departure (min)"),
    ("route_last", "마지막 출발 경로 (OSM way)", "route for the last departure (OSM ways)"),
    ("shelter_now", "지금 출발 시 대피소", "shelter if leaving at the issue time"),
    ("travel_now_min", "지금 출발 시 이동 (분)", "travel if leaving at the issue time (min)"),
    ("route_now", "지금 출발 경로 (OSM way)", "route if leaving at the issue time (OSM ways)"),
    ("refusal", "계산 거부 사유", "refusal reason"),
    ("place_id", "장소 ID", "place id"),
    ("certificate", "인증서", "certificate"),
    ("windows_s", "출발 가능 구간 (발표 후 초)", "departure windows (s after issue)"),
    ("leave_by_s", "출발 마감 (발표 후 초)", "leave by (s after issue)"),
    ("road_cut_s", "도로 차단 (발표 후 초)", "road cut (s after issue)"),
    ("fire_arrival_s", "화재 도달 (발표 후 초)", "fire arrival (s after issue)"),
    ("notice", "고지", "notice"),
]


def safe_id(pid: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", pid)


def ways(road, legs):
    out = []
    for leg in legs or []:
        if leg[0] == "EDGE":
            w = road.source_way[leg[1]]
            if w is not None and (not out or out[-1] != w):
                out.append(w)
    return " ".join(str(w) for w in out)


def village_name(o, lang):
    if o["name"]:
        return o["name"] if lang == "ko" else "%s (%s)" % (fmt.place_en(o["name"]), o["name"])
    return ("이름 없는 시설 · %s" % o["id"]) if lang == "ko" else ("unnamed facility · %s" % o["id"])


def town_label(o, lang):
    if not o["eupmyeon"]:
        return "읍면동 미확인" if lang == "ko" else "town unknown"
    return o["eupmyeon"] if lang == "ko" else "%s (%s)" % (fmt.romanize(o["eupmyeon"]), o["eupmyeon"])


def county_label(o, lang):
    if not o["sigungu"]:
        return "시군 미확인" if lang == "ko" else "county unknown"
    return o["sigungu"] if lang == "ko" else "%s (%s)" % (fmt.romanize(o["sigungu"]), o["sigungu"])


def fields(row, lang, ctx):
    """Ordered values of COLUMNS for one village."""
    ko = lang == "ko"
    o = row["origin"]
    issue = ctx["issue"]
    H = ctx["horizon_s"]
    st = ctx["settings"]["stage"]
    v = {c[0]: "" for c in COLUMNS}
    v["county"] = county_label(o, lang)
    v["town"] = town_label(o, lang)
    v["town_basis"] = TOWN_METHOD.get(o["town_method"], TOWN_METHOD["unknown"])[0 if ko else 1]
    v["village"] = village_name(o, lang)
    cat = CATEGORY.get(o["category"], (o["category"] or "", o["category"] or ""))
    v["type"] = cat[0 if ko else 1] + ((" · 취약" if ko else " · vulnerable") if o["vulnerable"] else "")
    v["place_id"] = o["id"]
    v["notice"] = fmt.NOTICE[lang]
    if row["refusal"]:
        v["refusal"] = row["refusal"][1 if ko else 2]
        return v
    v["certificate"] = "certificates/villages/%s.json" % safe_id(o["id"])
    A, cut, L = row["A"], row["cut"], row["L"]
    end_txt = fmt.full(fmt.t_floor(issue, H))

    def S(k):
        return fmt.STAGE[k][lang]

    if row["stage_now"]:
        v["stage_now"] = S(row["stage_now"])
    else:
        v["stage_now"] = ("판단 불가 (예측 범위 %g시간 < %g시간 기준)" % (H / 3600, st["standby_hours"]) if ko else
                          "cannot tell (horizon %g h < %g h threshold)" % (H / 3600, st["standby_hours"]))
    if A is None:
        v["fire_arrival"] = ("예측 범위 안 도달 없음 (%s 이후)" % end_txt) if ko else ("not within the horizon (after %s)" % end_txt)
    elif A == 0:
        v["fire_arrival"] = ("발표 시각에 이미 도달 (%s)" % fmt.full(fmt.t_floor(issue, 0))) if ko else \
            ("already there at the issue time (%s)" % fmt.full(fmt.t_floor(issue, 0)))
    else:
        v["fire_arrival"] = fmt.full(fmt.t_floor(issue, A))
    if row["stage_immediate_at"] is not None:
        v["stage_immediate_at"] = fmt.full(fmt.t_floor(issue, int(row["stage_immediate_at"])))
    elif row["stage_now"] == "즉시 실행":
        v["stage_immediate_at"] = "이미 즉시 실행" if ko else "already 'execute now'"
    else:
        v["stage_immediate_at"] = "예측 범위 밖" if ko else "beyond the horizon"

    def win(ivs):
        parts = []
        for lo, hi in ivs:
            a, b = fmt.t_ceil(issue, lo), fmt.t_floor(issue, hi)
            if a > b:
                parts.append("%s (1분 미만)" % fmt.full(fmt.t_floor(issue, lo)) if ko else "%s (under 1 min)" % fmt.full(fmt.t_floor(issue, lo)))
            else:
                parts.append("%s–%s" % (fmt.full(a), fmt.full(b)[11:] if a.date() == b.date() else fmt.full(b)))
        return "; ".join(parts) if parts else ("없음" if ko else "none")

    v["windows"] = win(row["windows"])
    v["windows_s"] = ";".join("%d-%d" % (lo, hi) for lo, hi in row["windows"])
    v["windows_by_shelter"] = " | ".join("%s: %s" % (p["shelter"]["name"] or p["shelter"]["id"], win(p["set"])) for p in row["per_shelter"])
    if row["leave_by"] is not None and cut is None:
        v["leave_by"] = ("예측 범위 안 마감 없음 (계산된 마지막 출발 %s)" % fmt.full(fmt.t_floor(issue, row["leave_by"]))) if ko else \
            ("no deadline within the horizon (last departure computed %s)" % fmt.full(fmt.t_floor(issue, row["leave_by"])))
        v["leave_by_s"] = str(row["leave_by"])
    elif row["leave_by"] is not None:
        v["leave_by"] = fmt.full(fmt.t_floor(issue, row["leave_by"]))
        v["leave_by_s"] = str(row["leave_by"])
    else:
        v["leave_by"] = "없음 (발표 시각에 이미 출발 불가)" if ko else "none (no safe departure at the issue time)"
    if cut is None:
        v["road_cut"] = ("예측 범위 안 차단 없음 (%s까지)" % end_txt) if ko else ("not cut within the horizon (to %s)" % end_txt)
        v["road_status"] = "예측 범위 안 차단 없음" if ko else "not cut within the horizon"
    elif cut == 0:
        v["road_cut"] = ("발표 시각 이전 (%s)" % fmt.full(fmt.t_floor(issue, 0))) if ko else ("at or before the issue time (%s)" % fmt.full(fmt.t_floor(issue, 0)))
        v["road_status"] = ("발표 시각에 이미 차단 (마을에 화재 도달)" if A == 0 else "발표 시각에 이미 차단") if ko else \
            ("already cut at the issue time (fire at the village)" if A == 0 else "already cut at the issue time")
        v["road_cut_s"] = "0"
    else:
        v["road_cut"] = fmt.full(fmt.t_floor(issue, cut))
        v["road_status"] = "차단" if ko else "cut"
        v["road_cut_s"] = str(cut)
    if A is not None:
        v["fire_arrival_s"] = str(A)
    if cut is not None:
        if row["gap"] is not None:
            v["gap_min"] = str(fmt.minutes_floor(row["gap"]))
        else:
            v["gap_min"] = (">%d (화재 도달이 예측 범위 밖)" % fmt.minutes_floor(H - cut)) if ko else (">%d (fire arrival beyond the horizon)" % fmt.minutes_floor(H - cut))
        if row["stage_at_cut"]:
            v["stage_at_cut"] = S(row["stage_at_cut"])
        elif row["flag"]:
            v["stage_at_cut"] = "준비 또는 실행대기" if ko else "prepare or standby"
        else:
            v["stage_at_cut"] = "판단 불가" if ko else "cannot tell"
    if row["flag"] is True:
        v["flag"] = "예" if ko else "yes"
    elif row["flag"] is False:
        v["flag"] = "아니오" if ko else "no"
    else:
        v["flag"] = "판단 불가" if ko else "cannot tell"
    road = ctx["road"]
    if row["last"] is not None:
        p = row["last"]
        v["shelter_last"] = p["shelter"]["name"] or p["shelter"]["id"]
        v["travel_last_min"] = str(-(-(p["w_last"]["arrival"] - p["L"]) // 60))  # rounded up
        v["route_last"] = ways(road, p["w_last"]["legs"])
    if row["now"] is not None:
        p = row["now"]
        v["shelter_now"] = p["shelter"]["name"] or p["shelter"]["id"]
        v["travel_now_min"] = str(-(-p["w_first"]["arrival"] // 60))  # rounded up
        v["route_now"] = ways(road, p["w_first"]["legs"])
    if not ko:
        for k in ("shelter_last", "shelter_now"):
            if v[k] and re.search(r"[가-힣]", v[k]):
                v[k] = "%s (%s)" % (fmt.place_en(v[k]), v[k])
        v["windows_by_shelter"] = " | ".join(
            "%s: %s" % ("%s (%s)" % (fmt.place_en(p["shelter"]["name"]), p["shelter"]["name"]) if p["shelter"]["name"] else p["shelter"]["id"],
                        win(p["set"])) for p in row["per_shelter"])
    return v


FRAGILITY_COLUMNS = [  # only with run --fragility (research/kcf-robust); appended after the standard columns
    ("frag_reach_km", "지금 출발: 견디는 추가 화재 확산 (km)", "leaving now: tolerated extra fire reach (km)"),
    ("frag_reach_road", "추가 확산에 먼저 끊기는 도로", "road that fails first under extra reach"),
    ("frag_timing_min", "지금 출발: 견디는 도로 차단 시각 오차 (분)", "leaving now: tolerated closure-timing error (min)"),
    ("frag_timing_road", "시각 오차에 먼저 끊기는 도로", "road that fails first under timing error"),
]


def fragility_fields(row, lang, frag):
    ko = lang == "ko"
    v = {c[0]: "" for c in FRAGILITY_COLUMNS}
    if row["refusal"]:
        return v
    f = (frag or {}).get(row["origin"]["id"])
    if f is None:
        return v
    if f.get("reach_note"):
        v["frag_reach_km"] = ("계산 안 함: " if ko else "not computed: ") + f["reach_note"]
    elif f["reach_km"] is None:
        v["frag_reach_km"] = "지금 출발 경로 없음" if ko else "no safe route now"
    else:
        v["frag_reach_km"] = ("%.3f 이상" if ko else ">= %.3f") % f["reach_km"] if f["reach_censored"] else "%.3f" % f["reach_km"]
    if f["timing_s"] is None:
        v["frag_timing_min"] = "지금 출발 경로 없음" if ko else "no safe route now"
    else:
        v["frag_timing_min"] = ("%d 이상" if ko else ">= %d") % (f["timing_s"] // 60) if f["timing_censored"] else "%d" % (f["timing_s"] // 60)
    for key, col in (("reach_binding", "frag_reach_road"), ("timing_binding", "frag_timing_road")):
        b = f.get(key)
        if b and not f.get(key.split("_")[0] + "_censored"):
            v[col] = b["label"] + ("" if b["way"] is None or b["label"].startswith("OSM way") else " (OSM way %s)" % b["way"])
    return v


def csv_bytes(rows, lang, ctx) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    frag = ctx.get("fragility")
    cols = COLUMNS + (FRAGILITY_COLUMNS if frag is not None else [])
    w.writerow([c[1] if lang == "ko" else c[2] for c in cols])
    for row in sorted(rows, key=sort_key):
        f = fields(row, lang, ctx)
        if frag is not None:
            f.update(fragility_fields(row, lang, frag))
        w.writerow([f[c[0]] for c in cols])
    data = buf.getvalue()
    # UTF-8 with BOM so that spreadsheet programs on Korean Windows open the Hangul correctly
    return ("﻿" + data).encode("utf-8")
