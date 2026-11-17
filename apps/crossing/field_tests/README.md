# Field tests A-F

Status 2026-11-17: scripts, protocol sheets and analysis are written and tested **on simulated data only**. None of
the six tests has been run on hardware. Nothing here shows that the unit or the app works, and nothing here may be
quoted as a result until the user has run the tests and pasted the measured snippets into `apps/crossing/RESULTS.md`.

The user runs the tests; these scripts record the runs and turn them into CSV + PNG + a Markdown snippet for
RESULTS.md. Every analysis reports failures as measured and ends with the same disclaimer (no readiness claim;
limits are placeholders for a fire service to set).

| Test | Protocol sheet | Record / run | Analysis | What it measures |
|---|---|---|---|---|
| A | `protocols/A_flux_plate.md`, `sheets/A_inputs.yaml` | `a_flux_record.py` (risk gate) | `a_flux_analyse.py` | Plate flux vs a **Bunsen burner only**, 5 distances x 3 repeats, cool-down fits; beside point source, closed form, FDS C064 reference |
| B | `protocols/B_radar.md` | `b_radar_record.py` (risk gate for flame and smoke) | `b_radar_analyse.py` | Corner reflector 2-5 m; nothing / flame / smoke / mist; loss and flicker vs noise; prints "flame effect below noise" |
| C | `protocols/C_thermal.md`, `sheets/C_inputs.yaml` | `c_thermal_record.py` | `c_thermal_analyse.py` | Near-edge distance error vs tape at 3-15 m and -5/0/+5 deg tilt |
| D | `protocols/D_failsafe.md` | `d_failsafe_run.py` (talks to the app on ws://127.0.0.1:8781/ws) | `d_failsafe_analyse.py` | Time from each fault to a fault-attributed CLOSED; pass <= 2 s |
| E | `protocols/E_vehicle.md` | `e_vehicle_record.py` (+ the Pi's own record) | `e_vehicle_analyse.py` | 30-min drive: link dropouts, GNSS, power, temperatures, completeness |
| F | `protocols/F_housing.md` (checklist) | `f_housing_record.py` | `f_housing_analyse.py` | Spray + hot-air gun: heartbeat gaps, silent stops, temperatures, throttling |

Run everything from `apps/crossing` with the venv, e.g.
`.venv/bin/python -m field_tests.a_flux_record --help`. Runtime data goes to `apps/crossing/records/field_tests/`
(git-ignored). Analyses write to `records/field_tests/<test>/analysis/` by default.

## Flame safety gate

Test A (always) and test B's flame and smoke conditions (a smouldering smoke source still burns) refuse to start
unless `--risk-assessment PATH` points to an existing, non-empty scan or PDF of the **adult supervisor's signed risk
assessment** and `--supervisor NAME` is given. The path, size, SHA-256 and the supervisor's name are written into the
run's `trial.json` (the document itself is not copied). Test A uses a Bunsen burner only. Test B's flame source is
the one approved in the signed risk assessment; the analysis assumes a Bunsen-size flame, so the record script needs
`--flame-kind bunsen|other` and `b_radar_analyse` flags every non-Bunsen run. Both analyses write a gate CSV
(`A_gate.csv`, `B_gate.csv`); a gated run without the gate is listed as GATE MISSING, never dropped.

## Flux-disc stop (70 C, PETG tabs)

The copper flux disc sits on printed PETG tabs. **Every record script** (A, B, C, E, F through
`recordkit.record_run`, and D's `d_failsafe_run`) runs `recordkit.DiscGuard`: a `tc_plate` reading without a
MAX31855 fault at or above `flux.disc_max_c` (crossing.yaml, **70 C, user-set**; 69.75 C does not stop, 70.00 C
does) stops the run at once and prints `STOP: flux disc at X C >= 70 C (PETG tabs)`. While a run needs the disc
temperature (test A: whole run; test F: hot-air and cool phases; test B flame / smoke: condition_on), more than 2 s
without a valid `tc_plate` reading (missing stream, link drop or thermocouple fault) also stops it
(`DISC_TEMP_UNKNOWN`). Test D stops on the disc temperature in the app State (and the unit stream with `--pi`), not
on a missing one (tc_plate_open is one of its faults). The run directory keeps everything up to the stop:
`trial.json` gets `stop_reason` (`DISC_OVER_70C` / `DISC_TEMP_UNKNOWN`, null when not stopped), `stop_detail`,
`disc_max_c` and a `disc_guard` summary; `marks.jsonl` a `disc_stop` mark; the script exits 3. The limit is never
above 70 C (crossing.yaml refuses more; `DiscGuard` caps any other value at 70). A run that gets no data from the
unit (nothing serving, wrong URL) prints `ABORTED: <reason>` (not `Done`), keeps `trial.json` with `aborted` set
and exits 4. Record-script exit codes: 0 done, 3 stopped by the disc guard, 4 aborted. The guard stops the
recording only: the operator removes the heat. Analyses report stopped runs as measured ("STOPPED: disc 70 C" /
"STOPPED: disc temperature unknown") and never drop them; `a_flux_analyse` also flags any recorded disc sample
>= 70 C (such runs are left out of the means and the loss fit, and listed), `f_housing_analyse` FAILs `disc_limit`
and `disc_guard_stop`. Not tested on hardware.

## Files

- `common.py`: paths, the risk gate, CSV / Markdown / PNG helpers (SIMULATED watermark), statistics.
- `recordkit.py`: laptop-side WebSocket recorder. A run directory has the same `<sensor>.jsonl.gz` files as a Pi
  record session (readable by `wfgvu.replay`, so it can also be replayed into the app), plus `rx.jsonl.gz`
  (laptop receipt times), `marks.jsonl` (protocol and operator marks with the estimated Pi time) and `trial.json`.
- `sessions.py`: loading runs and Pi sessions. `unitstats.py`: link dropouts, heartbeat gaps, silent stops,
  completeness, throttling decode (tests E and F).
- `simulate.py`: SIMULATED inputs for all six tests (stated, seeded, illustrative physics).
- `run_demo.py`: simulate + analyse everything into `example_outputs/` (every file there is SIMULATED).

## Where the code reuses the app

`crossing.flux` (FluxEstimator, fit_cooldown), `crossing.heat` (closed form via kcf-heat, FDS C064 reference),
`crossing.radar_flame` (RadarBaseline, RadarFlameDetector), `crossing.thermal` and `crossing.geometry` /
`crossing.terrain` (near_edge, Profile), and `wfgvu.protocol` / `wfgvu.replay` / `wfgvu.recorder` for the data
format. Test D reads the app's State (`crossing/pipeline.py`: verdict {state, reasons}, health {link_up, sensors})
and the research log (`research_log/README.md`: verdicts.csv / health.csv on `rx_mono`); test E also accepts the
research log's `wire.jsonl.gz` instead of `rx.jsonl.gz` for link dropouts. Those modules appeared while this was
being written; the readers are checked against the documented shapes, not against a live app session.
`wfgvu.synth`'s `corner_reflector` scenario feeds test B's analysis in an interop test (`synth_b_nothing`); the
other simulated inputs come from `simulate.py`.

## Findings from the simulated runs (design points, not hardware results)

- Test A: with the 70 C disc limit the cool-down loss fit covers only room temperature to about 60 C, and with the
  unfitted plate model (1 mm copper, h = 10 W/m2K, air 20 C) the disc settles at 70 C under about 0.9 kW/m2 and
  reaches it in about 2 min at a steady 2 kW/m2 (calculation, not measured). The old cool-down heating (8 kW/m2
  for 120 s, about 200 C) is no longer allowed: the simulated set has one such run, stopped by the guard
  (`A_cooldown_r3_SIM_overheated`, STOPPED: disc 70 C); the others heat at 1.5 kW/m2 (peak about 57 C).
- Test C: with the camera's 42 deg vertical field of view (InfiRay P2 Pro; TC001 vendor figure, UNVERIFIED), a
  level camera cannot see ground nearer than about 2.6 x its height (6.8 m at the 2.6 m roof height). `crossing.geometry.near_edge` flags such a base
  (`base_cut_off`, the app then gives CLOSED with NEAR_EDGE_NOT_OBSERVED); the test C analysis also reports it as
  "not observable".
- Test D: link loss and power loss are noticed after `silence_s = 1.5 s`, frozen thermal data after `freeze_s =
  1.0 s` of identical pixels (DESIGN.md section 5 as built 2026-11-17), so by design they should reach CLOSED in
  about 1.4-1.7 s and 0.8-1.3 s; not measured yet. Thermocouple / IMU / GNSS value freezes keep longer windows.
  Attribution is by change and by exact reason code: a CLOSED counts for a fault only when a code of that fault
  (`SENSOR_NOT_FRESH:<s>`, `SENSOR_FAULT:<s>`, `INPUT_*:<s>`, `LINK_DOWN`) or its health flag APPEARED after the
  fault; bench reasons (`RADAR_UNKNOWN`, `GNSS_NO_FIX`, ...) never count, and a cause already present before the
  fault gives NOT_ATTRIBUTABLE, never PASS. `thermal_freeze` is timed from the received thermal frames (needs
  `d_failsafe_run --pi`), else NOT_MEASURED. There is no Pi health (under-voltage) fault in test D.
