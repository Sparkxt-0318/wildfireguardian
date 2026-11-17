# Crossing app (laptop)

A fire-service vehicle meets a flame front across a road. The roof unit (`hardware/vehicle-unit/`, Raspberry Pi)
streams raw sensor data over one WebSocket and makes no decisions. This app, on a macOS laptop, fuses the data and
shows one of **CLOSED / CROSS FAST / SPRAY THEN RE-CHECK / REOPENED**.

- **Advisory only.** Verdicts are for trained crews. Every limit (dose limit, speeds, thresholds, intake air
  limit, reopen hold) is a **PLACEHOLDER for the fire service to set**.
- **Fail closed.** Missing, stale, frozen, malformed or out-of-range input, link loss, or a verdict older than 5 s
  gives CLOSED. Smoke is not a target and cannot trigger anything (radar AND thermal rule).
- **Not verified on hardware.** Everything here has been run only on synthetic sessions (`wfgvu.synth` and the
  generator in `tests/test_pipeline.py`). Nothing has been run against the real roof unit, a real flame or a real
  crossing. Simulated data is labelled `sim: true` end to end and the UI watermarks it SIMULATED (banner badge,
  3D view watermark and a tag beside the verdict); a replay of recorded real data is tagged "REPLAY: not live".

Design contract: `hardware/vehicle-unit/DESIGN.md` (sections 5 to 11 are this app).

## Run

```
./run_crossing.sh                                      # live: roof unit hotspot ws://10.42.0.1:8770/stream
./run_crossing.sh --pi ws://10.42.0.1:8770/stream --vehicle fire_engine --fuel GR1 [--dem road_dem.npz]
./run_crossing.sh --replay <Pi record dir | research-log session dir> [--speed 1] [--loop]
./run_crossing.sh --sim-link ws://127.0.0.1:8765/v1/live/closures --region <id>   # step 9, opt-in
WFG_BROWSER=none ./run_crossing.sh ...                  # do not open a browser
```

or directly `python -m crossing ...` (same options, `--help`). The server listens on **127.0.0.1:8781** only.
Other options: `--config crossing.yaml`, `--baseline saved.json`, `--auto-baseline`, `--records DIR`, `--no-log`,
`--host`, `--port`. Install: `python -m pip install -r requirements.txt` (Python 3.12; the dev venv is `.venv`).

Tests: `cd apps/crossing && .venv/bin/python -m pytest`.

