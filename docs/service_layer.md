# PHASE 19 — the service layer, and PHASE 20 — the one safe optimisation

Round-3. Written 2026-08-06.

`src/wildfireguardian/service/` (6 modules) · `scripts/measure_service_layer.py` ·
`tests/test_service_layer.py`

| PHASE / STEP | scope | state |
|---|---|---|
| 19 · 0 | investigate the entry points, the concurrency hazards and the 26.9 s | done, reported |
| 19 · 1 | extract the service functions, the resource cache, progress, the job model, the guards | done — §2–§4, regression in §6 |
| 19 · 2 | cancellation of a running scan, progress detail, and the seed record | done — §3.1, §3.2, §4.4.1 |
| **20** | **hoist the per-origin hazard table** — the one result-invariant optimisation the profile found | done — §5.1–§5.3 |
| 21? | a transport, and then the parallelism question | not started — §6.5 |

> ⚠ **There is no web server in this PHASE, and that is the point of it.** No
> HTTP, no framework, no port, no route table. The computation was separated
> from the scripts, made safe to call twice at once, given a job model and a
> progress report, and left exactly one layer short of a transport. A transport
> written on top of an unproven service layer would have two things to debug at
> once. `tests/test_service_layer.py` asserts the package imports no web
> framework, so this stays true by accident of nobody rather than by memory.

---

## 0. What the operator screen could not do, and why this exists

[`operator_screen.md`](operator_screen.md) describes a screen that **replays**.
Everything on it — the counts, the rows, the two routes, the timings — was
computed by `run_live_detection.py` beforehand and inlined at build time. The
page has no solver, by design and by test.

That is the right thing for a demonstration and the wrong thing for October.
A judge who asks *"what if the fire started here instead?"* needs a coordinate
to go in and a dispatch list to come out, and before PHASE 19 the only way to
answer was to run a script from a terminal in a working directory, which is not
a thing that happens during a four-minute talk.

Between that script and a web page sit six problems. This PHASE is those six.

---

## 1. What STEP 0 found

The measurements below are STEP 0's; they are what every design decision here
was made against.

### 1.1 Where the 26.9 seconds go

| stage | seconds | share |
|---|---:|---:|
| **routing total** | **26.9** | |
| load hazard field + walk graph + refuge POIs | 3.6 | once per process |
| cluster + render three formats × 29 villages | 0.06 | |
| A4 PDF, 29 sheets | +79 | *after* the list exists |

⚠ **STEP 0's split of the 26.9 s between the two routers was wrong** and has
been retracted — it attributed ~78 % to the shelter search. The measured split
is in **§5.1**, and it is roughly one third `naive_route` to two thirds
`future_aware_route`. The 26.9 s total, the 3.6 s load and the delivery figures
are unaffected; only the attribution inside the routing line was wrong.

⚠ **Re-measured during STEP 1, the same stages came out lower** — routing
22.1–25.4 s and loading 1.7–2.7 s across ten runs on the same machine. Nothing
in the code that computes them changed; what changed is the machine's state.
The snapshot graphml, the DEM and the POI GeoJSON had been read dozens of times
by then, so the OS page cache was hot, and the load stage in particular is a
measurement of a different situation. **Quote STEP 0's figures for the cold
case** — an operator's first request of the day is the cold one — and treat the
STEP-1 figures as the warm-machine floor.

Two consequences, and they point in opposite directions:

* **The 3.6 s is removable and small.** Pre-loading takes a cold request from
  ~30.5 s to ~26.9 s. Worth doing — not because 12 % is a lot, but because a
  service that re-parses an unchanged graph on every request pays that tax
  forever while the answer never changes.
* **The 26.9 s is large and is NOT touched here.** ⚠ See §5.

### 1.2 The four concurrency defects

| # | defect | what it does under two requests | fixed by |
|---|---|---|---|
| 1 | `run_id` is `%Y%m%dT%H%M%SZ` — **one-second resolution** | two requests in the same second share one output directory and overwrite each other's sheets | `service.routing.make_run_id`, §4.3 |
| 2 | `osmnx.settings` is a process-wide namespace | a request that edits it changes how every *other* request loads its graph, silently and after the fact | `service.guards`, §4.4 |
| 3 | numpy's **global** RNG is seeded inside seven functions under `scripts/spread_v2/` | a request path that ever reached one would move the stream under every later request | `service.guards`, §4.4 |
| 4 | `Resources` is loaded per process and never shared | two requests each hold their own walk graph, doubling peak memory to buy nothing | `service.resources`, §4.2 |

