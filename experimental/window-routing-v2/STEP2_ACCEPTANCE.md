# Step 2: memory accounting. Design and acceptance, written before any Step 2 code

Thomas reviews this design before code, per PLAN 2(c). Implementation also waits for Mira's verification of Step 1.

## The problem (F-DYN findings, verified)

Three lifetime-peak gates:
- the controller guard: current family RSS, 3,072 MiB;
- the solver gate: `road_core`, `ru_maxrss` vs `limits.rss_limit_mb`;
- the checker gate: `hybrid_checker._finish`, `ru_maxrss` vs the constant 3,072, and `adaptive_checker.py:185-186`.

Because the solver and checker gates compare **process-lifetime** peaks:
- a transient 9 GiB bound-model build disables all later search;
- a resident 4.4 GiB EA array causes completed checks to be **replaced** with RSS_LIMIT.

## Design

**(a) Isolation.**
- **RoadBoundModel construction** runs in a **spawned** child process (`multiprocessing`, spawn context).
  - The model is passed back through a temporary file: `numpy.save` arrays plus a pickled small state. Every array's
    sha256 is checked on load.
  - The parent's lifetime peak no longer includes the 9 GiB transient.
- **Each whole-road check** runs in a **forked** child (`multiprocessing`, fork context). Its route, request, graph and
  checker are copy-on-write; the check's result returns as JSON over a pipe.
- **The EarliestArrivalBound** stays in the parent: it is used during search. Its memory is Step 5 or Step 6.

**(b) Gates measure the right quantity.**
- **Solver gate (`road_core`):** compares the process's **current** RSS (`/proc/self/statm` resident) with
  `limits.rss_limit_mb`, instead of the lifetime `ru_maxrss`.
- **Checker gate (`hybrid_checker._finish`, `adaptive_checker`):** compares the check's **own** memory, the forked
  child's **private (unshared) peak**, with the constant.
  - The private peak comes from `/proc/self/smaps_rollup` (Private_Clean + Private_Dirty), sampled at the same points
    the gate already reads plus at the end. Pages shared copy-on-write with the parent (graph, EA) are not the check's.
  - **Fallback (spawn):** if Thomas does not accept the private-memory measure, the check runs in a **spawned** child
    instead, and the gate reads that child's own lifetime peak (his condition iii). The G5 cost is measured either way.
- **The controller guard** is unchanged (current family RSS, children included). D1 decides the budget: 3,072 MiB
  default, with a declared 12,288 MiB run labelled.

