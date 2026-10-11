# Flaming residence time and modeled active-flame positions

Research and implementation specification, verified on 8 October 2026.

This implementation estimates **passing surface-fire flame-front activity at representative grid locations**. It combines a supplied or predicted arrival with an explicit fuel-dependent residence-time scenario. It does not establish the locations of observed flames. In particular, estimating the duration of a main flame front does not determine when every small residual flame extinguishes.

## 1. Objects and scope

For a grid location indexed by row and column $i=(r,c)$, define:

| Symbol or object | Meaning | Unit or constraint |
| --- | --- | --- |
| $A_i$ | First arrival/ignition time at the representative location | Numeric seconds from one declared origin |
| $t$ | Time at which activity is requested | Seconds from the same origin as $A_i$ |
| $T_i$ | Deterministic flaming residence duration selected for that location | Strictly positive, finite seconds |
| $\sigma_i$ | Characteristic fuel-particle surface-area-to-volume ratio | m$^{-1}$; strictly positive and finite |
| $d_i$ | Fuel-particle diameter or the specified particle dimension | Metres for the Anderson constructor; millimetres for the eucalypt-wood constructor |
| $D$ | Forecast interval width | Strictly positive seconds; maintained wildfire checkpoints use $D=3600$ |
| $E_i$ | Event that previously unburned location $i$ first becomes newly burning during $[0,D]$ | An event, not a probability |
| $q_i$ | Probability assigned to $E_i$ | A model evaluation probability in $[0,1]$ |
| $V_i$ | Validity indicator for the supplied arrival or forecast probability | Boolean |
| `AffineGrid` | Affine mapping from cell indices to projected coordinates | Metres; array order is `[row, column]` |

The stored wildfire target is a transition in cumulative burning. Cumulative burning does not identify the age of a present flame. A raw, signed direct-convolution score is also not a probability; the active-flame bridge accepts the model's evaluation probability.

The duration describes a **point-scale** process. Giving a 375 m raster cell this duration means choosing a representative-location scenario. It does not compute the time during which some flame exists anywhere inside that cell. Within-cell propagation and its ignition-time distribution would be needed for that different quantity.

## 2. Primary literature and what was verified

### Anderson: particle size and a passing flaming front

Anderson (1969), *Heat transfer and fire spread*, USDA Forest Service Research Paper INT-69, printed pp. 15–16, reports the porous-fuel-bed approximation

$$
T_{\mathrm{minutes}}=8d_{\mathrm{inches}}.
$$

The underlying particle dimensions span approximately 0.0175–4 inches. The source also shows that needle-bed residence times can exceed the simple relation: porosity and packing matter. The constructor implements the approximation, without establishing that a particular event's fuel bed satisfies it. [Anderson primary report](https://research.fs.usda.gov/download/treesearch/40489.pdf), [official bibliographic record](https://research.fs.usda.gov/treesearch/40489).

