# Direction — where the project is going, on one screen

*Re-checked 2026-09-11T1416Z by critic #67 at `dec00f4`. Last rewritten 2026-09-10T1817Z by the research routine (CHARTER §14). The dev routine reads this before it claims a row; the critic re-checks it after every dev lap, at most one reorder per lap, with a reason. Only the most recent critic note is kept. **Critic #67 spent NO §3b row move: the top of the table is now correct because two NEW P0 rows were filed at position 1 and 2, which CHARTER §14b says is never a preemption.***

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a per-point walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive. Its defensible contribution is not forecast accuracy and not the architecture: it is the **output object and its measured limits**, a time-dependent decision per point with a page saying how wrong it can be.

⚠ Bokade et al. published this project's whole pipeline on **2026-09-09** (10.5281/zenodo.22668357). Nothing here rests on it, because WFG-251 narrowed Q16d to 「**공개된 기록과 초록에는** 성능 수치가 하나도 없습니다」, which is safe whether or not a lap can reach the record. **Claim the measurement, never the architecture.**

## Before any row: this lap's `fix-before-next-row` item

**ONE. It is WFG-258 half (a), and it is one clause on four lines plus the reprint.** The repository measured the fair opponent on 영덕 this morning (WFG-129, `7991512`) and **four judge-facing lines still say it has never been run**: `README.md:33-34`, `README.md:325`, `docs/auto/JUDGE_QA.md:954` (Q19's spoken draft) and `docs/auto/JUDGE_QA.md:1004` (critic #29's prescribed booth sentence). The disproof is `scripts/measure_present_perimeter_yeongdeok.py` → `data/processed/present_perimeter_yeongdeok_2025.json` → `docs/present_perimeter_yeongdeok.md`, and `paper/GAPS.md` G7 already records it ✅✅ **CLOSED**. Q19 is **on the paper in the box**: the kit hashes 7 of 7 and the bundle 19 of 19, re-measured by critic #67.

Each line says instead that the comparison **has** been run on 영덕, names the file, and says the counts are not yet licensed for the booth. Then `make printables` at a new stamp and `release/kcf-finals-2026/MANIFEST.json` re-pointed (NH-049).

⚠ **Put NO count on any surface in this item** — not 26, not 16, not 2, not 44. **NH-059** is the author's decision on whether they may be spoken. ⚠ **NH-054 does not hold this edit:** NH-054 is open on the **proportion** of the TL;DR bullet, this changes the **truth** of one clause inside it at about the same length, deletes no caveat and moves nothing. See `CRITIC_LATEST.md` for the full reasoning. ⚠ Do **not** touch `README.md`'s opening paragraph about the 2025 fire, and do **not** weaken the fire-blind-control or oracle-in-the-grading caveats; both are still true.

⚠ **Do NOT `git fetch --unshallow` in a critic or dev sandbox, and CHARTER §4 does not ask you to.** §4 forbids writing an ancestry claim from a shallow clone; it does not require deepening. Unshallowing drags in eleven side branches and turns `tests/test_timeline_roles.py`'s history check RED on a tree that is fine (critics #60 and #63 both paid). **Critic #67 did not deepen: `gates.py --mode full` exits 0 on its FIRST run** (2127 passed, 65 skipped, 3 xfailed). The cost, stated: in a shallow clone that history check **SKIPS** rather than runs (`tests/test_timeline_roles.py:234`), so a green critic gate does not certify it; GitHub at `fetch-depth: 0` does, and run 374 is green at `dec00f4`. Recorded on **WFG-217**. This note names those file lines and that measurement and expires at critic #68 unless that lap re-runs the case.

## Next three rows, and why each is next

1. **WFG-258 (P0, KCF), table position 1, and half (a) is the item above.** Its remaining halves after the reprint: (b) `paper/manuscript.md:414-418` (which still carries a `[GAP:` marker `paper/GAPS.md` calls closed) and `:718-724` — **the paper routine's**, under CHARTER §12 — and (c) `tests/test_future_aware_attribution.py:16-17,196`, whose docstring and failure message instruct the next lap to re-write the false clause.

2. **WFG-259 (P0, science), position 2, new this lap.** `docs/present_perimeter_yeongdeok.md` §5 item 5 states 「at 500 m, **15 of the 16** flip」 and a named origin flipping at 100 m. The artifact has **no** dilation or buffer-sensitivity block, `docs/NUMBERS.json` holds six `ppy_yeongdeok_` keys and none is the 15 or either width, and the script takes no buffer argument. **Nobody can re-derive it from this tree** (CHARTER §3.3). It is the most consequential integer in the repository — it implies a slightly better opponent reaches 41 of 42 — and the only one in its own page with nothing behind it. Preferred fix: run the dilation at the two widths already named, register the keys, re-point the sentence.

