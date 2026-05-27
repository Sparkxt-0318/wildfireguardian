# Notebooks

Exploratory analysis and figure generation. Notebooks here are **not** the
implementation — code that other modules depend on lives in
`src/wildfireguardian/`. Notebooks are for narrative, plots, and one-off
data exploration.

## Naming convention

`NN_short-topic.ipynb` where `NN` is a two-digit ordinal that imposes a
suggested reading order on a new contributor.

| Range  | Purpose                                                    |
|--------|------------------------------------------------------------|
| 00–09  | Environment smoke tests, dependency probes                 |
| 10–19  | Data ingestion experiments (FIRMS, Sentinel-2, KMA, OSM)   |
| 20–29  | LFMC retrieval experiments                                 |
| 30–39  | Rothermel + cellular-automaton experiments and figures     |
| 40–49  | Smoke dispersion experiments                               |
| 50–59  | Routing experiments                                        |
| 60–69  | Retrospective Yeongdeok 2025 validation                    |
| 90–99  | Figures for the submission writeup                         |

Notebooks should be **stripped of outputs** before commit (use
`jupyter nbconvert --clear-output --inplace`). Heavy artefacts that the
notebook produced go under `docs/figures/` (small PNG/SVG) or are
gitignored (large rasters).
