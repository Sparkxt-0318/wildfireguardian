# Benchmark plan, round 2 (frozen before the round-2 benchmark is run)

Frozen 19 Nov 2026, Shanghai evening, at the commit that adds this file, `bench2.py` and `margin_field/nb.py`.
`BENCH_PLAN.md` and `BENCH.md` §1 (round 1) stay as they are. Nothing below changes after the first round-2 number
exists; a mistake found later is corrected by a dated amendment at the bottom.

## Why a second round

Round 1 left three gaps, all stated in `BENCH.md`: the new pass was slower than the existing pass for a single field
on the three Yeongdeok caches; the only baseline for "many margins" was one existing pass per margin, with no smarter
baseline such as bisection; and nothing was compiled. Round 2 changes the code (`METHOD.md` §4.6 fast path, §4.7
compiled port) and measures again. The round-1 numbers are not replaced.

## What had been seen when this was written

Not blind for the pure-Python fast path. Before freezing I had run:
* a probe on 6 shelters (3 of `yeongdeok_2025/20250325T230000Z`, 3 of `uiseong_andong_2025/20250323T010000Z`), best
  of 3, with the 18,000-graph test and a pip download running on the machine: existing 0.08–0.42 s; new fast
  0.03–0.11 s at M = 0 and 0.03–0.14 s at M = 600; round-1 pass 0.09–0.37 s;
* the 18,000-graph test (fast path equal to the general path on every state; 0 mismatches against the existing field
  and the oracle);
* `bench2.py` on 340 toy random graphs, to check that it runs and reports 0 mismatches.

**Blind for everything compiled.** When this was frozen numba was not yet installed (the download was still
running). The compiled port had been run only as plain Python, on the 18,000 random graphs, where it equals the
reference pass on all 99,176 states. No compiled timing of any kind had been seen. If the port needs changes to
compile, they are made after this freeze and listed in the amendments; the tasks and rules below do not change.

Still running when this was frozen and to be finished before the benchmark starts: the six-cache exactness run with
the fast path (`results/real_fast/`).

## Machine and conditions

As round 1 (same Mac, one process, one thread, nothing else of this study running, `gc.collect()` before each timed
call, `time.perf_counter`), except the interpreter is `.venv-kcf/bin/python`: the same Python 3.13.13 with numba
added. The pure-Python methods do not import numba. All compiled code is compiled once on a toy instance before the
first timed call; compilation time is never counted.

## Methods

| name | what |
|---|---|
| EXISTING | `deadline_field.core.backward`, unchanged, pure Python. **The baseline for every claim.** |
| NEW | `margin_field(inst, M)` with the fast path (default), pure Python |
| V1 | `margin_field(inst, M, fast=False)`, the round-1 method, for continuity |
| NB | `margin_field_nb`, the compiled port of the general pass |
| NB0 | the same compiled kernel with M = 0 on a widened instance: a compiled pass for one margin |

There is no compiled form of EXISTING in the repository (`kcf-defend/fastfield.py` is a compiled scalar pass for
permanent closures only and does not compute this field). NB0 is my code, not the existing code.

## Inputs

The same 36 shelters as round 1 (six caches, cert rule, `random.Random(20261119).sample(sorted specs, 6)`), keep
variant, M = 600. And the 18,000 random graphs of the round-2 property test, as one batch.

## Tasks

| task | EXISTING | NEW | compiled |
|---|---|---|---|
| **T1** one field, margin 0 | `backward(inst)` | `margin_field(inst, 0)`; also V1 | NB: `margin_field_nb(inst, 0)`, graph packing included |
| **T2(K)**, K = 1, 2, 4, 8, 16, margins as round 1 | `backward(widen(inst, m_i))` per margin | one `margin_field(inst, 600)` + `level_set` of every μ_s and γ_s at each m_i | NB: one compiled pass + compiled read-off of R at each m_i. NB0: one compiled M = 0 pass per m_i |
| **T4** the margin of leaving now: largest m ≤ 600 with second 0 feasible, for every recorded origin of the shelter | bisection over m, one `backward(widen(inst, m))` + `issue_set` per probe, passes shared between origins | one `margin_field(inst, 600)` + `issue_margin` + value at 0 | not measured |
| **B** | `backward(widen(inst, m))` for m = 0..M | `margin_field(inst, M)` | not measured |

T3 of round 1 (all 601 margins) is not repeated.

Timing rules, as round 1: EXISTING's and NB0's times exclude `widen`; NEW's and NB's include building tents and the
read-off. The predecessor arrays of the graph are built once per shelter and shared by NB and NB0 in T2 (counted for
neither); in T1 NB builds them inside the timed call. T4: every widening the bisection asks for is built before the
clock starts. 5 repeats, the order of methods reversed on odd repeats; median, min, max.

Outputs compared outside the timed region, on the first repeat: T1 and T2, R and G of every state for NEW and V1
against EXISTING; R of every state for NB against EXISTING (T1, and T2 at margins 0, 60, 600) and against NB0 (every
T2 margin). T4: the margins themselves.

## Memory

`tracemalloc`, first sampled shelter per cache, separate run: one existing pass at margin 0; NEW at M = 600 and at
M = 0 (whole returned object). For NB the size in bytes of its two result arrays (tracemalloc does not see numba's
scratch buffers; no peak is claimed for NB).

## What will be claimed

Ratios per shelter, per cache the median of its 6 shelters, as round 1.

* **"Faster for one field"**: T1 ratio EXISTING / NEW above 1 on every one of the six caches.
* **"Faster for K margins"**: T2(K) ratio EXISTING / NEW above 1 on every cache.
* **"Faster than bisection"**: T4 ratio above 1 on every cache.
* The round-1 verdict rule is unchanged and was already met. Round 2 decides one thing: **the single-field caveat
  is removed from the verdict only if** "faster for one field" and "faster for K margins" at K = 1 both hold, there
  are zero mismatches in round 2, and the six-cache exactness run with the fast path has zero mismatches. Otherwise
  the caveat stays, with the round-2 numbers next to it.
* Whatever the outcome, `BENCH.md` says that the fast path is engineering that the existing pass does not have, so
  T1 does not show that the idea is faster than a single level pass; that is what NB against NB0 at K = 1 shows
  (same code, same engineering, M = 600 against M = 0), and it is reported either way.
* Compiled numbers are reported in full and **do not enter the verdict**: EXISTING / NB is not like for like
  (compiled against interpreted), and NB0 / NB compares two pieces of my own code.
* No claim for other machines or for instances unlike these.

## Amendments

**19 Nov 2026, after the run (14:32 UTC).** No change to tasks, inputs, repeats or rules.
1. The compiled port compiled under numba 0.68.1 exactly as frozen; no change was needed. The six-cache exactness
   run with the fast path finished, with zero mismatches, before the benchmark started.
2. T4 baseline, found in the results: the bisection as specified does not test m = 600 and m = 0 first. On these
   inputs every origin's answer is either the cap (74 of 79) or "cannot leave at second 0" (5), so the bisection
   used about 10 passes where 1 or 2 would do. The T4 numbers are reported as measured, with this stated beside
   them; the claim "faster than bisection" is to be read with it. Nothing was re-run.
