# Scratch descriptive interval supplement candidate

Status: **IMPLEMENTED_ON_INVENTED_DATA_ONLY; ACTUAL_EXECUTION_NOT_AUTHORIZED; INDEPENDENT_CANDIDATE_REVIEW_PENDING**.

This separate saved-output program implements the method fixed by `method/DESCRIPTIVE_INTERVAL_PROTOCOL_V1.json` (SHA256 `5fd4314d7bfa7523fe3a19432c61198a93f8484abb83bc20a4ae7d11937088a0`) and its separately fixed prerequisite spec (SHA256 `b69a8b57ba8ddbb92cbfdd4e07195c82058be6051a42dbee38e262a873be62e0`). No ROOT file was edited, no study artifact was inspected, and no actual supplement was executed to create this candidate.

## Fixed computation

Both cohorts remain separate: US2024, exactly273 cases/six named fires; Korea2025, exactly33 cases/four named fires. All16 fixed model columns are required. Every available interval uses the original complete common population. There is no available-fire or available-case fallback.

The program generates `default_rng(20261030).integers(0,F,size=(10000,F))` independently for each fixed cohort. Every model, absolute metric and paired AP difference uses those same whole-fire draws. Sufficient statistics cache only multiplicity vectors observed in that matrix; original frequencies and original draw order are restored before linear percentile quantiles. Unique vectors are never weighted uniformly.

Absolute metrics are pooled raw Brier, AP, ROC AUC, ten-bin ECE and clipped NLL. Paired AP is candidate minus each of persistence and dilation_best, positive favouring the candidate. Stored-score ties are exact groups; AUC gives half credit to ties. ECE uses the frozen boundaries and right=False assignment. NLL clips at1e-7 and1-1e-7. All-positive AP is1; no-positive AP is null; AUC needs both classes. If any draw is undefined, the full95% interval is null. Counts of undefined/defined draws and a separately labelled conditional-on-defined interval are retained. Nothing changes primary selection, calibration, original reports, promotion, or default models.

Original five points are evaluated by the exact SHA-pinned original baselines ASTs (`score`, `_average_precision`, `_auc`, `calibration_table`, their NumPy import and BINS/LOG_FLOOR constants), on canonical float64 entries in their frozen sorted-file order. Their scalar/None values must equal canonical raw JSON points exactly. Raw MC Brier is never compared with the variance-corrected field. NumPy1.26.4, SciPy1.13.1 and scikit-learn1.5.2 are required. The only tolerance is the prospectively prescribed rtol1e-12/atol1e-14 in independent grouped-versus-literal invented resample tests; it does not weaken original-point equality.

## Custody and actual execution boundary

An externally supplied authorization SHA256 is mandatory. The authorization cannot declare its own expected hash, and no caller boolean, URL, fixture flag or CLI policy override grants admission. The root-pinned authorization must bind the executing source, completed independent candidate review, original independent census/result review, their exact fixed checker sources, every canonical result/figure/assessment/frozen receipt, all consumed case/per-fire artifacts, immutable223-file proof and map, method/spec and frozen point source. Every consumed saved file is hashed before array loads and after computation.

The immutable `canonical_review_source_head` must match the authenticated original result-review receipt. It is not compared with current Git HEAD: later separately authorized supplement-only additions may advance HEAD while all223 original files and canonical scientific/review artifacts remain exact. The executing supplement still needs its own current root-authorized source hash. The program performs no Git operation.

The outer hash establishes byte custody under the explicitly trusted orchestration channel. Software does not authenticate a human author's identity or reviewer independence. The existing independent canonical result review provides the prior source/checkpoint/input and case-to-fire alignment evidence; this candidate does not rederive raw rasters, replay support envelopes, read model binaries, or independently establish physical truth.

An honest incomplete-scoring cohort receives null metrics and all original unavailable/failed outcomes. The other complete cohort can still be computed. A scientifically negative primary HOLD does not block an otherwise COMPLETE supported cohort. Invalid or incomplete populations, missing/extra models, changed probabilities/coordinates/labels, or individual/aggregate disagreement refuse complete-cohort intervals. No output values are used to trim support.

Actual execution acquires the existing HEAVY lease and creates an exclusive, previously nonexistent output directory under `research/forecast-v2/supplements/`. It never overwrites or resumes outputs. A late failure leaves a partial preserved directory without `COMPLETION.json`; it is not a completed computation. Final independent result review remains required for release, regardless of software completion.

## Exact future CLI

