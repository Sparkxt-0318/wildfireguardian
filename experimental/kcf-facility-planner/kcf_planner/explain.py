"""Judge-facing explanations: what changed after a delay, why (binding constraint), and what a person must check.

Everything here is derived from planner results and the case; nothing here creates or alters a schedule.
"""
from __future__ import annotations

import copy

from . import solver as S
from .model import parse_case

MARGIN_FLAG_S = 300  # a traversal within 5 minutes of a closed/unknown interval is flagged for human review

STATUS_KO = {
    "CHECKED_ROUTE": "확인된 이송 계획",
    "MISSING_INPUT": "입력 자료 누락 — 사람 확인 필요",
    "MODEL_SCOPED_NO_ROUTE": "이 모델 범위 안에서는 이송 불가",
    "UNRESOLVED": "계산 미완료 (불가 판정 아님)",
    "INVALID_INPUT": "입력 형식 오류",
}
REASON_KO = {
    "ALL_GROUPS_SUPPORTED": "모든 조가 확인된 입력만으로 이송 가능",
    "UNKNOWN_INPUT_COULD_ALLOW_EARLIER": "미확인 구간이 열려 있다면 더 빨리 끝날 수 있음 (확인 전에는 사용 불가)",
    "FEASIBLE_ONLY_IF_UNKNOWN_OPEN": "미확인(예측 누락) 구간이 열려 있어야만 가능한 계획만 존재",
    "PARTIAL_SUPPORTED_COVERAGE": "일부 조만 확인된 이송 계획이 있음",
    "OUT_OF_HORIZON": "계획 시간 범위(horizon)를 넘어서야 가능 — 범위 밖 시간은 모델이 판단하지 않음",
    "DESTINATION_WINDOW": "대피소 수용 시간 안에 하차를 마칠 수 없음",
    "DESTINATION_WINDOW_TOO_SHORT": "대피소 수용 시간이 하차 시간보다 짧음",
    "CLOSURES_BLOCK_ALL_ROUTES": "모의 통제 구간이 가능한 모든 경로를 막음",
    "CLOSURES_AND_TIME_LIMITS": "통제 구간과 시간 제한이 함께 모든 계획을 막음",
    "NO_PATH_IN_ROAD_MODEL": "도로 모델(회전 금지 포함)에 연결 경로가 없음",
    "NO_VEHICLE_ASSIGNED": "배정된 차량이 없는 조가 있음 (차량을 임의로 추가하지 않음)",
    "CAPACITY": "조 인원이 차량 좌석보다 많음",
    "SEARCH_CAP": "탐색 한도 도달 — 경로가 없다는 뜻이 아님",
    "PROOF_INCOMPLETE": "증명 미완료",
    "DIAGNOSTICS_INCOMPLETE": "불가 판정은 증명됐으나, 구체적 원인 분석은 탐색 한도로 미완료",
    "WITNESS_REPLAY_FAILED": "독립 재검증 실패로 결과를 보류함",
}


