# Kit v2: certified routing beyond one hour — plan (written before any code)

**Owner decision** relayed by the orchestrator, 12 Nov 2026, 15:05 UTC.
- **Lead:** Priya. **Certificates and checkers:** Thomas, who reviews every step that touches them, before code: steps 2(c), 4 and 5, and option A.
- **Verification:** Mira. **Assessment of each step:** Iris.
- **Revisions:** revised 15:1x UTC after Iris's assessment (adopt; steps 1↔2 swapped; G1 exception made mechanical;
  G5 added; steps 3–5 tightened).
- **Branch:** `claude/priya-kit-v2`, off `Main` @ 8fdce35. **Location:** `experimental/window-routing-v2/`.

## 0. Rules that hold for every step

- **The frozen kit is never edited.** That covers the release kit and the request-window kit
  (`experimental/window-routing/`, candidate `WFG-request-window-routing-20261029`).
- **v2 is built by its own builder,** `build_kit_v2.py`. It takes the request-window kit as its parent, verifies the
  parent's manifest hashes before copying (as `build_kit.py` does), and overlays only the files under `stack-v2/`.
- **v2 has its own identity,** so no output can be mistaken for the frozen kit's:
  - `candidate_id = WFG-request-window-routing-v2-<date>`;
  - `parent_candidate_id` and the parent manifest sha are recorded;
  - its own `CANDIDATE_MANIFEST.json`;
  - every worker output gains `kit_identity: {candidate_id, manifest_sha256}`;
  - the README states "v2 development kit — not the frozen kit".
- **Tests.**
  - Every existing test of the parent kit runs unchanged against v2 and must pass. No test is weakened or skipped.
  - Each step adds its own tests first (test-first).
- **No accuracy or soundness claim is relaxed for speed.**
  - Any change to what a certificate says, or to a bound a certificate relies on, needs Thomas's review **before** it
    is used in a run that is reported.
- **Process per step.** I write a step's acceptance rule into this file and commit it before that step's runs; then I
  build, test and run; Mira verifies; Iris assesses. A step does not start until the previous step is verified,
  unless the orchestrator says otherwise.
- **Reporting is always separate.** v2 counts are reported apart from the frozen kit's counts:
  - F-DYN: the frozen kit gives at most 2 of 12;
  - the offline re-check line and the A3(b) modified-kit line also stay separate.

## 1. Global acceptance rule (applies to every step that changes behaviour)

**G1. Frozen 1-hour panel.** The 20 missions of the request-window panel at the 81 s speed-equivalent budget, 2 reps,
uninstrumented, against a fresh 2-rep run of the frozen kit interleaved on the same host.
- **Identical (status, arrival seconds) sets on 19/20.**
- **Yeongdeok 0325T23 FL2** passes iff every v2 outcome is one already seen from the frozen kit at 81 s on this host:
  UNRESOLVED, FEASIBLE@1922 or OPTIMUM_PROVEN@1922. This is the stated rule from `OPTION_A_PLAN.md`.
- **Exception (mechanical definition, Iris).** An UNRESOLVED may become certified only if all three hold:
  1. the frozen kit's own per-stage records for that request show a memory stop, or a completed check that was
     discarded;
  2. the v2 result passes G2;
  3. where the frozen run left a rejected witness or a conditional optimum, the v2 arrival equals it.
- **Expected count, stated before every run:** the number of such changes on the 1-hour panel. I expect **zero**
  there. Any occurrence on the 1-hour panel goes to review, not to automatic acceptance.
- **Failures:**
  - certified → UNRESOLVED is a failure;
  - a certified arrival changing is a failure;
  - the class moving between FEASIBLE and OPTIMUM_PROVEN, in either direction, outside the FL2 rule is a failure.

**G2. Certificates.** Every route v2 publishes, on the 1-hour panel and on F-DYN, is re-checked in a fresh process by
both of the following, **unchanged**. Both must accept: whole-road CERTIFIED_ADMISSIBLE; independent ok with no codes.
- the frozen kit's whole-road checker (`adaptive_checker`, sha `1da95550…`, with the hashes of the files it loads);
- the routing package's independent checker (`routing.independent` after `validate_*`).

**G3. Bounds.**
- Certified dose and peak upper-bound shares on the 1-hour panel must be identical to the frozen kit's (within 1e-4
  absolute share), unless the step's own rule says otherwise **and** Thomas has approved.

