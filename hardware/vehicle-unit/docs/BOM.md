# Vehicle unit bill of materials

Status 2026-11-17: this is a parts list. Nothing has been bought against it by this project. The prices are left
blank on purpose: fill them in from real quotes. Part numbers are given only where the software depends on them.
Otherwise the entry is a specification, and any part that meets it will do.

The housing is **supplied**: the user's own printed PETG housing (HOUSING.md), being printed. There are no housing
parts to buy here beyond what the user's build manual lists; the earlier die-cast box, radome sheet, germanium window,
magnets and base plate are withdrawn.

## A. Fixed hardware (the user's list)

These parts are given. The rest of the design is built around them.

| # | Part | Qty | Purpose | Price (fill in) |
|---|---|---|---|---|
| A1 | Raspberry Pi 4 Model B (4 GB or more) **or** Raspberry Pi 5 (4/8 GB) | 1 | Sensor head computer: drivers, recorder, WebSocket server, Wi-Fi hotspot. Makes no decisions. | |
| A2 | InfiRay P2 Pro thermal camera (256 x 192, USB-C, USB id 0bda:5830; same 256x384 frame format as the Topdon TC001) | 1 | `thermal`: flame pixels, near edge, flame height | |
| A3 | TI IWR6843AOPEVM, stock out-of-box mmWave demo firmware | 1 | `radar`: range profile, azimuth heatmap, point cloud | |
| A4 | Copper flux disc for the 30.6 mm front-plate hole, blackened, on printed PETG tabs (size and thickness per the build manual; runs stop at 70 C) | 1 | `tc_plate`: thin-skin calorimeter (incident flux, dose) | |
| A5 | K-type thermocouple for the disc (bare wires or fine-gauge, glass-fibre insulated) | 1 | Disc junction | |
| A6 | MAX31855 breakout board (K type) | 3 | `tc_plate`, `tc_housing`, `tc_air` | |
| A7 | K-type thermocouples for the housing and the intake-height air | 2 | `tc_housing` (wall/air in box), `tc_air` (sheathed, ungrounded) | |
| A8 | BNO055 breakout | 1 | `imu`: roll, pitch, gravity vector | |
| A9 | USB GNSS receiver (NMEA) | 1 | `gnss`: position, speed, course, UTC | |
| A10 | 12 V accessory-socket power (the vehicle's socket and a plug) | 1 | Supply | |

## B. Power chain

| # | Part (specification) | Qty | Purpose | Price (fill in) |
|---|---|---|---|---|
| B1 | 12 V socket plug with its own fuse, lead >= 1.0 mm2 | 1 | Takes power from the vehicle | |
| B2 | Inline blade fuse holder (waterproof) + 5 A blade fuse (+ spares) | 1 (+3) | Protects the lead and the unit | |
| B3 | Reverse-polarity protection: ideal-diode controller module (P-FET) or 5 A Schottky diode | 1 | Survives a reversed plug or a mis-wired lead | |
| B4 | TVS diode for 12 V automotive load dump (unidirectional, e.g. 600 W-1.5 kW class, standoff about 18-24 V) | 1 | Clamps transients | |
| B5 | Automotive 12 V -> 5 V buck, >= 5 A output, input rated >= 36 V, works down to about 6-8 V; USB-C PD 5 V 5 A output for a Pi 5 | 1 | Pi + USB supply | |
| B6 | USB-C cable, short, 5 A rated (Pi 5) | 1 | Buck to Pi | |
| B7 | Powered USB hub, 5 V input (optional) | 0-1 | Only if the Pi limits USB current (WIRING.md section 6) | |
| B8 | Hold-up option: supercapacitor UPS HAT or small UPS module (optional) | 0-1 | Rides through cranking dips, gives a clean shutdown | |

## C. Wiring and connectors

| # | Part | Qty | Purpose | Price (fill in) |
|---|---|---|---|---|
| C1 | Type-K extension (KX) wire, twisted pair, glass-fibre or PTFE insulated | about 5 m | All thermocouple runs (no copper in the loop) | |
| C2 | Type-K miniature connectors (plug + socket) | 3 pairs | Detachable thermocouple leads | |
| C3 | Dupont/JST jumper wires or a small perfboard harness, 0.2-0.3 mm2, several colours | 1 set | SPI/I2C header wiring | |
| C4 | 10 kOhm resistor | 1 | Recommended pull-up GPIO5 (pin 29) -> 3V3 for the `tc_air` software chip select (advice, WIRING.md section 3.1) | |
| C5 | 10 nF ceramic capacitor | 3 | T+/T- filter, if the breakout lacks one | |
| C6 | 40-pin GPIO header breakout / screw-terminal HAT (optional) | 0-1 | Robust connections in a vibrating vehicle | |
| C7 | USB-C (female) to USB-A (male) adapter or cable, short | 1 | P2 Pro to the Pi | |
| C8 | Micro-USB cable, short, data-capable | 1 | IWR6843AOPEVM to the Pi | |
| C9 | Cable ties, heat-shrink, Kapton tape, wire labels | 1 lot | Harness | |

## D. Housing (supplied) and its fasteners

The housing, front plate and aluminium heat shield are the user's (HOUSING.md section 1). Listed here only so the
build is complete; buy nothing for them unless the build manual says so.

| # | Part | Qty | Purpose | Price (fill in) |
|---|---|---|---|---|
| D1 | Printed PETG housing, 180 x 140 x 72 mm, 4 mm walls (supplied by the user) | 1 | Body | |
| D2 | Bolt-on front plate 172 x 66 x 3 mm with camera hole, 1.2 mm radar window and flux-disc hole (supplied) | 1 | Sensor face | |
| D3 | Aluminium heat shield, 10 mm in front of the front plate (supplied; apertures: see HOUSING.md section 3) | 1 | Radiant-heat shield | |
| D4 | M3 screws for the floor rails (M3 pilot holes every 10 mm), length per the build manual | 1 set | Mount the boards on the rails | |
| D5 | Pi standoffs for the 58 x 49 mm pattern (M2.5 is the Raspberry Pi hole size), length per the build manual | 4 | Pi mounting | |
| D6 | Stainless tubes for the air-probe radiation shield (about 20 and 32 mm dia, 80 mm) + spacers | 1 set | `tc_air` shield | |
| D7 | High-temperature black paint, Pyromark-type | 1 | Disc coating (absorptivity to be measured) | |
| D8 | Flat window/door-seal pass-through cable or door-seal grommet | 1 | 12 V cable entry to the cabin (MOUNTING_AND_POWER.md) | |

## E. Storage and cooling

| # | Part | Qty | Purpose | Price (fill in) |
|---|---|---|---|---|
| E1 | microSD, high-endurance, 64 GB (or a USB SSD) | 1 | OS + `records/` | |
| E2 | Pi 5 Active Cooler, or a Pi 4 heatsink case insert | 1 | Avoid throttling in a closed box | |

## F. Laptop side (not part of the roof unit)

| # | Part | Qty | Purpose | Price (fill in) |
|---|---|---|---|---|
| F1 | macOS laptop running `apps/crossing` | 1 | Decides CLOSED / CROSS FAST / SPRAY THEN RE-CHECK / REOPENED | |
| F2 | 12 V -> USB-C PD laptop charger | 1 | Laptop power in the vehicle | |

## G. Test aids

| # | Part | Qty | Purpose | Price (fill in) |
|---|---|---|---|---|
| G1 | Trihedral corner reflector, about 10 cm | 1 | Test B (radar range, loss through the 1.2 mm window and the shield) | |
| G2 | Hot-air gun | 1 | Test F, polarity checks | |
| G3 | USB power meter (USB-A and USB-C) + bench supply 0-30 V 5 A | 1 each | Power budget measurement, brown-out test | |
| G4 | Reference thermocouple reader (calibrated) + a spare K probe | 1 | Thermocouple cross-check; front-plate and radar-window temperature during test F | |
