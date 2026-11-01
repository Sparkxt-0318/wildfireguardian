# Checkpoint 2: Phase 0 of both tracks + independent review

**Date:** 2026-10-31.

**Track C numbers are on SYNTHETIC instances.** Track A has no numbers yet.

**Details:**
- `program/reviews/phase0-review.md`: the review and the status of each fix.
- `program/DECISIONS.md`.
- `evacplan/docs/ASSUMPTIONS.md`.
- `firecast-lab/README.md` and `firecast-lab/docs/DATA_NOTES.md`.

## In short

- **Track C Phase 0 is done, except the Caldor instance.** The oracle, generators, frozen dev/test split, harness and
  baselines B0–B3 all work, and 310 tests pass. Caldor is blocked here: this host cannot reach OSM, CMS or the
  Census geocoder. The builder is written and no data was invented.
- **Coordination pays off.** On dev at 60 s, B2 (OR-Tools VRPTW) delivers 1682 of 1975 residents (85.2 %), or 1750
  in the review's run. B0, where each facility plans alone, delivers 1157.
- **Track A is built and tested but has no real-data number.** Harness, baselines, metrics, decision metric, producer
  and leaderboard aggregator pass 125 tests. The data root, the NIROPS perimeters and torch are on Siyeong's Mac.
- **The independent review found nothing critical.** It found 4 major and 15 minor problems; all are fixed, with
  regression tests. Both tracks are merged into `next/integration` and every suite passes.
- **What can start when:** Track C Phase 1 can start now on SYNTHETIC dev. Track A waits for data access
  (question 1).

## 1. Track C leaderboard (dev, 60 s budget, SYNTHETIC, 3 repeats per method)

Columns:
- **delivered**: residents whose trips the oracle checked in all K members (share of 1975 in brackets). Shown as
  mean [min–max] over seeds 0, 1 and 2.
- **unresolved**: never counted as delivered.
- **not planned**: residents that no itinerary boards.

All rows are at clean commit `b43990bb`; the rows are committed in `evacplan/results/`.

| method | delivered | unresolved | not planned | min slack | mean runtime |
|---|---|---|---|---|---|
| B0 independent (each facility alone) | 1157 (58.6 %) | 0 | 818 | 403 s | 0.5 s |
| B1 greedy EDF insertion | 1353 (68.5 %) | 0 | 622 | **1.9 s** | 1.8 s |
| B2 OR-Tools VRPTW | 1682 (85.2 %) [1682–1682]; **1750 / 0 in the review's run** | 68 | 225 | 16.7 s | 57.5 s |
| B3 HiGHS MIP (S only: 4 instances, 115 residents) | 103.7 [103–104] | 0 | 11.3 | 223 s | 33.8 s |
| noop | 0 | 0 | 1975 | – | 0 |

| delivered by size | S (115 residents, 4 instances) | M (635, 4) | L (1225, 2) |
|---|---|---|---|
| B0 | 81 | 432 | 644 |
| B1 | 104 | 519 | 730 |
| B2 | 108 | 529 | 1045 |
| B3 | 103.7 | – | – |
| best proven bound | 114 | none yet | none yet |

**What the numbers mean:**
- **One resident cannot be served.** It is on S-grid-t75-s103: no plan can serve this resident within the model, the
  fleet and the horizon. The oracle reports it as a scoped `model_no_route`.
- **B2's result depends on host load.** B2 is seedless and stops at a time limit, so its outcome depends on how far
  the search gets.
  - On a quiet host its 3 repeats were identical: 68 residents unresolved, all on one bus on M-geo-t25-s106 whose
    cumulative dose the oracle cannot certify.
  - In the review's slower run, the search stopped earlier and all 155 residents on that instance were checked:
    1750 / 0 in total.
  - The cause is that B2's model has no dose term.
  - Interim bar for "beats B2": the minimum of 3 repeats must exceed **1750** (question 3).
- **Checked trips can have almost no margin.**
  - B1's worst trip clears the fire by 1.9 s in some member.
  - 3 of 10 instances under B1, and 2 of 10 under B2, have a trip with less than 60 s of slack.
  - "Checked" has no margin today (question 5).
- **B3 is weaker than B2 on S.** It does not close its gap in 60 s and delivers less than B2 on S. Its certified bound
  (114 of 115 on S) is the only bound so far; M and L have none (E4).
- **Simply picking the better plan already reaches 1751.** Per instance, the better of B1 and B2 totals 1751. E1 must
  beat that too, to show that the gain comes from search rather than from picking.

## 2. Track A leaderboard

**There is no leaderboard, because no real-data rows exist.** The cloud host has none of what a real row needs:
- the data root, with the Choi et al. reconstructions, which are the labels;
- the NIROPS perimeters, which also still need a loader;
- torch, which c651 needs.

