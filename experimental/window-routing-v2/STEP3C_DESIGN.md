# Step 3c: outcome determinism independent of host speed (rule and test list; design only, no code)

Source: PLAN.md "Step 3c" (assessor design, adopted). This file turns that design into a rule and a test list for the
assessor, before any code is written. It adds one measured finding from the Step 3 rebase.

## The finding that changes the preflight (measured)
- On the replaced container (2026-11-13), the same kit and request (Yeongdeok kriged_mean …166) ran:
  - Z about 9% slower than on the reference host (10.5 s against 9.65 s);
  - the bound model's numpy coefficient work about **40% slower** (coef_s 67.1 s against 48.1 s, for an identical
    1,404 boxes).
- The pure-Python host-speed proxy from Step 3 (Z-sweep units/s) moved by only **3%** (28.6 M against 29.4 M/s).
- **So a pure-Python preflight would have called this host normal.** The preflight must measure each kind of work the
  stages do, separately. One scalar is not enough. (STEP3_RESULT, "Known limit, measured again on this host";
  `results/step3rebase/ab166/`.)

## Rule

### R1. Every stage is bounded by work units
| Stage | Work unit (the counter Step 3 already ticks, or the one to add) | Budget source |
|---|---|---|
| Z (setup, sweep) | setup units; sweep units | existing, 2^12 / 2^28 (Step 3) |
| LO, LO2, HI | expansions + bound-model boxes, ticked where Step 3 checks the wall | calibrated by Step 3's rule (1-hour panel only, median work in the stage's current cap, rounded up to a power of two), committed before any F-DYN run |
| EA build | backward-sweep seconds × states | same calibration rule |
| Admission, preparation, bound-model build | loop iterations (edges, members, boxes) | same rule. These are finite today; the budget makes the bound explicit |
| Whole-road checks (HybridChecker, adaptive fallback) | **not work-bounded.** This is shared, certificate-adjacent code; it needs the certificates reviewer before any edit | bounded only by the job-level watchdog (R2) |
| Publication, final binding | none (short, deterministic) | job-level watchdog |

- A stage that hits its work budget stops with the stage's existing incomplete-cap reason, never a new verdict.
- Unit counts are identical on any host.

### R2. One wall watchdog, at job level only
- There are no per-stage wall watchdogs. The Step 3 per-stage SIGALRM watchdogs become diagnostics, or are removed.
  The assessor rejected deriving stage caps from the remaining time.
- The job deadline stays the API's 81 s complete budget.
- **When the job-level watchdog fires,** the result carries a distinct status: **`HOST_TOO_SLOW_FOR_JOB`**.
  - It is never reported or compared as a model verdict.
  - It is never plain UNRESOLVED.
  - The planner/API maps it to its own label, with no route and no refusal.
  - The status names the stage that was running and that stage's unit count.

### R3. Host-speed preflight: one factor per kind of work, measured at job start
- **A fixed work-unit microbenchmark** for each kind of work the stages do:
  - (a) pure-Python label work (Z-sweep and road_core-like dict/heap operations);
  - (b) numpy batch arithmetic, shaped like the bound model's coefficient batches;
  - (c) exact `Fraction` arithmetic, shaped like `edge_occupancies`.
- Each is timed against a reference value committed with the code. The record is `host_speed: {python, numpy,
  fraction, max}`, in every result.
- **Comparability:** `max` > the stated factor (the validity margin, measured in T5) flags the run "not comparable"
  in the result. It never changes the verdict.
- **Preflight cost:** stated, measured, and at most 1 s per job. Its own wall time is reported.

## Tests (written before code; the assessor reviews this list before any code)
- **T1. Reference host:** the 1-hour panel's verdicts and arrivals are unchanged; G1 and G3 are as in Step 3; G6 passes
  under the rule in force.
- **T2. Unit determinism:** each stage's unit count is identical across two runs, and across hosts (the verifier's
  build).
- **T3. Injected slowdown** at factors 1.5, 2 and 3:
  - two injection modes, each tested separately:
    - (i) a per-unit delay in pure-Python work;
    - (ii) a delay inside the numpy batch call;
  - unit counts are identical to factor 1;
  - verdicts are identical until the job-level watchdog fires, and after that only `HOST_TOO_SLOW_FOR_JOB` appears;
  - **zero cases** where slowdown turns a refusal or a route into another model verdict, or into plain UNRESOLVED;
  - FD1 keeps its refusal at 2×.
- **T4. Preflight sensitivity:** under injection (ii), the preflight's numpy factor rises by the injected factor
  (within a tolerance stated before the run), while its python factor does not. This is the property the measured
  finding showed was missing.
- **T5. Validity margin:** the factor at which the job-level watchdog first fires on the 1-hour panel and the F-DYN
  set is measured and reported per work kind.
- **T6. Watchdog status discipline:** a synthetic non-returning check (the checker stays unbounded) under the
  job-level watchdog gives `HOST_TOO_SLOW_FOR_JOB` with the stage named. It is never UNRESOLVED and never a refusal.
- **T7. API mapping:** the classifier (`api.verdict.classify`) receives `HOST_TOO_SLOW_FOR_JOB` and gives its own
  label, never `unresolved` with reason TIMEOUT. That keeps G6's time-capped closed list unaffected.

## Interactions stated up front
- **G6b** runs on the current kit (0fffb589) under the amended definition. Step 3c changes stage stopping, so after it
  lands, the G6 gate is rerun on the new kit under whatever rule is then in force.
- **Step 3b** (edge_occupancies cache) waits for G6b. It changes the cost of a unit, not its count.

## Not in scope
Editing the whole-road checker. Changing the 81 s complete budget.
