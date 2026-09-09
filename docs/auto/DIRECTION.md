# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine; updated 2026-09-09T2319Z by critic #54 (CHARTER §14).
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

Table order at `3eec471`, after this lap's **zero** §3b reorders. There **is** one `fix-before-next-row` item
this lap and it is three lines in the Q&A bank: `CRITIC_LATEST.md` states it, and it is minutes.

0. **The `fix-before-next-row` item first.** `docs/auto/JUDGE_QA.md:609`, `:1159` and `:1377` tell the student
   that an answer from the 운영사무국 is still awaited; the author closed that on **2026-09-04** (NH-008), and
   `:1377` goes further and says a query **was submitted**, which NH-008's own resolution says was never sent.
   Q29 is **T0**, spoken from memory, and the bank is printed in the booth kit.

1. **WFG-218 (P0, KCF) and WFG-220 (P0, KCF) and WFG-222 (P0, KCF) — a lap that takes one should take all
   three.** 일정 counts **0** on `README.md` and **0** on `web/finals.html` (WFG-218). `web/finals.html` is the
   only judge-facing surface carrying no word of the oracle objection this repository corrected everywhere else
   earlier today (WFG-220). And WFG-222 is this lap's root objection, below. All three need `make finals` on a
   commit already on `origin` and a re-pointed `release/kcf-finals-2026/MANIFEST.json` after staging;
   **that mechanic is paid once if they ship together**, and WFG-222 adds a printables rebuild that WFG-218's
   and WFG-220's own edits would want anyway.

2. **WFG-222 (P0, KCF) is the one to write first inside that group**, because it is the only one of the three
   that is a **correction** rather than an addition: the front door said 지점 단위 with its bounds at 2206Z
   this evening and four other surfaces still say 가구 단위 with none. Adding a card to a screen that states the
   wrong thing about the project's one affirmative claim is work done twice.

3. **Behind those: the P1 band.** WFG-213 is `blocked(NH-052)`. **Fourteen P0 rows `todo`, six sprint days**,
   counted here at this head rather than inherited: WFG-218, 220, 222, 007, 117, 128, 129, 121, 106, 036, 101,
   119, 024, 054. One closed and one filed this lap, so the count is unchanged.

### Why zero reorders, in one paragraph

WFG-214 stood `todo` at table position 1 with no work left in it: critic #53 re-measured it down to one link in
`paper/manuscript.md`, and paper lap 25 (`4f3bd85`) added that link at 2126Z. The paper routine may not touch
`docs/auto/` beyond its own report (CHARTER §12), so no lap could close the row. I closed it on the
measurement — `grep -c oracle_gap paper/manuscript.md` answers 1 at this head — which is a **status update, not
a position change**, and §3b limits position changes. Closing it hands the top of the table to WFG-218, which a
dev lap can run today. A reorder would buy nothing, so none was spent.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- ⚠ **Do not write 「가구 단위」 or "per-household" on any judge-facing surface about the COMMITTED dispatch
  sheets.** `data/processed/rescue_routing.json` → `provenance.sources` reads `hazard: synthetic`,
  `terrain: synthetic`, `origins: sampled candidates`. The word for the committed instances is **지점 단위**,
  with the bound in the same block. That is WFG-222 and `README.md:212-251` is the model to copy.
- ⚠ **`data/processed/timeline_roles/timeline_roles.json` may be rebuilt from a FRESH full clone, and may not
  be rebuilt from a clone you deepened.** Critic #53 measured it in a fresh clone at `ba06467` (673 commits,
  `--is-shallow-repository` false, 12,393 packed objects): `%h` is **7** characters and
  `build_timeline_roles.py --check` exits **0**. The eight-character anchors that turn GitHub red come from
  `git fetch --unshallow` on an already-shallow clone, which leaves a bloated object store;
  `git gc --prune=now` cures it. **WFG-217** is still the right fix and is still P1.
- **Do not file a judge-facing critic finding at table position 1 while NH-051 is open.** NH-038's own option
  B puts it 「in the table like any other」; 「at position 1」 is option **D**'s mechanic. WFG-222 obeys this.
- **Do not settle the word 「상한」 / 「upper bound」 in any lap.** It is a claim about a judged headline
  number, nothing in the tree derives it, and NH-053 is open. Describe the mechanism; leave the word alone
  and point at NH-053.
- **Do not put a margin value (9, 27, 5, 19, 86) on any judge-facing surface** while NH-032, NH-034 and
  NH-052 are open, and not in `README.md:263-342` at all (the `Do NOT edit` note in `CRITIC_LATEST.md`, whose
  bounds moved this lap because WFG-212 inserted 43 lines above that block).
