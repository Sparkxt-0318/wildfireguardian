# WildfireGuardian

> Multi-scale wildfire forecasting and personalized evacuation system, focused on
> protecting rural elderly Koreans.
>
> 농촌 고령층 보호를 위한 다중규모 산불 예측·개인화 대피 안내 시스템.

![status](https://img.shields.io/badge/status-research%20PoC-orange)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## TL;DR

- **Current model (Build B — `spread_v2`)**: a data-driven, per-cell wildfire
  ignition-probability model (gradient-boosted trees) validated by
  **leave-one-fire-out** cross-validation on **six real Korean wildfires**.
  **Mean-of-folds ROC-AUC = 0.89** (range 0.68–0.97; pooled out-of-fold 0.905).
- **Headline finding**: fire-weather **severity** (the weather feature group,
  incl. wind speed) dominates wind **direction** by **~44×** in permutation
  importance; **`days_since_rain` is the single strongest feature**.
- The calibrated `P(ignite)` surface is coupled into **elderly-aware and
  rescue-aware evacuation routing** (the project's core systems contribution).
- **Intellectual-honesty record**: an earlier Rothermel-based *physics* model
  captured only **~9 %** of the burned area (a documented moisture-conflation
  bug), which **motivated the pivot** to this data-driven model. That history is
  preserved below in **[Research log / superseded approaches](#research-log--superseded-approaches-physics-model)**
  — it is no longer the current state.

> **Canonical source of truth for every number below:** [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md)
> and [`data/processed/spread_v2_lofo.json`](data/processed/spread_v2_lofo.json).
> No model code, results, or numbers were changed to write this README.

---

### 프로젝트 개요

**WildfireGuardian** 는 산불 발화부터 대피 완료까지의 "골든타임" 동안 위성 화재
탐지·데이터 기반 화재 확산 예측·개인 맞춤형 대피 경로 안내를 통합 제공하는 연구용
시스템입니다.

**보호 대상**: 한국 농촌의 고령층(60–80대). 2025년 3월 경북 **의성**에서 발화해
**의성→안동→청송→영양→영덕**으로 번진 산불(사망자 **27명**, 그중 **영덕 8명**, 대부분
60–80대 고령자; 약 **116,000 ha** 소실, 주택 **4,000여 채** 파손)의 재발 방지·대응
개선을 동기로 삼습니다. 〔출처: 한겨레·세계일보·서울환경연합〕 ("30명 이상"은 2025년
*전국* 산불 전체 사망자 합계로, 범위가 다른 수치입니다.)

**대회**: 2026 대한민국 학생 SW공모전(Korea Code Fair) → ISEF (Systems Software)
출전을 목표로 합니다.

### 현재 모델과 결과 (Build B — `spread_v2`, 데이터 기반)

본 저장소의 **정식(canonical) 모델은 Build B** (`src/wildfireguardian/spread_v2`)
이며, 모든 후속 결과(라우팅 노출도, 구조 4-구분 등)를 산출한 모델입니다. 한 산불의
다음 위성 통과 시점에 각 격자 셀이 발화(탐지)될 확률 `P(ignite)` 를 예측하는
그래디언트 부스팅(XGBoost 계열) 분류기입니다.

- **평가 — 한 산불씩 제외 교차검증 (LOFO; 각 산불을 그룹으로 묶어 통째로 제외하는
  leave-one-group-out / LOGO-CV)**: 6개 실제 산불(gangneung_2023, hongseong_2023,
  miryang_2022, uiseong_andong_2025, uljin_samcheok_2022, yeongdeok_2025).
- **폴드 평균 ROC-AUC = 0.89** (범위 0.68–0.97). `gangneung_2023` 폴드(0.68)는 양성
  약 8건(탐지 약 17건)뿐인 소규모·잡음 폴드이며, 이를 제외한 다섯 산불 평균은 약
  0.93 입니다. **일반화 지표로는 폴드 평균을 보고**합니다. 전체 보류예측 통합
  **pooled = 0.905** (부트스트랩 95 % CI [0.901, 0.909])는 *pooled* 로 명시해서만
  사용하며, 일반화 지표가 아닙니다.
- **핵심 발견 — 세기(severity) ≫ 풍향(direction)**: 순열 중요도에서 화재기상
  **세기**(`days_since_rain`, `vpd_kpa`, `rh_pct`, `temp_c`, `precip_24h_mm`,
  풍속 `wind_speed_ms`) 합 0.102 vs 풍향 정렬 `wind_alignment` 0.0023 → **약 44배**.
  단일 최강 특징은 **`days_since_rain`** (0.077) 입니다.
- **규모**: 16개 특징, 151,904행 / 양성 2,989(약 1.97 %), 시드 20250603,
  좌표계 EPSG:5179.
- **원거리(>3 km) 폴드 평균 AUC = 0.925** (n=3; 화선의 *도달* 예측력), 통합 pooled
  0.877. 순방향 모의 화선 **footprint IoU ≈ 0.40** (영덕, 3–12시간) — 물리(Rothermel)
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
> | 랜덤포레스트 | 0.920 ± 0.036 | 0.898 |
> | 로지스틱 회귀 | 0.903 ± 0.060 | 0.826 |
> | **XGBoost/GBM (본 모델)** | **0.889 ± 0.107** | **0.905** |
>
> 폴드 평균에서는 랜덤포레스트가 근소 우위이나, **보정된 확률**(라우터가 실제
> `P(ignite)` 를 소비) · **추론 속도** · **해석가능성**(순열 중요도가 "세기 ≫ 풍향"
> 발견을 제공)을 근거로 GBM을 정식 모델로 채택했습니다. 베이스라인 수치는 동일
> 게이트형 재실행(`scripts/ml_baselines.py`)으로 재현합니다. 방법론:
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
            │   XGBoost 계열 · LOFO 검증 · 보정된 P(ignite) │
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
  대한 LOFO 검증(폴드평균 ROC-AUC 0.89), 보정된 확률, 순열 중요도 기반 "세기≫풍향"
  발견. `src/wildfireguardian/spread_v2/`
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

### 재현 (Reproduce)

```bash
git clone https://github.com/sparkxt-0318/wildfireguardian.git
cd wildfireguardian
python -m venv .venv && source .venv/bin/activate

# 정식 분석 스크립트의 전체 의존성. (편집가능 설치 `pip install -e .` 만으로는
# scikit-learn / xgboost / xarray / pyproj / rasterio 등이 빠집니다.)
pip install -e ".[ml,geospatial]"     # numpy scipy pandas shapely matplotlib pydantic
                                      #  + scikit-learn xgboost xarray pyproj rasterio ...
pip install h5netcdf h5py             # ERA5 NetCDF 리더 (extras·requirements.txt 누락분)

# 데이터 번들 배치 (저장소에 없음 — git-ignore):
unzip firms_data.zip -d data/raw/     # 또는: export WFG_FIRMS_DIR=/path/to/firms

# 정식 LOFO 재실행 → 일치성 게이트가 pooled 0.905 / 폴드평균 0.890 재현
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

합성 영덕 PoC 4-구분(합 = N = 452): 원래 안전 154 · 구조가능 대피소로 구조 34 ·
도보 불가(구조대 출동) 244 · **차량 접근 불가(도달 불가) 20**. 도보 자력대피 실패율
**w ≈ 40 %**(임계값에 따라 33–45 %)는 10시간 보행 예산에서도 거동불능 가정과 무관하게
유지됩니다. 출동 지연 **0→60분**이면 도달 불가 출발지가 **6→34**로 늘어납니다.
예측 기반 주민 경로는 예측 없음 경로 대비 노출 **~85 % 감소**(24.06→3.55 prob·min),
생존-인지 구조대 진입은 최단경로 대비 노출 **~54 % 감소**(0.172→0.079 prob·min).
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
  title  = {WildfireGuardian: Multi-scale wildfire forecasting and personalised
            evacuation for rural elderly Koreans},
  author = {{WildfireGuardian Project Contributors}},
  year   = {2026},
  note   = {2026 Korea Code Fair SW공모전 submission.},
  url    = {https://github.com/sparkxt-0318/wildfireguardian}
}
```

---

### Project overview

**WildfireGuardian** integrates satellite fire detection, **data-driven fire-spread
prediction**, and personalised evacuation routing — with the explicit goal of
protecting rural elderly Koreans during the "golden time" between ignition and safe
evacuation.

**Motivating event**: the March 2025 wildfire that ignited in 의성 (Uiseong),
Gyeongbuk and ran 의성→안동→청송→영양→영덕
(Uiseong→Andong→Cheongsong→Yeongyang→Yeongdeok) killed **27** people — **8 in 영덕
(Yeongdeok) alone** — the majority in their 60s–80s living in rural villages, burning
**~116,000 ha** and destroying **4,000+ homes** (sources: 한겨레 / 세계일보 /
서울환경연합). Two stages of that fire — `uiseong_andong_2025` and `yeongdeok_2025` —
are among the six fires the current model is validated on. (The widely-quoted "30+"
figure is the *nationwide* 2025 all-fires death toll — a broader, different scope.)

**Target venue**: 2026 Korea Code Fair SW공모전 (Korean student SW competition),
with the stretch goal of qualifying for ISEF in the Systems Software category.

### Current model & results (Build B — `spread_v2`)

The **canonical model is Build B** (`src/wildfireguardian/spread_v2`) — the build
that produced **every** downstream result in this repo. It is a gradient-boosted
decision-tree classifier (XGBoost-class) that predicts, for each grid cell, the
probability `P(ignites by the next satellite overpass)`.

- **Evaluation — leave-one-fire-out (LOFO; each fire held out as a *group*, i.e.
  leave-one-group-out / LOGO-CV)** over **six real Korean fires**: gangneung_2023,
  hongseong_2023, miryang_2022, uiseong_andong_2025, uljin_samcheok_2022,
  yeongdeok_2025.
- **Mean-of-folds ROC-AUC = 0.89** (range **0.68–0.97**). The 0.68 fold
  (`gangneung_2023`, ~8 positives) is a tiny, noisy fold; excluding it, the other
  five average ≈ 0.93. **Mean-of-folds is the generalization figure.** The pooled
  out-of-fold AUC **0.905** (bootstrap 95 % CI [0.901, 0.909]) is reported only when
  labelled "pooled" and is **not** the generalization metric.
- **Headline finding — severity ≫ wind direction**: summed fire-weather
  **severity** permutation importance **0.102** vs `wind_alignment` (direction)
  **0.0023** → a **~44×** ratio. The **single strongest feature is
  `days_since_rain`** (0.077). The weather/severity group includes wind *speed*
  (`wind_speed_ms`); the *control* it dominates is wind *direction*.
- **Scale**: 16 features, 151,904 rows / 2,989 positives (~1.97 %), seed 20250603,
  EPSG:5179.
- **Far-band (>3 km) mean-of-folds AUC = 0.925** (n=3; the "can it predict *reach*?"
  question), pooled 0.877. Forward-simulated **footprint IoU ≈ 0.40** (Yeongdeok,
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
> | random forest | 0.920 ± 0.036 | 0.898 |
> | logistic regression | 0.903 ± 0.060 | 0.826 |
> | **XGBoost/GBM (ours)** | **0.889 ± 0.107** | **0.905** |
>
> Random forest edges us on mean-of-folds; we keep the GBM for its **calibrated
> probabilities** (the router consumes a real `P(ignite)`), **inference speed**, and
> **interpretability** (permutation importance is what surfaced "severity ≫
> direction"). Values reproduce via `scripts/ml_baselines.py`
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
                  │  gradient-boosted trees · LOFO · calibrated P   │
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

- **Data-driven per-cell ignition model (`spread_v2`, Build B)** — LOFO-validated
  on six real fires (mean-of-folds ROC-AUC 0.89), calibrated probabilities, the
  "severity ≫ direction" permutation-importance finding.
  `src/wildfireguardian/spread_v2/`
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

**Unit tests**: the full suite passes — **377 passed, 2 skipped** in a run with the
data bundle absent (the only skips are real-data-dependent: FIRMS/SRTM bundles not
present in a fresh clone), across 31 test modules.

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

# Re-run the canonical LOFO; the consistency gate reproduces
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

**Honest four-way origin split on the synthetic 영덕 PoC (sums to N = 452):**

| outcome | count |
|---|---:|
| already safe (naive walk works) | 154 |
| saved by routing to a rescue-reachable refuge | 34 |
| no safe pedestrian route — but a responder can reach (dispatched) | 244 |
| **no surviving vehicle ingress — UNREACHABLE (reported, not imputed)** | **20** |

Contrasts (the robust result; absolute magnitudes are illustrative on a single-fire
PoC + synthetic auxiliary inputs): the on-foot self-evacuation **failure rate
w ≈ 40 %** (33–45 % across thresholds) holds even with a 10-hour walking budget and
independent of the immobility assumption; the future-aware resident route cuts
predicted-hazard exposure **~85 %** vs naive (24.06 → 3.55 prob·min), and the
survival-aware responder ingress cuts exposure **~54 %** vs a fire-blind shortest
path (0.172 → 0.079 prob·min). A verification pass
(`scripts/verify_rescue_routing.py`) re-derives the split and runs a full-N 2-D
sweep whose baseline cell equals the headline (asserted); the robust finding is that
**unreachable starts rise monotonically with dispatch delay** (6 → 34 as delay goes
0 → 60 min). The downstream capacity/triage is a **PoC parameter, not measured 영덕
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
  title  = {WildfireGuardian: Multi-scale wildfire forecasting and personalised
            evacuation for rural elderly Koreans},
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
motivated the move to the data-driven, LOFO-validated `spread_v2` model.

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

An earlier project brief cited **0.834 / 0.80 / 0.32** (ROC-AUC / far-band /
footprint IoU) from a **different reconstruction** ("Build A": different fire set,
19 features, seed 42). Build A and the canonical Build B are **two independent
reconstructions and are not a like-for-like comparison** — the 0.834-vs-0.905 gap
must **not** be read as "B is better". Both nonetheless corroborate the central
finding (fire-weather *severity* ≫ wind *direction*). The full old→new correction
mapping is in [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md).

### spread_v2_xgb — superseded XGBoost re-train (legacy)

The **canonical** data-driven spread model is the `spread_v2` package
(`src/wildfireguardian/spread_v2/`) — the build that produces every live result
(pooled LOFO AUC **0.905**, seed `20250603`), driven end-to-end by
[`scripts/run_routing_integration.py`](scripts/run_routing_integration.py) and
[`scripts/calibration_metrics.py`](scripts/calibration_metrics.py). See
[`docs/REPRODUCE.md`](docs/REPRODUCE.md) to reproduce it from a fresh clone.

An **earlier** XGBoost re-train build lives at
`src/wildfireguardian/spread_v2_xgb/`. It is **superseded and not part of the live
pipeline** — no runtime/pipeline module imports it. Its "Deliverable 0–6" driver
scripts, `scripts/spread_v2/00_audit.py … 06_figures.py`, still `import
wildfireguardian.spread_v2_xgb`; each now carries a **`LEGACY / SUPERSEDED`
header banner** and is kept for **provenance only** — do not run them as part of
reproduction. They produced the research-history summaries under
`data/processed/spread_v2/*.json` (audit, LOFO/comparison/importance metrics),
which remain committed as evidence of the re-train. The only other reference is
`tests/test_spread_v2_xgb.py`, a pinned regression test that freezes the old
build's behaviour. **Canonical package = `spread_v2`; never substitute
`spread_v2_xgb`.**
