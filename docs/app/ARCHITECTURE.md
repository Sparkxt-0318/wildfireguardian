# WildfireGuardian Resident App — Architecture Specification

> The consumer-facing companion to the WildfireGuardian research system: a
> phone/web app that shows an elderly resident, in real time, exactly what they
> need to know about a nearby wildfire — and nothing they don't.
>
> This document is the **single source of truth** for the app's structure, API
> contract, design system, and product rules. Backend, frontend, and docs are
> all built against it.

---

## 1. Product decisions (non-negotiable)

1. **Every life-safety feature is free.** Danger status, the map, spread
   prediction, evacuation routes, alerts — free, forever, no account needed.
   Paywalled emergency information is both unethical and grounds for rejection
   from the Apple App Store and Google Play. The paid tier ("Guardian Plus",
   via Stripe) covers *convenience*: family circle notifications, SMS/phone-call
   alert delivery, offline map packs, and watching multiple addresses.
2. **Three danger levels, never more.** `SAFE` (안전, green), `WATCH` (주의,
   amber), `GO` (대피, red). Elderly users under stress cannot parse a 5-level
   scale. Each level is always shown as **color + icon + word** — never color
   alone.
3. **One primary action per screen.** The Home screen has exactly one giant
   button whose label changes with the danger level.
4. **Automatic information triage.** The backend's guidance engine picks an
   ordered subset of "cards" to show, by danger level (§6). In `GO` mode the
   app shows at most 4 cards. More information is not more helpful when the
   user is 78 and the hill behind the house is burning.
5. **Honesty labels.** When serving the bundled demonstration scenario the UI
   permanently shows a `연습 모드 / DEMO` banner. The app always carries the
   research disclaimer: it supplements — never replaces — official alerts
   (재난문자) and 119 instructions. No research metrics (AUC etc.) appear in
   the resident UI.
6. **Korean first, English second.** Every user-visible string exists in both;
   the backend ships both (`*_ko` / `*_en` fields, matching the existing
   repo convention of `reason_ko`), the client picks.
7. **The existing research/operator code is not touched.** The resident app is
   new code under `app/`; it imports nothing from
   `src/wildfireguardian` at runtime (the research pipeline's heavy geo stack
   must not be a deployment dependency), but its live mode is designed so the
   research pipeline can later feed it through the same JSON contract.

## 2. Repository layout

```
app/
  backend/                     # FastAPI resident gateway (Python 3.11)
    requirements.txt           # fastapi, uvicorn, httpx, stripe, pytest
    guardian_app/
      __init__.py
      main.py                  # app factory, CORS, router mounting
      config.py                # env-driven settings (see §8)
      models.py                # pydantic response/request schemas = the contract
      firestate.py             # FireStateProvider: DemoProvider | LiveFirmsProvider
      spread.py                # predicted spread slices + pathway arrows
      guidance.py              # the triage engine (§6) — pure, unit-tested
      evacroutes.py            # evacuation route provider
      alerts.py                # SSE stream (StreamingResponse, no extra deps)
      payments.py              # Stripe checkout / webhook / status
      store.py                 # stdlib sqlite3 persistence (subscriptions, families)
      demo_data/
        scenario_yeongdeok.json  # synthetic, clearly-labelled replay scenario
    tests/                     # pytest + fastapi TestClient
  frontend/                    # Vite + React + TypeScript PWA
    package.json  vite.config.ts  tsconfig.json  index.html
    capacitor.config.ts        # iOS/Android wrapper config
    public/                    # manifest.webmanifest, icons
    src/
      main.tsx  App.tsx
      api/client.ts            # typed client, mirrors §5 exactly
      i18n/                    # ko.ts en.ts index.tsx (context + hook)
      theme/tokens.css         # design tokens (§7)
      components/              # StatusHeader, GuidanceCard, BigButton, DangerBadge,
                               # WindCompass, SpreadTimeline, ReadAloud, DemoBanner...
      svg/                     # hand-crafted animated SVGs: FlamePulse, WindArrows,
                               # EvacArrow (SMIL/CSS animation, no libraries)
      screens/                 # Home, Map, Guide, Family, Settings
      lib/                     # tts.ts (Web Speech), geo.ts, format.ts, prefs.ts
docs/app/
  ARCHITECTURE.md              # this file
  PUBLISHING_MANUAL.md         # novice-proof app-store publishing guide
  AD_CAMPAIGN.md               # launch marketing campaign
marketing/
  assets/                      # generated imagery (icon concept, hero, ad creatives)
```

## 3. Runtime modes

