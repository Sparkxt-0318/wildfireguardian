# 결선 화면의 숫자 → 레지스트리 키 (WFG-110)

*작성: 자율 루프 2026-09-07T1528Z 랩. 방법을 제안한 것은 루프이고, 표의 칸을 채운 것은
템플릿의 카드 블록 여덟 개를 손으로 읽은 결과입니다 (CHARTER §9).*

## 0. 이 문서가 답하는 질문 하나

심사위원이 화면의 숫자를 가리키며 **「이 숫자는 어디서 나온 겁니까」** 라고 물을 때,
학생이 펼칠 수 있는 표입니다. 준비도 항목 **R1** 이 요구하는 방향이기도 합니다.

이 방향의 표는 지금까지 없었습니다. `docs/auto/DEMO_SCRIPT_5MIN.md` §3 의 표는
**반대 방향**입니다 — *학생이 말하는 값* 에서 키로 갑니다. 그 표는 대본을 지키는 데는
맞지만, 심사위원이 **화면을 먼저 가리키는** 순간에는 역인덱스가 필요합니다.

## 1. 방법

**무엇이 「화면」인지 판정하는 기준은 `scripts/finals.template.html` 입니다.** 빌드된
`web/finals.html` 에 키가 들어 있다는 것은 근거가 되지 않습니다: `scripts/build_finals.py`
가 레지스트리 조각을 **JSON 한 덩어리로 통째로** 심어 넣기 때문에, 어떤 카드도 읽지 않는
키까지 파일 안에는 정확히 한 번씩 나타납니다. 이 기준은 §3 표가 이미 쓰고 있는 것과
같습니다 (`tests/test_demo_script_5min.py`).

카드를 만드는 호출은 딱 두 가지입니다 — 근거(EVIDENCE) 뷰의 `evCard(grid, kicker, ...)`
와 신뢰성(RELIABILITY) 뷰의 `rel(title, ...)`. 키는 둘 중 한 자리에 나타납니다: 카드
호출의 괄호 **안**, 또는 그 카드를 만드는 중괄호 블록의 `const e = regEntry('...')`
**머리말**. 앞의 것은 그 카드에, 뒤의 것은 파일에서 **다음에 오는** 카드 호출에
속합니다. `scripts/finals_screen_keys.py` 가 그 규칙을 그대로 구현합니다.

**표를 만든 순서가 중요합니다.** 카드 블록 여덟 개를 먼저 손으로 읽어 아래 표를 채웠고,
그 다음에 `finals_screen_keys.py` 를 돌려 대조했습니다. 28개 키 전부에서 두 결과가
일치했습니다. 순서를 뒤집었다면 (스크립트로 표를 생성하고 스크립트로 검사했다면) 이
표는 자기 자신을 확인하는 문서였을 것입니다.

## 2. 표 — 화면의 카드에서 레지스트리 키로

뷰는 `근거` = EVIDENCE 탭, `신뢰성` = RELIABILITY 탭입니다.
`§3` 열은 그 키가 `docs/auto/DEMO_SCRIPT_5MIN.md` §3 의 대본 표에도 있는지입니다.

