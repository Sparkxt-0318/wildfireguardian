# PROTOCOL: published heat methods for road closure (kcf-radiation)

Frozen 2026-11-19, before any result on fire data was computed. Later changes are logged as amendments at the end,
with the reason, and never overwrite this text. The numbers are also frozen in code: `kcf_radiation/protocol.py`.

## 1. Question and stance

Replace the project's own heat law (`research/kcf-heat`, whose FDS gate was not passed) with established, published
methods, chosen for accuracy, with their uncertainty stated. No new method is proposed. Every formula is cited, with
its range, in METHOD.md.

The chain, per 375 m road cell and issue hour:

1. rate of spread R from the fire-arrival raster (eikonal relation);
2. fuel consumed from the cell's land-cover class (published loads, low / middle / high);
3. Byram's fireline intensity I = H w R;
4. Van Wagner's crown-fire initiation test; flame length by Byram (surface) or Thomas (crown), as FARSITE and
   FlamMap do; crown fraction burned by Van Wagner (1993) / Scott and Reinhardt (2001);
5. flame tilt in wind (Albini 1981) and flame height H = L cos(tilt);
6. radiant flux by the solid-flame model q = tau E F; safe distance d*(q*) where q falls below a threshold q*;
7. road closure: a road piece closes when the front comes within d* of it (section 6).

## 2. Inputs

As listed in DATA.md. The data folder named in the brief ("wildfire 3 (1)") could not be reached; the environment
rasters come from the earlier release `wildfire (2).zip` of the same workspace; FIRMS 2022-2023 from the public
yearly country files. No key is read or stored.

## 3. Rate of spread

* R = 1 / |grad t|, t = arrival time (s), central differences on the 375 m grid where both neighbours are finite,
  one-sided where only one is (kcf_radiation/ros.py).
