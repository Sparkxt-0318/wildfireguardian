# kcf-queue: the congested leave-by window (frozen before any result)

Frozen 2026-11-18, Main at `beed15c` (PR #203). Hard stop: Sat 21 Nov 2026, 18:00 Shanghai (10:00 UTC).
Nothing in §1–§9 changes after the first result is computed. A mistake found later is corrected by a dated
**amendment** at the bottom with its reason, never by editing this text. If a test fails it is reported as failed; no
parameter, rule or test is changed to make it pass.

**Every number here is model output on reconstructed inputs and assumed parameters. It is not what happened to people.
It is not an order or advice to any official.**

**What had been looked at before freezing:** `deadline_field/core.py`, `research/kcf-theorem/THEOREM.md`, the
`wfg-roadlayer` engine, card code and settings, `data/traffic_sources.json`, the structure (columns, counts) of
`research/kcf-replay/per_place.csv`, `research/kcf-roadcut/PROTOCOL.md`, `LITERATURE.md` (this folder). **No closure
field, no leave-by, no queue and no village outcome of this work had been computed.** The size of the graphs was
printed (Yeongdeok 56,369 nodes / 111,924 edges; Uiseong-Andong 23,158 / 43,826).

**Environment fact, stated now.** `DATA_GO_KR_KEY` and `KMA_API_KEY` are **not set in this container** (checked:
no variable named like either exists). No KOSIS or data.go.kr call is made. Household counts are the ones already in
`product/wfg-roadlayer/data/` (cited county / 읍·면 totals split equally over villages, an ASSUMED rule). A better
per-리 source is therefore **not** used, and every demand number inherits that limit.

## 1 What is computed

For each village `v` (168 villages and 1 hamlet of the 174 places; the 5 care facilities have no vehicle demand in
the card model and are reported as "not evaluated") and each issue hour `T` in 12:00…24:00 KST on 25 March 2025 (13
hours, 03:00–15:00 UTC; the hours of `research/kcf-roadcut`), the **leave-by start** `s*(v,T)`: the largest start
`s` (seconds after `T`, a multiple of 10 s) such that every vehicle of `v`, released from `s` by the mobilisation
curve (§3.4), reaches one of the village's 3 candidate shelters accepted (§3.3), under the rules of §3. Fire arm:
**MEASURED, 8 h horizon** of `research/kcf-replay` (`measured_arms.py`, `fire_discs.json`). Other arms and the 5 h
horizon are not run (stated limit).

## 2 Inputs and sources

| input | source | status |
|---|---|---|
| road graph (nodes, edges, travel seconds, segments per 375 m cell, forbidden turns, waitable nodes), shelters, places | `wfg-roadlayer` cache from release `research-final-20261015` (SHA-256 pinned in `data/regions.json`); OSM snapshot 2025-03-21 | CITED data, model of it |
| fire discs, MEASURED curve per `(T, H)` | `research/kcf-replay/fire_discs.json`, `measured_arms.py` | reconstruction (not observation) |
| closure second of a road cell | `ceil(closure_s(r5, r8, distance to known fire area at T))`, kept if `<= H`; exactly as `replay.run_one` | model |
| households per place | `product/wfg-roadlayer/data/households/*.csv` (cites gb.go.kr 2024-11-30, yd.go.kr 2025-12; equal split) | CITED totals, ASSUMED split |
| vehicles per household | 1,552,434 / 1,295,685 = 1.198 (`traffic_sources.json`) | DERIVED, province level |
| road capacity by class | `cards.toml`: two-lane 1,700 veh/h/direction (KHCM 2013 via KHCMinR, CITED); motorway/trunk 4,400 (2 lanes ASSUMED × 2,200 CITED); other roads 800 (ASSUMED) | mixed |
| road class per edge | `product/wfg-roadlayer/data/edges/*_ways.csv.gz` (OSM 2026 classes on 2025 graph, a known mismatch) | model |
| free-flow reference | `research/kcf-replay/per_place.csv` (`MEASURED`, `8h`), committed | frozen output |

No real traffic count, no driver-behaviour record and no observed queue is used anywhere. Nothing here is calibrated.

## 3 The model (KQ-1)

All times are integer seconds after `T`; `H = 28,800`; shelter dwell `120 s`.

**3.1 Network and closures (unchanged from the deadline field).** `build_instance` and `accept` of
`wfg_roadlayer/engine.py` (themselves `replay.py`'s): edge `j` may be **entered** at second `t` iff `t < lo_j`
(`B_j = [lo_j, H]`, permanent); entering takes `D_j` seconds. A turn `(i, j)` in the forbidden set is not allowed.

**3.2 Queues.** A vehicle may stand at a node `u` (a point queue; no length) during `[t, t+1]` iff `t < b_u - 1`, where
`b_u` is the closure second of `u`'s cell (no closure: always). A vehicle that has waited past this is lost. Waiting
is used only when capacity forces it (§3.5 shows why nothing else is needed). The origin is a node: a vehicle may not
leave it at `t >= b_o`.

**3.3 Acceptance.** Arrival at a candidate shelter node at second `a` is accepted iff `a in accept()` of
`engine.py`: `0 <= a <= H - 120`, and the shelter's cell not closed during `[a, a+120]`. Shelters have unlimited
space and no unloading queue (ASSUMED, a limit). Each vehicle may use any of the village's 3 candidate shelters
(`regiondata.Region.candidates(3)`).

**3.4 Demand and mobilisation.** `N_v = round(households_v * hh_mult * veh_per_hh)`. Vehicle `k = 0..N_v-1` is
released at `r_k = s + floor(W (2k+1) / (2 N_v))`, `W` the spread (a uniform ramp: ASSUMED, a stand-in for a
mobilisation curve; no behaviour data). A released vehicle is at the village's entry node.

**3.5 Capacity.** Directed edge `j` admits at most `n_j = max(1, floor(rho * cap_j / 60))` entries in every clock minute
`[60 m, 60 m + 59]` (bins aligned to `T`); `cap_j` from the class table of §2; `rho` the smoke factor. Rounding down
is conservative. Capacity is per edge only: no junction, merge or turning capacity, no shelter-gate capacity.
**FIFO.** Vehicles are interchangeable (same deadlines, differing only in release time). A schedule in which a vehicle
overtakes another can be relabelled into one where entries at every node follow arrival order, with the same
multiset of entry times on every edge (Hall's condition holds because each entry has an earlier arrival). The
checker therefore counts entries per bin and does not test order. This is an argument, not a machine-checked proof.
**No voluntary waiting.** Closures are permanent, so an earlier arrival at an edge state is never worse. Waiting that
is not forced by a full bin is not modelled. T2 tests that this equals the deadline field when capacity is unlimited.

**3.6 Solver (guaranteed-safe lower bound, CCRP-style).** (i) For each edge `j` and the village's candidate set
compute the free-flow **latest arrival** `ell_j` = the largest arrival second at `head(j)` via `j` from which some
route reaches an accepted shelter, by the backward recursion
`ell_j = max( a_max(head j) [if head j is a candidate shelter], max over allowed successors k of min(lo_k - 1, ell_k - D_k) )`
(a latest-label Dijkstra; Theorem 2(b) of `research/kcf-theorem/THEOREM.md` under its hypotheses, which hold for this
instance family: closures permanent, shelters accept from 0). (ii) Vehicles are routed one at a time in order of
`(release time, village id, k)`. Each vehicle takes the earliest-arrival timed path found by label-setting search over
edge states (A* with the free-flow travel-time lower bound, ties by smaller edge index), where at each edge it enters at
the earliest second `t >= arrival` such that the clock-minute bin of `t` has room, `t < lo_j`, `t - 1 < b_u - 1`
for the wait, and `t + D_j <= ell_j`; the entry is then reserved. A vehicle for which no path exists makes the start
`s` **infeasible** (the village does not clear at `s`). (iii) `s*` is the largest multiple of 10 s in `[0, L0]` for
which all vehicles are routed, by bisection, where `L0` is the free-flow latest departure of the first vehicle
(feasibility is assumed monotone in `s`; T4 measures this).
**What is proved and what is not.** Any `s` the solver accepts has an explicit schedule satisfying §3.1–§3.5 (the
certificate): `s*` is a **lower bound** on the true latest start under the same rules, with route choice free. It is
**not** proved equal to the optimum: the optimum is a flow-over-time problem and sequential reservation can be
sub-optimal. T1 measures the gap on small networks. An upper bound is `L0` (the free-flow single-vehicle leave-by).

**3.7 Scenarios.**
* **ISOLATED:** only `v` leaves. Queues form from its own vehicles.
* **CONTESTED:** `v` at start `s`, and every **neighbour** `u` of `v` released from `T` (their own §3.4 curve, same
  parameters). Neighbours are routed first (right of way to traffic already on the road), in the §3.6(ii) order, then
  `v`. A **neighbour** of `v` is a village whose first-vehicle route at release `T` in the ISOLATED run (the solver
  with no reservations) shares at least one directed edge with the same route of `v`. One hop only: neighbours'
  neighbours are absent. This under-counts traffic and can make `s*` too late in CONTESTED; it is a **definition of the
  scenario**, not a statement that nobody else is on the road. Neighbours that cannot be routed reserve nothing for
  their unrouted vehicles.

## 4 Parameters: low, middle, high (every assumed one)

| parameter | low-stress | middle | high-stress | status |
|---|---|---|---|---|
| households multiplier on the equal split | 0.7 | 1.0 | 1.4 | ASSUMED |
| vehicles per household | 0.9 | 1.198 | 1.5 | middle DERIVED; ends ASSUMED |
| mobilisation spread `W` | 15 min | 30 min | 60 min | ASSUMED |
| smoke capacity factor `rho` | 1.00 | 0.85 | 0.70 | ASSUMED (no source) |
| capacity of "other" roads (veh/h) | 1,000 | 800 | 600 | ASSUMED |
| two-lane 1,700; motorway/trunk 4,400; dwell 120 s | fixed | | | CITED / ASSUMED lanes |

"Low-stress" means the end that makes the answer later. Runs: **LOW**, **MID**, **HIGH** = all parameters at that
column, both scenarios, all 13 hours. **One-at-a-time:** for two cases (Uiseong-Andong 12:00 KST and Yeongdeok 18:00 KST,
the hours of the existing cards), each parameter set to low and to high with the others at middle, CONTESTED.

## 5 Tests and pass/fail rules (all run on the committed code; results reported as they come)

* **T0 reproduction of the free-flow field.** My closure fields and my `ell`-recursion give a free-flow leave-by `L0`
  for every place-hour of `per_place.csv` (`MEASURED`, `8h`, 2,262 rows). PASS: the state (`INSIDE`, `NOT_CUT_WITHIN_H`,
  `NO_SAFE_DEPARTURE`, `LATEST_SAFE_DEPARTURE`) equals in all rows and `L0` rounded down to the minute equals
  `latest_safe_departure_kst` in all `LATEST_SAFE_DEPARTURE` rows. Every mismatch is listed. Failure here means the
  closure reconstruction is not the published one and every later number is labelled "not reproduced".
* **T1 brute force.** ≥ 5,000 random small networks (seeded; 4–7 nodes, ≤ 12 edges, `D` 1–4 s, 1–2 shelters, random
  permanent closures and node wait cutoffs, forbidden turns, 1–3 vehicles, capacity per bin 1–2 with a short bin),
  exhaustive search over every timed route and every joint reservation. For every start `s` in range: **soundness**
  (solver feasible ⇒ brute force feasible) must hold in **all** cases, PASS only if 0 violations; **exactness**
  (solver feasible ⇔ brute force feasible) is reported as a count. If any case differs, the solver is reported as a
  lower bound, not exact.
* **T2 unlimited capacity.** With `n_j = ∞` the solver must give the deadline field's answer: (a) ≥ 5,000 random
  instances (permanent closures, forbidden turns, waitable nodes), vehicle-by-vehicle against `core.backward` +
  `core.issue_set`: feasible set of release seconds equal; PASS only if equal in all; (b) the real graph: `L0` against
  T0. Any difference is reported.
* **T3 mutation tests.** The independent checker (written without reading the solver) must reject each altered
  certificate. Mutant families fixed now: entry before release; entry before arrival at the tail; entry at or after
  the edge closure `lo_j`; entry after the node wait cutoff; two vehicles in one full bin; edge not adjacent to the
  previous head; forbidden turn; last edge not into a candidate shelter; arrival after the acceptance bound; vehicle
  count ≠ `N_v`; release not on the §3.4 curve; closure second of a cell altered after the input hash was fixed;
  capacity class altered likewise; vehicle dropped from a neighbour; duplicated vehicle; negative entry time. PASS:
  100 % of ≥ 2,000 mutants rejected, each with a reason naming the rule. **Not detectable by design** (declared now):
  a certificate whose raw input data and the hash of that data were both replaced consistently.
* **T3b** the checker accepts 100 % of the unaltered certificates of the main runs.
* **T4 monotonicity.** For a random 5 % of village-hours in MID/ISOLATED the start is scanned every 60 s over
  `[0, L0]`; the number of places where feasibility is not a prefix is reported. If any exist, `s*` is labelled "found
  by bisection, not proved a prefix".
* **T5 sharing.** CONTESTED `s*` ≤ ISOLATED `s*` is expected but not forced (greedy). Violations are counted and
  reported.

## 6 Outputs

`RESULTS.md`, `numbers.json`, per-place-hour CSV, certificates and checker output, one figure at most. Reported (with
n): how many place-hours have `s*` earlier than the free-flow answer, by how much (median, maximum; quartiles); the
decomposition free-flow `L0` → free-flow with the spread → ISOLATED → CONTESTED; which OSM ways bind for the most
villages (binding = the edge, shelter acceptance or horizon with the least slack at `s*`); how many villages cannot
clear at all (infeasible at `s = 0` although `L0` exists; and villages with no free-flow window); how every result
changes across LOW/MID/HIGH and one-at-a-time. All lower-bound caveats stated next to the number.
Village cards in `product/wfg-roadlayer` get a queue-aware leave-by (MID, CONTESTED, with the LOW–HIGH range) beside
the old "800 veh/h, no queue" clearance line, which stays visible.

## 7 Limits stated now

No traffic counts, no driver behaviour, parameters assumed; household split equal within a 읍·면 or 시·군; vehicles
per household is a province figure; no junction capacity; no shelter capacity or gate queue; point queues of zero
length (a queue on a road that closes is treated as a point at a node); one fire arm; one day; 2 regions; neighbours
one hop; sequential reservation is a bound not the optimum; the closure field is a reconstruction.

## 8 Definitions of the comparison numbers

`L0` = free-flow leave-by of the existing field for the first vehicle (what the existing cards show). `S_free` = `L0 −
(r_{N-1} − s)` offset, the free-flow start with the same spread (all vehicles in the field's feasible prefix).
Shift = `L0 − s*` and `S_free − s*` both reported; the primary headline is the shift against `L0`, the "free-flow
answer" of the cards.

## 9 Amendments

**Amendment 1, 2026-11-19** (before any real-data outcome; T0, T1, T2 had been run). (a) `CERTIFICATE_SPEC.md` R1 gets an
optional neighbour field `ks`, because a neighbour whose some vehicles cannot be routed cannot otherwise be written
into a certificate (§3.7 says such vehicles reserve nothing). The checker was extended and its tests rerun; no model
rule changes. (b) The solver rejects at once any vehicle released after the free-flow latest departure `L0` of its
village. This is exact (no departure after `L0` has a route even without queues) and changes no answer; it only avoids
exhaustive failing searches. T1 and T2 are rerun on the final code and the rerun is the one reported. (c) Certificates
are written for every MID answer only for the two card cases (Uiseong-Andong 12:00 KST, Yeongdeok 18:00 KST); every
MID answer is *checked* by the checker during the run, LOW/HIGH ISOLATED answers are all checked and LOW/HIGH CONTESTED
answers are checked for the villages whose id has `crc32 % 5 == 0`. Certificate files for all answers are not committed
(size); their verdicts are. This is the reading of "each answer gets a certificate" that fits the repository.
