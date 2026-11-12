# Kit v2: certified routing beyond one hour — plan (written before any code)

**Owner decision** relayed by the orchestrator, 12 Nov 2026, 15:05 UTC.
- **Lead:** Priya. **Certificates and checkers:** Thomas, who reviews every step that touches them, before code: steps 2(c), 4 and 5, and option A.
- **Verification:** Mira. **Assessment of each step:** Iris.
- **Approval:** approved by the orchestrator (15:08 UTC; D1 decided as proposed). Thomas reviewed steps 2(c), 5 and 7
  and G2 at 15:09 UTC; his conditions are folded in below, including G2b.
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

**G2b. Optimality and no-route claims (Thomas).** G2 checks fixed routes only; the whole-road checker makes no
global claim. So every request is also run through the F-3.2 contact relaxation, which is a certified lower bound on
the full policy (script by Thomas, in F-3.2). It is run only on packets that pass X1; envelope packets are excluded.
- (a) Every v2 FEASIBLE or OPTIMUM_PROVEN arrival A must satisfy **A ≥ T_relax**, the relaxation's certified optimum
  for the same request.
- (b) If the relaxation certifies NO_ROUTE, v2 must not publish a route.
- (c) If v2 claims a full-policy no-route while the relaxation has a route, it is listed. This is not a
  contradiction, because the relaxation is weaker.
- These are necessary conditions, not a proof of optimality. A failure of (a) or (b) fails the step.

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

### Step 1b: support outcomes (approved by the orchestrator 15:38 UTC; fields agreed with Clara)

**Order.** Built in sequence after Steps 1 and 2, never ahead of them. It is placed here because it extends the
decision layer that Step 1 touches.

**What.** Each attempt's decision gains three things.

1. **`support`**, or `null` when the packet has no mask (frozen writer):
   `{writer_version, rule, mask_sha256, packet_writer_sha256, base_packet_writer_sha256}`.
   The writer identity field is aligned with the one Thomas's G2b records.
2. **`unknown_support_involved`**, one of:
   - `none`;
   - `route_crosses`: the published or candidate route enters a cell with unknown support, derived from the route's
     occupied cells and HAZARD support;
   - `refusal_depends`: **taken from the refusal certificate's own reasoning**, i.e. the certificate counts an
     unsupported cell as blocking;
   - `not_evaluated`.
3. **`memory_budget_mib`** and **`memory_budget_default`**, per D1.

The decision schema becomes `wfg.journey-decision/2`.

**Review.** Thomas reviews before code, because `refusal_depends` is a statement about what a refusal certificate
relies on.

**Acceptance.** Committed before any run.
- **Unmasked results are byte-identical** in every pre-existing decision field, on the 1-hour panel and on F-DYN. Only
  the new fields are added.
- On masked packets, each `route_crosses` and `refusal_depends` value is checked against an independent derivation:
  - `route_crosses` from the route's cells and the mask;
  - `refusal_depends` against the certificate.
- G1–G3 and G5 apply. Clara's planner mapping is fail-closed: any missing field on a masked packet is unresolved.

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
  - This touches certificate semantics, so it needed Thomas's sign-off. **Signed off (15:09 UTC) with conditions:**
    - **(i) Only the RSS replacement changes.** `RSS_LIMIT` (in `hybrid_checker._finish`) and
      `RSS_LIMIT_AFTER_ADAPTIVE_FALLBACK` change. The following stay exactly as they are, and still replace a completed
      result:
      - `WALL_CAP_AFTER_CHECK` and `WALL_CAP_DURING_FINALIZATION` (time is part of the deployment claim);
      - `AUTHORITY_CHANGED_DURING_ADAPTIVE_FALLBACK` (a correctness gate).
    - **(ii) A kept result carries `resource_budget {gate_mb, peak_mb (the check's own), within_budget: false}`.**
      - It is reported as "certified, outside the declared memory budget".
      - It is counted separately and never pooled with within-budget results.
      - Either the decision layer reads `within_budget`, or a distinct status is used. No within-budget count may
        include it.
    - **(iii) (a) + (b) are the main fix.** With the check in its own child process, the child's peak is the check's
      memory, so (c) matters only for checks that genuinely need more than 3 GiB. Each kept result records which
      mechanism kept it.
    - **(iv) Tests:**
      - completed-then-over-budget keeps the result with `within_budget: false`;
      - an interrupted check (MemoryError or an exception) stays UNRESOLVED;
      - an authority change still replaces;
      - a wall cap still replaces.

