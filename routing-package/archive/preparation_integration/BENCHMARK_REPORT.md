# End-to-end preparation integration benchmark — 5 October 2026

Frozen, standard-library paired engineering evaluation: 120 rows / 60 pairs; 3 alternating paired repeats in fresh child processes. No final tuning. Candidate code, exact input bytes, modes, order, budgets and decision were frozen in `evidence/CONFIRM_FREEZE.json` before the final run. The existing exclusive machine wrapper was used; every error, regression and unresolved outcome remains in `evidence/confirm/ROWS.jsonl`. Recomputed summary and extra witness rows are alongside. Verdict on measured semantics: PASS.

## One full-road simple query, generated hazards

| Flow | Raw lifecycle s | Prepared lifecycle s | Median paired ratio | >5% slower pairs | Peak RSS raw/prepared MiB |
|---|---:|---:|---:|---:|---:|
| checked_session | 28.896 | 3.444 | 0.1186 | 0/3 | 140.38/183.31 |
| cli_replay | 23.829 | 3.030 | 0.1270 | 0/3 | 99.45/114.75 |
| cli_solve | 2.699 | 2.791 | 1.0362 | 0/3 | 68.44/93.36 |
| cold_session | 13.132 | 2.862 | 0.2181 | 0/3 | 134.19/152.91 |
| hazard_update | 34.045 | 3.102 | 0.0908 | 0/3 | 139.83/158.14 |
| repeated_session | 29.286 | 3.044 | 0.1035 | 0/3 | 136.11/155.67 |
| replacement | 26.605 | 5.799 | 0.2179 | 0/3 | 138.78/163.88 |
| replay | 23.549 | 3.040 | 0.1297 | 0/3 | 141.41/158.58 |
| return_fallback | 20.914 | 2.865 | 0.1366 | 0/3 | 127.72/133.20 |


Each mode has only three pairs on one full Nangok road query (5,765 nodes / 13,976 directed edges), with generated uniform incident-flux assumptions and two members. This is one geometry/workload, not three independent fires. Median of paired ratios is reported separately from ratios of marginal medians. No population significance or universal improvement claim is warranted.

## Tiny continuity and bounded distant-road search

| Flow | Raw lifecycle s | Prepared lifecycle s | Median paired ratio | >5% slower pairs | Peak RSS raw/prepared MiB |
|---|---:|---:|---:|---:|---:|
| checked_session | 0.080 | 0.081 | 1.0182 | 0/3 | 101.69/103.00 |
| cli_replay | 0.114 | 0.114 | 1.0017 | 0/3 | 21.39/21.64 |
| cli_solve | 0.099 | 0.106 | 1.0725 | 2/3 | 20.06/21.45 |
| cold_session | 0.072 | 0.074 | 1.0246 | 0/3 | 101.98/102.92 |
| hazard_update | 0.080 | 0.081 | 1.0070 | 0/3 | 101.61/103.17 |
| repeated_session | 0.081 | 0.081 | 1.0087 | 0/3 | 101.83/103.14 |
| replacement | 0.077 | 0.081 | 1.0192 | 0/3 | 102.02/103.08 |
| replay | 0.078 | 0.078 | 0.9802 | 0/3 | 101.45/102.97 |
| return_fallback | 0.070 | 0.072 | 1.0426 | 1/3 | 101.91/103.20 |


| Flow | Raw lifecycle s | Prepared lifecycle s | Median paired ratio | >5% slower pairs | Peak RSS raw/prepared MiB |
|---|---:|---:|---:|---:|---:|
| cold_session | 10.474 | 2.777 | 0.2661 | 0/3 | 114.03/131.28 |
| repeated_session | 20.982 | 2.954 | 0.1404 | 0/3 | 120.36/137.42 |


The intended difficult-envelope query uses the same road graph with a far destination, 240-second horizon and a predeclared 100-expansion cap. It actually returned DISCONNECTED in every arm/repeat, so the search cap was never exercised. It is retained as a structural-refusal lifecycle case, not claimed as hard-search evidence. A separately frozen connected diagnostic was then designed from static topology alone, with the routing candidate unchanged; its outcomes are reported separately below and do not drive promotion. Old established-planner exposure-active road inputs use a separate research API/contract and were not converted or regraded. Full-budget hard Pareto searches, many-member exposure-active search efficacy and other geographies remain untested.

## Chargeable lifecycle and phase evidence

The main lifecycle begins before routing imports and JSON cohort parsing. It includes initialization, accepted hazard validation, complete planning, commit and retained checks, updates, content comparisons, reset, replacement/rebuild and output construction. Per-child external `process_s` additionally charges interpreter startup and final JSON output serialization. CLI modes record complete nested CLI process times; raw facade-only `end_to_end_s` is not treated as complete CLI timing. Paired phase fields in rows preserve warm and startup costs separately; full lifecycle is the decision measure.

Session construction raw/prepared on simple road: 13.132 → 2.862 s for initialization+first request+commit+retained+reset as a complete flow. The isolated initialization phase itself is 2.604 / 2.669 s. Thus prepared construction is not free; session savings also remove duplicated raw graph admission in update/request/retained operations.

Three complete repeated plan/commit/retained cycles including initialization/reset: 29.286 → 3.044 s. Warm cycle 0: 7964.179 / 106.202 ms; warm cycle 1: 7889.847 / 103.437 ms. Checked-authority mode charges canonical content comparison separately on each operation, not a revision-only shortcut.

