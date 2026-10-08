# Hourly forecast to conditional routing

This isolated delivery preserves the original mentor hourly model and connects it to the maintained exact router through an explicit hazard constructor. Strict mode preserves missing physical information. Opt-in research mode declares every additional assumption and produces finite scenario interval enclosures on the matching Uljin grid.

Read `OWNER_HANDOFF.md` for final status and `REPRODUCE.md` for the commands. `ASSUMPTIONS.md`, `SUPPORT_DIAGNOSIS.md`, `VALIDATION_BOUNDARIES.md` and `INDEPENDENT_REVIEW.md` state the scientific and numerical limits. Effective comparison-panel freeze is `EXPERIMENT_FREEZE_V3.json`; its additional current-state variant is marked exploratory after an earlier smoke route. Earlier specifications and partial runs remain preserved.

After installing `requirements.txt` into a Python 3.12 environment, run:

```sh
.venv/bin/python -B candidate/hourly.py native-run --mode research --repeats 2 --output-dir results/my_run
```

This reruns the original saved checkpoint on a numeric copy of original raster-loader inputs, constructs the declared scenarios, prepares the Uljin graph, searches and independently checks a frozen query. No mentor response or manual missing implementation is needed.

Use `--mode strict` to obtain the information-preserving `UNSUPPORTED` report. A successful program exit means a report was produced; each query's status remains authoritative. Primary `TIMEOUT` is unresolved.

Validate the portable file seal with `.venv/bin/python -B tools/verify_delivery.py`. Run the software gates with `.venv/bin/python -B candidate/hourly.py tests`. For the complete frozen development panel, use `.venv/bin/python -B tools/run_frozen_panel.py --output results/my_panel`; the panel runner refuses existing result directories. Ordinary run/replay commands overwrite reports if their output directory is reused, so choose a fresh output directory.

To regenerate the optional figure, install its separate plotting dependency and run:

```sh
.venv/bin/python -m pip install matplotlib==3.9.2
.venv/bin/python -B tools/plot_route_example.py
```

The ZIP excludes `work/`, environments, caches and credentials. Original sources, checkpoints, frozen studies and incident eligibility remain preserved. The one isolated router compatibility patch admits the named research evidence class; it does not change search, exposure, geometry or budget semantics. Its inherited baseline seal is retained and intentionally detects that patch.

Engineering completion does not supply missing observations. These are conditional routes under explicit constructions, not validated real-fire trajectories or physical-safety guarantees.
