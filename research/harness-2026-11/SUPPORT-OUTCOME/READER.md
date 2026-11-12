# Fail-closed reader for support-masked results (orchestrator decision (c), 2026-11-12)

Design: DESIGN.md on branch clara/support-outcome. This cut ships only the reader.

- `planner/src/api/supportGate.ts`. A result is MASKED when its attempt, result or provenance carries a non-null
  `support` or `support_writer`, or an `unknown_support_involved` other than "none". (Kit v2 emits `support: null` and
  `"none"` for an unmasked packet; Priya, PLAN Step 1b.)
  - Every masked result is **unresolved**, `UNKNOWN_SUPPORT_NOT_EVALUATED@<sha8 of packet_writer_sha256>`, until the
    planner reads kit v2's outcome (decision schema /2). It is never a route, never "no route", and has no time.
  - A masked result without a 64-hex writer identity: unresolved, `WRITER_IDENTITY_MISSING`.
  - A support-write failure marker (`notes` / `markers` containing SUPPORT_WRITE_FAILED, raw_status, or
    `support_write_failed: true`): unresolved, `SUPPORT_WRITE_FAILED`, with or without a support block.
- Applied in `adaptAttempt` (per attempt, plus a job-level gate from the dispatch result's or job's provenance) and in
  `adaptRouteJob` (research origins, re-checks, travel-only comparisons). A gated route keeps no geometry, arrival or
  lower bound.
- The writer identity travels inside the reason code as `<CODE>@<sha8>`. `reasonText` splits it and shows
  "(UNKNOWN_SUPPORT_NOT_EVALUATED; writer ab12cd34)" / "생성 프로그램 ab12cd34" wherever reasons appear today: panel,
  timeline, CSV, A4 sheet. Results of different writers are therefore never pooled under one code (Hannah, consumer
  rule 1).
- Not covered here:
  - a missing BUILD_SUMMARY.json. That is a property of the packet directory, which the planner never reads. The
    producer (API / cache generator) must refuse such a packet (Hannah, consumer rule 2);
  - the memory-budget label (kit v2 does not emit `memory_budget_mib` yet);
  - the kit v2 outcome mapping (route_crosses / refusal_depends / none), which comes after Priya's Step 1b.
- Staff labels (EN; Korean by Sofia: one term "산불 상태 미확인 구역", "생성 프로그램" for the writer):
  - UNKNOWN_SUPPORT_NOT_EVALUATED: "forecast with areas of unknown fire state — their effect was not evaluated";
  - WRITER_IDENTITY_MISSING: "forecast packet writer identity missing";
  - SUPPORT_WRITE_FAILED: "unknown-area mask write failed for the forecast packet".

## Wire shape (pinned; Mira N2)
- Leo's masked packet (research/harness-2026-11/F-9.3/support_mask/packets_f93.py, stamp()) writes
  `provenance.identity = { packet_writer_sha256: <wrapper>, base_packet_writer_sha256: <frozen writer>,
  support_writer: { version, rule, support_mask_sha256, unsupported_cells, cells, provenance } }`, plus
  `provenance.support_semantics` (HAZARD) and `support_channel` (REPORT, NATIVE_METADATA).
  - The writer hash is a SIBLING of support_writer, not inside it.
- How the API passes this through to a planner result is not fixed yet. So the reader walks every nested object of the
  attempt, the result and both provenances (depth ≤ 6) and treats as masked any of `support`, `support_writer`,
  `support_semantics` or `support_channel` with a value other than null / undefined / false, or an
  `unknown_support_involved` other than "none".
- The writer is a 64-hex `packet_writer_sha256` beside such a key, or inside a support / support_writer block.
- Kit v2 (Priya, Step 1b) will add `support: {…, packet_writer_sha256}` per attempt; the reader handles both shapes.

## Fixes after Mira FAIL (ledger 80, at 8efdebb)
- FAIL 1: a gated route check now carries no exposure (so no "contact: no" flags), no full-policy grade, no
  within-budget flag and no dwell end, besides no geometry, arrival or lower bound.
- FAIL 2: any non-null / non-false mask value is masked (true, a string, an array, a number, {}).
- N1: the panel and timeline (components/format.ts reasonText, i18n) split "<CODE>@sha8" and show the label and
  "writer <sha8>" / "생성 프로그램 <sha8>". i18n keys were added for the three codes and the writer.
- N2: Leo's identity shape is read (sibling hash; identity nested under provenance).
- N3: markers match case-insensitively and anywhere in the walked objects, including inside a support block.

## Measured
- Gate (orchestrator): unmasked results are byte-identical to Main. The comparison is against the branch's real base,
  **Main 6babc5e** (the earlier note said 994abd7, which was wrong; Mira). The dump covers:
  - `cacheToModel` for all six caches, including route and travel-only details;
  - every attempt's and travel-only reason text in ko and en, through BOTH shared/strings attemptReasonText and
    components/format.ts unresolvedReasonText;
  - every message-kit output and violation for 531 real + 600 synthetic places.

  14,588,046 bytes, sha256 447e1eedd85c1a6f… on both.
- The six booth caches carry 0 masked results today, so nothing visible changes.
- With every result of a real cache marked masked: 0 checked routes, 0 no-routes, 0 leave-by times, and every reason
  carries the writer (test).
- Mutations (13 tests): the gate off → 8 fail; the writer hidden → 6 fail; the marker ignored → 3 fail; the full-policy
  grade kept on a gated route → 1 fails; the sibling writer not read → 1 fails.
- Suite (workflow environment) 27 files / 467; build:static OK; tsc clean.
