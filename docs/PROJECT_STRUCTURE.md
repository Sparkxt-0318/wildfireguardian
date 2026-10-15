# Project structure and version authority

Current scientific entry point: `integration/` with `wfg_latest` 1.0.0, reviewed kit v3 and checkpoint c651 in `forecast/`. Exact identities are in `RELEASE_IDENTITY.json`.

- `forecast/`: final maintained forecast source, tests, selected checkpoint and parameter/source documentation.
- `integration/`: evaluated API, routing/search/checking workers and lifecycle controller, plus repository-oriented examples.
- `hardware/`: logger firmware, conversion/export tools and local LIVE/replay map.
- `demos/showcase/`: offline illustrative 3D presentation, independent of the evaluated numerical pipeline.
- `research/`: accepted routing results/figures and separate forecast-ablation findings.
- `tools/`: hash verification and immutable evaluated-input download.
- `monte-carlo-extension/`: separately versioned optional extension, preserved at its existing path.

The earlier `routing-api/`, `routing-package/` and `routing-review/` directories remain at their original paths for existing links and historical users. They are superseded as the integrated submission entry point by `integration/`. Their original source and evidence are unchanged; historical results do not acquire the latest checkpoint or improved outcomes retroactively.

No claim is made that the illustrative website, logger and research router form one field-validated live product. They have separate launchers and input contracts. Forecast execution requires external environmental inputs; routing replay can use the published frozen hazard packets without those rasters.
