# Opt-in exact search geometry/cache candidate

Status: development candidate, independent review and frozen confirmation gates pending. The original `routing/core.py`, admission rules, hazard payloads, budgets and package default solver are preserved. `core_cached.py` is an independently selected clone with diagnostic instrumentation and two cache changes; it does not replace the default API.

## API and four-mode comparison

```python
from routing.core_cached import solve_cached
from routing.search_geometry_cache import SearchGeometryCache

solve_cached(graph, hazard, request, *, prepared=None,
             geometry_cache=None, cache_enabled=True)
```

`request.solver` still selects the existing `baseline`/`dijkstra`/`astar` ordering. Instrumented baseline and heuristic-only use `cache_enabled=False`; they deliberately construct occupancy before the original per-search cost lookup, preserving the eager original work. Cache-only and combined use `True`. All modes use the same observer and independent route checker. The opt-in wrapper records its mode and instrumentation; metrics from this observer must not be attributed to uninstrumented original runs.

`SearchGeometryCache(raw_graph)` validates and owns a `PreparedGraph` of every canonical graph byte. It exposes `matches(graph)`, fresh `snapshot()`, provenance `fingerprint`, `occupancies(edge_id,start,end,from_fraction=0,to_fraction=1)` and `cache_info()`. A supplied cache must have the exact class and full admitted graph contents. Same revision or digest alone is insufficient. A mismatch returns `INVALID_INPUT/GEOMETRY_CACHE_MISMATCH`, without replacing the cache or accepting the changed graph. Explicitly construct a new owner for a changed graph. Disabled mode rejects a supplied cache instead of silently ignoring it.

Construction and full binding happen after request/hazard admission but within the solve clock. A missing cache is constructed in that clock. Explicit warm construction occurs before the call and belongs to the caller's lifecycle cost; a warm call still charges exact graph-content comparison and per-call request/hazard validation. An optional `PreparedGraph` retains its original full-contents binding semantics.

## Exactness and dependencies

The original `edge_occupancies` computes a finite ordered list of interval and point contacts using exact `Fraction` grid intersections. For edge fraction range `[f,q]`, the new static template invokes precisely that implementation at normalized times `[0,1]` and owns a tuple `(cell,lo,hi)` for every occupancy in the original order. For arbitrary represented departure/arrival times `a,b`, it returns fresh dictionaries with times `a+(b-a)*lo` and `a+(b-a)*hi`. For `q != f`, substitution of `lo=(z-f)/(q-f)` gives the original time formula exactly in rational arithmetic. For `q == f`, both normalized point times are zero, yielding the original departure point `a`, even when `a != b`. Midpoint cell assignment, all cut-point closures, negative edge directions and partial edge fractions are preserved.

A template key is `(edge_id,Fraction(f),Fraction(q))`; its owner binds all graph contents, including coordinates, grid, topology, edge IDs/durations/segments, turns, waitability, reversal rule, revision and extra JSON fields. Templates own immutable tuples and fractions; output dictionary mutation and mutation of `snapshot()` cannot affect future queries. Construction installs a template only after exact geometry completes; a failed construction installs no partial entry. This API is an ownership contract, not protection against arbitrary Python reflection or private-field mutation. Calls sharing an owner must be serialized; concurrent caller mutation is outside the admitted immutable epoch contract.

The local exposure cost dictionary retains the original keys `PARTIAL(edge,departure,fraction)`, `EDGE(edge,t)`, `WAIT(node,t)` and `DWELL(node,t,end)`. Enabled mode consults it before invoking the occupancy builder. A hit therefore avoids both geometry reconstruction and exposure evaluation; a miss performs the same exact exposure integration and peak admission. The dictionary is newly allocated on every solve. Static geometry contains **no hazard, source, scenario, physical parameter, support, request, exposure, route or incumbent**. Changes in any such data cannot reuse an exposure cost. The external prepared source epoch must bind those dependencies independently; this geometry owner cannot authorize source reuse.

No state key, vector component, dominance comparison, incoming-edge context, admission flag, residual traversal duration, waiting, destination opening/dwell rule, incurred dose, heuristic arithmetic or tie-breaking changes. No labels are merged or pruned beyond the original exact dominance rule. The relaxed reverse-graph travel-time lower bound is unchanged, including its use of the admitted `dt` and original limits. Geometry cache entry eviction is zero; cached entries are not dominance labels.

## Caps and status authority

The original limits are retained. Clock sampling begins before validation/cache binding and includes construction, geometry, exposure, exact dominance, heuristic computation, search, independent checking and normal report finalization. Cold/warm launch, import, source epoch construction, result serialization and the separate whole-road check must additionally be charged by the owning wrapper/driver. The solver does not represent those external phases as zero work.

A checked route exceeding the search cap remains `TIMEOUT` with a separately labelled checked incumbent, never an optimum. An added finalization gate uses one last elapsed sample after positive report, cache introspection and process-RSS construction; the same sample is reported and compared to the original wall cap. A decisive result crossing that cap or the RSS limit becomes `TIMEOUT`; its completed decision is retained as secondary evidence, and an incumbent is retained only when the independent route checker returned `ok`. The final gate does not override invalid, unsupported or known at-issue rejection statuses. Normal Python return and external serialization latency belong to the enclosing measured lifecycle. Root preserves the rejected first finalization implementation and the independent review correction record before freezing.

