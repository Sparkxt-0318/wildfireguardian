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

## cgroup v1 points (Thomas, 17:22 UTC) and the host probe, run before any Step 2 code

Under-counting is the unsafe direction. The design is fixed as follows:
1. **The parent moves itself** into a fresh child cgroup, forks, and moves itself back, so fork-time charges (page
   tables, task struct) land in the child's cgroup. Mechanism name: `cgroup_v1_max_usage_parent_moved`.
2. **Swap.** On this host swap is off (`/proc/swaps` is header-only), and `memory.memsw.max_usage_in_bytes` is present.
   The gate reads **memsw** max_usage when present, otherwise max_usage with swap verified off. If swap is on and memsw
   is absent, the result is `not_proven`. The swap state is recorded per run.
3. **kmem.** Accounting is active here: `memory.kmem.max_usage_in_bytes` is non-zero (1.2–3.7 MiB) in the probe
   cgroups. The kmem state is recorded per run. If kmem is ever not accounted, `within_budget: true` requires
   max_usage ≤ gate − 64 MiB (a stated margin) and records "kmem not counted".
4. **Freshness.** One new cgroup per check, never reused. The code asserts usage before fork ≤ 4 KiB, reads max_usage
   after the child exits and before `force_empty` and rmdir, and records a failed rmdir without treating it as a
   measurement failure.
5. **use_hierarchy** is recorded. It is 1 here.
6. **Page cache** needs no change; it can only over-count.
7. **Portability.** Recorded per run: cgroup version, path, kmem state, swap state, mechanism. With no mechanism the
   result is `not_proven`, never `within_budget: true`.

**Probe on this host** (`tests/probe_cgroup_v1.py` → `results/step2/PROBE_CGROUP_V1.json`), all pass:

| Test | Expected | Measured peak |
|---|---|---|
| (a) child allocates 512 MiB | ≥ 512 MiB | **514.5 MiB** |
| (b) child only reads a 1 GiB parent array | far below 1 GiB | **3.5 MiB**: shared pages are not charged |
| (c) child writes every page of the 1 GiB parent array (COW) | ≥ 1,024 MiB | **1,027.3 MiB** |
| (d) child spikes 768 MiB and frees | the spike is seen | **773.0 MiB** |

Every cgroup was fresh (usage 0 before fork) and every rmdir succeeded. memsw max equals max_usage throughout, as
expected with swap off.

**Thomas cleared the mechanism (17:24 UTC).** Two test additions, no change of design:
- Test (d) is also run through the **full gate**, at a gate of 512 MiB, below the 773 MiB spike. It must assert
  `within_budget: false`, showing that the decision path uses the cgroup peak.
- The code **asserts** that the parent is back in its original cgroup after each fork, comparing `/proc/self/cgroup`
  before and after. A failed move-back raises, so it cannot silently charge later parent work to a check.

(Thomas did not verify PROBE_CGROUP_V1.json itself. Mira verifies it with Step 2.)

## Amendment E (18:15 UTC, before any bound-model code): the transient is one expression, so chunk it, don't spawn

**Measured** (`tools/bm_mem.py` → `results/step2/BOUND_MODEL_TRANSIENT.json`): RoadBoundModel construction alone, on
the four F-DYN packets, active window 0–18,000 s, with RSS sampled every 2 ms.

| Packet | Edges E | Potential sources P | One E×P float64 block | Lifetime peak | RSS after build | Peak at |
|---|---|---|---|---|---|---|
| Yeongdeok firms_early | 111,924 | 513 | 438 MiB | 1,992 MiB | 253 MiB | 95% of build |
| Yeongdeok kriged_mean | 111,924 | 625 | 534 MiB | 2,381 MiB | 257 MiB | 94% |
| Uiseong firms_early | 43,826 | 6,443 | 2,154 MiB | **9,071 MiB** | 384 MiB | 95% |
| Uiseong kriged_mean | 43,826 | 6,837 | 2,286 MiB | **9,618 MiB** | 398 MiB | 95% |

**Hypothesis, to be confirmed by the chunked build's measured peak.** The peak is 4.2–4.6 × one E×P block and occurs
at about 95% of the build. That matches the edge-to-source distance block in `road_bounds.RoadBoundModel.__init__`
(`gx`, `gy` and their temporaries, of which only the length-E `self.dist` is kept). It is a pure element-wise
expression followed by a row-wise `min`.

