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

(none yet)
