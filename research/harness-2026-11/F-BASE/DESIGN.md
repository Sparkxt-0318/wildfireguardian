# F-BASE: an independent exact baseline for the router (design and frozen comparison rules)

Owner: Marcus. Stream from the FIRE direction document §7.1. Status: **design and rules committed before any run.**

## Problem (as defined by the O2 integer instance)

The input is Thomas's independently re-derived integer instance in the `.wfgc` `INSTANCE` block (F-3.2 `FORMAT.md`, PR #116).
- **States.** A state `s` is the incoming edge: `s ∈ {0..nE-1}`, plus `s = nE` for the origin start state. The state's node is `hd(s)`.
- **Moves from `(s, t)`.**
  - **Edge `j`:** allowed when `tail[j] = hd(s)`, `(s, j)` is not forbidden, `t ∉ EB_j` and `t + D_j ≤ H`. It leads to `(j, t + D_j)`, and that arrival is *admitted*.
  - **Wait:** allowed when `hd(s)` is waitable and `t ∉ WB_hd(s)`, with `t + 1 ≤ H`. It leads to `(s, t + 1)` and is *not admitted*.
- **Goal.** The smallest admitted arrival time `T` with `T ∈ AC_hd(state)`, starting from `(s0, dep)`, which is admitted (the `k = 0` case). If none exists by `H`, the verdict is NO_ROUTE.

This is the contact relaxation of the router only. Radiation, peak and dose obligations are out of scope, exactly as for F-3.2's certificates.

## Exact baseline (F-BASE-X)

Forward label sweep with **interval-set labels**, one set of reachable seconds per state, not a single earliest time.

- **Why sets.** At a non-waitable node a later arrival can depart on an edge whose departure window was blocked earlier, so earliest-arrival dominance is invalid (F-3.2 spec).
- **Ordering.** States are processed in chronological order of interval starts, with a priority queue keyed by the earliest unprocessed second of each state.
- **Waiting.** At waitable nodes waiting closes each reachable interval forward, until the next blocked wait-start second (inclusive of the arrival second).
- **Edges.** Each edge maps a reachable set `S` to `(S \ EB_j) + D_j`, intersected with `[dep, H]`.
- **Termination.** The first admitted arrival in an acceptance set gives `T`, and a parent pointer per (state, interval) reconstructs a witness. The search stops when the queue empties (NO_ROUTE) or when the earliest unprocessed second exceeds the best `T`.
- **Independence.** Integers only. No code shared with `experimental/sipp-routing` (the router), Richard's F-3.1 deadline field or Thomas's checkers and generators. It reads only the `INSTANCE` block.
- **Self-check.** Every ROUTE witness is replayed by an independent lattice walker in the same module, and every result is fed to Thomas's checker: Python, and C where it builds.

## Naive baselines (what they get wrong is the informative part)

- **N1, classic time-dependent Dijkstra.** One earliest label per state, waiting assumed allowed everywhere (the FIFO idealisation). At a blocked departure it waits at any node. It can claim routes that need waiting at non-waitable nodes, so it is unsound.
- **N2, earliest label with waiting rules.** One earliest label per state, waiting respected, so a blocked departure at a non-waitable node is a dead end. It can miss routes that need a later arrival, so it is incomplete: false NO_ROUTE or a late T.
- **N3, no acceptance windows.** N1 or X with the destination accepted on first arrival. It can report a T before the destination opens.

For each naive baseline we report the disagreements on the 20 missions and on the 140-request departure sweep, and the **smallest failing instance**. The smallest instance is found by delta-debugging the instance (removing edges, intervals and nodes while the disagreement persists) and by hand-built 3–5 node cases.

## Frozen comparison rules (fixed before running)

