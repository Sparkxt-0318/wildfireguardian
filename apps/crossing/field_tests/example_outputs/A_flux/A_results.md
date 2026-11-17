### SIMULATED: Test A - flux plate vs Bunsen burner

> **SIMULATED DATA: these numbers come from field_tests/simulate.py, not from hardware. They only exercise the analysis; they are not a measurement.**

Heat source: Bunsen burner only. Gas: methane, Q = 1.130 kW (LHV default for methane (33.9 MJ/m3 at 15 C, 1 atm)). chi assumed 0.10 (band 0.03-0.20), flame width 0.020 m.
Plate loss model: h = 10.99 W/m2K, eps = 0.95 (median of 2 cool-down fit(s), eps fixed at 0.95; fit rms 47.5 W/m2).
Runs: 15 exposure, 3 cool-down; 0 exposure run(s) flagged and left out of the means.
Supervisors recorded: SIMULATED supervisor.

| r (m) | n | measured (kW/m2) | sd | point source | closed form | FDS C064 ref* | meas/point | implied chi |
|---|---|---|---|---|---|---|---|---|
| 0.100 | 3 | 0.714 | 0.008 | 0.899 | 0.895 | 0.868 | 0.794 | 0.079 |
| 0.150 | 3 | 0.320 | 0.002 | 0.400 | 0.399 | 0.808 | 0.800 | 0.080 |
| 0.200 | 3 | 0.180 | 0.003 | 0.225 | 0.225 | 0.752 | 0.800 | 0.080 |
| 0.300 | 3 | 0.080 | 0.001 | 0.100 | 0.100 | 0.651 | 0.804 | 0.080 |
| 0.400 | 3 | 0.045 | 0.002 | 0.056 | 0.056 | 0.564 | 0.801 | 0.080 |

*FDS C064 reference, not a measurement: a 4473 kW/m grass-fire radiometer curve scaled by I/4473 with I = Q / flame width. A Bunsen flame is not a line fire; this column is a scale check only.
The closed form maps the flame onto a front of depth = half-width x 2 = flame width; it tends to the point source for r >> flame width.

Flux-disc limit 70 C (copper disc on PETG tabs; user-set): 1 run(s) stopped by the record script's disc guard, 1 run(s) with recorded disc samples >= the limit (left out of the means and the loss fit, listed here as measured).
- A_cooldown_r3_SIM_overheated: STOPPED: disc 70 C - flux disc at 70.00 C >= 70 C (PETG tabs) (run kept, reported as measured)
- A_cooldown_r3_SIM_overheated: 1 disc sample(s) >= 70 C
Cool-down fits flagged (not pooled): A_cooldown_r3_SIM_overheated (STOPPED: disc 70 C (flux disc at 70.00 C >= 70 C (PETG tabs)); 1 disc sample(s) >= 70 C (disc limit, PETG tabs))

Plan coverage (sheet: 0.1, 0.15, 0.2, 0.3, 0.4 m x 3 repeats): complete.

Files: A_by_distance.csv, A_runs.csv, A_cooldown_fits.csv, plate_loss.json, A_flux_vs_distance.png, A_flux_timeseries.png, A_cooldown_fit.png.

_Results are reported as measured, including failures. Verdicts are advisory for trained crews and every limit is a placeholder for a fire service to set. These results do not show operational readiness._
