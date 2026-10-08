# Outcomes and computational work

No useful incident multi-edge route was demonstrated. All four modes have the same six incident outcomes in both phases: four TIMEOUTs and two AT_ISSUE_FAILUREs, giving **32 unresolved TIMEOUT phases and 16 at-issue refusals across 48 incident phases**. There is no incident destination witness or continuous-road certificate. The 17 known exact-reference cases preserve their expected centre outcomes in all modes, but all **136 reference phases** have unavailable physical source contracts and unresolved whole-road outcomes.

Raw panel: [confirmation_v1](/Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_integrated_search_followup_20261008_v1/results/confirmation_v1/ROWS.json). Reconciled 23 cases × four modes × cold/warm = **184 phase slots**. Every slot is retained; failed, missing, malformed or binding-failed authority is UNRESOLVED. Complete costs for such phases are UNKNOWN; recorded lower-bound work and full failed-launch costs remain in WORK.csv.

Independent final verification passes all 184 phases; the separate FINAL_GATES.json and INDEPENDENT_FINAL_REVIEW.md record NO_GO for useful integrated routing and promotion. This report remains the author-lane reconciliation; independent authority is in those reviewed artifacts. No default promotion, global road optimum/refusal claim or physical-safety claim is made.

The original 78 raw integration reports and 27 primary TIMEOUT cases remain preserved. All original TIMEOUTs are unresolved; recovered opt-in outcomes do not rewrite the old ledger. The two representative diagnostic profiles and development modes_v1/v2 are separate evidence; their counters must not be assigned to all 27 or the fresh cohort.

Original primary TIMEOUT ledger count: **27**. Original freeze records 30 calls including warm. Original raw file [/Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_integrated_search_followup_20261008_v1/baseline/ORIGINAL_ROWS.json](/Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_integrated_search_followup_20261008_v1/baseline/ORIGINAL_ROWS.json).

## Search outcomes

| Cohort | Phase | Mode | Outcomes (all slots) |
|---|---|---|---|
| incident | cold | baseline | AT_ISSUE_FAILURE: 2, TIMEOUT: 4 |
| incident | cold | cache | AT_ISSUE_FAILURE: 2, TIMEOUT: 4 |
| incident | cold | heuristic | AT_ISSUE_FAILURE: 2, TIMEOUT: 4 |
| incident | cold | combined | AT_ISSUE_FAILURE: 2, TIMEOUT: 4 |
| incident | warm | baseline | AT_ISSUE_FAILURE: 2, TIMEOUT: 4 |
| incident | warm | cache | AT_ISSUE_FAILURE: 2, TIMEOUT: 4 |
| incident | warm | heuristic | AT_ISSUE_FAILURE: 2, TIMEOUT: 4 |
| incident | warm | combined | AT_ISSUE_FAILURE: 2, TIMEOUT: 4 |
| reference | cold | baseline | AT_ISSUE_FAILURE: 2, CHECKED_ROUTE: 1, CONDITIONAL_OPTIMUM: 6, DISCONNECTED: 1, INVALID_INPUT: 1, PROVEN_INFEASIBLE: 4, UNSUPPORTED: 2 |
| reference | cold | cache | AT_ISSUE_FAILURE: 2, CHECKED_ROUTE: 1, CONDITIONAL_OPTIMUM: 6, DISCONNECTED: 1, INVALID_INPUT: 1, PROVEN_INFEASIBLE: 4, UNSUPPORTED: 2 |
| reference | cold | heuristic | AT_ISSUE_FAILURE: 2, CHECKED_ROUTE: 1, CONDITIONAL_OPTIMUM: 6, DISCONNECTED: 1, INVALID_INPUT: 1, PROVEN_INFEASIBLE: 4, UNSUPPORTED: 2 |
| reference | cold | combined | AT_ISSUE_FAILURE: 2, CHECKED_ROUTE: 1, CONDITIONAL_OPTIMUM: 6, DISCONNECTED: 1, INVALID_INPUT: 1, PROVEN_INFEASIBLE: 4, UNSUPPORTED: 2 |
| reference | warm | baseline | AT_ISSUE_FAILURE: 2, CHECKED_ROUTE: 1, CONDITIONAL_OPTIMUM: 6, DISCONNECTED: 1, INVALID_INPUT: 1, PROVEN_INFEASIBLE: 4, UNSUPPORTED: 2 |
| reference | warm | cache | AT_ISSUE_FAILURE: 2, CHECKED_ROUTE: 1, CONDITIONAL_OPTIMUM: 6, DISCONNECTED: 1, INVALID_INPUT: 1, PROVEN_INFEASIBLE: 4, UNSUPPORTED: 2 |
| reference | warm | heuristic | AT_ISSUE_FAILURE: 2, CHECKED_ROUTE: 1, CONDITIONAL_OPTIMUM: 6, DISCONNECTED: 1, INVALID_INPUT: 1, PROVEN_INFEASIBLE: 4, UNSUPPORTED: 2 |
| reference | warm | combined | AT_ISSUE_FAILURE: 2, CHECKED_ROUTE: 1, CONDITIONAL_OPTIMUM: 6, DISCONNECTED: 1, INVALID_INPUT: 1, PROVEN_INFEASIBLE: 4, UNSUPPORTED: 2 |

