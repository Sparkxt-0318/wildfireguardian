"""Alerts (PROTOCOL §9): only (1) a fire first affecting any village, (2) a last-road-out time moving > 15 min."""
from __future__ import annotations

import json
import os
import smtplib
import urllib.parse
from datetime import timedelta
from email.message import EmailMessage

from . import common as C

FOOT = "\n\n" + C.NOTICE["ko"] + "\n" + C.NOTICE["en"]


def channels():
    ch = []
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        ch.append("telegram")
    if all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "ALERT_EMAIL_TO")):
        ch.append("email")
    return ch


def decide(rec, state) -> list:
    """Messages to send, from the record and the alert state (dict, updated in place). Pure: no network."""
    move = C.settings()["alerts"]["move_min"] * 60
    T = C.parse_iso(rec["issue_utc"])
    st = state.setdefault("fires", {})
    msgs = []
    for F in rec["fires"]:
        regions = F.get("zone", {}).get("regions_reached", [])
        vs = [v for r in regions for v in rec["regions"].get(r, {}).get("affected", [])]
        s = st.setdefault(F["id"], {"first_sent": False, "cut_utc": {}})
        url = "https://sparkxt-0318.github.io/wildfireguardian/live/fire/%s.html" % F["id"]
        if vs and not s["first_sent"]:
            s["first_sent"] = True
            names = ", ".join(v["name_ko"] for v in vs[:12]) + (" 외 %d곳" % (len(vs) - 12) if len(vs) > 12 else "")
            msgs.append({"kind": "first_affect", "fire": F["id"],
                         "text": "[산불 모델 출력] %s 산불: 8시간 안에 영향 받는 마을·시설 %d곳 (%s). %s\n"
                                 "[Model output] Fire at %s: %d villages/facilities affected within 8 h. %s\n%s%s"
                                 % (F["address"], len(vs), names, "" if F["publish_numbers"] else "시간 숫자 보류.", F["address"], len(vs),
                                    "" if F["publish_numbers"] else "Times withheld.", url, FOOT)})
        if not F["publish_numbers"]:
            continue
        moved = []
        for v in vs:
            if v["road_cut_s"] is None:
                continue
            cut = T + timedelta(seconds=v["road_cut_s"])
            prev = s["cut_utc"].get(v["place_id"])
            if prev is None:
                s["cut_utc"][v["place_id"]] = C.iso(cut)
                continue
            d = (cut - C.parse_iso(prev)).total_seconds()
            if abs(d) > move:
                moved.append((v, prev, cut, d))
                s["cut_utc"][v["place_id"]] = C.iso(cut)
        if moved:
            lines = ["%s: %s → %s KST (%+d분/min)" % (v["name_ko"], C.kst(C.parse_iso(p))[11:], C.kst(c)[11:], round(d / 60)) for v, p, c, d in moved[:15]]
            msgs.append({"kind": "cut_moved", "fire": F["id"],
                         "text": "[산불 모델 출력] %s 산불: 마지막 도로 차단 시각이 15분 넘게 바뀐 마을 %d곳\n[Model output] last-road-out time moved > 15 min at %d places\n%s\n%s%s"
                                 % (F["address"], len(moved), len(moved), "\n".join(lines), url, FOOT)})
    return msgs


def send(msgs) -> dict:
    ch = channels()
    if not msgs:
        return {"channels": ch, "sent": [], "note": "nothing to send"}
    if not ch:
        return {"channels": [], "sent": [], "skipped": [m["kind"] for m in msgs],
                "note": "alerts skipped: no Telegram or email credentials in the environment"}
    sent, errors = [], []
    for m in msgs:
        if "telegram" in ch:
            data = urllib.parse.urlencode({"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": m["text"][:4000],
                                           "disable_web_page_preview": "true"}).encode()
            st, body, err = C.http("https://api.telegram.org/bot%s/sendMessage" % os.environ["TELEGRAM_BOT_TOKEN"], data=data, attempts=2, wait=3)
            (sent if st == 200 else errors).append({"kind": m["kind"], "channel": "telegram", "status": st})
        if "email" in ch:
            try:
                em = EmailMessage()
                em["Subject"] = "[모델 출력·참고용] wfg live: %s" % m["kind"]
                em["From"] = os.environ["SMTP_USER"]
                em["To"] = os.environ["ALERT_EMAIL_TO"]
                em.set_content(m["text"])
                with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "465")), timeout=30) as s:
                    s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
                    s.send_message(em)
                sent.append({"kind": m["kind"], "channel": "email"})
            except Exception as e:  # noqa: BLE001
                errors.append({"kind": m["kind"], "channel": "email", "error": type(e).__name__})
    return {"channels": ch, "sent": sent, "errors": errors}
