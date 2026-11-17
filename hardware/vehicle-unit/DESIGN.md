# Vehicle unit and crossing app: design contract

Status: design contract written 2026-11-17, before any code. Every module in `hardware/vehicle-unit/` and
`apps/crossing/` follows this file. If code and this file disagree, fix one of them in the same change.

Verdicts are advisory for trained crews. Every limit in this system is a placeholder for a fire service to set.
Allowed claim, and the only one: "vehicle-mountable unit, tested on a car and on lab flames, ready for a
fire-service trial". Until those tests have run and are reported in `apps/crossing/RESULTS.md`, not even that.

## 0. Ground rules

- Nothing outside `hardware/vehicle-unit/`, `apps/crossing/` and the step 9 live input in `api/` (plus its test
  `tests/api/test_live_closures.py`) is changed.
- Python: Pi code must run on Python 3.11 (Raspberry Pi OS bookworm) and parse on 3.12 (CI `tools/verify_release.py`
  ast-parses everything under `hardware/`). Laptop code targets Python 3.12. The dev venv is
  `apps/crossing/.venv` (numpy 1.26.4, PyYAML, websockets 13.1, fastapi, uvicorn, pytest, httpx, pyarrow,
  matplotlib, pyserial, pyproj 3.7.0). No scipy, no pandas: use numpy.
- Never name a folder `logs` or `devices` anywhere under `hardware/` (CI fails). Runtime data goes to `records/`.
- Units: SI plus kW/m2 for flux, degrees C for temperatures shown to people, K inside physics code.
  TDU = (kW/m2)^(4/3) s. Distances in m, speeds in m/s (UI also shows km/h).
- Monotonic time decides freshness. The laptop uses its own `time.monotonic()` at receipt; it never trusts
  the Pi's clock or the Pi's own "ok" flag for freshness.
- Fail closed. Missing, stale, frozen, unparseable or out-of-range input makes the verdict CLOSED.
- Simulated data is always labelled `"sim": true` end to end and watermarked "SIMULATED" in the UI.
- Reuse, do not fork, repo physics where it is importable without side effects:
  - closed-form law: load `research/kcf-heat/kcf_heat/law.py` by file path (stdlib only). Do not copy it.
  - TDU: `exposure.py` cannot be imported cheaply (it pulls closure.py and the repo root). Reimplement the one
    line `sum(q**(4/3)*dt for q in qs if q > q0)` in `crossing/flux.py::tdu` and say so in a comment.
  - Byram flame length L = 0.0775 I^0.46 (`experimental/flame-front-radiation/src/wfg_flamefront/intensity.py`).
  - FBFM40 residence times and loads: copy the table values from `forecast/wildfire/heat.py`
    (`_FBFM40_PARAMETERS`, Anderson t_r[min] = 384/sigma[ft^-1]) into `crossing/fuels.py` with a provenance comment.
  - Conformal: the requested `research/kcf-margin` does not exist. Use the conformal risk control rule of
    `research/harness-2026-11/S-D9/sd9bench/crc.py` (n/(n+1) R + B/(n+1) <= alpha, B = 1, crossing = exchangeable
    unit, infeasible when alpha < 1/(n+1)); see section 7.

## 1. Directory layout

```
hardware/vehicle-unit/                 # sensor head (Raspberry Pi 4/5)
  DESIGN.md  README.md  requirements-pi.txt  requirements-dev.txt  pytest.ini  run_unit.sh  .gitignore
  config/unit.yaml                     # ports, rates, SPI/I2C buses, camera index, mount offsets
  wfgvu/__init__.py                    # __version__ = "0.1.0"
  wfgvu/protocol.py                    # message envelope + encoders/decoders (shared with laptop)
  wfgvu/drivers/base.py                # Driver base: live/sim, heartbeat, reading callback
  wfgvu/drivers/thermal_tc001.py       # Topdon TC001 via OpenCV UVC (cv2 optional import)
  wfgvu/drivers/radar_iwr6843.py       # IWR6843AOP stock mmw demo: CLI config, UART frames
  wfgvu/drivers/tlv.py                 # pure TLV frame parser (no serial), unit-tested
  wfgvu/drivers/max31855.py            # 3 x MAX31855 on SPI (spidev optional import)
  wfgvu/drivers/bno055.py              # BNO055 on I2C (smbus2 optional import)
  wfgvu/drivers/gnss_nmea.py           # USB GNSS, NMEA GGA/RMC/VTG parser (pure + serial)
  wfgvu/drivers/pi_health.py           # CPU temp, throttling/under-voltage, input voltage if readable
  wfgvu/recorder.py                    # raw logging to records/<session_id>/
  wfgvu/replay.py                      # reads a recorded session for sim mode
  wfgvu/synth.py                       # synthetic scenario generator (writes the recorded-session format)
  wfgvu/server.py                      # asyncio WebSocket server, one socket, broadcast
  wfgvu/__main__.py                    # python -m wfgvu [--sim SESSION_DIR] [--config ...]
  system/hotspot.sh  system/wfgvu.service  system/README.md
  samples/<scenario>/                  # small synthetic sessions (committed, < 5 MB total)
  docs/WIRING.md docs/wiring.svg docs/HOUSING.md docs/housing.svg docs/housing.scad docs/BOM.md
  tests/
apps/crossing/                          # laptop app (macOS)
  README.md  RESULTS.md  LIMITS.md  requirements.txt  pytest.ini  run_crossing.sh  .gitignore
  crossing/__init__.py
  crossing/config.py                   # defaults + YAML loading (crossing.yaml)
  crossing/link.py                     # WS client to the Pi; per-sensor freshness; frozen-data detection
  crossing/flux.py                     # step 2 thin-skin calorimeter + TDU
  crossing/thermal.py                  # decode frames, hot-pixel masks, flame columns
  crossing/radar_flame.py              # step 3 radar effect + AND with thermal
  crossing/terrain.py                  # DEM npz lookup, road profile along heading
  crossing/geometry.py                 # step 4 near edge, flame height
  crossing/fuels.py                    # FBFM40 table + custom fuels (residence time, consumed load, heat content)
  crossing/heat.py                     # closed-form law adaptor + FDS C064 reference values
  crossing/depth.py                    # step 5 four estimators + combination
  crossing/calibrate.py                # predicted vs measured pairs, conformal recalibration, dB/m per fuel
  crossing/vehicles.py  crossing/vehicles.yaml
  crossing/decision.py                 # step 6 verdict state machine
  crossing/pipeline.py                 # fuses link data -> state -> verdict (5 Hz)
  crossing/research_log.py             # step 10
  crossing/simlink.py                  # step 9 client (flag-guarded)
  crossing/server.py  crossing/__main__.py   # FastAPI: browser WS, static web, live and replay
  web/index.html web/js/*.js web/css/app.css web/vendor/three/ (r180 copied from demos/showcase/vendor)
  virtual_fds/                          # step 8
  field_tests/                          # tests A-F: record + analyse scripts, protocols
  research_log/README.md               # column dictionary for step 10 output
  tests/
```

`.gitignore` in each new folder ignores `records/`, `.venv/`, `__pycache__/`, `out/`.

As built (integration, 2026-11-17): `apps/crossing/RESULTS.md` (simulated results, every test A-F marked NOT RUN)
and `LIMITS.md` (one-page placeholder limits sheet) exist. No field test (A-F) has run, so the allowed claim above
may not be made yet. The placeholder
limits live in `crossing/vehicles.yaml` and `crossing.yaml` (both say so in their headers). Extra files beyond the
layout: `docs/MOUNTING_AND_POWER.md`, `docs/make_drawings.py` (generates the SVGs) and `docs/test_docs.py` (collected
by the vehicle-unit `pytest.ini`, `testpaths = tests docs`); `field_tests/` holds `sheets/`, `protocols/`,
`example_outputs/` (SIMULATED) and shared modules; `virtual_fds/outputs/`; `apps/crossing/tests/test_end_to_end.py`
runs the Pi sim server and the crossing app over loopback sockets in one process (skips where binding is not
permitted). `virtual_fds/REPORT.md` holds the step 8 tables (SIMULATED).
Step 8 re-run (2026-11-17, SIMULATED, current radar noise floor / noise-rise gate / DEPTH-HI code): the virtual
radar's main case now reads bins, spacing, IF-limited range and wavelength from `config/iwr6843aop_vu.cfg` (128 x
0.468 m to 54 m; clutter per bin scaled by bin length, +9.8 dB); the short (22.5 m), long-fine and virtual 60 m x
0.0488 m runs are labelled side cases. Main case: radar UNKNOWN in 9/9 windows (7 by the noise-rise gate: refractive
phase flicker of the strong clutter in front of the flame raises the temporal residual 10.9-23.7 dB; 2 with no solid
echo beyond), so fusion UNKNOWN 9/9; combined depth (a+b) [lo, hi_decision_m] covers 11.1 m in 9/9.

