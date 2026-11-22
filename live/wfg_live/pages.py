"""Static pages for GitHub Pages /live/ (PROTOCOL §8). Korean first, English toggle; numbers hide when the page is stale."""
from __future__ import annotations

import csv
import html
import json
import shutil
from datetime import timedelta
from pathlib import Path

from . import cause as cause_mod, common as C, road

E = html.escape

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#5d5b55;--line:#d9d6cf;--card:#ffffff;--warn:#8a1c00;--warnbg:#fff1ea;--ok:#245c2a;--okbg:#eef7ee;--hl:#fff7d6;--acc:#0b5394}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#151514;--fg:#ecebe6;--mut:#a7a49c;--line:#3a3935;--card:#1e1e1c;--warn:#ffb59c;--warnbg:#3a1d12;--ok:#9fd8a3;--okbg:#17301a;--hl:#3a3418;--acc:#8ab8ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",sans-serif}
main{max-width:1080px;margin:0 auto;padding:16px}a{color:var(--acc)}h1{font-size:1.45rem;margin:.4rem 0}h2{font-size:1.15rem;margin:1.4rem 0 .5rem}
.notice{background:var(--warnbg);color:var(--warn);border:1px solid var(--warn);border-radius:6px;padding:10px 12px;font-weight:600}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between}.lang{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;padding:4px 10px;cursor:pointer}
.box{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;margin:10px 0}.mut{color:var(--mut)}.small{font-size:.88rem}
table{border-collapse:collapse;width:100%;font-size:.92rem}th,td{border-bottom:1px solid var(--line);padding:6px 6px;text-align:left;vertical-align:top}th{color:var(--mut);font-weight:600}
.scroll{overflow-x:auto}.pill{display:inline-block;border-radius:999px;padding:1px 9px;font-size:.85rem;border:1px solid var(--line)}
.on{background:var(--warnbg);color:var(--warn);border-color:var(--warn)}.off{background:var(--okbg);color:var(--ok);border-color:var(--ok)}.unk{color:var(--mut)}
.stale{display:none}.is-stale .stale{display:block}.is-stale .num{visibility:hidden}.is-stale .num-hide{display:none}
.big{font-size:1.25rem;font-weight:700}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
html[lang=ko] .en{display:none}html[lang=en] .ko{display:none}
.vk{display:grid;grid-template-columns:minmax(120px,38%) 1fr;gap:2px 10px;margin-top:6px}
.hist{border-style:dashed}.hb{display:grid;grid-template-columns:minmax(110px,30%) 1fr 4.5em;gap:6px;align-items:center;font-size:.9rem;margin:2px 0}
.hb i{display:block;height:.7rem;background:var(--mut);opacity:.55;border-radius:2px}.hb span:last-child{text-align:right}
input[type=search]{width:100%;padding:8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg);font-size:1rem}
"""

JS = """
(function(){var h=document.documentElement;try{var l=localStorage.getItem('wfg-live-lang');if(l)h.lang=l}catch(e){}
document.addEventListener('click',function(e){if(e.target.classList.contains('lang')){h.lang=h.lang==='ko'?'en':'ko';try{localStorage.setItem('wfg-live-lang',h.lang)}catch(e){}}});
function chk(){var t=Date.parse(h.getAttribute('data-issue'));var lim=+h.getAttribute('data-stale-min');if(!t)return;var age=(Date.now()-t)/60000;
var els=document.querySelectorAll('.age-min');for(var i=0;i<els.length;i++)els[i].textContent=Math.max(0,Math.round(age));
if(age>lim)document.body.classList.add('is-stale')}chk();setInterval(chk,60000)})();
"""


def L(ko, en):
    return '<span class="ko">%s</span><span class="en">%s</span>' % (ko, en)


def page(title_ko, title_en, body, rec, depth=0):
    up = "../" * depth
    issue = rec["issue_utc"]
    stale = C.settings()["age"]["page_stale_min"]
    return f"""<!doctype html>
<html lang="ko" data-issue="{issue}" data-stale-min="{stale}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(title_ko)} · {E(title_en)}</title>
<style>{CSS}</style></head><body><main>
<div class="bar"><div><a href="{up}index.html">{L("산불 현황", "Fire status")}</a> · <a href="{up}cards.html">{L("마을 카드 찾기", "Card lookup")}</a></div>
<button class="lang" type="button" aria-label="language">한국어 / English</button></div>
<p class="notice">{E(C.NOTICE["ko"])}<br><span class="small">{E(C.NOTICE["en"])}</span></p>
<div class="box stale notice">{L("이 페이지는 <b class=age-min></b>분 전 자료입니다 (한도 %d분). 숫자를 숨겼습니다. 최신 정보는 산림청·지자체 안내를 따르십시오." % stale,
  "This page is <b class=age-min></b> min old (limit %d min). Numbers are hidden. Follow the Forest Service and local authorities." % stale)}</div>
