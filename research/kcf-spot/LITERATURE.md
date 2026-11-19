# Wildfire spotting: literature review for a wind-only spot-ignition layer

Scope: ember (firebrand) transport and spot-fire ignition ahead of the front, with an eye to a layer
P(cell at downwind distance x is lit by a spot fire within t hours | forecast gust, direction, DEM).
Time-boxed review (about 90 min). Verification tags:
- **[V]**: the citation (authors, year, journal, volume, pages, DOI) was checked against Crossref or the publisher/agency page, and the quoted numbers were read in the source text.
- **[V-cit]**: the citation was checked, but the numbers come from the abstract or a secondary source that is named.
- **[U]**: not verified; it should not be used without checking.

## 1. Albini's maximum-spotting-distance models (BehavePlus / FlamMap)

**What they are.** Deterministic models of the *maximum* spotting distance. A firebrand is lofted to a height
z_F by the source's plume or flame and then drifts in a logarithmic wind profile above a cover of height H.
The models give no distribution and no probability.

- **Albini (1979), torching trees** (USDA FS GTR INT-56) [V-cit, FRAMES/NIST catalog]. Inputs are the number, species, DBH and height of torching trees, the cover height downwind and the 20-ft wind. Koo et al. (2010, Fig. 11) reproduce its flat-terrain nomograph [V].
- **Albini (1981), isolated sources / burning piles** (Res. Note INT-309) [V-cit]. Extends the model to non-forest downwind cover (low vegetation, bare ground, water).
- **Albini (1983), wind-driven surface fires** (Res. Pap. INT-309; the series differs from the 1981 note) [V-cit]. Lofting is driven by buoyant flow near the head of a surface fire. Albini called the model speculative and asked for field tests.
- **Albini, Alexander & Cruz (2012), active crown fires** (IJWF 21:609-627) [V-cit]. The abstract says initial comparisons with observed crown-fire spotting were encouraging. This is the relevant Albini variant for pine crown fires such as Uiseong. I did not extract its equations.

**Equations as implemented in BehavePlus/Behave** [V; read in `firelab/behave` `src/behave/spot.cpp`, US-government public-domain code].
Units are imperial: U = 20-ft wind (mph), L_f = flame length (ft), heights in ft, distance in miles.
```
I_B   = (L_f / 0.45)^(1/0.46)                     # Byram intensity, Btu/ft/s, back-calculated from flame length
f     = 322 * (0.474 U)^(-1.01)
z_F   = 1.055 * sqrt(f * I_B)                      # max firebrand height, surface fire
H_c   = max(H, 2.2 z_F^0.337 - 4.0)                # critical cover height
D_flat= 0.000718 U sqrt(H_c) [0.362 + 0.5 sqrt(z_F/H_c) ln(z_F/H_c)]   (miles)
drift = 0.000278 U z_F^0.643                       # surface-fire only
D_max = D_flat + drift ; burning pile: z_F = 12.2 * flame height
```
Terrain enters only through a ridge-to-valley cosine correction, which takes the horizontal and vertical
ridge-to-valley distances and the source location (valley, midslope, ridge). That correction can be computed from a DEM.

**Albini surface-fire D_max computed for our winds** (my computation from the code above, not a published table).
U is treated as the 20-ft wind, and fireline intensity I is an assumed input.

| I (kW/m), cover H | U = 10 m/s | 15 m/s | 20 m/s | 25 m/s |
|---|---|---|---|---|
| 1,000, H = 0 (open) | 0.56 km | 0.74 | 0.90 | 1.05 |
| 10,000, H = 0 | 1.18 km | 1.56 | 1.89 | 2.20 |
| 10,000, H = 10 m | 0.96 km | 1.23 | 1.47 | 1.68 |
| 30,000, H = 10 m | 1.46 km | 1.87 | 2.24 | 2.57 |
| 100,000, H = 10 m | 2.26 km | 2.92 | 3.51 | 4.03 |

In this formulation D_max grows roughly as U^0.6, because a stronger wind bends the plume and *lowers* z_F,
and roughly as I^0.25. Even at 100 MW/m and 25 m/s the surface model stays below about 5 km.
- It cannot produce the 10-35 km jumps documented in extreme events (section 4).
- Page et al. (2019) [V-cit, abstract] tested Albini (1979) against observed maximum spots in the Northern Rockies in 2017. They found that choosing a *high* estimate of wind speed was important to avoid under-prediction. That supports feeding Albini the forecast *gust* rather than the mean wind.

