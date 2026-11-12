# Step 3 result: caps enforced promptly, Z on deterministic work budgets (in progress; G2/G2b and F-DYN pending)

Kit `kit-v2-step3e`, branch `claude/priya-kit-v2-step3`, cut from the Step 1 tip with no Step 2 code.
Budgets: setup 2^12 and sweep 2^28, both extrapolated (STEP3_ACCEPTANCE, "Recalibration after the B2 correction").
**Mira has not verified any of this yet.**

## Tests (all on kit-v2-step3e)

- Step 3: 14 unit, Z, determinism, bound-interruption and watchdog-in-job tests.
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

## Pending

- G2 and G2b on the published v2 routes (running).
- The F-DYN set:
  - every stage stops within max(1 s, 5%) of its cap, with setup units and setup and sweep wall reported;
  - the A4 rerun, 10 reps × 2 requests at 900 s.
  - These run as tracked, checkpointed background tasks.