⚠ **Defects 2 and 3 are latent, not observed.** Nothing in the tree writes
`osmnx.settings`, and no service function touches the global RNG — measured, in
§4.4.1. That is precisely why guarding them now is cheap: a digest per job, and
the failure it prevents is invisible on the day it happens. Do not restate
either as something that *was* going wrong.

---

## 2. The six modules

| module | what it owns |
|---|---|
| `params.py` | the frozen parameter set of one request; defaults lifted **field-for-field** from the scripts' argparse defaults; the region gate as *data* |
| `guards.py` | osmnx settings and numpy's global RNG, frozen at start-up, asserted unchanged around every job |
| `progress.py` | the stage plan and a thread-safe progress reporter — `경로 산출 137/458` |
| `resources.py` | the walk graph, hazard field and refuge POIs: loaded once per region, shared read-only |
| `routing.py` | the service functions — arguments in, serialisable results out, no `print`, no `sys.exit` |
| `jobs.py` | submit → job id → poll status → read result → cancel, on a bounded queue |

### The scripts were not deleted; they became the console

`scripts/run_live_detection.run_trigger` is now a printing wrapper around
`service.routing.run_trigger_core`. The FIRMS, replay and manual paths all reach
it through that wrapper, so **"the three triggers run the same code" is a
property of one function** rather than an agreement between three — which is what
[`manual_trigger.md`](manual_trigger.md) already claimed and now enforces one
level deeper.

`tests/test_service_layer.py::test_run_trigger_delegates_to_the_service_instead_of_inlining_it`
fails if `pipeline.route_region`, `pipeline.deliver`, `pipeline.write_viz` or
`pipeline.build_run_record` ever reappear inside the script.

---

## 3. The asynchronous job model — decision ①

```
submit_ignition(request)  ->  job_id                    (returns in <1 ms)
status(job_id)            ->  {state, progress, ...}    (safe from any thread)
result(job_id)            ->  the dispatch list
cancel(job_id)            ->  True while QUEUED or RUNNING
```

States: `queued → running → succeeded | failed | cancelled`.

**The queue is bounded and refuses when full.** An unbounded queue accepts work
it cannot do and reports success for a request that will be served in an hour.

### 3.1 Cancellation — a misclick must not cost 26 seconds

`cancel(job_id)` works while a job is **queued and while it is running**. It is
cooperative, not pre-emptive:

| where the flag is read | cost of a cancel arriving just after |
|---|---|
| after the resource load | the load, ~1.5 s (one osmnx call, not interruptible) |
| at each origin boundary | **one origin, ~55 ms** |
| once more before delivery begins | nothing |

**A cancelled request leaves no artifact.** Routing precedes every write, so
stopping inside it means nothing exists yet; the run directory the job had
reserved is removed if it is still empty. That is why the flag is not read
*during* delivery — stopping there would leave one village's sheets written and
the next village's missing, which is a worse outcome than finishing the 0.04 s.

⚠ **Cancellation is a separate hook from progress, deliberately.**
`route_region` takes `on_progress` (observation: two integers out, return value
discarded) and `should_cancel` (control: a predicate that can raise
`RoutingCancelled`). Signalling cancellation *through* the progress callback —
by raising from it, or by reading its return — would make a progress listener
able to change an answer, and the guarantee that a run with progress equals a
run without it would be gone. A test asserts both hooks keep their roles.

A cancelled job reports state `cancelled`, not `failed`: the caller asked for
it, so it is not an error anyone should go hunting for.

### 3.2 Progress — what an operator sees during the 27 seconds

| stage | weight | unit |
|---|---:|---|
| 자원 적재 — 위험면·보행망·대피 POI | 0.118 | 단계 |
| **경로 산출 — 출발지별 대피소 탐색** | **0.867** | **출발지** |
| 마을 군집화 | 0.003 | 지점 |
| 전달물 생성 — A4·마을방송·SMS | 0.011 | 마을 |
| 기록 작성 — RUN.json·viz.json | 0.001 | 파일 |
| A4 PDF 변환 | — | **excluded from the total** |

The weights are §1.1's measurements, not a guess, which is why one stage owns
87 % of the bar. That is honest and it is also fine: what an operator watches is
the counter *inside* that stage, which advances about seventeen times a second.

