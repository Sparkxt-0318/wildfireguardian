# Sample sessions: SIMULATED

Every session in this folder is **synthetic**. `wfgvu/synth.py` generated them with illustrative physics. They are
not recordings, not measurements, and not evidence of how real flames, smoke, water mist or a real crossing look
to the TC001 camera, the IWR6843AOP radar or the thermocouples. In particular, the radar "flame effect" (phase
walk plus a small loss on echoes seen through the flame) is an assumption of this project. Every message carries
`"sim": true`, and each `session.json` has `"sim": true`, a `"simulated"` notice and a `truth` block.

They exist so that the sensor head's sim mode and the laptop app can be run and tested without hardware:

```sh
cd hardware/vehicle-unit
python -m wfgvu --sim samples/flame_front            # replay through the drivers and the WebSocket server
python -m wfgvu.synth samples samples                # regenerate this folder (seed 1, --compact settings)
```

## Format

Each folder is a session directory in the recorded-session format (DESIGN.md section 4): `session.json` plus
`<sensor>.jsonl.gz` for the eight sensors (protocol `reading` and `heartbeat` messages, heartbeats every 0.5 s) and
`events.jsonl.gz` (a `sim_note` event, plus one `synth_overlay` event per failure overlay). The two
`crossing_return*` folders also hold `dem.npz`: a SIMULATED DEM of exactly their synthetic ground plane in the laptop's
`crossing.terrain.Dem` format ("local-enu", 2 m cells), named in session.json `dem`. The laptop needs it for
REOPENED (`--dem samples/crossing_return/dem.npz`; FS-8 line of sight). It is bare earth and proves nothing about
real terrain.

Rates: thermal 4 Hz (the laptop's wire rate; a real TC001 records about 25 Hz), radar 10 Hz (4 Hz in the two
68 s `crossing_return*` sessions, so the folder stays under 5 MB), thermocouples 10 Hz, IMU 20 Hz, GNSS 5 Hz, Pi
health 1 Hz. The samples use the generator's `--compact` settings to stay small:

- Thermal has no per-pixel noise or row banding. The scene is rounded to 0.25 K, and a whole-frame offset walks
  by 1-2 raw counts (1/64 K) per frame, so consecutive frames always differ.
- Radar uses a reduced grid of 100 bins x 0.25 m (25 m) with 4 virtual antennas (uniform lambda/2), noise of
  1 int16 count per component, and a range profile in 0.5 dB steps. The default real config is 128 bins x 0.468 m (max 54 m)
  with 12 virtual antennas (`config/iwr6843aop_vu.cfg`; the old 512 bins x ~4.9 cm, 22.5 m config is kept as
  `config/iwr6843aop_vu_short.cfg`).

