# Development diagnosis: cache removes repeated geometry, not the unresolved search

The two named difficult development cases still produce **TIMEOUT/WALL_CLOCK in all 16 cold/warm mode phases**, with zero destination labels, zero independent route-check attempts and zero checked incumbents. No useful incident multi-edge route is demonstrated by these runs. Cache reuse addresses demonstrated duplicate computation, but it does not establish a solved query, global infeasibility or broad efficiency gain.

This report opens only `development/original_cap_reproductions`, `development/modes_v1` and `development/modes_v2` plus their preserved correction records. Fresh confirmation inputs/outcomes remain unopened by this lane. The original cohort has 27 primary TIMEOUT cases; these are two named representatives (baseline03 and fuel_double06), not a full 27-case computational diagnosis. The other 25 cases have no new profile here. Original 78 raw reports and all 27 unresolved outcomes remain unchanged.

## Evidence and comparison scopes

The original-cap reproductions use the unchanged core source SHA `b8168943168603f9beccfd2a0ca2b18b8cb77fac91de4f7dda481b2d2faa157c` through the diagnostic observer, whose injected source SHA is `3f6b6e8892f12956a7b2a80839a6368085ef4e0df5018be4d9dd1040fdfeee3a`. Input admission and `PreparedGraph` construction happen before its 30 s primary solve, but are charged in the process receipt. Observer accounting can alter the bounded search prefix; these are reproductions with instrumentation, not uninstrumented benchmark timings.

The four modes in modes_v2 use the same new observer-derived core. Baseline/heuristic preserve eager occupancy construction before the local cost lookup; cache/combined defer geometry until a local cost miss and reuse exact static graph-bound occupancy templates. Heuristic/combined select the existing relaxed reverse-graph travel-time ordering. Every mode retains the original limits, budgets, incurred ledgers, members and source channels. Cold raw graph validation is inside the primary cap; explicit warm graph admission reuse is inside the warm contract. External source admission/cache construction and the separate 30 s whole-road checker are measured outside the primary solve cap and included in full lifecycle costs.

Accordingly, original-cap reproduction versus common-observer cold counts are not a clean throughput comparison: their preprocessing placement and observer work differ. Even paired common-observer modes are single runs at a time cap, not fixed-work timing repetitions. More expansions at timeout mean more work completed in this recorded prefix; they do not mean the query became useful.

## Original-cap measured cause

| Representative | Labels retained | Expanded | Dominated | Edge geometry calls | Repeated same edge/time/fraction | Distinct static chords | Cost hits / misses | Geometry / exposure / dominance s |
|---|---:|---:|---:|---:|---:|---:|---|---|
| baseline03 | 89590 | 79528 | 3968 | 84493 | 72036 | 180 | 80679 / 12879 | 21.138008 / 3.542087 / 3.550665 |
| fuel_double06 | 86534 | 76776 | 3792 | 81537 | 69238 | 180 | 77609 / 12717 | 21.052458 / 3.571419 / 3.607896 |

The source-level eager expression constructs exact occupancy before `cost` can return a cached exposure. In baseline03, 84,493 edge geometry calls include72,036 repeated edge/time/fraction geometries, although only 180 static edge chords were encountered. The local cost dictionary already has 80,679 hits. Fuel_double06 has 81,537 edge calls,69,238 same-time/fraction repetitions,180 static chords and 77,609 cost hits. The profiles measure about 21.1 s geometry in each30 s solve. This is demonstrated redundant representation work; it is not an intentional modelling assumption or justification to reduce hazards.

At the original-cap cutoff, baseline03 reaches live-pop times only 0–277 s and fuel_double06 only 0–276 s within the3600 s horizon. Each expands 98 unique nodes and 12,290/12,130 unique exact keys respectively. Waiting contributes9,065/8,789 alternatives, of which8,643/8,371 repeat the same node/departure time. Time/incoming/admission keys and scenario-dose vectors remain semantically meaningful; repeated geometry or exposure evaluation can be removed without merging those states.

