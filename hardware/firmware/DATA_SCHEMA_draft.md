# Route logger data schema (draft, format version 2)

Draft from the firmware lane, 2026-10-03, revised for review rows R3, R4, R7, R19 (format 2: STATUS records and
start-reason attribution; format 1 files from firmware 0.1.0 remain readable by the firmware, usb_export.py and
viewer.html). The coordinator turns this into DATA_SCHEMA.md. This schema matches the
code in `firmware/lib/wfg_core/src/wfg_record.h` and `wfg_export.cpp`, and the samples in `phone_export/samples/`
were produced by that code in host tests (synthetic NMEA, not a real walk).

## 1. Layers and who is responsible for each value

| Layer | Where it lives | Written by | Can change later? |
|---|---|---|---|
| Observations (GNSS rows, no-fix rows, clock records) | device `.wfg` file | firmware, from the GNSS receiver | never; the raw file is the reference copy |
| Movement mode (WALK / VEHICLE / UNKNOWN) | SESSION_START record, one per session | owner, chosen on the device before starting (an auto-resumed session inherits the mode of the session that was cut) | not on the device; a later correction goes in a separate annotation file and keeps the original value |
| Session start reason | SESSION_START (header byte 3) | firmware: `OWNER_BUTTON`, or `AUTO_RESUMED_AFTER_RESET` with the cut session's number and the ESP reset reason | never |
| Device status (battery, storage) | STATUS records, at start and every 60 s | firmware, from its ADC and filesystem | never; the battery value depends on the calibration factor stored in the same record |
| Event markers | EVENT records | owner presses the button; firmware adds timing and an optional position | never |
| Owner annotations (observations, notes, corrected mode) | separate file next to the export, made on phone or PC | owner, after the trip | yes, it is the owner's own layer |
| Derived products (map matching, route segments, smoothing) | outside this logger | analysts | yes; must point back to `session_id` + `seq` and never overwrite lat/lon |

Every CSV row repeats `mode_source = owner_selected_on_device`, so mode is never mistaken for a sensor reading.
The device has no free-text input. `owner_annotation` in the CSV is always empty from the device and exists only as
a slot for later attribution.

## 2. Identifiers

| Field | Type | Meaning |
|---|---|---|
| `session_id` | string `WFG-<device 8 hex>-<session 6 digits>` | Unique per device. The device part is derived from the chip's factory MAC (not personal). The number is never reused, even after deletion or loss of `meta.txt`. |
| `seq` | uint32 | 0-based record index in the session file, +1 per record of any type, no gaps. A missing `seq` in an export means a record was lost or corrupt. |
| `record_type` | enum | `SESSION_START`, `FIX`, `NOFIX`, `EVENT`, `CLOCK`, `STATUS` (format 2), `SESSION_END`, or `CORRUPT` (CSV only: a record whose CRC failed; it is shown, not dropped). |
| `session_start_reason` | enum, every row | `OWNER_BUTTON` or `AUTO_RESUMED_AFTER_RESET`. Format 1 files read as `OWNER_BUTTON`. |
| `resumed_from_session_id` | string, every row | For an auto-resumed session: the `session_id` of the session cut by the reset. Empty otherwise. The two sessions stay separate files and separate ids; joining them is an analysis decision. |
| file name | `S000012.wfg` on device; `WFG-...-000012_WALK.csv` etc. after export | Exported names carry the mode so WALK and VEHICLE files are visibly separate. |

## 3. Time

