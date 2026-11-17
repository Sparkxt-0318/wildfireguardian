# WildfireGuardian vehicle unit (roof sensor head)

A roof-mounted sensor head for a fire-service vehicle that meets a flame front across a road. It runs on a
Raspberry Pi 4 or 5 and carries:

- a Topdon TC001 thermal camera;
- a TI IWR6843AOPEVM radar running TI's stock demo firmware;
- a blackened copper flux plate with a type-K thermocouple on a MAX31855;
- two more MAX31855 thermocouples, one for the housing and one for the air at engine-intake height;
- a BNO055 IMU;
- a USB GNSS receiver.

It is powered from the vehicle's 12 V socket.

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
   #   dtoverlay=spi1-1cs              # tc_air on SPI1 CE0 (config/unit.yaml default)
   #   dtparam=i2c_arm_baudrate=10000  # BNO055 clock-stretching workaround
   sudo usermod -aG spi,i2c,gpio,dialout,video "$USER"
   sudo reboot
   ```
4. **Python environment.** Create the venv with system site packages, so that apt's OpenCV, spidev and lgpio
   are visible:
   ```sh
   cd hardware/vehicle-unit
   python3 -m venv --system-site-packages .venv
   .venv/bin/pip install --only-binary=:all: -r requirements-pi.txt
   ```
   Do step 2 first: the minimums in `requirements-pi.txt` are the bookworm apt versions, so pip installs only
   websockets. Without the apt `python3-spidev`, pip would try to build spidev from source (no aarch64 wheel) and a
   failed build installs nothing; `--only-binary=:all:` makes that fail clearly instead.
5. **Config:** edit [`config/unit.yaml`](config/unit.yaml): serial ports (use `/dev/serial/by-id/...`), the
   camera index, and the mount offsets measured on the vehicle.
6. **Hotspot and service:** see `system/README.md`. `system/hotspot.sh` sets up the Pi's own Wi-Fi access point
   at 10.42.0.1. `system/wfgvu.service` runs the unit under systemd:
   ```sh
   sudo cp system/wfgvu.service /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable --now wfgvu
   journalctl -u wfgvu -f
   ```
7. **Run by hand:** `.venv/bin/python -m wfgvu --config config/unit.yaml`. A sensor that is not connected
   reports `no_device` heartbeats and is retried every 2 s. The unit does not refuse to start.

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
| `config/unit.yaml` | Ports, rates, SPI/I2C buses, camera index, mount offsets (placeholders) |
| `config/iwr6843aop_vu.cfg` | CLI config sent to the radar's stock demo (default, long range: 128 bins x 0.468 m, max 54 m, 10 Hz; UNTESTED on the EVM) |
| `config/iwr6843aop_vu_short.cfg`, `config/iwr6843aop_vu_long_fine.cfg` | alternatives: old 22.5 m config; 512 bins x 0.117 m to 54 m at 2.86 Hz |
| `wfgvu/protocol.py` | Message envelope, encoders and decoders (shared with the laptop) |
| `wfgvu/drivers/` | One driver per sensor (thermal, radar + TLV parser, 3 x MAX31855, BNO055, GNSS, Pi health); decode and timestamp only |
| `wfgvu/recorder.py`, `wfgvu/replay.py`, `wfgvu/synth.py` | Raw recording, replay for sim mode, synthetic scenarios |
| `wfgvu/server.py`, `wfgvu/__main__.py` | One WebSocket, broadcast; `python -m wfgvu` |
| `system/` | Hotspot script, systemd unit, Pi setup notes |
| `samples/` | Small synthetic sessions (labelled `sim`) |
| `docs/WIRING.md`, `docs/wiring.svg` | Pin table and wiring diagram (header, SPI, I2C, USB, power, thermocouples) |
| `docs/HOUSING.md`, `docs/housing.svg`, `docs/housing.scad` | Roof-box concept, radome and LWIR window, flux plate mounting, test F expectations |
| `docs/BOM.md` | Parts list (prices left for you to fill in) |
| `docs/MOUNTING_AND_POWER.md` | Car-roof installation (test E), cable routing, power budget, brown-out behaviour |
| `docs/make_drawings.py`, `docs/test_docs.py` | Regenerates both SVGs; checks the docs against each other and against `config/unit.yaml` |
| `tests/` | Unit tests (no hardware) |
| `records/` | Runtime recordings (git-ignored; never named `logs`) |

## Not verified on hardware

As of 2026-11-17, **nothing in this folder has run on a Raspberry Pi, the IWR6843AOPEVM radar, the TC001 camera,
the MAX31855 boards, the BNO055 or a GNSS receiver.** In particular:

- the drivers are tested only against synthetic bytes, frames and fakes, not real devices;
- the radar CLI config has not been sent to a real EVM, and the EVM's mode-switch positions have not been checked;
- the TC001 frame layout (lower half = raw temperature x 64) comes from the published format and has not been
  confirmed on our camera;
- the wiring, the SPI1 overlay, the BNO055 clock-stretching workaround, the hotspot and the systemd unit have
  not been tried;
- the housing, radome, germanium window, flux plate absorptivity, power budget and brown-out behaviour are
  design values (see `docs/`), none measured;
- no car-roof drive (test E) and no water/heat test (test F) has been done.

## What may be claimed

The only claim this project allows, and only after the tests have run and are reported in
`apps/crossing/RESULTS.md`:

> "vehicle-mountable unit, tested on a car and on lab flames, ready for a fire-service trial"

Until then, not even that. The unit is not operationally ready, and nothing here says otherwise.