## Whole-road and integrated witness outcomes

| Cohort | Phase | Mode | Outcomes (all slots) |
|---|---|---|---|
| incident | cold | baseline | NOT_RUN: 6 |
| incident | cold | cache | NOT_RUN: 6 |
| incident | cold | heuristic | NOT_RUN: 6 |
| incident | cold | combined | NOT_RUN: 6 |
| incident | warm | baseline | NOT_RUN: 6 |
| incident | warm | cache | NOT_RUN: 6 |
| incident | warm | heuristic | NOT_RUN: 6 |
| incident | warm | combined | NOT_RUN: 6 |
| reference | cold | baseline | UNRESOLVED: 17 |
| reference | cold | cache | UNRESOLVED: 17 |
| reference | cold | heuristic | UNRESOLVED: 17 |
| reference | cold | combined | UNRESOLVED: 17 |
| reference | warm | baseline | UNRESOLVED: 17 |
| reference | warm | cache | UNRESOLVED: 17 |
| reference | warm | heuristic | UNRESOLVED: 17 |
| reference | warm | combined | UNRESOLVED: 17 |

| Cohort | Phase | Mode | Outcomes (all slots) |
|---|---|---|---|
| incident | cold | baseline | UNRESOLVED: 6 |
| incident | cold | cache | UNRESOLVED: 6 |
| incident | cold | heuristic | UNRESOLVED: 6 |
| incident | cold | combined | UNRESOLVED: 6 |
| incident | warm | baseline | UNRESOLVED: 6 |
| incident | warm | cache | UNRESOLVED: 6 |
| incident | warm | heuristic | UNRESOLVED: 6 |
| incident | warm | combined | UNRESOLVED: 6 |
| reference | cold | baseline | UNRESOLVED: 17 |
| reference | cold | cache | UNRESOLVED: 17 |
| reference | cold | heuristic | UNRESOLVED: 17 |
| reference | cold | combined | UNRESOLVED: 17 |
| reference | warm | baseline | UNRESOLVED: 17 |
| reference | warm | cache | UNRESOLVED: 17 |
| reference | warm | heuristic | UNRESOLVED: 17 |
| reference | warm | combined | UNRESOLVED: 17 |

A centre CONDITIONAL_OPTIMUM concerns the supported discrete centre/cell model. Road CERTIFIED_ADMISSIBLE authorizes only the supplied recovered witness under the unchanged finite constructed source contract. A rejected road witness does not prove every road route infeasible; this experiment does not blacklist it and resume search. TIMEOUT remains unresolved even if a separately checked integrated witness is retained. Exact-reference fixtures lack continuous physical source evidence, so their whole-road result remains UNRESOLVED/SOURCE_CONTRACT_UNAVAILABLE.

## Complete process cost

All 92 recorded launches, including failures: wall **1453.294078 s**; child user CPU **1463.416766 s**; child system CPU **201.938998 s**. Process wall totals sum sequential launches once, not cold/warm phase wall plus launcher wall. Unknown values remain UNKNOWN. Driver completion: `{"all_failed_work_retained":true,"expected_workers":92,"total_child_system_CPU_s":201.938998,"total_child_user_CPU_s":1463.416766,"total_full_process_wall_s":1453.2940775840107,"valid_complete_workers":92,"worker_failures":0,"worker_slots":92}`.

WORK.csv has PHASE rows and separate WORKER_LAUNCH rows. The latter include interpreter startup/imports, source and implementation snapshots, source bridge re-admission, graph/cache binding, cold/warm search, independent centre and whole-road checks, final authority validation and serialization. Component timing dictionaries overlap with parent phases and are not summed blindly. RSS is the engine/mode-isolated worker lifetime peak, not incremental allocation, per-search memory or a phase-independent peak. Cold/warm share only that same case/mode worker.

