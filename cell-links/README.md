# Cell links: can microwave links act as wildfire tripwires?

An isolated feasibility experiment inside the WildfireGuardian repository. It does not use or change the forecasting or routing code.

## What and why

Mobile networks connect some mountain towers with point-to-point microwave links, and operators log the received signal level (RSL). Hydrologists already turn the rain-induced fading of these commercial microwave links (CMLs) into rainfall maps.

Vegetation flames also attenuate microwaves, because potassium from burning plants ionizes. If a wildfire crossing a link caused a detectable dip, existing links over Korean ridges could act as fire tripwires that work at night and through smoke.

This folder tests that idea for the March 2025 Uiseong fire area. It covers:
- the literature numbers;
- a flame and plume propagation model;
- hypothetical links on real terrain;
- simulated fire crossings;
- detection in real link noise from the open OpenMRG dataset.

## Status (2026-10-15)

First pass complete for all eight steps. Result: no-go for existing commercial backhaul as a primary tripwire. Planned links clear the terrain by a median of 187 m, so flames rarely enter the Fresnel zone. At realistic false-alarm rates, a few percent of simulated crossings are detected. The recommended next step is to request real link logs for the 2025 fire period.

Read [RESULTS.md](RESULTS.md) first. All simulated results are modeled estimates, not observations.

## Layout

| Path | Contents |
|---|---|
| `RESULTS.md` | Findings, go/no-go, next step, booth demo |
| `LOG.md` | Append-only run log (Asia/Shanghai time) |
| `docs/PROMPT.md` | The original request, verbatim |
| `docs/PARAMETERS.md` | Cited parameter table, with corrections to the prompt's numbers |
| `docs/METHODS.md` | How each step is modeled |
| `data/SOURCES.md` | Provenance and licences of every dataset and paper |
| `configs/*.json` | All run parameters |
| `src/physics.py` | Drude plasma, Saha ionization, line plume, refractivity, Fresnel screen, Rytov scintillation |
| `src/terrain.py`, `src/spread.py`, `src/detect.py` | DEM profiles, fire spread, detectors |
| `src/run_*.py` | One script per step (geometry, physics, crossings, detection, confounders, extras) |
| `results/` | CSV outputs and `NUMBERS.json` (every quoted number, with script, config and commit) |
| `figures/` | PNG (300 dpi) and SVG figures |
| `demo/` | Two-ESP32 booth demo: Arduino sketches and a live chart script |

## How to run

Tested with Python 3.13 on Linux; the target is macOS on Apple Silicon. All dependencies have arm64 wheels.

```sh
cd cell-links
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Data (git-ignored, about 390 MB in total)
mkdir -p data/raw/dem data/raw/openmrg/extracted
for t in N36_00_E128_00 N36_00_E129_00; do
  curl -o data/raw/dem/Copernicus_DSM_COG_10_${t}_DEM.tif \
    https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_${t}_DEM/Copernicus_DSM_COG_10_${t}_DEM.tif
done
curl -L -o data/raw/openmrg/OpenMRG.zip "https://zenodo.org/records/7107689/files/OpenMRG.zip?download=1"
# expected MD5 4e4cdf6ced4d45a084c348f245b8d690
(cd data/raw/openmrg/extracted && unzip ../OpenMRG.zip 'cml/*' 'gauges/*' readme.txt)

# Everything (about 30 minutes on 4 cores; needs about 3 GB of RAM)
./run_all.sh
```

Each step can also be run on its own:

```sh
.venv/bin/python src/run_geometry.py
.venv/bin/python src/run_physics.py
.venv/bin/python src/run_crossings.py
.venv/bin/python -I src/run_detection.py
.venv/bin/python -I src/run_confounders.py
.venv/bin/python -I src/run_extras.py
```

The scripts that read the downloaded OpenMRG data are run with `-I` (isolated mode), as a precaution with untrusted downloads. Expect the following:
- The Zenodo download can be slow. Parallel `curl -r` byte ranges, joined in order, worked well (see LOG.md).
- `cml.nc` unpacks to 4.6 GB.

`run_all.sh` refuses to run if `src/` or `configs/` have uncommitted changes. That way every entry in `results/NUMBERS.json` names the commit of the code that produced it.

## Licences and attribution

- Copernicus DEM: produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA; all rights reserved.
- OpenMRG: Andersson et al. (2022), CC BY-SA 4.0. Statistics derived from it in `results/detection/` are shared under the same licence.

See `data/SOURCES.md` for details.
