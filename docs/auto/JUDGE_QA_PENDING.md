# Judge Q&A — cards waiting to be merged into the bank

**This file is a staging area, not the bank.** `docs/auto/JUDGE_QA.md` is one of
the seven `SOURCES` of the printed kit, and
`tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree`
re-hashes every source against the newest manifest. A lap that adds a card to the
bank without running `make printables` at a new stamp and re-pointing
`release/kcf-finals-2026/MANIFEST.json` turns the tree red. **NH-049 is the open
decision about how that should work** (option A: a staging file the next dev lap
merges — WFG-205) and it is unanswered, so this lap used the staging route the
row itself offered rather than deciding NH-049 by acting.

**How a card leaves this file.** A lap that is already rebuilding the kit for
another reason merges the card into `docs/auto/JUDGE_QA.md`, runs
`make printables`, re-points the manifest and the bundle, and deletes nothing
here — it moves the entry under `## Merged` with the commit that merged it.

⚠ **Nothing in this file is printed, and the student does not study from it.**
Until a card is merged, the booth answer to the question it covers is whatever
the bank already says.

---

## Pending

### P-001 · WFG-264 · 「이 문장은 프로그램이 실제로 확인한 것입니까?」 <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. Same false-positive class as ba437f5, where the gate read a lap stamp as a camera count. No figure is asserted on this line. -->

*Filed 2026-09-12 by the WFG-264 lap. Raised by critic #71's judge drill, which <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. Same false-positive class as ba437f5, where the gate read a lap stamp as a camera count. No figure is asserted on this line. -->
could answer neither this nor P-002 from any file in the repository.*

**Q (드릴에서 나온 형태).** 이 A4 출동 지시서가 지금 심사위원 손에 있습니다.
「차량 도달 불가」 칸의 사유 문장은 프로그램이 실제로 확인한 것입니까?

**A (draft, tier T1 — 물으면 답한다, 먼저 꺼내지 않는다).**

> 지금 인쇄되는 문장은 「어느 거점에서도 생존 인지 차량 진입 경로가 확인되지
> 않음」입니다. 그게 코드가 실제로 확인한 전부입니다. 판정 조건은 「걸어서 나갈
> 수 없고, **모든 거점에 대해** 생존 인지 차량 경로가 집에 닿지 못했거나 화재를
> 통과하는 것으로 표시됨」이고, 그 이상은 아무것도 말하지 않습니다.
>
> 예전에는 「예산 내 차량 진입로가 화재로 차단됨(우회 포함)」이라고 적혀
> 있었습니다. 그건 세 가지를 주장하는 문장입니다 — 불이 원인이다, 예산을 다
> 썼다, 우회를 시도했다. **셋 다 코드가 보장하지 않습니다.** 탐색이 실패하는
> 지점이 세 군데인데 시트는 한 문장만 갖고 있었습니다. 거점 자체가 이미 통행
> 불가 기준 위에 있으면 탐색을 **시작도 하지 않고** 돌아오고(우회는 시도된 적이
> 없습니다), 탐색이 다 돌고도 못 닿는 경우는 예산 초과·화재·**도로가 아예 없는
> 경우**가 한 덩어리로 섞여 있습니다. 불이 전혀 없는 지도에서도 이 판정이
> 나오는 걸 시험으로 재현해 뒀습니다.
>
> 근거 문서는 `docs/routing_limitations.md` §7입니다. 판정 자체가 틀렸다는
> 뜻은 아닙니다 — 판정은 더 보수적인 쪽이고, 구조 차량을 불 속으로 보내지 않는
> 방향으로 틀리는 건 맞는 방향입니다. 고친 건 **문장**입니다.

**Source of every claim above:** `docs/routing_limitations.md` §7,
`tests/test_vehicle_unreachable_split.py`.

⚠ **No count from that section goes on this card**, and none is in the draft
above. NH-032, NH-034 and NH-052 are open on margin values, and §7's counts are
about the artifact's context field rather than about the class.

### P-002 · WFG-264 · 「커밋된 시트에는 옛 문장이 그대로입니다」 <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. Same false-positive class as ba437f5, where the gate read a lap stamp as a camera count. No figure is asserted on this line. -->

