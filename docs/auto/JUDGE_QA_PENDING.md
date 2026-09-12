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

## Merged

*(nothing yet)*
