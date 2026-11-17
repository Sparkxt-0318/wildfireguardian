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
dtparam=i2c_arm_baudrate=10000     # BNO055 clock stretching; slow bus (or use the i2c-gpio overlay)
```

No SPI overlay: all three MAX31855 are on SPI0 (`do_spi 0` above enables it). Pin map (user's printed build manual):
shared 3.3 V pin 17, GND pin 20, CLK pin 23 (GPIO11), DO pin 21 (GPIO9); chip selects plate CE0 GPIO8 pin 24,
housing CE1 GPIO7 pin 26, intake air GPIO5 pin 29 (software chip select: wfgvu opens `/dev/spidev0.0` with
`no_cs` and drives GPIO5 itself with `python3-lgpio`). BNO055: 3.3 V pin 1, GND pin 6, SDA pin 3, SCL pin 5. If an
older image has `dtoverlay=spi1-1cs` in `/boot/firmware/config.txt`, remove that line (GPIO18/19/21 are not used).

Reboot, then check: `ls /dev/spidev*` (spidev0.0 and spidev0.1 only), `ls -l /dev/gpiochip*` (group `gpio`),
`i2cdetect -y 1` (0x28 = BNO055), `lsusb` (InfiRay P2 Pro = `0bda:5830`), `v4l2-ctl --list-devices` (its
capture node; `config/unit.yaml` `thermal.index: auto` finds it by that USB id), `ls /dev/ttyUSB* /dev/ttyACM*`
(radar CP2105 pair, GNSS). Then the thermocouple check, with the service stopped:
`sudo systemctl stop wfgvu; cd /opt/wfgvu/hardware/vehicle-unit && .venv/bin/python -m wfgvu.tccheck`
(exit 0 OK, 1 fault, 2 flux disc >= 70 C, 3 SPI/GPIO busy or missing, 64 bad command line; see
`python3 -m wfgvu.tccheck --help`).

Software chip select, as built (untested on a Pi): every MAX31855 transfer runs under one SPI0 lock in the wfgvu
process; GPIO5 is claimed HIGH before the first transfer and is low only inside that lock; while a channel is open
the process holds an exclusive flock on the `/dev/spidev0.0` node itself (opened read-only, nothing created), so a
second process (tccheck while the service runs, any user in group `spi`) gets exit 3 instead of interleaving reads. If the SPI controller refuses `no_cs` (possible on the Pi 5's RP1 SPI; not
checked), `tc_air` reports `no_device` "no_cs unsupported" and is never read: every verdict stays CLOSED.

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
`.venv/bin/python -c 'import websockets, spidev, smbus2, numpy, yaml, serial, cv2, lgpio'` (untested on the target
Pi; `lgpio` drives the GPIO5 chip select, `gpiod` is the fallback).

Check ports and buses in `config/unit.yaml` (radar CLI/data ports, SPI bus/device and `cs_gpio` per thermocouple,
camera `index: auto` / `usb_id`, GNSS port). Mount heights and angles in that file are placeholders to measure on
the vehicle; `mount.sensor_offsets_mm` holds the user's build-manual figures. This `/opt/wfgvu` install is the
alternative to the main README's Quick start (clone in `~/wildfireguardian`, service installed for that clone and
the login user): the service reads the `config/unit.yaml` of the clone in its unit file, so edit that one.

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

Hotspot script, service unit, the GPIO5 software chip select (`no_cs` on the Pi 4 and the Pi 5, lgpio/gpiod chip
choice), BNO055 bus speed, CP2105 port order, the InfiRay P2 Pro's V4L2 format and raw scale (TC001-compatible by
the published format) and its discovery by USB id,
the radar CLI config, achievable radar frame rate at 921600 baud (see `wfgvu/drivers/radar_iwr6843.py`),
power ride-through. Every one of these needs a bench check on the real hardware before a vehicle test.
