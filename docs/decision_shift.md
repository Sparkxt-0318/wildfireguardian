# 판정 이동량 — 두 사건, 지역별 실측

**PHASE 25 STEP 0, 2026-08-13.** 이 저장소가 자체 발견하고 정정한 결함들 가운데,
**운영 판정(출발지 분류)의 이동량이 커밋된 산출물에 전후 양쪽 모두 보존된 것**을
전수 조사한 기록입니다.

조사는 읽기 전용이었습니다. 커밋 산출물은 수정하지 않았고, 어떤 산출 스크립트도
재실행하지 않았습니다. 아래 모든 수치는 열어본 파일 또는 실행한 `git show` 에서
나왔습니다 — [`HANDOFF_ROUND3.md`](HANDOFF_ROUND3.md) §4-B 규칙.

> ⚠ **이 문서는 초안이 적대적 검증을 거쳐 정정된 판본입니다.** 초안의 확정 서술은
> 「83개 출발지 대 1개」였습니다. 두 수가 **서로 다른 정의**였고(83 = `both_safe`
> 를 떠난 수, 1 = 버킷이 바뀐 수), 초안은 존재하지 않는다고 적은 출발지 단위
> 원장이 **실제로는 존재했습니다**. 정정 내역은 §10.

---

## 1. 확정된 서술, 그리고 쓰지 말아야 할 세 가지

> 한 산불 대피 라우팅 시스템에서, 자체 발견·정정된 **두 건**의 실제 자료 결함에
> 대해 운영 판정(출발지 분류)의 이동량을 **지역별로** 실측했다. 두 사건은 서로
> 다른 지역 집합을 움직였고, **증상이 관측된 지역이 판정이 움직인 지역이
> 아니었다** — 결함이 보이지 않던 지역에서 **90개** 출발지의 판정이 바뀌었고,
> 결함이 보이던 지역에서는 **1개**였다.

**90 과 1 은 같은 정의입니다** — 출발지 단위 원장에서 버킷이 바뀐 출발지 수
(§3.2). 초안의 「83」은 `both_safe` 를 떠난 수이고 울진의 「1」은 버킷이 바뀐
수여서, 둘을 나란히 놓으면 비교 불가능한 두 양을 비교하게 됩니다.

### ⚠ 세 가지는 검사되었고, 셋 다 지지되지 않습니다

| 쓰지 말 것 | 조사 결과 |
|---|---|
| **결함 건수를 표제로** | census 기록 156건은 *구별되는 결함 수*가 아닙니다. 4구분 이동을 주장한 항목 9건은 **사건 2개의 아홉 가지 서술**이었습니다. 하나의 측정을 아홉 번 세는 것은 §4-B 실패의 새 형태입니다 — 날조된 수치가 아니라 중복 계수. |
| **「세 지역」** | **어떤 결함도 세 지역을 동시에 움직이지 않았습니다.** 사건 1은 2개 지역, 사건 2는 1개 지역. 세 지역 모두에서 측정된 이동이 있는 것은 결함이 아니라 *평지-대-경사 대비*입니다(§5). |
| **신규성(「처음」/「최초」)** | 검증하지 않았습니다. 선행연구 부재 조사를 하지 않았습니다. Li et al. 2025 는 **gap 이 존재한다**는 것까지만 지지합니다(§6). |

⚠ **여기 쓰인 156 · 9 · 그리고 §8 의 97/26/33 은 세션 집계이며 커밋된 기록이
없습니다.** 대조할 산출물이 없다는 점에서, 이 문서 §8.1 이 「원리적으로 못 잡는
부류」라고 부르는 바로 그 형태입니다. 인용하실 거면 그렇게 표시하십시오.

### 등재된 규칙, 그리고 그 규칙이 닿지 않는 곳

