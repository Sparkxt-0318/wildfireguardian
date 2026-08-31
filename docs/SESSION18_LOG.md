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
