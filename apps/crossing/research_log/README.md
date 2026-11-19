# Research log: column dictionary (step 10, DESIGN.md section 11)

Written by `crossing/research_log.py` for every laptop session to `apps/crossing/records/<session>/` (git-ignored).
`python -m crossing --replay <session dir>` replays a session from its `wire.jsonl.gz`.

**Nothing in a research log is a validated measurement of fire behaviour.** Sessions recorded from synthetic data
have `sim = true` in every row that carries a `sim` column and in `session.json`. All limits that appear (dose
limit, speeds, thresholds) are PLACEHOLDERS.

## Conventions

- `rx_mono`: laptop `time.monotonic()` in seconds at receipt (or at the pipeline tick). This is the clock that decides
  freshness. Only differences between `rx_mono` values are meaningful.
- `t_mono_pi` / `t_pi`: the roof unit's (Pi) `time.monotonic()` from the message envelope, seconds. The plate flux and
  the crossing pulse use this clock (sample timing on the Pi, no Wi-Fi jitter).
- `t_utc` / `utc`: ISO 8601 UTC strings (Pi wall clock, or laptop wall clock for app rows).
- Empty cell = missing (None). Booleans are `true` / `false`. Lists are `;`-joined. `inf` appears where an interval
  end is unbounded (for example an occluded near edge).
- Units: temperatures in deg C (`_c`), thermal images in K, flux kW/m2, dose TDU = (kW/m2)^(4/3) s, distances m,
  speeds m/s, angles deg, radar amplitudes dB.

## Files

| file | written | content |
|---|---|---|
| `session.json` | start, on changes, at close | schema, versions, config, vehicle, fuel (+ `changes`), sim flag, Pi ids, baselines, row counts, files |
| `readings_<sensor>.csv` | every reading | flattened scalars of each protocol reading (below) |
| `thermal_frames.<n>.npz` | every `chunk_frames` (100) thermal readings | `rx_mono[n]`, `seq[n]`, `raw_u16[n,h,w]`, `raw_per_k[n]`; temperature K = `raw_u16 / raw_per_k` |
| `radar_frames.<n>.npz` | every `chunk_frames` radar readings, or when bins/antennas change | `rx_mono[n]`, `seq[n]`, `frame[n]`, `range_res_m[n]`, `profile_db[n,bins]` (NaN if absent), `iq[n,bins,ant]` complex64 (0 if absent), `has_iq[n]`, `has_profile[n]` |
| `heartbeats.csv` | every Pi heartbeat | |
| `events.csv` | Pi events, link up/down, parse errors, app changes | |
| `verdicts.csv` | every pipeline tick (5 Hz) | verdict and its main inputs |
| `depth.csv` | every tick | depth estimators, combination, intensity |
| `flux.csv` | every plate sample (10 Hz) | plate calorimeter output and running dose |
| `health.csv` | every 1 s | link and per-sensor freshness |
| `pairs.csv` | each stored predicted-vs-measured pair | calibration pairs of this session |
| `wire.jsonl.gz` | every message | `{"rx": rx_mono, "msg": <protocol message>}` or `{"rx", "link": "up"/"down", "reason"}` |
| `radar_baseline_<n>.json` | each baseline capture | `RadarBaseline.to_dict()` |
| `<table>.parquet` | at close, if pyarrow is importable | same columns and rows as the CSV (`research_log.export_parquet`) |

Readings with `chunk`/`index` point at row `index` of `thermal_frames.<chunk>.npz` / `radar_frames.<chunk>.npz`.
The calibration pairs themselves are also appended to the per-laptop store (`apps/crossing/records/calibration/
pairs.jsonl` for live real sessions, `pairs_sim.jsonl` for simulated ones, `pairs_replay.jsonl` for replays of
recorded real sessions; they are never mixed and only `pairs.jsonl` calibrates live decisions).

## readings_<sensor>.csv

Common columns (every sensor): `rx_mono`, `t_mono_pi`, `t_utc`, `seq` (per-sensor reading counter from the Pi;
thermal advances by the wire decimation step), `sim`.

