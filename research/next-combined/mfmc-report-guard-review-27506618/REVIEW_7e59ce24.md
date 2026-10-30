# Independent MF/MC report guard review

Review head: `7e59ce24a8d45e8d23b9efedb54bf3fb9a6a9806`.
Report source SHA-256: `2fce10538666e57d7036ceba8b601172ff5aefccf934265c6d80b11c8d2ad54c`.

Verdict: HOLD for one command-admission defect family. The actual completed comparison's separate independent 12/66 reconciliation remains valid; this review found a report-loader guard bypass in synthetic receipts. No actual comparison output, model, raw field/data array or heldout result was opened.

## P2: The effective argv guard ignores accepted overrides and invalid extras

The command-control loop in `report.py` finds only exact standalone option tokens. A trailing `--seed=7` or argparse abbreviation `--se=7` overrides the frozen seed in the real pinned parser, while the guard still reads the earlier standalone `--seed 0`. The report loader accepts the re-signed synthetic case as execution-complete with saved row seed0. Equivalent accepted bypasses affect N, case index, artifact suffix, manifest, thread count and unchecked run/event overrides. The loader also accepts receipts containing `--` followed by extra arguments, an unknown option or an extra positional token, although the pinned parser rejects each command with exit2.

`COMMAND_MATRIX_7e59.json` records 22 canonical, duplicate, mixed-form, equals, abbreviated, separator, unknown-option and positional scenarios. It is a failure matrix, not a passing test count. Actual parser behavior was obtained by extracting only the exact argparse-declaration AST from pinned P88d source, stopping before dispatch and executing no pipeline, model or numerical operation. The canonical full historical argv is positive; the existing last-standalone wrong-seed and wrong-dispatch controls refuse. Some last-effective-value duplicate forms also preserve the intended values, but strict rejection of every noncanonical form is acceptable for this fixed historical producer.

Repair should admit only the known canonical a06 argv form, or correctly parse all accepted forms and validate every effective parameter before authentication. A partial last-token scan is insufficient. The actual saved canonical commands and numerical outcomes do not require rerunning.

## Scoped positive evidence

All 13 separate source/custody/manual-plot controls pass. The independent controls copy the exact original 61 source-file bytes into synthetic fixtures and keep the production hardcoded EB51 trust anchor unchanged. Original F175 and archived live F65 positives authenticate the old producer; an unknown live auditor, corrupted original snapshot and fully re-signed changed numerical dependency refuse. The complete original source map matches the independently prepared source contract from before actual result access.

The manual plot controls reproduce six Korean cutoffs across three unique events, preserve all five horizon positions and null 12/24-hour points, check an independently set median of 0.035, distinguish known support from absent active points, and retain the min/max-not-CI and not-physical-flaming disclosures. Shared runtime totals count 12 joint24h MC/MF calls and six separate survey calls once each. The 34 evidence-manifest payloads, gzip original-byte hashes and all 17 protected prior function ASTs remain exact.

Both archived final fixed synthetic figures, partial support and all unavailable, were independently viewed. Their axes, horizon positions, support table, unique-event denominator, unavailable label and scope text are visible on 1050x720 canvases. These visuals concern synthetic metadata only. The source continues to distinguish summary authentication from unsaved-array recomputation.

## Evidence and limits

The initial equals-form probe and complete old report/test/P88d sources are preserved in `PRESERVED_SOURCE.json` and lossless gzip archives. `CLOSURE_PLOT_CONTROLS_7e59.json` records 13/13 controls; the command matrix retains each accepted or refused outcome. The owner's existing 68 targeted-test receipt was inspected but that suite was not duplicated during this independent review.

Tier 2 graph project `wfg-next-1b-audit-7e59ce24-20261030`, generation `2026-10-30T12:33:21Z`, is ready. The report scripts subtree is excluded, so all changed guard/plot functions and the complete material main caller were read directly. The narrowed test graph query returned all 21 functions without pagination; relevant test and manifest metadata coverage is current. Figures and compressed source evidence were inspected directly. Graph coverage is a best-effort signal only.

No tracked edit, source checkout, inference, field recomputation, merge or publication occurred. The detached audit worktree remains at 7e59 and clean. This review does not clear any prospective claim, full-cohort metric gate or physical forecast validity.
