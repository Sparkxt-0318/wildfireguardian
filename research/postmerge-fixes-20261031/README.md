# Post-merge compatibility and regression fixes — 31 October 2026

These repairs address the combined Main snapshot e6dd155b after PRs85–88 merged. All scientific HOLDs, the negative forecast superiority result and c651/default integration remain unchanged. No training, inference, routing benchmark, metric or figure was regenerated.

- Provenance: retain the historical 61-file producer closure. A single explicitly pinned callback-enabled rollout is admitted only by reconstructing the exact two insertions (three added lines) from the authenticated historical file and comparing its entire byte hash. Other edits, including appended comments or changes to another dependency, remain rejected. This is scoped source compatibility, not retroactive proof that earlier jobs executed newer checks.
- CI: the protected gates job now requires both earlier routing regressions and the new forecast/experimental job. Full Git history supplies preserved source versions used by compatibility tests. CPU dependencies and thread counts are pinned/configured.
- Scoring: unresolved computations make neither route nor no-route assertions. Both error metrics stay unknown, with unresolved counts reported separately and excluded from known error denominators.
- Radiation: an explicit extinction field must match the ignition grid and be finite; invalid supplied data never silently selects default residence. Existing supported-domain, unknown-geometry and physics restrictions remain.
- SIPP: expired deadlines are checked before the initial-destination shortcut and after preparation. The public planner checks the complete elapsed allowance across every return branch, including witness validation. The known-footprint outer gate remains intact.
- Documentation: the combined readiness report is explicitly identified as a pre-merge archive; its historical contents and statuses remain verbatim below the new status note.

## Preservation and verification

FROZEN_GIT_BLOBS.json binds 3,640 pre-existing frozen artifacts, including integration files, recorded model outputs/checkpoints and research evidence. The live audit tool and live combined README are the only excluded research paths. tools/verify_postmerge_preservation.py checks exact bytes without decoding scientific payloads. Original overlay source ledgers remain historical; POSTMERGE_SOURCE_SHA256.json records this repaired source separately. No old benchmark is attributed to the new code.

The independent post-merge regressions use explicit counterexamples, outcome/denominator checks, historical-source reconstruction and dependency-mutation rejection. Existing export tests also check unchanged-default byte behavior and an observer attempting to mutate its input. This is independent implementation-based verification, not a new external human/agent review or physical validation. Local suite receipts and CI provide the exact final execution results.

## Executed local validation

| Suite | Result | Receipt |
|---|---|---|
| Full forecast plus independent post-merge regressions | 3,531 passed; 551 dependency/deprecation warnings | [forecast log](verification/forecast_tests.log) |
| Full radiation, export, scenario-member, SIPP and truth suites in the complete forecast environment | 177 passed, no skips | [complete overlay log](verification/complete_overlay_r3_tests.log) |
| Frozen scientific artifacts | 3,640 exact Git blobs unchanged | [preservation log](verification/frozen_preservation.log) |

The forecast count includes 24 new counterexample regressions. The complete overlay count includes callback default-behavior and mutation-isolation controls. These are software verification results, not new scientific performance measurements.

Earlier local attempts are retained: the lean routing environment passed 171 tests and skipped four dependency-gated cases; the first complete-environment attempt could not collect without Hypothesis; the next passed 174 tests and failed three bridge imports without the frozen wfg_latest package. Installing the pinned test dependency and this repository's unchanged integration package produced the final 177/177 result. CI explicitly installs both, so dependency-gated tests cannot silently substitute for this full run. The serialized execution receipts record cleanup and lease release, including the intentionally separate process group exercised by lifecycle tests.

[Source hashes](POSTMERGE_SOURCE_SHA256.json), [test commands](verification/TEST_RESULTS.json), [complete overlay command](verification/COMPLETE_OVERLAY_R3_RESULTS.json), and the original failed logs provide the audit trail. The protected GitHub gates job must also pass on the final PR revision before merge.