3. **WFG-256 (P0, science) third** — the rotation null, still `todo`, still the only thing that would license a sentence about 「모양」 — then **WFG-255**, then **WFG-236**, **WFG-244**, **WFG-245**, **WFG-237**.

⚠ **WFG-234 remains the strongest science row after those**, and WFG-256 is its cheap sibling: a persistence null scored against the headline truth, where a bad result is a **named, published failure mode of the whole model class**. Pre-register it in the claim commit.

⚠ **WFG-129 is `done(20260911T1219Z)`.** Seven direction pages named it next; the eighth took it. Critic #66's pre-registration (「if TWO dev laps have completed since `c241904` and WFG-129 is still `todo`, that is finding #1」) **did not fire and is closed**: one dev lap ran and it ran the row.

⚠ **The board at `dec00f4` after this lap's two rows: 253 rows, 18 P0 `todo`, 111 P1 `todo`**, on critic #64's rule unchanged (split on pipes not preceded by a backslash, priority at cell 2, status at cell 5). **11 rows still render their priority and status in the wrong columns** because of unescaped pipes; that is **WFG-191** and it is the whole answer. Do not publish a board count without the rule that produced it and do not spend a lap reconciling one.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- ⚠⚠ **Before you call a row done, grep the judge-facing set for the NEGATION of what you just measured** — README, `docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md`, `docs/auto/finals/`, `web/finals.html`, `paper/manuscript.md`. One command. It would have caught WFG-258, WFG-138 and critic #27's original.
- ⚠ **Do not put any `ppy_yeongdeok_*` count on a judge-facing surface** while **NH-059** is open. The artifact says 「It is NOT a margin」 and that is true, but a judge hearing 26-of-44 will compute one, and NH-032, NH-034 and NH-052 are open.
- ⚠ **Do not widen WFG-258 into WFG-033(b) or NH-027.** A **buffered** present-perimeter opponent genuinely has not been run on 영덕; only the zero-buffer arm was.
- ⚠ **Do not weaken `docs/present_perimeter_yeongdeok.md` §5.** Its eight items, two of them added by a reviewer that blocked the lap, are the best self-criticism in the repository this week. WFG-259 makes item 5 re-derivable; it does not soften it.
- ⚠⚠ **Do not unshallow the clone.** See the note above.
- ⚠ **Do not re-open WFG-254.** It closed at `20260911T0921Z` across eight surfaces. The 「모양」 half is **WFG-256**.
- ⚠ **Do not weaken `docs/disc_null.md` §4's centroid finding**, and do not weaken 「방향은 아닙니다」: that half IS measured.
- ⚠ **Do not regenerate `paper/figures/F10_disc_null.png`** (CHARTER §3 rule 2). `F10b_disc_null.png` is the corrected file.
- ⚠ **Do not touch `docs/submission_reconciliation.md:63`.** Its 발화점 is about how the canonical array was seeded and is correct.
- ⚠ **Do not write 「여러 개의 산불」, or any count of fires, from WFG-255's measurement alone.** The row measures components, not fires.
- ⚠ **Do not edit a scorecard row another lap wrote** (CHARTER §3.7). See **WFG-252**.
- ⚠ **Do not add a syllable to `docs/auto/DEMO_SCRIPT_5MIN.md` without saying which segment pays for it** (**WFG-257**; the script is at 6.00 syllables per second, re-measured at `dec00f4`, and 마무리 is its longest segment).
- ⚠ **Do not "fix" WFG-249 by weakening Q20a's privacy answer.** ⚠ **Do not swap 가구 for 지점 in the demo closing, and do not swap either count** (the denominator is `l0i_failing_denominator_h240` **24**, not the **124**-building population).
- ⚠ **Do not open, cite or characterise the Bokade et al. body PDF**, and do not widen Q16d beyond 「공개된 기록과 초록」.
- ⚠ **Do not touch** Q16's 「가구 단위 폐쇄 시각」, Q16a's lines, the ⭕/❌ pair beside them, or the panel's two deliberately-kept 「집」 lines at `RELATED_WORK_PANEL.md:39-41` (`WC-013`, `WC-008`).
- ⚠ **Do not "re-fix" the household register.** Read `docs/auto/withdrawn_claims.json` before editing any 가구 line; the shipped checker is line-based so a reworded assertion escapes.
- ⚠ **Do not claim the architecture as the contribution.** Claim the output object and its measured limits. **WFG-239** writes the sentence.
- ⚠ **Do not write the 「위험 구역」 / 「잠재적 위험 구역」 zoning framing.** Recorded UNVERIFIED.
- ⚠ **Do not compare accuracy with any domestic system or study**, NIFoS, G-DAPS or the Kangwon National University DL model (**NH-056**).
- ⚠ **Do not quote the model-only IoU pair on any judge-facing surface without the seed-removed pair in the same block** (Q36 carries both).
- ⚠ **Do not edit `README.md`'s IoU bullet (`:520-522`, `:888-891`) while NH-055 is open**, and do not delete the Rothermel comparison in either direction.
- ⚠ **`README.md`'s TL;DR lead is frozen by NH-054 on its ORDERING AND PROPORTION, not on the truth of a clause inside it** (narrowed by critic #67; the measurement is NH-054's own 433-against-1,853 character count). Never rewrite its opening paragraph about the 2025 fire (CHARTER §3.5b).
- ⚠ **Do not edit `docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md` or `docs/auto/finals/RELATED_WORK_PANEL.md` without `make printables` at a new stamp and a re-pointed `MANIFEST.json`** (NH-049). Re-measured by critic #67 in its own process at `dec00f4`: the kit's seven sources hash **7 of 7** (`WFG_printables_20260911T1226Z.pdf`, 59 pages) and the bundle's nineteen entries hash **19 of 19**, and the bundle names that kit. This note expires at critic #68 unless that lap re-measures.
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

