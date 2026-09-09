# CRITIC_LATEST — critic #47, 2026-09-09T0230Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head: `86f8929`.
⚠ **This clone opened SHALLOW at 50 commits**, reading back only to 2026-09-08T08:28Z, which would have
hidden a third of my window. I deepened it with `git fetch --shallow-since='2026-09-08T00:00:00Z'` to
**66** commits, oldest resolvable `088203c` at **00:22:53Z on 09-08** — a deepening whose predicate is
**the window itself**, not a guessed number, which is the control CHARTER §4 says is missing when a lap
guesses 120 or 250. `--is-shallow-repository` still answers **true**, so **no ancestry or reachability
claim appears anywhere below.** Full report: `docs/auto/reports/<this lap>-critic.md`.*

## `fix-before-next-row` — **NONE this lap**

Everything CHARTER §14b makes eligible is green, re-run rather than read. `gates.py --mode full` exits
**0** (`1806 passed, 63 skipped, 2 xfailed`, pytest 348.2 s). GitHub's `auto-gates` runs **256 to 267**
carry one `failure` — run **260** at `7eeccab`, already closed by `1fa0b7f` and reported by the 2231Z
ci-red lap — and **run 267 is `success` at this exact head**, so there is no finding #1. The printed kit
is `WFG_printables_20260909T0055Z.pdf` and **all six of its `SOURCES` re-hash to the tree**. Every dev
report in the window carries `Reviewed by:`, and `gates.py --assert-reported --base d36ad21` exits 0.
There is no minutes-scale judge-facing defect and no red gate, so setting an item would displace the top
row for nothing.

**Take WFG-194, then WFG-125, then WFG-024.** The table's first `todo` row is now WFG-194 and
`docs/auto/DIRECTION.md` says the same thing, so no instruction is needed to reconcile them.

## The one thing to read first: **the window closed WFG-201 well, and the row it feeds is the one nobody has run**

`d78d39b` put the post-hoc-maximum qualifier on **six** judge-facing surfaces — one more than its own row
named, because the lap found `docs/present_perimeter_arm.md` §4 itself and did not leave it out — and
`tests/test_post_hoc_maximum.py` grades it against mutations, scopes the ban to the **section** a judge
reads rather than the file (the WC-004 failure mode), computes the property from the artifacts instead of
quoting a document, and states in its own docstring that it grades a **form and not a meaning**, which is
mandela leakage #4. That is the strongest kind of lap this loop produces and Track B's
데이터 수집·분석·해석 row moves 19 → 20 on it.

---

## F1. The root objection: two dev laps have now written *about* the bound, and the measurement three critic laps have called cheap is **18.3 % of the grid**

The project's headline 42곳 is what a **perfect** forecast buys. The README says so, Q36 says so, and
`docs/present_perimeter_arm.md` §5 says it in the document's own words. **WFG-125** is the row that would
replace that bound with what this project's model actually buys, and critic #45 raised it to P0 on the
ground that 「the input this row's expensive branch needs is ALREADY COMMITTED, so the cost written into
this row is wrong」.

**I measured the input instead of re-reading the row. It is committed and it is a sample, not a field.**
From `data/processed/spread_v2_lofo_oof_cells.csv.gz` at `86f8929`:

| region | hazard field it is graded on | grid | out-of-fold coverage |
|---|---|---|---|
| 영덕 / `yeongdeok_2025` | `data/processed/routing_demo.npz` | `haz_stack` (5, 181, 147) = **26,607** cells/slice | **20,749** rows, **5** `op_from` (matching the 5 slices), ~4,087 cells per op = **15.4 %**, union of distinct `(row, col)` **4,859** = **18.3 %**, rows 25-99 of 181 only, **769** positives |
| 의성·안동 | `hazard_uiseong_andong_2025.npz` | (5, 135, 128) = 17,280 | **18** `op_from`, union **50.1 %** |
| 울진·삼척 | `hazard_uljin_samcheok_2022.npz` | (5, 155, 92) = 14,260 | **26** `op_from`, union **16.9 %** |

So re-planning the forecast-aware arm on the model's own field is **not routing-only and not minutes**: it
needs a rule for the **~82 %** of 영덕 cells the out-of-fold never scores, plus an operating-point-to-slice
mapping for the two regions where those counts differ.

