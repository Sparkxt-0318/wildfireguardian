# 철회된 주장 레지스트리 — 방법, 결과, 한계

*작성: 자율 루프 dev 랩 20260904T2119Z (WFG-062). 방법을 제안한 것은 학생이 아니라
루프입니다 (CHARTER §9). 이 문서는 게이트 하나를 설명합니다; 게이트가 지키는 주장들의
내용은 `docs/detection_floor.md` 와 `docs/auto/JUDGE_QA.md` Q10 에 있습니다.*

## 0. 한 문장

이 저장소가 **철회한 주장**들을 파일 하나(`docs/auto/withdrawn_claims.json`)에 모으고,
추적되는 **모든** 문서를 그 파일에 대고 검사합니다. 어제까지는 "이 주장이 없어야 할
파일"을 손으로 열거하는 방식이었고, 그 목록은 (이 커밋 기준) 988개 중 **11개**를
덮고 있었습니다.

## 1. 왜 필요했는가 — 실제로 새어나간 것은 철자가 아니라 파일이었습니다

이 루프가 대가를 치른 세 번의 누락은 모두 **아무도 목록에 넣지 않은 파일**입니다.

| 언제 | 어디 | 무엇 |
|---|---|---|
| WFG-063 | `docs/SESSION19_REPORT.md` | 「아무도 목록에 넣지 않은 세션 보고서」가 순위표와 일차 주장을 주석 없이 그대로 들고 있었습니다 |
| WFG-070 | `docs/auto/research/RESEARCH_BRIEF_2026-09-03.md`, `sweeps_2026-09-03/R3_science_gaps.md` | 같은 주장이 **영어로** 살아 있었고, 한국어 목록은 영어를 읽지 않았습니다 |
| WFG-070 (같은 랩) | `sweeps_2026-09-03/R7_rubric_gap.md` | 찾으러 간 행 자신도 모르던 세 번째 사례 |

`tests/test_detection_ordering_is_not_claimed.py` 는 주장군 4개와 손으로 쓴 가드 목록
5개를 들고 있습니다. 그 합집합이 **11개 파일**입니다. 이 커밋에서 추적되는
`.md` · `.html` 는 **988개**입니다.

## 2. 방법

- **레지스트리** `docs/auto/withdrawn_claims.json`: 주장 하나당 `id`, 무엇을 주장했는지,
  **무엇이 그것을 철회했는지**(결정과 아티팩트), **대신 무엇을 말해야 하는지**,
  그리고 금지된 **철자들**(정규식 + 프래그마 토큰 + 이유).
- **기본 범위는 전부**: 추적되는 모든 `.md` · `.html`. 예외는 한 종류뿐이고,
  레지스트리 안에 **한 줄씩 이유와 함께** 적혀 있습니다 — 루프 자신의 기록물
  (`docs/auto/reports/`, MEMO, NEEDS_HUMAN, BACKLOG, SCORECARD, CRITIC_LATEST,
  KCF_READINESS, DIRECTION, CHARTER, ROUTINE_PROMPTS, `docs/auto/archive/`,
  생성된 `dashboard.html`). 이 파일들의 일은 철회된 주장을 **철회되었다고 기록하기
  위해 인용하는 것**이고, 심사위원은 이 파일들을 읽지 않습니다.
- **검사기** `scripts/check_withdrawn_claims.py`, `make check-withdrawn-claims`,
  그리고 `make verify` 안에 들어가 있으므로 모든 랩과 모든 푸시(GitHub Actions 포함)에서
  돕니다.
- **면제 방법은 하나**: 그 줄 또는 바로 윗줄의 `<!-- forbidden-ok: <토큰> -->`.
  `scripts/check_forbidden.py` 와 **같은** 프래그마이고 토큰은 주장별로 다릅니다.
  자기만의 뒷문을 가진 게이트는 사람들이 우회하는 법을 배우는 게이트입니다.

## 3. 결과 (재현 가능)

```
$ python scripts/check_withdrawn_claims.py --coverage
claims             : 3
spellings          : 15
tracked in scope   : 988 files ('.md', '.html')
gated              : 915
record class       : 73 files, 12 declared paths
$ python scripts/check_withdrawn_claims.py
=== check_withdrawn_claims: PASSED === 3 claims over 915 gated files
```

**11 → 915.** 이것이 이 행이 산 유일한 숫자이고,
`tests/test_withdrawn_claims_registry.py::test_the_coverage_this_row_bought_is_recorded_and_re_derived`
가 다시 계산합니다.

레지스트리를 처음 전체 트리에 돌렸을 때 **가드 목록 밖에서 11건**이 나왔고, 모두
두 파일에 있었습니다: `docs/SESSION19_REPORT.md` (10건)과
`docs/finals_screen_v2.md` (1건). 둘 다 이미 산문으로는 철회 주석을 달고 있었으나
기계가 읽을 수 있는 면제는 없었습니다. 산문은 한 글자도 고치지 않고 그 줄들에
프래그마를 붙였습니다.