## 2. Lognormal landing distributions: Sardoy, Perryman, Pagnini/Kaur/Trucchia

- **Sardoy et al. (2007)** (Combust. Flame 150:151-169) [V-cit]. A 3-D physical crown-fire plume carries disc firebrands that burn as they travel.
  - As summarised by Koo et al. (2010) [V]: for brands that stay long in the plume, the landing distance does not depend on initial diameter and correlates with **I^0.1 U_wind^0.9 (ρ_wo,f τ)^-0.2**.
  - So distance is nearly linear in wind and almost insensitive to intensity. This is the key justification for a wind-only model.
- **Sardoy et al. (2008)** (Combust. Flame 154:478-488, doi:10.1016/j.combustflame.2008.05.006) [V-cit, abstract].
  - Brands are lofted by line fires (moderate to high intensity surface fires) in a crosswind.
  - Ground distributions are **bimodal**. Flaming brands land close to the fire. Charring brands land far away, but in a char state with lower ignition potential.
  - The short-range mode is lognormal. Trucchia et al. (2019) describe it as "up to 1000 m", and Kaur et al. (2016) say up to 4500 m.
  - Two regimes are set by a plume Froude number, **Fr = U/√(g L_c)** with **L_c = (I/(ρ∞ c_p T∞ √g))^(2/3)**: buoyancy-driven (Fr < 1) and wind-driven (Fr > 1).
- **Perryman et al. (2013)** (IJWF 22:428-439) fit Sardoy's data for char content 0.39. The fit as printed in Pagnini & Mentrelli (2014, eqs 34-35) [V, read in full text] is below, with I_f in kW/m and U_t in m/s, U_t taken at the top of a 10 m canopy.
  - Wind-driven regime (Fr > 1): **μ = 1.32 I_f^0.26 U_t^0.11 − 0.02 ; s = 4.95 I_f^-0.01 U_t^-0.02 − 3.48**
  - Buoyancy-driven regime (Fr < 1): **μ = 1.47 I_f^0.54 U_t^-0.55 + 1.14 ; s = 0.86 I_f^-0.21 U_t^0.44 + 0.19**
  - The fitted distribution is **q(ℓ) = exp(−(ln ℓ − μ)²/(2 s²)) / (√(2π) s ℓ)**.
  - The constants in their Table 1 are ρ∞ = 1.1 kg/m³, T = 300 K, c_p = 1121, g = 9.81. Their Table 2 lists Fr = 10.4 (6.7 m/s, 10 MW/m), 7.2 (6.7, 30 MW/m), 27.8 (17.88, 10 MW/m) and 19.3 (17.88, 30 MW/m). I reproduced these exactly by entering I in kW/m.
  - **Any realistic wildfire wind gives Fr >> 1, so only the wind-driven branch matters for us.**
  - **Caveat (unresolved):** with I in kW/m, as printed, μ comes out at about 19-27, which is impossible as the log of a distance in metres. With I in MW/m it is 3.1-4.5, a median of about 20-90 m in unstated units. I could not read Sardoy (2008) or Perryman (2013) themselves (both paywalled), so **do not use this μ**.
  - **s is dimensionless and robust:** for I = 10-30 MW/m and U = 10-25 m/s it is **0.71-0.83**, almost independent of wind and intensity.
- **Kaur et al. (2016)** (CNSNS 39:300-320) [V, arXiv text] use the same lognormal (with "ℓ0 a unit reference length") inside the LSM and ForeFire simulators. They vary μ and σ by hand rather than through a physical formula.
- **Trucchia et al. (2019), RandomFront 2.3** (GMD 12:69-87) [V, full XML]. This is a physical parameterisation.
  - The lognormal median is set from the maximum loftable height H: **μ = H (3ρ_a C_d/(2ρ_f))^½**.
  - The shape follows **σ = (1/(2 z_p)) ln(U²/(r g))**, using the Froude-like ratio U²/(rg). Here z_p = 0.45 (the 67th percentile is taken as the "maximum" distance), ρ_a = 1.2, ρ_f = 542 kg/m³, C_d = 0.45, and the brand radius is r = 0.015-0.03 m.
  - In their tests the fire-spotting contribution to burned area *peaks* at about 10 m/s for r = 1.5 cm and about 22 m/s for r = 3 cm, then declines.
  - The parameterisation needs I, which we do not have.
