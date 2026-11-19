# METHOD: radiant heat at the road from published fire-behaviour and solid-flame methods

Nothing here is new. Each step is a published relation, used inside its stated range where one is stated; where the
use goes beyond it, that is said. Parameters are frozen in PROTOCOL.md section 4 and `kcf_radiation/protocol.py`.
Units: m, s, kg, kJ, kW, K.

## 1. Rate of spread from the arrival-time raster

A front that moves at normal speed R satisfies the eikonal equation |∇t| = 1/R for its arrival time t(x)
(Osher and Sethian 1988; Sethian 1999, *Level Set Methods and Fast Marching Methods*, ch. 1; the same relation is
the basis of minimum-travel-time fire growth, Finney 2002, *Can. J. For. Res.* 32:1420-1424). So

    R = 1 / |∇t|.

`ros.py` takes central differences on the 375 m grid (one-sided at the edge of the burned area) and limits R to
0.001-2.5 m/s.

**Range and caveats.** The relation is exact for a smooth front. On a 375 m grid it gives a spread rate averaged
over 375-750 m, so it smooths short runs and cannot see a front inside a cell. Where t comes from interpolated
detections (the KFS reconstructions, ordinary kriging of satellite detection times) or from a screening reach curve
(the replay rasters, research/kcf-replay MEASURED arm), R is that field's speed, not a measured flaming-front speed;
spotting makes the apparent speed of a reconstructed front larger than the flaming front's. Flat patches of equal
arrival time give an undefined gradient; those cells get R_max (PROTOCOL 3).

## 2. Byram's fireline intensity

    I = H w R      (kW/m)

Byram (1959), "Combustion of forest fuels", in Davis (ed.), *Forest Fire: Control and Use*, McGraw-Hill, 61-89.
H = heat yield, 18,000 kJ/kg: the low heat of combustion (about 18,600-20,000 kJ/kg dry) reduced for fuel moisture
and incomplete combustion, as recommended by Alexander (1982), "Calculating and interpreting forest fire
intensities", *Can. J. Bot.* 60:349-357. w = fuel consumed in the flaming front (kg/m2), not total consumption
(Alexander 1982).

**Range.** Defined for any quasi-steady front; observed values span < 10 kW/m (creeping litter fires) to
> 100,000 kW/m (crown fires; Alexander 1982). The uncertainty is mostly in w (section 3).

## 3. Fuel

Per cell only the Copernicus Global Land Cover 2019 class (100 m, mode-resampled to 375 m) is known. Each class is
mapped to a fuel group with low / middle / high parameters (PROTOCOL 4.2):

| group | w (kg/m2) | CBH (m) | CBD (kg/m3) | CFL (kg/m2) | sources |
|---|---|---|---|---|---|
| conifer (P. densiflora) | 0.50 / 0.76 / 1.10 | 5.2 / 4.4 / 3.6 | 0.13 / 0.20 / 0.27 | 1.27 / 2.12 / 3.08 | Won et al. 2006 (Uiseong surface fuel, shrub layer and below: 7.64 t/ha pure pine, 10.99 t/ha with mid-storey; USDA RMRS-P-41); Kim et al. 2020, *J. Environ. Sci. Manag.* (Gyeongbuk P. densiflora crown fuel: CBH 3.6-5.2 m, CBD 0.13-0.27 kg/m3 for needles and branches < 1 cm); CFL = CBD x (15 m - CBH) |
| mixed | as conifer | as conifer | half | half | ASSUMED |
| broadleaf (leaf-off) | 0.10 / 0.54 / 0.81 | – | – | – | Won et al. 2006 (1.01 t/ha); Scott and Burgan 2005 TL6 |
| shrub | 0.35 / 1.17 / 1.46 | – | – | – | Scott and Burgan 2005 SH1 / SH2 / SH5 |
| grass and other | 0.09 / 0.25 / 0.48 | – | – | – | Scott and Burgan 2005 GR1 / GR2 / GR4 |

