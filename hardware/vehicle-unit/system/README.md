# Vehicle unit: Raspberry Pi setup

Status: written against Raspberry Pi OS bookworm (64-bit) documentation. **None of these steps has been run on
the target Pi yet.** The unit streams and records raw data; it makes no decisions. The laptop app decides, and its
verdicts are advisory for trained crews.

## 1. OS and interfaces

```
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_wifi_country KR      # set your own regulatory country
```

`/boot/firmware/config.txt` additions:

```
dtoverlay=spi1-1cs                 # third MAX31855 (tc_air) on SPI1 CE0 = GPIO18
dtparam=i2c_arm_baudrate=10000     # BNO055 clock stretching; slow bus (or use the i2c-gpio overlay)
```

Reboot, then check: `ls /dev/spidev*` (spidev0.0, spidev0.1, spidev1.0), `i2cdetect -y 1` (0x28 = BNO055),
`v4l2-ctl --list-devices` (TC001), `ls /dev/ttyUSB* /dev/ttyACM*` (radar CP2105 pair, GNSS).

## 2. Code and Python environment

```
sudo useradd -r -m -G dialout,video,spi,i2c,gpio wfgvu
sudo mkdir -p /opt/wfgvu && sudo chown wfgvu: /opt/wfgvu
sudo -u wfgvu git clone <repo> /opt/wfgvu
cd /opt/wfgvu/hardware/vehicle-unit
sudo apt install -y python3-venv python3-numpy python3-yaml python3-serial \
    python3-opencv python3-spidev python3-smbus2 python3-lgpio v4l-utils i2c-tools
sudo -u wfgvu python3 -m venv --system-site-packages .venv
sudo -u wfgvu .venv/bin/pip install --only-binary=:all: -r requirements-pi.txt
```

Install the apt packages before the venv: the minimums in `requirements-pi.txt` are the bookworm apt versions
(spidev 3.5, smbus2 0.4.2), so pip only adds websockets. Without `python3-spidev` pip would try to build spidev from
source (no aarch64 wheel; needs `python3-dev`), and a failed build installs nothing, so the service would crash-loop
on a missing module. `--only-binary=:all:` makes that case fail at once with a clear message. Check after install:
`.venv/bin/python -c 'import websockets, spidev, smbus2, numpy, yaml, serial, cv2'` (untested on the target Pi).

Check ports and buses in `config/unit.yaml` (radar CLI/data ports, SPI bus/device per thermocouple, camera
index, GNSS port). Mount offsets in that file are placeholders to measure on the vehicle.

Smoke test without sensors (replays a recorded or synthetic session, labelled `sim: true`):

```
./run_unit.sh --sim samples/<scenario> --loop
```

## 3. Wi-Fi hotspot (WPA2, 10.42.0.1)

```
sudo install -d -m 700 /etc/wfgvu
sudo sh -c 'umask 077; printf "%s\n" "<your 8-63 character passphrase>" > /etc/wfgvu/hotspot.psk'
sudo system/hotspot.sh up        # creates NetworkManager connection "wfgvu-hotspot", autoconnect on boot
sudo system/hotspot.sh status
```

The laptop joins SSID `WFGVU-01` and connects to `ws://10.42.0.1:8770/stream`. The hotspot uses the Pi's
on-board Wi-Fi; the unit has no other network.

Put the passphrase in `/etc/wfgvu/hotspot.psk` (root only, mode 600) as above; `WFGVU_PSK` also works but is not
recommended. It must be 8-63 printable ASCII characters, no backslash, no leading or trailing space; a bad one is
rejected before anything changes. `up` writes the new profile as a NetworkManager keyfile (mode 600; the passphrase
is never on a command line), loads and activates it under a temporary name, and only then deletes the old
`wfgvu-hotspot` profile and renames the new one; if activation fails the old profile is re-activated. Tested only
against a fake `nmcli` (`tests/test_hotspot.py`), not on the Pi.

Clock: the Pi has no battery RTC and nothing sets its clock from GNSS (and there is usually no network), so the wall
clock (`t_utc`, `session_id`) can repeat or go backwards across boots. The recorder never reuses a session
directory (`<id>-2`, ... if taken) and records `boot_id` and the clock's sync state in `session.json`; order records by
`session_id` and `t_mono`, not by `t_utc`.

## 4. Service

```
sudo cp system/wfgvu.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wfgvu
journalctl -u wfgvu -f
```

`Restart=always` restarts the process 2 s after any exit. Missing sensors do not stop the service: each driver
reports `no_device` heartbeats and retries every 2 s.

## 5. Records

Raw data goes to `records/<session_id>/` (git-ignored): one `<sensor>.jsonl.gz` per sensor, `events.jsonl.gz`,
`unit.jsonl.gz`, `radar_uart.bin`, `session.json`. Files are flushed every second and rotated at 256 MB.
The recorder raises `disk_low` below 1000 MB free and pauses below 200 MB. Full-rate thermal recording is
roughly 1.6 MB/s at 25 Hz (estimated from a synthetic 256 x 192 image with 0.1 K noise, not measured on the
camera): about 5-6 GB per hour, so use a large, fast card or a USB SSD.

Copy a session to the laptop: `rsync -av wfgvu@10.42.0.1:/opt/wfgvu/hardware/vehicle-unit/records/ records/`.

## 6. Power

12 V vehicle socket -> automotive 12 V to 5 V/5 A converter -> Pi. Check under-voltage in the `pi` readings
(`under_voltage_now`, `under_voltage_ever`); any under-voltage makes the Pi's `pi` heartbeat `error`. Cranking
dips will reset the Pi unless the converter rides through them; that has not been tested.

## Not verified

Hotspot script, service unit, SPI1 overlay, BNO055 bus speed, CP2105 port order, TC001 V4L2 format and raw scale,
the radar CLI config, achievable radar frame rate at 921600 baud (see `wfgvu/drivers/radar_iwr6843.py`),
power ride-through. Every one of these needs a bench check on the real hardware before a vehicle test.
