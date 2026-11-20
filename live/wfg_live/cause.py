"""Reported cause of each fire (PROTOCOL amendment 2). Report only: nothing here predicts or infers a cause.

The Forest Service feed carries no cause (live/README.md, "Cause"). This module reads a cause only from the feed keys
named in config/live.toml [cause]; with those lists empty, every fire is "not reported". It never fills a gap from a
code it cannot read, from the fire's place or season, or from the history table.
"""
from __future__ import annotations

import json
from datetime import datetime

from . import common as C

STATUSES = ("confirmed", "presumed", "investigating", "unspecified", "not_reported")
LABELS = {
    "confirmed": ("확정", "confirmed"),
    "presumed": ("추정", "presumed"),
    "investigating": ("조사 중", "under investigation"),
    "unspecified": ("상태 표시 없음", "status not stated by the feed"),
    "not_reported": ("미보고", "not reported"),
}
# Keys seen in the KFS list on 2026-11-21 (live/README.md). A key outside this set is listed in the record so a person looks at it.
KNOWN_KEYS = frozenset("""frfrLctnXcrd frfrLctnYcrd frfrPrgrsStcd frfrPrgrsStcdNm frfrOccrrTpcd frfrOccrrStcd frfrStepIssuCd frfrStepIssuNm
frfrPotfrRt frfrSttmnDt frfrSttmnHms frfrPotfrRtDtm frfrInfoId frfrOccrrPbmrl frfrSttmnLctnXcrd frfrSttmnLctnYcrd frfrSttmnAddr
frfrSttmnAddrDe potfrCmpleDtm frfrOccrrWndrcCd frfrFrngDtm lgdngCd""".split())


def _first(f: dict, keys):
    for k in keys:
        v = f.get(k)
        if v is not None and str(v).strip() != "":
            return k, v
    return None, None


def extract(cfg: dict, f: dict, report_utc: str | None) -> dict:
    """The cause block for one raw KFS fire. Pure."""
    c = cfg.get("cause", {})
    kc, text = _first(f, c.get("feed_cause_keys", []))
    ks, sword = _first(f, c.get("feed_status_keys", []))
    kp, pts = _first(f, c.get("feed_points_keys", []))
    try:
        n = int(str(pts).strip()) if pts is not None else None
        n = n if n is not None and n >= 1 else None
    except ValueError:
        n = None
    if text is None:
        status, text_out = "not_reported", None
    else:
        text_out = str(text).strip()
        status = c.get("status_words", {}).get(str(sword).strip(), "unspecified") if sword is not None else "unspecified"
    return {"text": text_out, "status": status, "status_word": None if sword is None else str(sword).strip(),
            "first_reported_utc": report_utc, "ignition_points": n,
            "source_fields": [k for k in (kc, ks, kp) if k], "changes": []}


def track(state: dict, fire_id: str, block: dict, issue_utc: str) -> None:
    """Compare with the last run's cause for this fire (state is updated in place) and fill block["changes"].

    A change is any difference in text or status between two runs, including a cause appearing, disappearing or being
    revised. The earlier values are kept in the log's state, never overwritten in earlier records."""
    s = state.setdefault(fire_id, {"first_seen_utc": issue_utc, "history": []})
    last = s["history"][-1] if s["history"] else None
    now = {"utc": issue_utc, "text": block["text"], "status": block["status"], "ignition_points": block["ignition_points"]}
    if last is None:
        s["history"].append(now)
    elif (last["text"], last["status"], last["ignition_points"]) != (now["text"], now["status"], now["ignition_points"]):
        s["history"].append(now)
    block["first_seen_utc"] = s["first_seen_utc"]
    block["changes"] = [{"utc": b["utc"], "from": {"text": a["text"], "status": a["status"]}, "to": {"text": b["text"], "status": b["status"]}}
                        for a, b in zip(s["history"], s["history"][1:])]


def unknown_keys(fires) -> list:
    return sorted({k for f in fires or [] for k in f if k not in KNOWN_KEYS})


PROVINCE = (("경상북도", "gyeongbuk"), ("경북", "gyeongbuk"), ("강원", "gangwon"))


def province_of(address: str | None) -> str | None:
    a = address or ""
    return next((p for pre, p in PROVINCE if a.startswith(pre)), None)


def history_for(cfg: dict, address: str | None, report_utc: str | None) -> dict | None:
    """Share of fires by recorded cause, same province and calendar month (KST), 2016-2025. History, not this fire."""
    prov = province_of(address)
    if not prov or not report_utc:
        return None
    month = "%02d" % C.parse_iso(report_utc).astimezone(C.KST).month
    p = C.LIVE / cfg["cause"]["history_file"]
    if not p.exists():
        return None
    h = json.loads(p.read_text(encoding="utf-8"))
    by = h["provinces"][prov][month]
    return {"province": prov, "month": int(month), "years": h["years"], "n_fires": sum(by.values()), "by_cause": by,
            "source": h["source"], "source_page": h["source_page"], "retrieved": h["retrieved"]}
