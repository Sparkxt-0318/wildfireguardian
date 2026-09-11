# Critic #70, 2026-09-11T2300Z, reviewed `d291364`

*The next dev lap clears the `fix-before-next-row` item below before it claims a row
(CHARTER §11). Everything else here is a backlog row or a NEEDS_HUMAN update and waits
its turn. This file is rewritten by every critic lap; nothing in it survives to critic #71
unless #71 re-measures it.*

---

## Gate state, measured in this lap's own process

- `gates.py --mode full` exits **0** at `d291364` on its FIRST run in this sandbox:
  **2181 passed, 65 skipped, 3 xfailed**, pytest 490.3 s. `baseline-verify` is the known
  WARN (NH-029, CHARTER §3d).
- `--assert-head` exits 0 at `d291364`. `--assert-reported --base` exits 0 at every push
  boundary in the window: `8952a5b`, `b5987b7`, `031214b`, `e0a3c2a`, `edd0ec0`, `8e05ec0`.
- Every report in the window records `Reviewed by:` (sixteen checked, including the bolded
  spellings, which a strict `^Reviewed by:` grep misses).
- Printed kit re-hashed here, not read from a report: `WFG_printables_20260911T2137Z.pdf`,
  **60 pages**, seven sources **7 of 7**. Release bundle `19 of 19`, and it names that kit.
  R7 and R9 hold. This note names those two objects and that measurement and **expires at
  critic #71** unless #71 re-hashes them.
- Clone is SHALLOW at **55** commits, measured here with
  `git rev-parse --is-shallow-repository` and `git rev-list --count HEAD`, and was
  deliberately **not** deepened. **No ancestry or reachability claim is written anywhere in
  this lap.** The cost, stated: `tests/test_timeline_roles.py:234` SKIPS rather than runs in
  a shallow clone, so a green critic gate does not certify it; GitHub at `fetch-depth: 0`
  does, and run 387 is green at `d291364`.

## CHARTER §4b: there WAS a red run in the window, and it is already repaired

**GitHub `auto-gates` run 386 concluded `failure` at `edd0ec0`** (22:49Z). Run **387** is
`success` at `d291364`, the current head. Reproduced here at `edd0ec0`: three failures in
`tests/test_finals_screen.py`, all of the form 「`6f866dd` is not a valid object name」.

**It does not become this lap's `fix-before-next-row` item, and the reasoning is written
out rather than assumed.** §4b sets finding #1 for a red run 「while the lap that pushed it
reported green」. This lap did not: its gate table said **RED** and **stale**, it superseded
its own report 27 minutes later, and it annotated the superseded body in place. Nothing was
concealed, no judge-facing surface was ever wrong, and there is no red gate left to fix.
What survives is a false sentence in the permanent record, and that is **WFG-263** (P1) plus
the measured instance appended to **NH-043**. See the root objection below for why the false
sentence matters more than the red run did.

---

## THE ONE `fix-before-next-row` ITEM

**The front door still carries the scope clause that WFG-259 falsified, eleven lines above
the addendum that falsifies it.** `README.md:328-341`, the Round-4 bullet.

Read the bullet in order:

| line | what it says |
|---|---|
| `:328-329` | 「⚠ **영덕에서는 이 상대를 아직 돌리지 않았습니다.**」 plus the 42 sentence |
| `:330-331` | 「⚠ **정정(2026-09-11, WFG-258): 위 두 문장은 이제 「이 절의 상대」, 곧 완충거리를 더한 쪽에만 해당합니다.**」 |
| `:338-339` | 「**완충거리를 폭까지 훑어 정식 상대로 세운** 쪽은 영덕에서 여전히 돌리지 않았습니다.」 |
| `:339-341` | 「⚠ **덧붙임(2026-09-11, WFG-259): 그 문서 5절 5항이 이미 적어 두었던 두 폭은 그날 실제로 돌려 확인했고 ...**」 |

`:330-331` is the sentence that **defines what the surviving un-run claim covers**, and it
defines it as 「완충거리를 더한 쪽」, the side with a buffer added. WFG-259 ran the side with
a buffer added, at two widths, on 영덕, on 2026-09-11, and `:339-341` says so. So the front
door states the falsified scope and the true one in the same bullet, eleven lines apart.

**Why WC-020 did not catch it.** The registered pattern is
`완충거리를\s*더한\s*\*{0,2}\s*상대는\s*영덕에서\s*(?:아직|여전히)\s*돌리지\s*않았`, the whole
subject-plus-region clause. `:338` matched it and was narrowed. `:330-331` is not that
clause: it is the **scope definition of a correction**, and it carries the falsified reading
without ever asserting it in the registered spelling. **A registered spelling is a
copy-paste ratchet, not a claim detector** (`docs/withdrawn_claims.md` §4), and this is that
limit biting on the front door.

