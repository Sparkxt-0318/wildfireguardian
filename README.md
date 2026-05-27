# WildfireGuardian — 산불 골든타임

> Multi-scale wildfire forecasting and personalized evacuation system for the protection of rural elderly Koreans.
>
> 농촌 고령층을 위한 다중규모 산불 예측·개인화 대피 안내 시스템.

![status](https://img.shields.io/badge/status-research%20prototype-orange)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## 🇰🇷 한국어

### 프로젝트 개요

**WildfireGuardian** 은 산불 발생부터 대피 완료까지의 "골든타임" 동안 위성 화재 탐지·물리 기반 화재 확산 모델·연기 확산 모델·개인 맞춤형 대피 경로 안내를 통합 제공하는 연구용 시스템입니다.

**보호 대상**: 한국 농촌의 고령층(60–80대). 2025년 3월 22–28일 영남권 산불 (사망자 30 명 이상, 대부분 60–80 대 고령자) 의 재발 방지·대응 개선을 동기로 삼습니다.

**대회**: 2026년 대한민국 학생 SW공모전 → ISEF (Systems Software) 출전 목표. 제출 마감 2026-06-13.

### 시스템 구성

| 모듈 | 역할 | 과학적 근거 |
|------|------|-------------|
| `fire_detection` | 위성 (VIIRS, MODIS) 발화점 탐지 및 시간 정합 | NASA FIRMS 알고리즘 |
| `lfmc_model` | 생체 수분 (Live Fuel Moisture Content) 추정 | Sentinel-2 NDWI/NDVI 기반 회귀 |
| `spread_model` | 지표 화재 확산 시뮬레이션 | Rothermel (1972), Finney FARSITE (1998) |
| `smoke_dispersion` | 연기 확산 / PM2.5 노출 | Gaussian plume + HYSPLIT 결합 |
| `routing` | 고령자 가중치 반영 대피 경로 | 시간 의존 다익스트라 |
| `delivery` | 다채널 알림 (SMS, 마을 방송, 푸시) | — |
| `validation` | 2025년 영덕 산불 재현 검증 | 사후 분석 |

### 현재 상태

🟧 **연구 프로토타입 (alpha)**. 본 저장소는 다음을 제공합니다:

- ✅ 저장소 골격 및 모듈 구조
- ✅ Rothermel 표면 화재 확산 모델 (단일 연료층, Anderson 13 표준 연료) — `src/wildfireguardian/spread_model/rothermel.py`
- ✅ Huygens 타원 wavelet 기반 셀룰러 오토마타 확산 시뮬레이터 — `src/wildfireguardian/spread_model/cellular_automaton.py`
- ⏳ LFMC 회귀 모델 — 다음 세션
- ⏳ 위성 발화점 탐지 — 다음 세션
- ⏳ 대피 경로 그래프 — 다음 세션
- ⏳ 영덕 산불 검증 — 다음 세션

### 데이터 출처

본 시스템은 다음의 공개 데이터에 의존하며, **사용자 환경에서 직접 다운로드** 받습니다 (저장소에는 포함되지 않습니다).

- **NASA FIRMS** (VIIRS/MODIS 활성 화재 픽셀): <https://firms.modaps.eosdis.nasa.gov/>
- **Copernicus Sentinel-2** (광학 위성, LFMC 추정): <https://browser.dataspace.copernicus.eu/>
- **KMA AWS** (자동기상관측소 풍속·풍향·습도): <https://data.kma.go.kr/>
- **수치지도** (DEM 30 m, 지형도): 국토지리정보원
- **OpenStreetMap** (도로망): <https://www.openstreetmap.org/>

### 설치 및 테스트

```bash
git clone https://github.com/sparkxt-0318/wildfireguardian.git
cd wildfireguardian

python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .

# 단위 테스트 실행
pytest -v

# Rothermel LFMC 민감도 차트 생성
python -m wildfireguardian.spread_model.demo_sensitivity

# 영덕-유사 합성 시나리오 (셀룰러 오토마타)
python -m wildfireguardian.spread_model.demo_yeongdeok_synthetic
```

### 인용

```
WildfireGuardian Project (2026). WildfireGuardian: multi-scale wildfire
forecasting and personalized evacuation for rural elderly Koreans.
2026 Korea Code Fair SW공모전. https://github.com/sparkxt-0318/wildfireguardian
```

---

## 🇺🇸 English

### Project overview

**WildfireGuardian** is a research-grade system that integrates satellite fire
detection, physics-based fire spread modelling, atmospheric smoke dispersion,
and personalised evacuation routing — with the explicit goal of protecting
rural elderly Koreans during the "golden time" between ignition and safe
evacuation.

**Motivating event**: the Yeongnam wildfires of 22–28 March 2025 killed 30+
people in South Korea, the majority of whom were in their 60s–80s and lived
in rural villages (영덕군 in particular). The system is designed to be
retrospectively validated against that event before any real-time deployment.

**Target venue**: 2026 Korea Code Fair SW공모전 (Korean high school SW
competition), with the stretch goal of qualifying for ISEF in the Systems
Software category. Submission deadline 2026-06-13.

### System architecture (high level)

```
                  ┌───────────────────────────────────────────────┐
                  │           Satellite fire detection            │
                  │     (NASA FIRMS VIIRS + MODIS, near-real)     │
                  └────────────────────┬──────────────────────────┘
                                       │ ignition points
                  ┌────────────────────▼──────────────────────────┐
                  │              Fuel & weather state             │
                  │  LFMC (Sentinel-2) + KMA wind/RH + DEM/slope  │
                  └────────────────────┬──────────────────────────┘
                                       │
                  ┌────────────────────▼──────────────────────────┐
                  │     Rothermel surface fire spread model       │
                  │  + Huygens-elliptical cellular automaton CA   │
                  │  + Monte Carlo ensemble (wind/moisture noise) │
                  └────────────────────┬──────────────────────────┘
                                       │ perimeter, burn probability
                  ┌────────────────────▼──────────────────────────┐
                  │       Smoke dispersion (Gaussian plume)       │
                  │       Evacuation routing (elderly-aware)      │
                  └────────────────────┬──────────────────────────┘
                                       │
                  ┌────────────────────▼──────────────────────────┐
                  │      Personalised alerts & route delivery     │
                  └───────────────────────────────────────────────┘
```

See `docs/architecture.md` for the long form.

### Current status

🟧 **Research prototype (alpha).** This repository currently provides:

- ✅ Repository scaffold and module structure (this document)
- ✅ Rothermel surface fire spread model with the Anderson 13 standard fuel
  models (`src/wildfireguardian/spread_model/rothermel.py`)
- ✅ Cellular-automaton spread simulator with Huygens elliptical wavelets and
  Monte Carlo ensembling (`src/wildfireguardian/spread_model/cellular_automaton.py`)
- ⏳ LFMC regression — *not yet implemented*
- ⏳ Satellite ignition ingestion — *not yet implemented*
- ⏳ Evacuation routing graph — *not yet implemented*
- ⏳ Retrospective Yeongdeok validation — *not yet implemented*

This is **not** production software. It has not been validated against a real
fire event yet, and it must never be used as the sole input to a public
evacuation order without expert review.

### Data sources

All data sources are public. The repository does **not** distribute any data;
users download data into `data/raw/` at run time. See `docs/data_sources.md`.

### Install & run tests

```bash
git clone https://github.com/sparkxt-0318/wildfireguardian.git
cd wildfireguardian
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

pytest -v

# Generate the LFMC sensitivity figure
python -m wildfireguardian.spread_model.demo_sensitivity

# Run a synthetic Yeongdeok-like cellular-automaton scenario
python -m wildfireguardian.spread_model.demo_yeongdeok_synthetic
```

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

Core algorithmic references used in this repository:

- Rothermel, R.C. (1972). *A mathematical model for predicting fire spread in
  wildland fuels.* USDA Forest Service Research Paper INT-115.
- Albini, F.A. (1976). *Estimating wildfire behavior and effects.* USDA Forest
  Service General Technical Report INT-30.
- Anderson, H.E. (1982). *Aids to determining fuel models for estimating fire
  behavior.* USDA Forest Service General Technical Report INT-122.
- Finney, M.A. (1998). *FARSITE: Fire Area Simulator — model development and
  evaluation.* USDA Forest Service Research Paper RMRS-RP-4.
- Andrews, P.L. (2018). *The Rothermel surface fire spread model and
  associated developments: a comprehensive explanation.* USDA Forest Service
  General Technical Report RMRS-GTR-371.

### License

MIT. See [`LICENSE`](LICENSE).
