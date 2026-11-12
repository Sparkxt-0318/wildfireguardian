# Step 3 result: caps enforced promptly, Z on deterministic work budgets (in progress; G2/G2b and F-DYN pending)

Kit `kit-v2-step3e`, branch `claude/priya-kit-v2-step3`, cut from the Step 1 tip with no Step 2 code.
Budgets: setup 2^12 and sweep 2^28, both extrapolated (STEP3_ACCEPTANCE, "Recalibration after the B2 correction").
**Mira has not verified any of this yet.**

## Tests (all on kit-v2-step3e)

- Step 3: 15 unit, Z, determinism, bound-interruption and watchdog-in-job tests (Mira N1: 15, not 14).
- Thomas's conditions: the single alarm, the BaseException classes, downstream reuse, a capped LO that is never a refusal
  or bound, and the alarm disarmed at every whole-road check. All pass.
  - Thomas's whole-state completeness sweep passes on Hongseong 0402T14 FW2 and Uljin 0304T12 FW2 at k ∈ {1, 2, 3, 5,
    last}: no partial entry, nothing from the interrupted chunk, byte-identical replay, identical reachable state.
- Builder (exact Step 3 worker lines pinned) and Step 1 reasons: pass. Parent runner ok (only the provenance tests fail).
- Bugs found by the tests and fixed before the panel: after a Z watchdog the EA bound still ran, which is now fixed
  (fail closed). In the test harness itself: the shared `_REGISTRY`, quadratic walks, and repr addresses.

## G1 panel (2026-11-12T23:01:52Z, 20 missions × 2 reps, frozen vs v2 interleaved, 81 s, alone on the host, no restart)

`results/step3/G1_COMPARE.json`, rows in `results/step3/panel/`.

| Gate | Result |
|---|---|
| G1 | **20/20**, FL2 rule included; reason changes: none |
| G3 | **20/20** |
| G5 wall | **1.005** |
| G5 memory | pass on all 20 |
| kit_identity | V2 40/40, FROZEN 0 |
| G2 | **28/28** published routes accepted by both frozen checkers in fresh processes (`results/step3/G2.jsonl`) |
| G2b (Thomas's `xcheck/g2b.py` @ deeb7c2) | **40 runs, 0 violations** (38 PASS, 2 NOT_APPLICABLE_STATUS) (`results/step3/G2B.json`) |

**The one status change is Yeongdeok 0325T23 FL2:** frozen CHECKED_JOURNEY_FEASIBLE@1922 (2/2), v2
CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN@1922 (2/2). Both are inside the pre-stated FL2 rule.

**The 3 time-capped missions (Iris's reporting rule; `results/step3/Z_TIMECAPPED_3.json`).** Budget ratios: setup
budget ÷ its median 6 s equivalent = 1.90; sweep = 1.21.

| Mission | Units at its own old 6 s (setup / sweep) | Frozen Z (6 s wall cap) | v2 Z (budgets) | Z under the old cap, from the v2 run | Final, frozen → v2 |
|---|---|---|---|---|---|
| Yeongdeok 0325T19 FD1 | 2,573 / 129.4 M | TIMEOUT WALL_CLOCK, 6.1 s | TIMEOUT **WORK_BUDGET_SWEEP**, 8.6–8.7 s, setup 2,573, sweep 268,508,075 | TIMEOUT | FULL_MODEL_REFUSAL_PROVEN → same (stage LO) |
| Yeongdeok 0325T19 FX2 | 2,573 / 127.0 M | TIMEOUT WALL_CLOCK, 6.1 s | TIMEOUT **WORK_BUDGET_SWEEP**, 8.5 s | TIMEOUT | UNRESOLVED → same |
| Yeongdeok 0325T23 FL2 | 1,066 / 204.7 M | TIMEOUT WALL_CLOCK_AFTER_CHECK, 7.5 s | **CONDITIONAL_OPTIMUM @1922**, 7.7 s, sweep 215,231,775 | TIMEOUT (215.2 M > 204.7 M) | FEASIBLE → **FULL_OPTIMUM_PROVEN** @1922 |

- **FL2's change is the "Z was given more work" effect, stated separately.** Z needs 215.2 M sweep units, slightly
  more than the 204.7 M it reached by 6 s, and the sweep budget is 268.4 M. Z then proves the contact-sweep optimum
  1922, which the checker certifies.
- The FL2 outcome is now the same in both reps. In the frozen kit it depends on timing, which is the variation the FL2
  rule was written for.
- **Stop accuracy:** the sweep stops at the first sweep second over the budget: 268,508,075 against 268,435,456 units,
  an overshoot of 72,619, which is less than E + 1 = 111,925, i.e. one sweep second.
- **Beside any v2-vs-frozen comparison:** Z's budgets are 1.90× (setup) and 1.21× (sweep) the median 6 s equivalents on
  this host.

## Mira's verification (ledger 115, PASS WITH NOTES at 629ef31)

- She re-ran the tests on her own kits: test_step3_work 15/15, test_step3_thomas 6 (+10 subtests), and builder +
  reasons 17 passed / 3 skipped.
- **Second machine:** on all 20 calibration missions, every setup and sweep unit count equals all 3 of my runs
  (FL2's full sweep is exactly 215,231,775). Unit determinism therefore holds across two machines.
- FL2 end to end, 81 s, 2 runs per kit: FROZEN FEASIBLE@1922, V2 FULL_OPTIMUM_PROVEN@1922; no watchdog.
- The panel summary, recomputed from the committed rows, is identical. `kit_identity` was not checked, because the run
  folders are not committed.

**N2: slower-machine margin, stated.** Z no longer has a 6 s wall. Its only wall limit is the watchdog at
max(1.5 × 6, 6 + 10) = **16 s**, and a watchdog firing ends the job's search by fail-closed design. The budget-capped
Yeongdeok 0325T19 FD1/FX2 Z runs took about 8.5 s here.
- **On a machine about 1.9× slower than this host, those jobs would end in `STAGE_CAP_WATCHDOG`**, and FD1 would never
  reach the LO stage that now proves its refusal.
- **Unit determinism holds on any machine; outcome determinism holds only inside that wall margin.**
- (Proposal, not adopted: derive Z's watchdog threshold from the remaining job time rather than the nominal 6 s, since Z
  is bounded by work. That would be a decision for the orchestrator and Iris, with its own test.)

**N3: recorded as a guard against later re-tuning.** Uncapped, on Mira's machine:
- FX2's Z would complete at 281,267,525 sweep units with CONDITIONAL_OPTIMUM@2512, 4.8% above the 2^28 budget, so FX2
  stays UNRESOLVED by that margin;
- FD1's Z would complete at 403,041,925 sweep units as PROVEN_INFEASIBLE.
- **Any later budget change must come from the stated calibration rule, never from these two numbers.**

## Pending

- The F-DYN set:
  - every stage stops within max(1 s, 5%) of its cap, with setup units and setup and sweep wall reported;
  - the A4 rerun, 10 reps × 2 requests at 900 s.
  - These run as tracked, checkpointed background tasks.