The routing line carries what the stage is **doing**, not only how far along it
is — the per-origin cost is one full-graph Dijkstra plus a pick over the
region's shelters, so the shelter count goes on the line:

```
경로 산출 — 출발지별 대피소 탐색 137/458 출발지 · 대피소 46곳 탐색
```

A request emits 53–62 progress events at the measured throttle, and the counter
advances about twenty times a second underneath that. The callback is a plain
`Callable[[dict], None]`; nothing in this module knows what a browser is, and
`Progress` works identically when nobody is listening — `NullProgress` is the
default for batch callers, so the script path and the service path run the same
code rather than a with-progress and a without-progress variant.

`snapshot()` returns the stage name, the counter, the per-stage fraction and the
weighted overall fraction, already serialisable — a transport would hand it
straight out.

The PDF stage is excluded from the total for the same reason it is excluded from
every other timing in this project — it runs after the dispatch list already
exists and scales with village count rather than with the decision. The bar
reaches 100 % when the **decision** is ready.

⚠ **The progress hook cannot change the answer.** `route_region` and `deliver`
take an optional `on_progress` that defaults to `None`. It receives integers,
its return value is discarded, and a test parses `live/pipeline.py` to assert
every call is a bare statement — so a callback can never reach a bucket.

---

## 4. The other three decisions

### 4.1 A warm request reports a warm cost

`Resources.timings` carries the load cost of the run that *filled* the cache.
Handing that to a warm request would report 3.6 s the warm request never paid,
so the cache entry carries `was_cached` and the service zeroes the load stage
when it is true. A warm request's `cold_total_s` then equals its
`warm_total_s` — which is the truth: nothing was loaded.

⚠ **The batch path is deliberately unchanged.** A script owns its process, so
its second trigger's `cold_total_s` is still "what this process paid to get
here". Only the service's own entry point zeroes it, because there the load was
paid by a different request.

### 4.2 The cache key is not the parameter set

The walk network is built once per `(sampling_m, max_abs_slope)`. `p_cut`, the
budget and the stride change the **scan**, not the loaded network — so two
requests differing only in stride share one graph. Keying on the whole parameter
set would rebuild a graph to change a number that never touches it.

Two concurrent requests for the same region produce **one** load: a per-key load
lock makes the second wait rather than duplicate. A duplicate load is not merely
slow — it doubles the peak memory of a process already holding a walk graph.

### 4.3 Run-id isolation

```
20260806T093233Z_a1b2c3d4
└── committed scheme ──┘└─ job id ─┘
```

The timestamp prefix is kept because every consumer in this tree finds the
latest run by sorting directory names, and `tests/test_operator_screen.py` and
`tests/test_manual_trigger.py` both do exactly that. The suffix is what two
requests inside one second no longer share.

### 4.4 Frozen globals, and determinism — decisions ③ and ④

`freeze_globals()` records the osmnx settings digest and numpy's global RNG
digest at process start. Every job asserts they are unchanged on the way out and
raises `GlobalStateViolation` naming which one moved.

It **does not restore them**. A guard that silently restored a global would hide
the bug it exists to find.

Freezing is idempotent: a second `freeze_globals()` returns the first snapshot,
so a drift cannot be adopted as the new baseline. `force=True` exists for tests
and says so.

### 4.4.1 ⚠ The seed question, stated accurately

This was reported back to me in a stronger form than the evidence supports —
"two service functions were polluting the numpy global seed" — so the record
needs to be exact, because a documented finding that did not happen is worse
than no documentation at all.

**What is true:**

| claim | verdict | evidence |
|---|---|---|
| Some code in this tree calls `np.random.seed` on the **global** stream | **yes** | seven files under `scripts/spread_v2/` — `00_audit`, `01_build_features`, `02_lofo_cv`, `03_comparison`, `04_importance`, `05_weather_decomposition`, `06_figures` |
| A **service function** was polluting it | **no** | the two sampling functions this came up about — `convergence()` and `spatial_bias()` in `run_building_origin_routing.py` — take a seed and build `np.random.default_rng(seed)`, which does **not** touch the global stream. Measured: the digest is unchanged across both calls. |
| The pollution was ever **observed** | **no** | `measure_service_layer.py` digests the global RNG before and after a full run — cold load, three requests, two concurrent jobs — and reports `unchanged: true` |
| The seeding is at **module scope** | **no** | every one of the seven calls is inside a function body, and the files are named `NN_thing.py`, which is not an importable identifier |

