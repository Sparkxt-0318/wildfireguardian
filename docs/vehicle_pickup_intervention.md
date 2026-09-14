# One intervention on the credible walk-out failures: assisted pickup with an explicit fleet and timing

**Status: rule pre-registered 2026-09-13 before the run, after the diagnosis in
`docs/building_origins_observed_grading.md` was read; §4 is appended by the run.** Task 3
of the reviewer's note. Docs and `data/processed/` only; nothing registered, nothing on a
judge-facing surface; harness paused. This is a deterministic model of one intervention on
one committed hazard field, not a fleet plan.

## 1. Population and baseline

The **credible failures** of the diagnosis: no-safe-route nodes that are not snap-suspect,
budget-bound, threshold-bound or forecast-only. Baseline: walking completes none of them
(that is the class). A second, weaker baseline is the access-only reading the pipeline
already gives: 「a survival-aware vehicle route exists」 at W = 75, D = 30, with no fleet and
no timing. The intervention adds what that reading lacks: a counted fleet, sequential
trips, loading, egress and unloading, and a per-home deadline.

## 2. The model, declared

- **Fleet:** *k* ∈ {1, 2, 3, 4, 6, 8} vehicles, assigned round-robin to the four OSM depots,
  all free at the dispatch delay *D* ∈ {30, 15} min.
- **Deadline per home:** the earliest forecast time the home's drive node reaches the vehicle
  cutoff (0.7), `node_survival_time`; a pickup must arrive by deadline − 12 min (the config's
  safety margin). A home whose node never reaches the cutoff inside the forecast window has
  no binding deadline.
- **Trip:** survival-aware ingress route from the vehicle's current location (depot, or the
  refuge it last delivered to) departing at its free time, within W = 75 min per leg and never
  entering the vehicle cutoff; 10 min loading; survival-aware egress to the nearest
  rescue-reachable refuge departing after loading; 10 min unloading; the vehicle is then free
  at that refuge. One home per trip (no pooling).
- **Policy:** earliest-deadline-first: homes are taken in deadline order and each gets the
  vehicle with the earliest feasible arrival. No re-planning, no look-ahead. Deterministic.
- **Outcomes per home:** completed / missed (no vehicle reaches it safely before deadline −
  margin) / unsafe egress (reached, but no safe egress route within W).

## 3. What it does not model

Vehicle capacity in persons (one home per trip regardless of buildings behind the node),
road capacity, queues, real depot staffing, acknowledgment, who is actually in the
buildings, and any hazard other than the committed forecast field. 「Completed」 means the  <!-- forbidden-ok: wc022-forecast-field -->
model's trip closed before the model's deadline; it is not a rescue.

## 4. Results

_(appended by `scripts/run_vehicle_pickup_intervention.py`; nothing above this line is edited after the run)_

_Run 2026-09-13T06:09:42Z at `0619826`; artifact `data/processed/vehicle_pickup_intervention_yeongdeok.json`; 24 credible nodes / 74 buildings; deadlines (forecast vehicle cutoff at the home) min/median/max {'min': 0.0, 'median': 180.0, 'max': 180.0}; 57 s._

Baselines: walking completes 0 (the class is defined by it); access-only reading (a survival-aware route exists, W = 75, D = 30, no fleet, no timing): 9 of 24 nodes.

| dispatch delay | vehicles | completed nodes | completed buildings | missed (deadline) | unsafe egress | last delivery (min) |
|---|---:|---:|---:|---:|---:|---:|
| 30 | 1 | 9 | 40 | 15 | 0 | 372.2 |
| 30 | 2 | 9 | 40 | 15 | 0 | 203.0 |
| 30 | 3 | 9 | 40 | 15 | 0 | 167.3 |
| 30 | 4 | 9 | 40 | 15 | 0 | 146.1 |
| 30 | 6 | 9 | 40 | 15 | 0 | 119.6 |
| 30 | 8 | 9 | 40 | 15 | 0 | 89.7 |
| 15 | 1 | 9 | 40 | 15 | 0 | 357.2 |
| 15 | 2 | 9 | 40 | 15 | 0 | 188.0 |
| 15 | 3 | 9 | 40 | 15 | 0 | 152.3 |
| 15 | 4 | 9 | 40 | 15 | 0 | 131.1 |
| 15 | 6 | 9 | 40 | 15 | 0 | 104.6 |
| 15 | 8 | 9 | 40 | 15 | 0 | 74.7 |

## 5. Reading (written after the run)

- **The intervention resolves 9 of the 24 credible nodes (40 of 74 buildings), and neither
  fleet size (1 to 8 vehicles) nor an earlier dispatch (15 instead of 30 min) changes that
  count.** Every home a vehicle can reach safely is completed even by one vehicle, because
  none of those nine has a binding deadline (their drive node never reaches the vehicle
  cutoff inside the forecast window); fleet size only moves the last delivery from 372 to
  75 min. The 15 that are missed are missed for lack of any survival-aware vehicle route,
  not for lack of vehicles or time. In this model the binding constraint is **access**, not
  capacity.
- **Why the 15 are missed,** from the per-home record: 3 origins are already at the vehicle
  cutoff at t = 0 (deadline 0; two of them are also detected by FIRMS at t = 0); 2 walk
  nodes lie about 2 km from the nearest drive node, so no vehicle road exists near them (a
  map question); and **10 nodes in one cluster (walk nodes 119335830xx–119335831xx, 24
  buildings)** have no survival-aware drive route from any depot within 75 min although no
  deadline binds — their access corridor crosses the vehicle cutoff early. Their cells were
  all first detected at 333 min, so the observation agrees the fire came. That cluster is
  the concrete investigation target the reviewer asked for: the next intervention there is
  a verified alternative connection or an earlier movement, and both need field evidence
  the repository does not hold.
- **Caveats on the nine.** Five of them are 650–725 m from the drive node the vehicle
  「reaches」 (the walk node snaps to a road that far away), so 「completed」 there means the
  vehicle reached a road within a 10-minute walk, not the building. Buildings are not
  households; one home per trip; the deadline is the forecast's, not the fire's.
- **What this is:** a deterministic model of one intervention on one committed field,
  showing which of the credible failures a fleet can and cannot resolve and why. It is not
  a fleet plan and not a rescue count.
