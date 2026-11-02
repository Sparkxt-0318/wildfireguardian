# E1b: E1 with incremental certification (SYNTHETIC dev set)

**Type:** method experiment, Track C Phase 1 batch 2: the approved second (last) iteration of E1. **Method:**
`e1b_alns` (`evacplan/src/evacplan/methods/e1b_alns.py`, a subclass of E1's `e1_alns`). **Data:** the frozen SYNTHETIC
`dev` split only (the test set is never generated, loaded or run; no KR-2025 data). **Label:** every number here is
SYNTHETIC. **Parameters:** [`config.yaml`](config.yaml): E1's pre-registered values, unchanged and untuned.

**Approval** (`program/DECISIONS.md`, 2026-11-02, Siyeong's checkpoint-3 answers): "E1: run the approved second
iteration (E1b). Main change: incremental certification. Cache oracle results per vehicle itinerary and re-check only
vehicles whose itinerary changed. Profile the oracle first and report where the 33-41 s goes on L. Kill only if E1b's
worst of 5 seeds is still below 1751." And: "Final certification stays outside every method's budget. In-loop oracle
calls count."

**Outcome: KILL** (worst of 5: 1444, below 1751; B2 1749 in every seed of the same holds). See Results and Decision.

## Oracle profile (step 1: before any change; the oracle is not changed)

What was timed: `Oracle.check_plan` with a fresh Oracle (empty query cache) on B1's plan (seed 0; B1 is E1's warm start)
for the two SYNTHETIC L dev instances, under the bench lock (12:49-12:57 UTC, commit `22f6b594`, host `vm (Linux x86_64,
Intel(R) Xeon(R) Processor @ 2.80GHz, 4 cpu, python 3.12.3, vm boot 4169abd4)`). Nothing was tuned on these
instances; no E1b code existed yet. Raw output: [`profile/oracle_profile.json`](profile/oracle_profile.json), cProfile
listings: [`profile/`](profile/). Reproduce (from the worktree root, about 7 min):

```
.venv/bin/python /home/user/wildfireguardian/program/benchlock.py --wait-max 1800 --label E1b-profile -- \
    .venv/bin/python evacplan/experiments/E1b-incremental-cert/profile_oracle.py
```

| SYNTHETIC, B1's plan, seed 0 | L-grid-t50-s109 | L-geo-t50-s110 |
|---|---|---|
| vehicles / trips / residents delivered (oracle) | 10 / 53 / 335 (0 unresolved) | 10 / 61 / 395 (0 unresolved) |
| legs (drive / board / unload) | 1,772 (1,666 / 53 / 53) | 1,658 (1,536 / 61 / 61) |
| distinct hazard queries | 1,772 (one per leg; none repeats) | 1,658 |
| **cold `check_plan`** (simple timer; a second cold run) | **30.0 s = 16.9 ms/leg** (33.2 s = 18.7 ms/leg) | **31.3 s = 18.8 ms/leg** (29.7 s = 17.9 ms/leg) |
| re-check with the same Oracle (every hazard query a cache hit) | 3.1 s = 1.8 ms/leg | 3.2 s = 1.9 ms/leg |
| E1's in-loop path per vehicle (E1's `_check`): emit + RelaxedContactCheck + `check_itinerary` | 0.004 + 2.61 + 28.86 s = 31.5 s (17.8 ms/leg) | 0.006 + 2.67 + 30.64 s = 33.3 s (20.1 ms/leg) |

**Where the time goes** (cProfile of a further cold `check_plan`, cumulative time as a share of the check; the
profiler inflates the total to 40.3 / 41.5 s, so shares are approximate):

