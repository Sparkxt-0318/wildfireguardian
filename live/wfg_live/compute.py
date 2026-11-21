"""Compute stage: inputs folder -> record (dict) and road-layer outputs. No clock, no network (PROTOCOL §3-§7)."""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

from . import area, cause, common as C, fetch, flags, road

REASONS = {
    "KFS_MISSING": ("산불 목록을 이번 실행에서 받지 못함", "fire list not fetched in this run"),
    "FIRMS_MISSING": ("FIRMS 위성 탐지를 받지 못함", "FIRMS satellite detections not fetched"),
    "INPUT_OLD": ("입력 자료가 발표 시각보다 45분 이상 오래됨", "an input was fetched more than 45 min before the issue time"),
    "EVIDENCE_OLD": ("알려진 화재 범위의 최신 근거가 3시간보다 오래됨", "newest evidence of the known fire area is older than 3 h"),
    "FORECAST_MISSING": ("GFS 예보 주기가 없거나 불완전함 (범위 밖 여부 판단 불가)", "GFS cycle missing or incomplete (out-of-range check impossible)"),
    "OUT_OF_RANGE": ("예보 조건이 보정 화재 범위 밖 (여유 거리 숫자 보류)", "conditions outside the calibration fires (margin numbers withheld)"),
    "OOR_UNKNOWN": ("범위 밖 여부를 계산할 수 없음", "out-of-range check could not be computed"),
    "NO_LOCATION": ("신고 위치 좌표 없음", "no report coordinates"),
    "ROAD_REFUSED": ("도로 계층이 계산을 거부함", "the road layer refused"),
    "WITHHELD_NEIGHBOUR": ("같은 지역의 다른 산불 숫자가 보류됨", "another fire reaching the same region is withheld"),
}


def _src_ok(man, prefix):
    return [k for k, v in man["sources"].items() if k.startswith(prefix) and v["ok"]]


