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

## 2026-10-15 00:10 CST: literature verification results (research subagents)

Goal: verify the prompt's numbers against original papers and collect parameters.

Results (details and URLs in docs/PARAMETERS.md and data/SOURCES.md):
- Mphale and Heron (2007, J. Phys. D 40:2818) full text: attenuation 1.64 to 5.68 dB at 8 to 10.5 GHz (the abstract rounds to "1.6 to 5.8"); ne 0.51 to 1.35e16 m^-3 and nu 3.43 to 5.97e10 s^-1 confirmed. The burner was 0.5 m wide, but the authors' own inversion treats the reported dB values as dB/m, so the per-metre value is ambiguous by a factor of 2.
- "Largest losses through the hottest zone" is from Mphale's 2008 thesis and is a lab-time and modeling statement, not a measured height profile.
- Field crossings at VHF were tiny (0.03 to 0.05 dB over 44 m; 0.43 dB over 590 m of cane fire). Operation Euroka (1970, cited second hand) reported under 5 dB at UHF and X band over about 40 m at 1.7 m above the fuel.
- "Flames matter far more than smoke" holds for Hong et al. (2021) but is contradicted by Li et al. (2017) at 350 to 400 MHz and by Bystrov et al. (2021) at 79 and 300 GHz (smoke slightly worse than flame, both at most 0.13 dB/m).
- OpenMRG is open (Zenodo 7107689, CC BY-SA 4.0, 318 MB, 10 s sampling, RSL 0.3 dB, TSL 1 dB, ATPC disabled). OpenRainER (CC BY 4.0, 1 min, 25 GHz, mountainous) is a later option.
- Korea: microwave share of mobile backhaul in North East Asia is about 6 percent (Ericsson Microwave Outlook 2025); the only Korean CML study used KT 6 to 8 GHz relay links of 5.7 to 37.4 km.
- Uiseong fire: ignition 22 March 2025 about 11:25 KST, about 99,000 ha, 26 dead in five counties, peak spread 8.2 km/h reported, 1 to 3 mm of rain on 27 to 28 March.

