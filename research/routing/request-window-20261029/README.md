# Verified routing integration and original-panel replay — 29 October 2026

The sealed Caldor deadline repair is integrated as an [opt-in routing kit](../../../experimental/window-routing/README.md). The 52 production Python files are byte-identical to the verified candidate. The historical October release, input files and submitted results are preserved.

## Fresh original 20-mission regression

We reran the exact original queue: **20 missions, two repetitions and two implementations, 80 executions**, in its original region-interleaved ABBA order. Every graph, request and native hazard packet retained its original byte hash. Both sides used cold preparation, the original scientific constraints and label/expansion caps, a **30 s complete-request deadline** and a **3,072 MiB sampled process-family RSS guard**. The reference is the unchanged original implementation. The candidate includes the cumulative signed-domain/memory repairs and request-window/check-first fix, not just one isolated component.

| Result | Original reference, rerun | Integrated candidate, rerun |
|---|---:|---:|
| Missions resolved in both repetitions | 13/20 | 20/20 |
| Checked-route missions | 13 | 15 |
| Qualifying model-scoped no-route missions | 0 | 5 |
| Unresolved executions | 14/40 | 0/40 |
| Median complete-request time in jointly checked route pairs | 6.765 s | 6.846 s |
| Maximum sampled controller + worker-family RSS | 2,209.500 MiB | 1,489.875 MiB |

There are **26 jointly checked route-execution pairs**, all with equal arrival times. The median of their candidate/reference runtime ratios is **1.023901**; the candidate is faster in **5/26**. The lower all-outcome candidate median mixes fast no-route decisions with routes. This panel supports preserved resolution, **not a speed improvement or a universal memory benefit**. These family-RSS samples include the controller and are not the historical largest-process high-water metric or proof of unsampled peak usage.

The candidate already resolved 20/20 historically: this replay confirms no coverage regression. All **56 returned-route execution witnesses** match their historical complete route and center-exposure fields. The reference's 14 unresolved executions remain eight search-label-limit stops and six insufficiently scoped refusal publications; they are not 14 wall-clock deadline failures. All 80 publications completed within the allowance. Repetitions are not independent missions or fires; Yeongdeok and Uiseong–Andong share the Gyeongbuk parent incident.

## Independent verification

A separate verifier imported no production routing/checker code. It reconstructed journeys from raw graph/request/native arrays and used independent grammar, center exposure, exact closed-cell flame-contact and time-expanded relaxed-arrival checks. A separately authored rational positive-area reference enclosed continuous-road peak flux and cumulative dose, including waits, departure and destination stay, with prior dose added once.

- **25 distinct mathematical contexts** bind all 80 executions separately to their actual source/input hashes and publication receipts.
- **18 distinct returned journeys, 72/72 member-specific thermal threshold assessments**, cover all 56 returned-route executions and their 224 member assessments. No member reference hit a record or wall cap.
- All five candidate no-route missions are independently corroborated by complete relaxed reachability with nonbinding peak limits; the decision remains conditional on the represented graph, lattice, horizon and supplied fire histories.
- All observed worker processes were cleaned up and both campaign and reference leases were released.

This is independent implementation-based verification, not an additional human or agent review. It verifies these particular mathematical inputs and witnesses; it does not establish physical wildfire accuracy, operational evacuation safety or a universal enclosure theorem.

## Separately verified Caldor/Rim repair evidence

The earlier six-mission, two-repetition paired engineering panel remains separate from the Korean regression. With identical inputs and the same 30 s/3,072 MiB limits, resolution increased from **3/6 to 6/6**: three checked Caldor routes and three scoped Rim no-route missions. All **six Caldor route executions** passed independent full-source verification (**24/24 member thresholds**); their complete-request times range from **3.223 to 3.947 s**. The baseline hit the deadline on all six Caldor attempts. Because it returned no checked Caldor routes, there is no jointly successful route runtime ratio. These retrospective source constructions are not a new forecast validation.

The first stopped monitor pilot and the intermediate 5/6 candidate are retained in the local sealed study. The final repair was not retroactively substituted into those records. `CALDOR_RIM_*` files carry the final fixed-panel outcomes and independent-review provenance.

## Inspect or reproduce

- [Exact results](RESULTS.json), [80 execution rows](EXECUTIONS.csv), [26 paired route rows](PAIRED_ROUTES.csv).
- [Native manifest and unchanged input hashes](MANIFEST.json), [protocol](PROTOCOL.md), [source provenance](SOURCE_PROVENANCE.json).
- `RAW_EXECUTIONS.jsonl.gz`: all 80 actual jobs, raw worker results, complete-process receipts and publication boundaries.
- [Independent grades and context mapping](INDEPENDENT_GRADES.json), [custody and test receipts](VERIFICATION_CUSTODY.json).
- `verification_source/`: the exact independent adapters, oracle and campaign/analysis source used in the audited local environment. Their path bindings reference the native manifest and external assets; they are retained for audit, not presented as a clean-machine runner.
- `verify_evidence.py`: recompute the public counts, paired metrics and exact rational threshold decisions without the routing implementation.
- [Opt-in API setup and regression controls](../../../experimental/window-routing/README.md).

Measured runtime: Python 3.12.14, NumPy 1.26.4, CPU, macOS 27.0.1 arm64. The independent checking phase is offline and excluded from request latency. Absolute manifest paths identify the audited local environment; external input data and the interpreter are not bundled with these evidence files. Fetch the unchanged evaluated inputs using the repository's input installer before replaying. The assembled API kit also passed a separate unscored Uljin smoke replay with arrival 3,119 s, clean shutdown and an independent optimum verdict; that extra request is excluded from the 80-run table.
