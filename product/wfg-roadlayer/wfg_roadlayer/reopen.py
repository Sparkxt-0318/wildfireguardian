"""Optional reopening of burned-over road cells (research/kcf-reopen). Off by default.

A road cell closed from its closure second b (the fire input) is closed on [b, r) with r = max(b, A + burn-out), where A
is the cell's fire arrival: the input raster's own value, or a second "central arrival" raster when the input raster is
already moved earlier by a margin. Cells burning at the issue time (value <= 0) take A = 0: their age is unknown, so
they reopen at issue + burn-out, never before the true burn-out when the fire arrived before the issue time.

Modes (settings [reopen] mode, or --reopen):
  0 "off"        closures permanent, as before (the default; residents' sheets).
  1 "confirmed"  a burned-over cell reopens only when a report or a vehicle-unit REOPENED event in the cell confirms it:
                 the event's time u must satisfy A + burn-out <= u <= the issue time. Everything else stays closed.
  2 "responders" every closed cell with an arrival reopens at A + burn-out (responder use; not for residents).

Confirmations file (JSON): {"events": [{"event": "REOPENED" | "PASSABLE", "lat": .., "lon": .., "utc": "...Z",
"source": ".."}]}, the fields of api/live.py's REOPENED event; a point is placed in its 375 m road cell (EPSG:4326 ->
the road grid's CRS with pyproj).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import fireinput
from .errors import Refusal, reason
from .regiondata import parse_utc, sha256_file

MODES = {"off": 0, "confirmed": 1, "responders": 2}
NAMES = {v: k for k, v in MODES.items()}
TAU_SOURCE = ("research/kcf-reopen out/tau.json: 80th percentile of the time from first fire evidence to the last "
              "road-blocked report per road cell, Camp Fire 2018 (75 cells); low 105, high 465 min")


def _events(path, road, issue):
    p = Path(path)
    if not p.is_file():
        raise Refusal(reason("REOPEN_CONFIRMED_MISSING", "재개통 확인 파일이 없습니다: %s" % p, "reopening confirmations file not found: %s" % p))
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        evs = doc["events"] if isinstance(doc, dict) else doc
        from pyproj import Transformer
        tr = Transformer.from_crs(4326, int(str(road.crs).split(":")[-1]), always_xy=True)
        out = []
        for e in evs:
            if e.get("event", "REOPENED") not in ("REOPENED", "PASSABLE"):
                continue
            x, y = tr.transform(float(e["lon"]), float(e["lat"]))
            from fractions import Fraction as F
            c = road.cell_of(F(x), F(y))
            u = int((parse_utc(e["utc"]) - issue).total_seconds())
            out.append({"cell": c, "u_s": u, "source": e.get("source", e.get("unit_id", ""))})
        return out, sha256_file(p)
    except Refusal:
        raise
    except Exception as ex:  # malformed file: refuse rather than guess
        raise Refusal(reason("REOPEN_CONFIRMED_INVALID", "재개통 확인 파일을 읽을 수 없습니다: %s" % ex,
                             "the reopening confirmations file cannot be read: %s" % ex))


def build(region, fire, close_s: dict, cfg: dict, *, arrival_raster=None, confirmed=None, horizon_min=None, not_reached_value=None):
    """-> (open_s {cell: r seconds after issue}, info dict for run.json) or ({}, None) when off."""
    mode = int(cfg["reopen"]["mode"])
    if mode == 0:
        return {}, None
    tau_s = int(round(60 * float(cfg["reopen"]["burnout_min"])))
    H = fire.horizon_s
    if arrival_raster is not None:
        arr = fireinput.load_geotiff(arrival_raster, region.road, issue_utc=fire.issue_utc, horizon_min=horizon_min,
                                     not_reached_value=not_reached_value, keep_past=True)
        A = arr.arrival_s
        a_src = {"kind": "central arrival raster", "file": Path(arrival_raster).name, "sha256": arr.sha256}
    else:
        A = fire.arrival_s
        a_src = {"kind": "the input raster itself (if it is already moved earlier by a margin, reopening is earlier too)"}
    burned = {c: A[c] + tau_s for c in close_s if c in A}          # burn-out second, may lie before the issue time
    cand = {c: max(close_s[c], r) for c, r in burned.items()}
    info = {"mode": NAMES[mode], "burnout_min": cfg["reopen"]["burnout_min"], "burnout_source": TAU_SOURCE, "arrival": a_src,
            "rule": "cell closed on [b, r), r = max(b, A + burn-out); cells without an arrival stay closed to the horizon"}
    if mode == 1:
        if confirmed is None:
            raise Refusal(reason("REOPEN_CONFIRMED_MISSING", "--reopen confirmed 에는 --reopen-confirmed 파일이 필요합니다.",
                                 "--reopen confirmed needs a --reopen-confirmed file."))
        evs, sha = _events(confirmed, region.road, fire.issue_utc)
        ok = {}
        for e in evs:
            c = e["cell"]
            if c in cand and burned[c] <= e["u_s"] <= 0:
                ok[c] = cand[c]
        open_s = ok
        info["confirmations"] = {"file": Path(confirmed).name, "sha256": sha, "events": len(evs), "cells_confirmed": len(ok)}
    else:
        open_s = cand
    info["cells_closed"] = len(close_s)
    info["cells_reopening_within_horizon"] = sum(1 for c, r in open_s.items() if close_s[c] < r <= H)
    info["cells_burned_over_at_issue"] = sum(1 for c, r in open_s.items() if r <= max(close_s[c], 0))
    return open_s, info
