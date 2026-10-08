# Opt-in integrated search and source epochs, version 1

This candidate changes search ordering and reuse, not the supplied hazards, queries, dose/peak budgets, time lattice, dominance relation or routing defaults. It is an experiment over the original centre/cell contract followed by the independently accepted hybrid fixed-road checker. It cannot turn a centre optimum into a road optimum. Constructed four-member hazards remain assumptions, not observations or physical-safety evidence.

## Portable API and explicit ownership

```python
from search_followup import SearchFollowup, run_search, prepare_epoch

# One-shot cold API, returning JSON-compatible evidence:
report = run_search(graph, admitted_hazard, source_directory, request,
                    mode="combined", checker_wall_s=30)

# Explicit repeated use; the first run measures preparation:
session = SearchFollowup()
cold = session.run(graph, admitted_hazard, source_directory, request, mode="combined")
warm = session.run(graph, admitted_hazard, source_directory, new_request, mode="combined")

# Optional explicit preparation, charged separately by its caller:
epoch = prepare_epoch(graph, admitted_hazard, source_directory)
other = SearchFollowup(prepared_epoch=epoch)
```

`run_search(graph, admitted_hazard, source_directory, request, *, mode="baseline", prepared_epoch=None, geometry_cache=None, checker_settings=None, check_witness=True, checker_wall_s=30)` creates a one-shot session. `SearchFollowup(...).run` accepts the same four positional inputs and the mode/checking keywords. A supplied geometry cache is the cache lane's `routing.search_geometry_cache.SearchGeometryCache`; its entire graph binding is validated by the solver, never silently reset. A session retains its own populated geometry cache for subsequent explicit reuse. Modes are exactly `baseline`, `cache`, `heuristic`, `combined`.

Source directories for integrated experiments must contain `REPORT.json`, `NATIVE_METADATA.json`, and `constructed_arrays.npz`. The sidecar must equal the report's complete native metadata. The NPZ member fields are passed through the original `forecast_bridge.convert` with the original integration routing IDs by physical array index. For native v2, these are exactly `construction:<construction_id[:20]>:<index>` as assigned by unchanged `hourly.build_hazard`, distinct from constructor event labels. The full construction ID must also equal the original hourly SHA-256 of `{mode, version, parent_sha256, cutoff, construction}`, with `cutoff` the timezone-aware `issued_at` converted to UTC `isoformat()` and the same sorted compact JSON encoding. A coherent relabeling of hazard/report IDs cannot forge this provenance. Admitted hazard order and every report request incurred/dose ID order must agree; no ledger or hazard is renamed here. Legacy v1 labelled fixtures may use their explicitly declared identities. The resulting hazard must equal every canonical JSON byte of the supplied admitted hazard, including all flux/support/flame values, units, timing, grid, provenance, assumptions, versions and member order. Exactly four members are admitted for this integrated checker scope. Event/source-history arrays and all other NPZ contents are retained and content-bound even when the centre bridge does not consult them.

`source_directory=None` is permitted only as an explicitly labelled centre-only reference fixture: it never supplies missing physical history, and `whole_road_check` is `UNRESOLVED / SOURCE_CONTRACT_UNAVAILABLE`. These reference fixtures cannot establish an integrated road benefit.

`PreparedSearchEpoch` is a frozen, non-subclassable dataclass with owned immutable graph, hazard, source-file, implementation and settings bytes. Snapshot access returns decoded copies. Canonical JSON admission rejects masked arrays, non-JSON values, non-string keys and nonfinite numerics. Graph matching uses `PreparedGraph`'s full-byte equality. File comparisons use complete stored bytes, not only filenames, revisions or digests. Identity hashes are provenance, not the equality test. This is normal Python API immutability, not security isolation from reflection or arbitrary executable monkeypatches.

Each run checks complete graph/hazard/source/directory/code/settings contents before search and again after computation and after cache/RSS/ordinary metadata access. Source admission is therefore still checked during warm reuse. Every solver invocation freshly validates hazard availability, request version/as-of, member mapping, incurred exposure, budgets, incoming turn context, position, destination openings/dwell and limits. Requests, dose/exposure costs, frontier records and search outcomes are never stored in the epoch. Per-search cost caching stays local to the solver. Content changes are refused with a `NEW_EPOCH_REQUIRED` reason. Replacement is explicit: call `prepare_epoch` for the changed source/graph/hazard/settings and create a **new** `SearchFollowup`; there is no automatic cache reset or favorable replacement.

## Four modes and observer boundary

All four measured modes use the same opt-in `routing.core_cached.solve_cached` observer implementation:

| Mode | Original ordering | Geometry reuse |
|---|---|---|
| baseline | `solver="baseline"` | disabled; original eager reconstruction |
| cache | `solver="baseline"` | enabled; lazy exact templates |
| heuristic | `solver="astar"` | disabled; original eager reconstruction |
| combined | `solver="astar"` | enabled; lazy exact templates |

