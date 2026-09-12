# CRITIC_LATEST — critic #74, 2026-09-12T1125Z, reviewed `092c907`

**The next dev lap reads this file before it claims a row** (CHARTER §4 step 3). Only the
most recent critic lap's file is kept; the full report is
`docs/auto/reports/2026-09-12T1200Z-critic.md`, which is the one to read. The two earlier
stamps are kept as the record (CHARTER §3.7), each with a header saying what supersedes it and
why: **1125Z**, whose gate table named `092c907`, the head this lap *reviewed*, because
`report.py` runs before the lap's own commit exists; and **1152Z**, whose `## In plain terms`
told the author to answer **NH-037** with an option set that is **not** the one on the entry —
caught by this lap while reading its own outgoing email back, before it was sent, which is the
fourth instance in four windows of the class DIRECTION's newest rule names, this time in this
critic's own output.

## `fix-before-next-row`

**ONE item. Merge `docs/auto/JUDGE_QA_PENDING.md` P-005 into `docs/auto/JUDGE_QA.md` Q39,
run `make printables` at a new stamp, re-point `release/kcf-finals-2026/MANIFEST.json`.
Then claim WFG-256.**

**What is wrong.** Q39 (`docs/auto/JUDGE_QA.md:1554`) tells the student: the three biggest
clusters ship as pre-built `dispatch_a4.pdf`, print those and regenerate the other thirty
with `python scripts/generate_dispatch_outputs.py`. Measured here at `092c907`:

| | |
|---|---|
| pre-built PDFs in `outputs/dispatch/20260801T163042Z/` | **3** — `01-거무역리공원-북쪽`, `02-천전공원-일대`, `03-거무역리공원-남쪽` |
| of those, printing the superseded 사유 | **1** — `02-천전공원-일대` |
| what the other thirty print once regenerated | the repaired sentence |

So the card, as printed, assembles a stack in which one sheet says
「예산 내 차량 진입로가 화재로 차단됨(우회 포함)」 and thirty say
「어느 거점에서도 생존 인지 차량 진입 경로가 확인되지 않음」 for **one** code condition.
Q39 is source **3 of the 7** in `manifest_20260911T2137Z.json` (kit
`WFG_printables_20260911T2137Z.pdf`, **60** pages, re-hashed 7 of 7 here) and that kit is
named by `release/kcf-finals-2026/MANIFEST.json` (re-hashed 19 of 19 here). **This is on
paper in the box, not only in the tree.**

**(a)** Merge **P-005 only**. It is already written and replaces exactly one Q39 paragraph.
P-001 to P-004 stay with **WFG-205**; five cards is not minutes.

**(b) One correction to the draft before you paste it, measured above.** P-005 reads
「미리 만들어 둔 장은 2026-08-01 기록이라 「차량 도달 불가」 사유가 옛 문장이고」, which reads as
all three. It is **one of three**, and the other two stale sheets are both under
`outputs/dispatch_full/20260801T183522Z/03-영덕해맞이공원-일대/`, a directory Q39 never
mentions. Say 「세 장 중 한 장(`02-천전공원-일대`)」 and keep the instruction itself —
*regenerate all 33, hand over nothing pre-built* — exactly as drafted, because that
instruction is right for a reason independent of which sheet is stale.

**(c)** `make printables` at a new stamp and re-point `release/kcf-finals-2026/MANIFEST.json`
in the **same commit**, or `tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree`
goes red by name. Do **not** delete the 2137Z kit (CHARTER §3.2).

**(d)** Leave Q39's ❌ lines and its
`<!-- forbidden-ok: wc006-dispatch-committed-pdfs -->` pragma alone; `WC-006` still points at
a live wrong answer. Do not touch any committed sheet under `outputs/` (CHARTER §3 rule 2).

**Why this is minutes, and why the reason it was skipped does not hold.** The 0920Z dev lap
drafted P-005 and wrote that it did **not** merge it 「because NH-049 is open and
`JUDGE_QA.md` is one of the seven printable sources」. **NH-049 constrains the critic, not a
dev lap.** Its own text reads 「**the critic** has exactly two legal moves and neither is a
card」, and its recommended **option A** reads 「have **the next dev lap that rebuilds the
kit** merge and empty it (this is WFG-205)」. A dev lap merging a card and paying
`make printables` is option A being executed, not decided by acting. NH-049's own appended
measurement prices the rebuild at about **one minute** batched, and about two when a
reviewer block lands after the build — budget for two. This critic did not do it itself
because re-pointing `release/kcf-finals-2026/MANIFEST.json` is outside `docs/auto/`.

## What this lap checked, so you do not re-check it

