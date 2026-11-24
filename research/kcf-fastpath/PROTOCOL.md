# kcf-fastpath PROTOCOL: a faster, lighter deadline field, and proof that the answers do not change

Status: **FROZEN** at the commit that adds this file, before any timing of a fast solver. Any later change is added
at the end as a dated amendment with its reason; nothing above the amendments is edited.

Base: `Main` at `5ff9aa90`. Branch `research/kcf-fastpath`. Not merged into `Main`; a pull request is left open.
`deadline_field/core.py` is **not changed**: it is the baseline. The fast solver is a separate file,
`research/kcf-fastpath/fastfield.py`, that returns a field with the same reading interface (`inst`, `R`, `G`,
`stats`), so the unchanged `core.issue_set`, `core.issue_core` and `core.witness` read it.

Read first: `research/kcf-theorem/THEOREM.md` (Theorems 1 and 2, hypotheses M1–M4), `research/kcf-bench/BENCH.md`,
`research/kcf-bench-mac/RESULTS.md` (whose procedure, caches and job sets are reused here).

## 1 The two changes

Notation as in THEOREM.md §1: states are edges s; R_s, G_s ⊆ T = {0..H}; B, W, A, IB, AN; forbidden turns F.

### Change 1: scalar fast path (`solve(inst, scalar=True)`)

Theorem 2 says that under M1–M4 every set is a prefix [0, L] and one integer per state, the latest time, is
enough, computed by a reverse Dijkstra on ℓ_s = max(a_s, max_j τ_j(ℓ_j)), τ_j(x) = min(c_j − 1, x − D_j).

The solver **checks the hypotheses on the instance it is given, per state, and never assumes them**:

* For each edge j, M1 on its window: B_j ∩ [lo_j, up_j] is empty or [c, up_j]; c_j is the first closed second in
  the window (up_j + 1 if none).
* For each waitable node v, M2 on its window [lo_v, H − 1 − h(v)].
* For each state s, M3 on its window: A_s ∩ [α_s, H] is empty or [α_s, a].
* A state s is **R-clean** if M2 holds at head(s) (when waitable) and every allowed successor j ((s, j) ∉ F,
  tail(j) = head(s)) satisfies M1 and is G-clean. It is **G-clean** if it is R-clean and M3 holds for s. This is a
  greatest fixed point, computed as its complement: "dirty" spreads from the failing edges and nodes to their
  predecessors (a reverse breadth-first search over the turn-aware predecessor lists).
* G-clean and R-clean states are solved by the reverse Dijkstra, one integer per state (R-clean-only states keep
  their G as a short list because their acceptance set is not a prefix). **Every other state is solved by the
  interval method of `core.backward`**, reading the clean states' sets as fixed. Clean states never depend on dirty
  ones (the clean set is closed under successors), so the scalar phase runs first and the interval phase second.
* **M4 is not needed**: the origin read-off stays the existing interval code (`core.issue_set`), which handles
  any IB_o and AN_o.

Windows. Without pruning lo_j = 0, lo_v = 0, α_s = 0. **up_j = H − D_j − h(head j)**, h = `core.static_to_dest`
(fire-free, turn-free lower bound on the remaining travel time to any acceptance): a start on j after up_j cannot
be part of any accepted journey, so a closure that reopens only after up_j cannot matter. With `windows=False` the
solver uses the plain THEOREM.md windows [0, H − D_j] and [0, H − 1]. The sets returned are identical either way;
only the share of scalar states changes. Before this protocol I measured (untimed, `explore` scripts in §8) that on
UA 03-24 the plain per-state hypotheses leave about 5% of states scalar (the 88 reopening edges reach almost every
state), and the windowed check about 94%. **The mixed solver is used** (scalar where the per-state check passes,
intervals elsewhere); its soundness is proved in `WRITEUP.md`. A whole-instance fallback is the special case where no
state passes.

Report per cache: the share of states that took the scalar path (G-clean, R-clean only, interval, and with pruning
the void states), with `windows=True` (the benchmarked solver) and `windows=False`.

### Change 2: lower-bound pruning (`solve(inst, prune_origins=[...])`)

One forward Dijkstra from all origins of the field at departure 0, ignoring closures, waits, turns and acceptance,
gives e(v) ≤ arrival second at v of any journey from any of those origins at any departure t ≥ 0.
α_s = e(tail s) + D_s bounds the arrival over s. In the backward pass every piece of R_s or G_s is cut to
[α_s, H] (seeds, every candidate piece and every waiting closure); a state with α_s > H is void (empty) and not
processed. With pruning the windows of change 1 are lo_j = e(tail j), lo_v = e(v) and α_s.

The field records its sources. `fastfield.issue_set` and `fastfield.witness` **refuse an origin that was not in
the forward search** (ValueError), or with `fallback=True` re-solve without pruning for it: pruning is off for any
origin not in the forward search. `WRITEUP.md` proves that the cut cannot change Feas(o) for any source o, any
departure, or any witness route.

