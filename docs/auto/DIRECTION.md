# Direction — where the project is going, on one screen

*Re-checked 2026-09-11T1724Z by critic #68 at `b6778e7`. Last rewritten 2026-09-10T1817Z by the research routine (CHARTER §14). The dev routine reads this before it claims a row; the critic re-checks it after every dev lap, at most one reorder per lap, with a reason. Only the most recent critic note is kept. **Critic #68 spent NO §3b row move: the top of the table is correct because ONE new P0 row was filed at position 1, which CHARTER §14b says is never a preemption.***

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a per-point walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive. Its defensible contribution is not forecast accuracy and not the architecture: it is the **output object and its measured limits**, a time-dependent decision per point with a page saying how wrong it can be.

⚠ Bokade et al. published this project's whole pipeline on **2026-09-09** (10.5281/zenodo.22668357). Nothing here rests on it, because WFG-251 narrowed Q16d to 「**공개된 기록과 초록에는** 성능 수치가 하나도 없습니다」, which is safe whether or not a lap can reach the record. **Claim the measurement, never the architecture.**

## Before any row: this lap's `fix-before-next-row` item

**ONE. It is one clause on five lines plus the reprint, and it is about the reason, not the number.** The sentence the student is prescribed to say to all five judges beside the headline 42 now ends 「부스에서 말해도 되는지를 저희가 아직 정하지 않아서 오늘은 말씀드리지 않겠습니다」 (`docs/auto/JUDGE_QA.md:1017`, and the same clause at `:956` in Q19's spoken draft). `README.md:37` and `:335-336` print the entry id **NH-059** on the front door. A judge hears 「we measured it and have not decided whether we may tell you」, which reads as concealment, and the counts are already one click away because the TL;DR links `docs/present_perimeter_yeongdeok.md` and its §4 prints the 26 and the 16 in bold. **Replace the reason, speak no count**: say where the number is written, offer to open the page, and say it is a partition of 44 and not a margin. Then `make printables` at a new stamp and `release/kcf-finals-2026/MANIFEST.json` re-pointed (NH-049). Exact replacement wording, the mutation grade and the NH-054 licensing are in `CRITIC_LATEST.md`.

⚠ **Put NO count on any surface in this item**: not 26, not 16, not 2, not 44. **NH-059** stays open and all four of its options stay reachable after this edit. ⚠ Do **not** touch `README.md`'s opening paragraph about the 2025 fire (CHARTER §3.5b), and do **not** weaken the fire-blind-control or oracle-in-the-grading caveats.

⚠ **WFG-258 is `done`, all three halves, with the kit reprinted and the bundle re-pointed.** Re-measured by critic #68 in its own process: kit **7 of 7** (`WFG_printables_20260911T1627Z.pdf`, 59 pages), bundle **19 of 19**, bundle names that kit.

⚠ **Do NOT `git fetch --unshallow` in a critic or dev sandbox, and CHARTER §4 does not ask you to.** §4 forbids writing an ancestry claim from a shallow clone; it does not require deepening. Unshallowing drags in eleven side branches and turns `tests/test_timeline_roles.py`'s history check RED on a tree that is fine (critics #60 and #63 both paid). **Critic #68 did not deepen: `gates.py --mode full` exits 0 on its FIRST run** (2149 passed, 65 skipped, 3 xfailed). The cost, stated: in a shallow clone that history check **SKIPS** rather than runs (`tests/test_timeline_roles.py:234`), so a green critic gate does not certify it; GitHub at `fetch-depth: 0` does, and run 378 is green at `b6778e7`. Recorded on **WFG-217**. This note names those file lines and that measurement and expires at critic #69 unless that lap re-runs the case.

## Next three rows, and why each is next

1. **WFG-260 and WFG-259 TOGETHER, in one lap** (positions 1 and 2). Both are §5 of `docs/present_perimeter_yeongdeok.md`, both are a registration pass on the same script, and paying the setup twice is the waste. **WFG-260 (P0, science, new this lap):** the paper claims the fair opponent 「needs no model at all」 and the page's own §5 item 6 words its input so a reviewer would conclude the opposite. Critic #68 proved the claim from the committed array: `haz_stack[0]` is strictly binary and **identical cell for cell** to `obs_stack[0]` (249 cells), `build_canonical_hazard.py:88` seeds from the first FIRMS cumulative mask, and `hazard.py:97-100` mixes no slice at `t = 0`. **So slice 0 is the observation and the planning side is model-free, and no file says so.** **WFG-259 (P0, science):** 「at 500 m, 15 of the 16 flip」 at `:134` has six `ppy_yeongdeok_` keys behind the page and none is the 15 or either width. Nobody can re-derive it (CHARTER §3.3).

2. **WFG-256 (P0, science)** third, the rotation null, still `todo`, still the only thing that would license a sentence about 「모양」, then **WFG-255**, then **WFG-236**, **WFG-244**, **WFG-245**, **WFG-237**.

3. ⚠ **WFG-234 remains the strongest science row after those**, and WFG-256 is its cheap sibling: a persistence null scored against the headline truth, where a bad result is a **named, published failure mode of the whole model class**. Pre-register it in the claim commit.

⚠ **The board at `b6778e7` after this lap's one row: 254 rows, 15 P0 `todo`**, on critic #64's rule unchanged (split on pipes not preceded by a backslash, priority at cell 2, status at cell 5). **11 rows still render their priority and status in the wrong columns** because of unescaped pipes; that is **WFG-191** and it is the whole answer. Do not publish a board count without the rule that produced it and do not spend a lap reconciling one.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- ⚠⚠ **Before you call a row done, grep the judge-facing set for the NEGATION of what you just measured** — README, `docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md`, `docs/auto/finals/`, `web/finals.html`, `paper/manuscript.md`. One command. It caught WFG-258 and it would have caught WFG-138.
- ⚠⚠ **NEW, critic #68: do not write an internal entry id, or the reason an entry is open, onto a judge-facing surface.** `NH-###`, 「저자에게 열려 있습니다」, 「아직 정하지 않아서」 are the loop talking to itself. A judge reads them as a project that has not finished deciding what it believes. `README.md:50`, `:265`, `:351` still carry **NH-053** this way and are out of scope for the item above; they are the author's to rule on.
- ⚠ **Do not put any `ppy_yeongdeok_*` count on a judge-facing surface** while **NH-059** is open. The artifact says 「It is NOT a margin」 and that is true, but a judge hearing 26-of-44 will compute one, and NH-032, NH-034 and NH-052 are open.
- ⚠ **Do not widen WFG-258 into WFG-033(b) or NH-027.** A **buffered** present-perimeter opponent genuinely has not been run on 영덕; only the zero-buffer arm was.
- ⚠ **Do not weaken `docs/present_perimeter_yeongdeok.md` §5.** Its eight items are the best self-criticism in the repository this week. WFG-259 and WFG-260 make items 5 and 6 re-derivable; they do not soften either, and **item 6's scoring-side conclusion is TRUE and stays word for word**.
- ⚠⚠ **Do not unshallow the clone.** See the note above.
- ⚠ **Do not re-open WFG-254.** It closed at `20260911T0921Z` across eight surfaces. The 「모양」 half is **WFG-256**.
- ⚠ **Do not weaken `docs/disc_null.md` §4's centroid finding**, and do not weaken 「방향은 아닙니다」: that half IS measured.
- ⚠ **Do not regenerate `paper/figures/F10_disc_null.png`** (CHARTER §3 rule 2). `F10b_disc_null.png` is the corrected file.
- ⚠ **Do not touch `docs/submission_reconciliation.md:63`.** Its 발화점 is about how the canonical array was seeded and is correct.
- ⚠ **Do not write 「여러 개의 산불」, or any count of fires, from WFG-255's measurement alone.** The row measures components, not fires.
- ⚠ **Do not edit a scorecard row another lap wrote** (CHARTER §3.7). See **WFG-252**.
- ⚠ **Do not add a syllable to `docs/auto/DEMO_SCRIPT_5MIN.md` without saying which segment pays for it** (**WFG-257**; the script is at 6.00 syllables per second, unchanged since `f7ee58d`, re-checked at `b6778e7`, and 마무리 is its longest segment). Nothing in this repository pins the **absolute** rate, only the spread. <!-- collision-ok: 6.00 — the SPOKEN RATE of the whole script in syllables per second, which is `syllables_per_second` in `data/processed/demo_script_pace/pace_20260911T0620Z.json`. The gate reads it against the `demo_pace_*_rate_spread` keys (1.02, 1.03, 1.62), which are the RATIO of the fastest segment's implied rate to the slowest (`implied_rate_spread`, unit x, max over min). Two different quantities, and this line names both on purpose: the point of the sentence is that the ratio is gated and the rate is not. Neither value is stale. -->
- ⚠ **Do not "fix" WFG-249 by weakening Q20a's privacy answer.** ⚠ **Do not swap 가구 for 지점 in the demo closing, and do not swap either count** (the denominator is `l0i_failing_denominator_h240` **24**, not the **124**-building population).
- ⚠ **Do not open, cite or characterise the Bokade et al. body PDF**, and do not widen Q16d beyond 「공개된 기록과 초록」.
- ⚠ **Do not touch** Q16's 「가구 단위 폐쇄 시각」, Q16a's lines, the ⭕/❌ pair beside them, or the panel's two deliberately-kept 「집」 lines at `RELATED_WORK_PANEL.md:39-41` (`WC-013`, `WC-008`).
- ⚠ **Do not "re-fix" the household register.** Read `docs/auto/withdrawn_claims.json` before editing any 가구 line; the shipped checker is line-based so a reworded assertion escapes.
- ⚠ **Do not claim the architecture as the contribution.** Claim the output object and its measured limits. **WFG-239** writes the sentence.
- ⚠ **Do not write the 「위험 구역」 / 「잠재적 위험 구역」 zoning framing.** Recorded UNVERIFIED.
- ⚠ **Do not compare accuracy with any domestic system or study**, NIFoS, G-DAPS or the Kangwon National University DL model (**NH-056**).
- ⚠ **Do not quote the model-only IoU pair on any judge-facing surface without the seed-removed pair in the same block** (Q36 carries both).
- ⚠ **Do not edit `README.md`'s IoU bullet (`:520-522`, `:888-891`) while NH-055 is open**, and do not delete the Rothermel comparison in either direction.
- ⚠ **`README.md`'s TL;DR lead is frozen by NH-054 on its ORDERING AND PROPORTION, not on the truth or the length of a parenthetical inside it** (narrowed by critic #67, re-stated by #68; the measurement is NH-054's own 433-against-1,853 character count). Never rewrite its opening paragraph about the 2025 fire (CHARTER §3.5b).
- ⚠ **Do not edit `docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md` or `docs/auto/finals/RELATED_WORK_PANEL.md` without `make printables` at a new stamp and a re-pointed `MANIFEST.json`** (NH-049). Re-measured by critic #68 in its own process at `b6778e7`: the kit's seven sources hash **7 of 7** (`WFG_printables_20260911T1627Z.pdf`, 59 pages, 25 of them the Q&A bank) and the bundle's nineteen entries hash **19 of 19**, and the bundle names that kit. This note expires at critic #69 unless that lap re-measures.
- ⚠ **Do not write 「the fire stopped growing at 333 minutes」.** No observation exists between 0 and 333 minutes (WFG-230).
- ⚠ **Do not "fix" 「household-level」** in `README.md:3`, `CITATION.cff:5`, `src/wildfireguardian/__init__.py:1` or `paper/manuscript.md:1`; they name the **application** (WFG-231).
- ⚠ **Do not cite `data/processed/spread_v2/audit.json` for any number** (WFG-244).
- ⚠ **Do not rebuild `data/processed/timeline_roles/timeline_roles.json` from a deepened clone** (WFG-217; deadline 10-16). The refreshing lap works from a **single-branch full clone**.
- ⚠ **Do not weaken 「실제 확산면으로 만든 출동 지시서는 아직 없습니다」** on any surface (**NH-057**, **WFG-242**).
- **Do not settle 「상한」 / 「upper bound」 in any lap** (NH-053 open). Describe the mechanism.
- ⚠ **Do not put a margin value on any judge-facing surface** while NH-032, NH-034 and NH-052 are open.
- ⚠ **Do not add a word to `paper/manuscript.md` without trimming one** (NH-037, open).
- **Do not change `mr_uiseong_fa_exceeds_budget`** (NH-031 A; registry half is WFG-122).
- **Do not refit anything, and do not regenerate a committed artifact** (CHARTER §3 rule 2).
- **Do not re-open the AI-disclosure question** (NH-008 closed; CHARTER §9).
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13-§14).
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or `docs/NUMBERS.json`** (CHARTER §13).

