# F-BASE results: 20 frozen panel missions (rules: DESIGN.md, frozen at 85747d3c)

**Scope (applies to every count below):** contact relaxation (O2) only. Equality with the router's full-policy
verdicts holds only under the dose and peak precondition that Richard checks per request.

Command (host: this container, py3.12, single thread):

    python research/harness-2026-11/F-BASE/run_panel_fbase.py --bundles <F-3.2 run_panel output at a03f218> \
        --f32 <F-3.2 dir at a03f218> --summary <F-3.2 results/panel_summary_py312.json>

Raw output: `RESULTS_panel.json`. Bundles were regenerated with F-3.2's frozen `run_panel.py` at a03f218; all 20
instance sha256 values equal F-3.2's recorded `instance_sha256`.

## Agreement with recorded SIPP (rule 3: exact verdict, T to the second)

| solver | agree | disagreements |
|---|---|---|
| exact (F-BASE-X) | **20/20** | none |
| N1 earliest label, waiting everywhere | 20/20 | none on this panel (its unsound case exists, see tests) |
| N2 earliest label, waiting rules | 15/20 | 4 false NO_ROUTE, 1 late T (1294 vs 1270) |
| N3 no acceptance windows | 14/20 | 5 early T, 1 unsound ROUTE (T=2921 on a recorded NO_ROUTE) |

- N2 failures are all `FW*` missions: 2023-04-02 FW2, 2022-06-01 FW1 (late), 2025-03-25 FW1, 2022-03-04 FW2, 2025-03-26 FW1.
- N3 failures: the same five FW missions (early T: 968, 1032, 573, 1400, 776) plus 2025-03-25T19 FD1 (claims 2921).

### Which rule each failure trips (`mechanism.py`, `RESULTS_mechanism.json`)

Ablation, comparing each naive solver with the exact solver on the same ablated instance: remove all blocked
wait starts (`no_WB`), make every node waitable (`all_wait`), or widen acceptance windows to `[dep, H]` (`no_AC`).

| failures | fixed by no_WB | fixed by all_wait | fixed by no_AC |
|---|---|---|---|
| N2, 5 missions | 0/5 | 0/5 | **5/5** |
| N3, 6 missions | 0/6 | 0/6 | **6/6** |

All 11 failures trip **one rule: the destination acceptance window.** The ablation is counterfactual: widening AC
changes the instance and its exact answer too (for example FW2 1459 → 968). It shows which rule the naive solvers
violate, not that they would recover the original answers. Non-waitable nodes and blocked wait starts
trip none of them on this panel.
- In the five FW missions, the window opens later than the earliest possible arrival, at exactly the exact T
  (`[1459, 3480]`, `[1270, …]`, `[1064, …]`, `[1655, …]`, `[896, …]`).
  - N2 extends only the earliest departure of each state, so it misses the later admitted arrival into the window:
    four false NO_ROUTE and one late T.
  - N3 reports the earliest arrival, before the window opens.
- 2025-03-25T19 FD1: the window `[0, 2861]` closes before N3's arrival at 2921, so N3 claims an unsound route.
- N1 agrees 20/20 only because it lets an arrival wait at the destination until the window opens, which the
  admission rule does not allow. Its agreement on this panel is not evidence that it is sound: the panel has no case where waiting at a non-waitable
  node matters.

## Frozen published independent rows (Main 2a751631, `research/routing/INDEPENDENT_ROWS.csv`)

`compare_independent.py`, `RESULTS_independent.json`. Column meanings are as stated in INDEPENDENT_REPORT.v1.md.
- RDA_CAND: all 20 missions, both repetitions (40 rows), agree in verdict and arrival second (15 routes, 5 refusals).
  These are the same 20 instances as the panel, so this is agreement with another arm's recorded results, not 40
  independent instances.
- RDA_BASE: 26/26 resolved rows agree. The 14 unresolved rows (8 TIMEOUT, 6 centre-only refusals) have nothing to compare.

## Witnesses

All 15 exact ROUTE witnesses replay in `fbase.replay`. Spliced into the bundle in place of F-3.2's witness, each is
`ACCEPT ROUTE T` under F-3.2's `check_py.py` (15/15). The C checker was not built; not run.

## Cost (rule 4, this host only; median of 3 fresh processes; peak RSS = max over the 3)

Exact search 0.00–3.26 s, peak RSS 20–227 MiB; parse 0.00–0.19 s. Largest: 2025-03-25T19 FD1 (NO_ROUTE) 3.26 s / 227 MiB.
Per-mission figures are in `RESULTS_panel.json`. Verdict and T were identical across the 3 repeats for every solver.

## F-BASE-TEN: non-interval baseline (dated addition 2026-11-12; `run_panel_ten.py`, `RESULTS_panel_ten.json`)

