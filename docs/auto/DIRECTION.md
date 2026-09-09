# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine; updated 2026-09-09T1719Z by critic #52 (CHARTER §14).
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

Table order at `375be25`, **after this lap's one §3b reorder**. WFG-027 closed, so the top of the P0 block
turned over completely this window.

0. **First, the `fix-before-next-row` item in `CRITIC_LATEST.md`, which is prose only.**
   `docs/auto/finals/TIMELINE_ROLES.md` shipped six hours ago and says two things about itself that are not
   true at this head: that its phase boundaries were not chosen (the builder hard-codes all five, and skips a
   six-day gap while splitting on a one-day one), and that the trailer count is 513 of 662 (it is 517 of 666).
   Both are minutes of prose plus `make printables`. ⚠ **The item forbids rebuilding the artifact**, because
   that trips WFG-217.

1. **WFG-214 (P0, KCF). ⚠ THIS LAP'S ONE §3b REORDER MOVED IT ABOVE WFG-212, and the reason is below.**
   `README.md:36`, `:266-267` and `:702` still tell every reader that 42 is 「완벽한 예보 / a noiseless
   forecast」's value, and this repository's own `docs/oracle_gap.md` establishes that the arm plans on a
   leave-one-fire-out model output and is graded on that same array. Two of the row's five surfaces closed
   this window without a lap being told to (Q36 by the dev lap, the manuscript's mechanism by paper lap 24),
   so the row is now three README lines and one link. ⚠ It may **not** settle the word 「상한」; that is **NH-053**.

2. **WFG-212 (P0, KCF), filed by critic #50 and untouched.** `README.md:200-362` carries 11 ⚠ markers and 28
   negative-framing tokens against one affirmative-outcome token, and that one favours the opponent.
   「자료의 논리적 구성」, 20 points on both tables. ⚠ Not a request to soften anything: the fix **adds** a
   lead paragraph and removes no caveat.

3. **WFG-218 (P0, KCF), filed by this lap at the end of the P0 block.** 일정 counts **0** on `README.md` and
   **0** on `web/finals.html`. It is WFG-027's own disclosed residue, refiled because residue written into a
   **`done`** cell is invisible to CHARTER §4 step 3 and no lap would ever have taken it.

Behind those: WFG-213 is `blocked(NH-052)`. Then the P1 band, where **WFG-217** (the schedule gate that
measures the clone) sits behind WFG-215 and WFG-216. **Fourteen P0 rows `todo`, six sprint days**, counted
here at this head rather than inherited.

### Why the reorder, in one paragraph

WFG-214 and WFG-212 both edit `README.md`'s Round-4 material, and `README.md:266-267` is inside the block
WFG-212 is about. Writing an affirmative lead paragraph over a section whose body still describes the
mechanism wrongly means writing that section twice, and the second pass would have to re-open the first.
There is also a live contradiction to remove: `DIRECTION.md` listed WFG-214 second and WFG-212 third while
the **table** had WFG-212 at row 19 and WFG-214 at row 21, so 「table order」 and 「DIRECTION order」 named
different next rows, and the 1619Z dev report inherited the error verbatim (「WFG-214 sits above it in table
order」). The reorder makes both orders name the same row. Both are P0, so no P0 row falls below a non-P0 row.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- **Do not rebuild `data/processed/timeline_roles/timeline_roles.json`** until WFG-217 is fixed. In this
  sandbox the rebuild writes eight-character anchors and turns **GitHub** red on a tracked artifact.
- **Do not file a judge-facing critic finding at table position 1 while NH-051 is open.** NH-038's own option
  B puts it 「in the table like any other」; 「at position 1」 is option **D**'s mechanic.
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

## Readiness lines ticked in the last 24 h: ZERO, for the ninth consecutive critic lap

`docs/auto/KCF_READINESS.md` stands at **8 of 11** and has stood there since critic #43 ticked R8 at
2026-09-08T1429Z. Critic #50 measured the cause and I re-read it rather than restating it: R12 is the
author's (NH-014); R3 is `blocked(NH-046)`; and R11's row **WFG-024** is held by CHARTER §14b as loop hygiene,
released only when R1, R3, R4, R7, R8 and R9 all tick, of which **R3 is the only one unticked**. Both
remaining agent-reachable lines are downstream of **one unanswered question, NH-046**, whose recommendation
the loop has now stated five times. Nothing a lap can do moves the count. ⚠ Critic #51 did not touch the
page at all, so its tick header named critic #50 until this lap refreshed it.

## Critic's last direction note

**2026-09-09T1719Z, critic #52. ONE §3b reorder (WFG-214 above WFG-212, both P0). ONE `fix-before-next-row`
item, prose only, on the schedule document. TWO new rows (WFG-218 P0, WFG-217 P1), both in table order. ONE
existing row re-measured and shrunk (WFG-214). ZERO new NEEDS_HUMAN entries, deliberately.**

Verified at `375be25`. The clone opened **SHALLOW at 50**; I deepened it by the window predicate to 101 and
then with `--unshallow` to **666**, so `--is-shallow-repository` answers **false** and this lap's re-derivation
claims are licensed. `gates.py --mode full` exits **0** (1850 passed, 64 skipped, 3 xfailed, pytest 263.3 s);
`baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029 and §3d working.
`--assert-head` exits 0. **GitHub `auto-gates`, runs 255 to 294: two `failure` (255, 260), both inside critic
#50's window and both closed by `wfg-autoloop-ci-red` within the hour; three `cancelled`, each superseded by
the next push; and the five runs since critic #51 (290 to 294) all `success`, with 294 green at this exact
head. No new red run, so §4b sets no finding #1.** `factchk` had nothing new to check: the window's added
markdown contains no new external URL and no new citation.

**The root objection: the one gate that binds the schedule document to the history it reports measures the
clone rather than the tree, and gave four answers on four clone states of one tree today.**
`build_timeline_roles.py` resolves phase anchors with `%h`, whose width git derives from the clone's object
count. Shallow (as the sandbox opens) it exits 2 and the test skips. After `--unshallow`, at 20,641 packed
objects, `%h` is eight characters, `--check` exits 1 with `STALE timeline artifact: phase starts or anchor
commits`, and `gates.py --mode full` went **RED** on this lap's own commit `a53912d0`. Deleting the four
unrelated remote-tracking refs and running `git gc --prune=now` took the clone to 12,052 objects with not one
commit reachable from `HEAD` changed; `%h` is seven characters again and `--check` exits 0. GitHub run 294's
own log reads `1851 passed, 63 skipped`, so the test ran and passed there. **What decides the verdict of a
gate about this project's schedule is which other branches are in the clone.** The obvious repair is to
rebuild the artifact, which would commit eight-character anchors and turn GitHub red instead. ⚠ **The lap that shipped
this is the strongest 설계와 방법론 work of the sprint** and the defect is narrow: it is CHARTER §4's
clone-shape failure class arriving through abbreviation **width** instead of clone **depth**, which is why
its own docstring, written about depth, did not see it. **WFG-217**, and until it lands nobody rebuilds that
artifact.

⚠ **The one `Do NOT edit` note, RE-STATED after re-checking its premise (CHARTER §14c as the routine prompt
states it, NH-036 A; ⚠ a search for `14c` in `docs/auto/CHARTER.md` still answers **0** at this head, and
NH-036, NH-038 and NH-051 are all still `open`).** It covers **`README.md:210-282`**, the Round-4
fair-opponent block, whose bounds this lap re-measured (「### 1.」 at **210**, 「### 2.」 at **283**), unchanged
from critics #49, #50 and #51. It forbids exactly one thing in those lines: putting a present-perimeter
**margin value** (9, 27, 5, 19, 86) there while NH-032 and NH-034 are open. Both re-read at
`NEEDS_HUMAN.md:1391` and `:1574`: both still `open`, both due 2026-09-08, so **one day past** (critic #51
wrote 「two days」, which the calendar does not support). A scan of 210-282 finds no margin value there today.
**It expires at critic #53 unless that lap re-states it after re-reading them.** It freezes no file and no
question, and the edit it permits is named so nobody has to guess: **WFG-214's rewording of
`README.md:266-267` is inside these lines and is allowed**, because 「완벽한 예보」 is not a margin value.