| mode | fire data | spread prediction | trigger |
|---|---|---|---|
| `demo` (default) | bundled Yeongdeok-area synthetic replay, time-compressed loop | precomputed slices in the scenario file | no env keys set |
| `live` | NASA FIRMS area API (VIIRS+MODIS), 60 s cache | honest `"prediction_available": false` unless a prediction feed is configured | `WFG_FIRMS_MAP_KEY` set |

The demo scenario is **synthetic and labelled as such** inside the file
(`"synthetic": true`, header comment) and in every API response
(`"mode": "demo"`). Live spread prediction requires the research pipeline's
data bundle, which is not committed; the app degrades honestly rather than
fabricating a prediction. `LiveFirmsProvider` can also read a prediction
GeoJSON from `WFG_PREDICTION_FILE` — the hook by which the research pipeline
(`spread_v2` forward sim) feeds the app without becoming a dependency.

## 4. Demo scenario file

`scenario_yeongdeok.json`: a ~6-simulated-hour fire near (36.42 N, 129.37 E),
72 timesteps at 5-minute spacing, each timestep carrying:

```json
{ "t_min": 0, "detections": [{"lat":..,"lon":..,"frp_mw":..,"confidence":"h","sensor":"VIIRS"}],
  "wind": {"speed_ms":.., "dir_deg":..}, "weather": {"temp_c":.., "rh_pct":.., "days_since_rain":14},
  "spread": {"h1": [[...ring coords...]], "h3": [...], "h6": [...]},
  "pathways": [{"bearing_deg":.., "coords": [[lon,lat],...]}] }
```

The provider maps wall-clock time onto the loop (1 real minute = 5 scenario
minutes) and accepts `?t=<minutes>` on every data endpoint for deterministic
tests and demos. Shelters: 4 named synthetic shelters around the fire zone
(Korean + English names). The scenario is geographically plausible (real
coastline/terrain direction of the 2025 Yeongdeok fire: SW→NE run under strong
west winds) but **numerically synthetic**.

## 5. API contract (`/v1`)

All responses `application/json; charset=utf-8`. All user-visible strings in
both `*_ko` and `*_en`. Errors: `{"error": str, "detail_ko": str, "detail_en": str}`.

| method + path | purpose |
|---|---|
| `GET /v1/health` | `{ok, mode, time_utc}` |
| `GET /v1/config` | `{mode, stripe_publishable_key, tile_url, demo_banner_ko/en}` |
| `GET /v1/situation?lat&lon[&t]` | **the** endpoint — full triaged situation (below) |
| `GET /v1/fires[?t]` | GeoJSON FeatureCollection of active detections |
| `GET /v1/spread?lat&lon[&t]` | GeoJSON: spread polygons (props `horizon_hours` ∈ 1,3,6; `p_level` ∈ likely,possible) + pathway LineStrings (`kind:"pathway"`, `bearing_deg`) |
| `GET /v1/route?lat&lon[&t]` | evacuation route (below) |
| `GET /v1/shelters?lat&lon` | nearest shelters, sorted by walk distance |
| `GET /v1/history[?t]` | time series for charts: `[{t_utc, detections, area_ha_est, wind_speed_ms, rh_pct}]` |
| `GET /v1/alerts/stream?lat&lon` | SSE: `event: situation` every refresh, `event: heartbeat` every 15 s |
| `POST /v1/billing/checkout` | `{plan, success_url, cancel_url}` → `{checkout_url}` |
| `POST /v1/billing/webhook` | Stripe webhook (signature-verified) |
| `GET /v1/billing/status?customer_id` | `{active, plan, renews_utc}` |

### 5.1 `situation` response

```json
{
  "mode": "demo",
  "generated_utc": "2026-08-07T04:12:00Z",
  "danger": {"level": "GO", "label_ko": "대피", "label_en": "EVACUATE",
              "reason_ko": "...", "reason_en": "..."},
  "fire": {"active": true, "distance_km": 3.2, "bearing_deg": 310,
            "bearing_text_ko": "북서쪽", "bearing_text_en": "northwest",
            "detections": 41, "first_detected_utc": "...", "last_update_utc": "..."},
  "weather": {"wind_speed_ms": 8.2, "wind_dir_deg": 320, "wind_toward_user": true,
               "rh_pct": 18, "temp_c": 27, "days_since_rain": 14},
  "eta_minutes": 95,
  "cards": [ {"id": "route", "priority": 1, "kind": "route",
              "title_ko": "...", "title_en": "...", "body_ko": "...", "body_en": "...",
              "icon": "route", "action": {"type": "open_route", "value": null}} ],
  "prediction_available": true,
  "disclaimer_ko": "...", "disclaimer_en": "..."
}
```