`firecast-lab/LEADERBOARD.md` explains this and holds no synthetic numbers.

**What exists:**
- The baselines: persistence, tuned dilation, calibrated best dilation (the bar), logistic, and a c651 wrapper. All
  produce spatially coherent members and are cross-fitted by whole-fire folds.
- `METRICS.md`, and run rows with additive terms for every metric.
- The aggregator, with whole-fire bootstrap intervals.
- The decision metric through the oracle.
- The `hazard_contract` producer.

**Measured cost of the decision metric:**
- 3.3 min per window, on the real Uljin road graph with a SYNTHETIC fire.
- About 56 min per model for the roughly 17 Korean dev windows that have road graphs.

## 3. Oracle test results

Everything passes on the merge: evacplan 310 tests, hazard_contract 76.

- **Hand-worked cases** (26 tests):
  - closed-cell contact, including corners and waits in a cell that ignites;
  - exact safety slack;
  - dose across trips and per member;
  - peak-flux bounds;
  - unresolved, never delivered, for: running past the horizon, contact only after the horizon, an unknown cell
    on the route, and leaving the grid;
  - resource violations are `model_no_route` from that action on;
  - residents left on board;
  - plan accounting and labels.
- **Property tests on random SYNTHETIC cases** (17 tests over 7 properties, 150–300 cases each):
  - Adding any of 11 constraints never turns anything into checked. The 11 are: peak or dose budget, shelter window,
    vehicle space, shelter capacity, residents, burning cells, release, shift, turn rules and waitable nodes.
  - Unresolved never counts as delivered, and every delivered resident is re-verified independently.
  - Unknown data under a checked leg makes it unresolved, and an all-unknown hazard delivers nobody.
  - The relaxed check agrees exactly with `hazard_contract`.
  - Slack is exact.
- **Relaxation claims** (new in the fix round): whenever the oracle declares a class unservable (NO_ROUTE,
  NO_VEHICLE_IN_TIME or NO_TRIP_BY_HORIZON), an independent exhaustive search finds no trip. 8 tests: 150 random
  and 6 fixed cases.
- **Rule 3 guard** (new, AST-based): only `evacplan.oracle` constructs final states. It catches 13 declaration
  patterns and allows 12 reading patterns (36 tests together with the relaxed-check tests).
- **`hazard_contract` property tests:**
  - adding burning never turns contact into no contact and never lowers the flux upper bound;
  - unknown data is always unsupported;
  - the real Uljin packet test passes.
- **Accounting identity**, checked by the reviewer on every result row: delivered + unresolved + model_no_route +
  not planned = residents.

## 4. Independent review

**Method.** Each track got a fresh agent that had written none of the code, working from a clean checkout with a
fresh venv. A second agent then tried to refute each finding.

**Verdict.** No critical findings. 4 major:
- B2's run-to-run swing;
- unpinned OR-Tools, where 9.15 crashes B2;
- partly burned edge cells counted as never burning in the Korean decision truth;
- Track A metrics coded but never produced by any run.

15 minor. All are fixed (`phase0-review.md`, "Fix status").

**Checks that passed:**
- B1 reproduces exactly.
- The three-state rule, the splits, equal-time comparisons and provenance pass on both tracks.

## 5. Data problems

1. **This program runs in a cloud container, not on the Mac.**
   - Out of reach: the data root (Choi reconstructions, environment stacks), the NIROPS archive (1.39 GB), the sealed
     Caldor/Rim graph and packets, and torch.
   - Blocked hosts: zenodo.org, data.mendeley.com, data.cms.gov, overpass-api.de, geocoding.geo.census.gov and
     download.pytorch.org.
2. **The Korean router packets are mostly unsupported under rule 4.** 32–100 % of road cells have no native
   probability or an unknown burned state, so those packets mostly give `unresolved`. This is by design.
3. **The fresh holdout is empty.** NIROPS v1 ends in 2024. US 2025 needs a newer release; KR 2026 needs a new
   reconstruction.
4. **Korean label timing is loose and the fires are short.**
   - The labels' timing error is MAE 7.65–12.18 h, so the headline lead is 24 h and 12 h is a diagnostic only.
   - Six Korean dev fires are too short for 24 h windows.
   - Only about 17 Korean dev windows have road graphs (Uljin, Hongseong, Miryang).
5. **Three sources of hindsight:**
   - The reconstruction NoData mask leaks the final scar, so support masks use cutoff information only.
   - The cutoff state uses detections from the whole event: a smaller leak, accepted and stated.
   - The grid edge is a hindsight wall: nothing can burn beyond the final perimeter's box.
6. **Weather and fuels are crude.** The weather is archived IFS, repeated from the cutoff through the horizon. Static
   vegetation is from 2019.
