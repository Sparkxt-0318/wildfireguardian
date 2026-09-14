# WildfireGuardian Resident Gateway (backend)

FastAPI backend for the resident app. Built against
[`docs/app/ARCHITECTURE.md`](../../docs/app/ARCHITECTURE.md) — that document is
the binding contract for every endpoint, field, and rule here.

**Honesty first.** With no configuration this server runs in **demo mode**: it
replays a bundled, clearly-labelled **synthetic** scenario
(`guardian_app/demo_data/scenario_yeongdeok.json`, `"synthetic": true`). Every
response carries `"mode": "demo"` and the client shows a permanent
`연습 모드 / DEMO` banner. Nothing in demo mode is an observation, a research
output, or a forecast. In **live mode** the fire detections are real (NASA
FIRMS) but spread prediction is reported as `"prediction_available": false`
unless a prediction file is explicitly provided — the server degrades honestly
instead of inventing predictions. No research metrics (AUC etc.) appear
anywhere in this API.

## Run

Python 3.11. Dependencies: `fastapi, uvicorn, httpx, stripe, pytest` only
(stdlib `sqlite3` for persistence).

```bash
cd app/backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# dev server — port 8100 is the project convention
uvicorn guardian_app.main:app --port 8100

# with auto-reload during development
uvicorn guardian_app.main:app --port 8100 --reload
```

Smoke test:

```bash
curl "http://127.0.0.1:8100/v1/health"
curl "http://127.0.0.1:8100/v1/situation?lat=36.44&lon=129.45&t=200"
curl -N "http://127.0.0.1:8100/v1/alerts/stream?lat=36.44&lon=129.45"
```

## Tests

```bash
cd app/backend
pytest tests            # or from the repo root: pytest app/backend/tests
```

The tests run fully offline with no Stripe keys: Stripe calls are stubbed with
monkeypatch, and the demo provider needs no network. `tests/test_guidance.py`
holds the section-6 triage truth table and **is the spec** for the guidance
engine.

## Runtime modes

| mode | fire data | spread prediction | trigger |
|---|---|---|---|
| `demo` (default) | bundled synthetic Yeongdeok replay, looping, 1 real min = 5 scenario min | precomputed slices from the scenario file | no env keys set |
| `live` | NASA FIRMS area API (VIIRS + MODIS), 60 s cache | `"prediction_available": false` unless `WFG_PREDICTION_FILE` is set | `WFG_FIRMS_MAP_KEY` set |

Every data endpoint accepts `?t=<scenario minutes>` (demo mode) for
deterministic replays: `t=0` is ignition, `t=355` the last timestep, values
snap to the 5-minute grid and loop at 360.

The demo scenario is regenerated with:

```bash
python3 scripts/make_scenario.py          # rewrite the JSON (seeded, byte-stable)
python3 scripts/make_scenario.py --check  # verify the committed file matches
```

## Configuration (env, all optional — spec §8)

| variable | default | purpose |
|---|---|---|
| `WFG_APP_MODE` | auto | `demo` or `live`; auto = `live` iff `WFG_FIRMS_MAP_KEY` is set |
| `WFG_FIRMS_MAP_KEY` | – | NASA FIRMS map key; enables live detections |
| `WFG_PREDICTION_FILE` | – | GeoJSON from the research pipeline's forward sim; enables live spread prediction |
| `STRIPE_SECRET_KEY` | – | Stripe secret key (test-mode keys by default) |
| `STRIPE_PUBLISHABLE_KEY` | – | exposed to the client via `/v1/config` |
| `STRIPE_WEBHOOK_SECRET` | – | webhook signature verification |
| `STRIPE_PRICE_MONTHLY` | – | Guardian Plus monthly price id |
| `STRIPE_PRICE_YEARLY` | – | Guardian Plus yearly price id |
| `WFG_DB_PATH` | `guardian.db` | sqlite database file |
| `WFG_CORS_ORIGINS` | `*` | comma-separated allowed origins |
| `WFG_SCENARIO_FILE` | bundled scenario | dev/test hook: path to an alternate demo scenario JSON |

With no Stripe keys the billing endpoints answer
`{"error": "billing_not_configured"}` (503) and
`GET /v1/billing/status` returns `{"active": false, "reason":
"billing_not_configured"}`. **Every life-safety endpoint works without any
configuration — safety is free, forever (spec §1).**

## Endpoints (`/v1`, spec §5)

`health`, `config`, `situation`, `fires`, `spread`, `route`, `shelters`,
`history`, `alerts/stream` (SSE: `situation` on connect + every refresh,
`heartbeat` every 15 s), `billing/checkout`, `billing/webhook`,
`billing/status`. All user-visible strings are bilingual (`*_ko` / `*_en`).

## Demo heuristics (documented, not research claims)

* ETA: distance along the predicted pathway ÷ effective front speed, where
  `front_speed_kmh = 0.3 + 0.25 × wind_speed_ms` (`guardian_app/spread.py`).
* Burned-area estimate: `detections × 14 ha` (a VIIRS pixel is ~375 m).
* Walking pace for route timing: 3.4 km/h (elderly resident).

These exist so the demo behaves plausibly. They are not outputs of, nor
claims about, the research models in `src/wildfireguardian`.
