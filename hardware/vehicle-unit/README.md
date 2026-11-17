# WildfireGuardian vehicle unit (roof sensor head)

A roof-mounted sensor head for a fire-service vehicle that meets a flame front across a road. It runs on a
Raspberry Pi 4 or 5 and carries:

- an InfiRay P2 Pro thermal camera (USB id 0bda:5830; the same 256x384 frame as the Topdon TC001, so the driver
  module is still `thermal_tc001.py` and the sensor is still `thermal`);
- a TI IWR6843AOPEVM radar running TI's stock demo firmware;
- a blackened copper flux disc on printed PETG tabs with a type-K thermocouple on a MAX31855 (**every flux run stops
  and warns at 70 C disc temperature**);
- two more MAX31855 thermocouples, one for the housing and one for the air at engine-intake height;
- a BNO055 IMU;
- a USB GNSS receiver.

It is powered from the vehicle's 12 V socket. Everything sits in the user's own printed PETG housing (180 x 140 x
72 mm, bolt-on front plate, aluminium heat shield 10 mm in front), which this project documents in
[`docs/HOUSING.md`](docs/HOUSING.md) but does not design.

The unit **streams raw data** over one WebSocket (`ws://10.42.0.1:8770/stream`) on its own Wi-Fi hotspot, and
**records raw data** to `records/<session_id>/`. The macOS laptop app in [`../../apps/crossing/`](../../apps/crossing/)
turns that stream into one of four advisory verdicts: CLOSED / CROSS FAST / SPRAY THEN RE-CHECK / REOPENED.

The message format, units, sensor names, recorded-session format and decision rules are in
[`DESIGN.md`](DESIGN.md), which is the binding contract. This README does not repeat them.

## The rule: no decisions on the Pi

The Pi decodes, timestamps, streams and records. It never decides anything. It does not apply a flame threshold,
estimate a dose, check freshness for the laptop, or produce a verdict. Every decision is made on the laptop,
from the laptop's own clock. The laptop never trusts the Pi's "ok" flags or clock for freshness, and it fails
closed: missing, stale, frozen or malformed data gives CLOSED.

Smoke is not a target and must not trigger anything. Verdicts are advisory for trained crews. Every limit in this
system is a placeholder for a fire service to set.

## Quick start on a Raspberry Pi (untested on hardware)

These are the intended steps. They have **not** been run on a Pi yet.

1. **OS:** Raspberry Pi OS Bookworm (64-bit). Python 3.11 is the system Python, and the code here targets it.
2. **Packages:**
   ```sh
   sudo apt update
   sudo apt install -y python3-venv python3-numpy python3-yaml python3-serial \
       python3-opencv python3-spidev python3-smbus2 python3-lgpio v4l-utils i2c-tools
   ```
   `python3-smbus2` is in the Bookworm archive; if your mirror lacks it, use `pip install smbus2` inside the venv.
3. **Enable SPI and I2C** (see [docs/WIRING.md](docs/WIRING.md)):
   ```sh
   sudo raspi-config nonint do_spi 0
   sudo raspi-config nonint do_i2c 0
   # /boot/firmware/config.txt
   #   dtparam=i2c_arm_baudrate=10000  # BNO055 clock-stretching workaround (no other overlay is needed)
   sudo usermod -aG spi,i2c,gpio,dialout,video "$USER"
   sudo reboot
   ```
4. **Python environment.** Create the venv with system site packages, so that apt's OpenCV, spidev and lgpio
   are visible:
   ```sh
   git clone <repo> ~/wildfireguardian            # the one install location used below and by the service
   cd ~/wildfireguardian/hardware/vehicle-unit
   python3 -m venv --system-site-packages .venv
   .venv/bin/pip install --only-binary=:all: -r requirements-pi.txt
   ```
   Do step 2 first: the minimums in `requirements-pi.txt` are the bookworm apt versions, so pip installs only
   websockets. Without the apt `python3-spidev`, pip would try to build spidev from source (no aarch64 wheel) and a
   failed build installs nothing; `--only-binary=:all:` makes that fail clearly instead.