| part | L-grid | L-geo |
|---|---|---|
| hazard_contract queries (`Oracle._hazard`) | **88.8 %** | **89.3 %** |
| · `ScenarioSet.query_uniform` (drive legs; stays are point queries) | 88.0 % | 88.2 % |
| · · `ScenarioSet.query`, called for every uniform-motion piece twice (upper bounds on a widened interval, lower bounds on a narrowed one): 11,344 / 10,732 calls, 6.8 / 7.0 per drive leg | 78.0 % | 78.6 % |
| · · · `_member_result`: flux and dose bounds (the dose integration over the burning-set pieces), once per member, 8 per query | **48.1 %** | **48.4 %** |
| · · · `polyline_cells` (touched cells) | 9.6 % | 9.7 % |
| · · · `polyline_rect_dmin` (distances to the cells of the 5 km near box) | 5.2 % | 5.2 % |
| · · · `solid_angle_rects` (exact kernels at probe points) | 1.4 % | 1.5 % |
| · · · the rest of `query` (slicing K x near-box arrays, masks, kernel set-up) | 13.7 % | 13.8 % |
| · · `_point_burning` (exact contact under uniform motion, per cut point) | 8.1 % | 8.0 % |
| · · `uniform_pieces` (cut each edge at grid lines) | 1.6 % | 1.5 % |
| `Oracle.leg_slack` (exact slack of checked legs: `contact_records`) | 10.0 % | 9.9 % |
| validator (`validate_solution`), state classification, verdict bookkeeping | < 0.2 % | < 0.2 % |
| pydantic result objects (`LegResult`, `MemberHazard`, ...) | 0.7 % | 0.3 % |
| geometry `polyline_cells`, all callers (query 9.6-9.7 %, `_point_burning` 6.8-7.0 %, `leg_slack` via `_point_cells` and `contact_records` 8.0-8.1 %): 38,924 / 36,682 calls | 24.7 % | 24.6 % |

**Scaling with the K = 8 members** (cold `check_plan` of the same plan with the first K members):

| K | 1 | 2 | 4 | 8 | linear fit |
|---|---|---|---|---|---|
| L-grid, ms per leg | 9.0 | 10.6 | 13.6 | 18.7 | 7.9 + 1.38 K |
| L-geo, ms per leg | 10.8 | 10.9 | 14.2 | 17.9 | 9.4 + 1.08 K |

**Findings.**

* **Where E1's 33-41 s went on L.** It was E1's certification of B1's warm start inside the budget: every one of its
  ~1,660-1,770 legs was new to E1's per-itinerary cache and to the oracle's query cache. On E1's in-loop path the cost is
  about 92 % `Oracle.check_itinerary` and 8 % E1's RelaxedContactCheck guard; emitting the actions is negligible (5 ms
  per plan). Inside the oracle almost everything (89 %) is hazard_contract queries: about half of the check is the
  per-member flux and dose bounds (`_member_result`, 8 calls per query), a quarter is small-array geometry
  (`polyline_cells` alone 25 %, over half of it on single points), 10 % is the exact leg slack. The validator, the state logic
  and pydantic are below 1 %. In this VM session the same work takes 31.5-33.3 s (E1's runs measured 21.6-25.5 ms per
  leg in an earlier session).
* **K.** The cost per leg is about 8-9 ms fixed (geometry, near box, kernels, slack) plus 1.1-1.4 ms per member, linear
  in K; at K = 8 the per-member part is about half.
* **Cached legs are cheap.** A re-check whose hazard queries are all cached costs about 10 % of a cold check
  (1.8-1.9 ms per leg; the exact leg slack, which is not cached, is 10 % of a cold check). E1 and E1b keep one Oracle per run, so a changed itinerary pays
  ~18 ms for each leg the oracle has not queried before and ~2 ms for each one it has.

**Speed-up proposals (not implemented: the oracle and hazard_contract stay unchanged, rule 3; hazard_contract changes
go through the orchestrator and bump its version).** Each keeps every verdict and number unchanged if done exactly; each
would need a regression test that compares results bit for bit on the SYNTHETIC dev plans and the hazard_contract
property tests.
1. `query_uniform` queries every piece twice, and each `query` recomputes the piece's geometry (touched cells, near
   box, distances, kernels), which does not depend on the time interval: computing it once per piece saves up to half
   of the fixed part (about 15 % of a check).
2. `_member_result` runs once per member in Python: one batched numpy pass over the K members would cut most of the
   per-member Python overhead (48 % of a check at K = 8).
3. A single-point fast path in `polyline_cells` (at most 4 cells, no `np.unique`) for `_point_burning` and the oracle's
   `_point_cells`: about 12-14 % of a check.
4. A per-edge geometry cache (the pieces, cells and kernels of an edge are the same at every departure time) would make
   a leg on an already-queried edge at a new time cost only its time-dependent part; ALNS re-drives the same edges at
   new times all the time.
Rough combined effect of 1-3, from the shares above: 2-3x on a cold check; 4 adds to it on re-driven edges. Not measured.

