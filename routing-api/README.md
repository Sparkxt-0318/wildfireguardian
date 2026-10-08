# WildfireGuardian routing — importable Python API

`import wildfireguardian_routing` provides the maintained exact routing engine, explicit graph preparation and an independent route checker. `ReleaseRuntime` connects Python applications to the full forecast-integration and optional hybrid-checker deliveries.

**Version 0.1.0.** Research software. Routing outcomes concern the supplied discrete model and assumptions. Packaging does not resolve the 27 difficult search timeouts, validate constructed thermal hazards, or establish physical safety. The experimental search-followup is not promoted.

## 1. Install the lightweight API

Use Python 3.12 on macOS (tested). Linux is intended but not tested in this packaging run; Windows is unsupported because the preserved engine imports POSIX `resource`.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install https://github.com/Sparkxt-0318/wildfireguardian/releases/download/routing-mentor-review-20261008/wildfireguardian_routing-0.1.0-py3-none-any.whl
```

Alternatively, after downloading/cloning the repository, run `python -m pip install ./routing-api` from its root. This package is not published on PyPI. The basic router has **no third-party runtime dependencies**.

## 2. Calculate and independently check a complete route

Save this as `demo.py`, then run `python demo.py`:

```python
from wildfireguardian_routing import example, solve, check_route

case = example()  # Generated tiny road/hazard fixture, not observed fire data.
result = solve(case["graph"], case["hazard"], case["request"])
print(result["status"], result.get("arrival"))

if result.get("legs") is not None and result.get("destination") is not None:
    check = check_route(case["graph"], case["hazard"], case["request"],
                        result["legs"], result["destination"])
    print("Route admissible under supplied model:", check["ok"])
```

The supplied fixture returns `CONDITIONAL_OPTIMUM`, arrival `4.0`, and checker `True`. It illustrates API use, not a fire-escape validation experiment. `solve` calculates the complete route; it does not require people to wait for individual road segments to be planned.

## 3. Reuse graph preparation for repeated requests

```python
from wildfireguardian_routing import example, prepare_graph, solve

case = example()
prepared = prepare_graph(case["graph"])
first = solve(prepared, case["hazard"], case["request"])
second = solve(prepared, case["hazard"], case["request"])
```

Prepare again explicitly after graph changes. For a mutable authoritative graph, use `solve(raw_graph, hazard, request, prepared=prepared)` to require content equality. Forecast/request admission and route checks still execute. Prepared geometry saves repeated graph work; it does not fix hard-search timeouts. Concurrent use is not validated.

## 4. Supply your own routing inputs

```python
import json
from wildfireguardian_routing import solve

with open("graph.json") as f:
    graph = json.load(f)
with open("hazard.json") as f:
    hazard = json.load(f)
with open("request.json") as f:
    request = json.load(f)
result = solve(graph, hazard, request)
```

A wrapper document may contain `{"graph": ...}` or `{"request": ...}`; unwrap it before calling `solve`.

- **Graph:** revision, coordinate system, grid origin/resolution/dimensions, nodes, directed edges/travel ticks and legal turns/reversals.
- **Hazard:** matching graph/grid, time origin and issue/availability, version, time step and member IDs. Each member supplies interval breakpoints and flattened cell arrays of flame contact (Boolean), support (Boolean) and flux in **kW/m²**.
- **Request:** position, incoming edge, departure/horizon, destination opening intervals and any dwell, incurred exposure per member, hazard version/as-of time, peak/dose budgets and search caps. Dose is **kJ/m²**; time is seconds in the declared clock.

Use `example()` as an inspectable schema example. Do not replace unknown support with zero hazard, omit incurred exposure, change units, or silently weaken a budget. The native forecast adapter accepts **W/m²** and converts it; the routing hazard schema here expects **kW/m²**.

## 5. Download the full forecast-integration package

The small API wheel does not include the large checkpoint, Korean inputs, fixture graph or research raw results. Download `forecast_routing_hourly_integration_20261008_v1.zip` and `SHA256SUMS.txt` from:

https://github.com/Sparkxt-0318/wildfireguardian/releases/tag/routing-mentor-review-20261008

Example using GitHub CLI:

```sh
mkdir -p deliveries
cd deliveries
gh release download routing-mentor-review-20261008 --repo Sparkxt-0318/wildfireguardian --pattern forecast_routing_hourly_integration_20261008_v1.zip --pattern SHA256SUMS.txt
# Verify this one archive against its line in the checksum file.
grep '  forecast_routing_hourly_integration_20261008_v1.zip$' SHA256SUMS.txt | shasum -a 256 -c -
unzip forecast_routing_hourly_integration_20261008_v1.zip
cd ..
python -m pip install -r deliveries/forecast_routing_hourly_integration_20261008_v1/requirements.txt -c deliveries/forecast_routing_hourly_integration_20261008_v1/constraints.txt
```

Use the **full extraction**, not the GitHub `routing-review/` source subset. The requirements include NumPy, PyTorch, SciPy, rasterio, pandas, pyproj, affine and pytest. Installing the wheel alone does not install forecasting dependencies. You can also request them with `python -m pip install './routing-api[integration]'` in a local checkout, but the matching release's requirements/constraints are authoritative.

## 6. Run forecast → hazard construction → routing from Python

```python
from wildfireguardian_routing import ReleaseRuntime

