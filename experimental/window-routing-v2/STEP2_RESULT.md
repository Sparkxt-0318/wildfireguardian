# Step 2 result: memory accounting

**Amendment F result (first section below):**
- Every pre-stated criterion passes.
- M2-model is not evaluable on 6 refusal-type missions, where no check ran. They are listed and not counted as passes.
- This result is for Mira's verification.

The original Step 2 result follows it unchanged. That result was a G5 memory FAIL as written, which led to the owner
decision and to amendment F.

## Amendment F result (STEP2_ACCEPTANCE amendment F, R1-R7, ledgers 119/122/124)

### Run
- **Kit:** `kit-v2-step2f`, manifest `229f4015…`. Mira built the same manifest independently (ledger 122).
- **Tools:** at the commit that adds this section. The harness sampler is `tools/harness_mem.py`, with the N2 rules
  (ledger 124 PASS).
- **Panel `v2_step2f_g1`:**
  - 20 missions × 2 reps × 3 arms (FROZEN, V2, V2_NOISO), interleaved, 81 s, `--mode plain`, alone on the host;
  - **00:36:57–01:22:42 UTC, no restart during the run**;
  - 120 rows; redecide found 0 status differences against the recorded statuses;
  - rows are in `results/step2f/panel/`; the comparisons are `results/step2f/STEP2F_COMPARE.json` and
    `G1_COMPARE.json`.
- **Earlier attempts,** both kept unread and never used for any verdict:
  - `v2_step2f_g1_ABANDONED_unread_N2`: the old sampler, 00:17–00:27 UTC. Stopped because of Mira 122 N2.
  - `v2_step2f_g1_RESTART1_partial_unread`: launched 00:35:54Z. A container restart killed it during its first job,
    with zero rows written (`results/step2f/panel/RESTARTS.log`). The panel above restarted from zero.
- **Harness sampler over all 120 jobs:**
  - **0 unmeasured samples** (185,908 measured), so M1 and M2 are evaluable everywhere;
  - vanished pids, skipped and counted: FROZEN 404, V2 516, V2_NOISO 475.

### Criteria

