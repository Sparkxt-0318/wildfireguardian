"""Place labels for road locations, from data already in the repository only (never invented).

Availability (checked, see README.md "Labels"): the routing graph's edges carry an OSM way id (``source_way``) but no
``name``/``ref`` tags, and ``planner/data/osm/<region>.overpass.json`` holds places and facilities, not roads. A road
name or ref therefore cannot be established from repository data, so ``label_source`` is ``nearest_place`` (the nearest
OSM ``place=*`` node with a name, with its distance) or ``unnamed`` (no named place within ``MAX_PLACE_M``; the item
then names its road node). The OSM way id is always reported so a reader can look the road up.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

PLACE_KINDS = ("village", "hamlet", "town", "isolated_dwelling", "quarter", "neighbourhood")
MAX_PLACE_M = 5000.0


class PlaceIndex:
    def __init__(self, overpass_path, to_5179):
        """``to_5179(lon, lat) -> (x, y)`` (EPSG:5179 metres, same CRS as the routing graph)."""
        self.path = Path(overpass_path)
        raw = json.loads(self.path.read_text())
        self.osm_base = (raw.get("osm3s") or {}).get("timestamp_osm_base")
        self.places = []
        for el in raw.get("elements", []):
            tags = el.get("tags") or {}
            if tags.get("place") not in PLACE_KINDS or not tags.get("name"):
                continue
            lon, lat = (el.get("lon"), el.get("lat")) if el["type"] == "node" else \
                ((el.get("center") or {}).get("lon"), (el.get("center") or {}).get("lat"))
            if lon is None or lat is None:
                continue
            x, y = to_5179(lon, lat)
            self.places.append({"osm_id": "%s/%d" % (el["type"], el["id"]), "x": x, "y": y,
                                "ko": tags.get("name:ko") or tags.get("name"), "en": tags.get("name:en"),
                                "kind": tags["place"]})
        self.places.sort(key=lambda p: p["osm_id"])

    def nearest(self, x: float, y: float):
        best, bd = None, None
        for p in self.places:
            d = math.hypot(p["x"] - x, p["y"] - y)
            if bd is None or d < bd or (d == bd and p["osm_id"] < best["osm_id"]):
                best, bd = p, d
        return best, bd


def label_for(index: PlaceIndex | None, x: float, y: float, node_id: str) -> dict:
    """Label fields for a road point (EPSG:5179)."""
    if index is not None:
        p, d = index.nearest(x, y)
        if p is not None and d <= MAX_PLACE_M:
            return {"label_ko": p["ko"], "label_en": p["en"], "label_source": "nearest_place",
                    "place_osm_id": p["osm_id"], "place_kind": p["kind"], "place_distance_m": int(round(d)), "near_node_id": node_id}
    return {"label_ko": None, "label_en": None, "label_source": "unnamed", "place_osm_id": None, "place_kind": None,
            "place_distance_m": None, "near_node_id": node_id}
