# Firmware 0.3.0: LIVE lines over USB

Written 2026-10-08 (Asia/Shanghai). `firmware_v0_3_0_live/` is a full copy of `firmware/` (0.2.0) with the changes
below; `firmware/` itself is unchanged. The record format stays version 2 (no layout change): a session written by
0.3.0 differs from a 0.2.0 one only in the firmware version field of SESSION_START (3 instead of 2). Source diff:
`firmware_0.2.0_to_0.3.0.diff` (unified, `build_evidence/` excluded).

## What changed and why

1. **LIVE lines** (DEMO_SPEC section 5, milestone M2), so a laptop can follow the device while it records; until now
   DUMP, LIST and CHECK only work after recording stops. New hardware-independent module
   `lib/wfg_core/src/wfg_live.h/.cpp`: the commands `LIVE ON`, `LIVE OFF`, `LIVE NMEA ON`, `LIVE NMEA OFF` and their
   replies, the formatters of the eight line types (`ep`, `rec`, `st`, `ev`, `ss`, `se`, `drop`, `#N`), the drop rule,
   a collector that turns the bytes read from the GNSS UART into whole sentences for `#N`, and an estimate of the UART
   transmit queue (item 4). `src/main.cpp` and the host fake device use the same code. LIVE is off after every boot,
   so `usb_export.py` and the phone page behave exactly as with 0.2.0 unless a host sends `LIVE ON`. Formats, fields,
   order and the drop rule: README, "LIVE lines (0.3.0)".
2. **Record observer in the logger** (`Logger::setRecordObserver`): called after every record written to the current
   session file, with the 48 bytes, the seq and the file size after the write. It is also called for the SESSION_END
   that `append()` writes by itself after a short write (storage full). It is not called for the END records boot
   recovery adds to older files (at boot LIVE is off, and after `FORMAT` there is nothing to recover). Nothing else in
   the logger changed: the 0.2.0 host tests, unchanged, all pass, and the sample sessions they write are
   byte-identical to the 0.2.0 samples.
3. **`src/main.cpp`**
   - `Serial.setTxBufferSize(4096)` before `Serial.begin(115200)`, per serial class (checked in the Arduino-ESP32
     2.0.17 headers and sources in the PlatformIO cache): HardwareSerial on the classic ESP32 (FireBeetle) gets a
     4096-byte transmit ring buffer instead of only the 128-byte UART FIFO; HWCDC (USB-Serial-JTAG, all ESP32-S3
     envs) has the same call with the same meaning (its ring buffer, 256 bytes by default); TinyUSB CDC (USBCDC, used
     by no env here) has no `setTxBufferSize()` in 2.0.17 and is left alone. Guarded with `ARDUINO_USB_CDC_ON_BOOT`
     and `ARDUINO_USB_MODE`, the same macros the core uses to pick the class of `Serial`.
   - `handleSerial()`: LIVE commands are handled after the `ERR FS not-mounted` check and after the DUMP/LIST/CHECK
     refusal, before `Proto::handleLine()`. So `LIVE ON` works while recording, and with a broken filesystem it
     answers `ERR FS not-mounted` like every other command except VBAT, CALVBAT and FORMAT.
   - `ep` at both places in `loop()` where epochs are taken, written just before `Logger::onEpoch()`; `#N` from the
     collector, which sees every byte read from Serial1; `rec`, and `st` for STATUS records, through the observer;
     `st` every 10 s while not recording (battery reading of that moment and free space, the latter only computed
     while LIVE is on); `ev` after a successful mark; `ss` in `startSession()` (owner start and auto-resume); `se`
     checked after the owner stop, after the low-battery stop, after a mark and once per loop pass after the GNSS and
     `tick()` calls, so a session the logger ends by itself (storage full) also gets its `se`.
   - `#` banner lines, protocol replies and button behaviour are unchanged.