- ⚠ **Do not add a word to `paper/manuscript.md`.** `check_paper.py` reads **9,000** body words against a
  9,000 hard fail at this head: the margin is **zero**. NH-037 is open and due **2026-09-10**.
- **Do not refit anything.** Every headline number is downstream of the fitted `spread_v2` model and
  CHARTER §3 rule 2 forbids regenerating a committed artifact.
- **Do not add documents to the release bundle.** WFG-222 corrects text on files already in it; it adds none.
- **Do not re-open the AI-disclosure question.** NH-008 is closed and CHARTER §9 states what the project keeps
  voluntarily. The `fix-before-next-row` item makes the bank agree with that record; it does not restate it.
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13–§14).
- **Do not compare accuracy with NIFoS or G-DAPS.** Their figures are agency statements with no published
  metric definition; the differentiator is the output object.
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or
  `docs/NUMBERS.json`** (CHARTER §13, §3 rule 5b).

## Readiness lines ticked in the last 24 h: ZERO, for the eleventh consecutive critic lap

`docs/auto/KCF_READINESS.md` stands at **8 of 11** and has stood there since critic #43 ticked R8 at
2026-09-08T1429Z. The cause was measured by critic #50 and re-read rather than restated: R12 is the author's
(NH-014); R3 is `blocked(NH-046)`; and R11's row **WFG-024** is held by CHARTER §14b as loop hygiene, released
only when R1, R3, R4, R7, R8 and R9 all tick, of which **R3 is the only one unticked**. Both remaining
agent-reachable lines are downstream of **one unanswered question, NH-046**, which comes due **2026-09-10**,
tomorrow. Nothing a lap can do moves the count, and no fourteenth question is filed because filing one would be
the loop asking itself.

## Critic's last direction note

**2026-09-09T2319Z, critic #54. ZERO §3b reorders, deliberately. ONE `fix-before-next-row` item (three lines in
`docs/auto/JUDGE_QA.md`, minutes, and one of them is false rather than stale). ONE new row (WFG-222, P0, at the
end of the P0 block). ONE existing row closed on a measurement (WFG-214 → `done(4f3bd85)`). ZERO new
NEEDS_HUMAN entries; NH-037 updated with a zero-word margin. Scorecard: Track B 94 → 93, Track A 93 → 92, one
row on each and it is the same row, 제출 자료, down.**

Verified at `3eec471`. `gates.py --mode full` exits **0** (1871 passed, 64 skipped, 3 xfailed, pytest 333.2 s);
`baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029 and §3d working;
`--assert-head` and `--assert-reported --base ba06467` both exit 0. **GitHub `auto-gates`, runs 262 to 305: no
`failure` anywhere in the window, three `cancelled` (275, 278, 284) each superseded by the next push, and 305
green at this exact head — so CHARTER §4b sets no finding #1.** Every dev report in the window records
`Reviewed by:`. `factchk`: the window adds no external URL and no citation; its only world claims are about
this repository's own artifacts, and the two load-bearing ones re-derive from `rescue_routing.json` and
`outputs/dispatch/README.md`.

**The root objection: the lap that corrected the front door's one affirmative claim left the identical claim,
in the identical words, on the screen five judges stand in front of, on the card the student says out loud from
memory, on the spoken script, and in the printed kit — and the gate it wrote to prevent that reads only the
paragraph it fixed.** Full statement in `CRITIC_LATEST.md`; the row is **WFG-222**.

⚠ **The one `Do NOT edit` note, RE-STATED after re-reading NH-032 and NH-034 and after RE-MEASURING its bounds,
which had gone stale again (CHARTER §14c as this routine's prompt states it, NH-036 A).** It covers the Round-4
fair-opponent block, and at this head that block is **`README.md:263-342`**, not the 220-299 critic #53 wrote:
WFG-212 inserted 43 net lines above it, so 「### 1.」 moved 220 → **263** and 「### 2.」 300 → **343**. It
forbids exactly one thing in those lines: putting a present-perimeter **margin value** (9, 27, 5, 19, 86) there
while NH-032 and NH-034 are open. Both re-read: both still `open`, both stated due **2026-09-08**, so two days
past. A scan of 263-342 finds **zero** occurrences of any of the five. **It expires at critic #55 unless that
lap re-states it after re-reading them, and that lap must re-measure the bounds before quoting them — they have
gone stale twice in three laps.** It freezes no file and no question.
