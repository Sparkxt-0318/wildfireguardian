# Direction — where the project is going, on one screen

*Re-checked 2026-09-11T1125Z by critic #66 at `d67de57`, corrected mid-lap and shipped at `c241904`. Last rewritten 2026-09-10T1817Z by the research routine (CHARTER §14). The dev routine reads this before it claims a row; the critic re-checks it after every dev lap, at most one reorder per lap, with a reason. Only the most recent critic note is kept. **Critic #66 spent its ONE §3b row move, and it moved WFG-129.***

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a per-point walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive. Its defensible contribution is not forecast accuracy and not the architecture: it is the **output object and its measured limits**, a time-dependent decision per point with a page saying how wrong it can be.

⚠ Bokade et al. published this project's whole pipeline on **2026-09-09** (10.5281/zenodo.22668357). Critic #65 could not reach the Zenodo API from its sandbox and critic #66 did not retry; nothing here rests on it, because WFG-251 narrowed Q16d to 「**공개된 기록과 초록에는** 성능 수치가 하나도 없습니다」, which is safe whether or not a lap can reach the record. **Claim the measurement, never the architecture.**

## Before any row: this lap's `fix-before-next-row` item

**ONE, it is NEW, and it is one clause plus the 17-second rebuild.** `docs/auto/JUDGE_QA.md:1513`
(Q36, T0, said from memory to all five judges) and `docs/disc_null.md:225` both close on
「저희가 잘하는 것은 방향이 아니라 불의 모양입니다」, and **nothing in this repository has measured
the 「모양」 half**. Replace it with what the artifact supports, for example
「저희가 나은 것은 겹침이고, 방향은 아닙니다 — 그것이 모양 때문인지는 아직 재지 않았습니다」, then
`make printables` at a new stamp and re-point `release/kcf-finals-2026/MANIFEST.json`. ⚠ Do **not**
weaken 「방향은 아닙니다」: that half IS measured, by the `direction` block, and it is the card's
strongest move. This is the Q&A half of **WFG-256** and it does not wait for the experiment.

⚠⚠ **CORRECTED MID-LAP. Critic #65's item is PAID.** This lap reviewed `d67de57`, where WFG-254 was
`in-progress` with only its claim commit pushed; the lap holding it pushed `05d3bb3` while this page
was being written, and **WFG-254 is now `done(20260911T0921Z)`**. Re-measured at the rebased head
rather than read from the report: `발화점` answers **0** in the Q36 cell, `모양과 범위` answers **0**
across the bank, `docs/disc_null.md` and `docs/oracle_gap.md`, the kit is rebuilt at
`WFG_printables_20260911T0939Z.pdf` (59 p) with its seven sources hashing **7 of 7**, and the bundle
is re-pointed. The row went further than asked: an eighth surface in `paper/GAPS.md`, the measurement
turned into an artifact (`scripts/measure_disc_centre_vs_ignition.py`), and four spellings registered
as `WC-017`. **WFG-254 disambiguated the area-versus-reach axis correctly and that is not re-opened.
What it left standing is 「모양」 as an axis the model is said to have WON.**

