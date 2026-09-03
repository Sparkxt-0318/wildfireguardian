# SSOT 감사 — 한 수량, 한 자리 (2026-09-03, WFG-004)

**목적.** 같은 수량이 서로 다른 값으로 여러 문서에 앉아 있는 곳을 찾아, 각
수량에 **집(정본 위치)** 을 하나만 남기고 나머지는 그 집을 가리키게 만듭니다.
값을 지우지 않습니다 (CHARTER §3.7). 폐기된 값은 주석으로 남깁니다.

**방법.** `scripts/check_number_collisions.py --report`, `make check-forbidden`,
백로그 WFG-004 이 지목한 네 지점, 그리고 그 과정에서 발견된 두 지점.
게이트가 **구조적으로 볼 수 없는** 실패 유형을 하나 찾았고 (§1), 그것을
`tests/test_rescue_lineage_ssot.py` 로 막았습니다.

> ⚠ **이 문서가 보여주지 않는 것** 은 §5 에 있습니다. 이것은 "저장소의 모든
> 수량이 검증되었다" 는 문서가 **아닙니다**.

---

## §1 구조 지연 행 `6 → 66` vs `6 → 34` — 오타가 아니라 계보 혼입

**두 계보 모두 실재하는 산출물입니다.**

| 계보 | 산출물 | N | 4분할 | 지연 0/15/30/45/60분 |
|---|---|---|---|---|
| **439계열 (정본, real-OSM)** | `data/processed/rescue_verify.json` | 439 | 262 / 10 / 143 / 24 | **[6, 11, 24, 51, 66]** |
| **452계열 (superseded, pre-flip 합성)** | `data/processed/rescue_baseline_synthetic/rescue_verify.json` | 452 | 154 / 34 / 244 / 20 | **[6, 15, 20, 25, 34]** |

**정본의 집:** 레지스트리 키 `rescue_unreachable_delay_row_cutoff_0p7`.

**발견.** `README.md:731` 이 452계열의 `6 → 34` 를, 나머지가 모두 439계열인
문단 안에 적고 있었습니다. 같은 문단의 "the same 143 origins" 와
"6.12 → 1.71" 은 `data/processed/rescue_routing.json` (439계열, n = 143) 에서
옵니다. 즉 한 문단에 두 계보가 섞여 있었습니다.

**잘못 진단됐던 경로.** 이 지점은 세 번 기록되면서 사실이 아닌 쪽으로 굳었습니다.

1. `docs/auto/research/sweeps_2026-09-03/R7_rubric_gap.md` 는 **옳은 질문**
   ("which artifact is 34?") 을 적고 UNRESOLVED 로 두었습니다.
2. `docs/auto/research/RESEARCH_BRIEF_2026-09-03.md` 가 그 질문을
   "a typo, unregistered" 로 평평하게 만들었습니다.
3. `docs/submission_reconciliation.md` 행 8 이 거기서 한 걸음 더 나가
   **「34는 어느 산출물에도 없습니다」** 라고 단정하고, 학생이 부스에서
   **「오타입니다」** 라고 말하도록 대사까지 써 두었습니다.

세 번째가 실제 위험이었습니다. 심사위원이 `grep -rn "34" data/processed/` 한
번으로 반증할 수 있는 문장을, 저장소의 **계보 정직성을 담당하는 문서** 가
들고 있었습니다. 네 곳 모두 2026-09-03에 정정했습니다.

**정직하게 적어 둘 점:** `docs/rescue_routing.md` 와
`docs/REPORT_ROUND2_P1.md` 는 **처음부터 옳았습니다.** 전자는 문서 머리에
"DO NOT CITE / 제출·인용 금지 — SUPERSEDED" 배너와 `N = 452` 를 명시하고,
후자는 `6 → 34` 와 `6 → 66` 을 "synthetic lattice" 대 "real roads" 로
나란히 적습니다. 규칙을 깬 곳은 정확히 두 곳(README, 개정대조표)이었습니다.

