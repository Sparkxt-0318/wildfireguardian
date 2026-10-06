# Routing library and mentor adapter

Run `python -B run.py check` for packaged integration tests. `python -B run.py solve --input fixtures/example.json` emits JSON. `python -B run.py replay --input evidence/CONTINUITY_REPLAY_FIXTURE.json` demonstrates update/continuity/return. Python 3.11 standard library suffices for integration; the historical vector benchmark additionally needs NumPy. No HTTP deployment is required.

Library: `routing.core.solve(graph,hazard,request)`; `routing.service.plan_with_return(graph,hazard,request,history,endpoint,return_budget_s=5)`; `routing.session.RoutingSession(graph)`; independent `routing.independent.check_route` and bounded `exhaustive`. `baseline` is the adapter default. Optional `routing.optimization.solve` is a separate experimental arm.

## Actual payload validation
The complete runnable example is `fixtures/example.json`. It is labelled `LABELLED_FIXTURE`, never a sample supplied by the mentor. Supported hazard schema `wfg.routing.edgegrid/1` requires graph revision, matching projected CRS/regular grid, dt, UTC-aware issue/availability/time-origin timestamps, validity seconds, provenance, evidence class, explicit channels and absent channels, and members with unique IDs. Each member contains increasing breakpoints and interval×row-major-cell flux/flame/support arrays, all dimensioned over the **entire** grid. The schema fixes seconds, kW/m² and kJ/m²; an optional units object must match exactly. Graph contains nodes, directed edges with positive travel ticks and coordinate-derived cell segments, explicit forbidden turns and mid-edge reversal policy.

Requests contain current node or interior directed-edge fraction, incoming edge, departure/horizon absolute mission seconds, candidate destinations with dwell/openings, incurred dose keyed by member, hazard version, causal as-of time, `earliest_arrival`, explicit dose scope, member dose/peak budgets and wall/label/expansion/frontier caps (RSS defaults 3072MB). Return endpoint/history and separate return-check wall budget are supplied to the facade. The validators reject malformed arrays/numbers/masks, geography/road alignment, temporal coverage, stale/unavailable metadata, wrong identities/versions/units and unsupported quantities. False support is preserved explicitly, not converted to zero hazard.

Results carry status/reason, directed edge legs/times/waits/fractions, arrival/destination, per-member dose/peak checks, raw solver state/caps, metrics, provenance and certificate assumptions. CONDITIONAL_OPTIMUM is a supported declared-lattice certificate; CHECKED_ROUTE is a weaker witness; PROVEN_INFEASIBLE requires exact supported exhaustion; DISCONNECTED is structural; AT_ISSUE_FAILURE is a current violation; UNSUPPORTED/INVALID_INPUT/TIMEOUT remain distinct. A checked route satisfies modeled constraints, not physical safety.

## What the mentor must supply
1. One real sample/file or API response and schema/model version, with stable scenario identities.
2. Graph revision binding, projected CRS/grid coordinates/resolution, full spatial alignment and explicit support covering road occupancy and destination dwell.
3. Flame-contact Boolean intervals and **incident heat flux on the declared vehicle proxy**, in kW/m², with finite nonnegative values and increasing time breakpoints.
4. Issue, availability, validity and common time-origin semantics; provenance/physical interpretation and absent channels.
5. Scenario-change carry-forward bounds if IDs change; an observed/estimated incurred-dose source; separately agreed routing peak/dose/dwell policy.

The narrow adapter accepts that already compatible payload after full validation. Native array/tile formats can be decoded into this schema without changing routing search; their decoder must preserve units/support/time/geometry and be checked with an actual sample. Detection probability, arrival time, FRP, radiance and fireline intensity are **unsupported thermal quantities**. A flame/arrival-only forecast cannot be silently turned into incident heat flux; thermal support remains unavailable until an explicit defensible exposure adapter exists. Passing JSON schema is engineering admission, not forecast calibration or real-fire validation. Actual forecast integration remains NOT AVAILABLE.

## Session and fallback example
Create a session, accept a validated hazard, set actual progress including full traversed history, then plan and commit. `commit` checks accepted hazard version, current generation, request identity and independent admissibility. A new update invalidates earlier completions. `retained_plan` rechecks before display and labels an older accepted version following rejected updates. `reset` explicitly clears mission/history state. Changed member IDs require explicit conservative bounds; original dose never resets automatically. Time-origin changes require reset.

The replay shows an initial OA–AD plan, support loss forcing OB–BD, progress to B with nonzero histories, a checked BO return, missing support refusing return, stale updates and reset. It is deterministic after runtime metrics are removed; operational completion under resource limits is still runtime-dependent. Primary timeout and return-check outcome remain separate.

Session mutations and completion callbacks have one serialized owner, such as a single event loop. `RoutingSession` is not a thread-safe shared object. The version/generation check rejects delayed completions under this policy; a host that runs worker searches must serialize admission/progress/commit on the owner and pass immutable snapshots to workers. Simultaneous unsynchronized calls from multiple threads are outside the contract.


## Integration candidate lifecycle

Opt-in session, return facade and process-local replay integration is implemented in this isolated candidate. See [PREPARATION_LIFECYCLE.md](PREPARATION_LIFECYCLE.md) for ownership, checked mutable authority, atomic replacement/reset, initialization costs and CLI options. Raw APIs and the established separate research planner recommendation remain available.
