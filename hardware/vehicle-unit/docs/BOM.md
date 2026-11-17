# Vehicle unit bill of materials

Status 2026-11-17: this is a design list. Nothing has been bought against it yet. The prices are left blank on
purpose: fill them in from real quotes. Part numbers are given only where the design depends on them. Otherwise
the entry is a specification, and any part that meets it will do.

## A. Fixed hardware (the user's list)

These parts are given. The rest of the design is built around them.

| # | Part | Qty | Purpose | Price (fill in) |
|---|---|---|---|---|
| A1 | Raspberry Pi 4 Model B (4 GB or more) **or** Raspberry Pi 5 (4/8 GB) | 1 | Sensor head computer: drivers, recorder, WebSocket server, Wi-Fi hotspot. Makes no decisions. | |
| A2 | Topdon TC001 thermal camera (256 x 192, USB-C) | 1 | `thermal`: flame pixels, near edge, flame height | |
| A3 | TI IWR6843AOPEVM, stock out-of-box mmWave demo firmware | 1 | `radar`: range profile, azimuth heatmap, point cloud | |
| A4 | Copper flux plate, 50 x 50 x 1 mm, blackened | 1 | `tc_plate`: thin-skin calorimeter (incident flux, dose) | |
| A5 | K-type thermocouple for the plate (bare wires or fine-gauge, glass-fibre insulated) | 1 | Plate junction | |
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
| C4 | 10 kOhm resistor | 0-1 | GPIO25 pull-up, only for the software chip-select alternative (WIRING.md section 3) | |
| C5 | 10 nF ceramic capacitor | 3 | T+/T- filter, if the breakout lacks one | |
| C6 | 40-pin GPIO header breakout / screw-terminal HAT (optional) | 0-1 | Robust connections in a vibrating vehicle | |
| C7 | USB-C (female) to USB-A (male) adapter or cable, short | 1 | TC001 to the Pi | |
| C8 | Micro-USB cable, short, data-capable | 1 | IWR6843AOPEVM to the Pi | |
| C9 | Cable ties, heat-shrink, Kapton tape, wire labels | 1 lot | Harness | |

## D. Enclosure and mounts (see HOUSING.md)

| # | Part | Qty | Purpose | Price (fill in) |
|---|---|---|---|---|
| D1 | Die-cast aluminium enclosure, about 160 x 220 x 90 mm, gasketed lid | 1 | Roof box | |
| D2 | M16 cable glands, IP68 | 4 | 12 V, air TC lead, GNSS lead, spare | |
| D3 | M12 membrane (pressure-equalising) vent | 1 | Condensation and pressure | |
| D4 | PTFE sheet, 3.45 mm (n = 2) or 1.72 mm (n = 1), about 70 x 70 mm, thickness tolerance stated by the seller | 1 | Radar radome (HOUSING.md section 2) | |
| D5 | Germanium window, 25 mm dia, about 2 mm, AR-coated 8-14 um (or a chalcogenide equivalent) + O-ring | 1 | LWIR window | |
| D6 | Polycarbonate sheet about 2 mm, 90 x 40 mm | 1 | Rear RF (Wi-Fi) window | |
| D7 | Copper sheet (C101/C110), 1 mm, 50 x 50 mm | 1 | Flux plate blank (if A4 is made in-house) | |
| D8 | High-temperature black paint, Pyromark-type | 1 | Plate coating (absorptivity to be measured) | |
| D9 | Ceramic fibre board, 25 mm, 70 x 70 mm | 1 | Plate backing insulation | |
| D10 | Ceramic spacers or washers + stainless screws | 1 set | Isolate the plate from the chassis | |
| D11 | Aluminium sheet 1 mm, about 200 x 260 mm, + 4 standoffs 20 mm | 1 | Sun/heat shield | |
| D12 | Aluminium plate 5 mm, 240 x 320 mm | 1 | Base plate | |
| D13 | Rubber-coated pot magnets, about 88 mm dia, with threaded stud (rated pull stated by the maker) | 4 | Roof mount (steel roofs) | |
| D14 | Roof-bar U-bolt clamps (alternative to D13) | 0-2 | Roof-bar mount | |
| D15 | Tether strap with door-frame hooks | 1 | Secondary retention | |
| D16 | Aluminium angle 20 x 20 x 3 mm | about 0.3 m | Plate bracket | |
| D17 | Stainless tubes for the radiation shield (about 20 and 32 mm dia, 80 mm) + spacers | 1 set | Air probe shield | |
| D18 | Flat window/door-seal pass-through cable (USB or power ribbon), or a door-seal grommet | 1 | Cable entry to the cabin (MOUNTING_AND_POWER.md) | |
| D19 | Wi-Fi: USB adapter with bulkhead antenna (alternative to D6) | 0-1 | Only if the RF window is not enough | |

## E. Storage and cooling

| # | Part | Qty | Purpose | Price (fill in) |
|---|---|---|---|---|
| E1 | microSD, high-endurance, 64 GB (or a USB SSD) | 1 | OS + `records/` | |
| E2 | Pi 5 Active Cooler, or a Pi 4 heatsink case insert | 1 | Avoid throttling in a closed box | |
| E3 | Standoffs (M2.5) and a mounting plate inside the enclosure | 1 set | Board mounting | |

## F. Laptop side (not part of the roof unit)

| # | Part | Qty | Purpose | Price (fill in) |
|---|---|---|---|---|
| F1 | macOS laptop running `apps/crossing` | 1 | Decides CLOSED / CROSS FAST / SPRAY THEN RE-CHECK / REOPENED | |
| F2 | 12 V -> USB-C PD laptop charger | 1 | Laptop power in the vehicle | |

## G. Test aids

| # | Part | Qty | Purpose | Price (fill in) |
|---|---|---|---|---|
| G1 | Trihedral corner reflector, about 10 cm | 1 | Test B (radar range/radome check) | |
| G2 | Hot-air gun | 1 | Test F, polarity checks | |
| G3 | USB power meter (USB-A and USB-C) + bench supply 0-30 V 5 A | 1 each | Power budget measurement, brown-out test | |
| G4 | Reference thermocouple reader (calibrated) | 1 | Thermocouple cross-check | |