Common scene: the road climbs at 4 % (grade 0.04), so the vehicle's true pitch is atan(0.04) = 2.29 deg and its roll is 0.
The camera and radar sit 2.6 m above the ground point and the plate at 2.5 m (config/unit.yaml placeholders), with
mount angles of 0. Ambient is 25 C. The GNSS track starts at 36.39 N, 128.70 E (near Uiseong) with a course of 30 deg. The scene
also holds a sign post at 7 m (20 deg left) and a parked vehicle or guardrail end beyond the flame (the "solid
echo"; left out of `crossing_return*`, where it would stand on the return path). `truth.baseline_window_s` gives the stretch of no-flame radar frames for capturing a radar baseline.

## Sessions

| Folder | Scenario | Length | What it contains | Intended laptop reading |
|---|---|---|---|---|
| `no_fire` | `no_fire` | 40 s | Stationary vehicle, empty road, no fire. | NO_FLAME |
| `smoke_only` | `smoke_only` | 40 s | Smoke slab from 8 s, 12-22 m ahead, 12 m tall, 75 C, mostly transparent in LWIR (thermal max about 48 C). No radar effect. | NO_FLAME |
| `flame_front` | `flame_front` | 45 s | Line fire across the road appears at 8 s with its near edge at 14.0 m. It is 3.0 m deep and 2.0 m tall, and advances at 0.05 m/s towards the stationary vehicle. Thermal saturates at 550 C (low gain). The radar effect applies to echoes behind the flame. | FLAME after 8 s, NO_FLAME before |
| `water_mist` | `water_mist` | 40 s | Cool mist curtain (19 C) from 8 s, 4-8 m ahead. Radar: 2 dB loss plus amplitude flicker beyond 4 m, no phase walk. | Radar effect but cold thermal, so NO_FLAME |
| `corner_reflector_3m` | `corner_reflector` | 40 s | Corner reflector at 3.0 m and radar height, 50 dB echo, looks cold (5 C) in LWIR. Test B geometry. | NO_FLAME. Strong static echo at 3 m |
| `crossing` | `crossing` | 45 s | Flame (12.0 m, 3.0 m deep, 2.0 m tall, 0.02 m/s spread) appears at 8 s. The vehicle drives off at 20 s, reaches 5 m/s, crosses the flame at 23.59-24.18 s and stops 25 m beyond the far edge. Plate flux peaks at 50 kW/m2 (true). `truth.measured_thickness_m` = 10.215 m: the time the true flux is above 5 kW/m2 multiplied by speed. It includes the radiant zone ahead of the flame. | FLAME while stationary, UNKNOWN radar while moving |
| `after_pass` | `after_pass` | 55 s | No flame. Burnt road 10-16 m ahead (95 to 70 C) under a thin haze. The vehicle drives off at 4 s at 3 m/s through the burnt zone and stops 25 m past its far edge (`truth.burnt_zone.far_edge_lat/lon`). True flux stays at or below 0.15 kW/m2 and no pixel reaches 300 C. | Input for REOPENED tests |
| `flame_front_fail_radar` | `flame_front --fail radar@20` | 40 s | Same flame as `flame_front`. Radar readings stop at 20 s. Heartbeats stay `ok` for 1 s, then `stale` for 1 s, then `no_device` until the end. | Radar not fresh after the stop, so CLOSED |
| `flame_front_freeze_thermal` | `flame_front --freeze thermal@20` | 40 s | Same flame. From 20 s every thermal reading repeats the 19.80 s frame exactly, with `seq` still increasing and heartbeats `ok`. | Laptop frozen-data check must mark thermal not fresh, so CLOSED |
| `crossing_return` | `crossing_return` | 68 s | Same flame as `crossing` (from 4 s). The vehicle drives off at 9 s and crosses it at 12.62-13.21 s at 5 m/s. The flame burns out at 16 s and the burnt strip cools (time constant 8 s). The vehicle turns round forward at 3 m/s from 17.1 s to 32.85 s on an 8 m radius "teardrop", so GNSS course follows the heading. It comes back on a lane 3 m left of its track and stops at 36.69 s, 25 m past the far edge, facing the crossed road (course 210 deg). The turnaround needs 13 m of space to the right of the road. No parked vehicle beyond the flame. Includes `dem.npz`. | With `--dem`: REOPENED after the vehicle stops and the 30 s quiet hold completes (64.8 s on the laptop replay, `apps/crossing/tests/test_reopen_e2e.py`). Without a DEM it stays CLOSED |
| `crossing_return_hot` | `crossing_return_hot` | 68 s | Identical, but a 600 C hot area (2 m along x 3 m across, flat on the road) stays in the middle of the crossed strip after burn-out. It reads about 549 C from the stop. | Never REOPENED (flame-temperature pixels over the crossing) |

Values in the table are from `session.json` (`truth`) of the committed files.

## What these samples cannot tell you

- Whether any real sensor behaves like this. The flame emissivity, smoke and mist absorption, radar clutter,
  radar flame effect, plate heating and thermocouple lag are all toy models with stated, unvalidated parameters.
- Whether a real crew can turn round like `crossing_return*` does. The turnaround is a smooth forward "teardrop" at a
  constant 3 m/s with no reversing, the flame burns out on cue at 16 s and the strip cools with an 8 s time constant.
  All of this was chosen so that the REOPENED view can be reached. None of it is measured.
- Whether the laptop's thresholds are right. Agreement between the laptop and `truth` on these files only shows
  that the two codes use the same geometry conventions. It does not show that the pipeline works on hardware.
