# Step 8: FDS virtual unit (C064), report

**Everything here is SIMULATED.** The fire is the FDS 6.11.1 C064 grass-fire model. The sensors are modelled
physics run over the FDS fields: a thermal camera (`lwir.py`), the flux plate (`plate.py`) and the radar path
(`radar_path.py`). Nothing was measured with hardware, and no number here is a sensor result.

Run: `python -m virtual_fds.run` from `apps/crossing`. It ran on 2026-11-17 with the code as of that day, which
includes the radar noise floor and noise-rise gate, the solid-echo CFAR, the 2 s effect hold and the DEPTH-HI
decision upper end. Wall time was 154 s. Outputs are in `outputs/`: `results.json`, `results.csv`,
`fig_thermal/flux/plate/radar/depth.png` and `thermal_frames.npz`.

## Truth from FDS

| quantity | value |
|---|---|
| depth (b2 mean) | 11.14 m |
| depth from the 20 kW/m3 edge (40-84 s, 5 s frames) | 11.33 m (range 9-13) |
| ground-level depth (z < 2 m) | 9.78 m |
| spread rate R | 1.303 m/s (b2: 1.290) |
| intensity I | 4473 kW/m |
| radiant fraction chi | 0.318 |
| depth at window ends 50 / 53 / 56 s | 11 / 11 / 10 m |
| flame height at window ends 50 / 53 / 56 s | 5 / 6 / 7 m |

The FDS DEVC 'FIRE DEPTH' reads 4.42 m (2.73-6.64). Its definition was not checked, so it is not used as truth.

## Depth and geometry, per window and distance

Settings: 1 s ROI frames, 8 s track, vehicle at 10, 20 and 30 m from the leading edge. Each depth is given as
value [lo, hi] in m.

Estimators:
- a: spread x burn time
- b: Byram
- c: radar ceiling from the reflector geometry, quantised to the 0.468 m bin
- d: radar flicker extent from the detector (experimental, off)

Coverage of the 11.1 m truth is checked against both the display interval and the interval that ends at the
decision upper end.

| t_end | dist | near edge est vs truth | flame height est vs truth | a | b | c | d | combined depth_m [lo, hi_m] | decision upper end | covers 11.1 (display / decision) |
|---|---|---|---|---|---|---|---|---|---|---|
| 50.03 | 10 | 15.63 vs 10.0 | 2.19 vs 5 | 10.17 [6.19, 16.69] | 2.26 [0.67, 7.56] | 10.48 [9.05, 12.14] | invalid (no flicker bins) | 10.13 [4.82, 21.33] | 21.33 | yes / yes |
| 50.03 | 20 | 26.05 vs 20.0 | 2.60 vs 5 | 10.03 [6.09, 16.50] | 3.30 [0.99, 11.05] | 9.93 [8.50, 11.60] | invalid | 9.98 [4.73, 21.08] | 21.08 | yes / yes |
| 50.03 | 30 | 36.78 vs 30.0 | 2.65 vs 5 | 8.89 [5.30, 14.92] | 3.42 [1.02, 11.45] | 9.06 [7.64, 10.74] | invalid | 8.73 [4.02, 18.96] | 18.96 | yes / yes |
| 53.02 | 10 | 15.25 vs 10.0 | 1.52 vs 6 | 10.87 [6.62, 17.85] | 1.03 [0.31, 3.45] | 10.86 [9.43, 12.52] | invalid | 10.81 [5.13, 22.75] | 22.75 | yes / yes |
| 53.02 | 20 | 26.05 vs 20.0 | 1.88 vs 6 | 10.50 [6.39, 17.27] | 1.62 [0.48, 5.41] | 9.93 [8.50, 11.60] | invalid | 10.44 [4.95, 22.02] | 22.02 | yes / yes |
| 53.02 | 30 | 34.73 vs 30.0 | 2.08 vs 6 | 11.74 [7.07, 19.48] | 2.03 [0.61, 6.80] | 11.10 [9.66, 12.76] | invalid (no flicker beyond near edge) | 11.52 [5.39, 24.62] | 24.62 | yes / yes |
| 56.03 | 10 | 14.54 vs 10.0 | 1.63 vs 7 | 10.34 [6.29, 16.99] | 1.19 [0.35, 3.98] | 10.16 [8.73, 11.82] | invalid | 10.28 [4.88, 21.65] | 21.65 | yes / yes |
| 56.03 | 20 | 25.01 vs 20.0 | 2.40 vs 7 | 10.22 [6.19, 16.90] | 2.76 [0.82, 9.25] | 10.03 [8.61, 11.70] | invalid | 10.13 [4.76, 21.52] | 21.52 | yes / yes |
| 56.03 | 30 | 34.73 vs 30.0 | 2.64 vs 7 | 9.78 [5.85, 16.35] | 3.40 [1.01, 11.37] | 10.16 [8.73, 11.83] | invalid (no flicker beyond near edge) | 9.61 [4.44, 20.76] | 20.76 | yes / yes |

