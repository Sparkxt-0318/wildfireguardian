# Prepared additive current-cohort census guard

Actual reconciliation: NOT RUN. This guard is prepared for the parent's authorized final saved-result review after both current assessments finish. No live heldout or Korean assessment, array, model or scorer was opened during preparation.

`check_census.py` loads the two immutable timestamp-inventory objects from commit 6887dc618253e6568c6cbbfd3c9a96f1d0d86b70 with `git --no-replace-objects show`. It independently requires exact hardcoded SHA-256 pins before opening assessment metadata. There is no caller-selected expected map or empty-list fallback. The guard requires all 273 US cases across six fires and all 33 Korean windows across four events, exactly once each, with exact four-field event/cutoff/endpoint/hours identities and the current producer's 24-character SHA-256 case-ID formula. Per-fire counts and declared event membership must match. Missing, duplicated, replaced or relabelled cases cannot become a complete census.

SCORED, UNAVAILABLE and FAILED are all legitimate census outcomes. Honest unavailable/failed records satisfy membership when retained; the guard never fabricates a zero score or imposes new metric policy. An assessment claiming COMPLETE while containing an unscored case refuses. HOLD can retain every expected case and still pass this census. Census completeness is not a scientific, quality or promotion decision.

Case iteration order and declared event order are reported as diagnostics. Membership completeness is order-independent. The existing independent result checker retains its ordered event/interval/array-alignment tests. Its exact source remains unchanged at SHA-256 b3fb96f6c42a028b1e8ac67414b60e8b77735f9cf8559f784f546a7ab7929ee8. This additive guard does not replace its hashes, arrays, metrics, failure ledger, calibration, bootstrap or figure checks.

Synthetic validation: 34/34 controls pass. Four full 306-case positives cover all-scored, honest mixed outcomes, all-unavailable and all-failed. Additional controls detect omissions, duplicates, relabelled events, replaced cutoffs, wrong hours or IDs, extra case fields, wrong declarations, false COMPLETE statuses, invalid outcomes, empty populations and changed inventory pins. A reordered case list remains census-complete and is explicitly flagged as reordered. The empty caller inventory-map path refuses. Only fabricated assessment dictionaries and the two frozen metadata inventories were read.

Exact future command, only after parent authorization:

```sh
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 \
  /Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/current-cohort-census-review/check_census.py \
  --repo /Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b \
  --us-assessment /Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/forecast/runs/20261030_perimeter_trained/execution_v3/heldout/ASSESSMENT.json \
  --korean-assessment /Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/forecast/runs/20261030_perimeter_trained/execution_v3/korean2025/ASSESSMENT.json \
  --out /Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/current-cohort-census-review/ACTUAL_CENSUS.json
```

The immutable inventories and their pins are:

- PREASSESSMENT_US2024_TIMESTAMPS.json: 51d910392b5f47f20b57ba56a4b2d25bc9096d33ac1dd09361f32a925884028d.
- PREASSESSMENT_KOREA2025_WINDOWS.json: 6286e0541a95b5f4806943bb809aa9314d55c2a637171002027c05e6292fc42d.

The guard checks membership against those frozen inventories, not raw survey coverage or physical truth. It does not open prediction files or validate numerical values, source/model identities, masks, runtimes or metric gates. Exact timestamp strings and number serialization are preserved because they define the producer's case IDs. A later raw-input or protocol change requires a separately reviewed frozen inventory, not a silently changed caller map.

Source context: the parent supplied Tier 2 graph evidence for the unchanged result checker's `cohort` function, generation 2026-10-30T13:27:37Z, with complete relevant query/trace pagination. This preparation read its bounded 91-156 source to confirm the ID formula and identified coverage gap; graph status and exact-file coverage were rechecked. No new source discovery, graph mutation or edit to that checker occurred.