This is a command template for a later explicitly authorized integration/run. It is **not actual execution authorization**. The candidate must first pass independent source review, be integrated only into an authorized separate sidecar location, and receive the complete exogenous root receipt after the canonical report, census and original result review close. Do not execute it now.

```sh
PYTHONDONTWRITEBYTECODE=1 /absolute/path/to/venv-forecast/bin/python \
  /absolute/model-root/research/forecast-v2/supplements/candidate-source/supplement.py \
  --protocol /absolute/model-root/research/forecast-v2/supplements/candidate-source/method/DESCRIPTIVE_INTERVAL_PROTOCOL_V1.json \
  --model-root /absolute/model-root \
  --run /absolute/model-root/research/forecast-v2/executions/ROOT_AUTHORIZED_RUN \
  --results /absolute/model-root/research/forecast-v2/executions/ROOT_AUTHORIZED_RUN/RESULTS.json \
  --authorization /absolute/path/to/ROOT_AUTHORIZATION.json \
  --authorization-sha256 EXOGENOUS_ROOT_MESSAGE_SHA256 \
  --out /absolute/model-root/research/forecast-v2/supplements/ROOT_AUTHORIZED_NEW_DIRECTORY
```

`--run`, `--results`, `--out`, and actual executing script must equal the authorization's exact normalized identities. No draws/seed/model/cohort/test overrides exist.

Outputs: `DESCRIPTIVE_INTERVALS.json`, readable `README.md`, one `<cohort>_draws.npy` for each admitted complete cohort, deterministic `supplement_source.py.gz`, and final `COMPLETION.json`. Each matrix records filename, shape, little-endian int64 dtype/C-order, NPY-container SHA256 and exact payload SHA256. Completion pins result, README and source. Each JSON retains source/protocol/prerequisite/canonical/current223/input bookends, dependency versions, all16 absolute intervals and32 paired AP records. It always states promotion=false/model_inference=false.

## Invented tests and exact mocks

Run from this scratch directory only:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/venv-forecast/bin/python \
  -m pytest -q test_supplement.py --tb=short
```

All arrays and receipts in tests are invented. Full-chain fixtures copy only this candidate's already preserved source/method into a pytest temporary directory; they create306 tiny two-cell cases, fake metadata-only figures and223 invented frozen text files. They do not import ROOT production modules or read actual model/data/results.

Three in-process fixture substitutions are explicit: hard inventory SHA map is replaced with independently sealed invented inventories; the hard root-proof SHA is replaced with a sealed invented223-file proof; the real HEAVY lease is replaced by `nullcontext`. The fixture's exogenous authorization hash and independent-review identity are invented test authority, not evidence that real independent prerequisites happened. These substitutions are made through pytest monkeypatch on a temporary imported module before mutations. Production code exposes no such switch. The untouched exact checker source copies and fixed method/spec hashes are still validated in fixtures.

Controls compare every observed4/6-fire multiplicity vector with independent literal concatenation and sklearn ranking metrics, including ties, unequal fire sizes, absent classes, bin edges and NLL clipping. They check restored frequencies/matrix payloads, exact point reconciliation including a one-ULP refusal, complete16-model/32-pair handling, a nonzero manually replayed paired AP interval, full receipt positives before negatives, missing/extra/duplicate populations, unlisted/corrupt arrays, re-signed invalid probabilities/support/model columns, case/aggregate disagreement, source/checker/prerequisite/canonical mutations and output/path custody.

`evidence/initial_test_failure.json` preserves an initial incorrect test expectation: repeating the same invented fire changed NumPy reduction rounding by one ULP. The correction uses the full canonical concatenation for exact original points; no production tolerance or methodology changed. `evidence/test_run_01.log` is an earlier43-control pass, not evidence for later additions.

## Source evidence limits

Inherited graph context: parent Verify project `wfg-next-1b-20261030`, generation2026-10-30T02:11:43Z. Relevant research scripts were not tracked; searches returned0 with no pagination remainder and coverage reported no recorded issue on a best-effort basis. Exact source fallback was required and used. This is not a claim of graph completeness or fresh call-chain discovery. The separate inherited independent interval review supplies its own labelled source-chain evidence; exact source copies, hashes and original review bytes are preserved here.

The original review, canonical assessment, census and root proof have not been loaded from actual study artifacts by this work. This candidate's passing invented tests do not establish actual admission, source-data truth, current scientific performance, external clearance or independent review completion. Do not run or release the real supplement without the prescribed future authorization and review chain.
