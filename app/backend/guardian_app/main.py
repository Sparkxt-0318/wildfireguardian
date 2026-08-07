"""App factory, CORS, router mounting (spec sections 2, 5, 8).

Run the dev server on the project's conventional port 8100::

    uvicorn guardian_app.main:app --port 8100
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from . import __version__, alerts, payments
from .config import Settings, load_settings
from .evacroutes import build_route, sorted_shelters
from .firestate import make_provider
from .guidance import build_situation
from .models import (
    DEMO_BANNER_EN,
    DEMO_BANNER_KO,
    ConfigResponse,
    HealthResponse,
    HistoryPoint,
    RouteResponse,
    SheltersResponse,
    SituationResponse,
    UTF8JSONResponse,
)
from .spread import fires_feature_collection, spread_feature_collection
from .store import Store

TQuery = Query(
    default=None,
    ge=0,
    description="Scenario-minute override for deterministic demos/tests "
    "(demo mode; without it, wall clock maps 1 real min = 5 scenario min, looping).",
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_app(env: Optional[dict] = None) -> FastAPI:
    """Build the FastAPI app from the environment (or an explicit env dict)."""
    settings: Settings = load_settings(env)
    app = FastAPI(
        title="WildfireGuardian Resident Gateway",
        version=__version__,
        default_response_class=UTF8JSONResponse,  # spec §5: charset=utf-8
    )
    app.state.settings = settings
    app.state.provider = make_provider(settings)
    app.state.store = Store(settings.db_path)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        return UTF8JSONResponse(
            status_code=400,
            content={
                "error": "invalid_request",
                "detail_ko": "요청 값이 올바르지 않습니다. 위치 정보를 확인해 주세요.",
                "detail_en": "Invalid request parameters. Please check the location values.",
            },
        )

    v1 = APIRouter(prefix="/v1")

    @v1.get("/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(ok=True, mode=settings.mode, time_utc=_now_utc())

    @v1.get("/config", response_model=ConfigResponse)
    async def config():
        return ConfigResponse(
            mode=settings.mode,
            stripe_publishable_key=settings.stripe_publishable_key or None,
            tile_url=settings.tile_url,
            demo_banner_ko=DEMO_BANNER_KO,
            demo_banner_en=DEMO_BANNER_EN,
        )

    @v1.get("/situation", response_model=SituationResponse)
    async def situation(lat: float, lon: float, t: Optional[float] = TQuery):
        state = app.state.provider.snapshot(t)
        return build_situation(state, lat, lon)

    @v1.get("/fires")
    async def fires(t: Optional[float] = TQuery):
        state = app.state.provider.snapshot(t)
        return fires_feature_collection(state.detections, state.mode)

    @v1.get("/spread")
    async def spread(lat: float, lon: float, t: Optional[float] = TQuery):
        state = app.state.provider.snapshot(t)
        fc = spread_feature_collection(state.spread, state.pathways, state.mode)
        fc["prediction_available"] = state.prediction_available
        return fc

    @v1.get("/route", response_model=RouteResponse)
    async def route(lat: float, lon: float, t: Optional[float] = TQuery):
        state = app.state.provider.snapshot(t)
        return build_route(lat, lon, state)

    @v1.get("/shelters", response_model=SheltersResponse)
    async def shelters(lat: float, lon: float):
        state = app.state.provider.snapshot(None)
        return SheltersResponse(shelters=sorted_shelters(lat, lon, state))

    @v1.get("/history", response_model=list[HistoryPoint])
    async def history(t: Optional[float] = TQuery):
        # Spec §5: a bare array — the frontend chart consumes it directly.
        return app.state.provider.history(t)

    app.include_router(v1)
    app.include_router(alerts.router, prefix="/v1")
    app.include_router(payments.router, prefix="/v1")
    return app


_app: Optional[FastAPI] = None


def __getattr__(name: str) -> FastAPI:
    """Lazy module attribute (PEP 562): ``uvicorn guardian_app.main:app``
    builds the app on first access, while importing ``create_app`` for tests
    stays side-effect free (no sqlite file is created at import time)."""
    global _app
    if name == "app":
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