| sensor | columns | meaning |
|---|---|---|
| `thermal` | `w`, `h`, `gain`, `shutter`, `raw_per_k`, `t_min_c`, `t_max_c`, `t_mean_c`, `flame_pixels`, `valid`, `reason`, `chunk`, `index` | `w`, `h` image size px; `gain` low/high; `shutter` (Pi heuristic); `raw_per_k`; `t_min_c`, `t_max_c`, `t_mean_c` of the frame; `flame_pixels` (pixels >= flame threshold, empty if invalid); `valid`, `reason` (thermal.validate_frame); `chunk`, `index` |
| `radar` | `frame`, `range_res_m`, `n_bins`, `frame_ok`, `tlv_types`, `n_points`, `has_heatmap`, `n_ant`, `has_profile`, `chunk`, `index` | `frame` (radar frame number); `range_res_m`; `n_bins`; `frame_ok`; `tlv_types`; `n_points` (point cloud size); `has_heatmap`, `n_ant`; `has_profile`; `chunk`, `index` |
| `tc_plate` | `temp_c`, `cj_c`, `fault` | `temp_c` hot junction deg C; `cj_c` cold junction deg C; `fault` (open, short_gnd, short_vcc, spi or empty) |
| `tc_housing` | `temp_c`, `cj_c`, `fault` | as tc_plate |
| `tc_air` | `temp_c`, `cj_c`, `fault` | as tc_plate |
| `imu` | `roll_deg`, `pitch_deg`, `heading_deg`, `grav_x`, `grav_y`, `grav_z`, `calib_sys`, `calib_gyro`, `calib_accel`, `calib_mag` | `roll_deg` (+ right side down), `pitch_deg` (+ nose up), `heading_deg` (magnetic, not used); `grav_x`, `grav_y`, `grav_z` m/s2; `calib_sys`, `calib_gyro`, `calib_accel`, `calib_mag` (BNO055 0-3) |
| `gnss` | `fix`, `lat`, `lon`, `alt_m`, `speed_m_s`, `course_deg`, `hdop`, `sats`, `utc` | `fix` 0/1/2; `lat`, `lon` deg; `alt_m`; `speed_m_s`; `course_deg` (true, meaningless when stopped); `hdop` (not metres); `sats`; `utc` |
| `pi` | `cpu_c`, `throttled_hex`, `under_voltage_now`, `under_voltage_ever`, `input_v`, `disk_free_mb`, `rec_bytes` | `cpu_c`; `throttled_hex`; `under_voltage_now`, `under_voltage_ever`; `input_v`; `disk_free_mb`; `rec_bytes` |

## heartbeats.csv

`rx_mono`, `t_mono_pi`; `sensor` (or `unit` for the Pi server itself); `status` (ok, no_device, error, stale, sim_ended); `detail`; `last_reading_seq`; `rate_hz` (measured on the Pi); `seq` (heartbeat counter).

## events.csv

`rx_mono`; `source` (`pi` = protocol event, `link` = link up/down or parse error, `app` = vehicle / fuel / baseline change, crossing without a pair); `kind`; `detail`.

## verdicts.csv (every tick)

| column | meaning |
|---|---|
| `rx_mono` | tick time (laptop) |
| `utc` | laptop UTC |
| `state` | verdict shown (effective: CLOSED once older than 5 s) |
| `decided_state` | state decided at this tick |
| `verdict_id` | unique id of the verdict (sent with sim-link events) |
| `reasons` | reason codes (`CODE` or `CODE:detail`), `;`-joined |
| `min_speed_m_s` | CROSS FAST: smallest speed with dose <= limit (0.1 m/s, rounded up); SPRAY: max safe speed |
| `time_in_flame_s` | (depth_hi_decision + vehicle length) / speed |
| `dose_tdu` | closed-form dose at that speed |
| `dose_limit_tdu` | vehicle dose limit (PLACEHOLDER) |
| `dose_fds_ref_tdu` | FDS C064 reference dose (not a measurement, never decides) |
| `flame_status` | fused FLAME / NO_FLAME / UNKNOWN |
| `radar_status` | FLAME_EFFECT / NO_EFFECT / UNKNOWN |
| `thermal_flame` | flame-temperature pixels at the path bearing |
| `near_edge_m` | along-course distance to the flame base |
| `far_echo_m` | horizontal distance of the first solid radar echo beyond the flame base |
| `depth_m` | combined depth |
| `depth_lo_m` | 90 % interval low end |
| `depth_hi_m` | 90 % interval high end of the combined depth (display; not the dose upper end) |
| `intensity_kw_m` | Byram intensity central value |
| `intensity_hi_kw_m` | intensity upper end used by the dose |
| `lat` | GNSS latitude |
| `lon` | GNSS longitude |
| `speed_m_s` | GNSS speed |
| `passed` | vehicle is past the recorded far edge / flame location (REOPENED precondition) |
| `reopen_quiet_s` | how long the REOPENED quiet conditions have held |
| `link_up` | link up at the tick |
| `sim` | simulated session |
| `vehicle` | vehicle profile name |
| `fuel` | fuel code |
| `depth_hi_decision_m` | (appended) depth upper end the dose uses: DEPTH-HI rule, >= the largest valid non-experimental estimator upper end (depth.py) |