def single_exit_places() -> list:
    """Prepared places with single_exit = yes (committed card audits) with their road entry point."""
    out = []
    for rid in road.REGIONS:
        d = next((C.ROADLAYER / "examples/cards").glob("%s_2*" % rid.rsplit("_", 1)[0]))
        pts = {f["properties"]["id"]: f["properties"].get("entry") or {}
               for f in json.loads((C.REPO / "planner/public/data/regions" / rid / "places.geojson").read_text())["features"]}
        with open(d / ("audit_%s.csv" % rid), encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                e = pts.get(r["place_id"], {})
                out.append({"region": rid, "place_id": r["place_id"], "name": r["name"], "sigungu": r["sigungu"],
                            "eupmyeon": r["eupmyeon"], "single_exit": r["single_exit"] == "yes", "exits": r["exits"],
                            "lat": e.get("lat"), "lon": e.get("lon")})
    return out


def compute(inputs: Path, work: Path, replay: bool = False, with_cards: bool = True, cause_state: dict | None = None) -> dict:
    """`cause_state` (the log's state["cause"]) is updated in place when given; without it no cause change can be seen."""
    cfg = C.settings()
    man = json.loads((inputs / "manifest.json").read_text(encoding="utf-8"))
    T = C.parse_iso(man["issue_utc"])
    t_hour = T.replace(minute=0, second=0)
    rec = {"schema": "wfg.live.record/1", "issue_utc": C.iso(T), "issue_kst": C.kst(T), "issue_hour_utc": C.iso(t_hour),
           "settings_sha256": C.settings_sha256(), "protocol_sha256": C.sha256((C.LIVE / "PROTOCOL.md").read_bytes()),
           "notice": C.NOTICE, "inputs": man["sources"], "fires": [], "listed": []}
    lag_limit = T - timedelta(minutes=cfg["age"]["max_fetch_lag_min"])

    def too_old(name):
        m = man["sources"].get(name)
        return bool(m and m.get("ok") and C.parse_iso(m["fetched_utc"]) < lag_limit)

    fires = fetch.kfs_fires(inputs, man)
    rec["kfs_ok"] = fires is not None
    firms_ok = bool([k for k in _src_ok(man, "firms:") if "VIIRS" in k])
    rec["firms_ok"] = firms_ok
    gfs_m = man["sources"].get("gfs") or {}
    rec["gfs_ok"] = bool(gfs_m.get("ok"))
    rec["ahi_ok"] = bool((man["sources"].get("ahi") or {}).get("ok")) if "ahi" in man["sources"] else None
    firms_kept, firms_all = area.firms_rows(inputs, man) if firms_ok or _src_ok(man, "firms:") else ([], [])
    ahi = area.ahi_hotspots(inputs, man)
    rec["detections"] = {"firms_kept": len(firms_kept), "firms_all": len(firms_all), "ahi_hotspots": len(ahi)}

    rec["cause_feed"] = {"unknown_keys": cause.unknown_keys(fires), "note": "reported cause only; never inferred (PROTOCOL amendment 2)"}
    for f in fires or []:
        sc = fetch.in_scope(cfg, f)
        cb = cause.extract(cfg, f, C.iso(fetch.report_utc(f)))
        if cause_state is not None:
            cause.track(cause_state, str(f.get("frfrInfoId")), cb, rec["issue_utc"])
        rec["listed"].append({"cause": cb, "id": str(f.get("frfrInfoId")), "status_code": f.get("frfrPrgrsStcd"), "status": f.get("frfrPrgrsStcdNm"),
                              "address": f.get("frfrSttmnAddr"), "lgdng_cd": f.get("lgdngCd"), "step": f.get("frfrStepIssuNm"),
                              "contained_pct": f.get("frfrPotfrRt"), "report_utc": C.iso(fetch.report_utc(f)),
                              "lat": _num(f.get("frfrLctnYcrd")), "lon": _num(f.get("frfrLctnXcrd")), "in_scope": sc})

    import measured_arms as MA
    rasters = []
    for L in rec["listed"]:
        if not L["in_scope"]:
            continue
        F = {"id": L["id"], "address": L["address"], "report_utc": L["report_utc"], "point": {"lat": L["lat"], "lon": L["lon"]},
             "withheld": [], "cause": L["cause"],
             "cause_history": cause.history_for(cfg, L["address"], L["report_utc"])}
        if L["lat"] is None or L["lon"] is None or L["report_utc"] is None:
            F["withheld"].append("NO_LOCATION")
            rec["fires"].append(F)
            continue
        rep = C.parse_iso(L["report_utc"])
        ka = area.known_area((L["lat"], L["lon"]), rep, T, firms_kept, firms_all, ahi)
        discs = [dict(d, t=C.parse_iso(d["t_utc"])) for d in ka["discs"]]
        r5, r8, cls, prior3 = MA.curve(cfg["margin"]["arm"], discs, T, 8)
        F["area"] = {k: v for k, v in ka.items()}
        F["margin"] = {"arm": cfg["margin"]["arm"], "class": cls, "prior3_km": None if prior3 is None else round(prior3, 3),
                       "r5_km": r5 / 1000.0, "r8_km": r8 / 1000.0}
        F["flags"] = flags.fire_flags(inputs, man, t_hour, ka["centroid"], prior3)
        if not firms_ok:
            F["withheld"].append("FIRMS_MISSING")
        if any(too_old(k) for k in man["sources"] if k == "kfs" or k.startswith("firms:") or k == "ahi"):
            F["withheld"].append("INPUT_OLD")
        if ka["evidence_age_min"] > cfg["age"]["max_evidence_age_h"] * 60:
            F["withheld"].append("EVIDENCE_OLD")
        if not F["flags"]["gfs_complete"]:
            F["withheld"].append("FORECAST_MISSING")
        elif F["flags"]["oor"].get("state") is True:
            F["withheld"].append("OUT_OF_RANGE")
        elif F["flags"]["oor"].get("state") is None:
            F["withheld"].append("OOR_UNKNOWN")
        mins = road.arrival_minutes(discs, r5, r8)
        F["zone"] = {"regions_reached": road.regions_reached(mins)}
        rasters.append((F, mins))
        rec["fires"].append(F)

    # road layer per prepared region reached, on the minimum arrival over every in-scope fire reaching it
    rec["regions"] = {}
    for rid in road.REGIONS:
        contrib = [(F, m) for F, m in rasters if rid in F["zone"]["regions_reached"]]
        if not contrib:
            continue
        import numpy as np
        mins = np.minimum.reduce([m for _, m in contrib])
        rpath = work / rid / "arrival.tif"
        road.write_raster(rpath, mins, T, "live/ known fire area + research/kcf-replay MEASURED margin; fires %s"
                          % ",".join(F["id"] for F, _ in contrib))
        rr = road.run_roadlayer(rid, rpath, T, work / rid, replay, cards=with_cards)
        rr["fires"] = [F["id"] for F, _ in contrib]
        rr["raster_sha256"] = C.sha256(rpath.read_bytes())
        if "rows" in rr:
            rr["affected"] = road.affected(rr["rows"])
            if "cards" in rr:
                for v in rr["affected"]:
                    a = rr["cards"]["audit"].get(v["place_id"], {})
                    v["card"] = {"page": rr["cards"]["pages"].get(v["place_id"]), "exits": a.get("exits"),
                                 "single_exit": a.get("single_exit"), "departure_group": a.get("departure_group"),
                                 "departure_position": a.get("departure_position"),
                                 "departure_group_size": a.get("departure_group_size"),
                                 "departure_start_by_kst": a.get("departure_start_by_kst"), "departure_after": a.get("departure_after"),
                                 "leave_by_with_clearance_kst": a.get("leave_by_with_clearance_kst"),
                                 "clearance_min": a.get("clearance_min"), "trigger_kst": a.get("trigger_kst")}
            del rr["rows"]
            if "cards" in rr:
                rr["cards"].pop("audit", None)
        withheld = sorted({w for F, _ in contrib for w in F["withheld"]})
        rr["withheld"] = withheld
        if "refused" in rr:
            for F, _ in contrib:
                F["withheld"].append("ROAD_REFUSED")
        rec["regions"][rid] = rr
    for F in rec["fires"]:
        for rid in F.get("zone", {}).get("regions_reached", []):
            rr = rec["regions"].get(rid, {})
            if rr.get("withheld") and not F["withheld"]:
                F["withheld"].append("WITHHELD_NEIGHBOUR")
        F["withheld"] = sorted(set(F["withheld"]))
        F["publish_numbers"] = not F["withheld"]
        F["villages_affected"] = sum(len(rec["regions"].get(r, {}).get("affected", [])) for r in F.get("zone", {}).get("regions_reached", []))

    # bulletin (PROTOCOL §6)
    b = flags.bulletin_cells(inputs, man, t_hour)
    places = single_exit_places()
    on = [c for c in b["cells"] if c["state"]]
    for c in on:
        c["single_exit_places"] = [p for p in places if p["single_exit"] and p["lat"] is not None
                                   and c["lat0"] <= p["lat"] < c["lat0"] + 0.25 and c["lon0"] <= p["lon"] < c["lon0"] + 0.25]
    b["n_cells"] = len(b["cells"])
    b["n_on"] = len(on)
    rec["bulletin"] = b
    rec["withheld_reasons"] = {k: {"ko": v[0], "en": v[1]} for k, v in REASONS.items()}
    return rec


def _num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None