Coverage and the decision upper end:
- The combined depth (a + b) covers 11.1 m in 9 of 9 windows, on both intervals.
- The decision upper end equals hi_m in all 9 windows (source: the combined value), at 18.96-24.62 m.
- The snapshot run (5 s frames) gives a + b = 10.05 / 10.24 / 10.18 m at 10 / 20 / 30 m and covers the truth 3 of
  3 times.

Variant b_only:
- [lo, hi_m] misses 11.1 m in 3 of 9 windows: t53 at 10 and 20 m, and t56 at 10 m.
- In those windows the decision upper end comes from spread_burn (16.99-17.85 m) and covers the truth 9 of 9 times.
- spread_burn feeds the decision upper end even when it is disabled for the mean. That is deliberate and fails
  closed, but it means b_only is not a single-estimator result for the decision upper end.

Failures, as measured:
- The thermal near edge is 4.5-6.8 m too far in 9 of 9 windows.
- The flame height is 1.52-2.65 m against 5-7 m true, 2 to 4.6 times too low. The cause is the 300 °C pixel
  threshold on the modelled LWIR image.
- Byram (b) alone is 3 to 10 times too low.
- Estimator a covers the truth because it is a rate, and the near-edge offset cancels out of it. Its intervals are
  wide (about 4.4-24.6 m) because of the uncalibrated scale of 1.5.
- Estimator c uses the known reflector geometry, not a detected far echo. In the main radar case the detector found
  no far echo in 9 of 9 windows, so the detector itself cannot supply c.

Estimator d, does it work? **No.** It is not a depth measurement. Keep it experimental and off.
- Detector output, main case: invalid in 9 of 9 windows. In 7 the noise-rise gate returns before any flicker is
  scored. In 2 there is no flicker beyond the near edge.
- Oracle d' (true SNR): valid in 9 of 9, but it spans 1.24-35.23 m against 11.1 m true. Its interval covers the
  truth 8 of 9 times only because it is about 3.7 times wide each way.
- Side cases where the detector's d is valid: the value is set by the single reflector bin (reflector bin minus the
  thermal near edge, 9.2-11.6 m). That reflects where the reflector was placed (5 m behind the trailing edge) and
  the near-edge bias, not the flame's thickness. Reflector-only runs with no clutter give the same number.

## Radar flame status

The main case uses the shipped default `config/iwr6843aop_vu.cfg`: 128 bins of 0.468 m, echoes out to 53.96 m,
60.00-60.55 GHz, wavelength 4.97 mm. Ground clutter per bin is scaled by bin length, giving +9.8 dB.

Codes:
- U = UNKNOWN; gate = noise-rise gate (rise in dB in brackets)
- nosolid = no solid echo beyond the near edge
- noref = no reference echo beyond
- FE = FLAME_EFFECT (time held in brackets)
- NE = NO_EFFECT

