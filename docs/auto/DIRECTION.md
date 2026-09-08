# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine (CHARTER §14). The dev routine reads this before claiming a row; the critic re-checks it after every dev lap, at most one reorder per lap, with a reason. The previous version of this page had grown to **54,923 bytes** — roughly forty screens of stacked superseded leads and eight critic notes — which is a straight breach of the "one screen, never longer" rule it opens with, and it is archived verbatim (nothing deleted, CHARTER §3.7) at `docs/auto/archive/DIRECTION_superseded_2026-09-08T1817Z.md`. Only the most recent critic note is kept below, as §14 specifies.*

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a per-household walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive. Its defensible contribution is not forecast accuracy — Korea's own agencies forecast spread better resourced than we can — but the **output object**: a household-level, time-dependent decision with its limits measured and written down.

## Next three rows, and why each is next

Table order at `298a09c` after this run. **No P0 row was moved below a non-P0 row; this run reordered nothing.**

1. **WFG-193 (P0, infra)** — critic #44's one `fix-before-next-row` item and a **red GitHub run at the current head**. CHARTER §14b names a red gate explicitly. Nothing else starts while `auto-gates` is red and `Main` is not following.
2. **WFG-127 (P0, KCF)** — the claim `README.md:232` makes (「고원이 아니라 뾰족한 봉우리」) is the one a five-point grid cannot support, and the Q&A bank tells the student not to make it. It is on the front door, it is a claim drifting *stronger*, and the fix is a grep away.
3. **WFG-194 (P0, KCF)** — 창의성 is on the Q&A bank and at zero on `web/finals.html` and `DEMO_SCRIPT_5MIN.md`, the two surfaces a judge actually stands in front of.

Behind those, the P0 block: WFG-007, WFG-117, WFG-121, WFG-128, WFG-129, WFG-106, WFG-036, WFG-101, WFG-119, WFG-054. **Twelve P0 rows, seven sprint days.** That ratio is the single most important fact on this page.

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

**2026-09-08T1700Z, critic #44. ONE reorder, spent on a rule violation for the third time; ONE `fix-before-next-row` item, and it is a red gate; one new P0 row; two rows updated.**

Verified at `0cca093` on the default clone before deepening (`is-shallow-repository` = **true**, `rev-list --count HEAD` = **54**, oldest resolvable `6d1d730`; so this clone reads about 22 hours and claims nothing older and no ancestry at all): `gates.py --mode full` is **ALL GREEN**, exit **0** (1763 passed, 63 skipped, 2 xfailed), the run downloaded nothing, and both asserts exit 0.

**And GitHub does not agree, for the first time this week.** `auto-gates` run **253** at that head is **`failure`** while its own log prints `ALL GREEN`: the gate step passed, the step filing the gate's record 403'd, `promote` needs the job, so `Main` sat at `6ecc386`. Finding #1 and the one item. It is **not** a test failure, not a suite flake, and not a sandbox/runner difference — both machines agree the code is green. What disagreed was the artifact store, and the workflow let it speak for the gate.

**The root objection: the loop has one mechanism for a claim drifting weaker and none for a claim drifting stronger, and this window it drifted stronger onto the front door.** The lap acting on WFG-192 fixed both sentences it was given and in the same paragraph wrote `README.md:232`, the assertion WFG-127 has been saying the five-point grid cannot support. The gate for that exact claim exists, bans the English spelling, and the Korean one walked past it.

⚠ **The one `Do NOT edit` note is RE-STATED, not inherited** (CHARTER §14c, NH-036 A): it lives in `CRITIC_LATEST.md`, covers `README.md:220-239` only, forbids one thing (a margin value while NH-032 and NH-034 are open), and expires at critic #45 unless that lap re-checks both entries. It does **not** freeze `README.md:232`, which WFG-127 must edit.
