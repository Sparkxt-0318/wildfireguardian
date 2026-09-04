# A 주소정보누리집 subset cut on 시군구 code 47920, labelled 영덕 and not verified as 영덕 (2026-09-04)

> ## 정정 (2026-09-04, WFG-075) · this file's original claim was wrong
>
> **이 파일이 처음 주장한 것:** 아래 여덟 개 레이어가 **영덕군**의 지정 대피장소·무더위쉼터·
> 민원행정기관이라는 것. **그 주장은 성립하지 않는다.**
>
> `scripts/extract_juso_yeongdeok.py`는 시군구 코드 **47920**으로 잘랐고 그 코드에
> `# 경상북도 영덕군`이라는 주석이 붙어 있었다. 잘려 나온 239개 점은 전부
> **128.65-129.15 E / 36.78-37.06 N**에 있고, 이 저장소가 예보와 라우팅을 돌리는 영덕 상자
> `regions.lookup('yeongdeok_2025').bbox_wgs84` = **(129.25, 36.30, 129.55, 36.60)**
> (`config/default.yaml:83`) 안에 든 점은 **0개**다. 두 상자는 경도에서도 위도에서도 겹치지
> 않으며 약 45 km 떨어져 있다.
>
> 파일 안에 있던 두 번째 단서: 영덕은 동해안 군인데 239개 점 중 129.15 E 동쪽에 있는 점이
> 하나도 없고, **지진해일긴급대피장소 레이어가 0행**으로 돌아왔다. 이 파일의 이전 판은 그
> 0을 「영덕에는 해당 행이 없다」는 **영덕에 관한 사실로 기록했다.** 해안 군에는 지진해일
> 대피장소가 지정되어 있다. 그 0이 증거였고, 데이터로 읽혔다.
>
> **무엇이 맞고 무엇이 틀렸나.** 두 원본 zip은 문제가 없다: sha256, 제작 일자, 기관, CRS
> 메모는 모두 그대로 유효하다. 레이어별 **개수 자체도** 필터가 실제로 뽑은 행 수라는 뜻에서는
> 맞다. 틀린 것은 **그 행들이 어느 군의 것인가라는 라벨 하나**이며, 그 라벨에서 파생된 이
> 문서의 모든 문장이 함께 틀렸다.
>
> **어느 군인지는 여기에 쓰지 않는다.** 47920이 실제로 어느 시군구인지 이 랩은
> 행정표준코드(code.go.kr) 원부를 열어 확인하지 못했고, WFG-066은 「기록에서 읽지 않은
> 식별자는 적지 않는다」를 표준으로 세워 둔 규칙이다. 추정은 NH-022에만, 추정이라고 적혀
> 있다.
>
> **지금 상태.** 여덟 개 레지스트리 키는 값을 그대로 둔 채 `caveat` 맨 앞에 「SCOPE WRONG,
> DO NOT USE AS 영덕 DATA」와 `scope_status: wrong`을 달았다(CHARTER §3.2/§3.3: 더하고,
> 고치지 않는다). `scope`, `sample`, `derivation`에 남아 있는 「영덕군」은 **무엇이
> 주장되었는지의 기록으로 일부러 남겨 둔 것**이며, 라벨이 가리키는 지역 안에 형상이 있는지
> 검사하는 게이트(WFG-076)가 잡아야 할 대상이기도 하다. WFG-073과 WFG-074는
> `blocked(NH-022)`이다. 재추출은 노트북에서만 가능하다(`data/raw/juso/`는 git-ignored).
>
> **판정단이 보는 화면에는 이 값이 하나도 인쇄되지 않는다.** README, `web/finals.html`,
> `paper/manuscript.md`, `docs/auto/JUDGE_QA.md`를 확인했다. 부스에서 틀린 것은 오늘 없다.
> 「이 대피 지점들은 어디서 나온 겁니까?」에 대한 답은 이 데이터가 아니라 종전대로
> OSM 태그와 문서화된 합성 대체값이다(`docs/data_sources.md`).

**아래 원문은 정정 전 그대로 두었다.** 무엇이 주장되었는지가 기록이기 때문이다. 「영덕」이라고
읽히는 모든 문장은 위 정정을 거쳐 읽어야 한다.

**What this is.** On 2026-09-04 the author downloaded two datasets from 행정안전부's
주소정보누리집 (business.juso.go.kr), a portal the loop cannot log into, and placed the zips
under the git-ignored `data/raw/juso/`. `scripts/extract_juso_yeongdeok.py` cuts the 영덕군
subset into `data/processed/external/juso_yeongdeok/` (GeoJSON, EPSG:4326, about 100 KB) with
a manifest carrying both zips' sha256, the data dates and the filter; the layer counts are
registered as `juso_yeongdeok_*_count` by `scripts/register_juso_yeongdeok.py`.

| dataset | data date | what it holds for 영덕 | registry keys |
|---|---|---|---|
| 사물주소도형 (경상북도 전체분) | 2025-03-01 | 지진옥외대피장소, 무더위쉼터, 인명구조함, 소화전, 비상급수시설, 버스정류장 points (지진해일대피장소 and 비상급수 have no 영덕 rows) | `juso_yeongdeok_samul_*_count` |
| 민원행정기관 전자지도 | 2024-01-24 | schools, 읍면동 offices, 보건소·보건지소·진료소, 파출소, 119안전센터, post offices | `juso_yeongdeok_minwon_agencies_count` |

**What this is not.** Neither file is the 도로명주소 **건물** (building footprint) layer that
NH-005 asks for; household counts stay provisional on the OSM buildings and NH-005 stays open.

**Why it matters.** The router's refuges and depots have so far come from OSM tags, the
공공데이터포털 shelter standard data when configured, and a documented synthetic fallback
(`docs/data_sources.md`, "Rescue-aware routing inputs"). These two files give, for the first
time in the repository, an *agency-designated* list for 영덕: outdoor evacuation sites and
cooling centres as refuge candidates, and the 119 centres, 파출소 and 읍면동 offices as
responder depots or notification targets, each with a road address and a phone number.

**Method notes.** 사물주소 object ids encode the 시군구 code in positions 5–10
(`OBJ` + kind + `47920` + serial); the shapefiles ship without a `.prj` and were assigned
EPSG:5179 because they fall on the same grid as the agency points, which do carry it.
Re-running the extractor is deterministic; the raw zips are laptop-only.

**What it does not show.** Whether a listed 무더위쉼터 is open during a spring wildfire, its
capacity, or whether any site is a designated *wildfire* 대피소 — the 사물주소 categories are
earthquake, tsunami and heat. That question (NH-012 b) is narrowed, not answered.

**Next (backlog).** WFG-073 compares the router's current refuges with the designated sites;
WFG-074 wires the 119 centres, 파출소 and 읍면동 offices in as depots and notification targets.
