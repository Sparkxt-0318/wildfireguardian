"""SSE stream: the first `event: situation` must arrive immediately on connect."""

from __future__ import annotations

import json

NEAR = (36.44, 129.45)


def test_sse_first_event_is_situation(client):
    lat, lon = NEAR
    with client.stream("GET", f"/v1/alerts/stream?lat={lat}&lon={lon}") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        event_line = None
        data_line = None
        for line in resp.iter_lines():
            if line.startswith("event:"):
                event_line = line
            elif line.startswith("data:"):
                data_line = line
            elif line == "" and event_line is not None:
                break
        assert event_line == "event: situation"
        payload = json.loads(data_line[len("data:"):].strip())
        assert payload["mode"] == "demo"
        assert payload["danger"]["level"] in ("SAFE", "WATCH", "GO")
        assert "cards" in payload and payload["cards"]
        assert "reason_ko" in payload["danger"] and "reason_en" in payload["danger"]