## Cold/warm complete-call comparison

| Case | Cohort | Phase | Baseline s | Cache s | Heuristic s | Combined s | Combined minus baseline s |
|---|---|---|---:|---:|---:|---:|---:|
| 20220304T030000Z_original-hard | incident | cold | 44.135643 | 49.051969 | 44.503712 | 49.122218 | 4.986575 |
| 20220304T030000Z_original-hard | incident | warm | 30.663270 | 30.737699 | 30.673022 | 30.719450 | 0.056181 |
| 20220304T030000Z_topology-first | incident | cold | 44.650071 | 52.537319 | 44.672198 | 49.882986 | 5.232916 |
| 20220304T030000Z_topology-first | incident | warm | 30.668739 | 30.884659 | 30.671103 | 30.741369 | 0.072629 |
| 20220304T060000Z_original-hard | incident | cold | 44.515087 | 49.177974 | 44.716206 | 49.685814 | 5.170728 |
| 20220304T060000Z_original-hard | incident | warm | 30.692784 | 30.731823 | 30.664009 | 30.743858 | 0.051074 |
| 20220304T060000Z_topology-first | incident | cold | 45.825258 | 49.349833 | 44.795134 | 50.582733 | 4.757475 |
| 20220304T060000Z_topology-first | incident | warm | 30.678307 | 30.744358 | 30.794828 | 30.734066 | 0.055759 |
| 20220304T120000Z_original-hard | incident | cold | 19.465254 | 23.913630 | 19.122849 | 23.856509 | 4.391255 |
| 20220304T120000Z_original-hard | incident | warm | 0.812832 | 0.849200 | 0.799424 | 0.840971 | 0.028139 |
| 20220304T120000Z_topology-first | incident | cold | 19.278230 | 23.810429 | 19.457446 | 24.378036 | 5.099806 |
| 20220304T120000Z_topology-first | incident | warm | 0.797916 | 0.845830 | 0.808335 | 0.840677 | 0.042761 |
| at_issue_flame | reference | cold | 0.005414 | 0.005687 | 0.007763 | 0.004844 | -0.000570 |
| at_issue_flame | reference | warm | 0.003302 | 0.003079 | 0.002793 | 0.002906 | -0.000396 |
| clear_multiedge | reference | cold | 0.005558 | 0.006847 | 0.006413 | 0.005740 | 0.000182 |
| clear_multiedge | reference | warm | 0.003616 | 0.003392 | 0.004119 | 0.003596 | -0.000020 |
| contact_requires_wait | reference | cold | 0.007465 | 0.007436 | 0.007364 | 0.006697 | -0.000768 |
| contact_requires_wait | reference | warm | 0.004742 | 0.004696 | 0.005206 | 0.004258 | -0.000483 |
| destination_dwell_refusal | reference | cold | 0.011825 | 0.009106 | 0.014140 | 0.008620 | -0.003205 |
| destination_dwell_refusal | reference | warm | 0.011770 | 0.006834 | 0.008854 | 0.006963 | -0.004807 |
| destination_wait_is_not_admission | reference | cold | 0.004914 | 0.005374 | 0.005495 | 0.007117 | 0.002203 |
| destination_wait_is_not_admission | reference | warm | 0.003620 | 0.003561 | 0.003577 | 0.004523 | 0.000902 |
| dose_refusal | reference | cold | 0.011882 | 0.006861 | 0.006043 | 0.005906 | -0.005975 |
| dose_refusal | reference | warm | 0.006006 | 0.004159 | 0.005749 | 0.006130 | 0.000123 |
| incoming_turn_refusal | reference | cold | 0.004919 | 0.006754 | 0.003783 | 0.004406 | -0.000513 |
| incoming_turn_refusal | reference | warm | 0.002741 | 0.002782 | 0.002878 | 0.002258 | -0.000483 |
| incurred_boundary_equality | reference | cold | 0.006691 | 0.006732 | 0.006592 | 0.005155 | -0.001537 |
| incurred_boundary_equality | reference | warm | 0.005244 | 0.004750 | 0.004068 | 0.002796 | -0.002448 |
| incurred_over_budget | reference | cold | 0.004250 | 0.007004 | 0.004707 | 0.004047 | -0.000202 |
| incurred_over_budget | reference | warm | 0.002801 | 0.002208 | 0.002686 | 0.003254 | 0.000453 |
| mandatory_wait_opening | reference | cold | 0.007162 | 0.008203 | 0.015890 | 0.007107 | -0.000055 |
| mandatory_wait_opening | reference | warm | 0.007078 | 0.006092 | 0.004920 | 0.004908 | -0.002170 |
| member_identity_mismatch | reference | cold | 0.004651 | 0.003841 | 0.004504 | 0.005012 | 0.000362 |
| member_identity_mismatch | reference | warm | 0.002915 | 0.002923 | 0.002642 | 0.002343 | -0.000572 |
| member_tradeoff_dwell | reference | cold | 0.006697 | 0.006693 | 0.007079 | 0.006351 | -0.000346 |
| member_tradeoff_dwell | reference | warm | 0.004670 | 0.003869 | 0.003949 | 0.003551 | -0.001119 |
| missing_global_support | reference | cold | 0.006577 | 0.007322 | 0.007339 | 0.005419 | -0.001158 |
| missing_global_support | reference | warm | 0.004479 | 0.006356 | 0.003285 | 0.002860 | -0.001619 |
| missing_issue_support | reference | cold | 0.003849 | 0.004569 | 0.004139 | 0.004346 | 0.000497 |
| missing_issue_support | reference | warm | 0.002244 | 0.002214 | 0.002972 | 0.002746 | 0.000502 |
| peak_refusal | reference | cold | 0.011858 | 0.008520 | 0.015723 | 0.009001 | -0.002857 |
| peak_refusal | reference | warm | 0.009342 | 0.006820 | 0.010971 | 0.006835 | -0.002508 |
| stale_version | reference | cold | 0.004016 | 0.004826 | 0.003703 | 0.003809 | -0.000207 |
| stale_version | reference | warm | 0.002296 | 0.002612 | 0.002990 | 0.002124 | -0.000172 |
| turn_chooses_other_branch | reference | cold | 0.005644 | 0.006457 | 0.004830 | 0.005871 | 0.000227 |
| turn_chooses_other_branch | reference | warm | 0.003405 | 0.004310 | 0.002909 | 0.003089 | -0.000317 |

