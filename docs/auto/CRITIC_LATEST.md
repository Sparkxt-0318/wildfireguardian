# CRITIC_LATEST — critic #58, 2026-09-10T1120Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head: `d3ca754`, and
every measurement below was taken at that head in this clone unless it says otherwise. ⚠ This clone arrived
**SHALLOW at exactly 50 commits** again, which is the same coincidence critic #57 hit: 50 commits is almost
exactly the 24-hour window, so `git log --since` would have returned the whole clone and truncated silently.
I ran `git fetch --unshallow` before counting anything: `git rev-parse --is-shallow-repository` now answers
**`false`** and `git rev-list --count HEAD` answers **712**, so the window below is a real 24 hours and the
ancestry statements here are licensed under CHARTER §4. Full report:
`docs/auto/reports/2026-09-10T1120Z-critic.md`.*

## `fix-before-next-row`: ONE. `docs/oracle_gap.md:233`, and it is one sentence

**Rewrite the last clause of the second bullet of §7 so that it names the registered spelling and does not
carry a key count. Change nothing else on the page.** It is prose, it writes no number, it registers
nothing, it rebuilds nothing.

**What is wrong.** `docs/oracle_gap.md:232-233` reads:

> Anyone quoting 0.394 as "what the forecast buys" has misread it, and that phrasing is
> registered as forbidden on all ten keys.

Both halves of that clause are false, and they are false in two different ways. Measured here in one
process at `d3ca754`, not read from any report:

| check | answer |
|---|---|
| `og_yeongdeok_*` keys in `docs/NUMBERS.json` | **30**, not ten |
| of those 30, how many carry a `forbidden_phrasings` list | **30 of 30** — so 「all of them」 is right and only the number is wrong |
| is the quoted string 「what the forecast buys」 a registered `forbidden_phrasings` entry on ANY key | **no — zero keys** |
| the nearest registered spelling on those keys | 「**this measures what the model buys**」, one of seven, identical on all 30 |
| where 「forecast buys」 does occur in the registry | 75 `caveat` fields and 1 `derivation`, all of them on `pp_uiseong_*` keys, never as a forbidden phrasing |

So the sentence claims a machine protection that does not exist **for the string it puts in quotation
marks**, on the page four judge-facing surfaces send a judge to when they ask what the comparison is worth.
That is 「사용된 자료에 대한 출처 명기」, a named criterion of a 20-point row on **both** rubric tables,
and it is the same class of defect critic #57 fixed on line 39 of this same file one window ago: a prose
pointer that does not match the thing it points at.

⚠⚠ **The paragraph's ARGUMENT is correct and must not be softened.** 0.394 is not what the forecast buys,
and §7's job is to say so. What is wrong is only the appeal to the registry. Do not delete the sentence,
do not hedge the claim, and do not open a `WC-###`, because nothing is being withdrawn.

**How to write the repair, and this matters more than the repair.** ⚠ **Do NOT write 「on all thirty
keys」.** This document's own §「Registry」 line at `:6-9` says, in its own words, 「a key count written into
prose goes stale the next time the registrar grows」 — and the sentence at `:233` is that exact mistake, made
226 lines below the warning, by the same page. Write it with **no count**: name the prefix
(「every `og_yeongdeok_*` key」) and quote the registered spelling verbatim, e.g.

> Anyone quoting 0.394 as what the forecast buys has misread it. The spelling
> 「this measures what the model buys」 is registered as a forbidden phrasing on every
> `og_yeongdeok_*` key, so a document that writes it fails `make verify`.

If a lap wants the exact words 「what the forecast buys」 protected as well, that is a **registry change and
a separate row**, not this edit.

**Why it is a preemption and not a row.** Re-verified at this head rather than inherited from critic #57:
`docs/oracle_gap.md` is in **no** `SOURCES` list of the printed kit (the seven are `BOOTH_SETUP.md`,
`DEMO_SCRIPT_5MIN.md`, `JUDGE_QA.md`, `submission_reconciliation.md`, `DETECTION_FLOOR_CARD.md`,
`creativity_card.md`, `RELATED_WORK_PANEL.md`), so no kit rebuild is needed; and the four test files that
mention the document (`test_oracle_gap.py`, `test_oracle_card_on_the_finals_screen.py`,
`test_readme_round4.py`, `test_future_aware_attribution.py`) mention 「forecast buys」 only inside two
comment lines and pin no sentence of §7. The edit cascades into no gate.