The original exact dominance observer records 3,408,224/3,253,782 vector comparisons and 6,635,959/6,340,967 component comparisons. Widest exact-key frontiers are 96/95, with no evicted old labels. This is compatible with many incomparable member-dose histories; the counts alone do not prove every vector necessary or a dominance defect. Retained-dose maxima are only 1.11–4.50% of member budgets in baseline03 and 2.24–8.95% in fuel_double06. Dose rejection is therefore not demonstrated as the limiting factor in these particular explored prefixes. The fuel-double candidate peak maximum is 1.758076 times the peak budget; one observed cost refuses both flame and peak. This does not justify increasing any budget.

A TIMEOUT with no observed checked incumbent cannot be called proved infeasible. No route was found in these observed prefixes; nothing here rules out a later route or an alternative unsearched history.

## Common-observer work in all 16 development phases

| Case | Mode | Phase | Generated | Retained | Dominated | Expanded | EDGE / WAIT alternatives | Cost hits / misses | Edge geometry calls |
|---|---|---|---:|---:|---:|---:|---|---|---:|
| baseline03 | baseline | cold | 78977 | 75779 | 3198 | 67049 | 71202 / 7775 | 66859 / 12118 | 71202 |
| baseline03 | baseline | warm | 86540 | 82964 | 3576 | 73665 | 78225 / 8315 | 73999 / 12541 | 78225 |
| baseline03 | cache | cold | 253007 | 240803 | 12204 | 220231 | 235174 / 21540 | 238694 / 18020 | 17470 |
| baseline03 | cache | warm | 315176 | 300327 | 14849 | 274397 | 292954 / 27134 | 300957 / 19131 | 18549 |
| baseline03 | heuristic | cold | 74524 | 70880 | 3644 | 66617 | 72653 / 3175 | 63657 / 12171 | 72653 |
| baseline03 | heuristic | warm | 88653 | 84297 | 4356 | 79330 | 86421 / 3791 | 77409 / 12803 | 86421 |
| baseline03 | combined | cold | 244049 | 232059 | 11990 | 219554 | 238117 / 10412 | 231636 / 16893 | 16519 |
| baseline03 | combined | warm | 320188 | 304908 | 15280 | 289849 | 313891 / 13299 | 308845 / 18345 | 17937 |
| fuel_double06 | baseline | cold | 76322 | 73282 | 3040 | 64827 | 68799 / 7523 | 64351 / 11971 | 68799 |
| fuel_double06 | baseline | warm | 91198 | 87328 | 3870 | 77432 | 82365 / 8833 | 78432 / 12766 | 82365 |
| fuel_double06 | cache | cold | 249961 | 237769 | 12192 | 217284 | 232115 / 21508 | 235680 / 17943 | 17395 |
| fuel_double06 | cache | warm | 311455 | 296621 | 14834 | 270806 | 289221 / 27093 | 297259 / 19055 | 18475 |
| fuel_double06 | heuristic | cold | 68838 | 65526 | 3312 | 61570 | 67135 / 2912 | 58148 / 11899 | 67135 |
| fuel_double06 | heuristic | warm | 80950 | 76958 | 3992 | 72325 | 78903 / 3450 | 69894 / 12459 | 78903 |
| fuel_double06 | combined | cold | 260361 | 247545 | 12816 | 234426 | 254408 / 11017 | 248234 / 17191 | 16811 |
| fuel_double06 | combined | warm | 322734 | 307430 | 15304 | 292225 | 316437 / 13299 | 311370 / 18366 | 17958 |

All 16 report zero dominance evictions, dose-rejected insertion attempts, cap-rejected insertion attempts, destination labels, destination contract attempts, route checks and checked incumbents. The active cap is wall time. Generated means admissible insertion attempts and equals retained plus dominated here; it does not count an exposure-refused candidate as a generated retained label.