Andrews (2018), *The Rothermel surface fire spread model and associated developments: A comprehensive explanation*, RMRS-GTR-371, section 4.2, printed p. 27, gives $T_{\mathrm{minutes}}=384/\sigma_{\mathrm{ft}^{-1}}$, with $d_{\mathrm{inches}}=48/\sigma_{\mathrm{ft}^{-1}}$. Its definition excludes the indefinite trailing edge and assumes no packing effect. Sections 3.2.3–3.2.5, pp. 21–24, give surface-area weighting for characteristic particle size. These exact sections were inspected in the downloaded official PDF. DOI: [10.2737/RMRS-GTR-371](https://doi.org/10.2737/RMRS-GTR-371); [primary report](https://research.fs.usda.gov/download/treesearch/55928.pdf).

### Burrows: eucalypt particles and flame-out

Burrows's original 1994 PhD thesis, *Experimental development of a fire management model for jarrah (Eucalyptus marginata Donn ex Sm.) forest*, Australian National University, printed p. 69, equation 6-1, gives

$$
T_{\mathrm{seconds}}=0.871d_{\mathrm{mm}}^{1.875},
\qquad 1\le d_{\mathrm{mm}}\le16.
$$

This exact equation and its stated units/domain were visually verified in the rendered primary thesis. Methods on p. 67 concern individual oven-dried round-wood particles, 10 cm long, ignited above a pilot flame that was extinguished after ignition. Flame-out and cessation of glowing combustion are distinct endpoints. [Government-hosted primary thesis](https://library.dbca.wa.gov.au/FullTextFiles/016094.pdf).

Burrows (2001), “Flame residence times and rates of weight loss of eucalypt forest fuel particles,” *International Journal of Wildland Fire* 10(2), 137–143, verifies the eucalypt experimental scope and leaf combustion comparable to approximately 4 mm round wood in its publisher abstract. The exact power law was verified from the original thesis, not from the inaccessible full publisher article. DOI: [10.1071/WF01005](https://doi.org/10.1071/WF01005); [publisher abstract](https://connectsci.au/wf/article-abstract/10/2/137/22558/Flame-residence-times-and-rates-of-weight-loss-of?redirectedFrom=fulltext).

### Wotton: a main-front duration is not every remaining flame

Wotton, Gould, McCaw, Cheney, and Taylor (2012), “Flame temperature and residence time of fires in dry eucalypt forest,” *International Journal of Wildland Fire* 21(3), 270–281, found a main-front mean of 37 seconds, with standard deviation 14 seconds and 77 measurements. Thermocouples above the surface measured time above 300 °C; backing fires were excluded. Their video analysis separately records short continuous flames for 37–74 seconds after tall flames, followed by 75–127 seconds of intermittent flaming. These observations establish a distinction between the main front and residual activity; they do not supply a universal residual-flame duration. DOI: [10.1071/WF10127](https://doi.org/10.1071/WF10127); [publisher](https://connectsci.au/wf/article-abstract/21/3/270/119209/Flame-temperature-and-residence-time-of-fires-in?redirectedFrom=fulltext), [inspected author PDF](https://www.researchgate.net/profile/Sw-Taylor/publication/253843700_Flame_temperature_and_residence_time_of_fires_in_dry_eucalypt_forest/links/570583fe08ae44d70ee344b3/Flame-temperature-and-residence-time-of-fires-in-dry-eucalypt-forest.pdf).

A caller may explicitly supply 37 seconds as a dry-eucalypt main-front scenario with provenance. The implementation does not select it as a universal default.

### Scott and Burgan: reference surface fuel models

Scott and Burgan (2005), *Standard fire behavior fuel models: a comprehensive set for use with Rothermel's surface fire spread model*, RMRS-GTR-153, table 7, printed p. 18, supplies component dry loads and SAV values for all 40 standard burnable models. Constants on pp. 2 and 17 include dead 10-hour SAV of 109 ft$^{-1}$, dead 100-hour SAV of 30 ft$^{-1}$, and common particle density of 32 lb ft$^{-3}$. Page 6 preserves herbaceous SAV when curing transfers its load between live and dead. Page 3 restricts the models to the flaming front and excludes residual combustion; the catalog is not a postfrontal-consumption model. DOI: [10.2737/RMRS-GTR-153](https://doi.org/10.2737/RMRS-GTR-153); [official primary report](https://research.fs.usda.gov/download/treesearch/9521.pdf).

### Existing model precedent

Moody et al. (2022), “QES-Fire: a dynamically coupled fast-response wildfire model,” *International Journal of Wildland Fire* 31(3), 306–325, tracks time on fire and changes a cell to burned when its age reaches the residence duration. This is precedent for an age-gated modeled flame map, not validation of the present model's positions. DOI: [10.1071/WF21057](https://doi.org/10.1071/WF21057); [open primary publisher article, Fire map section](https://connectsci.au/wf/article/31/3/306/187714/QES-Fire-a-dynamically-coupled-fast-response).

## 3. Residence-time constructors and unit derivations

`FlameResidenceTime` stores a positive finite scalar or a complete `[H,W]` duration matrix, together with immutable provenance. Scalars apply to every valid location; a matrix must align exactly with the consumer's grid. Missing or nonburnable locations do not implicitly receive zero duration.

### 3.1 From characteristic surface-area-to-volume ratio

`FlameResidenceTime.from_surface_area_to_volume(sav_m_inv)` accepts $\sigma$ in m$^{-1}$. The numerical value in ft$^{-1}$ is $0.3048\sigma$. Converting minutes to seconds therefore gives

$$
T=\frac{384\times60}{0.3048\sigma}
=\frac{75\,590.55118110236}{\sigma}\ \mathrm{s}.
$$

The coefficient before division by $\sigma$ has units s m$^{-1}$. Substituting m$^{-1}$ values directly into `384 / sigma` would lose both the length and time conversions.

### 3.2 From particle diameter

`FlameResidenceTime.from_particle_diameter(diameter_m)` accepts $d$ in metres. Since an international inch is exactly 0.0254 m,

$$
T=8\times60\frac{d}{0.0254}
=18\,897.63779527559d\ \mathrm{s}.
$$

For a long cylindrical particle with negligible end area, $\sigma=4/d$; substitution reproduces section 3.1. This geometrical equivalence is not a rule for converting a leaf's surface area into a round-wood diameter. Neither constructor interprets raster width, vegetation height, or biome category as particle diameter.

### 3.3 From eucalypt round-wood diameter

`FlameResidenceTime.from_eucalypt_wood_diameter(diameter_mm)` applies Burrows's equation to millimetre inputs in the closed experimental range $[1,16]$. Extrapolation beyond this range is rejected. This is a different fuel-specific empirical relation from Anderson's linear approximation. Supplying a diameter supplies a scenario; it does not prove that jarrah particle experiments represent a different forest's fuel bed.

### 3.4 From the complete FBFM40 catalog

`FlameResidenceTime.from_fbfm40(codes)` supports all 40 standard burnable numeric identifiers:

| Group | Supported codes | Number of models |
| --- | --- | ---: |
| Grass, GR | 101–109 | 9 |
| Grass–shrub, GS | 121–124 | 4 |
| Shrub, SH | 141–149 | 9 |
| Timber understory, TU | 161–165 | 5 |
| Timber litter, TL | 181–189 | 9 |
| Slash/blowdown, SB | 201–204 | 4 |

For each component $j$, let $w_j$ be dry loading in one common unit, $\rho_j$ particle density, and $\sigma_j$ component SAV. Its surface area is proportional to $S_j=w_j\sigma_j/\rho_j$. Thus the characteristic SAV is the surface-area-weighted mean

$$
\bar\sigma
=\frac{\sum_j S_j\sigma_j}{\sum_j S_j}
=\frac{\sum_j w_j\sigma_j^2/\rho_j}
       {\sum_j w_j\sigma_j/\rho_j}.
$$

With the catalog's common density, this reduces to

$$
\boxed{\bar\sigma=\frac{\sum_jw_j\sigma_j^2}{\sum_jw_j\sigma_j}}.
$$

The common loading-unit factor also cancels. All five components are included: dead 1-hour, dead 10-hour, dead 100-hour, live herbaceous, and live woody. Table entries with zero load contribute zero surface area, including their `9999` SAV placeholders. Calculating the weighted value in ft$^{-1}$ and dividing by 0.3048 gives m$^{-1}$, then section 3.1 supplies $T$.

Moving a fraction of herbaceous load from live to dead while preserving its particle SAV leaves both sums unchanged. This invariance is only about the characteristic SAV used here; moisture and curing still affect fire spread and ignition. No live-fuel moisture measurement is inferred.

For GS4, table 7's component values yield approximately 1631 ft$^{-1}$, whereas its individual model summary lists 1674 ft$^{-1}$. The implementation consistently derives the value from table 7, with the discrepancy recorded in provenance.

Missing, nonburnable, custom, and unsupported codes fail unless the caller supplies `fallback_sav_m_inv` explicitly. Any override of a nonburnable code is a caller-selected combustion scenario, not a duration attributed to that source class. A modal 375 m fuel code also does not establish homogeneous fuel throughout the cell.

## 4. Activity from an arrival-time scenario

`active_flames_from_arrival(arrival_time_s, residence_time, time_s, grid=..., arrival_valid=...)` implements

$$
a_i(t)=\mathbf1\{A_i\le t<A_i+T_i\}
$$

at valid locations. The interval is half-open: a location is active at the supplied arrival, and inactive exactly at flame-front residence expiry. Internally, comparing $0\le t-A_i<T_i$ avoids overflowing a sum of arrival plus duration. Negative arrivals are allowed when they share the declared origin.

The resulting `ActiveFlameMap.probability` is 0 or 1 on valid locations and `NaN` elsewhere. For active locations, `remaining_duration_s` is $T_i-(t-A_i)$; it is zero on valid inactive locations. These are deterministic scenario values. A 1 is not a measured flame detection or an uncertainty-integrated probability.

Arrival uncertainty cannot be removed by selecting a short duration. For example, if arrival is only known to lie in $[L_i,U_i)$, the duration scenario permits possible activity when $L_i\le t$ and $U_i>t-T_i$; activity holds for every admissible arrival only when $t\ge U_i$ and $t<L_i+T_i$. An hour-wide arrival interval with a seconds-long duration generally cannot establish definite activity. The current deterministic API consumes point arrivals and does not perform this interval calculation.

## 5. Forecast conversion: endpoint versus interval mean

`forecast_active_flames(new_burn_probability, residence_time, interval_s, grid=..., probability_valid=...)` adds the explicit assumption

$$
A_i\mid E_i\sim\operatorname{Uniform}(0,D),
\qquad P(E_i)=q_i.
$$

The learned hourly predictor supplies $q_i$. It supplies neither this within-hour arrival law nor $T_i$. The conversion excludes flames already present at time zero; a cumulative burned-state map does not specify their remaining duration.

For $0\le t\le D$, newly igniting activity requires $t-T_i<A_i\le t$. The corresponding part of the uniform interval has length $\min(T_i,t)$, so

$$
p_i(t)=q_i\frac{\min(T_i,t)}{D}.
$$

Define $r_i=\min(T_i/D,1)$. At the endpoint,

$$
\boxed{p_i(D)=q_i r_i.}
$$

The fraction of the forecast interval occupied by a realized ignition is $\min(T_i,D-A_i)/D$. Equivalently, average $p_i(t)$ over the interval. For $T_i\le D$, split the integral at $T_i$:

$$
\bar p_i
=\frac{q_i}{D^2}
  \left(\int_0^{T_i}t\,dt+\int_{T_i}^{D}T_i\,dt\right)
=q_i\left(\frac{T_i}{D}-\frac{T_i^2}{2D^2}\right).
$$

For $T_i\ge D$, the same integral is $q_i/2$. Together,

$$
\boxed{\bar p_i=q_i\left(r_i-\frac{r_i^2}{2}\right).}
$$

`ActiveFlameForecast.endpoint` is an instantaneous `ActiveFlameMap` at `time_s == interval_s`. `mean_active_probability` is time-averaged occupancy, not an instantaneous position map. Neither field denotes the probability of ignition itself.

As a numerical example, a chosen $T=37$ s and $D=3600$ s give $p(D)\approx0.0102778q$ and $\bar p\approx0.0102250q$. The original ignition probability must not be relabeled as current flame probability, and the residence duration must not be rounded up to one hour to create visible activity. For $T\ge D$, $p(D)=q$ while $\bar p=q/2$, because uniform new ignitions still occur throughout the interval.

This calculation uses marginal probabilities for each location; it does not impose independence between locations or simulate spatial propagation. Other conditional arrival distributions can give different instantaneous and mean activity while leaving $q$ unchanged.

## 6. Model integration and position selection

`wildfire_burned_area_hourly.api.WildfireModel` provides active-flame forecast methods for array inputs (`predict_active_flames`) and dataset-sample inputs (`predict_active_flames_sample`). These reuse the saved wildfire predictor's probability of new burning during the next hour and the explicit residence scenario. The sample method uses the present state and features; it does not use the future arrival labels. These forecasts cover newly burning locations during that hour. They do not include flames already active at the cutoff. Checkpoint loading does not train a flame-duration model or fit an active-flame target, so the resulting flame probabilities have not been calibrated against observed active flames.

The heat calculation has a separate bridge. `CombustionParameters.from_flame_residence(...)` constructs combustion parameters with `burning_duration_s` equal to the supplied residence duration. Supplying `residence_time=...` to the `WildfireHeatModel` constructor enforces this equality and rejects a mismatch. `IntegratedHeatPrediction.endpoint_flame_map()` exposes its endpoint activity as an `ActiveFlameMap`, with the position API described below. This heat result includes flames present at the cutoff only when explicit present-burning inputs were supplied to the heat model. Equal durations keep the scenario consistent; they do not establish that the full fuel load is consumed during passage of the main flame front.

`ActiveFlameMap.positions(min_probability=...)` selects only valid locations whose instantaneous probability meets an explicit cutoff in $(0,1]$. Its `FlamePositions` result contains:

- `cells_rc`: zero-based `[row, column]` indices, shape `[N,2]`;
- `coordinates_xy_m`: projected cell-center `[x,y]` coordinates in metres, shape `[N,2]`;
- `probabilities`: the selected scenario probabilities, shape `[N]`.

An empty selection is represented by arrays with shapes `[0,2]`, `[0,2]`, and `[0]`. It is a legitimate result. Unknown cells remain unclassified.

For affine coefficients $(a,b,c,d,e,f)$, the center of row $r$, column $c_0$ is

$$
x=a(c_0+\tfrac12)+b(r+\tfrac12)+c,
\qquad
y=d(c_0+\tfrac12)+e(r+\tfrac12)+f.
$$

These coordinates are not latitude/longitude, subcell flame boundaries, or detected hotspots. A threshold is an explicit selection rule for a scenario; it does not establish classification accuracy or calibrated detection performance. Apply it to `forecast.endpoint`, not to the interval-mean occupancy, when requesting positions at the forecast endpoint.

## 7. FishCreek temporal-resolution check

The retrospective FishCreek example uses event origin `2024-08-21T00:00:00Z` and cutoff `2024-08-23T00:00:00Z`, so the query is 48 hours after the origin. Under the nominal arrival surface and the selected seconds-scale front-residence scenario, the default example produces no nominal active-flame positions at that instant. This is an outcome of the supplied reconstruction and duration, not evidence that the real fire had no active flames.

The completed default run records residence durations from **11.2190 s to 18.8307 s** and a forecast endpoint of `2024-08-23T01:00:00Z`. Among its 225 valid forecast locations, 23 cell centers have strictly positive endpoint flame probability; the maximum is **0.0004750484854**. None meet the explicit selection cutoff of **0.001**, so the returned endpoint position selection is empty. This is the modeled probability of new burning being in its flaming phase at the endpoint under the uniform-within-hour assumption, not a calibrated active-flame detection result. The chosen fuel scenario also records 173 locations assigned the explicit fallback surface-area-to-volume ratio for unsupported fuel codes 98 and 99; those durations are scenario overrides rather than durations derived from burnable catalog classes. The exact run values and assumptions are retained in [the active-flame demonstration summary](/Users/movinggk/Documents/영재멘토/WildfireGuardian/expected_heat_flux/outputs/active_flame_demo/summary.json).

The archived `WY-BTF-002416_FishCreek_pswt_ok_std` raster is tagged as **ordinary-kriging standard deviation, hours**. A read-only calculation using its exact saved float32 values, excluding negative NoData, verified 2642 valid locations and the following summaries:

| Summary | Arrival standard deviation |
| --- | ---: |
| Minimum | 32.7765541 h |
| Median | 87.6134186 h |
| Maximum | 246.6656189 h |

The exact source values are stored in [the FishCreek standard-deviation array](/Users/movinggk/Documents/영재멘토/WildfireGuardian/wildfire_burned_area_hourly/bitmaps/archive/rasters_us/WY-BTF-002416_FishCreek_pswt_ok_std.values.npy), with quantity/unit metadata in [the matching raster record](/Users/movinggk/Documents/영재멘토/WildfireGuardian/wildfire_burned_area_hourly/bitmaps/archive/rasters_us/WY-BTF-002416_FishCreek_pswt_ok_std.json). They must not be replaced by color-palette approximations.

Those uncertainties are vastly larger than the residence durations considered here. A standard-deviation raster alone does not specify a complete, calibrated arrival distribution. The deterministic scenario does not integrate it, and the uniform next-hour forecast assumption does not turn the retrospective arrival surface into operational or seconds-resolved flame observations.

## 8. Supported conclusions and remaining work

The implementation supports an explicit duration scenario, a deterministic age mask, and a mathematically specified new-ignition forecast conversion. It preserves missingness, distinguishes endpoint activity from interval means, and returns projected representative positions with their assumptions.

Literal detection of every continuing visible flame remains unresolved. It would require observations or additional validated modeling of residual flaming, intermittent extinction and reignition, fuel-bed packing, heterogeneous fuel consumption, and within-cell arrival progression. A separate combustion endpoint is also needed if smouldering or glowing heat is of interest. No universal duration, empirically calibrated active-flame accuracy, or event-specific flame observation is claimed by this change.