5. **Config:** edit [`config/unit.yaml`](config/unit.yaml): serial ports (use `/dev/serial/by-id/...`) and the
   mount heights and angles measured on the vehicle. The camera is found by its USB id (`index: auto`); the
   housing's sensor offsets are already in `mount.sensor_offsets_mm`.
6. **Hotspot and service:** see `system/README.md`. `system/hotspot.sh` sets up the Pi's own Wi-Fi access point
   at 10.42.0.1. `system/wfgvu.service` runs the unit under systemd. Install it for THIS clone and your login user
   (so the service reads the same `config/unit.yaml` you edited in step 5), but do not start it yet: First run
   step 3 starts it.
   ```sh
   cd ~/wildfireguardian/hardware/vehicle-unit
   sed -e "s|/opt/wfgvu|$HOME/wildfireguardian|g" -e "s|^User=wfgvu|User=$USER|" -e "s|^Group=wfgvu|Group=$(id -gn)|" \
       system/wfgvu.service | sudo tee /etc/systemd/system/wfgvu.service >/dev/null
   sudo systemctl daemon-reload
   ```
   (`system/README.md` section 2 describes the alternative: a dedicated `wfgvu` user and a clone in `/opt/wfgvu`.
   Then that clone's `config/unit.yaml` is the one the service reads, and every path below is
   `/opt/wfgvu/hardware/vehicle-unit`.)
7. **Run by hand:** `.venv/bin/python -m wfgvu --config config/unit.yaml`. A sensor that is not connected
   reports `no_device` heartbeats and is retried every 2 s. The unit does not refuse to start.

## Pin summary

Pin map from the user's printed build manual (2026-11-17); details and the drawing in
[`docs/WIRING.md`](docs/WIRING.md).

| Device | Pins on the 40-pin header |
|---|---|
| MAX31855 x3, shared | 3V3 pin 17, GND pin 20, CLK pin 23 (GPIO11), DO pin 21 (GPIO9) |
| `tc_plate` (flux plate) CS | GPIO8, pin 24 (SPI0 CE0) |
| `tc_housing` CS | GPIO7, pin 26 (SPI0 CE1) |
| `tc_air` (intake air) CS | GPIO5, pin 29 (software chip select) |
| BNO055 (I2C1, 0x28) | 3V3 pin 1, GND pin 6, SDA pin 3, SCL pin 5 |

## First run

The build manual points here. Do the four steps in this order. **None of them has been run on the real hardware
yet (2026-11-17)**; only the simulated parts have run, on a laptop.

The commands assume the repository is cloned to `~/wildfireguardian` on the Pi, the venv from Quick start step 4
exists and the service was installed for that clone (Quick start step 6). (If you followed `system/README.md`
section 2 instead, the clone is `/opt/wfgvu`: use `/opt/wfgvu/hardware/vehicle-unit` in place of
`~/wildfireguardian/hardware/vehicle-unit`.) Steps 1 to 3 need the service stopped (it holds SPI, GPIO5 and port
8770); this is harmless if it is not running:

```sh
sudo systemctl stop wfgvu
```

Activate the venv once per terminal, so that `python3` below is the venv's Python (websockets is installed only
there):

```sh
source ~/wildfireguardian/hardware/vehicle-unit/.venv/bin/activate
```

### 1. Thermocouple check

```sh
cd ~/wildfireguardian/hardware/vehicle-unit && python3 -m wfgvu.tccheck
```

If the service is installed and running, stop it first (`sudo systemctl stop wfgvu`): it holds SPI and GPIO5. The
check reads the three MAX31855 for 10 s at 2 Hz with the unit's own driver and `config/unit.yaml` (options
`--seconds N`, `--hz F`, `--config PATH`; `--fake` runs a simulated bench without hardware, and
`--fake-disc-c X` sets the simulated disc temperature to see the 70 C stop). It prints one line per read with, for
`tc_plate`, `tc_housing` and `tc_air`, the hot-junction C, the cold-junction C, the fault and the fault bits
(SCV/SCG/OC), then a summary per channel and one `VERDICT` line. `echo $?` shows the exit code:

