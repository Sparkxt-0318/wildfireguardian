# E4: a flow-over-time upper bound on residents delivered (SYNTHETIC dev)

**Type:** bound (no plan). **Track:** C, Phase 1 batch 1. **Data:** frozen SYNTHETIC dev split only
(rule 5: no test instance is generated, read or run). **Label:** every number and figure here is SYNTHETIC.
**Code:** `evacplan/src/evacplan/methods/flow_bound.py` (method `e4_flow_bound`, bound only),
`methods/lp_worker.py` (HiGHS in a child process), harness and leaderboard support for bound-only methods
(`harness.py`, `docs/ASSUMPTIONS.md` #94-#95), tests in `evacplan/tests/test_flow_bound.py`.

## Pre-registration (written before any dev bound was computed)

What had been run before this section was written: the LP on one dev S instance
(`SYNTHETIC-S-grid-t25-s101`, to check that the code runs; bound 23 = all residents, as B3 already proves),
solver timings on that LP, and model sizes (no solve) on one dev M instance. No other dev bound.

Amendment (before any further dev bound): on B3's tiny brute-force instance (SYNTHETIC, not dev) the plain LP
gave 6 against an optimum of 5. Fractions of the one van shared the work: one piece stayed at the facility and
boarded while another drove the residents away, and pieces relayed residents through another facility. Two
valid strengthenings were added (free space and trip cuts, below); with them the tiny bound is 5. Both are
switchable (`free_space`, `trip_cuts`) and the README reports their effect.

### Hypothesis

A dynamic-flow (flow-over-time) LP relaxation on the contact-free time-expanded network gives a **valid**
upper bound on the residents any plan can deliver on the M and L dev instances (where B3 cannot run),
within about 15 % of the best plan on M.

Background: the leaderboard has proven bounds only on S (B3's certified bound, 114 of 115 residents, all of
them the resource bound). On M and L the only bound so far is the trivial "every servable resident"
(635 on M, 1225 on L), against best plans of 597 on M (per instance, the best baseline) and 1045 on L (B2).

### Why it might work (the math)

Ford and Fulkerson: a maximum flow over time in a network with transit times is a static flow in the
time-expanded network (one copy of each node per time step, arcs that advance by the transit time, holdover
arcs). Hoppe and Tardos: the quickest transshipment, with many sources and sinks, is also a flow problem on
such a network. Evacuation is a dynamic transshipment with side constraints: residents are supplies at the
facilities (from the release time, until the fire closes the facility), shelters are sinks (windows,
capacity), and the "transport capacity" is vehicles, each with a fixed space per mobility class, which
spend real time boarding and unloading. On the time-expanded network all of this is linear in the number
of vehicles on each arc; dropping integrality (fractional vehicles) leaves an LP. If every plan the oracle
checks maps to a feasible point of that LP with the same number of delivered residents, the LP optimum is a
bound. The bound is informative when the scarce resource is vehicle time near the facilities' deadlines,
per-class space per trip (2 wheelchair slots per bus or van, 1 stretcher per ambulance) and round-trip
times: exactly what the trivial bound ignores.

### The relaxation

Time steps of `delta` seconds: cell `k` = [k·delta, (k+1)·delta) on the instance clock, `k = 0 ..
floor(Hi/delta)` (`Hi`: the last whole second of the hazard horizon). Locations: the distinct graph nodes of
facilities and shelters. Commodities: vehicle groups `g` (one per vehicle, or identical vehicles pooled).

* **Network.** Nodes `(i, k)`. *Moves* `(i, k) -> (j, k')` with `k' = floor(EA / delta)`, `EA` = the
  NEGATIVE-relaxation earliest arrival at `j` leaving `i` at `k·delta` (`Reach.earliest_arrival_neg`:
  only certain flame contact up to the horizon blocks a departure, waiting is allowed anywhere, no turn
  rules, unknown cells passable, every leg by the horizon). *Waits* `(i, k) -> (i, k+1)` everywhere. A
  vehicle *enters* at its depot at its start time (a depot that is not a location sends one move to each
  facility location, arriving at the NEGATIVE earliest arrival from the start), and *ends* at a shelter
  location (or never enters: unused).
* **Variables** (all continuous, >= 0): vehicle flow `x[g, a]` on every arc; load `y[g, c, a]` of class
  `c` on moves and waits; residents boarded `b[g, f, c, k]` and unloaded `u[g, s, c, k]` in cell `k`.
* **Rows.** Flow conservation per group and node; at most one entry per vehicle; per group, class and node:
  load in + boarded = load out + unloaded (entries and ends carry no load); per group, class and arc:
  `y <= space[g, c] · x`; residents boarded per facility and class <= residents; unloaded per shelter and
  class <= capacity; pooled groups: by the cell where a vehicle's shift ends, that many vehicles have
  ended.
* **Time actually spent.** Per group, site and cell: Σ_c seconds per resident · (boarded or unloaded) <=
  Σ over the arcs entering `(i, k)` of `x · usable seconds`, where a wait arc offers the usable part of the
  whole cell and a move (or entry) arriving at `EA` the usable part of `[EA, (k+1)·delta)`. *Usable* =
  inside the site's action set and the group's shifts `[start, min(Hi, start + shift))`. Action sets:
  facility `f`, class `c`: `[release_f, min(ignition_f, LD_neg(f, c) + 1))`, where `ignition_f` is the first
  instant a stationary occupancy of the node touches a burning cell in some member, and `LD_neg(f, c)` the
  latest NEGATIVE departure from the node that still reaches a shelter accepting `c` and unloads one
  resident inside a window by the horizon (`Reach.latest_arrival_neg`); empty if the node is unsupported.
  Shelter `s`, class `c` with capacity: its windows ∩ `[0, min(Hi, ignition_s))`.
* **Free space** (stops relays through facilities). Per group, class and arc into a facility-only node: free
  space `z >= 0` with `y + z <= space · x` (instead of `y <= space · x`); a vehicle enters with `z <= space`;
  at a facility-only node, the free space leaving towards facility-only nodes plus the residents boarded is
  at most the free space arriving. Free space is created only by unloading (at shelters, where it is not
  tracked) or at a vehicle's entry, so a fraction that leaves its load at a facility does not get room back.
* **Trip cuts** (stop parallel work by fractions of one vehicle at a facility that closes). Per vehicle
  (summed over a pooled group) and facility: residents of class `c` boarded there <= floor(max over m >= 1 of
  min(m · space_c, (W_c − (m − 1)·G) / b_c)), and boarding seconds there <= max over m of min(m · Σ_c b_c
  space_c, W − (m − 1)·G); `W` = min(end of the facility's action set, end of the vehicle's shift) −
  max(release, the NEGATIVE earliest arrival from the vehicle's start), `G` = the shortest free-flow round trip
  to a shelter that takes a class the vehicle carries plus the shortest such unloading.
* **Objective:** maximize Σ unloaded. **Bound** = floor(weak-duality value of the LP's row duals + a
  floating-point margin), then min with the resource bound (`timexp.trivial_bound`).

### Why every checked plan maps into it (the validity argument)

Take any plan and its oracle result. A resident is delivered iff the trip that unloads them is `checked`:
every occupancy of the vehicle from its start through that unloading is contact-free and supported in all K
members, ends by the horizon, and no validator rule is broken up to there (resources, release, windows,
shift, capacities, first come first served).

1. *Keep only what counts.* For each vehicle keep its itinerary up to its last delivering unloading, and of
   each boarding only the residents that are delivered. Everything kept is checked; dropping residents only
   lowers loads and seconds of work. Residents delivered from facility `f`, class `c`, were boarded at
   boardings the validator accepted, so they number at most the residents of `(f, c)`; those unloaded at a
   shelter at most its capacity (first come first served flags every excess).
2. *Stops and stays.* A stop is a maximal run of kept actions at one node with no drive in between. The
   vehicle stays at the node from the end of the drive before the run (`alpha`) to the start of the drive
   after it (`beta`). The stay maps to the nodes `(i, k)` of every cell it meets: `floor(alpha/delta) ..
   floor(beta/delta)`, linked by waits (a loop that leaves and comes back without a kept action elsewhere
   is mapped to waits: the network only gains presence).
3. *Moves.* The drive from `beta` (cell `k`) to the next stop's `alpha'` is a checked trip: each edge
   contact-free in every member, so not certainly blocked. With persistent burning and whole-second data
   (the 1 s lattice is complete, `ASSUMPTIONS.md` #72), flooring every time of a contact-free trip keeps it
   contact-free, so it is a NEGATIVE trip from `floor(beta)` arriving by `floor(alpha')`. NEGATIVE earliest
   arrival is non-decreasing in the departure time (waiting is free in it), hence `EA(k·delta) <=
   alpha'`, and the move arc from `(i, k)` lands in a cell `k' <= floor(alpha'/delta)`; waits carry the
   vehicle on to the cell of `alpha'` (the network's vehicle "waits" while the real one still drives, which
   only adds presence). The arc exists: `EA <= alpha' <= Hi`, and `alpha'` is before the end of the next
   site's action set. Because `delta` is at most the shortest free-flow time between two locations, every
   move advances at least one cell (no zero-time cycles in the network).
4. *Seconds.* An action's seconds are booked in the cells in which they happen, residents proportionally
   (a boarding of n residents over [t0, t1] books n·|[t0, t1] ∩ cell| / (t1 − t0) in each cell). In a cell
   the vehicle is at the node at most from its entry (cell start if it came by a wait, its arrival
   `alpha' >= EA` if it came by a move) to the cell end or its departure, and only acts inside the action
   set: boarding starts at or after release, the boarding stay is contact-free (ends before the node
   ignites), and the vehicle then leaves on a NEGATIVE trip that reaches a shelter for the resident's class,
   so the boarding ends before `floor(beta) + 1 <= LD_neg(f, c) + 1`; unloading lies in a window, ends by
   the horizon and before the shelter node ignites; every action ends within the vehicle's shift. So the
   seconds booked are at most the arc's usable seconds.
5. *Loads.* On a move arc the load is the real load at departure (every action of the stop is done by
   `beta`): at most the vehicle's space. On a wait arc inside a stay it lies between the loads before and
   after the action in progress, both within space. Conservation holds by construction; entries and ends
   carry no load (every kept resident is unloaded within the kept prefix).
6. *Vehicles.* Each vehicle is one unit of flow from its entry to the end node of its last delivering
   unloading (a shelter location), within its own cells; summing vehicles of a pooled group gives a feasible
   pooled flow (a vehicle that has ended has ended). The objective counts exactly the delivered residents.
7. *Free space.* Put `z = space − load` on every arc of the vehicle into a facility-only node: then
   `y + z = space`, `z = space` on entry, and at a facility-only node the load only grows by boarding, so the
   free space leaving equals the free space arriving minus the residents boarded (towards a shelter it is
   simply not carried). Summing vehicles keeps every row.
8. *Trip cuts.* Split the vehicle's kept boardings at the facility into trips, maximal runs with no kept
   unloading in between. Within a trip the kept load never decreases, so a trip boards at most the space of
   each class. Between two trips the vehicle unloads at least one resident at a shelter: it drives from the
   facility's node to the shelter's and back (at least the free-flow times) and unloads (at least the shortest
   unloading time): at least `G` seconds between the end of one trip's last boarding and the start of the
   next trip's first. All boardings take their seconds and lie between max(release, arrival) and the end of
   the action set (step 4) or of the shift, with arrival >= the NEGATIVE earliest arrival from its start
   (step 3). So for the number of trips m: `n_c <= m · space_c` and `Σ_c b_c n_c + (m − 1)·G <= W` (per
   class, with that class's action set); the counts are whole residents, hence the floor. A shelter on the facility's own node gives
   `G` = one unloading, and if no shelter can empty the vehicle there is one trip.

**What is relaxed, and why each only enlarges the feasible set:** vehicle identity within a pooled group and
integrality (any integral flow is a fractional flow; the free-space rows and trip cuts take back part of what
fractional vehicles gain); the order of actions inside a cell (only seconds per
cell are bounded); turn rules, waiting rules and unknown cells on the road (the NEGATIVE relaxation keeps every
contact-free trip); dose and peak flux (not modelled at all); each departure is rounded down to its cell start
(earliest arrival is monotone); arrivals are taken at `EA` (no later than real); action sets are supersets of
the times an oracle-checked action can happen (release, ignition, one second after the latest NEGATIVE
departure, windows, horizon, shift: each bound taken in the relaxation's favour). Arcs are dropped only where
no NEGATIVE trip exists, i.e. where contact is certain in some member (a checked trip never uses them).

**Model reduction that keeps the optimum.** A move is left out when two shorter moves through another
location reach the same destination in an earlier cell, or in the same cell no later: any flow on it can take
that path instead and gains only presence. The two moves are strictly shorter, so by induction the
replacement uses kept moves.

**Certificate.** HiGHS (interior point, threads = 1, in a child process because OR-Tools ships an incompatible
`libhighs`) solves the LP. The bound is not the solver's objective but weak duality evaluated on its row duals
`pi`: for ANY `pi`, `c·x <= Σ_i max(pi_i L_i, pi_i U_i) + Σ_j max(d_j l_j, d_j u_j)` with `d = c − Aᵀpi`, so
the bound holds whatever the solver's tolerances or status (signs of one-sided rows are clipped, both `pi`
and `−pi` are tried, every column has a finite upper bound). The interior point (no presolve: without crossover
HiGHS's postsolve does not restore consistent duals) gets 70 % of the time left; if it leaves no usable duals,
PDLP gets the rest, and the smaller certified value is kept. It is rounded down after a margin that covers
the floating-point error of that sum. If the lattice is not complete, no bound beyond the resource bound is
claimed.

### Setup

* Instances: the 10 frozen dev instances (4 S, 4 M, 2 L), SYNTHETIC; regenerated, fingerprints verified.
* `delta` = 60 s on S and M, 120 s on L (reduced automatically to the shortest free-flow time between two
  locations when that is shorter); commodities: one per vehicle on S and M, vehicles pooled by type on L
  (the LP with one commodity per vehicle is about 3x larger there). The configuration is fixed before the
  dev run (`config.yaml`); if L does not solve in the budget, `delta` on L may only grow (a coarser grid is
  still a valid, looser relaxation), and that is reported.
* One seed (the bound is deterministic; the seed is ignored). Run through the harness, `evacplan run
  --method e4_flow_bound --set dev --seeds 0`, under the bench lock, at the budget it needs (900 s); a proven
  bound does not depend on the budget, so its rows join every table of the same set and host.

### Baseline and metric

* Baseline bounds: the trivial bound (all residents of servable classes: the resource bound, minus the
  oracle's `unservable`) and B3's certified bound on S.
* **Metric:** gap per instance = (bound − best delivered by any method on this host) / bound, and its mean
  over S, M and L. Also reported: the trivial bound's gap and the share of it the E4 bound closes.

### Validity checks (the core of the experiment)

1. Siyeong's check: on every S instance the bound is >= B3's delivered value in every B3 row.
2. The bound is >= every checked plan's delivered count in every result row of every method on dev, same
   instance, any seed or host (`check_validity.py`, a script over `evacplan/results/*.csv`).
3. Tiny SYNTHETIC instances with a known optimum (brute force over every trip sequence of one vehicle, as in
   B3's tests): bound >= optimum (`tests/test_flow_bound.py`).
4. Properties: fewer vehicles, a shorter horizon, shorter shifts and more burning never raise the bound
   (`tests/test_flow_bound.py`), and on random small instances the bound is >= every plan the oracle checks
   (random plans, B0, B1, B3).

### Budget and decision rule

Time-box: about 4 h of work, at most 1 h of bench time.

* **KEEP** if the bound is valid on every check and informative: gap <= 30 % on M **and** strictly below
  the trivial bound on at least one instance where the best plan falls short of it.
* **KEEP as a sanity bound only** if it is valid but looser (no better than the trivial bound).
* **KILL** if it is invalid and cannot be fixed within the time-box.

Note: the trivial bound alone already has a mean gap of about 6 % on M against the best baselines
(597 of 635), so "gap <= 30 % on M" by itself does not show that the bound is informative; hence the second
condition (question for Siyeong below).

## Results

**Run.** `evacplan run --method e4_flow_bound --set dev --seeds 0 --budget-s 900` under the bench lock,
2026-11-01 07:15-08:06 UTC, commit `a4c88873`, host `vm (Linux x86_64, Intel(R) Xeon(R) Processor @ 2.80GHz,
4 cpu, python 3.12.3, vm boot ff671362)`. Rows: `evacplan/results/e4_flow_bound.csv` (flagged `bound_only`);
table: `results.csv` and `figures/bounds_vs_best_dev.png`, both from `check_validity.py`. **Best delivered** =
the most residents any method delivered on the instance on this host: B2's five repeats at 60 s (merged from
`evacplan/phase0` `c888a87b`); B0, B1 and B3 still had rows of the previous host string only (their 5-seed
re-runs were queued behind the bench lock). Trivial bound = min(resource bound, residents − unservable).

| instance (SYNTHETIC) | residents | trivial bound | **E4 bound** (LP value) | best delivered, this host | **gap** | trivial gap | trivial gap closed | runtime (s) | LP rows × cols |
|---|---|---|---|---|---|---|---|---|---|
| S-grid-t25-s101 | 23 | 23 | **23** (23.00) | 23 | 0 % | 0 % | – | 3.9 | 12k × 16k |
| S-geo-t25-s102 | 39 | 39 | **39** (39.00) | 36 (37 by B1, previous host) | 7.7 % | 7.7 % | 0 % | 6.4 | 13k × 18k |
| S-grid-t75-s103 | 27 | 26 | **25** (25.94) | 23 | 8.0 % | 11.5 % | 33 % | 1.3 | 4k × 5k |
| S-geo-t75-s104 | 26 | 26 | **26** (26.00) | 26 | 0 % | 0 % | – | 1.2 | 4k × 5k |
| M-grid-t25-s105 | 163 | 163 | **163** (163.00) | 163 | 0 % | 0 % | – | 221.5 | 125k × 195k |
| M-geo-t25-s106 | 155 | 155 | **155** (155.00) | 155 | 0 % | 0 % | – | 595.9 | 143k × 229k |
| M-grid-t75-s107 | 168 | 168 | **160** (160.11) | 140 | 12.5 % | 16.7 % | 29 % | 164.8 | 69k × 109k |
| M-geo-t75-s108 | 149 | 149 | **144** (144.03) | 139 | 3.5 % | 6.7 % | 50 % | 200.1 | 75k × 118k |
| L-grid-t50-s109 | 646 | 646 | **646** (not solved: 865) | 516 | 20.1 % | 20.1 % | 0 % | 881.1 | 139k × 246k |
| L-geo-t50-s110 | 579 | 579 | **579** (not solved: 591) | 528 | 8.8 % | 8.8 % | 0 % | 880.5 | 128k × 220k |

**Mean gap** (E4 / trivial bound): S 3.9 % / 4.8 %, **M 4.0 % / 5.8 %**, L 14.5 % / 14.5 %, all 6.1 % / 7.2 %.

* **S:** E4 matches the resource bound on three instances and proves **25 on S-grid-t75-s103**, below B3's
  certified 26 and the trivial 26 (best plan 23).
* **M:** the t25 instances are proven at their resident counts, which plans already reach (gap 0). On the
  two t75 instances, where plans fall short, E4 proves **160 of 168** (best plan 140) and **144 of 149** (best
  139): it closes 29 % and 50 % of the trivial gap; the largest M gap is 12.5 %, inside the hypothesis' 15 %.
* **L: not informative at this budget.** The pooled-type LP at a 119-120 s step (128k-139k rows, 220k-246k
  columns) did not converge in the interior point's 616 s share; its duals certify 865 and 591, PDLP's 270 s
  did not do better, so only the resource bound (646, 579) is claimed. For scale, M-geo-t25-s106 (229k columns)
  needed 591 s of interior point; the L LPs need a larger budget (a proven bound does not depend on it).
* **Solver notes.** On M-grid-t25-s105 the interior point stopped after 70 s at an infeasible point (status
  "Unknown"); the PDLP fallback certified 163. Every bound is weak duality on the reported duals, so neither
  status matters for validity.
* **Strengthenings.** On B3's tiny brute-force instance (optimum 5): plain LP 6, with free space 6, with free
  space and trip cuts 5 (tests). Their effect on dev was not measured: the ablation run was dropped to stay
  within the 1 h bench budget (`ablation.py` is the script, not run).

### Validity checks

| check | status |
|---|---|
| 1. S: bound >= B3's delivered value in every B3 row | **pass**: 12 B3 rows (23, 34-35, 21, 25 vs bounds 23, 39, 25, 26) |
| 2. bound >= every checked plan, every method, seed, budget and host on dev | **pass**: 0 violations over 152 rows of 5 methods (current rows, incl. B2 x 5 on this host) and over the 132 rows at `1373bb3f` (B0-B3 and noop, previous host) |
| 3. tiny instances: bound >= brute-force optimum | **pass**: B3's tiny instance (bound 5 = optimum 5) and 10 random off-grid variants at two steps each (`test_flow_bound.py`) |
| 4. adding a constraint never raises the bound; bound >= every checked plan on random small instances | **pass with one fix**: bound >= every checked plan (random plans, B0, B1, B3) on 12 random instances; the property test found one non-monotone case, a loose (not invalid) fallback when nothing is deliverable, fixed in `7ba44700` (below). The fixed property and harness tests have not yet been re-run under the bench lock (queued behind the baseline re-runs at hand-back) |

The full suite at `a4c88873` (in the same bench-lock hold as the dev run): 353 passed, 11 skipped, 2 failed.
(a) The monotonicity property found a case (`random_case(0)` with more burning) where the bound grew from 6 to
7: nothing could be delivered any more, the LP had no columns, HiGHS returned no duals and E4 fell back to the
resource bound, which is valid but loose. A network without unloading proves 0 (the mapping argument), and the
bound is now 0 there (`7ba44700`; no dev bound changes, every dev LP had columns). (b) The end-to-end harness
test checked the leaderboard text too broadly (the bounds table header names the method); fixed.

The final 5-seed baseline commit ("evacplan: baselines x 5 seeds") had not reached `evacplan/phase0` when
these checks ran; B0, B1 and B3 were checked against their rows at `1373bb3f` (previous host string) and B2
against its 5 repeats on this host (`c888a87b`). The orchestrator re-checks the new rows (and E1's).

### Decision: **KEEP**

Valid on every check, and informative where plans fall short: strictly below the trivial bound on
S-grid-t75-s103, M-grid-t75-s107 and M-geo-t75-s108; mean gap on M 4.0 % (<= 30 %), largest 12.5 %. It is the
first proven bound on M. Not yet on L: at a 900 s budget it claims only the resource bound there.

### Next step

1. L: rerun `e4_flow_bound` on the two L instances with a larger budget (about 30 min each, single thread; the
   bound is budget-independent and its rows join the 60 s table), or shrink the L model (coarser step with
   nearby locations merged, or decomposition by vehicle type).
2. Measure the strengthenings on dev (`ablation.py`) and tighten further where the gap is left (M-grid-t75-s107:
   12.5 %): the remaining slack is fractional vehicles doing work in parallel at facilities whose window is not
   binding, and departures rounded down to a cell start.
3. Use the LP's duals (value of a resident per facility and class, of vehicle time) to guide E1/E2.

### Questions for Siyeong

1. **Yardstick.** "Gap <= 30 % on M" is met by the trivial bound alone (5.8 % mean on M): should a bound be
   judged by the share of the trivial gap it closes (here 29 % and 50 % on the two M instances where plans fall
   short), as this README does?
2. **Bound-only rows across budgets.** E4's rows (computed at 900 s) feed the best-bound column of the 60 s table
   of the same host, because a proven bound does not depend on the budget that computed it. Agree, or keep
   bound-only methods inside their own budget's table?
3. **L budget.** The L LPs need roughly 15-30 min each, single-threaded. Run them once at a larger budget (not a
   timed comparison, the bound is deterministic), or allow HiGHS several threads for bound-only methods?
