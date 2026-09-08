# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine, updated 2026-09-08T2340Z by critic #46 (CHARTER §14). The dev routine reads this before claiming a row; the critic re-checks it after every dev lap, at most one reorder per lap, with a reason. The previous version of this page had grown to **54,923 bytes** — roughly forty screens of stacked superseded leads and eight critic notes — which is a straight breach of the "one screen, never longer" rule it opens with, and it is archived verbatim (nothing deleted, CHARTER §3.7) at `docs/auto/archive/DIRECTION_superseded_2026-09-08T1817Z.md`. Only the most recent critic note is kept below, as §14 specifies.*

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a per-household walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive. Its defensible contribution is not forecast accuracy — Korea's own agencies forecast spread better resourced than we can — but the **output object**: a household-level, time-dependent decision with its limits measured and written down.

## Next three rows, and why each is next

Table order at `cb9fcc3` after critic #46. **No P0 row was moved below a non-P0 row. This lap spent NO
§3b reorder and set NO `fix-before-next-row` item; its one table change is a new P0 row at position 1
(WFG-201), which CHARTER §14b as amended by NH-038 B says is never a preemption.**

1. **WFG-201 (P0, KCF)** — new, and it is the root objection of critic #46. The fair opponent's buffer
   width is chosen **after the fact by scanning outcomes**, so the reported margin is a **maximum over a
   grid** and is **non-increasing in how finely anyone searches**. Measured today by this repository:
   `9170a37` added three widths to a five-point grid and the margin went from **9** origins to **5**.
   `docs/present_perimeter_buffer_shape.md` §4 states the neighbouring caveat and `README.md:245-247`
   says the rerun went against the project; **neither states the property**, and it is the easiest thing
   a statistician judge can take from this project. Prose only, no run, all eight widths committed.
2. **WFG-194 (P0, KCF)** — 창의성 is 20 points on both tables, is named first in the 심사기준, and is
   still at **0** on `web/finals.html` and `DEMO_SCRIPT_5MIN.md`, re-measured at this head.
   `docs/creativity_card.md` is referenced nowhere under `release/` or `scripts/`, so it is in no printed
   kit. It is a missing topic where WFG-201 is a live wrongness, which is the only reason it is second.
3. **WFG-125 (P0, science)** — unchanged and still the cheapest real measurement available:
   `data/processed/spread_v2_lofo_oof_cells.csv.gz` already holds the shipped model's out-of-fold
   per-cell probabilities for both routing regions. ⚠ **This window raised its value.** The new
   buffer-shape document's own §4 ends 「every margin here is what a **noiseless** forecast would buy ...
   That difference is still unmeasured, and it is what WFG-125 exists for」 — so the project has now
   written, on a page a judge can open, that its headline comparison measures a bound its model does not
   reach. WFG-201 makes that bound shrink on refinement. The two together are the whole fair-opponent
   story and this row is the half nobody has run.

Behind those, the P0 block: WFG-007, WFG-117, WFG-128, WFG-129, WFG-121, WFG-106, WFG-036, WFG-101,
WFG-119, WFG-054. **Thirteen P0 rows `todo`, seven sprint days.** That ratio is still the single most
important fact on this page. This lap added one and **declined to add a second** (WFG-197, the missing
horizon card, kept at P1 with the measurement written onto the row) for exactly that reason. The
decision that would resolve it is **NH-038, due 2026-09-09**.

## What not to do

- **Do not start a P1 infra row while a P0 row is `todo`.** CHARTER §14b holds loop hygiene — report certification, gate-on-gate, commit-id bookkeeping — behind the readiness lines. This has been the critic's reorder three times in five laps; the cure is WFG-183/WFG-191's class (a gate on the table's own shape), not a fourth manual move.
- **Do not refit anything.** Every headline number is downstream of the fitted `spread_v2` model, and CHARTER §3 rule 2 forbids regenerating a committed artifact. This run parked a genuinely good feature idea (**P-003**, multi-timescale drought windows) for exactly this reason.
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13–§14: investigated and deliberately stopped). Not re-proposed this run.
- **Do not compare accuracy with NIFoS or G-DAPS.** Their figures are agency plan statements with no metric definition; the differentiator is the output object. Two research runs have now confirmed no comparable metric is public.
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or `docs/NUMBERS.json`** (CHARTER §13, §3 rule 5b). The new 8 h / 5 h / 76 % / 88 % / 30 % figures stay in `KOREAN_OPERATIONAL_SYSTEMS.md` with their agency, date and scope.

## The research lap's note (2026-09-08T1817Z)

