# Wildfire-vulnerable counties — deployment-target framework

## Why this list exists

WildfireGuardian is **not** a generic national wildfire system. It is a
specific intervention targeting rural elderly Koreans during fire-prone
spring conditions. The deployment target is the set of 시군구 where:

1. Wildfire frequency is high (East Coast Pine Belt, recurring events
   2019, 2022, 2025).
2. Population is rural and aging — disproportionately 65+, with high
   solitary-living elderly density.
3. Evacuation infrastructure is sparse — limited paved roads, few
   designated shelters per elderly capita, slower emergency response.

By contrast, a 65+ resident in Seoul or Busan does not need this system
— urban evacuation infrastructure, shelter density, and emergency
response are already strong. We do not target them, and we do not
inflate our population coverage claim by including them.

## Scoring framework

Three sub-scores ∈ [0, 1], combined by weighted **geometric** mean:

| Sub-score | What it captures | Data source (Session 3) |
|-----------|------------------|--------------------------|
| `fire_frequency_score` | Historical 산불발생 frequency per unit area / capita | KFS 산불통계 |
| `rural_elderly_density` | Rurality × % age 65+ × % solitary elderly | KOSIS 인구통계 |
| `infrastructure_score` | Inverse of road density × shelter availability × inverse response time | MOIS 안전지표 |

The composite score is

$$ S_{\text{composite}} = \exp\!\left(\frac{\sum_k w_k \log s_k}{\sum_k w_k}\right). $$

Geometric mean (rather than arithmetic) is deliberate: a county with NO
wildfires is not a deployment target no matter how many elderly live
there, and vice versa. The geometric mean zeros out the composite when
any single sub-score approaches zero.

## Session 2 status

The values in `src/wildfireguardian/utils/vulnerability.py::_PLACEHOLDER_SCORES`
are **placeholders** that approximate the qualitative ordering we expect
once real data is ingested. They are based on:

- Public news coverage of historical fire events (Goseong 2019, Uljin
  2022, Yeongdeok 2025) for fire frequency.
- General knowledge of Korean rural-elderly demographics (KOSIS-aggregate
  ordering, not exact numbers) for elderly density.
- Inferred from population density and county-vs-city status for
  infrastructure.

Every entry is tagged `placeholder=True` and explicitly flagged in
`docs/BLOCKERS.md` as needing real KOSIS/KFS/MOIS data ingestion. The
framework is structured so that swapping real data in does NOT change
the call sites.

## Deployment threshold

`DEPLOYMENT_THRESHOLD = 0.55` selects counties whose three sub-scores
average at least ~ 0.55 on the geometric mean. Under the Session 2
placeholders, this gives 9 counties in the East Coast Pine Belt:

| # | 시군구 | composite |
|---|--------|----------:|
| 1 | 울진군 (Uljin) | 0.864 |
| 2 | 영덕군 (Yeongdeok) | 0.864 |
| 3 | 고성군 (Goseong) | 0.814 |
| 4 | 영양군 (Yeongyang) | 0.812 |
| 5 | 봉화군 (Bonghwa) | 0.762 |
| 6 | 삼척시 (Samcheok) | 0.729 |
| 7 | 정선군 (Jeongseon) | 0.720 |
| 8 | 양양군 (Yangyang) | 0.716 |
| 9 | 평창군 (Pyeongchang) | 0.711 |

This list is the value of `WILDFIRE_VULNERABLE_COUNTIES`. It maps directly
to where the system would be initially deployed.

## Explicit exclusions

Counties below the threshold under placeholder scoring:

- **속초시, 동해시, 강릉시, 포항시 (북구·남구)** — semi-urban; lower
  rural-elderly density and stronger infrastructure.
- **Major metro 시 (Seoul, Busan, Daegu, Incheon, Daejeon, Gwangju,
  Ulsan)** — not in the placeholder list at all; explicitly outside scope.

## Refinement roadmap

1. **Session 3 KOSIS ingestion.** Pull 시군구별 65세 이상 독거노인 통계
   for 2020–2024. Replace `rural_elderly_density` placeholders.
2. **Session 3 KFS ingestion.** Pull 시군구별 산불발생 건수 2010–2024.
   Replace `fire_frequency_score` placeholders.
3. **Session 3 MOIS ingestion.** Pull 시군구별 지진/산불 대피소 현황.
   Replace `infrastructure_score` placeholders.
4. **Threshold calibration.** Once real data is in, the `0.55` threshold
   may need adjustment to keep the deployment list at a defensible size
   (target: 10–25 counties, broadly the East Coast Pine Belt + the
   adjacent inland mountain gun's).
5. **Annual refresh.** This data should refresh annually as demographics
   shift.

## References

- KOSIS — Korean Statistical Information Service (https://kosis.kr)
- Korea Forest Service — 산불통계 (https://forest.go.kr)
- Ministry of the Interior and Safety — 안전지표 (https://www.mois.go.kr)
- KOSTAT 행정구역 코드 (https://www.kostat.go.kr)
