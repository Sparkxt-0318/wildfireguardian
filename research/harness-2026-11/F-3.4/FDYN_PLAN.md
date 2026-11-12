# F-3.4 multi-hour profile and F-4.2 margins on F-DYN v3: fixed request set

Written before any F-DYN routing run (12 Nov, ~10:10 UTC). F-DYN v3 is Leo's `7eb3691` on
`leo/f-c1-see-before-leave`, passed by Nora with notes.

## Packets (4)

Both recorded starts that are also rule starts, 5 h horizon, central member, Q = 300, full KFS_01 grid, interim
graph:

| Region | Start (UTC) | Variants |
|---|---|---|
| uiseong_andong_2025 | 20250325T170000Z | kriged_mean, firms_early |
| yeongdeok_2025 | 20250325T230000Z | kriged_mean, firms_early |

Each packet is built by its exact `MANIFEST_v3.json` command and its hashes are recorded. The envelope variant is
excluded: it has a single implementation and is not independently checked.

## Requests (12)

Per region, taken from `INSTANCE.json` (`fdyn/instance.py`): the **first 3 places in file order**, departure 0, each
place's **first** listed destination, with the instance's limits (10 kW/m², 100 kJ/m²), 120 s stay and destination
window [0, H]. That gives 3 requests × 2 variants × 2 regions = 12. The same 12 are used for every budget and for the
margins.

## Runs

- **Profile.** Instrumented (`run_profile.py`-style job through the unchanged controller, request-window kit,
  `RDA_CAND`), cold preparation, sequential, quiet host. Budgets: **30 s** (the evaluated budget, outcome record only),
  then **300 s** and **900 s** (extended, reported separately), 1 repetition each. Memory guard 3,072 MiB as in the kit.
  If a run stops on the memory guard, it is repeated once with the guard raised to 12,288 MiB (host has 15 GiB), to
  locate the phase that grows. That repeat is labelled non-evaluated.
- **Reported per run.** Outcome; wall time by phase; per-phase RSS high-water; family peak RSS; host (stated; timings
  are host-relative).
- **Margins.** `clearance.py` on the same 12 requests: published-route clearance (where a route is published), margin
  bracket, ≤ +60/+300/+600 s trade-off, and crop/domain flag.
- **Carried notes (Nora).** Roads are the clipped recorded windows, so 45% of burned cells have no modelled roads.
  Dose binds over 5–8 h. This is a scenario, not what happened.

## Label correction (Leo, c79c510, received after the plan was fixed)

`firms_early` uses the FIRMS bracket start, which is **not a lower bound** on arrival. It stays in the fixed set,
because timing results are unaffected. Every result on it is labelled **"firms bracket-start (not a lower bound)"** and
is never described as early or conservative. Leo's sound envelope variant (`envelope_sound`) is not part of this plan.

## Version update (Leo 11:43 UTC; orchestrator decision): F-DYN v3.1

The plan runs on **v3.1**: `MANIFEST_v3_1.json` (sha `1c2e73db…`) at `3f1fa15`, with packets under
`_data/packets_v31/`. The 4 packets and 12 requests are unchanged in definition. The v3.1 data changes touch only the
23T23, 24T02 and 24T05 starts, not this plan's 0325T17 and 0325T23 starts; identity digests change. Each manifest
command is run as an argv list. Every packet hash is recorded in `fdyn_prepare.log`.

## Amendment A1 — 12 Nov 2026, committed 13:00:28 UTC (033e7f0) before the run it describes (run started ~13:01 UTC)

**Deviation 1: the 900 s / 12,288 MiB controller-only repeat was stopped** at 12:59:06 UTC, after 1 of 12 rows
(orchestrator decision). It cannot show search behaviour, for the reason below. The one completed row (Uiseong
kriged …323: UNRESOLVED, 151.9 s, 9,766 MiB) is kept and labelled "stopped repeat".

**Why.** The plan's memory repeat raised only the controller's guard. The kit's solver has a second memory gate,
which the plan did not cover: `phaseB/road_core.py:751-757`, the same code as `routing/core.py:605-611` in the
routing package. Every 64 expansions it compares the **process-lifetime maximum RSS** (`getrusage ru_maxrss`) with
`limits.rss_limit_mb`. The default is 3,072 because the requests do not set it.

