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
  "(UNKNOWN_SUPPORT_NOT_EVALUATED; writer ab12cd34)" / "작성기 ab12cd34" wherever reasons appear today: panel,
  timeline, CSV, A4 sheet. Results of different writers are therefore never pooled under one code (Hannah, consumer
  rule 1).
- Not covered here:
  - a missing BUILD_SUMMARY.json. That is a property of the packet directory, which the planner never reads. The
    producer (API / cache generator) must refuse such a packet (Hannah, consumer rule 2);
  - the memory-budget label (kit v2 does not emit `memory_budget_mib` yet);
  - the kit v2 outcome mapping (route_crosses / refusal_depends / none), which comes after Priya's Step 1b.
- Staff labels (EN; Korean pending Sofia):
  - UNKNOWN_SUPPORT_NOT_EVALUATED: "forecast with areas of unknown fire state — their effect was not evaluated";
  - WRITER_IDENTITY_MISSING: "forecast packet writer identity missing";
  - SUPPORT_WRITE_FAILED: "unknown-area mask write failed for the forecast packet".

## Measured
- Gate (orchestrator): unmasked results are byte-identical to Main. A dump of `cacheToModel` for all six caches, every
  attempt's staff reason text in ko and en, and every message-kit output and violation for 531 real + 600 synthetic
  places: 14,373,120 bytes, sha256 eb38f40d34631aa0… on both Main 994abd7… and this branch.
- The six booth caches carry 0 masked results today, so nothing visible changes.
- With every result of a real cache marked masked: 0 checked routes, 0 no-routes, 0 leave-by times, and every reason
  carries the writer (test).
- Mutations: the gate off → 5 of 8 tests fail; the writer hidden → 5 fail; the marker ignored → 2 fail.
- Suite (workflow environment) 27 files / 462; build:static OK; tsc clean.
