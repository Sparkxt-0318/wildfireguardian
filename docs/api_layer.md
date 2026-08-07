# PHASE 22 STEP 0 — the API layer

Round-3 PHASE 22, STEP 0. Written 2026-08-07.

`src/wildfireguardian/api/` · `scripts/run_api.py` · `tests/test_api.py` (34 tests)

> ⚠ **No screen was built.** STEP 0 is the transport only. What exists to look at
> is still `demo/operator_screen.html` (PHASE 8, replay-only).

---

## 0. What it is

Four endpoints over the PHASE-19 job model, plus static file serving for the
vendored fonts. The layer is thin on purpose — parse, call a service function,
serialise, choose a status code — because PHASE 19 was built so that it could
be.

| | |
|---|---|
| `GET /api/health` | start-up cost, preloaded regions, cache and runner stats |
| `GET /api/regions` | every registered region and whether its hazard field is on disk |
| `GET /api/regions/{region}/gate?lat=&lon=` | is this coordinate servable — verdict as data |
| `GET /api/regions/{region}/locate?x=&y=` | EPSG:5179 metres → degrees **and** the gate verdict, one round trip (§1.9) |
| `POST /api/regions/{region}/photo-gps` | a reported photograph's raw bytes → its EXIF GPS **and** the same gate verdict. Nothing is stored, only four EXIF tags are read, and the filename never leaves the browser. [`photo_exif.md`](photo_exif.md) |
| `POST /api/jobs` | submit an ignition point → **202** + job id |
| `GET /api/jobs/{id}` | state + the six-stage progress |
| `GET /api/jobs/{id}/result` | the dispatch list |
| `DELETE /api/jobs/{id}` | cancel, queued or running |
| **`GET /`** | **the operator console** — `web/console.html` |
| `/*` | `web/`, including `assets/fonts/` |

---

## 1. Measured

Server started with `scripts/run_api.py --port 8137`, driven with `curl`.

### 1.1 Start-up and memory

| | |
|---|---:|
| start-up (three regions preloaded) | **5.18 s** |
| regions resident | **3 / 3** |
| hazard fields, exact | 1.14 MiB |
| **process peak RSS after preload** | **522.66 MiB** |

Peak RSS is `getrusage(RUSAGE_SELF)`, read from inside the process by
`/api/health` — the same measurement `measure_service_layer.py` uses. PHASE 19
measured the same three regions at 462–489 MiB in a bare process, so **the
transport costs roughly 35–60 MiB** on top. `/usr/bin/time -l` was also wrapped
around the server but produced nothing: the process was stopped with SIGTERM and
never printed its summary. The in-process figure is the one to quote.

### 1.2 The full flow

| step | |
|---|---:|
| `POST /api/jobs` | **HTTP 202 in 6.1 ms** |
| routing (`route_s`) | 11.573 s |
| `warm_total_s` | 11.618 s |
| `GET /api/jobs/{id}/result` | HTTP 200 in 5.0 ms |
| submit → result, wall clock | 12.85 s |
| resources were cached | **true** |

⚠ The 12.85 s includes the poll interval of the verification script (1.2 s), so
it is an upper bound on the flow rather than a measurement of the work. The work
is `warm_total_s` = 11.618 s, consistent with PHASE 20's 10.9–11.1 s.

**Submit does not block: 6.1 ms.** That is the number the asynchronous design
exists to produce.

### 1.3 The answer is the committed one

```
counts    : 414 both_safe · 42 naive_into_FA_safe · 2 no_safe_route · 0 others
n_scanned : 458 · villages 29 · actionable points 44
```

The bucket fingerprint over all 458 origins is `f652bf1c0d349256…`, **identical
to the value PHASE 20 measured directly through the service layer**. The
transport changes no number, and that is checked by a digest rather than
asserted.

### 1.4 Progress, as an operator sees it

Ten polls over one request:

