# Step 2 result: memory accounting. G5 memory FAILS as written; Step 2 is not accepted as is

Kit `kit-v2-step2c` (manifest `6a39762c…`, branch commit 90659b3 + the compare tools). Panel `v2_step2_g1`:
- 20 missions × 2 reps, frozen kit and v2 interleaved, 81 s, `--mode plain`, alone on the host;
- 18:23:42–18:50 UTC, **no restart** (no RESTARTS.jsonl); 80 rows;
- rows and own-module decisions are in `results/step2/panel/`; the comparison is `results/step2/G1_COMPARE.json`.

## Gates

| Gate | Result |
|---|---|
| G1 (pre-memory-map status and arrival, Thomas's rule) | **20/20**, FL2 rule included; reason changes: none |
| Memory-mapped statuses (expected 0 / 0) | **0 OUTSIDE, 0 NOT_PROVEN** |
| Published-check budgets | **28 checks, 28 `within_budget: true`**, mechanism `cgroup_v1_max_usage_parent_moved`, largest check peak **493 MiB** |
| G3 (shares within 1e-4) | **20/20** |
| G5 wall (summed median) | **0.893** including Yeongdeok 0325T23 FL2; **0.996 excluding it** (339.8 → 338.3 s) — pass either way |
| G5 memory (per mission ≤ +10% and ≤ 3,072 MiB) | **FAIL on 12 of 20 missions.** Everything is ≤ 3,072 MiB (largest 1,138 MiB), but +40% to +78% on every mission that runs a whole-road check |
| G2 / G2b | running (below) |

**G5 memory failures** (median family peak, frozen → v2, MiB):
- Hongseong: 84 → 123 and 69 → 109.
- Miryang: 88 → 133 and 73 → 118.
- Uiseong: 349 → 594, 350 → 603 and 370 → 627.
- Uljin: 203 → 324, 275 → 403, 215 → 333 and 171 → 290.
- Yeongdeok 0326T08 FW1: 640 → 1,138.

Refusal missions, which run no check, are unchanged. Uiseong 0325T17 FW1 fell from 848 to 566, which is the bound-model
transient removed by amendment E.

## Why: measured diagnostic (`tools/family_pss.py` → `results/step2/FAMILY_PSS.json`, single runs)

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

## Decision needed (per STEP2_ACCEPTANCE: "if G5 fails, Step 2 is not accepted as is; the fallback is written before a rerun")

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