**Decision D1 (decided by the orchestrator, 15:08 UTC).**
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
- **Whole-function equality (Thomas, supersedes the line above).** The compact representation, decompressed or
  looked up, equals the frozen arrays **bit-for-bit at every (time, state) in the frozen domain**, on every F-DYN and
  1-hour request. The query set changes with steps 3 and 6, so queried-state equality is not enough.
- Any state outside a stored window or band returns an explicitly conservative value: a valid lower bound, such as 0
  or the static road-distance bound. This has a test.
- **No dtype narrowing that rounds.** Narrow only where the integer range provably fits, with max/min asserted at
  build time. Never use float32 for float64.
- A property test on random (time, state) pairs, plus the full-array comparison as the regression test.
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

`fastrad/TWO_TIER_ARGUMENT.md` must contain Thomas's four points:
1. **Each tier is individually a sound enclosure of the true coefficient.** This is the frozen kit's existing
   assumption; the argument cites where it is established. The cheap ⊇ exact property test is about fidelity, not
   soundness.
2. **Monotonicity.**
   - Per box, A's enclosure is either the full intersection or a superset of it.
   - So A's upper bounds are ≥ the frozen kit's, and A's lower bounds are ≤ the frozen kit's.
   - Therefore CERTIFIED under A implies CERTIFIED under the frozen kit, and DEFINITE_REJECT under A implies
     DEFINITE_REJECT under the frozen kit.
   - A can only lose decisions, never create them.
3. **Aggregation.** Dose is a sum and peak is a max of per-box bounds, so mixing cheap and exact boxes still gives a
   valid bound.
4. **The half-budget guard and the exact fallback do not affect point 2.**

Thomas reviews the argument.

## 3. What will not be done

- No change to the frozen kit or its outputs.
- No change to the hazard packets, the decision statuses, or the certificate contents, except where a step above
  says so and Thomas has approved it.
- No result from a test copy (A3(b)) is presented as a v2 or frozen-kit result.

## 4. First actions after approval

Step 0 only. Then G1/G2 on the scaffold, then Mira.

## Amendment B (16:0x UTC): refusal re-verification and the external review §12.4 (orchestrator, 15:52 and 16:00 UTC)

Rule-first, as for every step. Where I disagree or need a fact, it is marked **[open]**.

**G2c. Refusal certificates (Thomas reviews).**
- Every refusal certificate behind a v2 `FULL_MODEL_REFUSAL_PROVEN` is re-verified by **both** checkers in fresh
  processes, with the bundle sha256 recorded per run.
- A refusal that was not re-verified is published under a weaker, distinct status: `MODEL_REFUSAL_UNVERIFIED`. It is
  never pooled with re-verified refusals.
- Until G2c exists, every report of a kit refusal says "accepted on declared certificate fields, not re-verified".
  Checked: none of my F-3.4, F-4.2 or F-DYN reports calls a kit refusal "independently checked". The F-3.4 profile
  tables say "refusal proven", which is the kit's status name, and a footnote is now added there.
- **Step 0 G2b rerun with Thomas's fallback fix** (`thomas/routing-next` @ deeb7c2), with no manual exclusion:
  **40 run folders, 38 PASS, 2 NOT_APPLICABLE_STATUS, 0 violations** (`results/step0/G2B_all40.json`).

**G2c review (Thomas, 16:08 UTC); these conditions replace the G2c text above where they differ.**
- **Status.** The kit's internal `FULL_MODEL_REFUSAL_PROVEN` stays unchanged, so G1 identity holds. The mapping happens
  only at the reporting layer, via a field `refusal_reverification`:
  - `F32_BOTH_CHECKERS`;
  - `REEXECUTED_ONLY`;
  - `NONE`, which is published as `MODEL_REFUSAL_UNVERIFIED`.
