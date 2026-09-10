# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine; updated 2026-09-10T0237Z by critic #55 (CHARTER §14).
The dev routine reads this before it claims a row; the critic re-checks it after every dev lap, at most one
reorder per lap, with a reason. Only the most recent critic note is kept, as §14 specifies; the 54,923-byte
version this page replaced is archived verbatim at `docs/auto/archive/DIRECTION_superseded_2026-09-08T1817Z.md`.*

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a
per-point walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive.
Its defensible contribution is not forecast accuracy (Korea's own agencies forecast spread better resourced
than we can) but the **output object**: a time-dependent decision per point, with its limits measured and
written down.

## Next three rows, and why each is next

Table order at `7dabdef`, after this lap's **zero** §3b reorders. There is **no** `fix-before-next-row` item
this lap: critic #54's was cleared by the 0017Z lap and re-measured here, and §14b says at most one, not at
least one.

1. **WFG-218 (P0, KCF) is the next row to claim.** 일정 counts **0** on `README.md` and **0** on
   `web/finals.html`, and 「일정 및 팀원 역할 배분의 타당성」 is a **named sub-item of 설계와 방법론, 20 points
   on BOTH rubric tables**. It is the only `todo` P0 row that closes a **zero on a named criterion**, and the
   row that was going to fix it is `done`, which is the residue pathology it exists to make visible.

2. **WFG-220 (P0, KCF) with it, in the same lap.** The finals screen is the only judge-facing surface carrying
   no word of the oracle-in-the-grader objection that every other surface now states. **Both rows need
   `make finals` on a commit already on `origin` and a re-pointed `release/kcf-finals-2026/MANIFEST.json` after
   staging, and that mechanic is paid once if they ship together.** WFG-222 used to be the third of this group
   and is now `done`, so the pairing is two rows rather than three and is cheaper than it was yesterday.

3. **Behind those: eleven more P0 rows, and five sprint days.** **Thirteen** P0 rows are `todo` at this head,
   counted here rather than inherited: WFG-218, 220, 007, 117, 128, 129, 121, 106, 036, 101, 119, 024, 054, so
   eleven sit behind the two above. `blocked`: WFG-213 (NH-052), WFG-124 (NH-032),
   WFG-104 (NH-032), WFG-023 (human). One P0 row closed this window and none was filed, so the `todo` count is
   down by one for the first time in four laps.

### Why zero reorders, in one paragraph

WFG-218 already stands first among the runnable `todo` rows and it is where I would have moved it anyway, so a
reorder would buy nothing and §3b permits one act without requiring it. The one row filed this lap, **WFG-223**,
is P1 and went into the table in P1 order, not above the P0 block: it is a defect in a **gate**, and CHARTER
§14b holds gate-on-gate work behind R1, R3, R4, R7, R8 and R9. **WFG-155**, the neighbouring limit of the same
scanner, is P1 for the same reason, and putting this one above the P0 block would be the loop promoting its own
machinery over the booth.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- ⚠ **Do not write 「가구 단위」 or "per-household" about the COMMITTED dispatch sheets.** This is `done`
  (WFG-222, `WC-013` registered) and the corrected wording is **지점 단위** with 「화재 위험면과 지형은 합성 ·
  출발지는 표본 좌표」 and 「실제 확산면으로 만든 출동 지시서는 아직 없습니다」 **in the same block**.
  `README.md:212-251` is the model to copy. The four remaining 「가구 단위」 in `docs/auto/JUDGE_QA.md` are
  **deliberate and correct**: `:600` names the quantity, `:680-681` is the ⭕/❌ pair about other systems, and
  `:968` is Q20a's own question. Do not "fix" them.
- ⚠ **`data/processed/timeline_roles/timeline_roles.json` may be rebuilt from a FRESH full clone, and may not
  be rebuilt from a clone you deepened.** Critic #53 measured it in a fresh clone at `ba06467`: `%h` is **7**
  characters and `build_timeline_roles.py --check` exits **0**. The eight-character anchors that turn GitHub
  red come from `git fetch --unshallow` on an already-shallow clone; `git gc --prune=now` cures it.
  **WFG-217** is still the right fix and is still P1.
- **Do not file a judge-facing critic finding at table position 1 while NH-051 is open.** NH-038's own option B
  puts it 「in the table like any other」; 「at position 1」 is option **D**'s mechanic.
- **Do not settle the word 「상한」 / 「upper bound」 in any lap.** It is a claim about a judged headline
  number, nothing in the tree derives it, and NH-053 is open. Describe the mechanism; leave the word alone.
- **Do not put a margin value (9, 27, 5, 19, 86) on any judge-facing surface** while NH-032, NH-034 and NH-052
  are open, and not in `README.md:263-342` at all (the `Do NOT edit` note in `CRITIC_LATEST.md`, whose bounds
  were re-measured at this head and are **unchanged**, because the window's nine added README lines all landed
  below that block).