## Readiness and open decisions

`docs/auto/KCF_READINESS.md` stands at **8 of 11**, unchanged: R1, R2, R4, R5, R6, R7, R8, R9 tick; R3, R11 and R12 do not; R10 was withdrawn 2026-09-04. ⚠⚠ **ZERO lines ticked for the TWENTY-FIFTH consecutive critic lap**, verified here by diffing the R-row status cells across the window: not one changed. Critic #52 measured the cause and it has not changed: R12 is the author's (NH-014), R3 is `blocked(NH-046)`, R11's WFG-024 is held by §14b until R3 ticks. **There is still no path from any amount of loop work to a ninth tick**, which is why this is reported and not re-filed.

**Open decisions: 26 for the author** (25 DECISION + 1 BLOCKER), **2 undated** (NH-005, NH-014), plus 5 open FYI. Say 「N of 26, and 2 undated」 rather than a bare number. **NH-046, NH-049 and NH-051 are past due.** **NH-057** and **NH-059** are the highest-severity open entries, and NH-059 gained a measured update from critic #68. ⚠ **The channel has now produced nothing for SEVEN DAYS:** `decisions_seen.json` records `"seen": []`, the newest applied decision is NH-031 of **2026-09-06**, and critic #68 confirmed at the Gmail connector that the **30** newest threads matching the report subject in the last 14 days each carry exactly one message and every one is the loop's own send; PR #31's comment list is empty. That is **WFG-211**, already `todo`, confirmed here and not re-filed. The sprint ends 2026-09-15, **four days out**.

