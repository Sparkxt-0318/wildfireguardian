### SIMULATED: Test E - vehicle drive, unit on the roof

> **SIMULATED DATA: these numbers come from field_tests/simulate.py, not from hardware. They only exercise the analysis; they are not a measurement.**

Source: Pi record session(s); 1 Pi session(s); recorded span 30.0 min.
Link (laptop receipt, gaps > 1.0 s): 2 dropout(s), longest 4.5 s, total 6.0 s; 1 disconnect event(s); largest gap 4.50 s. Pi-side queue-drop events: 0.
GNSS: 1800 readings, fix ratio 0.978 (fix 2: 0.293), hdop median 0.95 / p95 2.64 / max 5.13, satellites median 10, 1 no-fix stretch(es) > 2 s (longest 41.0 s), distance 20.20 km.
Power: 1 under-voltage event(s), 2.0 s in total; throttling-bit readings: {'under-voltage now': 2, 'throttled now': 2}; occurred since boot (last reading): under-voltage occurred, throttling occurred; 0 reading(s) without throttle data.

| temperature | n | min (C) | median (C) | max (C) | missing/fault |
|---|---|---|---|---|---|
| cpu | 1800 | 54.1 | 61.5 | 68.8 | 0 |
| housing | 18000 | 24.8 | 31.5 | 38.2 | 0 |
| air | 17997 | 21.8 | 24.5 | 27.2 | 3 |

| sensor | readings | rate (Hz) | nominal | complete (%) | seq missing | gaps > stale | longest gap (s) | fresh time (%) | hb not ok (%) | faults |
|---|---|---|---|---|---|---|---|---|---|---|
| thermal | 1800 | 1.0 | 1.0 | 100.0 | 0 | 0 | 0.0 | 100.0 | 0.0 | 0 |
| radar | 3593 | 2.0 | 2.0 | 99.8 | 0 | 1 | 4.0 | 99.8 | 0.2 | 0 |
| tc_plate | 18000 | 10.0 | 10.0 | 100.0 | 0 | 0 | 0.0 | 100.0 | 0.0 | 0 |
| tc_housing | 18000 | 10.0 | 10.0 | 100.0 | 0 | 0 | 0.0 | 100.0 | 0.0 | 0 |
| tc_air | 18000 | 10.0 | 10.0 | 100.0 | 0 | 0 | 0.0 | 100.0 | 0.1 | 3 |
| imu | 36000 | 20.0 | 20.0 | 100.0 | 0 | 0 | 0.0 | 100.0 | 0.0 | 0 |
| gnss | 1800 | 1.0 | 1.0 | 100.0 | 0 | 0 | 0.0 | 100.0 | 0.0 | 0 |
| pi | 1800 | 1.0 | 1.0 | 100.0 | 0 | 0 | 0.0 | 100.0 | 0.0 | 0 |

Files: E_completeness.csv, E_link_dropouts.csv, E_power_events.csv, E_temperatures.csv, E_summary.json, E_track.png, E_timeline.png.

_Results are reported as measured, including failures. Verdicts are advisory for trained crews and every limit is a placeholder for a fire service to set. These results do not show operational readiness._
