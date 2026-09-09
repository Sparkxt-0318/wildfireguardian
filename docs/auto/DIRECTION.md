# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine; updated 2026-09-09T0820Z by critic #49 (CHARTER §14).
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

Table order at `7f914fd` after critic #49. **This lap spent NO §3b reorder and declines the one critic #48
pre-registered.** It filed one new P0 row at position 1 (WFG-210) and set one `fix-before-next-row` item,
minutes, on the README.

1. **WFG-210 (P0, KCF) — FILED AT POSITION 1 BY THIS LAP.** The 창의성 answer now stands on all four judge
   surfaces, and on three of them item ① 「the output object is the contribution」 anchors on
   `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md`, a landscape note about NIFoS and G-DAPS.
   `tests/test_creativity_card.py:86` defines `OTHER_SYSTEMS = ("NIFoS", "G-DAPS", "산림청", "경기도",
   "국립산림과학원", …)` and turns red if the spoken draft names one of them; the anchor that same file
   registers at `:65` and `:331` carries **34** mentions of those systems and **12** of their announced
   percentages. So the gate keeps the competitors out of the student's mouth and the anchor hands them to the
   judge, and no surface gives a path to an instance of the object item ① names. The README half is minutes and
   is this lap's `fix-before-next-row` item; the screen and card halves need `make finals`, a kit rebuild and a
   gate change, which is why they are a row.
2. **WFG-027 (P0, KCF)** — unchanged in place and unchanged in reasoning; it is the first `todo` row once
   WFG-210's README half is cleared. 일정 및 팀원 역할 배분 is a named sub-item of 설계와 방법론, **20 points on
   both tables**, and the 심사기준's 「개인의 경우 제외」 excludes the 팀원 half and not the 일정 half.
   Re-measured at this head: a raw count of 일정 answers **0** on `README.md`, **0** on `web/finals.html`,
   **0** on `docs/auto/JUDGE_QA.md` and **1** on `docs/auto/DEMO_SCRIPT_5MIN.md`, and that hit is the
   adjective. 로드맵 and 개발과정 are **0** on all four; 타임라인 occurs once, on `web/finals.html`, as a UI
   hint for the fire-time slider. A sub-item of a 20-point row is at literal zero on every surface a judge
   meets, and the answer already exists in CHARTER §1 and §11 plus `git log`.
3. **WFG-125 (P0, science)** — unchanged in place, and **this lap declines to demote it a third consecutive
   time.** Critic #47 measured it, critic #48 moved it from second to third for WFG-027, and critic #48 then
   pre-registered WFG-197 as the next promotion, which would have moved it to fourth. **That move is not made
   here.** The out-of-fold file covers **18.3 %** of 영덕's 26,607-cell grid, so the expensive branch needs a
   fill rule for the other ~82 % and a fill rule chosen after seeing the margin is a second post-hoc maximum;
   the second branch, record the absence with the paths checked, is the one that fits a lap. See the note
   below for why the deferral itself is now the objection.

Behind those, the P0 block: WFG-007, WFG-117, WFG-128, WFG-129, WFG-121, WFG-106, WFG-036, WFG-101,
WFG-119, WFG-054, WFG-024. **Thirteen P0 rows `todo`, six sprint days.** The ratio did not improve.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- **Do not promote WFG-197 above WFG-125 without saying what changed.** It is a real gap (re-measured here:
  `Ready.?Set.?Go|화선|8시간` is **0** on `docs/auto/JUDGE_QA.md`, **0** on `web/finals.html` and **0** on
  `docs/auto/DEMO_SCRIPT_5MIN.md`), and it is a P1 row on purpose until a science row runs.
- **Do not refit anything.** Every headline number is downstream of the fitted `spread_v2` model and
  CHARTER §3 rule 2 forbids regenerating a committed artifact.
- **Do not add documents to the release bundle.** WFG-208 closed with one sentence and a URL, which is the
  shape that fix takes; adding payload widens the freeze.
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13–§14).
- **Do not compare accuracy with NIFoS or G-DAPS.** Their figures are agency statements with no published
  metric definition; the differentiator is the output object.
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or
  `docs/NUMBERS.json`** (CHARTER §13, §3 rule 5b).

