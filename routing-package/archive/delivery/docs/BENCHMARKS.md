# Routing correctness and computation evidence

Forecast accuracy: NOT AVAILABLE. Evacuation decision value: NOT EVALUATED. The results below concern routing implementations under declared generated hazards.

## Frozen small cases

The 17 cases were authored and frozen by the independent review subagent before comparison. Five arms × two modes × three rotated repetitions = 510 fresh-process rows. All 510 are retained, including 42 incompatible legacy rows. All 468 eligible outcomes agree with the separately implemented exhaustive timed-walk reference after documenting DISCONNECTED as a stronger structural refinement of infeasibility. There are 222 separately recomputed route witnesses and zero failed checks. Unsupported support and at-issue violations are preserved. The 24 partial-global-support route rows carry CHECKED_ROUTE, without an optimality certificate. No tiny reference exceeded its walk cap.

The legacy arm is the byte-identical repaired vector **component**, not the full established eager/activation planner. It is restricted to 10 compatible cases. Cross-arm headline times over unequal eligibility sets are invalid; the raw paired file records eligibility for each case. Baseline and Dijkstra are the same arrival-order full-vector search, provided as explicit comparison arms. A* changes only queue priority with an admissible travel-time lower bound. Suffix adds the sole selected static legal-suffix pruning method to the baseline. No method receives weaker hazards or a hazard-free objective.

| Arm | Mode | Rows / unavailable | Route witnesses | Refusal / disconnected | At issue / unsupported | Median charged ms (eligible) | Total expansions | Maximum child RSS MiB |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| legacy | cold | 51 / 21 | 15 | 15 | 0 / 0 | 51.264 | 108 | 39.08 |
| legacy | warm | 51 / 21 | 15 | 15 | 0 / 0 | 2.801 | 108 | 40.09 |
| baseline | cold | 51 / 0 | 24 | 21 | 3 / 3 | 10.069 | 135 | 26.36 |
| baseline | warm | 51 / 0 | 24 | 21 | 3 / 3 | 0.501 | 135 | 26.38 |
| astar | cold | 51 / 0 | 24 | 21 | 3 / 3 | 10.002 | 117 | 26.27 |
| astar | warm | 51 / 0 | 24 | 21 | 3 / 3 | 0.517 | 117 | 26.28 |
| dijkstra | cold | 51 / 0 | 24 | 21 | 3 / 3 | 10.345 | 135 | 26.39 |
| dijkstra | warm | 51 / 0 | 24 | 21 | 3 / 3 | 0.609 | 135 | 26.41 |
| suffix | cold | 51 / 0 | 24 | 21 | 3 / 3 | 11.236 | 135 | 27.52 |
| suffix | warm | 51 / 0 | 24 | 21 | 3 / 3 | 0.800 | 135 | 27.39 |

Charged time includes method imports, validation/preparation, search and the mandatory internal independent route checker. External process time also includes interpreter launch, input reading and extra independent postcheck; both are retained in raw rows. Warm has one uncharged invocation first and no persistent cross-request forecast cache. High-water RSS includes that warmup. Tiny cold import overhead dominates; these timings do not establish road-scale performance. Exposure evaluations and all timing/expansion regressions are retained in `evidence/benchmark/rows.jsonl` and `paired_comparisons.json`.

Across the four fully compatible new arms there is no arrival or status regression. A* used 117 expansions per mode versus 135 for Dijkstra (three repetitions combined); this is bounded case evidence. Suffix used 135, the same as baseline, with greater median time and RSS. No optimization acceptance gate passed. It stays off by default; no novelty is claimed.

### Every frozen case, including failures

Each cell gives status, arrival seconds if any, and median charged cold / warm milliseconds. The independent reference is separate from candidate search, dominance and exposure routines.