| # | 뷰 | 카드 (kicker) | 레지스트리 키 | 그 카드에서 하는 일 | §3 |
|---|---|---|---|---|---|
| 1 | 근거 | 확산 모델 · LOFO 교차검증 | `lofo_mean_of_folds_auc` | 카드의 출처(prov) 줄 | ✅ |
| 2 | 근거 | 구조자 측 · 위험 노출 대비 | `responder_exposure_reduction_pct` | 본문의 감소율, 그리고 출처 줄 | ✅ |
| 3 | 근거 | 구조자 측 · 위험 노출 대비 | `responder_exposure_shortest_path_mean` | 큰 숫자의 **왼쪽** 값 | ❌ |
| 4 | 근거 | 구조자 측 · 위험 노출 대비 | `responder_exposure_survival_aware_mean` | 큰 숫자의 **오른쪽** 값 | ❌ |
| 5 | 근거 | 구조자 측 · 위험 노출 대비 | `rescue_dispatch_count` | 본문의 짝지은 출발지 개수 | ❌ |
| 6 | 근거 | 지형 보정 · 경사가 걸음을 바꿉니다 | `slope_walk_time_increase_pct` | 큰 숫자, 그리고 출처 줄 | ✅ |
| 7 | 근거 | 지형 보정 · 경사가 걸음을 바꿉니다 | `slope_canonical_fa_routes_changed_60m` | 본문의 「형태가 바뀐 경로」 건수 | ❌ |
| 8 | 근거 | 지형 보정 · 경사가 걸음을 바꿉니다 | `objective_canonical_longest_walk_saving_min` | 본문의 최악 사례 1건 절감 분 | ❌ |
| 9 | 근거 | 운영점 · 임계값에서 실제로 잡히는 비율 | `oof_pooled_recall_at_operating_threshold` | 큰 숫자, 그리고 경고 줄 | ✅ |
| 10 | 근거 | 운영점 · 임계값에서 실제로 잡히는 비율 | `oof_mean_of_folds_recall_at_operating_threshold` | 본문의 폴드 평균 재현율 | ✅ |
| 11 | 근거 | 운영점 · 임계값에서 실제로 잡히는 비율 | `oof_average_precision` | 본문의 평균 정밀도 | ❌ |
| 12 | 근거 | 운영점 · 임계값에서 실제로 잡히는 비율 | `oof_prevalence` | 본문의 유병률 (평균 정밀도의 기준선) | ✅ |
| 13 | 근거 | 탐지 바닥 · 정지궤도 위성이 볼 수 없는 구간 | `det_size_floor_ha_tf750` | 큰 숫자의 구간, 그리고 경고 줄 | ✅ |
| 14 | 근거 | 탐지 바닥 · 정지궤도 위성이 볼 수 없는 구간 | `det_gk2a_delay_uiseong_andong_min` | 본문 지연 목록의 첫 값 | ✅ |
| 15 | 근거 | 탐지 바닥 · 정지궤도 위성이 볼 수 없는 구간 | `det_gk2a_delay_gangneung_2023_min` | 본문 지연 목록의 둘째 값 | ✅ |
| 16 | 근거 | 탐지 바닥 · 정지궤도 위성이 볼 수 없는 구간 | `det_gk2a_delay_hongseong_2023_min` | 본문 지연 목록의 셋째 값 | ✅ |
| 17 | 근거 | 탐지 바닥 · 정지궤도 위성이 볼 수 없는 구간 | `det_control_steps` | 본문의 대조 스텝 수 | ✅ |
| 18 | 근거 | 탐지 바닥 · 정지궤도 위성이 볼 수 없는 구간 | `det_false_alarm_steps` | 본문의 오경보 스텝 수 | ✅ |
| 19 | 근거 | 240분 지평의 근거 · 표본은 6건이 아니라 2천 건 | `kfs_cum_le_240_pct` | 큰 숫자, 그리고 경고 줄 | ✅ |
| 20 | 근거 | 240분 지평의 근거 · 표본은 6건이 아니라 2천 건 | `kfs_n_usable_events` | 큰 숫자 아래 라벨의 n | ✅ |
| 21 | 근거 | 240분 지평의 근거 · 표본은 6건이 아니라 2천 건 | `kfs_containment_median_min` | 본문의 진화 중앙값 | ✅ |
| 22 | 근거 | 240분 지평의 근거 · 표본은 6건이 아니라 2천 건 | `kfs_area_ge100ha_median_min` | 본문의 100 ha 이상 중앙값 | ✅ |
| 23 | 근거 | 대피 지점 배치 · 한 곳을 더 두면 | `l0i_best_single_refuge_saved` | 큰 숫자의 **왼쪽** 값 | ✅ |
| 24 | 근거 | 대피 지점 배치 · 한 곳을 더 두면 | `l0i_best_pair_saved` | 큰 숫자의 **오른쪽** 값, 그리고 경고 줄 | ✅ |
| 25 | 근거 | 대피 지점 배치 · 한 곳을 더 두면 | `l0i_third_refuge_gain` | 본문의 세 번째 지점 이득 | ✅ |
| 26 | 근거 | 대피 지점 배치 · 한 곳을 더 두면 | `l0i_candidates_enumerated` | 본문의 후보 노드 수 | ✅ |
| 27 | 신뢰성 | 부정 결과도 결과입니다 · 배차 정렬 | `dispatch_order_deadline_wins_pct` | 본문의 우세 비율 | ✅ |
| 28 | 신뢰성 | 부정 결과도 결과입니다 · 배차 정렬 | `ordering_boundary_first_window_with_a_win` | 본문의 최초 승리 창 W | ✅ |

카드 8개, 키 28개. `대피 지점 배치` 카드의 kicker 는 화면에서 뒤에 지역 라벨이 괄호로
붙습니다 (`siteRow.label`); 위 표에는 템플릿에 적힌 고정 부분만 적었습니다.

