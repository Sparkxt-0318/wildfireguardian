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
