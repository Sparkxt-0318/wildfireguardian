# Staff headline = resident time (Iris E) — UNVERIFIED

Approved by the orchestrator after Iris's review of the P-PROTO gap fix. Before this change, every staff surface took
`latestSafeDepartureS` as the deadline. In a gap case (a requested departure with no checked route between the first
departure and a later checked one), that is LATER than the contiguous time residents get from the message kit and the
public card. It is the staff time that gets relayed by phone.

## Change
One function, `headlineDepartureS` / `deadlineHeadline` (planner/src/domain/plan.ts), now drives every staff surface.
The headline time is the contiguous time, kept only when the sweep bears it out. A sweep that contradicts it fails
closed; an empty sweep carries no detail and is not checked. Kinds:
- `deadline`: has the headline time. `laterWindowS` is set when the latest checked departure comes after a gap.
- `partial` (new): checked somewhere, but not at the first departure time computed. No headline time.
- `no_route` / `unresolved`: unchanged.

Surfaces:
- **Right panel headline:** "출발 마감 T". The sub now says that every departure time computed up to T has a checked
  route. In a gap case, a grey line below reads "그 뒤 점검된 경로가 없는 구간이 있고, L 출발에 다시 점검된 경로가
  있습니다 — 출발 마감이 아닙니다". A partial case shows "출발 마감 없음 — 첫 계산 출발 시각에 점검된 경로가 없습니다"
  in grey, never green, plus the later-window line.
- **Origin list:** the chip shows T, or "출발 마감 없음" (grey) for partial. A "빈 구간 뒤 경로" mark carries the full
  line as its tooltip.
- **Timeline and time slider:** the deadline tick sits at T. A separate grey "later window" tick marks L.
- **Default selected departure** when an origin opens: T. For partial, the first departure computed.
- **A4 plan sheet:**
  - deadline cell main = T; sub = "그 뒤 빈 구간 다음에 다시 확인된 출발이 있음 — 마감 아님 (화면 참고)".
  - L is NOT printed: paper outlives the result. This matches Iris's provenance rule; her answer on this surface is
    pending.
  - Partial: "—" and "출발 마감 없음".
  - The alternative-plan caveat is reworded the same way.
  - The sheet row's shelter, arrival and route are those checked at T, not at L. Partial: none.
- **CSV:**
  - "출발 마감 KST" = T, or "없음" for partial.
  - The "연속 확인 기준" column becomes "빈 구간 뒤 점검된 출발 KST (마감 아님) / Later checked departure after a gap
    (KST, not the deadline)" = L.
  - Shelter and arrival belong to L's route, so they are left empty in a gap or partial row (fail closed), with a note.
- **Explanation block (panel and sheet):** receives T. An explanation recorded for L does not match and is not shown;
  `matchesShown` already fails closed.
- **Urgency order:** unchanged. It already sorted by the contiguous time.

## Measured
Property test (`tests/planner/staffheadline.test.ts`): over 531 real and 600 synthetic origins, the staff headline
time equals the kit's leave-by time, and the public card shows a time exactly when they do.

Cases whose staff time changes:

| | changed | of which gap | of which partial |
|---|---|---|---|
| real | **0** | 0 | 0 |
| synthetic | **131** | 53 | 78 |

The 78 partial cases are new information: before, the staff panel gave them the latest checked time, while residents
got none.

Existing tests changed because the requirement changed (assertion for assertion; none removed):
- `plan.test.ts`, `cache.test.ts`: headline = contiguous time, plus later window / partial;
- `features.plansheet.test.ts`: deadline cell and caveat;
- `features.exports.test.ts`: CSV header and the gap row.

Suite 25 files / 405 tests; build:static OK.

## Not done / open
- Iris has not yet answered whether L may appear on the A4 sheet. It is kept off.
- The CSV gap row has no shelter or arrival for T's route, because the export type does not carry per-departure
  attempts. 0 real rows are affected.
- Comprehension untested: whether staff read "not the deadline" as intended. Hypothesis (Iris): "later" may be read
  as permission.
