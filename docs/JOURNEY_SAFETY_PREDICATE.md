# Journey-safety predicate

Track 1C-2. This is the mathematical statement that the planners (frozen sweep, SIPP) relax and that the checkers decide, with one requirement identifier per clause, traced to the frozen checker, to the independent implementation `experimental/sipp-routing/src/wfg_sipp/predicate.py`, and to tests. "Safe" in this document is a technical term: the journey satisfies every clause under the supplied members, lattice, horizon and construction law. It is not a statement about physical safety; no clause has been compared with field measurements.

## Definitions

- Graph: directed edges j with tail u_j, head v_j and integer travel time D_j (s); forbidden turn pairs (i, j); waitable flags per node. Time is in integer seconds from the forecast cutoff (dt = 1 s).
- Request: issue node o, incoming edge i_0 (or none), departure t_dep, horizon H, destinations d with dwell w_d and openings O_d, peak limit P (kW/m2), dose budget B_m and incurred dose I_m per member m, exposure scope (including or excluding the dwell).
- Member m: per cell c, half-open activity intervals A_m(c) (flaming); centre flux q_m(c, t) (kW/m2), piecewise constant on the member's breakpoints. A set S of members is the planning or acceptance set.
- Occupancy: for an EDGE leg on j entered at s, the closed spans (c, [s + D z_a, s + D z_b]) of the unit-clock occupancies of j (open sub-segments between grid-line cuts with the midpoint cell, every cut point with its floor cell); for a WAIT leg [a, b] at node n, the span (cell(n), [a, b]); for the dwell, (cell(d), [t_arr, t_arr + w_d]); the issue point (cell(o), [t_dep, t_dep]).
- Contact of a span (c, [x, y]) with member m: some [b, e) in A_m(c) with x < e and y >= b. (The frozen checker samples flame at x, y and every breakpoint strictly between; on the packets' piecewise-constant flame rows this is the same rule.)
- A journey J is a sequence of legs (EDGE j, s, e) or (WAIT n, s, e) and an arrival second t_arr.

## Predicate

J is safe under S iff all of the following hold.

| Id | Clause |
|---|---|
| JS-1 | Departure at or after issue: the first leg starts at t_dep. |
| JS-2 | Legs are contiguous: each leg starts when the previous one ends. |
| JS-3 | Times are monotone and bounded: every leg has e > s, and e <= H. |
| JS-4 | An EDGE leg on j lasts exactly D_j. |
| JS-5 | Turn restrictions and continuity: an EDGE leg leaves the current node, and (previous edge, j) is not forbidden. |
| JS-6 | WAIT legs occur only at waitable nodes. |
| JS-7 | Node waits lie inside node safe intervals: no WAIT span has contact with any m in S. |
| JS-8 | No traversal window meets a member's unsafe interval of that edge: no EDGE span has contact with any m in S (equivalently, every departure second lies in the edge's safe departure set for every m in S). |
| JS-9 | Peak: for every m in S, the centre flux sampled on every span (legs, dwell, issue) is at most P. |
| JS-10 | Dose: for every m in S, I_m + the integral of q_m over the leg spans (plus the dwell span when the scope includes the dwell) is at most B_m. |
| JS-11 | Destination: the last leg is an EDGE arrival (admission) at a destination d at t_arr, with some [o_1, o_2] in O_d such that o_1 <= t_arr and t_arr + w_d <= o_2, t_arr + w_d <= H, and no contact on the dwell span for any m in S. |
| JS-12 | At issue: no contact at the issue point for any m in S, and I_m <= B_m for every m in S. |

Acceptance (Contract D). The mission passes under rule `all` iff J is safe under every retained member; under `k_of_m` iff the members in which J is safe carry at least the fraction k/m of the retained weight. Monotonicity used by the planners: if J is safe under S it is safe under every subset of S, and J is safe under the union member of S (the member whose activity sets are the unions) iff it satisfies JS-7, JS-8, JS-11 and JS-12 for every member of S (the contact clauses are unions; peak and dose are per member and are not unions).

## Traceability

| Id | Frozen checker (`routing/independent.py` in the kit, imported unchanged) | Frozen relaxation (`phaseB/zsweep.py`) | Independent implementation (`wfg_sipp.predicate`) and the SIPP front end | Tests |
|---|---|---|---|---|
| JS-1 | `_shape`: first leg start equals `request["departure"]` | sweep starts at `dep` | `violations` JS-1; `sipp.solve` starts at `departure` | `test_predicate.py::test_each_requirement_is_detected`; `test_sipp_property.py` (witnesses pass `predicate.safe` and `bruteforce.check_legs`) |
| JS-2 | `_shape`: "noncontiguous or nonpositive leg" | lattice transitions | JS-2; `sipp._reconstruct` | same |
| JS-3 | `_shape`: "noncontiguous or nonpositive leg", "horizon exceeded" | `end <= hor`, `t + 1 <= hor` | JS-3; successor and component bounds | same |
| JS-4 | `_shape`: "edge travel duration mismatch" | `D = travel_ticks * dt` | JS-4; `Instance.D` | same |
| JS-5 | `_shape`: "edge discontinuity", "forbidden turn" | `preds` with `forbidden` | JS-5; `Instance.successors` | same; `test_relabelling_edges_and_nodes_changes_nothing` |
| JS-6 | `_shape`: "illegal wait" | `waitable` mask | JS-6; `component_end` | same |
| JS-7 | `check_route` / `_charge` on WAIT spans (FLAME_CONTACT) | `wmat` wait mask | JS-7; `frontend.build_instance` wait blocks | `test_each_requirement_is_detected`; `test_union_certificate_holds_for_each_member_and_every_subset`; `test_geometric_vs_frozen_sweep.py` |
| JS-8 | `check_route` / `_charge` on EDGE spans | `eblock` departure mask | JS-8; `frontend.build_instance` edge blocks | same, plus `test_adding_unsafe_intervals_never_decreases_the_optimal_arrival` and the 20-mission panel comparison |
| JS-9 | `check_route`: PEAK_BUDGET | relaxed (zero mode) | JS-9; checked after planning (`wfg_members.check`, `wfg_members.coverage`) | `test_each_requirement_is_detected`; `experimental/scenario-members/tests/test_decisions.py` (one-pass and per-member frozen checks agree) |
| JS-10 | `check_route`: DOSE_BUDGET (incurred added once; dwell by scope) | relaxed (zero mode) | JS-10; lazy constraints in `wfg_members.decide` | `test_each_requirement_is_detected`; `test_dwell_dose_counts_only_when_requested`; `test_cheap_checker_agrees_with_the_frozen_checker_on_built_members` |
| JS-11 | `_shape`: "route does not end at destination admission", "destination dwell horizon or opening violation"; `_charge` on the dwell span | `dest_ok` | JS-11; `frontend.build_instance` acceptance sets | `test_each_requirement_is_detected`; property and geometric tests |
| JS-12 | `check_route`: AT_ISSUE_FAILURE | AT_ISSUE check | JS-12; `frontend.sipp_plan` AT_ISSUE check | `test_each_requirement_is_detected` |

## Design frame

The planner is the unassured complex function and the checker is the assured monitor (a certifying algorithm in the sense of McConnell, Mehlhorn, Naher and Schweitzer 2011): no journey is reported as a checked route unless the checker accepts it, and any computation that does not finish (time cap, subset cap, lazy-constraint cap) is reported as unresolved, the recovery output of the runtime-assurance pattern (ASTM F3269-21). An unresolved outcome is never counted as a route or as a refusal.
