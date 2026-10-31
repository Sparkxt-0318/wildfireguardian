# Independent review of descriptive supplement candidate6080c09b

Status: HOLD for one confirmed strict-JSON admission defect. The reviewed pooled arithmetic and null/frequency semantics are consistent with the fixed method. No actual supplement execution is authorized by this review.

## Finding

**[P2] Reject exponent-overflow numbers as nonfinite JSON values.** `supplement.strict_json` lines69-79 passes a parse_constant rejection hook, which rejects NaN/Infinity literals but does not handle a legal JSON number such as1e999. Python's decoder converts it to positive infinity; -1e999 becomes negative infinity. Nested values also pass. This violates the hard-pinned prerequisite specification's explicit rejection of nonfinite JSON values.

Three direct invented probes failed to reject positive, negative and nested exponent overflow. A fourth full-chain negative probe added an unused exponent-overflow field to an invented canonical report, re-sealed the invented custody/receipts exactly as owner adversarial fixtures do, and ran authorization plus computation. The candidate completed both invented cohorts and wrote COMPLETION.json. `NONFINITE_FULL_CHAIN_PROOF.json` pins the resulting invented result and completion artifacts. This proves the strict parser gap reaches the completed path, not merely an unused helper.

The finding concerns admission conformance; it does not demonstrate an incorrect actual scientific metric. No real result or array was read. All ordinary metric outputs in the invented example remained finite. The exogenous authorization still binds the supplied bytes; that custody property does not satisfy the separate nonfinite-value rejection requirement.

Proposed scoped repair: make float decoding reject nonfinite results, for example a parse_float hook that converts the token to float and raises AdmissionError unless math.isfinite holds, or a complete recursive finite-scalar validation after decoding. Preserve the existing duplicate-key and parse_constant guards. Keep the fixed method5fd, pooled estimands, exact original-point equality, dependency versions, numerical tolerances and every canonical/frozen scientific file unchanged. Add direct nested positive/negative exponent controls and a re-signed full-chain pre-array rejection control. This review does not implement the production repair.

## Source custody and graph scope

The original candidate source SHA-256 is6080c09b5d2d7153fb9aa46e040bb6e85688f4b632b37b9a483fdd8c66f19b30; tests SHA-256 isf7e5a02adc9677f4dfd866f365dfef0ec118d9494dc86d479802bfd3bef3e91b. Candidate manifest SHA-256 is9c27a2ecd24300ecee0eb1304f5518b27614439d8165fde52011552e7505e213. All29 sealed payloads were hash-verified and copied into this review's sealed_candidate directory before inspection/tests. All9 bundled frozen sources were decompressed and verified against their declared original SHA-256 and length, preserving originals and the owner's initial failed fixture evidence. The original candidate29 payloads were verified unchanged after review. SOURCE_CUSTODY.json and CANDIDATE_AFTER_REVIEW.json record these checks.

Verify graph project wfg-next-interval-candidate-6080c09b-20261031 was confirmed ready at the exact candidate root, generation2026-10-30T23:10:57Z. The file-scoped function search returned56 nodes, including test functions, with no remaining page. authorize both-direction depth1 trace returned16 callees and10 callers including tests, no truncation. Exact interval snippet was read. supplement.py and test_supplement.py have metadata_match/no recorded gaps. Bundled frozen Python gzip files are excluded/not_tracked; their full bytes were decoded/hash-verified, and the material point definitions/import/constants and loader/conversion order were read directly. The two bundled independent checker text copies are not_tracked; their exact bytes were verified and relevant receipt-producing definitions read directly. These facts do not establish graph completeness or original-input/physical validity.

The full994-line implementation and full479-line test source were reviewed, along with exact protocol5fd4314d7bfa7523fe3a19432c61198a93f8484abb83bc20a4ae7d11937088a0 and prerequisiteb69a8b57ba8ddbb92cbfdd4e07195c82058be6051a42dbee38e262a873be62e0. The frozen point closure matches baselines325abbe7; imported definitions are only score, _average_precision, _auc and calibration_table plus the exact NumPy import/BINS/LOG_FLOOR constants. No model/data module is imported by the point engine.

## Confirmed implementation behavior

