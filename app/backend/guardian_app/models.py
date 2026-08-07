"""Pydantic response/request schemas — the API contract (spec section 5).

Every user-visible string exists in both Korean and English (``*_ko`` /
``*_en``), matching the repo-wide ``reason_ko`` convention.  GeoJSON payloads
(fires/spread/route geometry) are plain dicts: they follow RFC 7946, not a
pydantic schema.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

DangerLevel = Literal["SAFE", "WATCH", "GO"]
CardKind = Literal["action", "info", "route", "contact"]
CardIcon = Literal["flame", "wind", "route", "phone", "shelter", "clock", "check", "home"]
ActionType = Literal["open_map", "open_route", "call", "none"]
RouteStatus = Literal["ok", "no_safe_walk", "outside_region"]


class ErrorBody(BaseModel):
    error: str
    detail_ko: str
    detail_en: str


class HealthResponse(BaseModel):
    ok: bool
    mode: str
    time_utc: str


class ConfigResponse(BaseModel):
    mode: str
    stripe_publishable_key: Optional[str] = None
    tile_url: str
    demo_banner_ko: str
    demo_banner_en: str


class Danger(BaseModel):
    level: DangerLevel
    label_ko: str
    label_en: str
    reason_ko: str
    reason_en: str


class FireInfo(BaseModel):
    active: bool
    distance_km: Optional[float] = None
    bearing_deg: Optional[float] = None
    bearing_text_ko: Optional[str] = None
    bearing_text_en: Optional[str] = None
    detections: int = 0
    first_detected_utc: Optional[str] = None
    last_update_utc: Optional[str] = None


class WeatherInfo(BaseModel):
    wind_speed_ms: Optional[float] = None
    wind_dir_deg: Optional[float] = None
    wind_toward_user: bool = False
    rh_pct: Optional[float] = None
    temp_c: Optional[float] = None
    days_since_rain: Optional[int] = None


class CardAction(BaseModel):
    type: ActionType
    value: Optional[str] = None


class Card(BaseModel):
    id: str
    priority: int
    kind: CardKind
    title_ko: str
    title_en: str
    body_ko: str
    body_en: str
    icon: CardIcon
    action: CardAction


class SituationResponse(BaseModel):
    mode: str
    generated_utc: str
    danger: Danger
    fire: FireInfo
    weather: WeatherInfo
    eta_minutes: Optional[int] = None
    cards: list[Card]
    prediction_available: bool
    disclaimer_ko: str
    disclaimer_en: str


class ShelterInfo(BaseModel):
    name_ko: str
    name_en: str
    lat: float
    lon: float
    distance_km: float
    walk_minutes: int


class RouteStep(BaseModel):
    instruction_ko: str
    instruction_en: str
    distance_m: int


class RouteResponse(BaseModel):
    status: RouteStatus
    shelter: Optional[ShelterInfo] = None
    geometry: Optional[dict] = None  # GeoJSON LineString
    steps: list[RouteStep] = []
    warnings_ko: list[str] = []
    warnings_en: list[str] = []


class SheltersResponse(BaseModel):
    shelters: list[ShelterInfo]


class HistoryPoint(BaseModel):
    t_utc: str
    detections: int
    area_ha_est: float
    wind_speed_ms: float
    rh_pct: float


class HistoryResponse(BaseModel):
    mode: str
    points: list[HistoryPoint]


class CheckoutRequest(BaseModel):
    plan: Literal["monthly", "yearly"] = "monthly"
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str


DISCLAIMER_KO = (
    "이 앱은 참고용 보조 서비스입니다. 재난문자와 119 등 정부의 공식 안내를 "
    "항상 먼저 따라 주세요."
)
DISCLAIMER_EN = (
    "This app is a supplementary aid. Always follow official government "
    "alerts and 119 instructions first."
)

DEMO_BANNER_KO = "연습 모드 — 실제 산불이 아닙니다. 화면의 모든 정보는 훈련용 가상 자료입니다."
DEMO_BANNER_EN = "DEMO — not a real fire. Everything on screen is synthetic practice data."
