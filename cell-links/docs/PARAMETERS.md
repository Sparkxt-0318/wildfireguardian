# Parameters

Every value used in the models, with its source and status. Status is one of:

- Measured: reported from an observation or experiment in the cited source (FT = full text read, ABS = abstract or landing page only, SEC = seen only as cited by another paper).
- Derived: computed by us from measured values (the calculation is stated).
- Assumed: our choice for this first pass, with the reason.

Full references and URLs are in [data/SOURCES.md](../data/SOURCES.md). Values were checked on 2026-10-14.

## 1. Corrections to the numbers in the prompt

| Prompt statement | What the original says | Status |
|---|---|---|
| 1.6 to 5.8 dB at 8 to 10.5 GHz (Mphale and Heron 2007) | The abstract rounds to "1.6 to 5.8 dB"; the results and conclusion give 1.64 to 5.68 dB. The peak, 5.68 dB at 8 GHz, was 72 s after ignition. These are relative to a 7.2 dB system loss and were measured across a burner 0.5 m in internal diameter. The authors' own inversion of ne and nu treats the values as dB per metre, while their later paper quotes the same experiment as 1.95 to 11.36 dB/m (dividing by 0.5 m). The per-metre value is therefore uncertain by a factor of 2. Use "1.6 to 5.7 dB". | Measured, FT [S1] |
| ne roughly 0.5 to 1.4 x 10^16 m^-3 | 0.51 to 1.35 x 10^16 m^-3, inverted from the attenuation and phase data | Measured (inverted), FT [S1] |
| nu roughly 3.4 to 6.0 x 10^10 s^-1 | 3.43 to 5.97 x 10^10 s^-1 (it increases as the flame cools) | Measured (inverted), FT [S1] |
| Bushfire work: largest losses through the hottest zone | Mphale's 2008 PhD thesis says transmission through the hottest region (combustion zone) suffers significant loss and the cooler plume regions do not. The lab work only measured at the fuel-flame interface at different times. The decrease with height comes from models (PIER 67, PIER 68, thesis chapter 7), not from a measured height profile. | Measured in the lab, modeled with height [S3, S6, S7] |
| A compartment-fire study found flames affect the signal far more than smoke | True for Hong et al. 2021 (wood and foam fires, 0.43 to 2.6 GHz); their kerosene fire gave under 2 dB. Contradicted by Li et al. 2017 (350 to 400 MHz: smoke mattered, the flame did not) and by Bystrov et al. 2021 (79 and 300 GHz: smoke slightly worse than flame, both at most 0.13 dB/m). Treat the statement as contested. | Measured, FT/ABS [S11, S12, S13] |

## 2. Flame and plume plasma

| Quantity | Value | Context | Status | Source |
|---|---|---|---|---|
| Electron density, pine litter flame | 1.35e16 m^-3 (72 s), 7.33e15 (135 s), 5.41e15 (217 s), 5.13e15 (274 s) | Lab burner, 0.5 m, X band | Measured (inverted), FT | S1 |
| Collision frequency, same times | 3.43, 3.56, 5.75, 5.97 e10 s^-1 | Same | Measured (inverted), FT | S1 |
| Electron density, litter flames (pine, eucalyptus, grass) | 0.32 to 3.21e16 m^-3 | 9.8 to 12.5 GHz, flames 730 to 1000 K | Measured (inverted), FT | S2 |
| Collision frequency, same | 1.1 to 4.0e10 s^-1 | Same | Measured (inverted), FT | S2 |
| Specific attenuation, litter flames | 1.0 to 4.5 dB/m across the 0.5 m cavity (pine at 60 s: 4.45 dB/m at 9.8 GHz, 2.73 at 12.5 GHz) | Same | Measured, FT | S2 |
| Potassium content of fuel | Grass 12.9 mg/g, eucalyptus 6.62, pine 3.50; grass flames attenuated more despite being cooler | ICP-AES | Measured, FT | S2 |
| Grassfire ne | Up to 5.1e15 m^-3, assuming nu = 1e11 s^-1. A cold-plasma check with these values overpredicts their measured VHF loss about 40-fold, so treat as inconsistent | 554 kW/m field grassfire, 44 m path | Measured (inverted), FT | S4 |
| VHF field crossings | 0.03 dB/m at 30 MHz, 0.054 dB/m at 151 MHz; total about 0.03 to 0.05 dB over the 44 m path | Same | Measured, FT | S4 |
| Sugarcane fire, 151 MHz | 0.43 dB total over a 590 m path, flames 5 to 10 m, depth 8.7 m | Field | Measured, FT | S5 |
| Mass fire, UHF and X band | Under 5 dB over about 40 m at about 1.7 m above the fuel; ray bending 3 to 9 arcmin | Operation Euroka 1970 | Measured, SEC (via S3) | S8 |
| Hydrocarbon flame, 37 to 250 GHz | Generally under 5 dB through about 0.5 m at about 1000 K; scintillation, not absorption, dominated | Lab | Measured, SEC | S9 |
| Ionization mechanism | Thermal ionization of potassium (4.34 eV); K is up to about 3 percent of plant dry mass (0.05 to 2.71 percent in Australian vegetation) | Review | Measured, FT | S1, S3 |
| Field-bound path-averaged ne | 3.5e14 m^-3 | Gives 5 dB over 40 m at 10 GHz with nu = 5e10 s^-1 (the Euroka upper bound) | Derived | this study |
| K mole fraction in the flame | 1e-5 | Only sets the effective ionization temperature (1620 K); results are insensitive because ne is anchored to measurements | Assumed | |
| O2 electron affinity | 0.448 eV | Used for the electron attachment balance in the cooling plume | Measured | S29 |
| K ionization energy | 4.3407 eV | | Measured | S30 |