## Readiness lines ticked in the last 24 h: ZERO, for the sixth consecutive critic lap

`docs/auto/KCF_READINESS.md` stands at **8 of 11** and has stood there since critic #43 ticked R8 at
2026-09-08T1429Z. This window shipped real judge-facing work on all four surfaces and still ticked nothing,
because **none of the three unticked lines has a condition this window could meet**: R3 is `blocked(NH-046)`,
R12 is the author's (NH-014), and R11's row **WFG-024** sits at **table position 125**, a P0 below about a
hundred P1 rows, held there by CHARTER §14b as loop hygiene. The measurement is written into **NH-038**,
which asks this in the author's own words, rather than into a fourteenth question.

## Critic's last direction note

**2026-09-09T0820Z, critic #49. ZERO §3b reorders — the pre-registered WFG-197 promotion is DECLINED. ONE
new P0 row at position 1 (WFG-210); ONE `fix-before-next-row` item (WFG-210's README half, minutes); one
re-measurement appended to WFG-197; one measurement appended to NH-038; no new NEEDS_HUMAN entry.**

Verified at `7f914fd`. ⚠ **The clone opened SHALLOW at 50 commits.** Deepened with
`git fetch --shallow-since='2026-09-08T00:00:00Z'` to **83** commits, oldest resolvable `088203c` at
**00:22:53Z on 09-08**, a predicate that is the window and not a guessed depth. `--is-shallow-repository`
still answers `true`, so **no ancestry or reachability claim appears in this lap's output.**
`gates.py --mode full` exits **0** (1826 passed, 63 skipped, 3 xfailed, pytest 470.7 s); `baseline-verify`
WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029/§3d working. **GitHub `auto-gates`
carries no `failure` anywhere in this window** — the sixteen runs ending at **279**, of which 275 and 278 are
`cancelled`, superseded by the next push — and run **279** is `success` at this exact head, so there is no
finding #1. Every dev report in the window carries
`Reviewed by:`; `--assert-head` and `--assert-reported --base 088203c` both exit 0.

**The root objection: the card's own gate exists to keep the other systems out of the answer, and the answer
sends the judge to them.** `tests/test_creativity_card.py` spends four graded mutations proving that
「NIFoS 는 진압 지휘용입니다」 turns the suite red in either direction, and the same file registers
`docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` as the document a judge is pointed at for item ①.
That is a principle cited and its opposite implemented, and it now stands on three surfaces because the
anchor was written once in the card (WFG-182) and inherited twice, by the screen (WFG-194) and the front
door (WFG-207), each lap doing its own row correctly. **Cheapest test, ten seconds, already run:** count the
`OTHER_SYSTEMS` names inside the file the gate points at. Answer **34**, plus **12** of their announced
percentages. **WFG-210.**

⚠ **The one `Do NOT edit` note, RE-STATED after re-checking its premise (CHARTER §14c as the routine prompt
states it, NH-036 A — both still `open`, see NH-050).** It covers **`README.md:210-282`**, the Round-4
fair-opponent block, whose bounds this lap re-measured (「### 1.」 at 210, 「### 2.」 at 283) and which are
unchanged from critic #48. It forbids exactly one thing in those lines: putting a present-perimeter **margin
value** (9, 27, 5, 19, 86) there while NH-032 and NH-034 are open. Both re-read at `NEEDS_HUMAN.md:1391` and
`:1574`: both still `open`, both due 2026-09-08, so **one day overdue** — critic #48 wrote 「two days」 and the
0654Z dev report wrote 「three days」, and the correct figure is one. A scan of 210-282 finds no margin value
there today. **It expires at critic #50 unless that lap re-states it after re-reading them.** It freezes no
file and no question: `README.md:326-355`, four lines below, was written this window and that is the kind of
edit it permits.

⚠ **Candidate for the next critic lap, so it need not re-derive it:** if WFG-125 has still not run by then,
the question is no longer which row to promote but whether CHARTER §14b's ordering rule has any term a
measurement can ever win — prose surfaces are unbounded (창의성 was at zero on a fourth surface after three
laps had closed it), so the rule generates an endless queue of minutes-long rows that outranks any
measurement. That is **NH-038**, due today and open.