세 형태는 `scripts/check_forbidden.py` 에 `kind="claim"` 규칙으로 등재했습니다.
값이 아니라 **문장 형태**를 잡습니다. 추가 전에 양방향으로 측정했습니다: 추적 중인
`.md` 트리에 대해 오탐 0건, 정당한 이웃 표현 다섯 개(「두 건의 … 결함」, 「세
지역의 커버리지 공변량」, 「처음 보는 사람도」, "the first slice of the hazard
field", 「n = 3」)에 대해 0/5.

⚠ **범위 한계, 명시:** 신규성 형태와 세-지역 형태는 온전히 잡힙니다. **결함-건수
형태는 29/30/31건 표기만** 잡습니다 — 이 문서가 경고하는 「156」·「9」 표기는
현재 패턴에 걸리지 않습니다. 두 자리 수를 전부 넣으면 일반 산문을 때리므로
넓히지 않았습니다.

---

## 2. 무엇을 세는가 — 사실 정정 두 가지

### 2.1 「4구분」이 아니라 7키 분할입니다

만들어지는 키는 일곱 개입니다:

```
naive_into_FA_safe   no_safe_route   both_safe
both_enter   naive_unreachable   fa_exceeds_budget   unclassified
```

한국 실행에서는 `both_enter` · `naive_unreachable` · `unclassified` 가 구조적으로
0 이라 네 개만 보입니다. 「4구분」은 관측 결과이지 설계가 아닙니다.

⚠ **정의 지점은 하나가 아니라 둘입니다.**

| 파일 | 무엇을 만드는가 |
|---|---|
| `scripts/run_real_roads_real_hazard_slope.py:101` | 영덕 정본/경사 계열 |
| `scripts/run_multi_region_routing.py:297` | **§3 의 다섯-커밋 표와 사건 1 표를 생산한 쪽** — `real_roads_real_hazard_{region}.json` (`:778`) 과 `multi_region_comparison.json` |

두 번째는 의도적 복사이며 자기 주석이 그렇게 적고 있습니다(`:265-266`
"The origin rule and the classification — LIFTED, not re-derived"; `:272-275`
는 「나중에 영덕 스크립트를 고쳐도 다지역 행의 의미가 조용히 재정의되지 않도록」
`candidate_origins` 도 import 하지 않고 복제한다고 적습니다).
분기 순서와 조건은 의미상 동일하고
`tests/test_multi_region_routing.py:111-119` 가 둘을 서로 대조해 고정하므로
**수치는 위험하지 않습니다.** 그러나 「정의가 하나뿐」은 거짓이고, §3 을 생산한
파일은 첫 번째가 아닙니다.

`:143` 이 `sum(counts.values()) == len(cand)` 를 assert 하므로 분할은 가정이
아니라 **강제**됩니다. 평가 순서(`:127-141`)가 의미를 가지며,
`fa_exceeds_budget` 분기는

```python
elif not nv.enters_hazard and not fa.reached:
```

입니다 — **조건이 예산을 언급하지 않습니다.** 버킷 이름이 코드가 확립하지 않은
원인을 지목하고 있습니다.

### 2.2 이름이 다른 두 번째 4구분이 있습니다 — 절대 섞지 마십시오

| | 라우팅 축 (459 계열) | 응답자 축 (439 계열) |
|---|---|---|
| 산출물 | `real_roads_real_hazard_canonical.json`, `…_uiseong_andong_2025.json`, `…_uljin_samcheok_2022.json` | `rescue_routing.json` |
| 경로 | `.arms.<arm>.counts` | `.four_way_counts` |
| 키 | `both_safe` · `naive_into_FA_safe` · `no_safe_route` · `fa_exceeds_budget` | `already_safe` · `saved_by_rescue_reachable_refuge` · `no_safe_pedestrian_route` · `no_surviving_vehicle_ingress` |
| 분모 | 458 / 368 / 393 | 439 |
| 화재장 | 실제 예측장 | 합성 envelope |

(구형 `real_roads_real_hazard.json` 은 `.counts` 를 최상위에 두고
`fa_exceeds_budget` 키가 아예 없습니다 — 6키입니다.)

확인 방법: `dispatch_ordering_comparison.json`, `ordering_boundary.json`,
`rescue_capacity.json` 어디에도 `naive_into_FA_safe` 나 `both_safe` 문자열이
**존재하지 않습니다.**

⚠ 응답자 축까지 세면 실측된 전후 쌍은 2건이 아니라 4건입니다. 그렇게 쓰려면
**다른 분류라고 명시**해야 하고, 하나의 숫자로 합치면 안 됩니다.

---

## 3. 두 사건

### 3.1 계수 이동은 두 곳에서만 일어납니다

`multi_region_comparison.json` 을 건드린 다섯 커밋에서 같은 JSON 경로를 읽은 결과
(벡터 = `n · both_safe/FA-only/no_safe_route/fa_exceeds_budget`):

| 커밋 | 날짜 | 영덕 | 의성·안동 | 울진·삼척 |
|---|---|---|---|---|
| `a32da6b` | 08-02 | 460 · 440/17/3/0 | 368 · 346/13/0/9 | 393 · 376/3/10/4 |
| `141b035` | 08-02 | 460 · 440/17/3/0 | 368 · 346/13/0/9 | 393 · 376/3/10/4 |
| `9ba83b4` | 08-02 | 460 · 440/17/3/0 | 368 · **263/91/12/2** | 393 · **377/3/10/3** |
| `815dc02` | 08-02 | 458 · **414/42/2/0** | 368 · 263/91/12/2 | 393 · 377/3/10/3 |
| `825aba9` | 08-03 | 458 · 414/42/2/0 | 368 · 263/91/12/2 | 393 · 377/3/10/3 |

(영덕 행의 되돌려진-장 삼중은 폐기된 판독입니다 — 정본 값은 414/42/2 입니다.)

### 3.2 사건 1 — DEM 재취득 (`9ba83b4`), 출발지 단위 원장으로

두 지역 모두 `.arms.slope_digraph_canonical.origin_nodes_by_bucket` 에 **출발지
단위 원장**이 있고, 분모가 양쪽에서 같으므로(368 / 393) 집합 연산이 유효합니다.

| | 영덕 | 의성·안동 | 울진·삼척 |
|---|---|---|---|
| 경사 arm 전 | 440/17/3/0 | 346/13/0/9 | 376/3/10/4 |
| 경사 arm 후 | (이동 없음) | **263/91/12/2** | **377/3/10/3** |
| **버킷이 바뀐 출발지** | — | **90** | **1** |
| ├ `both_safe` 를 떠남 | — | 83 | 0 |
| ├ `both_safe` 로 들어옴 | — | 0 | 1 |
| └ 그 밖의 버킷 간 이동 | — | 7 (전부 `fa_exceeds_budget` → `no_safe_route`) | 0 |
| 평지 arm | — | 354/13/0/1 → **266/96/6/0** | 380/4/9/0 → **비트 동일** |
| FA-only 비율 | — | 3.53 % → **24.73 %** | 0.76 % → 0.76 % |
| 최종 슬라이스 핵심 셀 | 변화 없음 | 95 → **131** (+38 %) | 263 → **292** (+11 %) |

산술 정합: FA-only +78, `no_safe_route` +12, `fa_exceeds_budget` −7 → 합 83 =
`both_safe` 감소분. 7개의 버킷 간 이동은 `both_safe` 바깥에서 일어나므로 합에
영향을 주지 않습니다. 울진의 1개는 노드 `1722506083`,
`fa_exceeds_budget` → `both_safe`.

### ⚠ 역전 — 이것이 발견입니다

**증상이 보인 지역이 판정이 움직인 지역이 아닙니다.**

* **울진·삼척**은 자기 raster 가 동해를 램프로 채웠고, 보행 노드 7,300개 중
  405개(5.55 %)가 DEM 밖이었습니다(`.dem_footprint.n_nodes_outside_dem`).
  그런데 판정이 바뀐 출발지는 **1개**, 평지 arm 은 380/4/9/0 로 **비트 동일** —
  화재장이 11 % 자랐는데도 재분류가 0 입니다. 도로가 내륙이라 채워진 바다는
  사람이 걷는 곳이 아니었습니다.
* **의성·안동**은 보행망 결함이 **0**이었습니다(DEM 밖 노드 0개, nodata
  0.002 %). 그런데 판정이 바뀐 출발지가 **90개**입니다. 원인은 자기 지형이 아니라
  **공유 학습셋**입니다 — 모델은 6개 화재 하나의 데이터셋에서 leave-one-fire-out
  으로 학습하므로, 울진의 가짜 바다는 다른 모든 화재의 학습 데이터였습니다.

**지역별 DEM 점검으로는 원리적으로 잡을 수 없습니다.** 점검은 결함이 보이는
층에서 이루어지고, 피해는 보이지 않는 층에 있었습니다.

#### 램프의 깊이 — 두 수를 구분하십시오

| 수 | 무엇인가 | 출처 |
|---|---|---|
| **−497 m**, 57,600 셀 중 49 % 음수 | **표본** 최솟값 | [`dem_defect_2026-08-02.md`](dem_defect_2026-08-02.md) §1 (커밋된 산문) |
| **−551.0 m**, 3,888,000 셀 중 **49.3 %** 음수 | **전체 래스터** 최솟값 | 2026-08-13 이 세션에서 살아남은 결함 raster 를 직접 열어 측정. **어떤 커밋 산출물에도 없습니다** |

「−497 m」를 쓰실 때는 표본 최솟값이라고 적으십시오. 「전체 raster 의 49 %」는
우연히 맞지만(49.3 %), −497 은 raster 최솟값이 아닙니다.

### ⚠ 영덕 — 무엇이 측정되었고 무엇이 아닌가

영덕 DEM 은 커밋된 산출물의 입력이라 재취득하지 않았습니다
(`dem_acquisition.json` 에 영덕 취득 기록이 없습니다). 그러나 울진은 영덕
화재장을 만든 학습셋에도 들어 있으므로 **결함은 영덕에도 적용되었습니다.**

⚠ **초안은 「그 크기가 분리된 적이 없다」고 적었고, 그것은 틀렸습니다.**
`data/processed/yeongdeok_dem_sensitivity.json` 이 영덕 **화재장**에 대한 DEM
효과를 분리해 커밋해 두었습니다 — `.delta_corrected_minus_old`:
핵심 셀 `[0, −28, −77, −97, −80]`, 최종 슬라이스 envelope **−2,000 ha**,
core growth **−32.65 pp**.

측정되지 않은 것은 **영덕의 판정(라우팅) 이동**입니다. `old_dem` arm 위에서
라우팅을 돌린 실행이 존재하지 않으므로, 영덕에 대해서는 이 문서가 다루는 양이
없습니다. 「해당 없음」이 아니라 **「이 축에서는 측정되지 않음」**입니다.

### 3.3 사건 2 — 정본 화재장 전환 (`815dc02`)

영덕만: **460 · 440/17/3/0 → 458 · 414/42/2/0**, FA-only 3.70 % → **9.17 %**
(앞의 둘은 되돌려진 장의 폐기 판독).

두 신규 지역이 움직이지 않은 것은 **결함이 적용되지 않았기 때문**입니다. 두 지역은
`routing_demo.npz` 를 읽은 적이 없고 각자의 새로 시뮬레이션된 화재장을 씁니다.

양쪽 값이 오늘 작업 트리 한 파일 안에 함께 있습니다 —
`real_roads_real_hazard_canonical.json` 의
`.side_by_side.committed_slope60_col3_jul24_network_old_hazard` 와
`.canonical_slope_jul24_network_canonical_hazard`. git 복구가 필요 없습니다.

---

## 4. ⚠ 반드시 함께 갈 단서 두 개

### 4.1 사건 1 의 세 구성 결함은 판정 이동에 대해 분리되지 않습니다

`9ba83b4` 는 세 가지를 **한 커밋에서 함께** 고쳤습니다:

| # | 결함 | 근거의 강도 |
|---|---|---|
| 1 | 해수 void-fill 램프 | 표본 49 % 음수·−497 m 는 **산문**(`dem_defect_2026-08-02.md` §1); 전체 raster −551.0 m / 49.3 % 는 이 세션 측정. 음수-고도 행 자체는 `dem_negative_elevation_audit.json` 이 분리 |
| 2 | 발자국 결손(울진 보행 노드 405/7,300) | **산출물** — `multi_region_comparison.json` `.regions[*].dem_footprint` |
| 3 | 시뮬레이션 캔버스 평균채움(의성 10.03 %, 울진 15.58 %) | **커밋 산문만** — `forward_sim_regions.json` 과 `dem_acquisition.json` 어느 쪽에도 이 필드가 없습니다 |

⚠ **정확한 주장은 좁은 쪽입니다:** *의성·안동의 90개 판정 이동을 이 셋으로
분해하는 산출물이 없습니다.* 커밋 본문의 귀속(「그 가짜 바다 경사가 다른 모든
화재 모델의 학습 데이터였다」)은 **산문 추론이며 분해된 측정이 아닙니다.**
따라서 90개(또는 83개) 이동을 **「해수 채움 때문」이라고 지목하지 마십시오.**

(초안은 「어떤 산출물도 이 셋을 분리하지 않는다」고 넓게 적었습니다. 그것은
과합니다 — `dem_negative_elevation_audit.json` 이 음수-고도 행을 분리하고,
`.dem_footprint` 가 의성의 이동에서 구성요소 2를 배제합니다.)

### 4.2 사건 2 는 단일변수가 아닙니다

새 화재장은 **동시에 세 가지**입니다:

* 되돌려진 2026-07-20 실행이 아니라 정본 데이터셋 실행
* **정정된 DEM 계보 위에서** 만들어짐 (`9ba83b4` 가 `05fbfca` 의 조상임을
  `git merge-base --is-ancestor` 로 확인)
* 캔버스가 181×147 → 181×156 으로 확장

그리고 **분모가 460 → 458 로, 순 2 줄었습니다.** 출발지 집합은
`candidate_origins()` (`run_real_roads_real_hazard_slope.py:79-98`,
`run_multi_region_routing.py:269-294` 에 복제)에서 t=0 핵심(`haz[0] >= 0.5`)과 그
중심 주변 밴드로 걸러지므로 **표본 프레임 자체가 화재장의 함수**입니다. t=0 핵심은
241 → 249 셀로 **커졌으므로**, 프레임이 잃기만 한 것이 아니라 얻기도 했을 수
있습니다. **어느 출발지가 들어오고 나갔는지는 어디에도 기록되어 있지 않습니다.**

⚠ **따라서 「N개가 재분류됐다」 형태의 문장은 이 쌍에 대해 검증 불가입니다.**
`real_roads_real_hazard_canonical.json` 의 `.side_by_side.*` 는
`n_origins_scanned` · `counts` · `status` 만 담고 있고, `.arms.*` 에도
`origin_nodes_by_bucket` 이 없습니다. **이 쌍에는 원장이 없습니다.**

⚠ 대조적으로 **사건 1 에는 원장이 있습니다**(§3.2) — 그래서 사건 1 은 90/1 로
정확히 말할 수 있고 사건 2 는 말할 수 없습니다. 두 사건을 같은 문장 형태로 쓰지
마십시오.

### 4.3 ⚠ 저장소가 이 점을 잘못 적고 있었습니다 — 일부만 정정 가능

[`multi_region.md`](multi_region.md) §1 과 커밋 `815dc02` 는
「440/17/3 → 414/42/2 는 화재장 **단독** 귀속」이라고 적고 있었습니다. **어느
입력이 바뀌었는지**로는 맞지만, 그 입력이 한 축이 아니라 세 축이고 분모까지
움직였으므로 단일변수 대비가 아닙니다. `multi_region.md` 는 정정했습니다. 커밋
본문은 이력이므로 고치지 않습니다.

⚠ **정정이 닿지 않는 곳, 기록:** `real_roads_real_hazard_canonical.json` 의
`.side_by_side.single_variable_pairs` 가 문자열로

> "col2 vs canonical_flat, and col3 vs canonical_slope, differ ONLY in the
> hazard field."

라고 **커밋된 산출물 안에서 계속 주장합니다.** §5.2 가 커밋 산출물 수정을
금지하므로 이 문장은 남습니다. 이 산출물을 인용하는 사람은 §4.2 를 함께 읽어야
합니다.

---

## 5. 파생 실험 — 같은 사건 2, 더 큰 이동

사건 2 는 **세 개**의 파생 실험에 완전한 전후 쌍을 남겼습니다. **셀 단위 이동이
가장 큰 것은 예산 스윕이며, 이것이 STEP 0 census 에서 누락되었습니다.**

### 5.1 예산 스윕 — 빠듯한 예산에서 `no_safe_route` 가 1.7–2.4배

`budget_sweep_experiment.json` `.sweep[i].future_aware_counts` 대
`objective_budget_canonical.json` `.budget_sweep.rows[i].future_aware_counts`:

| 예산 | 전 (n=460) | 후 (n=458) | `no_safe_route` 배율 |
|---|---|---|---|
| 30분 | 205/2/18/235 | **198/1/43/216** | **2.39×** |
| 60분 | 285/2/18/155 | **275/10/34/139** | 1.89× |
| 90분 | 342/2/18/98 | **329/11/33/85** | 1.83× |
| 120분 | 371/2/18/69 | **358/13/31/56** | 1.72× |
| 600분 | 440/17/3/0 | **414/42/2/0** | 0.67× (3 → 2) |

⚠ **「전 구간에서 두 배 이상」은 틀립니다** — 두 배를 넘는 것은 30분뿐이고,
600분에서는 오히려 내려갑니다. 방향(빠듯한 예산 전 구간에서 `no_safe_route` 상승,
`fa_exceeds_budget` 하락)은 맞고, 크기 수식어가 틀렸습니다.

읽는 법: **되돌려진 장의 근-정적 핵심이 빠듯한 예산에서 실패를 「예산 초과」로
보이게 하고 있었습니다.** 정본 장에서는 같은 압력이 「안전 경로 없음」으로
나타납니다 — 운영상 다른 답입니다.

### 5.2 목적함수 2×2 — 완전 null 이 깨집니다

`routing_objective_experiment.json` `.arms` 대
`objective_budget_canonical.json` `.objective_2x2.arms`:

| 셀 | 전 (n=460) | 후 (n=458) |
|---|---|---|
| 평지 / `length_m` | 440/17/3 | 415/41/2/0 |
| 평지 / `time_min` | 440/17/3 | 415/41/2/0 |
| 경사 / `length_m` | 440/17/3 | 414/42/2/0 |
| 경사 / `time_min` | 440/17/3 | **413/43/2/0** |

되돌려진 장에서는 네 셀이 전부 동일한 완전 null 이었습니다. 정본 장에서는
**경사 arm 안에서 목적함수를 바꾸면 계수가 1 만큼 달라집니다.**

⚠ **「출발지 1개가 뒤집힌다」고 쓰지 마십시오.** 측정된 것은 **순 차이 1**이며,
이 파일에는 출발지 단위 원장이 없습니다(`.objective_2x2.arms.*` 의 키는
`timing · objective · n_origins_scanned · counts · naive_mean_distance_m ·
naive_mean_time_min · naive_max_time_min` 뿐이고,
`.objective_2x2.slope_routes_changed` = 150 은 *경로* 변경이지 버킷 변경이
아닙니다). k개가 한쪽으로, k−1개가 반대쪽으로 갔을 수도 있습니다. 이것은 이
문서 §9 규칙 5 가 금지하는 문장 형태입니다.

### 5.3 경사 스윕 — 30/60/90 m 가 세 개의 다른 벡터

`real_roads_real_hazard_slope_{30,60,90}.json`
`.three_column_comparison.{col2_jul24_flat, col3_jul24_slope}` 대
`slope_sweep_canonical.json` `.arms`:

| 간격 | 전 (n=460) | 후 (n=458) | 평지 대비 이동 |
|---|---|---|---|
| 평지 대조 | 440/17/3 | 415/41/2/0 | — |
| 30 m | 440/17/3 | **413/42/3/0** | 3 |
| 60 m | 440/17/3 | **414/42/2/0** | 1 |
| 90 m | 440/17/3 | **415/41/2/0** | 0 |

여기 「평지 대비 이동」은 원장 기반입니다 —
`.bucket_movement_vs_flat_control.per_spacing` 이 움직인 노드를 이름으로
열거합니다. (`col1_committed_jul23_flat` 은 459 · 438/18/3 로 **다른 벡터**이며
혼동하면 안 됩니다.)

### 5.4 ⚠ PHASE 2 결론에 영향을 주는가 — 판정

**문자적 형태는 깨졌고, 실질적 결론은 살아남습니다. 철회가 아니라 재서술입니다.**

* **깨진 것:** 「30/60/90 m 에서 계수가 동일」이라는 문자적 null. 정본 장에서 세
  간격은 세 개의 다른 벡터를 냅니다.
* **살아남은 것:** 「지형은 *어떻게* 걷는지를 바꾸지 *도달 여부*를 바꾸지
  않는다」. 근거는 **더 강해졌습니다**: `moved_at_all_spacings` = **[]** — 세 간격
  *모두*에서 버킷이 바뀌는 출발지는 **0개**입니다. 움직이는 세 출발지
  (`6205151092`, `12044832090`, `12048310971`)는 각각 한두 간격에서만 움직이고,
  이동은 샘플링이 유발한 시간 페널티(+40.4 / +26.6 / +21.0 %)에 단조입니다.
  산출물 자신의 판정이 `inconsistent_across_spacings` 입니다.

⚠ **이 판정의 출처를 정확히 하십시오.**
[`slope_integration.md`](slope_integration.md) 는 **수치를 전부 올바르게
기록**했고 실질적 판정도 내렸습니다(413/43/2 포함). 그러나 `:103` 은 null 이
정본 장에서도 **「holds」**라고 적습니다 — 문자적 불변성이 깨졌다는 진술은
어디에도 없습니다. **문자적/실질적 분리는 이 문서가 처음 내리는 판정입니다.**

⚠ **그리고 `multi_region.md` 는 반대로 적고 있었습니다 — 정정함.** `:218-220`
과 §8 규칙 11 이 「30/60/90 m 슬로프 실험과 PHASE-2-C 목적·예산 스윕은 정본
장에서 재실행되지 않았다」고 적고 있었습니다. `slope_sweep_canonical.json` 과
`objective_budget_canonical.json` 은 **커밋되어 있고 baseline freeze 에
있습니다.** 두 곳 모두 정정했습니다.

⚠ **레지스트리는 여전히 따라오지 않았습니다 — 열려 있는 항목.**
`docs/NUMBERS.json` 의 `slope_counts_unchanged_vs_flat` 와
`objective_counts_still_unchanged` 는 여전히 `value: true` 이고, 후자의 caveat 은
"the classification is still invariant" 라고 단언합니다. 두 항목은 **되돌려진
장의 측정을 서술**하므로 값 자체는 틀리지 않지만, 정본 장 결과로 가는 포인터가
없습니다. 이 파일은 `scripts/build_numbers.py` 가 생성하므로 수정에는 생성기
편집과 레지스트리 재생성이 필요합니다 — **STEP 0 의 범위를 넘으므로 하지
않았습니다.** 사용자 결정 사항입니다.

---

## 6. 문헌

### Li et al. (2025) — 확인됨, 인용 위치를 정정해야 합니다

* 제목: *"Mapping the Completeness and Positional Accuracy of OpenStreetMap Road
  Data at the County Level in the Contiguous United States"*
* *Transactions in GIS* 29(4):e70077, 2025. DOI `10.1111/tgis.70077`.
  PMID 41000462 / PMCID PMC12459646.

⚠ **해당 문장은 초록이 아니라 §4 Discussion 에 있습니다**, 그리고 문구가 다릅니다:

> "More research still needs to be conducted to assess how OSM road quality
> impacts the results when OSM roads are used in different applications."

`different applications` 이지 `various applications` 가 아니고, `impacts` 이지
`affects` 가 아닙니다. 바꿔 쓴 형태를 인용문으로 제시하지 마십시오.
초록에는 이 gap 진술이 **없습니다** — 초록에서 가장 가까운 문장은 데이터 이용자가
"better use OSM road data in different applications" 할 수 있게 한다는 **효용
주장**이며, 연구 gap 진술이 아닙니다.

**같은 문단이 산불 대피를 직접 사례로 듭니다** — 이것이 이 프로젝트와의 정렬점입니다.
OSM 도로 데이터가 "can be used as input for wildfire evacuation traffic simulation
to derive evacuation time estimates (ETEs)" 라고 적고, 완성도 부족이

> "may reduce the number of egresses in wildfire evacuation simulation, which
> can significantly impact the derived ETEs."

라고 씁니다.

⚠ **판본 단서, 반드시 함께 적을 것:** 위 문장들은 PMC 에 기탁된 **NIH 저자원고**
(PMC12459646)에서 읽었습니다. Wiley 정식본은 기사 페이지와 pdfdirect 양쪽 모두
**HTTP 402** 로 접근하지 못했습니다. 정식본 문구가 동일한지 확인하지 못했으며,
**정식본에 대한 쪽수·행 인용은 미검증**입니다.

### Herfort et al. (2023) — 확인됨

*"A spatio-temporal analysis investigating completeness and inequalities of
global urban building data in OpenStreetMap"*, *Nature Communications* 14:3985,
DOI `10.1038/s41467-023-39698-6`, PMCID PMC10326063.

13,189개 도시권을 1 km² 격자(총 665,641 셀)로 나누고, 162개국 6,633개 도시권의
외부 참조 데이터(권위 기관 + 상용 소스)로 학습한 Random Forest 로 셀별 건물
**면적**을 예측한 뒤 OSM 면적과의 비로 완성도를 정의합니다. **건물 개수가 아니라
면적**인 것은 의도적이며, Methods 가 디지타이징 관행 차이를 이유로 듭니다.

⚠ Methods 안에서 비율의 **방향이 서로 뒤집혀** 인쇄된 곳이 있습니다. 보고된
백분율과 정합적인 방향은 `OSM ÷ predicted` 입니다. 공식을 인용하실 거면 Methods 를
직접 여십시오.

⚠ **두 문헌 항목 모두 이 저장소 안에서는 검증 불가능합니다** — 대조할 파일이
없습니다. 인용을 확정하실 때 검색 기록(날짜·URL)을 함께 남기십시오. 날조는
없었습니다.

---

## 7. 이미 있는 것과 재실행 비용

### 7.1 재실행 없이 지금 쓸 수 있는 쌍

| 양 | 전 | 후 |
|---|---|---|
| far-band AUC | `spread_v2_lofo.json` `.far_band_auc` = 0.8766 | `spread_v2_lofo_dem_corrected.json` = **0.8408** (Δ −0.0357) |
| 강릉 폴드 AUC | 0.6820 | **0.7184** (Δ +0.0364) |
| 영덕 커버리지 | `a32da6b` `.regions[0].envelope_coverage_final_slice` = 0.5041 | 작업 트리 = **0.3263** |
| envelope 삼중 | `a32da6b` = 6100 / 2375 / 6575 ha | HEAD = **25900 / 3275 / 7300** |
| 영덕 화재장 DEM 효과 | — | `yeongdeok_dem_sensitivity.json` `.delta_corrected_minus_old` |
| 응답자 4구분 | `rescue_baseline_synthetic/rescue_routing.json` 452 · 154/34/244/20 | `rescue_routing.json` 439 · **262/10/143/24** |
| OSM 망 드리프트 | 439 · 262/10/143/24 | 441 · **255/12/142/32** |

### 7.2 ⚠ HANDOFF 오류 — 재실행 경로가 문서와 달랐습니다

**(1) 「스크립트는 전부 `--out` 을 받는다」는 거짓이었습니다.**
`HANDOFF_ROUND3.md` §7 규칙 1 은 *"The scripts all take one; the danger is the
default, not the flag."* 로 **끝나 있었습니다**(같은 작업에서 정정함 — 현재
문안은 그 문장을 이력으로 인용합니다). `data/processed` 를 참조하면서 out-플래그를
노출하지 않는 스크립트가 **18개**이고, 그중 **10개가 `data/processed` 에 직접
씁니다**:

| 스크립트 | 쓰는 곳 |
|---|---|
| `run_forward_sim_region.py` | `forward_sim_regions.json`, `hazard_{fire_id}.npz` (`OUT_DIR`, `:65`) |
| `export_demo_data.py` | `demo_data.json` (`OUT`, `:73`) |
| `measure_weather_dependency.py` | `weather_dependency.json` (`:44`) |
| `verify_rescue_routing.py` | `rescue_capacity.json`, `rescue_verify.json`, `rescue_verify_fc.json` (`:59`) |
| `derive_walk_failure.py` | `rescue_verify_fc.json` (`:28`) |
| `crown_sensitivity.py` | `crown_sensitivity.json` (`:119`) |
| `diagnose_crown.py` | `crown_diagnostic_log.json` (`:103`) |
| `waf_sensitivity_sweep.py` | `waf_sensitivity.json` (`:173`) |
| `run_ablation.py` | `yeongdeok_2025_ablation.json` (`:98`) |
| `run_yeongdeok_validation.py` | `yeongdeok_2025_validation_results.json` (`:138`) |

`run_forward_sim_region.py` 의 전체 argparse 표면(`:161-176`)은
`--fires --cell-m --n-steps --step-hours --advance-threshold --p-cut --seed
--walk-margin-km --acknowledge-fuel-gap` 이며 **`--out` 계열이 없습니다.**
⚠ 이 스크립트들에 대해서는 **위험이 기본값이 아니라 플래그의 부재**입니다.

