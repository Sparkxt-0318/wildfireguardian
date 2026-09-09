# CRITIC_LATEST — critic #51, 2026-09-09T1418Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head: `8506a2d`, and
every measurement below was taken on that head in this clone. ⚠ **This clone opened SHALLOW at 50 commits.**
I deepened it with `git fetch --shallow-since='2026-09-07T00:00:00Z'` to **149** commits, oldest resolvable
`0c862cb` at **00:18Z on 09-07**, a predicate that is the window and not a guessed depth.
`--is-shallow-repository` still answers **true**, so **no ancestry or reachability claim appears anywhere
below.** Full report: `docs/auto/reports/2026-09-09T1418Z-critic.md`.*

## `fix-before-next-row`: ONE item, and it is fifteen minutes

**`docs/auto/JUDGE_QA.md` Q36 (`:1399`) tells the student to say, out loud, to a judge, that this repository
has no answer to its hardest question. It has had one since 12:51Z today.**

Q36 is the oracle question, 「비교하신 예보 경로는 정답을 미리 본 예보 아닙니까?」. Its card reads
「**맞습니다. 오늘 이 질문의 정직한 답은 「맞습니다」 한 마디이고 그 뒤가 비어 있습니다**」 and instructs the
student to open at the booth with 「저희 모델이 실제로 사는 값은 아직 재지 않았습니다」. Two hours before I
read it, the same loop shipped `docs/oracle_gap.md`, whose §5 opens 「그 뒤가 비어 있습니다」 is no longer the
honest answer and gives the student four sentences that point at a committed file.

The card is one of the **seven** hashed `SOURCES` of the printed booth kit, so this is the surface a judge
actually meets, and NH-049 is why a critic lap may not fix it and a dev lap must.

**Scope it exactly, and no wider:**

- Fix only the clause that is now false. 「그 뒤가 비어 있습니다」 and the booth line built on it.
- Point the card at `docs/oracle_gap.md` and let it say what that file establishes: the field the arm plans on
  is a **leave-one-fire-out forward simulation**, a model output on a fire the model never saw, not truth; how
  far it sits from the observation is measured in that file.
- ⚠ **Put NO margin value on the card** (9, 27, 5, 19, 86) and do not assert a re-graded margin. WFG-213 is
  `blocked(NH-052)` and nothing about it is settled.
- ⚠ **Do not resolve the word 「상한」 on this card.** Whether 42 bounds the true margin from above is now an
  open question and it is **NH-053**, filed this lap. The card may say the question is open; it may not answer it.
- The kit is hashed, so the same lap runs `make printables` and re-points
  `release/kcf-finals-2026/MANIFEST.json` after staging, exactly as the 0949Z and 1250Z laps did.

**Then take the top row, which is WFG-027.** WFG-125 closed and I spent no reorder, so the table order stands
on its own.

## Nothing is red, and I checked rather than inherited it

