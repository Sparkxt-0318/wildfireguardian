### SIMULATED: Test C - thermal near-edge distance vs tape

> **SIMULATED DATA: these numbers come from field_tests/simulate.py, not from hardware. They only exercise the analysis; they are not a measurement.**

Heated panel (no flame) at 3, 5, 8, 11, 15 m, tilts -5, +0, +5 deg; threshold 150 C; camera height 1.50 m.
With IMU correction: |error| median 1.2 %, max 4.1 % (n = 11 runs); interval covers the tape distance in 11 of 11 runs. Ignoring the IMU: |error| median 36.6 %, max 184.2 %.

| tape (m) | tilt (deg) | IMU pitch | estimate (m) | error (m) | error (%) | lo (m) | hi (m) | covered | error, no IMU (%) | nearest visible (m) |
|---|---|---|---|---|---|---|---|---|---|---|
| 3.00 | -5.00 | -4.85 |  |  |  |  |  |  |  | 3.10 |
| 5.00 | -5.00 | -4.86 | 5.03 | 0.03 | 0.57 | 4.84 | 5.23 | yes | 44.28 | 3.09 |
| 8.00 | -5.00 | -4.85 | 8.05 | 0.05 | 0.59 | 7.60 | 8.55 | yes | 87.57 | 3.10 |
| 11.00 | -5.00 | -4.85 | 11.25 | 0.25 | 2.23 | 10.39 | 12.25 | yes | 184.19 | 3.10 |
| 15.00 | -5.00 | -4.85 | 15.47 | 0.47 | 3.13 | 13.91 | 17.41 | yes | nan | 3.10 |
| 3.00 | 0.00 | 0.14 |  |  |  |  |  |  |  | 3.94 |
| 5.00 | 0.00 | 0.14 | 5.05 | 0.05 | 0.93 | 4.86 | 5.25 | yes | 0.04 | 3.94 |
| 8.00 | 0.00 | 0.15 | 8.09 | 0.09 | 1.19 | 7.64 | 8.61 | yes | -0.23 | 3.94 |
| 11.00 | 0.00 | 0.15 | 11.25 | 0.25 | 2.25 | 10.40 | 12.24 | yes | 0.30 | 3.94 |
| 15.00 | 0.00 | 0.15 | 15.42 | 0.42 | 2.81 | 13.88 | 17.35 | yes | 0.04 | 3.94 |
| 3.00 | 5.00 | 5.16 |  |  |  |  |  |  |  | 5.29 |
| 5.00 | 5.00 | 5.14 |  |  |  |  |  |  |  | 5.28 |
| 8.00 | 5.00 | 5.14 | 8.10 | 0.10 | 1.20 | 7.64 | 8.60 | yes | -33.01 | 5.28 |
| 11.00 | 5.00 | 5.16 | 11.12 | 0.12 | 1.10 | 10.29 | 12.09 | yes | -40.17 | 5.29 |
| 15.00 | 5.00 | 5.16 | 15.62 | 0.62 | 4.13 | 14.04 | 17.59 | yes | -46.79 | 5.29 |

Flagged runs (as measured):
- C_d3.00_tilt-5.0_r1_SIM: hot area touches the bottom image row in all 8 frames: base below the field of view (nearest visible ground about 3.1 m), not observable
- C_d3.00_tilt+0.0_r1_SIM: hot area touches the bottom image row in all 8 frames: base below the field of view (nearest visible ground about 3.9 m), not observable
- C_d3.00_tilt+5.0_r1_SIM: no near edge in any frame (8 frame(s) with no pixel above 150 C in view, or invalid)
- C_d5.00_tilt+5.0_r1_SIM: hot area touches the bottom image row in all 8 frames: base below the field of view (nearest visible ground about 5.3 m), not observable

Flux-disc guard (disc on PETG tabs, 70 C user-set): 0 run(s) stopped by the record script.

Plan coverage (sheet distances x tilts): complete.

A frame whose hot area is cut off by the image (lowest hot pixel on the bottom row, or hot pixels in the outermost columns at either side: crossing.geometry.near_edge base_cut_off) is not used: the base may be outside the field of view, the estimate would only be a bound and its interval would start at 0 m (trivially covering the tape distance).
Flat surveyed ground; lens distortion not corrected; a panel edge is sharper than a real flame base. Files: C_runs.csv, C_error_vs_distance.png.

_Results are reported as measured, including failures. Verdicts are advisory for trained crews and every limit is a placeholder for a fire service to set. These results do not show operational readiness._
