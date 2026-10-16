# Independent publication-tools source review

**PASS for the bounded publication/reproduction helper scope.** No numerical routing campaign was run by this review, and no scientific source was changed. The packaging owner performs the final extraction/setup smoke separately.

## What was checked

- `prepare_reproduction.py` reconstructs the runner's required `<workspace>/outputs/<new-study>/study/` layout. It refuses an existing destination, verifies all scientific and grader identities, copies both manifest file sets, preserves the pre-run source review, and does not copy scored raw records.
- An existing shared lease is never overwritten or released. A missing lease is created exclusively with explicit fresh-workspace provenance and the `released_by` field required by the unchanged lease interface.
- All grading dependencies, including `study/runner/grade_route.py`, are included and rechecked after copying. Relative paths in both manifests are validated.
- The helper prints only fresh preflight, primary execution and grading commands. It explicitly states that a new independent review and report are required. The preserved original report writer is not advertised as a fresh-campaign reporting step.
- `verify_published_results.py` checks listed file hashes, 200 unique execution keys, the five policy denominators, common mission sets, repetition membership, outcome counts and the three stable-outcome summary fields. It assumes installation one directory below the published addition root. It does not rerun routing, reverify route constraints, recompute every cost statistic, authenticate authorship, or independently prove radiation bounds.
- `verify_archive.py` checks listed extracted member sizes and hashes. It belongs at the archive root next to `ARCHIVE_MANIFEST.json`. Its statement that it verifies preserved bytes, rather than scientific conclusions, is accurate.

## Concrete issues corrected before publication

1. A fresh FREE lease initially lacked the field required by the unchanged acquisition interface. Initialization provenance now includes that field without altering existing leases.
2. The first source-copy set omitted a grader listed only in the separate grading manifest. The helper now unions both manifest sets and verifies both copied sets.
3. The initial fresh-run instructions invoked a historical report writer dependent on original-only log files and fixed original-study review claims. That command has been removed; policy transformations are copied for provenance, and the receipt clearly requires new review/reporting.

No further concrete defect was found in this bounded exact-source review. Graph coverage for these current output files was unavailable under the older indexed generation; every helper was read directly in full. The scientific study's accepted results and limits remain unchanged.

## Reviewed helper hashes

- `prepare_reproduction.py`: `60e2fc39d80ca1f0594d0f2f1bc430572472bf77c44b8b15266cf713b59e740d`
- `verify_published_results.py`: `68db59fbfe53c9d9ccd3cb3c798bdb7e443c01cf0f3526b7a4438910c49efb6e`
- `verify_archive.py`: `b767eb387fdf1987a9d3a27f3079b1008de73fd1012414e7990536b0fdb10f9f`

Reviewed at 2026-10-16T04:45:19.542557+00:00.
