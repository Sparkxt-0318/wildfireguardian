# Field route logger: booth demo and device page (v2.1)

The booth app for the WildfireGuardian field route logger (Korea Code Fair 2026, SW연구 track). It replays recorded
routes on an offline map with the stops and delays found in them, connects to your own logger over USB to test it,
pull its recordings and check them, and shows the moving track while the logger records (LIVE, firmware 0.3.0).
It is built to `demo_live_v2_1/DEMO_SPEC.md` and runs offline on the Mac: everything it shows comes from this folder
and from the logger on the USB cable.

## 1. Set up the Mac (once, while online)

Python 3.11 or newer (Miniforge or conda on Apple Silicon is fine). From this folder:

```bash
conda create -n wfg python=3.12 -y && conda activate wfg       # or any Python 3.11+ environment
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium                          # for the E key (summary PNGs) and the browser tests
python3 -m pip install -r requirements-tools.txt                # only to run the tests
chmod +x run_demo.sh run_tests.sh
```

Google Chrome is used for the booth window if it is installed; otherwise Chromium, then Playwright's Chromium.

## 2. Run it

```bash
./run_demo.sh
```

The server starts on 127.0.0.1 only (port 8765, or `WFG_PORT=8800 ./run_demo.sh`), Chrome opens full screen in app
mode with its own profile (`.chrome-profile/`), and the Mac stays awake until you quit. Closing the window stops the
server and closes the port; Ctrl+C in the terminal does the same. The terminal shows every line sent to and received
from the logger.

Keys (H shows them all in the app): Space play or pause, R restart, ← → seek 10 s, + − speed, 1 to 9 saved
recordings, D device, Enter connect or choose, T test recording, P pull a recording (Shift+P downloads it again even
when the laptop has the same file), I device page over the LIVE map, X raw lines, E export the summary, F overview or
follow (in REPLAY and LIVE; R resumes the auto-fit after you move the map by hand, and in LIVE that is all R does),
L 한/EN, Esc back to the start screen.

