# Step 3: caps enforced promptly, Z on a deterministic work budget. Design and acceptance, written before any code

Branch `claude/priya-kit-v2-step3`, cut from the verified Step 1 tip `363c86d`. It does **not** contain Step 2's
forked check isolation (orchestrator 19:04 UTC), so either Step 2 owner decision can be applied underneath later.
Mira verifies, Iris assesses (calibration rule), and Thomas reviews the bound-model interruption point (B3) and the
watchdog's effect on caches (B5).

## A. Where the overruns are (measured before design)

1. **Z: static setup, before its first cap check.**
   - Recorded F-DYN runs (`fdyn_b300_g12k*`):
     - Uiseong Z ran 20.0–22.8 s against a 6 s cap, with `static_setup_s` 20.0–22.8 s and 0 sweep seconds;
     - Yeongdeok setup takes 5.3–6.6 s of the 6 s cap, leaving 0–336 sweep seconds.
   - The setup builds the contact masks (Uiseong: 11,000 contact edges, 5,824 contact nodes). Its first wall check is
     at sweep second 0. The Yeongdeok setup ≈ cap is exactly the race that flips A4's outcome class.
2. **LO: inside one expansion, in the bound model.**
   - Recorded `fdyn_b450_gate12k`: Uiseong LO ran 245.6, 273.2 and 272.4 s against 164–167 s caps, with **1
     expansion**.
   - Stack samples on a re-run (`tools/stack_sampler_worker.py`, 0.5 s sampling; Uiseong firms_early …323, 450 s,
     kit-v2-step1b; `results/step3/UI323_STACK_SAMPLES.json`): LO ran 216.7 s.
     - From about 103 s to the deadline the samples sit in `road_bounds` `ExposureView.edge` → `edge_store` →
       `_ensure_edges` → `_batch` → `coefficients` → `adaptive_checker.coefficients` → `ivkernel.rectangle_bounds`.
     - That is the analytic radiation coefficients of edge boxes against 6,443 sources, with no cap check between
       batches.
   - road_core checks the wall only between heap pops and at a few other points.
3. **EA:** checks its deadline every 64 backward seconds (no overrun seen; coarse). **Z's sweep:** checks every 16 sweep
   seconds.

## B. Design

1. **Work units: `phaseB/v2_work.py`, a deterministic counter.**
   - `Budget(units_cap, deadline)`: `tick(n)` adds `n` units. It raises `StageCap('WORK_BUDGET')` once units exceed
     the cap, and `StageCap('WALL_DEADLINE')` once `perf_counter() ≥ deadline`. Both are checked on every tick.
   - Units are counts of algorithmic items, never time, so they are identical on any machine for the same inputs.
