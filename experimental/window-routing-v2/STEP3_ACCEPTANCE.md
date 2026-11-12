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