These paired call costs include external preparation/binding and the separate road checker, so a slower call may also have produced additional checked work. Outcome/work CSVs retain primary search cost and every phase. Centre-only reference costs must remain distinct from incident physical-source costs. No claim of broad search efficiency follows from this bounded panel.

## Paired call regressions retained

Counts below compare each same-case complete call against its same-phase instrumented baseline, with no case exclusions. Positive summed delta means more wall time. These are single measurements, and small differences are not a statistical efficiency claim. All primary statuses are unchanged across modes for every case.

| Cohort | Phase | Mode vs baseline | Slower / faster cases | Summed full-call delta s | Largest individual slowdown s |
|---|---|---|---|---:|---:|
| incident | cold | cache | 6 / 0 | 29.971612 | 7.887249 |
| incident | cold | heuristic | 4 / 2 | -0.601998 | 0.368068 |
| incident | cold | combined | 6 / 0 | 29.638754 | 5.232916 |
| incident | warm | cache | 6 / 0 | 0.479721 | 0.215919 |
| incident | warm | heuristic | 4 / 2 | 0.096873 | 0.116521 |
| incident | warm | combined | 6 / 0 | 0.306543 | 0.072629 |
| reference | cold | cache | 11 / 6 | -0.001138 | 0.002755 |
| reference | cold | heuristic | 10 / 7 | 0.012133 | 0.008728 |
| reference | cold | combined | 5 / 12 | -0.013923 | 0.002203 |
| reference | warm | cache | 5 / 12 | -0.009615 | 0.001878 |
| reference | warm | heuristic | 6 / 11 | -0.005703 | 0.001629 |
| reference | warm | combined | 4 / 13 | -0.015134 | 0.000902 |

Both cache modes are slower on all six incident cold calls and all six incident warm calls. Cold cache-only adds 29.971612s across the six cases and combined adds 29.638754s; warm adds 0.479721s/0.306543s respectively. Cached runs may complete more label work before the same timeout, but none obtains a destination witness, so this does not demonstrate useful routing or justify default promotion. Heuristic-only has mixed cost direction and no outcome improvement. Exact-reference differences are millisecond-scale, source-free centre checks and remain separate from incident routing performance.

## Original unresolved TIMEOUT ledger

