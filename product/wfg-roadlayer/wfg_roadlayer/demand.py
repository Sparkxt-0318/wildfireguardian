"""People and buildings of a place for the cards and the fragility table (research/kcf-buildings).

Every figure carries a status word:
  MEASURED  a register count for exactly this place;
  MEASURED (읍·면·동) / ESTIMATED  the register count is for the 읍·면·동 and the village figure is an equal split over its
            법정리 (ESTIMATED);
  ESTIMATED the figure is built from other figures (vehicles = households x the province vehicles-per-household);
  MAPPED    OpenStreetMap buildings of 2025-03-21: a lower bound of what stands there, not a count.
Buildings at risk = mapped buildings that stand in a 375 m cell the input fire field reaches within the horizon. No fire is
spread from building to building.
"""
from __future__ import annotations

import csv
import gzip
import math
from functools import lru_cache

from .cards import PRODUCT


def _f(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def demo(h: dict) -> dict:
    """People fields of a household-table row (data/households/<region>.csv)."""
    care = h["kind"] != "village"
    return {
        "households": 0.0 if care else _f(h["households"], 0.0),
        "residents": _f(h.get("residents")),
        "residents65": _f(h.get("residents65")),
        "households_status": h.get("households_status") or h.get("status") or "ASSUMED",
        "residents_status": h.get("residents_status") or "ASSUMED",
        "residents65_status": h.get("residents65_status") or "not available",
        "vehicles": _f(h.get("vehicles")),
        "vehicles_status": h.get("vehicles_status") or "ASSUMED",
        "bldg": {k: int(_f(h.get("bldg_" + k), 0) or 0) for k in ("house", "apartment", "care", "school", "other", "unknown")},
        "schools": h.get("schools") or "", "care_facilities": h.get("care_facilities") or "",
        "bldg_status": h.get("bldg_status") or "",
    }


@lru_cache(maxsize=8)
def _buildings(region_id: str):
    fn = PRODUCT / "data" / "buildings" / ("%s.csv.gz" % region_id)
    out = {}
    if not fn.exists():
        return out
    with gzip.open(fn, "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["place_id"], []).append((float(r["x"]), float(r["y"]), r["use"]))
    return out


def at_risk(region_id: str, road, close_s: dict, H: int, place_id: str, node: int, households: float, mapped_min: int = 5) -> dict:
    """Mapped buildings in cells reached within H, and households at risk (ESTIMATED), for one place."""
    x0, y0, res, W, Hr = float(road.x0), float(road.y0), float(road.res), road.W, road.H
    blds = _buildings(region_id).get(place_id, [])
    n_at = 0
    by_use = {}
    for x, y, use in blds:
        c, r = math.floor((x - x0) / res), math.floor((y - y0) / res)
        if 0 <= c < W and 0 <= r < Hr:
            v = close_s.get(r * W + c)
            if v is not None and v <= H:
                n_at += 1
                by_use[use] = by_use.get(use, 0) + 1
    own = close_s.get(road.node_cell[node])
    own_reached = own is not None and own <= H
    if len(blds) >= mapped_min:
        hh_at = households * n_at / len(blds)
        basis = "share of %d mapped buildings in reached cells" % len(blds)
    else:
        hh_at = households if own_reached else 0.0
        basis = "fewer than %d mapped buildings: all households if the village's own cell is reached, else none" % mapped_min
    return {"mapped": len(blds), "at_risk": n_at, "at_risk_by_use": by_use, "households_at_risk": hh_at, "households_at_risk_basis": basis,
            "own_cell_reached": own_reached}