*Filed 2026-09-12 by the WFG-264 lap, the second half of the same drill.* <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. Same false-positive class as ba437f5, where the gate read a lap stamp as a camera count. No figure is asserted on this line. -->

**Q.** 보행 쪽은 오늘 고쳤다고 하셨는데, 저장소에 커밋된 시트에는 옛 문장이
그대로 있습니다.

**A (draft, tier T1).**

> 맞습니다, 그리고 일부러 그렇게 뒀습니다. `outputs/` 아래 실행 디렉터리는
> **그때 생성된 기록**입니다. 그 시트들은 2026-08-01에 만들어졌고, 그날 프로그램이
> 실제로 출력한 문장을 그대로 갖고 있습니다. 나중에 문장을 고쳤다고 해서 예전
> 기록을 손보면, 그 시트는 더 이상 무엇이 언제 출력됐는지에 대한 기록이 아니게
> 됩니다. 새로 돌린 실행부터 새 문장이 나갑니다.
>
> 어느 쪽이 지금 문장이고 어느 쪽이 지난 문장인지는 `docs/live_pipeline.md`의
> 표 두 개에 적혀 있고, 표의 칸이 코드의 문자열과 같은지를 확인하는 시험이
> 붙어 있습니다.

**Source:** `docs/live_pipeline.md` (the live table and the record table below
it), `tests/test_live_pipeline_doc_matches_code.py`.

---

### P-003 · WFG-266 · 「이 그림의 범례가 본문 설명과 다릅니다」
*Filed 2026-09-12 by critic #72's judge drill. ⚠⚠ **UPDATED 2026-09-12T0617Z BY THE
WFG-266 DEV LAP, WHICH CLOSED THE ROW AND SO FALSIFIED THIS CARD'S OWN DRAFT
ANSWER.** 카드가 근거로 삼을 문서가 이제 있습니다: `docs/figure_legend_claims.md`.
아래 첫 초안은 기록으로 남기고(CHARTER §3.7), 말할 답은 그 아래 둘째 초안입니다.*

**Q (드릴에서 나온 형태).** 본문에는 「2 reaching no refuge」라고 쓰셨는데, 바로 그
그림의 범례는 「no safe walking route」라고 적혀 있습니다. 어느 쪽이 맞습니까?

**A (draft, tier T1 - 물으면 답한다).**

> 지적하신 그대로였고, 고쳤습니다. 코드가 세우는 조건은 「불을 모르는 경로는
> 예측 위험을 지나서 대피소에 닿았고, 예보를 아는 탐색은 닿지 못했다」입니다.
> 「안전한 보행 경로가 없다」는 그보다 강한 주장이라, 세 범례를 모두 「no safe
> walking route **found**」로 바꿨습니다. 커밋된 그림은 다시 그리지 않고 새 파일
> 이름으로 만들었습니다(`F3b_regions.png`, `F8b_routing_map.png`, 앞선 랩의
> `F5b_decision_shift.png`). 방법과 한계는 `docs/figure_legend_claims.md`에
> 있습니다. ⚠ 이 고침이 「안전한 경로가 있다」는 뜻은 아닙니다. 두 탐색이 무엇을
> 돌려줬는지만 말할 수 있습니다.

**Source:** `docs/figure_legend_claims.md`; `paper/make_figures.py` F3b·F5b·F8b
범례; `tests/test_figure_legend_claims.py` (돌연변이 다섯 개로 채점).
⚠ **[2026-09-12T0920Z 갱신 · 이 경고는 더 이상 참이 아닙니다]** `README.md`가
들고 있던 더 강한 표현(「no safe walking route **at all**」)은 <!-- forbidden-ok: wc021-no-safe-walking-route-at-all -->
**WFG-270 (a)(b)로 고쳐졌습니다**: `:25`는 「**2** reach no refuge under that
policy」로, `:798`은 「**2** reach no refuge under it」로 바뀌었고, 철자는
`docs/auto/withdrawn_claims.json`에 **`WC-021`**로 등록되어 이제 추적되는 모든
`.md`·`.html`이 검사를 받습니다. 심사위원이 README를 들고 물으면, 고쳤고
등록까지 했다고 그대로 말합니다. 위 문단은 지우지 않고 날짜를 달아 둡니다
(CHARTER §3.7).