## 3. Temperatures, flame heights and plumes

| Quantity | Value | Status | Source |
|---|---|---|---|
| Pine litter surface temperature (lab) | Peak 1081 K at 76 s | Measured, FT | S1 |
| Eucalypt surface fire temperature | About 1100 °C near the flame base, decaying to about 300 °C at the visible tip; mean residence time 37 s | Measured, ABS | S14 |
| Crown fire peak air temperature | Above 1330 °C; radiant flux up to 290 kW/m^2 | Measured, ABS | S15 |
| Mean flame temperature used | 1100 K | Assumed from S1, S14 |
| Crown fire flames (ICFME) | 25 to 40 m above ground, intensity up to 90,000 kW/m, spread 15 to 70 m/min, canopy about 10 m | Measured, FT (partial) | S16 |
| Surface fire flame length | Byram (1959): L = 0.0775 I^0.46 (m, kW/m); 2000 kW/m gives 2.6 m | Empirical, SEC | S17 |
| Crown flame length | Thomas (1963): L = 0.0266 I^(2/3), capped at 35 m above the DSM | Empirical, SEC; cap assumed from S16 | S17 |
| Pool-fire plume regimes | Continuous flame ΔT about 800 °C; intermittent region ΔT ~ 1/z; plume ΔT ~ z^(-5/3) for point sources | Measured, FT | S18 |
| Line-fire plume | ΔT ~ 1/z above a long fireline; we use top-hat Morton-Taylor-Turner similarity with entrainment 0.16 in calm air (an upper bound, since wind bends and dilutes the plume) | Theory; Assumed coefficients | S19 |
| Convective fraction of fire heat | 0.75 | Assumed (radiative fraction 0.2 to 0.3 is typical) | |
| Plume temperature fluctuation | sigma_T = 0.4 x mean excess temperature; outer scale = plume half-width | Assumed from buoyant-plume turbulence measurements (George et al. 1977) | S20 |
| Combustion water | 0.7 kg vapour per 15 MJ of convective heat | Assumed (dry cellulose yields 0.56 kg/kg plus fuel moisture) | |
| Electron loss above the flame | H3O+ dissociative recombination about 4e-7 cm^3/s near 2000 K (lifetime about 0.25 ms at 1e16 m^-3); electron attachment to O2 takes microseconds once air cools | Measured, ABS; Derived | S21 |
| Radio refractivity | N = 77.6/T (P + 4810 e/T) | Standard | S22 |

## 4. Fire behaviour for the Uiseong case

| Quantity | Value | Status | Source |
|---|---|---|---|
| Ignition | 22 March 2025, about 11:24 to 11:25 KST, Anpyeong-myeon Goesan-ri, Uiseong; exact point not verified, we use the Anpyeong-myeon centroid 36.383 N, 128.585 E | Reported; location approximate | S23 |
| Spread | Uiseong to the Yeongdeok coast, about 50 km, between 14:00 on 25 March and 02:00 on 26 March; peak 8.2 km/h reported from satellite thermal data | Reported | S23 |
| Burned area | 99,289 ha (official forest damage, five counties) | Reported | S23 |
| Wind | Gusts up to 27 m/s; mean maximum wind over the burn area 13.7 m/s | Reported | S23, S24 |
| Humidity | 16 percent at 18:00 on 23 March | Reported | S23 |
| Rain | Afternoon of 27 March to dawn on 28 March: 1 to 3 mm | Reported | S23 |
| Telecom | About 2,900 base stations affected nationally across the March fires; Uiseong and Andong outages mainly from power cuts | Reported | S23 |
| Head ROS used | 0.4 m/s (moderate), 1.5 m/s (extreme, 5.4 km/h on flat) | Assumed, bracketing reports | |
| Wind used | Toward the east; 36 and 54 km/h | Assumed from the observed track | |
| Ellipse shape | Alexander (1985) length-to-breadth from wind | Empirical | S25 |
| Slope effect | McArthur: ROS x exp(0.069 theta) | Empirical | S26 |
| Heat content, fuel consumed | 18,000 kJ/kg; 1.5 kg/m^2 surface, 3.0 kg/m^2 crown | Assumed (typical values) | |
| Crown fire threshold | 2000 kW/m (Van Wagner 1977 with crown base 5 m, foliar moisture 100 percent gives about 1900 kW/m) | Derived from S27 | S27 |
| Flaming residence time | 40 s surface, 60 s crown | Assumed from S14 (37 s) | S14 |