`TIMEOUT` means unresolved. `PROVEN_INFEASIBLE` remains available only after supported frontier exhaustion. At-issue refusal, structural disconnection, incomplete support, a checked feasible witness and optimality proof remain distinct. A cell/centre checked route is not a whole-road exposure certificate; the accepted Stage 1 hybrid checker must check a recovered witness independently and preserve its own unresolved/reject outcome.

## Diagnostic metric definitions

| Fields | Scope |
|---|---|
| `labels`, `retained_labels` | Cumulative appended records, including records later dominated; no physical record deletion. |
| `generated_labels` | Calls to exact label insertion after an exposure-admissible alternative; raw alternatives are separately `edge_candidates`/`wait_candidates`. |
| `dominated`, `dose_rejected_labels`, `cap_rejected_labels` | Declined insertion attempts. Generated equals retained plus these three counts. |
| `evicted_dominance_labels` | Old frontier references removed by exact dominance; records remain available for route reconstruction. |
| `expansions`, `expanded_labels` | Original expansion counter; popped successful destination labels need not be expanded. |
| `peak_frontier` | Original maximum nondominated vector width within one exact state key. |
| `live_front_references`, `peak_front_references` | All retained dominance references, including expanded states; not search queue width. |
| `heap_entries`, `peak_heap_entries`, `heap_pushes/pops`, `stale_heap_pops` | Queue entries including stale dominated records. |
| `live_pending_labels`, `peak_live_pending_labels` | Unpopped live frontier labels, separate from heap entries and expanded references. |
| `cost_cache_hits/misses/entries`, `occupancy_evaluations` | Local cost dictionary work; issue exposure is an additional occupancy evaluation. |
| `geometry_calls`, `edge_geometry_calls`, `node_geometry_calls` | Actual occupancy builders invoked; enabled cost hits skip them. |
| `geometry_cache_search` | Delta hits/misses/materializations/evictions for this call. `geometry_cache_lifetime` reports the owner's accumulated work/storage separately. |
| `rejected_costs` | Unique local cost misses refused by support/contact/peak; alternative refusal counters may include hits. |
| `destination_labels`, `destination_contract_attempts`, `dwell_contract_rejects`, `destination_dose_rejects` | Arrival/admission progress and opening/horizon/dose refusals. |
| `wait_retained_labels`, `edge_exposure_rejects`, `wait_exposure_rejects`, `exposure_rejects` | Retained waits and declined edge/wait/destination alternatives. |
| `route_witness_checks`, `checked_incumbents` | Independent checks attempted; checked witnesses retained under a cap. |

`timing_s` contains validation, geometry binding, geometry, exposure, dominance, heuristic, structural preprocessing, independent check and finalization wall times. `search_setup` includes binding and issue geometry/exposure. `search_loop` includes child phases and initial report introspection. These inclusive quantities overlap: **do not sum them as exclusive CPU time**. Residual dispatch/counter/report operations appear in total wall time; caller/driver records CPU and launch/source phases. Warm graph-owner validation/storage work is distinct from each call's integration and route check.

RSS is the process-lifetime maximum reported by `getrusage`, including imports, previous calls and external preparation in that process. It is not allocated-memory delta or a per-phase peak. `encoded_graph_bytes` is serialized graph storage; `shallow_template_bytes` includes cache-key/template containers and excludes nested coordinate/dictionary/Fraction storage. Use engine-isolated RSS and full lifecycle measurements for computational claims. An owner accumulating many distinct partial fractions across requests grows monotonically; reuse must remain bounded by the caller's lifecycle and process cap. No hidden eviction changes search outcomes.

## Bounded development evidence

`tests/cache_development.py` passed **45 tests**, including 15 authored cache controls and the unchanged 15 preserved CoreTests run once through disabled and once through enabled instrumentation. The original suite includes its existing 40 tiny two-member exhaustive comparisons per run. A known 17-case independently authored fixture panel is also compared to untouched `core.solve` under all four cache/heuristic combinations; status, reason, routes, incurred/member results and original work counters agree. These are development references, not fresh confirmation or physical validation.

The controls cover complete graph mutations, output ownership, exact partial/point/rational-time recovery, explicit replacement, source/request/support/flame changes with no exposure reuse, failed-template atomicity, fixed state caps, zero deadline, post-check timeout and finalization deadline. A delayed destination on the original three-node fixture retains the same arrival 8, 45 labels, 38 expansions, 26 dominated attempts and 40 exposure evaluations. Eager mode invokes 72 occupancy builders (50 edges,22 nodes); enabled mode invokes 40 (29 edges,11 nodes), with four static edge builds, 25 template hits and 32 local cost hits. This identifies redundant geometry work on a small fixed reference; it makes no broad speed claim. Fresh confirmation and independent final gates remain coordinator-owned.

Graph evidence: parent Tier 2 original-core project generation `2026-10-08T00:16:31Z` with complete supplied solve/occupancy/preparation snippets, call traces and reported coverage. New files were authored using direct reads of those exact known paths because the new candidate index was pending. A clean graph coverage signal is no recorded gap, not proof of completeness; the coordinator/reviewer must record refreshed candidate coverage before final claims.
