# Critic verdict on the latest dev laps

Overwritten by every critic lap (history is in `docs/auto/reports/*-critic.md`). The
next dev lap clears every `fix-before-next-row` item here before claiming a row.

**Lap: 2026-09-03T2147Z (critic #3).** Scope: `1c1561e..8d1decf`, the four commits since
critic #2's report landed, which is the WFG-021 dev lap (2053Z). No paper lap in the
window, so `check_paper.py` was not run; `paper/` is untouched. `docs/auto/JUDGE_QA.md`
is untouched, so the judge drill did not run.

**Gates, re-run independently at `8d1decf`: `gates.py --mode full` exits 1. `auto/dev` is
RED right now.** `1 failed, 1152 passed, 62 skipped` in 167 s. verify PASS,
snapshot-verify PASS, env-check PASS, `baseline-verify` WARN as expected off-laptop
(5 differences, all additions or git-ignored raw manifests; soft step, `hard: false`).
The failure is `tests/test_rescue_lineage_ssot.py::test_every_prose_mention_of_the_synthetic_bracket_names_its_lineage`
on the dev lap's own report. The 2053Z report records `Reviewed by: subagent (block)`
at line 169 and acts on it rather than arguing, so the review discipline held.

**Root objection.** The 2053Z lap spent itself on one lesson, wrote that lesson into
CHARTER §4 step 8, filed WFG-046 to make it mechanical, recorded it in MEMO as
"the report is the one file in every lap that no gate has read", and then pushed a
branch that no gate had read. Not only the report: the gate run it calls **ALL GREEN**
happened at `f5f8498` (20:39:36Z), and the two commits after it (`e431696` 20:56:49Z,
`8d1decf` 20:57:29Z) changed `tests/test_gk2a_detector.py` by 162 lines,
`docs/detection_floor.md` by 41, and added the report. Those were the reviewer-block
fixes, the largest and least-reviewed edits of the lap, and `gates.py` never saw them.
So the diagnosis in the report is one step too narrow. The unchecked file is not the
report; the unchecked thing is **everything after the gate run**, and WFG-046 as written
would not have caught it, because it only gates what `report.py` itself writes. The fix
is smaller than WFG-046 and strictly stronger: `.auto/gates.json` already records
`git_head`. Refuse to push when it is not `HEAD`. Three lines, one failure class, gone.

---

## fix-before-next-row

### F13 — `auto/dev` is RED at HEAD, and the red is two words of prose

**Where:** `docs/auto/reports/2026-09-03T2053Z-dev.md:194`, inside the
`## In plain terms` block.

**What is wrong.** The line quotes the 폐기된 452계열 bracket, canonical is 6 -> 66, and
neither it nor the two lines either side carries a lineage label.
`tests/test_rescue_lineage_ssot.py` reads a plus-or-minus-two-line window and accepts
`452`, `synthetic`, `합성`, `pre-flip`, `superseded`, `retired`, `legacy`,
`baseline_synthetic`, `폐기`, or the canonical bracket shown beside it. The window at
lines 192 to 196 has none of them, so the gate fires. The value itself is correct: it is
the 폐기된 452계열 pre-flip baseline's own bracket, preserved at
`data/processed/rescue_baseline_synthetic/rescue_verify.json`.

**When it entered.** `e431696`, not `8d1decf`. Verified by replaying the gate's own regex
over the file at all three commits: clean at `f5f8498` (the report did not exist yet),
unlabelled at `e431696` and at `8d1decf`.

**Why it is finding #1.** Third occurrence of one failure class. The 1622Z lap installed
this gate. Critic #2 tripped it at `24751fa`. The 2053Z lap found that, fixed it,
documented it in three places, and tripped it again in the same lap that documented it.
That is not carelessness twice over, it is a missing mechanical check, which is F14.

**Smallest fix.** One annotation inside the gate's window, in the report, which is a
record and so is repaired by annotation rather than rewriting, exactly as `1c1561e` did:
make line 194 read `asks about the "6 → 34" number (폐기된 452계열 합성 baseline; 정본은
6 → 66), the honest answer is that both versions are real runs,`. That replacement text
is itself clean under both gates, so it can be copied verbatim. Then
`.auto/venv/bin/python -m pytest tests/test_rescue_lineage_ssot.py` and
`make check-forbidden`.

**One instruction for the next dev lap, because CHARTER §4 step 2 would otherwise stop
it.** Step 2 says a red baseline means do not build, and fix only if the cause is clearly
environmental. **This red is not environmental and it is not a reason to stop.** It
touches no code, no test, no artifact and no registry entry; it is a parenthetical in one
line of Markdown under `docs/auto/`. Make it the lap's first commit, confirm the suite is
green, then claim a row and build normally. Do not file a NEEDS_HUMAN BLOCKER for it.

### F14 — "ALL GREEN" names a head that is two commits and 200-plus changed lines behind what was pushed

**Where:** `docs/auto/reports/2026-09-03T2053Z-dev.md:207`
(`**ALL GREEN** · mode `full` · head `f5f8498` · 2026-09-03T20:52:29Z`);
`docs/auto/BACKLOG.md:72` (WFG-046 as currently scoped);
`scripts/auto/gates.py` (writes `.auto/gates.json`); CHARTER §4 step 8.

**What is wrong.** The sentence is true and it is not the truth a reader takes from it. A
report that says ALL GREEN is read as "this branch is green", and what it certifies is a
head that was superseded seventeen minutes and three files later. The two commits after
the gate run were not cosmetic: `e431696` alone rewrote 162 lines of
`tests/test_gk2a_detector.py` (the whole opt-in network block, group 5) and 41 lines of
`docs/detection_floor.md` (the retraction in §12). Those happen to pass, which this lap
confirmed by running the suite; that they pass is luck, not process.

**Why WFG-046 as filed does not close it.** WFG-046 asks `report.py` to run the prose
gates over what it just wrote. That catches F13. It does not catch a test-file or
source-file edit made after step 5 and before the push, which is what actually happened
here, and which is the more dangerous half because it can change behaviour rather than
prose.

**Smallest fix, and it subsumes WFG-046's own.** `.auto/gates.json` already carries
`"git_head": "8d1decf"` and `"passed": false`. Add to `scripts/auto/gates.py` a
`--assert-head` mode (or a five-line `scripts/auto/check_gates_current.py`) that reads
`.auto/gates.json`, compares `git_head` with `git rev-parse --short HEAD` and
`git status --porcelain`, and exits non-zero unless they agree and `passed` is true. Then
CHARTER §4 step 8 becomes one command instead of a list a tired lap can skip, and the
rule it enforces is the one that is actually load-bearing: **the commit you push is the
commit the gates read.** Widen WFG-046's `done when` to say exactly that.

---

## fix-this-sprint

### F15 — filed as WFG-047 · Two P0 rows are stranded in `in-progress` and no future lap can pick them up

**Where:** `docs/auto/BACKLOG.md:44` (WFG-021,
`in-progress(20260903T2050Z) — (b) done(f5f8498), (a) card + JUDGE_QA block outstanding,
(c) not attempted`) and `docs/auto/BACKLOG.md:47` (WFG-016,
`in-progress(kickoff seed)`); CHARTER §4 step 3 and §5.

**What is wrong.** CHARTER §4 step 3 tells a lap to take the highest-priority row that is
`todo`, agent-doable, unblocked, **and not `in-progress` by another lap**. The 2053Z lap
ended without finishing WFG-021 and left the row `in-progress`, which is honest reporting
and also makes the unfinished two thirds invisible to every lap that follows, because
there is no lap holding the claim any more. `in-progress` is written as a lock and there
is no release. WFG-016 has been in the same state since the kickoff seed.

**Why it costs something.** WFG-021 part (a) is the detection-floor evidence card on the
finals screen. `KCF_READINESS.md` R2 names it by row ID. So a readiness line the product's
definition of done depends on is now blocked by a status word, inside a twelve-day sprint
whose plan dated WFG-021 to 09-05.

**Smallest fix.** Two parts, both cheap. (1) CHARTER §5 gains one sentence: *a lap that
ends without finishing its row sets the row back to `todo` and appends what it did as a
residue note; `in-progress` is only ever held by a lap that is still running.* (2) Set
WFG-021 and WFG-016 to `todo`, keeping their residue text verbatim so nothing is lost.
Filed as **WFG-047**.

### F11 — **open**, unchanged, filed as WFG-045 · `paper/manuscript.md` ships 21 citations and no `## References` section

Carried from critic #2 without re-verification: `paper/` did not change in this window,
so nothing about F11 can have moved. Restated only so it is not read as closed.

### F5 — **open**, unchanged, filed as WFG-043 / NH-015 · The README's motivation paragraph still claims a burned area larger than the nationwide total

**Where:** `README.md:191-194` (Korean) and `README.md:486-491` (English). Third critic lap
in a row. It is the first paragraph a judge reads and it is falsifiable in one search;
it is correctly blocked on the author's sources (NH-015), which is why it is not
`fix-before-next-row`.

### F12 — **open**, unchanged, filed as WFG-044 · `report.py` has no `paper` kind

`scripts/auto/report.py:123` still reads
`choices=["dev","critic","research","kickoff","red","manual"]`. Verified again this lap.

---

## note

- **N12 · The window's actual product is good, and better than its process.**
  `tests/test_gk2a_detector.py` puts 545 lines under a detector that had none and whose
  numbers (+22 / +34 / +64 minutes, 0 of 709 control steps) are quoted on judge-facing
  documents. Group 4 binds six registry keys to
  `data/processed/detection/*.json` so prose cannot drift from the artifact.
  `test_a_contaminated_background_reproduces_the_recorded_yeongdeok_threshold` reads both
  the best-step anomaly and the recorded threshold **out of the artifact** rather than
  typing them, and requires the K = 4 rule to reproduce 21.964 K to the third decimal;
  that is the one test in the file an outside fact decides, and `docs/detection_floor.md`
  §12 says so in its own table. The `contextual_flag` extraction is semantics-preserving:
  compared line by line against the closure it replaced, the conjunction and its operand
  order are identical.
- **N13 · The retraction in `docs/detection_floor.md` §12 is factually correct, and this
  lap re-checked it rather than taking it on trust.** The draft's claim that the sandbox
  could not reach the NOAA GK2A archive was false. Re-fetched this lap:
  `https://noaa-gk2a-pds.s3.amazonaws.com/AMI/L1B/LA/202503/22/02/gk2a_ami_le1b_sw038_la020ge_202503220224.nc`
  returns HTTP 206 on a range request with a full object size of **458,172 bytes**, which
  is the exact figure §12 states. No credentials. Retracting a caveat in writing, in the
  document that leaned on it, is the behaviour CHARTER §3 rule 5 asks for.
- **N14 · The one externally-determined fact in the new test file is checked by nobody by
  default.** Group 5 is `skipif` on `WFG_GK2A_NETWORK_TESTS=1`, and the opt-in is correctly
  argued (a 0.45 MB download mid-suite would move the pass/skip counts this project's gates
  read, which is WFG-039's whole complaint). The consequence is still worth naming: whether
  sw038 is 14-bit and whether its gain is decreasing are the two facts §12 uses to argue
  that the mask hole does not open on real calibration, and no lap and no CI ever checks
  them unless a human sets the variable. Cheapest honest answer is not to un-skip it but to
  name it in WFG-039's opt-in inventory, so the `(collected, passed, skipped)` triple
  WFG-038 wants can account for it deliberately.
- **N15 · Suite census this lap, cold, in a fresh sandbox.** `collected 1215`,
  `1152 passed / 1 failed / 62 skipped` at `8d1decf`, against the 2053Z lap's
  `1159 passed / 56 skipped` at `f5f8498`. The six-test delta is again the SRTM-gated
  block (WFG-039), plus this lap's one real failure. `collected` is invariant across both
  environments for the third consecutive lap, which keeps critic #2's N7 recommendation
  standing: gate on `collected` alone.
- **N16 · `baseline-verify` WARN is unchanged and is not a finding.** Five differences,
  all of them either new tracked artifacts (`evidence/greenpeace_2026_survey.json`,
  `operating_point/per_fire_recall.json`), the registry growing 260 to 296, or the two
  `data/raw/firms_data/*.json` manifests that are git-ignored and cannot exist in a fresh
  clone. The step is `hard: false` for exactly this reason. Recorded so no lap "fixes" it.
- **N17 · WFG-021's row text is a model of how to report a partial row**, and F15 is a
  complaint about the status word, not about the honesty. `(b) done(f5f8498), (a) ...
  outstanding, (c) not attempted` is precisely what a fresh agent needs. Keep the text;
  change only `in-progress` to `todo`.

---

## The judge drill

`docs/auto/JUDGE_QA.md` did not change in this window, so no drill ran. The one question
critic #1 declined to add (116,000 ha against a nationwide 104,788 ha) is still
unanswerable and still correctly withheld; it becomes addable the lap WFG-043 closes.

---

## What five lenses converged on

| lens | verdict | the one load-bearing reason |
|---|---|---|
| KCF judge · SW professor | **fail** | The branch is red at HEAD and its report says ALL GREEN. A professor does not need to read the diff to score that: it is one `git clone` and one `pytest`. Everything else in the window is work I would credit. |
| KCF judge · 재난 대응 공무원 | pass, first time in three laps | The booth script no longer concedes an error the audit disproved (F1 closed at `1c1561e`), and R5 is ticked with evidence. Nothing in this window touched what the official watches, but nothing broke either. |
| fire-behaviour scientist | pass, on this window only | The detector's geometry (15 km target disc, 30 to 80 km background ring, the deliberate 15 to 30 km gap) is now pinned by tests, and 영덕 stays classified 교란 and counted in neither direction. The standing objection (F5, the opening burned-area figure) is not in this diff. |
| ML reviewer (leakage, baselines) | pass | Ran `mandela` over the new suite. Groups 1 to 3 are synthetic and the doc says so in bold; the gains and offsets are the test's own and §12 forbids citing them as GK2A calibration. The one test with outside ground truth reads its targets from the committed artifact, not from a literal. No leakage pattern fires. |
| statistician | pass | `0 of 709` is stated as an upper bound in the artifact caveat, in the registry entry, and in `docs/detection_floor.md` §5: 95 % upper limit near 0.4 % per step, of order 3 per day at 2-minute cadence, measured at four sites in one season. That is the correct treatment of a zero numerator and it is written three times. |

**Where they agree:** the engineering in this window is the strongest single artifact the
loop has produced since the survey evidence card, and it was shipped on a red branch under
a green headline. Four lenses pass on content; the one that fails, fails on process.

**Where they split:** L1 scores the tree a judge would clone. L3, L4 and L5 score the
method a judge would question at the booth. They do not disagree about any fact.

**The question that resolves the split:** *is the commit you push the commit the gates
read?* Today, twice out of the last three laps, no. F14's `--assert-head` check is five
lines and makes the answer yes permanently, and it is worth more than either row it
would have saved.
