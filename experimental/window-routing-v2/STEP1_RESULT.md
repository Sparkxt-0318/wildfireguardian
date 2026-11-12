# Step 1 result: PASS on every criterion of STEP1_ACCEPTANCE.md and its amendments

The acceptance file and its amendments 26e12e4 and 2 (in 183d63f) were committed before the panel run.

**Kit.** `kit-v2-step1`, manifest `5afb464b…`. The overlay is 5 files:
- `decision/journey_decision.py` and `decision/journey_decision_v2_1.py`: the reason post-step;
- `phaseB/rda_worker_v1_1.py`: identity, plus the SEARCH_PROGRESS hook;
- `phaseB/road_core.py` and `phaseB/zsweep.py`: optional hook calls.

**Panel.** 12 Nov 2026, 16:34–17:04 UTC. 20 missions × 2 reps, frozen and v2 interleaved, plain mode, 81 s, this host,
no restart. Data: `results/step1/`.

| Criterion | Result |
|---|---|
| **G1** (identical status and arrival sets + FL2 rule) | **20/20 identical** |
| Status changes (expected 0) | **0** |
| Reason changes (expected: only Yeongdeok 0325T19 FX2, in deadline-stopped reps) | **only FX2**: rep 2 was deadline-stopped during search, and LATE_RESULT → **DEADLINE_STOP_DURING_SEARCH**. Rep 1 published on time, so its reason is SEARCH_TIMEOUT in both kits' logic. |
| **G2** | **28/28** v2 routes accepted by both checkers, in fresh processes |
| **G2b** (thomas/routing-next @ deeb7c2) | 40 folders: **38 PASS, 2 NOT_APPLICABLE_STATUS, 0 violations** |
| **G3** | 20/20 |
| **G5** | wall ratio **0.999**; memory within limits on 20/20 |
| kit_identity | 40/40 V2, 0/40 FROZEN |

**Tests:**
- `test_step1_reasons.py`: 10/10, including 3 replays of the recorded F-DYN folders, with statuses identical to the
  frozen v2_1;
- `test_step1_progress.py`: 2/2 on real jobs;
- `test_build_v2.py`: 10/10;
- parent tests: only the 2 provenance tests differ, exactly on the 5 overlay files.

**Harness defect found and fixed (it affects reasons only, never statuses).**
- `run_profile.run_one` imports `journey_decision_v2_1` **by name** from the kit's decision dir. In one `g1_panel`
  process, the first kit's module is cached, so the other kit's rows were decided by the first kit's module.
- The new `tools/redecide.py` recomputes every row's decision with **its own** kit's module, loaded by path, from the
  run folder records. `g1_compare.py` reads those rows, and `g1_panel.py` now runs the recomputation automatically.
- **Step 0 recomputed:** 0 status differences and 0 reason differences (`results/step0/ROWS_REDECIDED.jsonl.gz`).
  This was expected, because Step 0's decision code is identical to the frozen kit's.
- **Step 1 recomputed:** 0 status differences. The only reason difference is FX2 rep 2, which is the expected one.

## Mira R14: PASS WITH NOTES (ledger 94), and the follow-ups

Mira's own 1-rep panel with redecide:
- 0 status differences; G1 20/20; G3 20/20; G5 1.006; G2 14/14; G2b 0 violations.
- Rule b confirmed on a real deadline-stopped v2 folder of her own.

**N1 (fixed).** `run_one` also imports `wfg_controller` by name, so the first kit's controller ran the other kit's
jobs. It was harmless, because `runner/` is byte-identical between the kits. Even so, `g1_panel.py` now runs **each job
in its own interpreter** (`tools/run_one_job.py`), so the controller **and** decision modules are always the job's own
kit's. `redecide.py` is kept as a cross-check. A smoke run of 2 missions × 2 kits gives 0 status differences vs
recorded.

**N2 (fixed).** The progress hook's `/proc` read and file write are now exception-guarded (hook, final write and flush).
An error is counted in `STATE.progress_hook.errors` and never propagates into `road_core` or `zsweep` control flow.
Wording correction: the zsweep calls sit at a new per-16-second (sweep) and per-64-second (EA) modulus check placed
beside the existing wall-cap check, **not** at a pre-existing bookkeeping statement.

**N3.** The F-DYN replays need my run folders; they ran here (10/10).

**N4.** Rule b needs `worker_failure = DeadlineStop`. A frozen-kit worker's deadline stop keeps LATE_RESULT; that is
conservative, as Mira notes.

**Kit after fixes.** Manifest `kit-v2-step1b`. Tests: builder 10/10; parent ok (only the provenance tests, on the 5
overlay files); reasons 7/7 unit; progress 2/2. The N2 change alters no behaviour when no error occurs. It is
exercised again by the Step 2 panel, which reports G1 against the frozen kit.
