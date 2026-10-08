# Current routing work — mentor review (8 October 2026)

This is the current review snapshot, not a promotion of experimental code into the existing `routing-package` default.

## Start here

1. **Hourly forecast-to-routing integration:** `forecast_routing_hourly_integration_20261008_v1/OWNER_HANDOFF.md`. Its `candidate/hourly.py` is the executable entry point; `forecast_bridge.py` adapts arrays; `hazard_constructor.py` declares the research assumptions. The original checkpoint and portable inputs are supplied in the release ZIP.
2. **Latest independently reviewed fixed-route checker:** `routing_hybrid_road_checker_20261008_v1/OWNER_HANDOFF.md`, `HYBRID_RADIATION_SPEC.md`, and `candidate/hybrid_checker.py`. `HybridChecker.check` checks a supplied complete mission; `hybrid_radiation.py` bounds the declared source law. It is optional and does not replace integrated route search.
3. **Latest integrated-search diagnosis:** `routing_integrated_search_followup_20261008_v1/OWNER_HANDOFF.md`, `DEVELOPMENT_DIAGNOSIS.md` and `candidate/search_followup.py`. This experiment is NO-GO for promotion. It preserves the failures rather than claiming the cache resolved them.

## What presently works and fails

- Original hourly integration reported 181 release tests plus 436 original-model tests passing. The 78-case panel contains 27 conditional optima, 27 unresolved timeouts and 24 at-issue failures. These are dependent queries on a development incident, not 78 independent fires.
- Latest hybrid fixed-witness panel: six checked multi-edge missions and six contact rejections on 12 incident cases; six additional controls include four certificates, one rejection and one unresolved case. An original null-schema review failure and its disclosed additive parser repair are retained in the full package.
- Search follow-up: the original 27 difficult timeouts remain unresolved; the fresh panel produced 32 timeout phases and 16 admission refusals, with no route witness. Processing more labels did not produce a useful integrated route.
- Strict mode preserves unknown hazard support. Research mode constructs hazards using explicit assumptions, including probability completion, burning duration and thermal parameters. No independent real-fire flame/thermal or physical-safety validation is claimed.

## Questions for code feedback

1. Is the forecast endpoint suitable as a flame-arrival surrogate? What active-fire state and remaining burn duration are defensible at the cutoff?
2. Which missing-probability and source-support rules are justified? Review `ASSUMPTIONS.md` before interpreting a route.
3. Are the combustion law, units and road-segment radiation bounds appropriate for the intended study?
4. Review label state, turn/wait semantics, dominance and destination dwell. Which mathematical simplification could reduce search without changing the problem?
5. Help distinguish infeasible missions from search failure. A dose-relaxed feasibility diagnosis and separate cost profiling have been requested; their results are not included or presumed here.
6. Agree on one supported demonstration origin/time/destination and sensitivity settings, while retaining the failed cases.

## Download and reproduce

Complete immutable packets are assets of [the mentor review release](https://github.com/Sparkxt-0318/wildfireguardian/releases/tag/routing-mentor-review-20261008). Extract each archive separately and follow its `REPRODUCE.md`. Use a fresh output directory.

This Git folder is deliberately a **review subset**, not a standalone installation. It contains original source, tests and narrative reports, with byte hashes in `SOURCE_SUBSET_MANIFEST.json`. Fixture graphs, checkpoints, arrays, complete raw results and original seals remain in the full archives. `RELEASE_ASSETS.json` gives archive hashes and sizes. Source files were not edited. The existing repository routing package remains unchanged.

Use Python 3.12 and the matching packet's pinned requirements. The hourly packet includes NumPy, PyTorch, SciPy, rasterio, pandas, pyproj, affine and pytest. The fixed checker packet has its own lighter requirements. Start with the documented regression/finite-reference commands; the full frozen timing panel is optional and expensive.

The release preserves previously reported results. Fresh checks performed while preparing this upload are recorded in `UPLOAD_VERIFICATION.json`; they are not a new sealed scientific evaluation.
