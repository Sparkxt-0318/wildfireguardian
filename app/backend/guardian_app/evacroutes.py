"""Evacuation route provider (spec section 5.2).

Demo-mode routing is a straight-line walking approximation to the nearest
*safe* shelter — a demo heuristic, not real pedestrian routing.  It fails
honestly:

* ``no_safe_walk``   — the user stands inside the 1-hour "likely" spread ring,
  or every shelter is unsafe (inside a predicted spread ring / within 2 km of
  a detection) or beyond ``MAX_WALK_KM``.  The caller then leads with a
  "call 119 now" card; no route is ever fabricated.
* ``outside_region`` — the user is outside the demo scenario region.

Walking speed assumes an elderly resident: 3.4 km/h.
"""

from __future__ import annotations

import math
from typing import Optional

from .firestate import FireState
from .models import RouteResponse, RouteStep, ShelterInfo
from .spread import (
    bearing_deg,
    bearing_to_text,
    haversine_km,
    in_any_ring,
    point_in_ring,
)

WALK_SPEED_KMH = 3.4
MAX_WALK_KM = 8.0
DEMO_REGION_RADIUS_KM = 60.0
SHELTER_MIN_FIRE_KM = 2.0


def shelter_info(user_lat: float, user_lon: float, s: dict) -> ShelterInfo:
    d = haversine_km(user_lat, user_lon, s["lat"], s["lon"])
    return ShelterInfo(
        name_ko=s["name_ko"],
        name_en=s["name_en"],
        lat=s["lat"],
        lon=s["lon"],
        distance_km=round(d, 2),
        walk_minutes=max(1, round(d / WALK_SPEED_KMH * 60.0)),
    )


def sorted_shelters(user_lat: float, user_lon: float, state: FireState) -> list[ShelterInfo]:
    infos = [shelter_info(user_lat, user_lon, s) for s in state.shelters]
    return sorted(infos, key=lambda s: s.distance_km)


def _shelter_is_safe(s: dict, state: FireState) -> bool:
    """A shelter is unsafe if fire could plausibly reach it before or shortly
    after an elderly resident's walk (~2 h at 3.4 km/h): inside either 1-hour
    ring, inside the 3-hour "likely" ring, or within 2 km of a detection."""
    lat, lon = s["lat"], s["lon"]
    if in_any_ring(lat, lon, state.spread, ("h1",), 0) or in_any_ring(
        lat, lon, state.spread, ("h1",), 1
    ):
        return False
    if in_any_ring(lat, lon, state.spread, ("h3",), 0):
        return False
    for d in state.detections:
        if haversine_km(lat, lon, d["lat"], d["lon"]) < SHELTER_MIN_FIRE_KM:
            return False
    return True


def _region_center(state: FireState) -> Optional[tuple[float, float]]:
    if state.front:
        return state.front["lat"], state.front["lon"]
    if state.detections:
        n = len(state.detections)
        return (
            sum(d["lat"] for d in state.detections) / n,
            sum(d["lon"] for d in state.detections) / n,
        )
    if state.shelters:
        n = len(state.shelters)
        return (
            sum(s["lat"] for s in state.shelters) / n,
            sum(s["lon"] for s in state.shelters) / n,
        )
    return None


def _line(user_lat: float, user_lon: float, s_lat: float, s_lon: float) -> list[list[float]]:
    """4-point polyline user -> shelter (straight, lightly interpolated)."""
    pts = []
    for t in (0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0):
        lat = user_lat + (s_lat - user_lat) * t
        lon = user_lon + (s_lon - user_lon) * t
        pts.append([round(lon, 5), round(lat, 5)])
    return pts


def _steps(user_lat: float, user_lon: float, sh: ShelterInfo) -> list[RouteStep]:
    total_m = int(round(sh.distance_km * 1000.0))
    b = bearing_deg(user_lat, user_lon, sh.lat, sh.lon)
    dir_ko, dir_en = bearing_to_text(b)
    first = int(round(total_m * 0.6))
    rest = max(0, total_m - first)
    return [
        RouteStep(
            instruction_ko=f"집에서 나와 {dir_ko}으로 {first}m 이동하세요.",
            instruction_en=f"Leave the house and walk {first} m to the {dir_en}.",
            distance_m=first,
        ),
        RouteStep(
            instruction_ko=f"{sh.name_ko}까지 {rest}m 더 이동하세요.",
            instruction_en=f"Continue {rest} m to {sh.name_en}.",
            distance_m=rest,
        ),
    ]


def build_route(user_lat: float, user_lon: float, state: FireState) -> RouteResponse:
    center = _region_center(state)
    if center is None or haversine_km(user_lat, user_lon, *center) > DEMO_REGION_RADIUS_KM:
        return RouteResponse(
            status="outside_region",
            warnings_ko=["현재 위치는 서비스 지역 밖입니다. 지역 안내 방송을 따라 주세요."],
            warnings_en=["Your location is outside the service region. Please follow local guidance."],
        )

    # Standing inside the 1-hour likely spread ring: walking out is not a
    # promise we can make — call 119 (honest failure, mirrors the research
    # finding that some origins have no safe pedestrian route).
    h1 = state.spread.get("h1") or []
    if h1 and point_in_ring(user_lat, user_lon, h1[0]):
        return RouteResponse(
            status="no_safe_walk",
            warnings_ko=["걸어서 대피할 수 있는 안전한 길을 찾지 못했습니다. 지금 119에 전화하세요."],
            warnings_en=["No safe walking route could be found. Call 119 now."],
        )

    safe = [s for s in state.shelters if _shelter_is_safe(s, state)]
    candidates = sorted(
        (shelter_info(user_lat, user_lon, s) for s in safe), key=lambda s: s.distance_km
    )
    candidates = [c for c in candidates if c.distance_km <= MAX_WALK_KM]
    if not candidates:
        return RouteResponse(
            status="no_safe_walk",
            warnings_ko=["걸어서 갈 수 있는 안전한 대피소를 찾지 못했습니다. 지금 119에 전화하세요."],
            warnings_en=["No safe shelter is within walking distance. Call 119 now."],
        )

    sh = candidates[0]
    warnings_ko: list[str] = []
    warnings_en: list[str] = []
    if state.detections:
        nearest_fire = min(
            haversine_km(user_lat, user_lon, d["lat"], d["lon"]) for d in state.detections
        )
        if nearest_fire < 10.0:
            warnings_ko.append("연기가 보이면 젖은 수건으로 코와 입을 가리세요.")
            warnings_en.append("If you see smoke, cover your nose and mouth with a wet cloth.")
    return RouteResponse(
        status="ok",
        shelter=sh,
        geometry={"type": "LineString", "coordinates": _line(user_lat, user_lon, sh.lat, sh.lon)},
        steps=_steps(user_lat, user_lon, sh),
        warnings_ko=warnings_ko,
        warnings_en=warnings_en,
    )