| config / case | t50: 10, 20, 30 m | t53: 10, 20, 30 m | t56: 10, 20, 30 m |
|---|---|---|---|
| **MAIN** default cfg, clutter, dry | U gate (22.7), U gate (17.9), U gate (10.9) | U gate (23.7), U gate (20.3), U nosolid | U gate (22.6), U gate (17.5), U nosolid |
| default cfg, clutter, wet | U gate, U nosolid, U nosolid | U gate, U nosolid, U nosolid | U gate, U nosolid, U nosolid |
| default cfg, reflector only | U 'no control echo in front of the flame' x 3 | same | same |
| default cfg, clutter NOT scaled (25 dB) | U gate, FE (5.0 s), FE (8.0 s) | U gate, U gate, FE (7.0 s) | U gate, NE, U nosolid |
| long_fine cfg (512 x 0.117 m) | U gate, U gate, U nosolid | U gate, U gate, U nosolid | U gate, U gate, U nosolid |
| short cfg (22.5 m) | U gate, U noref, U noref | U gate, U gate, U noref | U gate, U noref, U noref |
| virtual 60 m x 0.0488 m (old main case) | U gate, FE (3.0 s), FE (5.0 s) | U gate, U gate, FE (5.0 s) | U gate, FE (2.0 s), U nosolid |

**Main result: with the shipped default radar config, the virtual radar never confirms the flame (UNKNOWN 9 of 9),
so the fused flame is UNKNOWN and every verdict is CLOSED.** This fails closed, but on this simulation it means
CROSS FAST can never be reached with the default config.

Causes, all SIMULATED:
- The noise-rise gate reads the refractive phase flicker of strong clutter in front of the flame as a noise rise.
  The FDS gas temperature at the vehicle at z = 2.5 m is a mean of 112 °C (max 158) at 10 m, 62 °C (max 83) at
  20 m and 36 °C (max 46) at 30 m.
- With 0.468 m bins, the corner reflector does not stand 12 dB above the bin-scaled clutter at 30 m or more.
- In the reflector-only run the far echo was found at 26.23 / 36.07 / 45.91 m (t50), against a true reflector
  position of 26.04 / 36.03 / 46.02 m.

FLAME_EFFECT appears in 3-4 of 9 windows only with unscaled clutter or 0.0488 m bins. With the old code, the old
main case's t50 at 10 m was FLAME_EFFECT on a clutter echo at 15.86 m; the new solid-echo test removes it. The
outcome therefore depends on the clutter assumption, which is a placeholder. None of this has been checked on the
EVM.

## Flux at the vehicle

Units are kW/m². The plate sits on RAD_X102 (x = 102 m, z = 1.5 m). The vehicle reaches 10 / 20 / 30 m at
t = 74.03 / 66.55 / 60.05 s.

| distance | FDS radiometer, geomean [range] | plate fed with radiometer input (1 s / 10 s) | closed form, finite / long front | crossing.heat FDS ref | voxel at z = 1.5 m |
|---|---|---|---|---|---|
| 10 m | 0.62 [0.36, 1.06] | 0.50 vs 0.57 / 0.75 vs 0.76 | 12.93 / 14.56 | 0.74 | 11.77 [10.51, 15.11] |
| 20 m | 0.223 [0.147, 0.333] | 0.048 vs 0.19 / 0.236 vs 0.223 | 6.75 / 8.86 | 0.239 | 5.99 [5.56, 7.31] |
| 30 m | 0.0647 [0.0456, 0.116] | 0.131 vs 0.054 / 0.123 vs 0.071 | 4.11 / 6.37 | 0.075 | 3.62 [3.35, 4.28] |

Plate round trip:
- With closed-form or voxel input, the plate tracks its input to about 0.6 kW/m² rms (1 s window).
- Below about 0.3 kW/m² it is noise-limited: at 30 m the 10 s mean reads 0.12 for a 0.07 input.

Convective estimate at z = 2.5 m (h = 12 / 25 W/m²K): 0.97 / 2.01 at 10 m, 0.36 / 0.75 at 20 m and 0.05 / 0.10 at
30 m.

**Outside the flame, the closed form (and the voxel) is about 20x (10 m), 30x (20 m) and 60x (30 m) above the FDS
radiometers.** For the approach and exit part of the dose, the closed form is conservative by that factor.