- **Mendez & Farazmand (2022)** (Fire Saf. J. 132:103630) [V, arXiv text]. Physical trajectories of spherical brands produce heavy-tailed landing distributions. The most probable landing distance grows **linearly with wind**: L_m ≈ 188 v* for a log wind profile and L_m ≈ 10 U for a tanh profile (idealised, short range). Their Monte Carlo sampling fails beyond 90-230 m, and rare long jumps need large-deviation methods.
- **Woycheese (1999), as quoted in Koo et al. (2010)** [V]. Cedar brands in a 10 m/s wind travel at most 49, 290 and 1100 m for fires of 1 MW, 50 MW and 1 GW.

## 3. Martin & Hillen (2016)

Martin & Hillen (2016), "The spotting distribution of wildfires", *Applied Sciences* 6(6):177, doi:10.3390/app6060177 [V-cit; abstract only, the MDPI full text returned 403].
- They define a **spotting distribution**: the probability density of a new spot fire appearing at a location ahead of the front within a short time window. They build it from physical sub-models of plume, brand launch, wind transport, terminal-velocity fall, burning in flight and ignition on landing, which are reviewed in their appendix.
- They argue that earlier work focused on maximum distance or on single sub-processes. They also discuss how the distribution could be measured and used for fire breaching.
- Conceptually this is exactly our target quantity: a product of generation, transport and ignition terms. The specific functional forms were **not verified here**.

## 4. Mapped spot-fire datasets (empirical distances)

- **Storey, Price, Sharples & Bradstock (2020a)** (IJWF 29(6):459-472, doi:10.1071/WF19124) [V, full text].
  - Data: 338 airborne optical **linescan** observations of source fires, southeast Australia, 2002-2018.
  - Maximum spotting distance per source fire: **5 m to 13.9 km, mean 0.9 km, 95th percentile 3.9 km**, roughly exponential. Only 11 fires spotted beyond 5 km.
  - Spots beyond 500 m: 0-55 per fire, mean 2.3, 95th percentile 10.2. Mean total spots per fire: 13.
  - Max-distance model: a gamma GLM with log link, R²_LR = 0.52, test RMSE 1.2 km. The predictors were log source-fire area (strongest, LR 55), forest cover, **surface wind speed** (3-h AWS mean, LR 8.9, p = 0.003), slope (LR 4.3), topographic wind exposure (LR 4.8) and 500-hPa wind (LR 4.2).
  - Spot counts: a negative-binomial hurdle model, R²_LR = 0.39.
  - Predicted maximum distances: about 4 km at 1000 ha and about 8 km at 5000 ha for dense, steep, exposed forest under strong wind, versus about 0.4-0.9 km on sparse plains.
  - The model **under-predicted** the Kilmore East fire: 18.5 km predicted against the observed 30-35 km.
- **Storey, Price, Bradstock & Sharples (2020b)** (*Fire* 3(2):10, doi:10.3390/fire3020010) [V-cit, abstract summary]. 251 fires and more than 8,000 linescan images.
  - Spot number and maximum distance are fairly correlated. Distance distributions fall into three types, and long-distance spotting is mostly **multi-modal**, so exponential-shaped spotting models may *underestimate* long-distance spotting.
  - A subagent snippet said "94% of spots within 500 m"; that figure is [U].
- **Cruz et al. (2012), Kilmore East, Black Saturday 2009** (For. Ecol. Manage. 284:269-285, doi:10.1016/j.foreco.2012.02.035) [V-cit]. About 100,000 ha burned in under 12 h. Storey et al. (2020a) cite it for spotting of **30-35 km**. The "33 km" figure appears only on a secondary page, so I could not confirm it in the paper [U for 33 km].
- **Page, Wagenbrenner, Butler & Blunck (2019)** (Can. J. For. Res. 49(3):317-325, doi:10.1139/cjfr-2018-0094) [V-cit, abstract]. Maximum spots were taken from broadscale, temporally limited airborne IR hot-spot data from the 2017 Northern Rockies season.
  - Maximum distance increases with the **fire growth × wind speed** interaction.
  - It decreases with perimeter shape, canopy height and terrain steepness.
  - Counts and distances were not extracted.
