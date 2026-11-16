# Experimental corridor router

This research worker searches road corridors with time-dependent flame contact, permitted waiting and destination-stay constraints. For difficult heat-constrained journeys it combines a conservative exposure lower bound with candidate discovery and a directed thermal upper check. A bounded refinement attempts to reduce driving at a fixed arrival. Its result distinguishes a checked route, a model-scoped no-route proof and an unresolved request.

The worker is experimental. Its historical evaluation uses reconstructed scenarios and model-dependent exposure budgets. It is intended for research and comparison, not live evacuation decisions.

## Build and tests

The two numerical extensions are built locally from the accompanying C++ source. No machine-specific compiled library is required in the repository. Python, NumPy, a C++17 compiler and MPFR are required for the complete worker. Use the package's native build and tests from the repository root:

```sh
python experimental/corridor-router-v8/build_native.py
python -m unittest discover -s experimental/corridor-router-v8/tests
```

## Execution and input availability

`update.py` is the historical job-file worker entry point. `prepare_job.py` can rebind an original frozen job to matching data paths and the checked-in experimental routing stack:

```sh
python experimental/corridor-router-v8/prepare_job.py \
  --template FROZEN_JOB.json --template-sha256 TRUSTED_SHA256 \
  --graph GRAPH.json --request REQUEST.json \
  --packet PACKET_DIRECTORY --output NEW_OUTPUT_DIRECTORY
```

The adapter verifies the job against the supplied digest, then verifies the graph, request, packet and checker hashes in the template. Obtain the digest from a separately trusted source. It defaults to a cold graph preparation. The included supervisor runs the prepared worker, applies the 30-second wall limit and sampled process-family-plus-controller memory guard, and writes resource receipts:

```sh
python experimental/corridor-router-v8/run_guarded.py NEW_OUTPUT_DIRECTORY/job.json
```

To reuse a matching authenticated graph cache, add `--cache CACHE_DIRECTORY` to both commands. The cache must satisfy the existing prepared-graph authentication rules, including their path requirements. The data, original frozen job bundle and historical 273-case campaign controller are not distributed with this directory. The code in this package is not an independently callable replacement for the project's standard routing API. A complete request needs its original checker and fallback as well as the worker.

The historical manifests used local absolute paths and source hashes. The source forecast and road data have their own access, attribution and redistribution terms. See the repository's `NOTICE` and `docs/DATA_AND_RIGHTS.md`. A clean clone can run the included small controls, but cannot reproduce the full 273-case experiment from the materials included here.

## Evidence and interpretation

The historical v8 campaign produced 189 checked routes and 84 model-scoped no-route decisions in 273 requests under a 30-second complete-request and 3,072 MiB sampled memory limit. Independent review confirmed 187 earliest-arrival and 168 minimum-driving claims. Two Uiseong–Andong routes were feasible with independently bounded earliest-arrival gaps of seven and four seconds. One other route kept its arrival while requiring 186 additional seconds of driving relative to the previous run.

The 273 requests share five historical fires and use retrospective forecast reconstructions. The focus cases guided development. Under the historical permissive missing-input policy, 163 of the 189 returned routes touched at least one cell-hour without native forecast support. The historical maximum native request time was 28.244 seconds, close to the 30-second deadline. A subsequent local rerun of all 273 cases used the packaged worker and the same frozen inputs. Independent review confirmed the same 189 routes and 84 model-scoped no-route decisions, including 187 earliest-arrival and 168 minimum-driving proofs. All 273 finished under the sampled guard. The slowest request took 28.950 seconds, the highest sampled peak was 1,642 MiB, and the 273 guarded requests totaled 563.560 seconds. The full supervisor command took at most 29.009 seconds, and adapter preparation plus that command took at most 29.035 seconds. Graph-cache copying and earlier forecast generation were outside those timers, as in the historical study.

On 15 November 2026, two guarded smoke requests exercised the refactored worker and included supervisor using the original historical inputs and authenticated warm graph caches. FN1 returned the checked 3,187-second arrival in 28.022 seconds, with 1,249.375 MiB peak sampled memory. FT1 returned the checked 3,074-second arrival in 22.155 seconds, with 1,003.438 MiB peak sampled memory. Both requests exited cleanly under the same nominal limits. These two smokes are not an independent review or a full rerun of the 273-case experiment. [Smoke records](evidence/packaged_smokes.json)

The historical decision ledger, case-level proof summaries, lower-bound trials, timing summary and source hashes are in [`evidence/`](evidence/README.md). That folder describes what the records establish and what additional inputs would be needed to reproduce the historical campaign.

