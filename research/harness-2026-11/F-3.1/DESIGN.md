# F-3.1 Deadline field: backward-search state, transition and dominance rule

Status: **decision draft, sent for verification (Hannah) and assessment (Iris)**. Nothing below is a measured result.

## 1 The forward problem being inverted (as implemented, not as described)

These are the transitions of the kit's full-policy router (`integration/kit/phaseB/road_core.py::solve`, the same as
`routing-package/routing/core.py::solve`). The kit's own contact-only lower bound uses the same transitions
(`zsweep.py::EarliestArrivalBound`).

* Label (node v, incoming edge e or None, integer second t, admission flag, per-member dose). One tick is 1 s.
* EDGE j out of v, allowed iff (e, j) is not in `forbidden_turns` (e = None at the origin): occupancy
  [t, t + D_j], with end ≤ horizon H. The result is admission = **true**.
* WAIT: only if v is `waitable` and t + 1 ≤ H. It keeps e and sets admission = **false** (a wait never re-admits).
* Accept at destination node d when a popped label has admission = true, an opening [a, b] with a ≤ t and
  t + dwell ≤ b, t + dwell ≤ H, and an admissible DWELL [t, t + dwell] (here `including_dwell`).
* The initial label is (origin, None, dep, admission = true). Origin = destination never happens in the cache.
* Admissible means no flame contact (router rule) and peak ≤ 10, with dose accumulated ≤ 100 per member.

## 2 Reduction of the full policy to contact (checked precondition, not an assumption)

On the six planner packets: (i) the maximum flux over all cells, bins and members is ≤ 0.702 kW/m², below the
10 kW/m² peak limit, so peak never binds. (ii) The maximum flux over non-flame (cell, bin) pairs is ≤ 0.01555 kW/m².
(iii) The router samples every bin that an occupancy integrates (lo, hi and every interior breakpoint), so a
journey with no router contact integrates only non-flame flux. Its dose is therefore ≤ 0.01555 × 3600 = 56 kJ/m²,
below 100, for every planner request (incurred dose 0, journey ⊆ [0, 3600]).

Hence, for these inputs, **full-policy feasible = router-contact feasible**. The precondition is recomputed and
asserted per packet at run time. If it fails (other packets, nonzero incurred dose), the field becomes a relaxation
only, and every witness must pass the dose/peak checker (`routing.independent.check_route`) before it counts.

## 3 Backward state and set equations (no dominance on time at all)

State s = an edge index (the vehicle sits at head(s), having arrived over s), plus one issue state per origin.
Admission is not a state component: it is true exactly on arrival over an edge and false after any WAIT. The
backward object for a fixed destination set is, per state,

    R_s ⊆ {0..H}: the departure seconds t such that, standing at state s at time t (admission false), some
          admissible completion is accepted at a destination.
    A_s ⊆ {0..H}: arrival seconds t at which arriving over s is accepted (head(s) is a destination, the opening
          and horizon fit, and the dwell is contact-free).
    G_s = R_s ∪ A_s: arrival seconds over s from which success is possible.

    R_s = ⋃_{j: tail(j)=head(s), (s,j) allowed} { t : t ∉ B_j, t + D_j ∈ G_j }
        ∪ { t : head(s) waitable, t ∉ W_head(s), t + 1 ∈ R_s }

B_j is the set of integer start seconds at which EDGE j has contact (router rule; in the "certified" variant, router
rule ∪ closed-footprint rule). W_v is the set of seconds at which WAIT [t, t + 1] at v has contact. Each B, W and A
is a finite union of integer intervals computed exactly from phases with rational arithmetic. Under the closed
occupancy / half-open phase rule, start t meets the phase [b, x) on a relative occupancy [enter, leave] iff
t ∈ [⌈b − leave⌉, ⌈x − enter⌉ − 1]. This is the same formula as the kit's `EarliestArrivalBound` masks.

Origin o at departure t is feasible iff the issue point is clear at t and t ∈ R_issue(o), where R_issue uses the same
equation with incoming = None.

**Why this is exact.** Every transition strictly increases time (D_j ≥ 1, WAIT = +1 s). The time-expanded graph is
therefore acyclic, and the system has a unique fixed point: the set of time-expanded states from which an accepting
state is reachable. This equals the dense backward DP over seconds (kit `EarliestArrivalBound`, which stores the
earliest arrival in place of a membership bit).

**Why there is no dominance step to get wrong.** The SIPP notes say plain earliest-arrival dominance is invalid at
non-waitable nodes, because arriving earlier is not better when you cannot wait. The backward analogue would be
"departing later is not worse", and it is equally invalid. The design avoids both: it keeps the **whole set** R_s, a
sorted list of disjoint integer intervals, never a scalar latest-departure label. Admission is handled by the split
R versus A (acceptance only on arrival over an edge, never after a wait). Opening windows and the dwell enter only
through A. The waiting closure is exact: if R_s gains [lo, hi] at a waitable head, it also gains
[w + 1, lo − 1], where w is the largest wait-blocked second below lo.

## 4 Algorithm (event-driven least fixed point)

Seed with the A_j of edges into the destination. Keep a heap of new pieces (state, [lo, hi]) ordered by
descending hi. For a new piece of G_j, each allowed predecessor s gets (([lo, hi] − D_j) ∩ [0, H]) \ B_j \ R_s,
closed under waiting, then pushed. This is chaotic iteration of a monotone operator on a finite lattice, so it
reaches the least fixed point, and the fixed point is unique (acyclicity). The processing order affects only speed.

* With no hazards, every R_s is one interval and the run is a reverse Dijkstra on latest departure.
* Hazards fragment only the states whose futures cross blocked intervals.

The cost is proportional to the number of interval pieces, not to H × |E|.

Per origin and shelter: the latest feasible departure is LD = max(R_issue ∩ clear-issue seconds). The planner grid
answer is the largest offset in that set, and the deadline is the max over the origin's three shelters. For a
departure t, a forward Dijkstra on time over the time-expanded graph, pruned to G, returns the earliest arrival and a
witness journey. Every witness is replayed with both contact rules (`tools/explain_deadlines/replay.py`) and the
kit-independent checker. That replay is the exactness certificate per origin. The field is a "dual certificate" for
Thomas: each R_s/B_j piece list, with the per-edge blocked interval and its (member, cell, phase) cause, proves
infeasibility of any departure outside R_issue.

## 5 Verification plan (before scaling)

1. Brute-force oracle (forward exhaustive time-expanded search per departure second) on random small networks.
   It covers non-waitable nodes, forbidden turns, opening windows, dwell blocks, issue blocks and cycles, and is
   property-tested (Hypothesis) for equality of R_issue and the earliest arrival at every second.
2. Real data: compare the interval masks B/W/A against `Packet.contact_router` / `contact_closed`, evaluated
   directly per second on every edge that touches a burning cell.
3. Second implementation on real data: a dense numpy bitset sweep over seconds, with the same equations.
4. Reproduce the planner cache:
   * every recorded model_no_route ⇒ R_issue ∌ t (router field);
   * every checked_route ⇒ t ∈ R_issue, with an equal earliest arrival;
   * recorded deadlines at the 10-min grid match;
   * unresolved and AT_ISSUE cells are reported separately.
