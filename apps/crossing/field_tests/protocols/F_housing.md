# Test F: housing, water spray and hot-air gun

Status: protocol written 2026-11-17, not yet run. Print and fill in by hand. No flame: the hot-air gun stands in
for radiant heat and says nothing about flame exposure. Expectations are in
`hardware/vehicle-unit/docs/HOUSING.md` section 7.

**70 C disc limit.** The copper flux disc sits on printed PETG tabs: the hot air must not heat the disc to 70 C.
The record script STOPS the run and prints `STOP: flux disc at X C >= 70 C (PETG tabs)` at a disc reading of
70 C or more (crossing.yaml `flux.disc_max_c`, user-set), and also when the disc temperature is missing or faulted
for more than 2 s during the hot-air and cool phases. The run is kept and marked (`stop_reason` in trial.json,
check `disc_guard_stop` FAIL in the analysis; `disc_limit` FAILs on any disc reading >= 70 C); the script exits 3
after the checklist. **The script only stops the recording: switch the hot-air gun off at once when it fires.**

## Purpose

Check that the unit keeps running and keeps reporting truthfully while wet and hot: no heartbeat gaps > 2 s, no
reboot, no sensor that stops while its heartbeat says "ok", housing and CPU temperatures below the placeholder
limits, no throttling or under-voltage, no lost WebSocket, plate and air thermocouples respond correctly.

## Equipment

| Item | Notes | Tick |
|---|---|---|
| Assembled roof unit (supplied printed housing), front plate bolted on, cable entries as in the build manual, 12 V supply | Supply and connectors OUTSIDE the spray zone | [ ] |
| Laptop (dry, at least 3 m away), joined to the hotspot | | [ ] |
| Garden hose with spray nozzle (not a pressure washer) | | [ ] |
| Hot-air gun, model and setting: __________ | | [ ] |
| Paper towels (water-inside check), torch | | [ ] |
| Gloves, safety glasses, CO2 extinguisher | | [ ] |

## Safety

- 12 V is low voltage, but the supply feeding it must be protected: battery outside the spray zone, or a mains
  bench supply on an RCD and kept dry.
- Hot-air gun: hot nozzle (burns), never at people, nothing flammable within 1 m, park it on its stand.
- Stop the hot air at once if `tc_housing` passes 55 C, the radar window deforms, or anything smells hot.
- Do not aim the hot air directly at the camera hole (12 mm, lens behind it).
- The housing is printed PETG (it softens from roughly 70-80 C; the radar window is thinned to 1.2 mm): keep the
  gun moving, at least 20 cm away, and stop at once if any face or the radar window goes soft or shiny.
- Hot air on the flux plate: aim so the disc warms slowly and stays below about 60 C (watch the live tc_plate
  value); the script stops at 70 C. Inspect the PETG tabs after the phase.

## Steps

1. `python -m field_tests.f_housing_record --hot-air-gun "..." --spray "..." --operator "..."`
2. Follow the phases at each NOW: baseline (2 min) -> spray on all faces (5 min, keep moving) -> spray off (1 min)
   -> hot air on the front face and the aluminium heat shield (4 min, about 20 cm away) -> hot air on the flux
   plate (2 min, disc below about 60 C; the script stops at 70 C) -> hot air on the air probe (2 min) -> off (1 min).
3. While spraying, watch the app: no FLAME status from water alone (smoke and mist must not trigger).
4. At the end, answer the checklist questions (the script asks): open the lid, paper-towel test for water inside,
   radar window and camera hole condition, plate and PETG tabs condition.
5. Copy the Pi session of the same time next to the run, then:
   `python -m field_tests.f_housing_analyse --run records/field_tests/F/<run> --pi-session <pi session>`

## Checklist (tick on paper too)

| Check | Result |
|---|---|
| Water inside (paper towel): none / where | |
| Radar window (PETG, 1.2 mm) deformed, discoloured, cracked | |
| Camera hole / lens wet, damaged or blocked | |
| Plate coating, PETG tabs and thermocouple intact | |
| Run stopped by the disc guard (STOP printed)? peak disc C: ____ | |
| Any FLAME status during the spray (must be none) | |
| Any CROSS FAST / REOPENED caused by spray (must be none) | |
| Condensation inside after 30 min | |

## Known limits

- One spray session is not an IP rating test; the ingress rating of the printed housing is unknown.
- Housing and CPU limits are placeholders (HOUSING.md section 6) to be set from this test.
- A hot-air gun heats by convection; a flame front heats mainly by radiation.
