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