| Case | Mode | Phase | Geometry s | Exposure s | Dominance s | Heuristic s | Validation s | Full call wall / CPU s |
|---|---|---|---:|---:|---:|---:|---:|---|
| baseline03 | baseline | cold | 18.609939 | 3.478717 | 2.829867 | 0.000234 | 4.606201 | 45.059553 / 46.276214 |
| baseline03 | baseline | warm | 21.977633 | 3.748649 | 3.482837 | 0.000267 | 0.128315 | 30.802671 / 30.517062 |
| baseline03 | cache | cold | 4.515169 | 5.368367 | 14.074159 | 0.000241 | 4.624909 | 50.409406 / 51.206344 |
| baseline03 | cache | warm | 0.191759 | 5.658111 | 22.127182 | 0.000220 | 0.132690 | 30.720072 / 30.615103 |
| baseline03 | heuristic | cold | 19.387204 | 3.606962 | 2.021523 | 0.005032 | 4.552844 | 44.804923 / 46.814911 |
| baseline03 | heuristic | warm | 22.920917 | 3.784257 | 2.647967 | 0.005089 | 0.131105 | 30.691078 / 30.648964 |
| baseline03 | combined | cold | 4.368253 | 5.415401 | 13.955594 | 0.005071 | 4.890939 | 50.980909 / 52.734701 |
| baseline03 | combined | warm | 0.734118 | 5.825171 | 21.278921 | 0.004847 | 0.139662 | 30.762889 / 30.715385 |
| fuel_double06 | baseline | cold | 18.482937 | 3.551006 | 2.829531 | 0.000241 | 4.627931 | 45.098990 / 45.824689 |
| fuel_double06 | baseline | warm | 22.017306 | 3.725813 | 3.535378 | 0.000319 | 0.134367 | 30.702132 / 30.596569 |
| fuel_double06 | cache | cold | 4.405180 | 5.419307 | 14.216481 | 0.000213 | 4.542090 | 49.417127 / 51.491537 |
| fuel_double06 | cache | warm | 0.150025 | 5.631374 | 22.349592 | 0.000210 | 0.130302 | 30.708416 / 30.644348 |
| fuel_double06 | heuristic | cold | 19.319484 | 3.701906 | 1.915150 | 0.005113 | 4.641531 | 45.273339 / 47.319749 |
| fuel_double06 | heuristic | warm | 22.878122 | 4.008759 | 2.462815 | 0.005659 | 0.134681 | 30.681141 / 30.653769 |
| fuel_double06 | combined | cold | 3.941665 | 5.165559 | 14.978009 | 0.005139 | 4.529990 | 49.332857 / 51.363251 |
| fuel_double06 | combined | warm | 0.717541 | 5.652833 | 21.514068 | 0.006815 | 0.143080 | 30.750672 / 30.448604 |

These phase timers are wall-clock observations, not exclusive CPU partitions. `search_setup`/`search_loop` include some listed child phases; original `add_inclusive` overlaps dominance and original node geometry overlaps edge geometry. Never add overlapping timers to obtain total work. Full launch CPU includes user and system accounting for every process, separately from per-call CPU.

## Cache benefit and bottleneck shift

Warm cache-only geometry is 0.191759 s for baseline03 and 0.150025 s for fuel_double06, versus 21.977633 s/22.017306 s in their warm eager baselines. The recorded local exposure dictionaries still evaluate19,132/19,056 occupancies including issue; only static geometry is reused across searches. Warm cache-only has zero static-template misses and 18,549/18,475 hits. Cold cache-only builds186 templates; this differs from the180 chords encountered by the shorter original prefixes because a larger explored prefix encounters additional edges. No geometry/source epoch is silently reset.