<h1>{L(E(title_ko), E(title_en))}</h1>
{body}
<p class="small mut">{L("발표(실행) 시각", "Issue (run) time")}: {E(rec["issue_kst"])} KST · {L("페이지 나이", "page age")}: <span class="age-min"></span> {L("분", "min")} ·
{L("도로 자료: OpenStreetMap 2025-03-21 스냅샷 (그 뒤 생긴 도로·통제는 모름)", "Road data: OpenStreetMap snapshot of 2025-03-21 (later roads and closures unknown)")} ·
<a href="https://github.com/Sparkxt-0318/wildfireguardian/blob/Main/live/PROTOCOL.md">PROTOCOL</a> · <a href="{up}data/latest.json">record JSON</a></p>
<p class="small mut">{E(C.NOTICE["ko"])} {E(C.NOTICE["en"])}</p>
</main><script>{JS}</script></body></html>
"""


def flag_pill(state, on_ko, on_en, off_ko="아님", off_en="off"):
    if state is True:
        return '<span class="pill on">%s</span>' % L(on_ko, on_en)
    if state is False:
        return '<span class="pill off">%s</span>' % L(off_ko, off_en)
    return '<span class="pill unk">%s</span>' % L("알 수 없음", "unknown")


def _age(rec, m):
    if not m or not m.get("fetched_utc"):
        return "—"
    T = C.parse_iso(rec["issue_utc"])
    a = (T - C.parse_iso(m["fetched_utc"])).total_seconds() / 60
    return "%s KST (%+.0f %s)" % (C.kst(C.parse_iso(m["fetched_utc"])), -a, "min")


SRC_NAMES = {"kfs": ("산림청 국가산불정보시스템 (웹 페이지 자료 호출)", "Korea Forest Service fire list (web page data call)"),
             "gfs": ("GFS 0.25° 예보 (NOAA)", "GFS 0.25° forecast (NOAA)"), "ahi": ("히마와리-9 AHI (NOAA)", "Himawari-9 AHI (NOAA)")}


def sources_table(rec):
    rows = []
    for k, m in sorted(rec["inputs"].items()):
        nm = SRC_NAMES.get(k, ("NASA FIRMS " + k.split(":", 1)[-1], "NASA FIRMS " + k.split(":", 1)[-1]))
        st = '<span class="pill off">OK</span>' if m.get("ok") else '<span class="pill on">%s</span>' % L("실패", "failed")
        extra = ""
        if k == "gfs" and m.get("cycle_utc"):
            extra = " · cycle %s" % E(C.kst(C.parse_iso(m["cycle_utc"])) + " KST")
        if k == "ahi":
            extra = " · %s/%s scans" % (m.get("scans_read"), m.get("scans_expected", "?"))
        err = (" · " + E(str(m.get("error"))[:140])) if m.get("error") else ""
        rows.append("<tr><td>%s</td><td>%s</td><td>%s%s%s</td></tr>" % (L(E(nm[0]), E(nm[1])), st, E(_age(rec, m)), extra, err))
    if "ahi" not in rec["inputs"]:
        rows.append("<tr><td>%s</td><td>—</td><td>%s</td></tr>" % (L("히마와리-9 AHI", "Himawari-9 AHI"),
                    L("경북·강원에 진화 중인 산불이 없어 받지 않음", "not fetched: no active fire in Gyeongbuk or Gangwon")))
    return ('<div class="scroll"><table><tr><th>%s</th><th>%s</th><th>%s</th></tr>%s</table></div>'
            % (L("자료", "Source"), L("상태", "Status"), L("받은 시각 (발표 시각 대비)", "Fetched (relative to issue)"), "".join(rows)))


def reason_list(rec, reasons):
    if not reasons:
        return ""
    R = rec["withheld_reasons"]
    return "<ul>%s</ul>" % "".join("<li>%s</li>" % L(E(R[r]["ko"]), E(R[r]["en"])) for r in reasons)


def bulletin_html(rec):
    b = rec["bulletin"]
    if b.get("error"):
        return '<div class="box">%s: %s</div>' % (L("바람 경보 판단 불가", "Wind flag not computable"), E(b["error"]))
    on = [c for c in b["cells"] if c["state"]]
    day = rec.get("bulletin_day") or {}
    head = L("일일 바람 경보 (돌풍 규칙 G: 예보 순간풍속 20 m/s 이상이 2시간 연속, 앞으로 8시간)",
             "Daily wind-flag bulletin (gust rule G: forecast gust >= 20 m/s at two consecutive hours, next 8 h)")
    s = '<h2>%s</h2><div class="box"><p>%s: <b>%d</b> / %d %s · GFS cycle %s KST</p>' % (
        head, L("지금 시각 경보 칸", "Cells on now"), len(on), b["n_cells"], L("칸 (0.25° 격자, 경북·강원 상자)", "cells (0.25° lattice, Gyeongbuk-Gangwon box)"),
        E(C.kst(C.parse_iso(b["gfs_cycle_utc"]))))
    if day.get("cells_on_today") is not None:
        s += "<p>%s: <b>%d</b> (%s)</p>" % (L("오늘(KST) 한 번이라도 경보", "On at any issue hour today (KST)"), len(day["cells_on_today"]),
                                          L("시각: ", "hours: ") + E(", ".join(day.get("hours", []))))
    s += svg_grid(b, set(map(tuple, (day.get("cells_on_today") or []))))
    se = {}
    for c in b["cells"]:
        for p in c.get("single_exit_places", []):
            se[p["place_id"]] = p
    for cid in (day.get("cells_on_today") or []):
        for p in (day.get("single_exit_by_cell") or {}).get("%s,%s" % tuple(cid), []):
            se[p["place_id"]] = p
    if se:
        rows = "".join("<tr><td>%s</td><td>%s %s</td><td>%s</td></tr>" % (E(p["name"] or "(이름 없음)"), E(p["sigungu"]), E(p["eupmyeon"]),
                                                                          E(road.REGIONS[p["region"]]["ko"])) for p in sorted(se.values(), key=lambda p: (p["sigungu"], p["eupmyeon"], p["name"])))
        s += "<details><summary><b>%s (%d)</b></summary><div class=scroll><table><tr><th>%s</th><th>%s</th><th>%s</th></tr>%s</table></div>" % (
            L("경보 칸 안의 출구 하나뿐인 마을", "Single-exit villages in flagged cells"), len(se), L("마을", "Village"), L("시군·읍면", "County, town"),
            L("준비된 지역", "Prepared region"), rows) + "</details>"
    else:
        s += "<p>%s</p>" % L("경보 칸 안에 출구 하나뿐인 준비된 마을 없음. (도로 자료가 있는 곳은 영덕, 의성·안동뿐)",
                             "No prepared single-exit village in a flagged cell. (Road data exists only for Yeongdeok and Uiseong-Andong.)")
    return s + "</div>"


TOWNS = [("춘천", 37.88, 127.73), ("강릉", 37.75, 128.88), ("원주", 37.34, 127.92), ("삼척", 37.45, 129.17), ("안동", 36.57, 128.73),
         ("의성", 36.35, 128.70), ("영덕", 36.42, 129.37), ("포항", 36.02, 129.34), ("대구", 35.87, 128.60), ("울진", 36.99, 129.40)]


def svg_grid(b, today):
    cells = b["cells"]
    if not cells:
        return ""
    la = sorted({c["lat0"] for c in cells}); lo = sorted({c["lon0"] for c in cells})
    w, h = 22, 22
    W, H = len(lo) * w, len(la) * h
    parts = ['<svg viewBox="0 0 %d %d" width="%d" style="max-width:100%%;height:auto" role="img" aria-label="wind flag grid">' % (W + 70, H + 20, W + 70)]
    for c in cells:
        x = lo.index(c["lon0"]) * w
        y = (len(la) - 1 - la.index(c["lat0"])) * h
        col = "#c0392b" if c["state"] else ("#e8a87c" if (c["lat0"], c["lon0"]) in today else ("#9aa39a" if c["state"] is False else "#ddd"))
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s" stroke="#fff"><title>%.2f N %.2f E: %s</title></rect>'
                     % (x, y, w, h, col, c["lat0"], c["lon0"], c.get("level_g_k2_ms")))
    for name, lat, lon in TOWNS:
        if la[0] <= lat <= la[-1] + 0.25 and lo[0] <= lon <= lo[-1] + 0.25:
            x = (lon - lo[0]) / 0.25 * w
            y = (la[-1] + 0.25 - lat) / 0.25 * h
            parts.append('<circle cx="%.1f" cy="%.1f" r="3" fill="#111" stroke="#fff"/><text x="%.1f" y="%.1f" font-size="10" '
                         'fill="#111" stroke="#fff" stroke-width="2.5" paint-order="stroke">%s</text>' % (x, y, x + 4, y - 3, name))
    parts.append('<text x="%d" y="12" font-size="10" fill="currentColor">N %.2f</text>' % (W + 4, la[-1] + 0.25))
    parts.append('<text x="%d" y="%d" font-size="10" fill="currentColor">N %.2f</text>' % (W + 4, H, la[0]))
    parts.append('<text x="0" y="%d" font-size="10" fill="currentColor">E %.2f … %.2f</text>' % (H + 14, lo[0], lo[-1] + 0.25))
    parts.append("</svg>")
    leg = L("빨강: 지금 경보 · 주황: 오늘 앞서 경보 · 회색: 아님", "red: on now · orange: on earlier today · grey: off")
    return "".join(parts) + '<p class="small mut">%s</p>' % leg


def index_html(rec):
    T = C.parse_iso(rec["issue_utc"])
    m = T.minute
    nxt_t = T.replace(second=0) + timedelta(minutes=(7 - m) if m < 7 else (37 - m) if m < 37 else (67 - m))
    nxt = C.kst(nxt_t)
    body = '<div class="grid">'
    body += '<div class="box"><div class="mut small">%s</div><div class="big">%s KST</div></div>' % (L("마지막 실행", "Last run"), E(rec["issue_kst"]))
    body += '<div class="box"><div class="mut small">%s</div><div class="big">%s KST</div><div class="small mut">%s</div></div>' % (
        L("다음 예정 실행", "Next scheduled run"), E(nxt), L("GitHub 예약 실행은 늦어지거나 빠질 수 있음", "GitHub scheduled runs can be late or skipped"))
    scope = [f for f in rec["fires"]]
    body += '<div class="box"><div class="mut small">%s</div><div class="big">%s</div></div></div>' % (
        L("경북·강원 진화 중 산불", "Active fires, Gyeongbuk-Gangwon"), ("%d" % len(scope)) if rec["kfs_ok"] else L("목록 없음", "no list"))
    if not rec["kfs_ok"]:
        body += '<div class="box notice">%s</div>' % L("이번 실행에서 산림청 산불 목록을 받지 못했습니다. 산불 정보를 내지 않습니다. 산림청 국가산불정보시스템을 직접 확인하십시오.",
                                                       "The Forest Service fire list could not be fetched in this run. No fire information is shown. Check the Forest Service site directly.")
    body += "<h2>%s</h2>" % L("산림청 목록의 산불", "Fires in the Forest Service list")
    if rec["kfs_ok"] and not rec["listed"]:
        body += "<p>%s</p>" % L("목록에 산불 없음.", "No fire listed.")
    elif rec["listed"]:
        rows = []
        byid = {F["id"]: F for F in rec["fires"]}
        for x in rec["listed"]:
            F = byid.get(x["id"])
            if F:
                fl = F.get("flags", {})
                g = flag_pill(fl.get("gust", {}).get("state"), "돌풍 경보", "gust flag")
                o = flag_pill(fl.get("oor", {}).get("state"), "범위 밖", "out of range", "범위 안", "in range")
                nums = (L("숫자 공개", "numbers shown") if F["publish_numbers"] else L("숫자 보류", "numbers withheld"))
                link = '<a href="fire/%s.html">%s</a>' % (E(x["id"]), L("산불 페이지", "fire page"))
                extra = "%s %s · %s · %s %s" % (g, o, nums, F.get("villages_affected", 0), L("개 마을·시설 영향", "villages/facilities affected"))
            else:
                link, extra = "", L("범위 밖 (경북·강원 진화 중 아님)", "not in scope (not active in Gyeongbuk/Gangwon)")
            rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                E(x["address"] or ""), E(x["status"] or x["status_code"] or ""),
                E(C.kst(C.parse_iso(x["report_utc"]))) if x["report_utc"] else "—", extra, link))
        body += '<div class="scroll"><table><tr><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th></th></tr>%s</table></div>' % (
            L("위치 (신고 주소)", "Location (reported address)"), L("상태", "Status"), L("신고 (KST)", "Reported (KST)"), L("이 서비스", "This service"), "".join(rows))
    if rec["kfs_ok"] and not rec["fires"]:
        body += '<div class="box">%s</div>' % L("현재 경상북도·강원도에 진화 중인 산불이 없습니다. 아래는 바람 경보입니다.",
                                                "No fire is active in Gyeongbuk or Gangwon now. The wind-flag bulletin follows.")
    body += bulletin_html(rec)
    body += "<h2>%s</h2>%s" % (L("자료와 나이", "Inputs and their age"), sources_table(rec))
    body += '<p class="small mut">%s</p>' % L(
        "산림청 자료는 공개 API가 아니라 국가산불정보시스템 웹 페이지가 쓰는 자료 호출을 30분에 한 번 읽은 것입니다. 이 서비스는 산림청·지자체와 관계가 없습니다.",
        "The Forest Service data is the data call behind its public web page, read once per 30 min; it is not a published API. This service has no connection to the Forest Service or local governments.")
    return page("산불 현황 (실시간 모델 출력)", "Fire status (live model output)", body, rec)


def cause_html(rec, F) -> str:
    """Reported cause (feed only, never guessed) and, apart and labelled as history, the ten-year shares by cause."""
    c = F.get("cause")
    if not c:      # a record written before amendment 2 has no cause block
        return ""
    ko, en = cause_mod.LABELS[c["status"]]
    shown = L(E(c["text"]), E(c["text"])) if c["text"] else L("미보고", "not reported")
    rep = E(C.kst(C.parse_iso(c["first_reported_utc"]))) + " KST" if c.get("first_reported_utc") else "—"
    pts = ("%d" % c["ignition_points"]) if c.get("ignition_points") else L("미보고", "not reported")
    h = '<h2>%s</h2><div class="box"><div class="vk">' % L("보고된 발생 원인", "Reported cause")
    rows = [(L("원인", "Cause"), "<b>%s</b>" % shown), (L("상태", "Status"), L(ko, en)),
            (L("최초 신고", "First reported"), rep), (L("발화점 수", "Ignition points"), pts)]
    h += "".join('<div class="k mut small">%s</div><div>%s</div>' % kv for kv in rows) + "</div>"
    if c.get("changes"):
        h += "<p class=small>%s</p>" % L("원인 표시가 바뀐 기록: ", "Cause changed since first listed: ") + "; ".join(
            E("%s KST: %s (%s) → %s (%s)" % (C.kst(C.parse_iso(x["utc"])), x["from"]["text"] or "미보고", x["from"]["status"],
                                              x["to"]["text"] or "미보고", x["to"]["status"])) for x in c["changes"])
    h += '<p class="small mut">%s</p></div>' % L(
        "산림청이 알린 내용만 그대로 보여 줍니다. 원인을 추정하거나 예측하지 않으며, 알리지 않으면 \"미보고\"입니다. 원인은 마지막 도로 차단 시각 계산에 쓰이지 않습니다. 발화점이 여럿이거나 재발화가 우려되면 진화 대응이 달라지므로 보여 줍니다.",
        "Shown exactly as the Forest Service lists it. This service does not guess or predict a cause; when the feed is silent it says \"not reported\". Cause is not used in the last-road-out calculation. It is shown because several ignition points or a likely re-ignition change how crews respond.")
    H = F.get("cause_history")
    if H and H["n_fires"]:
        bars = "".join('<div class="hb"><span>%s</span><span><i style="width:%.1f%%"></i></span><span>%.0f%% (%d)</span></div>' % (
            E(k), 100.0 * v / H["n_fires"], 100.0 * v / H["n_fires"], v) for k, v in sorted(H["by_cause"].items(), key=lambda kv: (-kv[1], kv[0])))
        pn = {"gyeongbuk": ("경상북도", "Gyeongbuk"), "gangwon": ("강원도", "Gangwon")}[H["province"]]
        h += '<h2>%s</h2><div class="box hist"><p class="notice">%s</p><p><b>%s</b></p>%s<p class="small mut">%s</p></div>' % (
            L("배경: 과거 통계 (이 산불에 대한 설명이 아님)", "Background: history (not a statement about this fire)"),
            L("아래는 과거 산불의 원인 비율입니다. 지금 이 산불의 원인에 대해 아무것도 말해 주지 않습니다.",
              "These are shares of past fires by recorded cause. They say nothing about the cause of this fire."),
            L("%s, %d월 산불 %d건의 원인 (%d–%d년)" % (pn[0], H["month"], H["n_fires"], H["years"][0], H["years"][1]),
              "%s, fires in month %d: %d fires by recorded cause (%d–%d)" % (pn[1], H["month"], H["n_fires"], H["years"][0], H["years"][1])),
            bars, L("출처: %s · 조회일 %s. 괄호는 건수. 원인은 산림청이 사후에 기록한 분류이며 '원인 미상'과 '기타'도 포함합니다." % (E(H["source"]), E(H["retrieved"])),
                   "Source: %s, retrieved %s. Counts in brackets. Causes are the Forest Service's after-the-fact classes; unknown and other are included." % (E(H["source"]), E(H["retrieved"]))))
    return h


def fire_html(rec, F, site: Path):
    R = rec["withheld_reasons"]
    body = '<div class="box"><p><b>%s</b> · %s %s KST · %s %.4f N, %.4f E</p>' % (
        E(F["address"] or ""), L("신고", "reported"), E(C.kst(C.parse_iso(F["report_utc"]))) if F.get("report_utc") else "—",
        L("신고 위치", "report point"), F["point"]["lat"] or 0, F["point"]["lon"] or 0)
    if F["withheld"]:
        body += '<div class="notice">%s%s</div>' % (L("이 산불의 시간 숫자를 내지 않습니다:", "No times are shown for this fire:"), reason_list(rec, F["withheld"]))
    body += "</div>"
    body += cause_html(rec, F)
    if "area" in F:
        a, m, fl = F["area"], F["margin"], F["flags"]
        srcs = ", ".join("%s %d" % (k, v) for k, v in sorted(a["n_by_src"].items()))
        body += '<h2>%s</h2><div class="box"><p>%s: %d (%s)</p><p>%s: %s KST (%s %.0f %s)</p><p>%s: %s · R(5 h) %.1f km · R(8 h) %.1f km%s</p></div>' % (
            L("알려진 화재 범위와 여유 거리", "Known fire area and reach margin"),
            L("구성 탐지 수", "Members"), a["n_members"], E(srcs),
            L("가장 최근 근거", "Newest evidence"), E(C.kst(C.parse_iso(a["latest_member_utc"]))), L("나이", "age"), a["evidence_age_min"], L("분", "min"),
            L("확산 등급 (직전 3시간)", "Spread class (prior 3 h)"), E(m["class"]), m["r5_km"], m["r8_km"],
            "" if m["prior3_km"] is None else " · prior-3 h %.1f km" % m["prior3_km"])
        g, o = fl.get("gust", {}), fl.get("oor", {})
        body += '<h2>%s</h2><div class="box"><p>%s %s · %s</p><p>%s %s · %s</p><p class="small mut">GFS cycle %s KST · %s</p></div>' % (
            L("경보", "Flags"), L("돌풍 규칙 G", "Gust rule G"), flag_pill(g.get("state"), "켜짐", "on"),
            E("8 h max gust %s m/s, 2-hour level %s m/s" % (g.get("max_gust_ms"), g.get("level_g_k2_ms"))),
            L("범위 밖 (보정 화재 28개 기준)", "Out of range (28 calibration fires)"), flag_pill(o.get("state"), "켜짐", "on"),
            E("score %s, tau %.4f%s%s" % (("%.4f" % o["score"]) if o.get("score") is not None else "—", C.settings()["flags"]["oor_tau"],
                                           ", lowest: %s" % o.get("lowest_predictor") if o.get("lowest_predictor") else "",
                                           ", partial (4 of 5 predictors)" if o.get("partial") else "")),
            E(C.kst(C.parse_iso(fl["gfs_cycle_utc"]))) if fl.get("gfs_cycle_utc") else "—",
            L("범위 밖이면 여유 거리가 보정 범위를 벗어난 조건이라 숫자를 보류합니다.", "When out of range, conditions are outside the calibration fires and the margin's numbers are withheld."))
    regions = F.get("zone", {}).get("regions_reached", [])
    body += "<h2>%s</h2>" % L("영향 받는 마을 (8시간 안)", "Villages affected (within 8 h)")
    if not regions:
        body += '<div class="box">%s</div>' % L("8시간 여유 거리 안에 도로 자료가 준비된 지역(영덕, 의성·안동)이 없습니다. 이 저장소에는 다른 지역의 도로 자료가 없어 마을별 도로 시간을 낼 수 없습니다.",
                                                "No prepared region (Yeongdeok, Uiseong-Andong) is within the 8 h margin. This repository has no road data elsewhere, so no per-village road times can be given.")
    for rid in regions:
        rr = rec["regions"].get(rid, {})
        body += "<h3>%s</h3>" % L(road.REGIONS[rid]["ko"], road.REGIONS[rid]["en"])
        if rr.get("refused"):
            body += '<div class="box notice">%s: %s</div>' % (L("도로 계층이 계산을 거부함", "The road layer refused"), "; ".join(
                "%s %s" % (E(x.get("code") or ""), L(E(x.get("ko") or ""), E(x.get("en") or ""))) for x in rr["refused"].get("reasons", [])) or E(", ".join(rr["refused"].get("codes", []))))
            continue
        if rr.get("error"):
            body += '<div class="box notice">%s</div>' % E(rr["error"])
            continue
        vs = rr.get("affected", [])
        show = F["publish_numbers"]
        cards = rr.get("cards") or {}
        rows = []
        order = sorted(vs, key=lambda v: (v["road_cut_s"] if v["road_cut_s"] is not None else 10 ** 9, v["name_ko"]))
        for v in order:
            c = v.get("card") or {}
            link = ""
            if c.get("page") and cards.get("pdf_ko") and show:
                link = '<a href="%s/%s#page=%d">%s</a>' % (E(F["id"]), E(cards["pdf_ko"]), c["page"], L("카드", "card")) + \
                       ' / <a href="%s/%s#page=%d">EN</a>' % (E(F["id"]), E(cards["pdf_en"]), c["page"])
            dep = ""
            if c.get("departure_group"):
                dep = "%s %s/%s" % (E(c["departure_group"]), E(c.get("departure_position") or ""), E(c.get("departure_group_size") or ""))
            if show:
                kv = [(L("현재 단계", "Stage now"), L(E(v["stage_ko"]), E(v["stage_en"])), False),
                      (L("출발 마감", "Leave by"), "<b>%s</b>" % L(E(v["leave_by_ko"]), E(v["leave_by_en"])), True),
                      (L("마지막 도로 차단", "Last road out cut"), L(E(v["road_cut_ko"]), E(v["road_cut_en"])), True),
                      (L("차단 후 화재 도달까지", "Road cut to fire arrival"), "%s %s" % (E(v["gap_min"] or "—"), L("분", "min")), True),
                      (L("화재 도달", "Fire arrival"), L(E(v["fire_arrival_ko"]), E(v["fire_arrival_en"])), True),
                      (L("안전 출발 시간대", "Safe departure windows"), L(E(v["windows_ko"]), E(v["windows_en"])), True),
                      (L("경고: 즉시 실행 전 도로 차단", "Flag: road cut before 'execute now'"), L(E(v["flag_ko"]), E(v["flag_en"])), False),
                      (L("마지막 출발 시 대피소", "Shelter (last departure)"), L(E(v["shelter_ko"]), E(v["shelter_en"])), False),
                      (L("출발 순서 (조 · 순번/조 크기)", "Departure order (group · position/size)"), dep or "—", False)]
                rows.append('<div class="box"><div><b>%s</b> <span class="small mut">%s %s</span></div><div class="vk">%s</div>%s</div>' % (
                    L(E(v["name_ko"]), E(v["name_en"])), E(v["county_ko"]), E(v["town_ko"]),
                    "".join('<div class="k mut small">%s</div><div%s>%s</div>' % (k, ' class="num"' if num else "", val) for k, val, num in kv),
                    ('<div class="small">%s</div>' % link) if link else ""))
        if vs and not show:
            towns = {}
            for v in order:
                towns.setdefault("%s %s" % (v["county_ko"], v["town_ko"]), []).append(v["name_ko"])
            body += '<div class="box"><p>%s <b>%d</b></p>%s</div>' % (
                L("8시간 안에 닿는 마을·시설 (시간 보류, 위 이유):", "Villages and facilities within reach in 8 h (times withheld, reasons above):"), len(vs),
                "".join("<p class=small><b>%s</b>: %s</p>" % (E(t), E(", ".join(n))) for t, n in sorted(towns.items())))
            continue
        if rows:
            body += '<div class="num-hide">%s</div>' % "".join(rows)
            body += '<p class="small mut">%s</p>' % L("시간은 이 지역에 닿는 모든 진화 중 산불을 함께 반영합니다. 출발 순서: 같은 도로를 같은 방향으로 쓰는 마을끼리 마감이 늦은 마을이 나중.",
                                                      "Times account for every active fire reaching this region. Departure order: villages sharing a road in the same direction leave one after another, latest deadline last.")
        else:
            body += '<div class="box">%s</div>' % L("8시간 안에 도로가 끊기거나 불이 닿는 마을 없음.", "No village has its road cut or the fire arriving within 8 h.")
    return page("산불: %s" % (F["address"] or F["id"]), "Fire: %s" % (F["address"] or F["id"]), body, rec, depth=1)


def cards_html(rec, places_json: str):
    body = '<div class="box notice">%s</div>' % L(
        "시연용입니다. 출구 수·위험 도로·대피소·가구 수 같은 화재와 무관한 사실과, 2025년 3월 25일 재현(현재 산불 아님) 카드 PDF로 연결합니다.",
        "Demonstration. Fire-independent facts (exits, dangerous road, shelters, households) and a link to the card PDF of the 25 March 2025 replay (not a current fire).")
    body += '<input type="search" id="q" placeholder="마을 이름 / village name (예: 동변리)" aria-label="search">'
    body += '<div id="out" class="small"></div>'
    body += """<script>var P=%s;var q=document.getElementById('q'),o=document.getElementById('out');
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function show(){var s=q.value.trim();var r=P.filter(function(p){return !s||(p.name+' '+p.sigungu+' '+p.eupmyeon).indexOf(s)>=0}).slice(0,60);
o.innerHTML=r.map(function(p){return '<div class="box"><b>'+esc(p.name||'(이름 없음 / unnamed)')+'</b> · '+esc(p.sigungu)+' '+esc(p.eupmyeon)+' · '+esc(p.category)+
'<br>출구 exits: <b>'+esc(p.exits)+'</b>'+(p.single_exit==='yes'?' (<b>출구 하나 / single exit</b>)':'')+' · 대피소 shelters: '+esc(p.exit_shelters)+
'<br>위험 도로 dangerous road: '+esc(p.danger_road)+'<br>가구 households: '+esc(p.households)+' ('+esc(p.households_status)+') · 차량 vehicles: '+esc(p.vehicles)+
' · 정리 시간 clearance: '+esc(p.clearance_min)+' min ('+esc(p.narrowest_road_class)+')'+
(p.page?'<br><a href="demo/'+esc(p.pdf_ko)+'#page='+p.page+'">카드 PDF (2025-03-25 재현)</a> · <a href="demo/'+esc(p.pdf_en)+'#page='+p.page+'">card PDF (2025-03-25 replay)</a>':'<br>'+esc(p.refusal||''))+'</div>'}).join('')||'<p>없음 / none</p>'}
q.addEventListener('input',show);show();</script>""" % places_json
    return page("마을 대피 카드 찾기 (시연)", "Village card lookup (demonstration)", body, rec)


def demo_places(site: Path) -> str:
    """Card lookup data from the committed worked-example audits; copies the example card PDFs to /live/demo/."""
    out = []
    demo = site / "demo"
    demo.mkdir(parents=True, exist_ok=True)
    for rid in road.REGIONS:
        d = next((C.ROADLAYER / "examples/cards").glob("%s_2*" % rid.rsplit("_", 1)[0]))
        pages = road.card_pages(d / ("cards_ko_%s.pdf" % rid), d / ("audit_%s.csv" % rid))
        for lang in ("ko", "en"):
            shutil.copy(d / ("cards_%s_%s.pdf" % (lang, rid)), demo / ("cards_%s_%s.pdf" % (lang, rid)))
        with open(d / ("audit_%s.csv" % rid), encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                out.append({k: r[k] for k in ("name", "sigungu", "eupmyeon", "category", "exits", "single_exit", "exit_shelters", "danger_road",
                                               "households", "households_status", "vehicles", "clearance_min", "narrowest_road_class", "refusal")}
                           | {"page": pages.get(r["place_id"]), "pdf_ko": "cards_ko_%s.pdf" % rid, "pdf_en": "cards_en_%s.pdf" % rid})
    return json.dumps(out, ensure_ascii=False).replace("</", "<\\/")


def build(rec, work: Path, site: Path) -> dict:
    """Write the site; returns {path: sha256}."""
    if site.exists():
        shutil.rmtree(site)
    (site / "fire").mkdir(parents=True)
    (site / "data").mkdir()
    files = {}

    def put(rel, text):
        p = site / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        b = text.encode("utf-8")
        p.write_bytes(b)
        files[rel] = C.sha256(b)

    put("index.html", index_html(rec))
    for F in rec["fires"]:
        put("fire/%s.html" % F["id"], fire_html(rec, F, site))
        for rid in (F.get("zone", {}).get("regions_reached", []) if F.get("publish_numbers") else []):
            cards = rec["regions"].get(rid, {}).get("cards") or {}
            for k in ("pdf_ko", "pdf_en"):
                src = work / rid / "cards" / cards.get(k, "-")
                if cards.get(k) and src.exists():
                    dst = site / "fire" / F["id"] / cards[k]
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(src, dst)
                    files["fire/%s/%s" % (F["id"], cards[k])] = C.sha256(dst.read_bytes())
    put("cards.html", cards_html(rec, demo_places(site)))
    pub = json.loads(json.dumps(rec, default=str))
    for rid, rr in pub.get("regions", {}).items():
        if rr.get("withheld"):
            rr["affected"] = [{k: v[k] for k in ("place_id", "name_ko", "name_en", "county_ko", "town_ko")} | {"times": "withheld"}
                              for v in rr.get("affected", [])]
            rr.pop("cards", None)
    put("data/latest.json", json.dumps(pub, ensure_ascii=False, indent=1, sort_keys=True))
    put(".nojekyll", "")
    return files
