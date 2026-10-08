# Reproduce the organized routing release

Python 3.11+, standard library, macOS/Linux. No environment-specific absolute
paths are needed by the active library, CLI, bundled fixtures or tests.

From the extracted package root:

```sh
python3 -B run.py check
python3 -B -m routing solve --input fixtures/example.json
python3 -B -m routing replay --input fixtures/continuity_replay.json
python3 -B -m routing replay --prepare-graph --input fixtures/continuity_replay.json
python3 -B tools/verify_refactor.py
```

These commands do not rewrite archived evidence. The first command validates the
new release seal, runs regressions, compares repeated raw/prepared deterministic
replay, and rechecks the retained road-route witness. It does not reprove global
optimality on all roads or execute the historical timing studies.

`verification/VERIFICATION_REPORT.json` contains this refactor's measured check
results. `verification/SOURCE_PROVENANCE.json` maps the original candidate paths
to their new locations. `FILE_MANIFEST.json` covers the complete release except
itself. `tools/verify_refactor.py` verifies those hashes, preservation of archived
bytes and unchanged syntax trees in the original routing modules. If the original
source folder is absent, the original-source comparison is explicitly not run;
release integrity remains checkable on another machine.

Timing fields and process RSS are excluded only from routing-result comparisons;
all statuses, reasons, routes, checker results, exposure values and search counters
are retained. No new performance superiority is claimed.

After editing active code, use `python3 -B -m unittest discover -s tests` during
development rather than silently changing the release seal or any study freeze.