## Full packaged-worker rerun

The local full-census rerun used frozen package commit `61b3a4c8464e6c5499578d4d4acae7f1354b6122`, original forecast and road inputs, authenticated private warm caches, and a fixed 30-second / 3,072 MiB sampled guard. An independent reviewer rechecked every route, model refusal, claimed optimality, input identity and resource receipt. The two difficult paths also passed the separate original adaptive thermal checker offline. All 273 decision statuses and all 189 route arrivals and driving durations matched the original v8 outcomes. The two focus routes were accepted as feasible without a completed earliest proof. FN1 and FT1 remain within independently established arrival intervals [3180, 3187] and [3070, 3074] seconds after forecast issue.

The follow-up adapter change records the packaged worker's identity and checks it during supervision. That provenance correction and its tests were applied after the frozen run and do not change the measured router source. [Packaged rerun evidence](evidence/README.md)

## Native forecast support policy

By default, the worker applies `REQUIRE_NATIVE_SUPPORT`. This policy requires every cell touched during the whole journey, including movement, legal waits and the complete destination stay, to have native forecast support for every scenario member at the relevant hour. Closed road-cell intersections include gridlines and corner touches. The data are read from the frozen packet's `native_hourly_valid` mask. A cell outside the forecast grid is treated as unsupported.

The worker first searches under the original modeled flame restrictions. If its candidate crosses unsupported cells, it searches for an alternative over the supported road-and-time domain, then checks the reconstructed journey against the original fire and heat constraints. A fully checked supported candidate is labeled with the support policy. An earliest-arrival certificate for this restricted search applies to supported journeys. Where the supported search cannot produce a checked route, the result is `UNRESOLVED`; unavailable forecast input does not establish that a route is physically impossible. The worker may still publish an unrestricted, model-scoped no-route proof when its original unrestricted search or original heat lower bound actually proves one.

The legacy `HISTORICAL_ZERO_FILL` policy preserves the old benchmark behavior only when explicitly selected in the job. Do not interpret a supported-cell route as a field safety assessment. This policy neither fills missing forecast data nor establishes fire or radiation information for unsupported surrounding cells.

The full-census policy comparison, guard definition and independently checked results are reported separately in the supporting evidence.

## Native-support rerun

All 273 original requests were rerun with native-support enforcement, including support-checked driving refinement. The independently verified result is 28 supported checked journeys, 78 no-route decisions proved under the original configured model, and 167 unresolved requests. Of the 28, 26 have independently proved earliest arrival among supported journeys and 23 have a verified minimum-driving claim. Every returned journey has native forecast support in the occupied cells and hours.

The earlier permissive run returned 189 routes, of which 163 touched missing native input. Two of those 163 now have supported alternatives, with arrivals 71 and 2 seconds later. The other 161 return unresolved. The earlier run had 84 model-scoped no-route decisions; 78 were reproduced and six are now unresolved. All 26 earlier supported journeys retained their arrival and driving time.

No guard stopped a request. Maximum worker wall time was 28.834 seconds, maximum sampled family-plus-supervisor RSS was 1,341.297 MiB, and the largest adapter-plus-supervisor elapsed time was 28.922 seconds. Forecast generation and cache copying were outside the timed worker boundary. Native-validity masks were checked against the original source crops; the input observations were not recovered or filled. These results do not establish coverage for unknown fire or radiation sources outside the occupied route.

Both the initial supported-routing run and the final tie-preserving run were retained. The independent verifier's first final-run audit encountered a type error when an integer-valued clock was decoded as a float. The verifier was corrected with explicit integer checks and the complete audit restarted; it finished with zero discrepancies. The frozen worker and measured outputs were unchanged. [Case ledger and proofs](evidence/README.md)

## Forecast-input recovery on all 273 requests

After recovering forecast inputs for 16 of 18 windows, we reran every original request with the same router and limits. Independent checks found **35 supported routes, 114 model-scoped no-route proofs and 124 unresolved cases**, compared with 28, 78 and 167 before recovery. All returned journeys had native forecast support throughout driving, permitted waits and destination stays.

Of the 153 cases that previously had a missing endpoint, 11 now have complete endpoint coverage and 7 have a checked route. 17 others gained partial coverage and 125 gained no fully supported endpoint cells. Across the whole cohort, the archive supplied 4,442 additional supported road-grid cell-hours. All previously supported probabilities and scenario ignition draws were preserved.

[Case ledger, sensor sources and independent checks](evidence/forecast_input_recovery/README.md)
