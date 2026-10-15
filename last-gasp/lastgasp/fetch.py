"""Download an OpenStreetMap extract through the OSM editing API /map call.

The Overpass API was unreachable from the build environment (connection reset
and timeouts on four mirrors on 2026-10-14), so the main OSM API is used. It
allows small bounding boxes only and should be called sparingly.
"""
from __future__ import annotations

from pathlib import Path

import requests

OSM_MAP_URL = "https://api.openstreetmap.org/api/0.6/map"
USER_AGENT = "last-gasp-feasibility/0.1 (WildfireGuardian research prototype)"


def fetch_osm_map(bbox, out_path: Path, timeout=180):
    lon0, lat0, lon1, lat1 = bbox
    params = {"bbox": f"{lon0},{lat0},{lon1},{lat1}"}
    r = requests.get(OSM_MAP_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    r.raise_for_status()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(r.content)
    return out_path
