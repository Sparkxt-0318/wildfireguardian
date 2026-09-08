# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine, updated 2026-09-08T2000Z by critic #45 (CHARTER §14). The dev routine reads this before claiming a row; the critic re-checks it after every dev lap, at most one reorder per lap, with a reason. The previous version of this page had grown to **54,923 bytes** — roughly forty screens of stacked superseded leads and eight critic notes — which is a straight breach of the "one screen, never longer" rule it opens with, and it is archived verbatim (nothing deleted, CHARTER §3.7) at `docs/auto/archive/DIRECTION_superseded_2026-09-08T1817Z.md`. Only the most recent critic note is kept below, as §14 specifies.*

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a per-household walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive. Its defensible contribution is not forecast accuracy — Korea's own agencies forecast spread better resourced than we can — but the **output object**: a household-level, time-dependent decision with its limits measured and written down.

## Next three rows, and why each is next

Table order at `9c24a8b` after critic #45. **No P0 row was moved below a non-P0 row; the one move
this lap made was WFG-125 P1 to P0, upward, from table line 97 to line 49.**

0. **WFG-199 (P0, KCF)** — critic #45's one `fix-before-next-row` item, and it is one command.
   `make finals` before you claim: the judged screen's stamp is **22** commits behind against a
   limit of 30, up from 16 three hours earlier, and the lap after next trips the assert on its
   claim commit alone. That is NH-045 replaying.
1. **WFG-127 (P0, KCF)** — unchanged from critic #44 and still not done, because no dev lap ran in
   the window (the 1817Z slot was ceded to research). `README.md:232` still asserts
   「고원이 아니라 뾰족한 봉우리」, which the Q&A bank forbids the student to say and the booth
   script disclaims out loud.
2. **WFG-194 (P0, KCF)** — 창의성 is 20 points on both tables, is named first in the 심사기준, and
   is at **0** on `web/finals.html`, `DEMO_SCRIPT_5MIN.md` and the bundle README. Critic #45 adds
   that `docs/creativity_card.md` exists and is **not in the printed kit**.
3. **WFG-125 (P0, science)** — this lap's one move, and the reason is a measurement.
   `data/processed/spread_v2_lofo_oof_cells.csv.gz` already holds the shipped model's
   leave-one-fire-out out-of-fold per-cell probabilities for both routing regions (20,749 Yeongdeok
   cells, 82,736 Uiseong-Andong), so the experiment that turns Q36 — a **T0** card whose answer is
   today 「맞습니다」 and nothing measured — into a number needs routing only, no retrain and no
   re-acquisition. The cost written into the row was wrong.

Behind those, the P0 block: WFG-007, WFG-117, WFG-121, WFG-128, WFG-129, WFG-106, WFG-036, WFG-101,
WFG-119, WFG-054. **Thirteen P0 rows, seven sprint days.** That ratio is still the single most
important fact on this page, and this lap made it worse by one on purpose.

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

**2026-09-08T2000Z, critic #45. ONE reorder, spent UPWARD on a row whose cost turned out to be
wrong; ONE `fix-before-next-row` item and it is one command; one new P0 row; three rows updated;
no new NEEDS_HUMAN entry.**

Verified at `9c24a8b` on the default clone before any deepening (`is-shallow-repository` = **true**,
`rev-list --count HEAD` = **50**, oldest resolvable `088203c` at 00:22Z, so this clone reads about
**19.6 hours** and claims no ancestry at all): `gates.py --mode full` is **ALL GREEN**, exit **0**
(1763 passed, 63 skipped, 2 xfailed, 322.5 s), both asserts exit 0, and **GitHub agrees for the
first time this week** — runs 240-257 are 16 `success` and 2 `failure`, both failures closed
(253's `upload-artifact` 403 by WFG-193, 255's browser-launch CDPError by `298a09c`), run 257 green
at this head, and `Main` is back to following at `9c24a8b`.

**The root objection: the project's own front door now says its headline number is a bound its model
does not reach, and the experiment that would replace the bound with a number is the row nobody
prioritised — while the material that experiment needs has been committed here the whole time.**
`docs/auto/JUDGE_QA.md:1393` files this as **Q36 · T0**, the tier whose header says an unanswerable
card costs you that judge, and today's answer is 「맞습니다」 followed by nothing measured. That is
WFG-125, and it is now P0 at position 3.

⚠ **Standing observation, and it replaces three laps' worth of repeated reorders.** The head of the
`todo` block returns to a P1 infra row after every P0 row closes, and the mechanism is not that the
moves were wrong: **new rows are inserted near the top of the table, so a new P1 row is born above
the P0 block.** At `9c24a8b` before this lap's edits, WFG-189/191/192 sat at lines 49-51 and
WFG-196/197/198 — all filed in the last 24 h, all P1 — at lines 53-55, above six P0 `todo` rows. The
gate WFG-183 and WFG-191 ask for must therefore check **order**, not only **shape**.

**Next critic lap's reorder candidate, so it need not re-derive the measurement: WFG-027.**
설계와 방법론 (20 points, both tables) names 「일정 및 팀원(개인의 경우 제외) 역할 배분의
타당성」; for an individual entry the 팀원 half is excluded and the 일정 half is not, and 일정 is at
**zero** on the Q&A bank, the demo script, the finals screen and the bundle README. The row is P1
and estimates hours. This lap did not move it, because raising a priority without moving the
position is the defect critic #42 recorded against critic #41.

⚠ **The one `Do NOT edit` note is RE-STATED and NARROWED** (CHARTER §14c, NH-036 A): it lives in
`CRITIC_LATEST.md`, covers `README.md:220-239` only, forbids **present-perimeter margin values (9,
27, 5, 19, 86)** while NH-032 and NH-034 are open — both re-read at `:1391` and `:1524`, both still
`open`, both due **today**, not overdue as critic #44 wrote — and it expires at critic #46. **42 and
91 are removed from it**: those twenty lines are required by this page to state the 42 with its two
caveats, and they do. It does **not** freeze `README.md:232`, which WFG-127 must edit.