The request's only experimental dispatch change is its solver selector. Resource limits remain exactly the original values. The opt-in implementation is labelled in each report. Development controls compare its raw status, arrival, per-member witness and fixed-cap behavior against the untouched `routing.core.solve`; this does not mean observer overhead disappears under wall caps. Original raw failures remain separate. The geometry lane owns source derivation anchors, detailed work counters, observer accounting and proofs that template reuse reproduces exact occupancies. The wrapper adds no pruning, state merging, learned estimates or repeated rejected-route search.

Warm epochs explicitly reuse graph admission via `PreparedGraph`. Cold baseline uses raw graph admission in the primary solve again, preserving the original primary timing boundary. Warm source/hazard admission and all request checks still occur. Source snapshot reuse is not exposure-result reuse.

## Relaxed-road heuristic proof and exact arithmetic scope

The heuristic is the unchanged `core._lower_bounds`: reverse Dijkstra from every destination on the directed road graph, with edge weight `travel_ticks * dt`. It omits forbidden-turn state, waits, hazard/support/exposure constraints, destination openings, arrival admission rules and dwell. No edge direction is invented.

For any feasible continuation from a label at node `u`, remove waits and keep its directed edges. This is a directed walk to some destination. The least directed-road travel duration is at most that walk's travel duration and hence at most the continuation's remaining arrival duration. Every omitted restriction can only remove walks or add nonnegative waiting time; ignoring dwell cannot overestimate remaining arrival time. Thus `h(u)` is admissible. For every directed edge `u -> v`, `h(u) <= edge_duration + h(v)`; waits satisfy `h(u) <= dt + h(u)`. The same potential remains consistent when the search state includes incoming edge, exact time, admission flag and a vector of member doses. Zero at all destinations is valid despite later opening/dwell checks. An infinite value means no directed-road walk exists and cannot exclude a feasible continuation under the same graph.

The wrapper admits heuristic modes only with positive **integer** `dt`. Every edge weight and finite reverse-Dijkstra distance is therefore an exact Python integer. Positive edge weights imply that a shortest relaxed path is simple, so its duration is bounded by the sum of all graph edge durations. The guard checks, using exact `Fraction` arithmetic:

`abs(horizon) + abs(departure) + sum(edge.travel_ticks * dt) <= 2**53`,

with integer-valued represented horizon/departure. Existing lattice admission also runs. All finite generated schedule times and priorities are then representable exactly in binary64 where the inherited core uses floating times. The heap's `t + h(node)` cannot round upward or change ordering through rounding. Infinite disconnected priorities remain the exact no-path case. Noninteger/dyadic `dt` and graphs outside this conservative envelope are explicitly unresolved/unsupported for this experiment's heuristic dispatch; the wrapper does not silently round, scale or replace the old heuristic. This is a bounded supported arithmetic scope, not a physical modelling change.

## Separate budgets, lifecycle and primary outcomes

Primary search limits are copied without subtraction or expansion. In particular, the original 30-second solve cap includes the solver's own admission/preprocessing, ordering, geometry binding/lookup, search and independent centre route checking. External source admission, bridge conversion, immutable epoch preparation, caller-owned geometry-cache construction and warm full-content validation are separately measured. They are included in the combined lifecycle and cannot be presented as free. Preparation is not silently deducted from the original solve cap. No shared-30 cold diagnostic replaces these primary comparisons.

Whole-road checking gets a separate 30-second budget. HybridChecker construction begins inside that budget. Final integration authority and metadata work following the road check are also subject to its final guard; a late positive road result is preserved only as secondary evidence beneath primary road `UNRESOLVED`. One final clock value both gates that result and defines the lifecycle endpoint. Wall caps must be finite, nonnegative, non-Boolean numeric values. The checking flag must be an actual Boolean.

Timing fields identify request dispatch, epoch preparation/validation, source rebridge phases on cold runs, owned snapshot decoding, heuristic envelope checks, geometry-cache preparation, primary solve, whole-road checking, final authority verification and cache inspection. Core metrics supply the detailed work/timing breakdown. `combined_lifecycle_wall_s` covers the run call; the session's constructor is separately reported and charged once in `combined_lifecycle_including_constructor_wall_s`. One-shot `run_search` measures its complete constructor-plus-run lifecycle directly. `epoch_original_preparation_wall_s` is historical prep evidence for explicitly preconstructed epochs; callers must charge that when claiming cold full lifecycle. Process lifetime RSS is a common process high-water mark, not an exclusive engine heap measurement; owned epoch byte counts and geometry-template storage are reported separately.

Raw `primary_search` is retained. Road checking receives only a complete solver-returned route with `checker.ok is True`, or an explicit `TIMEOUT` `checked_incumbent` with that same independent-check success. An unchecked candidate is never promoted. Motion, issue state, waits, incurred history and destination dwell are passed to the accepted full-mission checker unchanged. No search is repeated after a road rejection.

