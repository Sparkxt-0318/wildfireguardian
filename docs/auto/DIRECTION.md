# Direction — where the project is going, on one screen

*Rewritten 2026-09-10T1817Z by the research routine (CHARTER §14) and re-checked 2026-09-10T2305Z by critic #62 at `f93af93`. The dev routine reads this before it claims a row; the critic re-checks it after every dev lap, at most one reorder per lap, with a reason. Only the most recent critic note is kept, as §14 specifies. **Critic #62 spent ZERO reorders**, the sixth consecutive critic lap to spend none.*

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a per-point walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive. Its defensible contribution is not forecast accuracy, and **as of 2026-09-09 it is not the architecture either** — it is the **output object and its measured limits**: a time-dependent decision per point, with a page saying how wrong it can be.

⚠ Bokade et al. published this project's whole pipeline — ML spread forecast feeding dynamic evacuation routing away from *actively predicted* fire — on **2026-09-09** (10.5281/zenodo.22668357, opened; `docs/auto/research/RUN_2026-09-10.md` §2.1). They evaluate **none** of it. This project ships `docs/disc_null.md`, `docs/oracle_gap.md` and a withdrawn-claims registry. **Claim the measurement, never the architecture.**

⚠⚠ **And the thesis has a bill attached that critic #62 measured: if the contribution is the output object, the object's own NAME is the claim, and the printed kit says it two ways.** 지점 단위 on the screen, the README, the panel's opening paragraph and the bank at `:1238`; 가구 / 집 on the panel at `:45-46`, `:73-74`, `:119-120` and on a **T0** bank card at `:657-659` and `:667`. `WC-013` withdrew the second register on 2026-09-10 and no gate can see any of these six spellings. **WFG-243** and **WFG-240** are that repair, and they are why the first row of the sprint's last five days is a printables lap.

## Before any row: this lap's `fix-before-next-row` items

**ZERO, and critic #62 measured it rather than inheriting it.** No gate is red: `gates.py --mode full` exits **0** at `f93af93` (**2054 passed**, 63 skipped, 3 xfailed, pytest 319.3 s) and GitHub `auto-gates` run **351** is `success` at this exact head. The two defects this lap found are **WFG-243** (pays the NH-049 printables rebuild) and **WFG-244** (on `docs/MODEL_CARD.md`, which is on none of §14b's listed surfaces). Neither is minutes on a listed surface. Take the top row directly.

## Next three rows, and why each is next

Table order at `f93af93`. **This page's naming power is spent on ONE thing this run: it names a BUNDLE of four rows as the first lap, and that bundle is already table order, so no row moved.** WFG-233 closed at `e8b6e01`, which removes the row this page named first for three runs.

1. **ONE lap takes WFG-235 + WFG-240 + WFG-241 + WFG-243, in that order, and pays `make printables` ONCE.** All four edit `docs/auto/JUDGE_QA.md` or `docs/auto/finals/RELATED_WORK_PANEL.md`, the two hashed printables sources, and each alone costs a rebuild at a new stamp plus a re-pointed `release/kcf-finals-2026/MANIFEST.json` (**NH-049**). Paying that once instead of four times is worth a whole lap of the five that remain. **Two of the four are the withdrawn household register on paper and on a card said from memory** (WFG-240, WFG-243), one is the missing 관련연구 card for the Bokade preprint (WFG-241), and one is the Q36 null card (WFG-235). ⚠ If the lap cannot finish all four, finish **WFG-243 and WFG-240 together** and rebuild: they are the same defect in two files and fixing one alone leaves the kit contradicting itself.

2. **WFG-236 (P0, KCF) second — unchanged from critic #60 and #61.** `docs/disc_null.md:20-21` and `docs/oracle_gap.md:180-181` both assert in bold that nothing said what **0.394** should be compared with, while `README.md:520-522` and `:888-891` have compared it to Rothermel's **~0.09** and called it 「약 4배」 for months. The row repairs the two `docs/` sentences and cross-links; whether the README's framing moves is **NH-055**, the author's. It pays no rebuild, so it is the natural second lap.

3. **WFG-244 (P0, KCF) third, and it is minutes.** The block written onto the submitted-document sentence at `e8b6e01` asserts 「Neither count has a second, independent derivation in this repository」 and 「its 17 agrees … by coincidence rather than by derivation」, while `data/processed/spread_v2/audit.json :: fires[5]` holds `detections_csv` 17, `detections_in_grid` 17, **`total_positives` 8** and `spread_cells_total` 8. Two unmeasured provenance claims on the one text bound for a judged document. Do not cite that file; name what it contains, which `:553-556` already does for the 17.

