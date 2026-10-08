# Routing refactor — 6 October 2026

## Delivered change

Created a self-contained development copy of the latest prepared-session routing
candidate. Public routing imports, payload/result schemas, objective, numerical
arithmetic, support/status distinctions, preparation ownership and session policy
remain unchanged. No existing delivery or scientific study was edited.

1. Extracted command-line argument parsing, fixture loading, service dispatch and
   JSON serialization into `routing/cli.py`.
2. Extracted release integrity, regression execution, deterministic replay and
   retained full-road witness checking into `routing/checks.py`.
3. Retained `run.py` as a compatibility launcher and added `python -m routing`.
4. Formatted the original twelve library modules using Black 24.10.0 in an
   isolated temporary development environment. Their abstract syntax trees match
   the source exactly; the kernel/search/checker logic was not rewritten.
5. Separated active library, tests, fixtures, documentation, verification tools,
   optional vendored comparator and archived delivery records. Updated active
   replay paths and removed the dependence on a parent folder for instructions.
6. Added seven CLI and release-boundary tests, including outside-working-directory
   invocation, raw/prepared equality, module/legacy entry points, import side
   effects, invalid command rejection and changed-input release rejection.

## Validation

- Original candidate: **84 tests passed**, original 21-hash check passed,
  deterministic replay and retained full-road witness passed.
- Refactor: **91 tests passed** during development.
- **102/102 fixture-result comparisons matched**, including all statuses, reasons,
  arrival times, routes, exposure/checker results and search counters. These are
  17 cases × three existing solver selections × raw/prepared admission. Wall
  duration and process memory are not compared for equality.
- Those comparisons included 42 conditional optima, 12 structural disconnections,
  30 modeled infeasibilities, six at-issue failures, six unsupported outcomes and
  six checked routes. These are repeated solver representations of finite
  fixtures, not 102 independent fire incidents.
- **48 refactored route witnesses** passed the separate existing checker; the
  original witnesses were also checked. Original/refactored raw/prepared replay
  outputs matched exactly.
- **12/12 original library syntax trees** unchanged; **104/104 original candidate
  files** unchanged at their source locations. Historical data/tests/scripts and
  documentation copies are verified against their source digests.

The release check, complete-file manifest and extracted-ZIP checks are recorded
in `verification/VERIFICATION_REPORT.json`, `verification/release_check.log`,
`verification/PACKAGE_VERIFICATION.json` and the ZIP-adjacent packaging report.

## Migration

| Previously | Now |
|---|---|
| `run.py` performed parsing, checks and service calls | thin launcher; `routing.cli` and `routing.checks` |
| root interface/spec/lifecycle documents | `docs/` |
| `evidence/CONTINUITY_REPLAY_FIXTURE.json` | active `fixtures/continuity_replay.json`; original archived |
| `evidence/ROAD_INTEGRATION_SMOKE.json` | active `verification/road_witness.json`; original archived |
| root benchmark/acquisition scripts | unedited `archive/legacy_scripts/` |
| root candidate historical handoff/manifests | `archive/delivery/` |
| parent authoritative integration reports/results | copied `archive/preparation_integration/` |
| implicit reliance on parent reproduction documents | root README and REPRODUCE |

The original entry point and `routing.*` imports are compatible. Historical
benchmark scripts retain original path assumptions and should be reproduced in
their original delivery layout. The exact mapping is in
`verification/SOURCE_PROVENANCE.json`.

## Limits and deliberate exclusions

This is not algorithmic promotion, a new timing study, or full-system deployment.
No dependencies were added to the routing runtime. The optional legacy comparator
still uses NumPy. No mentor forecast was connected. Hazard evidence remains
generated-fixture evidence and does not establish physical safety. No new
road-wide optimality/refusal certification or concurrency testing was performed.
Known geometry/return boundary-policy discrepancies remain explicit; the
refactor does not silently fix them or make earlier claims stronger.

The separate established road-research planner recommendation, unpromoted
optimization branches and frozen studies remain in their original packages.
Source control was not changed or pushed. The Mac's system Git is currently
blocked by the unaccepted Xcode license, so this delivery uses a verified folder,
file manifest and ZIP rather than a commit.