**So the finding is a shape, not an incident**, and the shape is the part worth
keeping:

* A **script owns its process.** It can seed the global stream, run, and exit;
  nothing else was ever going to observe that global. Seeding there is not just
  harmless, it is *invisible* — there is no second request to contaminate.
* A **service does not.** The same line, on a request path, would make every
  later request in that process depend on how many requests came before it —
  and it would do so without an error, without a log line, and without moving
  any artifact a diff could see.

That is why `guards.py` asserts the digest is unchanged rather than trying to
control what it was set to: the day a future edit reaches for `np.random.seed`
on the request path, the result should be a named exception, not one request
quietly changing the next one's answer.

### 4.4.2 ⚠ Why the regression gate could not have caught this — and did not catch a real bug

**The regression gate is structurally blind to it.** §6 runs *scripts*, each in
a fresh process, and diffs the artifacts. Cross-request contamination cannot
appear in that measurement **by construction**: a fresh process has no previous
request to be contaminated by. A gate that runs N processes once each can never
falsify a claim about what happens to request N+1 in one process.

This is not hypothetical, and STEP 1 proved it with something that actually
went wrong:

> `result_digest` — the service's own "did the answer change?" fingerprint —
> omitted `route_seconds`. Three scans with **byte-identical buckets** reported
> three different digests, and the first measurement recorded the service as
> **non-deterministic**. The artifact diff had already passed, 0 real
> differences, five series, three runs. It could not possibly have caught this:
> `result_digest` is service-only code that the script path never executes.

Two lessons, and the second is the general one:

1. A digest that calls a *slower* run a *different answer* is worse than no
   digest. Every duration field now lives in `NON_DETERMINISTIC_KEYS`, and two
   tests pin it — one on the specific `route_seconds` case, one that checks the
   exclusion set against the keys the service actually emits.
2. **When the structure changes, the check has to change with it.** The
   artifact diff answers "does the same script produce the same file?", which
   was the whole question while everything was a script. It is no longer the
   whole question. The properties that only a service can violate — global
   state surviving between requests, two requests sharing a directory, a job's
   answer depending on what ran before it — need checks that run *many requests
   in one process*, which is what `measure_service_layer.py` and the
   concurrency tests are for.

`docs/service_layer.md` §6 therefore has two halves on purpose: an artifact
diff for what scripts do, and an in-process measurement for what a service
does. Neither substitutes for the other.

### 4.4.3 Seed verification

The tests assert, explicitly:

* `building_origins.sample_seed` is `20260805` and comes from config;
* the same seed draws the same sample twice, and `seed + 1` — the separation
  between `convergence()` and `spatial_bias()` — draws a different one;
* drawing through `np.random.default_rng(seed)` does **not** move the legacy
  global stream;
* **building snapping has no seed at all**, and that is the finding rather than
  an omission: a building's origin node is the answer to a distance question,
  not to a random one. `load_walk_nodes` is called twice and compared, and the
  buildings module is asserted to contain no `random` at all.

`IgnitionRequest.determinism_key()` hashes region + coordinate + parameters, and
deliberately **excludes** `reported_by`: who reported a fire reaches the
artifact, not the computation.

---

## 5. ⚠ What was deliberately NOT done

**The routing is not optimised.** Nothing that computes a number was touched.

> ⚠ **CORRECTION, 2026-08-06.** An earlier revision of this section said the
> shelter search was "~78 % of the 26.9 s — 458 origins × 26 shelter targets
> ≈ 11,908 Dijkstra solves". **Both halves are wrong**, and they were written
> here from a conversational summary rather than from the code. Profiled:
>
> * `naive_route` runs **one** `single_source_dijkstra` per origin — measured
>   at exactly **1.00 calls per origin** across all three regions — and then
>   takes a linear minimum over the shelters. The multi-destination single
>   search is **already how it works**; the code even says so in a comment.
>   The scan runs ~458 naive Dijkstras, not ~11,908.
> * The shelter search is **not** the dominant cost. It is 13.5–28.2 % of the
>   scan depending on region. The largest single line item is the per-origin
>   **hazard table build** inside `future_aware_route` — 35–58 %.
>
> The real profile is in §5.1. Do not quote the retracted figures.

Structure first, arithmetic later. A refactor that also improved the routing
would make "the answer did not change" unfalsifiable, because there would be no
way to tell a bug in the move from an improvement in the maths.

### 5.1 Where the scan actually spends its time — measured