- ⚠ **Do not add a word to `paper/manuscript.md`.** `check_paper.py` reads **9,000** body words against a
  9,000 hard fail at this head: the margin is **zero**. NH-037 is open and due **today, 2026-09-10**.
- **Do not refit anything.** Every headline number is downstream of the fitted `spread_v2` model and
  CHARTER §3 rule 2 forbids regenerating a committed artifact.
- **Do not add documents to the release bundle.** WFG-218 and WFG-220 change text on files already in it.
- **Do not re-open the AI-disclosure question.** NH-008 is closed, CHARTER §9 states what the project keeps
  voluntarily, and the bank now agrees with that record on all three passages.
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13–§14).
- **Do not compare accuracy with NIFoS or G-DAPS.** Their figures are agency statements with no published
  metric definition; the differentiator is the output object.
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or
  `docs/NUMBERS.json`** (CHARTER §13, §3 rule 5b).

## Readiness lines ticked in the last 24 h: ZERO, for the twelfth consecutive critic lap

`docs/auto/KCF_READINESS.md` stands at **8 of 11** and has stood there since critic #43 ticked R8 at
2026-09-08T1429Z. The cause was re-read this lap rather than restated: R12 is the author's (NH-014); R3 is
`blocked(NH-046)`; and R11's row **WFG-024** is held by CHARTER §14b as loop hygiene, released only when R1, R3,
R4, R7, R8 and R9 all tick, of which **R3 is the only one unticked**. Both remaining agent-reachable lines are
downstream of **one unanswered question, NH-046, which comes due TODAY, 2026-09-10**. ⚠ This window is the
strongest evidence yet that the count is measuring the question rather than the work: WFG-222 closed on eleven
surfaces, seventy tests were added, the kit was rebuilt and the bundle re-pointed, and the number did not move,
because none of that is what R3 asks about.

## Critic's last direction note

**2026-09-10T0237Z, critic #55. ZERO §3b reorders, deliberately. ZERO `fix-before-next-row` items, because
critic #54's was cleared and nothing judge-facing is wrong at this head that is minutes. ONE new row (WFG-223,
P1, in P1 order). ZERO rows closed by me; the dev lap closed WFG-222. ZERO new NEEDS_HUMAN entries; NH-035
raised MEDIUM to HIGH. Scorecard: one row moves on both tracks and it is the same row, 제출 자료, UP.
Track B 93 → 94, Track A 92 → 93, paid on critic #54's pre-registered condition and verified in the tree.**

Verified at `7dabdef`. `gates.py --mode full` exits **0** (**1941 passed**, 64 skipped, 3 xfailed, pytest
259.0 s, up 70 tests in one window); `baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts,
which is NH-029 and §3d working. **GitHub `auto-gates`, runs 286 to 309: no `failure` anywhere in the window,
one `cancelled` (306) superseded by the next push, and 309 green at this exact head, so CHARTER §4b sets no
finding #1.** Every dev report in the window records `Reviewed by:`, and eight of the nine record
`subagent (block)` and spend commits acting on it. `factchk`: the window adds no new external URL and no new
citation.

⚠⚠ **This lap withdrew its own first draft and says so rather than quietly rewriting it.** It began at
`49ac16e`, where `origin` held only the WFG-222 **claim** commit and had shown nothing for 107 minutes, and it
wrote a root objection about a possibly dead lap and a locked P0 row. The 0017Z lap pushed at **02:13:26Z**,
between the fetch and the push, having committed its work locally at **00:53:53Z**. It was slow, not dead.
**The root objection that survives is the smaller true one: a lap's work is invisible to every other routine
until it pushes, and this window measured that gap at about 95 minutes on a P0 row.** At the 03:17Z wake
CHARTER §5b would have computed exactly 3 h 00 m from the stamp and 2 h 54 m from the claim commit, so both
readings would have said skip, on a row that was already finished. **NH-035** is the question and it is now
HIGH; option **B** is the only one whose outcome does not depend on which timestamp a lap reads.

⚠ **The one `Do NOT edit` note, RE-STATED after re-reading NH-032 and NH-034 and after RE-MEASURING its
bounds** (CHARTER §14c, NH-036 A). It covers the Round-4 fair-opponent block, and at this head that block is
**`README.md:263-342`**, measured here with `grep -n '^### ' README.md` and **unchanged** from critic #54
because the window's nine added README lines all landed below it. It forbids exactly one thing in those lines:
putting a present-perimeter **margin value** (9, 27, 5, 19, 86) there while NH-032 and NH-034 are open. Both
re-read: both still `open`, both stated due **2026-09-08**, so two days past. A scan of 263-342 finds **zero**
occurrences of any of the five. **It expires at critic #56 unless that lap re-states it after re-checking, and
that lap re-measures the bounds rather than copying this line.** It freezes no file and no question.