## 5. Links and logging

| Quantity | Value | Status | Source |
|---|---|---|---|
| CML frequencies | Typically 5 to 40 GHz; E band 71 to 86 GHz | Review | S31 |
| Hop length versus band | About 7 to 8 GHz for 10 to 40 km; 15 to 23 GHz for 5 to 15 km; 38 GHz for 1 to 5 km; E band under 1 to 5 km (synthesis) | Derived from S31 to S35 | |
| Mean path length | 3.1 km (Netherlands, 13 to 40 GHz); 7.6 km mean, mostly 5 to 10 km (Germany, 10 to 40 GHz); median about 2 km (Gothenburg) | Measured | S32, S33, S34 |
| Antenna height | About 30 m above ground on average (OpenMRG); 30 m used | Measured; Assumed | S34 |
| Clearance rule | Ray clears DSM plus Earth bulge (k = 4/3) by 0.6 F1 | Standard planning practice; Assumed | S36 |
| Logging, Netherlands | 15-min minimum and maximum RSL from 10 Hz sampling, 1 dB resolution, TSL nearly constant (±0.2 dB) | Measured | S32 |
| Logging, Germany | Instantaneous TSL and RSL every 1 min by SNMP; RSL 0.3 dB, TSL 1 dB; ATPC active on 75 percent of links | Measured | S33 |
| Logging, Gothenburg (OpenMRG) | 10 s by SNMP; RSL 0.3 dB, TSL 1 dB; ATPC disabled | Measured | S34 |
| Logging, E band (Prague) | About 10 s, 0.1 dB | Measured | S35 |
| Logging, Korea (KT 6 to 8 GHz) | Tx and Rx power at 15 s and 0.01 dBm in a research setup | Measured | S37 |
| NMS defaults | 15-min or hourly min/max, quantized at 0.1, 0.3 or 1 dB | Review | S31 |
| Dry-weather noise | No canonical value. Examples: OpenMRG example link -46.5 ± 0.5 dB; links over water swing up to 30 dB; Graf et al. flag a 1 h rolling std above 0.8 dB as erratic. We measure it directly from OpenMRG. | Measured | S31, S33, S34 |
| ATPC | Range is set link by link; vendor material cites up to about 30 dB in 1 dB steps; triggered by RSL drop at the far end | Standard, vendor (SEC) | S38 |
| Wet antenna attenuation | Several dB, up to 9 dB in extreme cases | Review | S31 |
| Rain attenuation | ITU-R P.838-3 k and alpha via pycomlink 0.6.0 | Standard | S39 |

## 6. Korean radio links that could act as tripwires

| Network | What is known | Status | Source |
|---|---|---|---|
| Mobile backhaul microwave | Ericsson Microwave Outlook (2025): microwave about 6 percent of backhaul in North East Asia (including China) through 2030; earlier editions call Korea fibre-dense. No Korea-only figure found. | Reported | S40 |
| KT microwave relays | "KT operates microwave links at frequencies of 10 GHz or less that are mainly used for broadcasting and communication relays"; eight 6 to 8 GHz links of 5.7 to 37.4 km in Seoul were logged at 15 s | Measured, FT | S37 |
| KT island and mountain microwave | KT runs an AI monitoring system ("Dr. Microwave") for microwave facilities serving islands and mountains; no link count | Reported | S41 |
| 6 GHz incumbents | When 5.925 to 7.125 GHz opened to unlicensed use (2020), outdoor use was limited to protect carrier island links and broadcaster content links | Reported | S42 |
| Broadcast relays (KBS, MBC) | Studio-to-transmitter paths use fibre, microwave and satellite; site counts not found | Reported, partial | S43 |
| Safe-Net (PS-LTE, 700 MHz) | Nationwide since May 2021, built with KT and SKT, designed for mountains; backhaul type not found | Reported, partial | S44 |
| Forest fire cameras | 1,971 Korea Forest Service cameras, about 200 more planned; transmission method not found | Reported, partial | S45 |
| K-water telemetry | Mainly VSAT satellite and CDMA | Reported | S46 |
| Fixed-station licence counts | Not found; the Central Radio Management Office publishes station statistics by class | Not verified | S47 |