Decisions: correct the quoted range to 1.6 to 5.7 dB; add a "field bound" flame scenario (path-averaged ne = 3.5e14 m^-3, from Euroka's under-5-dB-over-40-m bound) next to the lab values; treat the flame-versus-smoke statement as contested.

## 2026-10-15 00:30 CST: step 3 physics model

Goal: Drude attenuation 1 to 80 GHz, plume structure, mean loss and scintillation versus ray height.

Command: `.venv/bin/python src/run_physics.py` (config `configs/physics.json`), runtime about 70 s.

Parameters: lab peak ne 1.35e16 m^-3, nu 3.43e10 s^-1; field bound ne 3.5e14 m^-3, nu 5e10 s^-1; flame mean temperature 1100 K; K mole fraction 1e-5 (assumption); calm-air line plume with entrainment 0.16 and convective fraction 0.75; temperature fluctuation 0.4 of the mean excess; surface fire 2 MW/m (Byram flame 2.6 m, flaming depth 20 m); crown fire 30 MW/m (flame top 30 m, depth 60 m); 5 km link, fire at mid-span; flame height jittered 0.6 to 1.4 times the mean and power averaged over +-1 F1 of ray height to remove model ripple.

Results (modeled):
- Drude reproduces the reported lab values within 19 percent when they are read as dB/m (consistency check only, because ne and nu were inverted from the same data). Lab-peak specific attenuation falls from 6.9 dB/m at 7 GHz to 1.5 at 18, 0.37 at 38 and 0.08 at 80 GHz. Field-bound values are 40 times lower.
- Saha equilibrium cannot produce 1e16 m^-3 at 1100 K; the calibrated effective ionization temperature is 1620 K. Above the flame top, Saha electrons vanish within a metre; even the frozen-ion bound gives under 1e12 m^-3 above twice the flame height. Plume absorption is negligible at every band.
- Mean excess loss needs the flame inside the first Fresnel zone: at 18 GHz with the ray at the flame top, 1.6 dB (surface) and 2.9 dB (crown, lab peak); at 50 m and 150 m ray height it is within the +-0.3 dB model ripple.
- Plume scintillation (calm-air upper bound) at 18 GHz: crown fire 0.55 dB std at 50 m ray height and 0.17 dB at 150 m; surface fire 0.07 dB at 50 m.

Decisions: the first loss-versus-height figure showed unphysical Fresnel ripple from the sharp model flame top; added flame-height jitter and ray-height averaging, and a grey band marking the remaining +-0.3 dB ripple. Scintillation is capped at the saturated 5.6 dB.

Next step: fire spread model and synthetic RSL crossings on the hypothetical links.

## 2026-10-15 01:20 CST: step 5 synthetic fire crossings

Goal: move a fire across the real terrain and compute each crossed link's fire-induced mean loss A(t) and scintillation std S(t).

Command: `.venv/bin/python src/run_crossings.py` (config `configs/crossings.json`, plus geometry and physics configs). First run (wind toward 112.5 deg, ESE) took 2 min; the fire left the DEM through the southern edge and the signatures flickered on and off because a slow front crossed 15 m profile samples faster than 10 s steps could see. Fixes: wind toward 90 deg (east, the observed Uiseong to Yeongdeok track along 36.4 N) and a minimum burning time per sample of step/ROS with the flame path rescaled. Second run: 8.5 min.

Parameters: 90 m minimum-travel-time spread (16 neighbours) with Alexander (1985) ellipse and McArthur slope rule; ignition 128.585 E, 36.383 N (Anpyeong-myeon centroid, approximate); "moderate" head ROS 0.4 m/s with 36 km/h wind, "extreme" 1.5 m/s with 54 km/h; Byram intensity with 18,000 kJ/kg and 1.5 kg/m^2 (surface) or 3.0 kg/m^2 (crown); crown fire when intensity exceeds 2000 kW/m; flame residence 40 s (surface) and 60 s (crown); 10 s time step over 24 h.

Results (simulated, hypothetical links):
- Moderate: 12,890 ha in 24 h, 99 links crossed. No link reached 1 dB peak mean loss; 0 to 18 percent per band (100 percent of the two 80 GHz links) reached 0.3 dB peak scintillation std.
- Extreme: 100,438 ha in 24 h (comparable to the real fire's final 99,289 ha over about a week), 621 links crossed, 74 to 83 percent of the burned length in crown fire. Share of crossed links with peak mean loss of at least 1 dB (lab-peak ne): 7 to 12 percent per band; with the field-bound ne: 0 to 9 percent. Share with peak scintillation std of at least 0.3 dB: 16 to 33 percent.
- Signatures are short: mean-loss dips last one to a few minutes, while flames sit in the Fresnel zone near a low-clearance point; scintillation lasts as long as flames burn anywhere under the link.

Decisions: keep both spread scenarios; signatures are saved without noise in `results/crossings/signatures_<scenario>.npz` for injection into real noise.

Next step: detection with OpenMRG dry-weather noise (download in progress).

## 2026-10-15 01:45 CST: OpenMRG download

Goal: real dry-weather link noise for step 6.

Commands: `curl -L -o OpenMRG.zip https://zenodo.org/records/7107689/files/OpenMRG.zip?download=1` ran at 3 to 7 MB/min and was later stopped by the background time limit. A range request for the last 94 kB gave the zip central directory: `cml/cml.nc` alone is 307 MB compressed (4.6 GB uncompressed), so no partial shortcut exists. Eight parallel `curl -r` range requests fetched bytes 160,000,000 to the end, and these were joined to the first 160 MB of the slow download. The assembled file has MD5 4e4cdf6ced4d45a084c348f245b8d690, matching Zenodo. Extracted `cml/`, `gauges/` and `readme.txt` into `data/raw/openmrg/extracted/` (git-ignored).

Results: cml.nc has dims (time 794,887 at 10 s, sublink 728), with rsl and tsl in dBm, 1 Jun to 1 Sep 2015. A test on 10 sub-links gave dry-period standard deviations of RSL - TSL of 0.14 to 0.34 dB. 50 percent of the time falls within 3 h of a city-gauge rain tip.

## 2026-10-15 02:05 CST: step 6 first detection run (no link screening)

Goal: inject the step 5 signatures into dry OpenMRG noise and evaluate the drop and variance detectors under five logging schemes.

Command: `.venv/bin/python -I src/run_detection.py` (config `configs/detection.json`, 120 random sub-links, seed 20261014), runtime 6 min. A first test with the synthetic AR(1) fallback (OpenMRG not yet downloaded) found two bugs, both fixed: a 1 min resampling length error, and `DataFrame.ne` shadowing the "ne" column, which silently emptied the localization table.

Results: 4,360 dry link-days and 3,676 wet link-days. False alarm rates on all dry noise were high: 0.083 per link-day for a 3 dB drop at 10 s, and 0.008 per link-day even at 9 dB. In rainy periods they were 2.2 per link-day at 3 dB. At 0.01 false alarms per link-day almost nothing was detected (0.8 percent of extreme-scenario crossings).

Diagnosis: alarms are concentrated in a few erratic sub-links. 64 percent of sub-links had no 3 dB drop alarm in about 30 dry days, while the worst 10 percent produced 83 percent of all alarms.

Decision: add link screening, as operational CML rain processing does (Graf et al. 2020 drop erratic links). Sub-links are ranked on June dry data, the best 80 percent are kept, and false alarms and detection are evaluated only on July and August. The FAR targets are now 0.1, 0.01 and 0.001 per link-day, with 0.01 as the main one. Threshold grids were extended upward.