**(2) 열여덟 중 일곱 이상은 `ArgumentParser` 자체가 없습니다** —
`export_demo_data.py` 가 대표 예이고(`OUT` 이 `:73` 에 하드코딩),
`run_ablation.py` 와 `run_yeongdeok_validation.py` 도 그렇습니다.

추가로 `make_rescue_figures.py` · `make_routing_figures.py` ·
`make_ordering_boundary_figure.py` 는 `docs/figures/*.png` 에 쓰며, §5.3 이
재생성을 금지합니다.

**(3) ⚠ 초안의 「결함 DEM 바이트 복구 불가」는 틀렸습니다 — 정정.**
결함 raster 는 **작업 트리에 살아 있습니다**:

| | 경로 | sha256 |
|---|---|---|
| 울진·삼척 결함본 | `data/raw/firms_CANONICAL_TEST/uljin_samcheok_2022_dem.tif` | `4850941d…` ✓ `dem_acquisition.json` `.replaced.sha256` 와 일치 |
| 의성·안동 결함본 | `data/raw/firms_CANONICAL_TEST/uiseong_andong_2025_dem.tif` | `14288109…` ✓ 일치 |

`data/snapshots/` 는 **정정된** 바이트만 담고 있고, `data/raw/**` 는
git-ignored 이므로 **이 바이트는 어떤 커밋에도 없고 새로 클론하면 사라집니다.**