| Original case | Original primary | Interpretation |
|---|---|---|
| 20220304T030000Z_baseline_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T030000Z_missing_zero_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T030000Z_timing_late_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T030000Z_current_cold_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T030000Z_current_short_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T030000Z_fuel_half_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T030000Z_fuel_double_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T030000Z_duration_short_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T030000Z_duration_long_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T060000Z_baseline_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T060000Z_missing_zero_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T060000Z_timing_late_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T060000Z_current_cold_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T060000Z_current_short_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T060000Z_fuel_half_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T060000Z_fuel_double_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T060000Z_duration_short_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T060000Z_duration_long_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T120000Z_baseline_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T120000Z_missing_zero_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T120000Z_timing_late_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T120000Z_current_cold_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T120000Z_current_short_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T120000Z_fuel_half_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T120000Z_fuel_double_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T120000Z_duration_short_difficult | TIMEOUT | Unresolved, original outcome preserved |
| 20220304T120000Z_duration_long_difficult | TIMEOUT | Unresolved, original outcome preserved |

## Source preparation and preserved development failures

Fresh source construction and centre admission add **30.965016 measured wall seconds and 32.294404 measured CPU seconds**, once for three source packets, in addition to the 92 fresh workers. The receipt starts after imports: interpreter startup/imports, initial graph loading and final preparation cleanup costs are **UNAVAILABLE**, not zero. The full source-preparation process total is unavailable. See [COST_SCOPE.md](/Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_integrated_search_followup_20261008_v1/COST_SCOPE.md) and [FRESH_PREPARATION_WORK_SCOPE.json](/Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_integrated_search_followup_20261008_v1/evidence/FRESH_PREPARATION_WORK_SCOPE.json). No total-project efficiency claim is permitted.

| Preserved development group | Full process wall s | Child user CPU s | Child system CPU s | Interpretation |
|---|---:|---:|---:|---|
| Original-cap reproductions | 88.046064 | 88.120231 | 7.251268 | Two profiled original TIMEOUT representatives; observer work included |
| modes_v1 | 234.349345 | 234.063269 | 27.489975 | All 16 phases fail source-member binding before search; preserved failed cost |
| modes_v2 | 628.808378 | 624.618852 | 30.194955 | All 16 phases TIMEOUT; pre-digest-guard development evidence |

The initial wrapper software defect used constructor event member IDs rather than unchanged hourly routing IDs. Corrected namespace admission preserves arrays, source law, budgets and incurred ledgers; independent prefreeze review separately added a content-derived construction-digest guard. None of the failed work is removed. [DEVELOPMENT_DIAGNOSIS.md](/Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_integrated_search_followup_20261008_v1/DEVELOPMENT_DIAGNOSIS.md) documents the original-versus-common-observer scopes, duplicate geometry, the shift to exact dominance, weak heuristic effect, missing destination progress and two-case coverage limit. Those two profiles are not assigned to all 27 original TIMEOUT cases.

Source preparation stages, fresh full-worker receipts and the separately scoped development receipts must not be combined into a claimed complete project total. Author/reference/provenance controls, independent review and portable verification have separate receipts; unmeasured outer source-preparation overhead remains unavailable.

The sealed reporting command was externally timed at **0.16 s wall, 0.04 s user CPU, 0.02 s system CPU**, with 29,736,960 bytes maximum resident size, using `/usr/bin/time -l`. These values have the utility's displayed precision and describe report generation, not routing latency. A failed shell invocation using a nonexistent interpreter path also occurred during author analysis; it did not run an experiment or alter artifacts, and its independent CPU cost was not captured.

## Reporting anomalies and limitations

Unexpected/malformed input rows: `[]`. Slots with authority errors: **0**; details are retained in CASE_OUTCOMES.csv. Input hazard hashes and original limit maps must agree across all eight slots per case; disagreement is unresolved. Source file byte identity is enforced by the wrapper epochs and the separately frozen driver, not inferred from a favorable route.

The original modelling assumptions, constructed hazards, centre versus road distinction, finite scenario ensemble, supported horizon and independent review limits remain. Cache timings are instrumented on all four modes; uninstrumented original counters remain unrecorded. See [CACHE_SPEC.md](/Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_integrated_search_followup_20261008_v1/CACHE_SPEC.md) for precise metric aliases, exact affine geometry proof, ownership and cooperative cap scope.

Timing qualification: the frozen dominance timer covers the full label-add routine, including exact comparisons, frontier scans/updates, and record/heap bookkeeping. It does not isolate comparison cost. Comparison counts and integer bit lengths were not measured. A next diagnosis must distinguish these components before choosing a fix.
