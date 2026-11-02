# Reproduce WildfireGuardian on any machine

Two ways to check that the work runs as claimed: Docker on any OS, or native Python 3.12 on Linux or macOS. Neither changes the frozen kit, its thresholds, the recorded results or the Route-Check API's fixed 30 s request budget.

## Evaluated benchmark versus reproduction

- **The benchmark** is the 80-execution comparison. It ran on "the recorded native Darwin arm64 Apple M5 Pro host, 15 cores and 24 GiB RAM, with CPython 3.12.14 and NumPy 1.26.4", under a 30 s complete-request allowance ([independent report](../../research/routing/INDEPENDENT_REPORT.v1.md#exact-candidate-and-evaluation)).
- **A reproduction** runs the same code on the same SHA-256-verified inputs on another host, and checks that it returns the **same journey**. Its timings are not benchmark results. With the unchanged 30 s budget, a slower host can end a heavy mission as `unresolved`/`TIMEOUT`. That is correct behaviour, and unresolved is never reported as safe ([Linux VM report](../../api/reports/LINUX_VM_REPLAY_2026-10-17.md)).
- [`reproduce/replay_uljin_fx1.py`](reproduce/replay_uljin_fx1.py) therefore replays the recorded Uljin FX1 request through `wfg_latest.api.route_and_check(..., budget_s=300)` and labels every output **"Linux reproduction with extended budget — not the evaluated 30 s macOS benchmark"**. `--also-evaluated-budget` runs the same request once more at 30 s and only reports what the host returns.

Before anything runs, three **input checks** confirm that the recorded result files agree with each other and with the documented values, that the request requires the 120 s stay, and that the imported `wfg_latest` is the reviewed copy in `integration/src`. Sixteen **result checks** then compare the replay with values read from the recorded result files:

- authoritative status `CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN`, with a `CERTIFIED_ADMISSIBLE` whole-road check, on-time publication and clean process cleanup;
- arrival 3,119 s, 512 road legs, the request's destination and the 120 s required stay ([README](../../README.md#2-replay-a-recorded-korean-routing-case));
- the recorded full-policy route hash ([ablation rows](../../research/routing/final-input-ablation/data/ROWS.csv));
- the offline independent checker: completed, same trajectory, whole-road contact `CLEAR`, `INDEPENDENTLY_CERTIFIED_OPTIMAL`, no contradiction.

## Replay outcomes

| Exit code | `outcome` in `REPRODUCTION_SUMMARY.json` | When | In CI |
|---|---|---|---|
| 0 | `REPRODUCED` | All 16 result checks pass | passes |
| 3 | `SAME_ROUTE_OPTIMALITY_PROOF_UNFINISHED`, printed as "SAME ROUTE REPRODUCED — optimality proof not finished within the kit's 6 s stage-Z cap (host load)" | Only the status check fails: the status is `CHECKED_JOURNEY_FEASIBLE` or `CHECKED_JOURNEY_CENTRE_OPTIMUM`, the worker's own record shows stage Z timed out at its cap, and no optimality certificate was issued. Route hash, arrival, legs, destination, the whole-road check and the independent checker's optimality certificate all match | passes, with a warning annotation |
| 1 | `NOT_REPRODUCED` | Any other failed result check | fails |
| 2 | `NOTHING_RUN` | A prerequisite is missing or an input check failed | fails |

**Why exit 3 exists.** The frozen worker gives stage Z, the contact-only lattice relaxation whose lower bound backs the optimality proof, at most "min(remaining - 3, 6)" seconds, whatever the request budget (`ALLOCATION` in [rda_worker_v1_1.py](../../integration/kit/phaseB/rda_worker_v1_1.py)). A longer budget therefore cannot remove every effect of host speed. If the cap passes after stage Z has found and contact-checked its route, Z returns `TIMEOUT` with reason `WALL_CLOCK_AFTER_CHECK` and that route as its incumbent ([zsweep.py](../../integration/kit/phaseB/zsweep.py)). The worker whole-road-checks the incumbent and publishes it at once, with no completed lower bound, so the status is `CHECKED_JOURNEY_FEASIBLE`. If the cap passes before Z has found a route (reason `WALL_CLOCK`), stage LO can still complete the lower bound and the proof. The kit is not changed.

On the [receipt](#receipt) host the replay was also run with its process tree limited to a share of one CPU (a cgroup CPU quota, emulating a loaded host). With 48% of one CPU, stage Z stopped after 6.22 s with `WALL_CLOCK_AFTER_CHECK`, the status was `CHECKED_JOURNEY_FEASIBLE` and the replay exited 3, with the recorded route hash and 15 of the 16 result checks. With 35%, stage Z stopped after 6.04 s with `WALL_CLOCK`, before it had found a route; stage LO then completed the lower bound, and the replay exited 0 with all 16. Without a quota (load average 3.54 at the start) stage Z completed in 5.09 s and the replay exited 0. Later, with the host's load average at 7.76 from other jobs and no quota, the replay in the image-layout copy (below) exited 3 the same way, stage Z stopping after 7.62 s with `WALL_CLOCK_AFTER_CHECK`.

**CI decision.** Exit 3 passes with a warning annotation, because the journey itself is reproduced and only the kit's own proof was cut short by a fixed cap that a reproduction must not change. Exit 1 and 2 fail the job. `make reproduce-uljin` and `make reproduce-linux` print the same warning and continue.

## Option 1: Docker (any OS)

```sh
git clone --branch Main https://github.com/Sparkxt-0318/wildfireguardian.git && cd wildfireguardian
WFG_GIT_COMMIT=$(git rev-parse HEAD) docker compose up --build      # or: make docker-up
```

`WFG_GIT_COMMIT` puts the commit into every API response's provenance (the image has no `.git`); without it the commit is recorded as `unknown`. `docker compose up` starts the two services only; it does not run the replay or the tests.

- **Planner:** <http://127.0.0.1:8080>. For Uiseong–Andong and Yeongdeok it shows precomputed results from a host that [planner/cache/INDEX.json](../../planner/cache/INDEX.json) records as `macOS-27.0.1-arm64-arm-64bit`, 15 CPUs, Python 3.12.1, purpose `booth`, live API. Other regions and any new check run in the container, on a non-evaluated host; the planner shows the host next to each compute time.
- **API:** <http://127.0.0.1:8765/v1>, with Swagger UI at <http://127.0.0.1:8765/docs>. Both ports are published on 127.0.0.1 only, because "the API has no authentication and is meant for local use only".
- **Network** is needed only while building: base images, Python wheels, npm packages, and the recorded inputs, which the build downloads and SHA-256-verifies with [`tools/fetch_routing_inputs.py`](../../tools/fetch_routing_inputs.py). Nothing is taken from your checkout's `data/`.
- **Inside the container**, the same checks as the native path. The replay writes to a folder you mount, as your own user:

  ```sh
  mkdir -p out
  docker compose run --rm --no-deps --user "$(id -u):$(id -g)" -v "$PWD/out:/out" api \
    python docs/solve2027/reproduce/replay_uljin_fx1.py --out /out/uljin-fx1
  docker compose run --rm --no-deps api python -m pytest tests/api -m "not golden and not panel" -rs -p no:cacheprovider
  ```

- **Stop** with `docker compose down`. Add `-v` to also delete the job records kept in the `api-runtime` volume.

| Image ([Dockerfile](../../Dockerfile)) | Contents |
|---|---|
| `api` | `python:3.12.14-slim-bookworm`, GNU `time`, `procps` and `git` (the provenance tests create throwaway repositories), `./integration[packets]` and `api/requirements.txt` with the pinned constraints, the verified recorded inputs, `api/`, the kit, contract and ablation files, `tests/api` and the replay script. It runs as an unprivileged user. |
| `planner` | The planner's production build (`VITE_WFG_API_MODE=real`, `VITE_BASE_PATH=/`, recorded cache included), served by `nginxinc/nginx-unprivileged:1.30.6-alpine`. `/api/v1/*` is proxied to the API's `/v1/*` the same way `npm run dev` does it. |

Base images are pinned by digest. The host that produced the [receipt](#receipt) has no Docker daemon. On GitHub Actions, the [CI workflow](#ci-workflow) built and ran both images on `linux/amd64` for commit `2b1d54d1` ([run](https://github.com/Sparkxt-0318/wildfireguardian/actions/runs/41494735774)): image build, health checks, the planner's files, cache and proxy, `scripts/api_smoke.sh`, the in-image API tests and the in-image replay all passed. Other architectures are untested.

## Option 2: native Python 3.12 (Linux or macOS)

```sh
python3.12 -m venv .venv && source .venv/bin/activate
python -m pip install -c constraints-routing.txt './integration[packets]' -r api/requirements.txt
sudo apt-get install time procps        # Linux only: the kit controller measures every request with GNU time and ps
python tools/verify_release.py
python tools/verify_postmerge_preservation.py
python tools/fetch_routing_inputs.py
python docs/solve2027/reproduce/replay_uljin_fx1.py --out artifacts/solve2027/uljin-fx1 --also-evaluated-budget
python -m pytest tests/api -m "not golden and not panel" -rs
```

`make reproduce-linux` runs the same sequence. The root README's quick path does not list GNU `time`, but the [Makefile](../../Makefile) warns that "every route check will fail without it". The replay script stops with a clear message instead.

One fast test, `test_route_check_lifecycle_and_exports` in [tests/api/test_contract_data.py](../../tests/api/test_contract_data.py), runs the recorded Hongseong FD1 check through the API at the fixed 30 s budget and expects `checked_route`. On a slow or heavily loaded host that check can end `unresolved`/`TIMEOUT` and fail the test. That is the documented host-speed behaviour, not a different answer; rerun it on an idle machine.

## Time and memory to expect

| What | Evaluated host (recorded) | Other hosts (not benchmark results) |
|---|---|---|
| Uljin FX1 request | `wall_s` 14.532054333001724 and 14.585103332996368 ([INDEPENDENT_ROWS.csv](../../research/routing/INDEPENDENT_ROWS.csv), `RDA_CAND`) | 4-vCPU Linux VM at 30 s: "timed out four times (30.12-30.28 s) and met the budget once (29.94 s, identical to the record)"; at `budget_s=120`: 38.6 s ([report](../../api/reports/LINUX_VM_REPLAY_2026-10-17.md)). Receipt host: at 300 s, `CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN` with request wall_s 48.57 (54.74 s including the independent check); at 30 s, `UNRESOLVED` / `LATE_RESULT` after 30.12 s |
| Memory per check | Guard "3072 MiB" ([api/README.md](../../api/README.md#what-it-is)); largest recorded single-process RSS over the campaign 1,492 MiB for the candidate ([README](../../README.md#frozen-october-15-comparison)); Uljin FX1 `family_sampled_mib` 333.109375 and 325.921875 ([INDEPENDENT_ROWS.csv](../../research/routing/INDEPENDENT_ROWS.csv)) | Uljin FX1 at 300 s on the receipt host: sampled family peak RSS 227.4 MiB |
| API container memory | — | Not measured in Docker. Natively, in a copy of the API image's files, the API server's process tree used 348.0 MiB idle and at most 453.0 MiB (summed RSS) while `scripts/api_smoke.sh` ran its two checks one at a time ([receipt](#receipt)). Each check that runs at the same time (`WFG_API_WORKERS`, "physical cores − 2 (minimum 1)") can use up to the 3072 MiB guard |
| API fast tests | — | Receipt host: load average 5.57 rising to 7.94: "1 failed, 108 passed, 2 deselected, 1 warning in 185.03s (0:03:05)", largest process 418.4 MiB. The failure is the timing-sensitive FD1 test above ([receipt](#receipt)) |
| Planner image build | — | Build steps run natively on the receipt host: `npm run build` 85.57 s, largest process 492.8 MiB, `dist` 183.2 MiB (Node heap capped at 2048 MB in the image). Docker build times depend mostly on downloads |

## Receipt

[`reproduce/RECEIPT_2026-11-02_linux_2vcpu.json`](reproduce/RECEIPT_2026-11-02_linux_2vcpu.json) records one run of the whole sequence. It ran on a shared 2-vCPU Linux VM with no swap and no Docker daemon, while other jobs were running (load averages per step in `steps`). It is a non-evaluated host, and its timings are not benchmark results. It ran at commit `95b48f65`; the commits after it change only documentation, this receipt and a comment in the workflow.

- `verify_release.py`, `verify_postmerge_preservation.py` and a fresh `fetch_routing_inputs.py` passed.
- The extended-budget replay gave "REPRODUCED, exit 0; input checks 3/3, result checks 16/16". Under a CPU quota it exited 3 at 48% and 0 at 35% ([replay outcomes](#replay-outcomes)).
- The unchanged README quick path, `integration/examples/run_frozen_case.py`, keeps the evaluated 30 s budget. On this host it returned "UNRESOLVED / LATE_RESULT after 30.22 s, script exit code 2". That is the honest outcome on a slower host, not a different journey; the extended-budget replay shows the journey itself is reproduced.
- The API fast tests ran while the load average rose from 5.57 to 7.94: "1 failed, 108 passed, 2 deselected, 1 warning in 185.03s (0:03:05)". A rerun on the same commit named the failure, `test_route_check_lifecycle_and_exports`: its Hongseong FD1 check at the fixed 30 s budget ended `unresolved` / `TIMEOUT` ("1 failed, 108 passed, 2 deselected, 1 warning in 160.58s (0:02:40)"). This is the timing-sensitive test described [above](#option-2-native-python-312-linux-or-macos). On the 4-vCPU VM of the [Linux VM report](../../api/reports/LINUX_VM_REPLAY_2026-10-17.md) the same mission's `compute_s` was 14.66 s and 15.93 s.
- In a daemon-free copy of the API image's files (`api_image_layout_simulation`: what the `api` stage copies, the same pinned packages and a fresh input fetch, without `.git`), `tests/api/test_provenance.py` gave "3 passed in 0.92s" with git, which the image now installs, and "3 failed in 3.03s" without it. The full fast suite gave "1 failed, 108 passed, 2 deselected, 1 warning in 210.41s (0:03:30)"; the receipt names the failing test only for the later rerun, where it was the timing-sensitive FD1 test. No step wrote a file inside the copy outside `artifacts/`. The replay, writing to a folder outside the copy, took the commit from `WFG_API_GIT_COMMIT` and exited 3 at a load average of 7.76 ([above](#replay-outcomes)). `/v1/health` reported `ok`, and `scripts/api_smoke.sh` finished both jobs.
- The planner image's build steps ran natively in a copy of its build context: `npm ci`, then `npm run build` (85.57 s while the load average was 9.3 at the start).

Docker was not available on this host, so the images themselves were not built ([CI workflow](#ci-workflow)).

## CI workflow

[`reproduce-linux.yml`](../../.github/workflows/reproduce-linux.yml) runs on pushes and pull requests to `Main` that change a file the two jobs use (the `paths:` lists: the Docker files, `api/`, `integration/`, `planner/`, their tests, the inputs tool, the replay script and the files they read), and on manual dispatch (`workflow_dispatch`). One job repeats Option 2 on a GitHub-hosted Linux runner. The other job is configured to build both images (nothing is pushed), start them, check the planner's static files, cache and `/api/v1` proxy, run [`scripts/api_smoke.sh`](../../scripts/api_smoke.sh) through the proxy, and run the API fast tests and the replay inside the API image. It records the commit under test, for a pull request its head commit, in API provenance. Both jobs keep the replay's `REPRODUCTION_SUMMARY.json` as an artifact.