따라서 §4.1 의 분해 불가는 **원리 문제가 아니라 비용·취약성 문제입니다.**
분해는 원칙적으로 가능하되, 입력이 추적되지 않는 파일이라 이 기기 밖에서는
재현되지 않습니다. ⚠ **이 파일들은 다른 어디에도 없습니다. 지우지 마십시오.**

### 7.3 측정된 런타임 (추정 아님, 산출물에서 읽음)

459-스캔 의성 **87.4 s** · 울진 **61.9 s** (`.runtime_s`) · LOFO arm
**22.3–38.0 s** · 배차 순서 4-arm **159.1 s** · 순서 경계 4-arm **176.2 s** ·
DEM 다운로드 **15.7 / 17.2 s**.

---

## 8. 섭동 유형 분류 — 4분류가 닿지 않는 곳

「입력 자료의 성질」로 분류하는 4분류(커버리지 · 무결성 · 계보 · 파라미터)를
census **기록** 156건에 적용한 결과: **GOOD-FIT 97 · FORCED 26 ·
DOES-NOT-FIT 33.** ⚠ 이 세 수와 156 은 §1 과 같은 세션 집계이며 **커밋된 기록이
없습니다.** 그리고 156은 중복 제거된 수가 아닙니다.

**33건을 억지로 넣지 않았습니다.**

