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

The real API is **not part of this branch's tree**: it lives on branch `feat/api` (repository-root
`Makefile` and `api/`, contract v1.5.0, commit `bb2acd0`). `make api` therefore exists only in a
checkout where that branch is merged or checked out.

- If the repository root has a `Makefile` with an `api` target, run `make api` there.
- Otherwise use a separate worktree:

  ```bash
  git fetch origin feat/api
  git worktree add --detach ../wfg-api origin/feat/api
  (cd ../wfg-api && make api)
  ```

- Prerequisites: Python 3.12, GNU `time` (`/usr/bin/time`) and `procps` (`/bin/ps`); `make api`
  creates its `.venv` and fetches the recorded inputs on first use.
- It serves `http://127.0.0.1:8765/v1` — the same port as the mock, so stop the mock first.
- Then, from this planner checkout: `planner/scripts/precompute_planner.sh` (booth cache) or
  `npm run demo -- --mode real`. The precompute script talks to the API over HTTP only, so the two
  checkouts may be separate.
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
every check. The forecast layer (`GET /regions/{id}/forecast?only_nonzero=true`) needs the API.

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
| `VITE_WFG_API_MODE` | `mock` | `mock` → proxy `/api/v1` to the mock on `:8765`; `real` → to `VITE_WFG_API_TARGET` |
| `VITE_WFG_API_TARGET` | `http://127.0.0.1:8765` | real API base (see [Real Route-Check API](#real-route-check-api)) |
| `VITE_DEPARTURE_STEP_MIN` | `10` | departure offset step (5/10/15/20/30 min) over `[0, horizon)` |
| `VITE_SHELTERS_PER_ORIGIN` | `3` | K nearest shelters per origin with distinct entry nodes (1–5) |
| `VITE_WFG_ALLOW_BATCH` | `1` | `0`: never offer "점검 시작" for a scenario without a cache (real API) |
| `VWORLD_API_KEY` | empty | optional VWorld raster background (internet; off unless toggled) |
| `WFG_CACHE_DIR` | `cache` | server-side: folder served at `/cache/**` and copied into `dist/cache` (the build warns when it is not the booth cache) |

The browser always calls same-origin `/api/v1/*`; `vite dev` and `vite preview` proxy it, and
both serve the cache folder at `/cache/**` (its `.state/` working folder is never served).

## Source layout

```
src/
  api/wire.ts         contract v1.5 wire types (only the adapter reads them)
  api/client.ts       fetch + timeouts + polling + abort; ApiError(code, message)
  api/adapter.ts      wire ⇄ internal model; request builders (the only module that knows the wire)
  api/cache.ts        /cache/INDEX.json + cache files → internal model
  domain/             internal model, planning rules (plan.ts), clock (KST), banner/MOCK rules
  data/staticData.ts  /data/regions/index.json, places.geojson (+ optional temporary housing)
  state/              zustand store, controller (data flow), selectors, feature-module inputs
  map/                MapLibre view, offline basemap style (local PMTiles, Korean labels)
  components/         top bar, left list, right panel, timeline, time slider, icons
  i18n/               Korean-first strings with English mirror; useT()
  features/           About, plan sheet (A4/PDF), exports — feature builder (see its README)
```

## Scripts

| Command | |
|---|---|
| `npm run dev` / `npm run preview` | app with the API proxy and `/cache` |
| `npm run build` | `tsc -b` (app, config and tests) + production build (copies the cache into `dist/cache`) |
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