**게이트가 왜 못 봤는가.** `check_number_collisions.py` 는 *등록된* 수량이
자기 키의 anchor 단어 근처에서 **다른 값** 으로 나타날 때 발화합니다. 여기서는
두 값이 **서로 다른 계보에서 각각 옳은** 값이므로 모순이 없고, 게이트는
`README.md:731` 위에서 계속 초록이었습니다 (이 랩 시작 시점에도
`UNMARKED collisions: 0`, exit 0). 그래서 새 테스트는 **값 게이트가 아니라
계보 게이트** 입니다: 452계열 값이 문서 전체 배너도 없고 옆에 계보 표시도 없이
등장하면 실패합니다. 이 테스트는 켜자마자 위 1·2번을 스스로 찾아냈습니다.

---

## §2 의성·안동 : 영덕 future-aware-only 비 — 2.7×, 6.7× 아님

`docs/HANDOFF_ROUND3.md` 두 곳(§1.3 및 §2 목록)이 "nearly **seven times**
Yeongdeok's" 라고 적었습니다.

| 계산 | 값 | 상태 |
|---|---|---|
| 24.73 % / **3.70 %** | 6.7× | **폐기.** 3.70 % 는 되돌려진 실행의 영덕 지분 |
| 24.73 % / **9.17 %** | **2.7×** | 정본 (`mr_fa_only_share_pct` 계열) |

두 번째 occurrence 는 **바로 두 줄 위** 에서 "FA-only **9.17** / 24.73 /
0.76 %" 라고 정본 지분을 나열하고 있었으므로, 같은 문단 안에서 스스로
모순이었습니다. 두 곳 모두 2.7× 로 정정하고 6.7× 의 유래를 주석으로 남겼습니다.
방향 결론("quasi-static 한계는 실재했고 이익을 과소평가했다")은 **변하지
않습니다** — 2.7배도 같은 방향입니다.

---

## §3 pooled AUC 와 mean-of-folds — 어느 것이 1차인가

**모순처럼 보였던 것:**

| 문서 | 문장 |
|---|---|
| `docs/fold_sizes.md` §읽는 법 | "**Pooled AUC 가 1차 지표입니다.**" |
| `docs/NUMBERS.json` (2개 caveat) | "pooled AUC is the primary metric" |
| `docs/MODEL_CARD.md` | pooling "is **not** the generalization estimate" |

**해소:** 두 문장은 **다른 질문** 에 답합니다. 모순이 아닙니다.

- **pooled 0.905** (행 가중, 151,904행 1회씩) → 「증거 전체에 대한 **판별력**」.
  폴드 크기 왜곡이 없습니다. 대신 큰 폴드가 지배합니다 (의성·안동 54.47 %,
  영덕 32.6 % 의 행).
- **mean-of-folds 0.890** (폴드당 1표) → 「**처음 보는 화재** 로의 일반화」.
  대신 396행·양성 8셀의 gangneung_2023 (증거의 0.26 %) 이 값의 6분의 1을
  결정합니다.

**어느 쪽도 다른 쪽의 대체물이 아니고, 반드시 `docs/fold_sizes.md` 표와 함께
제시합니다.** 이 문장이 그 판단의 유일한 집이며, `fold_sizes.md` 와
`MODEL_CARD.md` 양쪽이 여기를 가리킵니다.

**함께 발견된 것: 1차 지표에 레지스트리 키가 없었습니다.** 세 문서가 pooled 를
1차라고 부르는데, pooled 0.905 는 등록된 적이 없었습니다 — README 산문과
**다른 키들의 caveat 문자열 안** 에만 존재했고, 정작 등록된 헤드라인은 1차가
아닌 mean-of-folds 0.890 이었습니다. 2026-09-03에
**`lofo_rowweighted_pooled_auc`** (arm `A_ssot`) 로 처음 등록했습니다.
같은 커밋된 산출물 `data/processed/spread_v2_lofo.json` 의 `pooled_auc` 를
읽을 뿐이고, **어떤 값도 수정하지 않았으며 헤드라인을 옮기지 않았습니다.**

> ⚠ **등록은 승격이 아닙니다.** 커밋된 헤드라인은 그대로 폴드평균 **0.890**
> 입니다. 서술의 앞에 어느 지표를 세울지는 **저자의 결정** 이며 루프의 것이
> 아닙니다 (CHARTER §6). 이 랩은 짝을 기록했을 뿐 고르지 않았습니다.

---