2. **Z on a work budget** (PLAN: replaces Z's 6 s wall cap).
   - Unit definitions (tests check them):
     - one unit per (candidate edge, occupancy, fire interval) item in the contact-mask setup;
     - one unit per (waitable fire-node state) row;
     - **(E + 1) units per sweep second**, i.e. the lattice states advanced.
   - Z stops at its work budget **inside setup or sweep**, with reason `WORK_BUDGET`. That is the same result class as
     today's `TIMEOUT` (`INCOMPLETE_CAP`), with no incumbent unless one was already found.
   - The overall complete deadline stays wall time and is also checked on every tick.
   - `Z_max_s` / `Z_reserve_s` remain only as watchdog inputs (B5).
3. **Bound-model interruption point (Thomas reviews).**
   - `road_bounds.RoadBoundModel` gets an optional `stage_budget` (None = parent behaviour). `_batch` / `coefficients`
     tick it **between sub-batches**, one unit per box.
   - When it raises, no partial result is stored:
     - each `_coef` entry is written only after its row is complete;
     - `_edge` / `_node` entries are written only after the whole edge or node is done.
     So the caches hold only complete, correct values.
   - road_core catches `StageCap` at its expansion call sites and returns `TIMEOUT`, `WALL_CLOCK_IN_BOUND_MODEL` or
     `WORK_BUDGET`, i.e. the existing incomplete-cap result.
   - **Test:** after an interrupted batch, every cache entry is byte-identical to the uninterrupted model's entry for
     the same key.
4. **Finer wall checks.** LO, LO2 and HI keep their wall caps, which are fractions of the remaining time (PLAN: only Z
   becomes work-based). They are now checked on every bound-model tick and every expansion. The EA build is checked
   every backward second, and the Z sweep every sweep second, instead of every 64 and 16.
5. **Watchdog (PLAN): `STAGE_CAP_WATCHDOG`.**
   - Each stage call runs under `signal.setitimer(ITIMER_REAL, max(1.5 × cap, cap + 10 s))`. For Z, the cap is the
     declared 6 s. The SIGALRM handler raises `StageCapWatchdog` in the main thread.
   - It is caught at the worker's stage call site. The stage is recorded as `TIMEOUT` / `STAGE_CAP_WATCHDOG`, never
     silently continued.
   - An asynchronous exception can land mid-update, so **after a watchdog fires, no later stage uses the bound model
     or the EA bound** (fail closed). Only candidates already checked remain.
   - In the acceptance runs, a watchdog firing is a finding to report: it means a cap check is missing somewhere.
6. **Determinism across machines.**
   - The same job is run normally and under contention: pinned to one core with a competing busy loop, i.e. a slower
     machine.
   - Z's unit count, its stop point and the Z outcome must be identical.
   - Mira is asked to repeat the 1-hour calibration panel's Z unit counts in her own container, i.e. a second machine.

## C. Calibration (Iris's rule, fixed before any run; 1-hour panel only)

The plan's rule says "the budget is the median work Z performs in 6 s over the 20 missions on this host, rounded up to
a power of two". **Interpretation, for Iris to confirm before the calibration run:**
- On many 1-hour missions Z completes in under 6 s, so "work performed in 6 s" is undefined for them.
- Proposed: for each mission, run Z with counting and **no** work cap, record units at **6.0 s** of Z wall time (or
  at completion, if earlier), and take the median over the 20 missions **of the 6.0 s values only for missions still
  running at 6 s**.
- If fewer than 5 missions run past 6 s, use instead the median over all 20 of
  `units / Z wall seconds × 6`, i.e. rate × 6 s.
- Round up to a power of two, then commit the budget and its measurement before any F-DYN run.

## D. Acceptance (all must hold)

- **Tests, written first** (`tests/test_step3_work.py`):
  - unit definitions;
  - the Z budget stop inside setup and inside the sweep;
  - cache identity after a bound-model interruption (B3);
  - the watchdog on a synthetic non-returning stage: it is killed within threshold + 1 s, reported as
    `STAGE_CAP_WATCHDOG`, and later stages do not use the bound model;
  - determinism of the unit count under contention.
- **G1–G3 on the 1-hour panel vs the frozen kit** (as PLAN; FL2 rule), plus G5. Z's outcome on the panel may differ
  from frozen only where the frozen Z was wall-capped; any such change is listed per mission.
- **A4 rerun:** 10 reps × 2 requests (…207, …168), 900 s, same settings as A4. **Each request gives one outcome class
  in 10/10.**
- **On the F-DYN set, every stage stops within max(1 s, 5% of its cap) of its cap.** Z's cap is in units and must stop
  exactly at the budget. Z's wall is reported.
- **No `STAGE_CAP_WATCHDOG`** in any acceptance run.
- Step 0/1 tests and parent tests pass. Overlay additions are declared and pinned as in Step 2.

## E. Not in this step

The Step 2 memory changes are kept separate on purpose. The F-DYN runs here use the A4 settings (controller and
request gates as recorded for A4), so they do not depend on the Step 2 decision. If the owner adopts F4 + F3, Step 3 is
rebased onto it and G1 is re-run.

## Amendments before any calibration result is read (19:3x UTC; the calibration run started 19:2x and has not been read)

### Iris (19:16 UTC): calibration interpretation accepted, plus a safeguard and measurement details

- **Three runs per mission.** For each mission, take the per-mission **median** of the three 6.0 s unit counts (or
  completion counts) and report the spread.
  - **Pre-stated spread factor: 1.25.** If a mission's three counts differ by more than ×1.25 (max/min), the note says so.
  - The 1-rep run already started counts as run 1. Two more V2-only reps follow.
- **"Units at 6.0 s"** is the count at the first clock check at or after 6.0 s of Z wall. The clock is read once per
  unit tick in setup (one perf_counter per contact item or wait row) and once per sweep second. The cost of that reading
  is measured: Z wall with counting vs the frozen Z wall, per mission, on the same panel.
- **Fallback extrapolation:** if fewer than 5 missions run past 6 s, the budget is the median over all 20 of
  units ÷ Z wall × 6. A budget obtained this way is **labelled "extrapolated"**.
- **Safeguard.** After calibration, every 1-hour mission whose Z completed within 6 s (uncapped total units) must also
  complete within the budget. If any would be cut, the budget is raised to the next power of two that cuts none, and
  both numbers and the reason are recorded. G6 later confirms it on the full set. The same check confirms that **no
  1-hour mission's setup alone exceeds the budget.**
- **Stated behaviour change at multi-hour:** a Uiseong F-DYN Z run that today spends 20–23 s in setup is cut **during
  setup**, deterministically. Z then returns `TIMEOUT` / `WORK_BUDGET` / `INCOMPLETE_CAP`, with no route, no incumbent,
  no lower bound and no refusal. Later stages run as today, and EA / LO do not depend on Z's result except through its
  incumbent and bound.
- Wall time and peak memory are reported beside unit counts on every run.

### Thomas (19:16 UTC): B3 / B5 accepted with conditions, all adopted

B3:
1. `StageCap` subclasses **BaseException**. The bound-model call path (road_bounds, adaptive_checker, ivkernel,
   hybrid_radiation, radiation_bounds) is grepped for bare `except:`, `except BaseException` and `except Exception`,
   and the findings are listed in the result.
2. **Whole-state completeness test.**
   - Take an attribute inventory of RoadBoundModel and of every object it reaches that holds a cache.
   - Interrupt at every k-th tick, k ∈ {1, 2, 3, 5, last}, then resume with the same queries.
   - Every returned value must be byte-identical to an uninterrupted model's. Counters may differ; no cache may hold a
     partial entry (every entry equals the fresh model's entry for that key).
3. **Downstream test:** an interrupted LO solve, then LO2-mode and HI-mode solves on the same model, compared with the
   same solves on a fresh model (status, arrival, legs, per-member values).
4. **A capped stage is never a refusal or a bound.** A job-level test forces a StageCap in LO and asserts: no refusal
   certificate, nothing from LO in `lower_bounds`, and any returned incumbent goes only to the whole-road check.

B5:
1. The watchdog exception is renamed **`WatchdogFired`** (BaseException, distinct from StageCap). It is caught only
   by the stage driver `_v2_run`.
2. **Alarm scope.** The alarm is armed only around search-stage calls (Z, EA, LO, LO2, HI solve or build). Whole-road
   checks run in `consider()` after the stage returns, with the alarm disarmed.
   - **Test:** an instrumented launcher records `signal.getitimer(ITIMER_REAL)` at every `HybridChecker.check` entry,
     and every reading must be 0.
3. The interrupted stage's own outputs (partial incumbent, lower bound, refusal flag) are discarded. Only candidates
   whose whole-road check completed before the firing survive.
4. The alarm is cancelled in `finally`. A **second arming while one is active raises** (never two alarms). The handler
   only raises (no IO). The watchdog is **best-effort**: a long C call delays delivery until it returns.
5. Any firing is a finding, reported per mission with the stage, elapsed time and what was discarded.

## Calibration result (20:0x UTC; `results/step3/Z_CALIBRATION.json`, kit-v2-step3a, 3 runs per mission)

- **Budget: 2^28 = 268,435,456 units, labelled EXTRAPOLATED.**
  - Only 3 of 20 missions were still running at 6 s (Yeongdeok 0325T19 FD1 and FX2, and 0325T23 FL2), fewer than 5,
    so the pre-stated fallback applies: the median over all 20 of units ÷ Z wall × 6 = 148,100,980, rounded up.
- **Spread:** max/min over the three runs is 1.000 on 17 missions; 1.082, 1.036 and 1.110 on the three time-capped ones.
  None exceeds 1.25.
- **Safeguard:**
  - the largest mission completing within 6 s needs 93,965,879 units (Uiseong 0324T09 FL2), which is within budget;
  - the largest setup alone is 8,085 units, also within budget;
  - **not raised.**
- **Consequence, stated before the G1 panel:**
  - The three time-capped missions reached 127.0 M, 126.9 M and 213.7 M units at 6 s, so under the budget their Z runs
    longer (about 12.7, 12.7 and 7.5 s at this host's rate) and may return a different Z outcome than today.
  - G1 compares final status and arrival, with the FL2 rule for 0325T23 FL2; any Z-stage change is listed per mission.
- Run 1 was interleaved with the frozen kit (`CAL_RUN1_PANEL_ROWS.jsonl.gz`); runs 2–3 were V2 only.

## Correction to §B2 (Iris 20:02 UTC, option (b)), written before code and before recalibrating

**Why.** Measured with instrumentation only, on kit-v2-step3c: Uiseong F-DYN Z setup is 35,165 units in 18.1 s, and
Yeongdeok F-DYN is 5,537 units in 5.0 s. Both were under load. So setup is never cut by a 2^28 budget, and the note
"Uiseong Z is cut in setup" was **false** and is withdrawn. cProfile: 93% of the Uiseong setup is in 11,011 calls to
`core.edge_occupancies` (exact Fractions, about 1.6 ms each), one per contact-candidate edge, which the old setup unit
did not count. One setup unit cost about 10^4 sweep units.

**Correction.**
1. **Two budgets.** Z has a **setup budget** and a **sweep budget**, each calibrated to a 6 s equivalent; there is no
   split of one 6 s.
   - **Setup unit:** 1 per contact-candidate edge examined, ticked **before** its `edge_occupancies` call, plus 1 per
     wait row. The old per-interval tick is removed.
     - Mira N4, definitional: a "wait row" unit is ticked on **every** `nblock` call, including cache hits for a node
       and length already computed. The count is deterministic either way.
   - **Sweep unit:** unchanged, (E + 1) per sweep second.
2. **Reason codes when Z is cut:**
   - `WORK_BUDGET_SETUP`: cut during setup. Z returns `TIMEOUT` / `INCOMPLETE_CAP` with no route, no incumbent, no lower
     bound and no refusal.
   - `WORK_BUDGET_SWEEP`: cut during the sweep. It returns the same, because Z returns as soon as a route is found, so a
     cut sweep has none.
3. **Calibration (same rule and safeguard, per budget), on a quiet host, 3 runs per mission, with the spread reported:**
   - The calibration kit has both caps None and keeps the parent's 6 s Z wall cap. It records setup units, setup wall
     (Z start to first sweep tick), sweep units and sweep wall (Z wall − setup wall).
   - **Setup budget** = median over the 20 missions of (setup units ÷ setup wall × 6), rounded up to a power of two.
     It is **labelled extrapolated** unless at least 5 missions' setup itself runs ≥ 6 s.
   - **Sweep budget** = median over the 20 missions of (sweep units ÷ sweep wall × 6), rounded up to a power of two.
     It is **labelled extrapolated** unless at least 5 missions' sweep itself runs ≥ 6 s; under the 6 s Z cap none can.
   - **Safeguard:** every 1-hour mission whose setup completes must fit within the setup budget. Every mission whose Z
     completes within 6 s must have sweep units within the sweep budget. If not, the budget goes to the next power of
     two, with both numbers recorded.
4. **Stated consequence:** Z's total work can reach about twice the old 6 s cap, more after rounding. This is the rule's
   consequence, not tuning.
5. **Reporting:**
   - Every multi-hour run reports setup units, setup wall and sweep wall separately, so that a multi-hour setup budget
     costing much more than 6 s of wall is visible.
   - The panel report states **two** ratios: each budget ÷ its median 6 s equivalent.
   - The 3 time-capped missions are listed with their units at their own 6 s, the budgets, and Z's outcome under the
     old cap and the new budgets. Both outcomes come from one run: Z's units are deterministic, so if a run's units are
     ≤ that mission's 6 s count the outcome is the same, otherwise the old cap would have cut it.
6. **Not in Step 3** (Iris): caching `edge_occupancies` by edge and fire field is a candidate next experiment, passed to
   the orchestrator.

The 2^28 budget committed at 7ebd84d is **superseded** and is not used for any G1 or F-DYN run.

## Recalibration after the B2 correction (quiet host, 2026-11-12T20:11:38Z onward; kit-v2-step3d; 3 runs × 20 missions; `results/step3/Z_CALIBRATION_V2.json`)

| Budget | Raw (median rate × 6 s) | Budget | Ratio | Basis | Safeguard |
|---|---|---|---|---|---|
| Setup | 2,153.6 units | **2^12 = 4,096** | 1.90 | EXTRAPOLATED (0 missions' setup ran ≥ 6 s; 16 missions have setup units > 0) | largest 1-hour setup 2,573 (Yeongdeok 0325T19) fits; not raised |
| Sweep | 221,648,345 units | **2^28 = 268,435,456** | 1.21 | EXTRAPOLATED (0 sweeps ran ≥ 6 s under the 6 s Z cap) | largest completing sweep 93,965,088 (Uiseong 0324T09 FL2) fits; not raised |

- **Unit-count spread over the three runs:** max/min ≤ 1.25 on every mission for both units. Units are deterministic
  except on the three time-capped missions.
- **Wall-time spread (reported, not part of the rule):** setup wall up to 1.45 (Hongseong 0230 FD1, on a 0.025 s setup),
  and sweep wall up to 1.98 (Miryang 0602 FW1, 0.19 s) and 1.72 (Yeongdeok 0325T23 FL2).
- **Setup cost per unit on 1-hour edges:** about 1.1 ms (Uiseong 0325T17 FW1: 2,090 units in 2.39 s) and about 1.5 ms
  (Yeongdeok 0325T19: 2,573 units in 3.87 s). So 4,096 setup units is about 4.5–6.2 s at 1-hour rates on this host.
- **Expected at multi-hour (from the earlier instrumentation, not yet re-measured):** Uiseong F-DYN has about 11,011
  candidate edges, more than 4,096, so its setup is cut with `WORK_BUDGET_SETUP`. The F-DYN runs report setup units and
  setup and sweep wall separately.
- **The 3 time-capped missions** (Yeongdeok 0325T19 FD1, FX2 and 0325T23 FL2):
  - at their own 6 s they had setup 2,573 / 2,573 / 1,066 units and sweep 129.4 M / 127.0 M / 204.7 M units;
  - under the budgets their setup completes, and their sweep gets up to 268.4 M units, i.e. 2.07×, 2.11× and 1.31× the
    sweep units they reached at the old cap;
  - outcomes at the old cap and under the budgets are both reported from the G1 run.

## Rebase onto the final Step 2 (written before any run on the rebased kit; 2026-11-13 ~02:0x UTC)

Order: orchestrator, Step 2F accepted by Mira (ledger 125). Branch `claude/priya-kit-v2-step3-on2`: a merge of the final
Step 3 (`claude/priya-kit-v2-step3` @ 149f448) into the final Step 2 (`claude/priya-kit-v2` @ bc90787). A merge is
used instead of replaying 19 commits; the resulting tree is what a rebase would produce. Neither existing branch is
rewritten.

### How the merge was resolved (mechanical, checked)
- Files both steps changed: the worker, road_core and g1_compare, plus road_bounds, test_build_v2 and SOURCE_SHA256
  (each in its own bullet below).
  - For the worker, road_core and g1_compare, the merged file minus Step 2's file equals Step 3's own change, line for
    line (checked by comparing sorted diff lines).
  - Every other file is exactly one side's version: zsweep and v2_work are Step 3's, journey_decision_v2_1 is Step
    2's.
  - Thomas's review (34a7e2da) corrected an earlier version of this bullet, which listed zsweep and
    journey_decision_v2_1 as changed by both steps.
- `road_bounds.py` (both sides added it to the overlay):
  - Step 2 amendment E's chunked `edge_source_dist` and `dist_sha256` are kept;
  - Step 3's `stage_budget` and its tick before each coefficient chunk are kept;
  - merged minus Step 2 is exactly those Step 3 lines;
  - the only Step 3 lines dropped are its six unchunked distance lines. Step 2 amendment E replaced them with a
    chunked computation whose OUTPUT is byte-identical (tested, `test_step2_dist`); the source is different.
- `test_build_v2.py`: STEP2_WORKER_LINES, STEP2_WRAPPER and STEP3_WORKER_LINES are kept, all exact. The worker-diff
  test now requires:
  - removed lines = the global line + Step 2's 3 check-call lines + Step 3's 6 stage calls + 3 extended lines;
  - added lines = exactly the Step 2 and Step 3 declared lines;
  - no line carries both markers.
- `SOURCE_SHA256.json` is recomputed from the merged overlay (11 files).

### Acceptance for the rebased kit (all must hold; same rules as before, nothing loosened)
- **Tests:** every suite of both steps on the rebased kit, with the parent runner ok. Reported as a count:
  passed + skipped.
- **G1 panel** (FROZEN vs rebased V2, 20 missions × 2 reps, 81 s, alone on the host, harness-tracked, checkpointed,
  restarts logged):
  - **G1** 20/20 under the G1 rule including FL2. The FL2 outcomes at the old cap and under the budgets are both
    reported.
  - **G3** 20/20.
  - Memory-mapped statuses 0 OUTSIDE and 0 NOT_PROVEN. Every published check `within_budget: true`.
  - **M1** (Step 2F, per rep, harness family PSS, host stated) ≤ 3,072 MiB. Not evaluable is never a pass.
  - **G5 wall** ≤ 1.10.
  - **G2** on every published route; **G2b** 0 violations.
  - Kit identity on every V2 row.
- **F-DYN every-stage-stop, rerun on the rebased kit (Mira ledger 127, before the cut).**
  - Reason: the combination is new on F-DYN. Step 2's solver current-RSS gate (road_core) and its forked checks now
    run inside Step 3's work-budgeted stages, and Step 3 lets Z run past the old 6 s. Step 3's 26-stage result came
    from a kit without Step 2.
  - Rule: unchanged from §D and the Step 3 result.
    - The 12 F-DYN requests, 300 s, `--mode plain`, controller guard and request `rss_limit_mb` both 12,288 MiB;
      kit-v2-step23; alone on the host, after the G1 panel; tracked, with restarts logged.
    - `tools/stage_stop_check.py`. **Every Z, LO, LO2 and HI stage checked against its cap, 0 violations,
      0 STAGE_CAP_WATCHDOG.** EA builds are reported, not checked.
    - Statuses are reported beside the Step 3 run's. Any difference is reported as a finding with the stage that
      produced it; it is not explained away.
  - The stage count is expected to be 26 if the same stages run. A different count is reported, not a failure in
    itself; every stage that runs must stop.
- **Not rerun:** Step 2F's M3(d) (Mira ledger 127: the controller is unchanged by Step 3, and M1 per rep on the G1 panel
  covers Step 3's memory at one hour).
- **Then A4:** 10 reps × 2 requests × 900 s on this kit, tracked and checkpointed, with a timing claim only from runs
  without a restart.
