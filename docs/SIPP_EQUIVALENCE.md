# SIPP and the contact-only lattice sweep: why they return the same answer

Track 1C-2. Code: `experimental/sipp-routing/src/wfg_sipp/` (`sipp.py` search, `frontend.py` geometry, `bruteforce.py` reference). Evidence: `research/sipp-routing/README.md`.

This note states the relaxation both solvers decide, the safe-interval state space, and the argument that Safe Interval Path Planning (SIPP; Phillips and Likhachev 2011, IEEE ICRA, pp. 5628-5635) returns exactly the earliest arrival of the frozen sweep `integration/kit/phaseB/zsweep.py::contact_sweep`, or proves that none exists. Every assumption is listed in the last section; outside them the argument does not apply.

**Safe interval (definition used throughout).** For a configuration (here: being at a road node after a given incoming edge), a safe interval is a maximal run of integer seconds during which the configuration can be occupied and, except at its last second, kept by waiting, without flame contact in any member of the planning set. "Safe" in this term means only "contact-free under the supplied members and the declared lattice"; it is not a statement about physical safety.

## 1 The relaxation Z (identical in both solvers)

Inputs: a directed road graph with integer travel times D_j = `travel_ticks * dt` (dt = 1 s), forbidden turn pairs, waitable flags per node, a request (issue node, issue second `dep`, integer horizon `hor`, destinations with dwell and opening intervals) and, per grid cell, the exact half-open activity intervals [b, e) of the planning members (first-new ignitions [b, b + T), present fire [0, R)), as exact rationals.

Lattice states are (s, t, a): s the directed edge just traversed (or the issue state), t an integer second, a an admission flag. Transitions:

- EDGE j from (s, t, .) when (s, j) is not a forbidden turn, the tail of j is the head of s, t is not a blocked departure second of j, and t + D_j <= hor; it reaches (j, t + D_j, admitted).
- WAIT from (s, t, .) when the head node is waitable, t is not a blocked wait second of that node and t + 1 <= hor; it reaches (s, t + 1, not admitted).
- Acceptance at (s, t, admitted) when the head node of s is a destination and t lies in its acceptance set; the issue state at `dep` counts as admitted.

