# Test E: 30-minute drive, unit on the roof, laptop inside

Status: protocol written 2026-11-17, not yet run. Print and fill in by hand. No fire. See also
`hardware/vehicle-unit/docs/MOUNTING_AND_POWER.md` section 1 for the roof installation.

## Purpose

Measure, as recorded: link dropouts between the roof unit and the laptop, GNSS quality along the track (fix
ratio, hdop distribution, map), power (under-voltage events, throttling), temperatures (CPU, housing, intake-height
air) and data completeness per sensor over a 30-minute drive.

## Equipment

| Item | Notes | Tick |
|---|---|---|
| Car with the roof attachment as in the build manual, rated for the unit's mass and the planned speed | | [ ] |
| Roof unit, cable through the door seal / flat window cable, 12 V socket power with the fused lead | | [ ] |
| Laptop secured inside (not on a lap of the driver), joined to the unit hotspot | | [ ] |
| Optional: the crossing app running with its research log (separate WebSocket client) | | [ ] |
| Planned route (mixed: open road, trees, an underpass if possible), written below | | [ ] |

## Safety and legality

- **The driver only drives.** A second person operates the laptop.
- Check the mount before driving and after 5 minutes; stop at once if anything moves.
- Keep to the speed limit and to the mount's rated speed (MOUNTING_AND_POWER.md, placeholder).
- The radar is an evaluation module: check whether operating it on a public road is allowed where you drive. If
  unsure, use private ground or a closed road.
- No flames, no fuel, nothing is tested on other road users.

## Steps

1. Start the unit (engine running first, so the crank dip happens before recording, or note it if not).
2. `python -m field_tests.e_vehicle_record --duration-s 1800 --vehicle "..." --route "..." --driver "..."`
3. During the drive, type a note + Enter at events: "tunnel", "trees", "bump", "stop", "Wi-Fi icon off".
4. After the drive, copy the Pi session from `hardware/vehicle-unit/records/<session_id>/` to the laptop (scp or
   rsync), next to the run. If the unit rebooted there are two sessions: copy both.
5. `python -m field_tests.e_vehicle_analyse --pi-session <pi session> --laptop records/field_tests/E/<run> --out records/field_tests/E/analysis`

## What to record (by hand)

| Item | Value |
|---|---|
| Date, start/end time | |
| Vehicle, mount type, unit position on the roof | |
| Route (roads, underpass, trees) | |
| Weather, air temperature, sun | |
| Max speed reached | |
| Mount check after 5 min / at the end | |
| Anything heard or seen (rattle, Wi-Fi icon, laptop sleep) | |

## Known limits

- One drive on one car is one sample. GNSS quality depends on the receiver, antenna position and sky view.
- Laptop receipt gaps include laptop-side pauses (sleep, CPU load); keep the laptop on mains power and awake.