Hazard-update flow constructs two copied versions and validates/accepts them, with three full request cycles: 34.045 → 3.102 s. Replay flow handles initialization, 3 actual PLAN events, update and reset: 23.549 → 3.040 s. Return flow includes cold graph preparation and 2 primary/recorded-return facades (simple-road primary PROVEN_INFEASIBLE with a refused UNSUPPORTED return; tiny mode primary TIMEOUT with CHECKED_ROUTE return): 20.914 → 2.865 s. No recorded primary TIMEOUT was relabelled resolved by a return.

Replacement flow charges the original full request, copied changed graph, rebuild, new matching hazard, new plan/commit/retained checks and reset: 26.605 → 5.799 s. Standalone replacement/rebuild phase raw/prepared is 2.709 / 2.781 s. Baseline explicitly resets and creates a new session; candidate uses atomic `replace_graph(..., reset=True)`. Generation counters differ naturally across fresh object construction, so only that comparison normalizes generation fields; stale-generation safety has separate adversarial tests and originals remain in rows.

## Memory and measurement limits

Repeated-road production peak RSS: 136.11 / 155.67 MiB. Immutable prepared payload: 3.679 MiB (3858130 bytes), excluding Python object overhead and fresh decoded graphs. RSS is the fresh child's high-water mark, including cohort parsing, temporary admission copies, allocator history and lifecycle work. It is not steady-state resident memory or allocation attribution; no memory-reduction claim. CLI peak RSS is taken from its sole child process. Retained payload bytes for replay/CLI are unmeasured/null because their private session is local to the call, not zero.

The JSON cohort contains duplicate road/replay representations, so parsing contributes high-water memory and absolute latency in both arms. Individual deployment payload size and allocator behavior could differ. Input construction and replacement coexistence are charged. Three repeats are descriptive only; other nonparticipating OS activity is not controlled and load averages are retained. Wrapper locking excludes participating heavy jobs, not every background process. Cooperative resource caps and 120-second external watchdog remain. Every regression pair can be recomputed; no outcome is removed for being slower, unsupported or unresolved.

## Preservation, repair and adoption

312 extra arithmetic/occupancy witness checks pass with the unchanged baseline checker; no road optimum/refusal is exhaustively recertified. Semantic disagreements: 0; deterministic search-counter disagreements: 0; child/watchdog errors: 0. Full statuses and exact dose strings/legs/checks remain in rows, including TIMEOUT and unsupported replay events.

An initial source audit found `reset="false"` accepted as truthy in the new replacement API. The partial first timing run was aborted and preserved with its freeze in `evidence/pre_repair_partial/` and `PRE_REPAIR_FREEZE.json`. A strict Boolean admission guard was independently tested, then candidate refrozen with identical confirmatory input bytes. No final timing results selected the repair or changed workload/budget/promotion rules. Independent review candidly records this bug was missed by its earlier suite. Partial rows are not part of the final summaries. Evaluator source/metadata corrections are recorded before confirmatory-row inference in the aggregator freezes; they change no candidate timing/input.

Adopt as optional measured integration paths for stable large-graph sessions (owned or checked authority), repeated replay, and compatible primary-plus-recorded-return use. Actual lifecycle rather than warm solve alone supports this recommendation where paired ratio passes 0.8. Keep tiny and successful one-shot CLI paths raw by default, and prefer raw/direct validation for frequent graph changes unless the ensuing request lifecycle repays rebuild. Preparation does not improve the search algorithm or resource-resolution rate. Existing separate AS-EAGER/CAND-2 research recommendation is unchanged. No new dependencies, forecast changes, physical safety, deployment or cross-process cache claim.


## Separately frozen connected capped-search diagnostic

The main intended hard case returned DISCONNECTED, so it did not test search. The candidate was left unchanged. Before the supplemental run, `HARD_DIAGNOSTIC_DESIGN.json`, `HARD_CONNECTED_INPUTS.json` and `HARD_CONNECTED_FREEZE.json` fixed a topology-selected query: first deterministic sorted edge with legal return and at least 500 reachable nodes; furthest legally reachable destination by static travel time. It reaches 5,689 nodes / 13,690 incoming-edge states. The primary session uses a 500-expansion cap and 60-second wall budget; the return facade uses a 1-expansion primary cap and a separate 60-second check. Three alternating paired repeats cover cold session, three-request lifecycle and two primary/return facades. This is a post-main engineering diagnostic, not a new independent confirmatory efficacy or promotion study. No routing code, numerical behavior, main input, budget or adoption statistic was tuned. Generic inherited freeze metadata is clarified without rewriting frozen bytes in HARD_FREEZE_METADATA_NOTE.md.

| Supplemental flow | Raw lifecycle s | Prepared lifecycle s | Paired ratio | Peak RSS raw/prepared MiB |
|---|---:|---:|---:|---:|
| cold_session | 10.564 | 3.002 | 0.2842 | 124.92/147.47 |
| repeated_session | 21.536 | 3.604 | 0.1662 | 129.52/150.78 |
| return_fallback | 20.599 | 2.790 | 0.1354 | 118.44/126.02 |

All 18 supplemental rows / 9 pairs agree in complete non-timing results and deterministic search counters, with no child errors. Cold/repeated searches actually hit MAX_EXPANSIONS at 500 in both arms; primary fallback searches hit their 1-expansion cap. Every primary TIMEOUT remains unresolved. Every separately checked reverse return succeeds, including nonzero prior dose and an actual legal directed reverse, and 12 extra unchanged-baseline return witness checks reproduce exact member exposure. No resolution-rate or faster-search claim: the warm search still performs the same expansions. Raw rows, summaries and witness rows are in evidence/hard_connected/. The shortest static legal path to this deliberately distant goal exceeds the declared horizon, so this is an unresolved capped-search stress case, not a solved hard road optimum/refusal or exposure-active multi-member stress test.