`eta_minutes` is `null` when the user is not on a predicted pathway. Card
`kind` ∈ `action|info|route|contact`; `icon` ∈
`flame|wind|route|phone|shelter|clock|check|home`; `action.type` ∈
`open_map|open_route|call|none` (`call` value e.g. `"119"`).

### 5.2 `route` response

```json
{"status": "ok",
 "shelter": {"name_ko": "...", "name_en": "...", "lat":.., "lon":..,
              "distance_km": 1.4, "walk_minutes": 25},
 "geometry": {"type": "LineString", "coordinates": [[lon,lat], ...]},
 "steps": [{"instruction_ko": "...", "instruction_en": "...", "distance_m": 240}],
 "warnings_ko": ["..."], "warnings_en": ["..."]}
```

`status` ∈ `ok | no_safe_walk | outside_region`. `no_safe_walk` mirrors the
research finding that ~11 % of origins have no safe pedestrian route — the
card set then leads with "call 119 now" instead of a route (honest failure,
never a fabricated route).

## 6. Guidance triage engine (deterministic, unit-tested)

Inputs: `fire.active`, `distance_km`, `eta_minutes`, `wind_toward_user`,
`route.status`. Rules, first match wins:

1. No active fire within 30 km → **SAFE**. Cards: today's conditions,
   know-your-shelter, emergency contacts check, preparedness kit. (≤ 6 cards)
2. Active fire within 30 km, but `eta_minutes` > 180 or not
   `wind_toward_user` → **WATCH**. Cards: fire distance+direction, wind card,
   prepare-to-leave checklist, notify family, charge phone. (≤ 6)
3. `eta_minutes` ≤ 180 **or** (`distance_km` < 5 and `wind_toward_user`) →
   **GO**. Cards (≤ 4, fixed order): ① evacuation route (or call-119 if
   `no_safe_walk`), ② shelter, ③ call 119, ④ do-nots (no driving through
   smoke, do not return for belongings).

The truth table lives in `tests/test_guidance.py` and is the spec.

## 7. Design system (frontend)

- **Type**: body ≥ 22 px (`--fs-body`), titles 28 px, hero status 40 px; user
  text-size setting ×1.0 / ×1.25 via root font-size. `Noto Sans KR` + system
  stack.
- **Color tokens**: `--safe #1B7F4B`, `--watch #B45309`, `--go #B91C1C`,
  pale derived tints for card backgrounds; AAA contrast for body text; single
  light theme (highest-contrast choice for elderly eyes), honors
  `prefers-reduced-motion` (all SVG animation off).
- **Touch**: min target 64 × 64 px; 8-px spacing grid; 16-px radius.
- **Every card has a 🔊 read-aloud button** (Web Speech API, ko-KR/en-US).
- **Charts** are hand-rolled SVG (wind compass, detection-count timeline,
  spread-ETA bar) following the dataviz design-system method — no chart
  library.
- **Map**: Leaflet + OpenStreetMap tiles; fire = pulsing flame SVG marker,
  spread = graded translucent polygons (1 h deepest), pathways = animated
  dashed arrows, route = thick blue line with walking figure; legend uses
  words + swatches; oversized zoom buttons.

## 8. Configuration (env)

`WFG_APP_MODE` (auto: live if `WFG_FIRMS_MAP_KEY` set), `WFG_FIRMS_MAP_KEY`,
`WFG_PREDICTION_FILE`, `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`,
`STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_MONTHLY`, `STRIPE_PRICE_YEARLY`,
`WFG_DB_PATH` (default `guardian.db`), `WFG_CORS_ORIGINS`. All optional; the
app boots into demo mode with Stripe endpoints returning
`{"error":"billing_not_configured"}` when keys are absent.

## 9. Stripe model

Hosted Stripe Checkout (no card data ever touches the backend), subscription
product **Guardian Plus** with monthly/yearly prices; webhook
(`checkout.session.completed`, `customer.subscription.updated|deleted`)
maintains a `subscriptions` table in sqlite. Test-mode keys by default. The
frontend Family screen calls `checkout` and redirects; on return it polls
`billing/status`. **In the iOS/Android store builds this flow must follow the
stores' purchase rules — the full treatment is in
`docs/app/PUBLISHING_MANUAL.md` §"Payments and the app stores".**

## 10. Verification

- Backend: `pytest app/backend/tests` — triage truth table, contract-shape
  tests for every endpoint, deterministic `?t=` scenarios, Stripe endpoints
  with a stubbed `stripe` module, SSE first-event test.
- Frontend: `npm run typecheck` (tsc --noEmit) and `npm run build` must pass.
- Neither build may modify anything outside `app/`, `docs/app/`, `marketing/`.
