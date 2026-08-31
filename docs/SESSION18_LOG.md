# Session 18 로그 — 본선 blockers

작업 기록입니다. 결론과 서술은 `docs/SESSION18_REPORT.md` 에 있습니다.

---

## Phase 0 — 기준선

### 게이트 9개 (파이프 없이 종료 코드 직접 확인)

| 게이트 | 종료 코드 |
|---|---|
| `verify_numbers.py` | 0 — **228/228** |
| `check_forbidden.py` | 0 |
| `check_region_literals.py` | 0 |
| `check_arm_isolation.py` | 0 — 154 Arm A entries unchanged; 74 in other arms |
| `check_gate_invocations.py` | 0 |
| `check_arm_controls.py` | 0 |
| `freeze_baseline.py --check` | 0 |
| `snapshot_external.py --verify` | 0 |
| `env_check.py` | 0 |

### 테스트 — **1,109 passed / 3 skipped / 1 xfailed / 0 failed**

세션 기준선과 동일. ⚠ 샌드박스의 명령당 178초 상한 때문에 60개 테스트
파일을 파일 경계에서 1–20 / 21–40 / 41–60 으로 나누어 돌렸습니다
(313 + 394 + 402 = 1,109). Session 17 과 동일한 절차입니다.

**녹색 확인. Phase 1 로 진행합니다.**

---

## Phase 0 인벤토리 1 — 실행 시점 임포트 그래프

`scripts/check_declared_deps.py` 로 기계적으로 수집했습니다. 선언된 것이
아니라 **실제로 임포트되는 것**을 셉니다: `src`, `scripts`, `tests`, `web`,
`demo`, `config`, `configs` 아래 **273개 `.py`** 를 `ast` 로 파싱하고,
중첩 깊이와 무관하게 모든 `import` / `from ... import` 를 수집하며,
`importlib.import_module("X")` 의 리터럴 인자도 잡습니다.

**표준 라이브러리·자기 자신을 제외한 서드파티 루트 모듈 24개:**

| 모듈 | 임포트 파일 수 | 선언 상태 (Phase 0 시점) |
|---|---:|---|
| `numpy` | 153 | 선언됨 |
| `pyproj` | 39 | 선언됨 |
| `pandas` | 33 | 선언됨 |
| `networkx` | 21 | 선언됨 |
| `matplotlib` | 20 | 선언됨 |
| `rasterio` | 15 | 선언됨 |
| `shapely` | 14 | 선언됨 |
| `scipy` | 13 | 선언됨 |
| `sklearn` | 11 | 선언됨 |
| `osmnx` | 9 | 선언됨 |
| `geopandas` / `PIL` | 6 / 6 | 선언됨 |
| `rich`, `xarray`, `fastapi` | 4 각각 | 선언됨 |
| `xgboost` | 3 | `legacy` extra |
| `yaml` | 2 | 선언됨 (requirements) |
| `pydantic`, `uvicorn` | 1 각각 | 선언됨 |
| `pytest` | 59 | 선언됨 |
| **`affine`** | **3** | **미선언** |
| **`fontTools`** | **2** | **미선언** |
| **`cdsapi`** | **1** | **미선언** |
| **`twilio`** | **1** | **미선언** |

**문자열 디스패치 백엔드 — 임포트 그래프로는 보이지 않는 부류:**

| 호출 | 필요 패키지 | 위치 | 선언 상태 |
|---|---|---|---|
| `engine="h5netcdf"` | **h5netcdf**, **h5py** | `spread_v2/data.py` | **미선언** |
| `engine="netcdf4"` | **netCDF4** | `spread_v2_xgb/era5.py` | **미선언** |

⚠ 이 두 줄이 브리프가 지목한 `h5netcdf` / `h5py` 의 정체입니다. **어떤
import 문에도 이름이 등장하지 않으므로** AST 임포트 순회만으로는 원리적으로
찾을 수 없습니다. `check_declared_deps.py` 가 `engine=` / `driver=` 리터럴을
따로 스캔하는 이유입니다.

## Phase 0 인벤토리 2 — 선언된 의존성 (Phase 0 시점)

- `requirements.txt` — 핀 19개 (`==`), conda-forge 설치 경로가 정본이라고
  명시. `xgboost` 는 주석 처리된 `legacy` extra.
- `pyproject.toml` — `dependencies` 8개(`>=`), extras `geospatial` / `ml` /
  `routing` / `legacy` / `dev`.

**두 파일이 서로 일치하지 않습니다** (Phase 3 충돌 표에 올립니다):

| | requirements.txt | pyproject.toml |
|---|---|---|
| `PyYAML` | 핀 있음 | **없음** |
| `fastapi` / `uvicorn` / `httpx` | 핀 있음 | **없음** |
| `pydantic` / `tqdm` | "0 imports" 라며 **제거** | `dependencies` 에 **있음** |
| `folium` | "0 imports" 라며 제거 | `geospatial` extra 에 **있음** |