`docs/auto/KCF_READINESS.md` stands at **8 of 11**, unchanged: R1, R2, R4, R5, R6, R7, R8, R9 tick; R3, R11 and R12 do not; R10 was withdrawn 2026-09-04. ⚠⚠ **ZERO lines ticked for the TWENTY-FOURTH consecutive critic lap.** Critic #52 measured the cause and it has not changed: R12 is the author's (NH-014), R3 is `blocked(NH-046)`, R11's WFG-024 is held by §14b until R3 ticks. **There is still no path from any amount of loop work to a ninth tick**, which is why this is reported and not re-filed.

**Open decisions: 26 for the author** (25 DECISION + 1 BLOCKER), **2 undated** (NH-005, NH-014), plus 5 open FYI. Say 「N of 26, and 2 undated」 rather than a bare number. **The twenty-sixth is NH-059**, filed by critic #67: whether the 26 / 16 / 2 goes on a judge-facing surface. **NH-046, NH-049 and NH-051 are past due.** **NH-057** and **NH-059** are the highest-severity open entries. ⚠ **The channel has now produced nothing for SIX DAYS:** `decisions_seen.json` records `"seen": []`, the newest applied decision is NH-031 of **2026-09-06**, and critic #67 confirmed at the Gmail connector that the 25 newest threads matching the report subject in the last 14 days each carry exactly one message and every one is the loop's own send; PR #31's comment list is empty. That is **WFG-211**, already `todo`, confirmed here and not re-filed. The sprint ends 2026-09-15, **four days out**.

## Critic's last direction note

**2026-09-11T1416Z, critic #67, reviewed `dec00f4`. NO §3b row move was spent.** The top of the table is correct because two NEW P0 rows were filed at positions 1 and 2 under CHARTER §14b, which is step 5 and not a reorder. TWO new rows (**WFG-258**, **WFG-259**), ONE new NEEDS_HUMAN entry (**NH-059**, the first in five critic laps), ONE `fix-before-next-row` item, which is WFG-258 half (a).

**The one thing that matters on this page.** The window contains the best experiment this project has run in a week and the plainest judge-facing falsehood it has carried in a week, and they are the **same fact**. WFG-129 measured the fair opponent on 영덕 and found that a router which only looks out of the window already saves 26 of the 44 the headline credits to the forecast. The lap wrote a 170-line 「What this does not show」 section, had its reviewer block it, and fixed what the reviewer found. Then it stopped — and four lines a judge reads, one of them said from memory and printed on page 25 of the kit, still say the comparison has never been run. **The care in this loop is concentrated on the page being written and is almost absent on the pages that page makes wrong.** WFG-138 is the record of this exact sentence going wrong the last time. The fix is one grep, before a row is called done.

**Scorecard: Track B 94 to 94, Track A 97 to 96.** On Track B two rows move in opposite directions and cancel: 데이터 수집·분석·해석 **18 to 19** for WFG-129's design, 제출 자료 **19 to 18** for WFG-258. On Track A only the second lands, because this track has no 데이터 수집·분석·해석 row, and it lands harder: what a judge carries away is the paper, and the false clause is on it.

Verified at `dec00f4`, the head reviewed. **GitHub `auto-gates` run 374 is `success` at `dec00f4`**, and **no run in the window concluded `failure`** (one `cancelled`, 368, superseded by the next push), so CHARTER §4b sets no finding #1 for the sixteenth consecutive lap. `gates.py --mode full` exits **0** on its FIRST run in this sandbox (2127 passed, 65 skipped, 3 xfailed), and **every dev report in the window records `Reviewed by:`** (nine checked, all `subagent`, four of them `block`). The clone is SHALLOW at **50** commits and was deliberately NOT deepened; no ancestry claim is written anywhere in this lap.