⚠⚠ **And the fill rule is a free parameter of exactly the kind WFG-201 was just filed about**, this time on
the project's headline number rather than on the opponent's. Chosen after seeing what it does to the margin,
it is a second post-hoc maximum; and filling the unscored cells from the graded field would reintroduce the
very oracle the row exists to remove. **So: if the first branch is run at all, the fill rule is written down
before the run and the row reports what it gets. The second branch — record the absence with the paths
checked — is the one that fits a lap, and the paths are now on the row so no lap re-derives them.**

**Cheapest test, thirty seconds, already run:** count the distinct `(row, col)` the out-of-fold file scores
against `haz_stack.shape`. That is the test that should have been run when the row was re-costed.

## F2. A P1 row sat at table position 1, above thirteen P0 rows, and the dev routine takes the table's first row

`WFG-202` was filed at position 1 by the 0056Z lap as WFG-201's follow-on. **The row is correct and its
premise re-verifies here** — a count of `argmax`, `post-hoc` and `maximum over` in `paper/manuscript.md`
answers **0**. But it is **P1**, it is the paper routine's under CHARTER §12, and CHARTER §4 step 3 tells
the dev lap to take the first `todo` row in **table order**, so the next dev lap would have spent a sprint
slot on a row no dev lap is meant to build. The paper routine does not read this table's order, so moving
it down costs the manuscript nothing. **This is this lap's ONE §3b reorder: a non-P0 row moved DOWN below
the P0 block, which is the only direction that rule permits.** The insertion-order count returns to **63**
non-P0 `todo` rows above the last P0 `todo` row.

## F3. Three P0 rows were carrying stale blocks, and one of them is the row that ticks readiness line R11

- **WFG-022** has been `blocked(human)` for five days on **NH-008, which the author closed on 2026-09-04**
  — verbatim 「Everything is fine here. Don't worry about this, and continue with the project.」, and the
  closing lap wrote its consequence in the same entry: 「**No contact with the 운영사무국 will be made.**」
  The work will never be done, so `blocked` is the wrong word and the row is now `dropped` **recording the
  author's decision rather than making one**. Reply and it returns.
- **WFG-023** keeps `blocked(human)`, but **three of its five items are discharged** and the row never said
  so: `Main` and `auto/dev` are settled in CHARTER §3 rule 1 and §4c, and NH-001, NH-002 and NH-006 are all
  `closed`. What remains: the two `docs/HANDOFF_ROUND3.md` §4 items and the decimation approve/veto.
- **WFG-024 is therefore `todo`**, because **neither blocker gates its work** — re-keying a branch name in a
  document needs the branch decision, not the 운영사무국's answers. ⚠ **The live defect:**
  `docs/HANDOFF_ROUND3.md:898` is rule 1 of the §5 block `CLAUDE.md` and CHARTER §3 bind every lap to, and
  it reads 「**Never push to `Main`. All work stays on `round3-dev`.**」 — a live instruction naming an
  abandoned branch, inside the one rule set the loop may never break. The stale **10-18** date survives in
  three `docs/auto/research/` files dated 2026-09-03, and those are **records**: the fix there is a dated
  superseding note, never a rewrite (CHARTER §3.5, §3.7).

## F4. Zero readiness lines ticked, for the fourth consecutive critic lap

**8 of 11**, unchanged since critic #43 ticked R8 at 2026-09-08T1429Z. The routine prompt calls zero across
**two** consecutive laps a finding about the loop's direction; this is four, and **NH-038 — written about
exactly this — is due today and open.** Of the three unticked lines: R3 is blocked by NH-046, R12 is the
author's (NH-014), and R11 was stuck on the bookkeeping F3 just cleared. That is not the whole cause, but it
is the part that was inside the loop's own reach.

## F5. Judge drill: the bank's citations are clean, and two 20-point sub-rows are at literal zero

**The clean half, said because restraint counts (CHARTER §7).** `docs/auto/JUDGE_QA.md` cites **121**
distinct file paths and **every one resolves in the tree**. The single path that does not exist,
`email_sent.json`, is cited **precisely because it does not exist** (「저장소에 한 개도 없습니다」), which
is the card being right.

**What the drill did find, both re-measured unpiped at this head:**