### 8.1 ⚠ 별도 범주 — 섭동된 것이 입력이 아니라 세션 기록

`vpd-unit-defect-never-existed` · `fabricated-phase20-step0` ·
`fabricated-completed-phase20` · `shelter-search-78pct-11908-dijkstra` ·
`vpd-importance-rank-claim`

이들은 **섭동된 입력이 없습니다.** 인용된 사건이 어느 브랜치·stash·reflog 에도
존재한 적이 없습니다. 4분류는 전부 「어떤 자료가 어떻게 잘못되었나」를 묻는데,
여기서는 잘못된 것이 자료가 아니라 **무엇이 측정되었는지에 대한 기록**입니다.

이 범주가 독립적이어야 하는 이유는 §4-B 가 스스로 적고 있습니다: 이 저장소의 모든
가드는 레지스트리 기반이라 *폐기된* 값의 재인용은 잡지만, **일어난 적 없는 사건의
인용은 대조할 파일이 없어 원리적으로 못 잡습니다.**

### 8.2 나머지 DOES-NOT-FIT

표현·레이아웃 결함(`kubun-column-clipped-silently`), 지표 정의
결함(`severity-over-direction-44x-withdrawn`, `tautological-ratio-1.000`), 추론
과잉일반화(`committed-model-order-insensitivity-overgeneralised`).