## 3. §3 표에 없던 여섯 개

`objective_canonical_longest_walk_saving_min`, `oof_average_precision`,
`rescue_dispatch_count`, `responder_exposure_shortest_path_mean`,
`responder_exposure_survival_aware_mean`, `slope_canonical_fa_routes_changed_60m`.

크리틱 #19 가 `92bfc4f` 에서 센 여섯 개와 같습니다. 이 랩이 그 계산을 스스로 다시
돌려 같은 여섯 개를 얻었습니다 (§1 의 스크립트, `docs/auto/DEMO_SCRIPT_5MIN.md` §3 의
파싱은 `tests/test_demo_script_5min.py` 와 같은 규칙).

**이것은 대본의 결함이 아닙니다.** 여섯 개 전부 학생이 **말하지 않는** 값이고, §3 은
말하는 값의 표입니다. 화면에는 그려지지만 5분 대본에서는 발음되지 않는 숫자가 있다는
뜻일 뿐이며, 심사위원이 그 여섯 개 중 하나를 가리키는 경우가 바로 이 문서가 필요한
경우입니다.

## 4. 한계 — 이 문서가 보여 주지 않는 것

- **화면이 그렇게 그려진다는 증명이 아닙니다.** 템플릿의 **소스**를 읽은 결과이고,
  브라우저에서 렌더링한 결과를 대조한 것이 아닙니다. 카드가 `if (…)` 조건 안에 있어
  레지스트리 항목이 없으면 아예 그려지지 않는 카드가 여럿입니다.
- **키가 화면에 그려지는 「모든」 숫자를 덮지 않습니다.** 레지스트리 키로 등록되지 않은
  화면 값 — 지역 표의 값, `DATA.ev2` 안의 파생 값, 실행 시간 — 은 여기 없습니다. R1 이
  묻는 것은 「레지스트리 키로 가는 숫자」의 사상이고, 그 밖의 값이 어디서 오는지는
  `docs/finals_screen_v2.md` 와 각 카드의 출처(prov) 버튼입니다.
- **귀속이 옳다고 말해 주지 않습니다.** 게이트는 이 표와 템플릿이 **서로 어긋나지
  않는다**는 것만 봅니다. 둘 다 같은 방식으로 틀릴 수 있고, 그래서 §1 에 손으로 읽은
  순서를 적어 두었습니다.
- **숫자의 값을 적지 않습니다.** 값은 `docs/NUMBERS.json` 과 `make verify` 의 것이고,
  이 문서에 값을 옮겨 적으면 같은 값이 두 곳에서 갈라질 수 있습니다 (CHARTER §3.3).

## 5. 게이트

`tests/test_finals_screen_numbers.py`:

| 테스트 | 무엇을 잡는가 |
|---|---|
| `test_the_table_covers_exactly_the_keys_the_template_references` | 카드가 새로 생겨 키가 늘었는데 이 표에 안 들어온 경우, 그리고 카드가 지워졌는데 표에 남은 경우 |
| `test_every_key_in_the_table_resolves_in_the_registry` | 이 표가 존재하지 않는 키를 가리키는 경우 |
| `test_every_row_names_the_card_the_template_puts_the_key_on` | 카드 사이로 키가 옮겨졌는데 표는 옛 카드를 가리키는 경우 |
| `test_every_row_names_the_view_that_builds_that_card` | `evCard` / `rel` 이 바뀌었는데 뷰 이름이 그대로인 경우 |
| `test_no_key_is_attributed_to_more_than_one_card` | 파생 규칙이 어떤 키를 카드 하나로 못 좁히는 경우 (그때는 §2 의 그 줄을 믿으면 안 됩니다) |
| `test_the_table_is_parseable_and_not_vacuous` | 표 머리글이 바뀌어 위 검사들이 **아무것도** 읽지 않게 되는 경우, 그리고 §1·§2 의 산문이 말하는 「카드 8개, 키 28개」가 트리와 어긋나는 경우 |
| `test_the_six_keys_absent_from_the_demo_script_are_named_here` | §3 과의 차집합이 바뀌었는데 §3 절의 목록이 그대로인 경우 |

이 표는 7줄이고 파일의 테스트도 7개입니다 — 그 대응 자체는 게이트가 아니라 손으로 맞춘
것이고, 어긋나면 문서가 자기 게이트를 잘못 세는 것이 됩니다 (이 랩의 독립 검토자가 초안에서
6개로 센 것을 잡았습니다).
