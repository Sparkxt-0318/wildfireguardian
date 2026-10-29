# Shared interfaces for the three parallel tracks (paste into the repo as docs/NEXT_INTERFACES.md before any track starts)

Purpose: tracks 1A (flame-front radiation), 1B (forecast upgrades) and 1C (routing: coherent scenario members, SIPP search, chance-constrained acceptance, synthetic-truth validation) run in parallel in separate git worktrees. They may only communicate through the contracts below. A track that needs something another track owns writes a fixture that satisfies the contract and continues.

Repository conventions that every track must respect (they are how this repo already works):

- The frozen research kit (`integration/kit/`, `integration/src/wfg_latest/` as released, checkpoint `c651f672...` in `forecast/runs/...`) is never edited. New behaviour lives in `experimental/<track-name>/` as an opt-in overlay with its own `README.md`, tests, `SOURCE_SHA256.json` manifest and, where it produces numbers, a matching evidence folder `research/<track-name>/` with `README.md`, `RESULTS.json`, per-execution CSV and figures.
- Routing code targets Python 3.12 and NumPy 1.26.4 (`constraints-routing.txt`). Forecast code targets the pinned PyTorch environment in `forecast/`.
- Three result states are sacred everywhere: checked route, model-scoped no-route, unresolved. No unfinished computation is ever reported as success, and nothing is ever described as physically validated unless it was measured in the field.
- Every number reported in a README must be reproducible from a script in the same folder, with seeds and input hashes recorded.
- No em dashes in any prose, code comment, docstring, figure label or commit message. Use commas, colons or parentheses.
- Figures: matplotlib, 300 dpi PNG plus SVG, white background, one sans-serif font, axis labels with units, no chart junk, colour-blind-safe palette (e.g. Okabe-Ito), legends outside the data when they would overlap, consistent sizes (single column 3.5 in wide, double column 7.2 in wide). Every figure gets a one-paragraph caption in the README that says what was measured and under which policy.

## Contract A: forecast export v3 (owner: track 1C; consumers: 1A, 1C)

`wfg.latest-forecast-export/3` extends the existing v2 export (`integration/src/wfg_latest/export.py`) without changing any v2 field.

New arrays in `FORECAST_<tag>.npz`:

- `trajectory_first_burn_hour`: int16 array of shape `[K, H, W]`. For trajectory k, the first whole hour (1..horizon_hours) at which the cell is burned in the recursive Monte Carlo rollout from the cutoff state; `0` for cells burned at the cutoff; `-1` for never within the horizon; `-2` for cells whose state is unknown (invalid) in that trajectory.
- `trajectory_seed`: int64 `[K]`, the per-trajectory seed derived exactly as `forecast/wildfire/rollout.py::_generator` derives it, so any trajectory can be regenerated.
- `trajectory_component`: int16 `[K]`, the Bayesian component index used by that trajectory, or `0` for a single predictor.

New record fields in `FORECAST_RECORD_<tag>.json`: `"export_version": "wfg.latest-forecast-export/3"`, `"trajectory_count": K`, `"trajectory_horizon_hours"`, `"trajectory_boundary"`, `"trajectory_missing_policy"`, and the SHA-256 of the checkpoint (unchanged, c651).

Implementation note: the only permitted change to `forecast/wildfire/rollout.py` is one new optional keyword argument `trajectory_callback=None` on `simulate(...)`, called once per trajectory block with `(block_index, states_bool_tensor[Kb,1,H,W], hour)` after each synchronous update. Default behaviour, random draws and outputs are byte-identical when the callback is `None`. Track 1B must not edit `rollout.py`.

## Contract B: hazard construction law v2 (owner: track 1C; consumers: 1A, 1C)

`wfg.hazard.construction/2` keeps the v1 packet layout (`HAZARD.json` edgegrid, `REPORT.json`, `NATIVE_METADATA.json`, `constructed_arrays.npz`) and the v1 member fields (`breakpoints`, `flame`, `flux_w_m2`, `ignition_time_s`, `extinction_breakpoint_s`) so that every existing checker still runs. It changes only how members are made:

