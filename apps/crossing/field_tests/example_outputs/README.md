# Example outputs: SIMULATED

**Every file in this folder was produced from SIMULATED inputs** (`field_tests/simulate.py`), by
`python -m field_tests.run_demo`. They show the format of the CSV / PNG / Markdown that each analysis script writes.
They are not measurements, they say nothing about how the unit or the app behaves on hardware, and they must not be
copied into `apps/crossing/RESULTS.md` as results.

The simulators deliberately include failures (a Bunsen radiant fraction that differs from the sheet, flame effects
below the radar noise at long range, a near edge outside the camera's field of view, one test D fault (imu_disconnect,
latency set to 2.3-2.6 s for this demo only) that takes longer than 2 s to detect and so FAILS, a thermal_freeze
whose operator mark is seconds off and is timed from the received thermal frames instead, a radar that stops while
its heartbeat says ok, link dropouts) so that every "report failures as measured" path of the analysis is exercised.

| Folder | Test | Snippet |
|---|---|---|
| A_flux | flux plate vs Bunsen burner | A_flux/A_results.md |
| B_radar | radar, corner reflector, nothing / flame / smoke / mist | B_radar/B_results.md |
| C_thermal | thermal near-edge distance vs tape | C_thermal/C_results.md |
| D_failsafe | fault to CLOSED timing | D_failsafe/D_results.md |
| E_vehicle | 30-minute drive | E_vehicle/E_results.md |
| F_housing | water spray and hot-air gun | F_housing/F_results.md |

`wfgvu.synth` present when generated: yes. It is used only by the test B interop test
(`simulate.synth_b_nothing`); these example outputs come from `field_tests/simulate.py`.
