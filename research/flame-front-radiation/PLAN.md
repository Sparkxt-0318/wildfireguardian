# Track 1A plan: flame-front radiation law v2

Branch `track/1a-flame-front-radiation`, created from `next/orchestrator`. Ownership: `experimental/flame-front-radiation/**`, `research/flame-front-radiation/**`, `docs/RADIATION_LAW_V2.md`. Nothing under `integration/`, `forecast/`, `api/`, `planner/` or `hardware/` is edited.

## Reading notes

### What law v1 computes

- `integration/src/wfg_latest/bridge.py` (`wfg.final-forecast-bridge/2.0-latest-c651`, source law `wfg.hazard.construction/1`). Each scenario member is an independent per-cell draw of a first-new-burn time, uniform in the hour (`draw_ignitions`, seed 20261008, 4 members). A cell that ignites at `b` is treated as a whole 375 m flaming cell on `[b, b + T)`, with `T = 3970.46 s` (point residence 11.52 s plus a 375 m crossing at 341 m/h, `contract.POLICY`). Present fire is a scalar maximum-remaining enclosure: every present-fire cell is active on `[0, R_max)`. For each breakpoint interval the active map goes through `ExpectedHeatFluxModel.predict_details`, and the flux at cell centres is stored in `HAZARD.json` (kW/m2) and in `constructed_arrays.npz` (per-member `ignition_time_s`, `current_active`, extinction breakpoints).
- `integration/src/wfg_latest/radiation/heat.py`. `CombustionParameters.heat_release_rate_density_w_m2 = w f H / T = 10 x 0.1 x 18.608e6 / 3970.46 = 4686.6 W/m2`. `ExpectedHeatFluxModel` multiplies by the radiative fraction 0.30 and treats each active cell as a horizontal isotropic source sheet at 5 m above an upward-facing receiver at 0 m. `_cell_transfer` returns the exact solid angle of the cell divided by 4 pi and clips it to `[0, 0.5]` (`np.clip(transfer, 0.0, 0.5)`).
- Where the 0.703 kW/m2 ceiling comes from: all coplanar non-overlapping source rectangles together subtend at most 2 pi sr below the 5 m plane, so the summed transfer is at most 2 pi / (4 pi) = 0.5, and flux is at most `0.5 x 0.30 x 4686.6 W/m2 = 703.0 W/m2`. The ablation records the same cap as `planar_solid_angle_cap_kw_m2 = 0.7029908348471505` in `research/routing/final-input-ablation/POLICY_TRANSFORMS.json`. Against the 10 kW/m2 peak limit the peak constraint cannot bind.
- `integration/kit/phaseB/road_bounds.py` and `integration/kit/routing_candidate/baseline/radiation_bounds.py` compute outward per-source coefficient bounds `lo_i(X) <= rho chi tau Omega_i(x)/(4 pi) <= hi_i(X)` over receiver boxes, take directed sums per member interval, and integrate dose bounds per sub-box with the exact activity intervals. Contract C `flux_enclosure` is designed so that a checker can use it in the same way (per box and time interval, upper bound never below any point value).
- `research/routing/final-input-ablation/README.md`: five policies, 200 native executions, peak and dose changed no outcome; the global flux cap 0.703 kW/m2 is the stated reason.
- `research/routing/request-window-20261029/README.md` and `RAW_EXECUTIONS.jsonl.gz`: 18 distinct returned journeys of the 20-mission Korean panel, with every leg (edge, fractions, start and end second) and the recorded centre-model per-member dose. Those legs are the journeys this track replays.

### Checker functions copied (not edited) into the adapter

- `routing-package/routing/core.py` (`edge_occupancies`, `node_cell`, `evaluate_occupancy`): the router's centre-model exposure path. The v1 regression test reruns the recorded Uljin journey through this copy and must match the recorded `result.per_member` doses to 1e-9 relative.
- `routing-package/routing/validation.py` is not needed. `phaseB/zsweep.py` (`contact_sweep`) is copied verbatim as the reference for the lattice grammar (edge states, forbidden turns, waits at waitable nodes, destination opening and dwell, exact contact intervals). The policy sweep in the adapter re-implements that grammar and adds peak blocking and per-member dose labels; its v1 output is compared with the frozen ablation outcomes.

## Decisions taken while reading

1. The library consumes the v1 member arrays only. Never-ignited cells get the declared arrival `horizon + T` (front continues toward them at the bridge's nominal pace and does not reach them in the horizon). Present-fire cells get `R_max - T` (the enclosure's youngest age); known burned cells that are no longer active get `-T`. Cells of unknown state are excluded and counted.
2. A flame segment is kept only where its host cell is active under the v1 activity at that time (contact consistency): v2 relocates the v1 flaming area onto a flame line inside the v1 flaming cells. Roads that pass the unchanged v1 contact test can therefore never be inside a v2 flame; any v2 peak is pure radiation across a cell boundary.
3. The packets carry no wind field, so flames are vertical in every routing run (the tilt relation is implemented and exercised only in the physics sweep).
4. Caldor/Rim packets are not available in this container. The orchestrator is asking the human; until then only the Korean panel is run.

## Steps

1. Library `experimental/flame-front-radiation/src/wfg_flamefront/` (isochrone, intensity, solidflame, law_v2, provenance) with tests.
2. Physics validation table and figures in `research/flame-front-radiation/physics_validation/`. Stop if any comparison is off by more than three times.
3. Adapter: frozen copies with hashes, v1 regression, v2 journey checker, 18 journeys x 4 members.
4. Policy sweep (five policies, v1 and v2), binding statistics, cost, figures, README, `docs/RADIATION_LAW_V2.md`.