⚠ **Do NOT `git fetch --unshallow` in a critic or dev sandbox, and CHARTER §4 does not ask you to.**
§4 forbids writing an ancestry claim from a shallow clone; it does not require deepening.
Unshallowing drags in eleven side branches and turns `tests/test_timeline_roles.py`'s history check
RED on a tree that is fine (critics #60 and #63 both paid). **Critic #66 did not deepen:
`gates.py --mode full` exits 0 on its FIRST run at both heads it ran on** (2097 passed, 65 skipped,
3 xfailed). The cost, stated: in a shallow clone that history check **SKIPS** rather than runs
(`tests/test_timeline_roles.py:234`), so a green critic gate does not certify it; GitHub at
`fetch-depth: 0` does. Recorded on **WFG-217**. This note names those file lines and that measurement
and expires at critic #67 unless that lap re-runs the case.

## Next three rows, and why each is next

1. ⚠⚠ **WFG-129 (P0, science) IS NOW AT TABLE POSITION 2, AND THAT IS THIS LAP'S ONE §3b ROW MOVE.** Seven direction pages have named it next and it has never been taken, and critic #65 measured why: 「the cause is this page's ordering rather than the lap's choice」. It was at **table position 78** while this page called it row 2, and CHARTER §14b tells the dev lap to prefer this page when the two differ, so the two now agree and the ordering excuse is gone. Fully specified in `paper/GAPS.md` G7 and in its own row: mask slice 0 of `data/processed/routing_demo_canonical.npz` as a node filter, re-run the existing `naive_route` over only the 44 origins whose fire-blind route enters the hazard, count how many a present-perimeter-only router already saves. Committed inputs only, no refit, no re-acquisition, no author decision. G7's own words: 「That is minutes of work」. It is the cheapest test of the exact number the booth leads with. ⚠ **Critic #65's pre-registration did NOT fire and is re-stated with the same teeth:** it asked for TWO dev laps since `f7ee58d`, and exactly ONE ran (the 0921Z lap, which closed WFG-254 in full). **Pre-registered for critic #67: if TWO dev laps have completed since `c241904` and WFG-129 is still `todo`, that is finding #1, and the cause is no longer this page's ordering.** ⚠ **WFG-254 is now `done` and no longer stands above this row.** The move passes over **WFG-255** (critic #65's own new row, position 4 now) and over **WFG-117** and **WFG-007**, whose remaining half its own cell marks 「print/laptop: human」. That is the whole skip list.

2. **WFG-256 (P0, science), new this lap, position 3.** The card five judges hear closes on 「저희가 잘하는 것은 방향이 아니라 불의 모양입니다」, and the artifact it rests on declines that attribution in its own words: `disc_null_yeongdeok.json :: what_this_is_not` calls the IoU gap 「joint PLACEMENT-AND-SHAPE skill」. The `direction` block prices the placement half (the model is worse than the stationary disc); **nothing in this repository measures the shape half**, and a search here for a shape-matched, second-moment, principal-axis or rotated null returns nothing. The row runs the rotation null: rotate the model's **own** core about the `t = 0` seed centroid through a pre-registered angle sweep and re-score. Shape and area are the model's own by construction, so the only thing that varies is orientation, and the spread of rotated IoUs is the shape-controlled null for placement. Zero free parameters, one committed npz.

3. **WFG-255 (P0, science) third**, then **WFG-236**, then **WFG-244**, **WFG-245** and **WFG-237**.

⚠ **WFG-234 remains the strongest science row after WFG-129 and WFG-256**, and WFG-256 is its cheap sibling: a persistence null scored against the headline truth, where a bad result is a **named, published failure mode of the whole model class**. Pre-register it in the claim commit. Take it before other P1 science work.

⚠ **The board at `d67de57` after this lap's two rows: 251 rows, 17 P0 `todo`, 111 P1 `todo`**, on critic #64's rule unchanged (split on pipes not preceded by a backslash, priority at cell 2, status at cell 5). **11 rows still render their priority and status in the wrong columns** because of unescaped pipes; that is **WFG-191** and it is the whole answer. Do not publish a board count without the rule that produced it and do not spend a lap reconciling one.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- ⚠ **Do not re-open WFG-254.** It closed at `20260911T0921Z` across eight surfaces with the kit rebuilt and the bundle re-pointed, and its reach clause is a description that stays. The 「모양」 half is **WFG-256**.
- ⚠⚠ **Do not unshallow the clone.** See the note above.
- ⚠ **Do not weaken `docs/disc_null.md` §4's centroid finding.** It survived WFG-254's relabelling unchanged, and 「방향은 아닙니다」 is the measured half of the card's closing sentence and the card's strongest move.
- ⚠ **Do not read WFG-254's reach clause as an attribution.** 「뻗은 거리」 is describable and measured; 「모양」 as an axis the model WON is **WFG-256** and is not measured.
- ⚠ **Do not regenerate `paper/figures/F10_disc_null.png`** (CHARTER §3 rule 2). `F10b_disc_null.png` is the corrected file and the old one keeps its dated note.
- ⚠ **Do not touch `docs/submission_reconciliation.md:63`.** Its 발화점 is about how the canonical array was seeded and is correct; that is precisely why the Q36 shorthand misleads.
- ⚠ **Do not write 「여러 개의 산불」, or any count of fires, from WFG-255's measurement alone.** The row measures components, not fires.
- ⚠ **Do not edit a scorecard row another lap wrote** (CHARTER §3.7). Critic #66 did not; it transcribed the missing series row and annotated the discrepancy. See **WFG-252**.
- ⚠ **Do not add a syllable to `docs/auto/DEMO_SCRIPT_5MIN.md` without saying which segment pays for it** (**WFG-257**, new; the script is at 6.00 syllables per second and 마무리 is now its longest segment).
- ⚠ **Do not "fix" WFG-249 by weakening Q20a's privacy answer** (closed 2026-09-11; the scope clause is the repair, not a softening).
- ⚠ **Do not swap 가구 for 지점 in the demo closing, and do not swap either count.** The denominator is `l0i_failing_denominator_h240` **24**, not the **124**-building population.
- ⚠ **Do not open, cite or characterise the Bokade et al. body PDF**, and do not widen Q16d beyond 「공개된 기록과 초록」.
- ⚠ **Do not touch** Q16's 「가구 단위 폐쇄 시각」, Q16a's lines, the ⭕/❌ pair beside them, or the panel's two deliberately-kept 「집」 lines at `RELATED_WORK_PANEL.md:39-41`. `WC-013` and `WC-008` preserve all of these by name.
- ⚠ **Do not "re-fix" the household register.** Read `docs/auto/withdrawn_claims.json` before editing any 가구 line; the shipped checker is line-based so a reworded assertion escapes (`docs/withdrawn_claims.md` §4).
- ⚠ **Do not claim the architecture as the contribution.** Claim the output object and its measured limits. **WFG-239** writes the sentence.
- ⚠ **Do not write the 「위험 구역」 / 「잠재적 위험 구역」 zoning framing.** Recorded UNVERIFIED.
- ⚠ **Do not compare accuracy with any domestic system or study**, NIFoS, G-DAPS or the Kangwon National University DL model (**NH-056**).
- ⚠ **Do not quote the model-only IoU pair on any judge-facing surface without the seed-removed pair in the same block** (Q36 carries both).
- ⚠ **Do not edit `README.md`'s IoU bullet (`:520-522`, `:888-891`) while NH-055 is open**, and do not delete the Rothermel comparison in either direction.
- ⚠ **Do not edit `README.md`'s TL;DR lead in either direction while NH-054 is open**, and never rewrite its opening paragraph about the 2025 fire (CHARTER §3.5b).
- ⚠ **Do not edit `docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md` or `docs/auto/finals/RELATED_WORK_PANEL.md` without `make printables` at a new stamp and a re-pointed `MANIFEST.json`** (NH-049). Re-measured by critic #66 in its own process at both heads: the kit's seven sources hash **7 of 7** at `d67de57` (`WFG_printables_20260911T0706Z.pdf`) and again at the rebased head (`WFG_printables_20260911T0939Z.pdf`), 59 pages each, with the bundle naming the newer one. ⚠ Critic #66 did **not** independently re-derive the 19-file bundle tally and does not restate it; `tests/test_finals_bundle.py` is green inside this lap's full gate run. This note expires at critic #67 unless that lap re-measures.
- ⚠ **Do not write 「the fire stopped growing at 333 minutes」.** No observation exists between 0 and 333 minutes (WFG-230).
- ⚠ **Do not "fix" 「household-level」** in `README.md:3`, `CITATION.cff:5`, `src/wildfireguardian/__init__.py:1` or `paper/manuscript.md:1`; they name the **application** (WFG-231).
- ⚠ **Do not cite `data/processed/spread_v2/audit.json` for any number** (WFG-244).
- ⚠ **Do not rebuild `data/processed/timeline_roles/timeline_roles.json` from a deepened clone** (WFG-217; deadline 10-16). Critic #66 did not re-measure the commit half of that gap; a shallow clone cannot count it and CHARTER §4 forbids writing it from one. The refreshing lap works from a **single-branch full clone**.
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

`docs/auto/KCF_READINESS.md` stands at **8 of 11**, re-counted by critic #66 from the checklist table at `d67de57`: R1, R2, R4, R5, R6, R7, R8, R9 tick; R3, R11 and R12 do not; R10 was withdrawn 2026-09-04. ⚠⚠ **ZERO lines ticked for the TWENTY-THIRD consecutive critic lap.** Critic #52 measured the cause and it has not changed: R12 is the author's (NH-014), R3 is `blocked(NH-046)`, R11's WFG-024 is held by §14b until R3 ticks. **There is still no path from any amount of loop work to a ninth tick**, which is why this is reported and not re-filed.

**Open decisions: 25 for the author** (24 DECISION + 1 BLOCKER), **2 undated** (NH-005, NH-014), plus 5 open FYI. Say 「N of 25, and 2 undated」 rather than a bare number. ⚠ **This count was 24 earlier in this lap and the twenty-fifth is NH-058**, filed by the 0921Z lap in the same mid-lap push that closed WFG-254: the dev routine's claim commit reached `origin` before it built, exactly as CHARTER §4 step 3 requires, and the paper routine built the same row anyway because the claim rule cannot see it. **That is the one new author question of this window and it is not critic #66's.** **NH-046, NH-049 and NH-051 are past due.** **NH-057** is the highest-severity open entry, and **NH-054** gained a measured note this lap. ⚠ **The channel has now produced nothing for FIVE DAYS:** `decisions_seen.json` records `"seen": []`, the newest applied decision is NH-031 of **2026-09-06**, and critic #66 confirmed at the Gmail connector that every thread matching the report subject in the last 14 days carries exactly one message and every one is the loop's own send. That is **WFG-211**, already `todo`, confirmed here and not re-filed. The sprint ends 2026-09-15, **four days out**.

## Critic's last direction note

**2026-09-11T1125Z, critic #66, reviewed `d67de57`, ships at `c241904`. ONE §3b row move: WFG-129 from table position 78 to position 2.** TWO new rows (**WFG-256** P0 at position 3, **WFG-257** P1 at the end); **WFG-252** updated in place rather than duplicated; ONE `fix-before-next-row` item, which is NEW: critic #65's was paid in full by the 0921Z lap while this page was being written, and the clause that survived it is the one no measurement supports; **NO new NEEDS_HUMAN entry, deliberately**, for the fourth consecutive lap, with a measured note appended to NH-054 instead.

**The one thing that matters on this page.** For seven consecutive pages this project has been told that the cheapest test of its own headline is minutes away, and for seven pages something more urgent arrived first. This lap removed the last mechanical excuse by putting WFG-129 where the table says it goes, and the thing that arrived first this time has now landed: WFG-254 is done across eight surfaces with the kit reprinted. **What the window leaves behind is the pattern in its cleanest form.** Two laps in two days went over the same sentence with a fine comb, and both of them corrected where the circle sits. Neither asked whether the sentence that follows is true. The card still tells five judges 「저희가 잘하는 것은 방향이 아니라 불의 모양입니다」, and the project's own artifact says in its own words that it cannot tell shape from placement. **The project checks its wording faster than it checks its claims. WFG-256 is the experiment that would let the card say it honestly, and WFG-129 is the row that stops the pattern.**

**Scorecard: Track B 95 to 94, Track A 96 to 97.** Three rows move and they do not all move the same way. **제출 자료 18 to 19 on BOTH tracks**, because critic #65's pre-registered condition was paid in full mid-lap: eight surfaces name the centre correctly, the kit is rebuilt and the bundle re-pointed, and Track A's extra clause (the replacement figure under a new filename with a correct heading) is met too. **데이터 수집·분석·해석 19 to 18** on Track B, a new defect (**WFG-256**). **연구 목적 19 to 18** on Track B, which is not a finding but the **withdrawal of an unevidenced point**: critic #65's row raised it from 18 while its own narrative called it HELD, and no lap has published a reason.

Verified at `d67de57`, the head reviewed, and re-verified on `c241904`, the commit this ships in after the rebase onto `05d3bb3`. **GitHub `auto-gates` run 369 is `success` at `d67de57`**, and **no run in the 24-hour window concluded `failure`** (three `cancelled`, runs 344, 352 and 368, each superseded by the next push), so CHARTER §4b sets no finding #1 for the fifteenth consecutive lap. `gates.py --mode full` exits **0** on its FIRST run in this sandbox at both heads (2097 passed, 65 skipped, 3 xfailed), `--assert-head` and `--assert-reported` exit 0 on the commit that is pushed, and **every dev report in the window records `Reviewed by:`** (ten checked, all `subagent`). The clone is SHALLOW at **50** commits and was deliberately NOT deepened; no ancestry claim is written anywhere in this lap.
