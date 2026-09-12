# CRITIC_LATEST — critic #72, 2026-09-12T0510Z, reviewed `cd18782`

**The next dev lap reads this file before it claims a row** (CHARTER §4 step 3). Only the
most recent critic lap's file is kept; the full report is
`docs/auto/reports/2026-09-12T0510Z-critic.md`.

## `fix-before-next-row`

**NONE. Claim the top backlog row directly.**

This is a measurement, not a shortage of findings. Critic #72 found two real judge-facing
defects and **neither is a fix of minutes**: WFG-266 needs two figures redrawn under new
filenames plus a docx rebuild, and WFG-267's cheapest honest half touches either
`docs/auto/JUDGE_QA.md`, where NH-049's reprint requirement fires, or a file CHARTER §14b
does not name. §14b says a judge-facing defect larger than minutes is 「a **P0 row at
position 1** of the table」 and 「never a preemption」, so both were filed that way and the
top row is displaced by nothing. §14b says 「at most ONE per critic lap」, not one every lap.

**What this lap checked, so the next lap does not re-check it:**

- `gates.py --mode full` exits **0** on its FIRST run at `cd18782` (2216 passed, 65
  skipped, 3 xfailed, pytest 493.9 s). `baseline-verify` is the usual sandbox WARN for two
  absent `data/raw/` manifests (CHARTER §3d).
- `--assert-head` and `--assert-reported` both exit **0**.
- **No red GitHub run in the window.** `auto-gates` runs 377 to 398 on `auto/dev` all
  concluded `success`, and run **398** is green at `cd18782`. The last `failure` is 386 at
  `edd0ec0`, critic #70's, outside this window. So CHARTER §4b sets no finding #1.
- All **twenty** build-lap reports in the window record `Reviewed by:`.
- Printed kit **7 of 7** (`WFG_printables_20260911T2137Z.pdf`, 60 pages), release bundle
  **19 of 19** against their own `source` fields, `tests/test_printables.py` 24 of 24.
- Clone is SHALLOW at **51** commits and was **not** deepened. No ancestry claim anywhere
  in this lap.
- Nothing new on either decision channel: Gmail's newest 25 matching threads each carry
  exactly one message and every one is the loop's own send; PR #31's comment list is empty.

## Findings, ranked

**F1 (root objection) — WFG-266, P0, position 1. A figure's caption and that figure's own
legend now assert different things, inside one commit, on a rubric criterion that names
legends in its own text.**

`docs/auto/RUBRIC.md:34` and `:47` word 제출 자료 as 「자료의 논리적 구성 · **그래픽 및
범례의 명확성** · 사용된 자료에 대한 출처 명기」, in **both** tables. Commit `63e9d20`
rewrote F8's caption in `paper/manuscript.md` from 「2 with no safe walking route」 to
「**2 reaching no refuge**」 and left `paper/make_figures.py:689`, the legend of that same
figure, reading 「origin: no safe walking route」. One grep of that file for the phrase
returns **three** hits and the lap changed **one** (`:244`, F5b, correctly under a new
filename with a full docstring). `:134` (F3_regions) is the third. Neither PNG was
regenerated: `git diff e7ba085..cd18782 -- paper/figures/` lists `F5b_decision_shift.png`
alone, and both files still carry `a37cfb0` as their newest commit.

⚠ **This is the third consecutive lap of instance-scoped repair**, and DIRECTION has named
the class twice already, each time one abstraction too high. The concrete naming, now on
the page: **grep the file you just edited for the string you just changed.** Not a
describing sentence, not a defining sentence: the same words, elsewhere in the same file.

**F2 — WFG-267, P0, position 2. WFG-264's repair has not reached the paper a judge is <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. Same false-positive class as ba437f5, where the gate read a lap stamp as a camera count. No figure is asserted on this line. -->
handed, and the card the student studies still gives the instruction that guarantees both
sentences in one stack.**

`outputs/dispatch/20260801T163042Z/` holds **33** committed sheets; **17** print
「예산 내 차량 진입로가 화재로 차단됨(우회 포함)」, and **44** files under `outputs/` carry it.
Only **3** clusters ship a pre-built `dispatch_a4.pdf` and `02-천전공원-일대` is one of the
17; `scripts/generate_dispatch_outputs.py:259` renders that PDF from that HTML through
`printable.html_to_pdf`. Q39 (`docs/auto/JUDGE_QA.md:1554`) instructs 3 pre-built plus 30
reprints; `outputs/dispatch/README.md` says rebuild all 33. Only the second is safe, and
neither file mentions the repair. This stack is also the one booth handout with **no
staleness gate**: `scripts/build_printables.py`'s `SOURCES` are seven markdown documents
and not one is a dispatch sheet.

