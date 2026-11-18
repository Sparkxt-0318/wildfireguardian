# Thermal dose enforced inside the deadline field

Status: **implemented and tested; run on the 1-hour panel and the 48 multi-hour HEADLINE packets**
(results: ROUTING_EFFECT.md). Code: `kcf_heat/dose.py`, `kcf_heat/tdu_field.py`, `kcf_heat/dose_check.py`;
tests: `tests/test_tdu_field.py`, `tests/test_dose_model.py`.

Before this, the thermal dose (TDU) was checked only after the fact, on the field's witness routes (C.3). Now the field
itself only returns departures for which some route keeps the dose within a budget.

## 1. What is limited

A journey's dose is the sum of its move doses (TDU = (kW/m²)^4/3·s):

* every edge traversal;
* every one-second wait;
* the destination dwell (shelter stay).

This covers departure to the end of the dwell, the same span the router's dose limit covers. The origin before
departure is not counted.

The dwell is a switch, `--dwell-dose count|exclude`, and every run is done both ways:

* **count** (default): the router's span, as if the stay is outdoors;
* **exclude**: the stay is indoors, and only the drive and the waits are limited.

Within a move, every second [τ, τ+1) adds φ(u(τ)), with φ(q) = q^4/3 if q > q₀ and 0 otherwise:

* **u(τ)** is an **upper bound** on the closed-form flux during that second. It uses the road piece the receiver
  occupies in that second, since traversal is at constant speed as in F-3.1. Terms:
  * a flaming cell gives χE_A R / (2π(dist + R t_r/2)), with dist the minimum distance from the piece to the cell
    rectangle;
  * a cell the piece crosses before its arrival b gives χE_A / (2π((b − s) + t_r/2)), where s is the latest moment
    of the second (front approaching inside the cell).
* **The maximum** is taken over cells and over hazard members. A journey must hold for every member, so summing the
  per-second maximum is an upper bound on each member's dose. It is exact for single-member packets, which include
  every F-DYN packet (`central`). The 1-hour packets have 4 members, so there it is conservative.
* **Constants:** packet values as in C.1. q₀ = 1.42 kW/m² (24 CFR 51.203). Vehicle shielding is not modelled.
* **Rounding:** each second's term is rounded **up** to a quantum of 10⁻⁴ TDU, so all sums are exact integers.

Because φ is increasing, the per-second bound makes the computed dose an upper bound on the model's integral. This is
stricter than C.3's post-hoc check, which took flux at the midpoint of each second and left out the dwell.

**Budgets** (HSL/2004/04 Table 1, bare skin, infrared; see ROUTING_EFFECT.md C.3):

* **92 TDU**: pain;
* **105 TDU**: threshold of first-degree burn;
* **290 TDU**: threshold of second-degree burn.

One field is computed at the largest budget and read at every budget.

## 2. Why the result is exact, not a heuristic

The dose is **one** additive, non-negative resource. Every other constraint is either part of the state (time) or a
mask, and the masks are F-3.1's router and closed-footprint contact plus the heat closure. So:

> a route from (state, t) with dose ≤ B exists **iff** the minimum dose over all routes from (state, t) is ≤ B.

No set of Pareto labels is needed. The minimum obeys a Bellman equation on F-3.1's time-expanded graph:

* m_s(t) = min over allowed successor edges j of [e_j(t) + g_j(t + D_j)], and, at a waitable head, w(t) + m_s(t+1);
* g_j(t) = min(m_j(t), dwell dose a(t) if t ∈ A_j).

Every move takes at least 1 s and every dose is ≥ 0. So a Dijkstra on dose, going **backward** from the acceptances,
settles each (state, second) once, with its minimum:

* **Seconds are kept in runs.** A run is an interval of seconds with equal value, as in F-3.1's interval sets. A run
  splits only where a move's dose changes, so far from the fire everything stays in long runs at dose 0.
* **The budget prunes.** Runs above it are never created.
* **With all doses 0**, the field settles exactly F-3.1's sets. This is tested.

A departure t from origin o is feasible at budget B iff its issue value ≤ B. The issue value applies the same equation
from the issue state (waiting keeps the issue state), then origin = destination acceptance at the departure second,
then the issue-point block.

## 3. Checks

**Random networks (`tests/test_tdu_field.py`).** 1,350 networks, built the same way as F-3.1's own field tests:

* features: non-waitable nodes, turn bans, cycles, blocked edges, waits and issue points, opening windows,
  dwell-blocked acceptance;
* random sparse doses on edges, waits and dwells.

At every origin and every second, the field's value equals an **exhaustive forward Dijkstra on dose** over the
time-expanded graph. That oracle is plain Python and shares no code with the field. In addition:

* every witness is replayed as a legal journey, and its dose, re-summed, equals the value;
* with doses set to 0, the feasible sets equal F-3.1's `issue_set` (800 networks);
* a larger budget never removes a departure.

**Real packet (`tests/test_dose_model.py`).** On Uiseong 03-24 09Z (4 members, 31 burning cells), the move doses lie
within independent bounds from `dose_check.py`:

* method: dense float sampling with explicit distance slack; no shared interval or difference-array code;
* coverage: 120 edges at several starts, and waits and 120 s dwells at 60 nodes.

**In every run, on every per-(origin, destination) deadline witness:**

1. the journey is legal under the cert_heat masks (independent replay);
2. its dose lies within the independent bounds and is ≤ the budget;
3. the next second is infeasible (or the planner range ends).

All pass in every run:

* 1-hour panel: 4,443 witnesses per dwell mode;
* multi-hour: 14,442 witnesses (dwell counted) and 14,466 (dwell excluded).

The `cert_heat` and `cert` fields computed alongside reproduce the committed 1-hour results and F-3.1's multi-hour
HEADLINE leave-bys (4,176 / 4,176).

**Cost.** Seconds near the fire carry distinct values, so the field is slower than F-3.1's interval field where much
of the graph is near the fire, and comparable elsewhere:

* **1-hour, per cache, all specs:**
  * Uiseong 03-24 09Z: 117 s for TDU against 17 s for cert_heat;
  * Yeongdeok: 97–130 s against 139–191 s.
* **Multi-hour, per packet:** 3–2,179 s (median 42 s) against 7–164 s (median 52 s) for cert_heat.
* The independent dose check prefilters cells by each leg's bounding box. This is pure speed: it changes no
  per-second evaluation.

## 4. Limits

* The flux law and its constants are those of DERIVATION.md. The law is unattenuated, so it is conservative against
  FDS (FDS_CHECK.md). The dose inherits that.
* The model reads the whole flaming 375 m cell as the front (nearest-front). The front's position inside the cell is
  not known.
* Not covered: shielding (vehicle or building), convection, smoke, embers, terrain.
* Unshielded TDU thresholds are applied to people in vehicles and at shelters. For occupants of a closed vehicle, or a
  dwell spent indoors, the doses are upper-side. The `exclude` mode bounds the second case from below: it drops the
  dwell entirely.
* Multi-member packets: maximum over members (conservative; section 1).
