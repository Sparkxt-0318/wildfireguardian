# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine; updated 2026-09-09T1122Z by critic #50 (CHARTER §14).
The dev routine reads this before it claims a row; the critic re-checks it after every dev lap, at most one
reorder per lap, with a reason. Only the most recent critic note is kept, as §14 specifies; the 54,923-byte
version this page replaced is archived verbatim at `docs/auto/archive/DIRECTION_superseded_2026-09-08T1817Z.md`.*

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a
per-household walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive.
Its defensible contribution is not forecast accuracy — Korea's own agencies forecast spread better resourced
than we can — but the **output object**: a household-level, time-dependent decision with its limits measured
and written down.

## Next three rows, and why each is next

Table order at `9c22ff3` after critic #50. **This lap spent its ONE §3b reorder promoting WFG-125 above
WFG-027, set NO `fix-before-next-row` item, and filed its one new P0 row in table order rather than at
position 1 (see the note at the foot of this page and NH-051).**

1. **WFG-125 (P0, science) — PROMOTED TO FIRST `todo` BY THIS LAP, after four consecutive critic laps of
   being ranked below a newer row.** The window did not make this row less urgent; it made it more urgent, and it did so on
   the front door. `README.md`'s TL;DR now carries, directly under its single headline number, 「42 is an upper
   bound: it is what a *noiseless* forecast would buy, not what this project's own model buys, which is less by
   an amount no run here measures」, and `README.md:261-268` repeats the property. **The repository now hands
   every judge who reads its front door the exact question this row exists to answer, and no file in the tree
   answers it.** The row's cheap branch is ten minutes and the row names it: record the absence with the paths
   checked (`data/processed/` holds `hazard_*.npz` and the `spread_v2/` outputs, and which of them is a
   prediction rather than the graded truth is the row's first question). The expensive branch needs a fill rule
   for the ~82 % of 영덕's 26,607-cell grid the out-of-fold file does not cover, and a fill rule chosen after
   seeing the margin is a second post-hoc maximum — so the cheap branch is the one that fits a lap.
2. **WFG-027 (P0, KCF) — moved down one place, and not because 일정 stopped mattering.** Re-measured at this
   head: 일정 answers **0** on `README.md`, **0** on `web/finals.html`, **0** on `docs/auto/JUDGE_QA.md` and
   **1** on `docs/auto/DEMO_SCRIPT_5MIN.md`, and that hit is the adjective 일정한; 로드맵 and 개발과정 answer
   **0** on all four. It is a named sub-item of 설계와 방법론, **20 points on both tables**. But that zero is a
   **documentation** zero — the student lived the schedule and can answer 「어떤 일정으로 만드셨습니까?」 from
   memory at the booth. WFG-125's zero is a **knowledge** zero: nobody in the room can answer 「그럼 선생님
   모델이 실제로 벌어 주는 값은 얼마입니까?」. Both are minutes on their cheap branch, so this costs WFG-027
   one lap at most.
3. **WFG-212 (P0, KCF) — filed by this lap, in table order.** `README.md:200-362` (Round 4, 163 lines, the
   first thing after the Round-3 record) carries **11** ⚠ markers and **28** negative-framing tokens against
   **one** affirmative-outcome token — 「더 좋」, and that one says the model-free opponent scored **better**
   than the repository had recorded. The section documents what Round 4 attacked and never states what the
   project still claims. This is 「자료의 논리적 구성」, a named criterion of 제출 자료 (20 points on both
   tables). ⚠ It is **not** a request to soften anything: every caveat is true and stays; the fix adds a lead
   paragraph, it removes nothing.

Behind those, in table order: WFG-007, WFG-117, WFG-128, WFG-129, WFG-121, WFG-106, WFG-036, WFG-101,
WFG-119, WFG-024, WFG-054. **Fourteen P0 rows `todo`, six sprint days**, counted here rather than inherited.
The ratio did not improve, and one of the fourteen is this lap's own.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- **Do not file a judge-facing critic finding at table position 1 while NH-051 is open.** NH-038's own option
  B puts it 「in the table like any other」; 「at position 1」 is option **D**'s mechanic. Write the placement
  and the reason into the row, as WFG-212 does.
- **Do not demote WFG-125 again without a measurement that beats the one above.** Four consecutive critic laps have ranked it
  below a newer row; the fifth needs an argument, not a newer defect.
- **Do not refit anything.** Every headline number is downstream of the fitted `spread_v2` model and
  CHARTER §3 rule 2 forbids regenerating a committed artifact.
- **Do not add documents to the release bundle.** WFG-208 closed with one sentence and a URL, which is the
  shape that fix takes; adding payload widens the freeze.
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13–§14).
- **Do not compare accuracy with NIFoS or G-DAPS.** Their figures are agency statements with no published
  metric definition; the differentiator is the output object.
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or
  `docs/NUMBERS.json`** (CHARTER §13, §3 rule 5b).

## Readiness lines ticked in the last 24 h: ZERO, for the seventh consecutive critic lap

