# Step 3 result: caps enforced promptly, Z on deterministic work budgets

> **Known limit, stated in every Step 3 report (Iris, adopted by the orchestrator 23:43 UTC; margin corrected per Mira,
> ledger 120).** Work-unit counts are identical on any machine. **Outcomes are deterministic only on hosts within about
> 1.65× of this reference host's speed.** Beyond that, the Z watchdog (16 s) can fire before Z's work budget does. The
> margin is the smallest across everything run here; per set:
> - **F-DYN set: 1.66×**, the smallest. Yeongdeok 0325T23 …166 kriged_mean, budget-capped Z 9.65 s; firms_early 8.82 s
>   (1.81×).
> - **1-hour panel: 1.84×.** Yeongdeok 0325T19 FD1, budget-capped Z 8.60–8.68 s, and FX2, 8.46–8.49 s. FD1 would lose
>   the LO stage that proves its refusal.
>
> Each run's host-speed figure (Z sweep units per second) is recorded below. STAGE_CAP_WATCHDOG results are reported
> apart from work-budget cuts. The fix is a separate later step (PLAN, "Step 3c").

Kit `kit-v2-step3e`, branch `claude/priya-kit-v2-step3`, cut from the Step 1 tip with no Step 2 code.
Budgets: setup 2^12 and sweep 2^28, both extrapolated (STEP3_ACCEPTANCE, "Recalibration after the B2 correction").
**Verified by Mira:** ledger 115, PASS WITH NOTES at 629ef31 (code, tests, unit determinism on a second machine, FL2, and the panel summary recomputed from the rows); ledger 117, G2/G2b records plus her own spot check of her two FL2 runs. The F-DYN every-stage-stop rows were produced on my host; Mira checked the committed summary against those rows (ledger 120) but did not re-run them.

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

## Host-speed figure per run (Iris: recorded with every run; `tools/host_speed.py`, `results/step3/HOST_SPEED_G1.json`)

The figure is Z sweep units per second of Z sweep wall, taken from each V2 run's own record.
- **It is mission-specific**, because the cost per lattice state differs between graphs: 9.5–56.8 M units/s across the
  panel (median 38.7 M). So two hosts are compared **per mission, never across missions**.
- On this reference host, the at-risk missions ran at:
  - yeongdeok_2025__20250325T190000Z_FD1: 55.9, 53.7 M units/s;
  - yeongdeok_2025__20250325T190000Z_FX2: 56.0, 56.8 M units/s;
- A host whose figure on these two missions is below about 1/1.84 of these values is outside the 1-hour panel's
  margin. The F-DYN set's margin is smaller: 1.66× (Yeongdeok …166).