```
running   11.8%  자원 적재 — … — 생략 (이미 적재됨 (사전 적재 캐시 적중))
running   21.8%  경로 산출 — 출발지별 대피소 탐색  53/458 출발지 · 대피소 46곳 탐색
running   45.3%  경로 산출 — 출발지별 대피소 탐색 177/458 출발지 · 대피소 46곳 탐색
running   80.1%  경로 산출 — 출발지별 대피소 탐색 361/458 출발지 · 대피소 46곳 탐색
running   98.8%  마을 군집화 44/44 지점
succeeded 100.0% 기록 작성 — RUN.json·viz.json 2/2 파일
```

The load stage reports **생략**, not 0 %, because the cache was warm — a warm
request did not pay that cost and the bar says so.

### 1.5 Two requests at once

| | |
|---|---|
| both completed | 23.3 s |
| counts identical | **yes** |
| bucket fingerprint identical | **yes** — and equal to the single-request run |
| `determinism_key` identical | **yes** |
| run directories separate | **yes** |

⚠ 23.3 s ≈ 2 × 11.6 s because **the runner has one worker**, so the two were
serialised by the queue rather than run together. That is deliberate (§2), and
it means this measures *correctness under concurrent submission*, not parallel
throughput — there is none to measure.

### 1.6 Cancel

| | |
|---|---|
| cancelled at | `경로 산출 … 175/458 출발지` |
| `DELETE` | HTTP 200, `cancel_accepted: true` |
| **time to stop** | **0.26 s** |
| final state | `cancelled`, `nothing_was_written: true` |
| result afterwards | **409**, not 404 — the job exists and has no result |

### 1.7 The offline gate on responses

Every endpoint, scanned with the same rule the static gate uses:

| response | bytes | external URLs |
|---|---:|---:|
| `/api/health` | 2,378 | **0** |
| `/api/regions` | 561 | **0** |
| `/api/regions/{r}/gate` | 162 | **0** |
| `/api/jobs/{id}` | 2,195 | **0** |
| `/api/jobs/{id}/result` | 58,062 | **0** |
| `/openapi.json` | 4,808 | **0** |

### 1.8 Static files

`assets/fonts/IBMPlexSansKR-Regular.woff2` 219,492 B ·
`IBMPlexMono-Regular.woff2` 14,708 B · `Pretendard-arrow.subset.woff2` 1,312 B ·
`LICENSE-IBMPlex.txt` 4,456 B — all HTTP 200, `font/woff2`.

---

## 1.9 Map-click ignition (STEP 1 ⓐ)

`GET /api/regions/{region}/locate?x=&y=` takes EPSG:5179 metres and returns
WGS84 degrees **and** the gate verdict, in one round trip.

⚠ **The geodesy is server-side, and that is the design rather than a
convenience.** The page turns a click into viewBox coordinates (a matrix it
already holds) and then into projected metres (arithmetic on the grid extent it
was handed at build time). It stops there. Metres to degrees is a *projection*,
and doing it in JavaScript would mean vendoring a projection library and
trusting it to agree with the pyproj transformer that produced every committed
coordinate in this repository. One transformer cannot disagree with itself.

**Round-trip accuracy, measured** — known lon/lat → 5179 → viewBox → 5179 →
lon/lat, where the middle two steps are exactly the arithmetic the page does:

| probe | error |
|---|---:|
| PHASE-12 manual-trigger coordinate | **0.000 mm** |
| hazard-field t=0 core | **0.000 mm** |
| walk-bbox SW / NE corners | **0.000 mm** |
| grid centre | **0.000 mm** |

The viewBox step is lossless. Through the live endpoint the error is **≤ 0.54
cm**, and all of it is the two-decimal metre the console puts in the query
string. Both are far below the things that actually bound a click: one viewBox
pixel is **78.0 m**, and the hazard grid's own cell is **500 m**.