1. **Instances.** The 20 frozen native-panel missions, instance bytes produced by F-3.2 at its frozen commit (PR #116 head `a03f218`). The instance sha256 (FORMAT.md identity rule) is recorded per mission. If they are available, the 140 departure-sweep requests are a second, separately reported set.
2. **Reference results.** The recorded SIPP results: 15 ROUTE arrival seconds and 5 NO_ROUTE, per F-3.2 claim 2, read from F-3.2's committed `results/panel_summary_*.json`. No other reference is used for agreement.
3. **Agreement.**
   - Verdicts must be identical, ROUTE or NO_ROUTE.
   - For ROUTE, `T` must be equal to the second.
   - Any difference is a disagreement to be explained, never tolerated: an instance error, a baseline bug, or a router discrepancy, in that order of suspicion.
   - Witness acceptance by Thomas's checker is reported separately.
4. **Cost.**
   - Wall time and peak RSS per mission, each solver in a fresh process on the same host, single thread.
   - Instance parse time is reported separately from search time.
   - Comparators: the router (`run_panel.py`'s SIPP search on the same mission) and Richard's F-3.1 field, using their own commands.
   - Timings are host-specific. The median of 3 runs is reported, and no speed claim is made across hosts.
5. **Naive baselines.** Disagreement counts per class (unsound ROUTE, false NO_ROUTE, late T, early T) and the smallest failing example per baseline. Each smallest example is committed as a `.wfgc` instance with Thomas's checker verdict on the exact baseline's answer.
6. **Second baseline.** A published exact method for time-dependent shortest paths with waiting restrictions, requested from Sofia: for example Orda & Rom-type waiting-policy results, or an exact resource-constrained / time-expanded formulation. It is matched under the same rules if one is identified and feasible.
7. **No retuning.** Rules 1–5 are fixed by this commit. Any change is a new dated section, and results are reported under both the old and the new rule.

## Not in scope

Full-policy obligations (radiation, peak, dose); fire-model or scenario construction; any change to router code.

## Dated addition, 2026-11-12 (after the first panel run at 676fc721; Iris's critique, Sofia's search)

Rules 1–5 above are unchanged and results under them stay reported as they are. Added, not replacing:

- **Scope sentence, next to every count.** All agreement counts are for the **contact relaxation** (O2). Equality with
  the router's full-policy verdicts holds only under the dose and peak precondition that Richard checks per request.
- **F-BASE-TEN, a non-interval baseline** (`fbase_ten.py`). Explicit integer-tick time-expanded network (Cai, Kloks &
  Wong 1997; Zeitz 2023; recommended by Sofia), one node per (state, second), arcs for legal moves only, searched by a
  third-party routine (`scipy.sparse.csgraph.breadth_first_order`). Own tokenizer, no interval reasoning, no code
  from `fbase.py`. It runs on every mission whose arc count fits the host memory budget; the others are listed with
  their size. Same agreement rule (3); witnesses checked by `check_py.py`.
- **References.** In addition to F-3.2's panel summary, compare with the frozen published arrival seconds (source to
  be confirmed by Iris), and record the chain.
- **More instances.** Leo's F-DYN packets and the pessimistic unknown-cell instances, through the same `.wfgc`
  INSTANCE format, for all solvers incl. N1–N3 (the naive-baseline counts there measure what interval labels buy).
- **Timing like for like.** Search time only for every solver (baseline, router, Richard's field), same host;
  instance build/parse time reported once, separately. For F-BASE-TEN, graph construction is reported with search
  (it is the method), and separately once instrumented.

## Dated addition, 2026-11-12 (b): Richard's F-3.1 field timing (rule fixed before the run)

- **Command.** Richard's own, unchanged: branch `claude/f31-deadline-field` at 25352cad, run as
  `python3 -m deadline_field.mission_timing --repeat 3` in `research/harness-2026-11/F-3.1`, on the same host as
  the F-BASE runs. Report his `build_s` and the median of his `search_s` per mission.
- **Not like for like.** One F-3.1 search returns the whole feasible departure set over [0, H] for the mission's
  first destination. Its certificate rule is the router rule OR the closed whole-road rule, and it covers the contact
  field only. Its time is therefore reported **beside** the single-departure searches, never as a ratio to them.
- **Consistency check, fixed now.** For each mission, the mission's departure second should be in F-3.1's feasible
  set exactly when the recorded SIPP result is ROUTE. Any mismatch is reported and explained (rule difference,
  destination choice, or a bug), never tolerated. No timing pass rule.

## Dated addition, 2026-11-12 (c): F-DYN instances (sample and rules fixed before any packet is built)

**Source.**
- Leo's `MANIFEST_v3_3.json` (sha aaed2402…) on leo/f-c1-see-before-leave at 93731885 or later.
- Requests come from Leo's `fdyn/requests.py` (20b29ce), and `INSTANCE.json` from `fdyn/instance.py`.
- Each manifest `cmd` is run as an argv list.
- Only the **kriged_mean** and **firms_early** variants are used (orchestrator). envelope and envelope_burnset are
  excluded: their arrays currently do not match HAZARD (Thomas, Mira, Nora; fix pending), and envelope_burnset is
  uninformative on Uiseong.
- Each entry's `soundness` label is carried verbatim. kriged_mean is a scenario; firms_early is "bracket-start, NOT a
  lower bound".

**Sample, fixed now.**
- Packets: the **6 recorded starts** (Uiseong 20250323T01, 20250324T09, 20250325T17; Yeongdeok 20250325T19,
  20250325T23, 20250326T08) × horizons {5 h, 8 h} × {kriged_mean, firms_early}, which is 24 packets.
- Requests per packet: origins sorted by `origin_id`, every 10th taken (index 0, 10, 20, …), × departures {0 s,
  7200 s}. These are the departures Thomas used, and both are in `depart_offsets_s`. Each request keeps all its
  destinations as written.
- A packet that fails to build, or exceeds memory on this host (15 GiB), is listed with its reason, never replaced.

**Pipeline per request.**
1. Thomas's `frontend.build_instance` (F-3.2 code at a03f218, unchanged) builds the router's instance, then
   `generate.certify` gives the SIPP claim, T and a .wfgc bundle.
2. The bundle's INSTANCE block goes to F-BASE exact, N1, N2 and N3.
3. The exact witness is spliced into the bundle and checked by `check_py.py`.
4. **F-BASE-TEN is not run.** At 5–8 h the network has about 5e8–3e9 nodes, beyond this host. This is stated, not
   attempted.

**Rules.**
- Agreement (rule 3): exact versus SIPP, identical verdict and arrival second. **Any disagreement is reported and
  explained, never tolerated.**
- Naive baselines (rule 5): counts per class (unsound ROUTE, false NO_ROUTE, late T, early T), per variant and
  soundness label, and per horizon.
- The `mechanism.py` ablation (no_WB, all_wait, no_AC) is applied to every naive failure, and is counterfactual as
  before.
- Cost: build, parse and search times reported, host-specific, with no speed claim.
- Scope sentence: contact relaxation only; full-policy equality only under the dose/peak precondition.
- **A smoke run** on one packet with two requests, to check the plumbing, is allowed before the main run. Its
  outputs are discarded and not reported as results.

## Dated addition, 2026-11-12 (d): static-snapshot baselines S1/S2 (rule fixed before any S1/S2 run)

Approved by the orchestrator, 16:01 UTC, for the external review's dynamic benchmark. The F-DYN N1–N3 run under (c)
is not altered. **None of N1–N3 is S1 or S2**: all of them use the full time-varying blocks.

**Instances and requests.**
- The same as rule (c): 24 packets, every 10th origin × {0, 7200}.
- Each O2 instance is regenerated with Thomas's `build_instance` from the same request and packet. Its
  `instance_sha256` must equal the one recorded by the (c) run, or the request is reported and skipped.

**Hazard readings.**
- **No re-entry (default).** This is Richard's definition (F-3.1 MULTIHOUR_HEADLINE_RULE.md @ 53def3b §1): a
  cell-level closure, where every cell is closed from its birth b to the horizon, and edge blocks are derived after.
- Implementation on the O2 instance: EB_j := [min EB_j, H] and WB_n := [min WB_n, H] (`fbase_static.no_reentry`).
- Equivalence argument: under cell-level closure, each edge's blocked start set is the suffix [s_j, H], where s_j is
  the first start that meets any of its cells at or after birth. Over the same chord pieces (and the union over
  members), that is exactly the minimum of the as-built EB_j. Richard states the same in his message of 16:01 UTC.
- The O2 instance uses the ROUTER rule. Richard's CERT adds the closed-footprint rule, so these numbers are for the
  router-rule relaxation, as stated.
- **Reopening (labelled variant).** The O2 blocks as built from ContactModel flame intervals.

**Baselines** (`fbase_static.py`, 5f7b2249). All three share the same states, turns, durations, waitable set and
acceptance windows.
- S1: edge j is fully blocked iff dep ∈ EB_j; waiting at n is forbidden iff dep ∈ WB_n.
- S2: edge j is fully blocked iff EB_j meets [dep, H]; waiting at n is forbidden iff WB_n meets [dep, H].
- Each static instance is solved exactly. An S1 ROUTE witness is replayed on the true instance of the same reading.

**Headline columns**, per region × horizon × variant × reading, with counts and rates:
- (i) **S1 returns a route the exact field rejects**: the exact result is NO_ROUTE, or the S1 witness fails replay.
  Denominator: all requests.
- (ii) **S2 refuses a request the exact field resolves**: S2 gives NO_ROUTE while exact gives ROUTE. Denominator:
  requests where exact gives ROUTE.
- Also reported: exact verdict counts per reading; the S2 arrival delay (T_S2 − T_exact) where both route; and the
  share of S1 routes that replay but arrive at a different T.
- No pass/fail. Any change is a new dated section.

## Dated addition, 2026-11-12 (e): S3, a re-planning snapshot baseline (rule fixed before any S3 run)

Approved by the orchestrator, 16:16 UTC. Verifier: Nora. Requests, instances, hazard readings (no re-entry default,
reopening labelled) and sha checks are exactly as in (d).

**S3(Δ), Δ ∈ {10 min, 30 min, 60 min}** (`fbase_static.solve_s3`). The vehicle re-plans on a refreshed S1 snapshot.
1. **Initial plan.** At (s0, dep), plan on the S1 snapshot taken at the current second t: edge j fully blocked iff
   t ∈ EB_j; waiting at n forbidden iff t ∈ WB_n. Plan from the current state s and time t, using the same exact
   solver as S1/S2. Next re-plan time = t + Δ.
2. **Execution.** Execute the plan's legs in order against the **time-dependent model** (the true instance of the
   same reading).
   - A leg that is illegal there is a **VIOLATION**: an EDGE departing at a ∈ EB_j, or a WAIT starting at a ∈ WB_n.
     The job ends there.
3. **Re-planning.** Re-plan at the first completed EDGE leg whose arrival is at or after the next re-plan time.
   - The vehicle is at an admitted state there, so the start-goal semantics are exact.
   - It plans again from (current state, current second) on a fresh S1 snapshot, and the re-plan time advances by Δ.
4. **Outcomes.**
   - The goal is reached when an executed EDGE arrival lands in AC of its head (ROUTE, with that T).
   - A snapshot plan that returns NO_ROUTE at any re-plan ends the job as REFUSED.
   - Unresolved after 10,000 re-plans, or a planner exception, is counted separately as UNRESOLVED.

**Columns**, per region × horizon × variant × reading × Δ. Rates are over **all jobs**; unresolved jobs are counted
separately and excluded from no rate's numerator silently.
- (i) The share of jobs where S3 enters a blocked edge or wait: a VIOLATION, **relative to the time-dependent model**.
- (ii) The share of jobs where S3 REFUSES while exact gives ROUTE.
- Also: the share where S3 reaches the goal legally, and its T minus the exact T.
- Wording in all text: "relative to the time-dependent model".
- Tests: S3 with Δ ≥ H matches executing S1's single plan; every legal S3 ROUTE replays on the true instance.

## Dated addition, 2026-11-12 (f): no-re-entry counts of (d)/(e) WITHDRAWN; no-re-entry instances rebuilt from the packet (rule fixed before any re-run)

Orchestrator ruling of 19:24 UTC, on Nora's defect report (F-BASE/RESULTS.md, defect section at a4e28f0b).

**Withdrawn, not replaced silently.**
- Every `no_reentry` count of (d) S1/S2 (commit 553704ea: RESULTS_fdyn_static.json, fdyn_d/) and of (e) S3 (commit
  6cd2019a: RESULTS_fdyn_s3.json, fdyn_e/) is withdrawn, at both departures. The headline totals mix the departures,
  so none of them stands.
- The (d) equivalence argument ("min of as-built EB_j") is withdrawn too. `build_instance` clips edge blocks to
  [max(dep, ·), H] and drops empty ones, so the argument holds only for dep = 0.
- `fbase_static.no_reentry` is retired. It is kept in the file for the record and is not called by any runner.
- The `reopening` columns of (d)/(e) are not withdrawn; they are built from the as-built packet with no transform.
  The files stay in the repository unchanged; this section is the withdrawal notice.

**Construction (replaces the transform).**
- A no-re-entry O2 instance is built by the unchanged `build_instance(graph, request_NR, ContactModel.from_packet(P_NR))`,
  where P_NR is the no-re-entry packet for the same (region, start, H, variant). Blocks are never transformed after
  instance construction.
- request_NR is the (c) request (same origin, departure, destinations, horizon, limits), with each member-id key in
  `budgets.dose` and `incurred` replaced by the P_NR member id at the same member index. Nothing else changes. The
  runner asserts that the two requests differ only in those keys.
- The instance sha is recorded. For no-re-entry it is no longer compared with (c); it is compared with Nora's
  independent build (acceptance below).

**Readings.**
- **no_reentry/2** (manifest v3.7; cells burned out before the start are also closed on [0, H)) is the default once
  Nora passes v3.7. The (d)/(e) re-runs are repeated on /2 then.
- **no_reentry/1** (manifest v3.6 @ ff3c031c, NOREENTRY_RULE.md; cells burned out before the start stay open) may be
  run meanwhile, ONLY as a labelled variant: "no_reentry/1 (labelled variant; not the default)".
- Packets are built with Leo's `fdyn/build.py --no-reentry` exactly as in the manifest entry's cmd. The HAZARD sha256
  of each built packet is recorded and compared with the manifest/BUILD_SUMMARY where one is listed.
- Baselines, columns, Δ and the waitable-rule sentence are as in (d)/(e). Every no-re-entry count carries its version
  label.

**Acceptance, stated before any re-run.**
1. **Regression test (Nora's counter-example).** UA, start 20250325T170000Z, h5, kriged_mean, origin
   osm_node_415158323. Under no_reentry/1:
   - dep 7200: exact is NO_ROUTE, S1 is NO_ROUTE, S2 is NO_ROUTE. The instance blocks edges 152, 153 and 154 at
     departure 7200.
   - dep 0: exact is ROUTE 259, S1 is ROUTE 259, S2 is NO_ROUTE.
   These values are Nora's, from nora_nr_d.py.
2. **Instance equality.** On Nora's sampled requests at BOTH departures, the instance equals the one built by her
   nora_nr_o2.py from the same packet after clipping to usable starts (a + D_j ≤ H; waits a ≤ H − 1). Exact/S1/S2
   must also be equal (nora_nr_d.py).
3. **Signature check.** At dep 7200, the no_reentry/1 verdicts are reported next to reopening. Nothing is asserted;
   this is the count that exposed the defect.

## Dated addition, 2026-11-13 (g): "waiting allowed everywhere" sensitivity row for (d)/(e)/(f) (rule fixed before any code or run)

Orchestrator decision on the owner's delegation, 13 Nov (relayed by Richard):
- Waiting only at graph dead-end nodes stays the documented default.
- "Waiting allowed everywhere" is ALWAYS reported as a labelled sensitivity row.
- No verified result changes.

**Sensitivity reading.**
- The same O2 instances as the verified runs:
  - reopening: built from the (c) packet and request, instance sha equal to (c);
  - no_reentry/1: built from the NR packet per (f), instance sha equal to the (f) row.
- Then `waitable := all nodes`. This is `ablate(inst, "all_wait")` as in summarize_fdyn.py, verbatim.
- Wait blocks (WB), edge blocks, acceptance windows, forbidden turns and durations are unchanged. A node that is
  burning still cannot be waited at.
- Solved for exact, S1 (+ replay), S2 and S3(600/1800/3600), using the same code as (d)/(e)/(f).

**Columns.**
- The columns of (d) and (e), for each reading.
- Also, per request, the verdict change against the default (dead-end) waitable rule: NO_ROUTE → ROUTE, ROUTE →
  NO_ROUTE (expected 0, because adding wait options can only enlarge the feasible set), and the T change where both route.
- **Label on every row:** "SENSITIVITY: waiting allowed at every node (not the documented default; default = graph
  dead ends only)".
- No pass/fail. The default rows are not changed.
- The (c) F-DYN fact is reported beside it, from verified rows: all 14 (c) NO_ROUTE requests are ROUTE under N1, the
  all-waitable relaxation (fdyn_c, 14/14).

**Acceptance (stated before running).**
1. The instance sha before the ablation equals the verified row's, on every request.
2. There are 0 ROUTE → NO_ROUTE changes for exact. A nonzero count is reported as a finding and stops the write-up
   until it is explained.