**Change of design (replaces (a)'s spawned bound-model build; everything else in this file stands):**
- `self.dist` is computed in **row blocks of edges**. Each block's temporaries are capped at 64 MiB:
  `rows = max(1, 64 MiB / (8 · P))`.
  - Every element is computed by the identical numpy expression on identical inputs.
  - `min` over a row does not depend on how the rows are blocked: it is a selection, not an accumulation.
  - So the array is **byte-identical by construction**. The test checks it rather than assuming it.
- **No spawned child, no array transfer, no pickled state.** Thomas's guards 3(a)–(c) (code identity across processes,
  hash at the source, thread environment) protected that transfer, so they no longer apply. Nothing crosses a process
  boundary for the bound model.
- **Certificate relevance.** `dist` only sets `n_default`, the sub-box counts per edge: "graph geometry (floats; only
  selects sub-box counts)". It is still certificate-relevant through the bound arrays. Hence:
- **Test 4 (replaced): byte identity.**
  - Chunked `dist` == unchunked `dist` byte for byte (`tobytes()`), and so is `n_default`.
  - This is checked on the 1-hour Yeongdeok and Uiseong packets and on all four F-DYN packets.
  - It is also checked at three block sizes: 1 row, the production cap, and E rows (unchunked).
  - **Recorded per result:** `bound_model.dist_sha256` and `dist_block_rows`, so a refusal ties to its bound arrays.
- **Acceptance addition:** the chunked build's measured lifetime peak on the four F-DYN packets is reported. The
  expectation (hypothesis) is ≤ RSS after build + 2 × 64 MiB + 200 MiB.
- **Memory caveat, stated:** the parent's lifetime peak still includes the EarliestArrivalBound array (Yeongdeok
  4.4 GiB resident). That stays Step 5/6 work, as already written, and the current-RSS solver gate is unchanged by this
  amendment.

Code for this amendment waits for Thomas's review. The check-isolation code (fork + cgroup v1) and the current-RSS
solver gate are as already cleared, and proceed now.

### Amendment E accepted by Thomas (17:55 UTC), with conditions, all adopted

1. Chunk over **edges only**; the full source axis is in every block. The literal expression and dtypes are kept,
   including the integer 0 in `np.maximum(0, …)`.
2. **Expected peak, stated before the measurement** (written 18:2x UTC, before any chunked build was measured).
   - The chunked build's lifetime peak on the 4 F-DYN packets, sampled at 2 ms with `tools/bm_mem.py`, is expected to be
     at most **post-build RSS + 5 blocks of 64 MiB + 200 MiB**. A block's live temporaries are gx, gy and up to three
     intermediates; 200 MiB covers the other transients earlier in the build.
   - Concretely:
     - **Uiseong ≤ 400 + 320 + 200 ≈ 920 MiB** (it was 9,071 and 9,618 MiB);
     - **Yeongdeok ≤ 260 + 320 + 200 ≈ 780 MiB** (it was 1,992 and 2,381 MiB).
   - If the Uiseong peak does not fall to that order, the transient is elsewhere. Then E is **not** the fix, the
     spawned build with guards 3(a)–(c) comes back, and no trial edits are made in the certificate path.
3. **Test 4** (`tests/test_step2_dist.py`):
   - function level: random shapes, rows 1 / 3 / 64 / cap / E / > E, E = 0, E not a multiple of the block, and
     exact-zero distances with no −0.0;
   - model level, using the parent's synthetic fixture: dist, n_default and identity at 1 row, the cap, unchunked and 2
     rows; the full_pot = 0 (inf) branch; no edges, which behaves as the parent does;
   - real packets, each in its own process: the 1-hour Yeongdeok and Uiseong packets and the 4 F-DYN packets, at 1 row,
     the cap and unchunked, against the parent build.
4. `bound_model_dist {dist_sha256, dist_block_rows}` is recorded per result in RESULT.
5. Relevance (Thomas): outward bounds are sound for any sub-box count. Tightness decides LO infeasibility and
   `lower_bound_arrival`, so identity is required for G1.

### Amendment E: chunked-build peak measured (kit-v2-step2b; `results/step2/BOUND_MODEL_TRANSIENT.json` → `chunked_amendment_E`)

