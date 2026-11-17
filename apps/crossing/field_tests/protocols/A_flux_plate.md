# Test A: flux plate vs Bunsen burner

Status: protocol written 2026-11-17, not yet run. Print this sheet and fill it in by hand on the day.

**Heat source: a Bunsen burner only.** No other flame, torch, heater or fuel is used in test A. The record script
refuses to start without `--risk-assessment` (scan or PDF of the signed risk assessment) and `--supervisor NAME`.

## Purpose

Measure incident heat flux with the roof unit's flux plate (blackened 1 mm copper, K thermocouple on MAX31855) at
5 distances x 3 repeats from a Bunsen flame, and compare with three models drawn from the sheet's inputs:
point source chi*Q/(4 pi r^2), the closed-form line-source law (kcf-heat) mapped onto the flame, and the FDS C064
radiometer curve scaled by I/4473 (a grass-fire reference, not a Bunsen model). Cool-down runs give the plate loss
model (`crossing.flux.fit_cooldown`) that the flux calculation needs.

## Equipment

| Item | Notes | Tick |
|---|---|---|
| Roof unit (plate, tc_plate, tc_air), powered, streaming | Same plate and coating as on the vehicle | [ ] |
| Laptop with `apps/crossing/.venv`, joined to the unit hotspot | | [ ] |
| Bunsen burner, gas tap, approved hose with clips | Hose checked for cracks | [ ] |
| Gas flow meter (rotameter or bubble meter) | Reading referred to 15 C, 1 atm | [ ] |
| Non-flammable base (ceramic tile / steel tray) for the burner | | [ ] |
| Distance jig: rule fixed to the bench, marks at 0.10/0.15/0.20/0.30/0.40 m | Burner axis to plate face | [ ] |
| Radiation shield (sheet of steel or ceramic board on a stand) | Used to switch exposure on/off | [ ] |
| Reference thermometer (room air) | | [ ] |
| Camera + scale for flame photo (width, height) | | [ ] |
| CO2 extinguisher, fire blanket, first-aid kit, burn gel | Within reach | [ ] |
| Heat-resistant gloves, safety glasses | | [ ] |

## Safety (must match the signed risk assessment)

- An adult supervisor is present for the whole session and signed the risk assessment; their name goes into
  every run (`--supervisor`).
- Lab or workshop with ventilation; no draughts (doors and windows closed, fans off) during runs.
- Nothing flammable within 1 m of the burner. Hair tied back, no loose sleeves. Safety glasses on.
- Leak-check the hose joints with soapy water before lighting. Light with a striker, gas on last.
- The plate reaches over 100 C in cool-down runs: do not touch it; handle the mount with gloves.
- The burner is never left lit unattended. Gas off at the tap at the end of every run and on any doubt.
- Stop at once if the hose, the plate mount or anything near the burner starts to smoke or discolour.

## Set-up

1. Plate face vertical, facing the burner axis; plate centre at flame mid-height. The burner is beside the plate,
   never under it (the hot plume must not hit the plate or its mount).
2. Fill in `sheets/A_inputs.yaml`: gas, measured flow, LHV (for natural gas you must look it up), air hole
   setting, flame width and height from a photo against a scale, room air temperature.
3. Keep the air hole setting the same for every run. Note it here: ________

## Steps

Cool-down runs (at least 2, before the exposure runs):

1. `python -m field_tests.a_flux_record --risk-assessment PATH --supervisor NAME --sheet field_tests/sheets/A_inputs.yaml --kind cooldown --repeat 1`
2. At "heat ... NOW": put the burner on the close-range mark (as allowed by the risk assessment). Keep it there.
3. At "cooldown ... NOW": move the burner away and turn the gas off. Nobody touches or blows on the plate.
4. Repeat for `--repeat 2`. Let the plate return to room temperature (within 2 C of the air) between runs.

Exposure runs (5 distances x 3 repeats; randomise the order and write it down):

1. `python -m field_tests.a_flux_record ... --kind exposure --distance-m 0.15 --repeat 1`
2. "background ... NOW": burner lit, shield in place (or burner away). 60 s.
3. "exposure ... NOW": remove the shield / put the burner on the mark. 180 s.
4. "cooldown ... NOW": shield back / burner away. 300 s (the plate cools; this tail is also fitted as a check).
5. Wait until the plate is within 2 C of the air before the next run.

Analysis: `python -m field_tests.a_flux_analyse --runs records/field_tests/A --out records/field_tests/A/analysis`

## What to record (by hand, per run)

| Run | Kind | r (m) | Repeat | Flow (L/min) | Air (C) | Flame w x h (cm) | Air hole | Time | Notes |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |
| | | | | | | | | | |
| | | | | | | | | | |

## Known limits

- Radiant fraction chi is an assumption on the sheet, not measured. The point source assumes an isotropic
  radiator; a Bunsen flame is tall and thin, and close to it the plate sees the flame at an angle.
- Convection from the plume is not separated from radiation; keep the plate beside the flame.
- The loss model is fitted in still air and only holds in still air.
- A Bunsen flame is not a wildland line fire: the FDS C064 column is a scale check only.
