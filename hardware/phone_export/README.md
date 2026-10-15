# Phone and PC export

Export lane output, 2026-10-03. Nothing here needs a native app, an internet connection or a website. Nothing has
been tested on a real iPhone or Android phone yet (see "Status").

## Decision: Wi-Fi download page from the device, not Bluetooth

| | Web Bluetooth (BLE) | Device Wi-Fi access point + local web page (chosen) |
|---|---|---|
| iPhone | Not possible: Safari has no Web Bluetooth, and every iOS browser uses Safari's engine. Would need a native app. | Works in Safari; files can be saved to Files. |
| Android | Chrome supports Web Bluetooth, but only on a secure (HTTPS) page. The device cannot serve HTTPS offline, so the page would have to come from an internet website. That is a live-website dependency, which this project rules out. | Works in Chrome. |
| Speed for a 1 to 6 MB session | Slow (a few kB/s to tens of kB/s in browsers) | Fast (Wi-Fi) |
| Extra parts or apps | none, but a native iOS app would be essential | none |

So the device runs a WPA2 Wi-Fi access point only while the owner puts it into export mode, and serves a small page
over plain HTTP at `http://192.168.4.1/`.

Consequences that the page and firmware already handle:
- No HTTPS is possible offline, so browser APIs that need a secure context (for example `crypto.subtle`) are not
  used. The page has its own JavaScript SHA-256 and CRC-32.
- The access point has no internet. Phones may warn about this or try to switch away (details below).
- Downloads must be done with the page open and in the foreground. iOS suspends background pages, which would
  break a transfer. The page says so at the top.
- No captive-portal pop-up is used on purpose: the iOS captive-portal mini browser cannot save files. The owner opens
  Safari or Chrome and types the address.
- USB serial export (`usb_export.py`) is the always-available fallback and does not depend on any phone.

## What the device page does

1. Lists sessions (ID, mode, records, size, how it ended, export state).
2. For each closed session: Save raw `.wfg`, CSV, GPX, GeoJSON. For each file the page first asks the device for its
   SHA-256, downloads it, computes SHA-256 in the phone browser and compares. For `.wfg` it also checks every
   record's CRC-32. Only a matching file is handed to the browser to save; a mismatch says "Retry".
3. "Confirm export" (enabled only after the `.wfg` verified) sends that SHA-256 back. The device checks it against
   the file and writes an export confirmation.
4. "Delete from device..." (only for confirmed sessions) asks the device to delete. Nothing happens until the
   owner holds the device button for 2.5 s within 30 s. The phone copy is not touched.

Wi-Fi name and password are shown on the device screen in export mode: `WFG-LOGGER-` + 4 random characters and a
random 10-character password. Both are new every time export mode is entered (nothing is derived from the chip ID),
so the phone has to join a "new" network each time. Export mode switches itself off after 10 minutes with no phone
connected. WPA2 with a random password keeps casual nearby phones out; it is not strong protection against a
determined attacker, so export in a private place.

## iPhone steps (Safari)

1. On the device: from IDLE, hold the button more than 6 s (the bar says "release: EXPORT MODE"). The screen shows
   the Wi-Fi name and password.
2. iPhone Settings > Wi-Fi > choose `WFG-LOGGER-xxxx`, enter the password. iOS may show "No Internet Connection"
   under the network name. That is expected; stay on this network. If the iPhone switches back to another
   Wi-Fi, use "Forget" on that one temporarily or turn off Auto-Join for it.
3. Open Safari and type `192.168.4.1` (no https). Keep Safari in front and the screen on until done.
4. Tap "Save raw .wfg". When Safari asks, tap Download. Wait for "wfg verified" and the SHA-256 line. Then save
   CSV and GPX the same way (GeoJSON is optional).
