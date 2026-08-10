"""Spread slices, pathway arrows, geometry helpers and the demo ETA model.

The ETA model (demo heuristic — NOT a research claim, and none of it comes
from the research pipeline):

    front_speed_kmh = 0.3 + 0.25 * wind_speed_ms
    eta_minutes     = (distance along the predicted pathway from the fire
                       front to the user's projection point, in km)
                      / front_speed_kmh * 60

A user counts as "on a predicted pathway" when they sit within
``PATHWAY_CORRIDOR_KM`` of one of the scenario's pathway polylines; otherwise
``eta_minutes`` is ``None`` (the contract's honest "no ETA" answer).
"""

from __future__ import annotations

import math
from typing import Optional

PATHWAY_CORRIDOR_KM = 3.0

#: Minimum along-pathway distance (km) that counts as "ahead of the front".
#: Below it the resident is beside or behind the fire and has no ETA at all —
#: see the note in :func:`eta_minutes_for`.
ETA_MIN_ALONG_KM = 0.1
WIND_TOWARD_HALF_ANGLE_DEG = 60.0

_KO_DIRS = ["북쪽", "북동쪽", "동쪽", "남동쪽", "남쪽", "남서쪽", "서쪽", "북서쪽"]
_EN_DIRS = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]


# ---------------------------------------------------------------- geometry --

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2, degrees clockwise from north."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def angle_diff_deg(a: float, b: float) -> float:
    d = abs((a - b) % 360.0)
    return min(d, 360.0 - d)


