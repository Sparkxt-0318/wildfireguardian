"""Known fire area (PROTOCOL §4): detections, AHI hotspots, persistent sources, membership, evidence age."""
from __future__ import annotations

import csv
import io
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from . import common as C

_TR = None


def to5179(lon, lat):
    global _TR
    if _TR is None:
        from pyproj import Transformer
        _TR = Transformer.from_crs(4326, 5179, always_xy=True)
    return _TR.transform(lon, lat)


def to4326(x, y):
    from pyproj import Transformer
    return Transformer.from_crs(5179, 4326, always_xy=True).transform(x, y)


def firms_rows(inputs: Path, manifest) -> tuple[list, list]:
    """-> (kept detections, all rows for the persistent-source rule). Each: dict(src, t, lat, lon, r_m, date)."""
    cfg = C.settings()["area"]
    kept, allrows = [], []
    for name, m in sorted(manifest["sources"].items()):
        if not name.startswith("firms:") or not m["ok"]:
            continue
        src = name.split(":", 1)[1]
        modis = src.startswith("MODIS")
        text = (inputs / m["file"]).read_text(encoding="utf-8", errors="replace")
        for r in csv.DictReader(io.StringIO(text)):
            try:
                lat, lon = float(r["latitude"]), float(r["longitude"])
                t = datetime.strptime(r["acq_date"] + r["acq_time"].zfill(4), "%Y-%m-%d%H%M").replace(tzinfo=C.UTC)
            except (KeyError, ValueError):
                continue
            conf = str(r.get("confidence", "")).strip().lower()
            row = {"src": src, "t": t, "lat": lat, "lon": lon, "date": r["acq_date"]}
            allrows.append(row)
            if r.get("type") not in (None, "", "0"):
                continue
            if modis:
                try:
                    ok = float(conf) >= cfg["modis_conf_min"]
                except ValueError:
                    ok = False
                r_m = cfg["modis_radius_m"]
            else:
                ok = conf in cfg["viirs_conf_keep"]
                r_m = cfg["viirs_radius_m"]
            if ok:
                kept.append(dict(row, r_m=r_m))
    return kept, allrows


def ahi_hotspots(inputs: Path, manifest) -> list:
    """research/kcf-margin AHI rule: B07 >= 320 K and B07-B14 >= 25 K in >= 2 scans of one UTC clock hour; known at the
    end of the second such scan."""
    m = manifest["sources"].get("ahi")
    if not m or not m["ok"]:
        return []
    a = C.settings()["ahi"]
    r_m = C.settings()["area"]["ahi_radius_m"]
    scans = json.loads((inputs / m["file"]).read_text())["scans"]
    scans.sort(key=lambda s: s["start_utc"])
    count, out = {}, {}
    for s in scans:
        hour = s["start_utc"][:13]
        for la, lo, b7, d in zip(s["lat"], s["lon"], s["b07"], s["b07_b14"]):
            if b7 is None or d is None or not (b7 >= a["b07_min_k"] and d >= a["diff_min_k"]):
                continue
            k = (hour, la, lo)
            count[k] = count.get(k, 0) + 1
            if count[k] == a["min_scans_in_hour"] and (la, lo, hour) not in out:
                out[(la, lo, hour)] = {"src": "AHI", "t": C.parse_iso(s["end_utc"]), "lat": la, "lon": lo, "r_m": r_m}
    return sorted(out.values(), key=lambda d: (d["t"], d["lat"], d["lon"]))


def persistent_cells(allrows, report: datetime) -> set:
    cfg = C.settings()["area"]
    step = cfg["persistent_cell_deg"]
    days = {}
    rday = report.strftime("%Y-%m-%d")
    for r in allrows:
        if r["date"] >= rday:
            continue
        k = (math.floor(r["lat"] / step), math.floor(r["lon"] / step))
        days.setdefault(k, set()).add(r["date"])
    return {k for k, v in days.items() if len(v) >= cfg["persistent_days"]}