- **There is no bundle to re-verify today.** The refusal dict from `rda_worker_v1_1.consider()` carries no proof
  object, and `_valid_refusal_certificate` checks three declared fields only. G2c therefore needs an emitted proof
  object first.
- **Stage Z refusals (contact_only_lattice_relaxation):**
  - emit an F-3.2 NO_ROUTE certificate (T = H + 1, C0–C4) for the same request;
  - check it with both F-3.2 checkers (`check_py.py`, `checker_c/wfgc_check`) in fresh processes;
  - record the bundle sha, plus the graph, packet and request digests;
  - gate: X1 rules 0–2 plus G2b agreement;
  - wording: "relaxation refusal independently checked by two checkers; implication to the kit model by an unverified
    dominance argument" (`xcheck/DOMINANCE_RULE.md`, code reading only, NOT verified).
- **Stage LO/LO2 refusals (road_lower_bound_lattice_relaxation):**
  - no independent certificate format exists;
  - a fresh-process road_core rerun is re-execution only, labelled `REEXECUTED_ONLY`, never pooled;
  - a certificate format is scoped separately by Thomas if the counts matter.
- **Count (Step 0 panel, v2, 2 reps).** Of 10 FULL_MODEL_REFUSAL_PROVEN results, **8 are stage Z** (Hongseong
  0700 FN1, FX1; Miryang 0601T08 FD1, FX1; 2 reps each) and **2 are stage LO** (Yeongdeok 0325T19 FD1, 2 reps). In
  missions: **4 of 5 refusal missions are Z, 1 is LO**.

**G2c result for the 4 stage-Z refusal missions (Thomas, 19:14 UTC; `thomas/routing-next` @ 8d3c58c7). NOT yet
verified by Mira.**
- All 4 are F-3.2 NO_ROUTE certificates with T = 3601. Each is accepted by `check_py` and `wfgc_check` in fresh
  processes, and each is FULLY_BOUND under binding rule 2.2 (R2, R3, T7a, T7b).
- Bundles (`xcheck/results/g2c_bundles/*.v2.wfgc`; record `xcheck/results/g2c_stage_z_refusals.json`):
  - Hongseong 0700 FN1: I 3848b22fb146eb98, 61,944 B;
  - Hongseong 0700 FX1: I 1c21b2d5b7a5c1e3, 61,943 B;
  - Miryang 0601T08 FD1: I 1b4026fd5f770959, 139,440 B;
  - Miryang 0601T08 FX1: I 136d908351445370, 137,294 B.
- Input digests match the request, HAZARD and graph prefixes I sent. The packet gate P1 (X1 rules 1, 2 and 4) passes;
  rule 3 is covered by T7b.
- So `refusal_reverification = F32_BOTH_CHECKERS` for these 4 missions, with the required wording: "relaxation refusal
  independently checked by two checkers; implication to the kit model by an unverified dominance argument"
  (`xcheck/DOMINANCE_RULE.md`, code reading only).
- Yeongdeok 0325T19 FD1 (stage LO) stays `REEXECUTED_ONLY`.

**G6. Full one-hour verdict reproduction (before any multi-hour v2 number is quoted).**
- v2 must reproduce all **9,722** recorded one-hour route-check verdicts, not only the 20-mission panel.
- **Pass rule:** identical verdicts on every record.
- **Exceptions are mechanical, listed beforehand,** and of the FL2 type only: a record whose frozen verdict itself
  varies across the recorded repetitions, judged against the frozen set.
- The expected exception list is produced from the records before v2 runs.
- **Source of record (orchestrator, 16:07 UTC).** The planner's six committed caches (Clara, `planner/cache/…`).
  - Unit: one route-check job. 9,722 jobs: 7,771 checked routes, 1,468 model no-route, 204 unresolved (distinct
    after re-checks) and 297 timeout originals.
  - Per-job rows reproduced from them: Richard's `results/threeway_jobs` on `claude/f31-deadline-field` (Nora rows
    25 and 43).
