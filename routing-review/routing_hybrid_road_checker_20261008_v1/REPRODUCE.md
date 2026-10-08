# Reproduce the isolated hybrid checker

Extract the ZIP into a new directory. The archive contains all frozen source histories, original saved forecast packets, represented road graph, three preserved checker implementations, exact source/selection/specification freezes, raw comparisons and independent references. Provenance records retain original absolute paths; portable numerical verification accesses the extracted directory through relative paths. The original host releases and canonical context are needed only for host preservation/maintenance checks, not the mathematical/reference tests.

The measured runtime is Python3.12.1, NumPy1.26.4, macOSarm64. Set up Python3.12 with the pinned requirements, then verify the manifest before executing tests:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -B tools/verify_delivery.py
```

The ZIP checksum is in its adjacent `.zip.sha256` file. The finite independent verification commands are:

```sh
.venv/bin/python -B tests/independent_hybrid_reference.py
.venv/bin/python -B tests/independent_hybrid_bounds.py
.venv/bin/python -B tests/independent_hybrid_wrapper.py
.venv/bin/python -B tests/independent_hybrid_shadow.py
.venv/bin/python -B tests/independent_hybrid_driver.py
.venv/bin/python -B tests/independent_hybrid_confirmation_schema_addendum.py --opened-by-coordinator
.venv/bin/python -B tests/hybrid_radiation_unit.py
.venv/bin/python -B tests/hybrid_wrapper_checks.py
```

The confirmation flag here repeats review of the already opened, shipped panel; it does not authorize opening another panel or changing its sources. Quadrature remains a supplemental consistency diagnostic without certificate authority. Review outputs may be rewritten in the disposable extraction. The565-file scientific seal must remain unchanged. The manifest binds the delivered snapshot before test outputs are regenerated; original ZIP bytes are preserved.

For the measured fresh-extraction workflow on macOS, use `tools/portable_verify.py --archive /absolute/path/to/routing_hybrid_road_checker_20261008_v1.zip`. It checks archive SHA/CRC/manifest, repeats an explicit command schedule in another fresh extraction, measures command CPU/wall/RSS and verifies scientific immutability. The original frozen schedule `tools/PORTABLE_COMMANDS.json` is preserved. Its original confirmation verifier is expected to fail on the unsupported baseline record's null bounds after passing 15 cases; the failure and full work are retained. Use `--commands /absolute/path/to/evidence/PORTABLE_COMPLETION_COMMANDS.json` for the disclosed nine-command completion schedule. It changes only that review command to the additive null-schema validator and repeats all other commands. Neither schedule changes candidate code, physics, references for finite bounds, inputs or outcomes. The completion runner is an additive post-opening review-parser repair, not a fresh confirmation or scientific correction. `evidence/PORTABLE_SCHEDULE_BINDING.json` binds host, extracted and manifest schedule hashes and the addendum. A custom schedule proves only its explicitly listed checks. The release separately preserves the failed original-schedule attempt and the successful completion-schedule attempt. The timing helper uses macOS `/usr/bin/time -lp`; other platforms may run the Python tests directly, but their timing/runtime behavior was not validated in this release.

`tools/confirmation_panel.py --run --out results/repeated_known_panel` optionally repeats all54 isolated engine workers, cold/warm30seconds each. This uses the same now-known frozen panel and can take many minutes; it is not fresh confirmation or a new general-gain experiment. Verification of every frozen code/input hash and both independent GO gates is mandatory. Existing output directories are refused. Source construction is not silently redrawn. The separately frozen seed/config and original packets are sufficient for auditing construction; regenerated inputs require a separate output and seal.

`HybridChecker.check` is the full supported fixed-mission API. `HybridRadiationBounds.trajectory_bound` is radiation-only and cannot authorize a road mission alone. Optional shadow remains explicitly enabled and preserves primary reports. No shipped default routing module imports or replaces the hybrid checker.

Host-only `tools/verify_preservation.py` checks original releases. Host-only `tools/append_canonical.py` appends the final evidence under the canonical file's existing inode lock; do not run it from a portable review or append an experiment twice.