## 2. Wire protocol (Pi -> laptop), `wfgvu/protocol.py`

One WebSocket, `ws://<pi>:8770/stream` (Pi hotspot address default 10.42.0.1). Text frames, one JSON object each.
`PROTOCOL_VERSION = 1`. Every message has:

```
{"v":1, "type": "...", "unit_id":"VU-01", "session_id":"VU-01-20261117T101500Z", "sim": false,
 "t_mono": 12345.678,          # Pi time.monotonic() at creation, seconds
 "t_utc": "2026-11-17T10:15:00.123Z" | null}   # Pi wall clock (NOT disciplined, see below)
```

As built (2026-11-17, VU-R4): the Pi clock is not disciplined: no RTC battery, nothing sets it from GNSS, usually no
network; it is restored at boot from the last saved time. `t_utc` and the wall-clock part of `session_id` can repeat
or go backwards across boots; `t_mono` (within a boot) and `session_id` are the ordering keys. The recorder never
reuses a session directory: if `records/<id>` exists it uses `<id>-2`, `<id>-3` ... and `__main__` puts that final
id into the protocol context before anything is sent; session.json records `boot_id` and `clock` (source, sync state
"unsynchronized" unless `timedatectl` confirms NTP sync).

Types:
- `hello` (first message on connect): `sensors: [names]`, `version`, `config_digest`.
- `heartbeat`: `sensor`, `status` in {"ok","no_device","error","stale","sim_ended"}, `detail` (str),
  `last_reading_seq` (int or null), `rate_hz` (measured), `seq` (heartbeat counter). Sent every 0.5 s per sensor.
  The Pi server also sends `sensor: "unit"` heartbeats (server alive).
- `reading`: `sensor`, `seq` (per-sensor, starts 0, +1 per reading, no gaps unless dropped; drops are counted),
  `data` (per sensor below). Exception: thermal goes to clients decimated (default 4 Hz) while the recorder keeps
  every frame, so on the wire the thermal `seq` jumps by the decimation step; that is not loss (decimation is
schedule-based: the next slot advances by exactly 1/thermal_wire_hz and a frame up to 20 % of a period early fills
it, so jittered 4 Hz input passes whole and the long-run wire rate is thermal_wire_hz). Real per-client
  losses arrive as `event` `kind="dropped"`. `hello` also carries `thermal_wire_hz` (extra keys are allowed) and
  `mount` (as built): live = `config/unit.yaml` `mount` (camera height/pitch/roll/yaw, + up; default camera pitch
  -18.0, i.e. 18 deg down); sim = the replayed session's own mount (session.json `config.mount`, else synth
  `truth.camera`), never the playing unit's config; absent when the session has none.
- `event`: `kind` (e.g. "sensor_reconnected", "record_rotated", "radar_config_sent", "dropped"), `detail`.

Sensor names (fixed): `thermal`, `radar`, `tc_plate`, `tc_housing`, `tc_air`, `imu`, `gnss`, `pi`.

`data` by sensor:
- `thermal` (default 4 Hz to the laptop, full rate recorded on the Pi):
  `{"w":256,"h":192,"enc":"u16-zlib-b64","raw_per_k":64.0,"pix":"<b64>","gain":"low"|"high","shutter":bool}`
  raw/64 = temperature in K (TC001 lower-half frame). Helpers: `encode_thermal(temps_k: np.ndarray) -> dict`,
  `decode_thermal(data) -> np.ndarray float32 [h,w] K`.
- `radar` (one per radar frame, ~10 Hz):
  `{"frame":int, "range_res_m":float, "n_bins":int,
    "range_profile_db": [floats] | null,               # TLV 2 / n_virt in dB = mean 20log10|x| (section 3)
    "az_heatmap": {"n_ant":int,"enc":"i16-zlib-b64","iq":"<b64>"} | null,   # TLV 4, complex [n_bins, n_ant]
    "points": [[x,y,z,doppler_m_s,snr_db],...] | null, # TLV 1 + TLV 7
    "tlv_types":[...], "frame_ok": bool}`
  Helpers: `encode_iq(c: np.ndarray complex64 [bins, ant]) -> dict`, `decode_iq(d) -> np.ndarray`.
- `tc_plate`, `tc_housing`, `tc_air` (10 Hz each): `{"temp_c": float|null, "cj_c": float|null,
  "fault": null|"open"|"short_gnd"|"short_vcc"|"spi"}`.
- `imu` (20 Hz): `{"roll_deg","pitch_deg","heading_deg","grav":[gx,gy,gz] m/s2,"calib":{"sys","gyro","accel","mag"}}`.
  Convention: pitch positive = nose up; roll positive = right side down; heading degrees clockwise from
  magnetic north (not used for slope lookup, GNSS course is).
- `gnss` (1-10 Hz): `{"fix": 0|1|2, "lat","lon","alt_m","speed_m_s","course_deg","hdop","sats","utc"}`;
  nulls when no fix. `hdop` is not an error in metres.
- `pi` (1 Hz): `{"cpu_c","throttled_hex","under_voltage_now":bool,"under_voltage_ever":bool,"input_v":float|null,
  "disk_free_mb","rec_bytes"}`.

`protocol.make(type, **fields)`, `protocol.parse(text) -> dict` (raises `ProtocolError` on any malformed message;
validates `v`, `type`, sensor names and required keys). The laptop drops (and counts) messages that fail `parse`.
`make` needs `unit_id`/`session_id` (or use `protocol.Context(unit_id, session_id, sim).make(...)`), defaults
`t_mono`/`t_utc` to now, and turns NaN/inf into null; `parse` rejects NaN/Infinity tokens. `protocol.dumps(msg)`
gives the exact wire text. Wire layout of `az_heatmap.iq`: int16 LE (real, imag) pairs, row-major [bin, ant].

## 3. Pi drivers (`wfgvu/drivers/`)

`Driver(name, cfg, emit, sim_source=None, *, ctx=None)` (`ctx` = `protocol.Context` for the envelope;
`emit(msg)` gets complete messages); `start()`, `stop()` (sends a final `no_device` heartbeat "driver stopped"),
a reader and a heartbeat thread per driver. Live mode opens the device;
on failure it reports `no_device` heartbeats and retries every 2 s. Sim mode reads `sim_source` (a
`replay.SensorStream`) and emits its readings at recorded timing (`speed` factor). The driver keeps
`last_seq`, `last_ok_mono`, measured rate; `heartbeat()` returns the heartbeat dict. `status` is `stale` when no
good reading for `stale_s` (thermal 1.0, radar 1.0, tc_* 1.0, imu 0.5, gnss 2.0, pi 3.0); `error` while the
latest reading is flagged bad (thermocouple fault, inconsistent radar frame, Pi under-voltage); heartbeats also go
out immediately on a status change. In sim mode recorded `no_device`/`error` heartbeats are adopted, a stream that
ends early goes `stale`, and `sim_ended` follows once the whole session's recorded time has passed.
No decisions on the Pi: drivers decode and timestamp, nothing else.
As built (VU-R2/R3/R6, 2026-11-17, not verified on hardware; limits are placeholders): BNO055 `read` checks
OPR_MODE before and after the data read and SYS_STATUS, raising (so the base loop re-opens the chip; `open` selects
page 0 and rewrites UNIT_SEL, axis map and NDOF) after a chip reset; `assess` rejects |g| outside 8.8..10.8 m/s2 and
an all-zero reading, and reports calibration below 3 in the heartbeat detail (not bad by itself). The radar raises
after `frame_watchdog_s` (default max(3 frame periods, 1 s) + 2 s) with no COMPLETE decoded frame (silent or
garbage-only UART; event `radar_watchdog`), so it is closed (sensorStop) and re-configured. Live heartbeats append
`Driver.parser_stats()` to the detail (no new field): GNSS `nmea_bad=N`, radar FrameSync frames / garbage_bytes /
bad_frames / truncated / last_error. GNSS raw lines (all of them, bad checksums and GSA/GSV included) go to
`records/<session>/gnss_nmea.bin`, each prefixed with the Pi monotonic time; MAX31855 readings also carry `bits`
(raw word, hex) and `fault_bit` (fault stays "spi" for D16 without a cause bit).