**This is the second consecutive lap of the same class, and the third surface.** Critic #69's
item was a card whose note about itself went stale nine lines above an edit. Critic #70's is
a correction whose scope clause went stale eleven lines above its own addendum. DIRECTION's
「grep the file you just edited for the sentences that DESCRIBE it」 was written for exactly
this and did not fire, because the stale sentence is not a description of the edit, it is the
**definition of the term the edit uses**.

### What to do, precisely

Rewrite `:330-331`'s scope clause so it names the same thing `:338` names. One substitution,
no new sentence, nothing else in the bullet touched. Suggested wording, which the lap may
improve but must not widen:

> ⚠ **정정(2026-09-11, WFG-258 · 보강 WFG-259): 위 두 문장은 이제 「이 절의 상대」, 곧
> **완충거리를 폭까지 훑어 정식 상대로 세운** 쪽에만 해당합니다.**

Then delete the now-duplicated 「거기서 나온 수치는 이 README 에 옮겨 적지 않습니다.」 at
`:341` **or** the one at `:335-336`, not both, since the bullet says it twice after the
WFG-259 addendum landed. Keeping one is required; keeping two is the 논리적 구성 defect that
costs 제출 자료.

### Bars on this item, read them before editing

- ⚠ **Do NOT touch `README.md`'s opening paragraph about the 2025 fire** (CHARTER §3.5b),
  and do not touch the TL;DR lead's ordering or proportion (**NH-054**, frozen on ordering
  and proportion only, not on the truth of a parenthetical).
- ⚠ **Put NO `ppy_yeongdeok_*` count in the replacement**, and **do not add a pointer to any
  section that prints them**. `:335` already points at 4절 and `:337` at 5절; critic #69 put
  those **existing** pointers out of scope and that licensed leaving them, not adding a
  third. **NH-059** stays open with all four options reachable.
- ⚠ **Do not weaken the WFG-258 correction's substance**, do not restore 「영덕에서는 이
  상대를 아직 돌리지 않았습니다」 as a live claim, and do not touch `WC-019` or `WC-020` in
  `docs/auto/withdrawn_claims.json`.
- ⚠ **Do not edit `docs/auto/JUDGE_QA.md` for this.** Its Q19 correction block at
  `:1006-1013` points at 「바로 위 문단의 마지막 절」, a positional pointer, and is **correct**;
  its `:956` and `:1011` both carry the narrowed wording. Checked here. README is the only
  surface with this defect. Leaving JUDGE_QA alone also keeps the item inside minutes and
  off **NH-049**'s reprint requirement.
- **Grade it.** Before the fix, a grep for the falsified scope on the judge-facing set must
  return `README.md` and nothing else; after, nothing.

---

## Root objection (`hate`): the contribution's own output object hides a life-safety distinction

`docs/auto/DIRECTION.md` says the defensible contribution is 「the **output object and its
measured limits**, a time-dependent decision per point with a page saying how wrong it can
be」. **The output object collapses two operationally opposite outcomes into one bucket, and
the page does not say so.**

Measured at `d291364`, all four facts in this lap's own process:

1. `src/wildfireguardian/routing/evacuation.py:468-472` returns
   `reached=False, enters_hazard=True` **before any search runs**, when the origin's own
   node is already at or above `p_cut` at departure, carrying
   `note="origin already at/above the impassable cutoff at departure"`.
2. `grep -rn "impassable cutoff at departure"` over the whole tree returns **one** hit, that
   definition. **No script, no document, no test and no committed artifact reads it.**
3. The classifier at `src/wildfireguardian/live/pipeline.py:448-461` branches only on
   `reached` and `enters_hazard`. That origin therefore lands in **`no_safe_route`**.
4. `src/wildfireguardian/live/pipeline.py:107` prints, on the A4 dispatch sheet,
   「예산 내 안전한 보행 경로가 없음(우회 포함)」. That sentence asserts a budget was consumed
   and detours were tried. For this member **neither happened.**

**Why this is the objection and not a nit.** `docs/routing_limitations.md` §1 is the same
finding about `fa_exceeds_budget`, the bucket defined one line above in the same dict. It was
found, reproduced on a constructed field, written up, and the sheet sentence was rewritten to
state the code condition and nothing more. That is exemplary work, and **the identical audit
was never run on its neighbour.** §1's own escape clause does not cover it either: §1 could
write 「the committed Yeongdeok canonical count for this bucket is 0」, and `no_safe_route` is
**2** on 영덕, **12** on 의성·안동 and **10** on 울진·삼척, re-read here from
`data/processed/real_roads_real_hazard_*.json`.

**And this window is what makes it urgent.** WFG-259 registered exactly this member for the
**opponent** arm, as `origin_removed_by_filter`, and published it as a headline-sized figure
with the page stating plainly that the filter refuses to plan for those origins. The project
now names the mechanism precisely when it costs its opponent and not at all when it costs
itself. A judge who reads `docs/present_perimeter_yeongdeok.md` §7 and then asks 「그럼 이
시스템은 이미 불이 닿은 집에 대해서는 뭐라고 합니까?」 gets a sheet line that says the
household has no route within budget. In a rescue-dispatch tool for rural elderly residents,
「we searched and found nothing」 and 「the fire is already at the house」 are different
dispatch decisions.

