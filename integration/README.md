# Forecast to checked route integration

The finalized research API is `wfg_latest` 1.0.0. `src/` and `kit/` are byte-identical copies of the independently reviewed package and executed kit v3. New examples adapt paths to this repository; they do not change the engine, hazards, thresholds, timeouts or scoring.

## Install and replay

From the repository root, with Python 3.12 on native macOS:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints-routing.txt './integration[packets]'
python tools/verify_release.py
python tools/fetch_routing_inputs.py
python integration/examples/run_frozen_case.py --out artifacts/uljin-replay
```

The replay uses real study roads and already constructed latest-input hazards, not fresh forecast inference. Its accepted recorded Uljin result has arrival 3,119 s and 512 road legs, followed by 120 s stay. A new replay is unscored; hardware and load can change deadline completion. A raw witness is never published as a qualifying route without the authority and required checks.

The complete request allowance is 30 s with a 3,072 MiB sampled-family guard. The offline independent checker runs after the timed request and has its own 120 s cap; therefore this whole script can take longer than 30 s. `MAX_LABELS`, outer deadline and memory stops are distinct unresolved reasons.

## Fresh forecast inference

Install the full root `requirements.txt`. Obtain the aligned environmental inputs described in `../forecast/GITHUB_SNAPSHOT.md` and use their actual local path:

```sh
python integration/examples/run_full_pipeline.py \
  --data-root /absolute/path/to/environment \
  --out artifacts/uljin-full-chain
```

The source, default checkpoint, pinned input identities and code are published. The environmental rasters and upstream training/survey datasets remain external; metadata catalogs alone are insufficient. Original access and redistribution terms apply.

## Import from Python

```python
from wfg_latest import api
# All paths are explicit; use a fresh output directory.
result = api.route_and_check(
    kit_root="integration/kit",
    packet_dir="data/routing/latest_inputs_try02/packets/uljin_2022/20220304T030000Z",
    graph="data/routing/graphs/uljin_2022/graph.json",
    request="data/routing/latest_inputs_try02/requests/uljin_2022/20220304T030000Z_FX1.json",
    out_dir="artifacts/python-route",
    arm="RDA_CAND",
)
print(result["authoritative_status"], result["arrival_s"], result["independent"])
```

The other API entry points are `export_forecast`, `build_packet` and `rekey_request`; the full-chain example demonstrates their order. Heavy components use isolated child interpreters. Route search is CPU work and does not use CUDA.

`kit/README_KIT.md` and kit manifests are preserved historical execution documents. Its full-campaign runner expects its original workspace layout and coordination context. For this repository use the two path-adapted example launchers above; do not treat the old campaign command as a standalone quickstart.

## Evidence

See `../research/routing/` for all 80 independent result rows, accepted findings and six reviewed figures. Download complete original raw records and reproduction evidence from the final GitHub release. A qualifying refusal is scoped to its model. Independently checked centre/contact results and runtime continuous-road certificates have different scopes; independent radiation/global-bound proofs remain open.
