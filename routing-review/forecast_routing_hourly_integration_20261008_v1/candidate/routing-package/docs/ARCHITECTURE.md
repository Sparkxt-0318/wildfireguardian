# Routing code map

The routing engine accepts an explicitly aligned directed road graph, declared
time-dependent hazard scenarios and a mission request. It finds the earliest
admissible arrival under those supplied conditions. It does not forecast fire.

```text
run.py / python -m routing
           |
       cli.py -------- checks.py (explicit release/test checks)
           |
       service.py ---- fallback.py (separately checked recorded return)
           |
        core.py ----- validation.py (graph/hazard/request admission)
           |           prepared.py (optional immutable graph admission)
           |
      independent.py (separate route checker / bounded exhaustive reference)

replay.py ---- session.py ---- service/core/fallback
```

| Module | Responsibility |
|---|---|
| `cli.py` | Argument parsing, fixture input, JSON output and command dispatch |
| `checks.py` | Release integrity, regressions, replay equality and retained witness |
| `core.py` | Exact represented-input geometry/exposure and bounded vector-label search |
| `validation.py` | Explicit units, geography, support, timing and request schema admission |
| `independent.py` | Separate witness arithmetic and finite exhaustive comparison |
| `prepared.py` | Optional owned immutable graph snapshot and content/revision checks |
| `service.py` | Primary search plus separately budgeted recorded-return alternative |
| `fallback.py` | Reverse actual recorded path and recheck current conditions |
| `session.py` | Position/time/turn/exposure/history continuity and stale-result rejection |
| `replay.py` | Deterministic serialized lifecycle demonstration |
| `fixture.py` | Explicit small generated demonstration data |
| `optimization.py` | Separate optional static suffix-pruning experiment; not promoted |
| `legacy_bridge.py` | Optional NumPy comparison with a hash-pinned historical engine |

The original twelve library modules were formatted for readable blocks and
expressions. Their abstract syntax trees are unchanged. We deliberately kept
the validated search/checker logic and public imports intact instead of combining
independent arithmetic implementations or changing mathematical policies as part
of organization work. The substantive structural refactor extracts command-line
orchestration and verification from the old compact root script.

## What belongs in a future change

New algorithms, altered objectives, geometry policy repairs, forecast quantity
conversion, synchronized concurrency and new hazard-dependent caches require
their own specifications and evaluations. They are not implied by this refactor.
In particular, the recorded-return boundary checker/specification discrepancy
reported by the separate return study is not repaired here.
