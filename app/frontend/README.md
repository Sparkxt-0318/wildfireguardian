# 산불지킴이 / WildfireGuardian — resident app frontend

Vite + React + TypeScript PWA, built against the contract in
`docs/app/ARCHITECTURE.md` (§5). No UI framework, no chart library — the
design system and all charts are hand-rolled (spec §7).

## Develop

```bash
cd app/frontend
npm install
npm run dev            # http://localhost:5173
```

The dev server proxies `/v1/*` to the resident gateway at
`http://localhost:8100` (see `vite.config.ts`). Start the backend first:

```bash
cd app/backend
pip install -r requirements.txt
uvicorn guardian_app.main:app --port 8100
```

With no env keys the backend serves the bundled demo scenario and the app
shows the permanent `연습 모드 / DEMO` banner.

## Checks & build

```bash
npm run typecheck      # tsc --noEmit
npm run build          # typecheck + vite build → dist/
npm run preview        # serve the production build locally
```

`npm run icons` regenerates `public/icons/icon-512.png` from the flame+shield
glyph (dependency-free PNG encoder in `scripts/make-icons.mjs`).

## Pointing at a backend

- **Dev**: automatic via the Vite proxy (`/v1` → `localhost:8100`).
- **Production web**: serve `dist/` behind the same origin as the gateway
  (any reverse proxy that forwards `/v1` to the backend works).
- **Different origin / native builds**: set `VITE_API_BASE` at build time:

  ```bash
  VITE_API_BASE=https://api.example.org npm run build
  ```

  The backend must then allow that origin via `WFG_CORS_ORIGINS`.

## Wrapping with Capacitor (iOS / Android)

`capacitor.config.ts` is committed (appId `kr.wildfireguardian.app`, appName
`산불지킴이`). The native platform folders are **not** committed — generate
them locally:

```bash
npm install
VITE_API_BASE=https://your-gateway.example.org npm run build
npx cap add ios        # once, on macOS with Xcode
npx cap add android    # once, with Android Studio
npx cap sync           # after every web build
npx cap open ios       # or: npx cap open android
```

Store submission steps (signing, listings, and the payment rules that apply
to Guardian Plus inside store builds) are covered novice-first in
`docs/app/PUBLISHING_MANUAL.md`.

## Structure

```
src/
  api/client.ts    typed client mirroring spec §5; SSE + 10 s polling fallback
  i18n/            ko.ts / en.ts single typed key map, ko default
  theme/tokens.css design tokens (§7) + base styles, prefers-reduced-motion
  components/      StatusHeader, BigButton, GuidanceCard, WindCompass,
                   DetectionTimeline, SpreadTimeline, ReadAloud, DemoBanner…
  svg/             FlamePulse, WindArrows, EvacArrow (CSS-animated)
  screens/         Home, Map, Guide, Family, Settings
  lib/             tts.ts, geo.ts, format.ts, prefs.ts
public/
  manifest.webmanifest, sw.js (app shell + last situation JSON), icons/
```

## Product rules honored here

- Every life-safety feature is free; Guardian Plus is convenience only.
- Danger is always color + icon + word; three levels only.
- One giant primary action per screen.
- The UI never displays a number the API did not send; demo data is always
  labelled; loading/error states are calm, huge-type, and bilingual.
- All animation is disabled under `prefers-reduced-motion`.

## Offline demo — the real app with no server

Two scripts turn this build into one self-contained HTML file that anybody can
open with no install, no server and no network:

```bash
cd app/backend  && python3 scripts/capture_demo_fixtures.py   # record the gateway
cd ../frontend  && npm run build && node scripts/make-offline-demo.mjs
# → marketing/demo/resident_app_offline.html
```

The page is this exact production bundle. Only the transport is replaced:
`fetch` and `EventSource` answer from `demo-fixtures.json`, which holds
responses **recorded from the real gateway** in demo mode. No triage rule is
reimplemented — the danger level, the cards, the spread rings and the route are
the backend's own output, so the demo cannot drift from the shipped app.

`capture_demo_fixtures.py --check` verifies the committed fixtures still match a
fresh capture, the same way `make_scenario.py --check` guards the scenario.