| Case | Reference | Legacy | Baseline | A* | Dijkstra | Suffix |
|---|---|---|---|---|---|---|
| plain_one_way | CONDITIONAL_OPTIMUM @2 | CONDITIONAL_OPTIMUM @2 (57.14/3.11) | CONDITIONAL_OPTIMUM @2 (12.87/0.87) | CONDITIONAL_OPTIMUM @2 (12.30/0.75) | CONDITIONAL_OPTIMUM @2 (12.82/0.89) | CONDITIONAL_OPTIMUM @2 (12.96/1.16) |
| legal_circling_nonwaitable_empty_layer_future_admission | CONDITIONAL_OPTIMUM @4 | CONDITIONAL_OPTIMUM @4 (57.01/3.38) | CONDITIONAL_OPTIMUM @4 (12.94/1.27) | CONDITIONAL_OPTIMUM @4 (12.71/1.21) | CONDITIONAL_OPTIMUM @4 (13.69/1.40) | CONDITIONAL_OPTIMUM @4 (14.02/1.79) |
| forbidden_turn_blocks_destination | PROVEN_INFEASIBLE | PROVEN_INFEASIBLE (54.17/3.26) | DISCONNECTED (9.62/0.20) | DISCONNECTED (9.75/0.21) | DISCONNECTED (9.96/0.20) | DISCONNECTED (12.18/0.32) |
| zero_leg_destination | CONDITIONAL_OPTIMUM @0 | UNAVAILABLE (10.44/0.17) | CONDITIONAL_OPTIMUM @0 (10.94/0.24) | CONDITIONAL_OPTIMUM @0 (10.05/0.25) | CONDITIONAL_OPTIMUM @0 (10.73/0.43) | CONDITIONAL_OPTIMUM @0 (11.78/0.41) |
| mid_edge_residual | CONDITIONAL_OPTIMUM @2 | UNAVAILABLE (11.01/0.17) | CONDITIONAL_OPTIMUM @2 (11.75/1.12) | CONDITIONAL_OPTIMUM @2 (11.78/0.79) | CONDITIONAL_OPTIMUM @2 (11.70/0.95) | CONDITIONAL_OPTIMUM @2 (12.69/1.27) |
| horizon_exact_arrival | CONDITIONAL_OPTIMUM @2 | CONDITIONAL_OPTIMUM @2 (48.68/1.98) | CONDITIONAL_OPTIMUM @2 (10.87/0.73) | CONDITIONAL_OPTIMUM @2 (10.67/0.70) | CONDITIONAL_OPTIMUM @2 (10.46/0.72) | CONDITIONAL_OPTIMUM @2 (11.24/1.07) |
| horizon_too_short | PROVEN_INFEASIBLE | PROVEN_INFEASIBLE (49.25/1.42) | PROVEN_INFEASIBLE (9.71/0.35) | PROVEN_INFEASIBLE (9.55/0.31) | PROVEN_INFEASIBLE (9.39/0.30) | PROVEN_INFEASIBLE (10.80/0.50) |
| opening_endpoint_with_dwell | CONDITIONAL_OPTIMUM @2 | CONDITIONAL_OPTIMUM @2 (56.61/3.16) | CONDITIONAL_OPTIMUM @2 (11.73/0.80) | CONDITIONAL_OPTIMUM @2 (11.95/0.73) | CONDITIONAL_OPTIMUM @2 (12.32/0.85) | CONDITIONAL_OPTIMUM @2 (11.92/1.19) |
| dwell_past_horizon | PROVEN_INFEASIBLE | PROVEN_INFEASIBLE (48.63/1.77) | PROVEN_INFEASIBLE (8.53/0.48) | PROVEN_INFEASIBLE (8.73/0.49) | PROVEN_INFEASIBLE (9.09/0.50) | PROVEN_INFEASIBLE (10.89/0.70) |
| incurred_budget_failure | AT_ISSUE_FAILURE | UNAVAILABLE (9.57/0.17) | AT_ISSUE_FAILURE (8.40/0.19) | AT_ISSUE_FAILURE (8.96/0.19) | AT_ISSUE_FAILURE (8.63/0.20) | AT_ISSUE_FAILURE (10.45/0.37) |
| missing_support_no_infeasibility_proof | UNSUPPORTED | UNAVAILABLE (9.81/0.17) | UNSUPPORTED (9.71/0.29) | UNSUPPORTED (8.93/0.35) | UNSUPPORTED (8.61/0.29) | UNSUPPORTED (10.62/0.47) |
| disconnected | PROVEN_INFEASIBLE | PROVEN_INFEASIBLE (49.74/2.32) | DISCONNECTED (9.00/0.17) | DISCONNECTED (8.69/0.17) | DISCONNECTED (8.86/0.17) | DISCONNECTED (10.29/0.23) |
| closure_at_arrival_tie | PROVEN_INFEASIBLE | PROVEN_INFEASIBLE (48.23/1.86) | PROVEN_INFEASIBLE (8.70/0.49) | PROVEN_INFEASIBLE (8.76/0.50) | PROVEN_INFEASIBLE (8.67/0.49) | PROVEN_INFEASIBLE (11.10/0.68) |
| multiple_member_dose_failure | PROVEN_INFEASIBLE | UNAVAILABLE (9.89/0.18) | PROVEN_INFEASIBLE (9.28/0.91) | PROVEN_INFEASIBLE (9.17/0.88) | PROVEN_INFEASIBLE (10.35/0.89) | PROVEN_INFEASIBLE (11.48/1.07) |
| route_only_excludes_dwell_dose | CONDITIONAL_OPTIMUM @2 | CONDITIONAL_OPTIMUM @2 (51.23/3.15) | CONDITIONAL_OPTIMUM @2 (11.17/0.87) | CONDITIONAL_OPTIMUM @2 (10.66/0.73) | CONDITIONAL_OPTIMUM @2 (11.39/0.81) | CONDITIONAL_OPTIMUM @2 (11.51/1.17) |
| including_dwell_counts_dose | PROVEN_INFEASIBLE | UNAVAILABLE (9.50/0.17) | PROVEN_INFEASIBLE (9.46/1.07) | PROVEN_INFEASIBLE (9.30/1.08) | PROVEN_INFEASIBLE (9.62/1.16) | PROVEN_INFEASIBLE (11.69/1.36) |
| checked_route_partial_global_support | CHECKED_ROUTE @1 | UNAVAILABLE (9.42/0.17) | CHECKED_ROUTE @1 (11.13/0.48) | CHECKED_ROUTE @1 (10.19/0.45) | CHECKED_ROUTE @1 (10.65/0.48) | CHECKED_ROUTE @1 (10.40/0.66) |

