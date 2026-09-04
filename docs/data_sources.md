# Data sources

WildfireGuardian relies entirely on **public** data. The repository does
not distribute any of it; users download datasets into `data/raw/` at
runtime using the ingestion helpers in `wildfireguardian.data_io`. None
of the runtime calls in this repository connect to remote sources without
explicit user opt-in.

The **canonical data-driven pipeline (`spread_v2`) uses four inputs**: NASA FIRMS
(VIIRS S-NPP/NOAA-20 + MODIS active fire), SRTM ~30 m DEM, ESA WorldCover 2021 (10 m
land cover → fuel burnability), and ECMWF ERA5 (reanalysis weather); the rescue
router adds OpenStreetMap walk/drive networks and 공공데이터포털 shelters/119 depots.
The **Sentinel-2 LFMC, KFS 임상도 fuel-model, and KMA-wind-field-for-CA entries below
belong to the earlier physics track** and are retained for reference, **not** as
current `spread_v2` inputs.

## Satellite

| Dataset | Provider | Use | Access | Auth |
|---------|----------|-----|--------|------|
| VIIRS S-NPP / NOAA-20 375 m active fire | NASA FIRMS | Real-time ignition detection | https://firms.modaps.eosdis.nasa.gov/api/ | MAP_KEY |
| MODIS Aqua/Terra MCD14ML | NASA FIRMS | Cross-check & historic ignitions | Same | MAP_KEY |
| Sentinel-2 L2A surface reflectance | Copernicus | LFMC retrieval (superseded physics track) | https://browser.dataspace.copernicus.eu/ | CDS account |
| Sentinel-3 SLSTR L2 FRP | Copernicus | Fire radiative power | Same | CDS account |

## Meteorology

| Dataset | Provider | Use | Access | Auth |
|---------|----------|-----|--------|------|
| KMA AWS hourly wind, RH, T | KMA | Spatial wind field for CA (superseded physics track) | https://data.kma.go.kr/ | service key |
| ERA5 single levels (10 m winds, 2 m T/q) | Copernicus C3S | **Canonical weather source for `spread_v2`** | CDS API | CDS account |
| GDAPS / KIM regional NWP | KMA | Short-range forecast wind | https://data.kma.go.kr/ | service key |

## Terrain — DEM

### Option A: NGII 국토지리정보원 (preferred for Korean operational use)

- **Dataset**: 1:5000 digital map (vector contour + spot heights) →
  rasterised to 5 m / 10 m / 30 m DEM.
- **Access**: https://map.ngii.go.kr/ → 국토정보플랫폼 → 디지털지도 →
  1:5000 vector contour. Free for research use.
- **Registration**: Korean residence required for full download; foreign
  researchers can request via the 국제협력 portal (slower).
- **License**: KOGL (Korea Open Government License) Type 1 — free
  redistribution as derived products with attribution.
- **What to do if blocked**: fall back to SRTM 30 m or COPDEM 30 m (below).
  Both are free and global; the loss of accuracy vs NGII is ~3-5 m
  vertical RMSE, acceptable for the model's slope / terrain features.
- **Where to put it**: ``data/raw/dem/ngii/<sheet>.tif`` (gridded GeoTIFF
  in EPSG:5179) or .shp for vector contours.

### Option B: SRTM (free global fallback)

- **Dataset**: NASA SRTM 30 m DEM (3-arc-second).
- **Access**: https://earthexplorer.usgs.gov/ (or AWS Open Data:
  ``s3://elevation-tiles-prod/``).
- **License**: Public domain.
- **Where to put it**: ``data/raw/dem/srtm/<tile>.hgt`` or .tif.

The `wildfireguardian.data_io.raster.load_dem` function tries
``source='ngii'`` → ``source='srtm'`` → ``source='synthetic'`` in order
when called with ``source='auto'``. Session 2 implements only the
synthetic path; the SRTM and NGII paths raise NotImplementedError with
clear instructions until Session 3.

## Fuel type — KFS 임상도

> *Superseded physics track.* The canonical `spread_v2` model derives fuel
> burnability from **ESA WorldCover** (see Landcover, below), not from KFS
> fuel-model codes. The 임상도 → fuel-model path below was for the Rothermel engine
> and is kept for reference.

