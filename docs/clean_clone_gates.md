# The suite on a clean clone — what green means when the data is not there

**Status:** measured 2026-09-03 on the autonomous loop's Linux sandbox
(`auto/dev`, head `953eb6c`, Python 3.11.15) by
`scripts/auto/gates.py --mode full`. Backlog row WFG-001.

## Why this document exists

Sessions 18–22 were green on one laptop. That laptop holds `data/raw/**`, which
is git-ignored: the FIRMS detections, the ERA5 pull, the DEM rasters, the two
acquisition manifests and the acquired OSM graphs never reach a clone. So "the
suite passes" was, until this row, a statement about one machine's disk.

A stranger cloning this repository gets the tracked artifacts and nothing else.
This file records what happens then, because the reproducibility claim in the
README is a claim about *their* run, not about the author's.

## Method

```
bash scripts/auto/bootstrap.sh                        # pip-only, pinned
.auto/venv/bin/python scripts/auto/gates.py --mode full
```

`gates.py` runs each gate as a direct subprocess and reads its exit status; it
never pipes one (`scripts/check_gate_invocations.py` enforces that; CHARTER
§3.10). No network, no keys, no `.env`.

## Result

| gate | outcome |
|---|---|
| `make verify` | PASS |
| `make baseline-verify` | WARN — soft here, see caveats |
| `make snapshot-verify` | PASS — all present snapshots intact, 47 local-only/digest-only absent |
| `make env-check` | PASS — the environment matches `requirements.txt` |
| `pytest` | **1063 passed, 54 skipped, 0 failed, 0 errors** (124 s) |

The same gates pass on a machine that shares nothing with this sandbox:
GitHub Actions run
[33718108879](https://github.com/Sparkxt-0318/wildfireguardian/actions/runs/33718108879)
(`auto-gates`, `ubuntu-latest`, head `c42287e`) concluded **success**, bootstrap
in 34 s and gates in 94 s. That is the second half of WFG-001's done-when, and
it is the first `auto-gates` run ever to conclude green: runs 1, 2, 3, 5, 6 and
9 were cancelled by the concurrency rule as pushes stacked, and runs 4 and 7
failed.

### The 54 skips, by cause

| cause | tests | it means |
|---|---:|---|
| git-ignored data bundle — FIRMS / ERA5 / DEM / detections CSV / the two acquisition manifests | 37 | the input is on the author's laptop only |
| OSM cache never acquired in this clone | 7 | `data/cache/**` is git-ignored |
| optional `legacy` extra (`xgboost`) not installed | 7 | deliberate: not a core dependency, see `requirements.txt` |
| deliberate, unrelated to this environment | 3 | e.g. a gate whose gap has since been closed |

Every one of the 54 carries its reason in the skip message; `pytest -rs` prints
them.

### The four missing outcomes, diagnosed

The first clean-clone lap recorded that the sandbox reported 1,116 outcomes
against the laptop's 1,120 and, rather than rounding the gap away, wrote it down
as undiagnosed. It is `tests/test_empirical_interaction.py` — reached here and,
independently and at nearly the same time, by that lap itself
(`requirements.txt`, and this row's second note in `docs/auto/BACKLOG.md`).

That module calls `pytest.importorskip("xgboost")` at line 12, at **module
level**. A collection-time skip reports as **one** outcome, not one per test,
and the module holds five tests. So:

| | collected | reported outcomes |
|---|---:|---:|
| sandbox at `953eb6c` | 1,115 | 1,116 (1,115 + the one collection-level skip) |
| this lap adds one test (a split, below) | 1,116 | 1,117 = 1,063 passed + 54 skipped |
| laptop, where `xgboost` is installed | 1,120 | 1,120 = 1,116 passed + 3 skipped + 1 xpassed |

1,116 − 1 + 5 = 1,120. Nothing is unaccounted for. ⚠ The laptop column is the
figure reported in the kickoff commit, not one this lap could re-measure; what
is measured here is the sandbox column and the five tests in that module.

## What had to change to get here

The first clean-clone run was 10 failed / 7 errors. `brotli` — undeclared, and
needed by `fontTools` to open the vendored `.woff2` faces — accounted for five
(`e1588b4`). The remaining twelve were tests that could not tell "the input is
absent" from "the result is wrong", fixed in `c42287e`: the `test_photo_exif`
fixture that preloads the region DEM, the two `test_osm_cache_isolation` guards
that asked whether the cache *directory* existed when one tracked file makes it
exist in every clone, and the laptop-only manifests in `test_baseline_freeze`
and `test_live_pipeline`. None was a defect in the project's science, and none
touched an artifact.

This lap adds one further split, in `test_live_pipeline.py`. One test asserted
both that the weather basis is *derived* from the detections archive and that it
is *never typed into the source*. Only the first needs the archive, so the
`skipif` covering both took the anti-hard-coding guard out of every clean clone
— precisely the environment in which hard-coding the date is the tempting fix.
The guard is now its own test and runs everywhere.

## Caveats, and what this does NOT show

- **`make baseline-verify` is soft here, not passing.** It exits non-zero
  because the two acquisition manifests are absent, and `gates.py` records it as
  a warning only where they are absent; on the author's laptop it is a hard
  gate. So this run does **not** verify the training-set definition. It does
  verify every tracked artifact's digest, which is the part a clone can check.
- **A green clean clone is not a reproduction of the results.** The 37
  data-gated skips are exactly the tests that re-derive numbers from raw inputs.
  This proves the code, the registry and the tracked artifacts are mutually
  consistent. It proves nothing about whether the FIRMS pull would come back the
  same.
- **54 skips is a coverage statement, not a passing grade.** About 4.8 % of the
  suite does not execute on a clean clone. The number to watch is whether it
  grows: in a summary line, a skip added to silence a failure is indistinguishable
  from a skip that was always unrunnable.
- **One sandbox, one Python (3.11.15), one pinned stack, plus one
  `ubuntu-latest` runner.** Nothing here speaks to macOS, to 3.12, or to a
  floated pin.
- The counts here are measurements of the test suite, not scientific results.
  They are deliberately **not** registered in `docs/NUMBERS.json`, which holds
  numbers derived from committed artifacts. Re-measure rather than quote these
  once the head has moved.

## Reproducing

Clone, then run the two commands under **Method**. The gate record lands in
`.auto/gates.json` (git-ignored) and is uploaded as a run artifact by the
`auto-gates` workflow on every push to `auto/**`.
