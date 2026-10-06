# Independent integration cross-review — reviewer D

Reviewer D authored `tests/test_crossreview.py` and this review. D did not author the candidate solver, session, fallback, original checker, or original exhaustive reference. C independently authored the checker/reference. A authored the candidate solver; B authored session/fallback; the coordinator subsequently repaired shared numerical and geometry defects. This common repair involvement is disclosed: implementation separation plus adversarial witnesses provides bounded engineering evidence, not independent mathematical proof of all software behavior.

The test cases are DEVELOPMENT fixtures. They do not add to, tune on, or replace the separately frozen 17 evaluation set. D did not read protected final sets, change eligibility or labels, train models, conduct road-scale timings, or publish anything. The frozen input hash is checked in the machine-readable evidence without using candidate outputs as truth.

## Scope and method

D read `CONTRACT_WORKING.md` and actual core, checker/reference, validator, session, fallback, and fixture sources. The new graph project is `routing-delivery-20261004-v1`, generation `2026-10-03T17:45:43Z`. A positive graph search returned 6 relevant functions with no further pagination. Coverage reported no recorded gaps, but core/checker/session/fallback/validator had changed metadata and the new test was not tracked; D therefore used direct current source reads. These signals do not prove complete coverage.

The DEVELOPMENT suite includes 36 freshly seeded cyclic graphs with three separately budgeted ensemble members, time-varying flux/flame, waits, travel durations, and destination dwell/opening variation. Each case compares baseline, Dijkstra, and A* against C's bounded exhaustive timed-walk reference: 108 solver comparisons. No reference returned UNRESOLVED. Candidate occupancy, candidate labels, pruning, or dominance are never used as the test oracle. Additional manual rational and coordinate witnesses challenge shared bugs that two agreeing implementations could otherwise miss.

## Defects and repairs checked

| Finding witnessed by D | Repair ownership | Regression evidence |
|---|---|---|
| Positive dose disappeared when added to incurred `1e16`, allowing an already fully spent budget to pass | A and coordinator; separate checker repair by coordinator | All three solvers and exhaustive reference reject positive travel; a manual rational partial-edge integral verifies exact reported dose |
| Same-node progress changed incoming `BO` to `AO` with no traversal, bypassing forbidden turns | B | Progress refused and subsequent plan remains DISCONNECTED |
| Malformed non-dictionary plan/commit/return inputs raised exceptions | B | Public interfaces fail closed for None/list/integer/Boolean inputs and malformed hazard |
| Request Boolean hazard version and NaN RSS cap passed validation | Coordinator | Boolean version and nonfinite/negative/string/Boolean RSS values rejected |
| Tolerant `.3/.1` lattice admission allowed a rounded schedule to claim infeasibility | Coordinator | Decimal near-lattice rejected; a dyadic `.125` schedule preserves exact `.375` boundary arrival |
| `1e-9` geometry tolerance admitted a positive gap between raster occupancy spans | Coordinator | A `2e-10` unmodelled gap rejected or canonicalized; final implementation rejects it |
| Checked return ignored its wall budget | Coordinator | Zero wall budget returns TIMEOUT; future return dose includes actual incurred exposure |
| Arbitrarily large integer travel ticks and incurred/history/mapping quantities raised OverflowError | Coordinator | Unrepresentable travel, incurred, history and conservative mapping fail closed |
| Interior diagonal raster cutpoint's coordinate cell could be omitted from positive spans and edge endpoint checks | Coordinator | Direct (20,10) coordinate witness checks cell 6, distinct from BD's positive-duration cells 5 and 2 |

Separate cap propagation tests verify that both total label exhaustion and incomparable per-member labels hitting frontier width return TIMEOUT without optimality or infeasibility certificates. Rejected forecast updates invalidate old asynchronous completions; explicitly labeled older accepted guidance can only commit after a fresh plan and route check.

A further source inspection found lingering approximate route continuity/duration/fraction checks. The coordinator removed those tolerances. D read the final exact continuity, rational lattice/duration, and represented fraction checks. This inspection is distinct from the nine witnessed defect groups above.

## Claim boundaries

The suite establishes bounded agreement and repaired witnesses under labelled engineering fixtures. Official frozen 17 evaluation and exclusive road/performance metrics are separate coordinator outputs. This review does not establish scale, forecast skill, road passability, physical thermal thresholds, vehicle protection, shelter usability, Korean field validity, or safe deployment. Activation remains unpromoted.

Exact resource arithmetic means exact rational operations over the represented numeric inputs and admitted occupancy model. It does not restore unknown real-world quantities or original decimal intent lost during JSON-to-binary64 parsing. Geometry intersections and coordinate cell selection are recomputed rationally from the represented coordinates; supplied segment fractions are checked canonical encodings. Request admission restricts the scheduling envelope. `dose_exact` is the resource comparison value; the displayed numeric `dose` is rounded and may be null on overflow. Wall/RSS caps are cooperative checks, not operating-system preemption or a guarantee that a single validation/checker call cannot exceed its budget.

The final run passed 18 DEVELOPMENT tests in 2.040 seconds, including 108 fresh candidate/reference comparisons. Relevant source hashes remained unchanged during that run; the frozen 17 input hash remained `07cb746c06ec8ba3d6ec294e2e168d684b5c3fdf1977826ef9b95763fb3fc4d2`. Details are recorded in `evidence/INDEPENDENT_EVALUATION.json`. A pass is bounded DEVELOPMENT acceptance of these cases, never a claim that the full system is bulletproof.