| Field | Unit | Meaning and missingness |
|---|---|---|
| `mono_ms` | ms since boot | Monotonic, from the ESP32 timer. Always present except on a SESSION_END written by boot recovery (empty, because the clock restarted). Resets at every boot; a session never spans a reboot. Wraps after 49.7 days (not a practical concern). For FIX/NOFIX rows it is the arrival time of the first NMEA sentence of that epoch. |
| `gnss_utc` | ISO 8601 UTC, ms | The receiver's own time and date for that epoch (GGA/RMC time + RMC date). Empty if the receiver gave no time or no date. Not corrected, not interpolated. |
| `utc_est` | ISO 8601 UTC | `mono_ms` + the latest clock offset known at that point in the file. Lets rows without `gnss_utc` (no-fix gaps, events, rows before the first fix) be placed on the UTC timeline. Empty before the first CLOCK record if UTC was never known. For EVENT rows it uses the press time. |
| `utc_est_basis` | string | `mono_ms+gnss_clock_offset` when `utc_est` is filled. |
| `epoch_age_ms` | ms, 10 ms steps | Time from the first sentence of the epoch to when the row was written (parser latency). Empty on gap-filler rows. |
| CLOCK records | | `clock_kind = FIRST_UTC`: first time this session has a usable UTC (needs a date of 2024 or later and a valid RMC or position). `JUMP`: the UTC minus mono offset changed by more than 2 s (receiver time correction, leap second, rollover). `clock_offset_ms` = UTC epoch ms minus mono ms. `clock_delta_ms` = change from the previous offset. Rows are never rewritten after a jump; use the CLOCK records to see where the timeline was corrected. |

## 4. Fix quality and position

| Field | Type / unit | Meaning |
|---|---|---|
| `fix_valid` | 0/1 | 1 on FIX rows (position valid: GGA quality > 0, or RMC status A if no GGA). |
| `nofix_reason` | enum, NOFIX only | `RECEIVER_NO_FIX`: receiver is talking (valid NMEA) but reports no position. `NO_NMEA_DATA`: no valid sentence for 1.5 s (UART silent, receiver unpowered or reset). `CHECKSUM_ERRORS_ONLY`: only corrupted sentences arrived. |
| `gga_quality` | int 0 to 8 | GGA fix quality as sent (0 invalid, 1 GPS/GNSS, 2 DGPS, 6 dead reckoning, ...). Empty if no GGA in that epoch. |
| `fix_type` | `NONE`/`2D`/`3D` | From GSA. Empty if no GSA. |
| `sats` | int | Satellites used in the solution (GGA field 7). Not satellites in view. |
| `hdop` | unitless, 2 decimals | Horizontal dilution of precision. A geometry factor, NOT an error in metres. HDOP 1.0 does not mean 1 m accuracy. Treat it only as a relative quality indicator; this logger makes no claim about accuracy in metres. |
| `lat`, `lon` | degrees WGS84, 7 decimals | Exactly as received from the GNSS receiver (degrees-minutes converted to decimal degrees with integer arithmetic, about 1 cm resolution). Not filtered, not smoothed, not snapped to roads. Empty on NOFIX rows and on unlocated events. |
| `alt_m` | metres | Altitude above mean sea level from GGA field 9. Empty if absent. Not ellipsoidal height. |
| `speed_mps` | m/s, 2 decimals | Speed over ground from RMC (knots converted). Only when RMC status is A. |
| `course_deg` | degrees true, 0 to 359.99 | Course over ground from RMC. It is the direction of travel derived by the receiver while moving, NOT a compass heading, and it is meaningless at walking pace standstill. Empty when not provided. |
| `nmea_checksum_errors_seen` | 0/1 | At least one corrupted NMEA sentence arrived since the previous row. |
| `raw_nmea_available` | 0/1 | Always 0 in formats 1 and 2 (raw sentences are not stored; see firmware README for the storage reason). |

Gaps stay visible: while recording, every log interval (about 1 s) produces either a FIX or a NOFIX row. A period
without position is a run of NOFIX rows, never missing rows and never interpolated points. GPX and GeoJSON break
the track into separate segments at each NOFIX row.

## 5. Events (button markers)