`scratchpad profile_routing.py`, 60 origins per region, timers around each
sub-step. Percentages are of the scan, load excluded.

| | 영덕 2025 | 의성·안동 2025 | 울진·삼척 2022 |
|---|---:|---:|---:|
| graph | 8,443 n / 46 shelters | 6,678 n / 31 | 7,300 n / 23 |
| per-origin | 53.8 ms | 76.9 ms | 39.4 ms |
| **`naive_route` total** | **33.1 %** | **19.5 %** | **37.4 %** |
| · `single_source_dijkstra` | 26.5 % | 13.5 % | 28.2 % |
| · pick nearest shelter | 1.2 % | 0.7 % | 1.5 % |
| · `_evaluate_path` | 5.4 % | 5.3 % | 7.7 % |
| **`future_aware_route` total** | **66.6 %** | **80.3 %** | **62.3 %** |
| · **hazard table build** | **57.9 %** | **35.0 %** | **52.1 %** |
| · time-expanded search | 1.3 % | 38.5 % | 3.0 % |
| · `_evaluate_path` | 7.4 % | 6.8 % | 7.1 % |

Two things this says that the retracted figures did not:

1. **`single_source_dijkstra` settles 100 % of the graph on every call**, in
   every region. It computes shortest paths to all 8,443 nodes when only the 46
   shelters are wanted. That is the waste in the shelter search — not a repeated
   search, an unbounded one.
2. **The single largest line is the hazard table.** `future_aware_route` builds
   an `(n_nodes × n_bins)` array — 8,443 × 61 ≈ 515,000 bilinear samples — and
   builds it **again for every origin**. It is a pure function of the hazard,
   the node coordinates, `departure_min`, the budget and the step. **None of
   those varies across the origins of one scan**, so all 458 tables are the same
   array.

### 5.2 PHASE 20 — the one optimisation that was adopted

**The hazard table was hoisted out of the per-origin loop.** That is the whole
of PHASE 20.

`future_aware_route` built an `(n_nodes × n_bins)` array from the hazard, the
node coordinates, `departure_min`, the budget and the step. A 459-series scan
holds **all five fixed across its origins** — `start` never enters the table —
so 458 identical arrays were being built where one would do.
`build_time_expanded_field` now builds it once per scan and every origin is
handed the **same object**.

⚠ **Why this one was allowed when the others were not.** It is memoisation of a
pure function. There is no version of it that returns a different number,
because the array every origin reads is bit-for-bit the array it would have
built for itself — asserted directly in
`test_the_hoisted_field_is_bit_identical_to_the_one_built_per_origin` and
`test_a_route_with_a_hoisted_field_equals_one_that_builds_its_own`. Every other
candidate below changes *which route is chosen*, which is a different claim
entirely.

`future_aware_route(field=...)` is optional and defaults to `None`; the ten
other call sites in the tree are untouched and still build their own. A field
built for different parameters, or for a different network, is **refused rather
than used** — a mismatched table has the right shape and its lookups succeed, so
it would otherwise return a plausible route for the wrong question.

The cancel check was moved to sit **before** the build: a request already
cancelled should not pay a few hundred milliseconds for a table nobody reads.

**Measured, on the full 458-origin Yeongdeok scan** (same machine, same
coordinate, PDF excluded — the manual-trigger path before and after):

| | before | after | |
|---|---:|---:|---:|
| routing | 26.5 s | **10.9 s** | **2.43×** |
| trigger → dispatch list (warm) | 26.9 s | **11.1 s** | **2.42×** |
| coordinate → dispatch list (cold, load included) | 29.6 s | **13.8 s** | **2.14×** |

⚠ **This is the SERVICE path only.** The batch runners
(`run_yeongdeok_canonical_routing.py`, `run_multi_region_routing.py`,
`run_real_roads_real_hazard*.py`, `run_building_origin_routing.py`) each carry
their own `classify()` loop — duplicated on purpose, so that editing a script
cannot silently redefine what "origin" means — and each still calls
`future_aware_route` with no field. They were re-timed at 27–28 s per arm,
unchanged.

That is deliberate for this PHASE and it is also what makes §6's evidence
readable: the batch re-derivations exercise the **default, self-building**
branch, so they prove that branch still produces the committed artifacts, while
the manual and replay diffs exercise the **hoisted** branch. Extending the hoist
into the batch runners is a small follow-up, and it must pass the same gate,
because those scripts are the ones that produce committed numbers.

