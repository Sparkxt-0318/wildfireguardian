# Owner handoff — routing engineering, 4 October 2026

The requested routing library, JSON CLI, forecast admission boundary, update/continuity replay and checked recorded-path return are implemented in this isolated delivery. They pass labelled-fixture engineering checks. Actual forecast integration, independent historical real-fire validation, operational deployment and a novelty contribution remain unestablished. The package does not replace the established road planner.

## Start here

Extract the companion ZIP and run these commands from its directory containing `run.py`. Use Python 3.11 or newer:

```sh
python3 -B run.py check
python3 -B run.py solve --input fixtures/example.json
python3 -B run.py replay --input evidence/CONTINUITY_REPLAY_FIXTURE.json
```

The core and check command use the standard library. The optional historical vector comparator needs NumPy; the workspace road regression also needs the pinned historical dependencies and scientific environment. This library emits machine-readable requests/results, rather than deploying a network service. On the shared research machine, use the existing exclusive wrapper for any road-scale check or reported timing, as described in REPRODUCE.md.

## Finish-line answers

| Question | Delivered state and evidence |
|---|---|
| Is routing engineering complete? | Complete for the declared library/CLI contract and fixture harness. Cooperative resource limits, serialized session ownership and unavailable external evidence remain explicit. No production or safety acceptance is claimed. |
| Did fixture integration pass? | Yes: 73 packaged unit/adversarial tests; deterministic replay; full historical graph admission with a separately checked one-edge witness. The final extracted-package check is saved in evidence/PACKAGED_CHECK.json. |
| Does replanning preserve position, time and dose? | Yes under serialized session ownership. Actual history, node/interior-edge position and incoming context are validated; time/dose cannot regress; forecast updates carry history by stable member ID. Changed identities require declared conservative bounds, otherwise UNSUPPORTED. Version/generation/request guards reject delayed results. |
| Does recorded-path return work? | Yes, including explicit reverse direction/turn permission, current fractions, actual return timing, current support/hazards, incurred-plus-return dose and required endpoint dwell. A timeout can yield a separately checked alternative while primary escape remains unresolved. A closed/unsupported return is explicitly refused. |
| What was independently verified? | Separately implemented exhaustive timed-walk reference on 17 frozen cases, 510 subprocess comparisons, 468 eligible matching outcomes and 222 separately recomputed route witnesses with no failed checks. Separate cyclic/fresh development cases and adversarial review found defects that were repaired. Subagent independence is implementation/authorship separation, not external human review. Larger road witnesses receive independent feasibility checks; their global optima/refusals are not independently recertified. |
| Which solver stays default? | The established eager/activation planner remains recommended for its historical road workload. The new compatible-payload library defaults to exact full-vector arrival-order search. Matched A* and the single pruning arm are optional; no new road-wide promotion gate passed. The unchanged legacy vector component is compared only on its compatible tiny subset. |
| Did optimization improve without regressions? | Static legal-suffix pruning preserved tiny outcomes but reduced no expansions (135 versus 135 per mode, summed over three repetitions), increased median time/memory and remains off. A* used 117 versus Dijkstra's 135 expansions in the same tiny cases; that is a bounded queue-order result. No novelty or universal gain is claimed. |
| What must the mentor supply? | A real sample/model-schema version; graph revision and CRS/grid binding; aligned flame-contact and incident heat-flux intervals in kW/m² with full support; issue/availability/validity/time-origin semantics; stable scenario IDs/provenance; a defensible past-dose mapping if IDs change. Supply an incurred-dose estimate and agree peak/dose/dwell policy separately. INTERFACE.md and fixtures/example.json show the exact adapter contract. |
| What is unavailable for independent real-fire validation? | Mentor predictions and independent matched time-resolved flame/thermal road truth, destination conditions, calibrated vehicle thresholds and passability validation. Forecast accuracy and evacuation decision value are not evaluated. Daejeon acquisitions and the DSM do not supply Nangok2023 thermal/passability truth. |

## Evidence and boundaries

`BENCHMARKS.md` retains every case, unavailable row, per-query timing/expansion regression and prior negative finding. Raw frozen small comparisons are in `evidence/benchmark/`; the separate full established road comparison is in `evidence/road_comparison/`. The small legacy arm is the repaired vector component, not the complete established planner. The full graph smoke has 5,765 nodes / 13,976 directed edges and generated uniform hazards; it deliberately does not reproduce difficult state expansion.

The six hard exposed road regressions have one cold repetition with the published 60 s / 3,072 MiB / 95 s watchdog, no hidden event proxy or storage cap. Their final status: {"rows": 24, "independent_route_member_checks": 120, "independent_failures": [], "global_optima_or_refusals_independently_recertified": false, "warm_and_repeats": "NOT_RUN_ON_HARD_ROADS; TINY_MATCHED_STUDY_HAS_BOTH"}.

Read ROUTING_SPEC.md before interpreting a certificate: exact represented-input arithmetic and declared-lattice optimality do not establish continuous-time or physical safety. Unknown support withholds global certificates. History/member carry-forward bounds are externally supplied assumptions. Destination dwell is always checked for peak/flame/support; route-only versus including-dwell dose scope is explicit. Embers and secondary ignition are absent. Mid-edge reversal is available only when explicitly permitted and exactly representable. Cycles remain legal; waiting does not reset turns or postpone physical arrival admission.

The session has a single serialized owner. It is not a thread-safe shared object. Production worker results must be immutable snapshots committed by that owner. No forecast-format decoder has been tested against a mentor sample; a compatible JSON payload can be admitted directly, while any new tile/array format needs its narrow checked decoder.

## Authorship, preservation and known incident

A handled core integration, B continuity/return, C the independently authored checker/reference/frozen cases and mathematical review, D fresh adversarial cross-review, and E mechanical performance tooling. A–D used GPT-6.1 Sol; E used the lower-cost GPT-6 Luna for tooling whose results were adjudicated by the coordinator. The coordinator owned validation, numerical/geometry/interface repairs, legacy matching, the one generic pruning method, official runs, reporting and packaging. C/D findings were recorded before integration; subsequent coordinator repairs are disclosed in reviews rather than represented as external independent certification.

Original completion/controlled/novelty manifests verified 32/50/53 files. The pipeline manifest was already stale at startup: 236 of 472 mismatches, including one lane-B audit script, mostly mutable cache/result rows. Its current source bytes were pinned; its archived aggregate hash is not represented as current. MANIFEST.json and evidence/PRESERVATION_CHECK.json record start/end preservation separately from concurrent specialized-study changes. Sealed labels, credentials and scientific eligibility were not accessed or changed.

One road fixture export unexpectedly ran past the light-job threshold while another study owned the lane. Its overlap and unknown external effect are recorded in evidence/MEASUREMENT_LANE_INCIDENT.json. The export's runtime is not a reported performance result. All later official comparisons and road checks use the shared exclusive wrapper. No concurrent process was stopped and no frozen original source/protocol/result was edited by this task.

The coordinator alone appends a dated evidence/artifact/limits entry to WildfireGuardian_Canonical_Context.md under its inode flock, with prefix preservation and hashes. The archive includes full source, fixtures, independent checks, reviews, protocols, raw rows and manifests. No merge, forecast training, hardware change or publication is part of this delivery.