## depth.csv (every tick)

| column | meaning |
|---|---|
| `rx_mono` | tick time |
| `valid` | a combined depth exists (False -> CLOSED) |
| `depth_m` | combined depth |
| `lo_m` | 90 % low end |
| `hi_m` | 90 % high end |
| `level` | interval level (0.90) |
| `used` | estimators in the combination |
| `calibrated` | conformal scale in use for this fuel |
| `n_pairs` | usable calibration pairs of this fuel |
| `scale` | interval scale (1.5 uncalibrated) |
| `sigma_log` | 1-sigma of ln(depth) of the combination |
| `ceiling_m` | radar ceiling (far echo - near edge) |
| `flags` | notes from depth.combine |
| `spread_burn_m`, `spread_burn_lo_m`, `spread_burn_hi_m`, `spread_burn_valid`, `spread_burn_reason` | estimator `spread_burn`: value, 90 % interval, valid flag, reason |
| `byram_m`, `byram_lo_m`, `byram_hi_m`, `byram_valid`, `byram_reason` | estimator `byram`: value, 90 % interval, valid flag, reason |
| `radar_ceiling_m`, `radar_ceiling_lo_m`, `radar_ceiling_hi_m`, `radar_ceiling_valid`, `radar_ceiling_reason` | estimator `radar_ceiling`: value, 90 % interval, valid flag, reason |
| `flicker_extent_m`, `flicker_extent_lo_m`, `flicker_extent_hi_m`, `flicker_extent_valid`, `flicker_extent_reason` | estimator `flicker_extent`: value, 90 % interval, valid flag, reason |
| `radar_loss_depth_m`, `radar_loss_depth_lo_m`, `radar_loss_depth_hi_m`, `radar_loss_depth_valid`, `radar_loss_depth_reason` | estimator `radar_loss_depth`: value, 90 % interval, valid flag, reason |
| `intensity_kw_m` | Byram intensity central |
| `intensity_lo_kw_m` | low end |
| `intensity_hi_kw_m` | high end |
| `intensity_sources` | byram_flame_height and/or spread_rate |
| `flame_height_m` | flame height |
| `flame_height_lo_m` | low end |
| `flame_height_hi_m` | high end |
| `near_edge_m` | near edge |
| `fuel` | fuel code |
| `hi_decision_m`, `hi_decision_from`, `disagree_ratio` | (appended) upper end the dose uses (DEPTH-HI rule), the estimator or "combined" it came from, max/min central value of the decision estimators (`ESTIMATORS_DISAGREE` in `flags` above `depth.disagree_factor`) |

Estimators (DESIGN 6.6): `spread_burn` (a, R x t_r from the near-edge world track), `byram` (b, flame height), `radar_ceiling` (c, upper bound, used only when calibration trusts it), `flicker_extent` (d, experimental, never used for the depth; whether it agreed with the measured thickness is reported per pair in `pairs.csv` `flicker_extent_agrees` and per fuel in the calibration status), `radar_loss_depth` (e, needs a calibrated dB/m).

## flux.csv (every plate sample)

| column | meaning |
|---|---|
| `rx_mono` | laptop receipt of the plate sample |
| `t_pi` | Pi time of the flux estimate (centre of the derivative window, lags the newest sample by half the window) |
| `plate_c` | plate thermocouple deg C |
| `air_c` | air thermocouple deg C used for the loss term |
| `q_kw_m2` | incident flux (absorbed / absorptivity) |
| `q_abs_kw_m2` | absorbed flux |
| `dTdt_k_s` | plate dT/dt K/s |
| `valid` | estimate valid |
| `reason` | why not valid |
| `dose_tdu` | running TDU of the valid samples so far |
| `dose_complete` | false once any interval was not integrated (dose is then a lower bound) |
| `uncounted_s` | seconds not integrated |

## health.csv (every 1 s)

