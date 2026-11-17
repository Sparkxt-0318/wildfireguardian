### SIMULATED: Test D - fail-safe: fault to CLOSED

> **SIMULATED DATA: these numbers come from field_tests/simulate.py, not from hardware. They only exercise the analysis; they are not a measurement.**

Source: live app states (D_SIM). Criterion: CLOSED attributable to the fault (a matching reason code or health flag that APPEARED after the fault time) within 2.0 s of the fault time. 9 of 10 faults passed; 0 not attributable, 0 not measured (neither is a pass).
Flux-disc guard (disc on PETG tabs, 70 C user-set): no guard result recorded.

| fault | verdict before | to CLOSED (s) | to not fresh (s) | result | why | recovery (s) |
|---|---|---|---|---|---|---|
| thermal_unplug | CROSS FAST | 0.74 | 0.74 | PASS |  | 2.21 |
| radar_unplug | CROSS FAST | 0.89 | 0.89 | PASS |  | 1.19 |
| gnss_unplug | CROSS FAST | 0.53 | 0.53 | PASS |  | 1.83 |
| imu_disconnect | CROSS FAST | 2.62 | 2.62 | FAIL | 2.62 s > 2.0 s | 1.47 |
| tc_plate_open | CROSS FAST | 0.34 | 0.34 | PASS |  | 2.12 |
| tc_air_open | CROSS FAST | 0.01 | 0.01 | PASS |  | 2.04 |
| tc_housing_open | CROSS FAST | 0.56 | 0.56 | PASS |  | 2.68 |
| wifi_drop | CROSS FAST | 1.70 | 1.70 | PASS |  | 1.90 |
| pi_power | CROSS FAST | 1.90 | 1.90 | PASS |  | 60.16 |
| thermal_freeze | CROSS FAST | 1.39 | 1.39 | PASS | fault time from received thermal frames (upper bound on the latency, <= one wire period) | 1.56 |

Marks are the NOW of a countdown; operator timing error (a few tenths of a second) is not measured. thermal_freeze is timed from the received thermal frames, never from NOW (NOW can be off from the sim session's freeze by seconds); without them that row is NOT_MEASURED. States arrive at 5 Hz (0.2 s resolution).
Expected by design (not measured): link loss and power loss after silence_s = 1.5 s (1.4-1.7 s), frozen thermal data after freeze_s = 1.0 s of identical pixels (0.8-1.3 s); every row is reported as measured.
Files: D_faults.csv, D_time_to_closed.png.

_Results are reported as measured, including failures. Verdicts are advisory for trained crews and every limit is a placeholder for a fire service to set. These results do not show operational readiness._
