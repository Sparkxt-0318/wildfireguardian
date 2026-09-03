# Critic verdict on the latest dev laps

Overwritten by every critic lap (history is in `docs/auto/reports/*-critic.md`). The
next dev lap clears every `fix-before-next-row` item here before claiming a row.

**Lap: 2026-09-03T1748Z (critic #1).** Scope: no previous critic report exists, so the
window is the last 26 hours — `25f1e14..1113388`, 33 commits, six dev reports, one
research brief, the new `paper/` tree. Gates re-run independently: `gates.py --mode
full` **exit 0** (verify PASS, snapshot-verify PASS, env-check PASS, pytest 1108
passed / 60 skipped, `baseline-verify` WARN as expected off-laptop). `paper/check_paper.py`
**exit 0**. The dev laps' green claims are true. Every finding below is something the
gates cannot see.

**Root objection (the one that makes the others moot).** The project's headline claim
is that every number traces to a committed artifact. That claim is enforced only where
a registry key exists — and the numbers that *frame the project to a judge*, in the
first paragraph a judge reads, have no key, no URL and no gate. `README.md:192-194`
and `README.md:486-491` assert 27 deaths, ~116,000 ha burned and 4,000+ homes destroyed,
sourced to "한겨레·세계일보·서울환경연합" with no link. None of the three resolves against
`docs/NUMBERS.json`. One of them is falsifiable in a single search (F5). The most
audited repository in the fair opens with its least audited numbers.

---

## fix-before-next-row

### F1 · `docs/auto/JUDGE_QA.md:46` still tells the student to concede an error the last lap disproved — and the new lineage gate passes it by accident

**Where:** `docs/auto/JUDGE_QA.md:46-48`; gate at `tests/test_rescue_lineage_ssot.py:104-179`.

**What is wrong.** The 1724Z lap established that `README.md:731`'s "6 → 34" is a real
committed value of the superseded 452-series, not a typo, and corrected that in four
places: `README.md`, `docs/submission_reconciliation.md` (row 8 and the spoken line),
`docs/HANDOFF_ROUND3.md` ×2, and the two research files. **`JUDGE_QA.md` was missed.**
Its §0 — the section headed "제출본과 현재 값이 다른 지점", the two things it tells the
student a judge will touch first — still reads (the bracket quoted below belongs to the
superseded, pre-flip **452-series** synthetic baseline; canonical real-road run is 6 → 66):

> **`README.md:731`은 서식이 아니라 저장소 쪽이 틀린 유일한 자리입니다** — 지연 행을 "6 → 34"로
> 적었지만 `rescue_verify.json`의 값은 `rescue_unreachable_delay_row_cutoff_0p7`입니다. 고치는
> 것은 WFG-004의 일입니다.

Two defects in three lines. It asserts the repository was wrong where it was not, in the
one document whose job is to prepare spoken booth answers; and it hands off to WFG-004,
which is `done(20260903T1622Z)`.

**Why no gate caught it.** `test_every_prose_mention_of_the_synthetic_bracket_names_its_lineage`
does match this line — `SYNTHETIC_MENTION` fires on `"6 → 34"`. It then accepts the line
because `LINEAGE_LABEL` is searched over a **±2-line window**, and line 45, in a *different
bullet about a different quantity* (the 459-series 438/18/3 split), happens to contain the
word **폐기**. Verified by mutation this lap: change 폐기된 → 버려진 on line 45, leaving line
46 untouched, and the gate fails naming `docs/auto/JUDGE_QA.md:46`. Restore it and the gate
goes green again. This is the same failure the independent reviewer blocked at 1724Z — a
judge-facing file exempted by an incidental keyword — surviving at a different granularity,
in the same file the gate's own comment names as the one that used to slip through.

**Smallest fix.** Rewrite the `README.md:731` bullet in `JUDGE_QA.md` §0 to say what the
audit established (both brackets are real runs; the submitted form quoted the real-road
439-series; the defect was a lineage mix in one paragraph), citing
`docs/ssot_audit_2026-09-03.md` §1, and drop the "WFG-004의 일" hand-off. The gate-window
half is bigger than a fix and is filed as **WFG-041**.

### F2 · `paper/references.bib` marks a citation `verified` whose title and authors are not the paper at that URL

**Where:** `paper/references.bib:4-11`; used at `paper/manuscript.md:13`.

**What is wrong.** The entry `wildfirespreadts2025` gives title *"WildfireSpreadTS: A
dataset of multi-modal time series for wildfire spread prediction"*, authors Gerard, Zhao
and Sullivan, `url = https://arxiv.org/abs/2502.12003`, and `note = {verified 2026-09-03
(research sweep R3)}`. Opened this lap: **arXiv:2502.12003 is "Improved Wildfire Spread
Prediction with Time-Series Data and the WSTS+ Benchmark", by Lahrichi, Bova, Johnson and
Malof (WACV 2026)** — a different paper by different authors, which *builds on* WSTS rather
than introducing it. The WildfireSpreadTS dataset paper is arXiv:2406.04759 (NeurIPS 2024
Datasets & Benchmarks).

This is the failure mode CHARTER §5 names first ("no fabricated citations"), inside the
only related-work citation the manuscript has, carrying a `verified` note. `check_paper.py`
cannot catch it: it checks that the key exists and that the note contains the word
"verified" — never that the metadata matches the URL. An ML reviewer or a KCF 제출 자료
row (출처 명기) would find it by clicking once.

**Smallest fix.** Either correct the entry to arXiv:2406.04759 with the Gerard/Zhao/Sullivan
metadata, or keep 2502.12003 with the Lahrichi et al. title and authors — whichever the
sentence at `manuscript.md:13` actually means. Re-open the URL and put the fetched title in
the `note`. The gate half is filed as **WFG-042**.

### F3 · `paper/manuscript.md:9` attributes a death toll to a source that gives a different one

**Where:** `paper/manuscript.md:9`.

**What is wrong.** "The March 2025 Gyeongbuk wildfires killed 27 people … [@wwa2025korea]".
The World Weather Attribution report at that URL, opened this lap, says: *"With 32
casualties, the fires are also South Korea's deadliest wildfires on record"*, with 26 of
those in 의성군, ~48,000 ha burned and ~5,000 buildings lost. It does not carry 27. The
repository's own README sources 27 to 한겨레·세계일보·서울환경연합 — three sources the
manuscript does not cite — and carefully footnotes that "30명 이상" is the different,
nationwide scope. The manuscript drops that footnote and pins the narrower number to a
source that reports the wider one.

**Smallest fix.** Move `[@wwa2025korea]` to a clause it supports (the climate-attribution
statement), and cite 27 to the sources the README names once they carry URLs (F5 /
**WFG-043**). Carry the README's scope footnote into the manuscript.

### F4 · Two live backlog rows share the ID `WFG-036`, and they are different work

**Where:** `docs/auto/BACKLOG.md:48` and `:64`; details at `:451`. Referenced as the final
product by `CHARTER.md:266`, `KCF_READINESS.md:5,18`, `BACKLOG.md:25,29`.

**What is wrong.** `WFG-036` is simultaneously **P0 · KCF · Final product bundle
`release/kcf-finals-2026/`** (added by the sprint commit `42818ec`) and **P1 · infra ·
`build_numbers.py` would destroy the registry it claims to build** (added by the research
re-key `d88c85b`). The only `### WFG-036` details section in the file is the *infra* one.
So the sprint plan's "09-10 | WFG-036 | final product bundle v1" resolves, for any lap that
reads the details section, to the `build_numbers.py` fix. The 1724Z lap resolved the
WFG-037/038 collision and did not see this one.

**Fixed this lap**, because a duplicate ID is the one thing this file is supposed not to
contain: the **infra** row is renumbered **WFG-040**, keeping `WFG-036` for the final
product, which is hard-referenced in three other files. One stale back-reference remains in
`docs/auto/reports/2026-09-03T0653Z-dev.md`, which is a historical record and is not edited.

---

## fix-this-sprint

### F5 · The README's motivation paragraph claims a burned area larger than the nationwide total

**Where:** `README.md:193` (Korean) and `README.md:488` (English) — both inside the Round-3
section, so both editable; the Round-2 record is untouched.

**What is wrong.** Both lines attribute **~116,000 ha** to the 의성→안동→청송→영양→영덕 chain
alone. Public reporting puts the **nationwide** March–May 2025 total (347 fires) at about
**104,788 ha**, and the WWA report gives ~48,000 ha for the fires it analysed. A sub-scope
figure larger than every national figure available is falsifiable by a judge in one search,
in the paragraph that states why the project exists. The same paragraph already carries a
careful scope footnote for the 27-vs-30+ death toll and none for the hectares. None of the
three figures (27 / 116,000 ha / 4,000+ homes) has a registry key or a URL.

**Smallest fix.** Open the three named sources, record which figure each gives and its
scope, register the values, and add the scope footnote the death-toll pair already has —
or replace with the 산림청 figure and say so. Filed as **WFG-043**; the author's own
sources are asked for in **NH-015**.

### F6 · `paper/STATE.json` states counts that its own gate contradicts

**Where:** `paper/STATE.json`.

**What is wrong.** It reads `last_incorporated_commit: null`, `body_words: 0`, `figures: 0`,
`references: 0`, `gaps: 0`. `check_paper.py` on the same tree prints `body_words: 605,
figures: 2, references: 4, gaps: 12`. The paper scaffolding was committed at `fec353e`
and the state file was never written. CHARTER §12 makes this file the paper lap's early-exit
test, so it is not decoration: it is the loop's record of what has been incorporated, and it
is false. Nothing gates it.

**Smallest fix.** Have `check_paper.py` (or the paper lap) write `STATE.json` from the same
`info` dict it already computes, and set `last_incorporated_commit` to the head it ran on.

### F7 · `docs/auto/CHARTER.md:11` and `docs/auto/RUBRIC.md:20` still carry the retired finals date

**Where:** `CHARTER.md:11` ("in priority order until 2026-10-18"), `RUBRIC.md:20`
("당일 10.18 참가자 등록 후"), and `NEEDS_HUMAN.md:72` ("the 10-10 freeze are set against 10.18").

**What is wrong.** NH-006 is closed: the author decided **2026-10-24**, freeze **2026-10-16**.
The charter's own §1 table says 10-24 two lines below §1's prose saying 10-18. `KCF_READINESS`
R11 requires every date in `docs/auto/` to read 10-16 and 10-24, so these three lines are R11
failing today, in the two documents every lap is told to read first.

**Smallest fix.** Correct the three lines; annotate rather than delete inside NH-006, which is
a record. The `docs/auto/research/sweeps_2026-09-03/*` files are dated artifacts of a scan run
before the decision and should keep their text.

### F8 · Every suite baseline the loop has recorded is an unlabelled mixture of two quantities

**Where:** `docs/auto/BACKLOG.md` WFG-038 / WFG-039; readings in all six dev reports.

**What is wrong.** WFG-039 established the cause (an SRTM tile downloaded mid-run, so six
tests skip on a cold container and pass on every run after). The consequence is broader than
the row states and is worth naming plainly: the recorded baselines 1065/51, 1077/54, 1081/54,
1088/60, 1094/54, 1106/54 and this lap's 1108/60 are a mixture of first-run and re-run
readings, so the cross-lap count comparison the loop uses as its "no test was lost" evidence
has been comparing different quantities the whole time. This is an internal-validity hole in
the loop's own instrument, not a nuisance. The rows are correctly filed and correctly
prioritised; this entry exists so the next lap does not cite a raw count as evidence until
they land.

**Smallest fix.** None here — WFG-038 and WFG-039 are the fix. Until then, reports state
whether a reading is cold or warm.

---

## note

- **N1 · `KCF_READINESS.md` R5 names a test file that does not exist.** It cites
  `tests/test_judge_qa.py`; the file is `tests/test_judge_qa_bank.py`. Corrected this lap.
- **N2 · `paper/figures/F3_regions.png` is built and committed but referenced by nothing.**
  `make_figures.py:128` produces it; `manuscript.md` never uses it. `check_paper.py` verifies
  that referenced figures exist, not that committed figures are referenced. Harmless today;
  it becomes a 제출 자료 finding if it ships in the bundle unexplained.
- **N3 · `paper/manuscript.md` has no `## References` section**, which CHARTER §12 lists among
  the required sections. The `.docx` build may render the bibliography; the markdown does not.
- **N4 · SRTM, ESA WorldCover and OpenStreetMap are named in `manuscript.md:19` with no bib
  entries**, while FIRMS and ERA5 have them. 출처 명기 is a scored row in both rubric tracks.
- **N5 · `docs/auto/BACKLOG.md` WFG-014 ("Paper skeleton in `paper/`") is still `todo`** though
  `fec353e` built it. Not a defect in the work, but the backlog is the loop's own state.
- **N6 · Reports before `a131daf` carry no `Reviewed by:` line, and that is correct.** The
  `review: subagent` key did not exist until that commit. Both reports written after it
  (1622Z, 1724Z) record a verdict, and both verdicts were `block` acted on rather than argued.
  The independent review is working; this note exists so a later lap does not read the four
  earlier reports as skipped verdicts.

---

## The judge drill, and the one question I did not add to the bank

`JUDGE_QA.md` changed this window, so the drill ran. It produced one question the bank
cannot currently answer:

> "README 첫 문단은 경북 산불 피해면적을 약 116,000 ha로 적었습니다. 2025년 3월–5월 **전국**
> 산불 피해면적 합계로 공개된 값은 약 104,788 ha입니다. 어느 쪽이 맞습니까?"

I did **not** add it to the bank. An answer requires a sourced value that does not exist yet
(F5), and CHARTER §5 forbids writing one that cannot be registered. Adding it would also
collide with the §0 rewrite F1 asks for. The lap that closes WFG-043 should add it then, with
its 근거 line, and update the tier counts and the §6 drill table together — the four
`test_judge_qa_bank.py` invariants pin all of them.

---

## What five lenses converged on

| lens | verdict | the one load-bearing reason |
|---|---|---|
| KCF judge · SW professor | pass, with reservation | The gate discipline is real and unusual for this level; the newest gate is green for an accidental reason (F1). |
| KCF judge · 재난 대응 공무원 | **fail** | The document that prepares spoken booth answers still instructs a concession that is false (F1). |
| fire-behaviour scientist | **fail** | The sentence that frames why the project exists carries a burned area larger than the national total (F5). |
| ML reviewer (leakage, baselines) | mixed | The evaluation is genuinely event-held-out and the negative results are kept; the only related-work citation is not the paper at its URL (F2). |
| statistician | pass | n = 6 is treated honestly throughout — zero-TP folds, pooled vs mean-of-folds, no threshold guarantee; the exposure is the loop's own suite instrument (F8). |

**Where they agree:** the substance is stronger than the labels on it. Every failing verdict
is about a sentence or a citation, not about a method or a result. Nothing found this window
requires an experiment to be redone.

**Where they split:** L1 calls the gates the project's strongest asset; L4 and L5 say two of
them are green for reasons unrelated to the property they name (F1, F8).

**The question that resolves the split:** *for each gate the loop cites as evidence, does a
seeded counterexample actually fail it?* The 1622Z lap answered yes for the purge gate by
running two mutations. The 1724Z lap answered yes for the lineage gate against the reviewer's
two counterexamples — but not against the file its own comment names, which is where it fails
(F1). Making a seeded-mutation proof mandatory for every new gate, recorded in the report, is
the single change that would close this.
