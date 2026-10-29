# Radiation law v2: `wfg.radiation.law/2-flamefront`

Opt-in research library in `experimental/flame-front-radiation/src/wfg_flamefront/` (NumPy only). It does not change the frozen kit, the released construction law `wfg.hazard.construction/1`, any frozen result or any published claim. Evidence and numbers: `research/flame-front-radiation/README.md`. This is a model; nothing here is field validated.

## Why v2 exists

The released law treats each burning 375 m cell as a horizontal isotropic source sheet 5 m above an upward-facing receiver, emitting `0.30 x w f H / T = 0.30 x 10 x 0.1 x 18,608 kJ/kg / 3,970.46 s = 1.406 kW/m2` per unit ground area for an hour. All coplanar sources together subtend at most 2 pi sr, so the flux anywhere is at most half of that, **0.703 kW/m2**, against a 10 kW/m2 routing limit. Peak flux therefore cannot bind, and the final-input ablation found that peak and dose limits changed no outcome.

A real front is a moving line of flames a few metres tall. The hazard to a road is set by the distance to that line during the minutes it passes. **Sub-cell position is the whole point**: the dangerous radiant zone is tens of metres (two to four flame heights). A receiver at the centre of an unburned 375 m cell is 190 to 375 m from a front in the neighbouring cell; even an infinitely wide 30 m flame wall at 290 kW/m2 gives at most about 23 kW/m2 at 190 m, and a finite front gives a few kW/m2. The peak check can only bind for roads inside or along the edge of a burning cell, so v2 uses the road's position within its cell and the front's position within the burning cell, never cell-centre distances.

## Equations

**Arrival field.** From a member's v1 arrays, every cell centre gets an arrival time tau: new ignition `b`; present fire `R_max - T` (the bridge's scalar maximum-remaining enclosure; per-cell `r - T` optional); known burned and inactive `-T`; never ignited `horizon + T`; unknown state excluded and counted (`unsupported_cells`). `T = 3,970.46 s` and `R_max` come from the packet's `REPORT.json`.

**Interpolant and isochrone.** Each dual square (corners at four cell centres) is split into four triangles at its centre, where the value is the bilinear centre value. tau is linear on each triangle, equal to the bilinear interpolant at the corners, along square edges and at the centre (marching squares with centre-value saddle disambiguation). The front at time t is the level line tau = t: a straight piece per crossed triangle, cut at the square midline into pieces that each lie in one host cell.

**Contact consistency.** A piece is kept only if its host cell is active at t under the v1 member activity (`flame` frames, or rebuilt from ignition, T, present fire and R_max). v2 flames are therefore a subset of v1 flaming cells. A route that passes the unchanged v1 contact test cannot be inside a v2 flame; any v2 exposure on such a route is radiation across a cell boundary.

**Rate of spread.** `R = 1 / |grad tau|` per triangle, clipped to 3 m/s. Direction: unit vector of +grad tau (the direction in which arrival time increases).

**Intensity and flame.** Byram (1959): `I = H w R` (kW/m; H = 18,608 kJ/kg, w = 0.1 x 10 = 1.0 kg/m2 consumed in the flaming front, scalar or per-cell), `L = 0.0775 I^0.46` (m). Tilt `tan theta = 1.4 U / sqrt(g L)` (Froude form attributed to Nelson and Adkins 1986, coefficient not verified here), height `L cos theta`, lean `L sin theta` downwind. The frozen packets carry no wind field, so every routing run uses vertical flames.

**Radiation.** Each piece carries a planar panel (base on the piece, height = flame height, top shifted by the lean), both faces emitting E. View factor from a differential receiver by Lambert's contour formula `v = (1 / 2 pi) sum_i gamma_i u_i`, `F(n) = n . v` (Howell, Menguc and Siegel; catalogue configuration B-3 is a unit test). Receiver `worst_case`: `F = |v|` per panel; `vertical_facing(theta)`: horizontal normal. `q = tau_a sum E F` over pieces within 500 m ground distance. A receiver inside the flaming band (`tau(x) <= t < tau(x) + residence`, host active) receives the in-flame value (E by default). Residence 11.52 s (export policy).

