# F-C1 see-before-leave gap: definitions (draft for verification, v1)

Status: **design decision, not yet computed for all 174 places.** For Hannah to verify and Iris to assess before
the full run. Nothing here changes routing, forecast, planner or published results.

## Question

For each place and recorded input time in the 2025 replay, does the planner's leave-by deadline come before the
first time the fire could be seen from that place within the same scenario? If it does, a resident who waits to see
the fire leaves too late by construction.

**gap = D - t_vis** (minutes). D = leave-by deadline. t_vis = first-visible time. A negative gap means waiting to
see is too late.

## What the replay data can and cannot support (checked before defining anything)

Measured from the frozen inputs (`data/routing`, release `research-final-20261015`). Reproduce with
`python3 seebefore/feasibility.py`.

1. **The scenario horizon is 1 hour.** Every HAZARD packet has `valid_until = 3600 s`. Beyond +60 min, the scenario
   says nothing about the fire. So t_vis is either known in [0, 3600] s or right-censored (> 3600 s).
2. **Within the hour, the fire is almost entirely the fire already burning at the input time.**
   - The packet build summaries list present-fire cells of 28, 10, 466, 240, 48 and 12 for the six inputs.
   - New ignitions are 0–9 cells per member per hour.
   - In practice, then, t_vis is 0 (the fire burning now is visible), a member's new-ignition time, or > 3600 s.
3. **The routing packet is a crop and omits most of the burning fire.** The full forecast grid (KFS_01 export npz,
   79 x 237 cells of 375 m) has 30, 18, 1505, 1443, 160 and 40 active cells at the six inputs. Only 28, 10, 466,
   240, 48 and 12 of them lie inside the packet domain (`outside_domain_fire` is an unsupported channel).
   **Visibility must use the full-grid active fire.** A resident can see fire that the routing model omits.
4. **D is usually not a fire deadline.** Among the 522 cases:

   | Class | Cases | Meaning |
   |---|---:|---|
   | `grid_end` | 354 | checked at every departure up to +50 min; true deadline ≥ 50 min (censored) |
   | `window` | 132 | deadline set by the 1-hour window; the fire-only deadline is unknown and ≥ D |
   | `fire_or_limits` | 15 | the next departure (D + 10 min) fits the window but was not checked; true deadline in [D, D + 10 min) |
   | none | 21 | no checked route at any departure |

   These counts reproduce `NUMBERS.json`.

Consequence: the sign of the gap can be decided only in these cases:

| Case | Condition | Gap |
|---|---|---|
| (a) | the fire is visible at t = 0 and a leave-by exists | gap ≥ D ≥ 0: **not negative** |
| (b) | a fire-set deadline (`fire_or_limits`) and t_vis > D + 10 min | **negative** (t_vis > 3600 s is enough) |
| (c) | t_vis known inside the hour and D a genuine bound | computed |

Every `grid_end` or `window` case where the fire is not visible at t = 0 is **indeterminate**. The 21 no-route cases
are reported separately: there is no leave-by, and visibility is moot for the deadline.

## Visibility model (the major decision)

| Item | Primary | Sensitivity | Why / direction of bias |
|---|---|---|---|
| Surface | Copernicus GLO-30 DSM (2021 release), bilinear to EPSG:5179, 30 m | none planned (FABDEM bare-earth optional) | DSM includes canopy and buildings partially (X-band), so it acts as the obstruction surface; a bare-earth DEM would over-state visibility through forest |
| Earth curvature | drop d²/(2R)·(1 − k), R = 6,371 km, k = 0.13 | none | matters at > 10 km (27 m at 20 km) |
| Observer | OSM place point, eye 2 m above DSM | (i) eye 10 m; (ii) best of 9 points: centre + 8 at 250 m radius | a village is not a point; the best-point variant is an optimistic "someone in the village can see it" |
| Target cell | each active 375 m fire cell, 3 x 3 sub-points (125 m spacing); a cell is visible if any sub-point is | none | the front occupies part of a cell; any-sub-point visibility is optimistic (earlier t_vis). That biases **against** finding negative gaps, so negative counts are conservative |
| Flames | target top 10 m above DSM surface | 2 m (surface fire), 30 m (crown fire) | flames on the far side of a ridge are hidden until the ridge no longer blocks |
| Night glow | 150 m above surface; only at night inputs | 50 m, 300 m | glow lights the plume base and the underside of smoke; not computed for daylight inputs |
| Smoke | column 1,000 m above surface | 300 m, 3,000 m | forest-fire plumes commonly reach 1–5 km; **smoke result is an upper bound on visibility** (drift, haze and night ignored) |
| Range cap | none inside the 79 x 237 grid (≈ 89 x 30 km) | flames capped at 15 km | fire outside the export grid is unknown |
| Required height | per (observer, sub-point): minimum target height above surface for line of sight, h_req = max over path samples of [(g(f) − z_eye)/f] − (z_t − z_eye), with g the surface plus curvature drop at fraction f; samples every 15 m | none | one pass serves every height threshold |

**Time of day of the inputs:**

| Input | KST | Daylight |
|---|---|---|
| Uiseong-Andong 1 | 2025-03-23 10:00 | day |
| Uiseong-Andong 2 | 2025-03-24 18:00 | dusk (sunset ≈ 18:50) |
| Uiseong-Andong 3 | 2025-03-26 02:00 | night |
| Yeongdeok 1 | 2025-03-26 04:00 | night |
| Yeongdeok 2 | 2025-03-26 08:00 | day |
| Yeongdeok 3 | 2025-03-26 17:00 | day |

## Fire set at time t (per scenario member)

| Part | Cells | When visible-eligible |
|---|---|---|
| Present fire | full-grid cells with `heat__initial_active_burning_probability > 0` (exactly 1 wherever > 0) | t = 0 |
| New ignitions | member flame cells not in the present set, from the HAZARD packet; flat index is row-major with **row 0 = south** (verified: 240/240 and 466/466 present cells match the npz under row 0 = south, 9/240 and 44/466 under row 0 = north) | first visible from the start of the member interval in which they become active |

- **Per-member t_vis** = the earliest such time.
- **Per-case** results report the minimum and maximum t_vis over the 4 members. The planner's leave-by already
  requires all 4 members to pass.

## Known limits (reported, not fixed)

- **Forecast quality.** The forecast failed its superiority test against persistence. The "present fire" is the
  thresholded retrospective kriged arrival field at the cutoff, not an observation.
- **Unknown burned state.** 7,768 of 18,723 grid cells have an unknown burned state and can hide fire.
- **No smoke physics.** No plume rise model, no wind drift, no visibility in haze, no night-time darkness of smoke.
- **The observer point is the mapped OSM point.** It is not the road entry point used for departures, and residents
  are spread out.
- **Seeing is not the same as noticing.** Line of sight is necessary, not sufficient, for a resident to notice and
  act. The result is a bound.