7. **Heat sources outside a scenario grid are not modelled,** so producers pad their grids.

## 6. Assumptions to check (defaults in place; nothing is blocked)

### Track C

Numbers are those of the "Questions for Siyeong" in `evacplan/docs/ASSUMPTIONS.md`.

- **Q7 Persistent burning (48 h).** Burned roads stay closed, which gives "before roads close" deadlines. The study
  packets burn for 66 min.
- **Q1 Exposure inside the facility.** Residents' exposure inside a facility before boarding is not checked. Under
  persistent burning this is moot, because a vehicle cannot reach a burned facility.
- **Q4 Contact only after the horizon** is `unresolved`.
- **Q5 Dose budget per vehicle,** which is conservative, rather than per resident from boarding.
- **Q12 Unservable vs not planned.** Refusals that hold even with nothing burning are a scoped `model_no_route`
  with the cause `NO_TRIP_BY_HORIZON`.
- **Q10 Equal counting.** The objective counts every resident equally. This favours ambulatory residents: a bus
  trip moves 40, an ambulance trip 1. Weight the classes, or add per-class columns?
- **Q13 B0 definition.** Each facility plans alone with the whole fleet, and the shared fleet serves bookings first
  come, first served. The alternative is a static split of the fleet.
- **Q15 B2's inputs.** B2 sees free-flow static times; the hazard reaches it only through the pickup windows, as
  specified.
- **Q16 B3's bound.** Only the certified bound is reported.
- **Q17 Threads.** All methods run single-threaded.
- **Smaller points:**
  - Q8: the mobility mix is a placeholder (SNF 75/18/7 %, ALF 90/9/1 %).
  - Q9: buses have 2 wheelchair slots; ambulances 1 stretcher.
  - Q14: deadline definitions.
  - Q2: turn context resets at stops.
  - Q3: no space substitution.
  - Q11: Caldor choices.

### hazard_contract

- **Projected CRSs only.** Geographic and Web Mercator CRSs are refused, which tightens the interface.
- **No opt-out from rule 4.** A labelled "packet policy" mode could reproduce the router's handling of
  policy-assigned cells, for comparison only. Is that wanted?

### Track A

From the `firecast-lab/README.md` open questions and DATA_NOTES §7.

- **Member coupling.** Shared field vs Gaussian copula at L = 8 cells (3 km, a placeholder).
- **Present fire.** Each cell's reconstructed arrival ("exact") vs the router's R_max enclosure.
- **Truth from perimeters** uses the envelope, so false-safe is an upper bound with respect to timing between
  surveys.
- **Edge-cell ring envelope** (from the A-M1 fix). Keep it, or narrow it to the earliest neighbour's interval?
- **Request population:**
  - origins within 3 km of the front;
  - 2–4 km trips;
  - half the origins wait up to 1 h;
  - budgets: 10 kW/m² peak, 100 kJ/m² dose.
- **Cutoff-state rule.** Outside the final scar, the generator input is "not burned at cutoff". The alternative,
  "unknown", leaks the final scar.
- **The 3 km headline buffer.**
- **Leaderboard details:**
  - Spread-skill uses fixed sd bins.
  - Reliability uses the member share, so the sub-1 % bins stay empty at K = 64. Should the probability field's
    reliability be pooled too?
  - c651 may score fewer cells than the other baselines. Rescore them all on the shared cells, or report c651
    separately?

## 7. Decisions needed before Phase 1

1. **Data access** (repeated from checkpoint 1). Track A and the Caldor instance need the Mac's data or the blocked
   hosts. Track C Phase 1 on SYNTHETIC dev needs none of this. Choose one:
   - **a. Run the program on the Mac** (Claude Code locally, same branches and rules). Recommended: everything is
     there.
   - **b. Connect the Mac to this session through Remote Control.** In the Claude desktop app: Settings, Claude Code,
     Remote Control, then add the repo folder. The data steps would then run there.
   - **c. Allow the blocked hosts** in this environment's network settings and approve these downloads:
     - NIROPS, 1.39 GB (over the 1 GB limit);
     - the CMS provider file;
     - OSM through Overpass;
     - the Census geocoder;
     - the torch CPU wheel;
     - the Choi reconstructions from Zenodo.
