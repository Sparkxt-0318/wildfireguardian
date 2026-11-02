# WildfireGuardian 마을별 사전 대피계획 도구

Pre-season village evacuation planner for 지자체 safety staff, 산림청 / fire departments and care
facility managers. For every village and care facility of a region it shows, per recorded fire
scenario, **the latest departure time that still has a checked vehicle route to a shelter**
("출발 마감 HH:MM"), with the evidence behind it: the route, per-scenario heat exposure, compute
time and full provenance.

> **사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.**
> Planning aid only — not for live evacuation operations.

The app never computes routes or forecasts itself. It talks only to the WildfireGuardian
**Route-Check API** (official contract [`contract/wfg_api_v1.yaml`](contract/wfg_api_v1.yaml),
v1.5.0) or reads results the API produced earlier (the precompute cache). The binding build
contract is [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Honesty rules the UI applies

- Exactly three results: **확인된 경로** `checked_route` (green, check), **모델상 경로 없음**
  `model_no_route` (black, slashed circle), **미확인** `unresolved` (grey hatch, question mark).
  Status is always colour + icon + text. Unresolved is never green, never "safe" and never counts
  toward a deadline.
- Per departure time: checked if any candidate shelter is checked; model_no_route only if every
  attempted shelter is model_no_route; otherwise unresolved.
- **출발 마감** = the latest departure offset with a checked route. When an earlier offset is not
  checked (the contract's `latest_contiguous_checked_depart_offset_s` differs or is null) the
  headline adds "앞선 출발 시각 중 확인되지 않은 구간이 있습니다 (연속 확인 기준 HH:MM | 없음)".
  The urgency list sorts model_no_route first, then unresolved, then checked origins by the
  contiguous deadline ascending (contract `latest_contiguous_checked_depart_offset_s`, as the API
  sorts): a checked origin whose earliest departure time has no checked route ranks first among
  them, then by its deadline; vulnerable facilities first on ties. Drawn zones put inside-zone
  origins first (Go before Set). The CSV, the list and the plan sheets use the same order.
- Departure times whose recorded arrival window cannot be met are not sent (the API would answer
  422 `WINDOW_UNSATISFIABLE`) and are shown as a distinct grey **시간창 밖** cell — never safe.
- Every screen states its fire input: "2025년 실제 산불 기록 기반 시나리오 재현" (recorded
  scenarios; the year comes from the region) or "사용자 입력 확산 구역 (가정)" (drawn zones), plus a
  **MOCK** badge whenever data comes from the mock server or a mock-made cache.
- The travel-time-only comparison (`policy: travel_only`) is drawn as a dashed ink line, labelled
  "이동시간만 고려한 경로 (비교용)", shows its flame-contact flags and full-policy re-assessment and is
  never green or called safe.
- Places come only from OSM and the recorded research missions; unnamed places stay unnamed
  ("이름 없는 마을 · node 123"). Places with no accepted road node within 2 km are shown as
  "도로망 2 km 밖 — 점검 불가" and never sent. Each place starts/ends at its 진입 지점 (nearest accepted
  road node, sent as `node_id`); travel between the place and its entry point is not modelled and
  is stated in the right panel, About, the plan sheet and the exports.
- Results computed on a host other than the evaluated booth host (e.g. a Linux container) are
  marked "시험 데이터 · 평가 호스트 아님" in the top bar, the data strip, the plan sheet and exports.

## Quick start

Node 20.19+ (22 recommended), Python 3.11+ for the mock server.

```bash
cd planner
npm ci
cp .env.example .env          # optional; defaults are mock mode

npm run demo                  # starts the MOCK server if needed + the app on http://127.0.0.1:5173
npm run demo -- --mode real   # real Route-Check API (VITE_WFG_API_TARGET, default http://127.0.0.1:8765)
npm run demo -- --preview     # production build + vite preview (same proxy and /cache)
```

Or step by step:

```bash
python3 mock_api/server.py            # terminal 1: MOCK API on http://127.0.0.1:8765/v1
npm run dev                           # terminal 2: app (VITE_WFG_API_MODE=mock by default)

VITE_WFG_API_MODE=real VITE_WFG_API_TARGET=http://127.0.0.1:8765 npm run dev   # real API
```

`npm run demo -- --help` lists the launcher options (`--no-batch` keeps a booth from starting
batches on scenarios without a cache; the launcher exits non-zero when the app server cannot start,
e.g. a busy port).

### Real Route-Check API

The Route-Check API is part of this repository: [`api/`](../api/README.md) with the repository-root
`Makefile` (contract in `contracts/wfg_api_v1.yaml`; the planner's copy is
[`contract/wfg_api_v1.yaml`](contract/wfg_api_v1.yaml)). To run it locally:

```bash
# from the repository root
make api            # first use: creates .venv (Python 3.12), installs pinned dependencies and
                    # fetches the SHA-verified recorded inputs into data/routing; then serves
                    # http://127.0.0.1:8765/v1 (Swagger UI at /docs)
```

- Prerequisites: Python 3.12, GNU `time` (`/usr/bin/time`) and `procps` (`/bin/ps`) — see
  [`api/README.md`](../api/README.md) (requirements, the fixed 30 s budget per check, endpoints).
- It serves `http://127.0.0.1:8765/v1` — the same port as the mock, so stop the mock first.
- Then, in `planner/`: `npm run demo -- --mode real` (the app with this API), or
  `planner/scripts/precompute_planner.sh` (booth cache). The planner talks to the API over HTTP only.
- The booth cache (`planner/cache/`) must come from the evaluated Apple M5 Pro host (native macOS
  arm64). On any other host the script refuses unless `ALLOW_NON_MAC=1`, and then writes test data
  to `planner/.test-cache/` (never committed; view with `WFG_CACHE_DIR=.test-cache npm run dev`).

Deep links (query, used by `scripts/screenshots.mjs` and `scripts/export_plan_pdfs.mjs`):
`?region=<id>&scenario=<input_compact|scenario_set_id|zones>&origin=<place id>&lang=ko|en`, e.g.
`?region=uiseong_andong_2025&scenario=20250324T090000Z&lang=en`. Drawn zones also take
`&input=<input_compact>` (기준 기록 시각) and `&preset=footprints` (copy the default recorded footprints);
`?print=all` opens the plan sheet with every map once the data is ready. The app then keeps its state in
the hash (`#region=…&scenario=<scenario_set_id|drawn>&origin=…`), which also works as a link.
`html[data-wfg-data-ready]` is `"true"` once the selected scenario's results (or the drawn-zone state)
are loaded and `"false"` while loading.

## Static demo (public, no server)

`VITE_WFG_API_MODE=static` (or `vite build --mode static`) builds the planner as a static site that
replays the committed precompute cache — `planner/cache/` (2025 의성·안동 and 영덕, 3 recorded input
times each, 9,722 route checks computed through the Route-Check API on the evaluated macOS host; see
`cache/INDEX.json`) — with no server and no API.
[`.github/workflows/planner-pages.yml`](../.github/workflows/planner-pages.yml) publishes it at
<https://sparkxt-0318.github.io/wildfireguardian/> **once the repository owner has enabled GitHub
Pages** (Settings → Pages → Source: GitHub Actions — a step to do before merging, see
[GitHub Pages](#github-pages-owner-before-merging) below); until then that address answers 404.

```bash
cd planner && npm ci
VITE_BASE_PATH=/wildfireguardian/ npm run build:static   # tsc + vite build --mode static + dist checks
npm run serve:static        # dist/ only, like GitHub Pages: http://127.0.0.1:4180/wildfireguardian/
npm run smoke:static        # headless Chromium smoke test against that dist-only server (see below)
```

(`npm run preview:static` also works; in static mode `vite preview` serves `dist/` only, without the
`/cache` middleware of the other modes.)

**What it shows and what it does not do**

- Everything is read from static files under the base path: `data/regions/**` (places, footprints),
  `data/forecast/**` (forecast cells, below), `basemap/**` (offline PMTiles, glyphs, sprites) and
  `cache/**` (INDEX.json + one file per region and input time, byte-identical to `planner/cache/`;
  the build checks every SHA-256 against `INDEX.json`). Only regions with recorded results are
  listed, and static builds leave out the basemaps of the other regions (울진, 밀양, 홍성).
- The API is never contacted. The client answers every API call with `STATIC_DEMO` without sending it,
  `src/config/sameOrigin.ts` refuses any request that would leave the page's origin or reach
  `…/api/…` (e.g. `http://127.0.0.1:8765`, `localhost`), and the built `index.html` carries a
  Content-Security-Policy (`connect-src 'self'` …) so the browser enforces the same. The VWorld
  raster and `VWORLD_API_KEY` are never part of a static build.
- Disabled, with a bilingual note and a link to [Real Route-Check API](#real-route-check-api), because
  they need live computation: "이 출발지 다시 계산" (recompute), comparison routes that are not in the
  cache, batches for scenarios without a cache, and checks of drawn spread zones (drawing and the
  recorded-footprint presets still work; every origin stays 미확인 · not computed, and the details
  say that the static demo cannot check drawn zones).
- The forecast-cell layer is on, with its usual labels (다음 1시간 신규 연소 확률 (예측 c651) · 입력 시각
  연소 중; MOCK only for MOCK data). `data/forecast/<region>__<input>.json` are the responses of
  `GET /v1/regions/{region}/forecast?input_time=…&only_nonzero=true` — the request the app makes —
  saved unchanged from the real Route-Check API by
  [`scripts/save_forecasts.py`](scripts/save_forecasts.py) for the six cached scenarios. That endpoint
  is a data read of the recorded c651 forecast export and packet (`api/forecast.py`; nothing is
  computed), and the script keeps a response only when its scenario set, checkpoint, graph and packet
  hashes (`constructed_arrays.npz`, `NATIVE_METADATA.json`) equal those recorded by the cached route
  checks of that scenario; it refuses the MOCK server, whose forecast fixtures differ.
  [`data/forecast/INDEX.json`](public/data/forecast/INDEX.json) records the request, the API identity
  (1.8.0, clean git commit, host), the blob ids of the serving code (the same files as the API commit
  that computed the cache), the input archive SHA-256 and each file's bytes, SHA-256 and checks;
  `build:static` re-checks the bytes and hashes. The app also refuses a file whose region, input time
  or scenario set differ from the scenario on screen.
- The honesty rules above all stay: fire-input banner, planning-aid footer, three verdicts as colour +
  icon + text, the "시험 데이터 · 평가 호스트 아님" marking for caches from another host (the committed
  cache is from the evaluated host, so it is not shown), MOCK only for MOCK-made data.
- A "DEMO · 2025년 3월 기록 시나리오 · 연구 프로토타입" chip (the period comes from `cache/INDEX.json`), a
  dismissible introduction with a 3-step tour (the urgency list → the 출발 마감 and evidence of the
  village or facility the user picks, else of the first one in the list with a checked route → the A4
  plan sheet; dismissal is remembered in `localStorage`), and "의견 보내기 / Feedback" →
  `VITE_FEEDBACK_URL` (default: the repository's
  [planner-feedback issue template](../.github/ISSUE_TEMPLATE/planner-feedback.md)). On a first visit
  the language follows the browser (Korean, else English); `?lang=ko|en` and the toggle still work.
  Keyboard: the introduction is a modal dialog (Tab stays inside, Escape closes it, the focus returns
  to the button that opened it); the tour card takes the focus at every step and Escape ends it.
- Every plan sheet carries "DEMO · 2025년 3월 기록 시나리오 재생 · 연구 프로토타입" / "DEMO · recorded
  March 2025 scenario replay · research prototype" in its A4 top margin, so printed and PDF sheets
  say what they are.
- Phones: below 900 px the list, map and details are one pane at a time (tab bar; a tap on a list row
  — also the selected one — opens its details), and the A4 plan sheet reflows into a readable column
  on screen (printing still produces A4). At ≤ 480 px the top bar keeps one row of controls above the
  fire-input banner and the DEMO ribbon is one line.

**Base path.** `VITE_BASE_PATH` sets Vite's `base`: `/` (default), `/wildfireguardian/` (GitHub Pages
project site) or `./` (relative: one build that works under any path). Code reaches its own files only
through `src/config/paths.ts` (`appPath`, `appUrl`, `fetchAppJson`). Any file added under
`planner/public/data/**` (e.g. generated `data/explanations/<region>__<input>.json`) is copied into the
build and served at `<base>data/…`; `fetchAppJson('data/…')` reads it (null when missing), and a
root-absolute `fetch('/data/…')` is moved under a sub-path base automatically.

<a id="github-pages-owner-before-merging"></a>**GitHub Pages (owner, before merging).** Settings → Pages
→ Build and deployment → Source: **GitHub Actions** — without it the deploy job fails and nothing is
published. After the merge, the push to `Main` (a change under `planner/`) or "Run workflow" on
"Planner static demo (GitHub Pages)" in the Actions tab builds and deploys; the site is live once that
run is green. The workflow runs `npm ci`, `npm test`, `npm run build:static` with
`VITE_BASE_PATH=/<repository>/` (override with the repository variable `PLANNER_BASE_PATH`, e.g. `/`
for a custom domain) and deploys `planner/dist` with `actions/upload-pages-artifact` +
`actions/deploy-pages`. Pull requests that touch `planner/` run the same install, tests and static
build without deploying.

**Any other static host (e.g. Vercel, Netlify, S3).** Build with the base the host serves the app
under (`VITE_BASE_PATH=/` for a site root, or `./` for any folder — the page URL must then end in `/`
or `index.html`) and upload the contents of
`planner/dist/` as they are — no server, rewrites or environment variables are needed (Vercel:
framework "Other", output directory `planner/dist`, or `vercel deploy planner/dist`). The host must
answer HTTP range requests for `*.pmtiles` (GitHub Pages does; check other hosts); without them the
basemap tiles do not load — the places, routes and results still do.

**Sizes** (`npm run build:static` prints them, in MiB): 1,077 files, 170.3 MiB (178.6 MB) — `cache/`
147.1 MiB (six JSON files of 22.2–25.7 MiB), `basemap/` 16.6 MiB (the two listed regions), `assets/`
5.1 MiB, `data/` 1.5 MiB (of which the forecast cells 0.9 MiB); every file < 100 MiB, total ≪ 1 GiB.
`planner/research-map/` and `planner/mock_api/` are not part of the build.

**Smoke test.** `npm run smoke:static` serves `dist/` the way GitHub Pages does
([`scripts/serve_static.mjs`](scripts/serve_static.mjs): only `dist/`, under `/wildfireguardian/`, a 404
for anything missing — no single-page-app fallback — and HTTP Range for the PMTiles) and drives
headless Chromium (the `playwright` package must be resolvable, e.g. a global install or
`PLAYWRIGHT_MODULE=/path/to/node_modules/playwright`; it never installs browsers; `--server vite` uses
`vite preview --mode static`, `--url` an already running server): desktop and 375 px, Korean and
English — intro (focus trap, Escape, focus back to the opener) → tour (step 2 shows the first village
or facility with a checked route) → its 출발 마감, evidence and forecast cells → A4 plan sheet with its
DEMO marker → English; on the phone also the one-line ribbon and a tap on the selected row. It records
every request (all must stay under the page's origin and base path), checks that the CSP refuses a
deliberate cross-origin probe, checks the honesty texts, and writes screenshots to
[`docs/screenshots/solve-demo/`](docs/screenshots/solve-demo/).

## Data flow

1. **Precompute cache** — when `/cache/INDEX.json` lists the selected region + scenario set, the
   app loads `/cache/<region>/<input>.json` (instant, offline) and labels it
   "사전 계산 결과 · <created_at KST> · <host>". Dispatch-plan attempts become per-origin sweeps,
   research `research_checks` become sweeps from the stored route checks, `travel_only` holds the
   comparison routes. The booth cache is produced only by `scripts/precompute_planner.sh` on the
   evaluation host; results computed elsewhere belong in `planner/.test-cache/` (view them with
   `WFG_CACHE_DIR=.test-cache npm run dev` on the command line — not as a permanent `.env` line) and
   are marked "시험 데이터 · 평가 호스트 아님" in the app. `precompute.py` itself refuses to write
   non-evaluation-host or MOCK results into `planner/cache`.
2. **Live API** — otherwise, when the API is reachable: OSM origins are grouped by their K nearest
   shelters into `POST /dispatch-plans` (≤ 200 origins, ≤ 20 destinations, ≤ 24 offsets,
   ≤ 4 800 attempts per plan, policy `full`, entry nodes as `{node_id}`), research origins run as
   single `POST /route-checks` with their recorded destination, dwell, window, incurred dose and
   limits; a progress bar shows "n / total 점검 완료" (refused or failed checks are counted
   separately as "거부·실패 n", never as done). Against the mock this starts at once (it answers
   from recordings in under a second); against the real API it starts only after "점검 시작" is
   pressed, because a region is hundreds of ~10 s checks on a shared API. The API has no cancel
   endpoint: "화면에서 중지" stops only this browser; submitted checks finish on the API, and
   "다시 시도" re-attaches to them (job ids are kept in memory, not across a reload).
   `VITE_WFG_ALLOW_BATCH=0` (or `npm run demo -- --no-batch`) never offers the batch.
3. **Neither** — the honest empty state "계산 결과 없음 — API 연결 또는 사전 계산 캐시가 필요합니다".

"이 출발지 다시 계산" re-runs ONE origin: one route check per departure offset per candidate shelter,
two at a time, coarse-to-fine so the timeline fills progressively, with the real `compute_s` of
every check. The forecast layer (`GET /regions/{id}/forecast?only_nonzero=true`) needs the API (the
static demo reads the saved responses in `data/forecast/`, see [Static demo](#static-demo-public-no-server)).

## 사용자 입력 확산 구역 (가정) — drawn spread zones

Fire input "확산 구역 직접 그리기 (가정)": the user draws or edits 산림청-style 5 h and 8 h spread-zone
polygons and the app sends them to the API as `fire_input {type: "spread_zones"}` (contract v1.5
`SpreadZonesFireInput`). Every screen then reads **사용자 입력 확산 구역 (가정)** (+ MOCK when applicable).

- **Settings (left panel)**: 기준 기록 시각 = one of the region's RECORDED input times (contract v1.1:
  it supplies grid, clock and currently burning cells; the hazard horizon is 1 h, so departures are
  checked over [0, 1 h) — 6 offsets at the 10 min step); 구역 예보 발표 시각 = input time − 0…8 h
  (`issued_at`; the 5 h / 8 h count from it, shown as "발표 후 T+h:mm"); 보수적 조기 점화 여유 =
  `margin_min` 0–120 (default 60). `burning_scenario_set_id` is the recorded set of the input time.
- **Editor (map, no extra dependency — `src/map/zoneEditor.ts`, toolbar `src/map/ZoneToolbar.tsx`)**:
  pick 5시간 / 8시간 구역 → 그리기 → click to add vertices; double-click, Enter or the first vertex
  closes; drag vertices; click a midpoint to insert; select + Delete/Backspace removes; Esc cancels;
  [ ] cycle vertices, arrows move one, Space adds a vertex at the centre crosshair, Ctrl/⌘+Z undoes;
  구역 지우기 per zone, 초기화 for both. Polygons are checked before anything is sent: ≥ 3 vertices,
  no crossing or overlapping edges (segment-intersection test; a hole touching its shell at one
  point is allowed), holes inside their shell, inside the region bbox (partly outside → warning,
  entirely outside → blocked, as the API answers 422 `ZONES_OUTSIDE_REGION`). Zones and settings
  are kept per region in `localStorage` (`wfg.planner.zones.<region>`), so a booth reload keeps them.
- **Preset "기록된 연소 범위로 시작"**: copies recorded burned footprints
  (`public/data/regions/<region>/footprints.geojson`, real data) — by default the footprint at the
  base time into the 5 h zone and the next later recorded footprint into the 8 h zone — reducing
  vertices with Douglas–Peucker (≈ 50 m, counts reported). Nothing is invented, buffered or scaled;
  the zones are labelled "가정 — 기록 연소 범위 복사 (YYYY-MM-DD HH:MM KST)".
- **Ready-Set-Go (산림청)**: planner-side point-in-polygon only — inside the 5 h zone
  "실행(Go) — 전원 대피", inside the 8 h zone "준비(Set) — 노약자·취약시설 우선 대피". In drawn mode
  the list puts origins inside zones first (Go before Set), then the urgency order; chip "구역 안".
- **Checks (never automatic)**: "선택한 출발지 계산" = one `POST /route-checks` per offset per K nearest
  shelter (entry nodes as `{node_id}`), 2 at a time, coarse-to-fine, real `compute_s`; "구역 안·주변 마을
  계산" = origins inside a zone or within 2 km, grouped into `POST /dispatch-plans` (policy full) after a
  confirm card ("약 N건 · 이 장비에서 수 분 이상 걸릴 수 있음" + the 30 s-budget bound). Drawn results
  replace the timeline and right panel in drawn mode only and are dropped when the zones or settings
  change; recorded results are kept and come back when switching back.
- **API 가정 (assumptions)**: the API's `RouteCheckResult.assumptions` / `DispatchPlanResult.assumptions`
  are shown verbatim (keys as sent, numbers via `String(n)`), with `provenance.approximation` as the
  warning line "근사 — 전문가 검토 필요" and a summary of the zones sent. The MOCK answers every
  spread_zones request with `unresolved` (`MOCK_SPREAD_ZONES_NOT_EVALUATED`) and says so — nothing is
  ever shown as checked.
- **Plan sheet / exports**: the drawn result is its own row labelled with the issue time (plus the
  recorded row of the same base time when it was loaded before switching); GeoJSON exports carry the
  zones as an extra polygon layer with `arrival_h_max` ("구역 GeoJSON" downloads them alone).

## Configuration (`.env`, see `.env.example`)

| Key | Default | Meaning |
|---|---|---|
| `VITE_WFG_API_MODE` | `mock` | `mock` → proxy `/api/v1` to the mock on `:8765`; `real` → to `VITE_WFG_API_TARGET`; `static` → no API, cache only ([Static demo](#static-demo-public-no-server); also `vite build --mode static`) |
| `VITE_WFG_API_TARGET` | `http://127.0.0.1:8765` | real API base (see [Real Route-Check API](#real-route-check-api)) |
| `VITE_BASE_PATH` | `/` | Vite `base`: `/wildfireguardian/` for GitHub Pages, `./` for a path-independent build |
| `VITE_FEEDBACK_URL` | static: the planner-feedback issue template | "의견 보내기 / Feedback" link (https only); outside the static demo the button shows only when set |
| `VITE_REPO_URL` | `https://github.com/Sparkxt-0318/wildfireguardian` | repository link used by the static demo's "how to run it locally" note |
| `VITE_DEPARTURE_STEP_MIN` | `10` | departure offset step (5/10/15/20/30 min) over `[0, horizon)` |
| `VITE_SHELTERS_PER_ORIGIN` | `3` | K nearest shelters per origin with distinct entry nodes (1–5) |
| `VITE_WFG_ALLOW_BATCH` | `1` | `0`: never offer "점검 시작" for a scenario without a cache (real API) |
| `VWORLD_API_KEY` | empty | optional VWorld raster background (internet; off unless toggled) |
| `WFG_CACHE_DIR` | `cache` | server-side: folder served at `/cache/**` and copied into `dist/cache` (the build warns when it is not the booth cache) |

The browser always calls same-origin `/api/v1/*`; `vite dev` and `vite preview` proxy it, and
both serve the cache folder at `<base>cache/**` (its `.state/` working folder is never served). In
static mode there is no proxy and no API call at all, and `vite preview` serves `dist/` only (the
build's verified copy in `dist/cache`).

## Source layout

```
src/
  api/wire.ts         contract v1.5 wire types (only the adapter reads them)
  api/client.ts       fetch + timeouts + polling + abort; ApiError(code, message); static: never sends
  api/adapter.ts      wire ⇄ internal model; request builders (the only module that knows the wire)
  api/cache.ts        <base>cache/INDEX.json + cache files → internal model
  config/             env (API mode incl. static), paths (base-path URLs), sameOrigin (static fetch guard)
  domain/             internal model, planning rules (plan.ts), clock (KST), banner/MOCK rules
  data/staticData.ts  <base>data/regions/index.json, places.geojson (+ optional temporary housing)
  state/              zustand store, controller (data flow), selectors, feature-module inputs
  map/                MapLibre view, offline basemap style (local PMTiles, Korean labels)
  components/         top bar, left list, right panel, timeline, time slider, icons, MobileNav (phones)
  components/demo/    static demo: DEMO ribbon, intro + tour, feedback link, "nothing computed" notes
  styles/mobile.css   ≤ 900 px layout (one pane at a time; plan sheet reflow on screen)
  i18n/               Korean-first strings with English mirror; useT()
  features/           About, plan sheet (A4/PDF), exports — feature builder (see its README)
```

## Scripts

| Command | |
|---|---|
| `npm run dev` / `npm run preview` | app with the API proxy and `/cache` |
| `npm run build` | `tsc -b` (app, config and tests) + production build (copies the cache into `dist/cache`) |
| `npm run build:static` / `npm run preview:static` | static demo build (+ `scripts/check_static_dist.mjs`: sizes, CSP, cache and forecast SHA-256, basemaps) / its preview (dist only) |
| `npm run serve:static` | `dist/` only, like GitHub Pages (`scripts/serve_static.mjs`) |
| `npm run smoke:static` | Playwright smoke test of the static demo (`scripts/static_smoke.mjs`) |
| `python3 scripts/save_forecasts.py --api http://127.0.0.1:8765` | saves the forecast cells of every cached scenario from a running real API into `public/data/forecast/` |
| `npm test` | Vitest: `tests/planner/*.test.ts` |
| `npm run mock` | the MOCK server |
| `npm run demo` | booth launcher (`scripts/demo.mjs`) |

## Limitations (also in the About panel)

- Recorded scenarios cover one hour after each recorded input time (0–3 600 s); departures are
  checked at the configured step only. Times between offsets are not checked.
- The checked route covers driving, waiting and the 120 s shelter stay; travel between an OSM point
  and its road entry node, and waiting at the origin before departure, are not modelled.
- `model_no_route` is a statement about this model and input scope, not proof that escape is
  impossible; `unresolved` is "cannot judge", never safe.
- Drawn spread zones (산림청 5 h / 8 h) are a user assumption converted by the API into 4 scenarios —
  an approximation that needs expert review; only the first hour after the base recorded time is
  represented, and zone cells outside the region window are not modelled.