## Pre-registration (written and committed before any E1b dev run)

### Hypothesis

E1 with incremental certification, i.e. in-loop oracle checks of only the itineraries its search changed (the B1 warm
start's itineraries that the search never changed are certified only by the harness after the timed solve, as B2's
whole plan is), delivers more residents than B2 on the SYNTHETIC dev set at 60 s: its worst of 5 seeds exceeds the bar
(at least 1751; higher if B2's rows in the same holds do better).

### Why it might work

* **E1's L budget went to certifying the warm start.** On L, E1 never searched: its 60 s went to the setup and B1
  (8-11 s), an oracle calibration check (2.5-3.8 s) and the in-budget certification of B1's plan (33-41 s), whose
  itineraries were all new to E1's cache (profile above). E1b moves that certification out of the budget: an unchanged
  warm-start itinerary is never sent to the oracle in the loop, so the search starts right after the warm start.
* **The search is good when it runs.** On S and M, E1 matched or beat every baseline (S 109 vs B2 108, M 605 vs 597),
  and the post hoc variant with no in-loop oracle at all (E1's `posthoc/`, not pre-registered, an earlier VM session)
  reached 525-553 per L instance (B2: 500-528) and per-seed totals of 1774-1799.
* **Dose stays with the oracle.** Every itinerary the search changed is still checked by the oracle in the loop, cached
  per itinerary, and cut before its first trip the oracle does not check (E1's mechanism, unchanged). The relaxed model
  is exact except for dose (E1, H0), and on dev the oracle never rejected a trip of any plan in E1's 50 runs.
* **Never below B1, by construction.** Candidates are valued with the oracle's numbers for changed itineraries and the
  relaxed numbers for unchanged warm-start ones, the same footing as the warm start; a relaxed count is never below the
  oracle's count of the same itinerary, so E1b delivers at least B1's residents on every instance and seed.

### Why it might not (predicted from the profile and recorded runs, before any E1b run)

* **On L one ALNS iteration changes nearly every vehicle.** B1 leaves 311 and 184 residents unplanned on the two L
  instances (all servable), and each repair inserts the whole pool wherever it fits, so the first improving candidate
  differs from the warm start on most of the 10 vehicles. Certifying it costs about as much as a whole plan: ~18-20 ms
  per leg on E1's path (profile); a candidate planning 450-550 residents has roughly 1,900-2,900 legs (B1's plans have
  4.2-5.3 legs per resident), i.e. 35-58 s of the ~47 s left after the warm start, before E1's 1.5x reserve. E1's search on L takes 1-4 s per iteration (11-52 iterations in 39-47 s in the post hoc run), so no
  100-iteration segment ends on L: certification happens when the time left only suffices for it, or at the end. If it
  does not fit, E1's per-check guard stops it, the search ends, and E1b returns B1's plan on L, as E1 did.
* So the likely outcomes on L range from B1's 335 / 395 (no certified candidate) to a candidate certified after one or a
  few iterations; beating the bar needs about 1,038 on L (with S + M near E1's 714), close to the post hoc variant's
  1,055-1,083, which had all 47 s for search. **Prediction: KILL is the more likely decision.** It is recorded here so
  that the outcome is judged against it; nothing in E1's parameters is changed to avoid it.

### Setup

* Instances: the 10 frozen SYNTHETIC dev instances (4 S, 4 M, 2 L). Tests: hand-built instances and generated ones with
  seeds 9701-9703, outside the split. Dev smoke: SYNTHETIC-S-grid-t25-s101 and SYNTHETIC-L-grid-t50-s109, seed 0, 60 s,
  rows into a scratch results directory (no dev row is written before the final run).
* Budget: 60 s wall clock per instance and seed, single-threaded. Inside it: setup, the B1 warm start, the search and
  every in-loop oracle check (DECISIONS 2026-11-02, item 2), and E1's reserve (0.5 s + 3 % of the budget). Outside it:
  the harness's final certification of the returned plan by a fresh oracle (`certify_s`).
* Repeats: seeds 0-4, B2 interleaved (ABAB) in the same lock hold with a speed check before every pair (harness of
  `aa0aeddd`, DECISIONS 2026-11-02 item 5). Two holds, each under the 2 h job limit: first the 8 S and M instances
  (about 90 min), then the 2 L instances (about 35 min). B2's seed offset is set to 0 in both holds
  (`--partner-seed-offset 0`; this host has no B2 rows yet in this branch), so B2 seed s pairs with E1b seed s and each
  of B2's five seeds covers all 10 instances (the harness's automatic offset would give B2 seeds 5-9 on L in the second
  hold, and B2 would get no per-seed totals):

  ```
  .venv/bin/python /home/user/wildfireguardian/program/benchlock.py --wait-max 1200 --label E1b-final-SM -- \
      .venv/bin/evacplan run --method e1b_alns --interleave-with b2_vrptw --partner-seed-offset 0 --set dev \
      --budget-s 60 --repeats 5 --instances SYNTHETIC-S-grid-t25-s101 SYNTHETIC-S-geo-t25-s102 \
      SYNTHETIC-S-grid-t75-s103 SYNTHETIC-S-geo-t75-s104 SYNTHETIC-M-grid-t25-s105 SYNTHETIC-M-geo-t25-s106 \
      SYNTHETIC-M-grid-t75-s107 SYNTHETIC-M-geo-t75-s108
  .venv/bin/python /home/user/wildfireguardian/program/benchlock.py --wait-max 1800 --label E1b-final-L -- \
      .venv/bin/evacplan run --method e1b_alns --interleave-with b2_vrptw --partner-seed-offset 0 --set dev \
      --budget-s 60 --repeats 5 --instances SYNTHETIC-L-grid-t50-s109 SYNTHETIC-L-geo-t50-s110
  ```
  (`--wait-max 1200` keeps the S and M hold, waiting included, under 2 h; a wait that times out exits 75 and is retried.)
* Host: this VM session (`vm boot 4169abd4`); B2's rows of the same holds are the comparison.

### The exact change (everything else is E1's code, inherited unchanged)

`e1b_alns` subclasses E1's run (`_Run`) and overrides two methods; E1's module, its tests and its rows are unchanged.

1. `_check(v, itinerary)`: if the itinerary is vehicle v's warm-start itinerary, unchanged (same trips; E1's decode is a
   function of the vehicle and its trips, so the same actions), it is not sent to the oracle. E1b uses its relaxed
   values (residents = its decoded residents, slack = its relaxed slack, no trip cut), cached under E1's key; its actions
   are emitted only if it is in the returned plan. Every other itinerary goes through E1's unchanged `_check`:
   RelaxedContactCheck, then `Oracle.check_itinerary`, cached per (vehicle, trips), with E1's per-check time guard and
   E1's measured seconds per leg.
2. `_estimate(plan)`: the certification estimate (and so the time E1 keeps free before it starts an iteration, and the
   point where repair stops) counts only changed itineraries not in the cache.

Consequences inside E1's unchanged flow: E1's calibration check (a warm-start itinerary) and E1's certifications of the
warm start become relaxed valuations with no oracle call, so before the first changed itinerary is checked the oracle's
cost is E1's prior (`oracle_s_per_leg0` = 0.01 s per leg). Untouched: parameters, operators, acceptance, cooling,
weights, objective, the lazy certification schedule, the incumbent rule, the 1.5x safety factor and the reserve.

### Baseline and metric

* Baseline: B2 (OR-Tools VRPTW), interleaved in the same holds. Bar: the leaderboard's (`compare_to_b2`): max(B2 best
  observed, best-of-baselines total), raised by the recorded observations 1750 and 1751: at least 1751.
