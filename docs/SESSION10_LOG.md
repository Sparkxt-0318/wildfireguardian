# Session 10 — 실행 기록 (Wind downscaling / Front assimilation)

본 문서는 Session 10의 Phase 0 요구사항, 즉 **세션 시작 시점의 정확한 상태**를
기록합니다. 여기 적힌 값은 이후 어떤 단계에서도 수정하지 않습니다.

---

## 0.1 실행 환경 — 이전 세션과 다릅니다

Session 1–9는 사용자의 Apple Silicon Mac에서 conda 환경 `wfg311`
(Python 3.11.15, conda-forge)로 실행되었습니다. **Session 10은 Linux
aarch64 샌드박스에서 실행되었습니다.** 이 차이는 결과 해석에 직접 영향을
주므로 먼저 기록합니다.

| 항목 | 참조 환경 (`wfg311`) | Session 10 실행 환경 |
|---|---|---|
| OS / arch | macOS, Apple Silicon (arm64) | Linux, aarch64 |
| Python | 3.11.15 (conda-forge) | 3.11.16 (python-build-standalone, uv) |
| 이진 스택 | conda-forge GDAL/GEOS/PROJ | PyPI manylinux aarch64 wheel |
| conda / Docker / root | 사용 가능 | **모두 사용 불가** |
| 단일 명령 실행 한도 | 없음 | **약 178초** (초과 시 강제 종료) |

`requirements.txt`의 핀은 **전부 그대로** 설치되었고 `make env-check`는
통과합니다. 즉 버전은 동일하고, 이진 빌드만 다릅니다.

## 0.2 베이스라인 — 6개 게이트 전부 통과

| 게이트 | 결과 |
|---|---|
| `verify_numbers.py` | **PASS** — 154/154 항목이 아티팩트와 일치, 138/154 재현 가능 |
| `check_forbidden.py` | **PASS** — 금지 문구 없음 (기지 3건은 `KNOWN_NEAR_UNLABELLED`에 기록됨) |
| `check_region_literals.py` | **PASS** — 11개 운영자 노출 파일에 새 지역 리터럴 없음 |
| `freeze_baseline.py --check` | **PASS** — 75개 아티팩트 무결, config `36f42903a65f…`, LOFO (151,904 / 2,989) |
| `snapshot_external.py --verify` | **PASS** — 스냅샷 무결 (2건 DIGEST-ONLY ORIGIN DRIFTED, 기존 기록 사항) |
| `env_check.py` | **PASS** — 환경이 `requirements.txt`와 일치 |

### 테스트 스위트 — 1건 실패, 원인 규명 완료

기준선은 `1085 passed / 3 skipped / 0 failed`입니다. 본 환경의 결과는
Phase 7에 최종 기록하며, **재현 결정성 테스트 1건**이 실패합니다.

- 실패: `tests/test_calibration_metrics.py::test_calibration_metrics_regenerates_deterministically`
- 원인: **sklearn `RandomForest` 지표만** 드리프트합니다
  (예: bin 5 `mean_pred` 0.001561 → 0.001578).
- **정규 모델 `hist_gbm`은 비트 단위로 정확히 재현**되며, 데이터셋 형상
  (`n=151,904`, `positives=2,989`, `base_rate=0.019677`)도 정확히 일치합니다.
- 즉 데이터 파이프라인과 보고 대상 모델은 충실하고, RandomForest의
  스레드 누적 순서만 플랫폼에 따라 다릅니다. RandomForest는 보고되는
  모델이 아닙니다 (정규 경로는 `HistGradientBoostingClassifier`).

이 실패는 **환경 드리프트로 분류하여 기록하고 진행**하기로 사용자가
결정했습니다. 저장소 상태의 문제가 아닙니다.

## 0.3 Arm 격리 장치

1. **`arm` 필드.** `docs/NUMBERS.json`의 모든 항목에 `arm` 필드를 부여하고,
   기존 154개 항목을 `"A"`로 백필했습니다. 파일은
   `json.dumps(indent=2, ensure_ascii=False)`로 바이트 단위 왕복이 확인되어,
   변경은 **항목당 한 줄 추가**뿐입니다 (308 insertions / 154 deletions).
2. **Arm별 산출물 루트.** 새 아티팩트는 `data/processed/arms/<ARM>/` 아래에만
   기록합니다. Arm A 경로는 읽기 전용으로 취급합니다.
3. **Arm A 불변성 게이트.** `scripts/check_arm_isolation.py` 가 154개 Arm A
   항목의 sha256을 `docs/arm_a_freeze.json`에 동결하고, 변경·삭제·다른 arm
   으로의 재라벨링·`arm` 필드 누락을 전부 실패로 처리합니다. 새 항목이
   `arm="A"`를 주장하는 것도 실패입니다.

## 0.4 현재 특징 목록 — 정확히 16개

`src/wildfireguardian/spread_v2/features.py::FEATURE_COLUMNS` 순서 그대로:

| # | 이름 | 그룹 |
|---|---|---|
| 1 | `dist_to_fire_m` | state / geometry |
| 2 | `active_frac_1500m` | state / geometry |
| 3 | `active_frac_3000m` | state / geometry |
| 4 | `n_active_adjacent` | state / geometry |
| 5 | `elevation_m` | terrain |
| 6 | `slope_deg` | terrain |
| 7 | `elev_above_source_m` | terrain |
| 8 | `burnable_frac` | fuel |
| 9 | `wind_speed_ms` | fire-weather severity |
| 10 | `temp_c` | fire-weather severity |
| 11 | `rh_pct` | fire-weather severity |
| 12 | `vpd_kpa` | fire-weather severity |
| 13 | `days_since_rain` | fire-weather severity |
| 14 | `precip_24h_mm` | fire-weather severity |
| 15 | `dt_hours` | interval |
| 16 | `wind_alignment` | **direction control** |