def bearing_to_text(b: float) -> tuple[str, str]:
    idx = int(((b % 360.0) + 22.5) // 45.0) % 8
    return _KO_DIRS[idx], _EN_DIRS[idx]


def point_in_ring(lat: float, lon: float, ring: list[list[float]]) -> bool:
    """Ray-cast point-in-polygon; ``ring`` is [[lon, lat], ...]."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def _project_on_segment_km(
    lat: float, lon: float, a: list[float], b: list[float]
) -> tuple[float, float]:
    """(perpendicular distance km, along-segment distance km from a).

    Local equirectangular approximation — fine at the <30 km demo scale.
    ``a``/``b`` are [lon, lat].
    """
    kx = 111.320 * math.cos(math.radians(lat))
    ky = 110.574
    ax, ay = (a[0] - lon) * kx, (a[1] - lat) * ky
    bx, by = (b[0] - lon) * kx, (b[1] - lat) * ky
    dx, dy = bx - ax, by - ay
    seg_len2 = dx * dx + dy * dy
    if seg_len2 <= 1e-12:
        return math.hypot(ax, ay), 0.0
    t = max(0.0, min(1.0, -(ax * dx + ay * dy) / seg_len2))
    px, py = ax + t * dx, ay + t * dy
    return math.hypot(px, py), t * math.sqrt(seg_len2)


def distance_along_polyline_km(
    lat: float, lon: float, coords: list[list[float]]
) -> tuple[float, float]:
    """(min perpendicular distance km, along-line distance km at that point)."""
    best_perp = float("inf")
    best_along = 0.0
    cum = 0.0
    for a, b in zip(coords, coords[1:]):
        perp, along = _project_on_segment_km(lat, lon, a, b)
        if perp < best_perp:
            best_perp = perp
            best_along = cum + along
        cum += haversine_km(a[1], a[0], b[1], b[0])
    return best_perp, best_along


# ------------------------------------------------------------- ETA & wind --

def front_speed_kmh(wind_speed_ms: Optional[float]) -> float:
    """Demo-heuristic effective head-fire speed (see module docstring)."""
    if wind_speed_ms is None:
        wind_speed_ms = 0.0
    return 0.3 + 0.25 * wind_speed_ms


def eta_minutes_for(
    lat: float,
    lon: float,
    pathways: list[dict],
    wind_speed_ms: Optional[float],
) -> Optional[int]:
    """Demo ETA: distance along the nearest pathway / effective front speed.

    ``None`` when the user is not within the corridor of any pathway.
    """
    if not pathways:
        return None
    best: Optional[float] = None
    for pw in pathways:
        coords = pw.get("coords") or []
        if len(coords) < 2:
            continue
        perp, along = distance_along_polyline_km(lat, lon, coords)
        if perp <= PATHWAY_CORRIDOR_KM and (best is None or along < best):
            best = along
    if best is None:
        return None
    # ⚠ AN ETA OF ZERO IS NOT AN ETA, AND SHOWING IT IS THE WORST KIND OF WRONG.
    # `along` is measured from the front, downwind. A resident who is beside or
    # BEHIND the front projects onto the start of the polyline and scores
    # along == 0 — the fire has passed them, or is moving away. Returning 0
    # there put "0분 / 0 minutes until the fire arrives" on a CAUTION screen
    # whose own sentence said the wind was blowing the fire away: the most
    # alarming number this app can print, next to a reassurance, for somebody
    # who is not in fact in the fire's path. The contract (§5.1) already says
    # what to answer when the resident is not on a predicted pathway — null —
    # and being beside the front is that case. Someone genuinely at the front
    # is still reached by the distance rule (<5 km + wind toward = GO), so no
    # warning is lost by declining to invent a countdown.
    if best <= ETA_MIN_ALONG_KM:
        return None
    speed = front_speed_kmh(wind_speed_ms)
    return max(0, round(best / speed * 60.0))


def wind_toward_user(
    fire_lat: float, fire_lon: float, user_lat: float, user_lon: float, wind_dir_deg: Optional[float]
) -> bool:
    """True when the downwind direction points from the fire toward the user
    (within ±60 degrees). ``wind_dir_deg`` is the meteorological FROM-direction."""
    if wind_dir_deg is None:
        return False
    downwind = (wind_dir_deg + 180.0) % 360.0
    to_user = bearing_deg(fire_lat, fire_lon, user_lat, user_lon)
    return angle_diff_deg(downwind, to_user) <= WIND_TOWARD_HALF_ANGLE_DEG


def in_any_ring(lat: float, lon: float, spread: dict, keys: tuple[str, ...], ring_idx: int) -> bool:
    """Is the point inside ring ``ring_idx`` (0=likely, 1=possible) of any of
    the given horizons?"""
    for k in keys:
        rings = spread.get(k) or []
        if len(rings) > ring_idx and point_in_ring(lat, lon, rings[ring_idx]):
            return True
    return False


# ------------------------------------------------------------ GeoJSON out --

_P_LEVELS = ["likely", "possible"]


def spread_feature_collection(spread: dict, pathways: list[dict], mode: str) -> dict:
    """GeoJSON FeatureCollection: spread polygons + pathway arrows (spec §5)."""
    features: list[dict] = []
    for key, hours in (("h1", 1), ("h3", 3), ("h6", 6)):
        rings = spread.get(key) or []
        for idx, ring in enumerate(rings):
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                    "properties": {
                        "horizon_hours": hours,
                        "p_level": _P_LEVELS[idx] if idx < len(_P_LEVELS) else "possible",
                    },
                }
            )
    for pw in pathways:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": pw.get("coords") or []},
                "properties": {"kind": "pathway", "bearing_deg": pw.get("bearing_deg")},
            }
        )
    return {"type": "FeatureCollection", "mode": mode, "features": features}


def fires_feature_collection(detections: list[dict], mode: str) -> dict:
    """GeoJSON FeatureCollection of active detections."""
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [d["lon"], d["lat"]]},
            "properties": {
                "frp_mw": d.get("frp_mw"),
                "confidence": d.get("confidence"),
                "sensor": d.get("sensor"),
            },
        }
        for d in detections
    ]
    return {"type": "FeatureCollection", "mode": mode, "features": features}
