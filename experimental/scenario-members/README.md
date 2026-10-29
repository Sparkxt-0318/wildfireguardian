# Trajectory members, scenario reduction and acceptance rules (track 1C-1, opt-in overlay)

**Headline.** Export v3 (Contract A) for all 15 frozen Korean cutoffs: N = 1,024 trajectories per window, replay mode, exact at the one-hour horizon of every frozen mission and identical to model mode on a FIXTURE run with the real c651 checkpoint (all 256 test trajectories and all 1,024 run trajectories equal). Bridge v2 (Contract B) rebuilds the frozen packets exactly when it is fed the v1 draws. The frozen packet arrays (breakpoints and flame) come back bit for bit, and the flux matches to within 6.5e-16 relative (FFT rounding differs between the macOS arm64 build host and this host). Evidence, numbers and figures are in `research/scenario-members/README.md`.

The frozen kit, the frozen bridge (`integration/src/wfg_latest/bridge.py`), the packet writer and the v2 exporter (`export.py`, orchestrator decision D1) are imported unchanged with pinned SHA-256 (`src/wfg_members/kit.py`). The single shared touch point outside this folder is the optional `trajectory_callback=None` keyword argument of `forecast/wildfire/rollout.py::simulate` (four added lines: the argument, one docstring line, and a two-line call), with its byte-identity tests in `forecast/tests/test_rollout_trajectory_callback.py`. `forecast/PUBLICATION_MANIFEST.json` describes the released snapshot of `rollout.py` (SHA-256 `11677460...`), which the test rebuilds by deleting the four lines (orchestrator decision D2).

## Contents

| Path | Role |
|---|---|
| `export_v3.py` | Contract A overlay: `wfg.latest-forecast-export/3`. `model` mode calls the frozen v2 exporter, then `simulate(..., trajectory_callback=...)`; `replay` mode re-runs `simulate` with its real random streams on a transition that returns the frozen v2 probability for the cutoff state and refuses any other state (one-hour horizon only). New arrays: `trajectory_first_burn_hour` int16 [K,H,W] (0 burned at cutoff, 1..H first-burn hour, -1 never within the horizon, -2 never recorded burned and outside the rollout's coverage at the horizon), `trajectory_seed` int64 [K] (the ignition-stream block seed of `rollout._generator`, uint64 stored as its int64 view; trajectory k is row k % B of block k // B), `trajectory_component` int16 [K] (0: c651 is a single-kernel model; Bayesian components are recomputed from the component stream). Record fields `export_version`, `trajectory_count`, `trajectory_horizon_hours`, `trajectory_boundary`, `trajectory_missing_policy`, plus seeds, batch size, v2 identities and the checkpoint SHA-256 (c651, unchanged). |
| `bridge_v2.py` | Contract B: members are trajectories. The trajectory ignition seconds are injected where the frozen packet writer injects the full-event draw, so the v1 packet layout and member fields are produced by the unchanged v1 code. Sub-hour timing `uniform` (U[0,1) per trajectory and cell, matching v1) or `ordered` (same seconds, reassigned within the hour by increasing distance to the previous hour's burned set; a heuristic, not a physical model). Records `dependence = "trajectory"`, `timing`, `member_selection` (method, distance, cost, indices, weights, extremes), `acceptance`, `construction_version = "wfg.hazard.construction/2"`; `source_law_version` stays `/1` because the per-member scalar law the checkers recompute is unchanged. |
| `src/wfg_members/contact.py` | Exact rational activity intervals per member on graph cells (equal to `RoadBoundModel.cell_intervals`, tested). |
| `src/wfg_members/reduction.py` | first_k, forward selection (Heitsch and Romisch), k-medoids; distances edge_arrival, first_burn_l1, road_symdiff; extremes per corridor; redistributed weights. |
| `src/wfg_members/acceptance.py` | Rules `all` and `k_of_m` with exact rational weights; CVaR of member arrival times (reporting only). |
| `src/wfg_members/planner.py`, `check.py`, `decide.py` | Planner interface and the frozen contact sweep planner; per-member Contract D reports from one frozen centre check plus per-member contact (identical to per-member frozen checks, tested); decisions with lazy constraint generation and exact chance-constrained subset enumeration (shared-bound shortcut, free members). |
| `src/wfg_members/coverage.py` | Cheap after-the-fact checker for coverage on all N trajectories (exact contact, conservative superposition dose). |
| `src/wfg_members/extended.py` | Derivation rule of the extended-horizon exploratory missions (not frozen missions). |
| `make_manifest.py`, `SOURCE_SHA256.json` | Source manifest of this overlay, the pinned frozen imports and the shared touch point. |

## Tests

```sh
python3.12 -m venv .venv && . .venv/bin/activate
pip install -c constraints-routing.txt './integration[packets]' -r experimental/scenario-members/requirements-test.txt
python -m pytest experimental/scenario-members/tests          # routing side; export tests skip without PyTorch
# forecast environment (PyTorch CPU, pip install -e ./forecast): export v3 and the rollout callback
python -m pytest experimental/scenario-members/tests/test_export_v3.py forecast/tests/test_rollout_trajectory_callback.py forecast/tests/test_rollout.py
```

Tests that need the frozen inputs skip when `tools/fetch_routing_inputs.py` has not been run (or `WFG_ROUTING_INPUTS` is unset). The export v3 tests check that v2 arrays are byte-identical in the v3 file, that first-burn hours agree with the saved probability within Monte Carlo tolerance (and exactly with the rollout's own estimate when K = N), that `trajectory_seed` regenerates every trajectory, that replay refuses horizons beyond one hour, and (FIXTURE) that model mode runs end to end and replay equals it at one hour.

## Limits

At the one-hour horizon of the frozen missions a trajectory is one synchronous transition from the cutoff state, so trajectory members and the v1 independent members have the same law; only sub-hour ordering, member count and reduction weights can differ. Multi-hour trajectories need the forecast's environmental rasters (model mode), which are not on this host; the multi-hour path is exercised only on a FIXTURE data root. No member law here is a calibrated joint forecast, and no result is physical-safety evidence.
