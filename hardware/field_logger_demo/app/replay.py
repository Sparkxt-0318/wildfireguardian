"""Build the replay payload the page plays: rows, records for the log stream, stops, gaps, metrics, zones.

Everything inside a privacy zone is removed here, before it reaches the page: coordinates become null and the
lat/lon bytes and the CRC of the record hex are masked. The page never receives a hidden coordinate.
"""
import json

from . import config, geo, library, privacy, stops
from .geo import haversine


def _r(v, n=7):
    return None if v is None else round(v, n)


def _first_fix(s):
    for r in s.rows:
        if r["fix"] and r["lat"] is not None:
            return r["lat"], r["lon"]
    return None, None


def area_meta(area):
    if not area:
        return None
    p = config.MAPDATA / area / "meta.json"
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    m["layers"] = sorted(x.stem for x in (config.MAPDATA / area).glob("*.geojson"))
    return m


def detect_area(bounds, sim=False):
    """Map data whose bounds contain the session's centre (used when the library entry names no area). A simulated
    session gets only the synthetic map and a real one only real map data: a SIM track is never drawn on real
    streets, nor a real track on invented ones (without real map data, a real session is drawn on the grid)."""
    if not bounds:
        return None
    cx, cy = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
    found = []
    for p in sorted(config.MAPDATA.glob("*/meta.json")):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        b = m.get("bounds")
        if b and b[0] <= cx <= b[2] and b[1] <= cy <= b[3] and bool(m.get("synthetic")) == bool(sim):
            found.append(p.parent.name)
    return found[0] if found else None


def build(entry):
    """entry: a sessions.json entry (or the default entry for a file)."""
    s = library.load(library.safe_path(entry["file"]))
    mode = s.mode
    res = stops.analyse(s.rows, mode, events=s.events, marks_are_stops=bool(entry.get("marks_are_stops")))
    zones = privacy.zones_for(s, entry.get("privacy"))
    obs, states, sp = res["obs"], res["states"], res["speeds"]
    row_index = {id(r): i for i, r in enumerate(obs)}
    hidden_rec = set()
    rows = []
    for i, (r, st) in enumerate(zip(obs, states)):
        hid = bool(r["fix"] and privacy.inside(zones, r["lat"], r["lon"]))
        if hid:
            hidden_rec.add(r["idx"])
        v = sp.get(i)
        rows.append({"t": round(r["t"], 3), "f": 1 if r["fix"] else 0,
                     "la": None if hid else _r(r["lat"]), "lo": None if hid else _r(r["lon"]), "h": 1 if hid else 0,
                     "s": st, "v": _r(r["speed"], 2), "vs": _r(v[2], 3) if v else None,
                     "vsrc": v[1] if v else None, "n": r["sats"], "hd": r["hdop"], "ft": r["fix_type"],
                     "nr": r["nofix_reason"], "fl": 1 if r.get("filler") else 0, "i": r["idx"], "u": r["utc_ms"]})
    events = []
    for e in s.events:
        hid = bool(e["located"] and privacy.inside(zones, e["lat"], e["lon"]))
        if hid:
            hidden_rec.add(e["idx"])
        events.append({"en": e["event_no"], "tp": _r(e["t_press"], 3), "t": _r(e["t"], 3), "lc": 1 if e["located"] else 0,
                       "la": None if hid else _r(e["lat"]), "lo": None if hid else _r(e["lon"]), "h": 1 if hid else 0,
                       "i": e["idx"]})
    recs = []
    prev_seq = prev_i = None
    seq_breaks = seq_missing = 0
    for r in s.records:
        hx = r.get("hex")
        if r["idx"] in hidden_rec:
            hx = privacy.mask_hex(hx, r["type"])
        elif not r["ok"] and hx:
            # a record that fails its CRC cannot be placed, so its position bytes may lie in a zone: always masked
            hx = privacy.mask_hex(hx, "FIX")
        o = {"i": r["idx"], "sq": r["seq"], "ty": r["type"], "t": _r(r.get("t"), 3), "u": r.get("utc_ms"),
             "ok": 1 if r["ok"] else 0, "hx": hx}
        # A record whose seq does not follow the last readable one (corrupt records keep their place, so they are
        # counted as positions, not as missing): reported in the log stream and on the summary, never repaired.
        if r["ok"] and r["seq"] is not None:
            if prev_seq is not None:
                expected = prev_seq + (r["idx"] - prev_i)
                if r["seq"] != expected:
                    o["sg"] = [prev_seq, r["seq"], max(0, r["seq"] - expected)]
                    seq_breaks += 1
                    seq_missing += max(0, r["seq"] - expected)
            prev_seq, prev_i = r["seq"], r["idx"]
        if "clock" in r:
            c = s.clocks[r["clock"]]
            o["ck"], o["cd"] = c["kind"], c["delta"]
        if "row" in r:
            row = s.rows[r["row"]]
            o["row"] = row_index.get(id(row))
        if "event" in r:
            o["ev"] = r["event"]
        if "status" in r:
            stt = s.status[r["status"]]
            o.update({"vb": stt["vbat_mv"], "ff": stt["fs_free"], "nmea": stt["nmea_ok"]})
        recs.append(o)
    stop_out = []
    for st in res["stops"]:
        hid = privacy.inside(zones, st["lat"], st["lon"])
        stop_out.append({"n": st["n"], "t0": st["t0"], "t1": st["t1"], "dur": st["dur"], "td": st["t_detect"],
                         "la": None if hid else _r(st["lat"]), "lo": None if hid else _r(st["lon"]), "h": 1 if hid else 0,
                         "me": st.get("match_event"), "mg": _r(st.get("match_gap"), 1), "nr": st["n_rows"],
                         "hd": st["median_hdop"]})
    gap_out = []
    for g in res["gaps"]:
        a, b = obs[g["a"]], obs[g["b"]]
        ha = privacy.inside(zones, a["lat"], a["lon"])
        hb = privacy.inside(zones, b["lat"], b["lon"])
        gap_out.append({"t0": g["t0"], "t1": g["t1"], "dur": g["dur"], "span_m": round(g["span_m"], 1),
                        "a": None if (ha or hb) else [_r(a["lon"]), _r(a["lat"])],
                        "b": None if (ha or hb) else [_r(b["lon"]), _r(b["lat"])]})
    vis = [r for r in rows if r["f"] and not r["h"] and r["la"] is not None]
    bounds = None
    if vis:
        bounds = [min(r["lo"] for r in vis), min(r["la"] for r in vis), max(r["lo"] for r in vis), max(r["la"] for r in vis)]
    integ = s.integrity or {}
    area = entry.get("area") or detect_area(bounds, sim=bool(s.sim))
    meta = {"key": entry.get("key"), "file": entry["file"], "name": s.name, "title_ko": entry.get("title_ko"),
            "title_en": entry.get("title_en"), "sid": s.sid, "device": s.device_label, "device_id": s.device_id,
            "mode": mode, "source": s.source, "sim": bool(s.sim),
            "sim_kind": ("double" if (s.sim_meta or {}).get("double") else "sim") if s.sim else None,
            "sha256": s.sha256, "size": s.size,
            "n_rec": len(s.records), "has_crc": s.source != "gpx",
            "crc_ok": sum(1 for r in s.records if r["ok"]) if s.source != "gpx" else None,
            "seq_breaks": seq_breaks, "seq_missing": seq_missing,
            "integrity": {k: integ.get(k) for k in ("status", "crc_errors", "seq_errors", "trailing_bytes", "has_end",
                                                     "end_reason")},
            "end_reason": s.end_reason, "start_reason": s.start_reason, "resumed_from": s.resumed_from,
            "tz": entry.get("tz") or geo.tz_for(*_first_fix(s)) or config.DEFAULT_TZ, "area": area,
            "area_meta": area_meta(area),
            "utc0": s.first_utc(), "t_end": max((r["t"] for r in rows), default=0.0),
            "device_test": entry["file"].startswith("real/device_tests/"),
            "nmea_last": s.status[-1]["nmea_ok"] if s.status else None}
    m = res["metrics"]
    return {"meta": meta, "rows": rows, "records": recs, "events": events, "stops": stop_out, "gaps": gap_out,
            "steps": [[round(t, 3), round(d, 2)] for t, d in res["steps"]],
            "span": list(res["span"]) if res["span"] else None, "metrics": m, "params": res["params"],
            "validation": res.get("validation"), "sensitivity": res.get("sensitivity"),
            "zones": [{"la": _r(z["lat"]), "lo": _r(z["lon"]), "r": z["radius_m"], "kind": z["kind"]}
                      for z in privacy.page_zones(zones, _points(s))],
            "bounds": bounds}