This baseline builds an explicit time-expanded network, one node per (state, second), and searches it with
`scipy.sparse.csgraph.breadth_first_order` (scipy 1.13.1). It uses its own tokenizer and no interval code.
Test: it equals the exact solver and brute force on 1,500 random instances, and its witnesses replay.
Host budget: 2e8 arcs (about 52 MiB per 10^6 arcs, 15 GiB host). Median of 3 fresh processes; graph build is included in the time.

- **16/16 run missions agree** in verdict and arrival second. All 12 route witnesses are `ACCEPT ROUTE T` under
  `check_py.py`. Results were identical across repeats.
- Sizes and cost of the missions that ran: 5.4e6–1.6e8 nodes, 0.5–16.9 s, peak RSS 0.36–9.4 GiB.
- **Not run (size, not a failure):** 2025-03-25T19 FD1, 2025-03-25T19 FX2 and 2025-03-25T23 FL2 (4.03e8 nodes,
  4.51e8 arcs), and 2025-03-26T08 FW1 (3.69e8 nodes, 4.14e8 arcs). At the measured rate these need about 21–23 GiB.

## Router search-only timing (rule 4 + dated like-for-like section; `run_router_timing.py`, `RESULTS_router_timing.json`)

The router is F-3.2's code at a03f218, unchanged: packet load plus `frontend.build_instance` is timed as build, and
`sipp.solve` is timed as search. The verdict uses F-3.2's own FOUND/EXHAUSTED mapping. Each mission runs in a fresh
process, median of 3, on the same host as the F-BASE runs.

- **Agreement:** the router reproduces the recorded verdict and arrival second on 20/20 missions, with results
  consistent across repeats.
- **Search time:** router 0.001–3.60 s per mission (5.27 s summed over the panel). The F-BASE exact baseline takes
  0.003–3.26 s (14.53 s summed). The per-mission ratio exact/router has median 4.3 and ranges from 0.2 to 98: the
  router is faster on 13 missions and slower on 7.
- **Router build** (packet load and instance construction): 0.03–4.1 s per mission. **F-BASE parse** of the integer
  INSTANCE block: 0.00–0.19 s. These differ in kind: the router builds from hazard packets, while F-BASE reads the
  already-derived O2 integer instance.
- **Router peak RSS:** 84–409 MiB, including the packet and contact model. F-BASE exact: 20–227 MiB.
- **Caveats.** The two searches run on different representations of the same contact relaxation: SIPP's native
  instance versus the O2 integer instance. All timings are host-specific. **No speed claim** is made beyond these
  measured numbers, and no claim across hosts. Richard's F-3.1 field is timed below.

## Richard's F-3.1 field (dated rule 2026-11-12 (b); `RESULTS_f31_timing.json`)

