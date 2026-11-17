# Test C: thermal near-edge distance at set distances and tilts

Status: protocol written 2026-11-17, not yet run. Print and fill in by hand. No flame is used in test C.

## Purpose

Measure the error of the app's near-edge distance (`crossing.geometry.near_edge`, the flame-base distance along the
ground) against a tape measure, with a heated panel standing on the ground as the flame-base stand-in, at
distances 3-15 m and camera-body tilts of -5, 0 and +5 deg. The IMU must see the tilt; the analysis also shows
the error when the IMU is ignored.

## Equipment

| Item | Notes | Tick |
|---|---|---|
| Roof unit (TC001 + BNO055) on a tripod or the vehicle, streaming | Same mount as planned | [ ] |
| Heat source: electric hot plate (or heated steel panel) standing on its edge, about 0.4 x 0.5 m | Bottom edge on the ground | [ ] |
| Stable non-flammable stand / bricks so it cannot tip over | | [ ] |
| Tape measure (30 m), ground marks at 3, 5, 8, 11, 15 m | Measured from the point under the lens | [ ] |
| Wedges for -5 / 0 / +5 deg tilt of the camera body; digital inclinometer to check | | [ ] |
| Spirit level (ground grade along the line) | | [ ] |
| Contact thermometer for the panel surface | | [ ] |
| Extension cable with RCD, cable ramp | | [ ] |

## Safety

- The panel surface is hot enough to burn; nobody touches it; a guard or cones around it.
- Stand it so it cannot tip over; keep the cable out of walkways (trip hazard); RCD on the supply.
- Nothing flammable against the hot face. Switch off and let it cool before moving it.

## Set-up

1. Flat ground. Measure the grade along the line of sight with the level and write it on the sheet
   (`ground_grade`, rise/run, + uphill away from the camera).
2. Measure the camera lens height above the ground (`camera_height_m`). **Nearest visible ground** for a level
   camera is about h / tan(21 deg) = 2.6 x h (vertical field of view 42 deg): 2.6 m for h = 1.0 m, 3.9 m for
   h = 1.5 m, 6.8 m for the 2.6 m roof height. Nose-up tilt makes it farther. A run whose panel base is below the
   image is reported as "not observable", which is a valid result. For the 3 m point use h <= 1.0 m.
3. Set the threshold in the sheet (`t_detect_c`) below what the panel reads (the TC001 reads a painted panel
   lower than a contact thermometer); 150 C is the template value.

## Steps

For each tilt (-5, 0, +5 deg) and each distance (3, 5, 8, 11, 15 m), in a written random order:

1. Place the panel with its bottom edge on the mark, face towards the camera, centred in the image.
2. Put the wedge under the camera body; check the tilt with the inclinometer and write it down.
3. `python -m field_tests.c_thermal_record --sheet field_tests/sheets/C_inputs.yaml --distance-m 8 --tilt-deg 5`
4. At "hold ... NOW" nobody moves for 10 s.

Analysis: `python -m field_tests.c_thermal_analyse --runs records/field_tests/C --out records/field_tests/C/analysis`

## What to record (by hand)

| Tilt (deg) | Inclinometer (deg) | Distance mark (m) | Tape to panel edge (m) | Panel surface (C) | Sun / wind | Notes |
|---|---|---|---|---|---|---|
| | | | | | | |
| | | | | | | |
| | | | | | | |

## Known limits

- Flat surveyed ground; the DEM and IMU-plane slope sources of the app are not tested here.
- A panel edge is sharper and hotter than a real flame base; a vegetation-hidden or cool flame base makes the real
  near edge read farther away, which this test cannot show.
- TC001 lens distortion is not corrected in the app; the error at the image edges is therefore part of the result.