- A member is one Monte Carlo trajectory from Contract A (coherent in space and time), not an independent per-cell draw. Within the first-burn hour, the ignition second is placed by the sub-hour rule recorded in `settings["timing"]` (`"uniform"` as today, or `"isochrone"` when 1A's front geometry is available).
- `settings["dependence"] = "trajectory"`, `settings["member_selection"]` records how the K members were chosen from the N trajectories (`"first_k"`, `"forward_selection"` or `"k_medoids"`), with the distance function name, the reduction cost, and the indices of the selected trajectories.
- `settings["acceptance"]` records the acceptance policy the request will be judged under: `{"rule": "all" | "k_of_m", "k": int, "m": int}`. The default stays `"all"` so that existing decisions are reproducible.

## Contract C: radiation law v2 (owner: track 1A; consumers: 1A, 1C)

`wfg.radiation.law/2-flamefront` is a pure function library in `experimental/flame-front-radiation/src/wfg_flamefront/` with no dependency on the frozen kit. It consumes exactly the v1/v2 member arrays plus the grid and fuel parameters, and provides:

- `front_segments(ignition_time_s[H,W], t, grid, residence_s[H,W]) -> list of line segments` with per-segment intensity (kW/m), flame length (m), flame height and tilt, derived from the isochrone of the ignition-time field at time t and the local rate of spread 1/|grad tau|.
- `flux_at_points(points_xy[P,2], times_s[T], member, grid, fuel, receiver="worst_case") -> q[P,T] in kW/m2`, the incident radiant flux at receiver points, with the emitter and receiver geometry documented in the module docstring.
- `flux_enclosure(box_xy, interval_s, member, grid, fuel) -> (lower, upper)`: rigorous lower and upper bounds of flux over a spatial box and a time interval, monotone in the box and interval, so a checker can integrate dose bounds exactly as the current `road_bounds.py` does. The upper bound must never be below the point evaluation at any point in the box.
- `dose(q[T], times_s[T], form="linear" | "tdu")` where `"tdu"` is the thermal dose unit integral of q^(4/3) dt with q in kW/m2 and t in s.

The library records `law_version`, every physical constant with its source, and a `provenance()` dict. It is deterministic.

## Contract D: acceptance and reporting (owner: track 1C; consumers: all)

A journey decision under law v2 and construction v2 reports, per member, contact (bool), peak (kW/m2), dose (linear and TDU), and whether the member passed. The mission outcome is computed by the recorded acceptance rule. The report adds `"binding_constraints"`: for each returned route, which of contact, peak, dose, destination window or horizon actually changed the outcome relative to travel-only, so that every README can state how often each constraint binds.

## Contract E: synthetic-truth validation record (owner: track 1C; consumers: 1B for forecast quality sweeps)

A validation case is `(cutoff, truth_source, forecast_source, mission)` where `truth_source` is one of `"holdout_trajectory"` (a Monte Carlo trajectory withheld from the forecast members), `"reconstructed_arrival"` (the kriged arrival-time raster of a historical fire), `"observed_perimeters"` (NIROPS unions) or `"external_simulator"` (FARSITE/ELMFIRE run). The executed journey is scored against the truth only: `true_contact`, `true_peak`, `true_dose`, `arrival_s`, `clairvoyant_arrival_s` (earliest arrival computed with the truth itself), and the derived `false_safe`, `false_refusal`, `regret_s`. Records are JSON lines; one file per campaign.

## Ownership table (files a track may create or modify; everything else is read-only for that track)

- 1A: `experimental/flame-front-radiation/**`, `research/flame-front-radiation/**`, `docs/RADIATION_LAW_V2.md`, and a test-only adapter under `experimental/flame-front-radiation/adapters/` that plugs law v2 into a copy of the journey checker for evaluation. 1A never edits `integration/**` or `forecast/**`.
- 1B: `forecast/wildfire/meanfield.py`, `forecast/wildfire/survival.py`, `forecast/wildfire/canonical.py`, `forecast/wildfire/burnout.py`, `forecast/wildfire/baselines.py`, additive classes in `forecast/wildfire/models.py`, additive CLI options in `forecast/wildfire/train.py` and `forecast/wildfire/evaluate.py`, new tests under `forecast/tests/`, a new run directory `forecast/runs/<date>_perimeter_trained/`, `forecast/documents/preregistration_blind_test.md`, and `research/forecast-v2/**`. 1B never edits `forecast/wildfire/rollout.py`, `integration/**` or the c651 checkpoint path.
- 1C: `experimental/sipp-routing/**`, `experimental/scenario-members/**`, `experimental/synthetic-truth/**`, `research/sipp-routing/**`, `research/scenario-members/**`, `research/synthetic-truth/**`, `integration/src/wfg_latest/export.py` (v3 additive), the single `trajectory_callback` kwarg in `forecast/wildfire/rollout.py`, and a new bridge module `experimental/scenario-members/bridge_v2.py` that imports but does not modify `integration/src/wfg_latest/bridge.py`.
- Orchestrator only: `docs/NEXT_INTERFACES.md` (this file), `docs/NEXT_PLAN.md`, final merge and the combined evidence README.
