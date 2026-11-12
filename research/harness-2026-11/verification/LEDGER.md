# Verification checkpoint ledger (November 2026 harness)

Kept by the independent verifier (Hannah). One row per verification request. The last **PASS** row for a stream is the checkpoint that stream returns to after a failure. Verdicts: PASS, PASS WITH NOTES, FAIL; "not run" items are never counted as passed.

| # | Stream | Worker | SHA | Claim | Command | Verdict | Date (UTC) | Notes |
|---|---|---|---|---|---|---|---|---|
| 0 | baseline | Hannah | `5fa19a2` (main) | Pre-existing state of every suite that runs in a Linux cloud container; reference for all "no regressions" claims | See [Baseline detail](#baseline-detail-5fa19a2) | PASS WITH NOTES (completed in row 0b) | 2026-11-12 | 1 env-dependent planner failure in the API venv (no `shapely`); passes in the planner's own venv. Forecast torch suites: see row 0b. |
| 0b | baseline (completion) | Hannah | `5fa19a2` (main) | Forecast/cross-track, experimental and explain_deadlines suites in the CI `next-tracks` environment | see Baseline detail (Full env rows) | PASS | 2026-11-12 | forecast/tests + tests/postmerge 3531 passed (584 s); 4 experimental suites 177 passed, 0 skipped (58 s); explain_deadlines 92 passed (14 s). Matches README counts. torch from PyPI (cu124 build, CPU run). |
| 1 | S-D9 | Victor | `df5aa8e` | Inventory: measured figures (pooled Brier of 5 predictors on 1,705,079/8,520; M548 8.17% BSS arithmetic; 273 cases; KR 26/33 scored, 7 KFS_01 unavailable; catalog 44 = 29 US + 15 KR) | Inventory §2 pooled script; JSON reads of `observed_runtime_*_20261013.json`, `events.json`, `korean2025/cases/*.json` | PASS WITH NOTES | 2026-11-12 | All measured numbers reproduce. "617 zero-p positives" is quoted from `docs/next/prompts/01B_forecast_upgrades.md`, not reproducible from git. Heldout dir 119 MiB, not 123 MB. |
| 2 | S-D9 | Victor | `3e2eb2d` | Exposure ledger: 49 fires FIT 34 / SELECTED_ON 1 / SCORED 11 / INSPECTED 3; interval rows 273/33/28/30; M548 27/28 and FARSITE 29/30 equal US2024 intervals; CSV SHA-256 e47d404f…, 4d0d555f… | `python3 research/harness-2026-11/S-D9/ledger/build_ledger.py && sha256sum …/*.csv` (unshallowed clone) | PASS WITH NOTES | 2026-11-12 | Hashes exact; class counts and SPLIT.json consistency independently re-derived; interval matches re-derived. Repo-wide ID grep found no missing fire. Rerun dirties `LEDGER_SUMMARY.json` (`repository_head` = build HEAD), so "no git diff" is false. 324 = 273 + 51 checked arithmetically only. |
| 3 | S-D9 | Victor | `8fe1e2b` (supersedes `29493b1`) | sd9bench reproduces every score field of forecast-v2 `heldout` (16 predictors, 30 paired intervals) within 1e-12 rel; 34 tests pass | fresh py3.12 venv, `pip install numpy==1.26.4 scipy==1.13.1 pytest`; `cd research/harness-2026-11/S-D9 && python -m pytest -q tests -p no:cacheprovider` | PASS | 2026-11-12 | 34 passed (68 s). `compare()` caught 338/338 random numeric mutations; no RESULTS.json read in sd9bench. 7 metadata keys of `heldout` not compared. RPS hand values checked by hand. |
| 4 | S-D2 | Elena | `6d125bd` | Kriging SD understates arrival uncertainty vs NIROPS brackets: pooled interval-censored MLE c = 1.747 (13,324 cells, 8,520 mapped; NLL 26,763 vs 31,143 at c=1); per-fire c 1.07–2.18; shifts −11 to +57 h; median SD 27–96 h | Zenodo 21788344 zip via `daniel/data-fetch` fetch.py (sha256 612edf5f… = SPLIT.json); `python calibrate_kriging_sd.py --rasters …/rasters_us` | PASS WITH NOTES | 2026-11-12 | Exact reproduction (≤1e-6 rel vs committed JSON). Independent bracket rebuild + own grid MLE: c 1.745, same NLL; −745 clamp never binds; direct row/col corr(μ, mid) 0.90–0.97 vs row-flip ≤0.56; t0 UTC per Zenodo README. Mislabel: max per-fire c is RedRock 2.21 (2.18 is Lava). c also absorbs NIROPS timing/mapping error. |
| 5 | S-D1 | Marcus | `adfb6f1` | (1) c651 pair rate = K (P = 1−exp(−dt·ΣKB)); hourly CA → CT jump process → FPP as dt→0. (2) sampler exact, 9 tests. (3) toy fast 349.8 vs 771.0 (55% fewer), slow 3.48 vs 3.63; convergence gap 14.1 → 0.34 | `python -m pytest research/harness-2026-11/s-d1/tests -q`; `python …/convergence_check.py`; `python …/toy_check.py` (py3.12, torch 2.5.1, numba 0.68.1) | PASS WITH NOTES | 2026-11-12 | Mapping confirmed in `models.py` (new_burn_probability, MixedNonnegativeKernel._combine) and `rollout.simulate` (synchronous, absorbing, env independent of state). 9 passed; convergence JSON byte-identical; toy table reproduced exactly. Module-level `importorskip("torch")` silently skips all 9 tests without torch. No end-to-end CA vs `rollout.simulate` test. First-order convergence noise-limited at dt ≤ 1/32. |
| 6 | S-D2 | Elena | `c7f7df3` | Synthetic (16 reps): perimeter MCEM beats plugin 16/16 (NLL 0.0909 vs 0.2752; rate ratio 1.012 vs 0.882); soft_hourly ratio 0.530, NLL 0.1953; soft_risk_softfeat 0.0333; kriged MCEM beats hard_hourly 3/16 | `python -m pytest -q tests` (18 passed); `python run_synthetic.py --replicates 4 --workers 4` | PASS WITH NOTES | 2026-11-12 | Committed summary matches all claims. Reps 0–3 rerun on py3.12/numpy 2.5.4 (author py3.13/numpy 2.1.3): simulation identical, deterministic estimators ≤3.2e-4 rel, MCEM rows differ up to 34% (chain sensitivity); all paired directions hold (perimeter 4/4, kriged vs hard_hourly 0/4). 'oracle' is not a floor (soft_risk_softfeat beats it). Full 16-rep run and exact author env not run. |

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
| explain_deadlines | `python -m pytest -q tests/explain_deadlines` | Full | **92 passed** | 14 s |
| Forecast + post-merge | `python -B -m pytest -q forecast/tests tests/postmerge` (CI env vars, 2 threads) | Full | **3531 passed**, 551 warnings | 584 s |
| Experimental tracks | `python -B -m pytest -q experimental/{flame-front-radiation,scenario-members,sipp-routing,synthetic-truth}/tests` (with CI's `PYTHONPATH`) | Full | **177 passed**, 0 skipped | 58 s |

Not run in this baseline: `make api-golden`, `make api-panel` (timing-sensitive, evaluated host is macOS), `make reproduce-linux` / Uljin FX1 replay, Docker builds and `scripts/api_smoke.sh` (no Docker daemon checked), `monte-carlo-extension/tests` (not in CI).

Working-tree check: `git status` clean after all runs (`data/`, `planner/.assets`, `node_modules`, native binary are git-ignored).
