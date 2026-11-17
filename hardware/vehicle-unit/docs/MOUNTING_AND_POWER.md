# Mounting on a car roof, and power

Status 2026-11-17: this is the plan for test E (the unit on a car roof, driven). It has not been done. Every
power figure below is approximate, from published typical values, and **must be measured** with a USB power meter
and a bench supply before the test.

## 1. Car-roof installation for test E

Test E is a car on public or closed roads, with no fire. It checks that the unit stays on the roof, stays
powered, keeps the link to the laptop, and records clean data while driving.

1. **Roof.** Magnets hold only on a steel roof. Aluminium, composite and glass roofs need roof bars and the
   U-bolt clamps instead. Clean the roof and the magnet rubber (grit scratches paint and lowers grip).
2. **Placement.** Put the unit on the centre line, forward of any sunroof, with the radar and camera facing
   forward over the bonnet and nothing in the field of view: no roof-bar fairing, aerial or light bar.
   - Measure and record in `config/unit.yaml` the **sensor height above the road** (camera and radar), the
     **mount pitch/roll/yaw** offsets relative to the car, and the lever arm from the GNSS antenna to the
     sensor head. The laptop's geometry (DESIGN.md section 6.4) depends on these.
   - Static levelling: with the car on level ground, record the IMU roll and pitch as the mount offset.
   - **Camera pitch.** The thermal camera is designed to sit **18 deg nose-down** relative to the enclosure
     (`mount.camera_pitch_deg: -18.0`, + up; arithmetic in `config/unit.yaml` and HOUSING.md section 3), so that
     ground from about 3.2 m outwards is in view (a level camera at 2.6 m sees no ground nearer than 6.8 m). Measure
     the bracket's actual angle with an inclinometer on the camera face and write it into `config/unit.yaml`; the
     unit sends `mount` to the laptop in its `hello`. Check on a laptop thermal view that the horizon is just
     inside the top of the image with the car level.
3. **Retention.** Fit four magnets (or two clamps) **plus a tether strap** hooked into the door frames, so a
   magnet failure does not drop the box onto the road. Do a pull test by hand in every direction before each
   drive.
4. **Speed limit for test E (placeholder):** keep below the magnet maker's rated speed for the load and frontal
   area, and in any case below the speed that the fire service sets for the test. No value has been
   calculated or tested here.
5. **Air thermocouple.** Run its lead along the A-pillar or the bonnet edge to the engine-intake height (for
   example in front of the grille). Clip it in its radiation shield clear of the radiator outflow. Tape the
   lead every 20-30 cm. It must not touch the exhaust or hot engine parts, or flap onto the paint.
6. **GNSS antenna.** Put the puck on the roof clear of the box shadow, at least about 10 cm from it, and
   measure its offset.

## 2. Cable routing into the cabin

Only the **12 V supply** has to reach the cabin. The data goes over Wi-Fi. (A USB/Ethernet tether is a
fallback for the bench, not for the roof.)

- **Through a door seal.** Route the cable over the top of a rear door, where the seal is soft. Use a thin, flat
  section: a **flat window/door pass-through cable** or a flat 2-core lead of at least 1.0 mm2. A round cable
  pinched by the door seal leaks and gets cut over time.
- **Through a window gap.** Use a flat pass-through ribbon under a closed window. Do not leave the window
  partly open with the cable resting in the gap.
- Leave a **drip loop** outside before the cable enters the door seal, so water runs off and does not follow the
  cable inside. Add strain relief at the gland and at the socket plug.
- The inline 5 A fuse sits **near the 12 V socket**, so the whole lead is protected.
- Keep the 12 V lead apart from the thermocouple leads (noise), and away from airbags and pedals inside the cabin.

## 3. Power budget (approximate, to be measured)