### 8.3 ⚠ 「커버리지」는 두 축입니다 — 갈라 쓰십시오

| 축 | 뜻 | 예 |
|---|---|---|
| **자료 커버리지** | 지도·보행망·래스터의 완성도 | 울진 보행 노드 405개가 DEM 밖; 영덕 보행 bbox 가 핵심의 32.6 % |
| **검사기 스코프 커버리지** | 가드가 실제로 스캔하는 표면 | `check_forbidden.py:226-228` (`is_authored_prose`)이 `.md` 로만 한정 → 폐기 계보를 실은 `.html` 화면이 조용히 통과 |

하나로 묶으면 「보이지 않던 지역이 움직였다」 같은 발견이 「검사기에 구멍이
있었다」와 한 칸에 들어가 버립니다.

---

## 9. 규칙

1. **결함 건수를 판정-이동 주장의 표제로 쓰지 마십시오.** 실측된 사건은
   라우팅 축 **2건**입니다(응답자 축까지 4건, 다른 분류라고 명시할 것).
2. **「세 지역」을 결함 이동 주장에 쓰지 마십시오.**
3. **신규성을 주장하지 마십시오.** 검증하지 않았습니다.
4. **90(또는 83)개 이동을 「해수 채움 때문」이라고 지목하지 마십시오** (§4.1).
5. **순 계수 차이를 출발지 단위 사건으로 서술하지 마십시오.** 「N개가
   재분류됐다」·「1개가 뒤집힌다」는 원장이 있을 때만 쓸 수 있습니다 — 사건 1과
   경사 스윕에는 있고, 사건 2와 목적함수 2×2에는 없습니다 (§4.2, §5.2).