On these packets, bound construction has already raised the lifetime maximum above 3 GiB, so the LO and HI stages
stop with `RSS_LIMIT` at 0 expansions. In the 300 s / 12,288 MiB repeat, 9 of 9 unresolved requests did this.

**Deviation 2: one more repeat.** It is labelled **non-evaluated, amendment A1**.
- The request carries `limits.rss_limit_mb = 12288`, a field the kit validates (`routing/validation.py:421`).
- So both gates are at 12,288 MiB: controller `--memory-guard-mib 12288`, and the solver via the request.
- Budget 300 s; the same 12 requests; one repetition; quiet host.
- Command: `fdyn_profile.py --budget 300 --memory-guard-mib 12288 --rss-limit-mb 12288`, output `fdyn_b300_g12k_rss12k`.

**Reported, descriptive only (no pass/fail threshold, per the orchestrator):** per request,
- outcome and terminal reason;
- per stage (Z, LO, LO2, HI): wall cap, elapsed, status, reason, labels and expansions;
- complete wall;
- family peak RSS, and resident vs lifetime-peak RSS at the end of the bound model, the EA bound and search.

Also reported beside it: the count of the 9 requests unresolved in the 300 s / 12,288 MiB repeat that reach
FEASIBLE or OPTIMUM_PROVEN with a completed whole-road check (Iris's question), as a number, not a pass rule.

**Findings recorded with this amendment (from existing rows; measured).**
1. **The gate measures lifetime peak, not current use.** Any large transient precompute therefore disables every
   later search stage for the rest of the process, even when resident memory has fallen back. On Uiseong:
   - RoadBoundModel construction peaks at 9.0–9.5 GiB, but resident RSS at its end is 0.40 GiB;
   - resident RSS at the end of `road_core.solve` is 2.09 GiB, below 3 GiB;
   - search was nevertheless stopped by the gate.
   On Yeongdeok the EarliestArrivalBound stays resident (4.4 GiB at its end and during search), so that memory is
   genuinely held.
2. **The terminal reason under-reports memory.** Gate-stopped runs end as `UNRESOLVED / SEARCH_TIMEOUT`, with
   search status `TIMEOUT`. `RSS_LIMIT` appears only in the per-stage records of `SEARCH_RESULT.json`. This is a
   reporting defect in the kit's terminal reason (observation; the frozen kit is not changed).
3. **Open item: Z overran its 6 s cap on Uiseong** (Z elapsed 20.0–22.4 s, wall cap 6 s). Not investigated.
4. **The 2 feasible results at 900 s / 3,072 MiB** (Yeongdeok firms_early, origins …207 and …168) came from **Z**:
   - Z timed out at its 6 s cap with a checked incumbent (`WALL_CLOCK_AFTER_CHECK`);
   - the whole-road check certified that incumbent, and it was published (`WHOLE_ROAD_CERTIFIED_NO_OPTIMALITY_CLAIM`);
   - so the EA bound was never built and the peak stayed at 2.3 GiB.
   At 300 s / 3,072 MiB, the same requests reached EA, which needs 4.4 GiB, and were stopped by the guard. The
   difference is whether Z had a certified incumbent when its fixed 6 s cap expired. That is a run-to-run timing
   effect at the Z cap, not an effect of the larger budget (hypothesis; 1 repetition each).

## Amendment A2: the precompute counterfactual, committed before it runs

This aligns with Iris and the orchestrator (12:58–12:59 UTC). Run (i) is the A1 run above, started about 13:01 UTC.
**Run (ii) is added here and has not started.**

**(ii) 450 s budget, both gates at 12,288 MiB.**
- Setup: controller `--memory-guard-mib 12288`, request `limits.rss_limit_mb = 12288`.
- Requests: only the 9 left UNRESOLVED in the 300 s / 12,288 MiB controller-only repeat (`fdyn_b300_g12k`):
  - Uiseong kriged and firms, origins …323 and …324;
  - Yeongdeok kriged, all 3 origins;
  - Yeongdeok firms, origins …166 and …168.
- One repetition. Output `fdyn_b450_g12k_rss12k`. It runs after (i) finishes.
- **Why 450 s.** It is 300 s plus the measured bound time, rounded up. The measured bound time (bound model + EA
  bound) is 104–116 s on Uiseong and 84–96 s on Yeongdeok. So the search sees at least the time it would have if the
  bounds were free.
- **Pass rule (written before running).** Count the requests among the 9 that reach `CHECKED_JOURNEY_FEASIBLE` or
  `CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN` with a completed whole-road check:
  - **0 of 9** → "search is the limit";
  - **≥ 3 of 9** → "precompute is the lever";
  - **1–2 of 9** → inconclusive.
- **Also reported for all 9:** expansions and labels per stage. "0 of 9 with many expansions" and "0 of 9 with few
  expansions" mean different things.

**Statements fixed for the write-up.**
- **Radiation cost at 5 h is unmeasured, not cheap.** In the existing runs, almost no route reached a whole-road
  check (route-check radiation 0.06 s in total).
- **Cache-saving report.** If a bound cache is ever evaluated, the saving is reported separately for the road bound
  model (keyed by forecast and window) and for the EA bound (keyed by forecast and destination set). A regression
  test would check that cached arrays equal freshly built ones (Iris).

## A1 result and deviation 3 — 12 Nov 2026, 13:40 UTC

**Data.** `results/fdyn/fdyn_b300_g12k_rss12k_{ROWS.jsonl.gz,STAGES.txt}`. Run (i): 300 s; controller guard and
solver gate both at 12,288 MiB; non-evaluated; 1 repetition.

**Outcomes (12 requests).**
- **2 CHECKED_JOURNEY_FEASIBLE:** Yeongdeok firms …207 (arrival 59 s) and …168 (arrival 274 s). Both come from a Z
  incumbent with a completed check; the EA bound was not built and the peak was 2.3 GiB.
- **2 AT_ISSUE_FAILURE:** Uiseong origin …334, in both variants.
- **4 Uiseong UNRESOLVED/LATE_RESULT** at about 300 s.
  - Time to the stage checkpoints: bound model at 72–90 s, then Z at 93–112 s (Z overran its 6 s cap: 21–23 s),
    then the EA bound at 149–167 s.
  - The search did not return before the deadline, so there are no per-stage expansions.
  - These are **time-limited**; memory was not the limit (peak 9.0–9.5 GiB, transient in the bound model).
- **4 Yeongdeok UNRESOLVED/SEARCH_TIMEOUT.** The search succeeds, but every route check is discarded on memory:
  - the per-stage records give LO, LO2 and HI all `CONDITIONAL_OPTIMUM`;
  - labels/expansions are 33/18 (kriged …207, arrival 59), 130/114 (kriged …168, arrival 274) and 1963/1669 (both
    …166 requests, arrival 3953);
  - each whole-road check of those routes returns `UNRESOLVED / RSS_LIMIT`.

**Third gate (not covered by A1 or A2).** `routing_candidate/baseline/hybrid_checker.py:9` fixes `RSS_LIMIT_MB = 3072`.
- At the end of the check (`_finish`, :31-35) it compares the process-lifetime `ru_maxrss` with 3,072 MiB. If above,
  it replaces the completed check result with `UNRESOLVED / RSS_LIMIT` and keeps the original only as a secondary
  result. The adaptive fallback does the same (`adaptive_checker.py:185-186`).
- This gate is a module constant, not a request field. The EA bound holds 4.4 GiB, so on Yeongdeok every route check
  is discarded whatever the request says.
- The kit's terminal decision still reads `SEARCH_TIMEOUT` ("the search stopped at a cap"), although the search
  stages returned conditional optima. This is the same reporting defect as before, now covering the checker gate.
- The secondary (pre-gate) check outcome is not written to RESULT.json, so whether those routes would have certified
  is unknown from the outputs.

**Deviation 3: run (ii), the A2 450 s counterfactual, was STOPPED** at 13:40:12 UTC, about 40 s after it started,
with 0 rows. Its pass rule counts checked results. With the checker gate at 3 GiB, the 5 Yeongdeok requests would
score 0 regardless of search, so "0 of 9 → search is the limit" would be a false conclusion. It is not rerun without
the orchestrator's decision.

## Amendment A3, committed before (a) or (b) starts (orchestrator decision 13:41 UTC)

Both parts are **non-evaluated**.

### (a) Fresh-process re-check of the Yeongdeok witness routes

**Which checks.** A1 left 4 Yeongdeok requests whose LO/LO2/HI routes were discarded by the checker gate. Within each
request, LO, LO2 and HI returned the same route (identical legs). That gives **3 distinct routes and 4
(route, packet) checks**:
- kriged …207: arrival 59, 18 legs;
- kriged …168: arrival 274, 114 legs;
- kriged …166 and firms …166: the same route, arrival 3953, 1669 legs, checked against each packet.

My 13:40 message said "5 routes"; that was wrong — it is 4 checks.

**How.** `F-4.2/fixed_route_check.py` with:
- the unchanged kit checker (`HybridChecker` from the request-window kit queue, as the worker uses it);
- the run's own `ORIGINAL_REQUEST.json`, graph and packet;
- the route legs and destination taken from `RESULT.json rejected_witnesses`;
- one fresh interpreter per check, wall 600 s.

The output also records the checker's `process_lifetime_rss_mb` and `rss_gate_mb`.

**"Would certify" means all three of:**
1. checker status `CERTIFIED_ADMISSIBLE` (the status the worker publishes on);
2. reason not `RSS_LIMIT`, not a wall cap, and not an adaptive-fallback RSS limit;
3. the checker's own measured lifetime RSS ≤ 3,072 MiB, so its gate did not fire.

**Other outcomes:**
- If a check returns `UNRESOLVED` for any other reason, or is refused, that is reported as it is.
- If the fresh process itself exceeds 3,072 MiB, the result is "gate fires even in a fresh process", not a certification.

**Reported per check:** status, reason, contact and radiation status, the largest dose and peak upper-bound share of
budget, elapsed time and lifetime RSS.

### (b) Test copy of the kit with all three gates at 12 GiB, then A2 rerun as pre-registered

**The test kit.**
- A copy of the request-window kit at `scratchpad/window-kit-gate12k`, labelled TEST COPY. It is never the frozen
  kit and never merged into it.
- The only changes allowed are `RSS_LIMIT_MB = 3072 → 12288` in `routing_candidate/baseline/hybrid_checker.py`, and
  the matching constant in `adaptive_checker.py` if it has its own. (It imports `RSS_LIMIT_MB` from
  `hybrid_checker`, so likely nothing changes there.)
- The full diff against the original kit is recorded in `results/fdyn/gate12k_kit.diff`.
- If the worker's module-hash self-check rejects the edited module, that is reported, and nothing else is changed to
  get around it.

**The run.**
- Same as A2: 450 s; controller guard 12,288 MiB; request `limits.rss_limit_mb = 12288`; the same 9 requests; 1 rep.
- Output `fdyn_b450_gate12k`. Same pass rule as A2:
  - **0 of 9** → "search is the limit";
  - **≥ 3 of 9** → "precompute is the lever";
  - **1–2** → inconclusive.
- **Reported:** expansions per stage, check outcomes, wall, peak RSS.

Run order: (a), then (b).

## A3(a) and A3(b) results — 12 Nov 2026, 14:45 UTC

### A3(a): offline re-check, outside the kit

- **What was checked:** 4 witness checks covering 3 distinct routes; one route was checked against both packets.
- **Whole-road checker** (unchanged, byte-identical to the job's `checker_sha256`): 4/4 `CERTIFIED_ADMISSIBLE`.
  Lifetime RSS 411–511 MiB, so the gate was never reached.
- **Independent checker** (`routing.independent` after validation): 4/4 ok, with no error codes.
- **What this shows and does not show:** the routes are **admissible**. Optimality is not re-established; "conditional
  optimum" is the kit's own search label.
- **Margins:** the two checkers agree on the verdict with very different margins.
  - Enclosure: dose ≤ 0.049, peak ≤ 0.054.
  - Cell-binned: dose ≤ 0.0123, peak ≤ 0.0006.
  - The enclosure is the looser bound.
- **Label:** re-checked offline outside the kit; not published by the kit. Counted separately from the kit's 2/12.
- **Files:** `results/fdyn/a3a/` (A3A.jsonl, A3A_INDEPENDENT.jsonl, A3A_HASHES.json).

### A3(b): modified test kit, all three gates at 12 GiB

**Setup.** Test copy `window-kit-gate12k`; the only edit is `hybrid_checker.RSS_LIMIT_MB` (`results/fdyn/gate12k_kit.diff`).
450 s, the 9 requests, 1 repetition. Every row comes from a **modified kit**. They are kept apart from the kit's own
count and from the A3(a) line.

**Pre-registered count: 5 of 9 reach a checked result.** All 5 are Yeongdeok `CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN`:

| Request | Arrival | Wall | LO labels / expansions |
|---|---|---|---|
| kriged …207 | 59 | 156.0 s | 33 / 18 |
| kriged …168 | 274 | 147.7 s | 130 / 114 |
| kriged …166 | 3953 | 219.7 s | 1963 / 1669 |
| firms …168 | 274 | 136.3 s | 130 / 114 |
| firms …166 | 3953 | 208.7 s | 1963 / 1669 |

In each, LO returned a conditional optimum and its check certified it. Peak 4.8 GiB.

**By the A2 rule, ≥ 3 of 9 maps to "precompute is the lever". That reading is NOT supported, and I am not adopting
it:**
- All 5 resolved within 136–220 s. That is less than the 300 s budget, so they did not need the extra 150 s that the
  450 s budget was meant to test.
- What changed them from unresolved (A1, 300 s) to proven is the checker gate, not the time.
- So the rule's question (would precomputing the bounds let search finish?) was not answered for Yeongdeok. Its
  outcome there is decided by memory accounting.
- For Uiseong the answer is 0 of 4.
- The pass rule did not anticipate this confound. The count stands as written, but its interpretation is replaced by
  the per-region statement below.

**Uiseong, 4 requests: all UNRESOLVED / LATE_RESULT at 450.3 s.**
- Bounds are built by about 147–164 s: bound model 67–76 s, EA bound 52–58 s, and Z overran to 20–23 s.
- **LO then ran 246–273 s and returned TIMEOUT**, against a wall cap of about 0.55 × remaining ≈ 160–165 s.
  So LO also overran its cap, by about 80–110 s.
- One request (kriged …324) did not return from LO at all before the deadline.
- HI never ran to completion.
- Labels and expansions for Uiseong are **not recorded**. The worker writes them only in SEARCH_RESULT.json, which a
  deadline stop never writes.
- So Uiseong search cost remains **unmeasured, except that LO did not finish in about 250–270 s with the bounds
  already built**.

**Per-region statement (modified kit, 450 s, 1 rep).**
- **Yeongdeok:** search finishes in ≤ 1,669 expansions. All 5 are proven once the checker's lifetime-peak gate is
  lifted.
- **Uiseong:** the LO search does not finish in about 250–270 s, and the wall caps for Z and LO are not enforced
  promptly. There the search, not only the bounds, is the limit at this budget.

**New open item: the LO wall-cap overrun on Uiseong** (246–273 s elapsed against about a 160 s cap). It adds to the
Z overrun (21–23 s against a 6 s cap).

## Amendment A4: Z-cap reproducibility sizing, committed before it runs (orchestrator decision 14:43 UTC)

**Question.** With identical inputs, how often does the unmodified kit publish from Z (FEASIBLE), and how often does
it go on to the EA bound and stop on the memory guard?

**Requests.** Yeongdeok 0325T23 `firms_early`, origins …11753630207 (Z incumbent arrival 59) and …415158168 (arrival
274).

**Setup.** The **unmodified** request-window kit; controller guard 3,072 MiB; no `rss_limit_mb` in the request; budget
900 s. **10 repetitions per request**, run sequentially (alternating the two requests) on a quiet host. Output
`fdyn_zcap_r{01..10}`.

**Reported per request (descriptive only, no pass/fail):**
- counts of CHECKED_JOURNEY_FEASIBLE / FULL_OPTIMUM_PROVEN, memory-guard stop, and other outcomes;
- per rep: the Z stage status and reason (`WALL_CLOCK_AFTER_CHECK` with an incumbent vs `WALL_CLOCK` without), Z
  elapsed, wall time and family peak RSS.

The 900 s / 3 GiB row from earlier (`fdyn_b900`) is reported beside these but not pooled.

**Label.** Non-evaluated (a sizing of an evaluated-kit behaviour at an extended budget). One host only, so the rates
are specific to this host.