| Exit | Meaning | What to do |
|---|---|---|
| 0 | PASS: all three answer, no fault, plausible bench readings | Warm each probe by hand in turn: only its own channel may rise (polarity and chip-select check). |
| 1 | FAIL: a fault or an implausible reading (open thermocouple, short, cold-junction spread > 5 C between chips, hot junction outside -20..60 C at a bench check; the bench limits are placeholders) | Check the wiring against [`docs/WIRING.md`](docs/WIRING.md). |
| 2 | `STOP: flux disc at X C >= 70 C (PETG tabs)`: stopped at once | Remove the heat source, let the disc cool below 70 C, check the PETG tabs. |
| 3 | Cannot open SPI/GPIO | `sudo systemctl stop wfgvu`; check that SPI is enabled and `ls /dev/spidev*` shows `spidev0.0` and `spidev0.1`; check the `spi` and `gpio` groups. |
| 64 | Bad command line | Check the options: `python3 -m wfgvu.tccheck --help`. |

A missing `--config` file, or a config whose three channels do not have distinct chip selects, is exit 1 (the check
never passes on built-in defaults).

### 2. Simulated mode on the Pi

```sh
cd ~/wildfireguardian/hardware/vehicle-unit && python3 -m wfgvu --sim samples/flame_front --loop --no-record
```

Replays the committed synthetic `flame_front` session through the real server on port 8770, in a loop, without
recording. Every message carries `"sim": true` and the laptop shows SIMULATED. Use it to check the hotspot and the
laptop app before any sensor is involved. Ctrl+C stops it. Stop the service first (`sudo systemctl stop wfgvu`):
if port 8770 is taken, wfgvu prints `error: port 8770 is already in use ...` and exits 2.

### 3. Real mode

The first time, in the foreground, so you see every message:

```sh
cd ~/wildfireguardian/hardware/vehicle-unit && python3 -m wfgvu
```

It reads `config/unit.yaml`, starts every sensor, streams on `ws://10.42.0.1:8770/stream` and records to
`records/<session_id>/`. A sensor that is not connected reports `no_device` heartbeats and is retried every 2 s; the
unit does not refuse to start. Ctrl+C stops it and closes the recording. Then run it as the service (installed in
Quick start step 6; it reads the `config/unit.yaml` of the clone it was installed for):

```sh
sudo systemctl start wfgvu
journalctl -u wfgvu -f
sudo systemctl enable wfgvu      # also start it at boot (after that, stop it before steps 1-3)
```

### 4. Laptop app

On the laptop, joined to the Pi's hotspot, from the repository root:

```sh
cd apps/crossing && ./run_crossing.sh --pi ws://10.42.0.1:8770/stream
```

It serves the app on `http://127.0.0.1:8781/` and opens a browser. Without the Pi, replay a committed sample:

```sh
cd apps/crossing && ./run_crossing.sh --replay ../../hardware/vehicle-unit/samples/flame_front --loop
```

Verdicts are advisory and every limit is a placeholder. A flux disc at or above 70 C gives the tc_plate fault
`PLATE_DISC_OVER_TEMP`, every verdict CLOSED while it lasts, and the warning
"Flux disc over 70 C: PETG tabs at risk".

## Sim mode (no hardware)

Sim mode replays a recorded or synthetic session through the same drivers and server. Every message carries
`"sim": true`, and the laptop UI watermarks it "SIMULATED".

```sh
cd hardware/vehicle-unit
python -m wfgvu --sim samples/<scenario>            # e.g. samples/flame_front, samples/smoke_only
python -m wfgvu --sim samples/<scenario> --speed 4 --loop
python -m wfgvu.synth flame_front "$TMPDIR/ff" --seed 1 --duration 60   # make a new synthetic session
```

Scenarios (DESIGN.md section 4): `no_fire`, `smoke_only`, `flame_front`, `water_mist`, `corner_reflector`,
`crossing`, `after_pass`. The failure overlays are `--fail SENSOR@T`, `--freeze SENSOR@T` and
`--fault tc_plate@T:open`. The synthetic physics is illustrative only. It is stated in the `wfgvu/synth.py`
docstrings and is not evidence of how a real flame looks to the radar or camera.

Laptop side: `python -m crossing --pi ws://<pi-or-127.0.0.1>:8770/stream` (see `apps/crossing/README.md`).

Tests (no hardware needed):