## Full historical graph adapter smoke

The portable labelled fixture admits all 5,765 nodes and 13,976 directed edges, coordinate-derived occupancy and 12,573 forbidden edge pairs. The selected one-edge query returns at 11.6015625 s, with independently recomputed per-member dose 1485/128 and 1485/64 kJ/m². Search expanded one label after full graph/payload validation. Total core wall time was 2.880 s; measured process high-water RSS was 64.375 MiB. This deliberately easy fixture demonstrates full graph admission and a witness; it does not exercise difficult state growth or independently certify full-road global optimality. Hazards, two members, destination, dwell and no-wait policy are generated.

## Six exposed hard road regressions

This separate experiment uses the historical 30-member controlled-hazard contract and all six already-exposed hard queries. It compares the full established eager/activation planner, matched cached A*, matched cached Dijkstra and the SAME legal-suffix pruning applied to A*. It preserves 60 s, 3,072 MiB and the external 95 s watchdog, with no event proxy cap. There is one cold repetition; warm/repeated road timing was not practical in this packaging window. No new sealed/final seeds or observation labels are used. The larger checker independently recomputes every returned route across all 30 planning members. Global optimality/refusal cannot be independently recertified on these hard cases. Their existing numerical semantics are retained, separate from the new exact represented-input adapter contract.