Removing repeated geometry allows these particular prefixes to reach274,397/270,806 expanded labels, but exact dominance now consumes22.127182 s/22.349592 s. Exact-key peak vector widths rise to 501. The dominant measured cost shifts from geometry to member-vector dominance, with5.658111 s/5.631374 s still in exposure. No search-state pruning or scenario reduction was introduced. Further acceleration must preserve those semantics or state a separately justified representation contract.

Cold cache-only complete calls are50.409406 s/49.417127 s, slower than the45.059553 s/45.098990 s cold eager calls, while both still time out. External cache construction adds4.682832 s/4.604855 s; cold source epoch preparation takes15.087953 s/14.194516 s and primary validation remains about 4.6 s. Those costs are real, not hidden behind a primary30 s search number. Warm baseline03 cache-only is 30.720072 s versus 30.802671 s eager, while fuel-double cache-only is 30.708416 s versus 30.702132 s eager: no universal full-call latency reduction is demonstrated.

| Case | Mode | Phase | Max width per key | Peak queue entries | Pending live at cutoff | Retained WAIT labels | Process lifetime RSS MiB |
|---|---|---|---:|---:|---:|---:|---:|
| baseline03 | baseline | cold | 91 | 8730 | 8730 | 7072 | 370.187500 |
| baseline03 | baseline | warm | 93 | 9317 | 9299 | 7517 | 407.343750 |
| baseline03 | cache | cold | 233 | 20615 | 20572 | 18519 | 573.015625 |
| baseline03 | cache | warm | 501 | 25982 | 25930 | 23451 | 692.296875 |
| baseline03 | heuristic | cold | 49 | 4263 | 4263 | 2434 | 361.656250 |
| baseline03 | heuristic | warm | 53 | 4967 | 4967 | 2888 | 409.000000 |
| baseline03 | combined | cold | 117 | 12563 | 12505 | 7784 | 549.281250 |
| baseline03 | combined | warm | 143 | 15059 | 15059 | 9978 | 702.843750 |
| fuel_double06 | baseline | cold | 90 | 8455 | 8455 | 6857 | 374.078125 |
| fuel_double06 | baseline | warm | 95 | 9896 | 9896 | 7972 | 383.718750 |
| fuel_double06 | cache | cold | 233 | 20571 | 20485 | 18487 | 618.578125 |
| fuel_double06 | cache | warm | 501 | 25920 | 25815 | 23410 | 728.812500 |
| fuel_double06 | heuristic | cold | 47 | 3956 | 3956 | 2246 | 351.703125 |
| fuel_double06 | heuristic | warm | 51 | 4633 | 4633 | 2630 | 412.281250 |
| fuel_double06 | combined | cold | 123 | 13119 | 13119 | 8242 | 626.390625 |
| fuel_double06 | combined | warm | 146 | 15205 | 15205 | 9978 | 702.500000 |

RSS is an isolated case/mode worker lifetime peak, including imports, source/graph snapshots and prior cold work in warm phases. It is not incremental cache allocation. Larger explored label prefixes can cost more memory despite cheaper geometry. Original observer approximate final search objects are 134,721,785/130,502,265 bytes, excluding graph/hazard, allocator overhead and observer sets; original full-worker RSS is 444.156250/438.234375 MiB. These differently scoped measures must not be conflated.

## Heuristic remains too weak to resolve these queries

The existing reverse-graph travel-time heuristic is cheap (roughly 0.005 s), ignores hazards, member-dose histories, turns, waits and destination dwell/opening conditions, and retains its existing admissibility envelope. Heuristic-only reduces warm exact-key width from 93/95 to 53/51 and waiting alternatives from 8,315/8,833 to 3,791/3,450. However, its warm expanded count changes in opposite directions across the two cases: 79,330 versus 73,665 for baseline03, 72,325 versus 77,432 for fuel_double06. These are different wall-capped prefixes, not equal-work trials.

