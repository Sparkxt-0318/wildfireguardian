# firecast-lab (Track A)

Calibrated probabilistic fire-hazard generator; side project of the program (rules: `CLAUDE.md`). Splits:
`SPLITS.json`. Data caveats: `docs/DATA_NOTES.md`. Metric definitions and the scoring domain: `METRICS.md`.

## Phase 0 baselines on the real data (Mac)

The real data root is not in the repo; every command refuses to run without it and never falls back.

```bash
export FIRECAST_DATA_ROOT=/path/to/data/environment        # events.json + regions/
python program/benchlock.py --label fl-dilation -- firecast-lab run --baseline dilation --split dev
#   -> firecast-lab/results/dilation.csv: one row per dev window, with commit, seed, config and host
python program/benchlock.py --label fl-c651-timing -- firecast-lab time-c651 --fire KFS_02 --members 256
#   time c651 on one fire BEFORE any full c651 run (needs torch 2.5.1); it extrapolates the dev run
```

Baselines (`--baseline`): `persistence`, `dilation` (k tuned by least pooled Brier), `calibrated_dilation`
(per-lead isotonic map of the Chebyshev distance to the front; the bar to beat), `logistic` (distance, wind
alignment, slope), `c651` (frozen checkpoint; in-sample on 25 dev fires). Dev scores are cross-fitted by leaving out
one SPLITS fold of whole fires. Every baseline gives K coherent members (`--members`, default 64, matched across
baselines) and is scored on identical cells, next to persistence and calibrated dilation in the same row. Rows hold
sums: pool by summing, resample whole fires with `metrics.fire_bootstrap`. `--split test` needs `--allow-test`
(milestones only, after Siyeong approves).

## Members, couplings and scenario sets

- `members.coherent_members(cum, K, seed=..., coupling=...)`: member k has burned a cell by lead l iff
  `U_k <= cum[l]`, one uniform field per member for every lead. Marginals are exact up to Monte Carlo error.
  - `shared` (default): one uniform per member, nested members; the least conservative coupling for
    "every member clear".
  - `copula --length-cells L`: Gaussian copula with declared correlation `exp(-r^2 / 2L^2)`.
  - The coupling is a modelling choice to calibrate on dev (backlog L8), not a fact.
- `producer.from_window(window, hours, model=..., seed=..., config=...)` writes hazard_contract v1 sets:
  - `source="model"`, the repo packet heat source, horizon = lead, provenance = commit, seed, config, host.
  - Unknown cells are NaN and unsupported.
  - Cells outside the reconstruction domain stay supported with the model's forecast (`producer` docstring).

## Decision metric (`METRICS.md` §7)

`firecast_lab.decision` runs fixed routing requests through `evacplan.oracle`, the only code that declares
`checked` / `model_no_route` / `unresolved`. Install evacplan into the venv first:
`uv pip install --python .venv/bin/python -e evacplan`.

```bash
export FIRECAST_DATA_ROOT=/path/to/data/environment
export FIRECAST_GRAPHS=$WFG_ROUTING_INPUTS/graphs        # road graphs: see below
python program/benchlock.py --label fl-decision -- firecast-lab decision --model calibrated_dilation --split dev
#   -> firecast-lab/results/decision_calibrated_dilation.csv: one row per request and coupling,
#      with commit, seed, config and host
#   -> .json: the four rates with whole-fire intervals, the K curves and per-window request counts
#   -> .png: false-safe against clearance as K varies
```

- **Requests.** Up to 32 per window (`--requests`), built from cutoff information only.
- **Model verdicts.** The model's K = 64 members (`--members`) are checked under both couplings: `shared`, and
  `copula` with L = 8 cells (`--length-cells`).
- **Truth.** Korean fires use reconstruction truth (hourly isochrones, mode `envelope`). US fires are skipped, with
  the reason printed: their truth needs NIROPS perimeters, which have no loader yet.
- **Refusals.** The command refuses to run without the data root or without the graph folder. Fires without a graph
  are listed as skipped.
- **Cost.** About 4.6 min per window on the 4-vCPU cloud host, so about 80 min per model for the 17 Korean dev
  windows that have graphs (timed on the real Uljin graph with a SYNTHETIC hazard). `--requests` and `--repeats`
  scale it.

### Real road graphs

The Korean router study graphs live in the fetched routing inputs (`$WFG_ROUTING_INPUTS/graphs/<folder>/graph.json`,
not in the repo). On the cloud host that is
`/tmp/claude-0/-home-user-wildfireguardian/a9efaa5c-c674-5d4b-a7c3-c4ab7b53f43d/scratchpad/routing_inputs/graphs`.
`decision.GRAPH_FOLDERS` maps fire ids to folders, and `load_road_graph` reads them through evacplan's router-graph
adapter with the router's own admission (`wfg_latest`, i.e. `integration/src`, must be importable).

| folder | fire | split | nodes / edges (waitable) | admitted, grid = event grid |
|---|---|---|---|---|
| `uljin_2022` | KFS_02 | dev | 9,372 / 18,909 (337) | yes, EPSG:5179 |
| `hongseong_2023` | KFS_05 | dev | 915 / 1,806 (39) | yes, EPSG:5179 |
| `miryang_2022` | KFS_11 | dev | 1,494 / 3,115 (78) | yes, EPSG:5179 |
| `uiseong_andong_2025`, `yeongdeok_2025` | KFS_01 | **test** | not used | do not use without approval |

- All three dev graphs are OSM snapshots from the day before ignition (© OpenStreetMap contributors, ODbL).
- No other fire has a road graph. US fires need OSM graphs built on the Mac (osmnx; OSM is blocked here), saved as
  `<fire id>/graph.json` in either the router format or evacplan's `RoadGraph` JSON.

## Open questions (for Siyeong)

1. Which coupling (and correlation length) should be the default? The decision metric reports both: `shared`, and
   `copula` at L = 8 cells (3 km) as a declared placeholder.
2. Present fire uses each cell's reconstructed arrival age ("exact"); hazard_contract's packet default is the
   router's `R_max` enclosure. Keep "exact"?
3. Decision truth uses `from_perimeters` mode `envelope`: a truth "safe" is certain, while a truth "hit" means
   contact under at least one timing consistent with the perimeters. False-safe is therefore an upper bound with
   respect to timing between surveys. Keep it?
4. Request population (`METRICS.md` §7.1): origins within 3 km of the cutoff front, trips of 2-4 km, half of the
   waitable origins wait up to 1 h, budgets peak 10 kW/m² and dose 100 kJ/m². Are these the right defaults?
