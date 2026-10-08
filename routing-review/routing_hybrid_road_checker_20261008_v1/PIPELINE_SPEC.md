# Hybrid fixed-mission pipeline and cache contract, version 1

The accepted API, subject to independent review and frozen confirmation, is `hybrid_checker.HybridChecker(case_directory, settings=None).check(graph, request, legs, destination, *, wall_s=30, deadline=None, expected_graph_revision=None, expected_graph_sha256=None)`. It is a separately versioned opt-in candidate. It does not replace the practical checker, strong rational comparator, original router or defaults. This pipeline performs fixed-witness checking, not search, optimality proof or graph-wide infeasibility proof.

## Complete charged checking sequence

The check starts its clock before dispatch, input hashes, any source preparation, graph snapshot/binding, contact checking, radiation preparation, geometry-cache inspection or radiation evaluation. An external deadline is intersected with the local cap, never extended. The primary comparison uses the unchanged 30 seconds. After checking, source and mission authority are rechecked and result finalization is charged before the final cap gate. A completed numerical result that crosses the deadline is retained only as a labelled secondary checked result; primary status is `UNRESOLVED`. The measured lifetime-RSS limit remains 3072 MiB and fails closed; it is not an operating-system allocation ceiling.

The stages are:

1. Bind immutable numerical settings and the explicitly owned case directory.
2. Hash the original source packet and complete source report; prepare or reuse the immutable owned contact snapshot.
3. Snapshot the supplied graph, request and legs, bind graph revision/content, and validate complete mission grammar.
4. Run exact closed-footprint contact clipping over departure, every moving chord, waits, arrival and full required dwell. A supported exact contact witness can reject without radiation work.
5. For complete contact-clear missions, prepare or reuse `HybridRadiationBounds` from the same unchanged source packet/report and numerical settings; evaluate peak/dose bounds with the request's unchanged member budgets and incurred histories.
6. Rehash source authority, settings and original graph/request/legs before returning; reject mutation with `UNRESOLVED`.
7. Charge metadata/result finalization and apply the final deadline/RSS gate.

`CERTIFIED_ADMISSIBLE` requires valid complete mission grammar, complete supported contact clearance and `CERTIFIED_RADIATION` from the numerical enclosure. `DEFINITE_REJECT` requires a supported exact contact witness or the radiation module's justified lower-bound violation. Any incomplete support, unsupported grammar/geometry, bound straddle, cap or authority change remains `UNRESOLVED`. No missing probability/source/history is reset or zero-filled. Incurred dose is passed unchanged to the radiation module. An equality decision must be based on the module's justified upper/lower bound semantics, not a displayed rounded value.

The inherited mission validator preserves graph-node/chord interpretation, incoming-edge context across waits, turn restrictions, timestamps, travel durations, temporal lattice/support horizon and complete destination dwell/opening. Partial-edge positions or unsupported mission grammar remain unresolved. Exact contact uses rational line/closed-rectangle clipping and half-open source phases. Those mathematical and physical contracts are inherited unchanged; this wrapper supplies no new physical assumption.

## Owned cache epochs and dependency handling

A checker owns one case-directory, source/report content, graph-content and numerical-settings epoch. Calls and authority writes must be serialized by the owner; the wrapper is not a thread-safe source-update scheduler. The frozen source/report and bound graph are immutable authority during a supported call. Before/after content guards detect persistent mutation; they are not a proof against an external actor modifying and restoring authority between probes. Such concurrent mutation is outside the supported ownership contract. Physical parameters, durations/current lifetime, future probabilities/provenance, event times, current mask, source support, affine geometry, scenario IDs, evidence/version metadata and numerical settings are covered by the complete packet/report hashes and settings digest. The first valid graph binds its full canonical content hash. A change to any source/report/graph/settings/directory dependency refuses the operation and requires explicit construction of a new checker. There is no automatic cache reset, source replacement or favourable fallback. Source/graph/settings authority is rechecked after numerical work to catch mutation during a check.

Contact snapshots own immutable tuple state and have no contact-result cache. Contact is checked completely on every call. The wrapper has no request-result cache. Different valid request budgets/incurred histories, departure/legs or dwell are validated and evaluated anew. The numerical module may reuse geometry enclosures only under its separately proven immutable source/settings identity and exact receiver-box keys; temporal overlap, dose accumulation and threshold decisions are recalculated. Reusing geometric bounds must not reuse a previous mission's admissibility conclusion.

The source/radiation epoch checks are conservative: even a metadata-only report change invalidates the wrapper epoch. Conversely, changing a request budget does not require throwing away compatible geometric enclosures, provided the changed request is recomputed. Returning the source packet to exactly its original bytes permits using the unchanged original epoch; this is not a reset or acceptance of the intervening changed packet.

Numerical hybrid dispatch, compatible enclosure intersection, source/receiver refinement and directed rounding are owned by the separate radiation lane. `HybridRadiationBounds` exports `DEFAULT_SETTINGS`, `from_case`, `trajectory_bound` and `cache_info` with the inherited radiation API. The wrapper accepts `CERTIFIED_RADIATION`, `DEFINITE_REJECT` or `UNRESOLVED`; it never promotes a sampled peak or an incomplete numerical result.