In the flame:
- At the FDS truth inputs (D = 11.1 m, I = 4473 kW/m, chi 0.30), the closed form gives 38.5 kW/m².
- The C064 in-fuel radiometers give 78.2 kW/m² (RAD_X080, max) and 62.6 kW/m² (RAD_X090).
- So at the true depth, the closed form is about 0.5 times the FDS value. That is not conservative.
- The decision uses the depth lower end and the intensity upper end (q_in = chi x I_hi / (pi x D_lo)). That raises
  the in-flame value, but the in-flame factor has not been checked against FDS on this run. Details:
  `RESULTS.md`, known issues.

## Radar attenuation (estimates)

| cause | one way | two way over 11.1 m |
|---|---|---|
| soot (f_v max 2.82e-7; wavelength 4.85 mm used) | 0.0018 dB/m | 0.039 dB |
| plasma, n_e 1e15 m^-3 (nu 1e11 / 1e12 s^-1) | 0.029 / 0.040 dB/m | 0.64 / 0.89 dB |
| plasma, n_e 1e16 | 0.29 / 0.40 dB/m | 6.4 / 8.9 dB |
| plasma, n_e 1e17 | 2.87 / 4.01 dB/m | 63.9 / 89.2 dB |

Soot is negligible. The plasma rows use an assumed electron density and collision rate (Drude model). FDS has no
ionisation, so these rows are unverified.

## Assumptions changed from the first step 8 run

1. The main radar bins are read from `iwr6843aop_vu.cfg`: 128 x 0.4684 m, echoes only to the IF-limited 53.96 m,
   wavelength 4.974 mm. The first run used 0.0488 m bins to a virtual 60 m at 61.8 GHz.
2. Ground clutter per bin is scaled by bin length: 34.8 dB per antenna at 10 m instead of 25 dB. This assumes the 64
   chirp loops recover the 6 dB lost to the shorter ADC window. UNVERIFIED. The unscaled case is kept as a side
   case.
3. The short case is read from `iwr6843aop_vu_short.cfg`: 512 bins, echoes to 22.48 m.
4. The excess phase is computed per bin geometry and wavelength.
5. The current `radar_flame` and `depth` code is used: noise-rise gate (10 dB), solid-echo CFAR, control echoes,
   2 s minimum effect time, and the DEPTH-HI decision upper end. Estimator d never sets the decision upper end.
6. Estimators c, d and d' use the config's 0.468 m spacing.
7. Two side cases were added: unscaled clutter and long_fine.

Other assumptions, unchanged:
- Corner reflector 45 dB at 10 m, 4 antennas, unit receiver noise.
- 1 s FDS frames are used instead of 0.1 s, and turbulence below 1 m is not resolved.
- LWIR, plate and radar constants are as stated in each module's docstring.
- The first run's committed outputs could not be diffed. `apps/` is untracked, so the old outputs were overwritten
  without a git copy.

## Provenance (sha256)

| file | sha256 | size |
|---|---|---|
| csiro-volume-dt5-120.npz | 7efeca01ee0a1d93b70b3c3acbb9d8bb8a59ea89d0f8d5b03c13247eb7488d88 | 123,438,543 B |
| c064-roi1-full.npz | fba3cc281d2a22455e51bf282888df77313b3e35d20d2ca434d5b3e99da8db32 | 70,098,512 B |
| C064_kcf_radiometers_devc.csv | 4ac5ee00029f67a833bee09bdced22bac069ad6078d942335ddba795598911a1 | |
| b2_fds_compare.json | 076511a175706320938197e3e459d678a22a197a1009366b159b2485bdb2d9e5 | |
| config/iwr6843aop_vu.cfg | ff6e2134e826da57e49859105f2163d9287c20eac6ce9e4dac4aa0375b1e4ef9 | |
| config/iwr6843aop_vu_short.cfg | 314202fdf8511f62f5005192e3cffda10f46541fa3523fdac478117e76fec9ea | |
| config/iwr6843aop_vu_long_fine.cfg | 8a353681d23e7943c7c41c4c0c57bfcbe38e53c7a9c00b8777cb6717a821a770 | |

The two npz files are outside the repository. Their path is recorded in `outputs/results.json` (provenance) and
can be set with `C064_FIRE_DATA`. Over 25 frames, the ROI file and the dt5 volume agree exactly (max abs diff 0
for T, soot and HRRPUV) on an aligned grid.
