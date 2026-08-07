"""Guidance triage engine (spec section 6) — pure, deterministic, unit-tested.

Inputs: ``fire_active``, ``distance_km``, ``eta_minutes``, ``wind_toward_user``,
``route_status``.  Rules, first match wins:

1. No active fire within 30 km                             -> SAFE
2. Fire within 30 km, but ETA > 180 min or wind not
   toward the user                                          -> WATCH
3. ETA <= 180 min, or (distance < 5 km and wind toward)     -> GO
   (an unknown ETA falls through rule 3's first clause)
Fallback (fire within 30 km, ETA unknown, wind toward user,
distance >= 5 km — matched no rule)                         -> WATCH

Card sets per level (SAFE <= 6, WATCH <= 6, GO <= 4, fixed order).  In GO with
``route_status == "no_safe_walk"`` the set leads with "call 119 now" instead
of a route and the separate call-119 card is dropped (no duplicate card).

The full truth table lives in ``tests/test_guidance.py`` and is the spec.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .models import (
    DISCLAIMER_EN,
    DISCLAIMER_KO,
    Card,
    CardAction,
    Danger,
    FireInfo,
    SituationResponse,
    WeatherInfo,
)

SAFE_RADIUS_KM = 30.0
GO_DISTANCE_KM = 5.0
GO_ETA_MINUTES = 180.0

_LABELS = {"SAFE": ("안전", "SAFE"), "WATCH": ("주의", "CAUTION"), "GO": ("대피", "EVACUATE")}


def triage_level(
    fire_active: bool,
    distance_km: Optional[float],
    eta_minutes: Optional[float],
    wind_toward_user: bool,
    route_status: str = "ok",
) -> str:
    """The section-6 decision rules, first match wins.  Pure."""
    if not fire_active or distance_km is None or distance_km > SAFE_RADIUS_KM:
        return "SAFE"
    if (eta_minutes is not None and eta_minutes > GO_ETA_MINUTES) or not wind_toward_user:
        return "WATCH"
    if (eta_minutes is not None and eta_minutes <= GO_ETA_MINUTES) or (
        distance_km < GO_DISTANCE_KM and wind_toward_user
    ):
        return "GO"
    return "WATCH"


def _fmt_km(v: Optional[float]) -> str:
    if v is None:
        return "?"
    return f"{v:.1f}" if v < 10 else f"{v:.0f}"


def danger_reason(
    level: str,
    distance_km: Optional[float],
    bearing_text_ko: Optional[str],
    bearing_text_en: Optional[str],
    eta_minutes: Optional[float],
    wind_toward_user: bool,
) -> tuple[str, str]:
    d = _fmt_km(distance_km)
    if level == "SAFE":
        return (
            "지금 주변 30km 안에 감지된 산불이 없습니다.",
            "No active fire detected within 30 km of you.",
        )
    if level == "WATCH":
        dir_ko = bearing_text_ko or "인근"
        dir_en = bearing_text_en or "nearby"
        if wind_toward_user:
            return (
                f"{dir_ko} 약 {d}km에 산불이 있습니다. 아직 시간 여유는 있지만 준비해 주세요.",
                f"A fire is about {d} km to the {dir_en}. There is still time, but please prepare.",
            )
        return (
            f"{dir_ko} 약 {d}km에 산불이 있지만, 바람이 우리 쪽으로 불지 않습니다.",
            f"A fire is about {d} km to the {dir_en}, but the wind is not blowing toward you.",
        )
    # GO
    if eta_minutes is not None:
        return (
            f"산불이 바람을 타고 다가오고 있습니다. 약 {int(eta_minutes)}분 안에 도착할 수 있습니다. 지금 대피해 주세요.",
            f"The fire is moving toward you with the wind and could arrive in about {int(eta_minutes)} minutes. Please evacuate now.",
        )
    return (
        f"산불이 약 {d}km까지 다가왔고 바람이 우리 쪽으로 붑니다. 지금 대피해 주세요.",
        f"The fire is about {d} km away and the wind is blowing toward you. Please evacuate now.",
    )


def make_danger(
    level: str,
    distance_km: Optional[float],
    bearing_text_ko: Optional[str],
    bearing_text_en: Optional[str],
    eta_minutes: Optional[float],
    wind_toward_user: bool,
) -> Danger:
    ko, en = _LABELS[level]
    r_ko, r_en = danger_reason(
        level, distance_km, bearing_text_ko, bearing_text_en, eta_minutes, wind_toward_user
    )
    return Danger(level=level, label_ko=ko, label_en=en, reason_ko=r_ko, reason_en=r_en)


def _card(id_, priority, kind, icon, t_ko, t_en, b_ko, b_en, action="none", value=None) -> Card:
    return Card(
        id=id_,
        priority=priority,
        kind=kind,
        title_ko=t_ko,
        title_en=t_en,
        body_ko=b_ko,
        body_en=b_en,
        icon=icon,
        action=CardAction(type=action, value=value),
    )


def build_cards(
    level: str,
    *,
    distance_km: Optional[float] = None,
    bearing_text_ko: Optional[str] = None,
    bearing_text_en: Optional[str] = None,
    wind_speed_ms: Optional[float] = None,
    wind_toward_user: bool = False,
    route_status: str = "ok",
    shelter_name_ko: Optional[str] = None,
    shelter_name_en: Optional[str] = None,
) -> list[Card]:
    """Ordered card set per level.  Pure; deterministic for fixed inputs."""
    if level == "SAFE":
        return _safe_cards()
    if level == "WATCH":
        return _watch_cards(
            distance_km, bearing_text_ko, bearing_text_en, wind_speed_ms, wind_toward_user
        )
    return _go_cards(route_status, shelter_name_ko, shelter_name_en)


def _safe_cards() -> list[Card]:
    return [
        _card(
            "conditions", 1, "info", "check",
            "오늘의 상황", "Today's conditions",
            "지금 주변 30km 안에는 감지된 산불이 없습니다. 편안한 하루 보내세요.",
            "No active fire detected within 30 km right now. Have a peaceful day.",
        ),
        _card(
            "know_shelter", 2, "info", "shelter",
            "가까운 대피소 알아 두기", "Know your nearest shelter",
            "미리 지도에서 가까운 대피소 위치를 한 번 확인해 두세요.",
            "Take a moment to check where your nearest shelter is on the map.",
            action="open_map",
        ),
        _card(
            "contacts", 3, "contact", "phone",
            "비상 연락처 확인", "Check emergency contacts",
            "가족과 이웃의 전화번호가 휴대전화에 저장되어 있는지 확인해 주세요.",
            "Make sure family and neighbor phone numbers are saved in your phone.",
        ),
        _card(
            "kit", 4, "info", "home",
            "비상 가방 준비", "Prepare a go-bag",
            "약, 물, 손전등, 신분증을 한 가방에 모아 두면 위급할 때 큰 도움이 됩니다.",
            "Keeping medicine, water, a flashlight, and your ID in one bag helps greatly in an emergency.",
        ),
    ]


def _watch_cards(
    distance_km: Optional[float],
    bearing_text_ko: Optional[str],
    bearing_text_en: Optional[str],
    wind_speed_ms: Optional[float],
    wind_toward_user: bool,
) -> list[Card]:
    d = _fmt_km(distance_km)
    dir_ko = bearing_text_ko or "인근"
    dir_en = bearing_text_en or "nearby"
    wind_txt = f"{wind_speed_ms:.0f}" if wind_speed_ms is not None else "?"
    toward_ko = "우리 쪽으로 불고 있습니다" if wind_toward_user else "우리 쪽으로 불지 않습니다"
    toward_en = "blowing toward you" if wind_toward_user else "not blowing toward you"
    return [
        _card(
            "fire_info", 1, "info", "flame",
            "산불 위치", "Fire location",
            f"{dir_ko} 약 {d}km 지점에서 산불이 감지되었습니다. 지도에서 확인해 보세요.",
            f"A fire has been detected about {d} km to the {dir_en}. See it on the map.",
            action="open_map",
        ),
        _card(
            "wind", 2, "info", "wind",
            "바람 정보", "Wind",
            f"바람이 초속 {wind_txt}m로 {toward_ko}.",
            f"The wind is {wind_txt} m/s and {toward_en}.",
        ),
        _card(
            "prepare", 3, "action", "clock",
            "떠날 준비", "Prepare to leave",
            "약, 물, 신분증, 겉옷을 현관 앞에 미리 챙겨 두세요.",
            "Place medicine, water, your ID, and a jacket by the front door now.",
        ),
        _card(
            "family", 4, "contact", "phone",
            "가족에게 알리기", "Tell your family",
            "가족에게 전화해서 지금 상황을 알려 주세요.",
            "Call your family and let them know the situation.",
        ),
        _card(
            "charge", 5, "action", "check",
            "휴대전화 충전", "Charge your phone",
            "휴대전화를 지금 충전해 두세요. 정전이 될 수 있습니다.",
            "Charge your phone now. The power may go out.",
        ),
    ]


def _go_cards(
    route_status: str,
    shelter_name_ko: Optional[str],
    shelter_name_en: Optional[str],
) -> list[Card]:
    shelter_ko = shelter_name_ko or "가까운 대피소"
    shelter_en = shelter_name_en or "the nearest shelter"
    donots = _card(
        "donots", 9, "info", "flame",
        "하지 마세요", "Do not",
        "연기 속으로 운전하지 마세요. 물건을 가지러 집에 돌아가지 마세요.",
        "Do not drive into smoke. Do not go back for belongings.",
    )
    shelter_card = _card(
        "shelter", 2, "info", "shelter",
        "대피소", "Shelter",
        f"{shelter_ko}(으)로 가세요. 지도에서 위치를 확인할 수 있습니다.",
        f"Go to {shelter_en}. You can see it on the map.",
        action="open_map",
    )
    if route_status == "no_safe_walk":
        cards = [
            _card(
                "call119_now", 1, "action", "phone",
                "지금 119에 전화하세요", "Call 119 now",
                "걸어서 갈 수 있는 안전한 길을 찾지 못했습니다. 지금 바로 119에 전화해서 도움을 요청하세요.",
                "We could not find a safe walking route. Call 119 right now and ask for help.",
                action="call", value="119",
            ),
            shelter_card,
            donots,
        ]
    else:
        cards = [
            _card(
                "route", 1, "route", "route",
                "대피 경로", "Evacuation route",
                f"{shelter_ko}까지 가는 길을 안내해 드립니다. 지금 출발하세요.",
                f"We will guide you to {shelter_en}. Leave now.",
                action="open_route",
            ),
            shelter_card,
            _card(
                "call119", 3, "contact", "phone",
                "119에 알리기", "Call 119",
                "이동이 어렵거나 도움이 필요하면 119에 전화하세요.",
                "If you cannot move or need help, call 119.",
                action="call", value="119",
            ),
            donots,
        ]
    for i, c in enumerate(cards, start=1):
        c.priority = i
    return cards


# --------------------------------------------------------------------------
# Situation assembly: FireState + user location -> the §5.1 response.
# Deterministic for a fixed FireState and location (timestamp aside).
# --------------------------------------------------------------------------

def build_situation(state, user_lat: float, user_lon: float) -> SituationResponse:
    """Assemble the full triaged situation for one user location.

    ``state`` is a ``firestate.FireState``.  Imports are local to keep the
    triage core of this module free of any heavier wiring.
    """
    from . import spread as sp
    from .evacroutes import build_route, sorted_shelters

    detections = state.detections
    fire_active = len(detections) > 0

    distance_km: Optional[float] = None
    fire_bearing: Optional[float] = None
    b_ko: Optional[str] = None
    b_en: Optional[str] = None
    if fire_active:
        nearest = min(
            detections, key=lambda d: sp.haversine_km(user_lat, user_lon, d["lat"], d["lon"])
        )
        distance_km = round(
            sp.haversine_km(user_lat, user_lon, nearest["lat"], nearest["lon"]), 1
        )
        fire_bearing = round(
            sp.bearing_deg(user_lat, user_lon, nearest["lat"], nearest["lon"]), 0
        )
        b_ko, b_en = sp.bearing_to_text(fire_bearing)

    wind_speed = state.wind.get("speed_ms")
    wind_dir = state.wind.get("dir_deg")
    toward = False
    if fire_active and wind_dir is not None:
        ref = state.front or {"lat": nearest["lat"], "lon": nearest["lon"]}
        toward = sp.wind_toward_user(ref["lat"], ref["lon"], user_lat, user_lon, wind_dir)

    eta = (
        sp.eta_minutes_for(user_lat, user_lon, state.pathways, wind_speed)
        if fire_active
        else None
    )

    route = build_route(user_lat, user_lon, state)
    level = triage_level(fire_active, distance_km, eta, toward, route.status)

    shelter_ko = shelter_en = None
    if route.shelter is not None:
        shelter_ko, shelter_en = route.shelter.name_ko, route.shelter.name_en
    else:
        shelters = sorted_shelters(user_lat, user_lon, state)
        if shelters:
            shelter_ko, shelter_en = shelters[0].name_ko, shelters[0].name_en

    cards = build_cards(
        level,
        distance_km=distance_km,
        bearing_text_ko=b_ko,
        bearing_text_en=b_en,
        wind_speed_ms=wind_speed,
        wind_toward_user=toward,
        route_status=route.status,
        shelter_name_ko=shelter_ko,
        shelter_name_en=shelter_en,
    )

    return SituationResponse(
        mode=state.mode,
        generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        danger=make_danger(level, distance_km, b_ko, b_en, eta, toward),
        fire=FireInfo(
            active=fire_active,
            distance_km=distance_km,
            bearing_deg=fire_bearing,
            bearing_text_ko=b_ko,
            bearing_text_en=b_en,
            detections=len(detections),
            first_detected_utc=state.first_detected_utc,
            last_update_utc=state.last_update_utc,
        ),
        weather=WeatherInfo(
            wind_speed_ms=wind_speed,
            wind_dir_deg=wind_dir,
            wind_toward_user=toward,
            rh_pct=state.weather.get("rh_pct"),
            temp_c=state.weather.get("temp_c"),
            days_since_rain=state.weather.get("days_since_rain"),
        ),
        eta_minutes=eta,
        cards=cards,
        prediction_available=state.prediction_available,
        disclaimer_ko=DISCLAIMER_KO,
        disclaimer_en=DISCLAIMER_EN,
    )