6. **이동 수를 인용할 때 정의를 함께 적으십시오** — `both_safe` 를 떠난 수와
   버킷이 바뀐 수는 다른 양입니다 (의성 83 대 90).
7. **두 개의 4구분을 섞지 마십시오** (§2.2).
8. **`fa_exceeds_budget` 를 예산이 원인이라고 읽지 마십시오** (§2.1).
9. **−497 m 를 raster 최솟값이라고 쓰지 마십시오** — 표본 최솟값입니다 (§3.2).
10. **영덕 절대 비율에는 32.6 % 커버리지 단서를 함께** (§5 규칙 19).
11. **Li et al. 을 초록 인용으로 쓰지 마십시오**, 저자원고에서 읽었다는 것을
    함께 적으십시오 (§6).
12. **`data/raw/firms_CANONICAL_TEST/` 를 지우지 마십시오** (§7.2).

---

## 10. 이 문서의 초안에서 정정된 것

초안은 4개 독립 에이전트의 적대적 검증을 받았고 95개 주장 중 43개가
CONFIRMED 가 아니었습니다. 실질을 바꾼 것들:

| 초안 | 정정 |
|---|---|
| 「83개 대 1개」 | 서로 다른 정의였음. **90 대 1**(버킷 변경) 또는 83 대 0(`both_safe` 이탈) |
| 「이 쌍에는 원장이 없다」(사건 1) | **원장이 있음** — `origin_nodes_by_bucket`. 없는 것은 사건 2 |
| 「`classify()` 정의는 하나뿐」 | **둘**이고, §3 을 생산한 것은 인용하지 않은 쪽 |
| 「`no_safe_route` 가 전 구간 두 배 이상」 | **1.7–2.4배**, 두 배 초과는 30분뿐 |
| 「결함 DEM 바이트 복구 불가 = 원리 문제」 | 바이트가 작업 트리에 **살아 있음**. 비용·취약성 문제 |
| 「영덕은 크기가 분리된 적 없음」 | 화재장 효과는 `yeongdeok_dem_sensitivity.json` 에 **분리되어 있음**. 미측정인 것은 판정 이동 |
| 「8개 스크립트가 data/processed 에 쓴다」 | **10개** |
| 「출발지 2개가 프레임을 떠났다」 | 분모가 **순 2 감소**. 어느 출발지인지는 미기록 |
| 「목적함수가 출발지 1개를 뒤집는다」 | **순 차이 1**. 원장 없음 |
| 「어떤 산출물도 세 결함을 분리하지 않는다」 | 판정 이동에 대해서만 참 |
| 「저장소가 이미 올바르게 판정했다」 | 수치는 기록했으나 문자적 null 이 깨졌다는 진술은 없었음 |
| −497 m | **표본** 최솟값. 전체 raster 는 −551.0 m / 49.3 % |
