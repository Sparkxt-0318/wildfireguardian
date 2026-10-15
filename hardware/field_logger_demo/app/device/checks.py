"""Result rows after a test recording or any pull from the device page (spec section 3C, "Results").
Values come only from the device's replies and the pulled file, decoded by usb_export.py. The page renders each row
from its id, mark and params (i18n keys res.<id>.<variant>)."""
from ..vendor import usb_export as ux

RESERVE_B = 32768
START_MIN_FREE_B = RESERVE_B + 8192     # below this the firmware refuses to start a recording
ROW_STEP_MAX_S = 1.6


def hours_left(free):
    return max(0.0, (free - RESERVE_B) / 48.0 / 3600.0)


def compute(s, ctx):
    """s: decoded Session of the pulled file. ctx: size_match, sha_match, sha, vbat (dict), free (int or None),
    restart_on_open (bool or None), screen (True/False/None), usb_power (bool)."""
    rows = []
    integ = s.integrity or {}
    n_rec = len(s.records)
    crc_ok = sum(1 for r in s.records if r["ok"])
    file_ok = ctx.get("size_match") and ctx.get("sha_match") and integ.get("status") in ("OK", "RECOVERED")
    rows.append({"id": "file", "mark": "ok" if file_ok else "bad", "variant": "ok" if file_ok else "bad",
                 "p": {"sha": (ctx.get("sha") or s.sha256)[:6] + "…" + (ctx.get("sha") or s.sha256)[-4:],
                       "ok": crc_ok, "total": n_rec, "status": integ.get("status")}})
    er = s.end_reason
    if er == "USER_STOP":
        rows.append({"id": "ended", "mark": "ok", "variant": "user_stop", "p": {"reason": er}})
    elif er == "RECOVERED_ON_BOOT":
        rows.append({"id": "ended", "mark": "info", "variant": "recovered", "p": {"reason": er}})
    elif er:
        rows.append({"id": "ended", "mark": "bad", "variant": "other", "p": {"reason": er}})
    else:
        rows.append({"id": "ended", "mark": "bad", "variant": "open", "p": {}})
    obs = [r for r in s.rows if r["mono"] is not None]
    steps = [(b["mono"] - a["mono"]) / 1000.0 for a, b in zip(obs, obs[1:])]
    n = len(obs)
    mx = max(steps) if steps else 0.0
    at = obs[steps.index(mx) + 1]["t"] if steps else 0.0
    fillers = sum(1 for r in obs if r.get("filler"))
    if n < 20:
        rows.append({"id": "spacing", "mark": "bad", "variant": "short", "p": {"n": n}})
    elif mx > ROW_STEP_MAX_S:
        rows.append({"id": "spacing", "mark": "bad", "variant": "step", "p": {"n": n, "max": round(mx, 1),
                                                                               "at": round(at, 1)}})
    elif fillers >= n / 2:
        rows.append({"id": "spacing", "mark": "ok", "variant": "filler", "p": {"n": n}})
    else:
        rows.append({"id": "spacing", "mark": "ok", "variant": "normal", "p": {"n": n, "max": round(mx, 1)}})
    n_fix = sum(1 for r in obs if r["fix"])
    reasons = {}
    for r in obs:
        if not r["fix"]:
            reasons[r["nofix_reason"]] = reasons.get(r["nofix_reason"], 0) + 1
    last_st = s.status[-1] if s.status else None
    nmea_ok = last_st["nmea_ok"] if last_st else None
    nmea_bad = last_st["nmea_bad"] if last_st else None
    if n_fix or reasons.get("RECEIVER_NO_FIX"):
        rows.append({"id": "gnss", "mark": "ok", "variant": "talking", "p": {"nmea": nmea_ok, "bad": nmea_bad}})
    elif reasons.get("CHECKSUM_ERRORS_ONLY", 0) > reasons.get("NO_NMEA_DATA", 0):
        rows.append({"id": "gnss", "mark": "bad", "variant": "cksum", "p": {"nmea": nmea_ok, "bad": nmea_bad}})
    else:
        rows.append({"id": "gnss", "mark": "bad", "variant": "nodata", "p": {"nmea": nmea_ok, "bad": nmea_bad}})
    if n_fix:
        fx = [r for r in obs if r["fix"]]
        sats = max((r["sats"] or 0) for r in fx)
        hd = [r["hdop"] for r in fx if r["hdop"] is not None]
        rows.append({"id": "position", "mark": "info", "variant": "fix",
                     "p": {"n": n_fix, "sats": sats, "hdop": min(hd) if hd else None}})
    else:
        rows.append({"id": "position", "mark": "info", "variant": "none", "p": {}})
    n_ev = len(s.events)
    rows.append({"id": "button", "mark": "ok" if n_ev else "bad", "variant": "ok" if n_ev else "none", "p": {"n": n_ev}})
    vb = ctx.get("vbat") or {}
    cal = vb.get("cal")
    if last_st and last_st["vbat_mv"] is not None and (last_st["flags"] & ux.ST_BATT_VALID):
        rows.append({"id": "battery", "mark": "ok", "variant": "ok",
                     "p": {"v": round(last_st["vbat_mv"] / 1000.0, 2), "usb": bool(ctx.get("usb_power", True)),
                           "uncal": cal in (None, "1.000")}})
    else:
        rows.append({"id": "battery", "mark": "bad", "variant": "none", "p": {}})
    free = ctx.get("free")
    if free is None and last_st:
        free = last_st["fs_free"]
    if free is not None and free >= START_MIN_FREE_B:
        rows.append({"id": "storage", "mark": "ok", "variant": "ok",
                     "p": {"mb": round(free / 1e6, 2), "h": round(hours_left(free), 1)}})
    else:
        rows.append({"id": "storage", "mark": "bad", "variant": "low", "p": {"mb": round((free or 0) / 1e6, 2)}})
    sc = ctx.get("screen")
    rows.append({"id": "screen", "mark": "wait" if sc is None else ("ok" if sc else "bad"),
                 "variant": "ask" if sc is None else ("seen" if sc else "unseen"), "p": {}})
    rr = ctx.get("restart_on_open")
    rows.append({"id": "restart", "mark": "info", "variant": "unknown" if rr is None else ("yes" if rr else "no"),
                 "p": {}})
    rows.append({"id": "clock", "mark": "info", "variant": "synced" if s.clocks else "later", "p": {}})
    counts = {k: sum(1 for r in rows if r["mark"] == k) for k in ("ok", "info", "bad", "wait")}
    monos = [r["mono"] for r in s.records if r.get("mono") is not None]
    if len(monos) >= 2:
        duration = (max(monos) - min(monos)) / 1000.0     # START to END (or to the last record a restart left)
    else:
        duration = (obs[-1]["t"] - obs[0]["t"] + 1.0) if obs else 0.0
    return {"rows": rows, "counts": counts, "total": len(rows), "ok": counts["bad"] == 0,
            "session": ctx.get("device_name") or s.name, "sid": s.sid, "records": n_rec, "duration_s": duration}