| Criterion (fixed before the panel) | Result |
|---|---|
| **M1** every V2 rep's harness family-PSS peak ≤ 3,072 MiB | **PASS, 40/40 reps.** Largest **1,823 MiB** (Yeongdeok 0325T23 FL2, rep 1). M1 not evaluable: none |
| **M2** per-mission table | below |
| M2 post-hoc tripwire: V2 − V2_NOISO > 50% AND > 300 MiB. Label: *post-hoc tripwire (set after 2 diagnostics on panel missions); passing it is not evidence of an acceptable cost* | Not tripped on any mission. Largest increase +275 MiB (FL2, +18%) |
| **M2-model** (an accounting-consistency bound, not a cost bound): median V2 − median V2_NOISO ≤ largest check cgroup peak + 64 MiB | **PASS on all 14 evaluable missions.** **Not evaluable on 6**, each for the reason "V2 rep 1: no check ran": Hongseong 0402T07 FN1 and FX1, Miryang 0601T08 FD1 and FX1, Yeongdeok 0325T19 FD1 and FX2. These are not passes. On them V2 − V2_NOISO is −1 to +1 MiB |
| **M3(a)/(b)** guard tests, **N3** controller-level guard tests, **R3** sampling-error tests | Pass (`test_step2f_guard`, 12/12) |
| **M3(d)** with R5, on F-DYN Yeongdeok kriged_mean …415158166 (300 s, guard 12,288 MiB): controller PSS peak within [0.95, 1.0] × harness PSS max, and below the harness RSS-sum peak | **PASS.** Controller **5,072.2 MiB**, harness **5,075.3 MiB**, ratio **0.9994**. Harness RSS-sum peak 9,334 MiB (previously 5,083 vs 9,352). Guard not triggered. Harness samples 11,744/11,744 measured; controller 2,070 PSS samples, 0 fallbacks. Single run, wall 216 s, FULL_OPTIMUM_PROVEN. Files: `results/step2f/M3D_FDYN_YD166*.json` |
| **M4** V2_NOISO pre-memory-map set = FROZEN's (G1 rule including FL2) | **PASS, 20/20** |
| **R6** V2 pre-memory-map set = V2_NOISO's | **PASS, 20/20.** 19 missions pass by exact set equality. **FL2 (Yeongdeok 0325T23) is judged under the G1 rule (N1): both arms fall within {UNRESOLVED, FEASIBLE@1922, OPTIMUM@1922}. This shows only that; it does not show that isolation leaves FL2's verdict unchanged.** Reported beside it, `R6_exact_sets_equal` for FL2: **True**. Both v2 arms are {FEASIBLE@1922, UNRESOLVED}; FROZEN is {FEASIBLE@1922} |
| **G1** V2 = FROZEN (pre-memory-map status and arrival) | **PASS, 20/20**, FL2 rule included. Memory-mapped statuses on V2: 0 OUTSIDE, 0 NOT_PROVEN. 27 published checks, all `within_budget: true`; largest check peak 494.6 MiB. Step 1 reason changes, not verdict changes: FX2 LATE_RESULT → DEADLINE_STOP_DURING_SEARCH; FL2 adds DEADLINE_STOP_DURING_SEARCH on its UNRESOLVED rep |
| G3 | **PASS, 20/20** |
| **G5 wall** V2 ≤ 1.10 × FROZEN (summed medians, sampler included) | **PASS, 1.005** (443.8 / 441.4 s) |
| **R7** isolation wall cost, V2 / V2_NOISO | **1.002** (443.8 / 443.1 s) |
| R7 harness sampler CPU per job, median | FROZEN 3.97 s, V2 4.24 s, V2_NOISO 3.72 s |
| G2: each published V2 route re-checked by both frozen checkers, in fresh interpreters | **PASS, 27/27** (`results/step2f/G2.jsonl`) |
| G2b (Thomas's `xcheck/g2b.py` @ deeb7c2) | **PASS: 40 runs, 0 violations** (37 PASS, 3 NOT_APPLICABLE_STATUS: UNRESOLVED runs, which make no claim) (`results/step2f/G2B.json`) |
| Superseded measure, reported and not a criterion: `g1_compare` "G5 memory" (controller RSS sum, ≤ +10%) | False on the missions that run a check. Amendment F replaced it with M1 and M2 on PSS |

### M2 per-mission table (harness family PSS peak, median over 2 reps, MiB)

- "(seen)" marks a mission seen before the tripwire was set (R1).
- "V2 max" is the larger of the 2 V2 reps, since M1 is per rep.

| Mission | FROZEN | V2_NOISO | V2 | V2 max | V2 − NOISO | V2 / FROZEN | largest check peak | M2-model |
|---|---|---|---|---|---|---|---|---|
| hongseong_2023/20230402T070000Z_FN1 | 42 | 42 | 43 | 45 | +1 | 1.03 | — (no check) | not evaluable |
| hongseong_2023/20230402T070000Z_FX1 | 42 | 43 | 42 | 42 | -1 | 1.01 | — (no check) | not evaluable |
| hongseong_2023/20230402T140000Z_FW2 | 78 | 77 | 90 | 91 | +14 | 1.15 | 47 | ok |
| hongseong_2023/20230402T230000Z_FD1 | 62 | 63 | 75 | 75 | +12 | 1.20 | 33 | ok |
| miryang_2022/20220531T100000Z_FN1 | 82 | 82 | 95 | 96 | +13 | 1.16 | 48 | ok |
| miryang_2022/20220601T020000Z_FW1 | 66 | 67 | 79 | 80 | +13 | 1.20 | 32 | ok |
| miryang_2022/20220601T080000Z_FD1 | 48 | 49 | 50 | 50 | +1 | 1.03 | — (no check) | not evaluable |
| miryang_2022/20220601T080000Z_FX1 | 49 | 49 | 49 | 49 | -0 | 1.01 | — (no check) | not evaluable |
| uiseong_andong_2025/20250323T010000Z_FD1 | 356 | 356 | 497 | 498 | +141 | 1.40 | 246 | ok |
| uiseong_andong_2025/20250323T010000Z_FX2 | 361 | 361 | 498 | 503 | +137 | 1.38 | 251 | ok |
| uiseong_andong_2025/20250324T090000Z_FL2 | 376 | 377 | 520 | 520 | +143 | 1.38 | 263 | ok |
| uiseong_andong_2025/20250325T170000Z_FW1 | 855 | 465 | 465 | 466 | +0 | 0.54 | 196 | ok |
| uljin_2022/20220304T030000Z_FD1 | 201 | 207 | 248 | 251 | +42 | 1.23 | 129 | ok |
| uljin_2022/20220304T030000Z_FX1 | 275 | 272 | 331 | 331 | +59 | 1.20 | 200 | ok |
| uljin_2022/20220304T060000Z_FL1 | 206 | 211 | 260 | 260 | +48 | 1.26 | 135 | ok |
| uljin_2022/20220304T120000Z_FW2 (seen) | 169 | 167 | 216 | 219 | +49 | 1.28 | 96 | ok |
| yeongdeok_2025/20250325T190000Z_FD1 | 1463 | 1464 | 1465 | 1466 | +1 | 1.00 | — (no check) | not evaluable |
| yeongdeok_2025/20250325T190000Z_FX2 | 1545 | 1545 | 1546 | 1547 | +0 | 1.00 | — (no check) | not evaluable |
| yeongdeok_2025/20250325T230000Z_FL2 | 1546 | 1546 | 1822 | 1823 | +275 | 1.18 | 495 | ok |
| yeongdeok_2025/20250326T080000Z_FW1 (seen) | 648 | 653 | 898 | 899 | +245 | 1.39 | 431 | ok |

Notes on the table (all measured):
- On missions that run a check, isolation adds +12 to +275 MiB of family PSS. That is always below the check's own
  cgroup peak, so the 64 MiB slack was never needed. On these missions V2 / FROZEN is 1.15–1.40.
- Uiseong 0325T17 FW1: FROZEN is 855 MiB and both v2 arms are 465 MiB.
  - The difference is the bound-model transient that amendment E removed, which is absent from both v2 arms.
  - Isolation adds 0 MiB at the family peak here, because the peak falls outside the check.
- Refusal-type missions (no check): V2, V2_NOISO and FROZEN agree within 2 MiB.

### Ideas and gaps
- M3(d) is a single run. In that 216 s run the harness sampler used 101 s of CPU, in the harness interpreter, outside
  the job's family. I did not measure whether this slowed the job.
- FL2's verdict under isolation: R6 shows only that both arms fall inside the G1 set (see above). FL2's timing
  sensitivity belongs to Step 3 (work budgets), not to this step.
- M2-model has no verdict on refusal-type missions by construction: no check runs, so there is no cgroup peak.
- Hypothesis, untested: the +275 MiB on FL2 is the check child's private pages. Its cgroup peak is 495 MiB.

## Original Step 2 result (kit-v2-step2c): G5 memory FAILS as written; not accepted as is

Kit `kit-v2-step2c` (manifest `6a39762c…`, branch commit 90659b3 + the compare tools). Panel `v2_step2_g1`:
- 20 missions × 2 reps, frozen kit and v2 interleaved, 81 s, `--mode plain`, alone on the host;
- 18:23:42–18:50 UTC, **no restart** (no RESTARTS.jsonl); 80 rows;
- rows and own-module decisions are in `results/step2/panel/`; the comparison is `results/step2/G1_COMPARE.json`.

### Gates

| Gate | Result |
|---|---|
| G1 (pre-memory-map status and arrival, Thomas's rule) | **20/20**, FL2 rule included; reason changes: none |
| Memory-mapped statuses (expected 0 / 0) | **0 OUTSIDE, 0 NOT_PROVEN** |
| Published-check budgets | **28 checks, 28 `within_budget: true`**, mechanism `cgroup_v1_max_usage_parent_moved`, largest check peak **493 MiB** |
| G3 (shares within 1e-4) | **20/20** |
| G5 wall (summed median) | **0.893** including Yeongdeok 0325T23 FL2; **0.996 excluding it** (339.8 → 338.3 s) — pass either way |
| G5 memory (per mission ≤ +10% and ≤ 3,072 MiB) | **FAIL on 12 of 20 missions.** Everything is ≤ 3,072 MiB (largest 1,138 MiB), but +40% to +78% on every mission that runs a whole-road check |
| G2 | **28/28** published routes accepted by both frozen checkers, each in a fresh process (`results/step2/G2.jsonl`) |
| G2b (Thomas's `xcheck/g2b.py` @ deeb7c2) | **40 runs, 0 violations** (38 PASS, 2 NOT_APPLICABLE_STATUS) (`results/step2/G2B.json`) |

**G5 memory failures** (median family peak, frozen → v2, MiB):
- Hongseong: 84 → 123 and 69 → 109.
- Miryang: 88 → 133 and 73 → 118.
- Uiseong: 349 → 594, 350 → 603 and 370 → 627.
- Uljin: 203 → 324, 275 → 403, 215 → 333 and 171 → 290.
- Yeongdeok 0326T08 FW1: 640 → 1,138.

Refusal missions, which run no check, are unchanged. Uiseong 0325T17 FW1 fell from 848 to 566, which is the bound-model
transient removed by amendment E.

### Why: measured diagnostic (`tools/family_pss.py` → `results/step2/FAMILY_PSS.json`, single runs)

The controller's family reading sums each process's RSS. A forked child's RSS includes the pages it shares with the
parent, so those pages count twice. A PSS sum, which splits shared pages, separates double counting from real memory:

| Mission | Frozen RSS-sum / PSS-sum | v2 RSS-sum / PSS-sum |
|---|---|---|
| Uljin 0304T12 FW2 | 196 / 182 MiB | 314 / **224** MiB |
| Yeongdeok 0326T08 FW1 | 668 / 654 MiB | 1,147 / **903** MiB |

So the rise is **part double counting** (RSS-sum vs PSS-sum: +90 and +244 MiB) and **part real**: PSS still rises by
+42 and +249 MiB, i.e. +23% and +38%. Under either measure, G5 memory fails.

Hypotheses, not yet measured:
- The real part is (i) copy-on-write copies of parent pages touched in the child: Python reference counts and the GC
  write into every object the check reads (graph, request);
- plus (ii) the checker's caches, which are rebuilt in the child where in-process they could reuse freed parent heap.

**Consequence beyond G5 (stated, not yet measured):** the controller's memory guard reads the same family RSS sum. So on
a large parent (F-DYN Yeongdeok, 4.4 GiB resident EA), forking a check can trip the 3,072 or 12,288 MiB guard on
double-counted pages.

### Decision needed (per STEP2_ACCEPTANCE: "if G5 fails, Step 2 is not accepted as is; the fallback is written before a rerun")

Options, for the orchestrator or owner:
- **(F1) Reduce what the child copies, then re-run G5.** Call `gc.freeze()` before the fork, so the collector stops
  touching parent objects, and measure. This is a wrapper-only change and leaves the checker untouched. It does not
  remove refcount COW, and it does not fix the controller guard's double counting.
- **(F2) Fork only above a stated size.** Below it the check runs in process, as frozen, and the result is
  `within_budget: "not_proven"`. That changes those successes to NOT_PROVEN on the 1-hour panel, which defeats G1's
  purpose. I would not recommend it unless a different in-process upper bound is found.
- **(F3) Amend G5 memory to measure family PSS** (or the job's cgroup peak), and make the controller guard PSS-based in
  v2. This is honest about double counting but changes a frozen gate's measure after seeing results, so it is only
  possible as a declared owner decision. The real +23–38% would remain and would still fail +10%.
- **(F4) Accept the measured memory cost** of proving within_budget as Step 2's price, all ≤ 3,072 MiB here. This is an
  owner decision.

My recommendation: F1 first, as a measured diagnostic. If it brings PSS within +10%, combine it with F3 for the
controller measure, as an amendment written before any rerun. Otherwise F4 goes to the owner, with the numbers above.

### Post hoc diagnostics (orchestrator 18:54 UTC). Measured, single runs, not kit changes

**F1: `gc.freeze()` before the fork.** This was a diagnostic copy, `kit-v2-step2c-f1diag`; the overlay is unchanged. It
barely helps:

| Mission | Frozen PSS-sum | v2 PSS-sum | v2 + gc.freeze PSS-sum | v2 + gc.freeze RSS-sum |
|---|---|---|---|---|
| Uljin 0304T12 FW2 | 182 | 224 | **222** | 314 |
| Yeongdeok 0326T08 FW1 | 654 | 903 | **852** | 1,172 |

So the real copy-on-write growth is mostly not from the collector. Hypothesis: reference-count writes, plus checker
work in the child. Not extended to the 12 missions, because it does not help enough.

**(i) Controller guard on a large parent.**
- Setup: F-DYN Yeongdeok kriged_mean …415158166, 300 s, guard 12,288 MiB, request `rss_limit_mb` 12,288, kit-v2-step2c.
  The family was sampled every 10 ms (`tools/family_pss.py --fdyn`; trace `results/step2/FDYN_YD166_FAMILY_TRACE.json`).
- Outcome: **CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN**. The check was `within_budget: true`, with a cgroup peak of 523 MiB.
  This was one of the A1 requests whose check the frozen-kit lifetime gate discarded. It is a diagnostic only, not the
  F-DYN acceptance run.
- Family memory:
  - **during the check:** RSS-sum (the controller's measure) **9,352 MiB**, PSS-sum **5,083 MiB**. The controller
    recorded 9,335 MiB;
  - **outside the check:** RSS-sum 4,843 MiB, PSS-sum 4,826 MiB, with the EarliestArrivalBound resident.
- **Answer.**
  - At 3,072 MiB the guard trips on this request with or without the fork: the parent alone is 4.8 GiB before any check.
  - But during a check the controller's reading nearly doubles (+4.3 GiB of double-counted parent pages). So **any
    guard between about 5.1 and 9.4 GiB would stop this job on pages that exist once.** That is a correctness risk of
    the fork design under an RSS-sum guard, as the orchestrator suspected. At 12,288 MiB it does not trip.

**(ii) Fork-early / fork-server (design note, estimate only, not measured).** A check server forked before the bound
model and EA exist would hold only the pre-search footprint, shared with the parent.
- Under PSS this removes the big-page COW. The F-DYN case would be about 5.1 → about 4.8 GiB plus the check's own peak.
- Under the controller's RSS-sum, the server's whole resident set is counted again for the **entire** job, not only
  during checks. That is the pre-search footprint: graph, packet and imports, of the order of the parent's RSS at
  admission.
  - The 1-hour panel would therefore still be well above +10% family RSS.
  - The F-DYN check-time reading would fall from 9.35 GiB to roughly 4.8 + admission RSS + check peak.
- Promising only together with a PSS or cgroup family measure (F3). For Thomas to read; nothing is built.

### Not merged into this step's claims

The panel used the v2 worktree's `research/harness-2026-11/F-3.4/run_profile.py`. It differs from the main branch's
copy only by the F-DYN `paths=` and `memory_guard_mib` parameters (default 3,072), so it is identical for the panel.
