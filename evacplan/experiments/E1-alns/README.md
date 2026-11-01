# E1: ALNS with the oracle in the loop (SYNTHETIC dev set)

**Type:** method experiment, Track C Phase 1 batch 1. **Method:** `e1_alns`
(`evacplan/src/evacplan/methods/e1_alns.py`). **Data:** the frozen SYNTHETIC `dev` split only (the test set is
never generated, loaded or run). **Label:** every number and figure here is SYNTHETIC. **Parameters:**
[`config.yaml`](config.yaml), fixed a priori and committed before any dev run; nothing is tuned to the SYNTHETIC
hazards (H0 found them "much hotter" than the Korean dev packets; Siyeong asked to be told before anything is
tuned to them).

## Pre-registration (written and committed before any dev run)

### Hypothesis

An adaptive large neighbourhood search (Ropke & Pisinger 2006) that searches a relaxed model (contact-free in all
K members by construction) and certifies only its incumbents with the oracle delivers more residents than B2 on
the dev set at 60 s: its worst of 5 repeats exceeds the bar for beating B2 (max of B2's best observed total and the
best-of-baselines total; 1750 / 1751 before the 5-seed reruns).

### Why it might work (the math)

* **The relaxed model is tight except for dose.** Plans are decoded on the POSITIVE masks of `evacplan.reach`:
  every drive, wait, boarding and unloading is contact-free in all K members, supported and ends by the horizon.
  Of the oracle's other rules, peak flux cannot bind (the flux law caps flux at q_rad / 2 = 0.70 kW/m² < 10 kW/m²,
  H0), so a decoded trip fails the oracle only on cumulative dose. The relaxed count is therefore an upper bound on
  the certified count of the same plan, equal to it unless a vehicle accumulates more than 100 kJ/m² (in H0 that
  happens only within about 375 m of burning cells). Searching the relaxed model loses little and costs microseconds
  per trip instead of the oracle's milliseconds per leg.
* **Lazy certification** (Dellin & Srinivasa 2016: evaluate expensive edges only on the current candidate optimum).
  The oracle runs only on the best relaxed candidate: at the end of each 100-iteration segment, when the time left
  would no longer suffice to certify it (the search then goes on with what remains) and at the end of the search;
  and only on itineraries it has not seen (cached by content). A vehicle's oracle state never improves along
  its itinerary, so a trip the oracle rejects is cut with the rest of that itinerary without changing any other
  verdict; the rejected prefix is remembered and cut from later plans, so the search sees the oracle's verdicts
  wherever it has them.
* **Large neighbourhoods fit this problem.** Boarding (40-450 s per resident) dominates trip times, so the plan's
  quality is decided by which vehicle serves which facility before its latest safe departure, and in what order. B1
  appends earliest-deadline-first and never revisits a choice; B2 optimises a static VRPTW whose free-flow times and
  static windows ignore the time-dependent hazard and then drops what the realization cannot do. E1 optimises the
  realized time-dependent plan directly: each iteration removes 10-40 % of the requests (random, worst-slack,
  related, whole trips or whole vehicle routes) and re-inserts the pool greedily or by regret-k. Regret insertion
  serves first the requests with the fewest good options, i.e. facilities near their deadline, which is exactly where
  greedy insertion loses residents. Insertions can top up a stop, add a stop to a trip (up to 3 facilities per
  trip) or open a trip anywhere in a vehicle's sequence; the latest safe departures prune options that cannot leave
  in time (an exact test: a departure after the latest safe departure has no contact-free route to an open shelter).
* **Never below the warm start.** The warm start is B1. A certified candidate replaces it only if its certified
  objective beats the warm start's optimistic bound (its relaxed resident count), so E1 delivers at least B1's
  residents on every instance and seed. The scalarisation `A*delivered + B*min(slack, Hi) - vehicle_time`
  (`B > vehicles x Hi`, `A > B x Hi`) keeps the lexicographic order exact.

