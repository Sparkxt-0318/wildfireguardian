# Trajectory export and strict scenario support

All 15 frozen Korean cutoff windows were re-exported from the actual c651 checkpoint with 1,024 Monte Carlo trajectories each. All 15/15 preserve every existing v2 array bit for bit, and all 15/15 reproduce the full-N empirical first-burn means exactly on known support. Every window also contains unknown trajectory support, ranging from 42.2% to 93.6% of cells. This prevents a complete-domain risk claim under the strict unknown-source policy.

A one-hour single-component transition from a fixed binary cutoff state has the same conditional spatial independence law as independent per-cell draws from its one-step probabilities. There is no multi-step recursive coherence difference to identify on these fixed one-hour missions. Comparing the historical zero-assigned v1 packets with new unknown-preserving v3 packets would additionally confound missingness policy with member construction. Neither comparison establishes a coherence benefit.

## Implemented and checked

The engine callback observes copied Boolean states after each synchronous update. With no callback, draws and result tensors match the original engine; an observer mutating its supplied tensor cannot change the simulation. The opt-in export wrapper supplies first-burn hours, component IDs and signed-int64 seed bit patterns, plus block offsets and batch size. The old RNG is block based, so a seed alone does not regenerate an individual trajectory. The complete regeneration identity is recorded explicitly.

The bridge imports the frozen validator/source radiation law, writes the inherited packet layout, and records construction version 2 separately from unchanged physical source law 1. A trajectory member with unknown emitting cells has unsupported flux at every receiver unless a bound on those sources is provided; it is never silently cold. Explicit new-member exposure history and budgets are required when writing a packet. The known fixture passes both contact planners at the same arrival and the complete copied cell-centre checker. Native whole-road compatibility and real trajectory-panel certificates are not claimed.

Forward selection, deterministic medoid swaps and first-K control are implemented, along with capped-field L1, supplied road-arrival and road-weighted symmetric-difference distances, redistributed weights, optional appended corridor extremes, weighted acceptance and upper-tail CVaR. Appending selected extremes is a heuristic, not proof of conservatism. Unknown fields are rejected by distance construction rather than zero-filled. The full three-distance reduction panel and all-N route coverage remain unestablished on unknown support.

## Reproduce and inspect

```sh
python research/scenario-members/run_exports.py --cases research/sipp-routing/native-panel-20261030/CASES.json --data-root DATA_ROOT --out FRESH_EXPORTS
python research/scenario-members/audit_exports.py --exports FRESH_EXPORTS --frozen-exports FROZEN_EXPORTS --out research/scenario-members/EXPORT_AUDIT.json
python research/scenario-members/analyze_exports.py --exports FRESH_EXPORTS
PYTHONPATH=forecast:experimental/scenario-members/src:experimental/synthetic-truth/src:experimental/sipp-routing/src python -m pytest experimental/scenario-members/tests
```

The export commands use the pinned forecast environment, Python 3.12.1, PyTorch 2.5.1 and NumPy 1.26.4. Routing tests use the separate fresh routing environment; export-only tests are skipped there and run in the forecast environment. `REAL_EXPORT_EXECUTIONS.json` records exact commands, exit codes, host-bound paths, checkpoint/input/output identities and elapsed time. Export seed 0, trajectory batch size 32. Sub-hour member seed 20261008. Checkpoint SHA-256 is c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843. All real export attempts completed on native macOS arm64; the detailed interpreter/host records remain in export records and the fresh environment receipts.

`FAILED_EXPORT_PREPARATION.json` preserves the first attempts that failed because the selective source extraction lacked weather completion metadata. Those outputs are not pooled with successful exports. Restoring the original metadata repaired loading; no source rasters or trained parameters changed. `EXPORT_AUDIT.json` compares all prior arrays, including embedded clock/policy fields, directly with the frozen exports.

## Figures

Figure 1, fig01_member_examples (PNG 300 dpi and SVG), shows one independent draw and one recorded Monte Carlo trajectory at the same Uljin cutoff and scale. Grey denotes unsupported cells in both panels. The illustration concerns the one-hour conditional law and does not demonstrate multi-hour coherence or observed fire geometry.

Figure 2, fig02_unknown_support_by_window (PNG and SVG), reports the fraction of cells carrying sentinel -2 in each actual export. Unknown cells remain unknown; the chart is an input-admission diagnostic, not an error-rate estimate.

## Scope and limits

No field validation or physical accuracy is established. Source-law constants and current-fire maximum-remaining enclosure are retained. The requested full outcome/reduction/coverage study is not complete; strict-admission attempts and null truth scores are in research/synthetic-truth. Caldor/Rim packets exist and were used for the separate exact contact study, but a c651 environmental export aligned to those frozen graph grids has not been established. No resampling or threshold/horizon changes were invented to bridge that gap. New-bridge real-panel equivalence, the member-count scaling curve, exposure histories for changed members and the full weighted chance-subset search remain open. TRACK_STATUS.json records each gate.

V3 is provided by the opt-in experimental/scenario-members/export_v3.py wrapper. The frozen integration/src/wfg_latest/export.py is restored byte-for-byte and its release manifest is unchanged. Existing real exports remain bound to the exact archived original producer in producer/. The wrapper preserves the same model arrays; exporter-source hashes legitimately identify different scripts.

The global-support refusal used here is a conservative admission choice. It is not proof that every local checker or a checker with pessimistic bounds on unknown sources would fail. Those alternative bounds and their effect on case scorability have not been established in this track.

The wrapper passed a bounded fresh real-cutoff equivalence check: all arrays and the entire NPZ are byte-identical to the archived producer for the checked KFS_11 cutoff. WRAPPER_EQUIVALENCE.json records the producing command and both source identities. The default release verifier passes after restoring the frozen exporter.
