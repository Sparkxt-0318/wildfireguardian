### SIMULATED: Test F - housing: water spray and hot-air gun

> **SIMULATED DATA: these numbers come from field_tests/simulate.py, not from hardware. They only exercise the analysis; they are not a measurement.**

Unit-side source: Pi record session. 2 check(s) FAIL, 0 WARN (thresholds are placeholders).

| check | result | value | limit | detail |
|---|---|---|---|---|
| reboot | PASS | 1 | 1 | session ids: VU-SIM-F-housing |
| unit_heartbeat_gaps | PASS | 0.00 | 2.00 | no gap > 2 s (Pi record session) |
| thermal_heartbeat_gaps | PASS | 0.00 | 2.00 |  |
| radar_heartbeat_gaps | PASS | 0.00 | 2.00 |  |
| silent_stop_radar | FAIL | 3.00 | 1.00 | readings stopped 3.0 s at +540 s while heartbeats said ok |
| tc_plate_heartbeat_gaps | PASS | 0.00 | 2.00 |  |
| tc_housing_heartbeat_gaps | PASS | 0.00 | 2.00 |  |
| tc_air_heartbeat_gaps | PASS | 0.00 | 2.00 |  |
| imu_heartbeat_gaps | PASS | 0.00 | 2.00 |  |
| gnss_heartbeat_gaps | PASS | 0.00 | 2.00 |  |
| pi_heartbeat_gaps | PASS | 0.00 | 2.00 |  |
| housing_temp | PASS | 44.25 | 60.00 | max tc_housing; warn 50 C, limit 60 C (placeholders) |
| cpu_temp | PASS | 70.60 | 80.00 | max pi.cpu_c |
| throttling | PASS | 0 | 0 | none |
| under_voltage | PASS | 0 | 0 | 0.0 s in total |
| link_dropouts | FAIL | 3.20 | 2.00 | 1 laptop receipt gap(s) > 2 s, 1 disconnect(s) |
| plate_faults | PASS | 0 | 0 |  |
| plate_step | PASS | 0.50 | 5.00 | largest step between consecutive plate readings in hot_air_plate |
| plate_rises_when_heated | PASS | 35.50 | 0.00 | end minus start of hot_air_plate (negative = polarity reversed?) |
| air_rise | PASS | 38.75 | 5.00 | tc_air rise during hot_air_probe; the laptop must CLOSE above the vehicle intake limit (test D/app) |
| disc_limit | PASS | 60.25 | 70.00 | max tc_plate over the run; the hot air must not heat the disc to 70 C (user-set) |
| disc_guard_stop | PASS |  |  | not stopped by the record script's disc guard |
| checklist_water_inside | INFO | no (SIMULATED answer) |  | operator answer |
| checklist_radome_damage | INFO | no (SIMULATED answer) |  | operator answer |
| checklist_window_damage | INFO | no (SIMULATED answer) |  | operator answer |
| checklist_plate_ok | INFO | yes (SIMULATED answer) |  | operator answer |
| checklist_notes | INFO |  |  | operator answer |

| phase | s | housing max (C) | CPU max (C) | plate max (C) | air max (C) | radar (Hz) |
|---|---|---|---|---|---|---|
| baseline | 120.0 | 24.2 | 53.5 | 24.2 | 22.2 | 2.0 |
| spray | 300.0 | 24.2 | 53.4 | 24.2 | 22.5 | 2.0 |
| dry | 60.0 | 24.2 | 52.9 | 24.2 | 22.2 | 2.0 |
| hot_air_front | 240.0 | 44.2 | 70.6 | 24.2 | 22.2 | 2.0 |
| hot_air_plate | 120.0 | 44.0 | 70.6 | 60.2 | 22.2 | 2.0 |
| hot_air_probe | 120.0 | 33.0 | 60.8 | 60.2 | 61.5 | 2.0 |
| cool | 60.5 | 28.2 | 56.6 | 26.0 | 61.0 | 2.0 |

Hot-air gun is a stand-in for radiant heat; it is not a flame and says nothing about flame exposure.
Files: F_checks.csv, F_phases.csv, F_timeline.png.

_Results are reported as measured, including failures. Verdicts are advisory for trained crews and every limit is a placeholder for a fire service to set. These results do not show operational readiness._
