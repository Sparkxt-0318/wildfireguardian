# Referenced heat parameters and their implementation

This audit describes the maintained implementation on **12 October 2026**. The
shared previous-burning rule and cell-duration extension were added on
**13 October 2026**. The
calculation predicts **incident radiant heat flux**, in W/m², at upward-facing
receiver points. It does not calculate absorbed heat, convection, a receiver's
temperature, or a measured total wildfire heat budget. Literature supports the
individual laws and explicitly identified reference scenarios below; it does
not validate their composition for the project's reconstructed wildfire cells.

The executable entry points are [CombustionParameters and integrated heat](../wildfire/heat.py),
[nominal fuel heat content](../wildfire/heat_parameters.py),
[radiative fraction and atmospheric transport](../wildfire/heat_transfer.py), and
[constant-hazard timing](../wildfire/heat_timing.py). Bibliographic records for
this audit are in [heat_parameter_models.bib](heat_parameter_models.bib).

## Objects, units, and source-to-parameter audit

Let $i$ index a source cell and $x$ denote a receiver point. All source
loadings refer to **the entire horizontal ground-cell area**. Let $D$ be the
forecast interval; the integrated checkpoint API requires exactly
$D=3600\,\mathrm{s}$.

| Object | Definition and units | Implemented source or modeling choice |
|---|---|---|
| $w_i\geq0$ | Initial dry fuel loading, kg/m² | Supplied field/model loading; optional aligned static LANDFIRE FCCS reference loading |
| $c_i\in[0,w_i]$ | Dry loading consumed in the selected flaming phase, kg/m² | Explicit measurement or external phase-specific model output |
| $f_i\in[0,1]$ | Selected phase consumed fraction; $c_i=w_if_i$ | Explicit input, or derived from separately supplied initial and consumed masses |
| $H_i>0$ | Heat released per kg of dry fuel consumed, J/kg | Supplied effective heat yield, or explicitly selected nominal FBFM40 heat content |
| $T_i>0$ | Duration of active emission in the selected phase, s | Supplied duration; point front residence; narrowly scoped Burrows laboratory twig scenario; or explicitly supplied cell front-crossing scenario |
| $Q_i\geq0$ | Conditional heat-release-rate density per source ground area, W/m² | $Q_i=c_iH_i/T_i=w_if_iH_i/T_i$, constant during active emission |
| $\chi_i\in[0,1]$ | Emitted radiant energy/power divided by matched total released source energy/power | Supplied value/map; matched energy-budget ratio; optional 0.30 pine/dead-litter reference |
| $\kappa\geq0$ | Homogeneous grey absorption coefficient, m⁻¹ | Supplied/calibrated coefficient; no universal smoke or humidity estimator |
| $\tau(r)\in(0,1]$ | Transmission over path length $r$, dimensionless | $\exp(-\kappa r)$; alternatively a fixed scalar transmission scenario |
| $h>0$ | Source elevation minus receiver elevation, m | Explicit fixed geometry input in a common height datum |
| $q_i\in[0,1]$ | Probability of first-new-burning during the next hour | Trained prediction or supplied probability; missing values remain unresolved |
| $\lambda_i\geq0$ | Constant first-ignition hazard, s⁻¹ | Explicit timing scenario, using a finite model rate or probability inversion when available |
| $m_i\in[0,1]$ | Mean active-burning probability over the interval | Derived from the selected initiation law and deterministic emission duration |

An available numerical parameter is not necessarily known physically. The
returned source-activity bounds hold $w_i,f_i,H_i,T_i,\chi_i,\kappa,h$, the
finite source domain, and the transfer model fixed. Uncertainty in these
physical parameters requires an additional sensitivity or uncertainty analysis.

## Combustion mass and energy

The selected phase releases $E_i=c_iH_i$ joules per square metre of source
ground area. Assuming a uniform release rate for $T_i$ seconds gives

