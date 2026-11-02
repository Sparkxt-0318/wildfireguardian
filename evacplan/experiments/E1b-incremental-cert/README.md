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