4. **Transmit queue estimate on the classic ESP32.** The spec relies on `availableForWrite()`. In Arduino-ESP32 2.0.17
   on the classic ESP32 it returns ESP-IDF's `uart_get_tx_buffer_free_size()`. Disassembling that function in the
   cached framework (`tools/sdk/esp32/lib/libdriver.a`, `uart.c.obj`) shows it returns `tx_buf_size - tx_len_tot`,
   and the UART interrupt handler sets `tx_len_tot` to the size of the one write it is sending and counts it down.
   Writes queued behind that one are not counted, so the value can be far too high, and a write that does not fit
   waits until the UART has sent enough. The UART has no flow control and keeps sending at 115200 baud whether or not
   a host listens, so `main.cpp` also keeps an estimate of the LIVE bytes it queued (`wfg::TxQueueModel`) and LIVE
   uses the smaller of the two values: at most 3072 of the 4096 bytes (the rest stays for protocol replies, `#`
   messages and the ring buffer's per-write headers), 32 bytes counted per write on top of the line, drained at
   5760 bytes/s (half the line rate, to allow for flash operations that hold off the UART interrupt). These constants
   were chosen on paper. At the expected load (about 1.5 kB/s with LIVE and NMEA on) the estimate stays far below the
   cap, so no lines should be dropped; a burst far above the line rate is dropped and counted instead of blocking (host
   test `tx_queue_model`). On the ESP32-S3 builds HWCDC reports its free space exactly; there LIVE leaves 512 bytes
   free for replies and `#` messages.
5. **FireBeetle board header**: `WFG_PIN_TFT_BL` 12 -> 13, because the display's BLK is wired to D7 = IO13
   (`../CAD_v2_firebeetle/instructions/PRINT_AND_ASSEMBLY_EN_ZH.md`, `../handoff_updates/PLAN_CHANGES_FOR_AGENT.md`
   section 9). IO12 is a strapping pin: the module pulls BLK up through 10 k, and IO12 high at boot selects 1.8 V flash,
   so the ESP32 does not start. No other pin changed.
6. **Version**: `WFG_FW_VERSION` 2 -> 3, `WFG_FW_VERSION_STR` "0.2.0" -> "0.3.0" (HELLO, the boot line, the phone
   page's status, SESSION_START). `WFG_FORMAT_VERSION` stays 2.
7. **Host fake device** (`test/host/fake_device.cpp`): accepts the LIVE commands through the shared parser and adds
   `!NMEA <sentence>` (fed byte by byte to the real NmeaParser; epochs go to `Logger::onEpoch` and to `ep`),
   `!START [WALK|VEHICLE|UNKNOWN]`, `!STOP` and `!MARK`, printing the `# REC ...`, `# STOPPED - saved` and
   `# EVENT n marked|(NO POSITION)` lines main.cpp prints. Like main.cpp it refuses DUMP, LIST and CHECK while
   recording, and it runs the epoch commit timeout, the gap filler, STATUS records and the delete-request expiry on the
   host clock. Unchanged: `# fake device ready` first, `!BUTTON_LONG`, `!QUIT`, and HELLO with its own board and
   firmware strings (`HOST-FAKE-DEVICE`, `0.1.0-host`).
8. **Tests**: new C++ host tests in `test/host/test_core.cpp` (see below) and a new end-to-end test of the fake
   device, `test/host/test_fake_device_live.py` (Python standard library only).
9. **`test/host/run_host_tests.sh`**: optional `WFG_SAMPLES_DIR` (default unchanged: `../phone_export/samples`),
   `python3 -B` so no `__pycache__` is written next to the sources, and it runs the new LIVE test.
10. **README**: protocol section with the LIVE commands, defaults, line formats and drop rule; version; BL pin 13.

## Verified on the host (simulated, no hardware)

Evidence: `build_evidence/host_tests_0.3.0.log`, `build_evidence/pio_build_summary_0.3.0.txt`,
`build_evidence/pio_run_all_envs_0.3.0.log`.

- C++ host tests (`run_host_tests.sh` flags: g++ 13.3, `-Wall -Wextra`, AddressSanitizer + UBSan): **868 checks
  passed, 0 failed, 0 compiler warnings**. New for 0.3.0:
  - every line format as exact strings: the spec's `ep` example byte for byte, an all-null `ep`, south/west
    coordinates, negative altitude, rounding to one decimal, 7-decimal coordinates from the e7 integers, course 359.95
    -> 0.0, `rec` (CRC hex with a leading zero kept), `st`, `ev`, `ss`, `se` (also with `"er":null`), `drop`, `#N`;
  - `ep` built from real NMEA sentences through the parser (fix, no fix, time without date);
  - the 320-byte limit: the longest possible line of each type (ep 250 bytes, rec 183, #N 104), a too-small buffer
    never gives a cut line, a line that cannot be sent is counted as dropped;
  - default off (nothing written, the sink is not even asked for space), NMEA only while LIVE is on, LIVE OFF keeps
    the NMEA setting;
  - the drop counter with a sink of limited space: lines dropped, a line that fits without its drop line dropped too,
    then one `drop` line with the right count followed by the line, then normal lines; a buffer that fills; a failing
    write; LIVE OFF clearing the count;
  - command replies, whitespace, case, and lines that are not LIVE commands;
  - the record observer on the logging core: the observed records equal the session file byte for byte, seq 0..n-1,
    file size after each write, also when storage runs out (END observed, `se` with STORAGE_FULL) and on a hard short
    write (END observed, or `"er":null` if the file had to stay open); the file is byte-identical with and without the
    observer; `ss`/`se` pairing including a missed end check;
  - the raw NMEA collector (CR/LF, noise before `$`, 100 characters pass and 101 do not, control and non-ASCII bytes,
    a sentence cut short by the next `$`) and the transmit queue estimate.
- The sample sessions written by the tests are byte-identical to the 0.2.0 samples in `../phone_export/samples` (the
  tests wrote into a copy; the package folder was not written to).
- `../phone_export/tests/test_usb_export.py` against the 0.3.0 fake device: **31 passed, 0 failed**.
- `test/host/test_fake_device_live.py`: **50 passed, 0 failed** (and 3 more runs, all passed): default off, LIVE
  commands while idle and while recording, `ep` keys in order and values, `#N` equal to the sentences sent, start
  (`rec` for START, CLOCK and STATUS, then `st`, `ss`, `# REC ...`), fixes while recording (`ep` before its row),
  mark, DUMP/LIST/CHECK refused while recording, gap-filler rows, stop (`rec` END, `se` with the record count,
  `# STOPPED - saved`), the `rec` lines rebuilding the session file byte for byte with correct `b`, `seq`, `crc` and
  `ty`, idle `st` every 10 s, silence after LIVE OFF, every line ASCII and at most 320 bytes.
- clang++ 18 without sanitizers (its ASan runtime is not installed in this workspace): 868 passed. One clang warning,
  in 0.2.0 code that was not touched: `wfg_logger.h` private field `start_written_utc_` is not used.
- PlatformIO (Core 6.2.0, espressif32 6.9.0, Arduino-ESP32 2.0.17), clean build of all five environments
  (tracker_v11, tracker_v2, tracker_v10, generic_esp32s3, fallback_fb2e): **all SUCCESS, 0 warnings**. LovyanGFX 1.2.7
  came from the local PlatformIO cache of the 0.2.0 build; nothing was downloaded. The `.pio` workspace was outside the
  package. Symbols in the ELF files confirm the per-class code: `HardwareSerial::setTxBufferSize` and the estimate in
  fallback_fb2e, `HWCDC::setTxBufferSize` in the ESP32-S3 builds. Static RAM grew by 544 to 592 bytes per env; the
  4096-byte transmit buffer comes from the heap at `Serial.begin()`.

## NOT verified on hardware

Nothing in 0.3.0 has been flashed or run on a board. Still open:

- **The 10-minute check of DEMO_SPEC section 5**: 10 minutes of recording with `LIVE ON` and `LIVE NMEA ON` must give
  no missing `seq`, no `drop` lines, and a FIX or NOFIX row at least every 1.6 s of `mono_ms` (every second once the
  receiver gives time; the gap filler writes one every 1.5 s before that). Not done.
- **The serial-open measurement of DEMO_SPEC section 5**: whether opening, closing, unplugging or reconnecting the
  port resets the FireBeetle, pyserial's default open compared with `dtr` and `rts` set to False before `open()`,
  while it records (a reset shows as a new session with AUTO_RESUMED_AFTER_RESET). Not done; 0.3.0 does not change
  anything here.
- The transmit buffer on the real UART: that the 4096-byte ring buffer is allocated, that the estimate's constants
  give no drops at the real load, and how long `Serial.flush()` (unchanged, after every protocol reply) waits when
  LIVE lines are queued: at most until the buffer is empty, about 0.36 s for a full 4096 bytes at 115200 baud and
  usually much less. Meanwhile GNSS bytes wait in Serial1's 4096-byte receive buffer, so none are lost, but sentences
  read after the wait get a later receive time. The 10-minute check covers this if it runs with the desktop app polling
  STATUS as it will in use.
- The backlight on IO13: that the screen turns off after 30 s and on with a press.
- The ESP32-S3 builds (HWCDC): compiled only.

Suggested way to run the 10-minute check (the desktop app's device log can replace the terminal):

1. In this folder: `pio run -e fallback_fb2e -t upload --upload-port /dev/cu.usbserial-XXXX`. `HELLO` must answer
   `fw=0.3.0`.
2. With a terminal that saves every line to a file, send `LIVE ON` and `LIVE NMEA ON`, start a recording with a
   2.5 s hold, wait 10 minutes (outdoors for FIX rows), stop with a 2.5 s hold, send `LIVE OFF`.
3. In the saved lines: the session's `rec` lines have `seq` 0, 1, 2, ... without a gap, the last one has `ty` 6 and the
   `se` line's `n` equals their count; there is no `drop` line; between consecutive rows of `ty` 2 or 3 the `mono_ms`
   (bytes 8..11 of `hx`, little-endian) never grows by more than 1600.
4. Pull the session as usual (`DUMP`, or `usb_export.py dump`) and compare it with the `hx` of the `rec` lines put
   together: they must be the same bytes.

## Notes

- LIVE is off after every reset, so an auto-resumed session has no `ss` line; the `ep` lines show its session number
  after `LIVE ON`, and its `se` comes when it ends.
- LIVE stays on until `LIVE OFF` or a reset. Closing the port or pulling the cable does not turn it off, so after a
  reconnect `#J` lines can arrive before the app sends `LIVE ON` again (which is harmless: `OK LIVE ON` again).
- Kept from 0.2.0 so replies stay byte-identical: while recording, `DUMP <name>` is refused with
  `ERR DUMP  recording-active (stop recording first)` with two spaces after DUMP (main.cpp prints the first five
  characters of the line). Hosts should match `ERR DUMP` as a prefix.
- `#N` forwards each sentence exactly as received, also with a bad checksum; the parser still checks checksums for
  the logging. Sentences longer than 100 characters or with bytes outside printable ASCII are not forwarded.
- `utc` in `ep` uses the same formatter as the CSV column `gnss_utc`, and `la`/`lo` the same as the CSV `lat`/`lon`.
- For the desktop app's tests (DEMO_SPEC section 3C and test 14): the 0.3.0 fake device answers `LIVE ON` with
  `OK LIVE ON` and can record (`!START`), so it serves the LIVE-mode tests. The basic-mode tests, which expect
  `ERR LIVE unknown-command` and a device that never records, need the fake device built from `../firmware/` (0.2.0).
