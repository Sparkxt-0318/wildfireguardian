"""One A5 page per village (Korean, English copy). Black and white: greys, line weights and dash patterns only."""
from __future__ import annotations

from reportlab import rl_config
from reportlab.lib.colors import Color, black, white
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from . import fmt
from .cards import way_label
from .report import village_name

rl_config.invariant = 1

G_FIRE = Color(0.45, 0.45, 0.45)
G_TRIG = Color(0.86, 0.86, 0.86)
G_ROAD = Color(0.70, 0.70, 0.70)
DASHES = [None, (5, 2), (1.2, 1.8), (6, 2, 1.2, 2), (3, 3), (8, 2, 2, 2, 2, 2), (2, 1), (10, 3)]
MAJOR = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link",
         "tertiary", "tertiary_link", "unclassified", "residential", "living_street"}

T = {
    "ko": {
        "kind": "마을 대피 카드", "issued": "발표 %s KST", "replay": " · 재현", "horizon": " · 예측 %g시간",
        "leave": "출발 마감 (도로 기준)", "leave_q": "출발 마감 (대기행렬 모델 KQ-1)", "q_v": "%s  [낙관 %s – 비관 %s]  · 차량 %d대", "q_none": "모델에서 전 차량 대피 불가 (출발 분산·대기가 여유 시간보다 김)", "q_na": "이 시각은 계산 안 함", "q_h": " (예측 범위 제한)",
        "leave_cl": "출발 마감 (정체 반영)", "leave_m": "여유 %d분 지키는 출발 마감",
        "trigger": "트리거 시각 (여유 %d분 + 정체)", "shelter": "대피소", "exits": "독립 출구", "danger": "위험 도로",
        "forest": "출구 도로 숲 비율", "order": "출발 순서", "nocar": "차 없는 주민 (추정)", "people": "세대·주민·건물",
        "people_v": "세대 %s (%s) · 주민 %s (%s) · 65세 이상 %s (%s) · 위험 건물 %d채 / 지도에 오른 %d채 (OSM 2025-03-21, 하한) · 불이 닿는 칸의 세대 %s (추정)", "people_fac": "시설 주민 %s명 (%s) · 지도에 오른 건물 %d채",
        "st_est": "추정", "st_meas": "측정", "st_ass": "가정", "st_na": "자료 없음",
        "none_dl": "마감 없음 (예측 %g시간 안 차단 없음)", "cut_now": "이미 끊김 — 모델상 안전 경로 없음",
        "late_by": "%s (이미 %d분 늦음)", "clear": "차량 %d대 ÷ 가장 좁은 길 %d대/시 (%s) = %d분",
        "clear_fac": "자가 차량 0대 (시설: 전원 승합차)", "trig_line": "%s — 지도 굵은 점선을 불이 넘기 전에 출발",
        "trig_passed": "이미 지남 — 여유 %d분을 지키려면 지금 출발", "trig_none": "예측 %g시간 안에는 없음",
        "exits_v": "%d개 (서로 겹치지 않는 경로; 출구 %s)", "danger_v": "%s — 막히면 출구 %d개 중 %d개 끊김",
        "danger_tie": " (같은 효과 %d곳 중 마을에서 가장 가까운 곳)", "forest_v": "%s · 침엽수 자료 없음 (임상도 미보유): 숲 전체 비율",
        "order_v": "%s조 %d/%d번째 · %s까지 출발 시작%s", "order_after": " · 앞: %s", "order_none": "같은 도로를 쓰는 다른 마을 없음",
        "order_late": " · %d분 부족", "nocar_v": "%d명 · 승합차 %d호 %s 도착%s", "nocar_late": " (마감 뒤!)",
        "nocar_unreach": "%d명 · 도로가 이미 끊겨 승합차 계획 없음", "nocar_zero": "0명",
        "nocar_left": " · %d명은 예측 범위 안 배정 못 함", "nocar_none": "%d명 · 승합차 %d대(%d인승)로 예측 %g시간 안 배정 못 함",
        "legend": ["마을", "대피소(번호=출구)", "출구 경로 1·2·3", "위험 도로 (375 m 칸)", "현재 불", "트리거 시각까지 탈 곳", "트리거선"],
        "notes": "모델 출력. 도로: OSM 2025-03-21, 40 km/h, 혼잡·연기 제외. 화재: %s. 세대·주민·65세 이상은 읍·면·동 주민등록 통계(MOIS 2025-02, 측정)를 법정리 수로 균등 분할한 마을 값(추정); 차량은 도 평균 세대당 차량×세대(추정); 건물은 OSM에 올라 있는 것만(하한, 건물 간 불 번짐 없음); "
                 "용량은 도로용량편람 2013 2차로 1,700대/시/방향, 마을길 800(ASSUMED). 출구 = 어느 대피소로든 도로 조각을 공유하지 않는 경로 수(회전 제한 무시). "
                 "트리거선 = 입력 화재 도달 예측의 그 시각 등시선. 설정: 여유 %d분, 차 없는 세대 %.0f%%, 세대당 차량 %.2f.",
        "foot": "%s · %s · 쪽 1/1",
    },
    "en": {
        "kind": "Village evacuation card", "issued": "Issued %s KST", "replay": " · replay", "horizon": " · %g h forecast",
        "leave": "Leave by (roads)", "leave_cl": "Leave by (with clearance)", "leave_q": "Leave by (queue model KQ-1)",
        "q_v": "%s  [low %s – high %s]  · %d vehicles", "q_none": "cannot clear in the model (spread or queue exceeds the window)",
        "q_na": "not computed for this hour", "q_h": " (horizon-limited)", "leave_m": "Leave by keeping %d min margin",
        "trigger": "Trigger time (%d min margin + clearance)", "shelter": "Shelter", "exits": "Independent exits",
        "danger": "Dangerous road", "forest": "Forest along exits", "order": "Departure order", "nocar": "Residents without a car (est.)",
        "people": "Households, residents, buildings",
        "people_v": "households %s (%s) · residents %s (%s) · aged 65+ %s (%s) · buildings at risk %d of %d mapped (OSM 2025-03-21, lower bound) · households in reached cells %s (est.)",
        "people_fac": "facility residents %s (%s) · mapped buildings %d", "st_est": "estimated", "st_meas": "measured", "st_ass": "assumed", "st_na": "n/a",
        "none_dl": "no deadline (no cut within %g h)", "cut_now": "already cut — no safe route in the model",
        "late_by": "%s (already %d min late)", "clear": "%d vehicles ÷ narrowest road %d veh/h (%s) = %d min",
        "clear_fac": "0 own vehicles (facility: all by van)", "trig_line": "%s — leave before fire crosses the thick dashed line",
        "trig_passed": "already passed — leave now to keep %d min margin", "trig_none": "none within %g h",
        "exits_v": "%d (routes sharing no road piece; exits %s)", "danger_v": "%s — if closed, %d of %d exits cut",
        "danger_tie": " (nearest of %d places with the same effect)", "forest_v": "%s · conifer share not available (no forest-type map): any forest",
        "order_v": "group %s, %d of %d · start leaving by %s%s", "order_after": " · after: %s", "order_none": "no other village shares its road",
        "order_late": " · short by %d min", "nocar_v": "%d · van %d arrives %s%s", "nocar_late": " (after leave-by!)",
        "nocar_unreach": "%d · road already cut, no van planned", "nocar_zero": "0",
        "nocar_left": " · %d not reached within the horizon", "nocar_none": "%d · %d vans (%d seats) cannot reach them within %g h",
        "legend": ["village", "shelter (no. = exit)", "exit routes 1·2·3", "dangerous road (375 m cell)", "fire now",
                   "burns by trigger time", "trigger line"],
        "notes": "Model output. Roads: OSM 2025-03-21, 40 km/h, no congestion or smoke. Fire: %s. Households, residents and 65+ are 읍·면·동 register "
                 "counts (MOIS 2025-02, measured) split equally over the 법정리 (village figure estimated); vehicles = households x province rate (estimated); buildings: only those mapped in OSM (lower bound; no fire spread between buildings); capacity: KHCM 2013 two-lane 1,700 veh/h/direction, village roads 800 "
                 "(ASSUMED). Exits = routes to any shelter sharing no road piece (turn restrictions ignored). Trigger line = isochrone "
                 "of the input fire-arrival forecast at that time. Settings: margin %d min, no-car households %.0f%%, %.2f vehicles/household.",
        "foot": "%s · %s · page 1/1",
    },
}


