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

Run once, as pre-registered: `evacplan run --method e1_alns --set dev --budget-s 60 --repeats 5`, one bench-lock hold
(08:15-09:07 UTC), commit `483eb527` (clean), host `vm (Linux x86_64, Intel(R) Xeon(R) Processor @ 2.80GHz, 4 cpu,
python 3.12.3, vm boot ff671362)`, the same container session as the B2 reruns. Rows: `evacplan/results/e1_alns.csv`;
per run: [`results.csv`](results.csv) (from [`e1_analysis.py`](e1_analysis.py)).

**Verdict (leaderboard): no (worst 1443 ≤ bar 1750).** Bar on this host = max(B2 best observed 1750 [recorded
Phase 0 observation], best-of-baselines total 1749 [B2 rows; the noop/B0/B1/B3 reruns of this session were still
queued]) = 1750.

| SYNTHETIC dev, 60 s, this host | per-seed totals (seeds 0-4) | median [min–max] | worst |
|---|---|---|---|
| **E1 ALNS** | 1445, 1444, 1446, 1443, 1444 | **1444 [1443–1446]** | **1443** |
| B2 OR-Tools VRPTW | 1749 × 5 | 1749 | 1749 |
| B1 greedy (E1's warm start)¹ | 1353 | 1353 | 1353 |

¹ B1 has no rows on this host yet (its 5-seed rerun was queued). B1 is deterministic; the numbers are the sizes of its
plans built inside E1's runs on this host, which equal its Phase 0 rows (1353).

| E1, sum over the 10 instances per seed | median [min–max] |
|---|---|
| delivered (checked in all K members) | 1444 [1443–1446] |
| unresolved | 0 |
| model_no_route | 0 |
| not planned | 531 [529–532] |
| delivered with slack ≥ 5 / 15 / 30 min | 1351 [1283–1352] / 1267 [1265–1267] / 992 [980–1030] (B2: 1523 [1482–1523] / 1463 / 1284) |
| minimum slack | 1.9 s (L-grid-t50-s109, B1's plan; B2 16.7 s) |
| runs over budget | 0 of 50 (mean runtime 55.8 s; S and M stop at 57.7 s = budget − reserve) |
| residents lost to dose in the final plans: DOSE_ABOVE_BUDGET (model_no_route) / DOSE_UNRESOLVED (unresolved) | 0 / 0 |
| residents in trips the oracle rejected during the search (summed over certifications) | 0 |
| relaxed best − certified incumbent | 0 in 49 runs; 1 in M-grid-t75-s107 seed 3 (a 148-resident candidate whose certification did not fit in the time left) |

| instance | residents | B1 | B2 median [min–max] | E1 median [min–max] | E1 − B2 | E1 iterations (median) | E1 oracle itinerary checks (median) |
|---|---|---|---|---|---|---|---|
| SYNTHETIC-S-grid-t25-s101 | 23 | 23 | 23 | 23 | +0 | 70,646 | 3 |
| SYNTHETIC-S-geo-t25-s102 | 39 | 37 | 36 | 37 | +1 | 26,200 | 3 |
| SYNTHETIC-S-grid-t75-s103 | 27 | 20 | 23 | 23 | +0 | 47,066 | 2 |
| SYNTHETIC-S-geo-t75-s104 | 26 | 24 | 26 | 26 | +0 | 59,925 | 2 |
| SYNTHETIC-M-grid-t25-s105 | 163 | 163 | 163 | 163 | +0 | 2,280 | 15 |
| SYNTHETIC-M-geo-t25-s106 | 155 | 155 | 155 | 155 | +0 | 2,925 | 16 |
| SYNTHETIC-M-grid-t75-s107 | 168 | 100 | 140 | 148 [147–150] | +8 | 1,079 | 11 |
| SYNTHETIC-M-geo-t75-s108 | 149 | 101 | 139 | 139 | +0 | 733 | 20 |
| SYNTHETIC-L-grid-t50-s109 | 646 | 335 | 516 | 335 | −181 | 0 | 10 |
| SYNTHETIC-L-geo-t50-s110 | 579 | 395 | 528 | 395 | −133 | 0 | 10 |

By size: S 109 vs B2 108 (the best-of-baselines S total is 109); M 605 vs B2 597 (best-of-baselines 597); L 730 vs B2
1044.

![SYNTHETIC: E1 vs B2 per instance](figures/e1_by_instance.png)

![SYNTHETIC: per-seed totals and the bar](figures/e1_seed_totals.png)

**What happened.**

* **S and M: E1 matches or beats every baseline on every instance, every trip certified.** On S it reaches B2/B3's
  values or better (S-geo-t25-s102: 37 in every seed vs B2 36); on M it delivers every resident of the two instances
  where a baseline did (163, 155), equals B2 on M-geo-t75-s108 (139) and beats it by 8 on M-grid-t75-s107 (147-150;
  B2 140, B1 100). Thousands of iterations on S and M; the oracle never
  rejected a trip in any certification (no dose cut anywhere), so the relaxed model was exact on these instances.
* **L: no search at all.** On both L instances the B1 warm start took 8.0-10.7 s, the oracle calibration 2.6-3.8 s, and
  the oracle cost 21.6-25.5 ms per leg on plans of 1,658-1,772 legs, i.e. one full-plan certification ≈ 36-45 s. E1
  reserves 1.5× the estimate (`oracle_safety`, fixed a priori) before it starts an iteration, so it never started one:
  it certified the warm start (33-41 s) and returned it, delivering exactly B1's 335 and 395. This was visible
  before the final run on an L instance outside the split (0 iterations there too); the parameter was kept as
  pre-registered (see Next step). Lowering it to 1.0 would have left about 10 s for perhaps a handful of
  iterations on L, nowhere near the 314-resident gap to B2.
* **The oracle is the bottleneck, also on M.** The certifications took 15-37 s of oracle time per M run (of 57.7 s),
  and 18 certifications on M were skipped because they would not have fitted in the time left (the incumbent stayed).
  "Search cheaply, check expensively" works only when the expensive check fits the budget; at 60 s it does not on L.
* **Dose.** In no run did the oracle reject a trip E1 proposed (DOSE_* = 0 in the final plans and in the search).
  The H0 caveat (SYNTHETIC dose_lower much hotter than the Korean packets) therefore did not touch these results;
  nothing in E1 depends on a dose value.

## Decision: KILL

By the pre-registered rule: the verdict is not "beats B2" and the worst of 5 (1443) does not exceed B2's median total
on this host (1749), so ITERATE does not apply. The negative result is specific: the ALNS itself is at least as good as
the best baseline on S and M at equal time, but certifying incumbents inside a 60 s budget is unaffordable on L with
the current oracle (~22 ms per leg, ~40 s per L plan), so E1 falls back to B1 there.

## Next step

Report to Siyeong; no further E1 runs in this batch. A follow-up (E1b) would need his approval, because each candidate
fix touches the comparison rule, the oracle interface or a pre-registered parameter:

1. **Cheaper certification on L** (untuned, structural): an oracle entry point that checks an itinerary's suffix from a
   cached prefix state (cumulative dose per member and the state so far) would make lazy certification cost only the
   changed legs. That is an `evacplan.oracle` API addition: the oracle stays the only code that declares states.
2. **Budget accounting for certification.** B2's plan is certified by the harness outside its budget, while E1 pays for
   certifying in-budget. Either both count it or neither; Siyeong decides the rule.
3. **`oracle_safety` 1.5 → 1.0** with the existing per-check guard (computational, not hazard-related; about 10 s of
   search on L).

## What tuning would be tried if Siyeong allows it

None of this was done in this batch (no parameter was changed after seeing a dev result):

1. **Search effort per instance size.** At 60 s M gets 600-3,300 iterations and L none, so Ropke & Pisinger's
   100-iteration segments update the operator weights only a few times on M. Tuning would set the segment length,
   the destroy range (10-40 % of the requests) and the cooling end point per size class on dev.
2. **Operator portfolio.** Drop or reweight operators from the learned weights on dev (initial weights, scores).
3. **Dose-aware insertion.** The oracle's dose verdicts could seed a cost on long stays within ~375 m of burning
   cells (H0's band where the budget binds). That is tuning to the SYNTHETIC hazards ("much hotter" than the
   Korean packets by H0's rule) and needs Siyeong's decision first.
4. **Certification cadence and safety factor** (computational): certify more or less often, and a smaller safety
   factor on the oracle's time estimate on large instances.

## Changes after seeing dev results

* Method (`e1_alns.py`) and parameters (`config.yaml`): none. The last method commit before the dev smoke is
  `e642c1bb`; the smoke ran at `c318d524` and the final run at `483eb527` (the commits in between touch only the
  analysis script and this README, plus the merge of the orchestrator's same-host B2 rows).
* `e1_analysis.py`, after the final run: the figures draw only methods that have rows on this host (B1's rerun was still
  queued, which left an empty B1 column) and the bar's label moved left. No number changed.

## Budget used

* Bench time: about 57 min (tests, profiling and the dev smoke 07:10-07:16 UTC; final evaluation 08:15-09:07 UTC,
  one hold). Waiting for the shared lock: about 1 h 40 min before the first hold and 1 h before the final one.
* Work: about 4 h 15 min (05:00-09:15 UTC).

## After the merge (orchestrator note, 2026-11-01)

The full suite on `evacplan/phase0` after merging E1, E3 and E4 failed one test, `test_respects_the_budget`: 1.68 s at a
1.5 s budget. E1 cannot interrupt the B1 warm start, which alone takes 1.4-1.5 s on that S test instance (3.0-4.2 s of
the M instance's 4 s), so at a budget smaller than the warm start E1 overruns by the rest of it. The test now asserts that
guarantee (overrun at most the rest of the warm start) plus a strict check at a 6 s budget; E1's code is unchanged. At
60 s on dev the warm start takes at most about 11 s (L), and none of the 50 runs was over budget, so no result changes.