| Query | Arm | Status | Arrival min | End-to-end s | Peak RSS MiB | Independent witness | Expanded labels |
|---|---|---|---:|---:|---:|---|---:|
| RB1-MAIN-LINE-09-Q07 | established | ROUTE_JOINT_OPTIMAL (None) | 41.6201171875 | 33.111 | 1164.828125 | True | UNAVAILABLE |
| RB1-MAIN-LINE-09-Q07 | astar | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.925 | 1161.828125 | NOT_APPLICABLE | 1807744 |
| RB1-MAIN-LINE-09-Q07 | dijkstra | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.837 | 1061.65625 | NOT_APPLICABLE | 1687808 |
| RB1-MAIN-LINE-09-Q07 | suffix_astar | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.881 | 1163.0 | NOT_APPLICABLE | 1790336 |
| RB1-MAIN-STRESS-08-Q06 | astar | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.903 | 1101.40625 | NOT_APPLICABLE | 1801856 |
| RB1-MAIN-STRESS-08-Q06 | dijkstra | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.892 | 1041.3125 | NOT_APPLICABLE | 1745152 |
| RB1-MAIN-STRESS-08-Q06 | suffix_astar | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.908 | 1277.375 | NOT_APPLICABLE | 1779712 |
| RB1-MAIN-STRESS-08-Q06 | established | REFUSED_JOINT_PROVEN (te_NO_ADMISSIBLE_LATTICE_ROUTE_WITHIN_HORIZON_support_established:SUPPORT_ESTABLISHED_FOR_EVERY_ENSEMBLE_MEMBER) | None | 28.071 | 851.78125 | NOT_APPLICABLE | UNAVAILABLE |
| RB1-MAIN-STRESS-08-Q08 | dijkstra | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.907 | 1041.015625 | NOT_APPLICABLE | 1736192 |
| RB1-MAIN-STRESS-08-Q08 | suffix_astar | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.918 | 1025.671875 | NOT_APPLICABLE | 1747584 |
| RB1-MAIN-STRESS-08-Q08 | established | REFUSED_JOINT_PROVEN (te_NO_ADMISSIBLE_LATTICE_ROUTE_WITHIN_HORIZON_support_established:SUPPORT_ESTABLISHED_FOR_EVERY_ENSEMBLE_MEMBER) | None | 28.211 | 849.890625 | NOT_APPLICABLE | UNAVAILABLE |
| RB1-MAIN-STRESS-08-Q08 | astar | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.904 | 1177.96875 | NOT_APPLICABLE | 1819264 |
| RB1-MAIN-STRESS-10-Q03 | suffix_astar | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.902 | 1113.375 | NOT_APPLICABLE | 1490816 |
| RB1-MAIN-STRESS-10-Q03 | established | ROUTE_JOINT_OPTIMAL (None) | 16.5625 | 34.417 | 1173.984375 | True | UNAVAILABLE |
| RB1-MAIN-STRESS-10-Q03 | astar | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.947 | 1117.609375 | NOT_APPLICABLE | 1485440 |
| RB1-MAIN-STRESS-10-Q03 | dijkstra | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.795 | 1153.625 | NOT_APPLICABLE | 1465216 |
| RB1-MAIN-STRESS-10-Q05 | established | ROUTE_JOINT_OPTIMAL (None) | 16.5625 | 33.037 | 1310.765625 | True | UNAVAILABLE |
| RB1-MAIN-STRESS-10-Q05 | astar | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 61.024 | 1188.546875 | NOT_APPLICABLE | 1581440 |
| RB1-MAIN-STRESS-10-Q05 | dijkstra | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.897 | 1249.453125 | NOT_APPLICABLE | 1521152 |
| RB1-MAIN-STRESS-10-Q05 | suffix_astar | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.892 | 1301.46875 | NOT_APPLICABLE | 1570304 |
| RB1-MAIN-STRESS-10-Q07 | astar | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.914 | 1238.0 | NOT_APPLICABLE | 1714048 |
| RB1-MAIN-STRESS-10-Q07 | dijkstra | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.870 | 1030.828125 | NOT_APPLICABLE | 1600512 |
| RB1-MAIN-STRESS-10-Q07 | suffix_astar | TIMEOUT (TOTAL_BUDGET_EXCEEDED) | None | 60.858 | 1204.859375 | NOT_APPLICABLE | 1689216 |
| RB1-MAIN-STRESS-10-Q07 | established | ROUTE_JOINT_OPTIMAL (None) | 74.8193359375 | 43.984 | 1123.484375 | True | UNAVAILABLE |

Final independent checking summary: `{"rows": 24, "independent_route_member_checks": 120, "independent_failures": [], "global_optima_or_refusals_independently_recertified": false, "warm_and_repeats": "NOT_RUN_ON_HARD_ROADS; TINY_MATCHED_STUDY_HAS_BOTH"}`.

## Preserved prior negative evidence

Manifested completion reported 616 routes across 753 development queries; all six activated queries were scalar, so that result did not validate vector search. The repaired vector empty-layer case is exercised independently here. The controlled 48-case / 576-run small study reported 8,169 Dijkstra labels versus 3,888 A* labels; activation could use more labels. Its cached A*/Dijkstra hard-road comparison had 12 timeouts out of 12 at 60 s cold / 3,072 MiB. The six lower-bound diagnostic queries returned one route and five timeouts. The novelty study's 240 tiny cases had no wrong result, but lazy and lazy-A* each timed out on all six hard roads. Eager without the event proxy produced four routes and two refusals; the event-proxy variant had four timeouts and two refusals. These established negative results remain intact; no 40 GB storage cap has been added.

## Measurement custody

Official runs use the existing shared exclusive wrapper. The full-graph EXPORT, before official comparison, unexpectedly exceeded the light-work threshold while another study measured. Its overlap and unknown external impact are disclosed in `evidence/MEASUREMENT_LANE_INCIDENT.json`; no timing claim here is based on the export. The source/preflight archives preserve stale-manifest disclosures. This package is subagent plus coordinator work, not an external human audit.