## The three larger findings, filed as rows, NOT as preemptions

All three are judge-facing and all three are larger than minutes, so under CHARTER §14b they are rows.
`docs/auto/DIRECTION.md` names the first one as the row to claim after WFG-226.

**1. WFG-228 (P0) — the headline of the new anchor document has no null model, and the repository already
ships the machinery for one.** `docs/oracle_gap.md` §4 concludes 「the model gets the size nearly exactly
right and the place substantially wrong」 on **IoU 0.394**, and that conclusion now stands on the README
TL;DR, the finals screen's first 알려진 한계 card and JUDGE_QA Q36 at tier T0. Nothing in the repository
says what 0.394 should be compared with. `src/wildfireguardian/validation/baselines.py` implements
`run_persistence_baseline` (`:44`) and `run_isotropic_baseline` (`:68`); `docs/MODEL_CARD.md` §「Footprint
IoU」 gives ~0.07 for the new-ring-only metric and **nothing** for the forward-sim envelope on any canvas.
An ML-reviewer or statistician judge asks 「0.394는 무엇에 견준 값입니까?」 and the honest answer today is
that nobody measured. The cheapest null with **zero free parameters** is an area-matched disc, described in
the row.

**2. WFG-229 (P0) — the schedule document now publishes the one number that answers 「이거 학생이 만든 게
맞습니까?」, and the card the student drills from does not carry it.** `docs/auto/finals/TIMELINE_ROLES.md:81`
states 「`Co-Authored-By: Claude` 트레일러 **513개** (전체 662개 중)」, sourced from
`timeline_agent_trailer_commits` and `timeline_total_commits`. That is **77.5 %** of the tree, and the
document that says it is the repository's answer to a **named sub-criterion of a 20-point row on both
tables** (「일정 및 팀원 역할 배분의 타당성」). `docs/auto/JUDGE_QA.md` Q29 · T0 answers the question well
in words and names **no number at all**; `grep -c 513 docs/auto/JUDGE_QA.md` answers 0. So the student is
drilled on a qualitative answer and the judge is holding a quantitative one.

**3. WFG-230 (P0) — §4's four slices are all graded against footprints within 5 % of each other, and the
document says so for three of them.** `docs/oracle_gap.md:124-127` says 「Three of the four slices are
scored against the same observation; only `t = 720` matches a later one」, which reads as though the fourth
escapes the constant-denominator problem. Counted from `data/processed/routing_demo_canonical.npz` here:
the observed cumulative footprint is **249 / 937 / 987 / 988 / 1021 / 1023** cells at
**0 / 333 / 1005 / 1480 / 1812 / 2403** minutes. The `t = 720` slice's denominator (987) is **5.3 %** larger
than the one the other three use (937). The fire's FIRMS-detected footprint is **91.6 %** complete at the
first post-ignition observation, so this fire gives the comparison **one informative frame**, not four.
That strengthens the document's own caveat rather than weakening it and it should be written down.

## `Do NOT edit` notes — one re-stated after re-checking, one NOT re-stated

CHARTER §14c: such a note names the exact lines and the measurement behind it, and expires at the next
critic lap unless that lap re-states it after re-checking.

**RE-STATED, re-measured at `d3ca754`. Do not put a margin value (9, 27, 5, 19, 86) anywhere in the
README's Round-4 section 1 while NH-032, NH-034 and NH-052 are open.** Measured by the two section headers
rather than copied, which is critic #57's instruction and it was right to give it: 「### 1. 가장 강한
주장에 「공정한 상대」를 세웠습니다」 opens the block and 「### 2. 철회한 주장이…」 closes it. That pair sat
at `:263-342` at `7dabdef`, `:270-349` at `9b7d21c`, `:274-353` at `16e6824` and **`:274-354` at
`d3ca754`**. ⚠ **The two ends moved differently this window, which is the first time they have**: the
opening header held at `:274` and the closing header moved down one line, so the block **grew** rather than
slid. A lap that had memorised the pair 「274 and 353」 would now protect one line too few at the bottom.
The single 「구체적인 margin 값들은 부스에서 말하지 않습니다」 line is at **`:340`**, unmoved.
**Anchor on the two headers, not on the digits.**

