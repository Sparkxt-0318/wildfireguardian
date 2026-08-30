# Session 14 — 실행 기록 (Layer 0: 대피 취약도)

## 0.1 베이스라인

9개 게이트 전부 종료 코드 0, 작업 트리 깨끗, `4f9647c` 기준.
테스트는 Phase 5에서 최종 기록합니다.

## 0.2 Layer 2 재사용 인벤토리 — 무엇이 발화를 요구하는가

이 층은 **발화 전**에 계산되어야 하므로, 기존 Layer 2 진입점 각각이 실제
화재를 요구하는지 아닌지가 재사용 가능량을 결정합니다.

### 발화와 무관 — 그대로 재사용

| 진입점 | 경로 |
|---|---|
| `load_snapshot_graph`, `build_walk_network` | `routing/slope.py` |
| `RoadNetwork` (`node_xy`, `nearest_node`) | `routing/future_front.py` |
| `load_buildings`, `BuildingSet`, `load_walk_nodes` | `buildings/__init__.py` |
| `load_shelters`, `load_depots`, `Destination` | `routing/rescue.py` |
| `snapshot_for`, `read_poi_snapshot` | `scripts/run_multi_region_routing.py` |
| `sample_corridor_points` | `routing/rescue.py` |
| `elderly_speed_ms` (Tobler 1993) | `routing/evacuation.py` |
| `cluster_points` (마을 단위 집계) | `delivery/villages.py` |

### 화재를 요구 — 대체 또는 대리 입력 필요

| 진입점 | 왜 |
|---|---|
| `origin_filter` / `candidate_origins` (4곳 중복) | `haz[0] >= 0.5` 의 중심에서 발화 프록시를 유도합니다. **발화 전에는 t=0 코어가 없습니다** — 가장 뚜렷한 단절이며, 본 층에서 교체했습니다. |
| `round_trip_margin`, `future_aware_route`, `build_dispatch_list`, `capacity_triage` | 전부 `HazardSequence` 를 위치 인자로 받습니다. |
| `live.pipeline.load_resources` | `fire_manifest.json` 항목이 없으면 `KeyError`. |
| `service.routing.IgnitionRequest` | 구조 자체가 발화 형태입니다. |

### 핵심 발견 — 이음매는 다섯 개짜리입니다

**화재 의존 함수 전부가 화재를 오직 `HazardSequence` 를 통해서만 만집니다**
(`grid`, `times_min`, `surfaces`, `prob_at`, `prob_at_points`). 그 계약을
만족하는 어떤 대리 필드도 하류 전체를 **수정 없이** 통과시킵니다. 가상 발화는
실제 발화와 똑같이 그 계약을 만족하므로, **Layer 2 의 마진·경로 스택 전체가
반사실적 화재에 그대로 돌아갑니다.** 교체가 필요했던 것은 발화 유래 origin
필터 하나뿐입니다.

## 0.3 새로 만든 것

| 파일 | 역할 |
|---|---|
| `src/wildfireguardian/vulnerability/hazard_sources.py` | 플러그형 위험원 — 학습 모델 / 지역 무관 타원 물리 |
| `src/wildfireguardian/vulnerability/ignition.py` | 발화 표집(prior, 관련성 반경) |
| `scripts/vulnerability_layer.py` | 한국 실행·스윕·웜스타트 |
| `scripts/osm_coverage_gate.py` | Phase 4 게이트 |
| `scripts/vulnerability_portability_run.py` | 비한국 사이트 실행 |

## 0.4 발화 표집 설계 (Phase 1a) — 인용 근거

**인위적 원인 우세.** 산림청 10년 평균(2016–2025, 연 529건): 입산자실화
30%, 쓰레기소각 12%, 논·밭두렁 소각 10%, 담뱃불실화 7%, 건축물화재 7%,
성묘객실화 3%, 기타 31%. **최소 69%가 명명된 인간 활동에 귀속**됩니다.
[산림청 「산불의 원인 및 영향」 cmsId=FC_001153]

⚠ **단순 거리감쇠가 아닙니다.** 영덕과 같은 동해안을 다룬 공간 연구는
발화가 마을·도로·농지 근접과 연관되나 **고밀도 인간활동으로부터 중간
거리에서 정점**을 이룬다고 보고합니다 (*Forests* 17(2):281). 따라서 커널의
정점을 0이 아닌 오프셋(기본 300 m)에 두었습니다.

⚠ **그래도 가정입니다.** 발화점 데이터셋을 적합시키지 않았습니다. 인용
문헌이 동기를 준 *형태*이지 보정된 모델이 아니며, 그래서 스윕합니다.

### 관련성 반경 — 기록해 둘 설계 결정

격자는 약 62×59 km 인데 OSM 가옥은 한 마을에 모여 있고, 4시간 지평에서
중간 규모 화재는 0.5–3 km 전진합니다. 구역 전체에 발화를 뿌리면 **구성상
어떤 가옥에도 닿을 수 없는** 시나리오가 표본을 채우고, 점수는 취약도가
아니라 구역 면적을 재게 됩니다. 그래서 가옥에서 **5 km 이내**로 제한하여
"당신에게 닿을 수 있는 화재가 났을 때 얼마나 자주 갇히는가"를 재도록
했습니다.

## 0.5 점수 정의 (Phase 1b)

> **취약도 = 표집된 발화 시나리오 중, 생존 가능한 자력 대피 경로가 없거나
> 여유 마진이 10분 미만인 시나리오의 비율**

**왜 순수 "경로 없음" 비율이 아닌가.** 영덕에서는 그 정의가 **전 가구
0** 입니다 — 피난처 POI 50개, 중간 규모 물리 화재, 4시간 지평에서 모두가
탈출합니다. 마진 문턱을 더하면 점수가 여전히 **실패 횟수**(운영자가 행동하는
단위)이면서 "2분 남기고 탈출"을 실패로 셉니다. **두 성분은 항상 분리해
보고**하므로 문턱의 기여가 보이지 않는 일은 없습니다.