Blocked sets (the sweep's occupancy semantics, `core.edge_occupancies` on the unit clock: open sub-segments between grid-line cuts with their midpoint cell, and every cut point with its floor cell; closed occupancy spans against half-open activity):

- departure t of edge j is blocked iff for some occupancy o = (cell c, fractions [z_a, z_b]) and some activity [b, e) of c: t + D z_a < e and t + D z_b >= b, i.e. t in [ceil(b - D z_b), ceil(e - D z_a) - 1];
- a wait from t to t + 1 at node n is blocked iff some activity [b, e) of n's cell has t < e and t + 1 >= b, i.e. t in [ceil(b - 1), ceil(e) - 1];
- acceptance at t needs an opening [o_1, o_2] with o_1 <= t and t + w <= o_2, t + w <= hor, and no activity of the destination cell with t < e and t + w >= b.

`frontend.build_instance` computes exactly these sets, with the same 1 m padded bounding-box prefilter, and the property tests compare it with the frozen sweep on random geometric instances.

The sweep processes seconds in increasing order; its first accepted second is the earliest arrival A* of Z, and if the reachable set empties (or the horizon passes) without acceptance, Z has no journey.

## 2 Safe intervals and the SIPP state

Wait components. At a waitable node n, define the component of second t as the maximal run [t_0, t_1] containing t such that every second in [t_0, t_1 - 1] is an unblocked wait second and t_1 <= hor. At a non-waitable node each second is its own component. The safe intervals of a node are its components; the free departure seconds of an edge are the complement of its blocked set.

SIPP label (a "piece"). A piece is (s, [lo, hi], h_arr): every second of [lo, hi] is reachable in state s, the seconds lo..h_arr by an edge arrival and the seconds after h_arr by waiting from h_arr inside one component. A piece never crosses a component boundary.

- At a waitable head, a piece is the classical SIPP state (configuration, safe interval) with the earliest arrival lo as its label, extended to the end of the safe interval.
- At a non-waitable head, a later arrival is not dominated by an earlier one (it cannot be reached by waiting), so the piece keeps the whole run of edge-arrival seconds. This is the one place where the construction departs from Phillips and Likhachev, whose dominance argument assumes that waiting is allowed in every configuration.

Successors of a piece: for every allowed edge j, the free departure seconds of j inside [lo, min(hi, hor - D_j)] form runs [x, y]; each run arrives in state j during [x + D_j, y + D_j]. At a waitable head the arrival run is split by components and each part is extended to its component end; at a non-waitable head it is kept as is. Per state, the seconds already covered by an earlier piece are subtracted from every new piece (dominance by set inclusion).

Goals. Acceptance needs an admission arrival at a particular second, so goal candidates are taken from the raw arrival run before the subtraction: the earliest accepted second of [x + D_j, y + D_j] is pushed as a goal with key equal to that second.

Order: best first on key = lo + h(head), h the static backward Dijkstra lower bound on remaining travel time to any destination with a non-empty acceptance set (it ignores fire and turn restrictions, so it is admissible, and D_j + h(v) >= h(u) makes it consistent).

## 3 The argument

Lemma 1 (pieces are exactly reachable sets). Every second of every piece is a reachable lattice state of Z, and every reachable lattice state (s, t) lies in some piece of state s. Proof sketch: by induction on t. A piece is created from a reachable departure second of a parent piece and a free departure of j (so the arrival seconds are reachable), and its extension stays inside one wait component (so each extra second is reached by unblocked waits). Conversely, a reachable (j, t) is reached either by an edge from some (s, t - D_j), which by induction lies in a piece of s whose expansion generates a run containing t, or by a wait from (j, t - 1), which lies in a piece of j whose extension (same component) contains t. Subtracting covered seconds only removes seconds that some earlier piece of the same state already contains.

Lemma 2 (successors depend only on (s, t)). The set of transitions out of a lattice state (s, t) does not depend on how (s, t) was reached; admission matters only for acceptance at that very second, and goal candidates are taken from edge-arrival runs. So keeping each (s, t) in one piece loses no journey. At waitable heads this is the SIPP dominance (Theorem 1 of Phillips and Likhachev: an earlier arrival in a safe interval can wait and reach every successor of a later one); at non-waitable heads it is set inclusion.

Lemma 3 (monotone keys). A child piece has lo_child >= lo_parent + D_j, so key_child = lo_child + h(v) >= lo_parent + D_j + h(v) >= lo_parent + h(u) = key_parent. A goal of second g generated from a parent has g >= lo_parent + D_j >= key_parent (h = 0 at an accepting destination).

Theorem 1 (earliest arrival). The first goal popped has second A*. Proof: every accepting admission arrival (j, g) of Z is generated as a goal candidate by Lemma 1 and the goal rule, with key g. With monotone keys (Lemma 3), all pieces and goals with key < g are popped before a goal of key g, so the first goal popped is the minimum over all generated goals, which is A*.

Theorem 2 (refusal). If the open list empties without a goal, Z has no admissible journey: by Lemma 1 every reachable state was in some piece and every admission arrival at a destination generated its goal candidates. The front end then distinguishes a forecast-independent structural disconnect (no destination state reachable in the turn graph at all, `DISCONNECTED`, as the sweep reports) from a model-scoped refusal (`PROVEN_INFEASIBLE`).

Witness. Each piece stores its parent piece and its last edge-arrival second; a goal is unwound edge by edge, inserting one-second WAIT legs where a departure second lies after the piece's last edge arrival. The witness is checked for structure by the frozen checker's `_shape` before it is returned, and its contact by the predicate tests.

## 4 Assumptions (all hold for the 20 frozen missions; the front end refuses otherwise)

1. Integer seconds: dt = 1, integer departure and horizon, integer travel times, as `zsweep` requires.
2. FIFO edges: travel times are constant, so leaving later never arrives earlier.
3. Waiting only at waitable nodes, in whole seconds; never on an edge.
4. Cost equals arrival time. If anything else is minimised (exposure, waiting penalties), earliest-label dominance is not valid and the generalised dominance of Gonzalez, Dornbush and Likhachev (ICRA 2012) or a label-setting resource search is required; otherwise optimality is silently lost.
5. Dose and peak are relaxed (zero mode). Cumulative exposure is a resource, not an interval property; it is handled outside SIPP by checking the witness and, if a contact-free candidate fails a dose or peak limit, by lazy constraint generation (blocking the offending edge departure windows and replanning). After any lazy cut the search is a heuristic: a returned route is still checked, but exhaustion is reported as unresolved, never as a refusal.
6. The issue position is a node and the incoming edge, if any, ends there.
7. The planning members' activity intervals are the exact rationals of the represented binary64 values (`ContactModel`, equal to `RoadBoundModel.cell_intervals` by test). Extinction-rounding gaps of the packets are a property of the relaxation, as in the sweep.
8. The heuristic is the static travel-time bound; any admissible and consistent bound keeps Theorem 1.

## 5 Relation to prior work

Safe intervals on road networks with moving obstacles appear in Wang and Zlatanova (2020, IEEE Transactions on Intelligent Transportation Systems 21(3):1044-1053, routes for first responders) and in Shahabi and Wilson (2017, Computers, Environment and Urban Systems 67:29-40). The operations-research precedent is time-dependent shortest paths on temporal graphs (Orda and Rom 1990; Dean 2004). We found no published use of safe intervals for wildfire or flood evacuation routing; this is stated as an observed gap in the literature we read, not as a claim of priority. Soft-constraint SIPP (SIPPS, Li et al. 2022, AAAI, MAPF-LNS2) counts violated constraints as a scalar lower bound and is exact only when a zero-violation path exists; it is cited and not used for any certificate. The overall design follows the certifying-algorithm pattern (McConnell, Mehlhorn, Naher and Schweitzer 2011): the planner is unassured, the checker is the assured monitor, and "unresolved" is the recovery output, as in the runtime-assurance pattern of ASTM F3269-21.

## 6 Evidence that the implementation meets the argument

- `experimental/sipp-routing/tests/test_sipp_property.py`: 10,000 random abstract instances (5 to 30 nodes, random turn restrictions, member activity intervals and destination windows): SIPP equals the brute-force time-expanded search, and every witness is a legal lattice journey; metamorphic tests (more unsafe intervals never decrease the arrival; a journey certified under the union of members is certified under each member and under every subset; shifting all times shifts the arrival; relabelling edges and nodes changes nothing).
- `experimental/sipp-routing/tests/test_geometric_vs_frozen_sweep.py`: 2,000 random geometric instances, SIPP front end against the frozen sweep (status and arrival second).
- `research/sipp-routing/`: the 20 frozen Korean missions, two repetitions, both solvers.