**Refusal is explicit, and the sentence is the service's.** A click outside the
registered walk bbox draws a red crosshair, disables the run button, and shows
`check_in_region`'s own Korean sentence — with `위험면 격자 밖입니다.` prefixed
when the click is outside the hazard grid entirely. Verified in a browser: a
click at 35.2834 N, 129.2587 E produced exactly that.

⚠ A click that did nothing visible would read as a broken screen, which is worse
than a refusal. Nothing is silently ignored.

**The constraint is on screen permanently**, not only after a click:

> ⚠ 위험면은 yeongdeok_2025의 사전 계산 결과이며 클릭 좌표로 재생성되지
> 않습니다. 클릭은 라우팅 출발점만 바꿉니다.

A click moves where the routing *starts*. It does not move the hazard surface,
which was simulated once for one fire and is held fixed because ERA5 publishes
on a ~5-day lag. Leaving that implicit invites "the prediction starts where I
clicked", which is not what happens. `#fde047` on `#1a1206` measures 14.06:1 —
it is a warning and is meant to be read.

**Verified end to end in a browser**, not asserted: click at 36.4907 N,
129.2856 E → 「이 지점에서 라이브 계산」 → progress → 「완료 · 458개 출발지」,
라우팅 11.751 s, badge flipped to 라이브 계산 결과.

## 1.10 ⚠ `GET /` returned 404, and the start-up message said otherwise

Reported from a running server and reproduced. Three findings, all fixed.

**1. The root URL was not the console.** `StaticFiles(directory=web, html=True)`
serves `index.html` for a directory request; `web/` has no `index.html`. So
`GET /` returned `{"detail":"Not Found"}` while `/console.html` returned 200.
For a demonstration that is the difference between "open localhost" and reading
a path aloud to a judge.

There is now an explicit `@app.get("/")` returning `web/console.html`. Naming the
file rather than renaming it to `index.html` keeps the filename meaningful and
puts the mapping where a reader can see it. If the console has not been built,
the route answers **503** with the build command — an unbuilt page is a different
problem from a missing route, and saying which saves the search.

**2. The start-up message was false.** It printed
「…http://127.0.0.1:8000 에서 응답합니다」 for an address that 404'd. It now names
the URL that is served, and a test pins both halves: the script must interpolate
the root URL, and the app must have a `/` route.

**3. The build template was publicly served.** `web/console.template.html`
returned **HTTP 200**, placeholder and all — a browser reaching it runs
`JSON.parse` on `/*__DATA__*/` and renders a blank console. It has moved to
`scripts/`, because **everything under `web/` is public** and a template is a
build input. A test asserts no HTML under `web/` contains a placeholder.

⚠ **A note on how this was verified, because the first two attempts lied.**
`curl` kept reporting 404 after the fix. The cause was not the code: a stale
server from before the edit still held port 8000, so the freshly started process
died with `[Errno 48] address already in use` and every request went to the old
one. The failure was silent because the bind error went to a log nobody read.
The fix was confirmed only after killing the holder **by pid** and checking the
port was free first. `TestClient` had been reporting 200 the whole time — when a
live check and an in-process check disagree, suspect the process before the code.

### Verified, on port 8000

| | |
|---|---|
| `GET /` | **HTTP 200**, 66,696 B, `text/html`, `<title>WildfireGuardian · 운영자 콘솔</title>` |
| `GET /` vs `/console.html` | identical bytes |
| `GET /console.template.html` | **404** |
| `GET /assets/fonts/…woff2` | 200, `font/woff2` |
| browser at `http://127.0.0.1:8000/` | console renders |
| click → live calculation | 36.4907 N, 129.2856 E → 「완료 · 458개 출발지」, 라우팅 11.693 s |
| gates | offline 0 · dash 0 · contrast 0 |

---

## 1.11 ⚠ 「라이브 계산 실행」 was refused every time, and the screen said only 422