⚠ **Credit first, because this is not 「nobody wrote it down」:** `docs/live_pipeline.md:193-201`
carries the supersession table, `tests/test_live_pipeline_doc_matches_code.py` binds it,
`docs/routing_limitations.md` §7 is the full audit, and `JUDGE_QA_PENDING.md` **P-002**
already drafts a good answer. What no file says is **which of the three pages in the
student's hand** is the old one.

**F3 — WFG-268, P1. CHARTER §4 tells every lap a tool is forbidden, and the tool works.**

§4's sandbox-facts paragraph says `curl` against `api.github.com` 「returns 403 here and must
not be used (WFG-119)」. Measured at `cd18782`: the call returns a full JSON body and exit 0,
and this lap read all of runs 377 to 398 from it. The session now routes outbound HTTPS
through a configured proxy, which is what changed. Date the old sentence, do not delete it.

**F4 — WFG-263, evidence added, still P1.** The 0420Z report's machine-written gate table
(`docs/auto/reports/2026-09-12T0420Z-dev.md:220`) is stamped at `1461e96` and marked
**stale** against `135822b`. **Neither commit resolves on `origin/auto/dev`**, and the head
the report ships in is `cd18782`. The lap handled it correctly in prose (the header table
names the rebase and says the gates were re-run green) but the generated table still
certifies nothing, and `WFG-264`'s status cell recorded `done(135822b)` for the same reason. <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. Same false-positive class as ba437f5, where the gate read a lap stamp as a camera count. No figure is asserted on this line. -->
Annotated rather than rewritten (CHARTER §3.7); the work actually landed at `fcc9391` +
`4d3a16d`. Third lap in a row that `report.py`-before-gates has cost a cycle. Loop hygiene,
so it waits on R3 per §14b.

## What this lap did NOT find, stated so the next lap does not look again

- **Nothing wrong with the WFG-264 measurement itself.** The three return sites read off <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. Same false-positive class as ba437f5, where the gate read a lap stamp as a camera count. No figure is asserted on this line. -->
  `rescue.py` and `evacuation.py`, the three constructed reproductions, the dual identity
  control on `len(unreachable_homes)`, the threshold read out of `provenance.assumed`, and
  the published retraction of the null-window discriminator all hold. The eight `vus_` keys
  carry a caveat naming four facts that travel together. This is the strongest methodology
  work in the record.
- **No new prose world-claim to check.** `factchk` over the window's added markdown found
  three mentions of OSM and one of SRTM, all describing this repository's own provenance.
  Nothing external is newly asserted, so nothing was verified against a source.
- **No leakage finding.** `mandela` over the `vus_` measurement: the quantity is a property
  of two committed artifacts, the threshold comes from the artifacts rather than the script,
  and the measurement explicitly declines to second-guess the classifier that produced the
  class. The synthetic-hazard provenance is stated on the page and not only in the registry.

## Scorecard

**ONE row moves on each track, the same row, DOWN. Track B 96 to 95, Track A 97 to 96**,
both on 제출 자료, both on F1, which this window **created**. 설계와 방법론 **20** and
데이터 수집·분석·해석 **20** HOLD and are re-earned rather than inherited. 구현 및 유용성
**HOLDS at 20**: critic #71's pre-registered fall does not fire, because its condition was
WFG-264 still being `todo` and the row is `done`. <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. Same false-positive class as ba437f5, where the gate read a lap stamp as a camera count. No figure is asserted on this line. -->

⚠ **Pre-registered for critic #73:** 제출 자료 returns to **19** if WFG-266 closes with F8
and F3 redrawn under new filenames and the manuscript pointing at them, and falls to **17**
if another window ships a third instance of the same grep. 구현 및 유용성 falls to **19** if
WFG-267 (i) is still `todo`.

## Readiness

**8 of 11, unchanged, and ZERO lines ticked for the twenty-ninth consecutive critic lap.**
`git diff e7ba085..cd18782 -- docs/auto/KCF_READINESS.md` is empty; the file's newest commit
is `a37cfb0`. R3 is the only one of §14b's six outstanding, it is `blocked(NH-046)`, NH-046
came due **2026-09-10**, and the sprint ends **2026-09-15**. One unanswered question holds
the ninth tick and the whole P1 block.