Radar specifics (`radar_iwr6843.py`, `tlv.py`): stock out-of-box demo. Send the CLI config file
(`config/iwr6843aop_vu.cfg`, committed; enables range profile, static azimuth heatmap, point cloud with side info)
on the CLI UART (115200), read data UART (921600). Magic word `02 01 04 03 06 05 08 07`. Header 40 bytes
(version, totalPacketLen, platform, frameNumber, timeCpuCycles, numDetectedObj, numTLVs, subFrameNumber).
TLV 1 points (float32 x,y,z,v), TLV 2 range profile (uint16 per bin: sum over virtual antennas of log2|x|, Q9;
divided by n_virt = mean 20log10|x|: dB = 20*log10(2) * value/512/n_virt, n_virt = TX x RX from the CLI config;
no config -> `range_profile_db` null; scaling per TI's UART output format page, UNVERIFIED on hardware; the laptop's
profile-only path gives UNKNOWN until an EVM capture confirms it, 6.3), TLV 4 azimuth static heatmap (int16 imag, real pairs per bin per virtual antenna),
TLV 7 side info (int16 snr, noise in 0.1 dB). `tlv.parse_frame(buf: bytes) -> dict` raises `TLVError` on bad
length/magic; `tlv.FrameSync` finds frames in a byte stream. The raw UART byte stream is also recorded.
As built (2026-11-17, UNTESTED on the EVM): the default `config/iwr6843aop_vu.cfg` is long range: 128 bins x
0.468 m (slope 25 MHz/us, 128 samples at 10 Msps, 320 MHz sampled bandwidth), IF-limited max range 54 m, 10 Hz,
3 TX x 4 RX, same TLVs; 6456 B/frame without points = 70 % of the 921600-baud data UART. The previous 512 x 0.049 m,
22.5 m config (2.8x over the UART at 10 Hz, and too short to see behind an ~11 m flame at 10-30 m) is kept as
`config/iwr6843aop_vu_short.cfg`; `config/iwr6843aop_vu_long_fine.cfg` is 512 x 0.117 m to 54 m at 2.86 Hz.
`RadarProfile.uart_load(baud)` is reported in the `radar_config_sent` event. Shutdown (as built): `UnitServer.stop`
is bounded by `server.stop_timeout_s` (1.8 s) with clients connected, including one that stopped reading (its
transport is aborted after 0.25 s; readers get close code 1001 "unit stopping"); drivers join with 0.4 s timeouts.
The recorder then gets its own budget, max(time left, `server.recorder_close_s` = 5 s) (systemd TimeoutStopSec=15);
if it still cannot finish, session.json says `closed_cleanly: false`, `writer_alive`, `queue_left` (VU-R8).

Thermal: OpenCV `VideoCapture(index)`, `CAP_PROP_CONVERT_RGB = 0`, frame 256x384 YUYV; lower half (rows 192-383)
holds 16-bit raw temperature: `k = (hi<<8 | lo) / 64`. Documented in the driver.

## 4. Recorded-session format (Pi recorder, sim replay, synth generator)

```
records/<session_id>/session.json      # unit_id, session_id, started_utc, sim, config, scenario/truth if synth
records/<session_id>/<sensor>.jsonl.gz # one protocol `reading` or `heartbeat` message per line, exactly as sent
records/<session_id>/<sensor>.<n>.jsonl.gz  # rotated continuation parts, n = 1, 2, ...
records/<session_id>/events.jsonl.gz   # events; unit.jsonl.gz: server ("unit") heartbeats (not sensor streams)
records/<session_id>/radar_uart.bin    # raw data-UART bytes (live only)
records/<session_id>/thermal_full.npz-chunks/ (optional, live only, full-rate frames)
```