The library on the start screen (`sessions/sessions.json`) holds four SIM recordings (watermarked "모의 데이터 · 실제
기록 아님"): a walk through 4 crossings, a vehicle ride past 6 traffic lights, a 30 m loop and a 10 km drive. Recordings
you pull from your logger are added under the next free key.

## 3. Try your own logger (Appendix D of the spec, about 15 minutes)

1. Wire it as in `CAD_v2_firebeetle/instructions/PRINT_AND_ASSEMBLY_EN_ZH.md`: TEL0157 switch on UART, D/T to D11
   (IO16), C/R to D10 (IO17), display BLK to D7 (IO13), never to D13 (IO12).
2. Flash firmware 0.2.0 as it is: in `firmware/`, `pio run -e fallback_fb2e -t upload --upload-port /dev/cu.usbserial-XXXX`
   (`python3 phone_export/usb_export.py ports` lists the port). The backlight simply stays on with 0.2.0.
3. Close every serial monitor (`pio device monitor`, the Arduino IDE): only one program may have the port open.
4. `./run_demo.sh`, press D, pick the port marked "기록기로 보임", press Enter. The device page should show firmware
   0.2.0, record format 2, a battery voltage and about 2.5 MB free (about 14 hours). Note what "포트를 열 때 재시작" says.
5. Press T and follow the five steps (about a minute); answer the screen question at the end.
6. Read the results. Indoors "측위 없음" is normal. If the GNSS row says no data arrives, check the UART switch and the
   D/T and C/R wires; if it still fails, the receiver may run at 115200 (`WFG_GNSS_BAUD` in
   `firmware/include/board_firebeetle2_esp32e_tel0157.h`). If the screen row fails, check BLK on D7 and the SPI wires.
7. Connection check (연결 점검, 2 to 6 minutes, battery fitted): finds out whether opening the port, closing it or
   replugging restarts the board, and remembers it for this board in `devices/`.
8. Outdoors (optional): wait for a fix on the device screen, press T again, then Enter replays the test on the map.
9. Battery calibration (the 보정 button on the battery tile) with the multimeter, and the Wi-Fi pull (when the device
   is in its export mode: on the connect card, and under the two cards of the device page) are there too.
10. Send the coding agent a screenshot of the result and `logs/device_<date>.log`. The log stays on the Mac and out of
    git; after an outdoor test it contains positions.

The app opens a port only when you press Enter or click Connect. It reconnects by itself after an unplug only when the
connection check showed that neither the open nor the replug restarts the board. It never sends `DELETE`, `CONFIRM`
or `FORMAT` (freeing space stays with `usb_export.py`), and sends `CALVBAT` only from the calibration form. If the
firmware reports a record format other than 1 or 2 with 48-byte records, the device page says so and offers no pull,
no test recording and no connection check. A command the board does not answer in time, or a cable pulled during a
pull, shows a short message instead of an error code.

**LIVE** needs firmware 0.3.0 (`firmware_v0_3_0_live/`, built and host-tested, not yet run on the board). The map
draws the track while the logger records, and the device stream shows the same stop lines as the REPLAY console
("▶ 정지 ③ 감지 · 16:23:16부터 ...", "■ 정지 ③ 종료 · 0:52"). With 0.2.0 the device page works in basic mode and you
replay a recording after pulling it.

## 4. Without the board

```bash
./run_demo.sh --dev-device-double       # a simulated logger behaving like firmware 0.2.0
./run_demo.sh --dev-double-live         # the same, with the LIVE lines of firmware 0.3.0
```

A small panel in the top bar ("모의 장치 조작 · 개발용", "+" opens it) presses the simulated button, pulls the cable,
restarts the board and switches the GNSS between indoors, time only, fix, no data and checksum errors. Everything from it is watermarked "모의 장치 · 실제
기기 아님" and saved under `sessions/sim/device_double/`, never with real recordings. The same holds for any pulled
file whose device id is 00000000, the id reserved for simulated data, whichever port it came from.

## 5. Map data

- `mapdata/gwangju_kdj/`: OpenStreetMap data, about 1.5 km around the Kim Dae-jung Convention Center and its subway
  station (downloaded 2026-10-08; © OpenStreetMap contributors, ODbL 1.0, see `SOURCE.txt`).
- `mapdata/sim_city/`: the invented streets the SIM recordings use, labelled "모의 지도 · 가상 도로".
- Without map data a recording is drawn on a plain grid. Real recordings never get the invented streets, and SIM
  recordings never get real ones.
- New area, once while online: `python3 tools/fetch_mapdata.py --name <area> --bbox S,W,N,E`, or
  `--around sessions/real/<file>.wfg --buffer-m 1200` for the area of a recording. It tries the Overpass API, then the
  OpenStreetMap API; from mainland China either may need a VPN. `--from-file export.osm` converts a file saved from
  openstreetmap.org (Export) instead.

## 6. Recordings, privacy and exports

- `sessions/sessions.json`: the start screen's keys 1 to 9 (`file`, titles, `area`, `tz`, `marks_are_stops`,
  `privacy`). `tz` defaults to the place: Asia/Seoul in Korea, Asia/Shanghai in China.
- Pulled recordings go to `sessions/real/`, test recordings to `sessions/real/device_tests/`. Both folders, the
  device logs (`logs/`), board profiles (`devices/`), exports (`out/`), `sessions/privacy.json` and
  `sessions/zone_secret` are git-ignored.
- Privacy zones: everything within 150 m of a recording's first and last fix is hidden on the map, in the log stream
  (coordinates and the position bytes of the hex) and in every export. The circle is drawn bigger than the hidden area
  and off-centre, so it does not point at the place; the offset is keyed with a random secret made on first use and
  kept only on this Mac (`sessions/zone_secret`), so nobody can work it out from a session's SHA-256 or a zone's name
  and move the circle back. A recording entry can change the radius or switch the zones off (the SIM 30 m loop does).
  Named zones (home, school) go in `sessions/privacy.json`:
  `[{"name": "home", "lat": 31.2, "lon": 121.4, "radius_m": 300}]`. A named zone always hides, but it is drawn (and
  the summary mentions it) only when the route enters it: a circle the route never touches would only show where it is.