**[기록 · 2026-09-12 · 오늘의 답이 아닙니다]** 최초 초안은 「범례가 아직 옛
표현입니다 ... F8과 F3 범례는 아직입니다」였고, 출처로 `paper/make_figures.py:689`
(F8 범례), `:134` (F3 범례), `:244` (F5b)를 들었습니다. WFG-266이 닫히면서 세 줄
모두 옮겨졌으므로 이 초안은 더 이상 참이 아닙니다.

---

### P-004 · WFG-267 · 「이 세 장 중 어느 것이 옛 문장입니까?」

*Filed 2026-09-12 by critic #72's judge drill, as the residual of P-002. P-002는
「왜 커밋된 시트가 옛 문장을 갖고 있는가」에 잘 답하지만, 부스에서 손에 든 세 장
중 **어느 장**이 그것인지는 어떤 파일도 말하지 않습니다.*

**Q.** 지금 주신 출동 지시서 묶음에서, 「차량 도달 불가」 사유가 서로 다르게 적힌
장이 섞여 있습니다. 어느 것이 지금 기준입니까?

**A (draft, tier T1).**

> 다시 뽑은 장이 지금 기준이고, 미리 만들어 둔 PDF가 2026-08-01 기록입니다.
> 이 디렉터리에서 미리 만들어 둔 장은 가장 큰 세 군집뿐이고, 그중 옛 사유가 찍힌
> 것은 `02-천전공원-일대` 한 장입니다. ⚠ 다만 저장소 전체로 보면 그 장 말고도
> `outputs/dispatch_full/20260801T183522Z/03-영덕해맞이공원-일대` 의 두 장이 더
> 있습니다. 경로까지 `outputs/dispatch/README.md` 에 적어 두었고, 테스트가 그
> 목록을 트리와 맞춰 봅니다. 가장 안전한 방법은 인쇄할 장을 전부 다시 뽑는
> 것이고, 그러면 섞이지 않습니다.

**Source (오늘 기준):** `outputs/dispatch/README.md` §「Which committed page carries
the SUPERSEDED …」(어느 장인가), [`docs/dispatch_sheet_staleness.md`](../dispatch_sheet_staleness.md)
(방법과 한계), `docs/live_pipeline.md` §「Responder-side」(무엇이 대체되었는지),
`docs/routing_limitations.md` §7(왜), 게이트 `tests/test_dispatch_sheet_staleness.py`.

⚠ **[2026-09-12T0920Z 갱신]** 위 ⚠ 경고는 「`02-천전공원-일대` 한 장이라는 말이
어떤 커밋된 문서에도 없다」였고, **WFG-267 (i)이 닫히면서 해소되었습니다** — 이제
`outputs/dispatch/README.md` 에 있습니다. ⚠⚠ **같은 랩이 그 말 자체도 좁혔습니다.**
「한 장」은 `outputs/dispatch/20260801T163042Z/` 안에서만 참입니다. 트리 전체에서는
커밋된 출동 지시서 PDF가 **38장**, run 디렉터리가 **12개**이고, 옛 사유를 든 장은
**3장**입니다(각각 `dss_committed_dispatch_pdfs`, `dss_run_dirs_with_a_committed_pdf`,
`dss_stale_committed_pdfs` 로 등록되어 있습니다). ⚠ **등급을 매긴 1차 근거는 PDF 본문이 아니라 그것이 렌더링되어 나온 형제
HTML입니다** — 심사위원이 캐물으면 그 추론을 먼저 말씀하십시오. ⚠ 다만 2026-09-12
랩이 `scripts/probe_dispatch_pdf_fonts.py` 로 **PDF 바이트 자체도** 확인했습니다:
심어진 한글 폰트 서브셋을 `zlib` 로 풀어 보면 그 세 장만 옛 사유를 철자할 수 있고
새 사유는 한 장도 철자하지 못합니다. 두 경로가 같은 답입니다. 방법과 그 한계는
`docs/dispatch_sheet_staleness.md` §4.

---
### P-006 · WFG-277 (a) · 「약한 상대라면서 왜 20개가 못 넘습니까?」