⚠ `docs/ENVIRONMENT.md` 의 conda 설치 줄은 `netcdf4` 와 `h5netcdf` 를
**이미 포함**하고 있습니다. 즉 참조 환경에는 있었고 **의존성 파일에만
없었습니다.** 그리고 그 문서의 설치 절차는 `pip install -e . --no-deps` 여서
`pyproject.toml` 의 의존성이 **한 번도 실제로 해석된 적이 없습니다.**
아무도 눈치채지 못한 이유가 이것입니다.

## Phase 0 인벤토리 3 — 문서·NUMBERS 가 인용하는 `data/processed/**`

정규식으로 커밋된 `.md` 를 훑고, `NUMBERS.json` 의 `source_file` 과
`check.operands[*].file` 을 합쳐 실제 존재하는 정규 파일만 남겼습니다.

- **인용된 아티팩트 86개, 합계 12,418,415 B (12.42 MB).**
  이 중 바이너리 5.08 MB (`.csv.gz` 3개, `.npz` 2개).
- **git 추적 중 68개 / 미추적 18개.** 미추적분 합계는 **108,393 B (108 KB)**,
  **전부 텍스트 JSON** 입니다.
- **50 MB 정지-게이트에 걸리지 않습니다. Git LFS 불필요.**

미추적 18개 (Phase 2 의 실제 격차, 전부 Session 10–17 산출):

| bytes | NUMBERS 항목 수 | 경로 |
|---:|---:|---|
| 19,760 | 3 | `data/processed/arms/E/lofo_arm_E.json` |
| 19,616 | 3 | `data/processed/arms/N_noise_control/lofo_arm_N.json` |
| 17,700 | 2 | `data/processed/arms/A_replication_e/lofo_arm_A.json` |
| 14,843 | 0 | `data/processed/vulnerability/ignition_sweep.json` |
| 8,419 | 8 | `data/processed/arms/D/lofo_arm_D.json` |
| 6,090 | 2 | `data/processed/arms/A_replication/lofo_arm_A.json` |
| 5,780 | 4 | `data/processed/vulnerability/tautology_decomposition.json` |
| 2,454 | 2 | `data/processed/vulnerability/horizon_sweep_yeongdeok.json` |
| 2,133 | 1 | `data/processed/vulnerability/portability_paradise_ca_2018.json` |
| 2,044 | 2 | `data/processed/vulnerability/vulnerability_yeongdeok_2025.json` |
| 1,883 | 4 | `data/processed/vulnerability/refuge_distance.json` |
| 1,561 | 2 | `data/processed/vulnerability/hazard_sensitivity.json` |
| 1,466 | 1 | `data/processed/vulnerability/network_matched.json` |
| 1,251 | 1 | `data/processed/vulnerability/network_structure.json` |
| 1,130 | 1 | `data/processed/vulnerability/matched_comparison.json` |
| 995 | 2 | `data/processed/vulnerability/refuge_audit_yeongdeok.json` |
| 801 | 1 | `data/processed/vulnerability/ignition_count_sweep.json` |
| 467 | 1 | `data/processed/vulnerability/warm_start.json` |

**41개 NUMBERS 항목이 저장소에 없는 파일을 가리키고 있었습니다.** 이것이
Phase 2 가 고칠 것입니다.

---

## Phase 1 — 빈 클론 오프라인 부팅

### 수정 전 상태에서 실제로 재현한 실패 (verbatim)

선언된 의존성만으로 설치한 뒤:

```
$ python -c 'import xarray as xr, io; xr.open_dataset(io.BytesIO(...), engine="h5netcdf")'
ModuleNotFoundError: No module named 'h5netcdf'
```

그리고 API 를 lifespan 과 함께 기동했을 때:

```
  File "/tmp/bootclone/src/wildfireguardian/api/app.py", line 110, in lifespan
    state["runner"] = build_runner(regions=regions,
  File "/tmp/bootclone/src/wildfireguardian/service/jobs.py", line 394, in build_runner
    cache.preload(regions, params or RoutingParams.from_config())
  File "/tmp/bootclone/src/wildfireguardian/service/resources.py", line 248, in preload
    _res, cached, entry = self.get(r, params)
  File "/tmp/bootclone/src/wildfireguardian/service/resources.py", line 207, in _load
    raise ResourceError(
wildfireguardian.service.resources.ResourceError: could not load resources for
yeongdeok_2025: RasterioIOError:
/tmp/bootclone/data/raw/firms_data/yeongdeok_2025_dem.tif: No such file or directory
```

