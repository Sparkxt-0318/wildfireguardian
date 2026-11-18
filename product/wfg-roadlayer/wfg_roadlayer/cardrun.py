"""`cards` command: village cards (A5, ko + en), audit CSV, pickup list, departure order, for one region and one fire input.

Writes
  <out>/cards_ko_<region>.pdf, <out>/cards_en_<region>.pdf   one A5 page per checkable place (sorted by 시군, 읍면, leave-by)
  <out>/audit_<region>.csv                                    one row per place, every value with its status
  <out>/pickup_<region>.csv                                   the van routes, stop by stop
  <out>/cards.json                                            inputs, settings, counts, file hashes
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path

from . import __version__, cardpdf, cards, fmt, overlap, pdfsheet, pipeline
from .errors import Refusal, reason

STATUS_CAP = {"motorway": "ASSUMED lanes x CITED per-lane", "trunk": "ASSUMED lanes x CITED per-lane",
              "primary": "CITED (two-lane assumed)", "secondary": "CITED (two-lane assumed)", "tertiary": "CITED (two-lane assumed)"}

AUDIT_COLS = [
    "region", "place_id", "name", "sigungu", "eupmyeon", "category", "refusal",
    "exits", "exit_shelters", "exit_length_km", "exit_travel_min", "exit_forest_share_pct", "exit_conifer_share",
    "danger_road", "danger_osm_way", "danger_cell", "danger_cell_centre_epsg5179", "danger_exits_cut", "danger_ties",
    "danger_travel_min_from_village", "single_exit", "dangerous_road_cuts_all",
    "households", "households_status", "households_basis", "vehicles", "vehicles_status", "no_car_persons", "no_car_status",
    "route_for_clearance", "narrowest_road_class", "narrowest_osm_way", "narrowest_capacity_veh_per_h", "capacity_status",
    "clearance_min", "leave_by_kst", "leave_by_with_clearance_kst", "short_with_clearance_min", "margin_min",
    "leave_by_with_margin_kst", "trigger_kst", "trigger_state",
    "departure_group", "departure_position", "departure_group_size", "departure_start_by_kst", "departure_short_min",
    "departure_after", "departure_shared_roads", "van", "van_first_arrival_kst", "van_last_arrival_kst", "van_after_leave_by",
    "van_unserved_within_horizon", "van_not_planned_road_cut", "replay_earliest_cut_kst", "replay_earliest_quartile", "notice"]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _kst(issue, s):
    return "" if s is None else fmt.full(fmt.t_floor(issue, s))


def _edges_index(road, size=1000.0):
    buckets = defaultdict(list)
    for j in range(len(road.tail)):
        (x0, y0), (x1, y1) = road.node_xy[road.tail[j]], road.node_xy[road.head[j]]
        for bx in range(int(min(x0, x1) // size), int(max(x0, x1) // size) + 1):
            for by in range(int(min(y0, y1) // size), int(max(y0, y1) // size) + 1):
                buckets[(bx, by)].append(j)

    def edges_in(xa, ya, xb, yb):
        out = set()
        for bx in range(int(xa // size), int(xb // size) + 1):
            for by in range(int(ya // size), int(yb // size) + 1):
                out.update(buckets.get((bx, by), ()))
        return sorted(out)
    return edges_in


def audit_rows(recs, rid, issue, ccfg, ways, road, replay):
    early, _ = overlap.early_set(replay) if replay else (set(), None)
    rows = []
    for r in recs:
        o = r["origin"]
        v = {k: "" for k in AUDIT_COLS}
        v.update(region=rid, place_id=o["id"], name=o["name"], sigungu=o["sigungu"], eupmyeon=o["eupmyeon"], category=o["category"],
                 notice=fmt.NOTICE["en"] + " / " + fmt.NOTICE["ko"])
        if replay is not None:
            t = replay.get((rid, o["id"]))
            v["replay_earliest_cut_kst"] = "" if t is None else ("not cut" if t == overlap.NEVER else t.strftime("2025-%m-%d %H:%M"))
            v["replay_earliest_quartile"] = "yes" if (rid, o["id"]) in early else "no"
        if r["refusal"]:
            v["refusal"] = r["refusal"][2]
            rows.append(v)
            continue
        P = r["paths"]
        v.update(exits=str(r["exits"]) + ("+" if r["exits"] >= ccfg["exits"]["max_exits"] else ""),
                 exit_shelters="|".join((p["shelter"]["name"] or p["shelter"]["id"]) if p["shelter"] else "" for p in P),
                 exit_length_km="|".join("%.2f" % (p["length_m"] / 1000) for p in P),
                 exit_travel_min="|".join("%.1f" % (p["travel_s"] / 60) for p in P),
                 exit_forest_share_pct="|".join("%.0f" % (100 * p["forest_share"]) for p in P),
                 exit_conifer_share="NOT AVAILABLE: no forest-type map in the repository; exit_forest_share_pct is any OSM forest within 50 m",
                 single_exit="yes" if r["single_exit"] else "no", dangerous_road_cuts_all="yes" if r["danger_all"] else "no")
        d = r["danger"]
        if d:
            rr, cc = divmod(d["cell"], road.W)
            res = float(road.res)
            v.update(danger_road=cards.way_label(ways, d["way"], "ko"), danger_osm_way=d["way"], danger_cell=d["cell"],
                     danger_cell_centre_epsg5179="%.0f %.0f" % (float(road.x0) + (cc + .5) * res, float(road.y0) + (rr + .5) * res),
                     danger_exits_cut=d["cut"], danger_ties=d["tied"], danger_travel_min_from_village="%.1f" % (d["first_s"] / 60))
        h = r["hh"]
        v.update(households=h["households"] if h["kind"] == "village" else "0 (care facility)", households_status="ASSUMED",
                 households_basis=h["basis"], vehicles=r["vehicles"],
                 vehicles_status="ASSUMED: households x %.3f (DERIVED, Gyeongbuk vehicles / households)" % ccfg["traffic"]["vehicles_per_household"],
                 no_car_persons=r["no_car_persons"],
                 no_car_status=("ASSUMED: %d care-facility residents" % r["no_car_persons"]) if h["kind"] != "village" else
                 "ASSUMED: households x %.2f no-car share x persons/household (CITED)" % ccfg["traffic"]["no_car_share"],
                 route_for_clearance={"last": "route at the leave-by time", "exit1": "exit route 1 (no route in the fire field)"}.get(r["route_kind"], ""),
                 narrowest_road_class=r["narrow_class"] or "", narrowest_osm_way=r["narrow_way"] or "",
                 narrowest_capacity_veh_per_h=r["narrow_cap"] or "",
                 capacity_status=STATUS_CAP.get((r["narrow_class"] or "").replace("_link", ""), "ASSUMED"),
                 clearance_min="" if r["clearance_s"] is None else "%.1f" % (r["clearance_s"] / 60),
                 margin_min=ccfg["trigger"]["margin_min"], trigger_state=r["trigger_state"])
        row = r["row"]
        if row["leave_by"] is None:
            v["leave_by_kst"] = "no safe departure at the issue time"
        elif r["no_deadline"]:
            v["leave_by_kst"] = "no deadline within the horizon"
        else:
            v["leave_by_kst"] = _kst(issue, r["leave_by"])
            lc = r["leave_by_clear"]
            v["leave_by_with_clearance_kst"] = _kst(issue, max(lc, 0))
            v["short_with_clearance_min"] = "%.1f" % (-lc / 60) if lc < 0 else "0"
        v["leave_by_with_margin_kst"] = _kst(issue, r["leave_by_m"]) if r["leave_by_m"] is not None else \
            ("no deadline within the horizon" if r["m_no_deadline"] else "none (margin already lost)")
        v["trigger_kst"] = _kst(issue, r["trigger_s"]) if r["trigger_state"] == "line" else ""
        if r.get("dep_group"):
            v.update(departure_group=r["dep_group"], departure_position=r["dep_pos"], departure_group_size=r["dep_size"],
                     departure_start_by_kst=_kst(issue, max(r["dep_start"], 0)), departure_short_min="%.1f" % (r["dep_late"] / 60),
                     departure_after=(r["dep_before"]["name"] or r["dep_before"]["id"]) if r.get("dep_before") else "",
                     departure_shared_roads="|".join(cards.way_label(ways, w, "ko") for w in r["dep_roads"]))
        if r["no_car_persons"]:
            e = r.get("pickup_first")
            v.update(van=e["van"] if e else "", van_first_arrival_kst=_kst(issue, e["arrive"]) if e else "",
                     van_last_arrival_kst=_kst(issue, r.get("pickup_last_s")) if e else "",
                     van_after_leave_by="yes" if r.get("pickup_late") else "no",
                     van_unserved_within_horizon=r.get("pickup_unserved", 0),
                     van_not_planned_road_cut="yes" if (r.get("pickup_unreachable") or row["leave_by"] is None) else "no")
        rows.append(v)
    return rows


def csv_bytes(header, rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow([r[k] for k in header])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def pickup_rows(pk, issue):
    out = []
    seq = Counter()
    for e in pk["log"]:
        seq[e["van"]] += 1
        r = e["rec"]
        if e["kind"] == "pickup":
            out.append({"van": e["van"], "stop": seq[e["van"]], "action": "pick up / 승차", "place": r["origin"]["name"] or r["origin"]["id"],
                        "place_id": r["origin"]["id"], "eupmyeon": r["origin"]["eupmyeon"], "arrive_kst": _kst(issue, e["arrive"]),
                        "persons": e["persons"], "van_load": e["load"], "left_at_place": e["remaining"],
                        "place_leave_by_kst": _kst(issue, r["leave_by"]) if r["leave_by"] is not None else "no deadline in horizon",
                        "after_leave_by": "yes" if e["late"] else "no"})
        else:
            out.append({"van": e["van"], "stop": seq[e["van"]], "action": "unload / 하차", "place": e["where"]["name"] or e["where"]["id"],
                        "place_id": e["where"]["id"], "eupmyeon": "", "arrive_kst": _kst(issue, e["arrive"]), "persons": e["persons"],
                        "van_load": 0, "left_at_place": "", "place_leave_by_kst": "", "after_leave_by": ""})
    for r in pk["unserved"]:
        out.append({"van": "", "stop": "", "action": "not served within the horizon / 예측 범위 안 승합차 배정 못 함",
                    "place": r["origin"]["name"] or r["origin"]["id"], "place_id": r["origin"]["id"], "eupmyeon": r["origin"]["eupmyeon"],
                    "arrive_kst": "", "persons": pk["left"][id(r)], "van_load": "", "left_at_place": pk["left"][id(r)],
                    "place_leave_by_kst": _kst(issue, r["leave_by"]) if r["leave_by"] is not None else "no deadline in horizon",
                    "after_leave_by": ""})
    for r in pk["unreachable"]:
        out.append({"van": "", "stop": "", "action": "not planned: road already cut / 계획 없음: 도로 이미 끊김",
                    "place": r["origin"]["name"] or r["origin"]["id"], "place_id": r["origin"]["id"], "eupmyeon": r["origin"]["eupmyeon"],
                    "arrive_kst": "", "persons": r["no_car_persons"], "van_load": "", "left_at_place": r["no_car_persons"],
                    "place_leave_by_kst": "", "after_leave_by": ""})
    return out


PICKUP_COLS = ["van", "stop", "action", "place", "place_id", "eupmyeon", "arrive_kst", "persons", "van_load", "left_at_place",
               "place_leave_by_kst", "after_leave_by"]


def run_cards(*, region_name, issue_time, raster=None, packet=None, horizon_min=None, not_reached_value=None, as_of=None,
              settings_path=None, card_settings=None, out=None, workers=None, assume_uncovered=False, overwrite=False, cache=None,
              replay_check=True, log=print) -> dict:
    t0 = time.perf_counter()
    ccfg = cards.load_settings(card_settings)
    kw = dict(region_name=region_name, issue_time=issue_time, raster=raster, packet=packet, horizon_min=horizon_min,
              not_reached_value=not_reached_value, as_of=as_of, settings_path=settings_path, out=out, workers=workers,
              assume_uncovered=assume_uncovered, overwrite=overwrite, cache=cache, log=log,
              default_out_fn=lambda rid, issue: Path("wfg-roadlayer-cards") / ("%s_%s" % (rid, issue.strftime("%Y%m%dT%H%MZ"))))
    c = pipeline.compute(**kw)
    M = int(round(ccfg["trigger"]["margin_min"] * 60))
    cm = pipeline.compute(**dict(kw, log=lambda *_: None), shift_s=M) if M else c
    rid, region, road, issue = c["rid"], c["region"], c["region"].road, c["fire"].issue_utc
    out = c["out"]
    recs = cards.compute(c, cm, ccfg)
    forest, ways = cards.load_edge_data(rid)
    ngroups = cards.departure_order(recs, road, ways, ccfg["traffic"])
    pk = cards.pickup(recs, region, c["H"], ccfg["pickup"])
    replay = overlap.earliest_cut() if (replay_check and overlap.PER_PLACE.is_file()) else None
    arrival_all = cards.full_grid_arrival(c)
    t_comp = time.perf_counter()

    tmp = out.with_name(out.name + ".partial")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    files = {}

    def put(rel, data):
        (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp / rel).write_bytes(data)
        files[rel] = _sha(data)

    put("audit_%s.csv" % rid, csv_bytes(AUDIT_COLS, audit_rows(recs, rid, issue, ccfg, ways, road, replay)))
    put("pickup_%s.csv" % rid, csv_bytes(PICKUP_COLS, pickup_rows(pk, issue)))
    pdfsheet.register_fonts(c["fonts"])
    fire = c["fire"]
    ctx = {"issue": issue, "road": road, "ccfg": ccfg, "tcfg": ccfg["traffic"], "horizon_s": c["H"], "as_of_given": c["as_of_given"],
           "ways": ways, "arrival_all": arrival_all, "edges_in": _edges_index(road),
           "fire_label": "%s (sha256 %s…)" % (Path(fire.path).name, fire.sha256[:12]),
           "run_label": "wfg-roadlayer %s cards · %s · %s" % (__version__, rid, issue.strftime("%Y%m%dT%H%MZ"))}
    ok = [r for r in recs if not r["refusal"]]

    def key(r):
        lb = r["row"]["leave_by"]
        return (r["origin"]["sigungu"], r["origin"]["eupmyeon"], 0 if lb is None else 1 if not r["no_deadline"] else 2,
                lb or 0, r["origin"]["name"], r["origin"]["id"])
    ok.sort(key=key)
    for lang in ("ko", "en"):
        rel = "cards_%s_%s.pdf" % (lang, rid)
        cardpdf.build(tmp / rel, ok, lang, ctx, "%s %s" % ({"ko": "마을 대피 카드", "en": "Village evacuation cards"}[lang], region.name[lang]))
        files[rel] = _sha((tmp / rel).read_bytes())
    t_out = time.perf_counter()
    counts = Counter()
    for r in recs:
        if r["refusal"]:
            counts["refused"] += 1
            continue
        counts["cards"] += 1
        counts["exits_%d" % r["exits"]] += 1
        counts["single_exit"] += r["single_exit"]
        counts["dangerous_road_cuts_all"] += r["danger_all"]
        counts["trigger_" + r["trigger_state"]] += 1
        if r["leave_by_clear"] is not None and r["leave_by_clear"] < 0:
            counts["deadline_missed_with_clearance"] += 1
        if r.get("dep_group"):
            counts["in_departure_group"] += 1
            counts["departure_short"] += r["dep_late"] > 0
        if r["no_car_persons"]:
            counts["pickup_places"] += 1
            counts["pickup_after_leave_by"] += bool(r.get("pickup_late"))
            counts["pickup_persons"] += r["no_car_persons"]
            counts["pickup_persons_unserved_within_horizon"] += r.get("pickup_unserved", 0)
    counts["departure_groups"] = ngroups
    man = {"schema": "wfg.roadlayer.cards/1", "tool": "wfg-roadlayer %s" % __version__, "notice": fmt.NOTICE_LONG, "region": rid,
           "issue_utc": issue.strftime("%Y-%m-%dT%H:%M:%SZ"), "fire_input_sha256": fire.sha256, "horizon_s": c["H"],
           "as_of_utc": c["now"].strftime("%Y-%m-%dT%H:%M:%SZ"),
           "card_settings": {k: v for k, v in ccfg.items() if not k.startswith("_")}, "card_settings_files": ccfg["_sources"],
           "settings": {k: v for k, v in c["cfg"].items() if not k.startswith("_")},
           "data": {"edges_forest_sha256": _sha((cards.PRODUCT / "data/edges" / ("%s_forest.csv.gz" % rid)).read_bytes()),
                    "edges_ways_sha256": _sha((cards.PRODUCT / "data/edges" / ("%s_ways.csv.gz" % rid)).read_bytes()),
                    "households_sha256": _sha((cards.PRODUCT / "data/households" / ("%s.csv" % rid)).read_bytes()),
                    "traffic_sources_sha256": _sha((cards.PRODUCT / "data/traffic_sources.json").read_bytes())},
           "pickup_depot": pk["depot"]["name"] or pk["depot"]["id"], "counts": dict(sorted(counts.items())),
           "files_sha256": dict(sorted(files.items())),
           "run_time_s": {"total": round(t_out - t0, 1), "compute": round(t_comp - t0, 1), "outputs": round(t_out - t_comp, 1)}}
    (tmp / "cards.json").write_text(json.dumps(man, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    if out.exists():
        shutil.rmtree(out)
    tmp.rename(out)
    log("%s: %d cards, %s -> %s (%.1f s)" % (rid, counts["cards"], ", ".join("%s %d" % kv for kv in sorted(counts.items())), out, t_out - t0))
    return {"manifest": man, "recs": recs, "out": out, "replay": replay}


def overlap_report(results, path_md: Path, path_json: Path):
    replay = next((r["replay"] for r in results if r["replay"]), None)
    if replay is None:
        raise Refusal(reason("REPLAY_MISSING", "research/kcf-replay/per_place.csv 가 없습니다.", "research/kcf-replay/per_place.csv not found."))
    flags = {}
    for res in results:
        rid = res["manifest"]["region"]
        for r in res["recs"]:
            if not r["refusal"]:
                flags[(rid, r["origin"]["id"])] = {"single_exit": r["single_exit"], "dangerous_road": r["danger_all"]}
    tab = overlap.table(flags, replay)
    path_json.write_text(json.dumps(tab, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    path_md.write_text("# Overlap: road-structure flags vs earliest replay cut-off\n\n" + fmt.NOTICE["ko"] + " / " + fmt.NOTICE["en"] +
                       "\n\n" + (overlap.__doc__ or "").strip() + "\n\n" + overlap.markdown(tab), encoding="utf-8")
    return tab