**(c) A completed check is never replaced for memory (Thomas's conditions i–iv).**
- Only the `RSS_LIMIT` and `RSS_LIMIT_AFTER_ADAPTIVE_FALLBACK` replacements change.
- These still replace a completed result, exactly as today: `WALL_CAP_AFTER_CHECK`, `WALL_CAP_DURING_FINALIZATION`
  and `AUTHORITY_CHANGED_DURING_ADAPTIVE_FALLBACK`.
- A completed check over its memory gate keeps its result. It carries
  `resource_budget {gate_mb, peak_mb (the check's own), within_budget: false, mechanism}`.
- The decision layer maps it to the **distinct reported status `CHECKED_JOURNEY_OUTSIDE_MEMORY_BUDGET`**.
  - It is never counted with within-budget results.
  - The kit's internal certified status is unchanged, but such a route is **not** published as a within-budget journey.
- An interrupted check (MemoryError or any exception) stays UNRESOLVED.

## Tests, written first (`tests/test_step2_memory.py`)

1. **Transient peak.** In a process that allocates, then frees, more than the gate before search, `road_core.solve` on
   a small fixture still expands (current-RSS gate). The frozen lifetime gate stops it at 0 expansions; this is shown
   as the control.
2. **Checker private memory.** A forked check whose parent holds a large allocation passes the gate when its own
   private peak is below the gate.
3. **Thomas's tests (iv):**
   - completed-then-over-budget keeps the result, with `within_budget: false`;
   - an interrupted check stays UNRESOLVED;
   - an authority change still replaces;
   - a wall cap still replaces.
4. **Bound-model transfer.** The model returned from the spawned child equals a freshly built one: every array is
   byte-identical, on one 1-hour and one F-DYN packet.
5. **Fork safety.** The check child exits cleanly. The controller's cleanup census shows no leftover processes.

## Acceptance (Step 2 passes iff all hold)

- **G1 on the 1-hour panel:** identical statuses and arrivals, plus the FL2 rule.
  - **Expected UNRESOLVED → certified changes: 0.** No 1-hour mission hits a memory gate (peak ≤ 1.6 GiB).
  - **Expected reason changes: 0** beyond Step 1's FX2 deadline behaviour.
- **G2, G2b, G3** as in PLAN.
- **G5: wall ratio ≤ 1.10.** Spawning the bound-model child and forking each check add overhead, which is measured
  and reported per mission. If G5 fails, Step 2 is not accepted as is; the fallback is isolation only above a stated
  graph size, written before a rerun.
- **F-DYN, labelled, at the declared 12,288 MiB controller budget**, 300 s, the 12 requests, 1 rep:
  - the 4 A1 Yeongdeok requests whose checks were discarded reach certified results **without** the A3(b) constant
    edit (the mechanism is recorded per result);
  - G2 on every route;
  - Uiseong is reported as is; Step 2 is not expected to rescue it (PLAN, Iris);
  - also reported at the 3,072 MiB default, where the controller guard is still expected to stop most requests
    (D1 reporting).
- **All Step 0/1 tests and parent tests:** pass, with the provenance tests differing only on the overlay files.

## Thomas's review (17:21 UTC), folded in before any code

**1. Checker gate: an asymmetric rule.**
- Private memory is the right quantity, but a sampled `smaps_rollup` value is a **lower** bound on the private peak.
- Therefore:
  - **sampled private > gate ⇒ outside budget.** This is sound.
  - **`within_budget: true` needs an UPPER-bound measure:**
    - **(a) a cgroup memory peak** for the check child; or
    - **(b) the spawn fallback** (the spawned child's lifetime `ru_maxrss`, an overestimate).
  - If neither is available, the result is **`within_budget: "not_proven"`**: its own reported row, in neither pool.
- **Host fact (checked 17:2x UTC).** This container has **cgroup v1**, not v2: no `cgroup.controllers` at the root.
  - The memory hierarchy at
    `/sys/fs/cgroup/memory/process_api/<id>/claude-code-bash` **allows creating a child cgroup** (mkdir/rmdir
    tested), which has `memory.max_usage_in_bytes`.
  - Plan for (a): the check child moves itself into a fresh child memory cgroup before allocating, and
    `memory.max_usage_in_bytes` is read at the end.
  - That peak covers pages first touched by the child, including COW copies (`move_charge_at_immigrate` = 0, so pages
    shared with the parent stay charged to the parent). It also includes the page cache of files the child reads,
    which only **overestimates** and is safe.
  - The mechanism is recorded per result: `cgroup_v1_max_usage`, `spawn_ru_maxrss`, or `fork_sampled_private`
    (outside-budget only).
  - Where neither (a) nor (b) is available, the result is `not_proven`.
- **New test:** a forked check that spikes above the gate and frees between two sample points. The fork-sampled path
  alone must **not** mark it `within_budget: true`.
- **G5 decides** between fork + cgroup and spawn, on cost.

**2. Reporting rule.** `CHECKED_JOURNEY_OUTSIDE_MEMORY_BUDGET` is accepted, with Thomas's conditions. Any table that
says "within budget" counts **only** `within_budget: true`; `not_proven` never counts.

**3. The spawned bound-model build is certificate-relevant (correction).** My earlier "I believe not" is withdrawn:
RoadBoundModel feeds the LO/LO2 refusals and `lower_bound_arrival`. Guards added:
- **(a) Code identity.** The parent records the sha256 of every module file the build imports (road_bounds,
  radiation_bounds, hybrid_radiation, zsweep, and their imports). The child recomputes them and refuses on any
  mismatch.
- **(b) Hash at the source.**
  - The child hashes each array **before** `numpy.save`, and the parent verifies after load.
  - The pickled state is sha-checked too, written to a 0700 private temporary directory, and deleted after load.
- **(c) Determinism environment.** The thread environment (OMP / MKL / OPENBLAS_NUM_THREADS) and any seed are passed
  explicitly. The byte-identity test runs with the **production** thread settings.
- **Recorded per result:** mechanism = spawned build, and the array sha256s, so a later re-check can tie a refusal to
  its bound arrays.

The prediction "Expected UNRESOLVED → certified changes on the 1-hour panel: 0 (peak ≤ 1.6 GiB)" stays as written.