def _in_persistent(d, cells, step):
    i, j = math.floor(d["lat"] / step), math.floor(d["lon"] / step)
    if d["src"] != "AHI":
        return (i, j) in cells
    # an AHI hotspot is ignored when a persistent cell centre lies within its 2 km disc
    rad = d["r_m"] / 111000.0
    n = int(math.ceil(rad / step)) + 1
    for di in range(-n, n + 1):
        for dj in range(-n, n + 1):
            if (i + di, j + dj) in cells:
                clat = (i + di + 0.5) * step
                clon = (j + dj + 0.5) * step
                dy = (clat - d["lat"]) * 111000.0
                dx = (clon - d["lon"]) * 111000.0 * math.cos(math.radians(d["lat"]))
                if math.hypot(dx, dy) <= d["r_m"]:
                    return True
    return False


def known_area(fire_pt, report: datetime, T: datetime, firms_kept, firms_all, ahi) -> dict:
    """fire_pt = (lat, lon). Returns discs (EPSG:5179, measured_arms format), evidence age, centroid, counts."""
    cfg = C.settings()["area"]
    step = cfg["persistent_cell_deg"]
    cells = persistent_cells(firms_all, report)
    px, py = to5179(fire_pt[1], fire_pt[0])
    t_lo = report - timedelta(hours=cfg["lookback_before_report_h"])
    seed = {"src": "KFS report", "t": report, "x": px, "y": py, "r_m": cfg["seed_radius_m"], "lat": fire_pt[0], "lon": fire_pt[1]}
    cands, n_persist, n_far = [], 0, 0
    for d in list(firms_kept) + list(ahi):
        if not (t_lo <= d["t"] < T):
            continue
        if _in_persistent(d, cells, step):
            n_persist += 1
            continue
        x, y = to5179(d["lon"], d["lat"])
        if math.hypot(x - px, y - py) > cfg["cap_km"] * 1000.0:
            n_far += 1
            continue
        cands.append(dict(d, x=x, y=y))
    cands.sort(key=lambda d: (d["t"], d["src"], d["lat"], d["lon"]))
    members = [seed]
    if cands:
        X = np.array([c["x"] for c in cands]); Y = np.array([c["y"] for c in cands]); R = np.array([c["r_m"] for c in cands])
        inside = np.zeros(len(cands), bool)
        frontier = [seed]
        link = cfg["link_km"] * 1000.0
        while frontier:
            new = np.zeros(len(cands), bool)
            for m in frontier:
                gap = np.hypot(X - m["x"], Y - m["y"]) - R - m["r_m"]
                new |= (gap <= link) & ~inside
            idx = np.flatnonzero(new)
            inside[idx] = True
            frontier = [cands[i] for i in idx]
            members.extend(frontier)
    members.sort(key=lambda d: (d["t"], d["src"], d.get("lat", 0), d.get("lon", 0)))
    latest = max(d["t"] for d in members)
    cx = float(np.mean([d["x"] for d in members])); cy = float(np.mean([d["y"] for d in members]))
    clon, clat = to4326(cx, cy)
    discs = [{"src": d["src"], "t_utc": C.iso(d["t"]), "x": round(float(d["x"]), 1), "y": round(float(d["y"]), 1),
              "r_m": float(d["r_m"])} for d in members]
    return {"discs": discs, "n_members": len(members), "n_by_src": _count(members), "n_candidates": len(cands),
            "n_ignored_persistent": n_persist, "n_ignored_far": n_far, "latest_member_utc": C.iso(latest),
            "evidence_age_min": round((T - latest).total_seconds() / 60.0, 1), "centroid": {"lat": round(clat, 5), "lon": round(clon, 5),
                                                                                          "x": round(cx, 1), "y": round(cy, 1)}}


def _count(ms):
    out = {}
    for d in ms:
        out[d["src"]] = out.get(d["src"], 0) + 1
    return out