- `gates.py --mode full` exits **0** on its **first** run at `092c907`: 2233 passed, 65
  skipped, 3 xfailed, pytest 357.8 s. `baseline-verify` is the usual sandbox WARN for two
  absent `data/raw/` manifests (CHARTER §3d). `--assert-head` and `--assert-reported` both
  exit 0, and `--assert-reported --base <push>` exits 0 for all ten pushes in the window.
- **GitHub is green.** `auto-gates` runs **399 to 409** on `auto/dev`: every one `success`
  except **403** and **404**, both `cancelled` by a newer push. Run **409** is `success` at
  `092c907`. CHARTER §4b sets **no finding #1**.
- All **39** reports dated 09-11 and 09-12 record `Reviewed by:`.
- Printed kit **7 of 7** sources at 60 pages; release bundle **19 of 19** against its own
  `source` fields; both re-hashed in this lap's own process.
- `scripts/probe_dispatch_pdf_fonts.py` re-run here reproduces the window's central claim
  independently: **38** committed PDFs probed, **3** able to spell the superseded sentence,
  **0** able to spell the current one.
- `web/finals.html`'s cited dispatch sheet
  (`20260801T163042Z/01-거무역리공원-북쪽/dispatch_a4.html`) carries **neither** sentence, so
  the judged screen is clean.
- The clone is **shallow at 50 commits** and was deliberately **not** deepened. No ancestry
  or reachability claim is written anywhere in this lap. ⚠ `git log --since` on a path whose
  newest commit sits at the boundary answers with that boundary commit and `git show`
  renders the file as `A`; that looks like a change and is not (WFG-217).
- PR #31's comment list is **empty**; the Gmail channel carries nothing new.

## The other findings, ranked, all filed rather than left here

1. **WFG-275, new, P1 — `paper/STATE.json` `body_words` is 9000 against a hard fail of
   9000, so the margin is ZERO for the first time, and both places that narrate this window
   open by saying it is 1.** `paper/README.md:1514` and the header of `STATE.json`'s
   `built_pages_note` say 「8,999 to 8,999; margin 1 to 1」; `paper/README.md:1560` in the
   same paragraph says 「8,999 to 9,000; margin 1 to 0」; `check_paper.py` re-derives **9000**
   here. Both headlines were true of the first draft and false of the tree, because the
   reviewer's `responder` repair landed after they were written. **The next paper lap that
   adds one word is red.** The author's half is **NH-037**, severity raised, with the
   measurement that the first thing the ceiling refused is a limitation this project found
   against itself (+32 words, reverted).
   ✅ The good news on the same file: `built_pages` is back at **23**, re-derived by a lap
   that installed LibreOffice Writer, so the author's 25-page rule is verified again.
2. **WFG-272 re-verified and it reproduces exactly** — `grep -n "no safe walking route"
   paper/make_figures.py` returns 133, 146, 172, 251, 282, 573, 580, 585, 754;
   `docs/figure_legend_claims.md:127` names 133, 146, 173, 252, 283, 574, 581, 586, 755. The
   corrected pointers for every site are now on the row, so the fix is two minutes. ⚠ **This
   critic nearly published a rebuttal of a correct finding** by reading 「nine line numbers」
   as nine citations and counting six. Run the command the finding names.
3. **Zero KCF_READINESS lines ticked for the 31st consecutive critic lap**, 8 of 11. R3 is
   the only one of CHARTER §14b's six outstanding, it is `blocked(NH-046)`, NH-046 came due
   **2026-09-10**, and the sprint ends **2026-09-15**.
4. **WFG-205 and WFG-211 annotated, not re-filed.** The staging file now holds five cards;
   29 of the 30 newest report threads carry `UNREAD` (a signal about the inbox copy, not
   proof the report was unread).
5. **WFG-252 annotated:** both track tables end with a `2026-09-11 b6778e7` row sitting
   below the 09-12 rows, and the Track B `cd18782` row spells 「제울 자료」. Reported and not
   fixed — CHARTER §3.7 forbids editing another lap's scorecard row.

## Direction

**No §3b row move spent.** Table order is already right: **WFG-256** (the rotation null)
then **WFG-255**. Nine of the fifteen rows closed in the last thirty hours are one wording
family and three are experiments; the next row should be the experiment. Full reasoning and
the standing prohibitions are in `docs/auto/DIRECTION.md`, which is the file to read, not
this one.

**Scorecard: Track A 96 to 97** (구현 및 유용성 19 to 20, critic #73's pre-registration
firing on its own words), **Track B holds at 96**. Pre-registered for critic #75: 제출 자료
reaches 20 on both tracks when the Q39 merge lands **and** WFG-272 closes; 창의성 reaches 20
when WFG-256 runs and reports either way; **구현 및 유용성 falls back to 19 if the Q39
instruction is still unmerged at the next critic lap.**
