# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine; updated 2026-09-09T1418Z by critic #51 (CHARTER §14).
The dev routine reads this before it claims a row; the critic re-checks it after every dev lap, at most one
reorder per lap, with a reason. Only the most recent critic note is kept, as §14 specifies; the 54,923-byte
version this page replaced is archived verbatim at `docs/auto/archive/DIRECTION_superseded_2026-09-08T1817Z.md`.*

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a
per-household walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive.
Its defensible contribution is not forecast accuracy (Korea's own agencies forecast spread better resourced
than we can) but the **output object**: a household-level, time-dependent decision with its limits measured
and written down.

## Next three rows, and why each is next

Table order at `8506a2d`. **This lap spent ZERO §3b reorders, set ONE `fix-before-next-row` item, and filed
its two new rows in table order rather than at position 1 (NH-051).** WFG-125 closed, so the order below is
the table's own and needed no lever.

0. **First, the `fix-before-next-row` item in `CRITIC_LATEST.md`, which is fifteen minutes.**
   `docs/auto/JUDGE_QA.md` Q36 (`:1399`) tells the student to say to a judge that after 「맞습니다」 this
   repository has nothing. It has had `docs/oracle_gap.md` since 12:51Z today. The card is one of the seven
   hashed `SOURCES` of the printed kit, so a critic lap cannot fix it (NH-049) and a dev lap must, with
   `make printables` and a re-pointed `release/kcf-finals-2026/MANIFEST.json` in the same lap.
1. **WFG-027 (P0, KCF), the top `todo` row, and it rose there on its own.** Re-measured at this head: 일정
   answers **0** on `README.md`, **0** on `web/finals.html`, **0** on `docs/auto/JUDGE_QA.md` and **1** on
   `docs/auto/DEMO_SCRIPT_5MIN.md`, and that hit is the adjective 일정한; 로드맵 and 개발과정 answer **0** on
   all four. A named sub-item of 설계와 방법론, **20 points on both tables**, at literal zero for a fifth
   consecutive critic lap. It is a documentation zero the student could answer from memory at the booth,
   which is exactly why it keeps losing to knowledge zeros, and why it is now first.
2. **WFG-214 (P0, KCF), filed by this lap, in table order.** Five judge-facing surfaces call 42 and 91
   「완벽한 예보의 상한」 and this repository's own newest document says that is the wrong reading:
   `docs/oracle_gap.md` §2 shows the arm plans on a leave-one-fire-out model output, not on truth, and §5
   calls 42 「자기 예측을 그대로 믿었을 때의 값」. The row fixes the **mechanism** description and links the
   four non-bank surfaces to that file. ⚠ It may **not** settle the word 「상한」; that is **NH-053**.
3. **WFG-212 (P0, KCF), filed by critic #50 and untouched.** `README.md:200-362` carries 11 ⚠ markers and 28
   negative-framing tokens against one affirmative-outcome token, and that one favours the opponent.
   「자료의 논리적 구성」, 20 points on both tables. ⚠ Not a request to soften anything: the fix **adds** a
   lead paragraph and removes no caveat.

Behind those, in table order: WFG-007, WFG-117, WFG-128, WFG-129, WFG-121, WFG-106, WFG-036, WFG-101,
WFG-119, WFG-024, WFG-054, and WFG-215 in the P1 band. **Fourteen P0 rows `todo`, six sprint days**, counted
here at this head rather than inherited (`WFG-213` is `blocked(NH-052)` and is not in that count). WFG-125
closed today and one P0 was filed, mine.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- **Do not file a judge-facing critic finding at table position 1 while NH-051 is open.** NH-038's own option
  B puts it 「in the table like any other」; 「at position 1」 is option **D**'s mechanic. Write the placement
  and the reason into the row, as WFG-212 and WFG-214 do.
- **Do not settle the word 「상한」 / 「upper bound」 in any lap.** It is a claim about a judged headline
  number, nothing in the tree derives it, and NH-053 is open. Describe the mechanism; leave the word alone
  and point at NH-053.
- **Do not put a margin value (9, 27, 5, 19, 86) on any judge-facing surface** while NH-032, NH-034 and
  NH-052 are open, and not in `README.md:210-282` at all (the `Do NOT edit` note in `CRITIC_LATEST.md`).
- **Do not refit anything.** Every headline number is downstream of the fitted `spread_v2` model and
  CHARTER §3 rule 2 forbids regenerating a committed artifact.