## §4 혼동되기 쉬운 짝 — 각 수량의 집

| 수량 | 정본의 집 | 혼동 상대 | 구분 |
|---|---|---|---|
| 구조 지연 행 (cutoff 0.7) | `rescue_unreachable_delay_row_cutoff_0p7` = [6, 11, 24, 51, 66] | 452계열 [6, 15, 20, 25, 34] | 계보 (real-OSM / pre-flip) |
| 구조 unreachable 기준값 | `rescue_unreachable_count` = 24 | 452계열의 20 | 같은 계보 차이 |
| LOFO 판별력 (행 가중) | `lofo_rowweighted_pooled_auc` = 0.905 | mean-of-folds 0.890 | 다른 질문 (§3) |
| LOFO 일반화 (폴드 1표) | `lofo_mean_of_folds_auc` = 0.890 | pooled 0.905 | 다른 질문 (§3) |
| HGB 폴드평균 | `mlbase_hgb_mean_of_folds_auc` = 0.894 ± 0.092 | `lofo_mean_of_folds_auc` 0.890 ± 0.107 | 다른 **계보** (정정 DEM), WFG-018 이 확정 |
| 영덕 FA-only 지분 | 9.17 % | 폐기된 3.70 % | 되돌려진 실행 |
| 의성·안동 : 영덕 비 | **2.7×** (§2) | 폐기된 6.7× | 분모가 폐기 지분 |
| 459계열 4분할 | 414 / 42 / 2 (n = 458) | 438/18/3, 440/17/3 | `docs/submission_reconciliation.md` |

`440 / 17 / 3`, `438 / 18 / 3`, `3.70 %`, `+1.2 %`, `44×`, `452`, `154`, `264`
는 `scripts/check_forbidden.py` 의 LABEL / LABEL_NEAR 규칙이 라벨 없는 등장을
막습니다. **폐기 값은 레지스트리에 등록하지 않습니다** (WFG-018 의 결정).

---

## §5 이 감사가 보여주지 않는 것

1. **전수 감사가 아닙니다.** WFG-004 가 지목한 네 지점과 그 과정에서 나온 두
   지점을 다뤘습니다. `docs/NUMBERS.json` 은 296개 항목을 담고 있고, 그중
   이 감사가 사람 눈으로 확인한 것은 §4 의 여덟 짝뿐입니다.
2. **§1 의 새 테스트는 한 수량만 지킵니다.** 구조 지연 행에만 적용됩니다.
   같은 실패 유형(다른 계보의 옳은 값을 잘못된 문단에 인용)이 다른 수량에
   존재하는지는 **확인되지 않았습니다.** 일반화된 게이트는 WFG-030
   (보고서 숫자 검사) 이 할 일이고, 아직 없습니다.
3. **`check_number_collisions.py` 가 초록이라는 사실은 산문이 옳다는 뜻이
   아닙니다.** §1 이 그 반례입니다. anchor 단어 3개 이상이 한 줄에 모여야
   발화하므로, 계보만 다른 값은 영원히 통과합니다.
4. **어떤 기본값도, 어떤 헤드라인도 움직이지 않았습니다.** 이 감사는 산문과
   레지스트리만 건드렸고, `data/processed/` 아래 산출물은 하나도 다시
   만들지 않았습니다.

---

## 이 랩이 바꾼 파일

| 파일 | 무엇 |
|---|---|
| `README.md` | §1 계보 혼입 정정 + 452계열 주석 |
| `docs/submission_reconciliation.md` | 행 8 과 30초 대사 8 — 거짓 단정 정정 |
| `docs/HANDOFF_ROUND3.md` | §2 두 곳 6.7× → 2.7× + 유래 주석 |
| `docs/fold_sizes.md` · `docs/MODEL_CARD.md` | §3 로 향하는 상호 주석 |
| `docs/NUMBERS.json` · `docs/arm_protocol.json` | `lofo_rowweighted_pooled_auc`, arm `A_ssot` |
| `docs/auto/research/RESEARCH_BRIEF_2026-09-03.md` · `sweeps_2026-09-03/R7_rubric_gap.md` | 오진 경로 주석 |
| `tests/test_rescue_lineage_ssot.py` | 계보 게이트 (6개 테스트) |
