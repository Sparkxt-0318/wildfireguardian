# Direction — where the project is going, on one screen

*Re-checked 2026-09-11T1100Z by critic #66 at `d67de57`. Last rewritten 2026-09-10T1817Z by the research routine (CHARTER §14). The dev routine reads this before it claims a row; the critic re-checks it after every dev lap, at most one reorder per lap, with a reason. Only the most recent critic note is kept. **Critic #66 spent its ONE §3b row move, and it moved WFG-129.***

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a per-point walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive. Its defensible contribution is not forecast accuracy and not the architecture: it is the **output object and its measured limits**, a time-dependent decision per point with a page saying how wrong it can be.

⚠ Bokade et al. published this project's whole pipeline on **2026-09-09** (10.5281/zenodo.22668357). Critic #65 could not reach the Zenodo API from its sandbox and critic #66 did not retry; nothing here rests on it, because WFG-251 narrowed Q16d to 「**공개된 기록과 초록에는** 성능 수치가 하나도 없습니다」, which is safe whether or not a lap can reach the record. **Claim the measurement, never the architecture.**

## Before any row: this lap's `fix-before-next-row` item

**ONE, it is critic #65's item RE-STATED because it is unpaid, and it is still minutes.** `docs/auto/JUDGE_QA.md:1513` (Q36, T0, said from memory to all five judges, page 25 of the 59-page kit) still tells a judge 「같은 면적의 원을 **발화점에** 놓고」, and the ignition point this project records is **19.20 km** from that circle's centre. Re-measured at `d67de57`: the clause is there, `docs/disc_null.md:221` and `docs/oracle_gap.md:204` carry the same locative, and the kit's seven sources hash **7 of 7** against the tree, so it is on the paper in the box.

⚠⚠ **What changed in this window is that the ENGLISH half was paid and the KOREAN half was not.** The paper lap corrected `paper/manuscript.md:710` to 「an equal-area disc centred on the first detections' centroid」, retired 「shape and extent」 there in favour of 「overlaps」, and reissued the figure as `paper/figures/F10b_disc_null.png`. **The manuscript and the booth card now disagree about what this project claims it is good at, and the card is the half five judges hear.** Pay the Korean half with the same `make printables` rebuild and a re-pointed `release/kcf-finals-2026/MANIFEST.json`. That is **WFG-254**, which is `in-progress(20260911T0921Z)` with only its claim commit pushed (1 h 40 m old at this head, inside CHARTER §5b's three hours, so it is NOT a stale claim and must not be taken from that lap).

⚠ **Do NOT `git fetch --unshallow` in a critic or dev sandbox.** CHARTER §4 forbids writing an ancestry claim from a shallow clone; it does not ask you to deepen. Unshallowing drags in eleven side branches and turns `tests/test_timeline_roles.py`'s history check RED on a tree that is fine (critics #60 and #63 both paid). **Critic #66 did not deepen: `gates.py --mode full` exits 0 on its FIRST run**, 2097 passed, 65 skipped, 3 xfailed. The cost, stated: in a shallow clone that history check **SKIPS** rather than runs (`tests/test_timeline_roles.py:234`), so a green critic gate does not certify it; GitHub at `fetch-depth: 0` does, and run **369** is `success` at this exact head. Recorded on **WFG-217**. This note names those file lines and that measurement and expires at critic #67 unless that lap re-runs the case.

## Next three rows, and why each is next

1. ⚠⚠ **WFG-129 (P0, science) IS NOW AT TABLE POSITION 2, AND THAT IS THIS LAP'S ONE §3b ROW MOVE.** Seven direction pages have named it next and it has never been taken, and critic #65 measured why: 「the cause is this page's ordering rather than the lap's choice」. It was at **table position 78** while this page called it row 2, and CHARTER §14b tells the dev lap to prefer this page when the two differ, so the two now agree and the ordering excuse is gone. Fully specified in `paper/GAPS.md` G7 and in its own row: mask slice 0 of `data/processed/routing_demo_canonical.npz` as a node filter, re-run the existing `naive_route` over only the 44 origins whose fire-blind route enters the hazard, count how many a present-perimeter-only router already saves. Committed inputs only, no refit, no re-acquisition, no author decision. G7's own words: 「That is minutes of work」. It is the cheapest test of the exact number the booth leads with. ⚠ **Critic #65's pre-registration did NOT fire and is re-stated with the same teeth:** it asked for TWO dev laps since `f7ee58d`, and exactly ONE has claimed (0921Z, WFG-254, still running). **Pre-registered for critic #67: if TWO dev laps have completed since `d67de57` and WFG-129 is still `todo`, that is finding #1, and the cause is no longer ordering.** The move passes over **WFG-255** (critic #65's own new row, position 4 now) and over **WFG-117** and **WFG-007**, whose remaining half its own cell marks 「print/laptop: human」. That is the whole skip list.

2. **WFG-256 (P0, science), new this lap, position 3.** The card five judges hear closes on 「저희가 잘하는 것은 방향이 아니라 불의 모양입니다」, and the artifact it rests on declines that attribution in its own words: `disc_null_yeongdeok.json :: what_this_is_not` calls the IoU gap 「joint PLACEMENT-AND-SHAPE skill」. The `direction` block prices the placement half (the model is worse than the stationary disc); **nothing in this repository measures the shape half**, and a search here for a shape-matched, second-moment, principal-axis or rotated null returns nothing. The row runs the rotation null: rotate the model's **own** core about the `t = 0` seed centroid through a pre-registered angle sweep and re-score. Shape and area are the model's own by construction, so the only thing that varies is orientation, and the spread of rotated IoUs is the shape-controlled null for placement. Zero free parameters, one committed npz.

