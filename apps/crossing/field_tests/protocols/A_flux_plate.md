# Test A: flux plate vs Bunsen burner

Status: protocol written 2026-11-17, not yet run. Print this sheet and fill it in by hand on the day.

**Heat source: a Bunsen burner only.** No other flame, torch, heater or fuel is used in test A. The record script
refuses to start without `--risk-assessment` (scan or PDF of the signed risk assessment) and `--supervisor NAME`.
**The signed risk assessment comes first**: no burner is lit before it is signed and its scan is on the laptop.

**70 C disc limit.** The copper flux disc sits on printed PETG tabs. The record script STOPS the run and prints
`STOP: flux disc at X C >= 70 C (PETG tabs)` as soon as the disc reads 70 C or more (crossing.yaml
`flux.disc_max_c`, set by the user, not a placeholder), and also when the disc temperature is missing or faulted
for more than 2 s. The run is kept and marked (`stop_reason` DISC_OVER_70C / DISC_TEMP_UNKNOWN in trial.json; the
analysis reports it as "STOPPED: disc 70 C"); the script exits 3. **The script only stops the recording: when it
fires, shield the burner and turn the gas off at once.** Start far, step closer: exposure runs go from the
largest distance to the smallest, and you stop stepping closer once a run peaks above about 60 C.

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
- The disc is limited to 70 C (PETG tabs) and is hot up to that: do not touch it; handle the mount with gloves.
- If the script stops with STOP: shield the burner, gas off, let the disc cool below 40 C, inspect the PETG tabs
  (soft, bent, discoloured = stop the session and replace them before any further run).
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
2. At "heat ... NOW": put the burner on a mark that heats the disc to about 55-60 C, never 70 C (find it with
   the first exposure runs: far first, then closer; watch the live tc_plate value). Use `--heat-s` to shorten the
   heating if the disc climbs too fast. If the script stops at 70 C: shield, gas off, see Safety.
3. At "cooldown ... NOW": move the burner away and turn the gas off. Nobody touches or blows on the plate.
4. Repeat for `--repeat 2`. Let the plate return to room temperature (within 2 C of the air) between runs.
   With the 70 C limit the loss fit covers only room temperature to about 60 C; above that it is extrapolated.

Exposure runs (5 distances x 3 repeats). Start far, step closer: begin with every 0.40 m run, then 0.30, 0.20,
0.15 and 0.10 m last (randomise the repeat order within a distance and write it down). Before stepping closer,
check the previous run's peak disc temperature (`plate_max_c` in the analysis, or the live value): if it was above
about 60 C, do not step closer.

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
- The loss model is fitted in still air and only holds in still air, and only up to the 70 C disc limit (about
  60 C in practice): flux at higher disc temperatures uses an extrapolated loss.
- Runs stopped by the disc guard are reported as measured ("STOPPED: disc 70 C"), never dropped; runs with any
  recorded disc sample >= 70 C are flagged and left out of the means and the loss fit.
- A Bunsen flame is not a wildland line fire: the FDS C064 column is a scale check only.
