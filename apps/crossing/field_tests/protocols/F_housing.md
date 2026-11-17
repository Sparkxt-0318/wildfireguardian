# Test F: housing, water spray and hot-air gun

Status: protocol written 2026-11-17, not yet run. Print and fill in by hand. No flame: the hot-air gun stands in
for radiant heat and says nothing about flame exposure. Expectations are in
`hardware/vehicle-unit/docs/HOUSING.md` section 8.

## Purpose

Check that the unit keeps running and keeps reporting truthfully while wet and hot: no heartbeat gaps > 2 s, no
reboot, no sensor that stops while its heartbeat says "ok", housing and CPU temperatures below the placeholder
limits, no throttling or under-voltage, no lost WebSocket, plate and air thermocouples respond correctly.

## Equipment

| Item | Notes | Tick |
|---|---|---|
| Assembled roof unit, lid closed, all glands fitted, 12 V supply | Supply and connectors OUTSIDE the spray zone | [ ] |
| Laptop (dry, at least 3 m away), joined to the hotspot | | [ ] |
| Garden hose with spray nozzle (not a pressure washer) | | [ ] |
| Hot-air gun, model and setting: __________ | | [ ] |
| Paper towels (water-inside check), torch | | [ ] |
| Gloves, safety glasses, CO2 extinguisher | | [ ] |

## Safety

- 12 V is low voltage, but the supply feeding it must be protected: battery outside the spray zone, or a mains
  bench supply on an RCD and kept dry.
- Hot-air gun: hot nozzle (burns), never at people, nothing flammable within 1 m, park it on its stand.
- Stop the hot air at once if `tc_housing` passes 55 C, the radome deforms, or anything smells hot.
- Do not aim the hot air directly at the germanium window.

## Steps

1. `python -m field_tests.f_housing_record --hot-air-gun "..." --spray "..." --operator "..."`
2. Follow the phases at each NOW: baseline (2 min) -> spray on all faces (5 min, keep moving) -> spray off (1 min)
   -> hot air on the front face and shield (4 min, about 20 cm away) -> hot air on the flux plate (2 min) -> hot air
   on the air probe (2 min) -> off (1 min).
3. While spraying, watch the app: no FLAME status from water alone (smoke and mist must not trigger).
4. At the end, answer the checklist questions (the script asks): open the lid, paper-towel test for water inside,
   radome and window condition, plate condition.
5. Copy the Pi session of the same time next to the run, then:
   `python -m field_tests.f_housing_analyse --run records/field_tests/F/<run> --pi-session <pi session>`

## Checklist (tick on paper too)

| Check | Result |
|---|---|
| Water inside (paper towel): none / where | |
| Radome deformed, discoloured, cracked | |
| Germanium window damaged | |
| Plate coating and thermocouple intact | |
| Any FLAME status during the spray (must be none) | |
| Any CROSS FAST / REOPENED caused by spray (must be none) | |
| Condensation inside after 30 min | |

## Known limits

- One spray session is not an IP rating test (IP65/66 is an untested target).
- Housing and CPU limits are placeholders (HOUSING.md section 7) to be set from this test.
- A hot-air gun heats by convection; a flame front heats mainly by radiation.