| Field | Meaning |
|---|---|
| `event_no` | 1, 2, 3 ... within the session. |
| `event_press_mono_ms` | When the button went down. |
| `event_ref_fix_seq` | `seq` of the most recent FIX row received at or before the press. Empty if there was none. |
| `event_ref_fix_age_ms` | Press time minus that fix's time. |
| `event_located` | 1 only if that fix is at most 2000 ms old (value stored in SESSION_START as `event_locate_max_age_ms`). Then `lat`/`lon` are a copy of that fix. |
| unlocated events | `event_located = 0`, `lat`/`lon` empty. No interpolation, no later fix used, no guess. GeoJSON writes `"geometry": null`; GPX lists them under `<extensions>` without coordinates. |

An event means only "the owner pressed the button here/then". What it marks is recorded by the owner later as an
annotation.

## 5b. STATUS records (format 2, review R7)

Written once right after SESSION_START and then every 60 s while recording. They are device-health rows, not
observations: no position, not in GPX/GeoJSON.

| CSV column | Unit | Meaning |
|---|---|---|
| `status_vbat_mv` | mV | Battery voltage = pin mV x factor. Empty if the reading was implausible (outside 2.5-4.5 V, e.g. no battery). |
| `status_vbat_pin_mv` | mV | ADC pin voltage before the divider (`analogReadMilliVolts`, eFuse-calibrated). Kept so a later, better calibration can recompute the battery voltage. |
| `status_vbat_factor` | ratio, 3 decimals | Factor actually used: nominal divider 4.900 x owner calibration (default 1.000). UNVERIFIED until calibrated. |
| `status_fs_free_bytes`, `status_fs_total_bytes` | bytes | LittleFS free and total at that moment. |
| `status_nmea_ok`, `status_nmea_checksum_errors` | count since boot | Valid and checksum-failed NMEA sentences received. |
| (binary only) flags | bits | battery reading valid, screen on, GNSS data seen in the last 3 s, low-battery stop pending; plus free heap bytes. |

Battery runtime can be read from the file: time from the first STATUS row to SESSION_END (LOW_BATTERY or
RECOVERED_ON_BOOT), with the voltage curve from the STATUS rows.

## 6. Session start and end

SESSION_START: device id, session number, movement mode, board revision code (10, 11, 20, 80, 90), firmware version,
log interval (1000 ms), format version, record size (48), boot count, event location age limit.
Format 1 (firmware 0.1.0) also held the UTC at start (bytes 32-39). Format 2 replaces that with
`resumed_from_session_no` (u32, bytes 32-35, 0 = none) and `reset_reason` (u8, byte 36: ESP-IDF
`esp_reset_reason()`, 1 POWERON (also the RST pin and battery reconnect), 3 SW, 4 PANIC, 5 INT_WDT, 6 TASK_WDT,
7 WDT, 9 BROWNOUT), and stores the start reason in header byte 3. UTC at start comes from the CLOCK record, which
is written right after SESSION_START whenever UTC is already known.
SESSION_END: `end_reason` = `USER_STOP`, `STORAGE_FULL`, `LOW_BATTERY`, `RECOVERED_ON_BOOT` (power loss or crash;
`end_torn_bytes_removed` says how many bytes of a partial record were cut), or `FS_ERROR`; record counts and a CRC-32
over all earlier bytes. A file with no SESSION_END is still OPEN (recording, or not yet recovered).

## 7. Binary record layout (`.wfg`, 48 bytes, little-endian)

| Bytes | All types |
|---|---|
| 0-1 | magic "WF" |
| 2 | record type (1 to 7) |
| 3 | flags0 (FIX/NOFIX: epoch age / 10 ms, 0xFF = not applicable; SESSION_START format 2: start reason) |
| 4-7 | seq (u32) |
| 8-11 | mono_ms (u32) |
| 12-43 | type-specific payload (see `wfg_record.h`) |
| 44-47 | CRC-32 (IEEE, same as zlib `crc32`) of bytes 0-43 |

