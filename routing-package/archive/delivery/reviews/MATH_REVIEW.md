# Independent mathematical review: pre-comparison record

Evidence class: independently authored finite contract reasoning and labelled fixtures. No field safety, stochastic confidence, empirical generality, or road-scale performance claim. Written before reading the new candidate solver. Historical generated-path graph coverage is unavailable/not tracked; no exhaustive code-discovery claim is made.

## Finite problem and reference

For valid finite graph G, finite horizon H, lattice step dt>0 and strictly positive integer edge durations, the timed-walk tree is finite. Its vertices retain node/occupied directed edge, incoming-edge turn context, absolute time, destination admission event, and the entire accumulated member dose vector. Each allowed node wait advances at least one tick. Circling edges are legal unless explicitly forbidden. Partial traversal duration is ceil(travel_ticks*(remaining fraction))*dt and the occupied fraction is spread uniformly over that duration. This rounding is a model choice, not an assertion about physical travel dynamics.

The independent reference enumerates timed walks without dominance or state merging in nondecreasing arrival time. It checks every candidate destination admission using its own continuity, turn, spatial/temporal occupancy, member budgets and opening/dwell checker. Therefore the first accepted route has minimal arrival among the enumerated finite contract set, provided support is complete. Noncompletion under its walk cap is **UNRESOLVED**. Missing support forbids a global optimality/infeasibility certificate even when a particular route is checkable. No-route after complete supported enumeration establishes contract infeasibility only.

## Dominance conditions and counterexamples

At identical (node, incoming edge, absolute time, admission event), a feasible label with componentwise smaller/equal incurred-plus-route member doses dominates another label for earliest arrival, because the identical future continuation adds identical nonnegative member doses and tests identical occupancy/turn/opening conditions. Prior peak can be omitted from the resource order only after each label has passed the common fixed peak cap: future max peaks are checked independently. This does not establish dominance across different times, different incoming edges, different admission events, or by a scalar aggregate of member resources.

Earlier arrival at a nonwaitable node does not dominate a later arrival. A legal cycle can create the only allowed future destination admission; `legal_circling_nonwaitable_empty_layer_future_admission` exposes that failure. Waiting at a destination never creates an admission event. Merging its post-wait state into an edge-arrival state is unsound. Arrival layers can be empty while later states remain queued (positive multi-tick edges); an empty layer cannot terminate search. Forbidden-turn context belongs in the state: identical node/time/resources reached through different incoming edges can have different legal continuations.

## A-star / activation boundaries

A static shortest-travel-time lower bound that ignores hazards, exposure, opening times and dwell remains admissible for earliest arrival. Directed distances must respect edge direction; unreachable values require careful handling. Consistency follows static edge triangle inequality; wait actions leave spatial lower bound unchanged and increase time. Heuristic correctness alone says nothing about frontier truncation, activation completeness or resource-label retention. Optimal A-star termination requires all lower-bound-preferred legal states be considered until the first accepted goal is popped, or a complete certificate using the frontier lower bound. Resource truncation/timeout must remove optimality and infeasibility claims.

An activation solver is exact only if its active successor relation includes every feasible wait, directed edge and legal cycle, all future labels survive resource dominance correctly, and admission/turn context is retained. Pruning an apparently unsafe prefix can be valid only when independent occupancy rejection applies to that prefix; missing support is not zero exposure and cannot supply an impossibility proof. No activation advantage has been measured by this review.

## Occupancy / integration

Flame and incident flux must be checked over each entire closed occupied cell/time interval, including both cells at spatial boundaries and right-continuous values at temporal breakpoints. At the final support endpoint the last interval value applies. Flux dose is the integral over positive measure spans; point checks affect peak/flame/support but add no dose. Every member has its own dose cap; average/worst aggregated exposure cannot replace these constraints. Default route-only dose includes travel and waits, excludes destination dwell dose; dwell still needs flame/peak/support checks. `including_dwell` explicitly adds its integral. Incurred dose is never reset during replanning.

## Open verification

Root input validation must pass and coordinator must freeze the labelled case bytes before final candidate/reference comparisons. Implementation cross-review and benchmark completion remain pending. Independent reference search caps remain unresolved whenever reached. This review does not modify frozen historical protocols or use specialized sealed final cases.

## Post-freeze source cross-review

Root validated all 17 evaluation cases and froze their bytes before these comparisons. 51 comparisons (17 cases times baseline/Dijkstra/A-star) agreed on every arrival and feasibility outcome. Six rows retain an explicit status refinement: candidate `DISCONNECTED` versus reference `PROVEN_INFEASIBLE` for the two static turn-disconnected cases. No frozen expected value was edited to erase this difference.

Direct source reading of `routing/core.py` confirmed componentwise member-dose dominance keyed by `(node,incoming,time,admission)`, closed edge occupancy, destination dwell occupancy and exposure-scope handling, directed static-travel A-star lower bounds, complete future heap processing, and TIMEOUT on every label/frontier/expansion/wall cap. Invocation-local occupancy memoization includes edge/time or node/time/end and cannot cross hazard versions. Activation currently returns `UNSUPPORTED/ACTIVATION_NOT_PROMOTED`; no activation algorithm or speedup was validated. This bounded review found no material disagreement in those tested cases; it is not proof against every implementation defect.

Independent development tests additionally cover equal scalar-resource sums with opposing member-dose vectors, multi-tick future arrivals across empty layers, explicit reverse partial traversal/forbidden reversal turns, fraction-one endpoint normalization, malformed/nonfinite route legs, and right-continuous closure at exact arrival. The checker has no imports of core cost/dominance logic and rejects malformed route legs with INVALID_ROUTE. Validated input dictionaries are a precondition; this checker is not a replacement for the root schema validator.

Coverage check for all four relied/generated paths returned `coverage_unavailable/not_tracked`; the routing scope had no recorded entries or pagination. Graph generation was `2026-10-02T04:21:31Z` with truncated ignored-file metadata. Exact current source was read instead, so claims above rely on source and tiny tests rather than a fresh graph. Benchmark/performance, physical model validity, mentor payload availability and all reference noncompletion remain open. Arithmetic uses Python floating-point quantities and strict cap comparisons; numerical behavior at a threshold is part of this implementation's declared computational contract, not exact real-arithmetic certification.