* Primary metric: total residents delivered (checked by the oracle in all K members) over the 10 dev instances per
  seed; median [min-max] and the worst of 5.
* Secondary: time to certified plan = runtime + `certify_s` (DECISIONS 2026-11-02, item 2). Also reported: unresolved
  and model_no_route (from unchanged warm-start itineraries only, by construction), delivered with slack >= 5 / 15 /
  30 min (30 min is the provisional default), per-instance medians vs B2 in the same hold, iterations, in-loop oracle
  calls and time, changed vs unchanged vehicles in the returned plans, residents the in-loop oracle cut, the speed
  checks.

### Decision rule (fixed before the run)

* **KEEP** if the leaderboard verdict is "beats B2" (worst of 5 above the bar, which is at least 1751).
* **KILL** if the worst of 5 is below 1751.
* **ITERATE** otherwise (worst of 5 at least 1751 but not above the bar, or a row over the budget). E1's approved budget
  was two iterations, so ITERATE would need Siyeong's decision.

### Budget

About 5 h of work. Bench time: profile 7 min, tests about 10 min, smoke about 5 min, final holds about 90 + 35 min.

## Results

### Before the final run (tests, dev smoke; no dev row written)

* **Implementation** (`dae67e86`, after the pre-registration `58a392c9`, before any dev run): `e1b_alns` as
  pre-registered; E1's module and tests unchanged; the registry line added.