- **Dataset**: 임상도 v1.4 (Korean Forest Service forest-stand-type map).
  Polygon shapefile with stand-level attributes: dominant species,
  age class, density, canopy closure.
- **Access**: https://map.forest.go.kr/forest/ → 임상정보 → 임상도.
  Requires Korean Forest Service registration; foreign researchers can
  apply via 국제협력 form.
- **License**: KOGL Type 1.
- **What to do if blocked**: ME 토지피복 v3 (Ministry of Environment land
  cover, below) provides 1-digit landcover that lets us infer "forest" vs
  "non-forest"; Session 2's synthetic-Korean-Pinus is a defensible
  fallback if no real fuel-type raster is available.
- **Where to put it**: ``data/raw/fuel/kfs_impsangdo/`` shapefile.
- **Refinement path**: stand-species codes → fuel-model codes via a
  lookup table (e.g., 소나무 / Pinus densiflora codes → KP_PINE; 참나무 /
  Quercus codes → FM9; 침엽 / mixed → FM10). Session 3 task.

## Landcover

| Dataset | Provider | Use | Access |
|---------|----------|-----|--------|
| 환경부 토지피복지도 v3 | ME (환경부) | Fuel-model fallback when 임상도 unavailable | https://egis.me.go.kr/ |
| ESA WorldCover 10 m | ESA | Global fallback | https://esa-worldcover.org/ |

## Roads & population

| Dataset | Provider | Use | Access |
|---------|----------|-----|--------|
| OSM road network | OpenStreetMap | Evacuation routing graph | https://www.openstreetmap.org/ |
| 행정안전부 주민등록 연령별 인구 통계 | MOIS | Rural-elderly density | https://mois.go.kr/ |
| KOSIS 시군구별 65세 이상 독거노인 | KOSIS | Solitary-elderly density | https://kosis.kr/ |
| SK Telecom Floating Population (sample) | KOSIS | Diurnal exposure adjustment | https://kosis.kr/ |

## Rescue-aware routing inputs (walk/drive networks, refuges, depots)

The rescue-aware evacuation router (`wildfireguardian.routing.rescue`) needs a
**drive** network (responders) in addition to the **walk** network (residents),
plus candidate refuges and responder depots. Each has a real-source loader **and**
a clearly-labelled synthetic fallback so the pipeline runs end-to-end offline; the
loader tags every record `source = "real" | "synthetic"`.

| Dataset | Provider | Use | Access | Real-source loader |
|---------|----------|-----|--------|--------------------|
| OSM `walk` + `drive` networks | OpenStreetMap (via OSMnx) | Pedestrian + vehicle routing graphs (reprojected to EPSG:5179, disk-cached) | https://www.openstreetmap.org/ | `rescue.load_drive_network(..., use_osm=True)` |
| 대피소·긴급대피장소 (전국 대피소 표준데이터) | 행정안전부 / 공공데이터포털 | Candidate refuges (shelter-in-refuge destinations) | https://www.data.go.kr/ | `rescue.load_shelters` (GeoJSON/CSV at `cfg.shelters_path`) |
| 119안전센터 현황 / OSM `amenity=fire_station` | 소방청 / 공공데이터포털 / OSM | Responder depots | https://www.data.go.kr/ | `rescue.load_depots` (GeoJSON/CSV at `cfg.depots_path`) |

When no `shelters_path`/`depots_path` is configured and `use_osm=False` (the
default, offline), the demo (`routing.rescue_demo`) substitutes **synthetic**
coastal assembly nodes + inland open-space refuges, synthetic near-town depots, a
synthetic growing hazard envelope, and an 8-connected lattice on the real 영덕
extent — all tagged synthetic and listed in `rescue_routing.json::provenance`.
KOGL (Korea Open Government License) attribution applies to the Korean open data
exactly as for the other datasets above.

## Wildfire validation — KFS perimeter shapefiles

| Event | Dataset | Provider | Access |
|-------|---------|----------|--------|
| 영덕 2025-03 | KFS post-event perimeter | KFS | KFS post-event report PDF + accompanying shapefile (request via KFS 산불방지과) |
| 울진/삼척 2022-03 | KFS final report perimeter | KFS | KFS 2022 final report |
| 고성/속초 2019-04 | KFS final report perimeter | KFS | KFS 2019 final report |

