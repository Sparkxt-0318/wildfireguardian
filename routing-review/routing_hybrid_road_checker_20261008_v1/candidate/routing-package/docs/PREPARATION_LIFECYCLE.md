# Graph preparation lifecycle and API — 5 October 2026

Engineering candidate, optional admission reuse; unchanged exact routing search and checker. Standard library, Python 3.11+. Serialized session owner required for every mutation and completion callback. This object adds no synchronization and is not thread safe.

## Session ownership

```python
from routing.session import RoutingSession
session = RoutingSession(graph)  # original raw path, default
session = RoutingSession(graph, prepare=True)  # privately owned immutable snapshot
session = RoutingSession(graph, prepare=True, graph_ownership="checked")
```

Snapshot sessions admit graph geometry once on construction. Trusted retained storage is immutable canonical JSON bytes. Each operation uses a fresh decoded graph; `.graph` returns a fresh export. Caller/export mutations cannot change that session. The immutable `prepared_graph` handle explicitly denotes snapshot ownership. No graph-dependent hazard/search/exposure caches survive operations.

Checked sessions retain the caller's mutable graph as the authority, under the same serialized-owner contract. Before update, progress, planning, commit, retained display, return and graph export, they compare every canonical byte against the owned preparation. Revision or hash strings never substitute for complete contents equality. Same-revision changed geometry, timings, turns, grid or metadata rejects with `INVALID_INPUT / PREPARED_GRAPH_MISMATCH`; commit returns false. Detection advances generation and discards pending/retained guidance, while keeping progress/history/dose to prevent silent reinterpretation. Simultaneous caller mutation during serialization is outside this contract.

Reset is deliberately available for recovery after a mismatch. It clears hazard, position/history/incurred dose, retained guidance, pending/request state and causal clock and advances generation. It keeps admitted graph bytes. A checked external graph still must match or be explicitly replaced before another operation succeeds. Reset never silently rebuilds a changed graph.

## Graph replacement

```python
session.replace_graph(changed_graph)  # only when no mission state exists
session.replace_graph(changed_graph, reset=True)  # explicit destructive mission reset
```

A valid replacement is admitted before old mission state is cleared. Invalid replacement leaves old graph/state intact. A hazard/progress/retained/pending state requires `reset=True`; otherwise `GRAPH_REPLACEMENT_REQUIRES_RESET` rejects, even if revisions are equal or position labels happen to exist in both graphs. The explicit reset clears rather than maps position, history or dose. Supply a newly admitted matching hazard and actual progress before planning the new mission. Old result generations cannot commit. Raw sessions validate a replacement without adopting preparation. Checked sessions transfer external authority to the supplied replacement; snapshot sessions own new bytes. Rebuild time and transient coexistence of old/new snapshots are charged to replacement.

## Planning, progress and retained guidance

Existing `accept_update`, `set_progress`, `plan`, `commit`, `retained_plan` and `reset` remain. Preparation skips only redundant graph geometry admission. Hazard/request admission occurs freshly on relevant operations, including every prepared plan, progress probe, commit and retained recheck. Requests retain exact represented-input dose arithmetic, per-member histories, destination opening/dwell/admission, incoming context, lattice and support semantics. Update versions/causal metadata, conservative changed-member mapping and generation/request guards remain. Retained guidance always receives independent route checking. No success or refusal is inferred from a timeout.

Construction/preparation is outside `solve`'s request wall budget; the host owns its initialization deadline. Session hazard/request admission, content comparisons and completion checks also consume lifecycle time. Cooperative search caps can overrun in individual validation/check steps. There is no hidden promise that the complete session lifecycle fits `limits.wall_s`; report externally measured full lifecycle alongside warm request phases.

## Return fallback

```python
from routing import prepare_graph
from routing.service import plan_with_return
from routing.fallback import checked_return
p = prepare_graph(graph)
result = plan_with_return(p, hazard, request, history, endpoint)
result = plan_with_return(graph, hazard, request, history, endpoint, prepared=p)
checked = checked_return(p, hazard, request, history, endpoint, dwell=0)
checked = checked_return(graph, hazard, request, history, endpoint, prepared=p)
checked = session.check_return(request, endpoint, dwell=0)
```

A service call reuses the same immutable preparation for primary search and separately budgeted reverse-history admission. Each still decodes owned data and validates fresh hazard/request and runs independent checking. The checked external form compares full supplied graph contents for both paths. Session return uses current accepted hazard and overrides request position, incoming edge, time and incurred dose from actual progress; recorded progress history is default. An explicit history remains independently checked.

Reverse direction/turn rules, partial position and mirrored fraction, support, absolute timing, incurred-plus-return exposure, endpoint windows/horizon and dwell remain unchanged. A primary TIMEOUT leaves `primary_problem_resolved=False`, even with a `CHECKED_ROUTE` return. A refused recorded return is not a proof that all escape routes are infeasible.

## CLI and replay

```sh
python3 -B run.py solve --input fixtures/example.json
python3 -B run.py replay --input fixtures/continuity_replay.json
python3 -B run.py replay --prepare-graph --input fixtures/continuity_replay.json
python3 -B run.py solve --prepare-graph --input fixtures/example.json
```

`replay(fixture, prepare=True)` prepares one owned graph for the process, covering repeated PLAN/update/progress/retained/RETURN events. Optional `GRAPH_REPLACE` replay events contain `graph` and an explicit Boolean `reset`; replacement uses the lifecycle above. Every RESET keeps the same graph until explicit replacement. Replay output omits wall/RSS fields to preserve deterministic semantics; measure its complete process outside replay.

The solve flag exists for a one-shot primary-plus-return facade that can reuse graph admission across those two operations. A successful one-shot solve has no across-request reuse and should normally remain raw. Prepared CLI `end_to_end_s` includes input parsing/preparation and first facade call; the preserved raw field retains its original facade-only meaning. Benchmark both using external complete process time. Interpreter/import/output serialization is measured externally. No cross-process reuse, persistent trusted cache, daemon or HTTP service is provided.

## Adoption boundary

Use only opt-in paths whose full lifecycle earns the complexity on measured workloads. Tiny, one-shot and frequent-replacement work should remain raw when gains are negligible/negative. Existing separate established AS-EAGER/CAND-2 road research planner recommendation is unchanged. Real-road geometry here has generated hazards, not measured thermal/passability truth. No new algorithm, universal speedup, physical safety, forecast accuracy, deployment or concurrent-throughput claim follows.