- **창의성 (WFG-194).** 20 points on **both** rubric tables, named **first** in the 심사기준. A count of
  창의 or 독창: **0** on `web/finals.html`, **0** on `docs/auto/DEMO_SCRIPT_5MIN.md`, **2** on the bank.
  `docs/creativity_card.md` holds **10** and **nothing under `release/` or `scripts/` references it**, so it
  is in none of the kit's six `SOURCES`. The material is written and a judge cannot reach it.
- **일정 (WFG-027).** 「일정 및 팀원 역할 배분의 타당성」 is a named sub-item **inside** 설계와 방법론,
  20 points on both tables. A count of 일정: **0** on the screen, **0** on the bank, **1** on the script —
  and that hit is `DEMO_SCRIPT_5MIN.md:70`, 「**일정 크기** 아래의」, an adjective and not a schedule. The
  팀원 half is excluded for a solo entrant by the 심사기준's own 「개인의 경우 제외」; the 일정 half is not,
  and the answer already exists in CHARTER §1 and §11. **This is the next critic's promotion candidate,
  ahead of WFG-197.**
- **The horizon (WFG-197).** A count of `Ready-Set-Go`, 화선 or 8시간 is **0** on all three surfaces, and
  none of the 46 cards asks why the forecast horizon is 3 to 12 hours. Unchanged from critic #46.

⚠ **Why none of these became a card instead of a row, which is itself a finding: `docs/auto/JUDGE_QA.md` is
one of the printed kit's six `SOURCES`,** and
`tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree` is a hard `assert` that
re-hashes every source. A critic that adds a card turns the tree **red**, and the only cure is an artifact
rebuild its charter forbids it. That is **NH-049** for the author and **WFG-205** for a lap.

## F6. `factchk`: the window's one new world claim survives, and one word of its scope does not

I opened `https://biz.heraldcorp.com/article/10675702` (헤럴드경제, 2026-02-12) rather than trusting the
citation. The article carries the research lap's quotes **verbatim**: 「'준비(Ready)-실행 대기(Set)-즉시
실행(Go)'으로 이어지는 단계별 체계」 and 「화선 도달 8시간 전 산불확산 예측 정보를 바탕으로 고령자 등
안전 취약계층의 선제적 대피를 돕고, 5시간 전에는 대상 주민이 안전한 곳으로 지체 없이 이동하도록 유도할
방침이다」. **The doctrine WFG-197 wants to reference is real and correctly quoted.**

**The one hit:** `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md:63` calls 「산불확산예측 정밀도 약
30 % 향상」 a **plan** figure. The article states it in the **past tense as achieved** — 「...적용함으로써,
산불확산예측 정밀도를 기존 대비 약 30% 향상시켰다」 — while the 76 % → 88 % accuracy figure genuinely is a
2027 target. The substantive caveat (no published metric definition, so not comparable with anything here)
is untouched and must stay. **WFG-203**, minutes, and it matters because one of the five judges is a
public-sector disaster-response official who may know the article.

## ⚠ This lap's own defect, recorded because the record is the point

My first version of F2's move note contained a `grep` pattern with an escaped pipe in it, which split
`WFG-202` into 12 fields — **the twelfth instance of the exact defect WFG-191 exists for, committed by the
lap that was reading WFG-191**, which is what critic #44 also did one day ago. I measured it, rewrote the
pattern in words, and re-measured: **11** malformed rows, all pre-existing, **none mine**. That the
convention cannot hold this invariant is now evidence from two consecutive critics, and WFG-191's gate must
check **order** as well as shape.

## ⚠ The one `Do NOT edit` note, RE-STATED after re-checking its premise (CHARTER §14c, NH-036 A)

**It covers `README.md:220-247` only** — the Round-4 fair-opponent block. **It forbids exactly one thing:
putting a present-perimeter margin value (9, 27, 5, 19, 86) into those lines while NH-032 and NH-034 are
open.** I re-read both entries rather than inheriting the note: both are still `open`, both are now one day
overdue, and this lap appended the oracle measurement above to each. **It expires at critic #48 unless that
lap re-states it after re-reading them.**

**It freezes no file and no question.** Those very lines were edited this window to name the statistic as a
post-hoc maximum, and that is the kind of edit it permits: a sentence about *how* the number is chosen, not
a margin value.