def _stat(st, lang):
    t = T[lang]
    st = (st or "").upper()
    if st.startswith("ESTIMATED"):
        return t["st_est"]
    if st.startswith("MEASURED"):
        return t["st_meas"]
    if st.startswith("ASSUMED"):
        return t["st_ass"]
    return t["st_na"]


def _n(x):
    return "—" if x is None else "%d" % round(x)


def _hm(issue, s, lang):
    dt = fmt.t_floor(issue, s)
    d = (dt.date() - fmt.kst(issue).date()).days
    return dt.strftime("%H:%M") + (("(+%d일)" % d if lang == "ko" else "(+%dd)" % d) if d else "")


def _wrap(text, font, size, width):
    out, line = [], ""
    for word in text.split(" "):
        cand = (line + " " + word).strip()
        if stringWidth(cand, font, size) <= width:
            line = cand
            continue
        if line:
            out.append(line)
        while stringWidth(word, font, size) > width:  # long Korean runs without spaces
            k = len(word)
            while k > 1 and stringWidth(word[:k], font, size) > width:
                k -= 1
            out.append(word[:k])
            word = word[k:]
        line = word
    if line:
        out.append(line)
    return out


def draw_card(cv: canvas.Canvas, rec, lang, ctx):
    t = T[lang]
    W, Hh = A5
    issue = ctx["issue"]
    o = rec["origin"]
    ccfg = ctx["ccfg"]
    M = ccfg["trigger"]["margin_min"]
    Hh_h = ctx["horizon_s"] / 3600
    x0, x1 = 9 * mm, W - 9 * mm
    # banner
    cv.setFillColor(black)
    cv.rect(0, Hh - 9 * mm, W, 9 * mm, stroke=0, fill=1)
    cv.setFillColor(white)
    cv.setFont("NanumBold", 11)
    cv.drawCentredString(W / 2, Hh - 6.3 * mm, fmt.NOTICE[lang])
    cv.setFillColor(black)
    # title
    name = village_name(o, lang) or o["id"]
    place = "%s %s" % ((o["sigungu"], o["eupmyeon"]) if lang == "ko" else
                       (fmt.romanize(o["sigungu"]) if o["sigungu"] else "", fmt.romanize(o["eupmyeon"]) if o["eupmyeon"] else ""))
    cv.setFont("NanumBold", 15)
    cv.drawString(x0, Hh - 16.5 * mm, name[:40])
    cv.setFont("Nanum", 7.5)
    sub = "%s · %s · %s%s%s" % (t["kind"], place.strip(), t["issued"] % fmt.full(fmt.kst(issue)), t["replay"] if ctx["as_of_given"] else "",
                                t["horizon"] % Hh_h)
    cv.drawString(x0, Hh - 21 * mm, sub)
    # ---------------------------------------------------------------- map
    shrink = (15 * mm if rec.get("queue") is not None else 0) + 8 * mm   # one more fact line (queue model) needs room
    mx0, my0, mw, mh = x0, 96 * mm + shrink, x1 - x0, 88 * mm - shrink
    _map(cv, rec, ctx, (mx0, my0, mw, mh), lang)
    # legend
    _legend(cv, x0, my0 - 4.2 * mm, x1 - x0, t["legend"])
    # ---------------------------------------------------------------- key facts
    lines = []
    row = rec["row"]
    if row["leave_by"] is None:
        lv = lv_cl = t["cut_now"]
    elif rec["no_deadline"]:
        lv = lv_cl = t["none_dl"] % Hh_h
    else:
        lv = _hm(issue, rec["leave_by"], lang)
        lc = rec["leave_by_clear"]
        lv_cl = _hm(issue, lc, lang) if lc >= 0 else t["late_by"] % (_hm(issue, 0, lang), -(lc // 60))
    if rec["hh"]["kind"] == "care_facility":
        cl_txt = t["clear_fac"]
    elif rec["clearance_s"] is not None:
        cl_txt = t["clear"] % (rec["vehicles"], rec["narrow_cap"], rec["narrow_class"], -(-rec["clearance_s"] // 60))
    else:
        cl_txt = ""
    lines.append((t["leave"], lv, True))
    lines.append((t["leave_cl"], lv_cl + ("  ·  " + cl_txt if cl_txt else ""), True))
    q = rec.get("queue")
    if q is not None:
        if q["s_cont_mid"] == "":
            qv = t["q_none"]
        else:
            qv = t["q_v"] % (_hm(issue, q["s_cont_mid"], lang), _hm(issue, q["s_cont_low"], lang) if q["s_cont_low"] != "" else "—",
                              _hm(issue, q["s_cont_high"], lang) if q["s_cont_high"] != "" else "—", q["N_mid"]) + (t["q_h"] if rec["no_deadline"] else "")
        lines.append((t["leave_q"], qv, True))
    if rec["leave_by_m"] is not None:
        lm = _hm(issue, rec["leave_by_m"], lang)
    elif rec["m_no_deadline"]:
        lm = t["none_dl"] % Hh_h
    else:
        lm = t["cut_now"]
    lines.append((t["leave_m"] % M, lm, False))
    ts = rec["trigger_state"]
    trig = (t["trig_line"] % _hm(issue, rec["trigger_s"], lang)) if ts == "line" else \
        (t["trig_passed"] % M) if ts == "passed" else (t["trig_none"] % Hh_h)
    lines.append((t["trigger"] % M, trig, True))
    sh = row["last"]["shelter"] if row.get("last") else (rec["paths"][0]["shelter"] if rec["paths"] else None)
    if sh:
        sname = sh["name"] or sh["id"]
        if lang == "en":
            sname = "%s (%s)" % (fmt.place_en(sname), sname)
        trav = -(-(row["last"]["w_last"]["arrival"] - row["last"]["L"]) // 60) if row.get("last") else -(-rec["paths"][0]["travel_s"] // 60)
        lines.append((t["shelter"], "%s · %d%s" % (sname, trav, "분" if lang == "ko" else " min"), False))
    ex_sh = ", ".join("%d→%s" % (i + 1, ((p["shelter"]["name"] if lang == "ko" else fmt.place_en(p["shelter"]["name"])) if p["shelter"] and p["shelter"]["name"] else "?"))
                      for i, p in enumerate(rec["paths"]))
    lines.append((t["exits"], t["exits_v"] % (rec["exits"], ex_sh), rec["exits"] == 1))
    d = rec["danger"]
    if d:
        dv = t["danger_v"] % (way_label(ctx["ways"], d["way"], lang), rec["exits"], d["cut"])
        if d["tied"] > 1:
            dv += t["danger_tie"] % d["tied"]
        lines.append((t["danger"], dv, rec["danger_all"] or rec["exits"] == 1))
    fv = ", ".join("%d: %.0f%%" % (i + 1, 100 * p["forest_share"]) for i, p in enumerate(rec["paths"]))
    lines.append((t["forest"], t["forest_v"] % fv, False))
    dm, rk = rec["demo"], rec["risk"]
    if rec["hh"]["kind"] == "village":
        pv = t["people_v"] % (_n(dm["households"]), _stat(dm["households_status"], lang), _n(dm["residents"]), _stat(dm["residents_status"], lang),
                              _n(dm["residents65"]), _stat(dm["residents65_status"], lang), rk["at_risk"], rk["mapped"], _n(rk["households_at_risk"]))
    else:
        pv = t["people_fac"] % (_n(dm["residents"]), _stat(dm["residents_status"], lang), rk["mapped"])
    lines.append((t["people"], pv, False))
    if rec.get("dep_group"):
        ov = t["order_v"] % (rec["dep_group"].lstrip("G") if lang == "ko" else rec["dep_group"], rec["dep_pos"], rec["dep_size"],
                             _hm(issue, max(rec["dep_start"], 0), lang), (t["order_late"] % -(-rec["dep_late"] // 60)) if rec["dep_late"] else "")
        if rec.get("dep_before"):
            ov += t["order_after"] % (village_name(rec["dep_before"], lang) or rec["dep_before"]["id"])
    else:
        ov = t["order_none"]
    lines.append((t["order"], ov, False))
    n = rec["no_car_persons"]
    if n == 0:
        nv = t["nocar_zero"]
    elif rec.get("pickup_unreachable") or row["leave_by"] is None:
        nv = t["nocar_unreach"] % n
    elif rec.get("pickup_first"):
        e = rec["pickup_first"]
        nv = t["nocar_v"] % (n, e["van"], _hm(issue, e["arrive"], lang), t["nocar_late"] if rec.get("pickup_late") else "")
        if rec.get("pickup_unserved"):
            nv += t["nocar_left"] % rec["pickup_unserved"]
    else:
        nv = t["nocar_none"] % (n, ccfg["pickup"]["vans"], ccfg["pickup"]["van_seats"], Hh_h)
    lines.append((t["nocar"], nv, False))
    y = my0 - 12.5 * mm
    lab_w = 37 * mm
    for lab, val, bold in lines:
        cv.setFont("NanumBold", 7.2)
        ll = _wrap(lab, "NanumBold", 7.2, lab_w - 2 * mm)[:2]
        for k, ln in enumerate(ll):
            cv.drawString(x0, y - k * 3.2 * mm, ln)
        f = "NanumBold" if bold else "Nanum"
        wl = _wrap(val, f, 7.6, x1 - x0 - lab_w)
        cv.setFont(f, 7.6)
        for k, ln in enumerate(wl[:3]):
            cv.drawString(x0 + lab_w, y - k * 3.2 * mm, ln)
        y -= max(len(wl[:3]), len(ll), 1) * 3.2 * mm + 1.8 * mm
        cv.setStrokeColor(G_ROAD)
        cv.setLineWidth(0.3)
        cv.line(x0, y + 3.5 * mm, x1, y + 3.5 * mm)
        cv.setStrokeColor(black)
    # notes and footer
    tc = ctx["tcfg"]
    note = t["notes"] % (ctx["fire_label"], M, 100 * tc["no_car_share"], tc["vehicles_per_household"])
    cv.setFont("Nanum", 5.6)
    yy = max(y - 1.0 * mm, 22 * mm)
    for ln in _wrap(note, "Nanum", 5.6, x1 - x0)[:6]:
        cv.drawString(x0, yy, ln)
        yy -= 2.5 * mm
    cv.setFillColor(black)
    cv.rect(0, 0, W, 7 * mm, stroke=0, fill=1)
    cv.setFillColor(white)
    cv.setFont("NanumBold", 7.5)
    cv.drawCentredString(W / 2, 2.4 * mm, fmt.NOTICE[lang])
    cv.setFillColor(black)
    cv.setFont("Nanum", 5.4)
    cv.drawRightString(x1, 8.3 * mm, t["foot"] % (o["id"], ctx["run_label"]))


def _legend(cv, x, y, width, labels):
    cv.setFont("Nanum", 6)
    items = ["village", "shelter", "route", "danger", "fire", "trig", "line"]
    nxt = list(labels[1:])
    cx = x
    for kind, lab in zip(items, labels):
        sw = 6 * mm
        if kind == "village":
            cv.setFillColor(black)
            cv.circle(cx + 1.5 * mm, y + 1 * mm, 1.3 * mm, stroke=0, fill=1)
        elif kind == "shelter":
            cv.setFillColor(white)
            cv.setLineWidth(0.8)
            cv.rect(cx + 0.3 * mm, y - 0.3 * mm, 2.6 * mm, 2.6 * mm, stroke=1, fill=1)
        elif kind == "route":
            cv.setLineWidth(1.4)
            for k, dsh in enumerate(DASHES[:3]):
                cv.setDash(*(dsh and (list(dsh), 0) or ([], 0)))
                cv.line(cx, y + (0.2 + k * 0.9) * mm, cx + sw - 1 * mm, y + (0.2 + k * 0.9) * mm)
            cv.setDash([], 0)
        elif kind == "danger":
            cv.setLineWidth(1.4)
            cv.setFillColor(white)
            cv.rect(cx, y - 0.4 * mm, 3 * mm, 3 * mm, stroke=1, fill=0)
            cv.setFillColor(black)
            cv.setFont("NanumBold", 6)
            cv.drawCentredString(cx + 1.5 * mm, y + 0.2 * mm, "!")
            cv.setFont("Nanum", 6)
        elif kind == "fire":
            cv.setFillColor(G_FIRE)
            cv.rect(cx, y - 0.4 * mm, 3.5 * mm, 2.8 * mm, stroke=0, fill=1)
        elif kind == "trig":
            cv.setFillColor(G_TRIG)
            cv.rect(cx, y - 0.4 * mm, 3.5 * mm, 2.8 * mm, stroke=0, fill=1)
        elif kind == "line":
            cv.setLineWidth(1.8)
            cv.setDash([4, 2], 0)
            cv.line(cx, y + 1 * mm, cx + 5 * mm, y + 1 * mm)
            cv.setDash([], 0)
        cv.setFillColor(black)
        lx = cx + (6.5 if kind in ("route", "line") else 4.2) * mm
        cv.drawString(lx, y, lab)
        cx = lx + stringWidth(lab, "Nanum", 6) + 2.8 * mm
        if nxt and cx + 7 * mm + stringWidth(nxt.pop(0), "Nanum", 6) > x + width:
            cx, y = x, y - 3.4 * mm
    cv.setLineWidth(1)


def _map(cv, rec, ctx, box, lang):
    road = ctx["road"]
    bx, by, bw, bh = box
    o = rec["origin"]
    vx, vy = road.node_xy[o["node"]]
    pts = [(vx, vy)]
    for p in rec["paths"]:
        for j in p["edges"]:
            pts.append(road.node_xy[road.head[j]])
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    w, h = max(maxx - minx, 2500.0), max(maxy - miny, 2500.0)
    cxm, cym = (minx + maxx) / 2, (miny + maxy) / 2
    w, h = w * 1.12, h * 1.12
    if w / h > bw / bh:
        h = w * bh / bw
    else:
        w = h * bw / bh
    X0, Y0 = cxm - w / 2, cym - h / 2
    sc = bw / w

    def P(x, y):
        return bx + (x - X0) * sc, by + (y - Y0) * sc

    cv.saveState()
    p = cv.beginPath()
    p.rect(bx, by, bw, bh)
    cv.clipPath(p, stroke=0)
    # fire now and area burning by the trigger time, cells of the routing lattice
    arr = ctx["arrival_all"]
    res = float(road.res)
    c_lo = max(int((X0 - float(road.x0)) // res), 0)
    c_hi = min(int((X0 + w - float(road.x0)) // res) + 1, road.W - 1)
    r_lo = max(int((Y0 - float(road.y0)) // res), 0)
    r_hi = min(int((Y0 + h - float(road.y0)) // res) + 1, road.H - 1)
    trig = rec["trigger_s"] if rec["trigger_state"] == "line" else None
    side = res * sc
    inside = set()
    for r in range(r_lo, r_hi + 1):
        for c in range(c_lo, c_hi + 1):
            a = arr.get(r * road.W + c)
            if a is None:
                continue
            xx, yy = P(float(road.x0) + c * res, float(road.y0) + r * res)
            if a <= 0:
                cv.setFillColor(G_FIRE)
                cv.rect(xx, yy, side + 0.05, side + 0.05, stroke=0, fill=1)
            elif trig is not None and a <= trig:
                cv.setFillColor(G_TRIG)
                cv.rect(xx, yy, side + 0.05, side + 0.05, stroke=0, fill=1)
            if trig is not None and a <= trig:
                inside.add((r, c))
    # background roads
    cv.setStrokeColor(G_ROAD)
    seen = set()
    ways = ctx["ways"]
    for j in ctx["edges_in"](X0, Y0, X0 + w, Y0 + h):
        rv = road.reverse_edge[j]
        if rv in seen:
            continue
        seen.add(road.edge_ids[j])
        cls = (ways.get(road.source_way[j]) or {}).get("class", "")
        if cls not in MAJOR:
            continue
        cv.setLineWidth(0.9 if cls in ("motorway", "trunk", "primary", "secondary", "tertiary") else 0.35)
        cv.line(*P(*road.node_xy[road.tail[j]]), *P(*road.node_xy[road.head[j]]))
    # trigger line: boundary between cells burning by the trigger time and cells that do not
    if inside:
        cv.setStrokeColor(black)
        cv.setLineWidth(1.8)
        cv.setDash([4, 2], 0)
        for (r, c) in inside:
            x_a, y_a = float(road.x0) + c * res, float(road.y0) + r * res
            for dr, dc, seg in ((1, 0, ((0, 1), (1, 1))), (-1, 0, ((0, 0), (1, 0))), (0, 1, ((1, 0), (1, 1))), (0, -1, ((0, 0), (0, 1)))):
                if (r + dr, c + dc) not in inside:
                    (ax, ay), (bx2, by2) = seg
                    cv.line(*P(x_a + ax * res, y_a + ay * res), *P(x_a + bx2 * res, y_a + by2 * res))
        cv.setDash([], 0)
    # exit routes
    cv.setStrokeColor(black)
    for k, pth in enumerate(rec["paths"]):
        dsh = DASHES[k % len(DASHES)]
        cv.setLineWidth(1.5)
        cv.setDash(*(dsh and (list(dsh), 0) or ([], 0)))
        pp = cv.beginPath()
        e = pth["edges"]
        if not e:
            continue
        pp.moveTo(*P(*road.node_xy[road.tail[e[0]]]))
        for j in e:
            pp.lineTo(*P(*road.node_xy[road.head[j]]))
        cv.drawPath(pp, stroke=1, fill=0)
    cv.setDash([], 0)
    # shelters at route ends, numbered
    cv.setFont("NanumBold", 7)
    for k, pth in enumerate(rec["paths"]):
        if not pth["edges"]:
            continue
        ex_, ey_ = P(*road.node_xy[road.head[pth["edges"][-1]]])
        cv.setFillColor(white)
        cv.setStrokeColor(black)
        cv.setLineWidth(1)
        cv.rect(ex_ - 2 * mm, ey_ - 2 * mm, 4 * mm, 4 * mm, stroke=1, fill=1)
        cv.setFillColor(black)
        cv.drawCentredString(ex_, ey_ - 0.9 * mm, str(k + 1))
    # village
    px, py = P(vx, vy)
    cv.setFillColor(white)
    cv.circle(px, py, 2.6 * mm, stroke=0, fill=1)
    cv.setFillColor(black)
    cv.circle(px, py, 1.8 * mm, stroke=0, fill=1)
    nm = village_name(o, lang) or ""
    cv.setFont("NanumBold", 7.5)
    tw = stringWidth(nm, "NanumBold", 7.5)
    cv.setFillColor(white)
    cv.rect(px + 2.8 * mm, py - 1.2 * mm, tw + 1.5 * mm, 3.4 * mm, stroke=0, fill=1)
    cv.setFillColor(black)
    cv.drawString(px + 3.5 * mm, py - 0.4 * mm, nm)
    # dangerous cell
    d = rec["danger"]
    if d:
        r, c = divmod(d["cell"], road.W)
        xx, yy = P(float(road.x0) + c * res, float(road.y0) + r * res)
        cv.setLineWidth(2.2)
        cv.setStrokeColor(black)
        cv.setFillColor(white)
        cv.rect(xx, yy, side, side, stroke=1, fill=0)
        cv.setFont("NanumBold", 8)
        cx_, cy_ = xx + side / 2, yy + side / 2
        cv.setLineWidth(1.2)
        cv.circle(cx_, cy_, 1.7 * mm, stroke=1, fill=1)
        cv.setFillColor(black)
        cv.drawCentredString(cx_, cy_ - 1.0 * mm, "!")
    cv.restoreState()
    # frame, scale bar, north
    cv.setLineWidth(0.6)
    cv.setStrokeColor(black)
    cv.rect(bx, by, bw, bh, stroke=1, fill=0)
    km = 1000.0
    for cand in (500.0, 1000.0, 2000.0, 5000.0):
        if cand * sc <= bw * 0.3:
            km = cand
    sx, sy = bx + 3 * mm, by + 3 * mm
    cv.setFillColor(white)
    cv.rect(sx - 1 * mm, sy - 1.5 * mm, km * sc + 12 * mm, 5 * mm, stroke=0, fill=1)
    cv.setFillColor(black)
    cv.setLineWidth(1.2)
    cv.line(sx, sy, sx + km * sc, sy)
    cv.line(sx, sy - 0.8 * mm, sx, sy + 0.8 * mm)
    cv.line(sx + km * sc, sy - 0.8 * mm, sx + km * sc, sy + 0.8 * mm)
    cv.setFont("Nanum", 6)
    cv.drawString(sx + km * sc + 1.2 * mm, sy - 0.8 * mm, ("%g km" % (km / 1000)))
    nx, ny = bx + bw - 6 * mm, by + bh - 9 * mm
    cv.setFillColor(white)
    cv.rect(nx - 2.5 * mm, ny - 1 * mm, 5 * mm, 8 * mm, stroke=0, fill=1)
    cv.setFillColor(black)
    p = cv.beginPath()
    p.moveTo(nx, ny + 6 * mm)
    p.lineTo(nx - 1.6 * mm, ny + 2 * mm)
    p.lineTo(nx + 1.6 * mm, ny + 2 * mm)
    p.close()
    cv.drawPath(p, stroke=0, fill=1)
    cv.setFont("NanumBold", 6.5)
    cv.drawCentredString(nx, ny - 0.3 * mm, "N")


def build(path, recs, lang, ctx, title):
    cv = canvas.Canvas(str(path), pagesize=A5, invariant=1, pageCompression=1)
    cv.setTitle(title)
    cv.setAuthor("wfg-roadlayer")
    cv.setSubject(fmt.NOTICE[lang])
    for rec in recs:
        draw_card(cv, rec, lang, ctx)
        cv.showPage()
    cv.save()
