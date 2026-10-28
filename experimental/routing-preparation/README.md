# Experimental prepared-graph routing

This **opt-in research package** explores reusing an admitted road graph across routing requests. It is separate from the frozen `integration/` release and uses the `wfg_routing_experimental` namespace. It is not an operational evacuation service.

The cache stores an authenticated graph, not a hazard, mission, or route. Each `solve` validates the hazard and request again. A changed graph produces a different cache identity; the disk cache also binds the package and backend identity. Owner-local cache keys are private and must not be committed or shared.

## Run the source-only tests

From this directory, on a POSIX system with Python 3.10 or newer:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Without a built extension, Python-backend tests run and native-only tests are explicitly skipped. The package uses `fcntl` and `resource`; Windows is not supported or tested. The tests use synthetic fixtures and do not validate real evacuation safety.

## Build and test the optional native backend

A matching CPython installation, its development headers, and a C compiler with `__int128` support are required. The build has been tested on macOS arm64 with CPython 3.12; Linux and other platforms have not been independently validated. Run from this directory:

```sh
python3 tools/build_native.py
PYTHONPATH=src WFG_TEST_REQUIRE_NATIVE=1 python3 -m unittest discover -s tests -v
```

The builder places a machine-specific extension under `src/wfg_routing_experimental/`; it is ignored by Git. Use the same interpreter and this source checkout when running with `PYTHONPATH=src`. A normal non-editable wheel installation **does not build or install the native extension**. If native mode is explicitly requested and unavailable, the package fails closed rather than silently claiming native execution. Rebuilding or relocating the extension changes cache identity.

## Minimal local example

```python
from wfg_routing_experimental import fixture, solve
from wfg_routing_experimental.prepared_reuse import LocalPreparedStore

inputs = fixture.example()  # synthetic fixture, not a real evacuation
store = LocalPreparedStore(backend="python")
prepared, first = store.get(inputs["graph"])
result = solve(prepared, inputs["hazard"], inputs["request"])
prepared_again, second = store.get(inputs["graph"])
assert not first.cache_hit and second.cache_hit
print(result["status"], result.get("arrival"))
```

After building the extension, select the native backend explicitly with `LocalPreparedStore(backend="native")`; use `backend="python"` to select the Python implementation.

`LocalPreparedStore` reuses graphs within a process. `ArtifactPreparedStore` provides optional authenticated on-disk reuse across processes; give it a private, owner-controlled directory with no symlinked parent components. Delete the directory when no longer needed. It is not designed to protect against an attacker who can access the same user's key or to accept untrusted artifacts.

## Evidence and limitations

[Prior matched experiments](../../research/routing/prepared-graph-cache/README.md) measured the earlier sealed candidate. This repository package changes the namespace and has a separately rebuilt binary; those measurements are **not** a benchmark of this exact refactored build. The fixed-panel evidence does not establish general end-to-end speed or memory improvements, real-world safety, or independently proved continuous-road thermal bounds. Use and performance on other platforms, concurrent schedules, graphs, and hazards remain to be assessed.
