"""SSE stream tests.

The installed Starlette TestClient buffers entire responses, so an infinite
SSE stream can never be read through it.  Instead we call the endpoint
directly with a real ``Request`` and consume the ``StreamingResponse`` async
generator — the exact code a real server runs.
"""

from __future__ import annotations

import asyncio
import json

from starlette.requests import Request

from guardian_app.alerts import alerts_stream

NEAR = (36.44, 129.45)


def _request(app) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/alerts/stream",
        "query_string": b"lat=36.44&lon=129.45",
        "headers": [],
        "app": app,
    }

    async def receive():
        await asyncio.sleep(3600)  # client never disconnects during the test

    return Request(scope, receive)


def test_sse_first_event_is_situation_immediately(app):
    async def run():
        resp = await alerts_stream(_request(app), lat=NEAR[0], lon=NEAR[1])
        assert resp.media_type == "text/event-stream"
        gen = resp.body_iterator
        first = await asyncio.wait_for(gen.__anext__(), timeout=2.0)
        await gen.aclose()
        return first

    first = asyncio.run(run())
    assert first.startswith("event: situation\n")
    data_line = [l for l in first.splitlines() if l.startswith("data:")][0]
    payload = json.loads(data_line[len("data:"):].strip())
    assert payload["mode"] == "demo"
    assert payload["danger"]["level"] in ("SAFE", "WATCH", "GO")
    assert payload["danger"]["reason_ko"] and payload["danger"]["reason_en"]
    assert payload["cards"]
    assert first.endswith("\n\n")


def test_sse_emits_heartbeat_and_refresh(app):
    # Shrink the cadence so the test finishes fast; the production values are
    # 15 s heartbeats and 10 s refreshes (spec section 5).
    app.state.settings.sse_heartbeat_seconds = 0.05
    app.state.settings.sse_refresh_seconds = 0.08

    async def run():
        resp = await alerts_stream(_request(app), lat=NEAR[0], lon=NEAR[1])
        gen = resp.body_iterator
        events = []
        for _ in range(4):
            events.append(await asyncio.wait_for(gen.__anext__(), timeout=5.0))
        await gen.aclose()
        return events

    events = asyncio.run(run())
    kinds = [e.split("\n", 1)[0] for e in events]
    assert kinds[0] == "event: situation"
    assert "event: heartbeat" in kinds[1:]
    assert kinds.count("event: situation") >= 2, "situation re-sent on refresh"
    hb = next(e for e in events if e.startswith("event: heartbeat"))
    hb_data = json.loads(hb.split("data:", 1)[1].strip())
    assert "time_utc" in hb_data
