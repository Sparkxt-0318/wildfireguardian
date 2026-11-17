# Mounting on a car roof, and power

Status 2026-11-17: this is the plan for test E (the unit on a car roof, driven). It has not been done. Every
power figure below is approximate, from published typical values, and **must be measured** with a USB power meter
and a bench supply before the test.

The housing is the user's **supplied printed PETG housing** (HOUSING.md): body 180 x 140 x 72 mm, 4 mm walls, the
Pi on four standoffs (58 x 49 mm pattern), boards on three floor rails with M3 pilot holes every 10 mm, a bolt-on
front plate with the camera, radar and flux disc on one line 34 mm above the housing base, and an aluminium heat
shield 10 mm in front. This page does not design any part of it. How the housing attaches to the vehicle is not
given here: follow the user's build manual.

## 1. Car-roof installation for test E

Test E is a car on public or closed roads, with no fire. It checks that the unit stays on the roof, stays
powered, keeps the link to the laptop, and records clean data while driving.

1. **Roof attachment.** As in the build manual. Whatever holds the housing, add a secondary retention (a tether
   strap hooked into the door frames), so a failed mount does not drop the unit onto the road.
2. **Inside the housing.** The boards sit on the floor rails (M3 pilot holes every 10 mm) and the Pi on its four
   standoffs. Fix the BNO055 rigidly to a rail, square to the housing, so its axes follow the vehicle (WIRING.md
   section 5). Keep the three MAX31855 boards away from the Pi and the buck (cold-junction error), and keep every
   thermocouple lead clear of the aluminium heat shield.
3. **Placement.** Put the unit on the centre line, forward of any sunroof, with the radar and camera facing
   forward over the bonnet and nothing in the field of view: no roof-bar fairing, aerial or light bar.
   - **Mounting height.** The camera and the radar sit on the same line, 34 mm above the housing base, so they
     share one height: road surface to that line = road to the housing base on the roof + 34 mm. Measure it on the
     vehicle and write the same number into `mount.camera_height_m` and `mount.radar_height_m` in
     `config/unit.yaml` (both 2.6 m placeholders today). The flux disc is on the same line (`mount.plate_height_m`).
     Their horizontal offsets (`mount.sensor_offsets_mm`: camera x = -52, radar x = -8, disc x = +45 mm, sign
     convention unconfirmed) are already in `config/unit.yaml` and go to the laptop in `hello.mount`.
   - Measure and record the **mount pitch/roll/yaw** offsets relative to the car, and the lever arm from the GNSS
     antenna to the sensor head. The laptop's geometry (DESIGN.md section 6.4) depends on these.
   - Static levelling: with the car on level ground, record the IMU roll and pitch as the mount offset.
   - **Camera pitch.** `mount.camera_pitch_deg: -18.0` (+ up) is a placeholder from the earlier concept (18 deg
     down puts ground from about 3.2 m outwards in view; a level camera at 2.6 m sees no ground nearer than 6.8 m).
     Whether the supplied housing holds the P2 Pro square to the front plate or tilted is not known here (HOUSING.md
     section 2). Measure the real angle with an inclinometer on the camera face (or the housing, if the camera is
     square to it) and write it into `config/unit.yaml`; the unit sends `mount` to the laptop in its `hello`. Check
     on a laptop thermal view where the horizon sits with the car level.
4. **Pull test.** Pull the mounted housing by hand in every direction before each drive.
5. **Speed limit for test E (placeholder):** keep below the rating of the roof attachment for the load and frontal
   area, and in any case below the speed that the fire service sets for the test. No value has been calculated or
   tested here.
6. **Air thermocouple.** Run its lead along the A-pillar or the bonnet edge to the engine-intake height (for
   example in front of the grille). Clip it in its radiation shield clear of the radiator outflow. Tape the
   lead every 20-30 cm. It must not touch the exhaust or hot engine parts, or flap onto the paint.
7. **GNSS antenna.** Put the puck on the roof clear of the housing and the aluminium heat shield, at least about
   10 cm from them, and measure its offset.

## 2. Cable routing into the cabin

Only the **12 V supply** has to reach the cabin. The data goes over Wi-Fi. (A USB/Ethernet tether is a
fallback for the bench, not for the roof.)

- **Through a door seal.** Route the cable over the top of a rear door, where the seal is soft. Use a thin, flat
  section: a **flat window/door pass-through cable** or a flat 2-core lead of at least 1.0 mm2. A round cable
  pinched by the door seal leaks and gets cut over time.
- **Through a window gap.** Use a flat pass-through ribbon under a closed window. Do not leave the window
  partly open with the cable resting in the gap.
- Leave a **drip loop** outside before the cable enters the door seal, so water runs off and does not follow the
  cable inside. Add strain relief where the cable enters the housing and at the socket plug.
- The inline 5 A fuse sits **near the 12 V socket**, so the whole lead is protected.
- Keep the 12 V lead apart from the thermocouple leads (noise), and away from airbags and pedals inside the cabin.

## 3. Power budget (approximate, to be measured)

| Load | Typical power | Notes |
|---|---|---|
| Raspberry Pi 4 | ~3-6 W | Idle to busy. More with heavy USB load. |
| Raspberry Pi 5 | up to ~12 W and more | Peak under load. Sized for a 27 W supply because of the USB budget. |
| Pi 5 Active Cooler | ~0.5 W | Fan at speed. |
| InfiRay P2 Pro | ~0.5-1 W | Through Pi USB. |
| IWR6843AOPEVM, stock demo | ~2-3 W | Through Pi USB. Peaks during chirps. |
| USB GNSS | ~0.2 W | |
| BNO055 | ~0.04 W | 3V3 from the Pi |
| 3 x MAX31855 | < 0.02 W | 3V3 from the Pi |
| USB Wi-Fi adapter (only if fitted) | ~0.5-1.5 W | Only if the Pi's own Wi-Fi does not reach the cabin |

| Total at 5 V (estimate) | Pi 4 build | Pi 5 build |
|---|---|---|
| Typical | ~7 W (1.4 A) | ~9 W (1.8 A) |
| Worst plausible | ~11 W (2.2 A) | ~17 W (3.4 A) |
| 12 V input current (buck efficiency ~88 % assumed, at 12 V) | ~0.7-1.0 A | ~0.9-1.6 A |
| 12 V input current while cranking (at 8 V) | up to ~1.6 A | up to ~2.4 A |

A 5 A fuse and a 5 V 5 A buck leave margin. USB current, not total power, is the tighter limit: the Pi 5 caps
its USB ports at 600 mA without a negotiated 5 V 5 A supply (WIRING.md section 6). Camera + EVM + GNSS together
are estimated at 0.6-0.9 A at 5 V. Nearly all of this power ends up as heat inside the closed PETG housing:
HOUSING.md section 3 (d) estimates the inside air at about 16-51 K above ambient (calculation).

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
- Roof attachment at speed, wind loads, and housing leakage are untested.
- Wi-Fi range from the housing on the roof to a laptop inside the cabin is untested.
- The SD-card behaviour after power loss is untested.