- **Lareau (2026)** (JGR-Atmos 131(6):e2025JD045798, doi:10.1029/2025JD045798) [V-cit; numbers from an AGU Eos highlight read by a subagent]. In the 2018 Camp Fire, radar and satellite data show **plume-coupled spotting 5-10 km ahead** of the front, in coherent fallout zones.
- **Ellis (2015)** (IJWF 24(2):225-235, doi:10.1071/WF14048) [V-cit only]. Probability that firebrands ignite dry-eucalypt litter, which is the ignition-probability term. Content not reviewed.
- **Koo, Pagni, Weise & Woycheese (2010)** review (IJWF 19(7):818-843, doi:10.1071/WF07119) [V, full text].
  - It treats spotting as three steps: generation, transport and ignition.
  - It covers literature to 2008, with anecdotal Australian distances of 30 km (Chandler et al. 1983).
- **Manzello firebrand studies** (brief) [V-cit]. They measure brand mass and size distributions from burning trees, e.g. Manzello, Maranghides & Mell (2007) and the Korean pine trees in Manzello et al. (2009). Most brands are small: a few cm and below 1 g, per the papers' titles and abstracts; I did not extract numbers. These studies are relevant to generation but not to distance.

## 5. Satellites and spot fires: what can be seen

- **No peer-reviewed study was found that counts spot fires from VIIRS, MODIS, GOES or Himawari.** Quantitative spot data come from airborne linescan or IR (Storey, Page), radar (Lareau) and ground reports.
- **VIIRS 375 m** (Schroeder et al. 2014, RSE 143:85-96) [V].
  - Simulations covered fires of 2-250 m² at 400-1200 K.
  - At night a 1.25 m-radius (about 5 m²) bonfire at about 1000 K was detected. Daytime detection is worse.
  - The 375 m product detects 3 times as many fire pixels as the 750 m product by day and 25 times as many at night.
  - The 50%-detection curves exist only as a figure (Fig. 4) and were not digitised.
- **GOES-16 ABI FDC** (Li et al. 2020, RSE 237:111600) [V-cit, abstract]. Fires smaller than about **34.5 MW** are hard to detect. Detection probability exceeds 95% only when the ABI pixel holds more than 11 VIIRS 375 m fire pixels.
- **Hall et al. (2023)** (IJRS 44(10):3174-3193) [V]. Geostationary sensors need "hundreds of square metres" of burning vegetation.
  - 84-88% of GOES-16 pixels containing at least 1 Landsat fire pixel were labelled non-fire.
  - Even with 75 or more Landsat fire pixels, 23-31% were missed.
  - The paper also covers Himawari AHI.
- **Himawari-8 AHI.**
  - Xu et al. (2017, RSE 193:138-149, doi:10.1016/j.rse.2017.02.024) [V-cit; numbers from the abstract via a subagent]: about 66% omission against MODIS, mostly low-FRP fires.
  - Wickramasinghe et al. (2016, Remote Sensing 8(11):932) [V-cit; numbers not verified].
- **GOFER** (Liu et al. 2024, ESSD 16:1395-1424, doi:10.5194/essd-16-1395-2024) [V-cit; details from a subagent who read it].
  - Hourly GOES-16/17 perimeters for 28 large California fires, 2019-2021, at an effective resolution of about 1.6-1.7 km. Final perimeters match FRAP with mean IoU 0.77.
  - The paper itself states that GOFER **cannot resolve spotting**.
- **Implication.**
  - Most spots are short range (Storey: most within about 0.5-1 km) and small at birth (m² to hundreds of m²).
  - Spots under about 2 km from the front fall inside the same GOES or AHI pixel as the front, or the one next to it.
  - Spots under about 0.75 km fall within 2 VIIRS pixels, and VIIRS samples only about 4 times a day.
  - So satellites see a jump only when (a) x is more than about 2 pixels and (b) the spot has grown above the detection floor before the next look: roughly tens of MW, or hundreds of m² burning, for GOES/AHI.
  - **Treat all satellite-derived "spot" events as right-censored in size and left-censored in distance.** The observable quantity is apparent frontal advance, which mixes spotting with spread.