⚠ **WFG-237 and WFG-234 are next after those.** WFG-237 is `docs/disc_null.md` §4's 3,646.1 m against 1,124.8 m, the magnitude the TL;DR's caveat never had, living in one file nothing points at. **WFG-234 remains the strongest science row**: a persistence null scored against the headline truth, where a bad result is a **named, published failure mode of the whole model class** (Bokade et al.'s own headline negative), not a private embarrassment. Pre-register it in the claim commit. **Take it before other P1 science work.**

⚠ **The board's own count, re-derived at this head after this lap: 238 rows, 98 P0 (77 written `**P0**`, 21 bare `P0`), 18 P0 `todo`, 106 P1 `todo`.** Critic #61's published 「236 / 94 / 15」 is right in its parts and mixed in its head: at `be39dea`, the head it reviewed, the board is **233 / 94 / 15**, and **236** is the count after that lap's own three rows landed. Use this head's numbers, and state the head with them. **WFG-191's column-shift defect is real and separate** and does not move this count.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- ⚠⚠ **Do not fix ONE of the six household-register lines and rebuild.** `docs/auto/JUDGE_QA.md:657-659` and `:667`, `docs/auto/finals/RELATED_WORK_PANEL.md:45-46`, `:73-74` and `:119-120` are one defect in two printed files, and `docs/global_portability.md:147` and `docs/SESSION14_REPORT.md:178` carry it off the kit. Register the spelling in `docs/auto/withdrawn_claims.json` in the **same lap** (CHARTER §3.5c), blast radius measured first.
- ⚠ **Do not touch** Q20a's definition of 「가구」 as one OSM walk-graph node (`:968-975`), Q16's 「가구 단위 폐쇄 시각」 (`:600`), Q16a's `:659-661` sentence about what other systems' **published material** does not show, or `:680-681`'s ⭕/❌ pair. `WC-013` preserves all four by name.
- ⚠ **Do not claim the architecture as the contribution** — forecast-driven evacuation routing was independently published on 2026-09-09. Claim the output object and its measured limits. **WFG-239** writes the sentence.
- ⚠ **Do not write the 「위험 구역」 / 「잠재적 위험 구역」 zoning framing** of the Korean evacuation doctrine. Recorded UNVERIFIED. Confirm at a document or do not write it.
- ⚠ **Do not compare accuracy with any domestic system or study** — NIFoS, G-DAPS, and the Kangwon National University DL model (**NH-056**). The differentiator is the output object.
- ⚠ **Do not quote `2.5360` or the pair `0.3941 / 0.1554` on any judge-facing surface without `2.2044` and `0.2577 / 0.1169` in the same block** (`docs/disc_null.md:119-120`, `docs/oracle_gap.md:194`).
- ⚠ **Do not edit `README.md`'s IoU bullet (`:520-522`, `:888-891`) while NH-055 is open**, and do not delete the `~0.09` Rothermel comparison in either direction.
- ⚠ **Do not edit `README.md`'s TL;DR lead in either direction while NH-054 is open.**
- ⚠ **Do not edit `docs/auto/JUDGE_QA.md` or `docs/auto/finals/RELATED_WORK_PANEL.md` without `make printables` at a new stamp and a re-pointed `release/kcf-finals-2026/MANIFEST.json`** (NH-049). Re-measured by critic #62 at `f93af93`: the kit's seven sources hash **7 of 7** against the tree. This note expires at critic #63 unless that lap re-measures and re-states it.
- ⚠ **Do not write 「the fire stopped growing at 333 minutes」.** No observation exists between 0 and 333 minutes (WFG-230).
- ⚠ **Do not "fix" 「household-level」** in `README.md:3`, `CITATION.cff:5`, `src/wildfireguardian/__init__.py:1` or `paper/manuscript.md:1` — they name the **application** (`paper/GAPS.md:389`; WFG-231 moves the ruling).
- ⚠ **Do not cite `data/processed/spread_v2/audit.json` for any number.** It carries `LEGACY_DO_NOT_CITE.md`. Naming what it contains in order to warn a lap off it is not citing it (WFG-244).
- ⚠ **Do not rebuild `data/processed/timeline_roles/timeline_roles.json` from a deepened clone** (WFG-217; deadline 10-16).
- ⚠ **Do not read a green withdrawn-claims gate as a corrected register.** Six spellings of `WC-013` stand at this head and no gate sees one of them (**WFG-243**, **WFG-240**).
- ⚠ **Do not weaken 「실제 확산면으로 만든 출동 지시서는 아직 없습니다」** on any surface. It is true, it is why the object is trusted, and only the author's laptop can change it (**NH-057**, **WFG-242**).
- ⚠ **Do not tell a judge the repository does not know of anyone who built the same thing.** Since 2026-09-10 it does (**WFG-241**); `docs/auto/JUDGE_QA.md:1246-1247` has not caught up.
- **Do not settle 「상한」 / 「upper bound」 in any lap** (NH-053 open). Describe the mechanism.
- ⚠ **Do not put a margin value (9, 27, 5, 19, 86) on any judge-facing surface** while NH-032, NH-034 and NH-052 are open. Anchor on the two section headers, not on the digits.
- ⚠ **Do not add a word to `paper/manuscript.md` without trimming one** (NH-037, due 2026-09-10, open).
- **Do not change `mr_uiseong_fa_exceeds_budget`** (NH-031 A; registry half is WFG-122).
- **Do not refit anything, and do not regenerate a committed artifact** (CHARTER §3 rule 2). This blocks P-003 and P-004 in `IDEAS_PARKED.md` until after the finals.
- **Do not re-open the AI-disclosure question** (NH-008 closed; CHARTER §9).
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13-§14).
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or `docs/NUMBERS.json`** (CHARTER §13, §3 rule 5b).

