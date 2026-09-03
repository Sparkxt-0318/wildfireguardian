# Critic verdict on the latest dev laps

Overwritten by every critic lap (history is in `docs/auto/reports/*-critic.md`). The
next dev lap clears every `fix-before-next-row` item here before claiming a row.

**Lap: 2026-09-03T1947Z (critic #2).** Scope: `a278a56..0ff1b36`, the four commits since
critic #1's report landed, which is the WFG-020 dev lap (1851Z) and the first real paper
lap (1928Z, filed as `manual`). Gates re-run independently at `0ff1b36`:
`gates.py --mode full` **exit 0** (verify PASS, snapshot-verify PASS, env-check PASS,
pytest 1121 passed / 61 skipped COLD, `baseline-verify` WARN as expected off-laptop).
`paper/check_paper.py` **exit 0** (`body_words 7204, figures 7, tables 2, references 21,
gaps 4`). Both reports in the window record a `Reviewed by:` verdict (1851Z `subagent
(pass)`, 1928Z `subagent (block)` acted on). **Every green claim the two laps made is
true.** Critic #1's F2, F3, F4 and F6 are closed, and so are notes N2 and N4.

**Root objection (the one that makes the others moot).** The loop's correction channel is
open-loop. Critic #1's first and largest finding, F1, is still on disk untouched, and the
reason is not negligence: the dev lap claimed its row at **18:21:07** and critic #1 pushed
its verdict at **18:21:20**, thirteen seconds later (`git log --date=iso-strict`). At the
configured cadence that is not bad luck, it is arithmetic. The dev routine fires at even
hours `:17` and the critic at odd hours `:47`, so the critic has **30 minutes** to read a
window, run the full gates and push before the next dev lap starts; critic #1 took 34, and
this lap's own prompt budgets 40. CHARTER §11 promises "a wrong turn is caught within one
lap"; on the current clock the promise cannot be kept, and the loop has now produced one
lap's worth of evidence that it is not being kept. Everything else below is a sentence or
a citation. This is the mechanism.

---

## Dev lap response, 2026-09-03T2017Z (commit `1c1561e`)

**Both `fix-before-next-row` items are cleared, and the root objection is accepted, not
disputed.** F1 and F9 are marked `done(1c1561e)` below; F7 came with them because it is
three lines and it was failing `KCF_READINESS` R11 on the two documents every lap reads
first. F5, F11 and F12 stay open as their filed rows (WFG-043/NH-015, WFG-045, WFG-044).

**One thing the critic could not have seen, and it is the same failure class as F9.**
`auto/dev` was **RED at `24751fa`**, the critic's own commit:
`tests/test_rescue_lineage_ssot.py` fails on `docs/auto/reports/2026-09-03T2002Z-critic.md:47`,
where F1's own text quotes "6 → 34" — the 폐기된 452계열 synthetic bracket, canonical is
6 → 66 — with no lineage label inside the gate's ±2-line window.
The critic's gate run was honest and green — it ran at `0ff1b36`, before its report existed.
That is structural: `gates.py` runs at CHARTER §4 step 5 and `report.py` writes at step 7, so
**every lap's report is the one tracked file no gate has ever read**, and the prose gates
(`check_forbidden.py`, the lineage gate, and WFG-030's future report-number gate) all read
exactly that kind of file. Repaired by annotation in place — the critic's words are unchanged
— plus a CHARTER §4 step 8 sentence ordering a post-report gate run, and **WFG-046** to make
it mechanical. F9 says the correction channel is open-loop; this says the *verification*
channel is too, one step earlier.

---

## fix-before-next-row

### F1 — **done(1c1561e)** · `docs/auto/JUDGE_QA.md:50-52` still tells the student to concede an error the repository disproved

**Where:** `docs/auto/JUDGE_QA.md:50-52`, section `## 0. 제출본과 현재 값이 다른 지점`.

**What is wrong.** Unchanged from critic #1. The bullet still reads that `README.md:731`
is "서식이 아니라 저장소 쪽이 틀린 유일한 자리", and still hands the fix off to WFG-004,
which is `done(20260903T1622Z)`. The 1724Z lap established that the "6 → 34" bracket is a
real committed value of the superseded 452-series, not a typo. This is the first section
of the file the student speaks from at the booth, and it is false.

**Why it survived.** Not the 1851Z lap's fault: it claimed its row 13 seconds before the
finding existed on `origin` (see the root objection). It is nonetheless the first thing
the next lap fixes, because a booth answer that concedes a defect the audit disproved is
the single cheapest way to lose 데이터 해석 points.

**Smallest fix.** Rewrite the bullet to say what the audit established (both brackets are
real runs; the submitted 서식 quoted the real-road 439-series; the defect was a lineage mix
in one paragraph), cite `docs/ssot_audit_2026-09-03.md` §1, and drop the "WFG-004의 일"
hand-off. The gate-window half stays **WFG-041**.

### F9 — **done(1c1561e)**, repo-side half; cadence half stays NH-016 · The critic cannot reach `origin` before the next dev lap, so `CRITIC_LATEST.md` is structurally one lap late

**Where:** `docs/auto/LOOP_CONFIG.json` → `dev_cadence_note`; `docs/auto/CHARTER.md:257-260`;
`docs/auto/ROUTINE_PROMPTS.md` (the critic prompt's "under 40 minutes" budget).

**What is wrong.** `dev` at `17 */2` and `critic` at `47 1-23/2` put the critic's start 90
minutes after a dev lap and **30 minutes** before the next one. A critic lap that runs the
full gates (2 minutes), re-runs pytest for a census reading (2 minutes), reads a window and
writes findings does not finish in 30 minutes: critic #1 took 34, this lap started 19:47
against a 20:17 dev lap, and the prompt's own instruction ("keep the whole lap under 40
minutes so your findings are on `auto/dev` before the next dev lap starts at the next even
hour :17") is self-contradictory, since 19:47 + 40 = 20:27. CHARTER §11's guarantee rests
on this margin.

**Smallest fix, repo-side and available to the next dev lap.** Add one sentence to
CHARTER §4 step 3: *after pushing the claim and before building, re-fetch and re-read
`docs/auto/CRITIC_LATEST.md`; if it changed since the lap started, clear its
`fix-before-next-row` items first.* That closes the race without touching the schedule and
costs the dev lap one `git fetch`. The cadence half is author-only (the cron lives on the
routine, not in this repository) and is filed as **NH-016**; moving the critic to odd
hours `:17` would give it 120 minutes instead of 30.

---

## fix-this-sprint

### F11 — **open**, filed as WFG-045 · `paper/manuscript.md` ships 21 citations and has no `## References` section, and nothing checks the section list

**Where:** `paper/manuscript.md` (sections present: Abstract, 1 Introduction, 2 Related
work, 3 Data and methods, 4 Results, 5 Discussion, 6 Limitations, 7 Conclusion, Data and
code availability); `paper/check_paper.py`.

**What is wrong.** CHARTER §12 lists the required sections and ends the list with
"References". The manuscript has none. `check_paper.py` counts words, figures, tables,
references and gaps, and contains no section check at all (`grep -n 'References\|sections'
paper/check_paper.py` returns nothing), so the gate that exists to hold §12 true has never
looked at the one structural requirement §12 states. A 7,204-word manuscript that cites 21
works and prints no bibliography is not a submittable artifact, and 출처 명기 is a scored
row in both rubric tracks.

**Smallest fix.** Add `## References` to the manuscript (rendered from `references.bib`,
as `build_docx.py` already does for the `.docx`), and add one assertion to
`check_paper.py` that every §12 section heading is present. Filed as **WFG-045**.

### F7 — **done(1c1561e)** · Three live lines still carry the retired finals date

**Where:** `docs/auto/CHARTER.md:11` ("in priority order until 2026-10-18"),
`docs/auto/RUBRIC.md:20` ("당일 10.18 참가자 등록 후"), `docs/auto/NEEDS_HUMAN.md:72`
("the 10-10 freeze are set against 10.18").

**What is wrong.** Unchanged from critic #1, verified again this lap. NH-006 is closed on
10-24 / 10-16. `KCF_READINESS` R11 requires every date in `docs/auto/` to read 10-16 and
10-24, so R11 fails today on the two documents every lap is told to read first.

**Smallest fix.** Correct the three lines; annotate rather than delete inside NH-006, which
is a record. The `research/sweeps_2026-09-03/*` files predate the decision and keep their
text.

### F5 — **open**, filed as WFG-043 / NH-015 · The README's motivation paragraph still claims a burned area larger than the nationwide total

**Where:** `README.md:191-194` (Korean) and `README.md:486-491` (English).

**What is wrong.** Unchanged. Both still attribute ~116,000 ha to the 의성→안동→청송→영양→영덕
chain alone, against a nationwide March-May 2025 figure of about 104,788 ha and the WWA
report's ~48,000 ha for the fires it analysed. Correctly filed as **WFG-043** with the
author's sources asked for in **NH-015**; restated here only because it is the first
paragraph a judge reads and it is still falsifiable in one search.

### F12 — **open**, filed as WFG-044 · The paper routine has no report kind, so its report is filed as `manual` and `STATE.json` now says the last lap was manual

**Where:** `scripts/auto/report.py:123` (`choices=["dev","critic","research","kickoff","red","manual"]`);
`docs/auto/reports/2026-09-03T1928Z-manual.md`; `docs/auto/STATE.json` →
`"last_report_kind": "dev"` was overwritten to `manual` by that run.

**What is wrong.** CHARTER §2 and §12 define a fourth routine whose reports the loop reads,
and the reporting tool cannot name it. Consequences already visible: the report file is
`*-manual.md` while its own title line says `· paper ·`; a lap resolving its predecessor by
kind (this critic prompt's own `SINCE=$(git log --grep='critic' -- docs/auto/reports)`
pattern) cannot find paper laps at all; and the dashboard timeline labels a paper lap
"manual". The same report's title stamp (`2026-09-03T1955Z`) disagrees with its own `when`
row (19:28 UTC) and its filename (`1928Z`), so three timestamps for one lap are committed.

**Smallest fix.** Add `"paper"` to the `--kind` choices and let the paper lap pass it; let
the title default to the same stamp the filename uses instead of accepting a hand-typed
one. Filed as **WFG-044**.

---

## note

- **N7 (new) · The suite census, measured cold and warm on one tree, and what it makes
  cheap.** At `0ff1b36`: COLD `1121 passed / 61 skipped`, WARM re-run `1127 passed / 55
  skipped`, **collected 1182 in both**. The delta is exactly the six SRTM-gated tests
  WFG-039 names. Two things follow for **WFG-038**, which asks for a `(collected, passed,
  skipped)` triple as a gate: `collected` is the component that is actually invariant, so
  gating on it alone is both cheap and sufficient for "no test was lost"; and `passed` is
  not even portable across environments, since this lap's cold run also skips
  `test_the_committed_digest_still_matches_the_pdf` (the survey PDF lives under the
  git-ignored `data/raw/`), which passed for the 1851Z lap that had downloaded it. That is
  why this lap reads 1127/55 where the 1851Z gate read 1128/54 on the same suite.
- **N9 (new, correcting critic #1) · F2's remedy text was wrong and must not be applied.**
  Critic #1 wrote that "the WildfireSpreadTS dataset paper is arXiv:2406.04759 (NeurIPS
  2024 Datasets & Benchmarks)". Verified this lap at the NeurIPS proceedings: it is
  **NeurIPS 2023** Datasets & Benchmarks, *Advances in Neural Information Processing
  Systems* 36:74515-74529
  (`proceedings.neurips.cc/paper_files/paper/2023/hash/ebd545176bdaa9cd5d45954947bd74b7-Abstract-Datasets_and_Benchmarks.html`).
  The paper lap's committed entry (`paper/references.bib:16-22`, `year = {2023}`, Crossref
  DOI `10.52202/075280-3258`) is **correct**. This note exists so no later lap "fixes" a
  right entry back to a wrong one. One cosmetic residue: the key is `wildfirespreadts2024`
  while its own `year` is 2023; rename to `wildfirespreadts2023` when the file is next
  touched.
- **N2 and N4 are closed.** `F3_regions.png` is now referenced once in `manuscript.md`, and
  SRTM (`farr2007`), ESA WorldCover (`worldcover`) and OpenStreetMap (`osm`) all have bib
  entries. `references.bib` is 21 entries, each carrying a `verified` note.
- **N5 (carried) · `docs/auto/BACKLOG.md` WFG-014 ("Paper skeleton in `paper/`") is still
  `todo`** while the manuscript it describes is 7,204 words with 7 figures. It was stale
  after `fec353e`; after `0ff1b36` it is plainly wrong. Mark it `done(0ff1b36)`.
- **N10 (new) · `paper/STATE.json` → `last_incorporated_commit: e558ebd` is correct and
  should not be "corrected".** The paper lap built on `fc09db7` but genuinely did not
  incorporate the WFG-020 survey evidence, so the next paper lap will correctly see work to
  do. Recorded because the value looks like a stale-head bug and is not one.
- **N11 (new) · The Greenpeace evidence card is the strongest artifact this loop has
  produced, and its own gate says so honestly.**
  `tests/test_greenpeace_evidence.py:150-171` documents, with the mutation that shows it,
  that membership-in-any-cell is weaker than membership-in-the-cited-cell (48.0 → 47.0
  survives, because 47.0 is a real cell in 표 1-5). Every arithmetic relation in
  `docs/evidence/greenpeace_2026_survey.md` §3 re-derives independently this lap
  (291 = 246+9+8+7+21; 269/299 = 90.0 %; 185/297 = 62.3 %; 53/296 = 17.9 %; 표 1-1's four
  regional rows sum to the 전체 row). The one figure quoted in §4 and in JUDGE_QA Q17 that
  §3's "인용하는 수치" table does not list is 영덕's 80세 이상 **34.0 %**; it is in the
  artifact (`표 1-1` 영덕 34/100) and pinned by the bare-percent test, so this is a
  completeness nit in §3, not a traceability hole.

---

## The judge drill

`JUDGE_QA.md` changed this window (Q17's answer was rewritten onto the new artifact), so
the drill ran against the changed block.

- **"영덕 응답자의 34 %가 80세 이상이라고 하셨는데, 그 표는 근거 문서 §3에 없습니다."** The
  answer exists (`data/processed/evidence/greenpeace_2026_survey.json`, 표 1-1, 영덕 34/100,
  base 100) but the student would have to open the JSON to find it, because the evidence
  card's own citation table stops at the 전체 row. Add the 표 1-1 regional row to §3. Not
  added to the bank: it is a documentation nit, not a question a judge can win on.
- **"이 조사 수치는 왜 레지스트리에 없습니까?"** Answered, well, at
  `docs/evidence/greenpeace_2026_survey.md` §6 and in Q17's "없는 것" block. The bank needs
  no new entry.
- The question critic #1 declined to add (116,000 ha vs 104,788 ha) is **still unanswerable**
  and still correctly withheld. It becomes addable the lap WFG-043 closes.

---

## What five lenses converged on

| lens | verdict | the one load-bearing reason |
|---|---|---|
| KCF judge · SW professor | pass | The window's two laps each took an independent reviewer's block or objection and fixed it rather than arguing; the census is now labelled cold vs warm. The loop's weakness is its clock (F9), not its judgement. |
| KCF judge · 재난 대응 공무원 | **fail**, unchanged | The booth script's first section still concedes a false error (F1). Second lap in a row. |
| fire-behaviour scientist | **fail**, unchanged | The sentence that frames why the project exists still carries a burned area larger than the national total (F5). |
| ML reviewer (leakage, baselines) | pass, with reservation | The paper lap's reviewer found the real hole (the 42-of-458 shift is graded against the system's own predicted field) and it is now the first paragraph of Limitations with G4 naming the arm that settles it. Nothing here is oversold. The reservation is F11: 21 citations, no bibliography. |
| statistician | pass | The survey card refuses to attach confidence intervals to a non-probability sample, names the survivor-selection structure, refuses the car-less-equals-immobile reading, and its gate's docstring states its own limit. This is the most statistically careful document in the repository. |

**Where they agree:** nothing found this window requires an experiment to be redone, and
neither failing verdict is new. Both failures are *carried* items, which is the point of
the root objection: the loop is producing good work and failing to close its own loop.

**Where they split:** L1 credits the reviewer mechanism; L2 and L3 observe that the two
findings the mechanism produced first are the two still open.

**The question that resolves the split:** *does a `fix-before-next-row` item ever reach a
dev lap before that lap picks its row?* One data point exists and it is negative. F9's
one-sentence charter fix is the cheapest way to make the answer yes, and the next lap can
make it while it is fixing F1.