Reported from the browser 2026-08-07 and reproduced. **The refusal was correct.
The screen was not.** Two faults, both fixed.

### What was actually happening

`build_console.py` set the console's unclicked start to the hazard field's t=0
core — deliberately, so that "an unclicked run is about THIS fire". For
`yeongdeok_2025` that coordinate is **36.4663 N, 129.2224 E**, and the region's
registered walk bbox starts at **129.25 E**. The core is therefore **2,472 m
west of the bbox** (geodesic, to the nearest point on it; measured by
`_default_start`, not estimated). So `POST /api/jobs` gated it, correctly, and
returned **422** — every time, for anyone who pressed the button without first
clicking the map.

| path | before | verdict |
|---|---|---|
| press with **no click** | **HTTP 422**, screen shows 「제출 거절 (HTTP 422)」 | **defect** |
| click inside the walk bbox, then press | runs, 「완료 · 458개 출발지」 | correct |
| click **outside the hazard grid** | red banner, full sentence, button disabled | correct |
| click inside grid, outside walk bbox | red banner, full sentence, button disabled | correct |
| queue | 3 concurrent submits all **202**; capacity 32, depth 2 | not involved |

⚠ **The queue was never the cause** and neither was a zombie process; both were
checked before the code was. The port was cleared by pid first, per §1.10.

### Fault 1 — the screen offered a run the server was certain to refuse

The button was enabled at page load, and the map drew the ◎ ignition marker
**outside** the dashed walk-bbox rectangle, which is exactly what an operator
reads as "the fire is here, compute it".

Fixed by asking the gate at BUILD time. `build_console.py` now calls the service's
own `check_in_region` — the same function `POST /api/jobs` refuses on, never a
second copy of the bbox test — and emits `default_start` = `{latlon, servable,
reason_ko, offset_m, note_ko}`. When `servable` is false the console starts with
the button **disabled and relabelled** 「지도를 클릭해 발화점 지정」, and says why
before anything is pressed.

⚠ **The unservable default was NOT replaced with a servable one.** Substituting
a coordinate inside the bbox would make the demonstration run from a point that
is not where the fire was, which is the manufactured evidence
`check_in_region`'s own sentence exists to prevent. The screen keeps showing the
real core and explains that it cannot be routed from — that IS the 32.6 %
coverage limitation, made visible at the moment it bites.

### Fault 2 — a justified refusal that an operator could not act on

The API already answers with the Korean sentence `service.params.check_in_region`
owns (§2, "A refusal carries the service's own Korean sentence"). The console
threw it away and printed the status code. **A refusal nobody can read is a
defect even when the refusal is right.**

