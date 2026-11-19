# Limits sheet: WildfireGuardian vehicle unit and crossing app

**Every number on this page is a PLACEHOLDER, except the 70 °C flux disc limit, which you set for the PETG tabs.**
None was set by a fire service, and none was checked on a real fire.
The verdicts are advisory for trained crews and never an instruction. The unit is not operationally ready.

The only claim allowed, and only after tests A-F have run and been reported in `RESULTS.md`:
"vehicle-mountable unit, tested on a car and on lab flames, ready for a fire-service trial". As of 2026-11-17 those
tests have not run, so the claim may not be made yet.

Sources: `crossing/vehicles.yaml`, `crossing.yaml`, `crossing/radar_flame.py` and `crossing/decision.py`.

## Vehicle profiles (`vehicles.yaml`; every row is `placeholder: true`)

| profile | length m | width m | height m | sensor height m | max safe speed m/s | dose limit TDU | intake air limit °C | water |
|---|---|---|---|---|---|---|---|---|
| fire_engine | 8.5 | 2.5 | 3.3 | 3.5 | 8.3 | 500 | 80 | yes |
| water_tanker | 9.5 | 2.5 | 3.2 | 3.4 | 6.9 | 500 | 80 | yes |
| pickup | 5.3 | 1.9 | 1.8 | 2.0 | 11.1 | 200 | 70 | no |
| command_car | 4.8 | 1.9 | 1.8 | 2.0 | 11.1 | 150 | 70 | no |
| evacuation_minibus | 7.0 | 2.1 | 2.7 | 2.9 | 8.3 | 80 | 70 | no |
| custom | 5.0 | 2.0 | 2.0 | 2.2 | 8.3 | 100 | 70 | no |

TDU = (kW/m²)^(4/3)·s. Dose is computed from the in-flame flux over time_in_flame, plus the approach and exit legs
(`approach_m` 30 m each side).

time_in_flame = (decision depth upper end + vehicle length) / speed.

## When each verdict is given

| verdict | given when |
|---|---|
| CLOSED | The default. Also given on: link down, any sensor heartbeat stale > 2.0 s, radar UNKNOWN, no solid echo beyond the flame, dose over the limit at max safe speed, intake air over the limit, near edge not observed, flame evidence < 3.0 s, verdict older than 5 s. |
| CROSS FAST | Fused FLAME held >= 3.0 s, every sensor fresh, dose at max safe speed <= the limit. Shows the minimum speed. Crew app only, never sent to routing. |
| SPRAY THEN RE-CHECK | Only for a vehicle with water, and only if CROSS FAST fails because the dose at max safe speed is over the limit by no more than 25 % (`spray_margin` 0.25). Crew app only. |
| REOPENED | All of the following hold: the vehicle has passed the crossing; it is stopped (<= 1.0 m/s); it faces the crossing within 40 m with DEM line of sight; plate flux < 1.0 kW/m²; 0 flame pixels in the image and 0 in the crossing's columns; every sensor is fresh. All of this held for 30 s while stopped. The verdict carries a GNSS stamp. |

## Decision and freshness thresholds

| setting | value | where |
|---|---|---|
| verdict lifetime | 5 s | `decision.verdict_ttl_s` |
| sensor heartbeat stale | 2.0 s | `link.heartbeat_stale_s`, `link.stale_s` |
| link silence = link down | 1.5 s | `link.silence_s` |
| frozen data (identical values) | thermal 1.0 s, radar 1.0 s, IMU 2.0 s, thermocouples 5.0 s, GNSS 5.0 s | `link.freeze_s` |
| maximum age of a value used | 1.0 s (GNSS 1.5 s, Pi health 1.6 s) | `use_max_age_s` |
| flame pixel threshold | 300 °C, camera in low gain only | `thermal.t_flame_c` |
| low gain verified | **false**: every LIVE verdict is CLOSED until a lab check on a target > 150 °C | `thermal.low_gain_verified` |
| **flux disc maximum (user-set, not a placeholder)** | **70 °C**: a reading at or above it is a tc_plate fault, PLATE_DISC_OVER_TEMP, and gives CLOSED. Every flux recording script and `wfgvu.tccheck` stop the run and warn. It cannot be set above 70. | `flux.disc_max_c`, `unit.yaml sensors.tc_plate.disc_max_c` |
| camera-radar parallax correction | off (`offset_x_sign: 0`) until the build manual's x sign is confirmed; about 0.25° at 10 m | `mount.offset_x_sign` |
| path half-width for the near edge | 6° | `geometry.path_half_width_deg` |
| IMU calibration minimum | 1 (BNO055 accel and gyro) | `geometry.imu_min_calib` |
| GNSS course trusted as heading | >= 2.0 m/s | `geometry.reliable_course_speed_m_s` |
| REOPENED view distance, FOV margin, road half-width | 40 m, 4°, 4 m | `geometry.reopen_*` |
| REOPENED hold, flux, hot pixels, maximum speed | 30 s, 1.0 kW/m², 0, 1.0 m/s | `decision.reopen_*` |
| flame evidence before CROSS FAST / SPRAY | 3.0 s continuous | `decision.min_flame_evidence_s` |
| radiant fraction chi | 0.30 | `decision.chi` |
| radar: stationary for baseline / baseline invalid after a move of | 0.3 m/s / 3 m | `radar.*` |
| radar: loss and flicker thresholds | 4 sigma and >= 1 dB loss; 4 sigma flicker | `radar_flame` defaults |
| radar: solid echo above clutter, noise-rise gate | 12 dB, 10 dB | `radar_flame` defaults |
| radar: effect held before FLAME_EFFECT | 2 s | `radar_flame` |
| depth: decision upper end | max(combined upper end, every valid non-experimental estimator's upper end); narrowing is off | `depth.narrow_decision_hi: false` |
| depth: minimum calibrated pairs before narrowing is allowed | 30 per fuel type | `depth.narrow_decision_hi_min_pairs` |
| depth: estimators-disagree flag | central values differ by > 3x (shown, does not close) | `depth.disagree_factor` |
| measured thickness for calibration | flux >= max(5 kW/m², 0.5 x pulse peak); vehicle >= 0.5 m/s | `crossing.*` |

## Step 9 routing link (off unless `WFG_API_LIVE_CLOSURES=1`)

- Only CLOSED and REOPENED are sent. CROSS FAST and SPRAY never leave the crew app.
- Simulated or replayed sessions are never sent as road state.
- Matching:
  - the client merges and matches within 50 m;
  - the API snaps within 50 m, with a 20 m match margin.
- Timing:
  - a CLOSED is re-asserted every 60 s and on each reconnect;
  - an ack times out after 5 s.
- The API accepts 20 events/s, with a burst of 60.
- Authentication: a token in the WebSocket subprotocol, read from an environment variable and never logged.
- A REOPENED is honoured only with the claim token of the CLOSED it lifts. If it is refused, the road stays closed.
- Closures are held in API memory only.

## What is not covered

- Smoke, steam and water mist are not targets and must never give FLAME. This was tested on simulated samples only.
- The following were not measured: radar on the EVM, the P2 Pro camera's gain and FOV, flux plate absorptivity, housing
  temperatures, and power.
- The camera pitch (-18°) and mounting height (2.6 m) are configured values. Measure them on the vehicle.
