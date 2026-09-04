# Critic verdict on the latest dev laps

Overwritten by every critic lap (history is in `docs/auto/reports/*-critic.md`). The
next dev lap clears every `fix-before-next-row` item here before claiming a row.

**Lap: 2026-09-04T0147Z (critic #5).** Scope: `a4dc9a7..5a0466e`, the five commits since
critic #4's report landed. That is one backlog claim (`58d4fa7`), the 0037Z manual lap
(`fbe71de`), the 0100Z cloud dev lap (`d2f314d`), the 2026-09-04 laptop dev lap
(`98557b9`) and its post-rebase follow-up (`5a0466e`). `paper/` did not change, so
`check_paper.py` was not run. `docs/auto/JUDGE_QA.md` changed (two references to a
deleted file), so a short drill ran.

**Landed during this lap, after the scope closed, and NOT reviewed here.** Two manual paper
laps pushed `b621441` and `2a02477` while this critic run was in progress: a substantial
rewrite of `paper/manuscript.md` (938 lines), `references.bib`, `make_figures.py`, `F1_system.png`,
the `.docx`, `GAPS.md`, and a new **NH-019** on what `fire_manifest.json`'s `start` field is
allowed to mean. None of it is in `a4dc9a7..5a0466e`, so no finding below covers it and
`check_paper.py` was not run against it. It is the next critic lap's first scope, and NH-019
is a live question about a claim the detection section already makes. The `dashboard.html`
in this commit was rendered before those two reports existed; the next report rebuilds it.

**Gates, re-run independently at `5a0466e`: `gates.py --mode full` exits 0. `auto/dev` is
GREEN at HEAD.** `1229 passed, 62 skipped` in 163 s; verify PASS (now including the new
`check-readme-figures` step), snapshot-verify PASS, env-check PASS, `baseline-verify`
WARN as expected off-laptop (soft step, `hard: false`). Second consecutive critic lap
opening on a green branch.

**Reviewer verdicts.** `docs/auto/reports/2026-09-04T0100Z-dev.md:191` records
`Reviewed by: subagent (block)` and acts on both block items without arguing.
`docs/auto/reports/2026-09-04T0037Z-manual.md:82` has a `## Reviewed by` section.
`docs/auto/reports/2026-09-04T0134Z-dev.md:13` records `Reviewed by: self`, with a
stated reason (the lap ran on the author's laptop, outside the routine). No report is
missing a verdict. `5a0466e` carries no verdict of its own; see F25.

**Root objection.** Critic #4 said the only prose that can be rewritten wrongly without
a gate noticing is the prose with no key and no URL. Three laps then did the expensive,
correct thing: every figure in the opening paragraph now has a `fire2025_*` registry key,
an artifact, an agency, an as-of date, a scope and a URL a lap opened, and two independent
gates hold the paragraph to them. Checked cold this lap against the primary pages, **every
figure the paragraph prints is right.** The paragraph still carries a false statement, and
it is the one sentence in it that is not a figure. Both language versions now assert that
matching bases would put this fire at "about 43 %" of the national total. That claim is
contradicted by the article the repository itself cites for the definition, by the standard
relation between the two Korean burned-area statistics, and by the repository's own
registry, which records the share as **94.8**. The failure class has moved one step:
numbers are now bound, and the *reasoning about* the numbers is not. A judge does not
check a registry; a judge checks a sentence.

The loop already knows. The laptop lap wrote this disagreement up as **NH-018** and left
the sentence standing because it "could not open a primary page that states which basis
the 104,788 total uses". That page is not needed; see F21. Parking a sentence the loop
believes is wrong in front of judges, as an author decision, is a more expensive habit
than a fourth rewrite would have been.

---

## fix-before-next-row

### F21 — The "about 43 %" sentence in both opening paragraphs is false, the repository's own registry says so, and the test written to forbid exactly this ratio cannot see it

**Where:** `README.md:210-211` (Korean: `같은 기준(산불영향구역)으로 맞추면 그 비율은 95 %가
아니라 약 43 %가 되며, 기준 선택만으로 두 배 달라지는 값은 수치가 아닙니다`);
`README.md:528` (English: `measured like-for-like on 산불영향구역 the share is about 43 %,
not 95 %`); `docs/data_sources.md:249-251` and 함정 1 at `:255-258`;
`tests/test_motivating_event_figures.py:208-231`; `docs/auto/NEEDS_HUMAN.md` NH-018 item 2.
Introduced by `d2f314d`, kept by `98557b9`.

**What is wrong.** The sentence needs 45,157 ha and 104,788 ha to be two values of the same
quantity on the same basis (산불영향구역), so that dividing them is the "like-for-like"
comparison. Three independent checks say they are not.

1. **The definition rules it out.** 산불영향구역 is the area inside the fire line, and it
   **includes the parts inside that line that did not burn**; 피해면적 is the surveyed area
   that actually burned, measured after containment. The larger of the two is normally the
   영향구역 (`산불영향면적이 실제 피해면적보다 넓게 잡히는 것이 통상적`, e-나라지표 /
   산림청 산불통계). A 산불영향구역 of 45,157 ha for a fire whose surveyed 피해면적 is
   99,289 ha is the relation upside down. 45,157 was not a different basis; it was an
   estimate that measurement overturned.
2. **The cited article says so in its headline.** `docs/data_sources.md` sources the
   45,157 row to [경향신문 2025-04-17](https://www.khan.co.kr/article/202504171020011),
   opened this lap. Its title is `경북 산불 실제 피해 약 10만ha, 산림청 추정치 '2배' 훌쩍…
   "초기 추산 엉터리" 비판도`, and its body reads `산림청은 산불 진화 이후 최근까지 경북의
   '산불영향구역' 추정치가 약 4만5157㏊라고 밝혀왔다`. The article's own frame is a bad
   early estimate that was corrected, not two coexisting quantities.
3. **The arithmetic rules it out.** The 산림청 season total of 104,788 ha is dated
   2025-05-16, a month *after* the 합동조사. The surveyed regional figures are 경북 99,289
   + 경남 3,397 + 울산(울주) 1,190 = **103,876 ha**, which is 99.1 % of the national total
   and leaves 912 ha for the roughly 340 other fires of the season. For the denominator to
   carry this chain at 45,157 instead, those same 340 fires would have to account for
   55,044 ha, about 162 ha each. The denominator already contains the 99,289.

So 45,157 / 104,788 is not a like-for-like ratio; it is a superseded numerator over a
current denominator, which is precisely the mixed-basis division the paragraph exists to
forbid. The repository agrees with this in the one place a judge will not look:
`docs/NUMBERS.json` registers `fire2025_chain_share_of_nationwide_pct = 94.8`, status
`derived`. Judge-facing prose and the registry state two different answers to the same
question, which is the defect WFG-049 was opened to end.

**And the tripwire cannot fire.** `test_the_nationwide_total_is_never_divided_by_the_chain`
scans only lines that contain `104,788`. In the current README that string is on line 206
(Korean) and line 522 (English); the ratios are on lines 210 and 528. The test passes on a
README that prints both of the ratios it was written to ban. This is the F16 pattern again:
a test whose first version passes on the defect it names.

**Smallest fix. It is a deletion, not a fourth rewrite of the figures.**

1. `README.md:210-211`, delete from `같은 기준(산불영향구역)으로` to the end of that sentence.
   The preceding clause (`①과는 기간·주체·집계 기준이 모두 다르므로 「이 화재군이 전국의
   몇 %」 같은 비율은 쓰지 않습니다`) is correct and is the whole rule. Do not put another
   ratio in its place.
2. `README.md:528`, delete `: measured like-for-like on 산불영향구역 the share is about
   43 %, not 95 %, and` so the sentence reads `So this repository prints no "share of the
   national total": a ratio that moves by a factor of two on basis choice is a framing, not
   a quantity.` If you prefer the stronger and now-sourced reason, say instead that the
   chain has no post-survey 산불영향구역 figure published, so no like-for-like ratio exists.
3. `docs/data_sources.md` 함정 6 and 함정 1: keep the two labels distinct, and correct the
   direction. 산불영향구역 normally exceeds 피해면적; 45,157 ha was the 산림청 pre-survey
   estimate that the 합동조사 more than doubled, criticised at the time as an undercount.
   `README 서두는 99,289 ha를 쓰고 45,157 ha는 기준과 시점을 밝혀서만 인용한다` is the
   sentence that survives.
4. Widen the tripwire to the paragraph rather than the line: locate the Korean and English
   scope notes the way `scripts/check_readme_figures.py` already does (label to label) and
   assert no `\d{1,3}\s*%` in either, after stripping link targets. Verify it fires by
   reverting the two sentences before you delete them.
5. Annotate NH-018 item 2 as resolved on evidence and leave the entry open for item 1 and
   for the author's confirmation. Under CHARTER §3 rule 5b the loop has standing permission
   to source public data, which is what item 2 was waiting on.

### F22 — `--assert-reported` accepts a report that was edited, so the prose-only commit it was built to stop still passes

**Where:** `scripts/auto/gates.py:97-127` (`assert_reported`, added by `98557b9`);
demonstrated on `5a0466e`.

**What is wrong.** The check collects `git diff --name-only <base>..HEAD`, calls anything
outside `REPORT_ONLY` substantive, and passes as soon as **any** path under
`docs/auto/reports/` appears in the same range. A path appears there whether it was added
or modified. So appending one line to a report from an earlier lap licenses an arbitrary
substantive commit.

This is not hypothetical; it is what the window's last commit does. `5a0466e` changes
`docs/auto/NEEDS_HUMAN.md` (+31, a new DECISION entry), `docs/auto/STATE.json`, and
`docs/auto/reports/2026-09-04T0134Z-dev.md` (+4 lines appended to the previous lap's
report). Run this lap:

    $ .auto/venv/bin/python scripts/auto/gates.py --assert-reported --base 98557b9
    [gates] ASSERT-REPORTED OK  1 substantive path(s) travel with report .../2026-09-04T0134Z-dev.md
    EXIT=0

`12b8ac7`, the commit in F19 that this check exists to refuse, would have passed the same
way had it appended a line to `ca366bf`'s report. The check as written tests that a lap
*touched* a report, not that a lap *wrote* one.

**Smallest fix.** One flag. Build `reports` from
`git diff --name-only --diff-filter=A <base>..HEAD` instead of the plain listing, so only a
**newly added** report file discharges the requirement. Keep the existing listing for the
`substantive` set. Add a test beside `tests/test_gates_assert_head.py` that seeds a
modified-only report and asserts exit 1, and one that seeds an added report and asserts
exit 0. `5a0466e` is the fixture: it is a real range that should have failed.

Note the intended flow still works, because a lap that appends to an old report while
pushing new work is a lap that should be writing a new report for that work.

---

## fix-this-sprint

### F23 — The registry, the sources table and the README name three different agencies for the same two figures, and the new gate checks that the field is filled, not that it agrees

**Where:** `docs/NUMBERS.json` / `data/processed/external/fire_2025_scale.json`
(`interim_chain_area_ha_20250327`, `chain_deaths`); `docs/data_sources.md:190`, `:194`, `:249-251`;
`README.md:198-199`, `README.md:204-205`; `scripts/check_readme_figures.py:88-92`.

**What is wrong.** Three disagreements, all inside the apparatus built this window to make
prose traceable:

| figure | registry `agency` / `url` | `docs/data_sources.md` | `README.md` | what the source says |
|---|---|---|---|---|
| 45,157 ha (interim) | 중앙재난안전대책본부 / khan 2025-03-28 | 산림청 / khan 2025-04-17 (`:194`) | 산림청 (`:204-205`) | **산림청** (khan 2025-04-17, opened this lap) |
| 사망 26명 | 중앙재난안전대책본부 (경북 5개 시군 합계) / 뉴시스 + 서울신문 | 경상북도 재난안전대책본부 / 대구MBC | no link of its own | not carried by the README's link |

The second row is the one a judge meets. `README.md:193-199` puts the whole chain parenthetical,
including `사망 **26명**`, under one citation: `[아시아경제 2025-05-06](https://view.asiae.co.kr/article/2025050610030818823)`,
`경상북도 최종 집계·중앙재난안전대책본부 확인`. That article was opened this lap. It carries
99,289 ha, 149시간, 3,819동, 2,246세대 / 3,587명 and 1조 505억 원, and it **carries no death
figure at all**. The English at `README.md:505-513` places the same citation after the same
list. So the one figure in the sentence that a judge is most likely to check is the one
whose link does not contain it.

`scripts/check_readme_figures.py` cannot see any of this: its provenance loop only asserts
that `agency`, `as_of`, `scope`, `source_url` and `figure_status` are non-empty, and it
never compares the README's own inline links, or the sources table's agency column, with
the registry. The gate makes values traceable and leaves attributions free.

**Smallest fix, in two parts.** (a) Correct the artifact: `interim_chain_area_ha_20250327`
becomes agency **산림청** with the khan 2025-04-17 URL (the page that states both the figure
and its 산불영향구역 label), and `chain_deaths` picks one agency spelling that
`docs/data_sources.md` also uses. Re-run `scripts/register_fire2025_figures.py`. (b) Give
`사망 26명` its own inline citation in both paragraphs, from the registry's own URL, rather
than leaving it under the 아시아경제 link. The gate half is filed as WFG-051.

### F24 — `docs/auto/AI_DISCLOSURE.md` was deleted, and CHARTER §3 rule 7 says archive

**Where:** `fbe71de` deletes `docs/auto/AI_DISCLOSURE.md` (48 lines);
`docs/auto/archive/` exists and holds `round1_docs_2026-06` and
`round2_pitch_page_2026-07-24`; `docs/auto/CHARTER.md` §9 and `KCF_READINESS.md` R10
record why.

**What is wrong.** The removal itself is the author's call and is documented (NH-008, and
§9 rewritten to say the practices are kept for booth explainability rather than for a form).
The mechanism is the finding: rule 7 reads `Never delete. Archive (docs/auto/archive/ or a
branch), and say why`, and this is a first-class judge-adjacent document that now exists
only in `git log`. The rule exists so that a later lap reading `docs/auto/` can see what was
retired and on what grounds without a `git log --all --` on a path it does not know to look
for. Two references in `JUDGE_QA.md` were cleaned in the same commit, so the tree is
consistent; nothing is broken today.

**Smallest fix.** `git show 12b8ac7^:docs/auto/AI_DISCLOSURE.md >
docs/auto/archive/AI_DISCLOSURE_retired_2026-09-04.md`, with a three-line header saying it
was retired at the author's instruction under NH-008, that KCF requires no disclosure
artifact, and that the live practices are CHARTER §9. Cost: one commit, no gate change.

---

## note

- **N24 · The 0100Z lap's independent reviewer is the best thing in this window and the
  cheapest.** It caught two defects the lap had no motive to look for: the nationwide total
  cited to a ko.wikipedia page that does not contain `347` at all, and the fact that
  104,788 ha / 347건 is a **봄철 산불조심기간 (2025-01-24 to 05-15)** total rather than a
  March one. Both confirmed this lap against the 산림청 release
  ([korea.kr 156689401](https://m.korea.kr/briefing/pressReleaseView.do?newsId=156689401),
  period `1.24~5.15`). The lap's own report says it plainly: `Had I not run it, this lap
  would have shipped 99,289 ha sourced to a page that says 45,157 ha`. Two of the three
  substantive defects in this window came from the two laps that did **not** run a subagent.
- **N25 · Every figure the paragraph prints was checked cold and every one holds.** Opened
  this lap: the 경상북도 release (`피해 면적 9만 9,289ha`, `주불 진화 시간 총 149시간`,
  `2,246세대, 3,587명의 이재민`, `주택은 3,819동`, `1조 505억 원`, and the superlative
  `1986년 이후 집계된 산불 통계치로는 역대 최대 피해 면적`), the 아시아경제 report of the
  same tally, the 경향신문 joint-survey article, and the 산림청 season-end release. The
  「1986년 이래 최대」 claim the README attaches to the chain is carried by the 경상북도
  release itself, not borrowed from the national total; critic #4 would have been wrong to
  assume otherwise, and this lap checked before writing it down.
- **N26 · `docs/NUMBERS.json` grew by 616 lines with zero deletions.** Verified:
  `git diff a4dc9a7..HEAD -- docs/NUMBERS.json | grep -c '^-[^-]'` returns `0`. CHARTER §3
  rule 3 (add, never edit a value) held under a 52-key addition.
- **N27 · The `docs/baseline_phase13.json` re-freeze is additive and is not a finding.**
  Three artifact hashes added, `frozen_utc` / `git_commit` / `registry_entries` updated, and
  **no existing hash changed**. A re-freeze that rewrote a hash would be a rule-2 break; this
  one is not. Recorded so no lap re-litigates it and no lap treats it as precedent for a
  re-freeze that does change hashes.
- **N28 · WFG-050 is open and correctly named.** The 0100Z reviewer's `mandela` finding
  stands: `tests/test_motivating_event_figures.py` reads its ground truth from
  `docs/data_sources.md`, a sibling document the same lap wrote in the same commit
  (leakage #3/#4/#5). `tests/test_readme_opening_figures.py` is one step better, since its
  ground truth is the registry, but the registry is fed by an artifact the same lap also
  wrote. The independent term in both chains is the set of URLs, and nothing pins their
  content. WFG-050's snapshot-with-sha256 proposal is the right fix and it is P1; F23 is
  what that leakage looks like when it bites.
- **N29 · Suite census, cold, in a fresh sandbox.** `1229 passed, 62 skipped` at `5a0466e`,
  against `1185 passed, 62 skipped` at `12b8ac7` last lap: +44, which is
  `test_motivating_event_figures.py` (21) + `test_readme_opening_figures.py` (up to 15) +
  `test_gates_assert_head.py` additions (6) and the rest. The skip count is unchanged at 62,
  the six SRTM-gated tests plus the rest (WFG-039). Critic #2's N7 recommendation, gate on
  `collected`, is still unimplemented.
- **N30 · `baseline-verify` WARN is unchanged and is not a finding.** Fifth lap running.
  `hard: false` for the git-ignored raw manifests.
- **N31 · Two dev laps ran against the same paragraph at the same time and neither lost
  work.** `98557b9` rebased onto `d2f314d`, kept the other lap's prose, and refitted its own
  gate to it. That is CHARTER §4's overlap rule working as written, on the hardest possible
  file. Worth keeping in MEMO as the positive case beside NH-007's negative one.

### F25 — carried, downgraded to a note

`5a0466e` changes `docs/auto/NEEDS_HUMAN.md` substantively with no reviewer verdict of its
own; it is covered by four lines appended to the previous lap's report. That is honest and
the content is a good-faith escalation, so this is not F19 repeating. It is the concrete
case that makes F22 a finding rather than a theory, and it is why F22 should be fixed before
the habit sets: the mechanism that would have to notice a real recurrence currently does not.

### F11, F12 — open, unchanged

`paper/` did not change in this window, so nothing about **F11** (`paper/manuscript.md`
ships 21 citations and no `## References` section, WFG-045) can have moved. **F12**
re-verified this lap: `scripts/auto/report.py:123` still reads
`choices=["dev","critic","research","kickoff","red","manual"]`, so there is still no
`paper` kind (WFG-044).

### F16, F17, F18, F19, F20 — closed

F16, F17 and F18 were closed at `e3e2ec2` and re-verified by critic #4 in place. This lap
re-checked the outcome rather than the process: the paragraph's figures are correct and
sourced. **F19 is closed in intent and open in effect** (F22). **F20 is closed**: NH-008,
NH-009 and NH-015 now carry `channel` / `received` / `verbatim` and say the reply arrived
where the repository cannot see it; part (1), the author's confirmation, is NH-017 and is
the author's.

---

## The judge drill

`docs/auto/JUDGE_QA.md` changed in `fbe71de`: two references to the deleted
`AI_DISCLOSURE.md` were removed, from the DRAFT banner and from the 근거 line of the
AI-assistance answer. The bank's 33 questions are otherwise unchanged, so the drill ran on
the two questions critic #4 **withheld** because they were unanswerable, plus the one the
edit touched.

**The two withheld questions are now answerable, and should go into the bank.** Critic #4
declined to add them while the paragraph was wrong. It is right now.

1. *"의성 산불 피해면적이 얼마입니까?"* The tree answers **99,289 ha**, 합동조사 기준, with
   the 경상북도 release behind it, and can explain in one breath why the 45,157 ha the judge
   may remember from the news is the pre-survey 산불영향구역 estimate. That is a T1 answer,
   and it is a better one than the question expects. **Add it, with the F21 fix applied**,
   because the answer as the README currently frames it invites the follow-up "그럼
   영향구역이 피해면적보다 작다는 말입니까?" and there is no good reply to that.
2. *"영덕에서 몇 분이 돌아가셨습니까?"* The tree answers **10명**, names it a 재인용값 from
   the 영덕군 공지 of 2025-04-29, and names the 경상북도 2025-03-30 interim of 9 beside it
   without collapsing them. Add as-is. Refusing to pick one is the correct answer and it
   demonstrates the sourcing discipline better than a clean number would.

**The AI-assistance answer (`JUDGE_QA.md:611`) still stands after the edit.** Its 근거 line
now points at `ROUTINE_PROMPTS.md`, `CHARTER.md` §9 and `docs/auto/reports/`, all of which
exist. The answer's substance (the student writes the 연구 계획서, 초록, 포스터 and 인용 by
hand; the loop does not draft them) is unchanged and is still supported. **One drill hit:**
the answer no longer has a single document to hand a judge who asks "그럼 어디에 정리되어
있습니까?", because the document that did that was deleted. F24's archived copy is also the
cheapest fix for this.

**Where the bank is silent and should stay silent.** Nothing in the bank claims a share of
the national total, and nothing should until F21 is fixed. If a judge raises it at the
booth, the answer is that the two totals sit on different bases and the repository declines
to divide them, which is exactly what the README will say once the 43 % sentence is gone.

---

## What five lenses converged on

| lens | verdict | the one load-bearing reason |
|---|---|---|
| KCF judge · SW professor | **pass** | Green at HEAD for the second straight window, a new gate that binds judge-facing prose to a registry key backed by an artifact backed by a URL, and 44 new tests. The engineering answer to "how do you know your own documents are right" is now demonstrable in ninety seconds at the booth. I would score this. |
| KCF judge · 재난 대응 공무원 | **pass, with one reservation** | The scale of the event is finally right: 99,289 ha, 149시간, 3,819동, 이재민 3,587명, 1조 505억. I recognise those numbers. The reservation is the sentence telling me the fire is "about 43 %" of the season. I would not have caught it, but if a colleague did, it would cost more than the paragraph is worth. |
| fire-behaviour scientist | **fail**, on one sentence | 산불영향구역 contains the unburned islands inside the fire line. It is bigger than 피해면적, always. A document that lectures me on the difference between the two statistics and then prints an 영향구역 for this fire that is less than half its 피해면적 has the concept backwards, in the paragraph where it is teaching me the concept. Everything else here is careful. |
| ML reviewer (leakage, baselines) | **pass**, with WFG-050 restated | Ran `mandela` over the window. No eval, split, metric or model changed. The prose tests have a real independence problem (ground truth written by the same lap, in the same commit, in a sibling file), which the lap's own reviewer named and filed rather than hid. That is the correct handling of a leak you cannot close today. |
| statistician | **fail**, same sentence, different reason | You have registered `fire2025_chain_share_of_nationwide_pct = 94.8` and printed 43 in the README. Whichever is right, a repository whose whole thesis is that every number traces to one artifact cannot hold two answers to one question in two files. And the test that was written to forbid this ratio scans one line and misses both copies, which is the third time in five laps that a new test passes on the defect it names. |

**Where they agree:** the window did the right work, at real cost, and got the numbers
right. Four of five lenses would let this paragraph go to a booth. The two failures are the
same sentence, reached from opposite directions (a domain definition and a registry
collision), which is the strongest possible signal that it is wrong rather than merely
unpopular.

**Where they split:** L1 and L2 score what the paragraph now proves; L3 and L5 score the one
claim it makes that is not a figure. They do not disagree about any fact.

**The question that resolves the split, and it has moved.** Critic #4 asked *which numbers
here can be wrong without a gate noticing*, and the answer, "the ones with no key," is now a
much smaller set. This lap's version is *which sentences here can be wrong without a gate
noticing*, and the answer is: the ones that reason about the numbers rather than state them.
`check_readme_figures.py` checks that a value appears. It cannot check what the sentence
around the value asserts. F21 is that gap with a judge standing in front of it, and F23 is
the same gap one level down, where a value is bound and its agency is free.
