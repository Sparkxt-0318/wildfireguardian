# WildfireGuardian field route logger: firmware

Firmware lane output, written 2026-10-03 (Asia/Shanghai), revised the same night for review rows R3, R4, R7, R8,
R10, R19, R23, R24 (firmware 0.2.0, record format version 2; format 1 files are still read). Records travelled routes (GNSS positions, not audio or
video) to the board's internal flash, with no phone needed while recording. Export is over USB serial (mandatory
fallback) or a Wi-Fi download page on the phone.

## Verification status (read this first)

| What | Status | Evidence |
|---|---|---|
| Firmware compile, 5 environments (tracker_v2, tracker_v11, tracker_v10, generic_esp32s3, fallback_fb2e) | PASS, 0 compiler warnings | `build_evidence/pio_build_summary.txt`, `build_evidence/pio_run_all_envs.log` |
| Host unit tests, C++ core (record codec, CRC, SHA-256, NMEA parser, session logger, torn-tail recovery, storage-full, export confirmation, button decoder, USB protocol, 150 sessions with recovery past #64, auto-resume decision + attribution, STATUS records, reading format v1 files) | 592 checks passed, 0 failed (built with AddressSanitizer + UBSan) | `build_evidence/host_tests.log` |
| Python host tests (usb_export.py byte-identical to firmware converters incl. an auto-resumed session, format v1 file still decodes, integrity checker, end-to-end USB protocol through a pseudo-terminal with the real C++ protocol code) | 31 passed, 0 failed | same log |
| Headless Chromium tests (viewer.html stats incl. battery STATUS and old v1 CSVs; device page JS SHA-256 + CRC check and confirm flow against a mock HTTP device) | 23 passed, 0 failed | `../phone_export/tests/test_pages_browser.py`, screenshots in `../phone_export/samples/screenshots/` |
| Flashing, GNSS reception, TFT, button, battery, Wi-Fi on a real phone | NOT DONE. No hardware here. | See "Physical tests still required" |

"Host/simulated" means the hardware-independent code ran on Linux against a simulated filesystem and synthetic NMEA.
It does not prove the ESP32 LittleFS driver, the UC6580 output, the panel or the phone behave as assumed.

## Target hardware

| Env | Board | Role | Flash |
|---|---|---|---|
| `tracker_v2` (default) | Heltec Wireless Tracker V2 (PCB "V2.3", bracket "Rev. 2.0") | PRIMARY (sourcing lane decision) | 8 MB (ESP32-S3FN8) |
| `tracker_v11` | Heltec Wireless Tracker V1.1 | same-family alternate | 8 MB |
| `tracker_v10` | Heltec Wireless Tracker V1.0 | do not buy; only for a board delivered by mistake | 8 MB |
| `fallback_fb2e` | DFRobot FireBeetle 2 ESP32-E + Gravity GNSS TEL0157 + GDI TFT | FALLBACK (sourcing lane decision) | 4 MB, uses `partitions_4MB.csv` |
| `generic_esp32s3` | any ESP32-S3 N8 dev board + UART GNSS | template | 8 MB |

All board-specific values are in exactly one header per board in `include/`, each value with its source:
`board_heltec_tracker_v2.h`, `board_heltec_tracker_v11.h`, `board_heltec_tracker_v10.h`,
`board_firebeetle2_esp32e_tel0157.h`, `board_generic_esp32s3_uart_gnss.h`. `include/board.h` selects one from the
build flag. The logging core in `lib/wfg_core/` contains no pin numbers and no Arduino calls; a new board needs only a
new header plus a `[env:...]` block.

## Pin map (Heltec Wireless Tracker)

| Function | V2 (primary) | V1.1 | V1.0 | Sources |
|---|---|---|---|---|
| USER/PRG button (strap pin) | GPIO0, active LOW | GPIO0, active LOW | GPIO0 | V2 DS p.9, V1.1 DS p.6, Meshtastic `BUTTON_PIN 0` |
| Vext (GNSS + LNA + TFT power) | GPIO3, HIGH = on | GPIO3, HIGH = on | GPIO3, LOW = on | Heltec update log, Meshtastic variants |
| GNSS enable | (none) | (none) | GPIO37, LOW = on | Meshtastic V1_0 variant |
| TFT power | (via Vext) | (via Vext) | GPIO46, LOW = on | Meshtastic V1_0 `VTFT_CTRL 46` |
| GNSS UART: ESP RX / ESP TX | 33 / 34 | 33 / 34 | 33 / 34 | DS pin tables, Meshtastic, Heltec GPS example |
| GNSS baud | 115200 | 115200 | 115200 | Meshtastic `GPS_BAUDRATE`, Heltec example |
| GNSS reset (active LOW) / PPS | 35 / 36 | 35 / 36 | 35 / 36 | DS, Meshtastic |
| TFT CS / RST / DC / SCLK / MOSI | 38 / 39 / 40 / 41 / 42 | same | same | DS, Meshtastic, Heltec `HT_st7735.h` |
| TFT backlight (LED_K) | GPIO21 | GPIO21 | GPIO45 | DS, Meshtastic |
| TFT offset X / Y, invert | 24 / 0, no invert | 26 / -1, invert | 26 / -1, invert | Meshtastic variants, Heltec lib (V2 invert off) |
| Battery ADC / divider enable | GPIO1 / GPIO2 (pull-up = on) | GPIO1 / GPIO2 | GPIO1 / none | DS, Meshtastic `ADC_CTRL`, `ADC_USE_PULLUP` |
| White LED (kept off) | GPIO18 | GPIO18 | GPIO18 | DS |
| SX1262 LoRa (unused, put to sleep) | CS 8, SCK 9, MOSI 10, MISO 11, RST 12, BUSY 13 | same | same | Meshtastic |
| LoRa FEM LDO (V2 only, driven LOW) | GPIO7 | n/a | n/a | Meshtastic V2 `LORA_PA_POWER 7` |

Pins never used by this firmware: none needed beyond the above; no external wiring on the Heltec builds.

## Wiring and power (Heltec build: no wiring, no solder)

```
                 USB-C (charge + data: flashing, USB export)
                    |
  +-----------------v-------------------------------------------+
  |  Heltec Wireless Tracker V2                                  |
  |  CN3165 charger (V2) / TP4054 (V1.1)  <---- SH1.25 2-pin "Bat" socket <---- 1S LiPo with protection PCB
  |                                             (check + / - against board silkscreen BEFORE plugging in)
  |  ESP32-S3FN8  --GPIO3 HIGH--> Vext 3.3 V --> UC6580 GNSS + LNA, ST7735S TFT
  |      |  UART1 RX33/TX34 <------ NMEA 115200 ------ UC6580 <--- onboard GNSS antenna
  |      |  SPI3 38-42 -----------> 0.96" 160x80 TFT (backlight GPIO21)
  |      |  GPIO0 <--- PRG/USER button (pressed by printed plunger in the enclosure)
  |      |  GPIO1 <--- VBAT divider (enabled by GPIO2)
  |      |  internal 8 MB flash: 1.5 MB app + 6.44 MB LittleFS (session files)
  |  SX1262 LoRa: unused, put into sleep; antenna connector left empty (do not transmit)
  +--------------------------------------------------------------+
```

Do not connect a battery to the "Solar" socket. Do not run the LoRa radio without an antenna; this firmware never
transmits on LoRa.

## Button and GPIO0 boot-strap behaviour

GPIO0 is an ESP32-S3 strapping pin. Espressif: "The ESP32-S3 will enter the serial bootloader when GPIO0 is held low
on reset", it has an internal pull-up, and in normal boot (GPIO0 high) GPIO46 is ignored
(https://docs.espressif.com/projects/esptool/en/latest/esp32s3/advanced-topics/boot-mode-selection.html).

Consequences built into the design:
- The firmware never requires holding the button at power-up or reset.
- If the button is held while the board resets or the battery is connected, the chip enters ROM download mode: the
  screen stays dark and nothing records. Release the button and press RST (or unplug/replug). The enclosure
  plunger must not rest on the button (design a free gap and a return spring/flexure, as the CAD lane specifies).
- If firmware does start with the button already down, `wfg::Button::begin()` locks it out until release, so a stuck
  plunger cannot start, stop or delete anything (host-tested).
- The enclosure button is the board's own USER/PRG switch, pressed through a printed plunger. No extra button.
- The RST button must stay recessed (no plunger), so it cannot be hit accidentally while recording.

Gestures (one button):

| State | Short press (< 2.5 s) | Hold 2.5 to 6 s (countdown bar on screen) | Hold over 6 s |
|---|---|---|---|
| IDLE | first press wakes the screen; next presses cycle mode WALK, VEHICLE, UNKNOWN | start recording | enter Wi-Fi export mode |
| RECORDING | event marker (works with the screen off) | **stop recording** | stop recording |
| EXPORT | none | confirm a pending delete | leave export mode |
| any, delete pending | none | confirm the delete | confirm the delete |

**A 2.5 s hold stops recording.** Start and stop both act on RELEASE after the hold (the screen shows a countdown
bar, then "release: STOP REC"), never while the button is still down, so a press against a strap or pocket that
is held and then released after 2.5 s does stop the session. The CAD lane is making the plunger nearly flush with a
guard ring for that reason, and the reset a recessed pin hole. If recording stops by accident, a new hold starts a
new session; nothing is lost.

Mode is chosen before starting and is stored once in the session header; it cannot change mid-session. Double-press
detection exists in the decoder but is not used, to keep event marks instant.

### Auto-resume after an unexpected reset (review R3)

When a session starts, the firmware stores "recording active, mode, session number" in NVS (Preferences). Every
clean end clears it: owner stop, STORAGE_FULL, LOW_BATTERY, filesystem error. If the board resets while the flag is
set (brownout, battery connector bounce, watchdog, crash, RST pin), boot recovery closes the cut session as
RECOVERED_ON_BOOT as before, and then the firmware **starts a NEW session with the same movement mode**. Its
SESSION_START carries `start_reason = AUTO_RESUMED_AFTER_RESET`, `resumed_from_session_no` and the ESP reset reason.
Every exported row of it shows `session_start_reason` and `resumed_from_session_id`. Sessions are never merged.
The screen shows "AUTO-RESUMED after reset" and "RESUMED" next to the session number.

Guards (`lib/wfg_core/src/wfg_resume.h`, host-tested): no resume if the filesystem is not mounted (flag kept), if
storage is full, or if the battery reads below the low-battery stop level. After 3 auto-resumes in a row that each
die within 60 s, it stops resuming ("RESET LOOP: not resuming"). Side effect to know: if the battery runs flat
without a LOW_BATTERY stop (for example the cell's protection cuts out first), the next power-on will start
recording again. Hold 2.5 s to stop it.

## Logging rate: why 1 Hz

- GNSS rate: the UC6580 supports up to 10 Hz (V1.1 and V2 datasheets, "Update frequency Max 10 Hz"). The factory
  output rate is UNVERIFIED; it is expected to be 1 Hz. The firmware does not reconfigure the receiver. It logs
  one row per GNSS epoch and drops extra epochs if the receiver runs faster than 1 Hz.
- Usefulness: walking is about 1.4 m/s and vehicles 10 to 30 m/s. At 1 Hz a vehicle moves 10 to 30 m between
  points, which is still enough to follow streets for later routing work.
- Storage: a record is 48 bytes, so 1 Hz is 172,800 bytes per hour, or 6.07 hours per MiB.
- Using the full LittleFS partition (6,750,208 bytes in `partitions.csv`), minus about 3 % filesystem metadata and a
  32 KiB reserve: about 37.7 hours of continuous recording on 8 MB boards and about 14 hours on the 4 MB fallback.
  There is no session or file-size cap. The ~37 h figure is an estimate, not a measurement.
- Power: the GNSS draws a lot more current than the logging does. The V2 datasheet lists "GNSS 127 mA" on battery
  (whole board, conditions not stated). Writing 48 bytes per second and fsyncing every 5 s adds very little. A
  10 Hz rate would cut storage to about 3.8 h and add CPU/flash wear without helping the routing work.
- Battery, not storage, is the limit. **Planning figure: plan on 5-6 h on an 800 mAh cell until measured.** The
  component-sum estimate of 8-10 h (screen off most of the time, GNSS-dominated draw) is optimistic and is not to
  be used for planning. The STATUS records (battery mV every 60 s) make the measurement possible from the session
  file itself.
- STATUS records add one 48-byte record per 60 s (0.08 % extra), which does not change the ~37.7 h estimate.
- Raw NMEA: storing every sentence would cost about 1 kB/s (about 1.9 h on 8 MB), so v1 stores decoded fields
  only. `raw_nmea_available` is always 0 in this version; the schema keeps the flag for a later optional sidecar.

## Partitions (8 MB)

`partitions.csv` (decoded from the built `partitions.bin` in `build_evidence/`):

| Name | Type | Offset | Size |
|---|---|---|---|
| nvs | data/nvs | 0x9000 | 20 KB (stores movement mode only) |
| factory | app | 0x10000 | 1536 KB (firmware uses 958 KB, 61 %) |
| spiffs (LittleFS) | data/spiffs | 0x190000 | 6592 KB |

No OTA slot and no otadata: flashing is over USB only, so the space goes to LittleFS. The partition label stays
`spiffs` because that is what Arduino `LittleFS.begin()` uses by default. Flash size: V1.0, V1.1 and V2 all use the
ESP32-S3FN8 (8 MB in package) per their datasheets; no difference between revisions was found. At boot the firmware
compares `ESP.getFlashChipSize()` to the header's `WFG_FLASH_MB` and shows "FLASH SIZE MISMATCH" if it is smaller.
The 4 MB FireBeetle fallback uses `partitions_4MB.csv` (2496 KB LittleFS).

## Storage robustness

- One append-only file per session, `S000001.wfg`, `S000002.wfg`, ... Fixed 48-byte binary records, each with magic
  "WF" and its own CRC-32. Format in `../firmware/DATA_SCHEMA_draft.md`.
- Session numbers are never reused, even if `meta.txt` is lost (the highest existing number is scanned at boot).
- First record SESSION_START (header), last record SESSION_END (footer) holding counts and a CRC-32 over all earlier
  bytes.
- fsync every 5 s and immediately after every event marker. A power cut loses at most about 5 rows.
- Boot recovery: every session without a valid SESSION_END is scanned, any torn partial record at the end is cut off,
  and a SESSION_END with reason RECOVERED_ON_BOOT and the number of torn bytes removed is appended. A file whose
  first record is unreadable is renamed `.bad` and kept, never deleted. Host-tested (`test_torn_tail_recovery`).
- Storage full: free space is checked as recording goes. Below the reserve, recording stops cleanly with
  SESSION_END reason STORAGE_FULL and the screen shows FULL. A hard short write (ENOSPC) cuts the partial record and
  closes the session. New sessions are refused while full. Nothing is ever overwritten or auto-deleted.
  Host-tested (`test_storage_full`).
- No count limit anywhere (review R4): boot recovery, USB LIST, the phone page list and the unexported count all
  walk every `S??????.wfg` file in session-number order. Only the session numbers (4 bytes each) are held in RAM
  while walking. Host-tested with 150 sessions, two of them damaged past the old 64-file mark.
- Deletion needs all of these: the session is closed; the phone page or `usb_export.py` downloaded it and its SHA-256
  matched the device's; that hash was sent back (`CONFIRM`), so a `.ok` marker holding it is written; a delete
  request with the same hash; and the owner holds the device button 2.5 s within 30 s. If the file changes after
  confirmation, the confirmation no longer counts.
- Integrity check: `Logger::checkSession()` (USB `CHECK S000001.wfg`, also `usb_export.py verify FILE.wfg`) reports
  OK, RECOVERED, OPEN, TORN_TAIL or CORRUPT with CRC and sequence error counts.
- LittleFS mount failure: the firmware formats only if the partition is completely blank (first flash). Otherwise it
  shows "FS ERROR" and waits. Erasing all data needs the explicit USB command `FORMAT ERASE-ALL-SESSIONS`.

## Wi-Fi export credentials (review R19)

Every time export mode is entered, the firmware makes a new random SSID suffix (`WFG-LOGGER-` + 4 characters) and a
new random 10-character WPA2 password (`esp_random()`, alphabet without 0/O/1/l/I). Neither is derived from the chip
ID. They are shown only on the device screen and change on the next entry. WPA2 with a 10-character random password
keeps casual nearby phones out while the AP is up (10 minutes without a client at most); it is not a guarantee
against a determined attacker who captures the handshake. Exports should be done in a private place.

## Screen

Line 1: state (IDLE / REC with blinking dot / FULL / EXPORT / FS ERR), movement mode, number of unexported sessions.
Line 2: GNSS (no data / NO FIX with satellites / 2D or 3D, satellites, HDOP shown as a plain unitless number).
Line 3: battery % and volts. Line 4: storage used % and estimated hours left at 1 Hz. Line 5: session number and
record count, or the Wi-Fi name and password in export mode. Line 6: last event (number, located or NO POS, age).
Bottom bar: hold countdown or messages. The screen turns off after 30 s without a press (except in export mode);
any press turns it on. The first short press in IDLE only wakes it. In RECORDING a short press always marks an event
even with the screen off.

## Battery measurement and calibration (review R7, R10)

- Battery voltage = ADC pin mV (`analogReadMilliVolts`, eFuse-calibrated, default 11 dB attenuation) x **4.900**
  (nominal 390k/100k divider) x owner calibration constant (default **1.000**, stored in NVS). Meshtastic's extra
  x1.045 belongs to its 2.5 dB attenuation setting and is not used here. **UNVERIFIED until calibrated.**
- Low-battery clean stop: **3400 mV**, 3 consecutive readings 10 s apart, session ends with LOW_BATTERY. Also
  UNVERIFIED until calibrated; the cell's protection cut-off voltage is not known.
- Calibration, about 2 minutes with a multimeter:
  1. Battery connected, USB unplugged if possible (USB charging raises the voltage). Connect USB only for the
     serial link, then measure quickly, or use a USB data cable through a power-only switch.
  2. Send `VBAT` over USB: replies `OK VBAT pin_mv=... factor=4.900 cal=1.000 vbat_mv=...`.
  3. Measure the battery at the cell's plug pins with the multimeter (mV), e.g. 3987.
  4. Send `CALVBAT 3987`. The firmware sets cal = measured / (pin_mv x 4.9), accepted only between 0.800 and
     1.200, stores it in NVS and replies `OK CALVBAT cal=... vbat_mv=...`. `CALVBAT RESET` returns to 1.000.
  5. Repeat `VBAT` at a second level (full about 4.1 V, then about 3.7 V) and note both errors; if they differ by
     more than 50 mV the single-factor model is not good enough and the threshold should be raised.
- STATUS record every 60 s while recording (and once at start): battery mV, raw pin mV, the factor used, storage
  free/total bytes, NMEA sentence counters, screen/GNSS flags. Runtime = first to last STATUS/END mono_ms in the
  file, with the voltage curve alongside. These are CSV rows (`record_type=STATUS`), not part of the track.

## Build and flash on macOS (M4 MacBook, Apple Silicon)

All toolchain packages used here exist for `darwin_arm64` in the PlatformIO registry (checked 2026-10-03:
toolchain-xtensa-esp32s3 8.4.0+2021r2-patch5, tool-mklittlefs 1.203.210628). Steps not run on a Mac here.

```bash
# 1. PlatformIO Core. Homebrew Python refuses `pip install --user` (PEP 668), so use a virtual environment:
python3 -m venv ~/wfg-venv
source ~/wfg-venv/bin/activate                       # run this in every new terminal
pip install platformio==6.2.0 pyserial==3.5
pio --version                                        # expect 6.2.0
#    Alternative: `brew install platformio` (Homebrew's version, may be newer than 6.2.0; the pinned
#    espressif32@6.9.0 platform in platformio.ini still fixes the toolchain) and `pip install pyserial` in the venv.

# 2. Build (first build downloads about 1 GB; in mainland China this can be slow, retry if it times out)
cd firmware
pio run -e tracker_v2            # or tracker_v11 if a V1.1 board arrived

# 3. Connect the board with a USB-C DATA cable, find the port
ls /dev/cu.usbmodem*             # native USB of the ESP32-S3, e.g. /dev/cu.usbmodem1101

# 4. Flash
pio run -e tracker_v2 -t upload --upload-port /dev/cu.usbmodem1101
#   If upload fails with "No serial data received" or the port does not appear:
#   hold PRG/USER, press and release RST, release PRG (download mode), then run the upload again,
#   then press RST once afterwards to start the firmware.

# 5. Watch the log / talk to it
pio device monitor -p /dev/cu.usbmodem1101 -b 115200     # type HELLO and press Enter
```

The FireBeetle fallback uses a USB-UART bridge; its port is `/dev/cu.usbserial-*` or `/dev/cu.wchusbserial*`.

Host tests on the Mac (Xcode command line tools provide clang++; ASan works there):
```bash
CXX=clang++ bash firmware/test/host/run_host_tests.sh
pip install playwright && python3 -m playwright install chromium   # optional, inside the venv
python3 phone_export/tests/test_pages_browser.py
```

If `web/device_page.html` is edited, run `python3 tools/embed_page.py` to regenerate `src/web_page.h`.

## Dependency versions (pinned)

| Item | Version |
|---|---|
| PlatformIO Core | 6.2.0 |
| platform espressif32 | 6.9.0 |
| framework-arduinoespressif32 | 3.20017.241212 (Arduino-ESP32 2.0.17, ESP-IDF 4.4.x) |
| toolchain-xtensa-esp32s3 | 8.4.0+2021r2-patch5 |
| LovyanGFX | 1.2.7 (lovyan03/LovyanGFX) |
| LittleFS, WiFi, WebServer, Preferences | bundled with the Arduino core above |
| NMEA parser | own (`lib/wfg_core/src/wfg_nmea.cpp`), no TinyGPSPlus |
| Host: pyserial 3.5; Playwright (optional, browser tests only) | |

The board definition `boards/heltec_wireless_tracker_wfg.json` is a local copy of Meshtastic's
`boards/heltec_wireless_tracker.json` (espressif32 6.9.0 has no Heltec Tracker board), with the generic esp32s3
variant so no Heltec-specific pins_arduino.h is needed.

## USB protocol (115200, line based)

`HELLO`, `STATUS`, `LIST`, `CHECK <name>`, `DUMP <name>`, `CONFIRM <name> <sha256>`, `DELETE <name> <sha256>`,
plus `VBAT`, `CALVBAT <mV>|RESET` (battery calibration) and `FORMAT ERASE-ALL-SESSIONS`.
Full description in `lib/wfg_core/src/wfg_proto.h`. Lines starting with `#` are log lines. DUMP, LIST and CHECK are
refused while recording, so a transfer can never starve the GNSS UART. Host tool: `../phone_export/usb_export.py`.

## Files

```
platformio.ini, partitions.csv, partitions_4MB.csv, boards/heltec_wireless_tracker_wfg.json
include/board.h + one board_*.h per board/revision
lib/wfg_core/src/   wfg_record (48-byte records, CRC-32), wfg_nmea (parser), wfg_logger (sessions, recovery,
                    storage-full, export confirmation, delete guard), wfg_export (CSV/GPX/GeoJSON), wfg_sha256,
                    wfg_button (gesture decoder), wfg_proto (USB protocol), wfg_storage (POSIX/LittleFS VFS),
                    wfg_resume (auto-resume decision)
src/main.cpp        hardware glue: power rails, UART, button, battery, screen timeout, USB, Wi-Fi mode
src/display.*       status screen (LovyanGFX)
src/web_export.*    SoftAP + HTTP API + streaming downloads; src/web_page.h generated from web/device_page.html
test/host/          test_core.cpp (C++ unit tests), fake_device.cpp (USB protocol over stdio), run_host_tests.sh
build_evidence/     compile logs, firmware sizes and hashes, decoded partition table, host test log
DATA_SCHEMA_draft.md
```

## UNVERIFIED items (need the delivered hardware)

1. Board revision actually delivered (V2 vs V1.1); flash the matching env.
2. TFT: X/Y offset (V2 24/0, V1.1 26/-1), colour inversion, rotation (set 1; use 3 if upside down in the
   housing), backlight polarity on GPIO21 (HIGH assumed on, from the Heltec library). Wrong offset shows a stripe
   of garbage pixels on one edge.
3. Button: active-LOW on GPIO0 (V2 from the sourcing lane's schematic reading; V2 schematic URL returned "Not Found"
   for this lane). Plunger travel and that it never rests on the switch.
4. Download-mode trap: holding the plunger during battery connect or reset gives a dark screen (expected chip
   behaviour, not a firmware fault).
5. UC6580 factory output: baud 115200, rate 1 Hz, which sentences (GGA, RMC, GSA expected; talker GN/GP/GB).
   Altitude field is MSL from GGA. Time-to-first-fix indoors/outdoors.
6. Battery ADC: factor 4.9 x calibration 1.000 and the LiPo % curve; calibrate with `CALVBAT`.
   Low-battery stop at 3400 mV (3 readings, 30 s); the cell's protection cut-off is unknown.
7. Current draw in each state (record, idle, screen off, export), and whether SX1262 sleep and FEM-LDO-off
   actually save current. Battery life must be measured, not taken from the 5 to 6 h estimate.
8. LittleFS on the real chip: mount, `truncate()` (the ESP-IDF LittleFS VFS in this core exports
   `vfs_littlefs_truncate`; a copy-and-rename fallback exists), free-space reporting, write speed. Long runs
   (several hours) and repeated power cuts during recording.
9. Wi-Fi export on the owner's phone: join WPA2 AP, iOS "no internet" handling, download and Save to Files, transfer
   speed for a multi-hour session.
10. GPIO3 Vext switches TFT and GNSS together, so the GNSS stays powered while the screen is off (wanted).
11. Auto-resume on real resets: brownout behaviour with a weak cell, and that `esp_reset_reason()` reports what
    the owner expects (the RST pin and a battery reconnect both show POWERON).
12. Wi-Fi: `esp_random()` is a true RNG only with the radio on; the credentials are generated after
    `WiFi.mode(WIFI_AP)` for that reason (per ESP-IDF docs, not measured).
13. FireBeetle fallback: every GDI and UART pin, GNSS baud (9600 assumed), ST7789 controller, battery ADC pin.

## Physical tests still required (none could be done here)

Flash and boot; screen readable, offsets right; button gestures including hold countdown; first fix outdoors with
time; walking session 15 min with event marks; vehicle session; pull the battery mid-recording then check
RECOVERED; fill test (temporarily set a large `reserve_bytes` to reach FULL quickly); USB export on the Mac; Wi-Fi
export on the owner's phone; battery runtime from full to stop with a USB power meter or periodic voltage log.