Richard's own command, unchanged: `claude/f31-deadline-field` at 25352cad, `python -m deadline_field.mission_timing
--repeat 3`, on the same host. The frozen routing inputs are shared with the F-3.2 worktree.

- **Consistency: 20/20.** Each mission's departure second is in F-3.1's feasible set exactly when the recorded SIPP
  result is ROUTE: 15 routes are inside the set and 5 refusals have an empty set.
- **Cost:** build 0.04–3.40 s per mission. Search, median of 3, 0.011–2.88 s per mission (13.05 s summed).
- **Not like for like.** One F-3.1 search returns the whole feasible departure set over [0, H], for example
  [0, 3112] for 2023-04-02T14 FW2. The router and F-BASE answer one departure each. The time is reported beside
  theirs and no ratio is formed. Answering every departure second with the router would take up to H + 1
  single-departure searches.

## F-DYN v3.3 multi-hour instances (dated rule (c); `run_fdyn.py`, `summarize_fdyn.py`, `RESULTS_fdyn.json`, `fdyn_c/`)

**Scope:** contact relaxation only; full-policy equality only under the per-request dose and peak precondition.

**Sample** (fixed before any packet was built):
- 24 packets: Leo MANIFEST_v3_3 (aaed2402…), the 6 recorded starts × {5 h, 8 h} × {kriged_mean, firms_early}. All 24
  built.
- The kriged_mean and firms_early entries are identical in content in v3.4.
- Requests come from Leo's `fdyn/requests.py` (20b29ce; round-trip tests at ba69e8d): every 10th origin × departures
  {0, 7200}, which gives 432 requests.
- Soundness labels, carried verbatim: kriged_mean is "kriged mean (not a bound …)"; firms_early is "bracket-start, NOT
  a lower bound".

**Agreement:**
- Exact equals SIPP (Thomas's build_instance + certify, F-3.2 at a03f218) in verdict and arrival second on **432/432**
  requests, with 0 unresolved.
- 418 ROUTE and 14 NO_ROUTE.
- All 418 exact witnesses replay and are `ACCEPT ROUTE T` under check_py.

**Naive baselines**, per region × horizon × variant (out of 54 requests each):

| region, h, variant | N1 unsound ROUTE | N2 false NO_ROUTE | N2 late T | N3 |
|---|---|---|---|---|
| Uiseong h5 firms_early | 2 | 2 | 0 | 0 |
| Uiseong h5 kriged_mean | 2 | 1 | 0 | 0 |
| Uiseong h8 firms_early | 2 | 2 | 0 | 0 |
| Uiseong h8 kriged_mean | 2 | 1 | 0 | 0 |
| Yeongdeok h5 firms_early | 1 | 0 | 1 | 0 |
| Yeongdeok h5 kriged_mean | 2 | 0 | 1 | 0 |
| Yeongdeok h8 firms_early | 1 | 0 | 1 | 0 |
| Yeongdeok h8 kriged_mean | 2 | 0 | 1 | 0 |

- **The 24 failures are only 7 distinct (start, origin, departure, baseline) cases.** The same request fails under
  both horizons and, mostly, both variants.
- N3 never fails, because these requests have destination window [0, H].

**Mechanism** (ablation, counterfactual as before; instances regenerated, sha equal to the (c) record for all 24):
- **All 24 failures (7 distinct cases) are fixed by `all_wait` alone**, while no_WB fixes 0 and no_AC fixes 0.
  - **N1** (5 distinct cases, 14 requests): N1 *is* the all-waitable relaxation by definition, so here `all_wait`
    changes the truth. Exact NO_ROUTE becomes N1's ROUTE and T. **N1 breaks the waiting rule.**
  - **N2** (2 distinct cases, 10 requests): exact is unchanged under `all_wait`, and N2 then agrees. N2 obeys the
    waiting rule, but **its one-earliest-label-per-state dominance fails when waiting is restricted** (Nora).
- This is the opposite of the 1 h panel, where every failure came from the acceptance window. So **N1's 20/20 on the
  panel was not soundness**: on F-DYN it returns 14 unsound routes out of 432 requests (5 of 7 distinct cases).
- **The NO_ROUTE verdicts hinge on the router's waitable set, not on fire geometry alone** (Nora).
  - Every exact NO_ROUTE in the sample (14 requests, 5 distinct cases) becomes ROUTE when all nodes are made
    waitable.
  - Only 554 of 23,158 nodes (Uiseong) and 1,527 of 56,369 (Yeongdeok) are waitable.
  - These are road-limited relaxation verdicts.
- **Rates:** per request, N1 14/432 and N2 10/432. Per distinct case, failures occur in 7 cases (N1 5, N2 2) out of
  108 distinct (start, origin, departure) triples (432 requests = 108 × 2 horizons × 2 variants).

**Rule before run:** established by **commit order only**. Rule (c) was committed at 13:53 (f3f0734d), the runner at
13:57 (8b99a06c) and the results at 16:14 (6f0925fa). The per-request records carry no timestamps; runs from S3
onward stamp started_utc in their header rows.

**Where the waitable rule comes from:** [pending one line each from Richard and Thomas on which OSM tags or which file
define the waitable nodes]. Any "routes into fire" or "no route" headline from this table carries this dependence.

**Verification:** Nora, **PASS WITH NOTES** (ledger row 55).
- She recounted every number and re-ran 6 packets (108 requests, including all 7 distinct failures), which came out
  identical on every request.
- Her ablation also gives 7/7 fixed by all_wait.
- Her notes 1–4 are applied: header rows of later runs carry started_utc; the mechanism wording above; the
  waitable-set caveat; rates per distinct case.

**Not run:** F-BASE-TEN, which at 5–8 h is beyond this host, as declared.

**Cost on this host:** exact search median 0.03 s (max 3.4 s); SIPP certify median 0.24 s (max 32.5 s); build median
4.4 s (max 24.5 s). Host-specific.

## Verification

Owen, eec16027 (covers 676fc721): **PASS WITH NOTES**. He reran all four commands and the tests, and every non-timing
field equals the committed outputs. His own brute-force time-expanded search, sharing no code, equals solve_exact and
solve_ten on 4,300 random instances. His wording notes are applied above. No speed claim is made, and the C checker
was not built.

Owen, router timing e20a0e08: **PASS WITH NOTES**.
- Verdict and T equal on 20/20, consistent across repeats.
- His search times were 0.001–2.60 s (3.97 s summed), and his exact/router ratio was median 4.2 with the same
  13/7 split.
- Agreement, consistency and order of magnitude are verified. Timings are host-specific. Keep the
  "different representations" caveat.

Owen, F-3.1 field timing a2f39381: **PASS WITH NOTES**.
- Feasible sets equal on 20/20.
- He recomputed departure membership independently and found 20/20 consistent.
- Search was 11.2 s summed on his host.
- No ratio against the router or exact baseline is formed.

## Not done yet

- 140-request departure sweep; delta-debug smallest failing panel-derived instances (hand-built 2–3 node cases are in tests).
- Second published baseline (Sofia).