`gates.py --mode full` exits **0** at `8506a2d` (1841 passed, 63 skipped, 3 xfailed, pytest 386.9 s).
`baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029 and CHARTER §3d
working as the author chose. `--assert-head` exits 0; `--assert-reported --base eff2183` exits 0 over 67
substantive paths.

**GitHub `auto-gates`, runs 242 to 289, the full 24 h window:** three `failure` runs, all of them inside
critic #50's window and all already closed. Run **253** (`0cca093`, upload-artifact 403, closed at
`b2cda36`), run **255** (`b7c1837`, browser launch, closed at `298a09c`), run **260** (`7eeccab`, a debug-port
race, closed at `1fa0b7f`). Five runs are `cancelled` (242, 245, 275, 278, 284), each superseded by the next
push. **The four runs since critic #50 (286, 287, 288, 289) are all `success`, and 289 is green at this exact
head.** So there is **no new red run** and CHARTER §4b sets no finding #1 this lap.

Every **dev** report in the window records `Reviewed by:`. Two reports do not, and neither is a dev report:
`2026-09-08T2231Z-manual.md` (a ci-red repair) and `2026-09-08T2343Z-critic.md`. CHARTER §4 step 5 puts the
independent review on the dev lap, so that is the rule working and not a gap.

## The root objection (`hate`)

**This repository now says two different things about what its headline number means, on six surfaces, and
the one that is right is the one nobody can reach.**

`docs/oracle_gap.md`, shipped at 12:51Z today, establishes in §2 that the forecast-aware arm **does not plan
on truth**. It plans on `haz_stack`, a leave-one-fire-out forward simulation, and what makes it an oracle is
that the **grader** treats that same array as truth. Its §5 says the consequence in the student's own words:
42 is 「**자기 예측을 그대로 믿었을 때의 값**」 rather than 「완벽한 예보의 값」.

Five surfaces still say the other thing, measured at this head:

| surface | line | what it says |
|---|---|---|
| `README.md` | `:36` | 「42 is an upper bound: it is what a *noiseless* forecast would buy」 |
| `README.md` | `:266-267` | 「42곳은 잡음 없는 완벽한 예보가 사 줄 값의 「상한」」 |
| `README.md` | `:702` | 「an **upper bound** — what a *noiseless* forecast would buy」 |
| `paper/manuscript.md` | `:512` | 「what a *noiseless* forecast is worth」 |
| `docs/auto/JUDGE_QA.md` | `:1399` | 「그건 완벽한 예보가 사는 값의 상한이고」, and the student is told to say it |

**A noiseless forecast plans on the observation. This arm plans on a model output and is graded on the same
model output.** Those are different objects, and the second is a self-consistency margin. Nothing in this
repository proves a self-consistency margin bounds the true margin from above: changing the grading field
moves the fire-blind arm's score too, and the margin is a difference of two scores. The word 「상한」 is
therefore **asserted, not derived**, and it is asserted on the front door, in the manuscript, and on a printed
card the student recites.

**The cheapest test, ten seconds, already run:** `grep -n "상한\|upper bound\|noiseless\|완벽한 예보"` over the
five files. Five hits, zero of them qualified, and `docs/oracle_gap.md` referenced by none of them.

**Credit where it is due, because it changes the reading.** The lap that created this inconsistency is the
best lap in the window and possibly in the sprint. It inverted a premise five laps had assumed, its
independent reviewer caught a false independence claim and the lap fixed it without arguing, and it registered
the per-slice time gaps as keys so the next reader can check it. The defect is not that the work was wrong. It
is that the correction stopped at the document that made it, which is CHARTER §5c's whole argument.

## What this lap changed, so you do not re-derive it

- **ZERO §3b reorders, spent deliberately.** WFG-125 is `done`, so WFG-027 rises to the top on its own and
  needs no lever. My new judge-facing row (**WFG-214**) is filed **in table order, not at position 1**, per
  `DIRECTION.md` and NH-051, and promoting it by a reorder would be that same mechanic under another name.
- **ONE `fix-before-next-row` item**, above, on the Q&A bank.
- **TWO new rows.** **WFG-214** (P0, KCF) propagates the oracle correction to the four non-bank surfaces.
  **WFG-215** (P1, science) is the interpretation defect I found inside `docs/oracle_gap.md` itself.
- **ONE new NEEDS_HUMAN entry, `NH-053`**, on the word 「상한」, with four options and a recommendation.
- **ONE correction written into an existing entry.** `NH-052` carried the sentence 「IoU 0.394, which
  independently re-derives the ≈ 0.40 figure `docs/MODEL_CARD.md` already reports **from a different
  artifact**」. That is the exact sentence the lap's own reviewer blocked on and the lap retracted in
  `docs/oracle_gap.md` §4b, calling the agreement 「close to **mechanical**」. The retraction reached the
  document and the registrar band and **not** the decision entry the author reads. I corrected it in place,
  dated, rather than filing a row asking someone else to.
- **Scorecard:** Track B **94 → 93**, Track A **93 → 92**. One row moves on each and it is the same row,
  제출 자료, **down**. See `docs/auto/SCORECARD.md` for the measurement and for the raise I did not give.
- **`docs/auto/JUDGE_QA.md` was NOT edited** (NH-049). The judge drill's two unanswerable questions are rows,
  not cards: 「어떤 일정으로 만드셨습니까?」 is WFG-027 and 「그럼 42는 완벽한 예보의 값입니까, 자기 예측을
  믿은 값입니까?」 is NH-053 plus WFG-214.

## The judge drill, and the two questions that still have no file behind them

I took the bank's hardest cards and tried to answer them from files alone.

1. **「어떤 일정으로 만드셨습니까?」** Re-measured at this head: 일정 answers **0** on `README.md`, **0** on
   `web/finals.html`, **0** on `docs/auto/JUDGE_QA.md`, **1** on `docs/auto/DEMO_SCRIPT_5MIN.md`, and that one
   is the adjective 일정한. 로드맵 and 개발과정 answer **0** on all four. It is a named sub-item of
   설계와 방법론, **20 points on both tables**. **WFG-027**, and it is the top row.
2. **「그럼 42는 완벽한 예보의 값입니까, 자기 예측을 믿은 값입니까?」** Six surfaces, two answers. **NH-053.**
3. **「선생님 모델이 실제로 벌어 주는 값은 얼마입니까?」** Still no number, and correctly so: WFG-213 is
   `blocked(NH-052)` and the loop must not guess. What changed today is that there is now a document that
   says what is known and what is not, and it is reachable from no judge-facing surface. **WFG-214.**

Everything else in the bank I could answer from a file.

## Readiness: 8 of 11, ZERO ticked for the EIGHTH consecutive critic lap

`docs/auto/KCF_READINESS.md` gained 279 lines this window and **no tick**. The count has stood at 8 since
critic #43 at 2026-09-08T1429Z. Critic #50 measured the cause and I re-read it rather than restating it: R12
is the author's (NH-014); R3 is `blocked(NH-046)`; R11's row WFG-024 is held by CHARTER §14b until R1, R3, R4,
R7, R8 and R9 all tick, and **R3 is the only one of the six unticked**. Both remaining agent-reachable lines
are downstream of **one unanswered question**. No fourteenth question is filed; NH-046 asks it already and has
carried the loop's recommendation unchanged for four laps.

⚠ **The `Do NOT edit` note is RE-STATED, its premise re-checked (CHARTER §14c as the routine prompt states it,
NH-036 A; ⚠ a search for `14c` in `docs/auto/CHARTER.md` still answers **0** at this head, and NH-036, NH-038
and NH-051 are all still `open`).** It covers **`README.md:210-282`**, the Round-4 fair-opponent block, whose
bounds I re-measured at this head (「### 1.」 at **210**, 「### 2.」 at **283**), unchanged from critic #49 and
#50. It forbids exactly one thing in those lines: putting a present-perimeter **margin value** (9, 27, 5, 19,
86) there while NH-032 and NH-034 are open. Both re-read at `NEEDS_HUMAN.md:1391` and `:1574`: still `open`,
both due 2026-09-08, so **two days overdue**. A scan of 210-282 finds no margin value there today. **It
expires at critic #52 unless that lap re-states it after re-reading them.** It freezes no file and no
question, and I am naming the edit it permits so nobody has to guess: **WFG-214's rewording of
`README.md:266-267` is inside these lines and is allowed**, because 「완벽한 예보」 is not a margin value.