| Load | Typical power | Notes |
|---|---|---|
| Raspberry Pi 4 | ~3-6 W | Idle to busy. More with heavy USB load. |
| Raspberry Pi 5 | up to ~12 W and more | Peak under load. Sized for a 27 W supply because of the USB budget. |
| Pi 5 Active Cooler | ~0.5 W | Fan at speed. |
| Topdon TC001 | ~0.5-1 W | Through Pi USB. |
| IWR6843AOPEVM, stock demo | ~2-3 W | Through Pi USB. Peaks during chirps. |
| USB GNSS | ~0.2 W | |
| BNO055 | ~0.04 W | 3V3 from the Pi |
| 3 x MAX31855 | < 0.02 W | 3V3 from the Pi |
| USB Wi-Fi adapter (only if fitted) | ~0.5-1.5 W | Alternative to the RF window |

| Total at 5 V (estimate) | Pi 4 build | Pi 5 build |
|---|---|---|
| Typical | ~7 W (1.4 A) | ~9 W (1.8 A) |
| Worst plausible | ~11 W (2.2 A) | ~17 W (3.4 A) |
| 12 V input current (buck efficiency ~88 % assumed, at 12 V) | ~0.7-1.0 A | ~0.9-1.6 A |
| 12 V input current while cranking (at 8 V) | up to ~1.6 A | up to ~2.4 A |

A 5 A fuse and a 5 V 5 A buck leave margin. USB current, not total power, is the tighter limit: the Pi 5 caps
its USB ports at 600 mA without a negotiated 5 V 5 A supply (WIRING.md section 6). TC001 + EVM + GNSS together
are estimated at 0.6-0.9 A at 5 V.

**Measure** each load separately with a USB power meter (idle, streaming, and radar running), then the whole unit
from the bench supply at 12.0 V, 9 V and 14.4 V. Replace this table with the measured values and the date.

## 4. Brown-out and power-loss behaviour

The vehicle supply is not clean. Running voltage is about 13.5-14.5 V. Cranking can pull the battery to roughly
6-9 V for a second or more. Load dump and other transients can exceed 24 V for milliseconds. Turning the
ignition off may cut the socket.

What the design does about it:
- **Transients:** the TVS clamps them and the buck's >= 36 V input rating absorbs them. Reverse-polarity
  protection guards against a mis-wired lead.
- **Cranking dips:** a buck that keeps regulating down to about 6 V may ride through. If it does not, the Pi
  resets. **Practice for the trial: start the engine first, then plug in the unit.** A supercapacitor UPS HAT
  (BOM B8) is the hardware fix.
- **Detection on the Pi:** the `pi` sensor reports `under_voltage_now` and `under_voltage_ever` (from
  `vcgencmd get_throttled` bits 0 and 16) and `throttled_hex` at 1 Hz. These are logged with the raw data, so
  every recording shows whether the supply sagged.
- **Detection on the laptop (fail closed):** if the Pi resets or loses power, the WebSocket drops. The laptop
  marks every sensor not fresh at once and the verdict becomes **CLOSED** (DESIGN.md sections 5 and 8). A Pi
  that comes back starts a new `session_id`. The laptop never resumes an old verdict, because every verdict
  expires 5 s after issue.
- **Data on the SD card:** a sudden power loss can truncate the last gzip member of the `.jsonl.gz` files in
  `records/<session_id>/`, or in the worst case corrupt the SD card. Mitigations: a high-endurance card, regular
  file rotation by the recorder, an optional read-only root filesystem (`raspi-config` overlay FS) with
  `records/` on a separate partition or USB drive, and the UPS HAT. The replay reader should tolerate a
  truncated last member. That is the recorder/replay owner's job; it is listed as an open item, not checked here.
- **Ignition-off:** if the socket stays live with the ignition off, the unit drains the battery at about
  0.7-1.6 A. Unplug it after the test.

## 5. Not verified

- None of the power figures above has been measured on these parts.
- The buck's behaviour during cranking, the TVS clamping, and the reverse-polarity protection are untested.
- Magnet retention at speed, wind loads, and roof-seal leakage are untested.
- Wi-Fi range from the roof box (through the rear RF window) to a laptop inside the cabin is untested.
- The SD-card behaviour after power loss is untested.
