# Field route logger and live map

This directory collects the maintained device software and local computer interface. It is separate from the computational routing benchmark: logging movement does not execute the wildfire router on the microcontroller.

| Folder | Purpose |
|---|---|
| `firmware_v0_3_0_live/` | Firmware 0.3.0 with USB LIVE telemetry and FireBeetle backlight configuration |
| `firmware/` | Preserved 0.2.0 comparator used by conversion/testing tools |
| `phone_export/` | USB export, recording conversion and offline viewer |
| `field_logger_demo/` | Local map/replay interface and USB device connection |

## Computer interface

```sh
cd hardware/field_logger_demo
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./run_demo.sh
```

The four included recordings are explicitly simulated. Real recordings, browser profiles, device logs and the local privacy secret are excluded from Git. USB connection is initiated by the user; do not open the port in two applications at once. Indoor GNSS may report NO FIX; a displayed synthetic replay is not live position evidence.

## Device firmware

Install PlatformIO separately. Read the firmware README and select the board actually connected. A compile-only example for the FireBeetle configuration:

```sh
cd hardware/firmware_v0_3_0_live
pio run -e fallback_fb2e
```

Uploading requires the correct serial port and is intentionally not part of setup or publication tests. The copied firmware documents retain their original build/host-test and physical-test status; this publication does not create new physical-device evidence. Existing hardware assembly is not altered.