### 5.3 ⚠ Optimisations NOT adopted, and why — read this before reviving one

Each of these is faster than what is in the tree. That is not sufficient, and
the reason each was rejected is recorded here because **speed is the part
someone will remember and the reason is the part they will not**.

| candidate | speed | why it was NOT adopted |
|---|---|---|
| **Multi-source Dijkstra from the shelters** — one search over the reversed graph, reused by every origin | large; removes most of the remaining `naive_route` cost | **Changes which shelter is chosen.** The committed rule is "minimum `lengths[shelter]`, ties broken by iteration order over `net.shelters`". A reverse search resolves ties by its own settle order, which is not the same order. Any origin equidistant from two shelters can flip, and with it its route, its exposure and possibly its bucket. Not a speed-up — a different rule. |
| **Precomputed shelter distance field** — one distance-to-nearest-shelter array, looked up per origin | largest of all the candidates | **Ignores arrival time.** The whole point of the 459 series is that safety depends on *when* you arrive, not only where you go. A static distance field answers the fire-blind question only, and would silently turn the future-aware arm into a second fire-blind arm. It would make the project's headline contrast meaningless while making it fast. |
| **Bounding the shelter Dijkstra** — stop once every shelter is settled instead of settling all 8,443 nodes | measured waste: **100 % of the graph is settled on every call**, in all three regions | **Plausible but unproven, and it touches the tie-break.** Early termination changes nothing *if* the stopping rule settles every shelter before it stops — but `single_source_dijkstra` with `paths` reconstructs to all nodes, and the pruned variant would have to reproduce the exact same `lengths` dict for the shelters. Cheap to try, but it must be proved by the same bit-identical gate, not argued. **This is the strongest remaining candidate.** |
| **Coarsening the time grid** — fewer bins in the time-expanded search | proportional to the bin reduction | **Changes the corridor test.** `kb = ceil((arrive - departure) / time_step_min)` is what decides whether an edge is passable at arrival. Fewer bins means a coarser round-up, means different edges forbidden, means different routes. `time_step_min` is a *model parameter*, not a performance knob — it is registered in `config/default.yaml` and every committed 459 number was produced at 10 minutes. |
| **Contracting the walk graph** — remove degree-2 chain nodes | ~4× on the graph search | **Node removal changes the origin set.** Origins ARE walk-graph nodes, selected by `stride 18` over `sorted(net.graph.nodes)`. Removing nodes renumbers that iteration, so a different 458 origins are scanned and the counts move for reasons that have nothing to do with routing. Contraction would have to preserve the node set exactly, at which point most of the saving is gone. |
| **Process-level parallelism** — split the origins across worker processes | 2–4× depending on cores | **Deferred, not rejected** — and deferred for a reason that is about the system rather than the maths. §6.5. |

⚠ The first two are the ones to be most careful about: both are *large* wins and
both are wrong, and neither would fail loudly. They would produce a complete,
well-formed dispatch list that is a slightly different dispatch list.

**No producing script was deleted**, and none was rewired except the two on the
trigger path.

---

## 6. The regression gate

The pre-PHASE-19 code was checked out into a second git worktree at
`real-buildings`, given the same `data/` and the same `.env` by symlink, and run
against the same inputs. Both sides' outputs were diffed file by file and key by
key.

A difference is allowed only if it is a **timestamp**, an **absolute path**, or
a **key PHASE 19 adds** (`service`, `read_from_cache`, `resource_cache`,
`resources_were_cached`). Everything else is a regression.

### 6.0 PHASE 20 — the same gate, run again after the hoist

The hoist changes what `future_aware_route` reads, so the whole gate was re-run
against the same pre-PHASE-19 baseline.

| run | shared files | byte-identical | time/place | PHASE-19 additions | **real** |
|---|---:|---:|---:|---:|---:|
| 수동 트리거 — **the hoisted path** | 119 | 87 | 57 | 8 | **0** |
| 재생 트리거 #1 | 119 | 117 | 15 | 8 | **0** |
| 재생 트리거 #2 | 119 | 117 | 15 | 8 | **0** |

| artifact re-derived | keys compared | **real diffs** |
|---|---:|---:|
| 459 · 영덕 정본 | 193 | **0** |
| 459 · 의성·안동 | 729 | **0** |
| 459 · 울진·삼척 | 462 | **0** |
| 건물 표본 (PHASE 18) | 3,367 | **0** |
| 439 · `rescue_routing_full` | 6,626 | **0** |

