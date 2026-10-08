# WildfireGuardian routing — organized development package

This is the refactored **routing integration library** from the 5 October
prepared-session delivery. It includes routing, independent route checking,
session continuity, opt-in immutable graph preparation, and recorded-return
checking. Original delivery folders and experiments are untouched.

## Start here

Use Python **3.11 or newer** on macOS or Linux. The active routing library and
checks use the standard library; no `pip install` is required. Windows support
has not been checked (`resource` is used for process measurements).

From this folder:

```sh
python3 -B run.py check
python3 -B run.py solve --input fixtures/example.json
python3 -B run.py replay --prepare-graph --input fixtures/continuity_replay.json
```

The equivalent module entry point is `python3 -B -m routing check`, `solve`, or
`replay`. Existing `routing.*` import paths and JSON request/result schemas are
preserved. Default routing is still raw; graph preparation remains opt-in.

## Layout

| Location | Purpose |
|---|---|
| `routing/` | Active Python library: search, admission, checking and lifecycle |
| `run.py` | Compatibility launcher; delegates to `routing.cli` |
| `tests/` | Existing regressions plus CLI/release-boundary tests |
| `fixtures/` | Small example, finite evaluation cases, replay and full road fixture |
| `docs/` | Interface, mathematical specification, lifecycle and architecture |
| `tools/` | Refactor verification; no experiment starts on import |
| `verification/` | This release's hashes, comparisons and checked road witness |
| `vendor/` | Hash-pinned optional historical vector comparator; not default routing |
| `archive/` | Unedited historical scripts, results, manifests and independent reviews |

Read [the architecture guide](docs/ARCHITECTURE.md),
[input/API contract](docs/INTERFACE.md),
[routing specification](docs/ROUTING_SPEC.md), and
[preparation lifecycle](docs/PREPARATION_LIFECYCLE.md).
[The refactor report](docs/REFACTOR_REPORT.md) explains exactly what changed.

## Library example

```python
import json
from pathlib import Path
from routing.session import RoutingSession

fixture = json.loads(Path("fixtures/example.json").read_text())
session = RoutingSession(fixture["graph"], prepare=True)
admission = session.accept_update(fixture["hazard"], fixture["request"]["as_of"])
if admission["status"] == "ACCEPTED_UPDATE":
    result = session.plan(fixture["request"])
    committed = session.commit(result)
    print(result["status"], committed)
```

One serialized owner must control each session. Prepared graphs are owned
snapshots unless checked mutable authority is explicitly selected. Graph
replacement requires an explicit reset. A primary `TIMEOUT` remains unresolved
even when a separately checked return is available.

## Scientific scope

This is code organization and maintainability work, **not a new algorithm or
speed study**. Current checks use generated hazards, including a fixture on
Nangok roads. Actual mentor forecast integration, physical firefighter safety,
and deployment validation are not established by this package. Historical
research planners and unpromoted novelty experiments remain in their original
deliveries; this folder is not a merger of every research branch.

The optional `routing.legacy_bridge` uses NumPy. It is a restricted historical
comparison, never a required application dependency. Black 24.10.0 was used only
in an isolated temporary formatting environment; it is not a runtime dependency.

## Development and verification

```sh
python3 -B -m unittest discover -s tests
python3 -B tools/verify_refactor.py
```

`check` verifies release hashes before running code checks. Intentional edits
will therefore invalidate the release seal; during development run the tests
directly. Do not regenerate historical study freezes. See
[reproduction instructions](REPRODUCE.md) and [archive notes](archive/README.md).