FIX/NOFIX payload: utc_date u32 YYYYMMDD, utc_ms_of_day u32, lat_e7 i32, lon_e7 i32, alt_cm i32, speed_cmps u16,
course_cdeg u16, hdop_x100 u16, sats u8, gga_quality u8, fix_type u8, nofix_reason u8, validity bits u16
(time, date, pos, alt, speed, course, hdop, sats, RMC active, raw NMEA, fix type, checksum error).
STATUS payload (format 2): vbat_mv u16 (0xFFFF unknown) @12, vbat_pin_mv u16 @14, vbat_factor_x1000 u16 @16,
flags u8 @18, reserved @19, fs_free_bytes u32 @20, fs_total_bytes u32 @24, nmea_ok u32 @28,
nmea_checksum_errors u32 @32, free_heap u32 @36, reserved @40-43.
A field is only meaningful when its validity bit is set; the exporters leave it empty otherwise. `0xFFFFFFFF` means
"none" in u32 reference fields.

Integrity: each record is checked on its own (CRC); the whole file is checked by SESSION_END counts and CRC; the
export as a whole by SHA-256 (shown on the phone page and written to `.wfg.sha256` by `usb_export.py`).

## 8. Owner annotations (added later on phone or PC, not on the device)

Proposed file `<session_id>_annotations.csv`, never merged into the device CSV:

```
session_id,target,target_ref,field,value,annotated_by,annotated_utc,note
WFG-1A2B3C4D-000001,event,2,observation,"smoke visible to the north",owner,2026-10-04T10:00:00Z,
WFG-1A2B3C4D-000001,session,,movement_mode_correction,VEHICLE,owner,2026-10-04T10:01:00Z,"forgot to switch mode"
WFG-1A2B3C4D-000001,seq_range,120-180,exclude_from_routing,true,owner,2026-10-04T10:02:00Z,"inside a building"
```

`target` is `session`, `event` (by `event_no`) or `seq_range`. The original `movement_mode` stays as recorded; a
correction is a separate, attributed line.

## 9. Joining with the existing vehicle-routing work (without changing it)

- This logger only adds new files. It does not edit, re-label or change the eligibility of any existing routing
  dataset or frozen experiment.
- Join key: `session_id` (plus `seq` for single points). Keep a small registry table, for example
  `route_logger_sessions.csv` with `session_id, movement_mode, mode_source, start_utc_est, end_reason,
  fix_points, pct_nofix_time, max_recording_gap_s, sha256, exported_utc`, in a new folder beside the routing work.
- Auto-resumed sessions (`session_start_reason = AUTO_RESUMED_AFTER_RESET`) are listed as their own sessions, with
  `resumed_from_session_id` pointing at the cut one. Treat the pair as one trip only by an explicit, documented
  analysis step; never rewrite either file.
- Split strictly by `movement_mode`: VEHICLE sessions may be compared with vehicle-routing outputs; WALK sessions
  form a separate walking set and must not be mixed into vehicle training or evaluation. UNKNOWN sessions are kept
  out of both until the owner adds a mode annotation.
- Any map matching is a derived layer with its own file that references `session_id` + `seq`; the original lat/lon
  stay untouched.
- A recorded route shows where someone travelled. It is not evidence that the route was safe, optimal, passable for
  other vehicles, or free of heat or fire hazard, and it must not be labelled that way.
- Quality filters (for example "exclude fixes with sats < 4" or "exclude HDOP > 5") are analysis choices to be
  documented in the analysis, not applied in the logger. HDOP thresholds are not metre thresholds.

## 10. Privacy and consent

The files are precise location histories of a person. They stay on the device and the owner's phone or PC; nothing
is uploaded by this system. The Wi-Fi export network exists only while the owner holds the device in export mode
(10 minutes without a client at most). Each time, the device makes a new random network name and a new random
10-character WPA2 password and shows them only on its screen; neither is derived from the chip ID. This keeps
casual nearby devices out but is not strong protection against a determined attacker, so export in a private
place. Anyone else carrying the logger must agree first, and their sessions should be marked in annotations.
Share only the derived, agreed subsets.
