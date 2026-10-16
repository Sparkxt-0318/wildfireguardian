# Final-input routing constraint ablation

## Result and scope

All **200 native macOS attempts** completed in the declared 30-second complete-request allowance, with clean shutdown, no scored retry, no interruption and no memory-guard stop. The timed queue ran from 2026-10-16T04:04:56.276177+00:00 to 2026-10-16T04:23:18.482666+00:00 (18.37 minutes). This is 20 designed missions across five regional panels / four parent incidents, five selected policies and two repetitions; it is not 200 independent incidents or a physical-accuracy estimate.

| Policy | Stable own-policy routes /20 | Stable scoped refusals /20 | Stable routes passing the unchanged full policy /20 | Median complete-request time (all40 executions) |
|---|---:|---:|---:|---:|
| Travel-only | 20 | 0 | 12 | 1.632 s |
| Flame contact | 15 | 5 | 15 | 1.991 s |
| Contact + peak | 15 | 5 | 15 | 6.541 s |
| Contact + cumulative dose | 15 | 5 | 15 | 6.599 s |
| All constraints | 15 | 5 | 15 | 6.511 s |

## What the constraints contributed

Travel-only found an own-policy route for every mission, but 8 missions did not pass the full hazard policy. Their specific flame, dose, exact road-contact and/or road-thermal failures are retained separately in analysis/STABLE_MISSIONS.json and the dual-policy grade records.
Flame avoidance produced 3 later arrivals among missions where both travel-only and contact-only returned routes. Their increases were 490–531 seconds.
The remaining contact-only refusals are not search timeouts. Independent refusal corroboration and exact limitations are recorded in review/.

Adding peak or cumulative dose produced no differences in outcomes, arrival times or route hashes compared with contact-only on this panel (40 paired executions per comparison). See analysis/POLICY_DIFFERENCES.json. This provides no additional observed objective benefit from those constraints here; it does not establish that they are unnecessary on other inputs or that every alternative contact-free journey meets the dose limit. Four travel-only missions exceeded a dose limit, but each also encountered flame contact, so those failures do not isolate a dose-only contribution.

The largest planar source flux cap across these constructed inputs is 0.702991 kW/m². The exact physical-model caps and thresholds are retained per mission in POLICY_TRANSFORMS.json; the finite sentinel is proven nonbinding rather than assumed.

## Method and correctness

The same proposed solver, frozen final checkpoint identity, source packets, graph, mission rules, search allocation,30-second deadline,3072MiB sampled family guard and fresh graph preparation were retained. Only the declared flame/peak/dose constraints changed. The two repetitions used counterbalanced cyclic/reversed policy order. All source identities were frozen before the first scored run. Six once-only lifecycle controls and five unscored real policy preflights passed. The full-policy preflight reproduced the parent journey exactly.

All40 full-policy (A4) scientific outcomes match the original final native campaign: status, destination, arrival, route legs and reported centre exposure. All353 frozen files match their declared hashes at the final source check. No production source, checkpoint, threshold or default was changed.

Every published journey is independently assessed from original source data for mission grammar, centre exposure and exact road contact, and checked against own/full policies with the project adaptive road-radiation checker. The separate review adds an independently written exact grid accounting checker and source-based refusal verification. Own-policy publication acceptance is recomputed with the final receipt-bound journey_decision_v2_1 routine. A weak-policy certificate is never counted as full-policy compliance.

The independent review reconstructed all200 scored records, separately recomputed exact grid accounting for all160 published-route executions (23 distinct trajectories), and independently corroborated all40 scoped-refusal executions through five source-based contact relaxations. No own-policy route certificate was contradicted.

Independent whole-road radiation enclosure and global proof closure are not newly established by this ablation. Project adaptive certificates remain conditional on the declared construction and checker mathematics. No numerical sampling is presented as proof. The external forecasting model is neither retrained nor re-evaluated here.

## Runtime and memory interpretation

Total measured request wall time was 1086.438s and CPU time 1077.520s; campaign wall time also includes controller sampling, publication and cleanup between jobs. Largest-process RSS peaked at 1799.12MiB, while the sampled family maximum was 1797.86MiB. These are different measurements. Own-policy checking is inside each request; independent dual-policy grading is outside it. All-outcome latency medians include both routes and refusals and must not be pooled with older matched-route latency medians.

A0/A1 retain the proposed solver preparation structure while omitting inapplicable thermal checks. This is a hazard-constraint ablation, not an optimized standalone travel-only baseline or a new search-engine comparison. The inherited stage diagnostic rss_mb_after is mislabelled on Darwin (KiB); only controller byte measurements are used for reported memory values.

## Reproducibility and delivery

PROTOCOL.md, FREEZE.json, GRADING_FREEZE.json, all raw records, exact inputs, source and policy transformations, failed build evidence, preflights and independent reviews are preserved. See REPRODUCE.md and STUDY_README.md. Failed pre-freeze construction and grading-review amendments are recorded in FAILURE_AND_DEVIATION_LEDGER.md. Historical300-run Linux ablation and original80-run final campaign are not pooled with this study.