⚠ **두 번째 실패는 브리프가 예고하지 않은 것이고, 더 심각합니다.**
`data/raw/` 는 **1.3 GB** 로 저장소에 없는 것이 정상인데, 그 부재가
**서비스 전체 기동을 죽였습니다.** 콘솔과 `/field` 는 완성된 HTML 이라 지역
데이터를 전혀 읽지 않는데도 **띄울 수가 없었습니다.**

⚠ 그리고 첫 수정 시도가 틀렸습니다. `except ResourceError` 만 잡도록 썼는데,
없는 지역은 DEM 보다 먼저 `check_npz` 에서 **`ParameterError`** 로 실패합니다.
`_MISSING_INPUT_ERRORS` 가 한 클래스가 아니라 계열
`(ResourceError, ParameterError, OSError)` 을 열거하는 이유입니다. 그 밖의
타입은 여전히 기동을 중단시킵니다 — 예상 밖 예외는 누락이 아니라 버그입니다.

### 수정 후 — 부팅 전문 (verbatim)

```
############ CLEAN-CLONE OFFLINE BOOT — Session 18 ############
### host: Linux aarch64   date: 2026-08-31T00:29:43Z

$ git clone <repo> /tmp/bootclone2
HEAD: 86203f1 phase 1: declare seven runtime imports, and stop a missing data
              bundle from killing boot

$ python3.11 -m venv .venv   [uv venv, same result]
  Using CPython 3.11.16
  Creating virtual environment at: /tmp/bootvenv2

$ pip install -r requirements.txt
   + threadpoolctl==3.6.0
   + typing-extensions==4.16.0
   + typing-inspection==0.4.4
   + urllib3==2.7.0
   + uvicorn==0.52.1
   + xarray==2026.7.0
  exit=0

$ pip install -e . --no-deps
  Installed 1 package in 0.48ms
   + wildfireguardian==0.1.0a0 (from file:///tmp/bootclone2)
  exit=0

### the four packages that were undeclared before this session
  affine       == 3.0.1
  h5netcdf     == 1.8.1
  h5py         == 3.16.0
  fonttools    == 4.63.0
  netCDF4      ABSENT (optional group, not core)
  cdsapi       ABSENT (optional group, not core)
  twilio       ABSENT (optional group, not core)

### data bundle deliberately ABSENT:
  data/raw/ present but empty (.gitkeep only)
  clone size: 307M

############ part 2 — the demo path (no data bundle) ############
$ python scripts/build_console.py
  exit=0
    -> web/console.html  (158.5 KiB, 3 regions inline)

$ python scripts/build_field_view.py
  exit=0
  [1/3] building REAL scenario (arm-B networks; synthetic hazard) ...
  [3/3] wrote web/field_view.html  {"mission_home_node": 11976273345,
        "margin_minutes": 13.03, "trigger_cells": 32, "front_slice_min": 0.0}

############ part 2b — served with OUTBOUND NETWORK BLOCKED ############
  network blocked: getaddrinfo, create_connection, non-loopback connect()
  GET /api/health   -> HTTP 200
     preloaded_regions      : []
     preload_failed_regions : ['yeongdeok_2025', 'uiseong_andong_2025',
                               'uljin_samcheok_2022']
  GET /               -> HTTP 200   162347 bytes
  GET /field          -> HTTP 200   144906 bytes
  GET /console.html   -> HTTP 200   162347 bytes
  GET /api/regions    -> HTTP 200      522 bytes
     external http refs in /       : 0 []
     external http refs in /field  : 0 []
  NO OUTBOUND CONNECTION WAS MADE — any attempt raises OSError above.

############ part 3 — gates a judge can run on the bare clone ############
  scripts/check_declared_deps.py  exit=0  :: OK — 24 third-party modules
                                              imported across 274 files;
                                              all declared.
  scripts/env_check.py            exit=0  :: OK — the environment matches
                                              requirements.txt.
############ BOOT TRANSCRIPT COMPLETE ############
```

### 오프라인 검증 방법에 대한 정직한 기록

네트워크 차단은 **DNS(`getaddrinfo`, `gethostbyname`), `create_connection`,
그리고 루프백이 아닌 주소로의 `socket.connect`** 를 예외로 만들어 구현했습니다.
`socket.socketpair()` 는 허용합니다 — **첫 시도에서 `socket.socket` 자체를
막았다가 asyncio 이벤트 루프가 자기 self-pipe 를 만들지 못해 실패했고**, 그것은
네트워크와 무관한 이유로 테스트가 깨진 것이었습니다.

⚠ **이것은 진짜 에어갭이 아니라 프로세스 내부 차단입니다.** 파이썬 소켓
계층을 우회하는 호출(예: 서브프로세스, C 확장이 직접 여는 소켓)은 이 방법으로
잡히지 않습니다. 함께 확인한 것은 **서빙된 HTML 안의 절대 http(s) 참조가
0건**이라는 정적 사실이며, 두 증거는 서로 다른 종류입니다.
