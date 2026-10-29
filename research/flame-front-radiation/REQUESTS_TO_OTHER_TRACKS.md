# Notes and requests from track 1A to other tracks

## To track 1C (Contract C consumer)

1. Signatures are exactly as in Contract C: `front_segments(ignition_time_s, t, grid, residence_s)`, `flux_at_points(points_xy, times_s, member, grid, fuel, receiver="worst_case")`, `flux_enclosure(box_xy, interval_s, member, grid, fuel)`, `dose(q, times_s, form)`. Extra arguments are keyword-only with defaults. The package imports with NumPy alone (`sys.path.insert(0, "experimental/flame-front-radiation/src")`).
2. `member` may be a v1 bridge member dict (`breakpoints`, `flame`, `ignition_time_s`, ...) plus present-fire keys (`current_active`, `remaining_s`, `burning_duration_s`), or the dicts returned by `wfg_flamefront.load_packet_members(packet_dir)`. For construction v2 trajectory members, pass the member's `ignition_time_s` with the trajectory's first-burn seconds and its `flame` frames; the activity clipping then follows the member exactly. Prepare once with `wfg_flamefront.prepare(member, grid)` and pass the returned `FrontField` to avoid repeated preparation.
3. `box_xy` accepts `(xmin, xmax, ymin, ymax)` (the kit's order) or `[[xmin, ymin], [xmax, ymax]]`. For many boxes use `flux_enclosure_many(boxes, intervals, ...)`. For trajectories use `flux_at_events(points, times, ...)` (paired samples).
4. The enclosure bounds the law as defined (500 m cutoff) by default; `truncate=False` also bounds the far-field tail. Its lower bound is 0 outside the flame, so a dose rejection must come from point samples (exact model values for the peak) or from a future orientation-aware lower bound.
5. Emissive power: the library default is 100 kW/m2 (specified). A measurement-consistent variant is `{"emissive_power_kw_m2": 22.6, "inflame_emissive_power_kw_m2": 100.0}`. Which one is the headline default awaits a human decision (sent to the orchestrator); please make it a run parameter rather than a constant.
6. Cost on this host (Linux container, load 4 to 7 on 4 vCPU, one thread): see `research/flame-front-radiation/README.md` (cost section) for the per-journey v2 check time against the 30 s allowance.

## To the orchestrator

- The Caldor/Rim sealed-study packets are not available in this container, so only the Korean panel was run. When a path is supplied, `run_replay.py` and `run_policy_study.py` need a `--inputs` root with the same `graphs/` and `latest_inputs_try02/` layout, or a small loader change for the sealed-study layout.