`rx_mono`, `link_up`, `link_reason`, then per sensor `<sensor>_fresh`, `<sensor>_reason`, `<sensor>_age_s` (seconds since the last reading arrived), `<sensor>_pi_status` (latest Pi heartbeat status). Full list: `thermal_fresh`, `thermal_reason`, `thermal_age_s`, `thermal_pi_status`, `radar_fresh`, `radar_reason`, `radar_age_s`, `radar_pi_status`, `tc_plate_fresh`, `tc_plate_reason`, `tc_plate_age_s`, `tc_plate_pi_status`, `tc_housing_fresh`, `tc_housing_reason`, `tc_housing_age_s`, `tc_housing_pi_status`, `tc_air_fresh`, `tc_air_reason`, `tc_air_age_s`, `tc_air_pi_status`, `imu_fresh`, `imu_reason`, `imu_age_s`, `imu_pi_status`, `gnss_fresh`, `gnss_reason`, `gnss_age_s`, `gnss_pi_status`, `pi_fresh`, `pi_reason`, `pi_age_s`, `pi_pi_status`.

## pairs.csv

| column | meaning |
|---|---|
| `rx_mono` | when stored |
| `utc` | laptop UTC |
| `source` | `auto` (flux pulse while moving) or `manual` (operator mark) |
| `fuel` | fuel code |
| `predicted_m` | depth predicted before the crossing |
| `lo_m` | its 90 % low end |
| `hi_m` | its 90 % high end |
| `sigma_log` | its sigma_log |
| `measured_m` | measured thickness: time the plate flux stays above max(`thickness_q_kw_m2` = 5 kW/m2, `thickness_frac_of_peak` = 0.5 x pulse peak) x mean GNSS speed over that time (DESIGN 7, D7: width at half maximum), or a tape value |
| `loss_db` | radar loss at the prediction |
| `est_spread_burn_m`, `est_byram_m`, `est_radar_ceiling_m`, `est_flicker_extent_m`, `est_radar_loss_depth_m` | per-estimator predicted values (m) |
| `lat` | position at the prediction |
| `lon` | position at the prediction |
| `session` | Pi session id |
| `sim` | simulated |
| `thickness_duration_s` | pulse duration |
| `thickness_mean_speed_m_s` | mean speed in the pulse |
| `prediction_age_s` | age of the prediction when paired |
| `store` | JSONL store the pair went to (`pairs.jsonl` live real data, `pairs_sim.jsonl` simulated, `pairs_replay.jsonl` replays of real data) |
| `key` | dedup key `session|fuel|pulse|<pulse end, Pi s>` (or `...|prediction|<rx>` for a tape mark without a pulse); a second pair with the same key, an overlapping pulse or the same prediction is refused, and recalibration counts each key once |
| `t_start_pi`, `t_end_pi` | measured flux pulse window (Pi clock) |
| `est_flicker_extent_lo_m`, `est_flicker_extent_hi_m`, `est_flicker_extent_valid`, `est_flicker_extent_reason` | estimator d (experimental) at the prediction, recorded whether valid or not |
| `flicker_extent_agrees` | `measured_m` inside estimator d's 90 % interval (empty when d was invalid); counts per fuel are in the calibration status (`n_d_valid`, `n_d_agree`, `n_d_disagree`); never used for calibration |

Known bias (synthetic check, not a measurement): `measured_m` is the pulse width at half maximum (never below
5 kW/m2). It still includes part of the radiant zone in front of and behind the flame and the derivative smoothing,
so it is larger than the flaming depth: on the SIMULATED `crossing` sample (true depth 3.0 m) DESIGN 7 (D7) quotes
4.2 m at half maximum (11.6 m with the old fixed 5 kW/m2 threshold, `thickness_frac_of_peak: 0`). For a uniform
in-flame flux smoothed by a symmetric kernel the half-maximum width is never below the flaming depth, so the bias
stays high: calibration from automatic pairs widens intervals (conservative) but LOWERS dB/m, which is
ANTI-conservative for the dose (a longer radar-loss depth raises the depth lower end and lowers the in-flame flux);
dB/m is therefore taken as the 90th percentile of loss_db / measured_m, and the remaining bias is a known bias. Not a
fit of depth.

## State JSON

The State pushed on `WS /ws` (and `GET /api/state`) is documented in `apps/crossing/README.md`, section
STATE_SCHEMA. `verdicts.csv`, `depth.csv` and `health.csv` are flattened from it at every tick.