def _points(s):
    """Every stored position of a session: its fixes and its located button marks."""
    return ([(r["lat"], r["lon"]) for r in s.rows if r["fix"] and r["lat"] is not None]
            + [(e["lat"], e["lon"]) for e in s.events if e.get("located") and e.get("lat") is not None])


def summary_numbers(payload):
    """The numbers written to summary.json (the same ones the summary page shows)."""
    m = payload["metrics"] or {}
    meta = payload["meta"]
    out = {"session_id": meta["sid"], "file": meta["name"], "sha256": meta["sha256"], "device": meta["device"],
           "simulated": meta["sim"], "source": meta["source"],
           "device_recording": meta["source"] != "gpx" and not meta["sim"],
           "mode": meta["mode"], "records": meta["n_rec"], "records_crc_ok": meta["crc_ok"],
           "seq_breaks": meta["seq_breaks"], "records_missing": meta["seq_missing"],
           "analysed_span_s": [payload["span"][0], payload["span"][1]] if payload["span"] else None,
           "metrics": m, "parameters": payload["params"], "validation": payload["validation"],
           "sensitivity": payload["sensitivity"],
           "stops": [{"n": s["n"], "t0_s": s["t0"], "t1_s": s["t1"], "duration_s": s["dur"], "lat": s["la"], "lon": s["lo"],
                      "inside_privacy_zone": bool(s["h"]), "n_rows": s["nr"], "median_hdop": s["hd"],
                      "matched_event_no": s["me"]} for s in payload["stops"]],
           "gaps": [{"t0_s": g["t0"], "t1_s": g["t1"], "duration_s": g["dur"], "span_m": g["span_m"]}
                    for g in payload["gaps"]],
           "privacy_zones": len(payload["zones"])}
    return out


def nearest_check(payload):
    """Test helper: the largest distance from any visible fix to any zone centre minus radius (must be >= 0)."""
    worst = None
    for r in payload["rows"]:
        if r["la"] is None:
            continue
        for z in payload["zones"]:
            d = haversine(r["la"], r["lo"], z["la"], z["lo"]) - z["r"]
            worst = d if worst is None else min(worst, d)
    return worst
