# Waiting-location sensitivity (rule, committed before any run)

Requested by the orchestrator (2026-11-12, 20:07 UTC), after Thomas's finding. On all 5 graphs, `node["waitable"]`
is true exactly for graph dead ends (one distinct neighbour), and no code or provenance states that rule.

## Label on existing tables

Every result table with NO_ROUTE, or with a deadline that depends on waiting, carries the line *"waiting is allowed
only at graph dead-end nodes (as supplied in graph.json; rule undocumented)"*.

## Sensitivity arm

* **Definition.** Every node is waitable: `PacketModel(..., waitable_all=True)`. The same flag is applied to the
  graph the unchanged full checker reads, so the field and the checker agree. Wait-point blocks are computed for every
  node by the same rule as before (a 1-second stay at the node point meets flame).
* **Label.** *"SENSITIVITY: waiting allowed at every node (not the supplied graph rule)"*. It is not a result in its
  own right and is never person-facing.
* **Expected direction.** Feasible sets can only grow, because waiting is optional. Any (origin, destination,
  departure) that is feasible under the supplied rule but infeasible with waiting everywhere is a **fault** and is
  listed.

## One-hour panel

* **Scope.** The 1-h planner caches of the three-way panel (9,722 jobs, 530 origins).
* **Field.** The optimistic (frozen packet) field, CERT and ROUTER, computed under the supplied rule and under the
  sensitivity arm.
* **Counts, per cache and in total, never pooled across regions in the headline line:**
  * job labels that change, as a from → to table (e.g. no_route → feasible);
  * NO_ROUTE verdicts that flip, with ROUTER counted separately;
  * origin deadlines that change, with the count and the median (upper) and maximum shift in seconds.

## Multi-hour

* **Scope.** The headline arm when it exists (v3.7 `no_reentry/2`). Until then, the `no_reentry/1` VARIANT packets,
  labelled as variant. 4 variants × 6 starts × {5 h, 8 h}.
* **Field.** CERT and ROUTER, no re-entry.
* **Counts:**
  * per (origin, destination, 30-min grid departure): verdict changes;
  * per origin: leave-by changes (count, median (upper) and maximum shift);
  * no-route → route flips, including how many had been labelled ROAD-LIMITED versus fire-limited.
* **Witnesses.** The new deadlines' witnesses are checked by the unchanged full checker on the waitable-everywhere
  graph. They are counted, and the counts are reported.

## Reporting

* Measured numbers only. Nothing here changes the frozen results or the headline tables. The sensitivity rows sit next
  to them.
* **Order.** These runs start after the current `no_reentry/1` variant batch finishes.

## Orchestrator decision on the owner's delegation, 13 Nov

**Waiting rule.** The supplied behaviour is kept as the documented default: waiting only at graph dead-end nodes.
- "Waiting allowed everywhere" is always reported as a labelled sensitivity row. This includes Marcus's finding that
  all 14 NO_ROUTE flip.
- No verified result changes.

**Plain-language wording: PENDING the orchestrator's confirmation.** The proposed wording was "wait before leaving at
the start place; no stopping mid-route". Richard flagged at 00:12 UTC that it does not match the graphs:
- 20 of 88 Uiseong start nodes are dead ends; 27 of 94 Yeongdeok start nodes are.
- 534 of 554 Uiseong dead ends are not start nodes; 1,500 of 1,527 Yeongdeok dead ends are not.
- The field chooses departure freely.

Richard's proposed wording: "Departure time is free (equivalent to waiting at the start place before leaving). Once
moving, a stop is allowed only at a road dead end (graph dead-end node), which may be a short detour off the route.
Waiting is not allowed at any other node."

**One-hour unknown-area headline tier (same decision).** 8.2 km/h.
- Labelled an assumption from an oral briefing figure. The written figure is ≈ 4.2 km/h; the detections give 7.0 km/h.
- 16.4 km/h and Tier A are shown beside it as sensitivity.
- One-hour tool only.
