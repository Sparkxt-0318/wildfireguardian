# Explicit graph preparation

```python
from routing import prepare_graph, solve

prepared = prepare_graph(graph)  # full graph admission and chord/grid validation
result = solve(prepared, hazard, request)

# If a mutable graph remains the caller's source of truth, require full contents
# equality on every call. A reused revision does not permit changed contents.
result = solve(graph, hazard, request, prepared=prepared)

# A replacement is an explicit lifecycle operation, never an implicit cache hit.
replacement = prepare_graph(changed_graph)
result = solve(replacement, updated_hazard, updated_request)
```

`PreparedGraph` owns canonical immutable JSON bytes. Its constructor always
validates a decoded private snapshot using the unchanged graph validator.
There is no public constructor from unvalidated bytes. `snapshot()` returns a
fresh decoded dictionary; mutating that dictionary or the original graph cannot
invalidate trusted storage. Frozen slotted fields prevent normal attribute
assignment. This contract does not sandbox arbitrary Python code using reflection.

`matches(graph)` compares all canonical bytes, including revision, CRS, grid,
coordinates, edge geometry, travel ticks, turn and reversal rules, and extra
metadata. Object key order is canonicalized; array order is retained. JSON float
round-tripping preserves represented binary64 values, signed zero, and numeric
integer/float encodings. SHA-256 `fingerprint` is provenance metadata; matching
uses the bytes themselves, avoiding hash-only trust. Changed contents, even with
the same revision, produce `INVALID_INPUT / PREPARED_GRAPH_MISMATCH` in the checked
raw-graph reuse path. Prepare a replacement explicitly after any graph change.
`encoded_size_bytes` reports retained serialized payload length, excluding Python
object overhead and transient decoded solve data; it is not total process memory.

Passing `solve(prepared, ...)` means planning on that owned graph snapshot. It
cannot observe a separate dictionary the caller later mutated; use the checked
raw-graph path when such a dictionary is authoritative. Graph revision checks in
each new forecast still run, but no API can detect that an external forecast
producer reused a revision for unrelated geometry without supplying that geometry.

Only graph admission is reused. Every solve freshly decodes the snapshot,
validates the hazard and request, rebuilds request-local graph/search structures,
evaluates exact Fraction exposures, and invokes the unchanged independent route
checker. Hazard fields, lower bounds, occupancy costs and search proofs are never
shared between requests. Geometry is admitted once; exact search/checker geometry
recomputation remains unchanged. No destination, incoming-turn, incurred-dose,
scenario identity, lattice, support, objective or budget semantics are changed.

The underlying optional preparation API accepts only standard JSON values, finite numbers
and string object keys; tuples, custom Python objects, and non-JSON metadata are
rejected with `PREPARED_GRAPH_FORMAT`. The original raw `solve(graph, ...)` path
keeps the baseline validator behavior. Python 3.10 or later is required for
slotted dataclasses; the baseline Python 3.11 environment suffices, with no new
external dependencies.

Preparation is explicit and has nonzero validation, serialization and memory
cost. Report cold end-to-end latency as `prepare_graph` plus first `solve`, and
report warm solve latency separately. The checked raw-graph reuse path incurs
full serialization/content comparison each call. Each solve includes snapshot
decoding inside the existing wall-clock accounting; preparation outside solve
is a separately measured initialization cost. Resource exhaustion remains
`TIMEOUT`, never proof of infeasibility. No universal speedup or physical-safety
claim follows from this API.


## Integration candidate lifecycle

Opt-in session, return facade and process-local replay integration is implemented in this isolated candidate. See [PREPARATION_LIFECYCLE.md](PREPARATION_LIFECYCLE.md) for ownership, checked mutable authority, atomic replacement/reset, initialization costs and CLI options. Raw APIs and the established separate research planner recommendation remain available.
