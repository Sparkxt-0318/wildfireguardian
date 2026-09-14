"""SSE alert stream (spec section 5) — plain StreamingResponse, no extra deps.

Wire format::

    event: situation      (immediately on connect, then on every refresh)
    data: {situation JSON}

    event: heartbeat      (every 15 s)
    data: {"time_utc": "..."}

Demo mode refreshes the situation every ``sse_refresh_seconds`` (10 s), which
at 1 real minute = 5 scenario minutes keeps the replay visibly moving.
"""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .firestate import utc_now_iso
from .guidance import build_situation

router = APIRouter()


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


def _situation_event(request: Request, lat: float, lon: float) -> str:
    state = request.app.state.provider.snapshot(None)
    situation = build_situation(state, lat, lon)
    return _sse("situation", situation.model_dump_json())


@router.get("/alerts/stream")
async def alerts_stream(request: Request, lat: float, lon: float):
    settings = request.app.state.settings

    async def gen():
        # First situation event goes out immediately on connect.
        yield _situation_event(request, lat, lon)
        last_refresh = last_heartbeat = time.monotonic()
        while True:
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.25)
            now = time.monotonic()
            if now - last_heartbeat >= settings.sse_heartbeat_seconds:
                yield _sse("heartbeat", json.dumps({"time_utc": utc_now_iso()}))
                last_heartbeat = now
            if now - last_refresh >= settings.sse_refresh_seconds:
                yield _situation_event(request, lat, lon)
                last_refresh = now

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
