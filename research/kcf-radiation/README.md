# kcf-radiation: radiant heat at the road by published methods

Replaces the project's own heat law (research/kcf-heat, gate not passed) with established methods: rate of spread
from the arrival raster, Byram intensity, Van Wagner crown test, Byram / Thomas flame length, Albini tilt, a
solid-flame radiation model with four view-factor geometries, and graded flux thresholds (7 / 4.7 / 2.5 kW/m2).
Nothing new is proposed.

| file | what |
|---|---|
| [PROTOCOL.md](PROTOCOL.md) | frozen before any result; amendments A1-A4 at the end |
| [METHOD.md](METHOD.md) | every formula with its source and range |
| [RESULTS.md](RESULTS.md) | checks C1-C4, the per-fire tables, the panels, the counts against no heat and the old law |
| [DATA.md](DATA.md) | inputs and where they came from (the brief's data folder could not be reached) |
| `kcf_radiation/` | the method (vendored byte for byte into product/wfg-roadlayer as the `--heat` option) |
| `scripts/check_c1..c4_*.py` | step 2 checks; outputs in `data/c*.json` |
| `scripts/run_fires.py` | per-cell tables of the four reconstructed fires and the FRP cross-check (`data/fires/`) |
| `scripts/run_panels.py`, `scripts/summarize.py` | step 3 on the Gyeongbuk replay and the 15 finals packets (`data/panels/`) |
| `tests/` | formula constants, view-factor identities, eikonal spread rate, closure = contact rule at d* = 0 |

Reproduce (Python 3.12+, numpy, scipy, rasterio, pyproj, pytest; the environment rasters as in DATA.md):

```sh
python -m pytest -q research/kcf-radiation/tests
```

```sh
cd research/kcf-radiation && python scripts/check_c1_butler_cohen.py && python scripts/check_c2_fds.py && python scripts/check_c3_flames.py && python scripts/check_c4_sensitivity.py
```

```sh
cd research/kcf-radiation && python scripts/run_fires.py --env ENV/regions --firms-2025 ../harness-2026-11/data-fetch/small/firms --firms-2022-23 FIRMS_DIR --out data/fires
```

```sh
cd research/kcf-radiation && python scripts/run_panels.py --env ENV/regions --replay REPLAY_DIR --packets ../../data/routing/latest_inputs_try02/packets --graphs ../../data/routing/graphs --out OUT && python scripts/summarize.py OUT data/panels/summary.json
```

REPLAY_DIR holds the 13 rasters built by `product/wfg-roadlayer/examples/build_example_raster.py --issue
2025-03-25THH:00:00Z` for HH = 03..15.