* **Tests** (under the bench lock, 13:03-13:15 UTC): `test_e1b_alns.py` 11 passed (oracle-valid plans; never fewer
  residents than the warm start; a candidate with one changed vehicle sends only that itinerary to the oracle, once, and
  the estimate counts it alone; over whole runs no warm-start itinerary reaches the oracle, no itinerary is sent twice,
  and every returned itinerary is either an unchanged warm-start one or one the oracle checked in the loop; a slow oracle
  is booked inside the runtime and the budget holds; the budget; determinism with an iteration cap; dose; E1's
  parameters). `test_e1_alns.py`, `test_relaxed_and_rule3.py` (the rule-3 guard now also scans `e1b_alns.py`) and the
  merged `test_harness.py`: 80 passed. Two test bugs were fixed before any dev run: pydantic actions are not hashable
  (itineraries are now compared by their JSON), and the "the test exercises something" check now applies over both
  instances (S 9702 has nothing to certify at seed 1 and 300 iterations; a check across processes with five hash seeds
  gave identical plans, so this was not nondeterminism).
* **Dose, on the hand-built tiny case** (scratch diagnostic, dose budget 0.02 kJ/m², 400 iterations): the in-loop oracle
  checked 6 changed itineraries and cut 40 residents (DOSE_ABOVE_BUDGET) from the candidates, none of which then beat
  the warm start's relaxed value, so E1b returned B1's plan unchanged: 5 delivered, 8 model_no_route, exactly B1's
  numbers (E1, which certifies the warm start in the loop, returns only checked trips there). This is the documented
  consequence of not checking unchanged warm-start itineraries in the loop; on the dev set no warm start has a trip the
  oracle rejects (E1's 50 runs).
* **Dev smoke** (13:16-13:20 UTC, `dae67e86`, seed 0, 60 s, rows in the scratchpad only):
  | instance | delivered | runtime | certify_s | iterations | what happened |
  |---|---|---|---|---|---|
  | SYNTHETIC-S-grid-t25-s101 | 23/23 | 57.7 s | 1.5 s | 76,511 | one certification (2 changed vehicles) at the first segment end; 1.0 s of in-loop oracle time |
  | SYNTHETIC-L-grid-t50-s109 | 427/646 | 51.7 s | 34.1 s | 1 | warm start 9.2 s (335 planned); the first iteration (whole-vehicle removal, regret-3 repair) took ~9.6 s, mostly 5,271 cold time-dependent routes, and changed 9 of the 10 vehicles (427 relaxed); the time left then only sufficed to certify it: 9 itineraries, 1,538 legs, 32.9 s of oracle time (21.4 ms per leg); certified at 51.7 s, no time for a second iteration; 1 vehicle kept its warm-start itinerary (8 residents, checked by the harness only) |
  As predicted: on L the search gets about one iteration and one certification. B2 delivered 509-516 on L-grid in the
  earlier session. No code or parameter was changed after the smoke.

### Final evaluation (dev, 60 s, seeds 0-4, B2 interleaved in the same holds)

Run once, as pre-registered (the two commands under Setup), both holds at commit `dae67e86` (clean), host `vm (Linux
x86_64, Intel(R) Xeon(R) Processor @ 2.80GHz, 4 cpu, python 3.12.3, vm boot 4169abd4)`: hold 1 (8 S and M instances,
40 pairs) `20261102T132039Z-e1b_alns-x-b2_vrptw-o0`, 13:20:39-14:43:06 UTC; hold 2 (2 L instances, 10 pairs)
`20261102T144553Z-e1b_alns-x-b2_vrptw-o0`, 14:45:53-15:15:33 UTC. Each pair: a speed probe, B2 with seed s, E1b with
seed s, each followed by the harness's cold certification (`certify_s`, outside the budget). Rows:
`evacplan/results/e1b_alns.csv`, `evacplan/results/b2_vrptw.csv` (B2 seeds 0-4 of this host), speed checks
`evacplan/results/speed/speed_check.csv`; per run: [`results.csv`](results.csv) (from [`e1b_analysis.py`](e1b_analysis.py)).

**Verdict (leaderboard): no (worst 1444 ≤ bar 1751).** Bar on this host = max(B2 best observed 1750 [recorded],
best-of-baselines total 1751 [recorded; this host's B2 rows give 1749]) = 1751.

| SYNTHETIC dev, 60 s, vm boot 4169abd4 | seed 0 | seed 1 | seed 2 | seed 3 | seed 4 | median [min–max] | worst |
|---|---|---|---|---|---|---|---|
| **E1b** | 1537 | 1583 | 1446 | 1444 | 1444 | **1446 [1444–1583]** | **1444** |
| B2 OR-Tools VRPTW (same holds, seed s) | 1749 | 1749 | 1749 | 1749 | 1749 | 1749 | 1749 |

By size, E1b / B2 per seed: **S 109 / 108** (every seed); **M 605 [605–607] / 597**; **L 730 [730–869] / 1044**. Per
hold: S and M 714 [714–716] / 705; L 730 [730–869] / 1044.

| instance | residents | B2 median | E1b median [min–max] | E1b − B2 | time to certified plan (s, median), B2 / E1b | E1b `certify_s` | E1b iterations (median [min–max]) | E1b in-loop oracle calls | E1b in-loop oracle time (s) |
|---|---|---|---|---|---|---|---|---|---|
| SYNTHETIC-S-grid-t25-s101 | 23 | 23 | 23 | +0 | 58.9 / 59.1 | 1.4 | 68,823 [57,612–81,179] | 2 [2–3] | 1.6 [1.2–2.7] |
| SYNTHETIC-S-geo-t25-s102 | 39 | 36 | 37 | +1 | 61.1 / 61.2 | 3.5 | 26,296 [24,613–27,263] | 2 | 3.8 [3.6–4.2] |
| SYNTHETIC-S-grid-t75-s103 | 27 | 23 | 23 | +0 | 58.7 / 58.9 | 1.2 | 48,652 [46,874–55,910] | 1 | 1.2 [1.0–1.3] |
| SYNTHETIC-S-geo-t75-s104 | 26 | 26 | 26 | +0 | 58.5 / 58.7 | 1.0 | 63,064 [58,597–73,737] | 1 | 1.0 [1.0–1.5] |
| SYNTHETIC-M-grid-t25-s105 | 163 | 163 | 163 | +0 | 62.0 / 62.1 | 4.5 | 2,673 [2,252–2,955] | 14 [9–19] | 18.1 [11.4–19.5] |
| SYNTHETIC-M-geo-t25-s106 | 155 | 155 | 155 | +0 | 62.7 / 62.4 | 5.5 | 2,870 [2,452–3,815] | 16 [9–25] | 15.9 [9.9–23.8] |
| SYNTHETIC-M-grid-t75-s107 | 168 | 140 | 148 [148–150] | +8 | 63.5 / 64.5 | 6.8 | 996 [794–1,016] | 10 [9–18] | 18.1 [15.7–22.9] |
| SYNTHETIC-M-geo-t75-s108 | 149 | 139 | 139 | +0 | 63.6 / 64.1 | 6.7 | 1,230 [760–1,435] | 18 [15–24] | 25.1 [20.4–35.9] |
| SYNTHETIC-L-grid-t50-s109 | 646 | 516 | 335 [335–427] | −181 | 89.4 / 86.8 | 32.6 | 1 [1–29] | 8 [7–10] | 29.7 [23.6–35.8] |
| SYNTHETIC-L-geo-t50-s110 | 579 | 528 | 395 [395–486] | −133 | 84.1 / 83.6 | 30.4 | 14 [1–24] | 8 [5–10] | 23.4 [14.5–31.6] |

B2 delivered the same on every seed of both holds. On S and M every E1b plan was fully checked by the oracle in the
loop (every returned itinerary had changed; 0 unchanged warm-start itineraries).

**The 10 L runs, one by one:**

| L run | E1b | B2 | iterations | new bests | relaxed best | in-loop oracle: itineraries / legs / s | outcome |
|---|---|---|---|---|---|---|---|
| L-grid s0 | 427 | 516 | 1 | 1 | 427 | 9 / 1,538 / 35.3 | certified at 54.1 s (9 changed vehicles, 1 kept its warm-start itinerary) |
| L-grid s1 | 383 | 516 | 1 | 1 | 383 | 10 / 1,757 / 35.8 | certified at 54.5 s |
| L-grid s2 | 335 | 516 | 14 | 6 | 533 | 7 / 1,118 / 23.6 | certification cut short: B1's plan returned |
| L-grid s3 | 335 | 516 | 1 | 1 | 388 | 8 / 1,419 / 29.7 | certification cut short: B1's plan returned |
| L-grid s4 | 335 | 516 | 29 | 7 | 530 | 7 / 1,132 / 24.2 | certification cut short: B1's plan returned |
| L-geo s0 | 395 | 528 | 8 | 5 | 530 | 8 / 1,246 / 23.4 | certification cut short: B1's plan returned |
| L-geo s1 | 486 | 528 | 1 | 1 | 486 | 10 / 1,604 / 31.6 | certified at 50.2 s |
| L-geo s2 | 395 | 528 | 14 | 5 | 522 | 8 / 1,226 / 23.9 | certification cut short: B1's plan returned |
| L-geo s3 | 395 | 528 | 15 | 8 | 526 | 7 / 1,091 / 22.3 | certification cut short: B1's plan returned |
| L-geo s4 | 395 | 528 | 24 | 1 | 521 | 5 / 707 / 14.5 | certification cut short: B1's plan returned |

| E1b vs B2, sums over the 10 instances per seed | E1b median [min–max] | B2 median [min–max] |
|---|---|---|
| delivered (checked in all K members) | 1446 [1444–1583] | 1749 |
| unresolved / model_no_route | 0 / 0 | 0 / 0 |
| not planned | 529 [392–531] | 226 |
| delivered with slack ≥ 5 / 15 / 30 min (30 min: provisional default) | 1351 [1283–1428] / 1267 [1265–1311] / 1030 [992–1061] | 1482 [1473–1514] / 1464 [1463–1464] / 1285 [1284–1285] |
| minimum slack | 1.9 s (B1's plan on L-grid) | 16.7 s |
| mean runtime / mean time to certified plan (runtime + `certify_s`) | 56.7 s / 66.3 s | 57.5 s / 66.3 s |
| runs over budget | 0 of 50 | 0 of 50 |
| residents the in-loop oracle cut (dose or otherwise), relaxed-check blocks, emit errors | 0, 0, 0 | – |

**Speed checks.** The probe (a fixed 1.5 M-step pure-Python loop before every pair) took 0.155 s [0.099–0.257] in hold 1
and 0.152 s [0.104–0.217] in hold 2: the leaderboard flags both spreads (102 % and 74 % of the median; threshold 10 %).
The values alternate between about 0.10 and 0.20 s over the whole of hold 1, with no trend. One process listing during
hold 2 showed only the hold running (load average 1.00). B2's delivered counts were identical in all five seeds of each
hold and E1b's S and M totals varied by 2, so the variation does not show in those counts. E1b's L outcome depends on
whether a certification fits in the time left, so it is the result most exposed to machine speed.

**What happened.**

* **S and M: E1b repeats E1, with every trip checked by the oracle in the loop.** S 109 vs B2 108 (S-geo-t25-s102: 37
  vs 36 in every seed), M 605-607 vs 597 (M-grid-t75-s107: 148-150 vs 140), equal elsewhere: E1's medians (an earlier
  VM session). The in-loop oracle took 10-36 s per M run (E1: 15-37 s); E1b saves essentially only E1's calibration
  check there, because every returned S and M itinerary was a changed one.
* **L: the in-loop certification of one changed plan does not fit, or barely fits.** Where a candidate was certified,
  the first iteration had changed 9-10 of the 10 vehicles: 1,500-1,800 legs at the measured 18.8-22.9 ms per leg (E1's
  `oracle_s_per_leg` on this host), i.e. 32-36 s of the ~47 s left after the warm start (7.9-10.2 s).
  * In 4 runs the first iteration was slow (8-13 s: cold time-dependent route caches, regret repair). E1 keeps twice the
    recent iteration time free, so the trigger ("the time left only suffices to certify") fired right after it. The
    certification fit in 3: 427, 383, 486, against B1's 335 and 395. In L-grid s3 the per-check guard refused the next
    itinerary after 8 had been checked.
  * In the other 6 runs the iterations were fast (1-2.5 s on average). The trigger estimated the certification at E1's prior,
    0.01 s per leg x 1.5 = 15 ms per leg: no changed itinerary had been checked yet, and E1b never checks a warm-start
    one (pre-registered consequence). The true cost was 19-23 ms per leg, and E1's per-check guard then wants 1.5x the
    measured cost before each vehicle. The certification started too late (29-40 s into the run): 5-8 changed
    itineraries were checked, and the guard refused the next. By E1's unchanged flow a certification that does not
    complete ends the search, so E1b returned B1's plan. In these runs the relaxed best was 521-533: as good as B2 (516, 528) and the post hoc
    no-oracle variant (525-553), but not certifiable in the time left.
  * Even when it fits, one certification takes most of the L budget. The best L outcome here (L-geo s1, 486) is still
    42 below B2's 528.
* **Time to certified plan** (the new secondary metric) is the same for both, 66.3 s on average: E1b's runtime is about
  1 s shorter (on L it stops when its certification ends or fails, 50-56 s), and its final certification takes about
  as long as B2's (S 1-4 s, M 4-7 s, L 28-37 s). The harness certifies with a fresh oracle, so E1b's in-loop checks
  do not shorten `certify_s`.
* **Dose.** No in-loop check cut a trip in any of the 50 runs, and no returned plan had an unresolved or
  model_no_route resident: on the dev set the relaxed model was exact again, as in E1.

## Decision: KILL

By the pre-registered rule: the worst of 5 (1444) is below 1751. This was E1's second and last approved iteration
(DECISIONS 2026-11-02: "Kill only if E1b's worst of 5 seeds is still below 1751"), so the E1 line ends here. The
prediction recorded before the run ("KILL is the more likely decision") held, through the failure mode named there: on L
the in-loop certification of a changed plan does not fit, or fits once.

## Next step

No further E1 runs. What the two iterations established, for Siyeong's next decisions (none of this is started):

1. **E1's search is not the limit; certifying inside the budget is.** On S and M the ALNS beats B2 at equal time with every
   trip oracle-checked in the loop (+1, +8). On L its relaxed best reached B2's level (521-533 vs 516/528) in 6 of 10 runs
   within 20-30 s of search, but one in-loop certification of a changed L plan costs 32-36 s at ~20 ms per leg.
2. **Oracle speed** (profile above) is the lever for any method that certifies in the loop on L, and it also bounds the
   new metric: the harness's cold certification costs 25-37 s per L plan. The four proposals in the profile section
   (estimated 2-3x on a cold check, not measured) are hazard_contract and oracle internals: the orchestrator's
   decision, with a bit-for-bit regression test.
3. **A cost estimate that is right from the start** might have rescued some of the 6 late-trigger runs on L (not
   measured), for example by timing the oracle on a short changed itinerary (never a warm-start one) before the search.
   Even then one certification takes most of an L run. It would be a third E1 iteration, outside the approved budget.
4. **The post hoc variant with no in-loop oracle** (E1's `posthoc/`: 1774-1799 per seed in an earlier VM session, one
   run per seed, not pre-registered) is the strongest evidence that E1's plans beat B2 when certification is left to
   the harness, as it is for B2. It leaves dose entirely to that final check. It could only be run as a new,
   pre-registered experiment if Siyeong wants that trade-off.

## Changes after seeing dev results

* Method (`e1b_alns.py`), its tests and the parameters (E1's): none after the dev smoke. The smoke and both holds ran at
  `dae67e86`.
* README only: the results, decision and next step above; the "Before the final run" section was written during hold 1
  (kept outside the checkout until hold 2 had recorded its commit, so that both holds ran at the same clean commit).
  `results.csv` comes from `e1b_analysis.py`, which was committed before the final run and is unchanged.

## Budget used

* Bench time: profile 7 min (12:49-12:57 UTC), tests about 12 min (13:03-13:15), dev smoke 3 min (13:16-13:20), final
  holds 82.5 min (13:20-14:43) and 29.7 min (14:45-15:15), leaderboard regeneration under the lock afterwards.
* Work: about 3 h (12:40-15:40 UTC), within the 5 h stated.