**NOT re-stated, because the defect it guarded is gone.** Critic #57's note 「Replace
`scripts/run_forward_sim_region.py` with `scripts/build_canonical_hazard.py` on `docs/oracle_gap.md:39`」 was
cleared by the 0952Z dev lap in the same commit as WFG-225. Verified here:
`grep -n run_forward_sim_region docs/oracle_gap.md` returns **nothing**, `:39` now cites
`scripts/build_canonical_hazard.py` (`:129-130`), and NH-053's verbatim quote at
`docs/auto/NEEDS_HUMAN.md:3236` was annotated in place at `:3242` rather than edited, which is CHARTER §3.7
done correctly. The note expires and is not carried forward.

## What this lap verified and found clean

- **`gates.py --mode full` exits 0 at `d3ca754`** — **2016 passed**, 64 skipped, 3 xfailed, pytest 299.1 s,
  **up 31 tests in one window** and the suite is **183 seconds faster** than critic #57 measured, which is
  worth knowing before someone reads a slow run as a regression. `baseline-verify` WARNs on the two
  git-ignored `data/raw/**` contracts, which is NH-029 and CHARTER §3d working as designed.
- **GitHub `auto-gates`, runs 301 to 327: 27 runs, 20 `success`, 7 `cancelled` (306, 310, 312, 316, 317,
  320, 326 — each superseded by the next push within minutes) and ZERO `failure`**, with run **327 green at
  this exact head**. CHARTER §4b sets **no finding #1** for the seventh consecutive lap.
- ⚠ **`curl` against `api.github.com` WORKS in this sandbox and returned HTTP 200.** WFG-119 and this
  routine's own history record it as 403. It is not 403 today. The observation is recorded on WFG-119
  rather than acted on, because a capability that flips between laps is not something to build on.
- **All eight** dev reports in the window record `Reviewed by:`, all eight name `subagent`, and **seven of
  the eight record `block`** and spend commits acting on it (the eighth, 0703Z, records `pass`).
- **Every push in the window carried a report.** `gates.py --assert-reported` run over each of the twelve
  consecutive pushed heads from `16f3525` to `d3ca754`: **twelve OK, zero missing**.
- **WFG-225 shipped as the 0952Z report says it did, and I checked the built file rather than the
  template.** The caveat string 「예산 초과는 두 팔에 서로 다른 시간 규칙…」 appears **twice** in
  `scripts/finals.template.html` and **twice** in `web/finals.html`, which is WFG-109's lesson obeyed, and
  `release/kcf-finals-2026/MANIFEST.json` is re-pointed.
- ⚠⚠ **THE OBJECTION I EXPECTED TO FIND, AND IT IS NOT THERE.** `scripts/build_canonical_hazard.py:137-145`
  chooses the canonical canvas by **sweeping westward extensions until the simulated envelope clears the
  in-grid guard** — that is, the canvas was fitted to contain the *prediction*. If the *observation* ran
  past that canvas, the 「burned, not predicted」 count of 403 would be a floor and IoU 0.394 would be
  optimistic. Measured directly from the npz: **neither stack touches any grid border in any slice.**
  `obs_stack` occupies rows 71-121, cols 6-96; `haz_stack`'s `p >= 0.5` core occupies rows 70-120, cols
  7-96; border cell count is **0** for all eleven slices, on a 181 × 156 grid. No clipping, so the
  decomposition is not truncated by the canvas choice. Recorded here because a judge will ask it and the
  answer is now in a file.
- **§4's whole result table re-derives from the artifact, exactly.** 952 / 937 / 534 / 418 / 403 / 0.3941 /
  1.016 all match `data/processed/oracle_gap_yeongdeok.json` and so do all four rows of the per-slice table.
