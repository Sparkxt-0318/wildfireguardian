# Cropped Fish Creek spatial heat maps

Cutoff **2024-08-23T00:00:00Z**; forecast interval **00:00–01:00 UTC** on 23 August 2024. Full grid: **103 × 73**, 375 m cells, EPSG 5070. Display crop: original zero-based rows **8–40**, columns **13–51**, or **33 × 39** cells.

The full grid is used for radiation calculation. The display crop includes every current burned cell and every cell with positive predicted first-new-burning probability, plus a three-cell margin. Radiation is nonzero beyond the crop; its tails are not the crop criterion. Rows increase downward, as in the original spatial matrix. White contours mark current burned boundaries. Heat and fuel arrays are co-registered without interpolation.

## Files

- `fuel_and_mean_heat_cropped.png/.svg`: panels A (fuel) and B (mean heat) side by side in one row.
- `fuel_and_mean_heat_log_cropped.png/.svg`: the same values with a logarithmic heat color scale to reveal weaker radiation.
- `burned_fuel_probability_heat_cropped.png/.svg`: aligned current state, fuel, probability and mean heat.
- `mean_and_endpoint_heat_cropped.png/.svg`: mean and endpoint flux on a common linear scale.
- `fuel_distribution_and_coverage_cropped.png/.svg`: mapped reference, scenario fuel and lookup coverage.
- `spatial_matrices.npz`: full-grid arrays, validity, geographic coordinates, grid and crop indices.
- `*_cropped_*.csv`: displayed matrices; their first row/column corresponds to the crop start.
- `summary.json`: source/checkpoint provenance, assumptions, values and checks.

- `duration_sensitivity.json`: fixed-input scenarios at 0.05, reported median, 0.10 and 0.20 m/s.

## Interpretation and assumptions

Raw state coverage contains 191 burned, 2451 known unburned and 4877 unavailable cells. The figure retains unavailable states in gray. For the conditional forecast, unavailable cumulative states are explicitly assumed unburned, and exterior model context is zero. Thus finite forecast coverage does not establish observed state coverage.

Fuel is static FCCS reference dry mass per entire ground-cell area. For readable partial coverage, scenario mass is coverage × mapped mass + (1 − coverage) × 10 kg/m²; unreadable loading uses 10 kg/m² for the entire cell. This is not measured remaining fuel. Combustion uses 10% phase consumption, 18 MJ/kg released heat, radiative fraction 0.30, 5 m source elevation above upward-facing ground receivers and transparent transmission. Local point residence uses FBFM40 reference SAV; unsupported/nonburnable codes use an explicit 2000 ft⁻¹ SAV fallback. The fallback does not establish combustible fuel. Cell emission lasts for a straight front's cell crossing time plus point residence. The configured speed is 0.09472222222 m/s and direction is 0° counterclockwise from projected +x. The default is the reported PT-FireSprd median 341 m/h (Benali et al. 2023), not a calibrated Fish Creek measurement. Cell durations range from 66.169 to 66.296 minutes. This is a reference scenario, not a postfrontal burnout estimate. The reconstructed arrival is retained as a cell burn-start scenario. The model uses a uniform whole-cell pulse and divides the same consumed-fuel energy by the longer duration.

New initiation is uniform within the hour conditional on first burning. Existing activity uses only reconstructed past arrival on known burned support and the same residence durations. This gives **5 nominal active cells** at the cutoff. The displayed mean heat sums their remaining-emission contribution and the expected contribution of predicted new ignitions. Separate component maps are exported and verified to sum to the total. Current activity is a scenario, not an observation.

Peak mean incident radiant flux: **1594.232648 W/m²**. Peak endpoint flux: **38.750432 W/m²**. Peak next-hour first-new-burning probability: **2.328285%**. Flux is sampled at receiver cell centers, not averaged over receiver areas. It excludes convection, external fires, parameter uncertainty and uncertainty in reconstructed arrivals. These are conditional model outputs, not measured or operationally validated heat maps.

Reproduce from the repository with `.venv/bin/python demonstration/heat_spatial_maps/generate.py`. Change speed with `--spread-rate-m-s 0.20` or direction with `--spread-direction-deg 45`.