Replay controls (replay mode only; the web UI's Play / Pause / speed): `GET /api/replay` returns
`{mode: "replay", paused, speed, t, t_end, t_fed, ended, loop, pass, source, sim}` (`t` = recorded seconds since the
session start, frozen while paused; `t_end` is null until known: from `session.json` for a Pi record dir, after the
first pass for a research-log dir). `POST /api/replay` takes `{"action": "play"}`, `{"action": "pause"}` or
`{"action": "speed", "speed": x}` with 0.1 <= x <= 20 and returns the same status. In live or idle mode both answer
404 `{"mode": "live" | "idle"}`. **Pause fails closed**: it stops feeding recorded messages and marks the link down
("replay paused"), and the app re-decides at once, so the verdict is CLOSED (`LINK_DOWN`) while paused; it would in
any case expire 5 s after issue. Play restores the link state recorded in the session and continues from the paused
point; sensors then need fresh readings before anything but CLOSED can be decided. An ended replay (no `--loop`)
reports `paused` and `ended`; Play starts it again from the beginning.

Operator workflow (live): park with a clear view of the road and no flame in view, press **capture baseline**
(`POST /api/baseline`), choose vehicle and fuel, wait for the verdict. The radar baseline is dropped automatically
when the vehicle moves (GNSS speed > 0.3 m/s twice, or > 3 m from the capture point); recapture after stopping.
After a crossing the app pairs the predicted depth with the measured thickness automatically (flux pulse while
moving); `POST /api/mark_crossing` adds a pair by hand (optionally with a tape-measured `measured_m`).

## Modules (this area)

| file | role |
|---|---|
| `crossing/config.py` | defaults + `crossing.yaml` (unknown keys are errors) |
| `crossing/link.py` | WebSocket client with reconnect/backoff; `LinkState` freshness per DESIGN 5 |
| `crossing/pipeline.py` | fusion at 5 Hz, State, crossing detection, replay sources (`iter_source`, `run_virtual`, `play`) |
| `crossing/research_log.py` | step 10 research log (column dictionary: `research_log/README.md`) |
| `crossing/simlink.py` | step 9 client: only a flame-backed CLOSED (at the flame location) and the REOPENED of a location it closed leave the app |
| `crossing/server.py`, `crossing/__main__.py` | FastAPI server and CLI; `server.ReplayPlayer` = replay with play / pause / speed |
| `crossing.yaml` | the config the app loads by default |

Physics and decision modules (`flux`, `thermal`, `radar_flame`, `terrain`, `geometry`, `fuels`, `heat`, `depth`,
`calibrate`, `vehicles`, `decision`) are used unchanged.

## Freshness and fail-closed rules applied by the app

- A sensor is **fresh** (DESIGN 5, as built D2/D6) only if: the link is connected and something arrived within
  1.5 s; a reading arrived within 2.0 s (laptop clock at receipt); the Pi's latest heartbeat for it is within 2.0 s
  and says `ok`; the stream is not frozen on the Pi (a reading or heartbeat whose `seq` is not above the previous
  one, or whose Pi `t_mono` is not later, makes the sensor not fresh AT ONCE, until the stream advances again); and
  its payload changed within `freeze_s` (thermal 1.0 s and radar 1.0 s, identical raw values; imu 2.0 s; tc_* and
  gnss 5.0 s; `pi` not freeze-checked). Link loss marks everything not fresh at once.
- The pipeline additionally stops **using** a value older than `use_max_age_s` (thermal, radar, tc_*, imu 1.0 s;
  gnss 1.5 s; pi 1.6 s). On synthetic sessions a sensor that stops gives CLOSED after 0.8 s (thermal), 1.0 s (radar,
  tc_plate, tc_air, imu) and 1.4 s (gnss); a frozen thermal / radar payload (seq still advancing) after about
  1.0 s plus the 0.2 s tick (DESIGN 5: 0.80-1.25 s measured on synthetic replays), a frozen tc_* / imu / gnss
  payload only after its long window (2.0 s or 5.0 s).
- The crossing is evaluated on the vehicle's path: near edge = nearest flame base within `path_half_width_deg`
  (6 deg) of straight ahead; thermal flag and radar beam at that bearing.
- Radar UNKNOWN (no baseline, vehicle moving or speed unknown, stale, ...) -> flame UNKNOWN -> CLOSED.
- A tick that raises an exception gives CLOSED (`INTERNAL_ERROR`). The State served between ticks re-checks the
  verdict's 5 s expiry at send time.

## STATE_SCHEMA

The State is one JSON object (schema id `crossing.state/1`), pushed on `WS /ws` at 5 Hz and returned by
`GET /api/state`. No NaN or Infinity: missing or non-finite values are `null`. Units in key names
(`_m`, `_s`, `_c`, `_kw_m2`, `_deg`, `_db`, `_tdu`, `_kw_m`). Distances are along the GNSS course from the vehicle's
ground point unless named `slant`. Bearings are degrees, + right of the vehicle's path / camera boresight.

Top level:

| key | type | meaning |
|---|---|---|
| `schema` | str | `"crossing.state/1"` |
| `app_version` | str | crossing package version |
| `t_mono` | float | laptop monotonic time of the tick (s) |
| `state_age_s` | float | only in pushes between ticks: now - `t_mono` |
| `utc` | str | laptop UTC of the tick |
| `sim` | bool | **any simulated input: show the SIMULATED watermark** |
| `mode` | str | `live`, `replay`, `idle` |
| `source` | str | Pi URL or replay directory |
| `advisory` | str | the advisory banner text (show it) |
| `unit` | object | link info: `connected`, `unit_id`, `session_id`, `sim`, `parse_errors`, `last_parse_error`, `dropped_events`, `last_dropped_detail`, `connects`, `n_messages`, `pi_version`, `thermal_wire_hz` |
| `verdict` | object | see below |
| `health` | object | `link_up`, `link_reason`, `t`, `sensors.<name>` = `{fresh, reason, age_s, status_from_pi, drops, rate_hz_pi}` for thermal, radar, tc_plate, tc_housing, tc_air, imu, gnss, pi (the health lights) |
| `flame` | object | see below |
| `geometry` | object | see below |
| `depth` | object | see below |
| `intensity` | object | `valid`, `i_kw_m`, `lo`, `hi` (kW/m), `sources` (`byram_flame_height`, `spread_rate`), `reason`, `details` |
| `flux` | object | see below |
| `heat` | object | see below |
| `gnss` | object | `fix` (0/1/2), `lat`, `lon`, `alt_m`, `speed_m_s`, `speed_km_h`, `course_deg` (receiver, meaningless when stopped), `course_used_deg` (last course while moving; null if never moved), `hdop` (not metres), `sats`, `utc`, `moving`, `fresh` |
| `reopen` | object | `passed` (bool), `quiet_s`, `hold_s` (30, placeholder), `flame_ref` / `far_edge_ref` (`{pos: [east_m, north_m], dir, beyond_m, rx, kind}`, far edge also `t_pi` (Pi time the plate flux fell below the thickness threshold; pos is the GNSS position then), or null; local metres about the first fix) |
| `vehicle` | object | selected profile: `name`, `label`, `length_m`, `width_m`, `height_m`, `sensor_height_m`, `max_safe_speed_m_s`, `dose_limit_tdu`, `intake_air_limit_c`, `has_water`, `placeholder`, `placeholder_note` (**print beside every limit**) |
| `fuel` | object | `code`, `name`, `residence_s`, `residence_rel_sigma`, `consumed_load_kg_m2`, `heat_kj_kg`, `energy_kj_m2`, `fbfm40`, `source` |
| `calibration` | object | calibrate.FuelCalibration of the selected fuel: `n_pairs`, `calibrated`, `scale`, `status`, `db_per_m`, `trust_radar_ceiling`, ...; `store` (pairs file), `sim_store` (true = simulated pairs store) |
| `tc` | object | latest used `tc_plate`, `tc_housing`, `tc_air` readings `{temp_c, cj_c, fault}` or null |
| `pi` | object | latest used Pi health reading or null |
| `placeholders` | object | `note` and flags saying which values are placeholders |
| `simlink` | object | `{enabled: false}` or `{enabled, blocked, blocked_reason, url, region, mode, allow_replay, origin, connected, connections, token ("set" / "not set"; never the value), handshake_refused, queued, dropped, last_error, last_state, pending, closures_held, claims[], not_closed_in_routing[], reopen_refused_in_routing[], merge_radius_m, merge_radius_placeholder, last_sent, last_ack}` (`claim_token` masked as `***` in `last_sent` / `last_ack`); `claims[]` = `{loc_id, event, lat, lon, verdict_id, status (pending / in flight / acked / refused), attempts, error, code (last terminal refusal code, null once acked)}`, `not_closed_in_routing[]` = CLOSED claims refused and not acked since, also while re-asserted (the UI shows "ROAD NOT CLOSED IN ROUTING"), `reopen_refused_in_routing[]` = refused REOPENED claims (the UI shows "REOPEN NOT APPLIED IN ROUTING"); `handshake_refused` true shows "routing API REFUSED the connection" |
| `errors` | object | `count`, `last` (pipeline exceptions; any is a bug) |

`verdict` (the effective verdict: CLOSED once older than `verdict_ttl_s` = 5 s):

| key | meaning |
|---|---|
| `state` | `CLOSED`, `CROSS FAST`, `SPRAY THEN RE-CHECK`, `REOPENED` |
| `decided_state` | the state decided at the last tick (differs from `state` only when it expired) |
| `reasons` | reason codes (`CODE` or `CODE:detail`), e.g. `LINK_DOWN`, `SENSOR_NOT_FRESH:radar`, `RADAR_UNKNOWN`, `FLAME_NOT_CONFIRMED`, `NO_FAR_ECHO`, `DEPTH_INVALID`, `DOSE_OVER_LIMIT`, `INTAKE_AIR_OVER_LIMIT`, `VERDICT_EXPIRED`, `DOSE_WITHIN_LIMIT`, `REOPEN_CONDITIONS_HELD`. Display only: the UI lists codes it does not know as sent (marked "code not known to this UI") and never derives a verdict from a reason; `REOPEN_..._NOT_IN_VIEW`, `NEAR_EDGE_..._NOT_OBSERVED` and `FLAME_..._TOO_SHORT` style codes also show a crew instruction (e.g. face the crossed road) |
| `verdict_id`, `issued_mono`, `expires_mono`, `age_s` | identity and timing (laptop clock) |
| `min_speed_m_s`, `min_speed_km_h` | CROSS FAST: smallest speed meeting the dose limit; SPRAY: max safe speed |
| `time_in_flame_s` | (depth upper end used for decision, `depth.hi_decision_m` + vehicle length) / speed |
| `dose_tdu`, `dose_limit_tdu` | closed-form dose at that speed vs the (PLACEHOLDER) limit |
| `dose_fds_ref_tdu` | FDS C064 reference dose: reference only, never decides |
| `details` | decision details (q_in_flame_kw_m2, depth_lo/hi, intensity_hi, crossing_reasons, reopen_reasons, `stamp` for REOPENED, ...) |
| `placeholder`, `placeholder_note`, `advisory` | always true / the texts to show |

`flame`:

| key | meaning |
|---|---|
| `status`, `reason` | fused `FLAME` / `NO_FLAME` / `UNKNOWN` (FLAME only if radar effect AND thermal flame at the path bearing) |
| `thermal` | `valid`, `reason`, `flame_pixels` (>= `t_flame_c`), `hot_pixels` (>= 60 C), `t_max_c`, `flame_at_bearing`, `pixels_at_bearing`, `bearing_deg` (path bearing in the camera), `t_flame_c`, `shutter`, `age_s`, `thumb` |
| `thermal.thumb` | null or `{w: 64, h: 48, enc: "u8-b64", pool: "max", t_min_c, t_max_c, pix}`: base64 of w*h uint8, row-major from the top-left, value v -> temperature `t_min_c + v/255*(t_max_c - t_min_c)` (4x4 max-pooled) |
| `radar` | `status` (`FLAME_EFFECT` / `NO_EFFECT` / `UNKNOWN`), `reason`, `loss_db`, `loss_z`, `flicker_phase_rad`, `flicker_phase_z`, `flicker_amp_db`, `flicker_amp_z`, `far_echo_m` (SLANT range of the first solid echo beyond the near edge), `source` (`heatmap`/`profile`), `noise_db`, `n_frames`, `window_span_s`, `effect_ranges_m`, `bearing_deg`, `near_edge_slant_m`, `moving`, `baseline` (`present`, `reason`, `n_frames`, `utc`, `forced`, ...), `latest_frame`, `per_bin` |
| `radar.per_bin` | `{}` or `{pool_factor, range_m[], window_max_db[], window_mean_db[], baseline_db[], loss_db[], loss_z[], flicker_amp_db[], flicker_amp_z[], flicker_phase_rad[], flicker_phase_z[], present_frac[], target[]}`: at most 128 entries, max-pooled by `pool_factor` bins (`range_m` = range of the first bin of each group; `target` = any target bin in the group). Entries may be null |

`geometry`:

| key | meaning |
|---|---|
| `valid`, `reason` | a near edge exists on the vehicle's path |
| `near_edge_m`, `near_edge_lo_m`, `near_edge_hi_m` | distance to the flame base and its interval (hi may be null = unbounded, e.g. occluded) |
| `bearing_deg`, `occluded`, `ground_dz_m`, `n_columns` | column used, base hidden behind a crest, ground height there, flame columns used |
| `flame_height_m`, `flame_height_lo_m`, `flame_height_hi_m` | flame height above the ground at the near edge |
| `far_echo_m`, `far_echo_slant_m` | first solid radar echo beyond the flame (horizontal, slant) |
| `slope_source` | `dem` or `imu` (**show it**) |
| `profile` | road profile `{source, valid, reason, s_m[], dz_m[]}`: along-course distance and ground height relative to the vehicle's ground point (for the 3D road) |
| `camera` | `height_m`, `mount_pitch_deg`, `mount_roll_deg`, `mount_yaw_deg`, `hfov_deg`, `vfov_deg` |
| `imu` | `roll_deg` (+ right side down), `pitch_deg` (+ nose up) |

`depth` (`depth.DepthResult`): `valid`, `depth_m`, `lo_m`, `hi_m` (90 % interval; draw the value solid and the
interval translucent), `level`, `used[]`, `calibrated`, `n_pairs`, `scale`, `sigma_log`, `flags[]`, `ceiling_m`,
`method`, `reason`, `estimators[]` = `{name, value_m, lo_m, hi_m, sigma_log, valid, reason, kind, details}` for
`spread_burn`, `byram`, `radar_ceiling` (`kind: "ceiling"`), `flicker_extent` (`kind: "experimental"`),
`radar_loss_depth`. `hi_decision_m` = depth upper end used for decision (the dose and time in flame use it, not
`hi_m`; DEPTH-HI rule, depth.py: >= the largest upper end of the valid non-experimental estimators `spread_burn`,
`byram`, `radar_loss_depth`; `flicker_extent` never raises or lowers it; the radar ceiling lowers it only when
calibration trusts it; null when the depth is invalid), `hi_decision_from` (estimator name, `combined`, or
`radar_ceiling (trusted cap)`), `hi_decision_rule`, `disagree_ratio` (largest / smallest central value of those
estimators; a flag starting `ESTIMATORS_DISAGREE` is in `flags[]` above `depth.disagree_factor`, default 3; shown,
does not close by itself). The UI shows `hi_decision_m` as "Depth upper end used for decision". The UI's estimator table says "used" only for an estimator named in `used[]` of a valid
combined depth; a valid estimator left out of the combination reads "valid, not used" (with "experimental, off by
default" or "ceiling; not trusted by calibration" for those kinds). With `used[]` missing or the depth invalid no
row says "used" (fail closed).

`flux`: `q_kw_m2` (incident plate flux, null if not valid), `valid`, `reason`, `dTdt_k_s`, `plate_c`, `air_c`,
`tc_plate_c`, `tc_air_c`, `tc_housing_c`, `dose_tdu` (running TDU since start), `dose_complete` (false = lower
bound), `uncounted_s`, `loss_model`, `crossing` (`active`, `t_start_pi`, `below_since_pi`, `last` = result of the
last crossing pairing `{ok, source, reason | measured_m, predicted_m, lo_m, hi_m, store, sim, ...}`, `n_auto`,
`n_manual`).

`heat`: `label` = "FDS C064 reference, not a measurement", `chi`, `valid`, `reason`, `depth_m`, `intensity_kw_m`
(central values), `curve[]` = `{d_m, closed_form_kw_m2, fds_ref_kw_m2, fds_ref_extrapolated}` at d = 0, 1, 2, 5, 10,
15, 20, 30, 40, 50 m from the flame, `in_flame_closed_form_kw_m2`, `in_flame_fds_ref_kw_m2`, `at_vehicle`
(closed form vs FDS reference at the near-edge distance), `note`.

Minimal State (before the first tick or after an internal error) carries the common keys plus `verdict` and
`health` only; the UI must treat any missing object as "no data".

## Research log

Every session writes `records/<session>/` (CSV, npz chunks, wire log, Parquet copies). Column dictionary:
`research_log/README.md`. `python -m crossing --replay records/<session>` replays it with the original receipt
timing and link drops.

## Step 9 sim-link

With `--sim-link URL --region R` the app sends `{"event": "CLOSED" | "REOPENED", "region", "lat", "lon", "utc",
"unit_id", "session_id", "verdict_id"}` to the routing API (rules as rebuilt after review findings R9-01, R9-08,
R9-09; `crossing/simlink.py` docstring has the full list):

- CLOSED is the default for every non-go situation, so a CLOSED verdict alone never leaves the app. Only a
  flame-backed CLOSED does: the raw verdict of the tick is CLOSED and not expired with `DOSE_OVER_LIMIT` or
  `NO_WATER_FOR_SPRAY`, the fused flame is FLAME with radar FLAME_EFFECT, held for the minimum flame evidence. It is
  sent once per location (locations within 50 m merge; PLACEHOLDER), at the flame location the pipeline recorded in
  that tick (vehicle GNSS position + near-edge distance along the GNSS course), never at the vehicle position. No
  flame location (e.g. no GNSS course yet: stationary since start): nothing is sent. Startup, faults, link loss,
  expiry, smoke, CROSS FAST, SPRAY THEN RE-CHECK and driving on send nothing.
- REOPENED is sent only for a location this link closed, at that stored location, when the reopen view confirmed
  the crossing within 50 m of it; the location is then forgotten.
- `--sim-link` with `--replay` is refused (exit 2) unless `--sim-link-allow-replay`; simulated data (`sim: true`)
  disables the link at run time. Allowed replay/sim messages carry `"origin": "replay" | "sim"`, which the routing
  API as built does not accept, so it refuses them (nothing applied).
- Handshake: the client offers the subprotocol `wfg-live.v1` and, with a token, `wfg-token.<token>`. When the API
  has `WFG_API_LIVE_TOKEN` set, give the laptop the same token in the environment, never on the command line:
  `WFG_SIM_LINK_TOKEN=<token> python -m crossing --sim-link URL --region R`, or
  `--sim-link-token-env VAR` to read another variable (exit 2 if that variable is unset or the token has characters
  other than letters, digits, `-`, `_`). The token is never logged (the websockets handshake logger is pinned above
  DEBUG), never in the State (`simlink.token` is only "set" / "not set") and never in the research log
  (`session.json` records "set (value not recorded)"). A refused handshake (HTTP 403: token missing or wrong, Host
  or Origin not allowed) sends nothing, is retried with the reconnect backoff and shows "routing API REFUSED the
  connection".
- The client keeps one claim per location and sends stop-and-wait (one frame, then its ack). Only `ok: true` acks a
  claim. Every CLOSED claim is re-sent after each (re)connect and every 60 s (PLACEHOLDER) because the API keeps
  closures in memory only. No ack within 5 s, a drop before the ack, `INTERNAL_ERROR`, `DATA_UNAVAILABLE`,
  `RATE_LIMITED` or an unknown code: retried with backoff. `VALIDATION_ERROR`, `UNKNOWN_EVENT`, `SNAP_TOO_FAR`,
  `UNKNOWN_REGION`, `NOT_CLOSED`, `CLOSED_BY_OTHER_UNIT`, `REOPEN_UNAUTHORIZED`, `REOPEN_TOO_FAR`,
  `REOPEN_NOT_ON_CLOSED_ROAD`: no backoff retry, logged (WARNING). A refused CLOSED is never given up: it shows "ROAD
  NOT CLOSED IN ROUTING" until an `ok: true` ack and is still re-asserted after reconnects and every 60 s. A refused
  REOPENED is not re-sent (the API leaves the road closed, which is the safe side) and shows "REOPEN NOT APPLIED IN
  ROUTING". A REOPENED replaces an unacked CLOSED of its location (only the latest state is ever re-sent); when the API
  returned a `claim_token` in the CLOSED ack, the REOPENED carries it back with `closes_verdict_id`. If that ack was
  lost (connection dropped after the API applied the CLOSED), the REOPENED goes without a token, the API answers
  `REOPEN_UNAUTHORIZED` and the road stays closed in routing until an operator clears it or the API restarts.
  `tests/test_simlink.py::test_every_api_live_code_is_classified` scans `api/live.py` and the live part of
  `api/app.py` and fails if the API gains an ack code this list does not classify.
- End-to-end check (`tests/test_simlink.py::test_end_to_end_against_the_routing_api`, skipped where loopback is
  blocked or the recorded graph is missing): starts `python -m api` with the repository `.venv` interpreter (or
  `WFG_API_TEST_PYTHON`) on a free 127.0.0.1 port with `WFG_API_LIVE_CLOSURES=1` and a token. The API needs a
  WebSocket implementation for uvicorn: `api/requirements.txt` pins `websockets==13.1`; a `.venv` built before that
  pin has none, and the test then puts this app's websockets 13.1 on the API process's `PYTHONPATH` (nothing is
  installed). It checks: no token -> handshake refused, nothing applied; CLOSED applied with the token; the REOPENED
  of the same claim lifts it; CROSS FAST / SPRAY never sent; a REOPENED without the claim token gets
  `REOPEN_UNAUTHORIZED` and the road stays closed; the token is in neither the State, the client logs nor the API log.

## Not verified / open issues

- Nothing in this app has run against the real roof unit, the TC001, the IWR6843AOP, the thermocouples, the BNO055
  or a GNSS receiver. Timing, Wi-Fi jitter and real frame rates are untested.
- The plate flux estimator runs with a 2.2 s derivative window (config `flux_window_s`) instead of DESIGN's 1.0 s.
  The original reason (FluxEstimator rejecting about half of jittered 10 Hz samples at 1.0 s) is fixed in
  `flux.py`; 2.2 s is kept because at 1.0 s the flux noise of a quiet plate keeps crossing the 1.0 kW/m2 REOPENED
  threshold and resets the 30 s hold (seen on SIMULATED sessions only). The measured crossing thickness uses a
  centred 1.0 s window instead.
- Measured thickness from the flux pulse is biased high (radiant zone and smoothing): see `research_log/README.md`.
- The first solid echo on `wfgvu.synth` sessions sits just beyond the near edge (inside the flame zone), so the
  radar ceiling there is far below the true depth; it is reported but not used unless calibration trusts it.
- Step 9 sim-link: the closed location is only as good as the GNSS course and the near-edge range (flame_ref), and
  the routing API's nearest-edge snapping can still pick an adjacent road. A unit that never had a GNSS course
  (stationary since start, IMU heading not trusted) records no flame location and so reports no closure at all.
  The 50 m merge/match radius, the 60 s re-assert period and the 5 s ack timeout are PLACEHOLDERS. Tested against
  an in-process fake socket, the API's parser, and (`tests/test_simlink.py::test_end_to_end_against_the_routing_api`)
  the real API app served by uvicorn on 127.0.0.1 with a token, on a recorded graph; never over a real network or
  radio link.
