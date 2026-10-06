# Reproduce the delivered package

Reference environment: `/Users/jp/miniforge3/envs/wfg311/bin/python` (Python 3.11.15; NumPy2.4.6 for legacy comparator). Integration uses standard library only. The existing wfg environment was also checked and not modified. Exact versions are in evidence/ENVIRONMENT.json.

```sh
cd /Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_delivery_overnight_20261004_v1
PYTHONDONTWRITEBYTECODE=1 /Users/jp/miniforge3/envs/wfg311/bin/python -B run.py check
```

One command starts a fresh test process, checks frozen candidate hashes, runs all packaged tests, replays updates twice for byte-equivalent deterministic content and independently checks the packaged full-road witness when present. This verifies the delivered copies, not scratch code. It does not run a forecast model or contact a service. `run.py solve` and `run.py replay` commands are in INTERFACE.md. After extraction, `python3 -B run.py check` works on a compatible macOS/Linux Python 3.11+ standard-library installation; no original workspace imports are used by integration.

Official timed reproduction on the shared machine MUST use its measurement lane:

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 /Users/jp/miniforge3/envs/wfg311/bin/python /Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_specialized_research_20261003_v1/coordination/run_locked.py --mode exclusive --owner routing_delivery_replay --label 'frozen routing delivery replay' -- /Users/jp/miniforge3/envs/wfg311/bin/python benchmark.py --run --out /tmp/wfg-routing-replay
```

The run has 510 rows: 17 cases × 5 arms × 2 modes × 3 rotated repetitions. Every child starts fresh. Warm means one uncharged process-local invocation before the measured one; core caches are invocation-local, so warm is primarily imports/allocator warmth, not forecast cache reuse. Charged method time includes imports/preparation/search/required route checking; process time separately includes interpreter launch, input reading and extra postcheck. Memory is measured child process high-water RSS. Reference enumeration is separate and its caps remain unresolved. Raw rows/pairs/summary preserve all unavailable/errors/regressions. Do not overwrite saved evidence or tune on these final rows.

The six exposed road comparisons use `road_comparison.py` through the same exclusive wrapper. Their external historical source/input dependencies are pinned in `evidence/ROAD_COMPARISON_FREEZE.json`; this optional regression is workspace-dependent, while the delivered core, fixtures, replay and check command are portable. Never overwrite the saved comparison directory when reproducing it: copy the package to a fresh destination first. Its 24 cold runs preserve 60 s / 3,072 MiB / 95 s watchdog, without an event proxy cap. The full established eager/activation planner is compared there, separately from the restricted vector-component tiny arm. End-to-end timing includes the separately implemented lane-F feasibility check; no independent full-road optimum/refusal certificate is available.

On this shared machine, also wrap `run.py check` in `run_locked.py --mode exclusive` when it checks the packaged road witness. On another machine, the direct one-command check above needs no local study lock.

`run_measurements.py` additionally executes the full historical graph smoke through the same lane. `build_road_fixture.py` is optional source export and depends on the pinned graph_nangok_r1 paths; it is road-scale work and MUST use the shared wrapper. The already exported full-graph fixture is portable and contains no protected labels. It never downloads data. The vendored repaired vector source remains byte-identical; legacy_bridge replaces two import bindings in memory with local measurement/result shims and documents its restricted matched subset.

Manifests: MANIFEST.json records delivery hashes, prior source/input hashes and preservation outcomes. The archive manifest excludes itself to avoid circular hashing; the separate ZIP SHA256 authenticates the archive. Canonical upkeep uses file-inode flock, append/prefix preservation, fsync, and before/after hashes; coordinator alone writes it. No original frozen source/protocol/result or scientific eligibility is modified.
