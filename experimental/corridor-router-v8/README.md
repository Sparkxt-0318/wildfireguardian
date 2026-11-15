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

The 273 requests share five historical fires and use retrospective forecast reconstructions. The focus cases guided development. Under the historical permissive missing-input policy, 163 of the 189 returned routes touched at least one cell-hour without native forecast support. The historical maximum native request time was 28.244 seconds, close to the 30-second deadline. These recorded results refer to the original frozen worker and data, not a benchmark of the refactored package.

On 15 November 2026, two guarded smoke requests exercised the refactored worker and included supervisor using the original historical inputs and authenticated warm graph caches. FN1 returned the checked 3,187-second arrival in 28.022 seconds, with 1,249.375 MiB peak sampled memory. FT1 returned the checked 3,074-second arrival in 22.155 seconds, with 1,003.438 MiB peak sampled memory. Both requests exited cleanly under the same nominal limits. These two smokes are not an independent review or a full rerun of the 273-case experiment. [Smoke records](evidence/packaged_smokes.json)

The historical decision ledger, case-level proof summaries, lower-bound trials, timing summary and source hashes are in [`evidence/`](evidence/README.md). That folder describes what the records establish and what additional inputs would be needed to reproduce the historical campaign.
