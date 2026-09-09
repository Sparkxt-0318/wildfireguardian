# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine; updated 2026-09-09T2023Z by critic #53 (CHARTER §14).
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

Table order at `ba06467`, **after this lap's one §3b reorder**. There is **no `fix-before-next-row` item this
lap** — §14b caps them at one, it does not require one, and the top of the table can be run straight through.

1. **WFG-212 (P0, KCF). ⚠ THIS LAP'S ONE §3b REORDER PUT IT BACK ABOVE WFG-214, and the reason is below.**
   `README.md:220-299` carries 11 ⚠ markers and 28 negative-framing tokens against one affirmative-outcome
   token, and that one favours the opponent. 「자료의 논리적 구성」, 20 points on both tables. ⚠ Not a request
   to soften anything: the fix **adds** a lead paragraph and removes no caveat.

2. **WFG-214 (P0, KCF), three of four surfaces closed and the fourth cannot be moved by a dev lap.**
   `README.md:36`, `:266-284` and `:715-723` now state the mechanism and all three link `docs/oracle_gap.md`.
   What is left is one link in `paper/manuscript.md`, and `paper/check_paper.py` reads **8,999** body words
   against a 9,000 hard fail (re-run at this head, exit 0), so the link costs a caveat, which CHARTER §3 rule 5
   forbids. That is **NH-037**, open, due 2026-09-10, and `paper/` is the paper routine's file (CHARTER §12).
   ⚠ It may **not** settle the word 「상한」; that is **NH-053**.

3. **WFG-218 (P0, KCF) and WFG-220 (P0, KCF), and a lap that takes one should take both.** 일정 counts **0** on
   `README.md` and **0** on `web/finals.html` (WFG-218). And `web/finals.html` — five judges, ten minutes each,
   offline — is the only judge-facing surface carrying no word of the objection this repository corrected
   everywhere else today (WFG-220; 채점 0, 오라클 0, `oracle_gap` 0 on both the built screen and its template).
   Both need `make finals` on a commit already on `origin` and a re-pointed `release/kcf-finals-2026/MANIFEST.json`
   after staging; **that mechanic is paid once if the two ship together.**

Behind those: WFG-213 is `blocked(NH-052)`. Then the P1 band. **Fifteen P0 rows `todo`, six sprint days**,
counted here at this head rather than inherited.

### Why the reorder, in one paragraph

Critic #52 moved WFG-214 above WFG-212 so the mechanism was corrected before a lead paragraph was written over
the same lines. **That reason is discharged** — the 1817Z lap corrected all three README lines. What is left of
WFG-214 is one link in a file the paper routine owns, blocked by an open NH-037, so a dev lap that claims the
top row today can do nothing with it. WFG-212 it can move. Both rows are P0, so no P0 row falls below a non-P0
row, and the reorder simply hands the top of the table back to the row that is actually runnable.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- ⚠ **CORRECTED THIS LAP, MEASURED, AND NARROWER THAN IT WAS WRITTEN: `data/processed/timeline_roles/timeline_roles.json`
  may be rebuilt from a FRESH full clone, and may not be rebuilt from a clone you deepened.** In a fresh clone of
  the repository at `ba06467` (673 commits, `--is-shallow-repository` false, 12,393 packed objects, all 13 origin
  branches fetched) `%h` is **7** characters and `build_timeline_roles.py --check` exits **0**. The eight-character
  anchors that turn GitHub red are produced by `git fetch --unshallow` on an already-shallow clone, which leaves a
  bloated object store; `git gc --prune=now` cures it. **WFG-217** is still the right fix and is still P1.
- **Do not file a judge-facing critic finding at table position 1 while NH-051 is open.** NH-038's own option
  B puts it 「in the table like any other」; 「at position 1」 is option **D**'s mechanic.
- **Do not settle the word 「상한」 / 「upper bound」 in any lap.** It is a claim about a judged headline
  number, nothing in the tree derives it, and NH-053 is open. Describe the mechanism; leave the word alone
  and point at NH-053.
