# R8 — Cloud-sandbox readiness audit (WildfireGuardian)

Date: 2026-09-03. Auditor ran read-only commands against
`/Users/jp/Desktop/Korea Code Fair/wildfireguardian` (branch `auto/dev` = `ordering-boundary`,
HEAD `25f1e14`) with the reference interpreter `/Users/jp/miniforge3/envs/wfg311/bin/python`
(3.11.15, conda-forge, arm64), plus a throw-away `git clone` of that branch in the scratchpad
to simulate a fresh checkout. No tracked file was modified.

## 0. Headline

1. **`make verify` passes on a clean clone with nothing but tracked files** (7.6 s locally;
   all 9 sub-gates OK). Nothing in it needs git-ignored data, the submodule, network, or a key.
2. **`pytest` on a clean clone is NOT green: `5 failed, 1067 passed, 41 skipped, 7 errors`
   (1,120 collected, 90 s).** All 12 non-passes are caused by git-ignored inputs
   (`data/raw/firms_data/*`, `data/cache/osm/yeongdeok_2025/*`) reached through tests whose
   skip guards are missing or defective. README.md:642 ("a bundle-absent run passes with more
   skips") is false today. The reference run with the bundle is 1,116 passed / 3 skipped /
   1 xfailed (docs/SESSION22_REPORT.md:259).
3. **Every pin in `requirements.txt` (24 packages) has a manylinux x86_64 wheel on PyPI for
   both cp311 and cp312, and the pinned set has no mutual metadata conflict** — pip-only
   install on Linux x86_64 is feasible; conda is not needed. (Verified 2026-09-03 via
   `https://pypi.org/pypi/<pkg>/<ver>/json`; see §3.)
4. **The draft loop scaffolding created today in the working tree (`scripts/auto/bootstrap.sh`,
   `scripts/auto/gates.py`, `.github/workflows/auto-gates.yml`) can never go green as written**:
   `gates.py --mode full` runs `make baseline-verify` as a hard gate (always red without the
   two git-ignored manifests) and full pytest without deselecting the 12 known non-passes.
   It also references `docs/auto/CHARTER.md`, `BACKLOG.md`, `NEEDS_HUMAN.md`, which do not exist.
5. **GitHub `origin/Main` (`c0bd560`, 2026-08-10) is 52 commits behind the local branch; `origin/round3-dev`
   is 135 behind.** A cloud agent cloning GitHub today works on Session-15-era code (52 test files
   vs 62 locally). Nothing the loop does matters until `auto/dev` is pushed.
6. The reference Mac env itself fails `make env-check` (`affine` pinned 3.0.1, installed 2.4.0),
   so `make all-checks` is red on the laptop today. The 3.0.1 pin came from the Session-18 Linux
   PyPI run (docs/SESSION18_REPORT.md:52-55) and will pass on pip-Linux.
7. One undeclared, gate-invisible dependency: the font-metric tests in `tests/test_screen_checks.py`
   open `.woff2` files with `fontTools.ttLib.TTFont`, which needs `brotli` (fontTools docs:
   https://fonttools.readthedocs.io/en/latest/optional.html). `fonttools==4.63.0` does not pull it
   (only the `[woff]` extra does; metadata checked via importlib.metadata). The clean-clone run
   passed only because conda's `wfg311` has Brotli 1.2.0. `scripts/check_declared_deps.py` cannot
   see it (no import statement, no `engine=` literal). Bootstrap must `pip install brotli`.
   **UNVERIFIED in practice** (I did not uninstall brotli to watch the failure), derived from
   fontTools' `woff2.py` import of `brotli`.

## 1. Inventory

### 1.1 Dependency declarations

| File | Content | Notes |
|---|---|---|
| `pyproject.toml` `[project].dependencies` | numpy, scipy, pandas, shapely, matplotlib, pydantic, tqdm, rich, PyYAML, affine, h5netcdf, h5py | `pydantic`, `tqdm` are declared but imported nowhere (requirements.txt comment); harmless. |
| extras | `geospatial` (geopandas, rasterio, xarray, pyproj, folium), `ml` (scikit-learn), `routing` (networkx, osmnx), `legacy` (xgboost, netCDF4), `dev` (pytest, jupyter, pillow, fonttools), `acquisition` (cdsapi), `sms` (twilio) | **`fastapi`, `uvicorn`, `httpx` are in NO extra** — only in requirements.txt. A fallback to extras (as bootstrap.sh drafts) silently drops the API layer → `tests/test_api.py` (45 tests) importorskips = the Round-2 silent-skip failure again. |
| `requirements.txt` | 24 exact pins (list in §3) | Header says "INSTALL VIA CONDA-FORGE, NOT PIP"; that advice predates Session 18, which installed all of it from PyPI wheels on Linux aarch64 py3.11 (docs/SESSION18_REPORT.md:324). PyPI has x86_64 wheels too (§3). |
| `[tool.pytest.ini_options]` | `testpaths=["tests"]`, `addopts="-ra --strict-markers"` | **No custom markers registered, no `conftest.py` anywhere.** There is no `-m` expression available; selection must be by node id / `-k`. |

### 1.2 Makefile targets (all `PYTHON ?= python`; `SHELL=bash -o pipefail -e`)

`verify` = verify-numbers + check-forbidden + check-region-literals + check-arm-isolation +
check-gate-invocations + check-arm-controls + check-declared-deps + check-artifact-manifest +
check-number-collisions. `baseline-verify` (freeze_baseline.py --check), `snapshot-verify`,
`env-check`, `test` (pytest -q), `finals` (rebuilds web/finals.html; needs the geospatial stack),
`all-checks` = verify + baseline-verify + snapshot-verify + env-check + test.

### 1.3 Gate scripts relevant to bootstrap

- `scripts/env_check.py`: every `==` pin in requirements.txt must be installed at that exact
  version; `--allow-version-drift` downgrades drift to a report. One-directional by design
  (docs/ENVIRONMENT.md "checks one direction only").
- `scripts/check_declared_deps.py`: AST walk of every tracked `.py` + `engine=`/`driver=` literal
  scan; exit 1 on an undeclared third-party import. Passes today (24 modules / 285 files).
- `scripts/freeze_baseline.py --check`: sha256 of 4 PROTECTED artifacts, 115 tracked
  `data/processed` files, **and the two git-ignored manifests**
  `data/raw/firms_data/fire_manifest.json`, `data_layers_manifest.json` (`UNTRACKED_CONTRACTS`).
  A missing manifest is reported as `MISSING` and exits non-zero (verified in the clone).
- `scripts/snapshot_external.py --verify`: passes on a clean clone ("all present snapshots intact,
  47 local-only/digest-only absent").

### 1.4 Test classification (1,120 collected; 62 files)

(a) **Network** — none. `grep` for `requests.get|urllib|urlopen|httpx.(get|post)|graph_from_*|cdsapi|overpass|smtplib|twilio` in `tests/` returns nothing. The only runtime network client in `src/` is `data_io/raster.py` (urllib, DEM download) and tests point it at `tmp_path`. `.env` is never loaded by tests. Airgap is not proven (SESSION18 §"검증하지 못한 것" 2), but no test intentionally contacts the network.

(b) **Git-ignored data** — the whole story. What a clean clone lacks: `data/raw/firms_data/*` (FIRMS CSV/GeoJSON, DEM `.tif`, ERA5 `.nc`, both manifests; 1.3 GB locally), `data/raw/dem/srtm/N36E129.hgt`, `data/cache/osm/yeongdeok_2025/{walk,drive}.graphml` etc. (only `vegetation.geojson` is tracked there), `.cache_weather_dependency.pkl` (24 MB scratch, referenced by no test), `outputs/live/screens/*` (git-ignored except `manual/`). Tracked and sufficient: `data/processed` (115 files, incl. `spread_v2_lofo.json`, all `.npz` hazard fields), `data/snapshots` (63 files: 3 SRTM DEMs, 5 OSM graphml, buildings), `data/raw/kfs_fire_statistics/*.csv`, `web/*.html` + vendored fonts, `demo/operator_screen.html`, `docs/figures/*.png`.

Behaviour in the clean clone:

| File | Tests | Clean-clone result | Why |
|---|---|---|---|
| test_spread_v2.py | 16 | 14 pass, 2 skip | `needs_data` guard; the 77 s LOFO test is one of the skips |
| test_fuel_coverage_gate.py | 13 | all skip | module `skipif(not MANIFEST.exists())` |
| test_calibration_metrics.py | 16 | 11 pass, 5 skip | guard on `data_available()`; the 1 xfail is among the skips |
| test_srtm_dem.py / test_validation_robustness / _session3 | 4+1+1 | skip | SRTM tile guard |
| test_slope_digraph.py, test_partition_categories.py | 4+1 | skip | DEM/NPZ guards |
| test_rescue_routing_real.py | 5 | skip | OSM cache guard |
| test_live_pipeline.py | 45 | 1 skip, **1 FAIL** | `test_weather_basis_is_derived_from_committed_data_not_a_literal` reads `yeongdeok_2025_detections.csv` with no guard (the module's `ARCHIVE` skipif at line 144 is not applied to this test at line 82) |
| test_baseline_freeze.py | 8 | **2 FAIL** | `test_the_live_tree_matches_the_record`, `test_a_moved_artifact_is_actually_detected` — `UNTRACKED_CONTRACTS` manifests absent → `MISSING` |
| test_osm_cache_isolation.py | 5 | **2 FAIL** | guard is `if not d.exists(): skip` but `data/cache/osm/yeongdeok_2025/` exists in every clone because `vegetation.geojson` is tracked → guard never fires; `walk.graphml` missing |
| test_photo_exif.py | 30 | 23 pass, **7 ERROR** | module-scoped `client` fixture calls `build_runner(regions=["yeongdeok_2025"])` → `RasterioIOError` on `data/raw/firms_data/yeongdeok_2025_dem.tif`; no guard |

(c) **OmniRoute submodule** — `external/OmniRoute` (gitlink `1b5f7dd`, https://github.com/diegosouzapw/OmniRoute.git) is referenced by **nothing** in `src/`, `scripts/`, `tests/`, `Makefile`, `pyproject.toml`, `README.md` (grep: 0 hits). Do not `submodule update`; it is dead weight.

(d) **> 60 s** — only `tests/test_spread_v2.py::test_lofo_auc_is_skilful_and_direction_is_unimportant` (76.7 s on M-series with data; skipped without). Next slowest with data absent: 9.7 s (`test_ml_baselines`). Whole clean-clone suite: 89.8 s on the Mac; expect ~3–6 min on a 2-vCPU GitHub runner (UNVERIFIED estimate).

(e) **macOS / fonts** — no `sys.platform`/darwin conditionals in tests. Font tests use the vendored `web/assets/fonts/*.woff2` via fontTools (needs brotli, §0.7). `test_calibration_metrics.py::test_random_forest_calibration_regenerates_exactly` is `xfail(strict=False)` for non-reference BLAS/thread order — only reachable with the data bundle. `tests/test_api.py::test_run_api_port_taken` spawns `scripts/run_api.py` as a subprocess and asserts on Korean stderr text; passed in the clone.

## 2. Measurements

| Command | Result |
|---|---|
| `make verify PYTHON=…wfg311…` (working tree) | PASSED, 7.6 s wall |
| `make verify` in clean clone (`PYTHONPATH=clone/src`) | PASSED (all 9 gates OK) |
| `make env-check` (wfg311, Mac) | **FAILED** — `affine` pinned 3.0.1, installed 2.4.0; 20 other pins ok |
| `pytest --collect-only -q` | 1,120 tests, 2.8 s |
| `pytest -q -x --durations=25 tests/test_smoke.py tests/test_clean_clone_boot.py tests/test_spread_v2.py` (with data) | 56 passed, 85 s; LOFO test 76.7 s, everything else < 2 s |
| Full `pytest -q -p no:cacheprovider` in clean clone | **5 failed, 1067 passed, 41 skipped, 7 errors**, 89.8 s |
| `make snapshot-verify` in clean clone | exit 0 |

## 3. PyPI wheel availability of the pins (Linux x86_64), checked 2026-09-03

Source: `https://pypi.org/pypi/<name>/<version>/json` for each pin. All 23 requirements pins plus
xgboost 3.2.0 have wheels for cp311 and cp312 on manylinux x86_64 (xgboost ships
`py3-none-manylinux_2_28_x86_64`). numpy 2.4.6, scipy 1.17.1, pandas 3.0.5, xarray 2026.7.0,
pyproj 3.7.2, networkx 3.6.1 (`!=3.14.1`), scikit-learn 1.9.0, matplotlib 3.11.1 all declare
`requires_python >= 3.11`, so **Python 3.10 cannot satisfy the pins; 3.11 or 3.12 is required**
(3.13 wheels exist for most but h5py 3.16.0 / shapely 2.1.2 / pillow 12.3.0 listings I fetched
showed cp310–cp312 only in the first six entries — treat 3.13 as UNVERIFIED). A requires_dist
cross-check of every pin against every other pin found **no conflicts** (osmnx 2.0.7 accepts
pandas 3.0.5, etc.).

## 4. bootstrap.sh — what it must do (concrete)

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
# 0. Interpreter: 3.11 preferred, 3.12 acceptable. 3.10 cannot satisfy the pins.
PY_BASE="${PYTHON:-$(command -v python3.11 || command -v python3.12)}"
"$PY_BASE" -m venv .auto/venv            # .auto/ is git-ignored (uncommitted .gitignore edit)
PY=.auto/venv/bin/python
$PY -m pip install -q --upgrade pip wheel
# 1. Exact pins. Every one has a manylinux x86_64 wheel; no --no-binary, no conda.
$PY -m pip install -q -r requirements.txt
# 2. Package itself, metadata only — pyproject deps would otherwise re-resolve pydantic/tqdm.
$PY -m pip install -q -e . --no-deps
# 3. Undeclared-but-needed: brotli for fontTools/woff2 (tests/test_screen_checks.py).
$PY -m pip install -q brotli
# 4. Optional legacy extra — only if tests/test_spread_v2_xgb.py, test_lfmc_retrieval.py,
#    test_empirical_interaction.py should run rather than importorskip (25 tests). Wheel exists.
$PY -m pip install -q xgboost==3.2.0
# 5. Do NOT `git submodule update` — external/OmniRoute is referenced by nothing.
# 6. No env vars are required. Optional: WFG_FIRMS_DIR (points at a FIRMS bundle if one is
#    ever mounted), WFG_CONFIG (alternate config yaml), WILDFIREGUARDIAN_CACHE_DIR.
#    Never export DEMO_MODE=0, GMAIL_*, TWILIO_* in the sandbox.
# 7. Fallbacks, in order, if step 1 fails on a pin:
#    a) retry once (PyPI transient); b) `pip install -r requirements.txt` with the failing
#       pin relaxed to `>=` and run `scripts/env_check.py --allow-version-drift` — but NEVER
#       relax osmnx (2.0.7 is a scientific pin, docs/ENVIRONMENT.md) and record the drift in
#       .auto/bootstrap.json; c) if the fallback is the pyproject extras, ALSO install
#       fastapi==0.141.1 uvicorn==0.52.1 httpx==0.28.1 — they are in no extra.
# 8. Prove it:
$PY -c "import osmnx, rasterio, geopandas, sklearn, networkx, xarray, h5netcdf, pyproj, shapely, yaml, pytest, fastapi, httpx, brotli"
make verify PYTHON=$PY
$PY scripts/env_check.py            # expected to PASS on pip-Linux (affine 3.0.1 installs)
```

Bootstrap must run while network is available; afterwards nothing needs it. Estimated pip time
2–4 min cold (UNVERIFIED; total wheel download of the geospatial stack is a few hundred MB).

## 5. Tests to deselect in the sandbox (exact)

No marker exists, so use node ids. All 12 are data-absence non-passes, not defects in the code
under test:

```
--deselect tests/test_baseline_freeze.py::test_the_live_tree_matches_the_record \
--deselect tests/test_baseline_freeze.py::test_a_moved_artifact_is_actually_detected \
--deselect tests/test_live_pipeline.py::test_weather_basis_is_derived_from_committed_data_not_a_literal \
--deselect tests/test_osm_cache_isolation.py::test_the_migrated_yeongdeok_cache_is_where_the_loader_looks \
--deselect tests/test_osm_cache_isolation.py::test_migrated_cache_still_matches_the_snapshot_store \
--deselect tests/test_photo_exif.py::test_a_photograph_inside_the_bbox_is_accepted_and_projected \
--deselect tests/test_photo_exif.py::test_a_photograph_outside_the_bbox_gets_the_MAP_CLICK_refusal_verbatim \
--deselect tests/test_photo_exif.py::test_a_photograph_with_no_location_is_200_with_a_verdict_not_a_4xx \
--deselect tests/test_photo_exif.py::test_the_two_sentences_do_not_overwrite_each_other \
--deselect tests/test_photo_exif.py::test_an_unregistered_region_is_404 \
--deselect tests/test_photo_exif.py::test_an_oversized_body_is_413_and_is_refused_on_the_header \
--deselect tests/test_photo_exif.py::test_the_response_carries_the_processing_statement
```

Equivalent `-k` (verify no name collisions before relying on it):
`-k "not (test_the_live_tree_matches_the_record or test_a_moved_artifact_is_actually_detected or test_weather_basis_is_derived_from_committed_data or test_the_migrated_yeongdeok_cache or test_migrated_cache_still_matches or test_a_photograph or test_the_two_sentences_do_not_overwrite or test_an_unregistered_region_is_404 or test_an_oversized_body_is_413 or test_the_response_carries_the_processing_statement)"`

Better than a deselect list (and consistent with the project's own rule that data-dependent
tests self-skip — docs/ENVIRONMENT.md, tests/test_clean_clone_boot.py docstring): the loop's
first code task should add guards — `skipif(not (REPO/"data/raw/firms_data/fire_manifest.json").exists())`
on the two baseline tests and the weather-basis test, `pytest.importorskip`-style
`if not (d/"walk.graphml").exists(): skip` in `test_osm_cache_isolation.py`, and
`pytest.skip` inside the `client` fixture of `test_photo_exif.py` when the yeongdeok DEM is
absent. That is a tests-only change, touches no artifact, and makes README.md:642 true again.

## 6. Expected green baseline in the sandbox

- `make verify`: PASS (9/9 gates).
- `make snapshot-verify`: PASS.
- `make env-check`: expected PASS on pip-Linux (all 24 pins installed exactly) — UNVERIFIED on
  the target; it FAILS on the Mac reference env (affine).
- `make baseline-verify`: **always FAIL** in any clone without the two git-ignored manifests.
  Must be soft/skipped in the sandbox, or the loop must be given the two small JSON manifests
  (sha256 `1aa75824…` and `f2a2266e…`, docs/baseline_phase13.json) as a mounted secret-free
  fixture — they are metadata (bboxes, dates), but §5.9 forbids editing and the test
  `test_the_git_ignored_manifest_has_a_tracked_contract` asserts they stay untracked, so do not
  commit them.
- `pytest` with the 12 deselects: **1067 passed, 41 skipped, 12 deselected** (= 1,120). With the
  guard fix instead: 1067 passed, 53 skipped. With `xgboost` omitted: 25 more skips (importorskip
  in test_spread_v2_xgb / test_lfmc_retrieval / test_empirical_interaction).
- With the full data bundle (never in the sandbox): 1116 passed / 3 skipped / 1 xfailed.

## 7. Audit of the draft loop scaffolding (untracked, created 2026-09-03 12:46–12:48)

Files: `scripts/auto/{bootstrap.sh,gates.py,report.py}`, `.github/workflows/{auto-gates,claude,report-email}.yml`, `.gitignore` (+`.auto/`), empty `docs/auto/{reports,research}/`.

| Item | Problem | Fix |
|---|---|---|
| gates.py `--mode full` | `baseline-verify` is a **hard** step → red forever in a sandbox (§6) | make it `hard=False` off-laptop, or run it only when both manifests exist |
| gates.py `pytest-full` | no deselects → 5F/7E → red forever | add the §5 list, or land the guard fix first |
| bootstrap.sh fallback | `pip install -e ".[geospatial,ml,routing,dev]"` omits fastapi/uvicorn/httpx | add them explicitly |
| bootstrap.sh | no `brotli` | add |
| bootstrap.sh comment | claims pins verified on "Linux x86_64/aarch64 and macOS arm64" — the Mac reference env has affine 2.4.0 and fails env-check; the x86_64 claim is only wheel-existence (§3) | reword |
| auto-gates.yml, claude.yml, report.py | reference `docs/auto/CHARTER.md`, `BACKLOG.md`, `NEEDS_HUMAN.md` — none exist | write them or drop the references |
| claude.yml | `contents: write` + `@claude` on any issue/PR comment = anyone who can comment on the public repo can steer a pushing agent; system prompt says "never push to Main" but the branch protection is prose only | protect `Main` in GitHub settings (require PR); restrict the workflow to `github.event.comment.author_association in (OWNER, MEMBER)` |
| report-email.yml | fine; needs SMTP secrets; skips quietly otherwise | — |
| `.claude/settings.json` rtk hook | rewrites `pytest`/`git`/`pip`… through `rtk` if the binary is on PATH; no-op otherwise | harmless in sandbox; do not install rtk there (it changes gate output the loop reads) |

## 8. Git workflow constraints the routine must respect

Sources: docs/HANDOFF_ROUND3.md §5 (24 items), §6, §7; docs/ENVIRONMENT.md; tests.

1. **Never push to `Main`** (§5.1). §5.1 literally says "all work stays on `round3-dev`"; the draft
   charter moves that to `auto/dev`. The user must ratify the branch name and then **push
   `auto/dev` to origin** — today origin has neither it nor the last 52 commits.
   Work on `auto/<topic>` branches, PR into `auto/dev`; merging to Main is the user's decision.
2. **Never modify a committed artifact** (§5.2): the 4 PROTECTED paths
   (`data/processed/real_roads_real_hazard.json`, `real_roads_real_hazard_slope_60.json`,
   `routing_demo.npz`, `rescue_routing.json` — sha256 `92248e5a…` pinned in
   tests/test_full_coverage.py) plus every one of the 115 tracked `data/processed` files
   (freeze in docs/baseline_phase13.json) and `data/snapshots/*` (MANIFEST.json). New results get
   new filenames. `baseline-freeze` is deliberate only, with the reason in the commit message.
3. **Never regenerate `docs/figures/*.png`** (§5.3; 40 tracked PNG/GIF cited by the submitted
   documents). `make finals` may rebuild `web/finals.html` but only on the geospatial stack and
   it runs `check_screen_assets.py`.
4. **Never edit `data/raw/firms_data/fire_manifest.json`** (§5.9) — and it is not in the sandbox anyway.
5. Never re-acquire Yeongdeok OSM (§5.4), never proceed on a partial Overpass graph (§5.6), never
   write acquired data only to `data/cache/` (§5.8), never mosaic DEM providers (§5.17), never
   re-run the 459 series into a committed filename (§5.18). In practice: **the sandbox should do
   no acquisition at all** — it has no keys and no bundle; any acquisition task is a NEEDS_HUMAN item.
6. Numbers: every reportable number goes through `scripts/build_numbers.py` → docs/NUMBERS.json and
   `make verify` must pass before commit; never pipe a gate (`check_gate_invocations.py`); the
   phrasing prohibitions in §5.5, 5.10–5.16, 5.19–5.24 are enforced by `check_forbidden.py`
   `kind="claim"` rules — run `make verify` after any prose edit.
7. Finals rule (KCF): the work must not contradict the submitted 서식1/서식2 purpose — prose
   changes in README/docs must stay inside that scope.
8. Commit hygiene already in use: one topic per commit, Korean/English summary line, and the
   session report convention `docs/SESSION<N>_REPORT.md`; the loop should write
   `docs/auto/reports/*.md` instead of new SESSION files to avoid confusing the human record.
9. Never commit `.env` (present locally with real keys: FIRMS_MAP_KEY, GMAIL_*, TWILIO_*,
   OPENTOPOGRAPHY_API_KEY, VWORLD_API_KEY, DEMO_*); it is git-ignored and must stay so.

## 9. Secrets / API keys and graceful degradation

`.env.example` is **stale**: it names `NASA_FIRMS_MAP_KEY`, `CDSAPI_URL/KEY`, `KMA_API_KEY`,
`MAPBOX_TOKEN`, `WILDFIREGUARDIAN_CACHE_DIR`, while the code and the real `.env` use different names.

| Variable (as read by code) | Where | Without it |
|---|---|---|
| `FIRMS_MAP_KEY` | `src/wildfireguardian/live/firms.py` | live FIRMS trigger raises its "No MAP_KEY" error; replay mode still works **only if** the detections archive exists (git-ignored) → in the sandbox the live pipeline is replay-from-committed-hazard-field only |
| `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `DEMO_RECIPIENT` | `delivery/email.py` (three locks) | nothing is sent; functions return a refusal record |
| `TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER`, `DEMO_PHONE_NUMBER`, `DEMO_MODE` (default on) | `delivery/sms.py` | `{"sent": False, "reason": "provider credentials absent"}`; twilio never imported |
| `OPENTOPOGRAPHY_API_KEY` | DEM acquisition (`data_io/raster.py` urllib path, scripts) | acquisition scripts stop; tests use tmp_path/synthetic |
| `CDSAPI_*` | `scripts/get_era5.py` only (`acquisition` extra) | not needed to run anything else |
| `VWORLD_API_KEY` | vworld acquisition scripts | not needed |
| `KMA_API_KEY`, `MAPBOX_TOKEN` | grep finds **no reader** in src/scripts | dead entries in .env.example |
| `WFG_FIRMS_DIR`, `WFG_CONFIG`, cache dir env | `spread_v2/data.py`, `config.py`, `data_io/raster.py` | defaults to in-repo paths |
| `SMTP_HOST/USERNAME/PASSWORD`, `REPORT_TO` | draft `scripts/auto/report.py`, report-email.yml | report written to `docs/auto/reports/`, not mailed |
| `ANTHROPIC_API_KEY` | claude.yml | job skipped |

The sandbox needs **no secret** to reach the §6 baseline. Anything that needs one is by
construction out of the loop's reach and should be filed as a human item, never faked.

## 10. Things I could not verify

- Actual `pip install -r requirements.txt` on Linux x86_64 (only wheel presence and metadata
  compatibility were checked from here; an aarch64 install succeeded in Session 18).
- Runtime of the suite and the pip step on a 2-vCPU runner.
- Python 3.13 wheel coverage for h5py/shapely/pillow pins.
- The brotli failure mode in practice (§0.7).
- Whether `docs/auto/CHARTER.md` exists somewhere outside the repo (it is referenced but absent
  from the working tree and from git).

## Sources

- Local: `pyproject.toml`, `requirements.txt`, `Makefile`, `scripts/env_check.py`,
  `scripts/check_declared_deps.py`, `scripts/freeze_baseline.py`, `docs/ENVIRONMENT.md`,
  `docs/HANDOFF_ROUND3.md` §5–§7, `docs/SESSION18_REPORT.md`, `docs/SESSION22_REPORT.md`,
  `docs/baseline_phase13.json`, `tests/*.py`, `.env.example`, `.gitmodules`,
  `scripts/auto/*`, `.github/workflows/*` (untracked drafts).
- Clean-clone pytest log: `/private/tmp/claude-501/-Users-jp-Desktop-Korea-Code-Fair/3b4a7de4-1c3c-48d0-8fd2-c34bf4ae1df9/scratchpad/r8/clone_pytest.log`
- PyPI JSON API, e.g. https://pypi.org/pypi/osmnx/2.0.7/json , https://pypi.org/pypi/numpy/2.4.6/json ,
  https://pypi.org/pypi/xgboost/3.2.0/json (queried 2026-09-03).
- fontTools optional dependencies (Brotli for WOFF2): https://fonttools.readthedocs.io/en/latest/optional.html
- GitHub repo: https://github.com/Sparkxt-0318/wildfireguardian ; submodule: https://github.com/diegosouzapw/OmniRoute.git