| Packet | Lifetime peak before → after | Stated beforehand | RSS after build | Build time before → after |
|---|---|---|---|---|
| Yeongdeok firms_early | 1,992 → **495 MiB** | ≤ 780 | 250 MiB | 7.1 → 4.8 s |
| Yeongdeok kriged_mean | 2,381 → **501 MiB** | ≤ 780 | 256 MiB | 7.7 → 5.8 s |
| Uiseong firms_early | 9,071 → **709 MiB** | ≤ 920 | 384 MiB | 31.2 → 26.5 s |
| Uiseong kriged_mean | 9,618 → **728 MiB** | ≤ 920 | 391 MiB | 32.1 → 28.1 s |

The hypothesis is confirmed: the peak now falls at 64–68% of the build, not 95%, and every value is within the stated bound.
Single runs, not quiet-host timings. The build times are indicative only, and G5 is decided by the panel.

### Thomas's checker review (18:12 UTC): three points, fixed before the panel (kit-v2-step2c)

1. **One verdict.** The checker no longer writes `resource_budget`. Its own record is `checker_sampled_budget`
   `{sampled_private_peak_mb, sample_is_check_own, over_gate_from_sample}`; the worker's wrapper alone writes
   `resource_budget`, which is the field the decision reads.
   - Test: a real job (Uljin 0304T12 FW2) whose RESULT text contains exactly one `"within_budget"`, which is True with
     `cgroup_v1_max_usage_parent_moved`.
2. **No parent-side outside claim.**
   - The checker claims "over from sample" only when `v2_memory.IN_CHECK_CHILD`, which is set in `run_check_forked`'s
     child, whose sampler is reset at fork. Anywhere else nothing is claimed, and the verdict comes only from the wrapper.
   - Fork failure: no check runs, the check is UNRESOLVED `CHECK_CHILD_FAILED`, and the budget is `not_proven`.
     Nothing is left behind (the cgroup is removed and the parent is back).
   - cgroup setup failure: the check is forked without a cgroup, so the verdict is the child's own sample (False only if
     over) or `not_proven`.
   - All of this is tested.
3. **Call sites.**
   - The only integration whole-road check is in `whole_road` (`_v2_check`).
   - `rda_worker` lines 374 (`road_core.check_route_mode`, inside the Z sweep) and 464 (`core.check_route`, the
     centre-mode path) are the search/routing package's own route checks, not `HybridChecker`.
   - The worker sets `v2_memory.REQUIRE_CHILD_FOR_CHECK = True`, so `HybridChecker.check` in the worker process raises
     `V2_WHOLE_ROAD_CHECK_IN_PARENT_PROCESS`. Tested both in the parent (raises) and in the child (runs).

Real-packet byte identity (test 4) passes 18/18 (`results/step2/DIST_IDENTITY.json`). Full suite on kit-v2-step2c:
50/50; parent runner ok.

### G1 comparison rule for Step 2 (Thomas 18:24 UTC), written before any panel result is read

The panel started at 2026-11-12T18:23:42Z, and no row has been read.

- **G1 identity** compares the v2 status **before the memory map** against the frozen kit: `certified_status_within_kit` when
  the memory map applied, otherwise `authoritative_status`. Arrivals are compared the same way; the arrival of a mapped
  journey is taken from `journey_outside_memory_budget`. The FL2 rule and the mechanical UNRESOLVED → certified exception
  apply as in PLAN.
- **Reported separately:** the count of memory-mapped statuses (OUTSIDE, NOT_PROVEN) and, per check, the
  `resource_budget` verdict, peak and mechanism.
- **Expected on the 1-hour panel on this host: 0 OUTSIDE and 0 NOT_PROVEN.** Every mission peaks at ≤ 1.6 GiB and the
  cgroup mechanism works here.
  - Any NOT_PROVEN means the mechanism failed on some job. That is a finding to report, not a G1 failure to explain away.
- **Portability (to be stated wherever v2 statuses are quoted):** on a host with no usable upper-bound mechanism, every
  success becomes CHECKED_JOURNEY_MEMORY_BUDGET_NOT_PROVEN by design.
- Thomas's note on the wrapper test: span (ii) fails closed if a later `rec[...]` assignment is added. Do not loosen
  the comparison.