- **"Reproduce" (Iris's definition, fixed before any run):**
  - a route has identical legs and arrival;
  - a refusal stays an identical refusal;
  - a timeout may resolve, but never into a contradiction of a recorded route or refusal.
- **Pending:** the row format from Richard and the cache schema from Clara, before the G6 runner is written.

**Step 6 design question (with Richard; short design note before any build).** Should v2's multi-hour solver be
Richard's interval deadline field, with the unchanged frozen checker as verifier, instead of the dense per-second
sweep?
- **Fact check of the reviewer's figure (measured here).** The EarliestArrivalBound stores `C` as int16 over
  (horizon + 1) × (edges + 1) (`zsweep.py:434`). Its recorded `bytes`:
  - Uiseong–Andong 5 h: **1,577,947,308 B = 1,505 MiB**;
  - Yeongdeok 5 h: **4,029,747,700 B = 3,843 MiB**.
  These equal the reviewer's 1,505 and 3,843 MiB exactly.
- **Is it the binding array?**
  - **Yeongdeok: yes.** EA is resident at 4.4 GiB through search, and 3.84 GiB of that is this array. It exceeds the
    3,072 MiB guard on its own.
  - **Uiseong: no.** The binding peak there is the **transient** RoadBoundModel build (9.0–9.5 GiB, 0.40 GiB
    resident after). The EA array (1.5 GiB) fits.

**Step 7 extension: constant-time first radiation tier (Thomas reviews admissibility).**
- If (non-flame flux bound × journey duration + incurred dose) is below the dose budget, and the flux bound is below
  the peak limit, then radiation is decided with no geometry. Otherwise fall through to option A, then to the exact
  tier.
- **Decided (orchestrator, 16:07 UTC): the cell-binned 0.0156 is NOT used.** The F-3.1 figure of 0.0156 kW/m² is the packet's **cell-binned** flux
  (Nora's scope note). It does **not** bound the whole-road checker's continuous enclosure, which is the quantity the
  checker certifies. Using it there would be unsound.
- **Proposal:** use a bound **of the checker's own enclosure**, e.g. the per-packet maximum of the radial-tier upper
  coefficient over every road box and every non-contact time, computed once per packet. Prove it is an upper bound
  under the checker's model before use.
- Flame contact is never decided by this tier.
- **Admissibility conditions (Thomas, 16:08 UTC).** A proof note is required before any code, and Thomas reviews it.
  1. **Bound the checker's per-source upper `hi`,** not the true flux. In `hybrid_radiation._coefficients`,
     hi_i = min(radial whole-source, 8×8 tiled, analytic, density/2), and hi = 0 for non-potential sources.
  2. **Windowed-mode trap.** Sources outside the request window get hi_i = outward(density/2), not the radial value.
     Either take the bound as the maximum of the checker's own `_coefficients` output, or prove that out-of-window
     sources have zero activity at every integrated time. This needs a reading of `RadiationBounds.trajectory_bound`
     first.
  3. **Composition.** Bound = max over road boxes b and times t of Σ_{i active at t} hi_i(b), over all members, with
     outward rounding.
     - The dose test uses bound × (horizon − departure), or a duration proven to cover the integration interval,
       including waits and dwell.
     - The peak test uses the checker's own comparison (strict or not).
  4. **No exclusion of contact times in version 1.**
  5. **Bind the bound to the packet sha and the checker settings version** (wfg.radiation.hybrid/1 plus the settings
     dict), and recompute it on any change.
  6. **Tests before use:**
     - (a) every request on which the tier fires also passes the full checker's radiation acceptance; any
       disagreement means the tier is unsound;
     - (b) a scaled-up control stops the tier firing;
     - (c) the firing rate is reported, and the tier is not worth its risk if it rarely fires.
  - Still to read before the note: `trajectory_bound` integration, how incurred dose enters, and the order of contact
    vs radiation in the checker.

**Step 8 (new): arrival ties broken by clearance (labelled behaviour change).**
- Among routes with the **same** arrival, prefer the larger clearance (the F-4.2 dilation r*).
- It is **outside G1's identity set**. Every changed route is listed, with old/new clearance and identical arrival and
  status.
- G2 and G2b apply to every changed route.
- Reviewer's figure: 2 of 15 one-hour missions gain clearance at no arrival cost. To be reproduced from F-4.2 data
  before the build.

**Reporting rules (apply to every table from now on).**
- **(E) Domain-limited clearance.** Where the packet edge sets the clearance, the clearance is labelled
  **domain-limited (lower bound within the packet)**.
  - In F-4.2 these are already labelled CROP: 8 of the 15 one-hour routes, and the F-DYN short routes.
  - The word "domain-limited" is added to the labels in the next F-4.2 commit.
- **(F) Budgets in work units.** Every budget is stated in work units (labels, expansions, sweep states) **and** in
  seconds, with the host named.

**(G) No-re-entry default for person-facing multi-hour outputs.**
- A burned cell is closed for the rest of the horizon. The reopening model ([b, b + T) activity) stays a labelled
  research variant.
- Scout-suggested occupant limits (1.0 kW/m², distance factor 1.5) never enter an operational output.
- **Decided (orchestrator, 16:07 UTC; Leo assigned).** The kit's search and checker read activity from the packet.
  No-re-entry is therefore realised as a **packet-level** transform: expiry set to the horizon for every ignited cell, written
  by the packet writer with its own identity (Leo).
- v2 code stays unchanged under it, and G1 still compares like with like on the frozen packets.
- No-re-entry results are reported as their own line.

## Amendment C (16:1x UTC): review §12.7 (orchestrator, 16:10 UTC)

**Facts first (my F-DYN results; non-evaluated runs).**
- **Today, linear dose decides 0 multi-hour requests.**
  - The kit's 2 routes have a certified dose upper bound of at most 0.0017 kJ/m².
  - The modified kit's 5 routes reach at most 4.92 kJ/m², on the 3,953 s route. That is a mean enclosure flux of about
    1.2 W/m² over about 4,070 s of journey plus dwell.
  - No request was refused on dose. Every F-DYN UNRESOLVED was a memory or search stop, and the AT_ISSUE failures are
    contact.
- **The reviewer's arithmetic is right as a capacity statement.** Using the packet's maximum non-flame road-cell flux
  (cell-binned model flux, not the checker's enclosure):
  - Uiseong 0325T17, 0.016 kW/m²: 100 kJ/m² after **6,250 s (104 min)**;
  - Yeongdeok 0325T23, 0.0089 kW/m²: after **11,236 s (187 min)**;
  - the reviewer's 0.012 kW/m² gives 8,333 s (139 min), and 216 kJ/m² over 18,000 s.
- **So linear dose would bind only for journeys or waits of about 1.7–3 h spent near the highest-background road
  cells.** The routes found so far are 59 s to 3,953 s long and pass through low-flux cells.
- **Caveat.** The checker integrates its own enclosure, which can exceed cell flux. The binding time under the
  checker could therefore be shorter than the cell-flux figures above. This is not measured.

**Step 9 (new): thresholded dose as a labelled multi-hour policy variant.**
- **What.** Flux below a stated threshold contributes nothing to dose. The linear dose stays as the frozen reference.
- **Reporting.** **Both** are reported for every multi-hour result, side by side, never pooled. No operational output
  uses the variant. Making it a default is the owner's decision.
- **Threshold value and source (Sofia, 16:11 UTC; sources she has read; logged in her LOG.md, (5)).** No source gives
  a multi-hour "no effect" flux, so every threshold is a labelled **modelling choice**, not a physiological fact.
  - **Primary variant: 1.0 kW/m² at the occupant (q_occ).** Source: NCC 2022 Vol. 1 Specification 43, the
    vulnerable-occupant refuge design limit. Label: "NCC Spec 43 vulnerable-occupant design limit; below it no dose
    accrues (modelling assumption)". It is a design criterion, not pain or burn data, and gives no duration.
  - **Sensitivity: 2.5 kW/m².** Source: ISO 13571:2007 §8.2 (read via DSTU ISO 13571:2012), "tolerated for 30 min or
    longer". It is a tenability / pain-onset threshold for escape and is stretched beyond its stated 30 min at
    multi-hour.
  - **Glass.** Neither source covers vehicle glass. If q_occ = τ·q_ext is used, τ ≈ 0.5 is labelled as MTDC 1997-based
    (windows block about half the radiant heat), with a glass-failure caveat: MTDC also reports breakage under fire
    heating.
  - **Reported:** both thresholds, plus how many hour-long background segments flip between them.
- **Review.** Thomas reviews admissibility; the variant must still be an upper bound of the thresholded quantity under
  the checker's enclosure. Iris assesses.
- **Acceptance (written before any code).**
  - The linear results are byte-identical to the reference.
  - The variant never certifies a route that the linear rule rejects **on contact or peak**. It may only differ on
    dose.
  - Every difference is listed.

**Reporting rule (R): road-limited "no route".**
- Every multi-hour "no route" on today's clipped graphs is reported as **"no route (road-limited: graph clipped to the
  one-hour window)"**, counted separately.
  - Roads exist only inside the recorded one-hour windows.
  - The Uiseong window lies 99.7% inside the final burn set, and about 45% of burned cells lie outside the windows.
- This holds until Daniel's full-export-grid graph is verified.
- It applies equally to `FULL_MODEL_REFUSAL_PROVEN` and to any relaxation NO_ROUTE.

## Amendment D (16:1x UTC): re-ordered plan (orchestrator decision, 16:14 UTC)

**New order:**
1. **Step 0:** done; verification pending (Mira, REQUEST 12).
2. **Step 1:** reasons and stage metrics (acceptance committed, e26a0ff).
3. **Step 2:** memory accounting. Kept: the checker's gates stay relevant to any solver.
4. **Step 3:** work-unit budgets.
5. **G6a:** the seeded 705-job reproduction (G6_RULE.md).
6. **Step 6:** the interval-field solver as the multi-hour solver, with the frozen whole-road checker as verifier.
   Sub-order:
   - an earliest-arrival pass restricted to the field;
   - measure field memory at 5 h;
   - restate the exactness precondition in the **checker's own enclosure quantity** (Thomas reviews);
   - then G2, G2b, G2c, plus multi-hour optimality against independent optima where they exist.
   - The dense path stays the 1-hour solver until G6 shows the field reproduces it.
7. **Then, by decision:** Step 1b (support outcomes); Step 7 (constant radiation tier and option A, 1-hour); Step 8
   (tie-break); Step 9 (thresholded-dose labelled variant). Iris reads the Step 9 sourcing lines before code.

**Step 3b (separate, later; NOT part of Step 3; orchestrator 20:02 UTC, from Iris's observation): cache
`routing.core.edge_occupancies`.**
- **Hypothesis**, measured once by cProfile under load: about 93% of the Uiseong F-DYN Z setup (about 18 s) is 11,011
  calls to `core.edge_occupancies`, one per contact-candidate edge, at about 1.6 ms each in exact Fraction arithmetic.
- **What:** a cache keyed on the edge and the fire field, if and only if a code reading shows the output depends on
  nothing else (no request field, no clock).
- **Acceptance:**
  - byte-identical occupancy output for every key (old vs cached, on the 1-hour panel and the F-DYN packets);
  - Z setup wall before and after, per mission;
  - setup units unchanged; the setup unit counts calls, so a cache hit still counts as one unit, which keeps budgets
    comparable. This is to be confirmed with Iris.
- **Thomas reviews it,** because the occupancies sit under the contact certificates.
- **Scope note:** if Step 6 (the interval-field solver for multi-hour) passes, the multi-hour solver no longer runs this
  setup. This step then matters only for the dense one-hour path.

**Steps 4 and 5 are CONDITIONAL, not deleted.** They are built only if Step 6 fails its acceptance, or if the dense
path is still needed at multi-hour:
- Step 4: dense per-forecast precompute of the bound model;
- Step 5: EA bound memory.

**Citation rule.** DESIGN_STEP6.md cites Richard's F-DYN router-field result (ac80919) as **unverified** until Nora has
passed it.