Two rows filed, both **P1**, both prose-only, neither competing with the P0 block: **WFG-197** (anchor the 3–12 h horizon to Korea's Ready-Set-Go 8 h / 5 h elderly-evacuation decision points, with the ≈ 0.40 envelope figure and the two-clocks limit in the same card) and **WFG-198** (state route-existence as *time-dependent* severance against a published *static* severance method). One escalation: **NH-048**, one line on the routine page to replace a scan channel that has failed twice with one this run proved works.

The finding worth the author's attention is WFG-197's: **Korean national doctrine makes the elderly-evacuation decision at 8 hours and completes it at 5 hours before fire-line arrival, and this project's 3–12 h horizon contains both.** That converts the horizon from a data artifact into an operational choice — but it measures no sufficiency, and the card must say so.

## Critic's last direction note

**2026-09-08T2340Z, critic #46. NO §3b reorder; NO `fix-before-next-row` item, because nothing eligible is
red or minutes-scale; ONE new P0 row at position 1 (WFG-201); three rows updated; no new NEEDS_HUMAN entry,
and measurements appended to NH-032, NH-034 and NH-038.**

⚠ **This lap's own correction, first, because a direction page is where a wrong steer would do the most
damage.** I drafted this note against `7cfe29a` at 23:00Z and its headline was that the 21:17Z dev lap had
claimed WFG-199 and WFG-127 and died. The evidence at that head was real (a pushed claim, no work commit, no
report, 1 h 43 m elapsed) and **the inference was wrong**: the lap was slow, not dead, and it pushed
`9170a37` and closed both rows at about 23:20Z. Nothing carrying that finding was pushed. NH-035 already
records the 2026-09-05 lap that 「looked dead for 1 h 45 m and was only slow」; I quoted that sentence in the
draft and drew the opposite conclusion anyway. **Rule for the next critic: before writing that a lap failed,
`git fetch` again.**

Verified at `cb9fcc3` on the default clone before any deepening (`is-shallow-repository` = **true**,
`rev-list --count HEAD` = **55**, oldest resolvable `24f914f` at 03:21:30Z, about **20.3 hours**, no ancestry
claim): `gates.py --mode full` is **ALL GREEN**, exit **0** (1786 passed, 63 skipped, 2 xfailed, 346.6 s);
`auto-gates` runs 246-263 carry three `failure`s, all closed, with 262 and 263 green; `Main` follows at
`cb9fcc3`; the kit's six `SOURCES` all re-hash to the tree; the screen's stamp is **8** behind a limit of 30,
down from 27 three hours ago.

**The root objection: the project's headline margin is a maximum over a grid it keeps extending, and the one
document that proves this does not say so.** The fair opponent's width is picked post hoc by scanning
outcomes, so a new width can only tie or beat the incumbent and the margin can only hold or fall. The first
refinement ever run removed four of the nine origins. **Cheapest test, and the data is already committed:**
print the margin at all eight measured widths beside the headline and add one sentence saying refinement can
only move it one way. That is WFG-201.

**Is the next `todo` row still the highest-leverage one for 2026-10-24? It is now, after this lap's one
change, and no reorder was needed to get there.** WFG-201 enters at position 1 under §14b's own rule and
WFG-194 slides to 2. A live wrongness on the headline statistic outranks a missing topic, which is the same
principle this project applies everywhere else: lead with what you cannot do.

⚠ **Two candidates for the next critic lap, so it need not re-derive either.** **WFG-197** (the horizon card:
`grep -ciE 'Ready.?Set.?Go|화선|8시간'` is 0 on all three judge surfaces and no card of the 46 asks why the
horizon is 3 to 12 hours) is first, ahead of **WFG-027** (일정, still zero; the single `일정` hit in
`web/finals.html:70` is 「일정 크기 아래의」 and is not a schedule). Both are P1 and both need a **priority
change** rather than a §3b move, since neither can go above the P0 block without breaking the rule.

⚠ **The insertion-order defect is confirmed and unchanged in size:** **63 non-P0 `todo` rows sit above the
last P0 `todo` row** at this head, and `docs/auto/research/WEEKLY_2026-W37.md` §7 asserts 「the two new rows
enter at the end of the P1 block, which reorders nothing」, which is false as measured. WFG-191's gate must
check **order**, not only **shape**, and must be runnable so a lap can check a position instead of asserting
one.

⚠ **The one `Do NOT edit` note is RE-STATED with its range WIDENED to match the block that grew** (CHARTER
§14c, NH-036 A): it lives in `CRITIC_LATEST.md`, covers `README.md:220-247` only, forbids **present-perimeter
margin values (9, 27, 5, 19, 86)** in those lines while NH-032 and NH-034 are open (both re-read, both still
`open`, both due today), and expires at critic #47 unless that lap re-states it. **It freezes no question:**
WFG-201 must edit those very lines, and that edit is a sentence about how the number is chosen rather than a
margin value.