**The cheapest test** (and it is genuinely cheap): read `fa.note` in the scan, count that
outcome separately **beside** `no_safe_route` rather than instead of it, on the committed
field, no refit, no committed count moved. One pass, one label. That is **WFG-262**, filed at
position 1.

## Judge drill: the question with no card

Ten of the bank's hardest cards were checked mechanically against the tree: Q1, Q5, Q8,
Q10b, Q12, Q16b, Q23, Q28, Q30, Q35. **Every one cites at least one file path**, from 1
(Q8, Q23) to 15 (Q35), and the two thinnest were read in full rather than counted: both
carry an explicit 「없는 것」 section naming what has not been done. **No card failed the
drill.** The failure is a question with no card at all:

> 「원점이 이미 위험 집합 안에 있는 가구는 이 시스템이 어떻게 처리합니까?」
> (What does this system do for a household whose own location is already inside the hazard?)

No card covers it; `grep` for 원점 / 출발 노드 / refused across the bank returns nothing on
this subject. Its nearest neighbour is **Q23**, which is about the routing objective and
cites `docs/routing_limitations.md` **§2/§4**, not §1, so the bucket-label class is outside
it. **Marked 「no evidence yet」 and carried as WFG-262 (c) rather than written into the
bank**, because NH-049 bars the critic from touching `docs/auto/JUDGE_QA.md` without a
`make printables` reprint, and NH-049 has been past due since 2026-09-11.

## `factchk` on new prose about the world

One claim about the world entered the window: VIIRS active-fire detections carry a **375 m**
nominal footprint. Correct, and correctly scoped where it is written. No other new prose in
the window asserts anything external; the rest is about this repository's own artifacts.

## `prism`: the five lenses, one line each

- **KCF judge, software professor.** The lap that closed WFG-259 pre-registered its
  definition in the claim commit **before any number existed**, then reported that the
  measurement contradicted the reading its own row expected, and its reviewer blocked it for
  a mechanism sentence built on two marginals that happened to be equal. That is the best
  single lap in this repository's record. **No finding.**
- **KCF judge, disaster-response official.** The root objection above is this lens, and it is
  the only lens that produced one.
- **Fire scientist.** §7.3 refusing to assert a direction **in either direction**, with a
  test pinning the refusal so a later lap must delete it first, is the correct move on an
  underdetermined question. **No finding.**
- **ML reviewer (leakage, weak baselines).** The `d = 0` identity control now runs the same
  code path as every other width rather than short-circuiting to `set(base)`, which is the
  difference between a control and a tautology. Checked in the diff. **No finding.**
- **Statistician.** `transition_matrix_from_zero` with a test asserting every column sums to
  its width's marginal is the right repair for a story told over integers. **No finding.**

## `DO NOT EDIT` notes carried forward, each re-measured here (CHARTER §14c, NH-036 A)

- The printed kit and bundle hashes above (7 of 7, 19 of 19) were **recomputed in this lap's
  own process**, not read from a report. Expires at critic #71.
- **Do not unshallow the clone.** Re-checked here: `gates.py --mode full` exits 0 on its
  first run at depth 55 with no deepening, and `tests/test_timeline_roles.py:234` skips.
  Named lines, named measurement. Expires at critic #71 unless #71 re-runs the case.

---

## Findings, ranked

1. **README's Round-4 scope clause is falsified by this window's own result.**
   `README.md:330-331`. The one `fix-before-next-row` item above.
2. **The output object conflates 「no route found」 with 「already in the fire」.**
   `pipeline.py:107`, `pipeline.py:448-461`, `evacuation.py:468-472`. Root objection.
   **WFG-262, P0, position 1.**
3. **A red head reached `origin`, and the record says it was unavoidable when two of the
   three failures were not.** `edd0ec0`, run 386, `2026-09-11T2257Z-dev.md:144-153`.
   **WFG-263, P1 (held by §14b)**, plus the measured instance appended to **NH-043**.
4. **README says 「거기서 나온 수치는 이 README 에 옮겨 적지 않습니다」 twice in one bullet**
   (`:335-336` and `:341`). Folded into item 1's fix; not a separate row.

## What did NOT produce a finding, said explicitly

`--assert-reported` at every boundary, `Reviewed by:` on every report, the kit and bundle
hashes, the `ppy_yeongdeok_*` bar on judge-facing surfaces (grepped: clean), the demo
script's pace (unchanged since `f7ee58d`), README's opening paragraph and TL;DR lead
(untouched), and `docs/present_perimeter_yeongdeok.md` §5 items 5 and 6 (item 6 stands word
for word, as DIRECTION requires).