`docs/auto/KCF_READINESS.md` stands at **8 of 11** and has stood there since critic #43 ticked R8 at
2026-09-08T1429Z. **The reason is now measured rather than restated, and it is a single point of failure:**
R12 is the author's (NH-014); R3 is `blocked(NH-046)`; and R11's row **WFG-024** is held by CHARTER §14b as
loop hygiene, whose release condition is that R1, R3, R4, R7, R8 and R9 all tick — of which **R3 is the only
one unticked**. So both remaining agent-reachable readiness lines are downstream of **one unanswered
question, NH-046**, whose own recommendation the loop has stated three times. Nothing a lap can do moves the
count.

## Critic's last direction note

**2026-09-09T1122Z, critic #50. ONE §3b reorder, spent promoting WFG-125 above WFG-027. ZERO
`fix-before-next-row` items, declined deliberately. ONE new P0 row (WFG-212), filed in table order and not at
position 1. ONE new NEEDS_HUMAN entry (NH-051). One measurement appended to WFG-125.**

Verified at `9c22ff3`. ⚠ **The clone opened SHALLOW at 50 commits.** Deepened with
`git fetch --shallow-since='2026-09-08T00:00:00Z'` to **90** commits, oldest resolvable `088203c` at
**00:22:53Z on 09-08**, a predicate that is the window and not a guessed depth. `--is-shallow-repository`
still answers `true`, so **no ancestry or reachability claim appears in this lap's output.**
`gates.py --mode full` exits **0** (1830 passed, 63 skipped, 3 xfailed, pytest 373.4 s); `baseline-verify`
WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029/§3d working. **GitHub `auto-gates`, the
full 24 h window this time — runs 246 to 285, wider than critic #49's — carries THREE `failure` runs, and all
three were closed inside the hour by `wfg-autoloop-ci-red`:** run **253** at `0cca093` (upload-artifact 403,
closed at `b2cda36`, WFG-193/195), run **255** at `b7c1837` (browser launch, closed at `298a09c`, WFG-196)
and run **260** at `7eeccab` (a debug-port race, closed at `1fa0b7f`). Runs 278 and 284 are `cancelled`,
each superseded by the next push, and run **285** is `success` at this exact head. **By the letter of
CHARTER §4b those three are finding #1; no `fix-before-next-row` item is set for them, because all three are
already fixed, reported and re-run green — an item would spend the dev lap on work that is done.** None was
a product test failure; all three were runner or upload shaped. All seven dev reports in the window carry
`Reviewed by:`; `--assert-head` and `--assert-reported --base 088203c` both exit 0 over 95 substantive
paths. **`factchk` on every new world claim in the window found
nothing:** Opanasopit & Louis (*Frontiers in Built Environment* 12, 2026-08-06), Chen et al. <!-- forbidden-ok: Chen --> (*PLOS ONE*,
2026-09-01) and 헤럴드경제 (2026-02-12) were each opened here and each confirmed the repository's wording,
including 70 isolated communities, 38,100 → 11,900 residents, R² 0.9251 and 0.57–0.77, and the verbatim
「화선 도달 8시간 전 … 5시간 전에는」.

**The root objection: the front door now asks the judge a question the repository cannot answer, and the loop
has spent four consecutive critic laps making the question sharper instead of answering it.** Round 4 and the TL;DR between them
retire this project's only headline number as an upper bound on what a *noiseless* forecast would buy, and
say in writing that what the project's own model buys is 「less by an amount no run here measures」. That is
the right sentence to have written. It is also an unanswered question printed on the most-read surface, and
`Track A 개발 목적` plus `구현 및 유용성` are **40 of 100** on a claim of usefulness the front door no longer
makes. **Cheapest test, ten seconds, already run:** count affirmative-outcome tokens in `README.md:200-362`.
Answer **one**, and it favours the opponent. **The fix is not less honesty — it is WFG-125 and WFG-212.**

⚠ **The one `Do NOT edit` note, RE-STATED after re-checking its premise (CHARTER §14c as the routine prompt
states it, NH-036 A; ⚠ a search for `14c` in `docs/auto/CHARTER.md` answers **0** at this head, and both NH
entries are still `open` — that is NH-050 and NH-051).** It covers **`README.md:210-282`**, the Round-4
fair-opponent block, whose bounds this lap re-measured (「### 1.」 at **210**, 「### 2.」 at **283**) and which
are unchanged from critic #49. It forbids exactly one thing in those lines: putting a present-perimeter
**margin value** (9, 27, 5, 19, 86) there while NH-032 and NH-034 are open. Both re-read at
`NEEDS_HUMAN.md:1391` and `:1574`: both still `open`, both due 2026-09-08, so **one day overdue**. A scan of
210-282 finds no margin value there today. **It expires at critic #51 unless that lap re-states it after
re-reading them.** It freezes no file and no question: `README.md:326-355` is four lines below it and was
edited this window, which is the kind of edit it permits, and WFG-212's lead paragraph is another.
