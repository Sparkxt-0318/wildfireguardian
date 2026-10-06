# Independent adversarial integration review

Date: 2026-10-05. Reviewer owned only `review/`; the coordinator owned production edits. No production edits, road timing, or lock-sensitive workloads were performed by the reviewer.

**Verdict: PASS for the tested finite integration contract.** Preparation remains opt-in. This review does not establish a universal speed-up, thread safety, road tenability, or physical safety. Adoption based on actual lifecycle latency remains the coordinator's benchmark decision.

## Frozen review and execution

The review script and input/source hashes were captured before child evaluation in `review/runs/20261005T073028Z/MANIFEST.json`. Final script SHA-256: `04fff3b8c9bf394fa2eb6ca1995e02b9a793852d310b82dc8aa31488c18a6ed1`. Full child stdout/stderr and every grouped result remain in `/Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_preparation_integration_20261005_v1/review/runs/20261005T073028Z`. `LATEST_RESULTS.json` points to the final result. Run:

```sh
cd /Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_preparation_integration_20261005_v1
python3 -B review/adversarial_review.py
```

The final run passed **39 grouped checks**. Baseline, raw integrated candidate, and prepared integrated candidate run in separate Python processes so package imports cannot contaminate comparison. The test driver takes source hashes and fixture hashes before evaluation. Comparisons preserve all result fields except measured wall time and process RSS; request wall budgets and deterministic search counters remain compared. Initialization is deliberately not benchmarked by this correctness script.

## Actual paths checked

- Repeated session requests; older request-generation commit rejection; independently checked latest commit; retained-plan display; rejected and stale updates; fresh updated hazards; old-version labeling.
- Actual traversal to A and then D with directed history, incoming-edge continuity, departure-time checks, incurred dose, rejected time/dose regression, and retained-plan refusal after progress.
- Changed member identity without mapping, insufficient mapping, explicit conservative mapping, rejection of the old member budget shape, and a newly adapted request whose carried dose remains 10 for each declared member.
- Invalid graph revision/grid/member IDs/version, nonfinite flux, future availability, out-of-order issue time, time-origin change, missing support, and new flame hazards. Prepared admission does not reuse a previous hazard/request validation result.
- Successful recorded return, exact dose including 8 for m1 on route-only return and 12 including dwell; forbidden directed turn, support and flame refusal, endpoint opening/dwell refusal, unavailable mutual reverse declarations, permitted/refused mid-edge reversal, mismatched partial history and nonrepresentable reverse fraction, and return timeout.
- Primary search TIMEOUT plus separately checked successful return: `primary_problem_resolved` remains false.
- Actual replay with repeated plans, update, retained plan, progress, return and reset; deterministic JSON equality with baseline.
- Actual `run.py solve` and `run.py replay` subprocesses, raw and `--prepare-graph`, compared against preserved baseline. No claim of reuse across these processes.
- Snapshot graph exports and caller mutations cannot alter prepared session planning. Checked external authority detects same-revision travel, turn, geometry, node-waitability, provenance, and array-order changes. Plan/update/progress/retained/return/commit guards reject mismatches; pending/retained results cannot be committed.
- Active replacement without reset refused; invalid replacement with reset is atomic and preserves admitted state; valid replacement explicitly clears hazard, progress and pending completion and changes arrival from 4 to 5; export mutation remains isolated; reset keeps graph ownership and admitted immutable bytes.
- Positive checked-content fallback/service reuse, mismatched supplied mutable contents, and invalid prepared-handle type rejection.

## Optimality and refusals

All **17** preserved finite evaluation fixtures were run through actual session admission/planning for baseline, Dijkstra and A* in all three modes: **153 end-to-end session/reference comparisons**. The preserved independently authored exhaustive timed-walk reference shares neither candidate search, dominance nor pruning. The byte-identical reference and fixture hashes are recorded in the manifest; the candidate `routing/independent.py` hash is `af2d8529efb1c2f65f511eb2a39bc2acc30e3a7088ee0e9e0c9eb48f0398d8bf` and matches the preserved baseline.

Reference enumeration completed on every fixture, with at most **10 popped walks** and no `UNRESOLVED` cap. Compared statuses include conditional optimum, checked route under partial global support, proven infeasible, unsupported and at-issue failure. Successful-route arrival matches the exhaustive optimum where complete support permits the optimum claim. A graph-only DISCONNECTED status is accepted only when exhaustive completion proves infeasibility. Route legs and exact per-member exposure are compared against preserved raw results, and all successful witnesses receive the independent occupancy check. These fixture counts must not be presented as exhaustive coverage of production graphs.

## Source review and graph limitations

Tier 2 graph-first evidence used project `routing-preparation-integration-20261005`, fast generation `2026-10-05T07:22:25Z`, targeted RoutingSession and reference discovery, and coverage checks on all relied-on routing files and `run.py`. Relevant searches were bounded; no exhaustive structural claim is made. Coverage initially had no recorded gaps, then reported `metadata_changed` for session/fallback/service/replay/run after integration. The reviewer read those complete final sources directly and compared core/validation against preserved baseline. `validation.py` is unchanged; core changes are confined to prepared graph admission before the unchanged search. A clean graph metadata signal is best effort, not proof of completeness. Fixture JSON was read directly.

## Recovery and caveats

`reset()` is an explicit recovery action: it clears mission state even when a checked external graph has been mutated, keeps the old immutable handle, and does not silently accept changed contents. New operations remain rejected until explicit replacement admits the changed graph. This behavior was tested. `graph` access itself checks external authority and can invalidate pending/retained state on mismatch. The `prepared_graph` handle is an immutable snapshot; callers choosing to use that handle independently are choosing snapshot semantics. Neither path implies concurrent thread safety.

The original raw path intentionally retains its historical mutable API and validation behavior. A prepared session additionally revalidates hazard/request admission at commit. The finite ordinary raw/prepared lifecycle outputs match. Serialized ownership is the supported contract; simultaneous external mutations and multi-thread interleavings were not evaluated.

## Retained failed review runs

The initial run `runs/20261005T072758Z` failed on two review-harness mistakes, and all errors remain saved: the reviewer changed member identity but did not adapt request budget keys, then asserted a request field on the correctly rejected input; the missing-reverse test removed only one side of a required mutual reverse declaration, so preparation correctly refused graph construction. The harness now records the invalid old-budget request before adapting budgets and removes both reciprocal declarations to test unavailable return. These were test-authoring corrections, not production fixes. The first corrected run `runs/20261005T072826Z` passed 35 groups; final predeclared additions covered positive checked facade reuse/type refusals and additional same-revision authority components, yielding 39 passes in `runs/20261005T073028Z`. No production change was requested as a result of this review.

Untested: adversarial large-graph search spaces, exhaustive road optimality/refusal, physical hazards, real forecasting, deployment, concurrency, persistent caches, and cross-process reuse. Timing and memory are outside this review and must be reported from the separate paired end-to-end benchmark.
