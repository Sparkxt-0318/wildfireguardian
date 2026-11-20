# Test D: fail-safe, fault to CLOSED

Status: protocol written 2026-11-17, not yet run. Print and fill in by hand. No fire.

## Purpose

For each single fault (unplug a sensor, open a thermocouple, drop Wi-Fi, pull 12 V, frozen data), measure the time
from the event mark to the first CLOSED verdict that the app attributes to that fault. **Pass if <= 2 s.**
Any CROSS FAST / SPRAY THEN RE-CHECK / REOPENED after the app had noticed the fault (and before the restore) is a
hard failure.

Expected by design (not yet measured): sensor unplug and thermocouple faults should be well under 2 s (the Pi
reports `no_device` / `error` at once); a Wi-Fi drop or power pull is noticed after `silence_s = 1.5 s` with no
message at all (expect 1.4-1.7 s), frozen thermal data after `freeze_s = 1.0 s` of identical pixels (expect
0.8-1.3 s; DESIGN.md section 5 as built 2026-11-17). Report every row as measured, pass or fail.

## Equipment

| Item | Notes | Tick |
|---|---|---|
| Roof unit, powered from 12 V, streaming | | [ ] |
| Laptop running the crossing app live: `python -m crossing --pi ws://10.42.0.1:8770/stream` | Its State socket is ws://127.0.0.1:8781/ws | [ ] |
| Second terminal for `field_tests.d_failsafe_run` | | [ ] |
| For `thermal_freeze`: the Pi in sim mode with a session made with `--freeze thermal@T`, and `d_failsafe_run` started with `--pi` | Needs `wfgvu.synth`; without the `--pi` copy the row is NOT_MEASURED | [ ] |

## Safety

- 12 V pull: use the inline connector, not the battery terminals; no metal tools near the open plug.
- I2C lead (BNO055 SDA): pull a jumper at a connector; never let the loose lead touch other pins (3.3 V logic).
- USB hot-unplug is normal use. Thermocouple connectors: hold the connector body, not the wire.

## Steps

1. Start the app (live), confirm health lights and that States arrive.
2. `python -m field_tests.d_failsafe_run --pi ws://10.42.0.1:8770/stream`
   (default faults: thermal_unplug, radar_unplug, gnss_unplug, imu_disconnect, tc_plate_open, tc_air_open,
   tc_housing_open, wifi_drop, pi_power; choose with `--faults a,b,c`).
3. For each fault: read the "Prepare" line, put your hand on the plug, press Enter. Act exactly at **NOW** after
   the 3-2-1 countdown. The script shows the time to CLOSED live.
4. Press Enter after restoring; wait until the script says the sensor is fresh again.
5. Repeat the whole set 3 times (3 sessions).

On a bench with no flame the verdict is already CLOSED before every fault; the time measured is then to the
CLOSED in which a reason code or health flag of that fault APPEARED compared with the last State before the fault
(the moment the app knew). Only exact codes count (`SENSOR_NOT_FRESH:<sensor>`, `SENSOR_FAULT:<sensor>`,
`INPUT_TOO_OLD:<sensor>`, ..., `LINK_DOWN`); bench reasons such as `RADAR_UNKNOWN`, `GNSS_NO_FIX` or `FLAME_*` never
do. If the fault's cause is already visible before the fault (mark late, sensor already down) the row is
NOT_ATTRIBUTABLE, never PASS; repeat that fault. Write that down; it is stated per row.

Offline alternative: `python -m field_tests.d_failsafe_analyse --research-log apps/crossing/records/<session> --marks records/field_tests/D/<run>/marks.jsonl`

## What to record (by hand)

| Session | Fault | Verdict before | Script time (s) | PASS/FAIL | Anything odd (UI, sounds, LEDs) |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |

## Known limits

- Operator reaction at NOW adds a few tenths of a second either way (not measured). States arrive at 5 Hz, so the
  resolution is 0.2 s.
- Frozen data cannot be produced physically on the stock unit; it needs the Pi's sim mode with a freeze overlay.
  The operator cannot see when the sim session reaches T, so NOW can be off by seconds: the analysis takes this
  fault's time from the thermal frames the laptop received (the `--pi` copy, or the research log's
  `wire.jsonl.gz`), as the last frame before identical repeats. That overstates the latency by up to one wire
  period (0.25 s at 4 Hz). Without those frames the row is reported as NOT_MEASURED ("fault time unknown, not a
  measurement") and is not scored. The Pi does not yet send a `sim_start` / overlay event on the wire.
- Not covered: a Pi health fault (under-voltage, throttling, `pi` heartbeat not "ok"). `pi` is a required input for
  every go verdict since decision D1, but producing under-voltage needs a variable bench supply and risks the SD
  card; CLOSED within 2 s for it is therefore not measured by this test (it is covered only by the unit tests in
  apps/crossing/tests/test_failsafe.py, which are not hardware).
