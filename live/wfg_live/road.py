"""Arrival raster from the known fire area and the frozen margin, and the road layer runs (PROTOCOL §5)."""
from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

from . import common as C

# KFS_01 375 m lattice of product/wfg-roadlayer/examples/build_example_raster.py (covers both prepared regions)
X0, Y0, RES, W, H = 1093875.0, 1815750.0, 375.0, 214, 67
REGIONS = {  # road-cell extents from product/wfg-roadlayer/INTERFACE.md (EPSG:5179)
    "uiseong_andong_2025": {"x": (1093875, 1121250), "y": (1815750, 1840125), "ko": "의성·안동", "en": "Uiseong-Andong"},
    "yeongdeok_2025": {"x": (1147500, 1174125), "y": (1815750, 1840875), "ko": "영덕", "en": "Yeongdeok"},
}


def cell_centres():
    cols = np.arange(W)
    rows = np.arange(H)
    cx = (X0 + (cols + 0.5) * RES)[None, :].repeat(H, 0)
    cy = (Y0 + (rows + 0.5) * RES)[:, None].repeat(W, 1)
    return cx, cy   # south-up rows


def distance_grid(discs):
    cx, cy = cell_centres()
    d = np.full(cx.shape, np.inf)
    for i in range(0, len(discs), 2000):
        part = discs[i:i + 2000]
        X = np.array([p["x"] for p in part]); Y = np.array([p["y"] for p in part]); R = np.array([p["r_m"] for p in part])
        dd = np.hypot(cx[..., None] - X, cy[..., None] - Y) - R
        d = np.minimum(d, np.maximum(dd, 0).min(-1))
    return d


def arrival_minutes(discs, r5_m, r8_m):
    import measured_arms as MA  # research/kcf-replay, unchanged
    d = distance_grid(discs)
    out = np.full(d.shape, np.inf)
    for (i, j), v in np.ndenumerate(d):
        if np.isfinite(v):
            s = MA.closure_s(r5_m, r8_m, float(v))
            if s <= 8 * 3600:
                out[i, j] = int(math.ceil(s)) / 60.0
    return out   # south-up


def regions_reached(minutes) -> list:
    cx, cy = cell_centres()
    hit = []
    for rid, e in REGIONS.items():
        m = (cx >= e["x"][0]) & (cx <= e["x"][1]) & (cy >= e["y"][0]) & (cy <= e["y"][1])
        if np.isfinite(minutes[m]).any():
            hit.append(rid)
    return hit


def write_raster(path: Path, minutes, issue: datetime, source: str):
    from wfg_roadlayer import geotiff
    md = {"WFG_ISSUE_TIME": C.iso(issue), "WFG_HORIZON_MIN": "480", "WFG_UNITS": "minutes", "WFG_SOURCE": source}
    path.parent.mkdir(parents=True, exist_ok=True)
    geotiff.write(path, minutes[::-1], (RES, 0.0, X0, 0.0, -RES, Y0 + RES * H), 5179, nodata=float("nan"), metadata=md)


def run_roadlayer(region: str, raster: Path, issue: datetime, out: Path, replay: bool, cards: bool = True) -> dict:
    """roadlayer.py run (+ cards). Returns status, refusal, parsed rows, card files and page map."""
    cfg = C.settings()
    base = [sys.executable, str(C.ROADLAYER / "roadlayer.py")]
    common_args = ["--region", region, "--issue-time", issue.astimezone(C.KST).strftime("%Y-%m-%dT%H:%M+09:00"),
                   "--raster", str(raster), "--settings", str(C.REPO / cfg["roadlayer"]["settings"])]
    if replay:
        common_args += ["--as-of", issue.astimezone(C.KST).strftime("%Y-%m-%dT%H:%M+09:00")]
    res = {"region": region}
    p = subprocess.run(base + ["run"] + common_args + ["--out", str(out / "run"), "--overwrite"], capture_output=True, text=True)
    res["run_exit"] = p.returncode
    if p.returncode != 0:   # the log holds run times, so it is kept only on failure (records must replay exactly)
        res["run_log_tail"] = (p.stdout + p.stderr)[-1500:]
    if p.returncode == 2:
        res["refused"] = _refusal(out / "run")
        return res
    if p.returncode != 0:
        res["error"] = "road layer error (exit %d)" % p.returncode
        return res
    res["rows"] = parse_rows(out / "run", region)
    if cards:
        q = subprocess.run(base + ["cards"] + common_args + ["--out", str(out / "cards"), "--overwrite"], capture_output=True, text=True)
        res["cards_exit"] = q.returncode
        if q.returncode != 0:
            res["cards_log_tail"] = (q.stdout + q.stderr)[-1500:]
        if q.returncode == 0:
            res["cards"] = parse_cards(out / "cards", region)
    return res