**G5. 1-hour cost (Iris; the project's second and third priorities).** At every step, report on the 1-hour panel:
- the summed median wall time;
- per-mission peak family memory;
against the frozen kit, on the same host.

The regression tolerance is stated now:
- the summed median wall may not rise by more than **10%**;
- no mission's peak memory may exceed the frozen kit's by more than **10%**, or exceed 3,072 MiB.

A step that fixes multi-hour while slowing the 1-hour kit beyond this is not accepted as is.

**G4. F-DYN.**
- Report v2 counts on the 12 requests of `FDYN_PLAN.md` (300 s and 900 s, 1 rep). Report them beside the frozen
  kit's, never pooled.
- No pass threshold. F-DYN is the target, not a gate.
- **Peak family memory is reported per request in every table,** so a reader can see what budget each result needed
  (Iris, D1).

## 2. Steps, in order

### Step 0: scaffold (no behaviour change)

**What.**
- `build_kit_v2.py`; `stack-v2/` that is empty except for an identity module; `README`; `CANDIDATE_MANIFEST`.
- A test that the builder refuses to write into, or over, any frozen kit path.
- A test that the parent's manifest hashes are re-verified.

**Acceptance.**
- With no overlay changes, v2 reproduces the frozen kit **bit-for-bit in verdicts and arrivals** on G1 (all 20 sets
  identical).
- G2 holds on all published routes.
- All parent tests pass.

### Step 1: honest terminal reasons and persisted stage metrics

**What.**
- A memory stop is reported as a memory reason, not SEARCH_TIMEOUT.
- "Search returned conditional optima but no check completed" gets its own reason.
- Each search stage writes running labels and expansions to `STAGE_PROGRESS.json` periodically (every 2 s), and
  flushes them on the deadline signal, so a deadline stop still leaves them.
- The decision-layer change is limited to the reason mapping. Statuses are not changed.

**Acceptance.**
- G1–G3. Statuses and arrivals are identical, so only reason strings may differ, and each difference is listed.
- Tests: each stop kind maps to its reason. A killed worker leaves progress no older than 2 s.
- **Why first (Iris).** It changes no status, so it can be accepted on "statuses and arrivals identical". It also
  provides the instrument for judging every later step, including whether step 2 moved a result for the intended
  reason.

### Step 2: memory accounting (the three 3 GiB lifetime-peak gates)

**Findings it addresses** (F-DYN, verified):
- the solver gate (`phaseB/road_core.py:751-757`) and the checker gate (`hybrid_checker.py:9`, `_finish`) compare
  the **process-lifetime** `ru_maxrss`;
- a transient 9 GiB bound-model build therefore disables search permanently, even though about 2 GiB stays resident;
- the checker gate **replaces a completed check result** with `RSS_LIMIT`.

**Design (to be reviewed by Thomas before code).**
- **(a) Isolation.** Bound construction (RoadBoundModel, EarliestArrivalBound) and each whole-road check run in their
  own child processes, with results passed back by file or shared memory and hash-verified. The worker's own lifetime
  peak then reflects only search.
- **(b) Measure current memory.** The solver and checker gates measure **current** RSS (`/proc/self/statm`), not
  lifetime peak, in addition to (a).
- **(c) Never replace a completed check.**
  - If a memory limit is reached **after** a check has completed, the completed result is kept and the memory event is
    recorded beside it.
  - A check **interrupted** by a memory limit stays UNRESOLVED (fail-closed is unchanged for incomplete checks).
  - This touches certificate semantics, so it needs Thomas's sign-off.

**Decision D1 (Iris agrees with the proposal; the orchestrator's answer is pending).**
- The controller guard (3,072 MiB) already samples **current** family RSS. The F-DYN stops at 300 s were genuine: the
  Yeongdeok EA bound is 4.4 GiB resident.
- So v2 either keeps a 3 GiB deployment budget (then Yeongdeok needs step 5 first) or declares a larger budget as an
  explicit, reported parameter.
- I propose: keep 3,072 MiB as the reported default, and report F-DYN additionally at a declared 12,288 MiB budget,
  labelled, with peak family memory per request in every table.

**Limit, stated in advance (Iris).** Step 2 will **not** rescue Uiseong at the 3 GiB budget.
- A child process that builds the bounds is still in the controller's sampled family, so its transient 9 GiB still
  counts against the controller guard.
- Only building the bound outside the request (step 4) removes it from that budget.
- For Uiseong, step 2's acceptance therefore concerns the solver and checker gates only.

**Acceptance.**
- G1–G3, G5.
- On F-DYN at 300 s with the declared budget, the 4 Yeongdeok requests whose checks were discarded in A1 reach
  certified results without the A3(b) constant edit, and G2 holds on them.
- New tests:
  - a synthetic transient-peak test (allocate then free beyond the gate, then search) must not stop search;
  - a check completed and then followed by a memory event must keep its result.

### Step 3: caps enforced promptly; work-based where possible

**Findings.**
- Z ran 20–23 s against a 6 s cap on Uiseong. LO ran 246–273 s against an inferred ~160 s cap. One LO call never
  returned.
- Whether Z holds a certified incumbent when its fixed 6 s wall cap expires flips the outcome class between runs
  (A4: …207 gives 8 proven / 1 feasible / 1 stopped; …168 gives 8 feasible / 2 stopped).

**What.**
- First, locate the overruns: where time goes outside the cap checks, e.g. setup before the heap loop and
  arrival-bound queries.
- Then add cap checks there.
- Replace the Z wall cap by a **deterministic work budget** (sweep seconds × lattice states, or labels).
- **Calibration rule, fixed before the rerun (Iris).** Calibrate on the **1-hour panel only**, never on the
  multi-hour set, so the cap cannot be tuned to produce a result. The budget is the median work Z performs in 6 s
  over the 20 missions on this host, rounded up to a power of two. It is committed with its measurement before any
  F-DYN run.
- The overall complete-deadline stays wall-time.
- **Watchdog (for the call that never returned).** A stage that exceeds its cap by more than a factor of 1.5 (or
  10 s, whichever is larger) is killed and reported as `STAGE_CAP_WATCHDOG`. It is never silently continued.

**Acceptance.**
- G1–G3.
- Rerun A4 (10 reps × 2 requests, 900 s): each request gives **one** outcome class in 10/10.
- Every stage stops within max(1 s, 5% of its cap) of its cap on the F-DYN set.
- A watchdog test with a synthetic non-returning stage passes.

### Step 4: per-forecast precompute of the road bound model

**Finding.** The bound model depends only on (forecast, active window). The identity keys are equal across origins,
and it costs 53–82 s on Uiseong.

**What.**
- Build it once per (packet sha, window, code sha) in a separate process.
- Store it as an authenticated artifact (like the prepared-graph cache), loaded by the worker after hash
  verification.
- **The cache key covers everything the model depends on (Iris):** graph sha, packet sha, active window, the code
  sha of every module in the build, and the numpy version and dtype. Thomas reviews before code.

**Acceptance.**
- G1–G3.
- **Regression test (Iris):** cached arrays equal freshly built ones, byte-for-byte, on every packet used.
- **Stale-cache test:** changing any one key component must make the cache miss.
- Report the time saving separately for the bound model and, later, for the EA bound.

### Step 5: the EA bound's resident memory (4.4 GiB on Yeongdeok)

**What.**
- Profile its arrays: dtype, (time × state) layout and what is actually read.
- Reduce them (narrower dtype, banded or sparse storage, computing only the reachable time window), keeping the
  values **identical**: it must stay an exact lower bound.
- Thomas reviews, because optimality certificates rely on the bound's admissibility.

**Acceptance.**
- G1–G3.
- The bound values are equal to the frozen implementation's at every state queried by the search, on every F-DYN and
  1-hour request.
- **Full-array equality (Iris)** on every instance small enough to hold both implementations. A difference at a state
  one request does not query can be a queried state on another.
- Resident memory is reported.

### Step 6: Uiseong search

**What.** Informed by the instrumented test-copy run already approved (expansions over time at one long budget,
declared before running). The design follows from what that run shows:
- if the frontier keeps growing steeply, a better bound or a different formulation is needed;
- if it finishes at some multiple of the budget, that multiple is the measured cost.

**Acceptance.** Written when the design is known, before code.

### Step 7: option A, two-tier radiation (1-hour item)

**What.** Folded in here. Its acceptance rule is the committed `OPTION_A_PLAN.md`:
- identical verdicts;
- the FL2 rule;
- bound shares within 1e-4;
- a wall gain of at least 20%;
- a property test, a nesting log, a half-budget guard;
- Thomas reviews the argument.

If it fails, it is recorded as a negative and dropped.

## 3. What will not be done

- No change to the frozen kit or its outputs.
- No change to the hazard packets, the decision statuses, or the certificate contents, except where a step above
  says so and Thomas has approved it.
- No result from a test copy (A3(b)) is presented as a v2 or frozen-kit result.

## 4. First actions after approval

Step 0 only. Then G1/G2 on the scaffold, then Mira.
