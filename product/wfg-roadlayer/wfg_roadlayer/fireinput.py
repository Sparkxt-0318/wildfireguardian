"""Fire input → closure second of every 375 m routing cell that carries a road.

Two input kinds (INTERFACE.md):
  * a fire-arrival GeoTIFF: minutes from the issue time to fire arrival, per pixel;
  * the repository's own hazard packet (wfg.routing.edgegrid/1 + constructed_arrays.npz).

Reading rule (permanent closure, the no-re-entry hull of research/kcf-theorem Corollary 3, which is safe):
  * a routing cell closes at the EARLIEST arrival over all pixels that overlap it with positive area, and stays
    closed to the end of the horizon (burn-out never reopens a road);
  * arrival seconds = floor(60 * minutes + 1e-6) (rounded down, so never later than the input);
  * value <= 0 or -inf: fire already there at the issue time (closed from 0);
  * value > horizon, +inf, or the declared not-reached value: not reached within the horizon;
  * nodata / NaN / outside the raster: NOT COVERED. A road cell that is not covered makes the run refuse, unless the
    operator passes --assume-uncovered-not-reached (then printed on every page).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import geotiff
from .errors import Refusal, reason
from .regiondata import RoadModel, parse_utc, sha256_file

NOT_REACHED = None


@dataclass
class FireInput:
    kind: str
    path: str
    sha256: str
    issue_utc: datetime
    horizon_s: int
    arrival_s: dict                 # road cell -> closure second (0..H); cells absent: not reached within H
    uncovered: list                 # road cells with no data
    info: dict = field(default_factory=dict)


def _check_issue(cli_issue: datetime | None, declared: datetime | None, where: str):
    if cli_issue is None:
        hint_ko = " (입력 파일에는 %s 로 적혀 있음)" % declared.isoformat() if declared else ""
        hint_en = " (the input file says %s)" % declared.isoformat() if declared else ""
        raise Refusal(reason("ISSUE_TIME_MISSING", "발표 시각(--issue-time)이 없습니다%s." % hint_ko,
                             "no issue time given (--issue-time)%s." % hint_en))
    if declared is not None and declared != cli_issue:
        raise Refusal(reason("ISSUE_TIME_CONFLICT",
                             "입력한 발표 시각 %s 과 %s 에 적힌 발표 시각 %s 이 다릅니다." % (cli_issue.isoformat(), where, declared.isoformat()),
                             "the issue time given (%s) differs from the one in %s (%s)." % (cli_issue.isoformat(), where, declared.isoformat())))
    return cli_issue


def _classify(v: np.ndarray, nodata, horizon_min: float, not_reached_value, H: int):
    """-> (covered bool array, seconds int64 array with H+1 meaning not reached)."""
    cov = ~np.isnan(v)
    if nodata is not None and not math.isnan(nodata):
        cov &= v != nodata
    sec = np.full(v.shape, H + 1, dtype=np.int64)
    with np.errstate(invalid="ignore", over="ignore"):
        burned = cov & (v <= 0)
        fin = cov & np.isfinite(v) & (v > 0) & (v <= horizon_min)
        if not_reached_value is not None:
            fin &= v != not_reached_value
            burned &= v != not_reached_value
        sec[burned] = 0
        s = np.floor(60.0 * v[fin] + 1e-6).astype(np.int64)
        sec[fin] = np.where(s > H, H + 1, np.maximum(s, 0))
    return cov, sec


def _cell_reduce(covs, secs, H):
    """A cell: closure = min over covered pixels; NOT COVERED if any pixel is uncovered, unless already burned (0)."""
    if secs.size == 0:
        return None
    m = int(secs[covs].min()) if covs.any() else H + 1
    if not covs.all() and m != 0:
        return None
    return m


def load_geotiff(path, road: RoadModel, *, issue_utc: datetime | None, horizon_min: float | None,
                 not_reached_value: float | None = None) -> FireInput:
    p = Path(path)
    if not p.is_file():
        raise Refusal(reason("FIRE_INPUT_MISSING", "화재 도달 래스터가 없습니다: %s" % p, "fire-arrival raster not found: %s" % p))
    try:
        r = geotiff.read(p)
    except geotiff.GeoTiffError as exc:
        raise Refusal(reason("FIRE_INPUT_UNREADABLE", "화재 도달 래스터를 읽을 수 없습니다: %s" % exc,
                             "cannot read the fire-arrival raster: %s" % exc)) from exc
    md = r.metadata
    declared = parse_utc(md["WFG_ISSUE_TIME"]) if md.get("WFG_ISSUE_TIME") else None
    issue = _check_issue(issue_utc, declared, "래스터 메타데이터 WFG_ISSUE_TIME")
    md_h = float(md["WFG_HORIZON_MIN"]) if md.get("WFG_HORIZON_MIN") else None
    if horizon_min is None and md_h is None:
        raise Refusal(reason("HORIZON_MISSING", "예측 범위(분)가 없습니다: --horizon-min 을 주거나 래스터 메타데이터 WFG_HORIZON_MIN 을 넣으십시오.",
                             "the forecast horizon (minutes) is missing: pass --horizon-min or set raster metadata WFG_HORIZON_MIN."))
    if horizon_min is not None and md_h is not None and abs(horizon_min - md_h) > 1e-9:
        raise Refusal(reason("HORIZON_CONFLICT", "입력한 예측 범위 %s분과 래스터의 %s분이 다릅니다." % (horizon_min, md_h),
                             "the horizon given (%s min) differs from the raster's (%s min)." % (horizon_min, md_h)))
    hmin = horizon_min if horizon_min is not None else md_h
    if not (hmin > 0):
        raise Refusal(reason("HORIZON_INVALID", "예측 범위가 0 이하입니다.", "the horizon must be positive."))
    if md.get("WFG_UNITS") and md["WFG_UNITS"].lower() not in ("minutes", "min", "분"):
        raise Refusal(reason("UNITS_INVALID", "래스터 단위가 분이 아닙니다: %s" % md["WFG_UNITS"],
                             "raster units are not minutes: %s" % md["WFG_UNITS"]))
    if r.epsg is None:
        raise Refusal(reason("CRS_MISSING", "래스터 좌표계(EPSG 코드)가 없습니다.", "the raster has no coordinate system (EPSG code)."))
    if md.get("WFG_NOT_REACHED") and not_reached_value is None:
        not_reached_value = float(md["WFG_NOT_REACHED"])
    H = int(round(hmin * 60))
    cov, sec = _classify(r.data, r.nodata, hmin, not_reached_value, H)
    a, b, c, d, e, f = r.affine
    rows, cols = r.shape
    arrival, uncovered = {}, []
    if r.epsg == 5179 and b == 0 and d == 0 and a > 0 and e != 0:
        eps = 1e-9
        for cell in road.road_cells:
            x0c, x1c, y0c, y1c = road.cell_rect(cell)
            c_lo = math.floor((x0c - c) / a + eps)
            c_hi = math.ceil((x1c - c) / a - eps) - 1
            if e < 0:
                r_lo = math.floor((f - y1c) / -e + eps)
                r_hi = math.ceil((f - y0c) / -e - eps) - 1
            else:
                r_lo = math.floor((y0c - f) / e + eps)
                r_hi = math.ceil((y1c - f) / e - eps) - 1
            inside = c_lo >= 0 and r_lo >= 0 and c_hi < cols and r_hi < rows
            cs, ss = cov[max(r_lo, 0):min(r_hi, rows - 1) + 1, max(c_lo, 0):min(c_hi, cols - 1) + 1], \
                sec[max(r_lo, 0):min(r_hi, rows - 1) + 1, max(c_lo, 0):min(c_hi, cols - 1) + 1]
            m = _cell_reduce(cs, ss, H)
            if m is None or (not inside and m != 0):
                uncovered.append(cell)
            elif m <= H:
                arrival[cell] = m
        rule = "exact pixel overlap (same CRS EPSG:5179, axis-aligned)"
    else:
        try:
            from pyproj import Transformer
        except ImportError as exc:
            raise Refusal(reason("PYPROJ_MISSING", "래스터 좌표계 EPSG:%d 를 변환하려면 pyproj 가 필요합니다 (pip install pyproj)." % r.epsg,
                                 "pyproj is needed to read a raster in EPSG:%d (pip install pyproj)." % r.epsg)) from exc
        tr = Transformer.from_crs("EPSG:5179", "EPSG:%d" % r.epsg, always_xy=True)
        det = a * e - b * d
        if det == 0:
            raise Refusal(reason("FIRE_INPUT_UNREADABLE", "래스터 변환 행렬이 잘못되었습니다.", "degenerate raster transform."))
        pix = math.sqrt(abs(det))
        pix_m = pix * (111_000.0 if r.epsg in (4326, 4737, 4166) else 1.0)
        n = int(min(64, max(5, math.ceil(375.0 / max(pix_m / 2.0, 1e-9)) + 1)))
        u = np.linspace(0.0, 1.0, n)
        for cell in road.road_cells:
            x0c, x1c, y0c, y1c = road.cell_rect(cell)
            X, Y = np.meshgrid(x0c + u * (x1c - x0c), y0c + u * (y1c - y0c))
            px, py = tr.transform(X.ravel(), Y.ravel())
            px, py = np.asarray(px) - c, np.asarray(py) - f
            col = np.floor((e * px - b * py) / det).astype(np.int64)
            row = np.floor((-d * px + a * py) / det).astype(np.int64)
            ok = (col >= 0) & (col < cols) & (row >= 0) & (row < rows)
            cs = np.zeros(col.shape, bool)
            ss = np.full(col.shape, H + 1, np.int64)
            cs[ok] = cov[row[ok], col[ok]]
            ss[ok] = sec[row[ok], col[ok]]
            m = _cell_reduce(cs, ss, H)
            if m is None:
                uncovered.append(cell)
            elif m <= H:
                arrival[cell] = m
        rule = "point sampling %dx%d per routing cell incl. edges, EPSG:5179 -> EPSG:%d (pyproj)" % (n, n, r.epsg)
    nodata_txt = None if r.nodata is None else ("NaN" if math.isnan(r.nodata) else r.nodata)
    info = {"crs": "EPSG:%d" % r.epsg, "affine": list(r.affine), "shape": list(r.shape), "nodata": nodata_txt,
            "metadata": md, "resampling": rule, "not_reached_value": not_reached_value, "tiff": r.info,
            "horizon_min": hmin, "horizon_source": "cli" if horizon_min is not None else "raster metadata"}
    return FireInput("geotiff", str(p), sha256_file(p), issue, H, arrival, sorted(uncovered), info)


def load_packet(path, road: RoadModel, *, issue_utc: datetime | None) -> FireInput:
    d = Path(path)
    need = ["REPORT.json", "HAZARD.json", "constructed_arrays.npz"]
    missing = [n for n in need if not (d / n).is_file()]
    if missing:
        raise Refusal(reason("FIRE_INPUT_MISSING", "패킷 파일이 없습니다: %s" % ", ".join(str(d / n) for n in missing),
                             "packet files missing: %s" % ", ".join(str(d / n) for n in missing)))
    rep = json.loads((d / "REPORT.json").read_text())
    md = rep["native_metadata"]
    hz = json.loads((d / "HAZARD.json").read_text())
    if hz.get("schema") != "wfg.routing.edgegrid/1":
        raise Refusal(reason("FIRE_INPUT_UNREADABLE", "패킷 스키마가 다릅니다: %r" % hz.get("schema"),
                             "unsupported packet schema %r" % hz.get("schema")))
    declared = parse_utc(md["time_origin"])
    issue = _check_issue(issue_utc, declared, "패킷 time_origin")
    H = int(math.floor(float(md["construction"]["assumptions"]["horizon_s"])))
    top = float(road.y0) + float(road.res) * road.H
    want = [float(road.res), 0.0, float(road.x0), 0.0, -float(road.res), top]
    if md.get("crs") != "EPSG:5179" or [float(v) for v in md.get("affine_transform", [])] != want or \
            list(md.get("shape", [])) != [road.H, road.W]:
        raise Refusal(reason("GRID_MISMATCH", "패킷 격자가 이 지역 도로망 격자와 다릅니다 (다른 지역의 패킷?).",
                             "the packet grid differs from this region's road grid (a packet of another region?)."))
    with np.load(d / "constructed_arrays.npz", allow_pickle=False) as z:
        ev = np.array(z["ignition_time_s"], dtype=float)
        cur = np.array(z["current_active"], dtype=bool)
        burned = np.array(z["mask__known_burned"], dtype=bool) if "mask__known_burned" in z.files else np.zeros_like(cur)
        valid = np.array(z["mask__probability_valid_native"], dtype=bool) if "mask__probability_valid_native" in z.files \
            else np.ones_like(cur)
    first = np.where(np.isfinite(ev), ev, np.inf).min(axis=0)
    covered = valid | cur | burned | np.isfinite(first)
    arrival, uncovered = {}, []
    for cell in road.road_cells:
        rr, cc = divmod(cell, road.W)
        nr = road.H - 1 - rr  # router rows are south-up, npz rows north-up
        if cur[nr, cc] or burned[nr, cc]:
            arrival[cell] = 0
        elif np.isfinite(first[nr, cc]):
            s = int(math.floor(first[nr, cc] + 1e-9))
            if s <= H:
                arrival[cell] = max(s, 0)
        elif not covered[nr, cc]:
            uncovered.append(cell)
    info = {"crs": "EPSG:5179", "members": int(ev.shape[0]), "rule": "earliest ignition over members; present fire and "
            "known burned = 0; cells without a native probability, present fire, known burn or ignition = NOT COVERED",
            "graph_revision": md.get("graph_revision"), "construction_id": md.get("construction_id")}
    sha = sha256_file(d / "constructed_arrays.npz")
    return FireInput("packet", str(d), sha, issue, H, arrival, sorted(uncovered), info)
