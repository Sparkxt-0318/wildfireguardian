# The suite on a clean clone — what green means when the data is not there

**Status:** measured 2026-09-03 on the autonomous loop's Linux sandbox
(`auto/dev`, head `017c9ec`), by `scripts/auto/gates.py --mode full`.
Backlog row WFG-001.

## Why this document exists

Sessions 18–22 were green on one laptop. That laptop holds `data/raw/**`, which
is git-ignored: the FIRMS detections, the ERA5 pull, the DEM rasters, the two
acquisition manifests and the acquired OSM graphs never reach a clone. So
"the suite passes" was, until now, a statement about one machine's disk.

A stranger cloning this repository gets the tracked artifacts and nothing else.
This file records what happens then — because the reproducibility claim in the
README is a claim about *their* run, not about the author's.

## Method

```
bash scripts/auto/bootstrap.sh                        # pip-only, pinned
.auto/venv/bin/python scripts/auto/gates.py --mode full
```

`gates.py` runs each gate as a direct subprocess and reads its exit status; it
never pipes one (`scripts/check_gate_invocations.py` enforces this; CHARTER §3.10). No network, no keys, no `.env`.

## Result

| gate | outcome |
|---|---|
| `make verify` | PASS |
| `make baseline-verify` | WARN (soft here — see caveats) |
| `make snapshot-verify` | PASS — all present snapshots intact, 47 local-only/digest-only absent |
| `make env-check` | PASS — the environment matches `requirements.txt` |
| `pytest` | **1065 passed, 52 skipped, 0 failed, 0 errors** (116 s) |

1,116 tests are collected. The 1,117th reported outcome is a module-level
`importorskip` in `tests/test_empirical_interaction.py`, which stands in for the
5 tests inside it.

### The 52 skips, by cause

| cause | tests | it means |
|---|---:|---|
| git-ignored data bundle (FIRMS / ERA5 / DEM / detections CSV) | 35 | the input is on the author's laptop only |
| OSM cache never acquired in this clone | 7 | `data/cache/**` is git-ignored |
| optional `legacy` extra (`xgboost`) not installed | 7 | deliberate: not a core dependency, see `requirements.txt` |
| deliberate skips unrelated to this environment | 3 | e.g. a gate whose gap has since been closed |

Every one of the 52 carries its reason in the skip message; `pytest -rs` prints
them.

### Reconciling with the laptop

The laptop baseline reported for the same head is 1,116 passed / 3 skipped /
1 xpassed = **1,120 outcomes**. This run reports **1,117**, one of which is a
test this lap added. So 1,116 outcomes before the addition, and the gap to 1,120
is exactly the 5 tests of `test_empirical_interaction.py` arriving as 1
collection-level skip: 1,116 − 1 + 5 = 1,120. Nothing is unaccounted for.

## What had to change to get here

Five tests and seven errors were red on the first clean-clone run. None was a
defect in the project's science; all five were tests that could not tell "the
input is absent" from "the result is wrong".

| what was red | what it was | what changed |
|---|---|---|
| `test_photo_exif.py` (7 errors) | its `client` fixture builds a runner that preloads the DEM raster | the fixture skips when the raster is absent; the 23 EXIF, refusal-wording and privacy tests above it still run everywhere |
| `test_osm_cache_isolation.py` (2) | guarded on the cache *directory*, which exists in every clone because one file in it is force-added (`vegetation.geojson`), while the graphs exist in none | guards on `walk.graphml` instead. This was a bug, not a missing skip: the tests could never have passed on any machine but the author's |
| `test_live_pipeline.py` (1) | one test asserted both that the weather basis is *derived* (needs the archive) and that it is *never hard-coded* (needs nothing) | split in two. The anti-hard-coding guard now runs on clean clones — which is precisely where somebody would be tempted to type the date in |
| `test_baseline_freeze.py` (2) | `--check` reports the two git-ignored acquisition manifests MISSING and exits 1 | absence of exactly those two paths is forgiven, and nothing else. A manifest that is *present* and whose sha256 has MOVED still fails, and every tracked artifact is checked exactly as hard as before |

## Caveats, and what this does NOT show

- **`make baseline-verify` is soft here, not passing.** It exits non-zero because
  the two acquisition manifests are absent, and `gates.py` records it as a
  warning only where they are absent — on the author's laptop it is a hard gate.
  So this run does **not** verify the training-set definition. It does verify
  every tracked artifact's digest, which is the part a clone can check.
- **A green clean-clone run is not a reproduction of the results.** The 35
  data-gated skips are exactly the tests that re-derive numbers from raw inputs.
  This run proves the code, the registry and the tracked artifacts are mutually
  consistent; it proves nothing about whether the FIRMS pull would come back the
  same.
- **52 skips is a coverage statement, not a passing grade.** Roughly 4.7 % of the
  suite does not execute on a clean clone. The number to watch is whether it
  grows: a skip added to silence a failure looks identical, in the summary line,
  to a skip that was always unrunnable.
- **This is one Linux sandbox, one Python (3.11.15), one pinned stack.** It says
  nothing about macOS, about 3.12, or about a floated pin.
- The counts here are session measurements of the test suite, not scientific
  results: they are deliberately **not** registered in `docs/NUMBERS.json`, which
  holds numbers derived from committed artifacts. Re-measure rather than quote
  these if the head has moved.

## Reproducing

Clone, then run the two commands under **Method**. The gate record lands in
`.auto/gates.json` (git-ignored) and is uploaded as an artifact by the
`auto-gates` GitHub Actions workflow on every push to `auto/**`.
