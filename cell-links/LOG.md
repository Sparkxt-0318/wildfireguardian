# LOG

Append-only. Times are Asia/Shanghai (CST, UTC+8). Each entry: goal, commands, parameters, results, decisions, next step.

## 2026-10-14 22:38 CST: setup

Goal: create an isolated workspace for the cell-links feasibility study.

Commands:
- `git rev-parse --show-toplevel` returned `/home/user/wildfireguardian`; branch `claude/epic-gauss-sbsk2w`. Read the root README (routing API docs); nothing in it is used here.
- `mkdir -p cell-links/{docs,data/raw,results,figures,src,configs}`
- `python3 -m venv cell-links/.venv` (Python 3.13.16, Linux container; the target machine is an M4 Pro Mac, all packages used have Apple Silicon wheels)
- `.venv/bin/pip install numpy scipy matplotlib pandas rasterio pyproj xarray netCDF4 pycomlink`
- Downloaded Copernicus GLO-30 tiles N36 E128 and N36 E129 from the AWS open data bucket (48.5 MB and 21.2 MB) into `data/raw/dem/` (git-ignored).

Results: all installs succeeded; DEM download succeeded, so real terrain is used (no synthetic fallback needed).

Decisions: pycomlink is used only for its ITU-R P.838 rain coefficients (`k_R_relation.a_b`). Two research subagents were started to verify literature numbers and dataset availability.

Next step: physics model and terrain geometry in parallel with the literature check.

## 2026-10-14 23:05 CST: physics module first sanity checks

Goal: check the Drude and diffraction code before using it.

Commands: ad hoc `.venv/bin/python` checks of `src/physics.py`.

Results:
- Knife edge exactly at the ray gives 6.02 dB loss; clearance 0.6 F1 gives a 0.37 dB gain; 1.0 F1 gives a 1.02 dB gain. These match textbook knife-edge values, so the Fresnel-integral screen is correct.
- Drude specific attenuation at 8 to 10.5 GHz for ne = 0.5 to 1.4e16 m^-3 and nu = 3.4 to 6.0e10 s^-1 is 1.42 to 6.34 dB/m (exact) and agrees with the weak-plasma formula within 1 percent.
- Thermal (Saha) ionization of potassium at a mean flame temperature of 1100 K cannot give 1e16 m^-3 with any physical K content (needs nK above total gas density). Decision: define an effective ionization temperature T_ion (1480 to 1700 K for K mole fraction 1e-4 to 1e-6) calibrated to the measured ne, and cool it with the plume dilution.

Next step: terrain geometry.

## 2026-10-14 23:20 CST: step 4 geometry on Copernicus DSM

Goal: hypothetical ridge-top links on real terrain around the Uiseong fire, and how much of each path a fire can reach.

Command: `.venv/bin/python src/run_geometry.py` (config `configs/geometry.json`), runtime 25 s.

Parameters: bbox 128.45 to 129.45 E, 36.25 to 36.65 N, UTM 52N at 30 m; sites are local maxima in a 2 km window with topographic position index above 40 m, at least 2.5 km apart, top 220 by TPI; antennas 30 m above the DSM; k = 4/3; links accepted only if the ray clears DSM plus Earth bulge by 0.6 F1 everywhere (standard planning rule); shortest feasible hops first, at most 3 links per site per band. Bands and hop lengths: 7 GHz 10 to 30 km, 13 GHz 5 to 18 km, 18 GHz 3 to 12 km, 23 GHz 2 to 8 km, 38 GHz 1 to 4 km, 80 GHz 0.5 to 3 km. Fire heights above DSM: surface flame 2 m (4 m high case), crown flame 20 m (35 m high case), calm-air line-plume heights for dT thresholds.

Results (modeled, hypothetical links): 215 sites, 1520 links. Median ray clearance 187 m. Length-weighted share of link length where the flame enters the first Fresnel zone: surface flame 0.000 in every band; crown flame (20 m) 0.001; crown flame (35 m) 0.018 overall but only 0.004 outside the 300 m tower zones. Share where the calm-air crown plume (30 MW/m) exceeds 100 K at the ray: 0.032 (0.005 outside tower zones); exceeds 30 K: 0.338. Exact values per band are in `results/geometry/summary.csv` and NUMBERS.json (`geom.*`).

Decisions: separated tower zones (within 300 m of an antenna) because a 30 m antenna height makes any 35 m flame at the tower base reach the beam, which says more about site survival than about detection. Reworked the map into small multiples and moved the profile legend below the panels after inspection (first versions were cluttered or overlapping).

Next step: the physics figures and the Mphale and Heron check, once the literature agent reports the original geometry.