2. **Approve Track C batch 1:** E1, E4 and E3 (below).
3. **B2 bar.** Keep the interim rule (minimum of 3 repeats above B2's best observed total, now 1750)? Or stop B2 at a
   solution limit fixed in advance, so that it is deterministic? Recommendation: keep 1750.
4. **Dose in the planners** (evacplan Q18). B2's model has no dose term, which is why s106 fails. Leave dose to the
   methods with the oracle in the loop (E1)? Or give the planners a cheap dose estimate, which makes B2 a stronger
   baseline? Recommendation: keep B2 as specified and let E1 handle dose.
5. **Safety margin.** A checked trip can clear the fire by 1.9 s. Should a trip need a minimum slack to count? That
   changes the problem definition. Or should the leaderboard add "delivered with slack ≥ 5 min" next to delivered?
   Recommendation: add the column now, and decide on a margin after E3.
6. **scikit-learn 1.5.2 and hypothesis,** which rule 8 does not list. Approve them? scikit-learn is the frozen
   `forecast` package's own extra, used by the logistic baseline; hypothesis is test-only.
7. **Rule 5 note.** Track A's data notes read survey-interval metadata of the six US-2024 test fires and Korean
   test-fire window counts, with no outcomes and no scores. Keep these numbers, or remove them?

## 8. Proposed first 3 experiments per track

All on dev only. Each states a budget and ends with KEEP, KILL or ITERATE.

### Track C (can start now; SYNTHETIC; 60 s per instance, 3 repeats)

**E1: ALNS with the oracle in the loop.**
- **Hypothesis.** The minimum of 3 repeats exceeds both 1750 (B2's best) and 1751 (the per-instance best of B1 and
  B2), with no unresolved.
- **Why.** B2 loses residents in two ways:
  - its static model (free-flow times, no dose: s106);
  - the 225 residents it leaves unplanned on tight instances.

  ALNS can fix both:
  - destroy/repair search: random, worst-slack and related removal; regret insertion;
  - the relaxed contact check inside the loop;
  - the oracle on each new incumbent, so dose is covered ("search cheaply, check expensively");
  - acceptance that follows the lexicographic objective.

  It warm-starts from B1 within the same 60 s.
- **Budget.** 2 iterations. KILL if the minimum of 3 is still ≤ 1750 after the second.

**E4: dynamic-flow upper bound.**
- **Hypothesis.** A max-flow-over-time relaxation on the contact-free time-expanded network gives a valid upper bound
  for M and L, within about 15 % of the best plan on M.
- **Why.** Every plan induces a feasible flow (temporally repeated flows, Ford–Fulkerson; quickest transshipment,
  Hoppe–Tardos), so the bound is valid. It is polynomial where B3's MIP does not finish.
- **Validity tests.** The bound is ≥ every checked plan on dev, and ≥ B3's optimum on tiny instances.
- **Decision.** KILL if the bound is invalid and cannot be fixed. If the gap is above 30 %, KEEP it as a sanity bound
  only.

**E3: scenario robustness.**
- **Hypothesis.** Plans checked in all K members fail, in fresh members from the same SYNTHETIC hazard generator,
  at a rate below the scenario-approach bound (Campi–Garatti). The bound then tells us which K is enough.
- **Setup:**
  - plan with K = 4, 8, 16, 32 and 64;
  - check on 256 fresh members;
  - compare all-K, CVaR over members, and allowing m violated members.
- **Metric.** Out-of-sample violation rate vs delivered.
- **Why it matters.** It measures what "checked in all K" is worth, and it sets the default K and margin
  (question 5).

### Track A (blocked until data access; cross-fitted by whole-fire folds)

**L1: calibration per lead time, plus conformal false-safe control.**
- **Hypothesis.** Isotonic or beta calibration beats calibrated best dilation on Brier skill, with a whole-fire
  bootstrap interval that excludes zero. Conformal risk control (Angelopoulos et al. 2022) keeps false-safe ≤ 5 % at
  a useful clearance rate.
- **Why.** SMOKE underpredicts low probabilities: 37 % of new burns fall in the < 1 % bin, and 617 positives got
  exactly 0. Monotone recalibration fixes reliability without changing the ranking.
- **Decision.** KILL if the interval includes zero and false-safe does not improve.

**L8: ensemble honesty.**
- **Hypothesis.** The members are under-dispersed: rank histograms are U-shaped and spread is smaller than error.
  Inflating member timing perturbations, as weather ensembles do, flattens the histograms and lowers false-safe at
  matched clearance.
- **Decision.** KILL if false-safe at matched clearance does not move.

**L2: fat-tailed kernel plus a background rate.**
- **Hypothesis.** A heavy-tailed (2Dt) long-range term plus a small background ignition rate brings the zero-probability
  positives from 617 to about 0, and fixes the < 1 % bin without hurting Brier skill.
- **Why.** A 9×9 kernel is exactly zero beyond its support; spotting and model error are not.
- **Needs** torch, so it must run on the Mac.
- **Decision.** KILL if Brier skill drops with an interval that excludes zero.

## Next

Nothing new runs until Siyeong answers. After approval, the answers go into `program/DECISIONS.md`.
`next/integration` is then merged into both track branches, and batch 1 starts. It runs at most 3 agents, each in
its own worktree on an `exp-` branch, with timed runs through the bench lock.