Scott and Burgan (2005), *Standard fire behavior fuel models*, USDA RMRS-GTR-153. Foliar moisture 100 %
(Van Wagner 1977's reference value; spring conifer foliage is near it).

**Quality.** This is the weakest input. Land cover is a 2019 classification, not a fuel map; the repository has no
Korean stand-level fuel or forest-type map (research/kcf-idea-forecast SURVEY). Korean crown-fuel measurements exist
for a few Gyeongbuk stands only (Kim et al. 2020 note how few there are). The low-high range spans about a factor of 2
in w and 2.4 in CFL; section 8 carries it through.

## 4. Crown-fire initiation and flame length

**Initiation** (Van Wagner 1977, "Conditions for the start and spread of crown fire", *Can. J. For. Res.* 7:23-34):

    I0 = (0.010 CBH (460 + 25.9 FMC))^1.5      (kW/m)

Crown fire when the surface intensity reaches I0. **Active crowning** when R >= R_active = 3.0 / CBD (m/min; Van
Wagner 1977). In between, the crown fraction burned (Van Wagner 1993; Scott and Reinhardt 2001, *Assessing crown fire
potential by linking models of surface and crown fire behavior*, USDA RMRS-RP-29):

    CFB = 1 - exp(-a (R - R_init)),  a = -ln(0.1) / (0.9 (R_active - R_init)),  R_init = I0 / (H w).

Total intensity I = H (w + CFB CFL) R.

**Flame length**, the surface / crown split used in US fire-behaviour practice:

* surface fire: Byram (1959) L = 0.0775 I^0.46 (Rothermel 1991 eq. 2: L = 0.45 I^0.46 in ft and Btu/ft/s);
* crown fire: Thomas (1963) L = 0.0266 I^(2/3) (Rothermel 1991, *Predicting behavior and size of crown fires in the
  Northern Rocky Mountains*, USDA INT-438, eq. 3: L = 0.2 I^(2/3) in ft and Btu/ft/s; Thomas, "The size of flames
  from natural fires", *9th Symp. (Int.) on Combustion*). Rothermel notes that Byram's relation "seriously
  underpredicts" crown flames. FARSITE's manual (Finney 1998, RMRS-RP-4) gives the crown initiation, active-crowning
  and crown-intensity equations used here but not a flame-length equation; that FlamMap uses Thomas for crown flames
  is as the brief states and was not checked in its documentation.

**Range.** Byram's relation was fitted to low- and moderate-intensity surface fires (roughly I < 3,000-4,000 kW/m;
Alexander and Cruz 2012). Thomas's comes from buoyant-plume scaling and laboratory crib fires, and is the accepted
choice for crown flames. Alexander and Cruz (2012), "Interdependencies between flame length and fireline intensity
in predicting crown fire initiation and crown scorch height", *Int. J. Wildland Fire* 21:95-113, show that the
flame-length-intensity relation depends on the fuel complex; across fuel types the scatter is about a factor of 2,
which is the test used in check C3. Van Wagner's criterion was calibrated on conifer stands with CBH about 1-12 m.

Here R is the observed spread rate, not a modelled surface rate. A crown-driven R inflates the surface intensity
used in the initiation test, so crowning is over-triggered: the conservative direction for heat.

## 5. Flame tilt, flame height and radiant flux

### 5.1 Tilt and height

Albini (1981), "A model for the wind-blown flame from a line fire", *Combustion and Flame* 43:155-174:

    tan θ = 1.22 U / √(g H),   H = L cos θ

θ from the vertical, U the wind acting on the flame. U = WAF x U10 / 1.15 (10 m to 6.1 m open wind, Turner and
Lawson 1978; WAF 0.4 open, 0.2 under canopy, 1.0 for crown flames; Albini and Baughman 1979, Andrews 2012
RMRS-GTR-266). U10 is the hourly ECMWF IFS wind at the cell's arrival hour.

**Range and evidence.** Wind-tilt correlations are poorly supported by field data: Nelson and Adkins (1986, *Can. J.
For. Res.* 16:1293-1300) advise against field use of their laboratory correlations, and Weise and Biging (1996, *Can.
J. For. Res.* 26:1849-1858) found Froude-number equations underestimate measured flame angles. So the worst-angle
envelope of 5.3 is carried alongside.

### 5.2 Emissive power and transmissivity

E = ε σ T^4 with ε = 1 and T = 1200 K (Butler and Cohen 1998); range 1090 K (AS 3959-2018, Method 2) to 1400 K.
Atmospheric transmissivity τ = 2.02 (P_w x)^-0.09 (TNO "Yellow Book", CPR 14E, ch. 6; often attributed to
Pietersen and Huerta 1985, not confirmed), P_w the water-vapour partial pressure (Pa) from RH and air temperature
(Alduchov and Eskridge 1996), x the path length; stated for 10^4 < P_w x < 10^5 Pa m and clipped to τ <= 1 below
that. AS 3959 uses Fuss and Hamins (2002, *Fire Safety J.* 37:181-190) instead, stated for 10-200 m paths and
1273-1873 K sources, outside most of this study's range.

### 5.3 View factor: four geometries

The flame is a flat radiating sheet along the front, of width W = 375 m (one cell; the result barely depends on W
once W >> d), seen by a vertical receiver 1.5 m above ground facing the fire.

| view factor | geometry | source |
|---|---|---|
| planar (McGuire) | vertical rectangle of the flame height; closed-form corner-rectangle sum | McGuire 1953, *Heat transfer by radiation*, Fire Research Special Report 2, HMSO; Howell's catalogue B-3. The Butler and Cohen (1998) geometry |
| tilted (baseline) | sheet of length L tilted θ toward the receiver; numerical integration of ∫ cos β1 cos β2 / (π r^2) dA | exact for the sheet; equals McGuire at θ = 0 (tested to 1e-4) |
| worst angle | the tilt that maximises the view factor | AS 3959-2018 Method 2; used for wildfire safety distances by Zárate, Arnaldos and Casal 2008, *Fire Safety J.* 43:565-575 |
| cylinder (Mudan) | vertical cylinder of diameter W and the flame height, target at W/2 + d from its axis | Mudan 1984, *Prog. Energy Combust. Sci.* 10:59-80 (and Mudan and Croce, SFPE Handbook); a shape comparator, not the line-fire geometry |

The brief also names "Mudan-Sparrow" and "Rai-Kalelkar". "Mudan-Sparrow" is not a standard citation; the likely
referent is Mudan's closed-form (tilted) cylinder view factors, derived with Sparrow's contour-integral method
(Sparrow 1963, *J. Heat Transfer* 85:81-88), which is the cylinder row above. Raj and Kalelkar (1974, *Assessment
models in support of the Hazard Assessment Handbook (CG-446-3)*, Arthur D. Little for the US Coast Guard, report
CG-D-65-74) model LNG pool-fire flames as tilted cylinders; their view-factor details were not obtained, and the
geometry is the same cylinder family. Neither adds a line-fire geometry beyond the four in the table.

Flux: q(d) = τ E F(d). Safe distance d*(q*): the smallest distance beyond which q < q*, by bisection.

### 5.4 Butler and Cohen 1998

Butler and Cohen (1998), "Firefighter safety zones: a theoretical model based on radiative heating", *Int. J.
Wildland Fire* 8:73-77: a flat vertical flame sheet 20 m wide, ε = 1, 1200 K, no attenuation (parameters as listed
by Butler 2014, *IJWF* 23:295-308, Table 1); with a 7 kW/m2 tolerance a linear fit gives a separation of about
4 x flame height. Check C1 reproduces it (RESULTS.md) and shows that a long front needs about 8 x flame length
(Rossi et al. 2011).

## 6. Fire radiative power

Combustion rate = 0.368 kg/MJ x FRP (Wooster et al. 2005, "Retrieval of biomass combustion rates and totals from
fire radiative power observations", *J. Geophys. Res.* 110, D24311); intensity I_FRP = H x 0.368 x FRP / L_f with
L_f the front length in the pixel, taken as √(scan x track). L_f is unobserved (a partly burning pixel has a shorter
front, a pixel with two fronts a longer one), FRP saturates and misses obscured flames, and the 0.368 factor carries
about ±5 % (Wooster) but varies by fuel (Freeborn et al. 2008 found 0.453). The check is order-of-magnitude only.

## 7. Road closure

PROTOCOL section 6; `closure.py`. Closure of a road piece = the time the front comes within d* of it, read from the
cell's arrival A, spread rate R and d*: A - (d* - δ) / R. For a piece inside its own cell this is the existing contact
closure moved earlier by the lead d*/R. With d* = 0 it reproduces the road layer's instance exactly (tested).

## 8. Uncertainty carried

Flame temperature 1090-1400 K (E changes by a factor 2.7); view factor planar / tilted / worst angle / cylinder;
fuel low / middle / high; transmissivity on / off. RESULTS.md gives the spread in safe distance and in the road
counts for each.

## 9. Limits

* **Fuel data quality.** Land-cover classes, not fuel maps; Korean crown-fuel data from a few stands; no fuel moisture
  in w. The largest single uncertainty in I, hence in L and d*.
* **375 m resolution.** Arrival and R are cell values; the front's position inside a cell is unknown. The contact
  rule already closes a whole cell when the fire first touches it, which is itself a spatial margin of up to ~530 m.
* **Radiation only.** No convective heating, no flame contact beyond the cell rule, no embers or spot fires, no
  smoke or visibility.
* **Geometry.** A single straight front facing the receiver; no flanks, junctions or multiple fronts (which add);
  flat ground (slope is not used: a fire on a slope below the road tilts toward it); no shielding by vehicles,
  terrain or trees, and no vehicle body: the receiver is a bare vertical surface.
* **Thresholds.** 7 kW/m2: Butler and Cohen's tolerance (second-degree burn to bare skin in under about 90 s; NWCG
  safety-zone basis). 4.7 kW/m2: API 521 (5th ed. onward: emergency actions of 2-3 min in appropriate clothing; pain
  after about 16 s). 2.5 kW/m2: ISO 13571 / Purser (SFPE Handbook): tolerable for about 30 min. None is a validated
  limit for people inside vehicles.
* **No field validation.** C2 is model-to-model. C3 compares flame lengths, not flux at a road.