## Critic's last direction note

**2026-09-11T1724Z, critic #68, reviewed `b6778e7`. NO §3b row move was spent.** The top of the table is correct because ONE new P0 row (**WFG-260**) was filed at position 1 under CHARTER §14b, which is step 5 and not a reorder. ONE new row, ZERO new NEEDS_HUMAN entries (NH-059 was updated instead, deliberately: 26 are already open and the channel has been silent seven days), ONE `fix-before-next-row` item.

**The one thing that matters on this page.** Yesterday's lesson was that the loop corrects the page it is writing and not the pages that page makes wrong. It learned that one: WFG-258 closed across every surface, the paper included, with the kit reprinted. The new failure is one level up. In closing it, the loop wrote **its own governance** onto the judged surfaces: the README's front door now prints an entry id, and the sentence the student says to five judges beside the headline 42 explains that a measured result is being withheld because nobody has decided whether it may be spoken. Inside the loop that sentence is correct and careful; to a judge it is the one thing that reads as concealment, and it is attached to the number the whole project is judged on. **The loop's internal vocabulary is not neutral when it reaches a surface. Nothing that names an NH entry, or the state of a decision, belongs in front of a judge.**

**Scorecard: Track B 94 to 95, Track A 96 to 97.** One row moves on each and it is the same row: 제출 자료 **18 to 19**, on critic #68's own pre-registration, because WFG-258 (a) closed with the kit reprinted and the bundle re-pointed, both re-hashed here. **19 and not 20** because of the item above.

Verified at `b6778e7`, the head reviewed and the head this lap ships in. **GitHub `auto-gates` run 378 is `success` at `b6778e7`**, and **no run in the window concluded `failure`** (one `cancelled`, 368, superseded by the next push), so CHARTER §4b sets no finding #1 for the seventeenth consecutive lap. `gates.py --mode full` exits **0** on its FIRST run in this sandbox (2149 passed, 65 skipped, 3 xfailed, pytest 501.4 s), and **every dev report in the window records `Reviewed by:`** (fourteen checked, all `subagent`, nine of them `block`). The clone is SHALLOW at **50** commits and was deliberately NOT deepened; no ancestry claim is written anywhere in this lap.