## 4. 이 게이트가 **하지 않는** 것 — 부스에서 근거로 들지 마십시오

1. **의미를 읽지 않습니다. 철자를 읽습니다.** 복사-붙여넣기 래칫입니다.
2. **재작성(rewording)에 대한 민감도는 조금도 개선되지 않았습니다.** 패턴이 같은
   패턴이기 때문이며, 그것이 의도입니다 (`test_the_registry_has_not_drifted_…`).
   외부에서 측정된 숫자는 그대로입니다 — **패턴 작성자가 쓰지 않은** 세 세트:
   크리틱 #9 의 스무 문장에 `primacy_violations` **0/20**, `priority_violations`
   **2/20** (BACKLOG WFG-062, 크리틱 #9 F47); 20260904T0855Z 랩 검토자의 스무 문장에
   `primacy_violations` **1/20**(19건 통과), 화면의 부정 규칙 **8/20**
   (`docs/auto/reports/2026-09-04T0855Z-dev.md`); WFG-070 검토자의 세트에 영어 구조
   규칙 **9/18**. **이 행은 그 숫자들을 바꾸지 않았고, 새 숫자를 주장하지도
   않습니다.**
3. **구조 규칙 두 개는 흡수하지 않았습니다.** `priority_violations` 와
   `english_ordering_violations` 는 줄바꿈된 마크다운 블록에서 문장을 언어별로
   재구성하므로 레지스트리 한 줄로 표현되지 않습니다. 흡수는 다음 행입니다.
4. **범위를 넓히면 거짓 양성이 생깁니다. 현재 트리에서 측정된 값은 915개 중 1건.**
   `docs/finals_screen_v2.md:75` 의 「사람 신고를 일차로 **끌어올리지 않습니다**」는 <!-- forbidden-ok: 신고 일차 -->
   정직한 부정문인데 `신고 일차` 철자에 걸립니다. 구조 규칙은 부정을 읽고 통과시키지만
   철자 규칙은 읽지 못합니다. 프래그마로 면제했고, 그것이 우회가 아니라 설계된
   방법입니다.
5. **커밋된 아티팩트가 걸리면 이 루프는 고칠 수 없습니다.** `outputs/dispatch*/` 의
   652개 생성 파일이 범위 안에 있고 CHARTER §3 규칙 2 는 커밋된 아티팩트의 수정을
   금지합니다. 그런 일이 생기면 그것은 NEEDS_HUMAN 항목이지 편집이 아닙니다.
   (오늘은 전부 깨끗합니다.)
6. **기록 클래스가 조용히 자라면 이 게이트는 조용히 작아집니다.** 그래서 **선언된
   경로 12개**와 그 중 **단일 파일 10개**가 테스트에 못 박혀 있고, 늘리려면 같은
   커밋에서 이 문서를 고쳐야 합니다. `docs/auto/reports/` 와 `docs/auto/archive/` 는
   설계상 매 랩 자라므로 **파일 수는 고정하지 않습니다** — 이 테스트의 첫 판은 73 을
   못 박았고, 그랬다면 그것을 실어 나르는 푸시에서 바로 빨간불이 됐을 것입니다.

## 5. 지금 등록된 주장

| id | 주장 | 무엇이 철회했나 | 철자 |
|---|---|---|---|
| WC-001 | 위성 트리거가 사람의 신고보다 늦었다(또는 빨랐다) | WFG-053 / NH-019 — 기준 시각은 매니페스트의 기록된 발생일시이고 이 저장소에 신고접수시각은 없습니다 | 6 | <!-- forbidden-ok: 신고보다 -->
| WC-002 | 사람 신고를 트리거의 일차 소스로 둔다 | WFG-063 / WFG-069 — 크기 바닥은 위성을 **배제**할 뿐 사람을 **옹립**하지 않습니다 | 6 | <!-- forbidden-ok: 신고 일차 -->
| WC-003 | 같은 두 주장, 영어로 | WFG-070 — 크리틱 #10 이 한국어 목록이 읽지 않는 세 연구 문서에서 살아 있는 것을 찾았습니다 | 3 |

## 6. 주장을 하나 더 철회하게 되면

`docs/auto/withdrawn_claims.json` 의 `claims` 에 `WC-###` 를 추가하고, 철자마다
`pattern` · `token` · `why` 를 씁니다. 그리고
`tests/test_withdrawn_claims_registry.py::_probe_sentence` 에 **저장소가 실제로
썼다가 철회한 문장**을 넣습니다 — 정규식에서 거꾸로 만들어낸 문장이 아니라. 목록은
편집하지 않습니다. 그것이 이 행의 전부입니다.
