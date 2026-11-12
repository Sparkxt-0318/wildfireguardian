# Verification checkpoint ledger (November 2026 harness)

Kept by the independent verifier (Hannah). One row per verification request. The last **PASS** row for a stream is the checkpoint that stream returns to after a failure. Verdicts: PASS, PASS WITH NOTES, FAIL; "not run" items are never counted as passed.

| # | Stream | Worker | SHA | Claim | Command | Verdict | Date (UTC) | Notes |
|---|---|---|---|---|---|---|---|---|
| 0 | baseline | Hannah | `5fa19a2` (main) | Pre-existing state of every suite that runs in a Linux cloud container; reference for all "no regressions" claims | See [Baseline detail](#baseline-detail-5fa19a2) | PASS WITH NOTES (forecast/experimental suites pending) | 2026-11-12 | 1 env-dependent planner failure in the API venv (no `shapely`); passes in the planner's own venv. Forecast torch suites pending. |

## Baseline detail (5fa19a2)

Host: Linux cloud container, 4 vCPU, 15 GiB RAM, Python 3.12 (`/usr/bin/python3.12`; container default is 3.13), Node 22.23.4, npm 10.9.9. GNU `time` was missing and was installed with `apt-get install time` (as `make api-tools` and CI require). Timings are wall clock, single run.

Environments:
- **API venv** `.venv`: `make api-setup` (rc 0, 39 s). Installs `./integration[packets]` + `api/requirements.txt` under `constraints-routing.txt`, fetches and SHA-verifies 132 recorded input files into `data/routing`.
- **Planner venv**: `python3.12 -m venv` + `pip install -r planner/tools/requirements.txt` (the file says the data was generated with Python 3.13.16; tests pass on 3.12).
- **Full forecast venv**: CI's `next-tracks` recipe. `download.pytorch.org` is **blocked** by this environment's network policy, so `torch==2.5.1` comes from PyPI (CUDA build, run on CPU) instead of CI's CPU wheel. Then `./forecast[test,baseline]`, `./integration[packets]`, `hypothesis==6.170.13`.

| Suite | Command (from repo root) | Env | Result | Time |
|---|---|---|---|---|
| API fast tests | `make api-test` | API | **109 passed**, 2 deselected (golden/panel), 1 warning (Starlette httpx deprecation) | 70 s |
| Release identities | `.venv/bin/python tools/verify_release.py` | API | PASS: 367 hashes, checkpoint, scores, syntax, privacy | 1 s |
| Post-merge preservation | `.venv/bin/python tools/verify_postmerge_preservation.py` | API | PASS: 3640 frozen artifacts byte-identical | 9 s |
| Planner pytest, before assets | `.venv/bin/python -m pytest -q tests/planner` | API | 147 passed, 13 skipped (`planner/.assets` missing) | 25 s |
| Planner assets | `PYTHON=.venv/bin/python bash planner/scripts/fetch_planner_assets.sh` | — | rc 0 | 11 s |
| Planner pytest, with assets | same | API | **1 failed**, 159 passed: `test_orientation_segment_midpoints_inside_published_cell_polygons`, `ModuleNotFoundError: shapely` (env, not code) | 28 s |
| Planner pytest, with assets | `<planner venv>/bin/python -m pytest -q tests/planner` | Planner | **160 passed** | 28 s |
| Planner npm (vitest, incl. Chromium print-fit) | `cd planner && npm ci && npm test` | Node | **365 passed** (21 files) | 62 s |
| Showcase | `node --test demos/showcase/tests/*.test.mjs` | Node | 8 passed | <1 s |
| Routing package | `cd routing-package && ../.venv/bin/python -m pytest -q tests` | API | 91 passed, 309 subtests | 4 s |
| Routing API | `cd routing-api && PYTHONPATH=src ../.venv/bin/python -m pytest -q tests` | API | 11 passed, 17 subtests | <1 s |
| Window routing checker | `.venv/bin/python -B experimental/window-routing/tests/test_full_checker_window.py` | API | OK | 2 s |
| Window kit build | `.venv/bin/python -B experimental/window-routing/build_kit.py --out <tmp>` | API | rc 0, 61 files | <1 s |
| Window evidence | `.venv/bin/python -B research/routing/request-window-20261029/verify_evidence.py` | API | PASS (80 executions, 26 paired times, 72 thermal assessments) | <1 s |
| Routing preparation, pure Python | `cd experimental/routing-preparation && PYTHONPATH=src python -m unittest discover -s tests` | API | OK, 24 skipped (native extension not built) | 1 s |
| Routing preparation, native | `python tools/build_native.py` then `PYTHONPATH=src WFG_TEST_REQUIRE_NATIVE=1 python -m unittest discover -s tests` | API | build rc 0; **OK, 0 skipped** | 3 s |
| Prepared-graph cache recompute | `.venv/bin/python research/routing/prepared-graph-cache/recompute.py` | API | rc 0 | <1 s |
| explain_deadlines | `python -m pytest -q tests/explain_deadlines` | API | **collection error**: `hypothesis` not installed in API venv (env) | 1 s |
| explain_deadlines | same | Full | pending | |
| Forecast + post-merge | `python -B -m pytest -q forecast/tests tests/postmerge` | Full | pending | |
| Experimental tracks | `python -B -m pytest -q experimental/{flame-front-radiation,scenario-members,sipp-routing,synthetic-truth}/tests` (with CI's `PYTHONPATH`) | Full | pending | |

Not run in this baseline: `make api-golden`, `make api-panel` (timing-sensitive, evaluated host is macOS), `make reproduce-linux` / Uljin FX1 replay, Docker builds and `scripts/api_smoke.sh` (no Docker daemon checked), `monte-carlo-extension/tests` (not in CI).

Working-tree check: `git status` clean after all runs (`data/`, `planner/.assets`, `node_modules`, native binary are git-ignored).
