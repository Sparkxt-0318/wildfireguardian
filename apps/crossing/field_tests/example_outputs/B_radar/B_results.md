### SIMULATED: Test B - radar, corner reflector, nothing / flame / smoke / mist

> **SIMULATED DATA: these numbers come from field_tests/simulate.py, not from hardware. They only exercise the analysis; they are not a measurement.**

Corner reflector at 2, 3, 4, 5 m; window 3 s; noise = std of the 'nothing' windows; 'below noise' = |effect| < 3 sigma for loss, amplitude flicker and phase flicker.

| d (m) | condition | windows | SNR (dB) | loss effect (dB) | sigma | amp flicker effect (dB) | sigma | phase flicker effect (rad) | sigma | FLAME_EFFECT frac |
|---|---|---|---|---|---|---|---|---|---|---|
| 2.000 | nothing | 27 | 48.013 | 0.000 | 0.012 | 0.000 | 0.006 | 0.000 | 0.000879 | 0.000 |
| 2.000 | flame | 27 | 48.013 | 0.006 | 0.012 | 0.009 | 0.006 | 0.038 | 0.000879 | 0.000 |
| 2.000 | smoke | 18 | 48.013 | -0.003 | 0.012 | 0.000327 | 0.006 | -1.65e-05 | 0.000879 | 0.000 |
| 2.000 | mist | 18 | 48.013 | 1.022 | 0.012 | 0.348 | 0.006 | 0.001 | 0.000879 | 0.000 |
| 3.000 | nothing | 27 | 41.006 | 0.000 | 0.039 | 0.000 | 0.014 | 0.000 | 0.002 | 0.000 |
| 3.000 | flame | 27 | 41.006 | 0.011 | 0.039 | 0.005 | 0.014 | 0.019 | 0.002 | 0.000 |
| 3.000 | smoke | 18 | 41.006 | 0.005 | 0.039 | -0.004 | 0.014 | -0.000507 | 0.002 | 0.000 |
| 3.000 | mist | 18 | 41.006 | 1.101 | 0.039 | 0.304 | 0.014 | 0.002 | 0.002 | 0.000 |
| 4.000 | nothing | 27 | 36.084 | 0.000 | 0.062 | 0.000 | 0.027 | 0.000 | 0.003 | 0.000 |
| 4.000 | flame | 27 | 36.084 | 0.030 | 0.062 | -0.006 | 0.027 | 0.010 | 0.003 | 0.000 |
| 4.000 | smoke | 18 | 36.084 | 0.039 | 0.062 | -0.017 | 0.027 | -0.002 | 0.003 | 0.000 |
| 4.000 | mist | 18 | 36.084 | 1.132 | 0.062 | 0.260 | 0.027 | 0.004 | 0.003 | 0.000 |
| 5.000 | nothing | 27 | 32.153 | 0.000 | 0.073 | 0.000 | 0.041 | 0.000 | 0.004 | 0.000 |
| 5.000 | flame | 27 | 32.153 | -0.013 | 0.073 | 0.016 | 0.041 | 0.005 | 0.004 | 0.000 |
| 5.000 | smoke | 18 | 32.153 | 0.034 | 0.073 | -0.007 | 0.041 | 0.002 | 0.004 | 0.000 |
| 5.000 | mist | 18 | 32.153 | 1.257 | 0.073 | 0.215 | 0.041 | 0.005 | 0.004 | 0.000 |

- 2.0 m, flame: **flame effect above 3 sigma of the nothing runs (flicker_phase_rad)** (detector FLAME_EFFECT in 0 % of windows)
- 2.0 m, smoke: **smoke effect below noise** (detector FLAME_EFFECT in 0 % of windows)
- 2.0 m, mist: **mist effect above 3 sigma of the nothing runs (loss_db, flicker_amp_db)** (detector FLAME_EFFECT in 0 % of windows)
- 3.0 m, flame: **flame effect above 3 sigma of the nothing runs (flicker_phase_rad)** (detector FLAME_EFFECT in 0 % of windows)
- 3.0 m, smoke: **smoke effect below noise** (detector FLAME_EFFECT in 0 % of windows)
- 3.0 m, mist: **mist effect above 3 sigma of the nothing runs (loss_db, flicker_amp_db)** (detector FLAME_EFFECT in 0 % of windows)
- 4.0 m, flame: **flame effect above 3 sigma of the nothing runs (flicker_phase_rad)** (detector FLAME_EFFECT in 0 % of windows)
- 4.0 m, smoke: **smoke effect below noise** (detector FLAME_EFFECT in 0 % of windows)
- 4.0 m, mist: **mist effect above 3 sigma of the nothing runs (loss_db, flicker_amp_db)** (detector FLAME_EFFECT in 0 % of windows)
- 5.0 m, flame: **flame effect below noise** (detector FLAME_EFFECT in 0 % of windows)
- 5.0 m, smoke: **smoke effect below noise** (detector FLAME_EFFECT in 0 % of windows)
- 5.0 m, mist: **mist effect above 3 sigma of the nothing runs (loss_db, flicker_amp_db)** (detector FLAME_EFFECT in 0 % of windows)

Safety gate (B_gate.csv): 20 flame/smoke run(s), 0 without a recorded risk assessment and supervisor. Flame source: as approved in the signed risk assessment; the analysis assumes a Bunsen-size flame (non-Bunsen runs are flagged).
Plan coverage (2, 3, 4, 5 m; >= 3 nothing, 3 flame, 2 smoke, 2 mist per distance): complete.

Flux-disc guard (disc on PETG tabs, 70 C user-set): 0 run(s) stopped by the record script.

The radar alone never decides FLAME: the app needs the radar effect AND flame-temperature pixels at the same bearing.
Files: B_conditions.csv, B_windows.csv, B_gate.csv, B_radar_conditions.png.

_Results are reported as measured, including failures. Verdicts are advisory for trained crews and every limit is a placeholder for a fire service to set. These results do not show operational readiness._
