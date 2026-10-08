# Reproduce the hourly forecast integration

Use Python 3.12 and the pinned requirements supplied in `requirements.txt`.
The existing compatible local interpreter is
`/Users/jp/Documents/Codex/2026-09-24/fu/outputs/forecast_routing_integration_20261007_v1/work/venv/bin/python`.
The portable delivery contains code, the original safe-loading checkpoint,
numeric original-loader input samples and native forecast samples; it does not
contain that environment or credentials. Every NPZ load uses `allow_pickle=False`;
the original checkpoint loader uses `torch.load(weights_only=True)` with no
unsafe fallback.

From a clean extraction, install dependencies once:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -c constraints.txt
```

Then this one command runs the original model on the portable original input,
constructs the explicit research scenarios, prepares the matching Uljin graph,
runs the frozen simple query twice and independently checks each returned route:

```sh
.venv/bin/python -B candidate/hourly.py native-run --mode research --repeats 2 --output-dir results/my_native_run
```

This reuses the supplied original checkpoint and original inference eligibility;
it does not retrain. The input is a numeric derivative of the original raster
loader, with preserved input hashes and retrospective current-state provenance.
Defaults target the first Uljin cutoff at 2022-03-04 03:00 UTC. The input, original
forecast and constructed arrays remain separately saved. `REPORT.json` records
source/checkpoint hashes, original/constructed support, assumptions, actual
generation times and assigned historical replay issue/availability, graph
revision, full request/results, exposure checks and latency/memory/payload.

Strict mode preserves missing information and routes its false joint support
through the maintained router:

```sh
.venv/bin/python -B candidate/hourly.py native-run --mode strict --output-dir results/my_strict_run
```

`UNSUPPORTED` is the expected information-preserving outcome. The command exits
successfully when it produces a valid report; that exit code does not mean a
route was found or a physical claim was validated. Invalid inputs exit 2.
Always inspect each row's `result.status` and `proof_level`. `TIMEOUT` remains
unresolved even if a separate recorded return can be checked.

Use fresh output directories: ordinary native/run/replay commands replace reports
when their output directory is reused. The frozen panel runner separately refuses
an existing output directory.

To route already supplied original forecast samples, without rerunning inference:

```sh
.venv/bin/python -B candidate/hourly.py run --mode research --repeats 2 --output-dir results/my_precomputed_run
.venv/bin/python -B candidate/hourly.py run --mode strict --output-dir results/my_precomputed_strict
```

Override `--snapshot` and `--metadata` with another paired native NPZ/JSON, and
`--request` with a frozen query from `sample/query_simple.json` or
`sample/query_difficult.json` if those coordinator-generated query files are
used. The original copied `sample/uljin_GRID_CONTROL.json` also supplies the same
simple query. Common member dose budgets are copied exactly to the constructed
identities; supplied peak/dose/search budgets and destination dwell are never
weakened. Full requested horizon must fit native coverage. Unsupported missions
are refused rather than repeating an hourly forecast.

An explicit custom research configuration is a JSON object matching
`ConstructionConfig`; pass `--config path/to/config.json`. The frozen panel and
assumptions are documented in `EXPERIMENT_FREEZE_V3.json` and `ASSUMPTIONS.md`.
The constructor's interval enclosures can increase modeled exposure or refuse
paths feasible under exact event timing. No sampled scenario count establishes
real-fire coverage.

Run all regression and independent review checks:

```sh
.venv/bin/python -B candidate/hourly.py tests
```

This includes the original routing regressions, version 1 bridge regressions,
constructor tests, integration/history tests and the independent checker's own
direct calculations and bounded routing references. Historical baseline logs and
the isolated whitelist patch are preserved under `evidence/`. The original
routing `run.py check` seal intentionally reports a validation-file mismatch
after the new `RESEARCH_CONSTRUCTION` whitelist extension; its frozen seal was
not rewritten. The new delivery's source manifest is the release authority.
No numerical, search, geometry, support or budget semantics changed in the router.

Exercise history transfer, new identities, prospective assumption changes,
stale update/result rejection and explicit graph reset:

```sh
.venv/bin/python -B candidate/replay_with_provenance.py --output-dir results/my_replay
```

The documented wrapper adds complete original/checkpoint hashes, source support,
constructor assumptions/law, grid revision, actual/assigned replay times and
runtime context to the same core replay. Replay first checks a ten-second stationary modeled prefix independently. It
records progress only if that prefix is supported and admissible. Each new future
is recombined with every accepted old supplied history using an upper encoded
maximum incurred dose. This is a finite conditional history contract, not a claim
that resampled future flame paths share a physical past. Changed assumptions are
prospective. The later 06:00 forecast starts three hours after the first cutoff;
its gap is explicitly refused because the old hour does not cover elapsed
progress. No missing dose becomes zero. The generated lifecycle control tests
exercise successful updates separately from real historical inputs.

For a full original raster-loader re-export, use `candidate/native_forecast.py`
with `--mentor-root`, `--data-root`, `--checkpoint`, `--out` and optional repeated
`--cutoff` arguments. The original source tree and data remain in the prior
packet's `work/mentor/`; this workflow is local and does not acquire new data or
change source eligibility. The portable numeric path above is sufficient for a
complete original-model-to-router reproduction.

Latency fields distinguish runtime imports, loading, original model loading and
inference, expected-heat export, construction, native adaptation, graph preparation,
search with the router's internal checker, an additional independent route check,
in-process cold total and warm queries using the same prepared payload. The
coordinator's panel also records external subprocess wall time. Process peak RSS
is a lifetime high-water mark, not incremental memory. Forecast horizon, historical
observation freshness, model generation time, update cadence and computation time
are distinct.

Engineering completion and finite model-conditional routing are the supported
claims. This Uljin development exercise has no independent real-fire thermal,
flame-contact, road-passability, operational or physical-safety validation.
