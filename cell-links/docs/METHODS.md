# Methods

This note records how each step is modeled. The parameter values and their sources are in [PARAMETERS.md](PARAMETERS.md). All outputs of these methods are modeled estimates, except the OpenMRG noise, which is observed data.

## Step 3: propagation physics (`src/physics.py`, `src/run_physics.py`)

Flame plasma. The flame is a cold collisional plasma with permittivity eps = 1 - wp^2 / (w (w + i nu)), wp^2 = ne e^2 / (eps0 me). The specific attenuation is 8.686 k0 Im(sqrt(eps)) dB/m. We use the exact expression, not the weak-plasma limit (the two agree within 1 percent here).

Flame and plume structure above a long fireline:
- Flame band from the ground to the flame height H, with a mean temperature of 1100 K and the measured ne and nu.
- Above the flame, a calm-air line plume (top-hat Morton-Taylor-Turner similarity, entrainment 0.16): excess temperature ΔT = T_amb (B / 2 alpha)^(2/3) / (g z), with buoyancy flux per unit length B = g Q_conv / (rho cp T_amb). Calm air is an upper bound on plume temperatures at link height, because wind bends the plume over and dilutes it.
- Plume electrons come from two models:
  - Central model: local Saha equilibrium for potassium at an effective ionization temperature, calibrated to the measured flame ne and cooled in proportion to plume dilution. Electron attachment to O2 is held in thermal equilibrium.
  - Upper bound ("frozen ions"): ions are diluted but never recombine, and electrons are lost only to attachment.
- Refractivity follows ITU-R P.453, using local temperature and vapour pressure. The vapour pressure includes combustion water in proportion to the convective heat.

Mean loss through a burning line. The link ray passes at height c above the ground at the fire location, at d1 from the transmitter and d2 from the receiver. We treat the fire as a thin screen perpendicular to the link. The screen is opaque below the ground, has complex transmission exp(i k0 Δn(z) path(z)) above it, and is uniform along the fireline. The received field is the 1-D Fresnel-Kirchhoff integral, evaluated exactly with Fresnel integrals for piecewise-constant transmission.

Two averages remove unphysical Fresnel ripple caused by the sharp model edges:
- Received power is averaged over flame heights from 0.6 to 1.4 times the mean, because flame tips are intermittent.
- Results are averaged over ±1 first-Fresnel-zone radius of ray height.

Excess loss is the loss with fire minus the loss from ground diffraction alone. The method reproduces knife-edge values: 6.02 dB at grazing incidence, and a 1.0 dB gain at a clearance of 1 F1.

Scintillation. Weak-fluctuation Rytov theory for a spherical wave through a thin turbulent slab:
- sigma_chi^2 = 0.563 k^(7/6) Cn^2 Δx (d1 d2 / L)^(5/6).
- Cn^2 comes from C_T^2 = 2 sigma_T^2 L0^(-2/3), with sigma_T = 0.4 ΔT, L0 equal to the plume half-width, and dn/dT from the refractivity model.
- The level standard deviation is 8.686 sigma_chi, capped at the saturated (Rayleigh) value of 5.6 dB.

## Step 4: terrain geometry (`src/terrain.py`, `src/run_geometry.py`)

The Copernicus GLO-30 DSM tiles N36 E128 and E129 are mosaicked, cropped to 128.45 to 129.45 E and 36.25 to 36.65 N, and reprojected to UTM 52N at 30 m.

Candidate tower sites are local maxima within a 2 km window whose topographic position index exceeds 40 m. They must be at least 2.5 km apart, and the 220 sites with the highest TPI are kept.

For each band, candidate site pairs are those within the band's hop-length range. Pairs are tried shortest first, and a link is accepted if the ray between 30 m antennas clears the DSM plus the Earth bulge (k = 4/3) by 0.6 F1 at every 15 m sample. Each site can have at most three links per band.

Along every accepted link we record the share of path length where each of the following holds:
- a flame of a given height above the DSM enters the first Fresnel zone, or reaches the ray;
- the calm-air plume exceeds a temperature threshold at ray height.

Because the DSM is close to canopy top in forest, adding surface-fire flame heights to it is optimistic. The links are hypothetical and are not real operator links.

## Step 5: fire spread and signatures (`src/spread.py`, `src/run_crossings.py`)

Spread model:
- Minimum travel time is computed with Dijkstra on a 90 m, 16-neighbour raster.
- Directional spread rate follows an Alexander (1985) wind ellipse.
- Slope uses the McArthur factor exp(0.069 theta), floored at 0.2.
- There is no fuel map: all land above 1 m elevation burns.

Fire intensity at each point is I = 18,000 kJ/kg x fuel consumed x local rate of spread, where the local rate of spread is 1 / |grad t|. Points above 2000 kW/m are crown fire. Flame height is Byram for surface fire and Thomas for crown fire (capped at 35 m above the DSM).

Each 15 m link sample burns for its residence time (40 or 60 s) after the fire arrives. At every 10 s step, each contiguous burning segment is treated as one screen at its centre, with the segment length as the beam path through the flame. Mean losses (in dB) and scintillation variances add over segments.

## Steps 6 and 7: detection (`src/detect.py`, `src/run_detection.py`, `src/run_confounders.py`)

Noise. OpenMRG RSL - TSL at 10 s (ATPC disabled in that network) for 120 randomly chosen sub-links. A period counts as dry if no city rain gauge reported rain within ±3 h. Dry chunks shorter than 12 h are discarded. If OpenMRG cannot be read, a documented AR(1) model (0.15 dB, rho 0.98, 0.3 dB steps) is used instead, and the log says so.

Injection. Each crossed link's mean loss A(t) plus scintillation S(t) N(0,1) is subtracted from a random dry chunk, after a 6 h signal-free lead used for the baseline.

Logging schemes:
- 10 s with 0.3 dB steps;
- 1 min instantaneous with 0.3 dB steps;
- 15 min minimum and maximum with 1 dB steps;
- 10 s with only RSL logged, under ATPC with a 2 or 5 dB window (logged fades are clipped at the window).

Detectors:
- Drop: a causal 60 min median baseline (ending 2 min before the sample) minus the level, required to persist for two 10 s samples or one 1 min sample. For 15-min logs, the drop of the 15-min minimum below the median of the previous 24 minima.
- Variance: the 3 min (10 min for 1-min data) rolling standard deviation divided by its causal 6 h median, with a floor of 0.087 dB (the 0.3 dB quantization noise). For 15-min logs, the growth of the max-min range over its 6 h median.

Evaluation:
- False alarm rate: alarm onsets per link-day on fire-free dry noise, with onsets merged within 60 min.
- Detection probability: the share of crossed links whose first alarm falls while the signature is active, or within 15 min after it.
- Delay: measured from the moment the fire first reaches the link's ground track.
- Localization: compares the link midpoint with the true first crossing point. The spread vector comes from a plane fit t = a + b x + c y to alarm times at link midpoints, compared with the same fit to the true crossing times and points.