*Filed 2026-09-12 by critic #75's judge drill, as **critic #75's one `fix-before-next-row`
item**. `docs/auto/JUDGE_QA.md` Q36 은 2026-09-12 에 회전 널의 수치를 받았지만, 그 수치를
바로 아래의 「구조상 약한 상대」 문장과 이어 주는 절은 받지 못했습니다. 그 절은 같은 날
`docs/disc_null.md:238-241` 에 쓰였고, 그 파일은 인쇄 묶음의 일곱 원본에 들어 있지
않습니다. Q36 은 들어 있습니다(source 3 of 7).*

**Q.** 방금 원판이 「구조상 약한 상대」라고 하셨는데, 같은 카드에서 돌린 23개 중
20개가 그 원판보다 못했다고 하셨습니다. 약한 상대인데 왜 못 넘습니까?

**A (draft, tier T0 보조절).**

> 두 말이 다 맞고, 기준이 다릅니다. 원판이 약한 상대라는 것은 **제대로 놓인**
> 예측 핵에 대해서입니다. 같은 핵을 엉뚱한 각도로 돌려 놓으면 원판이 오히려
> **더 나은** 상대가 됩니다. 23개 중 20개가 그렇습니다. 그래서 저희가 말할 수
> 있는 것은 「불규칙한 모양이라서 점수가 나왔다」가 아니라 「그 모양을 **그 각도로**
> 놓아서 나왔다」이고, 원판을 넘은 것은 여전히 **필요조건이지 충분조건이 아닙니다**.

**병합 지시(한 문장만 더합니다).** Q36 의 「⚠ **원판은 바닥이고 경쟁 상대가
아닙니다** … **필요조건이지 충분조건이 아닙니다**.」 문장 **뒤에** 다음 한 절을
덧붙이십시오. 기존 문장은 지우지 않습니다:

> ⚠ **다만 「약한 상대」는 제대로 놓인 핵에 대해서만 그렇습니다** — 같은 핵을 돌려
> 놓으면 원판은 23개 중 **20개보다 나은** 상대이고, 그래서 원판을 넘은 것이 모양의
> 불규칙함이 아니라 **각도**를 가리킵니다(`docs/disc_null.md` §5.1, §5b).

**Source (오늘 기준):** [`docs/disc_null.md`](../disc_null.md) §5.1 항목 1 의
2026-09-12 주석과 §5b, [`docs/rotation_null.md`](../rotation_null.md) §3,
레지스트리 키 `rn_yeongdeok_rotations_beating_the_disc` **3** ·
`rn_yeongdeok_rotations_not_beating_the_disc` **20** ·
`rn_yeongdeok_bare_worst_over_disc` **0.3311**. <!-- collision-ok: 0.3311 — this is `rn_yeongdeok_bare_worst_over_disc`, the RATIO of the WORST rotation's seed-removed IoU to the disc's (unit x, 0.0387 over 0.1169), and it is not an IoU. The gate's anchor set (bare, disc, yeongdeok) matches it against the eleven `*_bare_disc_iou` keys (0.1169, 0.0975, 0.1225) and against `rn_yeongdeok_bare_true_over_disc` (2.2044, the ratio for the TRUE orientation rather than the worst). Four different quantities; none of them is stale and no value here is superseded. -->


⚠ **병합하는 랩에게.** `docs/auto/JUDGE_QA.md` 를 고치면 `make printables` 를 새
스탬프로 돌리고 `release/kcf-finals-2026/MANIFEST.json` 을 다시 가리켜야 합니다
(NH-049). 이 파일(`JUDGE_QA_PENDING.md`)은 일곱 원본이 아니므로 여기에 초안을
두는 것은 인쇄 비용이 없습니다. ⚠ `WC-018` 은 그대로입니다 — 이 절은 「모양」을
모델이 이긴 축으로 되돌리지 않습니다. 「그 모양을 그 각도로」이지 「모양」이
아닙니다. ⚠ `docs/disc_null.md` §4 의 무게중심 결론과 「방향은 아닙니다」는
건드리지 마십시오.

---


## Merged

### P-005 · WFG-267 (ii) · merged into `docs/auto/JUDGE_QA.md` Q39 on 2026-09-12 by the WFG-256 dev lap