### Solver variants benchmarked

`baseline` = `core.backward`; `scalar` = change 1 (`windows=True`); `prune` = change 2; `both` = changes 1 and 2.

## 2 Data

* The six recorded caches `planner/cache/{uiseong_andong_2025,yeongdeok_2025}/*.json` (`research/kcf-bench-mac/common.py::CACHES`).
* Routing inputs (graphs and packets): `/Users/jp/wildfireguardian-forecast/data/routing`, the SHA-verified
  release `research-final-20261015` (`tools/fetch_routing_inputs.py`); all 132 files match `INPUT_FILES.json`
  (checked 23 Nov 2026). Read only. The data folder named for this task, `/Users/jp/Desktop/wildfire` (`data/`),
  was read first: it holds the finals forecast and physics data (`regions/` arrival-time rasters, `environment/`,
  `sources/`, `records/`) but **not** the routing graphs or packets the deadline field reads, so it is not an
  input here. Nothing is written inside it.
* Keys: `/Users/jp/wildfireguardian-keys/keys.env` does not exist on this machine (see `NEEDS.md`). No key is used.

## 3 Equality tests (all must pass, for each change alone and both together)

Every test compares with the unchanged `core.backward` on the same instance. Interval lists are normalized (sorted,
disjoint, non-adjacent), so two lists are equal exactly when the two sets are equal second by second.

* **E1 (from the task).** Feas(o) identical, second by second, to the current solver, for every origin, on all six
  recorded caches. Origins: for every destination spec (node, dwell, window) of a cache, every start node of a job of
  that spec (the origins `run_b.py` builds the field for), over **all** jobs of the cache. Variants `scalar`,
  `prune`, `both`, and also `scalar` and `both` with `windows=False`. (`eq_real.py`)
* **E2 (state sets).** For every state of every field: R_s and G_s identical (variants without pruning), or identical
  to the baseline sets cut to [α_s, H] (with pruning). Without pruning this implies Feas(o) identical for **every
  node** o as origin (`issue_core` reads only G, B, W, AN). Also the windowed fixed-point certificate
  (`fastfield.check_fixed_point`, equation (E) of THEOREM.md on [α_s, H]) must pass on every fast field. (`eq_real.py`)
* **E3 (answers and witness routes).** For every job of every cache: verdict, arrival second and the complete leg
  sequence of the witness identical to the baseline's. (`eq_real.py`)
* **E4 (random instances).** `test_fastfield.py 2000`: 2,000 instances in each of three families (`general` and
  `closure` from `research/kcf-theorem/randgraphs.py`, and `mixed`: up to 40 nodes and 120 edges, mostly permanent
  closures with a few reopening roads, waits and late shelters), seed 20261123. For six variants (neither, scalar,
  prune, both, scalar and both with `windows=False`): E2 on every state, the fixed-point certificate, Feas(o) for
  every node (or every pruning source), the witness at every feasible second, brute-force `checker.feasible_set` and
  `checker.check_route` on the two small families, and the refusal and fallback for non-sources. Zero differences.
  `mutants.py 300` must report differences for **every** mutant (hypotheses assumed instead of checked; pruning bound
  one second too high; a bound that is not a lower bound; no origin guard; destination window one second too narrow)
  and none for the unmutated code.
* **E5 (pruning guard on real data).** For every spec, three non-origin nodes (seeded choice): `issue_set` must refuse
  them, and the fallback must equal the baseline Feas. (`eq_real.py`)

The equality runs are untimed and separate from the benchmark. Outputs: `results/eq_<cache>.json`,
`results/random.json`, `results/mutants.json`.

## 4 Benchmark plan

Same six caches, same job sets and same procedure as `research/kcf-bench-mac` (method B), 5 repeats, one core.

* **Procedure.** `run_fast.py SOLVER CACHE OUT [JOBS]` is `research/kcf-bench-mac/run_b.py` step for step (load cache,
  packet model, precondition per (limits, incurred), one field per destination spec over the jobs' start nodes,
  issue set and witness per job), with the field call replaced by the chosen solver (`prune` and `both` get the spec's
  origins as pruning sources). Each run is measured by the unchanged `research/kcf-bench-mac/measure.py` (wall,
  CPU, peak resident set of the process, load average before and after).
* **Job sets** (the ones kcf-bench-mac ran B on): `full` (every job of the cache), `pass1` (the frozen pass-1
  set `runs/jobs/<cache>.pass1.json`; for UA 03-24 the 1,093 jobs A ran, `UA0324.pass1_ran.json`, as in its
  Amendment 4), and `repeat` (the 50-job set `runs/jobs/<cache>.repeat.json`). 18 job sets.