```sh
cd hardware/vehicle-unit
../../apps/crossing/.venv/bin/python -m pytest              # unit tests + docs/test_docs.py (testpaths = tests docs)
../../apps/crossing/.venv/bin/python -m pytest docs/test_docs.py   # docs, drawings, wiring vs unit.yaml only
```

Tests that open a loopback socket (`tests/test_server.py`) skip where binding a local port is not permitted.

## Folder map

| Path | What it is |
|---|---|
| `DESIGN.md` | Binding interface contract: protocol, units, recorded format, decision rules (shared with `apps/crossing`) |
| `config/unit.yaml` | Ports, rates, SPI/I2C buses and chip selects, camera USB id, the supplied housing's dimensions and sensor offsets, mount heights and angles (placeholders) |
| `config/iwr6843aop_vu.cfg` | CLI config sent to the radar's stock demo (default, long range: 128 bins x 0.468 m, max 54 m, 10 Hz; UNTESTED on the EVM) |
| `config/iwr6843aop_vu_short.cfg`, `config/iwr6843aop_vu_long_fine.cfg` | alternatives: old 22.5 m config; 512 bins x 0.117 m to 54 m at 2.86 Hz |
| `wfgvu/protocol.py` | Message envelope, encoders and decoders (shared with the laptop) |
| `wfgvu/drivers/` | One driver per sensor (thermal, radar + TLV parser, 3 x MAX31855, BNO055, GNSS, Pi health); decode and timestamp only |
| `wfgvu/recorder.py`, `wfgvu/replay.py`, `wfgvu/synth.py` | Raw recording, replay for sim mode, synthetic scenarios |
| `wfgvu/server.py`, `wfgvu/__main__.py` | One WebSocket, broadcast; `python -m wfgvu` |
| `wfgvu/tccheck.py` | Thermocouple bench check, `python3 -m wfgvu.tccheck` (First run step 1) |
| `system/` | Hotspot script, systemd unit, Pi setup notes |
| `samples/` | Small synthetic sessions (labelled `sim`) |
| `docs/WIRING.md`, `docs/wiring.svg` | Pin table and wiring diagram (header, SPI, I2C, USB, power, thermocouples) |
| `docs/HOUSING.md`, `docs/housing.svg` | The user's supplied housing (documented, not designed): front-plate layout, questions with arithmetic, test F expectations |
| `docs/BOM.md` | Parts list (prices left for you to fill in) |
| `docs/MOUNTING_AND_POWER.md` | Car-roof installation (test E), cable routing, power budget, brown-out behaviour |
| `docs/make_drawings.py`, `docs/test_docs.py` | Regenerates both SVGs and the HOUSING.md checks block; checks the docs against each other, the user's pin map and `config/unit.yaml` |
| `tests/` | Unit tests (no hardware) |
| `records/` | Runtime recordings (git-ignored; never named `logs`) |

## Not verified on hardware

As of 2026-11-17, **nothing in this folder has run on a Raspberry Pi, the IWR6843AOPEVM radar, the InfiRay P2 Pro
camera, the MAX31855 boards, the BNO055 or a GNSS receiver.** In particular:

- the drivers are tested only against synthetic bytes, frames and fakes, not real devices;
- the radar CLI config has not been sent to a real EVM, and the EVM's mode-switch positions have not been checked;
- the P2 Pro frame layout (lower half = raw temperature x 64, as for the TC001) comes from the published TC001
  format and has not been confirmed on our camera;
- the wiring, the GPIO5 software chip select (`no_cs`), the BNO055 clock-stretching workaround, the thermocouple
  check, the hotspot and the systemd unit have not been tried;
- the supplied housing has not been seen or measured by this project; the radar loss through its 1.2 mm window,
  the effect of the aluminium heat shield, the flux disc's absorptivity and view, the power budget and brown-out
  behaviour are calculations or estimates (see `docs/`), none measured;
- no car-roof drive (test E) and no water/heat test (test F) has been done.

## What may be claimed

The only claim this project allows, and only after the tests have run and are reported in
`apps/crossing/RESULTS.md`:

> "vehicle-mountable unit, tested on a car and on lab flames, ready for a fire-service trial"

Until then, not even that. The unit is not operationally ready, and nothing here says otherwise.