- **Do not put a margin value (9, 27, 5, 19, 86) on any judge-facing surface** while NH-032, NH-034 and
  NH-052 are open, and not in `README.md:220-299` at all (the `Do NOT edit` note in `CRITIC_LATEST.md`).
- **Do not refit anything.** Every headline number is downstream of the fitted `spread_v2` model and
  CHARTER §3 rule 2 forbids regenerating a committed artifact.
- **Do not add documents to the release bundle.** WFG-208 closed with one sentence and a URL, which is the
  shape that fix takes; adding payload widens the freeze. ⚠ WFG-220 obeys this: it adds **one card to an
  existing panel** on a screen already in the bundle, not a new file.
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13–§14).
- **Do not compare accuracy with NIFoS or G-DAPS.** Their figures are agency statements with no published
  metric definition; the differentiator is the output object.
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or
  `docs/NUMBERS.json`** (CHARTER §13, §3 rule 5b).

## Readiness lines ticked in the last 24 h: ZERO, for the tenth consecutive critic lap

`docs/auto/KCF_READINESS.md` stands at **8 of 11** and has stood there since critic #43 ticked R8 at
2026-09-08T1429Z. The cause was measured by critic #50 and I re-read it rather than restating it: R12 is the
author's (NH-014); R3 is `blocked(NH-046)`; and R11's row **WFG-024** is held by CHARTER §14b as loop hygiene,
released only when R1, R3, R4, R7, R8 and R9 all tick, of which **R3 is the only one unticked**. Both remaining
agent-reachable lines are downstream of **one unanswered question, NH-046**, which comes due **2026-09-10**,
tomorrow. Nothing a lap can do moves the count, and no fourteenth question is filed because filing one would be
the loop asking itself.

## Critic's last direction note

**2026-09-09T2023Z, critic #53. ONE §3b reorder (WFG-212 back above WFG-214, both P0). ZERO `fix-before-next-row`
items, deliberately — nothing found is minutes. ONE new row (WFG-220, P0, at the end of the P0 block). ONE existing
row re-measured and NARROWED (WFG-217). ZERO new NEEDS_HUMAN entries. Scorecard: Track B 93 → 94, Track A 92 → 93,
one row on each and it is the same row, 제출 자료, restored.**

Verified at `ba06467`. `gates.py --mode full` exits **0** (1862 passed, 64 skipped, 3 xfailed, pytest 383.2 s);
`baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029 and §3d working;
`--assert-head` exits 0. **GitHub `auto-gates`, runs 279 to 299: no `failure` anywhere in the window, two
`cancelled` (278, 284) each superseded by the next push, and 299 green at this exact head — so CHARTER §4b sets
no finding #1.** Every dev report in the window records `Reviewed by:`. `factchk`: the window's added prose
contains no new external URL and no new citation; every claim in it is about this repository's own git history
or its own committed arrays, and the two I re-derived independently in a full clone (673 commits, 42 active days)
agree with the artifact's as-of stamp.

**The root objection: `web/finals.html` is the one judge-facing surface with no word of the oracle objection, and
the one place it says 「LOFO」 is the card that uses the leave-one-fire-out design to show the model is good.**
Full statement in `CRITIC_LATEST.md`; the row is **WFG-220**.

⚠ **The one `Do NOT edit` note, RE-STATED after re-checking its premise AND after re-measuring its bounds, which
had gone stale (CHARTER §14c as this routine's prompt states it, NH-036 A).** It covers the Round-4 fair-opponent
block, and at this head that block is **`README.md:220-299`**, not the 210-282 critics #49 to #52 wrote: WFG-214
added ten lines inside it, so `## Round 4` moved 200 → 210, 「### 1.」 210 → **220** and 「### 2.」 283 → **300**.
It forbids exactly one thing in those lines: putting a present-perimeter **margin value** (9, 27, 5, 19, 86)
there while NH-032 and NH-034 are open. Both re-read: both still `open`, both stated due **2026-09-08**, so one
day past. A scan of 220-299 finds **zero** occurrences of any of the five values.
**It expires at critic #54 unless that lap re-states it after re-reading them, and that lap must re-measure the
bounds before quoting them.** It freezes no file and no question.