**Truncation at 500 m.** For a straight front at distance d, the omitted part is at most `E h d / (pi Y^2)` with `Y^2 = Rc^2 - d^2`, against at least `E h / (2 sqrt(h^2 + d^2))`, so the relative error is at most about `2 d^2 / (pi Y^2)`: 0.65 % at d = 50 m, 2.7 % at 100 m. Large convoluted fronts add more (measured on the largest Korean fire: 0.14 kW/m2 at 20 m and 0.15 at 400 m when the cutoff is removed), which is reported as a sensitivity.

**Dose.** Linear `integral q dt` (kJ/m2) and thermal dose units `integral q^(4/3) dt` ((kW/m2)^(4/3) s). Reference TDU: pain about 92, first-degree burn about 105, second-degree about 290, third-degree about 1000; 1 % lethality about 1000, 50 % about 2000. Eisenberg lethality probit `Pr = -14.9 + 2.56 ln(t q^(4/3))` with q in kW/m2 (with q in W/m2 the constant becomes -38.48; the 23.58 shift is the commonest copying error). AS 3959-2018 bands: BAL-12.5, BAL-19, BAL-29, BAL-40 by their upper limits, flame zone above 40 kW/m2.

## Enclosure argument (`flux_enclosure`)

For an axis-aligned receiver box X and closed interval [a, b]:

- Every point-law piece is the level line tau = L of one half-triangle for some L in [a, b], and its host is active somewhere in [a, b]. In the frame aligned with the half's level lines, all such pieces lie in a box: along the lines, the half cut by `Lmin <= tau <= Lmax` (vertices are half vertices inside the band and edge crossings of the two levels); across them, the exact band `[ (Lmin - tau0) / |g|, (Lmax - tau0) / |g| ]` (tau is linear); vertically [0, flame height of the half] (one rate per half); horizontally widened by the maximum lean. Minkowski difference with X gives a box containing `panel - x` for every x in X.
- For any receiver orientation the configuration factor of a panel is at most its solid angle over pi and at most 1, and the box's solid angle is exact (sum of visible faces). Upper radiation term: `sum tau_a E min(1, Omega / pi)` over the candidate halves; by default halves whose bounding box is farther than the cutoff from X are dropped, as the point law drops them (`truncate=False` keeps all and bounds the untruncated sum).
- Engulfment term: the in-flame value for any half whose host is active in [a, b] and whose part inside X can satisfy `tau <= b`, `tau + residence > a` (exact extremes of a linear field on a convex polygon).
- Upper = max(engulfment, radiation) x (1 + 1e-9) + 1e-12; never below any point value in X x [a, b] (term-by-term domination), and monotone in X and [a, b]. Lower = the in-flame value when X lies in one active host cell and inside the band throughout [a, b]; otherwise 0. A tighter rigorous lower bound outside the flame needs orientation enclosures and is not provided. 1,000 random boxes and intervals and nested shrinking are unit tests.

## v1 versus v2

| | v1 `wfg.hazard.construction/1` | v2 `wfg.radiation.law/2-flamefront` |
|---|---|---|
| Emitter | whole 375 m cell, horizontal sheet at 5 m | flame panel on the front line, Byram height |
| Emission | areal average 1.41 kW/m2 radiant for an hour | E = 100 kW/m2 (default) from the flame surface |
| Timing | cell flaming on [b, b + T), T = 3,970 s | front crosses the cell; a point flames for 11.52 s |
| Receiver | cell centre, facing up, 0 m | any point, worst-case orientation, 0 m |
| Global maximum | 0.703 kW/m2 | E inside the flame; tens of kW/m2 within metres |
| Inputs | v1 member arrays | the same v1 member arrays |
| Rigour | outward interval bounds in the kit | point law plus a solid-angle enclosure |

## Emissive power: specified default and a measurement-consistent variant