def _refusal(d: Path):
    p = d / "REFUSED.json"
    if p.exists():
        j = json.loads(p.read_text(encoding="utf-8"))
        rs = j.get("reasons") or []
        return {"codes": [r.get("code") for r in rs], "reasons": [{k: r.get(k) for k in ("code", "ko", "en")} for r in rs]}
    return {"codes": ["UNKNOWN"], "reasons": []}


def _csv(path):
    with open(path, encoding="utf-8-sig") as fh:
        return list(csv.reader(fh))


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_rows(d: Path, region: str) -> list:
    en = _csv(d / "en" / ("villages_road_cut_%s.csv" % region))
    ko = _csv(next((d / "ko").glob("*.csv")))
    he, hk = en[0], ko[0]
    rows = []
    for re_, rk in zip(en[1:], ko[1:]):
        e = dict(zip(he, re_))
        k = dict(zip(hk, rk))
        rows.append({
            "place_id": e["place id"], "name_en": e["village or facility"], "name_ko": k["마을·시설"],
            "county_ko": k["시군"], "town_ko": k["읍면동"], "county_en": e["county"], "town_en": e["town (eup/myeon/dong)"],
            "type_en": e["type"], "type_ko": k["구분"],
            "stage_en": e["stage now"], "stage_ko": k["현재 단계"],
            "windows_en": e["safe departure windows (KST)"], "windows_ko": k["안전 출발 가능 시간대 (KST)"],
            "leave_by_en": e["leave by (KST)"], "leave_by_ko": k["출발 마감 (KST)"],
            "road_cut_en": e["last road out cut (KST)"], "road_cut_ko": k["마지막 도로 차단 (KST)"],
            "road_status_en": e["road status"], "road_status_ko": k["도로 차단 상태"],
            "gap_min": e["minutes from road cut to fire arrival"],
            "fire_arrival_en": e["fire arrival (KST)"], "fire_arrival_ko": k["화재 도달 (KST)"],
            "flag_en": e["flag: road cut before 'execute now'"], "flag_ko": k["경고: '즉시 실행' 전에 도로 차단"],
            "shelter_en": e["shelter for the last departure"], "shelter_ko": k["마지막 출발 시 대피소"],
            "refusal_en": e["refusal reason"], "refusal_ko": k["계산 거부 사유"],
            "leave_by_s": _int(e["leave by (s after issue)"]), "road_cut_s": _int(e["road cut (s after issue)"]),
            "fire_arrival_s": _int(e["fire arrival (s after issue)"]),
        })
    return rows


def affected(rows, horizon_s=8 * 3600) -> list:
    out = []
    for r in rows:
        cut = r["road_cut_s"] is not None and r["road_cut_s"] <= horizon_s
        arr = r["fire_arrival_s"] is not None and r["fire_arrival_s"] <= horizon_s
        if (cut or arr) and not r["refusal_en"]:
            out.append(r)
    return out


def parse_cards(d: Path, region: str) -> dict:
    audit = {}
    with open(d / ("audit_%s.csv" % region), encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            audit[r["place_id"]] = {k: r[k] for k in ("exits", "single_exit", "departure_group", "departure_position",
                                                       "departure_group_size", "departure_start_by_kst", "departure_after",
                                                       "leave_by_with_clearance_kst", "clearance_min", "trigger_kst", "refusal")}
    pages = card_pages(d / ("cards_ko_%s.pdf" % region), d / ("audit_%s.csv" % region))
    return {"audit": audit, "pages": pages, "pdf_ko": "cards_ko_%s.pdf" % region, "pdf_en": "cards_en_%s.pdf" % region}


def card_pages(pdf: Path, audit_csv: Path) -> dict:
    """place_id -> 1-based page in the card PDF, matched on (읍·면, name, leave-by text); ties in audit order."""
    from pypdf import PdfReader
    pages = []
    for i, p in enumerate(PdfReader(str(pdf)).pages, 1):
        lines = (p.extract_text() or "").split("\n")
        name = lines[1].strip() if len(lines) > 1 else ""
        head = lines[2] if len(lines) > 2 else ""
        pages.append({"n": i, "name": name, "head": head, "text": " ".join(lines)})
    used = set()
    out = {}
    with open(audit_csv, encoding="utf-8-sig") as fh:
        rows = [r for r in csv.DictReader(fh) if not r["refusal"]]
    for r in rows:
        nm = r["name"] or ""
        cands = [p for p in pages if p["n"] not in used and r["eupmyeon"] in p["head"] and r["sigungu"] in p["head"]
                 and (p["name"] == nm or (not nm and r["place_id"].split("/")[-1] in p["text"]))]
        if len(cands) > 1 and r["leave_by_kst"]:
            narrowed = [p for p in cands if r["leave_by_kst"][-5:] in p["text"]]
            cands = narrowed or cands
        if cands:
            out[r["place_id"]] = cands[0]["n"]
            used.add(cands[0]["n"])
    return out