The output separates primary centre status, whole-road status and integrated status:

- Positive whole-road certification yields a conditional integrated witness, with `road_optimality_claim=False` and no global road refusal claim.
- A checked timeout incumbent can yield `TIMEOUT_WITH_CHECKED_INTEGRATED_WITNESS`; the primary search remains `TIMEOUT`, with unresolved optimum.
- Definite rejection describes this proposed witness only; it does not prove that all road routes fail.
- Centre `CONDITIONAL_OPTIMUM`, `PROVEN_INFEASIBLE` and `DISCONNECTED` remain their raw centre-contract outcomes. They are not global road-optimum/refusal certificates.
- Binding failures retain raw primary evidence but disable wrapper-authorized centre/integrated claims. Missing sources, support or arithmetic scope remain unresolved; none is zero-filled.

## Bounded development verification and retained corrections

The author suite is `tests/search_development.py`: 13 test methods, including 17 known independent reference fixture controls across four modes and cold/warm use (136 paired search calls), exact relaxed distances against separate simple-path enumeration, consistency inequalities, integer-envelope boundaries, fresh version/member/incurred/turn admission, fixed caps, immutable snapshots, full source-byte invalidation, exact bridge equality, explicit replacement, input mutation after search, strict checker caps and secondary checked-incumbent handling. The combustion model and imported package initializers are included in implementation binding. All pass. These are development checks, not fresh confirmation or physical validation.

Pre-seal corrections are retained here with their original conditions:

1. Independent review identified a float sum in the priority-envelope guard: near `2**53`, `2**53 + 1` could round down. The guard now sums exact `Fraction` values; the boundary regression rejects it. The heuristic itself remains the inherited implementation.
2. External request pre-validation initially made heuristic modes report `NOT_RUN` for stale versions/member mismatches that other modes returned as normal solver refusals. That redundant pre-validation was removed. Solver admission now preserves those statuses in all four modes.
3. Initial wrapper-authorized centre optimum reporting could survive final input-authority failure. Raw primary evidence remains, but the authorized claim now requires final binding success.
4. Final cache/RSS metadata initially followed the last content guard. Final full binding now occurs after that metadata, and cap gating uses one final endpoint clock. Checker cap/flag types are explicitly validated.
5. The first author synthetic source-binding test used parent SHA `test-parent`; the unchanged forecast bridge correctly rejected it with `CONSTRUCTION_PROVENANCE` (64 lowercase hex characters required). The fixture now uses an explicitly synthetic 64-hex identifier. This was a malformed test fixture, not a bridge or routing defect.
6. The initial reviewer reference fixture omitted required objective `earliest_arrival`; the reviewer corrected its own fixture. No admission rule was relaxed.

No fresh confirmation outcomes were accessed during selection or these corrections. Original source arrays, physical assumptions and checker settings are unchanged. Fresh incident benefit, meaningful search-produced multi-edge integration and independent proof gates remain coordinator/reviewer responsibilities.

7. A real original v2 development packet demonstrated `NOT_RUN / ADMITTED_HAZARD_NOT_EXACT_SOURCE_BRIDGE` in every mode. The wrapper incorrectly selected constructor event IDs (`constructed:...`) rather than the original hourly integration's routing IDs (`construction:<construction_id[:20]>:<array index>`). The corrected adapter derives only that original namespace, validates admitted hazard order and report request histories/budget order, and retains array-index correspondence. No source, hazard, budget, incurred exposure or physical assumption was changed. Full pre-correction source and SHA are preserved at `results/corrections/search_followup_pre_identity_correction.py.txt`; the classification and correction record are `results/corrections/search_source_identity_correction.json`. The author regression prepares the unchanged real baseline03 packet and rejects reversed member order, reversed report ledger order and altered construction identity.
8. The initial legacy synthetic binding fixture retained `RESEARCH_CONSTRUCTION` with native v1; the unchanged bridge correctly rejected it (`CONSTRUCTION_PROVENANCE`: research construction requires v2 provenance). It is now explicitly `LABELLED_FIXTURE`, as its synthetic source-binding-only scope requires. This does not change any incident metadata or physical source.

9. Independent negative provenance review identified that a new epoch could accept a forged 64-hex construction identity when admitted/report member names were coherently relabelled. The adapter now recomputes the exact original `hourly.build_hazard` construction digest before accepting its routing namespace. The unchanged real baseline03 packet passes; the coherent all-zero forged identity regression fails closed with `SOURCE_HOURLY_CONSTRUCTION_DIGEST_MISMATCH`. No array, ledger value, ordering, budget, heuristic or physical parameter changed. The measured pre-guard development `modes_v2` outcomes remain preserved as pre-guard diagnostics. Full pre-guard module source/SHA are retained at `results/corrections/search_followup_pre_digest_guard.py.txt` and `results/corrections/search_construction_digest_guard.json`.