`dist_band`(near / mid / far)는 특징이 아니라 평가용 태그입니다.

## 0.5 `wind_alignment`의 정확한 계산식

두 단계로 계산됩니다.

**(1) 바람 단위벡터** — `spread_v2/weather.py`, ERA5 `u10, v10`에서:

```
speed = hypot(u10, v10)
safe  = where(speed > 1e-6, speed, 1.0)
wind_u, wind_v = u10 / safe, v10 / safe        # 바람이 "향하는" 방향의 단위벡터
```

**(2) 셀별 코사인** — `spread_v2/features.py::build_candidate_frame`:

```
dist_cells, (src_r, src_c) = distance_transform_edt(~active, return_indices=True)
east  = (col - src_c) * cell_size_m
north = (src_r - row) * cell_size_m            # row 인덱스는 남쪽으로 증가
norm  = hypot(east, north);  safe = where(norm > 1e-6, norm, 1.0)
ux, uy = east / safe, north / safe
wind_alignment = ux * wind_u + uy * wind_v
```

기록해 둘 두 가지:

- **`wind_alignment`는 진짜 코사인입니다.** `wind_u, wind_v`가 단위벡터이므로
  값은 [-1, 1]이며 풍속과 얽혀 있지 않습니다. 따라서 Arm D의 `obs_alignment`
  (관측된 확산 방향과의 코사인)와 **직접 비교 가능**합니다.
- **기준점은 "가장 가까운 활성 셀"**입니다. 화재 중심이 아니라
  `distance_transform_edt`가 돌려준 최근접 발화 셀에서의 방위각을 씁니다.
- 시각 정합은 최근접 이웃입니다: `WeatherSeries.at(when)`이
  `argmin(|t - when|)`로 ERA5 3시간 스텝 하나를 고릅니다.

## 0.6 LOGO-CV 폴드 정의

`spread_v2/model.py::leave_one_fire_out`:

- **폴드 = 화재 1건.** `fires = sorted(ds["fire_id"].unique())`, 각 폴드마다
  `train = ds[fire_id != held]`, `test = ds[fire_id == held]`.
- **시드 `DEFAULT_SEED = 20250603`** — 분류기 `random_state`이자 순열 중요도
  RNG의 시드.
- 학습 데이터에 두 클래스가 모두 없거나 테스트가 비면 그 폴드는 `None`.
- **순열 중요도는 행 가중 평균**입니다. 폴드별 AUC 감소를 그 폴드의 보류
  행 수로 가중합니다 (최대 화재가 전체 행의 약 54%를 차지하므로 단순
  폴드 평균이 아닙니다).
- 모델: `HistGradientBoostingClassifier(loss="log_loss", learning_rate=0.08,
  max_iter=300, max_leaf_nodes=31, min_samples_leaf=40, l2_regularization=1.0,
  early_stopping=True, validation_fraction=0.15, random_state=seed)`.
  `class_weight="balanced"`는 의도적으로 쓰지 않습니다.

**6개 화재 (폴드 순서 = 알파벳순):**

| 화재 | 행 수 | 양성 | 오버패스 수 | 중앙 간격(h) | 관측 기간(h) |
|---|---:|---:|---:|---:|---:|
| `gangneung_2023` | 396 | 8 | 2 | 2.18 | 2.18 |
| `hongseong_2023` | 3,353 | 34 | 5 | 9.08 | 35.60 |
| `miryang_2022` | 3,019 | 24 | 5 | 15.73 | 60.58 |
| `uiseong_andong_2025` | 82,736 | 1,502 | 19 | 6.44 | 155.23 |
| `uljin_samcheok_2022` | 41,651 | 652 | 27 | 7.78 | 252.10 |
| `yeongdeok_2025` | 20,749 | 769 | 6 | 7.92 | 40.05 |
| **합계** | **151,904** | **2,989** | | | |

`data.list_fires()`는 8건을 돌려주지만 `gangneung_donghae_2022`와
`goseong_2019`는 사용 가능한 전이(transition)가 없어 0행이며, 기존 Arm A와
동일하게 제외됩니다. 합계 (151,904 / 2,989)는
`docs/baseline_phase13.json`의 `lofo_shape`와 정확히 일치합니다.

### 관측 주기에 대한 사실 정정

세션 지시서는 FIRMS 번들이 "하루 4–6회 통과"를 제공한다고 가정했습니다.
원시 탐지 수준에서는 맞을 수 있으나, **모델이 실제로 사용하는 단위**
(`overpass_snapshots(gap_minutes=90)`로 90분 이내 탐지를 하나로 묶은 뒤)에서는
중앙 간격이 **6.4–15.7시간**, 즉 하루 약 **1.5–3.7회**입니다. Arm D가 쓸 수
있는 동화(assimilation) 주기는 지시서의 가정보다 성깁니다.

---

_Session 10 Phase 0 완료. Arm A 아티팩트·숫자·설정 기본값은 변경되지
않았습니다 (`scripts/check_arm_isolation.py`로 검증)._
