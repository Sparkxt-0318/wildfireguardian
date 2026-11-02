# Reproduce WildfireGuardian on any machine

Two ways to check that the work runs as claimed: Docker on any OS, or native Python 3.12 on Linux or macOS. Neither changes the frozen kit, its thresholds, the recorded results or the Route-Check API's fixed 30 s request budget.

## Evaluated benchmark versus reproduction

- **The benchmark** is the 80-execution comparison. It ran on "the recorded native Darwin arm64 Apple M5 Pro host, 15 cores and 24 GiB RAM, with CPython 3.12.14 and NumPy 1.26.4", under a 30 s complete-request allowance ([independent report](../../research/routing/INDEPENDENT_REPORT.v1.md#exact-candidate-and-evaluation)).
- **A reproduction** runs the same code on the same SHA-256-verified inputs on another host, and checks that it returns the **same journey**. Its timings are not benchmark results. With the unchanged 30 s budget, a slower host can end a heavy mission as `unresolved`/`TIMEOUT`. That is correct behaviour, and unresolved is never reported as safe ([Linux VM report](../../api/reports/LINUX_VM_REPLAY_2026-10-17.md)).
- [`reproduce/replay_uljin_fx1.py`](reproduce/replay_uljin_fx1.py) therefore replays the recorded Uljin FX1 request through `wfg_latest.api.route_and_check(..., budget_s=300)` and labels every output **"Linux reproduction with extended budget — not the evaluated 30 s macOS benchmark"**. `--also-evaluated-budget` runs the same request once more at 30 s and only reports what the host returns.

The replay asserts, against values read from the recorded result files:

- authoritative status `CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN` with a `CERTIFIED_ADMISSIBLE` whole-road check;
- arrival 3,119 s, 512 road legs and the 120 s required stay ([README](../../README.md#2-replay-a-recorded-korean-routing-case));
- the recorded full-policy route hash ([ablation rows](../../research/routing/final-input-ablation/data/ROWS.csv));
- the offline independent checker's `INDEPENDENTLY_CERTIFIED_OPTIMAL` verdict, with no contradiction.

## Option 1: Docker (any OS)

```sh
git clone --branch Main https://github.com/Sparkxt-0318/wildfireguardian.git && cd wildfireguardian
WFG_GIT_COMMIT=$(git rev-parse HEAD) docker compose up --build      # or: make docker-up
```

- **Planner:** <http://127.0.0.1:8080>. For Uiseong–Andong and Yeongdeok it shows the recorded results precomputed on the evaluated host ([planner/cache/INDEX.json](../../planner/cache/INDEX.json)). Other regions and any new check run in the container, on a non-evaluated host; the planner shows the host next to each compute time.
- **API:** <http://127.0.0.1:8765/v1>, with Swagger UI at <http://127.0.0.1:8765/docs>. Both ports are published on 127.0.0.1 only, because "the API has no authentication and is meant for local use only".
- **Network** is needed only while building: base images, Python wheels, npm packages, and the recorded inputs, which the build downloads and SHA-256-verifies with [`tools/fetch_routing_inputs.py`](../../tools/fetch_routing_inputs.py). Nothing is taken from your checkout's `data/`.
- **Inside the container**, the same checks as the native path:

  ```sh
  docker compose run --rm --no-deps api python docs/solve2027/reproduce/replay_uljin_fx1.py --out /tmp/uljin-fx1
  docker compose run --rm --no-deps api python -m pytest tests/api -m "not golden and not panel" -rs -p no:cacheprovider
  ```

- **Stop** with `docker compose down`. Add `-v` to also delete the job records kept in the `api-runtime` volume.

| Image ([Dockerfile](../../Dockerfile)) | Contents |
|---|---|
| `api` | `python:3.12.14-slim-bookworm`, GNU `time` and `procps`, `./integration[packets]` and `api/requirements.txt` with the pinned constraints, the verified recorded inputs, `api/`, the kit, contract and ablation files. It runs as an unprivileged user. |
| `planner` | The planner's production build (`VITE_WFG_API_MODE=real`, recorded cache included), served by `nginxinc/nginx-unprivileged:1.30.6-alpine`. `/api/v1/*` is proxied to the API's `/v1/*` the same way `npm run dev` does it. |

CI builds and runs both images on `linux/amd64` ([workflow](../../.github/workflows/reproduce-linux.yml)). Other architectures are untested.

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

## Time and memory to expect

| What | Evaluated host (recorded) | Other hosts (not benchmark results) |
|---|---|---|
| Uljin FX1 request | `wall_s` 14.532054333001724 and 14.585103332996368 ([INDEPENDENT_ROWS.csv](../../research/routing/INDEPENDENT_ROWS.csv), `RDA_CAND`) | 4-vCPU Linux VM at 30 s: "timed out four times (30.12-30.28 s) and met the budget once (29.94 s, identical to the record)"; at `budget_s=120`: 38.6 s ([report](../../api/reports/LINUX_VM_REPLAY_2026-10-17.md)). 2-vCPU host of the [receipt](#receipt): at 300 s, `CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN` with request wall_s 44.71 (49.20 s including the independent check); at 30 s, `UNRESOLVED` / `LATE_RESULT` after 30.17 s |
| Memory per check | Guard "3072 MiB" ([api/README.md](../../api/README.md#what-it-is)); largest recorded single-process RSS over the campaign 1,492 MiB for the candidate ([README](../../README.md#frozen-october-15-comparison)); Uljin FX1 `family_sampled_mib` 333.109375 and 325.921875 ([INDEPENDENT_ROWS.csv](../../research/routing/INDEPENDENT_ROWS.csv)) | Uljin FX1 at 300 s on the receipt host: sampled family peak RSS 249.2 MiB. Docker needs room for the guard plus the API server itself |
| API fast tests | — | Receipt host: "109 passed, 2 deselected, 1 warning in 108.18s"; largest process 417.7 MiB |
| Planner image build | — | Build steps run natively on the receipt host: `npm run build` 32.76 s, largest process 485.9 MiB, `dist` 183.2 MiB (Node heap capped at 2048 MB in the image). Docker build times depend mostly on downloads; the CI run log gives a reference |

## Receipt

[`reproduce/RECEIPT_2026-11-02_linux_2vcpu.json`](reproduce/RECEIPT_2026-11-02_linux_2vcpu.json) records one run of the whole sequence. It ran on a shared 2-vCPU Linux VM with no swap and no Docker daemon, while other jobs were running ("load_average_during_replay" in its `headline`). It is a non-evaluated host, and its timings are not benchmark results.

- `verify_release.py`, `verify_postmerge_preservation.py` and a fresh `fetch_routing_inputs.py` passed.
- The extended-budget replay passed all assertions ("17/17 passed").
- The API fast tests passed.
- The unchanged README quick path, `integration/examples/run_frozen_case.py`, keeps the evaluated 30 s budget. On this host it returned "UNRESOLVED / LATE_RESULT after 30.17 s, script exit code 2". That is the honest outcome on a slower host, not a different journey. The extended-budget replay shows the journey itself is reproduced.

Docker images were not built on that host. The [workflow](../../.github/workflows/reproduce-linux.yml) builds both images on every pull request to `Main`. It then starts them, checks the planner's static files, cache and `/api/v1` proxy, runs [`scripts/api_smoke.sh`](../../scripts/api_smoke.sh) through the proxy, and repeats the replay inside the API image.
