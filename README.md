# WildfireGuardian

> Wildfire spread forecasting and household-level evacuation and rescue routing,
> focused on protecting rural elderly Koreans.
>
> 공개 데이터 기반 산불 확산 예측을 활용한 고령자 등 이동 취약 주민의 구조 우선순위 및 안전 이동경로 산정 연구

![status](https://img.shields.io/badge/status-research%20PoC-orange)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## TL;DR

- **Current model (Build B — `spread_v2`)**: a data-driven, per-cell wildfire
  ignition-probability model (gradient-boosted trees) validated by
  **leave-one-group-out cross-validation (LOGO-CV, group = fire)** on **six real
  Korean wildfires**.
  **Mean-of-folds ROC-AUC = 0.89** (range 0.68–0.97; pooled out-of-fold 0.905).
- **Headline result**: the calibrated `P(ignite)` surface is coupled into
  **elderly-aware and rescue-aware evacuation routing** — the project's core
  systems contribution. On the canonical Yeongdeok field, **42 of 458** scanned
  origins reach a refuge **only** when the router accounts for where the fire
  will be, and **2** reach no refuge under that policy
  ([Round 3](#round-3-2026-08); the 32.6 % coverage caveat applies).
  ⚠ **That contrast is measured against a fire-blind baseline**
  (`src/wildfireguardian/routing/evacuation.py:270`, "fire-blind shortest path to
  the nearest shelter"), **so it does not separate knowing where the fire will be
  from knowing where it is** — the manuscript's own wording
  ([`paper/manuscript.md`](paper/manuscript.md), Abstract). The fair opponent that
  would separate them, a plan that refuses only what is burning now, has been run
  on 의성·안동 ([`docs/present_perimeter_arm.md`](docs/present_perimeter_arm.md))
  and, since 2026-09-11, on 영덕 too
  ([`docs/present_perimeter_yeongdeok.md`](docs/present_perimeter_yeongdeok.md));
  neither re-grades the 42, whose control is still the fire-blind one, and
  neither count is restated here; both pages carry their own.
  ⚠ **And the forecast-aware arm is graded on the very field it planned on.** That
  field is not truth: the router plans on a **leave-one-fire-out** forward
  simulation — a model output on a fire the model never trained on — while the
  observed FIRMS footprint committed beside it in the same file scores nothing.
  **The oracle is in the grading, not in the planning**, so the arm cannot be wrong
  about the array that grades it, and 42 is what this policy buys **when its own
  prediction is believed** rather than what a *noiseless* forecast would buy. How
  far that prediction sits from the observation is counted cell by cell in
  [`docs/oracle_gap.md`](docs/oracle_gap.md), whose §7 states what that measurement
  does **not** show and whose §6 is the re-grading that would measure the real
  margin and has not been run. Whether this also makes 42 an **upper bound** on the
  real margin is an open question rather than a result: nothing in this repository
  derives it, and it is asked of the author as **NH-053**
  ([`paper/manuscript.md`](paper/manuscript.md) §4.5;
  [`docs/present_perimeter_arm.md`](docs/present_perimeter_arm.md) §5 says the
  same of the 의성 margin and calls it "a property the 91 has always had,
  inherited not introduced").
- ⚠ **A claim that used to stand here has been withdrawn.** Earlier versions led
  with "fire-weather severity dominates wind direction by ~44× in permutation
  importance". That ratio compares a **six-feature sum** against a **single
  variable**, and ERA5's 0.25° (~28 km) grid does not resolve the local winds the
  comparison is about. It is **not established** and must not be read as "wind
  direction does not matter". The measurement itself is retained, with its
  limits, in [Current model & results](#current-model--results-build-b--spread_v2).
- **Intellectual-honesty record**: an earlier Rothermel-based *physics* model
  captured only **~9 %** of the burned area (a documented moisture-conflation
  bug), which **motivated the pivot** to this data-driven model. That history is
  preserved below in **[Research log / superseded approaches](#research-log--superseded-approaches-physics-model)**
  — it is no longer the current state.

- **개발 일정과 역할**: 이 저장소의 개발은 **다섯 구간**으로 나뉘어 있고, 각 구간의
  기간·커밋 수·활동일 수와 1인 참가자의 역할 서술은
  [`docs/auto/finals/TIMELINE_ROLES.md`](docs/auto/finals/TIMELINE_ROLES.md) 가 스스로
  적습니다(그 문서가 자기 기준 시각을 함께 적으므로 여기에 옮겨 적지 않습니다).
  ⚠ **계획서가 아니라 기록입니다** — 미리 세운 일정이 아니라 끝난 뒤 `git log` 에서
  되짚어 만든 것이고, 그 점이 이 문서의 강점이자 한계입니다.

> **Canonical source of truth for every number below:** [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md)
> and [`data/processed/spread_v2_lofo.json`](data/processed/spread_v2_lofo.json).
> No model code, results, or numbers were changed to write this README.

## Round 2 결과 (2026-07)

> ⚠ **이 절은 제출 시점(2026-07)의 기록입니다.** 아래 첫 항목의 459 계열 수치는
> Round 3 에서 **자료 결함을 정정한 뒤 재산출**되었습니다. 현행 값은
> [Round 3](#round-3-2026-08) 을 보십시오. 제출 시점 상태 전체는 태그
> **`round2-submitted`** (`4e9dfe3`) 로 그대로 접근할 수 있습니다.

- 실제 OSM 도로 + 실자료 기반 예측 위험면 통합 주사 **459곳** — **438 / 18 / 3**, 분할 완전, 나머지 세 범주 **0곳** 실측. ⚠ **정본 위험면 재산출 후 458곳 — 414 / 42 / 2** ([Round 3](#round-3-2026-08)) → [`docs/real_roads_real_hazard.md`](docs/real_roads_real_hazard.md)
- 실자료 기반 위험면 위 라우팅 주사 **407곳** — **240 / 56 / 88 / 0** (분류 384) → [`docs/REPORT_ROUND2_P1.md`](docs/REPORT_ROUND2_P1.md)
- 예측 오차 하 경로 강건성 — 미래 인지 경로의 노출이 더 낮은 경우 **86 %**, 공간 오차 **125–530 m**에서 파단 → [`docs/forecast_robustness.md`](docs/forecast_robustness.md)
- 형태학적 팽창 교란 — 약 **122 m**에서 파단하며 공간 이동 축과 동일 거리 → [`docs/dilation_perturbation.md`](docs/dilation_perturbation.md)
- 취득 파라미터 문서화 — [`docs/data_provenance/`](docs/data_provenance/) (6개 화재 매니페스트 + 5개 화재 취득 기록)
- 재현성 실측 — 도로망 재취득 시 출발지 **439→441**, 도달 불가 **24→32 (+33 %)**; 짝지어진 노출 대비는 **0.56 %p**만 이동(이진 판정은 망에 민감, 대비는 강건). 그래프 스냅샷 미보존이 원인이며 한계로 기록 → [`docs/network_drift.md`](docs/network_drift.md) *(이전 판이 여기 인용한 보행 실패율 변화 수치는 근거 산출물이 저장소에 없어 제거)*

---

## Round 3 (2026-08)

Round 3 은 새 기능을 얹기 전에 **기존 수치가 아직 참인지 확인할 수 있는 층**을
먼저 만들었고, 그 층이 곧바로 자료 결함 하나를 찾아냈습니다.

> ⚠ **읽는 법.** 아래는 "제출본이 틀렸다"가 아닙니다. **자료 결함을 정정한 뒤
> 재산출한 값**이며, 바뀐 세 수치는 모두 **제출본이 결과를 과소평가하고 있었음**을
> 뜻합니다. 제출 시점 상태는 태그 **`round2-submitted`** (`4e9dfe3`) 로 그대로
> 접근할 수 있고, 무엇이 왜 바뀌었는지는
> [`docs/HANDOFF_ROUND3.md`](docs/HANDOFF_ROUND3.md) §2-A 에 있습니다.

### 1. 정본(canonical) 위험면 전환

`uljin_samcheok_2022` 의 DEM 이 **동해를 −497 m 까지 내려가는 경사면으로 메우고
있었고**(래스터의 49 %), 모델은 6개 산불 **하나의 공유 데이터셋**에서 leave-one-fire-out
으로 학습하므로 그 허구가 **모든 폴드의 학습 자료**였습니다. DEM 을 재취득해
측정하는 과정에서 두 번째 문제가 드러났습니다 — `routing_demo.npz` 는 **다음 날
되돌려진(reverted) 실행의 산출물**이었고, 그 아래 모든 수치가 아무도 선택하지 않은
위험면 위에서 측정돼 있었습니다.

정본 위험면 위에서 재산출한 결과 (영덕 459 계열):

| | 제출본 | 정본 재산출 | 방향 |
|---|---:|---:|---|
| 3-구분 counts | 440 / 17 / 3 | **414 / 42 / 2** | — |
| 미래 인지 경로로만 안전 | 17곳 | **42곳** | ⚠ **과소평가였음** |
| 미래 인지 전용 비율 | 3.70 % | **9.17 %** | ⚠ **과소평가였음** |
| 화선 핵심 성장 | +1.2 % | **+316.1 %** | ⚠ **과소평가였음** |

「준정적 핵심(quasi-static core)」이라는 한계 기술은 **화재의 성질이 아니라 되돌려진
위험면의 성질**이었습니다. **헤드라인 AUC 는 영향을 받지 않습니다** — DEM 정정은
폴드평균을 **+0.0048**, pooled 를 **−0.0017** 움직입니다
([`data/processed/spread_v2_lofo_dem_corrected.json`](data/processed/spread_v2_lofo_dem_corrected.json)).
그 재실행은 커밋된 산출물을 **대체하지 않았고**, 제출본이 인용하는 수치를 보존하기
위해 별도 파일로 둡니다. **439 계열(439/167/24)은 다른 파이프라인·다른 분모이므로
영향 없음**입니다.

### 2. 다지역 — 3곳

동일 규칙·동일 파라미터로 3개 지역을 취득·모의·라우팅했습니다.

| 지역 | 주사 출발지 | 3-구분 | 보행망 커버리지 | 차고지 |
|---|---:|---|---:|---:|
| 영덕 2025 | 458 | 414 / 42 / 2 | **32.6 %** | 4 |
| 의성·안동 2025 | 368 | 263 / 91 / 12 | **99.2 %** | **0** |
| 울진·삼척 2022 | 393 | 377 / 3 / 10 | **81.5 %** | 4 |

⚠ **세 지역을 이 표로 순위 매기지 마십시오.** n = 3 이고 커버리지·핵심 성장·포락면적이
함께 움직입니다 ([`docs/multi_region.md`](docs/multi_region.md) §8). 영덕의 절대 비율은
모두 **커버리지 32.6 %** 위의 값입니다.

⚠ **3-구분을 더해도 주사 출발지와 일치하지 않는 지역이 있습니다** — 의성·안동
263+91+12=366≠368, 울진·삼척 377+3+10=390≠393. 차이는 이 표가 생략한 넷째 버킷
**예산 초과(`fa_exceeds_budget`)** 각 2곳·3곳입니다(영덕은 0). 완전한 분할은
[`docs/multi_region.md`](docs/multi_region.md) §3 표에 있습니다.
⚠ **이 두 수는 두 팔에 서로 다른 시간 규칙을 적용해 잰 값입니다** — 예보 없는 팔에는
예산이 걸려 있지 않습니다. 한 규칙으로 다시 재면 의성·안동 쪽은 **비어 있고**,
울진·삼척 쪽은 아직 다시 재지 않았습니다
([`docs/multi_region.md`](docs/multi_region.md) §3.1).

⚠ **의성·안동은 919 km² 보행 bbox 안에 OSM 에 매핑된 `amenity=fire_station` 이 없어**
구조자 측 산출이 불가합니다(더 넓은 3,926 km² 범위에는 6곳). 「소방서가 없다」가
**아니라** OSM 매핑의 성질이며, 산출물은 이를 *0건*이 아니라 *해당 없음*으로 기록합니다.

### 3. 다지역 확장이 실제로 찾아낸 것 — 지역 리터럴 결함 3건

같은 결함을 **세 파일에서 세 번** 만났고, **셋 다 같은 형태**입니다: 지역별이어야 할
값이 **한 지역의 값으로 박혀 있고, 그 지역에서는 우연히 맞습니다.**

| # | 위치 | 증상 |
|---|---|---|
| 1 | 콘솔 빌더 | 커버리지가 리터럴 `32.6` — 지역 전환이 가능해지는 순간 나머지 둘에 대해 틀림 |
| 2 | 화면 생성기 범례 | **시연 화면이 32.6 %와 99.2 %를 동시에 표시** |
| 3 | 캐비엇 상수 | 영덕 이름과 32.6 %가 **273장의 A4 출동 시트**에 인쇄됨. 두 지역 모두 자기 커버리지가 시트에 없었음 |

⚠ **단일 지역 검증으로는 구조적으로 드러나지 않습니다.** 지역이 하나인 동안
리터럴과 옳은 값은 **같은 숫자**여서 어떤 단언도 둘을 가르지 못합니다. **두 번째
지역은 같은 것의 더 나은 테스트가 아니라, 존재하는 첫 테스트입니다.**
셋 중 하나는 「사본이 어긋난다」를 고치다 생겼습니다 — 통일은 옳았고, **통일된 하나가
지역별이어야 하는지는 아무도 묻지 않았습니다.**
전체 기록: [`docs/region_literals.md`](docs/region_literals.md) §0.

지금은 `make verify` 의 `check-region-literals` 가 이 부류를 막습니다.

### 4. 동작하는 운영 경로

- **실시간 트리거** — FIRMS NRT 또는 전화 신고 좌표 하나가 들어오면, 사전 계산된
  위험면 위에서 라우팅해 3종 전달물(SMS 초안·이장용 A4·마을방송 원고)까지 무인으로
  산출합니다. 최신 실행 실측 **탐지→목록 9.961초**(적재 포함 12.758초).
  [`docs/live_pipeline.md`](docs/live_pipeline.md)
- **운영자 콘솔** — 단일 파일 **153.9 KiB**, 3개 지역 인라인, 런타임 전환.
  지도를 클릭하면 그 지점에서 다시 계산합니다. 외부 요청 0건.
  [`docs/console_regions.md`](docs/console_regions.md)
- **신고 사진 EXIF** — 119 신고자가 주소를 모를 때, 사진의 GPS 좌표를 읽어 발화점으로
  씁니다. JPEG·HEIC·PNG. ⚠ **사진은 저장하지 않고, 좌표(4개 태그)만 읽고 즉시
  폐기하며, 파일명은 서버로 전송되지 않습니다.** 사진 내용으로 위치를 추정하지
  않습니다. [`docs/photo_exif.md`](docs/photo_exif.md)

### 5. 확인 가능성

- **`docs/NUMBERS.json`** — 보고 가능한 값 **136개**, 그중 **120개가 현재 입력에서
  재현 가능**. 나머지는 *검증되었으나 재현 불가*(2026-07-24 에 OSM 그래프가 덮어써짐)
  이며, **그 구분이 요점입니다** — 「재현 불가」는 「틀림」이 아니고, Round 3 이전에는
  어느 쪽인지 말할 방법이 없었습니다.
- **`make verify`** — 각 수치를 산출물에서 재유도하고, 폐기된 수치를 문서에서
  스캔하고, 지역 리터럴을 검사하고, Arm A 항목이 그대로인지 확인하고,
  게이트가 파이프 뒤에 숨지 않았는지 검사합니다.

  ⚠ **게이트를 파이프로 넘기지 마십시오.** POSIX 셸에서 파이프라인의 종료
  코드는 **마지막 명령의 것**이므로, `게이트 | tail` 은 게이트가 실패해도
  `tail` 의 0 을 돌려주고 `&&` 연쇄가 그대로 진행됩니다. Session 10 에서
  실제로 이 방식으로 빨간 게이트 위에 커밋이 올라갔습니다. 두 겹으로
  막아 둡니다 — `Makefile` 이 `.SHELLFLAGS := -o pipefail -e -c` 를 쓰고,
  `make check-gate-invocations` 가 추적 대상 셸·Makefile·CI·문서의 실행
  가능한 코드 블록에서 같은 패턴을 찾아 실패시킵니다. 직접 실행할 때는:

  ```bash
  set -o pipefail          # 파이프를 쓸 경우 반드시 먼저
  make verify              # 또는 게이트를 파이프 없이 그대로 실행
  ```
- **화면 게이트 3종** (`scripts/check_screen_assets.py`) — 오프라인(외부 요청 0),
  대시, WCAG 대비. ⚠ 이 게이트는 **JSON 페이로드로 도착하는 문자열을 보지 못합니다**;
  그 한계는 [`docs/screen_gate_scope.md`](docs/screen_gate_scope.md) 에 기록돼 있습니다.
- **테스트 1,021개 통과 / 3개 건너뜀** (2026-08-10 실측. 건너뜀 3 = 설계상 2 +
  DEM 격차 해소로 무의미해진 게이트 1. `calibration_metrics.json` 이 커밋되며
  8분짜리 재생성 결정론 게이트가 이 스위트에서 처음으로 실제 실행됩니다).

---

## Round 4 (2026-09 — 본선 준비)

> **이 절을 끝까지 읽고 난 뒤에도 이 저장소가 여전히 주장하는 것은 하나입니다.**
> 확산 예측의 **정확도**가 아니라 **산출물의 모양**입니다. 즉, 지점 단위로 「걸어서
> 나갈 수 있는가 / 구조를 보내야 하는가」를 **남은 시간과 함께** 판정하고 그 판정을
> 실제 출동 문서로 내놓는 산출물이, 실제 지역을 대상으로 만들어져 **저장소에 실물로
> 커밋되어 있다**는 것입니다. 이것은 **성능 주장이 아니라 존재
> 주장**이므로, 참인지 거짓인지는 심사위원이 파일을 여는 그 자리에서 판가름 납니다.
>
> - 출동 문서의 실물 → [`outputs/dispatch/README.md`](outputs/dispatch/README.md)
>   — 마을별 A4 출동 지시서 · 마을방송 낭독 문안 · 문자 초안. 어느 것도 발송되지
>   않았습니다.
> - 보행망과 확산면이 **동시에 실제**인 주사 →
>   [`docs/real_roads_real_hazard.md`](docs/real_roads_real_hazard.md)
>
> ⚠ **그 주장에 걸린 한정은 이렇습니다. 이 절의 나머지는 대부분 이것들을 실제로
> 재어 본 기록입니다.**
>
> - **위 두 링크는 같은 실행이 아니고, 앞의 것은 불이 실제가 아닙니다.** 커밋된 출동
>   문서를 만든 실행에서 **실제(OSM)인 것은 보행·차량 도로망, 대피소, 차고지**이고,
>   **화재 위험면과 지형은 합성**입니다(`data/processed/rescue_routing.json` 의
>   `provenance.sources` 가 스스로 그렇게 적습니다). 보행망과 확산면이 동시에 실제인
>   주사는 **별개의 실행**이고 그 실행은 4-구분 판정까지만 내놓습니다. **실제
>   확산면으로 만든 출동 지시서는 아직 없습니다** — 두 계보의 구분은
>   [`docs/HANDOFF_ROUND3.md`](docs/HANDOFF_ROUND3.md) 에 있습니다.
> - **여기서 「지점」은 실제 가구 주소가 아닙니다.** 고령 가구의 실제 위치는 공개
>   자료가 아니므로 출발지는 표본 좌표이고, 「마을」도 행정리가 아니라 공간 군집입니다.
>   커밋된 시트가 덮는 범위 또한 정본 산출물의 출동점 전부가 아니며, 그 범위는 위
>   README 가 스스로 적습니다.
> - **이 산출물이 「좋다」는 주장은 여기에 없습니다.** 얼마나 좋은지를 재던 성능
>   비교는 아래 **1번**에서 모델을 전혀 쓰지 않는 상대에게 대부분을 내주었고, 깎인
>   그대로 적혀 있습니다.
> - **출동 순서를 정하는 방식은 아직 이기지 못했습니다** — 마감 우선 배차는 최근접
>   우선을 이긴 적이 없습니다(아래 **3번**).
> - **입력은 「발화 즉시」가 아닙니다** — 탐지 바닥과 그 지연이 아래 **3번**에
>   있습니다.
> - **대상은 2025년 경북 산불의 영덕과 의성·안동뿐이고**, 다른 지역이나 다른 나라로의
>   이식성은 주장하지 않습니다.
> - **예보 인지 경로는 자기가 계획에 쓴 바로 그 장으로 채점됩니다.** 그 채점 성질은
>   [`docs/oracle_gap.md`](docs/oracle_gap.md) 가 셀 단위로 재어 두었고, 그것이 머리기사
>   수치의 뜻에 대해 무엇을 함의하는지는 이 저장소가 **정하지 않았습니다** — 저자에게
>   `docs/auto/NEEDS_HUMAN.md` 의 **NH-053**으로 열려 있습니다.

Round 4 는 **모델도 지역도 늘리지 않았습니다.** 새 확산 모델도, 재학습도, 새 지역
취득도 없습니다. 대신 이 저장소에서 **가장 강한 주장에 제대로 된 반대 상대를
세우고**, 한 번 철회한 주장이 조용히 되살아나지 못하게 하는 장치를 만들었습니다.
아래 다섯 항목은 모두 심사위원이 직접 열어 확인할 수 있습니다.

> ⚠ **읽는 법.** 이 절에서 **결과**인 항목은 1번과 3번 둘뿐이고, **둘 다 이 프로젝트의
> 주장을 깎는** 결과입니다. 4번과 5번은 결과가 아니라 심사위원이 열어볼 수 있는 것과
> 만든 것의 **목록**이고, 2번은 장치입니다. **이 절에 이 프로젝트에 유리한 결과는
> 없습니다.** 그렇게 적는 것이 이 절의 목적입니다.

### 1. 가장 강한 주장에 「공정한 상대」를 세웠습니다

지금까지 이 프로젝트의 머리기사 대비는 **불을 전혀 보지 못하는(fire-blind)**
기준선을 상대로 측정돼 있었습니다 — 가장 가까운 대피소로 최단경로를 걷고, 그
경로가 탔는지는 사후에야 듣는 상대입니다
(`src/wildfireguardian/routing/evacuation.py` 의 `naive_route`). 그래서 그 대비는
**「불이 어디로 갈지 아는 것」의 값어치**와 **「불이 지금 어디 있는지 아는 것」의
값어치**를 **가르지 못합니다**. 모델이 전혀 필요 없는 후자까지 예보의 공으로
돌립니다.

Round 4 는 그 둘을 가르는 상대를 실제로 돌렸습니다. **지금 타고 있는 영역에 고정
완충거리를 더해 거부하는 경로계획**(present perimeter + buffer)으로, 확산 모델을
쓰지 않습니다. **의성·안동**에서 측정했고, **결과는 이 프로젝트에 불리합니다** —
fire-blind 대비가 예보의 공으로 돌리던 것의 **대부분을, 모델 없는 이 상대가 이미
회수합니다**. 회수된 곳이 정확히 몇 곳인지, 그 경로가 얼마나 더 길어지는지, 그리고
이 상대가 **오히려 망가뜨리는** 곳은 몇 곳인지까지 모두
[`docs/present_perimeter_arm.md`](docs/present_perimeter_arm.md) 에 있습니다.

- ⚠ **그 완충거리의 폭은 자유 매개변수이고, 데이터가 그 값을 골라 준 것이
  아닙니다.** 이 실행이 쓴 폭은 사람이 고른 한 값이며, 같은 실행에서 다른 폭들도
  함께 측정했습니다. 폭을 바꾸면 이 상대가 **회수하는** 곳의 수도, 이 상대가
  **오히려 불 쪽으로 밀어 넣는** 곳의 수도 함께 바뀝니다. 그래서 이 항목에서 폭은
  결과보다 **먼저** 읽어야 하는 조건입니다. sweep 표와 그 해석은 위 문서의
  **4절**에 있고, 같은 사실을 원고는 「the buffer width is a second free parameter
  and nothing in the data chooses it」(`paper/manuscript.md`)로 적습니다.
- ⚠ **이 자리에 있던 문장 하나를 내렸습니다(2026-09-08).** 원래는 그 폭이 sweep
  안에서 넓은 고원이 아니라 하나뿐인 봉우리라고 적혀 있었지만, 그때 잰 폭은
  250 m · 500 m · 1 km · 2 km · 3 km 다섯 가지뿐이어서 가장 좋았던 폭의 양옆
  이웃이 각각 **두 배** 거리에 있었습니다. 그 격자로는 봉우리와 고원을 구분할 수
  없는데도 구분한 것처럼 적은 것입니다. 빠져 있던 **750 m · 1250 m · 1500 m**
  를 같은 코드·같은 입력으로 더 재보니 꼭대기는 봉우리가 아니라 **어깨**였고,
  게다가 **좌우가 대칭이 아니었습니다** — 얇은 쪽은 절벽이고 두꺼운 쪽은
  완만한 내리막이라, 틀리려면 **두껍게** 틀리는 편이 낫습니다. 방법과 표와 한계는
  [`docs/present_perimeter_buffer_shape.md`](docs/present_perimeter_buffer_shape.md),
  내린 문장의 기록은 `docs/auto/withdrawn_claims.json` 의 **WC-011** 입니다.
  ⚠ 이 재실행은 **이 프로젝트에 불리한 쪽으로** 끝났습니다: 새로 잰 폭 하나가
  기존 폭보다 점수가 높아서, 모델 없는 상대가 저장소가 적어 둔 것보다 **더
  강합니다**. 구체적인 값은 위 문서에 있고, 부스에서는 말하지 않습니다.
- ⚠ **그리고 그 상대의 폭은 결과를 다 보고 고른 것입니다 — 잰 폭들 위의
  최댓값이라, 잰 폭을 **더 늘릴수록** 이 상대는 세지기만 하고 예보가 낫다고
  말할 수 있는 몫은 줄어들기만 합니다.** 여유폭을 미리 정해 주는 규칙이 문제
  안에 없어서, 저희는 다 돌린 뒤 점수표를 읽어 상대에게 **가장 좋았던 폭**을
  줍니다. 그래서 새 폭을 하나 더 재면 기존 폭과 같거나 더 좋을 수만 있습니다.
  이건 가정이 아니라 위 재실행에서 실제로 일어난 일이고 — 저희가 해 본 첫 번째
  세밀화에서 가장 좋은 폭이 옮겨 갔습니다 — 더 촘촘히 재면 어디까지 갈지는
  **아무도 재보지 않았습니다**. 이 저장소가 이 상대와의 비교를 말할 때는 언제나
  「많아야 이만큼, 그것도 저희가 재본 격자 위에서」로 읽어야 합니다. 상대에게
  가장 유리한 폭을 주는 것 자체는 **일부러 그렇게 한** 보수적인 설계이고, 이
  항목은 그 설계의 **대가**를 적어 둔 것입니다. 성질과 그 대가는
  [`docs/present_perimeter_buffer_shape.md`](docs/present_perimeter_buffer_shape.md)
  **4절**에 있습니다.
- ⚠ **영덕에서는 이 상대를 아직 돌리지 않았습니다.** 위 TL;DR 의 **42곳**은
  영덕에서 나온 값이므로, 그 수치에는 이 검사가 **아직 적용되지 않았습니다**.
  ⚠ **정정(2026-09-11, WFG-258 · 보강 WFG-259): 위 두 문장은 이제 「이 절의 상대」,
  곧 완충거리를 폭까지 훑어 정식 상대로 세운 쪽에만 해당합니다.** 완충거리가
  **0 m** 인 상대 — 지금 타고 있는 자리만 거부하고 확산 모델은 전혀 쓰지 않는
  경로계획 — 은 2026-09-11 에 영덕의 바로 그
  **42곳 위에서 실제로 돌았습니다**. 방법·결과·한계는
  [`docs/present_perimeter_yeongdeok.md`](docs/present_perimeter_yeongdeok.md) 에
  있고, 거기서 나온 수치는 그 문서 **4절**에 그대로 적혀 있습니다. 이 README 에는
  옮겨 적지 않습니다 — 그건 여백이 아니라 대상 지점 전체를 세 갈래로 나눈
  **분할**이고, 그렇게 읽어야 하는 이유는 같은 문서 **5절**의 여덟 항목이기
  때문입니다. **완충거리를 폭까지 훑어 정식 상대로 세운** 쪽은 영덕에서 여전히
  돌리지 않았습니다. ⚠ **덧붙임(2026-09-11, WFG-259): 그 문서 5절 5항이 이미 적어
  두었던 두 폭은 그날 실제로 돌려 확인했고, 방법·결과·한계는 같은 문서에 함께
  공개되어 있습니다.**
  이 정정은 위 42곳의
  값을 바꾸지 않습니다 — 그 42곳은 여전히 아래 ①②의 두 단서를 그대로 답니다.
  그 42곳에는 언제나 **두 개의 단서가 함께 붙습니다**: ① 비교 상대가 **불을 전혀
  보지 못하는(fire-blind)** 기준선이므로 그 대비는 「어디로 갈지 아는 것」과
  「지금 어디 있는지 아는 것」을 가르지 못하고, ② 예보 인지 경로는 **자기가 계획에
  쓴 바로 그 장으로 채점됩니다**. 그 장은 「정답」이 아니라 **이 불을 한 번도 학습하지
  않은 모델이 만든 전방 시뮬레이션**(leave-one-fire-out)이고, 같은 파일 안에 함께
  들어 있는 관측(FIRMS 누적 발자국)은 채점에 전혀 쓰이지 않습니다. 그래서
  **오라클은 계획하는 쪽이 아니라 채점하는 쪽에 있고**, 42곳은 「완벽한 예보가 사 줄
  값」이라기보다 **자기 예측을 그대로 믿었을 때의 값**입니다. 그 예측이 관측과 얼마나
  벌어지는지는 [`docs/oracle_gap.md`](docs/oracle_gap.md) 가 셀 단위로 재어 두었고
  (§7 이 그 측정이 보여 주지 **않는** 것을 적습니다), 실제 예보 오차를 넣은 값은 아직
  재지 않았습니다(§6 이 그 재채점을 적어 둡니다). 그것이 곧 42곳이 참값의
  **「상한」**이라는 뜻인지는 **아직 정해지지 않은 물음**입니다 — 이 저장소의 어떤
  것도 그것을 유도하지 않으며, 저자에게 **NH-053** 으로 열려 있습니다.
- ⚠ 이 실험이 내놓은 **구체적인 margin 값들은 부스에서 말하지 않습니다.** 어느 값을
  정본으로 삼을지가 아직 정해지지 않았고 (`docs/auto/NEEDS_HUMAN.md` 의 열린 항목),
  정해지기 전에 말하지 않는 편이 낫다고 판단했습니다. **어디에 없고 어디에 있는지를
  정확히 적으면 이렇습니다**: 본선 화면(`web/finals.html`)에도, 인쇄 패널에도,
  제출 서식에도 그 값들은 **없습니다**. 인쇄 키트에 함께 묶여 있는
  **심사위원 질의응답 카드**(`docs/auto/JUDGE_QA.md`)에는 **있습니다** — 다만
  거기서는 **학생이 부스에서 말하면 안 되는 것들의 목록**으로만 실려 있고, 그 카드가
  존재하는 이유가 바로 그 금지입니다. ⚠ 이 항목은 2026-09-08 에 고쳐 썼습니다.
  그전에는 「어느 심사용 자료에도 싣지 않습니다」라고 적혀 있었는데, 「심사용 자료」가
  이 저장소 어디에도 정의돼 있지 않은 데다 위 카드가 인쇄 키트의 일부이므로
  **사실이 아니었습니다**. 「어느 자료에도 없다」처럼 **범위를 뭉뚱그린 한 문장**은
  범위를 적기만 하면 틀리지 않았을 자리에서 틀립니다. 그래서 이 자리는 범위를
  적는 쪽으로 바꿨습니다.

### 2. 철회한 주장이 되살아나지 못하게 했습니다

이 저장소는 틀린 것으로 밝혀진 주장을 지우지 않고 **기록으로 남깁니다**(TL;DR 의
철회 항목이 그 예입니다). Round 4 는 그 관행을 **기계가 읽는 등록부**로 바꿨습니다:
철회된 주장은 `docs/auto/withdrawn_claims.json` 에 실제로 쓰였던 표현들과 함께
등록되고, `make verify` 가 추적 대상 문서에서 그 표현을 다시 찾습니다. 한 문서만
고치고 여덟 절 뒤의 같은 문장을 놓치는 일 — 실제로 있었던 일입니다 — 이 그래서
막힙니다.

⚠ **이 장치의 한계는 장치 자신이 적어 둡니다.** 두 가지입니다. ① 등록부는
**복사·붙여넣기를 막는 래칫이지 주장 탐지기가 아니며, 다르게 고쳐 쓴 문장은
빠져나갑니다.** ② 검사 범위는 **`.md` 와 `.html` 뿐**이므로, `make verify` 가
초록색이라는 사실만으로 철회된 주장이 저장소에서 사라졌다고 읽으면 안 됩니다.
측정된 한계는 [`docs/withdrawn_claims.md`](docs/withdrawn_claims.md) 에 있습니다.

### 3. 불리한 결과 두 개를 그대로 싣습니다

- **배차 순서** — 이 시스템이 싣고 있는 **마감 우선(deadline-first)** 배차 순서는,
  운영 시점의 창에서 단순한 **최근접 우선**을 이긴 적이 **없습니다**. 이긴 칸의
  수는 **0**입니다. → [`docs/dispatch_ordering.md`](docs/dispatch_ordering.md)
- **탐지 바닥** — 정지궤도 위성 검출기는 이 화재들을 **화소 이하 크기의 바닥**에서,
  그리고 기록된 발생 시각보다 **수십 분 뒤에야** 봅니다. 즉 이 시스템의 입력은
  「발화 즉시」가 아닙니다. → [`docs/detection_floor.md`](docs/detection_floor.md),
  부스용 카드는 [`docs/auto/finals/DETECTION_FLOOR_CARD.md`](docs/auto/finals/DETECTION_FLOOR_CARD.md)

### 4. 심사위원이 그 자리에서 열어볼 수 있는 것

- **오프라인 본선 화면** — `web/finals.html` 외 3종. 외부 요청 0건이므로 부스에
  인터넷이 없어도 그대로 뜹니다.
- **USB 로 가는 꾸러미** — [`release/kcf-finals-2026/`](release/kcf-finals-2026/).
  `make finals-bundle` 이 트리에서 다시 만들어 SHA-256 을 재유도하고, 매니페스트와
  다르면 거부합니다. 빌려온 노트북에서는 `python scripts/check_bundle_copy.py` 가
  표준 라이브러리만으로 사본을 검사합니다.
- **인쇄물 묶음** — `docs/auto/finals/printables/` 의 A4 PDF 한 벌. 어느 문서
  몇 장으로 만들어졌는지는 같은 폴더의 매니페스트가 스스로 적으며, 원본 문서가
  바뀌면 게이트가 그 묶음을 낡은 것으로 판정합니다. (여기에 장수를 손으로 적지
  않는 이유가 그것입니다.)
- **질의응답 은행** — [`docs/auto/JUDGE_QA.md`](docs/auto/JUDGE_QA.md). 각 답변은
  파일을 가리키고, 카드마다 **「없는 것」** 을 함께 적습니다.
- **개발 일정과 역할** — [`docs/auto/finals/TIMELINE_ROLES.md`](docs/auto/finals/TIMELINE_ROLES.md).
  **1기 · 착수와 물리 모델**, **2기 · 1차 정리와 Round 2 제출**, **3기 · Round 3 개발**,
  **4기 · 세션 기록 정리와 재현성**, **5기 · 자율 루프 스프린트** 의 다섯 구간이고, 모든
  날짜와 수는 저장소의 산출물 `data/processed/timeline_roles/timeline_roles.json` 에서 다시
  세어지며 `tests/test_timeline_roles.py` 가 문서와 산출물을 대조합니다. ⚠ 미리 세운
  계획서가 아니라 사후에 만든 기록이고, 구간 사이의 빈칸(학기와 시험)도 그대로 둡니다.
- **깨끗한 복제본에서의 재검** — 매 push 마다 GitHub Actions 가 같은 게이트를
  빈 리눅스 머신에서 다시 돌립니다(`.github/workflows/auto-gates.yml`). 이
  저장소의 수치는 **이 노트북에서만 맞는 수치가 아닙니다.**

### 5. 창의성 — 이 작품이 직접 만든 것

⚠ 아래는 **무엇을 만들었는지**만 적습니다. 그것이 얼마나 뛰어난지는 적지 않습니다.
그 판정은 심사위원의 몫이고, 저장소가 스스로에게 줄 수 있는 점수가 아니기 때문입니다.

- **① 산출물 자체가 기여입니다.** 확산 예측 격자는 최종 결과물이 아니라 중간 입력이고,
  이 시스템이 내놓는 것은 **지점 단위의 「걸어서 나갈 수 있는가 / 구조를 보내야 하는가」
  판정과 그 도보 경로**입니다. 예측 정확도로 겨루지 않고 산출물의 모양으로 겨루는 쪽을
  택했다는 뜻입니다. **그 산출물의 실물이 저장소에 커밋돼 있습니다** — 마을별 A4 출동
  지시서, 마을방송 낭독 문안, 문자 초안이고, 어느 것도 발송되지 않았습니다.
  ⚠ **커밋된 그 실물을 만든 실행에서 화재 위험면과 지형은 합성이고, 출발지는 표본
  좌표입니다**(`data/processed/rescue_routing.json` 의 `provenance.sources` 가 스스로
  `hazard: synthetic`, `terrain: synthetic`, `origins: sampled candidates` 라고 적습니다).
  **실제 확산면으로 만든 출동 지시서는 아직 없습니다.** 「지점」은 실제 가구 주소가 아니고
  「마을」도 행정리가 아니라 공간 군집입니다. 아래의 「두 축이 동시에 실제인 실행」은
  **별개의 실행**이고 출동 문서를 내놓지 않으므로, 이 항목과 그 항목을 이어서 「실제 도로 +
  실제 불 → 이 지시서」로 읽어서는 안 됩니다 — 이 절 머리의 한정과 같은 내용입니다.
  → 실물과 그 한계: [`outputs/dispatch/README.md`](outputs/dispatch/README.md)
  → 정확도로 겨루지 않기로 한 판단의 근거:
  [`docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md`](docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md)
- **② 두 축이 동시에 실제인 실행.** 실제 OpenStreetMap 보행 그래프와 실제 전진
  시뮬레이션 확산면을 한 실행 안에서 함께 돌렸고, 그것이 이 프로젝트가 스스로 가장 크다고
  적어 두었던 한계를 닫은 지점입니다.
  → [`docs/real_roads_real_hazard.md`](docs/real_roads_real_hazard.md)
- **③ 철회한 주장을 기계가 읽도록 등록합니다.** 틀린 것으로 밝혀진 문장을 지우는 대신
  등록부에 남기고, `make verify` 가 매 push 마다 추적 문서를 상대로 그 표현을 다시
  찾습니다. 자기 교정을 관행이 아니라 **게이트**로 만든 것이 이 항목입니다.
  → [`docs/auto/withdrawn_claims.json`](docs/auto/withdrawn_claims.json),
  [`scripts/check_withdrawn_claims.py`](scripts/check_withdrawn_claims.py)

⚠ **없는 것.** ③의 등록부는 복사·붙여넣기를 막는 래칫이지 주장 탐지기가 아니어서
**다시 쓴 문장은 빠져나갑니다**; 검사 범위는 추적되는 `.md` 와 `.html` 뿐이고, 자동 루프가
스스로 남기는 **기록 문서**는 설계상 제외됩니다([`docs/withdrawn_claims.md`](docs/withdrawn_claims.md) §4).
그리고 위의 것들이 창의적인지, 애초에 이 세 가지가 옳은 세 가지인지는
**심사위원의 판단입니다.**

같은 답을 부스에서는 본선 화면의 「시스템 구조」 탭과 질의응답 카드 **Q29a** 가 말합니다.
이 답변이 왜 이 문체로 — 자평 없이, 다른 시스템과의 비교 없이 — 쓰였는지는
[`docs/creativity_card.md`](docs/creativity_card.md) 에 적혀 있습니다.

영문 초록 초안은 아래 [Abstract (draft)](#abstract-draft) 에 있습니다.

---

### 프로젝트 개요

**WildfireGuardian** 는 산불 발화부터 대피 완료까지의 "골든타임" 동안 위성 화재
탐지·데이터 기반 화재 확산 예측·개인 맞춤형 대피 경로 안내를 통합 제공하는 연구용
시스템입니다.

**보호 대상**: 한국 농촌의 고령층(60–80대). 2025년 3월 경북 **의성**에서 발화해
**의성→안동→청송→영양→영덕**으로 번진 산불(최종 피해면적 **99,289 ha**로 1986년 통계
작성 이래 최대, 주불 진화까지 149시간; 사망 **26명**, 그중 **영덕 10명**〈영덕군 공지
2025-04-29, 그린피스 실태조사 최종보고서 p.9 재인용값; 경상북도 재난안전대책본부
2025-03-30 중간 집계는 9명〉, 대부분 60–80대 고령자; 주택 **3,819동** 피해,
이재민 2,246세대 3,587명, 재산피해 1조 505억 원)의 재발 방지·대응 개선을 동기로 삼습니다
([아시아경제 2025-05-06](https://view.asiae.co.kr/article/2025050610030818823),
경상북도 최종 집계·중앙재난안전대책본부 확인).

〔**범위 주의 — 기준이 다른 값들을 서로 비교하거나 나누지 마십시오.**
① 위 **99,289 ha**는 관계기관 합동조사를 거친 이 화재군의 **산림피해 면적**입니다
([경향신문 2025-04-17](https://www.khan.co.kr/article/202504171020011)).
② 진화 중에 널리 인용된 **45,157 ha**는 같은 화재군의 **「산불영향구역」 초기 추정치**
(산림청, 2025-03-27)이며, 합동조사 결과는 그 추정치의 두 배를 넘었습니다.
③ 흔히 함께 인용되는 **104,788 ha**·**347건**은 이 산불 하나가 아니라
*2025년 **봄철 산불조심기간**(1월 24일 ~ 5월 15일) 전국 산불 전체*의 합계입니다
([산림청 보도자료 2025-05-16](https://www.pcccr.go.kr/base/board/read?boardManagementNo=43&boardNo=5375&menuLevel=2&menuNo=92)).
①과는 **기간·주체·집계 기준이 모두** 다르므로 「이 화재군이 전국의 몇 %」 같은 비율은
쓰지 않습니다. ②를 분자로 바꿔도 마찬가지입니다. ②는 ①과 나란히 놓을 수 있는 다른
기준의 값이 아니라 **합동조사가 뒤집은 이전 추정치**이므로, 같은 기준끼리 맞춘 비율은
이 저장소에 존재하지 않습니다(`docs/data_sources.md` 함정 6).
출처와 범위 정리는 `docs/data_sources.md` 참조〕

**대회**: 2026 대한민국 학생 SW공모전(Korea Code Fair) → ISEF (Software Design, SFTD)
출전을 목표로 합니다.

### 현재 모델과 결과 (Build B — `spread_v2`, 데이터 기반)

본 저장소의 **정식(canonical) 모델은 Build B** (`src/wildfireguardian/spread_v2`)
이며, 모든 후속 결과(라우팅 노출도, 구조 4-구분 등)를 산출한 모델입니다. 한 산불의
다음 위성 통과 시점에 각 격자 셀이 발화(탐지)될 확률 `P(ignite)` 를 예측하는
그래디언트 부스팅(sklearn `HistGradientBoostingClassifier`) 분류기입니다.

- **평가 — 한 산불씩 제외 교차검증 (LOGO-CV; leave-one-group-out, 그룹 = 산불)**: 6개 실제 산불(gangneung_2023, hongseong_2023,
  miryang_2022, uiseong_andong_2025, uljin_samcheok_2022, yeongdeok_2025).
- **폴드 평균 ROC-AUC = 0.89** (범위 0.68–0.97). `gangneung_2023` 폴드(0.68)는 양성
  약 8건(탐지 약 17건)뿐인 소규모·잡음 폴드이며, 이를 제외한 다섯 산불 평균은 약
  0.93 입니다. **일반화 지표로는 폴드 평균을 보고**합니다. 전체 보류예측 통합
  **pooled = 0.905** (부트스트랩 95 % CI [0.901, 0.909])는 *pooled* 로 명시해서만
  사용하며, 일반화 지표가 아닙니다.
- ⚠ **세기 vs 풍향 — 측정값이며 미확립입니다.** 순열 중요도에서 화재기상
  **세기**(`days_since_rain`, `vpd_kpa`, `rh_pct`, `temp_c`, `precip_24h_mm`,
  풍속 `wind_speed_ms`) 합은 **0.102**, 풍향 정렬 `wind_alignment` 는 **0.0023**
  입니다. 이전 판은 이 비율을 헤드라인으로 걸었으나 **철회**했습니다. 근거 세 가지:
  1. **6개 특징 합산**을 **단일 변수**와 견주는 비교입니다.
  2. ERA5 는 **0.25°(~28 km)** 라 세기 특징이 한 산불의 한 시점 안에서 거의 균일합니다.
     즉 *날짜·산불 간* 구분력이지 *통과 내 공간* 배치력이 아닙니다
     ([`docs/ROUTING_INTEGRATION_REPORT.md`](docs/ROUTING_INTEGRATION_REPORT.md) "Honest nuance").
  3. 시드·폴드에 걸친 산포를 측정하지 않은 **단일 점추정**입니다
     ([`docs/auc_intervals.md`](docs/auc_intervals.md)).

  ⚠ **「풍향이 중요하지 않다」는 뜻이 아닙니다.** 이 장비로는 볼 수 없다는 뜻입니다.
- ⚠ **그리고 1위 특징은 폴드 밖에서 모델을 악화시킵니다.** `days_since_rain` 은
  순열 중요도 1위(**+0.077**)이지만, *제거하면* 폴드평균 AUC 가 **+0.0270**,
  원거리대가 **+0.0533** 올라갑니다. 6개 산불 중 3개는 ERA5 창에 습윤 표본이
  **0개**라 이 값이 비가 아니라 **취득 창 시작점**에 고정됩니다 — 학습 자료의
  절반에서 취득 파라미터를 재는 셈입니다. *(「창 길이와 정확히 같다」던 이전
  서술은 학습 테이블 실측과 달라 2026-08-10 정정 — 실측값은
  [`docs/weather_dependency.md`](docs/weather_dependency.md) §②.)* PHASE 14.
- **규모**: 16개 특징, 151,904행 / 양성 2,989(약 1.97 %), 시드 20250603,
  좌표계 EPSG:5179.
- **원거리(>3 km) 폴드 평균 AUC = 0.925** (n=3; 화선의 *도달* 예측력 — ⚠ 이
  값은 커밋된 적 없는 정정 이전 재실행의 것으로, 커밋된 산출물
  `auc_intervals.json`(정정 계보)은 **0.904 ± 0.100** 을 담습니다), 통합 pooled
  0.877 — ⚠ 정정 DEM 재실행에서는 pooled 원거리대가 **0.8408**로 내려갑니다.
  0.877 을 인용할 때는 이 캐비앗을 함께 제시하십시오
  ([`docs/MODEL_CARD.md`](docs/MODEL_CARD.md) DEM 정정 절). 순방향 모의 화선
  **footprint IoU ≈ 0.40** (영덕, 3–12시간) — 물리(Rothermel)
  표면 모델 **~0.09** 대비 약 **4배**로, 표면물리가 놓치는 수관화·비화(crown/spotting)
  영역을 포착합니다.

| 산불 (held-out) | ROC-AUC | DeLong 95 % CI |
|---|---|---|
| miryang_2022 | 0.974 | [0.941, 0.989] |
| hongseong_2023 | 0.945 | [0.916, 0.964] |
| yeongdeok_2025 (시연 산불) | 0.941 | [0.936, 0.946] |
| uljin_samcheok_2022 | 0.918 | [0.911, 0.924] |
| uiseong_andong_2025 | 0.878 | [0.871, 0.884] |
| gangneung_2023 (양성 약 8건 — 잡음) | 0.682 | [0.577, 0.771] |

> **6개 폴드 모두 AUC = 0.5 대비 통계적으로 유의**합니다(`gangneung_2023`
> p = 2.7×10⁻⁴, 나머지 다섯 p ≪ 0.001). 위 폴드별 **DeLong 95 % 신뢰구간**과 유의성
> 검정은 `scripts/auc_intervals.py`(정식 수치 pooled 0.905 / 폴드평균 0.890에 대한
> **일치성 게이트** 통과 후 산출, FIRMS/ERA5/DEM 번들 필요)로 재현합니다. 번들이
> 없으면 **수치를 날조하지 않고 깨끗이 중단(STOP, exit 2)** 합니다. 통계 도구는 단위
> 테스트로 검증되어 있습니다(`tests/test_auc_stats.py`). 자세한 내용·한계:
> [`docs/auc_intervals.md`](docs/auc_intervals.md).
>
> **표준 ML 베이스라인**(동일 16특징·폴드·시드 20250603) — "나쁜 물리모델만 이긴 것
> 아니냐"에 답하는 통제 비교:
>
> | 모델 | 폴드 평균 AUC ± SD | pooled |
> |---|---|---|
> | 랜덤포레스트 | 0.914 ± 0.044 | 0.896 |
> | 로지스틱 회귀 | 0.903 ± 0.060 | 0.826 |
> | **hist_gbm (본 모델)** | **0.894 ± 0.092** | **0.904** |
>
> ⚠ 표의 수치는 커밋된 산출물 `data/processed/ml_baselines.json`(2026-08-10,
> **정정 DEM 번들** — 이 기기의 유일한 번들)의 값입니다. 이전 판의 수치
> (랜덤포레스트 0.920 등)는 커밋된 적 없는 정정 이전 실행의 것이었으며, 순위
> 결론(폴드 평균 RF 근소 우위, pooled GBM 우위)은 두 계보에서 동일합니다.
>
> 폴드 평균에서는 랜덤포레스트가 근소 우위입니다. ⚠ **보정도 GBM의 차별점이
> 아닙니다** — 실측(`calibration_metrics.json`): pooled Brier/ECE 가 GBM
> 0.0183/0.0086, RF **0.0174/0.0068** 로 베이스라인이 GBM 만큼 잘 보정됩니다.
> GBM 채택의 실측 근거는 **pooled AUC 우위 · 추론 속도 · NaN 원생 처리 ·
> 순열 중요도 산출**이며, 「보정된 확률」은 GBM 의 절대적 성질(라우터가 실제
> `P(ignite)` 를 소비, Brier 0.018)이지 비교 우위가 아닙니다. ⚠ 채택 근거로
> 들었던 "세기 ≫ 풍향" 발견은 미확립으로 철회되었습니다(위 참조).
> 재현: `scripts/ml_baselines.py` · `scripts/calibration_metrics.py`. 방법론:
> [`docs/baselines.md`](docs/baselines.md).

### 시스템 구성

```
            ┌──────────────────────────────────────────────┐
            │            위성 화재 탐지 (FIRMS)            │
            │        NASA FIRMS VIIRS + MODIS 발화점       │
            └───────────────────────┬──────────────────────┘
                                    │ 발화점
            ┌───────────────────────▼──────────────────────┐
            │           연료·지형·기상 상태층              │
            │  ESA WorldCover(연료) + SRTM(DEM) + ERA5(기상)│
            └───────────────────────┬──────────────────────┘
                                    │
            ┌───────────────────────▼──────────────────────┐
            │   데이터 기반 격자 발화확률 모델 (spread_v2)  │
            │  HistGradientBoosting · LOGO-CV 검증 · 보정 P(ignite) │
            └───────────────────────┬──────────────────────┘
                                    │ 위험도 표면
            ┌───────────────────────▼──────────────────────┐
            │  고령자·구조 인지 대피 라우팅 (시간의존)      │
            └───────────────────────┬──────────────────────┘
                                    │
            ┌───────────────────────▼──────────────────────┐
            │        개인 맞춤형 알림·경로 전달            │
            └──────────────────────────────────────────────┘
```

자세한 설계는 [`docs/architecture.md`](docs/architecture.md) 참고.

### 현재 상태

**연구 PoC(개념검증).** 알파 수준의 "미완성"이 아니라, 6개 실제 산불로 검증된
데이터 기반 모델과 그 위의 라우팅까지 동작하는 개념검증입니다. 본 저장소가 제공하는 것:

- **데이터 기반 격자 발화확률 모델 (`spread_v2`, Build B)** — 6개 실제 산불에
  대한 LOGO-CV 검증(폴드평균 ROC-AUC 0.89), 보정된 확률, 순열 중요도.
  ⚠ "세기≫풍향" 주장은 **미확립으로 철회**되었습니다 — 6개 특징 합산 대 단일 변수
  비교이며 ERA5 0.25°(~28 km)가 국지풍을 해상하지 못합니다. 「풍향이 중요하지 않다」는
  뜻이 아닙니다. `src/wildfireguardian/spread_v2/`
- **실데이터 인제스션** — NASA FIRMS 발화점 + SRTM DEM + ESA WorldCover 연료 +
  ERA5 기상(`spread_v2/data.py`). FIRMS 번들은 git-ignore 되어 별도 다운로드합니다.
- **검증 통계 도구** — DeLong CI/유의성, 부트스트랩, 순열검정, 폴드평균 t-구간
  (`validation/auc_stats.py`, 단위 테스트). 게이트형 재실행: `scripts/auc_intervals.py`.
- **표준 ML 베이스라인 비교** — 동일 16특징/폴드/시드의 로지스틱·랜덤포레스트
  비교(`scripts/ml_baselines.py`, `docs/baselines.md`).
- **구조-인지 대피 라우팅** — 미래-화선 인지 + 차량 진입로 생존성
  (`wildfireguardian.routing.rescue`).
- **지역 설정·취약도 골격** — 영덕 2025, 울진/삼척 2022, 고성 2019 등
  (`utils/regions.py`, `utils/vulnerability.py`).
- **물리(Rothermel) 화재 확산 모델** — 초기 접근으로 보존(아래 *연구 로그* 참조).

본 시스템은 **운영용 소프트웨어가 아닙니다.** 단일 산불(영덕) 후속 PoC이며, 라우팅
보조 데이터의 일부는 합성·근사값입니다(명시 표기). 전문가 검토 없이 공식 대피 명령의
유일한 근거로 사용해서는 안 됩니다.

### 데이터 출처

정식 파이프라인(`spread_v2`)이 실제로 사용하는 공개 데이터입니다. 저장소는 데이터를
배포하지 않으며, 사용자가 실행 시점에 `data/raw/` 로 직접 내려받습니다.

- **NASA FIRMS** (VIIRS S-NPP/NOAA-20 + MODIS 활성 화재 탐지): <https://firms.modaps.eosdis.nasa.gov/>
- **SRTM** (NASA, ~30 m DEM/지형): <https://earthexplorer.usgs.gov/>
- **ESA WorldCover 2021** (10 m 토지피복 → 연료 가연성): <https://esa-worldcover.org/>
- **ECMWF ERA5** (재분석 기상: 10 m 바람, 2 m 기온/이슬점, 강수): Copernicus C3S / CDS
- 라우팅 계층: **OpenStreetMap**(도보·차량 도로망, OSMnx), **공공데이터포털**
  전국 대피소 표준데이터(행정안전부), **119안전센터**(소방청) — 각각 실데이터
  로더와 *명시된 합성 대체값*을 제공.

전체 데이터 카탈로그(라이선스·접근 포함)는 [`docs/data_sources.md`](docs/data_sources.md).

### 처음 보는 노트북에서 데모 띄우기 (본선 · 오프라인)

**아래 그대로 붙여넣으면 됩니다.** 인터넷 없이 동작하며, 1.3 GB 데이터 번들도
필요 없습니다 — 콘솔과 `/field` 는 완성된 HTML 이라 지역 데이터를 읽지
않습니다. Session 18 에서 빈 클론·빈 가상환경으로 실제로 실행해 확인했습니다
(전문은 `docs/SESSION18_LOG.md`).

```bash
# 1. 클론
git clone https://github.com/sparkxt-0318/wildfireguardian.git
cd wildfireguardian

# 2. 가상환경 (Python 3.11)
python3.11 -m venv .venv && source .venv/bin/activate

# 3. 선언된 의존성만 설치. h5netcdf/h5py 를 따로 치던 줄은 필요 없습니다 —
#    Session 18 에서 requirements.txt 에 정식 선언했습니다.
pip install -r requirements.txt
pip install -e . --no-deps

# 4. 여기서 이미 데모가 뜹니다 — 브라우저로 파일을 직접 열면 됩니다.
#    web/console.html   운영 콘솔 (3개 지역 인라인)
#    web/field_view.html 현장 화면
#    외부 요청 0건: CDN·타일·API 를 일절 부르지 않습니다.

# 5. 서비스로 띄우려면 (선택)
python -m uvicorn --app-dir src --factory wildfireguardian.api.app:create_app --port 8000
#    -> http://127.0.0.1:8000/        콘솔
#    -> http://127.0.0.1:8000/field   현장 화면
#    -> http://127.0.0.1:8000/api/health
#    ⚠ 데이터 번들이 없으면 지역 preload 는 실패하지만 서비스는 정상 기동하고,
#      /api/health 의 preload_failed_regions 가 무엇이 없는지 알려줍니다.
#      (Session 18 이전에는 여기서 전체 기동이 죽었습니다.)

# 6. 화면 두 개를 다시 빌드하고 싶다면 (선택, 데이터 번들 불필요)
python scripts/build_console.py
python scripts/build_field_view.py
```

**게이트로 확인:** `python scripts/check_declared_deps.py` 는 선언되지 않은
런타임 임포트가 하나라도 생기면 exit 1 입니다. `import` 문뿐 아니라
`engine=` / `driver=` 문자열도 훑습니다 — `h5netcdf` 와 `h5py` 는 어떤 import
문에도 이름이 없고 `xr.open_dataset(engine="h5netcdf")` 로만 불려서, 임포트
순회만으로는 원리적으로 찾을 수 없기 때문입니다.

### 재현 (Reproduce)

전체 분석을 다시 돌리려면 데이터 번들이 필요합니다. 데모만 볼 때는 위 절차로
충분합니다.

```bash
git clone https://github.com/sparkxt-0318/wildfireguardian.git
cd wildfireguardian
python -m venv .venv && source .venv/bin/activate

# 정식 분석 스크립트의 전체 의존성. (편집가능 설치 `pip install -e .` 만으로는
# scikit-learn / xgboost / xarray / pyproj / rasterio 등이 빠집니다.)
pip install -e ".[ml,geospatial]"     # numpy scipy pandas shapely matplotlib pydantic
                                      #  + scikit-learn xgboost xarray pyproj rasterio ...
                                      #  h5netcdf/h5py 는 이제 코어 의존성입니다

# 데이터 번들 배치 (저장소에 없음 — git-ignore):
unzip firms_data.zip -d data/raw/     # 또는: export WFG_FIRMS_DIR=/path/to/firms

# 정식 LOGO-CV 재실행 → 일치성 게이트가 pooled 0.905 / 폴드평균 0.890 재현
python scripts/auc_intervals.py       # per-fire DeLong CI + 0.5 대비 유의성
python scripts/ml_baselines.py        # 로지스틱/랜덤포레스트 vs GBM (동일 특징/폴드/시드)

pytest -q                             # 단위 테스트 (실데이터 불필요; FIRMS/SRTM 의존
                                      #  테스트만 번들 부재 시 skip)
```

데이터 번들이 없으면 두 스크립트는 **exit 2 로 깨끗이 중단**하며 어떤 수치도 보고하지
않습니다(통계 도구 자체는 `pytest tests/test_auc_stats.py` 로 검증). 구조-라우팅
데모는 추가로 `pip install -e ".[routing]"`(osmnx, networkx)가 필요합니다.

### 구조-인지 대피 라우팅

`wildfireguardian.routing.rescue` 는 미래-화선 인지 라우터 위에 **구조 가능성**
제약을 더합니다: 고령자를 **차량 접근로가 예측 화재에서 살아남는** 대피소로만
안내하고, 스스로 대피할 수 없는 주민에게는 **구조대 차량의 진입 경로**를 계산하며,
**누가 도달 불가능한지 정직하게** 보고합니다(추정·날조 없음).

영덕 PoC 4-구분(합 = N = 439, 실제 OSM 도로·대피소·차고지 + 합성 화재·지형 기반):
원래 안전 262 · 구조가능 대피소로 구조 10 · 도보 불가(구조대 출동) 143 ·
**차량 접근 불가(도달 불가) 24**. 도보 자력대피 실패율 **w ≈ 11 %**(임계값에 따라 9–17 %)는
모델에서 도출된 값으로, 10시간 보행 예산·거동 불가 가정과 무관합니다. 반면 구조대가
필요한 출발지 **167/439 = 38 %**는 거동 불가 비율 0.30을 가정한 시나리오 추정치이며,
관측된 인구 특성이 아닙니다. 출동 지연 **0→60분**이면 도달 불가 출발지가 **6→66**으로
늘어납니다.

> 주민 측 노출 비교는 대응표본이 아니어서 인과 효과로 해석하지 않습니다. 대응표본으로
> 검증된 것은 구조자 측이며, 143곳 동일 출발지에서 최단경로 대비 노출이 6.12 → 1.71
> (약 72% 감소)입니다.

점추정치는 방향성 지표이며, 단일 산불 PoC + 합성 보조 데이터 위의 값입니다. 자세한
방법론·데이터 출처는 [`docs/rescue_routing.md`](docs/rescue_routing.md).

```bash
python scripts/run_rescue_routing.py            # 4-구분 + 노출 + 민감도
python scripts/verify_rescue_routing.py         # 재조정 baseline + 차량×지연 sweep
pytest tests/test_rescue_routing.py -q
```

![rescue four-way split](docs/figures/rescue_four_way.png)

### 인용

```bibtex
@software{wildfireguardian2026,
  title  = {WildfireGuardian: Wildfire spread forecasting and household-level
            evacuation and rescue routing for rural elderly Koreans},
  author = {{WildfireGuardian Project Contributors}},
  year   = {2026},
  note   = {2026 Korea Code Fair SW공모전 submission.},
  url    = {https://github.com/sparkxt-0318/wildfireguardian}
}
```

---

### Abstract (draft)

> ⚠ **This is a DRAFT written by the project's agent loop, not the student's own
> prose.** Siyeong Park (박시영) rewrites it in their own voice before any
> submission; the rule and the reason are in
> [`paper/AUTHORSHIP.md`](paper/AUTHORSHIP.md). It tracks the manuscript's abstract
> ([`paper/manuscript.md`](paper/manuscript.md)), which is the canonical version.

Satellite detection and district-level fire-danger forecasts were both operating
during the March 2025 Gyeongbuk wildfires, the largest on Korea's record by burned
area. Neither answered which way a rural household should walk **now**, or whether a
rescue crew can still reach the house. WildfireGuardian couples an event-held-out
ignition-probability model to a time-expanded pedestrian router and a rescue-ingress
calculation, and re-derives every published number from a committed artifact.

The spread model is deliberately ordinary — a gradient-boosted classifier over sixteen
public features, evaluated leave-one-fire-out on six real Korean fires, mean-of-folds
held-out ROC-AUC **0.890** (fold range 0.682–0.974; pooled out-of-fold 0.905, a
different quantity). **Its operating point is weak and is reported as such**: pooled
cell recall at the shipped threshold is **0.138**, and three of the six held-out fires
produce no true positive at all.

The coupling is nonetheless where the decision changes. On the canonical Yeongdeok
field, **42 of 458** scanned walk-network origins reach a refuge only under the
forecast-aware policy, and **2** reach no refuge under it, on a network
covering **32.6 %** of the predicted fire core whose bias runs in an unmeasured
direction. ⚠ **Two caveats bind that number and travel with it everywhere.** First,
the contrast is measured against a **fire-blind** baseline, so it does not separate
knowing where the fire *will be* from knowing where it *is*. Second, the
forecast-aware arm is graded on the **same field it planned on**, and that field is a
**leave-one-fire-out** model output rather than truth, so the oracle sits in the
grading: 42 is what the policy buys when its own prediction is believed, not what a
*noiseless* forecast would buy ([`docs/oracle_gap.md`](docs/oracle_gap.md)). Whether
that also makes 42 an **upper bound** on the real margin is an open question here and
not a result (**NH-053**). On a second region that separation has now been measured: a
present-perimeter opponent, which refuses what is burning now plus a fixed buffer and
needs no model at all, recovers most of what that region's fire-blind contrast credits
to the forecast ([`docs/present_perimeter_arm.md`](docs/present_perimeter_arm.md)).

Two further results are negative and are reported in full: the deadline-first dispatch
ordering the system ships never out-rescues nearest-first at the operating window, and
a geostationary detector sees these fires only at a sub-pixel size floor, tens of
minutes after their recorded occurrence time. On a six-event dataset the transferable
contribution is the **evaluation design** — paired contrasts, matched null controls,
and registries that keep withdrawn claims in the tree — rather than the model.

---

### Project overview

**WildfireGuardian** integrates satellite fire detection, **data-driven fire-spread
prediction**, and personalised evacuation routing — with the explicit goal of
protecting rural elderly Koreans during the "golden time" between ignition and safe
evacuation.

**Motivating event**: the March 2025 wildfire that ignited in 의성 (Uiseong),
Gyeongbuk and ran 의성→안동→청송→영양→영덕
(Uiseong→Andong→Cheongsong→Yeongyang→Yeongdeok) burned **99,289 ha** — the largest on
Korean record since statistics began in 1986, and 149 hours to 주불 진화 — killed **26**
people, **10 of them in 영덕 (Yeongdeok)** (영덕군 notice of 2025-04-29, quoted at p.9 of
the Greenpeace damage survey; a re-cited figure, not a survey result, against 9 in the
province's interim tally of 2025-03-30 — this repository keeps both and asserts neither
alone), the majority in their 60s–80s living in rural villages, and damaged **3,819
homes**, displacing 3,587 people from 2,246 households at a cost of ₩1.05 trillion
(Gyeongsangbuk-do final tally confirmed by 중앙재난안전대책본부;
[Asiae, 2025-05-06](https://view.asiae.co.kr/article/2025050610030818823)). Two stages of
that fire — `uiseong_andong_2025` and `yeongdeok_2025` — are among the six fires the
current model is validated on.

**Scope note — these figures sit on different bases; do not compare or divide them.**
(1) The **99,289 ha** above is this chain's *surveyed forest damage*, after the joint
agency survey ([Kyunghyang, 2025-04-17](https://www.khan.co.kr/article/202504171020011)).
(2) The **45,157 ha** widely quoted while the fire was still burning is the same chain's
*initial 「산불영향구역」 (fire-affected area) estimate* (산림청, 2025-03-27); the joint
survey came back at more than double it. (3) The **104,788 ha** across **347 fires** often
quoted alongside is the *nationwide total for the 2025 spring fire-prevention season,
24 January to 15 May*
([산림청 press release, 2025-05-16](https://www.pcccr.go.kr/base/board/read?boardManagementNo=43&boardNo=5375&menuLevel=2&menuNo=92)) —
a different **period**, body and basis, not merely a wider geography. So this repository
prints no "share of the national total". Putting (2) on top instead does not rescue the
ratio: (2) is not a parallel basis standing beside (1) but the earlier estimate the joint
survey overturned, so there is no like-for-like ratio here to print. Every figure here,
with its agency, scope and URL, is tabulated in `docs/data_sources.md`.

**Target venue**: 2026 Korea Code Fair SW공모전 (Korean student SW competition),
with the stretch goal of qualifying for ISEF in the Software Design (SFTD) category.

### Current model & results (Build B — `spread_v2`)

The **canonical model is Build B** (`src/wildfireguardian/spread_v2`) — the build
that produced **every** downstream result in this repo. It is a gradient-boosted
decision-tree classifier (sklearn `HistGradientBoostingClassifier`) that predicts, for each grid cell, the
probability `P(ignites by the next satellite overpass)`.

- **Evaluation — leave-one-group-out cross-validation (LOGO-CV; each fire held
  out as a *group*)** over **six real Korean fires**: gangneung_2023,
  hongseong_2023, miryang_2022, uiseong_andong_2025, uljin_samcheok_2022,
  yeongdeok_2025.
- **Mean-of-folds ROC-AUC = 0.89** (range **0.68–0.97**). The 0.68 fold
  (`gangneung_2023`, ~8 positives) is a tiny, noisy fold; excluding it, the other
  five average ≈ 0.93. **Mean-of-folds is the generalization figure.** The pooled
  out-of-fold AUC **0.905** (bootstrap 95 % CI [0.901, 0.909]) is reported only when
  labelled "pooled" and is **not** the generalization metric.
- ⚠ **Severity vs wind direction — measured, NOT established.** Summed
  fire-weather **severity** permutation importance is **0.102** against
  `wind_alignment` (direction) **0.0023**. Earlier versions led with the ~44×
  ratio; it is withdrawn as a headline for three reasons, each checkable:
  1. it sets a **six-feature sum** against a **single variable**;
  2. ERA5 is **0.25° (~28 km)**, so the severity features are near-uniform across
     one fire at one instant — they discriminate among *days and fires*, not
     *within-overpass spatial* placement
     ([`docs/ROUTING_INTEGRATION_REPORT.md`](docs/ROUTING_INTEGRATION_REPORT.md) §"Honest nuance");
  3. it is a **single point estimate** whose spread across seeds and folds was
     never measured ([`docs/auc_intervals.md`](docs/auc_intervals.md)).

  **It does not mean wind direction is unimportant** — it means this instrument
  cannot see it.
- ⚠ **And the top-ranked feature makes the model WORSE out-of-fold.**
<!-- collision-ok: 0.077 — permutation IMPORTANCE of days_since_rain, not the drop-delta wxdep_drop_days_since_rain_mean_delta (0.027). Different measurements of the same feature. -->
  `days_since_rain` ranks first at **+0.077**, but *dropping* it **raises**
  mean-of-folds AUC by **+0.0270** and far-band by **+0.0533**. For three of six
  fires the ERA5 window holds **zero** wet samples, so the feature anchors to the
  window START — an acquisition parameter, not rain — for half the training set.
  *(An earlier revision said it "equals the window length exactly"; the canonical
  table measures otherwise — corrected 2026-08-10, measured values in
  [`docs/weather_dependency.md`](docs/weather_dependency.md) §②.)* PHASE 14.
- **Scale**: 16 features, 151,904 rows / 2,989 positives (~1.97 %), seed 20250603,
  EPSG:5179.
- **Far-band (>3 km) mean-of-folds AUC = 0.925** (n=3; the "can it predict *reach*?"
  question — ⚠ a never-committed pre-correction re-run; the committed
  `auc_intervals.json` (corrected lineage) reads **0.904 ± 0.100**), pooled 0.877 — ⚠ the corrected-DEM re-run reads **0.8408** pooled;
  quote 0.877 only with that caveat ([`docs/MODEL_CARD.md`](docs/MODEL_CARD.md),
  DEM-correction section). Forward-simulated **footprint IoU ≈ 0.40** (Yeongdeok,
  3–12 h) — roughly **4×** the Rothermel surface model's **~0.09**, i.e. it captures
  the crown-fire / spotting regime that surface physics misses.

| held-out fire | ROC-AUC | DeLong 95 % CI |
|---|---|---|
| miryang_2022 | 0.974 | [0.941, 0.989] |
| hongseong_2023 | 0.945 | [0.916, 0.964] |
| yeongdeok_2025 (the demonstration fire) | 0.941 | [0.936, 0.946] |
| uljin_samcheok_2022 | 0.918 | [0.911, 0.924] |
| uiseong_andong_2025 | 0.878 | [0.871, 0.884] |
| gangneung_2023 (~8 positives — noisy) | 0.682 | [0.577, 0.771] |

`[ROC-AUC src: data/processed/spread_v2_lofo.json; DeLong CIs: scripts/auc_intervals.py; see docs/MODEL_CARD.md]`

> **All six folds are statistically significant vs AUC = 0.5** (`gangneung_2023`
> p = 2.7×10⁻⁴; the other five p ≪ 0.001). The per-fire DeLong CIs above and those
> significance tests come from the gated re-run `scripts/auc_intervals.py`, which
> reproduces pooled 0.905 / mean-of-folds 0.890 **before** reporting and **STOPs
> cleanly (exit 2)** if the FIRMS/ERA5/DEM bundle is absent rather than fabricate
> numbers. The statistics are unit-tested (`tests/test_auc_stats.py`). Method +
> limitations: [`docs/auc_intervals.md`](docs/auc_intervals.md).
>
> **Standard ML baselines** on the identical 16 features / folds / seed (20250603) —
> to answer "you only beat a bad physics model" honestly:
>
> | model | mean-of-folds AUC ± SD | pooled |
> |---|---|---|
> | random forest | 0.914 ± 0.044 | 0.896 |
> | logistic regression | 0.903 ± 0.060 | 0.826 |
> | **hist_gbm (ours)** | **0.894 ± 0.092** | **0.904** |
>
> ⚠ Values are the committed artifact `data/processed/ml_baselines.json`
> (2026-08-10, corrected-DEM bundle; an earlier revision carried a
> never-committed pre-correction run's values — same ordering conclusions).
> Random forest edges us on mean-of-folds. Calibration is **not** the
> differentiator either — measured pooled Brier/ECE: GBM 0.0183/0.0086 vs
> random forest **0.0174/0.0068** (`calibration_metrics.json`). What keeps
> the GBM: the **pooled-AUC edge**, **inference speed**, **native NaN
> handling**, and that it yields a **permutation-importance ranking** at all
> (the "severity ≫ direction" reading of that ranking is withdrawn — see
> above). Values reproduce via `scripts/ml_baselines.py`
> ([`docs/baselines.md`](docs/baselines.md)).

### System architecture (high level)

```
                  ┌───────────────────────────────────────────────┐
                  │           Satellite fire detection            │
                  │     (NASA FIRMS VIIRS + MODIS, near-real)     │
                  └────────────────────┬──────────────────────────┘
                                       │ ignition points
                  ┌────────────────────▼──────────────────────────┐
                  │           Fuel / terrain / weather state       │
                  │  ESA WorldCover (fuel) + SRTM (DEM) + ERA5 (wx) │
                  └────────────────────┬──────────────────────────┘
                                       │
                  ┌────────────────────▼──────────────────────────┐
                  │  Data-driven per-cell ignition model (spread_v2)│
                  │  gradient-boosted trees · LOGO-CV · calibrated P│
                  └────────────────────┬──────────────────────────┘
                                       │ hazard surface
                  ┌────────────────────▼──────────────────────────┐
                  │   Elderly- & rescue-aware evacuation routing   │
                  │            (time-dependent)                    │
                  └────────────────────┬──────────────────────────┘
                                       │
                  ┌────────────────────▼──────────────────────────┐
                  │      Personalised alerts & route delivery     │
                  └───────────────────────────────────────────────┘
```

See [`docs/architecture.md`](docs/architecture.md) for the long form.

### Current status

**Research PoC (proof-of-concept).** Not an unfinished "alpha": a data-driven
model validated on six real fires, with downstream routing working on top of it.
This repository provides:

- **Data-driven per-cell ignition model (`spread_v2`, Build B)** — LOGO-CV-validated
  on six real fires (mean-of-folds ROC-AUC 0.89), calibrated probabilities and
  permutation importance. ⚠ The "severity ≫ direction" claim is **withdrawn as
  not established** — a six-feature sum against one variable, on a 0.25° (~28 km)
  grid that does not resolve local wind. It does NOT mean direction is
  unimportant. `src/wildfireguardian/spread_v2/`
- **Real-data ingestion** — NASA FIRMS detections + SRTM DEM + ESA WorldCover
  fuel + ERA5 weather (`spread_v2/data.py`). The FIRMS bundle is git-ignored and
  downloaded separately.
- **Validation statistics** — DeLong CI / significance, bootstrap, permutation
  test, mean-of-folds t-interval (`validation/auc_stats.py`, unit-tested);
  gated re-run `scripts/auc_intervals.py`.
- **Standard ML baseline comparison** — logistic / random forest on identical
  features/folds/seed (`scripts/ml_baselines.py`, `docs/baselines.md`).
- **Rescue-aware evacuation routing** — future-front aware + vehicle-ingress
  survival (`wildfireguardian.routing.rescue`).
- **RegionConfig + vulnerability scaffolding** — Yeongdeok 2025, Uljin/Samcheok
  2022, Goseong 2019 (`utils/regions.py`, `utils/vulnerability.py`).
- **Rothermel physics fire-spread model** — preserved as the *initial* approach
  (see [Research log](#research-log--superseded-approaches-physics-model)).

**Unit tests**: the full suite passes — **1,021 passed, 3 skipped** (measured
2026-08-10 with the full data bundle present; data-dependent tests self-skip on
a fresh clone, so a bundle-absent run passes with more skips). *(An earlier
revision of this line carried the Round-2 count, 377/2.)*

This is **not** production software. It is a single-fire (영덕) downstream PoC with
synthetic-and-tagged auxiliary routing data, and must never be the sole input to a
public evacuation order without expert review.

### Data sources

The public datasets the **canonical `spread_v2` pipeline actually uses**. The
repository distributes none of them; users download into `data/raw/` at run time.

- **NASA FIRMS** (VIIRS S-NPP/NOAA-20 + MODIS active-fire detections): <https://firms.modaps.eosdis.nasa.gov/>
- **SRTM** (NASA, ~30 m DEM / terrain): <https://earthexplorer.usgs.gov/>
- **ESA WorldCover 2021** (10 m land cover → fuel burnability): <https://esa-worldcover.org/>
- **ECMWF ERA5** (reanalysis weather: 10 m winds, 2 m temp/dewpoint, precip), Copernicus C3S / CDS.
- Routing layer: **OpenStreetMap** (walk/drive networks via OSMnx),
  **공공데이터포털** national shelter standard data (행정안전부),
  **119안전센터** responder depots (소방청) — each with a real-source loader and a
  clearly-labelled synthetic fallback.

The full data catalogue (licensing + access) is in
[`docs/data_sources.md`](docs/data_sources.md).

### Reproduce

```bash
git clone https://github.com/sparkxt-0318/wildfireguardian.git
cd wildfireguardian
python -m venv .venv && source .venv/bin/activate

# Full dependency set the canonical scripts need. (The editable install
# `pip install -e .` alone MISSES scikit-learn / xgboost / xarray / pyproj /
# rasterio, and neither pyproject extras nor requirements.txt include h5netcdf/h5py.)
pip install -e ".[ml,geospatial]"     # numpy scipy pandas shapely matplotlib pydantic
                                      #  + scikit-learn xgboost xarray pyproj rasterio ...
pip install h5netcdf h5py             # ERA5 NetCDF readers (the missing pieces)

# Place the data bundle (git-ignored, absent in a fresh clone):
unzip firms_data.zip -d data/raw/     # or: export WFG_FIRMS_DIR=/path/to/firms

# Re-run the canonical LOGO-CV; the consistency gate reproduces
# pooled 0.905 / mean-of-folds 0.890 before any interval is reported:
python scripts/auc_intervals.py       # per-fire DeLong CIs + significance vs 0.5
python scripts/ml_baselines.py        # logistic / random_forest vs GBM (same features/folds/seed)

pytest -q                             # unit tests (no data needed; only FIRMS/SRTM-
                                      #  dependent tests skip when the bundle is absent)
```

Without the bundle both scripts **STOP cleanly (exit 2)** and report nothing rather
than fabricate AUCs (the statistics themselves are still validated by
`pytest tests/test_auc_stats.py`). The rescue-routing demo additionally needs
`pip install -e ".[routing]"` (osmnx, networkx).

### Rescue-aware evacuation routing

On top of the future-aware router, `wildfireguardian.routing.rescue` adds a
tightly-scoped **rescue-awareness** layer: it routes the vulnerable elderly only to
refuges whose **vehicle access road survives the predicted fire**, and — when a
resident cannot self-evacuate — computes the **responder's** ingress route instead,
always reporting honestly who cannot be reached.

**Honest four-way origin split on the real-OSM 영덕 PoC (sums to N = 439):**

| outcome | count |
|---|---:|
| already safe (naive walk works) | 262 |
| saved by routing to a rescue-reachable refuge | 10 |
| no safe pedestrian route — but a responder can reach (dispatched) | 143 |
| **no surviving vehicle ingress — UNREACHABLE (reported, not imputed)** | **24** |

Contrasts (the robust result; absolute magnitudes are illustrative on a single-fire
PoC with a real OSM road/refuge/depot network but synthetic fire hazard + terrain):
the walking-failure rate **w ≈ 11 %** (9–17 % across thresholds) is the model-derived
figure and does not depend on the immobility assumption. By contrast, the
**167 / 439 = 38 %** rescue-needed share is a scenario estimate conditional on an
assumed immobility rate of 0.30, not an observed population characteristic.

> The resident-side exposure comparison is **not paired** (the origin sets differ), so
> we do not interpret it as a causal effect. What *is* verified on paired samples is the
> responder side: across the same 143 origins, exposure falls from **6.12 → 1.71**
> prob·min (~72 % lower) versus a fire-blind shortest path.

A verification pass
(`scripts/verify_rescue_routing.py`) re-derives the split and runs a full-N 2-D
sweep whose baseline cell equals the headline (asserted); the robust finding is that
**unreachable starts rise monotonically with dispatch delay** (**6 → 66** as delay
goes 0 → 60 min; `rescue_unreachable_delay_row_cutoff_0p7` = [6, 11, 24, 51, 66] in
`data/processed/rescue_verify.json`, the same **439-series** run as the 143 origins
and 6.12 → 1.71 above, all on **real roads**). ⚠ Until 2026-09-03 this line read
**6 → 34**, which is the same bracket on the **pre-flip synthetic baseline**
— the superseded 452-series: [6, 15, 20, 25, 34], N = 452, unreachable 20 — preserved at
`data/processed/rescue_baseline_synthetic/rescue_verify.json` — the lineage
[`docs/rescue_routing.md`](docs/rescue_routing.md) documents behind its do-not-cite
banner. Both brackets are real runs of the same script and
[`docs/REPORT_ROUND2_P1.md`](docs/REPORT_ROUND2_P1.md) reports them side by side;
neither is a typo, and this paragraph is real-roads throughout. See
[`docs/ssot_audit_2026-09-03.md`](docs/ssot_audit_2026-09-03.md) §1.
The downstream capacity/triage is a **PoC parameter, not measured 영덕
fire-service capacity** — report the curve, not a single "X rescued". Full methods +
data provenance: [`docs/rescue_routing.md`](docs/rescue_routing.md).

```bash
python scripts/run_rescue_routing.py            # four-way split + exposure + sensitivity
python scripts/make_rescue_figures.py           # docs/figures/rescue_*.png
python scripts/verify_rescue_routing.py             # reconciled baseline + vehicle×delay sweep
python scripts/verify_rescue_routing.py --sweep fc  # immobile×walk-cutoff assumption sweep
pytest tests/test_rescue_routing.py -q          # incl. the orientation regression test
```

![rescue map](docs/figures/rescue_map.png)

![rescue four-way split](docs/figures/rescue_four_way.png)

![rescue 2-D sensitivity](docs/figures/rescue_sweep_2d.png)

### Citation

```bibtex
@software{wildfireguardian2026,
  title  = {WildfireGuardian: Wildfire spread forecasting and household-level
            evacuation and rescue routing for rural elderly Koreans},
  author = {{WildfireGuardian Project Contributors}},
  year   = {2026},
  note   = {2026 Korea Code Fair SW공모전 submission.},
  url    = {https://github.com/sparkxt-0318/wildfireguardian}
}
```

### Scientific references

- DeLong, E.R., DeLong, D.M., & Clarke-Pearson, D.L. (1988). *Comparing the areas
  under two or more correlated ROC curves.* Biometrics 44(3).
- Sun, X., & Xu, W. (2014). *Fast implementation of DeLong's algorithm for the
  area under correlated ROC curves.* IEEE Signal Processing Letters 21(11).
- Rothermel, R.C. (1972). *A mathematical model for predicting fire spread in
  wildland fuels.* USDA Forest Service Research Paper INT-115. *(physics model —
  see research log)*
- Andrews, P.L. (2018). *The Rothermel surface fire spread model and associated
  developments.* USDA Forest Service GTR RMRS-GTR-371. *(physics model)*

### License

MIT. See [`LICENSE`](LICENSE).

---

## Research log / superseded approaches (physics model)

> **This section is a preserved research record, not the current state.** It
> documents an earlier mechanistic (Rothermel-based) fire-spread track that was
> **superseded** by the data-driven Build B model above. It is kept deliberately,
> as evidence of self-correction — the failures here *motivated* the pivot.

### The pivot, in one paragraph

An early **Rothermel surface-fire** model (with a Huygens-elliptical cellular
automaton, Monte-Carlo ensembling, and a Korean *Pinus densiflora* fuel analog)
was the project's first spread engine. With physically-correct (midflame-adjusted)
wind it **under-predicted the Yeongdeok front by ~90 %** and captured only **~9 %**
of the burned area — it could not reproduce the crown/spotting-driven run. A
forensic audit also retracted an apparent "54 % area capture" crown-fire result as
a **moisture-conflation bug** (surface drought-LFMC ~40 % was fed into the crown
foliar-moisture check, which should use the measured ~119 % live-conifer value);
fixing the conflation collapsed the number back to the ~9 % surface baseline. These
honest negative results — *the physics-based prediction did not work* — are what
motivated the move to the data-driven, LOGO-CV-validated `spread_v2` model.

### What was learned / kept

- The **physics modules remain sound and are retained** (topographic wind, Van
  Wagner + Cruz/Alexander crown initiation, Albini spotting, a WAF wind
  correction, multi-class Rothermel weighting); only the *headline capture claim*
  was wrong, and it was caught and reported pre-writeup rather than tuned to
  survive.
- **Data-integrity bugs were found and fixed, not buried.** A raster-orientation
  bug had silently deleted **~85 % of `uljin_samcheok_2022`'s ignition points**; it
  was traced, fixed for good with an orientation-safe sampler
  (`src/wildfireguardian/spread_v2_xgb/grid.py`), and locked down with a regression
  test (`tests/test_rescue_routing.py::test_sampling_orientation_matches_raster_convention`).
- **Crown initiation is acutely sensitive to canopy base height (CBH)** — a real,
  reportable finding (stand structure governs catastrophe potential and is
  raisable by thinning). See
  [`docs/methodology/crown_initiation_sensitivity.md`](docs/methodology/crown_initiation_sensitivity.md).
- The earlier mentor-refocus "future-front-aware routing spine" is unaffected and
  evolved into the current rescue-aware router.

### Where to read the full self-correction trail

- [`docs/OVERNIGHT_REPORT_SESSION7.md`](docs/OVERNIGHT_REPORT_SESSION7.md) — the
  diagnostic that retracted the 54 % crown result as a foliar-moisture artifact.
- [`docs/OVERNIGHT_REPORT_SESSION6.md`](docs/OVERNIGHT_REPORT_SESSION6.md) — the
  fire-type physics (crown/spotting/topographic wind) that the audit corrected.
- [`docs/methodology/validation_limitations.md`](docs/methodology/validation_limitations.md)
  — the reviewer-defense on what was synthetic vs real in the physics era.

### Provenance note — two builds exist (A vs B)

An earlier project brief cited **0.834 / 0.80 / 0.32** (ROC-AUC / far-band /  <!-- forbidden-ok: 0.834 -->
footprint IoU) from a **different reconstruction** ("Build A": different fire set,
19 features, seed 42). Build A and the canonical Build B are **two independent
reconstructions and are not a like-for-like comparison** — the 0.834-vs-0.905 gap  <!-- forbidden-ok: 0.834 -->
must **not** be read as "B is better". ⚠ *A sentence here used to add that both
builds "corroborate the central finding (severity ≫ direction)" — that finding
is WITHDRAWN as not established (see the permutation-importance note above), and
what the two builds jointly show is only that the measured ratio reproduces
across implementations; both share the same 0.25° weather product, which is one
of the withdrawal's reasons.* The full old→new correction
mapping is in [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md).

### spread_v2_xgb — superseded XGBoost re-train (legacy)

The **canonical** data-driven spread model is the `spread_v2` package
(`src/wildfireguardian/spread_v2/`) — the build that produces every live result
(pooled LOGO-CV AUC **0.905**, seed `20250603`), driven end-to-end by
[`scripts/run_routing_integration.py`](scripts/run_routing_integration.py) and
[`scripts/calibration_metrics.py`](scripts/calibration_metrics.py). See
[`docs/REPRODUCE.md`](docs/REPRODUCE.md) to reproduce it from a fresh clone.

An **earlier** XGBoost re-train build lives at  <!-- forbidden-ok: XGBoost -->
`src/wildfireguardian/spread_v2_xgb/`. It is **superseded and not part of the live
pipeline** — no runtime/pipeline module imports it. Its "Deliverable 0–6" driver
scripts, `scripts/spread_v2/00_audit.py … 06_figures.py`, still `import
wildfireguardian.spread_v2_xgb`; each now carries a **`LEGACY / SUPERSEDED`
header banner** and is kept for **provenance only** — do not run them as part of
reproduction. They produced the research-history summaries under
`data/processed/spread_v2/*.json` (audit, LOGO-CV/comparison/importance metrics),
which remain committed as evidence of the re-train. The only other reference is
`tests/test_spread_v2_xgb.py`, a pinned regression test that freezes the old
build's behaviour. **Canonical package = `spread_v2`; never substitute
`spread_v2_xgb`.**