runtime = ReleaseRuntime("deliveries/forecast_routing_hourly_integration_20261008_v1")
report = runtime.run_hourly("my_strict_run", mode="strict", save_hazard=True)
for row in report["rows"]:
    print(row["result"]["status"], row["proof_level"])
```

Strict mode preserves missing hazard support; a valid `UNSUPPORTED` result is expected for these original incomplete inputs. A successful Python call is not evidence that a route exists.

To explicitly use the existing research assumptions:

```python
report = runtime.run_hourly("my_research_run", mode="research",
                            repeats=2, save_hazard=True)
print(report["rows"][0]["result"]["status"])
print(report["api_process_wall_s"])
```

This uses saved native forecast outputs. To rerun the original forecasting model before routing:

```python
report = runtime.run_hourly("my_native_run", mode="research", native=True,
                            save_hazard=True)
```

Every output directory must be new. The original `REPORT.json`, constructed arrays and optional `HAZARD.json` are saved there. Read the full release's `ASSUMPTIONS.md` and `REPRODUCE.md`. Changing `mode` does not turn assumed flames or received heat into independently validated observations.

Optional arguments: `graph`, `snapshot`, `metadata`, `request`, `config` are file paths; `input_snapshot`/`checkpoint` apply to `native=True`. `origin` sets an explicit time origin. The interpreter defaults to the current Python; use `ReleaseRuntime(path, python_executable="/absolute/path/to/compatible/python")` if needed.

## 7. Optionally check a supplied route with continuous-road bounds

Download and verify the separate `routing_hybrid_road_checker_20261008_v1.zip` from the same release, extract it and install its requirements in a compatible environment. This checker is optional and does not replace search.

```python
import json
from pathlib import Path
from wildfireguardian_routing import ReleaseRuntime

# A constructed output folder from step 6, or a supplied constructed fixture.
case = Path("my_research_run")
with open(case / "HAZARD.json") as f:
    hazard = json.load(f)
with open(case / "REPORT.json") as f:
    report = json.load(f)
with open("deliveries/forecast_routing_hourly_integration_20261008_v1/sample/uljin_graph.json") as f:
    graph = json.load(f)
row = report["rows"][0]
route = row["result"]
if route.get("legs") is not None and route.get("destination") is not None:
    checker = ReleaseRuntime("deliveries/routing_hybrid_road_checker_20261008_v1")
    checked = checker.check_fixed_route(case, graph, row["request"],
                                       route["legs"], route["destination"], wall_s=30)
    print(checked["status"], checked.get("reason"))
```

Do not expect every supplied route to receive a certificate. `CERTIFIED_ADMISSIBLE` means a fixed mission passed contact and radiation bounds under the declared source construction; it does not establish global optimality or physical safety. `DEFINITE_REJECT` concerns that supplied route, not all possible routes. `UNRESOLVED` remains unknown. Partial-edge start/trailing destination-wait limitations of the original checker remain.

Exact rational values in checker output are serialized as strings such as `"3/8"`; use `fractions.Fraction(value)` to read them without rounding.

This wrapper uses a separate process to isolate the backend's legacy imports. Each checker call starts a new cold cache epoch. It does not claim the warm-cache performance of a persistent checker. Constructor work shares the requested checker deadline; process startup is recorded separately in `api_process_wall_s`.

## 8. Interpret results and errors

- `CONDITIONAL_OPTIMUM`: optimum within the represented discrete model and supplied assumptions.
- `CHECKED_ROUTE`: admissible witness, without the same global optimality claim.
- `PROVEN_INFEASIBLE` / `DISCONNECTED`: model-qualified refusal according to the backend's documented contract.
- `AT_ISSUE_FAILURE`: departure/admission conditions fail.
- `TIMEOUT` / `UNSUPPORTED`: unresolved, never proof of infeasibility.

The API preserves original status strings. Invalid input may raise validation or backend errors rather than return a routing result. `BackendError` exposes `returncode`, `stdout`, `stderr`. Optional `process_timeout_s` limits the whole backend subprocess and raises `BackendTimeout`, which is unresolved; it does not alter the original search budgets. No outer timeout is imposed by default. Keep output folders from failed attempts for diagnosis.

## 9. Reproduce API tests and inspect source

In a local checkout after installation:

```sh
python -m unittest discover -s routing-api/tests -v
python routing-api/examples/quickstart.py
```

The six `_engine` files are byte-identical copies of the current hourly release core, checker, validation, preparation and fixture modules; only their enclosing Python namespace differs. `ENGINE_PROVENANCE.json` records hashes. The independent 17-case finite reference panel is included. Packaging changes are separate from frozen source releases and do not promote rejected experimental solvers.