Replay = read the `.jsonl.gz` files, merge by `t_mono`, re-emit with original spacing. `replay.load(dir) ->
Session` with `.streams[sensor]` iterators (`SensorStream`, `t_mono` order). Sim playback re-emits recorded `data`
with fresh envelopes (`sim: true`, the driver's own `seq`). `recorder.write_session(dir, info, messages)` writes
a complete session synchronously (for synth); session.json then also has `t_mono_first`/`t_mono_last`.
As built (2026-11-17, VU-R1/R4/R5): stream files are opened "xb", never appended (an existing file is left alone,
`record_error`, next free part; part numbers can have gaps). Any write/flush/rotation error closes that stream
(counts kept), drops the message (counted), raises `record_error` (at most one per 10 s) and reopens in a new part at
most once per `flush_s`; the writer thread never exits on an error (guard sets `failed`). The queue is bounded by
count and bytes (256 MB). The `unit` heartbeat is status "error" ("recorder dead" / "recording paused" / "record
error" in the last 10 s). `close()` is bounded even with a hung writer and a full queue. session.json is written via
tmp + fsync + rename + directory fsync; `replay.load` survives an empty or corrupt session.json (`info = {}`,
`info_error = "session_json_unreadable"`, ids from the directory name, `sim` from the messages, true if unknown), and
`replay.iter_lines` returns the lines before a corrupt later gzip member. Synthetic sessions (`wfgvu.synth`) write the same files plus
`truth` in session.json. Scenarios (CLI `python -m wfgvu.synth SCENARIO OUT_DIR --seed N --duration S`):
`no_fire`, `smoke_only`, `flame_front` (approaching line fire, known depth/height/spread), `water_mist`,
`corner_reflector` (2-5 m, test B geometry), `crossing` (vehicle drives through a flame zone: flux pulse,
GNSS track, the "measured thickness" is known), `after_pass` (fire gone, for REOPENED), and failure overlays
`--fail SENSOR@T` (sensor stops), `--freeze SENSOR@T` (same data repeats), `--fault tc_plate@T:open`.
As built (2026-11-17): `crossing_return` (cross, flame burns out at 16 s, forward "teardrop" turnaround at 3 m/s
so GNSS course follows the heading, stop 25 m past the far edge facing the crossed road; the only scenario off the
road axis: 2-D pose for radar, thermal, IMU, GNSS) and `crossing_return_hot` (same, a 600 C hot area stays over the
crossing) also write `dem.npz` (the session's ground plane as a `crossing.terrain.Dem` npz, "local-enu"), named in
session.json `dem`, for the laptop's `--dem` (FS-8). Committed as 68 s samples (radar 4 Hz to keep samples/ < 5 MB);
apps/crossing/tests/test_reopen_e2e.py replays them in process: REOPENED at 64.8 s (stop 36.69 s) with the DEM,
never without it, never for `_hot`.

Synthetic physics must be stated in `synth.py` docstrings and is illustrative only: radar flame effect = phase
flicker (random phase walk, std set by scenario) plus small loss on echoes behind the flame; smoke-only = no radar
effect and thermal below 120 C; mist = 1-3 dB loss, small amplitude flicker, cool thermal.

## 5. Laptop: link and freshness (`crossing/link.py`)

`SensorTrack` per sensor: `last_rx_mono` (laptop clock), `last_seq`, `last_payload_digest`,
`last_change_mono` (when the payload last differed), `status_from_pi`, `drops`.
`fresh(sensor, now) -> bool` is True only if all hold: link connected; a reading arrived within `stale_s = 2.0`;
the latest Pi heartbeat for that sensor arrived within 2.0 s and says "ok"; the payload changed within
`freeze_s` (thermal 2.0, radar 2.0, imu 2.0, tc_* 5.0 (thermocouples can sit still), gnss 5.0 when speed 0).
`Health` snapshot: dict sensor -> {fresh, reason, age_s}. Link loss marks every sensor not fresh at once.
As built: "link connected" also requires some message within `silence_s = 1.5` (Pi heartbeats every 0.5 s), so a
silent Wi-Fi link counts as lost before TCP notices; the GNSS freeze rule is applied at any speed (a live fix
changes its `utc` every fix); the `pi` payload is not freeze-checked. The pipeline additionally stops USING a value
older than `use_max_age_s` (thermal/radar/tc_*/imu 1.0 s, gnss 1.5 s), which closes the verdict within 2 s of a
sensor stopping. `LinkClient` reconnects with exponential backoff (0.5 s doubling to 5 s) and drops a connection
with no data for 3 s.
As built after the fail-safe fixes (2026-11-17, decisions D2/D6): freeze detection has two parts. (a) Pi-side
freeze: a reading or heartbeat whose `seq` is not above the previous one of that stream, or whose Pi `t_mono` is
not later, makes the sensor not fresh AT ONCE ("frozen on the Pi"), until the stream advances again. (b) Value
freeze: `freeze_s` thermal 1.0, radar 1.0 (identical raw values: thermal `pix`, radar IQ heatmap / range profile /
points; frame counters and flags are ignored), imu 2.0, tc_* 5.0, gnss 5.0 (values that can repeat legitimately,
so (a) is their fast path). A TC001 shutter/FFC pause longer than 1.0 s therefore gives a short CLOSED (fail closed).
Worst case at the laptop for a `wfgvu.synth --freeze` / test D thermal freeze (values repeat, seq and t_mono still
advance): <= 1.0 s after the fault + the 0.2 s tick (measured on synthetic replays: thermal 0.80-1.15 s, radar
1.00-1.25 s). A tc/imu/gnss value freeze with seq still advancing is caught only after its long window (not within
2 s; not among the test D faults). `use_max_age_s` pi is 1.6 s (every sensor is required, section 8). A health
`age_s` down to -1e-3 s is float rounding and counts as fresh (decision `AGE_ROUNDING_TOL_S`; the clamp in
link.py is gone); a clearly future time is not fresh.

## 6. Laptop physics modules

### 6.1 `flux.py` (step 2)
- `PlateSpec(thickness_m=0.001, rho=8960.0, cp=385.0, absorptivity=0.95, emissivity=0.95, area_m2=0.0025)`.
- `fit_cooldown(t_s, plate_c, air_c, spec) -> LossModel` fits `loss(T) = h*(T-Ta) + eps*sigma*(T^4 - Ta^4)`
  (h free, eps fixed from spec unless `fit_eps=True`) by least squares on `rho*cp*d*dT/dt = -loss`; returns h, eps,
  rms residual, n points, temperature range. Saved/loaded as JSON (`plate_loss.json`).
- `derivative(t, y, window_s=1.0, order=2) -> dT/dt` local polynomial (Savitzky-Golay style) in numpy.
- `FluxEstimator(spec, loss)`: `update(t_s, plate_c, air_c) -> FluxSample(t, q_kw_m2, q_abs_kw_m2, dTdt, valid,
  reason)`; incident q = (rho*cp*d*dT/dt + loss(T)) / absorptivity / 1000. Invalid on thermocouple fault, gaps
  > 0.5 s, or T outside [-20, 1000] C.
- `tdu(q_series_kw_m2, dt=1.0, q0=0.0)` identical to kcf_heat.exposure.tdu. `RunningDose(q0=0.0)` integrates
  sample by sample with the actual dt.
- As built: `update(t_s, plate_c, air_c, fault=None)` (a MAX31855 fault string invalidates the sample);
  `FluxSample.t` is the centre of the derivative window (lag window/2); invalid also on missing air temperature or
  time going backwards. The live pipeline uses a 2.2 s window (see section 9).

### 6.2 `thermal.py`
`ThermalFrame(t, temps_k [h,w])`; `flame_mask(temps_k, t_flame_c=300.0) -> bool [h,w]`;
`hot_mask(temps_k, t_hot_c=60.0)`; `column_bearing_deg(col, w=256, hfov_deg=56.0)` (+ right of boresight);
`flame_at_bearing(mask, bearing_deg, tol_deg) -> (bool, n_pixels)`. Camera model `CameraModel(w=256, h=192,
hfov_deg=56.0, vfov_deg=42.0)` pinhole, principal point at centre (configurable).
As built: `flame_at_bearing(mask, bearing_deg, tol_deg=3.0, model=CameraModel(), min_pixels=2)` (one hot pixel is
not a flame); pixel centres at whole-number coordinates, principal point ((w-1)/2, (h-1)/2); helpers
`validate_frame`, `saturated_mask`, `flame_columns`, `lowest_flame_row`, `top_flame_row`, `flame_bearing_deg`,
`frame_from_reading`.
As built after FS-1 (2026-11-17): flame pixels come only from `flame_evidence_mask(temps, gain, t_flame_c,
margin_c, scale_verified)`, which returns None (flame pixels UNKNOWN, never 0) unless the frame's `gain` is "low"
(missing / "high" = not low: the TC001 high-gain range, vendor ~-20..150 C, can never read the 300 C threshold, so
an empty mask would read as "no flame"), the threshold is below the gain ceiling (low ~550 C, high ~150 C, vendor
figures, unconfirmed) minus 5 C, and the low-gain scale is verified. Pixels at the gain ceiling count as flame
pixels. The pipeline then gives the thermal sensor a fault, fused flame UNKNOWN, no REOPENED hold. The camera's
gain is UNVERIFIED: the `gain` field is only the unit's configured value (the driver cannot read it back or set
it; shipped `config/unit.yaml` says `gain: high`), and the raw/64 K scale is documented for high gain only. Until a
lab check on a target hotter than 150 C confirms low gain and the low-gain scale, crossing.yaml
`thermal.low_gain_verified` stays false (placeholder) and every live (non-simulated) frame is flame-unknown, so
every live verdict is CLOSED; simulated frames count as verified.

### 6.3 `radar_flame.py` (step 3)
- `RadarBaseline` captured from N >= 20 frames with no flame (operator action "capture baseline" in the UI, or
  loaded from file): per range bin mean dB, std dB, phase std (rad) per bin from the az heatmap at boresight beam.
- `beam(iq [bins, ant], bearing_deg) -> complex [bins]` conventional beamforming for the AOP virtual array
  (configurable steering vector; default uniform linear 4-element azimuth, lambda/2).
- `RadarFlameDetector(baseline, window_s=3.0, cfg)`: `update(frame, t) -> RadarState`.
  Over the sliding window: strongest echo per bin = max amplitude (dB) over the window (gaps in the flame give
  clear looks); `loss_db` per target bin = baseline_db - window_max_db; `flicker_amp_db` = std of frame-to-frame
  amplitude differences; `flicker_phase_rad` = circular std of frame-to-frame phase differences at that bin;
  each turned into a z-score against the baseline's own frame-to-frame noise. `radar_effect` = any target bin
  beyond the near edge with (loss_z >= k_loss and loss_db >= min_loss_db) or flicker_phase_z >= k_flicker or
  flicker_amp_z >= k_flicker (defaults k = 4, min_loss_db = 1.0).
- `first_solid_echo(window_max_db, noise_db, near_edge_m, range_res_m, min_snr_db=12, persist=0.5)`: first bin
  beyond the near edge whose window-max is >= min_snr above noise and present in >= persist of the frames.
- `RadarState(status in {"FLAME_EFFECT","NO_EFFECT","UNKNOWN"}, reason, loss_db, flicker_phase_rad,
  flicker_amp_db, z-scores, far_echo_m|None, per_bin arrays for the UI)`. UNKNOWN when: no baseline, < 1 s of
  frames in the window, frames missing heatmap AND range profile, no echo at all beyond the near edge (cannot
  look behind the flame), or noise above `max_noise_db`.
- `fuse_flame(radar_state, thermal_flame_at_bearing: bool) -> FlameState(status in {"FLAME","NO_FLAME",
  "UNKNOWN"}, reason)`: FLAME only if radar FLAME_EFFECT AND thermal flame at that bearing. UNKNOWN if radar
  UNKNOWN. Everything else NO_FLAME. Smoke-only data must give NO_FLAME (tested).
- As built: the baseline keeps beam statistics on a -30..30 deg grid (5 deg steps; a bearing > 2.5 deg off the grid
  gives UNKNOWN). `RadarFlameDetector.update(frame, t, near_edge_m=None, bearing_deg=0.0, moving=False)` =
  `push(frame, t)` + `evaluate(now, ...)`; `evaluate` also checks staleness; `moving=True` gives UNKNOWN.
  Amplitude flicker is the std of frame-to-frame differences of LINEAR amplitude over the mean amplitude, in
  dB-equivalent (x 8.686); z = ln(s_window/sigma_b) / sqrt(0.75/m_window + 0.75/m_baseline) with sigma_b floored at
  the theoretical noise for the echo's SNR. Target bins: beyond the near edge with baseline echo >= 12 dB above
  noise; flicker only on bins >= `flicker_min_snr_db` (15). An echo is "present" in a frame at >= noise + 6 dB
  (`present_snr_db`); `first_solid_echo` takes `present_frac`. Noise limit: `max_noise_rise_db` = 10 above the
  baseline floor (absolute `max_noise_db` optional, off). Extra UNKNOWN cases: no reference echo beyond the near
  edge in the baseline, bin count / range resolution differ from the baseline, < 2 consecutive frame pairs.
  `fuse_flame(rs, None)` (thermal unknown) gives UNKNOWN. Near-edge ranges given to the detector are slant ranges.
- As built after the step 8 fixes (all limits below are placeholders):
  - Noise floor (heatmap): no longer the 25th percentile of per-bin medians (biased ~13 dB high when ground clutter
    fills every bin, so clutter beyond ~15 m was never scored). The baseline floor is the 60th percentile over bins
    of the frame-to-frame complex residual mean|y_i - y_(i-1)|^2 / 2 (`temporal_noise_db`; static echoes cancel,
    anything that moves an echo only raises it), never below the level estimate - 20 dB (guard against frozen or
    coarsely quantised IQ). The window floor = baseline floor + the measured rise of the median residual over the
    bins in front of the flame (all bins if < 16 there); rise > 10 dB gives UNKNOWN; thresholds and the thermal
    sigma floor use the risen floor. The range profile (no phase) keeps the level estimate. Baselines saved before
    this load with `noise_method` "level" (their old, higher floor).
  - `first_solid_echo(..., present_frac, reference_db, reference_std_db, clutter_margin_db=12, cfar_halfwidth_m=2,
    cfar_guard_m=0.3, max_reference_std_db=2)`: the "solid echo beyond" used by the CLOSED rule is the first bin
    beyond the near edge that is (1) seen through the window (window max >= noise + 12 dB, present in >= 50 % of
    frames), (2) point-like and clearly above clutter: its NO-FLAME BASELINE mean is >= 12 dB above the median of
    the baseline over +-2 m (excluding +-0.3 m) and the local maximum within +-0.3 m, and (3) static in the
    baseline (per-frame std <= 2 dB). Phase flicker in the window is allowed (that is the flame's effect on it).
    Ground clutter is not a solid echo. The radar ceiling (depth c = far echo - near edge) is reported; it changes
    hi_m only when calibration sets `trust_radar_ceiling` (`depth.combine`, tested); when trusted it only caps hi_m
    (min(hi_m, ceiling), PHYS-1); it never enters the mean and never raises lo_m.
  - Control echoes: bins >= 15 dB in FRONT of the flame (0.5 m to near edge - 2 m). An effect behind the near edge
    is UNKNOWN (not FLAME_EFFECT) if a control echo shows the effect, if the median control flicker z >= 1.5 (>= 8
    control bins), or if there is no control echo (`require_control`). Common-mode phase jitter measured on the
    control echoes is added in quadrature to every bin's phase sigma.
  - Minimum effect time: FLAME_EFFECT only if the effect has held for >= `min_effect_s` = 2 s of frame pairs
    (`effect_duration_s`: per-pair normalised step or per-frame loss on the effect bins >= 2.5, gaps <= 1 s, >= 50 %
    of pairs flagged in each half of the run); a window that is mostly pre-flame frames gives UNKNOWN ("held for
    only"). Measured on synthetic data: first FLAME_EFFECT 1.9-2.0 s after onset (the first pair includes the last
    pre-flame frame).
  - Range-profile-only frames (no heatmap) give UNKNOWN unless `allow_profile_only` (placeholder, default off):
    the TLV 2 dB scale (section 3) is UNVERIFIED on the EVM and every dB threshold of the profile path (solid echo,
    present, loss, noise rise) depends on it (PHYS-6).
  - `moving=True` gives UNKNOWN AND invalidates the baseline (`detector.baseline` becomes None, window cleared,
    `invalidated_reason` set), whatever debounce the caller applies; a new baseline must be captured once stopped.

### 6.4 `terrain.py`, `geometry.py` (step 4)
- `Dem.load(npz)`: keys `z` (float32 [h,w], row 0 north), `x0`, `y_top`, `res`, `crs` ("EPSG:5179" needs pyproj,
  or "local-enu" with `lat0`,`lon0`). `Dem.elevation(lat, lon)` bilinear, NaN outside.
  `road_profile(dem, lat, lon, course_deg, s_max_m=80, ds=2.0) -> Profile(s[], dz[], source)`; dz relative to
  the vehicle's ground point. Without a DEM: `Profile.plane(grade=tan(imu_pitch_corrected), source="imu")`.
  The geometry result carries `slope_source` in {"dem","imu"} and the UI shows it.
- `CameraPose(height_m, mount_pitch_deg, mount_roll_deg, mount_yaw_deg)` + IMU roll/pitch.
- `pixel_ray(model, pose, imu, row, col) -> unit vector in the vehicle-level frame (x fwd along course, z up)`.
- `intersect_profile(ray, cam_height, profile) -> s_m | None` (first crossing, numeric march then bisection).
- `near_edge(mask, ...) -> NearEdge(d_m, bearing_deg, row, col, d_lo_m, d_hi_m)`: lowest flame pixel per flame
  column, ray to ground, nearest over the flame columns near the chosen bearing; interval from +-0.5 px and
  IMU pitch uncertainty (config, default 0.5 deg).
- `flame_height(mask, near_edge, ...) -> (h_m, h_lo, h_hi)`: top flame pixel in those columns, elevation angle at
  the near-edge distance, minus ground height there from the profile.
- As built: `NearEdge.d_m` is the distance ALONG THE COURSE (not slant); nominal base = bottom edge of the lowest flame
  pixel (row + 0.5), +-0.5 px; extra fields `slope_source`, `occluded`, `ground_dz_m`, `columns`. A base hidden
  behind a crest gives `occluded`, d_m = d_lo_m = last visible ground point, d_hi_m = inf; the hidden ground is
  searched over the whole footprint of the lowest flame pixel (up to the farthest landing of the ray through its TOP
  edge, +-pitch sigma; PHYS-3: a crest cutting the flame inside that pixel was missed before). An occluded base is
  NOT observed: `flame_height` then has h_hi = inf, `depth.intensity` is invalid and the pipeline gives CLOSED with
  NEAR_EDGE_NOT_OBSERVED (FS-2). `near_edge(mask, model,
  pose, imu, profile, bearing_deg=None, tol_deg=5.0, pitch_sigma_deg=0.5)`; `flame_height(mask, ne, model, pose,
  imu, profile, pitch_sigma_deg)`. `road_profile` uses grid bearing = course - meridian convergence (pyproj) and the
  projection scale factor; `Profile` has `valid`/`reason`; `imu_plane_profile(pitch, mount_pitch)` is the fallback.
  A flame base cut off by the image (2026-11-17, D5): a flame column in the bearing window whose lowest flame pixel
  is on the bottom row, or flame in the 2 outermost columns at either side inside the window, sets
  `NearEdge.base_cut_off` (+ `cut_off_reason`, d_lo_m = 0; d_m NaN when no column reaches the ground); the pipeline
  then gives CLOSED with NEAR_EDGE_NOT_OBSERVED (a level camera at 2.6 m sees no ground nearer than about 6.8 m).
  A flame reaching the TOP row has an unknown height: `flame_height` returns None (`flame_top_cut_off`), so no Byram
  intensity comes from a lower bound. Camera pitch: crossing.yaml `mount.camera_pitch_deg` if set, else the unit's
  (`hello.mount`, a replayed session.json `config.mount`, else `config/unit.yaml`), else 0.

### 6.5 `fuels.py`, `heat.py`
- `Fuel(code, name, residence_s, residence_rel_sigma, consumed_load_kg_m2, heat_kj_kg)`; `FUELS` from FBFM40 table
  (consumed load = 1h + 50% live herb by default, stated) plus `C064_GRASS` (FDS case: t_r from SAV 9770 1/m,
  0.28 kg/m2, 17425 kJ/kg) and `DEFAULT` (t_r 11.52 s, 1.0 kg/m2, 18608 kJ/kg, from wfg_latest POLICY).
- `heat.closed_form_line_flux(d_m, depth_m, intensity_kw_m, chi=0.30, half_width_m=None)` calls kcf-heat
  `law.line_flux_s(s = d + depth/2, ...)` (R*t_r = depth). `heat.in_flame_flux(depth_m, intensity_kw_m, chi)`
  = value at d = 0 (the repo's contact convention chi*I/(pi*D), same as exposure.py inside a flaming cell).
- `heat.fds_reference(d_m, intensity_kw_m)` from `research/kcf-heat/data/b2_fds_compare.json` bins (geometric
  means, interpolated in log space, scaled linearly by I/4473) and in-flame reference from the C064 radiometers
  inside the fuel bed (RAD_X080 max 78.2, RAD_X090 max 62.6 kW/m2, scaled by I/4473). Always labelled
  "FDS C064 reference, not a measurement".

### 6.6 `depth.py` (step 5)
`Estimate(name, value_m, lo_m, hi_m, sigma_log, valid, reason)`. Estimators:
- a `spread_burn(near_edge_world_track, fuel)`: least-squares spread rate of the near edge towards the vehicle
  in a world frame (GNSS + course, so vehicle motion is removed) over >= 5 s, times fuel residence time.
  Invalid if R <= 0.02 m/s or fit poor; sigma from fit SE and the fuel's residence sigma.
- b `byram(flame_height_m, fuel)`: L >= height (vertical flame assumed; tilt makes L longer, stated),
  I = (L/0.0775)^(1/0.46), depth = I * t_r / (heat_kj_kg * consumed_load). sigma_log default 0.6 (as built: model
  part 0.6, total with t_r and H*w, see below).
- c `radar_ceiling(near_edge_m, far_echo_m)`: far - near. Reported as a ceiling; used as an estimator only when
  `trust_radar_ceiling` is enabled for the fuel by calibration (section 7); never used to LOWER the decision
  upper end otherwise.
- d `flicker_extent(per_bin_flicker_z, near_edge_m)`: extent in range of bins with flicker_z >= k beyond the near
  edge (experimental; off by default; reported every time with whether it agreed with measured thickness).
- e `radar_loss_depth(loss_db, db_per_m)`: only when calibration has a dB/m for the fuel (n >= 3 pairs).
`combine(estimates, calib) -> DepthResult(depth_m, lo_m, hi_m, level=0.90, used=[...], calibrated: bool,
n_pairs, method)`: inverse-variance weighted mean of log values of valid enabled estimators, interval
exp(mu +- z*sigma*scale) where scale comes from calibration (section 7; uncalibrated scale = 1.5 and flagged).
No valid estimator -> `DepthResult(valid=False)` -> CLOSED.
`intensity(flame_height, spread, fuel) -> IntensityResult(i_kw_m, lo, hi, sources)`: Byram inverse from flame
height interval and/or I = R * heat_kj_kg * consumed_load from estimator a; hi = max of available upper ends.
No source -> invalid -> CLOSED.
As built after the physics fixes (2026-11-17; all sigmas placeholders):
- PHYS-1: `radar_ceiling` never enters the mean (even if listed in `enabled`); when trusted it only caps hi_m =
  min(hi_m, ceiling) when ceiling >= depth_m (a lower ceiling is flagged as a conflict and not used). It never raises
  lo_m and never moves depth_m (it used to pull lo_m up to ~0.9x the ceiling: in-flame flux 48x too low on a probe).
- PHYS-5: spread_burn and byram share the fuel's residence-time error t_r; each estimate reports it as
  `details["shared_log_sigma"]` and `combine` is a GLS mean with C_ii = sigma_i^2, C_ij = s_i s_j (correlation 1),
  so the combined sigma_log never falls below residence_rel_sigma when every estimator used depends on t_r (falls
  back to the widest single estimator if the solve fails). byram sigma_log = sqrt(0.6^2 + residence_rel_sigma^2 +
  0.3^2) (model, t_r, H*w).
- FS-2 / PHYS-2: `intensity` is INVALID when the flame-height central value or upper end is missing, not finite,
  above 100 m or (upper end) below the central value, also when a spread-rate source exists; it is never replaced
  by the central height. A bad lower end only sets lo to 0.
- Estimator d (R6): recorded on every pair (value, lo, hi, valid, reason) with `flicker_extent_agrees` (measured
  inside its interval), in `pairs.csv`, the pair store and the calibration status (`n_d_valid`, `n_d_agree`,
  `n_d_disagree`, experimental, information only); not shown in the State/UI beyond the calibration status.
- DEPTH-HI rule (2026-11-17): the GLS mean follows the narrowest estimator, so its upper end fell BELOW the truth
  on the SIMULATED flame_front sample (true 3.0 m: combined median 0.58 m [0.27, 1.21]; spread_burn ~0.57 m, byram
  ~1.1 [0.33, 3.7] m). `DepthResult` now also carries `hi_decision_m` (the upper end the dose and time_in_flame use,
  via `decision.depth_hi_for_decision`; `depth_m`/`lo_m`/`hi_m` stay for display and calibration pairs) =
  max(combined upper end of the non-experimental estimators, hi_m of every valid `spread_burn`, `byram`,
  `radar_loss_depth`), plus `hi_decision_from`, `hi_decision_rule`, `disagree_ratio`. Estimator d never raises or
  lowers it (left out of the decision combination even when enabled; d alone -> INVALID). The radar ceiling never
  raises it and lowers it only when calibration trusts it (same cap rule as hi_m). Config `depth.narrow_decision_hi`
  (default false) lets it fall to the combined upper end only for a fuel calibrated with >= 
  `narrow_decision_hi_min_pairs` (30, placeholder, >= 9) pairs. `ESTIMATORS_DISAGREE` in `flags` when max/min
  central value > `depth.disagree_factor` (3.0, placeholder); shown in the UI, does not close by itself. State key
  `depth.hi_decision_m`, shown as "Depth upper end used for decision". Measured on the committed SIMULATED samples:
  flame_front hi_decision_m 2.6-7.5 m (median 3.9; truth 3.0 m inside [lo, hi_decision_m] in 93 % of valid
  States vs 14 % for [lo, hi_m]); crossing (byram only) unchanged, median 6.7 m.

## 7. Calibration (`calibrate.py`)
- Measured thickness during a crossing: time that plate flux stays above `thickness_q_kw_m2` (default 5.0) times
  mean GNSS speed over that time (`measure_thickness(flux_samples, gnss_samples)`).
  As built (2026-11-17, D7): the threshold is `max(thickness_q_kw_m2, thickness_frac_of_peak * pulse peak)`,
  default frac 0.5 (width at half maximum; 0 restores the fixed 5 kW/m2). Reason: 5 kW/m2 counts the radiant halo
  and the flux smoothing (SIMULATED `crossing` sample, true depth 3.0 m: 11.6 m at 5 kW/m2, 4.2 m at half maximum).
  For a uniform in-flame flux smoothed by a symmetric kernel the half-maximum width is never below the flaming
  depth, so the bias stays high: conservative for interval width and ceiling trust, but ANTI-conservative for dB/m
  (a lower dB/m lengthens the radar-loss depth, raises lo_m and lowers the dose; PHYS-4: known bias, mitigated by an
  upper-quantile dB/m below). Minimum pairs per
  fuel before anything changes: scale n >= 9, dB/m n >= 3, ceiling trust n >= 9; scale never below 1.0.
- Pair = {fuel, predicted depth_m, lo, hi, sigma_log, per-estimator values, radar loss_db, measured_m, time,
  lat, lon, session}. Stored as JSONL `apps/crossing/records/calibration/pairs.jsonl` (append-only, git-ignored)
  per laptop.
- Interval recalibration per fuel type, conformal risk control (S-D9 crc.py rule) with miscoverage loss: score_i =
  |log(measured_i / predicted_i)| / (z * sigma_log_i), z = 1.6449, so that s multiplies the nominal 90 % interval
  exactly as `scale` does in 6.6; choose the smallest scale s from {scores} such that
  n/(n+1) * mean(1{score_i > s}) + 1/(n+1) <= alpha (alpha = 0.10). If infeasible (n < 9 at alpha 0.10) keep the
  uncalibrated scale 1.5 and report "uncalibrated (n = k, need >= 9)". Never shrink below 1.0.
- dB/m per fuel: 90th percentile (as built, PHYS-4; was the median) of loss_db / measured_m over pairs with
  loss_db > 0, needs n >= 3.
- `trust_radar_ceiling` for a fuel only when n >= 9 and every pair had measured <= ceiling.
- As built (FS-5): each pair carries a dedup `key` (session, fuel, pulse end on the Pi clock to 1 s; or the
  prediction for a tape mark without a pulse), its pulse window, prediction time and source. A pair with the same
  key, an overlapping pulse in the same session or the same prediction is refused (`--loop` replays and repeated
  "mark crossing" presses add nothing); `recalibrate` counts each key once (old rows: one per session + measured +
  predicted), and scale, dB/m and ceiling trust take effect only with pairs from >= 2 distinct sessions. Replays of
  recorded real sessions use `pairs_replay.jsonl`; only live real sessions write and read `pairs.jsonl`.

## 8. Vehicles and decisions (`vehicles.yaml`, `decision.py`)

`vehicles.yaml` entries: fire_engine, water_tanker, pickup, command_car, evacuation_minibus, custom; each has
`length_m, width_m, height_m, sensor_height_m, max_safe_speed_m_s, dose_limit_tdu, intake_air_limit_c,
has_water` and `placeholder: true`. The UI prints "PLACEHOLDER limits: to be set by the fire service" beside every
limit. Global (crossing config): `stale_s = 2.0`, `verdict_ttl_s = 5.0`, `spray_margin = 0.25` (dose at max
speed may exceed the limit by up to 25 % for SPRAY THEN RE-CHECK), `reopen_hold_s = 30`, `reopen_flux_kw_m2 = 1.0`,
`reopen_hot_pixels = 0` (flame-temperature pixels), `q0_kw_m2 = 0.0`, `approach_m = 30`.
As built (FS-4): `config.validate` runs at load and refuses to start on any decision value that is not a finite
number or lies outside placeholder bounds: 0 < verdict_ttl_s <= 5, 0 < stale_s <= 2, 0 <= q0_kw_m2 <= 5,
0.1 <= chi <= 1, 0 <= spray_margin <= 0.5, min_flame_evidence_s >= 3, reopen_hold_s >= 30, approach_m > 0,
0 <= reopen_flux_kw_m2 <= 1, reopen_hot_pixels integer >= 0, 0 <= reopen_max_speed_m_s <= 1, speed_resolution_m_s >
0, leg_points integer >= 50, half_width_m null or > 0; link stale_s / heartbeat_stale_s and every use_max_age_s
finite and <= 2 s, silence_s > 0; freeze_s thermal/radar in (0, 2], tc_* / imu / gnss in (0, 5], only pi may be null.

Dose along a crossing at constant speed v. Conservative in both factors: time uses the depth UPPER end; the
closed-form flux falls as depth grows (chi*I/(pi*D) inside, s = d + D/2 outside), so flux uses the depth LOWER end
and the intensity UPPER end:
`time_in_flame = (depth_hi + vehicle.length_m) / v` (depth_hi = `depth.hi_decision_m`, 6.6 DEPTH-HI rule); TDU = in-flame flux^(4/3) * time_in_flame + approach and exit
legs integrated over `approach_m` each side with the closed-form line flux. FDS reference dose computed the same
way and shown beside (never used to decide).

`decide(inputs: DecisionInputs, vehicle, cfg, now) -> Verdict(state, reasons[], issued_mono, expires_mono,
min_speed_m_s, time_in_flame_s, dose_tdu, dose_limit_tdu, dose_fds_ref_tdu, details)`. Order:
1. Default CLOSED. CLOSED if: link down; any required sensor not fresh (as built 2026-11-17, D1: EVERY sensor,
   thermal, radar, tc_plate, tc_housing, tc_air, imu, gnss, pi, is required for EVERY go verdict, so any
   reading or Pi heartbeat older than 2 s, frozen, missing, faulted or Pi status not "ok" closes); radar status
   UNKNOWN; flame status not FLAME (for CROSS FAST/SPRAY); no first solid echo beyond the flame; depth invalid;
   intake air temperature (tc_air) over the vehicle limit; dose over limit at max safe speed (beyond spray rule);
   any input value NaN/inf/out of range; inputs older than verdict_ttl_s.
2. CROSS FAST: dose(v) <= limit for some v <= max_safe_speed; report `min_speed` = smallest such v (bisection,
   0.1 m/s resolution, rounded UP).
3. SPRAY THEN RE-CHECK: only if has_water and dose(max_safe_speed) <= limit * (1 + spray_margin). No water model.
4. REOPENED: `passed` (vehicle GNSS track went past the far edge recorded at the crossing or past a recorded
   flame location by depth_hi + length), and plate flux < reopen_flux and flame pixels <= reopen_hot_pixels
   continuously for reopen_hold_s, all REOPENED sensors fresh, GNSS fix valid; carries GNSS lat/lon/utc stamp.
Every verdict expires 5 s after issue; `effective(verdict, now)` returns CLOSED once expired. The pipeline
re-decides at 5 Hz from fresh data only.
As built: every required sensor also needs an `input_times` entry (missing, older than verdict_ttl_s or > 0.5 s in
the future -> CLOSED); a health entry counts only when `fresh is True` and `age_s <= stale_s`; any `faults` entry
of a required sensor closes; CROSS FAST/SPRAY also need a GNSS fix with lat/lon, IMU roll and pitch, flame_pixels
and tc_plate_c; FLAME with a radar status other than FLAME_EFFECT closes (FLAME_RADAR_INCONSISTENT); range checks
(e.g. |pitch|, |roll| <= 45 deg, tc_housing in [-40, 300] C) are placeholders. min_speed is capped at
max_safe_speed when rounding up would pass it. "Far edge recorded at the crossing" = the GNSS position (interpolated
between fixes) when the plate flux fell below `thickness_q_kw_m2` at the end of the pulse; the radiant zone beyond
the flame makes it later than the true far edge (conservative). A session with no recorded crossing and no recorded
flame location (e.g. the `after_pass` sample alone) can never give REOPENED.
As built after the fail-safe fixes (2026-11-17): CROSS FAST / SPRAY also need the fused FLAME held continuously
for `min_flame_evidence_s` = 3.0 s (placeholder; FLAME_EVIDENCE_TOO_SHORT; the earlier build gave CROSS FAST 0.38 s
after onset) and an observed flame base (`near_edge_observed`: not cut off by the image and not occluded by
terrain, else NEAR_EDGE_NOT_OBSERVED, see 6.4). An IMU whose BNO055 accel or gyro calibration status is below
`geometry.imu_min_calib` = 1 (or missing) is an IMU fault (FS-9, placeholder). REOPENED (D3)
also needs the recorded crossing IN THE CAMERA'S CURRENT VIEW: near/far edge GNSS positions recorded at the plate
flux pulse (else the recorded flame location + depth_hi), widened by `reopen_half_width_m` = 4 m across the track;
every corner at a camera bearing within the horizontal FOV minus `reopen_fov_margin_deg` = 4, farthest corner
within `reopen_max_view_m` = 40 m, nearest corner above the bottom image edge (flat ground, camera height, mount and
IMU pitch); heading = GNSS course while moving, the last moving course held while stopped, IMU heading only when the
unit config sets `imu_heading_trusted`. As built after FS-3 / FS-8 (2026-11-17, placeholders): the heading is the
camera FACING: a trusted IMU heading (+ offset) first, stopped or moving; else the GNSS course only from forward
travel at >= `reliable_course_speed_m_s` = 2 m/s, within 60 deg of a trusted IMU heading and within
`course_jump_deg` = 120 of the last forward course, held while stopped; a fix between 0.3 and 2 m/s keeps it only
within `low_speed_course_tol_deg` = 15 (braking), else (manoeuvring, reversing) the facing is unknown and the view
check fails until reliable travel in the old direction or a trusted IMU heading shows it again (a turn made below
2 m/s therefore blocks REOPENED without a trusted IMU heading). The view also needs LINE OF SIGHT over the DEM to
all six patch points (no DEM = not verifiable = not in view, so REOPENED needs `--dem`; a bare-earth DEM covers
terrain only, not buildings, walls, vegetation or vehicles), the patch points projected with DEM heights inside the
image margins, and the thermal pixel at each point a plausible ground temperature (-30..150 C; colder = sky). The
image check cannot tell a wall or crest face from the road. The DEM road profile for the geometry and the recorded
flame location also follow the facing. Otherwise CLOSED with REOPEN_CROSSING_NOT_IN_VIEW and State
`reopen.view.hint` asks the crew to face the crossed road. Also GNSS speed <= `reopen_max_speed_m_s` = 1.0
(REOPEN_VEHICLE_MOVING), and zero flame-temperature pixels in the image columns covering the crossing
(CROSSING_HOT_PIXELS_PRESENT); in-view, those columns and the speed limit are all part of the continuous
reopen_hold_s quiet hold, so the hold is time spent stopped facing the crossing (an unknown speed counts as moving;
fix 2026-11-17: before it the hold could start while still rolling, giving REOPENED 28 s after the stop).
A vehicle that passed and stopped facing away therefore never gets REOPENED (tested); all limits are placeholders.

Required unit tests (tests/test_failsafe.py): for a scenario that gives CROSS FAST (or REOPENED) with all inputs
good, each single sensor made stale / missing / frozen / faulted, link loss, and a verdict older than 5 s must
each give CLOSED. Randomised over many input combinations (seeded), no combination with any such fault may yield
CROSS FAST or REOPENED. As built: every single-sensor failure (stale, heartbeat stale, missing, faulted, frozen,
Pi no_device / error, NaN, inf, out of range) of every sensor is checked against each candidate verdict (CROSS
FAST, SPRAY THEN RE-CHECK, REOPENED); `pi` has no decision value, so NaN / out-of-range do not apply to it.

## 9. Pipeline, server, UI (`pipeline.py`, `server.py`, `web/`)
`Pipeline(cfg, vehicle, fuel)` consumes parsed messages (live link or replay) and every 0.2 s publishes a
`State` dict (JSON) with: verdict (effective), health, flame (thermal + radar + fused), geometry, depth (all
estimators + combined), flux (q, dose so far), heat (closed form vs FDS ref), vehicle, fuel, gnss, sim flag.
Server: FastAPI on 127.0.0.1:8781 (not 8765), `GET /` web app, `WS /ws` pushes State, `POST /api/vehicle`,
`/api/fuel`, `/api/baseline` (capture radar baseline), `/api/mark_crossing`. Live: `python -m crossing --pi
ws://10.42.0.1:8770/stream`; replay: `python -m crossing --replay <research-log session dir or Pi record dir>`.
3D view (three.js r180, vendored): road with slope from the profile, selected vehicle box to scale, flame wall at
the near edge, depth (combined value solid + 90 % interval translucent), flame height, first solid echo beyond
marker; panel with verdict, min speed, time in flame, dose vs limit (PLACEHOLDER label), slope source, health
lights, SIMULATED watermark, "Advisory only" banner.
As built: the State JSON schema (`crossing.state/1`) is in `apps/crossing/README.md`, section STATE_SCHEMA; it also
carries intensity, radar per-bin arrays (max-pooled to <= 128 bins), the road profile points, a 64x48 thermal
thumbnail, reopen/calibration/sim-link status and placeholder flags. Extra routes: `GET /api/state`, `/api/health`,
`/api/vehicles`, `/api/fuels`; replay mode only `GET`/`POST /api/replay` (play / pause / speed 0.1-20; 404 in live
mode). Pausing a replay fails closed: the feed stops and the link is marked down ("replay paused"), so the verdict
is CLOSED (LINK_DOWN) at once and stays CLOSED while paused. The UI lists reason codes it does not know as sent and
never derives a verdict from a reason; some CLOSED reasons carry a crew instruction (e.g. face the crossed road). `WS /ws` pushes the State right after each pipeline tick (so a new verdict reaches
the UI without an extra push-period delay). The crossing is evaluated on the vehicle's path: near edge = nearest flame base within
`path_half_width_deg` (6) of straight ahead, thermal flag and radar beam at that bearing. Radar baseline: operator
capture (refused while moving or with flame pixels in view unless forced), optional `--auto-baseline`, dropped
when GNSS shows motion or > 3 m displacement. Crossings for calibration: flux pulse > 5 kW/m2 while GNSS speed
>= 0.5 m/s, paired with the depth of the last CROSS FAST / SPRAY (else last valid depth); simulated pairs go to a
separate `pairs_sim.jsonl`, replays of recorded real sessions to `pairs_replay.jsonl` (FS-5, section 7). The live plate flux uses a 2.2 s FluxEstimator window (see apps/crossing/README.md:
kept for noise against the 1.0 kW/m2 REOPENED threshold; placeholder).

## 10. Live road state to the routing API (step 9)
Flag-guarded on both ends. Laptop: `--sim-link ws://127.0.0.1:8765/v1/live/closures --region <id>`; sends only
`{"event":"CLOSED"|"REOPENED","region","lat","lon","utc","unit_id","session_id","verdict_id"}`. CROSS FAST and
SPRAY THEN RE-CHECK never leave the app. As built (laptop, after review findings R9-01/R9-08/R9-09, 2026-11-17;
`crossing/simlink.py`): per location, not per global state. `SimLink.step(tick_evidence(...))` sends CLOSED only
when FLAME-BACKED on the RAW verdict of the tick (CLOSED, not expired, reasons include DOSE_OVER_LIMIT or
NO_WATER_FOR_SPRAY, fused FLAME + radar FLAME_EFFECT held >= min_flame_evidence_s), at the flame location recorded
that tick (`Pipeline.flame_ref` as lat/lon; never the vehicle position; none -> nothing sent, nothing pending), once
per location (merge radius 50 m, PLACEHOLDER). Startup, faults, expiry, no flame, smoke, driving on: nothing.
REOPENED only for a location this link closed, at the stored location, when the raw REOPENED is fresh and the reopen
view confirmed a crossing within 50 m of it; the location is then forgotten. CROSS FAST / SPRAY never clear stored
closures. The old `outgoing(verdict, position)` / `offer(...)` signatures remain and return None. `--sim-link` with
`--replay` exits 2 unless `--sim-link-allow-replay`; sim=true data disables the link at run time (reason in State
`simlink.blocked_reason`, shown in the UI); allowed replay/sim frames carry `"origin"`, which the API as built
refuses. Client: one claim per location, stop-and-wait acks (matched by verdict_id when the ack has one; only
ok:true acks), every CLOSED claim re-sent after each (re)connect and every 60 s (PLACEHOLDER); no ack in 5 s, a
drop before the ack, INTERNAL_ERROR, DATA_UNAVAILABLE, RATE_LIMITED or unknown codes are retried with backoff;
VALIDATION_ERROR, UNKNOWN_EVENT, SNAP_TOO_FAR, UNKNOWN_REGION, NOT_CLOSED, CLOSED_BY_OTHER_UNIT, REOPEN_UNAUTHORIZED,
REOPEN_TOO_FAR, REOPEN_NOT_ON_CLOSED_ROAD are terminal (logged once at WARNING): a refused CLOSED is shown as "ROAD NOT
CLOSED IN ROUTING" and still re-asserted after reconnects and every 60 s; a refused REOPENED is not re-sent (the road
stays closed in routing, the safe side) and is shown as "REOPEN NOT APPLIED IN ROUTING" (State
`simlink.reopen_refused_in_routing`); a REOPENED supersedes an unacked CLOSED; a `claim_token` from the CLOSED ack
is returned in the REOPENED with `closes_verdict_id`; claims are never dropped for space. Handshake: the client offers
subprotocol `wfg-live.v1` plus `wfg-token.<token>` when env `WFG_SIM_LINK_TOKEN` (or `--sim-link-token-env VAR`) holds
the API's `WFG_API_LIVE_TOKEN`; the token is never logged, in the State or in the research log; a refused handshake
(HTTP 403) is retried and shown. Measured 2026-11-17 against the real API app on 127.0.0.1 (uvicorn, token set,
recorded Hongseong graph; `apps/crossing/tests/test_simlink.py::test_end_to_end_against_the_routing_api`): no token ->
refused, nothing applied; CLOSED applied; its REOPENED lifted it; a REOPENED without the claim token got
REOPEN_UNAUTHORIZED and the road stayed closed; never over a real network. API: env `WFG_API_LIVE_CLOSURES=1`
registers `WS /v1/live/closures` and `GET /v1/live/state?region=`; with the flag off nothing changes. As built (API,
after review findings R9-02..R9-07, R9-10, R9-11, 2026-11-17; `api/live.py`, `api/app.py`): handshake refused before
accept for a browser Origin not listed in `WFG_API_LIVE_ORIGINS` ("null" never; no Origin is allowed), a Host other than
loopback / the bind host / `WFG_API_LIVE_HOSTS`, or, when `WFG_API_LIVE_TOKEN` is set, no matching `wfg-token.<token>`
subprotocol; per connection at most 20 events/s, burst 60 (PLACEHOLDER; over it: RATE_LIMITED, not applied). A CLOSED
closes the widened chord match (EPSG:5179, <= 300 m: every chord within dmin + 20 m and every edge at a junction within
20 m, each with its reverse; PLACEHOLDER margin) of its point and of each optional `ahead` flame point, as one record per
(unit_id, session_id, verdict_id) with a secret `claim_token` returned only in its ack; a repeat is idempotent (same
token, `duplicate: true`); a CLOSED covering all edges of an older record of the same unit/session supersedes it
(`superseded_verdict_ids`). A REOPENED withdraws one record only with its `claim_token` (constant-time compare;
`closes_verdict_id` optional cross-check), within 50 m (PLACEHOLDER) of the CLOSED or `ahead` point, and sharing an
edge or junction with the record; otherwise REOPEN_UNAUTHORIZED / NOT_CLOSED / REOPEN_TOO_FAR /
REOPEN_NOT_ON_CLOSED_ROAD and the road stays closed. A road another unit holds stays closed (CLOSED_BY_OTHER_UNIT,
`holder_count` only, never holder ids). A REOPENED replayed after an API restart gets NOT_CLOSED (harmless). New route
checks use a derived graph.json without closed edges (same revision; provenance `evaluated_configuration: false`).
Recomputes of the region's most recent dispatch plan are coalesced per region (one in flight; changes meanwhile stay
pending and rerun once); a pending change is cleared only when a recompute covering it finishes `done`; a failed
submit (BUSY, LAUNCHES_PAUSED, any exception) keeps it pending, the ack stays `ok: true` with `recompute.status:
failed, pending: true`, and it is retried on the next event or every 5 s while a socket is open; `GET /v1/live/state`
shows pending/failed. Every `leave_by_update` frame carries the job's own road snapshot (`closed_edge_ids`,
`state_version`), the current one and `stale`; an origin a newer live recompute also covers gets `leave_by_s: null`
(`superseded_by_version`); an unknown road state gives `unknown_state` and null times. Closures live in memory only:
units must re-send held closures after a reconnect (the laptop client does, above).

## 11. Research log (step 10)
Per laptop session `apps/crossing/records/<session>/`: `session.json`, `readings_<sensor>.csv` (flattened scalars;
thermal and radar arrays to `thermal_frames.npz`/`radar_frames.npz` chunks), `verdicts.csv`, `depth.csv`,
`flux.csv`, `health.csv`, `pairs.csv` (predicted vs measured), plus Parquet copies when pyarrow is present
(`research_log.export_parquet(dir)`). Column dictionary in `apps/crossing/research_log/README.md`.
As built: chunks are `thermal_frames.<n>.npz` / `radar_frames.<n>.npz`; extra files `heartbeats.csv`,
`events.csv`, `radar_baseline_<n>.json` and `wire.jsonl.gz` (every received message with its laptop receipt time
plus link up/down markers; this is what `--replay <research-log session dir>` plays).