## 6. Korean evidence (비화, 飛火)

**No Korean peer-reviewed study was found that measures spot-fire distances or fits a spotting model to Korean fires.**
Numbers below are from Korea Forest Service (KFS) and NIFoS (National Institute of Forest Science) outreach material and press briefings. A subagent opened each page.
- **KFS/NIFoS public Q&A booklet** ("비화란 무엇이고, 얼마나 멀리 날아가나요?", ob.forest.go.kr sb_3_05.pdf, no year).
  - Brands usually travel hundreds of metres. Pine branches, cones and bark from crown fire can travel "up to nearly 2 km" in strong wind.
  - It cites 35 km for Australia in 2009.
- **Uljin-Samcheok 2022** (KFS press release, 8 Apr 2022). Gusts up to 25 m/s. The fire covered more than 10 km in under 3 h. NIFoS: spread is about 78 times faster at 6 m/s wind on a 30° slope than with no wind on flat ground. No spot distance is given.
- **Goseong-Sokcho 2019** (press, Kyunghyang, 2022). Peak gust 35.6 m/s. The fire reached the coast 7.7 km away in under 90 min, about 5.1 km/h.
- **Uiseong 2025.**
  - KFS/NIFoS briefing reported by Newsis (27 Mar 2025): the fire travelled up to about 51 km to Yeongdeok within about 12 h. The front was mapped with VIIRS 375 m, drones and an IR aircraft. Gusts were about 27 m/s.
  - Kyongbuk Maeil (30 Mar 2025) gives a peak of about 8.2 km/h and calls it a record.
  - No single-jump spot distance was published.
  - The project's figure of "35-40 km in about 5 h" was **not found** in these sources [U]. Its source should be documented.
  Note added on commit: the figure is this repository's own measurement, not a published one: the 5 h reach of the
  FIRMS VIIRS + Himawari detection product on 25 March 2025 was 34.7 km at 14 KST and 40.1 km at 16 KST
  (`kcf-adaptive4/RESULTS.md`, 25 March hour table; `kcf-margin/score_gyeongbuk.py`). It is MEASURED from 2 km pixels.
  - A civil-society investigation (Pusan National University team, report meeting 25 Feb 2026, pn.or.kr) disputes the 27 m/s figure, saying weather-station winds were mostly 0-3 m/s on 22-25 Mar.
- **Korean firebrand experiments** are building- and ember-ignition tests, not transport tests:
  - Min (2021), J. Soc. Disaster Inf. 17(3):617-626.
  - KIFSE (2022) 36(5):114-121.
  - Kwon & Lee (2023), J. Korean Soc. Safety 38(4):39-46: pine cones had 10.9% moisture in March and ignite in 19 s.
- **Suggested next step for Korean data:** ask NIFoS's 산불예측·분석센터 for IR-aircraft or drone spot maps of the 2025 fires.

## 7. Which model fits our data

**What we can and cannot estimate.** We have no intensity or fuel inputs, and observations are at 375 m-2 km resolution with hours between looks.
We cannot identify brand physics. We can fit a **wind-conditioned, censored distance-to-new-ignition distribution**, and the literature supports making that distribution depend mainly on wind:
- Sardoy (2007): distance ∝ I^0.1 U^0.9.
- Albini: D_max ∝ U^0.6 I^0.25.
- Mendez & Farazmand: linear in U.
- Perryman/Pagnini: the shape s barely moves with I or U.
- Storey: surface wind and terrain exposure are significant, but source-fire size dominates.

**Recommended reference model (R0) to code and compare with the empirical fit.** It is a short-range lognormal, Albini-anchored, with a wind-only median.
```
P(cell lit within t | x, U) = 1 - exp( - Λ(U) · t · p_ign · ∫_cell f(x', U) g(y') dx' dy' )
f(x|U)  = lognormal: median m(U), log-sd σ          (downwind, x measured from the active front)
g(y)    = Normal(0, σ_y) crosswind                   (Perryman et al. 2013 structure)
σ       = 0.8                                        (Perryman 2013 fit via Pagnini & Mentrelli 2014: 0.71-0.83 for I=10-30 MW/m, U=10-25 m/s)
m(U)    = D_Albini(U, I*, H) / exp(2.326 σ)          (assume Albini D_max = 99th percentile; assumption)
I*      = 10 MW/m (sensitivity: 30 MW/m), H = 10 m   (Sardoy 2008 / Pagnini & Mentrelli 2014 test configurations)
U       = forecast gust used directly as the 20-ft wind  (deliberately high; Page et al. 2019)
```
Numbers from these equations (my computation):