* Limits: R_min = 0.001 m/s, R_max = 2.5 m/s (150 m/min, 9 km/h; above the 8.2 km/h press-reported maximum of the
  Gyeongbuk fire used by research/kcf-replay's RUNNING stand-in). A cell with zero or undefined gradient gets R_max
  (the larger intensity). The number of limited cells is reported per input.
* Inputs read: the replay GeoTIFFs and the finals packets on the routing grid (the full grid, not only road cells);
  the reconstructed arrival rasters of the four KFS fires for the per-fire tables and the FRP check.

## 4. Fire behaviour and radiation parameters

4.1 Heat yield H = 18,000 kJ/kg (Alexander 1982).

4.2 Fuel groups from the Copernicus LC100 class (fuels.py `LC_TO_GROUP`): conifer (needle-leaf forest), mixed
(mixed and unknown forest), broadleaf (broadleaf forest; leaf-off in March-April, so no canopy fuel), shrub, grass
(herbaceous, cropland, wetland and every non-vegetated class: a cell the arrival raster marks as burned is read as
the lightest fuel, not as unburnable). Values (low / middle / high; high = hazardous):

| group | w surface (kg/m2) | CBH (m) | CBD (kg/m3) | CFL (kg/m2) | FMC (%) | source |
|---|---|---|---|---|---|---|
| conifer | 0.50 / 0.76 / 1.10 | 5.2 / 4.4 / 3.6 | 0.13 / 0.20 / 0.27 | 1.27 / 2.12 / 3.08 | 100 | w: Won et al. 2006 (Uiseong P. densiflora, shrub layer and below: 0.76 pure stand, 1.10 with mid-storey; low = 2/3 of 0.76 for incomplete consumption). CBH, CBD: Kim et al. 2020 (Gyeongbuk P. densiflora; CBD = needles + branches < 1 cm). CFL = CBD x (15 m - CBH), 15 m = median GEDI-Landsat canopy height of the burned KFS_01 cells. FMC: Van Wagner 1977 reference value |
| mixed | as conifer | as conifer | half of conifer | half of conifer | 100 | ASSUMED: half the conifer canopy (broadleaf part leaf-off) |
| broadleaf | 0.10 / 0.54 / 0.81 | – | – | – | – | low: Won et al. 2006 (Uiseong broadleaf); middle, high: Scott and Burgan 2005 TL6 1-h, 1-h + 10-h |
| shrub | 0.35 / 1.17 / 1.46 | – | – | – | – | Scott and Burgan 2005 SH1, SH2, SH5 (1-h + live woody) |
| grass | 0.09 / 0.25 / 0.48 | – | – | – | – | Scott and Burgan 2005 GR1, GR2, GR4 (1-h + live herb) |

4.3 Crown fire: crown when I_surface >= I0 = (0.010 CBH (460 + 25.9 FMC))^1.5; CFB from R between
R_init = I0 / (H w) and R_active = 3.0 / CBD (m/min); total intensity H (w + CFB CFL) R; flame length by Thomas
L = 0.0266 I_total^(2/3) when crowning, else Byram L = 0.0775 I_surface^0.46. R is the observed spread rate from the
raster (not a modelled surface spread rate), so I_surface is that of a surface fire moving at the observed rate; this
over-states surface intensity when the observed spread is crown-driven, which over-triggers crowning (the conservative
direction for heat).

4.4 Tilt: tan(theta) = 1.22 U / sqrt(g H), H = L cos(theta) (Albini 1981), solved together; U = WAF x U10 / 1.15,
WAF = 0.4 (grass, shrub), 0.2 (surface fire under forest canopy), 1.0 (crown fire). U10, RH and air temperature: the
hourly ECMWF IFS rasters at the hour nearest the cell's arrival.

4.5 Radiation (baseline): flame = flat radiating sheet of length L, tilt theta, front width W = 375 m (one cell);
emissive power E = eps sigma T^4 with T = 1200 K, eps = 1 (Butler and Cohen 1998); view factor by numerical
integration over the tilted sheet (exactly McGuire's closed form at zero tilt); receiver vertical, facing the fire,
1.5 m above ground; transmissivity tau = 2.02 (P_w x)^-0.09 <= 1 (Pietersen and Huerta 1985), x = distance to the
sheet's centre of area. Flux is not evaluated closer than 0.5 m to the flame.

4.6 Safe distance d*(q*) = smallest d beyond which q < q*, by bisection to 1 cm, at inputs rounded to the
conservative side (L up 1 %, tilt up 0.5 degree, P_w down 5 %; table.py).

4.7 Thresholds, graded: q* = 7 kW/m2 (Butler and Cohen 1998: tolerance of a firefighter in protective clothing),
4.7 kW/m2 (API 521: emergency actions of 2-3 min by personnel without shielding but with appropriate clothing),
2.5 kW/m2 (tenability limit for skin exposure; ISO 13571, Purser). Every result is given at all three, as soft
margins, not one line.

## 5. Intensity from satellite fire radiative power

For each VIIRS / MODIS detection in a burned cell of a KFS fire whose time is within 1 h of the cell's reconstructed
arrival: I_FRP = H x 0.368 kg/MJ x FRP / L_f (Wooster et al. 2005), L_f = sqrt(scan x track). Reported: the ratio
I_model / I_FRP (middle fuel; and low, high) per fire, median and 10-90 % range. This is a cross-check of order of
magnitude, not a pass/fail test: L_f is not observed and the reconstructed arrival is itself built from detections.

## 6. Road closure

A road piece p (graph edge chord split by 375 m cell) closes at b(p) = min over cells c with arrival A_c within the
horizon of A_c - max(0, d*_c - delta(p, c)) / R_c, for delta(p, c) < d*_c or p in c; floored at 0; permanent. Nodes
(waits, origins, shelter stays) use the same rule at the node's point. With d* = 0 this is exactly the existing
contact rule (tested). The deadline field, shelters (3 nearest), dwell (120 s) and acceptance are
product/wfg-roadlayer's unchanged engine. Packets: cells without native data are read as not reached (the roadlayer's
--assume-uncovered-not-reached), for every variant alike.

The old kcf-heat law in the same rule: R = 341 m/h and d* = R T*(q*), T* = chi E_A / (2 pi q*) - t_r / 2 rounded up
(chi 0.30, E_A 18,608 kJ/m2, t_r 11.52 s); comparison (b) uses it at the same three thresholds.

## 7. Panels and outputs

7.1 Panel A: Gyeongbuk 25 March 2025 replay, 13 issue hours (12:00-24:00 KST) x 2 regions, MEASURED arm, 8 h.
Panel B: the 15 finals packets (5 regions, 1 h). Per-fire tables (no routing): the four KFS reconstructed fires.

7.2 Per road cell and input: R, fuel group, wind, I, crown, CFB, L, tilt, flame height, d* and lead d*/R at each
threshold, the flux at the road from the adjacent earlier-burning cell (front at that cell's nearest edge) and its
zone, and the closure time under each variant.

7.3 Counts against (a) no heat and (b) the old law, at each threshold, for the baseline and the settings fuel
low / high, T 1090 / 1400 K, view factor planar / worst-angle (AS 3959 Method 2) / Mudan cylinder, no transmissivity:
road cells whose closure time changes; leave-by times (origins x inputs with a leave-now window) that change, and by
how much; origins that lose every window. The share of road cells whose d* is below 375 m is reported, and if that is
nearly all of them RESULTS.md says so plainly.

## 8. Checks (step 2) and the gate for step 4

C1 Butler and Cohen. With their assumptions (flat vertical sheet, eps = 1, T = 1200 K, tau = 1), d(7 kW/m2) / H must
be independent of H (within 5 % for H = 2-20 m at a fixed width ratio W/H) and equal 4 +/- 0.5 at a width ratio
within the range they state. Also: McGuire's closed form equals the numerical integral at zero tilt (1e-4), Mudan's
cylinder formula equals direct integration (1 %), q(d) is decreasing, every formula's constants are tested
(tests/test_physics.py).

C2 FDS. Model-to-model only. (i) The C064 grass fire of research/kcf-heat (I = 4.47 MW/m, W = 60 m, R = 1.29 m/s,
receiver 1.5 m): the method's flux against FDS's radiometers and the voxel sum, per distance bin. (ii) The local FDS
runs: the plane-layer verification (radiation solver against an analytic value) and the 240 kW propane strip
(solid flame against FDS at 0.6 / 1.6 / 2.6 m, calm). Pass: the method is not below FDS in any C064 bin at d >= 1 m
(not on the unsafe side of the only independent radiation solver available). The ratio is reported either way.

C3 Flame length against published observations for the same fuel types: (i) crown fires, ICFME (Stocks et al. 2004;
Taylor et al. 2004: flames 18-25 m at 0.5-1.0 m/s); (ii) pine-litter surface fires (Nelson and Adkins 1986);
(iii) grass and shrub surface fires (RxCADRE 2012, Butler et al. 2016; the C064 grass fire flame height). The
observed intensity is used where the source reports it; otherwise the intensity is computed with this protocol's
fuel values. Pass: every predicted / observed flame length within a factor of 2 (the scatter documented by Alexander
and Cruz 2012 for Byram-type relations across fuel types).

C4 Sensitivity: T 1090-1400 K, the view-factor choice, fuel low / middle / high; the spread in safe distance is
reported on representative cells (one conifer crown, one conifer surface, one grass) and over the panels. No pass/fail.

Gate: step 4 (wire into product/wfg-roadlayer as the heat option, replacing the old law) proceeds only if C1, C2 and
C3 pass. The option is default off unless it changes answers on the panels (any leave-by time changed at the
baseline 4.7 kW/m2 setting), in which case RESULTS.md states the change and the default is decided there.

## 9. Not covered

Convection and flame contact beyond the cell rule, smoke, embers and spotting, terrain shading and slope effects on
flame geometry (slope is not used), vehicle shielding, multiple fronts adding flux, fuel moisture effects on w.
METHOD.md section 9 discusses each.

## Amendments

**A1 (2026-11-19, after the C1 numbers for a fixed width ratio were seen; before any panel, fire or C3 result).**
The literature check (Butler 2014, *IJWF* 23:295-308, Table 1) found that Butler and Cohen (1998) used a **fixed 20 m
flame width**, 1200 K, emissivity 1 and a vertical flame, not a fixed width-to-height ratio. With a fixed width,
d/H is not independent of H, so the C1 criterion of section 8 ("independent of H ... at a fixed width ratio") does not
describe their model. C1 is replaced by: with W = 20 m, 1200 K, eps = 1, tau = 1, vertical flame, the linear fit
(through the origin) of d against H for H = 1-10 m must lie within 15 % of each published result for that geometry:
Butler and Cohen 1998 (4 H at 7 kW/m2), Zarate et al. 2008 (3.8 H at 7 and 4.8 H at 4.7 kW/m2, as reported by
Butler 2014); and for a long front (W/L > 50) within 15 % of Rossi et al. 2011 (8 x flame length). The H range of the
fit (1-10 m) is chosen because Butler and Cohen's guidance addresses flames of that size and their safety-zone note
("more than 20 m wide") implies flames of a few metres; it was chosen after seeing that the fit depends on the range,
and RESULTS.md reports the other ranges too. Both C1 tables (fixed ratio and fixed width) stay in data/c1_butler_cohen.json.

**A2 (citations, no change to numbers).** (i) The Thomas crown flame length is cited to Rothermel (1991) INT-438
eq. 3 (L = 0.2 I^(2/3) in ft and Btu/ft/s, = 0.0266 I^(2/3) in m and kW/m); FARSITE's manual (Finney 1998) contains
the crown-fire initiation and intensity but not the flame-length equation. (ii) The transmissivity power law
tau = 2.02 (P_w x)^-0.09 is cited to the TNO Yellow Book (CPR 14E, ch. 6); its attribution to Pietersen and Huerta
1985 could not be confirmed. AS 3959 uses Fuss and Hamins (2002) instead; that alternative is not used here (it is
stated for paths of 10-200 m and source temperatures 1273-1873 K, outside most of this study's range). (iii) 4.7
kW/m2: API 521 (5th ed. onward: emergency actions of 2-3 min; time to pain 16 s). 2.5 kW/m2: ISO 13571 and Purser
(SFPE Handbook): tolerable for 30 min or more.

**A3 (computation, before any panel result).** For the worst-angle view factor only, the water-vapour pressure used
for transmissivity is rounded down in 50 % steps instead of 5 % (each evaluation needs ~100 numerical integrations).
Rounding down raises transmissivity, so d* can only grow.

**A4 (C3 data, before any C3 result).** The crown-fire comparison uses the per-plot intensities and spread rates of
Stocks et al. (2004, Table; I = H w R with H = 18,000 kJ/kg, 11 plots, 13,400-93,500 kW/m) against their reported
flame fronts "commonly 25-40 m above the ground" (a height; no flame length reported). Pass for a plot: the predicted
flame length lies within a factor 2 of the nearest end of 25-40 m. Pine-litter and grass comparisons have no paired
observations available in the sources obtained (Alexander and Cruz 2012 full text not obtained); they are reported as
range comparisons and do not count toward the gate.

**A5 (computation, after the first 12 panel inputs; no count had been read for the decision).** Routing all 31
variants single-process took over an hour per Yeongdeok input. From then on: the eight sensitivity settings are
routed at 4.7 kW/m2 only (their safe distances are still tabulated at all three thresholds), variants with identical
closures are routed once, and the field runs with 6 worker processes. The counts use only the variants routed in
every input (none; old law at 7 / 4.7 / 2.5; baseline at 7 / 4.7 / 2.5; each sensitivity setting at 4.7).

**A6 (exploratory analysis added after the panel results were seen; not part of the frozen method).** Panel B's
lost windows were traced to cells inside the known fire area, whose flat arrival field takes the capped spread rate
(section 3). One extra variant, "known-fire cells silent" (d* = 0 for cells with a zero or undefined arrival gradient,
baseline otherwise, 4.7 kW/m2), was run on both panels to measure that effect (`run_panels.py --front-only`,
`data/panels/exploratory_front_only.json`). It is reported as exploratory and does not change the method, the counts
of the main rows or the road layer.

**A7 (2026-11-20; a fix to the method for cells burning at issue. Written before the rerun. The results it responds to HAVE
ALREADY BEEN SEEN: RESULTS.md as merged at PR #228, including the 22 of 425 lost windows on panel B and the exploratory
row of A6).**

*Problem.* Section 3 gives a cell with zero or undefined arrival gradient the capped rate R_max = 150 m/min. Cells inside
the known fire at issue (arrival exactly 0: `current_active` or `known_burned` in a packet, inside a detection disc in a
replay raster) have a flat arrival field, so they got R_max, hence a crown flame of about 50 m and d* of about 290 m. That
closes road pieces next to the known fire at second 0 and produces 22 of the 425 panel B lost windows. The cap there is a
stand-in for a missing measurement, not a spread rate, and A6 showed that the effect is the whole of the panel B result.

*What changes (section 3 only, for known-fire cells with a flat or undefined gradient).* The spread rate is not read from
the flat field. It is the **median of the spread rates of the 3 nearest cells that have a real arrival gradient** (finite
and positive |grad t|, spread rate computed exactly as before and limited to [R_min, R_max]); nearest = centre distance on
the 375 m grid, donors may be anywhere in the grid (inside or outside the known fire), flat cells are never donors. If the
input has no cell with a real gradient, the cell gets no spread rate and no flame (d* = 0); the number of such cells is
reported. Cells outside the known fire that have a flat or undefined gradient (an isolated cell reached later) keep the
cap, as before. Nothing else changes: fuel, wind, crown test, flame, view factor, thresholds, closure rule (section 6),
panels, settings and the old-law comparison are those of sections 4-8 and A1-A6.

*Rule chosen and why.* The alternative, treating those cells as burned out with no flame front after a residence time,
was rejected because it needs the age of the burn at issue, and the inputs do not have it: the packets label
`known_burned` cells as "burned with unknown age", and the replay rasters store 0 for every disc cell whatever the disc's
time. Any residence time would be applied to an age that is not known, and a residence time long enough to switch off
the old interior would also switch off the active perimeter, which radiates. So the rule here carries **no residence
time**; it uses only the observed spread of the same fire near the cell. It keeps radiating from burned-out interior
cells (conservative), and it can still give a crown flame where the nearby observed spread is above the crown threshold.
The A6 "silent" row is kept as the lower bound; it is not the fix.

*Test.* A test fails if any known-fire cell with a flat or undefined gradient receives the default cap (provenance
flag), and on the 15 finals packets and the 26 replay inputs it checks that none does.

*Method of the rerun (data).* The data folder "wildfire 3 (1)" is not reachable from where this ran (no computer attached,
no Drive file access), and the environment rasters of the earlier archive are not in the repository. The 15 packets and the
road graphs are fetched from the public release (`tools/fetch_routing_inputs.py`, hash verified); the 13 replay rasters
are rebuilt by `build_example_raster.py` (the 03:00 one is byte-identical to the committed one). Fuel group, 10 m wind and
relative humidity per road cell are read from the committed per-road-cell tables `data/panels/road_cells_panel_{A,B}.csv.gz`;
air temperature, which those tables do not hold, is recovered per cell from the recorded baseline d* at the three
thresholds. Check, stated in advance: the same script run with the old rule must reproduce the old table of RESULTS.md. Any
difference is reported next to the new table, and the old column of the side-by-side table is the reproduced one.

*Reporting.* Old and new table side by side for both panels at 7, 4.7 and 2.5 kW/m2 (and the settings rows), every
leave-by time that differs between the rules, the test result, and what did not improve.