`serverReason()` now unwraps FastAPI's `detail` in all three shapes it arrives
in — a string (this app's refusals), an object (409), an array of validation
items (pydantic) — so none can reach the screen as `[object Object]`. Every
branch that prints a status code shows the sentence beside it: submit, status
poll, result fetch, and the map-click locate.

The banner gained an `info` variant (`#bfdbfe` on `#1e3a5f`, **8.10:1**, the
badge pair already measured) with `role="status"`. A standing precondition is
not an error the operator just caused and must not wear its colours, or
interrupt like one.

### Verified, in the browser

| | |
|---|---|
| unclicked press | button disabled; blue note names the 2,472 m and what to do |
| click 36.4498 N, 129.3996 E → press | 「완료 · 458개 출발지」, 라우팅 12.316 s |
| forced refusal on the submit path | red banner carries the full bbox sentence |
| 1920×1080 · 1600×900 · 1366×768 | document scroll **0 × 0** at all three |
| gates | offline 0 · dash 0 · contrast 0; suite 909 passed, 4 skipped |

⚠ **Why it survived STEP 1's verification.** The row in §1.9 reads
「click → live calculation」. The click path was exercised and passed; the path
with **no** click never was, and it is the one a first-time user takes. Four new
tests in `tests/test_screen_checks.py` pin both faults, and each was shown to
FAIL against an injected regression before being accepted.

### Still open, found while verifying (NOT introduced here, NOT fixed)

At **1366×768** the dispatch table is 548 px wide inside a 519 px pane, so
**29 px of the 구분 column is cut off** — `#tablewrap` is `overflow:hidden`, so it
is clipped silently rather than scrolled. Measured identical on `HEAD`'s
committed `console.html`, so it predates this fix. Document scroll is still 0;
the loss is inside the pane. It belongs with the multi-region screen work.

---

## 1.12 ⚠ The console's build input can vanish, and a rebuild then regresses the badge silently

Found while fixing §1.11, and it nearly happened: **the replay run the committed
console was built from was not on disk.**

### What the tree actually held, 2026-08-07

| | |
|---|---|
| `console.html` says it was built from | `20260807T015743Z`, warm **11.467 s** |
| that run, on disk | **absent** |
| newest `yeongdeok_2025` replay run present | `20260803T051744Z`, warm **29.051 s** |
| next newest | `20260803T051600Z`, warm **25.369 s** |

`build_console.newest_run()` takes the newest run it can *find*. So running the
documented rebuild command that day would have produced a console whose badge
read **29.051 s** — a pre-PHASE-20 figure — with no error, no warning, and no
diff anywhere except the one number a presenter says aloud. PHASE 20's measured
gain would have been quietly undone on the screen that demonstrates it.

It was caught only because §1.11's fix required a rebuild and the run IDs were
compared by hand first. Nothing in the tooling would have said anything.

### Two facts behind it

**① The build input is not committed — except that it is.**
`build_console.py`'s own docstring says a replay run is "~1 MiB of per-village
output and is not worth committing". The repository disagrees with it: the
`20260803T…` runs under `outputs/live/replay/` **are tracked**, 122 files each.
So the practice is to commit them and the documentation says not to, which is
exactly the gap a run fell through.

**② The ID is already recorded; nothing verifies it.**
The payload carries `precomputed.run_id`, so the console has always known which
run produced it. What is missing is any step that reads that field back. The
provenance is written and never checked, which looks identical to provenance
that was never written until somebody looks.

### Proposed, NOT implemented

Recorded here for a decision, deliberately left unbuilt:

1. **Make `build_console.py` refuse a silent downgrade.** It already knows the
   outgoing `run_id` and warm figure; before overwriting, read the EXISTING
   `web/console.html`'s payload and compare. If the run about to be used is
   older than the one already shipped, or its warm figure is worse, **stop with
   a message naming both** and require an explicit `--allow-older` to proceed.
   A rebuild that makes the demonstration slower should be a decision, not a
   default.
2. **Make the absence loud.** If `precomputed.run_id` of the shipped console has
   no directory under `outputs/live/replay/`, say so — at build time, and in a
   test. The console's provenance is either checkable or it is decoration.
3. **Settle ① either way.** Commit the run that built the shipped console (and
   correct the docstring), or stop committing runs (and say where the shipped
   console's input lives instead). The current split is what let a run
   disappear without anyone noticing.

⚠ **Interim, done now rather than proposed:** the run this console was rebuilt
from, `20260807T022854Z` (warm **10.385 s**), **is committed with it**, matching
what the tree already does for the `20260803T…` runs. That does not fix the
mechanism; it just means the shipped console's provenance is present today.

---

## 2. Decisions, and why

**One worker.** Threads do not make two scans faster: the routing is
pure-Python Dijkstra and the GIL serialises it, measured in PHASE 19 at roughly
double the single-job time each. A second worker only makes the second request
*start* sooner while both finish later. For one person clicking one coordinate,
one worker is honest; the bounded queue is what absorbs a double-click, and it
returns **429** rather than accepting work it cannot do.

> ⚠ **The consequence, stated plainly so nobody reads §1.5 as a throughput
> figure:** 동시 2요청은 23 s 이며 이는 큐 직렬화의 결과입니다. 병렬 처리량은
> 측정 대상이 아니며, 이 콘솔은 단일 운영자를 전제합니다.
>
> Two simultaneous requests take about twice one request, because the second
> waits in the queue. That is the design, not a limit that was hit. If a future
> deployment genuinely needs concurrent operators, the answer is processes, not
> threads — and it is a decision with a memory bill (each process carries its own
> ~500 MiB resource cache), deliberately **not** taken here: a demonstration has
> one person at one machine, so there is no concurrent load to optimise for.

**Routing parameters are not settable over HTTP.** `p_cut`, the budget, the
stride, the slope sampling all come from `config/default.yaml` through
`RoutingParams.from_config`. A dispatch list produced with a stride somebody
typed into a URL is not comparable with anything this project has published, and
a test asserts the request model cannot carry them.

**A refusal carries the service's own Korean sentence.** `POST /api/jobs` with a
coordinate outside the walk bbox returns 422 with the wording
`service.params.check_in_region` already owns. The transport does not compose
operator wording; there is one copy of that sentence.

**Status codes chosen so a poller knows what to do.** Result-before-completion is
**409**, not 404: 404 would tell a client to stop, and the right action is to
poll again. Unknown region is 404, unknown job is 404, malformed coordinate is
422 from validation.

**`/docs` and `/redoc` are disabled** because FastAPI serves Swagger UI and ReDoc
from jsDelivr. `/openapi.json` stays: it was **measured** to contain no external
URL, and it is how someone explores this API with curl and no screen.

**Bound to localhost.** This serves an operator console for one machine in one
room. A wider bind would put an unauthenticated dispatch generator on whatever
network the hall provides.

---

## 3. The dependency, and what it cost

`fastapi==0.141.1`, `uvicorn==0.52.1`, `httpx==0.28.1` added to
`requirements.txt`. Installed with **pip, not conda-forge** — these are pure
Python and pull no binary GDAL/GEOS/PROJ, so the reason the rest of that file
insists on conda does not apply.

⚠ `pip install --dry-run` was run **first**: 12 new packages, **zero upgrades**,
every existing pin untouched. That mattered, because `make env-check` compares
the environment against those pins and this project has already been bitten once
by an environment that did not match its declaration.

Transitives (starlette, pydantic, h11, anyio, httpcore, …) are deliberately
**not** pinned: pinning a transitive states a compatibility claim this project
has not tested, and `env-check` would then fail on a resolver's legitimate
choice.

⚠ `env-check` only verifies **declared → installed**, not the reverse. Installing
without pinning would have left the gate green and the environment undocumented
— the same shape as the Round-2 failure that file exists to prevent. Hence the
pins.

---

## 4. What STEP 0 did not do

1. **No screen.** Out of scope, by instruction.
2. **No authentication, no rate limit beyond the queue bound.** Localhost only.
3. **The job store is in memory.** A restart forgets every job id; the run
   directories survive. Fine for a console in the same process, wrong for
   anything that must outlive a restart.
4. **`demo/wildfire_demo.html` was not touched**, and is still on the
   pre-canonical lineage — `HANDOFF_ROUND3.md` §4. Do not demonstrate from it.
5. **No parallelism decision.** PHASE 19 deferred process-level parallelism until
   a transport existed and the real concurrency was known. It now exists; the
   measurement in §1.5 is the input to that decision, and the decision has not
   been made.

---

## 5. Checks

| | |
|---|---|
| `pytest` | **886 passed, 4 skipped, 0 failed** (852 → +34) |
| `make verify` | PASSED — 136/136 registry, no forbidden strings |
| `make env-check` | OK — environment matches `requirements.txt` |
| `make baseline-verify` | 63 artifacts intact |
| committed artifacts | unchanged |
| verification residue | removed (`git clean` on four untracked run dirs) |
