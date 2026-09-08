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
§3.10). No keys, no `.env`.

### ⚠ 「No network」 was false here for five weeks, and is now enforced (WFG-139)

This line read 「No network, no keys, no `.env`.」 from 2026-09-03 until
2026-09-08, and the first three words were wrong. On every **cold** run the
suite downloaded `N36E129.hgt` (25,934,402 B) and its `.gz` (8,473,868 B) from
`elevation-tiles-prod.s3.amazonaws.com` into `data/raw/dem/srtm/`, in the middle
of the `pytest-full` stage. Eleven consecutive laps measured it and none of them
could say which line did it, because a 25 MB file appearing during a five-minute
stage names no caller and a warm re-run never reproduces it.

**Method.** `tests/conftest.py` now installs a session-wide guard that refuses
outbound socket connections (`connect`, `connect_ex`, `create_connection`) to
any non-loopback address, and to any address named in the environment's
`*_proxy` variables even when it is loopback. A test that reaches the network
fails, naming CHARTER §4b, on every machine.

**Result, measured 2026-09-08 on this sandbox at `ab4e71e`.** ⚠ This line read
`088203c` until 2026-09-08T0321Z, and `git ls-tree -r 088203c -- tests/conftest.py`
is empty: the guard this result is about first exists at `ab4e71e`, the commit that
added it. The measurement was real and was reproduced; the commit id under it named
a tree with no guard in it (critic #39, WFG-178). With
`data/raw/dem/srtm/` and the derived `data/cache/dem_yeongdeok_2025_srtm_500m_*.nc`
deleted first, a full `pytest` run with the guard active **flagged three tests**:
**two** real network uses — one more than the backlog row had named in eleven
measurements — and one false positive that belonged to the guard's own first
draft rather than to the suite.

| test | what it was doing | fix |
|---|---|---|
| `tests/test_spread_warmup.py::test_model_config_ignition_radius_increases_initial_burn` | asked for `dem_source="srtm"` to assert the size of an ignition disc | now `"synthetic"` |
| `tests/test_raster_ingestion.py::test_auto_dem_prefers_srtm_when_tile_available_else_synthetic` | `source="auto"`, asserting 「either outcome is acceptable」 | split into three offline tests |
| `tests/test_finals_acts.py::test_the_four_acts_advance_in_a_real_browser` | talking to a Chromium this repository launched, on a loopback port | **not a network use**; the guard's first draft was wrong to refuse it |

`data/raw/` was byte-for-byte unchanged across that run. ⚠ That total is not written here as a figure: `data/raw/**` is git-ignored, so it holds a different number of bytes on every machine and **zero** on the clean CI clone this document is about. What is checkable is the difference, which is what the hook below measures.

**The second half of the mechanism.** The socket guard sees the calls the
standard library funnels connections through, and nothing else. What sees
everything else is `conftest.pytest_sessionfinish`, which measures `data/raw/`
before and after the run and **fails the run** if it grew — the same measurement
eleven laps took by hand, taken automatically at the end of every run. It was
graded rather than assumed: a throwaway test that wrote a few kilobytes into
`data/raw/` turned a passing run's exit status to 1 (2026-09-08). That hook also
answers WFG-172's 「did this run download anything」 without a network call.

**Caveats, and what this does not show.** Enumerated rather than gestured at,
because a guard's blind spots are the only part of it that can surprise anyone.
The socket guard does not see: a C extension calling `connect(2)` directly; a
subprocess; a loopback service that forwards traffic without appearing in the
proxy variables; **UDP** (`sendto`/`sendmsg` are not patched); **name
resolution** (`getaddrinfo` is not patched, so a test can still depend on DNS,
which is half of what CHARTER §4b forbids); anything at **import or collection
time**, because the guard is a session fixture and fixtures are set up after
collection; and any `pytest` invocation on a path outside `tests/`, which loads
no `conftest.py` at all. The session hook covers what leaves bytes behind in
`data/raw/` and nothing else: a fetch that writes nowhere, overwrites a
same-size file, or writes to another directory is seen by neither. Four of these
were named by this lap's independent reviewer and not by the lap. The guard's own first draft exempted loopback and therefore
blocked nothing in this sandbox, whose egress runs through
`HTTPS_PROXY=http://127.0.0.1:38639`; that is why the proxy clause exists and
why `tests/test_no_network_in_tests.py` asserts it rather than trusting it.

The **7** tests that `skipif` on the cached tile still skip on a clean clone —
this row makes that honest, it does not make them run. ⚠ This sentence said **six**
until 2026-09-08T0321Z, and the seventh
(`tests/test_raster_ingestion.py::test_auto_dem_prefers_srtm_when_the_tile_is_cached`)
was added by the same commit that wrote the six. Beside them, **4** more skips say SRTM
in their `reason` while gating on `data/raw/firms_data/yeongdeok_2025_dem.tif`, a
laptop-bundle GeoTIFF and not the tile (`tests/test_slope_digraph.py`); that naming
defect is WFG-180. So on a clean clone `pytest -rs` prints **11** SRTM-looking skips
and only **7** of them are about this tile. ⚠ **That is a clean-clone statement and
nowhere else's.** The four are gated on a laptop-bundle file and the seven on a tile
that a laptop may also have, so on the booth machine some or all of the eleven **run
instead of skipping**, and the count a judge sees there is lower. Do not quote 11 or 7
off a machine that carries `data/raw/`.

**Where these numbers come from.** `tests/test_tile_gated_skip_count.py` derives 7 and
4 from the test sources by walking their `skipif` decorators — not from a run, so it
answers the same on a warm laptop and a clean clone — and it fails when a sentence
bound to them disagrees with the tree, in this file and in the Q28 and Q40 cards. ⚠
**It binds the sentences it names and no others.** Every restatement of these integers
in this section is anchored there; a *new* one written elsewhere is unwatched, exactly
as 「여섯 개」 was. The canonical list is `pytest -rs` itself.

**Warming the cache on purpose** is a script's job, not a test's. Set
`WFG_TESTS_ALLOW_NETWORK=1` for a whole run if you must; no gate and no workflow
sets it, and a test asserts that.

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