- Fire order and16-model order are fixed by the sealed protocol. Metadata admission authenticates the exact frozen inventories and306 case IDs/identities, all expected files, complete per-fire support, source/canonical receipt identities and independent checker child summaries. Missing population is refused before array decoding.
- Draw construction uses default_rng(20261030).integers(0,F,size=(10000,F)). Multiplicity caching restores the complete original10,000 draw order/frequencies through inverse indexing. Points and intervals remain pooled cell-interval estimands, not equal-fire macro estimates.
- AP groups exact ties once, handles zero-weight groups, returns1 for all-positive draws and null for no-positive draws. AUC uses half credit for ties and is null for either absent class. Full intervals stay null when any draw or original point is undefined. Undefined-positive/negative/union counts and separately labelled conditional intervals are preserved.
- Brier is raw stored-probability SSE/count. ECE uses the exact10 floating bins and right=False assignment; clipped NLL uses1e-7 and1-1e-7. A separate c651 MC-variance-corrected diagnostic is ignored for raw-point reconciliation.
- Original five points execute the exact frozen AST closure on the canonical sorted per-fire float64 conversion/concatenation order, then require exact scalar/None equality to canonical raw JSON fields. No tolerance is introduced for original points. Grouped-versus-literal synthetic resamples use only the prospectively fixed tolerance.
- All32 paired AP candidate/reference records use the same fire draws, candidate minus persistence/dilation_best, with positive favourable direction. Existing canonical paired Brier/BSS/calibration/selection are neither recomputed nor overwritten by this program.
- Exogenous authorization hash and exact source/review/receipt/figure/inventory/map identities are required. All223 frozen paths and authorized consumed bytes have before/after custody checks. The source-head binding is the immutable reviewed canonical head, permitting separately authorized later sidecar additions without rewriting that head. Human identity/reviewer independence is explicitly outside hash authentication.
- The CLI has no seed/draw/model/cohort/test override. Actual execution is under HEAVY and uses an exclusive new separate output directory. Late protected-input failure leaves preserved partial output without COMPLETION. No production or actual command was executed by this review; --help and an invalid-option control performed no scientific work.

## Invented checks

The sealed owner's complete53 controls independently replayed PASS in25.50s. This is a host test duration, not a numerical-study performance claim. The inherited initial one-ULP fixture failure remains preserved. No original checker, canonical value or frozen source was altered.

Eight additional independent checks produced4 expected passes and4 failures exposing the JSON defect:

| Independent control | Outcome |
| --- | --- |
| CLI help and unknown-option rejection | PASS |
| Exponent-overflow positive / negative / nested value rejection | FAIL, accepted infinity in3 probes |
| Exponent overflow in unused invented canonical metadata, full-chain rejection | FAIL, received completed invented result |
| US COMPLETE retained while Korean cohort has26 SCORED/7 UNAVAILABLE | PASS, Korean metrics null/outcomes retained, no Korean NPZ decoded, no Korean draw artifact |
| Raw Brier stays tied to canonical raw field despite deliberately absurd corrected-diagnostic value | PASS |
| All-positive AUC absent-negative and undefined union counts | PASS |

The independent positive cohort test reuses only the owner's explicitly invented authority scaffolding: tiny invented306-case arrays,223 text artifacts, patched invented inventory/root-proof hashes and a null HEAVY context. It does not execute or authenticate real independent prerequisite checks, raw labels, model validity envelopes or model binaries. The test proves per-cohort gate behavior under sealed invented prerequisites. No actual US or Korean output was opened.

## Pending orchestration prerequisite

The candidate hard-pins original result checkerb3fb96f6c42a028b1e8ac67414b60e8b77735f9cf8559f784f546a7ab7929ee8 and requires an exact PASS_INDEPENDENT_SAVED_RESULT_AUDIT receipt. The parent reports a separate development mean equality HOLD under independent precision review. This reviewer has not read actual values/results and does not adjudicate that separate issue. The current candidate cannot legitimately admit that HOLD receipt. Any resulting checker/prerequisite schema amendment must be separately fixed and reviewed, with the original checker/failure retained and no fabricated PASS or canonical data edit. It must not silently amend the fixed numerical method5fd.

Actual candidate integration, actual saved-output computation and actual scientific interpretation remain NOT_RUN by this reviewer. Only this assigned scratch directory was written. Root retains authority for the narrow repair, prerequisite amendment and any later actual run.