$$
Q_i=\frac{E_i}{T_i}=\frac{w_if_iH_i}{T_i}.
$$

The units are $(\mathrm{kg/m^2})(\mathrm{J/kg})/\mathrm{s}=\mathrm{W/m^2}$.
The temporal shape is an explicit rectangular pulse, rather than a reconstructed
instantaneous heat-release curve. The flaming-front heat-per-area definition
uses fuel consumed in that phase and excludes heat released later in the
trailing burn. [Scott 2012, printed pp.17–18](https://pyrologix.com/wp-content/uploads/2014/04/Scott_20121.pdf)

The APIs preserve this distinction:

| API | Input meaning and behavior |
|---|---|
| `CombustionParameters(w, H, T, consumed_fraction=f, ...)` | Existing explicit combustion scenario; the first four positional arguments remain supported |
| `CombustionParameters.from_flame_residence(residence, ...)` | Uses the same supplied `FlameResidenceTime.duration_s` in combustion and activity |
| `CombustionParameters.from_consumed_fuel(c, heat_of_combustion_j_kg=H, burning_duration_s=T, ...)` | Stores already-consumed phase dry mass and sets its internal fraction to 1; this does not consume all initial fuel |
| `CombustionParameters.from_phase_consumption(w, c, heat_of_combustion_j_kg=H, burning_duration_s=T, ...)` | Derives $f=c/w$, defines $0/0=0$, and rejects $c>w$ |
| `CombustionParameters.from_fbfm40(codes, fuel_load_kg_m2=w, consumed_fraction=f, ...)` | Selects nominal reference heat content; requires an explicit phase fraction; derives reference residence or accepts `residence_time=` |
| `heat_content_from_fbfm40(codes)` | Returns only nominal reference heat content, allowing separate explicit mass and duration choices |

The new reference and phase-mass constructors require complete genuine numeric
scalars or nonempty [H,W] matrices; their physical inputs must broadcast
together. They reject negative mass, nonpositive heat or duration, invalid
fractions, and unresolved masked/nonfinite inputs. Metadata are copied into
immutable finite JSON-compatible mappings; `.provenance_dict()` returns an
independent mutable copy. Direct construction retains the established numeric
broadcast behavior and permits optional `provenance=`.

The phase-mass adapters can consume selected **flaming** mass from CONSUME or
another external model after conversion to kg/m² and alignment of its ground
area and time/phase definition. They do not run that software. CONSUME separates
strata and combustion phases and requires corresponding loadings, moisture and
site inputs. A single total FCCS loading value cannot replace those inputs.
[CONSUME 3.0 manual, phase reports pp.111,114; Appendix C pp.139–195](https://depts.washington.edu/fft/webtool/help/docs/consume30_users_guide.pdf)

`EcologicalFuelMaps.from_fccs_rasters` retains static reference loading and
coverage separately. Incomplete coverage requires an explicit fallback before
use as whole-cell combustion mass; the loading is not treated as event-date
measured available or consumed fuel. [LANDFIRE FCCS product](https://www.landfire.gov/fuel/fccs)

### Nominal reference heat content

Supported standard FBFM40 codes use $8000\,\mathrm{Btu/lb}$, except GR6
(`106`), which uses $9000\,\mathrm{Btu/lb}$, for both live and dead categories.
[Scott–Burgan catalog](https://research.fs.usda.gov/download/treesearch/9521.pdf),
[official NWCG table, Dead Heat and Live Heat columns](https://www-nwcg.fs2c.usda.gov/publications/pms437/fuels/surface-fuel-model-descriptions)

The implementation explicitly interprets the catalog Btu as International Table
Btu. With $1\,\mathrm{Btu_{IT}/lb}=2326\,\mathrm{J/kg}$,

$$
H_i^{\mathrm{nominal}}=
\begin{cases}
20{,}934{,}000\,\mathrm{J/kg},&\text{code }106,\\
18{,}608{,}000\,\mathrm{J/kg},&\text{other supported FBFM40 codes}.
\end{cases}
$$

The conversion follows [NIST SP811, Appendix B, printed p.46](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication811e2008.pdf).
No moisture, mineral, or incomplete-combustion correction is imposed. These
nominal values do not establish measured effective heat yield. Missing,
nonburnable, custom, and fractional codes raise an error; callers needing a
different scenario supply `heat_of_combustion_j_kg` explicitly.

## Duration models and their domains

`FlameResidenceTime.from_surface_area_to_volume(sav_m_inv)` applies the
reference front-passage relation

$$
T_i=\frac{384\times60}{0.3048\,\sigma_i}
\quad\text{seconds, with }\sigma_i\text{ in }\mathrm{m^{-1}}.
$$

`from_particle_diameter(diameter_m)` applies
$T_i=(8\times60/0.0254)d_i$ seconds. For a long cylinder neglecting its
ends, $\sigma_i=4/d_i$, so the two forms agree. These approximate surface-front
flaming time at a point; they exclude trailing combustion and cell traversal.
[Anderson 1969, printed pp.15–16](https://research.fs.usda.gov/download/treesearch/40489.pdf),
[Andrews 2018, §4.2, printed p.27](https://research.fs.usda.gov/download/treesearch/55928.pdf)

`FlameResidenceTime.from_fbfm40(codes)` uses the catalog's five particle-class
loadings $w_{ij}$ and particle SAVs $\sigma_{ij}$. Under common particle
density, surface-area weights give

$$
\sigma_i=
\frac{\sum_jw_{ij}\sigma_{ij}^2}{\sum_jw_{ij}\sigma_{ij}},
\qquad
T_i=\frac{23040}{\sigma_{i,\mathrm{ft^{-1}}}}\,\mathrm{s}.
$$

The implementation uses all nonzero reference particle loadings, including the
catalogue constants for dead 10-h and 100-h particle classes. Herbaceous curing
transfers mass while preserving that particle SAV, so it leaves this combined
characteristic SAV unchanged. A raster fuel code remains a reference fuelbed
assignment, rather than an observation of homogeneous coarse-cell burning.
[Scott–Burgan, p.6 and Table 7 p.18](https://research.fs.usda.gov/download/treesearch/9521.pdf),
[Andrews, §§3.2.3–3.2.5 pp.21–24](https://research.fs.usda.gov/download/treesearch/55928.pdf)

`FlameResidenceTime.from_eucalypt_wood_diameter(diameter_mm)` is a separate
laboratory option:

$$
T_i=0.871\,d_{i,\mathrm{mm}}^{1.875}\,\mathrm{s},\qquad1\leq d_{i,\mathrm{mm}}\leq16.
$$

Its domain is individual oven-dried, 10-cm-long jarrah twigs burning in still air
at 26–32 °C. The implementation rejects extrapolation beyond the tested diameter
range. It does not infer a general wind-, moisture-, or species-dependent
fuelbed duration. [Burrows 1994, methods p.67; Equation 6-1 p.69](https://library.dbca.wa.gov.au/FullTextFiles/016094.pdf)

### Coarse-cell front-crossing duration

Point flame residence and the interval during which some part of a coarse cell
contains a front are distinct quantities. The reference value 11.52 seconds
for a particle SAV of 2000 ft⁻¹ remains a point residence; it is not an estimate
of the time to cross a 375 m cell. `CellBurningDuration.from_front_crossing(
point_residence_time, *, grid,
spread_rate_m_s=DEFAULT_FRONT_SPREAD_RATE_M_S, spread_direction_deg=0.0,
provenance=None)` makes the cell-scale interpretation explicit.

The exported reference is
`DEFAULT_FRONT_SPREAD_RATE_M_S = 341.0 / 3600.0` m/s, approximately
0.0947222 m/s. Benali et al. report a forward rate-of-spread median of 341 m/h
in PT-FireSprd, a database containing 80 large Portuguese wildfires from
2015–2021. This is a median of spread estimates in the database, not a median
over 80 equally weighted per-fire average speeds. It is used as a reported
reference scenario, not a universal usual speed or an estimate for FishCreek
or US conifer forests.
[Benali et al. 2023, Section 3.1](https://essd.copernicus.org/articles/15/3791/2023/#section3)

Let $\mathbf u$ be the projected column edge vector of one cell and
$\mathbf v$ its row edge vector, both in metres. Let $V_i>0$ be the front speed
in m/s and $\theta_i$ its direction, measured counterclockwise from the positive
projected x axis. Put
$\mathbf n_i=(\cos(\pi\theta_i/180),\sin(\pi\theta_i/180))$ for these direction
values in degrees. Speed and direction are adjustable
finite scalars or `[H,W]` matrices; omitted speed uses the reference above,
and omitted direction uses 0°. There is no speed estimate from the fuel class.
A straight front translating at constant local speed reaches a
position $\mathbf x$ according to the projection $\mathbf n_i\cdot\mathbf x$.
For a parallelogram cell parametrized by
$\mathbf x=\mathbf x_0+s\mathbf u+t\mathbf v$, $0\le s,t\le1$, the range of
that projection is the sum of the two absolute projected edge lengths. Thus
the **derived geometric** crossing time is

$$
C_i=\frac{|\mathbf n_i\cdot\mathbf u|+|\mathbf n_i\cdot\mathbf v|}{V_i},
\qquad T_i^{\mathrm{cell}}=C_i+T_i^{\mathrm{point}}.
$$

The units of $C_i$ are metres divided by m/s, hence seconds. First front entry
starts this duration, and the last point extinguishes one point-residence time
after the front exits. With square 375 m cells,
$V=341/3600$ m/s and $\theta=0$°,
$C\approx3958.94$ seconds (65.98 minutes). If
$T^{\mathrm{point}}=11.52$ seconds, the duration is approximately
3970.46 seconds (66.17 minutes). These are reference-scenario values, not
estimates of FishCreek speed or duration.

Passing `cell_burning_duration=duration` to `model.heat_model(...)` or
`WildfireHeatModel(...)` substitutes $T_i^{\mathrm{cell}}$ into both the shared
burning-state age calculation and the heat-release denominator. It preserves

$$
E_i=w_if_iH_i,\qquad Q_i^{\mathrm{cell}}=E_i/T_i^{\mathrm{cell}},
$$

so extending the emission interval redistributes the same specified energy.
The composed API enables `use_cell_burning_duration=True` by default. If
`residence_time` is provided and no cell object is supplied, it constructs this
scenario automatically with adjustable `spread_rate_m_s` and
`spread_direction_deg`; `spread_rate_m_s=None` selects the reference speed.
A prebuilt cell object overrides automatic construction and cannot be combined
with an explicit speed or `use_cell_burning_duration=False`. Without either
point residence or a cell object, the explicit combustion duration is retained.
An explicitly requested speed or nondefault direction requires point residence.
Set `use_cell_burning_duration=False` to explicitly retain point-duration
emission.
Uniform emission over the whole cell and duration is a rectangular coarse-cell
approximation to the true moving-front history. Input burn-start times should
describe first cell entry. If a representative center-arrival timestamp is
used as cell burn start, that is an explicit approximation; the API does not
apply a hidden half-crossing-time shift. The independent `FlameResidenceTime`
and point-flame APIs retain their point-scale meanings.

Front passage also differs from post-frontal fuel burnout. FARSITE's
post-frontal extension uses time-dependent combustion histories, and BURNUP
requires fuel component sizes, masses, moisture and other physical inputs to
simulate flaming and smoldering over time.
[Finney, Seli and Andrews 2003, conference abstract](https://ams.confex.com/ams/FIRE2003/techprogram/paper_66204.htm),
[extended paper](https://ams.confex.com/ams/pdfpapers/66204.pdf),
[Lutes 2013, pp.1–2](https://research.fs.usda.gov/download/treesearch/43326.pdf).
These references support that distinction; they are not sources of the
geometric equation derived above. `CellBurningDuration` implements the declared
front-crossing scenario, not BURNUP or universal post-frontal burnout.

## Radiative fraction and matched energy budgets

`RadiativeFractionEstimate.pine_litter_reference()` explicitly selects
$\chi=0.30$. Dietenberger and Boardman's validation supports a pine/dead-litter
reference scenario; the reported litter test was a 0.6-m fire under an HRR hood
up to 250 kW. This value is not generalized to every vegetation or crown fire.
[Dietenberger and Boardman, Fire Technology 53 (2017), §4 p.592; online 2016](https://research.fs.usda.gov/treesearch/53606)

`RadiativeFractionEstimate.from_energy_budget(E_rad, E_total, provenance=...)`
forms $\chi=E_{\mathrm{rad}}/E_{\mathrm{total}}$, requiring the same source,
ground-area normalization, time period and shape for both budgets. Require
$0\leq E_{\mathrm{rad}}\leq E_{\mathrm{total}}$ and
$E_{\mathrm{total}}>0$. This is an integrated source-energy ratio; applying it
as a constant instantaneous fraction adds a temporal assumption. Incident
energy at one receiver cannot be used as emitted source radiant energy, and
the denominator is released heat rather than theoretical gross fuel energy.

Both `ExpectedHeatFluxModel` and `WildfireHeatModel` accept the estimate object
through `radiative_fraction=`, retain its provenance, and also accept existing
explicit scalar/source-map fractions. Linearity of expectation does not require
independence between cells.

## Atmospheric absorption and finite-cell transfer

`HomogeneousAtmosphere(kappa, provenance=...)` uses
$\tau(r)=\exp(-\kappa r)$, with $r$ in metres and
$\kappa$ in m⁻¹. Spectral transmission follows
$\tau_\nu=\exp[-\int\kappa_\nu(s)\,ds]$. Replacing it with one constant grey
coefficient is an explicit model reduction; scattering and medium self-emission
are omitted. [Yilmaz 2009, NIST GCR 09-922, Equation 1.18 p.17](https://nvlpubs.nist.gov/nistpubs/gcr/2009/gcr09-922.pdf)

`HomogeneousAtmosphere.from_reference_transmission(tau_ref, r_ref,
provenance=...)` computes

$$
\kappa=-\frac{\log\tau_{\mathrm{ref}}}{r_{\mathrm{ref}}},
\qquad0<\tau_{\mathrm{ref}}\leq1,\quad r_{\mathrm{ref}}>0.
$$

The reference must describe a matched path, band, and source spectrum. Zero
transmission would require an infinite coefficient and is rejected. A supplied
illustrative transmission produces an illustrative coefficient; it is not
automatically a measurement. Broadband reuse at other distances or spectra is
a grey approximation. Humidity or smoke labels alone do not determine
$\kappa$ in this implementation.

Let $A_i$ be the horizontal source-cell footprint and let a source point
$y\in A_i$ lie at height $h$ above the receiver. Its distance is
$r(y,x)=\sqrt{\lVert y-x\rVert^2+h^2}$. The dimensionless cell transfer is

$$
K_i(x)=\int_{A_i}\frac{h\,\exp[-\kappa r(y,x)]}
{4\pi\,r(y,x)^3}\,dA(y).
$$

It integrates the inverse-square isotropic source law and receiving-plane cosine
over the complete source footprint. The underlying point-source correlation is
documented in [Overholt 2014, NIST SP1169, §6.1 Equation 6.1 p.39](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1169.pdf).
Uniform horizontal source sheets at a supplied elevation are this project's
geometric extension; that reference does not validate coarse wildfire sheets.

For $\kappa=0$, $K_i=\Omega_i/(4\pi)$, where $\Omega_i$ is the
exact solid angle of the parallelogram cell, evaluated as two triangles. The
triangle expression is attributed to [van Oosterom and Strackee 1983](https://doi.org/10.1109/TBME.1983.325207).
Rotation and shear are supported. Receivers are point samples, not receiver-area
averages.

For $\kappa>0$, the implementation **does not multiply the whole solid angle
by transmission at the cell centre**. Each subdivided source tile has exact
transparent transfer $K_{0,b}$ and extremal path lengths
$r_{\min,b}\leq r\leq r_{\max,b}$. Positivity and monotonic transmission give

$$
K_{0,b}e^{-\kappa r_{\max,b}}
\leq K_b\leq
K_{0,b}e^{-\kappa r_{\min,b}}.
$$

The algorithm sums these enclosures and subdivides the tile with greatest gap.
For each cell/receiver pair it stops when

$$
K_{\mathrm U}-K_{\mathrm L}
\leq\texttt{transfer\_atol}
 +\texttt{transfer\_rtol}\,K_{\mathrm L}.
$$

Defaults are `transfer_atol=1e-7` and `transfer_rtol=1e-2`, both dimensionless.
The reported midpoint has error at most half the enclosure width under the
fixed geometry/absorption scenario, up to floating-point evaluation accuracy.
The absolute term means this is not an unconditional 0.5% relative flux-error
guarantee. Failure to meet tolerance within subdivision budgets raises an error.
These are kernel tolerances, not W/m² limits: source strengths scale the final
flux-enclosure width, which is recorded in result metadata.

Pass the object with `atmosphere=` to either heat-model constructor. Use either
this object or a nonunit scalar `atmospheric_transmissivity`, not both; scalar
transmission remains a distinct path-independent scenario. `emission_height_m`
and `receiver_height_m` remain explicit common-datum inputs, with a strictly
positive separation. The ignition probability does not determine flame height.

## From new-burning probability to active emission

The integrated API offers `ignition_time_model="uniform"` (the preserved
default) or the explicitly selected `"constant_hazard"`. Neither a one-hour
probability nor a reconstructed burned state alone identifies the true
within-hour arrival law.

For either scenario, an initially unburned cell with first arrival $A_i$
is active on $[A_i,A_i+T_i)$. Put $r_i=\min(T_i/D,1)$. The mean activity is
$m_i=D^{-1}\int_0^D\mathbb P(A_i\leq u<A_i+T_i)\,du$; endpoint activity is
the same probability evaluated at $u=D$.

### Uniform conditional arrival

Conditional on first burning during the hour, arrival is uniform on $[0,D]$.
The resulting unconditional mean and endpoint activity are

$$
m_i=q_i(r_i-r_i^2/2),\qquad e_i=q_ir_i.
$$

This is an explicit interpolation assumption. The formulas follow by integrating
the overlap of the arrival window with the interval of active emission.

### Constant first-ignition hazard

The exponential survival law is
$\mathbb P(A_i>u)=\exp(-\lambda_i u)$, with finite
$\lambda_i\geq0$. Its endpoint event probability is
$q_i=1-\exp(-\lambda_iD)$. This is the standard mathematical
constant-hazard law, rather than empirical evidence for wildfire arrival timing.
[NIST/SEMATECH e-Handbook, §8.1.6.1](https://www.itl.nist.gov/div898/handbook/apr/section1/apr161.htm)

For $x_i=\lambda_iD>0$, direct integration gives

$$
e_i=e^{-x_i(1-r_i)}-e^{-x_i},\qquad
m_i=r_i-\frac{e_i}{x_i}.
$$

At $\lambda_i=0$, both are zero. The code uses equivalent stable formulas
near zero and when products overflow; it preserves the original finite rate
when a computed probability rounds to one. `infer_ignition_rate(q, D)` uses
$-\log(1-q)/D$ only for $q<1$. Exact $q=1$ without a supplied finite
rate is rejected because no finite constant hazard produces it.

`WildfireHeatModel` uses available original finite neural-kernel rates for this
explicit scenario, converting per-hour rate to s⁻¹. The raw
`predict_from_new_burn_probability_details` method also accepts an optional
exact-shape `ignition_rate_s_inv` map and checks probability-rate consistency.
When a resolved rate is unavailable, probability inversion is explicitly marked
as a scenario in metadata. A forest probability is not a fitted physical hazard.
An equivalent rate obtained from a Bayesian average of probabilities is rejected:
generally, a mixture of exponentials is not exponential. Timing for such a
mixture requires componentwise occupancies and the same mixture weights, or the
uniform conditional scenario.

The two choices produce different answers even at the same $q_i$. Their
agreement at an endpoint does not establish agreement of within-hour activity
or mean heat. Constant hazard can concentrate initiation early; uniform
conditional arrival cannot do so.

## Meaning of lower and upper heat-flux bounds

For fixed physical parameters, the expected interval-mean radiant flux is

$$
\overline F(x)=\sum_i Q_i\chi_iK_i(x)m_i.
$$

If $\ell_i\leq m_i\leq u_i$ and the numerical transfer enclosure is
$K_{\mathrm L,i}\leq K_i\leq K_{\mathrm U,i}$, nonnegative source strengths
give

$$
\sum_iQ_i\chi_iK_{\mathrm L,i}\ell_i
\leq\overline F(x)\leq
\sum_iQ_i\chi_iK_{\mathrm U,i}u_i.
$$

The integrated outputs combine missing-activity bounds with these numerical
transfer enclosures. They are not confidence intervals, realization extrema,
or bounds over every possible physical parameter value.

| Unresolved source input | Mean activity interval | Endpoint activity upper bound |
|---|---|---|
| New burning, uniform scenario | $[0,r-r^2/2]$ | $r$ |
| New burning, constant-hazard scenario, all finite hazards allowed | $[0,r]$; upper endpoint is a supremum | $r(1-r)^{(1-r)/r}$ for $0<r<1$; 1 for $r=1$ |
| Known already-burned cell, age unknown | $[0,\min(T/D,1)]$ | 1 if $T>D$, otherwise 0 |

For the hazard endpoint bound with $0<r<1$, maximizing
$e^{-x(1-r)}-e^{-x}$ yields $x_*=-\log(1-r)/r$; substitution produces
the table value. Setting the unknown event probability to one would give the
wrong endpoint extremum when $T<D$. The mean upper bound $r$ is approached
as the finite hazard grows and need not be attained.

Existing fire is included by default throughout the composed heat API using
the shared `burning_state_from_arrival(...)` rule. A supplied arrival age
$s_i=t_0-a_i\geq0$ gives current activity
$\mathbf1_{\{s_i<T_i\}}$ and remaining duration
$R_i=\max(T_i-s_i,0)$. When a cell-duration scenario is selected, $T_i$ is that
cell duration. Initially active probability
$p_i$ contributes mean $p_i\min(R_i,D)/D$ and endpoint
$p_i\mathbf 1_{R_i>D}$. Query time exactly at the supplied extinction time is
inactive. Existing and first-new-burning support must describe disjoint events;
no inter-cell independence is required. Missing cumulative burned-state
coverage can hide existing fire outside the declared known support, which these
bounds do not resolve.

Even if all activity is resolved, nonzero numerical absorption integration
width can leave distinct reported bounds. A complete reported expectation uses
the numerical midpoint; unresolved emitting-source activity makes the full
expectation NaN while finite bound maps remain available. For the integrated
interval, incident energy bounds are $D$ times the corresponding mean-flux
bounds, with units J/m². Multiplying by receiver area assumes nearly uniform
irradiance over that small area; it does not calculate a large-area integral.

## Runnable synthetic pine/dead-litter scenario

Run this from the repository with its Python environment. The initial loading,
phase-consumed loading, reference transmission, source height and rates below
are **illustrative caller assumptions**, not site measurements or trained
checkpoint output. TL1 (`181`) supplies nominal reference heat and front duration;
the pine/dead-litter radiation fraction is explicitly selected within its
reference scope. This example models new burning only.

```python
import numpy as np

from wildfire.heat import AffineGrid, CombustionParameters, FlameResidenceTime, WildfireHeatModel
from wildfire.heat_parameters import heat_content_from_fbfm40
from wildfire.heat_transfer import HomogeneousAtmosphere, RadiativeFractionEstimate

codes = np.full((2, 2), 181)  # TL1 reference surface fuel model
residence = FlameResidenceTime.from_fbfm40(codes)
nominal_heat = heat_content_from_fbfm40(codes)

# Illustrative initial and flaming-consumed dry mass per entire ground-cell area.
initial = np.full((2, 2), 0.40)  # kg/m2
consumed = np.full((2, 2), 0.08)  # kg/m2 consumed in this modeled phase
combustion = CombustionParameters.from_phase_consumption(
    initial, consumed,
    heat_of_combustion_j_kg=nominal_heat,
    burning_duration_s=residence.duration_s,
    provenance={"scenario": "illustrative synthetic pine/dead-litter phase masses"},
)

atmosphere = HomogeneousAtmosphere.from_reference_transmission(
    0.95, 100.0,
    provenance={"scenario": "illustrative 95% transmission over 100 m; not a measurement"},
)
model = WildfireHeatModel(
    None,  # raw probability input below; no trained predictor required
    grid=AffineGrid.from_cell_size(20.0),
    combustion=combustion,
    residence_time=residence,
    radiative_fraction=RadiativeFractionEstimate.pine_litter_reference(),
    emission_height_m=3.0,  # illustrative sheet geometry
    receiver_height_m=0.0,
    atmosphere=atmosphere,
    transfer_atol=1e-7,
    transfer_rtol=1e-2,
    ignition_time_model="constant_hazard",
)

rate = np.array([[2e-5, 4e-5], [1e-5, 3e-5]])  # illustrative finite hazards, s^-1
q = -np.expm1(-rate * 3600.0)
prediction = model.predict_from_new_burn_probability_details(q, ignition_rate_s_inv=rate)

print("Mean incident radiant flux, W/m2:\n", prediction.expected_heat_flux_w_m2)
print("Lower bound, W/m2:\n", prediction.heat_flux_lower_bound_w_m2)
print("Upper bound, W/m2:\n", prediction.heat_flux_upper_bound_w_m2)
print("Incident energy over the hour, J/m2:\n", prediction.expected_incident_energy_j_m2)
assert np.all(np.isfinite(prediction.expected_heat_flux_w_m2))
assert np.all(prediction.heat_flux_lower_bound_w_m2 <= prediction.expected_heat_flux_w_m2)
assert np.all(prediction.expected_heat_flux_w_m2 <= prediction.heat_flux_upper_bound_w_m2)
```

The same calculation, with energy and missing-activity checks, is saved as
[validate.py](../demonstration/heat_reference_models/validate.py). Run
`python demonstration/heat_reference_models/validate.py` from the repository.
It writes [validation.json](../demonstration/heat_reference_models/validation.json),
including all supplied inputs, output maps, bounds and parameter provenance.

For a field application, replace the illustrative physical inputs with aligned,
appropriately scoped observations or external-model outputs and retain their
provenance. Unit checks, conservation checks and numerical enclosures verify
implementation properties. They do not establish event-specific radiative-flux,
operational forecast, or receiver-temperature validity.
