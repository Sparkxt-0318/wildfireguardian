# Routing development handoff — 6 October 2026

Start with [README.md](README.md). The active routing package is `routing/`.
Original deliveries and experiment evidence are preserved.

```sh
python3 -B run.py check
python3 -B -m routing solve --input fixtures/example.json
python3 -B -m routing replay --prepare-graph --input fixtures/continuity_replay.json
```

The code is organized into library, CLI/checking, tests, fixtures, docs and archived
research evidence. Original library syntax trees are unchanged. No runtime
dependency was added. Existing public imports and JSON payload/result semantics
are retained. This is an isolated development release, not a GitHub merge.

Validation: 91 tests, 102 matched routing outcomes on 17 finite fixtures, 48 checked
route witnesses, deterministic raw/prepared replay, retained road witness and
source preservation. Read [the refactor report](docs/REFACTOR_REPORT.md) and
`verification/VERIFICATION_REPORT.json` for scope and reproduction evidence.

Actual forecast integration, physical safety, general performance superiority,
full-road global certification and concurrency remain outside these checks.
Session ownership remains serialized and primary TIMEOUT remains unresolved.
