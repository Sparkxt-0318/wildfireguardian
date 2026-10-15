# Last Gasp: can dying devices map a wildfire's spread?

A self-contained feasibility experiment inside the WildfireGuardian repository. It does not import or modify any other part of the repository.

All results here are from synthetic simulations. They are not real-world performance.

## What this is and why

When a wildfire destroys a building, its connected devices go offline:
- smart electricity meters send a "last gasp" to the utility;
- routers drop off the internet provider's network;
- battery radio tags stop broadcasting.

If we knew the minute each device died, we might reconstruct the fire's arrival time building by building, through smoke and at night. That would be far denser in space and time than polar-orbiting satellite detections such as FIRMS.

The catch is that devices also die for non-fire reasons. A failed power line blacks out a whole branch, messages get lost, and clocks are noisy. This folder tests, in a synthetic but realistic world, how well death times can recover:
- (a) the arrival-time map;
- (b) spot fires;
- (c) fire-caused versus grid-caused outages.

It also tests which node densities, delivery rates, noise levels and grid fault rates make it work or break. The original brief is in `docs/PROMPT.md`.

## Current status (2026-10-15): frozen

No new experiments. The booth summary is `BOOTH.md` (English and Korean) with `figures/fig13_booth.png`. Draft pull request: https://github.com/Sparkxt-0318/wildfireguardian/pull/54.

### Phase 1 (complete): `RESULTS.md`

- Grid-powered smart-meter last gasp is weak as a fire tracker. About 75% of the fire signal is censored by upstream outages, and KEPCO AMI evidence does not show timestamped last gasps.
- Independent tags reconstruct arrival times well.

### Phase 2 (first pass of all five items complete): `RESULTS_PHASE2.md`

- **Receive side.** A LoRa tag mesh with 3 spread-out, fire-exposed gateways hears 96% of tag deaths. Arrival-time error is 1.6 / 5.6 min at 12 tags per km².
  - Gateway placement and independent power matter more than gateway count.
  - Store-and-forward helps only at the gateway, during backhaul outages.
- **Utility trip logs** add value only where tags are very sparse, and precautionary shutoffs remove or corrupt the signal.
- **Cost** is about $1,050 per km² up front for tags every 200 m of road (estimate).
- **Spot fire detection** remains weak (6% recall at 200 m spacing).
- **The core idea is prior art** (IBM patent, 2014). The reconstruction and spotting layer is the possible contribution.
- **Booth demo:** `demo/` runs in simulator mode.
- **Overall real-world feasibility: low to moderate.** The biggest open questions are tag death timing in a real fire and radio range in Korean terrain.

## Layout

| Path | Contents |
|---|---|
| `RESULTS.md` | Phase 1 findings (meters versus tags), go or no-go, data to request |
| `BOOTH.md` | One-page booth story in English and Korean, with the booth figure |
| `RESULTS_PHASE2.md` | Phase 2: receive side, trip logs, economics, novelty, demo, updated go or no-go |
| `demo/` | Booth display (simulator, serial or BLE input), heartbeat format, example ESP32 sketch; see `demo/README.md` |
| `LOG.md` | Append-only run log (Asia/Shanghai time) |
| `docs/PROMPT.md` | Original brief, verbatim |
| `docs/PARAMETERS.md` | Every phase 1 parameter, its default and the reason or source |
| `docs/PARAMETERS_PHASE2.md` | Phase 2 radio, gateway, trip-log and cost parameters with sources |
| `docs/UTILITY_LOGS.md` | Desk research: KEPCO trip logging and 2025 power events |
| `docs/NOVELTY.md` | Desk research: prior art and existing sensor networks |
| `docs/DESK_RESEARCH.md` | Real-world check: AMI in Korea, outage logging, data holders, legal limits |
| `data/SOURCES.md` | Provenance and licenses of all external data, papers and sources |
| `data/processed/world_yeongdeok.json` | OSM roads, 59 OSM buildings, substation and 1,441 synthetic buildings (ODbL) |
| `configs/default.json`, `configs/phase2.json` | All model parameters (phase 1, phase 2) |
| `lastgasp/` | Python package. Phase 1: `world`, `fire`, `grid`, `observe`, `classify`, `reconstruct`, `pipeline`. Phase 2: `deploy`, `receive`, `phase2`, `trips`, `economics`. Shared: `style`, `provenance`. |
| `scripts/` | Numbered run scripts and `run_all.sh` |
| `results/` | Metrics, sweep table and summary, `NUMBERS.json` (every quoted number with its provenance) |
| `figures/` | Figures 1 to 8, PNG at 300 dpi and SVG |

