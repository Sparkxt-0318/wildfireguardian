# Direction — where the project is going, on one screen

*Rewritten 2026-09-10T1817Z by the research routine (CHARTER §14), on critic #60's page of 2026-09-10T1657Z. The dev routine reads this before it claims a row; the critic re-checks it after every dev lap, at most one reorder per lap, with a reason. Only the most recent critic note is kept, as §14 specifies. This run spent **ZERO** reorders.*

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a per-point walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive. Its defensible contribution is not forecast accuracy, and **as of 2026-09-09 it is not the architecture either** — it is the **output object and its measured limits**: a time-dependent decision per point, with a page saying how wrong it can be.

⚠ **That second sentence is the one thing this run changed, and it changed because of evidence, not taste.** Bokade et al. published this project's whole pipeline — ML spread forecast feeding dynamic evacuation routing away from *actively predicted* fire — on **2026-09-09** (10.5281/zenodo.22668357, opened; `docs/auto/research/RUN_2026-09-10.md` §2.1). They evaluate **none** of it. This project ships `docs/disc_null.md`, `docs/oracle_gap.md` and a withdrawn-claims registry. **Claim the measurement, never the architecture.** This is the second novelty narrowing in two research runs (WFG-198 was the first) and both made the claim smaller and harder to attack.

## Before any row: this lap's `fix-before-next-row` items

**ZERO.** This is a research lap: it touched no code, no data, no figure and no registry entry, so it can create no gate failure and preempts nothing. CHARTER §14b's test is unchanged and belongs to the next critic lap.

## Next three rows, and why each is next

Table order at `9a45b2e`, carried from critic #60 unchanged. This page's naming power (§14) is spent only on the ordering below; no table row moved.

1. **WFG-233 (P0, KCF, minutes plus one registration) — unchanged, and still first.** `docs/MODEL_CARD.md:524-525` is the one sentence written to be pasted into the **submitted** 작품설명서, and it explains the weak `gangneung_2023` fold with 「탐지 약 17건」 while `:52-53`, `:86` and `docs/fold_sizes.md:10` explain the same fold with **8 positive cells**. `README.md:489` already writes both correctly. Minutes, no printables rebuild.

2. **WFG-236 (P0, KCF) second — unchanged from critic #60.** `docs/disc_null.md:20-21` and `docs/oracle_gap.md:180-181` both assert in bold that nothing said what **0.394** should be compared with, while `README.md:520-522` and `:888-891` have compared it to Rothermel's **~0.09** and called it 「약 4배」 for months. The row repairs the two `docs/` sentences and cross-links; whether the README's framing moves is **NH-055**, the author's.

3. **WFG-237 (P0, science) third, with WFG-235 riding along — unchanged.** `docs/disc_null.md` §4's 3,646.1 m against 1,124.8 m is the magnitude the TL;DR's caveat never had, and it lives in one file nothing points at. WFG-237 is the document half, WFG-235 the Q36 card half, which pays the `make printables` rebuild NH-049 names.

⚠ **WFG-234 rose in value this run and is the strongest science row behind those three.** It asks for a persistence null scored against the headline truth, and warns persistence may **beat** the model. Bokade et al. report exactly that as their headline — 「neither a recurrent nor a non-recurrent network learns to advect fire past the persistence baseline」 — and abandoned learned advection because of it. So a bad result there is a **named, published failure mode of the whole model class**, not a private embarrassment. The row now carries that framing and says to pre-register it in the claim commit. **Take it before other P1 science work.**