The four-way counts and the exposure reduction are inside those files and are
therefore covered: `458 / 414 / 42 / 2 / 0` on the canonical arm and
`415 / 41 / 2` on the flat control, unchanged.

### 6.1 The touched path — diffed against the pre-PHASE-19 code

| run | shared files | byte-identical | time/place | PHASE-19 additions | **real** |
|---|---:|---:|---:|---:|---:|
| 수동 트리거 (36.4436, 129.3696) | 119 | 87 | 58 | 8 | **0** |
| 재생 트리거 #1 | 119 | 117 | 14 | 8 | **0** |
| 재생 트리거 #2 | 119 | 117 | 13 | 8 | **0** |

The manual run has fewer byte-identical files only because its scope banner
carries a minute-resolution stamp that reaches all 29 villages' SMS drafts; the
sheets, broadcast scripts and message bodies are identical once that one
substring is masked.

### 6.2 The untouched paths — re-derived and diffed against the committed artifacts

| series | artifact | keys compared | **real diffs** |
|---|---|---:|---:|
| 459 · 영덕 정본 | `real_roads_real_hazard_canonical.json` | 193 | **0** |
| 459 · 의성·안동 | `real_roads_real_hazard_uiseong_andong_2025.json` | 729 | **0** |
| 459 · 울진·삼척 | `real_roads_real_hazard_uljin_samcheok_2022.json` | 462 | **0** |
| 439 | `rescue_routing_full.json` | 6,626 | **0** |
| 건물 표본 (PHASE 18) | `building_origin_routing.json` | 3,367 | **0** |

Plus `make baseline-verify` (63 artifacts intact), `make verify-numbers`
(136/136), and the four PROTECTED digests re-checked by the runners themselves.

### 6.3 What the regression FOUND

Two defects, both pre-existing, both surfaced by running the scripts with an
output root outside the repository — which is what a service does:

1. **`out_dir.relative_to(REPO)` in a console line raises** for any `--out-root`
   outside the repo, *after* every artifact has been written. Fixed with
   `rel_to_repo` in the two scripts PHASE 19 touches. ⚠ Still present in
   `run_yeongdeok_canonical_routing.py`, `run_multi_region_routing.py` and
   `run_building_origin_routing.py` — see §7.4.
2. **`--out-dir` is not created before it is written to** in
   `run_multi_region_routing.py`, so the first region's result is computed for
   ~4 minutes and then lost to `FileNotFoundError`.

Neither changes a number. Both were invisible while every run wrote inside
`data/processed`.

---

### 6.4 Measured — `scripts/measure_service_layer.py`

**Memory.** All three regions resident in one process, together:

| region | hazard field | walk nodes | walk edges | shelter nodes |
|---|---:|---:|---:|---:|
| 영덕 2025 | 0.54 MiB | 8,443 | 21,982 | 46 |
| 의성·안동 2025 | 0.33 MiB | 6,678 | 17,270 | 31 |
| 울진·삼척 2022 | 0.27 MiB | 7,300 | 18,264 | 23 |

**Process peak RSS with all three resident: 462–489 MiB** across two runs. So the answer to "cache
or replace" is **cache**: three regions cost about half a gigabyte including
the interpreter, numpy, osmnx and rasterio, and the graphs themselves — not the
hazard fields, which are trivial at ~1 MiB total — are what that buys.

⚠ The per-region RSS deltas are **peak** differences and are not additive. Peak
RSS never falls, so the first load's transient parse buffers raise the peak and
the second region's delta then reads far too low (1.4 MiB, which is obviously
not what a 6,678-node graph costs). Only the two exact figures — the hazard
`nbytes` and the total process peak — are quotable. Live-object accounting
needs `psutil`, which is not in this environment.

**Per-request time**, one process, one cache:

| | wall | load | routing | delivery |
|---|---:|---:|---:|---:|
| cold (nothing resident) | 23.58 s | **1.44 s** | 21.99 s | 0.04 s |
| warm #1 | 21.69 s | **0.00 s** | 21.64 s | 0.03 s |
| warm #2 | 21.88 s | **0.00 s** | 21.83 s | 0.03 s |

⚠ **Do not read the wall-clock difference as the saving.** Routing varies by
±2 s run to run, which is comparable to the load stage: cold-minus-warm has
measured 0.54 s and 1.70 s on two runs of the same script, and would come out
negative on another draw. The honest statement is the **load stage itself**:
1.4–1.5 s here, 2.5–2.7 s across the ten regression runs, 3.6 s in STEP 0 on a
colder machine — and **exactly 0.00 s on every warm request**, which is the part
that does not depend on how the figure was estimated.