5. Files are in the Files app > Downloads (or the folder set in Settings > Safari > Downloads).
6. Tap "Confirm export". Optionally "Delete from device..." and then hold the device button 2.5 s.
7. Leave export mode: hold the device button more than 6 s. Rejoin your normal Wi-Fi.
8. To look at the track: open `viewer.html` (keep a copy in Files), then pick the CSV. In Files, if tapping
   viewer.html only shows the source, use Share > open in Safari, or open it on a PC instead (UNVERIFIED which
   works on the owner's iOS version).

## Android steps (Chrome)

1. Put the device in export mode as above.
2. Settings > Wi-Fi > `WFG-LOGGER-xxxx`, enter the password. Android will say "No internet" or "Connected, no
   internet". If it asks "Stay connected?" or offers "Use this network without internet access", choose to stay /
   yes. Otherwise Android may keep using mobile data and the page will not load.
3. If 192.168.4.1 still does not open, turn off mobile data for the duration of the export (some phones send traffic
   over mobile data when Wi-Fi has no internet).
4. Chrome: type `http://192.168.4.1`. Keep Chrome in front.
5. Save `.wfg`, CSV, GPX as above; they land in Downloads. Recent Chrome versions may warn that a download from an
   http (not https) page is insecure, or "can't be downloaded securely". Tap **Keep** (or open the download list and
   choose Keep). This is expected on an offline device page; the page's SHA-256 check is what proves the file is
   intact. Desktop Chrome can show the same prompt. Confirm export; optionally delete.
6. Leave export mode with a 6 s hold. Re-enable mobile data.

## USB export (mandatory fallback; Mac or PC)

```bash
python3 -m venv ~/wfg-venv && source ~/wfg-venv/bin/activate   # Homebrew Python refuses pip --user (PEP 668)
pip install pyserial==3.5
python3 usb_export.py ports                                   # find /dev/cu.usbmodem... (macOS)
python3 usb_export.py list --port /dev/cu.usbmodem1101
python3 usb_export.py dump --port /dev/cu.usbmodem1101 --all --confirm --out exports/
python3 usb_export.py delete --port /dev/cu.usbmodem1101 --session S000001.wfg   # then hold device button 2.5 s
python3 usb_export.py verify exports/WFG-...-000001_WALK.wfg   # offline integrity check
python3 usb_export.py convert some.wfg --out exports/          # offline conversion
```

Stop recording first: the device refuses LIST/DUMP/CHECK while recording. `dump` checks transfer size, SHA-256
against the device's value, each record's CRC and sequence, writes `.wfg .csv .gpx .geojson .wfg.sha256
.integrity.json`, and with `--confirm` re-reads the saved `.wfg` from disk before confirming it on the device.
The CSV/GPX/GeoJSON from this script are byte-identical to what the device page serves (tested).

## Data format 2 (firmware 0.2.0)

CSV now has 43 columns: the former 34 plus `status_vbat_mv, status_vbat_pin_mv, status_vbat_factor,
status_fs_free_bytes, status_fs_total_bytes, status_nmea_ok, status_nmea_checksum_errors` (filled on
`record_type=STATUS` rows, written at start and every 60 s), and `session_start_reason, resumed_from_session_id`
(on every row; `AUTO_RESUMED_AFTER_RESET` marks a session started automatically after a reset). STATUS rows are
not track points and are not written to GPX/GeoJSON; the start reason is in their metadata. `.wfg` files from
firmware 0.1.0 (format 1) still decode, verify and convert (tested with `samples/format_v1/`).

## viewer.html

Single offline file (no CDN, no map tiles, no network requests; tested). Open it in Safari, Chrome or any desktop
browser, pick an exported `.csv` (preferred) or `.gpx`.
- Draws the track on a local metric projection with scale bar and north mark; pinch/drag/scroll to zoom.
- Fix gaps are drawn as dashed red straight lines between the last and next fix, labelled "route unknown".
- Located events are orange dots; unlocated events are listed as "no position".
- Stats: duration, fix points, observation rows, % no-fix time, max recording gap between any rows, max gap
  between fixes, path length over fix runs only, events located / unlocated, no-fix rows by reason, end reason,
  start reason (owner button or auto-resumed), battery mV at start and at the last STATUS row, storage free.
  From GPX, rows without a fix are not present, so no-fix time and recording gap show "n/a (load the CSV)".

## Samples (generated by the host tests, synthetic data)

`samples/S000001_WALK.{wfg,csv,gpx,geojson}` and `.wfg.sha256` (format 2): 86 records incl. 2 STATUS, 60 fixes, 17 no-fix rows (cold start
before first fix, 8 s receiver no-fix, 5 s with no NMEA at all), 3 event marks (1 located, 2 without position),
one GNSS clock jump of +3 s. `S000001_WALK_recovered.csv`: same session after a simulated power cut with a torn
29-byte tail, closed by boot recovery. `S000002_WALK_autoresumed.*`: a session started automatically after a simulated brownout, attributed to the cut
session. `format_v1/`: a format 1 file and the CSV firmware 0.1.0 produced from it (read-compatibility tests).
`usb_dump_transcript.txt`: the USB `DUMP` exchange. `screenshots/`:
headless Chromium renders of viewer.html (phone size, light and dark) and of the device page against a mock
device. These are synthetic, not a real recording.

## Status

| Check | Result |
|---|---|
| `tests/test_usb_export.py` (byte identity with firmware incl. auto-resumed sample, v1 compatibility, damage detection, end-to-end USB over a pseudo-terminal using the real C++ protocol) | 31 passed, 0 failed |
| `tests/test_pages_browser.py` (headless Chromium: viewer stats incl. STATUS rows and old CSVs, no network requests; device page downloads, JS SHA-256 and CRC, confirm flow against a mock HTTP device) | 23 passed, 0 failed |
| Real iPhone / Android, real device Wi-Fi, real USB on macOS | NOT TESTED (no hardware). iOS/Android network prompts above are expected behaviour to confirm, wording differs by OS version. |