⚠ **A caution about counting this page's own rows.** Critic #60 recorded **P0 `todo` = 15** at `71e95ee`. At `9a45b2e` a strict column-2 parse finds **21 P0 rows, 3 with a `todo` cell**; a 「P0 anywhere」 parse finds **108 rows, 28 with a `todo` cell`**. **This run does not claim which is right and publishes no fourth number** — the likely cause is **WFG-191**'s documented column-shift defect. Raised because this is the page a dev lap reads to choose work. Resolving it is the critic's direction check or WFG-191.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- ⚠ **Do not claim the architecture as the contribution** — forecast-driven evacuation routing was independently published on 2026-09-09 (thesis note above). Claim the output object and its measured limits. **WFG-239** writes the sentence.
- ⚠ **Do not write the 「위험 구역」 / 「잠재적 위험 구역」 zoning framing** of the Korean evacuation doctrine. A search summary described it; it is **not** on the government page this run opened, and is recorded UNVERIFIED. Confirm at a document or do not write it.
- ⚠ **Do not compare accuracy with any domestic system or study** — NIFoS, G-DAPS, and now the Kangwon National University DL model (**NH-056**). The tasks differ and no metric was read. The differentiator is the output object.
- ⚠ **Do not quote `2.5360` or the pair `0.3941 / 0.1554` on any judge-facing surface without `2.2044` and `0.2577 / 0.1169` in the same block** (`docs/disc_null.md:119-120`, `docs/oracle_gap.md:194`).
- ⚠ **Do not edit `README.md`'s IoU bullet (`:520-522`, `:888-891`) while NH-055 is open**, and do not delete the `~0.09` Rothermel comparison in either direction.
- ⚠ **Do not edit `README.md`'s TL;DR lead in either direction while NH-054 is open.**
- ⚠ **Do not edit `docs/auto/JUDGE_QA.md` without `make printables` at a new stamp and a re-pointed `release/kcf-finals-2026/MANIFEST.json`** (NH-049).
- ⚠ **Do not write 「the fire stopped growing at 333 minutes」.** No observation exists between 0 and 333 minutes (WFG-230).
- ⚠ **Do not "fix" 「household-level」** in `README.md:3`, `CITATION.cff:5`, `src/wildfireguardian/__init__.py:1` or `paper/manuscript.md:1` — they name the **application** (`paper/GAPS.md:389`; WFG-231 moves the ruling).
- ⚠ **Do not rebuild `data/processed/timeline_roles/timeline_roles.json` from a deepened clone** (WFG-217; deadline 10-16).
- ⚠ **Do not write 「가구 단위」 or "per-household" about the COMMITTED dispatch sheets** (`WC-013`); the corrected wording is **지점 단위**, `README.md:220-251` is the model.
- **Do not settle 「상한」 / 「upper bound」 in any lap** (NH-053 open). Describe the mechanism.
- ⚠ **Do not put a margin value (9, 27, 5, 19, 86) on any judge-facing surface** while NH-032, NH-034 and NH-052 are open. Anchor on the two section headers, not on the digits.
- ⚠ **Do not add a word to `paper/manuscript.md` without trimming one** (NH-037, due 2026-09-10, open).
- **Do not change `mr_uiseong_fa_exceeds_budget`** (NH-031 A; registry half is WFG-122).
- **Do not refit anything, and do not regenerate a committed artifact** (CHARTER §3 rule 2). This blocks P-003 and P-004 in `IDEAS_PARKED.md` until after the finals.
- **Do not re-open the AI-disclosure question** (NH-008 closed; CHARTER §9).
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13-§14).
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or `docs/NUMBERS.json`** (CHARTER §13, §3 rule 5b). This run added several — TFFM's exponents, the embargoed dryness study, the 118-event Korean archive — and **none** may travel.

## Readiness and open decisions

`docs/auto/KCF_READINESS.md` stood at **8 of 11** at critic #60's count (`71e95ee`): R1, R2, R4, R5, R6, R7, R8, R9 ticked; R3, R11, R12 not; R10 withdrawn 2026-09-04. **This research lap ticked none and could tick none** — it changes no judge-facing artifact by design. R12 is the author's (NH-014); R3 is `blocked(NH-046)`; R11's WFG-024 is held by §14b until R3 ticks.

**Open decisions: 23 for the author** after this run (22 at critic #60's count, plus **NH-056** filed here), **2 undated** (NH-005, NH-014) — say 「N of 23, and 2 undated」 rather than a bare number. **NH-046 was due 2026-09-10**, i.e. today at critic #60's reading; **NH-049 and NH-051 are due 2026-09-11.** The sprint ends 2026-09-15, five days out.

## Critic's last direction note

**2026-09-10T1657Z, critic #60. ZERO §3b reorders, the fourth consecutive critic lap to spend none. ZERO `fix-before-next-row` items, measured rather than assumed: the window's sharpest defect is on two `docs/` pages that are on no §14b surface and in neither hashed set. THREE new backlog rows (WFG-236 P0 KCF, WFG-237 P0 science, WFG-238 P1 infra) and ONE existing row corrected in place (WFG-235, which as filed told the next lap to write onto a T0 card the number its own day forbids quoting alone). ONE new NEEDS_HUMAN entry (NH-055, the README's 「약 4배」 against today's 2.2×, four options, nothing proposed for deletion). Scorecard: Track B 94 → 96 (데이터 수집·분석·해석 UP to 20 on critic #58's pre-registration, PAID by WFG-228; 창의성 UP to 19). Track A 96 → 97 (창의성 UP to 19 on the identical criterion). 제출 자료 HELD at 19 on both tracks: WFG-233 is still open and WFG-236 is new, against a window that shipped the seed-removed correction onto both pages and into the band on all 84 keys.**

Verified at `71e95ee`. `gates.py --mode full` exits **0** (**2041 passed**, 64 skipped, 3 xfailed, pytest 315.2 s); `baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029 and §3d working. **GitHub `auto-gates`, runs 294 to 338: 45 runs, 36 `success`, 9 `cancelled` and ZERO `failure`**, with **338 green at this exact head**, so CHARTER §4b sets no finding #1 for the ninth consecutive lap.
