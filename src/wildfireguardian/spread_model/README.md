# `spread_model` — wildland fire spread

**Status**: implemented (Rothermel point model + Huygens-elliptical CA).

**Purpose**: predict where a fire perimeter goes next, given fuel, weather,
and topography. This is the scientific core of the project.

**Inputs**:

- Fuel: one of the Anderson 13 standard fuel models (`FUEL_MODELS["FM4"]`,
  etc.) and a fuel moisture content (fraction, e.g. 0.40 for 40 % LFMC).
- Weather: midflame wind speed (m/s) and direction (° from north).
- Topography: slope (degrees) and aspect (° from north).

**Outputs**:

- `rothermel.compute_spread_rate(...)` → a `SpreadResult` dataclass containing
  spread rate (m/min) plus every intermediate quantity ($I_R$, $\xi$,
  $\phi_w$, $\phi_s$, $\rho_b$, $\varepsilon$, $Q_{ig}$, $\eta_M$, $\eta_s$).
- `cellular_automaton.FireGrid.run(...)` → a list of
  `(time_min, perimeter_polygon)` tuples plus the final burn-probability
  raster.

**Algorithmic basis**:

- Rothermel, R.C. (1972). *A mathematical model for predicting fire spread in
  wildland fuels.* USDA Forest Service Research Paper INT-115.
- Andrews, P.L. (2018). *The Rothermel surface fire spread model and
  associated developments: a comprehensive explanation.* USDA Forest Service
  General Technical Report RMRS-GTR-371.
- Finney, M.A. (1998). *FARSITE: Fire Area Simulator — model development and
  evaluation.* USDA Forest Service Research Paper RMRS-RP-4.