**Cancellation**, measured on a real 458-origin scan cancelled five seconds in:

| | |
|---|---|
| where it was when cancelled | `경로 산출 — 출발지별 대피소 탐색 106/458 출발지 · 대피소 46곳 탐색` |
| **time to stop** | **0.060 s** |
| final state | `cancelled` (not `failed`) |
| **files left behind** | **0** — the reserved run directory was removed |

0.06 s against a remaining 17 s of scan. That is the difference between a
misclick costing a presenter a beat and costing them the rest of their slot.

**Determinism and concurrency:**

| question | answer |
|---|---|
| same coordinate twice → same answer? | **yes** — one `result_digest` across three runs |
| two requests at once → same answer? | **yes** — identical digests and identical bucket fingerprints |
| two requests at once → two directories? | **yes** — `20260806T101246Z_e671a38e` and `…_4c8102bc`, **minted in the same second** |
| submit blocks? | **no** — returns in 0.1 ms |
| process globals moved? | **no** — osmnx and numpy digests unchanged |

The two concurrent run ids are the clearest evidence for §4.3: same timestamp to
the second, different directories. Under the committed scheme they were the same
string, and the second request would have written its sheets over the first's.

⚠ **Two concurrent jobs each took 43.5 s of routing, up from ~22 s.** That is
the GIL, measured: threads make the second request *start* immediately, not
finish sooner. Both together took 43.7 s against ~44 s sequential, so the
overlap is real and very small. §7.1.

---

### 6.5 Deferred to a later PHASE — decided, not forgotten

| item | why it waits | what to do when it is picked up |
|---|---|---|
| **Process-level parallelism** | 2–4× on the scan, and floating-point determinism would survive (each origin is independent and its arithmetic is unchanged). But it **interacts with the concurrency that already exists**: a transport is itself parallel, and nesting a process pool inside a parallel request handler contends for the same cores. Optimising one request's latency can make N simultaneous requests slower. | measure it **after** a transport exists and the real concurrency is known. Deciding now would be deciding without the number that matters. |
| **Locking osmnx settings** | nothing on the request path writes them today, so the present risk is low. `guards` already **detects** a change; what is deferred is *preventing* one (a read-only proxy over the settings namespace) | the guard stays; add prevention only if something ever needs to be set at start-up |
| **Delivery as service functions** | A4, 마을방송 and email already work as separate scripts, and the right shape for them will be obvious once something calls them over HTTP | revisit when the transport lands — the wrong abstraction now would have to be undone |

⚠ The osmnx item is **deferred, not dismissed.** The digest check runs on every
job and costs microseconds; only the stronger "cannot be written at all"
version is postponed.

---

## 7. Known limits

1. **Threads, not processes.** Two concurrent jobs are *safe* — shared
   read-only resources, per-job directories, per-job progress — but not
   *faster*: the scan is pure-Python networkx Dijkstra, so the GIL serialises
   it and each job's `route_s` roughly doubles. What concurrency buys today is
   that the second request **starts** at once instead of waiting. Real
   parallelism needs processes, and processes need a per-process resource cache
   — a decision with a memory bill attached, left to the next PHASE.
2. **The job store is in memory.** A restart forgets every job id. The run
   directories survive, so nothing is lost that was written; but a caller
   holding a job id gets a `KeyError` rather than a result. Acceptable while the
   caller is a demonstration console in the same process; a transport that
   survives restarts would need the store on disk.
3. **Cancellation is cooperative, so it cannot interrupt the load.** The ~1.5 s
   resource load is a single osmnx call with no boundary to check at. A cancel
   arriving during it lands immediately afterwards. Nothing is written either
   way.
4. **No transport.** By design — §0.
5. **`--out-root` outside the repo used to crash the console line** that printed
   where the run went, *after* every artifact had been written. Fixed in the two
   scripts PHASE 19 touches (`rel_to_repo`). ⚠ The same one-line pattern is
   still present in `run_yeongdeok_canonical_routing.py` and others, and the
   handoff's own scratch-output convention (§7) tells every future session to
   pass `--out` outside `data/processed` — so they will hit it. Not fixed here:
   out of this PHASE's scope, and the artifact is written before the crash.