* **Solvers:** baseline, scalar, prune, both. **5 repeats** of each (solver, job set): 360 timed runs.
* **Order:** repeat-major. In repeat r the caches run in the order of `common.CACHES` rotated by r − 1; for each cache
  the job sets run full, pass1, repeat; for each (repeat, cache, job set) the four solvers run in the order
  baseline, scalar, prune, both rotated by (r − 1 + cache index) mod 4. Repeat 1 writes per-job results; repeats 2–5
  run with `KCF_BENCH_B_SLIM=1` (identical computation, per-job output not written), as kcf-bench-mac did. The
  repeat-1 per-job answers (about 150 MB) are written outside the repository; the committed run file keeps their
  SHA-256, and equal digests across the four solvers are an extra check of E3 on the timed runs themselves.
  `bench.sh time` is the exact sequence; a run already finished is never re-run after an interruption.
* **One core:** macOS cannot pin a process to a core. Every timed run is one single-threaded Python process
  (`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`, `MKL_NUM_THREADS` = 1), started only after the
  previous one has exited; nothing else of this study runs during a timed run. The machine is the user's working Mac;
  load average is recorded per run and reported, never used to drop a run.
* **Python:** `/Users/jp/miniforge3/bin/python3` (3.13.13, the one kcf-bench-mac used), `PYTHONHASHSEED=0`.
* **Memory probe (untimed, after the timing):** one run per (solver, cache) on the `full` set with
  `KCF_FAST_TRACEMALLOC=1`: per spec, the peak bytes Python allocates during the solver call and the bytes the
  finished field keeps.
* **Metrics:** field time (`timing_s.fields`: the solver calls only, summed over specs), whole-run wall and CPU
  (`measure.py`), whole-process peak RSS, the tracemalloc solver peak and kept bytes, and the fast-path shares.

## 5 Pass rules

* **Correctness gate.** A change passes the gate only if E1, E2, E3 and E5 show **zero** differences on all six
  caches and E4 shows zero differences with every mutant detected, for that change alone **and** for both changes
  together. One difference anywhere fails the gate for that change, and no speed or memory claim is made for it.
* **Speed.** For each (job set, solver) the ratio baseline ÷ solver of the field time, as the median over the 5
  repeats with the widest range the repeats allow, [min ÷ max, max ÷ min] (the rule of `research/kcf-bench/BENCH.md`):
  **faster** if the whole range is above 1, **slower** if below 1, otherwise **not distinguished**. The same rule is
  reported for whole-run wall time and CPU.
* **Memory.** **Lighter** if the tracemalloc solver peak is lower than the baseline's on that cache (summed over the
  cache's specs, and also the largest single spec). Whole-process peak RSS is reported with the same range rule as speed.
* **A change PASSES** if it passes the correctness gate, its field time is **faster** on the `full` job set of all
  six caches, and its solver memory peak is **lighter** on all six. It **PARTLY passes** if it passes the gate but not
  every cache is faster or lighter (each such cache is named). It **FAILS** if it fails the gate.
* Every cache and every repeat is reported, whatever the outcome. No run is dropped or re-run for being slow.

## 6 What is written

`fastfield.py`, `run_fast.py`, `eq_real.py`, `test_fastfield.py`, `mutants.py`, `bench.sh`, `summarize.py`,
`results/` (raw run files and `RESULTS.json`), `WRITEUP.md` (proofs and results), `NEEDS.md`.

## 7 Rules for the run

No watermark or attribution line in commits, pull request or files. Work is pushed at least once a day.
`/Users/jp/Desktop/wildfire` is read only (another account's repository): nothing is committed, pushed or written there.

## 8 Done before this protocol was written (stated for completeness)

Untimed exploration on the six caches: counts of M1/M2/M3 failures and of clean states per spec (plain and windowed),
the forward lower bound's reach, and deterministic heap push and pop counts of each variant on three specs of
UA 03-24 and YD 03-25 19Z. One timing was taken: the **baseline** `core.backward` alone on six UA 03-24 specs
(0.16–0.55 s per spec) while reading the instance structure. **No fast solver was timed.** Unit runs of
`test_fastfield.py` (up to 30 instances per family) and `mutants.py 100`, and E1–E3/E5 on two UA 03-24 specs, all
with zero differences and every mutant detected.

## Amendments

**A1, 23 Nov 2026, before any timing.** The E1–E3/E5 run on UA 03-24 (`eq_real.py UA0324`) was stopped after 5 of
31 specs (0 differences so far) because it ran far longer than the other caches, and re-run as six parallel processes
over disjoint spec subsets (`eq_real.py UA0324 OUT 0,1,...,5`, ..., `30`), merged by `merge_eq.py` into
`results/eq_UA0324.json`. `merge_eq.py` checks that every variant covered all 31 specs. The tests are the same; only
the run was split. Reason: time.