- **`factchk` on the window's new prose about the world: nothing to correct.** The window adds no new
  external citation and no new URL to any judge-facing surface. The changes to
  `docs/evidence/greenpeace_2026_survey.md`, `docs/firefighter_consultation.md` and the two knowledge notes
  are all WFG-222 / WC-013 unit-word corrections carrying dated ⚠ annotations, and the research note's
  external figures (NIFoS 30 %, 5 m, 76 % → 88 %; G-DAPS 30-minute steps, 589 facilities) are pre-existing
  lines re-emitted under a correction banner.
- **The 「household-level」 hits in `README.md:3`, `CITATION.cff:5` and `src/wildfireguardian/__init__.py:1`
  are NOT a WC-013 breach, and the ruling already exists.** `paper/GAPS.md:389` records the distinction the
  paper routine drew: 「routing **for** household-level wildfire evacuation」 names the *application*, not a
  per-household *result*, and `:375` records that no registered spelling covers it. WC-013's own
  `spellings` block explains, at length, why it deliberately anchors on 「가구 단위」 **plus** the
  output-object phrase and never on the bare term. The lines are correct. ⚠ The ruling lives only in
  `paper/GAPS.md`, which is where the next lap sweeping for 「household」 will not look — **WFG-231**.

## Direction

**ZERO §3b reorders, for the second consecutive critic lap.** The rows a dev lap should meet first are
WFG-226 (filed by critic #57, still `todo`) and WFG-228 (filed here), and a newly filed row is not a move.
Both are filed **in the table like any other P0 row, not at position 1**, and `docs/auto/DIRECTION.md`
names them instead. ⚠ **This is the same deliberate departure from the stored prompt that critic #57 made,
made for the same reason and not quietly:** the prompt says 「a P0 row at position 1」 and **NH-051 proves
that mechanic is NH-038 option D's while the prompt cites option B**, whose own words put the row 「in the
table like any other」. NH-051 is open. If the author answers D, moving these rows up is one edit.

**Readiness: 8 of 11, ZERO ticked, FIFTEENTH consecutive critic lap.** Re-counted from the checklist table
at `docs/auto/KCF_READINESS.md:1825-1836` (its position after this lap's own append) rather than inherited: R1, R2, R4, R5, R6, R7, R8, R9 ticked;
R3, R11, R12 not; R10 withdrawn 2026-09-04. **R3 is `blocked(NH-046)`, NH-046 came due 2026-09-10 and is
now one day past due**, R11's WFG-024 is held behind R3 by CHARTER §14b, and R12 is the author's (NH-014).
**Five days of sprint remain.** This is a finding about the loop's direction, not about the product, and
it is the same finding fifteen times; the measurement is appended to NH-046 rather than filed again.

**Open decisions: 20 for the author (19 DECISION + 1 BLOCKER), plus 5 FYI, and 13 are at or past their
stated date** — parsed here rather than inherited, over `^## NH-\d+ · (DECISION|BLOCKER) · open` with the
date read from the same header line. The overdue list is **NH-032, 034, 045 (due 09-08), NH-035, 038, 043,
044 (09-09), NH-036, 037, 042, 046, 048, 050 (09-10)**. ⚠ **My own first pass said 14 and was wrong**: it
counted NH-049, which is due **09-11** and is not overdue. Two open entries carry **no date at all**
(NH-005, NH-014) and fall out of any date-based count, which is worth knowing before the next lap publishes
a fifteenth version of this number — WFG-107's shape, sixth recorded instance. The generated block in the
report email is the authority if the two ever disagree.

**Scorecard: Track B 95 HELD on two moves that offset, Track A 94 → 95.** 제출 자료 UP to 20 on Track B
and to 18 on Track A (the finals screen now states the budget-rule asymmetry in the panel that prints the
count, and the oracle page's script pointer is fixed); 데이터 수집·분석·해석 DOWN to 19 on Track B only,
on WFG-228 — the new anchor document's headline statistic has no comparator, which is
「수학 및 통계 방법의 적절한 적용」. Track A has no such row, which is why the same defect moves one table
and not the other. **Pre-registered:** 데이터 수집·분석·해석 returns to 20 when WFG-228 lands a null
figure with its caveat, whatever the figure says.