Combined warm expands 289,849/292,225 versus 274,397/270,806 cache-only (about 5.6%/7.9% more recorded expansions), with widths 143/146 rather than 501. Yet every phase still has zero destination progress. In cold baseline03, combined expands 219,554 versus 220,231 cache-only. This is evidence that ordering changes queue composition; it does not demonstrate a reliably useful heuristic or general efficiency gain. No hazard-aware strengthening was tuned or added.

## Preserved source-binding failure and correction

All 16 modes_v1 phases fail before search: raw primary `NOT_RUN`, external failure `ADMITTED_HAZARD_NOT_EXACT_SOURCE_BRIDGE`, integrated `UNRESOLVED`. Worker execution and output completion succeeded, so the zero worker-failure count does not mean the experiment succeeded. Search counters, solver work and any route benefit are UNKNOWN, not zero-filled. Failed attempt per-call wall times span 14.053058–15.241984 s.

The demonstrated defect was in the opt-in wrapper: it supplied constructor event scenario labels where unchanged `hourly.build_hazard` uses routing IDs `construction:<construction_id[:20]>:<array index>`. The correction reproduces that original namespace, validates hazard/report request member order and preserves incurred/dose keys rather than transferring a ledger. Numerical arrays, source law, hazards, budgets and requests are unchanged. Preserved code and correction are [search_followup_pre_identity_correction.py.txt](/Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_integrated_search_followup_20261008_v1/results/corrections/search_followup_pre_identity_correction.py.txt) and [search_source_identity_correction.json](/Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_integrated_search_followup_20261008_v1/results/corrections/search_source_identity_correction.json).

Independent prefreeze review then found a separate provenance validation gap: coherently forged construction IDs with coherently changed routing/report IDs could pass a newly prepared epoch. The added guard recomputes the unchanged hourly content-derived construction digest from mode/version/parent hash/cutoff/construction fields. This tightens source admission, with no ordering or numerical change. Modes_v2 are retained as **pre-digest-guard development evidence**; they cannot certify final candidate admission. The preserved correction record is [search_construction_digest_guard.json](/Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_integrated_search_followup_20261008_v1/results/corrections/search_construction_digest_guard.json); the completed targeted controls pass, and the final readiness gate is recorded separately in `review/IMPLEMENTATION_GATE.json`.

## All development process costs retained

| Development group | Worker launches | Recorded phases | Full launch wall s | Child user CPU s | Child system CPU s | Outcome |
|---|---:|---:|---:|---:|---:|---|
| original_cap_reproductions | 2 | 2 primary | 88.046064 | 88.120231 | 7.251268 | Two unresolved TIMEOUTs |
| modes_v1 | 8 | 16 | 234.349345 | 234.063269 | 27.489975 | Source-binding defect; no search |
| modes_v2 | 8 | 16 | 628.808378 | 624.618852 | 30.194955 | All 16 unresolved TIMEOUTs |

Full launch cost is counted once per worker, including import, loading, source bridge/preparation, cold/warm work, diagnostics/output and failed attempts. Cold/warm call wall or inclusive timers must not be added again to launch totals. The original primary caps remain 30 s, 1,000,000 labels, 1,000,000 expansions and 16,384 exact-key frontier width; the optional unchanged RSS default is 3072 MiB. Wall checks are cooperative, so the measured call/lifecycle may exceed30 s. Primary TIMEOUT is never converted to infeasible or an optimum.

The bounded next decision should use the separately frozen confirmation panel and independent exact/whole-road gates. This development already rejects a claim that cache plus the existing heuristic has solved difficult incident routing. Any future dominance or temporal representation proposal needs a separate exactness argument, preserved failed cases and fresh confirmation; a larger timeout alone is not a solution.

Timing qualification: the frozen dominance timer covers the full label-add routine, including exact comparisons, frontier scans/updates, and record/heap bookkeeping. It does not isolate comparison cost. Comparison counts and integer bit lengths were not measured. A next diagnosis must distinguish these components before choosing a fix.
