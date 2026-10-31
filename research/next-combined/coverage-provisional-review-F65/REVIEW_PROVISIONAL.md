# Independent provisional F65 preflight metadata review

No confirmed inconsistency found in the authorized bounded saved-metadata/custody review. This does not pass the live coverage gate or independently replay actual member/cache values. The original actual HOLD remains preserved.

The four parent-pinned artifacts match exactly:

| Artifact | SHA-256 |
| --- | --- |
| PREFLIGHT_RECEIPT.json | 6df0eaf4f3daf6e67c3cbe3c0cf7e5cd85f5498d1bf7e26fa19f66ceccedf8e7 |
| COVERAGE_PROVISIONAL.json | 12ed2aae675e78a355312c24d56fd2183b313c0238c3de8a2723964e71c3bbd6 |
| candidate_raw.json.gz | 5a45558a5b32c1a2350e52871fb010c828757c82c6e5bbee2e05efdf45987b29 |
| PREFLIGHT.log | a5e4ae58a2fd525ddc220090fe3547b7b0cb3ef34d3404d24c610f24f01bdfd0 |

The decompressed diagnostic hash is fe69aac33e242197e3e0fabfe141f5e4deb7a8684945b8ec9625d8cf30f395f8, matching the execution receipt and log. The wrapper preserves every raw result field, changes status to PROVISIONAL_NOT_FOR_REGISTRY and adds explicit execution/qualification fields. No cases or unavailable classifications were silently removed.

## Execution identity and admission status

The executing auditor is pinned before/after at65a7917868b70e00881722bda8ab2af71688fe78bf88128fad0376537f1d6536. The saved command points to that exact candidate file. The receipt records exit0, acquisition11:57:25.567718Z, completion11:57:43.667672Z and elapsed18.097600s. These are saved host execution facts, not performance or physical evidence.

All61 saved before/after checked source identities match, and independently rehashing those source files still matches. The raw result's generic source_sha256 map describes the checked live dependencies, including old main F1753cf31. It does not identify the executing auditor by itself. The separate receipt and wrapper explicitly identify executed F65 and acknowledge that F175 is a checked dependency. Those identities must remain separate; raw diagnostic JSON must not be described as produced by F175.

Only the exposed provisional wrapper has a documented old-main refusal. **Raw diagnostic nonadmission remains UNTESTED.** This review did not extract or submit raw PASS_COMPLETE_FIT_MEMBERSHIP JSON to any registry/selection path. Compression and a diagnostic pathname are not an admission proof. The execution receipt correctly limits its refusal test to the wrapper.

No live FIT_COVERAGE.json, MODEL_SELECTION.json or BLIND_REGISTRY.json exists at this review point. The original failed actual-audit receipt SHA ce7727c10e68cce536dbb0f1a56b68add941a46fab8c244f12ddf23e527d5633 still matches. A fresh canonical live-main audit after the authorized source boundary remains mandatory.

## Independently reconstructed metadata accounting

The saved expected ledger contains23US fit events and11Korean kriged-only events, with all34 kriged ledger keys retained. Every saved descriptor has a consistent event/kind/UTC clock and canonical case ID. Flattening those ledgers in the frozen order reproduces1,303 perimeter cases and3,088 additional kriged cases,4,391 total mixed cases, with unique IDs and matching ordered/membership digests.

All57 full-cache and57 first-three-cache identity records agree with the saved source-recomputed cache-audit records on counts, exact case IDs, hashes and sample value identities. The referenced cache-audit JSON retains4,296environment caches,114active sample caches and34excluded obsolete caches, a passing no-change status and no mismatches. This cross-checks saved authentication predicates and custody. It does not independently read, rebuild or compare the actual cache arrays, dtypes, channel values or raster sources.

All21development and7final phase records bind their saved fit metadata and execution receipts, complete reviewed producer profiles and intended phases. Development training/validation case lists were reconstructed from the frozen first-three-per-event-and-kind rule and fold ordering. Pure development training counts are48/30/60; mixed counts111/75/135. Validation counts are21/39/9. Historical cap160 is nonbinding for these populations; the later corrected spotting fold's explicit cap0 remains distinct. All three epochs retain positive updates and exact attempted/inferred optimized-plus-unsupported partitions. Each mixed development fold records seven source-inferred unsupported cases per epoch.

Each pure final variant retains1,303optimizer steps in each of three epochs and no skips, with historical IDs explicitly source-derived rather than runtime-recorded. Mixed final retains4,391distinct runtime attempted IDs per epoch,4,376updates and15explicit skipped IDs. Independent metadata set/count/hash checks reproduce that disjoint partition. Optimized mixed IDs are inferred from attempts minus runtime skipped IDs; they were not separately runtime-logged optimizer IDs. Support-envelope proofs retain their NOT_PER_OPTIMIZER_MASK_REPLAY qualification. No loss or unsupported case is turned into a zero Brier or quality score.

The script checks9,612 deterministic metadata predicates, all passing. These are correlated bookkeeping checks, not9,612 independent test cases, fires or empirical observations. No study forecast quality or scientific superiority was evaluated.

## Scope and next gate

Scoped clearance is granted for this provisional receipt and its internally consistent saved metadata under the earlier exact F65 source review. It does not establish independent actual input/member/cache-value replay, actual coverage admission, a frozen registry or permission for held-out inference. Keep the preflight artifacts provisional. Wait for all12 a06 cases, aggregate/receipt closure and source bookends before the root-authorized live application and canonical audit. Any real canonical mismatch remains HOLD.

The review read approved JSON/gzip metadata, hashed metadata/execution and first-party source files, and checked absence of live freeze artifacts. It did not open actual state/cache/raster/model arrays, deserialize a model, run a numerical forecast or fit, inspect held-out quality, execute the actual auditor or use the heavy lease. No track or integration file was edited.

Evidence: review_provisional.py, REVIEW_PROVISIONAL.json/.log and MANIFEST.json. Source context remains Tier2 projectwfg-next-1b-coverage-v2-65a79178-20261030, generation2026-10-30T11:40:54Z, ready at the reviewed candidate root. The auditor is excluded by design; its relevant complete source was already reviewed under the exact65pin. This review confirms that same executable pin. JSON/provenance files were parsed directly. Graph/source coverage is best-effort, not proof of physical or data completeness.