For Session 2, these perimeter polygons are **stub manifests** in
``data/validation_cases/*.json`` with approximate ignition points and
official-warning timelines reconstructed from public news coverage. Real
KFS shapefiles need to be ingested in Session 3 to enable Sørensen-Dice
and IoU validation.

## Vulnerability scoring inputs (Session 3 ingestion)

The placeholder vulnerability scores in
``src/wildfireguardian/utils/vulnerability.py`` will be replaced with real
data from:

- **KOSIS 65세 이상 독거노인 통계** for `rural_elderly_density`.
- **KFS 시군구별 산불발생 건수 2010-2024** for `fire_frequency_score`.
- **MOIS 지진/산불 대피소 시설 현황** for `infrastructure_score`
  (inverse — fewer shelters → higher vulnerability).

All three are public; all three require registration; all three are
explicitly catalogued in ``docs/BLOCKERS.md``.

## Licensing & attribution

All datasets listed here are public for non-commercial research. Each
ingestion helper in `wildfireguardian.data_io` emits the proper
attribution line in the output product metadata. Never redistribute raw
NASA FIRMS or Sentinel imagery; redistribute derived products only, with
provenance.

For Korean datasets covered by KOGL (Korea Open Government License),
attribution must include:

- The producing agency (NGII / KFS / KMA / ME / MOIS).
- The dataset name + version.
- The license URL: https://www.kogl.or.kr/info/license.do

## 동기 사건의 피해 규모 — 범위별 정리 (2025년 3월 산불)

README 서두가 인용하는 피해 수치의 출처와 **범위(scope)**를 한 곳에 모은 표다.
이 표가 있는 이유는 단순하다: 수치 하나가 어느 범위·어느 시점의 값인지 밝히지 않으면
심사위원이 한 번의 검색으로 반증할 수 있고, 이 저장소는 그 실수를 **양방향으로 두 번**
저질렀다(아래 「알려진 함정」).

**이 절의 규칙 (2026-09-04, critic #4 F18):** 모든 행은 **열 수 있는 URL**을 가진다.
URL을 확인하지 못한 값은 「주의해서 낮춘 값」으로 남기지 않고 **표에서 뺀다**(폐기 사유는
아래에 적어 남긴다). CHARTER §12가 `paper/references.bib`에 적용하는 규칙을 「데이터 출처」라는
이름을 단 문서에 그대로 적용한 것이다. 아래 URL은 모두 2026-09-04 랩이 직접 열어서 확인했다.

### A. 의성발 경북 산불 (의성→안동→청송→영양→영덕) — 이 프로젝트의 대상 사건

3월 22일 11:24 의성군 안평면 발화, 3월 28일 17:15 주불 진화(149시간).

| 항목 | 값 | 출처 | 기준 | URL |
|---|---|---|---|---|
| **최종 산림피해 면적** | **99,289 ha** | 경상북도 최종 집계(중대본 확인) | 2025-05-06 보도 | [아시아경제](https://view.asiae.co.kr/article/2025050610030818823) |
| 최종 면적(교차) | 약 99,000 ha | 경북도·시군·산림청 관계기관 합동조사 | 2025-04-17 발표 | [경향신문](https://www.khan.co.kr/article/202504171020011) |
| 사망 | 26명 | 경상북도 재난안전대책본부 | 2025-03-30 | [대구MBC](https://dgmbc.com/article/bLdh4s3M4pgcSdYI0MZPc) |
| └ 영덕 사망 | **10명** | 영덕군 공지(그린피스 보고서 p.9 재인용) | 2025-04-29 | `docs/evidence/greenpeace_2026_survey.md` §7 |
| └ 영덕 사망(중간) | 9명 | 경상북도 재난안전대책본부 | 2025-03-30 | [대구MBC](https://dgmbc.com/article/bLdh4s3M4pgcSdYI0MZPc) |
| **주택 피해** | **3,819동** | 경상북도 최종 집계(중대본 확인) | 2025-05-06 보도 | [아시아경제](https://view.asiae.co.kr/article/2025050610030818823) |
| 이재민 | 2,246세대 3,587명 | 경상북도 최종 집계(중대본 확인) | 2025-05-06 보도 | [아시아경제](https://view.asiae.co.kr/article/2025050610030818823) |
| 총 피해액 | 1조 505억 원 | 경상북도 최종 집계(중대본 확인) | 2025-05-06 보도 | [아시아경제](https://view.asiae.co.kr/article/2025050610030818823) |
| *(참고) 「산불영향구역」 추정* | *45,157 ha* | *산림청* | *2025-03-27* | [경향신문](https://www.khan.co.kr/article/202504171020011) |
| *(참고) 주택 전소 잠정* | *150동* | *산림청* | *2025-03-26* | [위키백과 「2025년 의성-안동 산불」](https://ko.wikipedia.org/wiki/2025%EB%85%84_%EC%9D%98%EC%84%B1-%EC%95%88%EB%8F%99_%EC%82%B0%EB%B6%88) |

**45,157 ha는 「잠정치」가 아니라 다른 양이다.** 산림청이 진화 중 발표한
**「산불영향구역」** 추정치이고, 99,289 ha는 합동조사를 거친 **산림피해 면적**이다.
같은 값의 옛 판본이 아니므로 「최종값으로 갱신되었다」가 아니라 **기준이 다르다**로 읽어야
한다(함정 1).

**영덕 사망자 주.** 10명은 영덕군 공지(2025-04-29)를 그린피스 「2025 영남 초대형 산불
피해 실태조사 최종보고서」 p.9가 인용한 **재인용값**이며, 그린피스의 조사 결과가 아니다.
저장소 내 정본은 `docs/evidence/greenpeace_2026_survey.md` §7 항목 1이다. 같은 화재군에
대해 경상북도 재난안전대책본부의 2025-03-30 집계는 **9명**을 제시한다(영양 7·안동 4·
청송 4·의성 2, 총 26명). 기준일과 집계 주체가 다르므로 **두 값을 모두 남기고 어느
한쪽을 단독으로 단정하지 않는다.** 폐기된 값은 「8명」이며, 이는 어느 출처에도 없다.

### B. 2025년 **봄철 산불조심기간**(1-24 ~ 5-15) 전국 산불 347건 — 대상 사건이 **아님**

**이 표의 범위는 「2025년 3월」이 아니다.** 2026-09-04의 두 랩이 모두 3월로 적었고,
그중 한 랩의 독립 리뷰어가 1차 출처를 열어 반증했다. 산림청 보도자료(2025-05-16)의
대상 기간은 **봄철 산불조심기간 2025년 1월 24일 ~ 5월 15일**이다.

| 항목 | 값 | 출처 | 기준 기간 | URL |
|---|---|---|---|---|
| 발생 건수 | 347건 | 산림청 보도자료 | 2025-01-24 ~ 05-15 | [산림청 2025-05-16](https://www.pcccr.go.kr/base/board/read?boardManagementNo=43&boardNo=5375&menuLevel=2&menuNo=92) |
| 피해면적 | 104,788 ha | 산림청 보도자료 | 2025-01-24 ~ 05-15 | 위와 같음 |

원문: 「올해 산불 발생 건수는 최근 10년 평균(394건)보다 12% 감소한 **347건**이었으나,
피해 면적은 **104,788헥타르(ha)**로 1986년 산불통계 작성 이래 가장 피해가 컸으며」.

**표에서 뺀 두 값과 그 이유**(값은 지우지 않고 여기 남긴다 — CHARTER §3 rule 3):

- 전국 **사망 32명 · 부상 54명**: 정책브리핑(korea.kr)에 게재된 같은 보도자료 본문에
  「**사상자도 86명(사망 32명, 부상 54명)**으로 많은 인명 피해가 발생했다」가 있다
  ([산림청 보도자료 2025-05-16, 대한민국 정책브리핑](https://m.korea.kr/briefing/pressReleaseView.do?newsId=156689401),
  2026-09-04 노트북 랩 열람). 등록 키 `fire2025_nationwide_deaths`, `fire2025_nationwide_injured`
  (기간: 봄철 산불조심기간 전체). README 서두는 이 값을 인용하지 않는다.
  *(이전 문장 보존)* 위 보도자료에서 확인하지 못했다. 이전 판본은 「산림청 2025-05-15」로
  적었으나 실제 근거는 위키백과 2차 인용이었고, 그 위키백과 문서에는 「347」이라는 숫자
  자체가 없다. 확인 가능한 1차 출처를 찾을 때까지 뺀다.
- 전국 **주택 피해 3,848동**: 산림청 보도자료에는 없고, 「2025 영남 초대형 산불 피해 실태조사
  최종보고서」(2026-03, [공동 발간처 게시 페이지](https://igt.or.kr/bbs/board.php?bo_table=m03_01&wr_id=65))
  요약이 **영남 초대형 산불(경북·경남·울산)** 기준으로 인용하는 값이다. 전국값도 A값도 아니며
  2차 출처이므로 `fire2025_yeongnam_homes_damaged_secondary`(status: secondary)로만 등록했다.
  *(이전 문장 보존)* 어떤 열람 가능한 출처에서도 확인하지 못했고, A의 3,819동과
  혼동된 값일 가능성이 있다.

또한 산림청 산불발생 통계 페이지는 **2025년 연간 459건·105,099.44 ha**를 제시하는데,
이는 봄철 기간(347건)이 아니라 **연간 전체**라 위 표와도 직접 비교되지 않는다
([산림청 산불발생현황](https://www.forest.go.kr/kfsweb/kfi/kfs/frfr/selectFrfrStats.do?mn=AR04_01_03),
2026-09-04 확인). **같은 해에 대해 서로 다른 세 개의 전국 숫자가 존재한다는 뜻이며,
그것이 이 문서가 존재하는 이유다.**

**A와 B의 관계 — 비율을 쓰지 않는다.** 2026-09-04T0037Z 수동 랩은 「A는 B의 약 95 %」라고
적었다. 그 문장은 이 절에서 **철회한다**: 분자와 분모의 집계 기준이 다르고(산림피해 면적
vs 전국 합계), 기간도 다르다(3월 6일간 vs 봄철 전체). 같은 기준으로 맞추면 약 43 %가
되므로, 기준 선택만으로 두 배 달라지는 값이다. 자세한 근거는 함정 6.

### 알려진 함정

1. **45,157 ha와 99,289 ha는 「틀린 값 / 맞는 값」이 아니라 서로 다른 양이다.**
   전자는 진화 중 산림청이 발표한 **「산불영향구역」 추정치**(2025-03-27), 후자는
   합동조사를 거친 **산림피해 면적**이다. 합동조사 결과는 추정치의 두 배를 넘었다.
   README 서두는 99,289 ha를 쓰고 45,157 ha는 기준을 밝혀서만 인용한다.
2. **116,000 ha는 어느 범위에도 해당하지 않는다.** 초기 README가 A 문장에 이 값을 썼으나
   전국 합계(104,788 ha)보다도 크다. 폐기.
3. **45,157 ha와 150동을 A의 최종값으로 쓰지 말 것.** 2026-09-04 커밋 `12b8ac7`이
   45,157 ha를 최종값으로 적고 "전국 104,788 ha는 다른 사건"이라는 **반대 방향으로 틀린**
   주석까지 달았다가 critic #4 F16에 걸렸다. 한 번 과대(116,000), 한 번 과소(45,157)로
   같은 문장이 두 번 틀렸다. 45,157 ha는 「산불영향구역」 추정치이고 A의 최종 산림피해
   면적은 99,289 ha, 주택 피해는 3,819동이다.
4. **사망자 27명은 어느 쪽도 아니다.** A는 26명이다.
5. **영덕 사망자는 출처에 따라 9명과 10명으로 갈린다.** 「8명」은 어느 출처에도 없으며
   폐기한다(critic #4 F17). 두 값은 기준일과 집계 주체가 다르므로 둘 다 남긴다.
6. **A와 B를 나누지 말 것 — 그 비율은 기준에 따라 두 배로 달라진다.** critic #4는
   「이 화재군이 전국의 약 95 %」를 README에 쓰라고 했고, 2026-09-04T0037Z 수동 랩이
   실제로 그렇게 썼다. 지금은 쓰지 않는다. 분자를 A의 산림피해 면적(99,289 ha)으로
   잡으면 약 95 %가 나오지만, B와 **같은 기준**인 산불영향구역(45,157 ha)으로 잡으면
   약 43 %가 나온다. 한 비율이 기준 선택만으로 두 배 이상 달라지면 그것은 수치가 아니라
   서술의 선택이다. 게다가 B는 **기간**도 다르다(봄철 전체 vs 3월 6일간).
7. **「주택 4,000여 채」는 A의 값이 아니다.** A의 최종 주택 피해는 3,819동이다. 전국
   집계로 흔히 인용되는 3,848동은 이번 랩이 **어떤 열람 가능한 출처에서도 확인하지
   못했고**, A의 3,819동과 혼동된 값일 가능성이 있어 B 표에서 뺐다(값 자체는 여기 남긴다).
8. **World Weather Attribution의 「48,000 ha 이상」은 A의 면적 근거로 인용하지 않는다.**
   WWA 신속연구(2025-04-30)가 **한국 남동부(southeastern Korea)** 범위로, 십수 건의
   화재를 합쳐 제시한 수치다. 2026-09-04 랩이 저장소에 적혀 있던 URL을 열지 못했고(404),
   같은 랩의 독립 리뷰어가 살아 있는 주소를 찾아 범위를 재확인했다. 범위가 다르다는 것이
   인용하지 않는 이유이며, 「링크가 죽었다」는 부차적 이유다.

### 등록 키와 아티팩트 (2026-09-04, WFG-049)

위 A·B 표의 값은 `data/processed/external/fire_2025_scale.json`에 기관·기준일·범위·상태
(`final` / `interim` / `secondary`)·열람 URL과 함께 저장되고, `docs/NUMBERS.json`의 `fire2025_*`
키로 등록된다(`scripts/register_fire2025_figures.py`, 추가 전용). `make verify`의
`check-readme-figures`는 README 서두 두 문단이 최종값을 등록값 그대로 쓰는지, 잠정치가
최종값 행세를 하지 않는지, 폐기값이 없는지를 검사하고,
`tests/test_readme_opening_figures.py`는 두 문단을 키에 묶는다.

| 키 | 값 | 상태 | 열람 URL |
|---|---|---|---|
| `fire2025_chain_area_ha` · `_hours_to_containment` · `_homes_damaged` · `_displaced_households` · `_displaced_people` · `_damage_krw_100m` | 99,289 ha · 149시간 · 3,819동 · 2,246세대 · 3,587명 · 1조 505억 원 | final | [경상북도 보도자료 2025-05-07](https://gb.go.kr/Main/governor/page.do?mnu_uid=6792&dept_code=&dept_name=&BD_CODE=bbs_bodo&bdName=&cmd=2&Start=100&B_NUM=503433101&B_STEP=503433100&B_LEVEL=0&key=4&word=&p1=0&p2=0&V_NUM=11584&tbbscode1=bbs_bodo) |
| `fire2025_chain_deaths` | 26명 | final | [뉴시스 2025-03-29](https://www.newsis.com/view/NISX20250329_0003118385) · [서울신문 2025-03-30](https://www.seoul.co.kr/news/society/accident/2025/03/30/20250330500072) (중대본: 사망 30 = 경북 26 + 경남 4) |
| `fire2025_chain_deaths_yeongdeok` | 10명 | final | 영덕군 공지 2025-04-29, 실태조사 최종보고서 p.9 재인용 ([게시 페이지](https://igt.or.kr/bbs/board.php?bo_table=m03_01&wr_id=65)); 중대본 03-30 집계 9명은 `earlier_tally`로 병기 |
| `fire2025_nationwide_fires` · `_area_ha` · `_deaths` · `_injured` | 347건 · 104,788 ha · 32명 · 54명 | final (봄철 산불조심기간 1-24 ~ 5-15) | [산림청 2025-05-16, korea.kr](https://m.korea.kr/briefing/pressReleaseView.do?newsId=156689401) |
| `fire2025_interim_chain_area_ha_20250327` | 45,157 ha | interim (「산불영향구역」 초기 추정치) | [경향신문 2025-03-28](https://m.khan.co.kr/article/202503280702001) (중대본 03-27 집계; 산불영향구역 기준) |
| `fire2025_interim_homes_destroyed_20250326` | 150동 | interim | 산림청 2025-03-26 브리핑, 2차 출처(위키백과 「2025년 의성-안동 산불」) |
| `fire2025_chain_share_of_nationwide_pct` | (등록값 참조) | derived | A의 최종 면적을 B의 면적으로 나눈 산술 기록. 두 랩의 판단이 갈린다(NH-018): 0100Z 랩은 기준·기간이 달라 비율을 쓰지 않기로 했고, README는 현재 어떤 비율도 인용하지 않는다. 키는 기록으로만 남기며 문서에는 인용하지 않는다. |