*Merged as critic #74's one `fix-before-next-row` item, with the correction that lap
measured. The draft below read 「미리 만들어 둔 장은 … 사유가 옛 문장이고」, which reads as all
three sheets; it is **one of the three** (`02-천전공원-일대`), and the other two stale committed
sheets are under `outputs/dispatch_full/20260801T183522Z/03-영덕해맞이공원-일대/`, a directory
Q39 never mentions. The merged paragraph says 「세 장 중 한 장」, points at that other directory,
and keeps the instruction — regenerate all 33, hand over nothing pre-built — exactly as drafted,
because that instruction is right for a reason independent of which sheet is stale. The printer
caveat the draft dropped (`WFG-007` 의 사람 몫, NH-014) was kept, and Q39's ❌ lines and its
`<!-- forbidden-ok: wc006-dispatch-committed-pdfs -->` pragma were left alone. `make printables`
ran at a new stamp and `release/kcf-finals-2026/MANIFEST.json` was re-pointed in the same commit.
The draft is kept verbatim below as the record (CHARTER §3.7); it is no longer the instruction.*


*Filed 2026-09-12T0920Z by the dev lap that claimed WFG-267. `docs/auto/JUDGE_QA.md`
는 NH-049 가 열려 있는 동안 직접 고치지 않습니다(고치면 `make printables` 를 새
스탬프로 다시 돌리고 `MANIFEST.json` 을 다시 가리켜야 합니다). 이 파일은 인쇄물
일곱 원본에 들어 있지 않으므로 초안은 여기에 둡니다.*

**무엇이 문제인가.** 두 파일이 서로 다른 인쇄 지시를 줍니다.

| 파일 | 지시 | 결과 |
|---|---|---|
| `docs/auto/JUDGE_QA.md` Q39 | 미리 만들어 둔 세 장 + 나머지는 다시 생성해 인쇄 | 옛 문장 3장과 새 문장 30장이 **한 묶음에 섞입니다** |
| `outputs/dispatch/README.md` | `python scripts/generate_dispatch_outputs.py` 로 전부 다시 생성 | 33장이 한 문장으로 통일됩니다 |

학생이 공부하는 카드가 앞쪽이고, 섞인 묶음을 만드는 쪽도 앞쪽입니다.

**제안 (Q39 의 해당 문단만 교체, T1).**

> **이 한 권에 없는 것은 마을 A4 출동 지시서뿐입니다.** `outputs/dispatch/20260801T163042Z/`
> 에 클러스터 33개가 있고 HTML · SMS 초안 · 방송 문안은 33개 모두 커밋돼 있지만,
> `dispatch_a4.pdf` 는 가장 큰 세 군집만 미리 만들어져 있습니다(33장이면 6.7 MB 라서).
> **인쇄할 때는 세 장을 그대로 쓰지 말고 33장을 전부 다시 만드십시오** —
> `python scripts/generate_dispatch_outputs.py`. 미리 만들어 둔 장은 2026-08-01
> 기록이라 「차량 도달 불가」 사유가 옛 문장이고, 다시 만든 장은 WFG-264 <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. No figure is asserted on this line. --> 로 고친
> 문장을 찍습니다. **섞으면 심사위원이 한 묶음에서 한 조건에 두 문장을 봅니다.**
> 어느 장이 옛 것인지는 `outputs/dispatch/README.md` 에 경로까지 있고,
> `tests/test_dispatch_sheet_staleness.py` 가 그 목록을 트리와 맞춰 봅니다.

**이미 섞인 묶음을 들고 물으시면:** 「그 장은 2026-08-01 실행의 기록이고, 저희가
기록을 고쳐 쓰지 않기 때문에 그대로 있습니다. 문장을 고친 이유는
`docs/routing_limitations.md` §7 에 있습니다.」

⚠ **Q39 의 ❌ 줄과 `<!-- forbidden-ok: wc006-dispatch-committed-pdfs -->` 는 그대로
둡니다** — WC-006 이 가리키는 것은 여전히 살아 있는 오답입니다.

**Source:** `outputs/dispatch/README.md`,
[`docs/dispatch_sheet_staleness.md`](../dispatch_sheet_staleness.md),
`scripts/generate_dispatch_outputs.py`, 게이트 `tests/test_dispatch_sheet_staleness.py`.