### Setup

* Instances: the 10 frozen SYNTHETIC dev instances (4 S, 4 M, 2 L). Smoke and debugging runs: at most 2 dev S
  instances with short budgets; unit tests and profiling use hand-built instances and generator seeds 9701+ outside
  the split.
* Budget: 60 s wall clock per instance and seed, B1 warm start, oracle checks and a reserve (0.5 s + 3 % of the budget,
  as B2) included; single-threaded.
* Repeats: seeds 0-4 (`--repeats 5`), one bench-lock acquisition, quiet machine, one host (the container session
  whose boot id starts `ff671362`; the final run is refused if the session changed, because the baselines must then
  be re-run first).
* Parameters: [`config.yaml`](config.yaml) (Ropke & Pisinger 2006: segment 100, reaction 0.1, scores 33/9/13,
  removal 10-40 %, p = 6 for Shaw and 3 for worst removal, Shaw weights 9/3/2/5, noise 0.025, start temperature
  accepting a 5 % worse solution with probability 0.5, cooling 0.99975 over 25,000 iterations as an overall decay).

### Baseline and metric

* Baselines: B2 (OR-Tools VRPTW, the bar) and B1 (the warm start), 5-seed rows of the same host.
* Primary metric: total residents delivered (checked by the oracle in all K members) over the dev set per seed;
  median [min-max] and the worst of 5, against the leaderboard's bar and verdict (`compare_to_b2`).
* Also reported: unresolved (must be 0), model_no_route, not planned, delivered with slack >= 5 / 15 / 30 min,
  minimum slack, over-budget runs, per-instance medians vs B1 and B2, residents lost to dose (the oracle's dose
  causes in the final plans, and the residents the search cut after the oracle rejected their trips), iterations,
  oracle calls and the time split.

### Decision rule (fixed before the run)

* **KEEP** if the leaderboard verdict is "beats B2".
* **ITERATE** if the worst of 5 exceeds B2's median total on this host but not the bar, and a concrete untuned fix can
  be named.
* **KILL** otherwise.

### Budget

About 4 hours of work; at most 2 hours of bench time including the final evaluation (about 55 min: 10 instances x 5
seeds x 60 s plus the harness's oracle checks).

## Results

### Before the final run (tests, profiling outside the split, dev smoke)

* Tests (07:10-07:12 UTC, under the lock): 45 passed (`test_e1_alns.py` 9, `test_relaxed_and_rule3.py` incl. the AST rule-3 guard).
* Profiling on generated instances OUTSIDE the frozen split (seeds 9711, 9712; 60 s; same host):
  | instance | residents | B1 | E1 | E1 iterations | E1 time split |
  |---|---|---|---|---|---|
  | SYNTHETIC-L-grid-t50-s9711 | 566 | 452 (8.4 s) | 452 (46.5 s) | 0 | warm start 8.2 s, oracle calibration 2.3 s, certification of the warm start 36.0 s; oracle 22.5 ms per leg (1,701 legs) |
  | SYNTHETIC-M-geo-t75-s9712 | 143 | 98 (3.4 s) | 143 (57.7 s) | 3,222 | warm start 3.4 s, search 52.4 s, 5 certifications (21.7 s of oracle time, 18.3 ms per leg) |
  On L the full plan costs ~38 s to certify, and E1 reserves 1.5x the estimate (oracle_safety, fixed a priori) before
  it starts an iteration, so it never starts one: it returns the certified warm start. Kept as pre-registered (no
  parameter change); see the findings.
* Dev smoke (2 S instances, 10 s, seed 0, rows in the scratchpad): S-grid-t25-s101 23/23 (9,171 iterations, 9.2 s);
  S-geo-t25-s102 37/39 (25 iterations, 6.8 s). No code was changed after the smoke.

### Final evaluation (dev, 60 s, seeds 0-4)

Queued behind the bench lock.