3. **WFG-255 (P0, science) third**, then **WFG-236**, then **WFG-244**, **WFG-245** and **WFG-237**.

⚠ **WFG-234 remains the strongest science row after WFG-129 and WFG-256**, and WFG-256 is its cheap sibling: a persistence null scored against the headline truth, where a bad result is a **named, published failure mode of the whole model class**. Pre-register it in the claim commit. Take it before other P1 science work.

⚠ **The board at `d67de57` after this lap's two rows: 251 rows, 17 P0 `todo`, 111 P1 `todo`**, on critic #64's rule unchanged (split on pipes not preceded by a backslash, priority at cell 2, status at cell 5). **11 rows still render their priority and status in the wrong columns** because of unescaped pipes; that is **WFG-191** and it is the whole answer. Do not publish a board count without the rule that produced it and do not spend a lap reconciling one.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- ⚠ **Do not take WFG-254 from the lap holding it** until its claim is three hours old with no work commit behind it (CHARTER §5b).
- ⚠⚠ **Do not unshallow the clone.** See the note above.
- ⚠ **Do not "fix" WFG-254 by changing any measured value.** Every number in `data/processed/disc_null_yeongdeok.json` is right; only the words naming what they are measured **from** are wrong. `docs/disc_null.md` §4's centroid finding survives the relabelling unchanged and must not be weakened.
- ⚠ **Do not write WFG-254's 「모양과 범위」 disambiguation as an attribution.** Reach is describable and measured; attributing the gap to shape is **WFG-256** and is not yet measured.
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
- ⚠ **Do not edit `docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md` or `docs/auto/finals/RELATED_WORK_PANEL.md` without `make printables` at a new stamp and a re-pointed `MANIFEST.json`** (NH-049). Re-measured by critic #66 at this head in its own process: the kit's seven sources hash **7 of 7** against the tree and the bundle names the newest kit, `WFG_printables_20260911T0706Z.pdf`, 59 pages. ⚠ Critic #66 did **not** independently re-derive the 19-file bundle tally and does not restate it; `tests/test_finals_bundle.py` is green inside this lap's full gate run. This note expires at critic #67 unless that lap re-measures.
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

**Open decisions: 24 for the author** (23 DECISION + 1 BLOCKER), **2 undated** (NH-005, NH-014), plus 5 open FYI. Say 「N of 24, and 2 undated」 rather than a bare number. **NH-046, NH-049 and NH-051 are past due.** **NH-057** is the highest-severity open entry, and **NH-054** gained a measured note this lap. ⚠ **The channel has now produced nothing for FIVE DAYS:** `decisions_seen.json` records `"seen": []`, the newest applied decision is NH-031 of **2026-09-06**, and critic #66 confirmed at the Gmail connector that every thread matching the report subject in the last 14 days carries exactly one message and every one is the loop's own send. That is **WFG-211**, already `todo`, confirmed here and not re-filed. The sprint ends 2026-09-15, **four days out**.

## Critic's last direction note

**2026-09-11T1100Z, critic #66 at `d67de57`. ONE §3b row move: WFG-129 from table position 78 to position 2.** TWO new rows (**WFG-256** P0 at position 3, **WFG-257** P1 at the end); **WFG-252** updated in place rather than duplicated; ONE `fix-before-next-row` item, which is critic #65's, re-measured and still unpaid; **NO new NEEDS_HUMAN entry, deliberately**, for the fourth consecutive lap, with a measured note appended to NH-054 instead.

**The one thing that matters on this page.** For seven consecutive pages this project has been told that the cheapest test of its own headline is minutes away, and for seven pages something more urgent arrived first. This lap removed the last mechanical excuse by putting WFG-129 where the table says it goes. Meanwhile the window produced the sharpest version yet of the pattern every direction page has named: the paper lap corrected the English sentence about what this project is good at, and the Korean sentence five judges actually hear now says something the project's own artifact refuses to say. **WFG-256 is the experiment that would let the card say it honestly. WFG-129 is the row that stops the pattern.**

**Scorecard: Track B 95 to 93, Track A 96 HELD.** Of Track B's two points, one is a new defect (데이터 수집·분석·해석 19 to 18, WFG-256: a second attribution in two windows that the artifact declines) and one is the **withdrawal of an unevidenced point** (연구 목적 19 to 18: critic #65's row raised it from 18 while its own narrative called it HELD, and no lap has published a reason). Track A holds because it has no 데이터 수집·분석·해석 row and its 개발 목적 is a differently worded criterion.

Verified at `d67de57`. **GitHub `auto-gates` run 369 is `success` at this exact head**, and **no run in the 24-hour window concluded `failure`** (three `cancelled`, runs 344, 352 and 368, each superseded by the next push), so CHARTER §4b sets no finding #1 for the fifteenth consecutive lap. `gates.py --mode full` exits **0** on its FIRST run in this sandbox (2097 passed, 65 skipped, 3 xfailed, 386.5 s), `--assert-reported --base ba76b8c` exits 0 over 68 substantive paths, and **every dev report in the window records `Reviewed by:`** (ten checked, all `subagent`). The clone is SHALLOW at **50** commits and was deliberately NOT deepened; no ancestry claim is written anywhere in this lap.
