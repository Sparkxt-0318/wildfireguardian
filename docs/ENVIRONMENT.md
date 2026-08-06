# Environment — how to reproduce it, and why it is built this way

Reference environment: **`wfg311`**, Python **3.11.15**, conda-forge.
Verified 2026-08-01: `395 passed, 1 skipped, 0 failed`.

## Build it

```bash
conda create -n wfg311 python=3.11 -y
conda activate wfg311
conda install -c conda-forge \
  "osmnx=2.0.7" geopandas networkx rasterio xarray scikit-learn matplotlib \
  pyyaml pytest scipy pandas numpy shapely pyproj netcdf4 h5netcdf rich -y
pip install -e . --no-deps
```

Optional, only to run the superseded Build-A / LFMC code:

```bash
conda install -c conda-forge "xgboost>=2.0" -y     # the `legacy` extra
```

Check it:

```bash
pytest -q                                          # expect 395 passed, 1 skipped
python -m wildfireguardian.config                  # prints config_hash
python scripts/snapshot_external.py --verify
```

## Why conda-forge and not pip

`geopandas`, `rasterio`, `osmnx` and `pyproj` are thin Python layers over binary
GDAL / GEOS / PROJ. conda-forge ships those binaries as first-class packages and
resolves them together; pip has to find compatible wheels for each independently
and silently fails on some platform/Python combinations. Round 2 hit exactly
that failure mode — see below.

## Why Python 3.11 and not 3.14

The Round-2 working environment was a Python 3.14 venv. On 3.14 the geospatial
stack did not install: `networkx`, `osmnx` and `geopandas` were all declared in
`requirements.txt` and none were present. The consequences were silent:

| | Round-2 venv (py3.14) | `wfg311` (py3.11) |
|---|---|---|
| `tests/test_rescue_routing_real.py` | 5 **skipped** ("osmnx not installed") | 5 **passed** |
| `tests/test_firegrid_crs.py` | 3 **failed** (`No module named 'geopandas'`) | 13 **passed** |
| `tests/test_spread_v2_xgb.py` | passed | passed (needs `legacy` extra) |
| suite | 387 passed / 3 failed / 6 skipped | **395 passed / 1 skipped** |

A skip is not a pass. Five tests that exercise the real OSM network — the ones
that matter most for the routing claims — were never running.

## Pins that are load-bearing

**`osmnx==2.0.7` is a deliberate scientific constraint, not an arbitrary pin.**
It is the version recorded in `created_with` inside
`data/snapshots/osm-*.graphml` — the graphs that PHASE 2 reads. The PHASE-2
comparison is reported in three columns:

| committed (Jul-23 network, flat) | Jul-24 network, flat | Jul-24 network, slope |
|---|---|---|

Columns 2 and 3 must differ by the **slope correction alone**. If osmnx floated,
a library upgrade could change how the snapshot graph is loaded or projected, and
that change would be silently attributed to slope. The pin is what makes column
2 → column 3 a clean single-variable contrast.

Do not float it without re-snapshotting the graphs and re-reporting the baseline.
`make env-check` fails on drift.

Everything else in `requirements.txt` is pinned to the exact `wfg311` versions
rather than to lower bounds, so "declared but not installed" cannot recur
unnoticed.

## Known state of the old `.venv/`

`.venv/` at the repo root is **broken and should not be used**. It was created
when the repo lived at `/Users/jp/Desktop/wildfireguardian`; after the move to
`/Users/jp/Desktop/Korea Code Fair/wildfireguardian` its absolute paths no
longer resolve:

* `.venv/bin/pip` has a dead shebang (`bad interpreter`); only
  `.venv/bin/python -m pip` works;
* the editable-install path file still points at the old `src/`, so
  `import wildfireguardian` fails unless `PYTHONPATH=src` is set.

It is left in place untouched. Use `wfg311`.

## A separate `wfg` conda env also exists

`/Users/jp/miniforge3/envs/wfg` is Python 3.11.15 with a nearly identical stack,
but carries **osmnx 2.1.0** and lacks `pyyaml`/`pytest`. It is not the reference
environment. Use `wfg311`.

## Dependency reality check

Declared in Round 2 but imported nowhere in `src/`, `scripts/` or `tests/`:
`pydantic`, `python-dotenv`, `tqdm`, `jupyter`, `folium`, `requests`. They have
been removed from `requirements.txt` and listed in a comment there, so the file
states only what the project actually uses.

`rich` was declared, genuinely used (lazy imports inside four demo CLIs'
`main()`), and not installed — the demos would have raised `ModuleNotFoundError`
on invocation. It is now installed and pinned.

## Test-guard gap — fixed

`tests/test_spread_v2_xgb.py::test_lofo_holds_out_whole_fire` imported `xgboost`
without a guard, so it **errored** instead of skipping when the optional `legacy`
extra was absent — a missing optional dependency read as a broken build. It now
calls `pytest.importorskip("xgboost")`, matching its sibling
`tests/test_lfmc_retrieval.py`. The canonical stack now tests clean with or
without the legacy extra.

## Keeping this honest

```bash
make env-check      # installed packages vs the pins here — fails on missing/drift
make test           # 395 passed, 1 skipped
```

`make env-check` exists specifically so the Round-2 failure mode — a dependency
declared in `requirements.txt` but absent from the environment — is a non-zero
exit rather than a silent skip.

## ⚠ `make env-check` checks one direction only

Recorded 2026-08-07, when PHASE 22 added FastAPI. **Not fixed, deliberately.**

`scripts/env_check.py` reads `requirements.txt` and asserts every **declared**
package is installed at the pinned version. It does **not** ask the reverse
question — whether everything installed is declared. So:

> **`pip install` something and do not pin it, and `make env-check` stays
> green while the environment silently stops matching its own declaration.**

That is the same shape as the Round-2 failure this target was written to catch,
approached from the other side. Round 2 declared `networkx`/`osmnx`/`geopandas`
without installing them; the reverse is installing without declaring. Both end
with an environment nobody can rebuild, and only the first is caught.

**Why the reverse check is not added.** It would require pinning every
transitive dependency — `starlette`, `pydantic`, `h11`, `anyio`, `httpcore`,
`annotated-types` and the rest arrive with FastAPI. Pinning a transitive states
a compatibility claim this project has never tested, and it makes `env-check`
fail whenever a resolver makes a legitimate different choice. The cure is worse
than the disease.

**What to do instead, every time a dependency is added:**

1. `pip install --dry-run <pkg>` FIRST, and read the output. If it would upgrade
   anything already pinned, stop — that is a change to the environment every
   committed number was produced in.
2. Pin the **direct** dependency in `requirements.txt`, at the exact installed
   version. Transitives stay unpinned, on purpose.
3. Say in the commit message which packages were added and that the dry run
   showed no upgrades.

PHASE 22 did exactly that: `fastapi`, `uvicorn`, `httpx`, dry run reporting 12
new packages and **zero** upgrades.