def fmt(t):
    if t is None:
        return "—"
    sign = "-" if t < 0 else ""
    t = abs(int(t))
    return "%sT+%d:%02d" % (sign, t // 60, t % 60)


def apply_delay(raw, vehicle_index, delay_s):
    c = copy.deepcopy(raw)
    c["vehicles"][vehicle_index]["available_s"] += int(delay_s)
    c["case_id"] = "%s+delay%ds" % (raw["case_id"], int(delay_s))
    return c


def fixed_path_timing(case, edge_ids, start_t, view="supported"):
    """Earliest timing along a FIXED road sequence; returns (exit times, first blocker) without rerouting."""
    g = S.Graph(case, view)
    t, rows = start_t, []
    for k, j in enumerate(edge_ids):
        e = g.by_id[j]
        last = k == len(edge_ids) - 1
        lo = case.window[0] if last else -S.INF
        hi = (min(case.window[1], case.horizon_s) - case.unload_s) if last else case.horizon_s
        d0 = max(t, lo - e.travel_s)
        hits = S.overlapping(g.block[j], d0, d0 + e.travel_s)
        d = S.earliest_free(e.travel_s, g.block[j], t, lo, hi)
        if d is None:
            return rows, {"edge_id": j, "at_s": d0, "blocked_by": [list(h) for h in hits],
                          "kind": _kind(e, d0), "limit": "horizon_or_window" if not hits else "interval"}
        rows.append({"edge_id": j, "entry_s": d, "exit_s": d + e.travel_s, "waited_s": d - t,
                     "blocked_by": [list(h) for h in hits]})
        t = d + e.travel_s
    return rows, None


def _kind(e, d):
    if S.overlapping(e.closed, d, d + e.travel_s):
        return "closed"
    if S.overlapping(e.unknown, d, d + e.travel_s):
        return "unknown"
    return None


def margins(case, trips):
    """Time between each traversal and the nearest closed/unknown interval on that edge (positive = clear)."""
    by_id = case.edge_by_id
    out = []
    for t in trips:
        for s in t["edges"]:
            e = by_id[s["edge_id"]]
            for kind, ivs in (("closed", e.closed_raw), ("unknown", e.unknown_raw)):
                for a, b in ivs:
                    if b <= a:
                        continue
                    if b <= s["entry_s"]:
                        m = s["entry_s"] - b
                    elif a >= s["exit_s"]:
                        m = a - s["exit_s"]
                    else:
                        m = -1
                    if m < MARGIN_FLAG_S:
                        out.append({"trip_id": t.get("trip_id"), "vehicle_id": t["vehicle_id"], "edge_id": e.id,
                                    "edge_name_ko": e.name_ko, "kind": kind, "interval": [a, b],
                                    "traversal": [s["entry_s"], s["exit_s"]], "margin_s": m})
    return out


def compare(raw_before, res_before, raw_after, res_after, vehicle_id):
    """Explain the change for the delayed vehicle and the final completion."""
    case_after = parse_case(raw_after)
    by_id = case_after.edge_by_id
    vb = [t for t in res_before["trips"] if t["vehicle_id"] == vehicle_id]
    va = [t for t in res_after["trips"] if t["vehicle_id"] == vehicle_id]
    va_cond = [t for t in res_after.get("conditional_trips", []) if t["vehicle_id"] == vehicle_id]
    out = {"vehicle_id": vehicle_id, "final_before_s": res_before["final_unload_s"],
           "final_after_s": res_after["final_unload_s"], "status_before": res_before["status"],
           "status_after": res_after["status"], "binding": []}
    if res_before["final_unload_s"] is not None and res_after["final_unload_s"] is not None:
        out["final_delta_s"] = res_after["final_unload_s"] - res_before["final_unload_s"]
    if not vb:
        return out
    first_before = vb[0]
    route_before = [s["edge_id"] for s in first_before["edges"]]
    after = va or va_cond
    route_after = [s["edge_id"] for s in after[0]["edges"]] if after and after[0]["kind"] == "outbound" else None
    out["route_before"] = route_before
    out["route_after"] = route_after
    out["route_changed"] = route_after is not None and route_after != route_before
    # Replay the original road sequence at the new availability: what stops it?
    v = next(x for x in case_after.vehicles if x.id == vehicle_id)
    rows, blocker = fixed_path_timing(case_after, route_before, v.available_s + case_after.board_s)
    msgs = []
    if blocker:
        e = by_id[blocker["edge_id"]]
        if blocker["blocked_by"]:
            iv = blocker["blocked_by"][0]
            kind_ko = "모의 통제" if blocker["kind"] == "closed" else "미확인(예측 누락)"
            msgs.append({"code": "ORIGINAL_ROAD_BLOCKED", "edge_id": e.id, "interval": iv, "kind": blocker["kind"],
                         "text_ko": "원래 경로의 '%s' 구간은 %s~%s %s 구간이라, 지연된 차량이 %s에 진입할 수 없습니다." % (
                             e.name_ko or e.id, fmt(iv[0]), fmt(iv[1]), kind_ko, fmt(blocker["at_s"])),
                         "text_en": "Original road %s is %s during [%s, %s); the delayed vehicle would enter at %s." % (
                             e.id, blocker["kind"], iv[0], iv[1], blocker["at_s"])})
        else:
            msgs.append({"code": "ORIGINAL_ROAD_TOO_LATE", "edge_id": e.id,
                         "text_ko": "원래 경로로는 계획 시간 범위 또는 대피소 수용 시간 안에 도착할 수 없습니다.",
                         "text_en": "On the original road the arrival would fall outside the horizon/window."})
    else:
        waited = [r for r in rows if r["waited_s"] > 0]
        for r in waited:
            e = by_id[r["edge_id"]]
            msgs.append({"code": "ORIGINAL_ROAD_NEEDS_WAIT", "edge_id": e.id, "waited_s": r["waited_s"],
                         "text_ko": "원래 경로는 '%s' 앞에서 %d초 기다려야 합니다." % (e.name_ko or e.id, r["waited_s"]),
                         "text_en": "Original road needs a %d s wait before %s." % (r["waited_s"], e.id)})
        if not waited:
            msgs.append({"code": "ORIGINAL_ROAD_STILL_OPEN",
                         "text_ko": "원래 경로를 그대로 쓸 수 있으며, 지연 시간만큼 늦어집니다.",
                         "text_en": "The original road remains usable; the delay simply shifts the journey."})
    for t in after:
        for c in t.get("binding_constraints", []):
            msgs.append({"code": "HOLD_" + c["code"], "detail": c,
                         "text_ko": "%s 대기 %d초: %s" % (t["vehicle_id"], c.get("delay_s", 0), _cause_ko(c, by_id)),
                         "text_en": "%s holds %d s: %s" % (t["vehicle_id"], c.get("delay_s", 0), c["code"])})
    out["binding"] = msgs
    return out


def _cause_ko(c, by_id):
    if c["code"] in ("EDGE_CLOSED", "EDGE_UNKNOWN"):
        e = by_id[c["edge_id"]]
        what = "모의 통제" if c["code"] == "EDGE_CLOSED" else "미확인 구간"
        return "'%s' %s %s~%s" % (e.name_ko or e.id, what, fmt(c["interval"][0]), fmt(c["interval"][1]))
    if c["code"] == "DESTINATION_NOT_OPEN":
        return "대피소 수용 시작(%s) 전 도착 불가" % fmt(c["window_open_s"])
    return "대기를 시설에서 하도록 앞당김"


def human_checks(raw, result):
    """What still needs a person: data gaps, tight margins, holds, and everything outside the model."""
    case = parse_case(raw)
    by_id = case.edge_by_id
    items = []
    for m in result.get("missing_information", []):
        e = by_id[m["edge_id"]]
        items.append({"code": "MISSING_FORECAST_INPUT", "edge_id": e.id,
                      "text_ko": "'%s' %s~%s 구간의 예측 자료가 없습니다 (%s 통과 예정). 사람이 도로 상태를 확인해야 합니다." % (
                          e.name_ko or e.id, fmt(m["unknown_interval"][0]), fmt(m["unknown_interval"][1]),
                          m["vehicle_id"])})
    for m in margins(case, result["trips"]):
        items.append({"code": "TIGHT_MARGIN", "edge_id": m["edge_id"], "margin_s": m["margin_s"],
                      "text_ko": "%s의 '%s' 통과(%s~%s)가 %s 구간과 %d초 차이입니다. 여유가 작아 사람이 확인해야 합니다." % (
                          m["vehicle_id"], m["edge_name_ko"] or m["edge_id"], fmt(m["traversal"][0]),
                          fmt(m["traversal"][1]), "모의 통제" if m["kind"] == "closed" else "미확인", m["margin_s"])})
    for t in result["trips"]:
        for w in t["waits"]:
            items.append({"code": "HOLD", "vehicle_id": t["vehicle_id"],
                          "text_ko": "%s가 %s~%s 동안 %s에서 대기합니다. 대기 장소의 안전을 사람이 확인해야 합니다." % (
                              t["vehicle_id"], fmt(w["start_s"]), fmt(w["end_s"]),
                              (raw.get("node_labels_ko") or {}).get(w["node"], w["node"]))})
    if result["status"] == "UNRESOLVED":
        items.append({"code": "UNRESOLVED", "text_ko": "계산이 끝나지 않았습니다. 경로가 없다는 뜻이 아닙니다."})
    for gid in result.get("groups_awaiting_checked_transport", []):
        items.append({"code": "AWAITING", "group_id": gid,
                      "text_ko": "%s는 확인된 이송 계획이 없습니다. 다른 수단을 사람이 마련해야 합니다." % gid})
    items += [
        {"code": "NOT_MODELLED", "text_ko": "누적 열 노출(복사열)은 계산하지 않았습니다 — 미해결 항목입니다."},
        {"code": "NOT_MODELLED", "text_ko": "실제 도로 개방·교통·연기 상황, 대피소 준비 상태, 운전자·입소자 건강은 사람이 확인해야 합니다."},
    ]
    return items