## How to run

Tested with Python 3.13 on Linux. All pinned dependencies publish Apple Silicon (macOS arm64) wheels.

```sh
cd last-gasp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
bash scripts/run_all.sh        # phase 1, about 7 to 10 minutes on 4 cores
```

Individual steps:

```sh
.venv/bin/python scripts/01_build_world.py            # download OSM if missing, build world and network
.venv/bin/python scripts/02_example_run.py --tag default
.venv/bin/python scripts/02_example_run.py --tag tags50 --set observe.meter_fraction=0.0 observe.tag_fraction=0.5
.venv/bin/python scripts/03_sweeps.py --workers 4     # 410 runs, writes results/sweeps.csv
.venv/bin/python scripts/04_figures_example.py        # figures 1 to 3
.venv/bin/python scripts/05_figures_sweeps.py         # figures 4 to 7 and results/sweep_summary.json
.venv/bin/python scripts/06_demo_sim.py               # figure 8, tabletop demo analogue
.venv/bin/python scripts/07_numbers.py                # results/NUMBERS.json (phase 1 and 2)

# Phase 2
.venv/bin/python scripts/10_phase2_sweeps.py --workers 4   # 1,150 runs, about 4 min; results/phase2_sweeps.csv
.venv/bin/python scripts/11_phase2_figures.py              # figures 9 to 12, results/phase2_summary.json
.venv/bin/python scripts/12_demo_metrics.py                # booth simulator metrics
.venv/bin/python scripts/07_numbers.py
```

Booth demo without hardware: `cd demo && ../.venv/bin/python -m lastgasp_demo --sim`.

Any parameter can be overridden for one run, for example `--set grid.substation_trip_min=40`.

The processed world file is committed, so the OSM download is only needed if you delete it. The raw OSM extract and per-run caches are not committed (`.gitignore`).

## Pipeline in brief

1. **World.** Real OSM roads and substation for Yeongdeok-eup, plus synthetic buildings along roads, because OSM maps only 59 buildings there.
2. **Fire truth.** 10 m anisotropic eikonal model (Dijkstra on a 16-neighbour grid), with an elliptical spread shape from wind, lognormal fuel variability and a lognormal spotting kernel with recomputation.
3. **Power network.** Radial feeders grown along roads from the substation, with breakers, reclosers, lateral fuses and transformer cutouts. A fault opens the nearest upstream device.
4. **Observation.** Fire, fire-caused grid faults, unrelated grid and device failures, delivery probability, clock jitter, ISP polling and tag heartbeats.
5. **Classification.** Topology-based burst detection per protective device, compared with a time-only rule.
6. **Reconstruction.**
   - IDW baseline.
   - A Huygens min-plus (eikonal) field with a fitted elliptical spread model, a k-th order statistic for robustness and a residual correction.
   - Spot detection from unexplained early deaths with surviving nodes in between.
7. **Evaluation.** Arrival-time error at every burned building, spot precision and recall with distance error, and classification balanced accuracy.

## Working rules followed

- All work stays inside `last-gasp/`, with its own `.venv` and `requirements.txt`.
- Commits start with `[last-gasp]` and stage only this folder.
- Nothing was pushed. The development environment for this pass was a Linux cloud container, not the MacBook named in the brief, so macOS installation is untested. The pinned packages publish macOS arm64 wheels.