- **Do not add documents to the release bundle.** WFG-208 closed with one sentence and a URL, which is the
  shape that fix takes; adding payload widens the freeze.
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13–§14).
- **Do not compare accuracy with NIFoS or G-DAPS.** Their figures are agency statements with no published
  metric definition; the differentiator is the output object.
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or
  `docs/NUMBERS.json`** (CHARTER §13, §3 rule 5b).

## Readiness lines ticked in the last 24 h: ZERO, for the eighth consecutive critic lap

`docs/auto/KCF_READINESS.md` stands at **8 of 11** and has stood there since critic #43 ticked R8 at
2026-09-08T1429Z. It gained 279 lines this window and no tick. Critic #50 measured the cause and I re-read it
rather than restating it: R12 is the author's (NH-014); R3 is `blocked(NH-046)`; and R11's row **WFG-024** is
held by CHARTER §14b as loop hygiene, released only when R1, R3, R4, R7, R8 and R9 all tick, of which **R3 is
the only one unticked**. Both remaining agent-reachable lines are downstream of **one unanswered question,
NH-046**, whose recommendation the loop has now stated four times. Nothing a lap can do moves the count.

## Critic's last direction note

**2026-09-09T1418Z, critic #51. ZERO §3b reorders, none needed. ONE `fix-before-next-row` item, on the
printed Q&A bank. TWO new rows (WFG-214 P0, WFG-215 P1), both in table order. ONE new NEEDS_HUMAN entry
(NH-053). ONE correction written into an existing entry (NH-052).**

Verified at `8506a2d`. ⚠ **The clone opened SHALLOW at 50 commits.** Deepened with
`git fetch --shallow-since='2026-09-07T00:00:00Z'` to **149** commits, oldest resolvable `0c862cb` at
**00:18Z on 09-07**, a predicate that is the window and not a guessed depth. `--is-shallow-repository` still
answers `true`, so **no ancestry or reachability claim appears in this lap's output.**
`gates.py --mode full` exits **0** (1841 passed, 63 skipped, 3 xfailed, pytest 386.9 s); `baseline-verify`
WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029 and §3d working. `--assert-head` and
`--assert-reported --base eff2183` both exit 0 over 67 substantive paths. **GitHub `auto-gates`, runs 242 to
289: three `failure` (253, 255, 260), all inside critic #50's window and all closed by `wfg-autoloop-ci-red`
within the hour; five `cancelled`, each superseded by the next push; and the four runs since critic #50 (286
to 289) all `success`, with 289 green at this exact head. No new red run, so §4b sets no finding #1.** Every
**dev** report in the window carries `Reviewed by:`; the two that do not are a ci-red repair and a critic
report, neither of which §4 step 5 covers. `factchk` had nothing new to check: the only prose added since
critic #50 is `docs/oracle_gap.md`, whose every claim is about arrays in this repository, and I verified
those against `data/processed/oracle_gap_yeongdeok.json` directly.

**The root objection: this repository now gives two answers to what its headline number means, on six
surfaces, and the right one is the one nobody can reach.** `docs/oracle_gap.md` establishes that the
forecast-aware arm does not plan on truth and that the oracle sits in the **grader**; five other surfaces,
including the manuscript and a card printed in the booth kit, still call 42 「완벽한 예보의 상한」. **Cheapest
test, ten seconds, already run:** grep the five files for 「상한」 / upper bound / noiseless. Five hits, none
qualified, and zero of them link to the document that corrects them. ⚠ **The lap that created this is the
best lap of the sprint** and the defect is not that its work was wrong: it is that the correction stopped at
the document that made it, which is CHARTER §5c's whole argument, restated one day later on a bigger claim.

⚠ **The one `Do NOT edit` note, RE-STATED after re-checking its premise (CHARTER §14c as the routine prompt
states it, NH-036 A; ⚠ a search for `14c` in `docs/auto/CHARTER.md` still answers **0** at this head, and
NH-036, NH-038 and NH-051 are all still `open`).** It covers **`README.md:210-282`**, the Round-4
fair-opponent block, whose bounds this lap re-measured (「### 1.」 at **210**, 「### 2.」 at **283**), unchanged
from critic #49 and #50. It forbids exactly one thing in those lines: putting a present-perimeter **margin
value** (9, 27, 5, 19, 86) there while NH-032 and NH-034 are open. Both re-read at `NEEDS_HUMAN.md:1391` and
`:1574`: both still `open`, both due 2026-09-08, so **two days overdue**. A scan of 210-282 finds no margin
value there today. **It expires at critic #52 unless that lap re-states it after re-reading them.** It
freezes no file and no question, and the edit it permits is named so nobody has to guess: **WFG-214's
rewording of `README.md:266-267` is inside these lines and is allowed**, because 「완벽한 예보」 is not a
margin value.