| U (m/s) | 10 | 15 | 20 | 25 |
|---|---|---|---|---|
| Albini D_max, I = 10 MW/m, H = 10 m | 961 m | 1231 | 1465 | 1676 |
| median m (μ = ln m) | 149 m (5.00) | 191 (5.25) | 227 (5.43) | 260 (5.56) |
| P(x < 500 m) | 0.93 | 0.88 | 0.84 | 0.79 |
| P(x > 750 m) (≈ 2 VIIRS px) | 0.022 | 0.044 | 0.068 | 0.093 |
| P(x > 4 km) (≈ 2 GOES/AHI px) | 2e-5 | 7e-5 | 2e-4 | 3e-4 |
| Albini D_max, I = 30 MW/m | 1455 m | 1874 | 2239 | 2569 |
| median, I = 30 MW/m | 226 m | 291 | 348 | 399 |

- **Power-law form:** m(U) ≈ 150 m · (U/10)^β, with β ≈ 0.6 (Albini-implied) or β = 0.9 (Sardoy 2007). Fit β from data and compare it with this range.
- **Consistency check:** P(x < 500 m) = 0.93 at 10 m/s agrees with the Storey "94% within 500 m" snippet, but that snippet is [U].
- **Albini bound:** D_Albini(gust) is a hard short-range cap. Any observed jump beyond about 2-5 km is *outside* R0.
- **Long-range component (R1)**, needed for Uiseong, Kilmore East or the Camp Fire:
  - Add a mixture f = (1−w) f_R0 + w f_LR. Sardoy (2008) found a bimodal distribution, and Storey (2020b) found multi-modal distances.
  - f_LR is a second lognormal with median in km. Fit both w and its median to the satellite jumps.
  - Bound it with the documented maxima: 13.9 km (Storey linescan), 5-10 km (Camp Fire), 30-35 km (Kilmore East).
  - No published model gives w(U), so it is purely empirical.
  - Storey's gamma-GLM gives another anchor if fire area from GOFER or VIIRS is allowed as a covariate: about 4 km at 1000 ha and about 8 km at 5000 ha in steep forest with strong wind.
- **Parameters we must assume:**

| Parameter | Value | Source |
|---|---|---|
| I* | 10-30 MW/m | Sardoy 2008 configurations |
| H | 10 m | Sardoy / Pagnini |
| σ | 0.8 | Perryman 2013 |
| Quantile matched to D_max | 0.99 | assumption |
| Λ(U), spots per km of active front per hour | unknown; Storey gives about 13 spots, and about 2.3 beyond 500 m, per fire per snapshot | fit from data |
| p_ign | about 0.1-1, depends on fuel moisture | Ellis 2015; not extracted |
| σ_y | unknown | fit from data |

- **Terrain:** use Albini's ridge-to-valley correction, or Storey's wind-exposure index (DEM-derivable; it raises maximum distance).
- **Comparison protocol:**
  - Fit the empirical P(lit within t | x, U) only for x > 2 pixel sizes: 0.75 km for VIIRS, about 4 km for GOES/AHI/GOFER.
  - Treat t as the time between looks, and score R0 and R1 by likelihood and Brier score on the censored data.
  - Under R0, satellite-resolvable jumps are rare (P(x > 4 km) < 1e-3). If the data show frequent 2-pixel jumps, that is evidence for the long-range mode or for fast continuous spread, not a failure of the fit.

## References

