#!/usr/bin/env python3
"""Freeze the demo-mode gateway's real responses into one JSON fixture file.

Why this exists
---------------
The resident app is a normal client: it talks to the gateway over HTTP. To let
somebody try the **real** app with no server — a judge's laptop, a phone on a
train, a link in a review — we need the gateway's answers without the gateway.

The honest way to do that is to **record** them, not to reimplement them. Every
byte in the output file is what ``guardian_app`` actually returned for that
request, produced by the same guidance engine, the same spread model and the
same committed synthetic scenario. Nothing here decides anything: this script
asks and writes down the answer. A second implementation of the triage rules in
JavaScript would be a second source of truth, and the first time the two
disagreed the shipped app and the demo would be telling residents different
things.

The companion bundler is ``app/frontend/scripts/make-offline-demo.mjs``.

Usage
-----
    python3 scripts/capture_demo_fixtures.py --out ../frontend/demo-fixtures.json

Determinism: demo mode + explicit ``?t=`` means two runs produce identical
bytes (``--check`` asserts exactly that, like ``make_scenario.py --check``).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

# The capture must describe demo mode. A stray key in the developer's shell
# would silently record live-mode answers into a file labelled "demo".
for _k in ("WFG_APP_MODE", "WFG_FIRMS_MAP_KEY", "WFG_PREDICTION_FILE",
           "STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY"):
    os.environ.pop(_k, None)

#: Scenario minutes to record. The scenario is a 5-minute grid running 0..355;
#: every 20 minutes is 18 frames — enough that the fire visibly advances
#: between steps, small enough that the bundle stays a few megabytes.
TIMES: tuple[int, ...] = tuple(range(0, 360, 20))

#: Coordinates to record, each a place a resident might actually be relative to
#: the scenario fire. The ids are referenced by the offline demo's place picker.
#: ``home`` is what the app itself defaults to (frontend ``DEFAULT_COORDS``).
PLACES: tuple[dict[str, object], ...] = (
    {"id": "ahead", "lat": 36.43, "lon": 129.48,
     "label_ko": "불길 진행 방향 마을", "label_en": "Village in the fire's path"},
    {"id": "home", "lat": 36.44, "lon": 129.40,
     "label_ko": "기본 위치 (마을 서쪽)", "label_en": "Default location (west of village)"},
    {"id": "near", "lat": 36.44, "lon": 129.45,
     "label_ko": "불길 바로 앞 외딴집", "label_en": "Isolated house close to the fire"},
    {"id": "south", "lat": 36.37, "lon": 129.40,
     "label_ko": "바람 반대편 남쪽 마을", "label_en": "South village, wind blowing away"},
    {"id": "far", "lat": 36.00, "lon": 129.00,
     "label_ko": "멀리 떨어진 읍내", "label_en": "Distant town"},
)


def _get(client, path: str):
    res = client.get(path)
    if res.status_code != 200:
        raise SystemExit(f"STOP: {path} -> HTTP {res.status_code}: {res.text[:200]}")
    return res.json()


def capture() -> dict:
    from fastapi.testclient import TestClient          # noqa: PLC0415

    from guardian_app.main import app                  # noqa: PLC0415

    with TestClient(app) as client:
        health = _get(client, "/v1/health")
        if health.get("mode") != "demo":
            raise SystemExit(f"STOP: gateway is in {health.get('mode')!r} mode, "
                             "refusing to write a file labelled demo")

        static = {
            "/v1/config": _get(client, "/v1/config"),
            "/v1/billing/status": _get(client, "/v1/billing/status?customer_id=demo"),
        }

        by_t: dict[str, dict] = {}
        for t in TIMES:
            by_t[str(t)] = {
                "fires": _get(client, f"/v1/fires?t={t}"),
                "history": _get(client, f"/v1/history?t={t}"),
            }

        by_place: dict[str, dict] = {}
        by_place_t: dict[str, dict] = {}
        levels: dict[str, list[str]] = {}
        for place in PLACES:
            pid, lat, lon = place["id"], place["lat"], place["lon"]
            by_place[str(pid)] = {
                "shelters": _get(client, f"/v1/shelters?lat={lat}&lon={lon}"),
            }
            seen: list[str] = []
            for t in TIMES:
                situation = _get(client, f"/v1/situation?lat={lat}&lon={lon}&t={t}")
                by_place_t[f"{pid}|{t}"] = {
                    "situation": situation,
                    "spread": _get(client, f"/v1/spread?lat={lat}&lon={lon}&t={t}"),
                    "route": _get(client, f"/v1/route?lat={lat}&lon={lon}&t={t}"),
                }
                seen.append(situation["danger"]["level"])
            levels[str(pid)] = seen

    return {
        "_comment": (
            "Recorded responses of the WildfireGuardian resident gateway in DEMO "
            "mode over the committed synthetic scenario. Not observations, not "
            "forecasts. Regenerate: app/backend/scripts/capture_demo_fixtures.py"
        ),
        "synthetic": True,
        "mode": "demo",
        "times": list(TIMES),
        "places": [dict(p) for p in PLACES],
        "static": static,
        "by_t": by_t,
        "by_place": by_place,
        "by_place_t": by_place_t,
        "levels": levels,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(BACKEND_ROOT.parent / "frontend" /
                                         "demo-fixtures.json"))
    ap.add_argument("--check", action="store_true",
                    help="verify the existing file matches a fresh capture")
    args = ap.parse_args()

    data = capture()
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"),
                      sort_keys=True) + "\n"
    out = Path(args.out)

    if args.check:
        if not out.is_file():
            print(f"MISSING: {out}", file=sys.stderr)
            return 2
        if out.read_text(encoding="utf-8") != text:
            print(f"DIFFERS: {out} is not what a fresh capture produces",
                  file=sys.stderr)
            return 1
        print(f"OK: {out} matches a fresh capture")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    kib = len(text.encode("utf-8")) / 1024
    print(f"wrote {out} ({kib:.0f} KiB)")
    print(f"  {len(TIMES)} times x {len(PLACES)} places")
    for pid, seq in data["levels"].items():
        first_go = next((TIMES[i] for i, lv in enumerate(seq) if lv == "GO"), None)
        print(f"  {pid:<6} {seq[0]} -> {seq[-1]}"
              f"{'' if first_go is None else f'   (GO from t={first_go})'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