## Readiness and open decisions

`docs/auto/KCF_READINESS.md` stands at **8 of 11**, re-counted by critic #62 at `f93af93` from the
checklist table rather than inherited: R1, R2, R4, R5, R6, R7, R8, R9 tick; R3, R11 and R12 do not;
R10 was withdrawn 2026-09-04. ⚠⚠ **ZERO lines ticked for the NINETEENTH consecutive critic lap, and
unlike the last window this one HAD judge-facing artifacts to tick against** (`docs/MODEL_CARD.md`
changed, `web/finals.html` was rebuilt). R12 is the author's (NH-014); R3 is `blocked(NH-046)`;
R11's WFG-024 is held by §14b until R3 ticks, so **106 P1 rows wait on one reply**.

**Open decisions: 24 for the author** (23 DECISION + 1 BLOCKER), **2 undated** (NH-005, NH-014),
plus 5 open FYI. Say 「N of 24, and 2 undated」 rather than a bare number. **NH-046 was due
2026-09-10 and it is already 2026-09-11 on the author's clock**; NH-049 and NH-051 come due
2026-09-11. **NH-057** is the highest-severity open entry. The sprint ends 2026-09-15, five days out.

## Critic's last direction note

**2026-09-10T2305Z, critic #62 at `f93af93`. ZERO §3b reorders, the sixth consecutive critic lap to
spend none, and ZERO `fix-before-next-row` items, measured. The one direction change is that this
page no longer names a single first row: it names a BUNDLE of four (WFG-235, WFG-240, WFG-241,
WFG-243), because all four edit a hashed printables source and the rebuild is the expensive part,
not the prose. That costs no reorder because table order already puts WFG-235 first now that
WFG-233 has closed. TWO new rows (WFG-243 P0 KCF, WFG-244 P0 KCF) and ONE existing row corrected in
place (WFG-240, which named two lines of its file when there are four). NO new NEEDS_HUMAN entry,
deliberately: both findings are agent-doable and nothing here needs a decision that is not already
open. Scorecard: Track B 95 -> 94 and Track A 96 -> 95, both on 제출 자료 18 -> 17, because one
제출 자료 row closed and two opened, and the larger of the two is on the paper a judge is handed and
on a card the student says from memory.**

Verified at `f93af93`. `gates.py --mode full` exits **0** (**2054 passed**, 63 skipped, 3 xfailed,
pytest 319.3 s); `baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is
NH-029 and §3d working. **GitHub `auto-gates` runs 332 to 351: 14 `success`, 6 `cancelled`, ZERO
`failure`**, with **351 green at this exact head**, so CHARTER §4b sets no finding #1 for the
eleventh consecutive lap. `--assert-reported` replayed pairwise over all seven pushed heads in the
window exits 0 at every step. The printed kit hashes **7 of 7** sources and the release bundle **19
of 19** against their sources, which is how WFG-243 is provable rather than suspected. The clone
opened SHALLOW at 51 commits and was `--unshallow`ed to **740** before anything was counted.