- Albini, F.A. (1979). Spot fire distance from burning trees: a predictive model. USDA For. Serv. Gen. Tech. Rep. INT-56, Ogden UT (catalog page counts 73 or 78 p.). [V-cit]
- Albini, F.A. (1981). Spot fire distance from isolated sources: extensions of a predictive model. USDA For. Serv. Res. Note INT-309. [V-cit]
- Albini, F.A. (1983). Potential spotting distance from wind-driven surface fires. USDA For. Serv. Res. Pap. INT-309, 27 p. (one catalog says 30 p.). [V-cit]
- Albini, F.A., Alexander, M.E., Cruz, M.G. (2012). A mathematical model for predicting the maximum potential spotting distance from a crown fire. Int. J. Wildland Fire 21(5):609-627. doi:10.1071/WF11020 [V-cit]
- Cruz, M.G., Sullivan, A.L., Gould, J.S., Sims, N.C., Bannister, A.J., Hollis, J.J., Hurley, R.J. (2012). Anatomy of a catastrophic wildfire: the Black Saturday Kilmore East fire in Victoria, Australia. For. Ecol. Manage. 284:269-285. doi:10.1016/j.foreco.2012.02.035 [V-cit]
- Ellis, P.F.M. (2015). The likelihood of ignition of dry-eucalypt forest litter by firebrands. Int. J. Wildland Fire 24(2):225-235. doi:10.1071/WF14048 [V-cit]
- Firelab/USFS. Behave library, `src/behave/spot.cpp` (BehavePlus spotting code), github.com/firelab/behave. [V]
- Hall, J.V., Schroeder, W., Rishmawi, K., Wooster, M., Schmidt, C.C., Huang, C., Csiszar, I., Giglio, L. (2023). Geostationary active fire products validation: GOES-17 ABI, GOES-16 ABI, and Himawari AHI. Int. J. Remote Sens. 44(10):3174-3193. doi:10.1080/01431161.2023.2217983 [V]
- Kaur, I., Mentrelli, A., Bosseur, F., Filippi, J.-B., Pagnini, G. (2016). Turbulence and fire-spotting effects into wild-land fire simulators. Commun. Nonlinear Sci. Numer. Simul. 39:300-320. doi:10.1016/j.cnsns.2016.03.003 [V]
- Koo, E., Pagni, P.J., Weise, D.R., Woycheese, J.P. (2010). Firebrands and spotting ignition in large-scale fires. Int. J. Wildland Fire 19(7):818-843. doi:10.1071/WF07119 [V]
- Lareau, N.P. (2026). Plume-coupled long-range spotting drove the explosive spread of the 2018 Camp Fire. J. Geophys. Res. Atmos. 131(6):e2025JD045798. doi:10.1029/2025JD045798 [V-cit]
- Li, F., Zhang, X., Kondragunta, S., Schmidt, C.C., Holmes, C.D. (2020). A preliminary evaluation of GOES-16 active fire product using Landsat-8 and VIIRS active fire data, and ground-based prescribed fire records. Remote Sens. Environ. 237:111600. doi:10.1016/j.rse.2019.111600 [V-cit]
- Liu, T., Randerson, J.T., Chen, Y., Morton, D.C., Wiggins, E.B., Smyth, P., Foufoula-Georgiou, E., Nadler, R., Nevo, O. (2024). Systematically tracking the hourly progression of large wildfires using GOES satellite observations. Earth Syst. Sci. Data 16:1395-1424. doi:10.5194/essd-16-1395-2024 [V-cit]
- Manzello, S.L., Maranghides, A., Mell, W.E. (2007). Firebrand generation from burning vegetation. Int. J. Wildland Fire 16(4):458-462. doi:10.1071/WF06079 [V-cit]
- Manzello, S.L., Maranghides, A., Shields, J.R., Mell, W.E., Hayashi, Y., Nii, D. (2009). Mass and size distribution of firebrands generated from burning Korean pine (*Pinus koraiensis*) trees. Fire Mater. 33(1):21-31. doi:10.1002/fam.977 [V-cit]
- Martin, J., Hillen, T. (2016). The spotting distribution of wildfires. Appl. Sci. 6(6):177. doi:10.3390/app6060177 [V-cit]
- Mendez, A., Farazmand, M. (2022). Quantifying rare events in spotting: how far do wildfires spread? Fire Saf. J. 132:103630. doi:10.1016/j.firesaf.2022.103630 [V]
- Page, W.G., Wagenbrenner, N.S., Butler, B.W., Blunck, D.L. (2019). An analysis of spotting distances during the 2017 fire season in the Northern Rockies, USA. Can. J. For. Res. 49(3):317-325. doi:10.1139/cjfr-2018-0094 [V-cit]
- Pagnini, G., Mentrelli, A. (2014). Modelling wildland fire propagation by tracking random fronts. Nat. Hazards Earth Syst. Sci. 14:2249-2263. doi:10.5194/nhess-14-2249-2014 (a corrigendum exists) [V]
- Perryman, H.A., Dugaw, C.J., Varner, J.M., Johnson, D.L. (2013). A cellular automata model to link surface fires to firebrand lift-off and dispersal. Int. J. Wildland Fire 22(4):428-439. doi:10.1071/WF11045 [V-cit; coefficients only via Pagnini & Mentrelli 2014]
- Sardoy, N., Consalvi, J.L., Porterie, B., Fernandez-Pello, A.C. (2007). Modeling transport and combustion of firebrands from burning trees. Combust. Flame 150(3):151-169. doi:10.1016/j.combustflame.2007.04.008 [V-cit]
- Sardoy, N., Consalvi, J.L., Kaiss, A., Fernandez-Pello, A.C., Porterie, B. (2008). Numerical study of ground-level distribution of firebrands generated by line fires. Combust. Flame 154(3):478-488. doi:10.1016/j.combustflame.2008.05.006 [V-cit]
- Schroeder, W., Oliva, P., Giglio, L., Csiszar, I.A. (2014). The New VIIRS 375 m active fire detection data product: algorithm description and initial assessment. Remote Sens. Environ. 143:85-96. doi:10.1016/j.rse.2013.12.008 [V]
- Storey, M.A., Price, O.F., Sharples, J.J., Bradstock, R.A. (2020a). Drivers of long-distance spotting during wildfires in south-eastern Australia. Int. J. Wildland Fire 29(6):459-472. doi:10.1071/WF19124 [V]
- Storey, M.A., Price, O.F., Bradstock, R.A., Sharples, J.J. (2020b). Analysis of variation in distance, number, and distribution of spotting in southeast Australian wildfires. Fire 3(2):10. doi:10.3390/fire3020010 [V-cit]
- Trucchia, A., Egorova, V., Butenko, A., Kaur, I., Pagnini, G. (2019). RandomFront 2.3: a physical parameterisation of fire spotting for operational fire spread models: implementation in WRF-SFIRE and response analysis with LSFire+. Geosci. Model Dev. 12:69-87. doi:10.5194/gmd-12-69-2019 [V]
- Wickramasinghe, C., Jones, S., Reinke, K., Wallace, L. (2016). Development of a multi-spatial resolution approach to the surveillance of active fire lines using Himawari-8. Remote Sens. 8(11):932. doi:10.3390/rs8110932 [V-cit]
- Xu, W., Wooster, M.J., Kaneko, T., He, J., Zhang, T., Fisher, D. (2017). Major advances in geostationary fire radiative power (FRP) retrieval over Asia and Australia stemming from use of Himawari-8 AHI. Remote Sens. Environ. 193:138-149. doi:10.1016/j.rse.2017.02.024 [V-cit]
- Korean grey literature (accessed via subagent; URLs): KFS/NIFoS Q&A booklet ob.forest.go.kr/kfs/images/data/down/sb_3_05.pdf; KFS press release 8 Apr 2022, m.korea.kr newsId=156502685; Newsis 27 Mar 2025, newsis.com/view/NISX20250327_0003115850; Kyongbuk Maeil 30 Mar 2025, kbmaeil.com/article/202503300914030; Kyunghyang 6 Mar 2022, khan.co.kr/article/202203061155001; pn.or.kr idxno=33278. [V-cit, press]
- Kwon, H., Lee, J.H. (2023). A study on the combustion characteristics of the crown of pine trees in the drying season. J. Korean Soc. Saf. 38(4):39-46. doi:10.14346/JKOSOS.2023.38.4.39 [V-cit via subagent]
- Min, J.-K. (2021). An experimental study on the influence of the spread of firebrand on building exterior materials and roofing materials in urban areas. J. Soc. Disaster Inf. 17(3):617-626. doi:10.15683/kosdi.2021.9.30.617 [V-cit via subagent]