The specified default E = 100 kW/m2 (surface) and 200 kW/m2 (crown) agrees within three times with the Butler and Cohen (1998) four-flame-height rule and with Zarate et al. (2008), but over-predicts the Morandini et al. (2006) measured decay for 2.5 m shrub flames on a 30 m plot by 2.9, 5.1 and 6.7 times at 5, 10 and 15 m, and the Pimont et al. (2014) FIRETEC crown values by 4 to 6 times. Under the stop rule of the track the model was fixed before any routing run by separating the panel emissive power from the in-flame value: `FuelParameters(emissive_power_kw_m2=..., inflame_emissive_power_kw_m2=...)`. The minimax fit to the Morandini decay is **E = 22.6 kW/m2** (within 1.52 times at all three distances, inside Frankman et al. 2013's measured 20 to 115 kW/m2 surface range). Packham and Pompe's 57 kW/m2 at 7.6 m needs E of at least 81 kW/m2 at any flame height, so the effective E grows with flame size (thin flames are not black); one constant cannot fit both. The library default stays 100 (conservative, Contract C unchanged); every binding statistic is reported for both.

**Flame-depth emissivity (human decision, 29 October 2026).** The option `FuelParameters(emissivity_model="flame_depth")` uses `E = (1 - exp(-k D)) sigma T_f^4` with flame depth `D = R x residence` and literature constants, not fitted: k = 0.72 m^-1 (Àgueda, Pastor, Pérez and Planas 2010, Int. J. Thermal Sciences 49:543-554; about 0.7 m^-1 also in Johnston, Wooster and Lynham 2014) and T_f = 1200 K (Butler and Cohen 1998). The decision rule fixed in advance: if every comparison is within three times, the depth law becomes the headline and the default for track 1C; otherwise E = 100 stays the headline with E = 22.6 as the sensitivity, without tuning. Result (`physics_validation/VALIDATION.json`, `depth_law_decision`): within three times for Butler and Cohen (0.53 to 1.05), Zarate (0.80 to 1.11), Packham and Pompe (0.83 to 1.17), Frankman (0.83 and 2.41) and Butler 2004 (0.59), but **3.43 and 4.53 times above Morandini et al. 2006 at 10 and 15 m and 3.48 and 3.52 times above the Pimont et al. 2014 FIRETEC values at 30 and 50 m; worst factor 4.53**. The depth law is therefore not adopted: **E = 100 kW/m2 is the headline, E = 22.6 kW/m2 the sensitivity**. This was fixed and committed before any routing outcome was inspected; the depth law remains available as an option.

## Threshold discussion

The routing thresholds are unchanged: 10 kW/m2 peak and the per-scenario dose budgets of each request (kJ/m2; 100 kJ/m2 for most missions, between 0.06 and 1,339 kJ/m2 for the others, including incurred exposure). They were designed for law v1. Candidate thresholds a fire-community reviewer would recognise:

- Peak: 12.5 kW/m2 (upper limit of AS 3959 BAL-12.5) instead of 10; for a vehicle, the CSIRO burnover tests' 10 to 40 kW/m2 range says that a peak limit alone is not protective because untenability inside was driven by smoke and particles after about 10 minutes.
- Dose: a thermal dose cap in TDU instead of linear kJ/m2, for example 92 TDU (pain) for exposed people or 290 TDU (second-degree burn); the linear kJ/m2 budget weights low fluxes as heavily as high ones, which TDU does not.

The research README reports, side by side for the same returned routes, how many fail at the current thresholds and at 12.5 kW/m2 and 92 / 290 TDU. The routes were not re-planned under the proposed thresholds.

## Not modelled

Convective heating (comparable to radiation at the front in surface fires and extending two or more flame lengths ahead on slopes and in wind), smoke and toxic gases, ember attack, vehicle shielding, flame emissivity below the declared E, atmospheric attenuation (transmissivity 1), slope, crown fire transition, spotting, and any wind in the frozen packets. Emissive power, residence time and fuel consumption are literature or repository values, not Korean measurements.