## Reporting complete work

`elapsed_s` is the primary complete-check wall time, including preparation, binding, validation, contact, radiation and finalization. `timing_s` exposes dispatch/settings binding, source content hashing, contact-source preparation, aggregate source preparation/binding, complete mission validation, contact, radiation preparation/checking, cache inspection before/after radiation, final authority verification and wrapper finalization. The aggregate source preparation/binding interval intentionally contains its hashing/preparation subintervals; **do not sum overlapping timing fields**. Substage sums plus overhead need not equal complete elapsed time exactly.

`cache_work` identifies cold/warm source and radiation-object reuse, no contact/request-result cache, source binding and numerical cache snapshots before/after checking. Radiation cache details separately report hits/misses/retained numeric bytes and numerical dispatch/refinement/source work. Process-lifetime RSS includes earlier preparation/work in that process. Constructor wall work is recorded as `constructor_wall_s`; the API constructor precedes `check`, so the coordinator's cold panel driver must start the shared deadline before construction and charge constructor work inside that budget. Imports, external source construction, freeze verification and input parsing must also be measured explicitly by that driver. They must not disappear from performance claims or be attributed selectively to one checker. No source construction or prediction inference is performed by this wrapper.

## Explicit shadow integration boundary

`hybrid_shadow.HybridShadowWitnessAdapter` is optional and disabled by default. The caller captures `bind_witness_context(case_directory, graph, request)` before a serialized primary-router operation. Shadow checking binds the full graph revision/content, source/report content and request digest to that context. It requires a supplied complete witness and a separately declared witness-check budget. Context hashing, checker preparation, checking, mutation checks and shadow finalization share that budget.

A primary `TIMEOUT` remains `TIMEOUT`; only an explicitly checked incumbent can be inspected as a secondary witness. Primary `UNSUPPORTED` and every other router outcome remain byte-content-equivalent in the returned copied primary report. A hybrid witness certificate cannot resolve a primary search timeout, establish optimality or replace the default. The adapter neither schedules concurrent router work nor provides a thread-safe ownership protocol; the caller must serialize authority. Availability of this module is not automatic promotion or acceptance of Stage 2 integration.

## Development checks and frozen-confirmation discipline

`tests/hybrid_wrapper_checks.py` exercises generated authority controls only, explicitly labelled as generated controls rather than incident or physical evidence. It checks cold/warm complete-work reporting, original incurred-dose equality/violation, every source-assumption key, source arrays/support/current state/member IDs/affine/provenance, graph geometry/revision/timing/turn/waitability, every numerical setting, directory changes, request/witness changes, mutation during checking, caps/RSS and shadow primary-outcome preservation. All old incident/control cases are development only. The coordinator owns three-checker development comparisons, implementation/input freezes and fresh panel reconciliation.

No fresh confirmation input or outcome is opened by this wrapper lane before coordinator seal authorization. Any correctness repair after opening would invalidate promotion from that panel and require a separately frozen fresh confirmation. Sealed inherited modules remain unchanged.

Run owned wrapper development checks from the isolated directory:

```sh
python -B tests/hybrid_wrapper_checks.py
```

Raw owned results are written to `development/wrapper_checks.json`. Independent review and fresh practical acceptance remain required before a narrowly scoped GO. Default promotion remains outside this experiment.

## Owned development result and source evidence

The pipeline/cache suite passed **72 development controls** before fresh confirmation. Raw records are retained in `development/wrapper_checks.json` and stdout in `development/wrapper_checks.log`. The constructor-cost metadata clarification is preserved in `development/wrapper_metadata_correction.json`; it changes reporting scope, not numerical or acceptance semantics. The full inherited incident/control comparison is coordinator-owned, so this lane does not rerun a duplicate comparison or claim fresh benefit from these controls.

Candidate graph project `routing_hybrid_road_checker_20261008_v1-candidate` was ready at generation `2026-10-08T07:47:22Z`. A three-hit symbol lookup for HybridChecker, its settings digest and HybridShadowWitnessAdapter was complete. The checker both-direction one-hop trace recorded 14 callees and one shadow-adapter caller. The shadow exact source snippet was read. Coverage of the wrapper/shadow/inherited practical/contact/mission/radial paths reported no recorded issue; the wrapper was metadata-changed after its reporting clarification and its complete current source was reread directly. Graph evidence is best-effort, not a completeness proof; the coordinator must refresh changed modules before seal. Tests and specs lie outside the candidate graph and were read directly.

The pre-confirmation fault-injection record `development/wrapper_rejected_arithmetic_guard.json` demonstrates that the initial derived wrapper propagated the numerical module's `ArithmeticError` instead of returning the required unresolved status. Its original code is retained as `development/wrapper_pre_arithmetic_guard.py`. The owned wrapper now maps such a numerical invariant failure to `UNRESOLVED` while retaining partial checking evidence. This is a pipeline API repair, not an observed inconsistency on incident inputs or a modification of numerical enclosures/source laws. The additional guard test passes.