- In LIVE, positions are shown only while the logger records. Once a recording starts, every position is hidden until
  its first fix has set the start zone (the logger sends an epoch's NMEA sentences before its `ep` line); the first
  150 m are hidden from that fix on, the named zones from the start of the session, and the last 150 m once the
  recording ends, when the lines already on the page that fall inside it are masked again. This holds for the
  sentences of any satellite system (`$GN`, `$GP`, `$BD`, ...), and a sentence whose position the app cannot read
  (garbled, or a type it does not know) is masked whenever positions are hidden.
- A record that fails its CRC still holds its position bytes and cannot be placed inside or outside a zone, so its
  position bytes and CRC are always masked, in REPLAY and in `DUMP` lines alike. `DUMP` lines that arrive late, after
  a pull gave up, are masked the same way.
- A GPX file (from a phone, for development) can be put under `sessions/real/` and given a key in
  `sessions/sessions.json` like any recording. It is labelled "외부 GPX · 개발용" on the start card, the replay, the
  summary and the exported PNG, and nothing claims a CRC for it (it has no record bytes; `summary.json` says
  `"source": "gpx"` and `"records_crc_ok": null`).
- E exports `out/<session id>/`: `summary_ko.png` and `summary_en.png` (3200 x 2000, white, for the poster),
  `stops.csv` and `summary.json` (every number on the summary). Nothing is written to `NUMBERS.json`.

## 7. Tests

```bash
./run_tests.sh            # everything, 195 tests (about 5 minutes; the browser tests need Playwright's Chromium)
./run_tests.sh --quick    # without the browser tests, 181 tests (about 2 minutes)
```

| Spec test | File |
|---|---|
| 1 offline start, 2 replay to summary, 4 integrity on screen (and a GPX without CRC claims), 5 language, 6 privacy in the page, 7 adaptive scale, 9 LIVE map, I, F and R, 11 nothing clipped (both sizes, both languages), Shift+P | `tests/test_web.py` |
| 2 SIM ground truth, 6 privacy in the data and the exports (a corrupted record included; circle offsets keyed with the local secret; a named zone the route never touches is not drawn) | `tests/test_privacy_sim.py` |
| 3 stop detector (including a CLOCK JUMP and one far outlier in a 10 s stop) | `tests/test_stops.py` |
| 4 integrity, `utc_est` against `usb_export.to_csv()` | `tests/test_session.py` |
| 5 language files, 8 colours and contrast, 13 what the app never sends (code search) | `tests/test_static.py` |
| 9 LIVE through the host fake device of firmware 0.3.0 on a pseudo-terminal; privacy before the first fix, in named zones and in the end zone, masking that fails closed, stop lines in the device stream | `tests/test_live.py` |
| 13 port safety | `tests/test_ports.py` |
| 14 protocol against the host fake device of firmware 0.2.0 on a pseudo-terminal | `tests/test_protocol_fake.py` |
| 15 line notes for every `#` line of firmware 0.2.0 | `tests/test_notes_link.py` |
| 16 test recording and result rows (test double); late `DUMP` lines, unsupported record format, error messages | `tests/test_device_flow.py` |
| 17 connection check (test double, restarts on open A, open B, close and replug) | `tests/test_conncheck.py` |
| 18 Wi-Fi pull against a local server, calibration form | `tests/test_wifi_cal.py` |
| map data tool and the venue area | `tests/test_mapdata.py` |

The host fake devices are compiled from `firmware/` and `firmware_v0_3_0_live/` with `g++` (Xcode command line tools
on the Mac); those tests are skipped when `g++` is missing.

`python3 tools/screenshots.py` takes every state (start, key help, replay, summary, device connect card, test in
progress, result, P menu, LIVE without and with a fix) in both languages at 1512 x 982 and 1728 x 1117 with the
simulated logger, and puts each next to its mockup (spec test 11, the part you check by eye). It writes to
`out/screenshots/`; a set taken on 2026-10-09 is in `../field_logger_demo_screens/`.

## 8. Where this differs from the spec, and why

- Text colours: the spec's `text-3` and `text-4` did not reach WCAG AA contrast on their backgrounds, so they are a
  little lighter (dark: `#86868b`, `#75757a`; light: `text-2 #57575c`, `text-3 #737378`). The values and the reason
  are in the header of `web/css/tokens.css`; a test checks every text token.
- The test double reaches the app through an in-process port object instead of a pseudo-terminal, because a
  pseudo-terminal cannot carry DTR and RTS (the spec says this for test 17; it applies to the double's other restart
  cases too). The real host fake devices of firmware 0.2.0 and 0.3.0 are tested on pseudo-terminals.
- D2Coding is bundled as a renamed subset (`WFGMonoHangul`, 2,574 Hangul syllables) to keep the folder small; its
  licence is next to it.
- LIVE announces a stop when it reaches 10 s, as the spec asks. While a recording runs, standing still at the end
  may be the start of the lead-out; when the recording ends, the detector runs once more exactly as in REPLAY and a
  stop that turns out to be the lead-out is withdrawn.
- Map data for the venue came from the OpenStreetMap API (the Overpass servers did not answer from the build machine);
  the tool supports both.
- Stop spread (spec 6, step 7): the 90th percentile is taken by nearest rank and never as the single farthest fix.
  With 10 fixes, the minimum stop, a linear 90th percentile still gives the farthest fix 10 % of the weight, so one
  stray fix 300 m away would have deleted a real stop, which step 7 rules out.
- Under the results, the three quiet buttons (연결 점검, 배터리 보정, Wi-Fi로 가져오기) appear only when the window has
  room for them (1728 x 1117). On 1512 x 982 the results take their place, as in the mockup; the connection check is
  still linked from the results and calibration from the battery tile.
- `web/vendor/maplibre-gl/maplibre-gl.js` is MapLibre GL JS 4.7.1 with one en dash and one em dash written as `\u`
  escapes, so the folder holds no dash characters; it behaves exactly as released (`web/vendor/README.md`).

## 9. Not verified on hardware

Nothing here has talked to a real board yet. The device page, the line notes, the connection check and LIVE are tested
against the firmware's own host builds and against the test double; Appendix D on your board is the first real test.
Firmware 0.3.0 compiles for every environment and passes its host tests, but has not been flashed. The 10-minute
outdoor LIVE check and the serial-open measurement (section 5) are still to do.

## 10. Folder

```
README.md  run_demo.sh  run_tests.sh  requirements.txt  requirements-tools.txt  pytest.ini  .gitignore
app/        server (main.py), sessions, stops, privacy, replay, exports, SIM writer; device/ (ports, link, notes,
            test_flow, checks, conncheck, live, wifi, save, profiles, double); vendor/usb_export.py (unmodified)
web/        index.html, css/ (tokens.css holds every colour), js/, i18n/ (ko, en), vendor/ (MapLibre, fonts; README.md), img/
tools/      fetch_mapdata.py, make_sim_session.py, screenshots.py
mapdata/    gwangju_kdj/ (OSM), sim_city/ (synthetic)
sessions/   sessions.json, sim/ (SIM recordings with ground truth); real/ and privacy.json stay on the Mac
tests/      the suite above; fakes/ (test double sessions, pseudo-terminal bridge, NMEA, tracks)
```

Created at run time and git-ignored: `sessions/real/`, `sessions/zone_secret`, `devices/`, `logs/`, `out/`,
`.chrome-profile/`.