- A fixed host-speed microbenchmark is part of the later Step 3c (Iris's preflight).

## Mira's verification (ledger 115, PASS WITH NOTES at 629ef31)

- She re-ran the tests on her own kits: test_step3_work 15/15, test_step3_thomas 6 (+10 subtests), and builder +
  reasons 17 passed / 3 skipped.
- **Second machine** (reworded per Mira, ledger 117):
  - 17/17 completing missions: setup and sweep units are equal to all 3 of my runs.
  - The 3 time-capped missions: setup units are equal (2,573 / 2,573 / 1,066), and FL2's full sweep, 215,231,775, equals
    the uncapped count. My calibration runs' sweep counts on those 3 were cut at the 6 s wall, so they are not
    comparable.
- G2/G2b additions (89b2117): PASS as records, plus Mira's own G2 and G2b of her two FL2 runs (ledger 117).
- FL2 end to end, 81 s, 2 runs per kit: FROZEN FEASIBLE@1922, V2 FULL_OPTIMUM_PROVEN@1922; no watchdog.
- The panel summary, recomputed from the committed rows, is identical. `kit_identity` was not checked, because the run
  folders are not committed.

**N2: slower-machine margin, stated.** Z no longer has a 6 s wall. Its only wall limit is the watchdog at
max(1.5 × 6, 6 + 10) = **16 s**, and a watchdog firing ends the job's search by fail-closed design. The budget-capped
Yeongdeok 0325T19 FD1/FX2 Z runs took about 8.5 s here.
- **On a machine about 1.84× slower than this host, those jobs would end in `STAGE_CAP_WATCHDOG`** (and the F-DYN
  Yeongdeok …166 jobs from about 1.66×; see the known-limit statement), and FD1 would never
  reach the LO stage that now proves its refusal.
- **Unit determinism holds on any machine; outcome determinism holds only inside that wall margin.**
- (Proposal, not adopted: derive Z's watchdog threshold from the remaining job time rather than the nominal 6 s, since Z
  is bounded by work. That would be a decision for the orchestrator and Iris, with its own test.)

**N3: recorded as a guard against later re-tuning.** Uncapped, on Mira's machine:
- FX2's Z would complete at 281,267,525 sweep units with CONDITIONAL_OPTIMUM@2512, 4.8% above the 2^28 budget, so FX2
  stays UNRESOLVED by that margin;
- FD1's Z would complete at 403,041,925 sweep units as PROVEN_INFEASIBLE.
- **Any later budget change must come from the stated calibration rule, never from these two numbers.**

## Every stage stops at its cap on the F-DYN set (acceptance D; `tools/stage_stop_check.py` → `results/step3/STAGE_STOP_FDYN.json`)

- **Setup:** the 12 F-DYN requests, 300 s, `--mode plain`, controller guard and request `rss_limit_mb` both 12,288 MiB
  (the A1 settings), kit-v2-step3e, 2026-11-12T23:37:49Z onward, alone on the host, no restart. Rows are in
  `results/step3/FDYN_STAGE_STOP_ROWS.jsonl`.
- **Result: 26 stages checked against their caps (12 Z, 6 LO, 2 LO2, 6 HI), 0 violations, 0 STAGE_CAP_WATCHDOG.**
  6 EA builds are reported with their elapsed time but **not** checked against a cap (`stage_stop_check.py` has no EA test).
- Tool note (Mira, ledger 120, not blocking): the Z sweep overshoot is allowed up to a fixed 120,000 units, not the job's own E + 1. It holds here (largest overshoot 72,619 < E + 1 = 111,925); a later edit should read E + 1 from the record.
- **Uiseong, 4 requests:**
  - Z is cut **in setup** with `WORK_BUDGET_SETUP` at 4,097 setup units, after 7.0–7.4 s (setup used to take 20–23 s).
  - LO stops 0.20–0.56 s past its 112–114 s cap, and HI 0.10–0.31 s past its 87–89 s cap, both
    `WALL_CLOCK_IN_BOUND_MODEL`. The tolerance is max(1 s, 5%), 4.4–5.7 s. LO used to overrun by 80–110 s with 1
    expansion.
- **Yeongdeok, 6 requests:**
  - Z completes on 4 (CONDITIONAL_OPTIMUM, setup 1,826 / 2,376 units in 4.8–5.8 s).
  - On …166, Z is cut by `WORK_BUDGET_SWEEP` at 268,508,075 units, within one sweep second of the budget. LO, LO2 and
    HI then finish well inside their caps.
- 2 requests are AT_ISSUE_FAILURE before any stage, as before.
- Host speed on these runs: Z sweep 19.3–66.7 M units/s (`results/step3/HOST_SPEED_FDYN.json`).

**Verdicts, reported only as a by-product (NOT a multi-hour result: PLAN forbids quoting multi-hour v2 numbers before
G6).** Compared with the earlier run under the same settings (`fdyn_b300_g12k_rss12k`, Step 1-era kit):
- the 4 Uiseong UNRESOLVED and 2 AT_ISSUE_FAILURE are unchanged;
- 4 Yeongdeok requests are now CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN (2 were FEASIBLE at the same arrivals 59 / 274; 2
  were UNRESOLVED), because Z now finishes instead of being cut by its 6 s wall after a 5–6 s setup;
- …166 stays UNRESOLVED.
- No G2 or G2b was run on these routes, so they are not acceptance evidence for anything except the stage-stop rule.

## Rebased onto the final Step 2 (kit-v2-step23, manifest `192f15cc…`; acceptance in STEP3_ACCEPTANCE "Rebase onto the final Step 2")

Merge `claude/priya-kit-v2-step3-on2` @ 34a7e2da (Step 3 149f448 into Step 2 bc90787): Thomas PASS WITH ONE NOTE (doc,
applied at 90012ac9); Mira ledger 127 PASS (own kit 192f15cc…, suite 81 + 3 skipped on her kit). All results below are
measured on one host (`vm`, x86_64, Intel Xeon @ 2.10 GHz, 4 CPUs), each run alone, no restart.

### Gates

| Gate | Result |
|---|---|
| Tests on kit-v2-step23 | **81 passed + 3 skipped**, parent runner ok |
| **G1** panel, 20 missions × 2 reps, 81 s, 02:06:49–02:35:28 UTC, 80 rows, redecide 0 differences (`results/step3rebase/`) | **20/20**, FL2 rule included |
| G3 | **20/20** |
| Memory-mapped statuses / check budgets | 0 OUTSIDE, 0 NOT_PROVEN; **28 checks, all `within_budget: true`**, largest check peak 487.6 MiB |
| **M1** (Step 2F, per V2 rep, harness family PSS) | **PASS 40/40**, largest **1,552.6 MiB** (Yeongdeok 0325T19 FX2, rep 2); 0 unmeasured samples (53,191 measured). Host as above |
| **G5 wall** (summed medians) | **0.892** (391.9 / 439.4 s), driven by FL2 (below) |
| **G2** | **28/28** published routes accepted by both frozen checkers |
| **G2b** (`xcheck/g2b.py` @ deeb7c2) | **40 runs, 0 violations** (38 PASS, 2 NOT_APPLICABLE_STATUS) |
| Kit identity | V2 40/40 |
| **F-DYN every-stage-stop** (Mira ledger 127; 12 requests, 300 s, guard and rss_limit 12,288 MiB, 02:35:33–03:05 UTC; `results/step3rebase/STAGE_STOP_FDYN.json`) | **22 stages checked (12 Z, 6 LO, 4 HI), 0 violations, 0 STAGE_CAP_WATCHDOG**; 6 EA builds reported, not checked |

- **FL2 (Yeongdeok 0325T23):** V2 is FULL_OPTIMUM_PROVEN@1922 on both reps in about 29 s. FROZEN is FEASIBLE@1922
  and UNRESOLVED, at 79–81 s. Step 3's own panel showed the same outcome under the budgets.
- **Step 1 reason changes, not verdict changes:**
  - FX2: LATE_RESULT → SEARCH_TIMEOUT;
  - FL2: LATE_RESULT no longer appears.

### F-DYN: differences from the Step 3 run, each tied to its stage (measured)
- **Stage count 22, not 26.** On both Yeongdeok …166 requests, LO2 and HI did not run, because the LO candidate was
  certified.
- **Verdict change on Yeongdeok …166 (both variants): UNRESOLVED → CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN, arrival 3953.**
  - Step 3 run: the whole-road check of the LO, LO2 and HI candidates returned UNRESOLVED / **RSS_LIMIT** each time,
    all at arrival 3953. That check runs in-process, so it is charged the 4.4 GiB parent.
  - Rebased kit: the check runs in a forked child under Step 2. It is CERTIFIED_ADMISSIBLE, with its own cgroup peak
    494–495 MiB, within_budget true.
  - This is Step 2's purpose showing on F-DYN. The same-host A/B below confirms it.
- **Uiseong family RSS-sum peak: 9.2–9.8 GiB → 2.3 GiB** (the 2 AT_ISSUE requests: 9.2–9.8 GiB → 0.9 GiB). Statuses are
  unchanged: 4 UNRESOLVED and 2 AT_ISSUE_FAILURE.
  - Hypothesis, untested: amendment E's chunked distance removes the transient there.
- **LO on …166 took longer: 70.4 / 82.7 s against 52.8 / 62.6 s, still 37–51 s inside its cap.**
  - The work is identical: 1,669 expansions, 1,404 boxes, 9 coefficient batches.
  - The whole difference is in the bound-model coefficient time (55.2 / 66.5 s against 38.4 / 48.1 s).
  - **Post-hoc diagnostic** (not in the acceptance; `results/step3rebase/ab166/`): Step 3's kit (kit-v2-step3e) and the
    rebased kit were run back-to-back on this host on kriged_mean …166, 03:18–03:27 UTC:

    | kit | Z | LO | coef_s | outcome |
    |---|---|---|---|---|
    | kit-v2-step3e | 10.5 s | 83.1 s | 67.1 s | TIMEOUT, LO check RSS_LIMIT |
    | kit-v2-step23 | 10.6 s | 85.4 s | 69.1 s | FULL_OPTIMUM_PROVEN, check certified |

  - So the slower LO and Z come from this host (the container was replaced at 00:36Z), not from the rebase.
  - The verdict change comes from Step 2: same host, same request, and only the rebased kit certifies.
  - The Z sweep units/s proxy differs by only 3% (median 28.6 M against 29.4 M), so the proxy does not capture this
    host's slowdown. That is a finding about the proxy.

### Known limit, measured again on this host
- Z budget-capped times on the rebased runs:
  - 10.3 s (…166 kriged_mean), 9.91 s (1-hour FX2 r1), 9.63 s (FD1 r1);
  - previously 9.65 s and 8.5 s on the reference host.
- **The watchdog margin on this host is 1.55× (F-DYN …166) and 1.61× (1-hour FX2).**
- The A/B shows this is the host: Step 3's kit takes 10.5 s here.
- The known-limit statement is relative to the reference host (Z 9.65 s on …166). This host is about 1.09× slower on
  that stage, so it is inside the 1.65× bound, with 1.51–1.55× left.
- Step 3c (Iris's host-speed design) remains the planned fix.

### Ideas and gaps
- The F-DYN set and the A/B are single runs per request.
- The host-speed proxy (pure-Python Z sweep) did not see a host change that slowed numpy coefficient work by about
  40% and Z by about 9%. Step 3c should not rely on that proxy alone.

## Pending

- The A4 rerun (10 reps × 2 requests at 900 s), now on kit-v2-step23, the settled base, after Mira's verdict on the
  results above. It runs as a tracked, checkpointed background task.
