"""One run: inputs → refusal checks → field → CSV (ko, en), A4 sheets per 읍·면 (ko, en), certificates, run.json."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__, certs, engine, fireinput, fmt, geotiff, pdfsheet, regiondata, report, settings as settings_mod
from .errors import Refusal, reason

HERE = Path(__file__).resolve().parent


def parse_time(s: str | None, what_ko: str, what_en: str, code: str) -> datetime | None:
    if s is None:
        return None
    try:
        dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise Refusal(reason(code, "%s 형식을 읽을 수 없습니다: %r (예: 2025-03-25T18:00+09:00)" % (what_ko, s),
                             "cannot read %s: %r (e.g. 2025-03-25T18:00+09:00)" % (what_en, s))) from exc
    if dt.tzinfo is None:
        raise Refusal(reason(code, "%s 에 시간대가 없습니다: %r (+09:00 또는 Z 를 붙이십시오)" % (what_ko, s),
                             "%s has no time zone: %r (add +09:00 or Z)" % (what_en, s)))
    return dt.astimezone(timezone.utc)


def freshness(issue: datetime, as_of: datetime, region, cfg) -> None:
    f = cfg["freshness"]
    out = []
    age = (as_of - issue).total_seconds() / 60
    if age > f["max_fire_input_age_min"]:
        out.append(reason("FIRE_INPUT_STALE",
                          "화재 도달 입력이 오래되었습니다: 발표 %s, 기준 시각 %s (%.0f분 경과, 한도 %g분)." % (
                              fmt.full(fmt.kst(issue)), fmt.full(fmt.kst(as_of)), age, f["max_fire_input_age_min"]),
                          "the fire-arrival input is stale: issued %s KST, as-of %s KST (%.0f min old, limit %g min)." % (
                              fmt.full(fmt.kst(issue)), fmt.full(fmt.kst(as_of)), age, f["max_fire_input_age_min"])))
    if -age > f["max_issue_ahead_min"]:
        out.append(reason("ISSUE_TIME_IN_FUTURE", "발표 시각 %s 이 기준 시각 %s 보다 %.0f분 뒤입니다." % (
            fmt.full(fmt.kst(issue)), fmt.full(fmt.kst(as_of)), -age),
                          "the issue time %s KST is %.0f min after the as-of time %s KST." % (
                              fmt.full(fmt.kst(issue)), -age, fmt.full(fmt.kst(as_of)))))
    for key, lim, ko, en, code in (("graph", f["max_road_age_days"], "도로망", "road graph", "ROADS_STALE"),
                                   ("places", f["max_places_age_days"], "마을·대피소 자료", "places and shelters", "PLACES_STALE")):
        snap = regiondata.parse_utc(region.meta[key]["snapshot_utc"])
        days = (issue - snap).total_seconds() / 86400
        if days > lim:
            out.append(reason(code, "%s 이 오래되었습니다: %s 자료, 발표 시각보다 %.0f일 이전 (한도 %g일)." % (ko, snap.date(), days, lim),
                              "the %s are stale: snapshot %s, %.0f days before the issue time (limit %g days)." % (en, snap.date(), days, lim)))
    if out:
        raise Refusal(out)


def default_out(rid: str, issue: datetime) -> Path:
    return Path("wfg-roadlayer-out") / ("%s_%s" % (rid, issue.strftime("%Y%m%dT%H%MZ")))


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def run(*, region_name, issue_time, raster=None, packet=None, horizon_min=None, not_reached_value=None, as_of=None,
        settings_path=None, out=None, workers=None, assume_uncovered=False, overwrite=False, cache=None, log=print,
        heat=None, heat_threshold=None, fragility=False) -> dict:
    t0 = time.perf_counter()
    if fragility:  # the fragility columns are computed from the raster closures only; heat closures are not included
        heat_on = bool(heat) if heat is not None else bool(settings_mod.load(settings_path)["heat"]["enabled"])
        if heat_on:
            raise Refusal(reason("FRAGILITY_WITH_HEAT",
                                 "--fragility 는 복사열 도로 폐쇄를 반영하지 않습니다. --heat 없이 실행하십시오.",
                                 "--fragility does not include the heat closures; run it without --heat."))
    c = compute(region_name=region_name, issue_time=issue_time, raster=raster, packet=packet, horizon_min=horizon_min,
                not_reached_value=not_reached_value, as_of=as_of, settings_path=settings_path, out=out, workers=workers,
                assume_uncovered=assume_uncovered, overwrite=overwrite, cache=cache, log=log, heat=heat,
                heat_threshold=heat_threshold)
    if fragility:  # optional columns and pages (research/kcf-robust); off by default, nothing else changes
        from . import fragility as frag_mod
        t_f = time.perf_counter()
        c["fragility"] = frag_mod.compute(c, raster, HERE.parent, log=log)
        c["fragility_s"] = round(time.perf_counter() - t_f, 1)
    return _write_outputs(c, t0)


def compute(*, region_name, issue_time, raster=None, packet=None, horizon_min=None, not_reached_value=None, as_of=None,
            settings_path=None, out=None, workers=None, assume_uncovered=False, overwrite=False, cache=None, log=print,
            default_out_fn=None, shift_s: int = 0, heat=None, heat_threshold=None) -> dict:
    """Inputs, refusal checks and the deadline field; no file written. ``shift_s`` > 0 moves every closure that many
    seconds earlier (floored at 0): the latest departures then keep that margin before fire arrival everywhere on the
    route and at the shelter (used by the village cards' trigger line; 0 for the sheets)."""
    cfg = settings_mod.load(settings_path)
    if heat is not None:
        cfg["heat"]["enabled"] = 1 if heat else 0
    if heat_threshold is not None:
        cfg["heat"]["threshold_kw_m2"] = float(heat_threshold)
    rid = regiondata.resolve_region(region_name)
    issue = parse_time(issue_time, "발표 시각", "the issue time", "ISSUE_TIME_INVALID")
    as_of_dt = parse_time(as_of, "기준 시각", "the as-of time", "AS_OF_INVALID")
    missing = []
    if issue is None:
        declared = None
        try:
            if raster is not None and Path(raster).is_file():
                declared = geotiff.read(raster).metadata.get("WFG_ISSUE_TIME")
            elif packet is not None and (Path(packet) / "REPORT.json").is_file():
                declared = json.loads((Path(packet) / "REPORT.json").read_text())["native_metadata"].get("time_origin")
        except Exception:  # the hint is optional; the refusal stands either way
            declared = None
        hint = (" (입력 파일에는 %s 로 적혀 있음; 확인 후 --issue-time 으로 주십시오)" % declared, " (the input file says %s; "
                "check it and pass it with --issue-time)" % declared) if declared else ("", "")
        missing.append(reason("ISSUE_TIME_MISSING", "발표 시각(--issue-time)이 없습니다%s." % hint[0],
                              "no issue time given (--issue-time)%s." % hint[1]))
    if raster is None and packet is None:
        missing.append(reason("FIRE_INPUT_MISSING", "화재 도달 입력이 없습니다 (--raster 또는 --packet).",
                              "no fire-arrival input given (--raster or --packet)."))
    if raster is not None and packet is not None:
        missing.append(reason("FIRE_INPUT_AMBIGUOUS", "--raster 와 --packet 중 하나만 주십시오.", "give either --raster or --packet, not both."))
    if missing:
        raise Refusal(missing)
    out = Path(out) if out else (default_out_fn or default_out)(rid, issue)
    if out.exists() and any(out.iterdir()) and not overwrite:
        raise Refusal(reason("OUTPUT_NOT_EMPTY", "출력 폴더가 비어 있지 않습니다: %s (--overwrite 로 교체)" % out,
                             "the output folder is not empty: %s (use --overwrite to replace it)" % out))
    cache = Path(cache) if cache else regiondata.default_cache()
    fonts = regiondata.font_paths(cache)
    region = regiondata.Region(rid, cache)
    region.candidates(cfg["routing"]["shelters_per_village"])
    if raster is not None:
        fire = fireinput.load_geotiff(raster, region.road, issue_utc=issue, horizon_min=horizon_min, not_reached_value=not_reached_value)
    else:
        fire = fireinput.load_packet(packet, region.road, issue_utc=issue)
    as_of_given = as_of_dt is not None
    now = as_of_dt or datetime.now(timezone.utc)
    freshness(fire.issue_utc, now, region, cfg)
    if fire.uncovered and not assume_uncovered:
        xs = [region.road.cell_rect(c) for c in fire.uncovered[:3]]
        where = "; ".join("x %.0f–%.0f, y %.0f–%.0f" % r for r in xs)
        raise Refusal(reason("FIRE_INPUT_UNCOVERED",
                             "도로가 지나는 375 m 셀 %d개에 화재 도달 자료가 없습니다 (nodata 또는 래스터 밖; 예: %s, EPSG:5179). "
                             "자료를 채우거나, 그 셀을 '도달 없음'으로 보는 가정을 받아들이면 --assume-uncovered-not-reached 를 주십시오 "
                             "(모든 쪽에 표시됨)." % (len(fire.uncovered), where),
                             "%d road cells (375 m) have no fire-arrival data (nodata or outside the raster; e.g. %s, EPSG:5179). "
                             "Fill them, or pass --assume-uncovered-not-reached to read them as not reached (printed on every page)."
                             % (len(fire.uncovered), where)))
    fire.uncovered_set = set(fire.uncovered)
    H = fire.horizon_s
    dwell = cfg["routing"]["dwell_s"]
    if H - dwell < 0:
        raise Refusal(reason("HORIZON_TOO_SHORT", "예측 범위가 대피소 체류 시간보다 짧습니다.", "the horizon is shorter than the shelter stay."))
    close_s = {k: max(0, v - shift_s) for k, v in fire.arrival_s.items()} if shift_s else dict(fire.arrival_s)
    t_in = time.perf_counter()
    inst = engine.build_instance(region.road, close_s, H)
    nodeb, heat_info, hc = None, None, None
    if cfg["heat"]["enabled"]:
        from . import heat as heat_mod
        import dataclasses
        fire_h = dataclasses.replace(fire, arrival_s=close_s) if shift_s else fire
        hc, heat_info = heat_mod.build(region, fire_h, cfg)
        inst.B, inst.W = hc.edge_blocks(), hc.wait_blocks()
        nodeb = hc.node_b
        log("%s: heat option on, %g kW/m2; safe distance max %.0f m over %d reached road cells" % (
            rid, heat_info["threshold_kw_m2"], heat_info["road_cells_safe_distance_m_max"], heat_info["road_cells_reached"]))
    jobs_by = defaultdict(set)
    for o in region.origins:
        if o["node"] is None or not o["checkable"]:
            continue
        for s in region.cands.get(o["id"], []):
            jobs_by[s["node"]].add(o["node"])
    jobs = [(sn, engine.accept(region.road, close_s, sn, H, dwell, nodeb),
             [(on, engine.origin_closure(region.road, close_s, on, H, nodeb)) for on in sorted(ons)]) for sn, ons in sorted(jobs_by.items())]
    nw = engine.default_workers(workers if workers is not None else cfg["run"]["workers"])
    log("%s: %d villages and facilities, %d shelter passes, %d workers" % (rid, len(region.origins), len(jobs), nw))
    results = engine.run_passes(region.road, inst, jobs, nw)
    rows = engine.assemble(region, fire, cfg, inst, results, close_s, nodeb)
    t_field = time.perf_counter()
    return {"cfg": cfg, "rid": rid, "out": out, "region": region, "fire": fire, "now": now, "as_of_given": as_of_given,
            "H": H, "dwell": dwell, "close_s": close_s, "inst": inst, "rows": rows, "nw": nw, "fonts": fonts, "t_in": t_in,
            "t_field": t_field, "assume_uncovered": assume_uncovered, "log": log, "jobs": len(jobs), "heat": heat_info, "hc": hc}


def _write_outputs(c: dict, t0: float) -> dict:
    cfg, rid, out, region, fire, now, as_of_given, H, dwell = (c[k] for k in ("cfg", "rid", "out", "region", "fire", "now",
                                                                            "as_of_given", "H", "dwell"))
    close_s, inst, rows, nw, fonts, t_in, t_field = (c[k] for k in ("close_s", "inst", "rows", "nw", "fonts", "t_in", "t_field"))
    assume_uncovered, log = c["assume_uncovered"], c["log"]

    # ------------------------------------------------------------------------------------ outputs
    tmp = out.with_name(out.name + ".partial")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    fire_label = "%s %s (sha256 %s…)" % ("GeoTIFF" if fire.kind == "geotiff" else "packet", Path(fire.path).name, fire.sha256[:12])
    ctx = {"issue": fire.issue_utc, "horizon_s": H, "settings": cfg, "road": region.road, "as_of": now, "as_of_given": as_of_given,
           "fire_label": fire_label, "road_date": region.meta["graph"]["snapshot_utc"][:10],
           "places_date": region.meta["places"]["snapshot_utc"][:10],
           "run_label": "wfg-roadlayer %s · %s · %s%s" % (__version__, rid, fire.issue_utc.strftime("%Y%m%dT%H%MZ"),
                                                         (" · heat %g kW/m²" % c["heat"]["threshold_kw_m2"]) if c.get("heat") else ""),
           "assumed_uncovered": len(fire.uncovered) if assume_uncovered else 0}
    if c.get("fragility") is not None:
        ctx["fragility"] = c["fragility"]
    files = {}

    def put(rel: str, data: bytes):
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        files[rel] = _sha(data)

    put("ko/마을별_도로차단_%s.csv" % rid, report.csv_bytes(rows, "ko", ctx))
    put("en/villages_road_cut_%s.csv" % rid, report.csv_bytes(rows, "en", ctx))
    pdfsheet.register_fonts(fonts)
    groups = defaultdict(list)
    for r in rows:
        groups[(r["origin"]["sigungu"], r["origin"]["eupmyeon"])].append(r)
    sheets = []
    for (sg, em), grp in sorted(groups.items()):
        for lang in ("ko", "en"):
            c_lab = report.county_label(grp[0]["origin"], lang)
            t_lab = report.town_label(grp[0]["origin"], lang)
            if lang == "ko":
                rel = "ko/sheets/%s_%s.pdf" % (sg or "시군미확인", em or "읍면동미확인")
            else:
                rel = "en/sheets/%s_%s.pdf" % (fmt.romanize(sg) if sg else "county-unknown", fmt.romanize(em) if em else "town-unknown")
            fs = pdfsheet.build(tmp / rel, lang, c_lab, t_lab, grp, ctx)
            files[rel] = _sha((tmp / rel).read_bytes())
            sheets.append({"file": rel, "villages": len(grp), "font_pt": fs})
            if c.get("fragility") is not None:
                from . import fragsheet
                frel = rel.replace("/sheets/", "/fragility/")
                ffs = fragsheet.build(tmp / frel, lang, c_lab, t_lab, grp, ctx, c["fragility"])
                files[frel] = _sha((tmp / frel).read_bytes())
                sheets.append({"file": frel, "villages": len(grp), "font_pt": ffs, "kind": "fragility"})
    cdir = tmp / "certificates"
    raw = certs.instance_bytes(region.road, inst, close_s, H, dwell, c.get("hc"))
    inst_sha = certs.write_instance(cdir, raw)
    (cdir / "README.md").write_text(certs.README, encoding="utf-8")
    ncert = 0
    for r in rows:
        if r["refusal"]:
            continue
        p = certs.write_village(cdir, r, ctx, inst_sha)
        files[str(p.relative_to(tmp))] = _sha(p.read_bytes())
        ncert += 1
    for rel in ("certificates/checker.py", "certificates/verify_certificate.py", "certificates/README.md"):
        files[rel] = _sha((tmp / rel).read_bytes())
    t_out = time.perf_counter()
    counts = defaultdict(int)
    for r in rows:
        if r["refusal"]:
            counts["refused"] += 1
        elif r["cut"] is None:
            counts["not_cut_within_horizon"] += 1
        elif r["cut"] == 0:
            counts["cut_at_issue"] += 1
        else:
            counts["cut_within_horizon"] += 1
        if not r["refusal"] and r["flag"]:
            counts["flag_cut_before_execute_now"] += 1
    run_time = round(t_out - t0, 1)
    manifest = {
        "schema": "wfg.roadlayer.run/1", "tool": "wfg-roadlayer %s" % __version__,
        "notice": fmt.NOTICE_LONG,
        "region": {"id": rid, "name": region.name, "graph_sha256": region.graph_sha256, "graph_snapshot_utc": region.meta["graph"]["snapshot_utc"],
                   "places_sha256": region.places_sha256, "places_snapshot_utc": region.meta["places"]["snapshot_utc"],
                   "towns_sha256": region.towns_sha256, "graph_revision": region.road.revision},
        "fire_input": {"kind": fire.kind, "file": Path(fire.path).name, "sha256": fire.sha256, "issue_utc": fire.issue_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "horizon_s": H, "road_cells": len(region.road.road_cells), "road_cells_closed_within_horizon": len(close_s),
                       "road_cells_uncovered": len(fire.uncovered), "assumed_uncovered_not_reached": bool(assume_uncovered),
                       "info": fire.info},
        "as_of_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "as_of_given_by_operator": as_of_given,
        "settings": {k: v for k, v in cfg.items() if not k.startswith("_")}, "settings_files": cfg["_sources"],
        "model": {"field": "research/harness-2026-11/F-3.1/deadline_field/core.py (vendored, sha256 %s)" % _sha((HERE / "vendor/deadline_field/core.py").read_bytes()),
                  "checker": "research/kcf-theorem/checker.py (vendored, sha256 %s)" % _sha((HERE / "vendor/kcf_theorem/checker.py").read_bytes()),
                  "instance": "research/kcf-replay/replay.py rules; closures permanent", "instance_sha256_uncompressed": inst_sha},
        "heat": c.get("heat"),
        "counts": dict(sorted(counts.items())), "villages": len(rows), "certificates": ncert, "sheets": sheets,
        "files_sha256": dict(sorted(files.items())),
        **({"fragility": {"method": "research/kcf-robust; wfg_roadlayer/fragility.py", "reach_step_km": 0.125, "reach_max_km": 15.0,
                          "timing_step_s": 60, "seconds": c.get("fragility_s"),
                          "villages": {k: {kk: vv for kk, vv in v.items() if kk != "method"} for k, v in sorted(c["fragility"].items())}}}
           if c.get("fragility") is not None else {}),
        "run_time_s": {"total": run_time, "field": round(t_field - t_in, 1), "outputs": round(t_out - t_field, 1), "workers": nw},
        "versions": {"python": platform.python_version(), "numpy": __import__("numpy").__version__,
                     "reportlab": __import__("reportlab").Version},
    }
    (tmp / "run.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    if out.exists():
        shutil.rmtree(out)
    tmp.rename(out)
    log("%s: %d rows (%s); %d sheets; %d certificates -> %s" % (rid, len(rows), ", ".join("%s %d" % kv for kv in sorted(counts.items())),
                                                               len(sheets), ncert, out))
    log("run time: %.1f s (field %.1f s, outputs %.1f s, %d workers)" % (run_time, t_field - t_in, t_out - t_field, nw))
    return manifest


def write_refusal(out: Path | None, ref: Refusal):
    if out is None:
        return
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "REFUSED.txt").write_text(ref.text(), encoding="utf-8")
    (out / "REFUSED.json").write_text(json.dumps({"refused": True, "notice": fmt.NOTICE_LONG,
                                                  "reasons": [{"code": c, "ko": k, "en": e} for c, k, e in ref.reasons]},
                                                 ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
